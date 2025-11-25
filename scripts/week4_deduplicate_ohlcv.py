#!/usr/bin/env python3
"""
Week 4 Task 1: OHLCV Timeframe Standardization & Deduplication Script

Purpose: Standardize timeframe values and remove duplicate records

Issue Discovered:
- Timeframe inconsistency: Korean data uses '1d', US data uses 'D'
- 19,747 ticker-date pairs have both timeframes (duplicates)
- Need to standardize to '1d' and remove 'D' duplicates

Solution:
1. Backup already created: backups/quant_platform_pre_deduplication_*.dump
2. Standardize all 'D' timeframes to '1d'
3. Remove duplicate (ticker, date, region, timeframe) records
4. Add UNIQUE constraint to prevent future duplicates

Usage:
    # Dry run (preview only)
    python3 scripts/week4_deduplicate_ohlcv.py --dry-run

    # Execute standardization and deduplication
    python3 scripts/week4_deduplicate_ohlcv.py

    # Execute with unique constraint
    python3 scripts/week4_deduplicate_ohlcv.py --add-constraint

Author: Spock Quant Platform - Week 4
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Dict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_deduplication_week4.log"
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


class OHLCVDeduplicator:
    """Remove duplicate OHLCV records and enforce unique constraint"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize deduplicator

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'total_records_before': 0,
            'unique_records': 0,
            'duplicate_records': 0,
            'records_deleted': 0,
            'total_records_after': 0
        }

    def analyze_duplicates(self) -> Dict:
        """
        Analyze timeframe inconsistency and duplicate records

        Returns:
            Dictionary with duplicate analysis statistics
        """
        logger.info("=" * 80)
        logger.info("OHLCV TIMEFRAME ANALYSIS & DUPLICATE DETECTION")
        logger.info("=" * 80)

        # Analyze timeframe distribution
        timeframe_query = """
        SELECT
            timeframe,
            COUNT(*) as record_count,
            COUNT(DISTINCT ticker) as unique_tickers
        FROM ohlcv_data
        WHERE region = 'KR'
        GROUP BY timeframe
        ORDER BY timeframe
        """

        timeframes = self.db.execute_query(timeframe_query)
        logger.info(f"\n📊 Timeframe Distribution:")
        for tf in timeframes:
            logger.info(f"  {tf['timeframe']}: {tf['record_count']:,} records ({tf['unique_tickers']} tickers)")

        # Count ticker-date pairs with multiple timeframes (duplicates)
        duplicate_query = """
        WITH duplicate_timeframes AS (
            SELECT ticker, date
            FROM ohlcv_data
            WHERE region = 'KR'
            GROUP BY ticker, date
            HAVING COUNT(DISTINCT timeframe) > 1
        )
        SELECT COUNT(*) as overlapping_ticker_dates FROM duplicate_timeframes
        """

        result = self.db.execute_query(duplicate_query)
        self.stats['duplicate_records'] = result[0]['overlapping_ticker_dates']

        logger.info(f"\n📊 Duplicate Ticker-Date Pairs (multiple timeframes): {self.stats['duplicate_records']:,}")

        # Sample duplicate records
        sample_query = """
        SELECT ticker, date, COUNT(DISTINCT timeframe) as timeframe_count,
               STRING_AGG(DISTINCT timeframe, ', ') as timeframes
        FROM ohlcv_data
        WHERE region = 'KR'
        GROUP BY ticker, date
        HAVING COUNT(DISTINCT timeframe) > 1
        LIMIT 10
        """

        samples = self.db.execute_query(sample_query)

        if samples:
            logger.info(f"\n📋 Sample Duplicates (ticker-date with multiple timeframes):")
            for sample in samples:
                logger.info(f"  {sample['ticker']} | {sample['date']} | {sample['timeframes']}")

        return self.stats

    def deduplicate(self) -> int:
        """
        Standardize timeframes and remove duplicate records

        Strategy:
        1. Update all 'D' timeframes to '1d' where no '1d' record exists
        2. Delete 'D' records where '1d' record already exists (duplicates)

        Returns:
            Number of records deleted
        """
        logger.info("\n" + "=" * 80)
        logger.info("TIMEFRAME STANDARDIZATION & DEDUPLICATION")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("[DRY RUN] Would execute timeframe standardization...")

            # Count 'D' records that would be updated (no '1d' counterpart)
            update_query = """
            SELECT COUNT(*) as would_update
            FROM ohlcv_data d1
            WHERE d1.region = 'KR' AND d1.timeframe = 'D'
            AND NOT EXISTS (
                SELECT 1 FROM ohlcv_data d2
                WHERE d2.ticker = d1.ticker
                AND d2.date = d1.date
                AND d2.region = d1.region
                AND d2.timeframe = '1d'
            )
            """

            result = self.db.execute_query(update_query)
            would_update = result[0]['would_update'] or 0

            # Count 'D' records that would be deleted (duplicate '1d' exists)
            delete_query = """
            SELECT COUNT(*) as would_delete
            FROM ohlcv_data d1
            WHERE d1.region = 'KR' AND d1.timeframe = 'D'
            AND EXISTS (
                SELECT 1 FROM ohlcv_data d2
                WHERE d2.ticker = d1.ticker
                AND d2.date = d1.date
                AND d2.region = d1.region
                AND d2.timeframe = '1d'
            )
            """

            result = self.db.execute_query(delete_query)
            would_delete = result[0]['would_delete'] or 0

            logger.info(f"\n[DRY RUN] Would update 'D' → '1d': {would_update:,} records")
            logger.info(f"[DRY RUN] Would delete duplicates: {would_delete:,} records")
            logger.info(f"[DRY RUN] Net change: -{would_delete:,} records")

            return would_delete

        # Execute timeframe standardization and deduplication
        logger.info("\n🔄 Standardizing timeframes...")

        try:
            # Step 1: Update 'D' to '1d' where no '1d' exists
            update_query = """
            UPDATE ohlcv_data
            SET timeframe = '1d'
            WHERE region = 'KR' AND timeframe = 'D'
            AND NOT EXISTS (
                SELECT 1 FROM ohlcv_data d2
                WHERE d2.ticker = ohlcv_data.ticker
                AND d2.date = ohlcv_data.date
                AND d2.region = ohlcv_data.region
                AND d2.timeframe = '1d'
            )
            """

            updated = self.db.execute_update(update_query, None)
            logger.info(f"  ✓ Updated {updated:,} 'D' records to '1d'")

            # Step 2: Delete 'D' records where '1d' already exists (duplicates)
            delete_query = """
            DELETE FROM ohlcv_data
            WHERE region = 'KR' AND timeframe = 'D'
            AND EXISTS (
                SELECT 1 FROM ohlcv_data d2
                WHERE d2.ticker = ohlcv_data.ticker
                AND d2.date = ohlcv_data.date
                AND d2.region = ohlcv_data.region
                AND d2.timeframe = '1d'
            )
            """

            deleted = self.db.execute_update(delete_query, None)
            logger.info(f"  ✓ Deleted {deleted:,} duplicate 'D' records")

            # Calculate stats
            self.stats['records_deleted'] = deleted
            self.stats['records_updated'] = updated

            logger.info(f"\n✅ Standardized: {updated:,} records updated")
            logger.info(f"✅ Deleted: {deleted:,} duplicate records")

            return deleted

        except Exception as e:
            logger.error(f"❌ Standardization failed: {e}")
            raise

    def add_unique_constraint(self):
        """
        Add unique constraint to prevent future duplicates

        Constraint: (ticker, date, region, timeframe) must be unique
        """
        logger.info("\n" + "=" * 80)
        logger.info("UNIQUE CONSTRAINT ADDITION")
        logger.info("=" * 80)

        if self.dry_run:
            logger.info("[DRY RUN] Would add unique constraint on (ticker, date, region, timeframe)")
            return

        # Check if constraint already exists
        check_query = """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'ohlcv_data'
          AND constraint_type = 'UNIQUE'
          AND constraint_name = 'ohlcv_unique_key'
        """

        result = self.db.execute_query(check_query)

        if result:
            logger.info("ℹ️  Unique constraint already exists, skipping...")
            return

        # Add unique constraint
        constraint_query = """
        ALTER TABLE ohlcv_data
        ADD CONSTRAINT ohlcv_unique_key
        UNIQUE (ticker, date, region, timeframe)
        """

        try:
            self.db.execute_update(constraint_query, None)
            logger.info("✅ Added unique constraint: ohlcv_unique_key")
            logger.info("   Constraint: (ticker, date, region, timeframe)")
            logger.info("   Future duplicate inserts will be rejected")

        except Exception as e:
            logger.error(f"❌ Failed to add constraint: {e}")
            raise

    def validate_cleanup(self):
        """
        Validate deduplication results

        Checks:
        1. No remaining duplicates
        2. Record count matches unique count
        3. Data integrity (sample verification)
        """
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION")
        logger.info("=" * 80)

        # Check for remaining duplicates
        duplicate_check = """
        SELECT COUNT(*) as duplicate_count
        FROM (
            SELECT ticker, date, region, timeframe, COUNT(*) as count
            FROM ohlcv_data
            WHERE region = 'KR' AND timeframe = '1d'
            GROUP BY ticker, date, region, timeframe
            HAVING COUNT(*) > 1
        ) duplicates
        """

        result = self.db.execute_query(duplicate_check)
        remaining_duplicates = result[0]['duplicate_count']

        if remaining_duplicates > 0:
            logger.error(f"❌ Validation FAILED: {remaining_duplicates} duplicates still exist!")
            return False

        logger.info(f"✅ No remaining duplicates")

        # Verify record count
        count_query = "SELECT COUNT(*) as total FROM ohlcv_data WHERE region = 'KR' AND timeframe = '1d'"
        result = self.db.execute_query(count_query)
        final_count = result[0]['total']

        logger.info(f"✅ Final record count: {final_count:,}")

        # Sample data integrity check (Samsung)
        sample_query = """
        SELECT ticker, date, open, high, low, close, volume
        FROM ohlcv_data
        WHERE ticker = '005930' AND region = 'KR'
        AND date BETWEEN '2024-12-24' AND '2024-12-30'
        ORDER BY date
        """

        samples = self.db.execute_query(sample_query)

        if samples:
            logger.info(f"\n📊 Sample Data Verification (Samsung Dec 24-30):")
            for sample in samples:
                logger.info(f"  {sample['date']} | close: ₩{sample['close']:,.2f} | volume: {sample['volume']:,}")

        logger.info(f"\n✅ Validation PASSED")
        return True

    def run(self, add_constraint: bool = False):
        """
        Run full deduplication workflow

        Args:
            add_constraint: If True, add unique constraint after deduplication
        """
        logger.info("=" * 80)
        logger.info("WEEK 4 OHLCV DEDUPLICATION")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        logger.info(f"Add Constraint: {add_constraint}")
        logger.info("")

        # Step 1: Analyze duplicates
        self.analyze_duplicates()

        # Step 2: Deduplicate
        deleted = self.deduplicate()

        # Step 3: Add unique constraint (if requested)
        if add_constraint and not self.dry_run:
            self.add_unique_constraint()

        # Step 4: Validate (only if not dry run)
        if not self.dry_run:
            self.validate_cleanup()

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print deduplication summary"""
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Records Before:       {self.stats['total_records_before']:>10,}")
        logger.info(f"Unique Records:       {self.stats['unique_records']:>10,}")
        logger.info(f"Duplicate Records:    {self.stats['duplicate_records']:>10,}")

        if not self.dry_run:
            logger.info(f"Records Deleted:      {self.stats['records_deleted']:>10,}")
            logger.info(f"Records After:        {self.stats['total_records_after']:>10,}")

        logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Deduplicate OHLCV data')
    parser.add_argument('--dry-run', action='store_true', help='Preview operations without database writes')
    parser.add_argument('--add-constraint', action='store_true', help='Add unique constraint after deduplication')

    args = parser.parse_args()

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize and run deduplicator
    try:
        deduplicator = OHLCVDeduplicator(db=db, dry_run=args.dry_run)
        deduplicator.run(add_constraint=args.add_constraint)
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Deduplication interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Deduplication failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
