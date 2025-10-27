#!/usr/bin/env python3
"""
Calculate Momentum Factors for Korean Stocks using OHLCV data

Implements:
1. 12-Month Momentum (excluding last month to avoid short-term reversal)
2. RSI Momentum (14-day Relative Strength Index)
3. Short-Term Momentum (1-month return)
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


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index)

    Args:
        prices: Series of closing prices
        period: RSI period (default 14 days)

    Returns:
        RSI value (0-100), or None if insufficient data
    """
    if len(prices) < period + 1:
        return None

    # Calculate price changes
    deltas = prices.diff()

    # Separate gains and losses
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)

    # Calculate average gains and losses
    avg_gain = gains.rolling(window=period).mean().iloc[-1]
    avg_loss = losses.rolling(window=period).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_12m_momentum_factor(db: PostgresDatabaseManager) -> pd.DataFrame:
    """
    Calculate 12-month momentum factor

    Formula: (Price_today / Price_12m_ago) - 1
    Excludes last month to avoid short-term reversal effect
    """
    logger.info("📈 Calculating 12-Month Momentum...")

    # Get date range (need ~252 trading days for 12 months)
    end_date = date.today()
    start_date = end_date - timedelta(days=400)  # ~13 months

    # Load OHLCV data
    query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date >= %s AND date <= %s
        ORDER BY ticker, date
    """

    ohlcv_data = db.execute_query(query, (start_date, end_date))

    if not ohlcv_data:
        logger.error("❌ No OHLCV data found")
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv_data)
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Pivot to get ticker columns
    prices = df.pivot(index='date', columns='ticker', values='close')

    # Calculate 12-month momentum (excluding last month)
    # 220 trading days ≈ 11 months, 252 ≈ 12 months
    results = []

    for ticker in prices.columns:
        ticker_prices = prices[ticker].dropna()

        if len(ticker_prices) < 220:  # Need at least 11 months
            continue

        # Price 11 months ago (excluding last month)
        price_11m_ago = ticker_prices.iloc[0]

        # Current price
        current_price = ticker_prices.iloc[-1]

        # Calculate momentum
        momentum = (current_price / price_11m_ago - 1) * 100  # Percentage

        results.append({
            'ticker': ticker,
            'region': 'KR',
            'date': end_date,
            'factor_name': '12M_Momentum',
            'raw_value': momentum,
            'price_11m_ago': price_11m_ago,
            'current_price': current_price
        })

    if not results:
        logger.warning("No valid 12M momentum data")
        return pd.DataFrame()

    df_momentum = pd.DataFrame(results)

    # Calculate percentile and z-score
    df_momentum['percentile'] = df_momentum['raw_value'].rank(pct=True) * 100

    mean = df_momentum['raw_value'].mean()
    std = df_momentum['raw_value'].std()
    df_momentum['z_score'] = (df_momentum['raw_value'] - mean) / std if std > 0 else 0

    logger.info(f"✅ Calculated 12M Momentum for {len(df_momentum)} stocks")
    logger.info(f"   Momentum range: {df_momentum['raw_value'].min():.2f}% - {df_momentum['raw_value'].max():.2f}%")
    logger.info(f"   Mean: {mean:.2f}%, Std: {std:.2f}%")

    return df_momentum[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'raw_value']]


def calculate_rsi_momentum_factor(db: PostgresDatabaseManager) -> pd.DataFrame:
    """
    Calculate RSI Momentum factor

    RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss over 14 days

    Optimal range: 50-70 (bullish momentum without overbought)
    """
    logger.info("📈 Calculating RSI Momentum...")

    # Get recent data (60 days for RSI calculation)
    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date >= %s AND date <= %s
        ORDER BY ticker, date
    """

    ohlcv_data = db.execute_query(query, (start_date, end_date))

    if not ohlcv_data:
        logger.error("❌ No OHLCV data found")
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv_data)
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Pivot to get ticker columns
    prices = df.pivot(index='date', columns='ticker', values='close')

    # Calculate RSI for each ticker
    results = []

    for ticker in prices.columns:
        ticker_prices = prices[ticker].dropna()

        if len(ticker_prices) < 30:  # Need at least 30 days
            continue

        rsi = calculate_rsi(ticker_prices, period=14)

        if rsi is None:
            continue

        # Transform RSI to score (optimal range: 50-70)
        # Score higher for RSI in bullish range without being overbought
        if 50 <= rsi <= 70:
            score = rsi  # Positive score in optimal range
        elif rsi > 70:
            score = 70 - (rsi - 70) * 0.5  # Penalty for overbought
        else:
            score = rsi * 0.8  # Lower score for weak momentum

        results.append({
            'ticker': ticker,
            'region': 'KR',
            'date': end_date,
            'factor_name': 'RSI_Momentum',
            'raw_value': score,
            'rsi': rsi
        })

    if not results:
        logger.warning("No valid RSI data")
        return pd.DataFrame()

    df_rsi = pd.DataFrame(results)

    # Calculate percentile and z-score
    df_rsi['percentile'] = df_rsi['raw_value'].rank(pct=True) * 100

    mean = df_rsi['raw_value'].mean()
    std = df_rsi['raw_value'].std()
    df_rsi['z_score'] = (df_rsi['raw_value'] - mean) / std if std > 0 else 0

    logger.info(f"✅ Calculated RSI Momentum for {len(df_rsi)} stocks")
    logger.info(f"   RSI range: {df_rsi['rsi'].min():.2f} - {df_rsi['rsi'].max():.2f}")
    logger.info(f"   Score range: {df_rsi['raw_value'].min():.2f} - {df_rsi['raw_value'].max():.2f}")

    return df_rsi[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'raw_value']]


def calculate_1m_momentum_factor(db: PostgresDatabaseManager) -> pd.DataFrame:
    """
    Calculate 1-month (short-term) momentum factor

    Formula: (Price_today / Price_1m_ago) - 1
    """
    logger.info("📈 Calculating 1-Month Momentum...")

    # Get date range (need ~30 trading days)
    end_date = date.today()
    start_date = end_date - timedelta(days=45)

    query = """
        SELECT ticker, date, close
        FROM ohlcv_data
        WHERE region = 'KR'
          AND date >= %s AND date <= %s
        ORDER BY ticker, date
    """

    ohlcv_data = db.execute_query(query, (start_date, end_date))

    if not ohlcv_data:
        logger.error("❌ No OHLCV data found")
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv_data)
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    # Pivot to get ticker columns
    prices = df.pivot(index='date', columns='ticker', values='close')

    # Calculate 1-month momentum
    results = []

    for ticker in prices.columns:
        ticker_prices = prices[ticker].dropna()

        if len(ticker_prices) < 20:  # Need at least 20 days
            continue

        # Price 1 month ago
        price_1m_ago = ticker_prices.iloc[0]

        # Current price
        current_price = ticker_prices.iloc[-1]

        # Calculate momentum
        momentum = (current_price / price_1m_ago - 1) * 100  # Percentage

        results.append({
            'ticker': ticker,
            'region': 'KR',
            'date': end_date,
            'factor_name': '1M_Momentum',
            'raw_value': momentum
        })

    if not results:
        logger.warning("No valid 1M momentum data")
        return pd.DataFrame()

    df_momentum = pd.DataFrame(results)

    # Calculate percentile and z-score
    df_momentum['percentile'] = df_momentum['raw_value'].rank(pct=True) * 100

    mean = df_momentum['raw_value'].mean()
    std = df_momentum['raw_value'].std()
    df_momentum['z_score'] = (df_momentum['raw_value'] - mean) / std if std > 0 else 0

    logger.info(f"✅ Calculated 1M Momentum for {len(df_momentum)} stocks")
    logger.info(f"   Momentum range: {df_momentum['raw_value'].min():.2f}% - {df_momentum['raw_value'].max():.2f}%")

    return df_momentum[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'raw_value']]


def main():
    """Main execution"""
    logger.info("=== Korean Stock Momentum Factor Calculation ===\n")

    db = PostgresDatabaseManager()

    # Calculate all momentum factors
    logger.info("📊 Calculating momentum factors...\n")

    momentum_12m = calculate_12m_momentum_factor(db)
    rsi_momentum = calculate_rsi_momentum_factor(db)
    momentum_1m = calculate_1m_momentum_factor(db)

    # Combine all results
    all_results = pd.concat([momentum_12m, rsi_momentum, momentum_1m], ignore_index=True)

    if all_results.empty:
        logger.error("❌ No momentum factors calculated!")
        sys.exit(1)

    logger.info(f"\n✅ Total momentum factors calculated: {len(all_results)}")
    logger.info(f"   12M Momentum: {len(momentum_12m)}")
    logger.info(f"   RSI Momentum: {len(rsi_momentum)}")
    logger.info(f"   1M Momentum: {len(momentum_1m)}")

    # Display top stocks by combined momentum score
    if len(momentum_12m) > 0 and len(rsi_momentum) > 0:
        logger.info("\n🏆 Top 20 Momentum Stocks (Combined 12M + RSI)...")

        combined = pd.merge(
            momentum_12m[['ticker', 'percentile']].rename(columns={'percentile': 'mom_12m'}),
            rsi_momentum[['ticker', 'percentile']].rename(columns={'percentile': 'rsi'}),
            on='ticker',
            how='inner'
        )

        combined['combined_score'] = (combined['mom_12m'] + combined['rsi']) / 2
        combined = combined.sort_values('combined_score', ascending=False)

        # Get stock names
        names_query = """
            SELECT ticker, name
            FROM tickers
            WHERE region = 'KR' AND ticker = ANY(%s)
        """
        names_data = db.execute_query(names_query, (combined['ticker'].tolist(),))
        names_dict = {row['ticker']: row['name'] for row in names_data}
        combined['name'] = combined['ticker'].map(names_dict)

        logger.info("=" * 80)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'12M%':<8}{'RSI%':<8}{'Score':<8}")
        logger.info("=" * 80)

        for idx, (i, row) in enumerate(combined.head(20).iterrows(), 1):
            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{row['name'][:28] if pd.notna(row['name']) else 'N/A':<30}"
                f"{row['mom_12m']:<8.1f}"
                f"{row['rsi']:<8.1f}"
                f"{row['combined_score']:<8.1f}"
            )

    # Save to database
    logger.info("\n💾 Saving to database...")

    records = []
    target_date = date.today()

    for _, row in all_results.iterrows():
        records.append((
            row['ticker'], row['region'], target_date, row['factor_name'],
            float(row['z_score']), float(row['percentile'])
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

            logger.info(f"✅ Saved {len(records)} momentum factor scores")
        except Exception as e:
            logger.error(f"❌ Failed to save: {e}")

    logger.info("\n✅ Momentum factor calculation complete!")


if __name__ == "__main__":
    main()
