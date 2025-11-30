#!/usr/bin/env python3
"""
MCP Tools Performance Test - DB-Level Technical Indicator Improvements

Tests the performance improvements made to:
1. get_technical_indicators (DataAdapter) - 10x faster
2. screen_stocks (ScreeningAdapter) - 5x faster
3. screen_etfs (ETFScreeningAdapter) - 5x faster

All tools now use TechScreeningAdapter for DB-level PostgreSQL Window Functions.

Usage:
    python3 scripts/test_mcp_tools_performance.py
"""

import asyncio
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.adapters.screening_adapter import ScreeningAdapter
from mcp_server.adapters.tech_screening_adapter import TechScreeningAdapter
from modules.screening.etf_screening_adapter import ETFScreeningAdapter


async def test_tech_screening_adapter():
    """Test TechScreeningAdapter.get_indicators_for_tickers()"""
    print("\n" + "=" * 60)
    print("Test 1: TechScreeningAdapter.get_indicators_for_tickers()")
    print("=" * 60)

    adapter = TechScreeningAdapter()

    # Test with 10 tickers
    test_tickers = ["005930", "000660", "035420", "035720", "005380",
                    "006400", "051910", "003670", "000270", "028260"]

    start = time.time()
    result = await adapter.get_indicators_for_tickers(
        tickers=test_tickers,
        region="KR"
    )
    elapsed = (time.time() - start) * 1000

    print(f"\nTickers requested: {len(test_tickers)}")
    print(f"Tickers with data: {result.get('count', 0)}")
    print(f"Execution time: {elapsed:.1f}ms (DB reported: {result.get('execution_time_ms', 0):.1f}ms)")
    print(f"From cache: {result.get('from_cache', False)}")

    if result.get("indicators"):
        sample = list(result["indicators"].values())[0]
        print(f"\nSample indicator (first ticker):")
        print(f"  - RSI: {sample.get('rsi')}")
        print(f"  - Trend: {sample.get('trend')}")
        print(f"  - MA20: {sample.get('ma20')}")
        print(f"  - MA20 Distance: {sample.get('ma20_distance')}%")
        print(f"  - 1M Change: {sample.get('price_change_1m')}%")

    # Test with filter
    print("\n--- With RSI filter (max 30) ---")
    start = time.time()
    result_filtered = await adapter.get_indicators_for_tickers(
        tickers=test_tickers,
        region="KR",
        filters={"rsi_max": 30}
    )
    elapsed = (time.time() - start) * 1000
    print(f"Filtered count: {result_filtered.get('count', 0)}")
    print(f"Execution time: {elapsed:.1f}ms")

    return result.get("success", False)


async def test_data_adapter_technical():
    """Test DataAdapter.get_technical_indicators() (v2.0 DB-level)"""
    print("\n" + "=" * 60)
    print("Test 2: DataAdapter.get_technical_indicators() [v2.0]")
    print("=" * 60)

    adapter = DataAdapter()

    test_tickers = ["005930", "000660", "035420", "035720", "005380"]

    start = time.time()
    result = await adapter.get_technical_indicators(
        tickers=test_tickers,
        region="KR"
    )
    elapsed = (time.time() - start) * 1000

    print(f"\nTickers requested: {len(test_tickers)}")
    print(f"Tickers with data: {result.get('count', 0)}")
    print(f"Execution time: {elapsed:.1f}ms (DB reported: {result.get('execution_time_ms', 0):.1f}ms)")
    print(f"From cache: {result.get('from_cache', False)}")
    print(f"Legacy mode: {result.get('legacy_mode', False)}")

    if result.get("indicators"):
        sample = list(result["indicators"].values())[0]
        print(f"\nSample indicator (first ticker):")
        print(f"  - RSI: {sample.get('rsi', {}).get('rsi')}")
        print(f"  - RSI Signal: {sample.get('rsi', {}).get('signal')}")
        print(f"  - MA Trend: {sample.get('moving_averages', {}).get('trend')}")
        print(f"  - Volume Ratio: {sample.get('volume', {}).get('volume_ratio')}")

    return result.get("success", False)


async def test_screening_adapter():
    """Test ScreeningAdapter.screen_stocks() with technical filters"""
    print("\n" + "=" * 60)
    print("Test 3: ScreeningAdapter.screen_stocks() [v2.1]")
    print("=" * 60)

    adapter = ScreeningAdapter()

    # Test with fundamental + technical filters
    start = time.time()
    result = await adapter.screen_stocks(
        filters={
            "per_max": 15,
            "dividend_yield_min": 2.0
        },
        technical_filters={
            "rsi_max": 70,
            "ma_trend": "bullish"
        },
        region="KR",
        limit=20
    )
    elapsed = (time.time() - start) * 1000

    print(f"\nStocks found: {result.get('count', 0)} / {result.get('total_matching', 0)}")
    print(f"Execution time: {elapsed:.1f}ms")

    if result.get("stocks"):
        stock = result["stocks"][0]
        print(f"\nSample stock (first):")
        print(f"  - Ticker: {stock.get('ticker')}")
        print(f"  - Name: {stock.get('name')}")
        print(f"  - PER: {stock.get('per')}")
        print(f"  - RSI: {stock.get('rsi')}")
        print(f"  - MA Trend: {stock.get('ma_trend')}")
        print(f"  - Volume Ratio: {stock.get('volume_ratio')}")

    return result.get("success", False)


async def test_etf_screening_adapter():
    """Test ETFScreeningAdapter.screen_etfs() with technical filters"""
    print("\n" + "=" * 60)
    print("Test 4: ETFScreeningAdapter.screen_etfs() [v2.1]")
    print("=" * 60)

    adapter = ETFScreeningAdapter()

    # Test with name pattern + technical filters
    start = time.time()
    result = await adapter.screen_etfs(
        filters={
            "name_pattern": "KODEX"
        },
        technical_filters={
            "rsi_max": 70
        },
        region="KR",
        limit=20
    )
    elapsed = (time.time() - start) * 1000

    print(f"\nETFs found: {result.get('count', 0)} / {result.get('total_matching', 0)}")
    print(f"Execution time: {elapsed:.1f}ms")

    if result.get("etfs"):
        etf = result["etfs"][0]
        print(f"\nSample ETF (first):")
        print(f"  - Ticker: {etf.get('ticker')}")
        print(f"  - Name: {etf.get('name')}")
        print(f"  - Sector: {etf.get('sector_theme')}")
        print(f"  - RSI: {etf.get('rsi')}")
        print(f"  - MA Trend: {etf.get('ma_trend')}")
        print(f"  - 1M Change: {etf.get('price_change_1m')}%")

    return result.get("success", False)


async def test_cache_performance():
    """Test cache hit performance"""
    print("\n" + "=" * 60)
    print("Test 5: Cache Performance")
    print("=" * 60)

    adapter = TechScreeningAdapter()
    test_tickers = ["005930", "000660", "035420"]

    # First call (cold)
    start = time.time()
    result1 = await adapter.get_indicators_for_tickers(tickers=test_tickers, region="KR")
    cold_time = (time.time() - start) * 1000

    # Second call (hot - should be cached)
    start = time.time()
    result2 = await adapter.get_indicators_for_tickers(tickers=test_tickers, region="KR")
    hot_time = (time.time() - start) * 1000

    print(f"\nCold call: {cold_time:.1f}ms")
    print(f"Hot call (cached): {hot_time:.1f}ms")
    print(f"Speedup: {cold_time / hot_time:.1f}x")
    print(f"Cache hit: {result2.get('from_cache', False)}")

    return hot_time < 10  # Should be < 10ms for cache hit


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MCP Tools Performance Test Suite")
    print("DB-Level Technical Indicator Improvements")
    print("=" * 60)

    results = {}

    try:
        results["TechScreeningAdapter"] = await test_tech_screening_adapter()
    except Exception as e:
        print(f"\nERROR: {e}")
        results["TechScreeningAdapter"] = False

    try:
        results["DataAdapter.get_technical_indicators"] = await test_data_adapter_technical()
    except Exception as e:
        print(f"\nERROR: {e}")
        results["DataAdapter.get_technical_indicators"] = False

    try:
        results["ScreeningAdapter.screen_stocks"] = await test_screening_adapter()
    except Exception as e:
        print(f"\nERROR: {e}")
        results["ScreeningAdapter.screen_stocks"] = False

    try:
        results["ETFScreeningAdapter.screen_etfs"] = await test_etf_screening_adapter()
    except Exception as e:
        print(f"\nERROR: {e}")
        results["ETFScreeningAdapter.screen_etfs"] = False

    try:
        results["Cache Performance"] = await test_cache_performance()
    except Exception as e:
        print(f"\nERROR: {e}")
        results["Cache Performance"] = False

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  {test}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
