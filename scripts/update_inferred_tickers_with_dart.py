#!/usr/bin/env python3
"""
update_inferred_tickers_with_dart.py - Update Inferred Tickers with DART Official Names

This script updates tickers that were inferred (no pykrx data) with official names from DART API.
It specifically targets timeout tickers that received placeholder names like "032850 (Inferred)".

Usage:
    python3 scripts/update_inferred_tickers_with_dart.py [--dry-run] [--limit N]
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient

# Configure logger
logger.remove()
logger.add(
    f"logs/update_dart_tickers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)
logger.add(sys.stdout, level="INFO")


class DARTTickerUpdater:
    """
    Update inferred tickers with DART official company names.

    Targets tickers with:
    - name LIKE '%Inferred%'
    - data_source = 'inference' or 'pykrx' (old backfills)
    - timeout_flag = FALSE (not yet marked)
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.dart_client = DARTApiClient()
        self.ticker_to_name = {}  # Ticker -> company name mapping
        self.stats = {
            'total_processed': 0,
            'updated': 0,
            'not_in_dart': 0,
            'already_correct': 0,
            'failed': 0
        }

        # Load DART corp codes
        self._load_dart_corp_codes()

    def _load_dart_corp_codes(self) -> None:
        """Load DART corporate codes and create ticker -> company name mapping."""
        try:
            xml_path = "config/dart_corp_codes.xml"
            logger.info(f"Loading DART corp codes from {xml_path}")

            # Parse corp codes: corp_name -> {corp_code, stock_code}
            corp_mapping = self.dart_client.parse_corp_codes(xml_path)

            # Create reverse mapping: stock_code (ticker) -> corp_name
            for corp_name, info in corp_mapping.items():
                stock_code = info.get('stock_code')
                if stock_code:
                    self.ticker_to_name[stock_code] = corp_name

            logger.info(f"Loaded {len(self.ticker_to_name)} ticker-to-name mappings from DART")

        except Exception as e:
            logger.error(f"Failed to load DART corp codes: {e}")
            raise

    def get_inferred_tickers(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Query tickers with inferred names from database.

        Returns list of tickers that need DART updates.
        """
        query = """
        SELECT ticker, name, exchange, data_source, timeout_flag
        FROM tickers
        WHERE region = 'KR'
          AND (
              name LIKE '%Inferred%'
              OR (data_source IN ('inference', 'pykrx') AND timeout_flag = FALSE)
          )
        ORDER BY ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)
        logger.info(f"Found {len(results)} tickers with inferred names")
        return results

    def update_single_ticker(self, ticker: str, current_name: str, dry_run: bool = False) -> bool:
        """
        Update a single ticker with DART official name.

        Args:
            ticker: Ticker code (6-digit)
            current_name: Current name in database
            dry_run: If True, don't update database

        Returns:
            True if successful, False otherwise
        """
        # Look up company name from DART
        dart_name = self.ticker_to_name.get(ticker)

        if not dart_name:
            logger.warning(f"⚠️  {ticker}: Not found in DART corp codes")
            self.stats['not_in_dart'] += 1
            return False

        # Check if already correct
        if dart_name == current_name:
            logger.info(f"✓ {ticker}: Already has correct name ({dart_name})")
            self.stats['already_correct'] += 1
            return True

        # Log update
        logger.info(f"✅ {ticker}: Updating name")
        logger.info(f"   OLD: {current_name}")
        logger.info(f"   NEW: {dart_name}")

        # Update database (unless dry run)
        if not dry_run:
            try:
                query = """
                UPDATE tickers
                SET name = %s,
                    data_source = 'DART',
                    timeout_flag = TRUE,
                    last_updated = NOW()
                WHERE ticker = %s AND region = 'KR'
                """
                self.db.execute_update(query, (dart_name, ticker))
                self.stats['updated'] += 1
                return True

            except Exception as e:
                logger.error(f"❌ {ticker}: Update failed - {e}")
                self.stats['failed'] += 1
                return False
        else:
            self.stats['updated'] += 1
            return True

    def update_all_inferred(self, dry_run: bool = False, limit: Optional[int] = None):
        """
        Update all inferred tickers with DART names.

        Args:
            dry_run: If True, don't update database
            limit: Max number of tickers to process (None = all)
        """
        inferred_tickers = self.get_inferred_tickers(limit=limit)

        logger.info("=" * 80)
        logger.info(f"DART Ticker Update {'(DRY RUN)' if dry_run else ''}")
        logger.info("=" * 80)
        logger.info(f"Total inferred tickers: {len(inferred_tickers)}")
        logger.info(f"DART mappings available: {len(self.ticker_to_name)}")
        logger.info("")

        for idx, row in enumerate(inferred_tickers, 1):
            ticker = row['ticker']
            current_name = row['name']

            logger.info(f"[{idx}/{len(inferred_tickers)}] Processing {ticker}...")
            self.update_single_ticker(ticker, current_name, dry_run=dry_run)
            self.stats['total_processed'] += 1

        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Update Summary")
        logger.info("=" * 80)
        logger.info(f"Total processed: {self.stats['total_processed']}")
        logger.info(f"✅ Updated: {self.stats['updated']}")
        logger.info(f"✓  Already correct: {self.stats['already_correct']}")
        logger.info(f"⚠️  Not in DART: {self.stats['not_in_dart']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        logger.info("")

        success_rate = (self.stats['updated'] + self.stats['already_correct']) / max(self.stats['total_processed'], 1) * 100
        dart_coverage = (self.stats['updated'] / max(self.stats['total_processed'], 1)) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info(f"DART coverage: {dart_coverage:.1f}%")

    def validate_updates(self) -> bool:
        """
        Validate update completeness.

        Returns:
            True if validation passes, False otherwise
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("Validation Checks")
        logger.info("=" * 80)

        # Check 1: No more inferred names
        query = """
        SELECT COUNT(*) as cnt
        FROM tickers
        WHERE region = 'KR' AND name LIKE '%Inferred%'
        """
        result = self.db.execute_query(query)
        inferred_count = result[0]['cnt']

        if inferred_count > 0:
            logger.warning(f"⚠️  Check 1 WARNING: {inferred_count} tickers still have inferred names")
            return False
        else:
            logger.info("✅ Check 1 PASSED: No tickers with inferred names")

        # Check 2: Timeout flags set correctly
        query = """
        SELECT COUNT(*) as cnt
        FROM tickers
        WHERE region = 'KR'
          AND data_source = 'DART'
          AND timeout_flag = FALSE
        """
        result = self.db.execute_query(query)
        incorrect_flags = result[0]['cnt']

        if incorrect_flags > 0:
            logger.warning(f"⚠️  Check 2 WARNING: {incorrect_flags} DART tickers missing timeout_flag")
            return False
        else:
            logger.info("✅ Check 2 PASSED: All DART tickers have timeout_flag = TRUE")

        # Check 3: Data source consistency
        query = """
        SELECT COUNT(*) as cnt
        FROM tickers
        WHERE region = 'KR'
          AND name LIKE '%Inferred%'
          AND data_source != 'inference'
        """
        result = self.db.execute_query(query)
        inconsistent = result[0]['cnt']

        if inconsistent > 0:
            logger.warning(f"⚠️  Check 3 WARNING: {inconsistent} tickers have inconsistent data_source")
            return False
        else:
            logger.info("✅ Check 3 PASSED: Data source consistency verified")

        logger.info("")
        logger.info("✅ All validation checks PASSED")
        return True


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Update inferred tickers with DART names')
    parser.add_argument('--dry-run', action='store_true', help='Test without database updates')
    parser.add_argument('--limit', type=int, help='Limit number of tickers to process')
    parser.add_argument('--validate', action='store_true', help='Run validation checks only')

    args = parser.parse_args()

    # Initialize database and updater
    db = PostgresDatabaseManager()
    updater = DARTTickerUpdater(db)

    if args.validate:
        # Validation only
        updater.validate_updates()
    else:
        # Run update
        updater.update_all_inferred(
            dry_run=args.dry_run,
            limit=args.limit
        )

        # Auto-validate after update (unless dry run)
        if not args.dry_run:
            logger.info("")
            updater.validate_updates()


if __name__ == "__main__":
    main()
