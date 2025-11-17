#!/usr/bin/env python3
"""
Clean up SQLite Test Database

Purpose:
    Remove orphaned data and corrupted ticker 091090 from SQLite test database.

Execution:
    python3 scripts/cleanup_sqlite_test_db.py
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'spock_local.db'


def main():
    """Clean up SQLite test database."""
    print("=" * 80)
    print("SQLITE TEST DATABASE CLEANUP")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    try:
        # Step 1: Count orphaned records
        print("Step 1: Analyzing orphaned data...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_data o
            LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
            WHERE t.ticker IS NULL
        """)
        orphaned_count = cursor.fetchone()[0]
        print(f"  Found {orphaned_count:,} orphaned records")

        # Step 2: Count ticker 091090 records
        print("\nStep 2: Analyzing ticker 091090...")
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE ticker = '091090' AND region = 'KR'
        """)
        ticker_091090_count = cursor.fetchone()[0]
        print(f"  Found {ticker_091090_count:,} ticker 091090 records")

        total_to_delete = orphaned_count + ticker_091090_count
        print(f"\n  Total records to delete: {total_to_delete:,}")

        # Step 3: Delete orphaned data
        print("\nStep 3: Deleting orphaned data...")
        cursor.execute("""
            DELETE FROM ohlcv_data
            WHERE rowid IN (
                SELECT o.rowid
                FROM ohlcv_data o
                LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
                WHERE t.ticker IS NULL
            )
        """)
        deleted_orphans = cursor.rowcount
        print(f"  ✅ Deleted {deleted_orphans:,} orphaned records")

        # Step 4: Delete ticker 091090
        print("\nStep 4: Deleting ticker 091090...")
        cursor.execute("""
            DELETE FROM ohlcv_data
            WHERE ticker = '091090' AND region = 'KR'
        """)
        deleted_091090 = cursor.rowcount
        print(f"  ✅ Deleted {deleted_091090:,} ticker 091090 records")

        # Step 5: Verify cleanup
        print("\nStep 5: Verifying cleanup...")

        # Check remaining orphans
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_data o
            LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
            WHERE t.ticker IS NULL
        """)
        remaining_orphans = cursor.fetchone()[0]

        # Check remaining ticker 091090
        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE ticker = '091090' AND region = 'KR'
        """)
        remaining_091090 = cursor.fetchone()[0]

        # Get final stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT ticker) as unique_tickers
            FROM ohlcv_data
            WHERE region = 'KR'
        """)
        total_records, unique_tickers = cursor.fetchone()

        print(f"  Remaining orphans: {remaining_orphans:,}")
        print(f"  Remaining ticker 091090: {remaining_091090:,}")
        print(f"  Total KR records: {total_records:,}")
        print(f"  Unique KR tickers: {unique_tickers:,}")

        # Validation
        if remaining_orphans == 0 and remaining_091090 == 0:
            conn.commit()
            print("\n✅ Cleanup committed successfully!")

            # VACUUM to reclaim space
            print("\nStep 6: Reclaiming disk space (VACUUM)...")
            conn.execute("VACUUM")
            print("  ✅ Database optimized")

            # Summary
            print("\n" + "=" * 80)
            print("CLEANUP SUMMARY")
            print("=" * 80)
            print(f"  Orphaned records deleted: {deleted_orphans:,}")
            print(f"  Ticker 091090 deleted: {deleted_091090:,}")
            print(f"  Total deleted: {deleted_orphans + deleted_091090:,}")
            print(f"  Remaining records: {total_records:,}")
            print(f"  Unique tickers: {unique_tickers:,}")
            print("  Status: ✅ SUCCESS")
            print("=" * 80)
        else:
            conn.rollback()
            print(f"\n❌ Validation failed - Rolling back")
            print(f"  Orphans remaining: {remaining_orphans:,}")
            print(f"  091090 remaining: {remaining_091090:,}")
            sys.exit(1)

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        print("  Changes rolled back")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
