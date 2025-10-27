#!/usr/bin/env python3
"""
Calculate Quality Factors for Korean Stocks using available fundamental data

Since ROE/ROA are not yet available in ticker_fundamentals, we use:
1. Earnings Quality (Low P/E + High Market Cap = Profitable large companies)
2. Financial Stability (PCR - Price to Cash Flow Ratio, lower is better)
3. Revenue Quality (PSR - Price to Sales Ratio, lower is better)
"""

import sys
from pathlib import Path
from datetime import datetime, date
from loguru import logger
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager


def calculate_earnings_quality_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Earnings Quality factor

    Formula: Low P/E ratio
    - Low P/E indicates profitability and value
    - Simple single-metric quality indicator

    Higher score = Better earnings quality (lower P/E)
    """
    # Filter for stocks with positive P/E
    valid = df[
        (df['per'].notna()) &
        (df['per'] > 0) &
        (df['per'] < 100)
    ].copy()

    if len(valid) == 0:
        logger.warning("No valid Earnings Quality data")
        return pd.DataFrame()

    # Invert P/E (lower P/E = higher score)
    valid['raw_score'] = -valid['per']
    valid['percentile'] = valid['raw_score'].rank(pct=True) * 100

    mean = valid['raw_score'].mean()
    std = valid['raw_score'].std()
    valid['z_score'] = (valid['raw_score'] - mean) / std if std > 0 else 0
    valid['factor_name'] = 'Earnings_Quality'

    logger.info(f"✅ Calculated Earnings Quality for {len(valid)} stocks")
    logger.info(f"   P/E range: {valid['per'].min():.2f} - {valid['per'].max():.2f}")

    return valid[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'per']]


def calculate_book_value_quality_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Book Value Quality factor

    Uses PBR (Price to Book Ratio)
    Lower PBR = Better book value quality = Higher quality

    Higher score = Better book value quality
    """
    valid = df[
        (df['pbr'].notna()) &
        (df['pbr'] > 0) &
        (df['pbr'] < 20)  # Filter outliers
    ].copy()

    if len(valid) == 0:
        logger.warning("No valid Book Value Quality data")
        return pd.DataFrame()

    # Invert PBR (lower PBR = higher score)
    valid['raw_score'] = -valid['pbr']
    valid['percentile'] = valid['raw_score'].rank(pct=True) * 100

    mean = valid['raw_score'].mean()
    std = valid['raw_score'].std()
    valid['z_score'] = (valid['raw_score'] - mean) / std if std > 0 else 0
    valid['factor_name'] = 'Book_Value_Quality'

    logger.info(f"✅ Calculated Book Value Quality for {len(valid)} stocks")
    logger.info(f"   PBR range: {valid['pbr'].min():.2f} - {valid['pbr'].max():.2f}")

    return valid[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'pbr']]


# Revenue Quality (PSR) removed - not available in pykrx data


def calculate_dividend_stability_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Dividend Stability factor

    Dividend yield > 0 indicates financial stability and shareholder-friendly policy
    Higher dividend yield (within reasonable range) = Higher quality

    Higher score = Better dividend stability
    """
    valid = df[
        (df['dividend_yield'].notna()) &
        (df['dividend_yield'] > 0) &
        (df['dividend_yield'] <= 15)  # Filter extreme values
    ].copy()

    if len(valid) == 0:
        logger.warning("No valid Dividend Stability data")
        return pd.DataFrame()

    # Higher dividend yield = higher score (but with diminishing returns)
    # Transform to reduce impact of very high yields (which may be unsustainable)
    valid['raw_score'] = np.sqrt(valid['dividend_yield'])
    valid['percentile'] = valid['raw_score'].rank(pct=True) * 100

    mean = valid['raw_score'].mean()
    std = valid['raw_score'].std()
    valid['z_score'] = (valid['raw_score'] - mean) / std if std > 0 else 0
    valid['factor_name'] = 'Dividend_Stability'

    logger.info(f"✅ Calculated Dividend Stability for {len(valid)} stocks")
    logger.info(f"   Dividend Yield range: {valid['dividend_yield'].min():.2f}% - {valid['dividend_yield'].max():.2f}%")

    return valid[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'dividend_yield']]


def main():
    """Main execution"""
    logger.info("=== Korean Stock Quality Factor Calculation ===\n")

    db = PostgresDatabaseManager()

    logger.info("📊 Loading Korean stock fundamentals...")

    # Load latest fundamental data
    query = """
        WITH latest_data AS (
            SELECT
                tf.ticker,
                tf.region,
                tf.date,
                tf.per,
                tf.pbr,
                tf.dividend_yield,
                t.name,
                ROW_NUMBER() OVER (PARTITION BY tf.ticker ORDER BY tf.date DESC) as rn
            FROM ticker_fundamentals tf
            JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
            WHERE tf.region = 'KR'
              AND tf.data_source = 'pykrx'
              AND (tf.per IS NOT NULL OR tf.pbr IS NOT NULL OR tf.dividend_yield IS NOT NULL)
        )
        SELECT ticker, region, date, per, pbr, dividend_yield, name
        FROM latest_data
        WHERE rn = 1
        ORDER BY ticker
    """

    fundamentals = db.execute_query(query)

    if not fundamentals:
        logger.error("❌ No fundamental data found!")
        sys.exit(1)

    df = pd.DataFrame(fundamentals)

    # Convert Decimal to float
    for col in ['per', 'pbr', 'dividend_yield']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    logger.info(f"✅ Loaded {len(df)} Korean stocks")

    logger.info("\n📈 Calculating quality factors...")

    # Calculate all quality factors (only those available from pykrx)
    earnings_quality = calculate_earnings_quality_factor(df)
    bookvalue_quality = calculate_book_value_quality_factor(df)
    dividend_stability = calculate_dividend_stability_factor(df)

    # Combine all results
    all_results = pd.concat([
        earnings_quality,
        bookvalue_quality,
        dividend_stability
    ], ignore_index=True)

    if all_results.empty:
        logger.error("❌ No quality factors calculated!")
        sys.exit(1)

    logger.info(f"\n✅ Total quality factors calculated: {len(all_results)}")
    logger.info(f"   Earnings Quality (P/E): {len(earnings_quality)}")
    logger.info(f"   Book Value Quality (P/B): {len(bookvalue_quality)}")
    logger.info(f"   Dividend Stability: {len(dividend_stability)}")

    # Display top stocks by combined quality score
    if len(earnings_quality) > 0 and len(bookvalue_quality) > 0:
        logger.info("\n🏆 Top 20 Quality Stocks (Combined Score)...")

        # Merge available quality factors
        combined = earnings_quality[['ticker', 'percentile']].rename(columns={'percentile': 'earnings_q'})

        if len(bookvalue_quality) > 0:
            combined = pd.merge(
                combined,
                bookvalue_quality[['ticker', 'percentile']].rename(columns={'percentile': 'bookval_q'}),
                on='ticker',
                how='outer'
            )

        if len(dividend_stability) > 0:
            combined = pd.merge(
                combined,
                dividend_stability[['ticker', 'percentile']].rename(columns={'percentile': 'div_q'}),
                on='ticker',
                how='outer'
            )

        # Calculate combined score (average of available factors)
        quality_cols = [col for col in ['earnings_q', 'bookval_q', 'div_q'] if col in combined.columns]
        combined['combined_score'] = combined[quality_cols].mean(axis=1)
        combined = combined.sort_values('combined_score', ascending=False)

        # Get stock names
        stock_names = df.set_index('ticker')['name'].to_dict()
        combined['name'] = combined['ticker'].map(stock_names)

        logger.info("=" * 100)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'Earn%':<8}{'Book%':<8}{'Div%':<8}{'Score':<8}")
        logger.info("=" * 100)

        for idx, (i, row) in enumerate(combined.head(20).iterrows(), 1):
            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{row['name'][:28] if pd.notna(row['name']) else 'N/A':<30}"
                f"{row.get('earnings_q', 0):<8.1f}"
                f"{row.get('bookval_q', 0):<8.1f}"
                f"{row.get('div_q', 0):<8.1f}"
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

            logger.info(f"✅ Saved {len(records)} quality factor scores")
        except Exception as e:
            logger.error(f"❌ Failed to save: {e}")

    logger.info("\n✅ Quality factor calculation complete!")


if __name__ == "__main__":
    main()
