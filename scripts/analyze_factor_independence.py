#!/usr/bin/env python3
"""
Factor Independence Analysis Script

Analyzes factor correlations and redundancy across multiple dates to:
1. Calculate correlation matrices between all factors
2. Identify redundant factor pairs (high correlation)
3. Suggest orthogonalized factor set (max inter-correlation < 0.5)
4. Perform hierarchical clustering

Usage:
    # Analyze specific dates
    python3 scripts/analyze_factor_independence.py \
      --dates 2024-10-10,2025-03-01,2025-09-18 \
      --region KR

    # Analyze latest date only
    python3 scripts/analyze_factor_independence.py \
      --region KR \
      --latest

    # Save correlation matrices to CSV
    python3 scripts/analyze_factor_independence.py \
      --region KR \
      --output-dir analysis/correlations/

Author: Spock Quant Platform - Week 4 Multi-Factor Analysis
Date: 2025-10-24
"""

import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from loguru import logger

from modules.analysis.factor_correlation import FactorCorrelationAnalyzer
from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def get_latest_factor_date(db: PostgresDatabaseManager, region: str) -> str:
    """Get the most recent date with factor scores"""
    query = """
        SELECT MAX(date) as latest_date
        FROM factor_scores
        WHERE region = %s
    """
    result = db.execute_query(query, (region,))
    if result and result[0]['latest_date']:
        return str(result[0]['latest_date'])
    return None


def print_correlation_matrix(corr_matrix: pd.DataFrame, date: str):
    """Pretty print correlation matrix"""
    logger.info(f"\n{'=' * 80}")
    logger.info(f"CORRELATION MATRIX - {date}")
    logger.info('=' * 80)

    # Format correlation matrix for display
    logger.info("\nSpearman Rank Correlation:")
    logger.info(corr_matrix.to_string(float_format=lambda x: f"{x:+.3f}"))

    # Summary statistics
    logger.info("\n" + "-" * 80)
    logger.info("CORRELATION SUMMARY")
    logger.info("-" * 80)

    # Get upper triangle (excluding diagonal)
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
    upper_triangle = corr_matrix.where(mask)
    correlations = upper_triangle.stack()

    logger.info(f"Total factor pairs: {len(correlations)}")
    logger.info(f"Average |correlation|: {abs(correlations).mean():.3f}")
    logger.info(f"Max |correlation|: {abs(correlations).max():.3f}")
    logger.info(f"Min |correlation|: {abs(correlations).min():.3f}")
    logger.info(f"")
    logger.info(f"Highly correlated pairs (|r| > 0.7): {(abs(correlations) > 0.7).sum()}")
    logger.info(f"Moderately correlated pairs (|r| > 0.5): {(abs(correlations) > 0.5).sum()}")
    logger.info(f"Weakly correlated pairs (|r| < 0.3): {(abs(correlations) < 0.3).sum()}")


def print_redundancy_report(redundant_pairs, threshold: float):
    """Print redundancy detection results"""
    logger.info(f"\n{'=' * 80}")
    logger.info(f"REDUNDANCY DETECTION (threshold: {threshold:.2f})")
    logger.info('=' * 80)

    if not redundant_pairs:
        logger.info("✅ No redundant factor pairs found!")
        logger.info("All factors are sufficiently independent.")
        return

    logger.info(f"\n⚠️  Found {len(redundant_pairs)} redundant factor pairs:\n")

    for i, pair in enumerate(redundant_pairs, 1):
        sig_marker = "✓" if pair.is_significant else "✗"
        logger.info(
            f"{i}. {pair.factor1:25s} <-> {pair.factor2:25s}: "
            f"r={pair.correlation:+.3f} (p={pair.p_value:.4f}) [{pair.num_stocks:,} stocks] {sig_marker}"
        )

    # Categorize by correlation strength
    very_high = [p for p in redundant_pairs if abs(p.correlation) > 0.9]
    high = [p for p in redundant_pairs if 0.7 <= abs(p.correlation) <= 0.9]

    logger.info(f"\n" + "-" * 80)
    logger.info("REDUNDANCY CATEGORIES")
    logger.info("-" * 80)
    logger.info(f"Very High (|r| > 0.9): {len(very_high)} pairs - Consider removing one factor")
    logger.info(f"High (0.7 < |r| < 0.9): {len(high)} pairs - Potential consolidation")

    if very_high:
        logger.info("\n🚨 CRITICAL REDUNDANCY - Very High Correlation (|r| > 0.9):")
        for pair in very_high:
            logger.info(f"  • {pair.factor1} <-> {pair.factor2}: r={pair.correlation:+.3f}")


def print_orthogonalization_suggestion(orthogonal_factors: List[str], max_corr: float):
    """Print orthogonalized factor set recommendation"""
    logger.info(f"\n{'=' * 80}")
    logger.info(f"ORTHOGONALIZED FACTOR SET (max |r| < {max_corr:.2f})")
    logger.info('=' * 80)

    logger.info(f"\n✅ Recommended {len(orthogonal_factors)} independent factors:\n")
    for i, factor in enumerate(orthogonal_factors, 1):
        logger.info(f"  {i}. {factor}")

    logger.info(f"\n💡 These factors have maximum pairwise correlation < {max_corr:.2f}")
    logger.info("   Use these for multi-factor portfolio construction to maximize diversification.")


def analyze_date(
    analyzer: FactorCorrelationAnalyzer,
    analysis_date: str,
    region: str,
    output_dir: str = None
) -> Dict:
    """
    Run complete correlation analysis for a single date

    Returns:
        Dict with analysis results
    """
    logger.info(f"\n{'#' * 80}")
    logger.info(f"ANALYZING DATE: {analysis_date}")
    logger.info('#' * 80)

    results = {
        'date': analysis_date,
        'region': region
    }

    # 1. Pairwise Correlation Matrix
    logger.info("\n[1/4] Calculating pairwise correlation matrix...")
    corr_matrix = analyzer.pairwise_correlation(analysis_date, region, method='spearman')

    if corr_matrix.empty:
        logger.warning(f"❌ No factor data found for {analysis_date}")
        return results

    print_correlation_matrix(corr_matrix, analysis_date)
    results['correlation_matrix'] = corr_matrix.to_dict()

    # Save to CSV if output directory specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, f"correlation_matrix_{analysis_date}.csv")
        corr_matrix.to_csv(csv_path)
        logger.info(f"\n💾 Correlation matrix saved: {csv_path}")

    # 2. Redundancy Detection
    logger.info("\n[2/4] Detecting redundant factor pairs...")
    redundant_pairs = analyzer.redundancy_detection(analysis_date, region, threshold=0.7)
    print_redundancy_report(redundant_pairs, 0.7)

    results['redundant_pairs'] = [
        {
            'factor1': p.factor1,
            'factor2': p.factor2,
            'correlation': p.correlation,
            'p_value': p.p_value,
            'is_significant': p.is_significant,
            'num_stocks': p.num_stocks
        }
        for p in redundant_pairs
    ]

    # 3. Orthogonalization Suggestion
    logger.info("\n[3/4] Suggesting orthogonalized factor set...")
    orthogonal_factors = analyzer.orthogonalization_suggestion(
        analysis_date, region, max_correlation=0.5
    )
    print_orthogonalization_suggestion(orthogonal_factors, 0.5)
    results['orthogonal_factors'] = orthogonal_factors

    # 4. Hierarchical Clustering
    logger.info("\n[4/4] Performing hierarchical clustering...")
    linkage_matrix, factor_names = analyzer.factor_clustering(
        analysis_date, region, method='ward'
    )

    if len(factor_names) > 0:
        logger.info(f"✅ Clustering complete: {len(factor_names)} factors")
        logger.info("   (Use visualize_factor_correlation.py to generate dendrogram)")

        results['clustering'] = {
            'linkage_matrix': linkage_matrix.tolist(),
            'factor_names': factor_names
        }

    return results


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description='Analyze factor independence and correlations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze specific dates
  python3 scripts/analyze_factor_independence.py \
    --dates 2024-10-10,2025-03-01,2025-09-18 \
    --region KR

  # Analyze latest date
  python3 scripts/analyze_factor_independence.py --region KR --latest

  # Save correlation matrices
  python3 scripts/analyze_factor_independence.py \
    --region KR \
    --output-dir analysis/correlations/
        """
    )

    parser.add_argument('--dates', type=str,
                       help='Comma-separated dates (YYYY-MM-DD) to analyze')
    parser.add_argument('--region', type=str, default='KR',
                       help='Market region (default: KR)')
    parser.add_argument('--latest', action='store_true',
                       help='Analyze latest date only')
    parser.add_argument('--output-dir', type=str,
                       help='Output directory for CSV files')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("FACTOR INDEPENDENCE ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Region: {args.region}")

    # Initialize database and analyzer
    db = PostgresDatabaseManager()

    # Determine dates to analyze
    if args.latest:
        latest_date = get_latest_factor_date(db, args.region)
        if not latest_date:
            logger.error("❌ No factor data found in database")
            return 1
        dates = [latest_date]
        logger.info(f"Latest date: {latest_date}")
    elif args.dates:
        dates = [d.strip() for d in args.dates.split(',')]
        logger.info(f"Analyzing {len(dates)} dates: {', '.join(dates)}")
    else:
        # Default: sample dates
        dates = ['2024-10-10', '2025-03-01', '2025-09-18']
        logger.info(f"Using sample dates: {', '.join(dates)}")

    logger.info("=" * 80)

    # Run analysis for each date
    all_results = []

    with FactorCorrelationAnalyzer() as analyzer:
        for date in dates:
            try:
                results = analyze_date(analyzer, date, args.region, args.output_dir)
                all_results.append(results)
            except Exception as e:
                logger.error(f"❌ Analysis failed for {date}: {e}")
                import traceback
                traceback.print_exc()

    # Summary across all dates
    logger.info(f"\n{'#' * 80}")
    logger.info("MULTI-DATE SUMMARY")
    logger.info('#' * 80)

    successful_dates = [r for r in all_results if 'correlation_matrix' in r]

    logger.info(f"\n✅ Successfully analyzed {len(successful_dates)}/{len(dates)} dates")

    if successful_dates:
        # Aggregate redundancy findings
        all_redundant_pairs = []
        for result in successful_dates:
            if 'redundant_pairs' in result:
                all_redundant_pairs.extend(result['redundant_pairs'])

        if all_redundant_pairs:
            # Find consistently redundant pairs
            pair_counts = {}
            for pair in all_redundant_pairs:
                key = tuple(sorted([pair['factor1'], pair['factor2']]))
                if key not in pair_counts:
                    pair_counts[key] = {'count': 0, 'avg_corr': 0}
                pair_counts[key]['count'] += 1
                pair_counts[key]['avg_corr'] += pair['correlation']

            consistent_pairs = [
                (k, v['count'], v['avg_corr'] / v['count'])
                for k, v in pair_counts.items()
                if v['count'] >= len(successful_dates) / 2
            ]

            if consistent_pairs:
                logger.info(f"\n⚠️  CONSISTENTLY REDUNDANT PAIRS (in ≥{len(successful_dates)//2} dates):\n")
                for (f1, f2), count, avg_corr in sorted(consistent_pairs, key=lambda x: abs(x[2]), reverse=True):
                    logger.info(f"  • {f1} <-> {f2}: r_avg={avg_corr:+.3f} (in {count}/{len(successful_dates)} dates)")

        # Aggregate orthogonal recommendations
        factor_selection_counts = {}
        for result in successful_dates:
            if 'orthogonal_factors' in result:
                for factor in result['orthogonal_factors']:
                    factor_selection_counts[factor] = factor_selection_counts.get(factor, 0) + 1

        consistent_orthogonal = [
            (f, count)
            for f, count in factor_selection_counts.items()
            if count >= len(successful_dates) / 2
        ]

        if consistent_orthogonal:
            logger.info(f"\n✅ CONSISTENTLY INDEPENDENT FACTORS (in ≥{len(successful_dates)//2} dates):\n")
            for factor, count in sorted(consistent_orthogonal, key=lambda x: x[1], reverse=True):
                logger.info(f"  • {factor}: Selected in {count}/{len(successful_dates)} dates")

    # Save complete results to JSON
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        json_path = os.path.join(
            args.output_dir,
            f"factor_correlation_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        # Convert numpy types to native Python types for JSON serialization
        def convert_to_native(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            return obj

        all_results_native = convert_to_native(all_results)

        with open(json_path, 'w') as f:
            json.dump(all_results_native, f, indent=2)

        logger.info(f"\n💾 Complete analysis saved: {json_path}")

    logger.info("\n" + "=" * 80)
    logger.info("ANALYSIS COMPLETE")
    logger.info("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
