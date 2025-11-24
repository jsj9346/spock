#!/usr/bin/env python3
"""
Region Column Migration Script

Migrates NULL region values in ohlcv_data table by joining with tickers table.

Usage:
    # Dry-run (recommended first)
    python3 scripts/migrate_region_column.py --dry-run

    # Execute migration
    python3 scripts/migrate_region_column.py

    # Verbose mode
    python3 scripts/migrate_region_column.py --dry-run --verbose

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import sqlite3
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RegionMigration:
    """
    Handles migration of NULL region values in ohlcv_data table

    Strategy:
    1. Analyze current state (NULL count, affected tickers)
    2. JOIN with tickers table to identify correct regions
    3. Update ohlcv_data.region in transaction
    4. Verify post-migration state
    """

    def __init__(self, db_path: str, dry_run: bool = False, verbose: bool = False):
        """
        Initialize migration

        Args:
            db_path: Path to SQLite database
            dry_run: If True, simulate without actual updates
            verbose: Enable verbose logging
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.verbose = verbose

        if verbose:
            logger.setLevel(logging.DEBUG)

        logger.info(f"{'DRY RUN MODE' if dry_run else 'LIVE MODE'}: {db_path}")

    def connect(self) -> sqlite3.Connection:
        """Create database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_pre_migration(self, conn: sqlite3.Connection) -> Dict:
        """
        Analyze database state before migration

        Returns:
            Dictionary with analysis results
        """
        logger.info("📊 Analyzing pre-migration state...")

        cursor = conn.cursor()

        # 1. Count NULL regions
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL")
        null_count = cursor.fetchone()[0]

        # 2. Count total rows
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        total_count = cursor.fetchone()[0]

        # 3. Get unique tickers with NULL region
        cursor.execute("""
            SELECT ticker, COUNT(*) as row_count
            FROM ohlcv_data
            WHERE region IS NULL
            GROUP BY ticker
            ORDER BY row_count DESC
        """)
        null_tickers = [dict(row) for row in cursor.fetchall()]

        # 4. Check if tickers exist in tickers table
        cursor.execute("""
            SELECT COUNT(DISTINCT o.ticker)
            FROM ohlcv_data o
            INNER JOIN tickers t ON o.ticker = t.ticker
            WHERE o.region IS NULL
        """)
        matched_count = cursor.fetchone()[0]

        # 5. Check for orphaned tickers
        cursor.execute("""
            SELECT COUNT(DISTINCT o.ticker)
            FROM ohlcv_data o
            LEFT JOIN tickers t ON o.ticker = t.ticker
            WHERE o.region IS NULL AND t.ticker IS NULL
        """)
        orphaned_count = cursor.fetchone()[0]

        # 6. Get region mapping from tickers
        cursor.execute("""
            SELECT DISTINCT
                o.ticker,
                t.region,
                t.name,
                COUNT(*) as rows_to_update
            FROM ohlcv_data o
            INNER JOIN tickers t ON o.ticker = t.ticker
            WHERE o.region IS NULL
            GROUP BY o.ticker, t.region, t.name
            ORDER BY rows_to_update DESC
        """)
        migration_plan = [dict(row) for row in cursor.fetchall()]

        results = {
            'null_count': null_count,
            'total_count': total_count,
            'null_percentage': (null_count / total_count * 100) if total_count > 0 else 0,
            'unique_tickers': len(null_tickers),
            'null_tickers': null_tickers,
            'matched_count': matched_count,
            'orphaned_count': orphaned_count,
            'migration_plan': migration_plan
        }

        return results

    def print_analysis(self, analysis: Dict):
        """Print analysis results"""
        logger.info("=" * 70)
        logger.info("PRE-MIGRATION ANALYSIS")
        logger.info("=" * 70)
        logger.info(f"Total OHLCV rows:        {analysis['total_count']:,}")
        logger.info(f"NULL region rows:        {analysis['null_count']:,} ({analysis['null_percentage']:.2f}%)")
        logger.info(f"Unique tickers:          {analysis['unique_tickers']}")
        logger.info(f"Matched in tickers:      {analysis['matched_count']}")
        logger.info(f"Orphaned (not matched):  {analysis['orphaned_count']}")
        logger.info("")

        if analysis['orphaned_count'] > 0:
            logger.warning("⚠️  WARNING: Some tickers not found in tickers table!")
            logger.warning("    These rows will NOT be updated.")

        if analysis['migration_plan']:
            logger.info("Migration Plan:")
            logger.info("-" * 70)
            for i, plan in enumerate(analysis['migration_plan'], 1):
                logger.info(f"{i}. {plan['ticker']} ({plan['name']}) -> {plan['region']} "
                          f"({plan['rows_to_update']} rows)")
            logger.info("=" * 70)

    def execute_migration(self, conn: sqlite3.Connection, analysis: Dict) -> Dict:
        """
        Execute migration with transaction

        Args:
            conn: Database connection
            analysis: Pre-migration analysis results

        Returns:
            Migration execution results
        """
        if self.dry_run:
            logger.info("🔍 DRY RUN: Simulating migration (no actual updates)")
            return {
                'updated_rows': analysis['null_count'] - analysis['orphaned_count'],
                'failed_rows': analysis['orphaned_count'],
                'execution_time': 0
            }

        logger.info("🚀 Starting migration...")
        start_time = datetime.now()

        try:
            cursor = conn.cursor()

            # Begin transaction
            conn.execute("BEGIN TRANSACTION")

            # Update query: JOIN with tickers to set region
            update_query = """
                UPDATE ohlcv_data
                SET region = (
                    SELECT t.region
                    FROM tickers t
                    WHERE t.ticker = ohlcv_data.ticker
                )
                WHERE region IS NULL
                AND ticker IN (SELECT ticker FROM tickers)
            """

            cursor.execute(update_query)
            updated_rows = cursor.rowcount

            # Commit transaction
            conn.commit()

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            logger.info(f"✅ Migration complete: {updated_rows} rows updated in {execution_time:.2f}s")

            return {
                'updated_rows': updated_rows,
                'failed_rows': analysis['orphaned_count'],
                'execution_time': execution_time
            }

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise

    def analyze_post_migration(self, conn: sqlite3.Connection) -> Dict:
        """
        Analyze database state after migration

        Returns:
            Dictionary with analysis results
        """
        logger.info("📊 Analyzing post-migration state...")

        cursor = conn.cursor()

        # 1. Count remaining NULL regions
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL")
        null_count = cursor.fetchone()[0]

        # 2. Region distribution
        cursor.execute("""
            SELECT
                COALESCE(region, 'NULL') as region,
                COUNT(*) as count
            FROM ohlcv_data
            GROUP BY region
            ORDER BY count DESC
        """)
        distribution = [dict(row) for row in cursor.fetchall()]

        results = {
            'null_count': null_count,
            'distribution': distribution
        }

        return results

    def print_post_analysis(self, post_analysis: Dict):
        """Print post-migration analysis"""
        logger.info("=" * 70)
        logger.info("POST-MIGRATION ANALYSIS")
        logger.info("=" * 70)
        logger.info(f"Remaining NULL regions:  {post_analysis['null_count']:,}")
        logger.info("")
        logger.info("Region Distribution:")
        logger.info("-" * 70)
        for dist in post_analysis['distribution']:
            logger.info(f"  {dist['region']:10s}: {dist['count']:,} rows")
        logger.info("=" * 70)

    def run(self):
        """
        Execute full migration workflow

        Workflow:
        1. Analyze pre-migration state
        2. Print migration plan
        3. Execute migration (or simulate if dry-run)
        4. Analyze post-migration state
        5. Verify success
        """
        logger.info("🚀 Starting Region Migration Script")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("")

        conn = self.connect()

        try:
            # Step 1: Pre-migration analysis
            pre_analysis = self.analyze_pre_migration(conn)
            self.print_analysis(pre_analysis)

            if pre_analysis['null_count'] == 0:
                logger.info("✅ No NULL regions found. Migration not needed.")
                return

            # Step 2: Confirm execution (if not dry-run)
            if not self.dry_run:
                logger.warning("")
                logger.warning("⚠️  This will update the database!")
                logger.warning("⚠️  Press Ctrl+C within 5 seconds to cancel...")
                import time
                time.sleep(5)
                logger.info("Proceeding with migration...")

            # Step 3: Execute migration
            migration_result = self.execute_migration(conn, pre_analysis)

            # Step 4: Post-migration analysis
            if not self.dry_run:
                post_analysis = self.analyze_post_migration(conn)
                self.print_post_analysis(post_analysis)

                # Step 5: Verify success
                if post_analysis['null_count'] == pre_analysis['orphaned_count']:
                    logger.info("✅ Migration successful!")
                    logger.info(f"   Updated: {migration_result['updated_rows']} rows")
                    if migration_result['failed_rows'] > 0:
                        logger.warning(f"   Orphaned: {migration_result['failed_rows']} rows (not updated)")
                else:
                    logger.error("❌ Migration verification failed!")
                    logger.error(f"   Expected NULL count: {pre_analysis['orphaned_count']}")
                    logger.error(f"   Actual NULL count: {post_analysis['null_count']}")
            else:
                logger.info("✅ Dry-run complete. No changes made.")
                logger.info(f"   Would update: {migration_result['updated_rows']} rows")
                if migration_result['failed_rows'] > 0:
                    logger.warning(f"   Would skip: {migration_result['failed_rows']} orphaned rows")

        finally:
            conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Migrate NULL region values in ohlcv_data table'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate migration without actual updates'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--db-path',
        default='/Users/13ruce/spock/data/spock_local.db',
        help='Path to SQLite database (default: data/spock_local.db)'
    )

    args = parser.parse_args()

    # Check if database exists
    if not os.path.exists(args.db_path):
        logger.error(f"❌ Database not found: {args.db_path}")
        sys.exit(1)

    # Run migration
    migration = RegionMigration(
        db_path=args.db_path,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    migration.run()


if __name__ == '__main__':
    main()
