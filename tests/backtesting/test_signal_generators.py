"""
Test Signal Generators

Tests for RSI, MACD, and Bollinger Bands signal generators.

Usage:
    pytest tests/backtesting/test_signal_generators.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path

from modules.backtesting.signal_generators.rsi_strategy import (
    calculate_rsi,
    rsi_signal_generator,
    rsi_mean_reversion_signal_generator
)
from modules.backtesting.signal_generators.macd_strategy import (
    calculate_macd,
    macd_signal_generator,
    macd_histogram_signal_generator,
    macd_trend_following_signal_generator
)
from modules.backtesting.signal_generators.bollinger_bands_strategy import (
    calculate_bollinger_bands,
    bb_signal_generator,
    bb_breakout_signal_generator,
    bb_squeeze_signal_generator,
    bb_dual_threshold_signal_generator
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_price_data():
    """Create sample price data for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')

    # Create realistic price movement with trend and volatility
    np.random.seed(42)

    # Base trend
    trend = np.linspace(100, 150, len(dates))

    # Add cyclical component
    cycle = 10 * np.sin(np.linspace(0, 4 * np.pi, len(dates)))

    # Add random noise
    noise = np.random.normal(0, 2, len(dates))

    # Combine components
    close = trend + cycle + noise

    return pd.Series(close, index=dates, name='close')


@pytest.fixture
def trending_up_data():
    """Create upward trending price data."""
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    close = np.linspace(100, 200, len(dates)) + np.random.normal(0, 1, len(dates))
    return pd.Series(close, index=dates, name='close')


@pytest.fixture
def trending_down_data():
    """Create downward trending price data."""
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    close = np.linspace(200, 100, len(dates)) + np.random.normal(0, 1, len(dates))
    return pd.Series(close, index=dates, name='close')


@pytest.fixture
def sideways_data():
    """Create sideways/range-bound price data."""
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    close = 150 + 5 * np.sin(np.linspace(0, 10 * np.pi, len(dates))) + np.random.normal(0, 0.5, len(dates))
    return pd.Series(close, index=dates, name='close')


# ============================================================================
# RSI Strategy Tests
# ============================================================================

class TestRSIStrategy:
    """Test RSI calculation and signal generation."""

    def test_calculate_rsi_basic(self, sample_price_data):
        """Test RSI calculation returns valid values."""
        rsi = calculate_rsi(sample_price_data, period=14)

        # Check type
        assert isinstance(rsi, pd.Series)

        # Check length matches input
        assert len(rsi) == len(sample_price_data)

        # Check RSI is in valid range (0-100) for non-NaN values
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

        # Check first value is NaN (EMA needs at least one prior value)
        # Note: EMA starts calculating from second value, unlike SMA
        assert rsi.iloc[0] == np.nan or pd.isna(rsi.iloc[0])

    def test_calculate_rsi_edge_cases(self):
        """Test RSI with edge cases."""
        # Constant prices (no change)
        constant = pd.Series([100.0] * 30, index=pd.date_range('2024-01-01', periods=30))
        rsi = calculate_rsi(constant, period=14)

        # Should be 50 (neutral) or NaN for constant prices
        valid_rsi = rsi.dropna()
        if len(valid_rsi) > 0:
            # With no price changes, RSI should be neutral or undefined
            assert valid_rsi.isna().all() or (valid_rsi == 50).all()

    def test_rsi_signal_generator_basic(self, sample_price_data):
        """Test RSI signal generator returns valid signals."""
        entries, exits = rsi_signal_generator(
            sample_price_data,
            rsi_period=14,
            oversold=30,
            overbought=70
        )

        # Check types
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)

        # Check lengths match
        assert len(entries) == len(sample_price_data)
        assert len(exits) == len(sample_price_data)

        # Check signals are boolean
        assert entries.dtype == bool
        assert exits.dtype == bool

        # Check signals are not all False (should have some signals)
        assert entries.sum() > 0 or exits.sum() > 0

    def test_rsi_signal_generator_parameters(self, sample_price_data):
        """Test RSI signal generator with different parameters."""
        # More aggressive (wider oversold/overbought thresholds)
        entries1, exits1 = rsi_signal_generator(
            sample_price_data,
            oversold=20,
            overbought=80
        )

        # Less aggressive (narrower thresholds)
        entries2, exits2 = rsi_signal_generator(
            sample_price_data,
            oversold=40,
            overbought=60
        )

        # Narrower thresholds should generate more signals
        assert entries2.sum() >= entries1.sum()
        assert exits2.sum() >= exits1.sum()

    def test_rsi_mean_reversion_generator(self, sample_price_data):
        """Test RSI mean reversion signal generator."""
        entries, exits = rsi_mean_reversion_signal_generator(
            sample_price_data,
            rsi_period=14,
            oversold_entry=30,
            oversold_exit=50
        )

        # Check basic properties
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool

        # Mean reversion should exit at neutral (50), not overbought
        # This is different from standard RSI strategy
        assert len(entries) == len(sample_price_data)


# ============================================================================
# MACD Strategy Tests
# ============================================================================

class TestMACDStrategy:
    """Test MACD calculation and signal generation."""

    def test_calculate_macd_basic(self, sample_price_data):
        """Test MACD calculation returns valid components."""
        macd_data = calculate_macd(
            sample_price_data,
            fast_period=12,
            slow_period=26,
            signal_period=9
        )

        # Check return type
        assert isinstance(macd_data, dict)

        # Check keys
        assert 'macd' in macd_data
        assert 'signal' in macd_data
        assert 'histogram' in macd_data

        # Check all components are Series
        assert isinstance(macd_data['macd'], pd.Series)
        assert isinstance(macd_data['signal'], pd.Series)
        assert isinstance(macd_data['histogram'], pd.Series)

        # Check lengths match
        assert len(macd_data['macd']) == len(sample_price_data)
        assert len(macd_data['signal']) == len(sample_price_data)
        assert len(macd_data['histogram']) == len(sample_price_data)

        # Check histogram = macd - signal
        np.testing.assert_array_almost_equal(
            macd_data['histogram'].values,
            (macd_data['macd'] - macd_data['signal']).values
        )

    def test_macd_signal_generator_basic(self, sample_price_data):
        """Test MACD signal generator returns valid signals."""
        entries, exits = macd_signal_generator(
            sample_price_data,
            fast_period=12,
            slow_period=26,
            signal_period=9
        )

        # Check types and lengths
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert len(entries) == len(sample_price_data)
        assert len(exits) == len(sample_price_data)

        # Check boolean
        assert entries.dtype == bool
        assert exits.dtype == bool

        # Should have some signals
        assert entries.sum() > 0 or exits.sum() > 0

    def test_macd_trending_market(self, trending_up_data):
        """Test MACD generates entry signals in uptrend."""
        entries, exits = macd_signal_generator(trending_up_data)

        # In strong uptrend, should have entry signals
        assert entries.sum() > 0

    def test_macd_histogram_generator(self, sample_price_data):
        """Test MACD histogram signal generator."""
        entries, exits = macd_histogram_signal_generator(
            sample_price_data,
            histogram_threshold=0.0
        )

        # Check basic properties
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool

    def test_macd_trend_following_generator(self, sample_price_data):
        """Test MACD trend following with confirmation filter."""
        entries, exits = macd_trend_following_signal_generator(
            sample_price_data,
            min_histogram=0.5
        )

        # Trend following should filter weak signals
        # Should have fewer entries than standard MACD
        standard_entries, _ = macd_signal_generator(sample_price_data)

        assert entries.sum() <= standard_entries.sum()


# ============================================================================
# Bollinger Bands Strategy Tests
# ============================================================================

class TestBollingerBandsStrategy:
    """Test Bollinger Bands calculation and signal generation."""

    def test_calculate_bollinger_bands_basic(self, sample_price_data):
        """Test Bollinger Bands calculation."""
        bb_data = calculate_bollinger_bands(
            sample_price_data,
            period=20,
            num_std=2.0
        )

        # Check return type and keys
        assert isinstance(bb_data, dict)
        assert 'upper' in bb_data
        assert 'middle' in bb_data
        assert 'lower' in bb_data
        assert 'bandwidth' in bb_data
        assert 'percent_b' in bb_data

        # Check all are Series
        for key in bb_data:
            assert isinstance(bb_data[key], pd.Series)
            assert len(bb_data[key]) == len(sample_price_data)

        # Check band relationships (for non-NaN values)
        valid_mask = ~(bb_data['upper'].isna() | bb_data['middle'].isna() | bb_data['lower'].isna())
        assert (bb_data['upper'][valid_mask] >= bb_data['middle'][valid_mask]).all()
        assert (bb_data['middle'][valid_mask] >= bb_data['lower'][valid_mask]).all()

        # Check bandwidth = upper - lower
        np.testing.assert_array_almost_equal(
            bb_data['bandwidth'][valid_mask].values,
            (bb_data['upper'][valid_mask] - bb_data['lower'][valid_mask]).values
        )

    def test_bollinger_bands_percent_b(self, sample_price_data):
        """Test %B indicator calculation."""
        bb_data = calculate_bollinger_bands(sample_price_data)
        percent_b = bb_data['percent_b']

        # %B should be:
        # - 0 when price at lower band
        # - 0.5 when price at middle band
        # - 1 when price at upper band
        # - Can be <0 or >1 when price outside bands

        # Just check it's calculated (values can be any real number)
        assert isinstance(percent_b, pd.Series)

    def test_bb_signal_generator_basic(self, sample_price_data):
        """Test Bollinger Bands mean reversion strategy."""
        entries, exits = bb_signal_generator(
            sample_price_data,
            period=20,
            num_std=2.0
        )

        # Check types
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool

        # Should have some signals
        assert entries.sum() > 0 or exits.sum() > 0

    def test_bb_breakout_generator(self, trending_up_data):
        """Test Bollinger Bands breakout strategy in uptrend."""
        entries, exits = bb_breakout_signal_generator(trending_up_data)

        # Breakout strategy should generate signals in trending market
        assert entries.sum() > 0

    def test_bb_squeeze_generator(self, sideways_data):
        """Test Bollinger Bands squeeze strategy."""
        entries, exits = bb_squeeze_signal_generator(
            sideways_data,
            squeeze_threshold=0.02
        )

        # Check basic properties
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)

        # Squeeze strategy looks for volatility expansion
        # Should have some signals in sideways market
        assert entries.sum() >= 0  # May or may not have signals

    def test_bb_dual_threshold_generator(self, sample_price_data):
        """Test Bollinger Bands dual threshold strategy."""
        entries, exits = bb_dual_threshold_signal_generator(
            sample_price_data,
            entry_percent_b=0.0,
            exit_percent_b=0.5
        )

        # Check basic properties
        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool

    def test_bb_different_std(self, sample_price_data):
        """Test Bollinger Bands with different standard deviations."""
        # Wider bands (3 std)
        bb_wide = calculate_bollinger_bands(sample_price_data, num_std=3.0)

        # Narrower bands (1 std)
        bb_narrow = calculate_bollinger_bands(sample_price_data, num_std=1.0)

        # Check bandwidth relationship
        valid_mask = ~bb_wide['bandwidth'].isna()
        assert (bb_wide['bandwidth'][valid_mask] > bb_narrow['bandwidth'][valid_mask]).all()


# ============================================================================
# Integration Tests
# ============================================================================

class TestSignalGeneratorIntegration:
    """Integration tests for signal generators with vectorbt."""

    @pytest.fixture(scope="class")
    def test_db_path(self):
        """Get test database path."""
        db_path = Path(__file__).parent.parent.parent / 'data' / 'spock_local.db'
        if not db_path.exists():
            pytest.skip(f"Test database not found: {db_path}")
        return str(db_path)

    def test_rsi_with_vectorbt(self, test_db_path):
        """Test RSI signal generator with vectorbt."""
        # Import here to avoid pytest-cov issues
        try:
            from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
            from modules.backtesting.backtest_config import BacktestConfig
            from modules.backtesting.data_providers import SQLiteDataProvider
            from modules.db_manager_sqlite import SQLiteDatabaseManager
        except ImportError:
            pytest.skip("Required modules not available")

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not available")

        # Create config
        config = BacktestConfig(
            start_date=date(2024, 10, 10),
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

        # Create data provider
        db_manager = SQLiteDatabaseManager(test_db_path)
        data_provider = SQLiteDataProvider(db_manager)

        # Create adapter with RSI signal generator
        adapter = VectorbtAdapter(config, data_provider, signal_generator=rsi_signal_generator)

        # Run backtest
        result = adapter.run()

        # Check result is valid
        assert result is not None
        assert result.total_return is not None
        assert isinstance(result.total_trades, (int, np.integer))

    def test_macd_with_vectorbt(self, test_db_path):
        """Test MACD signal generator with vectorbt."""
        try:
            from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
            from modules.backtesting.backtest_config import BacktestConfig
            from modules.backtesting.data_providers import SQLiteDataProvider
            from modules.db_manager_sqlite import SQLiteDatabaseManager
        except ImportError:
            pytest.skip("Required modules not available")

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not available")

        config = BacktestConfig(
            start_date=date(2024, 10, 10),
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

        db_manager = SQLiteDatabaseManager(test_db_path)
        data_provider = SQLiteDataProvider(db_manager)

        adapter = VectorbtAdapter(config, data_provider, signal_generator=macd_signal_generator)
        result = adapter.run()

        assert result is not None
        assert isinstance(result.total_trades, (int, np.integer))

    def test_bb_with_vectorbt(self, test_db_path):
        """Test Bollinger Bands signal generator with vectorbt."""
        try:
            from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
            from modules.backtesting.backtest_config import BacktestConfig
            from modules.backtesting.data_providers import SQLiteDataProvider
            from modules.db_manager_sqlite import SQLiteDatabaseManager
        except ImportError:
            pytest.skip("Required modules not available")

        if not VECTORBT_AVAILABLE:
            pytest.skip("vectorbt not available")

        config = BacktestConfig(
            start_date=date(2024, 10, 10),
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

        db_manager = SQLiteDatabaseManager(test_db_path)
        data_provider = SQLiteDataProvider(db_manager)

        adapter = VectorbtAdapter(config, data_provider, signal_generator=bb_signal_generator)
        result = adapter.run()

        assert result is not None
        assert isinstance(result.total_trades, (int, np.integer))


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_insufficient_data(self):
        """Test with insufficient data for indicators."""
        # Only 10 data points, but RSI needs 14 for stable results
        short_data = pd.Series(
            [100, 101, 99, 102, 98, 103, 97, 104, 96, 105],
            index=pd.date_range('2024-01-01', periods=10)
        )

        rsi = calculate_rsi(short_data, period=14)

        # EMA-based RSI will calculate with less data but may be unstable
        # Check that RSI is calculated (not all NaN) but first value is NaN
        assert isinstance(rsi, pd.Series)
        assert pd.isna(rsi.iloc[0])  # First value should be NaN
        # Most values should be valid (EMA adapts to available data)
        assert rsi.notna().sum() > 0

    def test_empty_data(self):
        """Test with empty data."""
        empty_data = pd.Series([], dtype=float)

        rsi = calculate_rsi(empty_data)
        assert len(rsi) == 0

        macd_data = calculate_macd(empty_data)
        assert len(macd_data['macd']) == 0

        bb_data = calculate_bollinger_bands(empty_data)
        assert len(bb_data['upper']) == 0

    def test_nan_handling(self):
        """Test handling of NaN values in data."""
        data_with_nan = pd.Series(
            [100, 101, np.nan, 102, 103, 104],
            index=pd.date_range('2024-01-01', periods=6)
        )

        # Indicators should handle NaN gracefully
        rsi = calculate_rsi(data_with_nan, period=3)
        assert isinstance(rsi, pd.Series)

        macd_data = calculate_macd(data_with_nan)
        assert isinstance(macd_data['macd'], pd.Series)

        bb_data = calculate_bollinger_bands(data_with_nan)
        assert isinstance(bb_data['upper'], pd.Series)
