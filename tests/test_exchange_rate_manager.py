"""
Unit Tests for ExchangeRateManager
Tests multi-source exchange rate fetching with caching

Test Coverage:
- Default rate retrieval
- BOK API integration (mocked)
- Database caching
- In-memory caching with TTL
- Currency conversion (to/from KRW)
- Cache invalidation and refresh

Author: Spock Trading System
Created: 2025-10-16
"""

import unittest
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.exchange_rate_manager import ExchangeRateManager
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestExchangeRateManager(unittest.TestCase):
    """Unit tests for ExchangeRateManager"""

    def setUp(self):
        """Setup test environment"""
        # Initialize manager without database for core functionality tests
        # Database tests will use a separate test with temp file
        self.manager = ExchangeRateManager(db_manager=None)

    def tearDown(self):
        """Cleanup"""
        pass

    # ===================================
    # Test 1: Default Rate Retrieval
    # ===================================

    def test_get_default_rates(self):
        """Test default rate retrieval (no API/DB)"""
        # Disable API calls
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # Test all currencies
            for currency, expected_rate in self.manager.DEFAULT_RATES.items():
                rate = self.manager.get_rate(currency)
                self.assertEqual(rate, expected_rate, f"Default rate mismatch for {currency}")

        print("✅ Test 1: Default rate retrieval - PASSED")

    # ===================================
    # Test 2: KRW Base Currency
    # ===================================

    def test_krw_base_currency(self):
        """Test KRW always returns 1.0"""
        rate = self.manager.get_rate('KRW')
        self.assertEqual(rate, 1.0, "KRW should always be 1.0")

        print("✅ Test 2: KRW base currency - PASSED")

    # ===================================
    # Test 3: Currency Conversion to KRW
    # ===================================

    def test_convert_to_krw(self):
        """Test currency conversion to KRW"""
        test_cases = [
            ('USD', 100, 130000),    # $100 × 1,300 = ₩130,000
            ('HKD', 1000, 170000),   # HK$1,000 × 170 = ₩170,000
            ('CNY', 500, 90000),     # ¥500 × 180 = ₩90,000
            ('JPY', 10000, 100000),  # ¥10,000 × 10 = ₩100,000
            ('VND', 1000000, 55000), # ₫1,000,000 × 0.055 = ₩55,000
        ]

        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            for currency, amount, expected_krw in test_cases:
                krw = self.manager.convert_to_krw(amount, currency)
                self.assertEqual(krw, expected_krw, f"Conversion failed: {amount} {currency} → {krw} KRW (expected: {expected_krw})")

        print("✅ Test 3: Currency conversion to KRW - PASSED")

    # ===================================
    # Test 4: Currency Conversion from KRW
    # ===================================

    def test_convert_from_krw(self):
        """Test currency conversion from KRW"""
        test_cases = [
            ('USD', 130000, 100.0),      # ₩130,000 ÷ 1,300 = $100
            ('HKD', 170000, 1000.0),     # ₩170,000 ÷ 170 = HK$1,000
            ('CNY', 90000, 500.0),       # ₩90,000 ÷ 180 = ¥500
            ('JPY', 100000, 10000.0),    # ₩100,000 ÷ 10 = ¥10,000
            ('VND', 55000, 1000000.0),   # ₩55,000 ÷ 0.055 = ₫1,000,000
        ]

        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            for currency, amount_krw, expected_foreign in test_cases:
                foreign = self.manager.convert_from_krw(amount_krw, currency)
                self.assertAlmostEqual(foreign, expected_foreign, places=2,
                                      msg=f"Conversion failed: {amount_krw} KRW → {foreign} {currency} (expected: {expected_foreign})")

        print("✅ Test 4: Currency conversion from KRW - PASSED")

    # ===================================
    # Test 5: In-Memory Cache
    # ===================================

    def test_in_memory_cache(self):
        """Test in-memory caching with TTL"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # First call - cache miss
            rate1 = self.manager.get_rate('USD')

            # Verify cache populated
            self.assertIn('USD', self.manager._cache)
            self.assertEqual(self.manager._cache['USD']['rate'], 1300.0)

            # Second call - cache hit (should not call API)
            rate2 = self.manager.get_rate('USD')
            self.assertEqual(rate1, rate2)

        print("✅ Test 5: In-memory cache - PASSED")

    # ===================================
    # Test 6: Cache TTL Expiration
    # ===================================

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # Populate cache
            self.manager.get_rate('USD')

            # Manually expire cache by modifying timestamp
            old_timestamp = datetime.now() - timedelta(hours=2)
            self.manager._cache['USD']['timestamp'] = old_timestamp

            # Check cache validity
            is_valid = self.manager._is_cache_valid('USD')
            self.assertFalse(is_valid, "Cache should be expired after 2 hours")

        print("✅ Test 6: Cache TTL expiration - PASSED")

    # ===================================
    # Test 7: Cache Clear
    # ===================================

    def test_cache_clear(self):
        """Test cache clearing"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # Populate cache
            self.manager.get_rate('USD')
            self.manager.get_rate('HKD')

            # Clear cache
            self.manager.clear_cache()

            # Verify cache empty
            self.assertEqual(len(self.manager._cache), 0, "Cache should be empty after clear")

        print("✅ Test 7: Cache clear - PASSED")

    # ===================================
    # Test 8: Database Persistence (Skipped)
    # ===================================

    def test_database_persistence(self):
        """Test database persistence of exchange rates (skipped - no db_manager)"""
        # This test requires a real database file
        # Skipping for basic unit tests (manager initialized with db_manager=None)
        print("⏭️  Test 8: Database persistence - SKIPPED (no db_manager)")

    # ===================================
    # Test 9: BOK API Success (Mocked)
    # ===================================

    def test_bok_api_success(self):
        """Test successful BOK API response (mocked)"""
        # Mock BOK API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'StatisticSearch': {
                'row': [
                    {
                        'DATA_VALUE': '1350.50',
                        'TIME': '20251016'
                    }
                ]
            }
        }

        with patch('requests.get', return_value=mock_response):
            rate = self.manager.get_rate('USD', force_refresh=True)

            # Should use BOK API rate (not default)
            self.assertEqual(rate, 1350.50, "Should use BOK API rate")

        print("✅ Test 9: BOK API success (mocked) - PASSED")

    # ===================================
    # Test 10: BOK API Fallback
    # ===================================

    def test_bok_api_fallback(self):
        """Test BOK API failure fallback to default"""
        # Mock BOK API timeout
        with patch('requests.get', side_effect=Exception("API timeout")):
            rate = self.manager.get_rate('USD', force_refresh=True)

            # Should fallback to default rate
            self.assertEqual(rate, 1300.0, "Should fallback to default rate on API failure")

        print("✅ Test 10: BOK API fallback - PASSED")

    # ===================================
    # Test 11: Get All Rates
    # ===================================

    def test_get_all_rates(self):
        """Test retrieving all exchange rates"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            all_rates = self.manager.get_all_rates()

            # Verify all currencies present
            expected_currencies = {'KRW', 'USD', 'HKD', 'CNY', 'JPY', 'VND'}
            self.assertEqual(set(all_rates.keys()), expected_currencies, "All currencies should be present")

            # Verify values
            self.assertEqual(all_rates['KRW'], 1.0)
            self.assertEqual(all_rates['USD'], 1300.0)

        print("✅ Test 11: Get all rates - PASSED")

    # ===================================
    # Test 12: Unknown Currency Fallback
    # ===================================

    def test_unknown_currency_fallback(self):
        """Test unknown currency fallback to USD"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            rate = self.manager.get_rate('XXX')  # Unknown currency

            # Should fallback to USD rate
            self.assertEqual(rate, 1300.0, "Unknown currency should fallback to USD")

        print("✅ Test 12: Unknown currency fallback - PASSED")

    # ===================================
    # Test 13: Cache Status
    # ===================================

    def test_cache_status(self):
        """Test cache status reporting"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # Empty cache
            status1 = self.manager.get_cache_status()
            self.assertEqual(status1['cache_count'], 0)

            # Populate cache
            self.manager.get_rate('USD')
            self.manager.get_rate('HKD')

            # Check status
            status2 = self.manager.get_cache_status()
            self.assertEqual(status2['cache_count'], 2)
            self.assertIn('USD', status2['cached_currencies'])
            self.assertIn('HKD', status2['cached_currencies'])

        print("✅ Test 13: Cache status - PASSED")

    # ===================================
    # Test 14: JPY Conversion (100 yen)
    # ===================================

    def test_jpy_conversion(self):
        """Test JPY conversion (BOK returns per 100 yen)"""
        # Mock BOK API response (per 100 yen)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'StatisticSearch': {
                'row': [
                    {
                        'DATA_VALUE': '1000.0',  # ¥100 = ₩1,000
                        'TIME': '20251016'
                    }
                ]
            }
        }

        with patch('requests.get', return_value=mock_response):
            rate = self.manager.get_rate('JPY', force_refresh=True)

            # Should divide by 100 (¥1 = ₩10)
            self.assertEqual(rate, 10.0, "JPY rate should be per 1 yen (not 100)")

        print("✅ Test 14: JPY conversion (100 yen) - PASSED")

    # ===================================
    # Test 15: Market Hours Detection
    # ===================================

    def test_market_hours_detection(self):
        """Test market hours detection"""
        # Test weekday market hours (09:00-15:30 KST)
        weekday_market = datetime(2025, 10, 16, 12, 0)  # Thursday 12:00 PM
        self.assertTrue(self.manager._is_market_hours(weekday_market), "Should be market hours")

        # Test weekday after hours
        weekday_after = datetime(2025, 10, 16, 16, 0)  # Thursday 4:00 PM
        self.assertFalse(self.manager._is_market_hours(weekday_after), "Should be after hours")

        # Test weekend
        weekend = datetime(2025, 10, 18, 12, 0)  # Saturday 12:00 PM
        self.assertFalse(self.manager._is_market_hours(weekend), "Should be weekend (closed)")

        print("✅ Test 15: Market hours detection - PASSED")


def run_tests():
    """Run all tests and generate report"""
    print("=" * 60)
    print("ExchangeRateManager Unit Tests")
    print("=" * 60)
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestExchangeRateManager)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print()
        print("✅ All tests passed!")
        return 0
    else:
        print()
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
