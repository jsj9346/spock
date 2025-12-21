# Week 5 Integration Test Plan - Task Orchestration

**Date**: 2025-10-30
**Phase**: Phase 0 Completion (Integration Tests)
**Duration**: 8-10 hours (2-3 days)
**Dependencies**: Phase 0.3 Complete (7.65% coverage, 90 factor tests)

---

## Executive Summary

Week 5 focuses on integration testing to complete Phase 0 test coverage expansion. This orchestrated plan addresses deferred database-dependent tests, backfills missing test data, and establishes realistic coverage targets for production readiness.

### Goals
1. ✅ Create PostgreSQL mock infrastructure for value factor tests
2. ✅ Backfill ticker 000020 Q1 2024 test data (OHLCV + fundamentals)
3. ✅ Implement value factor integration tests (15-20 tests)
4. ✅ Fix 6 environment-dependent walk-forward optimizer tests
5. ✅ Establish realistic coverage targets (15-20% overall, 50-60% factor modules)

### Expected Outcomes
- **Coverage**: 7.65% → 15-20% overall, 33.76% → 50-60% factor modules
- **Test Suite**: 138 passing → 160+ passing (95%+ pass rate)
- **Value Factor Coverage**: 0% → 60-70% (DividendYieldFactorPostgres, EVToEBITDAFactorPostgres)
- **Integration Tests**: 0 → 25+ (value factors + walk-forward optimizer)

---

## Task Breakdown

### Task 1: PostgreSQL Mock Infrastructure (2-3 hours)

**Dependencies**: None (can start immediately)
**Priority**: HIGH (blocks Task 3)
**Complexity**: MEDIUM

#### Objectives
1. Create reusable PostgreSQL mock fixtures using pytest-postgresql
2. Build test database schema matching production (tickers, fundamentals, ohlcv_data)
3. Implement fixture factories for realistic financial data
4. Validate mock infrastructure with sanity tests

#### Subtasks

##### 1.1 Install Testing Dependencies (15 min)
```bash
# Install PostgreSQL testing libraries
pip install pytest-postgresql psycopg2-binary faker

# Verify installation
python3 -c "import pytest_postgresql; print('✓ pytest-postgresql installed')"
```

**Deliverable**: Updated `requirements_quant.txt` with testing dependencies

##### 1.2 Create PostgreSQL Fixture Module (1 hour)
**File**: `/Users/13ruce/spock/tests/fixtures/postgres_fixtures.py`

```python
"""
PostgreSQL Fixtures for Integration Tests

Provides reusable database fixtures with:
- Temporary PostgreSQL instance (pytest-postgresql)
- Schema initialization (tickers, fundamentals, ohlcv_data)
- Data factory functions for realistic test data
"""

import pytest
from pytest_postgresql import factories
import psycopg2
from datetime import date, timedelta
from faker import Faker

# PostgreSQL process and connection fixtures
postgresql_proc = factories.postgresql_proc(port=None)
postgresql = factories.postgresql('postgresql_proc')

@pytest.fixture
def postgres_test_db(postgresql):
    """Create test database with schema."""
    conn = postgresql
    cursor = conn.cursor()

    # Create schema
    cursor.execute("""
        CREATE TABLE tickers (
            ticker VARCHAR(20) PRIMARY KEY,
            region VARCHAR(10),
            name VARCHAR(200),
            sector VARCHAR(100),
            market_cap BIGINT
        );
    """)

    cursor.execute("""
        CREATE TABLE ticker_fundamentals (
            ticker VARCHAR(20),
            region VARCHAR(10),
            date DATE,
            total_assets DECIMAL(20, 2),
            total_equity DECIMAL(20, 2),
            total_liabilities DECIMAL(20, 2),
            revenue DECIMAL(20, 2),
            operating_income DECIMAL(20, 2),
            net_income DECIMAL(20, 2),
            ebitda DECIMAL(20, 2),
            enterprise_value DECIMAL(20, 2),
            shares_outstanding BIGINT,
            PRIMARY KEY (ticker, region, date)
        );
    """)

    cursor.execute("""
        CREATE TABLE ohlcv_data (
            ticker VARCHAR(20),
            region VARCHAR(10),
            date DATE,
            open DECIMAL(20, 4),
            high DECIMAL(20, 4),
            low DECIMAL(20, 4),
            close DECIMAL(20, 4),
            volume BIGINT,
            PRIMARY KEY (ticker, region, date)
        );
    """)

    conn.commit()
    return conn

@pytest.fixture
def ticker_factory(postgres_test_db):
    """Factory for creating test tickers."""
    def create_ticker(ticker='005930', region='KR', name='Samsung Electronics',
                     sector='Technology', market_cap=500_000_000_000):
        cursor = postgres_test_db.cursor()
        cursor.execute("""
            INSERT INTO tickers (ticker, region, name, sector, market_cap)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ticker) DO NOTHING
        """, (ticker, region, name, sector, market_cap))
        postgres_test_db.commit()
        return ticker
    return create_ticker

@pytest.fixture
def fundamentals_factory(postgres_test_db):
    """Factory for creating test fundamental data."""
    def create_fundamentals(ticker, region, date,
                          total_assets=1_000_000, total_equity=500_000,
                          revenue=2_000_000, net_income=100_000):
        cursor = postgres_test_db.cursor()
        cursor.execute("""
            INSERT INTO ticker_fundamentals
            (ticker, region, date, total_assets, total_equity, revenue, net_income)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region, date) DO UPDATE SET
                total_assets = EXCLUDED.total_assets,
                total_equity = EXCLUDED.total_equity,
                revenue = EXCLUDED.revenue,
                net_income = EXCLUDED.net_income
        """, (ticker, region, date, total_assets, total_equity, revenue, net_income))
        postgres_test_db.commit()
    return create_fundamentals

@pytest.fixture
def ohlcv_factory(postgres_test_db):
    """Factory for creating test OHLCV data."""
    def create_ohlcv(ticker, region, start_date, end_date, base_price=100.0):
        cursor = postgres_test_db.cursor()
        current = start_date
        while current <= end_date:
            price = base_price * (1 + (current - start_date).days * 0.001)
            cursor.execute("""
                INSERT INTO ohlcv_data (ticker, region, date, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date) DO NOTHING
            """, (ticker, region, current, price, price*1.02, price*0.98, price, 1_000_000))
            current += timedelta(days=1)
        postgres_test_db.commit()
    return create_ohlcv
```

**Deliverable**: PostgreSQL fixture module with reusable test infrastructure

##### 1.3 Create Database Manager Mock (30 min)
**File**: `/Users/13ruce/spock/tests/fixtures/db_manager_mock.py`

```python
"""
Database Manager Mock for PostgreSQL Tests

Wraps pytest-postgresql fixtures to match production DatabaseManager interface.
"""

class MockPostgresManager:
    """Mock database manager matching production interface."""

    def __init__(self, connection):
        self.connection = connection

    def execute_query(self, query, params=None):
        """Execute query and return results."""
        cursor = self.connection.cursor()
        cursor.execute(query, params or ())

        if cursor.description:  # SELECT query
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        else:  # INSERT/UPDATE/DELETE
            self.connection.commit()
            return cursor.rowcount

    def fetchall(self, query, params=None):
        """Fetch all rows from query."""
        return self.execute_query(query, params)

    def close(self):
        """Close database connection."""
        self.connection.close()
```

**Deliverable**: Database manager mock matching production interface

##### 1.4 Validation Tests (30 min)
**File**: `/Users/13ruce/spock/tests/test_postgres_fixtures.py`

```python
"""
Validation Tests for PostgreSQL Fixtures

Ensures mock infrastructure works correctly before value factor tests.
"""

def test_postgres_connection(postgres_test_db):
    """Test PostgreSQL connection."""
    cursor = postgres_test_db.cursor()
    cursor.execute("SELECT 1")
    assert cursor.fetchone()[0] == 1

def test_ticker_creation(ticker_factory, postgres_test_db):
    """Test ticker creation."""
    ticker_factory('005930', 'KR', 'Samsung Electronics')

    cursor = postgres_test_db.cursor()
    cursor.execute("SELECT ticker, name FROM tickers WHERE ticker='005930'")
    row = cursor.fetchone()
    assert row[0] == '005930'
    assert row[1] == 'Samsung Electronics'

def test_fundamentals_creation(ticker_factory, fundamentals_factory, postgres_test_db):
    """Test fundamental data creation."""
    ticker_factory('005930')
    fundamentals_factory('005930', 'KR', date(2024, 3, 31),
                        total_assets=1_000_000, net_income=50_000)

    cursor = postgres_test_db.cursor()
    cursor.execute("""
        SELECT total_assets, net_income
        FROM ticker_fundamentals
        WHERE ticker='005930' AND date='2024-03-31'
    """)
    row = cursor.fetchone()
    assert row[0] == 1_000_000
    assert row[1] == 50_000

def test_ohlcv_creation(ticker_factory, ohlcv_factory, postgres_test_db):
    """Test OHLCV data creation."""
    ticker_factory('005930')
    ohlcv_factory('005930', 'KR', date(2024, 1, 1), date(2024, 1, 10))

    cursor = postgres_test_db.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM ohlcv_data
        WHERE ticker='005930' AND date BETWEEN '2024-01-01' AND '2024-01-10'
    """)
    count = cursor.fetchone()[0]
    assert count == 10  # 10 days of data
```

**Deliverable**: 4 validation tests ensuring fixtures work correctly

**Success Criteria**:
- ✅ pytest-postgresql installed and functional
- ✅ 4/4 fixture validation tests passing
- ✅ Mock database manager matches production interface
- ✅ Ready for value factor integration tests

---

### Task 2: Backfill Ticker 000020 Test Data (1-2 hours)

**Dependencies**: Task 1 complete (PostgreSQL fixtures ready)
**Priority**: HIGH (blocks Task 4)
**Complexity**: MEDIUM

#### Objectives
1. Extract ticker 000020 (동화약품) Q1 2024 data from production database
2. Insert into test SQLite database for walk-forward optimizer tests
3. Validate data completeness (90 days OHLCV + fundamentals)

#### Subtasks

##### 2.1 Extract Production Data (30 min)
```bash
# Connect to production PostgreSQL
psql -d quant_platform -c "
SELECT ticker, date, open, high, low, close, volume
FROM ohlcv_data
WHERE ticker='000020' AND region='KR'
  AND date BETWEEN '2024-01-01' AND '2024-03-31'
ORDER BY date
" > /tmp/ticker_000020_ohlcv.csv

# Extract fundamentals
psql -d quant_platform -c "
SELECT ticker, region, date, total_assets, total_equity, revenue, net_income
FROM ticker_fundamentals
WHERE ticker='000020' AND region='KR'
  AND date <= '2024-03-31'
ORDER BY date DESC LIMIT 1
" > /tmp/ticker_000020_fundamentals.csv
```

**Deliverable**: CSV files with ticker 000020 data

##### 2.2 Insert into Test Database (30 min)
```python
# Script: scripts/backfill_test_ticker_000020.py

import sqlite3
import csv
from pathlib import Path

def backfill_ticker_000020():
    """Backfill ticker 000020 Q1 2024 data into test database."""
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert ticker if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO tickers (ticker, region, name, sector)
        VALUES ('000020', 'KR', '동화약품', 'Healthcare')
    """)

    # Insert OHLCV data
    with open('/tmp/ticker_000020_ohlcv.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT OR REPLACE INTO ohlcv_data
                (ticker, region, date, open, high, low, close, volume, timeframe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '1d')
            """, (row['ticker'], 'KR', row['date'], row['open'],
                  row['high'], row['low'], row['close'], row['volume']))

    # Insert fundamentals
    with open('/tmp/ticker_000020_fundamentals.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT OR REPLACE INTO ticker_fundamentals
                (ticker, region, date, total_assets, total_equity, revenue, net_income)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (row['ticker'], row['region'], row['date'], row['total_assets'],
                  row['total_equity'], row['revenue'], row['net_income']))

    conn.commit()
    conn.close()
    print("✓ Ticker 000020 data backfilled successfully")

if __name__ == '__main__':
    backfill_ticker_000020()
```

**Deliverable**: Test database with ticker 000020 Q1 2024 data

##### 2.3 Validation (30 min)
```bash
# Verify OHLCV data
sqlite3 data/spock_local.db "
SELECT COUNT(*) as days, MIN(date) as start, MAX(date) as end
FROM ohlcv_data
WHERE ticker='000020' AND region='KR'
  AND date BETWEEN '2024-01-01' AND '2024-03-31'
"
# Expected: ~63 trading days (excluding weekends/holidays)

# Verify fundamentals
sqlite3 data/spock_local.db "
SELECT ticker, date, total_assets, net_income
FROM ticker_fundamentals
WHERE ticker='000020' AND region='KR'
ORDER BY date DESC LIMIT 1
"
# Expected: Latest fundamental data available

# Run walk-forward optimizer test
python3 -m pytest tests/backtesting/optimization/test_walk_forward_optimizer.py::TestOptimization::test_optimize_basic -v
# Expected: PASSED (previously failed with "No data loaded")
```

**Deliverable**: Validation report confirming data completeness

**Success Criteria**:
- ✅ 60-70 trading days of OHLCV data for ticker 000020
- ✅ Latest fundamental data available
- ✅ Walk-forward optimizer test now finds data (previously failed)

---

### Task 3: Value Factor Integration Tests (3-4 hours)

**Dependencies**: Task 1 complete (PostgreSQL fixtures ready)
**Priority**: MEDIUM (can run parallel with Task 2)
**Complexity**: HIGH

#### Objectives
1. Create integration tests for DividendYieldFactorPostgres
2. Create integration tests for EVToEBITDAFactorPostgres
3. Create integration tests for CompositeValueFactor
4. Achieve 60-70% coverage on value_factors.py

#### Subtasks

##### 3.1 DividendYieldFactorPostgres Tests (1.5 hours)
**File**: `/Users/13ruce/spock/tests/test_value_factors_integration.py`

**Test Structure** (8-10 tests):
```python
class TestDividendYieldFactorPostgres:
    def test_initialization(self, postgres_test_db):
        """Test factor initialization with database."""

    def test_calculate_high_dividend(self, postgres_test_db, ticker_factory, fundamentals_factory):
        """Test calculation with high dividend yield."""

    def test_calculate_zero_dividend(self, postgres_test_db, ticker_factory):
        """Test calculation with zero dividend (growth stock)."""

    def test_dividend_growth_trend(self, postgres_test_db):
        """Test dividend growth over multiple quarters."""

    def test_payout_ratio_validation(self, postgres_test_db):
        """Test payout ratio calculation and bounds."""

    def test_missing_fundamental_data(self, postgres_test_db):
        """Test handling of missing dividend data."""

    def test_negative_earnings_dividend(self, postgres_test_db):
        """Test dividend with negative earnings (payout > 100%)."""

    def test_metadata_completeness(self, postgres_test_db):
        """Ensure all metadata fields populated."""
```

**Expected Coverage**: 70-80% of DividendYieldFactorPostgres code

##### 3.2 EVToEBITDAFactorPostgres Tests (1.5 hours)
**Test Structure** (8-10 tests):
```python
class TestEVToEBITDAFactorPostgres:
    def test_initialization(self, postgres_test_db):
        """Test factor initialization with database."""

    def test_calculate_undervalued(self, postgres_test_db):
        """Test calculation with low EV/EBITDA (undervalued)."""

    def test_calculate_overvalued(self, postgres_test_db):
        """Test calculation with high EV/EBITDA (overvalued)."""

    def test_negative_ebitda_handling(self, postgres_test_db):
        """Test handling of negative EBITDA (loss-making)."""

    def test_enterprise_value_calculation(self, postgres_test_db):
        """Test EV = Market Cap + Debt - Cash calculation."""

    def test_sector_relative_valuation(self, postgres_test_db):
        """Test sector-relative EV/EBITDA comparison."""

    def test_missing_balance_sheet_data(self, postgres_test_db):
        """Test handling of missing debt/cash data."""

    def test_metadata_completeness(self, postgres_test_db):
        """Ensure all metadata fields populated."""
```

**Expected Coverage**: 60-70% of EVToEBITDAFactorPostgres code

##### 3.3 CompositeValueFactor Tests (30 min)
**Test Structure** (4-5 tests):
```python
class TestCompositeValueFactor:
    def test_initialization(self, postgres_test_db):
        """Test composite factor initialization."""

    def test_composite_scoring(self, postgres_test_db):
        """Test combination of dividend yield and EV/EBITDA."""

    def test_factor_weighting(self, postgres_test_db):
        """Test configurable factor weights."""

    def test_missing_subfactor(self, postgres_test_db):
        """Test handling when one subfactor unavailable."""
```

**Expected Coverage**: 50-60% of CompositeValueFactor code

**Success Criteria**:
- ✅ 20-25 value factor integration tests created
- ✅ All tests passing with PostgreSQL mock fixtures
- ✅ 60-70% coverage on value_factors.py (from 14.71%)
- ✅ Realistic financial scenarios tested (dividends, valuations)

---

### Task 4: Fix Walk-Forward Optimizer Tests (1-2 hours)

**Dependencies**: Task 2 complete (ticker 000020 data backfilled)
**Priority**: MEDIUM
**Complexity**: LOW (data issue, not logic issue)

#### Objectives
1. Re-run 6 environment-dependent walk-forward optimizer tests
2. Verify tests pass with ticker 000020 data available
3. Achieve 100% pass rate (18/18 tests)

#### Tests to Fix

1. `test_optimize_basic` - Basic optimization with parameter grid
2. `test_optimize_result_metrics` - Result metrics validation
3. `test_overfitting_detection` - Overfitting detection logic
4. `test_end_to_end_rolling_optimization` - Rolling window workflow
5. `test_end_to_end_anchored_optimization` - Anchored window workflow
6. `test_robustness_score_calculation` - Robustness metric calculation

#### Execution
```bash
# Run all walk-forward optimizer tests
python3 -m pytest tests/backtesting/optimization/test_walk_forward_optimizer.py -v

# Expected: 18/18 passing (previously 12/18)
```

**Success Criteria**:
- ✅ 18/18 walk-forward optimizer tests passing (from 12/18)
- ✅ All 6 integration tests with ticker 000020 data pass
- ✅ No "No data loaded" errors

---

### Task 5: Coverage Targets & Phase 0 Completion (1 hour)

**Dependencies**: Tasks 1-4 complete
**Priority**: LOW
**Complexity**: LOW

#### Objectives
1. Update QUANT_ROADMAP.md with realistic coverage targets
2. Generate comprehensive Phase 0 completion report
3. Document lessons learned and next steps

#### Subtasks

##### 5.1 Update Coverage Targets (15 min)
**File**: `/Users/13ruce/spock/docs/QUANT_ROADMAP.md`

**Changes**:
```markdown
### Success Metrics - Updated (2025-10-30)

#### Test Coverage Targets (Realistic)
- **Overall Project**: 15-20% (current: 7.65%)
- **Factor Modules**: 50-60% (current: 33.76%)
- **Backtesting Infrastructure**: 60-70% (current: 47.99%)
- **Data Providers**: 85%+ (current: 85.71% base, 47.99% postgres)

#### Test Suite Targets
- **Total Tests**: 160+ (current: 138 passing)
- **Pass Rate**: 95%+ (current: 96%)
- **Factor Tests**: 110-120 (current: 90)
- **Integration Tests**: 30-40 (current: 0)

#### Quality Gates
- All critical path tests passing (100%)
- No environment-dependent test failures
- Comprehensive test data for integration scenarios
```

##### 5.2 Generate Phase 0 Completion Report (30 min)
**File**: `/Users/13ruce/spock/docs/PHASE0_COMPLETION_REPORT.md`

**Structure**:
1. Executive Summary (Phase 0.1, 0.2, 0.3 achievements)
2. Coverage Progression (1.33% → 7.65% → 15-20%)
3. Test Suite Growth (23 → 138 → 160+)
4. Module-Specific Breakdown (factors, backtesting, data providers)
5. Lessons Learned (what worked, challenges, improvements)
6. Next Steps (Phase 1: Factor Library Development)

##### 5.3 Update Main Documentation (15 min)
**Files**:
- `CLAUDE.md`: Update Phase 0 status to COMPLETE
- `docs/QUANT_ROADMAP.md`: Mark Phase 0 checkpoints complete
- `README.md`: Update coverage badges and test counts

**Success Criteria**:
- ✅ Coverage targets updated to realistic levels
- ✅ Phase 0 completion report generated
- ✅ Documentation reflects current state

---

## Execution Strategy

### Recommended Sequence (Sequential with Parallel Opportunities)

**Day 1** (4-5 hours):
1. Task 1: PostgreSQL Mock Infrastructure (2-3 hours)
2. Task 2: Backfill Ticker 000020 Test Data (1-2 hours)

**Day 2** (3-4 hours):
3. Task 3: Value Factor Integration Tests (3-4 hours) [PARALLEL with Task 4 if Day 1 complete]
4. Task 4: Fix Walk-Forward Optimizer Tests (1-2 hours) [PARALLEL with Task 3]

**Day 3** (1 hour):
5. Task 5: Coverage Targets & Phase 0 Completion (1 hour)

### Parallel Execution Opportunities

**After Task 1 Complete**:
- Task 2 (data backfill) + Task 3 (value factor tests) can run in parallel
- Separate database instances (PostgreSQL mock vs SQLite test)

**After Task 2 Complete**:
- Task 3 (value factor tests) + Task 4 (walk-forward tests) can run in parallel
- Independent test suites (factor integration vs optimization)

---

## Risk Mitigation

### Known Risks

1. **PostgreSQL Mock Complexity**
   - **Mitigation**: Use proven pytest-postgresql library, start with simple fixtures
   - **Fallback**: SQLite-based mocks if PostgreSQL setup fails

2. **Test Data Quality**
   - **Mitigation**: Extract from production database, validate before backfill
   - **Fallback**: Synthetic data generation if production data unavailable

3. **Time Overrun**
   - **Mitigation**: Break tasks into 30-min increments, checkpoint progress
   - **Fallback**: Defer Task 5 (documentation) to Week 6 if needed

### Validation Checkpoints

- **After Task 1**: Run 4 fixture validation tests (must pass)
- **After Task 2**: Run 1 walk-forward test (must find data)
- **After Task 3**: Run all value factor tests (must pass)
- **After Task 4**: Run complete test suite (95%+ pass rate)

---

## Success Metrics

### Phase 0 Completion Criteria

- ✅ Overall coverage ≥15% (current: 7.65%)
- ✅ Factor module coverage ≥50% (current: 33.76%)
- ✅ Test suite pass rate ≥95% (current: 96%)
- ✅ All integration tests passing (value factors + walk-forward)
- ✅ Realistic coverage targets documented
- ✅ Phase 0 completion report generated

### Task-Specific Metrics

| Task | Success Criteria | Time Estimate |
|------|-----------------|---------------|
| 1. PostgreSQL Mock | 4/4 validation tests pass | 2-3 hours |
| 2. Test Data Backfill | 60-70 days OHLCV + fundamentals | 1-2 hours |
| 3. Value Factor Tests | 20-25 tests, 60-70% coverage | 3-4 hours |
| 4. Walk-Forward Tests | 18/18 passing (from 12/18) | 1-2 hours |
| 5. Coverage & Docs | Updated roadmap + completion report | 1 hour |
| **Total** | **160+ tests, 15-20% coverage** | **8-12 hours** |

---

## Next Steps After Week 5

### Phase 1: Factor Library Development (Week 6-8)
1. Implement remaining Growth & Efficiency factor tests
2. Expand factor combiner tests (11.36% → 60%+)
3. Create independence validator tests (0% → 70%+)
4. Target 20-25% overall coverage

### Phase 2: Strategy Development (Week 9-10)
1. Create multi-factor strategy framework
2. Implement strategy backtest workflows
3. Add performance attribution analysis

### Phase 3: Production Readiness (Week 11-15)
1. Market adapter tests (KIS API, data parsers)
2. End-to-end integration tests
3. Performance benchmarks and optimization
4. Target 30-40% overall coverage

---

**Plan Status**: Draft v1.0
**Prepared By**: Claude Code
**Date**: 2025-10-30
**Estimated Duration**: 8-12 hours (2-3 days)
