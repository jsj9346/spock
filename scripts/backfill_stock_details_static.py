"""
Backfill Script for stock_details Using Static Sector Mapping

This script provides a fallback mechanism when external APIs (PyKRX, KRX, KIS) are unavailable.
Uses manually curated sector mappings for top Korean stocks.

Priority:
1. KRX API (if available)
2. PyKRX (if available)
3. Static mapping (this script)

Usage:
    python3 scripts/backfill_stock_details_static.py [--dry-run] [--limit N]

Author: Spock Trading System
"""

import sys
import os
import argparse
import logging
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_static_mapping(mapping_file: str = 'config/static_sector_mapping.json'):
    """
    Load static sector mapping from JSON file

    Args:
        mapping_file: Path to JSON mapping file

    Returns:
        Dictionary of ticker -> sector mapping
    """
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        mappings = data.get('mappings', {})
        logger.info(f"✅ Loaded {len(mappings)} stock sector mappings from {mapping_file}")
        return mappings

    except Exception as e:
        logger.error(f"❌ Failed to load static mapping: {e}")
        return {}


def get_stocks_with_null_sector(db: SQLiteDatabaseManager, limit: int = None):
    """Query stocks with NULL sector information"""
    conn = db._get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.ticker, t.name, sd.sector, sd.industry
        FROM tickers t
        LEFT JOIN stock_details sd ON t.ticker = sd.ticker
        WHERE t.region = 'KR'
          AND t.asset_type = 'STOCK'
          AND t.is_active = 1
          AND sd.sector IS NULL
        ORDER BY t.ticker
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    stocks = [dict(row) for row in results]
    logger.info(f"📊 Found {len(stocks)} stocks with NULL sector")
    return stocks


def backfill_with_static_mapping(db: SQLiteDatabaseManager,
                                   stocks: list,
                                   mappings: dict,
                                   dry_run: bool = False):
    """
    Backfill using static sector mapping

    Args:
        db: Database manager
        stocks: List of stocks to update
        mappings: Static sector mapping dictionary
        dry_run: If True, only show what would be updated

    Returns:
        (success_count, skipped_count, failed_count)
    """
    logger.info("\\n" + "=" * 60)
    logger.info("📊 Backfilling with Static Sector Mapping")
    logger.info("=" * 60)

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        name = stock.get('name', 'Unknown')

        try:
            logger.info(f"[{idx}/{len(stocks)}] Processing {ticker} ({name})...")

            # Check if ticker is in static mapping
            if ticker not in mappings:
                logger.debug(f"⚠️ [{ticker}] Not in static mapping")
                skipped_count += 1
                continue

            # Get mapping data
            mapping = mappings[ticker]

            updates = {}
            if mapping.get('sector'):
                updates['sector'] = mapping['sector']
                logger.info(f"   → Sector: {mapping['sector']}")

            if mapping.get('sector_code'):
                updates['sector_code'] = mapping['sector_code']
                logger.info(f"   → Sector Code: {mapping['sector_code']}")

            if mapping.get('industry'):
                updates['industry'] = mapping['industry']
                logger.info(f"   → Industry: {mapping['industry']}")

            if mapping.get('industry_code'):
                updates['industry_code'] = mapping['industry_code']
                logger.info(f"   → Industry Code: {mapping['industry_code']}")

            if not updates:
                skipped_count += 1
                continue

            # Update database (unless dry run)
            if not dry_run:
                if db.update_stock_details(ticker, updates):
                    success_count += 1
                    logger.info(f"✅ [{ticker}] Updated successfully")
                else:
                    failed_count += 1
                    logger.error(f"❌ [{ticker}] Database update failed")
            else:
                logger.info(f"   [DRY RUN] Would update: {', '.join(updates.keys())}")
                success_count += 1

        except Exception as e:
            logger.error(f"❌ [{ticker}] Backfill failed: {e}")
            failed_count += 1

    return (success_count, skipped_count, failed_count)


def main():
    parser = argparse.ArgumentParser(description='Backfill stock_details with static sector mapping')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without making changes')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of stocks to process')
    parser.add_argument('--db-path', type=str, default='data/spock_local.db',
                       help='Path to SQLite database')
    parser.add_argument('--mapping-file', type=str, default='config/static_sector_mapping.json',
                       help='Path to static sector mapping JSON file')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🔧 Stock Details Backfill Script (Static Mapping)")
    logger.info("=" * 60)
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Mapping File: {args.mapping_file}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Limit: {args.limit if args.limit else 'No limit'}")
    logger.info("=" * 60)

    # Load static mapping
    mappings = load_static_mapping(args.mapping_file)
    if not mappings:
        logger.error("❌ No mappings loaded, exiting")
        return

    # Initialize database
    db = SQLiteDatabaseManager(db_path=args.db_path)

    # Get stocks to update
    stocks = get_stocks_with_null_sector(db, limit=args.limit)

    if not stocks:
        logger.info("✅ No stocks need updating")
        return

    # Backfill with static mapping
    success, skipped, failed = backfill_with_static_mapping(db, stocks, mappings, dry_run=args.dry_run)

    # Summary
    logger.info("\\n" + "=" * 60)
    logger.info("📊 BACKFILL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Stocks Checked: {len(stocks)}")
    logger.info(f"  ✅ Updated: {success}")
    logger.info(f"  ⚠️  Skipped (not in mapping): {skipped}")
    logger.info(f"  ❌ Failed: {failed}")
    logger.info(f"Coverage: {success}/{len(stocks)} ({100*success/len(stocks) if stocks else 0:.1f}%)")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("\\n💡 Tip: Run without --dry-run to apply updates to database")
    else:
        logger.info(f"\\n✅ Database updated successfully")
        logger.info(f"   {success} stocks now have sector information")


if __name__ == '__main__':
    main()
