"""
Unit Tests for Hong Kong Market Adapter

Tests HKAdapter functionality including:
- Stock scanning with yfinance
- OHLCV data collection
- Fundamentals collection
- Ticker normalization
- Cache management

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.market_adapters.hk_adapter import HKAdapter
from modules.parsers.hk_stock_parser import HKStockParser


class TestHKAdapter(unittest.TestCase):
    """Test cases for HKAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.adapter = HKAdapter(self.db_mock)

    def tearDown(self):
        """Clean up after tests"""
        self.adapter = None

    # ========================================
    # TEST: Initialization
    # ========================================

    def test_initialization(self):
        """Test adapter initializes correctly"""
        self.assertEqual(self.adapter.region_code, 'HK')
        self.assertIsNotNone(self.adapter.yfinance_api)
        self.assertIsNotNone(self.adapter.stock_parser)

    # ========================================
    # TEST: Stock Scanning
    # ========================================

    def test_scan_stocks_with_cache(self):
        """Test scan_stocks uses cache when available"""
        # Mock cached tickers
        cached_tickers = [
            {'ticker': '0700', 'name': 'Tencent', 'region': 'HK'},
            {'ticker': '0941', 'name': 'China Mobile', 'region': 'HK'}
        ]

        self.db_mock.get_last_update_time.return_value = datetime.now()
        self.db_mock.get_tickers.return_value = cached_tickers

        # Run scan
        result = self.adapter.scan_stocks(force_refresh=False)

        # Verify cache was used
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '0700')

    def test_scan_stocks_force_refresh(self):
        """Test scan_stocks with force_refresh ignores cache"""
        # Mock yfinance responses
        mock_info_0700 = {
            'symbol': '0700.HK',
            'longName': 'Tencent Holdings Limited',
            'sector': 'Communication Services',
            'industry': 'Internet Content & Information',
            'marketCap': 3500000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'EQUITY',
            'country': 'Hong Kong'
        }

        mock_info_0941 = {
            'symbol': '0941.HK',
            'longName': 'China Mobile Limited',
            'sector': 'Communication Services',
            'industry': 'Telecom Services',
            'marketCap': 1800000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'EQUITY',
            'country': 'Hong Kong'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(side_effect=[
            mock_info_0700,
            mock_info_0941
        ])

        # Run scan with small ticker list
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['0700', '0941']
        )

        # Verify data was fetched
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '0700')
        self.assertEqual(result[0]['name'], 'Tencent Holdings Limited')
        self.assertEqual(result[1]['ticker'], '0941')

    def test_scan_stocks_filters_common_stocks(self):
        """Test scan_stocks filters out non-equity types"""
        # Mock responses with mixed asset types
        mock_equity = {
            'symbol': '0700.HK',
            'longName': 'Tencent',
            'sector': 'Communication Services',
            'industry': 'Internet Content & Information',
            'marketCap': 3500000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'EQUITY'
        }

        mock_etf = {
            'symbol': '2800.HK',
            'longName': 'Tracker Fund of Hong Kong',
            'sector': None,
            'industry': None,
            'marketCap': 50000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'ETF'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(side_effect=[
            mock_equity,
            mock_etf
        ])

        # Run scan
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['0700', '2800']
        )

        # Verify only EQUITY type remains
        self.assertGreater(len(result), 0)
        etf_count = len([s for s in result if s.get('quote_type') == 'ETF'])
        self.assertEqual(etf_count, 0)

    def test_scan_stocks_handles_api_errors(self):
        """Test scan_stocks handles API errors gracefully"""
        # Mock API error
        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=None)

        # Run scan (should not crash)
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['0700']
        )

        # Verify empty result but no crash
        self.assertEqual(len(result), 0)

    # ========================================
    # TEST: OHLCV Collection
    # ========================================

    def test_collect_stock_ohlcv(self):
        """Test OHLCV collection for stocks"""
        # Mock database tickers
        self.db_mock.get_tickers.return_value = [
            {'ticker': '0700', 'region': 'HK', 'asset_type': 'STOCK'}
        ]

        # Mock yfinance OHLCV response
        mock_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=250),
            'open': [400] * 250,
            'high': [410] * 250,
            'low': [395] * 250,
            'close': [405] * 250,
            'volume': [10000000] * 250
        })

        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=mock_ohlcv)
        self.db_mock.insert_ohlcv_bulk = Mock()

        # Run collection
        count = self.adapter.collect_stock_ohlcv(days=250)

        # Verify success
        self.assertEqual(count, 1)
        self.db_mock.insert_ohlcv_bulk.assert_called_once()

    def test_collect_stock_ohlcv_handles_empty_data(self):
        """Test OHLCV collection handles empty responses"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '0700', 'region': 'HK', 'asset_type': 'STOCK'}
        ]

        # Mock empty response
        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=None)

        # Run collection (should not crash)
        count = self.adapter.collect_stock_ohlcv(days=250)

        # Verify 0 success count
        self.assertEqual(count, 0)

    # ========================================
    # TEST: Fundamentals Collection
    # ========================================

    def test_collect_fundamentals(self):
        """Test fundamentals collection"""
        # Mock database tickers
        self.db_mock.get_tickers.return_value = [
            {'ticker': '0700', 'region': 'HK', 'asset_type': 'STOCK'}
        ]

        # Mock yfinance info
        mock_info = {
            'symbol': '0700.HK',
            'longName': 'Tencent',
            'market_cap': 3500000000000,
            'currency': 'HKD',
            'exchange': 'HKG'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.insert_ticker_fundamentals = Mock()

        # Run collection
        count = self.adapter.collect_fundamentals()

        # Verify success
        self.assertEqual(count, 1)
        self.db_mock.insert_ticker_fundamentals.assert_called_once()

    def test_collect_fundamentals_handles_missing_data(self):
        """Test fundamentals collection with missing market cap"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '0700', 'region': 'HK', 'asset_type': 'STOCK'}
        ]

        # Mock info without market_cap
        mock_info = {
            'symbol': '0700.HK',
            'longName': 'Tencent',
            'currency': 'HKD',
            'market_cap': None  # No market cap
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_info)

        # Run collection
        count = self.adapter.collect_fundamentals()

        # Verify 0 inserts (no market cap to save)
        self.assertEqual(count, 0)

    # ========================================
    # TEST: Custom Ticker Management
    # ========================================

    def test_add_custom_tickers(self):
        """Test adding custom tickers"""
        # Mock yfinance response
        mock_info = {
            'symbol': '1810.HK',
            'longName': 'Xiaomi Corporation',
            'sector': 'Consumer Electronics',
            'industry': 'Consumer Electronics',
            'marketCap': 500000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'EQUITY'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_info)

        # Add custom ticker
        count = self.adapter.add_custom_tickers(['1810'])

        # Verify success
        self.assertEqual(count, 1)

    # ========================================
    # TEST: ETF Methods (Not Implemented)
    # ========================================

    def test_scan_etfs_not_implemented(self):
        """Test scan_etfs returns empty list"""
        result = self.adapter.scan_etfs()
        self.assertEqual(len(result), 0)

    def test_collect_etf_ohlcv_not_implemented(self):
        """Test collect_etf_ohlcv returns 0"""
        count = self.adapter.collect_etf_ohlcv()
        self.assertEqual(count, 0)


class TestHKStockParser(unittest.TestCase):
    """Test cases for HKStockParser"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = HKStockParser()

    def test_normalize_ticker(self):
        """Test ticker normalization"""
        self.assertEqual(self.parser.normalize_ticker('0700.HK'), '0700')
        self.assertEqual(self.parser.normalize_ticker('0700'), '0700')
        self.assertIsNone(self.parser.normalize_ticker('INVALID'))

    def test_denormalize_ticker(self):
        """Test ticker denormalization"""
        self.assertEqual(self.parser.denormalize_ticker('0700'), '0700.HK')
        self.assertEqual(self.parser.denormalize_ticker('0700.HK'), '0700.HK')

    def test_validate_ticker_format(self):
        """Test ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('0700'))
        self.assertTrue(self.parser.validate_ticker_format('9988'))
        self.assertTrue(self.parser.validate_ticker_format('0700.HK', require_suffix=True))
        self.assertFalse(self.parser.validate_ticker_format('ABC'))
        self.assertFalse(self.parser.validate_ticker_format('0700', require_suffix=True))


if __name__ == '__main__':
    unittest.main()
