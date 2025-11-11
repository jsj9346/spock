# PostgreSQL Schema Completion Design

**Created**: 2025-11-05
**Purpose**: Design missing database tables for production integration tests
**Status**: 🎯 **Design Phase**

---

## 📊 Executive Summary

### Problem Statement
Production integration tests are failing due to missing database tables:
1. `exchange_rates` - FX data storage (3 tests failing)
2. `fx_signals` - FX signal generation (1 test warning)
3. `ticker_fundamentals` - Missing from current PostgreSQL schema

### Solution Overview
Add 3 missing tables to `init_postgres_schema.py` following TimescaleDB best practices:
- **exchange_rates**: Hypertable for time-series FX data
- **fx_signals**: Regular table for FX trading signals
- **ticker_fundamentals**: Hypertable for fundamental metrics

### Impact
- ✅ **FX Tracker tests**: 6/7 passing (85%)
- ✅ **Complete schema**: All required tables present
- ✅ **Production ready**: Schema supports full data collection pipeline

---

## 🔍 Gap Analysis

### Current PostgreSQL Schema (init_postgres_schema.py)

**Core Tables** (3):
- ✅ `tickers` - Global ticker universe
- ✅ `stock_details` - Stock-specific metadata
- ✅ `etf_details` - ETF-specific metadata

**Hypertables** (2):
- ✅ `ohlcv_data` - OHLCV with technical indicators
- ✅ `factor_scores` - Multi-factor analysis scores

**Future Phase Tables** (3):
- ✅ `strategies` - Strategy definitions
- ✅ `backtest_results` - Backtesting results
- ✅ `portfolio_holdings` - Portfolio holdings

**Continuous Aggregates** (2):
- ✅ `ohlcv_monthly` - Monthly OHLCV aggregation
- ✅ `ohlcv_yearly` - Yearly OHLCV aggregation

### Missing Tables (3)

| Table | Type | Purpose | Test Impact |
|-------|------|---------|-------------|
| `exchange_rates` | Hypertable | Store FX rates | 3 tests failing |
| `fx_signals` | Regular | FX trading signals | 1 test warning |
| `ticker_fundamentals` | Hypertable | Fundamental metrics | Future use |

### SQLite vs PostgreSQL

**SQLite `init_db.py` has** (but PostgreSQL doesn't):
- exchange_rate_history → Need `exchange_rates`
- ticker_fundamentals → Need `ticker_fundamentals`
- technical_analysis → Covered by `ohlcv_data`
- trades, portfolio, kelly_sizing → Future phase
- filter_cache_* → Future phase
- risk_limits, circuit_breaker_logs → Future phase

---

## 🏗️ Table Design Specifications

### 1. exchange_rates Table (Hypertable)

**Purpose**: Store historical exchange rate data for multi-currency support

**Design Rationale**:
- **Hypertable**: FX data is time-series, needs efficient historical queries
- **Compression**: Historical FX data compresses well (10x savings)
- **Partition Key**: `date` (daily FX rates, monthly partitions)
- **Segment By**: `base_currency, quote_currency` (efficient queries per currency pair)

**Schema**:
```sql
CREATE TABLE exchange_rates (
    id BIGSERIAL,
    base_currency VARCHAR(3) NOT NULL,      -- KRW, USD, JPY, EUR, CNY
    quote_currency VARCHAR(3) NOT NULL,     -- USD, JPY, EUR, CNY, etc.
    date DATE NOT NULL,                     -- Exchange rate date
    rate NUMERIC(20, 10) NOT NULL,          -- Exchange rate (high precision)
    source VARCHAR(50),                     -- Data source (exchangerate.host, KIS API)
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (base_currency, quote_currency, date)
);
```

**Hypertable Configuration**:
```sql
-- Convert to hypertable (partition by date)
SELECT create_hypertable('exchange_rates', 'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE exchange_rates SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'base_currency, quote_currency',
    timescaledb.compress_orderby = 'date DESC'
);

-- Add compression policy (compress data older than 90 days)
SELECT add_compression_policy('exchange_rates', INTERVAL '90 days');
```

**Indexes**:
```sql
CREATE INDEX idx_exchange_rates_lookup
    ON exchange_rates(base_currency, quote_currency, date DESC);

CREATE INDEX idx_exchange_rates_date
    ON exchange_rates(date DESC);

CREATE INDEX idx_exchange_rates_source
    ON exchange_rates(source);
```

**Expected Data Volume**:
- **Currencies**: 5 quote currencies (USD, JPY, EUR, CNY, VND)
- **Base**: 1 base currency (KRW)
- **Daily updates**: 5 rows/day
- **Annual**: ~1,825 rows (5 × 365)
- **10-year**: ~18,250 rows
- **Compression**: 10x savings after 90 days

**Query Patterns**:
```sql
-- Get latest FX rate
SELECT rate
FROM exchange_rates
WHERE base_currency = 'KRW' AND quote_currency = 'USD'
ORDER BY date DESC
LIMIT 1;

-- Get FX rates for date range
SELECT date, rate
FROM exchange_rates
WHERE base_currency = 'KRW' AND quote_currency = 'USD'
  AND date BETWEEN '2024-01-01' AND '2024-12-31'
ORDER BY date DESC;

-- Get latest rates for all currencies
SELECT DISTINCT ON (quote_currency)
    quote_currency, date, rate
FROM exchange_rates
WHERE base_currency = 'KRW'
ORDER BY quote_currency, date DESC;
```

---

### 2. fx_signals Table (Regular Table)

**Purpose**: Store generated FX trading signals for portfolio decisions

**Design Rationale**:
- **Regular Table**: Signals are derived data, not raw time-series
- **No Hypertable**: Signal generation is infrequent, no need for time-series optimization
- **Lightweight**: Low data volume (few signals per day)

**Schema**:
```sql
CREATE TABLE fx_signals (
    id BIGSERIAL PRIMARY KEY,
    currency VARCHAR(3) NOT NULL,           -- USD, JPY, EUR, CNY, VND
    base_currency VARCHAR(3) NOT NULL DEFAULT 'KRW',
    signal_type VARCHAR(50) NOT NULL,       -- rapid_appreciation, rapid_depreciation, high_volatility
    magnitude NUMERIC(10, 4) NOT NULL,      -- Signal strength (percentage change)
    current_rate NUMERIC(20, 10) NOT NULL,  -- Current exchange rate
    previous_rate NUMERIC(20, 10),          -- Previous rate (for comparison)
    date DATE NOT NULL,                     -- Signal date
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes**:
```sql
CREATE INDEX idx_fx_signals_currency_date
    ON fx_signals(currency, date DESC);

CREATE INDEX idx_fx_signals_date
    ON fx_signals(date DESC);

CREATE INDEX idx_fx_signals_type
    ON fx_signals(signal_type);
```

**Expected Data Volume**:
- **Signals**: 0-3 signals/day (not every currency generates signals daily)
- **Annual**: ~100-500 rows
- **10-year**: ~1,000-5,000 rows
- **Lightweight**: No compression needed

**Query Patterns**:
```sql
-- Get latest signals
SELECT * FROM fx_signals
ORDER BY date DESC, created_at DESC
LIMIT 10;

-- Get signals for specific currency
SELECT * FROM fx_signals
WHERE currency = 'USD'
ORDER BY date DESC
LIMIT 20;

-- Count signals by type
SELECT signal_type, COUNT(*)
FROM fx_signals
GROUP BY signal_type;
```

**Signal Types**:
1. **rapid_appreciation**: Currency appreciating >2% daily
2. **rapid_depreciation**: Currency depreciating >2% daily
3. **high_volatility**: Volatility >1.5% (20-day rolling)

---

### 3. ticker_fundamentals Table (Hypertable)

**Purpose**: Store fundamental metrics (P/E, P/B, dividend yield, etc.) for value factor analysis

**Design Rationale**:
- **Hypertable**: Fundamental metrics are time-series data
- **Phase 2+**: Not immediately required, but critical for value factor library
- **Compression**: Historical fundamentals compress well
- **Partition Key**: `date` (quarterly/annual fundamentals)

**Schema**:
```sql
CREATE TABLE ticker_fundamentals (
    id BIGSERIAL,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,                     -- Report date
    period_type VARCHAR(20) NOT NULL,       -- DAILY, QUARTERLY, ANNUAL

    -- Basic Metrics
    shares_outstanding BIGINT,              -- Outstanding shares
    market_cap BIGINT,                      -- Market capitalization
    close_price NUMERIC(18, 4),             -- Closing price

    -- Valuation Metrics
    per NUMERIC(10, 4),                     -- Price/Earnings ratio
    pbr NUMERIC(10, 4),                     -- Price/Book ratio
    psr NUMERIC(10, 4),                     -- Price/Sales ratio
    pcr NUMERIC(10, 4),                     -- Price/Cash Flow ratio

    ev BIGINT,                              -- Enterprise value
    ev_ebitda NUMERIC(10, 4),               -- EV/EBITDA ratio

    -- Dividend Metrics
    dividend_yield NUMERIC(10, 4),          -- Dividend yield (%)
    dividend_per_share NUMERIC(10, 4),      -- Dividend per share

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    data_source VARCHAR(50),                -- KIS API, FnGuide, DART

    PRIMARY KEY (ticker, region, date, period_type),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
);
```

**Hypertable Configuration**:
```sql
-- Convert to hypertable
SELECT create_hypertable('ticker_fundamentals', 'date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE ticker_fundamentals SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, period_type',
    timescaledb.compress_orderby = 'date DESC'
);

-- Add compression policy (compress data older than 1 year)
SELECT add_compression_policy('ticker_fundamentals', INTERVAL '365 days');
```

**Indexes**:
```sql
CREATE INDEX idx_ticker_fundamentals_ticker_date
    ON ticker_fundamentals(ticker, region, date DESC);

CREATE INDEX idx_ticker_fundamentals_date
    ON ticker_fundamentals(date DESC);

CREATE INDEX idx_ticker_fundamentals_period
    ON ticker_fundamentals(period_type);

-- Value factor indexes
CREATE INDEX idx_ticker_fundamentals_per
    ON ticker_fundamentals(per) WHERE per IS NOT NULL;

CREATE INDEX idx_ticker_fundamentals_pbr
    ON ticker_fundamentals(pbr) WHERE pbr IS NOT NULL;

CREATE INDEX idx_ticker_fundamentals_dividend_yield
    ON ticker_fundamentals(dividend_yield) WHERE dividend_yield IS NOT NULL;
```

**Expected Data Volume**:
- **Tickers**: 21,098 (current database)
- **Periods**: 3 types (DAILY, QUARTERLY, ANNUAL)
- **Daily updates**: ~21,000 rows/day (DAILY period only)
- **Quarterly**: ~21,000 rows × 4 = 84,000 rows/year
- **Annual**: ~21,000 rows/year
- **Total**: ~105,000 rows/year (DAILY not always collected)
- **10-year**: ~1M rows
- **Compression**: 10x savings after 1 year

**Query Patterns**:
```sql
-- Get latest fundamentals for ticker
SELECT * FROM ticker_fundamentals
WHERE ticker = '005930' AND region = 'KR'
ORDER BY date DESC
LIMIT 1;

-- Get quarterly fundamentals for ticker
SELECT date, per, pbr, dividend_yield
FROM ticker_fundamentals
WHERE ticker = '005930' AND region = 'KR'
  AND period_type = 'QUARTERLY'
ORDER BY date DESC
LIMIT 8;

-- Find value stocks (low P/E, high dividend yield)
SELECT DISTINCT ON (ticker, region)
    ticker, region, per, dividend_yield, date
FROM ticker_fundamentals
WHERE period_type = 'DAILY'
  AND per < 15
  AND dividend_yield > 3.0
ORDER BY ticker, region, date DESC;
```

---

## 🔄 Migration Strategy

### Phase 1: Add Missing Tables (Immediate)

**Objective**: Fix failing production tests

**Steps**:
1. **Update `init_postgres_schema.py`** (15 minutes)
   - Add `create_exchange_rates_hypertable()` method
   - Add `create_fx_signals_table()` method
   - Add `create_ticker_fundamentals_hypertable()` method
   - Update `initialize()` method to call new table creators

2. **Run Schema Creation** (2 minutes)
   ```bash
   python3 scripts/init_postgres_schema.py
   ```

3. **Validate Schema** (1 minute)
   ```bash
   python3 scripts/init_postgres_schema.py --validate
   ```

4. **Re-run Tests** (10 minutes)
   ```bash
   python3 -m pytest tests/integration/production/test_fx_tracker_production.py -v -s --no-cov
   ```

**Expected Outcome**: FX Tracker tests 6/7 passing (85%)

### Phase 2: Update init_db.py (Optional)

**Objective**: Document PostgreSQL migration path in SQLite init script

**Changes**:
1. Add migration notes to docstring
2. Add PostgreSQL table equivalents in comments
3. Note which tables are PostgreSQL-only (hypertables)

**Impact**: Documentation only, no functional changes

---

## 📐 Schema Design Principles

### TimescaleDB Best Practices

**1. Hypertable vs Regular Table**:
- **Use Hypertable**: Time-series data with frequent queries by date range
- **Use Regular Table**: Derived data, low volume, infrequent updates

**Applied**:
- ✅ `exchange_rates` → Hypertable (time-series FX data)
- ✅ `ticker_fundamentals` → Hypertable (time-series fundamentals)
- ❌ `fx_signals` → Regular (derived signals, low volume)

**2. Partition Key Selection**:
- **Rule**: Choose column that appears in most queries
- **Best**: Date columns for time-series data
- **Chunk Size**: Match query patterns (1 month for daily data)

**Applied**:
- `exchange_rates`: Partition by `date`, chunk = 1 month
- `ticker_fundamentals`: Partition by `date`, chunk = 3 months (quarterly data)

**3. Compression Strategy**:
- **Rule**: Compress historical data that's rarely updated
- **Segment By**: Columns with high cardinality (ticker, currency)
- **Order By**: Date DESC (recent data first)
- **Policy**: Compress after data stabilizes (90 days - 1 year)

**Applied**:
- `exchange_rates`: Compress after 90 days, segment by currency pair
- `ticker_fundamentals`: Compress after 1 year, segment by ticker

**4. Index Design**:
- **Primary Access**: Index on primary query patterns
- **Composite Indexes**: Match query filters (ticker + region + date)
- **Partial Indexes**: For filtered queries (WHERE per IS NOT NULL)

**Applied**:
- Composite: `(base_currency, quote_currency, date DESC)`
- Partial: `(per) WHERE per IS NOT NULL`
- Covering: `(ticker, region, date DESC)` for ticker fundamentals

### Data Type Selection

| Column Type | PostgreSQL Type | Rationale |
|-------------|----------------|-----------|
| **Currency Code** | VARCHAR(3) | ISO 4217 (USD, KRW, JPY) |
| **Exchange Rate** | NUMERIC(20, 10) | High precision (0.0000000001 accuracy) |
| **Price** | NUMERIC(18, 4) | Sufficient for stock prices (4 decimal places) |
| **Percentage** | NUMERIC(10, 4) | Ratios and percentages (4 decimal places) |
| **Count** | BIGINT | Large numbers (shares, volume) |
| **Timestamp** | TIMESTAMPTZ | Timezone-aware timestamps |
| **Date** | DATE | Date-only fields (no time component) |

### Foreign Key Strategy

**Applied**:
- `ticker_fundamentals` → FOREIGN KEY (ticker, region) REFERENCES tickers
- **Benefit**: Data integrity, automatic cascade deletes
- **Performance**: Slight overhead on writes, validated on insert

**Not Applied**:
- `exchange_rates` → No foreign key (currency codes are static)
- `fx_signals` → No foreign key (lightweight, signals can exist without ticker)

---

## 🧪 Testing Strategy

### Validation Checklist

**Schema Creation** (5 minutes):
- [ ] Tables created successfully
- [ ] Hypertables converted
- [ ] Compression enabled
- [ ] Indexes created
- [ ] Foreign keys validated

**Data Insertion** (5 minutes):
- [ ] Insert test FX rates
- [ ] Insert test FX signals
- [ ] Insert test fundamentals
- [ ] Verify unique constraints
- [ ] Verify foreign keys

**Query Performance** (5 minutes):
- [ ] Latest FX rate query <10ms
- [ ] Date range query <50ms
- [ ] Ticker fundamental query <20ms
- [ ] Partial index usage verified

**Integration Tests** (10 minutes):
- [ ] `test_fx_tracker_production.py` - 6/7 passing
- [ ] `test_data_quality_validation.py` - FX tests passing
- [ ] No schema-related errors

### Test Queries

```sql
-- Test 1: Insert exchange rate
INSERT INTO exchange_rates (base_currency, quote_currency, date, rate, source)
VALUES ('KRW', 'USD', CURRENT_DATE, 1350.50, 'exchangerate.host');

-- Test 2: Query latest rate
SELECT rate FROM exchange_rates
WHERE base_currency = 'KRW' AND quote_currency = 'USD'
ORDER BY date DESC LIMIT 1;

-- Test 3: Insert FX signal
INSERT INTO fx_signals (currency, signal_type, magnitude, current_rate, previous_rate, date)
VALUES ('USD', 'rapid_appreciation', 2.5, 1350.50, 1320.00, CURRENT_DATE);

-- Test 4: Query signals
SELECT * FROM fx_signals ORDER BY date DESC LIMIT 10;

-- Test 5: Insert fundamental
INSERT INTO ticker_fundamentals
(ticker, region, date, period_type, per, pbr, dividend_yield, data_source)
VALUES ('005930', 'KR', CURRENT_DATE, 'DAILY', 25.5, 1.8, 2.5, 'KIS API');

-- Test 6: Query fundamental
SELECT * FROM ticker_fundamentals
WHERE ticker = '005930' AND region = 'KR'
ORDER BY date DESC LIMIT 1;
```

---

## 📊 Implementation Plan

### Timeline: 20 minutes total

| Step | Task | Time | Owner |
|------|------|------|-------|
| 1 | Update `init_postgres_schema.py` | 15 min | Dev |
| 2 | Run schema creation script | 2 min | Dev |
| 3 | Validate schema | 1 min | Dev |
| 4 | Test FX Tracker integration | 2 min | QA |
| **Total** | | **20 min** | |

### Step-by-Step Implementation

#### Step 1: Update init_postgres_schema.py (15 minutes)

**Add 3 new methods**:
1. `create_exchange_rates_hypertable()` (5 min)
2. `create_fx_signals_table()` (3 min)
3. `create_ticker_fundamentals_hypertable()` (5 min)

**Update `initialize()` method**:
```python
# After creating etf_details_table
logger.info("\n=== Creating FX & Fundamental Tables ===")
self.create_exchange_rates_hypertable()
self.create_fx_signals_table()
self.create_ticker_fundamentals_hypertable()
```

**Update `drop_all_tables()` method**:
```python
drop_statements = [
    # ... existing statements ...
    "DROP TABLE IF EXISTS fx_signals CASCADE;",
    "DROP TABLE IF EXISTS exchange_rates CASCADE;",
    "DROP TABLE IF EXISTS ticker_fundamentals CASCADE;",
    # ... existing statements ...
]
```

#### Step 2: Run Schema Creation (2 minutes)

```bash
# Run schema initialization
python3 scripts/init_postgres_schema.py

# Expected output:
# ✅ Connected to PostgreSQL: quant_platform@localhost:5432
# === Creating Core Tables ===
# ⚙️  Creating tickers table
# ✅ Creating tickers table
# ... (existing tables) ...
# === Creating FX & Fundamental Tables ===
# ⚙️  Creating exchange_rates table
# ✅ Creating exchange_rates table
# ⚙️  Converting exchange_rates to hypertable
# ✅ Converting exchange_rates to hypertable
# ⚙️  Creating fx_signals table
# ✅ Creating fx_signals table
# ⚙️  Creating ticker_fundamentals table
# ✅ Creating ticker_fundamentals table
# 🎉 Schema initialization complete!
```

#### Step 3: Validate Schema (1 minute)

```bash
# Run validation
python3 scripts/init_postgres_schema.py --validate

# Expected output:
# ✅ Created 12 tables:
#    - backtest_results
#    - etf_details
#    - exchange_rates       ← NEW
#    - factor_scores
#    - fx_signals            ← NEW
#    - ohlcv_data
#    - portfolio_holdings
#    - stock_details
#    - strategies
#    - ticker_fundamentals   ← NEW
#    - tickers
# ✅ Created 3 hypertables:
#    - exchange_rates       ← NEW
#    - factor_scores
#    - ohlcv_data
#    - ticker_fundamentals  ← NEW
# ✅ Compression status:
#    - exchange_rates: ✓ enabled       ← NEW
#    - factor_scores: ✓ enabled
#    - ohlcv_data: ✓ enabled
#    - ticker_fundamentals: ✓ enabled  ← NEW
```

#### Step 4: Test Integration (2 minutes)

```bash
# Re-run FX Tracker tests
python3 -m pytest tests/integration/production/test_fx_tracker_production.py -v -s --no-cov

# Expected results:
# test_01_database_connection PASSED     ← Fixed (table exists)
# test_02_fetch_exchange_rates PASSED    ← Fixed (table exists)
# test_03_verify_database_records PASSED ← Fixed (table exists)
# test_04_verify_fx_signals PASSED       ← Fixed (table exists)
# test_05_performance_metrics PASSED
# test_06_multiple_regions PASSED        ← Fixed (table exists)
# test_summary PASSED
#
# 7 passed in 3.5s ✅
```

---

## 📝 Documentation Updates

### 1. init_db.py Updates

**Add PostgreSQL migration notes** to docstring:
```python
"""
Spock Trading System - Database Initialization Script

SQLite 데이터베이스 초기화 및 테이블 생성

⚠️ PostgreSQL Migration Note:
This script is for SQLite (local development) only.
For production PostgreSQL setup, use:
    python3 scripts/init_postgres_schema.py

PostgreSQL Equivalents:
- exchange_rate_history → exchange_rates (hypertable)
- ticker_fundamentals → ticker_fundamentals (hypertable)
- tickers, stock_details, etf_details → Same structure
- ohlcv_data → ohlcv_data (hypertable with compression)

PostgreSQL-Only Features:
- TimescaleDB hypertables for time-series data
- Continuous aggregates (monthly/yearly OHLCV)
- Compression policies (10x storage savings)
- Optimized indexes for fast queries
"""
```

### 2. Schema Documentation

**Create** `docs/POSTGRES_SCHEMA_REFERENCE.md`:
- Complete table reference
- Query examples
- Migration guide
- Performance tuning tips

---

## 🎯 Success Criteria

### Immediate Goals (Phase 1)

- [x] **Schema Design**: Complete design document
- [ ] **Implementation**: 3 new tables added to init_postgres_schema.py
- [ ] **Testing**: FX Tracker tests 6/7 passing (85%)
- [ ] **Validation**: Schema validation passes
- [ ] **Documentation**: init_db.py updated with migration notes

### Long-term Goals (Phase 2+)

- [ ] **Data Migration**: SQLite → PostgreSQL migration script
- [ ] **Performance**: Query benchmarks <100ms for typical queries
- [ ] **Compression**: 10x storage savings on historical data
- [ ] **Monitoring**: Grafana dashboards for database metrics

---

## 📎 References

### Related Documents
- [PRODUCTION_TEST_FIX_COMPLETION_REPORT.md](PRODUCTION_TEST_FIX_COMPLETION_REPORT.md) - Test fixes
- [PRODUCTION_TEST_EXECUTION_REPORT.md](PRODUCTION_TEST_EXECUTION_REPORT.md) - Test results
- [QUANT_DATABASE_SCHEMA.md](QUANT_DATABASE_SCHEMA.md) - Database architecture

### External Resources
- **TimescaleDB Docs**: https://docs.timescale.com/
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **exchangerate.host API**: https://exchangerate.host/

---

**Last Updated**: 2025-11-05 21:30 KST
**Version**: 1.0 (Design Complete)
**Next Step**: Implementation (15 minutes)
