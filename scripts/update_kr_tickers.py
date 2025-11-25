#!/usr/bin/env python3
"""
KR Ticker Updater for Unified Database Update System

Updates Korean (KR) ticker table with latest listings from pykrx.
Detects new listings, delistings, and name changes for KOSPI, KOSDAQ, and KONEX markets.

Features:
- Incremental update mode (only process changes)
- Dry-run mode for preview
- Automatic delisting detection
- Name change tracking
- Statistics reporting

Usage:
    # Full update
    python3 scripts/update_kr_tickers.py

    # Dry run (preview only)
    python3 scripts/update_kr_tickers.py --dry-run

    # Incremental update (only changes)
    python3 scripts/update_kr_tickers.py --incremental

    # Verbose logging
    python3 scripts/update_kr_tickers.py --verbose

Author: Quant Investment Platform - Phase 2
Date: 2025-11-02
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Set, Tuple
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Try to import pykrx
try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    print("⚠️ pykrx not available, install with: pip install pykrx")

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_update_kr_tickers.log"
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


class KRTickerUpdater:
    """Korean ticker update orchestrator using pykrx"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize KR ticker updater

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'total_current': 0,
            'total_existing': 0,
            'new_listings': 0,
            'delistings': 0,
            'name_changes': 0,
            'unchanged': 0,
            'errors': 0
        }

        # Market info
        self.markets = {
            'KOSPI': 'Korean Stock Exchange',
            'KOSDAQ': 'Korean Securities Dealers Automated Quotations',
            'KONEX': 'Korea New Exchange'
        }

    def fetch_current_tickers(self) -> Dict[str, Dict]:
        """
        Fetch current ticker listings from pykrx

        Returns:
            Dictionary mapping ticker code to ticker info:
            {
                '005930': {'name': '삼성전자', 'market': 'KOSPI', 'is_etf': False},
                ...
            }
        """
        if not PYKRX_AVAILABLE:
            logger.error("❌ pykrx not available, cannot fetch tickers")
            return {}

        current_tickers = {}
        today = datetime.now().strftime('%Y%m%d')

        for market in ['KOSPI', 'KOSDAQ', 'KONEX']:
            try:
                logger.info(f"📊 Fetching {market} tickers...")

                # Get ticker list
                if market == 'KONEX':
                    # KONEX may not be supported in all pykrx versions
                    try:
                        ticker_list = stock.get_market_ticker_list(today, market=market)
                    except:
                        logger.warning(f"  ⚠️ {market} not supported in this pykrx version, skipping")
                        continue
                else:
                    ticker_list = stock.get_market_ticker_list(today, market=market)

                # Get ticker names
                for ticker in ticker_list:
                    try:
                        name = stock.get_market_ticker_name(ticker)

                        # Detect asset type (ETF or STOCK)
                        asset_type = 'ETF' if ('ETF' in name or 'ETN' in name or 'KODEX' in name or 'TIGER' in name) else 'STOCK'

                        current_tickers[ticker] = {
                            'name': name,
                            'market': market,
                            'asset_type': asset_type
                        }
                    except Exception as e:
                        logger.debug(f"  ⚠️ Failed to get name for {ticker}: {e}")
                        continue

                logger.info(f"  ✅ Fetched {len([t for t in current_tickers.values() if t['market'] == market])} tickers from {market}")

            except Exception as e:
                logger.error(f"  ❌ Failed to fetch {market} tickers: {e}")
                self.stats['errors'] += 1

        self.stats['total_current'] = len(current_tickers)
        logger.info(f"✅ Total current tickers: {self.stats['total_current']}")

        return current_tickers

    def get_existing_tickers(self) -> Dict[str, Dict]:
        """
        Get existing KR tickers from database

        Returns:
            Dictionary mapping ticker code to ticker info
        """
        query = """
        SELECT ticker, name, asset_type
        FROM tickers
        WHERE region = 'KR'
        """

        rows = self.db.execute_query(query)

        existing = {}
        for row in rows:
            existing[row['ticker']] = {
                'name': row['name'],
                'asset_type': row.get('asset_type', 'STOCK')
            }

        self.stats['total_existing'] = len(existing)
        logger.info(f"📂 Existing KR tickers in database: {self.stats['total_existing']}")

        return existing

    def detect_changes(self, current: Dict[str, Dict], existing: Dict[str, Dict]) -> Tuple[List, List, List]:
        """
        Detect new listings, delistings, and name changes

        Args:
            current: Current tickers from pykrx
            existing: Existing tickers from database

        Returns:
            (new_listings, delistings, name_changes)
        """
        current_codes = set(current.keys())
        existing_codes = set(existing.keys())

        # New listings
        new_codes = current_codes - existing_codes
        new_listings = [(code, current[code]) for code in new_codes]

        # Delistings
        delisted_codes = existing_codes - current_codes
        delistings = list(delisted_codes)

        # Name changes
        name_changes = []
        for code in current_codes & existing_codes:
            if current[code]['name'] != existing[code]['name']:
                name_changes.append((code, existing[code]['name'], current[code]['name']))

        self.stats['new_listings'] = len(new_listings)
        self.stats['delistings'] = len(delistings)
        self.stats['name_changes'] = len(name_changes)
        self.stats['unchanged'] = len(current_codes & existing_codes) - len(name_changes)

        # Log changes
        if new_listings:
            logger.info(f"🆕 New listings detected: {len(new_listings)}")
            for code, info in new_listings[:10]:  # Show first 10
                logger.info(f"  + {code}: {info['name']} ({info['market']})")
            if len(new_listings) > 10:
                logger.info(f"  ... and {len(new_listings) - 10} more")

        if delistings:
            logger.info(f"📉 Delistings detected: {len(delistings)}")
            for code in delistings[:10]:  # Show first 10
                logger.info(f"  - {code}: {existing[code]['name']}")
            if len(delistings) > 10:
                logger.info(f"  ... and {len(delistings) - 10} more")

        if name_changes:
            logger.info(f"✏️  Name changes detected: {len(name_changes)}")
            for code, old_name, new_name in name_changes[:5]:  # Show first 5
                logger.info(f"  ~ {code}: {old_name} → {new_name}")
            if len(name_changes) > 5:
                logger.info(f"  ... and {len(name_changes) - 5} more")

        if not new_listings and not delistings and not name_changes:
            logger.info("✅ No changes detected")

        return new_listings, delistings, name_changes

    def upsert_tickers(self, current: Dict[str, Dict]) -> int:
        """
        Upsert tickers to database

        Args:
            current: Current tickers to upsert

        Returns:
            Number of records upserted
        """
        if self.dry_run:
            logger.info("🔍 DRY RUN: Would upsert {} tickers".format(len(current)))
            return len(current)

        upsert_query = """
        INSERT INTO tickers (ticker, name, region, exchange, currency, asset_type, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (ticker, region)
        DO UPDATE SET
            name = EXCLUDED.name,
            exchange = EXCLUDED.exchange,
            asset_type = EXCLUDED.asset_type,
            last_updated = NOW()
        """

        records = [
            (code, info['name'], 'KR', info['market'], 'KRW', info['asset_type'])
            for code, info in current.items()
        ]

        try:
            self.db.execute_many(upsert_query, records)
            logger.info(f"✅ Upserted {len(records)} tickers to database")
            return len(records)
        except Exception as e:
            logger.error(f"❌ Failed to upsert tickers: {e}")
            self.stats['errors'] += 1
            return 0

    def mark_delistings(self, delistings: List[str]) -> int:
        """
        Mark delisted tickers (keep in database but mark inactive)

        Args:
            delistings: List of delisted ticker codes

        Returns:
            Number of tickers marked
        """
        if not delistings:
            return 0

        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would mark {len(delistings)} tickers as delisted")
            return len(delistings)

        # Note: We don't delete tickers, just mark them
        # You may want to add a 'status' or 'active' column to track this
        # For now, we just log the delistings
        logger.info(f"ℹ️  {len(delistings)} delistings detected (not removing from database)")
        return len(delistings)

    def run_update(self, incremental: bool = False) -> Dict:
        """
        Run ticker update process

        Args:
            incremental: If True, only process changes

        Returns:
            Statistics dictionary
        """
        logger.info("="*80)
        logger.info("KR Ticker Update - Starting")
        logger.info("="*80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Incremental: {incremental}")
        logger.info(f"Database: {self.db.database}")
        logger.info("="*80)

        start_time = datetime.now()

        try:
            # Step 1: Fetch current tickers from pykrx
            current_tickers = self.fetch_current_tickers()

            if not current_tickers:
                logger.error("❌ No tickers fetched, aborting")
                return self.stats

            # Step 2: Get existing tickers from database
            existing_tickers = self.get_existing_tickers()

            # Step 3: Detect changes
            new_listings, delistings, name_changes = self.detect_changes(current_tickers, existing_tickers)

            # Step 4: Update database
            if incremental and not new_listings and not delistings and not name_changes:
                logger.info("✅ No changes detected, skipping update")
            else:
                self.upsert_tickers(current_tickers)
                self.mark_delistings(delistings)

        except Exception as e:
            logger.error(f"❌ Update failed: {e}")
            self.stats['errors'] += 1
            raise

        finally:
            # Print summary
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("="*80)
            logger.info("KR Ticker Update - Summary")
            logger.info("="*80)
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Total current tickers: {self.stats['total_current']}")
            logger.info(f"Total existing tickers: {self.stats['total_existing']}")
            logger.info(f"New listings: {self.stats['new_listings']}")
            logger.info(f"Delistings: {self.stats['delistings']}")
            logger.info(f"Name changes: {self.stats['name_changes']}")
            logger.info(f"Unchanged: {self.stats['unchanged']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info("="*80)

        # Add success flag
        self.stats['success'] = self.stats['errors'] == 0
        self.stats['duration'] = duration

        return self.stats


def main():
    """Main entry point for standalone execution"""
    parser = argparse.ArgumentParser(
        description='Update Korean (KR) ticker table from pykrx'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database writes'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only process changes (skip if no changes detected)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    args = parser.parse_args()

    # Adjust logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize database
        logger.info("Connecting to PostgreSQL database...")
        db = PostgresDatabaseManager()
        logger.info("✅ Database connection established")

        # Run update
        updater = KRTickerUpdater(db, dry_run=args.dry_run)
        result = updater.run_update(incremental=args.incremental)

        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Update interrupted by user (Ctrl+C)")
        sys.exit(130)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == '__main__':
    main()
