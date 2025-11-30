# 글로벌 리전 TTM/연도별 조회 기능 확장 설계

## 1. 현재 상태 요약

### 리전별 데이터 소스 및 분기 데이터 지원 현황

| 리전 | 데이터 소스 | 연간 | 분기 | TTM 가능 | 현재 상태 |
|------|------------|------|------|---------|----------|
| **KR** | DART API | ✅ | ✅ (Q1/Q3) | ✅ | 구현 완료 |
| **US** | SEC EDGAR | ✅ | ✅ (10-Q) | ✅ | 구현 필요 |
| **JP** | EDINET | ✅ | ⚠️ (파서 보완 필요) | ⚠️ | 부분 구현 |
| **HK** | yfinance | ✅ | ❌ | ❌ | 연간만 지원 |
| **CN** | AkShare | ✅ | ❌ | ❌ | 연간만 지원 |
| **VN** | yfinance | ✅ | ❌ | ❌ | 연간만 지원 |

### 즉시 확장 가능한 리전: KR, US, JP

---

## 2. 리전별 확장 계획

### 2.1 US (미국) - SEC EDGAR 기반

**데이터 소스**: SEC EDGAR API (10-K, 10-Q)
**분기 보고서**: 10-Q (Form 10-Q)

**지원 지표 (30+ US-GAAP)**:
- Revenue, Net Income, Operating Income
- Total Assets, Total Equity, Total Liabilities
- EPS (Basic/Diluted), Shares Outstanding
- Operating/Investing/Financing Cash Flows

**백필 스크립트**: `scripts/backfill_fundamentals_sec.py` (확장 필요)

```python
# US 분기 백필 명령어
python3 scripts/backfill_fundamentals_sec.py \
  --report-type quarterly \
  --start-year 2023 \
  --limit 100
```

### 2.2 JP (일본) - EDINET 기반

**데이터 소스**: EDINET API
**분기 보고서**: 四半期報告書 (DocType 130)

**지원 지표 (20+ JP-GAAP/IFRS)**:
- 売上高 (Revenue), 営業利益 (Operating Profit)
- 当期純利益 (Net Income), 総資産 (Total Assets)
- 純資産 (Net Assets), 負債合計 (Total Liabilities)

**현재 상태**: 연간 보고서 파싱 완료, 분기 보고서 파서 보완 필요

**백필 스크립트**: `scripts/backfill_fundamentals_edinet.py` (확장 필요)

### 2.3 HK, CN, VN - 연간 데이터만 지원

**제한 사항**:
- yfinance/AkShare는 분기별 재무제표 미제공
- 유료 데이터 소스(Wind, Bloomberg) 필요

**대안 전략**:
- 연간 데이터 기반 YoY 비교만 제공
- TTM 기능은 지원 불가 (명시적 안내)

---

## 3. 통합 아키텍처

### 3.1 리전별 Backfill Executor 구조

```
modules/backfill/
├── orchestrator.py           # 공통 오케스트레이터
├── dart_executor.py          # KR 전용 (기존)
├── sec_executor.py           # US 전용 (확장)
├── edinet_executor.py        # JP 전용 (확장)
└── base_executor.py          # 공통 인터페이스
```

### 3.2 통합 TTM Calculator

```python
# modules/fundamentals/ttm_calculator.py (이미 구현됨)
# 리전 독립적 - 분기 데이터만 있으면 동작

from modules.fundamentals import TTMCalculator

calc = TTMCalculator()

# KR
kr_result = calc.calculate_ttm('005930', 'KR', kr_quarterly_data)

# US
us_result = calc.calculate_ttm('AAPL', 'US', us_quarterly_data)

# JP
jp_result = calc.calculate_ttm('7203', 'JP', jp_quarterly_data)
```

### 3.3 MCP Tool 확장

```python
# mcp_server/tools/fundamentals_unified_tool.py

def get_fundamentals_unified_tool_def() -> Tool:
    return Tool(
        name="query_fundamentals_unified",
        inputSchema={
            "properties": {
                "tickers": {...},
                "region": {
                    "type": "string",
                    "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                    "description": (
                        "Market region. TTM supported: KR, US, JP. "
                        "Annual only: HK, CN, VN."
                    )
                },
                "include_ttm": {
                    "type": "boolean",
                    "description": (
                        "Include TTM calculations. "
                        "Only available for KR, US, JP with quarterly data."
                    ),
                    "default": True
                },
                ...
            }
        }
    )
```

---

## 4. 리전별 회계 기준 매핑

### 4.1 계정과목 매핑 테이블

| 지표 | KR (K-IFRS) | US (US-GAAP) | JP (JP-GAAP/IFRS) |
|------|-------------|--------------|-------------------|
| Revenue | 매출액 | Revenues | 売上高 |
| Operating Profit | 영업이익 | OperatingIncome | 営業利益 |
| Net Income | 당기순이익 | NetIncomeLoss | 当期純利益 |
| Total Assets | 자산총계 | Assets | 総資産 |
| Total Equity | 자본총계 | StockholdersEquity | 純資産 |
| Total Liabilities | 부채총계 | Liabilities | 負債合計 |
| EBITDA | EBITDA | EBITDA | EBITDA |

### 4.2 매핑 구현

```python
# modules/fundamentals/region_mapping.py

REGION_METRIC_MAP = {
    'KR': {
        'revenue': 'revenue',
        'operating_profit': 'operating_profit',
        'net_income': 'net_income',
        'total_assets': 'total_assets',
        'total_equity': 'total_equity',
    },
    'US': {
        'revenue': 'Revenues',
        'operating_profit': 'OperatingIncome',
        'net_income': 'NetIncomeLoss',
        'total_assets': 'Assets',
        'total_equity': 'StockholdersEquity',
    },
    'JP': {
        'revenue': 'NetSales',
        'operating_profit': 'OperatingIncome',
        'net_income': 'NetIncome',
        'total_assets': 'TotalAssets',
        'total_equity': 'NetAssets',
    }
}

def normalize_metric(region: str, metric: str, value: Any) -> Any:
    """리전별 지표 정규화"""
    # DB에 저장할 때 공통 컬럼명으로 변환
    pass
```

---

## 5. 구현 우선순위

### Phase 1: US 시장 확장 (2-3일)

```
□ SEC 10-Q 분기 백필 스크립트 확장
  ├── scripts/backfill_fundamentals_sec.py 수정
  ├── --report-type quarterly 지원
  └── 분기별 데이터 파싱 검증

□ US TTM 계산 테스트
  ├── Apple (AAPL) 4분기 데이터 수집
  └── TTMCalculator 동작 검증
```

### Phase 2: JP 시장 확장 (2-3일)

```
□ EDINET 四半期報告書 파서 보완
  ├── DocType 130 XBRL 파싱
  └── JP-GAAP/IFRS 계정과목 매핑

□ JP TTM 계산 테스트
  ├── Toyota (7203) 4분기 데이터 수집
  └── TTMCalculator 동작 검증
```

### Phase 3: MCP Tool 통합 (1-2일)

```
□ query_fundamentals_unified Tool 구현
  ├── 리전별 TTM 지원 여부 체크
  ├── 분기 데이터 없는 리전 fallback 처리
  └── 응답 포맷 통일

□ 통합 테스트
  ├── KR + US + JP 동시 조회
  └── HK/CN/VN 연간 데이터만 반환 확인
```

### Phase 4: 문서화 및 모니터링 (0.5일)

```
□ 리전별 데이터 수집 현황 대시보드
□ TTM 계산 가능 ticker 수 모니터링
□ 사용자 가이드 문서
```

---

## 6. 리전별 백필 명령어

### KR (한국) - 이미 구현됨
```bash
# 분기 데이터 수집
python3 scripts/backfill_fundamentals_dart.py \
  --report-type quarterly \
  --start-year 2023 \
  --limit 100

# 모니터링
tail -f log/$(date +%Y%m%d)_backfill_fundamentals_dart.log
```

### US (미국) - 확장 필요
```bash
# 분기 데이터 수집 (10-Q)
python3 scripts/backfill_fundamentals_sec.py \
  --report-type quarterly \
  --start-year 2023 \
  --limit 100

# 연간 데이터 수집 (10-K)
python3 scripts/backfill_fundamentals_sec.py \
  --report-type annual \
  --start-year 2020
```

### JP (일본) - 확장 필요
```bash
# 분기 데이터 수집 (四半期報告書)
python3 scripts/backfill_fundamentals_edinet.py \
  --report-type quarterly \
  --start-year 2023 \
  --limit 100

# 연간 데이터 수집 (有価証券報告書)
python3 scripts/backfill_fundamentals_edinet.py \
  --report-type annual \
  --start-year 2020
```

---

## 7. 예상 데이터 볼륨

| 리전 | Ticker 수 | 연간 레코드 | 분기 레코드 | 총 레코드 |
|------|----------|-----------|-----------|----------|
| KR | ~2,700 | ~8,100 | ~21,600 | ~30,000 |
| US | ~4,000 | ~12,000 | ~32,000 | ~44,000 |
| JP | ~3,800 | ~11,400 | ~30,400 | ~42,000 |
| HK | ~2,500 | ~7,500 | - | ~7,500 |
| CN | ~4,500 | ~13,500 | - | ~13,500 |
| VN | ~400 | ~1,200 | - | ~1,200 |

**총 예상**: ~138,200 레코드

---

## 8. 에러 처리 및 Fallback

### TTM 불가능 시 Fallback

```python
async def get_fundamentals_unified(
    tickers: List[str],
    region: str,
    include_ttm: bool = True
) -> Dict:

    # TTM 미지원 리전 체크
    TTM_SUPPORTED_REGIONS = ['KR', 'US', 'JP']

    if include_ttm and region not in TTM_SUPPORTED_REGIONS:
        logger.warning(
            f"TTM not supported for region {region}. "
            f"Returning annual data only."
        )
        include_ttm = False

    # 분기 데이터 부족 시 Fallback
    if include_ttm:
        quarterly_count = count_quarterly_records(ticker, region)
        if quarterly_count < 4:
            logger.warning(
                f"Insufficient quarterly data ({quarterly_count}/4). "
                f"TTM calculation skipped."
            )
            include_ttm = False

    # 데이터 조회 및 반환
    ...
```

### 응답에 TTM 지원 여부 명시

```json
{
  "success": true,
  "data": {
    "AAPL": {
      "ticker": "AAPL",
      "region": "US",
      "ttm_supported": true,
      "ttm": {...},
      "annual": [...]
    },
    "0700.HK": {
      "ticker": "0700.HK",
      "region": "HK",
      "ttm_supported": false,
      "ttm_not_supported_reason": "Quarterly data not available for HK region",
      "annual": [...]
    }
  }
}
```

---

## 9. 다음 단계

1. **즉시 실행**: US SEC 10-Q 백필 스크립트 확장
2. **병렬 진행**: JP EDINET 분기 파서 보완
3. **통합**: MCP Tool 구현
4. **문서화**: 사용자 가이드

---

**작성일**: 2024-11-27
**상태**: 설계 완료, US 확장 착수 대기
