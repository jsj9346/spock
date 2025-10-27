#!/usr/bin/env python3
"""
Factor Optimizer - Orthogonal Factor Selection
Identifies and filters factors based on correlation thresholds
to maximize diversification in multi-factor portfolios.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FactorCorrelationResult:
    """Results from factor correlation analysis"""
    correlation_matrix: pd.DataFrame
    redundant_pairs: List[Tuple[str, str, float]]
    orthogonal_factors: List[str]
    max_correlation_threshold: float


class FactorOptimizer:
    """
    Optimizes factor selection by identifying orthogonal factors
    and removing redundant/highly-correlated factor pairs.
    """

    def __init__(
        self,
        db_manager,
        region: str = 'KR',
        max_correlation: float = 0.5,
        perfect_correlation_threshold: float = 0.95
    ):
        """
        Initialize FactorOptimizer

        Args:
            db_manager: Database manager instance
            region: Market region (KR, US, etc.)
            max_correlation: Maximum allowed pairwise correlation (default 0.5)
            perfect_correlation_threshold: Threshold for "perfect" correlation (default 0.95)
        """
        self.db = db_manager
        self.region = region
        self.max_correlation = max_correlation
        self.perfect_threshold = perfect_correlation_threshold

    def get_factor_scores(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieve factor scores from database

        Args:
            date: Specific date (YYYY-MM-DD), or None for latest

        Returns:
            DataFrame with columns [ticker, factor_name, score]
        """
        if date is None:
            # Get latest date
            query = """
                SELECT MAX(date) as latest_date
                FROM factor_scores
                WHERE region = %s
            """
            result = self.db.execute_query(query, (self.region,))
            date = result[0]['latest_date'].strftime('%Y-%m-%d')
            logger.info(f"Using latest date: {date}")

        # Retrieve factor scores
        query = """
            SELECT ticker, factor_name, score
            FROM factor_scores
            WHERE region = %s AND date = %s
            ORDER BY ticker, factor_name
        """

        df = pd.DataFrame(self.db.execute_query(query, (self.region, date)))
        logger.info(f"Retrieved {len(df)} factor scores for {date}")

        return df

    def calculate_correlation_matrix(
        self,
        factor_scores: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate pairwise Spearman correlation matrix for factors

        Args:
            factor_scores: DataFrame with columns [ticker, factor_name, score]

        Returns:
            Correlation matrix (factors x factors)
        """
        # Pivot to wide format (tickers x factors)
        pivot_df = factor_scores.pivot(
            index='ticker',
            columns='factor_name',
            values='score'
        )

        # Calculate Spearman correlation
        corr_matrix = pivot_df.corr(method='spearman')

        logger.info(f"Calculated correlation matrix for {len(corr_matrix)} factors")

        return corr_matrix

    def find_redundant_pairs(
        self,
        corr_matrix: pd.DataFrame
    ) -> List[Tuple[str, str, float]]:
        """
        Identify redundant factor pairs based on correlation thresholds

        Args:
            corr_matrix: Correlation matrix (factors x factors)

        Returns:
            List of (factor1, factor2, correlation) tuples
        """
        redundant_pairs = []
        factors = corr_matrix.columns.tolist()

        for i in range(len(factors)):
            for j in range(i + 1, len(factors)):
                factor1 = factors[i]
                factor2 = factors[j]
                corr = abs(corr_matrix.loc[factor1, factor2])

                # Check if correlation exceeds threshold
                if corr >= self.max_correlation:
                    redundant_pairs.append((factor1, factor2, corr))

        # Sort by correlation (highest first)
        redundant_pairs.sort(key=lambda x: x[2], reverse=True)

        logger.info(f"Found {len(redundant_pairs)} redundant pairs (|r| >= {self.max_correlation})")

        return redundant_pairs

    def select_orthogonal_factors(
        self,
        corr_matrix: pd.DataFrame,
        ic_weights: Optional[Dict[str, float]] = None
    ) -> List[str]:
        """
        Select orthogonal factors using greedy algorithm

        Algorithm:
        1. Start with highest IC factor (if IC weights provided)
        2. Add factors with max |correlation| < threshold
        3. Prioritize by IC weight

        Args:
            corr_matrix: Correlation matrix (factors x factors)
            ic_weights: Optional dict of {factor_name: IC} for prioritization

        Returns:
            List of orthogonal factor names
        """
        factors = corr_matrix.columns.tolist()

        # Sort factors by IC weight (if provided) or alphabetically
        if ic_weights:
            factors = sorted(
                factors,
                key=lambda f: abs(ic_weights.get(f, 0)),
                reverse=True
            )
            logger.info("Prioritizing factors by IC weight")

        selected_factors = []

        for factor in factors:
            # Check correlation with already-selected factors
            is_orthogonal = True

            for selected in selected_factors:
                corr = abs(corr_matrix.loc[factor, selected])

                if corr >= self.max_correlation:
                    is_orthogonal = False
                    logger.debug(f"Skipping {factor}: corr({factor}, {selected}) = {corr:.3f}")
                    break

            if is_orthogonal:
                selected_factors.append(factor)
                logger.info(f"Selected orthogonal factor: {factor}")

        logger.info(f"Selected {len(selected_factors)}/{len(factors)} orthogonal factors")

        return selected_factors

    def analyze_factors(
        self,
        date: Optional[str] = None,
        ic_weights: Optional[Dict[str, float]] = None
    ) -> FactorCorrelationResult:
        """
        Complete factor analysis pipeline

        Args:
            date: Specific date (YYYY-MM-DD), or None for latest
            ic_weights: Optional dict of {factor_name: IC} for prioritization

        Returns:
            FactorCorrelationResult with analysis results
        """
        logger.info("=== Factor Correlation Analysis ===")

        # Get factor scores
        factor_scores = self.get_factor_scores(date)

        # Calculate correlation matrix
        corr_matrix = self.calculate_correlation_matrix(factor_scores)

        # Find redundant pairs
        redundant_pairs = self.find_redundant_pairs(corr_matrix)

        # Select orthogonal factors
        orthogonal_factors = self.select_orthogonal_factors(corr_matrix, ic_weights)

        result = FactorCorrelationResult(
            correlation_matrix=corr_matrix,
            redundant_pairs=redundant_pairs,
            orthogonal_factors=orthogonal_factors,
            max_correlation_threshold=self.max_correlation
        )

        # Log summary
        self._log_summary(result)

        return result

    def _log_summary(self, result: FactorCorrelationResult):
        """Log analysis summary"""
        logger.info("\n" + "=" * 60)
        logger.info("FACTOR OPTIMIZATION SUMMARY")
        logger.info("=" * 60)

        # Perfect correlations
        perfect_pairs = [p for p in result.redundant_pairs if p[2] >= self.perfect_threshold]
        if perfect_pairs:
            logger.warning(f"\n🚨 PERFECT REDUNDANCY (|r| >= {self.perfect_threshold}):")
            for f1, f2, corr in perfect_pairs:
                logger.warning(f"  • {f1} ≡ {f2} (r={corr:.4f})")

        # High correlations
        high_pairs = [p for p in result.redundant_pairs if p[2] < self.perfect_threshold]
        if high_pairs:
            logger.warning(f"\n⚠️ HIGH REDUNDANCY ({self.max_correlation} <= |r| < {self.perfect_threshold}):")
            for f1, f2, corr in high_pairs:
                logger.warning(f"  • {f1} <-> {f2} (r={corr:.4f})")

        # Orthogonal factors
        logger.info(f"\n✅ ORTHOGONAL FACTORS (max |r| < {self.max_correlation}):")
        for factor in result.orthogonal_factors:
            logger.info(f"  • {factor}")

        logger.info(f"\n📊 STATISTICS:")
        logger.info(f"  Total factors: {len(result.correlation_matrix)}")
        logger.info(f"  Redundant pairs: {len(result.redundant_pairs)}")
        logger.info(f"  Orthogonal factors: {len(result.orthogonal_factors)}")
        logger.info(f"  Reduction: {len(result.correlation_matrix) - len(result.orthogonal_factors)} factors removed")
        logger.info("=" * 60 + "\n")

    def get_average_ic_weights(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_observations: int = 100
    ) -> Dict[str, float]:
        """
        Calculate average IC weights from ic_time_series table

        Args:
            start_date: Start date (YYYY-MM-DD), None for all history
            end_date: End date (YYYY-MM-DD), None for all history
            min_observations: Minimum number of observations required

        Returns:
            Dict of {factor_name: average_ic}
        """
        query = """
            SELECT
                factor_name,
                AVG(ic) as avg_ic,
                COUNT(*) as num_obs
            FROM ic_time_series
            WHERE region = %s
        """
        params = [self.region]

        if start_date:
            query += " AND date >= %s"
            params.append(start_date)

        if end_date:
            query += " AND date <= %s"
            params.append(end_date)

        query += """
            GROUP BY factor_name
            HAVING COUNT(*) >= %s
            ORDER BY ABS(AVG(ic)) DESC
        """
        params.append(min_observations)

        results = self.db.execute_query(query, tuple(params))

        ic_weights = {
            row['factor_name']: float(row['avg_ic'])
            for row in results
        }

        logger.info(f"Retrieved IC weights for {len(ic_weights)} factors")
        for factor, ic in sorted(ic_weights.items(), key=lambda x: abs(x[1]), reverse=True):
            logger.info(f"  {factor}: {ic:+.4f}")

        return ic_weights


if __name__ == '__main__':
    # Example usage
    import sys
    sys.path.append('/Users/13ruce/spock')
    from modules.db_manager_postgres import PostgresDBManager

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Initialize
    db = PostgresDBManager()
    optimizer = FactorOptimizer(db, region='KR', max_correlation=0.5)

    # Get IC weights
    ic_weights = optimizer.get_average_ic_weights()

    # Analyze factors
    result = optimizer.analyze_factors(ic_weights=ic_weights)

    # Print recommended factors
    print("\n" + "=" * 60)
    print("RECOMMENDED ORTHOGONAL FACTORS FOR BACKTESTING:")
    print("=" * 60)
    for factor in result.orthogonal_factors:
        ic = ic_weights.get(factor, 0.0)
        print(f"  • {factor:30s} (avg IC: {ic:+.4f})")
    print("=" * 60)
