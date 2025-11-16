"""
Test Walk-Forward Optimizer

Tests for walk-forward optimization with rolling/anchored windows and
parameter grid search for preventing overfitting.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/optimization/test_walk_forward_optimizer.py -v
"""

import pytest
from datetime import date, timedelta
from pathlib import Path

from modules.backtesting.optimization.walk_forward_optimizer import (
    WalkForwardOptimizer,
    WalkForwardWindow,
    WalkForwardResult
)
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.backtest_engines.vectorbt_adapter import VECTORBT_AVAILABLE


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="class")
def test_db_path():
    """Get test database path."""
    db_path = Path(__file__).parent.parent.parent.parent / 'data' / 'spock_local.db'
    if not db_path.exists():
        pytest.skip(f"Test database not found: {db_path}")
    return str(db_path)


@pytest.fixture
def sample_config():
    """Create sample backtest configuration."""
    return BacktestConfig(
        start_date=date(2024, 10, 10),  # Match available data range
        end_date=date(2025, 10, 20),    # ticker 000100 has 261 days of data
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000100'],  # Changed from 000020 (was orphaned data)
        max_position_size=0.15,
        score_threshold=60.0,
        risk_profile='moderate',
        commission_rate=0.00015,
        slippage_bps=5.0
    )


@pytest.fixture
def data_provider(test_db_path):
    """Create data provider."""
    db_manager = SQLiteDatabaseManager(test_db_path)
    return SQLiteDataProvider(db_manager)


@pytest.fixture
def optimizer(sample_config, data_provider):
    """Create WalkForwardOptimizer instance."""
    return WalkForwardOptimizer(sample_config, data_provider)


def create_rsi_signal_generator(rsi_period=14, oversold=30, overbought=70):
    """Factory function creating RSI signal generators with parameters."""
    def generator(close):
        import pandas as pd
        import pandas_ta as ta

        # Calculate RSI
        rsi = ta.rsi(close, length=rsi_period)

        # Handle NaN values (RSI needs warmup period)
        if rsi is None:
            # Return empty signals if RSI calculation fails
            return pd.Series(False, index=close.index), pd.Series(False, index=close.index)

        # Fill NaN values with neutral RSI=50
        rsi = rsi.fillna(50)

        # Generate signals
        entries = (rsi < oversold)
        exits = (rsi > overbought)

        return entries, exits

    return generator


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestWalkForwardOptimizerBasics:
    """Test basic WalkForwardOptimizer functionality."""

    def test_initialization(self, optimizer):
        """Test WalkForwardOptimizer initialization."""
        assert optimizer.config is not None
        assert optimizer.data_provider is not None
        assert optimizer.runner is not None

    def test_create_windows_rolling(self, optimizer):
        """Test rolling window creation."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=90,
            test_period_days=30,
            anchored=False
        )

        # Should create multiple windows
        assert len(windows) > 0

        # Check window structure
        for window in windows:
            assert isinstance(window, WalkForwardWindow)
            assert window.train_start < window.train_end
            assert window.test_start > window.train_end
            assert window.test_start < window.test_end

    def test_create_windows_anchored(self, optimizer):
        """Test anchored window creation."""
        start = date(2024, 1, 1)
        windows = optimizer.create_windows(
            start_date=start,
            end_date=date(2024, 12, 31),
            train_period_days=90,
            test_period_days=30,
            anchored=True
        )

        # All windows should start from the same date
        for window in windows:
            assert window.train_start == start

    def test_create_windows_custom_step(self, optimizer):
        """Test window creation with custom step size."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=90,
            test_period_days=30,
            step_days=15  # Half of test period
        )

        # Should create more windows with smaller step
        assert len(windows) > 5


# ============================================================================
# Window Creation Tests
# ============================================================================

class TestWindowCreation:
    """Test walk-forward window creation logic."""

    def test_window_ids_sequential(self, optimizer):
        """Test that window IDs are sequential."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=90,
            test_period_days=30
        )

        for i, window in enumerate(windows):
            assert window.window_id == i

    def test_windows_non_overlapping_test_periods(self, optimizer):
        """Test that test periods don't overlap."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=90,
            test_period_days=30
        )

        for i in range(len(windows) - 1):
            # Windows can be adjacent (test_end == next test_start) but not overlapping
            assert windows[i].test_end <= windows[i + 1].test_start

    def test_window_date_constraints(self, optimizer):
        """Test that all windows respect date constraints."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        windows = optimizer.create_windows(
            start_date=start,
            end_date=end,
            train_period_days=90,
            test_period_days=30
        )

        for window in windows:
            assert window.train_start >= start
            assert window.test_end <= end

    def test_short_period_windows(self, optimizer):
        """Test window creation with short time periods."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            train_period_days=30,
            test_period_days=15
        )

        # Should still create valid windows
        assert len(windows) >= 1

        for window in windows:
            train_days = (window.train_end - window.train_start).days
            test_days = (window.test_end - window.test_start).days

            # Allow some tolerance for non-trading days
            assert 28 <= train_days <= 32
            assert 13 <= test_days <= 17


# ============================================================================
# Optimization Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestOptimization:
    """Test walk-forward optimization functionality."""

    def test_optimize_basic(self, optimizer):
        """Test basic optimization with simple parameter grid."""
        param_grid = {
            'rsi_period': [14, 20],
            'oversold': [30, 40]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30,
            metric='sharpe_ratio'
        )

        # Check result structure
        assert isinstance(result, WalkForwardResult)
        assert result.best_params is not None
        assert len(result.all_results) > 0
        assert len(result.windows) > 0

    def test_optimize_result_metrics(self, optimizer):
        """Test that optimization result contains all required metrics."""
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30
        )

        # In-sample performance
        assert 'mean' in result.in_sample_performance
        assert 'std' in result.in_sample_performance
        assert 'min' in result.in_sample_performance
        assert 'max' in result.in_sample_performance

        # Out-of-sample performance
        assert 'mean' in result.out_of_sample_performance
        assert 'std' in result.out_of_sample_performance
        assert 'min' in result.out_of_sample_performance
        assert 'max' in result.out_of_sample_performance

        # Robustness metrics
        assert 0 <= result.robustness_score <= 1
        assert isinstance(result.overfitting_detected, bool)

    def test_parameter_grid_combinations(self, optimizer):
        """Test that all parameter combinations are tested."""
        param_grid = {
            'rsi_period': [10, 14, 20],
            'oversold': [20, 30, 40]
        }

        # Expected: 3 * 3 = 9 combinations
        combinations = optimizer._generate_param_combinations(param_grid)
        assert len(combinations) == 9

        # Check all combinations present
        rsi_periods = set()
        oversold_values = set()

        for combo in combinations:
            rsi_periods.add(combo['rsi_period'])
            oversold_values.add(combo['oversold'])

        assert rsi_periods == {10, 14, 20}
        assert oversold_values == {20, 30, 40}

    def test_overfitting_detection(self, optimizer):
        """Test overfitting detection logic."""
        # This is a simple test - real overfitting would require
        # carefully crafted scenarios
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30
        )

        # Overfitting detection should complete
        assert isinstance(result.overfitting_detected, bool)
        assert isinstance(result.degradation_pct, (int, float))


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_parameter_optimization(self, optimizer):
        """Test optimization with single parameter."""
        param_grid = {
            'rsi_period': [14]
        }

        combinations = optimizer._generate_param_combinations(param_grid)
        assert len(combinations) == 1
        assert combinations[0] == {'rsi_period': 14}

    def test_insufficient_data_period(self, optimizer):
        """Test behavior with very short data period."""
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            train_period_days=90,
            test_period_days=30
        )

        # Should create no windows when period is too short
        assert len(windows) == 0

    def test_window_boundary_conditions(self, optimizer):
        """Test window creation at exact boundary conditions."""
        # Exactly enough for 1 window
        windows = optimizer.create_windows(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 5, 1),  # 121 days
            train_period_days=90,
            test_period_days=30
        )

        # Should create exactly 1 window
        assert len(windows) == 1


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestIntegration:
    """Integration tests with real backtesting."""

    def test_end_to_end_rolling_optimization(self, optimizer):
        """Test complete rolling optimization workflow."""
        param_grid = {
            'rsi_period': [14, 20],
            'oversold': [30]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30,
            metric='sharpe_ratio',
            anchored=False
        )

        # Validate complete result
        assert result.best_params in [
            {'rsi_period': 14, 'oversold': 30},
            {'rsi_period': 20, 'oversold': 30}
        ]

        assert len(result.all_results) == len(result.windows)

        # Each window should have results
        for window_result in result.all_results:
            assert 'train_score' in window_result
            assert 'test_score' in window_result
            assert 'degradation' in window_result

    def test_end_to_end_anchored_optimization(self, optimizer):
        """Test complete anchored optimization workflow."""
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30,
            metric='total_return',
            anchored=True
        )

        # All windows should have same train_start
        train_starts = [w.train_start for w in result.windows]
        assert len(set(train_starts)) == 1

    def test_robustness_score_calculation(self, optimizer):
        """Test robustness score is calculated correctly."""
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        result = optimizer.optimize(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid,
            train_period_days=90,
            test_period_days=30
        )

        # Robustness should be between 0 and 1
        assert 0 <= result.robustness_score <= 1

        # If overfitting detected, robustness should be low
        if result.overfitting_detected:
            assert result.robustness_score < 0.5 or result.degradation_pct > 0.2
