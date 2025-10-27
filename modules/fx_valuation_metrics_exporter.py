#!/usr/bin/env python3
"""
FX Valuation Metrics Exporter - Phase 3-E

Purpose:
    Expose FX valuation metrics to Prometheus for alerting and monitoring.
    Extends existing metrics_exporter.py with valuation-specific metrics.

Metrics Exposed:
    - fx_valuation_attractiveness_score (gauge)
    - fx_valuation_confidence (gauge)
    - fx_valuation_return_1m, return_3m, return_6m, return_12m (gauges)
    - fx_valuation_trend_score (gauge)
    - fx_valuation_momentum_acceleration (gauge)
    - fx_valuation_volatility (gauge)
    - fx_valuation_data_quality (gauge with label)
    - fx_valuation_last_update_timestamp (gauge)
    - fx_valuation_analysis_total (counter)
    - fx_valuation_analysis_success_total (counter)
    - fx_valuation_analysis_errors_total (counter)
    - fx_valuation_analysis_duration_seconds (histogram)

Integration:
    - Works alongside existing metrics_exporter.py
    - Queries PostgreSQL fx_valuation_signals table
    - Updates metrics every 60 seconds
    - Exposed on port 8000 (same as main exporter)

Usage:
    # Start exporter (integrated into main metrics_exporter.py)
    python3 modules/metrics_exporter.py

    # Or standalone for testing
    python3 modules/fx_valuation_metrics_exporter.py

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prometheus_client import Gauge, Counter, Histogram, start_http_server
from modules.db_manager_postgres import PostgresDatabaseManager

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# ================================================================
# Prometheus Metrics Definitions
# ================================================================

# Valuation Score Metrics (per currency)
FX_ATTRACTIVENESS = Gauge(
    'fx_valuation_attractiveness_score',
    'Currency attractiveness score (0-100 scale)',
    ['currency', 'region']
)

FX_CONFIDENCE = Gauge(
    'fx_valuation_confidence',
    'Confidence score for valuation analysis (0.0-1.0 scale)',
    ['currency', 'region']
)

FX_RETURN_1M = Gauge(
    'fx_valuation_return_1m',
    '1-month return (percentage as decimal)',
    ['currency', 'region']
)

FX_RETURN_3M = Gauge(
    'fx_valuation_return_3m',
    '3-month return (percentage as decimal)',
    ['currency', 'region']
)

FX_RETURN_6M = Gauge(
    'fx_valuation_return_6m',
    '6-month return (percentage as decimal)',
    ['currency', 'region']
)

FX_RETURN_12M = Gauge(
    'fx_valuation_return_12m',
    '12-month return (percentage as decimal)',
    ['currency', 'region']
)

FX_TREND_SCORE = Gauge(
    'fx_valuation_trend_score',
    'Trend strength score (0-100 scale)',
    ['currency', 'region']
)

FX_MOMENTUM = Gauge(
    'fx_valuation_momentum_acceleration',
    'Momentum score (0-100 scale)',
    ['currency', 'region']
)

FX_VOLATILITY = Gauge(
    'fx_valuation_volatility',
    '60-day annualized volatility (percentage as decimal)',
    ['currency', 'region']
)

# Data Quality Metrics
FX_DATA_QUALITY = Gauge(
    'fx_valuation_data_quality',
    'Data quality (1=GOOD, 0.5=PARTIAL, 0.25=STALE, 0=MISSING)',
    ['currency', 'region', 'data_quality']
)

FX_LAST_UPDATE = Gauge(
    'fx_valuation_last_update_timestamp',
    'Unix timestamp of last valuation update',
    ['currency', 'region']
)

# Analysis Performance Metrics
FX_ANALYSIS_TOTAL = Counter(
    'fx_valuation_analysis_total',
    'Total number of valuation analyses attempted',
    ['currency']
)

FX_ANALYSIS_SUCCESS = Counter(
    'fx_valuation_analysis_success_total',
    'Total number of successful valuation analyses',
    ['currency']
)

FX_ANALYSIS_ERRORS = Counter(
    'fx_valuation_analysis_errors_total',
    'Total number of failed valuation analyses',
    ['currency', 'error_type']
)

FX_ANALYSIS_DURATION = Histogram(
    'fx_valuation_analysis_duration_seconds',
    'Duration of valuation analysis',
    ['currency'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)


# ================================================================
# FX Valuation Metrics Exporter
# ================================================================

class FXValuationMetricsExporter:
    """
    Prometheus metrics exporter for FX valuation data.

    Queries PostgreSQL database and exposes metrics for Prometheus scraping.
    """

    SUPPORTED_CURRENCIES = ['USD', 'HKD', 'CNY', 'JPY', 'VND']

    DATA_QUALITY_MAP = {
        'GOOD': 1.0,
        'PARTIAL': 0.5,
        'STALE': 0.25,
        'MISSING': 0.0
    }

    def __init__(self):
        """Initialize metrics exporter with database connection."""
        self.db = PostgresDatabaseManager()
        logger.info("FX Valuation Metrics Exporter initialized")

    def fetch_latest_valuation_data(self) -> List[Dict]:
        """
        Fetch latest valuation data for all currencies.

        Returns:
            List of dictionaries with valuation metrics
        """
        query = """
            SELECT
                currency,
                region,
                date,
                usd_rate,
                return_1m,
                return_3m,
                return_6m,
                return_12m,
                trend_score,
                momentum_acceleration,
                volatility,
                attractiveness_score,
                confidence,
                data_quality,
                updated_at
            FROM fx_valuation_signals
            WHERE date = (SELECT MAX(date) FROM fx_valuation_signals)
            ORDER BY currency
        """

        try:
            results = self.db.execute_query(query)

            if not results:
                logger.warning("No valuation data found in database")
                return []

            # Convert to list of dicts
            columns = [
                'currency', 'region', 'date', 'usd_rate',
                'return_1m', 'return_3m', 'return_6m', 'return_12m',
                'trend_score', 'momentum_acceleration', 'volatility',
                'attractiveness_score', 'confidence', 'data_quality', 'updated_at'
            ]

            data = []
            for row in results:
                row_dict = dict(zip(columns, row))
                data.append(row_dict)

            logger.info(f"Fetched valuation data for {len(data)} currencies")
            return data

        except Exception as e:
            logger.error(f"Error fetching valuation data: {e}", exc_info=True)
            return []

    def update_metrics(self):
        """
        Update Prometheus metrics with latest valuation data.

        This method is called periodically to refresh all metrics.
        """
        try:
            start_time = time.time()

            # Fetch latest data
            data = self.fetch_latest_valuation_data()

            if not data:
                logger.warning("No data to update metrics")
                return

            # Update metrics for each currency
            for row in data:
                currency = row['currency']
                region = row['region']

                # Valuation scores
                if row['attractiveness_score'] is not None:
                    FX_ATTRACTIVENESS.labels(currency=currency, region=region).set(
                        float(row['attractiveness_score'])
                    )

                if row['confidence'] is not None:
                    FX_CONFIDENCE.labels(currency=currency, region=region).set(
                        float(row['confidence'])
                    )

                # Returns
                if row['return_1m'] is not None:
                    FX_RETURN_1M.labels(currency=currency, region=region).set(
                        float(row['return_1m'])
                    )

                if row['return_3m'] is not None:
                    FX_RETURN_3M.labels(currency=currency, region=region).set(
                        float(row['return_3m'])
                    )

                if row['return_6m'] is not None:
                    FX_RETURN_6M.labels(currency=currency, region=region).set(
                        float(row['return_6m'])
                    )

                if row['return_12m'] is not None:
                    FX_RETURN_12M.labels(currency=currency, region=region).set(
                        float(row['return_12m'])
                    )

                # Trend and momentum
                if row['trend_score'] is not None:
                    FX_TREND_SCORE.labels(currency=currency, region=region).set(
                        float(row['trend_score'])
                    )

                if row['momentum_acceleration'] is not None:
                    FX_MOMENTUM.labels(currency=currency, region=region).set(
                        float(row['momentum_acceleration'])
                    )

                # Volatility
                if row['volatility'] is not None:
                    FX_VOLATILITY.labels(currency=currency, region=region).set(
                        float(row['volatility'])
                    )

                # Data quality
                data_quality = row['data_quality']
                quality_value = self.DATA_QUALITY_MAP.get(data_quality, 0.0)
                FX_DATA_QUALITY.labels(
                    currency=currency,
                    region=region,
                    data_quality=data_quality
                ).set(quality_value)

                # Last update timestamp
                if row['updated_at']:
                    timestamp = row['updated_at'].timestamp()
                    FX_LAST_UPDATE.labels(currency=currency, region=region).set(timestamp)

            duration = time.time() - start_time
            logger.info(f"Metrics updated successfully in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Error updating metrics: {e}", exc_info=True)

    def record_analysis_attempt(self, currency: str):
        """Record that an analysis was attempted."""
        FX_ANALYSIS_TOTAL.labels(currency=currency).inc()

    def record_analysis_success(self, currency: str, duration: float):
        """Record successful analysis."""
        FX_ANALYSIS_SUCCESS.labels(currency=currency).inc()
        FX_ANALYSIS_DURATION.labels(currency=currency).observe(duration)

    def record_analysis_error(self, currency: str, error_type: str):
        """Record analysis error."""
        FX_ANALYSIS_ERRORS.labels(currency=currency, error_type=error_type).inc()

    def run_exporter(self, port: int = 8001, update_interval: int = 60):
        """
        Run metrics exporter server.

        Args:
            port: Port to expose metrics on (default: 8001)
            update_interval: Seconds between metric updates (default: 60)
        """
        # Start HTTP server for Prometheus scraping
        start_http_server(port)
        logger.info(f"FX Valuation Metrics Exporter started on port {port}")
        logger.info(f"Metrics endpoint: http://localhost:{port}/metrics")
        logger.info(f"Update interval: {update_interval}s")

        # Continuous update loop
        while True:
            try:
                self.update_metrics()
                time.sleep(update_interval)
            except KeyboardInterrupt:
                logger.info("Exporter stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}", exc_info=True)
                time.sleep(update_interval)


# ================================================================
# Integration with Main Metrics Exporter
# ================================================================

def integrate_with_main_exporter():
    """
    Integration function for main metrics_exporter.py.

    This function should be called from the main exporter to add
    FX valuation metrics alongside existing metrics.

    Usage in metrics_exporter.py:
        from modules.fx_valuation_metrics_exporter import integrate_with_main_exporter

        # In main exporter loop:
        fx_exporter = integrate_with_main_exporter()
        fx_exporter.update_metrics()  # Call periodically
    """
    exporter = FXValuationMetricsExporter()
    logger.info("FX Valuation metrics integrated with main exporter")
    return exporter


# ================================================================
# Standalone Execution (Testing)
# ================================================================

def main():
    """
    Standalone execution for testing.

    Starts metrics exporter on port 8001 with 60-second updates.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='FX Valuation Metrics Exporter for Prometheus'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8001,
        help='Port to expose metrics on (default: 8001)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Update interval in seconds (default: 60)'
    )

    args = parser.parse_args()

    exporter = FXValuationMetricsExporter()
    exporter.run_exporter(port=args.port, update_interval=args.interval)


if __name__ == '__main__':
    main()
