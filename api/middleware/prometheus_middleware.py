"""
Prometheus Metrics Middleware for FastAPI

Collects HTTP request metrics for Prometheus monitoring:
- Request duration histograms (for P50, P95, P99 percentiles)
- Request counts by endpoint and status code
- Active requests gauge

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 1.0.0
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge
from loguru import logger


# Prometheus Metrics Definitions
# ================================

# Request Duration Histogram
# Buckets cover typical API response times (5ms to 10s)
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Request Count Counter
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Active Requests Gauge
REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently being processed',
    ['method', 'endpoint']
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware for collecting Prometheus metrics.

    Tracks:
    - Request duration (histogram for percentile calculation)
    - Request count (counter by endpoint and status)
    - Active requests (gauge for current load)

    Usage:
        app.add_middleware(PrometheusMiddleware)
    """

    def __init__(self, app, exclude_paths: set = None):
        """
        Initialize Prometheus middleware.

        Args:
            app: FastAPI/Starlette application
            exclude_paths: Set of paths to exclude from metrics (e.g., {'/metrics', '/health'})
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or {'/metrics', '/metrics/'}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process HTTP request and collect metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Extract request metadata
        method = request.method
        endpoint = request.url.path

        # Skip metrics collection for excluded paths
        if endpoint in self.exclude_paths:
            return await call_next(request)

        # Track request start
        start_time = time.time()

        # Increment active requests gauge
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Record metrics
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).observe(duration)

            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()

            return response

        except Exception as e:
            # Record error metrics (500 Internal Server Error)
            duration = time.time() - start_time
            REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_code=500
            ).observe(duration)

            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=500
            ).inc()

            logger.error(f"Request failed: {method} {endpoint} - {e}")
            raise

        finally:
            # Always decrement active requests (prevent gauge drift)
            REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()


# Utility functions for custom metrics
# =====================================

def record_custom_metric(metric_name: str, value: float, labels: dict = None):
    """
    Record a custom metric (for application-specific metrics).

    Args:
        metric_name: Metric name
        value: Metric value
        labels: Label dictionary (optional)
    """
    # Placeholder for future custom metrics
    # Will be implemented in P4.4 (Custom Application Metrics)
    pass
