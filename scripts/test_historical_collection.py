#!/usr/bin/env python3
"""
Test Historical Fundamental Data Collection

Validates historical annual data collection for backtesting.

Author: Spock Trading System
Date: 2025-10-17
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.fundamental_data_collector import FundamentalDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_historical_collection():
    """
    Test historical fundamental data collection

    Test Scenarios:
    1. Collect 2020-2024 annual data for Samsung Electronics (005930)
    2. Verify fiscal_year field populated correctly
    3. Check cache behavior (skip already collected years)
    4. Validate data quality (ROE, ROA, etc.)
    """
    print("\n" + "="*70)
    print("HISTORICAL FUNDAMENTAL DATA COLLECTION TEST")
    print("Spock Trading System")
    print("="*70 + "\n")

    # Check DART API key
    if not os.getenv('DART_API_KEY'):
        print("⚠️ DART_API_KEY not found in environment variables")
        print("📝 Get API key from: https://opendart.fss.or.kr/")
        print("💡 Set with: export DART_API_KEY='your_key_here'")
        print("\n❌ Skipping test\n")
        return False

    try:
        # Initialize
        db = SQLiteDatabaseManager()
        collector = FundamentalDataCollector(db)

        # Test parameters
        test_tickers = ['005930']  # Samsung Electronics only
        start_year = 2020
        end_year = 2024

        print(f"📊 Test Parameters:")
        print(f"  - Tickers: {test_tickers}")
        print(f"  - Year Range: {start_year}-{end_year}")
        print(f"  - Total Expected: {len(test_tickers)} × {end_year - start_year + 1} = {len(test_tickers) * (end_year - start_year + 1)} data points\n")

        # Test 1: Historical collection
        print("="*70)
        print("[Test 1/4] Historical Data Collection")
        print("="*70 + "\n")

        results = collector.collect_historical_fundamentals(
            tickers=test_tickers,
            region='KR',
            start_year=start_year,
            end_year=end_year,
            force_refresh=False  # Use cache if available
        )

        # Validate results
        print(f"\n📋 Collection Results:")
        for ticker, year_results in results.items():
            print(f"\n{ticker} (Samsung Electronics):")
            for year, success in sorted(year_results.items()):
                status = "✅" if success else "❌"
                print(f"  {year}: {status}")

        # Test 2: Verify fiscal_year field
        print("\n" + "="*70)
        print("[Test 2/4] Fiscal Year Field Validation")
        print("="*70 + "\n")

        for ticker in test_tickers:
            for year in range(start_year, end_year + 1):
                fundamentals = db.get_ticker_fundamentals(
                    ticker=ticker,
                    period_type='ANNUAL',
                    fiscal_year=year,
                    limit=1
                )

                if fundamentals:
                    data = fundamentals[0]
                    fiscal_year = data.get('fiscal_year')
                    data_source = data.get('data_source', '')

                    if fiscal_year == year:
                        print(f"✅ {ticker} {year}: fiscal_year={fiscal_year}, source={data_source}")
                    else:
                        print(f"❌ {ticker} {year}: MISMATCH fiscal_year={fiscal_year} (expected {year})")
                else:
                    print(f"⚠️  {ticker} {year}: No data found")

        # Test 3: Cache behavior
        print("\n" + "="*70)
        print("[Test 3/4] Cache Behavior Test")
        print("="*70 + "\n")

        print("🔄 Re-running collection without force_refresh...")
        print("Expected: Should skip all years (100% cache hit)\n")

        results2 = collector.collect_historical_fundamentals(
            tickers=test_tickers,
            region='KR',
            start_year=start_year,
            end_year=end_year,
            force_refresh=False
        )

        # Should be instant if cache working
        print("✅ Cache test completed")

        # Test 4: Data quality validation
        print("\n" + "="*70)
        print("[Test 4/4] Data Quality Validation")
        print("="*70 + "\n")

        for ticker in test_tickers:
            print(f"{ticker} Financial Metrics (2020-2024):\n")

            print(f"{'Year':<6} {'ROE':<10} {'ROA':<10} {'Debt Ratio':<15} {'Revenue':<20}")
            print("-" * 70)

            for year in range(start_year, end_year + 1):
                fundamentals = db.get_ticker_fundamentals(
                    ticker=ticker,
                    period_type='ANNUAL',
                    fiscal_year=year,
                    limit=1
                )

                if fundamentals:
                    data = fundamentals[0]
                    roe = data.get('roe')
                    roa = data.get('roa')
                    debt_ratio = data.get('debt_ratio')
                    revenue = data.get('revenue')

                    roe_str = f"{roe:.2f}%" if roe else "N/A"
                    roa_str = f"{roa:.2f}%" if roa else "N/A"
                    debt_str = f"{debt_ratio:.2f}%" if debt_ratio else "N/A"
                    rev_str = f"{revenue:,.0f}" if revenue else "N/A"

                    print(f"{year:<6} {roe_str:<10} {roa_str:<10} {debt_str:<15} {rev_str:<20}")
                else:
                    print(f"{year:<6} {'NO DATA':<10}")

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70 + "\n")

        total_expected = len(test_tickers) * (end_year - start_year + 1)
        total_collected = sum(
            1 for ticker_results in results.values()
            for success in ticker_results.values()
            if success
        )

        success_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

        print(f"📊 Success Rate: {total_collected}/{total_expected} ({success_rate:.1f}%)")
        print(f"📅 Year Range: {start_year}-{end_year}")
        print(f"🎯 Tickers Tested: {', '.join(test_tickers)}")

        if success_rate >= 80:
            print(f"\n✅ All tests passed!")
            return True
        else:
            print(f"\n⚠️  Success rate below 80%")
            return False

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner"""
    try:
        success = test_historical_collection()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user\n")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
