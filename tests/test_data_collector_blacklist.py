#!/usr/bin/env python3
"""
Data Collector Blacklist Integration Tests

Tests the blacklist functionality integrated into KISDataCollector.
Validates that:
1. Blacklisted tickers are filtered out BEFORE KIS API calls (DB blacklist)
2. Blacklisted tickers are filtered out BEFORE KIS API calls (file blacklist)
3. Non-blacklisted tickers pass through to OHLCV data collection
4. Blacklist filtering occurs BEFORE Stage 0 market filter checks (resource efficiency)
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
from unittest.mock import patch, MagicMock, Mock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.kis_data_collector import KISDataCollector
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from init_db import DatabaseInitializer


class TestDataCollectorBlacklist(unittest.TestCase):
    """Test suite for Data Collector blacklist integration"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests"""
        cls.test_db_path = "data/test_data_collector_blacklist.db"
        cls.test_blacklist_path = "config/test_data_collector_blacklist.json"

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

        # Initialize Data Collector in mock mode (no real API calls)
        # Set environment variables to empty to force mock mode
        os.environ['KIS_APP_KEY'] = ''
        os.environ['KIS_APP_SECRET'] = ''

        self.collector = KISDataCollector(
            db_path=self.test_db_path,
            region='KR'
        )

        # Override blacklist manager config_path to use test file
        self.collector.blacklist_manager.config_path = self.test_blacklist_path
        self.collector.blacklist_manager._load_file_blacklist()

        # Keep references for test assertions
        self.db_manager = SQLiteDatabaseManager(db_path=self.test_db_path)
        self.blacklist_manager = self.collector.blacklist_manager

    def tearDown(self):
        """Clean up after each test"""
        import time
        import gc

        # Force close all connections
        try:
            del self.collector
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
    # Test 1: DB Blacklist Filtering (Before API Calls)
    # ====================================================================

    def test_01_db_blacklist_filtering_before_api_calls(self):
        """Test that DB-blacklisted tickers are filtered out BEFORE KIS API calls"""
        # Given: Blacklist one ticker in DB
        success = self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: DB blacklist'
        )
        self.assertTrue(success, "Deactivation should succeed")

        # Mock safe_get_ohlcv to track which tickers are requested
        called_tickers = []

        def mock_get_ohlcv(ticker, count, timeframe):
            called_tickers.append(ticker)
            # Return mock DataFrame for non-blacklisted tickers
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        # Mock filter_manager to always pass (isolate blacklist testing)
        with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
            with patch.object(self.collector, '_run_stage0_filter', side_effect=lambda tickers: tickers):
                # When: Collect data with filtering
                stats = self.collector.collect_with_filtering(
                    tickers=['005930', '000660', '035720'],
                    days=30,
                    apply_stage0=False
                )

        # Then: Blacklisted ticker should be filtered out BEFORE API calls
        self.assertEqual(stats['blacklist_rejected'], 1, "Should reject 1 blacklisted ticker")
        self.assertEqual(stats['blacklist_passed'], 2, "Should pass 2 non-blacklisted tickers")

        # Verify that safe_get_ohlcv was NOT called for blacklisted ticker
        self.assertNotIn('005930', called_tickers, "Blacklisted ticker should not trigger API call")
        self.assertIn('000660', called_tickers, "Non-blacklisted ticker should trigger API call")
        self.assertIn('035720', called_tickers, "Non-blacklisted ticker should trigger API call")

    # ====================================================================
    # Test 2: File Blacklist Filtering (Before API Calls)
    # ====================================================================

    def test_02_file_blacklist_filtering_before_api_calls(self):
        """Test that file-blacklisted tickers are filtered out BEFORE KIS API calls"""
        # Given: Blacklist one ticker in file
        success = self.blacklist_manager.add_to_file_blacklist(
            ticker='035720',
            region='KR',
            reason='Test: File blacklist',
            added_by='unit_test'
        )
        self.assertTrue(success, "File blacklist add should succeed")

        # Mock safe_get_ohlcv to track which tickers are requested
        called_tickers = []

        def mock_get_ohlcv(ticker, count, timeframe):
            called_tickers.append(ticker)
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
            with patch.object(self.collector, '_run_stage0_filter', side_effect=lambda tickers: tickers):
                # When: Collect data with filtering
                stats = self.collector.collect_with_filtering(
                    tickers=['005930', '000660', '035720'],
                    days=30,
                    apply_stage0=False
                )

        # Then: File-blacklisted ticker should be filtered out BEFORE API calls
        self.assertEqual(stats['blacklist_rejected'], 1, "Should reject 1 file-blacklisted ticker")
        self.assertEqual(stats['blacklist_passed'], 2, "Should pass 2 non-blacklisted tickers")

        # Verify that safe_get_ohlcv was NOT called for blacklisted ticker
        self.assertNotIn('035720', called_tickers, "File-blacklisted ticker should not trigger API call")

    # ====================================================================
    # Test 3: Non-Blacklisted Tickers Pass Through
    # ====================================================================

    def test_03_non_blacklisted_tickers_pass_through(self):
        """Test that non-blacklisted tickers pass through to OHLCV collection"""
        # Given: No blacklisted tickers
        is_blacklisted_005930 = self.blacklist_manager.is_blacklisted('005930', 'KR')
        is_blacklisted_000660 = self.blacklist_manager.is_blacklisted('000660', 'KR')

        self.assertFalse(is_blacklisted_005930, "005930 should not be blacklisted")
        self.assertFalse(is_blacklisted_000660, "000660 should not be blacklisted")

        def mock_get_ohlcv(ticker, count, timeframe):
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
            with patch.object(self.collector, '_run_stage0_filter', side_effect=lambda tickers: tickers):
                # When: Collect data with filtering
                stats = self.collector.collect_with_filtering(
                    tickers=['005930', '000660'],
                    days=30,
                    apply_stage0=False
                )

        # Then: Both tickers should pass through blacklist filter
        self.assertEqual(stats['blacklist_rejected'], 0, "Should reject 0 tickers")
        self.assertEqual(stats['blacklist_passed'], 2, "Should pass 2 non-blacklisted tickers")

    # ====================================================================
    # Test 4: Blacklist Filter Priority (Before Stage 0)
    # ====================================================================

    def test_04_blacklist_filter_before_stage0(self):
        """Test that blacklist filtering occurs BEFORE Stage 0 filter (resource efficiency)"""
        # Given: Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Priority check'
        )

        # Mock Stage 0 filter and count how many tickers it receives
        call_count = {'count': 0}

        def counting_run_stage0(tickers):
            call_count['count'] = len(tickers)  # Count tickers received after blacklist filter
            return tickers  # Pass all tickers

        def mock_get_ohlcv(ticker, count, timeframe):
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        # Enable filtering temporarily for this test
        self.collector.filtering_enabled = True

        with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
            with patch.object(self.collector, '_run_stage0_filter', side_effect=counting_run_stage0):
                # When: Collect data with filtering
                stats = self.collector.collect_with_filtering(
                    tickers=['005930', '000660', '035720'],
                    days=30,
                    apply_stage0=True
                )

        # Then: Stage 0 filter should only receive non-blacklisted tickers
        # (2 tickers: 000660 and 035720, not blacklisted 005930)
        self.assertEqual(call_count['count'], 2,
                       "Stage 0 filter should only receive non-blacklisted tickers")
        self.assertEqual(stats['blacklist_rejected'], 1, "Should reject 1 blacklisted ticker")

    # ====================================================================
    # Test 5: Bulk Filtering Performance
    # ====================================================================

    def test_05_bulk_filtering_used(self):
        """Test that bulk filtering method is used for performance"""
        def mock_get_ohlcv(ticker, count, timeframe):
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        # Mock blacklist manager's bulk filter method
        with patch.object(self.blacklist_manager, 'filter_blacklisted_tickers',
                        wraps=self.blacklist_manager.filter_blacklisted_tickers) as mock_bulk_filter:

            with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
                with patch.object(self.collector, '_run_stage0_filter', side_effect=lambda tickers: tickers):
                    # When: Collect data with filtering
                    stats = self.collector.collect_with_filtering(
                        tickers=['005930', '000660', '035720'],
                        days=30,
                        apply_stage0=False
                    )

            # Then: Bulk filter should be called once (not 3 individual calls)
            self.assertEqual(mock_bulk_filter.call_count, 1,
                           "Bulk filtering method should be called once")

            # Check it was called with all ticker codes
            call_args = mock_bulk_filter.call_args
            self.assertEqual(len(call_args[0][0]), 3,
                           "All ticker codes should be passed to bulk filter")

    # ====================================================================
    # Test 6: Statistics Logging
    # ====================================================================

    def test_06_statistics_logging(self):
        """Test that blacklist rejection statistics are properly logged"""
        import logging
        from io import StringIO

        # Given: Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)

        # Get the __main__ logger (where kis_data_collector logs are written)
        collector_logger = logging.getLogger(__name__.split('.')[0])  # Get root logger for module
        collector_logger.addHandler(handler)
        collector_logger.setLevel(logging.INFO)

        # Blacklist one ticker
        self.blacklist_manager.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test: Statistics'
        )

        def mock_get_ohlcv(ticker, count, timeframe):
            import pandas as pd
            dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
            return pd.DataFrame({
                'open': [50000]*30,
                'high': [51000]*30,
                'low': [49000]*30,
                'close': [50500]*30,
                'volume': [1000000]*30
            }, index=dates)

        with patch.object(self.collector, 'safe_get_ohlcv', side_effect=mock_get_ohlcv):
            with patch.object(self.collector, '_run_stage0_filter', side_effect=lambda tickers: tickers):
                # When: Collect data with filtering
                stats = self.collector.collect_with_filtering(
                    tickers=['005930', '000660', '035720'],
                    days=30,
                    apply_stage0=False
                )

        # Then: Statistics should show blacklist filtering
        self.assertEqual(stats['blacklist_rejected'], 1, "Should have blacklist_rejected in stats")
        self.assertEqual(stats['blacklist_passed'], 2, "Should have blacklist_passed in stats")

        # Cleanup
        collector_logger.removeHandler(handler)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
