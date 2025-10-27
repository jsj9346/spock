#!/usr/bin/env python3
"""
test_factors.py - Unit Tests for Factor Library

Tests:
1. FactorBase abstract class validation
2. TwelveMonthMomentumFactor calculation
3. RSIMomentumFactor calculation
4. HistoricalVolatilityFactor calculation
5. MaxDrawdownFactor calculation
6. Data validation and error handling
7. Z-score and percentile calculations

Usage:
    python3 tests/test_factors.py
    pytest tests/test_factors.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from modules.factors import (
    FactorBase,
    FactorResult,
    FactorCategory,
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor,
    HistoricalVolatilityFactor,
    MaxDrawdownFactor
)


class TestFactorBase(unittest.TestCase):
    """Test FactorBase abstract class and utilities"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a simple concrete implementation for testing
        class TestFactor(FactorBase):
            def calculate(self, data: pd.DataFrame, ticker: str):
                return FactorResult(
                    ticker=ticker,
                    factor_name=self.name,
                    raw_value=10.0,
                    z_score=0.0,
                    percentile=50.0,
                    confidence=0.9,
                    metadata={}
                )

            def get_required_columns(self):
                return ['close', 'volume']

        self.factor = TestFactor(
            name="Test",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,
            min_required_days=30
        )

    def test_z_score_calculation(self):
        """Test z-score standardization"""
        values = np.array([10, 20, 30, 40, 50])
        z_score = self.factor._calculate_z_score(30, values)

        # Z-score should be 0 for median value
        self.assertAlmostEqual(z_score, 0.0, places=1)

    def test_z_score_extreme_capping(self):
        """Test z-score capping at ±3 sigma"""
        values = np.array([1, 2, 3, 4, 5])
        z_score = self.factor._calculate_z_score(1000, values)

        # Should be capped at 3.0
        self.assertEqual(z_score, 3.0)

    def test_percentile_calculation(self):
        """Test percentile ranking"""
        values = np.array([10, 20, 30, 40, 50])
        percentile = self.factor._calculate_percentile(30, values)

        # 30 is at 40th percentile (2 out of 5 values are less than 30)
        self.assertAlmostEqual(percentile, 40.0, places=0)

    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        confidence = self.factor._calculate_confidence(
            data_length=60,
            null_ratio=0.1
        )

        # Should be high confidence (sufficient data, low NULL ratio)
        self.assertGreater(confidence, 0.8)

    def test_null_ratio_calculation(self):
        """Test NULL ratio calculation"""
        data = pd.DataFrame({
            'close': [100, None, 110, None],
            'volume': [1000, 2000, None, 3000]
        })

        null_ratio = self.factor._calculate_null_ratio(data, ['close', 'volume'])

        # 3 NULLs out of 8 cells = 37.5%
        self.assertAlmostEqual(null_ratio, 0.375, places=2)

    def test_data_validation_empty(self):
        """Test data validation with empty DataFrame"""
        data = pd.DataFrame()
        is_valid, error_msg = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn("Empty", error_msg)

    def test_data_validation_insufficient_length(self):
        """Test data validation with insufficient data length"""
        data = pd.DataFrame({
            'close': [100] * 10,
            'volume': [1000] * 10
        })

        is_valid, error_msg = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn("Insufficient data", error_msg)

    def test_data_validation_missing_columns(self):
        """Test data validation with missing columns"""
        data = pd.DataFrame({
            'close': [100] * 50
            # Missing 'volume' column
        })

        is_valid, error_msg = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn("Missing columns", error_msg)

    def test_data_validation_success(self):
        """Test data validation with valid data"""
        data = pd.DataFrame({
            'close': [100] * 50,
            'volume': [1000] * 50
        })

        is_valid, error_msg = self.factor.validate_data(data)

        self.assertTrue(is_valid)
        self.assertEqual(error_msg, "Valid")


class TestTwelveMonthMomentumFactor(unittest.TestCase):
    """Test TwelveMonthMomentumFactor"""

    def setUp(self):
        """Set up test fixtures"""
        self.factor = TwelveMonthMomentumFactor()

        # Create synthetic data with upward momentum
        dates = pd.date_range(end=datetime.now(), periods=300, freq='D')
        np.random.seed(42)

        # Simulate upward trending stock price
        base_price = 100
        trend = np.linspace(0, 30, 300)  # 30% upward trend over 300 days
        noise = np.random.normal(0, 2, 300)
        prices = base_price + trend + noise

        self.upward_data = pd.DataFrame({
            'date': dates,
            'close': prices,
            'volume': np.random.randint(1000000, 5000000, 300),
            'ma20': pd.Series(prices).rolling(20).mean(),
            'ma60': pd.Series(prices).rolling(60).mean()
        })

    def test_calculation_success(self):
        """Test successful momentum calculation"""
        result = self.factor.calculate(self.upward_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, 'TEST001')
        self.assertEqual(result.factor_name, '12M_Momentum')
        self.assertGreater(result.raw_value, 0)  # Should be positive momentum
        self.assertGreater(result.confidence, 0.7)  # High confidence

    def test_insufficient_data(self):
        """Test with insufficient data"""
        short_data = self.upward_data.head(100)  # Only 100 days (need 252)
        result = self.factor.calculate(short_data, ticker='TEST001')

        self.assertIsNone(result)

    def test_metadata_completeness(self):
        """Test that metadata contains required fields"""
        result = self.factor.calculate(self.upward_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('base_momentum_return', result.metadata)
        self.assertIn('volume_ratio', result.metadata)
        self.assertIn('volume_weight', result.metadata)
        self.assertIn('trend_score', result.metadata)
        self.assertIn('final_momentum', result.metadata)

    def test_required_columns(self):
        """Test required columns specification"""
        required = self.factor.get_required_columns()

        self.assertIn('date', required)
        self.assertIn('close', required)
        self.assertIn('volume', required)
        self.assertIn('ma20', required)
        self.assertIn('ma60', required)


class TestRSIMomentumFactor(unittest.TestCase):
    """Test RSIMomentumFactor"""

    def setUp(self):
        """Set up test fixtures"""
        self.factor = RSIMomentumFactor()

        # Create data with RSI in optimal zone (50-70)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

        self.optimal_rsi_data = pd.DataFrame({
            'date': dates,
            'close': np.random.uniform(100, 110, 100),
            'rsi_14': [60.0] * 100  # Optimal RSI value
        })

        self.overbought_data = pd.DataFrame({
            'date': dates,
            'close': np.random.uniform(100, 110, 100),
            'rsi_14': [85.0] * 100  # Overbought
        })

    def test_optimal_rsi_zone(self):
        """Test RSI in optimal momentum zone"""
        result = self.factor.calculate(self.optimal_rsi_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertEqual(result.raw_value, 100.0)  # Maximum score
        self.assertEqual(result.metadata['rsi_zone'], 'bullish_momentum')

    def test_overbought_zone(self):
        """Test RSI in overbought zone"""
        result = self.factor.calculate(self.overbought_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertLess(result.raw_value, 100.0)  # Penalized score
        self.assertEqual(result.metadata['rsi_zone'], 'overbought')

    def test_missing_rsi_column(self):
        """Test with missing RSI column"""
        data = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=100, freq='D'),
            'close': [100] * 100
            # Missing rsi_14 column
        })

        result = self.factor.calculate(data, ticker='TEST001')

        self.assertIsNone(result)

    def test_rsi_column_variants(self):
        """Test that factor accepts both rsi_14 and rsi columns"""
        data_rsi = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=100, freq='D'),
            'close': [100] * 100,
            'rsi': [60.0] * 100  # Using 'rsi' instead of 'rsi_14'
        })

        result = self.factor.calculate(data_rsi, ticker='TEST001')

        # Should work with 'rsi' column as well
        # Note: Current implementation prioritizes 'rsi_14', so this might fail
        # This test documents expected behavior
        self.assertIsNotNone(result)


class TestHistoricalVolatilityFactor(unittest.TestCase):
    """Test HistoricalVolatilityFactor"""

    def setUp(self):
        """Set up test fixtures"""
        self.factor = HistoricalVolatilityFactor()

        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

        # Low volatility stock (stable prices)
        self.low_vol_data = pd.DataFrame({
            'date': dates,
            'close': 100 + np.random.normal(0, 1, 100)  # Low std dev
        })

        # High volatility stock (volatile prices)
        self.high_vol_data = pd.DataFrame({
            'date': dates,
            'close': 100 + np.random.normal(0, 10, 100)  # High std dev
        })

    def test_low_volatility(self):
        """Test low volatility stock (defensive)"""
        result = self.factor.calculate(self.low_vol_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertLess(result.metadata['annualized_volatility'], 50.0)  # Low vol
        # Factor value is negated, so low vol = higher (less negative) value
        self.assertGreater(result.raw_value, -50.0)

    def test_high_volatility(self):
        """Test high volatility stock (aggressive)"""
        result = self.factor.calculate(self.high_vol_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertGreater(result.metadata['annualized_volatility'], 50.0)  # High vol
        # Factor value is negated, so high vol = lower (more negative) value
        self.assertLess(result.raw_value, -50.0)

    def test_downside_volatility(self):
        """Test downside volatility calculation"""
        result = self.factor.calculate(self.high_vol_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('downside_volatility', result.metadata)
        self.assertGreater(result.metadata['downside_volatility'], 0.0)

    def test_metadata_completeness(self):
        """Test metadata contains required fields"""
        result = self.factor.calculate(self.low_vol_data, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('annualized_volatility', result.metadata)
        self.assertIn('downside_volatility', result.metadata)
        self.assertIn('daily_std', result.metadata)
        self.assertIn('negative_days', result.metadata)


class TestMaxDrawdownFactor(unittest.TestCase):
    """Test MaxDrawdownFactor"""

    def setUp(self):
        """Set up test fixtures"""
        self.factor = MaxDrawdownFactor()

        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

        # Stock with significant drawdown
        prices_with_drawdown = [100] * 20 + list(range(100, 70, -1)) + [70] * 50
        self.drawdown_data = pd.DataFrame({
            'date': dates,
            'close': prices_with_drawdown
        })

        # Stock with no drawdown (monotonic increase)
        self.no_drawdown_data = pd.DataFrame({
            'date': dates,
            'close': np.linspace(100, 120, 100)
        })

    def test_drawdown_calculation(self):
        """Test drawdown calculation with known drawdown"""
        result = self.factor.calculate(self.drawdown_data, ticker='TEST001')

        self.assertIsNotNone(result)
        # Drawdown from 100 to 70 = -30%
        self.assertAlmostEqual(result.metadata['max_drawdown'], -30.0, places=0)

    def test_no_drawdown(self):
        """Test with stock that has no drawdown"""
        result = self.factor.calculate(self.no_drawdown_data, ticker='TEST001')

        self.assertIsNotNone(result)
        # Should have minimal drawdown
        self.assertGreater(result.metadata['max_drawdown'], -5.0)

    def test_recovery_days(self):
        """Test recovery days calculation"""
        result = self.factor.calculate(self.drawdown_data, ticker='TEST001')

        self.assertIsNotNone(result)
        # Should not have recovered (price stays at 70)
        self.assertIsNone(result.metadata['recovery_days'])


class TestFactorIntegration(unittest.TestCase):
    """Integration tests for multiple factors"""

    def setUp(self):
        """Set up realistic test data (Samsung-like)"""
        # Create 300 days of realistic OHLCV data
        dates = pd.date_range(end=datetime.now(), periods=300, freq='D')
        np.random.seed(42)

        # Simulate realistic price movement
        base_price = 60000  # Similar to Samsung stock price
        trend = np.linspace(0, 10000, 300)
        noise = np.random.normal(0, 1000, 300)
        prices = base_price + trend + noise

        # Calculate RSI (simplified)
        returns = pd.Series(prices).pct_change()
        gains = returns.clip(lower=0)
        losses = -returns.clip(upper=0)
        avg_gains = gains.rolling(14).mean()
        avg_losses = losses.rolling(14).mean()
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        self.samsung_like_data = pd.DataFrame({
            'date': dates,
            'close': prices,
            'volume': np.random.randint(5000000, 20000000, 300),
            'ma20': pd.Series(prices).rolling(20).mean(),
            'ma60': pd.Series(prices).rolling(60).mean(),
            'rsi_14': rsi
        })

    def test_multiple_factors(self):
        """Test calculating multiple factors on same data"""
        momentum_factor = TwelveMonthMomentumFactor()
        rsi_factor = RSIMomentumFactor()
        vol_factor = HistoricalVolatilityFactor()

        momentum_result = momentum_factor.calculate(self.samsung_like_data, ticker='005930')
        rsi_result = rsi_factor.calculate(self.samsung_like_data, ticker='005930')
        vol_result = vol_factor.calculate(self.samsung_like_data, ticker='005930')

        # All should succeed
        self.assertIsNotNone(momentum_result)
        self.assertIsNotNone(rsi_result)
        self.assertIsNotNone(vol_result)

        # All should have reasonable confidence
        self.assertGreater(momentum_result.confidence, 0.5)
        self.assertGreater(rsi_result.confidence, 0.5)
        self.assertGreater(vol_result.confidence, 0.5)

    def test_factor_consistency(self):
        """Test that factor results are consistent across runs"""
        momentum_factor = TwelveMonthMomentumFactor()

        result1 = momentum_factor.calculate(self.samsung_like_data, ticker='005930')
        result2 = momentum_factor.calculate(self.samsung_like_data, ticker='005930')

        # Should get identical results
        self.assertEqual(result1.raw_value, result2.raw_value)
        self.assertEqual(result1.confidence, result2.confidence)


def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()
