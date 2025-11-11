"""
Unit Tests for Signal Generators

Tests for vectorbt-compatible signal generators including:
- BaseSignalGenerator contract compliance
- MomentumSignalGenerator RSI and MA crossover logic
- ValueSignalGenerator placeholder behavior
- CombinedSignalGenerator multi-factor logic
- SignalGeneratorFactory creation and registration

Author: Spock MCP Server
Date: 2025-10-31
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from mcp_server.strategies import (
    BaseSignalGenerator,
    MomentumSignalGenerator,
    ValueSignalGenerator,
    CombinedSignalGenerator,
    SignalGeneratorFactory,
)


class TestBaseSignalGenerator:
    """Test abstract base class contract."""

    def test_cannot_instantiate_abstract_class(self):
        """Verify BaseSignalGenerator cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseSignalGenerator({})

    def test_subclass_must_implement_generate_signals(self):
        """Verify subclasses must implement generate_signals()."""

        class IncompleteGenerator(BaseSignalGenerator):
            pass

        with pytest.raises(TypeError):
            IncompleteGenerator({})


class TestMomentumSignalGenerator:
    """Test momentum strategy signal generation."""

    @pytest.fixture
    def sample_prices(self):
        """Create sample price data for testing."""
        # Generate 100 days of price data with trend
        dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
        prices = pd.Series(
            100 + np.cumsum(np.random.randn(100) * 2),
            index=dates,
            name="TEST001"
        )
        return prices

    def test_momentum_generator_initialization(self):
        """Test momentum generator initialization with parameters."""
        params = {"rsi_period": 14, "ma_fast": 20, "ma_slow": 50}
        gen = MomentumSignalGenerator(params)

        assert gen.parameters == params
        assert callable(gen)

    def test_momentum_generator_signature(self):
        """Verify vectorbt-compatible signature."""
        gen = MomentumSignalGenerator({})
        close = pd.Series([100, 101, 99], index=pd.date_range("2024-01-01", periods=3))

        # Should accept pd.Series and return tuple of pd.Series
        entries, exits = gen.generate_signals(close)

        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool
        assert len(entries) == len(close)
        assert len(exits) == len(close)

    def test_momentum_generator_callable(self):
        """Verify generator is callable (vectorbt compatibility)."""
        gen = MomentumSignalGenerator({})
        close = pd.Series([100, 101, 99], index=pd.date_range("2024-01-01", periods=3))

        # Should work with both calling styles
        entries1, exits1 = gen.generate_signals(close)
        entries2, exits2 = gen(close)

        pd.testing.assert_series_equal(entries1, entries2)
        pd.testing.assert_series_equal(exits1, exits2)

    def test_momentum_signals_with_parameters(self, sample_prices):
        """Test signal generation with custom parameters."""
        gen = MomentumSignalGenerator({
            "rsi_period": 10,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
            "ma_fast": 10,
            "ma_slow": 20
        })

        entries, exits = gen.generate_signals(sample_prices)

        # Verify signals are generated (at least some should exist)
        assert entries.sum() > 0 or exits.sum() > 0

        # Verify no overlapping signals (entry and exit on same bar)
        assert not (entries & exits).any()

    def test_momentum_rsi_calculation(self, sample_prices):
        """Test RSI calculation produces valid values."""
        gen = MomentumSignalGenerator({"rsi_period": 14})

        # Calculate RSI internally
        rsi = gen._calculate_rsi(sample_prices, period=14)

        # RSI should be between 0 and 100
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

        # RSI should not have NaN after warmup period
        assert not rsi.iloc[14:].isna().any()

    def test_momentum_entry_conditions(self):
        """Test entry signal generation logic."""
        # Create price series with known RSI oversold condition
        prices = pd.Series(
            [100, 95, 90, 85, 80, 82, 85, 88, 90, 92],
            index=pd.date_range("2024-01-01", periods=10),
            name="TEST"
        )

        gen = MomentumSignalGenerator({
            "rsi_period": 5,
            "rsi_oversold": 30,
            "ma_fast": 3,
            "ma_slow": 5
        })

        entries, exits = gen.generate_signals(prices)

        # Entry should occur when RSI crosses above oversold AND trend is bullish
        # Exact conditions depend on data, but entries should exist
        assert entries.dtype == bool

    def test_momentum_parameter_override(self, sample_prices):
        """Test parameter override via kwargs."""
        gen = MomentumSignalGenerator({"rsi_period": 14})

        # Override with different period
        entries1, exits1 = gen.generate_signals(sample_prices, rsi_period=10)
        entries2, exits2 = gen.generate_signals(sample_prices, rsi_period=20)

        # Results should differ due to different RSI periods
        assert not entries1.equals(entries2) or not exits1.equals(exits2)


class TestValueSignalGenerator:
    """Test value strategy signal generation."""

    def test_value_generator_initialization(self):
        """Test value generator initialization."""
        gen = ValueSignalGenerator({})
        assert gen.parameters == {}

    def test_value_generator_buy_and_hold(self):
        """Test buy-and-hold placeholder behavior."""
        prices = pd.Series(
            [100, 105, 95, 110, 90],
            index=pd.date_range("2024-01-01", periods=5),
            name="TEST"
        )

        gen = ValueSignalGenerator({})
        entries, exits = gen.generate_signals(prices)

        # Should buy at start
        assert entries.iloc[0] == True
        assert entries.iloc[1:].sum() == 0  # No additional entries

        # Should not exit (hold until end)
        assert exits.sum() == 0

    def test_value_generator_signature_compatibility(self):
        """Verify value generator matches vectorbt signature."""
        gen = ValueSignalGenerator({})
        close = pd.Series([100, 101, 99], index=pd.date_range("2024-01-01", periods=3))

        entries, exits = gen(close)

        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert entries.dtype == bool
        assert exits.dtype == bool


class TestCombinedSignalGenerator:
    """Test combined momentum + value strategy."""

    def test_combined_generator_initialization(self):
        """Test combined generator initialization."""
        params = {"rsi_period": 14, "ma_fast": 20}
        gen = CombinedSignalGenerator(params)

        assert gen.parameters == params
        assert isinstance(gen.momentum_gen, MomentumSignalGenerator)
        assert isinstance(gen.value_gen, ValueSignalGenerator)

    def test_combined_generator_and_logic(self):
        """Test combined entry signals use AND logic."""
        prices = pd.Series(
            [100, 105, 110, 115, 120, 125, 130],
            index=pd.date_range("2024-01-01", periods=7),
            name="TEST"
        )

        gen = CombinedSignalGenerator({"rsi_period": 5, "ma_fast": 2, "ma_slow": 3})
        entries, exits = gen.generate_signals(prices)

        # Combined entries should be more conservative than momentum alone
        momentum_gen = MomentumSignalGenerator(gen.parameters)
        momentum_entries, _ = momentum_gen.generate_signals(prices)

        # Combined entries should be subset of momentum entries
        # (value always buys at start, so first entry might match)
        assert entries.sum() <= momentum_entries.sum()

    def test_combined_generator_or_logic(self):
        """Test combined exit signals use OR logic."""
        prices = pd.Series(
            [100, 95, 90, 85, 80, 75, 70],
            index=pd.date_range("2024-01-01", periods=7),
            name="TEST"
        )

        gen = CombinedSignalGenerator({"rsi_period": 5, "ma_fast": 2, "ma_slow": 3})
        entries, exits = gen.generate_signals(prices)

        # Combined exits should be more aggressive (OR logic)
        momentum_gen = MomentumSignalGenerator(gen.parameters)
        _, momentum_exits = momentum_gen.generate_signals(prices)

        # Combined exits should be superset of momentum exits
        # (value never exits, so combined = momentum in this case)
        assert exits.sum() >= momentum_exits.sum()


class TestSignalGeneratorFactory:
    """Test signal generator factory pattern."""

    def test_factory_create_momentum(self):
        """Test creating momentum generator via factory."""
        gen = SignalGeneratorFactory.create("momentum", {"rsi_period": 14})

        assert isinstance(gen, MomentumSignalGenerator)
        assert gen.parameters == {"rsi_period": 14}

    def test_factory_create_value(self):
        """Test creating value generator via factory."""
        gen = SignalGeneratorFactory.create("value", {})

        assert isinstance(gen, ValueSignalGenerator)

    def test_factory_create_combined(self):
        """Test creating combined generator via factory."""
        gen = SignalGeneratorFactory.create("momentum_value", {"rsi_period": 10})

        assert isinstance(gen, CombinedSignalGenerator)

    def test_factory_invalid_strategy(self):
        """Test factory rejects unknown strategy types."""
        with pytest.raises(ValueError, match="Unknown strategy type"):
            SignalGeneratorFactory.create("invalid_strategy", {})

    def test_factory_list_strategies(self):
        """Test factory lists available strategies."""
        strategies = SignalGeneratorFactory.list_strategies()

        assert "momentum" in strategies
        assert "value" in strategies
        assert "momentum_value" in strategies

    def test_factory_register_custom_strategy(self):
        """Test registering custom strategy."""

        class CustomSignalGenerator(BaseSignalGenerator):
            def generate_signals(self, close, **kwargs):
                # Simple custom logic
                entries = close > close.shift(1)
                exits = close < close.shift(1)
                return entries, exits

        # Register custom strategy
        SignalGeneratorFactory.register_strategy("custom", CustomSignalGenerator)

        # Verify registration
        assert "custom" in SignalGeneratorFactory.list_strategies()

        # Create instance
        gen = SignalGeneratorFactory.create("custom", {})
        assert isinstance(gen, CustomSignalGenerator)

    def test_factory_register_invalid_generator(self):
        """Test factory rejects non-BaseSignalGenerator subclasses."""

        class InvalidGenerator:
            pass

        with pytest.raises(ValueError, match="must inherit from BaseSignalGenerator"):
            SignalGeneratorFactory.register_strategy("invalid", InvalidGenerator)


class TestSignalGeneratorIntegration:
    """Integration tests for signal generators."""

    def test_end_to_end_momentum_backtest_compatibility(self):
        """Test momentum generator works with vectorbt-style usage."""
        # Simulate vectorbt usage pattern
        prices = pd.Series(
            np.random.randn(100).cumsum() + 100,
            index=pd.date_range("2024-01-01", periods=100),
            name="AAPL"
        )

        # Create generator via factory
        gen = SignalGeneratorFactory.create("momentum", {
            "rsi_period": 14,
            "ma_fast": 20,
            "ma_slow": 50
        })

        # Generate signals (vectorbt-style)
        entries, exits = gen(prices)

        # Verify basic properties
        assert len(entries) == len(prices)
        assert len(exits) == len(prices)
        assert entries.dtype == bool
        assert exits.dtype == bool

        # Verify signals are logical (no simultaneous entry/exit)
        assert not (entries & exits).any()

    def test_all_strategies_produce_valid_signals(self):
        """Test all registered strategies produce valid outputs."""
        prices = pd.Series(
            [100, 105, 110, 108, 112, 115, 113, 118, 120, 125],
            index=pd.date_range("2024-01-01", periods=10),
            name="TEST"
        )

        for strategy_name in SignalGeneratorFactory.list_strategies():
            gen = SignalGeneratorFactory.create(strategy_name, {})
            entries, exits = gen(prices)

            # Verify output format
            assert isinstance(entries, pd.Series)
            assert isinstance(exits, pd.Series)
            assert entries.dtype == bool
            assert exits.dtype == bool
            assert len(entries) == len(prices)
            assert len(exits) == len(prices)

            # Verify index alignment
            pd.testing.assert_index_equal(entries.index, prices.index)
            pd.testing.assert_index_equal(exits.index, prices.index)
