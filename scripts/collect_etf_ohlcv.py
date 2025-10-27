#!/usr/bin/env python3
"""
ETF OHLCV Collection Script

Purpose: Collect 250-day OHLCV data for 50 ETFs using the fixed stock API method

Usage:
    python3 scripts/collect_etf_ohlcv.py [--etf-count 50] [--days 250] [--dry-run]

Arguments:
    --etf-count: Number of ETFs to collect (default: 50)
    --days: Historical days to collect (default: 250)
    --dry-run: Test without actual collection

Prerequisites:
    - KIS API rate limit must be reset (wait 1-2 hours after last test)
    - .env file with KIS_APP_KEY and KIS_APP_SECRET
    - Database initialized with ETF tickers

Expected Output:
    - ~12,500 OHLCV records (50 ETFs × 250 days)
    - Technical indicators calculated (MA5, MA20, RSI, MACD, etc.)
    - Collection duration: 6-8 hours (with rate limiting)

Author: Spock Trading System
Phase: 2.5 - ETF Data Collection
"""

import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.market_adapters import KoreaAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager
from dotenv import load_dotenv
import argparse


def main():
    """Main execution function"""

    # Parse arguments
    parser = argparse.ArgumentParser(description='Collect ETF OHLCV data')
    parser.add_argument('--etf-count', type=int, default=50, help='Number of ETFs to collect')
    parser.add_argument('--days', type=int, default=250, help='Historical days to collect')
    parser.add_argument('--dry-run', action='store_true', help='Test without actual collection')
    args = parser.parse_args()

    # Load environment
    load_dotenv()

    print("=" * 80)
    print("ETF OHLCV Collection Script")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"   ETF Count: {args.etf_count}")
    print(f"   Days: {args.days}")
    print(f"   Dry Run: {args.dry_run}")
    print(f"   Expected Records: ~{args.etf_count * args.days:,}")

    # Check environment variables
    if not os.getenv('KIS_APP_KEY') or not os.getenv('KIS_APP_SECRET'):
        print("\n❌ ERROR: KIS API credentials not found in .env file")
        print("   Please set KIS_APP_KEY and KIS_APP_SECRET")
        sys.exit(1)

    # Initialize
    print("\n📊 Initializing...")
    db = SQLiteDatabaseManager(db_path='data/spock_local.db')
    adapter = KoreaAdapter(
        db_manager=db,
        kis_app_key=os.getenv('KIS_APP_KEY'),
        kis_app_secret=os.getenv('KIS_APP_SECRET')
    )

    # Get ETF list
    print(f"📋 Fetching ETF list from database...")
    etfs = db.get_tickers(region='KR', asset_type='ETF', is_active=True)

    if not etfs:
        print("❌ ERROR: No ETFs found in database")
        sys.exit(1)

    etf_tickers = [e['ticker'] for e in etfs[:args.etf_count]]
    print(f"   Selected {len(etf_tickers)} ETFs for collection")

    # Dry run check
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No actual collection will occur")
        print("\nETFs to be collected:")
        for i, ticker in enumerate(etf_tickers[:10], 1):
            etf_info = next(e for e in etfs if e['ticker'] == ticker)
            print(f"   {i}. {ticker}: {etf_info['name']}")
        if len(etf_tickers) > 10:
            print(f"   ... and {len(etf_tickers) - 10} more")

        print("\n✅ Dry run complete - ready for actual collection")
        return

    # Pre-collection validation
    print("\n🔍 Pre-collection validation...")

    # Check existing OHLCV count
    conn = db._get_connection()
    cursor = conn.cursor()
    existing_ohlcv = cursor.execute("""
        SELECT COUNT(*) FROM ohlcv_data
        WHERE ticker IN (SELECT ticker FROM tickers WHERE asset_type='ETF')
    """).fetchone()[0]
    conn.close()

    print(f"   Existing ETF OHLCV records: {existing_ohlcv:,}")

    # Confirm execution
    print("\n⚠️  WARNING: This will take 6-8 hours with rate limiting")
    print("   Press Ctrl+C to cancel within 5 seconds...")

    try:
        for i in range(5, 0, -1):
            print(f"   Starting in {i}...", end='\r')
            time.sleep(1)
        print("\n")
    except KeyboardInterrupt:
        print("\n\n❌ Collection cancelled by user")
        sys.exit(0)

    # Start collection
    print("=" * 80)
    print("STARTING ETF OHLCV COLLECTION")
    print("=" * 80)

    start_time = time.time()

    try:
        # Execute collection
        success_count = adapter.collect_etf_ohlcv(
            tickers=etf_tickers,
            days=args.days
        )

        elapsed_time = time.time() - start_time

        # Post-collection validation
        print("\n" + "=" * 80)
        print("COLLECTION COMPLETE")
        print("=" * 80)

        print(f"\n⏱️  Duration: {elapsed_time/60:.1f} minutes ({elapsed_time:.0f} seconds)")
        print(f"📊 Success Rate: {success_count}/{len(etf_tickers)} ETFs ({success_count/len(etf_tickers)*100:.1f}%)")

        # Check database
        conn = db._get_connection()
        cursor = conn.cursor()

        total_ohlcv = cursor.execute("SELECT COUNT(*) FROM ohlcv_data").fetchone()[0]
        etf_ohlcv = cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE ticker IN (SELECT ticker FROM tickers WHERE asset_type='ETF')
        """).fetchone()[0]

        new_records = etf_ohlcv - existing_ohlcv

        print(f"\n💾 Database:")
        print(f"   Total OHLCV records: {total_ohlcv:,}")
        print(f"   ETF OHLCV records: {etf_ohlcv:,}")
        print(f"   New records added: {new_records:,}")

        # Sample verification
        sample = cursor.execute("""
            SELECT ticker, COUNT(*) as days,
                   COUNT(ma5) as has_ma5, COUNT(rsi_14) as has_rsi,
                   MIN(date) as earliest, MAX(date) as latest
            FROM ohlcv_data
            WHERE ticker IN (SELECT ticker FROM tickers WHERE asset_type='ETF')
            GROUP BY ticker
            LIMIT 5
        """).fetchall()

        print(f"\n📋 Sample ETF OHLCV data:")
        for ticker, days, ma5, rsi, earliest, latest in sample:
            print(f"   {ticker}: {days} days | MA5: {ma5} | RSI: {rsi} | {earliest} to {latest}")

        conn.close()

        # Success criteria
        print("\n" + "=" * 80)
        if success_count >= args.etf_count * 0.8 and etf_ohlcv >= args.etf_count * args.days * 0.8:
            print("✅ COLLECTION SUCCESSFUL")
            print(f"   → {success_count} ETFs with {etf_ohlcv:,} OHLCV records")
            print(f"   → Technical indicators calculated")
            print(f"   → Phase 2.5 ready for completion")
        elif success_count >= args.etf_count * 0.5:
            print("⚠️  COLLECTION PARTIAL SUCCESS")
            print(f"   → {success_count}/{len(etf_tickers)} ETFs collected")
            print(f"   → {etf_ohlcv:,} OHLCV records (target: {args.etf_count * args.days:,})")
        else:
            print("❌ COLLECTION FAILED")
            print(f"   → Only {success_count}/{len(etf_tickers)} ETFs succeeded")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        elapsed_time = time.time() - start_time
        print(f"   Elapsed time: {elapsed_time/60:.1f} minutes")

        # Check partial results
        conn = db._get_connection()
        cursor = conn.cursor()
        etf_ohlcv = cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE ticker IN (SELECT ticker FROM tickers WHERE asset_type='ETF')
        """).fetchone()[0]
        conn.close()

        print(f"   Partial records saved: {etf_ohlcv:,}")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
