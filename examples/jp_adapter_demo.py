"""
Japan Market Adapter Demo Script

Demonstrates JPAdapter functionality for Tokyo Stock Exchange (TSE) data collection:
- Stock scanning with yfinance
- OHLCV data collection with technical indicators
- Fundamentals retrieval
- Custom ticker management

Usage:
    python3 examples/jp_adapter_demo.py [--dry-run] [--max-stocks N]

Requirements:
    - SQLite database initialized (spock_local.db)
    - yfinance installed
    - Internet connection for market data

Author: Spock Trading System
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.market_adapters.jp_adapter import JPAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager


def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def demo_stock_scanning(adapter: JPAdapter, max_stocks: int = 10):
    """
    Demo 1: Stock Scanning

    Demonstrates:
    - Fetching Japanese stock data from yfinance
    - Filtering REITs and preferred stocks
    - Saving to database with TSE→GICS sector mapping
    """
    print_section("Demo 1: Japan Stock Scanning")

    print(f"📊 Scanning Japanese stocks (max: {max_stocks})...")
    print(f"   Data source: yfinance (Yahoo Finance)")
    print(f"   Target: Tokyo Stock Exchange (TSE)")
    print(f"   Filter: Common stocks only (exclude REITs)\n")

    try:
        # Scan with limited stock count for demo
        stocks = adapter.scan_stocks(
            force_refresh=True,
            max_count=max_stocks
        )

        if not stocks:
            print("⚠️  No stocks returned from scan")
            return

        print(f"✅ Successfully scanned {len(stocks)} Japanese stocks\n")

        # Display sample results
        print("Sample stocks (first 3):")
        print("-" * 80)
        for i, stock in enumerate(stocks[:3], 1):
            print(f"{i}. {stock['ticker']} - {stock['name']}")
            print(f"   Sector: {stock.get('sector', 'N/A')}")
            print(f"   Industry: {stock.get('industry', 'N/A')}")
            print(f"   Market Cap: ¥{stock.get('market_cap', 0):,.0f}")
            print(f"   Currency: {stock.get('currency', 'N/A')}")
            print()

        # Sector distribution
        sectors = {}
        for stock in stocks:
            sector = stock.get('sector', 'Unknown')
            sectors[sector] = sectors.get(sector, 0) + 1

        print("Sector distribution:")
        for sector, count in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
            print(f"  {sector}: {count} stocks")

    except Exception as e:
        print(f"❌ Stock scanning failed: {e}")


def demo_ohlcv_collection(adapter: JPAdapter, days: int = 30):
    """
    Demo 2: OHLCV Data Collection

    Demonstrates:
    - Fetching historical price data
    - Calculating technical indicators (MA, RSI, MACD, BB, ATR)
    - Saving to database with proper date handling
    """
    print_section("Demo 2: OHLCV Data Collection")

    print(f"📈 Collecting OHLCV data for last {days} days...")
    print(f"   Technical indicators: MA5/20/60/120/200, RSI, MACD, BB, ATR")
    print(f"   Period: {(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')} ~ {datetime.now().strftime('%Y-%m-%d')}\n")

    try:
        # Get tickers from database
        db_tickers = adapter.db.get_tickers(region='JP', asset_type='STOCK', is_active=True)

        if not db_tickers:
            print("⚠️  No Japanese tickers found in database. Run stock scanning first.")
            return

        ticker_list = [t['ticker'] for t in db_tickers[:5]]  # Limit to 5 for demo
        print(f"Target tickers: {', '.join(ticker_list)}\n")

        # Collect OHLCV data
        success_count = adapter.collect_stock_ohlcv(
            tickers=ticker_list,
            days=days
        )

        print(f"\n✅ Successfully collected OHLCV data for {success_count}/{len(ticker_list)} stocks")

        # Display sample data
        if success_count > 0:
            sample_ticker = ticker_list[0]
            print(f"\nSample OHLCV data for {sample_ticker} (last 3 days):")
            print("-" * 80)

            # Query recent data
            query = f"""
                SELECT date, open, high, low, close, volume,
                       ma5, ma20, rsi_14, macd
                FROM ohlcv_data
                WHERE ticker = '{sample_ticker}' AND period_type = 'DAILY'
                ORDER BY date DESC
                LIMIT 3
            """
            result = adapter.db.conn.execute(query).fetchall()

            for row in result:
                print(f"Date: {row[0]}")
                print(f"  OHLCV: O={row[1]:,.0f} H={row[2]:,.0f} L={row[3]:,.0f} C={row[4]:,.0f} V={row[5]:,.0f}")
                ma5_str = f"{row[6]:.2f}" if row[6] else "N/A"
                ma20_str = f"{row[7]:.2f}" if row[7] else "N/A"
                rsi_str = f"{row[8]:.2f}" if row[8] else "N/A"
                macd_str = f"{row[9]:.2f}" if row[9] else "N/A"
                print(f"  MA5={ma5_str} MA20={ma20_str}")
                print(f"  RSI={rsi_str} MACD={macd_str}")
                print()

    except Exception as e:
        print(f"❌ OHLCV collection failed: {e}")


def demo_fundamentals_collection(adapter: JPAdapter):
    """
    Demo 3: Fundamentals Collection

    Demonstrates:
    - Fetching fundamental data (P/E, P/B, dividend yield)
    - Market cap and valuation metrics
    - Saving to database for analysis
    """
    print_section("Demo 3: Fundamentals Collection")

    print("💰 Collecting fundamental data...")
    print("   Metrics: Market cap, P/E, P/B, dividend yield, EPS, ROE\n")

    try:
        # Get tickers from database
        db_tickers = adapter.db.get_tickers(region='JP', asset_type='STOCK', is_active=True)

        if not db_tickers:
            print("⚠️  No Japanese tickers found in database. Run stock scanning first.")
            return

        ticker_list = [t['ticker'] for t in db_tickers[:5]]  # Limit to 5 for demo
        print(f"Target tickers: {', '.join(ticker_list)}\n")

        # Collect fundamentals
        success_count = adapter.collect_fundamentals(tickers=ticker_list)

        print(f"\n✅ Successfully collected fundamentals for {success_count}/{len(ticker_list)} stocks")

        # Display sample data
        if success_count > 0:
            print(f"\nSample fundamental data:")
            print("-" * 80)

            for ticker in ticker_list[:3]:
                query = f"""
                    SELECT ticker, market_cap, pe_ratio, pb_ratio,
                           dividend_yield, eps, roe, close_price
                    FROM ticker_fundamentals
                    WHERE ticker = '{ticker}'
                    ORDER BY date DESC
                    LIMIT 1
                """
                result = adapter.db.conn.execute(query).fetchone()

                if result:
                    ticker_info = adapter.db.get_tickers(ticker=ticker)[0]
                    print(f"{result[0]} - {ticker_info['name']}")
                    print(f"  Market Cap: ¥{result[1]:,.0f}" if result[1] else "  Market Cap: N/A")
                    print(f"  P/E Ratio: {result[2]:.2f}" if result[2] else "  P/E Ratio: N/A")
                    print(f"  P/B Ratio: {result[3]:.2f}" if result[3] else "  P/B Ratio: N/A")
                    print(f"  Dividend Yield: {result[4]*100:.2f}%" if result[4] else "  Dividend Yield: N/A")
                    print(f"  EPS: ¥{result[5]:.2f}" if result[5] else "  EPS: N/A")
                    print(f"  ROE: {result[6]*100:.2f}%" if result[6] else "  ROE: N/A")
                    print(f"  Current Price: ¥{result[7]:,.2f}" if result[7] else "  Current Price: N/A")
                    print()

    except Exception as e:
        print(f"❌ Fundamentals collection failed: {e}")


def demo_custom_ticker(adapter: JPAdapter, ticker: str = "7974"):
    """
    Demo 4: Custom Ticker Management

    Demonstrates:
    - Adding custom tickers (e.g., Nintendo: 7974)
    - Fetching and validating ticker info
    - Database integration
    """
    print_section("Demo 4: Custom Ticker Management")

    print(f"➕ Adding custom ticker: {ticker}")
    print(f"   Example: 7974 (Nintendo Co., Ltd.)\n")

    try:
        success = adapter.add_custom_ticker(ticker)

        if success:
            print(f"✅ Successfully added {ticker} to database")

            # Display ticker info
            ticker_info = adapter.db.get_tickers(ticker=ticker)
            if ticker_info:
                info = ticker_info[0]
                print(f"\nTicker details:")
                print(f"  Name: {info.get('name', 'N/A')}")
                print(f"  Sector: {info.get('sector', 'N/A')}")
                print(f"  Industry: {info.get('industry', 'N/A')}")
                print(f"  Currency: {info.get('currency', 'N/A')}")
                print(f"  Exchange: {info.get('exchange', 'N/A')}")
        else:
            print(f"❌ Failed to add {ticker}")

    except Exception as e:
        print(f"❌ Custom ticker addition failed: {e}")


def demo_database_stats(db: SQLiteDatabaseManager):
    """
    Demo 5: Database Statistics

    Demonstrates:
    - Querying database for JP stocks
    - Counting tickers and data points
    - Showing data coverage
    """
    print_section("Demo 5: Database Statistics")

    try:
        # Count JP stocks
        jp_stocks = db.get_tickers(region='JP', asset_type='STOCK', is_active=True)
        print(f"📊 Japan Market Data Summary:")
        print(f"   Total stocks in database: {len(jp_stocks)}")

        if jp_stocks:
            # Count OHLCV records
            query = """
                SELECT COUNT(*)
                FROM ohlcv_data
                WHERE ticker IN (SELECT ticker FROM tickers WHERE region = 'JP')
            """
            ohlcv_count = db.conn.execute(query).fetchone()[0]
            print(f"   OHLCV data points: {ohlcv_count:,}")

            # Count fundamentals
            query = """
                SELECT COUNT(*)
                FROM ticker_fundamentals
                WHERE ticker IN (SELECT ticker FROM tickers WHERE region = 'JP')
            """
            fundamentals_count = db.conn.execute(query).fetchone()[0]
            print(f"   Fundamental records: {fundamentals_count}")

            # Sector breakdown
            sectors = {}
            for stock in jp_stocks:
                sector = stock.get('sector', 'Unknown')
                sectors[sector] = sectors.get(sector, 0) + 1

            print(f"\n   Sector breakdown:")
            for sector, count in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
                print(f"     {sector}: {count} stocks")

    except Exception as e:
        print(f"❌ Database stats query failed: {e}")


def main():
    """Main demo execution"""
    parser = argparse.ArgumentParser(description='Japan Market Adapter Demo')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without making database changes')
    parser.add_argument('--max-stocks', type=int, default=10,
                       help='Maximum stocks to scan (default: 10)')
    parser.add_argument('--days', type=int, default=30,
                       help='Days of OHLCV data to collect (default: 30)')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("  Japan Market Adapter Demo - Tokyo Stock Exchange (TSE)")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Database: data/spock_local.db")
    print(f"  Data Source: yfinance (Yahoo Finance)")
    print(f"  Market: Tokyo Stock Exchange (TSE)")
    print(f"  Max Stocks: {args.max_stocks}")
    print(f"  OHLCV Days: {args.days}")
    print(f"  Dry Run: {'Yes' if args.dry_run else 'No'}")

    try:
        # Initialize database connection
        db = SQLiteDatabaseManager()
        adapter = JPAdapter(db)

        if args.dry_run:
            print("\n⚠️  DRY RUN MODE - No database changes will be made")
            print("   (Some demos may be skipped)")
            return

        # Run demos
        demo_stock_scanning(adapter, max_stocks=args.max_stocks)
        demo_ohlcv_collection(adapter, days=args.days)
        demo_fundamentals_collection(adapter)
        demo_custom_ticker(adapter, ticker="7974")  # Nintendo
        demo_database_stats(db)

        # Final summary
        print_section("Demo Complete")
        print("✅ All demos completed successfully!")
        print("\nNext steps:")
        print("  1. Review database: sqlite3 data/spock_local.db")
        print("  2. Check logs for detailed operations")
        print("  3. Adjust parameters and re-run as needed")
        print("  4. Integrate with trading strategies\n")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
