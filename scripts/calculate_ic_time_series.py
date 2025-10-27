#!/usr/bin/env python3
"""
IC (Information Coefficient) Time Series Calculation

Calculates the Information Coefficient for each factor across time to measure
predictive power of factors.

IC = Spearman rank correlation between factor scores and forward returns

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager


# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def get_factor_dates_with_forward_data(
    db: PostgresDatabaseManager,
    region: str = 'KR',
    holding_period: int = 21
) -> List[date]:
    """
    Get list of factor dates that have sufficient forward return data

    Args:
        db: Database manager
        region: Market region
        holding_period: Forward return period in days

    Returns:
        List of dates with forward return data available
    """
    query = """
        WITH factor_dates AS (
            SELECT DISTINCT date
            FROM factor_scores
            WHERE region = %s
            ORDER BY date
        ),
        date_coverage AS (
            SELECT
                fd.date as factor_date,
                EXISTS (
                    SELECT 1 FROM ohlcv_data o
                    WHERE o.region = %s
                      AND o.date >= fd.date + INTERVAL '%s days'
                      AND o.date <= fd.date + INTERVAL '%s days'
                ) as has_forward_data
            FROM factor_dates fd
        )
        SELECT factor_date
        FROM date_coverage
        WHERE has_forward_data = TRUE
        ORDER BY factor_date
    """

    result = db.execute_query(
        query,
        (region, region, holding_period, holding_period + 10)
    )

    if not result:
        return []

    return [row['factor_date'] if isinstance(row, dict) else row[0] for row in result]


def calculate_forward_returns(
    db: PostgresDatabaseManager,
    analysis_date: date,
    region: str,
    holding_period: int = 21
) -> pd.DataFrame:
    """
    Calculate forward returns for all stocks

    Args:
        db: Database manager
        analysis_date: Factor calculation date
        region: Market region
        holding_period: Forward return period (trading days)

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
              AND date = %s::date
        ),
        future_prices AS (
            SELECT
                ticker,
                close as future_close,
                date,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) as rn
            FROM ohlcv_data
            WHERE region = %s
              AND date > %s::date
              AND date <= %s::date + INTERVAL '30 days'
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
            bp.base_close,
            tp.future_close,
            (tp.future_close / bp.base_close) - 1 as forward_return
        FROM base_prices bp
        INNER JOIN target_prices tp ON bp.ticker = tp.ticker
        WHERE bp.base_close > 0
          AND tp.future_close > 0
        ORDER BY bp.ticker
    """

    result = db.execute_query(
        query,
        (region, analysis_date, region, analysis_date, analysis_date, holding_period)
    )

    if not result:
        return pd.DataFrame()

    df = pd.DataFrame(result)
    df['forward_return'] = pd.to_numeric(df['forward_return'], errors='coerce')

    return df[['ticker', 'forward_return']].dropna()


def calculate_ic_for_date(
    db: PostgresDatabaseManager,
    analysis_date: date,
    region: str,
    holding_period: int = 21
) -> Dict[str, Dict]:
    """
    Calculate IC for all factors on a specific date

    Args:
        db: Database manager
        analysis_date: Analysis date
        region: Market region
        holding_period: Forward return period

    Returns:
        Dict mapping factor_name to IC results
        {
            'PE_Ratio': {
                'ic': 0.15,
                'p_value': 0.001,
                'num_stocks': 100,
                'is_significant': True
            },
            ...
        }
    """
    # Get forward returns
    forward_returns = calculate_forward_returns(db, analysis_date, region, holding_period)

    if forward_returns.empty:
        logger.warning(f"  No forward return data for {analysis_date}")
        return {}

    # Get factor scores
    query = """
        SELECT
            ticker,
            factor_name,
            score,
            percentile
        FROM factor_scores
        WHERE region = %s
          AND date = %s::date
        ORDER BY ticker, factor_name
    """

    factor_scores = db.execute_query(query, (region, analysis_date))

    if not factor_scores:
        logger.warning(f"  No factor scores for {analysis_date}")
        return {}

    df_factors = pd.DataFrame(factor_scores)
    df_factors['score'] = pd.to_numeric(df_factors['score'], errors='coerce')

    # Merge with forward returns
    df_merged = df_factors.merge(forward_returns, on='ticker', how='inner')

    if df_merged.empty:
        logger.warning(f"  No matching tickers for {analysis_date}")
        return {}

    # Calculate IC for each factor
    ic_results = {}

    for factor_name in df_merged['factor_name'].unique():
        factor_data = df_merged[df_merged['factor_name'] == factor_name].copy()

        if len(factor_data) < 10:  # Need minimum sample size
            continue

        # Calculate Spearman correlation
        try:
            ic, p_value = spearmanr(
                factor_data['score'],
                factor_data['forward_return']
            )

            ic_results[factor_name] = {
                'ic': float(ic) if not np.isnan(ic) else 0.0,
                'p_value': float(p_value) if not np.isnan(p_value) else 1.0,
                'num_stocks': len(factor_data),
                'is_significant': p_value < 0.05 if not np.isnan(p_value) else False
            }
        except Exception as e:
            logger.error(f"  Error calculating IC for {factor_name}: {e}")
            continue

    return ic_results


def save_ic_results(
    db: PostgresDatabaseManager,
    analysis_date: date,
    region: str,
    holding_period: int,
    ic_results: Dict[str, Dict]
) -> int:
    """
    Save IC results to database

    Creates table if not exists:
    CREATE TABLE ic_time_series (
        id BIGSERIAL PRIMARY KEY,
        factor_name VARCHAR(50) NOT NULL,
        date DATE NOT NULL,
        region VARCHAR(2) NOT NULL,
        holding_period INTEGER NOT NULL,
        ic DECIMAL(10, 6),
        p_value DECIMAL(10, 6),
        num_stocks INTEGER,
        is_significant BOOLEAN,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (factor_name, date, region, holding_period)
    );

    Returns:
        Number of records saved
    """
    # Create table if not exists
    create_table_query = """
        CREATE TABLE IF NOT EXISTS ic_time_series (
            id BIGSERIAL PRIMARY KEY,
            factor_name VARCHAR(50) NOT NULL,
            date DATE NOT NULL,
            region VARCHAR(2) NOT NULL,
            holding_period INTEGER NOT NULL,
            ic DECIMAL(10, 6),
            p_value DECIMAL(10, 6),
            num_stocks INTEGER,
            is_significant BOOLEAN,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (factor_name, date, region, holding_period)
        );

        CREATE INDEX IF NOT EXISTS idx_ic_factor_date
        ON ic_time_series(factor_name, date DESC);

        CREATE INDEX IF NOT EXISTS idx_ic_date
        ON ic_time_series(date DESC);
    """

    db.execute_update(create_table_query)

    if not ic_results:
        return 0

    # Prepare records
    records = []
    for factor_name, ic_data in ic_results.items():
        records.append((
            factor_name,
            analysis_date,
            region,
            holding_period,
            float(ic_data['ic']),
            float(ic_data['p_value']),
            int(ic_data['num_stocks']),
            bool(ic_data['is_significant'])  # Convert numpy.bool to Python bool
        ))

    # Insert records (ON CONFLICT DO UPDATE)
    insert_query = """
        INSERT INTO ic_time_series
            (factor_name, date, region, holding_period, ic, p_value, num_stocks, is_significant)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (factor_name, date, region, holding_period)
        DO UPDATE SET
            ic = EXCLUDED.ic,
            p_value = EXCLUDED.p_value,
            num_stocks = EXCLUDED.num_stocks,
            is_significant = EXCLUDED.is_significant,
            created_at = NOW()
    """

    saved_count = 0
    for record in records:
        try:
            db.execute_update(insert_query, record)
            saved_count += 1
        except Exception as e:
            logger.error(f"  Error saving IC for {record[0]}: {e}")

    return saved_count


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Calculate IC Time Series')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--region', type=str, default='KR', help='Market region')
    parser.add_argument('--holding-period', type=int, default=21, help='Forward return period (days)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')

    args = parser.parse_args()

    region = args.region
    holding_period = args.holding_period
    dry_run = args.dry_run

    logger.info("=" * 80)
    logger.info("IC TIME SERIES CALCULATION")
    logger.info("=" * 80)
    logger.info(f"Region: {region}")
    logger.info(f"Holding Period: {holding_period} days")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 80)

    # Initialize database
    db = PostgresDatabaseManager()

    # Get dates with forward return data
    logger.info("\nFinding dates with forward return data...")
    valid_dates = get_factor_dates_with_forward_data(db, region, holding_period)

    if not valid_dates:
        logger.error("No dates with forward return data found")
        return

    # Filter by date range if specified
    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        valid_dates = [d for d in valid_dates if d >= start_date]

    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        valid_dates = [d for d in valid_dates if d <= end_date]

    logger.info(f"\nFound {len(valid_dates)} valid dates")
    logger.info(f"First date: {valid_dates[0]}")
    logger.info(f"Last date: {valid_dates[-1]}")

    # Calculate IC for each date
    total_ic_records = 0
    failed_dates = []

    for i, analysis_date in enumerate(valid_dates, 1):
        logger.info(f"\n[{i}/{len(valid_dates)}] Processing {analysis_date}...")

        try:
            ic_results = calculate_ic_for_date(db, analysis_date, region, holding_period)

            if ic_results:
                if dry_run:
                    logger.info(f"  [DRY RUN] Would save {len(ic_results)} IC values")
                    for factor_name, ic_data in ic_results.items():
                        sig = "✓" if ic_data['is_significant'] else "✗"
                        logger.info(f"    {factor_name}: IC={ic_data['ic']:+.4f} (p={ic_data['p_value']:.4f}) [{ic_data['num_stocks']} stocks] {sig}")
                else:
                    saved = save_ic_results(db, analysis_date, region, holding_period, ic_results)
                    total_ic_records += saved
                    logger.info(f"  ✅ Saved {saved} IC values")
            else:
                logger.warning(f"  ⚠️  No IC results for {analysis_date}")
                failed_dates.append(analysis_date)

        except Exception as e:
            logger.error(f"  ❌ Failed to process {analysis_date}: {e}")
            failed_dates.append(analysis_date)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("IC CALCULATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total IC Records: {total_ic_records:,}")
    logger.info(f"Successful Dates: {len(valid_dates) - len(failed_dates)}/{len(valid_dates)}")

    if failed_dates:
        logger.warning(f"\nFailed Dates ({len(failed_dates)}):")
        for failed_date in failed_dates[:10]:  # Show first 10
            logger.warning(f"  - {failed_date}")
        if len(failed_dates) > 10:
            logger.warning(f"  ... and {len(failed_dates) - 10} more")

    logger.info("=" * 80)


if __name__ == '__main__':
    main()
