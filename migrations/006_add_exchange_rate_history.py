"""
Migration 006: Add exchange_rate_history table
For Phase 1 - Global OHLCV Filtering Implementation

Purpose:
- Store historical exchange rates for multi-currency support
- Enable currency conversion tracking and auditing
- Support TTL caching with database persistence

Author: Spock Trading System
Created: 2025-10-16
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def upgrade(db_path: str = 'data/spock_local.db'):
    """
    Add exchange_rate_history table

    Table Structure:
    - id: Primary key (auto-increment)
    - currency: Currency code (USD, HKD, CNY, JPY, VND)
    - rate: Exchange rate to KRW (float)
    - timestamp: Rate timestamp (ISO format)
    - source: Data source (BOK_API, DEFAULT, etc.)

    Indexes:
    - idx_exrate_currency_timestamp: (currency, timestamp DESC)
    - idx_exrate_timestamp: (timestamp DESC)

    Unique Constraint:
    - Unique (currency, date) - one rate per currency per day
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create exchange_rate_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT NOT NULL,
                rate REAL NOT NULL,
                timestamp TEXT NOT NULL,
                rate_date TEXT NOT NULL,
                source TEXT DEFAULT 'BOK_API',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(currency, rate_date)
            )
        """)

        # Create indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exrate_currency_timestamp
            ON exchange_rate_history(currency, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exrate_timestamp
            ON exchange_rate_history(timestamp DESC)
        """)

        # Commit changes
        conn.commit()

        logger.info("✅ Migration 006: exchange_rate_history table created")
        logger.info("   - Table: exchange_rate_history")
        logger.info("   - Indexes: idx_exrate_currency_timestamp, idx_exrate_timestamp")
        logger.info("   - Unique constraint: (currency, date)")

    except sqlite3.Error as e:
        logger.error(f"❌ Migration 006 failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


def downgrade(db_path: str = 'data/spock_local.db'):
    """
    Remove exchange_rate_history table (rollback)

    Warning:
    - This will delete all historical exchange rate data
    - Use with caution
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Drop indexes
        cursor.execute("DROP INDEX IF EXISTS idx_exrate_currency_timestamp")
        cursor.execute("DROP INDEX IF EXISTS idx_exrate_timestamp")

        # Drop table
        cursor.execute("DROP TABLE IF EXISTS exchange_rate_history")

        conn.commit()

        logger.info("✅ Migration 006: exchange_rate_history table removed")

    except sqlite3.Error as e:
        logger.error(f"❌ Migration 006 downgrade failed: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    # Run migration
    print("=" * 60)
    print("Migration 006: Add exchange_rate_history table")
    print("=" * 60)

    db_path = 'data/spock_local.db'

    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("   Please run database initialization first")
        exit(1)

    # Run upgrade
    try:
        upgrade(db_path)
        print("\n✅ Migration completed successfully!")

        # Verify table creation
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='exchange_rate_history'
        """)

        if cursor.fetchone():
            print("   Table verification: ✅ exchange_rate_history exists")

            # Check indexes
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND tbl_name='exchange_rate_history'
            """)

            indexes = cursor.fetchall()
            print(f"   Index count: {len(indexes)}")
            for idx in indexes:
                print(f"     - {idx[0]}")
        else:
            print("   Table verification: ❌ exchange_rate_history not found")

        conn.close()

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        exit(1)
