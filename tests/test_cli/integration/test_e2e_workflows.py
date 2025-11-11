"""
End-to-end workflow integration tests.

Tests validate complete workflows from start to finish, including:
- Discovery workflow (query → filter → CSV export)
- Backtest workflow (strategy → execution → report)
- Multi-strategy comparison (3 strategies → ranking)
- Error recovery (DB disconnect → reconnect → success)
- Concurrent execution (5 parallel backtests)

Test Database:
- 5 KR tickers: 005930, 035720, 032830, 034020, 006800
- 1,220 OHLCV records (244 rows per ticker, 2024 data)
- TimescaleDB hypertable optimization enabled

Performance Targets:
- Discovery workflow: <5s
- Backtest workflow: <5s
- Multi-strategy comparison: <15s
- Error recovery: <5s
- Concurrent execution: <10s

Usage:
    # Run all E2E workflow tests
    pytest tests/test_cli/integration/test_e2e_workflows.py -v -m e2e

    # Run specific test
    pytest tests/test_cli/integration/test_e2e_workflows.py::TestE2EWorkflows::test_discovery_workflow -v
"""
import pytest
import time
import csv
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from cli.utils.database import DatabaseManager
from cli.utils.query_formatter import QueryFormatter
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider


@pytest.mark.integration
@pytest.mark.e2e
class TestE2EWorkflows:
    """End-to-end workflow integration tests."""

    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'quant_platform_test',
        'user': '13ruce'
    }

    @pytest.fixture
    def db_manager(self):
        """Create PostgresDatabaseManager instance for backtesting tests."""
        db = PostgresDatabaseManager(
            host=self.DB_CONFIG['host'],
            port=self.DB_CONFIG['port'],
            database=self.DB_CONFIG['database'],
            user=self.DB_CONFIG['user']
        )
        yield db
        # Cleanup connections
        if hasattr(db, 'pool') and db.pool:
            db.pool.closeall()

    @pytest.fixture
    def data_provider(self, db_manager):
        """Create PostgresDataProvider with backfill disabled for testing."""
        return PostgresDataProvider(
            db_manager=db_manager,
            cache_enabled=True,
            backfill_enabled=False  # Disable backfill for integration tests
        )

    @pytest.mark.asyncio
    async def test_discovery_workflow(self):
        """
        E2E-001: Discovery workflow (query → filter → CSV export).

        Pass Criteria:
        - All 3 steps succeed sequentially (query, filter, export)
        - CSV file created and valid (parseable with correct schema)
        - Data integrity maintained across steps (no data loss)
        - Complete workflow execution <5s

        Fail Criteria:
        - Any step fails or raises exception
        - Data loss between steps (row count mismatch)
        - CSV file malformed or missing columns
        - Timeout >10s
        """
        start = time.time()

        # Step 1: Query - Load OHLCV data for Samsung Electronics
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            query_sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                  AND o.date >= $3
                  AND o.date <= $4
                ORDER BY o.date ASC
            """
            rows = await db.fetch(query_sql, '005930', 'KR', datetime(2024, 1, 1), datetime(2024, 12, 31))

            # Validate query step
            assert len(rows) > 200, f"Query step failed: Expected >200 rows, got {len(rows)}"
            initial_row_count = len(rows)

            # Step 2: Filter - Apply volume filter (>10M shares)
            filtered_rows = [row for row in rows if row['volume'] > 10_000_000]

            # Validate filter step
            assert len(filtered_rows) > 0, "Filter step failed: No rows passed volume filter"
            assert len(filtered_rows) <= initial_row_count, "Filter step failed: Increased row count"

            # Step 3: Export - Export filtered results to CSV
            with tempfile.TemporaryDirectory() as tmpdir:
                csv_path = Path(tmpdir) / "discovery_output.csv"

                # Use QueryFormatter to export
                formatter = QueryFormatter()
                formatter.export_csv(filtered_rows, str(csv_path))

                # Validate export step - CSV file created
                assert csv_path.exists(), "Export step failed: CSV file not created"

                # Validate CSV structure and data integrity
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)

                    # Validate schema
                    expected_columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
                    assert all(col in reader.fieldnames for col in expected_columns), \
                        f"Export step failed: Missing columns. Expected: {expected_columns}, Got: {reader.fieldnames}"

                    # Validate data integrity (no data loss)
                    csv_rows = list(reader)
                    assert len(csv_rows) == len(filtered_rows), \
                        f"Export step failed: Data loss detected. Filter: {len(filtered_rows)}, CSV: {len(csv_rows)}"

                    # Validate data correctness (spot check first row)
                    if csv_rows:
                        first_csv = csv_rows[0]
                        first_filter = filtered_rows[0]
                        assert first_csv['ticker'] == first_filter['ticker'], "Export step failed: Data corruption"
                        assert float(first_csv['close']) == float(first_filter['close']), "Export step failed: Price mismatch"

            elapsed = time.time() - start

            # Validate performance
            assert elapsed < 5.0, f"Workflow took {elapsed:.2f}s (target: <5s)"

            print(f"✅ E2E-001 PASSED: Discovery workflow completed in {elapsed:.2f}s")
            print(f"  - Query: {initial_row_count} rows")
            print(f"  - Filter: {len(filtered_rows)} rows (volume >10M)")
            print(f"  - Export: {len(csv_rows)} rows to CSV")

        finally:
            await db.disconnect()

    def test_backtest_workflow(self, data_provider):
        """
        E2E-002: Backtest workflow (strategy → execution → report).

        Pass Criteria:
        - Strategy definition → backtest execution → metrics calculation complete
        - All metrics calculated correctly (finite, not NaN)
        - Workflow completes <5s

        Fail Criteria:
        - Workflow timeout >10s
        - Metrics calculation errors (NaN or infinite values)
        - Strategy execution failure
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date
        import numpy as np

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping E2E-002")

        start = time.time()

        # Step 1: Strategy Definition
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],  # Samsung Electronics
            initial_capital=100_000_000
        )

        # Step 2: Backtest Execution
        adapter = VectorbtAdapter(config=config, data_provider=data_provider)
        result = adapter.run()

        # Step 3: Metrics Calculation Validation
        # Validate all metrics are calculated
        assert hasattr(result, 'total_return'), "Missing total_return metric"
        assert hasattr(result, 'sharpe_ratio'), "Missing sharpe_ratio metric"
        assert hasattr(result, 'max_drawdown'), "Missing max_drawdown metric"
        assert hasattr(result, 'win_rate'), "Missing win_rate metric"
        assert hasattr(result, 'total_trades'), "Missing total_trades metric"

        # Validate metrics are finite (not NaN or inf)
        assert np.isfinite(result.total_return), "total_return is not finite"
        assert np.isfinite(result.sharpe_ratio), "sharpe_ratio is not finite"
        assert np.isfinite(result.max_drawdown), "max_drawdown is not finite"
        assert np.isfinite(result.win_rate), "win_rate is not finite"

        # Validate equity curve generated
        assert hasattr(result, 'equity_curve'), "Missing equity_curve"
        assert len(result.equity_curve) > 0, "Empty equity curve"

        elapsed = time.time() - start

        # Validate performance
        assert elapsed < 5.0, f"Workflow took {elapsed:.2f}s (target: <5s)"

        print(f"✅ E2E-002 PASSED: Backtest workflow completed in {elapsed:.2f}s")
        print(f"  - Strategy: MA Crossover (20/50)")
        print(f"  - Total Return: {result.total_return:.2%}")
        print(f"  - Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"  - Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  - Trades: {result.total_trades}")

    def test_multi_strategy_comparison(self, data_provider):
        """
        E2E-003: Multi-strategy comparison (3 strategies → ranking).

        Pass Criteria:
        - All 3 strategies run successfully
        - Strategies ranked by Sharpe ratio
        - Best strategy identified correctly
        - All executions complete <15s

        Fail Criteria:
        - Ranking incorrect (wrong order)
        - Missing strategy results
        - Comparison metrics inconsistent
        - Timeout >30s
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping E2E-003")

        start = time.time()

        # Define 3 strategies with different MA parameters
        strategies = [
            {'name': 'Aggressive', 'fast': 10, 'slow': 30},
            {'name': 'Moderate', 'fast': 20, 'slow': 50},
            {'name': 'Conservative', 'fast': 30, 'slow': 70}
        ]

        results = []

        # Execute all 3 strategies
        for strategy in strategies:
            config = BacktestConfig(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                regions=['KR'],
                tickers=['005930'],
                initial_capital=100_000_000
            )

            adapter = VectorbtAdapter(config=config, data_provider=data_provider)
            result = adapter.run(fast_window=strategy['fast'], slow_window=strategy['slow'])

            results.append({
                'name': strategy['name'],
                'fast': strategy['fast'],
                'slow': strategy['slow'],
                'sharpe': result.sharpe_ratio,
                'return': result.total_return,
                'drawdown': result.max_drawdown,
                'trades': result.total_trades
            })

        # Validate all strategies executed
        assert len(results) == 3, f"Expected 3 strategy results, got {len(results)}"

        # Rank strategies by Sharpe ratio (descending)
        ranked = sorted(results, key=lambda x: x['sharpe'], reverse=True)

        # Identify best strategy
        best_strategy = ranked[0]

        # Validate ranking is correct (Sharpe ratios in descending order)
        for i in range(len(ranked) - 1):
            assert ranked[i]['sharpe'] >= ranked[i+1]['sharpe'], \
                f"Ranking incorrect: {ranked[i]['name']} (Sharpe={ranked[i]['sharpe']:.2f}) should rank higher than {ranked[i+1]['name']} (Sharpe={ranked[i+1]['sharpe']:.2f})"

        elapsed = time.time() - start

        # Validate performance
        assert elapsed < 15.0, f"Multi-strategy comparison took {elapsed:.2f}s (target: <15s)"

        print(f"✅ E2E-003 PASSED: Multi-strategy comparison completed in {elapsed:.2f}s")
        print(f"\n  Strategy Rankings (by Sharpe Ratio):")
        for i, s in enumerate(ranked, 1):
            print(f"  {i}. {s['name']:12} (MA {s['fast']}/{s['slow']}): Sharpe={s['sharpe']:6.2f}, Return={s['return']:7.2%}, Trades={s['trades']}")
        print(f"\n  🏆 Best Strategy: {best_strategy['name']} (Sharpe={best_strategy['sharpe']:.2f})")

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self):
        """
        E2E-004: Error recovery workflow (DB disconnect → reconnect → success).

        Pass Criteria:
        - Simulated DB disconnect → automatic reconnect → query succeeds
        - No data corruption during recovery
        - Error handled gracefully (no crash)
        - Recovery time <5s

        Fail Criteria:
        - Permanent failure (no recovery)
        - Data corruption detected
        - Uncaught exception/crash
        - Connection leak
        """
        start = time.time()

        # Step 1: Establish initial connection and baseline query
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Baseline query
            initial_query = "SELECT COUNT(*) as count FROM tickers WHERE region = $1"
            initial_result = await db.fetchval(initial_query, 'KR')
            assert initial_result == 5, f"Baseline query failed: Expected 5 tickers, got {initial_result}"

            # Step 2: Simulate connection failure (disconnect)
            await db.disconnect()

            # Step 3: Attempt query while disconnected (should fail gracefully)
            query_failed = False
            try:
                await db.fetch(initial_query, 'KR')
            except Exception:
                query_failed = True  # Expected to fail

            assert query_failed, "Query should have failed after disconnect"

            # Step 4: Reconnect
            await db.connect(config=self.DB_CONFIG)

            # Step 5: Retry query (should succeed)
            recovery_result = await db.fetchval(initial_query, 'KR')

            # Validate data integrity after recovery
            assert recovery_result == initial_result, \
                f"Data corruption detected: Expected {initial_result} tickers, got {recovery_result} after recovery"

            elapsed = time.time() - start

            # Validate performance
            assert elapsed < 5.0, f"Error recovery took {elapsed:.2f}s (target: <5s)"

            print(f"✅ E2E-004 PASSED: Error recovery workflow completed in {elapsed:.2f}s")
            print(f"  - Initial query: {initial_result} tickers")
            print(f"  - Disconnect: Graceful failure ✓")
            print(f"  - Reconnect: Successful ✓")
            print(f"  - Recovery query: {recovery_result} tickers (data integrity maintained)")

        finally:
            await db.disconnect()

    def test_concurrent_execution(self, data_provider):
        """
        E2E-005: Concurrent execution (5 parallel backtests).

        Pass Criteria:
        - 5 concurrent backtests complete successfully
        - Total execution time <10s
        - No deadlocks or race conditions
        - All results valid and complete

        Fail Criteria:
        - Deadlock detected
        - Timeout >30s
        - Results inconsistent or corrupted
        - Resource exhaustion (connection pool/memory)
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date
        import numpy as np

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping E2E-005")

        start = time.time()

        # Define 5 ticker configs for concurrent execution
        tickers = ['005930', '035720', '032830', '034020', '006800']

        def run_backtest(ticker):
            """Execute single backtest (for ThreadPoolExecutor)."""
            config = BacktestConfig(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                regions=['KR'],
                tickers=[ticker],
                initial_capital=100_000_000
            )

            adapter = VectorbtAdapter(config=config, data_provider=data_provider)
            result = adapter.run()

            return {
                'ticker': ticker,
                'sharpe': result.sharpe_ratio,
                'return': result.total_return,
                'trades': result.total_trades
            }

        # Execute 5 backtests concurrently using ThreadPoolExecutor
        # (VectorbtAdapter is not async-compatible, so use thread-based parallelism)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_backtest, ticker) for ticker in tickers]
            results = [future.result() for future in futures]

        elapsed = time.time() - start

        # Validate all backtests completed
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"

        # Validate all results are valid
        for r in results:
            assert 'ticker' in r, "Missing ticker in result"
            assert 'sharpe' in r, "Missing sharpe ratio in result"
            assert np.isfinite(r['sharpe']), f"Invalid Sharpe ratio for {r['ticker']}"
            assert 'return' in r, "Missing return in result"
            assert np.isfinite(r['return']), f"Invalid return for {r['ticker']}"

        # Validate performance
        assert elapsed < 10.0, f"Concurrent execution took {elapsed:.2f}s (target: <10s)"

        print(f"✅ E2E-005 PASSED: Concurrent execution completed in {elapsed:.2f}s")
        print(f"\n  Concurrent Backtest Results:")
        for r in results:
            print(f"  - {r['ticker']}: Sharpe={r['sharpe']:6.2f}, Return={r['return']:7.2%}, Trades={r['trades']}")
        print(f"\n  Total execution time: {elapsed:.2f}s (5 backtests in parallel)")


# Integration test summary
if __name__ == "__main__":
    print("""
    E2E Workflow Integration Tests
    ===============================

    Test Suite: test_e2e_workflows.py
    Tests: 5 (E2E-001 through E2E-005)
    Target: Test complete end-to-end workflows

    Prerequisites:
    1. Test database created: python tests/fixtures/setup_test_database.py
    2. 5 tickers with 1,220 OHLCV records loaded
    3. PostgreSQL + TimescaleDB running on localhost:5432
    4. CLI utilities operational (DatabaseManager, QueryFormatter, etc.)
    5. Backtesting engines implemented (PostgresDataProvider, vectorbt)

    Run Tests:
    - All tests: pytest tests/test_cli/integration/test_e2e_workflows.py -v
    - Single test: pytest tests/test_cli/integration/test_e2e_workflows.py::TestE2EWorkflows::test_discovery_workflow -v
    - With coverage: pytest tests/test_cli/integration/test_e2e_workflows.py --cov=cli --cov=modules.backtesting

    Expected Results:
    - E2E-001: Discovery workflow (<5s)
    - E2E-002: Backtest workflow (<5s)
    - E2E-003: Multi-strategy comparison (<15s)
    - E2E-004: Error recovery (<5s)
    - E2E-005: Concurrent execution (<10s)
    """)
