#!/usr/bin/env python3
"""
Technical Filter (Stage 1) Blacklist Integration Tests

Tests the blacklist functionality integrated into StockPreFilter.
Validates that:
1. Blacklisted tickers are filtered out before technical analysis (DB blacklist)
2. Blacklisted tickers are filtered out before technical analysis (file blacklist)
3. Non-blacklisted tickers pass through to technical analysis
4. Blacklist filtering occurs BEFORE OHLCV data loading (resource efficiency)
5. Bulk filtering method is used for performance
6. Statistics are properly logged (blacklist rejected count)

Author: Spock Trading System
Created: 2025-10-17
"""

import os
import sys
import unittest
import sqlite3
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.stock_pre_filter import StockPreFilter
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from init_db import DatabaseInitializer


class TestTechnicalFilterBlacklist(unittest.TestCase):
    """Test suite for Technical Filter blacklist integration"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests"""
        cls.test_db_path = "data/test_technical_filter_blacklist.db"
        cls.test_blacklist_path = "config/test_technical_filter_blacklist.json"

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
        import time
        import gc

        # Ensure all connections are closed first
        gc.collect()
        time.sleep(0.1)

        # Insert test tickers FIRST
        self._insert_test_ticker('005930', 'KR', 'Samsung Electronics', 'KOSPI')
        self._insert_test_ticker('000660', 'KR', 'SK Hynix', 'KOSPI')
        self._insert_test_ticker('035720', 'KR', 'Kakao', 'KOSDAQ')

        # Insert test Stage 0 cache data
        self._insert_stage0_cache(['005930', '000660', '035720'])

        # Initialize Technical Filter
        self.filter = StockPreFilter(db_path=self.test_db_path, region='KR')

        # Override blacklist manager config_path to use test file
        self.filter.blacklist_manager.config_path = self.test_blacklist_path
        self.filter.blacklist_manager._load_file_blacklist()

        # Keep references for test assertions
        self.db_manager = SQLiteDatabaseManager(db_path=self.test_db_path)
        self.blacklist_manager = self.filter.blacklist_manager

    def tearDown(self):
        """Clean up after each test"""
        import time
        import gc

        # Force close all connections
        try:
            del self.filter
            del self.blacklist_manager
            del self.db_manager
        except:
            pass

        # Force garbage collection
        gc.collect()
        time.sleep(0.1)

        # Clear blacklist tables and Stage 0 cache
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE tickers SET is_active = 1")
        cursor.execute("DELETE FROM filter_cache_stage0")
        cursor.execute("DELETE FROM filter_cache_stage1")
        cursor.execute("DELETE FROM ohlcv_data")
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

    def _insert_test_ticker(self, ticker: str, region: str, name: str, exchange: str):
        """Helper: Insert test ticker into database"""
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()

        currency_map = {'KR': 'KRW', 'US': 'USD', 'CN': 'CNY', 'HK': 'HKD', 'JP': 'JPY', 'VN': 'VND'}
        currency = currency_map.get(region, 'KRW')
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

    def _insert_stage0_cache(self, tickers: list):
        """Helper: Insert test Stage 0 cache data"""
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()
        today = datetime.now().date().isoformat()

        # Ticker name mapping
        ticker_names = {
            '005930': 'Samsung Electronics',
            '000660': 'SK Hynix',
            '035720': 'Kakao'
        }

        for ticker in tickers:
            cursor.execute("""
                INSERT OR REPLACE INTO filter_cache_stage0 (
                    ticker, name, region, exchange, currency,
                    market_cap_krw, market_cap_local,
                    trading_value_krw, trading_value_local,
                    current_price_krw, current_price_local,
                    exchange_rate_to_krw,
                    stage0_passed, filter_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, ticker_names.get(ticker, 'Test Stock'), 'KR', 'KOSPI', 'KRW',
                1000000000000, 1000000000000,  # 1T KRW market cap
                10000000000, 10000000000,  # 10B KRW trading value
                50000, 50000,  # 50K KRW price
                1.0,  # Exchange rate
                True, today
            ))
        conn.commit()
        conn.close()

    # ====================================================================
    # Test 1: DB Blacklist Filtering
    # ====================================================================

    def test_01_db_blacklist_filtering_before_technical_analysis(self):
        """Test that DB-blacklisted tickers are filtered out BEFORE technical analysis"""
        # Given: Blacklist one ticker in DB
        success = self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: DB blacklist'
        )
        self.assertTrue(success, "Deactivation should succeed")

        # Mock _load_ohlcv_data to track which tickers are loaded
        called_tickers = []

        def mock_load_ohlcv(ticker):
            called_tickers.append(ticker)
            return []  # Return empty to simulate no OHLCV data (will fail technical filter)

        # When: Run Stage 1 filter with mocked OHLCV loading
        with patch.object(self.filter, '_load_ohlcv_data', side_effect=mock_load_ohlcv):
            results = self.filter.run_stage1_filter(force_refresh=True)

        # Then: Blacklisted ticker should be filtered out BEFORE OHLCV loading
        self.assertNotIn('005930', called_tickers, "Blacklisted ticker should not trigger OHLCV loading")
        self.assertIn('000660', called_tickers, "Non-blacklisted ticker should trigger OHLCV loading")
        self.assertIn('035720', called_tickers, "Non-blacklisted ticker should trigger OHLCV loading")

    # ====================================================================
    # Test 2: File Blacklist Filtering
    # ====================================================================

    def test_02_file_blacklist_filtering_before_technical_analysis(self):
        """Test that file-blacklisted tickers are filtered out BEFORE technical analysis"""
        # Given: Blacklist one ticker in file
        success = self.blacklist_manager.add_to_file_blacklist(
            ticker='035720',
            region='KR',
            reason='Test: File blacklist',
            added_by='unit_test'
        )
        self.assertTrue(success, "File blacklist add should succeed")

        # Mock _load_ohlcv_data to track which tickers are loaded
        called_tickers = []

        def mock_load_ohlcv(ticker):
            called_tickers.append(ticker)
            return []  # Return empty to simulate no OHLCV data

        # When: Run Stage 1 filter with mocked OHLCV loading
        with patch.object(self.filter, '_load_ohlcv_data', side_effect=mock_load_ohlcv):
            results = self.filter.run_stage1_filter(force_refresh=True)

        # Then: File-blacklisted ticker should be filtered out BEFORE OHLCV loading
        self.assertNotIn('035720', called_tickers, "File-blacklisted ticker should not trigger OHLCV loading")
        self.assertIn('005930', called_tickers, "Non-blacklisted ticker should trigger OHLCV loading")
        self.assertIn('000660', called_tickers, "Non-blacklisted ticker should trigger OHLCV loading")

    # ====================================================================
    # Test 3: Non-Blacklisted Tickers Pass Through
    # ====================================================================

    def test_03_non_blacklisted_pass_through(self):
        """Test that non-blacklisted tickers pass through to technical analysis"""
        # Given: No blacklisted tickers
        is_blacklisted_005930 = self.blacklist_manager.is_blacklisted('005930', 'KR')
        is_blacklisted_000660 = self.blacklist_manager.is_blacklisted('000660', 'KR')

        self.assertFalse(is_blacklisted_005930, "005930 should not be blacklisted")
        self.assertFalse(is_blacklisted_000660, "000660 should not be blacklisted")

        # Mock _load_ohlcv_data to track which tickers are processed
        called_tickers = []

        def mock_load_ohlcv(ticker):
            called_tickers.append(ticker)
            return []  # Return empty (will fail technical filter, but we're testing blacklist pass-through)

        # When: Run Stage 1 filter with mocked OHLCV loading
        with patch.object(self.filter, '_load_ohlcv_data', side_effect=mock_load_ohlcv):
            results = self.filter.run_stage1_filter(force_refresh=True)

        # Then: All non-blacklisted tickers should reach OHLCV loading
        self.assertIn('005930', called_tickers, "005930 should pass blacklist filter")
        self.assertIn('000660', called_tickers, "000660 should pass blacklist filter")
        self.assertIn('035720', called_tickers, "035720 should pass blacklist filter")

    # ====================================================================
    # Test 4: Blacklist Filter Priority (Before OHLCV Loading)
    # ====================================================================

    def test_04_blacklist_filter_before_ohlcv_loading(self):
        """Test that blacklist filtering occurs BEFORE OHLCV data loading (resource efficiency)"""
        # Given: Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Priority check'
        )

        # Mock _load_ohlcv_data and count how many times it's called
        call_count = {'count': 0}

        def counting_load_ohlcv(ticker):
            call_count['count'] += 1
            return []  # Return empty

        # When: Run Stage 1 filter with mocked OHLCV loading
        with patch.object(self.filter, '_load_ohlcv_data', side_effect=counting_load_ohlcv):
            results = self.filter.run_stage1_filter(force_refresh=True)

        # Then: _load_ohlcv_data should only be called for non-blacklisted tickers
        # (2 calls for 000660 and 035720, 0 calls for blacklisted 005930)
        self.assertEqual(call_count['count'], 2,
                       "_load_ohlcv_data should only be called for non-blacklisted tickers")

    # ====================================================================
    # Test 5: Bulk Filtering Performance
    # ====================================================================

    def test_05_bulk_filtering_used(self):
        """Test that bulk filtering method is used for performance"""
        # Given: Mock blacklist manager method
        with patch.object(self.blacklist_manager, 'filter_blacklisted_tickers',
                         wraps=self.blacklist_manager.filter_blacklisted_tickers) as mock_filter:
            # Mock _load_ohlcv_data to avoid actual data loading
            def mock_load_ohlcv(ticker):
                return []

            # When: Run Stage 1 filter with mocked OHLCV loading
            with patch.object(self.filter, '_load_ohlcv_data', side_effect=mock_load_ohlcv):
                results = self.filter.run_stage1_filter(force_refresh=True)

            # Then: filter_blacklisted_tickers should be called once (bulk operation)
            self.assertEqual(mock_filter.call_count, 1,
                           "Bulk filtering method should be called once")

            # Check it was called with the full list of tickers
            call_args = mock_filter.call_args
            self.assertEqual(len(call_args[0][0]), 3,
                           "All ticker codes should be passed to bulk filter")

    # ====================================================================
    # Test 6: Statistics Logging
    # ====================================================================

    def test_06_statistics_logging(self):
        """Test that blacklist rejection statistics are properly logged"""
        import logging
        from io import StringIO

        # Given: Capture log output from the modules.stock_pre_filter logger
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        # Get the stock_pre_filter logger (same as stock_pre_filter.py uses)
        filter_logger = logging.getLogger('modules.stock_pre_filter')
        filter_logger.addHandler(handler)
        filter_logger.setLevel(logging.INFO)

        # Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Statistics'
        )

        # Mock _load_ohlcv_data to avoid actual data loading
        def mock_load_ohlcv(ticker):
            return []

        # When: Run Stage 1 filter with mocked OHLCV loading
        with patch.object(self.filter, '_load_ohlcv_data', side_effect=mock_load_ohlcv):
            results = self.filter.run_stage1_filter(force_refresh=True)

        # Then: Log should contain blacklist statistics
        log_output = log_stream.getvalue()
        self.assertIn('Blacklist', log_output, "Log should mention blacklist filtering")
        self.assertIn('rejected', log_output, "Log should contain blacklist rejection count")

        # Cleanup
        filter_logger.removeHandler(handler)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
