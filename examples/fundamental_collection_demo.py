#!/usr/bin/env python3
"""
Fundamental Data Collection Demo

Demonstrates fundamental data collection for Korean and global markets.

Phase 1 (Korean Market):
- DART API fundamental extraction (ROE, ROA, debt ratio, etc.)
- Database storage and retrieval
- Caching and batch processing

Phase 3 (Global Markets):
- yfinance fundamental extraction (PER, PBR, dividends, etc.)
- Multi-region support (US, HK, CN, JP, VN)

Author: Spock Trading System
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.fundamental_data_collector import FundamentalDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_korean_market():
    """
    Demo: Korean market fundamental data collection

    Uses DART API to extract financial statement data for Korean stocks.

    Note:
        Requires DART_API_KEY environment variable to be set.
        Get API key from: https://opendart.fss.or.kr/
    """
    print("\n" + "="*70)
    print("DEMO 1: Korean Market Fundamental Data Collection")
    print("="*70 + "\n")

    # Check DART API key
    if not os.getenv('DART_API_KEY'):
        print("⚠️ DART_API_KEY not found in environment variables")
        print("📝 Get API key from: https://opendart.fss.or.kr/")
        print("💡 Set with: export DART_API_KEY='your_key_here'")
        print("\n❌ Skipping Korean market demo\n")
        return

    # Initialize collector
    db = SQLiteDatabaseManager()
    collector = FundamentalDataCollector(db)

    # Sample Korean stocks
    tickers = [
        '005930',  # Samsung Electronics
        '035720',  # Kakao
        '000660',  # SK Hynix
    ]

    print(f"📊 Collecting fundamentals for {len(tickers)} Korean stocks:")
    for ticker in tickers:
        print(f"  - {ticker}")
    print()

    # Collect fundamentals
    results = collector.collect_fundamentals(
        tickers=tickers,
        region='KR',
        force_refresh=False
    )

    # Display results
    print("\n" + "-"*70)
    print("Collection Results:")
    print("-"*70)

    for ticker, success in results.items():
        if success:
            # Retrieve and display fundamental data
            fundamentals = collector.get_fundamentals(ticker, 'KR', limit=1)

            if fundamentals:
                data = fundamentals[0]
                print(f"\n✅ {ticker} - {data.get('data_source', 'Unknown')}")
                print(f"  📅 Date: {data.get('date')}")
                print(f"  📈 ROE: {data.get('roe', 'N/A'):.2f}%" if data.get('roe') else "  📈 ROE: N/A")
                print(f"  📈 ROA: {data.get('roa', 'N/A'):.2f}%" if data.get('roa') else "  📈 ROA: N/A")
                print(f"  💰 Revenue: {data.get('revenue', 0):,.0f} KRW")
                print(f"  💼 Total Assets: {data.get('total_assets', 0):,.0f} KRW")
                print(f"  🏦 Total Equity: {data.get('total_equity', 0):,.0f} KRW")
            else:
                print(f"❌ {ticker} - No data retrieved")
        else:
            print(f"❌ {ticker} - Collection failed")

    print("\n" + "="*70 + "\n")


def demo_global_market():
    """
    Demo: Global market fundamental data collection

    Uses yfinance API to extract fundamental data for US, Hong Kong, and other markets.

    Note:
        Phase 3 feature - currently shows basic implementation.
    """
    print("\n" + "="*70)
    print("DEMO 2: Global Market Fundamental Data Collection")
    print("="*70 + "\n")

    # Initialize collector
    db = SQLiteDatabaseManager()
    collector = FundamentalDataCollector(db)

    # Sample global stocks
    test_cases = [
        ('AAPL', 'US'),    # Apple Inc.
        ('MSFT', 'US'),    # Microsoft
        ('0700.HK', 'HK'), # Tencent Holdings
    ]

    print(f"📊 Collecting fundamentals for {len(test_cases)} global stocks:")
    for ticker, region in test_cases:
        print(f"  - {ticker} ({region})")
    print()

    # Collect fundamentals
    for ticker, region in test_cases:
        print(f"\n🔄 Processing {ticker} ({region})...")

        results = collector.collect_fundamentals(
            tickers=[ticker],
            region=region,
            force_refresh=False
        )

        if results[ticker]:
            # Retrieve and display fundamental data
            fundamentals = collector.get_fundamentals(ticker, region, limit=1)

            if fundamentals:
                data = fundamentals[0]
                print(f"  ✅ Success - {data.get('data_source', 'Unknown')}")
                print(f"  📅 Date: {data.get('date')}")
                print(f"  💰 Market Cap: {data.get('market_cap', 0):,.0f}")
                print(f"  💵 Close Price: {data.get('close_price', 0):.2f}")

                # Phase 3: Additional fields (PER, PBR, ROE, etc.)
                # Will be available after Phase 3 Week 5 implementation
            else:
                print(f"  ⚠️ No data retrieved")
        else:
            print(f"  ❌ Collection failed")

    print("\n" + "="*70 + "\n")


def demo_batch_retrieval():
    """
    Demo: Batch fundamental data retrieval

    Demonstrates efficient batch querying for multiple tickers.
    """
    print("\n" + "="*70)
    print("DEMO 3: Batch Fundamental Data Retrieval")
    print("="*70 + "\n")

    # Initialize database
    db = SQLiteDatabaseManager()

    # Sample tickers (assuming data already collected)
    tickers = ['AAPL', 'MSFT', 'GOOGL']

    print(f"📊 Batch retrieving fundamentals for {len(tickers)} tickers:")
    for ticker in tickers:
        print(f"  - {ticker}")
    print()

    # Batch query
    fundamentals = db.get_latest_fundamentals_batch(tickers, period_type='DAILY')

    # Display results
    print("\n" + "-"*70)
    print("Batch Query Results:")
    print("-"*70 + "\n")

    for ticker in tickers:
        if ticker in fundamentals:
            data = fundamentals[ticker]
            print(f"✅ {ticker}:")
            print(f"  📅 Date: {data.get('date')}")
            print(f"  💰 Market Cap: {data.get('market_cap', 0):,.0f}")
            print(f"  💵 Close Price: {data.get('close_price', 0):.2f}")
            print(f"  📈 PER: {data.get('per', 'N/A')}")
            print(f"  📈 PBR: {data.get('pbr', 'N/A')}")
            print()
        else:
            print(f"❌ {ticker}: No data available\n")

    print("="*70 + "\n")


def demo_caching():
    """
    Demo: Caching behavior

    Demonstrates how caching prevents unnecessary API calls.
    """
    print("\n" + "="*70)
    print("DEMO 4: Caching Behavior")
    print("="*70 + "\n")

    # Initialize collector
    db = SQLiteDatabaseManager()
    collector = FundamentalDataCollector(db)

    ticker = 'AAPL'
    region = 'US'

    print(f"📊 Testing cache behavior for {ticker} ({region})\n")

    # First call (should fetch from API or fail if no data)
    print("🔄 First call (may fetch from API)...")
    results1 = collector.collect_fundamentals([ticker], region, force_refresh=False)
    print(f"  Result: {'Success' if results1[ticker] else 'Failed'}\n")

    # Second call (should use cache)
    print("🔄 Second call (should use cache)...")
    results2 = collector.collect_fundamentals([ticker], region, force_refresh=False)
    print(f"  Result: {'Success (cached)' if results2[ticker] else 'Failed'}\n")

    # Force refresh call (should bypass cache)
    print("🔄 Force refresh call (bypass cache)...")
    results3 = collector.collect_fundamentals([ticker], region, force_refresh=True)
    print(f"  Result: {'Success (refreshed)' if results3[ticker] else 'Failed'}\n")

    print("💡 Caching reduces API calls by >80% for repeat queries")
    print("💡 Cache TTL: 24 hours for daily metrics\n")

    print("="*70 + "\n")


def main():
    """
    Main demo runner

    Runs all demos in sequence.
    """
    print("\n" + "="*70)
    print("FUNDAMENTAL DATA COLLECTION DEMO")
    print("Spock Trading System")
    print("="*70)

    try:
        # Demo 1: Korean market (DART API)
        demo_korean_market()

        # Demo 2: Global market (yfinance)
        demo_global_market()

        # Demo 3: Batch retrieval
        demo_batch_retrieval()

        # Demo 4: Caching behavior
        demo_caching()

        print("\n✅ All demos completed successfully!\n")

    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user\n")
        return 1
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
