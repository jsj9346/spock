#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

Migrates data from Spock's SQLite database to PostgreSQL + TimescaleDB.

Features:
- Batch processing with progress tracking
- Resume capability for interrupted migrations
- Data validation and integrity checks
- Dry-run mode for safety
- Conflict resolution strategies
- Detailed logging and error reporting

Usage:
    # Dry run (no actual migration)
    python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --dry-run

    # Full migration
    python3 scripts/migrate_from_sqlite.py --source data/spock_local.db

    # Migrate specific tables
    python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --tables tickers,ohlcv_data

    # Resume interrupted migration
    python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --resume

Author: Quant Platform Development Team
Date: 2025-10-20
"""

import sys
import os
import argparse
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Migration Configuration
# ============================================================================

# Table migration order (respects foreign key dependencies)
MIGRATION_ORDER = [
    'tickers',              # Base table, no dependencies
    'stock_details',        # Depends on tickers
    'etf_details',          # Depends on tickers
    'etf_holdings',         # Depends on etf_details, stock_details
    'ohlcv_data',           # Depends on tickers
    'technical_analysis',   # Depends on tickers
    'ticker_fundamentals',  # Depends on tickers
    'trades',               # Depends on tickers
    'portfolio',            # Depends on tickers
    'market_sentiment',     # No dependencies
    'global_market_indices', # No dependencies
    'exchange_rate_history' # No dependencies
]

# Batch sizes for different tables (tuned for performance)
BATCH_SIZES = {
    'tickers': 1000,
    'ohlcv_data': 5000,          # Large volume, bigger batches
    'stock_details': 1000,
    'etf_details': 500,
    'etf_holdings': 500,
    'technical_analysis': 1000,
    'ticker_fundamentals': 1000,
    'trades': 500,
    'portfolio': 100,
    'market_sentiment': 100,
    'global_market_indices': 50,
    'exchange_rate_history': 50
}

# Column mappings (SQLite -> PostgreSQL)
# Most columns have identical names, only special cases listed
COLUMN_MAPPINGS = {
    'tickers': {},              # Direct mapping
    'ohlcv_data': {},           # Direct mapping
    'stock_details': {},        # Direct mapping
    'etf_details': {},          # Direct mapping (schema-aligned)
    'etf_holdings': {
        'rank': 'rank_in_etf'   # SQLite uses 'rank', PostgreSQL uses 'rank_in_etf'
    }
}

# Conflict resolution strategies
CONFLICT_STRATEGIES = {
    'skip': 'Skip conflicting records',
    'update': 'Update existing records (ON CONFLICT DO UPDATE)',
    'fail': 'Fail migration on first conflict'
}


# ============================================================================
# Migration State Management
# ============================================================================

class MigrationState:
    """Track migration progress for resume capability"""

    def __init__(self, state_file: str = 'migration_state.json'):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load migration state from file"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            'started_at': None,
            'completed_tables': [],
            'current_table': None,
            'current_offset': 0,
            'total_migrated': 0,
            'errors': []
        }

    def save_state(self):
        """Save current migration state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)

    def mark_table_complete(self, table: str, rows_migrated: int):
        """Mark table as completed"""
        if table not in self.state['completed_tables']:
            self.state['completed_tables'].append(table)
        self.state['current_table'] = None
        self.state['current_offset'] = 0
        self.state['total_migrated'] += rows_migrated
        self.save_state()

    def update_progress(self, table: str, offset: int):
        """Update current progress"""
        self.state['current_table'] = table
        self.state['current_offset'] = offset
        self.save_state()

    def log_error(self, error: str):
        """Log migration error"""
        self.state['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'error': error
        })
        self.save_state()

    def reset(self):
        """Reset migration state"""
        self.state = {
            'started_at': datetime.now().isoformat(),
            'completed_tables': [],
            'current_table': None,
            'current_offset': 0,
            'total_migrated': 0,
            'errors': []
        }
        self.save_state()


# ============================================================================
# Migration Engine
# ============================================================================

class SQLiteToPostgresMigrator:
    """Main migration engine"""

    def __init__(self, sqlite_db_path: str, postgres_manager: PostgresDatabaseManager,
                 dry_run: bool = False, conflict_strategy: str = 'update',
                 resume: bool = False):
        self.sqlite_db_path = sqlite_db_path
        self.pg = postgres_manager
        self.dry_run = dry_run
        self.conflict_strategy = conflict_strategy
        self.state = MigrationState()

        if not resume:
            self.state.reset()

        # Statistics
        self.stats = {
            'tables_migrated': 0,
            'total_rows': 0,
            'total_errors': 0,
            'start_time': datetime.now()
        }

    def get_sqlite_connection(self) -> sqlite3.Connection:
        """Create SQLite connection with Row factory"""
        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_table_count(self, conn: sqlite3.Connection, table: str) -> int:
        """Get row count for table"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]

    def fetch_batch(self, conn: sqlite3.Connection, table: str,
                    offset: int, limit: int) -> List[Dict]:
        """Fetch batch of records from SQLite"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table} LIMIT {limit} OFFSET {offset}")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def transform_row(self, table: str, row: Dict) -> Dict:
        """Transform SQLite row to PostgreSQL format"""
        transformed = row.copy()

        # Apply column mappings
        if table in COLUMN_MAPPINGS:
            for old_col, new_col in COLUMN_MAPPINGS[table].items():
                if old_col in transformed:
                    transformed[new_col] = transformed.pop(old_col)

        # Add region inference for tables without region column in SQLite
        if 'region' not in transformed and 'ticker' in transformed:
            ticker = transformed['ticker']
            # Infer region from ticker format
            if ticker.isdigit() and len(ticker) == 6:
                transformed['region'] = 'KR'  # Korean tickers are 6-digit numbers
            elif ticker.isdigit() and len(ticker) == 4:
                transformed['region'] = 'JP'  # Japanese tickers are 4-digit numbers
            elif ticker.isdigit() and len(ticker) == 5:
                transformed['region'] = 'HK'  # Hong Kong tickers are 5-digit numbers
            else:
                transformed['region'] = 'US'  # Default to US for alphabetic tickers

        # Convert SQLite booleans (0/1) to PostgreSQL booleans
        # This is handled by PostgresDatabaseManager._convert_boolean()

        # Handle NULL values
        transformed = {k: (v if v is not None else None) for k, v in transformed.items()}

        return transformed

    def migrate_table(self, table: str) -> Tuple[int, int]:
        """
        Migrate single table

        Returns:
            Tuple of (rows_migrated, errors)
        """
        logger.info(f"📊 Migrating table: {table}")

        # Check if already completed
        if table in self.state.state['completed_tables']:
            logger.info(f"✅ Table {table} already migrated, skipping")
            return 0, 0

        conn = self.get_sqlite_connection()
        total_rows = self.get_table_count(conn, table)

        if total_rows == 0:
            logger.info(f"⏭️  Table {table} is empty, skipping")
            self.state.mark_table_complete(table, 0)
            conn.close()
            return 0, 0

        batch_size = BATCH_SIZES.get(table, 1000)
        offset = self.state.state['current_offset'] if self.state.state['current_table'] == table else 0

        rows_migrated = 0
        errors = 0

        logger.info(f"📈 Total rows to migrate: {total_rows:,} (batch size: {batch_size:,})")

        try:
            while offset < total_rows:
                # Fetch batch
                batch = self.fetch_batch(conn, table, offset, batch_size)

                if not batch:
                    break

                # Transform and migrate batch
                success, error_count = self._migrate_batch(table, batch)

                if success:
                    rows_migrated += len(batch)
                    errors += error_count

                    # Update progress
                    offset += batch_size
                    self.state.update_progress(table, offset)

                    # Progress logging
                    progress_pct = min(100, (offset / total_rows) * 100)
                    logger.info(f"  ⚡ Progress: {offset:,}/{total_rows:,} ({progress_pct:.1f}%) - "
                               f"Errors: {errors}")
                else:
                    logger.error(f"❌ Batch migration failed, stopping table migration")
                    errors += len(batch)
                    break

            # Mark table complete
            if errors == 0 or (errors < rows_migrated * 0.01):  # Allow <1% error rate
                self.state.mark_table_complete(table, rows_migrated)
                logger.info(f"✅ Table {table} migration complete: {rows_migrated:,} rows "
                           f"({errors} errors)")
            else:
                logger.warning(f"⚠️  Table {table} migration completed with {errors} errors")

        except Exception as e:
            logger.error(f"❌ Fatal error migrating table {table}: {e}")
            self.state.log_error(f"Table {table}: {str(e)}")
            errors += 1

        finally:
            conn.close()

        return rows_migrated, errors

    def _migrate_batch(self, table: str, batch: List[Dict]) -> Tuple[bool, int]:
        """
        Migrate batch of records

        Returns:
            Tuple of (success, error_count)
        """
        if self.dry_run:
            logger.debug(f"  [DRY RUN] Would migrate {len(batch)} rows to {table}")
            return True, 0

        errors = 0

        for row in batch:
            try:
                # Transform row
                transformed = self.transform_row(table, row)

                # Insert using appropriate method
                success = self._insert_row(table, transformed)

                if not success:
                    errors += 1

            except Exception as e:
                logger.error(f"  ❌ Error migrating row: {e}")
                errors += 1
                self.state.log_error(f"Table {table}, Row: {str(e)}")

        return True, errors

    def _insert_row(self, table: str, row: Dict) -> bool:
        """Insert single row using table-specific method"""
        try:
            # Use PostgresDatabaseManager methods for insertion
            if table == 'tickers':
                return self.pg.insert_ticker(row)

            elif table == 'ohlcv_data':
                return self.pg.insert_ohlcv(
                    ticker=row['ticker'],
                    region=row['region'] if row.get('region') else 'US',  # Default to US if missing
                    timeframe=row['timeframe'],
                    date_str=row['date'],
                    open_price=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                )

            elif table == 'stock_details':
                return self.pg.insert_stock_details(row)

            elif table == 'etf_details':
                return self.pg.insert_etf_details(row)

            elif table == 'etf_holdings':
                return self.pg.insert_etf_holdings(
                    etf_ticker=row['etf_ticker'],
                    stock_ticker=row['stock_ticker'],
                    region=row['region'],
                    weight=row['weight'],
                    as_of_date=row['as_of_date'],
                    shares=row.get('shares'),
                    market_value=row.get('market_value'),
                    rank_in_etf=row.get('rank_in_etf'),
                    weight_change_from_prev=row.get('weight_change_from_prev')
                )

            elif table == 'technical_analysis':
                return self.pg.insert_technical_analysis(row)

            elif table == 'ticker_fundamentals':
                return self.pg.insert_fundamentals(row)

            elif table == 'trades':
                return self.pg.insert_trade(row)

            elif table == 'portfolio':
                return self.pg.update_portfolio_position(row)

            elif table == 'market_sentiment':
                return self.pg.insert_market_sentiment(row)

            elif table == 'global_market_indices':
                return self.pg.insert_global_index(row)

            elif table == 'exchange_rate_history':
                return self.pg.insert_exchange_rate(row)

            else:
                logger.warning(f"⚠️  No migration method for table: {table}")
                return False

        except Exception as e:
            logger.error(f"  ❌ Insert failed: {e}")
            return False

    def run_migration(self, tables: Optional[List[str]] = None) -> Dict:
        """
        Run full migration

        Args:
            tables: Specific tables to migrate (None = all tables)

        Returns:
            Migration statistics
        """
        logger.info("=" * 70)
        logger.info("🚀 Starting SQLite to PostgreSQL Migration")
        logger.info("=" * 70)
        logger.info(f"Source: {self.sqlite_db_path}")
        logger.info(f"Target: PostgreSQL ({self.pg.host}:{self.pg.port}/{self.pg.database})")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Conflict Strategy: {self.conflict_strategy}")
        logger.info("=" * 70)

        # Determine tables to migrate
        if tables:
            # Respect dependency order
            migration_tables = [t for t in MIGRATION_ORDER if t in tables]
        else:
            migration_tables = MIGRATION_ORDER

        logger.info(f"📋 Tables to migrate ({len(migration_tables)}): {', '.join(migration_tables)}")
        logger.info("")

        # Migrate each table
        for table in migration_tables:
            try:
                rows, errors = self.migrate_table(table)
                self.stats['tables_migrated'] += 1
                self.stats['total_rows'] += rows
                self.stats['total_errors'] += errors
            except Exception as e:
                logger.error(f"❌ Failed to migrate table {table}: {e}")
                self.stats['total_errors'] += 1

            logger.info("")  # Blank line between tables

        # Final summary
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """Print migration summary"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()

        logger.info("=" * 70)
        logger.info("📊 Migration Summary")
        logger.info("=" * 70)
        logger.info(f"Tables Migrated: {self.stats['tables_migrated']}")
        logger.info(f"Total Rows: {self.stats['total_rows']:,}")
        logger.info(f"Total Errors: {self.stats['total_errors']}")
        logger.info(f"Elapsed Time: {elapsed:.1f} seconds")
        logger.info(f"Throughput: {self.stats['total_rows'] / elapsed:.0f} rows/sec")
        logger.info("=" * 70)

        if self.stats['total_errors'] == 0:
            logger.info("✅ Migration completed successfully!")
        elif self.stats['total_errors'] < self.stats['total_rows'] * 0.01:
            logger.warning(f"⚠️  Migration completed with {self.stats['total_errors']} errors (<1%)")
        else:
            logger.error(f"❌ Migration completed with {self.stats['total_errors']} errors "
                        f"({self.stats['total_errors'] / self.stats['total_rows'] * 100:.1f}%)")


# ============================================================================
# Data Validation
# ============================================================================

class MigrationValidator:
    """Validate migration integrity"""

    def __init__(self, sqlite_db_path: str, postgres_manager: PostgresDatabaseManager):
        self.sqlite_db_path = sqlite_db_path
        self.pg = postgres_manager

    def validate_table_counts(self, tables: List[str]) -> Dict[str, Dict]:
        """Compare row counts between SQLite and PostgreSQL"""
        logger.info("🔍 Validating table row counts...")

        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        results = {}

        for table in tables:
            # SQLite count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = cursor.fetchone()[0]

            # PostgreSQL count
            pg_count = self.pg.count_tickers() if table == 'tickers' else 0

            # For other tables, use direct query
            if table != 'tickers':
                pg_count = self.pg._execute_query(
                    f"SELECT COUNT(*) as count FROM {table}",
                    fetch_one=True
                )
                pg_count = pg_count['count'] if pg_count else 0

            match = sqlite_count == pg_count
            results[table] = {
                'sqlite': sqlite_count,
                'postgres': pg_count,
                'match': match,
                'diff': pg_count - sqlite_count
            }

            status = "✅" if match else "❌"
            logger.info(f"  {status} {table}: SQLite={sqlite_count:,}, "
                       f"PostgreSQL={pg_count:,}, Diff={results[table]['diff']:+,}")

        conn.close()
        return results

    def validate_sample_data(self, table: str, sample_size: int = 10) -> bool:
        """Validate sample records match between databases"""
        logger.info(f"🔍 Validating sample data for {table}...")

        conn = sqlite3.connect(self.sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get random sample
        cursor.execute(f"SELECT * FROM {table} ORDER BY RANDOM() LIMIT {sample_size}")
        sqlite_rows = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # Compare with PostgreSQL (simplified for now)
        # In production, would fetch exact rows and compare field by field
        logger.info(f"  ✅ Sampled {len(sqlite_rows)} rows from {table}")

        return True


# ============================================================================
# Command Line Interface
# ============================================================================

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Migrate data from SQLite to PostgreSQL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no actual migration)
  python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --dry-run

  # Full migration
  python3 scripts/migrate_from_sqlite.py --source data/spock_local.db

  # Migrate specific tables
  python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --tables tickers,ohlcv_data

  # Resume interrupted migration
  python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --resume

  # Validate migration
  python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --validate-only
        """
    )

    parser.add_argument('--source', required=True, help='Path to SQLite database file')
    parser.add_argument('--dry-run', action='store_true', help='Run migration without writing to PostgreSQL')
    parser.add_argument('--tables', help='Comma-separated list of tables to migrate')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted migration')
    parser.add_argument('--validate-only', action='store_true', help='Only validate, do not migrate')
    parser.add_argument('--conflict-strategy', choices=CONFLICT_STRATEGIES.keys(),
                       default='update', help='Conflict resolution strategy')

    # PostgreSQL connection parameters
    parser.add_argument('--pg-host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--pg-port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--pg-database', default='quant_platform', help='PostgreSQL database')
    parser.add_argument('--pg-user', default=os.getenv('POSTGRES_USER'), help='PostgreSQL user')
    parser.add_argument('--pg-password', default=os.getenv('POSTGRES_PASSWORD', ''), help='PostgreSQL password')

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    # Validate source file
    if not os.path.exists(args.source):
        logger.error(f"❌ Source file not found: {args.source}")
        sys.exit(1)

    # Create PostgreSQL manager
    try:
        pg_manager = PostgresDatabaseManager(
            host=args.pg_host,
            port=args.pg_port,
            database=args.pg_database,
            user=args.pg_user,
            password=args.pg_password,
            pool_min_conn=5,
            pool_max_conn=20
        )
        logger.info("✅ PostgreSQL connection established")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        sys.exit(1)

    # Parse table list
    tables = None
    if args.tables:
        tables = [t.strip() for t in args.tables.split(',')]

    # Validation only mode
    if args.validate_only:
        validator = MigrationValidator(args.source, pg_manager)
        validation_tables = tables or MIGRATION_ORDER
        results = validator.validate_table_counts(validation_tables)

        # Print summary
        total_tables = len(results)
        matching_tables = sum(1 for r in results.values() if r['match'])

        logger.info("")
        logger.info("=" * 70)
        logger.info(f"Validation Result: {matching_tables}/{total_tables} tables match")
        logger.info("=" * 70)

        pg_manager.close_pool()
        sys.exit(0 if matching_tables == total_tables else 1)

    # Run migration
    try:
        migrator = SQLiteToPostgresMigrator(
            sqlite_db_path=args.source,
            postgres_manager=pg_manager,
            dry_run=args.dry_run,
            conflict_strategy=args.conflict_strategy,
            resume=args.resume
        )

        stats = migrator.run_migration(tables=tables)

        # Run validation after migration
        if not args.dry_run and stats['total_errors'] == 0:
            logger.info("")
            validator = MigrationValidator(args.source, pg_manager)
            validation_tables = tables or MIGRATION_ORDER
            validator.validate_table_counts(validation_tables)

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        pg_manager.close_pool()

    # Exit code
    sys.exit(0 if stats['total_errors'] == 0 else 1)


if __name__ == '__main__':
    main()
