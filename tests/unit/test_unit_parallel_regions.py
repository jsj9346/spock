#!/usr/bin/env python3
"""
Unit Tests for Parallel Region Refresh (Week 3)

Tests:
- Sequential vs Parallel execution
- Region worker allocation
- Error handling (Graceful degradation)
- Parallel flag toggle

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.ticker_refresh.ticker_refresher import TickerRefresher


class TestParallelRegionRefresh:
    """병렬 지역 수집 단위 테스트"""

    def setup_method(self):
        """각 테스트 전 TickerRefresher 초기화"""
        self.refresher = TickerRefresher()

    def test_sequential_execution(self):
        """Test 1: 순차 실행 모드"""
        # Mock refresh_region to track execution
        call_order = []

        def mock_refresh_region(region, incremental=True):
            call_order.append(region)
            return {
                'status': 'success',
                'new': 1,
                'updated': 0,
                'delisted': 0
            }

        self.refresher.refresh_region = mock_refresh_region

        # Execute sequentially
        result = self.refresher._refresh_all_regions_sequential(incremental=True)

        # Verify all regions processed
        assert len(result) == 6
        assert all(r['status'] == 'success' for r in result.values())

        # Verify sequential order
        assert call_order == ['KR', 'US', 'HK', 'JP', 'CN', 'VN']

    def test_parallel_execution(self):
        """Test 2: 병렬 실행 모드"""
        call_count = {'count': 0}

        def mock_refresh_region(region, incremental=True):
            call_count['count'] += 1
            time.sleep(0.05)  # 50ms delay
            return {
                'status': 'success',
                'new': 5,
                'updated': 2,
                'delisted': 1
            }

        self.refresher.refresh_region = mock_refresh_region

        # Execute in parallel
        start = time.time()
        result = self.refresher._refresh_all_regions_parallel(incremental=True)
        elapsed = time.time() - start

        # Verify all regions processed
        assert len(result) == 6
        assert all(r['status'] == 'success' for r in result.values())
        assert call_count['count'] == 6

        # Verify parallel execution (should be faster than sequential)
        # Sequential: 6 × 50ms = 300ms
        # Parallel: max(50ms) + overhead = ~100ms
        assert elapsed < 0.2  # Less than 200ms (generous for CI)

    def test_region_worker_allocation(self):
        """Test 3: 지역별 워커 할당"""
        def mock_refresh_region(region, incremental=True):
            return {'status': 'success', 'new': 0, 'updated': 0, 'delisted': 0}

        self.refresher.refresh_region = mock_refresh_region

        # Execute parallel - should use 6 workers for 6 regions
        result = self.refresher._refresh_all_regions_parallel(incremental=True)

        # All 6 regions should be processed
        assert len(result) == 6
        assert set(result.keys()) == {'KR', 'US', 'HK', 'JP', 'CN', 'VN'}

    def test_region_error_handling(self):
        """Test 4: 지역 오류 처리 (Graceful degradation)"""
        def mock_refresh_region(region, incremental=True):
            # US region fails
            if region == 'US':
                raise Exception("US API failure")

            return {
                'status': 'success',
                'new': 1,
                'updated': 0,
                'delisted': 0
            }

        self.refresher.refresh_region = mock_refresh_region

        # Execute parallel
        result = self.refresher._refresh_all_regions_parallel(incremental=True)

        # All regions should have results
        assert len(result) == 6

        # US should have error status
        assert result['US']['status'] == 'error'
        assert 'error' in result['US']

        # Other regions should succeed
        for region in ['KR', 'HK', 'JP', 'CN', 'VN']:
            assert result[region]['status'] == 'success'

    def test_parallel_flag_toggle(self):
        """Test 5: parallel 플래그 토글 동작"""
        execution_mode = []

        # Mock both sequential and parallel methods
        original_sequential = self.refresher._refresh_all_regions_sequential
        original_parallel = self.refresher._refresh_all_regions_parallel

        def mock_sequential(incremental=True):
            execution_mode.append('sequential')
            return {'KR': {'status': 'success', 'new': 0, 'updated': 0, 'delisted': 0}}

        def mock_parallel(incremental=True):
            execution_mode.append('parallel')
            return {'KR': {'status': 'success', 'new': 0, 'updated': 0, 'delisted': 0}}

        self.refresher._refresh_all_regions_sequential = mock_sequential
        self.refresher._refresh_all_regions_parallel = mock_parallel

        # Test parallel=True (default)
        self.refresher.refresh_all_regions(incremental=True, parallel=True)
        assert execution_mode[-1] == 'parallel'

        # Test parallel=False
        self.refresher.refresh_all_regions(incremental=True, parallel=False)
        assert execution_mode[-1] == 'sequential'

    def test_incremental_flag_propagation(self):
        """Test 6: incremental 플래그 전파"""
        received_flags = []

        def mock_refresh_region(region, incremental=True):
            received_flags.append(incremental)
            return {'status': 'success', 'new': 0, 'updated': 0, 'delisted': 0}

        self.refresher.refresh_region = mock_refresh_region

        # Test with incremental=True
        self.refresher._refresh_all_regions_parallel(incremental=True)
        assert all(flag is True for flag in received_flags)

        received_flags.clear()

        # Test with incremental=False
        self.refresher._refresh_all_regions_parallel(incremental=False)
        assert all(flag is False for flag in received_flags)

    def test_performance_comparison(self):
        """Test 7: 순차 vs 병렬 성능 비교"""
        def mock_refresh_region(region, incremental=True):
            time.sleep(0.05)  # 50ms per region
            return {'status': 'success', 'new': 5, 'updated': 2, 'delisted': 1}

        self.refresher.refresh_region = mock_refresh_region

        # Measure sequential execution
        start = time.time()
        self.refresher._refresh_all_regions_sequential(incremental=True)
        sequential_time = time.time() - start

        # Measure parallel execution
        start = time.time()
        self.refresher._refresh_all_regions_parallel(incremental=True)
        parallel_time = time.time() - start

        # Parallel should be significantly faster
        speedup = sequential_time / parallel_time

        # Expected: 6 workers processing 6 regions
        # Speedup should be close to 6x (allowing for overhead)
        assert speedup >= 3.0  # At least 3x faster

    def test_result_completeness(self):
        """Test 8: 결과 완전성 검증"""
        def mock_refresh_region(region, incremental=True):
            return {
                'status': 'success',
                'new': 10,
                'updated': 5,
                'delisted': 2,
                'errors': 0,
                'region': region
            }

        self.refresher.refresh_region = mock_refresh_region

        # Execute parallel
        result = self.refresher._refresh_all_regions_parallel(incremental=True)

        # Verify all fields present for each region
        for region in ['KR', 'US', 'HK', 'JP', 'CN', 'VN']:
            assert region in result
            assert 'status' in result[region]
            assert result[region]['new'] == 10
            assert result[region]['updated'] == 5
            assert result[region]['delisted'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
