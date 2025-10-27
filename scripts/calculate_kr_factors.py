#!/usr/bin/env python3
"""
Calculate Value Factors for Korean Stocks using pykrx data
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


def calculate_pe_factor(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate P/E factor scores"""
    valid_pe = df[(df['per'].notna()) & (df['per'] > 0) & (df['per'] < 100)].copy()
    
    if len(valid_pe) == 0:
        logger.warning("No valid P/E data")
        return pd.DataFrame()
    
    valid_pe['raw_score'] = -valid_pe['per']
    valid_pe['percentile'] = valid_pe['raw_score'].rank(pct=True) * 100
    
    mean = valid_pe['raw_score'].mean()
    std = valid_pe['raw_score'].std()
    valid_pe['z_score'] = (valid_pe['raw_score'] - mean) / std if std > 0 else 0
    valid_pe['factor_name'] = 'PE_Ratio'
    
    logger.info(f"✅ Calculated P/E factor for {len(valid_pe)} stocks")
    logger.info(f"   P/E range: {valid_pe['per'].min():.2f} - {valid_pe['per'].max():.2f}")
    
    return valid_pe[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'per']]


def calculate_pb_factor(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate P/B factor scores"""
    valid_pb = df[(df['pbr'].notna()) & (df['pbr'] > 0) & (df['pbr'] < 20)].copy()
    
    if len(valid_pb) == 0:
        logger.warning("No valid P/B data")
        return pd.DataFrame()
    
    valid_pb['raw_score'] = -valid_pb['pbr']
    valid_pb['percentile'] = valid_pb['raw_score'].rank(pct=True) * 100
    
    mean = valid_pb['raw_score'].mean()
    std = valid_pb['raw_score'].std()
    valid_pb['z_score'] = (valid_pb['raw_score'] - mean) / std if std > 0 else 0
    valid_pb['factor_name'] = 'PB_Ratio'
    
    logger.info(f"✅ Calculated P/B factor for {len(valid_pb)} stocks")
    logger.info(f"   P/B range: {valid_pb['pbr'].min():.2f} - {valid_pb['pbr'].max():.2f}")
    
    return valid_pb[['ticker', 'region', 'date', 'factor_name', 'z_score', 'percentile', 'pbr']]


def main():
    """Main execution"""
    logger.info("=== Korean Stock Factor Calculation (pykrx data) ===\n")
    
    db = PostgresDatabaseManager()
    
    logger.info("📊 Loading Korean stock fundamentals...")
    
    query = """
        WITH latest_data AS (
            SELECT 
                tf.ticker,
                tf.region,
                tf.date,
                tf.per,
                tf.pbr,
                t.name,
                ROW_NUMBER() OVER (PARTITION BY tf.ticker ORDER BY tf.date DESC) as rn
            FROM ticker_fundamentals tf
            JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
            WHERE tf.region = 'KR'
              AND tf.data_source = 'pykrx'
              AND tf.per IS NOT NULL
              AND tf.pbr IS NOT NULL
        )
        SELECT ticker, region, date, per, pbr, name
        FROM latest_data
        WHERE rn = 1
        ORDER BY ticker
    """
    
    fundamentals = db.execute_query(query)
    
    if not fundamentals:
        logger.error("❌ No fundamental data found!")
        sys.exit(1)
    
    df = pd.DataFrame(fundamentals)

    # Convert Decimal to float for pandas operations
    df['per'] = pd.to_numeric(df['per'], errors='coerce')
    df['pbr'] = pd.to_numeric(df['pbr'], errors='coerce')

    logger.info(f"✅ Loaded {len(df)} Korean stocks")

    logger.info("\n📈 Calculating value factors...")

    pe_scores = calculate_pe_factor(df)
    pb_scores = calculate_pb_factor(df)
    
    logger.info("\n🔀 Combining factors...")
    
    combined = pd.merge(
        pe_scores[['ticker', 'percentile', 'per']].rename(columns={'percentile': 'pe_percentile'}),
        pb_scores[['ticker', 'percentile', 'pbr']].rename(columns={'percentile': 'pb_percentile'}),
        on='ticker',
        how='inner'
    )
    
    combined['combined_score'] = (combined['pe_percentile'] + combined['pb_percentile']) / 2
    combined = combined.sort_values('combined_score', ascending=False)
    
    stock_names = df.set_index('ticker')['name'].to_dict()
    combined['name'] = combined['ticker'].map(stock_names)
    
    logger.info(f"✅ Combined scores for {len(combined)} stocks")
    
    logger.info("\n🏆 Top 20 Value Stocks...")
    logger.info("=" * 80)
    logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'P/E':<8}{'P/B':<8}{'Score':<8}")
    logger.info("=" * 80)
    
    for idx, (i, row) in enumerate(combined.head(20).iterrows(), 1):
        logger.info(
            f"{idx:<6}"
            f"{row['ticker']:<8}"
            f"{row['name'][:28]:<30}"
            f"{row['per']:<8.2f}"
            f"{row['pbr']:<8.2f}"
            f"{row['combined_score']:<8.1f}"
        )
    
    logger.info("\n💾 Saving to database...")
    
    records = []
    target_date = date.today()
    
    for _, row in pe_scores.iterrows():
        records.append((
            row['ticker'], row['region'], target_date, 'PE_Ratio',
            float(row['z_score']), float(row['percentile'])
        ))
    
    for _, row in pb_scores.iterrows():
        records.append((
            row['ticker'], row['region'], target_date, 'PB_Ratio',
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

            logger.info(f"✅ Saved {len(records)} factor scores")
        except Exception as e:
            logger.error(f"❌ Failed to save: {e}")
    
    logger.info("\n✅ Factor calculation complete!")


if __name__ == "__main__":
    main()
