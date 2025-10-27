#!/usr/bin/env python3
"""
SPAC Flag Backfill Script

Identifies and marks SPAC (Special Purpose Acquisition Company) stocks
in the stock_details table by analyzing stock names for SPAC indicators.

Detection Logic:
- Korean: "스팩", "기업인수목적"
- English: "SPAC"

Author: Spock Trading System
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_spac_backfill.log')
    ]
)
logger = logging.getLogger(__name__)


class SPACBackfill:
    """SPAC flag backfill for stock_details table"""

    # SPAC name patterns (Korean and English)
    SPAC_PATTERNS = [
        '스팩',        # Korean SPAC
        'SPAC',       # English SPAC
        '기업인수목적'  # Korean for "Purpose of Corporate Acquisition"
    ]

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db

    def identify_spac_stocks(self) -> list:
        """
        Identify SPAC stocks by name pattern matching

        Returns:
            List of (ticker, name) tuples for SPAC stocks
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Build WHERE clause for name pattern matching
        name_conditions = ' OR '.join([f"name LIKE '%{pattern}%'" for pattern in self.SPAC_PATTERNS])

        query = f"""
            SELECT t.ticker, t.name
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = 1
              AND sd.is_spac = 0
              AND ({name_conditions})
            ORDER BY t.ticker
        """

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        return [(row['ticker'], row['name']) for row in results]

    def backfill_spac_flags(self, dry_run: bool = False) -> tuple:
        """
        Backfill is_spac = 1 for identified SPAC stocks

        Args:
            dry_run: If True, only simulate without actual updates

        Returns:
            (success_count, failed_count)
        """
        logger.info("=" * 80)
        logger.info("📊 SPAC Flag Backfill")
        logger.info("=" * 80)

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only, no actual updates")

        # Identify SPAC stocks
        spac_stocks = self.identify_spac_stocks()

        if not spac_stocks:
            logger.info("✅ No SPAC stocks found that need updating")
            return (0, 0)

        logger.info(f"📌 Found {len(spac_stocks)} SPAC stocks to update:")
        logger.info("")

        success_count = 0
        failed_count = 0

        for ticker, name in spac_stocks:
            try:
                if not dry_run:
                    # Update is_spac flag
                    updates = {'is_spac': True}
                    self.db.update_stock_details(ticker, updates)

                logger.info(f"  ✅ [{ticker}] {name}{' (DRY RUN)' if dry_run else ''}")
                success_count += 1

            except Exception as e:
                logger.error(f"  ❌ [{ticker}] {name}: {e}")
                failed_count += 1

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success_count}, Failed={failed_count}")
        logger.info("=" * 80)

        return (success_count, failed_count)

    def show_spac_statistics(self):
        """Show SPAC stock statistics"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Total SPAC stocks
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM stock_details
            WHERE is_spac = 1
        """)
        spac_count = cursor.fetchone()['count']

        # Total stocks
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers
            WHERE asset_type = 'STOCK' AND region = 'KR' AND is_active = 1
        """)
        total_count = cursor.fetchone()['count']

        # SPAC stocks by name pattern (for verification)
        name_conditions = ' OR '.join([f"name LIKE '%{pattern}%'" for pattern in self.SPAC_PATTERNS])
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM tickers
            WHERE asset_type = 'STOCK'
              AND region = 'KR'
              AND is_active = 1
              AND ({name_conditions})
        """)
        pattern_match_count = cursor.fetchone()['count']

        conn.close()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 SPAC STOCK STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Active Stocks: {total_count}")
        logger.info(f"SPAC Stocks (is_spac=1): {spac_count} ({spac_count/total_count*100:.1f}%)")
        logger.info(f"Stocks with SPAC in Name: {pattern_match_count}")
        logger.info("")

        if spac_count != pattern_match_count:
            logger.warning(f"⚠️  Mismatch: {pattern_match_count} stocks have SPAC in name, but only {spac_count} marked as SPAC")
        else:
            logger.info("✅ All SPAC stocks correctly identified and marked")

        logger.info("=" * 80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='SPAC Flag Backfill')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 SPAC Flag Backfill Script")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = SPACBackfill(db=db)

    # Show current statistics
    logger.info("")
    logger.info("Current Statistics (Before Backfill):")
    backfill.show_spac_statistics()

    # Execute backfill
    logger.info("")
    success, failed = backfill.backfill_spac_flags(dry_run=args.dry_run)

    # Show final statistics
    if not args.dry_run and success > 0:
        logger.info("")
        logger.info("Final Statistics (After Backfill):")
        backfill.show_spac_statistics()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ SPAC Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
