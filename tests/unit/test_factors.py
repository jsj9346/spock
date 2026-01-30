#!/usr/bin/env python3
"""
test_factors.py - Unit Tests for Factors Module

Tests for:
- FactorCategory enum
- FactorResult dataclass
- FactorBase abstract class methods
- Factor utility functions (z-score, percentile, confidence)

Coverage target: factors/* (~1400+ Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

from modules.factors.factor_base import (
    FactorCategory,
    FactorResult,
    FactorBase
)


class TestFactorCategory(unittest.TestCase):
    """Test FactorCategory enum"""

    def test_momentum_category(self):
        """Test MOMENTUM category"""
        self.assertEqual(FactorCategory.MOMENTUM.value, "momentum")

    def test_value_category(self):
        """Test VALUE category"""
        self.assertEqual(FactorCategory.VALUE.value, "value")

    def test_quality_category(self):
        """Test QUALITY category"""
        self.assertEqual(FactorCategory.QUALITY.value, "quality")

    def test_low_vol_category(self):
        """Test LOW_VOL category"""
        self.assertEqual(FactorCategory.LOW_VOL.value, "low_volatility")

    def test_size_category(self):
        """Test SIZE category"""
        self.assertEqual(FactorCategory.SIZE.value, "size")

    def test_growth_category(self):
        """Test GROWTH category"""
        self.assertEqual(FactorCategory.GROWTH.value, "growth")

    def test_efficiency_category(self):
        """Test EFFICIENCY category"""
        self.assertEqual(FactorCategory.EFFICIENCY.value, "efficiency")

    def test_all_categories(self):
        """Test all categories are defined"""
        expected = ['MOMENTUM', 'VALUE', 'QUALITY', 'LOW_VOL', 'SIZE', 'GROWTH', 'EFFICIENCY']
        actual = [c.name for c in FactorCategory]
        self.assertEqual(sorted(actual), sorted(expected))


class TestFactorResult(unittest.TestCase):
    """Test FactorResult dataclass"""

    def test_basic_creation(self):
        """Test basic FactorResult creation"""
        result = FactorResult(
            ticker='005930',
            factor_name='12M_Momentum',
            raw_value=0.25,
            z_score=1.5,
            percentile=85.0,
            confidence=0.9
        )

        self.assertEqual(result.ticker, '005930')
        self.assertEqual(result.factor_name, '12M_Momentum')
        self.assertAlmostEqual(result.raw_value, 0.25)
        self.assertAlmostEqual(result.z_score, 1.5)
        self.assertAlmostEqual(result.percentile, 85.0)
        self.assertAlmostEqual(result.confidence, 0.9)

    def test_with_metadata(self):
        """Test FactorResult with metadata"""
        metadata = {'data_quality': 'good', 'sample_size': 250}
        result = FactorResult(
            ticker='005930',
            factor_name='PE_Ratio',
            raw_value=15.5,
            z_score=-0.5,
            percentile=35.0,
            confidence=0.85,
            metadata=metadata
        )

        self.assertEqual(result.metadata['data_quality'], 'good')
        self.assertEqual(result.metadata['sample_size'], 250)

    def test_percentile_clamping(self):
        """Test percentile is clamped to 0-100"""
        # Over 100
        result = FactorResult(
            ticker='TEST',
            factor_name='Test',
            raw_value=1.0,
            z_score=1.0,
            percentile=150.0,  # Over 100
            confidence=0.5
        )
        self.assertEqual(result.percentile, 100.0)

        # Under 0
        result2 = FactorResult(
            ticker='TEST',
            factor_name='Test',
            raw_value=1.0,
            z_score=1.0,
            percentile=-10.0,  # Under 0
            confidence=0.5
        )
        self.assertEqual(result2.percentile, 0.0)

    def test_confidence_clamping(self):
        """Test confidence is clamped to 0-1"""
        # Over 1
        result = FactorResult(
            ticker='TEST',
            factor_name='Test',
            raw_value=1.0,
            z_score=1.0,
            percentile=50.0,
            confidence=1.5  # Over 1
        )
        self.assertEqual(result.confidence, 1.0)

        # Under 0
        result2 = FactorResult(
            ticker='TEST',
            factor_name='Test',
            raw_value=1.0,
            z_score=1.0,
            percentile=50.0,
            confidence=-0.5  # Under 0
        )
        self.assertEqual(result2.confidence, 0.0)

    def test_to_dict(self):
        """Test to_dict conversion"""
        result = FactorResult(
            ticker='005930',
            factor_name='12M_Momentum',
            raw_value=0.25,
            z_score=1.5,
            percentile=85.0,
            confidence=0.9,
            metadata={'test': 'value'}
        )

        d = result.to_dict()

        self.assertEqual(d['ticker'], '005930')
        self.assertEqual(d['factor_name'], '12M_Momentum')
        self.assertAlmostEqual(d['raw_value'], 0.25)
        self.assertAlmostEqual(d['z_score'], 1.5)
        self.assertIn('calculation_date', d)

    def test_default_calculation_date(self):
        """Test default calculation_date is set"""
        result = FactorResult(
            ticker='TEST',
            factor_name='Test',
            raw_value=1.0,
            z_score=1.0,
            percentile=50.0,
            confidence=0.5
        )

        self.assertIsInstance(result.calculation_date, datetime)


class ConcreteFactor(FactorBase):
    """Concrete implementation for testing FactorBase"""

    def calculate(self, data: pd.DataFrame, ticker: str):
        """Simple momentum calculation for testing"""
        if data.empty or len(data) < self.min_required_days:
            return None

        first_price = data['close'].iloc[0]
        last_price = data['close'].iloc[-1]
        raw_value = (last_price - first_price) / first_price

        return FactorResult(
            ticker=ticker,
            factor_name=self.name,
            raw_value=raw_value,
            z_score=0.0,  # Would be calculated across universe
            percentile=50.0,
            confidence=0.9
        )

    def get_required_columns(self):
        return ['close', 'volume']


class TestFactorBase(unittest.TestCase):
    """Test FactorBase abstract class methods"""

    def setUp(self):
        """Create concrete factor for testing"""
        self.factor = ConcreteFactor(
            name='Test_Momentum',
            category=FactorCategory.MOMENTUM,
            lookback_days=250,
            min_required_days=60
        )

    def test_initialization(self):
        """Test factor initialization"""
        self.assertEqual(self.factor.name, 'Test_Momentum')
        self.assertEqual(self.factor.category, FactorCategory.MOMENTUM)
        self.assertEqual(self.factor.lookback_days, 250)
        self.assertEqual(self.factor.min_required_days, 60)

    def test_validate_data_empty(self):
        """Test validate_data with empty DataFrame"""
        data = pd.DataFrame()

        is_valid, message = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn('Empty', message)

    def test_validate_data_insufficient_length(self):
        """Test validate_data with insufficient data"""
        data = pd.DataFrame({
            'close': [100.0] * 30,
            'volume': [1000] * 30
        })

        is_valid, message = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn('Insufficient', message)

    def test_validate_data_missing_columns(self):
        """Test validate_data with missing columns"""
        data = pd.DataFrame({
            'close': [100.0] * 100
            # Missing 'volume' column
        })

        is_valid, message = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn('Missing columns', message)

    def test_validate_data_all_null_column(self):
        """Test validate_data with all-NULL column"""
        data = pd.DataFrame({
            'close': [100.0] * 100,
            'volume': [None] * 100
        })

        is_valid, message = self.factor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn('NULL', message)

    def test_validate_data_valid(self):
        """Test validate_data with valid data"""
        data = pd.DataFrame({
            'close': [100.0 + i for i in range(100)],
            'volume': [1000] * 100
        })

        is_valid, message = self.factor.validate_data(data)

        self.assertTrue(is_valid)
        self.assertEqual(message, 'Valid')

    def test_calculate_z_score(self):
        """Test z-score calculation"""
        value = 110.0
        values = np.array([90.0, 100.0, 110.0, 120.0, 130.0])

        z_score = self.factor._calculate_z_score(value, values)

        # Mean = 110, std ~14.14
        # z = (110 - 110) / 14.14 = 0
        self.assertAlmostEqual(z_score, 0.0, places=1)

    def test_calculate_z_score_positive(self):
        """Test z-score for above average value"""
        value = 130.0
        values = np.array([90.0, 100.0, 110.0, 120.0, 130.0])

        z_score = self.factor._calculate_z_score(value, values)

        self.assertGreater(z_score, 0)

    def test_calculate_z_score_capped(self):
        """Test z-score is capped at ±3"""
        value = 1000.0  # Extreme outlier
        values = np.array([100.0, 101.0, 102.0, 103.0, 104.0])

        z_score = self.factor._calculate_z_score(value, values)

        self.assertEqual(z_score, 3.0)

    def test_calculate_z_score_insufficient_values(self):
        """Test z-score with insufficient values"""
        value = 100.0
        values = np.array([100.0])  # Only 1 value

        z_score = self.factor._calculate_z_score(value, values)

        self.assertEqual(z_score, 0.0)

    def test_calculate_z_score_zero_std(self):
        """Test z-score with zero standard deviation"""
        value = 100.0
        values = np.array([100.0, 100.0, 100.0, 100.0])  # All same

        z_score = self.factor._calculate_z_score(value, values)

        self.assertEqual(z_score, 0.0)

    def test_calculate_percentile(self):
        """Test percentile calculation"""
        value = 30.0
        values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        percentile = self.factor._calculate_percentile(value, values)

        # 2 values below 30 out of 5 = 40%
        self.assertAlmostEqual(percentile, 40.0, places=1)

    def test_calculate_percentile_top(self):
        """Test percentile for top value"""
        value = 100.0
        values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        percentile = self.factor._calculate_percentile(value, values)

        # All 5 values below 100 = 100%
        self.assertEqual(percentile, 100.0)

    def test_calculate_percentile_bottom(self):
        """Test percentile for bottom value"""
        value = 5.0
        values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])

        percentile = self.factor._calculate_percentile(value, values)

        # 0 values below 5 = 0%
        self.assertEqual(percentile, 0.0)

    def test_calculate_percentile_insufficient_values(self):
        """Test percentile with insufficient values"""
        value = 100.0
        values = np.array([100.0])

        percentile = self.factor._calculate_percentile(value, values)

        # Default to 50% (median)
        self.assertEqual(percentile, 50.0)

    def test_calculate_confidence_basic(self):
        """Test basic confidence calculation"""
        confidence = self.factor._calculate_confidence(
            data_length=250,
            null_ratio=0.0
        )

        # Full data (250/250=1.0) * 0.6 + no nulls (1.0) * 0.4 = 1.0
        self.assertAlmostEqual(confidence, 1.0, places=2)

    def test_calculate_confidence_partial_data(self):
        """Test confidence with partial data"""
        confidence = self.factor._calculate_confidence(
            data_length=125,  # Half of lookback_days
            null_ratio=0.0
        )

        # (125/250=0.5) * 0.6 + 1.0 * 0.4 = 0.7
        self.assertAlmostEqual(confidence, 0.7, places=2)

    def test_calculate_confidence_with_nulls(self):
        """Test confidence with null values"""
        confidence = self.factor._calculate_confidence(
            data_length=250,
            null_ratio=0.5  # 50% nulls
        )

        # 1.0 * 0.6 + (1-0.5) * 0.4 = 0.8
        self.assertAlmostEqual(confidence, 0.8, places=2)

    def test_calculate_confidence_with_additional_factors(self):
        """Test confidence with additional factors"""
        confidence = self.factor._calculate_confidence(
            data_length=250,
            null_ratio=0.0,
            additional_factors={'volatility_quality': 0.8, 'trend_strength': 0.6}
        )

        # Base = 1.0, additional = (0.8 + 0.6) / 2 = 0.7
        # Final = 1.0 * 0.7 + 0.7 * 0.3 = 0.91
        self.assertGreater(confidence, 0.8)

    def test_calculate_null_ratio(self):
        """Test null ratio calculation"""
        data = pd.DataFrame({
            'close': [100.0, None, 100.0, 100.0],
            'volume': [1000, 1000, None, 1000]
        })

        null_ratio = self.factor._calculate_null_ratio(data, ['close', 'volume'])

        # 2 nulls out of 8 cells = 0.25
        self.assertAlmostEqual(null_ratio, 0.25, places=2)

    def test_calculate_null_ratio_no_nulls(self):
        """Test null ratio with no nulls"""
        data = pd.DataFrame({
            'close': [100.0] * 10,
            'volume': [1000] * 10
        })

        null_ratio = self.factor._calculate_null_ratio(data, ['close', 'volume'])

        self.assertEqual(null_ratio, 0.0)

    def test_repr(self):
        """Test string representation"""
        repr_str = repr(self.factor)

        self.assertIn('Test_Momentum', repr_str)
        self.assertIn('momentum', repr_str)


class TestFactorCalculation(unittest.TestCase):
    """Test factor calculation with sample data"""

    def setUp(self):
        """Create sample data and factor"""
        self.factor = ConcreteFactor(
            name='Test_Momentum',
            category=FactorCategory.MOMENTUM,
            lookback_days=100,
            min_required_days=30
        )

    def test_calculate_with_valid_data(self):
        """Test calculation with valid data"""
        data = pd.DataFrame({
            'close': [100.0 + i for i in range(100)],
            'volume': [1000] * 100
        })

        result = self.factor.calculate(data, '005930')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, '005930')
        self.assertGreater(result.raw_value, 0)  # Uptrend

    def test_calculate_with_empty_data(self):
        """Test calculation with empty data"""
        data = pd.DataFrame()

        result = self.factor.calculate(data, '005930')

        self.assertIsNone(result)

    def test_calculate_with_insufficient_data(self):
        """Test calculation with insufficient data"""
        data = pd.DataFrame({
            'close': [100.0] * 10,
            'volume': [1000] * 10
        })

        result = self.factor.calculate(data, '005930')

        self.assertIsNone(result)


# Parametrized tests
@pytest.mark.parametrize("category_name,expected_value", [
    ('MOMENTUM', 'momentum'),
    ('VALUE', 'value'),
    ('QUALITY', 'quality'),
    ('LOW_VOL', 'low_volatility'),
    ('SIZE', 'size'),
    ('GROWTH', 'growth'),
    ('EFFICIENCY', 'efficiency'),
])
def test_factor_category_values(category_name, expected_value):
    """Test factor category enum values"""
    category = FactorCategory[category_name]
    assert category.value == expected_value


@pytest.mark.parametrize("raw_percentile,expected", [
    (50.0, 50.0),
    (0.0, 0.0),
    (100.0, 100.0),
    (-10.0, 0.0),
    (150.0, 100.0),
])
def test_percentile_clamping_parametrized(raw_percentile, expected):
    """Test percentile clamping at boundaries"""
    result = FactorResult(
        ticker='TEST',
        factor_name='Test',
        raw_value=1.0,
        z_score=0.0,
        percentile=raw_percentile,
        confidence=0.5
    )
    assert result.percentile == expected


@pytest.mark.parametrize("raw_confidence,expected", [
    (0.5, 0.5),
    (0.0, 0.0),
    (1.0, 1.0),
    (-0.5, 0.0),
    (1.5, 1.0),
])
def test_confidence_clamping_parametrized(raw_confidence, expected):
    """Test confidence clamping at boundaries"""
    result = FactorResult(
        ticker='TEST',
        factor_name='Test',
        raw_value=1.0,
        z_score=0.0,
        percentile=50.0,
        confidence=raw_confidence
    )
    assert result.confidence == expected


@pytest.mark.parametrize("lookback,min_required,data_length,expected_valid", [
    (250, 60, 100, True),
    (250, 60, 30, False),
    (100, 50, 60, True),
    (100, 50, 40, False),
])
def test_data_validation_length(lookback, min_required, data_length, expected_valid):
    """Test data validation for various lengths"""
    factor = ConcreteFactor(
        name='Test',
        category=FactorCategory.MOMENTUM,
        lookback_days=lookback,
        min_required_days=min_required
    )

    data = pd.DataFrame({
        'close': [100.0] * data_length,
        'volume': [1000] * data_length
    })

    is_valid, _ = factor.validate_data(data)
    assert is_valid == expected_valid


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for factor calculations"""

    def setUp(self):
        self.factor = ConcreteFactor(
            name='Test',
            category=FactorCategory.MOMENTUM,
            lookback_days=100,
            min_required_days=30
        )

    def test_z_score_with_nan_values(self):
        """Test z-score calculation ignores NaN values"""
        value = 100.0
        values = np.array([90.0, np.nan, 100.0, np.nan, 110.0])

        z_score = self.factor._calculate_z_score(value, values)

        # Should calculate based on non-NaN values only
        self.assertIsInstance(z_score, float)
        self.assertNotEqual(z_score, np.nan)

    def test_percentile_with_nan_values(self):
        """Test percentile calculation ignores NaN values"""
        value = 100.0
        values = np.array([90.0, np.nan, 100.0, np.nan, 110.0])

        percentile = self.factor._calculate_percentile(value, values)

        # Should calculate based on non-NaN values only
        self.assertIsInstance(percentile, float)
        self.assertNotEqual(percentile, np.nan)

    def test_null_ratio_missing_column(self):
        """Test null ratio with missing column"""
        data = pd.DataFrame({
            'close': [100.0] * 10
        })

        # Should handle missing column gracefully
        null_ratio = self.factor._calculate_null_ratio(data, ['close', 'missing_col'])

        # Only 'close' column contributes (10 non-null)
        self.assertIsInstance(null_ratio, float)


# =============================================================================
# Phase 6.2: Momentum Factors Tests
# =============================================================================

class TestTwelveMonthMomentumFactorInit(unittest.TestCase):
    """Test TwelveMonthMomentumFactor initialization"""

    def test_initialization(self):
        """Test factor initialization"""
        from modules.factors.momentum_factors import TwelveMonthMomentumFactor

        factor = TwelveMonthMomentumFactor()

        self.assertEqual(factor.name, "12M_Momentum")
        self.assertEqual(factor.category, FactorCategory.MOMENTUM)
        self.assertEqual(factor.lookback_days, 252)
        self.assertEqual(factor.min_required_days, 252)

    def test_required_columns(self):
        """Test required columns"""
        from modules.factors.momentum_factors import TwelveMonthMomentumFactor

        factor = TwelveMonthMomentumFactor()
        columns = factor.get_required_columns()

        self.assertIn('date', columns)
        self.assertIn('close', columns)
        self.assertIn('volume', columns)
        self.assertIn('ma20', columns)
        self.assertIn('ma60', columns)


class TestTrendConfirmation(unittest.TestCase):
    """Test _calculate_trend_confirmation method"""

    def setUp(self):
        """Set up factor instance"""
        from modules.factors.momentum_factors import TwelveMonthMomentumFactor
        self.factor = TwelveMonthMomentumFactor()

    def test_bullish_trend(self):
        """Test bullish trend confirmation (positive slopes)"""
        # Create data with upward MA slopes
        data = pd.DataFrame({
            'ma20': [100.0 + i * 0.5 for i in range(30)],  # Upward slope
            'ma60': [95.0 + i * 0.3 for i in range(30)]    # Upward slope
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertGreater(trend_score, 0)
        self.assertLessEqual(trend_score, 1.0)

    def test_bearish_trend(self):
        """Test bearish trend confirmation (negative slopes)"""
        # Create data with downward MA slopes
        data = pd.DataFrame({
            'ma20': [100.0 - i * 0.5 for i in range(30)],  # Downward slope
            'ma60': [105.0 - i * 0.3 for i in range(30)]   # Downward slope
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertLess(trend_score, 0)
        self.assertGreaterEqual(trend_score, -1.0)

    def test_neutral_trend(self):
        """Test neutral/flat trend"""
        # Create data with flat MA
        data = pd.DataFrame({
            'ma20': [100.0] * 30,
            'ma60': [100.0] * 30
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertAlmostEqual(trend_score, 0.0, places=1)

    def test_missing_ma_columns(self):
        """Test with missing MA columns"""
        data = pd.DataFrame({
            'close': [100.0] * 30
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertEqual(trend_score, 0.0)

    def test_insufficient_ma_data(self):
        """Test with insufficient MA data points"""
        data = pd.DataFrame({
            'ma20': [100.0] * 10,  # Less than 20 points
            'ma60': [100.0] * 10
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertEqual(trend_score, 0.0)

    def test_trend_score_clamping(self):
        """Test that trend score is clamped to [-1, 1]"""
        # Extreme upward slope
        data = pd.DataFrame({
            'ma20': [100.0 + i * 5.0 for i in range(30)],  # Very steep
            'ma60': [100.0 + i * 5.0 for i in range(30)]
        })

        trend_score = self.factor._calculate_trend_confirmation(data)

        self.assertLessEqual(trend_score, 1.0)
        self.assertGreaterEqual(trend_score, -1.0)


class TestRSIMomentumFactor(unittest.TestCase):
    """Test RSIMomentumFactor initialization"""

    def test_initialization(self):
        """Test factor initialization"""
        from modules.factors.momentum_factors import RSIMomentumFactor

        factor = RSIMomentumFactor()

        self.assertEqual(factor.name, "RSI_Momentum")
        self.assertEqual(factor.category, FactorCategory.MOMENTUM)
        self.assertEqual(factor.lookback_days, 60)
        self.assertEqual(factor.min_required_days, 30)


class TestRSIScoreCalculation(unittest.TestCase):
    """Test _calculate_rsi_score method"""

    def setUp(self):
        """Set up factor instance"""
        from modules.factors.momentum_factors import RSIMomentumFactor
        self.factor = RSIMomentumFactor()

    def test_optimal_zone_50_70(self):
        """Test optimal momentum zone (RSI 50-70)"""
        for rsi in [50, 55, 60, 65, 70]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 100.0, f"RSI {rsi} should score 100")

    def test_good_zone_45_75(self):
        """Test good momentum zone (RSI 45-75, excluding 50-70)"""
        for rsi in [45, 46, 47, 48, 49, 71, 72, 73, 74, 75]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 75.0, f"RSI {rsi} should score 75")

    def test_acceptable_zone_40_80(self):
        """Test acceptable zone (RSI 40-80, excluding 45-75)"""
        for rsi in [40, 41, 42, 43, 44, 76, 77, 78, 79, 80]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 50.0, f"RSI {rsi} should score 50")

    def test_overbought_zone(self):
        """Test overbought zone (RSI >80)"""
        for rsi in [81, 85, 90, 95, 100]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 25.0, f"RSI {rsi} (overbought) should score 25")

    def test_oversold_zone(self):
        """Test oversold zone (RSI <30)"""
        for rsi in [0, 10, 20, 25, 29]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 30.0, f"RSI {rsi} (oversold) should score 30")

    def test_neutral_zone(self):
        """Test neutral zone (RSI 30-40)"""
        for rsi in [30, 32, 35, 38, 39]:
            score = self.factor._calculate_rsi_score(float(rsi))
            self.assertEqual(score, 40.0, f"RSI {rsi} (neutral) should score 40")


class TestRSIZoneClassification(unittest.TestCase):
    """Test _classify_rsi_zone method"""

    def setUp(self):
        """Set up factor instance"""
        from modules.factors.momentum_factors import RSIMomentumFactor
        self.factor = RSIMomentumFactor()

    def test_overbought_classification(self):
        """Test overbought zone classification (RSI >= 70)"""
        for rsi in [70, 75, 80, 90, 100]:
            zone = self.factor._classify_rsi_zone(float(rsi))
            self.assertEqual(zone, "overbought", f"RSI {rsi} should be overbought")

    def test_bullish_momentum_classification(self):
        """Test bullish momentum zone classification (RSI 50-70)"""
        for rsi in [50, 55, 60, 65, 69]:
            zone = self.factor._classify_rsi_zone(float(rsi))
            self.assertEqual(zone, "bullish_momentum", f"RSI {rsi} should be bullish_momentum")

    def test_neutral_classification(self):
        """Test neutral zone classification (RSI 30-50)"""
        for rsi in [30, 35, 40, 45, 49]:
            zone = self.factor._classify_rsi_zone(float(rsi))
            self.assertEqual(zone, "neutral", f"RSI {rsi} should be neutral")

    def test_oversold_classification(self):
        """Test oversold zone classification (RSI < 30)"""
        for rsi in [0, 10, 20, 25, 29]:
            zone = self.factor._classify_rsi_zone(float(rsi))
            self.assertEqual(zone, "oversold", f"RSI {rsi} should be oversold")


class TestShortTermMomentumFactor(unittest.TestCase):
    """Test ShortTermMomentumFactor"""

    def test_initialization(self):
        """Test factor initialization"""
        from modules.factors.momentum_factors import ShortTermMomentumFactor

        factor = ShortTermMomentumFactor()

        self.assertEqual(factor.name, "1M_Momentum")
        self.assertEqual(factor.category, FactorCategory.MOMENTUM)
        self.assertEqual(factor.lookback_days, 60)
        self.assertEqual(factor.min_required_days, 30)


# Parametrized tests for RSI scoring
@pytest.mark.parametrize("rsi_value,expected_score", [
    (50, 100.0),  # Optimal zone start
    (60, 100.0),  # Optimal zone middle
    (70, 100.0),  # Optimal zone end
    (45, 75.0),   # Good zone boundary
    (75, 75.0),   # Good zone boundary
    (40, 50.0),   # Acceptable zone
    (80, 50.0),   # Acceptable zone boundary
    (85, 25.0),   # Overbought
    (20, 30.0),   # Oversold
    (35, 40.0),   # Neutral
])
def test_rsi_score_parametrized(rsi_value, expected_score):
    """Parametrized RSI score test"""
    from modules.factors.momentum_factors import RSIMomentumFactor
    factor = RSIMomentumFactor()
    score = factor._calculate_rsi_score(rsi_value)
    assert score == expected_score


@pytest.mark.parametrize("rsi_value,expected_zone", [
    (70, "overbought"),
    (85, "overbought"),
    (50, "bullish_momentum"),
    (65, "bullish_momentum"),
    (30, "neutral"),
    (45, "neutral"),
    (10, "oversold"),
    (29, "oversold"),
])
def test_rsi_zone_parametrized(rsi_value, expected_zone):
    """Parametrized RSI zone classification test"""
    from modules.factors.momentum_factors import RSIMomentumFactor
    factor = RSIMomentumFactor()
    zone = factor._classify_rsi_zone(rsi_value)
    assert zone == expected_zone


if __name__ == '__main__':
    unittest.main(verbosity=2)
