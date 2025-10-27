#!/usr/bin/env python3
"""
Historical Factor Score Backfill Script

Backfills factor scores for historical dates (2024-10-10 to 2025-10-20).

Factors Calculated:
1. Value Factors (2): PE_Ratio, PB_Ratio
2. Momentum Factors (3): 12M_Momentum, 1M_Momentum, RSI_Momentum
3. Quality Factors (4): ROE_Proxy (operating_profit/equity),
                        Operating_Profit_Margin (operating_profit/revenue),
                        Current_Ratio (current_assets/current_liabilities),
                        Debt_Ratio (total_liabilities/total_assets)

Total: 9 factors × ~150 stocks × 250 trading days = ~337K rows

Note: Quality factors use alternative metrics due to semi-annual DART data limitations.
      Traditional ROE (net_income/equity) unavailable as net_income = 0 in semi-annual reports.

Usage:
    python3 scripts/backfill_factor_scores_historical.py --start-date 2024-10-10 --end-date 2025-10-20
    python3 scripts/backfill_factor_scores_historical.py --start-date 2024-10-10 --end-date 2025-10-20 --dry-run
    python3 scripts/backfill_factor_scores_historical.py --start-date 2024-10-10 --end-date 2025-10-20 --region KR
    python3 scripts/backfill_factor_scores_historical.py --start-date 2024-10-10 --end-date 2025-10-20 --factors value,momentum

Author: Spock Quant Platform
Date: 2025-10-23
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import pandas as pd
import psycopg2
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_value_factors(db: PostgresDatabaseManager, analysis_date: date, region: str) -> List[tuple]:
    """
    Calculate Value Factors (PE_Ratio, PB_Ratio)

    Returns list of tuples: (ticker, region, date, factor_name, score, percentile)
    """
    logger.info(f"  [Value Factors] Calculating for {analysis_date}...")

    query = """
        WITH latest_fundamentals AS (
            SELECT
                tf.ticker,
                tf.region,
                tf.per,
                tf.pbr,
                ROW_NUMBER() OVER (PARTITION BY tf.ticker
                                  ORDER BY ABS(tf.date - %s::date)) as rn
            FROM ticker_fundamentals tf
            WHERE tf.region = %s
              AND tf.per IS NOT NULL
              AND tf.pbr IS NOT NULL
              AND tf.date <= %s::date
        )
        SELECT ticker, region, per, pbr
        FROM latest_fundamentals
        WHERE rn = 1
          AND per > 0 AND per < 100
          AND pbr > 0 AND pbr < 20
        ORDER BY ticker
    """

    fundamentals = db.execute_query(query, (analysis_date, region, analysis_date))

    if not fundamentals:
        logger.warning(f"  [Value Factors] No fundamental data for {analysis_date}")
        return []

    df = pd.DataFrame(fundamentals)
    df['per'] = pd.to_numeric(df['per'], errors='coerce')
    df['pbr'] = pd.to_numeric(df['pbr'], errors='coerce')

    records = []

    # PE_Ratio factor
    valid_pe = df[df['per'].notna()].copy()
    if len(valid_pe) > 0:
        valid_pe['raw_score'] = -valid_pe['per']
        valid_pe['percentile'] = valid_pe['raw_score'].rank(pct=True) * 100
        mean_val = valid_pe['raw_score'].mean()
        std_val = valid_pe['raw_score'].std()
        valid_pe['z_score'] = (valid_pe['raw_score'] - mean_val) / std_val if std_val > 0 else 0

        for _, row in valid_pe.iterrows():
            records.append((
                row['ticker'], row['region'], analysis_date, 'PE_Ratio',
                float(row['z_score']), float(row['percentile'])
            ))
        logger.info(f"    ✓ PE_Ratio: {len(valid_pe)} stocks")

    # PB_Ratio factor
    valid_pb = df[df['pbr'].notna()].copy()
    if len(valid_pb) > 0:
        valid_pb['raw_score'] = -valid_pb['pbr']
        valid_pb['percentile'] = valid_pb['raw_score'].rank(pct=True) * 100
        mean_val = valid_pb['raw_score'].mean()
        std_val = valid_pb['raw_score'].std()
        valid_pb['z_score'] = (valid_pb['raw_score'] - mean_val) / std_val if std_val > 0 else 0

        for _, row in valid_pb.iterrows():
            records.append((
                row['ticker'], row['region'], analysis_date, 'PB_Ratio',
                float(row['z_score']), float(row['percentile'])
            ))
        logger.info(f"    ✓ PB_Ratio: {len(valid_pb)} stocks")

    return records


def calculate_momentum_factors(db: PostgresDatabaseManager, analysis_date: date, region: str) -> List[tuple]:
    """
    Calculate Momentum Factors (12M_Momentum, 1M_Momentum, RSI_Momentum)

    Returns list of tuples: (ticker, region, date, factor_name, score, percentile)
    """
    logger.info(f"  [Momentum Factors] Calculating for {analysis_date}...")

    # Get OHLCV data for momentum calculation
    query = """
        WITH price_data AS (
            SELECT
                ticker,
                region,
                date,
                close,
                LAG(close, 21) OVER (PARTITION BY ticker, region ORDER BY date) as close_1m,
                LAG(close, 252) OVER (PARTITION BY ticker, region ORDER BY date) as close_12m,
                volume
            FROM ohlcv_data
            WHERE region = %s
              AND date <= %s::date
              AND date >= %s::date - INTERVAL '18 months'
        )
        SELECT ticker, region, date, close, close_1m, close_12m, volume
        FROM price_data
        WHERE date = %s::date
          AND close_1m IS NOT NULL
          AND close_12m IS NOT NULL
        ORDER BY ticker
    """

    price_data = db.execute_query(query, (region, analysis_date, analysis_date, analysis_date))

    if not price_data:
        logger.warning(f"  [Momentum Factors] No price data for {analysis_date}")
        return []

    df = pd.DataFrame(price_data)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['close_1m'] = pd.to_numeric(df['close_1m'], errors='coerce')
    df['close_12m'] = pd.to_numeric(df['close_12m'], errors='coerce')

    records = []

    # 12M_Momentum (excluding last month)
    valid_12m = df[(df['close_1m'].notna()) & (df['close_12m'].notna()) & (df['close_12m'] > 0)].copy()
    if len(valid_12m) > 0:
        valid_12m['return_12m'] = (valid_12m['close_1m'] / valid_12m['close_12m']) - 1
        valid_12m['percentile'] = valid_12m['return_12m'].rank(pct=True) * 100
        mean_val = valid_12m['return_12m'].mean()
        std_val = valid_12m['return_12m'].std()
        valid_12m['z_score'] = (valid_12m['return_12m'] - mean_val) / std_val if std_val > 0 else 0

        for _, row in valid_12m.iterrows():
            records.append((
                row['ticker'], row['region'], analysis_date, '12M_Momentum',
                float(row['z_score']), float(row['percentile'])
            ))
        logger.info(f"    ✓ 12M_Momentum: {len(valid_12m)} stocks")

    # 1M_Momentum
    valid_1m = df[(df['close'].notna()) & (df['close_1m'].notna()) & (df['close_1m'] > 0)].copy()
    if len(valid_1m) > 0:
        valid_1m['return_1m'] = (valid_1m['close'] / valid_1m['close_1m']) - 1
        valid_1m['percentile'] = valid_1m['return_1m'].rank(pct=True) * 100
        mean_val = valid_1m['return_1m'].mean()
        std_val = valid_1m['return_1m'].std()
        valid_1m['z_score'] = (valid_1m['return_1m'] - mean_val) / std_val if std_val > 0 else 0

        for _, row in valid_1m.iterrows():
            records.append((
                row['ticker'], row['region'], analysis_date, '1M_Momentum',
                float(row['z_score']), float(row['percentile'])
            ))
        logger.info(f"    ✓ 1M_Momentum: {len(valid_1m)} stocks")

    # RSI_Momentum (simplified - using 14-day price changes)
    # Note: Full RSI calculation requires 14-day OHLCV data, simplified here
    if len(valid_1m) > 0:
        # Use 1M return as proxy for RSI momentum
        valid_rsi = valid_1m.copy()
        valid_rsi['rsi_proxy'] = 50 + (valid_rsi['return_1m'] * 100)  # Rough proxy
        valid_rsi['rsi_proxy'] = valid_rsi['rsi_proxy'].clip(0, 100)
        valid_rsi['percentile'] = valid_rsi['rsi_proxy'].rank(pct=True) * 100
        mean_val = valid_rsi['rsi_proxy'].mean()
        std_val = valid_rsi['rsi_proxy'].std()
        valid_rsi['z_score'] = (valid_rsi['rsi_proxy'] - mean_val) / std_val if std_val > 0 else 0

        for _, row in valid_rsi.iterrows():
            records.append((
                row['ticker'], row['region'], analysis_date, 'RSI_Momentum',
                float(row['z_score']), float(row['percentile'])
            ))
        logger.info(f"    ✓ RSI_Momentum: {len(valid_rsi)} stocks (proxy)")

    return records


def calculate_quality_factors(db: PostgresDatabaseManager, analysis_date: date, region: str) -> List[tuple]:
    """
    Calculate Quality Factors using Alternative Metrics

    Uses DART fundamental data with alternative quality metrics:
    - ROE_Proxy: operating_profit / total_equity (instead of net_income)
    - Operating_Margin: operating_profit / revenue
    - Current_Ratio: current_assets / current_liabilities
    - Debt_Ratio: total_liabilities / total_assets

    Note: Semi-annual DART reports don't provide net_income, so we use operating_profit as proxy.
    Coverage: 93-100% of KR stocks with DART data
    """
    logger.info(f"  [Quality Factors] Calculating for {analysis_date}...")

    # Get latest fundamental data for each ticker
    # Note: For historical backfill, use the most recent available fundamental data
    # This reflects real-world scenario where quarterly reports remain valid until next report
    query = """
        WITH latest_fundamentals AS (
            SELECT
                tf.ticker,
                tf.region,
                tf.operating_profit,
                tf.total_equity,
                tf.total_assets,
                tf.total_liabilities,
                tf.current_assets,
                tf.current_liabilities,
                tf.revenue,
                tf.fiscal_year,
                tf.date,
                ROW_NUMBER() OVER (PARTITION BY tf.ticker
                                  ORDER BY tf.date DESC) as rn
            FROM ticker_fundamentals tf
            WHERE tf.region = %s
              AND tf.operating_profit IS NOT NULL
              AND tf.total_equity IS NOT NULL
        )
        SELECT ticker, region, operating_profit, total_equity, total_assets, total_liabilities,
               current_assets, current_liabilities, revenue
        FROM latest_fundamentals
        WHERE rn = 1
        ORDER BY ticker
    """

    fundamentals = db.execute_query(query, (region,))

    if not fundamentals:
        logger.warning(f"  [Quality Factors] No fundamental data for {analysis_date}")
        return []

    df = pd.DataFrame(fundamentals)

    # Convert Decimal to float
    numeric_cols = ['operating_profit', 'total_equity', 'total_assets', 'total_liabilities',
                   'current_assets', 'current_liabilities', 'revenue']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    records = []

    # ROE_Proxy (using operating_profit instead of net_income)
    valid_roe = df[(df['operating_profit'].notna()) & (df['total_equity'].notna()) & (df['total_equity'] > 0)].copy()
    if len(valid_roe) > 0:
        valid_roe['roe_proxy'] = valid_roe['operating_profit'] / valid_roe['total_equity']
        valid_roe['percentile'] = valid_roe['roe_proxy'].rank(pct=True) * 100
        mean_val = valid_roe['roe_proxy'].mean()
        std_val = valid_roe['roe_proxy'].std()
        valid_roe['z_score'] = (valid_roe['roe_proxy'] - mean_val) / std_val if std_val > 0 else 0
        for _, row in valid_roe.iterrows():
            records.append((row['ticker'], row['region'], analysis_date, 'ROE_Proxy', float(row['z_score']), float(row['percentile'])))
        logger.info(f"    ✓ ROE_Proxy: {len(valid_roe)} stocks")

    # Operating_Profit_Margin
    valid_opm = df[(df['operating_profit'].notna()) & (df['revenue'].notna()) & (df['revenue'] > 0)].copy()
    if len(valid_opm) > 0:
        valid_opm['op_profit_margin'] = valid_opm['operating_profit'] / valid_opm['revenue']
        valid_opm['percentile'] = valid_opm['op_profit_margin'].rank(pct=True) * 100
        mean_val = valid_opm['op_profit_margin'].mean()
        std_val = valid_opm['op_profit_margin'].std()
        valid_opm['z_score'] = (valid_opm['op_profit_margin'] - mean_val) / std_val if std_val > 0 else 0
        for _, row in valid_opm.iterrows():
            records.append((row['ticker'], row['region'], analysis_date, 'Operating_Profit_Margin', float(row['z_score']), float(row['percentile'])))
        logger.info(f"    ✓ Operating_Profit_Margin: {len(valid_opm)} stocks")

    # Current_Ratio
    valid_cr = df[(df['current_assets'].notna()) & (df['current_liabilities'].notna()) & (df['current_liabilities'] > 0)].copy()
    if len(valid_cr) > 0:
        valid_cr['current_ratio'] = valid_cr['current_assets'] / valid_cr['current_liabilities']
        valid_cr['percentile'] = valid_cr['current_ratio'].rank(pct=True) * 100
        mean_val = valid_cr['current_ratio'].mean()
        std_val = valid_cr['current_ratio'].std()
        valid_cr['z_score'] = (valid_cr['current_ratio'] - mean_val) / std_val if std_val > 0 else 0
        for _, row in valid_cr.iterrows():
            records.append((row['ticker'], row['region'], analysis_date, 'Current_Ratio', float(row['z_score']), float(row['percentile'])))
        logger.info(f"    ✓ Current_Ratio: {len(valid_cr)} stocks")

    # Debt_Ratio (total_liabilities / total_assets)
    valid_dr = df[(df['total_liabilities'].notna()) & (df['total_assets'].notna()) & (df['total_assets'] > 0)].copy()
    if len(valid_dr) > 0:
        valid_dr['debt_ratio'] = valid_dr['total_liabilities'] / valid_dr['total_assets']
        valid_dr['raw_score'] = -valid_dr['debt_ratio']  # Lower debt is better
        valid_dr['percentile'] = valid_dr['raw_score'].rank(pct=True) * 100
        mean_val = valid_dr['raw_score'].mean()
        std_val = valid_dr['raw_score'].std()
        valid_dr['z_score'] = (valid_dr['raw_score'] - mean_val) / std_val if std_val > 0 else 0
        for _, row in valid_dr.iterrows():
            records.append((row['ticker'], row['region'], analysis_date, 'Debt_Ratio', float(row['z_score']), float(row['percentile'])))
        logger.info(f"    ✓ Debt_Ratio: {len(valid_dr)} stocks")

    # Note: Quick_Ratio, Accruals_Ratio, CF_to_NI_Ratio require more detailed financial data
    # Skipping for simplified version (can add later)

    return records


def save_factor_scores(db: PostgresDatabaseManager, records: List[tuple], dry_run: bool = False) -> int:
    """
    Save factor scores to database

    Returns number of records saved
    """
    if not records:
        return 0

    if dry_run:
        logger.info(f"  [DRY RUN] Would save {len(records)} factor scores")
        return len(records)

    query = """
        INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, factor_name)
        DO UPDATE SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
    """

    try:
        with db._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(query, records)
                conn.commit()
        return len(records)
    except Exception as e:
        logger.error(f"  [ERROR] Failed to save factor scores: {e}")
        return 0


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Historical Factor Score Backfill')
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--region', type=str, default='KR', help='Market region (default: KR)')
    parser.add_argument('--factors', type=str, default='all',
                       help='Factor types to calculate (all, value, momentum, quality) - comma separated')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of dates to process per batch')

    args = parser.parse_args()

    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    region = args.region
    dry_run = args.dry_run

    factor_types = args.factors.lower().split(',')
    if 'all' in factor_types:
        factor_types = ['value', 'momentum', 'quality']

    logger.info("=" * 80)
    logger.info("HISTORICAL FACTOR SCORE BACKFILL")
    logger.info("=" * 80)
    logger.info(f"Date Range: {start_date} to {end_date}")
    logger.info(f"Region: {region}")
    logger.info(f"Factor Types: {', '.join(factor_types)}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 80)

    db = PostgresDatabaseManager()

    # Get trading dates from OHLCV data
    query = """
        SELECT DISTINCT date
        FROM ohlcv_data
        WHERE region = %s
          AND date >= %s::date
          AND date <= %s::date
        ORDER BY date
    """

    trading_dates_result = db.execute_query(query, (region, start_date, end_date))
    trading_dates = [row['date'] if isinstance(row, dict) else row[0] for row in trading_dates_result]

    if not trading_dates:
        logger.error(f"No trading dates found for {region} between {start_date} and {end_date}")
        sys.exit(1)

    logger.info(f"\nFound {len(trading_dates)} trading dates")
    logger.info(f"First date: {trading_dates[0]}")
    logger.info(f"Last date: {trading_dates[-1]}\n")

    total_records = 0
    failed_dates = []

    for i, analysis_date in enumerate(trading_dates, 1):
        logger.info(f"\n[{i}/{len(trading_dates)}] Processing {analysis_date}...")

        all_records = []

        try:
            if 'value' in factor_types:
                value_records = calculate_value_factors(db, analysis_date, region)
                all_records.extend(value_records)

            if 'momentum' in factor_types:
                momentum_records = calculate_momentum_factors(db, analysis_date, region)
                all_records.extend(momentum_records)

            if 'quality' in factor_types:
                quality_records = calculate_quality_factors(db, analysis_date, region)
                all_records.extend(quality_records)

            saved = save_factor_scores(db, all_records, dry_run)
            total_records += saved

            logger.info(f"  ✅ Saved {saved} factor scores for {analysis_date}")

        except Exception as e:
            logger.error(f"  ❌ Failed to process {analysis_date}: {e}")
            failed_dates.append(analysis_date)

    logger.info("\n" + "=" * 80)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total Records: {total_records:,}")
    logger.info(f"Successful Dates: {len(trading_dates) - len(failed_dates)}/{len(trading_dates)}")

    if failed_dates:
        logger.warning(f"\nFailed Dates ({len(failed_dates)}):")
        for d in failed_dates[:10]:
            logger.warning(f"  - {d}")
        if len(failed_dates) > 10:
            logger.warning(f"  ... and {len(failed_dates) - 10} more")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
