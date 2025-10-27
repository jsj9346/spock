#!/usr/bin/env python3
"""
Unknown Sector/Industry Code Backfill Script

Assigns standardized codes (sector_code="99", industry_code="9999") to stocks
with "Unknown" sector and industry classifications but NULL code fields.

This ensures data completeness and enables consistent filtering logic.

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
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_unknown_codes_backfill.log')
    ]
)
logger = logging.getLogger(__name__)


class UnknownCodesBackfill:
    """Backfill standardized codes for "Unknown" sector/industry classifications"""

    # Standardized codes for unknown/unclassified stocks
    UNKNOWN_SECTOR_CODE = "99"
    UNKNOWN_INDUSTRY_CODE = "9999"

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db

    def identify_stocks_needing_codes(self) -> list:
        """
        Identify stocks with "Unknown" sector/industry but NULL codes

        Returns:
            List of (ticker, name) tuples
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT t.ticker, t.name
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = 1
              AND sd.sector = 'Unknown'
              AND sd.industry = 'Unknown'
              AND (sd.sector_code IS NULL OR sd.industry_code IS NULL)
            ORDER BY t.ticker
        """

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        return [(row['ticker'], row['name']) for row in results]

    def backfill_unknown_codes(self, dry_run: bool = False) -> tuple:
        """
        Backfill sector_code and industry_code for "Unknown" stocks

        Args:
            dry_run: If True, only simulate without actual updates

        Returns:
            (success_count, failed_count)
        """
        logger.info("=" * 80)
        logger.info("📊 Unknown Sector/Industry Code Backfill")
        logger.info("=" * 80)

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only, no actual updates")

        # Identify stocks needing codes
        stocks = self.identify_stocks_needing_codes()

        if not stocks:
            logger.info("✅ No stocks found that need code updates")
            return (0, 0)

        logger.info(f"📌 Found {len(stocks)} stocks with 'Unknown' classification but NULL codes")
        logger.info(f"📌 Assigning: sector_code='{self.UNKNOWN_SECTOR_CODE}', industry_code='{self.UNKNOWN_INDUSTRY_CODE}'")
        logger.info("")

        success_count = 0
        failed_count = 0

        for ticker, name in stocks:
            try:
                if not dry_run:
                    # Update sector_code and industry_code
                    updates = {
                        'sector_code': self.UNKNOWN_SECTOR_CODE,
                        'industry_code': self.UNKNOWN_INDUSTRY_CODE
                    }
                    self.db.update_stock_details(ticker, updates)

                # Log only first 10 and last 10 to avoid spam
                if success_count < 10 or success_count >= len(stocks) - 10:
                    logger.info(f"  ✅ [{ticker}] {name}{' (DRY RUN)' if dry_run else ''}")
                elif success_count == 10:
                    logger.info(f"  ... ({len(stocks) - 20} more stocks) ...")

                success_count += 1

            except Exception as e:
                logger.error(f"  ❌ [{ticker}] {name}: {e}")
                failed_count += 1

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success_count}, Failed={failed_count}")
        logger.info("=" * 80)

        return (success_count, failed_count)

    def show_statistics(self):
        """Show comprehensive statistics on sector/industry code coverage"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Total stocks
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers
            WHERE asset_type = 'STOCK' AND region = 'KR' AND is_active = 1
        """)
        total_count = cursor.fetchone()['count']

        # Stocks with complete sector/industry data
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND sd.sector IS NOT NULL
              AND sd.sector_code IS NOT NULL
              AND sd.industry IS NOT NULL
              AND sd.industry_code IS NOT NULL
        """)
        complete_count = cursor.fetchone()['count']

        # Stocks with "Unknown" codes
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM stock_details
            WHERE sector_code = ?
              AND industry_code = ?
        """, (self.UNKNOWN_SECTOR_CODE, self.UNKNOWN_INDUSTRY_CODE))
        unknown_code_count = cursor.fetchone()['count']

        # Stocks with NULL codes
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND (sd.sector_code IS NULL OR sd.industry_code IS NULL)
        """)
        null_code_count = cursor.fetchone()['count']

        # Properly classified stocks (not "Unknown")
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND sd.sector IS NOT NULL
              AND sd.sector <> 'Unknown'
              AND sd.sector_code IS NOT NULL
              AND sd.industry_code IS NOT NULL
        """)
        proper_classification_count = cursor.fetchone()['count']

        conn.close()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 SECTOR/INDUSTRY CODE COVERAGE STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Active Stocks: {total_count}")
        logger.info(f"Complete Data (all 4 fields): {complete_count} ({complete_count/total_count*100:.1f}%)")
        logger.info("")
        logger.info(f"Properly Classified: {proper_classification_count} ({proper_classification_count/total_count*100:.1f}%)")
        logger.info(f"  → Real sector/industry with codes")
        logger.info("")
        logger.info(f"Unknown Classification: {unknown_code_count} ({unknown_code_count/total_count*100:.1f}%)")
        logger.info(f"  → sector_code='{self.UNKNOWN_SECTOR_CODE}', industry_code='{self.UNKNOWN_INDUSTRY_CODE}'")
        logger.info("")
        logger.info(f"Missing Codes (NULL): {null_code_count}")
        logger.info("")

        if null_code_count == 0:
            logger.info("✅ All stocks have sector_code and industry_code assigned")
        else:
            logger.warning(f"⚠️  {null_code_count} stocks still have NULL codes")

        logger.info("=" * 80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Unknown Sector/Industry Code Backfill')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Unknown Sector/Industry Code Backfill Script")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Unknown Codes: sector_code='99', industry_code='9999'")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = UnknownCodesBackfill(db=db)

    # Show current statistics
    logger.info("")
    logger.info("Current Statistics (Before Backfill):")
    backfill.show_statistics()

    # Execute backfill
    logger.info("")
    success, failed = backfill.backfill_unknown_codes(dry_run=args.dry_run)

    # Show final statistics
    if not args.dry_run and success > 0:
        logger.info("")
        logger.info("Final Statistics (After Backfill):")
        backfill.show_statistics()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Unknown Code Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
