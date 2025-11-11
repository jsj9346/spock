#!/usr/bin/env python3
"""
Calculate Additional Momentum Factors for Korean Stocks

This script calculates:
1. 3M Momentum - 3-month (63 trading days) return
2. 6M Momentum - 6-month (126 trading days) return
3. 52-Week High Ratio - Current price / 52-week high

All factors measure price momentum and trend following.
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_momentum_factor(db: PostgresDatabaseManager, lookback_days: int, factor_name: str) -> pd.DataFrame:
    """
    Calculate momentum factor for given lookback period

    Args:
        lookback_days: Number of trading days to look back
        factor_name: Name of the factor (e.g., '3M_Momentum')
    """
    logger.info(f"📊 Calculating {factor_name} ({lookback_days} days)...")

    end_date = date.today()
    start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # Buffer for weekends/holidays

    query = """
        WITH price_data AS (
            SELECT
                ticker,
                region,
                date,
                close,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as row_desc,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date ASC) as row_asc
            FROM ohlcv_data
            WHERE region = 'KR'
              AND date >= %s
              AND date <= %s
              AND close > 0
        ),
        latest_prices AS (
            SELECT ticker, close as current_price
            FROM price_data
            WHERE row_desc = 1
        ),
        past_prices AS (
            SELECT ticker, close as past_price
            FROM price_data
            WHERE row_asc = 1
        ),
        date_counts AS (
            SELECT ticker, COUNT(*) as trading_days
            FROM price_data
            GROUP BY ticker
            HAVING COUNT(*) >= %s
        )
        SELECT
            dc.ticker,
            'KR' as region,
            lp.current_price,
            pp.past_price,
            dc.trading_days
        FROM date_counts dc
        JOIN latest_prices lp ON dc.ticker = lp.ticker
        JOIN past_prices pp ON dc.ticker = pp.ticker
        WHERE lp.current_price > 0 AND pp.past_price > 0
        ORDER BY dc.ticker
    """

    min_required_days = int(lookback_days * 0.8)  # Allow 20% tolerance
    result = db.execute_query(query, (start_date, end_date, min_required_days))

    if not result:
        logger.warning(f"No data found for {factor_name}!")
        return pd.DataFrame()

    df = pd.DataFrame(result)

    # Convert to numeric
    df['current_price'] = pd.to_numeric(df['current_price'], errors='coerce')
    df['past_price'] = pd.to_numeric(df['past_price'], errors='coerce')

    # Calculate return
    df['return'] = (df['current_price'] / df['past_price'] - 1) * 100  # Percentage

    # Remove invalid values
    df = df[(df['return'].notna()) & (df['return'].abs() < 1000)]  # Remove extreme outliers

    if len(df) == 0:
        logger.warning(f"No valid data for {factor_name} after filtering!")
        return pd.DataFrame()

    # Factor value = return (higher return = higher score)
    df['raw_score'] = df['return']

    # Calculate percentile
    df['percentile'] = df['raw_score'].rank(pct=True) * 100

    logger.info(f"✅ {factor_name} for {len(df)} stocks")
    logger.info(f"   Return range: {df['return'].min():.2f}% - {df['return'].max():.2f}%")
    logger.info(f"   Avg trading days: {df['trading_days'].mean():.1f}")

    return df[['ticker', 'region', 'raw_score', 'percentile', 'return']]


def calculate_52week_high_ratio(db: PostgresDatabaseManager) -> pd.DataFrame:
    """Calculate 52-week high ratio factor"""

    logger.info("📊 Calculating 52-Week High Ratio...")

    end_date = date.today()
    start_date = end_date - timedelta(days=380)  # ~52 weeks + buffer

    query = """
        WITH price_history AS (
            SELECT
                ticker,
                region,
                close,
                MAX(close) OVER (PARTITION BY ticker) as high_52w,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
            FROM ohlcv_data
            WHERE region = 'KR'
              AND date >= %s
              AND date <= %s
              AND close > 0
        ),
        current_data AS (
            SELECT
                ticker,
                region,
                close as current_price,
                high_52w
            FROM price_history
            WHERE rn = 1
        ),
        date_counts AS (
            SELECT ticker, COUNT(*) as trading_days
            FROM ohlcv_data
            WHERE region = 'KR'
              AND date >= %s
              AND date <= %s
            GROUP BY ticker
            HAVING COUNT(*) >= 200  -- Require ~200 trading days for 52 weeks
        )
        SELECT
            cd.ticker,
            cd.region,
            cd.current_price,
            cd.high_52w,
            dc.trading_days
        FROM current_data cd
        JOIN date_counts dc ON cd.ticker = dc.ticker
        WHERE cd.high_52w > 0
        ORDER BY cd.ticker
    """

    result = db.execute_query(query, (start_date, end_date, start_date, end_date))

    if not result:
        logger.warning("No data found for 52-Week High Ratio!")
        return pd.DataFrame()

    df = pd.DataFrame(result)

    # Convert to numeric
    df['current_price'] = pd.to_numeric(df['current_price'], errors='coerce')
    df['high_52w'] = pd.to_numeric(df['high_52w'], errors='coerce')

    # Calculate ratio
    df['ratio'] = (df['current_price'] / df['high_52w']) * 100  # Percentage of 52-week high

    # Remove invalid values
    df = df[(df['ratio'] > 0) & (df['ratio'] <= 105)]  # Allow slight overshoot

    if len(df) == 0:
        logger.warning("No valid data for 52-Week High Ratio after filtering!")
        return pd.DataFrame()

    # Factor value = ratio (higher ratio = higher score, closer to highs)
    df['raw_score'] = df['ratio']

    # Calculate percentile
    df['percentile'] = df['raw_score'].rank(pct=True) * 100

    logger.info(f"✅ 52-Week High Ratio for {len(df)} stocks")
    logger.info(f"   Ratio range: {df['ratio'].min():.1f}% - {df['ratio'].max():.1f}%")
    logger.info(f"   Avg trading days: {df['trading_days'].mean():.1f}")

    return df[['ticker', 'region', 'raw_score', 'percentile', 'ratio']]


def main():
    """Main execution"""
    logger.info("=== Additional Momentum Factor Calculation ===\n")

    db = PostgresDatabaseManager()

    # Calculate 3M Momentum (63 trading days)
    momentum_3m = calculate_momentum_factor(db, 63, '3M_Momentum')

    # Calculate 6M Momentum (126 trading days)
    momentum_6m = calculate_momentum_factor(db, 126, '6M_Momentum')

    # Calculate 52-Week High Ratio
    high_52w = calculate_52week_high_ratio(db)

    if momentum_3m.empty and momentum_6m.empty and high_52w.empty:
        logger.error("❌ No factors calculated!")
        sys.exit(1)

    # Get ticker names
    query = "SELECT ticker, name FROM tickers WHERE region = 'KR'"
    ticker_names_result = db.execute_query(query)
    ticker_names = {row['ticker']: row['name'] for row in ticker_names_result}

    # Display top momentum stocks
    if not momentum_6m.empty:
        logger.info("\n🏆 Top 20 Momentum Stocks (6M)...")
        logger.info("=" * 85)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'3M Return':<12}{'6M Return':<12}{'Score':<8}")
        logger.info("=" * 85)

        if not momentum_3m.empty:
            combined = pd.merge(
                momentum_3m[['ticker', 'return']].rename(columns={'return': 'return_3m'}),
                momentum_6m[['ticker', 'percentile', 'return']].rename(columns={'return': 'return_6m'}),
                on='ticker',
                how='inner'
            )
            combined = combined.sort_values('percentile', ascending=False)
            combined['name'] = combined['ticker'].map(ticker_names)

            for idx, (_, row) in enumerate(combined.head(20).iterrows(), 1):
                name_str = str(row['name']) if pd.notna(row['name']) else 'N/A'
                logger.info(
                    f"{idx:<6}"
                    f"{row['ticker']:<8}"
                    f"{name_str[:28]:<30}"
                    f"{row['return_3m']:.2f}%{'':<6}"
                    f"{row['return_6m']:.2f}%{'':<6}"
                    f"{row['percentile']:<8.1f}"
                )

    # Save to database
    logger.info("\n💾 Saving to database...")

    records = []
    target_date = date.today()

    for df, factor_name in [
        (momentum_3m, '3M_Momentum'),
        (momentum_6m, '6M_Momentum'),
        (high_52w, '52W_High_Ratio')
    ]:
        if not df.empty:
            for _, row in df.iterrows():
                records.append((
                    row['ticker'], row['region'], target_date, factor_name,
                    float(row['raw_score']), float(row['percentile'])
                ))

    if records:
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

            logger.info(f"✅ Saved {len(records)} factor scores")
        except Exception as e:
            logger.error(f"❌ Failed to save: {e}")
            sys.exit(1)

    logger.info("\n✅ Momentum factor calculation complete!")
    logger.info(f"   3M Momentum: {len(momentum_3m)} stocks")
    logger.info(f"   6M Momentum: {len(momentum_6m)} stocks")
    logger.info(f"   52-Week High Ratio: {len(high_52w)} stocks")
    logger.info(f"   Total records saved: {len(records)}")


if __name__ == "__main__":
    main()
