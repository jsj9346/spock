# Week 5: SQLite Schema Migration Requirement

**Status**: Technical Debt - Not Blocking Week 5 Priorities
**Priority**: Medium
**Estimated Effort**: 2-3 hours for complete migration
**Date**: 2025-10-28

---

## Problem Statement

The SQLite development database schema is missing the `rsi` column in the `ohlcv_data` table, causing 3 backtest_runner tests to fail with the following error:

```
ERROR modules.layered_scoring_engine:layered_scoring_engine.py:421
❌ 000020 데이터 로드 실패: Execution failed on sql '
    SELECT date, open, high, low, close, volume,
           ma5, ma20, ma60, ma120, ma200, rsi
    FROM ohlcv_data
    WHERE ticker = ?
    ORDER BY date DESC
    LIMIT 300
    ': no such column: rsi
```

---

## Impact Analysis

### Affected Tests (3/23 failures)

1. **`test_metrics_match_dict`** (tests/backtesting/test_backtest_runner.py)
   - Purpose: Validate consistency between custom and vectorbt engines
   - Failure: Cannot load OHLCV data for ticker 000020 due to missing `rsi` column

2. **`test_validate_consistency`** (tests/backtesting/test_backtest_runner.py)
   - Purpose: Validate consistency report generation
   - Failure: Same root cause - LayeredScoringEngine cannot load data

3. **`test_empty_tickers`** (tests/backtesting/test_backtest_runner.py)
   - Purpose: Test graceful handling of empty ticker lists
   - Failure: Same root cause - data loading fails before empty ticker logic executes

### Non-Blocking Status

This issue does **NOT** block other Week 5 priorities:
- ✅ Test coverage expansion can proceed with other modules
- ✅ Orphaned ticker backfill operates on PostgreSQL (production database)
- ✅ Factor library development doesn't depend on SQLite

---

## Root Cause

### Schema Divergence

**PostgreSQL Production Schema** (Correct):
```sql
CREATE TABLE ohlcv_data (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    date DATE NOT NULL,
    open NUMERIC(15,2),
    high NUMERIC(15,2),
    low NUMERIC(15,2),
    close NUMERIC(15,2),
    volume BIGINT,
    ma5 NUMERIC(15,2),
    ma20 NUMERIC(15,2),
    ma60 NUMERIC(15,2),
    ma120 NUMERIC(15,2),
    ma200 NUMERIC(15,2),
    rsi NUMERIC(8,4),  -- ✅ RSI column exists
    UNIQUE(ticker, region, date, timeframe)
);
```

**SQLite Development Schema** (Missing RSI):
```sql
CREATE TABLE ohlcv_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    ma120 REAL,
    ma200 REAL,
    -- ❌ RSI column missing
    UNIQUE(ticker, region, date)
);
```

### Historical Context

This divergence occurred during Week 4 when:
1. PostgreSQL schema was updated to include `rsi` column
2. SQLite schema was not synchronized
3. LayeredScoringEngine was updated to query `rsi` column
4. Tests using SQLite database began failing

---

## Migration Plan

### Step 1: Schema Update (10 minutes)

**Add RSI Column**:
```sql
ALTER TABLE ohlcv_data ADD COLUMN rsi NUMERIC(8,4);
```

**Verification**:
```sql
PRAGMA table_info(ohlcv_data);
-- Should show rsi column with type REAL
```

### Step 2: Data Backfill Strategy (1-2 hours)

**Option A: Recalculate RSI** (Recommended)
- Query existing OHLCV data from SQLite
- Calculate RSI(14) using pandas-ta or ta-lib
- Update records with calculated RSI values
- Advantage: Self-contained, no PostgreSQL dependency

**Option B: Copy from PostgreSQL**
- Export RSI values from PostgreSQL for matching (ticker, region, date) tuples
- Import into SQLite via UPDATE statements
- Advantage: Guaranteed consistency with production data
- Disadvantage: Requires PostgreSQL connection

**Recommended Script**:
```python
#!/usr/bin/env python3
"""
SQLite RSI Column Backfill Script

Usage:
    python3 scripts/backfill_sqlite_rsi.py --mode recalculate
    python3 scripts/backfill_sqlite_rsi.py --mode copy-from-postgres
"""

import sqlite3
import pandas as pd
import pandas_ta as ta
from modules.db_manager_sqlite import SQLiteDatabaseManager

def backfill_rsi_recalculate(db_path: str):
    """Recalculate RSI for all records."""
    db = SQLiteDatabaseManager(db_path)

    # Get unique tickers
    query = "SELECT DISTINCT ticker, region FROM ohlcv_data ORDER BY ticker"
    tickers = db.execute_query(query)

    for row in tickers:
        ticker, region = row['ticker'], row['region']

        # Load OHLCV data
        query = """
        SELECT date, close FROM ohlcv_data
        WHERE ticker = ? AND region = ?
        ORDER BY date ASC
        """
        df = pd.DataFrame(db.execute_query(query, (ticker, region)))
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # Calculate RSI(14)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # Update records
        for date, rsi in zip(df.index, df['rsi']):
            if not pd.isna(rsi):
                update_query = """
                UPDATE ohlcv_data
                SET rsi = ?
                WHERE ticker = ? AND region = ? AND date = ?
                """
                db.execute_query(update_query, (float(rsi), ticker, region, date.strftime('%Y-%m-%d')), commit=True)

        print(f"✅ {ticker} ({region}): {len(df)} records updated")

if __name__ == '__main__':
    backfill_rsi_recalculate('data/spock_local.db')
```

### Step 3: Testing and Validation (30 minutes)

**Test Execution**:
```bash
# Run affected tests
PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
  tests/backtesting/test_backtest_runner.py::TestComparison::test_metrics_match_dict \
  tests/backtesting/test_backtest_runner.py::TestValidation::test_validate_consistency \
  tests/backtesting/test_backtest_runner.py::TestEdgeCases::test_empty_tickers \
  -v
```

**Expected Outcome**:
```
tests/backtesting/test_backtest_runner.py::TestComparison::test_metrics_match_dict PASSED
tests/backtesting/test_backtest_runner.py::TestValidation::test_validate_consistency PASSED
tests/backtesting/test_backtest_runner.py::TestEdgeCases::test_empty_tickers PASSED

========================= 3 passed in 12.3s =========================
```

**Data Quality Validation**:
```sql
-- Check RSI coverage
SELECT
    COUNT(*) as total_records,
    SUM(CASE WHEN rsi IS NULL THEN 1 ELSE 0 END) as null_rsi,
    SUM(CASE WHEN rsi IS NOT NULL THEN 1 ELSE 0 END) as valid_rsi,
    ROUND(100.0 * SUM(CASE WHEN rsi IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as coverage_pct
FROM ohlcv_data;

-- Expected result:
-- total_records: ~10,000
-- null_rsi: ~140 (first 14 days per ticker)
-- valid_rsi: ~9,860
-- coverage_pct: ~98.6%

-- Check RSI value range (should be 0-100)
SELECT
    MIN(rsi) as min_rsi,
    MAX(rsi) as max_rsi,
    AVG(rsi) as avg_rsi,
    COUNT(*) as total_with_rsi
FROM ohlcv_data
WHERE rsi IS NOT NULL;

-- Expected result:
-- min_rsi: ~0-10
-- max_rsi: ~90-100
-- avg_rsi: ~45-55 (normally distributed around 50)
```

---

## Schema Parity Strategy

To prevent future divergence between SQLite and PostgreSQL:

### 1. Single Source of Truth

**Create `schema_definitions.py`**:
```python
"""
Database Schema Definitions - Single Source of Truth

Usage:
    from modules.schema_definitions import OHLCV_COLUMNS

    # Generate PostgreSQL CREATE TABLE
    postgres_schema = generate_postgres_schema(OHLCV_COLUMNS)

    # Generate SQLite CREATE TABLE
    sqlite_schema = generate_sqlite_schema(OHLCV_COLUMNS)
"""

OHLCV_COLUMNS = [
    ('id', 'INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY'),
    ('ticker', 'TEXT NOT NULL', 'VARCHAR(20) NOT NULL'),
    ('region', 'TEXT NOT NULL', 'VARCHAR(5) NOT NULL'),
    ('date', 'DATE NOT NULL', 'DATE NOT NULL'),
    ('open', 'REAL', 'NUMERIC(15,2)'),
    ('high', 'REAL', 'NUMERIC(15,2)'),
    ('low', 'REAL', 'NUMERIC(15,2)'),
    ('close', 'REAL', 'NUMERIC(15,2)'),
    ('volume', 'INTEGER', 'BIGINT'),
    ('ma5', 'REAL', 'NUMERIC(15,2)'),
    ('ma20', 'REAL', 'NUMERIC(15,2)'),
    ('ma60', 'REAL', 'NUMERIC(15,2)'),
    ('ma120', 'REAL', 'NUMERIC(15,2)'),
    ('ma200', 'REAL', 'NUMERIC(15,2)'),
    ('rsi', 'REAL', 'NUMERIC(8,4)'),  # ✅ Defined in single location
]
```

### 2. Automated Schema Validation

**Create `validate_schema_parity.py`**:
```python
#!/usr/bin/env python3
"""
Schema Parity Validation Script

Compares SQLite and PostgreSQL schemas to detect divergence.

Usage:
    python3 scripts/validate_schema_parity.py
"""

def validate_column_parity():
    """Compare column lists between SQLite and PostgreSQL."""
    sqlite_columns = get_sqlite_columns('ohlcv_data')
    postgres_columns = get_postgres_columns('ohlcv_data')

    missing_in_sqlite = set(postgres_columns) - set(sqlite_columns)
    missing_in_postgres = set(sqlite_columns) - set(postgres_columns)

    if missing_in_sqlite:
        print(f"❌ SQLite missing columns: {missing_in_sqlite}")
    if missing_in_postgres:
        print(f"❌ PostgreSQL missing columns: {missing_in_postgres}")

    if not missing_in_sqlite and not missing_in_postgres:
        print("✅ Schema parity validated")
```

### 3. CI/CD Integration

**Add to `.github/workflows/test.yml`**:
```yaml
- name: Validate Schema Parity
  run: |
    python3 scripts/validate_schema_parity.py
    if [ $? -ne 0 ]; then
      echo "❌ Schema parity check failed"
      exit 1
    fi
```

---

## Timeline and Priority

### Current Status (Week 5 Day 1)
- ✅ Priority 1: detect_price_anomalies.py fixed and validated
- ✅ Priority 2: backtest_runner tests 83% fixed (15/18)
- ⏳ Priority 3: Test coverage expansion (next task)
- ⏳ Priority 4: Orphaned ticker backfill
- 📋 Schema migration: Documented, deferred to separate focused task

### Recommended Scheduling

**Option A: Immediate Fix (2-3 hours)**
- Pause test coverage expansion
- Run migration script
- Validate all tests pass
- Resume test coverage work

**Option B: End of Week 5 (Current Choice)**
- Complete test coverage expansion first
- Complete orphaned ticker backfill
- Address schema migration as final Week 5 task
- Advantage: Doesn't disrupt current momentum

**Option C: Week 6 Cleanup**
- Focus Week 5 on core priorities
- Include schema migration in Week 6 technical debt sprint
- Advantage: Maintains Week 5 focus on high-value tasks

---

## Success Criteria

### Migration Success
- ✅ SQLite `ohlcv_data` table has `rsi` column
- ✅ ≥98% of records have valid RSI values (0-100 range)
- ✅ All 3 affected tests pass
- ✅ Overall test pass rate: 23/23 (100%)

### Parity Maintenance
- ✅ Schema validation script implemented
- ✅ CI/CD check prevents future divergence
- ✅ Single source of truth for schema definitions

---

## References

### Related Documentation
- [WEEK4_COMPLETION_REPORT.md](WEEK4_COMPLETION_REPORT.md) - Context on PostgreSQL migration
- [WEEK4_POSTGRES_DATA_PROVIDER_DESIGN.md](WEEK4_POSTGRES_DATA_PROVIDER_DESIGN.md) - PostgreSQL schema design

### Test Files
- `/Users/13ruce/spock/tests/backtesting/test_backtest_runner.py` - Affected tests

### Database Files
- SQLite: `/Users/13ruce/spock/data/spock_local.db`
- PostgreSQL: `quant_platform` database on localhost:5432

---

**Last Updated**: 2025-10-28
**Status**: Documentation Complete - Ready for Implementation
