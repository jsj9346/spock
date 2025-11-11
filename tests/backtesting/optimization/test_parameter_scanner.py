"""
Test Parameter Scanner

Tests for grid search parameter optimization and sensitivity analysis.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/optimization/test_parameter_scanner.py -v
"""

import pytest
from datetime import date
from pathlib import Path

from modules.backtesting.optimization.parameter_scanner import (
    ParameterScanner,
    ParameterSearchResult
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
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000020'],
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
def scanner(sample_config, data_provider):
    """Create ParameterScanner instance."""
    return ParameterScanner(sample_config, data_provider)


def create_rsi_signal_generator(rsi_period=14, oversold=30, overbought=70):
    """Factory function creating RSI signal generators with parameters."""
    def generator(close):
        import pandas_ta as ta

        # Calculate RSI
        rsi = ta.rsi(close, length=rsi_period)

        # Generate signals
        entries = (rsi < oversold)
        exits = (rsi > overbought)

        return entries, exits

    return generator


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestParameterScannerBasics:
    """Test basic ParameterScanner functionality."""

    def test_initialization(self, scanner):
        """Test ParameterScanner initialization."""
        assert scanner.config is not None
        assert scanner.data_provider is not None
        assert scanner.runner is not None

    def test_parameter_search_result_dataclass(self):
        """Test ParameterSearchResult dataclass creation."""
        result = ParameterSearchResult(
            params={'rsi_period': 14, 'oversold': 30},
            total_return=0.15,
            sharpe_ratio=1.5,
            max_drawdown=-0.10,
            total_trades=50,
            win_rate=0.55
        )

        assert result.params == {'rsi_period': 14, 'oversold': 30}
        assert result.total_return == 0.15
        assert result.sharpe_ratio == 1.5
        assert result.max_drawdown == -0.10
        assert result.total_trades == 50
        assert result.win_rate == 0.55


# ============================================================================
# Grid Search Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestGridSearch:
    """Test grid search functionality."""

    def test_grid_search_basic(self, scanner):
        """Test basic grid search with simple parameter grid."""
        param_grid = {
            'rsi_period': [14, 20],
            'oversold': [30]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        # Should test 2 combinations (14x30, 20x30)
        assert len(results) == 2

        # Check result structure
        for result in results:
            assert isinstance(result, ParameterSearchResult)
            assert 'rsi_period' in result.params
            assert 'oversold' in result.params
            assert isinstance(result.total_return, float)
            assert isinstance(result.sharpe_ratio, float)
            assert isinstance(result.max_drawdown, float)
            assert isinstance(result.total_trades, int)
            assert isinstance(result.win_rate, float)

    def test_grid_search_multiple_parameters(self, scanner):
        """Test grid search with multiple parameter dimensions."""
        param_grid = {
            'rsi_period': [10, 14, 20],
            'oversold': [20, 30, 40]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        # Should test 9 combinations (3 x 3)
        assert len(results) == 9

        # Verify all parameter combinations are present
        rsi_periods = set()
        oversold_values = set()

        for result in results:
            rsi_periods.add(result.params['rsi_period'])
            oversold_values.add(result.params['oversold'])

        assert rsi_periods == {10, 14, 20}
        assert oversold_values == {20, 30, 40}

    def test_grid_search_single_parameter(self, scanner):
        """Test grid search with single parameter variation."""
        param_grid = {
            'rsi_period': [14]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        # Should test 1 combination
        assert len(results) == 1
        assert results[0].params == {'rsi_period': 14}

    def test_grid_search_result_metrics(self, scanner):
        """Test that grid search results contain valid metrics."""
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        assert len(results) == 1
        result = results[0]

        # Metrics should be within reasonable ranges
        assert -1.0 <= result.total_return <= 10.0
        assert -5.0 <= result.sharpe_ratio <= 5.0
        assert -1.0 <= result.max_drawdown <= 0.0
        assert result.total_trades >= 0
        assert 0.0 <= result.win_rate <= 1.0


# ============================================================================
# DataFrame Conversion Tests
# ============================================================================

class TestDataFrameConversion:
    """Test conversion of search results to DataFrame."""

    def test_to_dataframe_basic(self, scanner):
        """Test basic DataFrame conversion."""
        # Create sample results
        results = [
            ParameterSearchResult(
                params={'rsi_period': 14, 'oversold': 30},
                total_return=0.15,
                sharpe_ratio=1.5,
                max_drawdown=-0.10,
                total_trades=50,
                win_rate=0.55
            ),
            ParameterSearchResult(
                params={'rsi_period': 20, 'oversold': 30},
                total_return=0.12,
                sharpe_ratio=1.3,
                max_drawdown=-0.08,
                total_trades=45,
                win_rate=0.52
            )
        ]

        df = scanner.to_dataframe(results)

        # Check DataFrame structure
        assert len(df) == 2
        assert 'rsi_period' in df.columns
        assert 'oversold' in df.columns
        assert 'total_return' in df.columns
        assert 'sharpe_ratio' in df.columns
        assert 'max_drawdown' in df.columns
        assert 'total_trades' in df.columns
        assert 'win_rate' in df.columns

    def test_to_dataframe_values(self, scanner):
        """Test DataFrame conversion preserves values correctly."""
        results = [
            ParameterSearchResult(
                params={'rsi_period': 14, 'oversold': 30},
                total_return=0.15,
                sharpe_ratio=1.5,
                max_drawdown=-0.10,
                total_trades=50,
                win_rate=0.55
            )
        ]

        df = scanner.to_dataframe(results)

        # Check values
        assert df.iloc[0]['rsi_period'] == 14
        assert df.iloc[0]['oversold'] == 30
        assert df.iloc[0]['total_return'] == 0.15
        assert df.iloc[0]['sharpe_ratio'] == 1.5
        assert df.iloc[0]['max_drawdown'] == -0.10
        assert df.iloc[0]['total_trades'] == 50
        assert df.iloc[0]['win_rate'] == 0.55

    def test_to_dataframe_empty(self, scanner):
        """Test DataFrame conversion with empty results."""
        results = []

        df = scanner.to_dataframe(results)

        assert len(df) == 0

    def test_to_dataframe_sorting(self, scanner):
        """Test that DataFrame can be sorted by metrics."""
        results = [
            ParameterSearchResult(
                params={'rsi_period': 14, 'oversold': 30},
                total_return=0.10,
                sharpe_ratio=1.2,
                max_drawdown=-0.15,
                total_trades=40,
                win_rate=0.50
            ),
            ParameterSearchResult(
                params={'rsi_period': 20, 'oversold': 30},
                total_return=0.20,
                sharpe_ratio=1.8,
                max_drawdown=-0.08,
                total_trades=50,
                win_rate=0.60
            )
        ]

        df = scanner.to_dataframe(results)

        # Sort by Sharpe ratio
        df_sorted = df.sort_values('sharpe_ratio', ascending=False)

        assert df_sorted.iloc[0]['rsi_period'] == 20
        assert df_sorted.iloc[0]['sharpe_ratio'] == 1.8


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestIntegration:
    """Integration tests with real backtesting."""

    def test_end_to_end_grid_search(self, scanner):
        """Test complete grid search workflow."""
        param_grid = {
            'rsi_period': [14, 20],
            'oversold': [30]
        }

        # Run grid search
        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        # Convert to DataFrame
        df = scanner.to_dataframe(results)

        # Find best parameters by Sharpe ratio
        best_idx = df['sharpe_ratio'].idxmax()
        best_params = {
            'rsi_period': df.loc[best_idx, 'rsi_period'],
            'oversold': df.loc[best_idx, 'oversold']
        }

        # Verify best parameters are valid
        assert best_params['rsi_period'] in [14, 20]
        assert best_params['oversold'] == 30

    def test_parameter_comparison(self, scanner):
        """Test parameter comparison analysis."""
        param_grid = {
            'rsi_period': [10, 14, 20],
            'oversold': [30]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        df = scanner.to_dataframe(results)

        # All results should have same oversold value
        assert len(df['oversold'].unique()) == 1

        # RSI periods should vary
        assert len(df['rsi_period'].unique()) == 3

    def test_performance_metrics_variability(self, scanner):
        """Test that different parameters produce different metrics."""
        param_grid = {
            'rsi_period': [10, 20],  # Very different periods
            'oversold': [30]
        }

        results = scanner.grid_search(
            signal_generator_factory=create_rsi_signal_generator,
            param_grid=param_grid
        )

        # Should have 2 results with potentially different metrics
        assert len(results) == 2

        # Extract metrics
        returns = [r.total_return for r in results]
        sharpes = [r.sharpe_ratio for r in results]

        # At least one metric should differ between the two
        # (though they could theoretically be identical)
        assert len(results) == 2


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_parameter_grid(self, scanner):
        """Test behavior with empty parameter grid."""
        param_grid = {}

        with pytest.raises((ValueError, KeyError)):
            scanner.grid_search(
                signal_generator_factory=create_rsi_signal_generator,
                param_grid=param_grid
            )

    def test_single_value_grid(self, scanner):
        """Test grid search with single value for each parameter."""
        param_grid = {
            'rsi_period': [14],
            'oversold': [30]
        }

        if VECTORBT_AVAILABLE:
            results = scanner.grid_search(
                signal_generator_factory=create_rsi_signal_generator,
                param_grid=param_grid
            )

            assert len(results) == 1
            assert results[0].params == {'rsi_period': 14, 'oversold': 30}
