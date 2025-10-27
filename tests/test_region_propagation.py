#!/usr/bin/env python3
"""
Unit Tests for Region Propagation

Tests region parameter propagation through adapter → database layer.

Author: Spock Trading System
Date: 2025-10-15
"""

import unittest
import os
import sys
import tempfile
import sqlite3
from datetime import datetime
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters.base_adapter import BaseMarketAdapter


class MockAdapter(BaseMarketAdapter):
    """
    Mock adapter for testing region propagation

    Inherits from BaseMarketAdapter to test:
    - _save_ohlcv_to_db() method
    - Automatic region injection
    """

    def __init__(self, db_manager, region_code: str):
        """Initialize mock adapter"""
        super().__init__(db_manager, region_code)

    def scan_stocks(self, force_refresh: bool = False):
        """Mock implementation"""
        return []

    def scan_etfs(self, force_refresh: bool = False):
        """Mock implementation"""
        return []

    def collect_stock_ohlcv(self, tickers=None, days=250):
        """Mock implementation"""
        return 0

    def collect_etf_ohlcv(self, tickers=None, days=250):
        """Mock implementation"""
        return 0


class TestRegionPropagation(unittest.TestCase):
    """Test region parameter propagation"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once"""
        # Create temporary database
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_path = cls.temp_db.name
        cls.temp_db.close()

        # Initialize schema manually
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create tickers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickers (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_eng TEXT,
                exchange TEXT NOT NULL,
                market_tier TEXT DEFAULT 'MAIN',
                region TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'KRW',
                asset_type TEXT NOT NULL DEFAULT 'STOCK',
                listing_date TEXT,
                is_active BOOLEAN DEFAULT 1,
                delisting_date TEXT,
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                data_source TEXT
            )
        """)

        # Create ohlcv_data table with region column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                date TEXT NOT NULL,
                region TEXT,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume BIGINT NOT NULL,
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                ma120 REAL,
                ma200 REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                atr_14 REAL,
                created_at TEXT NOT NULL,
                UNIQUE(ticker, region, timeframe, date),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

        conn.commit()
        conn.close()

        # Initialize database manager
        cls.db = SQLiteDatabaseManager(db_path=cls.db_path)

        print(f"\n🗄️  Test database: {cls.db_path}")

    @classmethod
    def tearDownClass(cls):
        """Cleanup after all tests"""
        # Delete temporary database
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)
            print(f"🗑️  Cleaned up test database")

    def setUp(self):
        """Setup before each test"""
        # Clear ohlcv_data table
        conn = self.db._get_connection()
        conn.execute("DELETE FROM ohlcv_data")
        conn.commit()
        conn.close()

    def test_01_database_layer_region_parameter(self):
        """Test 1: Database layer accepts region parameter"""
        print("\n📊 Test 1: Database Layer Region Parameter")

        # Create test DataFrame
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        # Insert with region='TEST'
        inserted_count = self.db.insert_ohlcv_bulk(
            ticker='TEST001',
            ohlcv_df=test_df,
            timeframe='D',
            region='TEST'
        )

        # Assertions
        self.assertEqual(inserted_count, 1, "Should insert 1 row")

        # Verify region in database
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT region FROM ohlcv_data WHERE ticker = 'TEST001'")
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result, "Should find inserted row")
        self.assertEqual(result[0], 'TEST', "Region should be 'TEST'")

        print(f"✅ Database layer correctly stores region='TEST'")

    def test_02_database_layer_null_region_warning(self):
        """Test 2: Database layer warns on NULL region"""
        print("\n⚠️  Test 2: Database Layer NULL Region Warning")

        # Create test DataFrame
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        # Insert without region (should warn but not fail)
        inserted_count = self.db.insert_ohlcv_bulk(
            ticker='TEST002',
            ohlcv_df=test_df,
            timeframe='D',
            region=None  # Explicit NULL
        )

        # Assertions
        self.assertEqual(inserted_count, 1, "Should still insert row")

        # Verify region is NULL
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT region FROM ohlcv_data WHERE ticker = 'TEST002'")
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result, "Should find inserted row")
        self.assertIsNone(result[0], "Region should be NULL")

        print(f"✅ Database layer allows NULL region (backward compatibility)")

    def test_03_base_adapter_auto_injection(self):
        """Test 3: BaseAdapter auto-injects region"""
        print("\n🔧 Test 3: BaseAdapter Auto-Injection")

        # Create mock adapter for KR region
        adapter = MockAdapter(self.db, region_code='KR')

        # Create test DataFrame
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000],
            'ma5': [102.0],
            'rsi_14': [50.0]
        })

        # Use BaseAdapter's _save_ohlcv_to_db (should auto-inject region='KR')
        adapter._save_ohlcv_to_db('TEST003', test_df, period_type='DAILY')

        # Verify region in database
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT region FROM ohlcv_data WHERE ticker = 'TEST003'")
        result = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(result, "Should find inserted row")
        self.assertEqual(result[0], 'KR', "Region should be auto-injected as 'KR'")

        print(f"✅ BaseAdapter auto-injected region='KR'")

    def test_04_multi_region_separation(self):
        """Test 4: Multi-region data separation"""
        print("\n🌍 Test 4: Multi-Region Data Separation")

        # Create adapters for different regions
        kr_adapter = MockAdapter(self.db, region_code='KR')
        us_adapter = MockAdapter(self.db, region_code='US')
        cn_adapter = MockAdapter(self.db, region_code='CN')

        # Create test DataFrame
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        # Insert same ticker with different regions
        kr_adapter._save_ohlcv_to_db('TEST004', test_df, period_type='DAILY')
        us_adapter._save_ohlcv_to_db('TEST004', test_df, period_type='DAILY')
        cn_adapter._save_ohlcv_to_db('TEST004', test_df, period_type='DAILY')

        # Count rows by region
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT region, COUNT(*) as count
            FROM ohlcv_data
            WHERE ticker = 'TEST004'
            GROUP BY region
            ORDER BY region
        """)
        results = cursor.fetchall()
        conn.close()

        # Assertions
        self.assertEqual(len(results), 3, "Should have 3 different regions")

        regions = {row[0]: row[1] for row in results}
        self.assertEqual(regions.get('CN'), 1, "Should have 1 CN row")
        self.assertEqual(regions.get('KR'), 1, "Should have 1 KR row")
        self.assertEqual(regions.get('US'), 1, "Should have 1 US row")

        print(f"✅ Multi-region separation working correctly")
        print(f"   KR: {regions.get('KR')} rows")
        print(f"   US: {regions.get('US')} rows")
        print(f"   CN: {regions.get('CN')} rows")

    def test_05_region_query_filtering(self):
        """Test 5: Region-based query filtering"""
        print("\n🔍 Test 5: Region-Based Query Filtering")

        # Insert test data for multiple regions
        kr_adapter = MockAdapter(self.db, region_code='KR')
        us_adapter = MockAdapter(self.db, region_code='US')

        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        kr_adapter._save_ohlcv_to_db('005930', test_df, period_type='DAILY')  # Samsung (KR)
        us_adapter._save_ohlcv_to_db('AAPL', test_df, period_type='DAILY')    # Apple (US)

        # Query KR region only
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, region
            FROM ohlcv_data
            WHERE region = 'KR'
        """)
        kr_results = cursor.fetchall()
        conn.close()

        # Query US region only
        conn2 = self.db._get_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT ticker, region
            FROM ohlcv_data
            WHERE region = 'US'
        """)
        us_results = cursor2.fetchall()
        conn2.close()

        # Assertions
        self.assertEqual(len(kr_results), 1, "Should find 1 KR row")
        self.assertEqual(len(us_results), 1, "Should find 1 US row")

        self.assertEqual(kr_results[0][0], '005930', "KR row should be Samsung")
        self.assertEqual(us_results[0][0], 'AAPL', "US row should be Apple")

        print(f"✅ Region-based filtering working correctly")
        print(f"   KR: {kr_results[0][0]}")
        print(f"   US: {us_results[0][0]}")

    def test_06_invalid_region_warning(self):
        """Test 6: Invalid region code warning"""
        print("\n⚠️  Test 6: Invalid Region Code Warning")

        # Create test DataFrame
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        # Insert with invalid region
        inserted_count = self.db.insert_ohlcv_bulk(
            ticker='TEST006',
            ohlcv_df=test_df,
            timeframe='D',
            region='INVALID'  # Invalid region code
        )

        # Should still insert (warning only)
        self.assertEqual(inserted_count, 1, "Should insert despite invalid region")

        # Verify region is stored as-is
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT region FROM ohlcv_data WHERE ticker = 'TEST006'")
        result = cursor.fetchone()
        conn.close()

        self.assertEqual(result[0], 'INVALID', "Should store invalid region as-is")

        print(f"✅ Invalid region code stored with warning")

    def test_07_technical_indicators_preserved(self):
        """Test 7: Technical indicators preserved with region"""
        print("\n📊 Test 7: Technical Indicators Preserved")

        # Create adapter
        adapter = MockAdapter(self.db, region_code='KR')

        # Create DataFrame with technical indicators
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000],
            'ma5': [102.0],
            'ma20': [101.5],
            'ma60': [100.0],
            'ma120': [99.0],
            'ma200': [98.0],
            'rsi_14': [55.0],
            'macd': [1.5],
            'macd_signal': [1.2],
            'macd_hist': [0.3],
            'bb_upper': [106.0],
            'bb_middle': [103.0],
            'bb_lower': [100.0],
            'atr_14': [2.5]
        })

        # Save with region
        adapter._save_ohlcv_to_db('TEST007', test_df, period_type='DAILY')

        # Verify all columns
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT region, ma5, ma20, rsi_14, macd, bb_upper, atr_14
            FROM ohlcv_data
            WHERE ticker = 'TEST007'
        """)
        result = cursor.fetchone()
        conn.close()

        # Assertions
        self.assertIsNotNone(result, "Should find row")
        self.assertEqual(result[0], 'KR', "Region should be KR")
        self.assertEqual(result[1], 102.0, "MA5 should be preserved")
        self.assertEqual(result[2], 101.5, "MA20 should be preserved")
        self.assertEqual(result[3], 55.0, "RSI should be preserved")
        self.assertEqual(result[4], 1.5, "MACD should be preserved")
        self.assertEqual(result[5], 106.0, "BB upper should be preserved")
        self.assertEqual(result[6], 2.5, "ATR should be preserved")

        print(f"✅ All technical indicators preserved with region")


class TestRegionMigration(unittest.TestCase):
    """Test region migration scenarios"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment"""
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_path = cls.temp_db.name
        cls.temp_db.close()

        # Initialize schema manually
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create tickers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickers (
                ticker TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_eng TEXT,
                exchange TEXT NOT NULL,
                market_tier TEXT DEFAULT 'MAIN',
                region TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'KRW',
                asset_type TEXT NOT NULL DEFAULT 'STOCK',
                listing_date TEXT,
                is_active BOOLEAN DEFAULT 1,
                delisting_date TEXT,
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                data_source TEXT
            )
        """)

        # Create ohlcv_data table with region column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                date TEXT NOT NULL,
                region TEXT,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume BIGINT NOT NULL,
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                ma120 REAL,
                ma200 REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,
                atr_14 REAL,
                created_at TEXT NOT NULL,
                UNIQUE(ticker, region, timeframe, date),
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

        conn.commit()
        conn.close()

        cls.db = SQLiteDatabaseManager(db_path=cls.db_path)

        print(f"\n🗄️  Test database: {cls.db_path}")

    @classmethod
    def tearDownClass(cls):
        """Cleanup"""
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)

    def test_08_migrate_null_regions(self):
        """Test 8: Migrate NULL regions using tickers table JOIN"""
        print("\n🔄 Test 8: Migrate NULL Regions")

        # Step 1: Insert ticker into tickers table
        self.db.insert_ticker({
            'ticker': '005930',
            'name': 'Samsung Electronics',
            'exchange': 'KOSPI',
            'region': 'KR',
            'currency': 'KRW',
            'asset_type': 'STOCK',
            'created_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        })

        # Step 2: Insert OHLCV data with NULL region (legacy data)
        test_df = pd.DataFrame({
            'date': [datetime.now().strftime('%Y-%m-%d')],
            'open': [100.0],
            'high': [105.0],
            'low': [99.0],
            'close': [103.0],
            'volume': [1000000]
        })

        self.db.insert_ohlcv_bulk(
            ticker='005930',
            ohlcv_df=test_df,
            timeframe='D',
            region=None  # NULL region (legacy)
        )

        # Verify NULL region
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT region FROM ohlcv_data WHERE ticker = '005930'")
        result = cursor.fetchone()
        conn.close()
        self.assertIsNone(result[0], "Region should be NULL initially")

        # Step 3: Migrate using JOIN
        conn2 = self.db._get_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("""
            UPDATE ohlcv_data
            SET region = (
                SELECT t.region
                FROM tickers t
                WHERE t.ticker = ohlcv_data.ticker
            )
            WHERE region IS NULL
            AND ticker IN (SELECT ticker FROM tickers)
        """)
        conn2.commit()

        # Step 4: Verify migration
        cursor2.execute("SELECT region FROM ohlcv_data WHERE ticker = '005930'")
        result = cursor2.fetchone()
        conn2.close()

        self.assertIsNotNone(result, "Should find row")
        self.assertEqual(result[0], 'KR', "Region should be migrated to 'KR'")

        print(f"✅ Successfully migrated NULL region to 'KR'")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
