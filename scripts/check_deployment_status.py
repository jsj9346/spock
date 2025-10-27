#!/usr/bin/env python3
"""
Check status of historical fundamental data deployment

Usage:
    python3 scripts/check_deployment_status.py
    python3 scripts/check_deployment_status.py --detailed
"""

import os
import sys
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager


def check_deployment_status(detailed: bool = False):
    """Check current status of historical data collection"""

    print("=" * 70)
    print("📊 HISTORICAL FUNDAMENTAL DATA - DEPLOYMENT STATUS")
    print("=" * 70)

    db = SQLiteDatabaseManager()
    conn = db._get_connection()
    cursor = conn.cursor()

    # Count total historical rows
    cursor.execute('''
        SELECT COUNT(*) FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND period_type = 'ANNUAL'
    ''')
    total_rows = cursor.fetchone()[0]
    print(f"\n📊 Total Historical Rows: {total_rows:,}")

    # Count distinct tickers
    cursor.execute('''
        SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND period_type = 'ANNUAL'
    ''')
    distinct_tickers = cursor.fetchone()[0]
    print(f"🎯 Distinct Tickers: {distinct_tickers}")

    # Count by year
    print(f"\n📅 Data by Year:")
    for year in range(2020, 2025):
        cursor.execute('''
            SELECT COUNT(*) FROM ticker_fundamentals
            WHERE fiscal_year = ? AND period_type = 'ANNUAL'
        ''', (year,))
        count = cursor.fetchone()[0]
        print(f"  {year}: {count:,} rows")

    if detailed:
        print(f"\n📋 Tickers with Complete Data (2020-2024):")

        # Get tickers with 5 years of data
        cursor.execute('''
            SELECT ticker, COUNT(*) as year_count
            FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND period_type = 'ANNUAL'
            GROUP BY ticker
            HAVING year_count = 5
            ORDER BY ticker
        ''')

        complete_tickers = cursor.fetchall()
        print(f"\n  Complete Tickers ({len(complete_tickers)}):")
        for ticker, count in complete_tickers:
            print(f"    ✅ {ticker} ({count} years)")

        # Get tickers with partial data
        cursor.execute('''
            SELECT ticker, COUNT(*) as year_count
            FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND period_type = 'ANNUAL'
            GROUP BY ticker
            HAVING year_count < 5
            ORDER BY ticker
        ''')

        partial_tickers = cursor.fetchall()
        if partial_tickers:
            print(f"\n  Partial Tickers ({len(partial_tickers)}):")
            for ticker, count in partial_tickers:
                print(f"    ⚠️  {ticker} ({count}/5 years)")

    conn.close()
    print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check deployment status')
    parser.add_argument('--detailed', action='store_true', help='Show detailed ticker list')

    args = parser.parse_args()
    check_deployment_status(detailed=args.detailed)
