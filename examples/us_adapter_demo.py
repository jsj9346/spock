"""
US Adapter Integration Demo

Demonstrates USAdapter usage for US stock market data collection.

Prerequisites:
1. Polygon.io API key (free tier)
2. Initialized SQLite database (spock_local.db)

Usage:
    python3 examples/us_adapter_demo.py --polygon-key YOUR_API_KEY

Features:
- Scan US stocks (NYSE, NASDAQ, AMEX)
- Collect OHLCV data with rate limiting
- Collect company fundamentals
- Verify database records

Author: Spock Trading System
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters.us_adapter import USAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/us_adapter_demo.log')
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main demo workflow"""
    parser = argparse.ArgumentParser(description='US Adapter Integration Demo')
    parser.add_argument('--polygon-key', type=str, help='Polygon.io API key')
    parser.add_argument('--db-path', type=str, default='data/spock_local.db',
                       help='SQLite database path')
    parser.add_argument('--scan-only', action='store_true',
                       help='Only scan tickers, skip OHLCV collection')
    parser.add_argument('--max-stocks', type=int, default=100,
                       help='Maximum stocks to process (default: 100)')
    parser.add_argument('--days', type=int, default=250,
                       help='Historical days to collect (default: 250)')

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get Polygon API key
    polygon_key = args.polygon_key or os.getenv('POLYGON_API_KEY')
    if not polygon_key:
        logger.error("❌ Polygon API key required. Use --polygon-key or set POLYGON_API_KEY env var")
        sys.exit(1)

    logger.info("=" * 80)
    logger.info("US Adapter Integration Demo")
    logger.info("=" * 80)

    try:
        # Initialize database manager
        logger.info(f"📂 Initializing database: {args.db_path}")
        db_manager = SQLiteDatabaseManager(db_path=args.db_path)

        # Initialize US adapter
        logger.info(f"🚀 Initializing USAdapter (Polygon.io free tier: 5 req/min)")
        us_adapter = USAdapter(db_manager, polygon_api_key=polygon_key)

        # Check market status
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Check US Market Status")
        logger.info("=" * 80)

        market_status = us_adapter.check_market_status()
        logger.info(f"Market Status: {market_status}")

        # Scan US stocks
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Scan US Stocks (NYSE, NASDAQ, AMEX)")
        logger.info("=" * 80)
        logger.info("⏱️ Estimated time: 3-5 minutes (pagination + rate limiting)")

        stocks = us_adapter.scan_stocks(force_refresh=True)
        logger.info(f"✅ Found {len(stocks)} US common stocks")

        # Display sample stocks
        logger.info("\n📊 Sample stocks (first 10):")
        for stock in stocks[:10]:
            logger.info(f"  - {stock['ticker']:6s} | {stock['name'][:40]:40s} | "
                       f"{stock['exchange']:7s} | {stock.get('sector', 'N/A')}")

        # Filter top stocks by market cap or alphabetically
        if args.max_stocks < len(stocks):
            logger.info(f"\n🔍 Limiting to top {args.max_stocks} stocks")
            stocks = stocks[:args.max_stocks]

        if args.scan_only:
            logger.info("\n✅ Scan complete (--scan-only flag set, skipping OHLCV collection)")
            return

        # Collect OHLCV data
        logger.info("\n" + "=" * 80)
        logger.info(f"STEP 3: Collect OHLCV Data ({args.days} days)")
        logger.info("=" * 80)
        logger.info(f"⏱️ Estimated time: {len(stocks) * 12 / 60:.1f} minutes (5 req/min)")

        tickers = [s['ticker'] for s in stocks]
        success_count = us_adapter.collect_stock_ohlcv(tickers=tickers, days=args.days)

        logger.info(f"✅ OHLCV collected for {success_count}/{len(stocks)} stocks")

        # Collect fundamentals for top 50
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Collect Company Fundamentals (Top 50)")
        logger.info("=" * 80)
        logger.info("⏱️ Estimated time: 10 minutes (50 stocks × 12 seconds)")

        top_50 = tickers[:50]
        fundamentals_count = us_adapter.collect_fundamentals(tickers=top_50)

        logger.info(f"✅ Fundamentals collected for {fundamentals_count}/{len(top_50)} stocks")

        # Verify database
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Verify Database Records")
        logger.info("=" * 80)

        db_stocks = db_manager.get_tickers(region='US', asset_type='STOCK')
        logger.info(f"📊 Database: {len(db_stocks)} US stocks")

        # Display sample database records
        logger.info("\n📊 Sample database records (first 5):")
        for stock in db_stocks[:5]:
            logger.info(f"  - {stock['ticker']:6s} | {stock['name'][:40]:40s} | "
                       f"{stock['region']} | {stock.get('sector', 'N/A')}")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ Demo Complete - Summary")
        logger.info("=" * 80)
        logger.info(f"  Total stocks scanned: {len(stocks)}")
        logger.info(f"  OHLCV data collected: {success_count} stocks")
        logger.info(f"  Fundamentals collected: {fundamentals_count} stocks")
        logger.info(f"  Database records: {len(db_stocks)} US stocks")
        logger.info(f"  Database path: {args.db_path}")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
