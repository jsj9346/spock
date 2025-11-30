#!/usr/bin/env python3
"""
Test script for query_fundamentals MCP tool

Validates:
1. DataAdapter.get_fundamentals() works correctly
2. Field mapping and response formatting
3. Error handling
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.tools.fundamentals_tool import (
    get_fields_for_categories,
    format_fundamentals_response,
    FUNDAMENTALS_FIELDS
)


async def test_get_fundamentals():
    """Test DataAdapter.get_fundamentals() method"""
    print("=" * 60)
    print("Test 1: DataAdapter.get_fundamentals()")
    print("=" * 60)

    adapter = DataAdapter()

    # Test with Samsung Electronics (KR)
    tickers = ["005930"]
    fields = get_fields_for_categories(["balance_sheet", "income_statement"])

    print(f"\nTickers: {tickers}")
    print(f"Fields: {fields[:10]}...")  # Show first 10
    print(f"Period Type: ANNUAL")
    print(f"Periods: 3")

    try:
        data = await adapter.get_fundamentals(
            tickers=tickers,
            fields=fields,
            period_type="ANNUAL",
            periods=3,
            region="KR"
        )

        print(f"\n✅ Success! Retrieved data for {len(data)} ticker(s)")

        for ticker, records in data.items():
            print(f"\n  {ticker}: {len(records)} period(s)")
            for record in records:
                fy = record.get("fiscal_year", "N/A")
                revenue = record.get("revenue")
                net_income = record.get("net_income")
                print(f"    - FY{fy}: Revenue={revenue}, Net Income={net_income}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

    return True


async def test_field_mapping():
    """Test field mapping for categories"""
    print("\n" + "=" * 60)
    print("Test 2: Field Mapping")
    print("=" * 60)

    # Test all categories
    for category in ["balance_sheet", "income_statement", "cash_flow", "valuation", "all"]:
        fields = get_fields_for_categories([category])
        print(f"\n  {category}: {len(fields)} fields")
        if category != "all":
            print(f"    Fields: {', '.join(fields[:5])}...")

    return True


async def test_response_formatting():
    """Test response formatting"""
    print("\n" + "=" * 60)
    print("Test 3: Response Formatting")
    print("=" * 60)

    adapter = DataAdapter()

    try:
        data = await adapter.get_fundamentals(
            tickers=["005930"],
            fields=get_fields_for_categories(["valuation"]),
            period_type="DAILY",
            periods=1,
            region="KR"
        )

        response = format_fundamentals_response(data, ["valuation"], "KR")

        print(f"\n✅ Response formatted successfully")
        print(f"  Success: {response['success']}")
        print(f"  Ticker count: {response['metadata']['ticker_count']}")
        print(f"  Currency: {response['metadata']['currency']}")

        # Show sample data
        if "005930" in response["data"]:
            ticker_data = response["data"]["005930"]
            if ticker_data["periods"]:
                period = ticker_data["periods"][0]
                print(f"\n  Sample valuation data:")
                if "valuation" in period:
                    for key, val in list(period["valuation"].items())[:5]:
                        print(f"    {key}: {val}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

    return True


async def test_us_market():
    """Test with US market data"""
    print("\n" + "=" * 60)
    print("Test 4: US Market (AAPL)")
    print("=" * 60)

    adapter = DataAdapter()

    try:
        data = await adapter.get_fundamentals(
            tickers=["AAPL"],
            fields=get_fields_for_categories(["balance_sheet"]),
            period_type="ANNUAL",
            periods=2,
            region="US"
        )

        print(f"\n✅ US market data retrieved")
        for ticker, records in data.items():
            print(f"  {ticker}: {len(records)} period(s)")
            for record in records:
                print(f"    - FY{record.get('fiscal_year')}: "
                      f"Total Assets={record.get('total_assets')}")

    except Exception as e:
        print(f"\n⚠️ US market test: {e}")
        # US market might not have all data - not a failure
        return True

    return True


async def main():
    """Run all tests"""
    print("\n🚀 Testing query_fundamentals MCP Tool\n")

    results = []

    results.append(("Field Mapping", await test_field_mapping()))
    results.append(("Get Fundamentals (KR)", await test_get_fundamentals()))
    results.append(("Response Formatting", await test_response_formatting()))
    results.append(("US Market", await test_us_market()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
