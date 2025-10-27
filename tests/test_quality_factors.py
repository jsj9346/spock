#!/usr/bin/env python3
"""
Unit Tests for Quality Factors - Week 2 Task 3 (PostgreSQL Version)

Tests all 9 quality factors with PostgreSQL integration:
- Profitability: ROE, ROA, Operating Margin, Net Profit Margin
- Liquidity: Current Ratio, Quick Ratio
- Leverage: Debt-to-Equity
- Earnings Quality: Accruals Ratio, CF-to-NI Ratio

Author: Quant Platform Development Team
Date: 2025-10-23
"""

import sys
import os
import unittest
import psycopg2
from datetime import date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.factors.quality_factors import (
    ROEFactor,
    ROAFactor,
    OperatingMarginFactor,
    NetProfitMarginFactor,
    CurrentRatioFactor,
    QuickRatioFactor,
    DebtToEquityFactor,
    AccrualsRatioFactor,
    CFToNIRatioFactor
)


class TestQualityFactors(unittest.TestCase):
    """Test suite for Quality Factors with PostgreSQL"""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection and create test data"""
        cls.conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER')
        )
        cls.test_ticker = 'TEST_QUALITY'
        cls.test_region = 'US'
        cls.test_date = date.today()

        # Create test ticker in tickers table (required for foreign key)
        cursor = cls.conn.cursor()
        cursor.execute("""
            INSERT INTO tickers (ticker, region, name, exchange, currency, asset_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region) DO NOTHING
        """, (cls.test_ticker, cls.test_region, 'Test Quality Company', 'TEST', 'USD', 'STOCK'))
        cls.conn.commit()
        cursor.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test data and close connection"""
        # Rollback any failed transactions first
        cls.conn.rollback()

        cursor = cls.conn.cursor()
        # Delete test fundamentals first (foreign key)
        cursor.execute("""
            DELETE FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s
        """, (cls.test_ticker, cls.test_region))
        # Delete test ticker
        cursor.execute("""
            DELETE FROM tickers
            WHERE ticker = %s AND region = %s
        """, (cls.test_ticker, cls.test_region))
        cls.conn.commit()
        cursor.close()
        cls.conn.close()

    def setUp(self):
        """Clear test data before each test"""
        # Rollback any failed transactions first
        self.conn.rollback()

        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s
        """, (self.test_ticker, self.test_region))
        self.conn.commit()
        cursor.close()

    def insert_test_fundamentals(self, **kwargs):
        """
        Helper method to insert test fundamental data

        Args:
            **kwargs: Fundamental metrics (net_income, total_equity, etc.)
        """
        cursor = self.conn.cursor()

        # Default values
        data = {
            'ticker': self.test_ticker,
            'region': self.test_region,
            'date': self.test_date,
            'period_type': 'ANNUAL',
            'fiscal_year': 2024,
            'net_income': kwargs.get('net_income'),
            'total_equity': kwargs.get('total_equity'),
            'total_assets': kwargs.get('total_assets'),
            'revenue': kwargs.get('revenue'),
            'operating_profit': kwargs.get('operating_profit'),
            'current_assets': kwargs.get('current_assets'),
            'current_liabilities': kwargs.get('current_liabilities'),
            'inventory': kwargs.get('inventory'),
            'total_liabilities': kwargs.get('total_liabilities'),
            'operating_cash_flow': kwargs.get('operating_cash_flow'),
            'data_source': 'test'
        }

        cursor.execute("""
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year,
                net_income, total_equity, total_assets, revenue, operating_profit,
                current_assets, current_liabilities, inventory, total_liabilities,
                operating_cash_flow, data_source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['ticker'], data['region'], data['date'], data['period_type'], data['fiscal_year'],
            data['net_income'], data['total_equity'], data['total_assets'], data['revenue'], data['operating_profit'],
            data['current_assets'], data['current_liabilities'], data['inventory'], data['total_liabilities'],
            data['operating_cash_flow'], data['data_source']
        ))

        self.conn.commit()
        cursor.close()

    # ===========================
    # Profitability Factor Tests
    # ===========================

    def test_roe_factor_high_profitability(self):
        """Test ROE with high profitability (20% ROE)"""
        self.insert_test_fundamentals(
            net_income=20000000,  # $20M
            total_equity=100000000  # $100M
        )

        factor = ROEFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, self.test_ticker)
        self.assertEqual(result.factor_name, 'ROE')
        self.assertAlmostEqual(result.raw_value, 20.0, delta=0.1)
        self.assertEqual(result.metadata['fiscal_year'], 2024)

        print(f"\n✓ ROE High Profitability Test:")
        print(f"  Net Income: $20M, Equity: $100M")
        print(f"  ROE: {result.raw_value:.2f}%")

    def test_roe_factor_negative_equity(self):
        """Test ROE with negative equity (should return None)"""
        self.insert_test_fundamentals(
            net_income=10000000,
            total_equity=-50000000  # Negative equity
        )

        factor = ROEFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNone(result, "Should return None for negative equity")
        print(f"\n✓ ROE Negative Equity Test: Correctly returned None")

    def test_roa_factor_efficient_asset_use(self):
        """Test ROA with efficient asset utilization (10% ROA)"""
        self.insert_test_fundamentals(
            net_income=50000000,  # $50M
            total_assets=500000000  # $500M
        )

        factor = ROAFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'ROA')
        self.assertAlmostEqual(result.raw_value, 10.0, delta=0.1)

        print(f"\n✓ ROA Efficient Asset Use Test:")
        print(f"  Net Income: $50M, Assets: $500M")
        print(f"  ROA: {result.raw_value:.2f}%")

    def test_operating_margin_factor_high_efficiency(self):
        """Test Operating Margin with high operational efficiency (25%)"""
        self.insert_test_fundamentals(
            operating_profit=25000000,  # $25M
            revenue=100000000  # $100M
        )

        factor = OperatingMarginFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Operating_Margin')
        self.assertAlmostEqual(result.raw_value, 25.0, delta=0.1)

        print(f"\n✓ Operating Margin High Efficiency Test:")
        print(f"  Operating Profit: $25M, Revenue: $100M")
        print(f"  Operating Margin: {result.raw_value:.2f}%")

    def test_net_profit_margin_factor_profitable_business(self):
        """Test Net Profit Margin with profitable business (15%)"""
        self.insert_test_fundamentals(
            net_income=15000000,  # $15M
            revenue=100000000  # $100M
        )

        factor = NetProfitMarginFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Net_Profit_Margin')
        self.assertAlmostEqual(result.raw_value, 15.0, delta=0.1)

        print(f"\n✓ Net Profit Margin Profitable Business Test:")
        print(f"  Net Income: $15M, Revenue: $100M")
        print(f"  Net Profit Margin: {result.raw_value:.2f}%")

    # ========================
    # Liquidity Factor Tests
    # ========================

    def test_current_ratio_factor_healthy_liquidity(self):
        """Test Current Ratio with healthy liquidity (2.0x)"""
        self.insert_test_fundamentals(
            current_assets=200000000,  # $200M
            current_liabilities=100000000  # $100M
        )

        factor = CurrentRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Current_Ratio')
        self.assertAlmostEqual(result.raw_value, 200.0, delta=0.1)  # Stored as percentage

        print(f"\n✓ Current Ratio Healthy Liquidity Test:")
        print(f"  Current Assets: $200M, Current Liabilities: $100M")
        print(f"  Current Ratio: {result.raw_value/100:.2f}x")

    def test_quick_ratio_factor_with_inventory(self):
        """Test Quick Ratio excluding inventory (1.5x)"""
        self.insert_test_fundamentals(
            current_assets=200000000,  # $200M
            inventory=50000000,  # $50M
            current_liabilities=100000000  # $100M
        )

        factor = QuickRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Quick_Ratio')
        self.assertAlmostEqual(result.raw_value, 150.0, delta=0.1)  # (200-50)/100 = 1.5x = 150%

        print(f"\n✓ Quick Ratio With Inventory Test:")
        print(f"  Current Assets: $200M, Inventory: $50M, Current Liabilities: $100M")
        print(f"  Quick Ratio: {result.raw_value/100:.2f}x")

    def test_quick_ratio_factor_null_inventory(self):
        """Test Quick Ratio with null inventory (treat as zero)"""
        self.insert_test_fundamentals(
            current_assets=200000000,  # $200M
            inventory=None,  # No inventory
            current_liabilities=100000000  # $100M
        )

        factor = QuickRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, 200.0, delta=0.1)  # 200/100 = 2.0x

        print(f"\n✓ Quick Ratio Null Inventory Test:")
        print(f"  Inventory treated as zero")
        print(f"  Quick Ratio: {result.raw_value/100:.2f}x")

    # =======================
    # Leverage Factor Tests
    # =======================

    def test_debt_to_equity_factor_low_leverage(self):
        """Test Debt-to-Equity with low leverage (0.5x, conservative)"""
        self.insert_test_fundamentals(
            total_liabilities=50000000,  # $50M
            total_equity=100000000  # $100M
        )

        factor = DebtToEquityFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Debt_to_Equity')
        # Factor value is negated (lower debt = higher score)
        self.assertAlmostEqual(result.raw_value, -50.0, delta=0.1)
        self.assertEqual(result.metadata['debt_to_equity'], 50.0)  # Actual D/E ratio

        print(f"\n✓ Debt-to-Equity Low Leverage Test:")
        print(f"  Total Liabilities: $50M, Equity: $100M")
        print(f"  D/E Ratio: {result.metadata['debt_to_equity']/100:.2f}x (Conservative)")

    def test_debt_to_equity_factor_high_leverage(self):
        """Test Debt-to-Equity with high leverage (2.0x, aggressive)"""
        self.insert_test_fundamentals(
            total_liabilities=200000000,  # $200M
            total_equity=100000000  # $100M
        )

        factor = DebtToEquityFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, -200.0, delta=0.1)
        self.assertEqual(result.metadata['debt_to_equity'], 200.0)

        print(f"\n✓ Debt-to-Equity High Leverage Test:")
        print(f"  Total Liabilities: $200M, Equity: $100M")
        print(f"  D/E Ratio: {result.metadata['debt_to_equity']/100:.2f}x (Aggressive)")

    # ==============================
    # Earnings Quality Factor Tests
    # ==============================

    def test_accruals_ratio_factor_high_quality(self):
        """Test Accruals Ratio with high earnings quality (low accruals)"""
        self.insert_test_fundamentals(
            net_income=50000000,  # $50M
            operating_cash_flow=55000000,  # $55M (cash > earnings)
            total_assets=500000000  # $500M
        )

        factor = AccrualsRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Accruals_Ratio')
        # Accruals = 50M - 55M = -5M
        # Accruals Ratio = -5M / 500M = -0.01 (negated → +0.01)
        self.assertGreater(result.raw_value, 0)  # Positive score for low accruals

        print(f"\n✓ Accruals Ratio High Quality Test:")
        print(f"  Net Income: $50M, Cash Flow: $55M, Assets: $500M")
        print(f"  Accruals: ${(50-55)}M (Cash exceeds earnings = High quality)")
        print(f"  Accruals Ratio: {result.metadata['accruals_ratio']:.4f}")

    def test_accruals_ratio_factor_low_quality(self):
        """Test Accruals Ratio with low earnings quality (high accruals)"""
        self.insert_test_fundamentals(
            net_income=50000000,  # $50M
            operating_cash_flow=30000000,  # $30M (cash < earnings)
            total_assets=500000000  # $500M
        )

        factor = AccrualsRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        # Accruals = 50M - 30M = 20M
        # Accruals Ratio = 20M / 500M = 0.04 (negated → -0.04)
        self.assertLess(result.raw_value, 0)  # Negative score for high accruals

        print(f"\n✓ Accruals Ratio Low Quality Test:")
        print(f"  Net Income: $50M, Cash Flow: $30M, Assets: $500M")
        print(f"  Accruals: ${(50-30)}M (Earnings exceed cash = Low quality)")
        print(f"  Accruals Ratio: {result.metadata['accruals_ratio']:.4f}")

    def test_cf_to_ni_ratio_factor_cash_backed_earnings(self):
        """Test CF-to-NI Ratio with cash-backed earnings (ratio > 1.0)"""
        self.insert_test_fundamentals(
            operating_cash_flow=60000000,  # $60M
            net_income=50000000  # $50M
        )

        factor = CFToNIRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'CF_to_NI_Ratio')
        self.assertAlmostEqual(result.raw_value, 1.2, delta=0.1)  # 60/50 = 1.2

        print(f"\n✓ CF-to-NI Ratio Cash-Backed Earnings Test:")
        print(f"  Cash Flow: $60M, Net Income: $50M")
        print(f"  CF/NI Ratio: {result.raw_value:.2f} (High quality)")

    def test_cf_to_ni_ratio_factor_accrual_heavy_earnings(self):
        """Test CF-to-NI Ratio with accrual-heavy earnings (ratio < 1.0)"""
        self.insert_test_fundamentals(
            operating_cash_flow=30000000,  # $30M
            net_income=50000000  # $50M
        )

        factor = CFToNIRatioFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, 0.6, delta=0.1)  # 30/50 = 0.6

        print(f"\n✓ CF-to-NI Ratio Accrual-Heavy Earnings Test:")
        print(f"  Cash Flow: $30M, Net Income: $50M")
        print(f"  CF/NI Ratio: {result.raw_value:.2f} (Low quality)")

    # ===========================
    # Edge Case and Error Tests
    # ===========================

    def test_insufficient_data_returns_none(self):
        """Test that factors return None when data is missing"""
        # No data inserted

        factor = ROEFactor()
        result = factor.calculate(None, 'NONEXISTENT_TICKER', self.test_region)

        self.assertIsNone(result)
        print(f"\n✓ Insufficient Data Test: Correctly returned None")

    def test_zero_denominator_handling(self):
        """Test handling of zero denominators (should skip with validation)"""
        self.insert_test_fundamentals(
            net_income=10000000,
            total_equity=0  # Zero equity (invalid)
        )

        factor = ROEFactor()
        result = factor.calculate(None, self.test_ticker, self.test_region)

        self.assertIsNone(result, "Should return None for zero equity")
        print(f"\n✓ Zero Denominator Test: Correctly returned None")

    def test_multi_region_support(self):
        """Test that region parameter works correctly"""
        cursor = self.conn.cursor()

        # Create KR ticker first (required for foreign key)
        cursor.execute("""
            INSERT INTO tickers (ticker, region, name, exchange, currency, asset_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region) DO NOTHING
        """, (self.test_ticker, 'KR', 'Test Quality Company KR', 'KRX', 'KRW', 'STOCK'))

        # Insert data for KR region
        cursor.execute("""
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year,
                net_income, total_equity, data_source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.test_ticker, 'KR', self.test_date, 'ANNUAL', 2024, 20000000, 100000000, 'test'))
        self.conn.commit()
        cursor.close()

        factor = ROEFactor()
        result = factor.calculate(None, self.test_ticker, 'KR')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, self.test_ticker)

        # Clean up KR data
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM ticker_fundamentals WHERE ticker = %s AND region = 'KR'",
                      (self.test_ticker,))
        cursor.execute("DELETE FROM tickers WHERE ticker = %s AND region = 'KR'",
                      (self.test_ticker,))
        self.conn.commit()
        cursor.close()

        print(f"\n✓ Multi-Region Support Test: KR region works correctly")


def run_tests():
    """Run all tests and print results"""
    print("=" * 70)
    print("Quality Factors Unit Tests - Week 2 Task 3 (PostgreSQL)")
    print("=" * 70)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestQualityFactors)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
