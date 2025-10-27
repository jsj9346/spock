#!/usr/bin/env python3
"""
Trading Engine Blacklist Integration Tests

Tests the blacklist functionality integrated into KISTradingEngine.
Validates that:
1. Blacklisted tickers are rejected before order execution (DB blacklist)
2. Blacklisted tickers are rejected before order execution (file blacklist)
3. Non-blacklisted tickers pass through normally
4. Blacklist check occurs before position limit checks
5. Error messages are properly formatted
6. Logging output is correct

Author: Spock Trading System
Created: 2025-10-17
"""

import os
import sys
import unittest
import sqlite3
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.kis_trading_engine import KISTradingEngine, TradingConfig
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from init_db import DatabaseInitializer


class TestTradingEngineBlacklist(unittest.TestCase):
    """Test suite for Trading Engine blacklist integration"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests"""
        cls.test_db_path = "data/test_trading_engine_blacklist.db"
        cls.test_blacklist_path = "config/test_stock_blacklist.json"

        # Remove existing test files
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
        if os.path.exists(cls.test_blacklist_path):
            os.remove(cls.test_blacklist_path)

        # Initialize test database
        print(f"\n📊 Initializing test database: {cls.test_db_path}")
        initializer = DatabaseInitializer(db_path=cls.test_db_path)
        initializer.initialize(reset=False, include_phase2=False)

        # Enable WAL mode for better concurrency
        conn = sqlite3.connect(cls.test_db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()

        print(f"✅ Test database created: {cls.test_db_path}")

        # Create test blacklist file
        blacklist_data = {
            "version": "2.0",
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "blacklist": {
                "KR": {},
                "US": {},
                "CN": {},
                "HK": {},
                "JP": {},
                "VN": {}
            }
        }
        os.makedirs(os.path.dirname(cls.test_blacklist_path), exist_ok=True)
        with open(cls.test_blacklist_path, 'w', encoding='utf-8') as f:
            json.dump(blacklist_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Test blacklist file created: {cls.test_blacklist_path}")

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment after all tests"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
            print(f"\n🧹 Cleaned up test database: {cls.test_db_path}")
        if os.path.exists(cls.test_blacklist_path):
            os.remove(cls.test_blacklist_path)
            print(f"🧹 Cleaned up test blacklist file: {cls.test_blacklist_path}")

    def setUp(self):
        """Set up test fixtures before each test"""
        # Insert test tickers FIRST (before initializing managers)
        self._insert_test_ticker('005930', 'KR', 'Samsung Electronics')
        self._insert_test_ticker('AAPL', 'US', 'Apple Inc')

        # Initialize Trading Engine with dry_run=True (mock mode)
        # This will create its own db_manager and blacklist_manager internally
        self.trading_engine = KISTradingEngine(
            db_path=self.test_db_path,
            config=TradingConfig(),
            dry_run=True
        )

        # Override blacklist manager config_path to use test file
        self.trading_engine.blacklist_manager.config_path = self.test_blacklist_path
        self.trading_engine.blacklist_manager._load_file_blacklist()

        # Keep references for test assertions
        self.db_manager = SQLiteDatabaseManager(db_path=self.test_db_path)
        self.blacklist_manager = self.trading_engine.blacklist_manager

    def tearDown(self):
        """Clean up after each test"""
        import time
        import gc

        # Force close all connections in trading engine components
        try:
            # These components hold database connections
            del self.trading_engine
            del self.blacklist_manager
            del self.db_manager
        except:
            pass

        # Force garbage collection to release connections
        gc.collect()

        # Small delay to ensure connections are released
        time.sleep(0.1)

        # Clear blacklist tables with timeout connection
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE tickers SET is_active = 1")
        cursor.execute("DELETE FROM trades")
        conn.commit()
        conn.close()

        # Reset file blacklist
        blacklist_data = {
            "version": "2.0",
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "blacklist": {
                "KR": {},
                "US": {},
                "CN": {},
                "HK": {},
                "JP": {},
                "VN": {}
            }
        }
        with open(self.test_blacklist_path, 'w', encoding='utf-8') as f:
            json.dump(blacklist_data, f, indent=2, ensure_ascii=False)

    def _insert_test_ticker(self, ticker: str, region: str, name: str):
        """Helper: Insert test ticker into database"""
        # Use direct connection with timeout to avoid locking
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()

        # Get exchange and currency based on region
        config_map = {
            'KR': ('KOSPI', 'KRW'),
            'US': ('NASDAQ', 'USD'),
            'CN': ('SSE', 'CNY'),
            'HK': ('HKEX', 'HKD'),
            'JP': ('TSE', 'JPY'),
            'VN': ('HOSE', 'VND')
        }
        exchange, currency = config_map.get(region, ('UNKNOWN', 'USD'))
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO tickers (
                ticker, region, name, exchange, currency,
                is_active, created_at, last_updated
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (ticker, region, name, exchange, currency, now, now))
        conn.commit()
        conn.close()

    # ====================================================================
    # Test 1: DB Blacklist Rejection
    # ====================================================================

    def test_01_db_blacklist_rejection(self):
        """Test that DB-blacklisted tickers are rejected"""
        # Given: Ticker is blacklisted in DB (is_active=False)
        success = self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Delisting'
        )
        self.assertTrue(success, "Deactivation should succeed")

        # When: Attempt to buy blacklisted ticker
        result = self.trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=100000,
            sector='Information Technology',
            region='KR'
        )

        # Then: Order should be rejected
        self.assertFalse(result.success, "Order should be rejected")
        self.assertIn('blacklisted', result.message.lower(), "Message should mention blacklist")
        self.assertEqual(result.quantity, 0, "Quantity should be 0")
        self.assertEqual(result.price, 0, "Price should be 0")

    # ====================================================================
    # Test 2: File Blacklist Rejection
    # ====================================================================

    def test_02_file_blacklist_rejection(self):
        """Test that file-blacklisted tickers are rejected"""
        # Given: Ticker is blacklisted in file
        success = self.blacklist_manager.add_to_file_blacklist(
            ticker='AAPL',
            region='US',
            reason='Test: Temporary exclusion',
            added_by='unit_test'
        )
        self.assertTrue(success, "File blacklist add should succeed")

        # When: Attempt to buy blacklisted ticker
        result = self.trading_engine.execute_buy_order(
            ticker='AAPL',
            amount_krw=100000,
            sector='Information Technology',
            region='US'
        )

        # Then: Order should be rejected
        self.assertFalse(result.success, "Order should be rejected")
        self.assertIn('blacklisted', result.message.lower(), "Message should mention blacklist")
        self.assertEqual(result.quantity, 0, "Quantity should be 0")
        self.assertEqual(result.price, 0, "Price should be 0")

    # ====================================================================
    # Test 3: Non-Blacklisted Ticker Passes
    # ====================================================================

    def test_03_non_blacklisted_ticker_passes(self):
        """Test that non-blacklisted tickers pass through normally"""
        # Given: Ticker is NOT blacklisted
        is_blacklisted = self.blacklist_manager.is_blacklisted('005930', 'KR')
        self.assertFalse(is_blacklisted, "Ticker should not be blacklisted")

        # When: Attempt to buy non-blacklisted ticker
        result = self.trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=100000,
            sector='Information Technology',
            region='KR'
        )

        # Then: Order should succeed (or fail for other reasons, but NOT blacklist)
        if not result.success:
            self.assertNotIn('blacklist', result.message.lower(),
                           "Failure should not be due to blacklist")
        else:
            self.assertTrue(result.success, "Order should succeed")
            self.assertGreater(result.quantity, 0, "Quantity should be > 0")

    # ====================================================================
    # Test 4: Blacklist Check Before Position Limits
    # ====================================================================

    def test_04_blacklist_check_before_position_limits(self):
        """Test that blacklist check occurs before position limit checks"""
        # Given: Ticker is blacklisted
        success = self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Priority check'
        )
        self.assertTrue(success, "Deactivation should succeed")

        # When: Attempt to buy with large amount (would trigger position limits)
        result = self.trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=50000000,  # 50M KRW (likely exceeds position limits)
            sector='Information Technology',
            region='KR'
        )

        # Then: Should be rejected due to blacklist, not position limits
        self.assertFalse(result.success, "Order should be rejected")
        self.assertIn('blacklist', result.message.lower(),
                    "Rejection should be due to blacklist, not position limits")
        self.assertNotIn('position limit', result.message.lower(),
                       "Message should not mention position limits")

    # ====================================================================
    # Test 5: Error Message Format
    # ====================================================================

    def test_05_error_message_format(self):
        """Test that blacklist rejection messages are properly formatted"""
        # Given: Ticker is blacklisted
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Message format'
        )

        # When: Attempt to buy blacklisted ticker
        result = self.trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=100000,
            sector='Information Technology',
            region='KR'
        )

        # Then: Message should be properly formatted
        self.assertIsNotNone(result.message, "Message should not be None")
        self.assertIn('Order rejected', result.message, "Message should start with 'Order rejected'")
        self.assertIn('005930', result.message, "Message should contain ticker")
        self.assertIn('blacklist', result.message.lower(), "Message should mention blacklist")
        self.assertIn('KR', result.message, "Message should contain region")

    # ====================================================================
    # Test 6: Logging Output
    # ====================================================================

    def test_06_logging_output(self):
        """Test that blacklist rejection is properly logged"""
        import logging
        from io import StringIO

        # Given: Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger('kis_trading_engine')
        logger.addHandler(handler)

        # Given: Ticker is blacklisted
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Logging'
        )

        # When: Attempt to buy blacklisted ticker
        result = self.trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=100000,
            sector='Information Technology',
            region='KR'
        )

        # Then: Log should contain rejection warning
        log_output = log_stream.getvalue()
        self.assertIn('ORDER REJECTED', log_output, "Log should contain 'ORDER REJECTED'")
        self.assertIn('005930', log_output, "Log should contain ticker")
        self.assertIn('blacklist', log_output.lower(), "Log should mention blacklist")

        # Cleanup
        logger.removeHandler(handler)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
