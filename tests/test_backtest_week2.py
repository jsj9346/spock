"""
Week 2 Backtesting Module Tests

Tests for StrategyRunner integration:
  - StrategyRunner initialization
  - Buy signal generation
  - LayeredScoringEngine integration
  - KellyCalculator integration
  - Pattern detection from scoring results
  - BacktestEngine integration with StrategyRunner
"""

import unittest
from datetime import date
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backtesting import (
    BacktestConfig,
    BacktestEngine,
    StrategyRunner,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestStrategyRunner(unittest.TestCase):
    """Test StrategyRunner initialization and signal generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()
        self.config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 1, 31),
            regions=["KR"],
            tickers=["005930"],  # Samsung Electronics
            initial_capital=100_000_000,
            score_threshold=70,
        )

    def test_strategy_runner_initialization(self):
        """Test StrategyRunner initialization."""
        strategy_runner = StrategyRunner(self.config, self.db)

        # Check attributes
        self.assertIsNotNone(strategy_runner.scoring_engine)
        self.assertIsNotNone(strategy_runner.kelly_calculator)
        self.assertEqual(strategy_runner.config, self.config)
        self.assertEqual(strategy_runner.db, self.db)

    def test_get_atr(self):
        """Test ATR retrieval from database."""
        strategy_runner = StrategyRunner(self.config, self.db)

        # Test with non-existent ticker (should return None gracefully)
        atr = strategy_runner._get_atr("NONEXISTENT", date(2023, 1, 1))
        self.assertIsNone(atr)

    def test_get_sector(self):
        """Test sector retrieval from database."""
        strategy_runner = StrategyRunner(self.config, self.db)

        # Test with non-existent ticker (should return None gracefully)
        sector = strategy_runner._get_sector("NONEXISTENT")
        self.assertIsNone(sector)

    def test_pattern_detection_logic(self):
        """Test pattern detection from scoring results."""
        from modules.backtesting.strategy_runner import StrategyRunner
        from modules.kelly_calculator import PatternType

        strategy_runner = StrategyRunner(self.config, self.db)

        # Create mock scoring result
        class MockScoringResult:
            def __init__(self, layer_scores, total_score):
                self.layer_scores = layer_scores
                self.total_score = total_score

        # Test Stage 1→2 transition detection
        result = MockScoringResult(
            layer_scores={"structural": 40, "micro": 28, "macro": 20}, total_score=88
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.STAGE_1_TO_2)

        # Test VCP breakout detection
        result = MockScoringResult(
            layer_scores={"structural": 30, "micro": 25, "macro": 20}, total_score=85
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.VCP_BREAKOUT)

        # Test Cup & Handle detection
        result = MockScoringResult(
            layer_scores={"structural": 28, "micro": 22, "macro": 18}, total_score=75
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.CUP_HANDLE)

        # Test 60-day high breakout
        result = MockScoringResult(
            layer_scores={"structural": 25, "micro": 15, "macro": 22}, total_score=70
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.HIGH_60D_BREAKOUT)

        # Test Stage 2 continuation
        result = MockScoringResult(
            layer_scores={"structural": 22, "micro": 12, "macro": 15}, total_score=65
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.STAGE_2_CONTINUATION)

        # Test MA200 breakout (fallback)
        result = MockScoringResult(
            layer_scores={"structural": 15, "micro": 8, "macro": 10}, total_score=50
        )
        pattern = strategy_runner._detect_pattern_from_score(result)
        self.assertEqual(pattern, PatternType.MA200_BREAKOUT)


class TestBacktestEngineWithStrategyRunner(unittest.TestCase):
    """Test BacktestEngine integration with StrategyRunner."""

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

    def test_backtest_engine_with_strategy_runner(self):
        """Test BacktestEngine initialization with StrategyRunner."""
        engine = BacktestEngine(self.config, self.db)

        # Check StrategyRunner is initialized
        self.assertIsNotNone(engine.strategy_runner)
        self.assertIsInstance(engine.strategy_runner, StrategyRunner)

    def test_strategy_runner_in_backtest_loop(self):
        """Test StrategyRunner integration in backtest loop."""
        # Note: This is a smoke test - full integration test would require
        # real market data in database
        engine = BacktestEngine(self.config, self.db)

        # Check components are initialized
        self.assertIsNotNone(engine.data_provider)
        self.assertIsNotNone(engine.portfolio)
        self.assertIsNotNone(engine.strategy_runner)


class TestRiskProfileIntegration(unittest.TestCase):
    """Test risk profile integration between BacktestConfig and KellyCalculator."""

    def test_conservative_risk_profile(self):
        """Test conservative risk profile."""
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="conservative",
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        # Check KellyCalculator risk level
        from modules.kelly_calculator import RiskLevel

        self.assertEqual(
            strategy_runner.kelly_calculator.risk_level, RiskLevel.CONSERVATIVE
        )

    def test_moderate_risk_profile(self):
        """Test moderate risk profile."""
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="moderate",
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        from modules.kelly_calculator import RiskLevel

        self.assertEqual(
            strategy_runner.kelly_calculator.risk_level, RiskLevel.MODERATE
        )

    def test_aggressive_risk_profile(self):
        """Test aggressive risk profile."""
        config = BacktestConfig.from_risk_profile(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            risk_profile="aggressive",
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        from modules.kelly_calculator import RiskLevel

        self.assertEqual(
            strategy_runner.kelly_calculator.risk_level, RiskLevel.AGGRESSIVE
        )


class TestScoreThresholdFiltering(unittest.TestCase):
    """Test score threshold filtering in StrategyRunner."""

    def test_score_threshold_conservative(self):
        """Test conservative score threshold (75)."""
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            score_threshold=75,  # Conservative: higher threshold
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        self.assertEqual(strategy_runner.config.score_threshold, 75)

    def test_score_threshold_moderate(self):
        """Test moderate score threshold (70, default)."""
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        self.assertEqual(strategy_runner.config.score_threshold, 70)

    def test_score_threshold_aggressive(self):
        """Test aggressive score threshold (65)."""
        config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            score_threshold=65,  # Aggressive: lower threshold
        )

        db = SQLiteDatabaseManager()
        strategy_runner = StrategyRunner(config, db)

        self.assertEqual(strategy_runner.config.score_threshold, 65)


if __name__ == "__main__":
    print("Running Week 2 Backtesting Module Tests...")
    print("=" * 80)
    unittest.main(verbosity=2)
