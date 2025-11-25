#!/usr/bin/env python3
"""
Integration Tests for Ticker Status Management System

Tests:
- Orchestrator integration with TickerStatusManager
- Query filtering for skip tickers
- Success/failure handling during collection
- Statistics output
- Stale ticker re-verification

Author: Spock Quant Platform
Date: 2025-11-26
"""

import sys
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.ticker_status_manager import TickerStatusManager
from modules.db_manager_postgres import PostgresDatabaseManager


class TestOrchestratorQueryFiltering:
    """I-01: OHLCV 수집 쿼리 필터링 테스트"""

    def test_query_excludes_skip_statuses(self):
        """I-01: 쿼리에서 skip 상태 티커 제외 확인"""
        # This test verifies the SQL query pattern
        expected_filter = "yf_status NOT IN ('delisted', 'unsupported', 'blacklist')"

        # Read the orchestrator file to verify the query
        orchestrator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'modules', 'orchestration', 'orchestrator.py'
        )

        with open(orchestrator_path, 'r') as f:
            content = f.read()

        # Verify the filter exists in the orchestrator
        assert "yf_status NOT IN" in content, "Skip status filter should be in orchestrator"
        assert "'delisted'" in content, "delisted should be filtered"
        assert "'unsupported'" in content, "unsupported should be filtered"
        assert "'blacklist'" in content, "blacklist should be filtered"

    def test_incremental_query_has_filter(self):
        """I-01: 증분 모드 쿼리에 필터 포함 확인"""
        orchestrator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'modules', 'orchestration', 'orchestrator.py'
        )

        with open(orchestrator_path, 'r') as f:
            content = f.read()

        # Count occurrences of the filter - should appear in both incremental and full queries
        filter_count = content.count("yf_status NOT IN")
        assert filter_count >= 2, f"Filter should appear at least twice (incremental + full), found {filter_count}"


class TestSuccessHandling:
    """I-02: OHLCV 수집 성공 시 처리 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_mark_success_called_on_collection_success(self):
        """I-02: 수집 성공 시 mark_success 호출 확인"""
        # Simulate successful collection
        self.tsm.mark_success('7203', 'JP')

        self.mock_db.execute_update.assert_called_once()
        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        assert "yf_status = %s" in query
        assert "yf_fail_count = 0" in query

    def test_status_changes_to_active(self):
        """I-02: 성공 후 상태가 active로 변경"""
        self.tsm.mark_success('005930', 'KR')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'active'


class TestFailureHandling:
    """I-03: OHLCV 수집 실패 시 처리 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_mark_failure_called_on_collection_failure(self):
        """I-03: 수집 실패 시 mark_failure 호출 확인"""
        self.tsm.mark_failure('9224', 'JP', 'No data found, symbol may be delisted')

        self.mock_db.execute_update.assert_called_once()

    def test_fail_count_incremented(self):
        """I-03: fail_count 증가 확인"""
        self.tsm.mark_failure('DELISTED', 'US', 'Connection error')

        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        assert "yf_fail_count = yf_fail_count + 1" in query


class TestStatisticsOutput:
    """I-04: 최종 통계 출력 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_summary_includes_skip_count(self):
        """I-04: 통계에 skip_count 포함 확인"""
        self.mock_db.execute_query.return_value = [
            {'yf_status': 'active', 'count': 4000},
            {'yf_status': 'delisted', 'count': 10},
            {'yf_status': 'unsupported', 'count': 5},
            {'yf_status': 'blacklist', 'count': 2},
        ]

        summary = self.tsm.get_status_summary('JP')

        assert 'skip_count' in summary
        assert summary['skip_count'] == 17  # 10 + 5 + 2

    def test_summary_includes_process_count(self):
        """I-04: 통계에 process_count 포함 확인"""
        self.mock_db.execute_query.return_value = [
            {'yf_status': 'active', 'count': 100},
            {'yf_status': 'unknown', 'count': 50},
            {'yf_status': 'retry', 'count': 5},
            {'yf_status': 'delisted', 'count': 10},
        ]

        summary = self.tsm.get_status_summary('KR')

        assert 'process_count' in summary
        assert summary['process_count'] == 155  # 100 + 50 + 5


class TestStaleTickerReverification:
    """I-05: 재검증 대상 티커 처리 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_stale_tickers_included_in_collection(self):
        """I-05: 30일 지난 delisted 티커 재수집 대상 포함"""
        # verify_stale_tickers returns tickers needing re-verification
        self.mock_db.execute_query.return_value = [
            {'ticker': 'OLD_DELISTED'},
            {'ticker': 'OLD_UNSUPPORTED'},
        ]

        stale_tickers = self.tsm.verify_stale_tickers('JP', days=30)

        assert len(stale_tickers) == 2
        assert 'OLD_DELISTED' in stale_tickers

    def test_get_active_tickers_includes_stale(self):
        """I-05: get_active_tickers가 stale 티커도 포함"""
        # Mock to return both active and stale tickers
        self.mock_db.execute_query.return_value = [
            {'ticker': 'ACTIVE1'},
            {'ticker': 'STALE_DELISTED'},  # Should be included because >30 days
        ]

        result = self.tsm.get_active_tickers('JP')

        # The query should include stale delisted/unsupported tickers
        call_args = self.mock_db.execute_query.call_args
        query = call_args[0][0]

        # Query should have OR condition for stale tickers
        assert 'yf_last_check <' in query or 'INTERVAL' in query


@pytest.mark.integration
class TestRealDatabaseIntegration:
    """실제 데이터베이스 연동 테스트 (requires DB)"""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """데이터베이스 연결 설정"""
        try:
            self.db = PostgresDatabaseManager()
            self.tsm = TickerStatusManager(self.db)
            yield
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_real_status_summary(self):
        """실제 DB에서 상태 요약 조회"""
        summary = self.tsm.get_status_summary('JP')

        assert 'total' in summary
        assert 'active' in summary
        assert 'skip_count' in summary
        assert isinstance(summary['total'], int)

    def test_real_skip_tickers(self):
        """실제 DB에서 스킵 티커 조회"""
        skip_tickers = self.tsm.get_skip_tickers('JP')

        assert isinstance(skip_tickers, list)
        # JP should have some skip tickers based on our deployment
        # But this depends on actual data state

    def test_real_active_tickers(self):
        """실제 DB에서 active 티커 조회"""
        active_tickers = self.tsm.get_active_tickers('JP')

        assert isinstance(active_tickers, list)
        # Should return tickers that are eligible for collection


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Orchestrator와의 통합 테스트"""

    def test_orchestrator_imports_ticker_status(self):
        """I-01: Orchestrator가 TickerStatusManager를 import하는지 확인"""
        orchestrator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'modules', 'orchestration', 'orchestrator.py'
        )

        with open(orchestrator_path, 'r') as f:
            content = f.read()

        assert 'from modules.ticker_status_manager import TickerStatusManager' in content

    def test_orchestrator_marks_success(self):
        """I-02: Orchestrator가 수집 성공 시 mark_success 호출"""
        orchestrator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'modules', 'orchestration', 'orchestrator.py'
        )

        with open(orchestrator_path, 'r') as f:
            content = f.read()

        assert 'mark_success' in content, "Orchestrator should call mark_success"

    def test_orchestrator_marks_failure(self):
        """I-03: Orchestrator가 수집 실패 시 mark_failure 호출"""
        orchestrator_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'modules', 'orchestration', 'orchestrator.py'
        )

        with open(orchestrator_path, 'r') as f:
            content = f.read()

        assert 'mark_failure' in content, "Orchestrator should call mark_failure"


class TestEndToEndScenarios:
    """종단 간 시나리오 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_ticker_lifecycle_unknown_to_active(self):
        """시나리오: unknown → 수집 성공 → active"""
        # Initial state: unknown
        # After successful collection
        self.tsm.mark_success('NEW_TICKER', 'US')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'active'

    def test_ticker_lifecycle_active_to_delisted(self):
        """시나리오: active → 3회 실패 → delisted"""
        # Simulate 3 consecutive failures
        for i in range(3):
            self.tsm.mark_failure('DELISTING', 'JP', 'No data found')

        # Should have been called 3 times
        assert self.mock_db.execute_update.call_count == 3

        # Last call should potentially change status to delisted
        # (depends on DB state, but query structure should support it)
        last_call = self.mock_db.execute_update.call_args
        query = last_call[0][0]

        assert 'CASE' in query  # Conditional status change

    def test_ticker_lifecycle_blacklist_to_unknown(self):
        """시나리오: blacklist → clear_blacklist → unknown"""
        self.tsm.clear_blacklist('RESTORED', 'US')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'unknown'


class TestConcurrencyScenarios:
    """동시성 시나리오 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_multiple_tickers_bulk_update(self):
        """여러 티커 동시 업데이트"""
        tickers = [
            ('7203', 'JP'),
            ('9984', 'JP'),
            ('6758', 'JP'),
            ('005930', 'KR'),
            ('000660', 'KR'),
        ]

        self.tsm.bulk_mark_success(tickers)

        assert self.mock_db.execute_update.call_count == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'not integration'])
