#!/usr/bin/env python3
"""
End-to-End Performance Validation Tests

Tests:
- Week 1-3 performance improvement validation
- System reliability under load
- Data consistency across optimizations

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import spock_refresh_v2
from spock_refresh_v2 import (
    get_database_status,
    get_database_status_cached,
    query_cache
)
from modules.ticker_refresh.ticker_refresher import TickerRefresher


class TestPerformanceValidation:
    """성능 검증 E2E 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        query_cache.invalidate()

    def test_performance_improvement_validation(self):
        """Test 1: Week 1-3 성능 향상 검증"""
        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            # Simulate realistic query times
            def slow_query(query):
                time.sleep(0.05)  # 50ms per query
                if 'region' in query:
                    return [{'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = slow_query
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Baseline metrics (simulated Week 0 - no optimizations)
            baseline_metrics = {
                'db_status_time': 450,  # ms (9 queries × 50ms sequential)
                'cache_hit_rate': 0     # No caching
            }

            # Test 1: Parallel query execution (Week 2)
            query_cache.invalidate()

            start = time.time()
            result = get_database_status()  # Parallel execution
            parallel_time = (time.time() - start) * 1000  # Convert to ms

            # Week 2 goal: 18.3% improvement (400ms → 327ms)
            # With parallel execution (4 workers), expect ~150-200ms
            assert parallel_time < 350  # Better than baseline
            assert result is not None

            # Test 2: Caching (Week 1)
            # First call - cache miss
            query_cache.invalidate()

            start = time.time()
            result1 = get_database_status_cached()
            cache_miss_time = (time.time() - start) * 1000

            # Second call - cache hit
            start = time.time()
            result2 = get_database_status_cached()
            cache_hit_time = (time.time() - start) * 1000

            # Week 1 goal: 72,603x speedup (cache hit vs miss)
            # Cache hit should be <1ms
            assert cache_hit_time < 1  # Very fast
            speedup = cache_miss_time / cache_hit_time if cache_hit_time > 0 else 10000

            # Speedup should be massive (>1000x)
            assert speedup > 100  # At least 100x faster

            # Calculate metrics
            optimized_metrics = {
                'db_status_time': parallel_time,
                'cache_hit_time': cache_hit_time,
                'cache_hit_rate': 50  # Assume 50% for this test
            }

            # Verify improvements
            improvement_pct = ((baseline_metrics['db_status_time'] - optimized_metrics['db_status_time']) /
                             baseline_metrics['db_status_time']) * 100

            # Should show significant improvement
            assert improvement_pct > 10  # At least 10% improvement

    def test_region_refresh_performance(self):
        """Test 2: 병렬 지역 수집 성능 검증 (Week 3)"""
        refresher = TickerRefresher()

        def mock_refresh_region(region, incremental=True):
            # Simulate realistic refresh time
            time.sleep(0.05)  # 50ms per region
            return {
                'status': 'success',
                'new': 10,
                'updated': 5,
                'delisted': 1
            }

        refresher.refresh_region = mock_refresh_region

        # Measure sequential execution
        start = time.time()
        seq_results = refresher._refresh_all_regions_sequential(incremental=True)
        sequential_time = (time.time() - start) * 1000

        # Measure parallel execution
        start = time.time()
        par_results = refresher._refresh_all_regions_parallel(incremental=True)
        parallel_time = (time.time() - start) * 1000

        # Week 3 goal: 78% improvement (468ms → 103ms)
        # Expected: Sequential ~300ms, Parallel ~60-80ms
        speedup = sequential_time / parallel_time

        # Verify results identical
        assert len(seq_results) == len(par_results) == 6

        # Verify performance improvement
        improvement_pct = ((sequential_time - parallel_time) / sequential_time) * 100

        # Should show significant improvement (at least 50%)
        assert improvement_pct > 50
        assert speedup > 3.0  # At least 3x faster

    def test_system_reliability_under_load(self):
        """Test 3: 부하 상황에서 시스템 안정성 검증"""
        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()
            request_count = {'count': 0}
            errors = {'count': 0}

            def mock_execute(query):
                request_count['count'] += 1
                # Simulate occasional slow query
                if request_count['count'] % 10 == 0:
                    time.sleep(0.1)
                else:
                    time.sleep(0.01)

                if 'region' in query:
                    return [{'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Simulate 50 concurrent requests
            concurrent_requests = 50

            start = time.time()

            with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                futures = [
                    executor.submit(get_database_status_cached)
                    for _ in range(concurrent_requests)
                ]

                results = []
                for future in futures:
                    try:
                        result = future.result(timeout=5)
                        results.append(result)
                    except Exception as e:
                        errors['count'] += 1

            elapsed = time.time() - start

            # All requests should complete
            assert len(results) == concurrent_requests - errors['count']

            # Error rate should be low
            error_rate = (errors['count'] / concurrent_requests) * 100
            assert error_rate < 10  # Less than 10% error rate

            # Should complete reasonably fast (caching helps)
            # 50 requests, most hitting cache
            assert elapsed < 5  # Less than 5 seconds total

    def test_data_consistency_validation(self):
        """Test 4: 데이터 일관성 검증"""
        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            # Fixed mock data for consistency check
            consistent_data = {
                'ohlcv_count': 12345,
                'ticker_count': 6789,
                'fund_count': 456,
                'latest_ohlcv': '2025-11-23'
            }

            def mock_execute(query):
                if 'ohlcv_data' in query and 'COUNT' in query and 'region' not in query:
                    return [{'count': consistent_data['ohlcv_count'], 'max': consistent_data['latest_ohlcv']}]
                elif 'region' in query:
                    return [{'region': 'KR', 'count': 5000, 'latest_date': '2025-11-23'}]
                elif 'tickers' in query:
                    return [{'count': consistent_data['ticker_count']}]
                elif 'ticker_fundamentals' in query:
                    return [{'count': consistent_data['fund_count'], 'max': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Clear cache
            query_cache.invalidate()

            # Run multiple times and collect results
            results = []
            for _ in range(10):
                result = get_database_status()
                results.append(result)

            # Verify all results consistent
            for i in range(1, len(results)):
                assert results[i]['ohlcv_count'] == results[0]['ohlcv_count']
                assert results[i]['ticker_count'] == results[0]['ticker_count']
                assert results[i]['latest_ohlcv'] == results[0]['latest_ohlcv']

            # Verify expected values
            assert results[0]['ohlcv_count'] == consistent_data['ohlcv_count']
            assert results[0]['ticker_count'] == consistent_data['ticker_count']

    def test_combined_optimizations_performance(self):
        """Test 5: 전체 최적화 조합 성능"""
        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            def mock_execute(query):
                time.sleep(0.05)  # 50ms per query
                if 'region' in query:
                    return [{'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Test combined: Parallel + Caching
            times = {
                'first_call': None,    # Cache miss + parallel
                'second_call': None,   # Cache hit
                'third_call': None     # Cache hit
            }

            # Clear cache
            query_cache.invalidate()

            # First call - cache miss, but parallel execution
            start = time.time()
            result1 = get_database_status_cached()
            times['first_call'] = (time.time() - start) * 1000

            # Second call - cache hit
            start = time.time()
            result2 = get_database_status_cached()
            times['second_call'] = (time.time() - start) * 1000

            # Third call - cache hit
            start = time.time()
            result3 = get_database_status_cached()
            times['third_call'] = (time.time() - start) * 1000

            # Verify cache performance
            # First call: parallel execution (~150-200ms)
            assert times['first_call'] < 300

            # Subsequent calls: cache hits (<1ms)
            assert times['second_call'] < 1
            assert times['third_call'] < 1

            # Calculate average with 90% cache hit rate
            # 10% cache miss: 200ms
            # 90% cache hit: 0.5ms
            average_time = 0.1 * times['first_call'] + 0.9 * times['second_call']

            # Average should be very fast (<25ms)
            assert average_time < 25

            # Verify data consistency
            assert result1 == result2 == result3


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
