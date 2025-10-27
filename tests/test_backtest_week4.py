"""
Test Suite for Week 4: BacktestReporter

Purpose: Validate multi-format output generation and reporting functionality.

Test Coverage:
  - Console summary output
  - JSON export/import
  - CSV trade log export
  - HTML report generation
  - Database persistence (backtest_results, backtest_trades, backtest_equity_curve)
  - Config hash deduplication
  - Edge cases (empty results, missing data)

Author: Spock Backtesting Module
"""

import unittest
import os
import json
import csv
import tempfile
import sqlite3
import hashlib
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    PatternMetrics,
    Trade,
)
from modules.backtesting.backtest_reporter import BacktestReporter
import pandas as pd


class TestConsoleOutput(unittest.TestCase):
    """Test console summary output formatting"""

    def setUp(self):
        """Create test backtest result"""
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000_000,  # ₩100M
            regions=['KR'],
            tickers=['005930', '035720'],
        )

        self.metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            cagr=0.25,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            calmar_ratio=1.5,
            max_drawdown=-0.12,
            max_drawdown_duration_days=30,
            std_returns=0.02,
            downside_deviation=0.015,
            total_trades=50,
            win_rate=0.60,
            profit_factor=2.4,
            avg_win_pct=0.12,
            avg_loss_pct=-0.06,
            avg_win_loss_ratio=2.0,
            avg_holding_period_days=15.5,
            kelly_accuracy=0.92,
            alpha=0.05,
            beta=0.85,
            information_ratio=0.75,
        )

        self.trades = [
            Trade(
                ticker='005930',
                region='KR',
                entry_date=date(2023, 1, 10),
                exit_date=date(2023, 1, 25),
                entry_price=60000,
                exit_price=66000,
                shares=100,
                commission=300,
                slippage=100,
                pnl=595600,
                pnl_pct=0.10,
                pattern_type='Stage 1→2',
                entry_score=75,
                exit_reason='profit_target',
                sector='IT',
            ),
            Trade(
                ticker='035720',
                region='KR',
                entry_date=date(2023, 2, 5),
                exit_date=date(2023, 2, 20),
                entry_price=400000,
                exit_price=380000,
                shares=20,
                commission=400,
                slippage=100,
                pnl=-400500,
                pnl_pct=-0.05,
                pattern_type='VCP',
                entry_score=72,
                exit_reason='stop_loss',
                sector='Consumer Discretionary',
            ),
        ]

        self.equity_curve = pd.Series({
            date(2023, 1, 1): 100_000_000,
            date(2023, 1, 15): 102_000_000,
            date(2023, 6, 30): 115_000_000,
            date(2023, 12, 31): 125_000_000,
        })

        self.result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            pattern_metrics={
                'Stage 1→2': PatternMetrics(
                    pattern_type='Stage 1→2',
                    total_trades=30,
                    win_rate=0.65,
                    avg_return=0.08,
                    total_pnl=12_000_000,
                    avg_holding_days=15.0,
                ),
                'VCP': PatternMetrics(
                    pattern_type='VCP',
                    total_trades=20,
                    win_rate=0.55,
                    avg_return=0.05,
                    total_pnl=8_000_000,
                    avg_holding_days=12.0,
                ),
            },
            region_metrics={
                'KR': PerformanceMetrics(
                    total_return=0.25,
                    annualized_return=0.25,
                    cagr=0.25,
                    sharpe_ratio=1.8,
                    sortino_ratio=2.5,
                    calmar_ratio=1.5,
                    max_drawdown=-0.12,
                    max_drawdown_duration_days=30,
                    std_returns=0.02,
                    downside_deviation=0.015,
                    total_trades=50,
                    win_rate=0.60,
                    profit_factor=2.4,
                    avg_win_pct=0.12,
                    avg_loss_pct=-0.06,
                    avg_win_loss_ratio=2.0,
                    avg_holding_period_days=15.5,
                    kelly_accuracy=0.92,
                ),
            },
            execution_time_seconds=125.5,
        )

    def test_console_summary_output(self):
        """Test console summary formatting"""
        reporter = BacktestReporter(self.result)

        # Should not raise any exceptions
        try:
            reporter.print_console_summary()
            success = True
        except Exception as e:
            success = False
            print(f"Console summary failed: {e}")

        self.assertTrue(success, "Console summary should complete without errors")

    def test_console_summary_with_empty_trades(self):
        """Test console summary with no trades"""
        result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=[],
            equity_curve=self.equity_curve,
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=10.0,
        )

        reporter = BacktestReporter(result)

        try:
            reporter.print_console_summary()
            success = True
        except Exception:
            success = False

        self.assertTrue(success, "Should handle empty trades gracefully")


class TestJSONExport(unittest.TestCase):
    """Test JSON export functionality"""

    def setUp(self):
        """Create test backtest result"""
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000_000,
            regions=['KR'],
        )

        self.metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            cagr=0.25,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            calmar_ratio=1.5,
            max_drawdown=-0.12,
            max_drawdown_duration_days=30,
            std_returns=0.02,
            downside_deviation=0.015,
            total_trades=1,
            win_rate=0.60,
            profit_factor=2.4,
            avg_win_pct=0.12,
            avg_loss_pct=-0.06,
            avg_win_loss_ratio=2.0,
            avg_holding_period_days=15.5,
            kelly_accuracy=0.92,
        )

        self.trades = [
            Trade(
                ticker='005930',
                region='KR',
                entry_date=date(2023, 1, 10),
                exit_date=date(2023, 1, 25),
                entry_price=60000,
                exit_price=66000,
                shares=100,
                commission=300,
                slippage=100,
                pnl=595600,
                pnl_pct=0.10,
                pattern_type='Stage 1→2',
                entry_score=75,
                exit_reason='profit_target',
            ),
        ]

        self.equity_curve = pd.Series({
            date(2023, 1, 1): 100_000_000,
            date(2023, 12, 31): 125_000_000,
        })

        self.result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=10.0,
        )

        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_json_export(self):
        """Test JSON export creates valid file"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'backtest_result.json')

        reporter.export_json(filepath)

        # Verify file exists
        self.assertTrue(os.path.exists(filepath), "JSON file should be created")

        # Verify JSON is valid
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.assertIn('config', data)
        self.assertIn('metrics', data)
        self.assertIn('trades', data)
        self.assertIn('equity_curve', data)

    def test_json_export_data_integrity(self):
        """Test JSON export preserves data accuracy"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'backtest_result.json')

        reporter.export_json(filepath)

        with open(filepath, 'r') as f:
            data = json.load(f)

        # Verify config
        self.assertEqual(data['config']['start_date'], '2023-01-01')
        self.assertEqual(data['config']['initial_capital'], 100_000_000)

        # Verify metrics
        self.assertAlmostEqual(data['metrics']['total_return'], 0.25, places=2)
        self.assertAlmostEqual(data['metrics']['sharpe_ratio'], 1.8, places=1)

        # Verify trades
        self.assertEqual(len(data['trades']), 1)
        self.assertEqual(data['trades'][0]['ticker'], '005930')
        self.assertAlmostEqual(data['trades'][0]['pnl_pct'], 0.10, places=2)

    def test_json_export_with_missing_fields(self):
        """Test JSON export handles optional fields gracefully"""
        # Create result with minimal data
        minimal_result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=[],
            equity_curve=pd.Series(),
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=10.0,
        )

        reporter = BacktestReporter(minimal_result)
        filepath = os.path.join(self.temp_dir, 'minimal_result.json')

        reporter.export_json(filepath)

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.assertIsInstance(data['trades'], list)
        self.assertEqual(len(data['trades']), 0)


class TestCSVExport(unittest.TestCase):
    """Test CSV trade log export"""

    def setUp(self):
        """Create test backtest result"""
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000_000,
            regions=['KR'],
        )

        self.metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            cagr=0.25,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            calmar_ratio=1.5,
            max_drawdown=-0.12,
            max_drawdown_duration_days=30,
            std_returns=0.02,
            downside_deviation=0.015,
            total_trades=2,
            win_rate=0.60,
            profit_factor=2.4,
            avg_win_pct=0.12,
            avg_loss_pct=-0.06,
            avg_win_loss_ratio=2.0,
            avg_holding_period_days=15.5,
            kelly_accuracy=0.92,
        )

        self.trades = [
            Trade(
                ticker='005930',
                region='KR',
                entry_date=date(2023, 1, 10),
                exit_date=date(2023, 1, 25),
                entry_price=60000,
                exit_price=66000,
                shares=100,
                commission=300,
                slippage=100,
                pnl=595600,
                pnl_pct=0.10,
                pattern_type='Stage 1→2',
                entry_score=75,
                exit_reason='profit_target',
                sector='IT',
            ),
            Trade(
                ticker='035720',
                region='KR',
                entry_date=date(2023, 2, 5),
                exit_date=date(2023, 2, 20),
                entry_price=400000,
                exit_price=380000,
                shares=20,
                commission=400,
                slippage=100,
                pnl=-400500,
                pnl_pct=-0.05,
                pattern_type='VCP',
                entry_score=72,
                exit_reason='stop_loss',
                sector='Consumer Discretionary',
            ),
        ]

        self.result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=pd.Series(),
            pattern_metrics={},
            execution_time_seconds=10.0,
        )

        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_csv_export(self):
        """Test CSV export creates valid file"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'trades.csv')

        reporter.export_csv_trades(filepath)

        # Verify file exists
        self.assertTrue(os.path.exists(filepath), "CSV file should be created")

        # Read CSV and verify structure
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2, "Should have 2 trade rows")

        # Verify headers
        expected_headers = [
            'ticker', 'region', 'entry_date', 'exit_date',
            'entry_price', 'exit_price', 'shares', 'commission', 'slippage',
            'pnl', 'pnl_pct', 'pattern_type', 'exit_reason',
            'entry_score', 'sector', 'holding_period_days'
        ]

        for header in expected_headers:
            self.assertIn(header, rows[0].keys(), f"Header '{header}' should exist")

    def test_csv_data_integrity(self):
        """Test CSV export preserves trade data accuracy"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'trades.csv')

        reporter.export_csv_trades(filepath)

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Verify first trade
        row = rows[0]
        self.assertEqual(row['ticker'], '005930')
        self.assertEqual(row['region'], 'KR')
        self.assertEqual(float(row['pnl']), 595600)
        self.assertAlmostEqual(float(row['pnl_pct']), 0.10, places=2)
        self.assertEqual(row['pattern_type'], 'Stage 1→2')
        self.assertEqual(row['exit_reason'], 'profit_target')

    def test_csv_with_empty_trades(self):
        """Test CSV export with no trades"""
        result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=[],
            equity_curve=pd.Series(),
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=10.0,
        )

        reporter = BacktestReporter(result)
        filepath = os.path.join(self.temp_dir, 'empty_trades.csv')

        reporter.export_csv_trades(filepath)

        self.assertTrue(os.path.exists(filepath), "CSV file should be created even with no trades")

        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 0, "Should have no data rows")


class TestHTMLReport(unittest.TestCase):
    """Test HTML report generation"""

    def setUp(self):
        """Create test backtest result"""
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000_000,
            regions=['KR'],
        )

        self.metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            cagr=0.25,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            calmar_ratio=1.5,
            max_drawdown=-0.12,
            max_drawdown_duration_days=30,
            std_returns=0.02,
            downside_deviation=0.015,
            total_trades=1,
            win_rate=0.60,
            profit_factor=2.4,
            avg_win_pct=0.12,
            avg_loss_pct=-0.06,
            avg_win_loss_ratio=2.0,
            avg_holding_period_days=15.5,
            kelly_accuracy=0.92,
        )

        self.trades = [
            Trade(
                ticker='005930',
                region='KR',
                entry_date=date(2023, 1, 10),
                exit_date=date(2023, 1, 25),
                entry_price=60000,
                exit_price=66000,
                shares=100,
                commission=300,
                slippage=100,
                pnl=595600,
                pnl_pct=0.10,
                pattern_type='Stage 1→2',
                entry_score=75,
                exit_reason='profit_target',
            ),
        ]

        self.result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=pd.Series(),
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=10.0,
        )

        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_html_report_generation(self):
        """Test HTML report file creation"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'backtest_report.html')

        reporter.generate_html_report(filepath)

        # Verify file exists
        self.assertTrue(os.path.exists(filepath), "HTML file should be created")

        # Verify it's valid HTML
        with open(filepath, 'r') as f:
            content = f.read()

        self.assertIn('<html>', content)
        self.assertIn('</html>', content)
        self.assertIn('<table>', content)  # Should have tables
        self.assertIn('Spock Backtest Report', content)  # Should have title

    def test_html_report_contains_metrics(self):
        """Test HTML report includes performance metrics"""
        reporter = BacktestReporter(self.result)
        filepath = os.path.join(self.temp_dir, 'backtest_report.html')

        reporter.generate_html_report(filepath)

        with open(filepath, 'r') as f:
            content = f.read()

        # Verify key metrics are present
        self.assertIn('25.0%', content)  # total_return
        self.assertIn('1.80', content)   # sharpe_ratio
        self.assertIn('60.0%', content)  # win_rate


class TestDatabasePersistence(unittest.TestCase):
    """Test database save functionality"""

    def setUp(self):
        """Create test database and backtest result"""
        # Create temp database
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_backtest.db')

        # Initialize database
        conn = sqlite3.connect(self.db_path)
        conn.close()

        self.db = SQLiteDatabaseManager(db_path=self.db_path)
        self.db.create_backtest_tables()

        # Create test result
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000_000,
            regions=['KR'],
            tickers=['005930'],
        )

        self.metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            cagr=0.25,
            sharpe_ratio=1.8,
            sortino_ratio=2.5,
            calmar_ratio=1.5,
            max_drawdown=-0.12,
            max_drawdown_duration_days=30,
            std_returns=0.02,
            downside_deviation=0.015,
            total_trades=10,
            win_rate=0.60,
            profit_factor=2.4,
            avg_win_pct=0.12,
            avg_loss_pct=-0.06,
            avg_win_loss_ratio=2.0,
            avg_holding_period_days=15.5,
            kelly_accuracy=0.92,
        )

        self.trades = [
            Trade(
                ticker='005930',
                region='KR',
                entry_date=date(2023, 1, 10),
                exit_date=date(2023, 1, 25),
                entry_price=60000,
                exit_price=66000,
                shares=100,
                commission=300,
                slippage=100,
                pnl=595600,
                pnl_pct=0.10,
                pattern_type='Stage 1→2',
                entry_score=75,
                exit_reason='profit_target',
            ),
        ]

        self.equity_curve = pd.Series({
            date(2023, 1, 1): 100_000_000,
            date(2023, 12, 31): 125_000_000,
        })

        self.result = BacktestResult(
            config=self.config,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=120.0,
        )

    def tearDown(self):
        """Clean up temp files"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_database_save(self):
        """Test saving backtest result to database"""
        reporter = BacktestReporter(self.result)
        backtest_id = reporter.save_to_database(self.db)

        self.assertIsNotNone(backtest_id, "Should return backtest_id")
        self.assertIsInstance(backtest_id, int, "backtest_id should be integer")

        # Verify backtest_results table
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM backtest_results WHERE id = ?", (backtest_id,))
        row = cursor.fetchone()

        self.assertIsNotNone(row, "Backtest result should be saved")
        self.assertEqual(row['start_date'], '2023-01-01')
        self.assertEqual(row['end_date'], '2023-12-31')
        self.assertEqual(row['regions'], '["KR"]')  # Stored as JSON
        self.assertAlmostEqual(row['total_return'], 0.25, places=2)
        self.assertAlmostEqual(row['sharpe_ratio'], 1.8, places=1)
        self.assertEqual(row['total_trades'], 10)

        conn.close()

    def test_database_save_trades(self):
        """Test saving trades to backtest_trades table"""
        reporter = BacktestReporter(self.result)
        backtest_id = reporter.save_to_database(self.db)

        # Verify backtest_trades table
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM backtest_trades WHERE backtest_id = ?", (backtest_id,))
        count = cursor.fetchone()['count']

        self.assertEqual(count, 1, "Should save 1 trade")

        cursor.execute("SELECT * FROM backtest_trades WHERE backtest_id = ?", (backtest_id,))
        trade = cursor.fetchone()

        self.assertEqual(trade['ticker'], '005930')
        self.assertEqual(trade['region'], 'KR')
        self.assertEqual(trade['entry_price'], 60000)
        self.assertEqual(trade['exit_price'], 66000)
        self.assertAlmostEqual(trade['pnl'], 595600, places=0)

        conn.close()

    def test_database_save_equity_curve(self):
        """Test saving equity curve to backtest_equity_curve table"""
        reporter = BacktestReporter(self.result)
        backtest_id = reporter.save_to_database(self.db)

        # Verify backtest_equity_curve table
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM backtest_equity_curve WHERE backtest_id = ?", (backtest_id,))
        count = cursor.fetchone()['count']

        self.assertEqual(count, 2, "Should save 2 equity curve points")

        conn.close()

    def test_config_hash_deduplication(self):
        """Test config hash prevents duplicate backtests"""
        reporter = BacktestReporter(self.result)

        # Save first time
        backtest_id1 = reporter.save_to_database(self.db)

        # Count rows before second save
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM backtest_results")
        count_before = cursor.fetchone()['count']

        # Save again with same config
        backtest_id2 = reporter.save_to_database(self.db)

        # Count rows after second save
        cursor.execute("SELECT COUNT(*) as count FROM backtest_results")
        count_after = cursor.fetchone()['count']
        conn.close()

        # Should not create duplicate rows (UNIQUE constraint causes REPLACE)
        self.assertEqual(count_before, count_after, "Should not create duplicate rows with same config hash")

    def test_config_hash_uniqueness(self):
        """Test different configs have different hashes"""
        reporter1 = BacktestReporter(self.result)

        # Create different config
        config2 = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=200_000_000,  # Different capital
            regions=['KR'],
            tickers=['005930'],
        )

        result2 = BacktestResult(
            config=config2,
            metrics=self.metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            pattern_metrics={},
            region_metrics={},
            execution_time_seconds=120.0,
        )

        reporter2 = BacktestReporter(result2)

        # Save both
        backtest_id1 = reporter1.save_to_database(self.db)
        backtest_id2 = reporter2.save_to_database(self.db)

        # Should have different IDs
        self.assertNotEqual(backtest_id1, backtest_id2, "Different configs should have different IDs")


def run_week4_tests():
    """Run all Week 4 tests"""
    # Create test suite
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestConsoleOutput))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestJSONExport))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCSVExport))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHTMLReport))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDatabasePersistence))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == '__main__':
    result = run_week4_tests()

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
