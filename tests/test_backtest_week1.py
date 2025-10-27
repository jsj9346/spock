"""
Week 1 Backtesting Module Tests

Tests for core backtesting infrastructure:
  - BacktestConfig validation
  - HistoricalDataProvider data loading
  - PortfolioSimulator position tracking
  - BacktestEngine event-driven loop
"""

import unittest
from datetime import date, timedelta
import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backtesting import (
    BacktestConfig,
    Position,
    Trade,
    BacktestEngine,
    HistoricalDataProvider,
    PortfolioSimulator,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestBacktestConfig(unittest.TestCase):
    """Test BacktestConfig dataclass validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            initial_capital=100_000_000,
        )
        self.assertEqual(config.regions, ["KR"])
        self.assertEqual(config.score_threshold, 70)

    def test_invalid_date_range(self):
        """Test invalid date range."""
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=date(2023, 12, 31),
                end_date=date(2023, 1, 1),
            )

    def test_invalid_risk_profile(self):
        """Test invalid risk profile."""
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
                risk_profile="invalid",
            )

    def test_from_risk_profile(self):
        """Test risk profile presets."""
        # Conservative profile
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="conservative",
        )
        self.assertEqual(config.score_threshold, 75)
        self.assertEqual(config.kelly_multiplier, 0.25)
        self.assertEqual(config.max_position_size, 0.10)

        # Moderate profile
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="moderate",
        )
        self.assertEqual(config.score_threshold, 70)
        self.assertEqual(config.kelly_multiplier, 0.5)

        # Aggressive profile
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="aggressive",
        )
        self.assertEqual(config.score_threshold, 65)
        self.assertEqual(config.kelly_multiplier, 0.75)


class TestPosition(unittest.TestCase):
    """Test Position dataclass."""

    def test_position_creation(self):
        """Test position creation."""
        position = Position(
            ticker="005930",
            region="KR",
            entry_date=date(2023, 6, 15),
            entry_price=70000,
            shares=100,
            stop_loss_price=65000,
            profit_target_price=84000,
            pattern_type="Stage2",
            entry_score=75,
        )
        self.assertEqual(position.position_value, 7_000_000)
        self.assertEqual(position.cost_basis, 7_000_000)


class TestTrade(unittest.TestCase):
    """Test Trade dataclass."""

    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            ticker="005930",
            region="KR",
            entry_date=date(2023, 6, 15),
            entry_price=70000,
            shares=100,
            commission=1050,
            slippage=350,
            pattern_type="Stage2",
            entry_score=75,
        )
        self.assertFalse(trade.is_closed)
        self.assertIsNone(trade.holding_period_days)

    def test_trade_close(self):
        """Test trade closing."""
        trade = Trade(
            ticker="005930",
            region="KR",
            entry_date=date(2023, 6, 15),
            entry_price=70000,
            shares=100,
            commission=1050,
            slippage=350,
            pattern_type="Stage2",
            entry_score=75,
        )

        # Close trade with profit
        trade.close(
            exit_date=date(2023, 7, 20),
            exit_price=84000,
            exit_reason="profit_target",
        )

        self.assertTrue(trade.is_closed)
        self.assertEqual(trade.holding_period_days, 35)
        self.assertEqual(trade.pnl, 1_400_000 - 1050 - 350)  # Gross P&L - costs
        self.assertAlmostEqual(trade.pnl_pct, 0.2, places=2)


class TestPortfolioSimulator(unittest.TestCase):
    """Test PortfolioSimulator."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            initial_capital=100_000_000,
        )
        self.portfolio = PortfolioSimulator(self.config)

    def test_initial_state(self):
        """Test initial portfolio state."""
        self.assertEqual(self.portfolio.cash, 100_000_000)
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertEqual(len(self.portfolio.trades), 0)

    def test_buy_order(self):
        """Test buy order execution."""
        trade = self.portfolio.buy(
            ticker="005930",
            region="KR",
            price=70000,
            buy_date=date(2023, 6, 15),
            kelly_fraction=0.3,
            pattern_type="Stage2",
            entry_score=75,
            atr=2000,
        )

        self.assertIsNotNone(trade)
        self.assertEqual(len(self.portfolio.positions), 1)
        self.assertTrue("005930" in self.portfolio.positions)

    def test_sell_order(self):
        """Test sell order execution."""
        # First buy
        self.portfolio.buy(
            ticker="005930",
            region="KR",
            price=70000,
            buy_date=date(2023, 6, 15),
            kelly_fraction=0.3,
            pattern_type="Stage2",
            entry_score=75,
            atr=2000,
        )

        # Then sell
        closed_trade = self.portfolio.sell(
            ticker="005930",
            price=84000,
            sell_date=date(2023, 7, 20),
            exit_reason="profit_target",
        )

        self.assertIsNotNone(closed_trade)
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertTrue(closed_trade.is_closed)

    def test_position_limits(self):
        """Test position size limits."""
        # Try to buy more than max position size
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            initial_capital=100_000_000,
            max_position_size=0.10,  # 10% max
        )
        portfolio = PortfolioSimulator(config)

        # This should cap position at 10M KRW
        trade = portfolio.buy(
            ticker="005930",
            region="KR",
            price=70000,
            buy_date=date(2023, 6, 15),
            kelly_fraction=0.5,  # Would be 25M without cap
            pattern_type="Stage2",
            entry_score=75,
        )

        position = portfolio.positions["005930"]
        position_value = position.shares * 70000
        self.assertLessEqual(position_value, 10_000_000)


class TestHistoricalDataProvider(unittest.TestCase):
    """Test HistoricalDataProvider (requires database)."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()
        self.provider = HistoricalDataProvider(self.db)

    def test_cache_initialization(self):
        """Test cache initialization."""
        self.assertEqual(len(self.provider.data_cache), 0)
        self.assertEqual(len(self.provider.tickers), 0)

    def test_cache_stats(self):
        """Test cache statistics."""
        stats = self.provider.get_cache_stats()
        self.assertIn("tickers_cached", stats)
        self.assertIn("memory_usage_mb", stats)


class TestBacktestEngine(unittest.TestCase):
    """Test BacktestEngine (requires database)."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),  # Short period for testing
            regions=["KR"],
            tickers=["005930"],  # Single ticker for testing
            initial_capital=100_000_000,
        )
        self.engine = BacktestEngine(self.config, self.db)

    def test_engine_initialization(self):
        """Test engine initialization."""
        self.assertIsNotNone(self.engine.data_provider)
        self.assertIsNotNone(self.engine.portfolio)
        self.assertEqual(self.engine.portfolio.cash, 100_000_000)

    def test_trading_days_generation(self):
        """Test trading days generation."""
        trading_days = self.engine._get_trading_days()
        self.assertGreater(len(trading_days), 0)
        # Check weekdays only
        for day in trading_days:
            self.assertLess(day.weekday(), 5)  # Monday-Friday


if __name__ == "__main__":
    print("Running Week 1 Backtesting Module Tests...")
    print("=" * 80)
    unittest.main(verbosity=2)
