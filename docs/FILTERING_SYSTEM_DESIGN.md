# Filtering System Design Specification

**Document Version**: 1.0
**Date**: 2025-10-04
**Author**: Spock Trading System
**Status**: Design Phase

---

## 1. Executive Summary

### 1.1 Problem Statement

**현재 비효율성**:
- KOSPI (~900) + KOSDAQ (~1,500) + ETF (~600) = **3,000 종목**
- 전체 OHLCV 수집: 3,000 × 250일 = **750,000 데이터 포인트**
- KIS API 제한: 20 req/sec → **최소 50분 소요**
- 저장 용량: **수 GB**

**실제 필요**:
- 매수 후보: 하루 **30-50 종목** (전체의 **2%**)
- 워치리스트: **~100 종목** (전체의 **3%**)

### 1.2 Solution Overview

**Multi-Stage Filtering Architecture** (3단계 깔때기 전략):
```
Stage 0: Basic Market Filter  → 3,000 → 600 (80% 감소)
Stage 1: Technical Pre-screen → 600 → 250 (60% 감소)
Stage 2: Deep Analysis         → 250 → 30-50 (90% 감소)
```

**효율성 개선**:
- 데이터 포인트: 750,000 → 80,500 (**89% 감소**)
- 실행 시간: 50분 → 1분 (**98% 감소**)
- API 호출: 3,000 → 850 (**72% 감소**)
- 저장 용량: 수 GB → ~100MB (**95% 감소**)

---

## 2. Architecture Design

### 2.1 System Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│ INPUT: All Listed Stocks                                │
│ Source: KRX Data API / pykrx                            │
│ Count: ~3,000 tickers                                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 0: Basic Market Filter (scanner.py enhanced)     │
│─────────────────────────────────────────────────────────│
│ Data Source: KIS API 현재가시세 (single batch call)    │
│ API Endpoint: /uapi/domestic-stock/v1/quotations/       │
│               inquire-price (FHKST01010100)             │
│                                                         │
│ Filters:                                                │
│   1. 시가총액 ≥ 1,000억원 (100B KRW)                    │
│   2. 일 거래대금 ≥ 100억원 (10B KRW)                    │
│   3. 가격 범위: 5,000원 ~ 500,000원                     │
│   4. 관리종목/정리매매 제외                             │
│   5. ETF/ETN/SPAC/우선주 제외                           │
│   6. 상장폐지 예정 종목 제외                            │
│                                                         │
│ Performance:                                            │
│   - API Calls: 1 batch call (~5초)                      │
│   - Cache: 1-hour TTL (market hours)                    │
│                                                         │
│ Output: ~600 tickers (80% reduction)                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: Technical Pre-screen (stock_pre_filter.py)    │
│─────────────────────────────────────────────────────────│
│ Data Source: KIS API 일봉 (30일치만 수집)              │
│ API Endpoint: /uapi/domestic-stock/v1/quotations/       │
│               inquire-daily-price (FHKST03010100)       │
│                                                         │
│ Technical Filters:                                      │
│   1. MA20 > MA60 (중기 상승 추세)                       │
│   2. 최근 3일 평균거래량 > 이전 10일 평균 (주목도 상승) │
│   3. 현재가 ≥ 52주 최고가 × 0.7 (강세 유지)             │
│   4. RSI(14) ∈ [30, 70] (과매도/과매수 제외)            │
│   5. 이동평균선 정배열: MA5 > MA20 > MA60               │
│                                                         │
│ Performance:                                            │
│   - API Calls: 600 calls (~30초, rate-limited)          │
│   - Cache: 6-hour TTL (after-hours update)              │
│   - Data Points: 600 × 30 = 18,000                      │
│                                                         │
│ Output: ~250 tickers (추가 60% reduction)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 2: Deep Analysis (stock_technical_filter.py)     │
│─────────────────────────────────────────────────────────│
│ Data Source: KIS API 일봉 (250일 전체 수집)            │
│ API Endpoint: Same as Stage 1 (full 250-day window)    │
│                                                         │
│ Analysis Engine:                                        │
│   - LayeredScoringEngine (100-point system)             │
│   - Weinstein Stage Analysis (Stage 2 detection)        │
│   - Pattern Recognition (Cup & Handle, VCP, etc.)       │
│   - Kelly Formula Position Sizing                       │
│                                                         │
│ Performance:                                            │
│   - API Calls: 250 calls (~15초)                        │
│   - Cache: 24-hour TTL (daily update)                   │
│   - Data Points: 250 × 250 = 62,500                     │
│                                                         │
│ Output:                                                 │
│   - BUY Candidates (≥70 points): ~30-50 tickers         │
│   - WATCH List (50-69 points): ~50-100 tickers          │
│   - AVOID (< 50 points): discarded                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ OUTPUT: Filtered Candidates                             │
│ Storage: SQLite filter_results table                    │
│ Update Frequency: Daily (pre-market: 08:30 KST)        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

#### **Component 1: scanner.py (Enhanced)**
- **Role**: Stage 0 Basic Market Filter
- **Input**: KRX Data API ticker list (~3,000)
- **Processing**:
  - KIS API batch call for current prices
  - Apply 6 basic filters
  - Cache results (1-hour TTL)
- **Output**: ~600 qualified tickers
- **Status**: **MODIFICATION REQUIRED** (add KIS API integration)

#### **Component 2: stock_pre_filter.py (NEW MODULE)**
- **Role**: Stage 1 Technical Pre-screen
- **Input**: Stage 0 output (~600 tickers)
- **Processing**:
  - Fetch 30-day OHLCV for each ticker
  - Calculate MA5, MA20, MA60, RSI(14)
  - Apply 5 technical filters
  - Cache results (6-hour TTL)
- **Output**: ~250 pre-screened tickers
- **Status**: **NEW DEVELOPMENT REQUIRED**

#### **Component 3: stock_technical_filter.py (EXISTING)**
- **Role**: Stage 2 Deep Analysis
- **Input**: Stage 1 output (~250 tickers)
- **Processing**:
  - Fetch 250-day OHLCV for each ticker
  - Run LayeredScoringEngine
  - Weinstein Stage Analysis
  - Pattern Recognition
- **Output**: BUY/WATCH/AVOID signals
- **Status**: **ALREADY IMPLEMENTED** (from Makenaide)

---

## 3. Detailed Specifications

### 3.1 Stage 0: Basic Market Filter

#### 3.1.1 Data Requirements

**KIS API Endpoint**:
```
GET /uapi/domestic-stock/v1/quotations/inquire-price
TR_ID: FHKST01010100
```

**Response Fields Used**:
| Field Name | Korean Name | Purpose | Filter Threshold |
|------------|-------------|---------|------------------|
| `stck_prpr` | 현재가 | Price filtering | 5,000 ~ 500,000원 |
| `acml_tr_pbmn` | 누적거래대금 | Liquidity check | ≥ 100억원 |
| `hts_avls` | 시가총액 | Market cap filter | ≥ 1,000억원 |
| `mrkt_warn_cls_code` | 시장경고코드 | Admin stock check | "00" only |
| `stock_prpr` | 전일종가 | 52-week calculation | Reference price |

#### 3.1.2 Filter Logic

```python
def apply_stage0_filter(ticker_data: Dict) -> bool:
    """
    Stage 0 기본 필터 적용

    Args:
        ticker_data: KIS API 현재가 응답 데이터

    Returns:
        True if ticker passes all filters
    """
    # Filter 1: 시가총액 (Market Cap)
    market_cap = ticker_data.get('hts_avls', 0)  # 단위: 원
    if market_cap < 100_000_000_000:  # 1,000억원
        return False

    # Filter 2: 거래대금 (Trading Value)
    trading_value = ticker_data.get('acml_tr_pbmn', 0)  # 단위: 원
    if trading_value < 10_000_000_000:  # 100억원
        return False

    # Filter 3: 가격 범위 (Price Range)
    price = ticker_data.get('stck_prpr', 0)
    if price < 5_000 or price > 500_000:
        return False

    # Filter 4: 관리종목 체크 (Admin Stock)
    market_warn_code = ticker_data.get('mrkt_warn_cls_code', '99')
    if market_warn_code != '00':  # 00 = 정상
        return False

    # Filter 5: 정리매매 체크 (Delisting)
    # KIS API field: 'sltr_yn' (정리매매여부)
    if ticker_data.get('sltr_yn', 'N') == 'Y':
        return False

    # Filter 6: Asset Type (ETF/ETN/SPAC 제외)
    # This is handled in scanner.py _classify_asset_type()
    # Already implemented

    return True
```

#### 3.1.3 Cache Strategy

**SQLite Table**: `filter_cache_stage0`
```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,  -- KOSPI, KOSDAQ

    -- Stage 0 filter data
    market_cap BIGINT,
    trading_value BIGINT,
    current_price INTEGER,
    market_warn_code TEXT,
    is_delisting BOOLEAN DEFAULT FALSE,

    -- Timestamps
    filter_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Filter result
    stage0_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT  -- If failed, reason (e.g., "market_cap_too_low")
);

CREATE INDEX idx_stage0_filter_date ON filter_cache_stage0(filter_date);
CREATE INDEX idx_stage0_passed ON filter_cache_stage0(stage0_passed);
```

**Cache TTL**: 1 hour (market hours), 24 hours (after-hours)

---

### 3.2 Stage 1: Technical Pre-screen

#### 3.2.1 Data Requirements

**KIS API Endpoint**:
```
GET /uapi/domestic-stock/v1/quotations/inquire-daily-price
TR_ID: FHKST03010100
Period: D (Daily)
Days: 30
```

**Technical Indicators**:
| Indicator | Parameters | Calculation Library | Purpose |
|-----------|------------|---------------------|---------|
| MA5 | 5-day SMA | pandas-ta | Short-term trend |
| MA20 | 20-day SMA | pandas-ta | Medium-term trend |
| MA60 | 60-day SMA | pandas-ta | Long-term trend |
| RSI | 14-day | pandas-ta | Momentum |
| 52-Week High | 250-day max (from cached data) | pandas | Strength |
| Volume SMA | 3-day, 10-day | pandas | Volume analysis |

#### 3.2.2 Filter Logic

```python
def apply_stage1_filter(ohlcv_df: pd.DataFrame) -> Tuple[bool, Dict]:
    """
    Stage 1 기술적 필터 적용

    Args:
        ohlcv_df: 30-day OHLCV DataFrame with indicators

    Returns:
        (passed, details) tuple
    """
    latest = ohlcv_df.iloc[-1]

    details = {
        'ma5': latest['MA_5'],
        'ma20': latest['MA_20'],
        'ma60': latest['MA_60'],
        'rsi': latest['RSI_14'],
        'current_price': latest['close'],
        '52w_high': ohlcv_df['high'].max(),
        'vol_3d_avg': ohlcv_df['volume'].tail(3).mean(),
        'vol_10d_avg': ohlcv_df['volume'].tail(13).head(10).mean()
    }

    # Filter 1: MA20 > MA60 (중기 상승 추세)
    if not (latest['MA_20'] > latest['MA_60']):
        return False, {**details, 'fail_reason': 'MA20 <= MA60'}

    # Filter 2: 거래량 증가 (최근 3일 > 이전 10일 평균)
    if details['vol_3d_avg'] <= details['vol_10d_avg']:
        return False, {**details, 'fail_reason': 'volume_decreasing'}

    # Filter 3: 52주 최고가 대비 -30% 이내
    price_vs_52w = latest['close'] / details['52w_high']
    if price_vs_52w < 0.70:
        return False, {**details, 'fail_reason': '52w_high_too_far'}

    # Filter 4: RSI(14) ∈ [30, 70]
    if not (30 <= latest['RSI_14'] <= 70):
        return False, {**details, 'fail_reason': 'RSI_extreme'}

    # Filter 5: 이동평균선 정배열
    if not (latest['MA_5'] > latest['MA_20'] > latest['MA_60']):
        return False, {**details, 'fail_reason': 'MA_not_aligned'}

    return True, details
```

#### 3.2.3 Cache Strategy

**SQLite Table**: `filter_cache_stage1`
```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
    ticker TEXT PRIMARY KEY,

    -- Stage 1 technical data (30-day window)
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    rsi_14 REAL,
    current_price INTEGER,
    week_52_high INTEGER,
    volume_3d_avg BIGINT,
    volume_10d_avg BIGINT,

    -- Timestamps
    filter_date DATE NOT NULL,
    data_start_date DATE,
    data_end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Filter result
    stage1_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT,

    -- Foreign key
    FOREIGN KEY (ticker) REFERENCES filter_cache_stage0(ticker)
);

CREATE INDEX idx_stage1_filter_date ON filter_cache_stage1(filter_date);
CREATE INDEX idx_stage1_passed ON filter_cache_stage1(stage1_passed);
```

**Cache TTL**: 6 hours (updated after-hours: 16:00 KST)

---

### 3.3 Stage 2: Deep Analysis (Existing System)

**Handled by**:
- `layered_scoring_engine.py`
- `integrated_scoring_system.py`
- `basic_scoring_modules.py`

**No modifications required** - already implemented and tested from Makenaide.

---

## 4. API Integration

### 4.1 KIS API Endpoint Mapping

| Stage | Endpoint | TR_ID | Rate Limit | Data Volume |
|-------|----------|-------|------------|-------------|
| Stage 0 | `/uapi/domestic-stock/v1/quotations/inquire-price` | FHKST01010100 | 20 req/sec | 1 call (batch) |
| Stage 1 | `/uapi/domestic-stock/v1/quotations/inquire-daily-price` | FHKST03010100 | 20 req/sec | 600 calls (~30초) |
| Stage 2 | Same as Stage 1 | FHKST03010100 | 20 req/sec | 250 calls (~15초) |

### 4.2 KoreaAdapter Integration

**Existing Methods** (modules/market_adapters/kr_adapter.py):
- ✅ `get_current_price(ticker)` → Stage 0 사용 가능
- ✅ `get_ohlcv(ticker, days)` → Stage 1, 2 사용 가능

**New Method Required**:
```python
def batch_get_current_prices(self, tickers: List[str]) -> Dict[str, Dict]:
    """
    Batch fetch current prices for multiple tickers

    Alternative: Call get_current_price() in loop with rate limiting
    KIS API doesn't support true batch queries, so sequential calls required

    Args:
        tickers: List of ticker codes

    Returns:
        {ticker: price_data_dict}
    """
    pass  # Implementation: sequential calls with rate limiting
```

---

## 5. Database Schema Extensions

### 5.1 New Tables

**Table 1: filter_cache_stage0** (Basic Market Filter Cache)
```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,

    market_cap BIGINT,
    trading_value BIGINT,
    current_price INTEGER,
    market_warn_code TEXT,
    is_delisting BOOLEAN DEFAULT FALSE,

    filter_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    stage0_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT
);
```

**Table 2: filter_cache_stage1** (Technical Pre-screen Cache)
```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
    ticker TEXT PRIMARY KEY,

    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    rsi_14 REAL,
    current_price INTEGER,
    week_52_high INTEGER,
    volume_3d_avg BIGINT,
    volume_10d_avg BIGINT,

    filter_date DATE NOT NULL,
    data_start_date DATE,
    data_end_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    stage1_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT,

    FOREIGN KEY (ticker) REFERENCES filter_cache_stage0(ticker)
);
```

**Table 3: filter_execution_log** (Performance Tracking)
```sql
CREATE TABLE IF NOT EXISTS filter_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_date DATE NOT NULL,
    stage INTEGER NOT NULL,  -- 0, 1, 2

    input_count INTEGER,
    output_count INTEGER,
    reduction_rate REAL,  -- (input - output) / input

    execution_time_sec REAL,
    api_calls INTEGER,
    error_count INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 Migration Script

**File**: `migrations/002_add_filtering_tables.py`
```python
"""
Migration 002: Add Filtering System Tables

Adds:
- filter_cache_stage0
- filter_cache_stage1
- filter_execution_log
"""

def upgrade(conn):
    cursor = conn.cursor()

    # Create Stage 0 cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT NOT NULL,
            market_cap BIGINT,
            trading_value BIGINT,
            current_price INTEGER,
            market_warn_code TEXT,
            is_delisting BOOLEAN DEFAULT FALSE,
            filter_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stage0_passed BOOLEAN DEFAULT TRUE,
            filter_reason TEXT
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX idx_stage0_filter_date ON filter_cache_stage0(filter_date)")
    cursor.execute("CREATE INDEX idx_stage0_passed ON filter_cache_stage0(stage0_passed)")

    # Create Stage 1 cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
            ticker TEXT PRIMARY KEY,
            ma5 REAL,
            ma20 REAL,
            ma60 REAL,
            rsi_14 REAL,
            current_price INTEGER,
            week_52_high INTEGER,
            volume_3d_avg BIGINT,
            volume_10d_avg BIGINT,
            filter_date DATE NOT NULL,
            data_start_date DATE,
            data_end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stage1_passed BOOLEAN DEFAULT TRUE,
            filter_reason TEXT,
            FOREIGN KEY (ticker) REFERENCES filter_cache_stage0(ticker)
        )
    """)

    cursor.execute("CREATE INDEX idx_stage1_filter_date ON filter_cache_stage1(filter_date)")
    cursor.execute("CREATE INDEX idx_stage1_passed ON filter_cache_stage1(stage1_passed)")

    # Create execution log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_execution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_date DATE NOT NULL,
            stage INTEGER NOT NULL,
            input_count INTEGER,
            output_count INTEGER,
            reduction_rate REAL,
            execution_time_sec REAL,
            api_calls INTEGER,
            error_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

def downgrade(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS filter_execution_log")
    cursor.execute("DROP TABLE IF EXISTS filter_cache_stage1")
    cursor.execute("DROP TABLE IF EXISTS filter_cache_stage0")
    conn.commit()
```

---

## 6. Implementation Plan

### 6.1 Development Tasks

#### **Task 1: Database Migration** (Priority: P0)
- [ ] Create `migrations/002_add_filtering_tables.py`
- [ ] Run migration script
- [ ] Verify tables created correctly
- **Estimated Time**: 1 hour

#### **Task 2: Enhance scanner.py** (Priority: P0)
- [ ] Add KIS API integration for `get_current_price()`
- [ ] Implement `apply_stage0_filter()` function
- [ ] Add `filter_cache_stage0` table operations
- [ ] Update CLI arguments (--stage0-only flag)
- **Estimated Time**: 3 hours

#### **Task 3: Create stock_pre_filter.py** (Priority: P0)
- [ ] Implement `StockPreFilter` class
- [ ] Add KoreaAdapter integration for 30-day OHLCV
- [ ] Implement `apply_stage1_filter()` function
- [ ] Add `filter_cache_stage1` table operations
- [ ] Create CLI for standalone testing
- **Estimated Time**: 4 hours

#### **Task 4: Pipeline Integration** (Priority: P1)
- [ ] Update main execution flow (spock.py)
- [ ] Add Stage 0 → Stage 1 → Stage 2 orchestration
- [ ] Implement cache management (TTL, cleanup)
- [ ] Add performance logging to `filter_execution_log`
- **Estimated Time**: 2 hours

#### **Task 5: Testing & Validation** (Priority: P1)
- [ ] Unit tests for Stage 0 filters
- [ ] Unit tests for Stage 1 filters
- [ ] Integration test: full 3-stage pipeline
- [ ] Performance benchmark (measure actual reduction rates)
- **Estimated Time**: 3 hours

#### **Task 6: Documentation** (Priority: P2)
- [ ] Update CLAUDE.md with filtering system
- [ ] Create FILTERING_SYSTEM_USAGE.md
- [ ] Add code comments and docstrings
- **Estimated Time**: 2 hours

**Total Estimated Time**: **15 hours** (~2 working days)

---

## 7. Performance Expectations

### 7.1 Throughput Metrics

| Stage | Input | Output | Reduction | Time | API Calls |
|-------|-------|--------|-----------|------|-----------|
| Stage 0 | 3,000 | 600 | 80% | ~5초 | 1 (batch) or 3,000 (sequential) |
| Stage 1 | 600 | 250 | 58% | ~30초 | 600 |
| Stage 2 | 250 | 30-50 | 85% | ~15초 | 250 |
| **TOTAL** | **3,000** | **30-50** | **98.5%** | **~50초** | **850** |

### 7.2 Comparison: Before vs After

| Metric | Before (No Filter) | After (3-Stage Filter) | Improvement |
|--------|-------------------|------------------------|-------------|
| Data Points | 750,000 | 80,500 | **89% reduction** |
| Execution Time | 50 minutes | 50 seconds | **98% faster** |
| API Calls | 3,000 | 850 | **72% reduction** |
| Storage | ~2 GB | ~100 MB | **95% reduction** |
| Daily Cost (API) | High risk of rate limit | Within limits | **No throttling** |

### 7.3 Success Criteria

**Functional Requirements**:
- ✅ Stage 0 reduces tickers to ≤700 (target: 600)
- ✅ Stage 1 reduces tickers to ≤300 (target: 250)
- ✅ Stage 2 identifies 30-50 BUY candidates
- ✅ Total execution time ≤60 seconds
- ✅ No KIS API rate limit violations

**Quality Requirements**:
- ✅ False negative rate ≤5% (missed good stocks)
- ✅ Cache hit rate ≥80% (during market hours)
- ✅ Data freshness ≤6 hours (Stage 1 cache)
- ✅ System uptime ≥99% (market hours)

---

## 8. Risk Assessment

### 8.1 Technical Risks

**Risk 1: KIS API Rate Limiting** (Probability: Medium, Impact: High)
- **Mitigation**: Implement exponential backoff, respect 20 req/sec limit
- **Fallback**: Use cached data from previous runs

**Risk 2: False Positives in Stage 0** (Probability: Low, Impact: Medium)
- **Mitigation**: Conservative thresholds (1,000억 market cap, 100억 trading value)
- **Fallback**: Stage 1 will filter out weak stocks

**Risk 3: Cache Staleness** (Probability: Medium, Impact: Low)
- **Mitigation**: 1-hour TTL for Stage 0 (market hours), force refresh daily
- **Fallback**: Manual `--force-refresh` flag

**Risk 4: Data Quality Issues** (Probability: Low, Impact: Medium)
- **Mitigation**: Validate API responses, log errors to `filter_execution_log`
- **Fallback**: Skip problematic tickers, alert via logging

### 8.2 Performance Risks

**Risk 5: Sequential API Calls Bottleneck** (Probability: High, Impact: Medium)
- **Current**: 600 Stage 1 calls take ~30 seconds
- **Mitigation**: Accept current performance, optimize later with async calls
- **Future**: Implement `asyncio` for parallel API calls (Phase 4 enhancement)

**Risk 6: Database I/O Bottleneck** (Probability: Low, Impact: Low)
- **Mitigation**: SQLite is fast for <1M rows, current scale is manageable
- **Monitoring**: Track query times in `filter_execution_log`

---

## 9. Future Enhancements (Phase 4+)

### 9.1 Machine Learning Integration
- **Pattern Recognition**: Train ML model on historical filter results
- **Dynamic Thresholds**: Auto-adjust filter thresholds based on market conditions
- **Backtesting**: Validate filter effectiveness against historical data

### 9.2 Real-time Filtering
- **WebSocket Integration**: Real-time price updates for Stage 0
- **Intraday Monitoring**: Detect new breakouts during trading hours
- **Alert System**: Push notifications when new BUY candidates emerge

### 9.3 Multi-Market Support
- **US Stocks**: Adapt filters for NYSE/NASDAQ
- **Global Markets**: Hong Kong, Japan, Vietnam expansion
- **Crypto Integration**: Reuse Makenaide filter logic

---

## 10. Appendix

### 10.1 KIS API Response Examples

**Stage 0: 현재가시세 (FHKST01010100)**
```json
{
  "rt_cd": "0",
  "msg_cd": "MCA00000",
  "msg1": "정상처리 되었습니다.",
  "output": {
    "stck_prpr": "60000",           // 현재가 (60,000원)
    "acml_tr_pbmn": "15000000000",  // 누적거래대금 (150억원)
    "hts_avls": "120000000000000",  // 시가총액 (120조원)
    "mrkt_warn_cls_code": "00",     // 시장경고코드 (00=정상)
    "sltr_yn": "N"                  // 정리매매여부 (N=정상)
  }
}
```

**Stage 1: 일별시세 (FHKST03010100)**
```json
{
  "rt_cd": "0",
  "output1": [
    {
      "stck_bsop_date": "20251003",  // 날짜
      "stck_oprc": "59500",           // 시가
      "stck_hgpr": "60500",           // 고가
      "stck_lwpr": "59000",           // 저가
      "stck_clpr": "60000",           // 종가
      "acml_vol": "1250000"           // 거래량
    }
    // ... 30 rows
  ]
}
```

### 10.2 Filter Threshold Rationale

**시가총액 1,000억원**:
- KOSPI 상위 400개 종목 포함
- 유동성 확보 (대형주 + 중형주)
- 소형주 리스크 배제

**거래대금 100억원**:
- 매수/매도 시 슬리피지 최소화
- 큰 포지션도 체결 가능
- 작전주 배제 효과

**가격 5,000~500,000원**:
- Penny stock 배제 (5,000원 미만)
- 고가주 Tick size 리스크 배제 (500,000원 초과)

**MA20 > MA60**:
- Weinstein Stage 2 전조 신호
- 중기 추세 전환 감지
- 단기 노이즈 배제

**RSI [30, 70]**:
- 과매도 (< 30): 하락 추세 가능성
- 과매수 (> 70): 단기 조정 가능성
- 중립 구간에서 안정적 진입

---

**End of Document**
