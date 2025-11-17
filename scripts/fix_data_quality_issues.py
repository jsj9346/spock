#!/usr/bin/env python3
"""
Fix Data Quality Issues (Week 4)

Purpose:
    Fix identified data quality issues from Week 4 Price Anomaly Investigation:
    1. Delete corrupted ticker 091090 data (Sept 23 - Oct 20, 2025)
    2. Clean up orphaned tickers in SQLite test database
    3. Generate data quality report

Usage:
    # Dry-run (preview changes)
    python3 scripts/fix_data_quality_issues.py --dry-run

    # Execute fixes
    python3 scripts/fix_data_quality_issues.py

    # Fix only ticker 091090
    python3 scripts/fix_data_quality_issues.py --ticker-091090-only

Database:
    - SQLite: /Users/13ruce/spock/data/spock_local.db (test database)
    - PostgreSQL: quant_platform (production - no issues detected)

References:
    - Week 4 Price Anomaly Investigation Report
    - docs/WEEK4_PRICE_ANOMALY_INVESTIGATION.md
"""

import argparse
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


class DataQualityFixer:
    """Fix data quality issues in SQLite test database."""

    def __init__(self, db_path: str, dry_run: bool = False):
        """
        Initialize data quality fixer.

        Args:
            db_path: Path to SQLite database
            dry_run: If True, only preview changes without executing
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.conn = None
        self.stats = {
            'ticker_091090_deleted': 0,
            'orphaned_tickers_found': 0,
            'orphaned_records_deleted': 0
        }

    def connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def check_ticker_091090_corruption(self) -> List[Dict]:
        """
        Check ticker 091090 for corrupted data.

        Returns:
            List of corrupted records
        """
        query = """
        SELECT date, open, high, low, close, volume,
               (high - low) / NULLIF(close, 0) * 100 as range_pct,
               (close - LAG(close) OVER (ORDER BY date)) /
                   NULLIF(LAG(close) OVER (ORDER BY date), 0) * 100 as change_pct
        FROM ohlcv_data
        WHERE ticker = '091090' AND region = 'KR'
          AND date BETWEEN '2025-09-23' AND '2025-10-20'
        ORDER BY date
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        corrupted = []
        for row in rows:
            record = dict(row)
            # Identify corrupted records
            if (record['range_pct'] is not None and record['range_pct'] > 30) or \
               (record['change_pct'] is not None and abs(record['change_pct']) > 100) or \
               (record['volume'] == 0 and record['open'] == record['close'] == 1270.0):
                corrupted.append(record)

        logger.info(f"Found {len(corrupted)} corrupted records for ticker 091090")
        return corrupted

    def delete_ticker_091090_corrupted_data(self) -> int:
        """
        Delete corrupted ticker 091090 data (2025-09-23 to 2025-10-20).

        Returns:
            Number of records deleted
        """
        query = """
        DELETE FROM ohlcv_data
        WHERE ticker = '091090' AND region = 'KR'
          AND date BETWEEN '2025-09-23' AND '2025-10-20'
        """

        if self.dry_run:
            # Count records that would be deleted
            count_query = """
            SELECT COUNT(*) as count
            FROM ohlcv_data
            WHERE ticker = '091090' AND region = 'KR'
              AND date BETWEEN '2025-09-23' AND '2025-10-20'
            """
            cursor = self.conn.cursor()
            cursor.execute(count_query)
            count = cursor.fetchone()['count']
            logger.warning(f"[DRY RUN] Would delete {count} records for ticker 091090")
            return count
        else:
            cursor = self.conn.cursor()
            cursor.execute(query)
            deleted = cursor.rowcount
            self.conn.commit()
            logger.success(f"Deleted {deleted} corrupted records for ticker 091090")
            return deleted

    def find_orphaned_tickers(self) -> List[Dict]:
        """
        Find orphaned tickers (OHLCV data without ticker registry).

        Returns:
            List of orphaned ticker stats
        """
        query = """
        SELECT
            o.ticker,
            o.region,
            COUNT(*) as record_count,
            MIN(o.date) as earliest_date,
            MAX(o.date) as latest_date
        FROM ohlcv_data o
        LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
        WHERE t.ticker IS NULL
        GROUP BY o.ticker, o.region
        ORDER BY record_count DESC
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        orphaned = [dict(row) for row in cursor.fetchall()]

        logger.info(f"Found {len(orphaned)} orphaned tickers")
        return orphaned

    def delete_orphaned_tickers(self, limit: int = None) -> int:
        """
        Delete OHLCV data for orphaned tickers.

        Args:
            limit: Maximum number of tickers to delete (None = all)

        Returns:
            Number of records deleted
        """
        # Get orphaned tickers
        orphaned = self.find_orphaned_tickers()

        if limit:
            orphaned = orphaned[:limit]

        if not orphaned:
            logger.info("No orphaned tickers found")
            return 0

        # Build delete query
        ticker_list = [(t['ticker'], t['region']) for t in orphaned]

        if self.dry_run:
            total_records = sum(t['record_count'] for t in orphaned)
            logger.warning(f"[DRY RUN] Would delete {total_records} records from {len(orphaned)} orphaned tickers")

            # Show sample
            logger.info("Sample orphaned tickers (top 10):")
            for t in orphaned[:10]:
                logger.info(f"  - {t['ticker']} ({t['region']}): {t['record_count']} records, {t['earliest_date']} to {t['latest_date']}")

            return total_records
        else:
            cursor = self.conn.cursor()
            total_deleted = 0

            for ticker, region in ticker_list:
                query = """
                DELETE FROM ohlcv_data
                WHERE ticker = ? AND region = ?
                """
                cursor.execute(query, (ticker, region))
                deleted = cursor.rowcount
                total_deleted += deleted
                logger.debug(f"Deleted {deleted} records for orphaned ticker {ticker} ({region})")

            self.conn.commit()
            logger.success(f"Deleted {total_deleted} records from {len(orphaned)} orphaned tickers")
            return total_deleted

    def generate_report(self) -> str:
        """
        Generate data quality fix report.

        Returns:
            Report as string
        """
        report = []
        report.append("=" * 80)
        report.append("DATA QUALITY FIX REPORT")
        report.append("=" * 80)
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Database: {self.db_path}")
        report.append(f"Mode: {'DRY RUN (Preview Only)' if self.dry_run else 'EXECUTION MODE'}")
        report.append("")

        # Ticker 091090 stats
        report.append("1. TICKER 091090 CORRUPTION FIX")
        report.append("-" * 40)
        report.append(f"   Records deleted: {self.stats['ticker_091090_deleted']}")
        report.append(f"   Date range: 2025-09-23 to 2025-10-20")
        report.append(f"   Issue: Price scale mismatch, extreme swings (+4,824%, -97.9%)")
        report.append("")

        # Orphaned tickers stats
        report.append("2. ORPHANED TICKERS CLEANUP")
        report.append("-" * 40)
        report.append(f"   Orphaned tickers found: {self.stats['orphaned_tickers_found']}")
        report.append(f"   Records deleted: {self.stats['orphaned_records_deleted']}")
        report.append(f"   Issue: OHLCV data without ticker registry entries")
        report.append("")

        # Summary
        report.append("SUMMARY")
        report.append("-" * 40)
        total_deleted = self.stats['ticker_091090_deleted'] + self.stats['orphaned_records_deleted']
        report.append(f"   Total records affected: {total_deleted:,}")

        if self.dry_run:
            report.append("")
            report.append("   ⚠️  This was a DRY RUN - no changes were made")
            report.append("   ⚠️  Run without --dry-run to execute fixes")
        else:
            report.append("")
            report.append("   ✅ All fixes executed successfully")

        report.append("=" * 80)

        return "\n".join(report)

    def run(self, fix_091090: bool = True, fix_orphaned: bool = True):
        """
        Run all data quality fixes.

        Args:
            fix_091090: Fix ticker 091090 corruption
            fix_orphaned: Fix orphaned tickers
        """
        try:
            self.connect()

            # Fix 1: Ticker 091090 corruption
            if fix_091090:
                logger.info("Checking ticker 091090 corruption...")
                corrupted = self.check_ticker_091090_corruption()

                if corrupted:
                    logger.warning(f"Found {len(corrupted)} corrupted records for ticker 091090")
                    deleted = self.delete_ticker_091090_corrupted_data()
                    self.stats['ticker_091090_deleted'] = deleted
                else:
                    logger.success("No corruption found for ticker 091090")

            # Fix 2: Orphaned tickers
            if fix_orphaned:
                logger.info("Checking orphaned tickers...")
                orphaned = self.find_orphaned_tickers()
                self.stats['orphaned_tickers_found'] = len(orphaned)

                if orphaned:
                    deleted = self.delete_orphaned_tickers()
                    self.stats['orphaned_records_deleted'] = deleted
                else:
                    logger.success("No orphaned tickers found")

            # Generate report
            report = self.generate_report()
            print("\n" + report)

            # Save report to file
            if not self.dry_run:
                report_path = Path(__file__).parent.parent / 'logs' / f'data_quality_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                report_path.parent.mkdir(exist_ok=True)
                report_path.write_text(report)
                logger.success(f"Report saved to: {report_path}")

        finally:
            self.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix data quality issues identified in Week 4 investigation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry-run (preview changes)
    python3 scripts/fix_data_quality_issues.py --dry-run

    # Execute all fixes
    python3 scripts/fix_data_quality_issues.py

    # Fix only ticker 091090
    python3 scripts/fix_data_quality_issues.py --ticker-091090-only

    # Fix only orphaned tickers
    python3 scripts/fix_data_quality_issues.py --orphaned-only
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without executing (default: False)'
    )

    parser.add_argument(
        '--ticker-091090-only',
        action='store_true',
        help='Fix only ticker 091090 corruption'
    )

    parser.add_argument(
        '--orphaned-only',
        action='store_true',
        help='Fix only orphaned tickers'
    )

    parser.add_argument(
        '--db-path',
        default='/Users/13ruce/spock/data/spock_local.db',
        help='Path to SQLite database (default: data/spock_local.db)'
    )

    args = parser.parse_args()

    # Validate database path
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    # Determine which fixes to run
    fix_091090 = not args.orphaned_only
    fix_orphaned = not args.ticker_091090_only

    # Run fixer
    fixer = DataQualityFixer(str(db_path), dry_run=args.dry_run)
    fixer.run(fix_091090=fix_091090, fix_orphaned=fix_orphaned)


if __name__ == '__main__':
    main()
