#!/usr/bin/env python3
"""
Calculate Size Factors for Korean Stocks

This script calculates:
1. Market Cap - Market capitalization from fundamentals
2. Liquidity - Average daily trading volume

Note: Free Float factor requires additional data not yet available.
"""

import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from loguru import logger
import pandas as pd
import numpy as np
import math

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_market_cap_scores(db: PostgresDatabaseManager) -> pd.DataFrame:
    """Calculate Market Cap factor from ticker_fundamentals"""

    logger.info("📊 Loading market cap data...")

    query = """
        WITH latest_fundamentals AS (
            SELECT
                tf.ticker,
                tf.region,
                tf.market_cap,
                tf.date,
                ROW_NUMBER() OVER (PARTITION BY tf.ticker ORDER BY tf.date DESC) as rn
            FROM ticker_fundamentals tf
            WHERE tf.region = 'KR'
              AND tf.market_cap IS NOT NULL
              AND tf.market_cap > 0
        )
        SELECT ticker, region, market_cap
        FROM latest_fundamentals
        WHERE rn = 1
        ORDER BY ticker
    """

    fundamentals = db.execute_query(query)

    if not fundamentals:
        logger.warning("No market cap data found!")
        return pd.DataFrame()

    df = pd.DataFrame(fundamentals)
    df['market_cap'] = pd.to_numeric(df['market_cap'], errors='coerce')

    # Remove invalid values
    df = df[(df['market_cap'] > 0) & (df['market_cap'].notna())]

    if len(df) == 0:
        logger.warning("No valid market cap data after filtering!")
        return pd.DataFrame()

    # Calculate factor value: Negative log for small-cap tilt
    # Lower market cap → Higher factor score (small-cap premium)
    df['raw_score'] = -np.log10(df['market_cap'] / 1e12)  # Normalize to trillions of KRW

    # Calculate percentile
    df['percentile'] = df['raw_score'].rank(pct=True) * 100

    logger.info(f"✅ Market Cap factor for {len(df)} stocks")
    logger.info(f"   Range: {df['market_cap'].min()/1e12:.2f}T - {df['market_cap'].max()/1e12:.2f}T KRW")

    return df[['ticker', 'region', 'raw_score', 'percentile', 'market_cap']]


def calculate_liquidity_scores(db: PostgresDatabaseManager) -> pd.DataFrame:
    """Calculate Liquidity factor from OHLCV data"""

    logger.info("📊 Loading liquidity data...")

    # Get average daily trading value over last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=60)  # Get 60 days to ensure 30+ trading days

    query = """
        WITH daily_values AS (
            SELECT
                ticker,
                region,
                date,
                volume * close as trading_value
            FROM ohlcv_data
            WHERE region = 'KR'
              AND date >= %s
              AND date <= %s
              AND volume > 0
              AND close > 0
        ),
        avg_liquidity AS (
            SELECT
                ticker,
                region,
                AVG(trading_value) as avg_trading_value,
                COUNT(*) as trading_days
            FROM daily_values
            GROUP BY ticker, region
            HAVING COUNT(*) >= 20
        )
        SELECT ticker, region, avg_trading_value, trading_days
        FROM avg_liquidity
        ORDER BY ticker
    """

    result = db.execute_query(query, (start_date, end_date))

    if not result:
        logger.warning("No liquidity data found!")
        return pd.DataFrame()

    df = pd.DataFrame(result)
    df['avg_trading_value'] = pd.to_numeric(df['avg_trading_value'], errors='coerce')

    # Remove invalid values
    df = df[(df['avg_trading_value'] > 0) & (df['avg_trading_value'].notna())]

    if len(df) == 0:
        logger.warning("No valid liquidity data after filtering!")
        return pd.DataFrame()

    # Calculate factor value: Log scale for liquidity
    # Higher liquidity → Higher factor score
    df['raw_score'] = np.log10(df['avg_trading_value'] / 1e8)  # Normalize to 100M KRW

    # Calculate percentile
    df['percentile'] = df['raw_score'].rank(pct=True) * 100

    logger.info(f"✅ Liquidity factor for {len(df)} stocks")
    logger.info(f"   Avg trading days: {df['trading_days'].mean():.1f}")
    logger.info(f"   Range: {df['avg_trading_value'].min()/1e8:.2f}억 - {df['avg_trading_value'].max()/1e8:.2f}억 KRW")

    return df[['ticker', 'region', 'raw_score', 'percentile', 'avg_trading_value']]


def main():
    """Main execution"""
    logger.info("=== Size Factor Calculation ===\n")

    db = PostgresDatabaseManager()

    # Calculate Market Cap factor
    market_cap_df = calculate_market_cap_scores(db)

    # Calculate Liquidity factor
    liquidity_df = calculate_liquidity_scores(db)

    if market_cap_df.empty and liquidity_df.empty:
        logger.error("❌ No factors calculated!")
        sys.exit(1)

    # Get ticker names for display
    query = "SELECT ticker, name FROM tickers WHERE region = 'KR'"
    ticker_names_result = db.execute_query(query)
    ticker_names = {row['ticker']: row['name'] for row in ticker_names_result}

    # Display combined results
    if not market_cap_df.empty and not liquidity_df.empty:
        logger.info("\n🏆 Top 20 Size Factor Stocks (Combined Score)...")
        logger.info("=" * 95)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'Market Cap':<15}{'Liquidity':<15}{'Combined':<8}")
        logger.info("=" * 95)

        combined = pd.merge(
            market_cap_df[['ticker', 'percentile', 'market_cap']].rename(
                columns={'percentile': 'mc_percentile'}
            ),
            liquidity_df[['ticker', 'percentile', 'avg_trading_value']].rename(
                columns={'percentile': 'liq_percentile'}
            ),
            on='ticker',
            how='inner'
        )

        combined['combined_score'] = (combined['mc_percentile'] + combined['liq_percentile']) / 2
        combined = combined.sort_values('combined_score', ascending=False)
        combined['name'] = combined['ticker'].map(ticker_names)

        for idx, (_, row) in enumerate(combined.head(20).iterrows(), 1):
            market_cap_str = f"{row['market_cap']/1e12:.2f}T"
            liquidity_str = f"{row['avg_trading_value']/1e8:.0f}억"
            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{row['name'][:28] if row['name'] else 'N/A':<30}"
                f"{market_cap_str:<15}"
                f"{liquidity_str:<15}"
                f"{row['combined_score']:<8.1f}"
            )

    # Save to database
    logger.info("\n💾 Saving to database...")

    records = []
    target_date = date.today()

    if not market_cap_df.empty:
        for _, row in market_cap_df.iterrows():
            records.append((
                row['ticker'], row['region'], target_date, 'Market_Cap',
                float(row['raw_score']), float(row['percentile'])
            ))

    if not liquidity_df.empty:
        for _, row in liquidity_df.iterrows():
            records.append((
                row['ticker'], row['region'], target_date, 'Liquidity',
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

    logger.info("\n✅ Size factor calculation complete!")
    logger.info(f"   Market Cap: {len(market_cap_df)} stocks")
    logger.info(f"   Liquidity: {len(liquidity_df)} stocks")
    logger.info(f"   Total records saved: {len(records)}")


if __name__ == "__main__":
    main()
