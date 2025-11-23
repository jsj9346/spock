"""
Rate Limiter for API Call Management

Provides intelligent rate limiting for external API calls (KIS, DART, pykrx).
Prevents exceeding API rate limits and ensures smooth operation.

Author: Quant Investment Platform
Date: 2025-11-01
Updated: 2025-11-23 (Week 4 Optimization - TokenBucketRateLimiter)
"""

import time
from typing import List, Optional
from collections import deque
import threading
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket-based rate limiter for API calls

    Features:
    - Configurable rate limits (max_rate calls per time_window)
    - Automatic wait when limit reached
    - Call history tracking
    - Statistics reporting

    Usage:
        limiter = RateLimiter(max_rate=20, time_window=1.0)  # 20 calls/sec
        limiter.wait_if_needed()  # Blocks if rate limit reached
        # Make API call...
    """

    def __init__(self, max_rate: int, time_window: float = 1.0, name: str = "default"):
        """
        Initialize rate limiter

        Args:
            max_rate: Maximum number of calls allowed in time_window
            time_window: Time window in seconds (default: 1.0)
            name: Limiter name for logging (e.g., 'KIS', 'DART')
        """
        self.max_rate = max_rate
        self.time_window = time_window
        self.name = name
        self.calls: List[float] = []  # Timestamp list of recent calls

        # Statistics
        self.total_calls = 0
        self.total_wait_time = 0.0

        logger.info(
            f"RateLimiter '{name}' initialized "
            f"(max_rate={max_rate}, time_window={time_window}s)"
        )

    def wait_if_needed(self) -> float:
        """
        Wait if rate limit would be exceeded

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        now = time.time()

        # Remove calls outside time window
        self.calls = [t for t in self.calls if now - t < self.time_window]

        # Check if rate limit reached
        if len(self.calls) >= self.max_rate:
            # Calculate wait time
            oldest_call = self.calls[0]
            wait_time = self.time_window - (now - oldest_call)

            if wait_time > 0:
                logger.debug(
                    f"[{self.name}] Rate limit reached ({len(self.calls)}/{self.max_rate}), "
                    f"waiting {wait_time:.2f}s"
                )

                time.sleep(wait_time)

                # Update statistics
                self.total_wait_time += wait_time

                # Remove oldest call
                self.calls.pop(0)

                return wait_time

        # Record this call
        self.calls.append(time.time())
        self.total_calls += 1

        return 0.0

    def reset(self) -> None:
        """Reset call history and statistics"""
        self.calls = []
        self.total_calls = 0
        self.total_wait_time = 0.0

        logger.info(f"[{self.name}] Rate limiter reset")

    def get_current_rate(self) -> float:
        """
        Get current call rate (calls per second)

        Returns:
            Current rate (calls/sec)
        """
        now = time.time()
        recent_calls = [t for t in self.calls if now - t < self.time_window]

        if not recent_calls:
            return 0.0

        time_span = now - min(recent_calls)
        if time_span == 0:
            return 0.0

        return len(recent_calls) / time_span

    def get_statistics(self) -> dict:
        """
        Get rate limiter statistics

        Returns:
            Dictionary with statistics:
            {
                'total_calls': int,
                'total_wait_time': float,
                'average_wait': float,
                'current_rate': float
            }
        """
        avg_wait = (
            self.total_wait_time / self.total_calls
            if self.total_calls > 0
            else 0.0
        )

        return {
            'name': self.name,
            'total_calls': self.total_calls,
            'total_wait_time': self.total_wait_time,
            'average_wait': avg_wait,
            'current_rate': self.get_current_rate()
        }

    def __repr__(self) -> str:
        return (
            f"RateLimiter(name='{self.name}', max_rate={self.max_rate}, "
            f"time_window={self.time_window}, calls={len(self.calls)})"
        )


class MultiRateLimiter:
    """
    Manages multiple rate limiters for different APIs

    Usage:
        limiters = MultiRateLimiter()
        limiters.add('KIS', max_rate=20, time_window=1.0)
        limiters.add('DART', max_rate=1, time_window=1.0)

        limiters.wait('KIS')  # Wait if needed for KIS API
    """

    def __init__(self):
        """Initialize multi-rate limiter"""
        self.limiters: dict[str, RateLimiter] = {}

    def add(self, name: str, max_rate: int, time_window: float = 1.0) -> RateLimiter:
        """
        Add a rate limiter

        Args:
            name: Limiter name (e.g., 'KIS', 'DART')
            max_rate: Maximum calls per time window
            time_window: Time window in seconds

        Returns:
            Created RateLimiter instance
        """
        limiter = RateLimiter(max_rate, time_window, name)
        self.limiters[name] = limiter
        return limiter

    def get(self, name: str) -> Optional[RateLimiter]:
        """Get rate limiter by name"""
        return self.limiters.get(name)

    def wait(self, name: str) -> float:
        """
        Wait if needed for specific rate limiter

        Args:
            name: Limiter name

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        limiter = self.limiters.get(name)

        if not limiter:
            logger.warning(f"Rate limiter '{name}' not found")
            return 0.0

        return limiter.wait_if_needed()

    def get_all_statistics(self) -> dict:
        """
        Get statistics for all rate limiters

        Returns:
            Dictionary mapping limiter name to statistics
        """
        return {
            name: limiter.get_statistics()
            for name, limiter in self.limiters.items()
        }

    def reset_all(self) -> None:
        """Reset all rate limiters"""
        for limiter in self.limiters.values():
            limiter.reset()

    def __repr__(self) -> str:
        return f"MultiRateLimiter(limiters={list(self.limiters.keys())})"


# ==============================================================================
# Week 4 Optimization: TokenBucketRateLimiter
# ==============================================================================

class TokenBucketRateLimiter:
    """
    Thread-safe token bucket rate limiter (Week 4 Optimization).

    Allows bursts up to max_rate within time_window, then enforces rate limit.
    More efficient than fixed-delay limiter as it only sleeps when necessary.

    Performance improvement over basic RateLimiter:
    - Thread-safe (can be used with ThreadPoolExecutor)
    - Efficient deque for call history (vs list)
    - Only sleeps when needed (not on every call)
    - Better statistics tracking

    Example:
        # Allow 20 requests per second
        limiter = TokenBucketRateLimiter(max_rate=20, time_window=1.0)

        # In parallel threads
        def worker(item):
            limiter.wait_if_needed()  # Thread-safe
            api_call(item)
    """

    def __init__(
        self,
        max_rate: int,
        time_window: float = 1.0,
        name: str = "RateLimiter"
    ):
        """
        Initialize rate limiter.

        Args:
            max_rate: Maximum requests allowed in time_window
            time_window: Time window in seconds (default: 1.0)
            name: Identifier for logging (default: "RateLimiter")
        """
        self.max_rate = max_rate
        self.time_window = time_window
        self.name = name

        # Thread-safe call history
        self.calls = deque()  # Stores timestamps of recent calls
        self.lock = threading.Lock()

        # Statistics
        self.total_calls = 0
        self.total_wait_time = 0.0

    def wait_if_needed(self) -> float:
        """
        Wait if rate limit would be exceeded, otherwise return immediately.

        Returns:
            float: Time waited in seconds (0.0 if no wait needed)

        Thread-safe: Can be called from multiple threads simultaneously.
        """
        with self.lock:
            now = time.time()

            # Remove calls outside time window
            while self.calls and self.calls[0] < now - self.time_window:
                self.calls.popleft()

            # Check if rate limit exceeded
            wait_time = 0.0
            if len(self.calls) >= self.max_rate:
                # Calculate sleep time
                oldest_call = self.calls[0]
                sleep_until = oldest_call + self.time_window
                sleep_time = sleep_until - now

                if sleep_time > 0:
                    # Rate limit exceeded - must wait
                    time.sleep(sleep_time)
                    self.total_wait_time += sleep_time
                    now = time.time()  # Update time after sleep

                    # Clean up again after sleep
                    while self.calls and self.calls[0] < now - self.time_window:
                        self.calls.popleft()

                    wait_time = sleep_time

            # Record this call
            self.calls.append(now)
            self.total_calls += 1

            return wait_time

    def get_stats(self) -> dict:
        """
        Get rate limiter statistics.

        Returns:
            dict: Statistics including total calls, wait time, efficiency
        """
        with self.lock:
            if self.total_calls == 0:
                efficiency = 100.0
            else:
                # Efficiency = % of time NOT waiting
                total_time = self.total_calls / self.max_rate  # Theoretical minimum time
                efficiency = (1 - self.total_wait_time / max(total_time, 0.001)) * 100

            return {
                'total_calls': self.total_calls,
                'total_wait_time': round(self.total_wait_time, 2),
                'current_queue_size': len(self.calls),
                'efficiency_percent': round(efficiency, 2),
                'avg_wait_per_call': round(
                    self.total_wait_time / self.total_calls
                    if self.total_calls > 0 else 0.0,
                    3
                )
            }

    def reset(self):
        """Reset statistics and call history."""
        with self.lock:
            self.calls.clear()
            self.total_calls = 0
            self.total_wait_time = 0.0
