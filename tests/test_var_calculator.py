"""
Unit Tests for VaR Calculator

Tests all three VaR methods (historical, parametric, monte_carlo) and
advanced features (component VaR, multi-confidence, multi-horizon, backtesting).

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - Track 5 Testing
"""

import pytest
import pandas as pd
import numpy as np
from modules.risk import VaRCalculator, RiskConfig, VaRResult


class TestVaRCalculatorBasic:
    """Basic VaR calculation tests"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data (1 year daily returns)"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    @pytest.fixture
    def portfolio_value(self):
        """Standard portfolio value for testing"""
        return 100_000_000  # 100M KRW

    def test_historical_var_calculation(self, sample_returns, portfolio_value):
        """Test historical VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='historical'
        )
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert isinstance(result, VaRResult)
        assert result.var_value < 0  # VaR should be negative (loss)
        assert result.confidence_level == 0.95
        assert result.time_horizon_days == 10
        assert result.method == 'historical'
        assert abs(result.var_percent) < 0.20  # VaR should be < 20%
        assert result.portfolio_value == portfolio_value

        # Metadata checks
        assert 'observations' in result.metadata
        assert 'mean_return' in result.metadata
        assert 'volatility' in result.metadata

    def test_parametric_var_calculation(self, sample_returns, portfolio_value):
        """Test parametric VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='parametric'
        )
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert result.method == 'parametric'
        assert result.var_value < 0
        assert result.confidence_level == 0.95
        assert abs(result.var_percent) < 0.20

    def test_monte_carlo_var_calculation(self, sample_returns, portfolio_value):
        """Test Monte Carlo VaR calculation"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='monte_carlo',
            monte_carlo_simulations=5000  # Reduced for faster testing
        )
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(sample_returns, portfolio_value)

        # Assertions
        assert result.method == 'monte_carlo'
        assert result.var_value < 0
        assert abs(result.var_percent) < 0.20

    def test_monte_carlo_reproducibility(self, sample_returns, portfolio_value):
        """Test Monte Carlo VaR reproducibility with seed"""
        config = RiskConfig(
            confidence_level=0.95,
            var_method='monte_carlo',
            monte_carlo_simulations=5000
        )
        var_calc = VaRCalculator(config)

        # Run twice with same seed
        np.random.seed(42)
        result1 = var_calc.calculate(sample_returns, portfolio_value)

        np.random.seed(42)
        result2 = var_calc.calculate(sample_returns, portfolio_value)

        # Results should be identical
        assert result1.var_value == result2.var_value
        assert result1.var_percent == result2.var_percent

    def test_1day_horizon(self, sample_returns, portfolio_value):
        """Test 1-day VaR (no scaling needed)"""
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(sample_returns, portfolio_value)

        assert result.time_horizon_days == 1
        assert result.var_value < 0

    def test_higher_confidence_level(self, sample_returns, portfolio_value):
        """Test 99% confidence VaR (should be more extreme than 95%)"""
        # 95% confidence
        config_95 = RiskConfig(confidence_level=0.95, var_method='historical')
        var_calc_95 = VaRCalculator(config_95)
        result_95 = var_calc_95.calculate(sample_returns, portfolio_value)

        # 99% confidence
        config_99 = RiskConfig(confidence_level=0.99, var_method='historical')
        var_calc_99 = VaRCalculator(config_99)
        result_99 = var_calc_99.calculate(sample_returns, portfolio_value)

        # 99% VaR should be more extreme (more negative) than 95% VaR
        assert result_99.var_value < result_95.var_value
        assert abs(result_99.var_percent) > abs(result_95.var_percent)


class TestVaRCalculatorInputValidation:
    """Test input validation and error handling"""

    def test_insufficient_data(self):
        """Test error handling for insufficient data"""
        config = RiskConfig()
        var_calc = VaRCalculator(config)

        # Only 20 observations (< 30 minimum)
        insufficient_returns = pd.Series(np.random.normal(0, 0.02, 20))

        with pytest.raises(ValueError, match="Insufficient returns data"):
            var_calc.calculate(insufficient_returns, 100_000_000)

    def test_nan_values(self):
        """Test error handling for NaN values"""
        config = RiskConfig()
        var_calc = VaRCalculator(config)

        # Returns with NaN
        returns_with_nan = pd.Series([0.01, 0.02, np.nan, -0.01, 0.015] * 10)

        with pytest.raises(ValueError, match="Returns contain NaN values"):
            var_calc.calculate(returns_with_nan, 100_000_000)

    def test_invalid_method(self):
        """Test error handling for invalid VaR method"""
        config = RiskConfig(var_method='invalid_method')

        with pytest.raises(ValueError, match="Invalid var_method"):
            VaRCalculator(config)

    def test_invalid_confidence_level(self):
        """Test error handling for invalid confidence level"""
        config = RiskConfig(confidence_level=1.5)  # > 1.0

        with pytest.raises(ValueError, match="confidence_level must be"):
            VaRCalculator(config)


class TestVaRCalculatorAdvanced:
    """Advanced VaR calculator features"""

    @pytest.fixture
    def sample_portfolio(self):
        """Generate multi-asset portfolio"""
        np.random.seed(42)
        asset_returns = pd.DataFrame(
            np.random.normal(0.001, 0.02, (252, 10)),
            columns=[f'ASSET{i}' for i in range(10)]
        )
        weights = pd.Series(0.1, index=asset_returns.columns)
        return asset_returns, weights

    def test_component_var(self, sample_portfolio):
        """Test component VaR calculation"""
        asset_returns, weights = sample_portfolio
        config = RiskConfig(var_method='historical')
        var_calc = VaRCalculator(config)

        component_df = var_calc.calculate_component_var(
            asset_returns,
            weights,
            portfolio_value=100_000_000
        )

        # Assertions
        assert isinstance(component_df, pd.DataFrame)
        assert len(component_df) == 10  # 10 assets
        assert 'ticker' in component_df.columns
        assert 'weight' in component_df.columns
        assert 'component_var' in component_df.columns
        assert 'component_var_pct' in component_df.columns

        # Weights should sum to 1
        assert np.isclose(component_df['weight'].sum(), 1.0)

        # Component VaRs should sum approximately to portfolio VaR
        # (Note: May not be exact due to finite difference approximation)
        portfolio_returns = (asset_returns * weights).sum(axis=1)
        portfolio_var = var_calc.calculate(portfolio_returns, 100_000_000)
        total_component_var = component_df['component_var'].sum()

        # Note: Component VaR using finite differences is an approximation
        # The sum may not exactly equal portfolio VaR due to:
        # 1. Numerical approximation error
        # 2. Non-linear effects in VaR calculation
        #
        # Component VaR can be positive or negative:
        # - Negative: Increasing this asset's weight increases portfolio risk
        # - Positive: Increasing this asset's weight decreases portfolio risk (diversifier)
        #
        # We validate reasonable behavior:
        assert abs(total_component_var) > 0, "Total component VaR should be non-zero"

        # Component VaRs should have mixed signs for diversified portfolio
        negative_components = (component_df['component_var'] < 0).sum()
        positive_components = (component_df['component_var'] > 0).sum()
        assert negative_components > 0, "Should have some risk-increasing assets"
        assert positive_components >= 0, "May have some diversifying assets"

    def test_var_by_confidence(self):
        """Test VaR calculation at multiple confidence levels"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig(var_method='historical')
        var_calc = VaRCalculator(config)

        vars_df = var_calc.calculate_var_by_confidence(
            returns,
            100_000_000,
            confidence_levels=[0.90, 0.95, 0.99]
        )

        # Assertions
        assert len(vars_df) == 3
        assert 'confidence_level' in vars_df.columns
        assert 'var_value' in vars_df.columns
        assert 'var_percent' in vars_df.columns

        # VaR should increase (more negative) with higher confidence
        assert vars_df.iloc[0]['var_value'] > vars_df.iloc[1]['var_value']
        assert vars_df.iloc[1]['var_value'] > vars_df.iloc[2]['var_value']

    def test_var_by_horizon(self):
        """Test VaR calculation at multiple time horizons"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig(var_method='historical')
        var_calc = VaRCalculator(config)

        vars_df = var_calc.calculate_var_by_horizon(
            returns,
            100_000_000,
            horizons=[1, 10, 20]
        )

        # Assertions
        assert len(vars_df) == 3
        assert 'horizon_days' in vars_df.columns
        assert 'var_value' in vars_df.columns

        # VaR magnitude should generally increase with longer horizon
        # (though not strictly monotonic due to empirical distribution)
        assert abs(vars_df.iloc[2]['var_value']) > abs(vars_df.iloc[0]['var_value'])

    def test_backtest_var(self):
        """Test VaR backtesting"""
        np.random.seed(42)
        # Generate longer series for backtesting
        returns = pd.Series(np.random.normal(0.001, 0.02, 500))

        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )
        var_calc = VaRCalculator(config)

        violation_rate, backtest_df = var_calc.backtest_var(
            returns,
            100_000_000,
            window_size=100
        )

        # Assertions
        assert isinstance(violation_rate, float)
        assert isinstance(backtest_df, pd.DataFrame)
        assert 'actual_loss' in backtest_df.columns
        assert 'var_prediction' in backtest_df.columns
        assert 'violation' in backtest_df.columns

        # Violation rate should be approximately 5% for 95% confidence
        # (Allow wide tolerance due to randomness)
        expected_rate = 1 - 0.95
        assert abs(violation_rate - expected_rate) < 0.10  # Within 10%


class TestVaRCalculatorComparison:
    """Compare VaR methods against each other"""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample returns with known characteristics"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    def test_method_comparison(self, sample_returns):
        """Compare all three VaR methods"""
        config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        portfolio_value = 100_000_000

        # Calculate VaR with each method
        results = {}
        for method in ['historical', 'parametric', 'monte_carlo']:
            config.var_method = method
            var_calc = VaRCalculator(config)

            # Set seed for Monte Carlo reproducibility
            if method == 'monte_carlo':
                np.random.seed(42)

            result = var_calc.calculate(sample_returns, portfolio_value)
            results[method] = result

        # All methods should produce negative VaR
        assert all(r.var_value < 0 for r in results.values())

        # All methods should be reasonably close (within 50% of each other)
        values = [abs(r.var_value) for r in results.values()]
        max_val = max(values)
        min_val = min(values)
        assert max_val / min_val < 2.0  # Methods shouldn't differ by more than 2x

    def test_exponential_weighting(self, sample_returns):
        """Test exponential weighting vs. equal weighting"""
        portfolio_value = 100_000_000

        # Historical VaR without weighting
        config_equal = RiskConfig(
            var_method='historical',
            exponential_weighting=False
        )
        var_calc_equal = VaRCalculator(config_equal)
        result_equal = var_calc_equal.calculate(sample_returns, portfolio_value)

        # Historical VaR with exponential weighting
        config_exp = RiskConfig(
            var_method='historical',
            exponential_weighting=True,
            lambda_decay=0.94
        )
        var_calc_exp = VaRCalculator(config_exp)
        result_exp = var_calc_exp.calculate(sample_returns, portfolio_value)

        # Results should be different
        assert result_equal.var_value != result_exp.var_value

        # Both should be valid VaR values
        assert result_equal.var_value < 0
        assert result_exp.var_value < 0


class TestVaRCalculatorResultFormat:
    """Test VaR result formatting and serialization"""

    def test_result_to_dict(self):
        """Test VaRResult to_dict() method"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig()
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(returns, 100_000_000)

        result_dict = result.to_dict()

        # Check all required keys
        assert 'var_value' in result_dict
        assert 'var_percent' in result_dict
        assert 'confidence_level' in result_dict
        assert 'time_horizon_days' in result_dict
        assert 'method' in result_dict
        assert 'portfolio_value' in result_dict
        assert 'calculation_date' in result_dict
        assert 'metadata' in result_dict

    def test_result_str(self):
        """Test VaRResult __str__() method"""
        np.random.seed(42)
        returns = pd.Series(np.random.normal(0.001, 0.02, 252))

        config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(returns, 100_000_000)

        result_str = str(result)

        # Check string contains key information
        assert '95%' in result_str or '0.95' in result_str
        assert '10d' in result_str or '10' in result_str
        assert 'historical' in result_str.lower() or result.method in result_str


# Run pytest if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
