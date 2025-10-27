"""
Integration Tests for ExchangeRateManager with Database
Tests database persistence, MarketFilterManager integration, and concurrent access

Test Coverage:
- Database persistence and retrieval
- Integration with MarketFilterManager
- Concurrent rate updates
- Cache invalidation with database fallback
- Multi-market currency conversion
- Historical rate tracking

Author: Spock Trading System
Created: 2025-10-16
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.exchange_rate_manager import ExchangeRateManager
from modules.market_filter_manager import MarketFilterManager
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestExchangeRateManagerIntegration(unittest.TestCase):
    """Integration tests for ExchangeRateManager with database and MarketFilterManager"""

    @classmethod
    def setUpClass(cls):
        """Setup test database directory"""
        cls.test_dir = tempfile.mkdtemp(prefix='spock_test_')
        cls.test_db_path = os.path.join(cls.test_dir, 'test_spock.db')

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database directory"""
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        """Setup test environment with real database"""
        # Create database file first
        import sqlite3
        conn = sqlite3.connect(self.test_db_path)
        conn.close()

        # Initialize database manager
        self.db_manager = SQLiteDatabaseManager(db_path=self.test_db_path)

        # Run migration to create exchange_rate_history table
        import importlib.util
        migration_path = project_root / 'migrations' / '006_add_exchange_rate_history.py'
        spec = importlib.util.spec_from_file_location("migration_006", migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        migration_module.upgrade(self.test_db_path)

        # Initialize manager with database
        self.manager = ExchangeRateManager(db_manager=self.db_manager)

    def tearDown(self):
        """Cleanup after each test"""
        # Clear cache
        self.manager.clear_cache()

        # Clear database table
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM exchange_rate_history")
        conn.commit()
        conn.close()

    # ===================================
    # Test 1: Database Persistence
    # ===================================

    def test_database_persistence(self):
        """Test exchange rate persistence to database"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=1350.50):
            # Get rate (should save to database)
            rate = self.manager.get_rate('USD', force_refresh=True)
            self.assertEqual(rate, 1350.50)

            # Verify database entry
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT currency, rate, source FROM exchange_rate_history
                WHERE currency = 'USD'
                ORDER BY timestamp DESC LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()

            self.assertIsNotNone(result, "Rate should be saved to database")
            self.assertEqual(result[0], 'USD')
            self.assertEqual(result[1], 1350.50)
            self.assertEqual(result[2], 'BOK_API')

        print("✅ Test 1: Database persistence - PASSED")

    # ===================================
    # Test 2: Database Retrieval Fallback
    # ===================================

    def test_database_retrieval_fallback(self):
        """Test fallback to database when API fails"""
        # First, populate database with a rate
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=1350.50):
            self.manager.get_rate('USD', force_refresh=True)

        # Clear cache
        self.manager.clear_cache()

        # Now simulate API failure and verify fallback to database
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            rate = self.manager.get_rate('USD')
            self.assertEqual(rate, 1350.50, "Should fallback to database rate")

        print("✅ Test 2: Database retrieval fallback - PASSED")

    # ===================================
    # Test 3: MarketFilterManager Integration
    # ===================================

    def test_market_filter_manager_integration(self):
        """Test integration with MarketFilterManager for currency conversion"""
        # Initialize MarketFilterManager
        config_dir = project_root / 'config' / 'market_filters'
        filter_manager = MarketFilterManager(config_dir=str(config_dir))

        # Get US config
        us_config = filter_manager.get_config('US')

        # Test conversion from USD to KRW
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            # Use default USD rate (1300.0)
            min_cap_local = us_config.config['stage0_filters']['min_market_cap_local']  # $76.9M
            min_cap_krw = self.manager.convert_to_krw(min_cap_local, us_config.currency)

            expected_krw = int(76_900_000 * 1300.0)  # $76.9M × 1,300 KRW/USD = ₩100B
            self.assertEqual(min_cap_krw, expected_krw)

        print("✅ Test 3: MarketFilterManager integration - PASSED")

    # ===================================
    # Test 4: Multi-Market Conversion Consistency
    # ===================================

    def test_multi_market_conversion_consistency(self):
        """Test consistent conversion across all markets"""
        config_dir = project_root / 'config' / 'market_filters'
        filter_manager = MarketFilterManager(config_dir=str(config_dir))

        # Test all markets have correct target KRW values
        target_market_cap_krw = 100_000_000_000  # ₩100B

        markets = ['US', 'HK', 'CN', 'JP', 'VN']

        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            for region in markets:
                config = filter_manager.get_config(region)

                # Get local threshold from config
                min_cap_local = config.config['stage0_filters']['min_market_cap_local']

                # Convert local threshold to KRW
                min_cap_krw = self.manager.convert_to_krw(
                    min_cap_local,
                    config.currency
                )

                # Allow 1% tolerance due to rounding
                tolerance = target_market_cap_krw * 0.01
                self.assertAlmostEqual(
                    min_cap_krw,
                    target_market_cap_krw,
                    delta=tolerance,
                    msg=f"{region} market cap conversion mismatch"
                )

        print("✅ Test 4: Multi-market conversion consistency - PASSED")

    # ===================================
    # Test 5: Historical Rate Tracking
    # ===================================

    def test_historical_rate_tracking(self):
        """Test tracking of historical exchange rates"""
        import sqlite3

        with patch.object(self.manager, '_fetch_from_bok_api') as mock_api:
            # Simulate first rate (today)
            mock_api.return_value = 1300.0
            self.manager.get_rate('USD', force_refresh=True)

            # Manually insert a historical rate (yesterday) to test multi-day tracking
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO exchange_rate_history (currency, rate, timestamp, rate_date, source)
                VALUES ('USD', 1280.0, ?, ?, 'BOK_API')
            """, (datetime.now().isoformat(), yesterday))
            conn.commit()
            conn.close()

            # Verify multiple entries in database
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM exchange_rate_history
                WHERE currency = 'USD'
            """)
            count = cursor.fetchone()[0]
            conn.close()

            self.assertGreaterEqual(count, 2, "Should have multiple historical entries")

        print("✅ Test 5: Historical rate tracking - PASSED")

    # ===================================
    # Test 6: Cache Invalidation with Database
    # ===================================

    def test_cache_invalidation_with_database(self):
        """Test cache invalidation falls back to database"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=1350.50):
            # Populate cache and database
            rate1 = self.manager.get_rate('USD', force_refresh=True)
            self.assertEqual(rate1, 1350.50)

        # Manually expire cache
        old_timestamp = datetime.now() - timedelta(hours=2)
        self.manager._cache['USD']['timestamp'] = old_timestamp

        # Get rate again (should use database, not API)
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            rate2 = self.manager.get_rate('USD')
            self.assertEqual(rate2, 1350.50, "Should retrieve from database")

        print("✅ Test 6: Cache invalidation with database - PASSED")

    # ===================================
    # Test 7: Concurrent Rate Updates
    # ===================================

    def test_concurrent_rate_updates(self):
        """Test handling of concurrent rate updates (same rate_date)"""
        with patch.object(self.manager, '_fetch_from_bok_api', return_value=1350.50):
            # First update
            self.manager.get_rate('USD', force_refresh=True)

            # Second update (same day, different time)
            self.manager.clear_cache()

            with patch.object(self.manager, '_fetch_from_bok_api', return_value=1355.00):
                self.manager.get_rate('USD', force_refresh=True)

            # Verify only one entry per day (UNIQUE constraint on currency + rate_date)
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*), MAX(rate) FROM exchange_rate_history
                WHERE currency = 'USD' AND rate_date = date('now')
            """)
            count, latest_rate = cursor.fetchone()
            conn.close()

            self.assertEqual(count, 1, "Should have only one entry per day")
            self.assertEqual(latest_rate, 1355.00, "Should use latest rate")

        print("✅ Test 7: Concurrent rate updates - PASSED")

    # ===================================
    # Test 8: All Markets Integration
    # ===================================

    def test_all_markets_integration(self):
        """Test exchange rate conversion for all supported markets"""
        config_dir = project_root / 'config' / 'market_filters'
        filter_manager = MarketFilterManager(config_dir=str(config_dir))

        # Test portfolio value conversion across all markets
        portfolio_krw = 10_000_000  # ₩10M

        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            for region in ['US', 'HK', 'CN', 'JP', 'VN']:
                config = filter_manager.get_config(region)

                # Convert to local currency
                portfolio_local = self.manager.convert_from_krw(
                    portfolio_krw,
                    config.currency
                )

                # Convert back to KRW
                portfolio_krw_back = self.manager.convert_to_krw(
                    portfolio_local,
                    config.currency
                )

                # Allow small rounding error
                self.assertAlmostEqual(
                    portfolio_krw_back,
                    portfolio_krw,
                    delta=100,  # ±100 KRW tolerance
                    msg=f"{region} round-trip conversion failed"
                )

        print("✅ Test 8: All markets integration - PASSED")

    # ===================================
    # Test 9: Database Migration Verification
    # ===================================

    def test_database_migration_verification(self):
        """Test exchange_rate_history table schema"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Verify table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='exchange_rate_history'
        """)
        table_exists = cursor.fetchone()
        self.assertIsNotNone(table_exists, "exchange_rate_history table should exist")

        # Verify columns
        cursor.execute("PRAGMA table_info(exchange_rate_history)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'id': 'INTEGER',
            'currency': 'TEXT',
            'rate': 'REAL',
            'timestamp': 'TEXT',
            'rate_date': 'TEXT',
            'source': 'TEXT',
            'created_at': 'TEXT'
        }

        for col_name, col_type in expected_columns.items():
            self.assertIn(col_name, columns, f"Column {col_name} should exist")
            self.assertEqual(columns[col_name], col_type, f"Column {col_name} type mismatch")

        # Verify unique constraint
        cursor.execute("""
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='exchange_rate_history'
        """)
        schema = cursor.fetchone()[0]
        self.assertIn('UNIQUE(currency, rate_date)', schema, "UNIQUE constraint should exist")

        conn.close()
        print("✅ Test 9: Database migration verification - PASSED")

    # ===================================
    # Test 10: Stage 0 Filter Integration
    # ===================================

    def test_stage0_filter_integration(self):
        """Test Stage 0 filter with real exchange rate conversion"""
        config_dir = project_root / 'config' / 'market_filters'
        filter_manager = MarketFilterManager(config_dir=str(config_dir))

        # Test US stock filtering
        # Trading value = 60M shares × $180 = $10.8B/day (passes ₩100B threshold)
        us_stock_data = {
            'ticker': 'AAPL',
            'market_cap_local': 3_000_000_000_000,  # $3T (passes)
            'trading_value_local': 10_800_000_000,  # $10.8B/day (60M shares × $180)
            'price_local': 180.0,  # $180 (passes)
            'asset_type': 'STOCK'
        }

        with patch.object(self.manager, '_fetch_from_bok_api', return_value=None):
            result = filter_manager.apply_stage0_filter('US', us_stock_data)

            if not result.passed:
                print(f"Filter failed reason: {result.reason}")

            self.assertTrue(result.passed, f"AAPL should pass Stage 0 filter (reason: {result.reason})")
            self.assertIn('market_cap_krw', result.normalized_data)
            self.assertIn('trading_value_krw', result.normalized_data)
            self.assertIn('current_price_krw', result.normalized_data)

            # Verify KRW normalization
            expected_market_cap_krw = int(3_000_000_000_000 * 1300.0)
            expected_trading_value_krw = int(10_800_000_000 * 1300.0)
            expected_price_krw = int(180.0 * 1300.0)

            self.assertEqual(result.normalized_data['market_cap_krw'], expected_market_cap_krw)
            self.assertEqual(result.normalized_data['trading_value_krw'], expected_trading_value_krw)
            self.assertEqual(result.normalized_data['current_price_krw'], expected_price_krw)

        print("✅ Test 10: Stage 0 filter integration - PASSED")


def run_tests():
    """Run all integration tests and generate report"""
    print("=" * 60)
    print("ExchangeRateManager Integration Tests")
    print("=" * 60)
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestExchangeRateManagerIntegration)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print()
    print("=" * 60)
    print("Integration Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print()
        print("✅ All integration tests passed!")
        print("🎉 Task 1.5 COMPLETE: Integration tests validated")
        return 0
    else:
        print()
        print("❌ Some integration tests failed")
        return 1


if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
