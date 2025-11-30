# 펀더멘털 지표 TTM/연도별 조회 기능 설계서

## 1. 개요

### 1.1 목적
펀더멘털 지표를 **연환산(TTM, Trailing Twelve Months)**과 **연도별(Fiscal Year)** 데이터로 함께 조회할 수 있는 기능을 구현합니다.

### 1.2 배경
현재 시스템의 제한사항:
- `period_type`이 DAILY, QUARTERLY, ANNUAL로 분리되어 있어 단일 쿼리로 TTM과 연도별 데이터를 함께 볼 수 없음
- PyKRX에서 제공하는 `trailing_eps`만 TTM 지원, 나머지 지표는 수동 계산 필요
- DART/SEC EDGAR의 분기 데이터를 TTM으로 변환하는 로직 부재

### 1.3 기대 효과
- **투자 분석 향상**: TTM 기반 밸류에이션과 연도별 추세를 동시 비교
- **데이터 활용성 증가**: 단일 API 호출로 다양한 시점의 데이터 조회
- **팩터 계산 정확도**: TTM 기반 팩터(P/E, EV/EBITDA 등) 계산 개선

---

## 2. 현재 인프라 분석

### 2.1 데이터베이스 스키마 (`ticker_fundamentals`)

```sql
-- 현재 Primary Key
PRIMARY KEY (ticker, region, date, period_type)

-- 기존 period_type 값
- 'DAILY'      -- 일일 밸류에이션 (PER, PBR, 배당수익률)
- 'QUARTERLY'  -- 분기 재무제표 (매출, 순이익 등)
- 'ANNUAL'     -- 연간 재무제표
```

### 2.2 현재 데이터 소스

| 소스 | 지역 | 주기 | 제공 지표 | TTM 지원 |
|------|------|------|----------|---------|
| **PyKRX** | KR | Daily | PER, PBR, EPS, BPS, DPS, 배당수익률 | ✅ trailing_eps만 |
| **DART** | KR | Q/A | 매출, 영업이익, 순이익, 자산, 부채 | ❌ 수동계산 필요 |
| **SEC EDGAR** | US | Q/A | 10-Q, 10-K 재무제표 전체 | ❌ 수동계산 필요 |
| **yfinance** | Global | Snapshot | 40+ 지표 | ✅ trailing 값 일부 |

### 2.3 현재 API 엔드포인트

```python
# MCP Tool: query_fundamentals
# - period_type: ANNUAL | QUARTERLY | DAILY (단일 선택)
# - periods: 1-10 (최근 N개 기간)

# DataAdapter.get_fundamentals()
async def get_fundamentals(
    tickers: List[str],
    fields: List[str],
    period_type: str = "ANNUAL",  # 단일 선택만 가능
    periods: int = 1,
    region: str = "KR"
) -> Dict[str, List[Dict]]
```

---

## 3. 설계 제안

### 3.1 새로운 Period Type 추가

```sql
-- period_type 확장
- 'DAILY'      -- 기존: 일일 밸류에이션
- 'QUARTERLY'  -- 기존: 분기 재무제표
- 'ANNUAL'     -- 기존: 연간 재무제표
- 'TTM'        -- 신규: 연환산 (최근 4분기 합산)
```

### 3.2 데이터 모델

#### 3.2.1 TTM 데이터 구조

```python
@dataclass
class FundamentalsTTM:
    """TTM 연환산 데이터"""
    ticker: str
    region: str
    as_of_date: date              # TTM 계산 기준일

    # 손익계산서 (합산 지표)
    revenue_ttm: Decimal          # 최근 4분기 매출 합계
    operating_income_ttm: Decimal # 최근 4분기 영업이익 합계
    net_income_ttm: Decimal       # 최근 4분기 순이익 합계
    ebitda_ttm: Decimal           # 최근 4분기 EBITDA 합계

    # 재무상태표 (최신 시점)
    total_assets: Decimal         # 최신 분기 총자산
    total_equity: Decimal         # 최신 분기 총자본
    total_debt: Decimal           # 최신 분기 총부채

    # 파생 비율 (TTM 기반 계산)
    roe_ttm: Decimal              # 순이익TTM / 평균자본
    roa_ttm: Decimal              # 순이익TTM / 평균자산
    operating_margin_ttm: Decimal # 영업이익TTM / 매출TTM
    net_margin_ttm: Decimal       # 순이익TTM / 매출TTM

    # 메타데이터
    quarters_included: List[str]  # 포함된 분기 목록 ["2024Q1", "2024Q2", ...]
    data_completeness: float      # 데이터 완성도 (0.0 ~ 1.0)
    calculated_at: datetime       # 계산 시점
```

#### 3.2.2 통합 조회 응답 구조

```python
@dataclass
class FundamentalsUnified:
    """TTM + 연도별 통합 응답"""
    ticker: str
    region: str
    currency: str

    # TTM 데이터
    ttm: Optional[FundamentalsTTM]

    # 연도별 데이터 (최근 N년)
    annual: List[FundamentalsAnnual]  # [{fiscal_year: 2024, ...}, ...]

    # 비교 분석
    comparison: FundamentalsComparison
```

### 3.3 TTM 계산 로직

#### 3.3.1 손익계산서 지표 (합산)

```python
def calculate_ttm_income_statement(
    quarterly_data: List[Dict],
    as_of_date: date
) -> Dict:
    """
    최근 4분기 손익계산서 지표 합산

    Example:
        Q4 2024: revenue=100, net_income=10
        Q3 2024: revenue=95,  net_income=9
        Q2 2024: revenue=90,  net_income=8
        Q1 2024: revenue=85,  net_income=7

        TTM Revenue = 100 + 95 + 90 + 85 = 370
        TTM Net Income = 10 + 9 + 8 + 7 = 34
    """
    # 합산 대상 지표
    SUM_METRICS = [
        'revenue', 'operating_income', 'net_income',
        'ebitda', 'interest_expense', 'depreciation',
        'operating_cash_flow', 'capex', 'fcf'
    ]

    # 최근 4분기 선택 (as_of_date 기준 과거 12개월)
    recent_4q = select_recent_quarters(quarterly_data, as_of_date, n=4)

    ttm_data = {}
    for metric in SUM_METRICS:
        values = [q.get(metric) for q in recent_4q if q.get(metric) is not None]
        if len(values) == 4:
            ttm_data[f'{metric}_ttm'] = sum(values)
        else:
            ttm_data[f'{metric}_ttm'] = None  # 불완전 데이터

    return ttm_data
```

#### 3.3.2 재무상태표 지표 (최신값)

```python
def calculate_ttm_balance_sheet(
    quarterly_data: List[Dict],
    as_of_date: date
) -> Dict:
    """
    재무상태표는 시점 데이터이므로 최신 분기 값 사용

    Note: 자산/부채/자본은 누적값이므로 합산하지 않음
    """
    # 최신값 사용 지표
    POINT_IN_TIME_METRICS = [
        'total_assets', 'current_assets', 'total_liabilities',
        'current_liabilities', 'total_equity', 'total_debt',
        'cash_and_equivalents', 'inventory', 'accounts_receivable'
    ]

    latest_quarter = select_recent_quarters(quarterly_data, as_of_date, n=1)[0]

    return {metric: latest_quarter.get(metric) for metric in POINT_IN_TIME_METRICS}
```

#### 3.3.3 파생 비율 계산

```python
def calculate_ttm_ratios(
    ttm_income: Dict,
    ttm_balance: Dict,
    quarterly_data: List[Dict]
) -> Dict:
    """
    TTM 기반 파생 비율 계산

    Note: 평균 자산/자본은 (기초 + 기말) / 2 로 계산
    """
    # 평균 자산/자본 계산 (4분기 전 vs 현재)
    avg_assets = calculate_average(
        quarterly_data[-1].get('total_assets'),
        quarterly_data[0].get('total_assets')
    )
    avg_equity = calculate_average(
        quarterly_data[-1].get('total_equity'),
        quarterly_data[0].get('total_equity')
    )

    ratios = {}

    # ROE (TTM)
    if ttm_income.get('net_income_ttm') and avg_equity:
        ratios['roe_ttm'] = ttm_income['net_income_ttm'] / avg_equity

    # ROA (TTM)
    if ttm_income.get('net_income_ttm') and avg_assets:
        ratios['roa_ttm'] = ttm_income['net_income_ttm'] / avg_assets

    # 마진 (TTM)
    if ttm_income.get('revenue_ttm'):
        revenue = ttm_income['revenue_ttm']
        if ttm_income.get('operating_income_ttm'):
            ratios['operating_margin_ttm'] = ttm_income['operating_income_ttm'] / revenue
        if ttm_income.get('net_income_ttm'):
            ratios['net_margin_ttm'] = ttm_income['net_income_ttm'] / revenue

    return ratios
```

### 3.4 API 확장 설계

#### 3.4.1 MCP Tool 확장: `query_fundamentals_unified`

```python
def get_fundamentals_unified_tool_def() -> Tool:
    """TTM + 연도별 통합 조회 Tool"""
    return Tool(
        name="query_fundamentals_unified",
        description=(
            "Get unified fundamental data with both TTM (Trailing Twelve Months) "
            "and annual fiscal year data for comparison analysis. "
            "Supports KR, US markets with quarterly data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols (max 20)",
                    "maxItems": 20
                },
                "include_ttm": {
                    "type": "boolean",
                    "description": "Include TTM (Trailing 12 Months) calculations",
                    "default": True
                },
                "annual_periods": {
                    "type": "integer",
                    "description": "Number of annual periods (1-5 years)",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3
                },
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["income", "balance", "cash_flow", "ratios", "valuation", "all"]
                    },
                    "default": ["all"]
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US"],
                    "default": "KR"
                }
            },
            "required": ["tickers"]
        }
    )
```

#### 3.4.2 DataAdapter 확장

```python
async def get_fundamentals_unified(
    self,
    tickers: List[str],
    include_ttm: bool = True,
    annual_periods: int = 3,
    categories: List[str] = ["all"],
    region: str = "KR"
) -> Dict[str, FundamentalsUnified]:
    """
    TTM + 연도별 통합 펀더멘털 데이터 조회

    Returns:
        {
            "005930": {
                "ticker": "005930",
                "region": "KR",
                "currency": "KRW",
                "ttm": {
                    "as_of_date": "2024-09-30",
                    "revenue_ttm": 300000000000000,
                    "net_income_ttm": 35000000000000,
                    "roe_ttm": 0.12,
                    "quarters_included": ["2024Q3", "2024Q2", "2024Q1", "2023Q4"],
                    "data_completeness": 1.0
                },
                "annual": [
                    {"fiscal_year": 2023, "revenue": 280000000000000, ...},
                    {"fiscal_year": 2022, "revenue": 302000000000000, ...},
                    {"fiscal_year": 2021, "revenue": 279000000000000, ...}
                ],
                "comparison": {
                    "revenue_ttm_vs_fy2023": 0.071,  # +7.1% 성장
                    "roe_ttm_vs_fy2023": 0.02,       # +2%p 개선
                    "trend": "improving"
                }
            }
        }
    """
```

#### 3.4.3 PostgresDatabaseManager 확장

```python
def get_fundamentals_with_ttm(
    self,
    ticker: str,
    region: str,
    as_of_date: date = None,
    annual_periods: int = 3
) -> Dict:
    """
    TTM 계산을 포함한 펀더멘털 데이터 조회

    SQL Strategy:
    1. 최근 4분기 QUARTERLY 데이터 조회
    2. 최근 N년 ANNUAL 데이터 조회
    3. Python에서 TTM 계산 수행
    """
    # Step 1: 분기 데이터 조회 (TTM 계산용)
    quarterly_query = """
        SELECT *
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = %s
          AND period_type = 'QUARTERLY'
          AND date <= %s
        ORDER BY date DESC
        LIMIT 8  -- 최근 8분기 (안전 마진)
    """

    # Step 2: 연간 데이터 조회
    annual_query = """
        SELECT *
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = %s
          AND period_type = 'ANNUAL'
        ORDER BY fiscal_year DESC
        LIMIT %s
    """

    # Step 3: TTM 계산 및 반환
    quarterly_data = self._execute_query(quarterly_query, ...)
    annual_data = self._execute_query(annual_query, ...)

    ttm_data = self._calculate_ttm(quarterly_data)

    return {
        'ttm': ttm_data,
        'annual': annual_data,
        'quarterly': quarterly_data[:4]  # 최근 4분기만 반환
    }
```

### 3.5 응답 포맷

```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "name": "삼성전자",
      "region": "KR",
      "currency": "KRW",

      "ttm": {
        "as_of_date": "2024-09-30",
        "period_label": "TTM (2023Q4 - 2024Q3)",

        "income_statement": {
          "revenue": {"value": 300000000000000, "unit": "KRW"},
          "operating_income": {"value": 25000000000000, "unit": "KRW"},
          "net_income": {"value": 35000000000000, "unit": "KRW"},
          "ebitda": {"value": 85000000000000, "unit": "KRW"}
        },

        "balance_sheet": {
          "total_assets": {"value": 450000000000000, "unit": "KRW"},
          "total_equity": {"value": 300000000000000, "unit": "KRW"},
          "total_debt": {"value": 100000000000000, "unit": "KRW"}
        },

        "ratios": {
          "roe": {"value": 0.117, "unit": "ratio", "formatted": "11.7%"},
          "roa": {"value": 0.078, "unit": "ratio", "formatted": "7.8%"},
          "operating_margin": {"value": 0.083, "unit": "ratio", "formatted": "8.3%"},
          "net_margin": {"value": 0.117, "unit": "ratio", "formatted": "11.7%"},
          "debt_to_equity": {"value": 0.33, "unit": "ratio"}
        },

        "data_quality": {
          "quarters_included": ["2024Q3", "2024Q2", "2024Q1", "2023Q4"],
          "completeness": 1.0,
          "missing_fields": []
        }
      },

      "annual": [
        {
          "fiscal_year": 2023,
          "period_end": "2023-12-31",
          "income_statement": {
            "revenue": {"value": 280000000000000, "unit": "KRW"},
            "operating_income": {"value": 22000000000000, "unit": "KRW"},
            "net_income": {"value": 32000000000000, "unit": "KRW"}
          },
          "ratios": {
            "roe": {"value": 0.107, "unit": "ratio"},
            "operating_margin": {"value": 0.079, "unit": "ratio"}
          }
        },
        {
          "fiscal_year": 2022,
          "period_end": "2022-12-31",
          "income_statement": {
            "revenue": {"value": 302000000000000, "unit": "KRW"},
            "operating_income": {"value": 43000000000000, "unit": "KRW"},
            "net_income": {"value": 55000000000000, "unit": "KRW"}
          },
          "ratios": {
            "roe": {"value": 0.183, "unit": "ratio"},
            "operating_margin": {"value": 0.142, "unit": "ratio"}
          }
        }
      ],

      "comparison": {
        "ttm_vs_latest_annual": {
          "revenue_growth": 0.071,
          "operating_income_growth": 0.136,
          "net_income_growth": 0.094,
          "roe_change": 0.01,
          "summary": "TTM 실적이 FY2023 대비 개선 중"
        },
        "yoy_annual": {
          "revenue_growth_2023": -0.073,
          "revenue_growth_2022": 0.082,
          "trend": "회복 국면"
        }
      }
    }
  },

  "metadata": {
    "ticker_count": 1,
    "region": "KR",
    "include_ttm": true,
    "annual_periods": 3,
    "query_time": "2024-11-27T10:30:00+09:00"
  }
}
```

---

## 4. 구현 계획

### 4.1 Phase 1: 핵심 TTM 계산 로직 (2-3일)

```
modules/
└── fundamentals/
    ├── __init__.py
    ├── ttm_calculator.py      # TTM 계산 핵심 로직
    ├── period_aggregator.py   # 분기 데이터 집계
    └── comparison_analyzer.py # TTM vs 연도별 비교 분석
```

**작업 내용**:
1. `TTMCalculator` 클래스 구현
2. 손익계산서 합산 로직 (revenue, net_income 등)
3. 재무상태표 최신값 추출 로직
4. 파생 비율 계산 (ROE, ROA, 마진)
5. 데이터 완성도 검증

### 4.2 Phase 2: Database Layer 확장 (1-2일)

**작업 내용**:
1. `PostgresDatabaseManager.get_fundamentals_with_ttm()` 메서드 추가
2. 분기 데이터 조회 쿼리 최적화
3. 배치 처리 지원 (다수 ticker)

### 4.3 Phase 3: MCP Tool 확장 (1-2일)

**작업 내용**:
1. `query_fundamentals_unified` Tool 정의
2. `DataAdapter.get_fundamentals_unified()` 구현
3. 응답 포맷터 구현

### 4.4 Phase 4: 테스트 및 검증 (1일)

**작업 내용**:
1. 단위 테스트 (TTM 계산 정확도)
2. 통합 테스트 (MCP Tool 호출)
3. 실제 데이터 검증 (삼성전자, SK하이닉스 등)

---

## 5. 파일 구조

```
spock/
├── modules/
│   └── fundamentals/                    # 신규 모듈
│       ├── __init__.py
│       ├── ttm_calculator.py            # TTM 계산 핵심
│       ├── period_aggregator.py         # 기간 집계
│       ├── comparison_analyzer.py       # 비교 분석
│       └── models.py                    # 데이터 모델
│
├── mcp_server/
│   ├── tools/
│   │   ├── fundamentals_tool.py         # 기존 (유지)
│   │   └── fundamentals_unified_tool.py # 신규: TTM+연도별
│   └── adapters/
│       └── data_adapter.py              # 확장: get_fundamentals_unified()
│
└── tests/
    └── unit/
        └── test_ttm_calculator.py       # TTM 계산 테스트
```

---

## 6. 데이터 요구사항

### 6.1 TTM 계산을 위한 필수 조건

| 조건 | 설명 | 현재 상태 |
|------|------|----------|
| **분기 데이터 4개** | 최근 4분기 QUARTERLY 데이터 필요 | ⚠️ DART 백필 필요 |
| **연속성** | 분기 간 누락 없이 연속 | ✅ 확인 필요 |
| **일관된 회계기준** | K-IFRS 또는 US-GAAP 통일 | ✅ DART/SEC 보장 |

### 6.2 우선 지원 지표

**Phase 1 (핵심 지표)**:
- 매출액 (revenue)
- 영업이익 (operating_income)
- 순이익 (net_income)
- EBITDA
- ROE, ROA
- 영업마진, 순이익마진

**Phase 2 (확장 지표)**:
- 잉여현금흐름 (FCF)
- 자본적지출 (CAPEX)
- 영업현금흐름
- 부채비율
- 이자보상배율

---

## 7. 제약사항 및 고려사항

### 7.1 데이터 소스별 제약

| 소스 | 제약 | 대응 방안 |
|------|------|----------|
| **DART** | 분기보고서 지연 (45일) | as_of_date 기준 조회 |
| **SEC EDGAR** | 10-Q/10-K 발표 시점 차이 | 발표일 기준 정렬 |
| **yfinance** | 과거 분기 데이터 제한 | DB 캐싱 필수 |

### 7.2 회계연도 차이

- **한국**: 대부분 12월 결산 (일부 3월 결산)
- **미국**: 회사별 상이 (Apple: 9월, MS: 6월)
- **대응**: `fiscal_year_end` 컬럼 활용

### 7.3 계산 예외 처리

```python
# 불완전 데이터 처리
if len(quarters) < 4:
    return {
        'ttm': None,
        'error': 'insufficient_quarterly_data',
        'available_quarters': len(quarters),
        'required_quarters': 4
    }

# 음수 자본 처리 (ROE 계산 불가)
if avg_equity <= 0:
    ratios['roe_ttm'] = None
    ratios['roe_ttm_note'] = 'negative_equity'
```

---

## 8. 예상 쿼리 성능

### 8.1 단일 ticker 조회
```sql
-- 분기 데이터 (최근 8분기) + 연간 데이터 (최근 5년)
-- 예상 레코드: 8 + 5 = 13개
-- 예상 시간: <50ms (인덱스 활용)
```

### 8.2 배치 조회 (20 tickers)
```sql
-- 분기: 20 * 8 = 160 레코드
-- 연간: 20 * 5 = 100 레코드
-- 총: 260 레코드
-- 예상 시간: <200ms
```

---

## 9. 다음 단계

1. **Phase 1 착수**: `modules/fundamentals/ttm_calculator.py` 구현
2. **데이터 검증**: 기존 QUARTERLY 데이터 품질 확인
3. **DART 백필**: 부족한 분기 데이터 수집
4. **테스트 케이스**: 삼성전자, SK하이닉스 등 실제 데이터로 검증

---

**작성일**: 2024-11-27
**상태**: 설계 완료, 구현 대기
**담당**: Quant Platform Development
