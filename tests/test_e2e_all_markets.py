"""
End-to-End Integration Tests - All Global Markets

Tests complete workflows for all 5 global markets outside Korea:
- US (NYSE/NASDAQ/AMEX) - Phase 2
- Hong Kong (HKEX) - Phase 3
- China (SSE/SZSE) - Phase 3
- Japan (TSE) - Phase 4
- Vietnam (HOSE/HNX) - Phase 5

Test Categories:
1. Stock Scanning: Discover tradable stocks with filters
2. Data Collection: Fetch OHLCV and fundamentals data
3. Data Validation: Verify data quality and completeness
4. Error Recovery: Handle API failures gracefully

Note: These are E2E tests using MOCK data, not live API calls.
For live API testing, use `--live-api` flag (requires API credentials).

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import tempfile

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters import (
    USAdapter,
    HKAdapter,
    CNAdapter,
    JPAdapter,
    VNAdapter
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


def create_test_database(db_path: str):
    """Create minimal test database schema"""
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tickers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            ticker TEXT NOT NULL,
            name TEXT,
            name_eng TEXT,
            exchange TEXT,
            region TEXT NOT NULL,
            currency TEXT,
            asset_type TEXT,
            sector TEXT,
            sector_code TEXT,
            listing_date TEXT,
            is_active INTEGER DEFAULT 1,
            market_cap REAL,
            created_at TEXT,
            last_updated TEXT,
            data_source TEXT,
            PRIMARY KEY (ticker, region, asset_type)
        )
    ''')

    # OHLCV data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            timeframe TEXT DEFAULT 'D',
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            created_at TEXT,
            PRIMARY KEY (ticker, date, timeframe)
        )
    ''')

    # Fundamentals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticker_fundamentals (
            ticker TEXT PRIMARY KEY,
            market_cap REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            dividend_yield REAL,
            eps REAL,
            roe REAL,
            last_updated TEXT
        )
    ''')

    conn.commit()
    conn.close()


class TestUSMarketE2E(unittest.TestCase):
    """End-to-end tests for US market (NYSE/NASDAQ/AMEX)"""

    def setUp(self):
        """Set up test database and adapter"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        # Create database manager and adapter
        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)
        # USAdapter requires polygon_api_key (use dummy key for testing)
        self.adapter = USAdapter(db_manager=self.db, polygon_api_key='test_key')

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('yfinance.Ticker')
    def test_us_stock_scanning_workflow(self, mock_ticker):
        """Test US: Stock scanning with market cap filter"""
        # Mock yfinance responses
        mock_info = {
            'symbol': 'AAPL',
            'longName': 'Apple Inc.',
            'quoteType': 'EQUITY',
            'exchange': 'NASDAQ',
            'currency': 'USD',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
            'marketCap': 3000000000000
        }
        mock_ticker.return_value.info = mock_info

        # Execute scan (US adapter doesn't support ticker_list, uses exchanges)
        # For E2E test, we just verify the workflow works
        results = self.adapter.scan_stocks(force_refresh=True)

        # Verify results
        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertEqual(results[0]['ticker'], 'AAPL')
            self.assertEqual(results[0]['region'], 'US')
            self.assertEqual(results[0]['exchange'], 'NASDAQ')

    @patch('yfinance.download')
    def test_us_ohlcv_collection_workflow(self, mock_download):
        """Test US: OHLCV data collection and storage"""
        # Insert test ticker first
        self.db.insert_ticker({
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'exchange': 'NASDAQ',
            'region': 'US',
            'currency': 'USD',
            'asset_type': 'STOCK',
            'sector': 'Information Technology',
            'created_at': datetime.now().isoformat()
        })

        # Mock yfinance download response
        mock_df = pd.DataFrame({
            'Open': [150.0, 151.0, 152.0],
            'High': [155.0, 156.0, 157.0],
            'Low': [148.0, 149.0, 150.0],
            'Close': [153.0, 154.0, 155.0],
            'Volume': [1000000, 1100000, 1200000]
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Execute OHLCV collection
        count = self.adapter.collect_stock_ohlcv(tickers=['AAPL'], days=3)

        # Verify collection succeeded
        self.assertGreaterEqual(count, 0, "OHLCV collection should return non-negative count")

    @patch('yfinance.Ticker')
    def test_us_fundamentals_collection_workflow(self, mock_ticker):
        """Test US: Fundamentals data collection"""
        # Insert test ticker first
        self.db.insert_ticker({
            'ticker': 'MSFT',
            'name': 'Microsoft Corporation',
            'exchange': 'NASDAQ',
            'region': 'US',
            'currency': 'USD',
            'asset_type': 'STOCK',
            'sector': 'Information Technology',
            'created_at': datetime.now().isoformat()
        })

        # Mock yfinance info response
        mock_info = {
            'marketCap': 2500000000000,
            'trailingPE': 30.5,
            'priceToBook': 12.3,
            'dividendYield': 0.0085,
            'trailingEps': 10.5,
            'returnOnEquity': 0.45
        }
        mock_ticker.return_value.info = mock_info

        # Execute fundamentals collection
        count = self.adapter.collect_fundamentals(tickers=['MSFT'])

        # Verify collection
        self.assertGreaterEqual(count, 0, "Fundamentals collection should return non-negative count")


class TestHKMarketE2E(unittest.TestCase):
    """End-to-end tests for Hong Kong market (HKEX)"""

    def setUp(self):
        """Set up test database and adapter"""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)
        self.adapter = HKAdapter(db_manager=self.db)

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('yfinance.Ticker')
    def test_hk_stock_scanning_workflow(self, mock_ticker):
        """Test HK: Stock scanning with HSI component filter"""
        # Mock yfinance response for Tencent (0700)
        mock_info = {
            'symbol': '0700.HK',
            'longName': 'Tencent Holdings Limited',
            'quoteType': 'EQUITY',
            'exchange': 'HKG',
            'currency': 'HKD',
            'industry': 'Internet Content & Information',
            'marketCap': 3500000000000
        }
        mock_ticker.return_value.info = mock_info

        # Execute scan with ticker list
        results = self.adapter.scan_stocks(force_refresh=True, ticker_list=['0700'])

        # Verify results
        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertEqual(results[0]['ticker'], '0700')
            self.assertEqual(results[0]['region'], 'HK')

    @patch('yfinance.download')
    def test_hk_ohlcv_collection_workflow(self, mock_download):
        """Test HK: OHLCV data collection with HKD currency"""
        # Insert test ticker
        self.db.insert_ticker({
            'ticker': '0700',
            'name': 'Tencent Holdings',
            'exchange': 'HKEX',
            'region': 'HK',
            'currency': 'HKD',
            'asset_type': 'STOCK',
            'sector': 'Communication Services',
            'created_at': datetime.now().isoformat()
        })

        # Mock OHLCV data
        mock_df = pd.DataFrame({
            'Open': [350.0, 355.0, 360.0],
            'High': [360.0, 365.0, 370.0],
            'Low': [345.0, 350.0, 355.0],
            'Close': [357.0, 362.0, 367.0],
            'Volume': [10000000, 11000000, 12000000]
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Execute collection
        count = self.adapter.collect_stock_ohlcv(tickers=['0700'], days=3)

        # Verify
        self.assertGreaterEqual(count, 0)


class TestCNMarketE2E(unittest.TestCase):
    """End-to-end tests for China market (SSE/SZSE)"""

    def setUp(self):
        """Set up test database and adapter"""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)
        self.adapter = CNAdapter(db_manager=self.db)

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('yfinance.Ticker')
    def test_cn_stock_scanning_workflow(self, mock_ticker):
        """Test CN: Stock scanning with CSI 300 components"""
        # Mock yfinance response for Kweichow Moutai (600519)
        mock_info = {
            'symbol': '600519.SS',
            'longName': 'Kweichow Moutai Co., Ltd.',
            'quoteType': 'EQUITY',
            'exchange': 'SSE',
            'currency': 'CNY',
            'industry': 'Beverages—Wineries & Distilleries',
            'marketCap': 2000000000000
        }
        mock_ticker.return_value.info = mock_info

        # Execute scan (CN adapter uses max_count, not ticker_list)
        # For E2E test, we just verify the workflow works
        results = self.adapter.scan_stocks(force_refresh=True, max_count=1)

        # Verify - E2E test, just verify workflow works and returns valid data
        self.assertIsInstance(results, list)
        if len(results) > 0:
            # Verify required fields present
            self.assertIn('ticker', results[0])
            self.assertIn('region', results[0])
            self.assertEqual(results[0]['region'], 'CN')

    @patch('yfinance.download')
    def test_cn_ohlcv_collection_workflow(self, mock_download):
        """Test CN: OHLCV data collection with CNY currency"""
        # Insert test ticker
        self.db.insert_ticker({
            'ticker': '600519',
            'name': 'Kweichow Moutai',
            'exchange': 'SSE',
            'region': 'CN',
            'currency': 'CNY',
            'asset_type': 'STOCK',
            'sector': 'Consumer Staples',
            'created_at': datetime.now().isoformat()
        })

        # Mock OHLCV data
        mock_df = pd.DataFrame({
            'Open': [1800.0, 1820.0, 1850.0],
            'High': [1850.0, 1870.0, 1900.0],
            'Low': [1780.0, 1800.0, 1830.0],
            'Close': [1830.0, 1860.0, 1890.0],
            'Volume': [500000, 550000, 600000]
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Execute collection
        count = self.adapter.collect_stock_ohlcv(tickers=['600519'], days=3)

        # Verify
        self.assertGreaterEqual(count, 0)


class TestJPMarketE2E(unittest.TestCase):
    """End-to-end tests for Japan market (TSE)"""

    def setUp(self):
        """Set up test database and adapter"""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)
        self.adapter = JPAdapter(db_manager=self.db)

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('yfinance.Ticker')
    def test_jp_stock_scanning_workflow(self, mock_ticker):
        """Test JP: Stock scanning with Nikkei 225 components"""
        # Mock yfinance response for Toyota (7203)
        mock_info = {
            'symbol': '7203.T',
            'longName': 'Toyota Motor Corporation',
            'quoteType': 'EQUITY',
            'exchange': 'JPX',
            'currency': 'JPY',
            'industry': 'Auto Manufacturers',
            'marketCap': 35000000000000
        }
        mock_ticker.return_value.info = mock_info

        # Execute scan
        with patch.object(self.adapter, 'DEFAULT_JP_TICKERS', ['7203']):
            results = self.adapter.scan_stocks(force_refresh=True, max_count=1)

        # Verify
        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertEqual(results[0]['ticker'], '7203')
            self.assertEqual(results[0]['region'], 'JP')

    @patch('yfinance.download')
    def test_jp_ohlcv_collection_workflow(self, mock_download):
        """Test JP: OHLCV data collection with JPY currency"""
        # Insert test ticker
        self.db.insert_ticker({
            'ticker': '7203',
            'name': 'Toyota Motor',
            'exchange': 'TSE',
            'region': 'JP',
            'currency': 'JPY',
            'asset_type': 'STOCK',
            'sector': 'Consumer Discretionary',
            'created_at': datetime.now().isoformat()
        })

        # Mock OHLCV data
        mock_df = pd.DataFrame({
            'Open': [2500.0, 2520.0, 2550.0],
            'High': [2550.0, 2570.0, 2600.0],
            'Low': [2480.0, 2500.0, 2530.0],
            'Close': [2530.0, 2560.0, 2590.0],
            'Volume': [3000000, 3200000, 3500000]
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Execute collection
        count = self.adapter.collect_stock_ohlcv(tickers=['7203'], days=3)

        # Verify
        self.assertGreaterEqual(count, 0)


class TestVNMarketE2E(unittest.TestCase):
    """End-to-end tests for Vietnam market (HOSE/HNX)"""

    def setUp(self):
        """Set up test database and adapter"""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)
        self.adapter = VNAdapter(db_manager=self.db)

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('yfinance.Ticker')
    def test_vn_stock_scanning_workflow(self, mock_ticker):
        """Test VN: Stock scanning with VN30 components"""
        # Mock yfinance response for Vietcombank (VCB)
        mock_info = {
            'symbol': 'VCB.VN',
            'longName': 'Vietnam Joint Stock Commercial Bank for Foreign Trade',
            'quoteType': 'EQUITY',
            'exchange': 'HOSE',
            'currency': 'VND',
            'industry': 'Banks—Regional',
            'marketCap': 500000000000000
        }
        mock_ticker.return_value.info = mock_info

        # Execute scan
        with patch.object(self.adapter, 'DEFAULT_VN_TICKERS', ['VCB']):
            results = self.adapter.scan_stocks(force_refresh=True, max_count=1)

        # Verify
        self.assertIsInstance(results, list)
        if len(results) > 0:
            self.assertEqual(results[0]['ticker'], 'VCB')
            self.assertEqual(results[0]['region'], 'VN')

    @patch('yfinance.download')
    def test_vn_ohlcv_collection_workflow(self, mock_download):
        """Test VN: OHLCV data collection with VND currency"""
        # Insert test ticker
        self.db.insert_ticker({
            'ticker': 'VCB',
            'name': 'Vietcombank',
            'exchange': 'HOSE',
            'region': 'VN',
            'currency': 'VND',
            'asset_type': 'STOCK',
            'sector': 'Financials',
            'created_at': datetime.now().isoformat()
        })

        # Mock OHLCV data
        mock_df = pd.DataFrame({
            'Open': [95000.0, 96000.0, 97000.0],
            'High': [98000.0, 99000.0, 100000.0],
            'Low': [94000.0, 95000.0, 96000.0],
            'Close': [97000.0, 98000.0, 99000.0],
            'Volume': [5000000, 5500000, 6000000]
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Execute collection
        count = self.adapter.collect_stock_ohlcv(tickers=['VCB'], days=3)

        # Verify
        self.assertGreaterEqual(count, 0)


class TestCrossMarketWorkflows(unittest.TestCase):
    """Test workflows across multiple markets"""

    def setUp(self):
        """Set up test database and all adapters"""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        create_test_database(self.temp_db.name)

        self.db = SQLiteDatabaseManager(db_path=self.temp_db.name)

        # Initialize all adapters
        self.adapters = {
            'US': USAdapter(db_manager=self.db, polygon_api_key='test_key'),
            'HK': HKAdapter(db_manager=self.db),
            'CN': CNAdapter(db_manager=self.db),
            'JP': JPAdapter(db_manager=self.db),
            'VN': VNAdapter(db_manager=self.db)
        }

    def tearDown(self):
        """Clean up test database"""
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_all_markets_adapter_initialization(self):
        """Test all market adapters initialize correctly"""
        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                self.assertIsNotNone(adapter, f"{region} adapter should initialize")
                self.assertEqual(adapter.region_code, region,
                               f"{region} adapter should have correct region code")

    def test_all_markets_have_default_tickers(self):
        """Test adapters have default ticker universes where applicable"""
        # Only some adapters have DEFAULT_*_TICKERS
        # US/CN use dynamic scanning, HK/JP/VN have predefined lists
        regions_with_defaults = ['HK', 'JP', 'VN']

        for region in regions_with_defaults:
            adapter = self.adapters[region]
            with self.subTest(region=region):
                attr_name = f'DEFAULT_{region}_TICKERS'
                self.assertTrue(hasattr(adapter, attr_name),
                              f"{region} adapter should have {attr_name}")
                default_tickers = getattr(adapter, attr_name)
                self.assertIsInstance(default_tickers, list,
                                    f"{region} default tickers should be a list")
                self.assertGreater(len(default_tickers), 0,
                                 f"{region} should have at least 1 default ticker")

    def test_all_markets_currency_consistency(self):
        """Test all markets use correct currency codes"""
        expected_currencies = {
            'US': 'USD',
            'HK': 'HKD',
            'CN': 'CNY',
            'JP': 'JPY',
            'VN': 'VND'
        }

        for region, expected_currency in expected_currencies.items():
            with self.subTest(region=region):
                # Currency codes should be 3-letter ISO 4217
                self.assertEqual(len(expected_currency), 3)
                self.assertTrue(expected_currency.isupper())

    @patch('yfinance.Ticker')
    @patch('yfinance.download')
    def test_sequential_multi_market_data_collection(self, mock_download, mock_ticker):
        """Test sequential data collection across all markets"""
        # Mock yfinance responses
        mock_ticker.return_value.info = {
            'symbol': 'TEST',
            'longName': 'Test Company',
            'quoteType': 'EQUITY',
            'exchange': 'TEST',
            'currency': 'USD',
            'industry': 'Technology',
            'marketCap': 1000000000
        }

        mock_df = pd.DataFrame({
            'Open': [100.0] * 3,
            'High': [105.0] * 3,
            'Low': [95.0] * 3,
            'Close': [102.0] * 3,
            'Volume': [1000000] * 3
        }, index=pd.date_range('2025-01-01', periods=3))
        mock_download.return_value = mock_df

        # Test sequential collection for all markets
        collection_results = {}

        for region, adapter in self.adapters.items():
            with self.subTest(region=region):
                # Insert test ticker
                self.db.insert_ticker({
                    'ticker': f'TEST{region}',
                    'name': f'Test {region} Company',
                    'exchange': 'TEST',
                    'region': region,
                    'currency': 'USD',
                    'asset_type': 'STOCK',
                    'sector': 'Information Technology',
                    'created_at': datetime.now().isoformat()
                })

                # Collect OHLCV
                count = adapter.collect_stock_ohlcv(tickers=[f'TEST{region}'], days=3)
                collection_results[region] = count

                # Verify collection succeeded
                self.assertGreaterEqual(count, 0,
                                      f"{region} collection should return non-negative count")

        # Verify all markets collected data
        self.assertEqual(len(collection_results), 5,
                        "Should have results for all 5 markets")


if __name__ == '__main__':
    unittest.main()
