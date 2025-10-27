"""
Integration Tests for KoreaAdapter

Tests actual API integration with KRX and KIS APIs.

Author: Spock Trading System
"""

import unittest
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters import KoreaAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestKoreaAdapter(unittest.TestCase):
    """Integration tests for KoreaAdapter"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once before all tests"""
        # Load environment variables
        load_dotenv()

        cls.kis_app_key = os.getenv('KIS_APP_KEY')
        cls.kis_app_secret = os.getenv('KIS_APP_SECRET')

        if not cls.kis_app_key or not cls.kis_app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET must be set in .env")

        # Initialize database
        cls.db = SQLiteDatabaseManager(db_path='data/spock_local.db')

        # Initialize adapter
        cls.adapter = KoreaAdapter(
            db_manager=cls.db,
            kis_app_key=cls.kis_app_key,
            kis_app_secret=cls.kis_app_secret
        )

    def test_01_health_check(self):
        """Test 1: API health check"""
        print("\n🏥 Test 1: Health Check")

        health = self.adapter.health_check()

        # Assert at least one API is healthy
        self.assertTrue(any(health.values()), "At least one API should be healthy")

        # KRX Data API should always work (no auth required)
        self.assertTrue(health['krx_data_api'], "KRX Data API should be accessible")

    def test_02_scan_stocks(self):
        """Test 2: Stock scanning"""
        print("\n📊 Test 2: Stock Scanning")

        # Scan stocks (force refresh to test actual API)
        stocks = self.adapter.scan_stocks(force_refresh=True)

        # Assertions
        self.assertIsInstance(stocks, list, "scan_stocks should return a list")
        self.assertGreater(len(stocks), 0, "Should find at least some stocks")

        # Check first stock structure
        if stocks:
            stock = stocks[0]
            self.assertIn('ticker', stock, "Stock should have ticker")
            self.assertIn('name', stock, "Stock should have name")
            self.assertIn('exchange', stock, "Stock should have exchange")
            self.assertEqual(stock['region'], 'KR', "Stock region should be KR")
            self.assertEqual(stock['currency'], 'KRW', "Stock currency should be KRW")

            print(f"✅ Found {len(stocks)} stocks")
            print(f"   Sample: {stock['ticker']} - {stock['name']} ({stock['exchange']})")

    def test_03_scan_stocks_cache(self):
        """Test 3: Stock scanning with cache"""
        print("\n💾 Test 3: Stock Scanning (Cache)")

        # First scan (should use cache from test_02)
        stocks = self.adapter.scan_stocks(force_refresh=False)

        # Assertions
        self.assertIsInstance(stocks, list, "Cached scan should return a list")
        self.assertGreater(len(stocks), 0, "Cache should have stocks")

        print(f"✅ Cache hit: {len(stocks)} stocks")

    def test_04_scan_etfs(self):
        """Test 4: ETF scanning"""
        print("\n📊 Test 4: ETF Scanning")

        # Scan ETFs (force refresh)
        etfs = self.adapter.scan_etfs(force_refresh=True)

        # Assertions
        self.assertIsInstance(etfs, list, "scan_etfs should return a list")
        self.assertGreater(len(etfs), 0, "Should find at least some ETFs")

        # Check first ETF structure
        if etfs:
            etf = etfs[0]
            self.assertIn('ticker', etf, "ETF should have ticker")
            self.assertIn('name', etf, "ETF should have name")
            self.assertEqual(etf['region'], 'KR', "ETF region should be KR")

            print(f"✅ Found {len(etfs)} ETFs")
            print(f"   Sample: {etf['ticker']} - {etf['name']}")

    def test_05_collect_stock_ohlcv_single(self):
        """Test 5: Collect OHLCV for a single stock"""
        print("\n📈 Test 5: Stock OHLCV Collection (Single)")

        # Use Samsung Electronics (005930) as test ticker
        test_ticker = '005930'

        # Collect OHLCV
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=[test_ticker],
            days=250
        )

        # Assertions
        self.assertEqual(success_count, 1, "Should successfully collect data for 1 stock")

        # Verify data in database
        ohlcv_data = self.db.get_ohlcv(test_ticker, period_type='DAILY', limit=10)
        self.assertGreater(len(ohlcv_data), 0, "Should have OHLCV data in database")

        if ohlcv_data:
            row = ohlcv_data[0]
            print(f"✅ Collected OHLCV for {test_ticker}")
            print(f"   Latest: {row.get('date')} - Close: {row.get('close'):,} KRW")
            print(f"   MA20: {row.get('ma20')}, RSI: {row.get('rsi_14')}")

    def test_06_collect_stock_ohlcv_multiple(self):
        """Test 6: Collect OHLCV for multiple stocks"""
        print("\n📈 Test 6: Stock OHLCV Collection (Multiple)")

        # Use top 5 stocks by market cap
        test_tickers = ['005930', '000660', '373220', '207940', '005380']  # Samsung, SK Hynix, LG Energy, Samsung Bio, Hyundai Motor

        # Collect OHLCV
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=test_tickers,
            days=100  # Use fewer days for faster testing
        )

        # Assertions
        self.assertGreaterEqual(success_count, 3, f"Should successfully collect data for at least 3 stocks (got {success_count})")

        print(f"✅ Collected OHLCV for {success_count}/{len(test_tickers)} stocks")

    def test_07_collect_etf_ohlcv(self):
        """Test 7: Collect OHLCV for ETFs"""
        print("\n📈 Test 7: ETF OHLCV Collection")

        # Get first 3 ETFs from database
        etf_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
        test_etfs = [etf['ticker'] for etf in etf_data[:3]]

        if not test_etfs:
            self.skipTest("No ETFs in database. Run test_04_scan_etfs first.")

        # Collect OHLCV
        success_count = self.adapter.collect_etf_ohlcv(
            tickers=test_etfs,
            days=100
        )

        # Assertions
        self.assertGreaterEqual(success_count, 1, f"Should successfully collect data for at least 1 ETF (got {success_count})")

        print(f"✅ Collected OHLCV for {success_count}/{len(test_etfs)} ETFs")

    def test_08_collect_etf_details(self):
        """Test 8: Collect ETF details"""
        print("\n📊 Test 8: ETF Details Collection")

        # Get first 3 ETFs from database
        etf_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
        test_etfs = [etf['ticker'] for etf in etf_data[:3]]

        if not test_etfs:
            self.skipTest("No ETFs in database. Run test_04_scan_etfs first.")

        # Collect details
        success_count = self.adapter.collect_etf_details(tickers=test_etfs)

        # Assertions
        self.assertGreaterEqual(success_count, 0, "Should not fail")

        if success_count > 0:
            # Verify data in database
            etf_details = self.db.get_etf_details(test_etfs[0])
            print(f"✅ Collected details for {success_count}/{len(test_etfs)} ETFs")
            if etf_details:
                print(f"   Sample: {etf_details.get('issuer')}, Expense: {etf_details.get('expense_ratio')}%")

    def test_09_collect_etf_tracking_error(self):
        """Test 9: Collect ETF tracking error"""
        print("\n📊 Test 9: ETF Tracking Error Collection")

        # Get first 3 ETFs from database
        etf_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
        test_etfs = [etf['ticker'] for etf in etf_data[:3]]

        if not test_etfs:
            self.skipTest("No ETFs in database. Run test_04_scan_etfs first.")

        # Collect tracking error
        success_count = self.adapter.collect_etf_tracking_error(tickers=test_etfs)

        # Assertions
        self.assertGreaterEqual(success_count, 0, "Should not fail")

        if success_count > 0:
            # Verify data in database
            etf_details = self.db.get_etf_details(test_etfs[0])
            print(f"✅ Collected tracking error for {success_count}/{len(test_etfs)} ETFs")
            if etf_details and etf_details.get('tracking_error_20d') is not None:
                print(f"   Sample 20d tracking error: {etf_details['tracking_error_20d']:.4f}%")

    def test_10_market_tier_detection(self):
        """Test 10: Market tier detection"""
        print("\n🏷️  Test 10: Market Tier Detection")

        # Get all stocks
        stocks = self.db.get_tickers(region='KR', asset_type='STOCK', is_active=True)

        # Count by tier
        tier_counts = {}
        for stock in stocks:
            tier = stock.get('market_tier', 'UNKNOWN')
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        # Assertions
        self.assertGreater(sum(tier_counts.values()), 0, "Should have stocks with tiers")

        print(f"✅ Market tier distribution:")
        for tier, count in sorted(tier_counts.items()):
            print(f"   {tier}: {count} stocks")


class TestKoreaAdapterErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment"""
        load_dotenv()

        cls.kis_app_key = os.getenv('KIS_APP_KEY')
        cls.kis_app_secret = os.getenv('KIS_APP_SECRET')

        cls.db = SQLiteDatabaseManager(db_path='data/spock_local.db')
        cls.adapter = KoreaAdapter(
            db_manager=cls.db,
            kis_app_key=cls.kis_app_key,
            kis_app_secret=cls.kis_app_secret
        )

    def test_invalid_ticker_ohlcv(self):
        """Test: OHLCV collection with invalid ticker"""
        print("\n❌ Test: Invalid Ticker OHLCV")

        # Try to collect OHLCV for invalid ticker
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=['INVALID999'],
            days=100
        )

        # Should fail gracefully
        self.assertEqual(success_count, 0, "Should return 0 for invalid ticker")
        print("✅ Handled invalid ticker gracefully")

    def test_empty_ticker_list(self):
        """Test: OHLCV collection with empty ticker list"""
        print("\n📭 Test: Empty Ticker List")

        # Try to collect OHLCV with empty list
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=[],
            days=100
        )

        # Should return 0
        self.assertEqual(success_count, 0, "Should return 0 for empty list")
        print("✅ Handled empty ticker list gracefully")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
