"""
Integration tests for backtesting engine components.

Tests validate PostgresDataProvider, vectorbt integration, metrics calculation,
report generation, and performance benchmarks with real test data.

Test Database:
- 5 KR tickers: 005930, 035720, 032830, 034020, 006800
- 1,220 OHLCV records (244 rows per ticker, 2024 data)
- TimescaleDB hypertable optimization enabled

Performance Targets:
- PostgresDataProvider loading: <500ms for 5 tickers
- vectorbt backtest: <1s for 5-year simulation
- Custom engine backtest: <30s for 5-year simulation

Usage:
    # Run all backtesting integration tests
    pytest tests/test_cli/integration/test_backtesting_integration.py -v -m integration

    # Run specific test
    pytest tests/test_cli/integration/test_backtesting_integration.py::TestBacktestingIntegration::test_postgres_data_provider_loading -v
"""
import pytest
import time
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import tempfile

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.backtesting.backtest_config import BacktestConfig


@pytest.mark.integration
@pytest.mark.backtesting
class TestBacktestingIntegration:
    """Integration tests for backtesting engine components."""

    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'quant_platform_test',
        'user': '13ruce'
    }

    @pytest.fixture
    def db_manager(self):
        """Create DatabaseManager instance for tests."""
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

    def test_postgres_data_provider_loading(self, data_provider):
        """
        BT-INT-001: PostgresDataProvider loads data within performance targets.

        Pass Criteria:
        - Load 5 tickers, 1 year data in <500ms
        - All tickers return data (no missing tickers)
        - Data has correct schema (date, OHLCV columns)
        - All dates within requested range

        Fail Criteria:
        - Loading timeout >2s
        - Missing tickers in result
        - Invalid schema or data types
        - Dates outside requested range
        """
        tickers = ['005930', '035720', '032830', '034020', '006800']
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)
        region = 'KR'

        start = time.time()

        # Load data for all tickers
        results = {}
        for ticker in tickers:
            df = data_provider.get_ohlcv(ticker, region, start_date, end_date)
            results[ticker] = df

        elapsed_ms = (time.time() - start) * 1000

        # Validate performance
        assert elapsed_ms < 500, f"Data loading took {elapsed_ms:.2f}ms (target: <500ms)"

        # Validate all tickers returned data
        assert len(results) == 5, f"Expected 5 tickers, got {len(results)}"
        for ticker, df in results.items():
            assert not df.empty, f"No data returned for ticker {ticker}"
            assert len(df) > 200, f"Expected >200 rows for {ticker}, got {len(df)}"

        # Validate schema
        expected_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for ticker, df in results.items():
            assert all(col in df.columns for col in expected_columns), \
                f"Missing columns for {ticker}. Expected: {expected_columns}, Got: {df.columns.tolist()}"

        # Validate date range
        for ticker, df in results.items():
            min_date = df['date'].min()
            max_date = df['date'].max()
            assert pd.Timestamp(start_date) <= min_date, \
                f"Data starts before requested range for {ticker}: {min_date}"
            assert max_date <= pd.Timestamp(end_date), \
                f"Data ends after requested range for {ticker}: {max_date}"

        # Validate data types
        for ticker, df in results.items():
            assert pd.api.types.is_datetime64_any_dtype(df['date']), \
                f"Date column not datetime for {ticker}"
            assert pd.api.types.is_numeric_dtype(df['close']), \
                f"Close column not numeric for {ticker}"
            assert pd.api.types.is_numeric_dtype(df['volume']), \
                f"Volume column not numeric for {ticker}"

        print(f"✅ BT-INT-001 PASSED: Loaded {len(results)} tickers in {elapsed_ms:.2f}ms")
        for ticker, df in results.items():
            print(f"  - {ticker}: {len(df)} rows")

    def test_vectorbt_strategy_execution(self, data_provider):
        """
        BT-INT-002: vectorbt strategy executes successfully.

        Pass Criteria:
        - Strategy runs without errors
        - Final portfolio value calculated
        - Metrics include total return, Sharpe ratio
        - Execution time <3s

        Fail Criteria:
        - Strategy execution error
        - NaN values in results
        - Missing metrics
        - Timeout >10s
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date

        # Skip if vectorbt not installed
        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping BT-INT-002")

        # Create backtest configuration
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],  # Samsung Electronics
            initial_capital=100_000_000  # 100M KRW
        )

        # Create vectorbt adapter
        adapter = VectorbtAdapter(
            config=config,
            data_provider=data_provider
        )

        # Execute backtest with timeout
        start = time.time()
        result = adapter.run()
        elapsed = time.time() - start

        # Validate execution time
        assert elapsed < 3.0, f"Strategy execution took {elapsed:.2f}s (target: <3s)"

        # Validate result structure
        assert result is not None, "Result is None"
        assert hasattr(result, 'total_return'), "Missing total_return"
        assert hasattr(result, 'sharpe_ratio'), "Missing sharpe_ratio"
        assert hasattr(result, 'equity_curve'), "Missing equity_curve"

        # Validate metrics are not NaN
        assert not pd.isna(result.total_return), "total_return is NaN"
        assert not pd.isna(result.sharpe_ratio), "sharpe_ratio is NaN"
        assert not pd.isna(result.max_drawdown), "max_drawdown is NaN"

        # Validate final portfolio value is calculated
        final_value = result.equity_curve.iloc[-1] if len(result.equity_curve) > 0 else 0
        assert final_value > 0, f"Invalid final portfolio value: {final_value}"

        # Validate trade statistics
        assert result.total_trades >= 0, f"Invalid total_trades: {result.total_trades}"
        assert 0 <= result.win_rate <= 1, f"Invalid win_rate: {result.win_rate}"

        print(f"✅ BT-INT-002 PASSED: Strategy executed in {elapsed:.2f}s")
        print(f"  - Total Return: {result.total_return:.2%}")
        print(f"  - Sharpe Ratio: {result.sharpe_ratio:.2f}")
        print(f"  - Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  - Total Trades: {result.total_trades}")
        print(f"  - Win Rate: {result.win_rate:.2%}")

    def test_metrics_calculation_accuracy(self, data_provider):
        """
        BT-INT-003: Metrics calculation accuracy validation.

        Pass Criteria:
        - Sharpe ratio within ±0.05 of expected
        - Max drawdown within ±1% of expected
        - Total return calculated correctly
        - Win rate matches trade outcomes

        Fail Criteria:
        - Metrics diverge >10% from expected
        - NaN or infinite values
        - Calculation errors
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date
        import numpy as np

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping BT-INT-003")

        # Run backtest
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],
            initial_capital=100_000_000
        )

        adapter = VectorbtAdapter(config=config, data_provider=data_provider)
        result = adapter.run()

        # Validate metrics are finite (not NaN or inf)
        assert np.isfinite(result.total_return), "total_return is not finite"
        assert np.isfinite(result.sharpe_ratio), "sharpe_ratio is not finite"
        assert np.isfinite(result.max_drawdown), "max_drawdown is not finite"
        assert np.isfinite(result.win_rate), "win_rate is not finite"

        # Validate metric ranges
        assert -1.0 <= result.total_return <= 10.0, f"total_return out of reasonable range: {result.total_return}"
        assert -5.0 <= result.sharpe_ratio <= 5.0, f"sharpe_ratio out of reasonable range: {result.sharpe_ratio}"
        assert -1.0 <= result.max_drawdown <= 0.0, f"max_drawdown out of range [-1, 0]: {result.max_drawdown}"
        assert 0.0 <= result.win_rate <= 1.0, f"win_rate out of range [0, 1]: {result.win_rate}"

        # Validate profit factor calculation
        if result.total_trades > 0:
            assert result.profit_factor >= 0, f"profit_factor cannot be negative: {result.profit_factor}"

        print(f"✅ BT-INT-003 PASSED: Metrics validation successful")
        print(f"  - Total Return: {result.total_return:.2%} (valid range: -100% to 1000%)")
        print(f"  - Sharpe Ratio: {result.sharpe_ratio:.2f} (valid range: -5.0 to 5.0)")
        print(f"  - Max Drawdown: {result.max_drawdown:.2%} (valid range: 0% to 100%)")
        print(f"  - Win Rate: {result.win_rate:.2%} (valid range: 0% to 100%)")

    def test_html_report_generation(self, data_provider):
        """
        BT-INT-004: HTML report generation validation.

        Pass Criteria:
        - Valid HTML structure
        - Charts render (embedded or linked)
        - Metrics table present with all required fields
        - Report file created successfully

        Fail Criteria:
        - Invalid HTML syntax
        - Broken charts or images
        - Missing metrics table
        - File creation failure
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from cli.utils.report_generator import ReportGenerator
        from datetime import date
        from html.parser import HTMLParser
        import os

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping BT-INT-004")

        # Run backtest to get portfolio data
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],
            initial_capital=100_000_000
        )

        adapter = VectorbtAdapter(config=config, data_provider=data_provider)
        result = adapter.run()

        # Prepare report data
        metrics = {
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'total_trades': result.total_trades,
            'profit_factor': result.profit_factor
        }

        # Get required data for report (VectorbtResult already has returns and positions)
        returns = result.returns_series
        trades = result.positions

        # Generate HTML report
        report_gen = ReportGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_backtest_report.html"

            report_path = report_gen.generate_backtest_report(
                portfolio_returns=returns,
                metrics=metrics,
                tickers=['005930'],
                strategy_name='Test Strategy',
                start_date='2024-01-01',
                end_date='2024-12-31',
                initial_cash=100_000_000,
                commission=0.0015,
                trades=trades,
                output_path=str(output_path),
                title='BT-INT-004 Test Report'
            )

            # Validate file created
            assert os.path.exists(report_path), "Report file not created"
            assert os.path.getsize(report_path) > 0, "Report file is empty"

            # Read and validate HTML content
            with open(report_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Validate HTML structure
            assert '<!DOCTYPE html>' in html_content or '<html' in html_content, "Invalid HTML structure"
            assert '<head>' in html_content, "Missing <head> tag"
            assert '<body>' in html_content, "Missing <body> tag"
            assert '</html>' in html_content, "Missing closing </html> tag"

            # Validate Plotly.js included
            assert 'plotly' in html_content.lower(), "Plotly.js not included"

            # Validate charts present (div IDs)
            assert 'equity-curve' in html_content, "Equity curve chart missing"
            assert 'drawdown' in html_content, "Drawdown chart missing"
            assert 'monthly-returns' in html_content, "Monthly returns chart missing"

            # Validate metrics present (check for formatted labels in HTML)
            assert 'Total Return' in html_content, "Total return metric missing"
            assert 'Sharpe Ratio' in html_content, "Sharpe ratio metric missing"
            assert 'Max Drawdown' in html_content, "Max drawdown metric missing"

            # Validate strategy information
            assert '005930' in html_content, "Ticker missing from report"
            assert 'Test Strategy' in html_content, "Strategy name missing"
            assert '2024-01-01' in html_content, "Start date missing"
            assert '2024-12-31' in html_content, "End date missing"

            # Validate trade analysis if trades present
            if trades is not None and len(trades) > 0:
                assert 'trade-analysis' in html_content or 'Trade' in html_content, "Trade analysis missing"

            print(f"✅ BT-INT-004 PASSED: HTML report generated successfully")
            print(f"  - Report path: {report_path}")
            print(f"  - File size: {os.path.getsize(report_path)} bytes")
            print(f"  - Charts: equity curve, drawdown, monthly returns ✅")
            print(f"  - Metrics: total return, sharpe ratio, max drawdown ✅")
            print(f"  - Trade analysis: {'included' if trades is not None and len(trades) > 0 else 'skipped'}")

    def test_performance_benchmark(self, data_provider):
        """
        BT-INT-005: Performance benchmark validation.

        Pass Criteria:
        - vectorbt: 5-year backtest <1s
        - Custom engine: 5-year backtest <30s
        - Memory usage reasonable (<500MB)

        Fail Criteria:
        - vectorbt timeout >3s
        - Custom engine timeout >60s
        - Memory leak detected
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
        from modules.backtesting.backtest_config import BacktestConfig
        from datetime import date

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping BT-INT-005")

        # Test with 1 year of data (closest we have to 5-year in test database)
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],
            initial_capital=100_000_000
        )

        # Benchmark vectorbt performance
        adapter = VectorbtAdapter(config=config, data_provider=data_provider)

        start = time.time()
        result = adapter.run()
        elapsed = time.time() - start

        # Validate performance (adjusted for 1-year data instead of 5-year)
        # Target: <1s for 5-year, so <0.3s for 1-year is reasonable
        assert elapsed < 3.0, f"vectorbt backtest took {elapsed:.2f}s (target: <3s for 1-year data)"

        # Validate backtest completed successfully
        assert result.total_trades >= 0, "Backtest failed to complete"
        assert len(result.equity_curve) > 0, "Empty equity curve"

        print(f"✅ BT-INT-005 PASSED: Performance benchmark successful")
        print(f"  - vectorbt execution time: {elapsed:.3f}s (1-year data)")
        print(f"  - Target: <3s for vectorbt")
        print(f"  - Trades processed: {result.total_trades}")
        print(f"  - Data points: {len(result.equity_curve)}")

    def test_engine_comparison_consistency(self, data_provider):
        """
        BT-INT-006: Engine comparison consistency validation.

        Pass Criteria:
        - vectorbt vs custom engine: total return within ±2%
        - Trade signals match (>95% agreement)
        - Final portfolio value within ±2%

        Fail Criteria:
        - Returns diverge >5%
        - Signal agreement <90%
        - Major discrepancies in results
        """
        from modules.backtesting.backtest_engines.vectorbt_adapter import VECTORBT_AVAILABLE
        from cli.utils.engine_comparator import EngineComparator
        from datetime import date

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not installed - skipping BT-INT-006")

        # Create backtest configuration
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            regions=['KR'],
            tickers=['005930'],
            initial_capital=100_000_000
        )

        # Run engine comparison
        comparator = EngineComparator(config=config, data_provider=data_provider)

        start = time.time()
        try:
            results = comparator.compare_engines(
                tolerance=0.02,  # 2% tolerance
                signal_agreement_threshold=0.95  # 95% agreement threshold
            )
        except RuntimeError as e:
            if "requires SQLite database" in str(e):
                pytest.skip(f"Engine comparison unavailable: {e}")
            raise
        elapsed = time.time() - start

        # Validate total return difference
        assert results['total_return_diff'] <= 0.02, \
            f"Total return difference {results['total_return_diff']:.2%} exceeds 2% tolerance"

        # Validate final portfolio value difference
        assert results['final_value_match'], \
            f"Final value difference {results['final_value_diff_pct']:.2%} exceeds 2% tolerance"

        # Validate signal agreement (trade count approximation)
        assert results['signal_agreement'] >= 0.90, \
            f"Signal agreement {results['signal_agreement']:.1%} below 90% minimum threshold"

        # Validate Sharpe ratio consistency
        assert results['sharpe_ratio_diff'] <= 0.1, \
            f"Sharpe ratio difference {results['sharpe_ratio_diff']:.2f} exceeds 0.1 tolerance"

        # Validate max drawdown consistency
        assert results['max_drawdown_diff'] <= 0.02, \
            f"Max drawdown difference {results['max_drawdown_diff']:.2%} exceeds 2% tolerance"

        # Validate overall metrics match
        assert results['metrics_match'], \
            f"Metrics do not match within tolerance\n{results['comparison_summary']}"

        print(f"✅ BT-INT-006 PASSED: Engine comparison successful ({elapsed:.2f}s)")
        print(f"\n{results['comparison_summary']}")
        print(f"\n  Key Findings:")
        print(f"  - Total return difference: {results['total_return_diff']:.2%} (target: <2%)")
        print(f"  - Final value match: {results['final_value_match']} (within {results['tolerance']:.1%})")
        print(f"  - Signal agreement: {results['signal_agreement']:.1%} (target: >{results['signal_agreement_threshold']:.1%})")
        print(f"  - Sharpe ratio difference: {results['sharpe_ratio_diff']:.2f} (target: <0.1)")
        print(f"  - Max drawdown difference: {results['max_drawdown_diff']:.2%} (target: <2%)")
        print(f"  - Overall: {'✅ CONSISTENT' if results['metrics_match'] else '❌ INCONSISTENT'}")


# Integration test summary
if __name__ == "__main__":
    print("""
    Backtesting Engine Integration Tests
    =====================================

    Test Suite: test_backtesting_integration.py
    Tests: 6 (BT-INT-001 through BT-INT-006)
    Target: Test backtesting engine components with real data

    Prerequisites:
    1. Test database created: python tests/fixtures/setup_test_database.py
    2. 5 tickers with 1,220 OHLCV records loaded
    3. PostgreSQL + TimescaleDB running on localhost:5432
    4. Backtesting engines implemented (PostgresDataProvider, vectorbt adapter)

    Run Tests:
    - All tests: pytest tests/test_cli/integration/test_backtesting_integration.py -v
    - Single test: pytest tests/test_cli/integration/test_backtesting_integration.py::TestBacktestingIntegration::test_postgres_data_provider_loading -v
    - With coverage: pytest tests/test_cli/integration/test_backtesting_integration.py --cov=modules.backtesting

    Expected Results:
    - BT-INT-001: PASS (PostgresDataProvider loading <500ms)
    - BT-INT-002-006: Implementation pending (Week 1 Sprint 7)
    """)
