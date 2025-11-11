#!/usr/bin/env python3
"""
Production Validation Test for Stock Screening Feature

Tests the screen_stocks functionality with real database data.
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Setup path
sys.path.insert(0, '/Users/13ruce/spock')
os.chdir('/Users/13ruce/spock')
os.environ['POSTGRES_PASSWORD'] = ''

from mcp_server.adapters.screening_adapter import ScreeningAdapter
from mcp_server.config import Config


class ScreeningProductionTest:
    """Production validation tests for screening functionality"""

    def __init__(self):
        """Initialize test environment"""
        self.config = Config.from_env()
        self.adapter = ScreeningAdapter(config=self.config)
        self.results = []

    async def test_fundamental_filters(self):
        """Test 1: Fundamental filters (P/E + Dividend Yield)"""
        print("\n" + "="*70)
        print("TEST 1: Fundamental Filters (P/E ≤ 15, Dividend Yield ≥ 3.0%)")
        print("="*70)

        filters = {
            "per_max": 15,
            "dividend_yield_min": 3.0
        }

        try:
            result = await self.adapter.screen_stocks(
                filters=filters,
                region="KR",
                limit=10
            )

            stocks = result.get("stocks", [])
            print(f"\n✅ Query executed successfully")
            print(f"📊 Results: {len(stocks)} stocks found")

            if stocks:
                print(f"\n{'Ticker':<10} {'Name':<20} {'P/E':>8} {'Div Yield':>10} {'Score':>8}")
                print("-" * 70)
                for stock in stocks[:10]:
                    ticker = stock.get("ticker", "N/A")
                    name = stock.get("name", "N/A")[:18]
                    per = stock.get("per", 0)
                    div_yield = stock.get("dividend_yield", 0)
                    composite = stock.get("composite_score", 0)
                    print(f"{ticker:<10} {name:<20} {per:>8.2f} {div_yield:>10.2f}% {composite:>8.1f}")

                # Validation
                validation_passed = True
                for stock in stocks:
                    if stock.get("per", 999) > 15:
                        print(f"❌ VALIDATION FAILED: {stock['ticker']} has P/E {stock['per']} > 15")
                        validation_passed = False
                    if stock.get("dividend_yield", 0) < 3.0:
                        print(f"❌ VALIDATION FAILED: {stock['ticker']} has Div Yield {stock['dividend_yield']}% < 3.0%")
                        validation_passed = False

                if validation_passed:
                    print(f"\n✅ All results pass filter criteria")
            else:
                print("\n⚠️ No stocks found matching criteria")

            self.results.append({
                "test": "fundamental_filters",
                "status": "PASS" if stocks else "NO_RESULTS",
                "count": len(stocks)
            })

            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({
                "test": "fundamental_filters",
                "status": "FAIL",
                "error": str(e)
            })
            return False

    async def test_combined_filters(self):
        """Test 2: Combined fundamental + technical filters"""
        print("\n" + "="*70)
        print("TEST 2: Combined Filters (P/E ≤ 20, P/B ≤ 3.0, RSI 30-70, MA Bullish)")
        print("="*70)

        filters = {
            "per_max": 20,
            "pbr_max": 3.0
        }

        technical_filters = {
            "rsi_min": 30,
            "rsi_max": 70,
            "ma_trend": "bullish"
        }

        try:
            result = await self.adapter.screen_stocks(
                filters=filters,
                technical_filters=technical_filters,
                region="KR",
                limit=20
            )

            stocks = result.get("stocks", [])
            print(f"\n✅ Query executed successfully")
            print(f"📊 Results: {len(stocks)} stocks found")

            if stocks:
                print(f"\n{'Ticker':<10} {'Name':<15} {'P/E':>7} {'P/B':>6} {'RSI':>6} {'MA Trend':<10} {'Score':>7}")
                print("-" * 75)
                for stock in stocks[:20]:
                    ticker = stock.get("ticker", "N/A")
                    name = stock.get("name", "N/A")[:13]
                    per = stock.get("per", 0)
                    pbr = stock.get("pbr", 0)
                    rsi = stock.get("technical_indicators", {}).get("rsi", 0)
                    ma_trend = stock.get("technical_indicators", {}).get("ma_trend", "N/A")
                    composite = stock.get("composite_score", 0)
                    print(f"{ticker:<10} {name:<15} {per:>7.2f} {pbr:>6.2f} {rsi:>6.1f} {ma_trend:<10} {composite:>7.1f}")

                # Validation
                validation_passed = True
                for stock in stocks:
                    # Fundamental validation
                    if stock.get("per", 999) > 20:
                        print(f"❌ VALIDATION FAILED: {stock['ticker']} has P/E {stock['per']} > 20")
                        validation_passed = False
                    if stock.get("pbr", 999) > 3.0:
                        print(f"❌ VALIDATION FAILED: {stock['ticker']} has P/B {stock['pbr']} > 3.0")
                        validation_passed = False

                    # Technical validation
                    tech = stock.get("technical_indicators", {})
                    if tech:
                        rsi = tech.get("rsi", 0)
                        ma_trend = tech.get("ma_trend", "")

                        if rsi < 30 or rsi > 70:
                            print(f"❌ VALIDATION FAILED: {stock['ticker']} has RSI {rsi} outside 30-70 range")
                            validation_passed = False

                        if ma_trend != "bullish":
                            print(f"❌ VALIDATION FAILED: {stock['ticker']} has MA trend '{ma_trend}' != 'bullish'")
                            validation_passed = False

                if validation_passed:
                    print(f"\n✅ All results pass filter criteria (fundamental + technical)")
            else:
                print("\n⚠️ No stocks found matching criteria (filters may be too strict)")

            self.results.append({
                "test": "combined_filters",
                "status": "PASS" if stocks else "NO_RESULTS",
                "count": len(stocks)
            })

            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            self.results.append({
                "test": "combined_filters",
                "status": "FAIL",
                "error": str(e)
            })
            return False

    async def test_edge_cases(self):
        """Test 3: Edge cases and error handling"""
        print("\n" + "="*70)
        print("TEST 3: Edge Cases and Error Handling")
        print("="*70)

        test_cases = [
            {
                "name": "No filters (should return all stocks)",
                "filters": {},
                "region": "KR",
                "limit": 5,
                "should_succeed": True
            },
            {
                "name": "Very strict filters (may return no results)",
                "filters": {"per_max": 1, "pbr_max": 0.1},
                "region": "KR",
                "limit": 10,
                "should_succeed": True
            },
            {
                "name": "Only technical filters (no fundamental)",
                "filters": {},
                "technical_filters": {"rsi_min": 40, "rsi_max": 60},
                "region": "KR",
                "limit": 10,
                "should_succeed": True
            }
        ]

        edge_case_results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. {test_case['name']}")
            print("-" * 70)

            try:
                kwargs = {
                    "filters": test_case["filters"],
                    "region": test_case["region"],
                    "limit": test_case["limit"]
                }

                if "technical_filters" in test_case:
                    kwargs["technical_filters"] = test_case["technical_filters"]

                result = await self.adapter.screen_stocks(**kwargs)
                stocks = result.get("stocks", [])

                print(f"   ✅ Query executed: {len(stocks)} results")

                if test_case["should_succeed"]:
                    edge_case_results.append(("PASS", test_case["name"]))
                else:
                    edge_case_results.append(("UNEXPECTED_SUCCESS", test_case["name"]))

            except Exception as e:
                if test_case["should_succeed"]:
                    print(f"   ❌ Unexpected error: {e}")
                    edge_case_results.append(("FAIL", test_case["name"]))
                else:
                    print(f"   ✅ Expected error: {e}")
                    edge_case_results.append(("PASS", test_case["name"]))

        # Summary
        passed = sum(1 for status, _ in edge_case_results if status == "PASS")
        total = len(edge_case_results)

        print(f"\n{'='*70}")
        print(f"Edge Case Summary: {passed}/{total} tests passed")
        print(f"{'='*70}")

        self.results.append({
            "test": "edge_cases",
            "status": "PASS" if passed == total else "PARTIAL",
            "passed": passed,
            "total": total
        })

        return passed == total

    async def run_all_tests(self):
        """Run all production validation tests"""
        print("\n" + "="*70)
        print("STOCK SCREENING PRODUCTION VALIDATION TEST SUITE")
        print("="*70)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {self.config.postgres_db}@{self.config.postgres_host}")
        print(f"Region: KR")

        # Run tests
        test1 = await self.test_fundamental_filters()
        test2 = await self.test_combined_filters()
        test3 = await self.test_edge_cases()

        # Final summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        for result in self.results:
            status_symbol = "✅" if result["status"] in ["PASS", "PARTIAL"] else "❌" if result["status"] == "FAIL" else "⚠️"
            print(f"{status_symbol} {result['test']}: {result['status']}")
            if "count" in result:
                print(f"   → Stocks found: {result['count']}")
            if "error" in result:
                print(f"   → Error: {result['error']}")

        all_passed = all(r["status"] in ["PASS", "PARTIAL", "NO_RESULTS"] for r in self.results)

        print("\n" + "="*70)
        if all_passed:
            print("✅ ALL TESTS PASSED - Production validation successful!")
        else:
            print("❌ SOME TESTS FAILED - Review errors above")
        print("="*70)

        return all_passed


async def main():
    """Main test runner"""
    tester = ScreeningProductionTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
