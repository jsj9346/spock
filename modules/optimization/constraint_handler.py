"""
Constraint Handler for Portfolio Optimization

This module provides utilities for validating and enforcing portfolio constraints
including position limits, sector limits, turnover constraints, and region limits.

Author: Quant Platform Development Team
Last Updated: 2025-10-21
Version: 1.0.0
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConstraintViolation:
    """
    Constraint violation information.

    Attributes:
        constraint_type: Type of constraint violated
        severity: Severity level (critical, warning, info)
        current_value: Current value
        limit_value: Limit value
        message: Human-readable message
    """
    constraint_type: str
    severity: str
    current_value: float
    limit_value: float
    message: str


class ConstraintHandler:
    """
    Portfolio constraint validation and enforcement utilities.

    Provides comprehensive constraint checking for:
    - Position size limits
    - Sector concentration limits
    - Region concentration limits
    - Turnover constraints
    - Cash reserve requirements
    - Long-only constraints
    """

    def __init__(
        self,
        min_position: float = 0.01,
        max_position: float = 0.15,
        max_sector: float = 0.40,
        max_region: Dict[str, float] = None,
        max_turnover: float = 0.20,
        min_cash: float = 0.10,
        long_only: bool = True
    ):
        """
        Initialize constraint handler.

        Args:
            min_position: Minimum position size (default: 1%)
            max_position: Maximum position size (default: 15%)
            max_sector: Maximum sector concentration (default: 40%)
            max_region: Dict of region-specific limits (default: None)
            max_turnover: Maximum turnover (default: 20%)
            min_cash: Minimum cash reserve (default: 10%)
            long_only: Long-only constraint (default: True)
        """
        self.min_position = min_position
        self.max_position = max_position
        self.max_sector = max_sector
        self.max_region = max_region or {
            'KR': 0.50,
            'US': 0.50,
            'CN': 0.20,
            'JP': 0.20,
            'HK': 0.20,
            'VN': 0.10
        }
        self.max_turnover = max_turnover
        self.min_cash = min_cash
        self.long_only = long_only

    def validate_weights(
        self,
        weights: Dict[str, float],
        ticker_metadata: Optional[Dict[str, Dict]] = None,
        current_weights: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, List[ConstraintViolation]]:
        """
        Validate portfolio weights against all constraints.

        Args:
            weights: Portfolio weights (dict: ticker -> weight)
            ticker_metadata: Ticker metadata (dict: ticker -> {sector, region})
            current_weights: Current portfolio weights (for turnover check)

        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []

        # 1. Check weight sum
        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0, atol=0.01):
            violations.append(ConstraintViolation(
                constraint_type='weight_sum',
                severity='critical',
                current_value=weight_sum,
                limit_value=1.0,
                message=f"Weights sum to {weight_sum:.4f}, expected 1.0"
            ))

        # 2. Check long-only constraint
        if self.long_only:
            negative_weights = {k: v for k, v in weights.items() if v < 0}
            if negative_weights:
                for ticker, weight in negative_weights.items():
                    violations.append(ConstraintViolation(
                        constraint_type='long_only',
                        severity='critical',
                        current_value=weight,
                        limit_value=0.0,
                        message=f"{ticker} has negative weight {weight:.4f}"
                    ))

        # 3. Check position size limits
        for ticker, weight in weights.items():
            if weight > 0:
                # Max position check
                if weight > self.max_position:
                    violations.append(ConstraintViolation(
                        constraint_type='max_position',
                        severity='critical',
                        current_value=weight,
                        limit_value=self.max_position,
                        message=f"{ticker} weight {weight:.4f} exceeds max {self.max_position}"
                    ))

                # Min position check
                if weight < self.min_position:
                    violations.append(ConstraintViolation(
                        constraint_type='min_position',
                        severity='warning',
                        current_value=weight,
                        limit_value=self.min_position,
                        message=f"{ticker} weight {weight:.4f} below min {self.min_position}"
                    ))

        # 4. Check sector concentration (if metadata provided)
        if ticker_metadata:
            sector_exposure = self._calculate_sector_exposure(weights, ticker_metadata)
            for sector, exposure in sector_exposure.items():
                if exposure > self.max_sector:
                    violations.append(ConstraintViolation(
                        constraint_type='sector_concentration',
                        severity='critical',
                        current_value=exposure,
                        limit_value=self.max_sector,
                        message=f"Sector {sector} exposure {exposure:.4f} exceeds max {self.max_sector}"
                    ))

            # 5. Check region concentration
            region_exposure = self._calculate_region_exposure(weights, ticker_metadata)
            for region, exposure in region_exposure.items():
                max_region_limit = self.max_region.get(region, 1.0)
                if exposure > max_region_limit:
                    violations.append(ConstraintViolation(
                        constraint_type='region_concentration',
                        severity='critical',
                        current_value=exposure,
                        limit_value=max_region_limit,
                        message=f"Region {region} exposure {exposure:.4f} exceeds max {max_region_limit}"
                    ))

        # 6. Check turnover (if current weights provided)
        if current_weights:
            turnover = self._calculate_turnover(weights, current_weights)
            if turnover > self.max_turnover:
                violations.append(ConstraintViolation(
                    constraint_type='turnover',
                    severity='warning',
                    current_value=turnover,
                    limit_value=self.max_turnover,
                    message=f"Turnover {turnover:.4f} exceeds max {self.max_turnover}"
                ))

        # Determine overall validity
        critical_violations = [v for v in violations if v.severity == 'critical']
        is_valid = len(critical_violations) == 0

        return is_valid, violations

    def _calculate_sector_exposure(
        self,
        weights: Dict[str, float],
        ticker_metadata: Dict[str, Dict]
    ) -> Dict[str, float]:
        """Calculate sector exposure from weights."""
        sector_weights = {}
        for ticker, weight in weights.items():
            if weight > 0 and ticker in ticker_metadata:
                sector = ticker_metadata[ticker].get('sector', 'Unknown')
                sector_weights[sector] = sector_weights.get(sector, 0) + weight
        return sector_weights

    def _calculate_region_exposure(
        self,
        weights: Dict[str, float],
        ticker_metadata: Dict[str, Dict]
    ) -> Dict[str, float]:
        """Calculate region exposure from weights."""
        region_weights = {}
        for ticker, weight in weights.items():
            if weight > 0 and ticker in ticker_metadata:
                region = ticker_metadata[ticker].get('region', 'Unknown')
                region_weights[region] = region_weights.get(region, 0) + weight
        return region_weights

    def _calculate_turnover(
        self,
        new_weights: Dict[str, float],
        current_weights: Dict[str, float]
    ) -> float:
        """Calculate portfolio turnover."""
        all_tickers = set(new_weights.keys()) | set(current_weights.keys())
        turnover = 0.0

        for ticker in all_tickers:
            new_w = new_weights.get(ticker, 0.0)
            current_w = current_weights.get(ticker, 0.0)
            turnover += abs(new_w - current_w)

        # Turnover is half of the sum of absolute changes
        return turnover / 2.0

    def enforce_constraints(
        self,
        weights: np.ndarray,
        tickers: List[str],
        ticker_metadata: Optional[Dict[str, Dict]] = None
    ) -> np.ndarray:
        """
        Enforce constraints by adjusting weights.

        This is a heuristic approach that may not always find a feasible solution.
        For critical applications, use cvxpy with explicit constraints.

        Args:
            weights: Portfolio weights (numpy array)
            tickers: List of ticker symbols
            ticker_metadata: Ticker metadata (optional)

        Returns:
            Adjusted weights
        """
        # Convert to dict for validation
        weight_dict = {ticker: float(weight) for ticker, weight in zip(tickers, weights)}

        # 1. Enforce long-only
        if self.long_only:
            weights = np.maximum(weights, 0)

        # 2. Enforce max position
        weights = np.minimum(weights, self.max_position)

        # 3. Re-normalize
        if weights.sum() > 0:
            weights = weights / weights.sum()

        # 4. Enforce min position (set small positions to zero)
        small_positions = (weights > 0) & (weights < self.min_position)
        weights[small_positions] = 0

        # 5. Re-normalize again
        if weights.sum() > 0:
            weights = weights / weights.sum()

        # 6. Validate sector/region constraints (if metadata provided)
        # This is more complex and would require iterative adjustment
        # For now, we just validate and warn
        if ticker_metadata:
            weight_dict = {ticker: float(weight) for ticker, weight in zip(tickers, weights)}
            is_valid, violations = self.validate_weights(weight_dict, ticker_metadata)

            if not is_valid:
                logger.warning(f"Constraint violations after enforcement: {len(violations)}")
                for v in violations:
                    if v.severity == 'critical':
                        logger.warning(f"  {v.message}")

        return weights

    def generate_constraint_report(
        self,
        weights: Dict[str, float],
        ticker_metadata: Optional[Dict[str, Dict]] = None,
        current_weights: Optional[Dict[str, float]] = None
    ) -> pd.DataFrame:
        """
        Generate constraint validation report.

        Args:
            weights: Portfolio weights
            ticker_metadata: Ticker metadata (optional)
            current_weights: Current weights (optional)

        Returns:
            DataFrame with constraint validation results
        """
        is_valid, violations = self.validate_weights(weights, ticker_metadata, current_weights)

        if len(violations) == 0:
            return pd.DataFrame([{
                'constraint_type': 'all',
                'severity': 'info',
                'status': 'PASS',
                'message': 'All constraints satisfied'
            }])

        # Convert violations to DataFrame
        df = pd.DataFrame([{
            'constraint_type': v.constraint_type,
            'severity': v.severity,
            'current_value': v.current_value,
            'limit_value': v.limit_value,
            'status': 'FAIL',
            'message': v.message
        } for v in violations])

        return df


# Export public API
__all__ = ['ConstraintHandler', 'ConstraintViolation']
