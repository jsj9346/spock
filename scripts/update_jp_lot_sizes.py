#!/usr/bin/env python3
"""
Update Japan stock lot_sizes using KIS Master File

This script updates all JP tickers in the database with accurate lot_size
information from KIS master file (tsemst.cod).

Background:
- 2018 TSE Reform: Standardized most stocks to 100 shares/lot
- Phase 1 Investigation: Found 66 stocks (1.6%) with lot_size ≠ 100
- Master File Data: "Bid order size" contains accurate lot_size

Usage:
    # Dry run (preview changes)
    python3 scripts/update_jp_lot_sizes.py --dry-run

    # Execute update
    python3 scripts/update_jp_lot_sizes.py

    # Update specific tickers only
    python3 scripts/update_jp_lot_sizes.py --tickers 7203 9984 6758
"""

import os
import sys
import argparse
import sqlite3
from datetime import datetime
from typing import List, Dict
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters.jp_adapter_kis import JPAdapterKIS
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_jp_tickers_from_db(db_manager) -> List[Dict]:
    """Get all JP tickers from database"""
    conn = sqlite3.connect(db_manager.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ticker, name, lot_size, last_updated
        FROM tickers
        WHERE region = 'JP'
        AND is_active = 1
        ORDER BY ticker
    """)

    tickers = []
    for row in cursor.fetchall():
        tickers.append({
            'ticker': row[0],
            'name': row[1],
            'current_lot_size': row[2],
            'last_updated': row[3]
        })

    conn.close()
    return tickers


def update_ticker_lot_size(db_path: str, ticker: str, lot_size: int, dry_run: bool = False):
    """Update lot_size for a single ticker"""
    if dry_run:
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute("""
        UPDATE tickers
        SET lot_size = ?,
            last_updated = ?
        WHERE ticker = ?
        AND region = 'JP'
    """, (lot_size, now, ticker))

    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description='Update JP stock lot_sizes')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without updating database')
    parser.add_argument('--tickers', nargs='+',
                       help='Update specific tickers only (e.g., 7203 9984 6758)')
    args = parser.parse_args()

    print("="*80)
    print("Japan Stock Lot_size Update Script")
    print("="*80)
    print()

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No database changes will be made")
        print()

    # Initialize database manager
    db = SQLiteDatabaseManager()

    # Initialize JP adapter (will use updated _fetch_lot_size method)
    adapter = JPAdapterKIS(
        db_manager=db,
        app_key=os.getenv('KIS_APP_KEY', ''),
        app_secret=os.getenv('KIS_APP_SECRET', '')
    )

    # Get all JP tickers from database
    print("📊 Loading JP tickers from database...")
    all_tickers = get_jp_tickers_from_db(db)
    print(f"✅ Found {len(all_tickers)} JP tickers")
    print()

    # Filter tickers if specific ones requested
    if args.tickers:
        ticker_set = set(args.tickers)
        all_tickers = [t for t in all_tickers if t['ticker'] in ticker_set]
        print(f"🎯 Filtering to {len(all_tickers)} requested tickers")
        print()

    if not all_tickers:
        print("❌ No tickers to update")
        sys.exit(1)

    # Statistics
    stats = {
        'total': len(all_tickers),
        'updated': 0,
        'unchanged': 0,
        'errors': 0,
        'lot_size_distribution': {}
    }

    # Create backup (if not dry-run)
    if not args.dry_run:
        backup_path = f"data/backups/spock_local_before_jp_lot_size_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        print(f"💾 Creating database backup...")
        import shutil
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy(db.db_path, backup_path)
        print(f"✅ Backup created: {backup_path}")
        print()

    # Process each ticker
    print(f"🔄 Processing {stats['total']} JP tickers...")
    print("-"*80)

    for i, ticker_info in enumerate(all_tickers, 1):
        ticker = ticker_info['ticker']
        name = ticker_info['name']
        current_lot_size = ticker_info['current_lot_size']

        try:
            # Fetch lot_size from master file
            new_lot_size = adapter._fetch_lot_size(ticker)

            # Track lot_size distribution
            if new_lot_size not in stats['lot_size_distribution']:
                stats['lot_size_distribution'][new_lot_size] = 0
            stats['lot_size_distribution'][new_lot_size] += 1

            # Check if update needed
            if current_lot_size == new_lot_size:
                print(f"[{i:4d}/{stats['total']}] ✓ {ticker:10s} ({name[:30]:30s}) "
                      f"lot_size={new_lot_size:5d} (unchanged)")
                stats['unchanged'] += 1
            else:
                action = "Would update" if args.dry_run else "Updated"
                print(f"[{i:4d}/{stats['total']}] ✅ {ticker:10s} ({name[:30]:30s}) "
                      f"lot_size: {current_lot_size:5d} → {new_lot_size:5d} ({action})")
                stats['updated'] += 1

                # Update database (if not dry-run)
                update_ticker_lot_size(db.db_path, ticker, new_lot_size, args.dry_run)

        except Exception as e:
            print(f"[{i:4d}/{stats['total']}] ❌ {ticker:10s} ({name[:30]:30s}) "
                  f"Error: {e}")
            stats['errors'] += 1

    # Summary
    print()
    print("="*80)
    print("Summary")
    print("="*80)
    print(f"Total tickers:        {stats['total']:5d}")
    print(f"Updated:              {stats['updated']:5d}")
    print(f"Unchanged:            {stats['unchanged']:5d}")
    print(f"Errors:               {stats['errors']:5d}")
    print()

    # Lot_size distribution
    print("Lot_size Distribution:")
    print("-"*80)
    for lot_size in sorted(stats['lot_size_distribution'].keys()):
        count = stats['lot_size_distribution'][lot_size]
        percentage = (count / stats['total']) * 100
        print(f"  {lot_size:5d} shares/lot: {count:5d} tickers ({percentage:5.1f}%)")
    print()

    # Expected distribution (from Phase 1 investigation)
    print("Expected Distribution (Phase 1 Investigation):")
    print("-"*80)
    print("  100 shares/lot: 98.4% (3,973 stocks) - Standard post-2018 reform")
    print("    1 share/lot:   1.6% (65 stocks) - Penny stocks or special securities")
    print("  1000 shares/lot: 0.0% (1 stock) - Legacy exception")
    print()

    if args.dry_run:
        print("⚠️  DRY RUN COMPLETE - No changes were made to the database")
        print("   Run without --dry-run to apply changes")
    else:
        print("✅ Database update complete!")
        print()
        print("Next Steps:")
        print("1. Verify lot_size distribution matches expectations (~66 tickers with lot_size ≠ 100)")
        print("2. Test trading engine with JP stocks")
        print("3. Monitor order execution for lot_size compliance")

    print()


if __name__ == '__main__':
    main()
