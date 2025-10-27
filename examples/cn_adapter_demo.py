#!/usr/bin/env python3
"""
China Market Adapter Demo

Demonstrates CNAdapter usage with hybrid fallback strategy:
1. Stock scanning (SSE + SZSE)
2. OHLCV data collection (AkShare → yfinance fallback)
3. Fundamentals collection
4. Database verification
5. Fallback statistics

Usage:
    python3 examples/cn_adapter_demo.py --max-stocks 50
    python3 examples/cn_adapter_demo.py --ticker 600519 000001
    python3 examples/cn_adapter_demo.py --force-fallback

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
from modules.market_adapters.cn_adapter import CNAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_cn_demo.log')
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main demo workflow"""
    parser = argparse.ArgumentParser(description='China Market Adapter Demo')
    parser.add_argument('--max-stocks', type=int, default=50,
                       help='Max number of stocks to process (default: 50)')
    parser.add_argument('--ticker', nargs='+',
                       help='Specific tickers to process (e.g., 600519 000001)')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh ticker data (ignore cache)')
    parser.add_argument('--skip-ohlcv', action='store_true',
                       help='Skip OHLCV collection (scanning only)')
    parser.add_argument('--days', type=int, default=250,
                       help='OHLCV days to collect (default: 250)')
    parser.add_argument('--force-fallback', action='store_true',
                       help='Force yfinance fallback (test fallback logic)')
    parser.add_argument('--no-fallback', action='store_true',
                       help='Disable yfinance fallback (AkShare only)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("China Market Adapter Demo")
    logger.info("Hybrid Strategy: AkShare (primary) + yfinance (fallback)")
    logger.info("=" * 60)

    # ========================================
    # Step 1: Initialize Database and Adapter
    # ========================================
    logger.info("\n📊 Step 1: Initializing database and adapter...")

    try:
        db = SQLiteDatabaseManager(db_path='data/spock_local.db')
        adapter = CNAdapter(db, enable_fallback=not args.no_fallback)
        logger.info("✅ Database and adapter initialized")

        if args.no_fallback:
            logger.info("⚠️ yfinance fallback disabled (AkShare only)")

    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        return 1

    # ========================================
    # Step 2: Scan Chinese Stocks
    # ========================================
    logger.info("\n📊 Step 2: Scanning Chinese stocks...")

    try:
        if args.ticker:
            # Scan specific tickers
            logger.info(f"📈 Scanning custom tickers: {args.ticker}")
            count = adapter.add_custom_tickers(args.ticker)
            stocks = db.get_tickers(region='CN', asset_type='STOCK', is_active=True)
            stocks = [s for s in stocks if s['ticker'] in args.ticker]
        else:
            # Scan from AkShare stock list
            logger.info(f"📈 Scanning up to {args.max_stocks} stocks from AkShare...")
            stocks = adapter.scan_stocks(
                force_refresh=args.force_refresh,
                max_count=args.max_stocks
            )

        if not stocks:
            logger.warning("⚠️ No stocks found")
            return 1

        logger.info(f"✅ Scanned {len(stocks)} stocks")

        # Display sample stocks
        logger.info("\n📋 Sample stocks:")
        for i, stock in enumerate(stocks[:5], 1):
            exchange = stock.get('exchange', 'N/A')
            market_cap = stock.get('market_cap', 0)
            mc_str = f"{market_cap/1e8:.0f}亿" if market_cap else "N/A"
            logger.info(f"  {i}. {stock['ticker']:6s} | {exchange:4s} | {stock['name'][:15]:15s} | {mc_str}")

    except Exception as e:
        logger.error(f"❌ Stock scanning failed: {e}")
        return 1

    # ========================================
    # Step 3: Collect OHLCV Data
    # ========================================
    if not args.skip_ohlcv:
        logger.info(f"\n📊 Step 3: Collecting OHLCV data ({args.days} days)...")
        logger.info("Strategy: AkShare primary + yfinance fallback")

        try:
            ticker_list = [s['ticker'] for s in stocks]

            # Test fallback by disabling AkShare temporarily
            if args.force_fallback:
                logger.warning("⚠️ --force-fallback enabled: Simulating AkShare failures")
                adapter.akshare_api.get_stock_daily_ohlcv = lambda *args, **kwargs: None

            success_count = adapter.collect_stock_ohlcv(
                tickers=ticker_list,
                days=args.days,
                use_fallback=not args.no_fallback
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
    logger.info("Data: CSRC industry → GICS sector mapping")

    try:
        ticker_list = [s['ticker'] for s in stocks]

        success_count = adapter.collect_fundamentals(
            tickers=ticker_list,
            use_fallback=not args.no_fallback
        )

        logger.info(f"✅ Fundamentals collected for {success_count}/{len(ticker_list)} stocks")

    except Exception as e:
        logger.error(f"❌ Fundamentals collection failed: {e}")

    # ========================================
    # Step 5: Verify Database
    # ========================================
    logger.info("\n📊 Step 5: Verifying database...")

    try:
        # Check tickers table
        db_tickers = db.get_tickers(region='CN', asset_type='STOCK', is_active=True)
        logger.info(f"✅ Tickers in database: {len(db_tickers)}")

        # Check OHLCV data (sample one ticker)
        if not args.skip_ohlcv and stocks:
            sample_ticker = stocks[0]['ticker']
            ohlcv_data = db.get_ohlcv_data(ticker=sample_ticker, days=30)

            if ohlcv_data:
                logger.info(f"✅ OHLCV data for {sample_ticker}: {len(ohlcv_data)} days")
                logger.info(f"   Latest: {ohlcv_data[0]['date']} | Close: {ohlcv_data[0]['close']:.2f} CNY")
            else:
                logger.warning(f"⚠️ No OHLCV data for {sample_ticker}")

        # Display sample ticker data
        if db_tickers:
            logger.info("\n📋 Sample ticker data (with exchange):")
            for i, ticker in enumerate(db_tickers[:3], 1):
                exchange = ticker.get('exchange', 'N/A')
                logger.info(f"  {i}. {ticker['ticker']:6s} | {exchange:4s} | {ticker['name'][:20]:20s}")
                logger.info(f"     Region: {ticker['region']} | Currency: {ticker['currency']}")

    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")

    # ========================================
    # Step 6: Fallback Statistics
    # ========================================
    logger.info("\n📊 Step 6: Fallback statistics...")

    try:
        stats = adapter.get_fallback_stats()
        logger.info(f"✅ Fallback enabled: {stats['fallback_enabled']}")
        logger.info(f"✅ Fallback available: {stats['fallback_available']}")

        if args.force_fallback:
            logger.info("⚠️ Force fallback mode was enabled for testing")

    except Exception as e:
        logger.error(f"❌ Failed to get fallback stats: {e}")

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

    logger.info(f"✅ Data source: AkShare (primary) + yfinance (fallback: {not args.no_fallback})")

    logger.info("\n💡 Next steps:")
    logger.info("   1. Run technical analysis: python3 modules/stock_technical_filter.py --region CN")
    logger.info("   2. Check database: python3 -c \"from modules.db_manager_sqlite import SQLiteDatabaseManager; db = SQLiteDatabaseManager(); print(db.get_tickers(region='CN'))\"")
    logger.info("   3. Test fallback: python3 examples/cn_adapter_demo.py --force-fallback --ticker 600519")
    logger.info("   4. Add famous stocks: python3 examples/cn_adapter_demo.py --ticker 600519 000858 000001")

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
