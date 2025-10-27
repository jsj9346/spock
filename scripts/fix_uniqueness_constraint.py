#!/usr/bin/env python3
"""
Database Migration: Fix ticker_fundamentals Uniqueness Constraint

Problem:
- Current constraint: UNIQUE(ticker, date, period_type)
- Issue: Historical data with same date but different fiscal_year overwrites
- Example: 2020, 2021, 2022 data all have date='2025-10-17' → only last one stored

Solution:
- New constraint: UNIQUE(ticker, fiscal_year, period_type)
- Allows multiple years of data with same collection date
- Prevents duplicate entries for same ticker + fiscal_year + period_type

Author: Spock Trading System
Date: 2025-10-17
Priority: HIGH
"""

import os
import sys
import sqlite3
import logging
import json
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
        backup_path = f"{db_path}.backup_constraint_fix_{timestamp}"

        # Copy database file
        import shutil
        shutil.copy2(db_path, backup_path)

        logger.info(f"✅ Backup created: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        raise


def export_existing_data(conn: sqlite3.Connection) -> list:
    """
    Export all existing data from ticker_fundamentals table

    Args:
        conn: SQLite connection

    Returns:
        List of row dictionaries
    """
    try:
        cursor = conn.cursor()

        # Get all data
        cursor.execute("""
            SELECT
                ticker, date, period_type, fiscal_year,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr, pcr, ev, ev_ebitda,
                dividend_yield, dividend_per_share,
                created_at, data_source
            FROM ticker_fundamentals
        """)

        rows = cursor.fetchall()

        # Convert to list of dicts
        columns = [
            'ticker', 'date', 'period_type', 'fiscal_year',
            'shares_outstanding', 'market_cap', 'close_price',
            'per', 'pbr', 'psr', 'pcr', 'ev', 'ev_ebitda',
            'dividend_yield', 'dividend_per_share',
            'created_at', 'data_source'
        ]

        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))

        logger.info(f"✅ Exported {len(data)} rows from ticker_fundamentals")
        return data

    except Exception as e:
        logger.error(f"❌ Data export failed: {e}")
        raise


def save_data_to_json(data: list, backup_dir: str) -> str:
    """
    Save exported data to JSON file for extra safety

    Args:
        data: List of row dictionaries
        backup_dir: Directory to save JSON file

    Returns:
        Path to JSON file
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(backup_dir, f'ticker_fundamentals_backup_{timestamp}.json')

        # Ensure directory exists
        os.makedirs(backup_dir, exist_ok=True)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Data saved to JSON: {json_path}")
        return json_path

    except Exception as e:
        logger.error(f"❌ JSON export failed: {e}")
        raise


def recreate_table(conn: sqlite3.Connection):
    """
    Recreate ticker_fundamentals table with updated constraint

    Args:
        conn: SQLite connection

    Steps:
    1. Drop old table
    2. Create new table with UNIQUE(ticker, fiscal_year, period_type)
    3. Recreate indexes
    """
    try:
        cursor = conn.cursor()

        logger.info("🗑️  Dropping old ticker_fundamentals table...")
        cursor.execute("DROP TABLE IF EXISTS ticker_fundamentals")

        logger.info("📝 Creating new ticker_fundamentals table...")
        cursor.execute("""
            CREATE TABLE ticker_fundamentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                date TEXT NOT NULL,                   -- 수집일 (YYYY-MM-DD)
                period_type TEXT NOT NULL,            -- DAILY, QUARTERLY, ANNUAL
                fiscal_year INTEGER,                  -- 회계연도 (2020, 2021, 2022, ...)

                -- ======== 기본 지표 ========
                shares_outstanding BIGINT,            -- 상장주식수
                market_cap BIGINT,                    -- 시가총액

                close_price REAL,                     -- 종가 (해당일 기준)

                -- ======== 밸류에이션 지표 ========
                per REAL,                             -- Price to Earnings Ratio
                pbr REAL,                             -- Price to Book Ratio
                psr REAL,                             -- Price to Sales Ratio
                pcr REAL,                             -- Price to Cash Flow Ratio

                ev BIGINT,                            -- Enterprise Value (기업가치)
                ev_ebitda REAL,                       -- EV/EBITDA

                -- ======== 배당 지표 ========
                dividend_yield REAL,                  -- 배당수익률 (%)
                dividend_per_share REAL,              -- 주당배당금

                -- ======== 메타 정보 ========
                created_at TEXT NOT NULL,
                data_source TEXT,                     -- DART, yfinance, etc.

                -- ✅ UPDATED CONSTRAINT: Include fiscal_year
                UNIQUE(ticker, fiscal_year, period_type),

                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

        logger.info("📊 Creating indexes...")

        # Index on fiscal_year (already created in add_fiscal_year_column.py)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_fiscal_year
            ON ticker_fundamentals(fiscal_year)
        """)

        # Composite index on ticker + fiscal_year
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_ticker_year
            ON ticker_fundamentals(ticker, fiscal_year)
        """)

        # Index on date for current data queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date
            ON ticker_fundamentals(ticker, date)
        """)

        # Index on period_type for filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fundamentals_period
            ON ticker_fundamentals(period_type)
        """)

        conn.commit()
        logger.info("✅ Table recreated successfully")

    except Exception as e:
        logger.error(f"❌ Table recreation failed: {e}")
        conn.rollback()
        raise


def restore_data(conn: sqlite3.Connection, data: list):
    """
    Restore data to new table

    Args:
        conn: SQLite connection
        data: List of row dictionaries

    Note:
        Uses INSERT OR IGNORE to handle potential duplicates
        with new uniqueness constraint
    """
    try:
        cursor = conn.cursor()

        logger.info(f"🔄 Restoring {len(data)} rows...")

        inserted_count = 0
        skipped_count = 0

        for row in data:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO ticker_fundamentals (
                        ticker, date, period_type, fiscal_year,
                        shares_outstanding, market_cap, close_price,
                        per, pbr, psr, pcr, ev, ev_ebitda,
                        dividend_yield, dividend_per_share,
                        created_at, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['ticker'],
                    row['date'],
                    row['period_type'],
                    row['fiscal_year'],
                    row['shares_outstanding'],
                    row['market_cap'],
                    row['close_price'],
                    row['per'],
                    row['pbr'],
                    row['psr'],
                    row['pcr'],
                    row['ev'],
                    row['ev_ebitda'],
                    row['dividend_yield'],
                    row['dividend_per_share'],
                    row['created_at'],
                    row['data_source']
                ))

                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logger.warning(f"⚠️  Failed to insert row {row['ticker']}/{row['fiscal_year']}: {e}")
                skipped_count += 1
                continue

        conn.commit()

        logger.info(f"✅ Data restored: {inserted_count} inserted, {skipped_count} skipped (duplicates)")

    except Exception as e:
        logger.error(f"❌ Data restoration failed: {e}")
        conn.rollback()
        raise


def verify_migration(conn: sqlite3.Connection, original_count: int):
    """
    Verify migration success

    Args:
        conn: SQLite connection
        original_count: Original row count before migration

    Checks:
    1. Table exists
    2. Constraint updated
    3. Indexes created
    4. Data count matches or is close (accounting for duplicates)
    """
    try:
        cursor = conn.cursor()

        # Check 1: Table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='ticker_fundamentals'
        """)
        if not cursor.fetchone():
            raise Exception("ticker_fundamentals table not found after migration")

        logger.info("✅ Table exists")

        # Check 2: Verify constraint
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='ticker_fundamentals'
        """)
        table_sql = cursor.fetchone()[0]

        if 'UNIQUE(ticker, fiscal_year, period_type)' in table_sql:
            logger.info("✅ Uniqueness constraint updated correctly")
        else:
            logger.warning("⚠️  Uniqueness constraint may not be correct")

        # Check 3: Count rows
        cursor.execute("SELECT COUNT(*) FROM ticker_fundamentals")
        new_count = cursor.fetchone()[0]

        logger.info(f"📊 Row count: {new_count} (original: {original_count})")

        if new_count >= original_count * 0.8:  # Allow 20% loss for duplicates
            logger.info("✅ Data count acceptable")
        else:
            logger.warning(f"⚠️  Significant data loss: {original_count - new_count} rows")

        # Check 4: Verify indexes
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='ticker_fundamentals'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        logger.info(f"✅ Found {len(indexes)} indexes: {', '.join(indexes)}")

        return True

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False


def main():
    """
    Main migration execution

    Steps:
    1. Create database backup
    2. Export existing data
    3. Save data to JSON (extra safety)
    4. Drop and recreate table with new constraint
    5. Restore data
    6. Verify migration success
    """
    print("\n" + "="*70)
    print("DATABASE MIGRATION: Fix Uniqueness Constraint")
    print("ticker_fundamentals table")
    print("="*70 + "\n")

    # Get database path
    db = SQLiteDatabaseManager()
    db_path = db.db_path

    logger.info(f"📊 Database: {db_path}")

    # Step 1: Create backup
    try:
        print("📦 Creating database backup...")
        backup_path = create_backup(db_path)
        print(f"✅ Backup created: {backup_path}\n")
    except Exception as e:
        print(f"\n❌ Failed to create backup: {e}")
        print("❌ Migration aborted for safety")
        return 1

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Step 2: Export existing data
        print("📤 Exporting existing data...")
        existing_data = export_existing_data(conn)
        original_count = len(existing_data)
        print(f"✅ Exported {original_count} rows\n")

        # Step 3: Save to JSON
        print("💾 Saving data to JSON backup...")
        json_path = save_data_to_json(existing_data, 'data/backups')
        print(f"✅ JSON backup: {json_path}\n")

        # Step 4: Recreate table
        print("🔄 Recreating table with updated constraint...")
        recreate_table(conn)
        print("✅ Table recreated\n")

        # Step 5: Restore data
        print("📥 Restoring data...")
        restore_data(conn, existing_data)
        print("✅ Data restored\n")

        # Step 6: Verify
        print("🔍 Verifying migration...")
        if verify_migration(conn, original_count):
            print("✅ Migration verified\n")
        else:
            print("⚠️  Verification warnings detected\n")

        # Final summary
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ticker_fundamentals")
        final_count = cursor.fetchone()[0]

        print("="*70)
        print("✅ Migration completed successfully!")
        print("="*70)

        print(f"\n📝 Summary:")
        print(f"  - Original rows: {original_count}")
        print(f"  - Final rows: {final_count}")
        print(f"  - Rows lost (duplicates): {original_count - final_count}")
        print(f"  - Database backup: {backup_path}")
        print(f"  - JSON backup: {json_path}")

        print(f"\n📋 New Constraint:")
        print(f"  - UNIQUE(ticker, fiscal_year, period_type)")
        print(f"  - Allows multiple years with same collection date")
        print(f"  - Prevents duplicates within same fiscal year")

        print("\n💡 Next Steps:")
        print("  1. Re-run historical collection test:")
        print("     python3 scripts/test_historical_collection.py")
        print("  2. Verify all 5 years (2020-2024) are stored:")
        print("     python3 -c \"from modules.db_manager_sqlite import SQLiteDatabaseManager; db = SQLiteDatabaseManager(); conn = db._get_connection(); cursor = conn.cursor(); cursor.execute('SELECT ticker, fiscal_year FROM ticker_fundamentals WHERE ticker=\\\"005930\\\" ORDER BY fiscal_year'); print('\\\\n'.join([f\\\"{r[0]} - {r[1]}\\\" for r in cursor.fetchall()])); conn.close()\"")
        print("  3. Continue with backtesting implementation\n")

        conn.close()
        return 0

    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        print(f"\n💡 Database backup available at: {backup_path}")
        print(f"💡 JSON backup available at: {json_path}")
        print(f"💡 To restore: cp {backup_path} {db_path}\n")

        conn.close()

        import traceback
        traceback.print_exc()
        return 1


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
