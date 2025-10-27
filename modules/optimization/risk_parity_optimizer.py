"""
Risk Parity Portfolio Optimization

This module implements Risk Parity (Equal Risk Contribution) portfolio optimization.
Each asset contributes equally to the portfolio's overall risk, providing better
diversification than equal weighting or mean-variance optimization.

Reference: Qian, E. (2005). Risk Parity Portfolios. PanAgora Asset Management.

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


class RiskParityOptimizer(PortfolioOptimizer):
    """
    Risk Parity Optimizer (Equal Risk Contribution).

    Finds portfolio weights where each asset contributes equally to total portfolio risk.
    This is NOT a return-maximizing strategy but rather a pure diversification approach.

    Risk contribution of asset i:
        RC_i = w_i * (Sigma * w)_i

    Objective: Minimize sum of squared differences in risk contributions
    """

    def __init__(
        self,
        constraints: Optional[OptimizationConstraints] = None,
        target_risk: Optional[float] = None
    ):
        """
        Initialize Risk Parity optimizer.

        Args:
            constraints: Optimization constraints (uses defaults if None)
            target_risk: Target portfolio volatility (None = unconstrained)
        """
        super().__init__(constraints)
        self.target_risk = target_risk

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio weights using risk parity.

        Args:
            expected_returns: Expected returns (used for metrics only)
            cov_matrix: Covariance matrix of asset returns (DataFrame)
            **kwargs: Additional parameters
                - risk_free_rate: Risk-free rate (default: 0.035)
                - method: scipy optimization method (default: 'SLSQP')

        Returns:
            OptimizationResult with risk parity weights
        """
        # Validate inputs
        self.validate_inputs(expected_returns, cov_matrix)

        # Start timer
        start_time = time.time()

        # Extract parameters
        risk_free_rate = kwargs.get('risk_free_rate', 0.035)
        method = kwargs.get('method', 'SLSQP')
        n_assets = len(expected_returns)
        tickers = expected_returns.index.tolist()

        # Convert covariance matrix to numpy
        cov_np = cov_matrix.values

        # Initial guess: equal weights
        x0 = np.ones(n_assets) / n_assets

        # Define objective function: minimize sum of squared RC differences
        def objective(weights):
            """Risk parity objective: minimize variance of risk contributions."""
            # Calculate portfolio variance
            portfolio_var = np.dot(weights, np.dot(cov_np, weights))

            # Calculate marginal risk contributions
            marginal_contrib = np.dot(cov_np, weights)

            # Calculate risk contributions
            risk_contrib = weights * marginal_contrib

            # Target: equal risk contribution (1/n of total risk)
            target_rc = portfolio_var / n_assets

            # Objective: sum of squared deviations from target
            return np.sum((risk_contrib - target_rc) ** 2)

        # Define constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum to 1
        ]

        # Add target risk constraint if specified
        if self.target_risk is not None:
            constraints_list.append({
                'type': 'eq',
                'fun': lambda w: np.sqrt(np.dot(w, np.dot(cov_np, w))) - self.target_risk
            })

        # Define bounds
        if self.constraints.long_only:
            bounds = tuple((0, self.constraints.max_position) for _ in range(n_assets))
        else:
            bounds = tuple((-self.constraints.max_position, self.constraints.max_position) for _ in range(n_assets))

        # Solve optimization
        result = minimize(
            objective,
            x0,
            method=method,
            bounds=bounds,
            constraints=constraints_list,
            options={'maxiter': 1000, 'disp': False}
        )

        # Extract solution
        if result.success:
            optimized_weights = result.x

            # Apply minimum position constraint
            optimized_weights = self._apply_min_position_constraint(optimized_weights)

            # Calculate portfolio metrics
            port_return, port_risk, sharpe = self.calculate_portfolio_metrics(
                optimized_weights,
                expected_returns,
                cov_matrix,
                risk_free_rate
            )

            # Calculate risk contributions for metadata
            marginal_contrib = np.dot(cov_np, optimized_weights)
            risk_contrib = optimized_weights * marginal_contrib
            risk_contrib_pct = risk_contrib / risk_contrib.sum()

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
                optimization_method='risk_parity',
                constraints_satisfied=is_valid,
                solver_status='optimal' if result.success else 'failed',
                solver_time=solver_time,
                metadata={
                    'target_risk': self.target_risk,
                    'method': method,
                    'n_assets': n_assets,
                    'n_nonzero_positions': np.sum(optimized_weights > 1e-6),
                    'risk_contributions': {
                        ticker: float(rc)
                        for ticker, rc in zip(tickers, risk_contrib_pct)
                    },
                    'risk_contrib_std': float(np.std(risk_contrib_pct)),
                    'validation_message': error_msg
                }
            )

            return opt_result

        else:
            raise RuntimeError(f"Risk parity optimization failed: {result.message}")

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

    def calculate_risk_contributions(
        self,
        weights: np.ndarray,
        cov_matrix: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate risk contributions for each asset.

        Args:
            weights: Portfolio weights
            cov_matrix: Covariance matrix

        Returns:
            DataFrame with ticker, weight, risk_contribution, risk_contrib_pct
        """
        cov_np = cov_matrix.values
        tickers = cov_matrix.index.tolist()

        # Calculate marginal risk contributions
        marginal_contrib = np.dot(cov_np, weights)

        # Calculate risk contributions
        risk_contrib = weights * marginal_contrib

        # Calculate percentages
        risk_contrib_pct = risk_contrib / risk_contrib.sum()

        # Create DataFrame
        df = pd.DataFrame({
            'ticker': tickers,
            'weight': weights,
            'risk_contribution': risk_contrib,
            'risk_contrib_pct': risk_contrib_pct
        })

        df = df[df['weight'] > 1e-6].sort_values('risk_contrib_pct', ascending=False)

        return df

    def hierarchical_risk_parity(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        **kwargs
    ) -> OptimizationResult:
        """
        Hierarchical Risk Parity (HRP) algorithm.

        HRP uses hierarchical clustering to build a diversified portfolio.
        This is a more sophisticated approach than vanilla risk parity.

        Reference: López de Prado, M. (2016). Building Diversified Portfolios that
        Outperform Out of Sample. Journal of Portfolio Management.

        Args:
            expected_returns: Expected returns (used for metrics only)
            cov_matrix: Covariance matrix
            **kwargs: Additional parameters

        Returns:
            OptimizationResult with HRP weights

        Note: Full HRP implementation requires additional dependencies (scipy.cluster).
        This is a placeholder for future implementation.
        """
        # For now, fall back to standard risk parity
        # TODO: Implement full HRP with hierarchical clustering
        return self.optimize(expected_returns, cov_matrix, **kwargs)


# Export public API
__all__ = ['RiskParityOptimizer']
