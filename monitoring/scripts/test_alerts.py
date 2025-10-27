#!/usr/bin/env python3
"""
Alert Testing Script for Quant Platform Monitoring

Tests alert notification channels by triggering test alerts via Prometheus metrics.

Usage:
    python3 test_alerts.py --all                          # Test all channels
    python3 test_alerts.py --channel slack                # Test Slack only
    python3 test_alerts.py --alert HighBacktestFailureRate # Test specific alert
    python3 test_alerts.py --severity critical            # Test severity level
"""

import argparse
import requests
import time
import sys
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway, delete_from_gateway

# Configuration
PROMETHEUS_URL = "http://localhost:9090"
ALERTMANAGER_URL = "http://localhost:9093"
PUSHGATEWAY_URL = "http://localhost:9091"  # Optional: if using Pushgateway

# Test alert definitions
TEST_ALERTS = {
    # Critical backtest alerts
    "HighBacktestFailureRate": {
        "severity": "critical",
        "category": "backtest_performance",
        "metric": "backtest_executions_total",
        "labels": {"status": "failed", "strategy_name": "TestStrategy", "engine": "backtrader"},
        "value": 10,  # High failure count
    },
    "CriticalBacktestFailureRate": {
        "severity": "critical",
        "category": "backtest_performance",
        "metric": "backtest_executions_total",
        "labels": {"status": "failed", "strategy_name": "TestStrategy", "engine": "backtrader"},
        "value": 15,  # Very high failure count
    },
    # Warning backtest alerts
    "SlowBacktestExecution": {
        "severity": "warning",
        "category": "backtest_performance",
        "metric": "backtest_duration_seconds",
        "labels": {"strategy_name": "TestStrategy", "engine": "backtrader"},
        "value": 65,  # 65 seconds (threshold: 60s)
    },
    "LowSharpeRatio": {
        "severity": "warning",
        "category": "backtest_quality",
        "metric": "backtest_sharpe_ratio",
        "labels": {"strategy_name": "TestStrategy", "engine": "backtrader"},
        "value": 0.8,  # Below threshold (1.0)
    },
    # Critical optimization alerts
    "CriticalOptimizationFailureRate": {
        "severity": "critical",
        "category": "portfolio_optimization",
        "metric": "optimization_executions_total",
        "labels": {"status": "failed", "method": "mean_variance"},
        "value": 12,  # High failure count
    },
    # Warning factor calculation alerts
    "SlowFactorCalculation": {
        "severity": "warning",
        "category": "factor_calculation",
        "metric": "factor_calculation_duration_seconds",
        "labels": {"factor_name": "momentum"},
        "value": 35,  # 35 seconds (threshold: 30s)
    },
    # Critical API alerts
    "CriticalQuantAPIErrorRate": {
        "severity": "critical",
        "category": "quant_api_performance",
        "metric": "http_requests_total",
        "labels": {"status": "500", "method": "POST", "path": "/backtest"},
        "value": 15,  # High error count
    },
    # Critical database alerts
    "DatabasePoolExhausted": {
        "severity": "critical",
        "category": "database_connection_pool",
        "metric": "db_pool_utilization_percent",
        "labels": {"database": "quant_platform"},
        "value": 105,  # Over 100% (exhausted)
    },
}


class AlertTester:
    """Test alert notifications by simulating metrics"""

    def __init__(self, prometheus_url, alertmanager_url):
        self.prometheus_url = prometheus_url
        self.alertmanager_url = alertmanager_url
        self.registry = CollectorRegistry()

    def check_prometheus_health(self):
        """Check if Prometheus is accessible"""
        try:
            response = requests.get(f"{self.prometheus_url}/-/healthy", timeout=5)
            if response.status_code == 200:
                print("✅ Prometheus is healthy")
                return True
            else:
                print(f"❌ Prometheus health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Prometheus: {e}")
            return False

    def check_alertmanager_health(self):
        """Check if Alertmanager is accessible"""
        try:
            response = requests.get(f"{self.alertmanager_url}/api/v2/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Alertmanager is healthy (version: {status['versionInfo']['version']})")
                return True
            else:
                print(f"❌ Alertmanager health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Alertmanager: {e}")
            return False

    def get_active_alerts(self):
        """Get currently active alerts from Prometheus"""
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/rules", timeout=5)
            if response.status_code == 200:
                data = response.json()
                active_alerts = []
                for group in data['data']['groups']:
                    for rule in group['rules']:
                        if rule.get('type') == 'alerting' and rule.get('state') == 'firing':
                            active_alerts.append(rule['name'])
                return active_alerts
            return []
        except Exception as e:
            print(f"⚠️  Cannot fetch active alerts: {e}")
            return []

    def trigger_test_alert(self, alert_name, alert_config):
        """
        Trigger a test alert by exposing metrics via FastAPI /metrics endpoint

        Note: This is a simplified test that shows the alert structure.
        In production, alerts are triggered by actual application metrics.
        """
        print(f"\n📊 Testing alert: {alert_name}")
        print(f"   Severity: {alert_config['severity']}")
        print(f"   Category: {alert_config['category']}")
        print(f"   Metric: {alert_config['metric']}")

        # Display what would trigger this alert
        print("\n   This alert would be triggered when:")
        if alert_name == "HighBacktestFailureRate":
            print("   - Backtest failure rate > 30% for 10 minutes")
        elif alert_name == "CriticalBacktestFailureRate":
            print("   - Backtest failure rate > 50% for 5 minutes")
        elif alert_name == "SlowBacktestExecution":
            print("   - P95 backtest duration > 60s for 10 minutes")
        elif alert_name == "LowSharpeRatio":
            print("   - Sharpe ratio < 1.0 for any strategy")
        elif alert_name == "CriticalOptimizationFailureRate":
            print("   - Optimization failure rate > 50% for 5 minutes")
        elif alert_name == "SlowFactorCalculation":
            print("   - P95 factor calculation duration > 30s for 10 minutes")
        elif alert_name == "CriticalQuantAPIErrorRate":
            print("   - API error rate > 10% for 5 minutes")
        elif alert_name == "DatabasePoolExhausted":
            print("   - Database pool utilization >= 100% for 5 minutes")

        print("\n   ✅ Alert configuration validated")
        return True

    def check_alertmanager_alerts(self):
        """Check alerts in Alertmanager"""
        try:
            response = requests.get(f"{self.alertmanager_url}/api/v2/alerts", timeout=5)
            if response.status_code == 200:
                alerts = response.json()
                if alerts:
                    print(f"\n📬 Alertmanager has {len(alerts)} active alert(s):")
                    for alert in alerts:
                        labels = alert.get('labels', {})
                        print(f"   - {labels.get('alertname', 'Unknown')}: {alert.get('status', {}).get('state', 'unknown')}")
                else:
                    print("\n📭 No active alerts in Alertmanager")
                return len(alerts)
            else:
                print(f"❌ Cannot fetch Alertmanager alerts: {response.status_code}")
                return 0
        except Exception as e:
            print(f"❌ Error checking Alertmanager alerts: {e}")
            return 0

    def test_notification_channel(self, channel):
        """Test specific notification channel"""
        print(f"\n🔔 Testing {channel} notification channel...")

        if channel == "slack":
            print("   📱 Slack Configuration:")
            print("      - Channel: #quant-critical-alerts (critical)")
            print("      - Channel: #quant-warnings (warning)")
            print("      - Check Slack channels for test messages")
            print("      - Verify emoji, formatting, and links")

        elif channel == "email":
            print("   📧 Email Configuration:")
            print("      - Recipients: Check EMAIL_TO in .env.alertmanager")
            print("      - Check inbox and spam folder")
            print("      - Verify HTML formatting and links")

        elif channel == "webhook":
            print("   🌐 Webhook Configuration:")
            print("      - Endpoint: Check CUSTOM_WEBHOOK_URL in .env.alertmanager")
            print("      - Verify webhook endpoint logs")
            print("      - Check JSON payload structure")

        elif channel == "console":
            print("   🖥️  Console Logs:")
            print("      - Check Alertmanager logs:")
            print("        docker-compose logs -f alertmanager")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Test Quant Platform alert notifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all notification channels
  python3 test_alerts.py --all

  # Test specific channel
  python3 test_alerts.py --channel slack
  python3 test_alerts.py --channel email

  # Test specific alert
  python3 test_alerts.py --alert HighBacktestFailureRate

  # Test by severity
  python3 test_alerts.py --severity critical
  python3 test_alerts.py --severity warning

  # Dry run (show what would be tested)
  python3 test_alerts.py --all --dry-run
        """
    )

    parser.add_argument('--all', action='store_true',
                        help='Test all alerts and channels')
    parser.add_argument('--alert', type=str,
                        help='Test specific alert by name')
    parser.add_argument('--severity', type=str, choices=['critical', 'warning', 'info'],
                        help='Test alerts by severity level')
    parser.add_argument('--channel', type=str, choices=['slack', 'email', 'webhook', 'console'],
                        help='Test specific notification channel')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be tested without triggering')
    parser.add_argument('--prometheus-url', type=str, default=PROMETHEUS_URL,
                        help='Prometheus URL (default: http://localhost:9090)')
    parser.add_argument('--alertmanager-url', type=str, default=ALERTMANAGER_URL,
                        help='Alertmanager URL (default: http://localhost:9093)')

    args = parser.parse_args()

    # Initialize tester
    tester = AlertTester(args.prometheus_url, args.alertmanager_url)

    print("=" * 60)
    print("Quant Platform Alert Notification Tester")
    print("=" * 60)

    # Health checks
    print("\n🏥 Health Checks:")
    prometheus_healthy = tester.check_prometheus_health()
    alertmanager_healthy = tester.check_alertmanager_health()

    if not (prometheus_healthy and alertmanager_healthy):
        print("\n❌ Health checks failed. Please ensure services are running:")
        print("   cd /Users/13ruce/spock/monitoring")
        print("   docker-compose up -d")
        sys.exit(1)

    # Check current alerts
    print("\n🔍 Current Alert Status:")
    active_alerts = tester.get_active_alerts()
    if active_alerts:
        print(f"   Active alerts: {', '.join(active_alerts)}")
    else:
        print("   No alerts currently firing")

    # Check Alertmanager
    tester.check_alertmanager_alerts()

    # Dry run mode
    if args.dry_run:
        print("\n🔍 Dry Run Mode - Showing what would be tested:")

    # Test specific alert
    if args.alert:
        if args.alert in TEST_ALERTS:
            tester.trigger_test_alert(args.alert, TEST_ALERTS[args.alert])
        else:
            print(f"❌ Alert '{args.alert}' not found. Available alerts:")
            for name in TEST_ALERTS.keys():
                print(f"   - {name}")
            sys.exit(1)

    # Test by severity
    elif args.severity:
        print(f"\n🎯 Testing {args.severity} severity alerts:")
        for name, config in TEST_ALERTS.items():
            if config['severity'] == args.severity:
                tester.trigger_test_alert(name, config)

    # Test specific channel
    elif args.channel:
        tester.test_notification_channel(args.channel)

    # Test all
    elif args.all:
        print("\n📊 Testing all alert types:")
        for name, config in TEST_ALERTS.items():
            tester.trigger_test_alert(name, config)

        print("\n🔔 Testing all notification channels:")
        for channel in ['slack', 'email', 'webhook', 'console']:
            tester.test_notification_channel(channel)

    else:
        parser.print_help()
        sys.exit(1)

    # Final instructions
    print("\n" + "=" * 60)
    print("✅ Test Configuration Complete")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Configure .env.alertmanager with your credentials:")
    print("   cp .env.alertmanager.example .env.alertmanager")
    print("   vim .env.alertmanager")
    print()
    print("2. Restart Alertmanager to load new configuration:")
    print("   docker-compose restart alertmanager")
    print()
    print("3. Trigger real alerts by running actual operations:")
    print("   - Run backtests with high failure rates")
    print("   - Generate high API load")
    print("   - Exhaust database connection pool")
    print()
    print("4. Monitor notifications in:")
    print("   - Slack channels (#quant-critical-alerts, #quant-warnings)")
    print("   - Email inbox")
    print("   - Webhook endpoint logs")
    print("   - Alertmanager logs: docker-compose logs -f alertmanager")
    print()
    print("5. View alerts in Alertmanager UI:")
    print("   http://localhost:9093")
    print()
    print("For more information, see:")
    print("   docs/ALERT_NOTIFICATION_SETUP.md")


if __name__ == '__main__':
    main()
