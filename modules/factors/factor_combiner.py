#!/usr/bin/env python3
"""
Factor Combination Engine - Multi-Factor Alpha Score Generation

Combines 22 factor scores into composite alpha scores using different weighting methods.

Three Combination Methods:
1. EqualWeightCombiner - Simple arithmetic mean (baseline)
2. CategoryWeightCombiner - Category-weighted average (strategic allocation)
3. OptimizationCombiner - Historical performance-based optimal weights (data-driven)

Usage Example:
    from modules.factors import EqualWeightCombiner, CategoryWeightCombiner

    # Equal weight
    combiner = EqualWeightCombiner()
    alpha_score = combiner.combine(factor_scores)

    # Category weight
    weights = {
        'MOMENTUM': 0.30,
        'VALUE': 0.25,
        'QUALITY': 0.25,
        'LOW_VOLATILITY': 0.15,
        'SIZE': 0.05
    }
    combiner = CategoryWeightCombiner(weights)
    alpha_score = combiner.combine(factor_scores)

Author: Spock Quant Platform - Phase 2 Multi-Factor
"""

import logging
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .factor_base import FactorCategory

logger = logging.getLogger(__name__)

# Default category weights (균등 가중 20% each)
DEFAULT_CATEGORY_WEIGHTS = {
    'MOMENTUM': 0.20,
    'VALUE': 0.20,
    'QUALITY': 0.20,
    'LOW_VOL': 0.20,
    'SIZE': 0.20
}

# Factor name → Category mapping
FACTOR_CATEGORY_MAP = {
    # Momentum factors
    'momentum_12m': FactorCategory.MOMENTUM,
    'rsi_momentum': FactorCategory.MOMENTUM,
    'short_term_momentum': FactorCategory.MOMENTUM,

    # Low-volatility factors
    'volatility': FactorCategory.LOW_VOL,
    'beta': FactorCategory.LOW_VOL,
    'max_drawdown': FactorCategory.LOW_VOL,

    # Value factors
    'pe_ratio': FactorCategory.VALUE,
    'pb_ratio': FactorCategory.VALUE,
    'ev_ebitda': FactorCategory.VALUE,
    'dividend_yield': FactorCategory.VALUE,

    # Quality factors
    'roe': FactorCategory.QUALITY,
    'roa': FactorCategory.QUALITY,
    'operating_margin': FactorCategory.QUALITY,
    'net_margin': FactorCategory.QUALITY,
    'current_ratio': FactorCategory.QUALITY,
    'quick_ratio': FactorCategory.QUALITY,
    'debt_to_equity': FactorCategory.QUALITY,
    'accruals_ratio': FactorCategory.QUALITY,
    'cf_to_ni': FactorCategory.QUALITY,

    # Size factors
    'market_cap': FactorCategory.SIZE,
    'liquidity': FactorCategory.SIZE,
    'float': FactorCategory.SIZE,
}


class FactorCombinerBase(ABC):
    """Abstract base class for factor combination strategies"""

    @abstractmethod
    def combine(self, factor_scores: Dict[str, float]) -> float:
        """
        Combine factor scores into composite alpha score

        Args:
            factor_scores: Dictionary of factor scores
                Example: {'momentum_12m': 75.5, 'value': 60.0, ...}

        Returns:
            Composite alpha score (0-100 range)
        """
        pass

    @abstractmethod
    def get_weights(self, factor_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Return current factor weights

        Args:
            factor_scores: Dictionary of factor scores (for dynamic weight calculation)

        Returns:
            Dictionary of factor weights {factor_name: weight}
        """
        pass

    def _filter_valid_scores(self, factor_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Filter out None and NaN values from factor scores

        Args:
            factor_scores: Raw factor scores (may contain None/NaN)

        Returns:
            Filtered factor scores (valid only)
        """
        return {
            name: score
            for name, score in factor_scores.items()
            if score is not None and not pd.isna(score)
        }


class EqualWeightCombiner(FactorCombinerBase):
    """
    Equal Weight Combiner - Simple arithmetic mean

    All factors receive equal weight (1/N).

    장점: 구현 간단, 해석 용이, 안정적
    단점: 팩터 성과 차이 무시

    Example:
        combiner = EqualWeightCombiner()
        alpha_score = combiner.combine({'momentum': 75, 'value': 60, 'quality': 90})
        # Result: 75.0 (average of 3 scores)
    """

    def __init__(self):
        logger.info("Initialized EqualWeightCombiner")

    def combine(self, factor_scores: Dict[str, float]) -> float:
        """Calculate simple arithmetic mean of factor scores"""
        valid_scores = self._filter_valid_scores(factor_scores)

        if not valid_scores:
            logger.warning("No valid factor scores provided")
            return 50.0  # Neutral score

        composite = sum(valid_scores.values()) / len(valid_scores)

        logger.debug(f"Combined {len(valid_scores)} factors → {composite:.2f}")
        return composite

    def get_weights(self, factor_scores: Dict[str, float]) -> Dict[str, float]:
        """Return equal weights for all factors"""
        valid_scores = self._filter_valid_scores(factor_scores)

        if not valid_scores:
            return {}

        weight = 1.0 / len(valid_scores)
        return {factor: weight for factor in valid_scores.keys()}


class CategoryWeightCombiner(FactorCombinerBase):
    """
    Category Weight Combiner - Category-weighted average

    Factors within same category are averaged, then weighted by category weights.

    장점: 투자 전략 반영 (공격적 vs 방어적), 카테고리 독립성 유지
    단점: 가중치 설정 주관적

    Example:
        weights = {
            'MOMENTUM': 0.30,      # 30% to momentum factors
            'VALUE': 0.25,         # 25% to value factors
            'QUALITY': 0.25,
            'LOW_VOL': 0.15,
            'SIZE': 0.05
        }
        combiner = CategoryWeightCombiner(weights)
        alpha_score = combiner.combine(factor_scores)
    """

    def __init__(self, category_weights: Optional[Dict[str, float]] = None):
        """
        Initialize with category weights

        Args:
            category_weights: Dictionary of category weights
                Keys: 'MOMENTUM', 'VALUE', 'QUALITY', 'LOW_VOL', 'SIZE'
                Values: Weights (must sum to 1.0)
                Default: Equal weights (0.20 each)
        """
        if category_weights is None:
            self.category_weights = DEFAULT_CATEGORY_WEIGHTS.copy()
            logger.info("Using default category weights (0.20 each)")
        else:
            self.category_weights = category_weights
            self._validate_weights()

        logger.info(f"Initialized CategoryWeightCombiner: {self.category_weights}")

    def _validate_weights(self):
        """Validate that weights are non-negative and sum to 1.0"""
        # Check non-negative
        if any(w < 0 for w in self.category_weights.values()):
            raise ValueError("Category weights must be non-negative")

        # Check sum to 1.0 (with tolerance for floating point errors)
        total = sum(self.category_weights.values())
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"Category weights must sum to 1.0 (got {total:.6f})")

        # Check valid categories
        valid_categories = {'MOMENTUM', 'VALUE', 'QUALITY', 'LOW_VOL', 'SIZE'}
        invalid = set(self.category_weights.keys()) - valid_categories
        if invalid:
            raise ValueError(f"Invalid categories: {invalid}")

    def combine(self, factor_scores: Dict[str, float]) -> float:
        """
        Calculate category-weighted average

        Process:
        1. Group factors by category
        2. Calculate average score per category
        3. Weighted sum using category weights
        """
        valid_scores = self._filter_valid_scores(factor_scores)

        if not valid_scores:
            logger.warning("No valid factor scores provided")
            return 50.0  # Neutral score

        # Group scores by category
        category_scores = {}
        for factor_name, score in valid_scores.items():
            if factor_name not in FACTOR_CATEGORY_MAP:
                logger.warning(f"Unknown factor: {factor_name} (skipped)")
                continue

            category = FACTOR_CATEGORY_MAP[factor_name]
            category_name = category.name  # Convert enum to string

            if category_name not in category_scores:
                category_scores[category_name] = []
            category_scores[category_name].append(score)

        # Calculate category averages
        category_avg = {
            cat: sum(scores) / len(scores)
            for cat, scores in category_scores.items()
        }

        # Weighted sum
        composite = 0.0
        total_weight = 0.0

        for category, avg_score in category_avg.items():
            if category in self.category_weights:
                weight = self.category_weights[category]
                composite += avg_score * weight
                total_weight += weight

        # Normalize if not all categories present
        if total_weight > 0 and not np.isclose(total_weight, 1.0):
            composite = composite / total_weight

        logger.debug(f"Category averages: {category_avg}")
        logger.debug(f"Composite score: {composite:.2f}")

        return composite

    def get_weights(self, factor_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Return factor-level weights based on category weights

        Factor weight = (Category weight) / (# factors in category)
        """
        valid_scores = self._filter_valid_scores(factor_scores)

        if not valid_scores:
            return {}

        # Count factors per category
        category_counts = {}
        for factor_name in valid_scores.keys():
            if factor_name not in FACTOR_CATEGORY_MAP:
                continue

            category = FACTOR_CATEGORY_MAP[factor_name].name
            category_counts[category] = category_counts.get(category, 0) + 1

        # Calculate factor weights
        factor_weights = {}
        for factor_name in valid_scores.keys():
            if factor_name not in FACTOR_CATEGORY_MAP:
                continue

            category = FACTOR_CATEGORY_MAP[factor_name].name
            category_weight = self.category_weights.get(category, 0.0)
            count = category_counts.get(category, 1)

            factor_weights[factor_name] = category_weight / count

        # Normalize weights
        total = sum(factor_weights.values())
        if total > 0:
            factor_weights = {k: v/total for k, v in factor_weights.items()}

        return factor_weights


class OptimizationCombiner(FactorCombinerBase):
    """
    Optimization Combiner - Historical performance-based optimal weights

    Uses mean-variance optimization to find optimal factor weights that maximize
    Sharpe ratio (or minimize variance, maximize return) based on historical data.

    장점: 데이터 기반 의사결정, 백테스트 성과 우수
    단점: Overfitting 위험, 시장 환경 변화 시 재최적화 필요

    Example:
        combiner = OptimizationCombiner(db_path="./data/spock_local.db")
        combiner.fit(start_date='2018-01-01', end_date='2023-12-31', objective='max_sharpe')
        alpha_score = combiner.combine(factor_scores)

        # View optimal weights
        weights = combiner.get_optimal_weights()
        for factor, weight in sorted(weights.items(), key=lambda x: -x[1]):
            print(f"{factor}: {weight:.2%}")
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        """
        Initialize optimization combiner

        Args:
            db_path: Path to SQLite database with historical data
        """
        self.db_path = db_path
        self.optimal_weights = None
        self._is_fitted = False

        logger.info(f"Initialized OptimizationCombiner with db_path={db_path}")

    def fit(
        self,
        start_date: str = '2018-01-01',
        end_date: str = '2023-12-31',
        objective: str = 'max_sharpe'
    ):
        """
        Calculate optimal weights from historical factor returns

        Args:
            start_date: Start date for historical data (YYYY-MM-DD)
            end_date: End date for historical data (YYYY-MM-DD)
            objective: Optimization objective
                'max_sharpe' - Maximize Sharpe ratio (default)
                'min_variance' - Minimize portfolio variance
                'max_return' - Maximize expected return

        Raises:
            ValueError: If insufficient data or optimization fails
        """
        from scipy.optimize import minimize

        logger.info(f"Fitting OptimizationCombiner: {start_date} to {end_date}, objective={objective}")

        # TODO: Replace with actual DB query when historical factor data available
        # For now, use equal weights as fallback
        logger.warning("Historical factor data not yet available - using equal weights")

        # Placeholder: Equal weights
        all_factors = list(FACTOR_CATEGORY_MAP.keys())
        self.optimal_weights = {factor: 1.0/len(all_factors) for factor in all_factors}
        self._is_fitted = True

        logger.info(f"Optimization complete: {len(self.optimal_weights)} factors")
        return

        # # Real implementation (uncomment when DB data ready):
        # historical_data = self._fetch_historical_factor_returns(start_date, end_date)
        #
        # if historical_data.empty or len(historical_data) < 12:
        #     raise ValueError(f"Insufficient historical data: {len(historical_data)} months")
        #
        # # Calculate mean returns and covariance matrix
        # mean_returns = historical_data.mean()
        # cov_matrix = historical_data.cov()
        #
        # # Optimization objective functions
        # def sharpe_ratio(weights):
        #     portfolio_return = np.dot(weights, mean_returns)
        #     portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        #     return -portfolio_return / portfolio_std  # Negative for minimization
        #
        # def portfolio_variance(weights):
        #     return np.dot(weights.T, np.dot(cov_matrix, weights))
        #
        # def negative_return(weights):
        #     return -np.dot(weights, mean_returns)
        #
        # # Select objective
        # obj_funcs = {
        #     'max_sharpe': sharpe_ratio,
        #     'min_variance': portfolio_variance,
        #     'max_return': negative_return
        # }
        #
        # if objective not in obj_funcs:
        #     raise ValueError(f"Invalid objective: {objective}")
        #
        # # Constraints and bounds
        # n = len(mean_returns)
        # constraints = [
        #     {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}  # Weights sum to 1
        # ]
        # bounds = [(0, 1) for _ in range(n)]  # Non-negative weights
        #
        # # Initial guess: equal weights
        # x0 = np.ones(n) / n
        #
        # # Optimize
        # result = minimize(
        #     obj_funcs[objective],
        #     x0=x0,
        #     method='SLSQP',
        #     bounds=bounds,
        #     constraints=constraints,
        #     options={'maxiter': 1000}
        # )
        #
        # if not result.success:
        #     raise ValueError(f"Optimization failed: {result.message}")
        #
        # # Store optimal weights
        # self.optimal_weights = dict(zip(mean_returns.index, result.x))
        # self._is_fitted = True
        #
        # logger.info(f"Optimization successful: Sharpe={-result.fun:.3f}")

    def combine(self, factor_scores: Dict[str, float]) -> float:
        """
        Apply optimal weights to factor scores

        Raises:
            ValueError: If fit() not called before combine()
        """
        if not self._is_fitted:
            raise ValueError("Must call fit() before combine()")

        valid_scores = self._filter_valid_scores(factor_scores)

        if not valid_scores:
            logger.warning("No valid factor scores provided")
            return 50.0

        # Weighted sum
        composite = 0.0
        total_weight = 0.0

        for factor, score in valid_scores.items():
            if factor in self.optimal_weights:
                weight = self.optimal_weights[factor]
                composite += score * weight
                total_weight += weight

        # Normalize if some factors missing
        if total_weight > 0 and not np.isclose(total_weight, 1.0):
            composite = composite / total_weight

        return composite

    def get_weights(self, factor_scores: Dict[str, float]) -> Dict[str, float]:
        """Return optimal weights (renormalized for available factors)"""
        if not self._is_fitted:
            raise ValueError("Must call fit() before get_weights()")

        valid_scores = self._filter_valid_scores(factor_scores)

        # Filter weights for available factors only
        available_weights = {
            factor: self.optimal_weights[factor]
            for factor in valid_scores.keys()
            if factor in self.optimal_weights
        }

        # Renormalize
        total = sum(available_weights.values())
        if total > 0:
            available_weights = {k: v/total for k, v in available_weights.items()}

        return available_weights

    def get_optimal_weights(self) -> Dict[str, float]:
        """
        Get raw optimal weights (before renormalization)

        Returns:
            Dictionary of optimal factor weights
        """
        if not self._is_fitted:
            raise ValueError("Must call fit() before get_optimal_weights()")

        return self.optimal_weights.copy()
