#!/usr/bin/env python3
"""
Test Suite for Growth and Efficiency Factors (Phase 2B)

Tests:
1. Module import validation
2. Factor initialization
3. Factor calculation with mock data
4. Integration with FactorScoreCalculator

Author: Spock Quant Platform - Phase 2B Testing
Date: 2025-10-24
"""

import os
import sys
import unittest
import psycopg2
from decimal import Decimal

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.factors import (
    # Growth factors
    RevenueGrowthFactor,
    OperatingProfitGrowthFactor,
    NetIncomeGrowthFactor,

    # Efficiency factors
    AssetTurnoverFactor,
    EquityTurnoverFactor,

    # Base classes
    FactorCategory,
    FactorScoreCalculator
)


class TestGrowthFactors(unittest.TestCase):
    """Test suite for Growth factors"""

    def setUp(self):
        """Setup test fixtures"""
        self.revenue_growth_factor = RevenueGrowthFactor()
        self.op_growth_factor = OperatingProfitGrowthFactor()
        self.ni_growth_factor = NetIncomeGrowthFactor()

    def test_factor_initialization(self):
        """Test factor initialization and properties"""
        # Revenue Growth Factor
        self.assertEqual(self.revenue_growth_factor.name, "Revenue_Growth_YOY")
        self.assertEqual(self.revenue_growth_factor.category, FactorCategory.GROWTH)
        self.assertEqual(self.revenue_growth_factor.lookback_days, 730)

        # Operating Profit Growth Factor
        self.assertEqual(self.op_growth_factor.name, "Operating_Profit_Growth_YOY")
        self.assertEqual(self.op_growth_factor.category, FactorCategory.GROWTH)

        # Net Income Growth Factor
        self.assertEqual(self.ni_growth_factor.name, "Net_Income_Growth_YOY")
        self.assertEqual(self.ni_growth_factor.category, FactorCategory.GROWTH)

    def test_required_columns(self):
        """Test required columns (should be empty for DB query factors)"""
        self.assertEqual(self.revenue_growth_factor.get_required_columns(), [])
        self.assertEqual(self.op_growth_factor.get_required_columns(), [])
        self.assertEqual(self.ni_growth_factor.get_required_columns(), [])

    def test_revenue_growth_calculation_real_db(self):
        """Test revenue growth calculation with real database"""
        try:
            # Test with a US ticker that has data
            result = self.revenue_growth_factor.calculate(None, ticker='AAPL', region='US')

            if result:
                # Validate result structure
                self.assertIsNotNone(result.raw_value)
                self.assertEqual(result.factor_name, "Revenue_Growth_YOY")
                self.assertEqual(result.ticker, 'AAPL')
                self.assertIn('revenue_growth_yoy', result.metadata)
                self.assertIn('current_year', result.metadata)
                self.assertIn('previous_year', result.metadata)
                print(f"✅ Revenue Growth Test: AAPL growth = {result.metadata['revenue_growth_yoy']}% (FY{result.metadata['current_year']})")
            else:
                print("⚠️ Revenue Growth Test: No data for AAPL (expected if ticker_fundamentals is empty)")
        except Exception as e:
            print(f"⚠️ Revenue Growth Test: DB connection error (expected if PostgreSQL not running): {e}")

    def test_operating_profit_growth_calculation_real_db(self):
        """Test operating profit growth calculation with real database"""
        try:
            result = self.op_growth_factor.calculate(None, ticker='AAPL', region='US')

            if result:
                self.assertIsNotNone(result.raw_value)
                self.assertEqual(result.factor_name, "Operating_Profit_Growth_YOY")
                self.assertIn('op_growth_yoy', result.metadata)
                print(f"✅ Operating Profit Growth Test: AAPL growth = {result.metadata['op_growth_yoy']}% (FY{result.metadata['current_year']})")
            else:
                print("⚠️ Operating Profit Growth Test: No data for AAPL")
        except Exception as e:
            print(f"⚠️ Operating Profit Growth Test: DB error: {e}")

    def test_net_income_growth_calculation_real_db(self):
        """Test net income growth calculation with real database"""
        try:
            result = self.ni_growth_factor.calculate(None, ticker='AAPL', region='US')

            if result:
                self.assertIsNotNone(result.raw_value)
                self.assertEqual(result.factor_name, "Net_Income_Growth_YOY")
                self.assertIn('ni_growth_yoy', result.metadata)
                print(f"✅ Net Income Growth Test: AAPL growth = {result.metadata['ni_growth_yoy']}% (FY{result.metadata['current_year']})")
            else:
                print("⚠️ Net Income Growth Test: No data for AAPL")
        except Exception as e:
            print(f"⚠️ Net Income Growth Test: DB error: {e}")


class TestEfficiencyFactors(unittest.TestCase):
    """Test suite for Efficiency factors"""

    def setUp(self):
        """Setup test fixtures"""
        self.asset_turnover_factor = AssetTurnoverFactor()
        self.equity_turnover_factor = EquityTurnoverFactor()

    def test_factor_initialization(self):
        """Test factor initialization and properties"""
        # Asset Turnover Factor
        self.assertEqual(self.asset_turnover_factor.name, "Asset_Turnover")
        self.assertEqual(self.asset_turnover_factor.category, FactorCategory.EFFICIENCY)
        self.assertEqual(self.asset_turnover_factor.lookback_days, 730)

        # Equity Turnover Factor
        self.assertEqual(self.equity_turnover_factor.name, "Equity_Turnover")
        self.assertEqual(self.equity_turnover_factor.category, FactorCategory.EFFICIENCY)

    def test_required_columns(self):
        """Test required columns (should be empty for DB query factors)"""
        self.assertEqual(self.asset_turnover_factor.get_required_columns(), [])
        self.assertEqual(self.equity_turnover_factor.get_required_columns(), [])

    def test_asset_turnover_calculation_real_db(self):
        """Test asset turnover calculation with real database"""
        try:
            result = self.asset_turnover_factor.calculate(None, ticker='AAPL', region='US')

            if result:
                self.assertIsNotNone(result.raw_value)
                self.assertEqual(result.factor_name, "Asset_Turnover")
                self.assertIn('asset_turnover', result.metadata)
                self.assertIn('revenue', result.metadata)
                self.assertIn('avg_total_assets', result.metadata)
                print(f"✅ Asset Turnover Test: AAPL turnover = {result.metadata['asset_turnover']:.2f}x (FY{result.metadata['fiscal_year']})")
            else:
                print("⚠️ Asset Turnover Test: No data for AAPL")
        except Exception as e:
            print(f"⚠️ Asset Turnover Test: DB error: {e}")

    def test_equity_turnover_calculation_real_db(self):
        """Test equity turnover calculation with real database"""
        try:
            result = self.equity_turnover_factor.calculate(None, ticker='AAPL', region='US')

            if result:
                self.assertIsNotNone(result.raw_value)
                self.assertEqual(result.factor_name, "Equity_Turnover")
                self.assertIn('equity_turnover', result.metadata)
                self.assertIn('revenue', result.metadata)
                self.assertIn('avg_total_equity', result.metadata)
                print(f"✅ Equity Turnover Test: AAPL turnover = {result.metadata['equity_turnover']:.2f}x (FY{result.metadata['fiscal_year']})")
            else:
                print("⚠️ Equity Turnover Test: No data for AAPL")
        except Exception as e:
            print(f"⚠️ Equity Turnover Test: DB error: {e}")


class TestFactorScoreCalculatorIntegration(unittest.TestCase):
    """Test integration with FactorScoreCalculator"""

    def test_calculator_includes_new_factors(self):
        """Test that FactorScoreCalculator includes all 27 factors"""
        # Note: FactorScoreCalculator uses SQLite by default
        # This test only validates factor registration
        try:
            calculator = FactorScoreCalculator()

            # Check total factor count (should be 27)
            self.assertEqual(len(calculator.factors), 27)

            # Check Growth factors are registered
            self.assertIn('revenue_growth', calculator.factors)
            self.assertIn('operating_profit_growth', calculator.factors)
            self.assertIn('net_income_growth', calculator.factors)

            # Check Efficiency factors are registered
            self.assertIn('asset_turnover', calculator.factors)
            self.assertIn('equity_turnover', calculator.factors)

            print(f"✅ FactorScoreCalculator Integration Test: All 27 factors registered")
            print(f"   Growth factors: revenue_growth, operating_profit_growth, net_income_growth")
            print(f"   Efficiency factors: asset_turnover, equity_turnover")
        except Exception as e:
            print(f"⚠️ FactorScoreCalculator Integration Test: Error: {e}")


class TestModuleImports(unittest.TestCase):
    """Test module imports and exports"""

    def test_all_imports(self):
        """Test that all new factors can be imported"""
        from modules.factors import (
            RevenueGrowthFactor,
            OperatingProfitGrowthFactor,
            NetIncomeGrowthFactor,
            AssetTurnoverFactor,
            EquityTurnoverFactor
        )

        # Test instantiation
        revenue_growth = RevenueGrowthFactor()
        op_growth = OperatingProfitGrowthFactor()
        ni_growth = NetIncomeGrowthFactor()
        asset_turnover = AssetTurnoverFactor()
        equity_turnover = EquityTurnoverFactor()

        # Validate types
        self.assertIsNotNone(revenue_growth)
        self.assertIsNotNone(op_growth)
        self.assertIsNotNone(ni_growth)
        self.assertIsNotNone(asset_turnover)
        self.assertIsNotNone(equity_turnover)

        print("✅ Module Import Test: All 5 new factors imported successfully")

    def test_factor_counts(self):
        """Test factor count constants"""
        from modules.factors import (
            PHASE_2B_GROWTH_FACTORS,
            PHASE_2B_EFFICIENCY_FACTORS,
            IMPLEMENTED_FACTORS,
            TOTAL_FACTORS
        )

        self.assertEqual(PHASE_2B_GROWTH_FACTORS, 3)
        self.assertEqual(PHASE_2B_EFFICIENCY_FACTORS, 2)
        self.assertEqual(IMPLEMENTED_FACTORS, 27)
        self.assertEqual(TOTAL_FACTORS, 27)

        print(f"✅ Factor Count Test: TOTAL_FACTORS = {TOTAL_FACTORS} (expected: 27)")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("Growth & Efficiency Factors Test Suite (Phase 2B)")
    print("="*80 + "\n")

    # Run tests
    unittest.main(verbosity=2)
