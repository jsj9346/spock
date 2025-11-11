"""
Unit tests for FXTracker

Tests:
- Exchange rate fetching and storage
- FX signal generation (rapid moves, volatility)
- Region-specific currency mapping
- INSERT ... ON CONFLICT DO NOTHING strategy
- API client integration

Author: Spock Quant Platform
Date: 2025-11-05
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
from decimal import Decimal

from modules.fx_tracking.fx_tracker import FXTracker


class TestFXTracker(unittest.TestCase):
    """Test cases for FXTracker"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_mock = Mock()
        self.tracker = FXTracker(db_manager=self.db_mock, base_currency='KRW')

    def test_get_currencies_for_regions_kr(self):
        """Test currency mapping for KR region"""
        currencies = FXTracker.get_currencies_for_regions(['KR'])

        # Should return KR-relevant currencies
        expected_currencies = {'USD', 'JPY', 'CNY', 'EUR'}
        self.assertEqual(set(currencies), expected_currencies)

    def test_get_currencies_for_regions_multiple(self):
        """Test currency mapping for multiple regions"""
        currencies = FXTracker.get_currencies_for_regions(['KR', 'US'])

        # Should return union of currencies
        expected_currencies = {'USD', 'JPY', 'CNY', 'EUR', 'KRW', 'GBP'}
        self.assertEqual(set(currencies), expected_currencies)

    def test_get_currencies_for_regions_all(self):
        """Test currency mapping for all supported regions"""
        regions = ['KR', 'US', 'JP', 'CN', 'HK', 'VN']
        currencies = FXTracker.get_currencies_for_regions(regions)

        # Should return comprehensive currency list
        self.assertGreater(len(currencies), 5)
        self.assertIn('USD', currencies)
        self.assertIn('JPY', currencies)
        self.assertIn('EUR', currencies)

    def test_fetch_rates_mock(self):
        """Test fetching exchange rates (mock mode)"""
        currencies = ['USD', 'JPY', 'EUR']

        # Should use mock rates when API unavailable
        rates = self.tracker._fetch_rates(currencies)

        # Verify mock rates returned
        self.assertEqual(len(rates), 3)
        self.assertIn('USD', rates)
        self.assertIn('JPY', rates)
        self.assertIn('EUR', rates)

        # Verify rates are Decimal type
        self.assertIsInstance(rates['USD'], Decimal)
        self.assertGreater(rates['USD'], 0)

    def test_get_mock_rates(self):
        """Test mock rate generation"""
        currencies = ['USD', 'JPY', 'EUR', 'CNY']

        rates = self.tracker._get_mock_rates(currencies)

        # Verify all requested currencies have rates
        self.assertEqual(len(rates), 4)
        for currency in currencies:
            self.assertIn(currency, rates)
            self.assertIsInstance(rates[currency], Decimal)
            self.assertGreater(rates[currency], 0)

    def test_insert_rates_batch(self):
        """Test batch insert of exchange rates"""
        rates = {
            'USD': Decimal('1350.50'),
            'JPY': Decimal('10.25'),
            'EUR': Decimal('1450.75')
        }

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_cursor.rowcount = 3

        self.db_mock.get_connection.return_value = mock_conn

        # Insert rates
        inserted = self.tracker._insert_rates(rates)

        # Verify batch insert was called
        mock_cursor.executemany.assert_called_once()

        # Verify INSERT ... ON CONFLICT query
        call_args = mock_cursor.executemany.call_args[0]
        query = call_args[0]
        self.assertIn('INSERT INTO exchange_rates', query)
        self.assertIn('ON CONFLICT', query)
        self.assertIn('DO NOTHING', query)

        # Verify 3 values passed
        values = call_args[1]
        self.assertEqual(len(values), 3)

        # Verify inserted count
        self.assertEqual(inserted, 3)

    def test_insert_rates_empty(self):
        """Test insert with empty rates dict"""
        rates = {}

        inserted = self.tracker._insert_rates(rates)

        # Should return 0 without DB call
        self.assertEqual(inserted, 0)

    def test_insert_rates_no_db(self):
        """Test insert when database manager is None"""
        tracker_no_db = FXTracker(db_manager=None)

        rates = {'USD': Decimal('1350.50')}
        inserted = tracker_no_db._insert_rates(rates)

        # Should return 0 gracefully
        self.assertEqual(inserted, 0)

    def test_calculate_signals_rapid_appreciation(self):
        """Test FX signal for rapid appreciation (>2%)"""
        current_rates = {
            'USD': Decimal('1400.00')  # Up from 1350.50 (+3.7%)
        }

        # Mock previous rates
        with patch.object(self.tracker, '_get_previous_rates') as mock_prev:
            mock_prev.return_value = {'USD': Decimal('1350.50')}

            # Mock volatility detection
            with patch.object(self.tracker, '_detect_high_volatility') as mock_vol:
                mock_vol.return_value = []

                signals = self.tracker._calculate_signals(current_rates)

                # Should detect rapid appreciation
                self.assertEqual(len(signals), 1)
                self.assertEqual(signals[0]['currency'], 'USD')
                self.assertEqual(signals[0]['signal_type'], 'rapid_appreciation')
                self.assertGreater(signals[0]['magnitude'], 0.02)

    def test_calculate_signals_rapid_depreciation(self):
        """Test FX signal for rapid depreciation (>2%)"""
        current_rates = {
            'JPY': Decimal('9.50')  # Down from 10.25 (-7.3%)
        }

        # Mock previous rates
        with patch.object(self.tracker, '_get_previous_rates') as mock_prev:
            mock_prev.return_value = {'JPY': Decimal('10.25')}

            # Mock volatility detection
            with patch.object(self.tracker, '_detect_high_volatility') as mock_vol:
                mock_vol.return_value = []

                signals = self.tracker._calculate_signals(current_rates)

                # Should detect rapid depreciation
                self.assertEqual(len(signals), 1)
                self.assertEqual(signals[0]['currency'], 'JPY')
                self.assertEqual(signals[0]['signal_type'], 'rapid_depreciation')
                self.assertGreater(signals[0]['magnitude'], 0.02)

    def test_calculate_signals_no_change(self):
        """Test FX signal with minimal change (<2%)"""
        current_rates = {
            'EUR': Decimal('1460.00')  # Up from 1450.75 (+0.6%)
        }

        # Mock previous rates
        with patch.object(self.tracker, '_get_previous_rates') as mock_prev:
            mock_prev.return_value = {'EUR': Decimal('1450.75')}

            # Mock volatility detection
            with patch.object(self.tracker, '_detect_high_volatility') as mock_vol:
                mock_vol.return_value = []

                signals = self.tracker._calculate_signals(current_rates)

                # Should not detect any signal (< 2% threshold)
                self.assertEqual(len(signals), 0)

    def test_calculate_signals_no_previous_data(self):
        """Test FX signal calculation with no previous rates"""
        current_rates = {
            'USD': Decimal('1350.50')
        }

        # Mock empty previous rates
        with patch.object(self.tracker, '_get_previous_rates') as mock_prev:
            mock_prev.return_value = {}

            # Mock volatility detection
            with patch.object(self.tracker, '_detect_high_volatility') as mock_vol:
                mock_vol.return_value = []

                signals = self.tracker._calculate_signals(current_rates)

                # Should return empty list (no comparison possible)
                self.assertEqual(len(signals), 0)

    def test_update_exchange_rates_success(self):
        """Test successful exchange rate update workflow"""
        currencies = ['USD', 'JPY', 'EUR']

        # Mock fetch rates
        with patch.object(self.tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1350.50'),
                'JPY': Decimal('10.25'),
                'EUR': Decimal('1450.75')
            }

            # Mock insert rates
            with patch.object(self.tracker, '_insert_rates') as mock_insert:
                mock_insert.return_value = 3

                # Mock calculate signals
                with patch.object(self.tracker, '_calculate_signals') as mock_signals:
                    mock_signals.return_value = []

                    result = self.tracker.update_exchange_rates(
                        currencies=currencies,
                        dry_run=False
                    )

                    # Verify success
                    self.assertTrue(result['success'])
                    self.assertEqual(result['updated'], 3)
                    self.assertEqual(result['signals'], 0)
                    self.assertIn('rates', result)

    def test_update_exchange_rates_dry_run(self):
        """Test exchange rate update with dry_run=True"""
        currencies = ['USD', 'JPY']

        # Mock fetch rates
        with patch.object(self.tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1350.50'),
                'JPY': Decimal('10.25')
            }

            # Mock calculate signals
            with patch.object(self.tracker, '_calculate_signals') as mock_signals:
                mock_signals.return_value = []

                result = self.tracker.update_exchange_rates(
                    currencies=currencies,
                    dry_run=True
                )

                # Should not call _insert_rates
                # (no way to verify with mock, but logged)
                self.assertTrue(result['success'])
                self.assertEqual(result['updated'], 0)  # No insert in dry run
                self.assertIn('rates', result)

    def test_update_exchange_rates_empty_fetch(self):
        """Test exchange rate update when fetch returns empty"""
        currencies = ['USD', 'JPY']

        # Mock empty fetch
        with patch.object(self.tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {}

            result = self.tracker.update_exchange_rates(
                currencies=currencies,
                dry_run=False
            )

            # Should return failure
            self.assertFalse(result['success'])
            self.assertEqual(result['updated'], 0)
            self.assertEqual(result['signals'], 0)

    def test_get_previous_rates_db_query(self):
        """Test fetching previous rates from database"""
        currencies = ['USD', 'JPY']

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        self.db_mock.get_connection.return_value = mock_conn

        # Mock query result
        mock_cursor.fetchall.return_value = [
            ('USD', 1350.50),
            ('JPY', 10.25)
        ]

        result = self.tracker._get_previous_rates(currencies)

        # Verify query was called
        mock_cursor.execute.assert_called_once()

        # Verify results
        self.assertEqual(len(result), 2)
        self.assertIn('USD', result)
        self.assertEqual(result['USD'], Decimal('1350.50'))

    def test_insert_fx_signals_success(self):
        """Test inserting FX signals into database"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.025,
                'current_rate': 1400.00,
                'previous_rate': 1350.50,
                'date': date.today()
            },
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.073,
                'current_rate': 9.50,
                'previous_rate': 10.25,
                'date': date.today()
            }
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_cursor.rowcount = 1  # Each signal inserts 1 row

        # Mock duplicate check (no duplicates)
        mock_cursor.fetchone.return_value = (0,)

        self.db_mock._get_connection.return_value = mock_conn

        # Insert signals
        inserted = self.tracker._insert_fx_signals(signals)

        # Verify duplicate check was called for each signal
        self.assertEqual(mock_cursor.execute.call_count, 4)  # 2 checks + 2 inserts

        # Verify INSERT query
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT INTO fx_signals' in str(call)]
        self.assertEqual(len(insert_calls), 2)

        # Verify inserted count
        self.assertEqual(inserted, 2)

    def test_insert_fx_signals_duplicate_skip(self):
        """Test skipping duplicate FX signals"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.025,
                'current_rate': 1400.00,
                'previous_rate': 1350.50,
                'date': date.today()
            }
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        # Mock duplicate check (found duplicate)
        mock_cursor.fetchone.return_value = (1,)

        self.db_mock._get_connection.return_value = mock_conn

        # Insert signals
        inserted = self.tracker._insert_fx_signals(signals)

        # Should skip duplicate signal (no INSERT called)
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT INTO fx_signals' in str(call)]
        self.assertEqual(len(insert_calls), 0)

        # Verify inserted count is 0
        self.assertEqual(inserted, 0)

    def test_insert_fx_signals_partial_duplicate(self):
        """Test inserting FX signals with some duplicates"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.025,
                'current_rate': 1400.00,
                'previous_rate': 1350.50,
                'date': date.today()
            },
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.073,
                'current_rate': 9.50,
                'previous_rate': 10.25,
                'date': date.today()
            }
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_cursor.rowcount = 1

        # Mock duplicate check: first is duplicate, second is new
        mock_cursor.fetchone.side_effect = [(1,), (0,)]

        self.db_mock._get_connection.return_value = mock_conn

        # Insert signals
        inserted = self.tracker._insert_fx_signals(signals)

        # Should insert only 1 signal (second one)
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT INTO fx_signals' in str(call)]
        self.assertEqual(len(insert_calls), 1)

        # Verify inserted count
        self.assertEqual(inserted, 1)

    def test_insert_fx_signals_high_volatility(self):
        """Test inserting high volatility signal (no current_rate/previous_rate)"""
        signals = [
            {
                'currency': 'EUR',
                'signal_type': 'high_volatility',
                'magnitude': 0.018,
                'date': date.today()
            }
        ]

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_cursor.rowcount = 1

        # Mock duplicate check (no duplicates)
        mock_cursor.fetchone.return_value = (0,)

        self.db_mock._get_connection.return_value = mock_conn

        # Insert signals
        inserted = self.tracker._insert_fx_signals(signals)

        # Verify INSERT was called
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT INTO fx_signals' in str(call)]
        self.assertEqual(len(insert_calls), 1)

        # Verify None values for current_rate/previous_rate
        insert_args = insert_calls[0][0][1]  # Second argument (values tuple)
        self.assertIsNone(insert_args[3])  # current_rate should be None
        self.assertIsNone(insert_args[4])  # previous_rate should be None

        # Verify inserted count
        self.assertEqual(inserted, 1)

    def test_insert_fx_signals_empty_list(self):
        """Test inserting empty signal list"""
        signals = []

        inserted = self.tracker._insert_fx_signals(signals)

        # Should return 0 without DB call
        self.assertEqual(inserted, 0)

    def test_insert_fx_signals_no_db(self):
        """Test inserting signals when database manager is None"""
        tracker_no_db = FXTracker(db_manager=None)

        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.025,
                'current_rate': 1400.00,
                'previous_rate': 1350.50,
                'date': date.today()
            }
        ]

        inserted = tracker_no_db._insert_fx_signals(signals)

        # Should return 0 gracefully
        self.assertEqual(inserted, 0)

    def test_update_exchange_rates_with_signals_insertion(self):
        """Test exchange rate update with signal insertion"""
        currencies = ['USD', 'JPY']

        # Mock fetch rates
        with patch.object(self.tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1400.00'),
                'JPY': Decimal('9.50')
            }

            # Mock insert rates
            with patch.object(self.tracker, '_insert_rates') as mock_insert:
                mock_insert.return_value = 2

                # Mock calculate signals
                with patch.object(self.tracker, '_calculate_signals') as mock_signals:
                    mock_signals.return_value = [
                        {
                            'currency': 'USD',
                            'signal_type': 'rapid_appreciation',
                            'magnitude': 0.025,
                            'current_rate': 1400.00,
                            'previous_rate': 1350.50,
                            'date': date.today()
                        }
                    ]

                    # Mock insert signals
                    with patch.object(self.tracker, '_insert_fx_signals') as mock_insert_signals:
                        mock_insert_signals.return_value = 1

                        result = self.tracker.update_exchange_rates(
                            currencies=currencies,
                            dry_run=False
                        )

                        # Verify success
                        self.assertTrue(result['success'])
                        self.assertEqual(result['updated'], 2)
                        self.assertEqual(result['signals'], 1)
                        self.assertEqual(result['signals_inserted'], 1)

                        # Verify signal insertion was called
                        mock_insert_signals.assert_called_once()

    def test_update_exchange_rates_dry_run_no_signals_insertion(self):
        """Test dry_run mode should not insert signals"""
        currencies = ['USD']

        # Mock fetch rates
        with patch.object(self.tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1400.00')
            }

            # Mock calculate signals
            with patch.object(self.tracker, '_calculate_signals') as mock_signals:
                mock_signals.return_value = [
                    {
                        'currency': 'USD',
                        'signal_type': 'rapid_appreciation',
                        'magnitude': 0.025,
                        'current_rate': 1400.00,
                        'previous_rate': 1350.50,
                        'date': date.today()
                    }
                ]

                # Mock insert signals (should not be called)
                with patch.object(self.tracker, '_insert_fx_signals') as mock_insert_signals:
                    result = self.tracker.update_exchange_rates(
                        currencies=currencies,
                        dry_run=True
                    )

                    # Verify no signal insertion in dry_run mode
                    mock_insert_signals.assert_not_called()
                    self.assertEqual(result['signals_inserted'], 0)

    def test_notification_service_integration(self):
        """Test FXTracker integration with FXNotificationService"""
        # Create mock notification service
        mock_notifier = Mock()
        mock_notifier.notify_fx_signals.return_value = {
            'critical_sent': 1,
            'warning_queued': 0,
            'info_queued': 0,
            'spam_filtered': 0
        }

        # Create tracker with notification service
        tracker = FXTracker(
            db_manager=self.db_mock,
            notification_service=mock_notifier
        )

        currencies = ['USD']

        # Mock fetch rates
        with patch.object(tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1440.00')  # Up 6% from 1350.50
            }

            # Mock insert rates
            with patch.object(tracker, '_insert_rates') as mock_insert:
                mock_insert.return_value = 1

                # Mock calculate signals (CRITICAL signal)
                with patch.object(tracker, '_calculate_signals') as mock_signals:
                    critical_signal = {
                        'currency': 'USD',
                        'signal_type': 'rapid_appreciation',
                        'magnitude': 0.06,  # CRITICAL (≥5%)
                        'current_rate': 1440.00,
                        'previous_rate': 1350.50,
                        'date': date.today()
                    }
                    mock_signals.return_value = [critical_signal]

                    # Mock insert signals
                    with patch.object(tracker, '_insert_fx_signals') as mock_insert_signals:
                        mock_insert_signals.return_value = 1

                        result = tracker.update_exchange_rates(
                            currencies=currencies,
                            dry_run=False
                        )

                        # Verify notification service was called
                        mock_notifier.notify_fx_signals.assert_called_once()

                        # Verify notification result in response
                        self.assertIn('notifications', result)
                        self.assertEqual(result['notifications']['critical_sent'], 1)

    def test_notification_service_not_called_dry_run(self):
        """Test notification service is not called in dry_run mode"""
        # Create mock notification service
        mock_notifier = Mock()

        # Create tracker with notification service
        tracker = FXTracker(
            db_manager=self.db_mock,
            notification_service=mock_notifier
        )

        currencies = ['USD']

        # Mock fetch rates
        with patch.object(tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1440.00')
            }

            # Mock calculate signals
            with patch.object(tracker, '_calculate_signals') as mock_signals:
                mock_signals.return_value = [
                    {
                        'currency': 'USD',
                        'signal_type': 'rapid_appreciation',
                        'magnitude': 0.06,
                        'current_rate': 1440.00,
                        'previous_rate': 1350.50,
                        'date': date.today()
                    }
                ]

                result = tracker.update_exchange_rates(
                    currencies=currencies,
                    dry_run=True
                )

                # Verify notification service was NOT called in dry_run mode
                mock_notifier.notify_fx_signals.assert_not_called()

    def test_notification_service_not_called_no_signals(self):
        """Test notification service is not called when no signals generated"""
        # Create mock notification service
        mock_notifier = Mock()

        # Create tracker with notification service
        tracker = FXTracker(
            db_manager=self.db_mock,
            notification_service=mock_notifier
        )

        currencies = ['USD']

        # Mock fetch rates
        with patch.object(tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1355.00')  # Only +0.3% change
            }

            # Mock insert rates
            with patch.object(tracker, '_insert_rates') as mock_insert:
                mock_insert.return_value = 1

                # Mock calculate signals (no signals due to low change)
                with patch.object(tracker, '_calculate_signals') as mock_signals:
                    mock_signals.return_value = []  # No signals

                    # Mock insert signals
                    with patch.object(tracker, '_insert_fx_signals') as mock_insert_signals:
                        mock_insert_signals.return_value = 0

                        result = tracker.update_exchange_rates(
                            currencies=currencies,
                            dry_run=False
                        )

                        # Verify notification service was NOT called (no signals)
                        mock_notifier.notify_fx_signals.assert_not_called()

    def test_notification_service_optional(self):
        """Test FXTracker works without notification_service (backward compatibility)"""
        # Create tracker without notification service
        tracker = FXTracker(db_manager=self.db_mock)

        currencies = ['USD']

        # Mock fetch rates
        with patch.object(tracker, '_fetch_rates') as mock_fetch:
            mock_fetch.return_value = {
                'USD': Decimal('1440.00')
            }

            # Mock insert rates
            with patch.object(tracker, '_insert_rates') as mock_insert:
                mock_insert.return_value = 1

                # Mock calculate signals
                with patch.object(tracker, '_calculate_signals') as mock_signals:
                    mock_signals.return_value = [
                        {
                            'currency': 'USD',
                            'signal_type': 'rapid_appreciation',
                            'magnitude': 0.06,
                            'current_rate': 1440.00,
                            'previous_rate': 1350.50,
                            'date': date.today()
                        }
                    ]

                    # Mock insert signals
                    with patch.object(tracker, '_insert_fx_signals') as mock_insert_signals:
                        mock_insert_signals.return_value = 1

                        result = tracker.update_exchange_rates(
                            currencies=currencies,
                            dry_run=False
                        )

                        # Should succeed without notification service
                        self.assertTrue(result['success'])
                        self.assertEqual(result['signals'], 1)


class TestFXTrackerIntegration(unittest.TestCase):
    """Integration tests for FXTracker (requires database)"""

    @unittest.skip("Requires live database connection")
    def test_full_fx_update_kr(self):
        """Test full FX update workflow for KR region"""
        tracker = FXTracker()

        currencies = FXTracker.get_currencies_for_regions(['KR'])
        result = tracker.update_exchange_rates(currencies, dry_run=False)

        # Verify result structure
        self.assertIn('updated', result)
        self.assertIn('signals', result)
        self.assertIn('success', result)
        self.assertTrue(result['success'])


if __name__ == '__main__':
    unittest.main()
