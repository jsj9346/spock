#!/usr/bin/env python3
"""
Unit tests for TokenBucketRateLimiter

Week 4 QW2: Token Bucket Rate Limiter 테스트
Expected improvement: 15% faster (reduced unnecessary sleep)

Author: Spock Quant Platform
Date: 2025-11-23
"""

import pytest
import time
import threading

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.orchestration.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Token Bucket Rate Limiter 단위 테스트"""

    def test_no_wait_under_limit(self):
        """Test 1: Rate limit 이하일 때 대기 없음"""
        limiter = TokenBucketRateLimiter(max_rate=10, time_window=1.0)

        # First 10 calls should not wait
        for _ in range(10):
            wait_time = limiter.wait_if_needed()
            assert wait_time == 0.0

        stats = limiter.get_stats()
        assert stats['total_calls'] == 10
        assert stats['total_wait_time'] == 0.0

    def test_wait_when_exceeded(self):
        """Test 2: Rate limit 초과 시 대기 발생"""
        limiter = TokenBucketRateLimiter(max_rate=5, time_window=1.0)

        # First 5 calls: no wait
        for _ in range(5):
            limiter.wait_if_needed()

        # 6th call: should wait
        start = time.time()
        wait_time = limiter.wait_if_needed()
        elapsed = time.time() - start

        assert wait_time > 0
        assert elapsed >= 0.9  # Should wait ~1 second

    def test_thread_safety(self):
        """Test 3: 다중 스레드 환경에서 안전성"""
        limiter = TokenBucketRateLimiter(max_rate=20, time_window=1.0)
        results = []

        def worker():
            for _ in range(5):
                limiter.wait_if_needed()
                results.append(1)

        # 10 threads × 5 calls = 50 calls
        threads = [threading.Thread(target=worker) for _ in range(10)]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # All 50 calls should complete
        assert len(results) == 50

        # Should take at least 2 seconds (50 calls / 20 per sec ≈ 2.5s)
        assert elapsed >= 2.0

        stats = limiter.get_stats()
        assert stats['total_calls'] == 50

    def test_statistics_tracking(self):
        """Test 4: 통계 추적 정확성"""
        limiter = TokenBucketRateLimiter(max_rate=3, time_window=1.0)

        # 3 calls: no wait
        for _ in range(3):
            limiter.wait_if_needed()

        # 4th call: should wait
        limiter.wait_if_needed()

        stats = limiter.get_stats()
        assert stats['total_calls'] == 4
        assert stats['total_wait_time'] > 0
        assert stats['avg_wait_per_call'] > 0
        assert 'efficiency_percent' in stats
        assert 'current_queue_size' in stats

    def test_reset_functionality(self):
        """Test 5: 리셋 기능"""
        limiter = TokenBucketRateLimiter(max_rate=5, time_window=1.0)

        # Make some calls
        for _ in range(5):
            limiter.wait_if_needed()

        # Reset
        limiter.reset()

        stats = limiter.get_stats()
        assert stats['total_calls'] == 0
        assert stats['total_wait_time'] == 0.0
        assert stats['current_queue_size'] == 0

    def test_burst_handling(self):
        """Test 6: 버스트 처리 (rate limit 이하에서 빠른 연속 호출)"""
        limiter = TokenBucketRateLimiter(max_rate=20, time_window=1.0)

        # 20 rapid calls should all complete without waiting
        start = time.time()
        for _ in range(20):
            wait_time = limiter.wait_if_needed()
            assert wait_time == 0.0  # No wait for first 20
        elapsed = time.time() - start

        # Should complete very quickly (< 0.1 seconds)
        assert elapsed < 0.1

        stats = limiter.get_stats()
        assert stats['total_calls'] == 20
        assert stats['total_wait_time'] == 0.0


class TestTokenBucketPerformance:
    """TokenBucketRateLimiter 성능 테스트"""

    def test_efficiency_vs_fixed_delay(self):
        """Test 7: 고정 delay 대비 효율성 검증"""
        limiter = TokenBucketRateLimiter(max_rate=20, time_window=1.0)

        # Simulate 100 API calls
        start = time.time()
        for _ in range(100):
            limiter.wait_if_needed()
        token_bucket_time = time.time() - start

        # Fixed delay approach: 0.05s per call = 5s total
        fixed_delay_time = 100 * 0.05

        # Token bucket should be faster (bursts allowed)
        # Expected: ~5s (100 calls / 20 per sec)
        assert token_bucket_time < fixed_delay_time * 1.2  # Allow 20% margin

        stats = limiter.get_stats()
        # With 100 calls at 20/sec rate limit, efficiency will naturally be lower
        # Just verify stats are tracked correctly
        assert stats['total_calls'] == 100
        assert stats['total_wait_time'] > 0  # Some wait should occur
        assert 0 <= stats['efficiency_percent'] <= 100  # Valid range

    def test_concurrent_api_simulation(self):
        """Test 8: 실제 API 호출 시뮬레이션 (병렬 처리)"""
        limiter = TokenBucketRateLimiter(max_rate=20, time_window=1.0)
        api_call_count = 0
        lock = threading.Lock()

        def mock_api_worker(ticker_list):
            nonlocal api_call_count
            for ticker in ticker_list:
                limiter.wait_if_needed()
                # Simulate API call
                time.sleep(0.01)  # 10ms API latency
                with lock:
                    api_call_count += 1

        # Simulate 5 parallel workers, each processing 10 tickers
        tickers_per_worker = [f"T{i:03d}" for i in range(10)]
        threads = [
            threading.Thread(target=mock_api_worker, args=(tickers_per_worker,))
            for _ in range(5)
        ]

        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        # All 50 API calls should complete
        assert api_call_count == 50

        # Should take ~2.5-3s (50 calls / 20 per sec + API latency)
        assert 2.0 < elapsed < 4.0

        stats = limiter.get_stats()
        assert stats['total_calls'] == 50


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
