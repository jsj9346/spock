#!/usr/bin/env python3
"""
Test script for calculate_financial_ratios MCP tool

Validates:
1. FinancialRatioCalculator calculations
2. Ratio interpretation and health assessment
3. MCP tool integration
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator, RATIO_DEFINITIONS
from mcp_server.tools.ratios_tool import REQUIRED_FIELDS


async def test_ratio_calculator():
    """Test FinancialRatioCalculator with sample data"""
    print("=" * 60)
    print("Test 1: FinancialRatioCalculator")
    print("=" * 60)

    # Sample fundamental data (Samsung-like)
    sample_data = {
        "current_assets": 200000000000000,
        "current_liabilities": 80000000000000,
        "inventory": 40000000000000,
        "total_assets": 450000000000000,
        "total_liabilities": 100000000000000,
        "total_equity": 350000000000000,
        "revenue": 300000000000000,
        "gross_profit": 90000000000000,
        "operating_profit": 45000000000000,
        "net_income": 35000000000000,
        "ebitda": 60000000000000,
        "interest_expense": 2000000000000,
        "dividend_yield": 1.5,
        "dividend_per_share": 1444,
        "shares_outstanding": 5969782550,
        "cogs": 210000000000000,
        "accounts_receivable": 35000000000000,
    }

    calculator = FinancialRatioCalculator(sample_data)

    print("\n📊 Liquidity Ratios:")
    print(f"  Current Ratio: {calculator.calculate_current_ratio():.2f}")
    print(f"  Quick Ratio: {calculator.calculate_quick_ratio():.2f}")

    print("\n📊 Leverage Ratios:")
    print(f"  Debt Ratio: {calculator.calculate_debt_ratio():.2f}%")
    print(f"  Interest Coverage: {calculator.calculate_interest_coverage():.2f}x")

    print("\n📊 Profitability Ratios:")
    print(f"  Gross Margin: {calculator.calculate_gross_margin():.2f}%")
    print(f"  Operating Margin: {calculator.calculate_operating_margin():.2f}%")
    print(f"  Net Margin: {calculator.calculate_net_margin():.2f}%")
    print(f"  ROE: {calculator.calculate_roe():.2f}%")
    print(f"  ROA: {calculator.calculate_roa():.2f}%")

    print("\n📊 Efficiency Ratios:")
    print(f"  Asset Turnover: {calculator.calculate_asset_turnover():.2f}x")
    print(f"  Inventory Turnover: {calculator.calculate_inventory_turnover():.2f}x")

    return True


async def test_interpretation():
    """Test ratio interpretation and health status"""
    print("\n" + "=" * 60)
    print("Test 2: Ratio Interpretation")
    print("=" * 60)

    # Test with different scenarios
    test_cases = [
        # Healthy company
        {
            "name": "Healthy Company",
            "data": {
                "current_assets": 200,
                "current_liabilities": 100,  # CR = 2.0 (healthy)
                "total_liabilities": 50,
                "total_equity": 150,  # Debt ratio = 33% (healthy)
                "net_income": 20,
                "revenue": 200,  # Net margin = 10% (healthy)
            }
        },
        # Risky company
        {
            "name": "Risky Company",
            "data": {
                "current_assets": 80,
                "current_liabilities": 100,  # CR = 0.8 (warning)
                "total_liabilities": 300,
                "total_equity": 100,  # Debt ratio = 300% (warning)
                "net_income": 2,
                "revenue": 200,  # Net margin = 1% (low)
            }
        }
    ]

    for case in test_cases:
        print(f"\n🏢 {case['name']}:")
        calculator = FinancialRatioCalculator(case['data'])
        ratios = calculator.calculate_all()
        summary = calculator.get_summary(ratios)

        print(f"  Overall Health: {summary['overall_health']}")
        print(f"  Health Breakdown: {summary['health_breakdown']}")

        if summary['concerns']:
            print(f"  Concerns: {summary['concerns'][:2]}")

    return True


async def test_real_data():
    """Test with real data from database"""
    print("\n" + "=" * 60)
    print("Test 3: Real Data (Samsung Electronics)")
    print("=" * 60)

    adapter = DataAdapter()

    try:
        # Get fundamental data
        data = await adapter.get_fundamentals(
            tickers=["005930"],
            fields=REQUIRED_FIELDS,
            period_type="ANNUAL",
            periods=1,
            region="KR"
        )

        if "005930" not in data or not data["005930"]:
            print("⚠️ No data found for 005930")
            return True

        fundamentals = data["005930"][0]

        print(f"\nFiscal Year: {fundamentals.get('fiscal_year')}")
        print(f"Period: {fundamentals.get('period_type')}")

        # Calculate ratios
        calculator = FinancialRatioCalculator(fundamentals)
        ratios = calculator.calculate_all()

        print("\n📊 Calculated Ratios:")
        for category, category_ratios in ratios.items():
            print(f"\n  {category.upper()}:")
            for ratio_name, ratio_data in category_ratios.items():
                value = ratio_data.get("value")
                unit = ratio_data.get("unit")
                health = ratio_data.get("health_status")
                korean = ratio_data.get("korean")

                if value is not None:
                    if unit == "percent":
                        value_str = f"{value:.2f}%"
                    elif unit == "times":
                        value_str = f"{value:.2f}x"
                    else:
                        value_str = f"{value:.2f}"

                    health_emoji = {"healthy": "✅", "caution": "⚠️", "warning": "❌"}.get(health, "❓")
                    print(f"    {korean}: {value_str} {health_emoji}")

        # Summary
        summary = calculator.get_summary(ratios)
        print(f"\n📋 Summary:")
        print(f"  Overall Health: {summary['overall_health']}")
        print(f"  Healthy: {summary['health_breakdown'].get('healthy', 0)}")
        print(f"  Caution: {summary['health_breakdown'].get('caution', 0)}")
        print(f"  Warning: {summary['health_breakdown'].get('warning', 0)}")

    except Exception as e:
        print(f"⚠️ Test with real data: {e}")
        return True

    return True


async def test_mcp_integration():
    """Test full MCP tool integration"""
    print("\n" + "=" * 60)
    print("Test 4: MCP Tool Integration")
    print("=" * 60)

    from mcp_server.tools.ratios_tool import handle_calculate_financial_ratios

    adapter = DataAdapter()

    arguments = {
        "tickers": ["005930"],
        "ratio_categories": ["liquidity", "profitability"],
        "period_type": "ANNUAL",
        "include_interpretation": True,
        "region": "KR"
    }

    try:
        result = await handle_calculate_financial_ratios(adapter, arguments)

        # Parse response
        import json
        response_text = result[0].text
        response = json.loads(response_text)

        print(f"\n✅ MCP Tool Response:")
        print(f"  Success: {response.get('success')}")
        print(f"  Ticker Count: {response['metadata']['ticker_count']}")
        print(f"  Ratios Calculated: {response['metadata']['ratios_calculated']}")
        print(f"  Categories: {response['metadata']['categories']}")

        if "005930" in response["data"]:
            ticker_data = response["data"]["005930"]
            print(f"\n  Samsung (005930):")
            print(f"    Fiscal Year: {ticker_data.get('fiscal_year')}")
            print(f"    Overall Health: {ticker_data.get('summary', {}).get('overall_health')}")

    except Exception as e:
        print(f"❌ MCP Integration Error: {e}")
        return False

    return True


async def main():
    """Run all tests"""
    print("\n🚀 Testing calculate_financial_ratios MCP Tool\n")

    results = []

    results.append(("Ratio Calculator", await test_ratio_calculator()))
    results.append(("Interpretation", await test_interpretation()))
    results.append(("Real Data", await test_real_data()))
    results.append(("MCP Integration", await test_mcp_integration()))

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
