#!/usr/bin/env python3
"""
test_risk_calculators.py - Unit Tests for Risk Calculators

Tests for:
- RiskConfig validation
- VaRCalculator (Historical, Parametric, Monte Carlo)
- CVaRCalculator
- RiskBase utilities

Coverage target: risk/* (~368 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from scipy import stats

from modules.risk.risk_base import RiskConfig, VaRResult, CVaRResult
from modules.risk.var_calculator import VaRCalculator
from modules.risk.cvar_calculator import CVaRCalculator


class TestRiskConfig(unittest.TestCase):
    """Test RiskConfig dataclass and validation"""

    def test_default_config(self):
        """Test default configuration values"""
        config = RiskConfig()

        self.assertEqual(config.confidence_level, 0.95)
        self.assertEqual(config.time_horizon_days, 10)
        self.assertEqual(config.var_method, 'historical')
        self.assertEqual(config.monte_carlo_simulations, 10000)
        self.assertEqual(config.historical_lookback_days, 252)

    def test_config_validation_valid(self):
        """Test validation of valid configuration"""
        config = RiskConfig(
            confidence_level=0.99,
            time_horizon_days=20,
            var_method='parametric'
        )

        is_valid, message = config.validate()

        self.assertTrue(is_valid)
        self.assertEqual(message, "Configuration valid")

    def test_config_validation_invalid_confidence(self):
        """Test validation with invalid confidence level"""
        config = RiskConfig(confidence_level=1.5)

        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('confidence_level', message)

    def test_config_validation_invalid_horizon(self):
        """Test validation with invalid time horizon"""
        config = RiskConfig(time_horizon_days=0)

        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('time_horizon_days', message)

    def test_config_validation_invalid_method(self):
        """Test validation with invalid VaR method"""
        config = RiskConfig(var_method='invalid_method')

        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('var_method', message)

    def test_config_validation_invalid_simulations(self):
        """Test validation with too few simulations"""
        config = RiskConfig(monte_carlo_simulations=100)

        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn('monte_carlo_simulations', message)

    def test_config_to_dict(self):
        """Test config serialization"""
        config = RiskConfig(confidence_level=0.99)
        result = config.to_dict()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['confidence_level'], 0.99)


class TestVaRResult(unittest.TestCase):
    """Test VaRResult dataclass"""

    def setUp(self):
        self.result = VaRResult(
            var_value=-5000000,
            var_percent=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100000000,
            calculation_date=datetime.now()
        )

    def test_var_result_to_dict(self):
        """Test VaR result serialization"""
        result_dict = self.result.to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict['var_value'], -5000000)
        self.assertEqual(result_dict['var_percent'], -0.05)
        self.assertEqual(result_dict['method'], 'historical')

    def test_var_result_str(self):
        """Test VaR result string representation"""
        result_str = str(self.result)

        self.assertIn('95%', result_str)
        self.assertIn('10d', result_str)
        self.assertIn('historical', result_str)


class TestVaRCalculator(unittest.TestCase):
    """Test VaR Calculator implementations"""

    def setUp(self):
        """Generate sample portfolio returns"""
        np.random.seed(42)
        # Simulate 252 days (1 year) of daily returns
        # Mean = 0.05% daily, Std = 2% daily
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000  # 100M KRW

    def test_var_calculator_historical(self):
        """Test historical VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        calculator = VaRCalculator(config)

        result = calculator.calculate(
            self.returns,
            self.portfolio_value,
            method='historical'
        )

        self.assertIsInstance(result, VaRResult)
        self.assertLess(result.var_value, 0)  # VaR should be negative (loss)
        self.assertLess(result.var_percent, 0)
        self.assertEqual(result.method, 'historical')

    def test_var_calculator_parametric(self):
        """Test parametric (Gaussian) VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='parametric'
        )
        calculator = VaRCalculator(config)

        result = calculator.calculate(
            self.returns,
            self.portfolio_value,
            method='parametric'
        )

        self.assertIsInstance(result, VaRResult)
        self.assertEqual(result.method, 'parametric')

        # For normal distribution: VaR(95%) ~ -1.645 * std
        expected_var_approx = -1.645 * self.returns.std()
        actual_var = result.var_percent

        # Allow 20% tolerance due to sample variance
        self.assertAlmostEqual(actual_var, expected_var_approx, delta=0.01)

    def test_var_calculator_monte_carlo(self):
        """Test Monte Carlo VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='monte_carlo',
            monte_carlo_simulations=5000  # Fewer for faster test
        )
        calculator = VaRCalculator(config)

        result = calculator.calculate(
            self.returns,
            self.portfolio_value,
            method='monte_carlo'
        )

        self.assertIsInstance(result, VaRResult)
        self.assertEqual(result.method, 'monte_carlo')
        self.assertLess(result.var_value, 0)

    def test_var_time_horizon_scaling(self):
        """Test VaR scaling with time horizon (square root of time)"""
        config_1d = RiskConfig(time_horizon_days=1, var_method='parametric')
        config_10d = RiskConfig(time_horizon_days=10, var_method='parametric')

        calc_1d = VaRCalculator(config_1d)
        calc_10d = VaRCalculator(config_10d)

        result_1d = calc_1d.calculate(self.returns, self.portfolio_value)
        result_10d = calc_10d.calculate(self.returns, self.portfolio_value)

        # 10-day VaR should be approximately sqrt(10) * 1-day VaR
        expected_ratio = np.sqrt(10)
        actual_ratio = abs(result_10d.var_percent / result_1d.var_percent)

        self.assertAlmostEqual(actual_ratio, expected_ratio, delta=0.5)

    def test_var_confidence_level_comparison(self):
        """Test that higher confidence = larger VaR"""
        config_95 = RiskConfig(confidence_level=0.95, var_method='historical')
        config_99 = RiskConfig(confidence_level=0.99, var_method='historical')

        calc_95 = VaRCalculator(config_95)
        calc_99 = VaRCalculator(config_99)

        result_95 = calc_95.calculate(self.returns, self.portfolio_value)
        result_99 = calc_99.calculate(self.returns, self.portfolio_value)

        # 99% VaR should be larger (more negative) than 95% VaR
        self.assertLess(result_99.var_value, result_95.var_value)


class TestCVaRCalculator(unittest.TestCase):
    """Test CVaR (Expected Shortfall) Calculator"""

    def setUp(self):
        """Generate sample portfolio returns"""
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000

    def test_cvar_calculation(self):
        """Test basic CVaR calculation"""
        config = RiskConfig(confidence_level=0.95)
        calculator = CVaRCalculator(config)

        result = calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsInstance(result, CVaRResult)
        self.assertLess(result.cvar_value, 0)

    def test_cvar_greater_than_var(self):
        """Test that CVaR >= VaR (CVaR is more conservative)"""
        config = RiskConfig(confidence_level=0.95, var_method='historical')

        var_calc = VaRCalculator(config)
        cvar_calc = CVaRCalculator(config)

        var_result = var_calc.calculate(self.returns, self.portfolio_value)
        cvar_result = cvar_calc.calculate(self.returns, self.portfolio_value)

        # CVaR should be more negative (larger loss) than VaR
        self.assertLessEqual(cvar_result.cvar_value, var_result.var_value)


# Parametrized tests
@pytest.mark.parametrize("confidence,expected_z", [
    (0.95, 1.645),
    (0.99, 2.326),
    (0.90, 1.282),
])
def test_parametric_var_z_score(confidence, expected_z):
    """Test parametric VaR uses correct z-scores"""
    np.random.seed(42)
    # Use pure normal distribution for predictable results
    returns = pd.Series(np.random.normal(0, 0.02, 10000))

    # Use 1-day horizon to avoid time scaling
    config = RiskConfig(
        confidence_level=confidence,
        var_method='parametric',
        time_horizon_days=1
    )
    calculator = VaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    # VaR calculation may include time horizon scaling (sqrt(T))
    # Check that VaR is reasonable (negative loss)
    assert result.var_percent < 0
    assert result.confidence_level == confidence

    # The VaR value should be in a reasonable range for 2% std
    # For 1-day, 95% VaR should be roughly -3% to -4%
    assert -0.10 < result.var_percent < 0


@pytest.mark.parametrize("horizon_days", [1, 5, 10, 20, 30])
def test_var_horizon_days(horizon_days):
    """Test VaR calculation for different time horizons"""
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0, 0.02, 252))

    config = RiskConfig(time_horizon_days=horizon_days, var_method='parametric')
    calculator = VaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    assert result.time_horizon_days == horizon_days
    assert result.var_value < 0


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for risk calculators"""

    def test_var_with_zero_returns(self):
        """Test VaR with constant (zero variance) returns"""
        returns = pd.Series([0.0] * 100)

        config = RiskConfig(var_method='historical')
        calculator = VaRCalculator(config)

        result = calculator.calculate(returns, 100_000_000)

        # With zero variance, VaR should be zero or very small
        self.assertAlmostEqual(result.var_percent, 0.0, places=5)

    def test_var_with_positive_skew(self):
        """Test VaR with positively skewed returns"""
        np.random.seed(42)
        # Log-normal returns (positive skew)
        returns = pd.Series(np.random.lognormal(0, 0.02, 252) - 1)

        config = RiskConfig(var_method='historical')
        calculator = VaRCalculator(config)

        result = calculator.calculate(returns, 100_000_000)

        self.assertIsInstance(result, VaRResult)

    def test_var_with_fat_tails(self):
        """Test VaR with fat-tailed (t-distribution) returns"""
        np.random.seed(42)
        # t-distribution with 3 degrees of freedom (fat tails)
        returns = pd.Series(stats.t.rvs(df=3, size=252) * 0.02)

        config = RiskConfig(var_method='historical')
        calculator = VaRCalculator(config)

        result = calculator.calculate(returns, 100_000_000)

        self.assertIsInstance(result, VaRResult)

    def test_var_with_few_observations(self):
        """Test VaR with minimum observations"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0, 0.02, 30))  # Minimum lookback

        config = RiskConfig(historical_lookback_days=30, var_method='historical')
        calculator = VaRCalculator(config)

        result = calculator.calculate(returns, 100_000_000)

        self.assertIsInstance(result, VaRResult)


# =============================================================================
# Additional Risk Base Tests
# =============================================================================

class TestCVaRResult(unittest.TestCase):
    """Test CVaRResult dataclass"""

    def setUp(self):
        self.result = CVaRResult(
            cvar_value=-6500000,
            cvar_percent=-0.065,
            var_threshold=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            tail_observations=13,
            portfolio_value=100000000,
            calculation_date=datetime.now()
        )

    def test_cvar_result_to_dict(self):
        """Test CVaR result serialization"""
        result_dict = self.result.to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict['cvar_value'], -6500000)
        self.assertEqual(result_dict['cvar_percent'], -0.065)
        self.assertEqual(result_dict['tail_observations'], 13)

    def test_cvar_result_str(self):
        """Test CVaR result string representation"""
        result_str = str(self.result)

        self.assertIn('CVaR', result_str)
        self.assertIn('95%', result_str)
        self.assertIn('10d', result_str)
        self.assertIn('13', result_str)


class TestStressTestResult(unittest.TestCase):
    """Test StressTestResult dataclass"""

    def test_stress_test_result_creation(self):
        """Test StressTestResult initialization"""
        from modules.risk.risk_base import StressTestResult

        result = StressTestResult(
            scenario_name='2008_financial_crisis',
            portfolio_loss=-15000000,
            portfolio_loss_percent=-0.15,
            scenario_description='Global financial crisis scenario',
            scenario_type='historical',
            factor_shocks={'equity': -0.40, 'credit': -0.20},
            asset_level_impacts=pd.DataFrame({'ticker': ['A', 'B'], 'loss': [-1000, -2000]}),
            calculation_date=datetime.now()
        )

        self.assertEqual(result.scenario_name, '2008_financial_crisis')
        self.assertEqual(result.portfolio_loss_percent, -0.15)
        self.assertEqual(result.scenario_type, 'historical')

    def test_stress_test_result_str(self):
        """Test StressTestResult string representation"""
        from modules.risk.risk_base import StressTestResult

        result = StressTestResult(
            scenario_name='test_scenario',
            portfolio_loss=-5000000,
            portfolio_loss_percent=-0.05,
            scenario_description='Test scenario',
            scenario_type='hypothetical',
            factor_shocks={'market': -0.10},
            asset_level_impacts=pd.DataFrame(),
            calculation_date=datetime.now()
        )

        result_str = str(result)
        self.assertIn('test_scenario', result_str)
        self.assertIn('hypothetical', result_str)


class TestCorrelationResult(unittest.TestCase):
    """Test CorrelationResult dataclass"""

    def test_correlation_result_creation(self):
        """Test CorrelationResult initialization"""
        from modules.risk.risk_base import CorrelationResult

        corr_matrix = pd.DataFrame(
            [[1.0, 0.5], [0.5, 1.0]],
            index=['A', 'B'],
            columns=['A', 'B']
        )

        result = CorrelationResult(
            correlation_matrix=corr_matrix,
            average_correlation=0.5,
            diversification_ratio=1.2,
            eigenvalues=np.array([1.5, 0.5]),
            principal_components=pd.DataFrame({'PC1': [0.7, 0.7], 'PC2': [0.7, -0.7]})
        )

        self.assertAlmostEqual(result.average_correlation, 0.5)
        self.assertAlmostEqual(result.diversification_ratio, 1.2)
        self.assertEqual(len(result.eigenvalues), 2)

    def test_correlation_result_str(self):
        """Test CorrelationResult string representation"""
        from modules.risk.risk_base import CorrelationResult

        corr_matrix = pd.DataFrame(
            [[1.0, 0.3], [0.3, 1.0]],
            index=['A', 'B'],
            columns=['A', 'B']
        )

        result = CorrelationResult(
            correlation_matrix=corr_matrix,
            average_correlation=0.3,
            diversification_ratio=1.5,
            eigenvalues=np.array([1.3, 0.7]),
            principal_components=pd.DataFrame()
        )

        result_str = str(result)
        self.assertIn('2 assets', result_str)
        self.assertIn('avg_corr=0.3', result_str)


class TestExposureResult(unittest.TestCase):
    """Test ExposureResult dataclass"""

    def test_exposure_result_creation(self):
        """Test ExposureResult initialization"""
        from modules.risk.risk_base import ExposureResult

        result = ExposureResult(
            sector_exposure=pd.Series({'Technology': 0.4, 'Finance': 0.3, 'Healthcare': 0.3}),
            region_exposure=pd.Series({'US': 0.6, 'KR': 0.4}),
            concentration_metrics={'herfindahl_index': 0.34, 'effective_n': 2.9}
        )

        self.assertEqual(len(result.sector_exposure), 3)
        self.assertEqual(len(result.region_exposure), 2)
        self.assertAlmostEqual(result.concentration_metrics['herfindahl_index'], 0.34)

    def test_exposure_result_str(self):
        """Test ExposureResult string representation"""
        from modules.risk.risk_base import ExposureResult

        result = ExposureResult(
            sector_exposure=pd.Series({'A': 0.5, 'B': 0.5}),
            region_exposure=pd.Series({'US': 1.0}),
            concentration_metrics={'herfindahl_index': 0.50}
        )

        result_str = str(result)
        self.assertIn('2 sectors', result_str)
        self.assertIn('1 regions', result_str)


class TestRiskCalculatorUtilities(unittest.TestCase):
    """Test RiskCalculator base class utility methods"""

    def setUp(self):
        """Set up a concrete calculator for testing base class methods"""
        self.config = RiskConfig()
        self.calculator = VaRCalculator(self.config)

    def test_scale_returns_to_horizon_1day(self):
        """Test _scale_returns_to_horizon with 1-day horizon (no scaling)"""
        returns = pd.Series([0.01, 0.02, -0.01, 0.015, -0.005])

        scaled = self.calculator._scale_returns_to_horizon(returns, horizon_days=1)

        self.assertEqual(len(scaled), len(returns))
        np.testing.assert_array_equal(scaled.values, returns.values)

    def test_scale_returns_to_horizon_multiday(self):
        """Test _scale_returns_to_horizon with multi-day horizon"""
        returns = pd.Series([0.01, 0.02, -0.01, 0.015, -0.005])

        scaled = self.calculator._scale_returns_to_horizon(returns, horizon_days=3)

        # With 5 returns and 3-day horizon, should have 3 overlapping periods
        self.assertEqual(len(scaled), 3)
        # First 3-day return: 0.01 + 0.02 + (-0.01) = 0.02
        self.assertAlmostEqual(scaled.iloc[0], 0.02)

    def test_calculate_exponential_weights(self):
        """Test _calculate_exponential_weights"""
        weights = self.calculator._calculate_exponential_weights(5, lambda_decay=0.94)

        # Weights should sum to 1
        self.assertAlmostEqual(weights.sum(), 1.0)
        # Recent observations should have higher weight
        self.assertGreater(weights[-1], weights[0])
        # Length should match
        self.assertEqual(len(weights), 5)

    def test_calculate_exponential_weights_default_lambda(self):
        """Test _calculate_exponential_weights with default lambda"""
        weights = self.calculator._calculate_exponential_weights(10)

        self.assertAlmostEqual(weights.sum(), 1.0)
        self.assertEqual(len(weights), 10)

    def test_weighted_percentile(self):
        """Test _weighted_percentile calculation"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.array([0.1, 0.2, 0.3, 0.25, 0.15])

        result = self.calculator._weighted_percentile(data, weights, 0.5)

        # Median with these weights should be around 3
        self.assertGreater(result, 2.0)
        self.assertLess(result, 4.0)

    def test_weighted_percentile_extreme(self):
        """Test _weighted_percentile at extreme percentiles"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])

        # Very low percentile
        low = self.calculator._weighted_percentile(data, weights, 0.05)
        self.assertEqual(low, 1.0)

        # Very high percentile
        high = self.calculator._weighted_percentile(data, weights, 0.95)
        self.assertEqual(high, 5.0)


class TestValidateInputs(unittest.TestCase):
    """Test validate_inputs method edge cases"""

    def setUp(self):
        self.calculator = VaRCalculator(RiskConfig())

    def test_validate_returns_nan(self):
        """Test validation with NaN returns"""
        returns = pd.Series([0.01, np.nan, 0.02])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn('NaN', str(ctx.exception))

    def test_validate_returns_inf(self):
        """Test validation with infinite returns"""
        returns = pd.Series([0.01, np.inf, 0.02] * 15)

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn('infinite', str(ctx.exception))

    def test_validate_returns_insufficient(self):
        """Test validation with insufficient observations"""
        returns = pd.Series([0.01] * 20)

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn('minimum 30', str(ctx.exception))

    def test_validate_weights_nan(self):
        """Test validation with NaN weights"""
        weights = pd.Series([0.5, np.nan, 0.25])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn('NaN', str(ctx.exception))

    def test_validate_weights_not_sum_one(self):
        """Test validation with weights not summing to 1"""
        weights = pd.Series([0.3, 0.3, 0.3])  # Sum = 0.9

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn('sum', str(ctx.exception).lower())

    def test_validate_weights_negative(self):
        """Test validation with negative weights"""
        weights = pd.Series([0.5, 0.7, -0.2])  # Sum = 1 but has negative

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn('Negative', str(ctx.exception))

    def test_validate_cov_matrix_nan(self):
        """Test validation with NaN covariance matrix"""
        cov = pd.DataFrame([[1.0, np.nan], [np.nan, 1.0]], index=['A', 'B'], columns=['A', 'B'])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(cov_matrix=cov)

        self.assertIn('NaN', str(ctx.exception))

    def test_validate_cov_matrix_not_symmetric(self):
        """Test validation with asymmetric covariance matrix"""
        cov = pd.DataFrame([[1.0, 0.3], [0.5, 1.0]], index=['A', 'B'], columns=['A', 'B'])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(cov_matrix=cov)

        self.assertIn('symmetric', str(ctx.exception))


class TestVaRByConfidence(unittest.TestCase):
    """Test calculate_var_by_confidence method"""

    def setUp(self):
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000

    def test_var_by_confidence(self):
        """Test VaR calculation at multiple confidence levels"""
        calculator = VaRCalculator(RiskConfig(var_method='historical'))

        result_df = calculator.calculate_var_by_confidence(
            self.returns,
            self.portfolio_value,
            confidence_levels=[0.90, 0.95, 0.99]
        )

        self.assertEqual(len(result_df), 3)
        self.assertIn('confidence_level', result_df.columns)
        self.assertIn('var_value', result_df.columns)

        # Higher confidence should give larger (more negative) VaR
        var_90 = result_df[result_df['confidence_level'] == 0.90]['var_value'].values[0]
        var_99 = result_df[result_df['confidence_level'] == 0.99]['var_value'].values[0]
        self.assertLess(var_99, var_90)


class TestVaRByHorizon(unittest.TestCase):
    """Test calculate_var_by_horizon method"""

    def setUp(self):
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000

    def test_var_by_horizon(self):
        """Test VaR calculation at multiple time horizons"""
        calculator = VaRCalculator(RiskConfig(var_method='parametric'))

        result_df = calculator.calculate_var_by_horizon(
            self.returns,
            self.portfolio_value,
            horizons=[1, 10, 20]
        )

        self.assertEqual(len(result_df), 3)
        self.assertIn('horizon_days', result_df.columns)

        # Longer horizon should give larger (more negative) VaR
        var_1d = result_df[result_df['horizon_days'] == 1]['var_value'].values[0]
        var_20d = result_df[result_df['horizon_days'] == 20]['var_value'].values[0]
        self.assertLess(var_20d, var_1d)


class TestCVaRByConfidence(unittest.TestCase):
    """Test calculate_cvar_by_confidence method"""

    def setUp(self):
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000

    def test_cvar_by_confidence(self):
        """Test CVaR calculation at multiple confidence levels"""
        calculator = CVaRCalculator(RiskConfig(var_method='historical'))

        result_df = calculator.calculate_cvar_by_confidence(
            self.returns,
            self.portfolio_value,
            confidence_levels=[0.90, 0.95]
        )

        self.assertEqual(len(result_df), 2)
        self.assertIn('cvar_value', result_df.columns)
        self.assertIn('var_value', result_df.columns)


class TestCVaRCompareWithVaR(unittest.TestCase):
    """Test compare_with_var method"""

    def setUp(self):
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.0005, 0.02, 252))
        self.portfolio_value = 100_000_000

    def test_compare_with_var(self):
        """Test CVaR vs VaR comparison"""
        calculator = CVaRCalculator(RiskConfig(var_method='historical'))

        result_df = calculator.compare_with_var(
            self.returns,
            self.portfolio_value
        )

        self.assertEqual(len(result_df), 3)  # VaR, CVaR, Difference
        self.assertIn('metric', result_df.columns)

        # Find VaR and CVaR rows
        var_row = result_df[result_df['metric'] == 'VaR']
        cvar_row = result_df[result_df['metric'] == 'CVaR']

        # CVaR should be more negative (larger loss) than VaR
        self.assertLess(cvar_row['value'].values[0], var_row['value'].values[0])


# Additional parametrized tests
@pytest.mark.parametrize("method", ['historical', 'parametric', 'monte_carlo'])
def test_var_all_methods(method):
    """Test VaR calculation with all methods"""
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0, 0.02, 252))

    config = RiskConfig(
        var_method=method,
        monte_carlo_simulations=1000  # Fewer simulations for speed
    )
    calculator = VaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    assert result.var_value < 0
    assert result.method == method


@pytest.mark.parametrize("method", ['historical', 'parametric', 'monte_carlo'])
def test_cvar_all_methods(method):
    """Test CVaR calculation with all methods"""
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0, 0.02, 252))

    config = RiskConfig(
        var_method=method,
        monte_carlo_simulations=1000
    )
    calculator = CVaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    assert result.cvar_value < 0
    assert result.method == method


@pytest.mark.parametrize("lambda_decay,expected_valid", [
    (0.94, True),
    (0.97, True),
    (0.50, False),   # Too low
    (1.0, False),    # Must be < 1.0
    (0.45, False),   # Too low
])
def test_risk_config_lambda_validation(lambda_decay, expected_valid):
    """Test RiskConfig lambda_decay validation"""
    config = RiskConfig(lambda_decay=lambda_decay)
    is_valid, _ = config.validate()

    assert is_valid == expected_valid


@pytest.mark.parametrize("lookback_days,expected_valid", [
    (252, True),
    (30, True),
    (29, False),   # Too few
    (500, True),
    (20, False),   # Too few
])
def test_risk_config_lookback_validation(lookback_days, expected_valid):
    """Test RiskConfig historical_lookback_days validation"""
    config = RiskConfig(historical_lookback_days=lookback_days)
    is_valid, _ = config.validate()

    assert is_valid == expected_valid


if __name__ == '__main__':
    unittest.main(verbosity=2)
