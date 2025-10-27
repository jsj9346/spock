"""
Black-Litterman Portfolio Optimization

This module implements the Black-Litterman model, a Bayesian approach that combines
market equilibrium returns with investor views to produce more stable and intuitive
portfolio allocations.

Reference: Black, F. & Litterman, R. (1992). Global Portfolio Optimization.
           Financial Analysts Journal.

Author: Quant Platform Development Team
Last Updated: 2025-10-21
Version: 1.0.0
"""

import time
from typing import Optional, Dict, List, Tuple
import numpy as np
import pandas as pd
import cvxpy as cp

from modules.optimization.optimizer_base import (
    PortfolioOptimizer,
    OptimizationConstraints,
    OptimizationResult
)


class BlackLittermanOptimizer(PortfolioOptimizer):
    """
    Black-Litterman Optimizer.

    The Black-Litterman model combines:
    1. Market equilibrium (implied returns from market cap weights)
    2. Investor views (explicit views on expected returns)

    This produces a posterior expected return estimate that is more stable
    than pure historical estimates.

    Formula:
        E[R] = [(tau * Sigma)^-1 + P' * Omega^-1 * P]^-1
               * [(tau * Sigma)^-1 * Pi + P' * Omega^-1 * Q]

    Where:
        Pi: Implied equilibrium returns
        P: Matrix linking views to assets
        Q: View returns
        Omega: Uncertainty in views
        tau: Uncertainty in prior (default: 0.05)
        Sigma: Covariance matrix
    """

    def __init__(
        self,
        constraints: Optional[OptimizationConstraints] = None,
        tau: float = 0.05,
        risk_aversion: float = 2.5,
        solver: str = 'ECOS'
    ):
        """
        Initialize Black-Litterman optimizer.

        Args:
            constraints: Optimization constraints (uses defaults if None)
            tau: Uncertainty in prior (default: 0.05)
            risk_aversion: Market risk aversion (default: 2.5)
            solver: cvxpy solver (ECOS, SCS, OSQP)
        """
        super().__init__(constraints)
        self.tau = tau
        self.risk_aversion = risk_aversion
        self.solver = solver

    def optimize(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        market_cap_weights: Optional[pd.Series] = None,
        views: Optional[Dict[str, Tuple[List[str], float, float]]] = None,
        **kwargs
    ) -> OptimizationResult:
        """
        Optimize portfolio using Black-Litterman model.

        Args:
            expected_returns: Historical expected returns (used as fallback)
            cov_matrix: Covariance matrix of asset returns
            market_cap_weights: Market capitalization weights (implied equilibrium)
                If None, uses equal weights
            views: Dictionary of investor views
                Format: {
                    'view_name': ([tickers], return, confidence),
                    ...
                }
                Example: {
                    'tech_outperform': (['AAPL', 'MSFT'], 0.15, 0.8),
                    'energy_underperform': (['XOM'], -0.05, 0.6)
                }
            **kwargs: Additional parameters
                - risk_free_rate: Risk-free rate (default: 0.035)

        Returns:
            OptimizationResult with Black-Litterman optimized weights
        """
        # Validate inputs
        self.validate_inputs(expected_returns, cov_matrix)

        # Start timer
        start_time = time.time()

        # Extract parameters
        risk_free_rate = kwargs.get('risk_free_rate', 0.035)
        n_assets = len(expected_returns)
        tickers = expected_returns.index.tolist()
        cov_np = cov_matrix.values

        # Step 1: Calculate implied equilibrium returns (Pi)
        if market_cap_weights is None:
            # Use equal weights if market cap not provided
            market_cap_weights = pd.Series(np.ones(n_assets) / n_assets, index=tickers)

        # Implied returns: Pi = risk_aversion * Sigma * w_mkt
        implied_returns = self.risk_aversion * np.dot(cov_np, market_cap_weights.values)

        # Step 2: Incorporate investor views (if provided)
        if views is not None and len(views) > 0:
            # Build P matrix (views x assets)
            # Build Q vector (view returns)
            # Build Omega matrix (view uncertainties)
            P, Q, Omega = self._build_view_matrices(views, tickers)

            # Step 3: Calculate posterior expected returns
            posterior_returns = self._calculate_posterior_returns(
                implied_returns,
                cov_np,
                P,
                Q,
                Omega
            )

        else:
            # No views: use implied returns
            posterior_returns = implied_returns

        # Step 4: Optimize portfolio using posterior returns
        posterior_returns_series = pd.Series(posterior_returns, index=tickers)

        weights = cp.Variable(n_assets)

        # Objective: maximize return - (risk_aversion / 2) * variance
        portfolio_return = posterior_returns @ weights
        portfolio_variance = cp.quad_form(weights, cov_np)
        objective = cp.Maximize(portfolio_return - (self.risk_aversion / 2) * portfolio_variance)

        # Constraints
        constraints_list = [
            cp.sum(weights) == 1,  # Fully invested
        ]

        if self.constraints.long_only:
            constraints_list.append(weights >= 0)

        constraints_list.append(weights <= self.constraints.max_position)

        # Solve
        problem = cp.Problem(objective, constraints_list)

        try:
            if self.solver == 'ECOS':
                problem.solve(solver=cp.ECOS, verbose=False)
            elif self.solver == 'SCS':
                problem.solve(solver=cp.SCS, verbose=False)
            else:
                problem.solve(verbose=False)

        except Exception as e:
            print(f"⚠️ Solver {self.solver} failed, trying SCS: {e}")
            problem.solve(solver=cp.SCS, verbose=False)

        # Extract solution
        if problem.status in ['optimal', 'optimal_inaccurate']:
            optimized_weights = weights.value

            # Apply minimum position constraint
            optimized_weights = self._apply_min_position_constraint(optimized_weights)

            # Calculate portfolio metrics using POSTERIOR returns
            port_return, port_risk, sharpe = self.calculate_portfolio_metrics(
                optimized_weights,
                posterior_returns_series,
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
                optimization_method='black_litterman',
                constraints_satisfied=is_valid,
                solver_status=problem.status,
                solver_time=solver_time,
                metadata={
                    'tau': self.tau,
                    'risk_aversion': self.risk_aversion,
                    'n_views': len(views) if views else 0,
                    'n_assets': n_assets,
                    'n_nonzero_positions': np.sum(optimized_weights > 1e-6),
                    'implied_returns': {
                        ticker: float(ret)
                        for ticker, ret in zip(tickers, implied_returns)
                    },
                    'posterior_returns': {
                        ticker: float(ret)
                        for ticker, ret in zip(tickers, posterior_returns)
                    },
                    'validation_message': error_msg
                }
            )

            return result

        else:
            raise RuntimeError(f"Black-Litterman optimization failed: {problem.status}")

    def _build_view_matrices(
        self,
        views: Dict[str, Tuple[List[str], float, float]],
        tickers: List[str]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Build P, Q, Omega matrices from investor views.

        Args:
            views: Dictionary of views
            tickers: List of tickers

        Returns:
            Tuple of (P, Q, Omega)
        """
        n_views = len(views)
        n_assets = len(tickers)

        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        Omega = np.zeros((n_views, n_views))

        ticker_to_idx = {ticker: i for i, ticker in enumerate(tickers)}

        for view_idx, (view_name, (view_tickers, view_return, confidence)) in enumerate(views.items()):
            # Build P matrix row
            for ticker in view_tickers:
                if ticker in ticker_to_idx:
                    P[view_idx, ticker_to_idx[ticker]] = 1.0 / len(view_tickers)

            # Build Q vector
            Q[view_idx] = view_return

            # Build Omega matrix (diagonal, uncertainty inversely proportional to confidence)
            Omega[view_idx, view_idx] = (1.0 - confidence) * 0.01  # 1% base uncertainty

        return P, Q, Omega

    def _calculate_posterior_returns(
        self,
        implied_returns: np.ndarray,
        cov_matrix: np.ndarray,
        P: np.ndarray,
        Q: np.ndarray,
        Omega: np.ndarray
    ) -> np.ndarray:
        """
        Calculate posterior expected returns using Black-Litterman formula.

        Args:
            implied_returns: Implied equilibrium returns (Pi)
            cov_matrix: Covariance matrix (Sigma)
            P: View matrix
            Q: View returns
            Omega: View uncertainties

        Returns:
            Posterior expected returns
        """
        # tau * Sigma
        tau_sigma = self.tau * cov_matrix

        # (tau * Sigma)^-1
        tau_sigma_inv = np.linalg.inv(tau_sigma)

        # P' * Omega^-1 * P
        omega_inv = np.linalg.inv(Omega)
        P_omega_P = np.dot(P.T, np.dot(omega_inv, P))

        # Posterior covariance: [(tau * Sigma)^-1 + P' * Omega^-1 * P]^-1
        posterior_cov = np.linalg.inv(tau_sigma_inv + P_omega_P)

        # Posterior returns: posterior_cov * [(tau * Sigma)^-1 * Pi + P' * Omega^-1 * Q]
        term1 = np.dot(tau_sigma_inv, implied_returns)
        term2 = np.dot(P.T, np.dot(omega_inv, Q))
        posterior_returns = np.dot(posterior_cov, term1 + term2)

        return posterior_returns

    def _apply_min_position_constraint(self, weights: np.ndarray) -> np.ndarray:
        """Apply minimum position constraint (post-processing)."""
        weights[weights < 1e-6] = 0
        small_positions = (weights > 0) & (weights < self.constraints.min_position)
        weights[small_positions] = 0

        if weights.sum() > 0:
            weights = weights / weights.sum()

        return weights


# Export public API
__all__ = ['BlackLittermanOptimizer']
