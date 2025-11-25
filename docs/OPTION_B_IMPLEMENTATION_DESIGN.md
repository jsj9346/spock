# Option B Implementation Design: Data Merge Approach

**Date**: 2025-10-28
**Status**: Design Phase
**Complexity**: High
**Expected Implementation Time**: 8-12 hours

---

## Executive Summary

This document provides a comprehensive design for **Option B (Data Merge Approach)** implementation, which integrates multiple fundamental data sources (pykrx, DART) into a unified `ticker_fundamentals` table while maintaining clear data lineage and query efficiency.

### Design Philosophy
- **Clear Data Lineage**: Use `period_type` and `data_source` columns to track data origin
- **Explicit Filtering**: All queries explicitly specify period_type and data_source (no implicit selection)
- **Independent Pipelines**: pykrx and DART collection can run independently without blocking each other
- **Point-in-Time Accuracy**: Support accurate backtesting with historical fundamental snapshots
- **Extensibility**: Framework supports adding future data sources (yfinance, Bloomberg) without architectural changes

### Key Advantages Over Option A
| Dimension | Option A | Option B | Improvement |
|-----------|----------|----------|-------------|
| Query Efficiency | 3/10 | 9/10 | **+200%** |
| Backtesting Accuracy | 4/10 | 9/10 | **+125%** |
| Data Quality Management | 4/10 | 10/10 | **+150%** |
| Cross-sectional Analysis | 5/10 | 9/10 | **+80%** |
| Extensibility | 5/10 | 9/10 | **+80%** |

---

## 1. Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                   Factor Calculation Layer                       │
│  - calculate_dividend_yield.py (queries period_type='DAILY')    │
│  - calculate_ev_ebitda.py (queries period_type='ANNUAL')        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Data Storage Layer (PostgreSQL)                     │
│  Table: ticker_fundamentals                                      │
│  Discriminator: (period_type, data_source)                      │
│  Unique Constraint: (ticker, region, date, period_type)         │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌──────────────────────┐      ┌──────────────────────┐
│  pykrx Pipeline       │      │  DART Pipeline        │
│  - DAILY data         │      │  - ANNUAL data        │
│  - Market ratios      │      │  - Financial stmts    │
│  - Dividend data      │      │  - EBITDA             │
│  - data_source='pykrx'│      │  - data_source='DART' │
└──────────────────────┘      └──────────────────────┘
```

### Data Flow

**pykrx Pipeline**:
1. Fetch market fundamental data (PER, PBR, DIV, DPS) via `stock.get_market_fundamental()`
2. Transform to DB schema
3. Insert with `period_type='DAILY'`, `data_source='pykrx'`
4. Coverage: 2,712 tickers (77% of OHLCV universe)

**DART Pipeline**:
1. Fetch financial statements via DART API
2. Calculate EBITDA (operating_profit + depreciation)
3. Insert with `period_type='ANNUAL'`, `data_source='DART'`
4. Coverage: All listed companies with financial filings

**Factor Calculation**:
- Dividend Yield: Query `WHERE period_type='DAILY' AND data_source='pykrx'`
- EV/EBITDA: Query `WHERE period_type='ANNUAL' AND data_source='DART'`

---

## 2. Database Design

### Schema Usage Pattern

**Key Columns in `ticker_fundamentals`**:
```sql
CREATE TABLE ticker_fundamentals (
    ticker VARCHAR(20),
    region VARCHAR(10),
    date DATE,
    period_type VARCHAR(20),  -- 'DAILY' | 'ANNUAL' | 'QUARTERLY'

    -- pykrx DAILY data
    per DECIMAL(10, 2),
    pbr DECIMAL(10, 2),
    dividend_yield DECIMAL(10, 4),     -- pykrx pre-calculated (%)
    dividend_per_share DECIMAL(10, 2), -- DPS in KRW

    -- DART ANNUAL data
    ebitda BIGINT,                     -- EBITDA in KRW
    total_liabilities BIGINT,
    current_assets BIGINT,
    shares_outstanding BIGINT,

    -- Metadata
    data_source VARCHAR(50),           -- 'pykrx' | 'DART' | 'yfinance' | etc.
    fiscal_year INTEGER,               -- For ANNUAL data
    created_at TIMESTAMP,

    UNIQUE (ticker, region, date, period_type)
);
```

### Data Coexistence Pattern

**Same ticker, different period_type → Both stored**:
```sql
-- pykrx DAILY record
INSERT INTO ticker_fundamentals (ticker, region, date, period_type, dividend_per_share, data_source)
VALUES ('005930', 'KR', '2025-10-21', 'DAILY', 1444, 'pykrx');

-- DART ANNUAL record (different date - fiscal year end)
INSERT INTO ticker_fundamentals (ticker, region, date, period_type, ebitda, fiscal_year, data_source)
VALUES ('005930', 'KR', '2024-12-31', 'ANNUAL', 72000000000000, 2024, 'DART');
```

**No conflict**: Unique constraint allows coexistence due to different `period_type`.

### Index Recommendations

```sql
-- Factor calculation queries (frequent)
CREATE INDEX idx_fundamentals_daily_lookup
    ON ticker_fundamentals (ticker, region, period_type, date DESC)
    WHERE period_type = 'DAILY';

CREATE INDEX idx_fundamentals_annual_lookup
    ON ticker_fundamentals (ticker, region, period_type, fiscal_year DESC)
    WHERE period_type = 'ANNUAL';

-- Coverage monitoring queries
CREATE INDEX idx_fundamentals_source_date
    ON ticker_fundamentals (data_source, date DESC);

-- Cross-sectional analysis (all tickers at specific date)
CREATE INDEX idx_fundamentals_date_period
    ON ticker_fundamentals (date, period_type, data_source)
    WHERE period_type IN ('DAILY', 'ANNUAL');
```

**Query Performance Targets**:
- Single ticker lookup: <10ms
- Cross-sectional (all tickers): <100ms
- Coverage monitoring: <50ms

---

## 3. Data Collection Design

### 3.1 pykrx Collection Pipeline

**Purpose**: Collect DAILY market fundamental data (PER, PBR, dividend metrics)

**Script**: `scripts/collect_pykrx_fundamentals.py`

**Data Source**: `pykrx.stock.get_market_fundamental(date, market='ALL')`

**Key Implementation**:
```python
def fetch_pykrx_fundamentals(target_date: date, market: str = 'ALL'):
    """
    Fetch pykrx market fundamental data for given date.

    Returns:
        DataFrame with columns: BPS, PER, PBR, EPS, DIV, DPS
        Index: ticker (6-digit stock code)
    """
    from pykrx import stock
    import time

    date_str = target_date.strftime('%Y%m%d')

    # Rate limiting: 2 requests/second
    time.sleep(0.5)

    df = stock.get_market_fundamental(date_str, market=market)

    # Data validation
    df = df[df['DIV'].notna()]  # Filter out missing dividend data
    df = df[(df['PER'] > 0) & (df['PBR'] > 0)]  # Filter negative/zero ratios

    return df

def insert_pykrx_data(ticker: str, target_date: date, data: dict):
    """
    Insert pykrx data into ticker_fundamentals with DAILY period_type.
    """
    query = """
    INSERT INTO ticker_fundamentals (
        ticker, region, date, period_type,
        per, pbr, eps, bps,
        dividend_yield, dividend_per_share,
        data_source, created_at
    )
    VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s,
        %s, NOW()
    )
    ON CONFLICT (ticker, region, date, period_type)
    DO UPDATE SET
        per = EXCLUDED.per,
        pbr = EXCLUDED.pbr,
        eps = EXCLUDED.eps,
        bps = EXCLUDED.bps,
        dividend_yield = EXCLUDED.dividend_yield,
        dividend_per_share = EXCLUDED.dividend_per_share,
        data_source = EXCLUDED.data_source
    """

    params = (
        ticker,
        'KR',
        target_date,
        'DAILY',  # ← KEY: DAILY for pykrx
        data.get('PER'),
        data.get('PBR'),
        data.get('EPS'),
        data.get('BPS'),
        data.get('DIV'),   # pykrx dividend yield (%)
        data.get('DPS'),   # dividend per share (KRW)
        'pykrx'            # ← KEY: data_source tracking
    )

    db.execute_query(query, params)
```

**Execution Strategy**:
```bash
# Backfill historical data (30 days recommended for factor calculation)
python3 scripts/collect_pykrx_fundamentals.py \
    --start 2024-10-01 \
    --end 2025-10-21 \
    --market ALL

# Daily incremental update (run via cron)
python3 scripts/collect_pykrx_fundamentals.py \
    --date today \
    --market ALL
```

**Error Handling**:
- API timeout → Retry with exponential backoff (3 attempts)
- Invalid data (negative PER, null DIV) → Skip ticker, log warning
- Rate limit exceeded → Sleep and retry
- Network error → Log error, continue with next date

**Data Quality Checks**:
- Coverage: Expect 2,700+ tickers per day
- Dividend coverage: >95% of tickers should have non-null DPS
- Value ranges: PER (0-100), PBR (0-20), DIV (0-20%)

---

### 3.2 DART Collection Pipeline

**Purpose**: Collect ANNUAL financial statement data (EBITDA, debt, assets)

**Script**: `scripts/collect_dart_fundamentals.py` (refactor existing)

**Data Source**: DART Open API (금융감독원 전자공시시스템)

**Key Implementation**:
```python
def fetch_dart_financials(corp_code: str, year: int, reprt_code: str = '11011'):
    """
    Fetch DART financial statements.

    Args:
        corp_code: DART corporation code
        year: Fiscal year (e.g., 2024)
        reprt_code: Report type ('11011' = Annual, '11012' = Q1, etc.)

    Returns:
        dict with financial data
    """
    from dart_fss import filings
    import time

    # Rate limiting: 1 request/second
    time.sleep(1.0)

    # Fetch financial statements
    fs = filings.get_corp_code(corp_code).get_financial_statements(year, reprt_code)

    # Extract key metrics
    data = {
        'revenue': extract_value(fs, '매출액'),
        'operating_profit': extract_value(fs, '영업이익'),
        'depreciation': extract_value(fs, '감가상각비'),
        'total_assets': extract_value(fs, '자산총계'),
        'total_liabilities': extract_value(fs, '부채총계'),
        'current_assets': extract_value(fs, '유동자산'),
        'shares_outstanding': extract_shares(fs)
    }

    # Calculate EBITDA
    if data['operating_profit'] and data['depreciation']:
        data['ebitda'] = data['operating_profit'] + data['depreciation']

    return data

def insert_dart_data(ticker: str, fiscal_year: int, data: dict):
    """
    Insert DART data into ticker_fundamentals with ANNUAL period_type.
    """
    query = """
    INSERT INTO ticker_fundamentals (
        ticker, region, date, period_type,
        revenue, operating_profit, depreciation, ebitda,
        total_assets, total_liabilities, current_assets,
        shares_outstanding,
        fiscal_year, data_source, created_at
    )
    VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s,
        %s, %s, NOW()
    )
    ON CONFLICT (ticker, region, date, period_type)
    DO UPDATE SET
        revenue = EXCLUDED.revenue,
        operating_profit = EXCLUDED.operating_profit,
        depreciation = EXCLUDED.depreciation,
        ebitda = EXCLUDED.ebitda,
        total_assets = EXCLUDED.total_assets,
        total_liabilities = EXCLUDED.total_liabilities,
        current_assets = EXCLUDED.current_assets,
        shares_outstanding = EXCLUDED.shares_outstanding,
        fiscal_year = EXCLUDED.fiscal_year,
        data_source = EXCLUDED.data_source
    """

    # Date = fiscal year end date (typically 12-31 or quarter end)
    fiscal_date = date(fiscal_year, 12, 31)  # Adjust for fiscal year end

    params = (
        ticker,
        'KR',
        fiscal_date,
        'ANNUAL',  # ← KEY: ANNUAL for DART
        data.get('revenue'),
        data.get('operating_profit'),
        data.get('depreciation'),
        data.get('ebitda'),
        data.get('total_assets'),
        data.get('total_liabilities'),
        data.get('current_assets'),
        data.get('shares_outstanding'),
        fiscal_year,
        'DART'     # ← KEY: data_source tracking
    )

    db.execute_query(query, params)
```

**Execution Strategy**:
```bash
# Backfill multiple years
python3 scripts/collect_dart_fundamentals.py \
    --year 2024 \
    --year 2023 \
    --year 2022 \
    --limit 100  # Process 100 tickers per run

# Quarterly update (after earnings season)
python3 scripts/collect_dart_fundamentals.py \
    --year 2024 \
    --quarter Q3 \
    --incremental
```

**Error Handling**:
- Missing depreciation data → Skip EBITDA calculation, log warning
- Incomplete financial statements → Mark as partial data, continue
- Corp code mapping failure → Use fallback mapping table
- API error → Retry with exponential backoff (3 attempts)

**Data Quality Checks**:
- EBITDA validation: operating_profit + depreciation consistency
- Balance sheet validation: total_assets = total_liabilities + equity
- Year-over-year consistency: flag >50% changes for review

---

## 4. Factor Calculation Design

### 4.1 Dividend Yield Factor

**Purpose**: Calculate dividend yield as (latest DPS / latest stock price) × 100

**Script**: `scripts/calculate_dividend_yield.py`

**Algorithm**:
```python
def calculate_dividend_yield_factor(db: PostgresDatabaseManager, ticker: str) -> Optional[float]:
    """
    Calculate Dividend Yield factor for given ticker.

    User Requirement:
        "가장 최근 지급한 주당 배당금과 가장 최근 수집한 주가를 기준으로 배당수익률이 계산"

    Returns:
        Dividend yield percentage (e.g., 3.5 for 3.5%)
    """

    # Step 1: Get latest dividend per share from pykrx (DAILY data)
    query_dps = """
    SELECT
        dividend_per_share,
        date as dps_date
    FROM ticker_fundamentals
    WHERE ticker = %s
      AND region = 'KR'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
      AND dividend_per_share IS NOT NULL
      AND dividend_per_share > 0
    ORDER BY date DESC
    LIMIT 1
    """

    dps_result = db.execute_query(query_dps, (ticker,))
    if not dps_result:
        logger.warning(f"{ticker}: No dividend data found")
        return None

    dividend_per_share = float(dps_result[0]['dividend_per_share'])
    dps_date = dps_result[0]['dps_date']

    # Step 2: Get latest stock price from OHLCV
    query_price = """
    SELECT
        close,
        date as price_date
    FROM ohlcv_data
    WHERE ticker = %s
      AND region = 'KR'
      AND close > 0
    ORDER BY date DESC
    LIMIT 1
    """

    price_result = db.execute_query(query_price, (ticker,))
    if not price_result:
        logger.warning(f"{ticker}: No price data found")
        return None

    close_price = float(price_result[0]['close'])
    price_date = price_result[0]['price_date']

    # Step 3: Calculate dividend yield
    dividend_yield = (dividend_per_share / close_price) * 100

    # Data quality validation
    if dividend_yield > 20:
        logger.warning(f"{ticker}: Unusually high dividend yield {dividend_yield:.2f}%")

    # Metadata for logging
    metadata = {
        'dividend_per_share': dividend_per_share,
        'close_price': close_price,
        'dps_date': dps_date,
        'price_date': price_date,
        'date_diff_days': (price_date - dps_date).days
    }

    logger.info(f"{ticker}: Dividend Yield = {dividend_yield:.2f}% | DPS={dividend_per_share} | Price={close_price} | Metadata={metadata}")

    return dividend_yield
```

**Query Pattern - Explicit Filtering**:
```sql
-- CORRECT: Explicit period_type and data_source
SELECT dividend_per_share, date
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND region = 'KR'
  AND period_type = 'DAILY'      -- ← Explicit
  AND data_source = 'pykrx'      -- ← Explicit
  AND dividend_per_share IS NOT NULL
ORDER BY date DESC
LIMIT 1;

-- INCORRECT: Implicit filtering (ambiguous)
SELECT dividend_per_share, date
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND dividend_per_share IS NOT NULL
ORDER BY date DESC
LIMIT 1;
-- ⚠️ This could return DAILY or ANNUAL data unpredictably!
```

**Factor Value Interpretation**:
- Higher dividend yield = Higher factor score (better for income investors)
- raw_score = dividend_yield (NOT negated)
- Percentile ranking: 0-100 (100 = highest dividend yield)

**Data Quality Validation**:
- Dividend yield range: 0-20% (flag if outside)
- Date alignment: DPS date vs price date (log difference)
- Zero/negative values: Filter out invalid data

---

### 4.2 EV/EBITDA Factor

**Purpose**: Calculate Enterprise Value to EBITDA ratio as valuation metric

**Script**: `scripts/calculate_ev_ebitda.py`

**Algorithm**:
```python
def calculate_ev_ebitda_factor(db: PostgresDatabaseManager, ticker: str) -> Optional[float]:
    """
    Calculate EV/EBITDA factor for given ticker.

    Formula:
        EV = Market Cap + Total Debt - Cash
        EV/EBITDA = EV / EBITDA

    Returns:
        EV/EBITDA ratio (e.g., 8.5 for 8.5x EBITDA)
    """

    # Step 1: Get latest EBITDA and financial data from DART (ANNUAL data)
    query_dart = """
    SELECT
        ebitda,
        total_liabilities,
        current_assets,
        shares_outstanding,
        fiscal_year,
        date as financial_date
    FROM ticker_fundamentals
    WHERE ticker = %s
      AND region = 'KR'
      AND period_type = 'ANNUAL'
      AND data_source = 'DART'
      AND ebitda IS NOT NULL
      AND ebitda > 0
    ORDER BY fiscal_year DESC, date DESC
    LIMIT 1
    """

    dart_result = db.execute_query(query_dart, (ticker,))
    if not dart_result:
        logger.warning(f"{ticker}: No DART financial data found")
        return None

    ebitda = float(dart_result[0]['ebitda'])
    total_liabilities = float(dart_result[0]['total_liabilities'] or 0)
    current_assets = float(dart_result[0]['current_assets'] or 0)
    shares_outstanding = float(dart_result[0]['shares_outstanding'])
    fiscal_year = dart_result[0]['fiscal_year']
    financial_date = dart_result[0]['financial_date']

    # Step 2: Get latest stock price from OHLCV
    query_price = """
    SELECT
        close,
        date as price_date
    FROM ohlcv_data
    WHERE ticker = %s
      AND region = 'KR'
      AND close > 0
    ORDER BY date DESC
    LIMIT 1
    """

    price_result = db.execute_query(query_price, (ticker,))
    if not price_result:
        logger.warning(f"{ticker}: No price data found")
        return None

    close_price = float(price_result[0]['close'])
    price_date = price_result[0]['price_date']

    # Step 3: Calculate Enterprise Value
    market_cap = close_price * shares_outstanding
    cash_equivalents = current_assets  # Approximation (DART may not separate cash)
    enterprise_value = market_cap + total_liabilities - cash_equivalents

    # Step 4: Calculate EV/EBITDA
    ev_to_ebitda = enterprise_value / ebitda

    # Data quality validation
    if ev_to_ebitda < 0:
        logger.warning(f"{ticker}: Negative EV/EBITDA {ev_to_ebitda:.2f} (enterprise value < 0)")
        return None

    if ev_to_ebitda > 100:
        logger.warning(f"{ticker}: Unusually high EV/EBITDA {ev_to_ebitda:.2f}")

    # Metadata for logging
    metadata = {
        'market_cap': market_cap,
        'enterprise_value': enterprise_value,
        'ebitda': ebitda,
        'total_liabilities': total_liabilities,
        'cash_approximation': cash_equivalents,
        'shares_outstanding': shares_outstanding,
        'close_price': close_price,
        'fiscal_year': fiscal_year,
        'financial_date': financial_date,
        'price_date': price_date,
        'date_diff_days': (price_date - financial_date).days
    }

    logger.info(f"{ticker}: EV/EBITDA = {ev_to_ebitda:.2f} | EV={enterprise_value/1e12:.2f}T | EBITDA={ebitda/1e12:.2f}T | Metadata={metadata}")

    return ev_to_ebitda
```

**Query Pattern - ANNUAL Data**:
```sql
-- CORRECT: Explicit ANNUAL period_type for financial statements
SELECT
    ebitda,
    total_liabilities,
    current_assets,
    shares_outstanding,
    fiscal_year,
    date
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND region = 'KR'
  AND period_type = 'ANNUAL'    -- ← Explicit
  AND data_source = 'DART'      -- ← Explicit
  AND ebitda IS NOT NULL
  AND ebitda > 0
ORDER BY fiscal_year DESC, date DESC
LIMIT 1;
```

**Factor Value Interpretation**:
- Lower EV/EBITDA = Better value (cheaper relative to earnings)
- raw_score = -log(ev_to_ebitda) for ranking (lower ratio = higher score)
- Percentile ranking: 0-100 (100 = lowest EV/EBITDA, best value)

**Data Quality Validation**:
- EV/EBITDA range: 0-100 (flag if outside)
- Negative EV: Filter out (indicates financial distress or data error)
- Date staleness: Financial date vs price date (log warning if >180 days)
- EBITDA sanity check: Should be positive for valuation

---

## 5. Data Quality Framework

### 5.1 Coverage Monitoring

**Purpose**: Track data availability across tickers and time periods

**Query - pykrx Coverage**:
```sql
-- Daily coverage check
SELECT
    DATE(o.date) as check_date,
    COUNT(DISTINCT o.ticker) as ohlcv_tickers,
    COUNT(DISTINCT f.ticker) as pykrx_tickers,
    ROUND(
        COUNT(DISTINCT f.ticker)::numeric /
        NULLIF(COUNT(DISTINCT o.ticker), 0) * 100,
        2
    ) as coverage_pct
FROM ohlcv_data o
LEFT JOIN ticker_fundamentals f
    ON o.ticker = f.ticker
    AND DATE(f.date) = DATE(o.date)
    AND f.period_type = 'DAILY'
    AND f.data_source = 'pykrx'
WHERE o.region = 'KR'
  AND o.date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(o.date)
ORDER BY check_date DESC;
```

**Target Metrics**:
- pykrx coverage: >75% of OHLCV universe (baseline: 77%)
- DART coverage: >80% of active tickers (baseline: TBD)
- Alert threshold: Coverage drops below 70%

**Query - DART Coverage**:
```sql
-- DART coverage by fiscal year
SELECT
    fiscal_year,
    COUNT(DISTINCT ticker) as tickers_with_data,
    COUNT(DISTINCT CASE WHEN ebitda IS NOT NULL THEN ticker END) as tickers_with_ebitda
FROM ticker_fundamentals
WHERE region = 'KR'
  AND period_type = 'ANNUAL'
  AND data_source = 'DART'
GROUP BY fiscal_year
ORDER BY fiscal_year DESC;
```

---

### 5.2 Freshness Validation

**Purpose**: Detect stale data that needs refresh

**Query - Data Staleness**:
```sql
-- Check data freshness by source
SELECT
    data_source,
    period_type,
    MAX(date) as latest_date,
    CURRENT_DATE - MAX(date) as days_stale,
    COUNT(DISTINCT ticker) as ticker_count
FROM ticker_fundamentals
WHERE region = 'KR'
GROUP BY data_source, period_type
ORDER BY data_source, period_type;
```

**Alert Thresholds**:
```python
FRESHNESS_THRESHOLDS = {
    ('pykrx', 'DAILY'): 3,      # Alert if >3 days old
    ('DART', 'ANNUAL'): 90,     # Alert if >90 days old (quarterly cycle)
    ('DART', 'QUARTERLY'): 45   # Alert if >45 days old
}

def check_data_freshness(db):
    results = db.execute_query(FRESHNESS_QUERY)

    for row in results:
        source = row['data_source']
        period = row['period_type']
        staleness = row['days_stale']

        threshold = FRESHNESS_THRESHOLDS.get((source, period), 7)

        if staleness > threshold:
            logger.warning(
                f"Stale data detected: {source} {period} | "
                f"{staleness} days old (threshold: {threshold})"
            )
```

---

### 5.3 Source-Specific Quality Metrics

**pykrx Quality Checks**:
```python
def validate_pykrx_data(db, target_date: date):
    """
    Validate pykrx data quality for given date.
    """

    # Check 1: Dividend coverage (expect >95% non-null DPS)
    query_dividend = """
    SELECT
        COUNT(*) as total_tickers,
        COUNT(CASE WHEN dividend_per_share IS NOT NULL THEN 1 END) as with_dividend,
        ROUND(
            COUNT(CASE WHEN dividend_per_share IS NOT NULL THEN 1 END)::numeric /
            COUNT(*) * 100,
            2
        ) as dividend_coverage_pct
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
      AND date = %s
    """

    result = db.execute_query(query_dividend, (target_date,))
    coverage = result[0]['dividend_coverage_pct']

    if coverage < 95:
        logger.warning(f"Low dividend coverage: {coverage}% (expected >95%)")

    # Check 2: Value distribution sanity
    query_distribution = """
    SELECT
        AVG(per) as avg_per,
        AVG(pbr) as avg_pbr,
        AVG(dividend_yield) as avg_div,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY per) as median_per,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pbr) as median_pbr
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
      AND date = %s
      AND per > 0 AND pbr > 0
    """

    stats = db.execute_query(query_distribution, (target_date,))

    # Sanity checks
    if stats[0]['avg_per'] > 50 or stats[0]['avg_per'] < 5:
        logger.warning(f"Unusual average PER: {stats[0]['avg_per']:.2f}")

    if stats[0]['avg_pbr'] > 5 or stats[0]['avg_pbr'] < 0.5:
        logger.warning(f"Unusual average PBR: {stats[0]['avg_pbr']:.2f}")
```

**DART Quality Checks**:
```python
def validate_dart_data(db, fiscal_year: int):
    """
    Validate DART data quality for given fiscal year.
    """

    # Check 1: EBITDA calculation success rate
    query_ebitda = """
    SELECT
        COUNT(*) as total_records,
        COUNT(CASE WHEN ebitda IS NOT NULL THEN 1 END) as with_ebitda,
        COUNT(CASE WHEN operating_profit IS NOT NULL AND depreciation IS NOT NULL THEN 1 END) as with_inputs,
        ROUND(
            COUNT(CASE WHEN ebitda IS NOT NULL THEN 1 END)::numeric /
            COUNT(*) * 100,
            2
        ) as ebitda_success_rate
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND period_type = 'ANNUAL'
      AND data_source = 'DART'
      AND fiscal_year = %s
    """

    result = db.execute_query(query_ebitda, (fiscal_year,))
    success_rate = result[0]['ebitda_success_rate']

    if success_rate < 80:
        logger.warning(f"Low EBITDA calculation success: {success_rate}% (expected >80%)")

    # Check 2: Balance sheet consistency
    query_balance = """
    SELECT
        ticker,
        total_assets,
        total_liabilities,
        total_equity,
        ABS(total_assets - (total_liabilities + total_equity)) as balance_error
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND period_type = 'ANNUAL'
      AND data_source = 'DART'
      AND fiscal_year = %s
      AND total_assets IS NOT NULL
    """

    results = db.execute_query(query_balance, (fiscal_year,))

    for row in results:
        # Allow 1% tolerance for rounding
        if row['balance_error'] > row['total_assets'] * 0.01:
            logger.warning(
                f"{row['ticker']}: Balance sheet inconsistency | "
                f"Error: {row['balance_error']/1e9:.2f}B KRW"
            )
```

---

### 5.4 Anomaly Detection

**Purpose**: Identify unusual values that may indicate data errors

**Dividend Yield Anomalies**:
```sql
-- Detect unusually high dividend yields (>20%)
SELECT
    f.ticker,
    t.name,
    f.dividend_yield,
    f.dividend_per_share,
    o.close as current_price,
    f.date
FROM ticker_fundamentals f
JOIN tickers t ON f.ticker = t.ticker AND f.region = t.region
LEFT JOIN LATERAL (
    SELECT close FROM ohlcv_data
    WHERE ticker = f.ticker AND region = 'KR'
    ORDER BY date DESC LIMIT 1
) o ON true
WHERE f.region = 'KR'
  AND f.period_type = 'DAILY'
  AND f.data_source = 'pykrx'
  AND f.dividend_yield > 20
ORDER BY f.dividend_yield DESC;
```

**EV/EBITDA Anomalies**:
```sql
-- Detect negative or extreme EV/EBITDA values
WITH ev_calculation AS (
    SELECT
        f.ticker,
        t.name,
        o.close * f.shares_outstanding as market_cap,
        (o.close * f.shares_outstanding + f.total_liabilities - f.current_assets) as enterprise_value,
        f.ebitda,
        (o.close * f.shares_outstanding + f.total_liabilities - f.current_assets) / NULLIF(f.ebitda, 0) as ev_to_ebitda
    FROM ticker_fundamentals f
    JOIN tickers t ON f.ticker = t.ticker AND f.region = t.region
    LEFT JOIN LATERAL (
        SELECT close FROM ohlcv_data
        WHERE ticker = f.ticker AND region = 'KR'
        ORDER BY date DESC LIMIT 1
    ) o ON true
    WHERE f.region = 'KR'
      AND f.period_type = 'ANNUAL'
      AND f.data_source = 'DART'
      AND f.ebitda IS NOT NULL
)
SELECT *
FROM ev_calculation
WHERE ev_to_ebitda < 0 OR ev_to_ebitda > 100
ORDER BY ev_to_ebitda DESC;
```

**Spike Detection (Time Series)**:
```python
def detect_value_spikes(db, factor_name: str, ticker: str, window_days: int = 30):
    """
    Detect sudden spikes in factor values using Z-score.
    """

    query = """
    SELECT
        date,
        dividend_yield,
        AVG(dividend_yield) OVER (
            ORDER BY date
            ROWS BETWEEN %s PRECEDING AND 1 PRECEDING
        ) as rolling_avg,
        STDDEV(dividend_yield) OVER (
            ORDER BY date
            ROWS BETWEEN %s PRECEDING AND 1 PRECEDING
        ) as rolling_std
    FROM ticker_fundamentals
    WHERE ticker = %s
      AND region = 'KR'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
      AND dividend_yield IS NOT NULL
    ORDER BY date DESC
    LIMIT 90
    """

    results = db.execute_query(query, (window_days, window_days, ticker))

    for row in results:
        if row['rolling_std'] and row['rolling_std'] > 0:
            z_score = (row['dividend_yield'] - row['rolling_avg']) / row['rolling_std']

            if abs(z_score) > 3:
                logger.warning(
                    f"{ticker}: Value spike detected | "
                    f"Date: {row['date']} | "
                    f"Value: {row['dividend_yield']:.2f} | "
                    f"Z-score: {z_score:.2f}"
                )
```

---

## 6. Extensibility Framework

### 6.1 Multi-Source Priority System

**Design Pattern**: Configuration-driven source priority with automatic fallback

**Configuration**:
```python
# config/data_source_priority.yaml
data_source_priority:
  dividend_yield:
    primary: pykrx
    fallback:
      - yfinance
      - manual
    quality_threshold: 0.8

  dividend_per_share:
    primary: pykrx
    fallback:
      - yfinance
      - DART  # DART may add dividend data in future
    quality_threshold: 0.8

  ebitda:
    primary: DART
    fallback:
      - bloomberg
      - manual
    quality_threshold: 0.9

  per:
    primary: pykrx
    fallback:
      - DART
      - yfinance
    quality_threshold: 0.7
```

**Implementation**:
```python
class MultiSourceDataProvider:
    """
    Provides fundamental data with automatic source fallback.
    """

    def __init__(self, db: PostgresDatabaseManager, config_path: str):
        self.db = db
        self.config = self._load_config(config_path)

    def get_field_value(
        self,
        ticker: str,
        field_name: str,
        period_type: str,
        date_range: Optional[tuple] = None
    ) -> Optional[dict]:
        """
        Get field value with source fallback.

        Returns:
            {
                'value': field_value,
                'source': data_source,
                'date': data_date,
                'quality_score': 0.0-1.0
            }
        """

        # Get priority list for field
        priority_config = self.config['data_source_priority'].get(field_name)
        if not priority_config:
            raise ValueError(f"No priority configuration for field: {field_name}")

        sources = [priority_config['primary']] + priority_config.get('fallback', [])
        quality_threshold = priority_config.get('quality_threshold', 0.0)

        # Try each source in order
        for source in sources:
            result = self._query_source(ticker, field_name, period_type, source, date_range)

            if result and self._validate_quality(result, quality_threshold):
                logger.info(f"{ticker}.{field_name}: Using source '{source}' (quality: {result['quality_score']:.2f})")
                return result

            logger.debug(f"{ticker}.{field_name}: Source '{source}' failed (quality check or no data)")

        logger.warning(f"{ticker}.{field_name}: No valid data found from any source")
        return None

    def _query_source(
        self,
        ticker: str,
        field_name: str,
        period_type: str,
        source: str,
        date_range: Optional[tuple]
    ) -> Optional[dict]:
        """
        Query specific data source.
        """

        query = f"""
        SELECT
            {field_name} as value,
            date,
            data_source
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = 'KR'
          AND period_type = %s
          AND data_source = %s
          AND {field_name} IS NOT NULL
        """

        params = [ticker, period_type, source]

        if date_range:
            query += " AND date BETWEEN %s AND %s"
            params.extend(date_range)

        query += " ORDER BY date DESC LIMIT 1"

        result = self.db.execute_query(query, tuple(params))

        if not result:
            return None

        row = result[0]

        # Calculate quality score (simplified)
        quality_score = self._calculate_quality_score(row)

        return {
            'value': row['value'],
            'source': row['data_source'],
            'date': row['date'],
            'quality_score': quality_score
        }

    def _calculate_quality_score(self, data: dict) -> float:
        """
        Calculate data quality score (0.0-1.0).

        Factors:
        - Freshness (date proximity)
        - Completeness (missing fields)
        - Consistency (historical volatility)
        """

        from datetime import date, timedelta

        # Freshness score (decay over time)
        data_date = data['date']
        days_old = (date.today() - data_date).days
        freshness_score = max(0, 1.0 - days_old / 365)  # Linear decay over 1 year

        # Completeness score (placeholder - would check related fields)
        completeness_score = 1.0

        # Overall quality (weighted average)
        quality_score = (
            freshness_score * 0.6 +
            completeness_score * 0.4
        )

        return quality_score

    def _validate_quality(self, result: dict, threshold: float) -> bool:
        """
        Validate data quality against threshold.
        """
        return result['quality_score'] >= threshold
```

**Usage Example**:
```python
provider = MultiSourceDataProvider(db, 'config/data_source_priority.yaml')

# Automatic fallback: pykrx → yfinance → manual
dividend_data = provider.get_field_value(
    ticker='005930',
    field_name='dividend_yield',
    period_type='DAILY'
)

if dividend_data:
    print(f"Dividend Yield: {dividend_data['value']}% (source: {dividend_data['source']})")
```

---

### 6.2 Adding New Data Source (Example: yfinance)

**Step 1: Create Collection Script**

**File**: `scripts/collect_yfinance_fundamentals.py`

```python
#!/usr/bin/env python3
"""
Collect fundamental data from yfinance API.

Usage:
    python3 scripts/collect_yfinance_fundamentals.py --tickers 005930.KS 000660.KS
"""

import yfinance as yf
from datetime import date
from modules.db_manager_postgres import PostgresDatabaseManager

def fetch_yfinance_fundamentals(ticker: str):
    """
    Fetch fundamental data from yfinance.

    Args:
        ticker: Yahoo Finance ticker (e.g., '005930.KS' for Samsung Electronics)

    Returns:
        dict with fundamental data
    """

    stock = yf.Ticker(ticker)
    info = stock.info

    # Extract relevant fields
    data = {
        'per': info.get('trailingPE'),
        'pbr': info.get('priceToBook'),
        'dividend_yield': info.get('dividendYield') * 100 if info.get('dividendYield') else None,
        'dividend_per_share': info.get('dividendRate'),
        'market_cap': info.get('marketCap'),
        'enterprise_value': info.get('enterpriseValue'),
        'ebitda': info.get('ebitda')
    }

    return data

def insert_yfinance_data(db: PostgresDatabaseManager, ticker: str, data: dict):
    """
    Insert yfinance data into ticker_fundamentals.
    """

    # Convert Yahoo ticker to KR ticker (remove '.KS' suffix)
    kr_ticker = ticker.replace('.KS', '')

    query = """
    INSERT INTO ticker_fundamentals (
        ticker, region, date, period_type,
        per, pbr,
        dividend_yield, dividend_per_share,
        market_cap, enterprise_value, ebitda,
        data_source, created_at
    )
    VALUES (
        %s, %s, %s, %s,
        %s, %s,
        %s, %s,
        %s, %s, %s,
        %s, NOW()
    )
    ON CONFLICT (ticker, region, date, period_type)
    DO UPDATE SET
        per = EXCLUDED.per,
        pbr = EXCLUDED.pbr,
        dividend_yield = EXCLUDED.dividend_yield,
        dividend_per_share = EXCLUDED.dividend_per_share,
        market_cap = EXCLUDED.market_cap,
        enterprise_value = EXCLUDED.enterprise_value,
        ebitda = EXCLUDED.ebitda,
        data_source = EXCLUDED.data_source
    """

    params = (
        kr_ticker,
        'KR',
        date.today(),
        'DAILY',  # yfinance provides real-time/daily data
        data.get('per'),
        data.get('pbr'),
        data.get('dividend_yield'),
        data.get('dividend_per_share'),
        data.get('market_cap'),
        data.get('enterprise_value'),
        data.get('ebitda'),
        'yfinance'  # ← KEY: New data source
    )

    db.execute_query(query, params)

# ... rest of implementation
```

**Step 2: Update Priority Configuration**

**File**: `config/data_source_priority.yaml`

```yaml
data_source_priority:
  dividend_yield:
    primary: pykrx
    fallback:
      - yfinance  # ← NEW: Add yfinance as fallback
      - manual
    quality_threshold: 0.8

  # ... other fields
```

**Step 3: No Changes to Factor Calculation**

Existing factor calculation scripts (`calculate_dividend_yield.py`) continue to work because:
- They query by `period_type` and `data_source` explicitly
- OR they use `MultiSourceDataProvider` with automatic fallback

**Step 4: Test Integration**

```bash
# Collect yfinance data
python3 scripts/collect_yfinance_fundamentals.py --tickers 005930.KS

# Verify data stored
psql -d quant_platform -c "
SELECT ticker, date, period_type, data_source, dividend_yield
FROM ticker_fundamentals
WHERE ticker = '005930' AND data_source = 'yfinance'
ORDER BY date DESC LIMIT 5;
"

# Calculate factors (should use pykrx first, yfinance as fallback)
python3 scripts/calculate_dividend_yield.py --ticker 005930
```

---

### 6.3 Conflict Resolution Strategy

**Scenario**: Same ticker, same date, same period_type, but different data sources

**Example**:
```sql
-- Both records inserted on same date
('005930', 'KR', '2025-10-21', 'DAILY', 3.5, 'pykrx')   -- dividend_yield = 3.5%
('005930', 'KR', '2025-10-21', 'DAILY', 3.8, 'yfinance') -- dividend_yield = 3.8%
```

**Problem**: Unique constraint `(ticker, region, date, period_type)` prevents both records.

**Solution Options**:

**Option 1: Priority-Based Upsert (Recommended)**
```python
# Only insert if higher priority source OR existing source is lower priority
query = """
INSERT INTO ticker_fundamentals (...)
VALUES (...)
ON CONFLICT (ticker, region, date, period_type)
DO UPDATE SET
    dividend_yield = CASE
        WHEN (
            SELECT priority FROM data_source_priority
            WHERE source = EXCLUDED.data_source
        ) > (
            SELECT priority FROM data_source_priority
            WHERE source = ticker_fundamentals.data_source
        )
        THEN EXCLUDED.dividend_yield
        ELSE ticker_fundamentals.dividend_yield
    END,
    data_source = CASE ... END
"""
```

**Option 2: Multi-Value Storage (Complex)**
```sql
-- Add JSONB column to store multiple source values
ALTER TABLE ticker_fundamentals
ADD COLUMN dividend_yield_sources JSONB;

-- Example value:
{
  "pykrx": {"value": 3.5, "quality_score": 0.95, "timestamp": "2025-10-21T09:00:00"},
  "yfinance": {"value": 3.8, "quality_score": 0.85, "timestamp": "2025-10-21T09:05:00"}
}
```

**Option 3: Separate Tables by Source (Not Recommended)**
- Violates Option B design principle
- Would revert to Option A complexity

**Recommended**: Option 1 (Priority-Based Upsert) with configurable source priorities.

---

## 7. Implementation Specifications

### 7.1 File Structure

```
spock/
│
├── scripts/
│   ├── collect_pykrx_fundamentals.py       # New: pykrx collection
│   ├── collect_dart_fundamentals.py         # Refactor: DART collection
│   ├── calculate_dividend_yield.py          # New: Dividend Yield factor
│   ├── calculate_ev_ebitda.py               # New: EV/EBITDA factor
│   ├── validate_fundamentals_data.py        # New: Data quality validation
│   └── monitor_data_quality.py              # New: Daily monitoring cron
│
├── modules/
│   ├── factors/
│   │   ├── value_factors.py                 # Update: Add new factors
│   │   ├── multi_source_provider.py         # New: Multi-source data access
│   │   └── independence_validator.py        # Existing: Validate new factors
│   │
│   └── db_manager_postgres.py               # Existing: PostgreSQL interface
│
├── config/
│   ├── data_source_priority.yaml            # New: Source priority config
│   └── data_quality_thresholds.yaml         # New: Quality alert thresholds
│
├── tests/
│   ├── test_pykrx_collection.py
│   ├── test_dart_collection.py
│   ├── test_dividend_yield_factor.py
│   ├── test_ev_ebitda_factor.py
│   └── test_multi_source_provider.py
│
└── docs/
    ├── OPTION_B_IMPLEMENTATION_DESIGN.md    # This document
    └── DATA_QUALITY_MONITORING.md           # New: Quality monitoring guide
```

---

### 7.2 Function Signatures

**Data Collection**:
```python
# scripts/collect_pykrx_fundamentals.py
def fetch_pykrx_fundamentals(
    target_date: date,
    market: str = 'ALL'
) -> pd.DataFrame:
    """Fetch pykrx market fundamental data."""

def insert_pykrx_data(
    db: PostgresDatabaseManager,
    ticker: str,
    target_date: date,
    data: dict
) -> bool:
    """Insert pykrx data with period_type='DAILY'."""

# scripts/collect_dart_fundamentals.py
def fetch_dart_financials(
    corp_code: str,
    year: int,
    reprt_code: str = '11011'
) -> dict:
    """Fetch DART financial statements."""

def insert_dart_data(
    db: PostgresDatabaseManager,
    ticker: str,
    fiscal_year: int,
    data: dict
) -> bool:
    """Insert DART data with period_type='ANNUAL'."""
```

**Factor Calculation**:
```python
# scripts/calculate_dividend_yield.py
def calculate_dividend_yield_factor(
    db: PostgresDatabaseManager,
    ticker: str
) -> Optional[float]:
    """Calculate Dividend Yield factor (latest DPS / latest price)."""

def save_factor_scores(
    db: PostgresDatabaseManager,
    factor_name: str,
    scores: List[tuple]  # [(ticker, raw_score, percentile), ...]
) -> None:
    """Save factor scores to factor_scores table."""

# scripts/calculate_ev_ebitda.py
def calculate_ev_ebitda_factor(
    db: PostgresDatabaseManager,
    ticker: str
) -> Optional[float]:
    """Calculate EV/EBITDA factor."""
```

**Data Quality**:
```python
# scripts/validate_fundamentals_data.py
def check_coverage(
    db: PostgresDatabaseManager,
    data_source: str,
    period_type: str,
    target_date: date
) -> dict:
    """Check data coverage for given source and date."""

def check_freshness(
    db: PostgresDatabaseManager,
    data_source: str,
    period_type: str
) -> dict:
    """Check data freshness (staleness)."""

def detect_anomalies(
    db: PostgresDatabaseManager,
    factor_name: str,
    threshold_z_score: float = 3.0
) -> List[dict]:
    """Detect anomalous factor values."""
```

---

### 7.3 API Contracts

**Configuration Files**:

**File**: `config/data_source_priority.yaml`
```yaml
# Data source priority configuration
# Higher priority sources are queried first

data_source_priority:
  dividend_yield:
    primary: pykrx
    fallback:
      - yfinance
      - manual
    quality_threshold: 0.8

  dividend_per_share:
    primary: pykrx
    fallback:
      - yfinance
    quality_threshold: 0.8

  ebitda:
    primary: DART
    fallback:
      - bloomberg
      - manual
    quality_threshold: 0.9

  per:
    primary: pykrx
    fallback:
      - DART
      - yfinance
    quality_threshold: 0.7

# Source priority scores (used for conflict resolution)
source_priority_scores:
  pykrx: 100
  DART: 90
  yfinance: 80
  bloomberg: 95
  manual: 50
```

**File**: `config/data_quality_thresholds.yaml`
```yaml
# Data quality alert thresholds

coverage_thresholds:
  pykrx:
    DAILY: 0.75  # 75% of OHLCV universe
  DART:
    ANNUAL: 0.80  # 80% of active tickers

freshness_thresholds:
  pykrx:
    DAILY: 3     # days
  DART:
    ANNUAL: 90   # days
    QUARTERLY: 45

anomaly_thresholds:
  dividend_yield:
    max_value: 20.0   # %
    z_score: 3.0

  ev_to_ebitda:
    min_value: 0.0
    max_value: 100.0
    z_score: 3.0

alerting:
  email: alerts@example.com
  slack_webhook: https://hooks.slack.com/...
```

---

## 8. Deployment Workflow

### Phase 1: Data Collection (Parallel Execution)

**Terminal 1: pykrx Collection**
```bash
# Backfill 90 days of pykrx data (recommended for factor calculation)
python3 scripts/collect_pykrx_fundamentals.py \
    --start 2024-07-23 \
    --end 2025-10-21 \
    --market ALL \
    --dry-run  # Preview first

# Actual execution
python3 scripts/collect_pykrx_fundamentals.py \
    --start 2024-07-23 \
    --end 2025-10-21 \
    --market ALL

# Expected output:
# ✅ 2024-07-23: 2,712 tickers collected
# ✅ 2024-07-24: 2,715 tickers collected
# ...
# ✅ 2025-10-21: 2,708 tickers collected
# Total: 243,180 records inserted (90 days × ~2,700 tickers)
```

**Terminal 2: DART Collection (Can Run Simultaneously)**
```bash
# Backfill 2024 annual data
python3 scripts/collect_dart_fundamentals.py \
    --year 2024 \
    --limit 100 \
    --dry-run  # Preview first

# Actual execution
python3 scripts/collect_dart_fundamentals.py \
    --year 2024 \
    --limit 100

# Expected output:
# ✅ 005930 (삼성전자): EBITDA calculated, data saved
# ✅ 000660 (SK하이닉스): EBITDA calculated, data saved
# ...
# Total: 100 records inserted
```

**Validation Checkpoint 1**:
```bash
# Check data collection results
python3 scripts/validate_fundamentals_data.py \
    --check-coverage \
    --check-freshness

# Expected output:
# Coverage Report:
#   pykrx DAILY: 2,708 / 3,521 tickers (76.9%) ✅
#   DART ANNUAL: 100 / 3,521 tickers (2.8%) ⏳ (ongoing)
#
# Freshness Report:
#   pykrx DAILY: Latest 2025-10-21 (0 days old) ✅
#   DART ANNUAL: Latest 2024-12-31 (294 days old) ✅
```

---

### Phase 2: Data Quality Validation

**Step 1: Coverage Analysis**
```bash
# Detailed coverage breakdown
psql -d quant_platform -c "
SELECT
    data_source,
    period_type,
    COUNT(DISTINCT ticker) as ticker_count,
    MIN(date) as earliest_date,
    MAX(date) as latest_date,
    COUNT(*) as total_records
FROM ticker_fundamentals
WHERE region = 'KR'
GROUP BY data_source, period_type
ORDER BY data_source, period_type;
"

# Expected output:
#  data_source | period_type | ticker_count | earliest_date | latest_date | total_records
# -------------+-------------+--------------+---------------+-------------+---------------
#  pykrx       | DAILY       |         2708 | 2024-07-23    | 2025-10-21  |        243180
#  DART        | ANNUAL      |          100 | 2024-12-31    | 2024-12-31  |           100
```

**Step 2: Quality Checks**
```bash
# Run comprehensive quality validation
python3 scripts/validate_fundamentals_data.py \
    --check-coverage \
    --check-freshness \
    --check-anomalies \
    --report-path results/data_quality_report_20251028.txt

# Review anomalies (if any)
cat results/data_quality_report_20251028.txt
```

**Validation Checkpoint 2**:
- pykrx coverage ≥75%: ✅
- DART coverage ≥50 tickers: ✅
- No critical anomalies: ✅ (or review flagged tickers)
- Data freshness within thresholds: ✅

---

### Phase 3: Factor Calculation

**Step 1: Calculate Dividend Yield**
```bash
# Calculate Dividend Yield factor for all tickers with pykrx data
python3 scripts/calculate_dividend_yield.py \
    --dry-run  # Preview calculation

# Actual execution
python3 scripts/calculate_dividend_yield.py

# Expected output:
# 📊 Calculating Dividend Yield for 2,708 tickers...
# ✅ 005930: Dividend Yield = 3.24% | DPS=1444 | Price=44500
# ✅ 000660: Dividend Yield = 1.85% | DPS=2000 | Price=108000
# ...
# 💾 Saving to database...
# ✅ Saved 2,708 factor scores
#
# Top 20 High-Yield Stocks:
#   1. 123456 (Some Stock): 8.5%
#   2. 234567 (Another Stock): 7.2%
#   ...
```

**Step 2: Calculate EV/EBITDA**
```bash
# Calculate EV/EBITDA factor for tickers with DART data
python3 scripts/calculate_ev_ebitda.py \
    --dry-run  # Preview calculation

# Actual execution
python3 scripts/calculate_ev_ebitda.py

# Expected output:
# 📊 Calculating EV/EBITDA for 100 tickers...
# ✅ 005930: EV/EBITDA = 8.5 | EV=456.2T | EBITDA=53.6T
# ✅ 000660: EV/EBITDA = 12.3 | EV=98.5T | EBITDA=8.0T
# ...
# 💾 Saving to database...
# ✅ Saved 100 factor scores
#
# Top 20 Value Stocks (Low EV/EBITDA):
#   1. 123456 (Some Stock): 3.2x
#   2. 234567 (Another Stock): 4.5x
#   ...
```

**Validation Checkpoint 3**:
```bash
# Verify factor scores saved
psql -d quant_platform -c "
SELECT
    factor_name,
    COUNT(DISTINCT ticker) as ticker_count,
    MIN(percentile) as min_percentile,
    MAX(percentile) as max_percentile,
    AVG(percentile) as avg_percentile
FROM factor_scores
WHERE region = 'KR'
  AND date = CURRENT_DATE
  AND factor_name IN ('Dividend_Yield', 'EV_EBITDA')
GROUP BY factor_name;
"

# Expected output:
#   factor_name   | ticker_count | min_percentile | max_percentile | avg_percentile
# ----------------+--------------+----------------+----------------+----------------
#  Dividend_Yield |         2708 |           0.00 |         100.00 |          50.00
#  EV_EBITDA      |          100 |           0.00 |         100.00 |          50.00
```

---

### Phase 4: Factor Validation

**Step 1: Factor Independence Check**
```bash
# Validate independence of new factors with existing factors
python3 modules/factors/independence_validator.py \
    --start-date 2024-10-01 \
    --end-date 2025-10-21 \
    --factors Dividend_Yield,EV_EBITDA,PB_Ratio,PE_Ratio \
    --threshold 0.5 \
    --report-path results/independence_validation_20251028.txt

# Expected output:
# Independence Validation Report
# ==============================
# Date: 2025-10-28
# Period: 2024-10-01 to 2025-10-21
# Threshold: |r| < 0.5
#
# Results:
#   Total pairs tested: 6
#   Independent pairs: 5 (83.3%)
#   Correlated pairs: 1
#
# Correlated Factors:
#   Dividend_Yield ↔ PB_Ratio: r=0.52 ⚠️
#   (Both may be value indicators, acceptable correlation)
```

**Step 2: Review and Adjust**
```bash
# Review detailed correlation report
cat results/independence_validation_20251028.txt

# If correlations are acceptable, proceed
# If correlations are too high (r > 0.7), consider:
#   - Adjusting factor weights in portfolio construction
#   - Excluding redundant factor
#   - Using orthogonalization techniques
```

**Validation Checkpoint 4**:
- Independence rate ≥80%: ✅
- No perfect correlations (r=1.0): ✅
- Critical correlations reviewed: ✅

---

### Phase 5: Production Integration

**Step 1: Update Factor Library**
```bash
# Update value_factors.py to include new factors
python3 modules/factors/value_factors.py --list-factors

# Expected output:
# Available Value Factors:
#   - PE_Ratio (P/E) ✅
#   - PB_Ratio (P/B) ✅
#   - EV_EBITDA (EV/EBITDA) ✅ NEW
#   - Dividend_Yield (배당수익률) ✅ NEW
```

**Step 2: Setup Automated Monitoring**
```bash
# Add cron job for daily data collection and validation
crontab -e

# Add lines:
# Daily pykrx collection (market close + 30 min)
30 15 * * 1-5 cd /Users/13ruce/spock && python3 scripts/collect_pykrx_fundamentals.py --date today >> log/pykrx_collection.log 2>&1

# Daily data quality check (evening)
0 20 * * * cd /Users/13ruce/spock && python3 scripts/monitor_data_quality.py >> log/data_quality.log 2>&1

# Weekly factor re-calculation (Sunday midnight)
0 0 * * 0 cd /Users/13ruce/spock && python3 scripts/calculate_dividend_yield.py && python3 scripts/calculate_ev_ebitda.py >> log/factor_calculation.log 2>&1
```

**Step 3: Monitoring Dashboard Setup**
```bash
# Create Grafana dashboard for data quality metrics
# (Manual setup via Grafana UI)

# Import dashboard template:
#   - Data coverage chart (pykrx vs DART)
#   - Data freshness gauge
#   - Anomaly alert panel
#   - Factor distribution histograms
```

---

### Rollback Procedure (If Issues Found)

```bash
# Step 1: Stop automated jobs
crontab -e
# Comment out relevant cron jobs

# Step 2: Remove bad data
psql -d quant_platform

# Remove pykrx data from specific date range
DELETE FROM ticker_fundamentals
WHERE data_source = 'pykrx'
  AND period_type = 'DAILY'
  AND date BETWEEN '2025-10-21' AND '2025-10-21';

# Remove derived factors
DELETE FROM factor_scores
WHERE factor_name IN ('Dividend_Yield', 'EV_EBITDA')
  AND date >= '2025-10-21';

# Step 3: Re-run collection with fixes
python3 scripts/collect_pykrx_fundamentals.py --date 2025-10-21

# Step 4: Re-calculate factors
python3 scripts/calculate_dividend_yield.py
python3 scripts/calculate_ev_ebitda.py

# Step 5: Validate again
python3 scripts/validate_fundamentals_data.py --check-all
```

---

## 9. Performance Benchmarks

### 9.1 Data Collection Performance

**pykrx Collection**:
- Single day, all tickers: ~30 seconds (2,700 tickers)
- 90 days backfill: ~45 minutes
- Rate limit: 2 requests/second (0.5s delay)

**DART Collection**:
- Single ticker, 1 year: ~2 seconds
- 100 tickers, 1 year: ~4 minutes
- Rate limit: 1 request/second (1.0s delay)

**Optimization Strategies**:
- Parallel execution (pykrx and DART simultaneously)
- Batch inserts (100 records per transaction)
- Connection pooling (reuse DB connections)

---

### 9.2 Query Performance

**Single Ticker Lookup**:
```sql
-- Dividend Yield data (pykrx DAILY)
SELECT dividend_per_share, date
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND region = 'KR'
  AND period_type = 'DAILY'
  AND data_source = 'pykrx'
ORDER BY date DESC
LIMIT 1;
-- Performance: <5ms with index
```

**Cross-Sectional Query** (all tickers at date):
```sql
-- All tickers with dividend data on 2025-10-21
SELECT ticker, dividend_per_share, dividend_yield
FROM ticker_fundamentals
WHERE region = 'KR'
  AND period_type = 'DAILY'
  AND data_source = 'pykrx'
  AND date = '2025-10-21'
  AND dividend_per_share IS NOT NULL;
-- Performance: <50ms with index (2,700 rows)
```

**Optimization Applied**:
- Partial indexes on period_type (see Section 2.3)
- Composite indexes for common query patterns
- Query result caching (Redis, if needed)

---

### 9.3 Factor Calculation Performance

**Dividend Yield (2,708 tickers)**:
- Data fetch: ~2 seconds
- Calculation: <1 second
- Percentile ranking: <1 second
- Database save: ~3 seconds
- **Total: ~7 seconds** ✅

**EV/EBITDA (100 tickers)**:
- Data fetch: ~1 second
- Calculation: <1 second
- Percentile ranking: <1 second
- Database save: <1 second
- **Total: ~3 seconds** ✅

---

## 10. Testing Strategy

### 10.1 Unit Tests

**Test Coverage Targets**:
- Data collection: 80%+
- Factor calculation: 90%+
- Data quality validation: 85%+

**Example Test Cases**:

**File**: `tests/test_pykrx_collection.py`
```python
def test_fetch_pykrx_fundamentals():
    """Test pykrx data fetch."""
    from scripts.collect_pykrx_fundamentals import fetch_pykrx_fundamentals
    from datetime import date

    df = fetch_pykrx_fundamentals(date(2025, 10, 21))

    assert len(df) > 2500, "Expected >2500 tickers"
    assert 'DIV' in df.columns, "Missing DIV column"
    assert df['DIV'].notna().sum() > 2500, "Expected >2500 non-null dividends"

def test_insert_pykrx_data():
    """Test pykrx data insertion."""
    from scripts.collect_pykrx_fundamentals import insert_pykrx_data
    from modules.db_manager_postgres import PostgresDatabaseManager
    from datetime import date

    db = PostgresDatabaseManager()

    test_data = {
        'PER': 10.5,
        'PBR': 1.2,
        'DIV': 3.5,
        'DPS': 1444
    }

    result = insert_pykrx_data(db, '005930', date(2025, 10, 21), test_data)

    assert result == True, "Insertion should succeed"

    # Verify data
    query = """
    SELECT * FROM ticker_fundamentals
    WHERE ticker = '005930'
      AND date = '2025-10-21'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
    """
    rows = db.execute_query(query)

    assert len(rows) == 1, "Should have 1 record"
    assert float(rows[0]['dividend_yield']) == 3.5, "Dividend yield mismatch"
```

**File**: `tests/test_dividend_yield_factor.py`
```python
def test_calculate_dividend_yield_factor():
    """Test dividend yield factor calculation."""
    from scripts.calculate_dividend_yield import calculate_dividend_yield_factor
    from modules.db_manager_postgres import PostgresDatabaseManager

    db = PostgresDatabaseManager()

    # Test with known ticker (005930 - Samsung Electronics)
    result = calculate_dividend_yield_factor(db, '005930')

    assert result is not None, "Should return dividend yield"
    assert 0 < result < 20, "Dividend yield should be 0-20%"

def test_dividend_yield_edge_cases():
    """Test edge cases for dividend yield calculation."""
    # ... test missing data, zero prices, etc.
```

---

### 10.2 Integration Tests

**File**: `tests/test_option_b_integration.py`

```python
def test_end_to_end_dividend_yield_pipeline():
    """
    Test complete pipeline: collection → validation → calculation → scoring.
    """
    from datetime import date
    from scripts.collect_pykrx_fundamentals import fetch_pykrx_fundamentals, insert_pykrx_data
    from scripts.calculate_dividend_yield import calculate_dividend_yield_factor
    from scripts.validate_fundamentals_data import check_coverage
    from modules.db_manager_postgres import PostgresDatabaseManager

    db = PostgresDatabaseManager()
    target_date = date(2025, 10, 21)
    test_ticker = '005930'

    # Step 1: Collect pykrx data
    df = fetch_pykrx_fundamentals(target_date)
    assert test_ticker in df.index, f"Ticker {test_ticker} should be in data"

    data = df.loc[test_ticker].to_dict()
    insert_success = insert_pykrx_data(db, test_ticker, target_date, data)
    assert insert_success == True, "Data insertion should succeed"

    # Step 2: Validate coverage
    coverage = check_coverage(db, 'pykrx', 'DAILY', target_date)
    assert coverage['coverage_pct'] > 70, "Coverage should be >70%"

    # Step 3: Calculate factor
    dividend_yield = calculate_dividend_yield_factor(db, test_ticker)
    assert dividend_yield is not None, "Dividend yield should be calculated"
    assert 0 < dividend_yield < 20, "Dividend yield should be reasonable"

    # Step 4: Verify factor score saved
    query = """
    SELECT * FROM factor_scores
    WHERE ticker = %s
      AND region = 'KR'
      AND factor_name = 'Dividend_Yield'
      AND date = CURRENT_DATE
    """
    scores = db.execute_query(query, (test_ticker,))
    assert len(scores) == 1, "Factor score should be saved"
    assert 0 <= scores[0]['percentile'] <= 100, "Percentile should be 0-100"

def test_multi_source_fallback():
    """Test multi-source fallback logic."""
    # ... test pykrx → yfinance fallback
```

---

## 11. Success Metrics

### 11.1 Data Quality Metrics

**Coverage**:
- ✅ pykrx DAILY: ≥75% of OHLCV universe
- ✅ DART ANNUAL: ≥80% of active tickers (target)

**Freshness**:
- ✅ pykrx: ≤3 days stale
- ✅ DART: ≤90 days stale (quarterly cycle)

**Accuracy**:
- ✅ EBITDA calculation success: ≥80%
- ✅ Dividend coverage: ≥95%
- ✅ Anomaly rate: <5% of universe

---

### 11.2 Factor Quality Metrics

**Independence**:
- ✅ Independence rate: ≥80%
- ✅ No perfect correlations (r=1.0)
- ✅ Critical correlations: r<0.7

**Distribution**:
- ✅ Normal distribution (Shapiro-Wilk test)
- ✅ No extreme outliers (>3σ: <1%)
- ✅ Stable over time (rolling correlation >0.8)

---

### 11.3 System Performance Metrics

**Collection Speed**:
- ✅ pykrx 90-day backfill: <45 minutes
- ✅ DART 100-ticker backfill: <5 minutes

**Query Performance**:
- ✅ Single ticker lookup: <10ms
- ✅ Cross-sectional query: <100ms

**Factor Calculation**:
- ✅ Dividend Yield (2,700 tickers): <10 seconds
- ✅ EV/EBITDA (100 tickers): <5 seconds

---

## 12. Next Steps

### Immediate (Week 1)
1. ✅ Complete design document review
2. ⏳ Implement `collect_pykrx_fundamentals.py`
3. ⏳ Implement `calculate_dividend_yield.py`
4. ⏳ Write unit tests (target: 80% coverage)

### Short-term (Week 2-3)
5. ⏳ Refactor `collect_dart_fundamentals.py`
6. ⏳ Implement `calculate_ev_ebitda.py`
7. ⏳ Implement data quality validation scripts
8. ⏳ Run end-to-end integration tests

### Medium-term (Week 4-5)
9. ⏳ Backfill historical data (90 days pykrx + 3 years DART)
10. ⏳ Validate factor independence
11. ⏳ Setup automated monitoring (cron jobs)
12. ⏳ Create Grafana dashboards

### Long-term (Week 6+)
13. 📋 Add yfinance data source (optional)
14. 📋 Implement multi-source priority system
15. 📋 Integrate factors into portfolio optimizer
16. 📋 Production deployment and monitoring

---

## 13. Appendix

### 13.1 Glossary

- **period_type**: Database column distinguishing DAILY vs ANNUAL data
- **data_source**: Database column tracking data origin (pykrx, DART, yfinance, etc.)
- **EV**: Enterprise Value = Market Cap + Total Debt - Cash
- **EBITDA**: Earnings Before Interest, Taxes, Depreciation, Amortization
- **DPS**: Dividend Per Share (주당 배당금)
- **DIV**: Dividend Yield (배당수익률) - pre-calculated by pykrx

### 13.2 References

- **pykrx Documentation**: https://github.com/sharebook-kr/pykrx
- **DART Open API**: https://opendart.fss.or.kr/
- **yfinance Documentation**: https://github.com/ranaroussi/yfinance
- **PostgreSQL Partial Indexes**: https://www.postgresql.org/docs/current/indexes-partial.html
- **TimescaleDB Continuous Aggregates**: https://docs.timescale.com/timescaledb/latest/how-to-guides/continuous-aggregates/

### 13.3 Contact

- **Primary Developer**: @13ruce
- **Project Repository**: `/Users/13ruce/spock`
- **Design Review**: 2025-10-28

---

**End of Design Document**

**Status**: ✅ Design Complete | Ready for Implementation
**Next Action**: Implementation kickoff meeting → Create implementation tasks in TODO list
