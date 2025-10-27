#!/usr/bin/env python3
"""
FactorAnalyzer - Quintile Return Analysis and Information Coefficient

Analyzes factor predictive power through:
1. Quintile Analysis - Group stocks by factor score, measure forward returns
2. Information Coefficient (IC) - Spearman rank correlation between factor and returns
3. Factor Turnover - Stability analysis and transaction cost implications

Academic Foundation:
- Fama & French (1992, 1993) - Cross-sectional return analysis methodology
- Grinold & Kahn (2000) - Information Coefficient framework
- Barra (1998) - Quintile analysis for factor validation

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import psycopg2
from scipy import stats
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


@dataclass
class QuintileResult:
    """Results from quintile analysis"""
    quintile: int                # Quintile number (1=lowest score, 5=highest)
    num_stocks: int              # Number of stocks in quintile
    mean_return: float           # Mean forward return
    median_return: float         # Median forward return
    std_dev: float               # Standard deviation of returns
    sharpe_ratio: float          # Annualized Sharpe ratio
    hit_rate: float              # % of stocks with positive returns
    min_return: float            # Minimum return in quintile
    max_return: float            # Maximum return in quintile
    turnover: Optional[float] = None  # Turnover from previous period


@dataclass
class ICResult:
    """Results from Information Coefficient analysis"""
    date: date                   # Analysis date
    ic_value: float              # Spearman rank correlation
    num_stocks: int              # Number of stocks in universe
    p_value: float               # Statistical significance
    is_significant: bool         # True if p_value < 0.05


class FactorAnalyzer:
    """
    Factor Analysis Engine

    Provides comprehensive factor validation and performance analysis tools.

    Methods:
        quintile_analysis() - Divide universe into quintiles, analyze forward returns
        calculate_ic() - Compute Information Coefficient time series
        calculate_ic_stats() - Aggregate IC statistics (mean, IR, t-stat)
        factor_turnover() - Measure quintile stability over time

    Usage:
        analyzer = FactorAnalyzer()
        results = analyzer.quintile_analysis('12M_Momentum', '2024-10-10', 'KR', 21)
    """

    def __init__(self):
        """Initialize FactorAnalyzer"""
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

    def quintile_analysis(
        self,
        factor_name: str,
        analysis_date: str,
        region: str = 'KR',
        holding_period: int = 21,
        num_quintiles: int = 5
    ) -> List[QuintileResult]:
        """
        Quintile Analysis - Divide universe by factor score, measure forward returns

        Methodology:
        1. Retrieve factor scores for all stocks on analysis_date
        2. Divide stocks into quintiles based on factor percentile
        3. Calculate forward returns (holding_period days)
        4. Compute statistics for each quintile

        Args:
            factor_name: Name of factor (e.g., '12M_Momentum', 'PE_Ratio')
            analysis_date: Date to analyze (YYYY-MM-DD format)
            region: Market region (KR, US, JP, CN, HK, VN)
            holding_period: Forward return period in trading days (default: 21 = 1 month)
            num_quintiles: Number of quintiles (default: 5)

        Returns:
            List[QuintileResult]: Quintile statistics ordered from Q1 (lowest) to Q5 (highest)

        Example:
            >>> analyzer = FactorAnalyzer()
            >>> results = analyzer.quintile_analysis('12M_Momentum', '2024-10-10', 'KR', 21)
            >>> print(f"Q5 mean return: {results[4].mean_return:.2%}")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Step 1: Get factor scores and forward returns
            query = """
            WITH factor_data AS (
                SELECT
                    ticker,
                    region,
                    date AS factor_date,
                    score,
                    percentile
                FROM factor_scores
                WHERE factor_name = %s
                  AND date = %s
                  AND region = %s
                  AND score IS NOT NULL
            ),
            forward_returns AS (
                SELECT
                    o1.ticker,
                    o1.region,
                    o1.date AS start_date,
                    o1.close AS start_price,
                    o2.date AS end_date,
                    o2.close AS end_price,
                    ((o2.close - o1.close) / o1.close) AS return_pct
                FROM ohlcv_data o1
                INNER JOIN LATERAL (
                    SELECT date, close
                    FROM ohlcv_data o2
                    WHERE o2.ticker = o1.ticker
                      AND o2.region = o1.region
                      AND o2.date > o1.date
                    ORDER BY o2.date
                    LIMIT 1 OFFSET %s
                ) o2 ON TRUE
                WHERE o1.date = %s
                  AND o1.region = %s
            )
            SELECT
                f.ticker,
                f.score,
                f.percentile,
                r.return_pct
            FROM factor_data f
            INNER JOIN forward_returns r
                ON f.ticker = r.ticker
                AND f.region = r.region
            WHERE r.return_pct IS NOT NULL
            ORDER BY f.percentile;
            """

            # holding_period - 1 because OFFSET is zero-indexed
            cursor.execute(query, (
                factor_name,
                analysis_date,
                region,
                holding_period - 1,
                analysis_date,
                region
            ))

            rows = cursor.fetchall()

            if not rows:
                logger.warning(f"No data found for {factor_name} on {analysis_date} (region: {region})")
                return []

            # Step 2: Create DataFrame
            df = pd.DataFrame(rows, columns=['ticker', 'score', 'percentile', 'return_pct'])

            # Step 3: Assign quintiles based on percentile
            df['quintile'] = pd.qcut(
                df['percentile'],
                q=num_quintiles,
                labels=range(1, num_quintiles + 1),
                duplicates='drop'
            )

            # Step 4: Calculate statistics for each quintile
            results = []
            for q in range(1, num_quintiles + 1):
                quintile_data = df[df['quintile'] == q]['return_pct']

                if len(quintile_data) == 0:
                    continue

                mean_return = float(quintile_data.mean())
                std_dev = float(quintile_data.std())

                # Annualized Sharpe ratio (assuming 252 trading days)
                if std_dev > 0:
                    sharpe = (mean_return / std_dev) * np.sqrt(252 / holding_period)
                else:
                    sharpe = 0.0

                result = QuintileResult(
                    quintile=q,
                    num_stocks=len(quintile_data),
                    mean_return=mean_return,
                    median_return=float(quintile_data.median()),
                    std_dev=std_dev,
                    sharpe_ratio=sharpe,
                    hit_rate=float((quintile_data > 0).sum() / len(quintile_data)),
                    min_return=float(quintile_data.min()),
                    max_return=float(quintile_data.max())
                )

                results.append(result)

            logger.info(
                f"{factor_name} quintile analysis: {len(df)} stocks, "
                f"Q1 return: {results[0].mean_return:.2%}, "
                f"Q5 return: {results[-1].mean_return:.2%}"
            )

            return results

        except Exception as e:
            logger.error(f"Quintile analysis failed for {factor_name}: {e}")
            raise

        finally:
            cursor.close()

    def calculate_ic(
        self,
        factor_name: str,
        start_date: str,
        end_date: str,
        region: str = 'KR',
        holding_period: int = 21
    ) -> List[ICResult]:
        """
        Calculate Information Coefficient (IC) time series

        IC = Spearman rank correlation between factor scores and forward returns

        Interpretation:
        - IC > 0.05: Strong predictive power
        - IC > 0.03: Moderate predictive power
        - IC > 0.00: Weak/marginal predictive power
        - IC < 0.00: Negative relationship (contrarian signal)

        Args:
            factor_name: Name of factor
            start_date: Start date for IC calculation (YYYY-MM-DD)
            end_date: End date for IC calculation (YYYY-MM-DD)
            region: Market region
            holding_period: Forward return period in trading days

        Returns:
            List[ICResult]: IC values for each date

        Example:
            >>> ic_series = analyzer.calculate_ic('PE_Ratio', '2024-10-10', '2025-10-20', 'KR', 21)
            >>> print(f"Mean IC: {np.mean([ic.ic_value for ic in ic_series]):.4f}")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get all dates with factor scores in range
            cursor.execute("""
                SELECT DISTINCT date
                FROM factor_scores
                WHERE factor_name = %s
                  AND date BETWEEN %s AND %s
                  AND region = %s
                ORDER BY date
            """, (factor_name, start_date, end_date, region))

            dates = [row[0] for row in cursor.fetchall()]

            if not dates:
                logger.warning(f"No factor scores found for {factor_name} between {start_date} and {end_date}")
                return []

            ic_results = []

            for analysis_date in dates:
                # Get factor scores and forward returns for this date
                query = """
                WITH factor_data AS (
                    SELECT
                        ticker,
                        score
                    FROM factor_scores
                    WHERE factor_name = %s
                      AND date = %s
                      AND region = %s
                      AND score IS NOT NULL
                ),
                forward_returns AS (
                    SELECT
                        o1.ticker,
                        ((o2.close - o1.close) / o1.close) AS return_pct
                    FROM ohlcv_data o1
                    INNER JOIN LATERAL (
                        SELECT close
                        FROM ohlcv_data o2
                        WHERE o2.ticker = o1.ticker
                          AND o2.region = o1.region
                          AND o2.date > o1.date
                        ORDER BY o2.date
                        LIMIT 1 OFFSET %s
                    ) o2 ON TRUE
                    WHERE o1.date = %s
                      AND o1.region = %s
                )
                SELECT
                    f.ticker,
                    f.score,
                    r.return_pct
                FROM factor_data f
                INNER JOIN forward_returns r ON f.ticker = r.ticker
                WHERE r.return_pct IS NOT NULL;
                """

                cursor.execute(query, (
                    factor_name,
                    analysis_date,
                    region,
                    holding_period - 1,
                    analysis_date,
                    region
                ))

                rows = cursor.fetchall()

                if len(rows) < 10:  # Need minimum stocks for meaningful correlation
                    continue

                # Calculate Spearman rank correlation
                scores = np.array([row[1] for row in rows])
                returns = np.array([row[2] for row in rows])

                ic_value, p_value = stats.spearmanr(scores, returns)

                ic_result = ICResult(
                    date=analysis_date,
                    ic_value=float(ic_value),
                    num_stocks=len(rows),
                    p_value=float(p_value),
                    is_significant=(p_value < 0.05)
                )

                ic_results.append(ic_result)

            logger.info(
                f"{factor_name} IC calculation: {len(ic_results)} dates, "
                f"mean IC: {np.mean([ic.ic_value for ic in ic_results]):.4f}"
            )

            return ic_results

        except Exception as e:
            logger.error(f"IC calculation failed for {factor_name}: {e}")
            raise

        finally:
            cursor.close()

    def calculate_ic_stats(self, ic_results: List[ICResult]) -> Dict[str, float]:
        """
        Calculate aggregate IC statistics

        Args:
            ic_results: List of ICResult from calculate_ic()

        Returns:
            Dict with keys:
            - mean_ic: Average IC across all dates
            - std_ic: Standard deviation of IC
            - ic_ir: IC Information Ratio (mean_ic / std_ic)
            - t_stat: T-statistic for mean IC
            - p_value: P-value for t-test (H0: mean_ic = 0)
            - pct_significant: % of dates with significant IC (p < 0.05)
            - pct_positive: % of dates with positive IC

        Example:
            >>> ic_series = analyzer.calculate_ic('12M_Momentum', '2024-10-10', '2025-10-20', 'KR')
            >>> stats = analyzer.calculate_ic_stats(ic_series)
            >>> print(f"IC IR: {stats['ic_ir']:.2f}")
        """
        if not ic_results:
            return {
                'mean_ic': 0.0,
                'std_ic': 0.0,
                'ic_ir': 0.0,
                't_stat': 0.0,
                'p_value': 1.0,
                'pct_significant': 0.0,
                'pct_positive': 0.0
            }

        ic_values = np.array([ic.ic_value for ic in ic_results])

        mean_ic = float(np.mean(ic_values))
        std_ic = float(np.std(ic_values))

        # IC Information Ratio
        ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0

        # T-test for mean IC (H0: mean = 0)
        t_stat, p_value = stats.ttest_1samp(ic_values, 0.0)

        # Percentage metrics
        pct_significant = sum(1 for ic in ic_results if ic.is_significant) / len(ic_results)
        pct_positive = sum(1 for ic in ic_results if ic.ic_value > 0) / len(ic_results)

        return {
            'mean_ic': mean_ic,
            'std_ic': std_ic,
            'ic_ir': float(ic_ir),
            't_stat': float(t_stat),
            'p_value': float(p_value),
            'pct_significant': float(pct_significant),
            'pct_positive': float(pct_positive)
        }

    def factor_turnover(
        self,
        factor_name: str,
        date1: str,
        date2: str,
        region: str = 'KR'
    ) -> float:
        """
        Calculate factor turnover between two dates

        Turnover = % of stocks that changed quintile between date1 and date2

        High turnover → High transaction costs, less stable factor
        Low turnover → Lower costs, more stable factor

        Args:
            factor_name: Name of factor
            date1: First date (YYYY-MM-DD)
            date2: Second date (YYYY-MM-DD)
            region: Market region

        Returns:
            float: Turnover rate (0.0 to 1.0)

        Example:
            >>> turnover = analyzer.factor_turnover('PE_Ratio', '2024-10-10', '2024-11-10', 'KR')
            >>> print(f"Monthly turnover: {turnover:.1%}")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get factor scores for both dates
            query = """
            WITH scores1 AS (
                SELECT ticker, percentile
                FROM factor_scores
                WHERE factor_name = %s AND date = %s AND region = %s
            ),
            scores2 AS (
                SELECT ticker, percentile
                FROM factor_scores
                WHERE factor_name = %s AND date = %s AND region = %s
            )
            SELECT
                s1.ticker,
                s1.percentile AS percentile1,
                s2.percentile AS percentile2
            FROM scores1 s1
            INNER JOIN scores2 s2 ON s1.ticker = s2.ticker;
            """

            cursor.execute(query, (
                factor_name, date1, region,
                factor_name, date2, region
            ))

            rows = cursor.fetchall()

            if not rows:
                logger.warning(f"No overlapping stocks for {factor_name} between {date1} and {date2}")
                return 0.0

            # Assign quintiles
            df = pd.DataFrame(rows, columns=['ticker', 'percentile1', 'percentile2'])

            df['quintile1'] = pd.qcut(df['percentile1'], q=5, labels=[1, 2, 3, 4, 5], duplicates='drop')
            df['quintile2'] = pd.qcut(df['percentile2'], q=5, labels=[1, 2, 3, 4, 5], duplicates='drop')

            # Calculate turnover (% of stocks that changed quintile)
            turnover = float((df['quintile1'] != df['quintile2']).sum() / len(df))

            logger.info(
                f"{factor_name} turnover from {date1} to {date2}: {turnover:.1%} "
                f"({len(df)} stocks)"
            )

            return turnover

        except Exception as e:
            logger.error(f"Turnover calculation failed: {e}")
            raise

        finally:
            cursor.close()

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
