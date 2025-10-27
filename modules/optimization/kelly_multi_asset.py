"""
Kelly Criterion Multi-Asset Portfolio Optimization

This module extends the traditional single-asset Kelly Criterion to multi-asset portfolios
by incorporating asset correlations and portfolio-level risk management.

Reference: Thorp, E. O. (1969). Optimal Gambling Systems for Favorable Games.
           Rotando, L. M. & Thorp, E. O. (1992). The Kelly Criterion and the Stock Market.

Author: Quant Platform Development Team
Last Updated: 2025-10-21
Version: 1.0.0
"""

import time
from typing import Optional
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from modules.optimization.optimizer_base import (
    PortfolioOptimizer,
    OptimizationConstraints,
    OptimizationResult
)


class KellyMultiAssetOptimizer(PortfolioOptimizer):
    """
    Kelly Criterion Multi-Asset Optimizer.

    The traditional Kelly Criterion maximizes geometric growth rate for a single asset:
        f* = (p × b - (1-p)) / b

    For multi-asset portfolios, we must account for correlations:
        Maximize: E[log(1 + w' × r)]
        Where:
            w = portfolio weights
            r = asset returns (correlated random variables)

    This is implemented using numerical optimization (scipy.minimize) with
    logarithmic utility and correlation-adjusted risk.
    """

    def __init__(
        self,
        constraints: Optional[OptimizationConstraints] = None,
        fractional_kelly: float = 0.5,
        use_correlation: bool = True
    ):
        """
        Initialize Kelly multi-asset optimizer.

        Args:
            constraints: Optimization constraints (uses defaults if None)
            fractional_kelly: Fraction of Kelly to use (0.0-1.0, default: 0.5)
                - 1.0: Full Kelly (maximum growth, high volatility)
                - 0.5: Half Kelly (balanced, more stable)
                - 0.25: Quarter Kelly (conservative)
            use_correlation: Account for asset correlations (default: True)
        """
        super().__init__(constraints)
        self.fractional_kelly = fractional_kelly
        self.use_correlation = use_correlation

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio weights using Kelly Criterion for multi-asset.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix of asset returns (DataFrame)
            **kwargs: Additional parameters
                - risk_free_rate: Risk-free rate (default: 0.035)

        Returns:
            OptimizationResult with Kelly-optimized weights
        """
        # Validate inputs
        self.validate_inputs(expected_returns, cov_matrix)

        # Start timer
        start_time = time.time()

        # Extract parameters
        risk_free_rate = kwargs.get('risk_free_rate', 0.035)
        n_assets = len(expected_returns)
        tickers = expected_returns.index.tolist()

        # Convert to numpy
        mu = expected_returns.values  # Expected returns
        Sigma = cov_matrix.values     # Covariance matrix

        # Define objective function: maximize geometric mean return
        # E[log(1 + w' × r)] ≈ w' × mu - 0.5 × w' × Sigma × w
        def objective(weights):
            """
            Kelly objective: maximize expected log return.

            For small returns, log(1 + x) ≈ x - x^2/2
            So: E[log(1 + R_p)] ≈ E[R_p] - 0.5 × Var(R_p)
            """
            portfolio_return = np.dot(weights, mu)
            portfolio_variance = np.dot(weights, np.dot(Sigma, weights))

            # Kelly criterion: maximize log wealth growth
            # Approximation: log(1 + r) ≈ r - 0.5 × r^2
            kelly_objective = portfolio_return - 0.5 * portfolio_variance

            # Return negative (since we minimize)
            return -kelly_objective

        # Initial guess: equal weights
        x0 = np.ones(n_assets) / n_assets

        # Define constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum to 1
        ]

        # Define bounds
        if self.constraints.long_only:
            bounds = tuple((0, self.constraints.max_position) for _ in range(n_assets))
        else:
            bounds = tuple((-self.constraints.max_position, self.constraints.max_position) for _ in range(n_assets))

        # Solve optimization
        result = minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints_list,
            options={'maxiter': 1000, 'disp': False}
        )

        # Extract solution
        if result.success:
            optimized_weights = result.x

            # Apply fractional Kelly adjustment
            if self.fractional_kelly < 1.0:
                # Fractional Kelly: f_fractional = fractional_kelly × f_full + (1 - fractional_kelly) × cash
                cash_weight = 1.0 - self.fractional_kelly
                optimized_weights = optimized_weights * self.fractional_kelly

                # Ensure sum to (1 - cash_weight)
                optimized_weights = optimized_weights / optimized_weights.sum() * (1.0 - cash_weight)

            # Apply minimum position constraint
            optimized_weights = self._apply_min_position_constraint(optimized_weights)

            # Calculate portfolio metrics
            port_return, port_risk, sharpe = self.calculate_portfolio_metrics(
                optimized_weights,
                expected_returns,
                cov_matrix,
                risk_free_rate
            )

            # Calculate geometric mean return
            geometric_mean = port_return - 0.5 * (port_risk ** 2)

            # Validate constraints
            is_valid, error_msg = self.constraints.validate_weights(optimized_weights)

            # Convert to dict
            weight_dict = self.weights_to_dict(optimized_weights, tickers)

            # Calculate solver time
            solver_time = time.time() - start_time

            # Create result
            opt_result = OptimizationResult(
                weights=weight_dict,
                expected_return=float(port_return),
                expected_risk=float(port_risk),
                sharpe_ratio=float(sharpe),
                optimization_method='kelly_multi_asset',
                constraints_satisfied=is_valid,
                solver_status='optimal' if result.success else 'failed',
                solver_time=solver_time,
                metadata={
                    'fractional_kelly': self.fractional_kelly,
                    'use_correlation': self.use_correlation,
                    'geometric_mean_return': float(geometric_mean),
                    'cash_allocation': float(1.0 - optimized_weights.sum()) if self.fractional_kelly < 1.0 else 0.0,
                    'n_assets': n_assets,
                    'n_nonzero_positions': np.sum(optimized_weights > 1e-6),
                    'validation_message': error_msg
                }
            )

            return opt_result

        else:
            raise RuntimeError(f"Kelly optimization failed: {result.message}")

    def _apply_min_position_constraint(self, weights: np.ndarray) -> np.ndarray:
        """
        Apply minimum position constraint (post-processing).

        Args:
            weights: Original weights

        Returns:
            Adjusted weights
        """
        # Set tiny positions to zero
        weights[weights < 1e-6] = 0

        # Set positions below min_position to zero
        small_positions = (weights > 0) & (weights < self.constraints.min_position)
        weights[small_positions] = 0

        # Re-normalize
        if weights.sum() > 0:
            weights = weights / weights.sum()

        return weights

    def calculate_single_asset_kelly(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate single-asset Kelly percentage.

        Traditional Kelly formula: f* = (p × b - (1-p)) / b

        Args:
            win_rate: Probability of winning (0.0-1.0)
            avg_win: Average win size (e.g., 0.25 for 25% gain)
            avg_loss: Average loss size (e.g., 0.08 for 8% loss)

        Returns:
            Kelly fraction (0.0-1.0, can be >1.0 for extremely favorable bets)

        Example:
            >>> # 65% win rate, 25% avg win, 8% avg loss
            >>> kelly_pct = self.calculate_single_asset_kelly(0.65, 0.25, 0.08)
            >>> print(kelly_pct)  # 0.543 (54.3% of capital)
        """
        # Kelly formula: f = (p × b - (1-p)) / b
        # Where b = avg_win / avg_loss
        b = avg_win / avg_loss
        p = win_rate

        kelly_fraction = (p * b - (1 - p)) / b

        # Ensure non-negative
        kelly_fraction = max(0.0, kelly_fraction)

        return kelly_fraction

    def optimize_with_win_rates(
        self,
        win_rates: pd.Series,
        avg_wins: pd.Series,
        avg_losses: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize using win rates and average win/loss ratios.

        This is an alternative interface for users who have historical
        win/loss statistics instead of expected returns.

        Args:
            win_rates: Win rate for each asset (0.0-1.0)
            avg_wins: Average win size for each asset (e.g., 0.25 for 25%)
            avg_losses: Average loss size for each asset (e.g., 0.08 for 8%)
            cov_matrix: Covariance matrix of asset returns
            **kwargs: Additional parameters

        Returns:
            OptimizationResult with Kelly-optimized weights
        """
        # Convert win rates to expected returns
        expected_returns = pd.Series(
            [
                win_rate * avg_win - (1 - win_rate) * avg_loss
                for win_rate, avg_win, avg_loss in zip(win_rates, avg_wins, avg_losses)
            ],
            index=win_rates.index
        )

        # Use standard optimize method
        return self.optimize(expected_returns, cov_matrix, **kwargs)


# Export public API
__all__ = ['KellyMultiAssetOptimizer']
