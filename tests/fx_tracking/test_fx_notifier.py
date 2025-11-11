"""
Unit tests for FXNotificationService

Tests:
- Signal severity classification
- Spam filtering
- Quiet hours detection
- Message formatting
- Notification workflow

Author: Spock Quant Platform
Date: 2025-11-06
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, time
from decimal import Decimal

from modules.fx_tracking.fx_notifier import FXNotificationService, SignalSeverity


class TestFXNotificationService(unittest.TestCase):
    """Test cases for FXNotificationService"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock SNS notifier
        self.sns_mock = Mock()

        # Create notifier with mock config
        self.notifier = FXNotificationService(
            sns_notifier=self.sns_mock,
            config_path='nonexistent.yaml'  # Force default config
        )

    def test_classify_signals_critical(self):
        """Test CRITICAL severity classification (≥5% magnitude)"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,  # 6% > 5% threshold
                'current_rate': 1440.00,
                'previous_rate': 1350.00,
                'date': date.today()
            }
        ]

        classified = self.notifier._classify_signals(signals)

        # Should be CRITICAL
        self.assertEqual(len(classified['CRITICAL']), 1)
        self.assertEqual(len(classified['WARNING']), 0)
        self.assertEqual(len(classified['INFO']), 0)

    def test_classify_signals_warning(self):
        """Test WARNING severity classification (2-5% magnitude)"""
        signals = [
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.03,  # 3% in WARNING range (2-5%)
                'current_rate': 9.50,
                'previous_rate': 10.25,
                'date': date.today()
            }
        ]

        classified = self.notifier._classify_signals(signals)

        # Should be WARNING
        self.assertEqual(len(classified['CRITICAL']), 0)
        self.assertEqual(len(classified['WARNING']), 1)
        self.assertEqual(len(classified['INFO']), 0)

    def test_classify_signals_info(self):
        """Test INFO severity classification (1-2% magnitude)"""
        signals = [
            {
                'currency': 'EUR',
                'signal_type': 'high_volatility',
                'magnitude': 0.018,  # 1.8% in INFO range (1.5-2%)
                'date': date.today()
            }
        ]

        classified = self.notifier._classify_signals(signals)

        # Should be INFO
        self.assertEqual(len(classified['CRITICAL']), 0)
        self.assertEqual(len(classified['WARNING']), 0)
        self.assertEqual(len(classified['INFO']), 1)

    def test_classify_signals_mixed(self):
        """Test mixed severity classification"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,  # CRITICAL
                'current_rate': 1440.00,
                'previous_rate': 1350.00,
                'date': date.today()
            },
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.03,  # WARNING
                'current_rate': 9.50,
                'previous_rate': 10.25,
                'date': date.today()
            },
            {
                'currency': 'EUR',
                'signal_type': 'high_volatility',
                'magnitude': 0.018,  # INFO
                'date': date.today()
            }
        ]

        classified = self.notifier._classify_signals(signals)

        # Should have all three severities
        self.assertEqual(len(classified['CRITICAL']), 1)
        self.assertEqual(len(classified['WARNING']), 1)
        self.assertEqual(len(classified['INFO']), 1)

    def test_calculate_severity_rapid_move(self):
        """Test severity calculation for rapid move signals"""
        # CRITICAL (≥5%)
        signal_critical = {
            'signal_type': 'rapid_appreciation',
            'magnitude': 0.055
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_critical),
            SignalSeverity.CRITICAL
        )

        # WARNING (2-5%)
        signal_warning = {
            'signal_type': 'rapid_depreciation',
            'magnitude': 0.035
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_warning),
            SignalSeverity.WARNING
        )

        # INFO (<2%)
        signal_info = {
            'signal_type': 'rapid_appreciation',
            'magnitude': 0.015
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_info),
            SignalSeverity.INFO
        )

    def test_calculate_severity_volatility(self):
        """Test severity calculation for volatility signals"""
        # CRITICAL (≥3%)
        signal_critical = {
            'signal_type': 'high_volatility',
            'magnitude': 0.04
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_critical),
            SignalSeverity.CRITICAL
        )

        # WARNING (2-3%)
        signal_warning = {
            'signal_type': 'high_volatility',
            'magnitude': 0.025
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_warning),
            SignalSeverity.WARNING
        )

        # INFO (1.5-2%)
        signal_info = {
            'signal_type': 'high_volatility',
            'magnitude': 0.018
        }
        self.assertEqual(
            self.notifier._calculate_severity(signal_info),
            SignalSeverity.INFO
        )

    def test_filter_spam_no_filtering(self):
        """Test spam filter with no duplicates"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,
                'date': date.today()
            },
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.03,
                'date': date.today()
            }
        ]

        filtered = self.notifier._filter_spam(signals)

        # All signals should pass
        self.assertEqual(len(filtered), 2)

    def test_filter_spam_cooldown(self):
        """Test spam filter cooldown period"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,
                'date': date.today()
            }
        ]

        # First notification should pass
        filtered1 = self.notifier._filter_spam(signals)
        self.assertEqual(len(filtered1), 1)

        # Second notification (same currency+signal_type) should be filtered
        filtered2 = self.notifier._filter_spam(signals)
        self.assertEqual(len(filtered2), 0)

    def test_filter_spam_different_signal_types(self):
        """Test spam filter allows different signal types"""
        signals_appreciation = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,
                'date': date.today()
            }
        ]

        signals_depreciation = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.06,
                'date': date.today()
            }
        ]

        # Both should pass (different signal types)
        filtered1 = self.notifier._filter_spam(signals_appreciation)
        filtered2 = self.notifier._filter_spam(signals_depreciation)

        self.assertEqual(len(filtered1), 1)
        self.assertEqual(len(filtered2), 1)

    def test_is_quiet_hours_within_range(self):
        """Test quiet hours detection (within range)"""
        # Mock time to 03:00 (within 01:00-07:00)
        with patch('modules.fx_tracking.fx_notifier.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 11, 6, 3, 0, 0)
            mock_datetime.strptime = datetime.strptime

            is_quiet = self.notifier._is_quiet_hours()
            self.assertTrue(is_quiet)

    def test_is_quiet_hours_outside_range(self):
        """Test quiet hours detection (outside range)"""
        # Mock time to 10:00 (outside 01:00-07:00)
        with patch('modules.fx_tracking.fx_notifier.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 11, 6, 10, 0, 0)
            mock_datetime.strptime = datetime.strptime

            is_quiet = self.notifier._is_quiet_hours()
            self.assertFalse(is_quiet)

    def test_notify_fx_signals_empty_list(self):
        """Test notification with empty signal list"""
        result = self.notifier.notify_fx_signals([])

        # Should return zero counts
        self.assertEqual(result['critical_sent'], 0)
        self.assertEqual(result['warning_queued'], 0)
        self.assertEqual(result['info_queued'], 0)
        self.assertEqual(result['spam_filtered'], 0)

    def test_notify_fx_signals_critical_only(self):
        """Test notification with CRITICAL signals only"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,  # CRITICAL (≥5%)
                'current_rate': 1440.00,
                'previous_rate': 1350.00,
                'date': date.today()
            }
        ]

        # Mock _send_immediate_notifications
        with patch.object(self.notifier, '_send_immediate_notifications') as mock_send:
            mock_send.return_value = 1

            result = self.notifier.notify_fx_signals(signals)

            # Should send 1 CRITICAL notification
            self.assertEqual(result['critical_sent'], 1)
            self.assertEqual(result['warning_queued'], 0)
            self.assertEqual(result['info_queued'], 0)

    def test_notify_fx_signals_mixed_severities(self):
        """Test notification with mixed severity signals"""
        signals = [
            {
                'currency': 'USD',
                'signal_type': 'rapid_appreciation',
                'magnitude': 0.06,  # CRITICAL
                'current_rate': 1440.00,
                'previous_rate': 1350.00,
                'date': date.today()
            },
            {
                'currency': 'JPY',
                'signal_type': 'rapid_depreciation',
                'magnitude': 0.03,  # WARNING
                'current_rate': 9.50,
                'previous_rate': 10.25,
                'date': date.today()
            },
            {
                'currency': 'EUR',
                'signal_type': 'high_volatility',
                'magnitude': 0.018,  # INFO
                'date': date.today()
            }
        ]

        # Mock _send_immediate_notifications
        with patch.object(self.notifier, '_send_immediate_notifications') as mock_send:
            mock_send.return_value = 1

            result = self.notifier.notify_fx_signals(signals)

            # Should classify correctly
            self.assertEqual(result['critical_sent'], 1)
            self.assertEqual(result['warning_queued'], 1)
            self.assertEqual(result['info_queued'], 1)
            self.assertEqual(result['spam_filtered'], 0)

    def test_format_slack_message(self):
        """Test Slack message formatting"""
        signal = {
            'currency': 'USD',
            'signal_type': 'rapid_appreciation',
            'magnitude': 0.06,
            'current_rate': 1440.00,
            'previous_rate': 1350.00,
            'date': date.today()
        }

        message = self.notifier._format_slack_message(signal, 'CRITICAL')

        # Should contain key elements
        self.assertIn('USD', message)
        self.assertIn('rapid_appreciation', message)
        self.assertIn('6.00%', message)  # magnitude as percentage

    def test_format_email_subject(self):
        """Test email subject formatting"""
        signal = {
            'currency': 'USD',
            'signal_type': 'rapid_appreciation',
            'magnitude': 0.06
        }

        subject = self.notifier._format_email_subject(signal, 'CRITICAL')

        # Should contain severity, currency, and signal type
        self.assertIn('CRITICAL', subject)
        self.assertIn('USD', subject)
        self.assertIn('rapid_appreciation', subject)

    def test_format_email_body(self):
        """Test email body HTML formatting"""
        signal = {
            'currency': 'USD',
            'signal_type': 'rapid_appreciation',
            'magnitude': 0.06,
            'current_rate': 1440.00,
            'previous_rate': 1350.00,
            'date': date.today()
        }

        body = self.notifier._format_email_body(signal, 'CRITICAL')

        # Should be HTML
        self.assertIn('<', body)
        self.assertIn('>', body)

        # Should contain key data
        self.assertIn('USD', body)
        self.assertIn('rapid_appreciation', body)


if __name__ == '__main__':
    unittest.main()
