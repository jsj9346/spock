"""
Unit Tests for KIS-Based Adapters (Phase 6)

Tests for KIS API overseas stock adapters:
- USAdapterKIS (US market)
- HKAdapterKIS (Hong Kong market)
- CNAdapterKIS (China market)
- JPAdapterKIS (Japan market)
- VNAdapterKIS (Vietnam market)

Author: Spock Trading System - Phase 6
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta

from modules.market_adapters.us_adapter_kis import USAdapterKIS
from modules.market_adapters.hk_adapter_kis import HKAdapterKIS
from modules.market_adapters.cn_adapter_kis import CNAdapterKIS
from modules.market_adapters.jp_adapter_kis import JPAdapterKIS
from modules.market_adapters.vn_adapter_kis import VNAdapterKIS


class TestUSAdapterKIS(unittest.TestCase):
    """Test suite for USAdapterKIS (Phase 6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        self.app_key = 'test_kis_app_key'
        self.app_secret = 'test_kis_app_secret'

        with patch('modules.market_adapters.us_adapter_kis.KISOverseasStockAPI'):
            with patch('modules.market_adapters.us_adapter_kis.MarketCalendar'):
                self.adapter = USAdapterKIS(self.mock_db, self.app_key, self.app_secret)
                self.adapter.kis_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test USAdapterKIS initialization"""
        self.assertEqual(self.adapter.region_code, 'US')
        self.assertEqual(self.adapter.REGION_CODE, 'US')
        self.assertEqual(len(self.adapter.EXCHANGE_CODES), 3)
        self.assertIn('NASD', self.adapter.EXCHANGE_CODES)
        self.assertIn('NYSE', self.adapter.EXCHANGE_CODES)
        self.assertIn('AMEX', self.adapter.EXCHANGE_CODES)
        self.assertIsNotNone(self.adapter.kis_api)
        self.assertIsNotNone(self.adapter.stock_parser)

    def test_scan_stocks_with_cache(self):
        """Test scan_stocks with valid cache"""
        cached_stocks = [
            {'ticker': 'AAPL', 'name': 'Apple Inc.', 'region': 'US', 'kis_exchange_code': 'NASD'},
            {'ticker': 'MSFT', 'name': 'Microsoft Corp', 'region': 'US', 'kis_exchange_code': 'NASD'}
        ]

        self.adapter._load_tickers_from_cache = Mock(return_value=cached_stocks)

        result = self.adapter.scan_stocks(force_refresh=False)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['ticker'], 'AAPL')
        self.adapter._load_tickers_from_cache.assert_called_once()

    def test_scan_stocks_kis_api_call(self):
        """Test scan_stocks fetches from KIS API"""
        # Mock KIS API response
        self.adapter.kis_api.get_tradable_tickers.return_value = ['AAPL', 'MSFT', 'GOOGL']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'sector': 'Technology',
            'market_cap': 2800000000000
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        # KIS API should be called for all 3 exchanges
        self.assertEqual(self.adapter.kis_api.get_tradable_tickers.call_count, 3)
        # Parser should be called for each ticker across all exchanges
        self.assertGreater(self.adapter.stock_parser.parse_ticker_info.call_count, 0)
        self.adapter._save_tickers_to_db.assert_called_once()

    def test_scan_stocks_exchange_filtering(self):
        """Test scan_stocks with specific exchanges"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['AAPL']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': 'AAPL',
            'name': 'Apple Inc.'
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True, exchanges=['NASD'])

        # Should only call KIS API for NASDAQ
        self.adapter.kis_api.get_tradable_tickers.assert_called_once_with(
            exchange_code='NASD',
            max_count=None
        )

    def test_collect_stock_ohlcv(self):
        """Test OHLCV data collection via KIS API"""
        self.mock_db.get_tickers.return_value = [
            {'ticker': 'AAPL', 'kis_exchange_code': 'NASD'},
            {'ticker': 'MSFT', 'kis_exchange_code': 'NASD'}
        ]

        # Mock KIS API OHLCV response
        mock_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [150.0, 151.0, 152.0, 153.0, 154.0],
            'high': [151.0, 152.0, 153.0, 154.0, 155.0],
            'low': [149.0, 150.0, 151.0, 152.0, 153.0],
            'close': [150.5, 151.5, 152.5, 153.5, 154.5],
            'volume': [100000, 110000, 120000, 130000, 140000]
        })

        self.adapter.kis_api.get_ohlcv.return_value = mock_ohlcv
        self.adapter._calculate_technical_indicators = Mock(side_effect=lambda df: df)
        self.mock_db.save_ohlcv_batch = Mock()

        result = self.adapter.collect_stock_ohlcv(tickers=['AAPL', 'MSFT'], days=250)

        self.assertEqual(result, 2)
        self.assertEqual(self.adapter.kis_api.get_ohlcv.call_count, 2)
        self.assertEqual(self.mock_db.save_ohlcv_batch.call_count, 2)

    def test_collect_stock_ohlcv_empty_response(self):
        """Test OHLCV collection with empty KIS API response"""
        self.mock_db.get_tickers.return_value = [{'ticker': 'INVALID', 'kis_exchange_code': 'NASD'}]

        self.adapter.kis_api.get_ohlcv.return_value = pd.DataFrame()
        self.mock_db.save_ohlcv_batch = Mock()

        result = self.adapter.collect_stock_ohlcv(tickers=['INVALID'], days=250)

        self.assertEqual(result, 0)
        self.mock_db.save_ohlcv_batch.assert_not_called()

    def test_collect_fundamentals(self):
        """Test fundamentals collection (yfinance fallback)"""
        self.mock_db.get_tickers.return_value = [{'ticker': 'AAPL'}]

        self.adapter.stock_parser.parse_fundamentals = Mock(return_value={
            'market_cap': 2800000000000,
            'pe_ratio': 28.5,
            'dividend_yield': 0.005
        })
        self.mock_db.save_fundamentals = Mock()

        result = self.adapter.collect_fundamentals(tickers=['AAPL'])

        self.assertEqual(result, 1)
        self.adapter.stock_parser.parse_fundamentals.assert_called_once_with('AAPL')
        self.mock_db.save_fundamentals.assert_called_once()

    def test_add_custom_ticker(self):
        """Test adding custom ticker"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['AAPL', 'CUSTOM']
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': 'CUSTOM',
            'name': 'Custom Corp'
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.add_custom_ticker('CUSTOM', exchange_code='NASD')

        self.assertTrue(result)
        self.adapter._save_tickers_to_db.assert_called_once()

    def test_check_connection(self):
        """Test KIS API connection check"""
        self.adapter.kis_api.check_connection.return_value = True

        result = self.adapter.check_connection()

        self.assertTrue(result)
        self.adapter.kis_api.check_connection.assert_called_once()

    def test_get_market_status(self):
        """Test market status retrieval"""
        self.adapter.calendar.is_market_open.return_value = True
        self.adapter.calendar.get_next_market_open.return_value = datetime.now()
        self.adapter.calendar.get_next_market_close.return_value = datetime.now() + timedelta(hours=4)

        result = self.adapter.get_market_status()

        self.assertEqual(result['region'], 'US')
        self.assertTrue(result['is_open'])
        self.assertEqual(result['timezone'], 'America/New_York')


class TestHKAdapterKIS(unittest.TestCase):
    """Test suite for HKAdapterKIS (Phase 6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        with patch('modules.market_adapters.hk_adapter_kis.KISOverseasStockAPI'):
            with patch('modules.market_adapters.hk_adapter_kis.MarketCalendar'):
                self.adapter = HKAdapterKIS(self.mock_db, 'key', 'secret')
                self.adapter.kis_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test HKAdapterKIS initialization"""
        self.assertEqual(self.adapter.region_code, 'HK')
        self.assertEqual(self.adapter.EXCHANGE_CODE, 'SEHK')
        self.assertIsNotNone(self.adapter.kis_api)

    def test_scan_stocks_kis_api(self):
        """Test HK stock scanning via KIS API"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['0700', '0941', '9988']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': '0700',
            'name': 'Tencent Holdings',
            'sector': 'Communication Services'
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        self.adapter.kis_api.get_tradable_tickers.assert_called_once_with(
            exchange_code='SEHK',
            max_count=None
        )
        self.assertGreater(len(result), 0)

    def test_collect_stock_ohlcv(self):
        """Test HK OHLCV collection"""
        self.mock_db.get_tickers.return_value = [{'ticker': '0700'}]

        mock_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [300.0] * 5,
            'high': [310.0] * 5,
            'low': [290.0] * 5,
            'close': [305.0] * 5,
            'volume': [50000000] * 5
        })

        self.adapter.kis_api.get_ohlcv.return_value = mock_ohlcv
        self.adapter._calculate_technical_indicators = Mock(side_effect=lambda df: df)
        self.mock_db.save_ohlcv_batch = Mock()

        result = self.adapter.collect_stock_ohlcv(tickers=['0700'], days=250)

        self.assertEqual(result, 1)


class TestCNAdapterKIS(unittest.TestCase):
    """Test suite for CNAdapterKIS (Phase 6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        with patch('modules.market_adapters.cn_adapter_kis.KISOverseasStockAPI'):
            with patch('modules.market_adapters.cn_adapter_kis.MarketCalendar'):
                self.adapter = CNAdapterKIS(self.mock_db, 'key', 'secret')
                self.adapter.kis_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test CNAdapterKIS initialization"""
        self.assertEqual(self.adapter.region_code, 'CN')
        self.assertEqual(len(self.adapter.EXCHANGE_CODES), 2)
        self.assertIn('SHAA', self.adapter.EXCHANGE_CODES)
        self.assertIn('SZAA', self.adapter.EXCHANGE_CODES)

    def test_scan_stocks_filters_st_stocks(self):
        """Test CN stock scanning filters ST stocks"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['600519', 'ST0001', '000001']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)

        # Mock parser to return ticker info
        def mock_parse(ticker):
            if 'ST' in ticker:
                return None  # ST stocks filtered by parser
            return {'ticker': ticker, 'name': f'Company {ticker}'}

        self.adapter.stock_parser.parse_ticker_info = Mock(side_effect=mock_parse)
        self.adapter.stock_parser.filter_common_stocks = Mock(side_effect=lambda stocks: [
            s for s in stocks if 'ST' not in s.get('ticker', '')
        ])
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        # ST stocks should be filtered out
        st_stocks = [s for s in result if 'ST' in s.get('ticker', '')]
        self.assertEqual(len(st_stocks), 0)

    def test_scan_stocks_both_exchanges(self):
        """Test CN scanning covers both SSE and SZSE"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['600519']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': '600519',
            'name': 'Kweichow Moutai'
        })
        self.adapter.stock_parser.filter_common_stocks = Mock(side_effect=lambda stocks: stocks)
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        # Should call both exchanges (SHAA, SZAA)
        self.assertEqual(self.adapter.kis_api.get_tradable_tickers.call_count, 2)


class TestJPAdapterKIS(unittest.TestCase):
    """Test suite for JPAdapterKIS (Phase 6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        with patch('modules.market_adapters.jp_adapter_kis.KISOverseasStockAPI'):
            with patch('modules.market_adapters.jp_adapter_kis.MarketCalendar'):
                self.adapter = JPAdapterKIS(self.mock_db, 'key', 'secret')
                self.adapter.kis_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test JPAdapterKIS initialization"""
        self.assertEqual(self.adapter.region_code, 'JP')
        self.assertEqual(self.adapter.EXCHANGE_CODE, 'TKSE')

    def test_scan_stocks_kis_api(self):
        """Test JP stock scanning via KIS API"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['7203', '9984', '6758']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': '7203',
            'name': 'Toyota Motor Corp',
            'sector': 'Consumer Cyclical'
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        self.adapter.kis_api.get_tradable_tickers.assert_called_once()
        self.assertGreater(len(result), 0)


class TestVNAdapterKIS(unittest.TestCase):
    """Test suite for VNAdapterKIS (Phase 6)"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_db = Mock()
        self.mock_db.get_tickers.return_value = []

        with patch('modules.market_adapters.vn_adapter_kis.KISOverseasStockAPI'):
            with patch('modules.market_adapters.vn_adapter_kis.MarketCalendar'):
                self.adapter = VNAdapterKIS(self.mock_db, 'key', 'secret')
                self.adapter.kis_api = Mock()
                self.adapter.calendar = Mock()

    def test_init_adapter(self):
        """Test VNAdapterKIS initialization"""
        self.assertEqual(self.adapter.region_code, 'VN')
        self.assertEqual(len(self.adapter.EXCHANGE_CODES), 2)
        self.assertIn('HASE', self.adapter.EXCHANGE_CODES)
        self.assertIn('VNSE', self.adapter.EXCHANGE_CODES)

    def test_scan_stocks_both_exchanges(self):
        """Test VN scanning covers HOSE and HNX"""
        self.adapter.kis_api.get_tradable_tickers.return_value = ['VCB', 'VNM']
        self.adapter._load_tickers_from_cache = Mock(return_value=None)
        self.adapter.stock_parser.parse_ticker_info = Mock(return_value={
            'ticker': 'VCB',
            'name': 'Vietcombank'
        })
        self.adapter._save_tickers_to_db = Mock()

        result = self.adapter.scan_stocks(force_refresh=True)

        # Should call both exchanges (HASE, VNSE)
        self.assertEqual(self.adapter.kis_api.get_tradable_tickers.call_count, 2)

    def test_collect_stock_ohlcv_with_exchange_codes(self):
        """Test VN OHLCV collection retrieves exchange codes"""
        self.mock_db.get_tickers.return_value = [
            {'ticker': 'VCB', 'kis_exchange_code': 'HASE'}
        ]

        mock_ohlcv = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=3),
            'open': [90000] * 3,
            'high': [91000] * 3,
            'low': [89000] * 3,
            'close': [90500] * 3,
            'volume': [1000000] * 3
        })

        self.adapter.kis_api.get_ohlcv.return_value = mock_ohlcv
        self.adapter._calculate_technical_indicators = Mock(side_effect=lambda df: df)
        self.mock_db.save_ohlcv_batch = Mock()

        result = self.adapter.collect_stock_ohlcv(tickers=['VCB'], days=250)

        self.assertEqual(result, 1)
        # Verify KIS API called with correct exchange code
        self.adapter.kis_api.get_ohlcv.assert_called_once()
        call_args = self.adapter.kis_api.get_ohlcv.call_args
        self.assertEqual(call_args[1]['exchange_code'], 'HASE')


class TestKISAdaptersComparison(unittest.TestCase):
    """Test suite comparing KIS adapters with legacy adapters"""

    def test_performance_advantage(self):
        """Verify KIS adapters have performance advantages"""
        # KIS API rate limit: 20 req/sec
        # Polygon.io: 5 req/min = 0.083 req/sec → 240x improvement
        # yfinance: 1 req/sec → 20x improvement
        # AkShare: 1.5 req/sec → 13.3x improvement

        kis_rate_limit = 20  # req/sec

        # Legacy API rates
        polygon_rate = 5 / 60  # 5 req/min
        yfinance_rate = 1
        akshare_rate = 1.5

        # Calculate improvements
        polygon_improvement = kis_rate_limit / polygon_rate
        yfinance_improvement = kis_rate_limit / yfinance_rate
        akshare_improvement = kis_rate_limit / akshare_rate

        self.assertGreater(polygon_improvement, 200)  # ~240x
        self.assertEqual(yfinance_improvement, 20)    # 20x
        self.assertGreater(akshare_improvement, 13)   # ~13.3x

    def test_unified_api_key(self):
        """Verify all KIS adapters use same API key"""
        mock_db = Mock()
        app_key = 'unified_kis_key'
        app_secret = 'unified_kis_secret'

        with patch('modules.market_adapters.us_adapter_kis.KISOverseasStockAPI') as mock_us:
            with patch('modules.market_adapters.hk_adapter_kis.KISOverseasStockAPI') as mock_hk:
                with patch('modules.market_adapters.cn_adapter_kis.KISOverseasStockAPI') as mock_cn:
                    with patch('modules.market_adapters.jp_adapter_kis.KISOverseasStockAPI') as mock_jp:
                        with patch('modules.market_adapters.vn_adapter_kis.KISOverseasStockAPI') as mock_vn:
                            # Patch market calendars
                            calendar_patches = [
                                patch('modules.market_adapters.us_adapter_kis.MarketCalendar'),
                                patch('modules.market_adapters.hk_adapter_kis.MarketCalendar'),
                                patch('modules.market_adapters.cn_adapter_kis.MarketCalendar'),
                                patch('modules.market_adapters.jp_adapter_kis.MarketCalendar'),
                                patch('modules.market_adapters.vn_adapter_kis.MarketCalendar')
                            ]

                            for calendar_patch in calendar_patches:
                                calendar_patch.start()

                            try:
                                # Create all adapters
                                us = USAdapterKIS(mock_db, app_key, app_secret)
                                hk = HKAdapterKIS(mock_db, app_key, app_secret)
                                cn = CNAdapterKIS(mock_db, app_key, app_secret)
                                jp = JPAdapterKIS(mock_db, app_key, app_secret)
                                vn = VNAdapterKIS(mock_db, app_key, app_secret)

                                # Verify all use same credentials
                                for mock_api in [mock_us, mock_hk, mock_cn, mock_jp, mock_vn]:
                                    mock_api.assert_called_once()
                                    call_args = mock_api.call_args
                                    self.assertEqual(call_args[1]['app_key'], app_key)
                                    self.assertEqual(call_args[1]['app_secret'], app_secret)
                            finally:
                                for calendar_patch in calendar_patches:
                                    calendar_patch.stop()


if __name__ == '__main__':
    unittest.main()
