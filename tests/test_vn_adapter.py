"""
Unit Tests for Vietnam Market Adapter

Tests VNAdapter functionality including:
- Stock scanning with yfinance (VN30 index)
- OHLCV data collection
- Fundamentals collection
- Ticker normalization (.VN suffix)
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

from modules.market_adapters.vn_adapter import VNAdapter
from modules.parsers.vn_stock_parser import VNStockParser


class TestVNAdapter(unittest.TestCase):
    """Test cases for VNAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.adapter = VNAdapter(self.db_mock)

    def tearDown(self):
        """Clean up after tests"""
        self.adapter = None

    # ========================================
    # TEST: Initialization
    # ========================================

    def test_initialization(self):
        """Test adapter initializes correctly"""
        self.assertEqual(self.adapter.region_code, 'VN')
        self.assertIsNotNone(self.adapter.yf_api)
        self.assertIsNotNone(self.adapter.parser)
        self.assertIsInstance(self.adapter.parser, VNStockParser)
        self.assertEqual(len(self.adapter.default_tickers), 30)  # VN30 index

    # ========================================
    # TEST: Stock Scanning
    # ========================================

    def test_scan_stocks_force_refresh(self):
        """Test scan_stocks with force_refresh fetches fresh data"""
        # Mock yfinance responses for Vietnamese stocks
        mock_info_vcb = {
            'symbol': 'VCB.VN',
            'longName': 'Joint Stock Commercial Bank for Foreign Trade of Vietnam',
            'shortName': 'Vietcombank',
            'sector': 'Financial Services',
            'industry': 'Banks—Regional',
            'marketCap': 500000000000000,  # ~500 trillion VND
            'currency': 'VND',
            'exchange': 'HCM',  # yfinance might return HCM for HOSE
            'quoteType': 'EQUITY',
            'country': 'Vietnam',
            'currentPrice': 90000
        }

        mock_info_fpt = {
            'symbol': 'FPT.VN',
            'longName': 'FPT Corporation',
            'shortName': 'FPT Corp',
            'sector': 'Technology',
            'industry': 'Information Technology Services',
            'marketCap': 150000000000000,  # ~150 trillion VND
            'currency': 'VND',
            'exchange': 'HCM',
            'quoteType': 'EQUITY',
            'country': 'Vietnam',
            'currentPrice': 125000
        }

        self.adapter.yf_api.get_ticker_info = Mock(side_effect=[
            mock_info_vcb,
            mock_info_fpt
        ])

        # Mock database save
        self.db_mock.save_ticker = Mock()

        # Run scan with limited tickers
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['VCB', 'FPT']
        )

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], 'VCB')
        self.assertEqual(result[0]['region'], 'VN')
        self.assertEqual(result[0]['currency'], 'VND')
        self.assertEqual(result[1]['ticker'], 'FPT')

        # Verify database was called
        self.assertEqual(self.db_mock.save_ticker.call_count, 2)

    def test_scan_stocks_filters_reits(self):
        """Test scan_stocks filters out REITs"""
        # Mock REIT response
        mock_reit = {
            'symbol': 'VREIT.VN',
            'longName': 'Vietnam REIT Fund',
            'sector': 'Real Estate',
            'industry': 'REIT—Diversified',
            'marketCap': 50000000000000,
            'currency': 'VND',
            'exchange': 'HCM',
            'quoteType': 'EQUITY'
        }

        # Mock normal stock
        mock_vcb = {
            'symbol': 'VCB.VN',
            'longName': 'Vietcombank',
            'sector': 'Financial Services',
            'industry': 'Banks—Regional',
            'marketCap': 500000000000000,
            'currency': 'VND',
            'exchange': 'HCM',
            'quoteType': 'EQUITY'
        }

        self.adapter.yf_api.get_ticker_info = Mock(side_effect=[
            mock_reit,
            mock_vcb
        ])

        self.db_mock.save_ticker = Mock()

        # Run scan
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['VREIT', 'VCB']
        )

        # Verify REIT was filtered
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticker'], 'VCB')

    def test_scan_stocks_api_error(self):
        """Test scan_stocks handles API errors gracefully"""
        # Mock API error
        self.adapter.yf_api.get_ticker_info = Mock(side_effect=Exception("API Error"))

        # Run scan
        result = self.adapter.scan_stocks(
            force_refresh=True,
            ticker_list=['VCB']
        )

        # Verify empty result on error
        self.assertEqual(len(result), 0)

    def test_scan_stocks_max_count(self):
        """Test scan_stocks respects max_count parameter"""
        # Mock successful responses
        mock_info = {
            'symbol': 'VCB.VN',
            'longName': 'Vietcombank',
            'sector': 'Financial Services',
            'industry': 'Banks—Regional',
            'marketCap': 500000000000000,
            'currency': 'VND',
            'exchange': 'HCM'
        }

        self.adapter.yf_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.save_ticker = Mock()

        # Run scan with max_count
        result = self.adapter.scan_stocks(
            force_refresh=True,
            max_count=5
        )

        # Verify max_count was respected
        self.assertLessEqual(len(result), 5)

    # ========================================
    # TEST: OHLCV Collection
    # ========================================

    def test_collect_stock_ohlcv(self):
        """Test collect_stock_ohlcv fetches and saves data"""
        # Mock database tickers
        self.db_mock.get_tickers.return_value = [
            {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN'}
        ]

        # Mock yfinance history data
        mock_history = pd.DataFrame({
            'Date': pd.date_range(start='2025-01-01', periods=30),
            'Open': [90000] * 30,
            'High': [91000] * 30,
            'Low': [89000] * 30,
            'Close': [90500] * 30,
            'Volume': [1000000] * 30
        })
        mock_history.set_index('Date', inplace=True)

        self.adapter.yf_api.get_ohlcv_data = Mock(return_value=mock_history)
        self.db_mock.save_ohlcv_data = Mock()

        # Run collection
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=['VCB'],
            days=30
        )

        # Verify success
        self.assertEqual(success_count, 1)
        self.adapter.yf_api.get_ohlcv_data.assert_called_once()
        self.db_mock.save_ohlcv_data.assert_called_once()

    def test_collect_stock_ohlcv_empty_data(self):
        """Test collect_stock_ohlcv handles empty data"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN'}
        ]

        # Mock empty history
        self.adapter.yf_api.get_ohlcv_data = Mock(return_value=None)

        # Run collection
        success_count = self.adapter.collect_stock_ohlcv(
            tickers=['VCB'],
            days=30
        )

        # Verify no success
        self.assertEqual(success_count, 0)

    # ========================================
    # TEST: Fundamentals Collection
    # ========================================

    def test_collect_fundamentals(self):
        """Test collect_fundamentals fetches and saves data"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN'}
        ]

        # Mock yfinance info with fundamentals
        mock_info = {
            'symbol': 'VCB.VN',
            'marketCap': 500000000000000,
            'trailingPE': 15.5,
            'priceToBook': 3.2,
            'dividendYield': 0.025,
            'trailingEps': 5800,
            'returnOnEquity': 0.22,
            'currentPrice': 90000
        }

        self.adapter.yf_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.save_fundamentals = Mock()

        # Run collection
        success_count = self.adapter.collect_fundamentals(tickers=['VCB'])

        # Verify success
        self.assertEqual(success_count, 1)
        self.adapter.yf_api.get_ticker_info.assert_called_once()
        self.db_mock.save_fundamentals.assert_called_once()

    def test_collect_fundamentals_missing_data(self):
        """Test collect_fundamentals handles missing data"""
        self.db_mock.get_tickers.return_value = [
            {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN'}
        ]

        # Mock None response
        self.adapter.yf_api.get_ticker_info = Mock(return_value=None)

        # Run collection
        success_count = self.adapter.collect_fundamentals(tickers=['VCB'])

        # Verify no success
        self.assertEqual(success_count, 0)

    # ========================================
    # TEST: Parser Functionality
    # ========================================

    def test_parser_normalize_ticker(self):
        """Test ticker normalization: VCB.VN → VCB"""
        parser = VNStockParser()

        # Test normal case
        self.assertEqual(parser.normalize_ticker('VCB.VN'), 'VCB')
        self.assertEqual(parser.normalize_ticker('vcb.vn'), 'VCB')
        self.assertEqual(parser.normalize_ticker('FPT.VN'), 'FPT')

        # Test invalid cases
        self.assertIsNone(parser.normalize_ticker('ABCD.VN'))  # 4 letters
        self.assertIsNone(parser.normalize_ticker('AB.VN'))    # 2 letters
        self.assertIsNone(parser.normalize_ticker(''))
        self.assertIsNone(parser.normalize_ticker(None))

    def test_parser_denormalize_ticker(self):
        """Test ticker denormalization: VCB → VCB.VN"""
        parser = VNStockParser()

        # Test normal case
        self.assertEqual(parser.denormalize_ticker('VCB'), 'VCB.VN')
        self.assertEqual(parser.denormalize_ticker('FPT'), 'FPT.VN')
        self.assertEqual(parser.denormalize_ticker('HPG'), 'HPG.VN')

        # Test empty case
        self.assertEqual(parser.denormalize_ticker(''), '')

    def test_parser_map_industry_to_gics(self):
        """Test industry → GICS sector mapping"""
        parser = VNStockParser()

        # Test direct mappings
        self.assertEqual(parser._map_industry_to_gics('Banks—Regional'), 'Financials')
        self.assertEqual(parser._map_industry_to_gics('Information Technology Services'), 'Information Technology')
        self.assertEqual(parser._map_industry_to_gics('Real Estate—Development'), 'Real Estate')

        # Test fuzzy keyword matching
        self.assertEqual(parser._map_industry_to_gics('Banking Services'), 'Financials')
        self.assertEqual(parser._map_industry_to_gics('Technology Consulting'), 'Information Technology')

        # Test default fallback
        self.assertEqual(parser._map_industry_to_gics('Unknown Industry'), 'Industrials')
        self.assertEqual(parser._map_industry_to_gics(''), 'Industrials')
        self.assertEqual(parser._map_industry_to_gics(None), 'Industrials')

    def test_parser_ticker_format_validation(self):
        """Test Vietnamese ticker format validation"""
        parser = VNStockParser()

        # Valid 3-letter formats
        self.assertEqual(parser.normalize_ticker('VCB.VN'), 'VCB')
        self.assertEqual(parser.normalize_ticker('FPT.VN'), 'FPT')
        self.assertEqual(parser.normalize_ticker('HPG.VN'), 'HPG')

        # Invalid formats
        self.assertIsNone(parser.normalize_ticker('1234.VN'))  # Numbers
        self.assertIsNone(parser.normalize_ticker('ABCD.VN'))  # 4 letters
        self.assertIsNone(parser.normalize_ticker('AB.VN'))    # 2 letters
        # Note: 'VCB' without .VN is normalized to 'VCB' (valid 3-letter code)

    # ========================================
    # TEST: Utility Functions
    # ========================================

    def test_add_custom_ticker(self):
        """Test adding custom ticker to default list"""
        # Use a ticker NOT in default list
        test_ticker = 'ABC'

        # Remove from default list if present
        if test_ticker in self.adapter.default_tickers:
            self.adapter.default_tickers.remove(test_ticker)

        # Mock successful ticker fetch
        mock_info = {
            'symbol': 'ABC.VN',
            'longName': 'ABC Company',
            'sector': 'Financial Services',
            'industry': 'Banks—Regional',
            'marketCap': 100000000000000,
            'currency': 'VND',
            'exchange': 'HCM'
        }

        self.adapter.yf_api.get_ticker_info = Mock(return_value=mock_info)
        self.db_mock.save_ticker = Mock()

        # Add custom ticker
        success = self.adapter.add_custom_ticker(test_ticker)

        # Verify success
        self.assertTrue(success)
        self.assertIn(test_ticker, self.adapter.default_tickers)
        self.adapter.yf_api.get_ticker_info.assert_called_once()
        self.db_mock.save_ticker.assert_called_once()

    def test_add_custom_ticker_invalid(self):
        """Test adding invalid ticker fails gracefully"""
        success = self.adapter.add_custom_ticker('INVALID')
        self.assertFalse(success)

    def test_scan_etfs_not_implemented(self):
        """Test scan_etfs returns empty (not implemented)"""
        result = self.adapter.scan_etfs()
        self.assertEqual(result, [])

    def test_collect_etf_ohlcv_not_implemented(self):
        """Test collect_etf_ohlcv returns 0 (not implemented)"""
        result = self.adapter.collect_etf_ohlcv()
        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
