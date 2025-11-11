"""
FX Notification Service

FX 신호 기반 실시간 알림 시스템

Features:
- Severity 기반 알림 그룹핑 (CRITICAL/WARNING/INFO)
- 즉시 알림 vs 일일/주간 요약
- Slack 및 Email 멀티채널 지원
- 스팸 방지 및 중복 필터링
- Quiet hours 설정

Author: Spock Quant Platform
Date: 2025-11-06
"""

import logging
import yaml
import os
from datetime import datetime, time
from typing import Dict, List, Optional
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalSeverity(Enum):
    """FX 신호 심각도 레벨"""
    CRITICAL = "CRITICAL"    # ≥5% 변동: 즉시 알림
    WARNING = "WARNING"      # 2-5% 변동: 일일 요약
    INFO = "INFO"           # 1-2% 변동: 주간 요약


class FXNotificationService:
    """
    FX 신호 알림 서비스

    Features:
    - Severity 기반 알림 그룹핑
    - MakenaideSNSNotifier 통합 (Slack/Email)
    - 스팸 방지 및 중복 필터링
    - 통화별 우선순위 관리
    - Quiet hours 설정

    Usage:
        notifier = FXNotificationService(
            sns_notifier=makenaide_notifier,
            config_path='config/fx_config.yaml'
        )

        notifier.notify_fx_signals(signals)
    """

    def __init__(self, sns_notifier=None, config_path: str = 'config/fx_config.yaml'):
        """
        Initialize FX Notification Service

        Args:
            sns_notifier: MakenaideSNSNotifier instance (optional)
            config_path: Path to fx_config.yaml
        """
        self.sns_notifier = sns_notifier
        self.logger = logger

        # Load configuration
        self.config = self._load_config(config_path)

        # Spam prevention tracking
        self.message_history = defaultdict(list)  # {currency: [timestamps]}
        self.last_notification_time = {}  # {(currency, signal_type): timestamp}

    def _load_config(self, config_path: str) -> Dict:
        """
        Load FX notification configuration from YAML

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.logger.debug(f"Loaded FX config from {config_path}")
                return config
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._get_default_config()
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """
        Get default configuration

        Returns:
            Default configuration dictionary
        """
        return {
            'signal_thresholds': {
                'rapid_move': {
                    'critical': 0.05,
                    'warning': 0.02,
                    'info': 0.01
                },
                'volatility': {
                    'critical': 0.03,
                    'warning': 0.02,
                    'info': 0.015
                }
            },
            'notification_policy': {
                'immediate': {
                    'enabled': True,
                    'min_severity': 'CRITICAL'
                }
            },
            'spam_prevention': {
                'enabled': True,
                'time_window_minutes': 60,
                'max_critical_per_window': 5,
                'cooldown_minutes': 10
            },
            'quiet_hours': {
                'enabled': True,
                'start': '01:00',
                'end': '07:00',
                'bypass_critical': True
            }
        }

    def notify_fx_signals(self, signals: List[Dict]) -> Dict:
        """
        FX 신호 알림 전송

        Args:
            signals: List of FX signal dicts from FXTracker._calculate_signals()
                     Example: [{'currency': 'USD', 'signal_type': 'rapid_appreciation',
                               'magnitude': 0.025, 'current_rate': 1400.00, ...}]

        Returns:
            Dict with notification results:
                - critical_sent: Number of CRITICAL notifications sent
                - warning_queued: Number of WARNING signals queued for daily summary
                - info_queued: Number of INFO signals queued for weekly summary
                - spam_filtered: Number of signals filtered by spam prevention
        """
        if not signals:
            return {'critical_sent': 0, 'warning_queued': 0, 'info_queued': 0, 'spam_filtered': 0}

        # 1. Classify signals by severity
        classified = self._classify_signals(signals)

        # 2. Filter spam
        filtered_critical = self._filter_spam(classified['CRITICAL'])
        filtered_warning = self._filter_spam(classified['WARNING'])

        spam_filtered = (
            len(classified['CRITICAL']) - len(filtered_critical) +
            len(classified['WARNING']) - len(filtered_warning)
        )

        # 3. Send immediate notifications (CRITICAL only)
        critical_sent = 0
        if self.config['notification_policy']['immediate']['enabled']:
            critical_sent = self._send_immediate_notifications(filtered_critical)

        # 4. Queue daily summary (WARNING)
        warning_queued = len(filtered_warning)

        # 5. Queue weekly summary (INFO)
        info_queued = len(classified['INFO'])

        self.logger.info(
            f"📊 FX Notifications: {critical_sent} CRITICAL sent, "
            f"{warning_queued} WARNING queued, {info_queued} INFO queued, "
            f"{spam_filtered} spam filtered"
        )

        return {
            'critical_sent': critical_sent,
            'warning_queued': warning_queued,
            'info_queued': info_queued,
            'spam_filtered': spam_filtered
        }

    def _classify_signals(self, signals: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Classify signals by severity

        Args:
            signals: List of FX signal dicts

        Returns:
            Dict with keys 'CRITICAL', 'WARNING', 'INFO' containing signal lists
        """
        classified = {'CRITICAL': [], 'WARNING': [], 'INFO': []}

        for signal in signals:
            severity = self._calculate_severity(signal)
            classified[severity.value].append(signal)

        self.logger.debug(
            f"Classified signals: {len(classified['CRITICAL'])} CRITICAL, "
            f"{len(classified['WARNING'])} WARNING, {len(classified['INFO'])} INFO"
        )

        return classified

    def _calculate_severity(self, signal: Dict) -> SignalSeverity:
        """
        Calculate severity level for a signal

        Args:
            signal: FX signal dict

        Returns:
            SignalSeverity enum
        """
        signal_type = signal['signal_type']
        magnitude = signal['magnitude']

        # Get thresholds based on signal type
        if signal_type in ['rapid_appreciation', 'rapid_depreciation']:
            thresholds = self.config['signal_thresholds']['rapid_move']
        elif signal_type == 'high_volatility':
            thresholds = self.config['signal_thresholds']['volatility']
        else:
            # Unknown signal type, default to INFO
            return SignalSeverity.INFO

        # Classify by magnitude
        if magnitude >= thresholds['critical']:
            return SignalSeverity.CRITICAL
        elif magnitude >= thresholds['warning']:
            return SignalSeverity.WARNING
        else:
            return SignalSeverity.INFO

    def _filter_spam(self, signals: List[Dict]) -> List[Dict]:
        """
        Filter duplicate and spammy signals

        Args:
            signals: List of signals to filter

        Returns:
            Filtered signal list
        """
        if not self.config['spam_prevention']['enabled']:
            return signals

        filtered = []
        now = datetime.now()

        for signal in signals:
            currency = signal['currency']
            signal_type = signal['signal_type']
            key = (currency, signal_type)

            # Check cooldown
            if key in self.last_notification_time:
                last_time = self.last_notification_time[key]
                cooldown_minutes = self.config['spam_prevention']['cooldown_minutes']

                if (now - last_time).total_seconds() < cooldown_minutes * 60:
                    self.logger.debug(
                        f"Filtered {currency} {signal_type} (cooldown)"
                    )
                    continue

            # Check time window limit
            time_window_minutes = self.config['spam_prevention']['time_window_minutes']
            max_per_window = self.config['spam_prevention']['max_critical_per_window']

            # Clean old history
            self.message_history[currency] = [
                t for t in self.message_history[currency]
                if (now - t).total_seconds() < time_window_minutes * 60
            ]

            if len(self.message_history[currency]) >= max_per_window:
                self.logger.debug(
                    f"Filtered {currency} (max {max_per_window} per {time_window_minutes}min)"
                )
                continue

            # Passed filters
            filtered.append(signal)
            self.message_history[currency].append(now)
            self.last_notification_time[key] = now

        return filtered

    def _send_immediate_notifications(self, critical_signals: List[Dict]) -> int:
        """
        Send immediate notifications for CRITICAL signals

        Args:
            critical_signals: List of CRITICAL severity signals

        Returns:
            Number of notifications sent
        """
        if not critical_signals:
            return 0

        # Check quiet hours
        if self._is_quiet_hours() and not self.config['quiet_hours']['bypass_critical']:
            self.logger.info(
                f"Quiet hours active, skipping {len(critical_signals)} CRITICAL notifications"
            )
            return 0

        sent = 0
        for signal in critical_signals:
            try:
                self._send_slack_notification(signal, severity='CRITICAL')
                self._send_email_notification(signal, severity='CRITICAL')
                sent += 1
            except Exception as e:
                self.logger.error(f"Failed to send notification for {signal['currency']}: {e}")

        return sent

    def _is_quiet_hours(self) -> bool:
        """
        Check if current time is within quiet hours

        Returns:
            True if within quiet hours
        """
        if not self.config['quiet_hours']['enabled']:
            return False

        now = datetime.now().time()
        start = datetime.strptime(self.config['quiet_hours']['start'], '%H:%M').time()
        end = datetime.strptime(self.config['quiet_hours']['end'], '%H:%M').time()

        if start < end:
            return start <= now <= end
        else:
            # Crosses midnight
            return now >= start or now <= end

    def _send_slack_notification(self, signal: Dict, severity: str):
        """
        Send Slack notification (stub for Phase 2.2)

        Args:
            signal: FX signal dict
            severity: Severity level string
        """
        if not self.sns_notifier:
            self.logger.debug("SNS notifier not configured, skipping Slack notification")
            return

        # Format Slack message
        message = self._format_slack_message(signal, severity)

        # TODO: Implement Slack webhook integration via MakenaideSNSNotifier
        self.logger.info(f"🚨 Slack notification: {signal['currency']} {signal['signal_type']}")

    def _send_email_notification(self, signal: Dict, severity: str):
        """
        Send Email notification via SNS (stub for Phase 2.2)

        Args:
            signal: FX signal dict
            severity: Severity level string
        """
        if not self.sns_notifier:
            self.logger.debug("SNS notifier not configured, skipping Email notification")
            return

        # Format email subject and body
        subject = self._format_email_subject(signal, severity)
        body = self._format_email_body(signal, severity)

        # TODO: Implement SNS email via MakenaideSNSNotifier
        self.logger.info(f"📧 Email notification: {subject}")

    def _format_slack_message(self, signal: Dict, severity: str) -> str:
        """
        Format Slack message from template

        Args:
            signal: FX signal dict
            severity: Severity level

        Returns:
            Formatted Slack message
        """
        template = self.config.get('message_templates', {}).get('slack', {}).get(
            severity.lower(),
            "🚨 *{severity} FX Alert*\n\n*Currency*: {currency}\n*Signal*: {signal_type}\n*Magnitude*: {magnitude:.2%}"
        )

        return template.format(
            severity=severity,
            currency=signal['currency'],
            signal_type=signal['signal_type'],
            magnitude=signal['magnitude'],
            current_rate=signal.get('current_rate', 0),
            previous_rate=signal.get('previous_rate', 0),
            date=signal.get('date', datetime.now().date()),
            change=signal.get('magnitude', 0) if signal['signal_type'] == 'rapid_appreciation' else -signal.get('magnitude', 0)
        )

    def _format_email_subject(self, signal: Dict, severity: str) -> str:
        """
        Format email subject

        Args:
            signal: FX signal dict
            severity: Severity level

        Returns:
            Email subject line
        """
        template = self.config.get('message_templates', {}).get('email', {}).get(
            f'subject_{severity.lower()}',
            '[{severity}] FX Alert: {currency} {signal_type}'
        )

        return template.format(
            severity=severity,
            currency=signal['currency'],
            signal_type=signal['signal_type']
        )

    def _format_email_body(self, signal: Dict, severity: str) -> str:
        """
        Format email body HTML

        Args:
            signal: FX signal dict
            severity: Severity level

        Returns:
            Email body HTML
        """
        template = self.config.get('message_templates', {}).get('email', {}).get(
            'body_html',
            '<h2>{severity} FX Alert</h2><p>{currency}: {signal_type} ({magnitude:.2%})</p>'
        )

        return template.format(
            severity=severity,
            currency=signal['currency'],
            signal_type=signal['signal_type'],
            magnitude=signal['magnitude'],
            current_rate=signal.get('current_rate', 0),
            previous_rate=signal.get('previous_rate', 0),
            date=signal.get('date', datetime.now().date())
        )
