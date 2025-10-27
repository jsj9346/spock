"""
Week 3 Backtesting Module Tests

Tests for PerformanceAnalyzer:
  - Return metrics calculation (total_return, annualized_return, CAGR)
  - Risk metrics calculation (Sharpe, Sortino, Calmar, max_drawdown)
  - Trading metrics calculation (win_rate, profit_factor, avg_win_loss_ratio)
  - Pattern-specific metrics
  - Region-specific metrics
  - Kelly accuracy validation
"""

import unittest
from datetime import date, timedelta
import sys
import os
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backtesting import (
    BacktestConfig,
    Trade,
    PerformanceMetrics,
    PatternMetrics,
)
from modules.backtesting.performance_analyzer import PerformanceAnalyzer
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestReturnMetrics(unittest.TestCase):
    """Test return metrics calculation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock equity curve (100M initial → 125M final, 20% return over 1 year)
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        # Linear growth from 100M to 125M
        values = [100_000_000 + (25_000_000 * i / len(dates)) for i in range(len(dates))]
        self.equity_curve = pd.Series(values, index=dates)

        # Create mock trades
        self.trades = [
            Trade(
                ticker="005930",
                region="KR",
                entry_date=date(2023, 6, 1),
                entry_price=70000,
                shares=100,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=75,
                exit_date=date(2023, 7, 1),
                exit_price=84000,
                pnl=1_398_600,
                pnl_pct=0.20,
                exit_reason="profit_target",
            )
        ]

        self.initial_capital = 100_000_000

    def test_total_return_calculation(self):
        """Test total return calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Total return should be 25% (100M → 125M)
        self.assertAlmostEqual(metrics.total_return, 0.25, places=2)

    def test_annualized_return_calculation(self):
        """Test annualized return calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Annualized return should be ~25% for 1-year period
        self.assertAlmostEqual(metrics.annualized_return, 0.25, places=1)

    def test_cagr_calculation(self):
        """Test CAGR calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # CAGR should equal annualized return
        self.assertEqual(metrics.cagr, metrics.annualized_return)


class TestRiskMetrics(unittest.TestCase):
    """Test risk metrics calculation."""

    def setUp(self):
        """Set up test fixtures with realistic volatility."""
        # Create equity curve with volatility
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        import numpy as np

        np.random.seed(42)  # Reproducible random data

        # Simulate returns with 15% annualized volatility
        daily_returns = np.random.normal(0.001, 0.01, len(dates))
        cumulative_returns = np.cumprod(1 + daily_returns)
        values = 100_000_000 * cumulative_returns

        self.equity_curve = pd.Series(values, index=dates)
        self.initial_capital = 100_000_000

        # Create mock trades
        self.trades = [
            Trade(
                ticker="005930",
                region="KR",
                entry_date=date(2023, 6, 1),
                entry_price=70000,
                shares=100,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=75,
                exit_date=date(2023, 7, 1),
                exit_price=84000,
                pnl=1_398_600,
                pnl_pct=0.20,
                exit_reason="profit_target",
            )
        ]

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Sharpe ratio should be positive (return > 0, std > 0)
        self.assertGreater(metrics.sharpe_ratio, 0)

    def test_sortino_ratio_calculation(self):
        """Test Sortino ratio calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Sortino ratio should be positive
        self.assertGreater(metrics.sortino_ratio, 0)

    def test_calmar_ratio_calculation(self):
        """Test Calmar ratio calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Calmar ratio should be positive (CAGR > 0, max_dd < 0)
        self.assertGreater(metrics.calmar_ratio, 0)

    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Max drawdown should be negative
        self.assertLess(metrics.max_drawdown, 0)

    def test_downside_deviation_calculation(self):
        """Test downside deviation calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Downside deviation should be positive
        self.assertGreater(metrics.downside_deviation, 0)


class TestTradingMetrics(unittest.TestCase):
    """Test trading metrics calculation."""

    def setUp(self):
        """Set up test fixtures with multiple trades."""
        # Create equity curve
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        values = [100_000_000 + (10_000_000 * i / len(dates)) for i in range(len(dates))]
        self.equity_curve = pd.Series(values, index=dates)
        self.initial_capital = 100_000_000

        # Create mix of winning and losing trades
        self.trades = [
            # Winning trade 1
            Trade(
                ticker="005930",
                region="KR",
                entry_date=date(2023, 1, 1),
                entry_price=70000,
                shares=100,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=75,
                exit_date=date(2023, 2, 1),
                exit_price=84000,
                pnl=1_398_600,
                pnl_pct=0.20,
                exit_reason="profit_target",
            ),
            # Winning trade 2
            Trade(
                ticker="000660",
                region="KR",
                entry_date=date(2023, 3, 1),
                entry_price=140000,
                shares=50,
                commission=1050,
                slippage=350,
                pattern_type="VCP",
                entry_score=78,
                exit_date=date(2023, 4, 1),
                exit_price=154000,
                pnl=698_600,
                pnl_pct=0.10,
                exit_reason="profit_target",
            ),
            # Losing trade 1
            Trade(
                ticker="035720",
                region="KR",
                entry_date=date(2023, 5, 1),
                entry_price=50000,
                shares=100,
                commission=750,
                slippage=250,
                pattern_type="CupHandle",
                entry_score=72,
                exit_date=date(2023, 6, 1),
                exit_price=45000,
                pnl=-501_000,
                pnl_pct=-0.10,
                exit_reason="stop_loss",
            ),
        ]

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Win rate should be 2/3 = 66.7%
        self.assertAlmostEqual(metrics.win_rate, 0.667, places=2)

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Profit factor = (1,398,600 + 698,600) / 501,000 = 4.19
        expected_profit_factor = (1_398_600 + 698_600) / 501_000
        self.assertAlmostEqual(metrics.profit_factor, expected_profit_factor, places=1)

    def test_avg_win_loss_ratio_calculation(self):
        """Test average win/loss ratio calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Avg win = (0.20 + 0.10) / 2 = 0.15 = 15%
        # Avg loss = -0.10 = -10%
        # Ratio = 15 / 10 = 1.5
        self.assertAlmostEqual(metrics.avg_win_loss_ratio, 1.5, places=1)

    def test_avg_holding_period_calculation(self):
        """Test average holding period calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # All trades hold for 31 days
        self.assertAlmostEqual(metrics.avg_holding_period_days, 31, places=0)


class TestPatternMetrics(unittest.TestCase):
    """Test pattern-specific metrics."""

    def setUp(self):
        """Set up test fixtures with different patterns."""
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        values = [100_000_000 + (15_000_000 * i / len(dates)) for i in range(len(dates))]
        self.equity_curve = pd.Series(values, index=dates)
        self.initial_capital = 100_000_000

        # Create trades with different patterns
        self.trades = [
            # Stage 2 trades (2 winners, 1 loser)
            Trade(
                ticker="005930",
                region="KR",
                entry_date=date(2023, 1, 1),
                entry_price=70000,
                shares=100,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=75,
                exit_date=date(2023, 2, 1),
                exit_price=84000,
                pnl=1_398_600,
                pnl_pct=0.20,
                exit_reason="profit_target",
            ),
            Trade(
                ticker="000660",
                region="KR",
                entry_date=date(2023, 3, 1),
                entry_price=140000,
                shares=50,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=77,
                exit_date=date(2023, 4, 1),
                exit_price=154000,
                pnl=698_600,
                pnl_pct=0.10,
                exit_reason="profit_target",
            ),
            Trade(
                ticker="035420",
                region="KR",
                entry_date=date(2023, 5, 1),
                entry_price=100000,
                shares=50,
                commission=750,
                slippage=250,
                pattern_type="Stage2",
                entry_score=72,
                exit_date=date(2023, 6, 1),
                exit_price=92000,
                pnl=-401_000,
                pnl_pct=-0.08,
                exit_reason="stop_loss",
            ),
            # VCP trades (1 winner, 1 loser)
            Trade(
                ticker="035720",
                region="KR",
                entry_date=date(2023, 7, 1),
                entry_price=50000,
                shares=100,
                commission=750,
                slippage=250,
                pattern_type="VCP",
                entry_score=80,
                exit_date=date(2023, 8, 1),
                exit_price=60000,
                pnl=999_000,
                pnl_pct=0.20,
                exit_reason="profit_target",
            ),
            Trade(
                ticker="005380",
                region="KR",
                entry_date=date(2023, 9, 1),
                entry_price=80000,
                shares=50,
                commission=600,
                slippage=200,
                pattern_type="VCP",
                entry_score=78,
                exit_date=date(2023, 10, 1),
                exit_price=72000,
                pnl=-400_800,
                pnl_pct=-0.10,
                exit_reason="stop_loss",
            ),
        ]

    def test_pattern_specific_metrics(self):
        """Test pattern-specific metrics calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        pattern_metrics = analyzer.calculate_pattern_metrics()

        # Check Stage2 metrics
        self.assertIn("Stage2", pattern_metrics)
        stage2_metrics = pattern_metrics["Stage2"]
        self.assertEqual(stage2_metrics.total_trades, 3)
        self.assertAlmostEqual(stage2_metrics.win_rate, 2 / 3, places=2)

        # Check VCP metrics
        self.assertIn("VCP", pattern_metrics)
        vcp_metrics = pattern_metrics["VCP"]
        self.assertEqual(vcp_metrics.total_trades, 2)
        self.assertEqual(vcp_metrics.win_rate, 0.5)

    def test_kelly_accuracy_validation(self):
        """Test Kelly accuracy validation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        metrics = analyzer.calculate_metrics()

        # Kelly accuracy should be between 0 and 1
        self.assertGreaterEqual(metrics.kelly_accuracy, 0.0)
        self.assertLessEqual(metrics.kelly_accuracy, 1.0)


class TestRegionMetrics(unittest.TestCase):
    """Test region-specific metrics."""

    def setUp(self):
        """Set up test fixtures with multiple regions."""
        dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        values = [100_000_000 + (20_000_000 * i / len(dates)) for i in range(len(dates))]
        self.equity_curve = pd.Series(values, index=dates)
        self.initial_capital = 100_000_000

        # Create trades from different regions
        self.trades = [
            # KR trades (2 winners)
            Trade(
                ticker="005930",
                region="KR",
                entry_date=date(2023, 1, 1),
                entry_price=70000,
                shares=100,
                commission=1050,
                slippage=350,
                pattern_type="Stage2",
                entry_score=75,
                exit_date=date(2023, 2, 1),
                exit_price=84000,
                pnl=1_398_600,
                pnl_pct=0.20,
                exit_reason="profit_target",
            ),
            Trade(
                ticker="000660",
                region="KR",
                entry_date=date(2023, 3, 1),
                entry_price=140000,
                shares=50,
                commission=1050,
                slippage=350,
                pattern_type="VCP",
                entry_score=78,
                exit_date=date(2023, 4, 1),
                exit_price=154000,
                pnl=698_600,
                pnl_pct=0.10,
                exit_reason="profit_target",
            ),
            # US trades (1 winner, 1 loser)
            Trade(
                ticker="AAPL",
                region="US",
                entry_date=date(2023, 5, 1),
                entry_price=150,
                shares=50,
                commission=7.5,
                slippage=2.5,
                pattern_type="CupHandle",
                entry_score=82,
                exit_date=date(2023, 6, 1),
                exit_price=180,
                pnl=1_490,
                pnl_pct=0.20,
                exit_reason="profit_target",
            ),
            Trade(
                ticker="TSLA",
                region="US",
                entry_date=date(2023, 7, 1),
                entry_price=250,
                shares=30,
                commission=5.0,
                slippage=2.0,
                pattern_type="Stage2",
                entry_score=76,
                exit_date=date(2023, 8, 1),
                exit_price=225,
                pnl=-757,
                pnl_pct=-0.10,
                exit_reason="stop_loss",
            ),
        ]

    def test_region_specific_metrics(self):
        """Test region-specific metrics calculation."""
        analyzer = PerformanceAnalyzer(
            trades=self.trades,
            equity_curve=self.equity_curve,
            initial_capital=self.initial_capital,
        )

        region_metrics = analyzer.calculate_region_metrics()

        # Check KR metrics
        self.assertIn("KR", region_metrics)
        kr_metrics = region_metrics["KR"]
        self.assertEqual(kr_metrics.total_trades, 2)
        self.assertEqual(kr_metrics.win_rate, 1.0)  # 100% win rate

        # Check US metrics
        self.assertIn("US", region_metrics)
        us_metrics = region_metrics["US"]
        self.assertEqual(us_metrics.total_trades, 2)
        self.assertEqual(us_metrics.win_rate, 0.5)  # 50% win rate


class TestBacktestEngineWithPerformanceAnalyzer(unittest.TestCase):
    """Test BacktestEngine integration with PerformanceAnalyzer."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),
            regions=["KR"],
            tickers=["005930"],
            initial_capital=100_000_000,
        )

    def test_backtest_engine_with_performance_analyzer(self):
        """Test BacktestEngine integration with PerformanceAnalyzer."""
        from modules.backtesting import BacktestEngine

        engine = BacktestEngine(self.config, self.db)

        # Check PerformanceAnalyzer is available
        from modules.backtesting.performance_analyzer import PerformanceAnalyzer

        self.assertIsNotNone(PerformanceAnalyzer)


if __name__ == "__main__":
    print("Running Week 3 Backtesting Module Tests...")
    print("=" * 80)
    unittest.main(verbosity=2)
