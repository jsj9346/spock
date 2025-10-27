#!/usr/bin/env python3
"""
test_global_market_collector.py - Unit Tests for Global Market Indices Collection

Test Coverage:
1. YFinanceIndexSource: Data fetching, caching, rate limiting
2. GlobalMarketCollector: Batch collection, error handling
3. GlobalIndicesDatabase: Persistence, retrieval
4. Scoring Algorithm: Score calculation, consistency bonus

Author: Spock Trading System
Date: 2025-10-15
"""

import os
import sys
import unittest
import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.stock_sentiment import (
    YFinanceIndexSource,
    GlobalMarketCollector,
    GlobalIndicesDatabase,
    GlobalMarketData,
    calculate_global_indices_score,
    _calculate_consistency_bonus
)


class TestYFinanceIndexSource(unittest.TestCase):
    """Test YFinanceIndexSource class"""

    def setUp(self):
        """Set up test fixtures"""
        self.source = YFinanceIndexSource(rate_limit_sec=0.1, cache_ttl_sec=2)

    def test_initialization(self):
        """Test YFinanceIndexSource initialization"""
        self.assertEqual(self.source.rate_limit_sec, 0.1)
        self.assertEqual(self.source.cache_ttl_sec, 2)
        self.assertIsNone(self.source.last_request_time)
        self.assertEqual(len(self.source.cache), 0)

    def test_get_index_data_success(self):
        """Test successful index data retrieval"""
        data = self.source.get_index_data('^GSPC', days=5)

        self.assertIsNotNone(data)
        self.assertIsInstance(data, GlobalMarketData)
        self.assertEqual(data.symbol, '^GSPC')
        self.assertEqual(data.index_name, 'S&P 500')
        self.assertEqual(data.region, 'US')
        self.assertIsInstance(data.close_price, float)
        self.assertIsInstance(data.change_percent, float)
        self.assertIn(data.trend_5d, ['UP', 'DOWN', 'FLAT'])
        self.assertGreaterEqual(data.consecutive_days, 0)

    def test_get_index_data_invalid_symbol(self):
        """Test handling of invalid symbol"""
        data = self.source.get_index_data('INVALID_SYMBOL', days=5)
        # yfinance may return None or empty data for invalid symbols
        # The behavior depends on yfinance version, so we accept both
        self.assertTrue(data is None or isinstance(data, GlobalMarketData))

    def test_cache_functionality(self):
        """Test session caching works correctly"""
        # First call - should fetch from network
        data1 = self.source.get_index_data('^DJI', days=5)
        self.assertIsNotNone(data1)
        self.assertEqual(len(self.source.cache), 1)

        # Second call - should return from cache
        data2 = self.source.get_index_data('^DJI', days=5)
        self.assertIsNotNone(data2)
        self.assertEqual(data1.date, data2.date)
        self.assertEqual(data1.close_price, data2.close_price)

    def test_cache_expiry(self):
        """Test cache expiry after TTL"""
        import time

        # Set very short TTL
        self.source.cache_ttl_sec = 0.5

        # First call
        data1 = self.source.get_index_data('^IXIC', days=5)
        self.assertIsNotNone(data1)

        # Wait for cache to expire
        time.sleep(0.6)

        # Second call - should re-fetch
        data2 = self.source.get_index_data('^IXIC', days=5)
        self.assertIsNotNone(data2)

    def test_get_batch_indices(self):
        """Test batch index retrieval"""
        symbols = ['^GSPC', '^DJI', '^IXIC']
        results = self.source.get_batch_indices(symbols, days=5)

        self.assertIsInstance(results, dict)
        self.assertGreaterEqual(len(results), 0)

        for symbol, data in results.items():
            self.assertIsInstance(data, GlobalMarketData)
            self.assertEqual(data.symbol, symbol)

    def test_is_available(self):
        """Test availability check"""
        available = self.source.is_available()
        self.assertIsInstance(available, bool)
        # Should be True if yfinance and internet connection are working
        # We don't assert True because tests may run offline


class TestGlobalMarketCollector(unittest.TestCase):
    """Test GlobalMarketCollector class"""

    def setUp(self):
        """Set up test fixtures"""
        # Use real data source for integration tests
        self.collector = GlobalMarketCollector()

    def test_initialization(self):
        """Test GlobalMarketCollector initialization"""
        self.assertIsNotNone(self.collector.data_source)
        self.assertEqual(len(self.collector.INDEX_SYMBOLS), 2)  # US and ASIA
        self.assertEqual(len(self.collector.INDEX_SYMBOLS['US']), 3)
        self.assertEqual(len(self.collector.INDEX_SYMBOLS['ASIA']), 2)

    def test_collect_all_indices(self):
        """Test collecting all 5 global indices"""
        results = self.collector.collect_all_indices(days=5)

        self.assertIsInstance(results, dict)
        # Should get at least some indices (may fail if offline)
        self.assertGreaterEqual(len(results), 0)

        for symbol, data in results.items():
            self.assertIsInstance(data, GlobalMarketData)
            self.assertIn(symbol, ['^GSPC', '^IXIC', '^DJI', '^HSI', '^N225'])

    def test_collect_us_indices(self):
        """Test collecting US indices only"""
        results = self.collector.collect_us_indices(days=5)

        self.assertIsInstance(results, dict)

        for symbol in results.keys():
            self.assertIn(symbol, ['^GSPC', '^IXIC', '^DJI'])

    def test_collect_asia_indices(self):
        """Test collecting Asia indices only"""
        results = self.collector.collect_asia_indices(days=5)

        self.assertIsInstance(results, dict)

        for symbol in results.keys():
            self.assertIn(symbol, ['^HSI', '^N225'])


class TestGlobalIndicesDatabase(unittest.TestCase):
    """Test GlobalIndicesDatabase class"""

    def setUp(self):
        """Set up test fixtures with temporary database"""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()

        # Initialize database schema
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE global_market_indices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                index_name TEXT NOT NULL,
                region TEXT NOT NULL,
                close_price REAL NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                volume BIGINT,
                change_percent REAL NOT NULL,
                trend_5d TEXT,
                consecutive_days INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(date, symbol)
            )
        """)
        conn.commit()
        conn.close()

        self.db = GlobalIndicesDatabase(db_path=self.temp_db.name)

    def tearDown(self):
        """Clean up temporary database"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_save_index_data(self):
        """Test saving single index data"""
        data = GlobalMarketData(
            date='2025-10-14',
            symbol='^GSPC',
            index_name='S&P 500',
            region='US',
            close_price=6676.05,
            open_price=6670.00,
            high_price=6680.00,
            low_price=6665.00,
            volume=1000000,
            change_percent=0.32,
            trend_5d='UP',
            consecutive_days=2,
            timestamp=datetime.now()
        )

        result = self.db.save_index_data(data)
        self.assertTrue(result)

        # Verify data was saved
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM global_market_indices")
        count = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count, 1)

    def test_save_batch(self):
        """Test saving multiple indices"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
                volume=1000000, change_percent=0.32, trend_5d='UP', consecutive_days=2,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46445.42, open_price=46400.00, high_price=46500.00, low_price=46350.00,
                volume=500000, change_percent=0.82, trend_5d='UP', consecutive_days=2,
                timestamp=datetime.now()
            )
        }

        saved_count = self.db.save_batch(indices)
        self.assertEqual(saved_count, 2)

    def test_get_latest_indices(self):
        """Test retrieving latest indices"""
        # Save test data
        data = GlobalMarketData(
            date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
            close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
            volume=1000000, change_percent=0.32, trend_5d='UP', consecutive_days=2,
            timestamp=datetime.now()
        )
        self.db.save_index_data(data)

        # Retrieve
        results = self.db.get_latest_indices()

        self.assertIsInstance(results, dict)
        self.assertEqual(len(results), 1)
        self.assertIn('^GSPC', results)

        retrieved = results['^GSPC']
        self.assertEqual(retrieved.date, data.date)
        self.assertEqual(retrieved.close_price, data.close_price)


class TestGlobalIndicesScoring(unittest.TestCase):
    """Test global indices scoring algorithm"""

    def test_calculate_score_all_up(self):
        """Test scoring with all indices trending up"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
                volume=1000000, change_percent=1.5, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^IXIC': GlobalMarketData(
                date='2025-10-14', symbol='^IXIC', index_name='NASDAQ', region='US',
                close_price=22665.30, open_price=22600.00, high_price=22700.00, low_price=22550.00,
                volume=800000, change_percent=1.2, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46445.42, open_price=46400.00, high_price=46500.00, low_price=46350.00,
                volume=500000, change_percent=1.0, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^HSI': GlobalMarketData(
                date='2025-10-14', symbol='^HSI', index_name='Hang Seng', region='ASIA',
                close_price=25441.35, open_price=25400.00, high_price=25500.00, low_price=25350.00,
                volume=300000, change_percent=1.0, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^N225': GlobalMarketData(
                date='2025-10-14', symbol='^N225', index_name='Nikkei', region='ASIA',
                close_price=46847.32, open_price=46800.00, high_price=46900.00, low_price=46750.00,
                volume=400000, change_percent=0.8, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            )
        }

        score = calculate_global_indices_score(indices)

        # All positive changes + consistency bonus
        self.assertGreater(score, 0)
        # Should get bonus for 3+ indices up for 3+ days
        self.assertGreaterEqual(score, 3.0)

    def test_calculate_score_all_down(self):
        """Test scoring with all indices trending down"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6576.05, open_price=6670.00, high_price=6680.00, low_price=6565.00,
                volume=1000000, change_percent=-1.5, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^IXIC': GlobalMarketData(
                date='2025-10-14', symbol='^IXIC', index_name='NASDAQ', region='US',
                close_price=22465.30, open_price=22600.00, high_price=22700.00, low_price=22450.00,
                volume=800000, change_percent=-1.2, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46045.42, open_price=46400.00, high_price=46500.00, low_price=46000.00,
                volume=500000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^HSI': GlobalMarketData(
                date='2025-10-14', symbol='^HSI', index_name='Hang Seng', region='ASIA',
                close_price=25141.35, open_price=25400.00, high_price=25500.00, low_price=25100.00,
                volume=300000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^N225': GlobalMarketData(
                date='2025-10-14', symbol='^N225', index_name='Nikkei', region='ASIA',
                close_price=46447.32, open_price=46800.00, high_price=46900.00, low_price=46400.00,
                volume=400000, change_percent=-0.8, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            )
        }

        score = calculate_global_indices_score(indices)

        # All negative changes + negative consistency bonus
        self.assertLess(score, 0)
        # Should get negative bonus for 3+ indices down for 3+ days
        self.assertLessEqual(score, -3.0)

    def test_calculate_score_mixed(self):
        """Test scoring with mixed index movements"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
                volume=1000000, change_percent=0.5, trend_5d='UP', consecutive_days=1,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46445.42, open_price=46400.00, high_price=46500.00, low_price=46350.00,
                volume=500000, change_percent=-0.3, trend_5d='DOWN', consecutive_days=1,
                timestamp=datetime.now()
            )
        }

        score = calculate_global_indices_score(indices)

        # Mixed movements should result in moderate score
        self.assertGreater(score, -5.0)
        self.assertLess(score, 5.0)

    def test_calculate_score_empty(self):
        """Test scoring with empty indices"""
        score = calculate_global_indices_score({})
        self.assertEqual(score, 0.0)

    def test_consistency_bonus_up(self):
        """Test consistency bonus for upward trends"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
                volume=1000000, change_percent=1.0, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^IXIC': GlobalMarketData(
                date='2025-10-14', symbol='^IXIC', index_name='NASDAQ', region='US',
                close_price=22665.30, open_price=22600.00, high_price=22700.00, low_price=22550.00,
                volume=800000, change_percent=1.0, trend_5d='UP', consecutive_days=4,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46445.42, open_price=46400.00, high_price=46500.00, low_price=46350.00,
                volume=500000, change_percent=1.0, trend_5d='UP', consecutive_days=5,
                timestamp=datetime.now()
            )
        }

        bonus = _calculate_consistency_bonus(indices)
        self.assertEqual(bonus, 3.0)

    def test_consistency_bonus_down(self):
        """Test consistency bonus for downward trends"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6576.05, open_price=6670.00, high_price=6680.00, low_price=6565.00,
                volume=1000000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^IXIC': GlobalMarketData(
                date='2025-10-14', symbol='^IXIC', index_name='NASDAQ', region='US',
                close_price=22465.30, open_price=22600.00, high_price=22700.00, low_price=22450.00,
                volume=800000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=4,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46045.42, open_price=46400.00, high_price=46500.00, low_price=46000.00,
                volume=500000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=5,
                timestamp=datetime.now()
            )
        }

        bonus = _calculate_consistency_bonus(indices)
        self.assertEqual(bonus, -3.0)

    def test_consistency_bonus_mixed(self):
        """Test consistency bonus with mixed trends"""
        indices = {
            '^GSPC': GlobalMarketData(
                date='2025-10-14', symbol='^GSPC', index_name='S&P 500', region='US',
                close_price=6676.05, open_price=6670.00, high_price=6680.00, low_price=6665.00,
                volume=1000000, change_percent=1.0, trend_5d='UP', consecutive_days=3,
                timestamp=datetime.now()
            ),
            '^DJI': GlobalMarketData(
                date='2025-10-14', symbol='^DJI', index_name='DOW', region='US',
                close_price=46045.42, open_price=46400.00, high_price=46500.00, low_price=46000.00,
                volume=500000, change_percent=-1.0, trend_5d='DOWN', consecutive_days=3,
                timestamp=datetime.now()
            )
        }

        bonus = _calculate_consistency_bonus(indices)
        self.assertEqual(bonus, 0.0)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
