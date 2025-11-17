#!/usr/bin/env python3
"""
Test Low-Volatility Factors

Tests for 3 Low-Vol factors:
- HistoricalVolatilityFactor: Annualized volatility
- BetaFactor: Market sensitivity (KOSPI benchmark)
- MaxDrawdownFactor: Maximum peak-to-trough decline

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/test_modules/factors/test_low_vol_factors.py -v
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from datetime import date, timedelta

from modules.factors.low_vol_factors import (
    HistoricalVolatilityFactor,
    BetaFactor,
    MaxDrawdownFactor
)
from modules.factors.factor_base import FactorCategory


# ============================================================================
# HistoricalVolatilityFactor Tests
# ============================================================================

class TestHistoricalVolatilityFactor:
    """Test HistoricalVolatilityFactor implementation."""

    def test_initialization(self):
        """Test HistoricalVolatilityFactor initialization."""
        # Given / When
        factor = HistoricalVolatilityFactor()

        # Then
        assert factor.name == "Historical_Volatility"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 30
        assert factor.min_required_days == 30

    def test_calculate_low_volatility(self):
        """Test calculation for low-volatility stock."""
        # Given: Stable stock with low volatility
        dates = pd.date_range(start='2024-01-01', periods=60)
        np.random.seed(42)
        # Low volatility: 1% daily std
        returns = np.random.normal(0.0001, 0.01, 60)
        prices = 100 * np.cumprod(1 + returns)

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        factor = HistoricalVolatilityFactor()

        # When
        result = factor.calculate(data=data, ticker='000660')

        # Then
        assert result is not None
        assert result.ticker == '000660'
        assert result.factor_name == 'Historical_Volatility'
        # Factor value is negated: higher value = lower volatility
        assert result.raw_value < 0  # Negative annualized volatility
        assert 'annualized_volatility' in result.metadata
        assert result.metadata['annualized_volatility'] < 20  # Low vol stock

    def test_calculate_high_volatility(self):
        """Test calculation for high-volatility stock."""
        # Given: Volatile stock
        dates = pd.date_range(start='2024-01-01', periods=60)
        np.random.seed(42)
        # High volatility: 5% daily std
        returns = np.random.normal(0.0001, 0.05, 60)
        prices = 100 * np.cumprod(1 + returns)

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        factor = HistoricalVolatilityFactor()

        # When
        result = factor.calculate(data=data, ticker='005930')

        # Then
        assert result is not None
        # Higher absolute value = higher volatility = lower defensive score
        assert abs(result.raw_value) > 30  # High annualized volatility
        assert result.metadata['annualized_volatility'] > 30

    def test_calculate_insufficient_data(self):
        """Test calculation with insufficient data."""
        # Given: Only 20 days of data (< min_required_days=30)
        data = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=20),
            'close': np.random.uniform(100, 110, 20)
        })

        factor = HistoricalVolatilityFactor()

        # When
        result = factor.calculate(data=data, ticker='000660')

        # Then
        assert result is None


# ============================================================================
# BetaFactor Tests
# ============================================================================

class TestBetaFactor:
    """Test BetaFactor implementation."""

    def test_initialization(self):
        """Test BetaFactor initialization."""
        # Given / When
        factor = BetaFactor()

        # Then
        assert factor.name == "Beta"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 252
        assert factor.min_required_days == 60

    @patch('modules.factors.low_vol_factors.PostgresDatabaseManager')
    def test_calculate_low_beta(self, mock_db_manager):
        """Test beta calculation for defensive stock (beta < 1.0)."""
        # Given: Stock with low beta (defensive)
        dates = pd.date_range(start='2024-01-01', periods=100)
        np.random.seed(42)

        # Market returns (mean=0.05%, std=1%)
        market_returns = np.random.normal(0.0005, 0.01, 100)
        market_prices = 2500 * np.cumprod(1 + market_returns)

        # Stock returns: 60% correlation with market, lower volatility
        stock_returns = 0.6 * market_returns + 0.4 * np.random.normal(0.0003, 0.005, 100)
        stock_prices = 50000 * np.cumprod(1 + stock_returns)

        data = pd.DataFrame({
            'date': dates,
            'close': stock_prices
        })

        # Mock database response with market data
        market_data = [(date, price) for date, price in zip(dates, market_prices)]
        mock_db = Mock()
        mock_db.execute_query.return_value = market_data
        mock_db_manager.return_value = mock_db

        factor = BetaFactor()

        # When
        result = factor.calculate(data=data, ticker='000660', region='KR')

        # Then
        assert result is not None
        assert result.ticker == '000660'
        assert result.factor_name == 'Beta'
        # Beta should be < 1.0 (defensive)
        assert result.metadata['beta'] < 1.0
        # Factor value is negated: lower beta = higher score
        assert result.raw_value > -1.0  # -beta for defensive ranking
        assert result.metadata['category'] == "Low Beta (Defensive)"
        assert result.metadata['market_index'] == 'KOSPI'

    @patch('modules.factors.low_vol_factors.PostgresDatabaseManager')
    def test_calculate_high_beta(self, mock_db_manager):
        """Test beta calculation for aggressive stock (beta > 1.0)."""
        # Given: Stock with high beta (aggressive)
        dates = pd.date_range(start='2024-01-01', periods=100)
        np.random.seed(42)

        # Market returns
        market_returns = np.random.normal(0.0005, 0.01, 100)
        market_prices = 2500 * np.cumprod(1 + market_returns)

        # Stock returns: high correlation, higher volatility (1.5x market)
        stock_returns = 1.5 * market_returns + 0.2 * np.random.normal(0, 0.01, 100)
        stock_prices = 50000 * np.cumprod(1 + stock_returns)

        data = pd.DataFrame({
            'date': dates,
            'close': stock_prices
        })

        # Mock database response
        market_data = [(date, price) for date, price in zip(dates, market_prices)]
        mock_db = Mock()
        mock_db.execute_query.return_value = market_data
        mock_db_manager.return_value = mock_db

        factor = BetaFactor()

        # When
        result = factor.calculate(data=data, ticker='005930', region='KR')

        # Then
        assert result is not None
        # Beta should be > 1.0 (aggressive)
        assert result.metadata['beta'] > 1.0
        # Negated beta for defensive ranking (lower score for high beta)
        assert result.raw_value < -1.0
        assert result.metadata['category'] == "High Beta (Aggressive)"

    @patch('modules.factors.low_vol_factors.PostgresDatabaseManager')
    def test_calculate_insufficient_market_data(self, mock_db_manager):
        """Test calculation when market data is insufficient."""
        # Given: Stock data but no market data
        data = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=100),
            'close': np.random.uniform(50000, 60000, 100)
        })

        # Mock: No market data available
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = BetaFactor()

        # When
        result = factor.calculate(data=data, ticker='000660', region='KR')

        # Then
        assert result is None


# ============================================================================
# MaxDrawdownFactor Tests
# ============================================================================

class TestMaxDrawdownFactor:
    """Test MaxDrawdownFactor implementation."""

    def test_initialization(self):
        """Test MaxDrawdownFactor initialization."""
        # Given / When
        factor = MaxDrawdownFactor()

        # Then
        assert factor.name == "Max_Drawdown"
        assert factor.category == FactorCategory.LOW_VOL
        assert factor.lookback_days == 252
        assert factor.min_required_days == 30

    def test_calculate_small_drawdown(self):
        """Test calculation for stock with small drawdown (defensive)."""
        # Given: Stable upward trend with small drawdown
        dates = pd.date_range(start='2024-01-01', periods=100)

        # Price increases steadily with small dip
        prices = np.linspace(100, 150, 100)
        # Create a small 5% drawdown at day 50
        prices[50:60] *= 0.95

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        factor = MaxDrawdownFactor()

        # When
        result = factor.calculate(data=data, ticker='000660')

        # Then
        assert result is not None
        assert result.ticker == '000660'
        assert result.factor_name == 'Max_Drawdown'
        # Max drawdown should be small (around -5%)
        assert result.metadata['max_drawdown'] < 0  # Negative value
        assert result.metadata['max_drawdown'] > -10  # Small drawdown
        # Factor value is negated: higher value = smaller drawdown (defensive)
        assert result.raw_value > 0  # Positive after negating small drawdown

    def test_calculate_large_drawdown(self):
        """Test calculation for stock with large drawdown (risky)."""
        # Given: Stock with significant crash
        dates = pd.date_range(start='2024-01-01', periods=100)

        # Price crashes 40% then recovers
        prices = np.ones(100) * 100
        prices[:30] = 100  # Peak
        prices[30:50] = 60  # 40% drawdown
        prices[50:] = np.linspace(60, 90, 50)  # Partial recovery

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        factor = MaxDrawdownFactor()

        # When
        result = factor.calculate(data=data, ticker='005930')

        # Then
        assert result is not None
        # Max drawdown should be around -40%
        assert result.metadata['max_drawdown'] < -30
        assert result.metadata['max_drawdown'] > -50
        # Factor value is negated: -(-40%) = +40%
        # Lower score for risky stock (large drawdown results in smaller factor value after comparison)
        assert result.raw_value > 30  # Positive value after negating -40%

    def test_calculate_with_recovery(self):
        """Test recovery time calculation."""
        # Given: Stock with drawdown and full recovery
        dates = pd.date_range(start='2024-01-01', periods=100)

        prices = np.ones(100) * 100
        prices[20:40] = 80  # 20% drawdown
        prices[40:] = 100  # Full recovery

        data = pd.DataFrame({
            'date': dates,
            'close': prices
        })

        factor = MaxDrawdownFactor()

        # When
        result = factor.calculate(data=data, ticker='000660')

        # Then
        assert result is not None
        assert result.metadata['recovery_days'] is not None
        assert result.metadata['recovery_days'] > 0
        # Current drawdown should be 0 (fully recovered)
        assert abs(result.metadata['current_drawdown']) < 1  # Near 0

    def test_calculate_insufficient_data(self):
        """Test calculation with insufficient data."""
        # Given: Only 50 days (< min 60 for reliable drawdown)
        data = pd.DataFrame({
            'date': pd.date_range(start='2024-01-01', periods=50),
            'close': np.random.uniform(100, 110, 50)
        })

        factor = MaxDrawdownFactor()

        # When
        result = factor.calculate(data=data, ticker='000660')

        # Then
        assert result is None
