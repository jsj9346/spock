#!/usr/bin/env python3
"""
Overseas Markets listing_date Backfill Script

Backfills missing listing_date data for overseas tickers (US, HK, JP, CN, VN)
using yfinance historical data start dates.

Data Source: yfinance (max period historical data)
Method: First trading date from historical data = listing_date

Usage:
    # All overseas markets
    python3 scripts/backfill_listing_dates_overseas.py

    # Specific regions
    python3 scripts/backfill_listing_dates_overseas.py --regions US HK JP

    # Dry-run (preview only)
    python3 scripts/backfill_listing_dates_overseas.py --dry-run

    # With rate limiting (delay between API calls)
    python3 scripts/backfill_listing_dates_overseas.py --delay 0.5

Author: Quant Investment Platform
Date: 2025-11-07
"""

import sys
import os
import argparse
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_backfill_listing_dates_overseas.log"
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


# Ticker suffix mapping for yfinance
REGION_SUFFIX_MAP = {
    'US': '',           # No suffix for US
    'HK': '.HK',        # Hong Kong
    'JP': '.T',         # Tokyo Stock Exchange
    'CN': '.SS',        # Shanghai (or .SZ for Shenzhen)
    'VN': '.VN'         # Vietnam (limited support)
}


class OverseasListingDateBackfiller:
    """Backfill listing_date for overseas markets using yfinance"""

    def __init__(self, db: PostgresDatabaseManager,
                 regions: List[str] = None,
                 dry_run: bool = False,
                 delay: float = 0.2):
        """
        Initialize backfiller

        Args:
            db: Database manager
            regions: List of regions to backfill (default: all overseas)
            dry_run: Preview mode without DB writes
            delay: Delay between API calls in seconds (default: 0.2)
        """
        self.db = db
        self.regions = regions or ['US', 'HK', 'JP', 'CN', 'VN']
        self.dry_run = dry_run
        self.delay = delay

        # Statistics per region
        self.stats = {region: {
            'tickers_checked': 0,
            'tickers_updated': 0,
            'tickers_failed': 0,
            'tickers_no_data': 0
        } for region in self.regions}

    def get_tickers_without_listing_date(self, region: str) -> List[Dict]:
        """
        Query tickers missing listing_date for specific region

        Args:
            region: Region code (US, HK, JP, CN, VN)

        Returns:
            List of ticker dicts
        """
        query = """
        SELECT ticker, name, asset_type
        FROM tickers
        WHERE region = %s
          AND asset_type IN ('STOCK', 'ETF')
          AND is_active = TRUE
          AND listing_date IS NULL
        ORDER BY ticker
        """
        return self.db.execute_query(query, (region,))

    def normalize_hk_ticker(self, ticker: str) -> str:
        """
        Normalize HK ticker to 4-digit format required by yfinance

        Examples:
            '0001.HK' → '0001'
            '00001' → '0001'
            '0700' → '0700'
            '00700' → '0700'

        Args:
            ticker: Original ticker symbol

        Returns:
            Normalized 4-digit ticker (without suffix)
        """
        # Remove .HK suffix if present
        base_ticker = ticker.replace('.HK', '')

        # Remove leading zeros beyond 4 digits
        if base_ticker.isdigit() and len(base_ticker) > 4:
            base_ticker = base_ticker.lstrip('0').zfill(4)

        return base_ticker

    def normalize_cn_ticker(self, ticker: str) -> tuple:
        """
        Normalize CN ticker, return (base_ticker, existing_suffix)

        Examples:
            '688099.SS' → ('688099', '.SS')
            '000001.SZ' → ('000001', '.SZ')
            '600519' → ('600519', None)

        Args:
            ticker: Original ticker symbol

        Returns:
            Tuple of (base_ticker, existing_suffix or None)
        """
        if ticker.endswith('.SS'):
            return (ticker[:-3], '.SS')
        elif ticker.endswith('.SZ'):
            return (ticker[:-3], '.SZ')
        else:
            return (ticker, None)

    def fetch_listing_date_yfinance(self, ticker: str, region: str) -> Optional[date]:
        """
        Fetch listing date from yfinance historical data

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            Listing date or None
        """
        try:
            import yfinance as yf

            # Special handling for HK market (ticker format normalization)
            if region == 'HK':
                base_ticker = self.normalize_hk_ticker(ticker)
                yf_ticker = f"{base_ticker}.HK"

                stock = yf.Ticker(yf_ticker)
                hist = stock.history(period='max')

                if not hist.empty:
                    first_date = hist.index[0].date()
                    logger.debug(f"✅ {ticker} → {yf_ticker} ({region}): {first_date}")
                    return first_date
                else:
                    logger.debug(f"⚠️ {ticker} → {yf_ticker} ({region}): No historical data")
                    return None

            # Special handling for CN market (check existing suffix)
            if region == 'CN':
                base_ticker, existing_suffix = self.normalize_cn_ticker(ticker)

                if existing_suffix:
                    # Ticker already has exchange info - use it directly
                    yf_ticker = ticker  # Use original ticker (already has .SS or .SZ)
                    stock = yf.Ticker(yf_ticker)
                    hist = stock.history(period='max')

                    if not hist.empty:
                        first_date = hist.index[0].date()
                        logger.debug(f"✅ {ticker} ({region}): {first_date} via existing suffix")
                        return first_date
                    else:
                        logger.debug(f"⚠️ {ticker} ({region}): No data with existing suffix")
                        return None
                else:
                    # Try Shanghai first, then Shenzhen
                    for exchange_suffix in ['.SS', '.SZ']:
                        yf_ticker = f"{base_ticker}{exchange_suffix}"
                        stock = yf.Ticker(yf_ticker)
                        hist = stock.history(period='max')

                        if not hist.empty:
                            first_date = hist.index[0].date()
                            logger.debug(f"✅ {ticker} → {yf_ticker} ({region}): {first_date}")
                            return first_date

                    logger.debug(f"⚠️ {ticker} ({region}): No data from both SS and SZ exchanges")
                    return None

            # Standard handling for other regions (US, JP, VN)
            suffix = REGION_SUFFIX_MAP.get(region, '')
            yf_ticker = f"{ticker}{suffix}"

            stock = yf.Ticker(yf_ticker)
            hist = stock.history(period='max')

            if not hist.empty:
                # First trading date = listing date
                first_date = hist.index[0].date()
                logger.debug(f"✅ {ticker} ({region}): {first_date}")
                return first_date
            else:
                logger.debug(f"⚠️ {ticker} ({region}): No historical data")
                return None

        except Exception as e:
            logger.debug(f"❌ {ticker} ({region}): {e}")
            return None

    def update_listing_date(self, ticker: str, region: str, listing_date: date) -> bool:
        """
        Update listing_date in database

        Args:
            ticker: Ticker symbol
            region: Region code
            listing_date: Listing date

        Returns:
            Success status
        """
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would update {ticker} ({region}) listing_date: {listing_date}")
            return True

        try:
            query = """
            UPDATE tickers
            SET listing_date = %s, last_updated = NOW()
            WHERE ticker = %s AND region = %s
            """
            success = self.db.execute_update(query, (listing_date, ticker, region))

            if success:
                logger.debug(f"✅ Updated {ticker} ({region}): listing_date={listing_date}")
            else:
                logger.warning(f"⚠️ No rows updated for {ticker} ({region})")

            return success

        except Exception as e:
            logger.error(f"Failed to update {ticker} ({region}): {e}")
            return False

    def run_backfill_region(self, region: str) -> Dict:
        """
        Run listing_date backfill for specific region

        Args:
            region: Region code

        Returns:
            Statistics dict
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🌍 Processing {region} Market")
        logger.info(f"{'='*80}")

        # Step 1: Get tickers without listing_date
        tickers = self.get_tickers_without_listing_date(region)
        logger.info(f"📊 Found {len(tickers)} tickers without listing_date")

        if not tickers:
            logger.info(f"✅ All {region} tickers have listing_date - skipping")
            return self.stats[region]

        # Show sample
        logger.info(f"\nSample tickers (first 3):")
        for ticker_info in tickers[:3]:
            logger.info(f"  {ticker_info['ticker']} ({ticker_info['name']}) - {ticker_info['asset_type']}")

        # Step 2: Fetch and update listing dates
        logger.info(f"\n🔄 Fetching listing dates from yfinance...")

        for i, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            self.stats[region]['tickers_checked'] += 1

            # Progress indicator (every 100 tickers)
            if i % 100 == 0:
                logger.info(f"  Progress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%)")

            # Fetch listing date
            listing_date = self.fetch_listing_date_yfinance(ticker, region)

            if listing_date:
                success = self.update_listing_date(ticker, region, listing_date)
                if success:
                    self.stats[region]['tickers_updated'] += 1
                else:
                    self.stats[region]['tickers_failed'] += 1
            else:
                self.stats[region]['tickers_no_data'] += 1

            # Rate limiting
            time.sleep(self.delay)

        return self.stats[region]

    def run_backfill(self) -> Dict:
        """
        Run listing_date backfill for all regions

        Returns:
            Complete statistics dict
        """
        start_time = datetime.now()
        logger.info("="*80)
        logger.info("🌎 OVERSEAS MARKETS LISTING_DATE BACKFILL")
        logger.info("="*80)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Regions: {', '.join(self.regions)}")
        logger.info(f"Data Source: yfinance (historical data)")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Rate Limit: {self.delay}s delay")
        logger.info("="*80)

        # Process each region
        for region in self.regions:
            try:
                self.run_backfill_region(region)
            except Exception as e:
                logger.error(f"❌ Failed to process {region}: {e}")
                import traceback
                traceback.print_exc()

        # Print summary
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("\n" + "=" * 80)
        logger.info("📊 BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")

        # Per-region statistics
        total_checked = 0
        total_updated = 0
        total_no_data = 0
        total_failed = 0

        logger.info(f"\n{'Region':<10} {'Checked':<10} {'Updated':<10} {'No Data':<10} {'Failed':<10}")
        logger.info("-" * 80)

        for region in self.regions:
            stats = self.stats[region]
            total_checked += stats['tickers_checked']
            total_updated += stats['tickers_updated']
            total_no_data += stats['tickers_no_data']
            total_failed += stats['tickers_failed']

            logger.info(
                f"{region:<10} {stats['tickers_checked']:<10} "
                f"{stats['tickers_updated']:<10} "
                f"{stats['tickers_no_data']:<10} "
                f"{stats['tickers_failed']:<10}"
            )

        logger.info("-" * 80)
        logger.info(
            f"{'TOTAL':<10} {total_checked:<10} {total_updated:<10} "
            f"{total_no_data:<10} {total_failed:<10}"
        )

        # Calculate success rate
        if total_checked > 0:
            success_rate = (total_updated / total_checked) * 100
            logger.info(f"\n📈 Success Rate: {success_rate:.2f}%")

        logger.info("=" * 80)

        return self.stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Backfill listing_date for overseas markets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # All overseas markets
  python3 scripts/backfill_listing_dates_overseas.py

  # Specific regions
  python3 scripts/backfill_listing_dates_overseas.py --regions US HK JP

  # Dry-run preview
  python3 scripts/backfill_listing_dates_overseas.py --dry-run --regions US

  # Slower rate (safer for large volumes)
  python3 scripts/backfill_listing_dates_overseas.py --delay 1.0
        """
    )

    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to backfill (default: all)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without DB writes'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.2,
        help='Delay between API calls in seconds (default: 0.2)'
    )

    args = parser.parse_args()

    try:
        # Check yfinance availability
        try:
            import yfinance as yf
        except ImportError:
            logger.error("❌ yfinance not installed. Install with: pip install yfinance")
            sys.exit(1)

        # Initialize
        db = PostgresDatabaseManager()
        backfiller = OverseasListingDateBackfiller(
            db,
            regions=args.regions,
            dry_run=args.dry_run,
            delay=args.delay
        )

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
