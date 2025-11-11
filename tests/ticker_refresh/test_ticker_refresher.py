"""
Unit tests for TickerRefresher

Tests:
- Multi-region ticker refresh
- OTC filtering
- Ticker validation
- Change detection (new, updated, delisted)
- Database operations
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from typing import Dict, List

from modules.ticker_refresh.ticker_refresher import TickerRefresher, TickerChange


class TestTickerRefresher(unittest.TestCase):
    """Test cases for TickerRefresher"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.refresher = TickerRefresher(db_manager=self.db_mock)

    def test_supported_regions(self):
        """Test that all supported regions are defined"""
        expected_regions = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']
        self.assertEqual(self.refresher.SUPPORTED_REGIONS, expected_regions)

    def test_valid_asset_types(self):
        """Test that only STOCK and ETF are valid"""
        expected_types = ['STOCK', 'ETF']
        self.assertEqual(self.refresher.VALID_ASSET_TYPES, expected_types)

    def test_is_otc_ticker_us(self):
        """Test OTC detection for US market"""
        # OTC by exchange
        otc_ticker1 = {'ticker': 'ABCD', 'exchange': 'OTCMKTS'}
        self.assertTrue(self.refresher._is_otc_ticker(otc_ticker1, 'US'))

        # OTC by suffix
        otc_ticker2 = {'ticker': 'ABCD.PK', 'exchange': 'NASDAQ'}
        self.assertTrue(self.refresher._is_otc_ticker(otc_ticker2, 'US'))

        # Not OTC
        valid_ticker = {'ticker': 'AAPL', 'exchange': 'NASDAQ'}
        self.assertFalse(self.refresher._is_otc_ticker(valid_ticker, 'US'))

    def test_is_valid_ticker_symbol_kr(self):
        """Test ticker symbol validation for Korean market"""
        # Valid KR ticker (6 digits)
        self.assertTrue(self.refresher._is_valid_ticker_symbol('005930', 'KR'))

        # Invalid KR tickers
        self.assertFalse(self.refresher._is_valid_ticker_symbol('00593', 'KR'))  # Too short
        self.assertFalse(self.refresher._is_valid_ticker_symbol('0059301', 'KR'))  # Too long
        self.assertFalse(self.refresher._is_valid_ticker_symbol('ABCD', 'KR'))  # Not digits

    def test_is_valid_ticker_symbol_us(self):
        """Test ticker symbol validation for US market"""
        # Valid US tickers
        self.assertTrue(self.refresher._is_valid_ticker_symbol('AAPL', 'US'))
        self.assertTrue(self.refresher._is_valid_ticker_symbol('A', 'US'))
        self.assertTrue(self.refresher._is_valid_ticker_symbol('GOOGL', 'US'))

        # Invalid US tickers
        self.assertFalse(self.refresher._is_valid_ticker_symbol('ABCDEF', 'US'))  # Too long
        self.assertFalse(self.refresher._is_valid_ticker_symbol('123', 'US'))  # Not letters
        self.assertFalse(self.refresher._is_valid_ticker_symbol('aapl', 'US'))  # Not uppercase

    def test_validate_tickers(self):
        """Test ticker validation and filtering"""
        raw_tickers = [
            # Valid stock
            {'ticker': '005930', 'asset_type': 'STOCK', 'exchange': 'KSE'},

            # Valid ETF
            {'ticker': '091160', 'asset_type': 'ETF', 'exchange': 'KSE'},

            # Invalid asset type
            {'ticker': '123456', 'asset_type': 'BOND', 'exchange': 'KSE'},

            # OTC ticker (US)
            {'ticker': 'ABCD', 'asset_type': 'STOCK', 'exchange': 'OTCMKTS'},

            # Invalid ticker symbol
            {'ticker': 'ABC', 'asset_type': 'STOCK', 'exchange': 'KSE'},
        ]

        valid_tickers = self.refresher._validate_tickers(raw_tickers, 'KR')

        # Should only have 2 valid tickers
        self.assertEqual(len(valid_tickers), 2)
        self.assertEqual(valid_tickers[0]['ticker'], '005930')
        self.assertEqual(valid_tickers[1]['ticker'], '091160')

    def test_has_metadata_changed(self):
        """Test metadata change detection"""
        # No change
        live_data = {'name': 'Samsung Electronics', 'exchange': 'KSE', 'asset_type': 'STOCK'}
        db_data = {'name': 'Samsung Electronics', 'exchange': 'KSE', 'asset_type': 'STOCK'}
        self.assertFalse(self.refresher._has_metadata_changed(live_data, db_data))

        # Name changed
        live_data = {'name': 'Samsung Electronics Co., Ltd.', 'exchange': 'KSE', 'asset_type': 'STOCK'}
        db_data = {'name': 'Samsung Electronics', 'exchange': 'KSE', 'asset_type': 'STOCK'}
        self.assertTrue(self.refresher._has_metadata_changed(live_data, db_data))

        # Exchange changed
        live_data = {'name': 'Samsung Electronics', 'exchange': 'KOSDAQ', 'asset_type': 'STOCK'}
        db_data = {'name': 'Samsung Electronics', 'exchange': 'KSE', 'asset_type': 'STOCK'}
        self.assertTrue(self.refresher._has_metadata_changed(live_data, db_data))

    def test_detect_changes(self):
        """Test change detection (new, updated, delisted)"""
        # Live tickers
        valid_tickers = [
            # New ticker
            {'ticker': '000001', 'name': 'New Company', 'exchange': 'KSE', 'asset_type': 'STOCK'},

            # Updated ticker (name changed)
            {'ticker': '000002', 'name': 'Updated Company Name', 'exchange': 'KSE', 'asset_type': 'STOCK'},

            # Unchanged ticker
            {'ticker': '000003', 'name': 'Same Company', 'exchange': 'KSE', 'asset_type': 'STOCK'},
        ]

        # Existing tickers in database
        existing_tickers = {
            '000002': {
                'ticker': '000002',
                'name': 'Old Company Name',
                'exchange': 'KSE',
                'asset_type': 'STOCK',
                'status': 'active'
            },
            '000003': {
                'ticker': '000003',
                'name': 'Same Company',
                'exchange': 'KSE',
                'asset_type': 'STOCK',
                'status': 'active'
            },
            # Delisted ticker
            '000004': {
                'ticker': '000004',
                'name': 'Delisted Company',
                'exchange': 'KSE',
                'asset_type': 'STOCK',
                'status': 'active'
            }
        }

        changes = self.refresher._detect_changes(valid_tickers, existing_tickers, 'KR')

        # Should have 3 changes: 1 new, 1 updated, 1 delisted
        self.assertEqual(len(changes), 3)

        change_types = {change.ticker: change.change_type for change in changes}
        self.assertEqual(change_types['000001'], 'new')
        self.assertEqual(change_types['000002'], 'updated')
        self.assertEqual(change_types['000004'], 'delisted')

    @patch('modules.ticker_refresh.ticker_refresher.PostgresDatabaseManager')
    def test_get_existing_tickers(self, mock_db_class):
        """Test fetching existing tickers from database"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result
        mock_cursor.fetchall.return_value = [
            ('005930', 'Samsung Electronics', 'STOCK', 'KSE', 'active', date(2000, 1, 1), None, datetime.now()),
            ('091160', 'TIGER 200', 'ETF', 'KSE', 'active', date(2010, 1, 1), None, datetime.now())
        ]

        result = self.refresher._get_existing_tickers('KR')

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertIn('005930', result)
        self.assertEqual(result['005930']['name'], 'Samsung Electronics')
        self.assertEqual(result['005930']['asset_type'], 'STOCK')

    def test_ticker_change_dataclass(self):
        """Test TickerChange dataclass"""
        change = TickerChange(
            ticker='005930',
            region='KR',
            change_type='new',
            metadata={'name': 'Samsung', 'exchange': 'KSE'},
            timestamp=datetime.now()
        )

        self.assertEqual(change.ticker, '005930')
        self.assertEqual(change.region, 'KR')
        self.assertEqual(change.change_type, 'new')
        self.assertEqual(change.metadata['name'], 'Samsung')


class TestTickerRefresherIntegration(unittest.TestCase):
    """Integration tests for TickerRefresher (requires database)"""

    @unittest.skip("Requires live database connection")
    def test_refresh_region_kr(self):
        """Test full refresh workflow for Korean region"""
        refresher = TickerRefresher()
        result = refresher.refresh_region('KR', incremental=True)

        # Verify result structure
        self.assertIn('new', result)
        self.assertIn('updated', result)
        self.assertIn('delisted', result)
        self.assertIn('errors', result)

    @unittest.skip("Requires live database connection")
    def test_refresh_all_regions(self):
        """Test refreshing all supported regions"""
        refresher = TickerRefresher()
        results = refresher.refresh_all_regions(incremental=True)

        # Should have results for all regions
        for region in refresher.SUPPORTED_REGIONS:
            self.assertIn(region, results)


if __name__ == '__main__':
    unittest.main()
