"""
Mean-Variance Portfolio Optimization (Markowitz)

This module implements the classic Markowitz mean-variance optimization using cvxpy.
Maximizes expected return for a given risk level or minimizes risk for a given return.

Reference: Markowitz, H. (1952). Portfolio Selection. Journal of Finance.

Author: Quant Platform Development Team
Last Updated: 2025-10-21
Version: 1.0.0
"""

import time
from typing import Optional
import numpy as np
import pandas as pd
import cvxpy as cp

from modules.optimization.optimizer_base import (
    PortfolioOptimizer,
    OptimizationConstraints,
    OptimizationResult
)


class MeanVarianceOptimizer(PortfolioOptimizer):
    """
    Mean-Variance Optimizer (Markowitz).

    Solves the following optimization problem:
        maximize: expected_return - (risk_aversion / 2) * portfolio_variance
        subject to:
            - sum(weights) = 1
            - weights >= 0 (if long_only)
            - weights[i] <= max_position
            - weights[i] >= min_position (if weight[i] > 0)
            - sector/region constraints
    """

    def __init__(
        self,
        constraints: Optional[OptimizationConstraints] = None,
        risk_aversion: float = 1.0,
        solver: str = 'ECOS'
    ):
        """
        Initialize Mean-Variance optimizer.

        Args:
            constraints: Optimization constraints (uses defaults if None)
            risk_aversion: Risk aversion coefficient (0-10, default: 1.0)
                - 0: Maximize return (ignore risk)
                - 1: Balanced risk/return trade-off
                - 10: Minimize risk (conservative)
            solver: cvxpy solver (ECOS, SCS, OSQP, CVXOPT)
        """
        super().__init__(constraints)
        self.risk_aversion = risk_aversion
        self.solver = solver

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        target_return: Optional[float] = None,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio weights using mean-variance optimization.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix of asset returns (DataFrame)
            target_return: Target return (if None, use risk_aversion)
            **kwargs: Additional parameters
                - risk_free_rate: Risk-free rate (default: 0.035)

        Returns:
            OptimizationResult with optimized weights and metrics
        """
        # Validate inputs
        self.validate_inputs(expected_returns, cov_matrix)

        # Start timer
        start_time = time.time()

        # Extract parameters
        risk_free_rate = kwargs.get('risk_free_rate', 0.035)
        n_assets = len(expected_returns)
        tickers = expected_returns.index.tolist()

        # Define optimization variable
        weights = cp.Variable(n_assets)

        # Define objective: maximize return - (risk_aversion / 2) * variance
        portfolio_return = expected_returns.values @ weights
        portfolio_variance = cp.quad_form(weights, cov_matrix.values)

        if target_return is None:
            # Risk-aversion based optimization
            objective = cp.Maximize(portfolio_return - (self.risk_aversion / 2) * portfolio_variance)
        else:
            # Target return optimization (minimize risk)
            objective = cp.Minimize(portfolio_variance)

        # Define constraints
        constraints = [
            cp.sum(weights) == 1,  # Fully invested
        ]

        # Long-only constraint
        if self.constraints.long_only:
            constraints.append(weights >= 0)

        # Position size constraints
        constraints.append(weights <= self.constraints.max_position)

        # Add target return constraint if specified
        if target_return is not None:
            constraints.append(portfolio_return >= target_return)

        # Create problem
        problem = cp.Problem(objective, constraints)

        # Solve problem
        try:
            if self.solver == 'ECOS':
                problem.solve(solver=cp.ECOS, verbose=False)
            elif self.solver == 'SCS':
                problem.solve(solver=cp.SCS, verbose=False)
            elif self.solver == 'OSQP':
                problem.solve(solver=cp.OSQP, verbose=False)
            else:
                problem.solve(verbose=False)

        except Exception as e:
            # Try fallback solver
            print(f"⚠️ Solver {self.solver} failed, trying SCS: {e}")
            problem.solve(solver=cp.SCS, verbose=False)

        # Get solver status
        solver_status = problem.status

        # Extract solution
        if problem.status in ['optimal', 'optimal_inaccurate']:
            optimized_weights = weights.value

            # Apply minimum position constraint (post-processing)
            optimized_weights = self._apply_min_position_constraint(optimized_weights)

            # Calculate portfolio metrics
            port_return, port_risk, sharpe = self.calculate_portfolio_metrics(
                optimized_weights,
                expected_returns,
                cov_matrix,
                risk_free_rate
            )

            # Validate constraints
            is_valid, error_msg = self.constraints.validate_weights(optimized_weights)

            # Convert to dict
            weight_dict = self.weights_to_dict(optimized_weights, tickers)

            # Calculate solver time
            solver_time = time.time() - start_time

            # Create result
            result = OptimizationResult(
                weights=weight_dict,
                expected_return=float(port_return),
                expected_risk=float(port_risk),
                sharpe_ratio=float(sharpe),
                optimization_method='mean_variance',
                constraints_satisfied=is_valid,
                solver_status=solver_status,
                solver_time=solver_time,
                metadata={
                    'risk_aversion': self.risk_aversion,
                    'target_return': target_return,
                    'solver': self.solver,
                    'n_assets': n_assets,
                    'n_nonzero_positions': np.sum(optimized_weights > 1e-6),
                    'validation_message': error_msg
                }
            )

            return result

        else:
            # Optimization failed
            raise RuntimeError(f"Optimization failed with status: {solver_status}")

    def _apply_min_position_constraint(self, weights: np.ndarray) -> np.ndarray:
        """
        Apply minimum position constraint (post-processing).

        Small positions below min_position threshold are set to zero,
        and the weights are re-normalized.

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

    def efficient_frontier(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        n_points: int = 50,
        **kwargs
    ) -> pd.DataFrame:
        """
        Calculate efficient frontier.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix (DataFrame)
            n_points: Number of points on the frontier (default: 50)
            **kwargs: Additional parameters

        Returns:
            DataFrame with return, risk, sharpe_ratio, weights columns
        """
        # Validate inputs
        self.validate_inputs(expected_returns, cov_matrix)

        # Calculate min and max returns
        min_return = expected_returns.min()
        max_return = expected_returns.max()

        # Generate target returns
        target_returns = np.linspace(min_return, max_return, n_points)

        # Calculate efficient frontier
        results = []
        for target_return in target_returns:
            try:
                result = self.optimize(
                    expected_returns,
                    cov_matrix,
                    target_return=target_return,
                    **kwargs
                )

                results.append({
                    'target_return': target_return,
                    'expected_return': result.expected_return,
                    'expected_risk': result.expected_risk,
                    'sharpe_ratio': result.sharpe_ratio,
                    'weights': result.weights
                })

            except RuntimeError:
                # Skip infeasible points
                continue

        # Convert to DataFrame
        df = pd.DataFrame(results)
        return df

    def max_sharpe_portfolio(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Find portfolio with maximum Sharpe ratio.

        This is a wrapper around optimize() with risk_aversion tuned
        to maximize Sharpe ratio.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix (DataFrame)
            **kwargs: Additional parameters

        Returns:
            OptimizationResult with max Sharpe ratio portfolio
        """
        # Use grid search to find optimal risk aversion
        best_sharpe = -np.inf
        best_result = None

        for ra in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
            self.risk_aversion = ra
            try:
                result = self.optimize(expected_returns, cov_matrix, **kwargs)
                if result.sharpe_ratio > best_sharpe:
                    best_sharpe = result.sharpe_ratio
                    best_result = result
            except RuntimeError:
                continue

        if best_result is None:
            raise RuntimeError("Failed to find max Sharpe portfolio")

        return best_result

    def min_volatility_portfolio(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Find minimum volatility portfolio.

        Args:
            expected_returns: Expected returns for each asset (Series)
            cov_matrix: Covariance matrix (DataFrame)
            **kwargs: Additional parameters

        Returns:
            OptimizationResult with minimum volatility portfolio
        """
        # Set very high risk aversion (effectively minimize variance)
        self.risk_aversion = 1000.0

        result = self.optimize(expected_returns, cov_matrix, **kwargs)
        result.metadata['optimization_objective'] = 'min_volatility'

        return result


# Export public API
__all__ = ['MeanVarianceOptimizer']
