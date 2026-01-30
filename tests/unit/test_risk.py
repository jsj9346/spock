#!/usr/bin/env python3
"""
test_risk.py - Unit Tests for Risk Module

Tests for:
- RiskConfig dataclass with validation
- VaRResult, CVaRResult, StressTestResult dataclasses
- VaRCalculator: Historical, Parametric, Monte Carlo VaR
- CVaRCalculator: Historical, Parametric, Monte Carlo CVaR
- RiskCalculator base class utilities

Coverage target: modules/risk/*.py (~700+ lines)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from scipy import stats


# =============================================================================
# RiskConfig Tests
# =============================================================================

class TestRiskConfigDataclass(unittest.TestCase):
    """Test RiskConfig dataclass"""

    def test_default_initialization(self):
        """Test RiskConfig default values"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig()

        self.assertEqual(config.confidence_level, 0.95)
        self.assertEqual(config.time_horizon_days, 10)
        self.assertEqual(config.var_method, 'historical')
        self.assertEqual(config.monte_carlo_simulations, 10000)
        self.assertEqual(config.historical_lookback_days, 252)
        self.assertEqual(config.correlation_window_days, 60)
        self.assertFalse(config.exponential_weighting)
        self.assertEqual(config.lambda_decay, 0.94)
        self.assertEqual(len(config.stress_test_scenarios), 3)

    def test_custom_initialization(self):
        """Test RiskConfig with custom values"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(
            confidence_level=0.99,
            time_horizon_days=20,
            var_method='parametric',
            monte_carlo_simulations=50000,
            exponential_weighting=True,
            lambda_decay=0.97
        )

        self.assertEqual(config.confidence_level, 0.99)
        self.assertEqual(config.time_horizon_days, 20)
        self.assertEqual(config.var_method, 'parametric')
        self.assertEqual(config.monte_carlo_simulations, 50000)
        self.assertTrue(config.exponential_weighting)
        self.assertEqual(config.lambda_decay, 0.97)

    def test_validate_success(self):
        """Test validate() with valid config"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig()
        is_valid, message = config.validate()

        self.assertTrue(is_valid)
        self.assertEqual(message, "Configuration valid")

    def test_validate_invalid_confidence_level_low(self):
        """Test validate() with confidence_level < 0.5"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=0.4)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("confidence_level", message)

    def test_validate_invalid_confidence_level_high(self):
        """Test validate() with confidence_level >= 1.0"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=1.0)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("confidence_level", message)

    def test_validate_invalid_time_horizon(self):
        """Test validate() with time_horizon_days < 1"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(time_horizon_days=0)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("time_horizon_days", message)

    def test_validate_invalid_var_method(self):
        """Test validate() with invalid var_method"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(var_method='invalid_method')
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("var_method", message)

    def test_validate_invalid_monte_carlo_simulations(self):
        """Test validate() with monte_carlo_simulations < 1000"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(monte_carlo_simulations=500)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("monte_carlo_simulations", message)

    def test_validate_invalid_lookback_days(self):
        """Test validate() with historical_lookback_days < 30"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(historical_lookback_days=20)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("historical_lookback_days", message)

    def test_validate_invalid_correlation_window(self):
        """Test validate() with correlation_window_days < 20"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(correlation_window_days=10)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("correlation_window_days", message)

    def test_validate_invalid_lambda_decay_low(self):
        """Test validate() with lambda_decay <= 0.5"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(lambda_decay=0.5)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("lambda_decay", message)

    def test_validate_invalid_lambda_decay_high(self):
        """Test validate() with lambda_decay >= 1.0"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(lambda_decay=1.0)
        is_valid, message = config.validate()

        self.assertFalse(is_valid)
        self.assertIn("lambda_decay", message)

    def test_to_dict(self):
        """Test to_dict() serialization"""
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=0.99, time_horizon_days=5)
        result = config.to_dict()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['confidence_level'], 0.99)
        self.assertEqual(result['time_horizon_days'], 5)
        self.assertIn('stress_test_scenarios', result)
        self.assertIn('exponential_weighting', result)


# =============================================================================
# VaRResult Tests
# =============================================================================

class TestVaRResultDataclass(unittest.TestCase):
    """Test VaRResult dataclass"""

    def test_creation(self):
        """Test VaRResult initialization"""
        from modules.risk.risk_base import VaRResult

        result = VaRResult(
            var_value=-5000000,
            var_percent=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100000000,
            calculation_date=datetime.now()
        )

        self.assertEqual(result.var_value, -5000000)
        self.assertEqual(result.var_percent, -0.05)
        self.assertEqual(result.confidence_level, 0.95)
        self.assertEqual(result.method, 'historical')
        self.assertIsNone(result.metadata)

    def test_creation_with_metadata(self):
        """Test VaRResult with metadata"""
        from modules.risk.risk_base import VaRResult

        result = VaRResult(
            var_value=-5000000,
            var_percent=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100000000,
            calculation_date=datetime.now(),
            metadata={'observations': 252, 'volatility': 0.02}
        )

        self.assertIsNotNone(result.metadata)
        self.assertEqual(result.metadata['observations'], 252)

    def test_to_dict(self):
        """Test to_dict() serialization"""
        from modules.risk.risk_base import VaRResult

        now = datetime.now()
        result = VaRResult(
            var_value=-5000000,
            var_percent=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100000000,
            calculation_date=now
        )

        d = result.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d['var_value'], -5000000)
        self.assertEqual(d['calculation_date'], now.isoformat())

    def test_str_representation(self):
        """Test __str__ representation"""
        from modules.risk.risk_base import VaRResult

        result = VaRResult(
            var_value=-5234567,
            var_percent=-0.0523,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100000000,
            calculation_date=datetime.now()
        )

        s = str(result)

        self.assertIn("VaR", s)
        self.assertIn("95%", s)
        self.assertIn("10d", s)
        self.assertIn("historical", s)


# =============================================================================
# CVaRResult Tests
# =============================================================================

class TestCVaRResultDataclass(unittest.TestCase):
    """Test CVaRResult dataclass"""

    def test_creation(self):
        """Test CVaRResult initialization"""
        from modules.risk.risk_base import CVaRResult

        result = CVaRResult(
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

        self.assertEqual(result.cvar_value, -6500000)
        self.assertEqual(result.cvar_percent, -0.065)
        self.assertEqual(result.var_threshold, -0.05)
        self.assertEqual(result.tail_observations, 13)

    def test_to_dict(self):
        """Test to_dict() serialization"""
        from modules.risk.risk_base import CVaRResult

        result = CVaRResult(
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

        d = result.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d['cvar_value'], -6500000)
        self.assertEqual(d['tail_observations'], 13)

    def test_str_representation(self):
        """Test __str__ representation"""
        from modules.risk.risk_base import CVaRResult

        result = CVaRResult(
            cvar_value=-6543210,
            cvar_percent=-0.0654,
            var_threshold=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            tail_observations=13,
            portfolio_value=100000000,
            calculation_date=datetime.now()
        )

        s = str(result)

        self.assertIn("CVaR", s)
        self.assertIn("95%", s)
        self.assertIn("13 tail obs", s)


# =============================================================================
# StressTestResult Tests
# =============================================================================

class TestStressTestResultDataclass(unittest.TestCase):
    """Test StressTestResult dataclass"""

    def test_creation(self):
        """Test StressTestResult initialization"""
        from modules.risk.risk_base import StressTestResult

        result = StressTestResult(
            scenario_name='2008_financial_crisis',
            portfolio_loss=-15000000,
            portfolio_loss_percent=-0.15,
            scenario_description='Lehman Brothers collapse',
            scenario_type='historical',
            factor_shocks={'equity': -0.40, 'credit': -0.20},
            asset_level_impacts=pd.DataFrame([
                {'ticker': '005930', 'impact': -0.35},
                {'ticker': '000660', 'impact': -0.42}
            ]),
            calculation_date=datetime.now()
        )

        self.assertEqual(result.scenario_name, '2008_financial_crisis')
        self.assertEqual(result.portfolio_loss_percent, -0.15)
        self.assertEqual(result.scenario_type, 'historical')

    def test_str_representation(self):
        """Test __str__ representation"""
        from modules.risk.risk_base import StressTestResult

        result = StressTestResult(
            scenario_name='2020_covid_crash',
            portfolio_loss=-10000000,
            portfolio_loss_percent=-0.10,
            scenario_description='COVID-19 market crash',
            scenario_type='historical',
            factor_shocks={'equity': -0.30},
            asset_level_impacts=pd.DataFrame(),
            calculation_date=datetime.now()
        )

        s = str(result)

        self.assertIn("2020_covid_crash", s)
        self.assertIn("historical", s)


# =============================================================================
# RiskCalculator Base Class Tests
# =============================================================================

class TestRiskCalculatorValidation(unittest.TestCase):
    """Test RiskCalculator validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator

        self.calculator = VaRCalculator()

    def test_validate_inputs_valid_returns(self):
        """Test validate_inputs with valid returns"""
        returns = pd.Series(np.random.normal(0, 0.02, 100))

        # Should not raise
        self.calculator.validate_inputs(returns=returns)

    def test_validate_inputs_nan_returns(self):
        """Test validate_inputs with NaN in returns"""
        returns = pd.Series([0.01, 0.02, np.nan, 0.01])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn("NaN", str(ctx.exception))

    def test_validate_inputs_insufficient_returns(self):
        """Test validate_inputs with < 30 observations"""
        returns = pd.Series(np.random.normal(0, 0.02, 20))

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn("Insufficient", str(ctx.exception))

    def test_validate_inputs_infinite_returns(self):
        """Test validate_inputs with infinite values"""
        # Need at least 30 observations to pass length check first
        returns = pd.Series([0.01] * 30)
        returns.iloc[10] = np.inf
        returns.iloc[20] = -np.inf

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(returns=returns)

        self.assertIn("infinite", str(ctx.exception))

    def test_validate_inputs_valid_weights(self):
        """Test validate_inputs with valid weights"""
        weights = pd.Series([0.3, 0.3, 0.4], index=['A', 'B', 'C'])

        # Should not raise
        self.calculator.validate_inputs(weights=weights)

    def test_validate_inputs_nan_weights(self):
        """Test validate_inputs with NaN in weights"""
        weights = pd.Series([0.3, np.nan, 0.4], index=['A', 'B', 'C'])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn("NaN", str(ctx.exception))

    def test_validate_inputs_weights_not_sum_to_one(self):
        """Test validate_inputs with weights not summing to 1"""
        weights = pd.Series([0.3, 0.3, 0.3], index=['A', 'B', 'C'])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn("Weights sum", str(ctx.exception))

    def test_validate_inputs_negative_weights(self):
        """Test validate_inputs with negative weights"""
        weights = pd.Series([0.5, 0.7, -0.2], index=['A', 'B', 'C'])

        with self.assertRaises(ValueError) as ctx:
            self.calculator.validate_inputs(weights=weights)

        self.assertIn("Negative weights", str(ctx.exception))


class TestRiskCalculatorHelperMethods(unittest.TestCase):
    """Test RiskCalculator helper methods"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        self.calculator = VaRCalculator(RiskConfig(time_horizon_days=5))

    def test_scale_returns_to_horizon_single_day(self):
        """Test _scale_returns_to_horizon with 1-day horizon"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        calculator = VaRCalculator(RiskConfig(time_horizon_days=1))
        returns = pd.Series([0.01, 0.02, -0.01, 0.03])

        scaled = calculator._scale_returns_to_horizon(returns)

        # Should return same series for 1-day horizon
        pd.testing.assert_series_equal(scaled, returns)

    def test_scale_returns_to_horizon_multi_day(self):
        """Test _scale_returns_to_horizon with multi-day horizon"""
        returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.02])

        scaled = self.calculator._scale_returns_to_horizon(returns)

        # 5-day horizon -> should produce len(returns) - 5 + 1 = 1 observation
        self.assertEqual(len(scaled), 1)
        # Sum of all returns
        self.assertAlmostEqual(scaled.iloc[0], 0.07, places=5)

    def test_calculate_exponential_weights(self):
        """Test _calculate_exponential_weights"""
        weights = self.calculator._calculate_exponential_weights(10, lambda_decay=0.94)

        # Weights should sum to 1
        self.assertAlmostEqual(weights.sum(), 1.0, places=5)

        # More recent observations should have higher weights
        self.assertGreater(weights[-1], weights[0])

        # Length should match input
        self.assertEqual(len(weights), 10)


# =============================================================================
# VaRCalculator Tests
# =============================================================================

class TestVaRCalculatorInit(unittest.TestCase):
    """Test VaRCalculator initialization"""

    def test_default_initialization(self):
        """Test default initialization"""
        from modules.risk.var_calculator import VaRCalculator

        calculator = VaRCalculator()

        self.assertEqual(calculator.config.confidence_level, 0.95)
        self.assertEqual(calculator.config.var_method, 'historical')

    def test_custom_config_initialization(self):
        """Test initialization with custom config"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=0.99, var_method='parametric')
        calculator = VaRCalculator(config)

        self.assertEqual(calculator.config.confidence_level, 0.99)
        self.assertEqual(calculator.config.var_method, 'parametric')

    def test_invalid_config_raises(self):
        """Test initialization with invalid config raises ValueError"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=1.5)

        with self.assertRaises(ValueError):
            VaRCalculator(config)


class TestVaRCalculatorHistorical(unittest.TestCase):
    """Test Historical VaR calculation"""

    def setUp(self):
        """Set up test fixtures with reproducible random data"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        self.calculator = VaRCalculator(self.config)

    def test_calculate_historical_var(self):
        """Test historical VaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertLess(result.var_value, 0)  # VaR should be negative (loss)
        self.assertLess(result.var_percent, 0)
        self.assertEqual(result.method, 'historical')
        self.assertEqual(result.confidence_level, 0.95)

    def test_historical_var_95_vs_99_confidence(self):
        """Test that 99% VaR is more extreme than 95% VaR"""
        from modules.risk.risk_base import RiskConfig
        from modules.risk.var_calculator import VaRCalculator

        config_95 = RiskConfig(confidence_level=0.95, time_horizon_days=1)
        config_99 = RiskConfig(confidence_level=0.99, time_horizon_days=1)

        calc_95 = VaRCalculator(config_95)
        calc_99 = VaRCalculator(config_99)

        var_95 = calc_95.calculate(self.returns, self.portfolio_value)
        var_99 = calc_99.calculate(self.returns, self.portfolio_value)

        # 99% VaR should be more negative (larger loss)
        self.assertLess(var_99.var_value, var_95.var_value)

    def test_historical_var_with_horizon_scaling(self):
        """Test historical VaR with multi-day horizon"""
        from modules.risk.risk_base import RiskConfig
        from modules.risk.var_calculator import VaRCalculator

        config_1d = RiskConfig(confidence_level=0.95, time_horizon_days=1)
        config_10d = RiskConfig(confidence_level=0.95, time_horizon_days=10)

        calc_1d = VaRCalculator(config_1d)
        calc_10d = VaRCalculator(config_10d)

        var_1d = calc_1d.calculate(self.returns, self.portfolio_value)
        var_10d = calc_10d.calculate(self.returns, self.portfolio_value)

        # 10-day VaR should be more extreme
        self.assertLess(var_10d.var_value, var_1d.var_value)


class TestVaRCalculatorParametric(unittest.TestCase):
    """Test Parametric VaR calculation"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='parametric'
        )
        self.calculator = VaRCalculator(self.config)

    def test_calculate_parametric_var(self):
        """Test parametric VaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertLess(result.var_value, 0)
        self.assertEqual(result.method, 'parametric')

    def test_parametric_var_formula_validation(self):
        """Test parametric VaR formula: VaR = mu*T - z*sigma*sqrt(T)"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        mu = self.returns.mean()
        sigma = self.returns.std()
        z = stats.norm.ppf(0.05)  # 1 - 0.95

        expected_var_pct = mu - z * sigma  # For 1-day horizon
        # Note: z is negative for left tail, so we add z * sigma
        expected_var_pct = mu + z * sigma

        self.assertAlmostEqual(result.var_percent, expected_var_pct, places=4)


class TestVaRCalculatorMonteCarlo(unittest.TestCase):
    """Test Monte Carlo VaR calculation"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='monte_carlo',
            monte_carlo_simulations=10000
        )
        self.calculator = VaRCalculator(self.config)

    def test_calculate_monte_carlo_var(self):
        """Test Monte Carlo VaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertLess(result.var_value, 0)
        self.assertEqual(result.method, 'monte_carlo')

    def test_monte_carlo_var_stability(self):
        """Test Monte Carlo VaR consistency across runs"""
        np.random.seed(123)
        result1 = self.calculator.calculate(self.returns, self.portfolio_value)

        np.random.seed(123)
        result2 = self.calculator.calculate(self.returns, self.portfolio_value)

        # Same seed should produce same result
        self.assertAlmostEqual(result1.var_percent, result2.var_percent, places=4)


class TestVaRCalculatorMultipleConfidence(unittest.TestCase):
    """Test VaR calculation at multiple confidence levels"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000
        self.calculator = VaRCalculator()

    def test_calculate_var_by_confidence(self):
        """Test calculate_var_by_confidence"""
        result_df = self.calculator.calculate_var_by_confidence(
            self.returns,
            self.portfolio_value,
            confidence_levels=[0.90, 0.95, 0.99]
        )

        self.assertEqual(len(result_df), 3)
        self.assertIn('confidence_level', result_df.columns)
        self.assertIn('var_value', result_df.columns)

        # Higher confidence -> more extreme VaR
        vars_sorted = result_df.sort_values('confidence_level')['var_value'].values
        self.assertTrue(all(vars_sorted[i] >= vars_sorted[i+1] for i in range(len(vars_sorted)-1)))


class TestVaRCalculatorMultipleHorizon(unittest.TestCase):
    """Test VaR calculation at multiple time horizons"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.var_calculator import VaRCalculator

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000
        self.calculator = VaRCalculator()

    def test_calculate_var_by_horizon(self):
        """Test calculate_var_by_horizon"""
        result_df = self.calculator.calculate_var_by_horizon(
            self.returns,
            self.portfolio_value,
            horizons=[1, 5, 10]
        )

        self.assertEqual(len(result_df), 3)
        self.assertIn('horizon_days', result_df.columns)

        # Longer horizon -> more extreme VaR
        vars_sorted = result_df.sort_values('horizon_days')['var_value'].values
        self.assertTrue(all(vars_sorted[i] >= vars_sorted[i+1] for i in range(len(vars_sorted)-1)))


# =============================================================================
# CVaRCalculator Tests
# =============================================================================

class TestCVaRCalculatorInit(unittest.TestCase):
    """Test CVaRCalculator initialization"""

    def test_default_initialization(self):
        """Test default initialization"""
        from modules.risk.cvar_calculator import CVaRCalculator

        calculator = CVaRCalculator()

        self.assertEqual(calculator.config.confidence_level, 0.95)
        self.assertIsNotNone(calculator.var_calculator)

    def test_custom_config_initialization(self):
        """Test initialization with custom config"""
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(confidence_level=0.99)
        calculator = CVaRCalculator(config)

        self.assertEqual(calculator.config.confidence_level, 0.99)


class TestCVaRCalculatorHistorical(unittest.TestCase):
    """Test Historical CVaR calculation"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        self.calculator = CVaRCalculator(self.config)

    def test_calculate_historical_cvar(self):
        """Test historical CVaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertLess(result.cvar_value, 0)
        self.assertLess(result.cvar_percent, 0)
        self.assertEqual(result.method, 'historical')
        self.assertGreater(result.tail_observations, 0)

    def test_cvar_more_extreme_than_var(self):
        """Test that CVaR is more extreme than VaR"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        # CVaR should be more negative (larger loss) than VaR
        self.assertLess(result.cvar_value, result.metadata['var_value'])
        self.assertLess(result.cvar_percent, result.var_threshold)


class TestCVaRCalculatorParametric(unittest.TestCase):
    """Test Parametric CVaR calculation"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='parametric'
        )
        self.calculator = CVaRCalculator(self.config)

    def test_calculate_parametric_cvar(self):
        """Test parametric CVaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertEqual(result.method, 'parametric')
        self.assertLess(result.cvar_value, 0)


class TestCVaRCalculatorMonteCarlo(unittest.TestCase):
    """Test Monte Carlo CVaR calculation"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000

        self.config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='monte_carlo',
            monte_carlo_simulations=10000
        )
        self.calculator = CVaRCalculator(self.config)

    def test_calculate_monte_carlo_cvar(self):
        """Test Monte Carlo CVaR calculation"""
        result = self.calculator.calculate(self.returns, self.portfolio_value)

        self.assertIsNotNone(result)
        self.assertEqual(result.method, 'monte_carlo')
        self.assertLess(result.cvar_value, 0)


class TestCVaRCalculatorComparison(unittest.TestCase):
    """Test CVaR vs VaR comparison"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.risk.cvar_calculator import CVaRCalculator

        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        self.portfolio_value = 100_000_000
        self.calculator = CVaRCalculator()

    def test_compare_with_var(self):
        """Test compare_with_var method"""
        result_df = self.calculator.compare_with_var(
            self.returns,
            self.portfolio_value
        )

        self.assertEqual(len(result_df), 3)
        self.assertEqual(result_df.iloc[0]['metric'], 'VaR')
        self.assertEqual(result_df.iloc[1]['metric'], 'CVaR')
        self.assertEqual(result_df.iloc[2]['metric'], 'Difference')

        # CVaR should be more extreme
        var_value = result_df[result_df['metric'] == 'VaR']['value'].iloc[0]
        cvar_value = result_df[result_df['metric'] == 'CVaR']['value'].iloc[0]
        self.assertLess(cvar_value, var_value)


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("confidence_level,expected_valid", [
    (0.50, True),
    (0.90, True),
    (0.95, True),
    (0.99, True),
    (0.49, False),
    (1.0, False),
    (1.5, False),
])
def test_risk_config_confidence_validation(confidence_level, expected_valid):
    """Test RiskConfig confidence level validation"""
    from modules.risk.risk_base import RiskConfig

    config = RiskConfig(confidence_level=confidence_level)
    is_valid, _ = config.validate()

    assert is_valid == expected_valid


@pytest.mark.parametrize("var_method,expected_valid", [
    ('historical', True),
    ('parametric', True),
    ('monte_carlo', True),
    ('invalid', False),
    ('HISTORICAL', False),  # Case sensitive
])
def test_risk_config_method_validation(var_method, expected_valid):
    """Test RiskConfig var_method validation"""
    from modules.risk.risk_base import RiskConfig

    config = RiskConfig(var_method=var_method)
    is_valid, _ = config.validate()

    assert is_valid == expected_valid


@pytest.mark.parametrize("method", ['historical', 'parametric', 'monte_carlo'])
def test_var_all_methods_produce_result(method):
    """Test all VaR methods produce valid results"""
    from modules.risk.var_calculator import VaRCalculator
    from modules.risk.risk_base import RiskConfig

    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.02, 252))

    config = RiskConfig(var_method=method)
    calculator = VaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    assert result is not None
    assert result.var_value < 0
    assert result.method == method


@pytest.mark.parametrize("method", ['historical', 'parametric', 'monte_carlo'])
def test_cvar_all_methods_produce_result(method):
    """Test all CVaR methods produce valid results"""
    from modules.risk.cvar_calculator import CVaRCalculator
    from modules.risk.risk_base import RiskConfig

    np.random.seed(42)
    returns = pd.Series(np.random.normal(0.001, 0.02, 252))

    config = RiskConfig(var_method=method)
    calculator = CVaRCalculator(config)

    result = calculator.calculate(returns, 100_000_000)

    assert result is not None
    assert result.cvar_value < 0
    assert result.method == method


if __name__ == '__main__':
    unittest.main(verbosity=2)
