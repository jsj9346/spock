"""
Integration tests for TickerRefresher + KRMarketAdapter

Tests the integration between TickerRefresher and KRMarketAdapter,
verifying that the components can work together correctly.

Focus:
- Import and instantiation
- Adapter lazy loading
- Method interface compatibility

Out of Scope (for this test):
- Full data fetching (requires API credentials and live data)
- Database operations (requires schema migration from SQLite to Postgres)

Author: Spock Quant Platform
Date: 2025-11-04
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.ticker_refresh.ticker_refresher import TickerRefresher
from modules.market_adapters.kr_adapter import KRMarketAdapter, KoreaAdapter


class TestTickerRefresherIntegration(unittest.TestCase):
    """Integration tests for TickerRefresher + KRMarketAdapter"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock database manager to avoid Postgres dependency
        self.mock_db = Mock()

    def test_import_kr_market_adapter(self):
        """Test 1: Verify KRMarketAdapter can be imported"""
        # Verify KRMarketAdapter exists and is alias for KoreaAdapter
        self.assertIsNotNone(KRMarketAdapter)
        self.assertEqual(KRMarketAdapter, KoreaAdapter)

    def test_kr_adapter_has_fetch_method(self):
        """Test 2: Verify KRMarketAdapter has fetch_kr_tickers method"""
        # Create mock adapter instance
        adapter = KRMarketAdapter(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Verify method exists
        self.assertTrue(hasattr(adapter, 'fetch_kr_tickers'))
        self.assertTrue(callable(adapter.fetch_kr_tickers))

    def test_ticker_refresher_instantiation(self):
        """Test 3: Verify TickerRefresher can be instantiated with KIS credentials"""
        # Create TickerRefresher with mocked database
        refresher = TickerRefresher(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Verify instantiation successful
        self.assertIsNotNone(refresher)
        self.assertEqual(refresher.db, self.mock_db)
        self.assertEqual(refresher.kis_app_key, 'test_key')
        self.assertEqual(refresher.kis_app_secret, 'test_secret')

    def test_ticker_refresher_lazy_adapter_loading(self):
        """Test 4: Verify TickerRefresher can lazy-load KR adapter"""
        # Create TickerRefresher
        refresher = TickerRefresher(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Verify adapter not loaded yet
        self.assertNotIn('KR', refresher._adapters)

        # Load KR adapter
        kr_adapter = refresher._get_adapter('KR')

        # Verify adapter loaded and is correct type
        self.assertIsNotNone(kr_adapter)
        self.assertIsInstance(kr_adapter, KoreaAdapter)
        self.assertIn('KR', refresher._adapters)

    def test_kr_adapter_integration_with_refresher(self):
        """Test 5: Verify KR adapter integrates correctly with TickerRefresher"""
        # Create TickerRefresher
        refresher = TickerRefresher(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Get KR adapter
        kr_adapter = refresher._get_adapter('KR')

        # Verify adapter properties
        self.assertEqual(kr_adapter.region_code, 'KR')
        self.assertEqual(kr_adapter.db, self.mock_db)

        # Verify adapter has required methods
        self.assertTrue(hasattr(kr_adapter, 'fetch_kr_tickers'))
        self.assertTrue(hasattr(kr_adapter, 'scan_stocks'))
        self.assertTrue(hasattr(kr_adapter, 'scan_etfs'))

    def test_fetch_kr_tickers_interface(self):
        """Test 6: Verify fetch_kr_tickers() has correct interface"""
        # Create mock adapter
        adapter = KRMarketAdapter(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Mock the underlying methods to avoid API calls
        with patch.object(adapter, 'scan_stocks') as mock_scan_stocks:
            with patch.object(adapter, 'scan_etfs') as mock_scan_etfs:
                # Setup mock returns
                mock_scan_stocks.return_value = [
                    {
                        'ticker': '005930',
                        'name': '삼성전자',
                        'asset_type': 'STOCK',
                        'exchange': 'KOSPI',
                        'region': 'KR'
                    }
                ]
                mock_scan_etfs.return_value = [
                    {
                        'ticker': '069500',
                        'name': 'KODEX 200',
                        'asset_type': 'ETF',
                        'exchange': 'KOSPI',
                        'region': 'KR'
                    }
                ]

                # Call fetch_kr_tickers
                tickers = adapter.fetch_kr_tickers()

                # Verify results
                self.assertIsInstance(tickers, list)
                self.assertEqual(len(tickers), 2)
                self.assertEqual(tickers[0]['ticker'], '005930')
                self.assertEqual(tickers[1]['ticker'], '069500')

                # Verify methods were called
                mock_scan_stocks.assert_called_once_with(force_refresh=False)
                mock_scan_etfs.assert_called_once_with(force_refresh=False)

    def test_ticker_refresher_fetch_live_tickers_integration(self):
        """Test 7: Verify TickerRefresher._fetch_live_tickers() calls adapter correctly"""
        # Create TickerRefresher
        refresher = TickerRefresher(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Mock the adapter and its methods
        mock_adapter = Mock()
        mock_adapter.fetch_kr_tickers.return_value = [
            {'ticker': '005930', 'name': '삼성전자', 'asset_type': 'STOCK'}
        ]

        # Replace _get_adapter to return our mock
        with patch.object(refresher, '_get_adapter', return_value=mock_adapter):
            # Call _fetch_live_tickers
            tickers = refresher._fetch_live_tickers('KR')

            # Verify results
            self.assertIsInstance(tickers, list)
            self.assertEqual(len(tickers), 1)
            self.assertEqual(tickers[0]['ticker'], '005930')

            # Verify adapter method was called
            mock_adapter.fetch_kr_tickers.assert_called_once()

    @patch.dict('os.environ', {
        'KIS_APP_KEY': 'test_key_from_env',
        'KIS_APP_SECRET': 'test_secret_from_env'
    })
    def test_ticker_refresher_loads_credentials_from_env(self):
        """Test 8: Verify TickerRefresher loads credentials from environment"""
        # Create TickerRefresher without explicit credentials
        refresher = TickerRefresher(db_manager=self.mock_db)

        # Verify credentials loaded from environment
        self.assertEqual(refresher.kis_app_key, 'test_key_from_env')
        self.assertEqual(refresher.kis_app_secret, 'test_secret_from_env')

    def test_kr_adapter_error_handling(self):
        """Test 9: Verify error handling when adapter methods fail"""
        # Create mock adapter
        adapter = KRMarketAdapter(
            db_manager=self.mock_db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )

        # Mock scan_stocks to raise exception
        with patch.object(adapter, 'scan_stocks', side_effect=Exception("API error")):
            with patch.object(adapter, 'scan_etfs', return_value=[]):
                # Call fetch_kr_tickers
                tickers = adapter.fetch_kr_tickers()

                # Should return empty list or partial results (not crash)
                self.assertIsInstance(tickers, list)

    def test_ticker_refresher_missing_credentials(self):
        """Test 10: Verify error handling when KIS credentials missing"""
        # Create TickerRefresher without credentials
        with patch.dict('os.environ', {}, clear=True):
            # Clear any loaded credentials
            refresher = TickerRefresher(db_manager=self.mock_db)
            refresher.kis_app_key = None
            refresher.kis_app_secret = None

            # Attempt to get KR adapter
            with self.assertRaises(ValueError) as context:
                refresher._get_adapter('KR')

            # Verify error message
            self.assertIn('KIS API credentials required', str(context.exception))


if __name__ == '__main__':
    unittest.main()
