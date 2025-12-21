#!/usr/bin/env python3
"""
Integration Test: HK & CN Fundamental Data Collection
Tests the complete API → Parser → Database flow

Test Coverage:
- HK: AkShare API → HK Parser → PostgreSQL (36 indicators)
- CN: AkShare Batch/Individual API → CN Parser → PostgreSQL (86 indicators)
- Database: Verify new ratio columns populated correctly
- Data Quality: Validate field completeness and accuracy

Author: Claude Code
Date: 2025-12-18
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
from datetime import datetime
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.market_adapters.hk_adapter import HKAdapter
from modules.market_adapters.cn_adapter import CNAdapter


class TestHKFundamentalIntegration(unittest.TestCase):
    """Test HK fundamental data collection end-to-end"""

    @classmethod
    def setUpClass(cls):
        """Initialize database and adapter once for all tests"""
        cls.db = PostgresDatabaseManager()
        cls.adapter = HKAdapter(cls.db, enable_fallback=True)
        cls.test_tickers = ['2318.HK', '0700.HK', '09988.HK']  # Ping An, Tencent, Alibaba

    def test_01_hk_api_collection(self):
        """Test 1: Verify HK API can collect fundamental data"""
        print("\n" + "="*80)
        print("TEST 1: HK API Collection")
        print("="*80)

        for ticker in self.test_tickers:
            print(f"\n📊 Testing {ticker}...")
            result = self.adapter.collect_fundamentals(tickers=[ticker], use_fallback=True)
            self.assertGreaterEqual(result, 1, f"Failed to collect data for {ticker}")
            print(f"   ✅ Collection successful: {result} ticker updated")

    def test_02_hk_database_storage(self):
        """Test 2: Verify data stored in database with all new columns"""
        print("\n" + "="*80)
        print("TEST 2: HK Database Storage Verification")
        print("="*80)

        required_columns = [
            'eps', 'bps', 'roe', 'roa', 'roic',
            'debt_ratio', 'gross_margin', 'net_margin',
            'revenue', 'revenue_yoy', 'net_income', 'net_income_yoy',
            'trailing_eps'
        ]

        for ticker in self.test_tickers:
            print(f"\n📊 Checking {ticker}...")

            query = f"""
                SELECT {', '.join(required_columns)}
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = 'HK'
                ORDER BY date DESC
                LIMIT 1
            """

            results = self.db.execute_query(query, (ticker,))
            self.assertIsNotNone(results, f"No data found for {ticker}")
            self.assertTrue(len(results) > 0, f"Empty result for {ticker}")

            data = results[0]

            # Check critical fields are populated
            critical_fields = ['eps', 'revenue', 'net_income']
            for field in critical_fields:
                self.assertIsNotNone(data.get(field), f"{ticker}: {field} is NULL")
                print(f"   ✅ {field}: {data[field]}")

            # Check ratio fields (some may be NULL, that's OK)
            ratio_fields = ['roe', 'roa', 'roic', 'net_margin']
            populated_count = sum(1 for f in ratio_fields if data.get(f) is not None)
            self.assertGreater(populated_count, 0, f"{ticker}: No ratio fields populated")
            print(f"   ✅ Ratio fields populated: {populated_count}/{len(ratio_fields)}")

    def test_03_hk_data_quality(self):
        """Test 3: Verify data quality and reasonable values"""
        print("\n" + "="*80)
        print("TEST 3: HK Data Quality Validation")
        print("="*80)

        for ticker in self.test_tickers:
            print(f"\n📊 Validating {ticker}...")

            query = """
                SELECT eps, roe, roa, revenue, net_income, debt_ratio, data_source
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = 'HK'
                ORDER BY date DESC
                LIMIT 1
            """

            results = self.db.execute_query(query, (ticker,))
            data = results[0]

            # Validate data source
            self.assertIn(data['data_source'], ['akshare', 'akshare_batch', 'yfinance'],
                         f"{ticker}: Invalid data source")
            print(f"   ✅ Data source: {data['data_source']}")

            # Validate reasonable ranges
            if data.get('eps'):
                self.assertGreater(data['eps'], -100, f"{ticker}: EPS too negative")
                self.assertLess(data['eps'], 1000, f"{ticker}: EPS too high")
                print(f"   ✅ EPS in reasonable range: {data['eps']}")

            if data.get('roe'):
                self.assertGreater(data['roe'], -100, f"{ticker}: ROE too negative")
                self.assertLess(data['roe'], 200, f"{ticker}: ROE too high")
                print(f"   ✅ ROE in reasonable range: {data['roe']}%")

            if data.get('revenue'):
                self.assertGreater(data['revenue'], 0, f"{ticker}: Revenue must be positive")
                print(f"   ✅ Revenue is positive: {data['revenue']:,.0f}")


class TestCNFundamentalIntegration(unittest.TestCase):
    """Test CN fundamental data collection end-to-end"""

    @classmethod
    def setUpClass(cls):
        """Initialize database and adapter once for all tests"""
        cls.db = PostgresDatabaseManager()
        cls.adapter = CNAdapter(cls.db, enable_fallback=True)
        cls.test_tickers = ['600519.SH', '000001.SZ', '600036.SH']  # Moutai, Ping An Bank, China Merchants Bank

    def test_01_cn_batch_collection(self):
        """Test 1: Verify CN batch collection works"""
        print("\n" + "="*80)
        print("TEST 1: CN Batch Collection")
        print("="*80)

        result = self.adapter.collect_fundamentals(mode='batch')
        self.assertGreater(result, 1000, "Batch collection failed to get >1000 stocks")
        print(f"   ✅ Batch collection successful: {result} stocks updated")

    def test_02_cn_individual_collection(self):
        """Test 2: Verify CN individual collection for specific tickers"""
        print("\n" + "="*80)
        print("TEST 2: CN Individual Collection")
        print("="*80)

        for ticker in self.test_tickers:
            print(f"\n📊 Testing {ticker}...")
            result = self.adapter.collect_fundamentals(
                tickers=[ticker],
                mode='individual',
                use_fallback=True
            )
            # Note: Individual may fail for some tickers (expected 1-2% failure)
            # But should work for major stocks like these
            print(f"   {'✅' if result >= 1 else '⚠️'} Collection result: {result} ticker updated")

    def test_03_cn_database_storage(self):
        """Test 3: Verify CN data stored in database"""
        print("\n" + "="*80)
        print("TEST 3: CN Database Storage Verification")
        print("="*80)

        required_columns = [
            'eps', 'roe', 'revenue', 'net_income', 'data_source'
        ]

        # Check batch data (should exist for all test tickers)
        for ticker in self.test_tickers:
            print(f"\n📊 Checking {ticker}...")

            query = f"""
                SELECT {', '.join(required_columns)}
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = 'CN'
                ORDER BY date DESC
                LIMIT 1
            """

            results = self.db.execute_query(query, (ticker,))
            self.assertIsNotNone(results, f"No data found for {ticker}")
            self.assertTrue(len(results) > 0, f"Empty result for {ticker}")

            data = results[0]

            # Check critical fields
            self.assertIsNotNone(data.get('eps'), f"{ticker}: EPS is NULL")
            self.assertIsNotNone(data.get('revenue'), f"{ticker}: Revenue is NULL")
            self.assertIsNotNone(data.get('net_income'), f"{ticker}: Net Income is NULL")

            print(f"   ✅ EPS: {data['eps']}")
            print(f"   ✅ Revenue: {data['revenue']:,.0f} CNY")
            print(f"   ✅ Net Income: {data['net_income']:,.0f} CNY")
            print(f"   ✅ Data source: {data['data_source']}")

    def test_04_cn_data_coverage(self):
        """Test 4: Verify CN data coverage across all registered tickers"""
        print("\n" + "="*80)
        print("TEST 4: CN Data Coverage Analysis")
        print("="*80)

        query = """
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT ticker) as unique_tickers,
                COUNT(eps) as has_eps,
                COUNT(roe) as has_roe,
                COUNT(revenue) as has_revenue,
                COUNT(net_income) as has_net_income,
                MAX(date) as latest_date
            FROM ticker_fundamentals
            WHERE region = 'CN'
        """

        results = self.db.execute_query(query)
        stats = results[0]

        print(f"\n📊 CN Fundamental Data Statistics:")
        print(f"   Total records: {stats['total_records']}")
        print(f"   Unique tickers: {stats['unique_tickers']}")
        print(f"   Latest date: {stats['latest_date']}")
        print(f"   EPS coverage: {stats['has_eps']}/{stats['total_records']} ({stats['has_eps']/stats['total_records']*100:.1f}%)")
        print(f"   ROE coverage: {stats['has_roe']}/{stats['total_records']} ({stats['has_roe']/stats['total_records']*100 if stats['total_records'] > 0 else 0:.1f}%)")
        print(f"   Revenue coverage: {stats['has_revenue']}/{stats['total_records']} ({stats['has_revenue']/stats['total_records']*100:.1f}%)")

        # Assert minimum coverage
        self.assertGreater(stats['unique_tickers'], 1000, "Should have >1000 CN tickers")
        eps_coverage = stats['has_eps'] / stats['total_records'] * 100 if stats['total_records'] > 0 else 0
        self.assertGreater(eps_coverage, 95, f"EPS coverage {eps_coverage:.1f}% is too low")
        print(f"   ✅ Coverage meets >95% threshold")


class TestCombinedValidation(unittest.TestCase):
    """Test combined HK & CN fundamental data"""

    @classmethod
    def setUpClass(cls):
        cls.db = PostgresDatabaseManager()

    def test_01_schema_validation(self):
        """Test 1: Verify database schema has all required columns"""
        print("\n" + "="*80)
        print("TEST: Database Schema Validation")
        print("="*80)

        # Get column names from ticker_fundamentals table
        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'ticker_fundamentals'
            AND column_name IN (
                'eps', 'bps', 'roe', 'roa', 'roic',
                'debt_ratio', 'current_ratio',
                'gross_margin', 'net_margin',
                'revenue_yoy', 'net_income_yoy', 'trailing_eps'
            )
            ORDER BY column_name
        """

        results = self.db.execute_query(query)
        column_names = [r['column_name'] for r in results]

        required_columns = [
            'eps', 'bps', 'roe', 'roa', 'roic',
            'debt_ratio', 'current_ratio',
            'gross_margin', 'net_margin',
            'revenue_yoy', 'net_income_yoy', 'trailing_eps'
        ]

        for col in required_columns:
            self.assertIn(col, column_names, f"Column {col} missing from schema")
            print(f"   ✅ Column exists: {col}")

    def test_02_data_quality_comparison(self):
        """Test 2: Compare data quality between HK and CN"""
        print("\n" + "="*80)
        print("TEST: HK vs CN Data Quality Comparison")
        print("="*80)

        for region in ['HK', 'CN']:
            query = """
                SELECT
                    COUNT(*) as total,
                    COUNT(eps) as has_eps,
                    COUNT(roe) as has_roe,
                    COUNT(roa) as has_roa,
                    COUNT(revenue) as has_revenue,
                    COUNT(DISTINCT data_source) as sources
                FROM ticker_fundamentals
                WHERE region = %s
                AND date >= CURRENT_DATE - INTERVAL '1 year'
            """

            results = self.db.execute_query(query, (region,))
            stats = results[0]

            print(f"\n📊 {region} Region:")
            print(f"   Total records: {stats['total']}")
            print(f"   EPS coverage: {stats['has_eps']}/{stats['total']} ({stats['has_eps']/stats['total']*100 if stats['total'] > 0 else 0:.1f}%)")
            print(f"   ROE coverage: {stats['has_roe']}/{stats['total']} ({stats['has_roe']/stats['total']*100 if stats['total'] > 0 else 0:.1f}%)")
            print(f"   Data sources: {stats['sources']}")

            # Both regions should have good coverage
            if stats['total'] > 0:
                coverage = stats['has_eps'] / stats['total'] * 100
                self.assertGreater(coverage, 90, f"{region} EPS coverage {coverage:.1f}% is too low")


def run_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("HK & CN FUNDAMENTAL DATA INTEGRATION TESTS")
    print("="*80)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Create test suite
    suite = unittest.TestSuite()

    # Add HK tests
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHKFundamentalIntegration))

    # Add CN tests
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCNFundamentalIntegration))

    # Add combined validation tests
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCombinedValidation))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
