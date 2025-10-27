#!/usr/bin/env python3
"""
Migrate ticker_fundamentals data from SQLite to PostgreSQL (incremental).
Only migrates missing rows to avoid duplication.
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

def get_existing_keys_from_postgres(pg_conn):
    """Get set of (ticker, region, date, period_type) already in PostgreSQL."""
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT ticker, region, date::text, period_type
        FROM ticker_fundamentals
    """)
    existing = set(cursor.fetchall())
    cursor.close()
    return existing

def get_ticker_regions_from_postgres(pg_conn):
    """Get mapping of ticker -> region from tickers table."""
    cursor = pg_conn.cursor()
    cursor.execute("SELECT ticker, region FROM tickers")
    ticker_regions = dict(cursor.fetchall())
    cursor.close()
    return ticker_regions

def migrate_ticker_fundamentals():
    """Migrate missing ticker_fundamentals rows from SQLite to PostgreSQL."""

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
        # Get existing data from PostgreSQL
        print("📊 Checking existing data in PostgreSQL...")
        existing_keys = get_existing_keys_from_postgres(pg_conn)
        ticker_regions = get_ticker_regions_from_postgres(pg_conn)
        print(f"   Found {len(existing_keys)} existing rows in PostgreSQL")
        print(f"   Found {len(ticker_regions)} tickers in tickers table")

        # Get all data from SQLite
        print("\n📊 Reading data from SQLite...")
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute("""
            SELECT
                ticker, date, period_type, fiscal_year,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr, pcr,
                ev, ev_ebitda,
                dividend_yield, dividend_per_share,
                created_at, data_source
            FROM ticker_fundamentals
        """)
        sqlite_rows = sqlite_cursor.fetchall()
        print(f"   Found {len(sqlite_rows)} rows in SQLite")

        # Filter rows that need migration
        rows_to_migrate = []
        skipped_no_ticker = 0
        skipped_already_exists = 0

        for row in sqlite_rows:
            ticker = row[0]
            date = row[1]
            period_type = row[2]

            # Get region for this ticker
            if ticker not in ticker_regions:
                skipped_no_ticker += 1
                continue

            region = ticker_regions[ticker]

            # Check if this row already exists in PostgreSQL
            key = (ticker, region, date, period_type)
            if key in existing_keys:
                skipped_already_exists += 1
                continue

            # Prepare row for PostgreSQL
            # Note: PostgreSQL schema doesn't have fiscal_year field
            rows_to_migrate.append((
                ticker,
                region,
                date,
                period_type,
                row[4],   # shares_outstanding
                row[5],   # market_cap
                row[6],   # close_price
                row[7],   # per
                row[8],   # pbr
                row[9],   # psr
                row[10],  # pcr
                row[11],  # ev
                row[12],  # ev_ebitda
                row[13],  # dividend_yield
                row[14],  # dividend_per_share
                row[15],  # created_at
                row[16]   # data_source
            ))

        print(f"\n📊 Migration summary:")
        print(f"   Rows to migrate: {len(rows_to_migrate)}")
        print(f"   Skipped (ticker not in tickers table): {skipped_no_ticker}")
        print(f"   Skipped (already exists): {skipped_already_exists}")

        # Migrate rows in batches
        if rows_to_migrate:
            print(f"\n🚀 Migrating {len(rows_to_migrate)} rows...")
            pg_cursor = pg_conn.cursor()

            execute_values(
                pg_cursor,
                """
                INSERT INTO ticker_fundamentals (
                    ticker, region, date, period_type,
                    shares_outstanding, market_cap, close_price,
                    per, pbr, psr, pcr,
                    ev, ev_ebitda,
                    dividend_yield, dividend_per_share,
                    created_at, data_source
                ) VALUES %s
                ON CONFLICT (ticker, region, date, period_type) DO NOTHING
                """,
                rows_to_migrate,
                page_size=100
            )

            pg_conn.commit()
            pg_cursor.close()
            print(f"   ✅ Migration complete!")
        else:
            print("\n   ℹ️  No new rows to migrate")

        # Verify final counts
        print("\n📊 Final verification:")
        sqlite_cursor.execute("SELECT COUNT(*) FROM ticker_fundamentals")
        sqlite_count = sqlite_cursor.fetchone()[0]

        pg_cursor = pg_conn.cursor()
        pg_cursor.execute("SELECT COUNT(*) FROM ticker_fundamentals")
        pg_count = pg_cursor.fetchone()[0]
        pg_cursor.close()

        print(f"   SQLite total: {sqlite_count}")
        print(f"   PostgreSQL total: {pg_count}")
        print(f"   Difference: {sqlite_count - pg_count} (expected: {skipped_no_ticker})")

    except Exception as e:
        print(f"❌ Error: {e}")
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == '__main__':
    migrate_ticker_fundamentals()
