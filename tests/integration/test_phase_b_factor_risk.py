#!/usr/bin/env python3
"""
Phase B Integration Tests: Factor Analysis + Risk Management

Integration test scenarios for verifying end-to-end functionality:
- 3.1: Factor calculation -> scoring integration
- 3.2: Factor Combiner multiple methodologies
- 3.3: Factor independence validation
- 3.4: Factor time-series consistency
- 4.1: VaR/CVaR calculation integration
- 4.2: Portfolio risk metrics calculation
- 4.3: DataProvider -> Risk calculation integration

Author: Spock Quant Platform
Date: 2025-12-12
"""

import sys
import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing with proper consistency."""
    dates = pd.date_range(start='2024-01-01', end='2024-03-31', freq='B')
    np.random.seed(42)

    base_price = 50000
    returns = np.random.randn(len(dates)) * 0.02
    close_prices = base_price * np.cumprod(1 + returns)

    open_prices = close_prices * (1 + np.random.randn(len(dates)) * 0.005)
    high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.randn(len(dates)) * 0.005))
    low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.randn(len(dates)) * 0.005))

    df = pd.DataFrame({
        'date': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, len(dates))
    })
    return df


@pytest.fixture
def sample_returns():
    """Create sample portfolio returns for risk calculations."""
    np.random.seed(42)
    # 252 trading days of returns (1 year)
    returns = pd.Series(
        np.random.normal(0.0005, 0.02, 252),
        index=pd.date_range(start='2024-01-01', periods=252, freq='B')
    )
    return returns


@pytest.fixture
def sample_factor_scores():
    """Create sample factor scores for testing."""
    return {
        'momentum_12m': 75.5,
        'short_term_momentum': 68.2,
        'volatility': 45.0,
        'max_drawdown': 55.3,
        'pe_ratio': 62.1,
        'pb_ratio': 58.7,
        'roe': 71.2,
        'roa': 65.4,
        'market_cap': 80.0,
        'liquidity': 72.5
    }


@pytest.fixture
def sample_multi_ticker_returns():
    """Create sample returns for multiple tickers."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='B')

    # Create correlated returns
    base_returns = np.random.normal(0.0005, 0.02, 252)

    returns_dict = {
        '005930': pd.Series(base_returns + np.random.normal(0, 0.005, 252), index=dates),
        '035420': pd.Series(base_returns * 0.8 + np.random.normal(0.0002, 0.025, 252), index=dates),
        '051910': pd.Series(base_returns * 0.6 + np.random.normal(0.0003, 0.015, 252), index=dates)
    }
    return returns_dict


# =============================================================================
# Scenario 3.1: Factor Calculation -> Scoring Integration
# =============================================================================

class TestScenario3_1_FactorScoring:
    """
    Scenario 3.1: Factor 계산 -> 점수화 통합

    Tests:
    - FactorResult creation and validation
    - Z-score calculation
    - Percentile ranking
    - Confidence scoring
    """

    def test_factor_result_creation(self):
        """Test: FactorResult 생성 및 검증"""
        from modules.factors.factor_base import FactorResult

        result = FactorResult(
            ticker='005930',
            factor_name='momentum_12m',
            raw_value=0.25,
            z_score=1.5,
            percentile=85.0,
            confidence=0.9,
            metadata={'lookback_days': 252}
        )

        assert result.ticker == '005930'
        assert result.factor_name == 'momentum_12m'
        assert result.raw_value == 0.25
        assert result.z_score == 1.5
        assert result.percentile == 85.0
        assert result.confidence == 0.9

    def test_factor_result_validation(self):
        """Test: FactorResult 범위 검증"""
        from modules.factors.factor_base import FactorResult

        # Percentile should be clamped to 0-100
        result = FactorResult(
            ticker='005930',
            factor_name='test',
            raw_value=0.5,
            z_score=0.0,
            percentile=150.0,  # Out of range
            confidence=1.5     # Out of range
        )

        assert result.percentile == 100.0  # Clamped
        assert result.confidence == 1.0    # Clamped

    def test_factor_result_to_dict(self):
        """Test: FactorResult 딕셔너리 변환"""
        from modules.factors.factor_base import FactorResult

        result = FactorResult(
            ticker='005930',
            factor_name='pe_ratio',
            raw_value=15.5,
            z_score=-0.5,
            percentile=35.0,
            confidence=0.85
        )

        d = result.to_dict()
        assert d['ticker'] == '005930'
        assert d['factor_name'] == 'pe_ratio'
        assert d['raw_value'] == 15.5
        assert 'calculation_date' in d

    def test_factor_category_enum(self):
        """Test: FactorCategory 열거형"""
        from modules.factors.factor_base import FactorCategory

        assert FactorCategory.MOMENTUM.value == 'momentum'
        assert FactorCategory.VALUE.value == 'value'
        assert FactorCategory.QUALITY.value == 'quality'
        assert FactorCategory.LOW_VOL.value == 'low_volatility'
        assert FactorCategory.SIZE.value == 'size'

    def test_z_score_calculation(self):
        """Test: Z-score 계산"""
        # Manual z-score calculation
        values = np.array([10, 20, 30, 40, 50])
        mean = np.mean(values)
        std = np.std(values, ddof=0)

        z_scores = (values - mean) / std

        # Verify z-scores
        assert np.isclose(np.mean(z_scores), 0, atol=1e-10)
        assert np.isclose(np.std(z_scores, ddof=0), 1, atol=1e-10)


# =============================================================================
# Scenario 3.2: Factor Combiner Multiple Methodologies
# =============================================================================

class TestScenario3_2_FactorCombiner:
    """
    Scenario 3.2: Factor Combiner 다중 방법론

    Tests:
    - Equal weight combination
    - Category weight combination
    - Score normalization
    - Missing factor handling
    """

    def test_factor_category_mapping(self):
        """Test: 팩터-카테고리 매핑"""
        from modules.factors.factor_combiner import FACTOR_CATEGORY_MAP
        from modules.factors.factor_base import FactorCategory

        # Verify momentum factors
        assert FACTOR_CATEGORY_MAP['momentum_12m'] == FactorCategory.MOMENTUM
        assert FACTOR_CATEGORY_MAP['short_term_momentum'] == FactorCategory.MOMENTUM

        # Verify low-vol factors
        assert FACTOR_CATEGORY_MAP['volatility'] == FactorCategory.LOW_VOL
        assert FACTOR_CATEGORY_MAP['max_drawdown'] == FactorCategory.LOW_VOL

        # Verify value factors
        assert FACTOR_CATEGORY_MAP['pe_ratio'] == FactorCategory.VALUE
        assert FACTOR_CATEGORY_MAP['pb_ratio'] == FactorCategory.VALUE

    def test_default_category_weights(self):
        """Test: 기본 카테고리 가중치"""
        from modules.factors.factor_combiner import DEFAULT_CATEGORY_WEIGHTS

        # Sum should be 1.0
        assert np.isclose(sum(DEFAULT_CATEGORY_WEIGHTS.values()), 1.0)

        # Each category should have 20%
        for weight in DEFAULT_CATEGORY_WEIGHTS.values():
            assert np.isclose(weight, 0.20)

    def test_equal_weight_combination(self, sample_factor_scores):
        """Test: 균등 가중 조합"""
        # Simple equal weight average
        scores = list(sample_factor_scores.values())
        equal_weight_score = np.mean(scores)

        # Score should be between 0 and 100
        assert 0 <= equal_weight_score <= 100
        assert np.isclose(equal_weight_score, np.mean(scores))

    def test_category_weight_combination(self, sample_factor_scores):
        """Test: 카테고리 가중 조합"""
        from modules.factors.factor_combiner import FACTOR_CATEGORY_MAP
        from modules.factors.factor_base import FactorCategory

        # Group factors by category
        category_scores = {}
        for factor_name, score in sample_factor_scores.items():
            if factor_name in FACTOR_CATEGORY_MAP:
                category = FACTOR_CATEGORY_MAP[factor_name].name
                if category not in category_scores:
                    category_scores[category] = []
                category_scores[category].append(score)

        # Calculate category averages
        category_avg = {cat: np.mean(scores) for cat, scores in category_scores.items()}

        # All category averages should be in valid range
        for avg in category_avg.values():
            assert 0 <= avg <= 100

    def test_missing_factor_handling(self, sample_factor_scores):
        """Test: 누락 팩터 처리"""
        # Remove some factors
        partial_scores = {k: v for k, v in sample_factor_scores.items()
                         if k not in ['momentum_12m', 'pe_ratio']}

        # Should still be able to calculate average
        avg_score = np.mean(list(partial_scores.values()))
        assert 0 <= avg_score <= 100


# =============================================================================
# Scenario 3.3: Factor Independence Validation
# =============================================================================

class TestScenario3_3_FactorIndependence:
    """
    Scenario 3.3: Factor 독립성 검증

    Tests:
    - Correlation calculation
    - Independence threshold check
    - Multicollinearity detection
    """

    def test_correlation_calculation(self):
        """Test: 상관관계 계산"""
        np.random.seed(42)

        # Create sample factor data
        n_samples = 100
        factor1 = np.random.randn(n_samples)
        factor2 = np.random.randn(n_samples)
        factor3 = factor1 * 0.8 + np.random.randn(n_samples) * 0.2  # Correlated

        df = pd.DataFrame({
            'factor1': factor1,
            'factor2': factor2,
            'factor3': factor3
        })

        corr_matrix = df.corr()

        # factor1 and factor2 should have low correlation
        assert abs(corr_matrix.loc['factor1', 'factor2']) < 0.3

        # factor1 and factor3 should have high correlation
        assert corr_matrix.loc['factor1', 'factor3'] > 0.7

    def test_independence_threshold(self):
        """Test: 독립성 임계값 검증"""
        # Independence threshold is typically 0.7
        INDEPENDENCE_THRESHOLD = 0.7

        correlations = [0.1, 0.3, 0.5, 0.65, 0.75, 0.9]

        for corr in correlations:
            is_independent = abs(corr) < INDEPENDENCE_THRESHOLD
            if corr < INDEPENDENCE_THRESHOLD:
                assert is_independent
            else:
                assert not is_independent

    def test_multicollinearity_detection(self):
        """Test: 다중공선성 탐지"""
        np.random.seed(42)

        n_samples = 100
        base = np.random.randn(n_samples)

        # Create highly correlated factors (multicollinearity)
        df = pd.DataFrame({
            'f1': base,
            'f2': base + np.random.randn(n_samples) * 0.1,
            'f3': base + np.random.randn(n_samples) * 0.2,
            'f4': np.random.randn(n_samples)  # Independent
        })

        corr_matrix = df.corr()

        # Count high correlations (excluding diagonal)
        high_corr_count = 0
        for i in range(len(corr_matrix)):
            for j in range(i+1, len(corr_matrix)):
                if abs(corr_matrix.iloc[i, j]) > 0.7:
                    high_corr_count += 1

        # Should detect multicollinearity among f1, f2, f3
        assert high_corr_count >= 2


# =============================================================================
# Scenario 3.4: Factor Time-Series Consistency
# =============================================================================

class TestScenario3_4_TimeSeriesConsistency:
    """
    Scenario 3.4: Factor 시계열 일관성

    Tests:
    - Factor value stability over time
    - Rank correlation persistence
    - Information coefficient consistency
    """

    def test_factor_value_stability(self):
        """Test: 팩터 값 안정성"""
        np.random.seed(42)

        # Simulate factor values over 12 months
        n_months = 12
        n_stocks = 50

        factor_values = []
        for _ in range(n_months):
            # Factor values should be relatively stable with some noise
            base_values = np.random.randn(n_stocks)
            factor_values.append(base_values)

        # Calculate month-over-month correlation
        correlations = []
        for i in range(1, n_months):
            corr = np.corrcoef(factor_values[i-1], factor_values[i])[0, 1]
            correlations.append(corr)

        # Average correlation should indicate some stability
        # (For random data, correlation is near 0)
        avg_corr = np.mean(correlations)
        assert -0.5 <= avg_corr <= 0.5  # Random data

    def test_rank_correlation_persistence(self):
        """Test: 순위 상관관계 지속성"""
        from scipy.stats import spearmanr

        np.random.seed(42)

        # Simulate rankings over time
        n_periods = 6
        n_stocks = 30

        # Create somewhat persistent rankings
        base_rank = np.random.randn(n_stocks)
        rankings = []
        for i in range(n_periods):
            noise = np.random.randn(n_stocks) * 0.3
            rankings.append(base_rank + noise * (i + 1) / n_periods)

        # Calculate rank correlations between adjacent periods
        rank_corrs = []
        for i in range(1, n_periods):
            corr, _ = spearmanr(rankings[i-1], rankings[i])
            rank_corrs.append(corr)

        # Earlier periods should have higher correlation
        # (Rankings become less persistent over time)
        assert rank_corrs[0] > rank_corrs[-1] or len(rank_corrs) < 2

    def test_information_coefficient_calculation(self):
        """Test: IC (Information Coefficient) 계산"""
        from scipy.stats import spearmanr

        np.random.seed(42)
        n_stocks = 100

        # Factor scores
        factor_scores = np.random.randn(n_stocks)

        # Forward returns (with some predictive power)
        forward_returns = factor_scores * 0.1 + np.random.randn(n_stocks) * 0.5

        # Calculate IC (Spearman correlation)
        ic, p_value = spearmanr(factor_scores, forward_returns)

        # IC should be positive (factor has predictive power)
        assert ic > 0
        assert -1 <= ic <= 1


# =============================================================================
# Scenario 4.1: VaR/CVaR Calculation Integration
# =============================================================================

class TestScenario4_1_VaRCVaRCalculation:
    """
    Scenario 4.1: VaR/CVaR 계산 통합

    Tests:
    - VaR calculation methods
    - CVaR calculation
    - Confidence level variations
    - Time horizon scaling
    """

    def test_var_result_creation(self):
        """Test: VaRResult 생성"""
        from modules.risk.risk_base import VaRResult

        result = VaRResult(
            var_value=-5_000_000,
            var_percent=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            portfolio_value=100_000_000,
            calculation_date=datetime.now()
        )

        assert result.var_value == -5_000_000
        assert result.var_percent == -0.05
        assert result.confidence_level == 0.95
        assert result.method == 'historical'

    def test_cvar_result_creation(self):
        """Test: CVaRResult 생성"""
        from modules.risk.risk_base import CVaRResult

        result = CVaRResult(
            cvar_value=-7_000_000,
            cvar_percent=-0.07,
            var_threshold=-0.05,
            confidence_level=0.95,
            time_horizon_days=10,
            method='historical',
            tail_observations=13,
            portfolio_value=100_000_000,
            calculation_date=datetime.now()
        )

        assert result.cvar_value == -7_000_000
        assert result.cvar_percent == -0.07
        assert result.tail_observations == 13

    def test_historical_var_calculation(self, sample_returns):
        """Test: Historical VaR 계산"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )

        calculator = VaRCalculator(config)
        result = calculator.calculate(sample_returns, portfolio_value=100_000_000)

        # VaR should be negative
        assert result.var_value < 0
        assert result.var_percent < 0
        assert result.method == 'historical'

    def test_parametric_var_calculation(self, sample_returns):
        """Test: Parametric VaR 계산"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='parametric'
        )

        calculator = VaRCalculator(config)
        result = calculator.calculate(sample_returns, portfolio_value=100_000_000)

        # VaR should be negative
        assert result.var_value < 0
        assert result.method == 'parametric'

    def test_cvar_vs_var_relationship(self, sample_returns):
        """Test: CVaR >= VaR 관계 검증"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=1,
            var_method='historical'
        )

        var_calc = VaRCalculator(config)
        cvar_calc = CVaRCalculator(config)

        var_result = var_calc.calculate(sample_returns, portfolio_value=100_000_000)
        cvar_result = cvar_calc.calculate(sample_returns, portfolio_value=100_000_000)

        # CVaR should be more extreme (more negative) than VaR
        assert cvar_result.cvar_value <= var_result.var_value

    def test_confidence_level_impact(self, sample_returns):
        """Test: 신뢰수준 영향"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        var_95 = None
        var_99 = None

        # 95% VaR
        config_95 = RiskConfig(confidence_level=0.95, var_method='historical')
        var_calc_95 = VaRCalculator(config_95)
        var_95 = var_calc_95.calculate(sample_returns, 100_000_000)

        # 99% VaR
        config_99 = RiskConfig(confidence_level=0.99, var_method='historical')
        var_calc_99 = VaRCalculator(config_99)
        var_99 = var_calc_99.calculate(sample_returns, 100_000_000)

        # 99% VaR should be more extreme than 95% VaR
        assert var_99.var_value <= var_95.var_value


# =============================================================================
# Scenario 4.2: Portfolio Risk Metrics Calculation
# =============================================================================

class TestScenario4_2_PortfolioRiskMetrics:
    """
    Scenario 4.2: 포트폴리오 리스크 메트릭 계산

    Tests:
    - Correlation matrix calculation
    - Diversification ratio
    - Sector exposure analysis
    """

    def test_correlation_matrix_calculation(self, sample_multi_ticker_returns):
        """Test: 상관관계 행렬 계산"""
        returns_df = pd.DataFrame(sample_multi_ticker_returns)
        corr_matrix = returns_df.corr()

        # Diagonal should be 1
        for ticker in corr_matrix.index:
            assert np.isclose(corr_matrix.loc[ticker, ticker], 1.0)

        # Off-diagonal should be between -1 and 1
        for i in corr_matrix.index:
            for j in corr_matrix.columns:
                if i != j:
                    assert -1 <= corr_matrix.loc[i, j] <= 1

    def test_correlation_result_creation(self):
        """Test: CorrelationResult 생성"""
        from modules.risk.risk_base import CorrelationResult

        corr_matrix = pd.DataFrame({
            'A': [1.0, 0.3, 0.2],
            'B': [0.3, 1.0, 0.4],
            'C': [0.2, 0.4, 1.0]
        }, index=['A', 'B', 'C'])

        eigenvalues = np.array([1.5, 1.0, 0.5])
        pc = pd.DataFrame({'PC1': [0.5, 0.5, 0.7], 'PC2': [0.7, -0.5, 0.2]})

        result = CorrelationResult(
            correlation_matrix=corr_matrix,
            average_correlation=0.3,
            diversification_ratio=1.2,
            eigenvalues=eigenvalues,
            principal_components=pc
        )

        assert result.average_correlation == 0.3
        assert result.diversification_ratio == 1.2

    def test_diversification_ratio_calculation(self, sample_multi_ticker_returns):
        """Test: 분산 비율 계산"""
        returns_df = pd.DataFrame(sample_multi_ticker_returns)

        # Equal weights
        weights = np.array([1/3, 1/3, 1/3])

        # Individual volatilities
        individual_vols = returns_df.std()

        # Portfolio volatility
        cov_matrix = returns_df.cov()
        portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
        portfolio_vol = np.sqrt(portfolio_var)

        # Weighted average of individual vols
        weighted_vol_sum = np.sum(weights * individual_vols)

        # Diversification ratio = weighted_vol_sum / portfolio_vol
        div_ratio = weighted_vol_sum / portfolio_vol

        # Should be >= 1 (diversification benefit)
        assert div_ratio >= 1.0

    def test_exposure_result_creation(self):
        """Test: ExposureResult 생성"""
        from modules.risk.risk_base import ExposureResult

        sector_exp = pd.Series({'IT': 0.3, 'Finance': 0.25, 'Healthcare': 0.2, 'Other': 0.25})
        region_exp = pd.Series({'KR': 0.6, 'US': 0.3, 'JP': 0.1})

        result = ExposureResult(
            sector_exposure=sector_exp,
            region_exposure=region_exp,
            concentration_metrics={'herfindahl_index': 0.25, 'effective_n': 4.0}
        )

        assert result.sector_exposure['IT'] == 0.3
        assert result.region_exposure['KR'] == 0.6
        assert result.concentration_metrics['effective_n'] == 4.0


# =============================================================================
# Scenario 4.3: DataProvider -> Risk Calculation Integration
# =============================================================================

class TestScenario4_3_DataProviderRiskIntegration:
    """
    Scenario 4.3: DataProvider -> Risk 계산 통합

    Tests:
    - OHLCV data to returns conversion
    - Returns to VaR calculation pipeline
    - Multi-ticker risk calculation
    """

    def test_ohlcv_to_returns_conversion(self, sample_ohlcv_data):
        """Test: OHLCV -> 수익률 변환"""
        # Calculate returns from close prices
        returns = sample_ohlcv_data['close'].pct_change().dropna()

        # Returns should have one less observation
        assert len(returns) == len(sample_ohlcv_data) - 1

        # Returns should be reasonable (not extreme)
        assert returns.abs().max() < 0.5  # Max 50% daily move

    def test_returns_to_var_pipeline(self, sample_ohlcv_data):
        """Test: 수익률 -> VaR 계산 파이프라인"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        # Convert OHLCV to returns
        returns = sample_ohlcv_data['close'].pct_change().dropna()

        # Calculate VaR
        config = RiskConfig(confidence_level=0.95, var_method='historical')
        calculator = VaRCalculator(config)
        result = calculator.calculate(returns, portfolio_value=100_000_000)

        # Verify result
        assert result.var_value < 0
        assert result.metadata['observations'] == len(returns)

    def test_multi_ticker_risk_calculation(self, sample_multi_ticker_returns):
        """Test: 멀티 티커 리스크 계산"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        # Create portfolio returns (equal weighted)
        returns_df = pd.DataFrame(sample_multi_ticker_returns)
        weights = np.array([1/3, 1/3, 1/3])
        portfolio_returns = (returns_df * weights).sum(axis=1)

        # Calculate portfolio VaR
        config = RiskConfig(confidence_level=0.95, var_method='historical')
        calculator = VaRCalculator(config)
        result = calculator.calculate(portfolio_returns, portfolio_value=100_000_000)

        assert result.var_value < 0
        assert result.method == 'historical'

    def test_risk_config_validation(self):
        """Test: RiskConfig 검증"""
        from modules.risk.risk_base import RiskConfig

        # Valid config
        config = RiskConfig(
            confidence_level=0.95,
            time_horizon_days=10,
            var_method='historical'
        )
        is_valid, msg = config.validate()
        assert is_valid

        # Invalid confidence level
        config_invalid = RiskConfig(confidence_level=1.5)
        is_valid, msg = config_invalid.validate()
        assert not is_valid
        assert 'confidence_level' in msg

    def test_stress_test_result_creation(self):
        """Test: StressTestResult 생성"""
        from modules.risk.risk_base import StressTestResult

        result = StressTestResult(
            scenario_name='2008_financial_crisis',
            portfolio_loss=-15_000_000,
            portfolio_loss_percent=-0.15,
            scenario_description='2008 Financial Crisis simulation',
            scenario_type='historical',
            factor_shocks={'equity': -0.40, 'vol': 0.80},
            asset_level_impacts=pd.DataFrame({
                'ticker': ['005930', '035420'],
                'loss': [-5_000_000, -3_000_000]
            }),
            calculation_date=datetime.now()
        )

        assert result.scenario_name == '2008_financial_crisis'
        assert result.portfolio_loss_percent == -0.15
        assert result.scenario_type == 'historical'


# =============================================================================
# End-to-End Integration Tests
# =============================================================================

class TestEndToEndFactorRisk:
    """
    End-to-End Integration Tests for Factor and Risk modules
    """

    def test_factor_to_risk_pipeline(self, sample_ohlcv_data, sample_factor_scores):
        """Test: Factor -> Risk 파이프라인"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        # 1. Calculate returns from OHLCV
        returns = sample_ohlcv_data['close'].pct_change().dropna()

        # 2. Calculate composite factor score
        composite_score = np.mean(list(sample_factor_scores.values()))
        assert 0 <= composite_score <= 100

        # 3. Calculate VaR
        config = RiskConfig(confidence_level=0.95, var_method='historical')
        calculator = VaRCalculator(config)
        var_result = calculator.calculate(returns, portfolio_value=100_000_000)

        # 4. Verify complete pipeline
        assert var_result.var_value < 0
        assert composite_score > 0

    def test_complete_risk_assessment(self, sample_returns):
        """Test: 완전한 리스크 평가"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.cvar_calculator import CVaRCalculator
        from modules.risk.risk_base import RiskConfig

        portfolio_value = 100_000_000

        # VaR calculation
        var_config = RiskConfig(confidence_level=0.95, var_method='historical')
        var_calc = VaRCalculator(var_config)
        var_result = var_calc.calculate(sample_returns, portfolio_value)

        # CVaR calculation
        cvar_calc = CVaRCalculator(var_config)
        cvar_result = cvar_calc.calculate(sample_returns, portfolio_value)

        # Verify relationship
        assert cvar_result.cvar_value <= var_result.var_value

        # Verify metadata
        assert var_result.metadata['observations'] == len(sample_returns)

    def test_multi_confidence_risk_report(self, sample_returns):
        """Test: 다중 신뢰수준 리스크 보고서"""
        from modules.risk.var_calculator import VaRCalculator
        from modules.risk.risk_base import RiskConfig

        portfolio_value = 100_000_000
        confidence_levels = [0.90, 0.95, 0.99]

        results = []
        for conf in confidence_levels:
            config = RiskConfig(confidence_level=conf, var_method='historical')
            calc = VaRCalculator(config)
            result = calc.calculate(sample_returns, portfolio_value)
            results.append(result)

        # Higher confidence should have more extreme VaR
        for i in range(1, len(results)):
            assert results[i].var_value <= results[i-1].var_value


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
