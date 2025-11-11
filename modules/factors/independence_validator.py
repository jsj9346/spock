#!/usr/bin/env python3
"""
independence_validator.py - Factor Independence Validation

Purpose:
- Validate factor independence (correlation < 0.5 threshold)
- Test pairwise correlations between all factors
- Analyze within-category independence
- Generate validation reports with recommendations

Design Philosophy:
- Evidence-based: Use actual factor time-series data
- Threshold-based: Flag correlations above configurable threshold
- Category-aware: Test both inter-category and intra-category independence
- Actionable: Provide clear recommendations for correlated factors
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import date, datetime
import logging
import os

from modules.factors.factor_base import FactorCategory

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """
    Result of pairwise factor correlation analysis

    Attributes:
        factor1: First factor name
        factor2: Second factor name
        correlation: Pearson correlation coefficient (-1 to 1)
        p_value: Statistical significance
        sample_size: Number of observations
        category1: Category of first factor
        category2: Category of second factor
        is_independent: Whether correlation meets independence threshold
        threshold: Independence threshold used
    """
    factor1: str
    factor2: str
    correlation: float
    p_value: float
    sample_size: int
    category1: str
    category2: str
    is_independent: bool
    threshold: float

    def __repr__(self) -> str:
        status = "✅ Independent" if self.is_independent else "❌ Correlated"
        return (
            f"{status}: {self.factor1} ↔ {self.factor2} "
            f"(r={self.correlation:.3f}, p={self.p_value:.4f}, n={self.sample_size})"
        )


@dataclass
class IndependenceValidationReport:
    """
    Comprehensive independence validation report

    Attributes:
        validation_date: Date of validation
        universe_size: Number of tickers analyzed
        period: Date range used for correlation analysis
        independence_threshold: Correlation threshold (default: 0.5)
        total_factor_pairs: Total number of factor pairs tested
        independent_pairs: Number of pairs meeting independence threshold
        correlated_pairs: Number of pairs failing independence threshold
        correlations: List of all correlation results
        category_summary: Independence summary by category
        recommendations: Actionable recommendations
    """
    validation_date: datetime
    universe_size: int
    period: Tuple[date, date]
    independence_threshold: float
    total_factor_pairs: int
    independent_pairs: int
    correlated_pairs: int
    correlations: List[CorrelationResult] = field(default_factory=list)
    category_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    @property
    def independence_rate(self) -> float:
        """Calculate percentage of independent pairs"""
        if self.total_factor_pairs == 0:
            return 0.0
        return (self.independent_pairs / self.total_factor_pairs) * 100

    def __repr__(self) -> str:
        return (
            f"Independence Validation Report\n"
            f"{'='*50}\n"
            f"Date: {self.validation_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Period: {self.period[0]} to {self.period[1]}\n"
            f"Universe: {self.universe_size} tickers\n"
            f"Threshold: |r| < {self.independence_threshold}\n"
            f"\n"
            f"Results:\n"
            f"  Total pairs tested: {self.total_factor_pairs}\n"
            f"  Independent pairs: {self.independent_pairs} ({self.independence_rate:.1f}%)\n"
            f"  Correlated pairs: {self.correlated_pairs}\n"
        )


class IndependenceValidator:
    """
    Validator for testing factor independence using correlation analysis

    Usage:
        validator = IndependenceValidator(
            region='KR',
            independence_threshold=0.5,
            min_sample_size=20
        )

        report = validator.validate_independence(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            tickers=['005930', '000660', '035420']
        )

        print(report)
        validator.save_report(report, 'results/independence_report.txt')
    """

    def __init__(
        self,
        region: str = 'KR',
        independence_threshold: float = 0.5,
        min_sample_size: int = 20,
        significance_level: float = 0.05
    ):
        """
        Initialize independence validator

        Args:
            region: Region filter for factors (default: 'KR')
            independence_threshold: Maximum correlation for independence (default: 0.5)
            min_sample_size: Minimum observations required for valid correlation (default: 20)
            significance_level: P-value threshold for statistical significance (default: 0.05)
        """
        self.region = region
        self.independence_threshold = independence_threshold
        self.min_sample_size = min_sample_size
        self.significance_level = significance_level

        # Factor category mapping (will be populated from database)
        self.factor_categories: Dict[str, str] = {}

        logger.info(
            f"IndependenceValidator initialized: "
            f"region={region}, threshold={independence_threshold}, "
            f"min_samples={min_sample_size}"
        )

    def _connect_db(self) -> psycopg2.extensions.connection:
        """Create database connection"""
        return psycopg2.connect(
            dbname="quant_platform",
            user=os.getenv("USER", "13ruce"),
            host="localhost",
            port=5432
        )

    def _load_factor_categories(self, conn: psycopg2.extensions.connection) -> None:
        """
        Load factor category mapping from database

        Args:
            conn: Database connection
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query distinct factors and their categories
            query = """
            SELECT DISTINCT factor_name
            FROM factor_scores
            WHERE region = %s
            ORDER BY factor_name;
            """
            cur.execute(query, (self.region,))
            factors = [row['factor_name'] for row in cur.fetchall()]

        # Map factors to categories based on naming convention
        # Format: "{category}_{factor_name}" (e.g., "Momentum_12M", "Value_PB")
        for factor in factors:
            if '_' in factor:
                category = factor.split('_')[0]
                self.factor_categories[factor] = category
            else:
                # Fallback: try to infer from common patterns
                factor_lower = factor.lower()
                if any(kw in factor_lower for kw in ['momentum', '12m', 'rsi', 'trend']):
                    self.factor_categories[factor] = 'Momentum'
                elif any(kw in factor_lower for kw in ['value', 'pb', 'pe', 'yield']):
                    self.factor_categories[factor] = 'Value'
                elif any(kw in factor_lower for kw in ['quality', 'roe', 'debt']):
                    self.factor_categories[factor] = 'Quality'
                elif any(kw in factor_lower for kw in ['vol', 'volatility', 'beta']):
                    self.factor_categories[factor] = 'Low-Vol'
                elif any(kw in factor_lower for kw in ['size', 'cap', 'liquidity']):
                    self.factor_categories[factor] = 'Size'
                elif any(kw in factor_lower for kw in ['growth', 'revenue', 'earnings']):
                    self.factor_categories[factor] = 'Growth'
                elif any(kw in factor_lower for kw in ['efficiency', 'turnover', 'margin']):
                    self.factor_categories[factor] = 'Efficiency'
                else:
                    self.factor_categories[factor] = 'Unknown'

        logger.info(f"Loaded {len(self.factor_categories)} factor categories")

    def _load_factor_time_series(
        self,
        conn: psycopg2.extensions.connection,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load factor time series data for correlation analysis

        Args:
            conn: Database connection
            start_date: Start date for analysis period
            end_date: End date for analysis period
            tickers: Optional list of tickers to filter (None = all tickers)

        Returns:
            DataFrame with MultiIndex (date, ticker) and columns=factors
        """
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build query
            query = """
            SELECT
                date,
                ticker,
                factor_name,
                percentile
            FROM factor_scores
            WHERE region = %s
              AND date >= %s
              AND date <= %s
            """
            params = [self.region, start_date, end_date]

            if tickers:
                query += " AND ticker = ANY(%s)"
                params.append(tickers)

            query += " ORDER BY date, ticker, factor_name;"

            cur.execute(query, params)
            rows = cur.fetchall()

        if not rows:
            logger.warning(
                f"No factor scores found for region={self.region}, "
                f"period={start_date} to {end_date}"
            )
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(rows)

        # Ensure percentile is numeric (fix object dtype issue)
        df['percentile'] = pd.to_numeric(df['percentile'], errors='coerce')

        # Pivot to wide format: (date, ticker) x factors
        df_pivot = df.pivot_table(
            index=['date', 'ticker'],
            columns='factor_name',
            values='percentile',
            aggfunc='first'  # Handle potential duplicates
        )

        logger.info(
            f"Loaded factor time series: "
            f"{len(df_pivot)} observations, {len(df_pivot.columns)} factors"
        )

        return df_pivot

    def _calculate_pairwise_correlations(
        self,
        factor_data: pd.DataFrame
    ) -> List[CorrelationResult]:
        """
        Calculate pairwise correlations between all factors

        Args:
            factor_data: DataFrame with factors as columns

        Returns:
            List of CorrelationResult objects
        """
        from scipy.stats import pearsonr

        factors = factor_data.columns.tolist()
        correlations = []

        # Calculate pairwise correlations
        for i, factor1 in enumerate(factors):
            for factor2 in factors[i+1:]:  # Avoid duplicates and self-correlation
                # Extract factor values
                data1 = factor_data[factor1].dropna()
                data2 = factor_data[factor2].dropna()

                # Align indices (only use common observations)
                common_idx = data1.index.intersection(data2.index)

                if len(common_idx) < self.min_sample_size:
                    logger.debug(
                        f"Skipping {factor1} ↔ {factor2}: "
                        f"insufficient samples ({len(common_idx)} < {self.min_sample_size})"
                    )
                    continue

                aligned_data1 = data1.loc[common_idx]
                aligned_data2 = data2.loc[common_idx]

                # Calculate Pearson correlation
                try:
                    corr_coef, p_value = pearsonr(aligned_data1, aligned_data2)
                except Exception as e:
                    logger.warning(f"Correlation calculation failed for {factor1} ↔ {factor2}: {e}")
                    continue

                # Check independence
                is_independent = abs(corr_coef) < self.independence_threshold

                # Get categories
                category1 = self.factor_categories.get(factor1, 'Unknown')
                category2 = self.factor_categories.get(factor2, 'Unknown')

                correlations.append(CorrelationResult(
                    factor1=factor1,
                    factor2=factor2,
                    correlation=corr_coef,
                    p_value=p_value,
                    sample_size=len(common_idx),
                    category1=category1,
                    category2=category2,
                    is_independent=is_independent,
                    threshold=self.independence_threshold
                ))

        logger.info(f"Calculated {len(correlations)} pairwise correlations")

        return correlations

    def _generate_recommendations(
        self,
        correlations: List[CorrelationResult]
    ) -> List[str]:
        """
        Generate actionable recommendations based on correlation results

        Args:
            correlations: List of correlation results

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Find highly correlated pairs (|r| > threshold)
        correlated_pairs = [c for c in correlations if not c.is_independent]

        if not correlated_pairs:
            recommendations.append("✅ All factor pairs meet independence threshold.")
            return recommendations

        # Sort by absolute correlation
        correlated_pairs.sort(key=lambda x: abs(x.correlation), reverse=True)

        recommendations.append(
            f"⚠️  Found {len(correlated_pairs)} correlated factor pairs "
            f"(|r| >= {self.independence_threshold})"
        )
        recommendations.append("")

        # List top 5 most correlated pairs
        recommendations.append("Top correlated pairs:")
        for c in correlated_pairs[:5]:
            recommendations.append(
                f"  - {c.factor1} ↔ {c.factor2}: r={c.correlation:.3f} "
                f"({c.category1} / {c.category2})"
            )

        if len(correlated_pairs) > 5:
            recommendations.append(f"  ... and {len(correlated_pairs) - 5} more")

        recommendations.append("")

        # Category-specific recommendations
        intra_category = [c for c in correlated_pairs if c.category1 == c.category2]
        inter_category = [c for c in correlated_pairs if c.category1 != c.category2]

        if intra_category:
            recommendations.append(
                f"📊 Intra-category correlations: {len(intra_category)} pairs"
            )
            recommendations.append(
                "   Recommendation: Consider dropping redundant factors within categories"
            )
            recommendations.append("")

        if inter_category:
            recommendations.append(
                f"📊 Inter-category correlations: {len(inter_category)} pairs"
            )
            recommendations.append(
                "   Recommendation: Review factor weighting in combination strategies"
            )
            recommendations.append("")

        # General recommendations
        recommendations.append("💡 General Recommendations:")
        recommendations.append("  1. Use equal-weight combiner for highly correlated factors")
        recommendations.append("  2. Consider dropping one factor from each correlated pair")
        recommendations.append("  3. Use orthogonalization techniques (e.g., PCA)")
        recommendations.append("  4. Monitor factor correlations over time (regime changes)")

        return recommendations

    def validate_independence(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None
    ) -> IndependenceValidationReport:
        """
        Validate factor independence for given period and universe

        Args:
            start_date: Start date for correlation analysis
            end_date: End date for correlation analysis
            tickers: Optional list of tickers (None = all available)

        Returns:
            IndependenceValidationReport with validation results
        """
        logger.info(
            f"Starting independence validation: "
            f"period={start_date} to {end_date}, universe={'all' if not tickers else len(tickers)} tickers"
        )

        conn = self._connect_db()

        try:
            # Load factor categories
            self._load_factor_categories(conn)

            # Load factor time series
            factor_data = self._load_factor_time_series(conn, start_date, end_date, tickers)

            if factor_data.empty:
                logger.error("No factor data available for validation")
                return IndependenceValidationReport(
                    validation_date=datetime.now(),
                    universe_size=0,
                    period=(start_date, end_date),
                    independence_threshold=self.independence_threshold,
                    total_factor_pairs=0,
                    independent_pairs=0,
                    correlated_pairs=0
                )

            # Calculate pairwise correlations
            correlations = self._calculate_pairwise_correlations(factor_data)

            # Count results
            independent_pairs = sum(1 for c in correlations if c.is_independent)
            correlated_pairs = len(correlations) - independent_pairs

            # Generate category summary
            category_summary = {}
            for category in set(self.factor_categories.values()):
                category_correlations = [
                    c for c in correlations
                    if c.category1 == category and c.category2 == category
                ]
                if category_correlations:
                    category_summary[category] = {
                        'total_pairs': len(category_correlations),
                        'independent_pairs': sum(1 for c in category_correlations if c.is_independent),
                        'correlated_pairs': sum(1 for c in category_correlations if not c.is_independent)
                    }

            # Generate recommendations
            recommendations = self._generate_recommendations(correlations)

            # Get unique tickers
            universe_size = factor_data.index.get_level_values('ticker').nunique()

            report = IndependenceValidationReport(
                validation_date=datetime.now(),
                universe_size=universe_size,
                period=(start_date, end_date),
                independence_threshold=self.independence_threshold,
                total_factor_pairs=len(correlations),
                independent_pairs=independent_pairs,
                correlated_pairs=correlated_pairs,
                correlations=correlations,
                category_summary=category_summary,
                recommendations=recommendations
            )

            logger.info(
                f"Validation complete: {independent_pairs}/{len(correlations)} pairs independent "
                f"({report.independence_rate:.1f}%)"
            )

            return report

        finally:
            conn.close()

    def save_report(
        self,
        report: IndependenceValidationReport,
        filepath: str,
        include_details: bool = True
    ) -> None:
        """
        Save validation report to file

        Args:
            report: Validation report to save
            filepath: Output file path
            include_details: Include detailed correlation results (default: True)
        """
        with open(filepath, 'w') as f:
            # Write summary
            f.write(str(report))
            f.write("\n\n")

            # Write category summary
            if report.category_summary:
                f.write("Category Summary:\n")
                f.write("=" * 50 + "\n")
                for category, stats in report.category_summary.items():
                    independence_rate = (stats['independent_pairs'] / stats['total_pairs']) * 100
                    f.write(
                        f"{category}:\n"
                        f"  Total pairs: {stats['total_pairs']}\n"
                        f"  Independent: {stats['independent_pairs']} ({independence_rate:.1f}%)\n"
                        f"  Correlated: {stats['correlated_pairs']}\n"
                    )
                f.write("\n")

            # Write recommendations
            if report.recommendations:
                f.write("Recommendations:\n")
                f.write("=" * 50 + "\n")
                for rec in report.recommendations:
                    f.write(f"{rec}\n")
                f.write("\n")

            # Write detailed correlations (if requested)
            if include_details and report.correlations:
                f.write("Detailed Correlation Results:\n")
                f.write("=" * 50 + "\n")

                # Group by independence status
                independent = [c for c in report.correlations if c.is_independent]
                correlated = [c for c in report.correlations if not c.is_independent]

                if correlated:
                    f.write(f"\nCorrelated Pairs ({len(correlated)}):\n")
                    f.write("-" * 50 + "\n")
                    for c in sorted(correlated, key=lambda x: abs(x.correlation), reverse=True):
                        f.write(f"{c}\n")

                if independent and len(independent) <= 20:  # Only write if manageable
                    f.write(f"\nIndependent Pairs ({len(independent)}):\n")
                    f.write("-" * 50 + "\n")
                    for c in independent:
                        f.write(f"{c}\n")
                elif independent:
                    f.write(f"\n✅ {len(independent)} pairs meet independence threshold\n")

        logger.info(f"Report saved to {filepath}")


if __name__ == '__main__':
    """Test independence validator"""
    import sys
    sys.path.insert(0, '/Users/13ruce/spock')

    from datetime import date

    print("Testing IndependenceValidator...")

    # Initialize validator
    validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.5,
        min_sample_size=20
    )

    # Validate independence for recent period
    report = validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None  # All available tickers
    )

    # Print report
    print("\n" + str(report))

    # Print recommendations
    if report.recommendations:
        print("\nRecommendations:")
        for rec in report.recommendations:
            print(rec)

    # Save report
    output_path = 'results/independence_validation_report.txt'
    validator.save_report(report, output_path)
    print(f"\n✅ Report saved: {output_path}")
