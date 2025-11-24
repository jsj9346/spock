#!/usr/bin/env python3
"""
Migrate remaining data differences from SQLite to PostgreSQL.
- stock_details (7 rows difference)
- etf_details (136 rows difference)
- ohlcv_data (261 rows difference)
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

load_dotenv()

# Database connections
SQLITE_DB = 'data/spock_local.db'
PG_HOST = os.getenv('POSTGRES_HOST', 'localhost')
PG_PORT = int(os.getenv('POSTGRES_PORT', 5432))
PG_DB = os.getenv('POSTGRES_DB', 'quant_platform')
PG_USER = os.getenv('POSTGRES_USER', '13ruce')
PG_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

def get_ticker_regions(pg_conn):
    """Get mapping of ticker -> region from tickers table."""
    cursor = pg_conn.cursor()
    cursor.execute("SELECT ticker, region FROM tickers")
    ticker_regions = dict(cursor.fetchall())
    cursor.close()
    return ticker_regions

def migrate_stock_details(sqlite_conn, pg_conn, ticker_regions):
    """Migrate missing stock_details rows."""
    print("\n" + "="*70)
    print("📊 MIGRATING STOCK_DETAILS")
    print("="*70)

    # Get existing keys from PostgreSQL
    pg_cursor = pg_conn.cursor()
    pg_cursor.execute("SELECT ticker, region FROM stock_details")
    existing_keys = set(pg_cursor.fetchall())
    print(f"   Existing in PostgreSQL: {len(existing_keys)} rows")

    # Get all data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("""
        SELECT
            ticker, sector, sector_code, industry, industry_code,
            is_spac, is_preferred, par_value,
            created_at, last_updated
        FROM stock_details
    """)
    sqlite_rows = sqlite_cursor.fetchall()
    print(f"   Total in SQLite: {len(sqlite_rows)} rows")

    # Filter rows to migrate
    rows_to_migrate = []
    skipped_no_ticker = 0
    skipped_exists = 0

    for row in sqlite_rows:
        ticker = row[0]
        if ticker not in ticker_regions:
            skipped_no_ticker += 1
            continue

        region = ticker_regions[ticker]
        key = (ticker, region)

        if key in existing_keys:
            skipped_exists += 1
            continue

        # Prepare row for PostgreSQL (convert SQLite integers to booleans, truncate codes)
        rows_to_migrate.append((
            ticker, region,
            row[1],  # sector
            row[2][:10] if row[2] else None,  # sector_code (truncate to 10 chars)
            row[3],  # industry
            row[4][:10] if row[4] else None,  # industry_code (truncate to 10 chars)
            bool(row[5]) if row[5] is not None else False,  # is_spac
            bool(row[6]) if row[6] is not None else False,  # is_preferred
            row[7],  # par_value
            row[8],  # created_at
            row[9]   # last_updated
        ))

    print(f"   To migrate: {len(rows_to_migrate)} rows")
    print(f"   Skipped (no ticker): {skipped_no_ticker}")
    print(f"   Skipped (exists): {skipped_exists}")

    if rows_to_migrate:
        execute_values(
            pg_cursor,
            """
            INSERT INTO stock_details (
                ticker, region, sector, sector_code, industry, industry_code,
                is_spac, is_preferred, par_value, created_at, last_updated
            ) VALUES %s
            ON CONFLICT (ticker, region) DO NOTHING
            """,
            rows_to_migrate,
            page_size=100
        )
        pg_conn.commit()
        print(f"   ✅ Migrated {len(rows_to_migrate)} rows")

def migrate_etf_details(sqlite_conn, pg_conn, ticker_regions):
    """Migrate missing etf_details rows."""
    print("\n" + "="*70)
    print("📊 MIGRATING ETF_DETAILS")
    print("="*70)

    # Get existing keys from PostgreSQL
    pg_cursor = pg_conn.cursor()
    pg_cursor.execute("SELECT ticker, region FROM etf_details")
    existing_keys = set(pg_cursor.fetchall())
    print(f"   Existing in PostgreSQL: {len(existing_keys)} rows")

    # Get all data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("""
        SELECT
            ticker, issuer, inception_date, underlying_asset_class,
            tracking_index, geographic_region, sector_theme, fund_type,
            aum, listed_shares, underlying_asset_count,
            expense_ratio, ter, leverage_ratio, currency_hedged,
            tracking_error_20d, tracking_error_60d,
            tracking_error_120d, tracking_error_250d,
            created_at, last_updated
        FROM etf_details
    """)
    sqlite_rows = sqlite_cursor.fetchall()
    print(f"   Total in SQLite: {len(sqlite_rows)} rows")

    # Filter rows to migrate
    rows_to_migrate = []
    skipped_no_ticker = 0
    skipped_exists = 0

    for row in sqlite_rows:
        ticker = row[0]
        if ticker not in ticker_regions:
            skipped_no_ticker += 1
            continue

        region = ticker_regions[ticker]
        key = (ticker, region)

        if key in existing_keys:
            skipped_exists += 1
            continue

        # Prepare row for PostgreSQL (convert booleans)
        rows_to_migrate.append((
            ticker, region,
            row[1],  # issuer
            row[2],  # inception_date
            row[3],  # underlying_asset_class
            row[4],  # tracking_index
            row[5],  # geographic_region
            row[6],  # sector_theme
            row[7],  # fund_type
            row[8],  # aum
            row[9],  # listed_shares
            row[10], # underlying_asset_count
            row[11], # expense_ratio
            row[12], # ter
            row[13], # leverage_ratio
            bool(row[14]) if row[14] is not None else False,  # currency_hedged
            row[15], # tracking_error_20d
            row[16], # tracking_error_60d
            row[17], # tracking_error_120d
            row[18], # tracking_error_250d
            row[19], # created_at
            row[20]  # last_updated
        ))

    print(f"   To migrate: {len(rows_to_migrate)} rows")
    print(f"   Skipped (no ticker): {skipped_no_ticker}")
    print(f"   Skipped (exists): {skipped_exists}")

    if rows_to_migrate:
        execute_values(
            pg_cursor,
            """
            INSERT INTO etf_details (
                ticker, region, issuer, inception_date, underlying_asset_class,
                tracking_index, geographic_region, sector_theme, fund_type,
                aum, listed_shares, underlying_asset_count,
                expense_ratio, ter, leverage_ratio, currency_hedged,
                tracking_error_20d, tracking_error_60d,
                tracking_error_120d, tracking_error_250d,
                created_at, last_updated
            ) VALUES %s
            ON CONFLICT (ticker, region) DO NOTHING
            """,
            rows_to_migrate,
            page_size=100
        )
        pg_conn.commit()
        print(f"   ✅ Migrated {len(rows_to_migrate)} rows")

def migrate_ohlcv_data(sqlite_conn, pg_conn, ticker_regions):
    """Migrate missing ohlcv_data rows."""
    print("\n" + "="*70)
    print("📊 MIGRATING OHLCV_DATA")
    print("="*70)

    # Get existing keys from PostgreSQL (sample check - full check would be too slow)
    pg_cursor = pg_conn.cursor()
    pg_cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
    existing_count = pg_cursor.fetchone()[0]
    print(f"   Existing in PostgreSQL: {existing_count:,} rows")

    # Get all data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
    sqlite_count = sqlite_cursor.fetchone()[0]
    print(f"   Total in SQLite: {sqlite_count:,} rows")

    # For ohlcv_data, we'll use a different approach - find date ranges
    # Get the latest date for each ticker in PostgreSQL
    pg_cursor.execute("""
        SELECT ticker, region, MAX(date) as max_date
        FROM ohlcv_data
        GROUP BY ticker, region
    """)
    latest_dates = {(row[0], row[1]): row[2] for row in pg_cursor.fetchall()}

    # Get data from SQLite that's after the latest date in PostgreSQL
    sqlite_cursor.execute("""
        SELECT
            ticker, date, timeframe, open, high, low, close, volume,
            created_at
        FROM ohlcv_data
        ORDER BY ticker, date
    """)

    rows_to_migrate = []
    skipped_no_ticker = 0
    skipped_old_date = 0
    processed = 0

    print(f"   Processing rows...")
    for row in sqlite_cursor:
        processed += 1
        if processed % 100000 == 0:
            print(f"      Processed: {processed:,} rows")

        ticker = row[0]
        date = row[1]

        if ticker not in ticker_regions:
            skipped_no_ticker += 1
            continue

        region = ticker_regions[ticker]
        key = (ticker, region)

        # Skip if we already have data up to or past this date
        if key in latest_dates and date <= str(latest_dates[key]):
            skipped_old_date += 1
            continue

        # Prepare row for PostgreSQL
        rows_to_migrate.append((
            ticker, region, date,
            row[2],  # timeframe
            row[3],  # open
            row[4],  # high
            row[5],  # low
            row[6],  # close
            row[7]   # volume
        ))

    print(f"   To migrate: {len(rows_to_migrate)} rows")
    print(f"   Skipped (no ticker): {skipped_no_ticker}")
    print(f"   Skipped (old date): {skipped_old_date}")

    if rows_to_migrate:
        print(f"   🚀 Migrating in batches of 5000...")
        batch_size = 5000
        for i in range(0, len(rows_to_migrate), batch_size):
            batch = rows_to_migrate[i:i+batch_size]
            execute_values(
                pg_cursor,
                """
                INSERT INTO ohlcv_data (
                    ticker, region, date, timeframe, open, high, low,
                    close, volume
                ) VALUES %s
                ON CONFLICT (ticker, region, date, timeframe) DO NOTHING
                """,
                batch,
                page_size=1000
            )
            if (i + batch_size) % 10000 == 0:
                print(f"      Migrated: {i+batch_size:,} / {len(rows_to_migrate):,}")

        pg_conn.commit()
        print(f"   ✅ Migrated {len(rows_to_migrate)} rows")

def main():
    """Main migration function."""
    print("\n" + "="*70)
    print("🚀 INCREMENTAL DATA MIGRATION: SQLite → PostgreSQL")
    print("="*70)

    # Connect to databases
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    pg_conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )

    try:
        # Get ticker regions mapping
        print("\n📊 Loading ticker regions mapping...")
        ticker_regions = get_ticker_regions(pg_conn)
        print(f"   Found {len(ticker_regions)} tickers in PostgreSQL")

        # Migrate each table
        migrate_stock_details(sqlite_conn, pg_conn, ticker_regions)
        migrate_etf_details(sqlite_conn, pg_conn, ticker_regions)
        migrate_ohlcv_data(sqlite_conn, pg_conn, ticker_regions)

        print("\n" + "="*70)
        print("✅ MIGRATION COMPLETE!")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == '__main__':
    main()
