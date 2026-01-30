#!/usr/bin/env python3
"""
Unit Tests for RatioCalculator - Turnover Ratios

Tests for:
- Inventory Turnover and Inventory Days
- Receivables Turnover and Receivables Days
- Edge cases (zero values, None values)
"""

import os
import sys
import unittest
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Skip this test module if mcp_server.calculators is not importable
try:
    from mcp_server.calculators.ratio_calculator import FinancialRatioCalculator as RatioCalculator, RATIO_DEFINITIONS
except ImportError:
    pytest.skip("mcp_server.calculators not available", allow_module_level=True)


class TestInventoryTurnoverRatios(unittest.TestCase):
    """Test inventory turnover and inventory days calculations."""

    def test_inventory_turnover_basic(self):
        """Test basic inventory turnover calculation."""
        data = {
            "cogs": 600000,
            "inventory": 100000
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_turnover()

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 6.0, places=2)

    def test_inventory_days_basic(self):
        """Test basic inventory days calculation."""
        data = {
            "cogs": 600000,
            "inventory": 100000  # Turnover = 6
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_days()

        self.assertIsNotNone(result)
        expected = 365.0 / 6  # ~60.83
        self.assertAlmostEqual(result, expected, places=2)

    def test_inventory_turnover_zero_inventory(self):
        """Test inventory turnover with zero inventory."""
        data = {
            "cogs": 600000,
            "inventory": 0
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_turnover()

        # Division by zero should return None
        self.assertIsNone(result)

    def test_inventory_days_zero_turnover(self):
        """Test inventory days when turnover is zero."""
        data = {
            "cogs": 600000,
            "inventory": 0  # Turnover will be None
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_days()

        self.assertIsNone(result)

    def test_inventory_turnover_none_values(self):
        """Test inventory turnover with None values."""
        data = {
            "cogs": None,
            "inventory": 100000
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_turnover()

        self.assertIsNone(result)

    def test_inventory_days_missing_data(self):
        """Test inventory days with missing data."""
        data = {}  # No data
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_days()

        self.assertIsNone(result)


class TestReceivablesTurnoverRatios(unittest.TestCase):
    """Test receivables turnover and receivables days calculations."""

    def test_receivables_turnover_basic(self):
        """Test basic receivables turnover calculation."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 100000
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_turnover()

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 10.0, places=2)

    def test_receivables_days_basic(self):
        """Test basic receivables days calculation."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 100000  # Turnover = 10
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_days()

        self.assertIsNotNone(result)
        expected = 365.0 / 10  # 36.5
        self.assertAlmostEqual(result, expected, places=2)

    def test_receivables_turnover_zero_receivables(self):
        """Test receivables turnover with zero receivables."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 0
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_turnover()

        self.assertIsNone(result)

    def test_receivables_days_zero_turnover(self):
        """Test receivables days when turnover is zero."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 0
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_days()

        self.assertIsNone(result)

    def test_receivables_days_high_turnover(self):
        """Test receivables days with high turnover (short collection period)."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 27397  # Turnover ≈ 36.5 => Days ≈ 10
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_days()

        self.assertIsNotNone(result)
        # Turnover = 1000000 / 27397 ≈ 36.5
        # Days = 365 / 36.5 ≈ 10
        self.assertAlmostEqual(result, 10.0, places=0)


class TestTurnoverDaysDefinitions(unittest.TestCase):
    """Test that turnover days are properly defined in RATIO_DEFINITIONS."""

    def test_inventory_days_definition_exists(self):
        """Test inventory_days is in RATIO_DEFINITIONS."""
        self.assertIn("efficiency", RATIO_DEFINITIONS)
        self.assertIn("inventory_days", RATIO_DEFINITIONS["efficiency"])

    def test_receivables_days_definition_exists(self):
        """Test receivables_days is in RATIO_DEFINITIONS."""
        self.assertIn("efficiency", RATIO_DEFINITIONS)
        self.assertIn("receivables_days", RATIO_DEFINITIONS["efficiency"])

    def test_inventory_days_definition_correct(self):
        """Test inventory_days definition is correct."""
        inv_days = RATIO_DEFINITIONS["efficiency"]["inventory_days"]

        self.assertEqual(inv_days["unit"], "days")
        self.assertEqual(inv_days["korean"], "재고자산회전일수")
        self.assertIn("365", inv_days["formula"])

    def test_receivables_days_definition_correct(self):
        """Test receivables_days definition is correct."""
        rec_days = RATIO_DEFINITIONS["efficiency"]["receivables_days"]

        self.assertEqual(rec_days["unit"], "days")
        self.assertEqual(rec_days["korean"], "매출채권회전일수")
        self.assertIn("365", rec_days["formula"])

    def test_inventory_days_healthy_range(self):
        """Test inventory_days has proper healthy range."""
        inv_days = RATIO_DEFINITIONS["efficiency"]["inventory_days"]

        # Lower is better for inventory days (faster turnover)
        healthy_range = inv_days.get("healthy_range", {})
        self.assertIn("max", healthy_range)
        self.assertLessEqual(healthy_range.get("max", 0), 120)  # Max ~4 months

    def test_receivables_days_healthy_range(self):
        """Test receivables_days has proper healthy range."""
        rec_days = RATIO_DEFINITIONS["efficiency"]["receivables_days"]

        # Lower is better for receivables days (faster collection)
        healthy_range = rec_days.get("healthy_range", {})
        self.assertIn("max", healthy_range)
        self.assertLessEqual(healthy_range.get("max", 0), 90)  # Max ~3 months


class TestEfficiencyCategoryCalculation(unittest.TestCase):
    """Test that efficiency category includes all turnover ratios."""

    def test_efficiency_category_includes_turnover_days(self):
        """Test efficiency category includes inventory_days and receivables_days."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 100000,
            "cogs": 600000,
            "inventory": 100000,
            "total_assets": 2000000
        }

        calculator = RatioCalculator(data)
        efficiency = calculator.calculate_category("efficiency")

        expected_ratios = [
            "asset_turnover",
            "inventory_turnover",
            "receivables_turnover",
            "inventory_days",
            "receivables_days"
        ]

        for ratio in expected_ratios:
            self.assertIn(ratio, efficiency, f"{ratio} not found in efficiency category")

    def test_efficiency_category_values_consistent(self):
        """Test that turnover and days values are consistent."""
        data = {
            "revenue": 1000000,
            "accounts_receivable": 100000,
            "cogs": 600000,
            "inventory": 100000,
            "total_assets": 2000000
        }

        calculator = RatioCalculator(data)
        efficiency = calculator.calculate_category("efficiency")

        # Check inventory consistency: turnover * days ≈ 365
        inv_turnover = efficiency.get("inventory_turnover", {}).get("value")
        inv_days = efficiency.get("inventory_days", {}).get("value")

        if inv_turnover and inv_days:
            self.assertAlmostEqual(inv_turnover * inv_days, 365.0, places=0)

        # Check receivables consistency: turnover * days ≈ 365
        rec_turnover = efficiency.get("receivables_turnover", {}).get("value")
        rec_days = efficiency.get("receivables_days", {}).get("value")

        if rec_turnover and rec_days:
            self.assertAlmostEqual(rec_turnover * rec_days, 365.0, places=0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for turnover calculations."""

    def test_very_high_turnover(self):
        """Test with very high turnover (less than 1 day)."""
        data = {
            "revenue": 365000000,
            "accounts_receivable": 100000  # Turnover = 3650
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_days()

        self.assertIsNotNone(result)
        self.assertLess(result, 1.0)  # Less than 1 day

    def test_very_low_turnover(self):
        """Test with very low turnover (over 1 year)."""
        data = {
            "revenue": 100000,
            "accounts_receivable": 500000  # Turnover = 0.2
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_receivables_days()

        self.assertIsNotNone(result)
        self.assertGreater(result, 365.0)  # Over 1 year

    def test_negative_values(self):
        """Test with negative values (invalid data)."""
        data = {
            "cogs": -600000,  # Negative COGS (invalid)
            "inventory": 100000
        }
        calculator = RatioCalculator(data)
        result = calculator.calculate_inventory_turnover()

        # Should still calculate (raw ratio), interpretation handles meaning
        self.assertIsNotNone(result)
        self.assertLess(result, 0)


if __name__ == "__main__":
    unittest.main()
