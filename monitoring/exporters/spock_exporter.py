#!/usr/bin/env python3
"""
Spock Trading System - Prometheus Metrics Exporter

Exposes Spock system metrics for Prometheus scraping.

Usage:
    python3 spock_exporter.py --port 8000

Metrics exposed:
    - OHLCV data quality metrics
    - API health and performance
    - Database metrics
    - System health metrics

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import time
import argparse
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================================
# Prometheus Metrics Definitions
# ========================================

# OHLCV Data Metrics
ohlcv_rows_total = Gauge('spock_ohlcv_rows_total', 'Total OHLCV rows', ['region'])
ohlcv_null_regions = Gauge('spock_ohlcv_null_regions_total', 'Number of OHLCV rows with NULL region')
cross_region_contamination = Gauge('spock_cross_region_contamination_total', 'Tickers present in multiple regions')
unique_tickers = Gauge('spock_unique_tickers_total', 'Unique tickers per region', ['region'])
last_data_update = Gauge('spock_last_data_update_timestamp', 'Timestamp of last data update', ['region'])

# Data Collection Metrics
data_collection_attempts = Counter('spock_data_collection_attempts_total', 'Data collection attempts', ['region'])
data_collection_success = Counter('spock_data_collection_success_total', 'Successful data collections', ['region'])
data_collection_failed = Counter('spock_data_collection_failed_total', 'Failed data collections', ['region'])

# API Metrics
api_requests_total = Counter('spock_api_requests_total', 'Total API requests', ['region', 'endpoint'])
api_requests_failed = Counter('spock_api_requests_failed_total', 'Failed API requests', ['region', 'endpoint'])
api_request_duration = Histogram('spock_api_request_duration_seconds', 'API request duration', ['region', 'endpoint'])
api_rate_limit_usage = Gauge('spock_api_rate_limit_usage_percent', 'API rate limit usage percentage', ['region'])

# Database Metrics
database_size = Gauge('spock_database_size_bytes', 'Database size in bytes')
db_query_duration = Histogram('spock_db_query_duration_seconds', 'Database query duration', ['query_type'])
last_backup_timestamp = Gauge('spock_last_backup_timestamp', 'Timestamp of last database backup')

# System Metrics
memory_usage_percent = Gauge('spock_memory_usage_percent', 'Memory usage percentage')
disk_free_bytes = Gauge('spock_disk_free_bytes', 'Free disk space in bytes')

# Trading Metrics
orders_total = Counter('spock_orders_total', 'Total orders placed', ['region', 'ticker'])
orders_failed = Counter('spock_orders_failed_total', 'Failed orders', ['region', 'ticker'])
position_size_percent = Gauge('spock_position_size_percent', 'Position size as percentage of max', ['ticker'])

# System Info
system_info = Info('spock_system', 'Spock Trading System information')


class SpockMetricsExporter:
    """Prometheus metrics exporter for Spock Trading System"""

    def __init__(self, db_path: str = '/Users/13ruce/spock/data/spock_local.db'):
        """
        Initialize metrics exporter

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.db = SQLiteDatabaseManager(db_path=db_path)
        self.regions = ['KR', 'US', 'CN', 'HK', 'JP', 'VN']

        # Set system info
        system_info.info({
            'version': '1.0.0',
            'database': db_path,
            'regions': ','.join(self.regions)
        })

        logger.info(f"Initialized Spock metrics exporter with database: {db_path}")

    def collect_ohlcv_metrics(self):
        """Collect OHLCV data quality metrics"""
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            # Total rows per region
            for region in self.regions:
                cursor.execute("""
                    SELECT COUNT(*) FROM ohlcv_data WHERE region = ?
                """, (region,))
                count = cursor.fetchone()[0]
                ohlcv_rows_total.labels(region=region).set(count)

            # NULL regions count
            cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL")
            null_count = cursor.fetchone()[0]
            ohlcv_null_regions.set(null_count)

            # Cross-region contamination (tickers in multiple regions)
            cursor.execute("""
                SELECT COUNT(DISTINCT ticker)
                FROM (
                    SELECT ticker, COUNT(DISTINCT region) as region_count
                    FROM ohlcv_data
                    WHERE region IS NOT NULL
                    GROUP BY ticker
                    HAVING region_count > 1
                )
            """)
            contamination = cursor.fetchone()[0]
            cross_region_contamination.set(contamination)

            # Unique tickers per region
            for region in self.regions:
                cursor.execute("""
                    SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE region = ?
                """, (region,))
                count = cursor.fetchone()[0]
                unique_tickers.labels(region=region).set(count)

            # Last data update timestamp per region
            for region in self.regions:
                cursor.execute("""
                    SELECT MAX(created_at) FROM ohlcv_data WHERE region = ?
                """, (region,))
                result = cursor.fetchone()
                if result and result[0]:
                    try:
                        last_update = datetime.fromisoformat(result[0])
                        last_data_update.labels(region=region).set(last_update.timestamp())
                    except:
                        pass

            conn.close()

        except Exception as e:
            logger.error(f"Error collecting OHLCV metrics: {e}")

    def collect_database_metrics(self):
        """Collect database metrics"""
        try:
            # Database file size
            if os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
                database_size.set(size)

            # Last backup timestamp
            backup_dir = os.path.dirname(self.db_path) + '/backups'
            if os.path.exists(backup_dir):
                backups = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
                if backups:
                    latest_backup = max(backups)
                    backup_path = os.path.join(backup_dir, latest_backup)
                    backup_time = os.path.getmtime(backup_path)
                    last_backup_timestamp.set(backup_time)

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")

    def collect_system_metrics(self):
        """Collect system health metrics"""
        try:
            import psutil

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_percent.set(memory.percent)

            # Disk free space
            disk = psutil.disk_usage(os.path.dirname(self.db_path))
            disk_free_bytes.set(disk.free)

        except ImportError:
            logger.warning("psutil not installed, skipping system metrics")
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    def collect_api_metrics_from_logs(self):
        """
        Collect API metrics from kis_api_logs table

        Note: This reads historical data from logs. For real-time metrics,
        the adapters should be instrumented to call prometheus_client directly.
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            # Check if kis_api_logs table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='kis_api_logs'
            """)

            if cursor.fetchone():
                # Count API requests by region and status (last 1 hour)
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()

                cursor.execute("""
                    SELECT
                        region,
                        endpoint,
                        status,
                        COUNT(*) as count
                    FROM kis_api_logs
                    WHERE created_at > ?
                    GROUP BY region, endpoint, status
                """, (one_hour_ago,))

                for row in cursor.fetchall():
                    region = row[0] if row[0] else 'UNKNOWN'
                    endpoint = row[1] if row[1] else 'unknown'
                    status = row[2]
                    count = row[3]

                    # Note: Counters should only go up, so we can't set them directly
                    # This is a limitation of reading from logs
                    # For proper metrics, adapters should increment counters directly

            conn.close()

        except Exception as e:
            logger.error(f"Error collecting API metrics from logs: {e}")

    def collect_all_metrics(self):
        """Collect all metrics"""
        logger.info("Collecting metrics...")

        self.collect_ohlcv_metrics()
        self.collect_database_metrics()
        self.collect_system_metrics()
        self.collect_api_metrics_from_logs()

        logger.info("Metrics collection complete")

    def run(self, port: int = 8000, interval: int = 15):
        """
        Start metrics exporter HTTP server

        Args:
            port: HTTP server port
            interval: Metrics collection interval (seconds)
        """
        # Start HTTP server for Prometheus scraping
        start_http_server(port)
        logger.info(f"Metrics exporter started on port {port}")
        logger.info(f"Metrics available at http://localhost:{port}/metrics")

        # Collect metrics periodically
        try:
            while True:
                self.collect_all_metrics()
                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Shutting down metrics exporter...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Spock Trading System - Prometheus Metrics Exporter'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='HTTP server port (default: 8000)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=15,
        help='Metrics collection interval in seconds (default: 15)'
    )
    parser.add_argument(
        '--db-path',
        default='/Users/13ruce/spock/data/spock_local.db',
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Check if database exists
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found: {args.db_path}")
        sys.exit(1)

    # Initialize and run exporter
    exporter = SpockMetricsExporter(db_path=args.db_path)
    exporter.run(port=args.port, interval=args.interval)


if __name__ == '__main__':
    main()
