#!/usr/bin/env python3
"""
Database Migration: Add fiscal_year column to ticker_fundamentals table

Purpose:
- Enable historical fundamental data storage for backtesting
- Support queries by fiscal year (2020, 2021, 2022, 2023, 2024)
- Maintain backward compatibility (existing data: fiscal_year = NULL)

Author: Spock Trading System
Date: 2025-10-17
"""

import os
import sys
import logging
import sqlite3
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_exists(db_path: str) -> bool:
    """
    Check if fiscal_year column already exists

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if column exists, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get table schema
        cursor.execute("PRAGMA table_info(ticker_fundamentals)")
        columns = cursor.fetchall()

        # Check if fiscal_year exists
        for col in columns:
            if col[1] == 'fiscal_year':
                conn.close()
                return True

        conn.close()
        return False

    except Exception as e:
        logger.error(f"Failed to check column existence: {e}")
        return False


def add_fiscal_year_column(db_path: str) -> bool:
    """
    Add fiscal_year column to ticker_fundamentals table

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if successful, False otherwise

    Migration Steps:
    1. Check if column already exists
    2. Add fiscal_year column (INTEGER, nullable)
    3. Create index for efficient queries
    4. Verify migration success
    """
    try:
        # Step 1: Check if column exists
        if check_column_exists(db_path):
            logger.info("✅ fiscal_year column already exists, skipping migration")
            return True

        logger.info("🔄 Starting migration: Adding fiscal_year column")

        # Step 2: Add column
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        logger.info("📝 Adding fiscal_year column...")
        cursor.execute("""
            ALTER TABLE ticker_fundamentals
            ADD COLUMN fiscal_year INTEGER
        """)

        # Step 3: Create index for efficient queries
        logger.info("📊 Creating index on fiscal_year...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_fiscal_year
            ON ticker_fundamentals(fiscal_year)
        """)

        # Create composite index for common query pattern
        logger.info("📊 Creating composite index on ticker + fiscal_year...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_ticker_year
            ON ticker_fundamentals(ticker, fiscal_year)
        """)

        conn.commit()

        # Step 4: Verify migration
        cursor.execute("PRAGMA table_info(ticker_fundamentals)")
        columns = cursor.fetchall()

        fiscal_year_found = False
        for col in columns:
            if col[1] == 'fiscal_year':
                fiscal_year_found = True
                logger.info(f"✅ Verified: fiscal_year column added (Type: {col[2]})")
                break

        conn.close()

        if fiscal_year_found:
            logger.info("✅ Migration completed successfully")
            return True
        else:
            logger.error("❌ Migration failed: fiscal_year column not found after migration")
            return False

    except sqlite3.Error as e:
        logger.error(f"❌ SQLite error during migration: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def populate_fiscal_year_from_data_source(db_path: str) -> int:
    """
    Populate fiscal_year for existing data based on data_source field

    For existing data with data_source format "DART-YYYY-REPCODE",
    extract and populate fiscal_year.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Number of rows updated
    """
    try:
        logger.info("🔄 Populating fiscal_year from data_source...")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Find rows with data_source format "DART-YYYY-*"
        cursor.execute("""
            SELECT id, data_source
            FROM ticker_fundamentals
            WHERE data_source LIKE 'DART-%-%'
              AND fiscal_year IS NULL
        """)

        rows = cursor.fetchall()

        if not rows:
            logger.info("ℹ️  No rows to update (fiscal_year already populated or no DART data)")
            conn.close()
            return 0

        logger.info(f"📝 Found {len(rows)} rows to update")

        updated_count = 0
        for row_id, data_source in rows:
            # Parse data_source: "DART-2025-11012" → fiscal_year=2025
            try:
                parts = data_source.split('-')
                if len(parts) >= 2:
                    fiscal_year = int(parts[1])

                    cursor.execute("""
                        UPDATE ticker_fundamentals
                        SET fiscal_year = ?
                        WHERE id = ?
                    """, (fiscal_year, row_id))

                    updated_count += 1

            except (ValueError, IndexError) as e:
                logger.warning(f"⚠️  Failed to parse data_source '{data_source}': {e}")
                continue

        conn.commit()
        conn.close()

        logger.info(f"✅ Updated {updated_count} rows with fiscal_year")
        return updated_count

    except Exception as e:
        logger.error(f"❌ Failed to populate fiscal_year: {e}")
        return 0


def create_backup(db_path: str) -> str:
    """
    Create database backup before migration

    Args:
        db_path: Path to SQLite database file

    Returns:
        Path to backup file
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{db_path}.backup_{timestamp}"

        # Copy database file
        import shutil
        shutil.copy2(db_path, backup_path)

        logger.info(f"✅ Backup created: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        raise


def main():
    """
    Main migration execution

    Steps:
    1. Create database backup
    2. Add fiscal_year column
    3. Create indexes
    4. Populate existing data
    5. Verify migration
    """
    print("\n" + "="*70)
    print("DATABASE MIGRATION: Add fiscal_year column")
    print("Spock Trading System")
    print("="*70 + "\n")

    # Get database path
    db = SQLiteDatabaseManager()
    db_path = db.db_path

    logger.info(f"📊 Database: {db_path}")

    # Step 1: Create backup
    try:
        print("📦 Creating backup...")
        backup_path = create_backup(db_path)
        print(f"✅ Backup created: {backup_path}\n")
    except Exception as e:
        print(f"\n❌ Failed to create backup: {e}")
        print("❌ Migration aborted for safety")
        return 1

    # Step 2: Add fiscal_year column
    print("🔄 Adding fiscal_year column...")
    if not add_fiscal_year_column(db_path):
        print("\n❌ Migration failed")
        print(f"💡 Database backup available at: {backup_path}")
        return 1

    print("✅ fiscal_year column added\n")

    # Step 3: Populate existing data
    print("🔄 Populating fiscal_year for existing data...")
    updated_count = populate_fiscal_year_from_data_source(db_path)
    print(f"✅ Updated {updated_count} existing rows\n")

    # Step 4: Verify schema
    print("🔍 Verifying schema...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(ticker_fundamentals)")
    columns = cursor.fetchall()

    print("\n📋 ticker_fundamentals schema:")
    for i, col in enumerate(columns, 1):
        col_name = col[1]
        col_type = col[2]
        not_null = "NOT NULL" if col[3] else ""
        print(f"  {i:2}. {col_name:30} {col_type:15} {not_null}")

    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='ticker_fundamentals'
    """)
    indexes = cursor.fetchall()

    print("\n📊 Indexes:")
    for idx in indexes:
        print(f"  - {idx[0]}")

    conn.close()

    print("\n" + "="*70)
    print("✅ Migration completed successfully!")
    print("="*70)

    print(f"\n📝 Summary:")
    print(f"  - fiscal_year column added: ✅")
    print(f"  - Indexes created: ✅")
    print(f"  - Existing rows updated: {updated_count}")
    print(f"  - Backup location: {backup_path}")

    print("\n💡 Next Steps:")
    print("  1. Test with: python3 -c \"from modules.db_manager_sqlite import SQLiteDatabaseManager; db = SQLiteDatabaseManager(); print('fiscal_year column available:', 'fiscal_year' in str(db.get_ticker_fundamentals('005930', limit=1)))\"")
    print("  2. Collect historical data: python3 scripts/collect_historical_fundamentals.py")
    print("  3. Run backtesting: python3 modules/backtester.py\n")

    return 0


if __name__ == '__main__':
    try:
        exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user\n")
        exit(1)
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)
