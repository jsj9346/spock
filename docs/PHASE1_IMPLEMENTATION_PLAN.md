# Phase 1: Database Migration - Implementation Plan

**Version**: 1.0.0
**Created**: 2025-10-21
**Status**: ✅ 70% Complete → Focus on Remaining 30%
**Timeline**: 2-3 days (remaining work)

---

## Current Status Assessment

### ✅ Already Completed (70%)

#### 1. PostgreSQL + TimescaleDB Infrastructure
- ✅ PostgreSQL 15 installed and running
- ✅ TimescaleDB 2.22.1 extension enabled
- ✅ Database `quant_platform` created
- ✅ Connection pooling configured

#### 2. Schema Creation
- ✅ Core tables created (12 tables):
  - `tickers` (18,660 rows)
  - `ohlcv_data` (926,064 rows)
  - `stock_details`
  - `etf_details`
  - `etf_holdings`
  - `exchange_rate_history`
  - `global_market_indices`
  - `ticker_fundamentals`
  - `factor_scores`
  - `strategies`
  - `backtest_results`
  - `portfolio_holdings`

#### 3. TimescaleDB Hypertables
- ✅ `ohlcv_data` converted to hypertable
- ✅ `factor_scores` converted to hypertable
- ✅ Compression configured:
  - Segment by: ticker, region, timeframe
  - Order by: date DESC
  - Compression settings active

#### 4. Continuous Aggregates
- ✅ `ohlcv_monthly` - Monthly OHLCV aggregation
- ✅ `ohlcv_yearly` - Yearly OHLCV aggregation

#### 5. Indexes
- ✅ Primary keys on all tables
- ✅ Optimized indexes for common queries:
  - `idx_ohlcv_date` - Date-based queries
  - `idx_ohlcv_ticker_region` - Ticker lookup
  - `idx_ohlcv_region` - Region filtering

#### 6. Database Manager
- ✅ `modules/db_manager_postgres.py` implemented:
  - Connection pooling (ThreadedConnectionPool)
  - Bulk insert optimization (COPY command)
  - Region-aware composite keys
  - Backward-compatible with SQLite interface

#### 7. Migration Scripts
- ✅ `scripts/init_postgres_schema.py` - Schema initialization
- ✅ `scripts/migrate_from_sqlite.py` - Data migration tool
  - Batch processing with progress tracking
  - Resume capability
  - Data validation
  - Dry-run mode

#### 8. Data Migration
- ✅ Partial migration from Spock SQLite:
  - 18,660 tickers migrated
  - 926,064 OHLCV records migrated
  - Stock/ETF details migrated

---

## ⏳ Remaining Work (30%)

### Task 1: Complete Data Migration
**Priority**: High
**Estimated Time**: 4-6 hours

#### What's Missing
- Missing tables from SQLite:
  - `technical_analysis` (technical indicators)
  - `trades` (historical trades)
  - `portfolio` (portfolio positions)
  - `market_sentiment` (sentiment data)

#### Implementation Steps
1. **Verify source data availability**
   ```bash
   sqlite3 data/spock_local.db ".tables"
   sqlite3 data/spock_local.db "SELECT count(*) FROM technical_analysis;"
   ```

2. **Run full migration**
   ```bash
   # Dry run first
   python3 scripts/migrate_from_sqlite.py \
     --source data/spock_local.db \
     --dry-run

   # Full migration
   python3 scripts/migrate_from_sqlite.py \
     --source data/spock_local.db \
     --batch-size 5000
   ```

3. **Validate migration**
   ```bash
   # Compare row counts
   python3 scripts/validate_migration.py
   ```

**Acceptance Criteria**:
- ✅ 100% row count match between SQLite and PostgreSQL
- ✅ No data loss or corruption
- ✅ All foreign key relationships intact

---

### Task 2: Create Quarterly Continuous Aggregate
**Priority**: Medium
**Estimated Time**: 1 hour

#### What's Missing
- `ohlcv_quarterly` view (mentioned in design but not created)

#### Implementation SQL
```sql
-- Create quarterly continuous aggregate
CREATE MATERIALIZED VIEW ohlcv_quarterly
WITH (timescaledb.continuous) AS
SELECT ticker, region,
       time_bucket('3 months', date) AS quarter,
       first(open, date) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close, date) AS close,
       sum(volume) AS volume,
       first(ma5, date) AS ma5_start,
       last(ma20, date) AS ma20_end,
       last(rsi_14, date) AS rsi_14_end
FROM ohlcv_data
WHERE timeframe = '1d'
GROUP BY ticker, region, quarter;

-- Add refresh policy (daily refresh)
SELECT add_continuous_aggregate_policy('ohlcv_quarterly',
    start_offset => INTERVAL '1 year',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

**File**: `scripts/create_quarterly_aggregate.sql`

**Acceptance Criteria**:
- ✅ `ohlcv_quarterly` view created
- ✅ Refresh policy active
- ✅ Query performance <500ms for 5-year quarterly data

---

### Task 3: Setup Compression Policy
**Priority**: High
**Estimated Time**: 2 hours

#### What's Missing
- Compression policy not activated (compression configured but not automated)
- `factor_scores` hypertable needs compression configuration

#### Implementation Steps

**1. Check current compression status**
```sql
-- Check if any chunks are compressed
SELECT hypertable_name,
       count(*) FILTER (WHERE is_compressed = true) as compressed_chunks,
       count(*) FILTER (WHERE is_compressed = false) as uncompressed_chunks
FROM timescaledb_information.chunks
WHERE hypertable_name IN ('ohlcv_data', 'factor_scores')
GROUP BY hypertable_name;
```

**2. Enable compression policy for ohlcv_data**
```sql
-- Compress chunks older than 1 year
SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days');
```

**3. Configure compression for factor_scores**
```sql
-- Enable compression on factor_scores
ALTER TABLE factor_scores SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, factor_name',
    timescaledb.compress_orderby = 'date DESC'
);

-- Add compression policy (compress after 6 months)
SELECT add_compression_policy('factor_scores', INTERVAL '180 days');
```

**4. Manually compress old data**
```sql
-- Compress all chunks older than 1 year (ohlcv_data)
SELECT compress_chunk(i)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '365 days') i;

-- Check compression results
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) as uncompressed_size,
    pg_size_pretty(after_compression_total_bytes) as compressed_size,
    round((1 - after_compression_total_bytes::numeric / before_compression_total_bytes::numeric) * 100, 2) as compression_ratio
FROM timescaledb_information.compression_settings
WHERE hypertable_name IN ('ohlcv_data', 'factor_scores');
```

**File**: `scripts/setup_compression_policy.sql`

**Acceptance Criteria**:
- ✅ Compression policies active for both hypertables
- ✅ >70% compression ratio achieved
- ✅ Old data (>1 year) automatically compressed
- ✅ Query performance maintained (<1s for 10-year data)

---

### Task 4: Add Missing Tables for Quant Platform
**Priority**: High
**Estimated Time**: 3-4 hours

#### What's Missing
Tables needed for Quant Platform (not in Spock SQLite):

1. **`portfolio_transactions`** - Trade history for backtesting
2. **`walk_forward_results`** - Walk-forward optimization results
3. **`optimization_history`** - Portfolio optimization history

#### Implementation SQL

**1. portfolio_transactions**
```sql
CREATE TABLE portfolio_transactions (
    id BIGSERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    shares DECIMAL(15, 4) NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    commission DECIMAL(10, 4) DEFAULT 0,
    slippage DECIMAL(10, 4) DEFAULT 0,
    total_value DECIMAL(15, 4) GENERATED ALWAYS AS (shares * price + commission + slippage) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_transactions_strategy ON portfolio_transactions(strategy_id, date DESC);
CREATE INDEX idx_transactions_ticker ON portfolio_transactions(ticker, region, date DESC);
```

**2. walk_forward_results**
```sql
CREATE TABLE walk_forward_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    train_start_date DATE NOT NULL,
    train_end_date DATE NOT NULL,
    test_start_date DATE NOT NULL,
    test_end_date DATE NOT NULL,
    in_sample_sharpe DECIMAL(10, 4),
    out_sample_sharpe DECIMAL(10, 4),
    in_sample_return DECIMAL(10, 4),
    out_sample_return DECIMAL(10, 4),
    overfitting_ratio DECIMAL(10, 4),  -- out_sample_sharpe / in_sample_sharpe
    optimal_params JSONB,  -- Parameters found during training
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_walkforward_strategy ON walk_forward_results(strategy_id);
CREATE INDEX idx_walkforward_dates ON walk_forward_results(train_start_date, test_end_date);
```

**3. optimization_history**
```sql
CREATE TABLE optimization_history (
    id SERIAL PRIMARY KEY,
    optimization_date DATE NOT NULL,
    universe VARCHAR(50) NOT NULL,  -- 'KR_TOP100', 'US_SP500', etc.
    method VARCHAR(50) NOT NULL,    -- 'mean_variance', 'risk_parity', etc.
    target_return DECIMAL(10, 4),
    target_risk DECIMAL(10, 4),
    constraints JSONB,
    optimal_weights JSONB NOT NULL,  -- {ticker: weight}
    expected_return DECIMAL(10, 4),
    expected_risk DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_optimization_date ON optimization_history(optimization_date DESC);
CREATE INDEX idx_optimization_method ON optimization_history(method, optimization_date DESC);
```

**File**: `scripts/add_quant_platform_tables.sql`

**Acceptance Criteria**:
- ✅ All 3 tables created with proper constraints
- ✅ Indexes created for performance
- ✅ Foreign keys validated
- ✅ Integration tested with `db_manager_postgres.py`

---

### Task 5: Database Performance Tuning
**Priority**: Medium
**Estimated Time**: 2-3 hours

#### What's Missing
- Performance tuning and optimization
- Query plan analysis for common queries
- Connection pool optimization

#### Implementation Steps

**1. Analyze query performance**
```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top 10 slowest queries
SELECT query,
       calls,
       total_exec_time / 1000 as total_time_sec,
       mean_exec_time / 1000 as avg_time_sec,
       max_exec_time / 1000 as max_time_sec
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**2. Create missing indexes based on query patterns**
```sql
-- Example: If factor score queries are slow
CREATE INDEX idx_factor_scores_factor_date
ON factor_scores(factor_name, date DESC)
WHERE percentile IS NOT NULL;

-- Example: If backtest result lookups are slow
CREATE INDEX idx_backtest_sharpe
ON backtest_results(strategy_id, sharpe_ratio DESC);
```

**3. Update table statistics**
```sql
-- Analyze all tables for query planner
ANALYZE tickers;
ANALYZE ohlcv_data;
ANALYZE factor_scores;
ANALYZE strategies;
ANALYZE backtest_results;
ANALYZE portfolio_holdings;
```

**4. Configure connection pool settings**
```python
# Update modules/db_manager_postgres.py
# Optimize connection pool based on workload

# For read-heavy workload (backtesting, research)
pool_min_conn = 10  # Increased from 5
pool_max_conn = 30  # Increased from 20

# For write-heavy workload (data collection)
pool_min_conn = 5
pool_max_conn = 15
```

**5. Benchmark critical queries**
```bash
# Create benchmark script
python3 scripts/benchmark_queries.py
```

**File**: `scripts/performance_tuning.sql`

**Acceptance Criteria**:
- ✅ Common queries <1s (10-year OHLCV data)
- ✅ Factor score queries <500ms
- ✅ Backtest result retrieval <200ms
- ✅ Connection pool optimized (no exhaustion under load)

---

### Task 6: Data Validation and Integrity Checks
**Priority**: High
**Estimated Time**: 2-3 hours

#### What's Missing
- Comprehensive validation of migrated data
- Integrity constraint verification
- Data quality checks

#### Implementation Steps

**1. Create validation script**
```python
# scripts/validate_phase1_completion.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
import pandas as pd

def validate_row_counts():
    """Compare row counts between SQLite and PostgreSQL"""
    sqlite_db = SQLiteDatabaseManager('data/spock_local.db')
    postgres_db = PostgresDatabaseManager()

    tables = ['tickers', 'ohlcv_data', 'stock_details', 'etf_details',
              'technical_analysis', 'ticker_fundamentals']

    results = []
    for table in tables:
        sqlite_count = sqlite_db.execute_query(f"SELECT COUNT(*) as count FROM {table}")[0]['count']
        postgres_count = postgres_db.execute_query(f"SELECT COUNT(*) as count FROM {table}")[0]['count']

        match = sqlite_count == postgres_count
        results.append({
            'table': table,
            'sqlite_count': sqlite_count,
            'postgres_count': postgres_count,
            'match': '✅' if match else '❌'
        })

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    return all(r['match'] == '✅' for r in results)

def validate_data_integrity():
    """Check for data quality issues"""
    postgres_db = PostgresDatabaseManager()

    checks = []

    # Check 1: No NULL values in critical columns
    null_check = postgres_db.execute_query("""
        SELECT
            COUNT(*) FILTER (WHERE close IS NULL) as null_close,
            COUNT(*) FILTER (WHERE volume IS NULL) as null_volume
        FROM ohlcv_data
    """)[0]

    checks.append({
        'check': 'No NULL prices/volumes',
        'passed': null_check['null_close'] == 0 and null_check['null_volume'] == 0
    })

    # Check 2: Date ranges valid
    date_check = postgres_db.execute_query("""
        SELECT
            MIN(date) as min_date,
            MAX(date) as max_date,
            COUNT(DISTINCT date) as unique_dates
        FROM ohlcv_data
    """)[0]

    checks.append({
        'check': 'Valid date range',
        'passed': date_check['min_date'] is not None and date_check['max_date'] is not None
    })

    # Check 3: No duplicate primary keys
    dup_check = postgres_db.execute_query("""
        SELECT COUNT(*) as dup_count
        FROM (
            SELECT ticker, region, date, timeframe, COUNT(*) as cnt
            FROM ohlcv_data
            GROUP BY ticker, region, date, timeframe
            HAVING COUNT(*) > 1
        ) dups
    """)[0]

    checks.append({
        'check': 'No duplicate OHLCV records',
        'passed': dup_check['dup_count'] == 0
    })

    # Print results
    for check in checks:
        status = '✅' if check['passed'] else '❌'
        print(f"{status} {check['check']}")

    return all(c['passed'] for c in checks)

def validate_performance():
    """Benchmark query performance"""
    postgres_db = PostgresDatabaseManager()

    import time

    # Test 1: 10-year OHLCV query
    start = time.time()
    result = postgres_db.execute_query("""
        SELECT * FROM ohlcv_data
        WHERE ticker = '005930' AND region = 'KR'
        AND date >= CURRENT_DATE - INTERVAL '10 years'
        ORDER BY date DESC
    """)
    duration_10y = time.time() - start

    # Test 2: Factor score query
    start = time.time()
    result = postgres_db.execute_query("""
        SELECT * FROM factor_scores
        WHERE factor_name = 'momentum'
        AND date >= CURRENT_DATE - INTERVAL '1 year'
    """)
    duration_factor = time.time() - start

    # Test 3: Continuous aggregate query
    start = time.time()
    result = postgres_db.execute_query("""
        SELECT * FROM ohlcv_monthly
        WHERE ticker = '005930' AND region = 'KR'
    """)
    duration_monthly = time.time() - start

    print(f"\nPerformance Benchmarks:")
    print(f"  10-year OHLCV query: {duration_10y:.3f}s (target: <1s)")
    print(f"  Factor score query: {duration_factor:.3f}s (target: <0.5s)")
    print(f"  Monthly aggregate: {duration_monthly:.3f}s (target: <0.2s)")

    return (duration_10y < 1.0 and
            duration_factor < 0.5 and
            duration_monthly < 0.2)

if __name__ == '__main__':
    print("=" * 60)
    print("Phase 1 Validation Report")
    print("=" * 60)

    print("\n1. Row Count Validation")
    print("-" * 60)
    row_count_ok = validate_row_counts()

    print("\n2. Data Integrity Validation")
    print("-" * 60)
    integrity_ok = validate_data_integrity()

    print("\n3. Performance Validation")
    print("-" * 60)
    performance_ok = validate_performance()

    print("\n" + "=" * 60)
    if row_count_ok and integrity_ok and performance_ok:
        print("✅ Phase 1 VALIDATION PASSED")
    else:
        print("❌ Phase 1 VALIDATION FAILED")
        sys.exit(1)
```

**File**: `scripts/validate_phase1_completion.py`

**Acceptance Criteria**:
- ✅ 100% row count match
- ✅ No data integrity violations
- ✅ All performance targets met

---

### Task 7: Documentation Updates
**Priority**: Medium
**Estimated Time**: 1-2 hours

#### What's Missing
- Database schema diagram
- Migration runbook
- Performance tuning guide

#### Deliverables

**1. Database Schema Diagram**
```markdown
# docs/DATABASE_SCHEMA_DIAGRAM.md

[Include visual diagram of tables, relationships, indexes]
```

**2. Migration Runbook**
```markdown
# docs/MIGRATION_RUNBOOK.md

Step-by-step guide for:
- Fresh installation
- Incremental migration
- Rollback procedures
- Troubleshooting common issues
```

**3. Performance Tuning Guide**
```markdown
# docs/PERFORMANCE_TUNING_GUIDE.md

Guidelines for:
- Index optimization
- Query optimization
- Connection pool tuning
- Compression management
```

**Acceptance Criteria**:
- ✅ All documentation complete
- ✅ Runbook tested with fresh install
- ✅ Diagrams accurate and up-to-date

---

## Implementation Timeline

### Day 1 (4-6 hours)
- **Morning**: Task 1 (Complete Data Migration) - 3 hours
- **Afternoon**: Task 2 (Quarterly Aggregate) + Task 3 (Compression Policy) - 3 hours

### Day 2 (4-6 hours)
- **Morning**: Task 4 (Add Missing Tables) - 4 hours
- **Afternoon**: Task 5 (Performance Tuning) - 2 hours

### Day 3 (3-4 hours)
- **Morning**: Task 6 (Validation) - 2 hours
- **Afternoon**: Task 7 (Documentation) - 2 hours

**Total Estimated Time**: 11-16 hours (2-3 days)

---

## Acceptance Criteria (Phase 1 Complete)

### Infrastructure
- ✅ PostgreSQL 15+ + TimescaleDB 2.11+ installed
- ✅ Database `quant_platform` operational
- ✅ Connection pooling configured (10-30 connections)

### Schema
- ✅ All 15 tables created with proper constraints
- ✅ Hypertables: `ohlcv_data`, `factor_scores`
- ✅ Continuous aggregates: `ohlcv_monthly`, `ohlcv_quarterly`, `ohlcv_yearly`
- ✅ Compression enabled on hypertables (>70% ratio)

### Data
- ✅ 100% data migrated from Spock SQLite
- ✅ No data loss or corruption
- ✅ All foreign key relationships intact
- ✅ Data validation passed

### Performance
- ✅ 10-year OHLCV query <1s
- ✅ Factor score query <500ms
- ✅ Continuous aggregate query <200ms
- ✅ No connection pool exhaustion under load

### Documentation
- ✅ Database schema diagram
- ✅ Migration runbook
- ✅ Performance tuning guide
- ✅ Validation report

---

## Quick Start Commands

### Run Migration
```bash
# Full migration with validation
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db

# Validate migration
python3 scripts/validate_phase1_completion.py
```

### Setup Compression
```bash
# Run compression setup
psql -d quant_platform -f scripts/setup_compression_policy.sql

# Check compression status
psql -d quant_platform -c "
SELECT
    hypertable_name,
    count(*) FILTER (WHERE is_compressed = true) as compressed_chunks,
    count(*) as total_chunks
FROM timescaledb_information.chunks
GROUP BY hypertable_name;
"
```

### Create Quarterly Aggregate
```bash
psql -d quant_platform -f scripts/create_quarterly_aggregate.sql
```

### Add Quant Platform Tables
```bash
psql -d quant_platform -f scripts/add_quant_platform_tables.sql
```

### Performance Tuning
```bash
psql -d quant_platform -f scripts/performance_tuning.sql
python3 scripts/benchmark_queries.py
```

---

## Troubleshooting

### Issue: Migration Fails
```bash
# Check SQLite source
sqlite3 data/spock_local.db ".schema"

# Run dry-run first
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --dry-run

# Check PostgreSQL logs
tail -f /opt/homebrew/var/log/postgresql@17.log
```

### Issue: Compression Not Working
```bash
# Check if compression policy exists
SELECT * FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

# Manually compress old chunks
SELECT compress_chunk(i)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '365 days') i;
```

### Issue: Slow Queries
```bash
# Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries >1s
SELECT pg_reload_conf();

# Analyze query plan
EXPLAIN ANALYZE
SELECT * FROM ohlcv_data
WHERE ticker = '005930' AND date >= '2020-01-01';
```

---

## Next Steps After Phase 1

Once Phase 1 is complete (100%), proceed to:

**Phase 2: Factor Library (Week 2-3)**
- Implement value factors (P/E, P/B, dividend yield)
- Implement momentum factors (12-month, RSI)
- Implement quality factors (ROE, debt/equity)
- Implement low-volatility factors
- Implement size factors
- Factor combination framework

**Prerequisites from Phase 1**:
- ✅ `factor_scores` table ready
- ✅ `ticker_fundamentals` table populated
- ✅ `ohlcv_data` with technical indicators
- ✅ Database performance optimized

---

**Document Status**: Ready for Implementation
**Estimated Completion**: 2-3 days from start
**Current Progress**: 70% → Target: 100%
