"""
Test Performance Tracker

Tests for backtesting performance monitoring including execution time,
memory usage, and CPU tracking.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/validation/test_performance_tracker.py -v
"""

import pytest
import time
from datetime import datetime

from modules.backtesting.validation.performance_tracker import (
    PerformanceTracker,
    PerformanceMetrics
)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestPerformanceTrackerBasics:
    """Test basic PerformanceTracker functionality."""

    def test_initialization(self):
        """Test PerformanceTracker initialization."""
        tracker = PerformanceTracker()

        assert tracker.metrics_history == {}
        assert tracker.process is not None

    def test_metrics_history_empty_on_init(self):
        """Test metrics history is empty on initialization."""
        tracker = PerformanceTracker()

        assert len(tracker.metrics_history) == 0

    def test_process_initialized(self):
        """Test psutil process is initialized."""
        tracker = PerformanceTracker()

        # Process should be current Python process
        assert tracker.process.pid > 0


# ============================================================================
# PerformanceMetrics Dataclass Tests
# ============================================================================

class TestPerformanceMetricsDataclass:
    """Test PerformanceMetrics dataclass."""

    def test_metrics_dataclass_creation(self):
        """Test PerformanceMetrics dataclass creation."""
        metrics = PerformanceMetrics(
            operation_name="test_op",
            timestamp=datetime.now(),
            execution_time=1.234,
            memory_usage_mb=12.5,
            cpu_percent=45.6,
            success=True,
            error_message=None
        )

        assert metrics.operation_name == "test_op"
        assert isinstance(metrics.timestamp, datetime)
        assert metrics.execution_time == 1.234
        assert metrics.memory_usage_mb == 12.5
        assert metrics.cpu_percent == 45.6
        assert metrics.success is True
        assert metrics.error_message is None

    def test_metrics_with_error_message(self):
        """Test PerformanceMetrics with error message."""
        metrics = PerformanceMetrics(
            operation_name="failed_op",
            timestamp=datetime.now(),
            execution_time=0.5,
            memory_usage_mb=5.0,
            cpu_percent=20.0,
            success=False,
            error_message="Operation failed"
        )

        assert metrics.success is False
        assert metrics.error_message == "Operation failed"


# ============================================================================
# Context Manager Tests
# ============================================================================

class TestContextManager:
    """Test track context manager functionality."""

    def test_track_successful_operation(self):
        """Test tracking a successful operation."""
        tracker = PerformanceTracker()

        with tracker.track("test_operation"):
            time.sleep(0.01)  # Small delay to measure time

        # Operation should be recorded
        assert "test_operation" in tracker.metrics_history
        assert len(tracker.metrics_history["test_operation"]) == 1

    def test_track_operation_with_exception(self):
        """Test tracking an operation that raises an exception."""
        tracker = PerformanceTracker()

        with pytest.raises(ValueError):
            with tracker.track("failing_operation"):
                raise ValueError("Test error")

        # Operation should still be recorded
        assert "failing_operation" in tracker.metrics_history
        metrics = tracker.metrics_history["failing_operation"][0]
        assert metrics.success is False
        assert "Test error" in metrics.error_message

    def test_track_records_execution_time(self):
        """Test that track records execution time."""
        tracker = PerformanceTracker()

        with tracker.track("timed_operation"):
            time.sleep(0.05)  # 50ms delay

        metrics = tracker.get_latest("timed_operation")
        assert metrics is not None
        assert metrics.execution_time >= 0.04  # Should be at least 40ms
        assert metrics.execution_time < 1.0    # Should be less than 1s

    def test_track_records_memory_usage(self):
        """Test that track records memory usage."""
        tracker = PerformanceTracker()

        with tracker.track("memory_operation"):
            pass

        metrics = tracker.get_latest("memory_operation")
        assert metrics is not None
        assert isinstance(metrics.memory_usage_mb, float)

    def test_track_records_cpu_percent(self):
        """Test that track records CPU percentage."""
        tracker = PerformanceTracker()

        with tracker.track("cpu_operation"):
            pass

        metrics = tracker.get_latest("cpu_operation")
        assert metrics is not None
        assert isinstance(metrics.cpu_percent, float)
        assert metrics.cpu_percent >= 0.0

    def test_track_successful_operation_sets_success_true(self):
        """Test successful operation sets success flag to True."""
        tracker = PerformanceTracker()

        with tracker.track("success_operation"):
            pass

        metrics = tracker.get_latest("success_operation")
        assert metrics.success is True
        assert metrics.error_message is None

    def test_track_failed_operation_sets_success_false(self):
        """Test failed operation sets success flag to False."""
        tracker = PerformanceTracker()

        with pytest.raises(RuntimeError):
            with tracker.track("failure_operation"):
                raise RuntimeError("Intentional failure")

        metrics = tracker.get_latest("failure_operation")
        assert metrics.success is False

    def test_track_captures_error_message_on_exception(self):
        """Test that error message is captured on exception."""
        tracker = PerformanceTracker()

        with pytest.raises(ValueError):
            with tracker.track("error_operation"):
                raise ValueError("Custom error message")

        metrics = tracker.get_latest("error_operation")
        assert metrics.error_message == "Custom error message"

    def test_track_raises_exception(self):
        """Test that exceptions are propagated after tracking."""
        tracker = PerformanceTracker()

        with pytest.raises(KeyError):
            with tracker.track("exception_operation"):
                raise KeyError("Test key error")

        # Exception should propagate, but metrics still recorded
        assert "exception_operation" in tracker.metrics_history

    def test_track_timestamp_recorded(self):
        """Test that timestamp is recorded."""
        tracker = PerformanceTracker()
        before = datetime.now()

        with tracker.track("timestamp_operation"):
            pass

        after = datetime.now()
        metrics = tracker.get_latest("timestamp_operation")

        assert metrics.timestamp >= before
        assert metrics.timestamp <= after


# ============================================================================
# Metrics Storage Tests
# ============================================================================

class TestMetricsStorage:
    """Test metrics storage and retrieval."""

    def test_track_appends_to_history(self):
        """Test that track appends to history."""
        tracker = PerformanceTracker()

        with tracker.track("append_test"):
            pass

        assert len(tracker.metrics_history["append_test"]) == 1

        with tracker.track("append_test"):
            pass

        assert len(tracker.metrics_history["append_test"]) == 2

    def test_track_multiple_operations_separate_lists(self):
        """Test that different operations have separate histories."""
        tracker = PerformanceTracker()

        with tracker.track("operation_a"):
            pass

        with tracker.track("operation_b"):
            pass

        assert len(tracker.metrics_history) == 2
        assert "operation_a" in tracker.metrics_history
        assert "operation_b" in tracker.metrics_history
        assert len(tracker.metrics_history["operation_a"]) == 1
        assert len(tracker.metrics_history["operation_b"]) == 1

    def test_get_metrics_by_operation_name(self):
        """Test retrieving metrics by operation name."""
        tracker = PerformanceTracker()

        with tracker.track("get_test"):
            pass

        metrics = tracker.get_metrics("get_test")
        assert isinstance(metrics, list)
        assert len(metrics) == 1
        assert metrics[0].operation_name == "get_test"

    def test_get_metrics_unknown_operation_returns_empty(self):
        """Test that unknown operation returns empty list."""
        tracker = PerformanceTracker()

        metrics = tracker.get_metrics("nonexistent")
        assert metrics == []

    def test_get_metrics_returns_list(self):
        """Test that get_metrics returns a list."""
        tracker = PerformanceTracker()

        with tracker.track("list_test"):
            pass

        metrics = tracker.get_metrics("list_test")
        assert isinstance(metrics, list)


# ============================================================================
# Latest Metrics Tests
# ============================================================================

class TestLatestMetrics:
    """Test get_latest functionality."""

    def test_get_latest_returns_most_recent(self):
        """Test that get_latest returns most recent metrics."""
        tracker = PerformanceTracker()

        with tracker.track("latest_test"):
            time.sleep(0.01)

        first_time = tracker.get_latest("latest_test").execution_time

        with tracker.track("latest_test"):
            time.sleep(0.02)

        second_time = tracker.get_latest("latest_test").execution_time

        # Latest should be the second one with longer execution time
        assert second_time > first_time

    def test_get_latest_returns_none_for_unknown_operation(self):
        """Test that unknown operation returns None."""
        tracker = PerformanceTracker()

        latest = tracker.get_latest("unknown_operation")
        assert latest is None

    def test_get_latest_with_single_metric(self):
        """Test get_latest with single recorded metric."""
        tracker = PerformanceTracker()

        with tracker.track("single_test"):
            pass

        latest = tracker.get_latest("single_test")
        assert latest is not None
        assert latest.operation_name == "single_test"

    def test_get_latest_order_of_operations(self):
        """Test that get_latest returns last operation chronologically."""
        tracker = PerformanceTracker()

        # Track multiple times
        with tracker.track("order_test"):
            pass
        with tracker.track("order_test"):
            pass
        with tracker.track("order_test"):
            pass

        # Should have 3 entries
        assert len(tracker.get_metrics("order_test")) == 3

        # Latest should be the last one
        latest = tracker.get_latest("order_test")
        all_metrics = tracker.get_metrics("order_test")
        assert latest == all_metrics[-1]


# ============================================================================
# Average Time Tests
# ============================================================================

class TestAverageTime:
    """Test get_average_time calculation."""

    def test_get_average_time_single_operation(self):
        """Test average time with single operation."""
        tracker = PerformanceTracker()

        with tracker.track("avg_single"):
            time.sleep(0.01)

        avg_time = tracker.get_average_time("avg_single")
        assert avg_time >= 0.009  # Should be around 10ms

    def test_get_average_time_multiple_operations(self):
        """Test average time with multiple operations."""
        tracker = PerformanceTracker()

        # Track operations with different times
        with tracker.track("avg_multi"):
            time.sleep(0.01)  # ~10ms

        with tracker.track("avg_multi"):
            time.sleep(0.02)  # ~20ms

        with tracker.track("avg_multi"):
            time.sleep(0.03)  # ~30ms

        avg_time = tracker.get_average_time("avg_multi")
        # Average should be around 20ms
        assert 0.015 <= avg_time <= 0.025

    def test_get_average_time_empty_returns_zero(self):
        """Test that empty metrics returns 0.0."""
        tracker = PerformanceTracker()

        avg_time = tracker.get_average_time("nonexistent")
        assert avg_time == 0.0

    def test_get_average_time_correct_calculation(self):
        """Test that average is calculated correctly."""
        tracker = PerformanceTracker()

        # Manually set execution times for testing
        tracker.metrics_history["calc_test"] = [
            PerformanceMetrics(
                operation_name="calc_test",
                timestamp=datetime.now(),
                execution_time=1.0,
                memory_usage_mb=10.0,
                cpu_percent=50.0,
                success=True
            ),
            PerformanceMetrics(
                operation_name="calc_test",
                timestamp=datetime.now(),
                execution_time=2.0,
                memory_usage_mb=10.0,
                cpu_percent=50.0,
                success=True
            ),
            PerformanceMetrics(
                operation_name="calc_test",
                timestamp=datetime.now(),
                execution_time=3.0,
                memory_usage_mb=10.0,
                cpu_percent=50.0,
                success=True
            )
        ]

        avg_time = tracker.get_average_time("calc_test")
        assert avg_time == 2.0  # (1.0 + 2.0 + 3.0) / 3 = 2.0

    def test_get_average_time_unknown_operation_returns_zero(self):
        """Test that unknown operation returns 0.0."""
        tracker = PerformanceTracker()

        avg_time = tracker.get_average_time("unknown")
        assert avg_time == 0.0


# ============================================================================
# Memory Calculation Tests
# ============================================================================

class TestMemoryCalculation:
    """Test memory usage delta calculation."""

    def test_memory_usage_calculated_as_delta(self):
        """Test memory usage is calculated as end - start."""
        tracker = PerformanceTracker()

        with tracker.track("memory_delta"):
            # Allocate some memory
            _ = [0] * 10000  # Small allocation

        metrics = tracker.get_latest("memory_delta")
        # Memory usage should be a delta (can be positive or negative)
        assert isinstance(metrics.memory_usage_mb, float)

    def test_memory_usage_can_be_negative(self):
        """Test memory usage delta can be negative (memory freed)."""
        tracker = PerformanceTracker()

        # This test acknowledges that memory_usage_mb is a delta
        # and can be negative if memory is freed during the operation
        with tracker.track("memory_test"):
            pass

        metrics = tracker.get_latest("memory_test")
        # Just verify it's a valid float (positive or negative)
        assert isinstance(metrics.memory_usage_mb, float)

    def test_memory_usage_in_megabytes(self):
        """Test memory usage is in megabytes."""
        tracker = PerformanceTracker()

        with tracker.track("memory_mb"):
            pass

        metrics = tracker.get_latest("memory_mb")
        # Memory should be in MB (reasonable range)
        # Even a small operation should have < 1000 MB delta
        assert abs(metrics.memory_usage_mb) < 1000


# ============================================================================
# Multiple Operations Tests
# ============================================================================

class TestMultipleOperations:
    """Test tracking multiple named operations."""

    def test_track_different_operations_separate_histories(self):
        """Test different operations maintain separate histories."""
        tracker = PerformanceTracker()

        with tracker.track("op1"):
            pass

        with tracker.track("op2"):
            pass

        assert "op1" in tracker.metrics_history
        assert "op2" in tracker.metrics_history
        assert tracker.metrics_history["op1"] != tracker.metrics_history["op2"]

    def test_track_same_operation_multiple_times(self):
        """Test same operation can be tracked multiple times."""
        tracker = PerformanceTracker()

        for i in range(5):
            with tracker.track("repeated_op"):
                time.sleep(0.001)

        metrics = tracker.get_metrics("repeated_op")
        assert len(metrics) == 5

    def test_get_metrics_returns_all_instances(self):
        """Test get_metrics returns all tracked instances."""
        tracker = PerformanceTracker()

        # Track 3 times
        with tracker.track("multi_instance"):
            pass
        with tracker.track("multi_instance"):
            pass
        with tracker.track("multi_instance"):
            pass

        metrics = tracker.get_metrics("multi_instance")
        assert len(metrics) == 3

        # All should be PerformanceMetrics instances
        for m in metrics:
            assert isinstance(m, PerformanceMetrics)
            assert m.operation_name == "multi_instance"


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_track_with_empty_operation_name(self):
        """Test tracking with empty operation name."""
        tracker = PerformanceTracker()

        with tracker.track(""):
            pass

        # Should still work, just with empty key
        assert "" in tracker.metrics_history

    def test_track_with_very_short_operation(self):
        """Test tracking very short operation (< 1ms)."""
        tracker = PerformanceTracker()

        with tracker.track("instant_op"):
            pass  # Instant operation

        metrics = tracker.get_latest("instant_op")
        assert metrics.execution_time >= 0.0
        # Execution time should be very small
        assert metrics.execution_time < 0.1

    def test_multiple_trackers_independent(self):
        """Test that multiple tracker instances are independent."""
        tracker1 = PerformanceTracker()
        tracker2 = PerformanceTracker()

        with tracker1.track("tracker1_op"):
            pass

        with tracker2.track("tracker2_op"):
            pass

        # Each tracker should have only its own operations
        assert "tracker1_op" in tracker1.metrics_history
        assert "tracker1_op" not in tracker2.metrics_history
        assert "tracker2_op" in tracker2.metrics_history
        assert "tracker2_op" not in tracker1.metrics_history
