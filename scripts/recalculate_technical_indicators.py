#!/usr/bin/env python3
"""
recalculate_technical_indicators.py - Comprehensive Technical Indicator Recalculation

Purpose:
- Recalculate ALL 16 technical indicators for KR market tickers
- Fix MA120/MA200 NULL issues (currently 31.91% and 74.25%)
- Batch processing with vectorized calculations for optimal performance
- Transaction-based database updates for data integrity

Technical Indicators (16 total):
- Moving Averages (5): ma5, ma20, ma60, ma120, ma200
- Momentum (1): rsi_14
- MACD (3): macd, macd_signal, macd_hist
- Bollinger Bands (3): bb_upper, bb_middle, bb_lower
- Volatility (2): atr, atr_14
- Volume (2): volume_ma20, volume_ratio

Design Reference: docs/TECHNICAL_INDICATOR_RECALCULATION_DESIGN.md
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for pandas_ta availability
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
    logger.info("✅ pandas_ta available - using optimized calculations")
except ImportError:
    HAS_PANDAS_TA = False
    logger.warning("⚠️  pandas_ta not available - using manual calculations")

# Configuration
DB_PATH = 'data/spock_local.db'
BATCH_SIZE = 500  # Process 500 tickers per batch
REGION = 'KR'
MIN_REQUIRED_DAYS = 200  # Minimum data required for MA200

# Technical Indicator Columns
INDICATOR_COLUMNS = [
    'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
    'rsi_14',
    'macd', 'macd_signal', 'macd_hist',
    'bb_upper', 'bb_middle', 'bb_lower',
    'atr', 'atr_14',
    'volume_ma20', 'volume_ratio'
]


def get_database_statistics(conn: sqlite3.Connection) -> Dict:
    """Get current database statistics"""
    cursor = conn.cursor()

    # Total rows
    cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region = ?', (REGION,))
    total_rows = cursor.fetchone()[0]

    # Unique tickers
    cursor.execute('SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE region = ?', (REGION,))
    total_tickers = cursor.fetchone()[0]

    # NULL rates for each indicator
    null_rates = {}
    for col in INDICATOR_COLUMNS:
        cursor.execute(f'SELECT COUNT(*) FROM ohlcv_data WHERE region = ? AND {col} IS NULL', (REGION,))
        null_count = cursor.fetchone()[0]
        null_rates[col] = (null_count / total_rows * 100) if total_rows > 0 else 0

    # Average data coverage per ticker
    cursor.execute('''
        SELECT AVG(day_count) as avg_days, MIN(day_count) as min_days, MAX(day_count) as max_days
        FROM (
            SELECT COUNT(*) as day_count
            FROM ohlcv_data
            WHERE region = ?
            GROUP BY ticker
        )
    ''', (REGION,))
    avg_days, min_days, max_days = cursor.fetchone()

    return {
        'total_rows': total_rows,
        'total_tickers': total_tickers,
        'null_rates': null_rates,
        'avg_days': avg_days,
        'min_days': min_days,
        'max_days': max_days
    }


def print_statistics_report(stats: Dict, title: str):
    """Print formatted statistics report"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    print(f"Total OHLCV rows: {stats['total_rows']:,}")
    print(f"Unique tickers: {stats['total_tickers']:,}")
    print(f"Data coverage: {stats['avg_days']:.1f} days (avg), {stats['min_days']} - {stats['max_days']} days (range)")

    print(f"\n📊 Indicator NULL Rates:")
    print(f"  Moving Averages:")
    print(f"    MA5:   {stats['null_rates']['ma5']:.2f}%")
    print(f"    MA20:  {stats['null_rates']['ma20']:.2f}%")
    print(f"    MA60:  {stats['null_rates']['ma60']:.2f}%")
    print(f"    MA120: {stats['null_rates']['ma120']:.2f}%")
    print(f"    MA200: {stats['null_rates']['ma200']:.2f}%")

    print(f"  Momentum & Trend:")
    print(f"    RSI-14: {stats['null_rates']['rsi_14']:.2f}%")
    print(f"    MACD:   {stats['null_rates']['macd']:.2f}%")
    print(f"    MACD Signal: {stats['null_rates']['macd_signal']:.2f}%")
    print(f"    MACD Hist:   {stats['null_rates']['macd_hist']:.2f}%")

    print(f"  Bollinger Bands:")
    print(f"    BB Upper:  {stats['null_rates']['bb_upper']:.2f}%")
    print(f"    BB Middle: {stats['null_rates']['bb_middle']:.2f}%")
    print(f"    BB Lower:  {stats['null_rates']['bb_lower']:.2f}%")

    print(f"  Volatility:")
    print(f"    ATR:    {stats['null_rates']['atr']:.2f}%")
    print(f"    ATR-14: {stats['null_rates']['atr_14']:.2f}%")

    print(f"  Volume:")
    print(f"    Volume MA20:   {stats['null_rates']['volume_ma20']:.2f}%")
    print(f"    Volume Ratio:  {stats['null_rates']['volume_ratio']:.2f}%")


def calculate_indicators_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all technical indicators using vectorized operations

    Args:
        df: DataFrame with OHLCV data (date, open, high, low, close, volume)

    Returns:
        DataFrame with all 16 technical indicators
    """
    df_indicators = df.copy()

    # 1. Moving Averages (5)
    df_indicators['ma5'] = df['close'].rolling(window=5, min_periods=5).mean()
    df_indicators['ma20'] = df['close'].rolling(window=20, min_periods=20).mean()
    df_indicators['ma60'] = df['close'].rolling(window=60, min_periods=60).mean()
    df_indicators['ma120'] = df['close'].rolling(window=120, min_periods=120).mean()
    df_indicators['ma200'] = df['close'].rolling(window=200, min_periods=200).mean()

    # 2. Volume Indicators (2)
    df_indicators['volume_ma20'] = df['volume'].rolling(window=20, min_periods=20).mean()
    df_indicators['volume_ratio'] = (df['volume'] / df_indicators['volume_ma20']).fillna(1.0)

    # 3. RSI-14 (1)
    if HAS_PANDAS_TA:
        df_indicators['rsi_14'] = ta.rsi(df['close'], length=14)
    else:
        # Manual RSI calculation
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df_indicators['rsi_14'] = 100 - (100 / (1 + rs))

    # 4. MACD (3)
    if HAS_PANDAS_TA:
        macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df_indicators['macd'] = macd_result['MACD_12_26_9']
        df_indicators['macd_signal'] = macd_result['MACDs_12_26_9']
        df_indicators['macd_hist'] = macd_result['MACDh_12_26_9']
    else:
        # Manual MACD calculation
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        df_indicators['macd'] = macd
        df_indicators['macd_signal'] = signal
        df_indicators['macd_hist'] = macd - signal

    # 5. Bollinger Bands (3)
    if HAS_PANDAS_TA:
        bb = ta.bbands(df['close'], length=20, std=2)
        bb_cols = list(bb.columns)
        bb_upper_col = [c for c in bb_cols if c.startswith('BBU')][0]
        bb_middle_col = [c for c in bb_cols if c.startswith('BBM')][0]
        bb_lower_col = [c for c in bb_cols if c.startswith('BBL')][0]
        df_indicators['bb_upper'] = bb[bb_upper_col]
        df_indicators['bb_middle'] = bb[bb_middle_col]
        df_indicators['bb_lower'] = bb[bb_lower_col]
    else:
        # Manual Bollinger Bands calculation
        bb_middle = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df_indicators['bb_upper'] = bb_middle + (bb_std * 2)
        df_indicators['bb_middle'] = bb_middle
        df_indicators['bb_lower'] = bb_middle - (bb_std * 2)

    # 6. ATR (2 - both atr and atr_14 for backward compatibility)
    if HAS_PANDAS_TA:
        atr_value = ta.atr(df['high'], df['low'], df['close'], length=14)
        df_indicators['atr'] = atr_value
        df_indicators['atr_14'] = atr_value  # Both columns for compatibility
    else:
        # Manual ATR calculation
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr_value = tr.rolling(window=14).mean()
        df_indicators['atr'] = atr_value
        df_indicators['atr_14'] = atr_value  # Both columns for compatibility

    return df_indicators


def update_ticker_indicators_batch(conn: sqlite3.Connection, ticker: str, df_indicators: pd.DataFrame) -> int:
    """
    Update technical indicators for a single ticker using batch UPDATE

    Args:
        conn: Database connection
        ticker: Stock ticker code
        df_indicators: DataFrame with calculated indicators

    Returns:
        Number of rows updated
    """
    cursor = conn.cursor()

    # Build UPDATE query with all indicators
    update_sql = f'''
        UPDATE ohlcv_data
        SET ma5 = ?, ma20 = ?, ma60 = ?, ma120 = ?, ma200 = ?,
            rsi_14 = ?,
            macd = ?, macd_signal = ?, macd_hist = ?,
            bb_upper = ?, bb_middle = ?, bb_lower = ?,
            atr = ?, atr_14 = ?,
            volume_ma20 = ?, volume_ratio = ?
        WHERE ticker = ? AND region = ? AND date = ?
    '''

    # Prepare batch data
    batch_data = []
    for idx, row in df_indicators.iterrows():
        # Convert date to string format for SQLite
        date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])

        batch_data.append((
            float(row['ma5']) if pd.notna(row['ma5']) else None,
            float(row['ma20']) if pd.notna(row['ma20']) else None,
            float(row['ma60']) if pd.notna(row['ma60']) else None,
            float(row['ma120']) if pd.notna(row['ma120']) else None,
            float(row['ma200']) if pd.notna(row['ma200']) else None,
            float(row['rsi_14']) if pd.notna(row['rsi_14']) else None,
            float(row['macd']) if pd.notna(row['macd']) else None,
            float(row['macd_signal']) if pd.notna(row['macd_signal']) else None,
            float(row['macd_hist']) if pd.notna(row['macd_hist']) else None,
            float(row['bb_upper']) if pd.notna(row['bb_upper']) else None,
            float(row['bb_middle']) if pd.notna(row['bb_middle']) else None,
            float(row['bb_lower']) if pd.notna(row['bb_lower']) else None,
            float(row['atr']) if pd.notna(row['atr']) else None,
            float(row['atr_14']) if pd.notna(row['atr_14']) else None,
            float(row['volume_ma20']) if pd.notna(row['volume_ma20']) else None,
            float(row['volume_ratio']) if pd.notna(row['volume_ratio']) else None,
            ticker, REGION, date_str
        ))

    # Execute batch update
    cursor.executemany(update_sql, batch_data)
    return cursor.rowcount


def process_batch(conn: sqlite3.Connection, ticker_batch: List[str], batch_num: int, total_batches: int) -> Tuple[int, int, int]:
    """
    Process a batch of tickers

    Args:
        conn: Database connection
        ticker_batch: List of tickers to process
        batch_num: Current batch number
        total_batches: Total number of batches

    Returns:
        Tuple of (success_count, skip_count, error_count)
    """
    success_count = 0
    skip_count = 0
    error_count = 0

    batch_start_time = time.time()

    for ticker in ticker_batch:
        try:
            # Load OHLCV data for ticker
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = ? AND region = ?
                ORDER BY date ASC
            ''', (ticker, REGION))

            rows = cursor.fetchall()

            if len(rows) < MIN_REQUIRED_DAYS:
                skip_count += 1
                logger.debug(f"⏭️  [{batch_num}/{total_batches}] {ticker}: Skipped (insufficient data: {len(rows)} days)")
                continue

            # Create DataFrame
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Calculate indicators (vectorized)
            df_indicators = calculate_indicators_vectorized(df)
            df_indicators = df_indicators.reset_index()  # Reset index to get 'date' as column

            # Update database (batch UPDATE)
            rows_updated = update_ticker_indicators_batch(conn, ticker, df_indicators)

            success_count += 1
            logger.debug(f"✅ [{batch_num}/{total_batches}] {ticker}: {rows_updated} rows updated")

        except Exception as e:
            error_count += 1
            logger.error(f"❌ [{batch_num}/{total_batches}] {ticker}: Error - {e}")

    batch_time = time.time() - batch_start_time
    logger.info(f"✅ Batch {batch_num}/{total_batches} completed: {success_count} success, {skip_count} skipped, {error_count} errors ({batch_time:.1f}s)")

    return success_count, skip_count, error_count


def main():
    print("="*80)
    print("KR Market Technical Indicator Recalculation")
    print("="*80)

    start_time = time.time()

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Pre-validation: Current statistics
    print("\n📊 Pre-Validation: Current Database Statistics")
    pre_stats = get_database_statistics(conn)
    print_statistics_report(pre_stats, "BEFORE Recalculation")

    # Quality check
    if pre_stats['avg_days'] < MIN_REQUIRED_DAYS:
        print(f"\n⚠️  WARNING: Average data coverage ({pre_stats['avg_days']:.1f} days) < minimum required ({MIN_REQUIRED_DAYS} days)")
        print(f"   Consider running full historical data collection first.")
        response = input("   Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("❌ Recalculation aborted.")
            conn.close()
            return

    # Get all tickers
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT ticker FROM ohlcv_data WHERE region = ? ORDER BY ticker', (REGION,))
    all_tickers = [row[0] for row in cursor.fetchall()]

    total_tickers = len(all_tickers)
    total_batches = (total_tickers + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n🎯 Processing Configuration:")
    print(f"   Total tickers: {total_tickers:,}")
    print(f"   Batch size: {BATCH_SIZE}")
    print(f"   Total batches: {total_batches}")
    print(f"   Minimum required days: {MIN_REQUIRED_DAYS}")

    # Statistics
    total_success = 0
    total_skip = 0
    total_error = 0

    # Process batches
    print(f"\n🔄 Starting batch processing...\n")

    for i in range(total_batches):
        batch_start_idx = i * BATCH_SIZE
        batch_end_idx = min((i + 1) * BATCH_SIZE, total_tickers)
        ticker_batch = all_tickers[batch_start_idx:batch_end_idx]

        # Start transaction for batch
        conn.execute('BEGIN')

        try:
            success, skip, error = process_batch(conn, ticker_batch, i + 1, total_batches)

            # Commit transaction
            conn.commit()

            total_success += success
            total_skip += skip
            total_error += error

        except Exception as e:
            # Rollback on batch failure
            conn.rollback()
            logger.error(f"❌ Batch {i+1}/{total_batches} failed: {e}")
            total_error += len(ticker_batch)

    # Post-validation: New statistics
    print("\n📊 Post-Validation: Updated Database Statistics")
    post_stats = get_database_statistics(conn)
    print_statistics_report(post_stats, "AFTER Recalculation")

    # Final summary
    total_time = time.time() - start_time

    print(f"\n{'='*80}")
    print("Recalculation Complete!")
    print(f"{'='*80}")
    print(f"✅ Success: {total_success:,} tickers ({total_success/total_tickers*100:.1f}%)")
    print(f"⏭️  Skipped: {total_skip:,} tickers ({total_skip/total_tickers*100:.1f}%)")
    print(f"❌ Errors:  {total_error:,} tickers ({total_error/total_tickers*100:.1f}%)")
    print(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} minutes)")

    # Improvement metrics
    print(f"\n📈 Improvement Metrics:")
    for col in ['ma120', 'ma200', 'rsi_14', 'atr_14']:
        before = pre_stats['null_rates'][col]
        after = post_stats['null_rates'][col]
        improvement = before - after
        print(f"   {col.upper()}: {before:.2f}% → {after:.2f}% (improved by {improvement:.2f} percentage points)")

    # Quality assessment
    print(f"\n🎯 Quality Assessment:")
    ma200_null_rate = post_stats['null_rates']['ma200']
    ma120_null_rate = post_stats['null_rates']['ma120']

    if ma200_null_rate < 1.0 and ma120_null_rate < 1.0:
        print(f"   ✅ EXCELLENT - MA120/MA200 NULL rates < 1%")
        print(f"   ✅ LayeredScoringEngine ready for execution")
    elif ma200_null_rate < 5.0 and ma120_null_rate < 5.0:
        print(f"   ⚠️  GOOD - MA120/MA200 NULL rates < 5%")
        print(f"   ⚠️  Minor data gaps remaining, but usable")
    else:
        print(f"   ❌ INSUFFICIENT - MA120/MA200 NULL rates still high")
        print(f"   ❌ Additional data collection may be required")

    conn.close()


if __name__ == '__main__':
    main()
