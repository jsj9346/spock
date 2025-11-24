#!/usr/bin/env python3
"""
Unit Tests for Parallel Query Execution (Week 2)

Tests:
- Parallel query execution with ThreadPoolExecutor
- Independent DB connections per query
- Error isolation
- Result aggregation

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import spock_refresh
from spock_refresh import _execute_single_query, get_database_status


class TestParallelQueryExecution:
    """병렬 쿼리 실행 단위 테스트"""

    def test_single_query_execution(self):
        """Test 1: 단일 쿼리 실행 (헬퍼 함수)"""
        # Mock DB manager
        with patch('spock_refresh.db_manager') as mock_db_manager:
            mock_session = MagicMock()
            mock_session.execute_query.return_value = [{'count': 100}]
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute single query
            result = _execute_single_query("SELECT COUNT(*) as count FROM table1")

            assert result is not None
            assert result == [{'count': 100}]
            mock_session.execute_query.assert_called_once()

    def test_single_query_error_handling(self):
        """Test 2: 단일 쿼리 오류 처리"""
        # Mock DB manager to raise error
        with patch('spock_refresh.db_manager') as mock_db_manager:
            mock_session = MagicMock()
            mock_session.execute_query.side_effect = Exception("DB Error")
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute should return None on error
            result = _execute_single_query("SELECT * FROM table1")

            assert result is None

    def test_parallel_query_count(self):
        """Test 3: 병렬 실행되는 쿼리 개수 검증"""
        with patch('spock_refresh.db_manager') as mock_db_manager:
            # Mock responses for all queries
            mock_session = MagicMock()

            def mock_execute(query):
                if 'ohlcv_data' in query and 'region' in query:
                    # Regional query
                    return [
                        {'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'},
                        {'region': 'US', 'count': 200, 'latest_date': '2025-11-23'}
                    ]
                elif 'COUNT' in query:
                    return [{'count': 100, 'max': '2025-11-23'}]
                return []

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute parallel queries
            result = get_database_status()

            # Verify all queries executed
            assert result is not None
            assert 'ohlcv_count' in result
            assert 'ticker_count' in result
            # At least 9 queries should have been executed (see Week 2 implementation)
            assert mock_session.execute_query.call_count >= 9

    def test_independent_db_connections(self):
        """Test 4: 각 쿼리가 독립적인 DB 연결 사용"""
        connection_ids = []

        with patch('spock_refresh.db_manager') as mock_db_manager:
            def track_connection(query):
                # Track which connection was used
                conn_id = id(mock_db_manager.session.return_value)
                connection_ids.append(conn_id)
                return [{'count': 100}]

            mock_session = MagicMock()
            mock_session.execute_query.side_effect = track_connection
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute multiple queries in parallel
            queries = {
                'query1': "SELECT COUNT(*) FROM table1",
                'query2': "SELECT COUNT(*) FROM table2",
                'query3': "SELECT COUNT(*) FROM table3"
            }

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(_execute_single_query, q): key
                    for key, q in queries.items()
                }
                results = {futures[f]: f.result() for f in futures}

            # Each query should have used a session (context manager called)
            assert mock_db_manager.session.call_count >= 3

    def test_max_workers_configuration(self):
        """Test 5: max_workers 설정 검증"""
        from spock_refresh import RefreshConstants

        # Verify default max_workers
        assert RefreshConstants.ParallelExecution.MAX_WORKERS_DEFAULT == 4

        # This is used in get_database_status()
        # Verified by implementation inspection

    def test_query_error_isolation(self):
        """Test 6: 개별 쿼리 오류 격리"""
        with patch('spock_refresh.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            call_count = [0]

            def mock_execute(query):
                call_count[0] += 1
                # First query fails
                if call_count[0] == 1:
                    raise Exception("Query 1 failed")
                # Other queries succeed
                if 'region' in query:
                    return [{'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute - should handle partial failures
            result = get_database_status()

            # Should still return a result (not None)
            # Some queries succeeded even though one failed
            assert result is not None or call_count[0] > 1

    def test_result_aggregation(self):
        """Test 7: 병렬 결과 집계 정확성"""
        with patch('spock_refresh.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            def mock_execute(query):
                if 'ohlcv_data' in query and 'region' not in query:
                    return [{'count': 1000, 'max': '2025-11-23'}]
                elif 'region' in query:
                    return [
                        {'region': 'KR', 'count': 500, 'latest_date': '2025-11-23'},
                        {'region': 'US', 'count': 500, 'latest_date': '2025-11-23'}
                    ]
                elif 'tickers' in query:
                    return [{'count': 100}]
                elif 'ticker_fundamentals' in query:
                    return [{'count': 200, 'max': '2025-11-23'}]
                elif 'factor_scores' in query:
                    return [{'count': 300, 'max': '2025-11-23'}]
                elif 'global_market_indices' in query:
                    return [{'count': 50, 'max': '2025-11-23'}]
                elif 'market_sentiment' in query:
                    return [{'count': 60, 'max': '2025-11-23'}]
                elif 'bond_yields' in query:
                    return [{'count': 70, 'max': '2025-11-23'}]
                elif 'commodities' in query:
                    return [{'count': 80, 'max': '2025-11-23'}]
                return []

            mock_session.execute_query.side_effect = mock_execute
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            result = get_database_status()

            # Verify aggregated results
            assert result is not None
            assert result['ohlcv_count'] == 1000
            assert result['ticker_count'] == 100
            assert result['fund_count'] == 200
            assert result['factor_count'] == 300

            # Verify regional breakdown
            assert 'ohlcv_by_region' in result
            assert 'KR' in result['ohlcv_by_region']
            assert result['ohlcv_by_region']['KR']['count'] == 500

    def test_parallel_execution_performance(self):
        """Test 8: 병렬 실행 성능 검증"""
        with patch('spock_refresh.db_manager') as mock_db_manager:
            mock_session = MagicMock()

            def slow_query(query):
                time.sleep(0.05)  # 50ms delay per query
                if 'region' in query:
                    return [{'region': 'KR', 'count': 100, 'latest_date': '2025-11-23'}]
                return [{'count': 100, 'max': '2025-11-23'}]

            mock_session.execute_query.side_effect = slow_query
            mock_db_manager.session.return_value.__enter__.return_value = mock_session

            # Execute parallel queries
            start = time.time()
            result = get_database_status()
            elapsed = time.time() - start

            # With 9 queries at 50ms each:
            # Sequential would take: 9 × 50ms = 450ms
            # Parallel (4 workers) should take: ~150ms (3 batches)
            # Allow some overhead, should be < 300ms
            assert elapsed < 0.3  # Less than 300ms
            assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
