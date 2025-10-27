#!/usr/bin/env python3
"""
Stock Scanner Blacklist Integration Tests

Tests the blacklist functionality integrated into StockScanner.
Validates that:
1. Blacklisted tickers are filtered out during Stage 0 scanning (DB blacklist)
2. Blacklisted tickers are filtered out during Stage 0 scanning (file blacklist)
3. Non-blacklisted tickers pass through Stage 0 filtering
4. Blacklist filtering occurs BEFORE market filter checks (resource efficiency)
5. Statistics are properly logged (blacklist rejected count)
6. Bulk filtering method is used for performance

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

from modules.scanner import StockScanner
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from init_db import DatabaseInitializer


class TestScannerBlacklist(unittest.TestCase):
    """Test suite for Stock Scanner blacklist integration"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests"""
        cls.test_db_path = "data/test_scanner_blacklist.db"
        cls.test_blacklist_path = "config/test_scanner_blacklist.json"

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
        # Insert test tickers FIRST
        self._insert_test_ticker('005930', 'KR', 'Samsung Electronics', 'KOSPI')
        self._insert_test_ticker('000660', 'KR', 'SK Hynix', 'KOSPI')
        self._insert_test_ticker('035720', 'KR', 'Kakao', 'KOSDAQ')

        # Initialize Stock Scanner with test database
        self.scanner = StockScanner(db_path=self.test_db_path, region='KR')

        # Override blacklist manager config_path to use test file
        self.scanner.blacklist_manager.config_path = self.test_blacklist_path
        self.scanner.blacklist_manager._load_file_blacklist()

        # Keep references for test assertions
        self.db_manager = SQLiteDatabaseManager(db_path=self.test_db_path)
        self.blacklist_manager = self.scanner.blacklist_manager

    def tearDown(self):
        """Clean up after each test"""
        import time
        import gc

        # Force close all connections
        try:
            del self.scanner
            del self.blacklist_manager
            del self.db_manager
        except:
            pass

        # Force garbage collection
        gc.collect()
        time.sleep(0.1)

        # Clear blacklist tables
        conn = sqlite3.connect(self.test_db_path, timeout=10.0)
        cursor = conn.cursor()
        cursor.execute("UPDATE tickers SET is_active = 1")
        cursor.execute("DELETE FROM filter_cache_stage0")
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

    # ====================================================================
    # Test 1: DB Blacklist Filtering
    # ====================================================================

    def test_01_db_blacklist_filtering(self):
        """Test that DB-blacklisted tickers are filtered out during Stage 0"""
        # Given: Blacklist one ticker in DB
        success = self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: DB blacklist'
        )
        self.assertTrue(success, "Deactivation should succeed")

        # Create mock ticker data
        mock_tickers = [
            {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
            {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'},
            {'ticker': '035720', 'name': 'Kakao', 'market': 'KOSDAQ'}
        ]

        # Mock FilterResult to always pass for market filter (isolate blacklist testing)
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        # When: Apply filters with mocked market filter
        with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', return_value=mock_result):
            filtered = self.scanner._apply_spock_filters(mock_tickers)

        # Then: Blacklisted ticker should be removed
        filtered_tickers = [t['ticker'] for t in filtered]
        self.assertNotIn('005930', filtered_tickers, "DB-blacklisted ticker should be filtered out")
        self.assertIn('000660', filtered_tickers, "Non-blacklisted ticker should pass through")

    # ====================================================================
    # Test 2: File Blacklist Filtering
    # ====================================================================

    def test_02_file_blacklist_filtering(self):
        """Test that file-blacklisted tickers are filtered out during Stage 0"""
        # Given: Blacklist one ticker in file
        success = self.blacklist_manager.add_to_file_blacklist(
            ticker='035720',
            region='KR',
            reason='Test: File blacklist',
            added_by='unit_test'
        )
        self.assertTrue(success, "File blacklist add should succeed")

        # Create mock ticker data
        mock_tickers = [
            {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
            {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'},
            {'ticker': '035720', 'name': 'Kakao', 'market': 'KOSDAQ'}
        ]

        # Mock FilterResult to always pass for market filter (isolate blacklist testing)
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        # When: Apply filters with mocked market filter
        with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', return_value=mock_result):
            filtered = self.scanner._apply_spock_filters(mock_tickers)

        # Then: File-blacklisted ticker should be removed
        filtered_tickers = [t['ticker'] for t in filtered]
        self.assertNotIn('035720', filtered_tickers, "File-blacklisted ticker should be filtered out")
        self.assertIn('005930', filtered_tickers, "Non-blacklisted ticker should pass through")

    # ====================================================================
    # Test 3: Non-Blacklisted Tickers Pass Through
    # ====================================================================

    def test_03_non_blacklisted_pass_through(self):
        """Test that non-blacklisted tickers pass through Stage 0 filtering"""
        # Given: No blacklisted tickers
        is_blacklisted_005930 = self.blacklist_manager.is_blacklisted('005930', 'KR')
        is_blacklisted_000660 = self.blacklist_manager.is_blacklisted('000660', 'KR')

        self.assertFalse(is_blacklisted_005930, "005930 should not be blacklisted")
        self.assertFalse(is_blacklisted_000660, "000660 should not be blacklisted")

        # Create mock ticker data
        mock_tickers = [
            {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
            {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'}
        ]

        # Mock FilterResult to always pass for market filter (isolate blacklist testing)
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        # When: Apply filters with mocked market filter
        with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', return_value=mock_result):
            filtered = self.scanner._apply_spock_filters(mock_tickers)

        # Then: Both tickers should pass through (not blacklisted)
        filtered_tickers = [t['ticker'] for t in filtered]
        self.assertIn('005930', filtered_tickers, "005930 should pass through all filters")
        self.assertIn('000660', filtered_tickers, "000660 should pass through all filters")

    # ====================================================================
    # Test 4: Blacklist Filter Priority (Before Market Filters)
    # ====================================================================

    def test_04_blacklist_filter_priority(self):
        """Test that blacklist filtering occurs BEFORE market filter checks"""
        # Given: Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Priority check'
        )

        # Create mock ticker data
        mock_tickers = [
            {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
            {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'}
        ]

        # Mock FilterResult and count how many times market filter is called
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        call_count = {'count': 0}

        def counting_apply(*args, **kwargs):
            call_count['count'] += 1
            return mock_result

        with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', side_effect=counting_apply):
            filtered = self.scanner._apply_spock_filters(mock_tickers)

        # Then: MarketFilterManager should only be called for non-blacklisted tickers
        # (1 call for 000660, 0 calls for blacklisted 005930)
        self.assertLess(call_count['count'], len(mock_tickers),
                       "MarketFilterManager should not be called for blacklisted tickers")

    # ====================================================================
    # Test 5: Bulk Filtering Performance
    # ====================================================================

    def test_05_bulk_filtering_used(self):
        """Test that bulk filtering method is used for performance"""
        # Mock FilterResult to always pass for market filter (isolate blacklist testing)
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        # Given: Mock blacklist manager method
        with patch.object(self.blacklist_manager, 'filter_blacklisted_tickers', wraps=self.blacklist_manager.filter_blacklisted_tickers) as mock_filter:
            # Create mock ticker data
            mock_tickers = [
                {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
                {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'},
                {'ticker': '035720', 'name': 'Kakao', 'market': 'KOSDAQ'}
            ]

            # When: Apply filters with mocked market filter
            with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', return_value=mock_result):
                filtered = self.scanner._apply_spock_filters(mock_tickers)

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

        # Given: Capture log output from the modules.scanner logger
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        # Get the modules.scanner logger (same as scanner.py uses)
        scanner_logger = logging.getLogger('modules.scanner')
        scanner_logger.addHandler(handler)
        scanner_logger.setLevel(logging.INFO)

        # Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Statistics'
        )

        # Create mock ticker data
        mock_tickers = [
            {'ticker': '005930', 'name': 'Samsung Electronics', 'market': 'KOSPI'},
            {'ticker': '000660', 'name': 'SK Hynix', 'market': 'KOSPI'}
        ]

        # Mock FilterResult to always pass for market filter (isolate blacklist testing)
        from modules.market_filter_manager import FilterResult
        mock_result = FilterResult(passed=True, reason='', normalized_data={})

        # When: Apply filters with mocked market filter
        with patch.object(self.scanner.filter_manager, 'apply_stage0_filter', return_value=mock_result):
            filtered = self.scanner._apply_spock_filters(mock_tickers)

        # Then: Log should contain blacklist statistics
        log_output = log_stream.getvalue()
        self.assertIn('Blacklist', log_output, "Log should mention blacklist filtering")

        # Cleanup
        scanner_logger.removeHandler(handler)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
