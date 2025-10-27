"""
Risk Calculator Base Classes and Data Structures

This module provides abstract base classes and data structures for all risk calculators.
All risk calculators extend RiskCalculator and use standardized result classes.

NO database dependencies - pure calculation logic using NumPy/pandas.

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - Track 5 Implementation
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime


@dataclass
class RiskConfig:
    """
    Risk calculation configuration

    Attributes:
        confidence_level: VaR/CVaR confidence level (0.95 or 0.99)
        time_horizon_days: Risk horizon in days (1, 10, 20)
        var_method: VaR calculation method ('historical', 'parametric', 'monte_carlo')
        monte_carlo_simulations: Number of Monte Carlo simulations
        historical_lookback_days: Historical data window (default 252 = 1 year)
        stress_test_scenarios: List of stress test scenario names
        correlation_window_days: Rolling correlation window
        exponential_weighting: Use exponentially weighted returns (RiskMetrics)
        lambda_decay: Decay factor for exponential weighting (RiskMetrics standard: 0.94)
    """
    confidence_level: float = 0.95
    time_horizon_days: int = 10
    var_method: str = 'historical'
    monte_carlo_simulations: int = 10000
    historical_lookback_days: int = 252
    stress_test_scenarios: List[str] = field(default_factory=lambda: [
        '2008_financial_crisis',
        '2020_covid_crash',
        '2022_bear_market'
    ])
    correlation_window_days: int = 60
    exponential_weighting: bool = False
    lambda_decay: float = 0.94

    def validate(self) -> Tuple[bool, str]:
        """
        Validate configuration parameters

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not 0.5 <= self.confidence_level < 1.0:
            return False, f"confidence_level must be 0.5-1.0, got {self.confidence_level}"

        if self.time_horizon_days < 1:
            return False, f"time_horizon_days must be >= 1, got {self.time_horizon_days}"

        if self.var_method not in ['historical', 'parametric', 'monte_carlo']:
            return False, f"Invalid var_method: {self.var_method}"

        if self.monte_carlo_simulations < 1000:
            return False, f"monte_carlo_simulations should be >= 1000, got {self.monte_carlo_simulations}"

        if self.historical_lookback_days < 30:
            return False, f"historical_lookback_days should be >= 30, got {self.historical_lookback_days}"

        if self.correlation_window_days < 20:
            return False, f"correlation_window_days should be >= 20, got {self.correlation_window_days}"

        if not 0.5 < self.lambda_decay < 1.0:
            return False, f"lambda_decay must be 0.5-1.0, got {self.lambda_decay}"

        return True, "Configuration valid"

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary for serialization"""
        return {
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon_days,
            'var_method': self.var_method,
            'monte_carlo_simulations': self.monte_carlo_simulations,
            'historical_lookback_days': self.historical_lookback_days,
            'stress_test_scenarios': self.stress_test_scenarios,
            'correlation_window_days': self.correlation_window_days,
            'exponential_weighting': self.exponential_weighting,
            'lambda_decay': self.lambda_decay
        }


@dataclass
class VaRResult:
    """
    Value at Risk calculation result

    Attributes:
        var_value: VaR in portfolio currency (e.g., -5,000,000 KRW)
        var_percent: VaR as % of portfolio value (e.g., -0.05 = -5%)
        confidence_level: Confidence level used (0.95 or 0.99)
        time_horizon_days: Time horizon in days
        method: Calculation method ('historical', 'parametric', 'monte_carlo')
        portfolio_value: Current portfolio value
        calculation_date: Timestamp of calculation
        metadata: Additional calculation metadata
    """
    var_value: float
    var_percent: float
    confidence_level: float
    time_horizon_days: int
    method: str
    portfolio_value: float
    calculation_date: datetime
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        return {
            'var_value': self.var_value,
            'var_percent': self.var_percent,
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon_days,
            'method': self.method,
            'portfolio_value': self.portfolio_value,
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

    def __str__(self) -> str:
        """Human-readable string representation"""
        return (
            f"VaR({self.confidence_level*100:.0f}%, {self.time_horizon_days}d): "
            f"{self.var_value:,.0f} ({self.var_percent:.2%}) "
            f"[{self.method}]"
        )


@dataclass
class CVaRResult:
    """
    Conditional VaR (Expected Shortfall) result

    Attributes:
        cvar_value: CVaR in portfolio currency
        cvar_percent: CVaR as % of portfolio value
        var_threshold: VaR threshold used for CVaR calculation
        confidence_level: Confidence level
        time_horizon_days: Time horizon in days
        method: Calculation method
        tail_observations: Number of observations in tail (beyond VaR)
        portfolio_value: Current portfolio value
        calculation_date: Timestamp of calculation
        metadata: Additional metadata
    """
    cvar_value: float
    cvar_percent: float
    var_threshold: float
    confidence_level: float
    time_horizon_days: int
    method: str
    tail_observations: int
    portfolio_value: float
    calculation_date: datetime
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        return {
            'cvar_value': self.cvar_value,
            'cvar_percent': self.cvar_percent,
            'var_threshold': self.var_threshold,
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon_days,
            'method': self.method,
            'tail_observations': self.tail_observations,
            'portfolio_value': self.portfolio_value,
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

    def __str__(self) -> str:
        """Human-readable string representation"""
        return (
            f"CVaR({self.confidence_level*100:.0f}%, {self.time_horizon_days}d): "
            f"{self.cvar_value:,.0f} ({self.cvar_percent:.2%}) "
            f"[{self.method}, {self.tail_observations} tail obs]"
        )


@dataclass
class StressTestResult:
    """
    Stress test scenario result

    Attributes:
        scenario_name: Scenario identifier
        portfolio_loss: Expected loss in currency
        portfolio_loss_percent: Expected loss as %
        scenario_description: Human-readable description
        scenario_type: 'historical' or 'hypothetical'
        factor_shocks: Dict of factor-level shocks
        asset_level_impacts: DataFrame with per-asset impacts
        calculation_date: Timestamp of calculation
        metadata: Additional metadata
    """
    scenario_name: str
    portfolio_loss: float
    portfolio_loss_percent: float
    scenario_description: str
    scenario_type: str
    factor_shocks: Dict[str, float]
    asset_level_impacts: pd.DataFrame
    calculation_date: datetime
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        return {
            'scenario_name': self.scenario_name,
            'portfolio_loss': self.portfolio_loss,
            'portfolio_loss_percent': self.portfolio_loss_percent,
            'scenario_description': self.scenario_description,
            'scenario_type': self.scenario_type,
            'factor_shocks': self.factor_shocks,
            'asset_level_impacts': self.asset_level_impacts.to_dict('records'),
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

    def __str__(self) -> str:
        """Human-readable string representation"""
        return (
            f"Stress Test [{self.scenario_name}]: "
            f"{self.portfolio_loss:,.0f} ({self.portfolio_loss_percent:.2%}) "
            f"[{self.scenario_type}]"
        )


@dataclass
class CorrelationResult:
    """
    Correlation analysis result

    Attributes:
        correlation_matrix: Asset correlation matrix
        average_correlation: Portfolio average correlation
        diversification_ratio: Ratio of portfolio vol to weighted sum of vols
        eigenvalues: Eigenvalues of correlation matrix (PCA)
        principal_components: Principal component loadings (DataFrame)
        rolling_correlations: Time-series of rolling correlations (optional)
        calculation_date: Timestamp of calculation
        metadata: Additional metadata
    """
    correlation_matrix: pd.DataFrame
    average_correlation: float
    diversification_ratio: float
    eigenvalues: np.ndarray
    principal_components: pd.DataFrame
    rolling_correlations: Optional[pd.DataFrame] = None
    calculation_date: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        result = {
            'correlation_matrix': self.correlation_matrix.to_dict(),
            'average_correlation': self.average_correlation,
            'diversification_ratio': self.diversification_ratio,
            'eigenvalues': self.eigenvalues.tolist(),
            'principal_components': self.principal_components.to_dict(),
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

        if self.rolling_correlations is not None:
            result['rolling_correlations'] = self.rolling_correlations.to_dict()

        return result

    def __str__(self) -> str:
        """Human-readable string representation"""
        n_assets = len(self.correlation_matrix)
        return (
            f"Correlation Analysis: "
            f"{n_assets} assets, avg_corr={self.average_correlation:.3f}, "
            f"div_ratio={self.diversification_ratio:.3f}"
        )


@dataclass
class ExposureResult:
    """
    Factor/sector exposure result

    Attributes:
        sector_exposure: Exposure by sector (Series)
        region_exposure: Exposure by region (Series)
        factor_exposure: Exposure to risk factors (DataFrame, optional)
        concentration_metrics: Concentration metrics (HHI, Effective N)
        top_exposures: Top 10 exposures (DataFrame)
        calculation_date: Timestamp of calculation
        metadata: Additional metadata
    """
    sector_exposure: pd.Series
    region_exposure: pd.Series
    factor_exposure: Optional[pd.DataFrame] = None
    concentration_metrics: Dict[str, float] = field(default_factory=dict)
    top_exposures: pd.DataFrame = field(default_factory=pd.DataFrame)
    calculation_date: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for serialization"""
        result = {
            'sector_exposure': self.sector_exposure.to_dict(),
            'region_exposure': self.region_exposure.to_dict(),
            'concentration_metrics': self.concentration_metrics,
            'top_exposures': self.top_exposures.to_dict('records'),
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

        if self.factor_exposure is not None:
            result['factor_exposure'] = self.factor_exposure.to_dict()

        return result

    def __str__(self) -> str:
        """Human-readable string representation"""
        n_sectors = len(self.sector_exposure)
        n_regions = len(self.region_exposure)
        hhi = self.concentration_metrics.get('herfindahl_index', 0)
        return (
            f"Exposure Analysis: "
            f"{n_sectors} sectors, {n_regions} regions, HHI={hhi:.4f}"
        )


class RiskCalculator(ABC):
    """
    Abstract base class for all risk calculators

    All risk calculators must extend this class and implement the calculate() method.
    Provides common validation and utility methods.
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        Initialize risk calculator with configuration

        Args:
            config: Risk calculation configuration (uses defaults if None)

        Raises:
            ValueError: If configuration is invalid
        """
        self.config = config or RiskConfig()
        is_valid, msg = self.config.validate()
        if not is_valid:
            raise ValueError(f"Invalid RiskConfig: {msg}")

    @abstractmethod
    def calculate(self, *args, **kwargs):
        """
        Calculate risk metric (implemented by subclasses)

        Returns:
            Risk calculation result (VaRResult, CVaRResult, etc.)
        """
        pass

    def validate_inputs(
        self,
        returns: Optional[pd.Series] = None,
        weights: Optional[pd.Series] = None,
        cov_matrix: Optional[pd.DataFrame] = None
    ) -> None:
        """
        Validate input data for risk calculations

        Args:
            returns: Historical returns series
            weights: Portfolio weights series
            cov_matrix: Covariance matrix

        Raises:
            ValueError: If inputs are invalid
        """
        if returns is not None:
            if returns.isnull().any():
                raise ValueError("Returns contain NaN values")

            if len(returns) < 30:
                raise ValueError(
                    f"Insufficient returns data: {len(returns)} observations "
                    f"(minimum 30 required)"
                )

            if not np.isfinite(returns).all():
                raise ValueError("Returns contain infinite values")

        if weights is not None:
            if weights.isnull().any():
                raise ValueError("Weights contain NaN values")

            if not np.isclose(weights.sum(), 1.0, atol=0.01):
                raise ValueError(
                    f"Weights sum to {weights.sum():.4f}, expected 1.0 "
                    f"(tolerance ±0.01)"
                )

            if (weights < 0).any():
                raise ValueError(
                    "Negative weights detected (long-only portfolio expected)"
                )

            if not np.isfinite(weights).all():
                raise ValueError("Weights contain infinite values")

        if cov_matrix is not None:
            if cov_matrix.isnull().any().any():
                raise ValueError("Covariance matrix contains NaN values")

            if not np.allclose(cov_matrix, cov_matrix.T, atol=1e-8):
                raise ValueError("Covariance matrix is not symmetric")

            eigenvalues = np.linalg.eigvalsh(cov_matrix.values)
            if (eigenvalues < -1e-8).any():
                raise ValueError(
                    "Covariance matrix is not positive semi-definite"
                )

            if not np.isfinite(cov_matrix.values).all():
                raise ValueError("Covariance matrix contains infinite values")

        if weights is not None and cov_matrix is not None:
            if not weights.index.equals(cov_matrix.index):
                raise ValueError(
                    "Weights and covariance matrix indices do not match"
                )

    def _scale_returns_to_horizon(
        self,
        returns: pd.Series,
        horizon_days: Optional[int] = None
    ) -> pd.Series:
        """
        Scale daily returns to multi-day horizon using overlapping periods

        Args:
            returns: Daily returns series
            horizon_days: Time horizon (uses config if None)

        Returns:
            Scaled returns series
        """
        horizon = horizon_days or self.config.time_horizon_days

        if horizon == 1:
            return returns

        scaled_returns = []
        for i in range(len(returns) - horizon + 1):
            period_return = returns.iloc[i:i+horizon].sum()
            scaled_returns.append(period_return)

        return pd.Series(scaled_returns)

    def _calculate_exponential_weights(
        self,
        n: int,
        lambda_decay: Optional[float] = None
    ) -> np.ndarray:
        """
        Calculate exponentially decaying weights (RiskMetrics approach)

        Args:
            n: Number of observations
            lambda_decay: Decay factor (uses config if None)

        Returns:
            Normalized weight array (sums to 1.0)
        """
        lambda_val = lambda_decay or self.config.lambda_decay
        weights = np.array([lambda_val ** i for i in range(n)])
        weights = weights[::-1]  # Reverse so recent observations have higher weight
        weights /= weights.sum()  # Normalize to sum to 1.0
        return weights

    def _weighted_percentile(
        self,
        data: np.ndarray,
        weights: np.ndarray,
        percentile: float
    ) -> float:
        """
        Calculate weighted percentile

        Args:
            data: Data array
            weights: Weight array (must sum to 1.0)
            percentile: Percentile value (0.0 - 1.0)

        Returns:
            Weighted percentile value
        """
        sorted_indices = np.argsort(data)
        sorted_data = data[sorted_indices]
        sorted_weights = weights[sorted_indices]
        cumsum = np.cumsum(sorted_weights)

        # Find index where cumulative weight exceeds percentile
        idx = np.searchsorted(cumsum, percentile)
        idx = min(idx, len(sorted_data) - 1)  # Ensure within bounds

        return sorted_data[idx]
