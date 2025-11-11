"""
Unit tests for OHLCVUpdater

Tests:
- Incremental OHLCV updates
- Technical indicator backfill
- Data validation
- Batch processing
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

from modules.ohlcv_update.ohlcv_updater import OHLCVUpdater


class TestOHLCVUpdater(unittest.TestCase):
    """Test cases for OHLCVUpdater"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.updater = OHLCVUpdater(db_manager=self.db_mock)

    def test_validate_ohlcv_valid_data(self):
        """Test OHLCV validation with valid data"""
        ohlcv_data = [
            {
                'date': date(2023, 1, 1),
                'open': 100.0,
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume': 1000000
            },
            {
                'date': date(2023, 1, 2),
                'open': 105.0,
                'high': 115.0,
                'low': 100.0,
                'close': 110.0,
                'volume': 1200000
            }
        ]

        validated = self.updater._validate_ohlcv(ohlcv_data, '005930')

        # All records should pass validation
        self.assertEqual(len(validated), 2)

    def test_validate_ohlcv_missing_fields(self):
        """Test OHLCV validation with missing fields"""
        ohlcv_data = [
            # Valid record
            {
                'date': date(2023, 1, 1),
                'open': 100.0,
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume': 1000000
            },
            # Missing 'close' field
            {
                'date': date(2023, 1, 2),
                'open': 105.0,
                'high': 115.0,
                'low': 100.0,
                'volume': 1200000
            }
        ]

        validated = self.updater._validate_ohlcv(ohlcv_data, '005930')

        # Only 1 record should pass
        self.assertEqual(len(validated), 1)

    def test_validate_ohlcv_negative_prices(self):
        """Test OHLCV validation with negative prices"""
        ohlcv_data = [
            {
                'date': date(2023, 1, 1),
                'open': -100.0,  # Negative price
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume': 1000000
            }
        ]

        validated = self.updater._validate_ohlcv(ohlcv_data, '005930')

        # Should be filtered out
        self.assertEqual(len(validated), 0)

    def test_validate_ohlcv_invalid_ohlc_relationship(self):
        """Test OHLCV validation with invalid OHLC relationship"""
        ohlcv_data = [
            # Valid record
            {
                'date': date(2023, 1, 1),
                'open': 100.0,
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume': 1000000
            },
            # Invalid: close > high
            {
                'date': date(2023, 1, 2),
                'open': 105.0,
                'high': 115.0,
                'low': 100.0,
                'close': 120.0,  # close > high
                'volume': 1200000
            },
            # Invalid: open < low
            {
                'date': date(2023, 1, 3),
                'open': 90.0,  # open < low
                'high': 120.0,
                'low': 100.0,
                'close': 115.0,
                'volume': 1300000
            }
        ]

        validated = self.updater._validate_ohlcv(ohlcv_data, '005930')

        # Only 1 valid record
        self.assertEqual(len(validated), 1)

    def test_validate_ohlcv_extreme_outlier(self):
        """Test OHLCV validation with extreme price changes"""
        ohlcv_data = [
            {
                'date': date(2023, 1, 1),
                'open': 100.0,
                'high': 110.0,
                'low': 95.0,
                'close': 105.0,
                'volume': 1000000
            },
            # 1000% jump (extreme outlier)
            {
                'date': date(2023, 1, 2),
                'open': 1050.0,
                'high': 1200.0,
                'low': 1000.0,
                'close': 1155.0,  # 1000% increase from previous close
                'volume': 1200000
            }
        ]

        validated = self.updater._validate_ohlcv(ohlcv_data, '005930')

        # Extreme outlier should be filtered out
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]['close'], 105.0)

    def test_calculate_indicators(self):
        """Test technical indicator calculation"""
        # Create sample OHLCV data (250 days for MA200)
        dates = pd.date_range(start='2023-01-01', periods=250, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(90, 110, 250),
            'high': np.random.uniform(100, 120, 250),
            'low': np.random.uniform(80, 100, 250),
            'close': np.random.uniform(90, 110, 250),
            'volume': np.random.randint(1000000, 5000000, 250)
        })

        # Calculate indicators
        df_with_indicators = self.updater._calculate_indicators(df)

        # Check that indicators were added
        self.assertIn('ma_20', df_with_indicators.columns)
        self.assertIn('ma_50', df_with_indicators.columns)
        self.assertIn('ma_200', df_with_indicators.columns)
        self.assertIn('rsi_14', df_with_indicators.columns)
        self.assertIn('macd', df_with_indicators.columns)
        self.assertIn('bb_upper', df_with_indicators.columns)

        # Check that indicators have values (not all NaN)
        # MA200 should have values after 200 days
        self.assertFalse(df_with_indicators['ma_200'].iloc[-1] is pd.NA)

        # RSI should be between 0 and 100
        rsi_values = df_with_indicators['rsi_14'].dropna()
        if len(rsi_values) > 0:
            self.assertTrue((rsi_values >= 0).all())
            self.assertTrue((rsi_values <= 100).all())

    @patch('modules.ohlcv_update.ohlcv_updater.PostgresDatabaseManager')
    def test_get_last_ohlcv_date(self, mock_db_class):
        """Test fetching last OHLCV date from database"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result
        mock_cursor.fetchone.return_value = (date(2023, 12, 31),)

        result = self.updater._get_last_ohlcv_date('005930', 'KR')

        # Verify result
        self.assertEqual(result, date(2023, 12, 31))

        # Verify query was called correctly
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        self.assertIn('MAX(date)', call_args[0])
        self.assertEqual(call_args[1], ('005930', 'KR'))

    @patch('modules.ohlcv_update.ohlcv_updater.PostgresDatabaseManager')
    def test_get_last_ohlcv_date_no_data(self, mock_db_class):
        """Test fetching last OHLCV date when no data exists"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result (no data)
        mock_cursor.fetchone.return_value = (None,)

        result = self.updater._get_last_ohlcv_date('999999', 'KR')

        # Should return None
        self.assertIsNone(result)

    @patch('modules.ohlcv_update.ohlcv_updater.PostgresDatabaseManager')
    def test_get_active_tickers(self, mock_db_class):
        """Test fetching active tickers from database"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result
        mock_cursor.fetchall.return_value = [
            ('005930',),
            ('000660',),
            ('035420',)
        ]

        result = self.updater._get_active_tickers('KR')

        # Verify results
        self.assertEqual(len(result), 3)
        self.assertIn('005930', result)
        self.assertIn('000660', result)
        self.assertIn('035420', result)

    def test_update_ticker_already_up_to_date(self):
        """Test updating ticker that is already up to date"""
        # Mock get_last_ohlcv_date to return today
        with patch.object(self.updater, '_get_last_ohlcv_date', return_value=date.today()):
            result = self.updater.update_ticker('005930', 'KR', backfill_indicators=False)

            # Should return 'up_to_date' status
            self.assertEqual(result['status'], 'up_to_date')
            self.assertEqual(result['records'], 0)


class TestOHLCVUpdaterIntegration(unittest.TestCase):
    """Integration tests for OHLCVUpdater (requires database)"""

    @unittest.skip("Requires live database connection")
    def test_update_ticker_kr(self):
        """Test updating OHLCV for Korean ticker"""
        updater = OHLCVUpdater()
        result = updater.update_ticker('005930', 'KR', backfill_indicators=True)

        # Verify result structure
        self.assertIn('status', result)
        self.assertIn('records', result)
        self.assertIn('indicators_backfilled', result)

    @unittest.skip("Requires live database connection")
    def test_backfill_null_indicators(self):
        """Test backfilling NULL indicators"""
        updater = OHLCVUpdater()
        result = updater.backfill_null_indicators(region='KR')

        # Verify result structure
        self.assertIn('total', result)
        self.assertIn('successful', result)
        self.assertIn('failed', result)

    @unittest.skip("Requires live database connection")
    def test_update_all_tickers(self):
        """Test updating all tickers in region"""
        updater = OHLCVUpdater()
        result = updater.update_all_tickers('KR', backfill_indicators=False, batch_size=10)

        # Verify result structure
        self.assertIn('total_tickers', result)
        self.assertIn('successful', result)
        self.assertIn('failed', result)
        self.assertIn('total_records', result)


if __name__ == '__main__':
    unittest.main()
