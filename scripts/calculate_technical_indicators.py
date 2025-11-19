#!/usr/bin/env python3
"""
Technical Indicators Calculation Script for HK Market
Calculates MA, RSI, MACD for all tickers in ohlcv_data table

Usage:
    python3 scripts/calculate_technical_indicators.py --region HK --batch-size 50
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Optional
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/technical_indicators_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TechnicalIndicatorCalculator:
    """Calculate and store technical indicators in database"""

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager

    def calculate_ma(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """Calculate Moving Averages"""
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period, min_periods=period).mean()
        return df

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate RSI (Relative Strength Index)"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        df['rsi_14'] = rsi
        return df

    def calculate_macd(self, df: pd.DataFrame,
                      fast_period: int = 12,
                      slow_period: int = 26,
                      signal_period: int = 9) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        # Calculate EMAs
        ema_fast = df['close'].ewm(span=fast_period, adjust=False, min_periods=fast_period).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False, min_periods=slow_period).mean()

        # MACD line
        macd = ema_fast - ema_slow

        # Signal line
        signal = macd.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()

        # Histogram
        hist = macd - signal

        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist

        return df

    def calculate_indicators_for_ticker(self, ticker: str, region: str) -> bool:
        """Calculate all technical indicators for a single ticker"""
        try:
            # Fetch OHLCV data sorted by date
            query = """
                SELECT ticker, region, date, timeframe, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s AND timeframe = '1d'
                ORDER BY date ASC
            """

            # Convert List[Dict] to DataFrame
            result = self.db.execute_query(query, (ticker, region))
            df = pd.DataFrame(result)

            if df.empty or len(df) < 200:  # Need at least 200 days for MA200
                logger.warning(f"⚠️  {ticker}: Insufficient data ({len(df)} records). Skipping.")
                return False

            # Calculate indicators
            df = self.calculate_ma(df, periods=[5, 20, 50, 60, 120, 200])
            df = self.calculate_rsi(df, period=14)
            df = self.calculate_macd(df)

            # Prepare update data (only records with calculated values)
            update_records = []
            for _, row in df.iterrows():
                # Only update if we have at least MA5 (shortest indicator)
                if pd.notna(row.get('ma5')):
                    update_records.append({
                        'ticker': row['ticker'],
                        'region': row['region'],
                        'date': row['date'],
                        'timeframe': row['timeframe'],
                        'ma5': row.get('ma5'),
                        'ma20': row.get('ma20'),
                        'ma50': row.get('ma50'),
                        'ma60': row.get('ma60'),
                        'ma120': row.get('ma120'),
                        'ma200': row.get('ma200'),
                        'rsi_14': row.get('rsi_14'),
                        'macd': row.get('macd'),
                        'macd_signal': row.get('macd_signal'),
                        'macd_hist': row.get('macd_hist')
                    })

            if not update_records:
                logger.warning(f"⚠️  {ticker}: No valid indicators calculated")
                return False

            # Batch update database
            update_query = """
                UPDATE ohlcv_data
                SET ma5 = %(ma5)s,
                    ma20 = %(ma20)s,
                    ma50 = %(ma50)s,
                    ma60 = %(ma60)s,
                    ma120 = %(ma120)s,
                    ma200 = %(ma200)s,
                    rsi_14 = %(rsi_14)s,
                    macd = %(macd)s,
                    macd_signal = %(macd_signal)s,
                    macd_hist = %(macd_hist)s
                WHERE ticker = %(ticker)s
                  AND region = %(region)s
                  AND date = %(date)s
                  AND timeframe = %(timeframe)s
            """

            # Batch update using loop (execute_batch_update not available)
            for record in update_records:
                self.db.execute_update(update_query, record)

            logger.info(f"✅ {ticker}: {len(update_records)} records updated with technical indicators")
            return True

        except Exception as e:
            logger.error(f"❌ {ticker}: Error calculating indicators - {str(e)}")
            return False

    def calculate_all_tickers(self, region: str, batch_size: int = 50, incremental: bool = True) -> dict:
        """Calculate indicators for all tickers in a region

        Args:
            region: Market region (KR, HK, US, JP, CN, VN)
            batch_size: Progress report interval (default: 50)
            incremental: If True, only calculate missing indicators (ma5 IS NULL);
                        If False, recalculate all records (default: True)
        """
        mode = "incremental" if incremental else "full recalculation"
        logger.info(f"🚀 Starting technical indicators calculation for region: {region} ({mode})")

        # Get list of tickers with OHLCV data
        if incremental:
            # Incremental mode: Only tickers where the LATEST date has missing indicators
            # This targets newly added OHLCV data that hasn't been calculated yet
            query = """
                WITH latest_dates AS (
                    SELECT ticker, MAX(date) as max_date
                    FROM ohlcv_data
                    WHERE region = %s AND timeframe = '1d'
                    GROUP BY ticker
                )
                SELECT DISTINCT o.ticker
                FROM ohlcv_data o
                INNER JOIN latest_dates ld ON o.ticker = ld.ticker AND o.date = ld.max_date
                WHERE o.region = %s AND o.timeframe = '1d'
                  AND o.ma5 IS NULL
                ORDER BY o.ticker
            """
        else:
            # Full recalculation mode: All tickers
            query = """
                SELECT DISTINCT ticker
                FROM ohlcv_data
                WHERE region = %s AND timeframe = '1d'
                ORDER BY ticker
            """

        # Extract ticker list from List[Dict] result
        if incremental:
            # Incremental query needs region parameter twice
            result = self.db.execute_query(query, (region, region))
        else:
            # Full query needs region parameter once
            result = self.db.execute_query(query, (region,))
        tickers = [row['ticker'] for row in result]

        logger.info(f"📊 Found {len(tickers)} tickers to process")

        # Process in batches
        success_count = 0
        failed_count = 0
        start_time = datetime.now()

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] Processing {ticker}...")

            if self.calculate_indicators_for_ticker(ticker, region):
                success_count += 1
            else:
                failed_count += 1

            # Progress update every batch_size
            if i % batch_size == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed
                remaining = (len(tickers) - i) / rate if rate > 0 else 0
                logger.info(f"📈 Progress: {i}/{len(tickers)} ({i*100//len(tickers)}%) | "
                          f"Success: {success_count} | Failed: {failed_count} | "
                          f"ETA: {remaining/60:.1f} min")

        # Final summary
        duration = (datetime.now() - start_time).total_seconds()
        results = {
            'total_tickers': len(tickers),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': f"{success_count*100/len(tickers):.2f}%",
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            'rate_per_second': len(tickers) / duration if duration > 0 else 0
        }

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Technical Indicators Calculation Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Total Tickers: {results['total_tickers']}")
        logger.info(f"Success: {results['success_count']} ({results['success_rate']})")
        logger.info(f"Failed: {results['failed_count']}")
        logger.info(f"Duration: {results['duration_minutes']:.2f} minutes")
        logger.info(f"Rate: {results['rate_per_second']:.2f} tickers/sec")
        logger.info(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(description='Calculate technical indicators for OHLCV data')
    parser.add_argument('--region', type=str, default='HK', help='Market region (default: HK)')
    parser.add_argument('--batch-size', type=int, default=50, help='Progress report batch size (default: 50)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database updates)')
    parser.add_argument('--full-recalc', action='store_true', help='Full recalculation mode (recalculate all records)')

    args = parser.parse_args()

    # Determine incremental mode (opposite of full-recalc)
    incremental_mode = not args.full_recalc

    logger.info(f"🎯 Technical Indicators Calculator")
    logger.info(f"Region: {args.region}")
    logger.info(f"Batch Size: {args.batch_size}")
    logger.info(f"Mode: {'Incremental (ma5 IS NULL only)' if incremental_mode else 'Full Recalculation (ALL records)'}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("")

    # Initialize database
    db_manager = PostgresDatabaseManager()

    if args.dry_run:
        logger.info("⚠️  DRY RUN MODE - No database updates will be performed")
        return

    # Calculate indicators
    calculator = TechnicalIndicatorCalculator(db_manager)
    results = calculator.calculate_all_tickers(region=args.region, batch_size=args.batch_size, incremental=incremental_mode)

    # Close database connection pool
    try:
        db_manager.close_pool()
    except AttributeError:
        pass  # Connection pool closes automatically

    logger.info("🎉 Script completed successfully!")


if __name__ == "__main__":
    main()
