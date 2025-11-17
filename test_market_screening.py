#!/usr/bin/env python3
"""
Market Screening Validation Test
Tests screening functionality for HK, JP, CN, VN markets
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp_server.adapters.screening_adapter import ScreeningAdapter
from modules.screening.etf_screening_adapter import ETFScreeningAdapter
from mcp_server.config import Config


def print_section(title):
    """Print section header"""
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80)


def print_results(results, test_name):
    """Print test results"""
    print(f"\n{test_name}")
    print("-" * 80)

    if results.get("success"):
        print(f"✅ SUCCESS")
        print(f"Region: {results.get('region')}")
        print(f"Total Matching: {results.get('total_matching', 0)}")
        print(f"Returned: {results.get('count', 0)}")

        if results.get('stocks'):
            print(f"\nSample Results (top 3):")
            for i, stock in enumerate(results['stocks'][:3], 1):
                print(f"  {i}. {stock.get('ticker')} - {stock.get('name')}")
                if stock.get('per'):
                    print(f"     P/E: {stock['per']:.2f}")
                if stock.get('pbr'):
                    print(f"     P/B: {stock['pbr']:.2f}")
                if stock.get('dividend_yield'):
                    print(f"     Div Yield: {stock['dividend_yield']:.2f}%")
                if stock.get('rsi'):
                    print(f"     RSI: {stock['rsi']:.2f}")
                if stock.get('ma_trend'):
                    print(f"     MA Trend: {stock['ma_trend']}")

        return True
    else:
        print(f"❌ FAILED: {results}")
        return False


async def test_hk_fundamental_screening(adapter):
    """Test 1: HK Market Fundamental Screening"""
    print_section("Test 1: HK Market Fundamental Screening")

    try:
        result = await adapter.screen_stocks(
            region="HK",
            filters={
                "per_max": 15,
                "pbr_max": 2,
                "dividend_yield_min": 3.0
            },
            limit=10
        )
        return print_results(result, "HK Fundamental Screening (P/E < 15, P/B < 2, Div > 3%)")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_jp_technical_screening(adapter):
    """Test 2: JP Market Technical Screening"""
    print_section("Test 2: JP Market Technical Screening")

    try:
        result = await adapter.screen_stocks(
            region="JP",
            filters={
                "per_max": 20
            },
            technical_filters={
                "rsi_max": 30,
                "ma_trend": "bullish"
            },
            limit=10
        )
        return print_results(result, "JP Technical Screening (P/E < 20, RSI < 30, Bullish MA)")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cn_etf_screening(etf_adapter):
    """Test 3: CN Market ETF Screening"""
    print_section("Test 3: CN Market ETF Screening")

    try:
        result = await etf_adapter.screen_etfs(
            region="CN",
            filters={
                "name_pattern": "科技"  # Technology ETFs
            },
            limit=5
        )

        print(f"\nCN ETF Screening (Name: 科技)")
        print("-" * 80)

        if result.get("success"):
            print(f"✅ SUCCESS")
            print(f"Region: {result.get('region')}")
            print(f"Total Matching: {result.get('total_matching', 0)}")
            print(f"Returned: {result.get('count', 0)}")

            if result.get('etfs'):
                print(f"\nResults:")
                for i, etf in enumerate(result['etfs'], 1):
                    print(f"  {i}. {etf.get('ticker')} - {etf.get('name')}")
                    if etf.get('listing_date'):
                        print(f"     Listing: {etf['listing_date']}")

            return True
        else:
            print(f"❌ FAILED: {result}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vn_full_screening(adapter):
    """Test 4: VN Market Full Screening"""
    print_section("Test 4: VN Market Full Screening")

    try:
        result = await adapter.screen_stocks(
            region="VN",
            filters={
                "per_max": 50  # Broader filter for VN market
            },
            limit=10
        )
        return print_results(result, "VN Full Screening (P/E < 50)")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 80)
    print("MARKET SCREENING VALIDATION TEST")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Markets: HK, JP, CN, VN")
    print()

    # Initialize adapters
    config = Config.from_env()
    stock_adapter = ScreeningAdapter(config=config)
    etf_adapter = ETFScreeningAdapter(config=config)

    # Run tests
    results = []

    # Test 1: HK Fundamental
    results.append(await test_hk_fundamental_screening(stock_adapter))

    # Test 2: JP Technical
    results.append(await test_jp_technical_screening(stock_adapter))

    # Test 3: CN ETF
    results.append(await test_cn_etf_screening(etf_adapter))

    # Test 4: VN Full
    results.append(await test_vn_full_screening(stock_adapter))

    # Summary
    print_section("TEST SUMMARY")
    passed = sum(results)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed ({passed*100//total}%)")
    print()

    if passed == total:
        print("✅ ALL TESTS PASSED!")
        print("\nMarket expansion successful:")
        print("  ✅ HK market screening enabled")
        print("  ✅ JP market screening enabled")
        print("  ✅ CN market screening enabled (including ETFs)")
        print("  ✅ VN market screening enabled")
        return 0
    else:
        print(f"⚠️ {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
