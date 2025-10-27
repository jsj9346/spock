"""
Portfolio Optimization Module

This module provides portfolio optimization algorithms for the Quant Investment Platform.
Implements multiple optimization methods including Mean-Variance, Risk Parity, Black-Litterman,
and Kelly Criterion for multi-asset allocation.

Optimization Methods:
- Mean-Variance: Markowitz optimization (cvxpy)
- Risk Parity: Equal risk contribution
- Black-Litterman: Bayesian approach combining market equilibrium and investor views
- Kelly Criterion: Geometric growth rate maximization (multi-asset extension)

Core Components:
- PortfolioOptimizer: Abstract base class for all optimizers
- OptimizationConstraints: Portfolio constraint definitions
- OptimizationResult: Standardized result container
- TransactionCostModel: Transaction cost calculator
- ConstraintHandler: Constraint validation utilities

Dependencies:
- cvxpy 1.7.3+: Convex optimization
- PyPortfolioOpt 1.5.6+: Portfolio optimization toolkit
- riskfolio-lib 7.0.1+: Advanced optimization methods

Usage Example:
    from modules.optimization import MeanVarianceOptimizer

    optimizer = MeanVarianceOptimizer()
    result = optimizer.optimize(
        expected_returns=returns,
        cov_matrix=cov,
        target_return=0.15
    )

    print(f"Optimal weights: {result.weights}")
    print(f"Sharpe ratio: {result.sharpe_ratio:.2f}")

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 4 - Skeleton Complete (2025-10-21)
"""

# Import base classes and data structures
from modules.optimization.optimizer_base import (
    OptimizationConstraints,
    OptimizationResult,
    PortfolioOptimizer,
    TransactionCostModel
)

# Import optimizer implementations
from modules.optimization.mean_variance_optimizer import MeanVarianceOptimizer
from modules.optimization.risk_parity_optimizer import RiskParityOptimizer
from modules.optimization.black_litterman_optimizer import BlackLittermanOptimizer
from modules.optimization.kelly_multi_asset import KellyMultiAssetOptimizer

# Import constraint utilities
from modules.optimization.constraint_handler import (
    ConstraintHandler,
    ConstraintViolation
)

__all__ = [
    # Base classes
    'OptimizationConstraints',
    'OptimizationResult',
    'PortfolioOptimizer',
    'TransactionCostModel',
    # Optimizers
    'MeanVarianceOptimizer',
    'RiskParityOptimizer',
    'BlackLittermanOptimizer',
    'KellyMultiAssetOptimizer',
    # Utilities
    'ConstraintHandler',
    'ConstraintViolation',
]

__version__ = '1.0.0'
