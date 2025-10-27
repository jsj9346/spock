#!/usr/bin/env python3
"""
FX Collection Prometheus Metrics

Purpose:
- Define Prometheus metrics for FX data collection monitoring
- Track collection performance, data quality, and errors
- Export metrics for Prometheus scraping

Metrics Categories:
1. Collection Performance: duration, throughput, API calls
2. Data Quality: rate changes, quality scores, missing data
3. Error Tracking: error counts by type and currency
4. System Health: cache hit rate, database performance

Usage:
    from monitoring.prometheus.fx_collection_metrics import FXCollectionMetrics

    metrics = FXCollectionMetrics()

    # Record collection duration
    with metrics.collection_duration.labels(currency='USD').time():
        # ... collection logic ...

    # Increment success counter
    metrics.collection_success.labels(currency='USD').inc()

Author: Spock Quant Platform
Created: 2025-10-24
"""

from typing import Optional
import logging

# Optional Prometheus dependency (graceful degradation)
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        Summary,
        generate_latest,
        REGISTRY
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)


class FXCollectionMetrics:
    """
    Prometheus metrics for FX data collection

    Metrics exported:
    - fx_collection_duration_seconds: Collection duration histogram
    - fx_collection_success_total: Successful collections counter
    - fx_collection_errors_total: Error counter by type
    - fx_rate_change_daily_percent: Daily rate change gauge
    - fx_data_quality_score: Data quality score gauge (0-1)
    - fx_missing_days_count: Missing days counter
    - fx_api_calls_total: Total API calls counter
    - fx_cache_hit_rate: Cache hit rate gauge
    - fx_records_inserted_total: Inserted records counter
    - fx_records_updated_total: Updated records counter
    - fx_backfill_progress: Backfill progress gauge (0-100%)
    """

    def __init__(self):
        """
        Initialize FX collection metrics

        Note:
            If prometheus_client is not installed, all metric operations
            become no-ops (graceful degradation)
        """
        self.enabled = HAS_PROMETHEUS

        if not self.enabled:
            logger.warning("⚠️ Prometheus client not available - metrics disabled")
            logger.warning("   Install with: pip install prometheus-client")
            return

        # ================================================================
        # Collection Performance Metrics
        # ================================================================

        # Collection duration (histogram for percentiles)
        self.collection_duration = Histogram(
            'fx_collection_duration_seconds',
            'FX data collection duration in seconds',
            ['currency'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )

        # Collection success counter
        self.collection_success = Counter(
            'fx_collection_success_total',
            'Total successful FX data collections',
            ['currency']
        )

        # Collection error counter (by error type)
        self.collection_errors = Counter(
            'fx_collection_errors_total',
            'Total FX collection errors',
            ['currency', 'error_type']
        )

        # API calls counter
        self.api_calls = Counter(
            'fx_api_calls_total',
            'Total BOK API calls made',
            ['currency', 'endpoint']
        )

        # ================================================================
        # Data Quality Metrics
        # ================================================================

        # Daily rate change percentage
        self.rate_change_daily = Gauge(
            'fx_rate_change_daily_percent',
            'Daily FX rate change percentage',
            ['currency']
        )

        # Data quality score (0.0 - 1.0)
        self.data_quality_score = Gauge(
            'fx_data_quality_score',
            'FX data quality score (0.0=poor, 1.0=excellent)',
            ['currency']
        )

        # Missing days count
        self.missing_days_count = Gauge(
            'fx_missing_days_count',
            'Number of missing days in FX data (last 30 days)',
            ['currency']
        )

        # Current USD-normalized rate
        self.current_usd_rate = Gauge(
            'fx_current_usd_rate',
            'Current USD-normalized exchange rate',
            ['currency']
        )

        # ================================================================
        # Database Performance Metrics
        # ================================================================

        # Records inserted
        self.records_inserted = Counter(
            'fx_records_inserted_total',
            'Total FX records inserted',
            ['currency']
        )

        # Records updated
        self.records_updated = Counter(
            'fx_records_updated_total',
            'Total FX records updated',
            ['currency']
        )

        # Database query duration
        self.db_query_duration = Histogram(
            'fx_db_query_duration_seconds',
            'FX database query duration',
            ['operation'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        )

        # ================================================================
        # Cache Performance Metrics
        # ================================================================

        # Cache hit rate
        self.cache_hit_rate = Gauge(
            'fx_cache_hit_rate',
            'FX exchange rate cache hit rate (0.0-1.0)',
            ['currency']
        )

        # Cache size
        self.cache_size = Gauge(
            'fx_cache_size_bytes',
            'FX exchange rate cache size in bytes'
        )

        # ================================================================
        # Backfill Progress Metrics
        # ================================================================

        # Backfill progress percentage
        self.backfill_progress = Gauge(
            'fx_backfill_progress_percent',
            'FX historical backfill progress percentage (0-100)',
            ['currency']
        )

        # Backfill records processed
        self.backfill_records_processed = Counter(
            'fx_backfill_records_processed_total',
            'Total records processed during backfill',
            ['currency']
        )

        # Backfill duration
        self.backfill_duration = Histogram(
            'fx_backfill_duration_seconds',
            'FX backfill duration in seconds',
            ['currency'],
            buckets=[1, 10, 60, 300, 600, 1800, 3600]
        )

        # ================================================================
        # System Health Metrics
        # ================================================================

        # Last successful collection timestamp
        self.last_success_timestamp = Gauge(
            'fx_last_success_timestamp_seconds',
            'Timestamp of last successful FX collection',
            ['currency']
        )

        # Consecutive failures
        self.consecutive_failures = Gauge(
            'fx_consecutive_failures_count',
            'Number of consecutive FX collection failures',
            ['currency']
        )

        # BOK API health (0=down, 1=up)
        self.bok_api_health = Gauge(
            'fx_bok_api_health',
            'BOK API health status (0=down, 1=up)'
        )

        # PostgreSQL health (0=down, 1=up)
        self.postgres_health = Gauge(
            'fx_postgres_health',
            'PostgreSQL database health status (0=down, 1=up)'
        )

        # ================================================================
        # Info Metrics (metadata)
        # ================================================================

        # Build info
        self.build_info = Info(
            'fx_collector_build',
            'FX collector build information'
        )

        # Set build info
        self.build_info.info({
            'version': '1.0.0',
            'component': 'fx_data_collector',
            'phase': 'Phase 1-C/1-D/1-E'
        })

        logger.info("✅ FX Collection Prometheus metrics initialized")
        logger.info(f"   Total metrics: {len(REGISTRY._collector_to_names)}")

    # ================================================================
    # Helper Methods
    # ================================================================

    def record_collection_success(self, currency: str, duration: float):
        """
        Record successful collection with metrics update

        Args:
            currency: Currency code
            duration: Collection duration in seconds
        """
        if not self.enabled:
            return

        self.collection_success.labels(currency=currency).inc()
        self.collection_duration.labels(currency=currency).observe(duration)

        import time
        self.last_success_timestamp.labels(currency=currency).set(time.time())
        self.consecutive_failures.labels(currency=currency).set(0)

    def record_collection_error(self, currency: str, error_type: str):
        """
        Record collection error

        Args:
            currency: Currency code
            error_type: Error type (e.g., 'APIError', 'DatabaseError')
        """
        if not self.enabled:
            return

        self.collection_errors.labels(
            currency=currency,
            error_type=error_type
        ).inc()

        # Increment consecutive failures
        current_failures = self.consecutive_failures.labels(currency=currency)._value.get()
        self.consecutive_failures.labels(currency=currency).set(current_failures + 1)

    def record_api_call(self, currency: str, endpoint: str = 'StatisticSearch'):
        """
        Record BOK API call

        Args:
            currency: Currency code
            endpoint: API endpoint name
        """
        if not self.enabled:
            return

        self.api_calls.labels(currency=currency, endpoint=endpoint).inc()

    def update_data_quality(self, currency: str, quality_score: float):
        """
        Update data quality score

        Args:
            currency: Currency code
            quality_score: Quality score (0.0 - 1.0)
        """
        if not self.enabled:
            return

        self.data_quality_score.labels(currency=currency).set(quality_score)

    def update_rate_change(self, currency: str, change_percent: float):
        """
        Update daily rate change percentage

        Args:
            currency: Currency code
            change_percent: Rate change percentage (e.g., 1.5 for +1.5%)
        """
        if not self.enabled:
            return

        self.rate_change_daily.labels(currency=currency).set(change_percent)

    def update_current_rate(self, currency: str, usd_rate: float):
        """
        Update current USD-normalized rate

        Args:
            currency: Currency code
            usd_rate: USD-normalized exchange rate
        """
        if not self.enabled:
            return

        self.current_usd_rate.labels(currency=currency).set(usd_rate)

    def set_bok_api_health(self, is_healthy: bool):
        """
        Update BOK API health status

        Args:
            is_healthy: True if API is healthy, False otherwise
        """
        if not self.enabled:
            return

        self.bok_api_health.set(1 if is_healthy else 0)

    def set_postgres_health(self, is_healthy: bool):
        """
        Update PostgreSQL health status

        Args:
            is_healthy: True if database is healthy, False otherwise
        """
        if not self.enabled:
            return

        self.postgres_health.set(1 if is_healthy else 0)

    def get_metrics_text(self) -> str:
        """
        Get metrics in Prometheus text format

        Returns:
            Prometheus metrics text (for HTTP endpoint)
        """
        if not self.enabled:
            return "# Prometheus client not available\n"

        return generate_latest(REGISTRY).decode('utf-8')


# ================================================================
# Global Singleton Instance
# ================================================================

_metrics_instance: Optional[FXCollectionMetrics] = None


def get_metrics() -> FXCollectionMetrics:
    """
    Get global FX collection metrics instance (singleton)

    Returns:
        FXCollectionMetrics instance
    """
    global _metrics_instance

    if _metrics_instance is None:
        _metrics_instance = FXCollectionMetrics()

    return _metrics_instance


# ================================================================
# Standalone Testing
# ================================================================

if __name__ == '__main__':
    """
    Test metrics initialization and export
    """
    print("=" * 70)
    print("FX Collection Prometheus Metrics - Test")
    print("=" * 70)

    # Initialize metrics
    metrics = get_metrics()

    if not metrics.enabled:
        print("❌ Prometheus client not available")
        print("   Install with: pip install prometheus-client")
        exit(1)

    # Simulate collection
    print("\n📊 Simulating FX collection metrics...")

    metrics.record_collection_success('USD', duration=1.234)
    metrics.update_data_quality('USD', quality_score=1.0)
    metrics.update_rate_change('USD', change_percent=0.5)
    metrics.update_current_rate('USD', usd_rate=1.0)
    metrics.record_api_call('USD', endpoint='StatisticSearch')

    metrics.record_collection_success('CNY', duration=2.567)
    metrics.update_data_quality('CNY', quality_score=0.9)
    metrics.update_rate_change('CNY', change_percent=-0.3)
    metrics.update_current_rate('CNY', usd_rate=0.138462)

    # Simulate error
    metrics.record_collection_error('JPY', error_type='APITimeout')

    # Health checks
    metrics.set_bok_api_health(True)
    metrics.set_postgres_health(True)

    print("✅ Metrics recorded successfully")

    # Export metrics
    print("\n📤 Exporting Prometheus metrics...")
    print("=" * 70)

    metrics_text = metrics.get_metrics_text()

    # Print sample metrics (first 50 lines)
    lines = metrics_text.split('\n')
    for line in lines[:50]:
        if line and not line.startswith('#'):
            print(line)

    print(f"\n... (Total: {len(lines)} lines)")
    print("=" * 70)

    print("\n✅ Test completed successfully")
    print(f"   Total metrics defined: {len([line for line in lines if not line.startswith('#') and line.strip()])}")
