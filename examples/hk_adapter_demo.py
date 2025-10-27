#!/usr/bin/env python3
"""
Hong Kong Market Adapter Demo

Demonstrates HKAdapter usage for:
1. Stock scanning (Hang Seng constituents + H-shares)
2. OHLCV data collection
3. Fundamentals collection
4. Database verification

Usage:
    python3 examples/hk_adapter_demo.py --max-stocks 10
    python3 examples/hk_adapter_demo.py --ticker 0700 0941 9988
    python3 examples/hk_adapter_demo.py --force-refresh

Author: Spock Trading System
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/13ruce/spock')

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters.hk_adapter import HKAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_hk_demo.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main demo workflow"""
    parser = argparse.ArgumentParser(description='Hong Kong Market Adapter Demo')
    parser.add_argument('--max-stocks', type=int, default=30,
                       help='Max number of stocks to process (default: 30)')
    parser.add_argument('--ticker', nargs='+',
                       help='Specific tickers to process (e.g., 0700 0941)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh ticker data (ignore cache)')
    parser.add_argument('--skip-ohlcv', action='store_true',
                       help='Skip OHLCV collection (scanning only)')
    parser.add_argument('--days', type=int, default=250,
                       help='OHLCV days to collect (default: 250)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Hong Kong Market Adapter Demo")
    logger.info("=" * 60)

    # ========================================
    # Step 1: Initialize Database and Adapter
    # ========================================
    logger.info("\n📊 Step 1: Initializing database and adapter...")

    try:
        db = SQLiteDatabaseManager(db_path='data/spock_local.db')
        adapter = HKAdapter(db)
        logger.info("✅ Database and adapter initialized")
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        return 1

    # ========================================
    # Step 2: Scan Hong Kong Stocks
    # ========================================
    logger.info("\n📊 Step 2: Scanning Hong Kong stocks...")

    try:
        if args.ticker:
            # Scan specific tickers
            logger.info(f"📈 Scanning custom tickers: {args.ticker}")
            stocks = adapter.scan_stocks(
                force_refresh=True,
                ticker_list=args.ticker
            )
        else:
            # Scan default ticker list
            ticker_list = adapter.DEFAULT_HK_TICKERS[:args.max_stocks]
            logger.info(f"📈 Scanning {len(ticker_list)} default tickers...")
            stocks = adapter.scan_stocks(
                force_refresh=args.force_refresh,
                ticker_list=ticker_list
            )

        if not stocks:
            logger.warning("⚠️ No stocks found")
            return 1

        logger.info(f"✅ Scanned {len(stocks)} stocks")

        # Display sample stocks
        logger.info("\n📋 Sample stocks:")
        for i, stock in enumerate(stocks[:5], 1):
            logger.info(f"  {i}. {stock['ticker']:6s} - {stock['name'][:30]:30s} | {stock['sector']}")

    except Exception as e:
        logger.error(f"❌ Stock scanning failed: {e}")
        return 1

    # ========================================
    # Step 3: Collect OHLCV Data
    # ========================================
    if not args.skip_ohlcv:
        logger.info(f"\n📊 Step 3: Collecting OHLCV data ({args.days} days)...")

        try:
            ticker_list = [s['ticker'] for s in stocks]
            success_count = adapter.collect_stock_ohlcv(
                tickers=ticker_list,
                days=args.days
            )

            logger.info(f"✅ OHLCV collected for {success_count}/{len(ticker_list)} stocks")

        except Exception as e:
            logger.error(f"❌ OHLCV collection failed: {e}")
            # Continue to next step even if OHLCV fails

    else:
        logger.info("\n⏭️  Step 3: Skipping OHLCV collection (--skip-ohlcv)")

    # ========================================
    # Step 4: Collect Fundamentals
    # ========================================
    logger.info("\n📊 Step 4: Collecting fundamentals...")

    try:
        ticker_list = [s['ticker'] for s in stocks]
        success_count = adapter.collect_fundamentals(tickers=ticker_list)

        logger.info(f"✅ Fundamentals collected for {success_count}/{len(ticker_list)} stocks")

    except Exception as e:
        logger.error(f"❌ Fundamentals collection failed: {e}")

    # ========================================
    # Step 5: Verify Database
    # ========================================
    logger.info("\n📊 Step 5: Verifying database...")

    try:
        # Check tickers table
        db_tickers = db.get_tickers(region='HK', asset_type='STOCK', is_active=True)
        logger.info(f"✅ Tickers in database: {len(db_tickers)}")

        # Check OHLCV data (sample one ticker)
        if not args.skip_ohlcv and stocks:
            sample_ticker = stocks[0]['ticker']
            ohlcv_data = db.get_ohlcv_data(ticker=sample_ticker, days=30)

            if ohlcv_data:
                logger.info(f"✅ OHLCV data for {sample_ticker}: {len(ohlcv_data)} days")
                logger.info(f"   Latest: {ohlcv_data[0]['date']} | Close: {ohlcv_data[0]['close']:.2f} HKD")
            else:
                logger.warning(f"⚠️ No OHLCV data for {sample_ticker}")

        # Display sample ticker data
        if db_tickers:
            logger.info("\n📋 Sample ticker data:")
            for i, ticker in enumerate(db_tickers[:3], 1):
                logger.info(f"  {i}. {ticker['ticker']:6s} - {ticker['name'][:30]:30s}")
                logger.info(f"     Exchange: {ticker['exchange']} | Region: {ticker['region']} | Currency: {ticker['currency']}")

    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")

    # ========================================
    # Summary
    # ========================================
    logger.info("\n" + "=" * 60)
    logger.info("Demo Complete!")
    logger.info("=" * 60)
    logger.info(f"✅ Stocks scanned: {len(stocks)}")
    logger.info(f"✅ Tickers in DB: {len(db_tickers)}")

    if not args.skip_ohlcv:
        logger.info(f"✅ OHLCV collected: {args.days} days")

    logger.info("\n💡 Next steps:")
    logger.info("   1. Run technical analysis: python3 modules/stock_technical_filter.py --region HK")
    logger.info("   2. Check database: python3 -c \"from modules.db_manager_sqlite import SQLiteDatabaseManager; db = SQLiteDatabaseManager(); print(db.get_tickers(region='HK'))\"")
    logger.info("   3. Add more tickers: python3 examples/hk_adapter_demo.py --ticker 1810 9618")

    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n⚠️ Demo interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
