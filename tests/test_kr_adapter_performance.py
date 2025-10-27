"""
Performance Tests for KoreaAdapter

Tests rate limiting compliance, caching effectiveness, and API fallback mechanisms.

Author: Spock Trading System
"""

import unittest
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters import KoreaAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestKoreaAdapterPerformance(unittest.TestCase):
    """Performance and compliance tests"""

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

        print("\n" + "=" * 80)
        print("KOREA ADAPTER - PERFORMANCE TESTS")
        print("=" * 80)

    def test_rate_limiting_compliance(self):
        """Test: Rate limiting compliance (KIS API)"""
        print("\n⏱️  Test: Rate Limiting Compliance")
        print("-" * 80)

        # KIS API limit: 20 req/sec (0.05 sec interval)
        test_ticker = '005930'  # Samsung Electronics
        num_requests = 10

        print(f"Making {num_requests} consecutive API calls...")
        start_time = time.time()

        for i in range(num_requests):
            self.adapter.kis_stock_api.get_current_price(test_ticker)

        elapsed = time.time() - start_time

        # Expected minimum time: (num_requests - 1) * 0.05 = 0.45 seconds
        expected_min_time = (num_requests - 1) * 0.05

        print(f"✅ {num_requests} requests completed in {elapsed:.2f} seconds")
        print(f"   Expected minimum: {expected_min_time:.2f} seconds")
        print(f"   Average interval: {elapsed/(num_requests-1):.3f} seconds")

        # Verify rate limiting compliance
        self.assertGreaterEqual(elapsed, expected_min_time * 0.9,
                              f"Requests should be rate-limited (expected >={expected_min_time:.2f}s, got {elapsed:.2f}s)")

    def test_cache_effectiveness(self):
        """Test: Cache effectiveness for stock scanning"""
        print("\n💾 Test: Cache Effectiveness")
        print("-" * 80)

        # First scan (force refresh - should hit API)
        print("[1/3] First scan (force refresh)...")
        start_time = time.time()
        stocks_1 = self.adapter.scan_stocks(force_refresh=True)
        time_1 = time.time() - start_time

        print(f"✅ First scan: {len(stocks_1)} stocks in {time_1:.2f} seconds")

        # Second scan (use cache - should be much faster)
        print("[2/3] Second scan (use cache)...")
        start_time = time.time()
        stocks_2 = self.adapter.scan_stocks(force_refresh=False)
        time_2 = time.time() - start_time

        print(f"✅ Second scan: {len(stocks_2)} stocks in {time_2:.2f} seconds")

        # Third scan (use cache again)
        print("[3/3] Third scan (use cache)...")
        start_time = time.time()
        stocks_3 = self.adapter.scan_stocks(force_refresh=False)
        time_3 = time.time() - start_time

        print(f"✅ Third scan: {len(stocks_3)} stocks in {time_3:.2f} seconds")

        # Verify cache effectiveness
        print(f"\n📊 Cache Performance:")
        print(f"   API call time: {time_1:.2f}s")
        print(f"   Cache hit #1: {time_2:.2f}s ({time_1/time_2:.1f}x faster)")
        print(f"   Cache hit #2: {time_3:.2f}s ({time_1/time_3:.1f}x faster)")

        # Cache should be at least 5x faster
        self.assertLess(time_2, time_1 / 5,
                       f"Cache should be at least 5x faster (API: {time_1:.2f}s, Cache: {time_2:.2f}s)")

        # Results should be identical
        self.assertEqual(len(stocks_1), len(stocks_2), "Cache should return same number of stocks")
        self.assertEqual(len(stocks_2), len(stocks_3), "Cache should be consistent")

    def test_api_fallback_mechanism(self):
        """Test: API fallback mechanism (KRX → pykrx)"""
        print("\n🔄 Test: API Fallback Mechanism")
        print("-" * 80)

        # This test verifies that if KRX Data API fails, pykrx fallback works
        # We can't force KRX API to fail in a test, but we can verify the fallback logic exists

        print("[1/2] Testing KRX Data API...")
        try:
            krx_stocks = self.adapter.krx_api.get_stock_list(market='ALL')
            krx_available = True
            print(f"✅ KRX Data API: {len(krx_stocks)} stocks")
        except Exception as e:
            krx_available = False
            print(f"❌ KRX Data API failed: {e}")

        print("[2/2] Testing pykrx fallback...")
        try:
            pykrx_stocks = self.adapter.pykrx_api.get_stock_list()
            pykrx_available = True
            print(f"✅ pykrx fallback: {len(pykrx_stocks)} stocks")
        except Exception as e:
            pykrx_available = False
            print(f"❌ pykrx fallback failed: {e}")

        # At least one should be available
        self.assertTrue(krx_available or pykrx_available,
                       "Either KRX Data API or pykrx should be available")

        print(f"\n📊 Fallback Status:")
        print(f"   Primary (KRX): {'✅ Available' if krx_available else '❌ Unavailable'}")
        print(f"   Fallback (pykrx): {'✅ Available' if pykrx_available else '❌ Unavailable'}")

    def test_oauth_token_caching(self):
        """Test: OAuth token caching"""
        print("\n🔑 Test: OAuth Token Caching")
        print("-" * 80)

        # First call - should get new token
        print("[1/3] First API call (new token)...")
        start_time = time.time()
        token_1 = self.adapter.kis_stock_api._get_access_token()
        time_1 = time.time() - start_time
        print(f"✅ Token obtained in {time_1:.3f} seconds")

        # Second call - should use cached token
        print("[2/3] Second API call (cached token)...")
        start_time = time.time()
        token_2 = self.adapter.kis_stock_api._get_access_token()
        time_2 = time.time() - start_time
        print(f"✅ Token obtained in {time_2:.3f} seconds")

        # Third call - should use cached token
        print("[3/3] Third API call (cached token)...")
        start_time = time.time()
        token_3 = self.adapter.kis_stock_api._get_access_token()
        time_3 = time.time() - start_time
        print(f"✅ Token obtained in {time_3:.3f} seconds")

        # Verify token caching
        print(f"\n📊 Token Caching Performance:")
        print(f"   First call: {time_1:.3f}s")
        print(f"   Second call: {time_2:.3f}s ({time_1/time_2:.1f}x faster)")
        print(f"   Third call: {time_3:.3f}s ({time_1/time_3:.1f}x faster)")

        # Cached calls should be much faster (< 1ms vs ~100ms for API call)
        self.assertLess(time_2, time_1 / 10,
                       f"Cached token should be at least 10x faster (First: {time_1:.3f}s, Second: {time_2:.3f}s)")

        # Tokens should be identical
        self.assertEqual(token_1, token_2, "Token should be cached")
        self.assertEqual(token_2, token_3, "Token should remain cached")

    def test_parallel_ohlcv_collection(self):
        """Test: Parallel OHLCV collection performance"""
        print("\n🚀 Test: Parallel OHLCV Collection Performance")
        print("-" * 80)

        # Use 10 test tickers
        test_tickers = ['005930', '000660', '373220', '207940', '005380',
                       '000270', '068270', '035720', '051910', '006400']

        print(f"Collecting OHLCV for {len(test_tickers)} stocks...")
        start_time = time.time()

        success_count = self.adapter.collect_stock_ohlcv(
            tickers=test_tickers,
            days=100
        )

        elapsed = time.time() - start_time

        print(f"✅ Collected {success_count}/{len(test_tickers)} stocks in {elapsed:.2f} seconds")
        print(f"   Average time per stock: {elapsed/len(test_tickers):.2f} seconds")

        # Should successfully collect at least 80% of stocks
        self.assertGreaterEqual(success_count / len(test_tickers), 0.8,
                              f"Should successfully collect at least 80% of stocks (got {success_count/len(test_tickers)*100:.0f}%)")

    def test_database_write_performance(self):
        """Test: Database write performance"""
        print("\n💾 Test: Database Write Performance")
        print("-" * 80)

        # Scan stocks and measure database write time
        print("[1/2] Scanning stocks...")
        stocks = self.adapter.scan_stocks(force_refresh=True)

        print(f"[2/2] Measuring database write performance...")
        start_time = time.time()
        self.adapter._save_tickers_to_db(stocks[:100], asset_type='STOCK')
        elapsed = time.time() - start_time

        print(f"✅ Wrote 100 stocks to database in {elapsed:.2f} seconds")
        print(f"   Average time per stock: {elapsed/100*1000:.1f} ms")

        # Should write at least 10 stocks per second
        self.assertLess(elapsed, 10.0,
                       f"Should write 100 stocks in < 10 seconds (got {elapsed:.2f}s)")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
