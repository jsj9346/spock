#!/usr/bin/env python3
"""
Test script for query_dividend_history MCP tool

Validates:
1. DataAdapter.get_dividend_history()
2. Dividend growth analysis (CAGR, streak)
3. MCP tool integration
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.tools.dividend_tool import (
    calculate_dividend_cagr,
    calculate_dividend_streak,
    get_annual_summary,
)


async def test_data_adapter():
    """Test DataAdapter.get_dividend_history()"""
    print("=" * 60)
    print("Test 1: DataAdapter.get_dividend_history()")
    print("=" * 60)

    adapter = DataAdapter()

    # Test KR dividends
    print("\n Testing KR dividends (Samsung 005930)...")
    try:
        kr_data = await adapter.get_dividend_history(
            tickers=["005930"],
            region="KR",
            years=5
        )

        if "005930" in kr_data and kr_data["005930"]:
            print(f"  Found {len(kr_data['005930'])} dividend records")
            for div in kr_data["005930"][:3]:
                print(f"    {div.get('fiscal_year')} {div.get('dividend_type')}: "
                      f"{div.get('dividend_per_share')} {div.get('currency')}")
        else:
            print("  No dividend data found for 005930")

    except Exception as e:
        print(f"  Error: {e}")

    # Test US dividends
    print("\n Testing US dividends (AAPL)...")
    try:
        us_data = await adapter.get_dividend_history(
            tickers=["AAPL"],
            region="US",
            years=3
        )

        if "AAPL" in us_data and us_data["AAPL"]:
            print(f"  Found {len(us_data['AAPL'])} dividend records")
            for div in us_data["AAPL"][:5]:
                print(f"    {div.get('fiscal_year')} {div.get('dividend_type')}: "
                      f"${div.get('dividend_per_share'):.4f} on {div.get('ex_dividend_date')}")
        else:
            print("  No dividend data found for AAPL")

    except Exception as e:
        print(f"  Error: {e}")

    return True


async def test_growth_analysis():
    """Test dividend growth analysis functions"""
    print("\n" + "=" * 60)
    print("Test 2: Dividend Growth Analysis")
    print("=" * 60)

    # Sample dividend data (simulating quarterly dividends)
    sample_dividends = [
        {"fiscal_year": 2024, "dividend_type": "quarterly", "dividend_per_share": 0.25},
        {"fiscal_year": 2024, "dividend_type": "quarterly", "dividend_per_share": 0.25},
        {"fiscal_year": 2024, "dividend_type": "quarterly", "dividend_per_share": 0.24},
        {"fiscal_year": 2024, "dividend_type": "quarterly", "dividend_per_share": 0.24},
        {"fiscal_year": 2023, "dividend_type": "quarterly", "dividend_per_share": 0.24},
        {"fiscal_year": 2023, "dividend_type": "quarterly", "dividend_per_share": 0.24},
        {"fiscal_year": 2023, "dividend_type": "quarterly", "dividend_per_share": 0.23},
        {"fiscal_year": 2023, "dividend_type": "quarterly", "dividend_per_share": 0.23},
        {"fiscal_year": 2022, "dividend_type": "quarterly", "dividend_per_share": 0.23},
        {"fiscal_year": 2022, "dividend_type": "quarterly", "dividend_per_share": 0.23},
        {"fiscal_year": 2022, "dividend_type": "quarterly", "dividend_per_share": 0.22},
        {"fiscal_year": 2022, "dividend_type": "quarterly", "dividend_per_share": 0.22},
    ]

    print("\n CAGR Calculation:")
    cagr = calculate_dividend_cagr(sample_dividends, 3)
    print(f"  3-Year CAGR: {cagr * 100:.2f}%" if cagr else "  3-Year CAGR: N/A")

    print("\n Dividend Streak:")
    streak = calculate_dividend_streak(sample_dividends)
    print(f"  Consecutive Years: {streak['consecutive_years']}")
    print(f"  Streak Type: {streak['streak_type']}")
    print(f"  Last Year: {streak['last_year']}")

    print("\n Annual Summary (2024):")
    summary = get_annual_summary(sample_dividends, 2024)
    print(f"  Total DPS: ${summary['total_dps']:.2f}")
    print(f"  Payments: {summary['payments']}")
    print(f"  Types: {summary['types']}")

    return True


async def test_mcp_integration():
    """Test full MCP tool integration"""
    print("\n" + "=" * 60)
    print("Test 3: MCP Tool Integration")
    print("=" * 60)

    from mcp_server.tools.dividend_tool import handle_query_dividend_history

    adapter = DataAdapter()

    # Test KR market
    print("\n Testing KR market (Samsung)...")
    arguments = {
        "tickers": ["005930"],
        "years": 5,
        "include_growth_analysis": True,
        "include_upcoming": True,
        "region": "KR"
    }

    try:
        result = await handle_query_dividend_history(adapter, arguments)

        # Parse response
        import json
        response_text = result[0].text
        response = json.loads(response_text)

        print(f"  Success: {response.get('success')}")
        print(f"  Ticker Count: {response['metadata']['ticker_count']}")

        if "005930" in response["data"]:
            ticker_data = response["data"]["005930"]
            print(f"\n  Samsung (005930):")
            print(f"    Has Dividends: {ticker_data.get('has_dividends')}")
            if ticker_data.get('has_dividends'):
                print(f"    Records: {len(ticker_data.get('dividend_history', []))}")
                if 'growth_analysis' in ticker_data:
                    ga = ticker_data['growth_analysis']
                    print(f"    Streak Type: {ga.get('dividend_streak')}")
                    print(f"    Consecutive Years: {ga.get('consecutive_years')}")

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test US market
    print("\n Testing US market (AAPL)...")
    arguments = {
        "tickers": ["AAPL"],
        "years": 3,
        "include_growth_analysis": True,
        "include_upcoming": True,
        "region": "US"
    }

    try:
        result = await handle_query_dividend_history(adapter, arguments)

        import json
        response_text = result[0].text
        response = json.loads(response_text)

        print(f"  Success: {response.get('success')}")

        if "AAPL" in response["data"]:
            ticker_data = response["data"]["AAPL"]
            print(f"\n  Apple (AAPL):")
            print(f"    Has Dividends: {ticker_data.get('has_dividends')}")
            if ticker_data.get('has_dividends'):
                print(f"    Records: {len(ticker_data.get('dividend_history', []))}")
                if 'summary' in ticker_data:
                    s = ticker_data['summary']
                    print(f"    Current Year Total: ${s.get('annual_dividend_current', 0):.2f}")
                    print(f"    Last Year Total: ${s.get('annual_dividend_last_year', 0):.2f}")

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


async def main():
    """Run all tests"""
    print("\n Testing query_dividend_history MCP Tool\n")

    results = []

    results.append(("Data Adapter", await test_data_adapter()))
    results.append(("Growth Analysis", await test_growth_analysis()))
    results.append(("MCP Integration", await test_mcp_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = " PASS" if result else " FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
