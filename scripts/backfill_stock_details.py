"""
Backfill Script for stock_details Table

Updates existing NULL values in stock_details table with sector/industry information
using pykrx API integration.

Usage:
    python3 scripts/backfill_stock_details.py [--dry-run] [--limit N] [--tickers TICKER1,TICKER2,...]

Author: Spock Trading System
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.api_clients.pykrx_api import PyKRXAPI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_stocks_with_null_sector(db: SQLiteDatabaseManager, limit: int = None):
    """
    Query stocks with NULL sector information

    Args:
        db: Database manager instance
        limit: Maximum number of stocks to return

    Returns:
        List of ticker dictionaries
    """
    conn = db._get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.ticker, t.name, sd.sector, sd.industry
        FROM tickers t
        LEFT JOIN stock_details sd ON t.ticker = sd.ticker
        WHERE t.region = 'KR'
          AND t.asset_type = 'STOCK'
          AND t.is_active = 1
          AND (sd.sector IS NULL OR sd.industry IS NULL)
        ORDER BY t.ticker
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    stocks = [dict(row) for row in results]
    logger.info(f"📊 Found {len(stocks)} stocks with NULL sector/industry")
    return stocks


def backfill_stock_details(db_path: str = 'data/spock_local.db',
                           dry_run: bool = False,
                           limit: int = None,
                           tickers: list = None):
    """
    Main backfill function

    Args:
        db_path: Path to SQLite database
        dry_run: If True, only show what would be updated
        limit: Maximum number of stocks to process
        tickers: Specific tickers to process (None = all NULL stocks)
    """
    logger.info("=" * 60)
    logger.info("🔧 Stock Details Backfill Script")
    logger.info("=" * 60)
    logger.info(f"Database: {db_path}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"Limit: {limit if limit else 'No limit'}")
    logger.info(f"Specific Tickers: {tickers if tickers else 'All NULL stocks'}")
    logger.info("=" * 60)

    # Initialize database and API
    db = SQLiteDatabaseManager(db_path=db_path)
    pykrx_api = PyKRXAPI()

    # Check pykrx availability
    if not pykrx_api.pykrx_available:
        logger.error("❌ pykrx is not installed. Install with: pip install pykrx>=1.0.51")
        return

    # Get stocks to update
    if tickers:
        stocks = []
        for ticker in tickers:
            stocks.append({'ticker': ticker, 'name': None, 'sector': None, 'industry': None})
        logger.info(f"📊 Processing {len(stocks)} specific tickers")
    else:
        stocks = get_stocks_with_null_sector(db, limit=limit)

    if not stocks:
        logger.info("✅ No stocks need updating")
        return

    # Statistics
    success_count = 0
    failed_count = 0
    skipped_count = 0

    # Process each stock
    logger.info(f"\n{'🔍 DRY RUN MODE' if dry_run else '🚀 UPDATE MODE'}")
    logger.info("-" * 60)

    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        name = stock.get('name', 'Unknown')

        try:
            # Get sector info from pykrx
            logger.info(f"[{idx}/{len(stocks)}] Processing {ticker} ({name})...")
            sector_info = pykrx_api.get_stock_sector_info(ticker)

            if not sector_info or not any([
                sector_info.get('sector'),
                sector_info.get('industry'),
                sector_info.get('par_value')
            ]):
                logger.warning(f"⚠️ [{ticker}] No sector information available")
                skipped_count += 1
                continue

            # Display updates
            updates = {}
            if sector_info.get('sector'):
                updates['sector'] = sector_info['sector']
                logger.info(f"   → Sector: {sector_info['sector']}")
            if sector_info.get('industry'):
                updates['industry'] = sector_info['industry']
                logger.info(f"   → Industry: {sector_info['industry']}")
            if sector_info.get('par_value'):
                updates['par_value'] = sector_info['par_value']
                logger.info(f"   → Par Value: {sector_info['par_value']}")

            # Update database (unless dry run)
            if not dry_run:
                if db.update_stock_details(ticker, updates):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                logger.info(f"   [DRY RUN] Would update: {', '.join(updates.keys())}")
                success_count += 1

        except Exception as e:
            logger.error(f"❌ [{ticker}] Backfill failed: {e}")
            failed_count += 1

        # Progress logging every 10 stocks
        if idx % 10 == 0:
            logger.info(f"📊 Progress: {idx}/{len(stocks)} stocks processed")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 BACKFILL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Stocks: {len(stocks)}")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"⚠️  Skipped: {skipped_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info("=" * 60)

    if dry_run:
        logger.info("\n💡 Tip: Run without --dry-run to apply updates to database")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill stock_details table with sector/industry data')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without making changes')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of stocks to process')
    parser.add_argument('--tickers', type=str,
                       help='Comma-separated list of specific tickers to process')
    parser.add_argument('--db-path', type=str, default='data/spock_local.db',
                       help='Path to SQLite database (default: data/spock_local.db)')

    args = parser.parse_args()

    # Parse tickers if provided
    tickers_list = None
    if args.tickers:
        tickers_list = [t.strip() for t in args.tickers.split(',')]

    # Run backfill
    backfill_stock_details(
        db_path=args.db_path,
        dry_run=args.dry_run,
        limit=args.limit,
        tickers=tickers_list
    )
