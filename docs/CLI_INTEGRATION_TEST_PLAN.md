# CLI Integration Test Plan

**Date**: 2025-10-30
**Sprint**: Sprint 7 - Integration Testing Phase
**Prerequisites**: Unit test framework operational (85% complete)

---

## Executive Summary

This plan defines the integration testing strategy for Spock CLI, building upon the existing `test_full_integration.sh` foundation. Integration tests validate component interactions, database operations, and end-to-end workflows to ensure the CLI functions correctly as a cohesive system.

**Objectives**:
- Validate interactions between CLI commands, database, and backtesting engines
- Test real database operations with PostgreSQL/TimescaleDB
- Verify end-to-end workflows (query → filter → export → backtest)
- Ensure performance targets are met in realistic scenarios
- Achieve ≥80% integration test coverage for critical paths

---

## Test Architecture

### Test Layer Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    E2E Tests (Level 3)                       │
│  Full workflow validation: CLI → DB → Engine → Report       │
│  Example: Complete backtest from query to HTML report       │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│              Integration Tests (Level 2)                     │
│  Component interaction validation: CLI ↔ Database           │
│  Example: QueryBuilder + DatabaseManager + OHLCV Loader     │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│                  Unit Tests (Level 1)                        │
│  Isolated component testing (79 tests, Sprint 7)            │
│  Example: DatabaseManager singleton, QueryBuilder SQL       │
└─────────────────────────────────────────────────────────────┘
```

### Integration Test Categories

#### Category 1: Database Integration Tests
**Purpose**: Validate real PostgreSQL/TimescaleDB operations

**Components Under Test**:
- DatabaseManager + asyncpg connection pooling
- OHLCV data queries with TimescaleDB hypertables
- Transaction management and rollback
- Query performance with real data volumes

**Test Strategy**:
- Use test database (quant_platform_test)
- Load representative dataset (5 tickers, 1 year OHLCV = ~1,260 rows per ticker)
- Measure query performance against benchmarks
- Validate data integrity and consistency

#### Category 2: CLI Command Integration Tests
**Purpose**: Validate command parsing, execution, and output formatting

**Components Under Test**:
- Query command → QueryBuilder → DatabaseManager → QueryFormatter
- Backtest command → BacktestRunner → vectorbt/PostgresDataProvider → ReportGenerator
- Setup command → database initialization → schema validation

**Test Strategy**:
- Execute CLI commands programmatically using `subprocess`
- Capture stdout/stderr for validation
- Parse JSON/CSV/HTML output for correctness
- Measure command execution time

#### Category 3: Backtesting Engine Integration Tests
**Purpose**: Validate backtesting pipeline with real data

**Components Under Test**:
- PostgresDataProvider → vectorbt strategy execution → metrics calculation
- BacktestRunner orchestration
- HTML/JSON report generation

**Test Strategy**:
- Use known strategies with predictable outcomes
- Validate metrics accuracy (Sharpe, drawdown, returns)
- Compare vectorbt vs custom engine results
- Performance benchmarking (<1s for 1-year backtest)

#### Category 4: End-to-End Workflow Tests
**Purpose**: Validate complete user workflows

**Workflows**:
1. **Discovery Workflow**: Query available tickers → filter by criteria → export to CSV
2. **Analysis Workflow**: Load OHLCV → calculate indicators → visualize
3. **Backtest Workflow**: Define strategy → run backtest → generate report → review metrics
4. **Portfolio Workflow**: Multiple backtests → compare results → select best strategy

**Test Strategy**:
- Scripted workflows using CLI commands
- State validation at each step
- Error handling and recovery testing
- Performance profiling for entire workflow

---

## Test Pass/Fail Criteria

### Category 1: Database Integration

| Test ID | Test Name | Pass Criteria | Fail Criteria |
|---------|-----------|---------------|---------------|
| DB-INT-001 | Connection pool creation | Pool created with 5-20 connections, no errors | Connection failure, timeout >5s |
| DB-INT-002 | OHLCV query performance | Query 1 ticker, 1 year <100ms | Query timeout >500ms, incorrect data |
| DB-INT-003 | Batch OHLCV query | Query 20 tickers, 1 year <500ms | Query timeout >2s, missing tickers |
| DB-INT-004 | Transaction rollback | Failed insert rolls back, no data corruption | Partial data commit, integrity violation |
| DB-INT-005 | Hypertable query optimization | TimescaleDB chunks used (EXPLAIN analysis) | Full table scan, >1s query time |
| DB-INT-006 | Connection pool exhaustion recovery | All connections released after queries | Connection leak, pool exhausted |

### Category 2: CLI Command Integration

| Test ID | Test Name | Pass Criteria | Fail Criteria |
|---------|-----------|---------------|---------------|
| CLI-INT-001 | Query command basic execution | Valid JSON output, correct schema | Invalid JSON, missing fields |
| CLI-INT-002 | Query command with filters | Filtered results match criteria (10/10 correct) | Wrong results, partial filter application |
| CLI-INT-003 | Query command CSV export | Valid CSV with header, correct data | Malformed CSV, data truncation |
| CLI-INT-004 | Backtest command execution | HTML report generated, metrics present | Error, missing report, no metrics |
| CLI-INT-005 | Setup command database init | Database created, schema valid, test query succeeds | Schema errors, missing tables |
| CLI-INT-006 | Error handling for invalid input | Clear error message, exit code ≠ 0 | Crash, stack trace, exit code 0 |

### Category 3: Backtesting Engine Integration

| Test ID | Test Name | Pass Criteria | Fail Criteria |
|---------|-----------|---------------|---------------|
| BT-INT-001 | PostgresDataProvider data loading | Data loaded for 5 tickers, 1 year, <500ms | Missing data, timeout >2s |
| BT-INT-002 | vectorbt strategy execution | Strategy runs, final portfolio value calculated | Error, NaN values, crash |
| BT-INT-003 | Metrics calculation accuracy | Sharpe ratio ±0.05 of expected, drawdown ±1% | Metrics >10% off, NaN values |
| BT-INT-004 | HTML report generation | Valid HTML, charts render, metrics table present | Invalid HTML, broken charts |
| BT-INT-005 | Performance benchmark | 5-year backtest <1s (vectorbt), <30s (custom) | Timeout >3s (vectorbt), >60s (custom) |
| BT-INT-006 | Engine comparison consistency | vectorbt vs custom engine: returns ±2% | Returns diverge >5%, different signals |

### Category 4: End-to-End Workflow

| Test ID | Test Name | Pass Criteria | Fail Criteria |
|---------|-----------|---------------|---------------|
| E2E-001 | Discovery workflow | Query → filter → export: 3 steps succeed, CSV valid | Any step fails, data loss |
| E2E-002 | Backtest workflow | Strategy → backtest → report: complete in <5s, metrics correct | Timeout >10s, incomplete report |
| E2E-003 | Multi-strategy comparison | 3 strategies compared, ranked by Sharpe, best identified | Ranking incorrect, missing strategy |
| E2E-004 | Error recovery workflow | DB disconnect → reconnect → query succeeds | Permanent failure, data corruption |
| E2E-005 | Performance under load | 5 concurrent backtests complete in <10s | Deadlock, timeout >30s |

---

## Performance Benchmarks

### Database Performance Targets

| Operation | Target | Warning | Critical |
|-----------|--------|---------|----------|
| Single ticker OHLCV query (1 year) | <100ms | 100-200ms | >500ms |
| Batch OHLCV query (20 tickers, 1 year) | <500ms | 500-1000ms | >2s |
| Database connection | <50ms | 50-100ms | >200ms |
| Query with aggregation (monthly avg) | <200ms | 200-500ms | >1s |

### Backtesting Performance Targets

| Operation | Target | Warning | Critical |
|-----------|--------|---------|----------|
| vectorbt 1-year backtest (1 ticker) | <100ms | 100-500ms | >1s |
| vectorbt 5-year backtest (5 tickers) | <1s | 1-3s | >5s |
| Custom engine 5-year backtest | <30s | 30-60s | >120s |
| Report generation (HTML) | <500ms | 500-1000ms | >2s |

### CLI Command Performance Targets

| Command | Target | Warning | Critical |
|---------|--------|---------|----------|
| `query --ticker 005930` | <200ms | 200-500ms | >1s |
| `query --all --export csv` | <2s | 2-5s | >10s |
| `backtest --strategy momentum` | <5s | 5-10s | >30s |
| `setup --init-db` | <10s | 10-30s | >60s |

---

## Test Implementation Strategy

### Phase 1: Database Integration Tests (Week 1)

**Priority**: HIGHEST (foundation for all other tests)

**Implementation**:
1. Create test database: `quant_platform_test`
2. Load test dataset: 5 representative tickers (005930 Samsung, 035720 Kakao, US:AAPL, US:TSLA, ETF:KODEX200)
3. Implement pytest tests in `tests/test_cli/integration/test_database_integration.py`

**Test Structure**:
```python
@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    @pytest.fixture(scope="class")
    async def test_db(self):
        """Setup test database with sample data."""
        # Create test database
        # Load 5 tickers, 1 year OHLCV data
        yield db_manager
        # Cleanup

    @pytest.mark.asyncio
    async def test_connection_pool_creation(self, test_db):
        """DB-INT-001: Validate connection pool creation."""
        # Test implementation

    @pytest.mark.asyncio
    async def test_ohlcv_query_performance(self, test_db):
        """DB-INT-002: Validate single ticker query <100ms."""
        # Test implementation
```

**Success Criteria**: All 6 database integration tests passing

### Phase 2: CLI Command Integration Tests (Week 1-2)

**Priority**: HIGH (validates user-facing functionality)

**Implementation**:
1. Use `subprocess.run()` to execute CLI commands
2. Capture and validate stdout/stderr output
3. Parse JSON/CSV output for correctness
4. Implement in `tests/test_cli/integration/test_cli_commands.py`

**Test Structure**:
```python
@pytest.mark.integration
class TestCLICommands:
    def test_query_command_basic(self, test_db):
        """CLI-INT-001: Query command produces valid JSON."""
        result = subprocess.run(
            ["python3", "cli/shell.py", "query", "--ticker", "005930", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "ticker" in data
        assert "ohlcv" in data

    def test_query_command_with_filters(self, test_db):
        """CLI-INT-002: Query filters work correctly."""
        # Test implementation
```

**Success Criteria**: All 6 CLI command integration tests passing

### Phase 3: Backtesting Engine Integration Tests (Week 2)

**Priority**: HIGH (core functionality validation)

**Implementation**:
1. Use PostgresDataProvider with test database
2. Execute known strategies with predictable outcomes
3. Validate metrics against expected values
4. Implement in `tests/test_cli/integration/test_backtest_integration.py`

**Test Structure**:
```python
@pytest.mark.integration
class TestBacktestIntegration:
    @pytest.fixture
    def momentum_strategy(self):
        """Simple momentum strategy for testing."""
        # Return strategy configuration

    @pytest.mark.asyncio
    async def test_postgres_data_provider_loading(self, test_db):
        """BT-INT-001: Validate data provider loads data correctly."""
        provider = PostgresDataProvider(db_manager=test_db)
        data = await provider.load_ohlcv(
            tickers=["005930", "035720"],
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        assert len(data) == 2
        assert data["005930"].shape[0] > 200  # ~252 trading days

    def test_vectorbt_strategy_execution(self, test_db, momentum_strategy):
        """BT-INT-002: vectorbt strategy executes successfully."""
        # Test implementation
```

**Success Criteria**: All 6 backtesting integration tests passing

### Phase 4: End-to-End Workflow Tests (Week 2-3)

**Priority**: MEDIUM (validates complete workflows)

**Implementation**:
1. Script multi-step workflows using CLI commands
2. Validate state at each step
3. Test error recovery and edge cases
4. Implement in `tests/test_cli/integration/test_e2e_workflows.py`

**Test Structure**:
```python
@pytest.mark.integration
@pytest.mark.e2e
class TestE2EWorkflows:
    def test_discovery_workflow(self, test_db):
        """E2E-001: Complete discovery workflow."""
        # Step 1: Query all tickers
        result1 = subprocess.run(...)
        assert result1.returncode == 0

        # Step 2: Filter by criteria
        result2 = subprocess.run(...)
        assert result2.returncode == 0

        # Step 3: Export to CSV
        result3 = subprocess.run(...)
        assert result3.returncode == 0
        assert os.path.exists("output.csv")

    def test_backtest_workflow(self, test_db):
        """E2E-002: Complete backtest workflow <5s."""
        # Test implementation with timing validation
```

**Success Criteria**: All 5 E2E workflow tests passing

---

## Test Data Management

### Test Database Setup

**Database**: `quant_platform_test` (separate from production `quant_platform`)

**Test Dataset**:
```sql
-- 5 representative tickers
Ticker    | Region | Type  | OHLCV Records | Period
----------|--------|-------|---------------|----------
005930    | KR     | Stock | 1,260         | 2020-2025
035720    | KR     | Stock | 1,260         | 2020-2025
AAPL      | US     | Stock | 1,260         | 2020-2025
TSLA      | US     | Stock | 1,260         | 2020-2025
KODEX200  | KR     | ETF   | 1,260         | 2020-2025

Total: 6,300 OHLCV records
```

**Setup Script**: `tests/fixtures/setup_test_database.py`
```python
async def setup_test_database():
    """Initialize test database with sample data."""
    # 1. Create test database
    # 2. Run schema migrations
    # 3. Load test data from CSV fixtures
    # 4. Validate data integrity
```

**Teardown Strategy**:
- **Per-test**: Rollback transactions (fast, isolated)
- **Per-session**: Recreate database (slow, clean slate)
- **CI/CD**: Ephemeral Docker container with PostgreSQL + TimescaleDB

### Test Fixtures

**Location**: `tests/fixtures/`

**Files**:
- `ohlcv_samsung_2020-2025.csv` - Samsung Electronics daily OHLCV
- `ohlcv_kakao_2020-2025.csv` - Kakao Corp daily OHLCV
- `ohlcv_aapl_2020-2025.csv` - Apple Inc daily OHLCV
- `ohlcv_tsla_2020-2025.csv` - Tesla Inc daily OHLCV
- `ohlcv_kodex200_2020-2025.csv` - KODEX 200 ETF daily OHLCV

**Generation**: Extract from production database or use yfinance to fetch historical data

---

## Test Execution Plan

### Local Development Testing

**Command**:
```bash
# Run all integration tests
python -m pytest tests/test_cli/integration/ -v -m integration

# Run specific category
python -m pytest tests/test_cli/integration/ -v -m database

# Run with coverage
python -m pytest tests/test_cli/integration/ -v --cov=cli --cov-report=html

# Run performance benchmarks
python -m pytest tests/test_cli/integration/ -v -m "integration and not slow"
```

### CI/CD Integration

**GitHub Actions Workflow**:
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: quant_platform_test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          pip install -r requirements_quant.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Setup test database
        run: python tests/fixtures/setup_test_database.py

      - name: Run integration tests
        run: pytest tests/test_cli/integration/ -v --cov=cli --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Performance Regression Testing

**Strategy**: Track performance metrics over time using `pytest-benchmark`

**Implementation**:
```python
@pytest.mark.integration
@pytest.mark.benchmark
def test_query_performance_regression(benchmark, test_db):
    """Track query performance over time."""
    result = benchmark(
        lambda: query_ohlcv(ticker="005930", start="2023-01-01", end="2023-12-31")
    )
    # pytest-benchmark automatically tracks and compares results
```

**Baseline**: First run establishes baseline, subsequent runs compared against it

---

## Integration with Existing Tests

### Extend test_full_integration.sh

**Current Structure** (19 tests across 6 sprints):
```bash
# Sprint 1-2: Database & Query
test_database_connection
test_query_single_ticker
test_query_with_filters
test_csv_export

# Sprint 3-4: Backtesting
test_backtest_simple_strategy
test_vectorbt_integration
test_report_generation

# Sprint 5-6: Shell & Performance
test_interactive_shell
test_performance_benchmarks
```

**Enhancement Plan**:
1. Keep shell script for quick smoke tests
2. Add detailed pytest integration tests for each category
3. Use shell script as pre-commit hook (fast validation)
4. Use pytest for comprehensive integration testing (CI/CD)

**Relationship**:
```
test_full_integration.sh (smoke tests, 2-3 min)
    ↓ If all pass
pytest integration tests (comprehensive, 5-10 min)
    ↓ If all pass
pytest e2e tests (workflows, 10-15 min)
```

---

## Test Coverage Goals

### Integration Test Coverage Targets

| Component | Target Coverage | Priority |
|-----------|-----------------|----------|
| CLI commands (query, backtest, setup) | 90%+ | HIGHEST |
| DatabaseManager + PostgresDataProvider | 85%+ | HIGHEST |
| BacktestRunner + vectorbt adapter | 85%+ | HIGH |
| Report generation | 75%+ | MEDIUM |
| Shell integration | 70%+ | LOW |

### Critical Path Identification

**Critical Path 1: Query Workflow**
```
CLI input → QueryBuilder → DatabaseManager → PostgreSQL → QueryFormatter → Output
Coverage Target: 95%
```

**Critical Path 2: Backtest Workflow**
```
CLI input → BacktestRunner → PostgresDataProvider → vectorbt → ReportGenerator → HTML
Coverage Target: 90%
```

**Critical Path 3: Error Recovery**
```
Database disconnect → Retry logic → Reconnection → Query retry → Success
Coverage Target: 85%
```

### Risk-Based Test Prioritization

**Priority 1 (Must Have)**:
- Database connection and query operations (DB-INT-001 to DB-INT-003)
- Basic CLI command execution (CLI-INT-001, CLI-INT-004)
- Backtest execution and metrics (BT-INT-001 to BT-INT-003)

**Priority 2 (Should Have)**:
- Error handling and recovery (CLI-INT-006, E2E-004)
- Performance benchmarks (BT-INT-005, E2E-005)
- Report generation (BT-INT-004)

**Priority 3 (Nice to Have)**:
- Advanced filtering and export (CLI-INT-002, CLI-INT-003)
- Multi-strategy comparison (E2E-003)
- Connection pool exhaustion recovery (DB-INT-006)

---

## Quality Gates

### Integration Test Quality Gate

**Gate Criteria** (all must pass before merging):
1. ✅ All Priority 1 integration tests passing (18 tests)
2. ✅ Integration test coverage ≥80%
3. ✅ All performance benchmarks within target thresholds
4. ✅ No critical or high-severity bugs
5. ✅ Test execution time <15 minutes (full suite)

### Definition of Done for Integration Testing

**Sprint 7 Integration Testing Complete When**:
1. ✅ 23 integration tests implemented and passing (6 DB + 6 CLI + 6 BT + 5 E2E)
2. ✅ Test database setup automated (`setup_test_database.py`)
3. ✅ CI/CD workflow configured and running
4. ✅ Performance baseline established and documented
5. ✅ Integration test documentation complete (this document + inline docstrings)
6. ✅ All critical paths covered (≥95% coverage)

---

## Monitoring and Reporting

### Test Execution Monitoring

**Metrics to Track**:
- Test pass rate (target: 100%)
- Average test execution time (baseline TBD, alert if >2x baseline)
- Flaky test rate (target: <5%)
- Code coverage trend (target: increasing to 80%+)

**Reporting Tools**:
- pytest HTML report (`--html=report.html`)
- Coverage HTML report (`--cov-report=html`)
- pytest-benchmark results (JSON export)

### Continuous Monitoring

**Daily**:
- Integration test suite execution (automated via cron or CI/CD)
- Performance regression detection (pytest-benchmark alerts)
- Test failure notifications (email/Slack)

**Weekly**:
- Coverage trend analysis
- Flaky test identification and resolution
- Performance benchmark review

**Monthly**:
- Integration test effectiveness review
- Test suite optimization (remove redundant tests, add missing coverage)
- Performance baseline recalibration

---

## Risks and Mitigations

### Risk 1: Test Database State Pollution
**Impact**: HIGH - Tests may fail intermittently if database state is not clean

**Mitigation**:
- Use transactions with rollback for each test
- Implement database cleanup fixtures (`@pytest.fixture(scope="function")`)
- Run tests in isolated Docker containers in CI/CD

### Risk 2: Slow Test Execution
**Impact**: MEDIUM - Long test execution discourages frequent testing

**Mitigation**:
- Optimize test data size (use minimal representative dataset)
- Implement test parallelization (`pytest-xdist`)
- Use test markers to run fast tests frequently, slow tests in CI/CD

### Risk 3: Flaky Tests Due to Timing Issues
**Impact**: MEDIUM - Intermittent failures reduce confidence in test suite

**Mitigation**:
- Avoid hard-coded sleep() calls, use proper async/await patterns
- Implement retry logic for network/database operations
- Use pytest-rerunfailures plugin for automatic retry

### Risk 4: Test Data Drift
**Impact**: LOW - Test fixtures become outdated or inconsistent

**Mitigation**:
- Version control test fixtures (CSV files in `tests/fixtures/`)
- Automate fixture generation from production database snapshots
- Document fixture generation process

---

## Success Metrics

### Quantitative Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Integration test count | 19 (shell script) | 23+ (pytest) | pytest count |
| Integration test pass rate | N/A | 100% | pytest report |
| Integration test coverage | N/A | ≥80% | pytest-cov |
| Critical path coverage | N/A | ≥95% | Manual analysis |
| Test execution time | N/A | <15 min | pytest duration |
| Flaky test rate | N/A | <5% | Manual tracking |

### Qualitative Metrics

- **Developer Confidence**: Developers can refactor confidently knowing tests will catch regressions
- **Bug Detection Rate**: Integration tests catch bugs before manual testing
- **Documentation Quality**: Tests serve as executable documentation for component interactions
- **Maintainability**: Tests are easy to understand, modify, and extend

---

## Timeline

### Week 1: Database + CLI Integration Tests (5-7 days)
- Day 1-2: Setup test database, load fixtures, implement DB integration tests (6 tests)
- Day 3-4: Implement CLI command integration tests (6 tests)
- Day 5: Test execution, debugging, documentation
- **Deliverable**: 12 integration tests passing, test database operational

### Week 2: Backtesting + E2E Integration Tests (5-7 days)
- Day 1-2: Implement backtesting integration tests (6 tests)
- Day 3-4: Implement E2E workflow tests (5 tests)
- Day 5: Performance benchmarking, optimization, documentation
- **Deliverable**: 23 integration tests passing, performance baselines established

### Week 3: CI/CD Integration + Monitoring (3-5 days)
- Day 1-2: Configure GitHub Actions workflow, Docker setup
- Day 3: Implement monitoring and reporting
- Day 4-5: Documentation, final validation, Sprint 7 completion report
- **Deliverable**: Automated testing pipeline, Sprint 7 complete

---

## Appendix

### Appendix A: Example Test Implementation

**File**: `tests/test_cli/integration/test_database_integration.py`

```python
"""
Integration tests for database operations.

Tests validate real PostgreSQL/TimescaleDB interactions, connection pooling,
query performance, and data integrity.
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from cli.utils.database import DatabaseManager
from cli.utils.ohlcv_loader import OHLCVLoader


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.fixture(scope="class")
    async def test_db(self):
        """Setup test database connection."""
        db = DatabaseManager()
        await db.connect(config={
            'host': 'localhost',
            'port': 5432,
            'database': 'quant_platform_test',
            'user': 'postgres',
            'password': 'test'
        })
        yield db
        await db.disconnect()

    @pytest.mark.asyncio
    async def test_connection_pool_creation(self, test_db):
        """
        DB-INT-001: Validate connection pool creation.

        Pass Criteria: Pool created with 5-20 connections, no errors
        Fail Criteria: Connection failure, timeout >5s
        """
        start = time.time()

        # Validate pool exists
        assert test_db._pool is not None

        # Validate connection pool size
        pool_size = test_db._pool.get_size()
        assert 5 <= pool_size <= 20, f"Pool size {pool_size} outside range 5-20"

        # Validate connection time
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Connection took {elapsed:.2f}s (>5s limit)"

    @pytest.mark.asyncio
    async def test_ohlcv_query_performance(self, test_db):
        """
        DB-INT-002: Validate single ticker query <100ms.

        Pass Criteria: Query 1 ticker, 1 year <100ms
        Fail Criteria: Query timeout >500ms, incorrect data
        """
        start_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now()

        start = time.time()

        # Execute query
        query = """
            SELECT ticker, date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = $1
              AND date >= $2
              AND date <= $3
            ORDER BY date
        """
        rows = await test_db.fetch(query, "005930", start_date, end_date)

        elapsed = (time.time() - start) * 1000  # Convert to ms

        # Validate performance
        assert elapsed < 100, f"Query took {elapsed:.2f}ms (>100ms target)"

        # Validate data
        assert len(rows) > 200, f"Expected >200 rows, got {len(rows)}"
        assert all(row['ticker'] == '005930' for row in rows)

    @pytest.mark.asyncio
    async def test_batch_ohlcv_query_performance(self, test_db):
        """
        DB-INT-003: Validate batch query <500ms.

        Pass Criteria: Query 20 tickers, 1 year <500ms
        Fail Criteria: Query timeout >2s, missing tickers
        """
        tickers = ["005930", "035720", "051910", "005380", "000660"] * 4  # 20 tickers
        start_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now()

        start = time.time()

        # Execute batch query
        query = """
            SELECT ticker, date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = ANY($1::text[])
              AND date >= $2
              AND date <= $3
            ORDER BY ticker, date
        """
        rows = await test_db.fetch(query, tickers, start_date, end_date)

        elapsed = (time.time() - start) * 1000  # Convert to ms

        # Validate performance
        assert elapsed < 500, f"Batch query took {elapsed:.2f}ms (>500ms target)"

        # Validate all tickers present
        tickers_in_result = set(row['ticker'] for row in rows)
        assert len(tickers_in_result) >= 5, f"Expected 5+ unique tickers, got {len(tickers_in_result)}"

    # Additional tests: DB-INT-004, DB-INT-005, DB-INT-006...
```

### Appendix B: Test Fixture Examples

**File**: `tests/fixtures/setup_test_database.py`

```python
"""
Setup test database with sample OHLCV data.

Usage:
    python tests/fixtures/setup_test_database.py
"""
import asyncio
import asyncpg
import pandas as pd
from pathlib import Path


async def setup_test_database():
    """Initialize test database with sample data."""
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='test'
    )

    # Drop and recreate test database
    await conn.execute("DROP DATABASE IF EXISTS quant_platform_test")
    await conn.execute("CREATE DATABASE quant_platform_test")
    await conn.close()

    # Connect to test database
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='quant_platform_test',
        user='postgres',
        password='test'
    )

    # Enable TimescaleDB
    await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # Create schema (copy from production schema)
    schema_file = Path(__file__).parent.parent.parent / "scripts" / "init_postgres_schema.sql"
    schema_sql = schema_file.read_text()
    await conn.execute(schema_sql)

    # Load test data
    fixtures_dir = Path(__file__).parent
    test_tickers = [
        ("005930", "KR", "Stock"),
        ("035720", "KR", "Stock"),
        ("AAPL", "US", "Stock"),
        ("TSLA", "US", "Stock"),
        ("KODEX200", "KR", "ETF")
    ]

    for ticker, region, asset_type in test_tickers:
        # Insert ticker
        await conn.execute("""
            INSERT INTO tickers (ticker, name, region, asset_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (ticker, region) DO NOTHING
        """, ticker, ticker, region, asset_type)

        # Load OHLCV data from CSV
        csv_file = fixtures_dir / f"ohlcv_{ticker.lower()}_2020-2025.csv"
        if csv_file.exists():
            df = pd.read_csv(csv_file)

            # Insert OHLCV data
            await conn.executemany("""
                INSERT INTO ohlcv_data (ticker, region, timeframe, date, open, high, low, close, volume)
                VALUES ($1, $2, '1d', $3, $4, $5, $6, $7, $8)
                ON CONFLICT (ticker, region, timeframe, date) DO NOTHING
            """, [
                (ticker, region, row['date'], row['open'], row['high'],
                 row['low'], row['close'], row['volume'])
                for _, row in df.iterrows()
            ])

            print(f"Loaded {len(df)} OHLCV records for {ticker}")

    await conn.close()
    print("Test database setup complete!")


if __name__ == "__main__":
    asyncio.run(setup_test_database())
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Next Review**: After Phase 1 completion (Week 1)
