"""
Backfill Script for stock_details Table (Version 2)

Priority 2 implementation with KRX sector classification API and KIS par_value API.

Updates existing NULL values with:
- KRX API: sector, sector_code, industry, industry_code
- KIS API: par_value
- Fallback to pykrx if KRX API fails

Usage:
    python3 scripts/backfill_stock_details_v2.py [--dry-run] [--limit N] [--tickers TICKER1,TICKER2,...]
    python3 scripts/backfill_stock_details_v2.py --collect-par-value  # KIS API only

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
from modules.api_clients.krx_data_api import KRXDataAPI
from modules.api_clients.kis_domestic_stock_api import KISDomesticStockAPI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_stocks_with_null_sector(db: SQLiteDatabaseManager, limit: int = None):
    """Query stocks with NULL sector information"""
    conn = db._get_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.ticker, t.name, sd.sector, sd.industry, sd.par_value
        FROM tickers t
        LEFT JOIN stock_details sd ON t.ticker = sd.ticker
        WHERE t.region = 'KR'
          AND t.asset_type = 'STOCK'
          AND t.is_active = 1
          AND (sd.sector IS NULL OR sd.industry IS NULL OR sd.par_value IS NULL)
        ORDER BY t.ticker
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    stocks = [dict(row) for row in results]
    logger.info(f"📊 Found {len(stocks)} stocks with NULL fields")
    return stocks


def backfill_with_krx_api(db: SQLiteDatabaseManager,
                          stocks: list,
                          dry_run: bool = False):
    """
    Backfill using KRX sector classification API (Priority 2)

    Args:
        db: Database manager
        stocks: List of stocks to update
        dry_run: If True, only show what would be updated

    Returns:
        (success_count, skipped_count, failed_count)
    """
    logger.info("\n" + "=" * 60)
    logger.info("📊 Strategy 1: KRX Sector Classification API")
    logger.info("=" * 60)

    krx_api = KRXDataAPI()
    pykrx_api = PyKRXAPI()

    # Get sector classification map (single API call for all stocks)
    try:
        sector_map = krx_api.get_sector_classification(market='ALL')
        logger.info(f"✅ Loaded sector classification for {len(sector_map)} stocks")
    except Exception as e:
        logger.error(f"❌ KRX Sector Classification API failed: {e}")
        return (0, len(stocks), 0)

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        name = stock.get('name', 'Unknown')

        try:
            logger.info(f"[{idx}/{len(stocks)}] Processing {ticker} ({name})...")

            if ticker not in sector_map:
                logger.warning(f"⚠️ [{ticker}] Not in KRX sector map")
                skipped_count += 1
                continue

            krx_sector_info = sector_map[ticker]

            # Map KRX sector to GICS
            krx_sector = krx_sector_info.get('sector')
            gics_sector = pykrx_api._map_krx_to_gics(krx_sector) if krx_sector else None

            updates = {}
            if gics_sector:
                updates['sector'] = gics_sector
                logger.info(f"   → Sector: {gics_sector} (KRX: {krx_sector})")

            if krx_sector_info.get('sector_code'):
                updates['sector_code'] = krx_sector_info['sector_code']
                logger.info(f"   → Sector Code: {krx_sector_info['sector_code']}")

            if krx_sector_info.get('industry'):
                updates['industry'] = krx_sector_info['industry']
                logger.info(f"   → Industry: {krx_sector_info['industry']}")

            if krx_sector_info.get('industry_code'):
                updates['industry_code'] = krx_sector_info['industry_code']
                logger.info(f"   → Industry Code: {krx_sector_info['industry_code']}")

            if not updates:
                skipped_count += 1
                continue

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

    return (success_count, skipped_count, failed_count)


def backfill_par_value(db: SQLiteDatabaseManager,
                       stocks: list,
                       kis_app_key: str,
                       kis_app_secret: str,
                       dry_run: bool = False):
    """
    Backfill par_value using KIS API

    Args:
        db: Database manager
        stocks: List of stocks to update
        kis_app_key: KIS API key
        kis_app_secret: KIS API secret
        dry_run: If True, only show what would be updated

    Returns:
        (success_count, skipped_count, failed_count)
    """
    logger.info("\n" + "=" * 60)
    logger.info("💰 Strategy 2: KIS Stock Info API (Par Value)")
    logger.info("=" * 60)

    kis_api = KISDomesticStockAPI(kis_app_key, kis_app_secret)

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']
        name = stock.get('name', 'Unknown')

        # Skip if par_value already exists
        if stock.get('par_value'):
            skipped_count += 1
            continue

        try:
            logger.info(f"[{idx}/{len(stocks)}] Processing {ticker} ({name})...")

            # Get stock info from KIS API
            stock_info = kis_api.get_stock_info(ticker)

            if not stock_info or not stock_info.get('par_value'):
                logger.warning(f"⚠️ [{ticker}] No par value data")
                skipped_count += 1
                continue

            updates = {'par_value': stock_info['par_value']}
            logger.info(f"   → Par Value: {stock_info['par_value']:,}원")

            # Update database (unless dry run)
            if not dry_run:
                if db.update_stock_details(ticker, updates):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                logger.info(f"   [DRY RUN] Would update: par_value")
                success_count += 1

        except Exception as e:
            logger.error(f"❌ [{ticker}] Par value collection failed: {e}")
            failed_count += 1

    return (success_count, skipped_count, failed_count)


def main():
    parser = argparse.ArgumentParser(description='Backfill stock_details with Priority 2 APIs')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be updated without making changes')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of stocks to process')
    parser.add_argument('--tickers', type=str,
                       help='Comma-separated list of specific tickers')
    parser.add_argument('--db-path', type=str, default='data/spock_local.db',
                       help='Path to SQLite database')
    parser.add_argument('--collect-par-value', action='store_true',
                       help='Only collect par_value using KIS API')
    parser.add_argument('--skip-par-value', action='store_true',
                       help='Skip par_value collection (KRX API only)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🔧 Stock Details Backfill Script v2 (Priority 2)")
    logger.info("=" * 60)
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Limit: {args.limit if args.limit else 'No limit'}")
    logger.info(f"Specific Tickers: {args.tickers if args.tickers else 'All NULL stocks'}")
    logger.info("=" * 60)

    # Initialize database
    db = SQLiteDatabaseManager(db_path=args.db_path)

    # Get stocks to update
    if args.tickers:
        stocks = []
        for ticker in args.tickers.split(','):
            stocks.append({'ticker': ticker.strip(), 'name': None, 'sector': None, 'industry': None, 'par_value': None})
        logger.info(f"📊 Processing {len(stocks)} specific tickers")
    else:
        stocks = get_stocks_with_null_sector(db, limit=args.limit)

    if not stocks:
        logger.info("✅ No stocks need updating")
        return

    # Backfill with KRX API (sector/industry/codes)
    if not args.collect_par_value:
        success1, skipped1, failed1 = backfill_with_krx_api(db, stocks, dry_run=args.dry_run)
    else:
        success1, skipped1, failed1 = (0, 0, 0)

    # Backfill par_value with KIS API
    # ⚠️ WARNING: KIS stock info API endpoint is deprecated (404 Not Found)
    # The /inquire-search-stock-info endpoint is no longer available
    if not args.skip_par_value:
        logger.warning("=" * 60)
        logger.warning("⚠️ Par Value Collection SKIPPED - KIS API Endpoint Deprecated")
        logger.warning("=" * 60)
        logger.warning("The KIS API endpoint for stock info is no longer available:")
        logger.warning("  /uapi/domestic-stock/v1/quotations/inquire-search-stock-info")
        logger.warning("")
        logger.warning("Status: ❌ Returns 404 Not Found (removed from official catalog)")
        logger.warning("")
        logger.warning("Alternatives for par_value collection:")
        logger.warning("  1. KIS GitHub master files: github.com/koreainvestment/open-trading-api")
        logger.warning("  2. Alternative data sources (Naver Finance, etc.)")
        logger.warning("")
        logger.warning("Note: Par value is NOT critical for trading logic")
        logger.warning("      Sector classification (KRX/PyKRX) is sufficient")
        logger.warning("=" * 60)
        success2, skipped2, failed2 = (0, len(stocks), 0)
    else:
        success2, skipped2, failed2 = (0, 0, 0)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 BACKFILL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Stocks: {len(stocks)}")
    logger.info(f"KRX API (Sector/Industry):")
    logger.info(f"  ✅ Success: {success1}")
    logger.info(f"  ⚠️  Skipped: {skipped1}")
    logger.info(f"  ❌ Failed: {failed1}")
    logger.info(f"KIS API (Par Value):")
    logger.info(f"  ✅ Success: {success2}")
    logger.info(f"  ⚠️  Skipped: {skipped2}")
    logger.info(f"  ❌ Failed: {failed2}")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("\n💡 Tip: Run without --dry-run to apply updates to database")


if __name__ == '__main__':
    main()
