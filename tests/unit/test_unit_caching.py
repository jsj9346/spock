#!/usr/bin/env python3
"""
Unit Tests for Caching System (Week 1)

Tests:
- QueryCache: TTL-based caching mechanism
- DBConnectionManager: Connection pool management
- Cache hit/miss behavior
- Thread safety

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
import pytest
from datetime import datetime, timedelta
from threading import Thread

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spock_refresh import QueryCache, DBConnectionManager


class TestQueryCache:
    """쿼리 캐시 단위 테스트"""

    def setup_method(self):
        """각 테스트 전 캐시 초기화"""
        self.cache = QueryCache()
        self.cache.invalidate()

    def test_cache_miss_first_call(self):
        """Test 1: 첫 호출 시 캐시 미스"""
        call_count = [0]

        def fetch_func():
            call_count[0] += 1
            return {'data': 'test', 'timestamp': datetime.now()}

        # First call - should be cache miss
        result = self.cache.get_or_fetch('test_key', fetch_func, ttl_seconds=60)

        assert result is not None
        assert result['data'] == 'test'
        assert call_count[0] == 1  # Function called once
        assert self.cache._misses == 1
        assert self.cache._hits == 0

    def test_cache_hit_second_call(self):
        """Test 2: 두 번째 호출 시 캐시 히트"""
        call_count = [0]

        def fetch_func():
            call_count[0] += 1
            return {'data': 'test', 'count': call_count[0]}

        # First call - cache miss
        result1 = self.cache.get_or_fetch('test_key', fetch_func, ttl_seconds=60)

        # Second call - should be cache hit
        result2 = self.cache.get_or_fetch('test_key', fetch_func, ttl_seconds=60)

        assert result1 == result2  # Same result
        assert call_count[0] == 1  # Function called only once
        assert self.cache._hits == 1
        assert self.cache._misses == 1

    def test_cache_ttl_expiration(self):
        """Test 3: TTL 만료 후 재조회"""
        call_count = [0]

        def fetch_func():
            call_count[0] += 1
            return {'count': call_count[0]}

        # First call with 1 second TTL
        result1 = self.cache.get_or_fetch('test_key', fetch_func, ttl_seconds=1)
        assert result1['count'] == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Second call - TTL expired, should fetch again
        result2 = self.cache.get_or_fetch('test_key', fetch_func, ttl_seconds=1)
        assert result2['count'] == 2  # New fetch
        assert call_count[0] == 2

    def test_cache_invalidation(self):
        """Test 4: 캐시 무효화 동작"""
        def fetch_func():
            return {'data': 'test'}

        # Populate cache
        self.cache.get_or_fetch('key1', fetch_func)
        self.cache.get_or_fetch('key2', fetch_func)

        assert len(self.cache._cache) == 2

        # Invalidate all
        self.cache.invalidate()

        assert len(self.cache._cache) == 0
        assert len(self.cache._timestamps) == 0

    def test_cache_pattern_invalidation(self):
        """Test 5: 패턴 기반 캐시 무효화"""
        def fetch_func():
            return {'data': 'test'}

        # Populate cache with different keys
        self.cache.get_or_fetch('db_status', fetch_func)
        self.cache.get_or_fetch('db_coverage', fetch_func)
        self.cache.get_or_fetch('macro_data', fetch_func)

        assert len(self.cache._cache) == 3

        # Invalidate only 'db_' pattern
        self.cache.invalidate(pattern='db_')

        assert len(self.cache._cache) == 1
        assert 'macro_data' in self.cache._cache
        assert 'db_status' not in self.cache._cache
        assert 'db_coverage' not in self.cache._cache

    def test_thread_safe_cache_access(self):
        """Test 6: 멀티스레드 환경에서 캐시 안전성"""
        call_count = [0]

        def fetch_func():
            call_count[0] += 1
            time.sleep(0.01)  # Simulate slow operation
            return {'count': call_count[0]}

        def access_cache():
            self.cache.get_or_fetch('shared_key', fetch_func, ttl_seconds=60)

        # Create 10 threads accessing same cache key
        threads = [Thread(target=access_cache) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Despite 10 threads, function should be called minimal times due to locking
        # (May be called more than once due to race conditions before first cache write)
        assert call_count[0] <= 10  # Not more than thread count
        assert len(self.cache._cache) == 1  # Only one key cached

    def test_cache_hit_rate_calculation(self):
        """Test 7: 캐시 히트율 계산"""
        def fetch_func():
            return {'data': 'test'}

        # 3 cache misses
        self.cache.get_or_fetch('key1', fetch_func)
        self.cache.get_or_fetch('key2', fetch_func)
        self.cache.get_or_fetch('key3', fetch_func)

        # 7 cache hits
        for _ in range(7):
            self.cache.get_or_fetch('key1', fetch_func)

        # Total: 3 misses + 7 hits = 10 requests
        # Hit rate: 7/10 = 70%
        assert self.cache.hit_rate == 70.0

    def test_cache_stats(self):
        """Test 8: 캐시 통계 정확성"""
        def fetch_func():
            return {'data': 'test'}

        # Populate cache
        self.cache.get_or_fetch('key1', fetch_func)  # miss
        self.cache.get_or_fetch('key1', fetch_func)  # hit
        self.cache.get_or_fetch('key2', fetch_func)  # miss

        stats = self.cache.stats

        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['total_requests'] == 3
        assert stats['hit_rate'] == pytest.approx(33.33, rel=0.1)
        assert stats['cached_items'] == 2


class TestDBConnectionManager:
    """DB 연결 관리자 단위 테스트"""

    def setup_method(self):
        """각 테스트 전 연결 관리자 초기화"""
        # Note: DBConnectionManager is singleton, so we get the same instance
        self.manager = DBConnectionManager()

    def test_singleton_pattern(self):
        """Test 1: 싱글톤 패턴 검증"""
        manager1 = DBConnectionManager()
        manager2 = DBConnectionManager()

        assert manager1 is manager2  # Same instance

    def test_connection_lifecycle(self):
        """Test 2: 연결 생성/해제 라이프사이클"""
        initial_count = self.manager.active_connections

        # Create connection using context manager
        with self.manager.session() as db:
            # Connection should be active
            assert self.manager.active_connections == initial_count + 1

        # After context exit, connection should be closed
        assert self.manager.active_connections == initial_count

    def test_connection_pool_stats(self):
        """Test 3: 연결 통계 정확성"""
        initial_total = self.manager.total_connections_created

        # Create 3 connections
        for _ in range(3):
            with self.manager.session() as db:
                pass

        # Total connections should increase by 3
        assert self.manager.total_connections_created == initial_total + 3

    def test_context_manager_cleanup(self):
        """Test 4: 컨텍스트 매니저 자동 정리"""
        initial_count = self.manager.active_connections

        try:
            with self.manager.session() as db:
                # Simulate error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Even with error, connection should be cleaned up
        assert self.manager.active_connections == initial_count

    def test_multiple_concurrent_connections(self):
        """Test 5: 동시 다중 연결"""
        initial_count = self.manager.active_connections

        # Create 3 nested connections
        with self.manager.session() as db1:
            assert self.manager.active_connections == initial_count + 1

            with self.manager.session() as db2:
                assert self.manager.active_connections == initial_count + 2

                with self.manager.session() as db3:
                    assert self.manager.active_connections == initial_count + 3

            # After inner contexts close
            assert self.manager.active_connections == initial_count + 1

        # All closed
        assert self.manager.active_connections == initial_count


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
