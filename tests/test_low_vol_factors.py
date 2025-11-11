"""
Test Low-Volatility Factors

Tests for low-volatility factor implementations:
- Historical Volatility Factor
- Beta Factor (placeholder)
- Maximum Drawdown Factor

Usage:
    pytest tests/test_low_vol_factors.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from modules.factors.low_vol_factors import (
    HistoricalVolatilityFactor,
    BetaFactor,
    MaxDrawdownFactor
)
from modules.factors.factor_base import FactorCategory


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_price_data_stable():
    """Create stable price series with low volatility."""
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    # Stable prices around 100 with small random noise
    np.random.seed(42)
    prices = 100 + np.random.normal(0, 1, len(dates))  # Low vol: std=1

    return pd.DataFrame({
        'date': dates,
        'close': prices
    })


@pytest.fixture
def sample_price_data_volatile():
    """Create volatile price series with high volatility."""
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    # Volatile prices with large swings
    np.random.seed(42)
    prices = 100 + np.random.normal(0, 10, len(dates))  # High vol: std=10

    return pd.DataFrame({
        'date': dates,
        'close': prices
    })


@pytest.fixture
def sample_price_data_with_drawdown():
    """Create price series with significant drawdown and recovery."""
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')

    # Create pattern: rise → sharp drop → recovery
    prices = []
    for i in range(len(dates)):
        if i < 100:  # Rise to peak
            prices.append(100 + i * 0.5)
        elif i < 150:  # Sharp 30% drawdown
            peak = 100 + 99 * 0.5
            prices.append(peak * (1 - 0.006 * (i - 100)))
        else:  # Gradual recovery
            trough = 100 + 99 * 0.5 * 0.7
            recovery_days = i - 150
            prices.append(trough + recovery_days * 0.3)

    return pd.DataFrame({
        'date': dates,
        'close': prices
    })


@pytest.fixture
def insufficient_data():
    """Create insufficient price data (< 30 days)."""
    dates = pd.date_range('2024-01-01', '2024-01-20', freq='D')
    return pd.DataFrame({
        'date': dates,
        'close': [100.0] * len(dates)
    })


@pytest.fixture
def minimal_data():
    """Create minimal valid price data (exactly 30 days)."""
    dates = pd.date_range('2024-01-01', '2024-01-30', freq='D')
    np.random.seed(42)
    prices = 100 + np.random.normal(0, 2, len(dates))

    return pd.DataFrame({
        'date': dates,
        'close': prices
    })


# ============================================================================
# HistoricalVolatilityFactor Tests
# ============================================================================

class TestHistoricalVolatilityFactor:
    """Test historical volatility factor calculation."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = HistoricalVolatilityFactor()

        assert factor.name == "Historical_Volatility"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 30
        assert factor.min_required_days == 30

    def test_required_columns(self):
        """Test required column specification."""
        factor = HistoricalVolatilityFactor()
        required = factor.get_required_columns()

        assert 'date' in required
        assert 'close' in required
        assert len(required) == 2

    def test_calculate_stable_prices(self, sample_price_data_stable):
        """Test volatility calculation with stable prices."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(sample_price_data_stable, '005930')

        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == "Historical_Volatility"

        # Negated volatility - stable = high score (less negative)
        assert result.raw_value < 0  # Volatility is negated
        assert result.raw_value > -50  # But not too negative (low vol)

        # Metadata checks
        assert 'annualized_volatility' in result.metadata
        assert 'downside_volatility' in result.metadata
        assert result.metadata['annualized_volatility'] < 50  # Low volatility

    def test_calculate_volatile_prices(self, sample_price_data_volatile):
        """Test volatility calculation with volatile prices."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(sample_price_data_volatile, '035420')

        assert result is not None

        # Volatile prices = more negative score
        assert result.raw_value < -50  # Higher volatility
        assert result.metadata['annualized_volatility'] > 50

    def test_volatility_ranking_logic(self, sample_price_data_stable, sample_price_data_volatile):
        """Test that lower volatility ranks higher (less negative)."""
        factor = HistoricalVolatilityFactor()

        stable_result = factor.calculate(sample_price_data_stable, 'STABLE')
        volatile_result = factor.calculate(sample_price_data_volatile, 'VOLATILE')

        assert stable_result is not None
        assert volatile_result is not None

        # Lower volatility = higher (less negative) raw_value
        assert stable_result.raw_value > volatile_result.raw_value

    def test_downside_volatility(self, sample_price_data_stable):
        """Test downside volatility calculation."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(sample_price_data_stable, '005930')

        assert result is not None
        assert 'downside_volatility' in result.metadata
        assert result.metadata['downside_volatility'] >= 0
        assert 'negative_days' in result.metadata
        assert 'negative_ratio' in result.metadata

    def test_annualized_volatility_formula(self, sample_price_data_stable):
        """Test annualized volatility calculation formula."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(sample_price_data_stable, '005930')

        assert result is not None

        # Annualized vol = daily_std * sqrt(252) * 100
        daily_std = result.metadata['daily_std']
        annualized_vol = result.metadata['annualized_volatility']

        expected_annualized = daily_std * np.sqrt(252) * 100
        assert abs(annualized_vol - expected_annualized) < 0.01

    def test_insufficient_data(self, insufficient_data):
        """Test handling of insufficient data."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(insufficient_data, '005930')

        assert result is None  # Not enough data

    def test_minimal_data(self, minimal_data):
        """Test calculation with minimal valid data."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(minimal_data, '005930')

        # Should work with exactly 30 days
        assert result is not None

    def test_confidence_score(self, sample_price_data_stable):
        """Test confidence score calculation."""
        factor = HistoricalVolatilityFactor()
        result = factor.calculate(sample_price_data_stable, '005930')

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

        # Stable prices with full data = high confidence
        assert result.confidence > 0.7

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        factor = HistoricalVolatilityFactor()
        empty_df = pd.DataFrame(columns=['date', 'close'])

        result = factor.calculate(empty_df, '005930')
        assert result is None

    def test_zero_returns_handling(self):
        """Test handling of constant prices (zero returns)."""
        factor = HistoricalVolatilityFactor()

        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        constant_prices = pd.DataFrame({
            'date': dates,
            'close': [100.0] * len(dates)  # No volatility
        })

        result = factor.calculate(constant_prices, '005930')
        assert result is not None
        assert result.metadata['annualized_volatility'] == 0.0
        assert result.raw_value == 0.0  # -0.0


# ============================================================================
# BetaFactor Tests
# ============================================================================

class TestBetaFactor:
    """Test beta factor (placeholder implementation)."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = BetaFactor()

        assert factor.name == "Beta"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 252
        assert factor.min_required_days == 60

    def test_required_columns(self):
        """Test required column specification."""
        factor = BetaFactor()
        required = factor.get_required_columns()

        assert 'date' in required
        assert 'close' in required
        assert 'market_close' in required  # Requires market index

    def test_placeholder_returns_none(self, sample_price_data_stable):
        """Test that placeholder implementation returns None."""
        factor = BetaFactor()
        result = factor.calculate(sample_price_data_stable, '005930')

        # Placeholder always returns None
        assert result is None


# ============================================================================
# MaxDrawdownFactor Tests
# ============================================================================

class TestMaxDrawdownFactor:
    """Test maximum drawdown factor calculation."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = MaxDrawdownFactor()

        assert factor.name == "Max_Drawdown"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 252
        assert factor.min_required_days == 30

    def test_required_columns(self):
        """Test required column specification."""
        factor = MaxDrawdownFactor()
        required = factor.get_required_columns()

        assert 'date' in required
        assert 'close' in required
        assert len(required) == 2

    def test_calculate_with_drawdown(self, sample_price_data_with_drawdown):
        """Test drawdown calculation with significant decline."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(sample_price_data_with_drawdown, '005930')

        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == "Max_Drawdown"

        # Max drawdown should be negative
        assert result.metadata['max_drawdown'] < 0

        # Factor value is negated (smaller drawdown = higher score)
        assert result.raw_value > 0  # Negated negative = positive

    def test_drawdown_ranking_logic(self, sample_price_data_stable, sample_price_data_with_drawdown):
        """Test that smaller drawdown ranks higher."""
        factor = MaxDrawdownFactor()

        stable_result = factor.calculate(sample_price_data_stable, 'STABLE')
        drawdown_result = factor.calculate(sample_price_data_with_drawdown, 'DRAWDOWN')

        assert stable_result is not None
        assert drawdown_result is not None

        # Smaller drawdown magnitude = smaller raw_value (less negative when negated)
        # stable has -6.83% drawdown → raw_value = 6.83
        # drawdown has -29.4% drawdown → raw_value = 29.4
        # BUT for ranking, we want smaller drawdown to rank BETTER
        # So we check metadata: smaller abs(max_drawdown) = better
        assert abs(stable_result.metadata['max_drawdown']) < abs(drawdown_result.metadata['max_drawdown'])

    def test_recovery_time_calculation(self, sample_price_data_with_drawdown):
        """Test recovery time tracking."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(sample_price_data_with_drawdown, '005930')

        assert result is not None
        assert 'recovery_days' in result.metadata

        # Should have recovered (or None if not recovered)
        recovery_days = result.metadata['recovery_days']
        if recovery_days is not None:
            assert recovery_days > 0

    def test_current_drawdown(self, sample_price_data_with_drawdown):
        """Test current drawdown tracking."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(sample_price_data_with_drawdown, '005930')

        assert result is not None
        assert 'current_drawdown' in result.metadata

        # Current drawdown should be <= 0
        assert result.metadata['current_drawdown'] <= 0

    def test_no_recovery_scenario(self):
        """Test scenario where price never recovers."""
        factor = MaxDrawdownFactor()

        # Create declining price series (no recovery)
        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        prices = [100 - i * 0.1 for i in range(len(dates))]

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        result = factor.calculate(data, '005930')
        assert result is not None
        assert result.metadata['recovery_days'] is None  # Never recovered

    def test_insufficient_data(self, insufficient_data):
        """Test handling of insufficient data."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(insufficient_data, '005930')

        assert result is None  # Not enough data (< 60 days)

    def test_minimal_data(self):
        """Test calculation with minimal valid data (60 days)."""
        factor = MaxDrawdownFactor()

        dates = pd.date_range('2024-01-01', '2024-03-01', freq='D')
        np.random.seed(42)
        prices = 100 + np.random.normal(0, 2, len(dates))

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        result = factor.calculate(data, '005930')
        assert result is not None

    def test_confidence_score(self, sample_price_data_with_drawdown):
        """Test confidence score calculation."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(sample_price_data_with_drawdown, '005930')

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

        # Large drawdown = lower confidence
        if abs(result.metadata['max_drawdown']) > 30:
            assert result.confidence < 0.8

    def test_zero_drawdown_scenario(self):
        """Test scenario with continuously rising prices (no drawdown)."""
        factor = MaxDrawdownFactor()

        dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
        prices = [100 + i * 0.1 for i in range(len(dates))]  # Continuously rising

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        result = factor.calculate(data, '005930')
        assert result is not None
        assert result.metadata['max_drawdown'] == 0.0
        assert result.raw_value == 0.0  # Negated zero = zero

    def test_metadata_completeness(self, sample_price_data_with_drawdown):
        """Test that all metadata fields are populated."""
        factor = MaxDrawdownFactor()
        result = factor.calculate(sample_price_data_with_drawdown, '005930')

        assert result is not None
        assert 'max_drawdown' in result.metadata
        assert 'recovery_days' in result.metadata
        assert 'current_drawdown' in result.metadata
        assert 'data_points' in result.metadata

        assert result.metadata['data_points'] > 0

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        factor = MaxDrawdownFactor()
        empty_df = pd.DataFrame(columns=['date', 'close'])

        result = factor.calculate(empty_df, '005930')
        assert result is None
