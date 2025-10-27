#!/usr/bin/env python3
"""
Rolling IC Calculator
Dynamically calculates Information Coefficient with rolling windows for regime-aware factor weighting.

Tier 2 MVP Features:
1. Rolling IC windows (3-month default, configurable)
2. Dynamic calculation during backtest
3. Absolute IC weighting (factor direction agnostic)

Author: Spock Quant Platform
Date: 2025-10-24
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from scipy.stats import spearmanr
from typing import Dict, List, Optional
from functools import lru_cache
from loguru import logger


class RollingICCalculator:
    """
    Calculates Information Coefficient using rolling windows for adaptive factor weighting

    Key Features:
    - Dynamic IC calculation during backtest (no pre-calculation needed)
    - Rolling windows for regime adaptation
    - Caching for performance optimization
    - Absolute IC weighting (all factors contribute positively)
    """

    def __init__(
        self,
        db_manager,
        window_days: int = 60,
        holding_period: int = 21,
        region: str = 'KR',
        min_stocks: int = 10,
        cache_size: int = 128,
        min_p_value: float = 0.05,
        min_observations: int = 30,
        min_ic_threshold: float = 0.08,
        use_signed_ic: bool = True
    ):
        """
        Initialize Rolling IC Calculator

        Args:
            db_manager: Database manager instance
            window_days: Rolling window size in calendar days (default: 60 for 3-month)
            holding_period: Forward return period in trading days (default: 21)
            region: Market region (default: 'KR')
            min_stocks: Minimum stocks required for IC calculation (default: 10)
            cache_size: LRU cache size for performance (default: 128)
            min_p_value: Maximum p-value for statistical significance (default: 0.05)
            min_observations: Minimum IC observations required (default: 30)
            min_ic_threshold: Minimum |IC| required (default: 0.08)
            use_signed_ic: Use signed IC weighting (exclude negative IC factors) (default: True)
        """
        self.db = db_manager
        self.window_days = window_days
        self.holding_period = holding_period
        self.region = region
        self.min_stocks = min_stocks

        # Quality filter parameters (Phase 2B)
        self.min_p_value = min_p_value
        self.min_observations = min_observations
        self.min_ic_threshold = min_ic_threshold
        self.use_signed_ic = use_signed_ic

        # Setup caching for repeated queries
        self._get_factor_scores_cached = lru_cache(maxsize=cache_size)(self._get_factor_scores)
        self._calculate_forward_returns_cached = lru_cache(maxsize=cache_size)(self._calculate_forward_returns)

    def _get_factor_scores(self, factor_date: date) -> pd.DataFrame:
        """
        Get factor scores for a specific date

        Args:
            factor_date: Date to retrieve factor scores

        Returns:
            DataFrame with columns: ticker, factor_name, score
        """
        query = """
            SELECT
                ticker,
                factor_name,
                score
            FROM factor_scores
            WHERE region = %s
              AND date = %s
            ORDER BY ticker, factor_name
        """

        results = self.db.execute_query(query, (self.region, factor_date))

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['score'] = pd.to_numeric(df['score'], errors='coerce')

        return df.dropna()

    def _calculate_forward_returns(self, base_date: date) -> pd.DataFrame:
        """
        Calculate forward returns for all stocks from a base date

        Args:
            base_date: Starting date for forward return calculation

        Returns:
            DataFrame with columns: ticker, forward_return
        """
        query = """
            WITH base_prices AS (
                SELECT
                    ticker,
                    close as base_close
                FROM ohlcv_data
                WHERE region = %s
                  AND date = %s
            ),
            future_prices AS (
                SELECT
                    ticker,
                    close as future_close,
                    date,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) as rn
                FROM ohlcv_data
                WHERE region = %s
                  AND date > %s
                  AND date <= %s + INTERVAL '30 days'
            ),
            target_prices AS (
                SELECT
                    ticker,
                    future_close
                FROM future_prices
                WHERE rn = %s
            )
            SELECT
                bp.ticker,
                (tp.future_close / bp.base_close) - 1 as forward_return
            FROM base_prices bp
            INNER JOIN target_prices tp ON bp.ticker = tp.ticker
            WHERE bp.base_close > 0
              AND tp.future_close > 0
        """

        results = self.db.execute_query(
            query,
            (self.region, base_date, self.region, base_date, base_date, self.holding_period)
        )

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df['forward_return'] = pd.to_numeric(df['forward_return'], errors='coerce')

        return df[['ticker', 'forward_return']].dropna()

    def calculate_factor_ic(
        self,
        factor_name: str,
        calculation_date: date
    ) -> Dict[str, float]:
        """
        Calculate IC for a single factor on a specific date

        Args:
            factor_name: Name of the factor
            calculation_date: Date to calculate IC

        Returns:
            Dict with keys: ic, p_value, num_stocks, is_significant
        """
        # Get factor scores
        factor_scores = self._get_factor_scores_cached(calculation_date)

        if factor_scores.empty:
            return {
                'ic': 0.0,
                'p_value': 1.0,
                'num_stocks': 0,
                'is_significant': False
            }

        # Filter for specific factor
        factor_data = factor_scores[factor_scores['factor_name'] == factor_name].copy()

        if len(factor_data) < self.min_stocks:
            return {
                'ic': 0.0,
                'p_value': 1.0,
                'num_stocks': len(factor_data),
                'is_significant': False
            }

        # Get forward returns
        forward_returns = self._calculate_forward_returns_cached(calculation_date)

        if forward_returns.empty:
            return {
                'ic': 0.0,
                'p_value': 1.0,
                'num_stocks': 0,
                'is_significant': False
            }

        # Merge factor scores with forward returns
        merged = factor_data.merge(forward_returns, on='ticker', how='inner')

        if len(merged) < self.min_stocks:
            return {
                'ic': 0.0,
                'p_value': 1.0,
                'num_stocks': len(merged),
                'is_significant': False
            }

        # Calculate Spearman correlation
        try:
            ic, p_value = spearmanr(merged['score'], merged['forward_return'])

            ic_value = float(ic) if not np.isnan(ic) else 0.0
            p_value_safe = float(p_value) if not np.isnan(p_value) else 1.0

            # Phase 2B: Quality filter assessment
            passes_quality_filter = (
                p_value_safe < self.min_p_value and
                len(merged) >= self.min_observations and
                abs(ic_value) >= self.min_ic_threshold
            )

            return {
                'ic': ic_value,
                'p_value': p_value_safe,
                'num_stocks': len(merged),
                'is_significant': p_value_safe < 0.05,
                'passes_quality_filter': passes_quality_filter
            }
        except Exception as e:
            logger.warning(f"Error calculating IC for {factor_name} on {calculation_date}: {e}")
            return {
                'ic': 0.0,
                'p_value': 1.0,
                'num_stocks': len(merged),
                'is_significant': False,
                'passes_quality_filter': False
            }

    def get_rolling_ic_weights(
        self,
        factors: List[str],
        target_date: date,
        verbose: bool = False
    ) -> Dict[str, float]:
        """
        Calculate IC weights using rolling window (ending at target_date)

        Args:
            factors: List of factor names
            target_date: End date of rolling window
            verbose: Print detailed IC calculations

        Returns:
            Dict of {factor_name: normalized_weight}
        """
        # Calculate start date of rolling window
        start_date = target_date - timedelta(days=self.window_days)

        # Get all available factor dates in the window
        query = """
            SELECT DISTINCT date
            FROM factor_scores
            WHERE region = %s
              AND date >= %s
              AND date <= %s
            ORDER BY date
        """

        results = self.db.execute_query(query, (self.region, start_date, target_date))

        if not results:
            logger.warning(f"No factor dates found in rolling window {start_date} to {target_date}")
            # Return equal weights if no IC data available
            equal_weight = 1.0 / len(factors) if factors else 0.0
            return {factor: equal_weight for factor in factors}

        window_dates = [row['date'] if isinstance(row, dict) else row[0] for row in results]

        if verbose:
            logger.info(f"\n📊 Rolling IC Window: {start_date} to {target_date} ({len(window_dates)} dates)")

        # Calculate IC for each factor across all dates in window
        factor_ics = {factor: [] for factor in factors}
        factor_ic_results = {factor: [] for factor in factors}  # Store full results for quality filtering

        for calculation_date in window_dates:
            for factor in factors:
                ic_result = self.calculate_factor_ic(factor, calculation_date)
                if ic_result['num_stocks'] >= self.min_stocks:
                    factor_ics[factor].append(ic_result['ic'])
                    factor_ic_results[factor].append(ic_result)

        # Phase 2B: Apply quality filters and signed IC weighting
        ic_weights = {}
        filter_stats = {'passed': [], 'failed_p_value': [], 'failed_observations': [],
                       'failed_ic_threshold': [], 'failed_negative_ic': []}

        for factor in factors:
            if not factor_ics[factor]:
                ic_weights[factor] = 0.0
                filter_stats['failed_observations'].append(factor)
                continue

            avg_ic = np.mean(factor_ics[factor])
            n_obs = len(factor_ics[factor])

            # Quality filter: Check if majority of observations pass quality thresholds
            quality_passed = sum(1 for r in factor_ic_results[factor] if r['passes_quality_filter'])
            quality_rate = quality_passed / n_obs if n_obs > 0 else 0.0

            # Apply filters
            if n_obs < self.min_observations:
                ic_weights[factor] = 0.0
                filter_stats['failed_observations'].append(factor)
            elif abs(avg_ic) < self.min_ic_threshold:
                ic_weights[factor] = 0.0
                filter_stats['failed_ic_threshold'].append(factor)
            elif self.use_signed_ic and avg_ic < 0:
                # Signed IC: Exclude negative predictive factors
                ic_weights[factor] = 0.0
                filter_stats['failed_negative_ic'].append(factor)
            else:
                # Factor passed all filters
                if self.use_signed_ic:
                    ic_weights[factor] = avg_ic  # Use signed IC (positive only)
                else:
                    ic_weights[factor] = abs(avg_ic)  # Use absolute IC (legacy)
                filter_stats['passed'].append(factor)

        # Normalize weights to sum to 1.0
        total_ic = sum(ic_weights.values())

        if total_ic > 0:
            for factor in ic_weights:
                ic_weights[factor] = ic_weights[factor] / total_ic
        else:
            # Fallback to equal weights if all factors filtered out
            equal_weight = 1.0 / len(factors) if factors else 0.0
            ic_weights = {factor: equal_weight for factor in factors}
            if verbose:
                logger.warning(f"⚠️  All factors failed quality filters! Using equal weights fallback.")

        if verbose:
            mode_str = "SIGNED" if self.use_signed_ic else "ABS"
            logger.info(f"📊 Rolling IC Weights ({mode_str}, {self.window_days}-day window):")
            logger.info(f"   Quality Filters: p<{self.min_p_value}, n≥{self.min_observations}, |IC|≥{self.min_ic_threshold}")
            logger.info(f"   Passed: {len(filter_stats['passed'])}, Failed: {len(factors) - len(filter_stats['passed'])}")

            for factor, weight in sorted(ic_weights.items(), key=lambda x: x[1], reverse=True):
                avg_ic = np.mean(factor_ics[factor]) if factor_ics[factor] else 0.0
                n_obs = len(factor_ics[factor])
                status = "✓" if factor in filter_stats['passed'] else "✗"
                logger.info(f"  {status} {factor:28s}: {weight:6.2%} (avg IC={avg_ic:+.4f}, n={n_obs})")

        return ic_weights

    def clear_cache(self):
        """Clear LRU cache (useful between backtests)"""
        self._get_factor_scores_cached.cache_clear()
        self._calculate_forward_returns_cached.cache_clear()

    def get_cache_info(self) -> Dict:
        """Get cache statistics for monitoring"""
        return {
            'factor_scores_cache': self._get_factor_scores_cached.cache_info()._asdict(),
            'forward_returns_cache': self._calculate_forward_returns_cached.cache_info()._asdict()
        }


if __name__ == '__main__':
    """Test Rolling IC Calculator"""
    import sys
    from pathlib import Path

    # Add project root to path
    sys.path.append(str(Path(__file__).parent.parent))

    from modules.db_manager_postgres import PostgresDatabaseManager
    from datetime import date

    # Configure logger
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=''),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    logger.info("=" * 80)
    logger.info("ROLLING IC CALCULATOR TEST")
    logger.info("=" * 80)

    # Initialize
    db = PostgresDatabaseManager()
    calculator = RollingICCalculator(db, window_days=60, holding_period=21, region='KR')

    # Test factors
    factors = ['12M_Momentum', '1M_Momentum', 'PE_Ratio']

    # Test date (rebalance date in 2023)
    test_date = date(2023, 6, 30)

    logger.info(f"\nTest Date: {test_date}")
    logger.info(f"Factors: {factors}")

    # Calculate rolling IC weights
    ic_weights = calculator.get_rolling_ic_weights(factors, test_date, verbose=True)

    # Show cache stats
    cache_info = calculator.get_cache_info()
    logger.info(f"\n📊 Cache Performance:")
    logger.info(f"  Factor Scores: {cache_info['factor_scores_cache']}")
    logger.info(f"  Forward Returns: {cache_info['forward_returns_cache']}")

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)
