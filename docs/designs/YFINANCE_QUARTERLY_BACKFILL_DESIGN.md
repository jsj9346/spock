# yfinance 분기별 재무제표 백필 설계

> HK, CN, VN 리전의 QUARTERLY 데이터 수집 및 TTM 지원을 위한 설계 문서

## 1. 개요

### 1.1 목적
- HK(홍콩), CN(중국), VN(베트남) 리전의 분기별 재무제표 데이터 수집
- TTM(Trailing Twelve Months) 계산을 위한 QUARTERLY 데이터 확보
- 기존 SEC EDGAR(US), DART(KR), EDINET(JP) 백필 시스템과 통합

### 1.2 현재 상태

| 리전 | QUARTERLY 소스 | 상태 | TTM 가능 |
|------|---------------|------|---------|
| KR | DART API | ✅ 구현됨 | ✅ |
| US | SEC EDGAR (10-Q) | ✅ 구현됨 | ✅ |
| JP | EDINET API | ⚠️ 부분 구현 | ⚠️ |
| **HK** | **yfinance** | ❌ 미구현 | ❌ |
| **CN** | **yfinance** | ❌ 미구현 | ❌ |
| **VN** | **yfinance** | ❌ 미구현 | ❌ |

### 1.3 yfinance 데이터 가용성 검증 결과

```
[HK] 0700.HK (텐센트)
  Income Stmt:    ✅ (6 quarters)
  Balance Sheet:  ✅ (2 quarters)
  Cash Flow:      ❌ (일부 종목 미제공)

[CN] 600519.SS (마오타이)
  Income Stmt:    ✅ (6 quarters)
  Balance Sheet:  ✅ (6 quarters)
  Cash Flow:      ✅ (5 quarters)

[VN] VNM.VN (비나밀크)
  Income Stmt:    ✅ (6 quarters)
  Balance Sheet:  ✅ (6 quarters)
  Cash Flow:      ✅ (6 quarters)
```

---

## 2. 아키텍처

### 2.1 시스템 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│                    spock_refresh.py                              │
│  9. Fundamental Backfill → 6. Other Markets (HK/CN/VN)          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              YFinanceQuarterlyBackfiller                         │
│  - 리전별 티커 조회 (HK, CN, VN)                                 │
│  - yfinance quarterly 데이터 수집                                │
│  - ticker_fundamentals 테이블 저장 (period_type='QUARTERLY')     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TTMService                                    │
│  - QUARTERLY 데이터 기반 TTM 계산                                │
│  - ticker_fundamentals_ttm 테이블 저장                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 파일 구조

```
modules/
└── backfill/
    └── yfinance_quarterly_executor.py  # 신규 생성

scripts/
└── backfill_fundamentals_yfinance.py   # 기존 (DAILY 전용)
└── backfill_quarterly_yfinance.py      # 신규 생성 (QUARTERLY 전용)

spock_refresh.py                        # 메뉴 통합
```

---

## 3. 데이터 매핑

### 3.1 yfinance → ticker_fundamentals 필드 매핑

#### Income Statement (손익계산서)

| yfinance 필드 | DB 필드 | 설명 |
|--------------|---------|------|
| `Total Revenue` | `revenue` | 총매출 |
| `Cost Of Revenue` | `cogs` | 매출원가 |
| `Gross Profit` | `gross_profit` | 매출총이익 |
| `Operating Income` | `operating_profit` | 영업이익 |
| `Net Income` | `net_income` | 순이익 |
| `EBITDA` | `ebitda` | EBITDA |
| `Interest Expense` | `interest_expense` | 이자비용 |
| `Interest Income` | `interest_income` | 이자수익 |
| `Research And Development` | `rd_expense` | R&D 비용 |
| `Selling General And Administration` | `sga_expense` | 판관비 |
| `Basic EPS` | `trailing_eps` | 주당순이익 |
| `Basic Average Shares` | `shares_outstanding` | 발행주식수 |

#### Balance Sheet (재무상태표)

| yfinance 필드 | DB 필드 | 설명 |
|--------------|---------|------|
| `Total Assets` | `total_assets` | 총자산 |
| `Total Liabilities Net Minority Interest` | `total_liabilities` | 총부채 |
| `Stockholders Equity` | `total_equity` | 자기자본 |
| `Current Assets` | `current_assets` | 유동자산 |
| `Current Liabilities` | `current_liabilities` | 유동부채 |
| `Inventory` | `inventory` | 재고자산 |
| `Accounts Receivable` | `accounts_receivable` | 매출채권 |
| `Cash And Cash Equivalents` | `cash_and_equivalents` | 현금성자산 |
| `Net PPE` | `pp_e` | 유형자산 |
| `Capital Stock` | `capital_stock` | 자본금 |
| `Retained Earnings` | `retained_earnings` | 이익잉여금 |
| `Treasury Stock` | `treasury_stock` | 자기주식 |

#### Cash Flow (현금흐름표)

| yfinance 필드 | DB 필드 | 설명 |
|--------------|---------|------|
| `Operating Cash Flow` | `operating_cash_flow` | 영업활동현금흐름 |
| `Investing Cash Flow` | `investing_cf` | 투자활동현금흐름 |
| `Financing Cash Flow` | `financing_cf` | 재무활동현금흐름 |
| `Capital Expenditure` | `capex` | 자본적지출 |
| `Free Cash Flow` | `fcf` | 잉여현금흐름 |

### 3.2 리전별 티커 변환

```python
TICKER_MAPPING = {
    'HK': lambda t: t,           # 0700.HK → 0700.HK (그대로)
    'CN': lambda t: t,           # 600519.SS → 600519.SS (그대로)
    'VN': lambda t: f"{t}.VN"    # VNM → VNM.VN (suffix 추가)
}
```

---

## 4. 구현 설계

### 4.1 YFinanceQuarterlyExecutor 클래스

```python
class YFinanceQuarterlyExecutor(BackfillExecutor):
    """
    yfinance 분기별 재무제표 백필 실행기

    HK, CN, VN 리전의 분기별 데이터를 yfinance에서 수집하여
    ticker_fundamentals 테이블에 저장합니다.
    """

    SUPPORTED_REGIONS = ['HK', 'CN', 'VN']

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 0.5,  # yfinance 권장: 2 req/sec
        regions: List[str] = None
    ):
        ...

    def get_tickers_for_backfill(
        self,
        region: str,
        limit: Optional[int] = None,
        force_refresh: bool = False
    ) -> List[TickerGapInfo]:
        """
        백필 대상 티커 조회

        Args:
            region: 대상 리전 (HK, CN, VN)
            limit: 최대 티커 수
            force_refresh: True면 이미 QUARTERLY 데이터가 있는 티커도 포함
        """
        ...

    def fetch_quarterly_data(
        self,
        ticker: str,
        region: str
    ) -> Optional[List[Dict]]:
        """
        yfinance에서 분기별 재무제표 수집

        Returns:
            분기별 데이터 리스트 (최대 8분기)
        """
        ...

    def run_backfill(
        self,
        regions: List[str] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
        calculate_ttm: bool = True  # 백필 후 자동 TTM 계산
    ) -> BackfillStats:
        ...
```

### 4.2 데이터 수집 로직

```python
def fetch_quarterly_data(self, ticker: str, region: str) -> List[Dict]:
    """yfinance에서 분기별 데이터 수집"""

    yf_ticker = self._to_yf_ticker(ticker, region)
    stock = yf.Ticker(yf_ticker)

    # 손익계산서
    income_stmt = stock.quarterly_income_stmt

    # 재무상태표
    balance_sheet = stock.quarterly_balance_sheet

    # 현금흐름표 (없을 수 있음)
    try:
        cashflow = stock.quarterly_cashflow
    except:
        cashflow = None

    # 날짜별로 데이터 병합
    quarters = []
    for date_col in income_stmt.columns:
        quarter_data = {
            'ticker': ticker,
            'region': region,
            'date': date_col.date(),
            'period_type': 'QUARTERLY',
            'data_source': 'yfinance',
            # Income Statement
            'revenue': self._safe_get(income_stmt, 'Total Revenue', date_col),
            'gross_profit': self._safe_get(income_stmt, 'Gross Profit', date_col),
            'operating_profit': self._safe_get(income_stmt, 'Operating Income', date_col),
            'net_income': self._safe_get(income_stmt, 'Net Income', date_col),
            'ebitda': self._safe_get(income_stmt, 'EBITDA', date_col),
            # Balance Sheet (있는 경우)
            'total_assets': self._safe_get(balance_sheet, 'Total Assets', date_col),
            'total_equity': self._safe_get(balance_sheet, 'Stockholders Equity', date_col),
            # Cash Flow (있는 경우)
            'operating_cash_flow': self._safe_get(cashflow, 'Operating Cash Flow', date_col),
            'fcf': self._safe_get(cashflow, 'Free Cash Flow', date_col),
        }
        quarters.append(quarter_data)

    return quarters
```

### 4.3 spock_refresh.py 메뉴 통합

```python
# 옵션 9 → 6. Other Markets (yfinance)
elif choice == '6':
    print("🌐 Other Markets Fundamentals (yfinance)")
    print("=" * 70)

    # 리전 선택
    print("  1. 🇭🇰 HK (Hong Kong)")
    print("  2. 🇨🇳 CN (China)")
    print("  3. 🇻🇳 VN (Vietnam)")
    print("  4. All (HK + CN + VN)")
    region_choice = input("Select region [4]: ").strip() or '4'

    # Period Type 선택 (NEW)
    print("\n📋 Period Type:")
    print("  D. DAILY - 일일 시가총액/PER/PBR (기존)")
    print("  Q. QUARTERLY - 분기별 재무제표 (TTM 계산용)")
    period_choice = input("Select period type [Q]: ").strip().upper() or 'Q'

    if period_choice == 'Q':
        # QUARTERLY 백필 + 자동 TTM 계산
        run_yfinance_quarterly_backfill(
            regions=selected_regions,
            limit=limit_val,
            calculate_ttm=True
        )
    else:
        # 기존 DAILY 백필
        run_yfinance_daily_backfill(...)
```

---

## 5. 에러 처리

### 5.1 yfinance 제한사항

| 제한 | 대응 방안 |
|------|----------|
| Rate Limit (비공식) | 0.5초 딜레이 (2 req/sec) |
| 일부 종목 데이터 없음 | fund_status='unavailable' 마킹 |
| Cash Flow 없는 종목 | NULL 허용, 경고 로그 |
| 레거시 CN 티커 (비6자리) | 사전 필터링 (기존 로직) |

### 5.2 데이터 품질 검증

```python
def _validate_quarterly_data(self, data: Dict) -> bool:
    """분기 데이터 품질 검증"""

    # 필수 필드 확인
    if not data.get('revenue') and not data.get('net_income'):
        return False

    # 비정상 값 필터링
    if data.get('revenue') and data['revenue'] < 0:
        return False  # 음수 매출은 오류

    return True
```

---

## 6. 테스트 계획

### 6.1 단위 테스트

```python
class TestYFinanceQuarterlyExecutor:
    def test_ticker_mapping_hk(self):
        """HK 티커 변환 테스트"""
        assert executor._to_yf_ticker('0700', 'HK') == '0700.HK'

    def test_ticker_mapping_cn(self):
        """CN 티커 변환 테스트"""
        assert executor._to_yf_ticker('600519.SS', 'CN') == '600519.SS'

    def test_fetch_quarterly_data(self):
        """분기 데이터 수집 테스트"""
        data = executor.fetch_quarterly_data('0700', 'HK')
        assert len(data) > 0
        assert 'revenue' in data[0]
```

### 6.2 통합 테스트

```bash
# DRY RUN 테스트
python scripts/backfill_quarterly_yfinance.py --region HK --limit 3 --dry-run

# 실제 백필 테스트 (소량)
python scripts/backfill_quarterly_yfinance.py --region HK --limit 5

# TTM 계산 검증
python scripts/calculate_ttm_fundamentals.py --region HK
```

---

## 7. 예상 커버리지

### 7.1 티커 수

| 리전 | 전체 티커 | 예상 성공률 | 예상 QUARTERLY |
|------|----------|------------|----------------|
| HK | 2,732 | ~70% | ~1,912 |
| CN | 2,436 | ~60% | ~1,462 |
| VN | 310 | ~80% | ~248 |
| **합계** | **5,478** | **~67%** | **~3,622** |

### 7.2 TTM 커버리지 목표

- **1차 목표**: 각 리전 50% 이상 TTM 데이터 확보
- **2차 목표**: 시가총액 상위 100개 종목 100% 커버

---

## 8. 구현 일정

| 단계 | 작업 | 예상 소요 |
|------|------|----------|
| 1 | YFinanceQuarterlyExecutor 구현 | 1시간 |
| 2 | spock_refresh.py 메뉴 통합 | 30분 |
| 3 | 단위 테스트 작성 | 30분 |
| 4 | DRY RUN 테스트 | 15분 |
| 5 | 실제 백필 테스트 (소량) | 30분 |
| 6 | 문서 업데이트 | 15분 |

---

## 9. 참고 사항

### 9.1 기존 코드 재사용

- `BackfillExecutor` 추상 클래스 상속
- `TickerGapInfo`, `BackfillStats` 데이터 구조 재사용
- `TTMService` TTM 계산 로직 재사용

### 9.2 향후 확장

- JP 리전도 yfinance로 백업 데이터 수집 가능
- 연간(ANNUAL) 데이터도 동일 로직으로 수집 가능
- 데이터 품질 모니터링 대시보드 연동

---

**작성일**: 2025-12-11
**작성자**: Claude Code
**상태**: 설계 완료, 구현 대기
