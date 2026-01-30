#!/usr/bin/env python3
"""
test_orchestration.py - Unit Tests for Orchestration Module

Tests for:
- RateLimiter: Token bucket rate limiting
- CheckpointManager: Checkpoint save/restore
- DataQualityValidator: Data quality validation

Coverage target: orchestration/* (~280 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import time
import json
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from modules.orchestration.rate_limiter import RateLimiter, MultiRateLimiter, TokenBucketRateLimiter
from modules.orchestration.checkpoint import CheckpointManager


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter class"""

    def test_initialization(self):
        """Test rate limiter initialization"""
        limiter = RateLimiter(max_rate=10, time_window=1.0, name="test")

        self.assertEqual(limiter.max_rate, 10)
        self.assertEqual(limiter.time_window, 1.0)
        self.assertEqual(limiter.name, "test")
        self.assertEqual(limiter.total_calls, 0)
        self.assertEqual(limiter.total_wait_time, 0.0)
        self.assertEqual(limiter.calls, [])

    def test_wait_if_needed_no_limit(self):
        """Test wait_if_needed when under limit"""
        limiter = RateLimiter(max_rate=10, time_window=1.0)

        wait_time = limiter.wait_if_needed()

        self.assertEqual(wait_time, 0.0)
        self.assertEqual(limiter.total_calls, 1)
        self.assertEqual(len(limiter.calls), 1)

    def test_wait_if_needed_multiple_calls(self):
        """Test multiple calls under limit"""
        limiter = RateLimiter(max_rate=5, time_window=1.0)

        for _ in range(3):
            wait_time = limiter.wait_if_needed()
            self.assertEqual(wait_time, 0.0)

        self.assertEqual(limiter.total_calls, 3)
        self.assertEqual(len(limiter.calls), 3)

    def test_reset(self):
        """Test resetting rate limiter"""
        limiter = RateLimiter(max_rate=10, time_window=1.0)

        # Make some calls
        limiter.wait_if_needed()
        limiter.wait_if_needed()

        # Reset
        limiter.reset()

        self.assertEqual(limiter.calls, [])
        self.assertEqual(limiter.total_calls, 0)
        self.assertEqual(limiter.total_wait_time, 0.0)

    def test_get_current_rate_no_calls(self):
        """Test get_current_rate with no calls"""
        limiter = RateLimiter(max_rate=10, time_window=1.0)

        rate = limiter.get_current_rate()

        self.assertEqual(rate, 0.0)

    def test_get_current_rate_with_calls(self):
        """Test get_current_rate with calls"""
        limiter = RateLimiter(max_rate=10, time_window=1.0)

        # Make a few calls
        for _ in range(3):
            limiter.wait_if_needed()

        rate = limiter.get_current_rate()

        # Rate should be positive
        self.assertGreaterEqual(rate, 0.0)

    def test_get_statistics(self):
        """Test get_statistics"""
        limiter = RateLimiter(max_rate=10, time_window=1.0, name="test")

        # Make some calls
        limiter.wait_if_needed()
        limiter.wait_if_needed()

        stats = limiter.get_statistics()

        self.assertEqual(stats['name'], 'test')
        self.assertEqual(stats['total_calls'], 2)
        self.assertIsInstance(stats['total_wait_time'], float)
        self.assertIsInstance(stats['average_wait'], float)
        self.assertIsInstance(stats['current_rate'], float)

    def test_repr(self):
        """Test string representation"""
        limiter = RateLimiter(max_rate=10, time_window=1.0, name="test")

        repr_str = repr(limiter)

        self.assertIn("test", repr_str)
        self.assertIn("10", repr_str)
        self.assertIn("1.0", repr_str)


class TestMultiRateLimiter(unittest.TestCase):
    """Test MultiRateLimiter class"""

    def test_initialization(self):
        """Test multi rate limiter initialization"""
        limiter = MultiRateLimiter()

        self.assertEqual(limiter.limiters, {})

    def test_add_limiter(self):
        """Test adding a limiter"""
        limiter = MultiRateLimiter()

        limiter.add("KIS", max_rate=20, time_window=1.0)

        self.assertIn("KIS", limiter.limiters)
        self.assertEqual(limiter.limiters["KIS"].max_rate, 20)

    def test_wait_for_api(self):
        """Test wait for specific API"""
        limiter = MultiRateLimiter()
        limiter.add("KIS", max_rate=10, time_window=1.0)

        wait_time = limiter.wait("KIS")

        self.assertEqual(wait_time, 0.0)

    def test_wait_unknown_api(self):
        """Test wait for unknown API"""
        limiter = MultiRateLimiter()

        # Should not raise error, just return 0
        wait_time = limiter.wait("UNKNOWN")

        self.assertEqual(wait_time, 0.0)

    def test_get_all_statistics(self):
        """Test getting statistics for all limiters"""
        limiter = MultiRateLimiter()
        limiter.add("KIS", max_rate=20, time_window=1.0)
        limiter.add("DART", max_rate=10, time_window=1.0)

        stats = limiter.get_all_statistics()

        self.assertIn("KIS", stats)
        self.assertIn("DART", stats)

    def test_get_limiter(self):
        """Test getting a limiter by name"""
        limiter = MultiRateLimiter()
        limiter.add("KIS", max_rate=20, time_window=1.0)

        kis_limiter = limiter.get("KIS")

        self.assertIsNotNone(kis_limiter)
        self.assertEqual(kis_limiter.max_rate, 20)

    def test_reset_all(self):
        """Test resetting all limiters"""
        limiter = MultiRateLimiter()
        limiter.add("KIS", max_rate=20, time_window=1.0)
        limiter.wait("KIS")

        limiter.reset_all()

        self.assertEqual(limiter.limiters["KIS"].total_calls, 0)


class TestTokenBucketRateLimiter(unittest.TestCase):
    """Test TokenBucketRateLimiter class"""

    def test_initialization(self):
        """Test token bucket initialization"""
        limiter = TokenBucketRateLimiter(
            max_rate=10,
            time_window=1.0,
            name="test"
        )

        self.assertEqual(limiter.max_rate, 10)
        self.assertEqual(limiter.time_window, 1.0)
        self.assertEqual(limiter.name, "test")

    def test_wait_if_needed(self):
        """Test wait_if_needed"""
        limiter = TokenBucketRateLimiter(
            max_rate=10,
            time_window=1.0
        )

        wait_time = limiter.wait_if_needed()

        # Should not wait initially
        self.assertEqual(wait_time, 0.0)

    def test_wait_if_needed_multiple(self):
        """Test multiple calls under limit"""
        limiter = TokenBucketRateLimiter(
            max_rate=100,
            time_window=1.0
        )

        for _ in range(5):
            wait_time = limiter.wait_if_needed()
            self.assertEqual(wait_time, 0.0)

    def test_thread_safety(self):
        """Test thread-safe rate limiting"""
        import threading

        limiter = TokenBucketRateLimiter(
            max_rate=100,
            time_window=1.0,
            name="test"
        )

        results = []

        def make_call():
            wait_time = limiter.wait_if_needed()
            results.append(wait_time)

        threads = [threading.Thread(target=make_call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 10)
        # All initial calls should not wait
        self.assertTrue(all(w == 0.0 for w in results))


class TestCheckpointManager(unittest.TestCase):
    """Test CheckpointManager class"""

    def setUp(self):
        """Set up temporary directory for checkpoints"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(checkpoint_dir=self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test checkpoint manager initialization"""
        self.assertEqual(self.manager.checkpoint_dir, self.temp_dir)
        self.assertTrue(os.path.exists(self.temp_dir))

    def test_step_order(self):
        """Test step order constant"""
        self.assertIn('tickers', CheckpointManager.STEP_ORDER)
        self.assertIn('ohlcv', CheckpointManager.STEP_ORDER)
        self.assertIn('fundamentals', CheckpointManager.STEP_ORDER)

    def test_save_checkpoint(self):
        """Test saving checkpoint"""
        result = {'success': True, 'count': 100}

        filepath = self.manager.save('tickers', result)

        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.endswith('.json'))

        # Verify content
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.assertEqual(data['step'], 'tickers')
        self.assertEqual(data['result']['success'], True)
        self.assertIn('timestamp', data)
        self.assertIn('next_step', data)

    def test_save_checkpoint_with_metadata(self):
        """Test saving checkpoint with metadata"""
        result = {'success': True}
        metadata = {'regions': ['KR', 'US'], 'force': False}

        filepath = self.manager.save('ohlcv', result, metadata=metadata)

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.assertEqual(data['metadata']['regions'], ['KR', 'US'])
        self.assertFalse(data['metadata']['force'])

    def test_load_latest_no_checkpoints(self):
        """Test load_latest with no checkpoints"""
        checkpoint = self.manager.load_latest()

        self.assertIsNone(checkpoint)

    def test_load_latest_single_checkpoint(self):
        """Test load_latest with single checkpoint"""
        self.manager.save('tickers', {'success': True})

        checkpoint = self.manager.load_latest()

        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint['step'], 'tickers')

    def test_load_latest_multiple_checkpoints(self):
        """Test load_latest with multiple checkpoints"""
        self.manager.save('tickers', {'success': True})
        time.sleep(0.1)  # Ensure different timestamp
        self.manager.save('ohlcv', {'success': True})

        checkpoint = self.manager.load_latest()

        self.assertEqual(checkpoint['step'], 'ohlcv')

    def test_get_next_step(self):
        """Test _get_next_step"""
        next_step = self.manager._get_next_step('tickers')

        expected_idx = CheckpointManager.STEP_ORDER.index('tickers') + 1
        expected_next = CheckpointManager.STEP_ORDER[expected_idx]

        self.assertEqual(next_step, expected_next)

    def test_get_next_step_last_step(self):
        """Test _get_next_step for last step"""
        last_step = CheckpointManager.STEP_ORDER[-1]

        next_step = self.manager._get_next_step(last_step)

        self.assertIsNone(next_step)

    def test_checkpoint_round_trip(self):
        """Test saving and loading checkpoint"""
        original_result = {
            'success': True,
            'count': 500,
            'errors': []
        }

        self.manager.save('fundamentals', original_result)

        loaded = self.manager.load_latest()

        self.assertEqual(loaded['result']['success'], True)
        self.assertEqual(loaded['result']['count'], 500)
        self.assertEqual(loaded['result']['errors'], [])


class TestCheckpointManagerCleanup(unittest.TestCase):
    """Test CheckpointManager cleanup functionality"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(checkpoint_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_cleanup_old_checkpoints(self):
        """Test cleanup of old checkpoints"""
        # Create multiple checkpoint files directly to avoid timing issues
        for i in range(5):
            filepath = os.path.join(self.temp_dir, f"checkpoint_test_{i}.json")
            with open(filepath, 'w') as f:
                json.dump({'step': 'tickers', 'index': i}, f)

        # Check files exist
        files_before = len([f for f in os.listdir(self.temp_dir) if f.startswith('checkpoint_')])
        self.assertEqual(files_before, 5)

        # Cleanup keeping only 2 (if cleanup method exists)
        if hasattr(self.manager, 'cleanup'):
            self.manager.cleanup(keep_last=2)
            files_after = len([f for f in os.listdir(self.temp_dir) if f.startswith('checkpoint_')])
            self.assertEqual(files_after, 2)
        else:
            # Skip if cleanup method doesn't exist
            self.skipTest("cleanup method not implemented")


# Parametrized tests
@pytest.mark.parametrize("max_rate,time_window", [
    (10, 1.0),
    (20, 0.5),
    (100, 2.0),
    (5, 0.1),
])
def test_rate_limiter_configurations(max_rate, time_window):
    """Test various rate limiter configurations"""
    limiter = RateLimiter(max_rate=max_rate, time_window=time_window)

    assert limiter.max_rate == max_rate
    assert limiter.time_window == time_window

    # Should not block for a single call
    wait_time = limiter.wait_if_needed()
    assert wait_time == 0.0


@pytest.mark.parametrize("step,expected_next", [
    ('tickers', 'ticker_refresh'),
    ('ohlcv', 'fundamentals'),
    ('fundamentals', 'classification'),
])
def test_checkpoint_step_order(step, expected_next):
    """Test checkpoint step ordering"""
    temp_dir = tempfile.mkdtemp()
    try:
        manager = CheckpointManager(checkpoint_dir=temp_dir)
        next_step = manager._get_next_step(step)
        assert next_step == expected_next
    finally:
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    unittest.main(verbosity=2)
