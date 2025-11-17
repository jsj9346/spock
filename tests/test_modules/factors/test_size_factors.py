#!/usr/bin/env python3
"""
Test Size Factors - PostgreSQL-based Tests

Tests for 3 Size factors:
- MarketCapFactor: Market capitalization with small-cap tilt
- LiquidityFactor: Average daily trading volume
- FloatFactor: Free float percentage

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/test_modules/factors/test_size_factors.py -v
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import date

from modules.factors.size_factors import (
    MarketCapFactor,
    LiquidityFactor,
    FloatFactor
)
from modules.factors.factor_base import FactorCategory


# ============================================================================
# MarketCapFactor Tests
# ============================================================================

class TestMarketCapFactor:
    """Test MarketCapFactor implementation."""

    def test_initialization(self):
        """Test MarketCapFactor initialization."""
        # Given / When
        factor = MarketCapFactor()

        # Then
        assert factor.name == "Market_Cap"
        assert factor.category == FactorCategory.SIZE
        assert factor.lookback_days == 1
        assert factor.min_required_days == 1

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_large_cap(self, mock_db_manager):
        """Test market cap calculation for large-cap stock."""
        # Given: Large cap (>10T KRW) - Samsung Electronics
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (500_000_000_000_000, 100_000_000, 5_000_000, 2024)  # market_cap, shares, price, fiscal_year
        ]
        mock_db_manager.return_value = mock_db

        factor = MarketCapFactor()

        # When
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == 'Market_Cap'
        # Negative value for small-cap tilt: -log10(500T / 1T) = -log10(500) ≈ -2.7
        assert result.raw_value < 0  # Negative for large cap
        assert result.confidence == 0.95
        assert result.metadata['category'] == "Large Cap"
        assert result.metadata['market_cap_trillion'] == 500.0
        assert result.metadata['fiscal_year'] == 2024

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_small_cap(self, mock_db_manager):
        """Test market cap calculation for small-cap stock."""
        # Given: Small cap (<1T KRW)
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (500_000_000_000, 10_000_000, 50_000, 2024)  # 500B KRW
        ]
        mock_db_manager.return_value = mock_db

        factor = MarketCapFactor()

        # When
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then
        assert result is not None
        # Negative value for small-cap tilt: -log10(0.5T / 1T) = -log10(0.5) ≈ 0.3 (positive!)
        assert result.raw_value > 0  # Positive for small cap (small-cap tilt)
        assert result.metadata['category'] == "Small Cap"
        assert result.metadata['market_cap_trillion'] == 0.5

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """Test calculation when no market cap data available."""
        # Given: No database results
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = MarketCapFactor()

        # When
        result = factor.calculate(data=None, ticker='999999', region='KR')

        # Then
        assert result is None


# ============================================================================
# LiquidityFactor Tests
# ============================================================================

class TestLiquidityFactor:
    """Test LiquidityFactor implementation."""

    def test_initialization(self):
        """Test LiquidityFactor initialization."""
        # Given / When
        factor = LiquidityFactor()

        # Then
        assert factor.name == "Liquidity"
        assert factor.category == FactorCategory.SIZE
        assert factor.lookback_days == 30
        assert factor.min_required_days == 20

    def test_calculate_high_liquidity(self):
        """Test liquidity calculation for high-liquidity stock."""
        # Given: 30 days of high-volume data
        data = pd.DataFrame({
            'volume': [1_000_000] * 30,  # 1M shares/day
            'close': [50_000] * 30       # 50,000 KRW/share
        })

        factor = LiquidityFactor()

        # When
        result = factor.calculate(data=data, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == 'Liquidity'
        # avg_liquidity = 1M * 50,000 = 50B KRW/day
        # factor_value = log10(50B / 100M) = log10(500) ≈ 2.7
        assert result.raw_value > 2.0
        assert result.confidence == 0.85
        assert result.metadata['category'] == "High Liquidity"
        assert result.metadata['avg_liquidity_billion'] == 500.0
        assert result.metadata['days_calculated'] == 30

    def test_calculate_low_liquidity(self):
        """Test liquidity calculation for low-liquidity stock."""
        # Given: 30 days of low-volume data
        data = pd.DataFrame({
            'volume': [10_000] * 30,    # 10K shares/day
            'close': [5_000] * 30       # 5,000 KRW/share
        })

        factor = LiquidityFactor()

        # When
        result = factor.calculate(data=data, ticker='000660', region='KR')

        # Then
        assert result is not None
        # avg_liquidity = 10K * 5,000 = 50M KRW/day
        # factor_value = log10(50M / 100M) = log10(0.5) ≈ -0.3
        assert result.raw_value < 0
        assert result.metadata['category'] == "Low Liquidity"

    def test_calculate_insufficient_data(self):
        """Test calculation with insufficient data."""
        # Given: Only 10 days of data (< min_required_days=20)
        data = pd.DataFrame({
            'volume': [100_000] * 10,
            'close': [10_000] * 10
        })

        factor = LiquidityFactor()

        # When
        result = factor.calculate(data=data, ticker='000660', region='KR')

        # Then
        assert result is None

    def test_calculate_missing_columns(self):
        """Test calculation with missing required columns."""
        # Given: DataFrame without volume column
        data = pd.DataFrame({
            'close': [10_000] * 30
        })

        factor = LiquidityFactor()

        # When
        result = factor.calculate(data=data, ticker='000660', region='KR')

        # Then
        assert result is None


# ============================================================================
# FloatFactor Tests
# ============================================================================

class TestFloatFactor:
    """Test FloatFactor implementation."""

    def test_initialization(self):
        """Test FloatFactor initialization."""
        # Given / When
        factor = FloatFactor()

        # Then
        assert factor.name == "Free_Float"
        assert factor.category == FactorCategory.SIZE
        assert factor.lookback_days == 1
        assert factor.min_required_days == 1

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_high_float(self, mock_db_manager):
        """Test free float calculation for high-float stock."""
        # Given: High float (>50%)
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (75.5, 100_000_000, 2024)  # free_float_pct, shares_outstanding, fiscal_year
        ]
        mock_db_manager.return_value = mock_db

        factor = FloatFactor()

        # When
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then
        assert result is not None
        assert result.ticker == '005930'
        assert result.factor_name == 'Free_Float'
        assert result.raw_value == 75.5
        assert result.confidence == 0.80
        assert result.metadata['free_float_pct'] == 75.5
        assert result.metadata['category'] == "High Float"
        assert result.metadata['fiscal_year'] == 2024

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_low_float(self, mock_db_manager):
        """Test free float calculation for low-float stock."""
        # Given: Low float (<30%)
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            (25.0, 50_000_000, 2024)
        ]
        mock_db_manager.return_value = mock_db

        factor = FloatFactor()

        # When
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then
        assert result is not None
        assert result.raw_value == 25.0
        assert result.metadata['category'] == "Low Float"

    @patch('modules.factors.size_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """Test calculation when no float data available."""
        # Given: No database results
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = FloatFactor()

        # When
        result = factor.calculate(data=None, ticker='999999', region='KR')

        # Then
        assert result is None
