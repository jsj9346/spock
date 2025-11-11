#!/usr/bin/env python3
"""
Calculate Low-Volatility Factors for Korean Stocks

This script calculates:
1. Historical Volatility (60-day annualized)
2. Maximum Drawdown (60-day peak-to-trough)
3. Beta (vs KOSPI - requires market index data)

Note: Beta factor is currently a placeholder and requires market index integration.
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
from modules.factors.low_vol_factors import (
    HistoricalVolatilityFactor,
    MaxDrawdownFactor
)


def load_ohlcv_data(db: PostgresDatabaseManager, ticker: str, days: int = 90) -> pd.DataFrame:
    """Load OHLCV data for a ticker"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    query = """
        SELECT date, open, high, low, close, volume
        FROM ohlcv_data
        WHERE ticker = %s
          AND region = 'KR'
          AND date >= %s
          AND date <= %s
        ORDER BY date ASC
    """

    result = db.execute_query(query, (ticker, start_date, end_date))

    if not result:
        return pd.DataFrame()

    df = pd.DataFrame(result)

    # Convert Decimal to float
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def calculate_factors_for_ticker(ticker: str, db: PostgresDatabaseManager) -> dict:
    """Calculate all Low-Vol factors for a single ticker"""

    # Load data (90 days to ensure we have 30+ valid days)
    data = load_ohlcv_data(db, ticker, days=90)

    # Require minimum 30 days instead of 60 for better coverage
    if len(data) < 30:
        logger.debug(f"{ticker}: Insufficient data ({len(data)} days)")
        return {}

    results = {}

    # Calculate Historical Volatility
    vol_factor = HistoricalVolatilityFactor()
    vol_result = vol_factor.calculate(data, ticker)
    if vol_result:
        results['Historical_Volatility'] = {
            'score': vol_result.raw_value,
            'percentile': None  # Will be calculated across all stocks
        }

    # Calculate Maximum Drawdown
    dd_factor = MaxDrawdownFactor()
    dd_result = dd_factor.calculate(data, ticker)
    if dd_result:
        results['Max_Drawdown'] = {
            'score': dd_result.raw_value,
            'percentile': None  # Will be calculated across all stocks
        }

    return results


def main():
    """Main execution"""
    logger.info("=== Low-Volatility Factor Calculation ===\n")

    db = PostgresDatabaseManager()

    # Get list of active Korean tickers
    logger.info("📊 Loading active Korean tickers...")
    query = """
        SELECT DISTINCT t.ticker, t.name
        FROM tickers t
        WHERE t.region = 'KR'
          AND EXISTS (
              SELECT 1 FROM ohlcv_data o
              WHERE o.ticker = t.ticker
                AND o.region = 'KR'
                AND o.date >= CURRENT_DATE - INTERVAL '90 days'
          )
        ORDER BY t.ticker
    """

    tickers = db.execute_query(query)

    if not tickers:
        logger.error("❌ No tickers found!")
        sys.exit(1)

    ticker_list = [row['ticker'] for row in tickers]
    ticker_names = {row['ticker']: row['name'] for row in tickers}

    logger.info(f"✅ Found {len(ticker_list)} active tickers\n")

    # Calculate factors for all tickers
    logger.info("📈 Calculating Low-Vol factors...")

    all_results = {}
    success_count = 0

    for idx, ticker in enumerate(ticker_list, 1):
        if idx % 50 == 0:
            logger.info(f"   Progress: {idx}/{len(ticker_list)} tickers processed...")

        try:
            results = calculate_factors_for_ticker(ticker, db)
            if results:
                all_results[ticker] = results
                success_count += 1
        except Exception as e:
            logger.error(f"❌ {ticker}: {e}")

    logger.info(f"✅ Successfully calculated factors for {success_count}/{len(ticker_list)} tickers\n")

    if not all_results:
        logger.error("❌ No factors calculated!")
        sys.exit(1)

    # Convert to DataFrames for percentile calculation
    logger.info("📊 Calculating percentile rankings...")

    factor_dfs = {}

    for factor_name in ['Historical_Volatility', 'Max_Drawdown']:
        data = []
        for ticker, factors in all_results.items():
            if factor_name in factors:
                data.append({
                    'ticker': ticker,
                    'score': factors[factor_name]['score']
                })

        if data:
            df = pd.DataFrame(data)
            df['percentile'] = df['score'].rank(pct=True) * 100
            factor_dfs[factor_name] = df

            logger.info(f"   {factor_name}: {len(df)} stocks")
            logger.info(f"      Score range: {df['score'].min():.2f} to {df['score'].max():.2f}")

    # Display top stocks by combined Low-Vol score
    logger.info("\n🏆 Top 20 Low-Volatility Stocks...")
    logger.info("=" * 90)
    logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'Vol Score':<12}{'DD Score':<12}{'Combined':<8}")
    logger.info("=" * 90)

    # Merge factors
    if 'Historical_Volatility' in factor_dfs and 'Max_Drawdown' in factor_dfs:
        combined = pd.merge(
            factor_dfs['Historical_Volatility'][['ticker', 'percentile']].rename(
                columns={'percentile': 'vol_percentile'}
            ),
            factor_dfs['Max_Drawdown'][['ticker', 'percentile']].rename(
                columns={'percentile': 'dd_percentile'}
            ),
            on='ticker',
            how='inner'
        )

        combined['combined_score'] = (combined['vol_percentile'] + combined['dd_percentile']) / 2
        combined = combined.sort_values('combined_score', ascending=False)
        combined['name'] = combined['ticker'].map(ticker_names)

        for idx, (_, row) in enumerate(combined.head(20).iterrows(), 1):
            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{row['name'][:28]:<30}"
                f"{row['vol_percentile']:<12.1f}"
                f"{row['dd_percentile']:<12.1f}"
                f"{row['combined_score']:<8.1f}"
            )

    # Save to database
    logger.info("\n💾 Saving to database...")

    records = []
    target_date = date.today()

    for factor_name, df in factor_dfs.items():
        for _, row in df.iterrows():
            records.append((
                row['ticker'], 'KR', target_date, factor_name,
                float(row['score']), float(row['percentile'])
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

    logger.info("\n✅ Low-Vol factor calculation complete!")
    logger.info(f"   Historical Volatility: {len(factor_dfs.get('Historical_Volatility', []))} stocks")
    logger.info(f"   Max Drawdown: {len(factor_dfs.get('Max_Drawdown', []))} stocks")
    logger.info(f"   Total records saved: {len(records)}")


if __name__ == "__main__":
    main()
