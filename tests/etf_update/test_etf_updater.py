"""
Unit tests for ETFUpdater

Tests:
- ETF metadata fetching (KR, US)
- ETF holdings fetching (KR, US)
- Tracking error calculation
- Database UPSERT strategy (etf_details)
- Database DELETE+INSERT strategy (etf_holdings)
- Mock data fallback
- Error handling

Author: Spock Quant Platform
Date: 2025-11-04
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
from decimal import Decimal

from modules.etf_update.etf_updater import ETFUpdater


class TestETFUpdater(unittest.TestCase):
    """Test cases for ETFUpdater"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.updater = ETFUpdater(db_manager=self.db_mock)

    def test_fetch_etf_details_kr_mock(self):
        """Test KR ETF details fetching (mock mode)"""
        ticker = '069500'
        region = 'KR'

        result = self.updater._fetch_etf_details_kr(ticker)

        # Verify mock data returned
        self.assertIsNotNone(result)
        self.assertIn('aum', result)
        self.assertIn('ter', result)
        self.assertIn('holdings_count', result)
        self.assertIn('benchmark_index', result)
        self.assertEqual(result['benchmark_index'], 'KOSPI 200')

    def test_fetch_etf_details_us_mock(self):
        """Test US ETF details fetching (mock mode)"""
        ticker = 'SPY'
        region = 'US'

        result = self.updater._fetch_etf_details_us(ticker)

        # Verify data returned (may be real or mock depending on yfinance availability)
        self.assertIsNotNone(result)
        self.assertIn('aum', result)
        self.assertIn('ter', result)
        self.assertIn('benchmark_index', result)
        # Don't assert specific benchmark value as it may vary

    def test_get_mock_etf_details_kr(self):
        """Test mock ETF details generation (KR)"""
        ticker = '069500'
        region = 'KR'

        result = self.updater._get_mock_etf_details(ticker, region)

        # Verify KR mock data structure
        self.assertEqual(result['aum'], 1_000_000_000_000)
        self.assertEqual(result['ter'], 0.0015)
        self.assertEqual(result['holdings_count'], 30)
        self.assertIsInstance(result['inception_date'], date)

    def test_get_mock_etf_details_us(self):
        """Test mock ETF details generation (US)"""
        ticker = 'SPY'
        region = 'US'

        result = self.updater._get_mock_etf_details(ticker, region)

        # Verify US mock data structure
        self.assertEqual(result['aum'], 1_000_000_000)
        self.assertEqual(result['ter'], 0.0003)
        self.assertEqual(result['holdings_count'], 500)
        self.assertIsInstance(result['inception_date'], date)

    def test_fetch_etf_holdings_kr_mock(self):
        """Test KR ETF holdings fetching (mock mode)"""
        ticker = '069500'
        region = 'KR'

        result = self.updater._fetch_etf_holdings_kr(ticker)

        # Verify mock holdings returned
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn('constituent_ticker', result[0])
        self.assertIn('weight', result[0])
        self.assertEqual(result[0]['constituent_ticker'], '005930')

    def test_fetch_etf_holdings_us_mock(self):
        """Test US ETF holdings fetching (mock mode)"""
        ticker = 'SPY'
        region = 'US'

        result = self.updater._fetch_etf_holdings_us(ticker)

        # Verify mock holdings returned (yfinance has limited holdings API)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn('constituent_ticker', result[0])
        # yfinance fallback returns mock data
        self.assertEqual(result[0]['constituent_ticker'], 'AAPL')

    def test_get_mock_holdings_kr(self):
        """Test mock holdings generation (KR)"""
        ticker = '069500'
        region = 'KR'

        result = self.updater._get_mock_holdings(ticker, region)

        # Verify KR mock holdings structure
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['constituent_ticker'], '005930')
        self.assertEqual(result[0]['constituent_name'], '삼성전자')
        self.assertIsInstance(result[0]['weight'], float)
        self.assertIsInstance(result[0]['shares'], int)

    def test_get_mock_holdings_us(self):
        """Test mock holdings generation (US)"""
        ticker = 'SPY'
        region = 'US'

        result = self.updater._get_mock_holdings(ticker, region)

        # Verify US mock holdings structure
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]['constituent_ticker'], 'AAPL')
        self.assertIsInstance(result[0]['weight'], float)

    def test_calculate_tracking_errors_mock(self):
        """Test tracking error calculation (mock mode)"""
        ticker = '069500'
        region = 'KR'

        result = self.updater._calculate_tracking_errors(ticker, region)

        # Verify tracking errors returned
        self.assertIsNotNone(result)
        self.assertIn('te_20d', result)
        self.assertIn('te_60d', result)
        self.assertIn('te_120d', result)
        self.assertIn('te_250d', result)
        self.assertGreater(result['te_20d'], 0)

    def test_update_etf_details_upsert(self):
        """Test ETF details database UPSERT"""
        ticker = '069500'
        region = 'KR'
        details = {
            'aum': 1_000_000_000_000,
            'ter': 0.0015,
            'holdings_count': 30,
            'benchmark_index': 'KOSPI 200',
            'inception_date': date(2020, 1, 1)
        }

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Execute update
        self.updater._update_etf_details(ticker, region, details)

        # Verify UPSERT query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        self.assertIn('INSERT INTO etf_details', query)
        self.assertIn('ON CONFLICT (ticker, region)', query)
        self.assertIn('DO UPDATE SET', query)

        # Verify parameters
        self.assertEqual(params[0], ticker)
        self.assertEqual(params[1], region)
        self.assertEqual(params[2], 1_000_000_000_000)

        # Verify commit
        mock_conn.commit.assert_called_once()

    def test_update_etf_holdings_delete_insert(self):
        """Test ETF holdings database DELETE + INSERT"""
        ticker = '069500'
        region = 'KR'
        holdings = [
            {
                'constituent_ticker': '005930',
                'constituent_name': '삼성전자',
                'weight': 25.5,
                'shares': 100000,
                'market_value': 5_000_000_000
            },
            {
                'constituent_ticker': '000660',
                'constituent_name': 'SK하이닉스',
                'weight': 15.2,
                'shares': 50000,
                'market_value': 3_000_000_000
            }
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Execute update
        self.updater._update_etf_holdings(ticker, region, holdings)

        # Verify DELETE + INSERT queries
        self.assertEqual(mock_cursor.execute.call_count, 1)  # DELETE
        self.assertEqual(mock_cursor.executemany.call_count, 1)  # INSERT batch

        # Verify DELETE query
        delete_call = mock_cursor.execute.call_args[0]
        delete_query = delete_call[0]
        self.assertIn('DELETE FROM etf_holdings', delete_query)

        # Verify INSERT query
        insert_call = mock_cursor.executemany.call_args[0]
        insert_query = insert_call[0]
        insert_values = insert_call[1]

        self.assertIn('INSERT INTO etf_holdings', insert_query)
        self.assertEqual(len(insert_values), 2)

        # Verify commit
        mock_conn.commit.assert_called_once()

    def test_update_etf_holdings_empty(self):
        """Test update with empty holdings"""
        ticker = '069500'
        region = 'KR'
        holdings = []

        # Should return without DB call
        self.updater._update_etf_holdings(ticker, region, holdings)

        # No DB connection should be requested
        self.db_mock.get_connection.assert_not_called()

    def test_update_tracking_errors_upsert(self):
        """Test tracking errors database UPSERT"""
        ticker = '069500'
        region = 'KR'
        tracking_errors = {
            'te_20d': 0.0015,
            'te_60d': 0.0025,
            'te_120d': 0.0035,
            'te_250d': 0.0045
        }

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Execute update
        self.updater._update_tracking_errors(ticker, region, tracking_errors)

        # Verify UPSERT query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        self.assertIn('INSERT INTO etf_details', query)
        self.assertIn('ON CONFLICT (ticker, region)', query)
        self.assertIn('DO UPDATE SET', query)
        self.assertIn('te_20d', query)

        # Verify parameters
        self.assertEqual(params[0], ticker)
        self.assertEqual(params[1], region)
        self.assertEqual(params[2], 0.0015)

        # Verify commit
        mock_conn.commit.assert_called_once()

    def test_update_etf_data_success(self):
        """Test full ETF update workflow (success)"""
        tickers = ['069500', '252670']
        region = 'KR'

        # Mock fetch methods
        with patch.object(self.updater, '_fetch_etf_details') as mock_details:
            mock_details.return_value = {
                'aum': 1_000_000_000_000,
                'ter': 0.0015,
                'holdings_count': 30,
                'benchmark_index': 'KOSPI 200',
                'inception_date': date(2020, 1, 1)
            }

            with patch.object(self.updater, '_fetch_etf_holdings') as mock_holdings:
                mock_holdings.return_value = [
                    {'constituent_ticker': '005930', 'constituent_name': '삼성전자',
                     'weight': 25.5, 'shares': 100000, 'market_value': 5_000_000_000}
                ] * 10  # 10 holdings

                with patch.object(self.updater, '_calculate_tracking_errors') as mock_te:
                    mock_te.return_value = {
                        'te_20d': 0.0015, 'te_60d': 0.0025,
                        'te_120d': 0.0035, 'te_250d': 0.0045
                    }

                    with patch.object(self.updater, '_update_etf_details'):
                        with patch.object(self.updater, '_update_etf_holdings'):
                            with patch.object(self.updater, '_update_tracking_errors'):
                                result = self.updater.update_etf_data(
                                    region=region,
                                    tickers=tickers,
                                    dry_run=False
                                )

        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_details'], 2)
        self.assertEqual(result['updated_holdings'], 2)
        self.assertEqual(result['tracking_errors'], 2)
        self.assertEqual(len(result['errors']), 0)

    def test_update_etf_data_dry_run(self):
        """Test ETF update with dry_run=True"""
        tickers = ['069500']
        region = 'KR'

        # Mock fetch methods
        with patch.object(self.updater, '_fetch_etf_details') as mock_details:
            mock_details.return_value = {'aum': 1_000_000_000_000}

            with patch.object(self.updater, '_fetch_etf_holdings') as mock_holdings:
                mock_holdings.return_value = [
                    {'constituent_ticker': '005930', 'weight': 25.5}
                ] * 10

                with patch.object(self.updater, '_calculate_tracking_errors') as mock_te:
                    mock_te.return_value = {'te_20d': 0.0015}

                    result = self.updater.update_etf_data(
                        region=region,
                        tickers=tickers,
                        dry_run=True
                    )

        # Should not update database in dry run
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_details'], 0)
        self.assertEqual(result['updated_holdings'], 0)
        self.assertEqual(result['tracking_errors'], 0)

    def test_update_etf_data_insufficient_holdings(self):
        """Test ETF update with insufficient holdings"""
        tickers = ['069500']
        region = 'KR'

        # Mock fetch with insufficient holdings
        with patch.object(self.updater, '_fetch_etf_details') as mock_details:
            mock_details.return_value = {'aum': 1_000_000_000_000}

            with patch.object(self.updater, '_fetch_etf_holdings') as mock_holdings:
                mock_holdings.return_value = [
                    {'constituent_ticker': '005930', 'weight': 25.5}
                ] * 5  # Only 5 holdings (< MIN_HOLDINGS=10)

                with patch.object(self.updater, '_update_etf_details'):
                    with patch.object(self.updater, '_update_etf_holdings'):
                        with patch.object(self.updater, '_calculate_tracking_errors'):
                            result = self.updater.update_etf_data(
                                region=region,
                                tickers=tickers,
                                dry_run=False
                            )

        # Should report errors (insufficient holdings + mock protocol error)
        self.assertFalse(result['success'])
        self.assertGreaterEqual(len(result['errors']), 1)
        # Verify insufficient holdings error is reported
        errors_str = ' '.join(result['errors'])
        self.assertIn('Insufficient holdings', errors_str)

    def test_update_etf_data_no_metadata(self):
        """Test ETF update with no metadata"""
        tickers = ['069500']
        region = 'KR'

        # Mock fetch with no metadata
        with patch.object(self.updater, '_fetch_etf_details') as mock_details:
            mock_details.return_value = None

            result = self.updater.update_etf_data(
                region=region,
                tickers=tickers,
                dry_run=False
            )

        # Should report error for no metadata
        self.assertFalse(result['success'])
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('No metadata', result['errors'][0])

    def test_updater_with_no_db(self):
        """Test updater initialization without database"""
        updater_no_db = ETFUpdater(db_manager=None)

        # Should not fail
        self.assertIsNone(updater_no_db.db)

        # Tracking error calculation should return None
        result = updater_no_db._calculate_tracking_errors('069500', 'KR')
        self.assertIsNone(result)


class TestETFUpdaterIntegration(unittest.TestCase):
    """Integration tests for ETFUpdater (requires database)"""

    @unittest.skip("Requires live database connection")
    def test_full_etf_update_kr(self):
        """Test full ETF update workflow for KR region"""
        updater = ETFUpdater()

        tickers = ['069500', '252670']
        result = updater.update_etf_data(
            region='KR',
            tickers=tickers,
            dry_run=False
        )

        # Verify result structure
        self.assertIn('updated_details', result)
        self.assertIn('updated_holdings', result)
        self.assertIn('tracking_errors', result)
        self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main()
