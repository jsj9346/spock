#!/usr/bin/env python3
"""
alert_system.py - Threshold-Based Alert System

Purpose:
- Monitor system metrics against defined thresholds
- Generate alerts for threshold violations
- Support multiple alert channels (console, file, email placeholder)
- Track alert history and prevent alert fatigue
- Provide alert escalation based on severity

Alert Levels:
- INFO: Informational alerts (no action required)
- WARNING: Potential issues (monitoring recommended)
- CRITICAL: Immediate attention required

Alert Categories:
- API: Error rates, latency, rate limits
- Database: Query performance, storage
- Data Quality: NULL values, integrity violations
- System: CPU, memory, disk usage
- Collectors: Success rates, processing time

Author: Spock Trading System
Created: 2025-10-16 (Phase 3, Task 3.2.3)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.metrics_collector import MetricsCollector


class Alert:
    """Alert data structure"""

    def __init__(self, level: str, category: str, message: str, value: float = None, threshold: float = None):
        self.timestamp = datetime.now().isoformat()
        self.level = level  # INFO, WARNING, CRITICAL
        self.category = category  # API, DATABASE, DATA_QUALITY, SYSTEM, COLLECTORS
        self.message = message
        self.value = value
        self.threshold = threshold
        self.id = f"{level}_{category}_{hash(message) % 10000}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'level': self.level,
            'category': self.category,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold
        }

    def __str__(self) -> str:
        icon = {'INFO': 'ℹ️', 'WARNING': '⚠️', 'CRITICAL': '🚨'}.get(self.level, '•')
        value_str = f" (value: {self.value:.2f}, threshold: {self.threshold:.2f})" if self.value is not None else ""
        return f"{icon} [{self.level}] {self.category}: {self.message}{value_str}"


class AlertSystem:
    """Threshold-based monitoring and alerting system"""

    def __init__(self, config_file: str = None):
        self.metrics_collector = MetricsCollector()
        self.alert_history = []
        self.suppressed_alerts = {}  # Alert ID -> last trigger time
        self.suppression_window = timedelta(minutes=15)  # Suppress repeat alerts for 15 minutes

        # Load alert thresholds
        self.thresholds = self.load_thresholds(config_file)

    def load_thresholds(self, config_file: str = None) -> Dict[str, Any]:
        """Load alert thresholds from config file or use defaults"""
        default_thresholds = {
            'api': {
                'error_rate_warning': 5.0,       # %
                'error_rate_critical': 20.0,     # %
                'latency_warning': 500.0,        # ms
                'latency_critical': 1000.0,      # ms
                'rate_limit_warning': 80.0,      # %
                'rate_limit_critical': 95.0      # %
            },
            'database': {
                'query_time_warning': 500.0,     # ms
                'query_time_critical': 1000.0,   # ms
                'size_warning': 1000.0,          # MB
                'size_critical': 5000.0          # MB
            },
            'data_quality': {
                'critical_nulls_warning': 1,     # count
                'critical_nulls_critical': 10,   # count
                'violations_warning': 100,       # count
                'violations_critical': 1000      # count
            },
            'system': {
                'cpu_warning': 70.0,             # %
                'cpu_critical': 85.0,            # %
                'memory_warning': 70.0,          # %
                'memory_critical': 85.0,         # %
                'disk_warning': 80.0,            # %
                'disk_critical': 90.0            # %
            },
            'collectors': {
                'success_rate_warning': 95.0,    # %
                'success_rate_critical': 80.0,   # %
                'processing_time_warning': 500.0, # ms
                'processing_time_critical': 1000.0  # ms
            }
        }

        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    custom_thresholds = json.load(f)
                    # Merge custom thresholds with defaults
                    for category, thresholds in custom_thresholds.items():
                        if category in default_thresholds:
                            default_thresholds[category].update(thresholds)
                print(f"✅ Loaded custom thresholds from: {config_file}")
            except Exception as e:
                print(f"⚠️  Failed to load custom thresholds: {e}")
                print(f"   Using default thresholds")

        return default_thresholds

    def check_all_thresholds(self) -> List[Alert]:
        """Check all metrics against thresholds and generate alerts"""
        metrics = self.metrics_collector.collect_all_metrics()
        alerts = []

        # Check API metrics
        alerts.extend(self.check_api_metrics(metrics['api']))

        # Check database metrics
        alerts.extend(self.check_database_metrics(metrics['database']))

        # Check data quality metrics
        alerts.extend(self.check_data_quality_metrics(metrics['data_quality']))

        # Check system metrics
        alerts.extend(self.check_system_metrics(metrics['system']))

        # Check collector metrics
        alerts.extend(self.check_collector_metrics(metrics['collectors']))

        # Filter suppressed alerts
        active_alerts = self.filter_suppressed_alerts(alerts)

        # Update alert history
        self.alert_history.extend(active_alerts)
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

        return active_alerts

    def check_api_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check API metrics against thresholds"""
        alerts = []

        # Error rate
        error_rate = metrics['error_rate']
        if error_rate >= self.thresholds['api']['error_rate_critical']:
            alerts.append(Alert('CRITICAL', 'API', f"API error rate critical: {error_rate:.1f}%",
                              error_rate, self.thresholds['api']['error_rate_critical']))
        elif error_rate >= self.thresholds['api']['error_rate_warning']:
            alerts.append(Alert('WARNING', 'API', f"API error rate high: {error_rate:.1f}%",
                              error_rate, self.thresholds['api']['error_rate_warning']))

        # Latency
        if metrics['avg_latency_ms'] is not None:
            avg_latency = metrics['avg_latency_ms']
            if avg_latency >= self.thresholds['api']['latency_critical']:
                alerts.append(Alert('CRITICAL', 'API', f"API latency critical: {avg_latency:.1f}ms",
                                  avg_latency, self.thresholds['api']['latency_critical']))
            elif avg_latency >= self.thresholds['api']['latency_warning']:
                alerts.append(Alert('WARNING', 'API', f"API latency high: {avg_latency:.1f}ms",
                                  avg_latency, self.thresholds['api']['latency_warning']))

        # Rate limit usage
        rate_limit_pct = metrics['rate_limit_usage_pct']
        if rate_limit_pct >= self.thresholds['api']['rate_limit_critical']:
            alerts.append(Alert('CRITICAL', 'API', f"Rate limit usage critical: {rate_limit_pct:.1f}%",
                              rate_limit_pct, self.thresholds['api']['rate_limit_critical']))
        elif rate_limit_pct >= self.thresholds['api']['rate_limit_warning']:
            alerts.append(Alert('WARNING', 'API', f"Rate limit usage high: {rate_limit_pct:.1f}%",
                              rate_limit_pct, self.thresholds['api']['rate_limit_warning']))

        return alerts

    def check_database_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check database metrics against thresholds"""
        alerts = []

        # Query performance
        for query_name, perf in metrics['query_performance'].items():
            latency = perf['latency_ms']
            if latency >= self.thresholds['database']['query_time_critical']:
                alerts.append(Alert('CRITICAL', 'DATABASE', f"Query '{query_name}' critical: {latency:.1f}ms",
                                  latency, self.thresholds['database']['query_time_critical']))
            elif latency >= self.thresholds['database']['query_time_warning']:
                alerts.append(Alert('WARNING', 'DATABASE', f"Query '{query_name}' slow: {latency:.1f}ms",
                                  latency, self.thresholds['database']['query_time_warning']))

        # Database size
        db_size_mb = metrics['database_size_mb']
        if db_size_mb >= self.thresholds['database']['size_critical']:
            alerts.append(Alert('CRITICAL', 'DATABASE', f"Database size critical: {db_size_mb:.1f}MB",
                              db_size_mb, self.thresholds['database']['size_critical']))
        elif db_size_mb >= self.thresholds['database']['size_warning']:
            alerts.append(Alert('WARNING', 'DATABASE', f"Database size high: {db_size_mb:.1f}MB",
                              db_size_mb, self.thresholds['database']['size_warning']))

        return alerts

    def check_data_quality_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check data quality metrics against thresholds"""
        alerts = []

        # Critical NULL values
        critical_nulls = sum(1 for col in metrics['null_rates'].values() if col['status'] == 'critical')
        if critical_nulls >= self.thresholds['data_quality']['critical_nulls_critical']:
            alerts.append(Alert('CRITICAL', 'DATA_QUALITY', f"Critical NULL values: {critical_nulls}",
                              critical_nulls, self.thresholds['data_quality']['critical_nulls_critical']))
        elif critical_nulls >= self.thresholds['data_quality']['critical_nulls_warning']:
            alerts.append(Alert('WARNING', 'DATA_QUALITY', f"Critical NULL values detected: {critical_nulls}",
                              critical_nulls, self.thresholds['data_quality']['critical_nulls_warning']))

        # Integrity violations
        violations = metrics['integrity_violations']['total']
        if violations >= self.thresholds['data_quality']['violations_critical']:
            alerts.append(Alert('CRITICAL', 'DATA_QUALITY', f"Integrity violations critical: {violations}",
                              violations, self.thresholds['data_quality']['violations_critical']))
        elif violations >= self.thresholds['data_quality']['violations_warning']:
            alerts.append(Alert('WARNING', 'DATA_QUALITY', f"Integrity violations detected: {violations}",
                              violations, self.thresholds['data_quality']['violations_warning']))

        return alerts

    def check_system_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check system metrics against thresholds"""
        alerts = []

        # CPU usage
        cpu_pct = metrics['cpu']['usage_pct']
        if cpu_pct >= self.thresholds['system']['cpu_critical']:
            alerts.append(Alert('CRITICAL', 'SYSTEM', f"CPU usage critical: {cpu_pct:.1f}%",
                              cpu_pct, self.thresholds['system']['cpu_critical']))
        elif cpu_pct >= self.thresholds['system']['cpu_warning']:
            alerts.append(Alert('WARNING', 'SYSTEM', f"CPU usage high: {cpu_pct:.1f}%",
                              cpu_pct, self.thresholds['system']['cpu_warning']))

        # Memory usage
        memory_pct = metrics['memory']['usage_pct']
        if memory_pct >= self.thresholds['system']['memory_critical']:
            alerts.append(Alert('CRITICAL', 'SYSTEM', f"Memory usage critical: {memory_pct:.1f}%",
                              memory_pct, self.thresholds['system']['memory_critical']))
        elif memory_pct >= self.thresholds['system']['memory_warning']:
            alerts.append(Alert('WARNING', 'SYSTEM', f"Memory usage high: {memory_pct:.1f}%",
                              memory_pct, self.thresholds['system']['memory_warning']))

        # Disk usage
        disk_pct = metrics['disk']['usage_pct']
        if disk_pct >= self.thresholds['system']['disk_critical']:
            alerts.append(Alert('CRITICAL', 'SYSTEM', f"Disk usage critical: {disk_pct:.1f}%",
                              disk_pct, self.thresholds['system']['disk_critical']))
        elif disk_pct >= self.thresholds['system']['disk_warning']:
            alerts.append(Alert('WARNING', 'SYSTEM', f"Disk usage high: {disk_pct:.1f}%",
                              disk_pct, self.thresholds['system']['disk_warning']))

        return alerts

    def check_collector_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check collector metrics against thresholds"""
        alerts = []

        # Collection success rate
        for region, rates in metrics['collection_rates'].items():
            success_rate = rates['success_rate']
            if success_rate <= self.thresholds['collectors']['success_rate_critical']:
                alerts.append(Alert('CRITICAL', 'COLLECTORS', f"{region} success rate critical: {success_rate:.1f}%",
                                  success_rate, self.thresholds['collectors']['success_rate_critical']))
            elif success_rate <= self.thresholds['collectors']['success_rate_warning']:
                alerts.append(Alert('WARNING', 'COLLECTORS', f"{region} success rate low: {success_rate:.1f}%",
                                  success_rate, self.thresholds['collectors']['success_rate_warning']))

        # Processing time
        for region, times in metrics['processing_time'].items():
            avg_ms = times['avg_ms']
            if avg_ms >= self.thresholds['collectors']['processing_time_critical']:
                alerts.append(Alert('CRITICAL', 'COLLECTORS', f"{region} processing time critical: {avg_ms:.1f}ms",
                                  avg_ms, self.thresholds['collectors']['processing_time_critical']))
            elif avg_ms >= self.thresholds['collectors']['processing_time_warning']:
                alerts.append(Alert('WARNING', 'COLLECTORS', f"{region} processing time high: {avg_ms:.1f}ms",
                                  avg_ms, self.thresholds['collectors']['processing_time_warning']))

        return alerts

    def filter_suppressed_alerts(self, alerts: List[Alert]) -> List[Alert]:
        """Filter out recently triggered alerts to prevent alert fatigue"""
        active_alerts = []
        now = datetime.now()

        for alert in alerts:
            # Check if alert was recently triggered
            if alert.id in self.suppressed_alerts:
                last_trigger = self.suppressed_alerts[alert.id]
                time_since_last = now - datetime.fromisoformat(last_trigger)

                if time_since_last < self.suppression_window:
                    # Suppress this alert
                    continue

            # Alert is active, update suppression tracking
            self.suppressed_alerts[alert.id] = now.isoformat()
            active_alerts.append(alert)

        return active_alerts

    def send_alerts(self, alerts: List[Alert], channels: List[str] = None):
        """Send alerts to configured channels"""
        if not alerts:
            return

        if channels is None:
            channels = ['console', 'file']

        for channel in channels:
            if channel == 'console':
                self.send_console_alerts(alerts)
            elif channel == 'file':
                self.send_file_alerts(alerts)
            elif channel == 'email':
                self.send_email_alerts(alerts)  # Placeholder

    def send_console_alerts(self, alerts: List[Alert]):
        """Send alerts to console"""
        print("\n" + "="*70)
        print(f"Alert System - {len(alerts)} Active Alert(s)")
        print("="*70)

        for alert in alerts:
            print(f"{alert}")

        print("="*70 + "\n")

    def send_file_alerts(self, alerts: List[Alert]):
        """Save alerts to file"""
        alert_dir = project_root / 'alert_logs'
        alert_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        alert_file = alert_dir / f"alerts_{timestamp}.json"

        alert_data = {
            'timestamp': datetime.now().isoformat(),
            'alert_count': len(alerts),
            'alerts': [alert.to_dict() for alert in alerts]
        }

        with open(alert_file, 'w') as f:
            json.dump(alert_data, f, indent=2)

        print(f"💾 Alerts saved: {alert_file}")

    def send_email_alerts(self, alerts: List[Alert]):
        """Placeholder for email alerts"""
        print("📧 Email alerts (not implemented)")
        print("   To enable email alerts, configure SMTP settings")

    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert statistics and summary"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        recent_alerts_1h = [a for a in self.alert_history if datetime.fromisoformat(a.timestamp) >= hour_ago]
        recent_alerts_24h = [a for a in self.alert_history if datetime.fromisoformat(a.timestamp) >= day_ago]

        summary = {
            'total_alerts': len(self.alert_history),
            'last_hour': {
                'total': len(recent_alerts_1h),
                'critical': len([a for a in recent_alerts_1h if a.level == 'CRITICAL']),
                'warning': len([a for a in recent_alerts_1h if a.level == 'WARNING']),
                'info': len([a for a in recent_alerts_1h if a.level == 'INFO'])
            },
            'last_24h': {
                'total': len(recent_alerts_24h),
                'critical': len([a for a in recent_alerts_24h if a.level == 'CRITICAL']),
                'warning': len([a for a in recent_alerts_24h if a.level == 'WARNING']),
                'info': len([a for a in recent_alerts_24h if a.level == 'INFO'])
            },
            'by_category': self.get_alerts_by_category(recent_alerts_24h)
        }

        return summary

    def get_alerts_by_category(self, alerts: List[Alert]) -> Dict[str, int]:
        """Group alerts by category"""
        by_category = defaultdict(int)
        for alert in alerts:
            by_category[alert.category] += 1
        return dict(by_category)


if __name__ == '__main__':
    # Example usage
    alert_system = AlertSystem()

    print("="*70)
    print("Alert System - Live Demo")
    print("="*70)

    # Check all thresholds
    print("\n🔍 Checking all metrics against thresholds...")
    alerts = alert_system.check_all_thresholds()

    if alerts:
        # Send alerts
        alert_system.send_alerts(alerts, channels=['console', 'file'])

        # Get summary
        summary = alert_system.get_alert_summary()
        print(f"\n📊 Alert Summary:")
        print(f"   Last Hour: {summary['last_hour']['total']} alerts "
              f"({summary['last_hour']['critical']} critical, {summary['last_hour']['warning']} warning)")
        print(f"   Last 24h: {summary['last_24h']['total']} alerts "
              f"({summary['last_24h']['critical']} critical, {summary['last_24h']['warning']} warning)")

        if summary['by_category']:
            print(f"\n   By Category:")
            for category, count in summary['by_category'].items():
                print(f"      {category}: {count}")
    else:
        print("\n✅ No alerts triggered - all systems healthy!")
