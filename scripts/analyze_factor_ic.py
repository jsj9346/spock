#!/usr/bin/env python3
"""
Factor IC Analysis Script
Systematically analyze Information Coefficient for all available factors.

Purpose:
- Calculate IC (Spearman correlation between factor scores and forward returns)
- Measure IC mean, std, and win rate (% positive IC)
- Identify factors with predictive power

Phase 3-1: Root cause analysis for 0% win rate problem

Author: Spock Quant Platform
Date: 2025-10-24
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import date, timedelta
from scipy.stats import spearmanr
from loguru import logger
import argparse

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_single_date_ic(
    db: PostgresDatabaseManager,
    factor_name: str,
    calculation_date: date,
    holding_period: int = 21,
    region: str = 'KR'
):
    """
    Calculate IC for a single factor on a specific date

    Returns:
        dict with keys: ic, p_value, num_stocks
    """
    # Get factor scores for this date
    query_scores = """
        SELECT ticker, score
        FROM factor_scores
        WHERE region = %s
          AND date = %s
          AND factor_name = %s
        ORDER BY ticker
    """

    results_scores = db.execute_query(query_scores, (region, calculation_date, factor_name))

    if not results_scores or len(results_scores) < 10:
        return {'ic': np.nan, 'p_value': 1.0, 'num_stocks': len(results_scores) if results_scores else 0}

    df_scores = pd.DataFrame(results_scores)

    # Get forward returns (holding_period days later)
    query_returns = """
        WITH base_prices AS (
            SELECT ticker, close as base_close
            FROM ohlcv_data
            WHERE region = %s AND date = %s
        ),
        future_prices AS (
            SELECT ticker, close as future_close, date,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) as rn
            FROM ohlcv_data
            WHERE region = %s
              AND date > %s
              AND date <= %s + INTERVAL '30 days'
        ),
        target_prices AS (
            SELECT ticker, future_close
            FROM future_prices
            WHERE rn = %s
        )
        SELECT bp.ticker, (tp.future_close / bp.base_close) - 1 as forward_return
        FROM base_prices bp
        INNER JOIN target_prices tp ON bp.ticker = tp.ticker
        WHERE bp.base_close > 0 AND tp.future_close > 0
    """

    results_returns = db.execute_query(
        query_returns,
        (region, calculation_date, region, calculation_date, calculation_date, holding_period)
    )

    if not results_returns or len(results_returns) < 10:
        return {'ic': np.nan, 'p_value': 1.0, 'num_stocks': 0}

    df_returns = pd.DataFrame(results_returns)

    # Merge factor scores with forward returns
    merged = df_scores.merge(df_returns, on='ticker', how='inner')

    if len(merged) < 10:
        return {'ic': np.nan, 'p_value': 1.0, 'num_stocks': len(merged)}

    # Calculate Spearman correlation (IC)
    try:
        ic, p_value = spearmanr(merged['score'], merged['forward_return'])
        return {
            'ic': float(ic) if not np.isnan(ic) else np.nan,
            'p_value': float(p_value) if not np.isnan(p_value) else 1.0,
            'num_stocks': len(merged)
        }
    except Exception as e:
        logger.warning(f"Error calculating IC for {factor_name} on {calculation_date}: {e}")
        return {'ic': np.nan, 'p_value': 1.0, 'num_stocks': len(merged)}


def analyze_factor_ic(
    db: PostgresDatabaseManager,
    factor_name: str,
    start_date: str,
    end_date: str,
    holding_period: int = 21,
    region: str = 'KR'
):
    """
    Analyze IC for a factor over a date range

    Returns:
        DataFrame with IC time series and summary statistics
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"ANALYZING FACTOR: {factor_name}")
    logger.info(f"{'='*80}")
    logger.info(f"Period: {start_date} to {end_date}")
    logger.info(f"Holding Period: {holding_period} days")
    logger.info(f"Region: {region}")

    # Get all available dates for this factor in the date range
    query_dates = """
        SELECT DISTINCT date
        FROM factor_scores
        WHERE region = %s
          AND factor_name = %s
          AND date >= %s
          AND date <= %s
        ORDER BY date
    """

    results_dates = db.execute_query(query_dates, (region, factor_name, start_date, end_date))

    if not results_dates:
        logger.warning(f"⚠️  No data found for {factor_name} in date range {start_date} to {end_date}")
        return None

    dates = [row['date'] if isinstance(row, dict) else row[0] for row in results_dates]
    logger.info(f"📊 Found {len(dates)} dates with factor data")

    # Calculate IC for each date
    ic_results = []

    for i, calc_date in enumerate(dates):
        if (i + 1) % 50 == 0:
            logger.info(f"   Progress: {i+1}/{len(dates)} dates processed...")

        result = calculate_single_date_ic(db, factor_name, calc_date, holding_period, region)

        if not np.isnan(result['ic']):
            ic_results.append({
                'date': calc_date,
                'ic': result['ic'],
                'p_value': result['p_value'],
                'num_stocks': result['num_stocks'],
                'is_significant': result['p_value'] < 0.05,
                'is_positive': result['ic'] > 0
            })

    if not ic_results:
        logger.warning(f"⚠️  No valid IC results for {factor_name}")
        return None

    df_ic = pd.DataFrame(ic_results)

    # Calculate summary statistics
    ic_mean = df_ic['ic'].mean()
    ic_std = df_ic['ic'].std()
    ic_median = df_ic['ic'].median()
    ic_win_rate = (df_ic['ic'] > 0).sum() / len(df_ic) * 100
    ic_significant_rate = df_ic['is_significant'].sum() / len(df_ic) * 100
    avg_stocks = df_ic['num_stocks'].mean()

    # Calculate rolling statistics
    df_ic['ic_12m_ma'] = df_ic['ic'].rolling(window=252, min_periods=60).mean()
    df_ic['ic_3m_ma'] = df_ic['ic'].rolling(window=63, min_periods=20).mean()

    logger.info(f"\n📊 IC SUMMARY STATISTICS")
    logger.info(f"   {'─'*60}")
    logger.info(f"   IC Mean:              {ic_mean:+.4f}")
    logger.info(f"   IC Std:               {ic_std:.4f}")
    logger.info(f"   IC Median:            {ic_median:+.4f}")
    logger.info(f"   IC Win Rate:          {ic_win_rate:.2f}%")
    logger.info(f"   Significant Rate:     {ic_significant_rate:.2f}%")
    logger.info(f"   Avg Stocks:           {avg_stocks:.0f}")
    logger.info(f"   Total Observations:   {len(df_ic)}")
    logger.info(f"   {'─'*60}")

    # Interpretation
    logger.info(f"\n💡 INTERPRETATION")
    if abs(ic_mean) >= 0.05:
        if ic_mean > 0:
            logger.info(f"   ✅ STRONG POSITIVE PREDICTIVE POWER (IC={ic_mean:+.4f})")
        else:
            logger.info(f"   ⚠️  STRONG NEGATIVE PREDICTIVE POWER (IC={ic_mean:+.4f})")
            logger.info(f"      → Consider contrarian strategy or factor inversion")
    elif abs(ic_mean) >= 0.02:
        logger.info(f"   ⚡ MODERATE PREDICTIVE POWER (IC={ic_mean:+.4f})")
    else:
        logger.info(f"   ❌ WEAK/NO PREDICTIVE POWER (IC={ic_mean:+.4f})")

    if ic_std < 0.10:
        logger.info(f"   ✅ STABLE IC (std={ic_std:.4f})")
    elif ic_std < 0.20:
        logger.info(f"   ⚡ MODERATE IC STABILITY (std={ic_std:.4f})")
    else:
        logger.info(f"   ⚠️  UNSTABLE IC (std={ic_std:.4f})")

    if ic_win_rate >= 60:
        logger.info(f"   ✅ CONSISTENT POSITIVE IC ({ic_win_rate:.1f}% win rate)")
    elif ic_win_rate >= 50:
        logger.info(f"   ⚡ NEUTRAL IC ({ic_win_rate:.1f}% win rate)")
    else:
        logger.info(f"   ⚠️  CONSISTENTLY NEGATIVE IC ({ic_win_rate:.1f}% win rate)")

    return df_ic


def main():
    parser = argparse.ArgumentParser(description='Analyze Factor IC Performance')
    parser.add_argument('--factors', type=str, help='Comma-separated factor names (or "all")')
    parser.add_argument('--start', type=str, default='2023-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-10-09', help='End date (YYYY-MM-DD)')
    parser.add_argument('--holding-period', type=int, default=21, help='Forward return period (days)')
    parser.add_argument('--region', type=str, default='KR', help='Market region')
    parser.add_argument('--output', type=str, help='Output CSV file path')

    args = parser.parse_args()

    # Configure logger
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=''),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    logger.info("="*80)
    logger.info("FACTOR IC ANALYSIS - PHASE 3-1")
    logger.info("="*80)

    # Initialize database
    db = PostgresDatabaseManager()

    # Get list of factors to analyze
    if args.factors and args.factors.lower() != 'all':
        factors = [f.strip() for f in args.factors.split(',')]
    else:
        # Get all available factors with sufficient data
        query = """
            SELECT factor_name, COUNT(DISTINCT date) as num_dates
            FROM factor_scores
            WHERE region = %s
              AND date >= %s
              AND date <= %s
            GROUP BY factor_name
            HAVING COUNT(DISTINCT date) >= 100
            ORDER BY factor_name
        """
        results = db.execute_query(query, (args.region, args.start, args.end))
        factors = [row['factor_name'] if isinstance(row, dict) else row[0] for row in results]
        logger.info(f"\n📋 Found {len(factors)} factors with sufficient data (≥100 dates)")
        logger.info(f"   Factors: {', '.join(factors)}")

    # Analyze each factor
    all_results = []

    for i, factor in enumerate(factors, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"FACTOR {i}/{len(factors)}: {factor}")
        logger.info(f"{'='*80}")

        df_ic = analyze_factor_ic(
            db=db,
            factor_name=factor,
            start_date=args.start,
            end_date=args.end,
            holding_period=args.holding_period,
            region=args.region
        )

        if df_ic is not None:
            df_ic['factor_name'] = factor
            all_results.append(df_ic)

    # Combine all results
    if all_results:
        df_all = pd.concat(all_results, ignore_index=True)

        # Save to CSV if requested
        if args.output:
            df_all.to_csv(args.output, index=False)
            logger.info(f"\n💾 Results saved to: {args.output}")

        # Generate comparative summary
        logger.info(f"\n{'='*80}")
        logger.info(f"COMPARATIVE FACTOR SUMMARY")
        logger.info(f"{'='*80}")

        summary = df_all.groupby('factor_name').agg({
            'ic': ['mean', 'std', 'median'],
            'is_positive': 'mean',
            'is_significant': 'mean',
            'num_stocks': 'mean'
        }).round(4)

        summary.columns = ['IC_Mean', 'IC_Std', 'IC_Median', 'Win_Rate', 'Significant_Rate', 'Avg_Stocks']
        summary['Win_Rate'] *= 100
        summary['Significant_Rate'] *= 100
        summary = summary.sort_values('IC_Mean', ascending=False)

        logger.info(f"\n{summary.to_string()}")

        # Identify best factors
        logger.info(f"\n{'='*80}")
        logger.info(f"FACTOR RECOMMENDATIONS")
        logger.info(f"{'='*80}")

        top_positive = summary[summary['IC_Mean'] > 0].head(3)
        if not top_positive.empty:
            logger.info(f"\n✅ TOP POSITIVE IC FACTORS:")
            for idx, (factor, row) in enumerate(top_positive.iterrows(), 1):
                logger.info(f"   {idx}. {factor}: IC={row['IC_Mean']:+.4f}, Win Rate={row['Win_Rate']:.1f}%")

        top_negative = summary[summary['IC_Mean'] < 0].tail(3)
        if not top_negative.empty:
            logger.info(f"\n⚠️  TOP NEGATIVE IC FACTORS (consider contrarian):")
            for idx, (factor, row) in enumerate(top_negative.iterrows(), 1):
                logger.info(f"   {idx}. {factor}: IC={row['IC_Mean']:+.4f}, Win Rate={row['Win_Rate']:.1f}%")

    logger.info(f"\n{'='*80}")
    logger.info(f"FACTOR IC ANALYSIS COMPLETE")
    logger.info(f"{'='*80}\n")


if __name__ == '__main__':
    main()
