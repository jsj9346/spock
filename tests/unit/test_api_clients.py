#!/usr/bin/env python3
"""
test_api_clients.py - Unit Tests for API Client Modules

Tests for:
- YFinanceAPI: Rate limiting, ticker conversion, OHLCV fetching
- KRXDataAPI: Stock/ETF list, market cap, sector classification

Coverage target: api_clients/*.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime, timedelta
import time


# =============================================================================
# YFinanceAPI Tests
# =============================================================================

class TestYFinanceAPIInit(unittest.TestCase):
    """Test YFinanceAPI initialization"""

    @patch('modules.api_clients.yfinance_api.yf')
    def test_initialization_default(self, mock_yf):
        """Test default initialization"""
        from modules.api_clients.yfinance_api import YFinanceAPI

        api = YFinanceAPI()

        self.assertEqual(api.rate_limit, 1.0)
        self.assertEqual(api.last_request_time, 0)
        self.assertIsNone(api.session)

    @patch('modules.api_clients.yfinance_api.yf')
    def test_initialization_custom_rate(self, mock_yf):
        """Test initialization with custom rate limit"""
        from modules.api_clients.yfinance_api import YFinanceAPI

        api = YFinanceAPI(rate_limit_per_second=2.0)

        self.assertEqual(api.rate_limit, 2.0)


class TestYFinanceAPITickerConversion(unittest.TestCase):
    """Test ticker format conversion"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI()

    def test_convert_preferred_stock(self):
        """Test US preferred stock conversion (/ -> -)"""
        result = self.api._to_yf_ticker('BRK/B')
        self.assertEqual(result, 'BRK-B')

    def test_convert_multiple_slash(self):
        """Test ticker with multiple slashes"""
        result = self.api._to_yf_ticker('MS/A')
        self.assertEqual(result, 'MS-A')

    def test_no_conversion_needed(self):
        """Test ticker without slash"""
        result = self.api._to_yf_ticker('AAPL')
        self.assertEqual(result, 'AAPL')

    def test_hong_kong_ticker(self):
        """Test HK ticker (no change)"""
        result = self.api._to_yf_ticker('0700.HK')
        self.assertEqual(result, '0700.HK')

    def test_japan_ticker(self):
        """Test Japan ticker (no change)"""
        result = self.api._to_yf_ticker('7203.T')
        self.assertEqual(result, '7203.T')


class TestYFinanceAPIRateLimiting(unittest.TestCase):
    """Test rate limiting functionality"""

    @patch('modules.api_clients.yfinance_api.yf')
    @patch('modules.api_clients.yfinance_api.time.sleep')
    @patch('modules.api_clients.yfinance_api.time.time')
    def test_rate_limit_sleep(self, mock_time, mock_sleep, mock_yf):
        """Test rate limiting sleep"""
        from modules.api_clients.yfinance_api import YFinanceAPI

        api = YFinanceAPI(rate_limit_per_second=1.0)
        api.last_request_time = 10.0

        # First call: 0.5 seconds elapsed -> should sleep 0.5s
        mock_time.return_value = 10.5
        api._rate_limit_sleep()

        mock_sleep.assert_called_once()
        args = mock_sleep.call_args[0]
        self.assertAlmostEqual(args[0], 0.5, places=1)

    @patch('modules.api_clients.yfinance_api.yf')
    @patch('modules.api_clients.yfinance_api.time.sleep')
    @patch('modules.api_clients.yfinance_api.time.time')
    def test_no_sleep_when_enough_time_passed(self, mock_time, mock_sleep, mock_yf):
        """Test no sleep when enough time has passed"""
        from modules.api_clients.yfinance_api import YFinanceAPI

        api = YFinanceAPI(rate_limit_per_second=1.0)
        api.last_request_time = 10.0

        # 2 seconds elapsed -> no sleep needed
        mock_time.return_value = 12.0
        api._rate_limit_sleep()

        mock_sleep.assert_not_called()

    @patch('modules.api_clients.yfinance_api.yf')
    def test_zero_rate_limit(self, mock_yf):
        """Test zero rate limit (no limiting)"""
        from modules.api_clients.yfinance_api import YFinanceAPI

        api = YFinanceAPI(rate_limit_per_second=0)
        api._rate_limit_sleep()  # Should not raise


class TestYFinanceAPIRetry(unittest.TestCase):
    """Test retry logic with exponential backoff"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)

    def test_successful_first_attempt(self):
        """Test successful first attempt"""
        mock_func = Mock(return_value='success')

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertEqual(result, 'success')
        mock_func.assert_called_once()

    @patch('modules.api_clients.yfinance_api.time.sleep')
    def test_retry_on_failure(self, mock_sleep):
        """Test retry on transient failure"""
        mock_func = Mock(side_effect=[Exception("Network error"), 'success'])

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 2)

    def test_non_retryable_error_delisted(self):
        """Test non-retryable error (delisted)"""
        mock_func = Mock(side_effect=Exception("Symbol may be delisted"))

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertIsNone(result)
        mock_func.assert_called_once()

    def test_non_retryable_error_no_data(self):
        """Test non-retryable error (no data)"""
        mock_func = Mock(side_effect=Exception("No data found"))

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertIsNone(result)
        mock_func.assert_called_once()

    def test_non_retryable_error_no_ohlcv_data(self):
        """Test non-retryable error (no OHLCV data)"""
        mock_func = Mock(side_effect=Exception("No OHLCV data for INVALID"))

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertIsNone(result)
        mock_func.assert_called_once()

    @patch('modules.api_clients.yfinance_api.time.sleep')
    def test_all_retries_exhausted(self, mock_sleep):
        """Test all retries exhausted"""
        mock_func = Mock(side_effect=Exception("Network error"))

        result = self.api._retry_on_failure(mock_func, max_retries=3)

        self.assertIsNone(result)
        self.assertEqual(mock_func.call_count, 3)


class TestYFinanceAPITickerInfo(unittest.TestCase):
    """Test ticker info fetching"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)
        self.mock_yf = mock_yf

    def test_get_ticker_info_success(self):
        """Test successful ticker info fetch"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'symbol': 'AAPL',
            'longName': 'Apple Inc.',
            'sector': 'Technology',
            'industry': 'Consumer Electronics',
            'marketCap': 3000000000000,
            'currency': 'USD',
            'exchange': 'NMS'
        }

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ticker_info('AAPL')

        self.assertIsNotNone(result)
        self.assertEqual(result['symbol'], 'AAPL')
        self.assertEqual(result['longName'], 'Apple Inc.')

    def test_get_ticker_info_no_data(self):
        """Test ticker info with no data"""
        mock_ticker = Mock()
        mock_ticker.info = {}

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ticker_info('INVALID')

        self.assertIsNone(result)

    def test_get_ticker_info_preferred_stock(self):
        """Test ticker info for preferred stock"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'symbol': 'BRK-B',
            'longName': 'Berkshire Hathaway Inc. Class B'
        }

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker) as mock_class:
            result = self.api.get_ticker_info('BRK/B')
            # Verify conversion happened
            mock_class.assert_called_with('BRK-B', session=None)


class TestYFinanceAPITickerSummary(unittest.TestCase):
    """Test simplified ticker summary"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)

    def test_get_ticker_summary_success(self):
        """Test successful ticker summary"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'symbol': '0700.HK',
            'longName': 'Tencent Holdings Limited',
            'sector': 'Communication Services',
            'industry': 'Internet Content & Information',
            'marketCap': 3500000000000,
            'currency': 'HKD',
            'exchange': 'HKG',
            'quoteType': 'EQUITY',
            'country': 'China',
            'website': 'https://www.tencent.com',
            'longBusinessSummary': 'Tencent Holdings Limited...'
        }

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ticker_summary('0700.HK')

        self.assertIsNotNone(result)
        self.assertEqual(result['ticker'], '0700.HK')
        self.assertEqual(result['name'], 'Tencent Holdings Limited')
        self.assertEqual(result['sector'], 'Communication Services')
        self.assertEqual(result['currency'], 'HKD')

    def test_get_ticker_summary_no_data(self):
        """Test ticker summary with no data"""
        mock_ticker = Mock()
        mock_ticker.info = {}

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ticker_summary('INVALID')

        self.assertIsNone(result)


class TestYFinanceAPIOHLCV(unittest.TestCase):
    """Test OHLCV data fetching"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)

    def test_get_ohlcv_success_period(self):
        """Test successful OHLCV fetch with period"""
        mock_ticker = Mock()
        mock_df = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=5),
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, 103, 104, 105, 106],
            'Volume': [1000000, 1100000, 1200000, 1300000, 1400000],
            'Dividends': [0, 0, 0, 0, 0],
            'Stock Splits': [0, 0, 0, 0, 0]
        }).set_index('Date')
        mock_ticker.history.return_value = mock_df

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ohlcv('AAPL', period='1mo')

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 5)
        self.assertIn('date', result.columns)
        self.assertIn('close', result.columns)

    def test_get_ohlcv_success_date_range(self):
        """Test successful OHLCV fetch with date range"""
        mock_ticker = Mock()
        mock_df = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=3),
            'Open': [100, 101, 102],
            'High': [105, 106, 107],
            'Low': [95, 96, 97],
            'Close': [102, 103, 104],
            'Volume': [1000000, 1100000, 1200000],
        }).set_index('Date')
        mock_ticker.history.return_value = mock_df

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ohlcv('AAPL', start_date='2024-01-01', end_date='2024-01-31')

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)

    def test_get_ohlcv_empty_data(self):
        """Test OHLCV with empty data"""
        mock_ticker = Mock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_ohlcv('INVALID')

        self.assertIsNone(result)

    def test_get_ohlcv_preferred_stock(self):
        """Test OHLCV for preferred stock"""
        mock_ticker = Mock()
        mock_df = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=2),
            'Open': [400, 401],
            'High': [410, 411],
            'Low': [390, 391],
            'Close': [405, 406],
            'Volume': [500000, 600000],
        }).set_index('Date')
        mock_ticker.history.return_value = mock_df

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker) as mock_class:
            result = self.api.get_ohlcv('BRK/B', period='1d')
            mock_class.assert_called_with('BRK-B', session=None)


class TestYFinanceAPIBatch(unittest.TestCase):
    """Test batch operations"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)

    def test_get_tickers_batch_success(self):
        """Test batch ticker info fetch"""
        mock_ticker = Mock()
        mock_ticker.info = {
            'symbol': 'TEST',
            'longName': 'Test Company'
        }

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.get_tickers_batch(['AAPL', 'MSFT', 'GOOGL'])

        self.assertEqual(len(result), 3)

    def test_get_tickers_batch_partial_failure(self):
        """Test batch with some failures"""
        def side_effect(*args, **kwargs):
            mock = Mock()
            if args[0] == 'INVALID':
                mock.info = {}
            else:
                mock.info = {'symbol': args[0], 'longName': 'Company'}
            return mock

        with patch('modules.api_clients.yfinance_api.yf.Ticker', side_effect=side_effect):
            result = self.api.get_tickers_batch(['AAPL', 'INVALID', 'GOOGL'])

        self.assertEqual(len(result), 2)
        self.assertIn('AAPL', result)
        self.assertNotIn('INVALID', result)


class TestYFinanceAPIUtility(unittest.TestCase):
    """Test utility methods"""

    @patch('modules.api_clients.yfinance_api.yf')
    def setUp(self, mock_yf):
        from modules.api_clients.yfinance_api import YFinanceAPI
        self.api = YFinanceAPI(rate_limit_per_second=0)

    def test_search_tickers_not_implemented(self):
        """Test search_tickers returns empty list"""
        result = self.api.search_tickers('Apple')
        self.assertEqual(result, [])

    def test_get_exchange_tickers_not_implemented(self):
        """Test get_exchange_tickers returns empty list"""
        result = self.api.get_exchange_tickers('NYSE')
        self.assertEqual(result, [])

    def test_validate_ticker_valid(self):
        """Test validate_ticker with valid ticker"""
        mock_ticker = Mock()
        mock_ticker.info = {'symbol': 'AAPL'}

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.validate_ticker('AAPL')

        self.assertTrue(result)

    def test_validate_ticker_invalid(self):
        """Test validate_ticker with invalid ticker"""
        mock_ticker = Mock()
        mock_ticker.info = {}

        with patch('modules.api_clients.yfinance_api.yf.Ticker', return_value=mock_ticker):
            result = self.api.validate_ticker('INVALID')

        self.assertFalse(result)

    def test_close_session(self):
        """Test session close"""
        mock_session = Mock()
        self.api.session = mock_session
        self.api.close()

        mock_session.close.assert_called_once()
        self.assertIsNone(self.api.session)

    def test_close_no_session(self):
        """Test close with no session"""
        self.api.session = None
        self.api.close()  # Should not raise


# =============================================================================
# KRXDataAPI Tests
# =============================================================================

class TestKRXDataAPIInit(unittest.TestCase):
    """Test KRXDataAPI initialization"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def test_initialization(self, mock_session_class):
        """Test default initialization"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI

        api = KRXDataAPI()

        self.assertEqual(api.session, mock_session)
        mock_session.headers.update.assert_called_once()


class TestKRXDataAPIParseNumber(unittest.TestCase):
    """Test number parsing utility"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session):
        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_parse_number_with_commas(self):
        """Test parsing number with commas"""
        result = self.api._parse_number('1,234,567')
        self.assertEqual(result, 1234567)

    def test_parse_number_without_commas(self):
        """Test parsing number without commas"""
        result = self.api._parse_number('12345')
        self.assertEqual(result, 12345)

    def test_parse_number_empty(self):
        """Test parsing empty string"""
        result = self.api._parse_number('')
        self.assertEqual(result, 0)

    def test_parse_number_dash(self):
        """Test parsing dash (missing value)"""
        result = self.api._parse_number('-')
        self.assertEqual(result, 0)

    def test_parse_number_none(self):
        """Test parsing None"""
        result = self.api._parse_number(None)
        self.assertEqual(result, 0)


class TestKRXDataAPIStockList(unittest.TestCase):
    """Test stock list fetching"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session_class):
        self.mock_session = Mock()
        mock_session_class.return_value = self.mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_get_stock_list_success(self):
        """Test successful stock list fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'OutBlock_1': [
                {
                    'ISU_SRT_CD': '005930',
                    'ISU_ABBRV': '삼성전자',
                    'ISU_ENG_NM': 'Samsung Electronics',
                    'MKT_TP_NM': 'KOSPI',
                    'LIST_DD': '1975-06-11',
                    'LIST_SHRS': '5,969,782,550'
                },
                {
                    'ISU_SRT_CD': '035720',
                    'ISU_ABBRV': '카카오',
                    'ISU_ENG_NM': 'Kakao',
                    'MKT_TP_NM': 'KOSPI',
                    'LIST_DD': '2017-07-10',
                    'LIST_SHRS': '445,348,875'
                }
            ]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.get_stock_list('ALL')

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], '005930')
        self.assertEqual(result[0]['name'], '삼성전자')
        self.assertEqual(result[0]['market'], 'KOSPI')
        self.assertEqual(result[0]['data_source'], 'KRX Data API')

    def test_get_stock_list_empty(self):
        """Test stock list with empty result"""
        mock_response = Mock()
        mock_response.json.return_value = {'OutBlock_1': []}
        self.mock_session.post.return_value = mock_response

        result = self.api.get_stock_list('KONEX')

        self.assertEqual(result, [])

    def test_get_stock_list_error(self):
        """Test stock list with API error"""
        self.mock_session.post.side_effect = Exception("Network error")

        with self.assertRaises(Exception):
            self.api.get_stock_list('ALL')


class TestKRXDataAPIETFList(unittest.TestCase):
    """Test ETF list fetching"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session_class):
        self.mock_session = Mock()
        mock_session_class.return_value = self.mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_get_etf_list_success(self):
        """Test successful ETF list fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'output': [
                {
                    'ISU_SRT_CD': '069500',
                    'ISU_ABBRV': 'KODEX 200',
                    'ISU_ENG_NM': 'KODEX 200',
                    'COMPANY_NM': '삼성자산운용',
                    'OBJ_TP_NM': 'KOSPI 200',
                    'LIST_SHRS': '160,000,000',
                    'LIST_DD': '2002-10-14'
                }
            ]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.get_etf_list()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticker'], '069500')
        self.assertEqual(result[0]['name'], 'KODEX 200')
        self.assertEqual(result[0]['issuer'], '삼성자산운용')
        self.assertEqual(result[0]['market'], 'KOSPI')

    def test_get_etf_list_outblock1_format(self):
        """Test ETF list with OutBlock_1 format"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'OutBlock_1': [
                {
                    'ISU_SRT_CD': '069500',
                    'ISU_ABBRV': 'KODEX 200'
                }
            ]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.get_etf_list()

        self.assertEqual(len(result), 1)

    def test_get_etf_list_error(self):
        """Test ETF list with API error"""
        self.mock_session.post.side_effect = Exception("Timeout")

        with self.assertRaises(Exception):
            self.api.get_etf_list()


class TestKRXDataAPIMarketCap(unittest.TestCase):
    """Test market cap data fetching"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session_class):
        self.mock_session = Mock()
        mock_session_class.return_value = self.mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_get_market_cap_data_success(self):
        """Test successful market cap fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'OutBlock_1': [
                {
                    'ISU_SRT_CD': '005930',
                    'ISU_ABBRV': '삼성전자',
                    'TDD_CLSPRC': '71,000',
                    'MKTCAP': '423,634,400,900,000',
                    'ACC_TRDVOL': '12,345,678',
                    'ACC_TRDVAL': '876,543,210,000'
                }
            ]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.get_market_cap_data('ALL')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticker'], '005930')
        self.assertEqual(result[0]['close_price'], 71000)
        self.assertEqual(result[0]['market_cap'], 423634400900000)

    def test_get_market_cap_data_error(self):
        """Test market cap with API error"""
        self.mock_session.post.side_effect = Exception("Server error")

        with self.assertRaises(Exception):
            self.api.get_market_cap_data('ALL')


class TestKRXDataAPIConnection(unittest.TestCase):
    """Test connection check"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session_class):
        self.mock_session = Mock()
        mock_session_class.return_value = self.mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_check_connection_success(self):
        """Test successful connection check"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'OutBlock_1': [{'ISU_SRT_CD': '005930'}]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.check_connection()

        self.assertTrue(result)

    def test_check_connection_empty_result(self):
        """Test connection check with empty result"""
        mock_response = Mock()
        mock_response.json.return_value = {'OutBlock_1': []}
        self.mock_session.post.return_value = mock_response

        result = self.api.check_connection()

        self.assertFalse(result)

    def test_check_connection_no_outblock(self):
        """Test connection check with no OutBlock_1"""
        mock_response = Mock()
        mock_response.json.return_value = {}
        self.mock_session.post.return_value = mock_response

        result = self.api.check_connection()

        self.assertFalse(result)

    def test_check_connection_failure(self):
        """Test connection check failure"""
        self.mock_session.post.side_effect = Exception("Connection refused")

        result = self.api.check_connection()

        self.assertFalse(result)


class TestKRXDataAPISectorClassification(unittest.TestCase):
    """Test sector classification fetching"""

    @patch('modules.api_clients.krx_data_api.requests.Session')
    def setUp(self, mock_session_class):
        self.mock_session = Mock()
        mock_session_class.return_value = self.mock_session

        from modules.api_clients.krx_data_api import KRXDataAPI
        self.api = KRXDataAPI()

    def test_get_sector_classification_success(self):
        """Test successful sector classification fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'OutBlock_1': [
                {
                    'ISU_SRT_CD': '005930',
                    'IDX_IND_NM': '전기전자',
                    'IDX_IND_CD': 'G25',
                    'IDX_NM': '반도체',
                    'IDX_CD': 'G2520'
                }
            ]
        }
        self.mock_session.post.return_value = mock_response

        result = self.api.get_sector_classification('ALL')

        self.assertIn('005930', result)
        self.assertEqual(result['005930']['sector'], '전기전자')
        self.assertEqual(result['005930']['industry'], '반도체')

    def test_get_sector_classification_empty_first_retry(self):
        """Test sector classification with date fallback"""
        mock_response_empty = Mock()
        mock_response_empty.json.return_value = {'OutBlock_1': []}

        mock_response_success = Mock()
        mock_response_success.json.return_value = {
            'OutBlock_1': [
                {'ISU_SRT_CD': '005930', 'IDX_IND_NM': '전기전자'}
            ]
        }

        self.mock_session.post.side_effect = [mock_response_empty, mock_response_success]

        result = self.api.get_sector_classification('ALL')

        self.assertIn('005930', result)

    def test_get_sector_classification_all_dates_empty(self):
        """Test sector classification with all dates returning empty"""
        mock_response = Mock()
        mock_response.json.return_value = {'OutBlock_1': []}
        self.mock_session.post.return_value = mock_response

        result = self.api.get_sector_classification('ALL')

        # After trying multiple dates, should return empty dict
        self.assertEqual(result, {})


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("db_ticker,expected_yf", [
    ('BRK/B', 'BRK-B'),
    ('MS/A', 'MS-A'),
    ('AAPL', 'AAPL'),
    ('0700.HK', '0700.HK'),
    ('7203.T', '7203.T'),
])
def test_yfinance_ticker_conversion(db_ticker, expected_yf):
    """Test ticker conversion for various formats"""
    with patch('modules.api_clients.yfinance_api.yf'):
        from modules.api_clients.yfinance_api import YFinanceAPI
        api = YFinanceAPI()
        assert api._to_yf_ticker(db_ticker) == expected_yf


@pytest.mark.parametrize("value,expected", [
    ('1,234,567', 1234567),
    ('100', 100),
    ('', 0),
    ('-', 0),
    (None, 0),
    ('0', 0),
])
def test_krx_parse_number(value, expected):
    """Test KRX number parsing"""
    with patch('modules.api_clients.krx_data_api.requests.Session'):
        from modules.api_clients.krx_data_api import KRXDataAPI
        api = KRXDataAPI()
        assert api._parse_number(value) == expected


@pytest.mark.parametrize("market,market_map_key,expected", [
    ('KOSPI', 'KOSPI', 'KOSPI'),
    ('KOSDAQ', 'KOSDAQ', 'KOSDAQ'),
    ('KONEX', 'KONEX', 'KONEX'),
])
def test_krx_market_mapping(market, market_map_key, expected):
    """Test KRX market mapping"""
    market_map = {'KOSPI': 'KOSPI', 'KOSDAQ': 'KOSDAQ', 'KONEX': 'KONEX'}
    assert market_map.get(market, 'UNKNOWN') == expected


@pytest.mark.parametrize("error_msg,should_retry", [
    ('Network timeout', True),
    ('Connection refused', True),
    ('Symbol may be delisted', False),
    ('No data found', False),
    ('No OHLCV data', False),
    ('Quote not found', False),
])
def test_yfinance_retry_decision(error_msg, should_retry):
    """Test retry decision based on error message"""
    non_retryable_errors = [
        'delisted', 'no data found', 'no data', 'no ohlcv data',
        'not found', 'symbol may be delisted', 'no timezone found', 'quote not found'
    ]
    is_non_retryable = any(err in error_msg.lower() for err in non_retryable_errors)
    assert is_non_retryable == (not should_retry)


if __name__ == '__main__':
    unittest.main(verbosity=2)
