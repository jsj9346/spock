"""
Portfolio Optimization Base Classes

This module provides abstract base classes and data structures for portfolio optimization.
All optimizer implementations (Mean-Variance, Risk Parity, Black-Litterman, Kelly) inherit
from these base classes.

Author: Quant Platform Development Team
Last Updated: 2025-10-21
Version: 1.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime


@dataclass
class OptimizationConstraints:
    """
    Portfolio optimization constraints configuration.

    Attributes:
        min_position: Minimum position size (default: 1%)
        max_position: Maximum position size (default: 15%)
        max_sector_exposure: Maximum sector exposure (default: 40%)
        max_turnover: Maximum turnover per rebalancing (default: 20%)
        min_cash: Minimum cash reserve (default: 10%)
        max_cash: Maximum cash reserve (default: 30%)
        long_only: Long-only constraint (default: True)
        max_leverage: Maximum leverage (1.0 = no leverage)
        region_limits: Dict of region-specific limits
        sector_limits: Dict of sector-specific limits
    """
    min_position: float = 0.01
    max_position: float = 0.15
    max_sector_exposure: float = 0.40
    max_turnover: float = 0.20
    min_cash: float = 0.10
    max_cash: float = 0.30
    long_only: bool = True
    max_leverage: float = 1.0
    region_limits: Optional[Dict[str, float]] = None
    sector_limits: Optional[Dict[str, float]] = None

    def __post_init__(self):
        """Initialize default region and sector limits if not provided."""
        if self.region_limits is None:
            self.region_limits = {
                'KR': 0.50,
                'US': 0.50,
                'CN': 0.20,
                'JP': 0.20,
                'HK': 0.20,
                'VN': 0.10
            }

        if self.sector_limits is None:
            self.sector_limits = {
                'Technology': 0.40,
                'Financials': 0.30,
                'Healthcare': 0.30,
                'Consumer_Discretionary': 0.25,
                'Consumer_Staples': 0.25,
                'Industrials': 0.25,
                'Energy': 0.20,
                'Materials': 0.20,
                'Utilities': 0.15,
                'Real_Estate': 0.15,
                'Communication_Services': 0.25
            }

    def validate_weights(self, weights: np.ndarray) -> Tuple[bool, str]:
        """
        Validate portfolio weights against constraints.

        Args:
            weights: Portfolio weights (numpy array)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check weight sum
        if not np.isclose(weights.sum(), 1.0, atol=0.01):
            return False, f"Weights sum to {weights.sum():.4f}, expected 1.0"

        # Check long-only constraint
        if self.long_only and np.any(weights < 0):
            return False, "Negative weights not allowed (long_only=True)"

        # Check position limits
        if np.any(weights > self.max_position):
            max_weight = weights.max()
            return False, f"Max weight {max_weight:.4f} exceeds limit {self.max_position}"

        if np.any((weights > 0) & (weights < self.min_position)):
            min_nonzero = weights[weights > 0].min()
            return False, f"Min weight {min_nonzero:.4f} below limit {self.min_position}"

        return True, "All constraints satisfied"


@dataclass
class OptimizationResult:
    """
    Portfolio optimization result container.

    Attributes:
        weights: Optimized portfolio weights (dict: ticker -> weight)
        expected_return: Expected annual return
        expected_risk: Expected annual volatility
        sharpe_ratio: Sharpe ratio (return / risk)
        optimization_method: Method used (mean_variance, risk_parity, etc.)
        constraints_satisfied: Whether all constraints were satisfied
        solver_status: Solver status (optimal, infeasible, etc.)
        solver_time: Optimization runtime in seconds
        metadata: Additional metadata (dict)
    """
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    optimization_method: str
    constraints_satisfied: bool
    solver_status: str
    solver_time: float
    metadata: Optional[Dict] = None

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert weights to DataFrame for analysis.

        Returns:
            DataFrame with ticker, weight, region, sector columns
        """
        df = pd.DataFrame([
            {'ticker': ticker, 'weight': weight}
            for ticker, weight in self.weights.items()
            if weight > 0.0001  # Filter out tiny positions
        ])
        df = df.sort_values('weight', ascending=False)
        return df

    def get_sector_exposure(self, ticker_metadata: Dict[str, Dict]) -> pd.Series:
        """
        Calculate sector exposure from portfolio weights.

        Args:
            ticker_metadata: Dict mapping ticker to metadata (sector, region)

        Returns:
            Series of sector exposures
        """
        sector_weights = {}
        for ticker, weight in self.weights.items():
            if weight > 0 and ticker in ticker_metadata:
                sector = ticker_metadata[ticker].get('sector', 'Unknown')
                sector_weights[sector] = sector_weights.get(sector, 0) + weight

        return pd.Series(sector_weights).sort_values(ascending=False)

    def get_region_exposure(self, ticker_metadata: Dict[str, Dict]) -> pd.Series:
        """
        Calculate region exposure from portfolio weights.

        Args:
            ticker_metadata: Dict mapping ticker to metadata (sector, region)

        Returns:
            Series of region exposures
        """
        region_weights = {}
        for ticker, weight in self.weights.items():
            if weight > 0 and ticker in ticker_metadata:
                region = ticker_metadata[ticker].get('region', 'Unknown')
                region_weights[region] = region_weights.get(region, 0) + weight

        return pd.Series(region_weights).sort_values(ascending=False)


class PortfolioOptimizer(ABC):
    """
    Abstract base class for portfolio optimizers.

    All optimizer implementations must inherit from this class and implement
    the optimize() method.
    """

    def __init__(self, constraints: Optional[OptimizationConstraints] = None):
        """
        Initialize optimizer with constraints.

        Args:
            constraints: OptimizationConstraints object (uses defaults if None)
        """
        self.constraints = constraints or OptimizationConstraints()

    @abstractmethod
    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio weights.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix of asset returns (DataFrame)
            **kwargs: Additional optimizer-specific parameters

        Returns:
            OptimizationResult with optimized weights and metrics
        """
        pass

    def validate_inputs(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame
    ) -> None:
        """
        Validate input data for optimization.

        Args:
            expected_returns: Expected returns series
            cov_matrix: Covariance matrix

        Raises:
            ValueError: If inputs are invalid
        """
        # Check expected returns
        if expected_returns.isna().any():
            raise ValueError("Expected returns contain NaN values")

        if len(expected_returns) == 0:
            raise ValueError("Expected returns is empty")

        # Check covariance matrix
        if cov_matrix.isna().any().any():
            raise ValueError("Covariance matrix contains NaN values")

        if not np.allclose(cov_matrix, cov_matrix.T):
            raise ValueError("Covariance matrix is not symmetric")

        # Check positive semi-definite
        eigenvalues = np.linalg.eigvalsh(cov_matrix)
        if np.any(eigenvalues < -1e-8):
            raise ValueError(f"Covariance matrix is not positive semi-definite (min eigenvalue: {eigenvalues.min():.2e})")

        # Check index alignment
        if not expected_returns.index.equals(cov_matrix.index):
            raise ValueError("Expected returns and covariance matrix indices do not match")

    def calculate_portfolio_metrics(
        self,
        weights: np.ndarray,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_free_rate: float = 0.035
    ) -> Tuple[float, float, float]:
        """
        Calculate portfolio return, risk, and Sharpe ratio.

        Args:
            weights: Portfolio weights (numpy array)
            expected_returns: Expected returns (Series)
            cov_matrix: Covariance matrix (DataFrame)
            risk_free_rate: Risk-free rate (default: 3.5%)

        Returns:
            Tuple of (expected_return, expected_risk, sharpe_ratio)
        """
        # Calculate expected return
        portfolio_return = np.dot(weights, expected_returns.values)

        # Calculate portfolio variance and risk
        portfolio_variance = np.dot(weights, np.dot(cov_matrix.values, weights))
        portfolio_risk = np.sqrt(portfolio_variance)

        # Calculate Sharpe ratio
        if portfolio_risk > 0:
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_risk
        else:
            sharpe_ratio = 0.0

        return portfolio_return, portfolio_risk, sharpe_ratio

    def weights_to_dict(
        self,
        weights: np.ndarray,
        tickers: List[str]
    ) -> Dict[str, float]:
        """
        Convert numpy array of weights to dict.

        Args:
            weights: Numpy array of weights
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker to weight
        """
        return {ticker: float(weight) for ticker, weight in zip(tickers, weights)}


class TransactionCostModel:
    """
    Transaction cost model for portfolio rebalancing.

    Calculates commission, slippage, and market impact costs.
    """

    def __init__(
        self,
        commission_rates: Optional[Dict[str, float]] = None,
        slippage_bps: float = 5.0,
        market_impact_coefficient: float = 0.1
    ):
        """
        Initialize transaction cost model.

        Args:
            commission_rates: Dict of region-specific commission rates (default: from config)
            slippage_bps: Slippage in basis points (default: 5 bps)
            market_impact_coefficient: Market impact coefficient (default: 0.1)
        """
        if commission_rates is None:
            self.commission_rates = {
                'KR': 0.00015,  # 0.015%
                'US': 0.00050,  # 0.050%
                'CN': 0.00100,  # 0.100%
                'JP': 0.00100,  # 0.100%
                'HK': 0.00100,  # 0.100%
                'VN': 0.00150   # 0.150%
            }
        else:
            self.commission_rates = commission_rates

        self.slippage_bps = slippage_bps
        self.market_impact_coefficient = market_impact_coefficient

    def calculate_cost(
        self,
        trade_value: float,
        region: str,
        volume_pct: float = 0.01
    ) -> float:
        """
        Calculate total transaction cost.

        Args:
            trade_value: Absolute value of trade (dollars)
            region: Region code (KR, US, CN, etc.)
            volume_pct: Trade size as % of daily volume (default: 1%)

        Returns:
            Total transaction cost (dollars)
        """
        # Commission cost
        commission_rate = self.commission_rates.get(region, 0.001)
        commission = trade_value * commission_rate

        # Slippage cost
        slippage = trade_value * (self.slippage_bps / 10000)

        # Market impact cost (increases with trade size)
        market_impact = trade_value * self.market_impact_coefficient * np.sqrt(volume_pct)

        return commission + slippage + market_impact

    def calculate_turnover_cost(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        ticker_metadata: Dict[str, Dict],
        portfolio_value: float
    ) -> float:
        """
        Calculate total cost of rebalancing from current to target weights.

        Args:
            current_weights: Current portfolio weights
            target_weights: Target portfolio weights
            ticker_metadata: Ticker metadata (region, volume)
            portfolio_value: Total portfolio value (dollars)

        Returns:
            Total turnover cost (dollars)
        """
        total_cost = 0.0

        # Get all tickers
        all_tickers = set(current_weights.keys()) | set(target_weights.keys())

        for ticker in all_tickers:
            current_w = current_weights.get(ticker, 0.0)
            target_w = target_weights.get(ticker, 0.0)

            # Calculate trade value
            trade_value = abs(target_w - current_w) * portfolio_value

            if trade_value > 0 and ticker in ticker_metadata:
                region = ticker_metadata[ticker].get('region', 'US')
                volume_pct = 0.01  # Assume 1% of daily volume

                cost = self.calculate_cost(trade_value, region, volume_pct)
                total_cost += cost

        return total_cost


# Export public API
__all__ = [
    'OptimizationConstraints',
    'OptimizationResult',
    'PortfolioOptimizer',
    'TransactionCostModel'
]
