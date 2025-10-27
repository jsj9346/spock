#!/usr/bin/env python3
"""
IC Time Series Visualization CLI

Standalone script for generating interactive IC (Information Coefficient) charts
from PostgreSQL database with Plotly.

Features:
- Load IC data from ic_time_series table
- Generate all chart types (time series, heatmap, distribution, rolling average)
- Export to HTML (interactive) and PNG (static) formats
- Support date range filtering and factor selection

Usage:
    python3 scripts/visualize_ic_time_series.py \
      --region KR \
      --holding-period 21 \
      --output-dir reports/ic_charts/

    python3 scripts/visualize_ic_time_series.py \
      --start-date 2025-01-01 \
      --end-date 2025-09-30 \
      --factors PE_Ratio,PB_Ratio \
      --charts timeseries,heatmap \
      --formats html,png

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
from datetime import date, datetime
from typing import List, Optional
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.visualization.ic_charts import ICChartGenerator


# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def load_ic_data(
    db: PostgresDatabaseManager,
    region: str,
    holding_period: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    factors: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Load IC time series from database

    Args:
        db: Database manager
        region: Market region (e.g., 'KR', 'US')
        holding_period: Forward return period in days
        start_date: Start date filter (optional)
        end_date: End date filter (optional)
        factors: List of factor names to filter (optional, default: all)

    Returns:
        DataFrame with columns: [date, factor_name, ic, p_value, num_stocks, is_significant]
    """
    query = """
        SELECT
            date,
            factor_name,
            ic,
            p_value,
            num_stocks,
            is_significant
        FROM ic_time_series
        WHERE region = %s
          AND holding_period = %s
    """

    params = [region, holding_period]

    # Add optional date filters
    if start_date:
        query += " AND date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND date <= %s"
        params.append(end_date)

    # Add optional factor filter
    if factors:
        placeholders = ','.join(['%s'] * len(factors))
        query += f" AND factor_name IN ({placeholders})"
        params.extend(factors)

    query += " ORDER BY date, factor_name"

    result = db.execute_query(query, tuple(params))

    if not result:
        logger.warning("No IC data found with specified filters")
        return pd.DataFrame()

    df = pd.DataFrame(result)

    # Convert types
    df['date'] = pd.to_datetime(df['date'])
    df['ic'] = pd.to_numeric(df['ic'], errors='coerce')
    df['p_value'] = pd.to_numeric(df['p_value'], errors='coerce')
    df['num_stocks'] = pd.to_numeric(df['num_stocks'], errors='coerce')

    return df


def print_summary_statistics(ic_df: pd.DataFrame):
    """
    Print summary statistics for IC data

    Args:
        ic_df: DataFrame with IC data
    """
    if ic_df.empty:
        logger.warning("No data to summarize")
        return

    logger.info("\n" + "=" * 80)
    logger.info("IC DATA SUMMARY")
    logger.info("=" * 80)

    # Overall stats
    logger.info(f"Date Range: {ic_df['date'].min():%Y-%m-%d} to {ic_df['date'].max():%Y-%m-%d}")
    logger.info(f"Total Records: {len(ic_df):,}")
    logger.info(f"Unique Dates: {ic_df['date'].nunique()}")
    logger.info(f"Factors: {', '.join(ic_df['factor_name'].unique())}")

    logger.info("\n" + "-" * 80)
    logger.info("PER-FACTOR STATISTICS")
    logger.info("-" * 80)

    # Per-factor stats
    for factor in ic_df['factor_name'].unique():
        factor_data = ic_df[ic_df['factor_name'] == factor]

        avg_ic = factor_data['ic'].mean()
        std_ic = factor_data['ic'].std()
        min_ic = factor_data['ic'].min()
        max_ic = factor_data['ic'].max()
        pct_positive = (factor_data['ic'] > 0).sum() / len(factor_data) * 100
        pct_significant = (factor_data['is_significant'] == True).sum() / len(factor_data) * 100

        logger.info(f"\n{factor}:")
        logger.info(f"  Average IC: {avg_ic:+.4f}")
        logger.info(f"  Std Dev: {std_ic:.4f}")
        logger.info(f"  IC Range: {min_ic:+.4f} to {max_ic:+.4f}")
        logger.info(f"  % Positive IC: {pct_positive:.1f}%")
        logger.info(f"  % Significant (p<0.05): {pct_significant:.1f}%")
        logger.info(f"  Num Records: {len(factor_data)}")

    logger.info("\n" + "=" * 80)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Generate interactive IC time series visualizations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all charts for KR market
  python3 scripts/visualize_ic_time_series.py --region KR --holding-period 21

  # Generate specific charts with date filter
  python3 scripts/visualize_ic_time_series.py \\
    --start-date 2025-01-01 \\
    --end-date 2025-09-30 \\
    --charts timeseries,distribution

  # Export specific factors to PNG
  python3 scripts/visualize_ic_time_series.py \\
    --factors PE_Ratio,PB_Ratio \\
    --formats html,png \\
    --output-dir reports/ic_charts/
        """
    )

    # Database filters
    parser.add_argument('--region', type=str, default='KR',
                       help='Market region (default: KR)')
    parser.add_argument('--holding-period', type=int, default=21,
                       help='Forward return period in days (default: 21)')
    parser.add_argument('--start-date', type=str,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--factors', type=str,
                       help='Comma-separated factor names (default: all)')

    # Chart options
    parser.add_argument('--charts', type=str, default='all',
                       help='Comma-separated chart types: timeseries,heatmap,distribution,rolling,dashboard (default: all)')
    parser.add_argument('--rolling-window', type=int, default=20,
                       help='Rolling window size for moving averages (default: 20)')

    # Export options
    parser.add_argument('--output-dir', type=str, default='reports/ic_charts/',
                       help='Output directory for charts (default: reports/ic_charts/)')
    parser.add_argument('--formats', type=str, default='html',
                       help='Export formats: html,png (default: html)')
    parser.add_argument('--theme', type=str, default='plotly_white',
                       help='Plotly theme (default: plotly_white)')

    args = parser.parse_args()

    # Parse arguments
    region = args.region
    holding_period = args.holding_period
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date() if args.start_date else None
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date() if args.end_date else None
    factors = args.factors.split(',') if args.factors else None
    rolling_window = args.rolling_window
    output_dir = args.output_dir
    formats = args.formats.split(',')
    theme = args.theme

    # Chart types
    if args.charts.lower() == 'all':
        chart_types = ['timeseries', 'heatmap', 'distribution', 'rolling', 'dashboard']
    else:
        chart_types = args.charts.lower().split(',')

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 80)
    logger.info("IC TIME SERIES VISUALIZATION")
    logger.info("=" * 80)
    logger.info(f"Region: {region}")
    logger.info(f"Holding Period: {holding_period} days")
    logger.info(f"Date Range: {start_date or 'All'} to {end_date or 'All'}")
    logger.info(f"Factors: {factors or 'All'}")
    logger.info(f"Chart Types: {', '.join(chart_types)}")
    logger.info(f"Export Formats: {', '.join(formats)}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info("=" * 80)

    # Load IC data from database
    logger.info("\nLoading IC data from database...")
    db = PostgresDatabaseManager()

    ic_df = load_ic_data(
        db=db,
        region=region,
        holding_period=holding_period,
        start_date=start_date,
        end_date=end_date,
        factors=factors
    )

    if ic_df.empty:
        logger.error("No IC data found. Exiting.")
        return

    logger.info(f"✓ Loaded {len(ic_df):,} IC records")

    # Print summary statistics
    print_summary_statistics(ic_df)

    # Initialize chart generator
    generator = ICChartGenerator(theme=theme)

    # Generate charts
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    generated_files = []

    # Chart 1: IC Time Series
    if 'timeseries' in chart_types:
        logger.info("\nGenerating IC time series chart...")
        fig = generator.plot_ic_time_series(
            ic_df=ic_df,
            rolling_window=rolling_window,
            show_significance=True
        )

        if 'html' in formats:
            filename = f'ic_timeseries_{region}_{timestamp}.html'
            filepath = os.path.join(output_dir, filename)
            fig.write_html(filepath)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved HTML: {filepath}")

        if 'png' in formats:
            filename = f'ic_timeseries_{region}_{timestamp}.png'
            filepath = os.path.join(output_dir, filename)
            fig.write_image(filepath, width=1200, height=600)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved PNG: {filepath}")

    # Chart 2: Monthly Heatmap (per factor)
    if 'heatmap' in chart_types:
        for factor in ic_df['factor_name'].unique():
            logger.info(f"\nGenerating monthly heatmap for {factor}...")
            fig = generator.plot_monthly_ic_heatmap(
                ic_df=ic_df,
                factor_name=factor
            )

            if 'html' in formats:
                filename = f'ic_heatmap_{factor}_{region}_{timestamp}.html'
                filepath = os.path.join(output_dir, filename)
                fig.write_html(filepath)
                generated_files.append(filepath)
                logger.info(f"  ✓ Saved HTML: {filepath}")

            if 'png' in formats:
                filename = f'ic_heatmap_{factor}_{region}_{timestamp}.png'
                filepath = os.path.join(output_dir, filename)
                fig.write_image(filepath, width=1000, height=600)
                generated_files.append(filepath)
                logger.info(f"  ✓ Saved PNG: {filepath}")

    # Chart 3: IC Distribution
    if 'distribution' in chart_types:
        logger.info("\nGenerating IC distribution histogram...")
        fig = generator.plot_ic_distribution(ic_df=ic_df)

        if 'html' in formats:
            filename = f'ic_distribution_{region}_{timestamp}.html'
            filepath = os.path.join(output_dir, filename)
            fig.write_html(filepath)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved HTML: {filepath}")

        if 'png' in formats:
            filename = f'ic_distribution_{region}_{timestamp}.png'
            filepath = os.path.join(output_dir, filename)
            fig.write_image(filepath, width=1000, height=600)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved PNG: {filepath}")

    # Chart 4: Rolling IC Average
    if 'rolling' in chart_types:
        logger.info(f"\nGenerating rolling IC average ({rolling_window}d)...")
        fig = generator.plot_rolling_ic_average(
            ic_df=ic_df,
            window=rolling_window
        )

        if 'html' in formats:
            filename = f'ic_rolling_avg_{region}_{timestamp}.html'
            filepath = os.path.join(output_dir, filename)
            fig.write_html(filepath)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved HTML: {filepath}")

        if 'png' in formats:
            filename = f'ic_rolling_avg_{region}_{timestamp}.png'
            filepath = os.path.join(output_dir, filename)
            fig.write_image(filepath, width=1200, height=600)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved PNG: {filepath}")

    # Chart 5: Multi-Factor Dashboard
    if 'dashboard' in chart_types:
        logger.info("\nGenerating multi-factor dashboard...")
        fig = generator.create_multi_factor_dashboard(
            ic_df=ic_df,
            rolling_window=rolling_window
        )

        if 'html' in formats:
            filename = f'ic_dashboard_{region}_{timestamp}.html'
            filepath = os.path.join(output_dir, filename)
            fig.write_html(filepath)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved HTML: {filepath}")

        if 'png' in formats:
            filename = f'ic_dashboard_{region}_{timestamp}.png'
            filepath = os.path.join(output_dir, filename)
            fig.write_image(filepath, width=1600, height=1000)
            generated_files.append(filepath)
            logger.info(f"  ✓ Saved PNG: {filepath}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("VISUALIZATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total Charts Generated: {len(generated_files)}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info("\nGenerated Files:")
    for filepath in generated_files:
        logger.info(f"  - {filepath}")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
