"""
Monitoring Adapter Extension (Phase 2.4)

Skeleton implementation for Grafana dashboard integration.

Author: Spock Quant Platform
Date: 2025-10-29
Version: 1.0.0
Status: Skeleton Only (Not Implemented)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime
from loguru import logger


class MonitoringAdapter(ABC):
    """
    Monitoring and metrics adapter for Grafana integration.

    Skeleton implementation - override for Prometheus/Grafana setup.

    Future Implementation:
        - Prometheus Counter for total backfills
        - Histogram for backfill duration
        - Gauge for current API rate limit usage
        - Labels for ticker, region, api_source
    """

    def __init__(self, config: dict):
        """
        Initialize monitoring adapter.

        Args:
            config: Configuration
                - enabled (bool): Whether monitoring is enabled
                - prometheus_host (str): Prometheus server host
                - prometheus_port (int): Prometheus server port
                - metrics_prefix (str): Prefix for metric names
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.prometheus_host = config.get('prometheus_host', 'localhost')
        self.prometheus_port = config.get('prometheus_port', 9090)
        self.metrics_prefix = config.get('metrics_prefix', 'backfill_')

        # In-memory metrics (for skeleton)
        self.metrics = {
            'total_backfills': 0,
            'successful_backfills': 0,
            'failed_backfills': 0,
            'total_records_fetched': 0,
            'total_duration_ms': 0.0
        }

        if self.enabled:
            logger.warning(
                "⚠️ MonitoringAdapter is enabled but not implemented. "
                "This is a skeleton - metrics will not be exported to Prometheus."
            )

    @abstractmethod
    def record_backfill_event(
        self,
        ticker: str,
        region: str,
        api_source: str,
        records_fetched: int,
        duration_ms: float,
        success: bool
    ) -> None:
        """
        Record backfill event for monitoring.

        Args:
            ticker: Stock ticker
            region: Market region
            api_source: API used (pykrx, yfinance, kis)
            records_fetched: Number of records fetched
            duration_ms: Backfill duration in milliseconds
            success: Whether backfill succeeded

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            from prometheus_client import Counter, Histogram

            # Update Prometheus metrics
            backfill_total.labels(
                ticker=ticker,
                region=region,
                api_source=api_source,
                status='success' if success else 'failure'
            ).inc()

            backfill_duration_seconds.labels(
                ticker=ticker,
                region=region,
                api_source=api_source
            ).observe(duration_ms / 1000.0)

            backfill_records_fetched.labels(
                ticker=ticker,
                region=region,
                api_source=api_source
            ).inc(records_fetched)
            ```
        """
        if not self.enabled:
            return

        # Skeleton implementation: just track in-memory
        self.metrics['total_backfills'] += 1
        if success:
            self.metrics['successful_backfills'] += 1
        else:
            self.metrics['failed_backfills'] += 1
        self.metrics['total_records_fetched'] += records_fetched
        self.metrics['total_duration_ms'] += duration_ms

        logger.debug(
            f"📊 Backfill event recorded: {ticker} ({region}) from {api_source} - "
            f"{records_fetched} records in {duration_ms:.1f}ms (success={success})"
        )

    @abstractmethod
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of backfill metrics.

        Returns:
            Dictionary with metrics:
                - total_backfills: Total backfill operations
                - success_rate: Percentage of successful backfills
                - avg_duration_ms: Average backfill duration
                - total_records: Total records fetched

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            from prometheus_client import REGISTRY

            # Query Prometheus for aggregated metrics
            query = f'''
                sum(rate({self.metrics_prefix}backfill_total[5m]))
            '''
            response = requests.get(
                f"http://{self.prometheus_host}:{self.prometheus_port}/api/v1/query",
                params={'query': query}
            )

            return response.json()['data']['result']
            ```
        """
        if not self.enabled:
            return {}

        # Skeleton implementation: return in-memory stats
        total = self.metrics['total_backfills']
        success_rate = (
            (self.metrics['successful_backfills'] / total * 100)
            if total > 0 else 0.0
        )
        avg_duration = (
            (self.metrics['total_duration_ms'] / total)
            if total > 0 else 0.0
        )

        return {
            'total_backfills': total,
            'successful_backfills': self.metrics['successful_backfills'],
            'failed_backfills': self.metrics['failed_backfills'],
            'success_rate': f"{success_rate:.1f}%",
            'avg_duration_ms': f"{avg_duration:.1f}",
            'total_records_fetched': self.metrics['total_records_fetched']
        }

    def is_enabled(self) -> bool:
        """
        Check if monitoring is enabled.

        Returns:
            True if monitoring is enabled
        """
        return self.enabled

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MonitoringAdapter(enabled={self.enabled}, "
            f"prometheus={self.prometheus_host}:{self.prometheus_port}, "
            f"status='skeleton')"
        )
