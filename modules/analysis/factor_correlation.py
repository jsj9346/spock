#!/usr/bin/env python3
"""
FactorCorrelationAnalyzer - Factor Independence and Redundancy Detection

Analyzes relationships between factors to:
1. Identify redundant factors (high correlation)
2. Detect independent factor groups
3. Optimize factor combinations for diversification

Academic Foundation:
- Markowitz (1952) - Portfolio diversification theory (applied to factors)
- Principal Component Analysis (PCA) - Factor dimensionality reduction
- Hierarchical Clustering - Factor grouping methodology

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import date
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg2
from scipy import stats
from scipy.cluster import hierarchy
from scipy.spatial.distance import pdist
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


@dataclass
class CorrelationPair:
    """Pair of factors with correlation coefficient"""
    factor1: str
    factor2: str
    correlation: float
    p_value: float
    is_significant: bool  # True if p_value < 0.05
    num_stocks: int       # Number of common stocks


class FactorCorrelationAnalyzer:
    """
    Factor Correlation Analysis Engine

    Methods:
        pairwise_correlation() - Calculate correlation matrix between all factors
        redundancy_detection() - Identify highly correlated factor pairs
        factor_clustering() - Group factors by similarity
        orthogonalization_suggestion() - Recommend factor combinations

    Usage:
        analyzer = FactorCorrelationAnalyzer()
        corr_matrix = analyzer.pairwise_correlation('2025-10-22', 'KR')
    """

    def __init__(self):
        """Initialize FactorCorrelationAnalyzer"""
        self.conn = None

    def _get_connection(self):
        """Get PostgreSQL connection"""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
        return self.conn

    def pairwise_correlation(
        self,
        analysis_date: str,
        region: str = 'KR',
        method: str = 'spearman'
    ) -> pd.DataFrame:
        """
        Calculate pairwise correlation matrix between all factors

        Correlation Types:
        - spearman: Rank correlation (robust to outliers, preferred)
        - pearson: Linear correlation (sensitive to outliers)

        Args:
            analysis_date: Date to analyze (YYYY-MM-DD)
            region: Market region
            method: Correlation method ('spearman' or 'pearson')

        Returns:
            pd.DataFrame: Correlation matrix (factors x factors)

        Example:
            >>> analyzer = FactorCorrelationAnalyzer()
            >>> corr_matrix = analyzer.pairwise_correlation('2025-10-22', 'KR')
            >>> print(corr_matrix.loc['PE_Ratio', 'PB_Ratio'])
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get all factor names for this date and region
            cursor.execute("""
                SELECT DISTINCT factor_name
                FROM factor_scores
                WHERE date = %s AND region = %s
                ORDER BY factor_name
            """, (analysis_date, region))

            factor_names = [row[0] for row in cursor.fetchall()]

            if len(factor_names) < 2:
                logger.warning(f"Need at least 2 factors for correlation analysis (found {len(factor_names)})")
                return pd.DataFrame()

            # Get factor scores for all factors
            query = """
            SELECT ticker, factor_name, score
            FROM factor_scores
            WHERE date = %s
              AND region = %s
              AND factor_name = ANY(%s)
              AND score IS NOT NULL
            ORDER BY ticker, factor_name;
            """

            cursor.execute(query, (analysis_date, region, factor_names))
            rows = cursor.fetchall()

            # Pivot to wide format (tickers x factors)
            df = pd.DataFrame(rows, columns=['ticker', 'factor_name', 'score'])
            factor_data = df.pivot(index='ticker', columns='factor_name', values='score')

            # Drop tickers with missing factor scores
            factor_data_complete = factor_data.dropna()

            if len(factor_data_complete) < 10:
                logger.warning(f"Only {len(factor_data_complete)} stocks with complete factor scores")

            # Calculate correlation matrix
            if method == 'spearman':
                corr_matrix = factor_data_complete.corr(method='spearman')
            else:
                corr_matrix = factor_data_complete.corr(method='pearson')

            logger.info(
                f"Correlation matrix: {len(factor_names)} factors, "
                f"{len(factor_data_complete)} stocks, "
                f"method: {method}"
            )

            return corr_matrix

        except Exception as e:
            logger.error(f"Correlation calculation failed: {e}")
            raise

        finally:
            cursor.close()

    def redundancy_detection(
        self,
        analysis_date: str,
        region: str = 'KR',
        threshold: float = 0.7
    ) -> List[CorrelationPair]:
        """
        Identify highly correlated factor pairs (redundancy)

        Redundant factors provide little diversification benefit and can be consolidated.

        Redundancy Thresholds:
        - |correlation| > 0.9: Very high redundancy (consider removing one)
        - |correlation| > 0.7: High redundancy (potential consolidation)
        - |correlation| > 0.5: Moderate redundancy (acceptable if complementary)
        - |correlation| < 0.3: Low correlation (independent factors)

        Args:
            analysis_date: Date to analyze (YYYY-MM-DD)
            region: Market region
            threshold: Correlation threshold for redundancy (default: 0.7)

        Returns:
            List[CorrelationPair]: Factor pairs sorted by absolute correlation (descending)

        Example:
            >>> redundant_pairs = analyzer.redundancy_detection('2025-10-22', 'KR', 0.7)
            >>> for pair in redundant_pairs:
            ...     print(f"{pair.factor1} <-> {pair.factor2}: {pair.correlation:.3f}")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get all factor names
            cursor.execute("""
                SELECT DISTINCT factor_name
                FROM factor_scores
                WHERE date = %s AND region = %s
                ORDER BY factor_name
            """, (analysis_date, region))

            factor_names = [row[0] for row in cursor.fetchall()]

            if len(factor_names) < 2:
                return []

            redundant_pairs = []

            # Calculate pairwise correlations
            for i, factor1 in enumerate(factor_names):
                for factor2 in factor_names[i+1:]:
                    # Get scores for both factors
                    query = """
                    SELECT
                        f1.ticker,
                        f1.score AS score1,
                        f2.score AS score2
                    FROM (
                        SELECT ticker, score
                        FROM factor_scores
                        WHERE date = %s AND region = %s AND factor_name = %s AND score IS NOT NULL
                    ) f1
                    INNER JOIN (
                        SELECT ticker, score
                        FROM factor_scores
                        WHERE date = %s AND region = %s AND factor_name = %s AND score IS NOT NULL
                    ) f2 ON f1.ticker = f2.ticker;
                    """

                    cursor.execute(query, (
                        analysis_date, region, factor1,
                        analysis_date, region, factor2
                    ))

                    rows = cursor.fetchall()

                    if len(rows) < 10:
                        continue

                    scores1 = np.array([row[1] for row in rows])
                    scores2 = np.array([row[2] for row in rows])

                    # Spearman rank correlation
                    corr, p_value = stats.spearmanr(scores1, scores2)

                    # Check if exceeds threshold
                    if abs(corr) >= threshold:
                        pair = CorrelationPair(
                            factor1=factor1,
                            factor2=factor2,
                            correlation=float(corr),
                            p_value=float(p_value),
                            is_significant=(p_value < 0.05),
                            num_stocks=len(rows)
                        )
                        redundant_pairs.append(pair)

            # Sort by absolute correlation (descending)
            redundant_pairs.sort(key=lambda x: abs(x.correlation), reverse=True)

            logger.info(
                f"Redundancy detection: {len(redundant_pairs)} pairs above threshold {threshold:.2f}"
            )

            return redundant_pairs

        except Exception as e:
            logger.error(f"Redundancy detection failed: {e}")
            raise

        finally:
            cursor.close()

    def factor_clustering(
        self,
        analysis_date: str,
        region: str = 'KR',
        method: str = 'ward'
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Hierarchical clustering of factors based on correlation

        Groups factors into clusters of similar factors, useful for:
        - Identifying independent factor groups
        - Selecting one representative from each cluster
        - Understanding factor structure

        Clustering Methods:
        - ward: Minimizes within-cluster variance (recommended)
        - average: Average linkage clustering
        - complete: Maximum linkage clustering
        - single: Minimum linkage clustering

        Args:
            analysis_date: Date to analyze (YYYY-MM-DD)
            region: Market region
            method: Clustering linkage method

        Returns:
            Tuple[np.ndarray, List[str]]:
            - linkage_matrix: Hierarchical clustering linkage matrix
            - factor_names: Ordered factor names

        Example:
            >>> linkage, factors = analyzer.factor_clustering('2025-10-22', 'KR')
            >>> from scipy.cluster.hierarchy import dendrogram
            >>> import matplotlib.pyplot as plt
            >>> dendrogram(linkage, labels=factors)
            >>> plt.show()
        """
        # Get correlation matrix
        corr_matrix = self.pairwise_correlation(analysis_date, region, method='spearman')

        if corr_matrix.empty:
            logger.warning("Empty correlation matrix, cannot perform clustering")
            return np.array([]), []

        # Convert correlation to distance (distance = 1 - |correlation|)
        distance_matrix = 1 - np.abs(corr_matrix.values)

        # Hierarchical clustering
        # pdist expects condensed distance matrix (upper triangle)
        condensed_dist = pdist(distance_matrix, metric='correlation')

        linkage_matrix = hierarchy.linkage(condensed_dist, method=method)

        factor_names = corr_matrix.index.tolist()

        logger.info(
            f"Factor clustering: {len(factor_names)} factors, method: {method}"
        )

        return linkage_matrix, factor_names

    def orthogonalization_suggestion(
        self,
        analysis_date: str,
        region: str = 'KR',
        max_correlation: float = 0.5
    ) -> List[str]:
        """
        Suggest orthogonalized factor set (low inter-correlation)

        Strategy:
        1. Calculate pairwise correlations
        2. Identify redundant factor pairs
        3. Select one factor from each redundant pair
        4. Return maximally independent factor set

        Args:
            analysis_date: Date to analyze (YYYY-MM-DD)
            region: Market region
            max_correlation: Maximum allowed correlation between selected factors

        Returns:
            List[str]: Suggested factor names for orthogonalized set

        Example:
            >>> factors = analyzer.orthogonalization_suggestion('2025-10-22', 'KR', 0.5)
            >>> print(f"Orthogonalized factor set: {', '.join(factors)}")
        """
        # Get correlation matrix
        corr_matrix = self.pairwise_correlation(analysis_date, region, method='spearman')

        if corr_matrix.empty:
            return []

        # Greedy algorithm: Select factors one by one
        selected_factors = []
        remaining_factors = corr_matrix.index.tolist()

        while remaining_factors:
            # Start with first remaining factor
            candidate = remaining_factors[0]

            # Check if candidate is independent from all selected factors
            is_independent = True
            for selected in selected_factors:
                correlation = abs(corr_matrix.loc[candidate, selected])
                if correlation > max_correlation:
                    is_independent = False
                    break

            if is_independent:
                selected_factors.append(candidate)

            remaining_factors.remove(candidate)

        logger.info(
            f"Orthogonalization: {len(selected_factors)} independent factors "
            f"(max correlation: {max_correlation:.2f})"
        )

        return selected_factors

    def close(self):
        """Close database connection"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
