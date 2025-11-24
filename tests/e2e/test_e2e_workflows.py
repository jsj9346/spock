#!/usr/bin/env python3
"""
End-to-End Tests for Complete Workflows

Tests:
- Daily refresh workflow (status → parallel region update → cache invalidation)
- Incremental update workflow
- Full refresh workflow
- Error recovery workflow

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

import spock_refresh_v2
from spock_refresh_v2 import (
    get_database_status_cached,
    query_cache
)
from modules.ticker_refresh.ticker_refresher import TickerRefresher


class TestEndToEndWorkflows:
    """전체 워크플로우 E2E 테스트"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        query_cache.invalidate()

    def test_daily_refresh_workflow(self):
        """Test 1: 일일 데이터 갱신 워크플로우"""
        # This workflow simulates:
        # 1. Check current status (using cache)
        # 2. Refresh regions in parallel
        # 3. Update database
        # 4. Invalidate cache
        # 5. Verify final status

        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            # Stage 1: Initial status check
            def mock_execute_initial(query):
                if 'region' in query:
                    return [{'region': 'KR', 'count': 1000, 'latest_date': '2025-11-22'}]  # Yesterday
                return [{'count': 1000, 'max': '2025-11-22'}]

            mock_session.execute_query.side_effect = mock_execute_initial
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Step 1: Check status (should show yesterday's data)
            initial_status = get_database_status_cached()
            assert initial_status is not None
            assert initial_status['latest_ohlcv'] == '2025-11-22'

            # Step 2: Simulate region refresh
            refresher = TickerRefresher()

            def mock_refresh_region(region, incremental=True):
                time.sleep(0.01)  # Simulate work
                return {
                    'status': 'success',
                    'new': 10,
                    'updated': 5,
                    'delisted': 0
                }

            refresher.refresh_region = mock_refresh_region

            # Execute parallel refresh
            refresh_results = refresher.refresh_all_regions(incremental=True, parallel=True)

            # Verify all regions refreshed
            assert len(refresh_results) == 6
            assert all(r['status'] == 'success' for r in refresh_results.values())

            # Step 3: Simulate DB update (mock new data)
            def mock_execute_updated(query):
                if 'region' in query:
                    return [{'region': 'KR', 'count': 1015, 'latest_date': '2025-11-23'}]  # Today
                return [{'count': 1015, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute_updated

            # Step 4: Invalidate cache
            query_cache.invalidate()

            # Step 5: Verify final status
            final_status = get_database_status_cached()
            assert final_status is not None
            assert final_status['latest_ohlcv'] == '2025-11-23'  # Updated to today
            assert final_status['ohlcv_count'] == 1015  # Increased by 15 (10 new + 5 updated)

    def test_incremental_update_workflow(self):
        """Test 2: 증분 업데이트 워크플로우"""
        # This workflow simulates:
        # 1. Check last update time
        # 2. Refresh only changed regions (parallel)
        # 3. Selective cache invalidation

        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            def mock_execute(query):
                if 'region' in query:
                    return [
                        {'region': 'KR', 'count': 1000, 'latest_date': '2025-11-23'},  # Up to date
                        {'region': 'US', 'count': 500, 'latest_date': '2025-11-22'}   # Needs update
                    ]
                return [{'count': 1500, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Step 1: Check current status
            status = get_database_status_cached()
            assert status is not None

            # Identify regions needing update (US only)
            regions_to_update = ['US']  # Only US is outdated

            # Step 2: Refresh only changed regions
            refresher = TickerRefresher()

            def mock_refresh_region(region, incremental=True):
                # Only US actually refreshes
                if region == 'US':
                    return {'status': 'success', 'new': 20, 'updated': 10, 'delisted': 0}
                return {'status': 'skipped', 'new': 0, 'updated': 0, 'delisted': 0}

            refresher.refresh_region = mock_refresh_region

            # Refresh all (but only US actually updates)
            results = {}
            for region in regions_to_update:
                results[region] = refresher.refresh_region(region, incremental=True)

            # Verify only US updated
            assert results['US']['status'] == 'success'
            assert results['US']['new'] == 20

            # Step 3: Selective cache invalidation (only affected queries)
            query_cache.invalidate(pattern='database_status')

    def test_full_refresh_workflow(self):
        """Test 3: 전체 갱신 워크플로우"""
        # This workflow simulates:
        # 1. Full cache invalidation
        # 2. All regions parallel refresh
        # 3. Full DB update
        # 4. Build new cache

        with patch('spock_refresh_v2.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            # Stage 1: Old data
            def mock_execute_old(query):
                if 'region' in query:
                    return [{'region': 'KR', 'count': 1000, 'latest_date': '2025-11-20'}]
                return [{'count': 1000, 'max': '2025-11-20'}]

            mock_session.execute_query.side_effect = mock_execute_old
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Step 1: Full cache invalidation
            query_cache.invalidate()

            # Verify cache is empty
            assert len(query_cache._cache) == 0

            # Step 2: Refresh all regions in parallel
            refresher = TickerRefresher()

            def mock_refresh_region(region, incremental=False):
                time.sleep(0.02)  # Simulate work
                return {
                    'status': 'success',
                    'new': 50,
                    'updated': 30,
                    'delisted': 5
                }

            refresher.refresh_region = mock_refresh_region

            # Execute full refresh (incremental=False)
            start = time.time()
            results = refresher.refresh_all_regions(incremental=False, parallel=True)
            elapsed = time.time() - start

            # Verify all regions refreshed
            assert len(results) == 6
            assert all(r['status'] == 'success' for r in results.values())

            # Verify parallel execution (should be fast)
            # 6 regions × 20ms = 120ms sequential
            # Parallel with 6 workers: ~30ms
            assert elapsed < 0.1  # Less than 100ms

            # Step 3: Simulate full DB update
            def mock_execute_new(query):
                if 'region' in query:
                    return [{'region': 'KR', 'count': 1080, 'latest_date': '2025-11-23'}]
                return [{'count': 1080, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute_new

            # Step 4: Build new cache
            new_status = get_database_status_cached()

            # Verify cache populated
            assert len(query_cache._cache) > 0
            assert new_status['ohlcv_count'] == 1080
            assert new_status['latest_ohlcv'] == '2025-11-23'

    def test_error_recovery_workflow(self):
        """Test 4: 오류 복구 워크플로우"""
        # This workflow simulates:
        # 1. Detect partial region failures
        # 2. Process successful regions
        # 3. Retry failed regions
        # 4. Verify final state

        refresher = TickerRefresher()

        # Simulate region failures
        failure_count = {'US': 2}  # US will fail 2 times, then succeed

        def mock_refresh_region(region, incremental=True):
            if region == 'US':
                if failure_count['US'] > 0:
                    failure_count['US'] -= 1
                    raise Exception(f"US API failure (attempts left: {failure_count['US']})")

            # Other regions succeed
            return {
                'status': 'success',
                'new': 10,
                'updated': 5,
                'delisted': 0
            }

        refresher.refresh_region = mock_refresh_region

        # Step 1: Initial refresh - US fails
        results_1 = refresher.refresh_all_regions(incremental=True, parallel=True)

        # Verify US failed, others succeeded
        assert results_1['US']['status'] == 'error'
        assert all(
            results_1[r]['status'] == 'success'
            for r in ['KR', 'HK', 'JP', 'CN', 'VN']
        )

        # Step 2: Retry US only
        results_2 = refresher.refresh_all_regions(incremental=True, parallel=True)

        # US still fails (1 attempt left)
        assert results_2['US']['status'] == 'error'

        # Step 3: Final retry
        results_3 = refresher.refresh_all_regions(incremental=True, parallel=True)

        # US succeeds on third attempt
        assert results_3['US']['status'] == 'success'

        # Step 4: Verify all regions now successful
        assert all(r['status'] == 'success' for r in results_3.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
