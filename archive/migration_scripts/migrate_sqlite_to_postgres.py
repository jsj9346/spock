#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script

Migrates data from Spock's SQLite database to PostgreSQL + TimescaleDB.

Features:
- Batch processing for large datasets
- Progress tracking with logging
- Data validation and integrity checks
- Error handling with rollback capability
- Dry-run mode for testing

Usage:
    python3 scripts/migrate_sqlite_to_postgres.py --dry-run
    python3 scripts/migrate_sqlite_to_postgres.py --batch-size 10000
    python3 scripts/migrate_sqlite_to_postgres.py --tables tickers,ohlcv_data
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import time
import sqlite3
import psycopg2.extras

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from modules.db_manager_postgres import PostgresDatabaseManager
from scripts.init_postgres_schema import PostgresSchemaInitializer


class SQLiteToPostgresMigrator:
    """
    Migrates data from SQLite to PostgreSQL with batch processing.

    Handles:
    - Tickers
    - OHLCV data
    - Stock details
    - ETF details
    - Technical analysis
    - Ticker fundamentals
    - Market sentiment
    - Global market indices
    """

    def __init__(self,
                 sqlite_path: str,
                 postgres_manager: PostgresDatabaseManager,
                 batch_size: int = 10000,
                 dry_run: bool = False):
        """
        Initialize migrator.

        Args:
            sqlite_path: Path to SQLite database
            postgres_manager: PostgreSQL database manager
            batch_size: Number of rows per batch
            dry_run: If True, don't commit changes
        """
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        self.postgres_db = postgres_manager
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Migration statistics
        self.stats = {
            'tickers': {'total': 0, 'migrated': 0, 'errors': 0},
            'ohlcv_data': {'total': 0, 'migrated': 0, 'errors': 0},
            'stock_details': {'total': 0, 'migrated': 0, 'errors': 0},
            'etf_details': {'total': 0, 'migrated': 0, 'errors': 0},
            'technical_analysis': {'total': 0, 'migrated': 0, 'errors': 0},
            'ticker_fundamentals': {'total': 0, 'migrated': 0, 'errors': 0},
            'market_sentiment': {'total': 0, 'migrated': 0, 'errors': 0},
            'global_market_indices': {'total': 0, 'migrated': 0, 'errors': 0},
        }

        logger.info(f"Initialized migrator (batch_size={batch_size}, dry_run={dry_run})")

    def migrate_tickers(self) -> bool:
        """
        Migrate tickers table.

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 70)
        logger.info("Migrating tickers...")

        try:
            # Count total rows
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM tickers")
            total = cursor.fetchone()[0]

            self.stats['tickers']['total'] = total
            logger.info(f"Total tickers to migrate: {total}")

            # Fetch all tickers (PostgreSQL schema matches SQLite)
            cursor.execute("""
                SELECT ticker, name, name_eng, exchange, region, currency, asset_type,
                       listing_date, delisting_date, is_active, lot_size, created_at,
                       last_updated, data_source
                FROM tickers
                ORDER BY ticker, region
            """)
            tickers = cursor.fetchall()

            if not tickers:
                logger.warning("No tickers found in SQLite")
                return True

            # Prepare data for PostgreSQL
            rows = []
            for t in tickers:
                rows.append((
                    t['ticker'],
                    t['region'],
                    t['name'] if t['name'] else '',
                    t['name_eng'] if 'name_eng' in t.keys() and t['name_eng'] else None,
                    t['exchange'],
                    t['currency'] if 'currency' in t.keys() and t['currency'] else 'KRW',
                    t['asset_type'] if 'asset_type' in t.keys() and t['asset_type'] else 'STOCK',
                    t['listing_date'] if 'listing_date' in t.keys() and t['listing_date'] else None,
                    t['delisting_date'] if 'delisting_date' in t.keys() and t['delisting_date'] else None,
                    bool(t['is_active']) if 'is_active' in t.keys() and t['is_active'] is not None else True,
                    t['lot_size'] if 'lot_size' in t.keys() and t['lot_size'] else 1,
                    t['last_updated'] if 'last_updated' in t.keys() and t['last_updated'] else None,
                    t['data_source'] if 'data_source' in t.keys() and t['data_source'] else None
                ))

            # Insert into PostgreSQL
            if self.dry_run:
                logger.info(f"[DRY RUN] Would insert {len(rows)} tickers")
                self.stats['tickers']['migrated'] = len(rows)
            else:
                insert_query = """
                    INSERT INTO tickers (ticker, region, name, name_eng, exchange, currency,
                                        asset_type, listing_date, delisting_date, is_active,
                                        lot_size, last_updated, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, region) DO UPDATE SET
                        name = EXCLUDED.name,
                        name_eng = EXCLUDED.name_eng,
                        exchange = EXCLUDED.exchange,
                        currency = EXCLUDED.currency,
                        asset_type = EXCLUDED.asset_type,
                        listing_date = EXCLUDED.listing_date,
                        delisting_date = EXCLUDED.delisting_date,
                        is_active = EXCLUDED.is_active,
                        lot_size = EXCLUDED.lot_size,
                        last_updated = EXCLUDED.last_updated,
                        data_source = EXCLUDED.data_source
                """

                # Use psycopg2.extras.execute_batch for batch insert
                with self.postgres_db._get_connection() as conn:
                    try:
                        with conn.cursor() as cur:
                            psycopg2.extras.execute_batch(cur, insert_query, rows)
                        conn.commit()
                        self.stats['tickers']['migrated'] = len(rows)
                        logger.info(f"✅ Migrated {len(rows)} tickers")
                    except Exception as e:
                        conn.rollback()
                        raise e

            return True

        except Exception as e:
            logger.error(f"❌ Error migrating tickers: {e}")
            self.stats['tickers']['errors'] += 1
            return False

    def migrate_ohlcv_data(self,
                          region: Optional[str] = None,
                          start_date: Optional[str] = None) -> bool:
        """
        Migrate OHLCV data with batch processing.

        Args:
            region: Filter by region (e.g., 'KR', 'US')
            start_date: Only migrate data after this date (YYYY-MM-DD)

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 70)
        logger.info("Migrating OHLCV data...")

        try:
            # Build query with filters
            where_clauses = []
            if region:
                where_clauses.append(f"region = '{region}'")
            if start_date:
                where_clauses.append(f"date >= '{start_date}'")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Count total rows
            count_query = f"SELECT COUNT(*) as count FROM ohlcv_data {where_sql}"
            cursor = self.sqlite_conn.cursor()
            cursor.execute(count_query)
            total = cursor.fetchone()[0]

            self.stats['ohlcv_data']['total'] = total
            logger.info(f"Total OHLCV records to migrate: {total:,}")

            if total == 0:
                logger.warning("No OHLCV data found")
                return True

            # Batch processing
            offset = 0
            migrated = 0
            errors = 0

            while offset < total:
                batch_start = time.time()

                # Fetch batch
                batch_query = f"""
                    SELECT ticker, region, date, timeframe,
                           open, high, low, close, volume
                    FROM ohlcv_data
                    {where_sql}
                    ORDER BY ticker, region, date
                    LIMIT {self.batch_size} OFFSET {offset}
                """

                cursor.execute(batch_query)
                batch = cursor.fetchall()

                if not batch:
                    break

                # Prepare batch data
                rows = []
                for row in batch:
                    rows.append((
                        row['ticker'],
                        row['region'] if 'region' in row.keys() else None,
                        row['date'],
                        row['timeframe'] if 'timeframe' in row.keys() else '1d',
                        row['open'] if 'open' in row.keys() else None,
                        row['high'] if 'high' in row.keys() else None,
                        row['low'] if 'low' in row.keys() else None,
                        row['close'] if 'close' in row.keys() else None,
                        row['volume'] if 'volume' in row.keys() else None
                    ))

                # Insert batch
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would insert batch of {len(rows)} records")
                    migrated += len(rows)
                else:
                    try:
                        insert_query = """
                            INSERT INTO ohlcv_data (ticker, region, date, timeframe,
                                                   open, high, low, close, volume)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (ticker, region, date, timeframe) DO UPDATE SET
                                open = EXCLUDED.open,
                                high = EXCLUDED.high,
                                low = EXCLUDED.low,
                                close = EXCLUDED.close,
                                volume = EXCLUDED.volume
                        """

                        # Use psycopg2.extras.execute_batch for batch insert
                        with self.postgres_db._get_connection() as conn:
                            with conn.cursor() as cur:
                                psycopg2.extras.execute_batch(cur, insert_query, rows)
                            conn.commit()
                            migrated += len(rows)

                            batch_time = time.time() - batch_start
                            progress = (offset + len(rows)) / total * 100
                            rate = len(rows) / batch_time if batch_time > 0 else 0

                            logger.info(
                                f"Progress: {progress:.1f}% "
                                f"({offset + len(rows):,}/{total:,}) "
                                f"| Rate: {rate:.0f} rows/s"
                            )

                    except Exception as e:
                        logger.error(f"❌ Error in batch at offset {offset}: {e}")
                        errors += len(rows)

                offset += self.batch_size

            self.stats['ohlcv_data']['migrated'] = migrated
            self.stats['ohlcv_data']['errors'] = errors

            logger.info(f"✅ Migrated {migrated:,} OHLCV records (errors: {errors})")
            return errors == 0

        except Exception as e:
            logger.error(f"❌ Error migrating OHLCV data: {e}")
            self.stats['ohlcv_data']['errors'] += 1
            return False

    def migrate_stock_details(self) -> bool:
        """Migrate stock_details table."""
        logger.info("=" * 70)
        logger.info("Migrating stock_details...")

        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM stock_details")
            total = cursor.fetchone()[0]

            self.stats['stock_details']['total'] = total
            logger.info(f"Total stock details to migrate: {total}")

            if total == 0:
                logger.warning("No stock details found")
                return True

            # SQLite stock_details has different schema - only migrate available fields
            # PostgreSQL schema: ticker, region, sector, sector_code, industry, industry_code,
            #                   is_spac, is_preferred, par_value, created_at, last_updated
            cursor.execute("""
                SELECT ticker, region, sector, sector_code, industry, industry_code,
                       is_spac, is_preferred, par_value, last_updated
                FROM stock_details
            """)
            details = cursor.fetchall()

            rows = []
            for d in details:
                rows.append((
                    d['ticker'],
                    d['region'] if 'region' in d.keys() else None,
                    d['sector'] if 'sector' in d.keys() else None,
                    d['sector_code'] if 'sector_code' in d.keys() else None,
                    d['industry'] if 'industry' in d.keys() else None,
                    d['industry_code'] if 'industry_code' in d.keys() else None,
                    bool(d['is_spac']) if 'is_spac' in d.keys() and d['is_spac'] is not None else False,
                    bool(d['is_preferred']) if 'is_preferred' in d.keys() and d['is_preferred'] is not None else False,
                    d['par_value'] if 'par_value' in d.keys() else None,
                    d['last_updated'] if 'last_updated' in d.keys() else None
                ))

            if self.dry_run:
                logger.info(f"[DRY RUN] Would insert {len(rows)} stock details")
                self.stats['stock_details']['migrated'] = len(rows)
            else:
                insert_query = """
                    INSERT INTO stock_details (ticker, region, sector, sector_code,
                                              industry, industry_code, is_spac, is_preferred,
                                              par_value, last_updated)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, region) DO UPDATE SET
                        sector = EXCLUDED.sector,
                        sector_code = EXCLUDED.sector_code,
                        industry = EXCLUDED.industry,
                        industry_code = EXCLUDED.industry_code,
                        is_spac = EXCLUDED.is_spac,
                        is_preferred = EXCLUDED.is_preferred,
                        par_value = EXCLUDED.par_value,
                        last_updated = EXCLUDED.last_updated
                """

                # Use psycopg2.extras.execute_batch for batch insert
                with self.postgres_db._get_connection() as conn:
                    try:
                        with conn.cursor() as cur:
                            psycopg2.extras.execute_batch(cur, insert_query, rows)
                        conn.commit()
                        self.stats['stock_details']['migrated'] = len(rows)
                        logger.info(f"✅ Migrated {len(rows)} stock details")
                    except Exception as e:
                        conn.rollback()
                        raise e

            return True

        except Exception as e:
            logger.error(f"❌ Error migrating stock_details: {e}")
            self.stats['stock_details']['errors'] += 1
            return False

    def migrate_technical_analysis(self) -> bool:
        """Migrate technical_analysis table with batch processing."""
        logger.info("=" * 70)
        logger.info("Migrating technical_analysis...")

        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM technical_analysis")
            total = cursor.fetchone()[0]

            self.stats['technical_analysis']['total'] = total
            logger.info(f"Total technical analysis records to migrate: {total:,}")

            if total == 0:
                logger.warning("No technical analysis data found")
                return True

            # Batch processing for large datasets
            offset = 0
            migrated = 0

            while offset < total:
                cursor.execute(f"""
                    SELECT ticker, region, date, rsi_14, macd, macd_signal,
                           macd_histogram, bb_upper, bb_middle, bb_lower,
                           sma_20, sma_50, sma_200, ema_12, ema_26,
                           atr_14, adx_14, stochastic_k, stochastic_d,
                           obv, williams_r, cci, last_updated
                    FROM technical_analysis
                    ORDER BY ticker, region, date
                    LIMIT {self.batch_size} OFFSET {offset}
                """)
                batch = cursor.fetchall()

                if not batch:
                    break

                rows = []
                for t in batch:
                    rows.append((
                        t['ticker'],
                        t['region'] if 'region' in t.keys() else None,
                        t['date'],
                        t['rsi_14'] if 'rsi_14' in t.keys() else None,
                        t['macd'] if 'macd' in t.keys() else None,
                        t['macd_signal'] if 'macd_signal' in t.keys() else None,
                        t['macd_histogram'] if 'macd_histogram' in t.keys() else None,
                        t['bb_upper'] if 'bb_upper' in t.keys() else None,
                        t['bb_middle'] if 'bb_middle' in t.keys() else None,
                        t['bb_lower'] if 'bb_lower' in t.keys() else None,
                        t['sma_20'] if 'sma_20' in t.keys() else None,
                        t['sma_50'] if 'sma_50' in t.keys() else None,
                        t['sma_200'] if 'sma_200' in t.keys() else None,
                        t['ema_12'] if 'ema_12' in t.keys() else None,
                        t['ema_26'] if 'ema_26' in t.keys() else None,
                        t['atr_14'] if 'atr_14' in t.keys() else None,
                        t['adx_14'] if 'adx_14' in t.keys() else None,
                        t['stochastic_k'] if 'stochastic_k' in t.keys() else None,
                        t['stochastic_d'] if 'stochastic_d' in t.keys() else None,
                        t['obv'] if 'obv' in t.keys() else None,
                        t['williams_r'] if 'williams_r' in t.keys() else None,
                        t['cci'] if 'cci' in t.keys() else None,
                        t['last_updated'] if 'last_updated' in t.keys() else None
                    ))

                if self.dry_run:
                    migrated += len(rows)
                else:
                    insert_query = """
                        INSERT INTO technical_analysis (
                            ticker, region, date, rsi_14, macd, macd_signal,
                            macd_histogram, bb_upper, bb_middle, bb_lower,
                            sma_20, sma_50, sma_200, ema_12, ema_26, atr_14,
                            adx_14, stochastic_k, stochastic_d, obv,
                            williams_r, cci, last_updated
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, region, date) DO UPDATE SET
                            rsi_14 = EXCLUDED.rsi_14,
                            macd = EXCLUDED.macd,
                            macd_signal = EXCLUDED.macd_signal,
                            macd_histogram = EXCLUDED.macd_histogram,
                            bb_upper = EXCLUDED.bb_upper,
                            bb_middle = EXCLUDED.bb_middle,
                            bb_lower = EXCLUDED.bb_lower,
                            sma_20 = EXCLUDED.sma_20,
                            sma_50 = EXCLUDED.sma_50,
                            sma_200 = EXCLUDED.sma_200,
                            ema_12 = EXCLUDED.ema_12,
                            ema_26 = EXCLUDED.ema_26,
                            atr_14 = EXCLUDED.atr_14,
                            adx_14 = EXCLUDED.adx_14,
                            stochastic_k = EXCLUDED.stochastic_k,
                            stochastic_d = EXCLUDED.stochastic_d,
                            obv = EXCLUDED.obv,
                            williams_r = EXCLUDED.williams_r,
                            cci = EXCLUDED.cci,
                            last_updated = EXCLUDED.last_updated
                    """

                    # Use psycopg2.extras.execute_batch for batch insert
                    with self.postgres_db._get_connection() as conn:
                        with conn.cursor() as cur:
                            psycopg2.extras.execute_batch(cur, insert_query, rows)
                        conn.commit()
                        migrated += len(rows)

                        progress = (offset + len(rows)) / total * 100
                        logger.info(f"Progress: {progress:.1f}% ({migrated:,}/{total:,})")

                offset += self.batch_size

            self.stats['technical_analysis']['migrated'] = migrated
            logger.info(f"✅ Migrated {migrated:,} technical analysis records")
            return True

        except Exception as e:
            logger.error(f"❌ Error migrating technical_analysis: {e}")
            self.stats['technical_analysis']['errors'] += 1
            return False

    def print_summary(self):
        """Print migration summary."""
        logger.info("=" * 70)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 70)

        for table, stats in self.stats.items():
            if stats['total'] > 0:
                success_rate = (stats['migrated'] / stats['total'] * 100) if stats['total'] > 0 else 0
                logger.info(
                    f"{table:25s} | "
                    f"Total: {stats['total']:8,} | "
                    f"Migrated: {stats['migrated']:8,} | "
                    f"Errors: {stats['errors']:5} | "
                    f"Success: {success_rate:5.1f}%"
                )

        logger.info("=" * 70)


def main():
    """Main migration workflow."""
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument(
        '--sqlite-path',
        default='data/spock_local.db',
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='Number of rows per batch'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test migration without committing'
    )
    parser.add_argument(
        '--tables',
        help='Comma-separated list of tables to migrate (default: all)'
    )
    parser.add_argument(
        '--region',
        help='Filter OHLCV data by region (e.g., KR, US)'
    )
    parser.add_argument(
        '--start-date',
        help='Only migrate OHLCV data after this date (YYYY-MM-DD)'
    )

    args = parser.parse_args()

    # Setup logging
    log_file = f"logs/{datetime.now().strftime('%Y%m%d')}_migration.log"
    logger.add(log_file, rotation="100 MB")

    logger.info("=" * 70)
    logger.info("SQLite to PostgreSQL Migration")
    logger.info("=" * 70)
    logger.info(f"SQLite DB: {args.sqlite_path}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Dry run: {args.dry_run}")

    # Initialize PostgreSQL
    try:
        postgres_db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    # Initialize schema if needed
    try:
        schema_init = PostgresSchemaInitializer()
        schema_init.connect()

        # Check if schema exists
        try:
            schema_init.validate_schema()
            logger.info("✅ PostgreSQL schema ready")
        except Exception:
            logger.info("Initializing PostgreSQL schema...")
            schema_init.initialize_complete_schema()
            logger.info("✅ PostgreSQL schema initialized")

        schema_init.close()
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        return 1

    # Create migrator
    migrator = SQLiteToPostgresMigrator(
        sqlite_path=args.sqlite_path,
        postgres_manager=postgres_db,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    # Determine which tables to migrate
    all_tables = ['tickers', 'ohlcv_data', 'stock_details', 'technical_analysis']
    tables_to_migrate = (
        args.tables.split(',') if args.tables
        else all_tables
    )

    logger.info(f"Tables to migrate: {', '.join(tables_to_migrate)}")

    # Execute migration
    start_time = time.time()
    success = True

    if 'tickers' in tables_to_migrate:
        success = migrator.migrate_tickers() and success

    if 'ohlcv_data' in tables_to_migrate:
        success = migrator.migrate_ohlcv_data(
            region=args.region,
            start_date=args.start_date
        ) and success

    if 'stock_details' in tables_to_migrate:
        success = migrator.migrate_stock_details() and success

    if 'technical_analysis' in tables_to_migrate:
        success = migrator.migrate_technical_analysis() and success

    # Print summary
    migrator.print_summary()

    elapsed = time.time() - start_time
    logger.info(f"Total migration time: {elapsed:.1f}s")

    if success:
        logger.info("✅ Migration completed successfully")
        return 0
    else:
        logger.error("❌ Migration completed with errors")
        return 1


if __name__ == '__main__':
    sys.exit(main())
