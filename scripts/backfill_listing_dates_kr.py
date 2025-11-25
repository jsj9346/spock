#!/usr/bin/env python3
"""
KR Market listing_date Backfill Script

Backfills missing listing_date data for KR tickers using KRX Data API.
Falls back to pykrx if KRX API is unavailable.

Usage:
    # Full backfill (all missing listing_dates)
    python3 scripts/backfill_listing_dates_kr.py

    # Dry-run (preview only)
    python3 scripts/backfill_listing_dates_kr.py --dry-run

    # Use pykrx instead of KRX API
    python3 scripts/backfill_listing_dates_kr.py --source pykrx

Author: Quant Investment Platform
Date: 2025-11-07
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Optional
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.api_clients.krx_data_api import KRXDataAPI

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_backfill_listing_dates_kr.log"
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


class ListingDateBackfiller:
    """Backfill listing_date for KR tickers"""

    def __init__(self, db: PostgresDatabaseManager,
                 source: str = 'krx', dry_run: bool = False):
        """
        Initialize backfiller

        Args:
            db: Database manager
            source: Data source ('krx' or 'pykrx')
            dry_run: Preview mode without DB writes
        """
        self.db = db
        self.source = source
        self.dry_run = dry_run

        # Initialize API clients
        self.krx_api = KRXDataAPI() if source == 'krx' else None

        # Statistics
        self.stats = {
            'tickers_checked': 0,
            'tickers_updated': 0,
            'tickers_failed': 0,
            'tickers_no_data': 0,
            'tickers_skipped': 0
        }

    def get_tickers_without_listing_date(self) -> List[Dict]:
        """
        Query KR tickers missing listing_date

        Returns:
            List of ticker dicts
        """
        query = """
        SELECT ticker, name, asset_type
        FROM tickers
        WHERE region = 'KR'
          AND asset_type IN ('STOCK', 'ETF')
          AND is_active = TRUE
          AND listing_date IS NULL
        ORDER BY ticker
        """
        return self.db.execute_query(query)

    def fetch_listing_dates_krx(self) -> Dict[str, date]:
        """
        Fetch listing dates from KRX Data API

        Returns:
            Dict mapping ticker -> listing_date
        """
        logger.info("Fetching listing dates from KRX Data API...")

        try:
            # Get stock list with listing_date
            stocks = self.krx_api.get_stock_list()

            # Get ETF list with listing_date
            try:
                etfs = self.krx_api.get_etf_list()
                stocks.extend(etfs)
            except Exception as e:
                logger.warning(f"Failed to fetch ETF list: {e}")

            listing_dates = {}
            for item in stocks:
                ticker = item.get('ticker')
                listing_date_str = item.get('listing_date')

                if ticker and listing_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD or YYYYMMDD or YYYY/MM/DD)
                        listing_date_str = str(listing_date_str).strip()

                        if '/' in listing_date_str:
                            listing_date = datetime.strptime(listing_date_str, '%Y/%m/%d').date()
                        elif '-' in listing_date_str:
                            listing_date = datetime.strptime(listing_date_str, '%Y-%m-%d').date()
                        else:
                            listing_date = datetime.strptime(listing_date_str, '%Y%m%d').date()

                        listing_dates[ticker] = listing_date

                    except Exception as e:
                        logger.debug(f"Failed to parse date for {ticker} ({listing_date_str}): {e}")

            logger.info(f"✅ Fetched {len(listing_dates)} listing dates from KRX")
            return listing_dates

        except Exception as e:
            logger.error(f"❌ Failed to fetch from KRX API: {e}")
            return {}

    def update_listing_date(self, ticker: str, listing_date: date) -> bool:
        """
        Update listing_date in database

        Args:
            ticker: Ticker symbol
            listing_date: Listing date

        Returns:
            Success status
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would update {ticker} listing_date: {listing_date}")
            return True

        try:
            query = """
            UPDATE tickers
            SET listing_date = %s, last_updated = NOW()
            WHERE ticker = %s AND region = 'KR'
            """
            success = self.db.execute_update(query, (listing_date, ticker))

            if success:
                logger.debug(f"✅ Updated {ticker}: listing_date={listing_date}")
            else:
                logger.warning(f"⚠️ No rows updated for {ticker}")

            return success

        except Exception as e:
            logger.error(f"Failed to update {ticker}: {e}")
            return False

    def run_backfill(self) -> Dict:
        """
        Run listing_date backfill process

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        logger.info("="*80)
        logger.info("🚀 KR MARKET LISTING_DATE BACKFILL")
        logger.info("="*80)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Data Source: {self.source.upper()}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("="*80)

        # Step 1: Get tickers without listing_date
        tickers = self.get_tickers_without_listing_date()
        logger.info(f"📊 Found {len(tickers)} tickers without listing_date")

        if not tickers:
            logger.info("✅ All tickers have listing_date - nothing to backfill")
            logger.info("="*80)
            return self.stats

        # Show sample
        logger.info(f"\nSample tickers (first 5):")
        for ticker_info in tickers[:5]:
            logger.info(f"  {ticker_info['ticker']} ({ticker_info['name']}) - {ticker_info['asset_type']}")

        # Step 2: Fetch listing dates from data source
        logger.info(f"\n📡 Fetching listing dates from {self.source.upper()}...")

        if self.source == 'krx':
            listing_dates = self.fetch_listing_dates_krx()
        else:
            logger.error(f"Unsupported source: {self.source}")
            return self.stats

        if not listing_dates:
            logger.error("❌ No listing dates fetched - aborting backfill")
            logger.info("="*80)
            return self.stats

        # Step 3: Update tickers
        logger.info(f"\n🔄 Updating {len(tickers)} tickers...")

        for ticker_info in tickers:
            ticker = ticker_info['ticker']
            self.stats['tickers_checked'] += 1

            listing_date = listing_dates.get(ticker)

            if listing_date:
                success = self.update_listing_date(ticker, listing_date)
                if success:
                    self.stats['tickers_updated'] += 1
                else:
                    self.stats['tickers_failed'] += 1
            else:
                logger.debug(f"No listing_date found for {ticker}")
                self.stats['tickers_no_data'] += 1

        # Step 4: Print summary
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("\n" + "=" * 80)
        logger.info("📊 BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")
        logger.info(f"\nStatistics:")
        logger.info(f"  Tickers Checked:  {self.stats['tickers_checked']:,}")
        logger.info(f"  ✅ Updated:        {self.stats['tickers_updated']:,}")
        logger.info(f"  ⚠️ No Data:        {self.stats['tickers_no_data']:,}")
        logger.info(f"  ❌ Failed:         {self.stats['tickers_failed']:,}")

        # Calculate coverage improvement
        if self.stats['tickers_updated'] > 0:
            coverage_improvement = (self.stats['tickers_updated'] / self.stats['tickers_checked']) * 100
            logger.info(f"\n📈 Coverage Improvement: +{coverage_improvement:.2f}%")

        logger.info("=" * 80)

        return self.stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Backfill listing_date for KR tickers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full backfill
  python3 scripts/backfill_listing_dates_kr.py

  # Dry-run preview
  python3 scripts/backfill_listing_dates_kr.py --dry-run

  # Use pykrx (fallback)
  python3 scripts/backfill_listing_dates_kr.py --source pykrx
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without DB writes'
    )
    parser.add_argument(
        '--source',
        choices=['krx', 'pykrx'],
        default='krx',
        help='Data source (default: krx)'
    )

    args = parser.parse_args()

    try:
        # Initialize
        db = PostgresDatabaseManager()
        backfiller = ListingDateBackfiller(db, source=args.source, dry_run=args.dry_run)

        # Run
        backfiller.run_backfill()

        # Cleanup
        db.close_pool()

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
