#!/usr/bin/env python3
"""
Phase 1.5 - Day 2: pykrx Fundamental Data Backfill for KR Market

Backfills ticker_fundamentals table with valuation ratios from pykrx library.
Extracts: PER, PBR, EPS, DIV (dividend yield), DPS, BPS

Target Coverage: 100% of KR market (141 active stocks)
Data Source: pykrx (KRX market data)

Usage:
    # Full backfill (historical data)
    python3 scripts/backfill_fundamentals_pykrx.py --start 2020-01-01 --end 2025-10-21

    # Dry run (preview only)
    python3 scripts/backfill_fundamentals_pykrx.py --dry-run --start 2025-01-01

    # Incremental update (only missing data)
    python3 scripts/backfill_fundamentals_pykrx.py --incremental

    # Limit processing (for testing)
    python3 scripts/backfill_fundamentals_pykrx.py --limit 10 --start 2025-01-01

    # Rate limiting
    python3 scripts/backfill_fundamentals_pykrx.py --rate-limit 0.5 --start 2020-01-01

Author: Quant Investment Platform - Phase 1.5
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
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals_pykrx.log"
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


class PyKRXFundamentalBackfiller:
    """pykrx fundamental data backfill orchestrator"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False, rate_limit_delay: float = 0.5):
        """
        Initialize backfiller

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 0.5 = 2 req/sec)
        """
        self.db = db
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0

        # Statistics
        self.stats = {
            'dates_processed': 0,
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'records_updated': 0
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

    def get_date_range_for_backfill(self, start_date: date, end_date: date, incremental: bool = False) -> List[date]:
        """
        Generate list of dates for backfill

        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
            incremental: If True, only get dates with missing data

        Returns:
            List of dates to backfill
        """
        if incremental:
            # Get dates that don't have pykrx data yet
            query = """
            SELECT DISTINCT date
            FROM generate_series(%s::date, %s::date, '1 day'::interval) AS date
            WHERE date NOT IN (
                SELECT DISTINCT date
                FROM ticker_fundamentals
                WHERE data_source = 'pykrx'
                  AND region = 'KR'
            )
            AND EXTRACT(DOW FROM date) NOT IN (0, 6)  -- Exclude weekends
            ORDER BY date
            """
            results = self.db.execute_query(query, (start_date, end_date))
            dates = [row['date'] for row in results]
        else:
            # Generate all business days (Monday-Friday)
            dates = []
            current = start_date
            while current <= end_date:
                # Skip weekends (5=Saturday, 6=Sunday in weekday())
                if current.weekday() < 5:
                    dates.append(current)
                current += timedelta(days=1)

        logger.info(f"📅 Found {len(dates)} dates for backfill")
        return dates

    def fetch_pykrx_fundamental_data(self, target_date: date, market: str = "ALL") -> Optional[pd.DataFrame]:
        """
        Fetch fundamental data from pykrx for a specific date

        Args:
            target_date: Date to fetch data for
            market: Market type (KOSPI, KOSDAQ, or ALL)

        Returns:
            DataFrame with columns: ticker (index), BPS, PER, PBR, EPS, DIV, DPS
            None if fetch fails
        """
        try:
            self._wait_for_rate_limit()
            self.stats['api_calls'] += 1

            date_str = target_date.strftime('%Y%m%d')

            # Fetch fundamental data from pykrx
            df = stock.get_market_fundamental(date_str, market=market)

            if df is None or df.empty:
                logger.debug(f"⚠️ [{date_str}] No fundamental data available")
                return None

            # Rename index to ticker for consistency
            df.index.name = 'ticker'
            df = df.reset_index()

            logger.debug(f"✅ [{date_str}] Fetched {len(df)} tickers from pykrx")
            return df

        except Exception as e:
            logger.error(f"❌ [{target_date}] pykrx fetch failed: {e}")
            return None

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Convert value to Decimal safely"""
        if value is None or pd.isna(value):
            return None
        try:
            return Decimal(str(float(value)))
        except (ValueError, TypeError, InvalidOperation):
            return None

    def insert_or_update_fundamental_data(self, ticker: str, target_date: date, data: Dict) -> bool:
        """
        Insert or update fundamental data in database

        Args:
            ticker: Stock ticker
            target_date: Date of the data
            data: Dictionary with fundamental metrics

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] Would insert/update {ticker} for {target_date}")
            logger.debug(f"  → PER: {data.get('per')}, PBR: {data.get('pbr')}, EPS: {data.get('eps')}")
            return True

        try:
            # UPSERT query - map pykrx data to actual schema columns
            # Note: Schema has per, pbr, dividend_yield, dividend_per_share
            # pykrx provides: PER, PBR, EPS, DIV (dividend yield), BPS, DPS
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                per, pbr, dividend_yield, dividend_per_share,
                data_source, created_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                dividend_yield = EXCLUDED.dividend_yield,
                dividend_per_share = EXCLUDED.dividend_per_share,
                data_source = EXCLUDED.data_source
            """

            # Convert data dict to tuple in correct order (9 params for 10 columns, NOW() handles created_at)
            params = (
                ticker,                           # 1. ticker
                'KR',                             # 2. region
                target_date,                      # 3. date
                'DAILY',                          # 4. period_type
                data.get('per'),                 # 5. per
                data.get('pbr'),                 # 6. pbr
                data.get('dividend_yield'),      # 7. dividend_yield
                data.get('dividend_per_share'),  # 8. dividend_per_share
                'pykrx'                          # 9. data_source
            )

            self.db.execute_update(query, params)

            # Determine if insert or update
            if self.db.cursor.rowcount > 0:
                if 'INSERT' in self.db.cursor.statusmessage:
                    self.stats['records_inserted'] += 1
                else:
                    self.stats['records_updated'] += 1
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ [{ticker}] Database insert/update failed: {e}")
            logger.error(f"   Query has {query.count('%s')} placeholders")
            logger.error(f"   Params has {len(params)} values: {params}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False

    def check_duplicate_exists(self, ticker: str, target_date: date) -> bool:
        """
        Check if fundamental data already exists for ticker+date

        Args:
            ticker: Stock ticker (KR format)
            target_date: Date to check

        Returns:
            True if data exists, False otherwise
        """
        try:
            query = """
            SELECT COUNT(*) as count
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = 'KR'
              AND date = %s
              AND data_source = 'pykrx'
            """
            result = self.db.execute_query(query, (ticker, target_date))

            if result and result[0]['count'] > 0:
                logger.debug(f"🔄 [KR:{ticker}] Duplicate found for {target_date}, will update")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ [KR:{ticker}] Duplicate check failed: {e}")
            return False

    def process_date(self, target_date: date, tickers: List[str]) -> int:
        """
        Process fundamental data for a specific date

        Args:
            target_date: Date to process
            tickers: List of tickers to process

        Returns:
            Number of successful insertions
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing date: {target_date}")
        logger.info(f"{'='*60}")

        # Fetch data for all tickers on this date
        df = self.fetch_pykrx_fundamental_data(target_date, market="ALL")

        if df is None or df.empty:
            logger.warning(f"⚠️ [{target_date}] No data available")
            return 0

        success_count = 0

        # Filter to only our target tickers
        df_filtered = df[df['ticker'].isin(tickers)]

        logger.info(f"📊 Processing {len(df_filtered)} tickers with data on {target_date}")

        for _, row in df_filtered.iterrows():
            ticker = row['ticker']
            self.stats['tickers_processed'] += 1

            # Check for duplicates (will still update if exists via UPSERT)
            if self.check_duplicate_exists(ticker, target_date):
                logger.debug(f"🔄 [KR:{ticker}] Data exists for {target_date}, will update with latest")

            # Prepare data dictionary - map pykrx columns to schema
            # pykrx: PER, PBR, EPS, DIV (dividend yield %), BPS, DPS (dividend per share)
            # schema: per, pbr, dividend_yield, dividend_per_share
            data = {
                'per': self._safe_decimal(row.get('PER')),
                'pbr': self._safe_decimal(row.get('PBR')),
                'dividend_yield': self._safe_decimal(row.get('DIV')),  # DIV = dividend yield %
                'dividend_per_share': self._safe_decimal(row.get('DPS'))  # DPS = dividend per share
            }

            # Insert/update database
            if self.insert_or_update_fundamental_data(ticker, target_date, data):
                self.stats['tickers_success'] += 1
                success_count += 1
            else:
                self.stats['tickers_failed'] += 1

        logger.info(f"✅ [{target_date}] Processed {success_count}/{len(df_filtered)} tickers successfully")
        return success_count

    def run_backfill(self, start_date: date, end_date: date, incremental: bool = False, limit: Optional[int] = None) -> Dict:
        """
        Run full backfill process

        Args:
            start_date: Start date for backfill
            end_date: End date for backfill
            incremental: If True, only fetch missing data
            limit: Maximum tickers to process (for testing)

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        logger.info("="*80)
        logger.info("PHASE 1.5 - DAY 2: PYKRX FUNDAMENTAL DATA BACKFILL")
        logger.info("="*80)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"Mode: {'INCREMENTAL' if incremental else 'FULL BACKFILL'}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Rate Limit: {self.rate_limit_delay} sec/request")
        if limit:
            logger.info(f"Limit: {limit} tickers")
        logger.info("="*80)

        # Get tickers for backfill
        tickers = self.get_kr_tickers_for_backfill(limit=limit)

        if not tickers:
            logger.warning("⚠️ No tickers to process")
            return self.stats

        # Get dates for backfill
        dates = self.get_date_range_for_backfill(start_date, end_date, incremental=incremental)

        if not dates:
            logger.warning("⚠️ No dates to process")
            return self.stats

        logger.info(f"\n📊 Processing {len(dates)} dates × {len(tickers)} tickers...")
        logger.info(f"⏱️ Estimated time: ~{len(dates) * self.rate_limit_delay / 60:.1f} minutes\n")

        # Process each date
        for i, target_date in enumerate(dates, 1):
            self.stats['dates_processed'] += 1

            logger.info(f"\n[{i}/{len(dates)}] Processing {target_date}...")

            self.process_date(target_date, tickers)

            # Progress update every 10 dates
            if i % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(dates) - i) / rate if rate > 0 else 0
                logger.info(f"\n📊 Progress: {i}/{len(dates)} dates ({i/len(dates)*100:.1f}%)")
                logger.info(f"⏱️ Elapsed: {elapsed/60:.1f}min | Remaining: {remaining/60:.1f}min")
                logger.info(f"📈 Success Rate: {self.stats['tickers_success']}/{self.stats['tickers_processed']} ({self.stats['tickers_success']/self.stats['tickers_processed']*100:.1f}%)")

        # Final statistics
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETE")
        logger.info("="*80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration/60:.2f} minutes")
        logger.info(f"\nStatistics:")
        logger.info(f"  Dates Processed: {self.stats['dates_processed']}")
        logger.info(f"  Tickers Processed: {self.stats['tickers_processed']}")
        logger.info(f"  API Calls: {self.stats['api_calls']}")
        logger.info(f"  Success: {self.stats['tickers_success']}")
        logger.info(f"  Failed: {self.stats['tickers_failed']}")
        logger.info(f"  Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"  Records Updated: {self.stats['records_updated']}")
        logger.info(f"  Success Rate: {self.stats['tickers_success']/self.stats['tickers_processed']*100:.1f}%")

        if self.stats['tickers_success'] / self.stats['tickers_processed'] < 0.8:
            logger.warning("⚠️ Backfill completed with low success rate: {:.1f}%".format(
                self.stats['tickers_success']/self.stats['tickers_processed']*100
            ))
        else:
            logger.info("✅ Backfill completed successfully!")

        logger.info("="*80)

        return self.stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='pykrx Fundamental Data Backfill (Phase 1.5 - Day 2)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full backfill (5 years)
  python3 scripts/backfill_fundamentals_pykrx.py --start 2020-01-01 --end 2025-10-21

  # Incremental update (only missing dates)
  python3 scripts/backfill_fundamentals_pykrx.py --incremental --start 2020-01-01

  # Test with 10 tickers for recent month
  python3 scripts/backfill_fundamentals_pykrx.py --limit 10 --start 2025-09-01

  # Dry run
  python3 scripts/backfill_fundamentals_pykrx.py --dry-run --start 2025-01-01
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                        help='Preview operations without database writes')
    parser.add_argument('--incremental', action='store_true',
                        help='Only fetch missing data (last 90 days)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of tickers (for testing)')
    parser.add_argument('--rate-limit', type=float, default=0.5,
                        help='Delay between API calls in seconds (default: 0.5)')
    parser.add_argument('--start', type=str, required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None,
                        help='End date (YYYY-MM-DD, default: today)')

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date() if args.end else date.today()

    # Validate date range
    if start_date > end_date:
        logger.error("❌ Start date must be before end date")
        sys.exit(1)

    try:
        # Initialize database connection
        db = PostgresDatabaseManager()

        # Initialize backfiller
        backfiller = PyKRXFundamentalBackfiller(
            db=db,
            dry_run=args.dry_run,
            rate_limit_delay=args.rate_limit
        )

        # Run backfill
        stats = backfiller.run_backfill(
            start_date=start_date,
            end_date=end_date,
            incremental=args.incremental,
            limit=args.limit
        )

        # Exit with status code
        if stats['tickers_success'] / max(stats['tickers_processed'], 1) >= 0.8:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Backfill interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
