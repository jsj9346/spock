# Phase 1: Database Migration Design
## SQLite → PostgreSQL + TimescaleDB Migration Plan

**Status**: Design Phase
**Priority**: P0 - Critical
**Estimated Duration**: 1 week (5 working days)
**Target Completion**: Week 1 of Quant Platform Development

---

## Executive Summary

This document outlines the migration strategy from **SQLite (Spock Trading System)** to **PostgreSQL + TimescaleDB (Quant Investment Platform)**.

**Key Changes**:
- **Data Retention**: 250 days → Unlimited (years of historical data)
- **Database Engine**: SQLite → PostgreSQL 15+ with TimescaleDB 2.11+
- **Storage Strategy**: Simple file-based → Hypertables with compression
- **Query Performance**: <1s for 10-year OHLCV data queries
- **Aggregation**: Manual queries → Continuous aggregates (monthly/yearly)

**Success Criteria**:
- ✅ Zero data loss during migration
- ✅ Backward compatibility with existing Spock modules (70% reuse)
- ✅ <1 second query time for 10-year OHLCV data
- ✅ 10x storage savings with TimescaleDB compression
- ✅ Seamless integration with Factor Library (Phase 2)

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [Target State Architecture](#2-target-state-architecture)
3. [Schema Design](#3-schema-design)
4. [Migration Strategy](#4-migration-strategy)
5. [Implementation Plan](#5-implementation-plan)
6. [Risk Assessment](#6-risk-assessment)
7. [Testing Strategy](#7-testing-strategy)
8. [Rollback Plan](#8-rollback-plan)

---

## 1. Current State Analysis

### 1.1 Existing SQLite Schema (Spock)

**Database**: `data/spock_local.db` (SQLite 3)

**Core Tables** (35 total):
```
tickers (Primary Key: ticker)
├── stock_details (FK: ticker)
├── etf_details (FK: ticker)
├── ohlcv_data (ticker, date, timeframe)
├── technical_analysis (ticker, date)
├── ticker_fundamentals (ticker, report_date)
└── filter_cache_* (stage0, stage1, stage2)

Transactional:
├── trades
├── portfolio
├── kelly_analysis
└── gpt_analysis

Reference Data:
├── global_market_indices
├── exchange_rate_history
└── market_sentiment
```

**Key Constraints**:
- **250-day retention**: Automatic cleanup for OHLCV data
- **No partitioning**: Single table for all regions/tickers
- **Limited concurrency**: SQLite write bottleneck
- **No continuous aggregates**: Manual monthly/yearly calculations

### 1.2 Data Volume (Current)

| Table | Row Count (Est.) | Storage | Retention |
|-------|------------------|---------|-----------|
| tickers | ~10,000 | 5 MB | Unlimited |
| stock_details | ~8,000 | 3 MB | Unlimited |
| etf_details | ~2,000 | 2 MB | Unlimited |
| ohlcv_data | ~2,500,000 | 500 MB | 250 days |
| technical_analysis | ~2,500,000 | 300 MB | 250 days |
| ticker_fundamentals | ~50,000 | 10 MB | Unlimited |
| **Total** | **~5M rows** | **~820 MB** | - |

**Projected Growth (Quant Platform)**:
- **Unlimited OHLCV retention**: 250 days → 10 years
- **Expected volume**: 2.5M rows → **100M rows** (40x growth)
- **Storage without compression**: 500 MB → **20 GB**
- **Storage with TimescaleDB compression**: **~2 GB** (10x savings)

---

## 2. Target State Architecture

### 2.1 PostgreSQL + TimescaleDB Stack

**Database Server**: PostgreSQL 15.5+
**Extension**: TimescaleDB 2.11+
**Connection Pooler**: pgBouncer (optional, for production)
**Backup Strategy**: pg_dump + WAL archiving

**Why PostgreSQL + TimescaleDB?**
1. **Hypertables**: Automatic partitioning by time (date column)
2. **Compression**: 10x storage savings for historical data
3. **Continuous Aggregates**: Materialized views for monthly/yearly data
4. **ACID Compliance**: Transaction safety for portfolio operations
5. **Concurrency**: 100+ concurrent connections
6. **Advanced Indexing**: BRIN, GIN, GiST for time-series queries

### 2.2 Connection Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Quant Platform Applications                │
│  Factor Library | Backtesting | Optimization | Dashboard    │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│              PostgresDatabaseManager                         │
│  - Connection pooling (psycopg2.pool)                       │
│  - Automatic reconnection                                    │
│  - Query logging & monitoring                                │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                PostgreSQL 15 + TimescaleDB 2.11              │
│  Database: quant_platform                                    │
│  Port: 5432 (default)                                        │
│  SSL: Required in production                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Schema Design

### 3.1 Core Tables (PostgreSQL)

#### 3.1.1 `tickers` Table

```sql
-- Master ticker table (all regions)
CREATE TABLE tickers (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,  -- KR, US, CN, HK, JP, VN

    -- Basic Information
    name TEXT NOT NULL,
    name_eng TEXT,
    exchange VARCHAR(20) NOT NULL,  -- KOSPI, NYSE, NASDAQ, etc.
    currency VARCHAR(3) NOT NULL DEFAULT 'KRW',
    asset_type VARCHAR(20) NOT NULL DEFAULT 'STOCK',  -- STOCK, ETF

    -- Dates
    listing_date DATE,
    delisting_date DATE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    lot_size INTEGER DEFAULT 1,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    data_source VARCHAR(50),

    PRIMARY KEY (ticker, region)
);

-- Indexes
CREATE INDEX idx_tickers_region ON tickers(region);
CREATE INDEX idx_tickers_exchange ON tickers(exchange);
CREATE INDEX idx_tickers_is_active ON tickers(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_tickers_asset_type ON tickers(asset_type);

-- Comments
COMMENT ON TABLE tickers IS 'Global ticker universe for all supported regions';
COMMENT ON COLUMN tickers.region IS 'ISO 3166-1 alpha-2 country code';
```

**Migration Notes**:
- SQLite Primary Key: `ticker` (single column)
- PostgreSQL Primary Key: `(ticker, region)` (composite)
- **Reason**: Support global tickers (e.g., AAPL in US, AAPL in HK)

---

#### 3.1.2 `ohlcv_data` Table (Hypertable)

```sql
-- Hypertable for OHLCV data (time-series optimized)
CREATE TABLE ohlcv_data (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT '1d',  -- 1d, 1w, 1m

    -- OHLCV
    open NUMERIC(18, 4),
    high NUMERIC(18, 4),
    low NUMERIC(18, 4),
    close NUMERIC(18, 4),
    volume BIGINT,

    -- Technical Indicators (from basic_scoring_modules.py)
    ma5 NUMERIC(18, 4),
    ma20 NUMERIC(18, 4),
    ma60 NUMERIC(18, 4),
    ma120 NUMERIC(18, 4),
    ma200 NUMERIC(18, 4),

    rsi_14 NUMERIC(8, 4),

    macd NUMERIC(18, 4),
    macd_signal NUMERIC(18, 4),
    macd_hist NUMERIC(18, 4),

    bb_upper NUMERIC(18, 4),
    bb_middle NUMERIC(18, 4),
    bb_lower NUMERIC(18, 4),

    atr_14 NUMERIC(18, 4),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker, region, date, timeframe)
);

-- Convert to hypertable (partition by date)
SELECT create_hypertable('ohlcv_data', 'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_ohlcv_ticker_region ON ohlcv_data(ticker, region, date DESC);
CREATE INDEX idx_ohlcv_date ON ohlcv_data(date DESC);
CREATE INDEX idx_ohlcv_region ON ohlcv_data(region, date DESC);

-- Enable compression (10x space savings)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, timeframe',
    timescaledb.compress_orderby = 'date DESC'
);

-- Automatic compression policy (compress data older than 1 year)
SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days');

-- Comments
COMMENT ON TABLE ohlcv_data IS 'Daily/weekly/monthly OHLCV data with technical indicators';
```

**Migration Notes**:
- SQLite: `UNIQUE(ticker, timeframe, date)` → PostgreSQL: `PRIMARY KEY (ticker, region, date, timeframe)`
- **Hypertable Partitioning**: Automatic monthly chunks for time-series optimization
- **Compression**: Reduces 10-year data from 20GB → 2GB

---

#### 3.1.3 Continuous Aggregates (Monthly/Yearly)

```sql
-- Monthly OHLCV aggregate (materialized view)
CREATE MATERIALIZED VIEW ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    region,
    timeframe,
    time_bucket('1 month', date) AS month,

    -- OHLCV aggregation
    FIRST(open, date) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, date) AS close,
    SUM(volume) AS volume,

    -- Count
    COUNT(*) AS trading_days
FROM ohlcv_data
GROUP BY ticker, region, timeframe, month;

-- Refresh policy (update every night)
SELECT add_continuous_aggregate_policy('ohlcv_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);

-- Yearly OHLCV aggregate
CREATE MATERIALIZED VIEW ohlcv_yearly
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    region,
    timeframe,
    time_bucket('1 year', date) AS year,

    FIRST(open, date) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, date) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS trading_days
FROM ohlcv_data
GROUP BY ticker, region, timeframe, year;

SELECT add_continuous_aggregate_policy('ohlcv_yearly',
    start_offset => INTERVAL '2 years',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day'
);

-- Comments
COMMENT ON MATERIALIZED VIEW ohlcv_monthly IS 'Pre-aggregated monthly OHLCV data for fast queries';
COMMENT ON MATERIALIZED VIEW ohlcv_yearly IS 'Pre-aggregated yearly OHLCV data for long-term analysis';
```

**Benefits**:
- **Query Speed**: Monthly data queries: 10ms (vs 500ms for manual aggregation)
- **Automatic Refresh**: Daily updates via TimescaleDB policy
- **Storage Efficiency**: Only stores aggregated results

---

#### 3.1.4 `factor_scores` Table (New for Phase 2)

```sql
-- Factor scores for multi-factor analysis
CREATE TABLE factor_scores (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,

    -- Factor names (value, momentum, quality, low_vol, size)
    factor_name VARCHAR(50) NOT NULL,

    -- Raw score and percentile rank (0-100)
    score NUMERIC(10, 4),
    percentile NUMERIC(5, 2),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (ticker, region, date, factor_name)
);

-- Convert to hypertable
SELECT create_hypertable('factor_scores', 'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_factor_scores_date ON factor_scores(date DESC);
CREATE INDEX idx_factor_scores_ticker ON factor_scores(ticker, region, date DESC);
CREATE INDEX idx_factor_scores_factor ON factor_scores(factor_name, date DESC);

-- Compression
ALTER TABLE factor_scores SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, factor_name',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('factor_scores', INTERVAL '180 days');

-- Comments
COMMENT ON TABLE factor_scores IS 'Daily factor scores for multi-factor analysis (Phase 2)';
```

---

### 3.2 Additional Tables (Direct Migration)

**Tables to migrate 1:1 from SQLite**:
- `stock_details` → PostgreSQL (add `region` to composite key)
- `etf_details` → PostgreSQL (add `region` to composite key)
- `ticker_fundamentals` → Hypertable (partition by `report_date`)
- `global_market_indices` → Hypertable (partition by `date`)
- `exchange_rate_history` → Hypertable (partition by `date`)

**Tables to deprecate** (Spock-specific):
- `trades` → Keep for historical analysis only (no new inserts)
- `portfolio` → Keep for historical analysis only
- `filter_cache_*` → Rebuild in PostgreSQL with new structure

---

## 4. Migration Strategy

### 4.1 Migration Approach

**Strategy**: **Parallel Migration** (Zero Downtime)

```
Phase 1A: Setup PostgreSQL + TimescaleDB
├── Install PostgreSQL 15.5
├── Install TimescaleDB 2.11 extension
├── Create database 'quant_platform'
└── Initialize schema

Phase 1B: Implement PostgresDatabaseManager
├── modules/db_manager_postgres.py
├── Connection pooling (psycopg2.pool)
└── Query interface compatible with SQLiteDatabaseManager

Phase 1C: Data Migration
├── scripts/migrate_from_sqlite.py
├── Migrate tickers (10K rows)
├── Migrate stock_details/etf_details (10K rows)
├── Migrate ohlcv_data (2.5M rows → PostgreSQL)
├── Migrate ticker_fundamentals (50K rows)
└── Migrate reference data (indices, exchange rates)

Phase 1D: Validation
├── Row count verification
├── Data integrity checks (foreign keys)
├── Query performance benchmarks
└── Continuous aggregate verification

Phase 1E: Switchover
├── Update modules to use PostgresDatabaseManager
├── Parallel operation (SQLite + PostgreSQL) for 1 week
└── Deprecate SQLite (archive for backup)
```

### 4.2 Migration Tools

**Primary Tool**: `scripts/migrate_from_sqlite.py`

```python
# Key Features:
- Batch migration (1000 rows per batch)
- Progress tracking (tqdm)
- Automatic retry on failure
- Data validation after migration
- Rollback capability
```

**Dependencies**:
```python
psycopg2==2.9.7
pandas==2.0.3
tqdm==4.67.1
```

---

## 5. Implementation Plan

### 5.1 Day-by-Day Breakdown

#### **Day 1: Environment Setup**
```yaml
Tasks:
  - Install PostgreSQL 15.5 (Homebrew on macOS, apt on Ubuntu)
  - Install TimescaleDB 2.11 extension
  - Create database 'quant_platform'
  - Configure postgresql.conf (shared_buffers, work_mem)
  - Setup connection (psycopg2)

Deliverables:
  - PostgreSQL running on localhost:5432
  - TimescaleDB extension enabled
  - docs/POSTGRES_SETUP_GUIDE.md

Success Criteria:
  - ✅ psql -U postgres -d quant_platform -c "SELECT version();"
  - ✅ psql -U postgres -d quant_platform -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';"
```

#### **Day 2: Schema Implementation**
```yaml
Tasks:
  - Create scripts/init_postgres_schema.py
  - Implement all table definitions (tickers, ohlcv_data, etc.)
  - Create hypertables (ohlcv_data, factor_scores, ticker_fundamentals)
  - Setup compression policies
  - Create continuous aggregates (ohlcv_monthly, ohlcv_yearly)

Deliverables:
  - scripts/init_postgres_schema.py (executable)
  - docs/DATABASE_SCHEMA.md (complete schema documentation)

Success Criteria:
  - ✅ All 15 core tables created
  - ✅ Hypertables configured (3 tables)
  - ✅ Continuous aggregates active (2 views)
  - ✅ Compression policies enabled
```

#### **Day 3: Database Manager Implementation**
```yaml
Tasks:
  - Implement modules/db_manager_postgres.py
  - Connection pooling (psycopg2.pool.ThreadedConnectionPool)
  - CRUD methods (compatible with SQLiteDatabaseManager interface)
  - Bulk insert optimization (COPY command)
  - Query builder for hypertable-specific queries

Deliverables:
  - modules/db_manager_postgres.py
  - tests/test_db_manager_postgres.py

Success Criteria:
  - ✅ Connection pool working (min 5, max 20 connections)
  - ✅ Bulk insert 10K rows <1 second
  - ✅ All CRUD operations tested
  - ✅ 100% backward compatibility with SQLiteDatabaseManager interface
```

#### **Day 4: Migration Script**
```yaml
Tasks:
  - Implement scripts/migrate_from_sqlite.py
  - Migrate tickers table (10K rows)
  - Migrate stock_details, etf_details (10K rows)
  - Migrate ohlcv_data (2.5M rows, batch size 1000)
  - Migrate ticker_fundamentals (50K rows)
  - Migrate reference data (indices, exchange rates)

Deliverables:
  - scripts/migrate_from_sqlite.py
  - Migration log (CSV with row counts)

Success Criteria:
  - ✅ Zero data loss (row count match)
  - ✅ Foreign key integrity maintained
  - ✅ Migration time <30 minutes
  - ✅ Automatic rollback on error
```

#### **Day 5: Testing & Validation**
```yaml
Tasks:
  - Run data integrity checks (row counts, NULL checks)
  - Query performance benchmarks
  - Continuous aggregate verification
  - Compression verification (storage savings)
  - Integration testing with existing modules

Deliverables:
  - tests/test_migration_integrity.py
  - docs/MIGRATION_VALIDATION_REPORT.md
  - Performance benchmark report

Success Criteria:
  - ✅ 100% row count match (SQLite vs PostgreSQL)
  - ✅ <1 second query time for 10-year OHLCV data
  - ✅ 10x compression achieved (20GB → 2GB)
  - ✅ All existing tests pass with PostgreSQL
```

---

## 6. Risk Assessment

### 6.1 Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data loss during migration | Low | Critical | Batch migration with transaction rollback + backup |
| Query performance degradation | Medium | High | Hypertable indexing + continuous aggregates |
| Foreign key violations | Low | High | Validate FK integrity before migration |
| TimescaleDB version incompatibility | Low | Medium | Use stable version (2.11+) |
| Disk space exhaustion | Medium | High | Monitor storage, enable compression early |
| Connection pool exhaustion | Medium | Medium | Configure max_connections, use pgBouncer |

### 6.2 Mitigation Strategies

**Data Integrity**:
- SQLite backup before migration (`cp data/spock_local.db data/spock_local_backup_YYYYMMDD.db`)
- Transaction-based migration (COMMIT only after full batch success)
- Post-migration validation (row counts, checksums)

**Performance**:
- Hypertable chunk size tuning (1 month per chunk)
- BRIN indexes on date columns
- Continuous aggregates for common queries

**Monitoring**:
- Migration progress tracking (tqdm)
- PostgreSQL slow query log
- TimescaleDB chunk statistics

---

## 7. Testing Strategy

### 7.1 Unit Tests

**Coverage**: 100% for `db_manager_postgres.py`

```python
# tests/test_db_manager_postgres.py
class TestPostgresDatabaseManager:
    def test_connection_pooling(self):
        """Test connection pool creation and recycling"""
        pass

    def test_bulk_insert_performance(self):
        """Bulk insert 10K rows <1 second"""
        pass

    def test_hypertable_queries(self):
        """Test time-series queries on hypertables"""
        pass

    def test_continuous_aggregate_accuracy(self):
        """Verify monthly/yearly aggregates match manual calculations"""
        pass

    def test_compression_effectiveness(self):
        """Verify 10x compression achieved"""
        pass
```

### 7.2 Integration Tests

**Coverage**: End-to-end data flow

```python
# tests/test_migration_e2e.py
class TestMigrationE2E:
    def test_full_migration(self):
        """Migrate all tables from SQLite → PostgreSQL"""
        pass

    def test_data_integrity(self):
        """Verify row counts, foreign keys, NULL constraints"""
        pass

    def test_backward_compatibility(self):
        """Test existing modules with PostgreSQL backend"""
        pass
```

### 7.3 Performance Benchmarks

**Target Metrics**:
- 10-year OHLCV query: <1 second
- Bulk insert (10K rows): <1 second
- Monthly aggregate query: <10ms
- Compression ratio: >10x

---

## 8. Rollback Plan

### 8.1 Rollback Triggers

**Automatic Rollback** (during migration):
- Data integrity failure (row count mismatch)
- Foreign key violation
- Disk space exhaustion

**Manual Rollback** (post-migration):
- Query performance <50% of target
- Continuous aggregate failure
- Application errors with PostgreSQL backend

### 8.2 Rollback Procedure

```bash
# Step 1: Stop PostgreSQL writes
python scripts/freeze_postgres_writes.py

# Step 2: Restore SQLite backup
cp data/spock_local_backup_YYYYMMDD.db data/spock_local.db

# Step 3: Revert modules to SQLiteDatabaseManager
git checkout modules/db_manager_sqlite.py

# Step 4: Restart application
python spock.py --mode manual --region KR
```

**Recovery Time Objective (RTO)**: <30 minutes

---

## 9. Success Metrics

### 9.1 Migration Success Criteria

- ✅ **Zero data loss**: Row counts match (SQLite vs PostgreSQL)
- ✅ **Performance targets met**:
  - 10-year OHLCV query: <1 second
  - Bulk insert 10K rows: <1 second
  - Monthly aggregate query: <10ms
- ✅ **Storage efficiency**: 10x compression (20GB → 2GB)
- ✅ **Backward compatibility**: All existing modules work without modification
- ✅ **Continuous aggregates**: Monthly/yearly views update automatically

### 9.2 Post-Migration Monitoring

**Metrics to Track** (Prometheus + Grafana):
- Query latency (p50, p95, p99)
- Connection pool usage
- Disk space (with compression)
- Continuous aggregate lag
- Error rate (PostgreSQL logs)

---

## 10. Next Steps (Phase 2 Integration)

Upon successful completion of Phase 1:
1. **Factor Library Integration**: `factor_scores` table ready for Phase 2
2. **Backtesting Data Access**: Unlimited historical data for backtesting
3. **Portfolio Optimization**: Efficient multi-ticker queries
4. **Dashboard**: Real-time queries with continuous aggregates

**Phase 2 Preparation**:
- `factor_scores` hypertable already created
- Compression policies configured
- Query interface compatible with Factor Library

---

## Appendix A: Installation Commands

### macOS (Homebrew)
```bash
# Install PostgreSQL
brew install postgresql@15

# Install TimescaleDB
brew tap timescale/tap
brew install timescaledb

# Configure TimescaleDB
timescaledb-tune --quiet --yes

# Start PostgreSQL
brew services start postgresql@15

# Create database
createdb quant_platform

# Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Ubuntu/Debian
```bash
# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Install PostgreSQL
sudo apt update
sudo apt install postgresql-15

# Add TimescaleDB repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Install TimescaleDB
sudo apt update
sudo apt install timescaledb-2-postgresql-15

# Configure TimescaleDB
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql

# Create database
sudo -u postgres createdb quant_platform

# Enable TimescaleDB extension
sudo -u postgres psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

---

## Appendix B: Configuration Files

### postgresql.conf (Recommended Settings)
```ini
# Memory Configuration
shared_buffers = 2GB          # 25% of system RAM
effective_cache_size = 6GB    # 75% of system RAM
work_mem = 16MB
maintenance_work_mem = 512MB

# TimescaleDB Settings
timescaledb.max_background_workers = 8
max_worker_processes = 13
shared_preload_libraries = 'timescaledb'

# Connection Settings
max_connections = 100
```

### .env (Connection String)
```ini
# PostgreSQL Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quant_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your-password>

# Legacy SQLite (for migration)
SQLITE_DB_PATH=data/spock_local.db
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Author**: Quant Platform Development Team
