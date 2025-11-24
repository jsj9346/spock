"""
ETF Holdings Schema Migration Script

Phase 1 Implementation: ETF-Stock relationship database schema migration

Creates:
- etfs: ETF metadata table
- etf_holdings: ETF-stock Many-to-Many relationship table with weights
- Indexes: 4 strategic indexes for optimized queries

Usage:
    python scripts/migrate_etf_holdings_schema.py
    python scripts/migrate_etf_holdings_schema.py --db-path data/spock_local.db
    python scripts/migrate_etf_holdings_schema.py --dry-run
    python scripts/migrate_etf_holdings_schema.py --verify-only

Author: Spock Trading System
Date: 2025-10-17
"""

import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ETFHoldingsSchemaMigration:
    """ETF Holdings schema migration manager"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"Database not found: {db_path}\n"
                f"Please run: python init_db.py"
            )

    def migrate(self, dry_run: bool = False) -> bool:
        """
        Execute ETF holdings schema migration

        Args:
            dry_run: If True, only validate without applying changes

        Returns:
            True if successful
        """
        logger.info("=" * 70)
        logger.info("ETF Holdings Schema Migration - Phase 1")
        logger.info("=" * 70)

        if dry_run:
            logger.info("🔍 DRY RUN MODE: No changes will be applied")

        # Step 1: Validate prerequisites
        logger.info("\n[Step 1/5] Validating prerequisites...")
        if not self._validate_prerequisites():
            logger.error("❌ Prerequisites validation failed")
            return False
        logger.info("✅ Prerequisites validated")

        if dry_run:
            logger.info("\n✅ DRY RUN COMPLETE: Schema migration would succeed")
            return True

        # Step 2: Create etfs table
        logger.info("\n[Step 2/5] Creating etfs table...")
        if not self._create_etfs_table():
            logger.error("❌ Failed to create etfs table")
            return False
        logger.info("✅ etfs table created")

        # Step 3: Create etf_holdings table
        logger.info("\n[Step 3/5] Creating etf_holdings table...")
        if not self._create_etf_holdings_table():
            logger.error("❌ Failed to create etf_holdings table")
            return False
        logger.info("✅ etf_holdings table created")

        # Step 4: Create indexes
        logger.info("\n[Step 4/5] Creating indexes for performance optimization...")
        if not self._create_indexes():
            logger.error("❌ Failed to create indexes")
            return False
        logger.info("✅ Indexes created")

        # Step 5: Verify schema
        logger.info("\n[Step 5/5] Verifying schema...")
        if not self._verify_schema():
            logger.error("❌ Schema verification failed")
            return False
        logger.info("✅ Schema verified")

        logger.info("\n" + "=" * 70)
        logger.info("✅ ETF Holdings Schema Migration COMPLETE")
        logger.info("=" * 70)

        return True

    def _validate_prerequisites(self) -> bool:
        """Validate database prerequisites"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check if tickers table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='tickers'
            """)
            if not cursor.fetchone():
                logger.error("❌ tickers table not found")
                return False

            # Check if asset_type column exists in tickers
            cursor.execute("PRAGMA table_info(tickers)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'asset_type' not in columns:
                logger.error("❌ tickers.asset_type column not found")
                return False

            # Check if etfs/etf_holdings already exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('etfs', 'etf_holdings')
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]

            if existing_tables:
                logger.warning(f"⚠️  Tables already exist: {', '.join(existing_tables)}")
                logger.warning("⚠️  Migration will skip existing tables (IF NOT EXISTS)")

            logger.info(f"✓ Database file: {self.db_path}")
            logger.info(f"✓ Database size: {os.path.getsize(self.db_path) / (1024*1024):.2f} MB")
            logger.info(f"✓ tickers table: EXISTS")
            logger.info(f"✓ asset_type column: EXISTS")

            return True

        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            return False
        finally:
            conn.close()

    def _create_etfs_table(self) -> bool:
        """Create etfs table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS etfs (
                    -- ========================================
                    -- Primary Key
                    -- ========================================
                    ticker TEXT PRIMARY KEY,                    -- ETF ticker (tickers.ticker FK)

                    -- ========================================
                    -- Basic Information
                    -- ========================================
                    name TEXT NOT NULL,                         -- ETF name (Korean)
                    name_eng TEXT,                              -- ETF name (English)
                    region TEXT NOT NULL,                       -- Market region (KR, US, CN, HK, JP, VN)
                    exchange TEXT,                              -- Exchange (KOSPI, NYSE, etc.)

                    -- ========================================
                    -- ETF Classification
                    -- ========================================
                    category TEXT,                              -- ETF category (INDEX, SECTOR, THEME, LEVERAGED, INVERSE)
                    subcategory TEXT,                           -- Subcategory (IT, 반도체, ESG, etc.)
                    tracking_index TEXT,                        -- Tracking index (KOSPI 200, S&P 500, etc.)

                    -- ========================================
                    -- Financial Information
                    -- ========================================
                    total_assets REAL,                          -- AUM (Assets Under Management, in KRW)
                    expense_ratio REAL,                         -- Total expense ratio (%)
                    listed_shares INTEGER,                      -- Number of listed shares

                    -- ========================================
                    -- Issuer Information
                    -- ========================================
                    issuer TEXT,                                -- Fund manager (삼성자산운용, BlackRock, etc.)
                    inception_date TEXT,                        -- Inception date (YYYY-MM-DD)

                    -- ========================================
                    -- Investment Strategy
                    -- ========================================
                    leverage_ratio REAL,                        -- Leverage ratio (1.0=normal, 2.0=2x, etc.)
                    is_inverse BOOLEAN DEFAULT 0,               -- Inverse ETF flag
                    currency_hedged BOOLEAN DEFAULT 0,          -- Currency hedged flag

                    -- ========================================
                    -- Performance Metrics
                    -- ========================================
                    tracking_error_20d REAL,                    -- 20-day tracking error (%)
                    tracking_error_60d REAL,                    -- 60-day tracking error (%)
                    tracking_error_120d REAL,                   -- 120-day tracking error (%)
                    tracking_error_250d REAL,                   -- 250-day tracking error (%)
                    premium_discount REAL,                      -- Premium/discount rate (market price vs NAV, %)

                    -- ========================================
                    -- Trading Information
                    -- ========================================
                    avg_daily_volume REAL,                      -- Average daily volume (recent 20 days)
                    avg_daily_value REAL,                       -- Average daily trading value (recent 20 days, in KRW)

                    -- ========================================
                    -- Metadata
                    -- ========================================
                    created_at TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    data_source TEXT,                           -- Data source (KIS_API, etfcheck.co.kr, etc.)

                    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
                )
            """)

            conn.commit()
            logger.info("  ✓ etfs table schema created")

            # Verify table creation
            cursor.execute("PRAGMA table_info(etfs)")
            columns = cursor.fetchall()
            logger.info(f"  ✓ etfs table columns: {len(columns)}")

            return True

        except Exception as e:
            logger.error(f"❌ Create etfs table error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _create_etf_holdings_table(self) -> bool:
        """Create etf_holdings table (Many-to-Many relationship)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS etf_holdings (
                    -- ========================================
                    -- Primary Key
                    -- ========================================
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- ========================================
                    -- Relationship Definition
                    -- ========================================
                    etf_ticker TEXT NOT NULL,                   -- ETF ticker (etfs.ticker FK)
                    stock_ticker TEXT NOT NULL,                 -- Stock ticker (tickers.ticker FK)

                    -- ========================================
                    -- Composition Information
                    -- ========================================
                    weight REAL NOT NULL,                       -- Weight in ETF (%)
                    shares INTEGER,                             -- Number of shares held
                    market_value REAL,                          -- Market value (shares × price, in KRW)

                    -- ========================================
                    -- Ranking and Changes
                    -- ========================================
                    rank_in_etf INTEGER,                        -- Rank within ETF by weight
                    weight_change_from_prev REAL,              -- Weight change from previous period (percentage points)

                    -- ========================================
                    -- Time-Series Tracking
                    -- ========================================
                    as_of_date TEXT NOT NULL,                   -- Reference date (YYYY-MM-DD)

                    -- ========================================
                    -- Metadata
                    -- ========================================
                    created_at TEXT NOT NULL,
                    data_source TEXT,                           -- Data source

                    -- ========================================
                    -- Foreign Keys
                    -- ========================================
                    FOREIGN KEY (etf_ticker) REFERENCES etfs(ticker) ON DELETE CASCADE,
                    FOREIGN KEY (stock_ticker) REFERENCES tickers(ticker) ON DELETE CASCADE,

                    -- ========================================
                    -- Constraints
                    -- ========================================
                    UNIQUE(etf_ticker, stock_ticker, as_of_date)  -- Prevent duplicates per date
                )
            """)

            conn.commit()
            logger.info("  ✓ etf_holdings table schema created")

            # Verify table creation
            cursor.execute("PRAGMA table_info(etf_holdings)")
            columns = cursor.fetchall()
            logger.info(f"  ✓ etf_holdings table columns: {len(columns)}")

            return True

        except Exception as e:
            logger.error(f"❌ Create etf_holdings table error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _create_indexes(self) -> bool:
        """Create strategic indexes for query optimization"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        indexes = [
            # etfs table indexes
            (
                "CREATE INDEX IF NOT EXISTS idx_etfs_region ON etfs(region)",
                "etfs region index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_etfs_category ON etfs(category)",
                "etfs category index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_etfs_issuer ON etfs(issuer)",
                "etfs issuer index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_etfs_total_assets ON etfs(total_assets DESC)",
                "etfs total_assets index (DESC)"
            ),

            # etf_holdings table indexes (strategic indexes for query optimization)
            (
                "CREATE INDEX IF NOT EXISTS idx_holdings_stock_date_weight "
                "ON etf_holdings(stock_ticker, as_of_date DESC, weight DESC)",
                "holdings stock→ETF query index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_holdings_etf_date_weight "
                "ON etf_holdings(etf_ticker, as_of_date DESC, weight DESC)",
                "holdings ETF→stock query index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_holdings_date "
                "ON etf_holdings(as_of_date DESC)",
                "holdings date index"
            ),
            (
                "CREATE INDEX IF NOT EXISTS idx_holdings_weight "
                "ON etf_holdings(weight DESC)",
                "holdings weight index (high-weight filter)"
            ),
        ]

        try:
            for idx_sql, idx_desc in indexes:
                cursor.execute(idx_sql)
                logger.info(f"  ✓ Created: {idx_desc}")

            conn.commit()
            logger.info(f"  ✓ Total indexes created: {len(indexes)}")

            return True

        except Exception as e:
            logger.error(f"❌ Create indexes error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def _verify_schema(self) -> bool:
        """Verify schema migration success"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('etfs', 'etf_holdings')
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

            if 'etfs' not in tables:
                logger.error("❌ etfs table not found")
                return False
            if 'etf_holdings' not in tables:
                logger.error("❌ etf_holdings table not found")
                return False

            # Check indexes exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name LIKE 'idx_%etfs%' OR name LIKE 'idx_holdings%'
                ORDER BY name
            """)
            indexes = [row[0] for row in cursor.fetchall()]

            expected_indexes = [
                'idx_etfs_category',
                'idx_etfs_issuer',
                'idx_etfs_region',
                'idx_etfs_total_assets',
                'idx_holdings_date',
                'idx_holdings_etf_date_weight',
                'idx_holdings_stock_date_weight',
                'idx_holdings_weight',
            ]

            missing_indexes = set(expected_indexes) - set(indexes)
            if missing_indexes:
                logger.warning(f"⚠️  Missing indexes: {missing_indexes}")

            # Verify foreign key constraints
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            if fk_status != 1:
                logger.warning("⚠️  Foreign key constraints are DISABLED")

            logger.info("\n📊 Schema Verification Summary:")
            logger.info(f"  ✓ etfs table: EXISTS")
            logger.info(f"  ✓ etf_holdings table: EXISTS")
            logger.info(f"  ✓ Indexes: {len(indexes)}/{len(expected_indexes)}")
            logger.info(f"  ✓ Foreign keys: {'ENABLED' if fk_status else 'DISABLED'}")

            return True

        except Exception as e:
            logger.error(f"❌ Schema verification error: {e}")
            return False
        finally:
            conn.close()

    def get_schema_info(self) -> Dict:
        """Get detailed schema information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        info = {
            'db_path': self.db_path,
            'db_size_mb': os.path.getsize(self.db_path) / (1024 * 1024),
            'tables': {},
            'indexes': []
        }

        try:
            # Get table info
            for table_name in ['etfs', 'etf_holdings']:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                info['tables'][table_name] = {
                    'row_count': row_count,
                    'column_count': len(columns),
                    'columns': [col[1] for col in columns]
                }

            # Get index info
            cursor.execute("""
                SELECT name, tbl_name FROM sqlite_master
                WHERE type='index' AND (name LIKE 'idx_%etfs%' OR name LIKE 'idx_holdings%')
                ORDER BY name
            """)
            info['indexes'] = [{'name': row[0], 'table': row[1]} for row in cursor.fetchall()]

            return info

        finally:
            conn.close()

    def print_schema_summary(self):
        """Print detailed schema summary"""
        info = self.get_schema_info()

        logger.info("\n" + "=" * 70)
        logger.info("ETF Holdings Schema Summary")
        logger.info("=" * 70)
        logger.info(f"Database: {info['db_path']}")
        logger.info(f"Size: {info['db_size_mb']:.2f} MB")

        logger.info("\n📋 Tables:")
        for table_name, table_info in info['tables'].items():
            logger.info(f"\n  {table_name}:")
            logger.info(f"    Rows: {table_info['row_count']:,}")
            logger.info(f"    Columns: {table_info['column_count']}")
            logger.info(f"    Fields: {', '.join(table_info['columns'][:10])}")
            if len(table_info['columns']) > 10:
                logger.info(f"            ... and {len(table_info['columns']) - 10} more")

        logger.info("\n🔍 Indexes:")
        for idx in info['indexes']:
            logger.info(f"  - {idx['name']} (on {idx['table']})")

        logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='ETF Holdings Schema Migration - Phase 1',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run migration
  python scripts/migrate_etf_holdings_schema.py

  # Dry run (validation only)
  python scripts/migrate_etf_holdings_schema.py --dry-run

  # Verify existing schema
  python scripts/migrate_etf_holdings_schema.py --verify-only

  # Custom database path
  python scripts/migrate_etf_holdings_schema.py --db-path data/custom.db
        """
    )
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path (default: data/spock_local.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate prerequisites without applying changes'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Verify existing schema without migration'
    )

    args = parser.parse_args()

    try:
        migrator = ETFHoldingsSchemaMigration(db_path=args.db_path)

        if args.verify_only:
            logger.info("Verifying existing schema...")
            if migrator._verify_schema():
                migrator.print_schema_summary()
                logger.info("\n✅ Schema verification PASSED")
            else:
                logger.error("\n❌ Schema verification FAILED")
                sys.exit(1)
        else:
            success = migrator.migrate(dry_run=args.dry_run)

            if success:
                if not args.dry_run:
                    migrator.print_schema_summary()
                logger.info("\n✅ Migration completed successfully")
                sys.exit(0)
            else:
                logger.error("\n❌ Migration FAILED")
                sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
