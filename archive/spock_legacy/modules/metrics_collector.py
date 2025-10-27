#!/usr/bin/env python3
"""
metrics_collector.py - Metrics Collection System

Purpose:
- Collect real-time metrics for API performance, database health, and system resources
- Track data quality metrics across all markets
- Monitor collector performance and error rates
- Generate time-series metrics for dashboard visualization
- Support alerting based on threshold violations

Metrics Categories:
1. API Metrics: Request rates, error rates, latency, rate limit usage
2. Database Metrics: Query performance, connection pool, storage growth, row counts
3. Data Quality Metrics: NULL rates, validation failures, contamination
4. System Metrics: CPU, memory, disk usage
5. Collector Metrics: Collection rates, success/failure, processing time

Author: Spock Trading System
Created: 2025-10-16 (Phase 3, Task 3.2.1)
"""

import os
import sys
import json
import time
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager


class MetricsCollector:
    """Real-time metrics collection system"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.metrics_history = []
        self.start_time = datetime.now()

    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all metrics categories"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'api': self.collect_api_metrics(),
            'database': self.collect_database_metrics(),
            'data_quality': self.collect_data_quality_metrics(),
            'system': self.collect_system_metrics(),
            'collectors': self.collect_collector_metrics()
        }

        # Store in history (last 1000 samples)
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 1000:
            self.metrics_history.pop(0)

        return metrics

    def collect_api_metrics(self) -> Dict[str, Any]:
        """Collect API performance metrics"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'error_rate': 0.0,
            'avg_latency_ms': 0.0,
            'p95_latency_ms': 0.0,
            'rate_limit_usage_pct': 0.0,
            'requests_by_region': {}
        }

        # Check if kis_api_logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kis_api_logs'")
        if cursor.fetchone() is None:
            conn.close()
            return metrics

        # Get recent API logs (last 1 hour)
        # Note: kis_api_logs schema: status_code (200=success), response_time (seconds), no region column
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status_code != 200 OR status_code IS NULL THEN 1 ELSE 0 END) as failed,
                AVG(CASE WHEN response_time IS NOT NULL THEN response_time * 1000 ELSE 0 END) as avg_latency_ms
            FROM kis_api_logs
            WHERE timestamp >= '{one_hour_ago}'
        """)

        row = cursor.fetchone()
        if row:
            total, successful, failed, avg_latency_ms = row
            metrics['total_requests'] = total
            metrics['successful_requests'] = successful
            metrics['failed_requests'] = failed
            metrics['error_rate'] = (failed / total * 100) if total > 0 else 0.0
            metrics['avg_latency_ms'] = avg_latency_ms

        # Calculate p95 latency (response_time in seconds, convert to ms)
        cursor.execute(f"""
            SELECT response_time * 1000
            FROM kis_api_logs
            WHERE timestamp >= '{one_hour_ago}' AND response_time IS NOT NULL
            ORDER BY response_time DESC
            LIMIT 1 OFFSET (SELECT COUNT(*) * 0.05 FROM kis_api_logs WHERE timestamp >= '{one_hour_ago}')
        """)
        p95_result = cursor.fetchone()
        metrics['p95_latency_ms'] = round(p95_result[0], 2) if p95_result else 0.0

        # Rate limit usage (20 req/sec = 1200 req/min)
        recent_1min = (datetime.now() - timedelta(minutes=1)).isoformat()
        cursor.execute(f"SELECT COUNT(*) FROM kis_api_logs WHERE timestamp >= '{recent_1min}'")
        recent_requests = cursor.fetchone()[0]
        metrics['rate_limit_usage_pct'] = (recent_requests / 1200.0 * 100) if recent_requests else 0.0

        conn.close()
        return metrics

    def collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database health metrics"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        metrics = {
            'total_rows': 0,
            'rows_by_region': {},
            'database_size_mb': 0.0,
            'avg_row_size_bytes': 0,
            'query_performance': {},
            'storage_growth': {}
        }

        # Total rows
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        metrics['total_rows'] = cursor.fetchone()[0]

        # Rows by region
        cursor.execute("SELECT region, COUNT(*) FROM ohlcv_data GROUP BY region")
        for region, count in cursor.fetchall():
            metrics['rows_by_region'][region] = count

        # Database size
        if os.path.exists(self.db_path):
            db_size_bytes = os.path.getsize(self.db_path)
            metrics['database_size_mb'] = db_size_bytes / (1024 * 1024)
            metrics['avg_row_size_bytes'] = int(db_size_bytes / metrics['total_rows']) if metrics['total_rows'] > 0 else 0

        # Query performance (measure 3 common queries)
        queries = {
            'region_select': "SELECT * FROM ohlcv_data WHERE region = 'KR' LIMIT 1000",
            'ticker_select': "SELECT * FROM ohlcv_data WHERE ticker = '005930' AND region = 'KR' ORDER BY date DESC LIMIT 100",
            'aggregation': "SELECT region, COUNT(*), AVG(close) FROM ohlcv_data GROUP BY region"
        }

        for query_name, query in queries.items():
            start = time.time()
            cursor.execute(query)
            _ = cursor.fetchall()
            elapsed_ms = (time.time() - start) * 1000
            metrics['query_performance'][query_name] = {
                'latency_ms': round(elapsed_ms, 2),
                'status': 'healthy' if elapsed_ms < 500 else 'slow'
            }

        # Storage growth (last 7 days)
        cursor.execute("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as rows_added
            FROM ohlcv_data
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)

        for date, rows_added in cursor.fetchall():
            metrics['storage_growth'][date] = rows_added

        conn.close()
        return metrics

    def collect_data_quality_metrics(self) -> Dict[str, Any]:
        """Collect data quality metrics"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        metrics = {
            'null_rates': {},
            'integrity_violations': {},
            'contamination': {},
            'completeness': {}
        }

        # NULL rates for critical columns
        total_rows_query = "SELECT COUNT(*) FROM ohlcv_data"
        cursor.execute(total_rows_query)
        total_rows = cursor.fetchone()[0]

        if total_rows == 0:
            conn.close()
            return metrics

        critical_columns = ['ticker', 'region', 'date', 'open', 'high', 'low', 'close', 'volume']

        for column in critical_columns:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {column} IS NULL")
            null_count = cursor.fetchone()[0]
            metrics['null_rates'][column] = {
                'null_count': null_count,
                'null_pct': round(null_count / total_rows * 100, 2) if total_rows > 0 else 0.0,
                'status': 'critical' if null_count > 0 else 'healthy'
            }

        # OHLCV integrity violations
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE high < low")
        high_low_violations = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL
            AND (close < low * 0.98 OR close > high * 1.02)
        """)
        close_violations = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE volume < 0")
        volume_violations = cursor.fetchone()[0]

        metrics['integrity_violations'] = {
            'high_low': high_low_violations,
            'close_range': close_violations,
            'negative_volume': volume_violations,
            'total': high_low_violations + close_violations + volume_violations,
            'status': 'healthy' if (high_low_violations + close_violations + volume_violations) == 0 else 'warning'
        }

        # Cross-region contamination (sample check)
        import re
        patterns = {
            'KR': r'^(\d{6}|\d{4}[A-Z]\d|\d{5}[KL])$',
            'US': r'^[A-Z]{1,5}(\.[A-Z])?$',
            'HK': r'^\d{4,5}$',
            'CN': r'^\d{6}$',
            'JP': r'^\d{4}$',
            'VN': r'^[A-Z]{3}$'
        }

        for region, pattern in patterns.items():
            cursor.execute(f"SELECT DISTINCT ticker FROM ohlcv_data WHERE region = '{region}' LIMIT 100")
            contamination_count = 0

            for (ticker,) in cursor.fetchall():
                ticker_base = ticker.split('.')[0] if region in ['CN', 'HK'] else ticker
                if not re.match(pattern, ticker_base):
                    contamination_count += 1

            metrics['contamination'][region] = {
                'violations': contamination_count,
                'status': 'healthy' if contamination_count == 0 else 'warning'
            }

        # Data completeness (recent data availability)
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        for region in ['KR', 'US', 'HK', 'CN', 'JP', 'VN']:
            cursor.execute(f"""
                SELECT COUNT(DISTINCT ticker)
                FROM ohlcv_data
                WHERE region = '{region}' AND date >= '{yesterday}'
            """)
            recent_tickers = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE region = '{region}'")
            total_tickers = cursor.fetchone()[0]

            completeness_pct = (recent_tickers / total_tickers * 100) if total_tickers > 0 else 0.0

            metrics['completeness'][region] = {
                'recent_tickers': recent_tickers,
                'total_tickers': total_tickers,
                'completeness_pct': round(completeness_pct, 2),
                'status': 'healthy' if completeness_pct >= 90 else 'warning' if completeness_pct >= 70 else 'critical'
            }

        conn.close()
        return metrics

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system resource metrics"""
        metrics = {
            'cpu': {},
            'memory': {},
            'disk': {}
        }

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        metrics['cpu'] = {
            'usage_pct': cpu_percent,
            'count': cpu_count,
            'status': 'healthy' if cpu_percent < 70 else 'warning' if cpu_percent < 85 else 'critical'
        }

        # Memory metrics
        memory = psutil.virtual_memory()

        metrics['memory'] = {
            'total_mb': round(memory.total / (1024 * 1024), 2),
            'used_mb': round(memory.used / (1024 * 1024), 2),
            'available_mb': round(memory.available / (1024 * 1024), 2),
            'usage_pct': memory.percent,
            'status': 'healthy' if memory.percent < 70 else 'warning' if memory.percent < 85 else 'critical'
        }

        # Disk metrics
        disk = psutil.disk_usage(str(project_root))

        metrics['disk'] = {
            'total_gb': round(disk.total / (1024 * 1024 * 1024), 2),
            'used_gb': round(disk.used / (1024 * 1024 * 1024), 2),
            'free_gb': round(disk.free / (1024 * 1024 * 1024), 2),
            'usage_pct': disk.percent,
            'status': 'healthy' if disk.percent < 80 else 'warning' if disk.percent < 90 else 'critical'
        }

        return metrics

    def collect_collector_metrics(self) -> Dict[str, Any]:
        """Collect data collector performance metrics"""
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        metrics = {
            'collection_rates': {},
            'error_rates': {},
            'processing_time': {}
        }

        # Check if kis_api_logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kis_api_logs'")
        if cursor.fetchone() is None:
            conn.close()
            return metrics

        # Collection rates (last 1 hour) - Overall stats since kis_api_logs doesn't have region column
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

        # Overall success rate
        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as successful
            FROM kis_api_logs
            WHERE timestamp >= '{one_hour_ago}'
        """)
        row = cursor.fetchone()
        total, successful = row if row else (0, 0)

        success_rate = (successful / total * 100) if total > 0 else 0.0

        metrics['collection_rates']['overall'] = {
            'total': total,
            'successful': successful,
            'success_rate': round(success_rate, 2),
            'status': 'healthy' if success_rate >= 95 else 'warning' if success_rate >= 80 else 'critical'
        }

        # Error rate
        error_rate = 100 - success_rate
        metrics['error_rates']['overall'] = {
            'error_rate': round(error_rate, 2),
            'status': 'healthy' if error_rate < 5 else 'warning' if error_rate < 20 else 'critical'
        }

        # Processing time (response_time in seconds, convert to ms)
        cursor.execute(f"""
            SELECT AVG(response_time * 1000), MAX(response_time * 1000)
            FROM kis_api_logs
            WHERE timestamp >= '{one_hour_ago}' AND response_time IS NOT NULL
        """)
        row = cursor.fetchone()
        avg_latency, max_latency = row if row and row[0] else (0, 0)

        metrics['processing_time']['overall'] = {
            'avg_ms': round(avg_latency, 2) if avg_latency else 0.0,
            'max_ms': round(max_latency, 2) if max_latency else 0.0,
            'status': 'healthy' if avg_latency < 500 else 'warning' if avg_latency < 1000 else 'critical'
        }

        conn.close()
        return metrics

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get high-level metrics summary for dashboard"""
        metrics = self.collect_all_metrics()

        summary = {
            'timestamp': metrics['timestamp'],
            'uptime_seconds': metrics['uptime_seconds'],
            'overall_status': 'healthy',
            'critical_alerts': [],
            'warnings': [],
            'health_scores': {}
        }

        # Calculate health scores (0-100)
        health_scores = {}

        # API health
        api_health = 100
        if metrics['api']['error_rate'] > 20:
            api_health = 50
            summary['critical_alerts'].append(f"API error rate: {metrics['api']['error_rate']:.1f}%")
        elif metrics['api']['error_rate'] > 5:
            api_health = 75
            summary['warnings'].append(f"API error rate: {metrics['api']['error_rate']:.1f}%")

        health_scores['api'] = api_health

        # Database health
        db_health = 100
        slow_queries = sum(1 for q in metrics['database']['query_performance'].values() if q['status'] == 'slow')
        if slow_queries > 0:
            db_health = 85
            summary['warnings'].append(f"{slow_queries} slow database queries detected")

        health_scores['database'] = db_health

        # Data quality health
        dq_health = 100
        total_violations = metrics['data_quality']['integrity_violations']['total']
        if total_violations > 0:
            dq_health = 80
            summary['warnings'].append(f"{total_violations} data integrity violations")

        critical_nulls = sum(1 for col in metrics['data_quality']['null_rates'].values() if col['status'] == 'critical')
        if critical_nulls > 0:
            dq_health = 50
            summary['critical_alerts'].append(f"{critical_nulls} critical NULL value violations")

        health_scores['data_quality'] = dq_health

        # System health
        system_health = 100
        if metrics['system']['cpu']['status'] == 'critical':
            system_health = 60
            summary['critical_alerts'].append(f"CPU usage: {metrics['system']['cpu']['usage_pct']:.1f}%")
        elif metrics['system']['cpu']['status'] == 'warning':
            system_health = 80
            summary['warnings'].append(f"CPU usage: {metrics['system']['cpu']['usage_pct']:.1f}%")

        if metrics['system']['memory']['status'] == 'critical':
            system_health = min(system_health, 60)
            summary['critical_alerts'].append(f"Memory usage: {metrics['system']['memory']['usage_pct']:.1f}%")
        elif metrics['system']['memory']['status'] == 'warning':
            system_health = min(system_health, 80)
            summary['warnings'].append(f"Memory usage: {metrics['system']['memory']['usage_pct']:.1f}%")

        if metrics['system']['disk']['status'] == 'critical':
            system_health = min(system_health, 60)
            summary['critical_alerts'].append(f"Disk usage: {metrics['system']['disk']['usage_pct']:.1f}%")
        elif metrics['system']['disk']['status'] == 'warning':
            system_health = min(system_health, 80)
            summary['warnings'].append(f"Disk usage: {metrics['system']['disk']['usage_pct']:.1f}%")

        health_scores['system'] = system_health

        # Overall status
        summary['health_scores'] = health_scores
        avg_health = sum(health_scores.values()) / len(health_scores)

        if avg_health >= 90:
            summary['overall_status'] = 'healthy'
        elif avg_health >= 75:
            summary['overall_status'] = 'warning'
        else:
            summary['overall_status'] = 'critical'

        summary['overall_health_score'] = round(avg_health, 1)

        return summary

    def save_metrics(self, output_file: str = None):
        """Save current metrics to JSON file"""
        metrics = self.collect_all_metrics()

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"metrics_reports/metrics_{timestamp}.json"

        # Create directory if needed
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Save metrics
        with open(output_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        return output_file

    def get_time_series_metrics(self, metric_path: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get time-series data for specific metric path"""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)

        time_series = []
        for metrics in self.metrics_history:
            timestamp = datetime.fromisoformat(metrics['timestamp'])
            if timestamp >= cutoff_time:
                # Navigate metric path (e.g., "api.error_rate")
                value = metrics
                for key in metric_path.split('.'):
                    value = value.get(key, None)
                    if value is None:
                        break

                if value is not None:
                    time_series.append({
                        'timestamp': metrics['timestamp'],
                        'value': value
                    })

        return time_series


if __name__ == '__main__':
    # Example usage
    collector = MetricsCollector()

    print("="*70)
    print("Metrics Collection System - Live Demo")
    print("="*70)

    # Collect all metrics
    print("\n📊 Collecting all metrics...")
    metrics = collector.collect_all_metrics()

    # Get summary
    print("\n📈 Generating summary...")
    summary = collector.get_metrics_summary()

    print(f"\nOverall Status: {summary['overall_status'].upper()}")
    print(f"Overall Health Score: {summary['overall_health_score']}/100")
    print(f"\nHealth Scores:")
    for category, score in summary['health_scores'].items():
        print(f"  {category}: {score}/100")

    if summary['critical_alerts']:
        print(f"\n🚨 Critical Alerts ({len(summary['critical_alerts'])}):")
        for alert in summary['critical_alerts']:
            print(f"  - {alert}")

    if summary['warnings']:
        print(f"\n⚠️  Warnings ({len(summary['warnings'])}):")
        for warning in summary['warnings']:
            print(f"  - {warning}")

    # Save metrics
    output_file = collector.save_metrics()
    print(f"\n💾 Metrics saved: {output_file}")
