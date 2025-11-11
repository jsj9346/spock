"""
Setup test database with sample OHLCV data.

Automated database initialization for integration testing:
1. Connect to PostgreSQL
2. Drop and recreate test database
3. Enable TimescaleDB extension
4. Load schema from init_postgres_schema.sql
5. Insert test tickers
6. Load OHLCV data from CSV fixtures

Usage:
    python tests/fixtures/setup_test_database.py

    # Optional: Skip database recreation (faster for re-runs)
    python tests/fixtures/setup_test_database.py --skip-recreate
"""
import asyncio
import asyncpg
import pandas as pd
import subprocess
import sys
from pathlib import Path


async def setup_test_database(skip_recreate=False):
    """Initialize test database with sample data."""
    print("🚀 Starting test database setup...")

    # Database configuration
    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'user': '13ruce',
        'database': 'quant_platform_test'
    }

    # Recreate database (unless --skip-recreate)
    if not skip_recreate:
        print("\n📦 Step 1: Recreating test database...")
        try:
            # Connect to postgres database to drop/create
            conn = await asyncpg.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                database='postgres',
                user=DB_CONFIG['user']
            )

            # Drop existing test database
            await conn.execute("DROP DATABASE IF EXISTS quant_platform_test")
            print("  ✅ Dropped existing test database")

            # Create new test database
            await conn.execute("CREATE DATABASE quant_platform_test")
            print("  ✅ Created new test database")

            await conn.close()

            # Enable TimescaleDB extension
            conn = await asyncpg.connect(**DB_CONFIG)
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
            print("  ✅ Enabled TimescaleDB extension")
            await conn.close()

            # Load schema using psql
            print("\n📄 Step 2: Loading database schema...")
            schema_file = Path(__file__).parent.parent.parent / "scripts" / "init_postgres_schema.sql"

            result = subprocess.run(
                ['psql', '-d', 'quant_platform_test', '-f', str(schema_file)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print("  ✅ Schema loaded successfully")
            else:
                print(f"  ⚠️  Schema load completed with warnings")
                # Note: Some errors are expected (e.g., materialized view refresh errors)

        except Exception as e:
            print(f"  ❌ Error recreating database: {e}")
            sys.exit(1)
    else:
        print("\n⏩ Skipping database recreation (--skip-recreate)")

    # Connect to test database
    print("\n💾 Step 3: Loading test data...")
    conn = await asyncpg.connect(**DB_CONFIG)

    # Test tickers
    test_tickers = [
        ('005930', 'Samsung Electronics', 'KR'),
        ('035720', 'Kakao Corp', 'KR'),
        ('032830', 'Samsung Life Insurance', 'KR'),
        ('034020', 'Doosan Heavy Industries', 'KR'),
        ('006800', 'Mirae Asset Securities', 'KR')
    ]

    # Insert tickers
    print("\n  📋 Inserting tickers...")
    for ticker, name, region in test_tickers:
        await conn.execute("""
            INSERT INTO tickers (ticker, name, region)
            VALUES ($1, $2, $3)
            ON CONFLICT (ticker, region) DO NOTHING
        """, ticker, name, region)
        print(f"    ✓ {ticker} ({name})")

    # Load OHLCV data from CSV fixtures
    print("\n  📊 Loading OHLCV data from fixtures...")
    fixtures_dir = Path(__file__).parent
    total_rows = 0

    for ticker, name, region in test_tickers:
        csv_file = fixtures_dir / f"ohlcv_{ticker.lower()}_2024.csv"

        if not csv_file.exists():
            print(f"    ⚠️  Fixture not found: {csv_file.name}")
            continue

        # Read CSV and parse dates
        df = pd.read_csv(csv_file, parse_dates=['date'])

        # Insert OHLCV data
        rows_inserted = 0
        for _, row in df.iterrows():
            await conn.execute("""
                INSERT INTO ohlcv_data (ticker, region, timeframe, date, open, high, low, close, volume)
                VALUES ($1, $2, '1d', $3, $4, $5, $6, $7, $8)
                ON CONFLICT (ticker, region, timeframe, date) DO NOTHING
            """, ticker, region, row['date'].date(), row['open'], row['high'], row['low'], row['close'], row['volume'])
            rows_inserted += 1

        total_rows += rows_inserted
        print(f"    ✓ {ticker}: {rows_inserted} rows")

    print(f"\n  📊 Total OHLCV records loaded: {total_rows}")

    # Validation queries
    print("\n🔍 Step 4: Validating test database...")

    # Check ticker count
    ticker_count = await conn.fetchval("SELECT COUNT(*) FROM tickers")
    print(f"  ✓ Tickers: {ticker_count}")

    # Check OHLCV count
    ohlcv_count = await conn.fetchval("SELECT COUNT(*) FROM ohlcv_data")
    print(f"  ✓ OHLCV records: {ohlcv_count}")

    # Check date range
    date_range = await conn.fetchrow("""
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM ohlcv_data
    """)
    print(f"  ✓ Date range: {date_range['min_date']} to {date_range['max_date']}")

    # Test query performance
    import time
    start = time.time()
    test_rows = await conn.fetch("""
        SELECT * FROM ohlcv_data
        WHERE ticker = '005930' AND region = 'KR'
        ORDER BY date
        LIMIT 100
    """)
    elapsed_ms = (time.time() - start) * 1000
    print(f"  ✓ Sample query: {len(test_rows)} rows in {elapsed_ms:.2f}ms")

    await conn.close()

    print("\n✅ Test database setup complete!")
    print(f"\n📊 Summary:")
    print(f"  - Database: quant_platform_test")
    print(f"  - Tickers: {ticker_count}")
    print(f"  - OHLCV records: {ohlcv_count}")
    print(f"  - Date range: 2024 (1 year)")
    print(f"  - Ready for integration testing!")


async def teardown_test_database():
    """Drop test database (cleanup)."""
    print("🧹 Tearing down test database...")
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='postgres',
        user='13ruce'
    )
    await conn.execute("DROP DATABASE IF EXISTS quant_platform_test")
    await conn.close()
    print("✅ Test database dropped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--teardown":
        asyncio.run(teardown_test_database())
    else:
        skip_recreate = "--skip-recreate" in sys.argv
        asyncio.run(setup_test_database(skip_recreate=skip_recreate))
