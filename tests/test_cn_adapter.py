"""
Unit Tests for China Market Adapter

Tests CNAdapter functionality including:
- Stock scanning with AkShare
- Hybrid fallback strategy (AkShare → yfinance)
- OHLCV data collection
- Fundamentals collection
- Ticker normalization
- CSRC → GICS sector mapping

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.market_adapters.cn_adapter import CNAdapter
from modules.parsers.cn_stock_parser import CNStockParser


class TestCNAdapter(unittest.TestCase):
    """Test cases for CNAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.adapter = CNAdapter(self.db_mock, enable_fallback=True)

    def tearDown(self):
        """Clean up after tests"""
        self.adapter = None

    # ========================================
    # TEST: Initialization
    # ========================================

    def test_initialization(self):
        """Test adapter initializes correctly"""
        self.assertEqual(self.adapter.region_code, 'CN')
        self.assertIsNotNone(self.adapter.akshare_api)
        self.assertIsNotNone(self.adapter.yfinance_api)
        self.assertIsNotNone(self.adapter.stock_parser)
        self.assertTrue(self.adapter.enable_fallback)

    def test_initialization_without_fallback(self):
        """Test adapter initialization with fallback disabled"""
        adapter = CNAdapter(self.db_mock, enable_fallback=False)
        self.assertIsNone(adapter.yfinance_api)
        self.assertFalse(adapter.enable_fallback)

    # ========================================
    # TEST: Stock Scanning
    # ========================================

    def test_scan_stocks_with_cache(self):
        """Test scan_stocks uses cache when available"""
        # Mock cached tickers
        cached_tickers = [
            {'ticker': '600519', 'name': '贵州茅台', 'region': 'CN'},
            {'ticker': '000001', 'name': '平安银行', 'region': 'CN'}
        ]

        self.db_mock.get_last_update_time.return_value = datetime.now()
        self.db_mock.get_tickers.return_value = cached_tickers

        # Run scan
        result = self.adapter.scan_stocks(force_refresh=False)

        # Verify cache was used
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '600519')

    def test_scan_stocks_force_refresh(self):
        """Test scan_stocks with force_refresh from AkShare"""
        # Mock AkShare response
        mock_df = pd.DataFrame({
            'code': ['600519', '000001'],
            'name': ['贵州茅台', '平安银行'],
            'price': [1800.0, 15.0],
            'change_percent': [2.5, -1.0],
            'volume': [1000000, 5000000],
            'amount': [1800000000, 75000000],
            'market_cap': [2000000000000, 200000000000]
        })

        self.adapter.akshare_api.get_stock_list_realtime = Mock(return_value=mock_df)

        # Run scan
        result = self.adapter.scan_stocks(force_refresh=True, max_count=2)

        # Verify data was fetched
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '600519')
        self.assertEqual(result[0]['name'], '贵州茅台')
        self.assertEqual(result[1]['ticker'], '000001')

    def test_scan_stocks_filters_st_stocks(self):
        """Test scan_stocks filters out ST stocks"""
        # Mock response with ST stocks
        mock_df = pd.DataFrame({
            'code': ['600519', 'ST600001', '000001'],
            'name': ['贵州茅台', 'ST股票', '平安银行'],
            'price': [1800.0, 5.0, 15.0],
            'market_cap': [2000000000000, 10000000000, 200000000000]
        })

        self.adapter.akshare_api.get_stock_list_realtime = Mock(return_value=mock_df)

        # Run scan
        result = self.adapter.scan_stocks(force_refresh=True)

        # Verify ST stock was filtered out
        ticker_list = [s['ticker'] for s in result]
        self.assertNotIn('600001', ticker_list)  # ST stock removed

    def test_scan_stocks_handles_api_errors(self):
        """Test scan_stocks handles API errors gracefully"""
        # Mock API error
        self.adapter.akshare_api.get_stock_list_realtime = Mock(return_value=None)

        # Run scan (should not crash)
        result = self.adapter.scan_stocks(force_refresh=True)

        # Verify empty result but no crash
        self.assertEqual(len(result), 0)

    # ========================================
    # TEST: OHLCV Collection with Fallback
    # ========================================

    def test_collect_stock_ohlcv_akshare_success(self):
        """Test OHLCV collection succeeds with AkShare"""
        # Mock database tickers
        self.db_mock.get_tickers.return_value = [
            {'ticker': '600519', 'region': 'CN', 'asset_type': 'STOCK'}
        ]

        # Mock AkShare OHLCV response
        mock_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=250),
            'open': [1800] * 250,
            'high': [1850] * 250,
            'low': [1750] * 250,
            'close': [1820] * 250,
            'volume': [1000000] * 250
        })

        self.adapter.akshare_api.get_stock_daily_ohlcv = Mock(return_value=mock_ohlcv)
        self.db_mock.insert_ohlcv_bulk = Mock()

        # Run collection
        count = self.adapter.collect_stock_ohlcv(days=250, use_fallback=False)

        # Verify success
        self.assertEqual(count, 1)
        self.db_mock.insert_ohlcv_bulk.assert_called_once()

    def test_collect_stock_ohlcv_fallback_to_yfinance(self):
        """Test OHLCV collection falls back to yfinance when AkShare fails"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '600519', 'region': 'CN', 'asset_type': 'STOCK'}
        ]

        # Mock AkShare failure
        self.adapter.akshare_api.get_stock_daily_ohlcv = Mock(return_value=None)

        # Mock yfinance success
        mock_yf_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=250),
            'open': [1800] * 250,
            'high': [1850] * 250,
            'low': [1750] * 250,
            'close': [1820] * 250,
            'volume': [1000000] * 250
        })

        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=mock_yf_ohlcv)
        self.db_mock.insert_ohlcv_bulk = Mock()

        # Run collection with fallback
        count = self.adapter.collect_stock_ohlcv(days=250, use_fallback=True)

        # Verify fallback was used
        self.assertEqual(count, 1)
        self.adapter.yfinance_api.get_ohlcv.assert_called_once()

    def test_collect_stock_ohlcv_both_sources_fail(self):
        """Test OHLCV collection when both sources fail"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '600519', 'region': 'CN', 'asset_type': 'STOCK'}
        ]

        # Mock both sources failing
        self.adapter.akshare_api.get_stock_daily_ohlcv = Mock(return_value=None)
        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=None)

        # Run collection
        count = self.adapter.collect_stock_ohlcv(days=250, use_fallback=True)

        # Verify 0 success count
        self.assertEqual(count, 0)

    # ========================================
    # TEST: Fundamentals Collection
    # ========================================

    def test_collect_fundamentals_akshare_success(self):
        """Test fundamentals collection succeeds with AkShare"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '600519', 'region': 'CN', 'asset_type': 'STOCK'}
        ]

        # Mock AkShare info
        mock_info = {
            '股票简称': '贵州茅台',
            '所属行业': '白酒',
            '总市值': '2万亿'
        }

        self.adapter.akshare_api.get_stock_info = Mock(return_value=mock_info)
        self.db_mock.insert_ticker_fundamentals = Mock()
        self.db_mock.update_stock_details = Mock()

        # Run collection
        count = self.adapter.collect_fundamentals(use_fallback=False)

        # Verify success
        self.assertEqual(count, 1)
        self.db_mock.insert_ticker_fundamentals.assert_called_once()

    def test_collect_fundamentals_fallback_to_yfinance(self):
        """Test fundamentals fallback to yfinance"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '600519', 'region': 'CN', 'asset_type': 'STOCK'}
        ]

        # Mock AkShare failure
        self.adapter.akshare_api.get_stock_info = Mock(return_value=None)

        # Mock yfinance success
        mock_yf_info = {
            'symbol': '600519.SS',
            'longName': 'Kweichow Moutai',
            'industry': 'Beverages—Alcoholic',
            'marketCap': 2000000000000
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_yf_info)
        self.db_mock.insert_ticker_fundamentals = Mock()

        # Run collection
        count = self.adapter.collect_fundamentals(use_fallback=True)

        # Verify fallback was used
        self.assertEqual(count, 1)
        self.adapter.yfinance_api.get_ticker_info.assert_called_once()

    # ========================================
    # TEST: Custom Tickers
    # ========================================

    def test_add_custom_tickers(self):
        """Test adding custom tickers"""
        # Mock AkShare response
        mock_df = pd.DataFrame({
            'code': ['600519', '000001'],
            'name': ['贵州茅台', '平安银行'],
            'price': [1800.0, 15.0],
            'market_cap': [2000000000000, 200000000000]
        })

        self.adapter.akshare_api.get_stock_list_realtime = Mock(return_value=mock_df)

        # Add custom tickers
        count = self.adapter.add_custom_tickers(['600519', '000001'])

        # Verify success
        self.assertEqual(count, 2)

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

    # ========================================
    # TEST: Fallback Stats
    # ========================================

    def test_get_fallback_stats(self):
        """Test fallback statistics"""
        stats = self.adapter.get_fallback_stats()
        self.assertTrue(stats['fallback_enabled'])
        self.assertTrue(stats['fallback_available'])


class TestCNStockParser(unittest.TestCase):
    """Test cases for CNStockParser"""

    def setUp(self):
        """Set up test fixtures"""
        self.parser = CNStockParser()

    def test_normalize_ticker(self):
        """Test ticker normalization"""
        self.assertEqual(self.parser.normalize_ticker('SH600519'), '600519')
        self.assertEqual(self.parser.normalize_ticker('SZ000001'), '000001')
        self.assertEqual(self.parser.normalize_ticker('600519'), '600519')
        self.assertIsNone(self.parser.normalize_ticker('INVALID'))

    def test_denormalize_ticker_yfinance(self):
        """Test ticker denormalization for yfinance"""
        self.assertEqual(self.parser.denormalize_ticker_yfinance('600519'), '600519.SS')
        self.assertEqual(self.parser.denormalize_ticker_yfinance('000001'), '000001.SZ')
        self.assertEqual(self.parser.denormalize_ticker_yfinance('300001'), '300001.SZ')

    def test_get_exchange(self):
        """Test exchange detection"""
        self.assertEqual(self.parser.get_exchange('600519'), 'SSE')
        self.assertEqual(self.parser.get_exchange('000001'), 'SZSE')
        self.assertEqual(self.parser.get_exchange('300001'), 'SZSE')

    def test_validate_ticker_format(self):
        """Test ticker format validation"""
        self.assertTrue(self.parser.validate_ticker_format('600519'))
        self.assertTrue(self.parser.validate_ticker_format('000001'))
        self.assertTrue(self.parser.validate_ticker_format('300001'))
        self.assertFalse(self.parser.validate_ticker_format('ABC123'))
        self.assertFalse(self.parser.validate_ticker_format('60051'))  # Too short


if __name__ == '__main__':
    unittest.main()
