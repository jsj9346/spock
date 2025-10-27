#!/usr/bin/env python3
"""
Example: Factor Analysis with Real Data

Demonstrates usage of Factor Analysis modules:
1. FactorAnalyzer - Quintile analysis and IC calculation
2. FactorCorrelationAnalyzer - Correlation matrix and redundancy detection
3. PerformanceReporter - Generate visualizations and reports

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
from datetime import date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.analysis import (
    FactorAnalyzer,
    FactorCorrelationAnalyzer,
    PerformanceReporter
)


def main():
    """Run comprehensive factor analysis example"""

    # Configuration
    analysis_date = '2025-10-22'  # Date with real factor data
    region = 'KR'
    holding_period = 21  # 21-day forward returns
    output_dir = 'reports/factor_analysis_example/'

    print("=" * 80)
    print("Factor Analysis Example - Spock Quant Platform")
    print("=" * 80)
    print(f"\nAnalysis Date: {analysis_date}")
    print(f"Region: {region}")
    print(f"Holding Period: {holding_period} days")
    print(f"Output Directory: {output_dir}\n")

    # =========================================================================
    # Part 1: Factor Correlation Analysis
    # =========================================================================
    print("\n" + "=" * 80)
    print("PART 1: FACTOR CORRELATION ANALYSIS")
    print("=" * 80)

    analyzer = FactorCorrelationAnalyzer()

    # Calculate pairwise correlation matrix
    print("\n[1.1] Calculating pairwise factor correlations...")
    corr_matrix = analyzer.pairwise_correlation(
        analysis_date=analysis_date,
        region=region,
        method='spearman'
    )

    if not corr_matrix.empty:
        print(f"✓ Correlation matrix calculated: {corr_matrix.shape}")
        print(f"  Factors analyzed: {', '.join(corr_matrix.index.tolist())}")
        print("\nCorrelation Matrix Preview:")
        print(corr_matrix.round(3))
    else:
        print("⚠ No factor data available for correlation analysis")
        return

    # Detect redundant factor pairs
    print("\n[1.2] Detecting redundant factor pairs (|correlation| > 0.7)...")
    redundant_pairs = analyzer.redundancy_detection(
        analysis_date=analysis_date,
        region=region,
        threshold=0.7
    )

    if redundant_pairs:
        print(f"✓ Found {len(redundant_pairs)} redundant pairs:")
        for i, pair in enumerate(redundant_pairs[:5], 1):  # Top 5
            significance = "✓" if pair.is_significant else "✗"
            print(f"  {i}. {pair.factor1:20s} <-> {pair.factor2:20s}: "
                  f"{pair.correlation:+.3f} ({pair.num_stocks} stocks) "
                  f"[p-value: {pair.p_value:.4f}] {significance}")
    else:
        print("✓ No highly redundant factor pairs found (good diversification)")

    # Suggest orthogonal factor set
    print("\n[1.3] Suggesting orthogonalized factor set (max correlation: 0.5)...")
    orthogonal_factors = analyzer.orthogonalization_suggestion(
        analysis_date=analysis_date,
        region=region,
        max_correlation=0.5
    )

    if orthogonal_factors:
        print(f"✓ Suggested {len(orthogonal_factors)} independent factors:")
        for i, factor in enumerate(orthogonal_factors, 1):
            print(f"  {i}. {factor}")

    analyzer.close()

    # =========================================================================
    # Part 2: Quintile Analysis (Per-Factor Performance)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PART 2: QUINTILE ANALYSIS")
    print("=" * 80)

    factor_analyzer = FactorAnalyzer()

    # Select a few factors for quintile analysis
    sample_factors = ['12M_Momentum', 'PE_Ratio', 'Earnings_Quality']

    for factor_name in sample_factors:
        print(f"\n[2.1] Analyzing factor: {factor_name}")
        print("-" * 80)

        quintile_results = factor_analyzer.quintile_analysis(
            factor_name=factor_name,
            analysis_date=analysis_date,
            region=region,
            holding_period=holding_period
        )

        if quintile_results:
            print(f"✓ Quintile analysis complete ({len(quintile_results)} quintiles)")
            print("\nQuintile Performance Summary:")
            print(f"{'Q':<3} {'Stocks':<8} {'Mean Return':<12} {'Median Return':<14} "
                  f"{'Sharpe':<8} {'Hit Rate':<10}")
            print("-" * 80)

            for q in quintile_results:
                print(f"{q.quintile:<3} {q.num_stocks:<8} {q.mean_return:>11.2%} "
                      f"{q.median_return:>13.2%} {q.sharpe_ratio:>7.2f} "
                      f"{q.hit_rate:>9.1%}")

            # Calculate quintile spread (Q5 - Q1)
            if len(quintile_results) >= 5:
                spread = quintile_results[-1].mean_return - quintile_results[0].mean_return
                print(f"\nQuintile Spread (Q5 - Q1): {spread:+.2%}")

                if abs(spread) > 0.05:  # >5% spread
                    direction = "Long Q5, Short Q1" if spread > 0 else "Long Q1, Short Q5"
                    print(f"✓ Strong signal: {direction}")
                else:
                    print("⚠ Weak signal: Limited predictive power")
        else:
            print(f"⚠ No forward return data available for {factor_name}")

    factor_analyzer.close()

    # =========================================================================
    # Part 3: Generate Visualization Reports
    # =========================================================================
    print("\n" + "=" * 80)
    print("PART 3: VISUALIZATION REPORTS")
    print("=" * 80)

    reporter = PerformanceReporter(output_dir=output_dir)

    # Generate correlation heatmap
    print("\n[3.1] Generating correlation heatmap...")
    heatmap_files = reporter.correlation_heatmap(
        corr_matrix=corr_matrix,
        analysis_date=analysis_date,
        region=region,
        export_formats=['png', 'pdf']
    )

    if heatmap_files:
        print("✓ Correlation heatmap generated:")
        for format_type, filepath in heatmap_files.items():
            print(f"  {format_type.upper()}: {filepath}")

    # Generate quintile performance reports (if data available)
    print("\n[3.2] Generating quintile performance reports...")

    # Re-run quintile analysis to get results for reporting
    factor_analyzer = FactorAnalyzer()

    for factor_name in ['12M_Momentum', 'PE_Ratio']:
        quintile_results = factor_analyzer.quintile_analysis(
            factor_name=factor_name,
            analysis_date=analysis_date,
            region=region,
            holding_period=holding_period
        )

        if quintile_results:
            report_files = reporter.quintile_performance_report(
                factor_name=factor_name,
                quintile_results=quintile_results,
                analysis_date=analysis_date,
                region=region,
                holding_period=holding_period,
                export_formats=['png', 'csv']
            )

            if report_files:
                print(f"✓ {factor_name} quintile report generated:")
                for format_type, filepath in report_files.items():
                    print(f"  {format_type.upper()}: {filepath}")
        else:
            print(f"⚠ Skipping {factor_name} (no forward return data)")

    factor_analyzer.close()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nAll reports saved to: {output_dir}")
    print("\nKey Findings:")
    print(f"  • {len(corr_matrix)} factors analyzed")
    print(f"  • {len(redundant_pairs)} redundant pairs detected (threshold: 0.7)")
    print(f"  • {len(orthogonal_factors)} independent factors suggested")
    print("\nNext Steps:")
    print("  1. Review correlation heatmap for factor independence")
    print("  2. Examine quintile reports for factor predictive power")
    print("  3. Consider removing redundant factors from strategy")
    print("  4. Backfill historical factor scores for IC time series analysis")
    print("=" * 80)


if __name__ == '__main__':
    main()
