#!/usr/bin/env python3
"""
Add Financial Statement Columns to ticker_fundamentals Table

Purpose:
    Quick fix to add financial statement columns (total_assets, total_equity, net_income, etc.)
    to ticker_fundamentals table so DART data can be stored immediately.

Why needed:
    DART API returns financial statement data but ticker_fundamentals table doesn't have
    columns for it, so the data gets discarded.

Long-term solution:
    Migrate to normalized schema with separate income_statements, balance_sheets tables.
    For now, add columns to ticker_fundamentals for immediate testing.

Columns to add:
    - total_assets BIGINT
    - total_liabilities BIGINT
    - total_equity BIGINT
    - revenue BIGINT
    - operating_profit BIGINT
    - net_income BIGINT
    - ebitda BIGINT

Usage:
    python3 scripts/add_financial_columns_to_fundamentals.py

Author: Spock Quant Platform
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "./data/spock_local.db"

# Columns to add
NEW_COLUMNS = [
    ("total_assets", "BIGINT"),
    ("total_liabilities", "BIGINT"),
    ("total_equity", "BIGINT"),
    ("revenue", "BIGINT"),
    ("operating_profit", "BIGINT"),
    ("net_income", "BIGINT"),
    ("ebitda", "BIGINT"),
]


def add_columns():
    """Add financial statement columns to ticker_fundamentals table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check existing columns
        cursor.execute("PRAGMA table_info(ticker_fundamentals)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        logger.info(f"📊 Current columns in ticker_fundamentals: {len(existing_columns)}")

        # Add new columns
        added_count = 0
        for col_name, col_type in NEW_COLUMNS:
            if col_name not in existing_columns:
                logger.info(f"➕ Adding column: {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE ticker_fundamentals ADD COLUMN {col_name} {col_type}")
                added_count += 1
            else:
                logger.info(f"⏭️  Column already exists: {col_name}")

        conn.commit()
        conn.close()

        logger.info(f"\n✅ Schema update complete:")
        logger.info(f"   - Added {added_count} new columns")
        logger.info(f"   - Total columns: {len(existing_columns) + added_count}")

        return True

    except Exception as e:
        logger.error(f"❌ Schema update failed: {e}")
        return False


if __name__ == '__main__':
    add_columns()
