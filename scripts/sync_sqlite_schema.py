#!/usr/bin/env python3
"""
SQLite Schema Sync Script

Purpose: Synchronize SQLite schema with PostgreSQL to fix missing columns
Issue: SQLite missing 'rsi' column causing 27 LayeredScoringEngine SQL errors

Usage:
    python3 scripts/sync_sqlite_schema.py [--dry-run] [--db-path PATH]

Arguments:
    --dry-run    : Show what would be done without making changes
    --db-path    : Path to SQLite database (default: data/spock_local.db)

Exit Codes:
    0: Success (column added or already exists)
    1: Database not found
    2: Schema sync failed
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [col[1] for col in cursor.fetchall()]
    return column in columns


def get_table_columns(cursor: sqlite3.Cursor, table: str) -> List[Tuple[str, str]]:
    """Get all columns and their types from a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return [(col[1], col[2]) for col in cursor.fetchall()]


def add_rsi_column(conn: sqlite3.Connection, dry_run: bool = False) -> bool:
    """
    Add missing 'rsi' column to ohlcv_data table.

    Returns:
        True if column was added or already exists, False on error
    """
    cursor = conn.cursor()

    # Check if rsi column exists
    if check_column_exists(cursor, "ohlcv_data", "rsi"):
        print("✅ 'rsi' column already exists in ohlcv_data table")
        return True

    print("❌ 'rsi' column missing from ohlcv_data table")

    if dry_run:
        print("[DRY RUN] Would execute: ALTER TABLE ohlcv_data ADD COLUMN rsi REAL")
        return True

    try:
        print("🔧 Adding 'rsi' column to ohlcv_data table...")
        cursor.execute("ALTER TABLE ohlcv_data ADD COLUMN rsi REAL")
        conn.commit()
        print("✅ Successfully added 'rsi' column")
        return True
    except sqlite3.Error as e:
        print(f"❌ Failed to add 'rsi' column: {e}")
        return False


def verify_schema(cursor: sqlite3.Cursor) -> None:
    """Verify and display ohlcv_data schema."""
    print("\n📋 Current ohlcv_data schema:")
    print("-" * 60)
    columns = get_table_columns(cursor, "ohlcv_data")
    for col_name, col_type in columns:
        print(f"  {col_name:<20} {col_type}")
    print("-" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync SQLite schema with PostgreSQL (add missing rsi column)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/spock_local.db",
        help="Path to SQLite database (default: data/spock_local.db)"
    )

    args = parser.parse_args()

    # Check database exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("   Please check the path and try again.")
        sys.exit(1)

    print(f"🔍 Analyzing database: {db_path}")
    print(f"   Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Show current schema
        verify_schema(cursor)

        # Add missing rsi column
        print("\n🔧 Schema Sync Operation:")
        print("-" * 60)
        success = add_rsi_column(conn, dry_run=args.dry_run)
        print("-" * 60)

        if not success:
            conn.close()
            sys.exit(2)

        # Show updated schema
        if not args.dry_run:
            print()
            verify_schema(cursor)

        conn.close()

        print("\n✅ Schema sync completed successfully")
        print("\n📝 Next Steps:")
        print("   1. Run backtest_runner tests to verify fix")
        print("   2. Check LayeredScoringEngine SQL errors are resolved")
        print("   3. Consider backfilling RSI values if needed")

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
