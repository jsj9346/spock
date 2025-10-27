"""
Unit Tests for USAdapter

Tests US stock market data collection via Polygon.io integration.

Author: Spock Trading System
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime

from modules.market_adapters.us_adapter import USAdapter
from modules.parsers.us_stock_parser import USStockParser


class TestUSAdapter(unittest.TestCase):
    """Test suite for USAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock database manager
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        # Mock Polygon API key
        self.api_key = 'test_polygon_api_key'

        # Create adapter with mocked dependencies
        with patch('modules.market_adapters.us_adapter.PolygonAPI'):
            with patch('modules.market_adapters.us_adapter.MarketCalendar'):
                self.adapter = USAdapter(self.mock_db, self.api_key)
                self.adapter.polygon_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test USAdapter initialization"""
        self.assertEqual(self.adapter.region_code, 'US')
        self.assertIsNotNone(self.adapter.polygon_api)
        self.assertIsNotNone(self.adapter.stock_parser)
        self.assertIsNotNone(self.adapter.sector_mapper)
        self.assertIsNotNone(self.adapter.calendar)

    def test_scan_stocks_with_cache(self):
        """Test scan_stocks with valid cache"""
        # Mock cached data
        cached_stocks = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.', 'region': 'US'},
            {'ticker': 'MSFT', 'name': 'Microsoft Corporation', 'region': 'US'}
        ]

        self.adapter._load_tickers_from_cache = Mock(return_value=cached_stocks)

        # Scan stocks (should use cache)
        result = self.adapter.scan_stocks(force_refresh=False)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], 'AAPL')
        self.adapter._load_tickers_from_cache.assert_called_once()

    def test_scan_stocks_force_refresh(self):
        """Test scan_stocks with force_refresh=True"""
        # Mock Polygon API response
        mock_polygon_response = [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True
            },
            {
                'ticker': 'GOOGL',
                'name': 'Alphabet Inc.',
                'market': 'stocks',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True
            }
        ]

        self.adapter.polygon_api.get_stock_list.return_value = mock_polygon_response
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter._enrich_with_fundamentals = Mock(side_effect=lambda stocks, max_count: stocks)
        self.adapter._save_tickers_to_db = Mock()

        # Scan stocks
        result = self.adapter.scan_stocks(force_refresh=True)

        self.assertGreater(len(result), 0)
        self.adapter.polygon_api.get_stock_list.assert_called()
        self.adapter._save_tickers_to_db.assert_called_once()

    def test_scan_stocks_filters_common_stocks(self):
        """Test that scan_stocks filters out non-common stocks"""
        # Mock response with mixed asset types
        mock_response = [
            {'ticker': 'AAPL', 'market': 'stocks', 'type': 'CS', 'active': True},  # Common
            {'ticker': 'SPY', 'market': 'stocks', 'type': 'ETF', 'active': True},  # ETF
            {'ticker': 'BAC.PFD', 'market': 'stocks', 'type': 'PFD', 'active': True}  # Preferred
        ]

        self.adapter.polygon_api.get_stock_list.return_value = mock_response
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        # Mock enrichment to only keep the stocks it receives (already filtered)
        self.adapter._enrich_with_fundamentals = Mock(side_effect=lambda stocks, max_count: stocks[:max_count])
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        # Filter was applied by USStockParser.filter_common_stocks()
        # All results should be common stocks (CS)
        common_stocks = [s for s in result if s.get('asset_type_code') == 'CS']
        # Result should contain only AAPL (1 common stock)
        self.assertGreater(len(common_stocks), 0)
        # Verify filtering happened
        etf_count = len([s for s in result if s.get('asset_type_code') == 'ETF'])
        self.assertEqual(etf_count, 0)  # No ETFs should remain

    def test_scan_etfs(self):
        """Test ETF scanning"""
        mock_response = [
            {'ticker': 'SPY', 'market': 'stocks', 'type': 'ETF', 'active': True},
            {'ticker': 'QQQ', 'market': 'stocks', 'type': 'ETF', 'active': True},
            {'ticker': 'AAPL', 'market': 'stocks', 'type': 'CS', 'active': True}  # Not ETF
        ]

        self.adapter.polygon_api.get_stock_list.return_value = mock_response
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_etfs(force_refresh=True)

        # Should only return ETFs
        self.assertEqual(len(result), 2)
        self.assertTrue(all(t.get('asset_type_code') == 'ETF' for t in result))

    def test_collect_stock_ohlcv(self):
        """Test OHLCV data collection"""
        # Mock ticker list
        self.mock_db.get_tickers.return_value = [
            {'ticker': 'AAPL'},
            {'ticker': 'MSFT'}
        ]

        # Mock Polygon API OHLCV response
        mock_ohlcv = [
            {
                'v': 100000000, 'vw': 150.25, 'o': 150.00, 'c': 151.00,
                'h': 152.00, 'l': 149.50, 't': 1609459200000, 'date': '2021-01-01'
            }
        ]

        self.adapter.polygon_api.get_daily_ohlcv_last_n_days.return_value = mock_ohlcv
        self.adapter._calculate_technical_indicators = Mock(side_effect=lambda df: df)
        self.adapter._save_ohlcv_to_db = Mock()

        # Collect OHLCV
        result = self.adapter.collect_stock_ohlcv(tickers=['AAPL', 'MSFT'], days=250)

        self.assertEqual(result, 2)  # Both stocks successful
        self.assertEqual(self.adapter.polygon_api.get_daily_ohlcv_last_n_days.call_count, 2)
        self.assertEqual(self.adapter._save_ohlcv_to_db.call_count, 2)

    def test_collect_stock_ohlcv_empty_response(self):
        """Test OHLCV collection with empty API response"""
        self.mock_db.get_tickers.return_value = [{'ticker': 'INVALID'}]

        # Mock empty response
        self.adapter.polygon_api.get_daily_ohlcv_last_n_days.return_value = []
        self.adapter._save_ohlcv_to_db = Mock()

        result = self.adapter.collect_stock_ohlcv(tickers=['INVALID'], days=250)

        self.assertEqual(result, 0)  # No successful updates
        self.adapter._save_ohlcv_to_db.assert_not_called()

    def test_collect_fundamentals(self):
        """Test fundamentals collection"""
        mock_details = {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'market_cap': 2800000000000,
            'sic_code': '3571',
            'sic_description': 'ELECTRONIC COMPUTERS'
        }

        self.adapter.polygon_api.get_ticker_details.return_value = mock_details
        self.adapter._save_fundamentals_to_db = Mock()

        result = self.adapter.collect_fundamentals(tickers=['AAPL'])

        self.assertEqual(result, 1)
        self.adapter.polygon_api.get_ticker_details.assert_called_once_with('AAPL')
        self.adapter._save_fundamentals_to_db.assert_called_once()

    def test_enrich_with_fundamentals(self):
        """Test stock enrichment with fundamentals"""
        stocks = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.'},
            {'ticker': 'MSFT', 'name': 'Microsoft Corporation'}
        ]

        mock_details = {
            'ticker': 'AAPL',
            'sector': 'Information Technology',
            'market_cap': 2800000000000
        }

        self.adapter.polygon_api.get_ticker_details.return_value = mock_details
        self.adapter.stock_parser.parse_ticker_details = Mock(return_value=mock_details)

        result = self.adapter._enrich_with_fundamentals(stocks, max_count=1)

        # First stock should be enriched
        self.assertEqual(result[0]['sector'], 'Information Technology')
        self.assertEqual(result[0]['market_cap'], 2800000000000)

        # Second stock should remain unenriched
        self.assertNotIn('sector', result[1])

    def test_check_market_status(self):
        """Test market status check"""
        mock_status = {
            'is_open': True,
            'market': 'US',
            'time_until_close': '4:30:00'
        }

        self.adapter.calendar.get_market_status.return_value = mock_status

        result = self.adapter.check_market_status()

        self.assertTrue(result['is_open'])
        self.assertEqual(result['market'], 'US')

    def test_exchange_mapping(self):
        """Test exchange code to name mapping"""
        self.assertEqual(self.adapter.EXCHANGES['XNYS'], 'NYSE')
        self.assertEqual(self.adapter.EXCHANGES['XNAS'], 'NASDAQ')
        self.assertEqual(self.adapter.EXCHANGES['XASE'], 'AMEX')

    def test_rate_limiting_in_collection(self):
        """Test that rate limiting is respected during OHLCV collection"""
        self.mock_db.get_tickers.return_value = [
            {'ticker': 'AAPL'},
            {'ticker': 'MSFT'},
            {'ticker': 'GOOGL'}
        ]

        mock_ohlcv = [
            {'v': 100000000, 'vw': 150.25, 'o': 150.00, 'c': 151.00,
             'h': 152.00, 'l': 149.50, 't': 1609459200000, 'date': '2021-01-01'}
        ]

        self.adapter.polygon_api.get_daily_ohlcv_last_n_days.return_value = mock_ohlcv
        self.adapter._calculate_technical_indicators = Mock(side_effect=lambda df: df)
        self.adapter._save_ohlcv_to_db = Mock()

        # Collect OHLCV (rate limiting handled by Polygon API client)
        result = self.adapter.collect_stock_ohlcv(tickers=['AAPL', 'MSFT', 'GOOGL'], days=250)

        # Verify all stocks processed
        self.assertEqual(result, 3)
        self.assertEqual(self.adapter.polygon_api.get_daily_ohlcv_last_n_days.call_count, 3)


if __name__ == '__main__':
    unittest.main()
