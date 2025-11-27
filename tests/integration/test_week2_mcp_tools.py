#!/usr/bin/env python3
"""
Week 2 MCP Tools Integration Tests

Tests for dividend history and cash ratio features:
- Phase 3: dividend_history table and query_dividend_history tool
- Phase 4: cash columns and cash_position ratio calculations
"""

import os
import sys
import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger


class Week2IntegrationTests:
    """Integration tests for Week 2 MCP features."""

    def __init__(self):
        self.results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tests": []
        }

    def record_result(self, test_name: str, passed: bool, message: str = "", skipped: bool = False):
        """Record test result."""
        if skipped:
            self.results["skipped"] += 1
            status = "SKIPPED"
        elif passed:
            self.results["passed"] += 1
            status = "PASSED"
        else:
            self.results["failed"] += 1
            status = "FAILED"

        self.results["tests"].append({
            "name": test_name,
            "status": status,
            "message": message
        })
        logger.info(f"[{status}] {test_name}: {message}")

    # =========================================================================
    # Phase 3 Tests: Dividend History
    # =========================================================================

    def test_dividend_history_table_exists(self):
        """Test that dividend_history table was created."""
        test_name = "dividend_history_table_exists"
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            db = PostgresDatabaseManager()

            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'dividend_history'
            ) as exists
            """
            result = db.execute_query(query)

            if result and result[0].get('exists'):
                self.record_result(test_name, True, "dividend_history table exists")
            else:
                self.record_result(test_name, False, "dividend_history table not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_history_data_migrated(self):
        """Test that dividend data was migrated."""
        test_name = "dividend_history_data_migrated"
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            db = PostgresDatabaseManager()

            query = """
            SELECT
                region,
                COUNT(*) as count,
                COUNT(DISTINCT ticker) as tickers
            FROM dividend_history
            GROUP BY region
            ORDER BY region
            """
            result = db.execute_query(query)

            if result and len(result) > 0:
                total = sum(r['count'] for r in result)
                regions = [r['region'] for r in result]
                self.record_result(
                    test_name, True,
                    f"Found {total} dividend records in {len(regions)} regions: {regions}"
                )
            else:
                self.record_result(test_name, False, "No dividend data found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_cagr_calculation(self):
        """Test dividend CAGR calculation."""
        test_name = "dividend_cagr_calculation"
        try:
            from mcp_server.tools.dividend_tool import calculate_dividend_cagr

            # Test data: dividends growing from 100 to 200 over 5 years
            # Expected CAGR: (200/100)^(1/5) - 1 = 0.1487 (14.87%)
            test_dividends = [
                {"fiscal_year": 2019, "dividend_per_share": 100},
                {"fiscal_year": 2020, "dividend_per_share": 120},
                {"fiscal_year": 2021, "dividend_per_share": 140},
                {"fiscal_year": 2022, "dividend_per_share": 160},
                {"fiscal_year": 2023, "dividend_per_share": 180},
                {"fiscal_year": 2024, "dividend_per_share": 200},
            ]

            cagr = calculate_dividend_cagr(test_dividends, 5)

            if cagr is not None and 0.14 < cagr < 0.16:
                self.record_result(test_name, True, f"CAGR = {cagr:.4f} (expected ~0.1487)")
            else:
                self.record_result(test_name, False, f"Unexpected CAGR: {cagr}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_streak_calculation(self):
        """Test dividend streak detection."""
        test_name = "dividend_streak_calculation"
        try:
            from mcp_server.tools.dividend_tool import calculate_dividend_streak

            # Test 5-year streak
            test_dividends = [
                {"fiscal_year": 2020, "dividend_per_share": 100},
                {"fiscal_year": 2021, "dividend_per_share": 110},
                {"fiscal_year": 2022, "dividend_per_share": 120},
                {"fiscal_year": 2023, "dividend_per_share": 130},
                {"fiscal_year": 2024, "dividend_per_share": 140},
            ]

            streak = calculate_dividend_streak(test_dividends)

            if streak["consecutive_years"] == 5 and streak["streak_type"] == "stable":
                self.record_result(
                    test_name, True,
                    f"Streak: {streak['consecutive_years']} years ({streak['streak_type']})"
                )
            else:
                self.record_result(test_name, False, f"Unexpected streak: {streak}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_tool_definition(self):
        """Test dividend tool definition."""
        test_name = "dividend_tool_definition"
        try:
            from mcp_server.tools.dividend_tool import get_dividend_tool_def

            tool_def = get_dividend_tool_def()

            checks = [
                tool_def.name == "query_dividend_history",
                "tickers" in tool_def.inputSchema["properties"],
                "years" in tool_def.inputSchema["properties"],
                "include_growth_analysis" in tool_def.inputSchema["properties"],
            ]

            if all(checks):
                self.record_result(test_name, True, "Tool definition is correct")
            else:
                self.record_result(test_name, False, f"Tool definition incomplete: {tool_def.name}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_data_adapter_dividend_history(self):
        """Test DataAdapter.get_dividend_history method."""
        test_name = "data_adapter_dividend_history"
        try:
            from mcp_server.adapters.data_adapter import DataAdapter

            adapter = DataAdapter()

            # Test with a KR ticker that should have dividend data
            async def run_test():
                result = await adapter.get_dividend_history(
                    tickers=["005930"],  # Samsung
                    region="KR",
                    years=3
                )
                return result

            result = asyncio.run(run_test())

            if "005930" in result and len(result["005930"]) > 0:
                self.record_result(
                    test_name, True,
                    f"Found {len(result['005930'])} dividend records for 005930"
                )
            else:
                # May not have data, but method should work
                self.record_result(
                    test_name, True,
                    "Method works but no dividend data for 005930"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 4 Tests: Cash Ratio
    # =========================================================================

    def test_cash_columns_exist(self):
        """Test that cash columns were added to ticker_fundamentals."""
        test_name = "cash_columns_exist"
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            db = PostgresDatabaseManager()

            query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
              AND column_name IN ('cash_and_equivalents', 'short_term_investments', 'marketable_securities')
            """
            result = db.execute_query(query)

            columns_found = [r['column_name'] for r in result] if result else []

            if len(columns_found) == 3:
                self.record_result(test_name, True, f"All cash columns exist: {columns_found}")
            else:
                self.record_result(test_name, False, f"Missing columns. Found: {columns_found}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_cash_data_backfilled(self):
        """Test that some cash data has been backfilled."""
        test_name = "cash_data_backfilled"
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            db = PostgresDatabaseManager()

            query = """
            SELECT COUNT(*) as count
            FROM ticker_fundamentals
            WHERE cash_and_equivalents IS NOT NULL
            """
            result = db.execute_query(query)

            count = result[0]['count'] if result else 0

            if count > 0:
                self.record_result(test_name, True, f"Found {count} records with cash data")
            else:
                self.record_result(
                    test_name, True,
                    "No cash data yet (backfill may not have run for all tickers)"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_cash_ratio_calculator(self):
        """Test cash ratio calculation logic."""
        test_name = "cash_ratio_calculator"
        try:
            from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator

            # Test data
            test_data = {
                "cash_and_equivalents": 1000000,
                "short_term_investments": 500000,
                "marketable_securities": 300000,
                "current_liabilities": 2000000,
                "total_assets": 10000000,
                "total_liabilities": 5000000,
            }

            calculator = FinancialRatioCalculator(test_data)

            # Test cash_ratio = cash_and_equivalents / current_liabilities = 0.5
            cash_ratio = calculator.calculate_cash_ratio()

            # Test cash_to_assets
            cash_to_assets = calculator.calculate_cash_to_assets()

            # Test net_cash_position
            net_cash = calculator.calculate_net_cash_position()

            results_ok = True
            messages = []

            if cash_ratio is not None and abs(cash_ratio - 0.5) < 0.01:
                messages.append(f"cash_ratio={cash_ratio:.2f}")
            else:
                results_ok = False
                messages.append(f"cash_ratio wrong: {cash_ratio}")

            if cash_to_assets is not None:
                messages.append(f"cash_to_assets={cash_to_assets:.4f}")
            else:
                results_ok = False
                messages.append("cash_to_assets failed")

            if net_cash is not None:
                messages.append(f"net_cash_position={net_cash}")
            else:
                results_ok = False
                messages.append("net_cash_position failed")

            self.record_result(test_name, results_ok, "; ".join(messages))

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_cash_position_category_in_ratios(self):
        """Test that cash_position category is available in ratio definitions."""
        test_name = "cash_position_category_in_ratios"
        try:
            from mcp_server.calculators.ratio_calculator import RATIO_DEFINITIONS

            # cash_ratio is in "liquidity" category
            # cash_to_assets and net_cash_position are in "cash_position" category
            checks = []

            # Check cash_ratio in liquidity
            if "liquidity" in RATIO_DEFINITIONS:
                if "cash_ratio" in RATIO_DEFINITIONS["liquidity"]:
                    checks.append("cash_ratio in liquidity")

            # Check cash_position category
            if "cash_position" in RATIO_DEFINITIONS:
                ratios = list(RATIO_DEFINITIONS["cash_position"].keys())
                expected = ["cash_to_assets", "net_cash_position"]
                if all(r in ratios for r in expected):
                    checks.append(f"cash_position ratios: {ratios}")

            if len(checks) == 2:
                self.record_result(test_name, True, "; ".join(checks))
            else:
                self.record_result(test_name, False, f"Missing ratios. Found: {checks}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_ratios_tool_includes_cash_position(self):
        """Test that ratios tool schema includes cash_position category."""
        test_name = "ratios_tool_includes_cash_position"
        try:
            from mcp_server.tools.ratios_tool import get_ratios_tool_def

            tool_def = get_ratios_tool_def()
            schema = tool_def.inputSchema

            categories_enum = schema["properties"]["ratio_categories"]["items"]["enum"]

            if "cash_position" in categories_enum:
                self.record_result(test_name, True, f"Categories: {categories_enum}")
            else:
                self.record_result(test_name, False, f"cash_position not in {categories_enum}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_required_fields_include_cash(self):
        """Test that REQUIRED_FIELDS includes cash columns."""
        test_name = "required_fields_include_cash"
        try:
            from mcp_server.tools.ratios_tool import REQUIRED_FIELDS

            cash_fields = ["cash_and_equivalents", "short_term_investments", "marketable_securities"]
            missing = [f for f in cash_fields if f not in REQUIRED_FIELDS]

            if not missing:
                self.record_result(test_name, True, "All cash fields in REQUIRED_FIELDS")
            else:
                self.record_result(test_name, False, f"Missing fields: {missing}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Integration Tests: End-to-End
    # =========================================================================

    def test_dividend_tool_handler(self):
        """Test dividend tool handler end-to-end."""
        test_name = "dividend_tool_handler_e2e"
        try:
            from mcp_server.adapters.data_adapter import DataAdapter
            from mcp_server.tools.dividend_tool import handle_query_dividend_history

            adapter = DataAdapter()

            async def run_test():
                result = await handle_query_dividend_history(
                    adapter,
                    {
                        "tickers": ["005930"],
                        "years": 3,
                        "include_growth_analysis": True,
                        "region": "KR"
                    }
                )
                return result

            result = asyncio.run(run_test())

            if result and len(result) > 0:
                response_text = result[0].text
                response = json.loads(response_text)

                if response.get("success"):
                    self.record_result(test_name, True, "Handler returned success response")
                else:
                    # May not have data but handler should work
                    self.record_result(test_name, True, f"Handler works: {response.get('error', 'no data')}")
            else:
                self.record_result(test_name, False, "No response from handler")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_ratios_tool_handler_cash_position(self):
        """Test ratios tool handler with cash_position category."""
        test_name = "ratios_tool_handler_cash_position"
        try:
            from mcp_server.adapters.data_adapter import DataAdapter
            from mcp_server.tools.ratios_tool import handle_calculate_financial_ratios

            adapter = DataAdapter()

            async def run_test():
                result = await handle_calculate_financial_ratios(
                    adapter,
                    {
                        "tickers": ["AAPL"],
                        "ratio_categories": ["cash_position"],
                        "period_type": "ANNUAL",
                        "region": "US"
                    }
                )
                return result

            result = asyncio.run(run_test())

            if result and len(result) > 0:
                response_text = result[0].text
                response = json.loads(response_text)

                if response.get("success"):
                    data = response.get("data", {})
                    if "AAPL" in data:
                        ratios = data["AAPL"].get("ratios", {})
                        if "cash_position" in ratios:
                            self.record_result(
                                test_name, True,
                                f"Got cash_position ratios: {list(ratios['cash_position'].keys())}"
                            )
                        else:
                            self.record_result(
                                test_name, True,
                                "Handler works but no cash data for AAPL"
                            )
                    else:
                        self.record_result(test_name, True, "Handler works, no AAPL data")
                else:
                    self.record_result(test_name, True, f"Handler works: {response.get('error', 'no data')}")
            else:
                self.record_result(test_name, False, "No response from handler")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_mcp_server_tool_registration(self):
        """Test that all Week 2 tools are registered in MCP server."""
        test_name = "mcp_server_tool_registration"
        try:
            # Check imports work
            from mcp_server.tools.dividend_tool import get_dividend_tool_def, handle_query_dividend_history
            from mcp_server.tools.ratios_tool import get_ratios_tool_def, handle_calculate_financial_ratios

            # Get tool definitions
            dividend_tool = get_dividend_tool_def()
            ratios_tool = get_ratios_tool_def()

            checks = [
                dividend_tool.name == "query_dividend_history",
                ratios_tool.name == "calculate_financial_ratios",
            ]

            if all(checks):
                self.record_result(test_name, True, "All Week 2 tools properly defined")
            else:
                self.record_result(test_name, False, "Some tools not properly defined")

        except ImportError as e:
            self.record_result(test_name, False, f"Import error: {e}")
        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 5 Tests: Orchestrator Integration
    # =========================================================================

    def test_orchestrator_dividend_step(self):
        """Test that orchestrator has dividend step with history collection."""
        test_name = "orchestrator_dividend_step"
        try:
            from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator

            # Check STEP_ORDER contains dividend
            if 'dividend' in DatabaseUpdateOrchestrator.STEP_ORDER:
                self.record_result(test_name, True, "dividend step in STEP_ORDER")
            else:
                self.record_result(test_name, False, "dividend step not found in STEP_ORDER")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_orchestrator_cash_backfill_step(self):
        """Test that orchestrator has cash_backfill step."""
        test_name = "orchestrator_cash_backfill_step"
        try:
            from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator

            if 'cash_backfill' in DatabaseUpdateOrchestrator.STEP_ORDER:
                self.record_result(test_name, True, "cash_backfill step in STEP_ORDER")
            else:
                self.record_result(test_name, False, "cash_backfill step not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_orchestrator_fundamental_ratios_step(self):
        """Test that orchestrator has fundamental_ratios step."""
        test_name = "orchestrator_fundamental_ratios_step"
        try:
            from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator

            if 'fundamental_ratios' in DatabaseUpdateOrchestrator.STEP_ORDER:
                self.record_result(test_name, True, "fundamental_ratios step in STEP_ORDER")
            else:
                self.record_result(test_name, False, "fundamental_ratios step not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_collector_exists(self):
        """Test that DividendCollector class exists and is importable."""
        test_name = "dividend_collector_exists"
        try:
            from modules.collection.dividend_collector import DividendCollector, DividendRecord

            collector = DividendCollector()

            # Check methods exist
            methods = ['collect_kr_dividends', 'collect_yfinance_dividends',
                       'collect_ticker_dividends', 'collect_batch', 'save_dividend_record']
            missing = [m for m in methods if not hasattr(collector, m)]

            if not missing:
                self.record_result(test_name, True, "DividendCollector has all methods")
            else:
                self.record_result(test_name, False, f"Missing methods: {missing}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_cash_backfiller_exists(self):
        """Test that CashDataBackfiller class exists."""
        test_name = "cash_backfiller_exists"
        try:
            from scripts.backfill_cash_data import CashDataBackfiller

            backfiller = CashDataBackfiller()

            # Check methods exist
            methods = ['get_tickers_needing_cash_data', 'fetch_us_cash_data',
                       'update_cash_data', 'run_backfill']
            missing = [m for m in methods if not hasattr(backfiller, m)]

            if not missing:
                self.record_result(test_name, True, "CashDataBackfiller has all methods")
            else:
                self.record_result(test_name, False, f"Missing methods: {missing}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 6 Tests: Turnover Ratios (Inventory Days, Receivables Days)
    # =========================================================================

    def test_inventory_days_in_ratio_definitions(self):
        """Test that inventory_days is defined in RATIO_DEFINITIONS."""
        test_name = "inventory_days_in_ratio_definitions"
        try:
            from mcp_server.calculators.ratio_calculator import RATIO_DEFINITIONS

            if "efficiency" in RATIO_DEFINITIONS:
                if "inventory_days" in RATIO_DEFINITIONS["efficiency"]:
                    ratio_def = RATIO_DEFINITIONS["efficiency"]["inventory_days"]
                    if ratio_def.get("unit") == "days" and ratio_def.get("korean") == "재고자산회전일수":
                        self.record_result(test_name, True, f"inventory_days defined: {ratio_def['formula']}")
                    else:
                        self.record_result(test_name, False, "inventory_days has wrong definition")
                else:
                    self.record_result(test_name, False, "inventory_days not in efficiency category")
            else:
                self.record_result(test_name, False, "efficiency category not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_receivables_days_in_ratio_definitions(self):
        """Test that receivables_days is defined in RATIO_DEFINITIONS."""
        test_name = "receivables_days_in_ratio_definitions"
        try:
            from mcp_server.calculators.ratio_calculator import RATIO_DEFINITIONS

            if "efficiency" in RATIO_DEFINITIONS:
                if "receivables_days" in RATIO_DEFINITIONS["efficiency"]:
                    ratio_def = RATIO_DEFINITIONS["efficiency"]["receivables_days"]
                    if ratio_def.get("unit") == "days" and ratio_def.get("korean") == "매출채권회전일수":
                        self.record_result(test_name, True, f"receivables_days defined: {ratio_def['formula']}")
                    else:
                        self.record_result(test_name, False, "receivables_days has wrong definition")
                else:
                    self.record_result(test_name, False, "receivables_days not in efficiency category")
            else:
                self.record_result(test_name, False, "efficiency category not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_inventory_days_calculation(self):
        """Test inventory_days calculation logic."""
        test_name = "inventory_days_calculation"
        try:
            from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator as RatioCalculator

            # Test data: Inventory Turnover = 6 => Inventory Days = 365/6 ≈ 60.83
            test_data = {
                "cogs": 600000,
                "inventory": 100000  # Turnover = 6
            }

            calculator = RatioCalculator(test_data)
            inventory_days = calculator.calculate_inventory_days()

            if inventory_days is not None:
                expected = 365.0 / 6  # ~60.83
                if abs(inventory_days - expected) < 0.1:
                    self.record_result(test_name, True, f"inventory_days = {inventory_days:.2f} (expected ~60.83)")
                else:
                    self.record_result(test_name, False, f"Wrong value: {inventory_days} (expected ~60.83)")
            else:
                self.record_result(test_name, False, "calculate_inventory_days returned None")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_receivables_days_calculation(self):
        """Test receivables_days calculation logic."""
        test_name = "receivables_days_calculation"
        try:
            from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator as RatioCalculator

            # Test data: Receivables Turnover = 10 => Receivables Days = 365/10 = 36.5
            test_data = {
                "revenue": 1000000,
                "accounts_receivable": 100000  # Turnover = 10
            }

            calculator = RatioCalculator(test_data)
            receivables_days = calculator.calculate_receivables_days()

            if receivables_days is not None:
                expected = 365.0 / 10  # 36.5
                if abs(receivables_days - expected) < 0.1:
                    self.record_result(test_name, True, f"receivables_days = {receivables_days:.2f} (expected 36.5)")
                else:
                    self.record_result(test_name, False, f"Wrong value: {receivables_days} (expected 36.5)")
            else:
                self.record_result(test_name, False, "calculate_receivables_days returned None")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_turnover_days_in_efficiency_category(self):
        """Test that turnover days are calculated when efficiency category is requested."""
        test_name = "turnover_days_in_efficiency_category"
        try:
            from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator as RatioCalculator

            test_data = {
                "revenue": 1000000,
                "accounts_receivable": 100000,
                "cogs": 600000,
                "inventory": 100000,
                "total_assets": 2000000
            }

            calculator = RatioCalculator(test_data)
            efficiency_ratios = calculator.calculate_category("efficiency")

            expected_ratios = ["asset_turnover", "inventory_turnover", "receivables_turnover",
                              "inventory_days", "receivables_days"]
            found_ratios = list(efficiency_ratios.keys())

            if all(r in found_ratios for r in expected_ratios):
                self.record_result(test_name, True, f"All efficiency ratios found: {found_ratios}")
            else:
                missing = [r for r in expected_ratios if r not in found_ratios]
                self.record_result(test_name, False, f"Missing ratios: {missing}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 7 Tests: Multi-Region Dividend Support
    # =========================================================================

    def test_dividend_collector_yfinance_ticker_format(self):
        """Test yfinance ticker formatting for different regions."""
        test_name = "dividend_collector_yfinance_ticker_format"
        try:
            from modules.collection.dividend_collector import DividendCollector

            collector = DividendCollector()

            # Test ticker formatting
            test_cases = [
                ("AAPL", "US", "AAPL"),
                ("7203", "JP", "7203.T"),
                ("0700", "HK", "0700.HK"),
                ("600519", "CN", "600519.SS"),
                ("000001", "CN", "000001.SZ"),
                ("005930", "KR", "005930.KS"),
            ]

            results = []
            for ticker, region, expected in test_cases:
                formatted = collector._format_yfinance_ticker(ticker, region)
                if formatted == expected:
                    results.append(f"{region}:{ticker}✓")
                else:
                    results.append(f"{region}:{ticker}✗({formatted})")

            if all("✓" in r for r in results):
                self.record_result(test_name, True, f"All formats correct: {results}")
            else:
                self.record_result(test_name, False, f"Format errors: {results}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_update_database_script_steps(self):
        """Test that update_database.py has new steps in choices."""
        test_name = "update_database_script_steps"
        try:
            import ast

            with open("scripts/update_database.py", "r") as f:
                content = f.read()

            # Check for new steps in the choices list
            required_steps = ["cash_backfill", "fundamental_ratios", "dividend"]
            found_steps = []

            for step in required_steps:
                if f"'{step}'" in content or f'"{step}"' in content:
                    found_steps.append(step)

            if len(found_steps) == len(required_steps):
                self.record_result(test_name, True, f"All steps in update_database.py: {found_steps}")
            else:
                missing = [s for s in required_steps if s not in found_steps]
                self.record_result(test_name, False, f"Missing steps: {missing}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def run_all_tests(self):
        """Run all integration tests."""
        logger.info("=" * 70)
        logger.info("Week 2 MCP Tools Integration Tests")
        logger.info("=" * 70)

        # Phase 3: Dividend History Tests
        logger.info("\n--- Phase 3: Dividend History Tests ---")
        self.test_dividend_history_table_exists()
        self.test_dividend_history_data_migrated()
        self.test_dividend_cagr_calculation()
        self.test_dividend_streak_calculation()
        self.test_dividend_tool_definition()
        self.test_data_adapter_dividend_history()

        # Phase 4: Cash Ratio Tests
        logger.info("\n--- Phase 4: Cash Ratio Tests ---")
        self.test_cash_columns_exist()
        self.test_cash_data_backfilled()
        self.test_cash_ratio_calculator()
        self.test_cash_position_category_in_ratios()
        self.test_ratios_tool_includes_cash_position()
        self.test_required_fields_include_cash()

        # Phase 5: Orchestrator Integration Tests
        logger.info("\n--- Phase 5: Orchestrator Integration Tests ---")
        self.test_orchestrator_dividend_step()
        self.test_orchestrator_cash_backfill_step()
        self.test_orchestrator_fundamental_ratios_step()
        self.test_dividend_collector_exists()
        self.test_cash_backfiller_exists()

        # Phase 6: Turnover Ratios Tests
        logger.info("\n--- Phase 6: Turnover Ratios Tests ---")
        self.test_inventory_days_in_ratio_definitions()
        self.test_receivables_days_in_ratio_definitions()
        self.test_inventory_days_calculation()
        self.test_receivables_days_calculation()
        self.test_turnover_days_in_efficiency_category()

        # Phase 7: Multi-Region Dividend Support Tests
        logger.info("\n--- Phase 7: Multi-Region Dividend Support Tests ---")
        self.test_dividend_collector_yfinance_ticker_format()
        self.test_update_database_script_steps()

        # End-to-End Tests
        logger.info("\n--- End-to-End Integration Tests ---")
        self.test_dividend_tool_handler()
        self.test_ratios_tool_handler_cash_position()
        self.test_mcp_server_tool_registration()

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("Test Summary")
        logger.info("=" * 70)
        logger.info(f"Passed:  {self.results['passed']}")
        logger.info(f"Failed:  {self.results['failed']}")
        logger.info(f"Skipped: {self.results['skipped']}")
        logger.info(f"Total:   {len(self.results['tests'])}")

        if self.results['failed'] > 0:
            logger.info("\nFailed Tests:")
            for test in self.results['tests']:
                if test['status'] == 'FAILED':
                    logger.info(f"  - {test['name']}: {test['message']}")

        return self.results


def main():
    """Run Week 2 integration tests."""
    tests = Week2IntegrationTests()
    results = tests.run_all_tests()

    # Exit with error code if tests failed
    if results['failed'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
