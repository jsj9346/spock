"""
Test Momentum Factors

Tests for momentum factor implementations:
- TwelveMonthMomentumFactor (12M momentum with volume/trend adjustments)
- RSIMomentumFactor (Relative Strength Index momentum)
- ShortTermMomentumFactor (Short-term price momentum)

Usage:
    pytest tests/test_momentum_factors.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from modules.factors.momentum_factors import (
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor
)
from modules.factors.factor_base import FactorCategory


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def strong_momentum_data():
    """Create price series with strong upward momentum."""
    dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')
    # Strong uptrend: +50% over 12 months
    prices = [100 * (1 + 0.50 * i / len(dates)) for i in range(len(dates))]
    volumes = [1000000] * len(dates)

    # Calculate moving averages (required by TwelveMonthMomentumFactor)
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': volumes
    })

    # Add MA20 and MA60
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()

    return df


@pytest.fixture
def weak_momentum_data():
    """Create price series with weak/negative momentum."""
    dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')
    # Weak downtrend: -20% over 12 months
    prices = [100 * (1 - 0.20 * i / len(dates)) for i in range(len(dates))]
    volumes = [1000000] * len(dates)

    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': volumes
    })

    # Add MA20 and MA60
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()

    return df


@pytest.fixture
def high_volume_momentum_data():
    """Create momentum data with increasing volume (strong signal)."""
    dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')
    prices = [100 * (1 + 0.30 * i / len(dates)) for i in range(len(dates))]
    # Volume increases with price (confirmation)
    volumes = [1000000 * (1 + 0.50 * i / len(dates)) for i in range(len(dates))]

    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': volumes
    })

    # Add MA20 and MA60
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()

    return df


@pytest.fixture
def rsi_overbought_data():
    """Create price series with RSI in overbought territory."""
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    np.random.seed(42)
    # Consistently rising prices → RSI >70
    prices = [100 + i * 0.5 + np.random.normal(0, 0.5) for i in range(len(dates))]

    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': [1000000] * len(dates)
    })

    # Calculate RSI-14 (required by RSIMomentumFactor)
    # Simplified RSI calculation for testing
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))

    # For overbought scenario, ensure RSI > 70
    df['rsi_14'] = df['rsi_14'].fillna(75.0)  # Fill NaN with overbought value

    return df


@pytest.fixture
def rsi_oversold_data():
    """Create price series with RSI in oversold territory."""
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    np.random.seed(42)
    # Consistently falling prices → RSI <30
    prices = [100 - i * 0.5 + np.random.normal(0, 0.5) for i in range(len(dates))]

    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': [1000000] * len(dates)
    })

    # Calculate RSI-14 (required by RSIMomentumFactor)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))

    # For oversold scenario, ensure RSI < 30
    df['rsi_14'] = df['rsi_14'].fillna(25.0)  # Fill NaN with oversold value

    return df


@pytest.fixture
def insufficient_data_252():
    """Create insufficient data for 12M momentum (<252 days)."""
    dates = pd.date_range('2024-01-01', '2024-06-30', freq='D')  # ~180 days
    return pd.DataFrame({
        'date': dates,
        'close': [100.0] * len(dates),
        'volume': [1000000] * len(dates)
    })


@pytest.fixture
def minimal_data_252():
    """Create minimal valid data for 12M momentum (exactly 252 days)."""
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')  # ~365 days
    prices = [100 + i * 0.1 for i in range(len(dates))]
    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': [1000000] * len(dates)
    })

    # Add MA20 and MA60
    df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
    df['ma60'] = df['close'].rolling(window=60, min_periods=1).mean()

    return df


# ============================================================================
# TwelveMonthMomentumFactor Tests
# ============================================================================

class TestTwelveMonthMomentumFactor:
    """Test 12-month momentum factor with volume/trend adjustments."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = TwelveMonthMomentumFactor()

        assert factor.name == "12M_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 252
        assert factor.min_required_days == 252

    def test_required_columns(self):
        """Test required column specification."""
        factor = TwelveMonthMomentumFactor()
        required = factor.get_required_columns()

        assert 'date' in required
        assert 'close' in required
        assert 'volume' in required
        assert 'ma20' in required
        assert 'ma60' in required

    def test_calculate_strong_momentum(self, strong_momentum_data):
        """Test calculation with strong upward momentum."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(strong_momentum_data, '005930')

        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == "12M_Momentum"

        # Strong uptrend should have positive momentum
        assert result.raw_value > 0
        assert 'base_momentum_return' in result.metadata
        assert result.metadata['base_momentum_return'] > 0

    def test_calculate_weak_momentum(self, weak_momentum_data):
        """Test calculation with weak/negative momentum."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(weak_momentum_data, '035420')

        assert result is not None

        # Weak/negative trend should have negative or low momentum
        assert result.metadata['base_momentum_return'] < 0

    def test_momentum_ranking_logic(self, strong_momentum_data, weak_momentum_data):
        """Test that stronger momentum ranks higher."""
        factor = TwelveMonthMomentumFactor()

        strong_result = factor.calculate(strong_momentum_data, 'STRONG')
        weak_result = factor.calculate(weak_momentum_data, 'WEAK')

        assert strong_result is not None
        assert weak_result is not None

        # Stronger momentum = higher raw_value
        assert strong_result.raw_value > weak_result.raw_value

    def test_volume_adjustment(self, high_volume_momentum_data):
        """Test volume-weighted momentum adjustment."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(high_volume_momentum_data, '005930')

        assert result is not None
        assert 'volume_ratio' in result.metadata
        assert result.metadata['volume_ratio'] > 1.0  # Increasing volume

    def test_insufficient_data(self, insufficient_data_252):
        """Test handling of insufficient data (<252 days)."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(insufficient_data_252, '005930')

        assert result is None  # Not enough data

    def test_minimal_data(self, minimal_data_252):
        """Test calculation with minimal valid data (252+ days)."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(minimal_data_252, '005930')

        # Should work with 252+ days
        assert result is not None

    def test_confidence_score(self, strong_momentum_data):
        """Test confidence score calculation."""
        factor = TwelveMonthMomentumFactor()
        result = factor.calculate(strong_momentum_data, '005930')

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

        # Full 12M data with good volume = high confidence
        assert result.confidence > 0.7

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        factor = TwelveMonthMomentumFactor()
        empty_df = pd.DataFrame(columns=['date', 'close', 'volume'])

        result = factor.calculate(empty_df, '005930')
        assert result is None


# ============================================================================
# RSIMomentumFactor Tests
# ============================================================================

class TestRSIMomentumFactor:
    """Test RSI momentum factor."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = RSIMomentumFactor()

        assert factor.name == "RSI_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 60
        assert factor.min_required_days == 30

    def test_required_columns(self):
        """Test required column specification."""
        factor = RSIMomentumFactor()
        required = factor.get_required_columns()

        assert 'rsi_14' in required

    def test_calculate_overbought(self, rsi_overbought_data):
        """Test RSI calculation in overbought territory."""
        factor = RSIMomentumFactor()
        result = factor.calculate(rsi_overbought_data, '005930')

        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == "RSI_Momentum"

        # Overbought RSI should be >70
        assert 'rsi_value' in result.metadata
        assert result.metadata['rsi_value'] > 50  # Strong uptrend

    def test_calculate_oversold(self, rsi_oversold_data):
        """Test RSI calculation in oversold territory."""
        factor = RSIMomentumFactor()
        result = factor.calculate(rsi_oversold_data, '035420')

        assert result is not None

        # Oversold RSI should be <50 (falling prices)
        assert result.metadata['rsi_value'] < 50

    def test_rsi_bounds(self, rsi_overbought_data):
        """Test that RSI stays within 0-100 bounds."""
        factor = RSIMomentumFactor()
        result = factor.calculate(rsi_overbought_data, '005930')

        assert result is not None
        assert 0 <= result.metadata['rsi_value'] <= 100

    def test_insufficient_data(self):
        """Test handling of insufficient data (<30 days)."""
        factor = RSIMomentumFactor()
        dates = pd.date_range('2024-01-01', '2024-01-20', freq='D')
        data = pd.DataFrame({'date': dates, 'close': [100.0] * len(dates)})

        result = factor.calculate(data, '005930')
        assert result is None

    def test_confidence_score(self, rsi_overbought_data):
        """Test confidence score calculation."""
        factor = RSIMomentumFactor()
        result = factor.calculate(rsi_overbought_data, '005930')

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        factor = RSIMomentumFactor()
        empty_df = pd.DataFrame(columns=['date', 'close'])

        result = factor.calculate(empty_df, '005930')
        assert result is None


# ============================================================================
# ShortTermMomentumFactor Tests
# ============================================================================

class TestShortTermMomentumFactor:
    """Test short-term momentum factor."""

    def test_initialization(self):
        """Test factor initialization."""
        factor = ShortTermMomentumFactor()

        assert factor.name == "1M_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 60
        assert factor.min_required_days == 30

    def test_required_columns(self):
        """Test required column specification."""
        factor = ShortTermMomentumFactor()
        required = factor.get_required_columns()

        assert 'date' in required
        assert 'close' in required

    def test_calculate_short_term_gain(self):
        """Test calculation with short-term price gains."""
        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')  # 90 days
        # Strong 1M gain: +15%
        prices = [100 + i * 0.5 for i in range(len(dates))]
        data = pd.DataFrame({'date': dates, 'close': prices, 'volume': [1000000] * len(dates)})

        factor = ShortTermMomentumFactor()
        result = factor.calculate(data, '005930')

        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == "1M_Momentum"

        # Short-term gain should have positive momentum
        assert result.raw_value > 0
        assert 'momentum_return' in result.metadata

    def test_calculate_short_term_loss(self):
        """Test calculation with short-term price losses."""
        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')  # 90 days
        # 1M loss: -10%
        prices = [100 - i * 0.3 for i in range(len(dates))]
        data = pd.DataFrame({'date': dates, 'close': prices, 'volume': [1000000] * len(dates)})

        factor = ShortTermMomentumFactor()
        result = factor.calculate(data, '035420')

        assert result is not None

        # Short-term loss should have negative momentum
        assert result.metadata['momentum_return'] < 0

    def test_momentum_ranking_logic(self):
        """Test that stronger short-term momentum ranks higher."""
        factor = ShortTermMomentumFactor()

        # Strong gain scenario
        dates1 = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        prices1 = [100 + i * 0.5 for i in range(len(dates1))]
        strong_data = pd.DataFrame({'date': dates1, 'close': prices1, 'volume': [1000000] * len(dates1)})

        # Weak/negative scenario
        dates2 = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        prices2 = [100 - i * 0.2 for i in range(len(dates2))]
        weak_data = pd.DataFrame({'date': dates2, 'close': prices2, 'volume': [1000000] * len(dates2)})

        strong_result = factor.calculate(strong_data, 'STRONG')
        weak_result = factor.calculate(weak_data, 'WEAK')

        assert strong_result is not None
        assert weak_result is not None

        # Stronger short-term momentum = higher raw_value
        assert strong_result.raw_value > weak_result.raw_value

    def test_insufficient_data(self):
        """Test handling of insufficient data (<30 days)."""
        factor = ShortTermMomentumFactor()
        dates = pd.date_range('2024-01-01', '2024-01-20', freq='D')
        data = pd.DataFrame({'date': dates, 'close': [100.0] * len(dates)})

        result = factor.calculate(data, '005930')
        assert result is None

    def test_minimal_data(self):
        """Test calculation with minimal valid data (exactly 30 days)."""
        factor = ShortTermMomentumFactor()
        dates = pd.date_range('2024-01-01', '2024-01-30', freq='D')
        prices = [100 + i * 0.3 for i in range(len(dates))]
        data = pd.DataFrame({'date': dates, 'close': prices, 'volume': [1000000] * len(dates)})

        result = factor.calculate(data, '005930')
        # Should work with exactly 30 days
        assert result is not None

    def test_confidence_score(self):
        """Test confidence score calculation."""
        factor = ShortTermMomentumFactor()
        dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        prices = [100 + i * 0.3 for i in range(len(dates))]
        data = pd.DataFrame({'date': dates, 'close': prices, 'volume': [1000000] * len(dates)})

        result = factor.calculate(data, '005930')

        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        factor = ShortTermMomentumFactor()
        empty_df = pd.DataFrame(columns=['date', 'close'])

        result = factor.calculate(empty_df, '005930')
        assert result is None
