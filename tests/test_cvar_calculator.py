"""
Unit Tests for CVaR Calculator

Tests Conditional VaR (Expected Shortfall) calculation methods and
advanced features including multi-confidence, multi-horizon analysis,
and VaR comparison.

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - Track 5 Testing
"""

import pytest
import pandas as pd
import numpy as np
from modules.risk import CVaRCalculator, RiskConfig, CVaRResult


class TestCVaRCalculatorBasic:
    """Basic CVaR calculation tests"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data (1 year daily returns)"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    @pytest.fixture
    def portfolio_value(self):
        """Standard portfolio value for testing"""
        return 100_000_000  # 100M KRW

    def test_historical_cvar_calculation(self, sample_returns, portfolio_value):
        """Test historical CVaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='historical'
        )
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert isinstance(result, CVaRResult)
        assert result.cvar_value < 0  # CVaR should be negative (loss)
        assert result.confidence_level == 0.95
        assert result.time_horizon_days == 10
        assert result.method == 'historical'
        assert abs(result.cvar_percent) < 0.30  # CVaR should be < 30%
        assert result.portfolio_value == portfolio_value

        # Metadata checks
        assert 'var_value' in result.metadata
        assert 'var_percent' in result.metadata
        assert 'tail_pct' in result.metadata
        assert 'worst_loss' in result.metadata
        assert 'cvar_var_ratio' in result.metadata

    def test_parametric_cvar_calculation(self, sample_returns, portfolio_value):
        """Test parametric CVaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='parametric'
        )
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert result.method == 'parametric'
        assert result.cvar_value < 0
        assert result.confidence_level == 0.95
        assert abs(result.cvar_percent) < 0.30

    def test_monte_carlo_cvar_calculation(self, sample_returns, portfolio_value):
        """Test Monte Carlo CVaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='monte_carlo',
            monte_carlo_simulations=5000  # Reduced for faster testing
        )
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert result.method == 'monte_carlo'
        assert result.cvar_value < 0
        assert abs(result.cvar_percent) < 0.30

    def test_monte_carlo_reproducibility(self, sample_returns, portfolio_value):
        """Test Monte Carlo CVaR reproducibility with seed"""
        config = RiskConfig(
            confidence_level=0.95,
            var_method='monte_carlo',
            monte_carlo_simulations=5000
        )
        cvar_calc = CVaRCalculator(config)

        # Run twice with same seed
        np.random.seed(42)
        result1 = cvar_calc.calculate(sample_returns, portfolio_value)

        np.random.seed(42)
        result2 = cvar_calc.calculate(sample_returns, portfolio_value)

        # Results should be identical
        assert result1.cvar_value == result2.cvar_value
        assert result1.cvar_percent == result2.cvar_percent

    def test_1day_horizon(self, sample_returns, portfolio_value):
        """Test 1-day CVaR (no scaling needed)"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(sample_returns, portfolio_value)

        assert result.time_horizon_days == 1
        assert result.cvar_value < 0

    def test_higher_confidence_level(self, sample_returns, portfolio_value):
        """Test 99% confidence CVaR (should be more extreme than 95%)"""
        # 95% confidence
        config_95 = RiskConfig(confidence_level=0.95, var_method='historical')
        cvar_calc_95 = CVaRCalculator(config_95)
        result_95 = cvar_calc_95.calculate(sample_returns, portfolio_value)

        # 99% confidence
        config_99 = RiskConfig(confidence_level=0.99, var_method='historical')
        cvar_calc_99 = CVaRCalculator(config_99)
        result_99 = cvar_calc_99.calculate(sample_returns, portfolio_value)

        # 99% CVaR should be more extreme (more negative) than 95% CVaR
        assert result_99.cvar_value < result_95.cvar_value
        assert abs(result_99.cvar_percent) > abs(result_95.cvar_percent)


class TestCVaRCalculatorInputValidation:
    """Test input validation and error handling"""

    def test_insufficient_data(self):
        """Test error handling for insufficient data"""
        config = RiskConfig()
        cvar_calc = CVaRCalculator(config)

        # Only 20 observations (< 30 minimum)
        insufficient_returns = pd.Series(np.random.normal(0, 0.02, 20))

        with pytest.raises(ValueError, match="Insufficient returns data"):
            cvar_calc.calculate(insufficient_returns, 100_000_000)

    def test_nan_values(self):
        """Test error handling for NaN values"""
        config = RiskConfig()
        cvar_calc = CVaRCalculator(config)

        # Returns with NaN
        returns_with_nan = pd.Series([0.01, 0.02, np.nan, -0.01, 0.015] * 10)

        with pytest.raises(ValueError, match="Returns contain NaN values"):
            cvar_calc.calculate(returns_with_nan, 100_000_000)

    def test_invalid_method(self):
        """Test error handling for invalid CVaR method"""
        config = RiskConfig(var_method='invalid_method')

        with pytest.raises(ValueError, match="Invalid var_method"):
            CVaRCalculator(config)

    def test_invalid_confidence_level(self):
        """Test error handling for invalid confidence level"""
        config = RiskConfig(confidence_level=1.5)  # > 1.0

        with pytest.raises(ValueError, match="confidence_level must be"):
            CVaRCalculator(config)


class TestCVaRCalculatorAdvanced:
    """Advanced CVaR calculator features"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    def test_cvar_by_confidence(self, sample_returns):
        """Test CVaR calculation at multiple confidence levels"""
        config = RiskConfig(var_method='historical')
        cvar_calc = CVaRCalculator(config)

        cvars_df = cvar_calc.calculate_cvar_by_confidence(
            sample_returns,
            100_000_000,
            confidence_levels=[0.90, 0.95, 0.99]
        )

        # Assertions
        assert len(cvars_df) == 3
        assert 'confidence_level' in cvars_df.columns
        assert 'cvar_value' in cvars_df.columns
        assert 'cvar_percent' in cvars_df.columns
        assert 'var_value' in cvars_df.columns
        assert 'var_percent' in cvars_df.columns

        # CVaR should increase (more negative) with higher confidence
        assert cvars_df.iloc[0]['cvar_value'] > cvars_df.iloc[1]['cvar_value']
        assert cvars_df.iloc[1]['cvar_value'] > cvars_df.iloc[2]['cvar_value']

    def test_cvar_by_horizon(self, sample_returns):
        """Test CVaR calculation at multiple time horizons"""
        config = RiskConfig(var_method='historical')
        cvar_calc = CVaRCalculator(config)

        cvars_df = cvar_calc.calculate_cvar_by_horizon(
            sample_returns,
            100_000_000,
            horizons=[1, 10, 20]
        )

        # Assertions
        assert len(cvars_df) == 3
        assert 'horizon_days' in cvars_df.columns
        assert 'cvar_value' in cvars_df.columns
        assert 'var_value' in cvars_df.columns

        # CVaR magnitude should generally increase with longer horizon
        assert abs(cvars_df.iloc[2]['cvar_value']) > abs(cvars_df.iloc[0]['cvar_value'])

    def test_compare_with_var(self, sample_returns):
        """Test CVaR vs VaR comparison"""
        config = RiskConfig(var_method='historical')
        cvar_calc = CVaRCalculator(config)

        comparison_df = cvar_calc.compare_with_var(sample_returns, 100_000_000)

        # Assertions
        assert isinstance(comparison_df, pd.DataFrame)
        assert len(comparison_df) == 3  # VaR, CVaR, Difference
        assert 'metric' in comparison_df.columns
        assert 'value' in comparison_df.columns
        assert 'percent' in comparison_df.columns

        # Extract values
        var_value = comparison_df[comparison_df['metric'] == 'VaR']['value'].iloc[0]
        cvar_value = comparison_df[comparison_df['metric'] == 'CVaR']['value'].iloc[0]
        diff_value = comparison_df[comparison_df['metric'] == 'Difference']['value'].iloc[0]

        # CVaR should be more extreme than VaR (more negative)
        assert cvar_value < var_value
        assert diff_value < 0  # Difference should be negative


class TestCVaRCalculatorComparison:
    """Compare CVaR properties and methods"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample returns with known characteristics"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    def test_cvar_greater_than_var(self, sample_returns):
        """Test that CVaR >= VaR for all methods"""
        config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        portfolio_value = 100_000_000

        for method in ['historical', 'parametric', 'monte_carlo']:
            config.var_method = method
            cvar_calc = CVaRCalculator(config)

            # Set seed for Monte Carlo reproducibility
            if method == 'monte_carlo':
                np.random.seed(42)

            result = cvar_calc.calculate(sample_returns, portfolio_value)

            # CVaR should be more extreme (more negative) than VaR
            assert result.cvar_value < result.metadata['var_value']
            assert abs(result.cvar_percent) > abs(result.metadata['var_percent'])

    def test_method_comparison(self, sample_returns):
        """Compare all three CVaR methods"""
        config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        portfolio_value = 100_000_000

        # Calculate CVaR with each method
        results = {}
        for method in ['historical', 'parametric', 'monte_carlo']:
            config.var_method = method
            cvar_calc = CVaRCalculator(config)

            # Set seed for Monte Carlo reproducibility
            if method == 'monte_carlo':
                np.random.seed(42)

            result = cvar_calc.calculate(sample_returns, portfolio_value)
            results[method] = result

        # All methods should produce negative CVaR
        assert all(r.cvar_value < 0 for r in results.values())

        # All methods should be reasonably close (within 3x of each other)
        values = [abs(r.cvar_value) for r in results.values()]
        max_val = max(values)
        min_val = min(values)
        assert max_val / min_val < 3.0  # Methods shouldn't differ by more than 3x

    def test_tail_observations_count(self, sample_returns):
        """Test that tail observations count is reasonable"""
        config = RiskConfig(confidence_level=0.95, var_method='historical')
        cvar_calc = CVaRCalculator(config)

        result = cvar_calc.calculate(sample_returns, 100_000_000)

        # Tail percentage should be approximately (1 - confidence_level)
        expected_tail_pct = 1 - config.confidence_level
        actual_tail_pct = result.metadata['tail_pct']

        # Allow reasonable tolerance (within 50% of expected)
        assert abs(actual_tail_pct - expected_tail_pct) < expected_tail_pct * 0.5


class TestCVaRResultFormat:
    """Test CVaR result formatting and serialization"""

    def test_result_to_dict(self):
        """Test CVaRResult to_dict() method"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig()
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(returns, 100_000_000)

        result_dict = result.to_dict()

        # Check all required keys
        assert 'cvar_value' in result_dict
        assert 'cvar_percent' in result_dict
        assert 'var_threshold' in result_dict
        assert 'confidence_level' in result_dict
        assert 'time_horizon_days' in result_dict
        assert 'method' in result_dict
        assert 'tail_observations' in result_dict
        assert 'portfolio_value' in result_dict
        assert 'calculation_date' in result_dict
        assert 'metadata' in result_dict

    def test_result_str(self):
        """Test CVaRResult __str__() method"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        cvar_calc = CVaRCalculator(config)
        result = cvar_calc.calculate(returns, 100_000_000)

        result_str = str(result)

        # Check string contains key information
        assert '95%' in result_str or '0.95' in result_str
        assert '10d' in result_str or '10' in result_str
        assert 'historical' in result_str.lower() or result.method in result_str
        assert 'tail obs' in result_str.lower()


# Run pytest if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
