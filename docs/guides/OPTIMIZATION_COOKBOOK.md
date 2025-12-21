# OPTIMIZATION_COOKBOOK.md

Portfolio optimization recipes and implementation examples for the Quant Investment Platform.

## Table of Contents

1. [Overview](#overview)
2. [Mean-Variance Optimization (Markowitz)](#mean-variance-optimization-markowitz)
3. [Risk Parity Portfolio](#risk-parity-portfolio)
4. [Black-Litterman Model](#black-litterman-model)
5. [Kelly Criterion Multi-Asset](#kelly-criterion-multi-asset)
6. [Constraint Handling](#constraint-handling)
7. [Rebalancing Strategies](#rebalancing-strategies)
8. [Advanced Recipes](#advanced-recipes)
9. [Performance Comparison](#performance-comparison)

---

## Overview

### Purpose

This cookbook provides battle-tested portfolio optimization recipes for systematic quant investment strategies. Each recipe includes:
- Mathematical formulation
- Complete Python implementation using cvxpy
- Practical examples with real data
- Common pitfalls and solutions
- Performance characteristics

### Core Libraries

```python
import cvxpy as cp
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple
```

### Optimization Framework Base Class

```python
class PortfolioOptimizer:
    """Base class for portfolio optimization algorithms."""

    def __init__(self, returns: pd.DataFrame, **kwargs):
        """
        Args:
            returns: DataFrame with asset returns (rows: dates, columns: tickers)
            **kwargs: Additional configuration parameters
        """
        self.returns = returns
        self.n_assets = len(returns.columns)
        self.tickers = returns.columns.tolist()

        # Calculate statistics
        self.mean_returns = returns.mean()
        self.cov_matrix = returns.cov()

    def optimize(self, **kwargs) -> Dict:
        """Run optimization and return results."""
        raise NotImplementedError

    def _validate_weights(self, weights: np.ndarray) -> bool:
        """Validate weight constraints."""
        return np.isclose(weights.sum(), 1.0) and np.all(weights >= 0)
```

---

## Mean-Variance Optimization (Markowitz)

### 1.1 Mathematical Formulation

**Objective**: Minimize portfolio variance for a given target return

```
minimize:    w^T Σ w
subject to:  w^T μ = r_target
             w^T 1 = 1
             w ≥ 0
```

Where:
- w: asset weights
- Σ: covariance matrix
- μ: expected returns
- r_target: target return

### 1.2 Basic Implementation

```python
class MarkowitzOptimizer(PortfolioOptimizer):
    """Mean-Variance Optimization (Markowitz 1952)."""

    def optimize(
        self,
        target_return: Optional[float] = None,
        risk_aversion: float = 1.0,
        min_weight: float = 0.0,
        max_weight: float = 1.0
    ) -> Dict:
        """
        Optimize portfolio using Mean-Variance approach.

        Args:
            target_return: Target return (if None, maximize Sharpe ratio)
            risk_aversion: Risk aversion parameter (λ)
            min_weight: Minimum asset weight
            max_weight: Maximum asset weight

        Returns:
            Dictionary with weights, expected_return, volatility, sharpe_ratio
        """
        # Define optimization variables
        weights = cp.Variable(self.n_assets)

        # Portfolio statistics
        portfolio_return = self.mean_returns.values @ weights
        portfolio_variance = cp.quad_form(weights, self.cov_matrix.values)

        # Objective function
        if target_return is not None:
            # Minimize variance for target return
            objective = cp.Minimize(portfolio_variance)
        else:
            # Maximize Sharpe ratio (minimize -return/risk)
            # Use quadratic utility: return - λ * variance
            objective = cp.Maximize(
                portfolio_return - risk_aversion * portfolio_variance
            )

        # Constraints
        constraints = [
            cp.sum(weights) == 1,           # Full investment
            weights >= min_weight,           # Minimum weight
            weights <= max_weight,           # Maximum weight
        ]

        if target_return is not None:
            constraints.append(portfolio_return >= target_return)

        # Solve optimization problem
        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.ECOS)

        if problem.status not in ["optimal", "optimal_inaccurate"]:
            raise ValueError(f"Optimization failed: {problem.status}")

        # Extract results
        optimal_weights = weights.value
        expected_return = float(self.mean_returns.values @ optimal_weights)
        volatility = float(np.sqrt(optimal_weights @ self.cov_matrix.values @ optimal_weights))
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0

        return {
            'weights': pd.Series(optimal_weights, index=self.tickers),
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'status': problem.status
        }
```

### 1.3 Efficient Frontier

```python
def compute_efficient_frontier(
    returns: pd.DataFrame,
    n_points: int = 50,
    min_weight: float = 0.0,
    max_weight: float = 1.0
) -> pd.DataFrame:
    """
    Compute the efficient frontier.

    Args:
        returns: Asset returns DataFrame
        n_points: Number of points on the frontier
        min_weight: Minimum asset weight
        max_weight: Maximum asset weight

    Returns:
        DataFrame with return, volatility, weights for each frontier point
    """
    optimizer = MarkowitzOptimizer(returns)

    # Get min/max achievable returns
    min_return = returns.mean().min()
    max_return = returns.mean().max()

    # Generate target returns
    target_returns = np.linspace(min_return, max_return, n_points)

    frontier_results = []

    for target_ret in target_returns:
        try:
            result = optimizer.optimize(
                target_return=target_ret,
                min_weight=min_weight,
                max_weight=max_weight
            )

            frontier_results.append({
                'target_return': target_ret,
                'expected_return': result['expected_return'],
                'volatility': result['volatility'],
                'sharpe_ratio': result['sharpe_ratio'],
                'weights': result['weights']
            })
        except ValueError:
            # Skip infeasible target returns
            continue

    return pd.DataFrame(frontier_results)
```

### 1.4 Maximum Sharpe Ratio Portfolio

```python
def max_sharpe_portfolio(
    returns: pd.DataFrame,
    risk_free_rate: float = 0.02,
    min_weight: float = 0.0,
    max_weight: float = 1.0
) -> Dict:
    """
    Find the portfolio with maximum Sharpe ratio.

    Args:
        returns: Asset returns DataFrame
        risk_free_rate: Risk-free rate (annualized)
        min_weight: Minimum asset weight
        max_weight: Maximum asset weight

    Returns:
        Dictionary with optimal weights and portfolio statistics
    """
    n_assets = len(returns.columns)

    # Objective: Minimize negative Sharpe ratio
    def neg_sharpe(weights):
        portfolio_return = (returns.mean().values @ weights) * 252  # Annualize
        portfolio_vol = np.sqrt(weights @ returns.cov().values @ weights) * np.sqrt(252)
        sharpe = (portfolio_return - risk_free_rate) / portfolio_vol
        return -sharpe

    # Constraints
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum to 1
    ]

    # Bounds
    bounds = tuple((min_weight, max_weight) for _ in range(n_assets))

    # Initial guess (equal weight)
    initial_weights = np.array([1/n_assets] * n_assets)

    # Optimize
    result = minimize(
        neg_sharpe,
        initial_weights,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )

    if not result.success:
        raise ValueError(f"Optimization failed: {result.message}")

    optimal_weights = result.x
    portfolio_return = (returns.mean().values @ optimal_weights) * 252
    portfolio_vol = np.sqrt(optimal_weights @ returns.cov().values @ optimal_weights) * np.sqrt(252)
    sharpe = (portfolio_return - risk_free_rate) / portfolio_vol

    return {
        'weights': pd.Series(optimal_weights, index=returns.columns),
        'expected_return': portfolio_return,
        'volatility': portfolio_vol,
        'sharpe_ratio': sharpe
    }
```

### 1.5 Example Usage

```python
# Load historical returns (250 trading days)
returns = pd.read_sql(
    """
    SELECT date, ticker, daily_return
    FROM ohlcv_data
    WHERE region = 'KR'
      AND date >= CURRENT_DATE - INTERVAL '250 days'
    """,
    db.engine
).pivot(index='date', columns='ticker', values='daily_return')

# 1. Basic Mean-Variance optimization
optimizer = MarkowitzOptimizer(returns)
result = optimizer.optimize(risk_aversion=2.0, max_weight=0.20)

print("Optimal Weights:")
print(result['weights'].sort_values(ascending=False).head(10))
print(f"\nExpected Return: {result['expected_return']:.2%}")
print(f"Volatility: {result['volatility']:.2%}")
print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")

# 2. Compute efficient frontier
frontier = compute_efficient_frontier(returns, n_points=50, max_weight=0.20)

# 3. Find max Sharpe portfolio
max_sharpe = max_sharpe_portfolio(returns, risk_free_rate=0.035, max_weight=0.20)

print("\nMax Sharpe Portfolio:")
print(max_sharpe['weights'].sort_values(ascending=False).head(10))
print(f"Sharpe Ratio: {max_sharpe['sharpe_ratio']:.2f}")
```

---

## Risk Parity Portfolio

### 2.1 Mathematical Formulation

**Objective**: Equalize risk contribution from each asset

```
Risk Contribution_i = w_i * (Σw)_i / sqrt(w^T Σ w)

Objective: Minimize Σ (RC_i - 1/N)^2
```

### 2.2 Implementation

```python
class RiskParityOptimizer(PortfolioOptimizer):
    """Risk Parity Portfolio Optimization."""

    def optimize(
        self,
        target_risk_contributions: Optional[np.ndarray] = None,
        max_weight: float = 0.40,
        tolerance: float = 1e-6
    ) -> Dict:
        """
        Optimize portfolio using Risk Parity approach.

        Args:
            target_risk_contributions: Target risk contributions (default: equal)
            max_weight: Maximum asset weight
            tolerance: Convergence tolerance

        Returns:
            Dictionary with weights, risk_contributions, volatility
        """
        if target_risk_contributions is None:
            target_risk_contributions = np.ones(self.n_assets) / self.n_assets

        # Objective: Minimize squared difference from target risk contributions
        def objective(weights):
            portfolio_vol = np.sqrt(weights @ self.cov_matrix.values @ weights)
            marginal_contrib = self.cov_matrix.values @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            risk_contrib_pct = risk_contrib / risk_contrib.sum()

            # Sum of squared errors
            sse = np.sum((risk_contrib_pct - target_risk_contributions) ** 2)
            return sse

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Sum to 1
        ]

        # Bounds
        bounds = tuple((0.0, max_weight) for _ in range(self.n_assets))

        # Initial guess (equal weight)
        initial_weights = np.array([1/self.n_assets] * self.n_assets)

        # Optimize
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': tolerance}
        )

        if not result.success:
            raise ValueError(f"Optimization failed: {result.message}")

        optimal_weights = result.x

        # Calculate risk contributions
        portfolio_vol = np.sqrt(optimal_weights @ self.cov_matrix.values @ optimal_weights)
        marginal_contrib = self.cov_matrix.values @ optimal_weights
        risk_contrib = optimal_weights * marginal_contrib / portfolio_vol
        risk_contrib_pct = risk_contrib / risk_contrib.sum()

        expected_return = float(self.mean_returns.values @ optimal_weights)
        sharpe_ratio = expected_return / portfolio_vol if portfolio_vol > 0 else 0

        return {
            'weights': pd.Series(optimal_weights, index=self.tickers),
            'risk_contributions': pd.Series(risk_contrib_pct, index=self.tickers),
            'expected_return': expected_return,
            'volatility': portfolio_vol,
            'sharpe_ratio': sharpe_ratio
        }
```

### 2.3 Example Usage

```python
# Risk Parity optimization
rp_optimizer = RiskParityOptimizer(returns)
rp_result = rp_optimizer.optimize(max_weight=0.30)

print("Risk Parity Weights:")
print(rp_result['weights'].sort_values(ascending=False).head(10))

print("\nRisk Contributions:")
print(rp_result['risk_contributions'].sort_values(ascending=False).head(10))

print(f"\nVolatility: {rp_result['volatility']:.2%}")
print(f"Sharpe Ratio: {rp_result['sharpe_ratio']:.2f}")

# Verify equal risk contribution
print("\nRisk Contribution Stats:")
print(f"Mean: {rp_result['risk_contributions'].mean():.4f}")
print(f"Std Dev: {rp_result['risk_contributions'].std():.4f}")
```

---

## Black-Litterman Model

### 3.1 Mathematical Formulation

**Combines market equilibrium (CAPM) with investor views**

```
Posterior Expected Returns: μ_BL = [(τΣ)^(-1) + P^T Ω^(-1) P]^(-1) [(τΣ)^(-1) π + P^T Ω^(-1) Q]
```

Where:
- π: Equilibrium returns (market-implied)
- P: Pick matrix (which assets are affected by views)
- Q: View returns
- Ω: Uncertainty in views
- τ: Scaling factor (typically 0.025-0.05)

### 3.2 Implementation

```python
class BlackLittermanOptimizer(PortfolioOptimizer):
    """Black-Litterman Portfolio Optimization."""

    def __init__(
        self,
        returns: pd.DataFrame,
        market_caps: pd.Series,
        risk_free_rate: float = 0.02,
        tau: float = 0.025
    ):
        """
        Args:
            returns: Asset returns DataFrame
            market_caps: Market capitalization for each asset
            risk_free_rate: Risk-free rate (annualized)
            tau: Scaling factor for uncertainty in prior
        """
        super().__init__(returns)
        self.market_caps = market_caps
        self.risk_free_rate = risk_free_rate
        self.tau = tau

        # Compute equilibrium returns (reverse optimization)
        self.equilibrium_returns = self._compute_equilibrium_returns()

    def _compute_equilibrium_returns(self) -> np.ndarray:
        """
        Compute market equilibrium returns using reverse optimization.

        π = λ * Σ * w_mkt
        where λ = (E[R_m] - R_f) / σ_m^2
        """
        # Market weights (proportional to market cap)
        market_weights = self.market_caps / self.market_caps.sum()
        market_weights = market_weights.reindex(self.tickers, fill_value=0).values

        # Market return and variance
        market_return = (self.mean_returns.values @ market_weights) * 252
        market_variance = market_weights @ self.cov_matrix.values @ market_weights * 252

        # Risk aversion parameter
        risk_aversion = (market_return - self.risk_free_rate) / market_variance

        # Equilibrium returns
        equilibrium_returns = risk_aversion * (self.cov_matrix.values @ market_weights)

        return equilibrium_returns

    def optimize(
        self,
        views: List[Dict],
        confidence: float = 0.5,
        min_weight: float = 0.0,
        max_weight: float = 0.30
    ) -> Dict:
        """
        Optimize portfolio using Black-Litterman model with investor views.

        Args:
            views: List of view dictionaries with format:
                   {'type': 'absolute' or 'relative',
                    'assets': [ticker1, ticker2, ...],
                    'return': expected_return}
            confidence: Confidence in views (0-1, higher = more confident)
            min_weight: Minimum asset weight
            max_weight: Maximum asset weight

        Returns:
            Dictionary with weights, posterior_returns, expected_return, volatility
        """
        # Construct pick matrix P and view returns Q
        P, Q = self._construct_views(views)
        k = len(views)  # Number of views

        # View uncertainty matrix Ω
        # Higher confidence → lower uncertainty
        omega = np.eye(k) * (1 - confidence)

        # Black-Litterman formula
        tau_sigma = self.tau * self.cov_matrix.values

        # Posterior covariance
        M_inv = np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P
        M = np.linalg.inv(M_inv)

        # Posterior expected returns
        posterior_returns = M @ (
            np.linalg.inv(tau_sigma) @ self.equilibrium_returns +
            P.T @ np.linalg.inv(omega) @ Q
        )

        # Optimize using posterior returns
        weights = cp.Variable(self.n_assets)
        portfolio_return = posterior_returns @ weights
        portfolio_variance = cp.quad_form(weights, self.cov_matrix.values)

        # Maximize Sharpe ratio
        objective = cp.Maximize(portfolio_return - 2.0 * portfolio_variance)

        constraints = [
            cp.sum(weights) == 1,
            weights >= min_weight,
            weights <= max_weight
        ]

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.ECOS)

        if problem.status not in ["optimal", "optimal_inaccurate"]:
            raise ValueError(f"Optimization failed: {problem.status}")

        optimal_weights = weights.value
        expected_return = float(posterior_returns @ optimal_weights)
        volatility = float(np.sqrt(optimal_weights @ self.cov_matrix.values @ optimal_weights))
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0

        return {
            'weights': pd.Series(optimal_weights, index=self.tickers),
            'posterior_returns': pd.Series(posterior_returns, index=self.tickers),
            'equilibrium_returns': pd.Series(self.equilibrium_returns, index=self.tickers),
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio
        }

    def _construct_views(
        self,
        views: List[Dict]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Construct pick matrix P and view returns Q from view specifications.

        Args:
            views: List of view dictionaries

        Returns:
            P (k x n), Q (k x 1) where k = number of views
        """
        k = len(views)
        n = self.n_assets

        P = np.zeros((k, n))
        Q = np.zeros(k)

        for i, view in enumerate(views):
            view_type = view['type']
            assets = view['assets']
            view_return = view['return']

            if view_type == 'absolute':
                # Absolute view: Asset X will return r%
                ticker_idx = self.tickers.index(assets[0])
                P[i, ticker_idx] = 1.0
                Q[i] = view_return

            elif view_type == 'relative':
                # Relative view: Asset X will outperform Asset Y by r%
                ticker1_idx = self.tickers.index(assets[0])
                ticker2_idx = self.tickers.index(assets[1])
                P[i, ticker1_idx] = 1.0
                P[i, ticker2_idx] = -1.0
                Q[i] = view_return

            else:
                raise ValueError(f"Unknown view type: {view_type}")

        return P, Q
```

### 3.3 Example Usage

```python
# Black-Litterman with investor views
market_caps = pd.read_sql(
    """
    SELECT ticker, market_cap
    FROM tickers
    WHERE region = 'KR'
    """,
    db.engine
).set_index('ticker')['market_cap']

bl_optimizer = BlackLittermanOptimizer(
    returns=returns,
    market_caps=market_caps,
    risk_free_rate=0.035,
    tau=0.025
)

# Define investor views
views = [
    {
        'type': 'absolute',
        'assets': ['005930'],  # Samsung Electronics
        'return': 0.15  # Expect 15% annual return
    },
    {
        'type': 'relative',
        'assets': ['000660', '005380'],  # SK Hynix vs Hyundai Motor
        'return': 0.05  # SK Hynix outperforms by 5%
    }
]

bl_result = bl_optimizer.optimize(
    views=views,
    confidence=0.7,  # 70% confidence in views
    max_weight=0.25
)

print("Black-Litterman Weights:")
print(bl_result['weights'].sort_values(ascending=False).head(10))

print("\nPosterior Returns vs Equilibrium:")
comparison = pd.DataFrame({
    'Equilibrium': bl_result['equilibrium_returns'],
    'Posterior': bl_result['posterior_returns']
})
print(comparison.sort_values('Posterior', ascending=False).head(10))

print(f"\nExpected Return: {bl_result['expected_return']:.2%}")
print(f"Volatility: {bl_result['volatility']:.2%}")
print(f"Sharpe Ratio: {bl_result['sharpe_ratio']:.2f}")
```

---

## Kelly Criterion Multi-Asset

### 4.1 Mathematical Formulation

**Kelly Formula for Multiple Assets**

```
f* = Σ^(-1) * (μ - r_f)

where:
- f*: optimal leverage/weights
- Σ: covariance matrix
- μ: expected returns
- r_f: risk-free rate
```

### 4.2 Implementation

```python
class KellyCriterionOptimizer(PortfolioOptimizer):
    """Kelly Criterion Portfolio Optimization."""

    def optimize(
        self,
        risk_free_rate: float = 0.02,
        kelly_fraction: float = 0.5,
        min_weight: float = 0.0,
        max_weight: float = 0.30,
        max_leverage: float = 1.0
    ) -> Dict:
        """
        Optimize portfolio using Kelly Criterion.

        Args:
            risk_free_rate: Risk-free rate (annualized)
            kelly_fraction: Fraction of full Kelly (0.5 = Half Kelly)
            min_weight: Minimum asset weight
            max_weight: Maximum asset weight
            max_leverage: Maximum portfolio leverage

        Returns:
            Dictionary with weights, expected_return, volatility, kelly_leverage
        """
        # Annualize returns and covariance
        annual_returns = self.mean_returns * 252
        annual_cov = self.cov_matrix * 252

        # Full Kelly weights
        excess_returns = annual_returns - risk_free_rate

        try:
            full_kelly_weights = np.linalg.solve(
                annual_cov.values,
                excess_returns.values
            )
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse for singular matrices
            full_kelly_weights = np.linalg.lstsq(
                annual_cov.values,
                excess_returns.values,
                rcond=None
            )[0]

        # Apply Kelly fraction
        kelly_weights = full_kelly_weights * kelly_fraction

        # Normalize and apply constraints
        if kelly_weights.sum() > max_leverage:
            kelly_weights = kelly_weights / kelly_weights.sum() * max_leverage

        # Clip to min/max weights
        kelly_weights = np.clip(kelly_weights, min_weight, max_weight)

        # Renormalize to sum to 1
        kelly_weights = kelly_weights / kelly_weights.sum()

        # Calculate portfolio statistics
        expected_return = float(self.mean_returns.values @ kelly_weights)
        volatility = float(np.sqrt(kelly_weights @ self.cov_matrix.values @ kelly_weights))
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0
        kelly_leverage = kelly_weights.sum()

        return {
            'weights': pd.Series(kelly_weights, index=self.tickers),
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'kelly_leverage': kelly_leverage
        }
```

### 4.3 Example Usage

```python
# Kelly Criterion optimization
kelly_optimizer = KellyCriterionOptimizer(returns)

# Full Kelly (aggressive)
full_kelly = kelly_optimizer.optimize(
    risk_free_rate=0.035,
    kelly_fraction=1.0,
    max_weight=0.30
)

# Half Kelly (conservative)
half_kelly = kelly_optimizer.optimize(
    risk_free_rate=0.035,
    kelly_fraction=0.5,
    max_weight=0.20
)

print("Full Kelly Weights:")
print(full_kelly['weights'].sort_values(ascending=False).head(10))
print(f"Kelly Leverage: {full_kelly['kelly_leverage']:.2f}")

print("\nHalf Kelly Weights:")
print(half_kelly['weights'].sort_values(ascending=False).head(10))
print(f"Kelly Leverage: {half_kelly['kelly_leverage']:.2f}")

print(f"\nFull Kelly Sharpe: {full_kelly['sharpe_ratio']:.2f}")
print(f"Half Kelly Sharpe: {half_kelly['sharpe_ratio']:.2f}")
```

---

## Constraint Handling

### 5.1 Position Limits

```python
def optimize_with_position_limits(
    returns: pd.DataFrame,
    min_positions: int = 10,
    max_positions: int = 30,
    min_weight_per_position: float = 0.02,
    max_weight_per_position: float = 0.15
) -> Dict:
    """
    Optimize portfolio with constraints on number of positions.

    Args:
        returns: Asset returns DataFrame
        min_positions: Minimum number of positions
        max_positions: Maximum number of positions
        min_weight_per_position: Minimum weight for active positions
        max_weight_per_position: Maximum weight per position

    Returns:
        Dictionary with optimal weights and portfolio statistics
    """
    n_assets = len(returns.columns)

    # Variables
    weights = cp.Variable(n_assets)
    active = cp.Variable(n_assets, boolean=True)  # Binary indicator

    # Portfolio statistics
    mean_returns = returns.mean().values
    cov_matrix = returns.cov().values
    portfolio_return = mean_returns @ weights
    portfolio_variance = cp.quad_form(weights, cov_matrix)

    # Objective: Maximize Sharpe ratio
    objective = cp.Maximize(portfolio_return - 2.0 * portfolio_variance)

    # Constraints
    constraints = [
        cp.sum(weights) == 1,                      # Full investment
        weights >= 0,                               # Long-only
        weights <= max_weight_per_position,         # Max position size
        cp.sum(active) >= min_positions,            # Min number of positions
        cp.sum(active) <= max_positions,            # Max number of positions
    ]

    # Link weights to active indicators
    for i in range(n_assets):
        constraints.extend([
            weights[i] >= min_weight_per_position * active[i],
            weights[i] <= max_weight_per_position * active[i]
        ])

    # Solve
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.GUROBI)  # Requires Gurobi for MIQP

    if problem.status not in ["optimal", "optimal_inaccurate"]:
        raise ValueError(f"Optimization failed: {problem.status}")

    optimal_weights = weights.value
    n_positions = int(active.value.sum())
    expected_return = float(mean_returns @ optimal_weights)
    volatility = float(np.sqrt(optimal_weights @ cov_matrix @ optimal_weights))
    sharpe_ratio = expected_return / volatility if volatility > 0 else 0

    return {
        'weights': pd.Series(optimal_weights, index=returns.columns),
        'n_positions': n_positions,
        'expected_return': expected_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio
    }
```

### 5.2 Sector Limits

```python
def optimize_with_sector_limits(
    returns: pd.DataFrame,
    sector_mapping: Dict[str, str],
    max_sector_weight: float = 0.40,
    min_weight: float = 0.0,
    max_weight: float = 0.20
) -> Dict:
    """
    Optimize portfolio with sector exposure constraints.

    Args:
        returns: Asset returns DataFrame
        sector_mapping: Dictionary mapping ticker → sector
        max_sector_weight: Maximum weight per sector
        min_weight: Minimum asset weight
        max_weight: Maximum asset weight

    Returns:
        Dictionary with optimal weights and sector exposures
    """
    n_assets = len(returns.columns)
    tickers = returns.columns.tolist()

    # Get unique sectors
    sectors = list(set(sector_mapping.values()))

    # Variables
    weights = cp.Variable(n_assets)

    # Portfolio statistics
    mean_returns = returns.mean().values
    cov_matrix = returns.cov().values
    portfolio_return = mean_returns @ weights
    portfolio_variance = cp.quad_form(weights, cov_matrix)

    # Objective
    objective = cp.Maximize(portfolio_return - 2.0 * portfolio_variance)

    # Constraints
    constraints = [
        cp.sum(weights) == 1,
        weights >= min_weight,
        weights <= max_weight
    ]

    # Sector constraints
    for sector in sectors:
        sector_tickers = [t for t in tickers if sector_mapping.get(t) == sector]
        sector_indices = [tickers.index(t) for t in sector_tickers]

        if sector_indices:
            sector_weights = cp.sum([weights[i] for i in sector_indices])
            constraints.append(sector_weights <= max_sector_weight)

    # Solve
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.ECOS)

    if problem.status not in ["optimal", "optimal_inaccurate"]:
        raise ValueError(f"Optimization failed: {problem.status}")

    optimal_weights = weights.value

    # Calculate sector exposures
    sector_exposures = {}
    for sector in sectors:
        sector_tickers = [t for t in tickers if sector_mapping.get(t) == sector]
        sector_weight = sum(optimal_weights[tickers.index(t)] for t in sector_tickers)
        sector_exposures[sector] = sector_weight

    expected_return = float(mean_returns @ optimal_weights)
    volatility = float(np.sqrt(optimal_weights @ cov_matrix @ optimal_weights))
    sharpe_ratio = expected_return / volatility if volatility > 0 else 0

    return {
        'weights': pd.Series(optimal_weights, index=tickers),
        'sector_exposures': pd.Series(sector_exposures),
        'expected_return': expected_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio
    }
```

### 5.3 Turnover Constraints

```python
def optimize_with_turnover_limit(
    returns: pd.DataFrame,
    current_weights: pd.Series,
    max_turnover: float = 0.20,
    min_weight: float = 0.0,
    max_weight: float = 0.20
) -> Dict:
    """
    Optimize portfolio with turnover constraint.

    Args:
        returns: Asset returns DataFrame
        current_weights: Current portfolio weights
        max_turnover: Maximum one-way turnover (0.2 = 20% turnover)
        min_weight: Minimum asset weight
        max_weight: Maximum asset weight

    Returns:
        Dictionary with optimal weights and turnover
    """
    n_assets = len(returns.columns)
    tickers = returns.columns.tolist()

    # Align current weights with returns
    current_weights = current_weights.reindex(tickers, fill_value=0.0).values

    # Variables
    weights = cp.Variable(n_assets)

    # Portfolio statistics
    mean_returns = returns.mean().values
    cov_matrix = returns.cov().values
    portfolio_return = mean_returns @ weights
    portfolio_variance = cp.quad_form(weights, cov_matrix)

    # Objective
    objective = cp.Maximize(portfolio_return - 2.0 * portfolio_variance)

    # Turnover: sum of absolute weight changes
    turnover = cp.norm1(weights - current_weights)

    # Constraints
    constraints = [
        cp.sum(weights) == 1,
        weights >= min_weight,
        weights <= max_weight,
        turnover <= max_turnover  # Turnover constraint
    ]

    # Solve
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.ECOS)

    if problem.status not in ["optimal", "optimal_inaccurate"]:
        raise ValueError(f"Optimization failed: {problem.status}")

    optimal_weights = weights.value
    actual_turnover = float(np.sum(np.abs(optimal_weights - current_weights)))

    expected_return = float(mean_returns @ optimal_weights)
    volatility = float(np.sqrt(optimal_weights @ cov_matrix @ optimal_weights))
    sharpe_ratio = expected_return / volatility if volatility > 0 else 0

    return {
        'weights': pd.Series(optimal_weights, index=tickers),
        'turnover': actual_turnover,
        'expected_return': expected_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio
    }
```

---

## Rebalancing Strategies

### 6.1 Time-Based Rebalancing

```python
class TimeBasedRebalancer:
    """Time-based portfolio rebalancing."""

    def __init__(
        self,
        optimizer,
        rebalance_frequency: str = 'monthly'
    ):
        """
        Args:
            optimizer: Portfolio optimizer instance
            rebalance_frequency: 'daily', 'weekly', 'monthly', 'quarterly'
        """
        self.optimizer = optimizer
        self.rebalance_frequency = rebalance_frequency
        self.last_rebalance_date = None
        self.current_weights = None

    def should_rebalance(self, current_date: pd.Timestamp) -> bool:
        """Check if rebalancing is needed."""
        if self.last_rebalance_date is None:
            return True

        if self.rebalance_frequency == 'daily':
            return True
        elif self.rebalance_frequency == 'weekly':
            return (current_date - self.last_rebalance_date).days >= 7
        elif self.rebalance_frequency == 'monthly':
            return current_date.month != self.last_rebalance_date.month
        elif self.rebalance_frequency == 'quarterly':
            return current_date.quarter != self.last_rebalance_date.quarter
        else:
            raise ValueError(f"Unknown frequency: {self.rebalance_frequency}")

    def rebalance(self, current_date: pd.Timestamp, **optimizer_kwargs) -> Dict:
        """Execute rebalancing."""
        if not self.should_rebalance(current_date):
            return {'weights': self.current_weights, 'rebalanced': False}

        # Run optimization
        result = self.optimizer.optimize(**optimizer_kwargs)

        self.current_weights = result['weights']
        self.last_rebalance_date = current_date

        return {**result, 'rebalanced': True, 'rebalance_date': current_date}
```

### 6.2 Threshold-Based Rebalancing

```python
class ThresholdRebalancer:
    """Threshold-based portfolio rebalancing."""

    def __init__(
        self,
        optimizer,
        deviation_threshold: float = 0.05,
        min_rebalance_interval_days: int = 30
    ):
        """
        Args:
            optimizer: Portfolio optimizer instance
            deviation_threshold: Max deviation from target weights (0.05 = 5%)
            min_rebalance_interval_days: Minimum days between rebalances
        """
        self.optimizer = optimizer
        self.deviation_threshold = deviation_threshold
        self.min_rebalance_interval_days = min_rebalance_interval_days
        self.target_weights = None
        self.last_rebalance_date = None

    def should_rebalance(
        self,
        current_weights: pd.Series,
        current_date: pd.Timestamp
    ) -> bool:
        """
        Check if rebalancing is needed based on drift from target.

        Args:
            current_weights: Current portfolio weights (after market movements)
            current_date: Current date

        Returns:
            True if rebalancing is needed
        """
        if self.target_weights is None:
            return True

        # Check minimum interval
        if self.last_rebalance_date is not None:
            days_since_last = (current_date - self.last_rebalance_date).days
            if days_since_last < self.min_rebalance_interval_days:
                return False

        # Align current weights with target
        current_weights = current_weights.reindex(
            self.target_weights.index,
            fill_value=0.0
        )

        # Check maximum deviation
        max_deviation = (current_weights - self.target_weights).abs().max()

        return max_deviation > self.deviation_threshold

    def rebalance(
        self,
        current_weights: pd.Series,
        current_date: pd.Timestamp,
        **optimizer_kwargs
    ) -> Dict:
        """Execute rebalancing if needed."""
        if not self.should_rebalance(current_weights, current_date):
            return {'weights': self.target_weights, 'rebalanced': False}

        # Run optimization
        result = self.optimizer.optimize(**optimizer_kwargs)

        self.target_weights = result['weights']
        self.last_rebalance_date = current_date

        return {**result, 'rebalanced': True, 'rebalance_date': current_date}
```

### 6.3 Adaptive Rebalancing

```python
class AdaptiveRebalancer:
    """Adaptive rebalancing based on market conditions."""

    def __init__(
        self,
        optimizer,
        volatility_window: int = 60,
        low_vol_frequency_days: int = 90,
        high_vol_frequency_days: int = 30
    ):
        """
        Args:
            optimizer: Portfolio optimizer instance
            volatility_window: Rolling window for volatility calculation
            low_vol_frequency_days: Rebalance frequency in low volatility
            high_vol_frequency_days: Rebalance frequency in high volatility
        """
        self.optimizer = optimizer
        self.volatility_window = volatility_window
        self.low_vol_frequency_days = low_vol_frequency_days
        self.high_vol_frequency_days = high_vol_frequency_days
        self.current_weights = None
        self.last_rebalance_date = None

    def calculate_market_volatility(
        self,
        returns: pd.DataFrame,
        current_date: pd.Timestamp
    ) -> float:
        """Calculate recent market volatility."""
        # Get recent returns
        recent_returns = returns.loc[:current_date].tail(self.volatility_window)

        # Calculate portfolio volatility (equal-weighted)
        equal_weights = np.ones(len(returns.columns)) / len(returns.columns)
        portfolio_returns = recent_returns @ equal_weights

        return portfolio_returns.std() * np.sqrt(252)  # Annualize

    def should_rebalance(
        self,
        returns: pd.DataFrame,
        current_date: pd.Timestamp
    ) -> bool:
        """Decide if rebalancing is needed based on market volatility."""
        if self.last_rebalance_date is None:
            return True

        # Calculate current volatility
        current_vol = self.calculate_market_volatility(returns, current_date)

        # Determine rebalance frequency based on volatility
        # High volatility → more frequent rebalancing
        historical_vol = returns.std().mean() * np.sqrt(252)
        vol_ratio = current_vol / historical_vol

        if vol_ratio > 1.5:
            # High volatility regime
            required_frequency_days = self.high_vol_frequency_days
        else:
            # Low volatility regime
            required_frequency_days = self.low_vol_frequency_days

        days_since_last = (current_date - self.last_rebalance_date).days

        return days_since_last >= required_frequency_days

    def rebalance(
        self,
        returns: pd.DataFrame,
        current_date: pd.Timestamp,
        **optimizer_kwargs
    ) -> Dict:
        """Execute adaptive rebalancing."""
        if not self.should_rebalance(returns, current_date):
            return {'weights': self.current_weights, 'rebalanced': False}

        # Run optimization
        result = self.optimizer.optimize(**optimizer_kwargs)

        self.current_weights = result['weights']
        self.last_rebalance_date = current_date

        # Calculate current volatility for reporting
        current_vol = self.calculate_market_volatility(returns, current_date)

        return {
            **result,
            'rebalanced': True,
            'rebalance_date': current_date,
            'market_volatility': current_vol
        }
```

---

## Advanced Recipes

### 7.1 Hierarchical Risk Parity (HRP)

```python
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform

class HierarchicalRiskParityOptimizer(PortfolioOptimizer):
    """Hierarchical Risk Parity (Lopez de Prado 2016)."""

    def optimize(self) -> Dict:
        """
        Optimize portfolio using Hierarchical Risk Parity.

        Steps:
        1. Cluster assets based on correlation
        2. Quasi-diagonalize covariance matrix
        3. Recursive bisection for weight allocation
        """
        # Step 1: Tree clustering
        corr_matrix = self.returns.corr()
        dist_matrix = np.sqrt((1 - corr_matrix) / 2)  # Distance metric
        linkage_matrix = linkage(squareform(dist_matrix), method='single')

        # Step 2: Quasi-diagonalization
        sorted_indices = self._get_quasi_diag(linkage_matrix)
        sorted_cov = self.cov_matrix.iloc[sorted_indices, sorted_indices]

        # Step 3: Recursive bisection
        weights = self._recursive_bisection(sorted_cov)

        # Reorder weights to original order
        weights_series = pd.Series(weights, index=sorted_cov.columns)
        weights_series = weights_series.reindex(self.tickers)

        # Calculate portfolio statistics
        expected_return = float(self.mean_returns.values @ weights_series.values)
        volatility = float(np.sqrt(
            weights_series.values @ self.cov_matrix.values @ weights_series.values
        ))
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0

        return {
            'weights': weights_series,
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio
        }

    def _get_quasi_diag(self, linkage_matrix: np.ndarray) -> List[int]:
        """Get quasi-diagonal order from linkage matrix."""
        from scipy.cluster.hierarchy import to_tree

        tree = to_tree(linkage_matrix, rd=False)
        sorted_indices = []

        def traverse(node):
            if node.is_leaf():
                sorted_indices.append(node.id)
            else:
                traverse(node.get_left())
                traverse(node.get_right())

        traverse(tree)
        return sorted_indices

    def _recursive_bisection(self, cov: pd.DataFrame) -> np.ndarray:
        """Recursive bisection for weight allocation."""
        weights = pd.Series(1.0, index=cov.index)
        clusters = [cov.index.tolist()]

        while len(clusters) > 0:
            clusters = [
                cluster[start:end]
                for cluster in clusters
                for start, end in [(0, len(cluster)//2), (len(cluster)//2, len(cluster))]
                if len(cluster) > 1
            ]

            for i in range(0, len(clusters), 2):
                cluster1 = clusters[i]
                cluster2 = clusters[i+1] if i+1 < len(clusters) else []

                if not cluster2:
                    continue

                # Calculate cluster variances
                cov1 = cov.loc[cluster1, cluster1]
                cov2 = cov.loc[cluster2, cluster2]

                var1 = self._get_cluster_variance(cov1)
                var2 = self._get_cluster_variance(cov2)

                # Allocate weights inversely proportional to variance
                alpha = 1 - var1 / (var1 + var2)

                weights[cluster1] *= alpha
                weights[cluster2] *= (1 - alpha)

        return weights.values

    def _get_cluster_variance(self, cov: pd.DataFrame) -> float:
        """Calculate variance of equally-weighted cluster."""
        n = len(cov)
        equal_weights = np.ones(n) / n
        return equal_weights @ cov.values @ equal_weights
```

### 7.2 Minimum Correlation Algorithm

```python
class MinimumCorrelationOptimizer(PortfolioOptimizer):
    """Minimum Correlation Portfolio."""

    def optimize(
        self,
        min_weight: float = 0.0,
        max_weight: float = 0.25
    ) -> Dict:
        """
        Optimize portfolio to minimize average correlation.

        Objective: Minimize w^T C w
        where C is the correlation matrix
        """
        n_assets = self.n_assets

        # Variables
        weights = cp.Variable(n_assets)

        # Correlation matrix
        corr_matrix = self.returns.corr().values

        # Objective: Minimize portfolio correlation
        portfolio_correlation = cp.quad_form(weights, corr_matrix)
        objective = cp.Minimize(portfolio_correlation)

        # Constraints
        constraints = [
            cp.sum(weights) == 1,
            weights >= min_weight,
            weights <= max_weight
        ]

        # Solve
        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.ECOS)

        if problem.status not in ["optimal", "optimal_inaccurate"]:
            raise ValueError(f"Optimization failed: {problem.status}")

        optimal_weights = weights.value

        # Calculate portfolio statistics
        expected_return = float(self.mean_returns.values @ optimal_weights)
        volatility = float(np.sqrt(
            optimal_weights @ self.cov_matrix.values @ optimal_weights
        ))
        sharpe_ratio = expected_return / volatility if volatility > 0 else 0

        # Calculate average correlation
        avg_correlation = float(optimal_weights @ corr_matrix @ optimal_weights)

        return {
            'weights': pd.Series(optimal_weights, index=self.tickers),
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'avg_correlation': avg_correlation
        }
```

---

## Performance Comparison

### 8.1 Backtesting Multiple Strategies

```python
def backtest_optimization_strategies(
    returns: pd.DataFrame,
    strategies: Dict[str, PortfolioOptimizer],
    rebalance_frequency: str = 'monthly',
    transaction_cost_bps: float = 10.0
) -> pd.DataFrame:
    """
    Backtest multiple optimization strategies.

    Args:
        returns: Historical returns DataFrame
        strategies: Dictionary mapping strategy name → optimizer
        rebalance_frequency: Rebalancing frequency
        transaction_cost_bps: Transaction costs in basis points

    Returns:
        DataFrame with performance metrics for each strategy
    """
    results = []

    for strategy_name, optimizer in strategies.items():
        print(f"Backtesting: {strategy_name}...")

        # Initialize
        portfolio_value = 100.0
        weights = None
        portfolio_returns = []

        dates = returns.index
        rebalance_dates = _get_rebalance_dates(dates, rebalance_frequency)

        for i, date in enumerate(dates):
            # Rebalance if needed
            if date in rebalance_dates:
                new_weights = optimizer.optimize()['weights']

                # Apply transaction costs
                if weights is not None:
                    turnover = (new_weights - weights).abs().sum()
                    transaction_cost = turnover * (transaction_cost_bps / 10000)
                    portfolio_value *= (1 - transaction_cost)

                weights = new_weights

            # Calculate portfolio return
            if weights is not None:
                daily_returns = returns.loc[date]
                portfolio_return = (weights * daily_returns).sum()
                portfolio_value *= (1 + portfolio_return)
                portfolio_returns.append(portfolio_return)

        # Calculate performance metrics
        portfolio_returns = pd.Series(portfolio_returns, index=dates[:len(portfolio_returns)])

        total_return = (portfolio_value - 100) / 100
        annual_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
        annual_vol = portfolio_returns.std() * np.sqrt(252)
        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0
        max_drawdown = _calculate_max_drawdown(portfolio_returns)

        results.append({
            'Strategy': strategy_name,
            'Total Return': total_return,
            'Annual Return': annual_return,
            'Annual Volatility': annual_vol,
            'Sharpe Ratio': sharpe_ratio,
            'Max Drawdown': max_drawdown,
            'Final Value': portfolio_value
        })

    return pd.DataFrame(results)

def _get_rebalance_dates(dates: pd.DatetimeIndex, frequency: str) -> List[pd.Timestamp]:
    """Get rebalancing dates based on frequency."""
    if frequency == 'monthly':
        return dates[dates.to_series().dt.is_month_end]
    elif frequency == 'quarterly':
        return dates[dates.to_series().dt.is_quarter_end]
    else:
        raise ValueError(f"Unknown frequency: {frequency}")

def _calculate_max_drawdown(returns: pd.Series) -> float:
    """Calculate maximum drawdown."""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min()
```

### 8.2 Example Comparison

```python
# Load historical data (3 years)
returns = pd.read_sql(
    """
    SELECT date, ticker, daily_return
    FROM ohlcv_data
    WHERE region = 'KR'
      AND date >= CURRENT_DATE - INTERVAL '3 years'
    """,
    db.engine
).pivot(index='date', columns='ticker', values='daily_return')

# Define strategies
strategies = {
    'Equal Weight': None,  # Benchmark
    'Mean-Variance': MarkowitzOptimizer(returns),
    'Risk Parity': RiskParityOptimizer(returns),
    'Kelly Criterion': KellyCriterionOptimizer(returns),
    'Hierarchical Risk Parity': HierarchicalRiskParityOptimizer(returns),
    'Minimum Correlation': MinimumCorrelationOptimizer(returns)
}

# Backtest
performance = backtest_optimization_strategies(
    returns=returns,
    strategies=strategies,
    rebalance_frequency='monthly',
    transaction_cost_bps=10.0
)

print("\n" + "="*80)
print("PORTFOLIO OPTIMIZATION STRATEGY COMPARISON")
print("="*80)
print(performance.to_string(index=False))
print("="*80)

# Identify best strategy
best_sharpe = performance.loc[performance['Sharpe Ratio'].idxmax()]
print(f"\n🏆 Best Sharpe Ratio: {best_sharpe['Strategy']} ({best_sharpe['Sharpe Ratio']:.2f})")

best_return = performance.loc[performance['Annual Return'].idxmax()]
print(f"📈 Best Annual Return: {best_return['Strategy']} ({best_return['Annual Return']:.2%})")

best_drawdown = performance.loc[performance['Max Drawdown'].idxmax()]
print(f"🛡️ Lowest Drawdown: {best_drawdown['Strategy']} ({best_drawdown['Max Drawdown']:.2%})")
```

---

## Summary

This cookbook provides comprehensive portfolio optimization recipes covering:

1. **Mean-Variance Optimization**: Classic Markowitz approach with efficient frontier
2. **Risk Parity**: Equal risk contribution across assets
3. **Black-Litterman**: Combining market equilibrium with investor views
4. **Kelly Criterion**: Optimal leverage for multi-asset portfolios
5. **Constraint Handling**: Position limits, sector limits, turnover constraints
6. **Rebalancing**: Time-based, threshold-based, and adaptive strategies
7. **Advanced Methods**: Hierarchical Risk Parity, Minimum Correlation
8. **Performance Comparison**: Backtesting framework for strategy evaluation

### Key Takeaways

- **No single "best" optimizer**: Performance varies by market conditions
- **Constraint handling is critical**: Real-world portfolios require careful constraint design
- **Rebalancing strategy matters**: Frequency and conditions significantly impact returns
- **Transaction costs are non-trivial**: Always include in backtests
- **Robustness over optimality**: Prefer robust solutions to over-optimized portfolios

### Integration with Quant Platform

All optimizers integrate seamlessly with:
- Multi-factor analysis engine (factor scores → expected returns)
- Backtesting framework (strategy evaluation)
- Risk management system (position sizing, stop-loss)
- Database layer (historical data, portfolio tracking)

See `QUANT_PLATFORM_ARCHITECTURE.md` for system integration details.

---

**Next Document**: [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Complete PostgreSQL + TimescaleDB schema
