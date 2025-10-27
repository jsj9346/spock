"""
Unit Tests for Japan Market Adapter

Tests JPAdapter functionality including:
- Stock scanning with yfinance
- OHLCV data collection
- Fundamentals collection
- Ticker normalization
- Cache management
- REIT/preferred stock filtering

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.market_adapters.jp_adapter import JPAdapter
from modules.parsers.jp_stock_parser import JPStockParser


class TestJPAdapter(unittest.TestCase):
    """Test cases for JPAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.adapter = JPAdapter(self.db_mock)

    def tearDown(self):
        """Clean up after tests"""
        self.adapter = None

    # ========================================
    # TEST: Initialization
    # ========================================

    def test_initialization(self):
        """Test adapter initializes correctly"""
        self.assertEqual(self.adapter.region_code, 'JP')
        self.assertIsNotNone(self.adapter.yfinance_api)
        self.assertIsNotNone(self.adapter.stock_parser)

    # ========================================
    # TEST: Stock Scanning
    # ========================================

    def test_scan_stocks_with_cache(self):
        """Test scan_stocks uses cache when available"""
        # Mock cached tickers
        cached_tickers = [
            {'ticker': '7203', 'name': 'Toyota Motor', 'region': 'JP'},
            {'ticker': '6758', 'name': 'Sony Group', 'region': 'JP'}
        ]

        self.db_mock.get_last_update_time.return_value = datetime.now()
        self.db_mock.get_tickers.return_value = cached_tickers

        # Run scan
        result = self.adapter.scan_stocks(force_refresh=False)

        # Verify cache was used
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '7203')

    def test_scan_stocks_force_refresh(self):
        """Test scan_stocks with force_refresh ignores cache"""
        # Mock yfinance responses
        mock_info_7203 = {
            'symbol': '7203.T',
            'longName': 'Toyota Motor Corporation',
            'sector': 'Consumer Cyclical',
            'industry': 'Auto Manufacturers',
            'marketCap': 40000000000000,  # ~40 trillion JPY
            'currency': 'JPY',
            'exchange': 'JPX',
            'quoteType': 'EQUITY',
            'country': 'Japan'
        }

        mock_info_6758 = {
            'symbol': '6758.T',
            'longName': 'Sony Group Corporation',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
            'marketCap': 15000000000000,  # ~15 trillion JPY
            'currency': 'JPY',
            'exchange': 'JPX',
            'quoteType': 'EQUITY',
            'country': 'Japan'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(side_effect=[
            mock_info_7203,
            mock_info_6758
        ])

        # Run scan with custom ticker list
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['7203', '6758']
        )

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '7203')
        self.assertEqual(result[0]['name'], 'Toyota Motor Corporation')
        self.assertEqual(result[1]['ticker'], '6758')
        self.assertEqual(result[1]['currency'], 'JPY')

    def test_scan_stocks_filters_reits(self):
        """Test scan_stocks filters out REITs"""
        # Mock yfinance responses with REIT
        mock_info_stock = {
            'symbol': '7203.T',
            'longName': 'Toyota Motor Corporation',
            'sector': 'Consumer Cyclical',
            'industry': 'Auto Manufacturers',
            'marketCap': 40000000000000,
            'currency': 'JPY',
            'exchange': 'JPX',
            'quoteType': 'EQUITY'
        }

        mock_info_reit = {
            'symbol': '3269.T',
            'longName': 'Advance Residence Investment',
            'sector': 'Real Estate',
            'industry': 'REIT—Residential',  # REIT should be filtered
            'marketCap': 500000000000,
            'currency': 'JPY',
            'exchange': 'JPX',
            'quoteType': 'EQUITY'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(side_effect=[
            mock_info_stock,
            mock_info_reit
        ])

        # Run scan
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['7203', '3269']
        )

        # Verify REIT was filtered out
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticker'], '7203')

    def test_scan_stocks_api_error(self):
        """Test scan_stocks handles API errors gracefully"""
        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=None)

        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['7203']
        )

        # Should return empty list when API fails
        self.assertEqual(len(result), 0)

    # ========================================
    # TEST: OHLCV Collection
    # ========================================

    def test_collect_stock_ohlcv(self):
        """Test OHLCV data collection"""
        # Mock database tickers
        self.db_mock.get_tickers.return_value = [
            {'ticker': '7203', 'name': 'Toyota', 'region': 'JP'}
        ]

        # Mock yfinance OHLCV data
        mock_ohlcv = pd.DataFrame({
            'Date': pd.date_range('2025-01-01', periods=5, freq='D'),
            'Open': [3000, 3050, 3025, 3000, 2975],
            'High': [3100, 3075, 3050, 3025, 3000],
            'Low': [2950, 3000, 2975, 2950, 2925],
            'Close': [3050, 3025, 3000, 2975, 2950],
            'Volume': [1000000, 1100000, 1050000, 1200000, 1150000]
        }).set_index('Date')

        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=mock_ohlcv)
        self.db_mock.insert_ohlcv_data = Mock()

        # Run collection
        count = self.adapter.collect_stock_ohlcv(days=250)

        # Verify success
        self.assertEqual(count, 1)
        self.db_mock.insert_ohlcv_data.assert_called()

    def test_collect_stock_ohlcv_empty_data(self):
        """Test OHLCV collection handles empty data"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '7203', 'name': 'Toyota', 'region': 'JP'}
        ]

        self.adapter.yfinance_api.get_ohlcv = Mock(return_value=pd.DataFrame())

        count = self.adapter.collect_stock_ohlcv(days=250)

        # Should return 0 for empty data
        self.assertEqual(count, 0)

    # ========================================
    # TEST: Fundamentals Collection
    # ========================================

    def test_collect_fundamentals(self):
        """Test fundamentals collection"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '7203', 'name': 'Toyota', 'region': 'JP'}
        ]

        mock_info = {
            'symbol': '7203.T',
            'longName': 'Toyota Motor Corporation',
            'marketCap': 40000000000000,
            'trailingPE': 12.5,
            'priceToBook': 1.2,
            'dividendYield': 0.028,
            'trailingEps': 250.0,
            'returnOnEquity': 0.105,
            'currentPrice': 3000.0,
            'currency': 'JPY'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.insert_ticker_fundamentals = Mock()

        count = self.adapter.collect_fundamentals()

        self.assertEqual(count, 1)
        self.db_mock.insert_ticker_fundamentals.assert_called_once()

    def test_collect_fundamentals_missing_data(self):
        """Test fundamentals collection handles missing data"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': '7203', 'name': 'Toyota', 'region': 'JP'}
        ]

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=None)

        count = self.adapter.collect_fundamentals()

        # Should return 0 when no data
        self.assertEqual(count, 0)

    # ========================================
    # TEST: JPStockParser
    # ========================================

    def test_parser_normalize_ticker(self):
        """Test ticker normalization"""
        parser = JPStockParser()

        # Test various formats
        self.assertEqual(parser.normalize_ticker('7203.T'), '7203')
        self.assertEqual(parser.normalize_ticker('7203'), '7203')
        self.assertEqual(parser.normalize_ticker('6758.T'), '6758')

        # Test invalid formats
        self.assertIsNone(parser.normalize_ticker('999.T'))  # Too short
        self.assertIsNone(parser.normalize_ticker('12345.T'))  # Too long
        self.assertIsNone(parser.normalize_ticker('ABCD.T'))  # Not numeric

    def test_parser_denormalize_ticker(self):
        """Test ticker denormalization"""
        parser = JPStockParser()

        self.assertEqual(parser.denormalize_ticker('7203'), '7203.T')
        self.assertEqual(parser.denormalize_ticker('6758'), '6758.T')

    def test_parser_map_industry_to_gics(self):
        """Test industry to GICS sector mapping"""
        parser = JPStockParser()

        # Test direct mappings
        self.assertEqual(parser._map_industry_to_gics('Auto Manufacturers'), 'Consumer Discretionary')
        self.assertEqual(parser._map_industry_to_gics('Banks—Regional'), 'Financials')
        self.assertEqual(parser._map_industry_to_gics('Drug Manufacturers—General'), 'Health Care')

        # Test fuzzy matching
        self.assertEqual(parser._map_industry_to_gics('Some Tech Company'), 'Information Technology')
        self.assertEqual(parser._map_industry_to_gics('Financial Services'), 'Financials')

        # Test default fallback
        self.assertEqual(parser._map_industry_to_gics('Unknown Industry'), 'Industrials')

    def test_parser_ticker_format_validation(self):
        """Test ticker format validation"""
        parser = JPStockParser()

        # Valid 4-digit codes
        self.assertEqual(parser.normalize_ticker('7203.T'), '7203')
        self.assertEqual(parser.normalize_ticker('0001.T'), '0001')
        self.assertEqual(parser.normalize_ticker('9999.T'), '9999')

        # Invalid codes
        self.assertIsNone(parser.normalize_ticker('123.T'))    # 3 digits
        self.assertIsNone(parser.normalize_ticker('12345.T'))  # 5 digits
        self.assertIsNone(parser.normalize_ticker('7A03.T'))   # Contains letter
        self.assertIsNone(parser.normalize_ticker(''))         # Empty

    # ========================================
    # TEST: Utilities
    # ========================================

    def test_add_custom_ticker(self):
        """Test adding custom ticker"""
        mock_info = {
            'symbol': '7203.T',
            'longName': 'Toyota Motor Corporation',
            'sector': 'Consumer Cyclical',
            'industry': 'Auto Manufacturers',
            'marketCap': 40000000000000,
            'currency': 'JPY',
            'exchange': 'JPX',
            'quoteType': 'EQUITY'
        }

        self.adapter.yfinance_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.insert_ticker = Mock()
        self.db_mock.insert_stock_details = Mock()
        self.db_mock.delete_tickers = Mock()

        result = self.adapter.add_custom_ticker('7203')

        self.assertTrue(result)

    def test_scan_etfs_not_implemented(self):
        """Test ETF scanning returns empty list"""
        result = self.adapter.scan_etfs()
        self.assertEqual(result, [])

    def test_collect_etf_ohlcv_not_implemented(self):
        """Test ETF OHLCV collection returns 0"""
        count = self.adapter.collect_etf_ohlcv()
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()
