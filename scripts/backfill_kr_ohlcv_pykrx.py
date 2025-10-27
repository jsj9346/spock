#!/usr/bin/env python3
"""
KR OHLCV Historical Data Backfill (pykrx)

Backfills historical OHLCV data for KR stocks using pykrx library.
Required for momentum factor calculation (12M_Momentum needs 252-day lookback).

Target Coverage: All KR stocks in database
Data Source: pykrx (KRX market data - official Korean exchange data)
Target Date Range: 2023-10-10 to 2024-10-09 (252 trading days for 12M momentum)

Usage:
    # Full backfill (252 days of historical data)
    python3 scripts/backfill_kr_ohlcv_pykrx.py --start 2023-10-10 --end 2024-10-09

    # Dry run (preview only)
    python3 scripts/backfill_kr_ohlcv_pykrx.py --dry-run --start 2023-10-10 --end 2024-10-09

    # With rate limiting (recommended for large backfills)
    python3 scripts/backfill_kr_ohlcv_pykrx.py --start 2023-10-10 --end 2024-10-09 --rate-limit 1.0

    # Limit tickers (for testing)
    python3 scripts/backfill_kr_ohlcv_pykrx.py --limit 10 --start 2024-01-01 --end 2024-10-09

Exit Codes:
    0: Success
    1: Critical error

Author: Spock Quant Platform - Week 4 OHLCV Backfill
Date: 2025-10-23
"""

import sys
import os
import argparse
import logging
import time
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# pykrx library
try:
    from pykrx import stock
except ImportError:
    print("❌ pykrx library not installed")
    print("Install with: pip3 install pykrx")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_backfill_kr_ohlcv_pykrx.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PyKRXOHLCVBackfiller:
    """pykrx OHLCV data backfill orchestrator"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False, rate_limit_delay: float = 1.0):
        """
        Initialize backfiller

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 1.0 = 1 req/sec)
        """
        self.db = db
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'total_days_collected': 0
        }

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def get_kr_tickers_for_backfill(self, limit: Optional[int] = None) -> List[str]:
        """
        Get list of KR tickers for backfill

        Args:
            limit: Maximum tickers to return (for testing)

        Returns:
            List of ticker codes
        """
        query = """
        SELECT DISTINCT ticker
        FROM tickers
        WHERE region = 'KR'
          AND asset_type = 'STOCK'
          AND is_active = TRUE
        ORDER BY ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)
        tickers = [row['ticker'] for row in results]

        logger.info(f"📊 Found {len(tickers)} KR stocks for backfill")
        return tickers

    def check_existing_data(self, ticker: str, start_date: date, end_date: date) -> Dict:
        """
        Check existing OHLCV data coverage for ticker

        Args:
            ticker: Stock ticker code
            start_date: Start date for backfill range
            end_date: End date for backfill range

        Returns:
            Dict with existing data stats
        """
        query = """
        SELECT
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(*) as existing_records
        FROM ohlcv_data
        WHERE ticker = %s
          AND region = 'KR'
          AND date BETWEEN %s AND %s
        """

        results = self.db.execute_query(query, (ticker, start_date, end_date))

        if results and results[0]['existing_records'] > 0:
            return {
                'has_data': True,
                'earliest': results[0]['earliest_date'],
                'latest': results[0]['latest_date'],
                'count': results[0]['existing_records']
            }
        else:
            return {
                'has_data': False,
                'count': 0
            }

    def fetch_ohlcv_from_pykrx(self, ticker: str, start_date: date, end_date: date) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from pykrx

        Args:
            ticker: Stock ticker code
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with OHLCV data or None if error
        """
        try:
            self._wait_for_rate_limit()
            self.stats['api_calls'] += 1

            # pykrx expects YYYYMMDD format
            from_date = start_date.strftime('%Y%m%d')
            to_date = end_date.strftime('%Y%m%d')

            # Fetch data
            df = stock.get_market_ohlcv_by_date(
                fromdate=from_date,
                todate=to_date,
                ticker=ticker,
                freq='d',  # Daily data
                adjusted=False  # Use unadjusted prices (we'll calculate adjusted separately)
            )

            if df is None or len(df) == 0:
                logger.warning(f"  {ticker}: No data returned from pykrx")
                return None

            # Rename columns to English
            df = df.rename(columns={
                '시가': 'open',
                '고가': 'high',
                '저가': 'low',
                '종가': 'close',
                '거래량': 'volume'
            })

            # Reset index to make 'date' a column
            df.reset_index(inplace=True)
            df.rename(columns={'날짜': 'date'}, inplace=True)

            # Ensure date is datetime
            df['date'] = pd.to_datetime(df['date'])

            return df

        except Exception as e:
            logger.error(f"  {ticker}: pykrx error - {str(e)}")
            return None

    def insert_ohlcv_data(self, ticker: str, df: pd.DataFrame) -> int:
        """
        Insert OHLCV data into database

        Args:
            ticker: Stock ticker code
            df: DataFrame with OHLCV data

        Returns:
            Number of records inserted
        """
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would insert {len(df)} records for {ticker}")
            return len(df)

        success_count = 0

        for _, row in df.iterrows():
            # Use upsert (INSERT ... ON CONFLICT UPDATE)
            query = """
            INSERT INTO ohlcv_data (
                ticker, region, date, timeframe,
                open, high, low, close, volume
            ) VALUES (
                %s, 'KR', %s, '1d',
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (ticker, region, date, timeframe)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
            """

            params = (
                ticker,
                row['date'].date(),
                float(row['open']) if pd.notna(row['open']) else None,
                float(row['high']) if pd.notna(row['high']) else None,
                float(row['low']) if pd.notna(row['low']) else None,
                float(row['close']) if pd.notna(row['close']) else None,
                int(row['volume']) if pd.notna(row['volume']) else None
            )

            try:
                # Use execute_update() to properly commit the transaction
                if self.db.execute_update(query, params):
                    success_count += 1
            except Exception as e:
                logger.error(f"  {ticker}: Insert error for {row['date'].date()} - {str(e)}")

        self.stats['records_inserted'] += success_count

        return success_count

    def backfill_ticker(self, ticker: str, start_date: date, end_date: date) -> bool:
        """
        Backfill OHLCV data for a single ticker

        Args:
            ticker: Stock ticker code
            start_date: Start date
            end_date: End date

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check existing data
            existing = self.check_existing_data(ticker, start_date, end_date)

            if existing['has_data']:
                logger.info(f"  {ticker}: Already has {existing['count']} records ({existing['earliest']} to {existing['latest']})")
                # Still fetch to fill any gaps

            # Fetch data from pykrx
            logger.info(f"  {ticker}: Fetching OHLCV data from pykrx...")
            df = self.fetch_ohlcv_from_pykrx(ticker, start_date, end_date)

            if df is None:
                self.stats['tickers_failed'] += 1
                return False

            logger.info(f"  {ticker}: Received {len(df)} days of data")

            # Insert/update data
            records_saved = self.insert_ohlcv_data(ticker, df)

            if records_saved > 0:
                logger.info(f"  ✅ {ticker}: Saved {records_saved} records")
                self.stats['tickers_success'] += 1
                self.stats['total_days_collected'] += len(df)
                return True
            else:
                logger.warning(f"  ⚠️  {ticker}: No records saved")
                self.stats['tickers_skipped'] += 1
                return False

        except Exception as e:
            logger.error(f"  ❌ {ticker}: Backfill error - {str(e)}")
            self.stats['tickers_failed'] += 1
            return False

    def run_backfill(self, start_date: date, end_date: date, limit: Optional[int] = None):
        """
        Run full backfill operation

        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
            limit: Maximum tickers to process (for testing)
        """
        logger.info("=" * 80)
        logger.info("KR OHLCV Historical Data Backfill (pykrx)")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Rate Limit: {self.rate_limit_delay}s delay per ticker")
        logger.info("")

        # Get tickers
        tickers = self.get_kr_tickers_for_backfill(limit=limit)
        total_tickers = len(tickers)

        if total_tickers == 0:
            logger.warning("No tickers found for backfill")
            return

        # Process each ticker
        start_time = time.time()

        for idx, ticker in enumerate(tickers, 1):
            logger.info(f"[{idx}/{total_tickers}] Processing {ticker}...")
            self.stats['tickers_processed'] += 1

            self.backfill_ticker(ticker, start_date, end_date)

            # Progress update every 50 tickers
            if idx % 50 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                remaining = (total_tickers - idx) * avg_time

                logger.info("")
                logger.info("=" * 80)
                logger.info(f"Progress: {idx}/{total_tickers} ({idx/total_tickers*100:.1f}%)")
                logger.info(f"Success: {self.stats['tickers_success']}, Failed: {self.stats['tickers_failed']}, Skipped: {self.stats['tickers_skipped']}")
                logger.info(f"Elapsed: {elapsed/60:.1f}min, Remaining: {remaining/60:.1f}min")
                logger.info("=" * 80)
                logger.info("")

        # Final summary
        total_time = time.time() - start_time

        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total Tickers: {total_tickers}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']} ({self.stats['tickers_success']/total_tickers*100:.1f}%)")
        logger.info(f"  ⚠️  Skipped: {self.stats['tickers_skipped']} ({self.stats['tickers_skipped']/total_tickers*100:.1f}%)")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']} ({self.stats['tickers_failed']/total_tickers*100:.1f}%)")
        logger.info(f"")
        logger.info(f"API Calls: {self.stats['api_calls']}")
        logger.info(f"Records Saved: {self.stats['records_inserted']:,}")
        logger.info(f"Total Days Collected: {self.stats['total_days_collected']:,}")
        logger.info(f"")
        logger.info(f"Total Time: {total_time/60:.1f} minutes")
        logger.info(f"Avg Time per Ticker: {total_time/total_tickers:.2f} seconds")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backfill KR OHLCV historical data using pykrx')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--limit', type=int, help='Limit number of tickers (for testing)')
    parser.add_argument('--rate-limit', type=float, default=1.0, help='Delay between API calls in seconds (default: 1.0)')

    args = parser.parse_args()

    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        logger.error(f"❌ Invalid date format: {e}")
        logger.error("Use YYYY-MM-DD format")
        return 1

    # Validate date range
    if start_date > end_date:
        logger.error("❌ Start date must be before end date")
        return 1

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize and run backfiller
    try:
        backfiller = PyKRXOHLCVBackfiller(
            db=db,
            dry_run=args.dry_run,
            rate_limit_delay=args.rate_limit
        )

        backfiller.run_backfill(
            start_date=start_date,
            end_date=end_date,
            limit=args.limit
        )

        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Backfill interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
