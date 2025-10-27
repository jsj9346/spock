"""
Performance Tracker - Backtesting Performance Monitoring

Tracks and analyzes backtesting engine performance metrics including execution
time, memory usage, cache efficiency, and throughput.

Purpose:
    - Benchmark execution times for both engines
    - Memory usage profiling
    - Cache hit rate monitoring
    - Identify performance bottlenecks
    - Track performance trends over time

Usage:
    from modules.backtesting.validation import PerformanceTracker

    tracker = PerformanceTracker()
    with tracker.track("rsi_backtest"):
        result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)

    metrics = tracker.get_metrics("rsi_backtest")
    print(f"Execution time: {metrics.execution_time:.3f}s")
"""

import time
import psutil
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from contextlib import contextmanager
from loguru import logger


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation."""

    operation_name: str
    timestamp: datetime
    execution_time: float
    memory_usage_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None


class PerformanceTracker:
    """
    Backtesting performance monitoring.

    Tracks execution time, memory usage, CPU usage, and other performance
    metrics for backtesting operations.

    Example:
        >>> tracker = PerformanceTracker()
        >>>
        >>> # Track a single operation
        >>> with tracker.track("my_backtest"):
        ...     result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)
        >>>
        >>> # Get metrics
        >>> metrics = tracker.get_metrics("my_backtest")
        >>> print(f"Execution time: {metrics[0].execution_time:.3f}s")
        >>>
        >>> # Get performance trend
        >>> trend = tracker.get_trend("my_backtest")
    """

    def __init__(self):
        """Initialize PerformanceTracker."""
        self.metrics_history: Dict[str, List[PerformanceMetrics]] = {}
        self.process = psutil.Process()
        logger.info("PerformanceTracker initialized")

    @contextmanager
    def track(self, operation_name: str):
        """
        Context manager for tracking operation performance.

        Args:
            operation_name: Name of operation being tracked

        Example:
            >>> with tracker.track("rsi_backtest"):
            ...     result = runner.run(...)
        """
        # Record start state
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = self.process.cpu_percent()

        error_message = None
        success = True

        try:
            yield

        except Exception as e:
            error_message = str(e)
            success = False
            raise

        finally:
            # Record end state
            execution_time = time.time() - start_time
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            cpu_percent = self.process.cpu_percent()

            # Create metrics
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                timestamp=datetime.now(),
                execution_time=execution_time,
                memory_usage_mb=end_memory - start_memory,
                cpu_percent=cpu_percent,
                success=success,
                error_message=error_message
            )

            # Store metrics
            if operation_name not in self.metrics_history:
                self.metrics_history[operation_name] = []
            self.metrics_history[operation_name].append(metrics)

            # Log
            status = "✅" if success else "❌"
            logger.info(
                f"{status} {operation_name}: "
                f"time={execution_time:.3f}s, "
                f"memory={metrics.memory_usage_mb:.1f}MB, "
                f"cpu={cpu_percent:.1f}%"
            )

    def get_metrics(self, operation_name: str) -> List[PerformanceMetrics]:
        """Get all metrics for an operation."""
        return self.metrics_history.get(operation_name, [])

    def get_latest(self, operation_name: str) -> Optional[PerformanceMetrics]:
        """Get latest metrics for an operation."""
        metrics = self.get_metrics(operation_name)
        return metrics[-1] if metrics else None

    def get_average_time(self, operation_name: str) -> float:
        """Get average execution time for an operation."""
        metrics = self.get_metrics(operation_name)
        if not metrics:
            return 0.0
        return sum(m.execution_time for m in metrics) / len(metrics)
