"""
Migration 002: Add lot_size column to tickers table

Purpose: Support overseas stock trading units (lot size/board lot) for global market orders

Created: 2025-10-17
Target Tables: tickers

Changes:
- Add lot_size INTEGER column (default 1)
- Set region-based default values
- Add validation constraints

Rollback: Remove lot_size column
"""

import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime
from typing import Dict, List

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class LotSizeMigration:
    """Migration 002: Add lot_size column to tickers table"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.migration_version = '002'
        self.migration_name = 'add_lot_size_column'

    def execute(self, dry_run: bool = False):
        """
        Execute forward migration

        Args:
            dry_run: If True, preview changes without applying
        """
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}=== Migration 002: Add lot_size Column ===")

        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            return False

        # Backup database
        if not dry_run:
            self._backup_database()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Step 1: Check if column already exists
            if self._column_exists(cursor, 'tickers', 'lot_size'):
                logger.warning("⚠️  Column 'lot_size' already exists in 'tickers' table")
                conn.close()
                return True

            # Step 2: Add lot_size column
            logger.info("📝 Step 1: Adding lot_size column...")
            if dry_run:
                logger.info("  [DRY RUN] Would execute: ALTER TABLE tickers ADD COLUMN lot_size INTEGER DEFAULT 1")
            else:
                cursor.execute("""
                    ALTER TABLE tickers ADD COLUMN lot_size INTEGER DEFAULT 1
                """)
                logger.info("  ✅ Column added successfully")

            # Step 3: Set region-based default values
            logger.info("📝 Step 2: Setting region-based lot_size defaults...")

            region_defaults = {
                'KR': 1,    # Korea: 1 share
                'US': 1,    # US: 1 share
                'CN': 100,  # China: 100 shares
                'JP': 100,  # Japan: 100 shares
                'VN': 100,  # Vietnam: 100 shares
                # HK: NULL (will be fetched from API during ticker scan)
            }

            for region, lot_size in region_defaults.items():
                if dry_run:
                    # Preview: Count affected rows (without checking lot_size column)
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM tickers
                        WHERE region = ?
                    """, (region,))
                    count = cursor.fetchone()['count']
                    logger.info(
                        f"  [DRY RUN] Would update {count} tickers: "
                        f"region={region}, lot_size={lot_size}"
                    )
                else:
                    cursor.execute("""
                        UPDATE tickers
                        SET lot_size = ?
                        WHERE region = ? AND (lot_size IS NULL OR lot_size = 1)
                    """, (lot_size, region))
                    updated_count = cursor.rowcount
                    logger.info(
                        f"  ✅ Updated {updated_count} tickers: "
                        f"region={region}, lot_size={lot_size}"
                    )

            # Step 4: Verify data integrity
            logger.info("📝 Step 3: Verifying data integrity...")

            if dry_run:
                logger.info("  [DRY RUN] Would verify lot_size data integrity")
            else:
                verification = self._verify_lot_size_data(cursor)

                if verification['success']:
                    logger.info("  ✅ Data integrity verified:")
                    for region, count in verification['region_counts'].items():
                        logger.info(f"    - {region}: {count} tickers")
                    logger.info(f"  📊 Total tickers with lot_size: {verification['total_with_lot_size']}")
                    logger.info(f"  📊 Tickers with NULL lot_size: {verification['null_count']} (HK expected)")
                else:
                    logger.error("  ❌ Data integrity verification failed")
                    raise ValueError(verification['error'])

            # Step 5: Commit changes
            if not dry_run:
                conn.commit()
                logger.info("✅ Migration 002 completed successfully")
            else:
                logger.info("✅ [DRY RUN] Migration preview completed (no changes made)")

            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            if not dry_run:
                conn.rollback()
            conn.close()
            return False

    def rollback(self):
        """Execute rollback (remove lot_size column)"""
        logger.info("=== Migration 002 Rollback: Remove lot_size Column ===")

        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            return False

        # Backup before rollback
        self._backup_database(suffix='_before_rollback')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check if column exists
            if not self._column_exists(cursor, 'tickers', 'lot_size'):
                logger.warning("⚠️  Column 'lot_size' does not exist (already rolled back?)")
                conn.close()
                return True

            logger.info("📝 Removing lot_size column...")

            # SQLite doesn't support DROP COLUMN directly
            # We need to recreate the table without lot_size column

            # Step 1: Create backup table
            logger.info("  Step 1: Creating backup table...")
            cursor.execute("""
                CREATE TABLE tickers_backup AS
                SELECT
                    ticker, name, name_eng, exchange, market_tier, region, currency,
                    asset_type, listing_date, is_active, delisting_date,
                    created_at, last_updated, data_source
                FROM tickers
            """)

            # Step 2: Drop original table
            logger.info("  Step 2: Dropping original table...")
            cursor.execute("DROP TABLE tickers")

            # Step 3: Rename backup table
            logger.info("  Step 3: Restoring table without lot_size...")
            cursor.execute("ALTER TABLE tickers_backup RENAME TO tickers")

            # Step 4: Recreate indexes
            logger.info("  Step 4: Recreating indexes...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_exchange ON tickers(exchange)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_asset_type ON tickers(asset_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_region ON tickers(region)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickers_exchange_tier ON tickers(exchange, market_tier)")

            conn.commit()
            conn.close()

            logger.info("✅ Rollback completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            conn.rollback()
            conn.close()
            return False

    def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        """Check if column exists in table"""
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns

    def _backup_database(self, suffix: str = '_before_migration_002'):
        """Create database backup"""
        import shutil

        backup_dir = 'data/backups'
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'spock_local{suffix}_{timestamp}.db')

        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"💾 Database backed up: {backup_path}")
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            raise

    def _verify_lot_size_data(self, cursor) -> Dict:
        """Verify lot_size data integrity after migration"""
        try:
            # Count tickers by region and lot_size
            cursor.execute("""
                SELECT
                    region,
                    lot_size,
                    COUNT(*) as count
                FROM tickers
                WHERE lot_size IS NOT NULL
                GROUP BY region, lot_size
                ORDER BY region, lot_size
            """)

            region_lot_size = cursor.fetchall()

            # Count NULL lot_size (expected for HK)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tickers
                WHERE lot_size IS NULL
            """)
            null_count = cursor.fetchone()[0]

            # Count total tickers with lot_size
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM tickers
                WHERE lot_size IS NOT NULL
            """)
            total_with_lot_size = cursor.fetchone()[0]

            # Build region summary
            region_counts = {}
            for row in region_lot_size:
                region = row[0]
                lot_size = row[1]
                count = row[2]

                if region not in region_counts:
                    region_counts[region] = 0
                region_counts[region] += count

                logger.debug(f"  {region}: lot_size={lot_size}, count={count}")

            # Validate expected lot_size values
            expected_lot_sizes = {
                'KR': [1],
                'US': [1],
                'CN': [100],
                'JP': [100],
                'VN': [100],
                # HK: NULL or variable (100-2000)
            }

            for region, expected_values in expected_lot_sizes.items():
                cursor.execute("""
                    SELECT DISTINCT lot_size
                    FROM tickers
                    WHERE region = ? AND lot_size IS NOT NULL
                """, (region,))

                actual_values = [row[0] for row in cursor.fetchall()]

                if actual_values and not all(v in expected_values for v in actual_values):
                    return {
                        'success': False,
                        'error': f"Invalid lot_size values for {region}: {actual_values} (expected: {expected_values})"
                    }

            return {
                'success': True,
                'region_counts': region_counts,
                'null_count': null_count,
                'total_with_lot_size': total_with_lot_size
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def status(self):
        """Check migration status"""
        logger.info("=== Migration 002 Status ===")

        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if lot_size column exists
        column_exists = self._column_exists(cursor, 'tickers', 'lot_size')

        if column_exists:
            logger.info("✅ Migration 002 applied: lot_size column exists")

            # Show statistics
            cursor.execute("""
                SELECT
                    region,
                    COUNT(*) as total,
                    COUNT(lot_size) as with_lot_size,
                    COUNT(*) - COUNT(lot_size) as null_lot_size
                FROM tickers
                GROUP BY region
                ORDER BY region
            """)

            results = cursor.fetchall()

            logger.info("\n📊 Lot_size Statistics by Region:")
            logger.info(f"{'Region':<10} {'Total':<10} {'With Lot_size':<15} {'NULL':<10}")
            logger.info("-" * 50)

            for row in results:
                logger.info(
                    f"{row['region']:<10} {row['total']:<10} "
                    f"{row['with_lot_size']:<15} {row['null_lot_size']:<10}"
                )

            # Show unique lot_size values by region
            cursor.execute("""
                SELECT
                    region,
                    lot_size,
                    COUNT(*) as count
                FROM tickers
                WHERE lot_size IS NOT NULL
                GROUP BY region, lot_size
                ORDER BY region, lot_size
            """)

            lot_size_values = cursor.fetchall()

            logger.info("\n📋 Lot_size Values by Region:")
            logger.info(f"{'Region':<10} {'Lot_size':<15} {'Count':<10}")
            logger.info("-" * 40)

            for row in lot_size_values:
                logger.info(
                    f"{row['region']:<10} {row['lot_size']:<15} {row['count']:<10}"
                )

        else:
            logger.info("❌ Migration 002 not applied: lot_size column does not exist")

        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Migration 002: Add lot_size column to tickers table'
    )
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying (safe mode)'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback migration (remove lot_size column)'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check migration status'
    )

    args = parser.parse_args()

    migration = LotSizeMigration(db_path=args.db_path)

    if args.status:
        migration.status()
    elif args.rollback:
        migration.rollback()
    else:
        migration.execute(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
