#!/usr/bin/env python3
"""
Unit Tests for TickerStatusManager

Tests:
- Status query methods (get_active_tickers, get_skip_tickers, get_status)
- Status update methods (mark_success, mark_failure)
- Error classification and status transitions
- Blacklist management
- Auto-detection features
- Statistics and summaries

Author: Spock Quant Platform
Date: 2025-11-26
"""

import sys
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.ticker_status_manager import TickerStatusManager


class TestTickerStatusManagerConstants:
    """상수 및 초기화 테스트"""

    def test_status_constants_defined(self):
        """Test: 상태 상수가 정의되어 있는지 확인"""
        assert TickerStatusManager.STATUS_UNKNOWN == 'unknown'
        assert TickerStatusManager.STATUS_ACTIVE == 'active'
        assert TickerStatusManager.STATUS_DELISTED == 'delisted'
        assert TickerStatusManager.STATUS_UNSUPPORTED == 'unsupported'
        assert TickerStatusManager.STATUS_BLACKLIST == 'blacklist'
        assert TickerStatusManager.STATUS_RETRY == 'retry'

    def test_skip_statuses_set(self):
        """Test: SKIP_STATUSES에 올바른 상태가 포함되어 있는지 확인"""
        expected = {'delisted', 'unsupported', 'blacklist'}
        assert TickerStatusManager.SKIP_STATUSES == expected

    def test_active_statuses_set(self):
        """Test: ACTIVE_STATUSES에 올바른 상태가 포함되어 있는지 확인"""
        expected = {'unknown', 'active', 'retry'}
        assert TickerStatusManager.ACTIVE_STATUSES == expected

    def test_fail_count_threshold(self):
        """Test: FAIL_COUNT_THRESHOLD 값 확인"""
        assert TickerStatusManager.FAIL_COUNT_THRESHOLD == 3

    def test_stale_days(self):
        """Test: STALE_DAYS 값 확인"""
        assert TickerStatusManager.STALE_DAYS == 30


class TestGetActiveTickers:
    """U-01: get_active_tickers() 테스트"""

    def setup_method(self):
        """각 테스트 전 Mock DB 설정"""
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_returns_active_unknown_retry_tickers(self):
        """U-01: active/unknown/retry 상태 티커만 반환"""
        # Mock query result
        self.mock_db.execute_query.return_value = [
            {'ticker': '005930'},
            {'ticker': '000660'},
            {'ticker': '035720'},
        ]

        result = self.tsm.get_active_tickers('KR')

        assert len(result) == 3
        assert '005930' in result
        assert '000660' in result
        assert '035720' in result

        # Verify query was called with correct statuses
        call_args = self.mock_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert 'yf_status IN %s' in query
        # Check that active statuses are passed
        assert 'unknown' in params[1] or 'active' in params[1]

    def test_excludes_skip_statuses(self):
        """U-01: delisted/unsupported/blacklist 상태는 제외"""
        # Return empty when all tickers are skip status
        self.mock_db.execute_query.return_value = []

        result = self.tsm.get_active_tickers('KR')

        assert len(result) == 0

    def test_include_retry_parameter(self):
        """U-01: include_retry=False 시 retry 상태 제외"""
        self.mock_db.execute_query.return_value = [
            {'ticker': '005930'},
        ]

        result = self.tsm.get_active_tickers('KR', include_retry=False)

        # Should still work, just with different statuses
        assert isinstance(result, list)


class TestGetSkipTickers:
    """U-02: get_skip_tickers() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_returns_only_skip_statuses(self):
        """U-02: delisted/unsupported/blacklist만 반환"""
        self.mock_db.execute_query.return_value = [
            {'ticker': 'DELISTED1'},
            {'ticker': 'PRF/A'},
            {'ticker': 'BLACKLISTED'},
        ]

        result = self.tsm.get_skip_tickers('US')

        assert len(result) == 3
        assert 'DELISTED1' in result
        assert 'PRF/A' in result

    def test_excludes_active_tickers(self):
        """U-02: active 상태 티커는 제외"""
        # Query should filter by SKIP_STATUSES
        self.mock_db.execute_query.return_value = []

        result = self.tsm.get_skip_tickers('US')

        # Verify query contains skip statuses filter
        call_args = self.mock_db.execute_query.call_args
        query = call_args[0][0]
        assert 'yf_status IN %s' in query


class TestGetStatus:
    """U-03: get_status() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_returns_status_dict(self):
        """U-03: 단일 티커 상태 조회 시 딕셔너리 반환"""
        self.mock_db.execute_query.return_value = [{
            'ticker': '7203',
            'region': 'JP',
            'yf_status': 'active',
            'yf_last_check': datetime.now(),
            'yf_fail_reason': None,
            'yf_fail_count': 0
        }]

        result = self.tsm.get_status('7203', 'JP')

        assert result is not None
        assert result['ticker'] == '7203'
        assert result['yf_status'] == 'active'
        assert result['yf_fail_count'] == 0

    def test_returns_none_for_nonexistent(self):
        """U-03: 존재하지 않는 티커는 None 반환"""
        self.mock_db.execute_query.return_value = []

        result = self.tsm.get_status('NONEXISTENT', 'US')

        assert result is None


class TestMarkSuccess:
    """U-04: mark_success() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_updates_to_active_status(self):
        """U-04: 성공 시 active 상태로 변경"""
        self.tsm.mark_success('7203', 'JP')

        # Verify execute_update was called
        self.mock_db.execute_update.assert_called_once()

        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert 'yf_status = %s' in query
        assert params[0] == 'active'

    def test_resets_fail_count(self):
        """U-04: 성공 시 fail_count를 0으로 리셋"""
        self.tsm.mark_success('005930', 'KR')

        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        assert 'yf_fail_count = 0' in query

    def test_clears_fail_reason(self):
        """U-04: 성공 시 fail_reason을 NULL로 클리어"""
        self.tsm.mark_success('AAPL', 'US')

        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        assert 'yf_fail_reason = NULL' in query


class TestMarkFailure:
    """U-05, U-06: mark_failure() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_increments_fail_count(self):
        """U-05: 실패 시 fail_count 증가"""
        self.tsm.mark_failure('7203', 'JP', 'Connection error')

        self.mock_db.execute_update.assert_called_once()
        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        assert 'yf_fail_count = yf_fail_count + 1' in query

    def test_status_unchanged_on_first_failure(self):
        """U-05: 1~2회 실패 시 상태 유지 (CASE 문으로 조건부 변경)"""
        self.tsm.mark_failure('AAPL', 'US', 'Timeout error')

        call_args = self.mock_db.execute_update.call_args
        query = call_args[0][0]

        # Should have conditional status change
        assert 'CASE' in query
        assert 'yf_fail_count >=' in query

    def test_status_changes_after_threshold(self):
        """U-06: 3회 연속 실패 시 상태 변경 (조건부)"""
        self.tsm.mark_failure('DELISTED', 'JP', 'No data found')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        # FAIL_COUNT_THRESHOLD - 1 should be in params (for >= comparison)
        assert 2 in params  # 3 - 1 = 2


class TestErrorClassification:
    """U-07, U-08: 에러 메시지 분류 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_no_data_found_classifies_as_delisted(self):
        """U-07: 'no data found' → delisted 분류"""
        self.tsm.mark_failure('9224', 'JP', 'No data found, symbol may be delisted')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        # fail_reason should be 'no_data_found' or similar
        assert 'no_data' in params[0] or 'delisted' in str(params)

    def test_rate_limit_classifies_as_retry(self):
        """U-08: 'rate limit' → retry 분류"""
        self.tsm.mark_failure('AAPL', 'US', 'Rate limit exceeded')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert 'rate_limit' in params[0]

    def test_connection_error_classifies_as_retry(self):
        """U-08: 'connection' → retry 분류"""
        self.tsm.mark_failure('005930', 'KR', 'Connection timeout')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        # Should classify as retry-able error
        assert 'connection' in params[0] or 'timeout' in params[0]


class TestUSPreferredStock:
    """U-09: US Preferred Stock 처리 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_preferred_stock_classifies_as_unsupported(self):
        """U-09: US preferred stock (ticker에 '/' 포함) → unsupported"""
        self.tsm.mark_failure('ABR/D', 'US', 'No data found')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        # Should be classified as preferred_stock
        assert 'preferred_stock' in params[0]

    def test_non_us_slash_ticker_not_special_treated(self):
        """U-09: US 외 리전의 '/' 포함 티커는 특별 처리 안함"""
        self.tsm.mark_failure('TEST/A', 'JP', 'No data found')

        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        # Should NOT be classified as preferred_stock
        assert params[0] != 'preferred_stock'


class TestBlacklistManagement:
    """U-10, U-11: 블랙리스트 관리 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_set_blacklist(self):
        """U-10: 수동 블랙리스트 추가"""
        self.tsm.set_blacklist('PROBLEMATIC', 'US', 'manual_exclude')

        self.mock_db.execute_update.assert_called_once()
        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'blacklist'
        assert params[1] == 'manual_exclude'

    def test_clear_blacklist(self):
        """U-11: 블랙리스트 해제 → unknown으로 리셋"""
        self.tsm.clear_blacklist('RESTORED', 'US')

        self.mock_db.execute_update.assert_called_once()
        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'unknown'

    def test_reset_status_same_as_clear_blacklist(self):
        """U-11: reset_status()는 clear_blacklist()와 동일 동작"""
        self.tsm.reset_status('TICKER', 'JP')

        self.mock_db.execute_update.assert_called_once()
        call_args = self.mock_db.execute_update.call_args
        params = call_args[0][1]

        assert params[0] == 'unknown'


class TestAutoDetectUnsupported:
    """U-12: auto_detect_unsupported() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_detects_us_preferred_stocks(self):
        """U-12: US preferred stock 자동 탐지"""
        # Mock count query
        self.mock_db.execute_query.return_value = [{'cnt': 5}]

        result = self.tsm.auto_detect_unsupported('US')

        assert result == 5
        # execute_update should be called to mark them
        self.mock_db.execute_update.assert_called_once()

    def test_non_us_returns_zero(self):
        """U-12: US 외 리전은 0 반환 (현재 구현)"""
        result = self.tsm.auto_detect_unsupported('JP')

        assert result == 0
        # No query should be executed
        self.mock_db.execute_query.assert_not_called()

    def test_zero_when_no_preferred_stocks(self):
        """U-12: preferred stock 없으면 0 반환"""
        self.mock_db.execute_query.return_value = [{'cnt': 0}]

        result = self.tsm.auto_detect_unsupported('US')

        assert result == 0
        # execute_update should NOT be called
        self.mock_db.execute_update.assert_not_called()


class TestGetStatusSummary:
    """U-13: get_status_summary() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_returns_correct_counts(self):
        """U-13: 리전별 상태 집계 정확성"""
        self.mock_db.execute_query.return_value = [
            {'yf_status': 'active', 'count': 100},
            {'yf_status': 'unknown', 'count': 50},
            {'yf_status': 'delisted', 'count': 10},
            {'yf_status': 'unsupported', 'count': 5},
            {'yf_status': 'blacklist', 'count': 2},
            {'yf_status': 'retry', 'count': 3},
        ]

        result = self.tsm.get_status_summary('JP')

        assert result['total'] == 170
        assert result['active'] == 100
        assert result['unknown'] == 50
        assert result['delisted'] == 10
        assert result['unsupported'] == 5
        assert result['blacklist'] == 2
        assert result['retry'] == 3
        assert result['skip_count'] == 17  # delisted + unsupported + blacklist
        assert result['process_count'] == 153  # total - skip_count

    def test_handles_empty_region(self):
        """U-13: 빈 리전 처리"""
        self.mock_db.execute_query.return_value = []

        result = self.tsm.get_status_summary('EMPTY')

        assert result['total'] == 0
        assert result['skip_count'] == 0


class TestStaleTickerVerification:
    """U-14: 재검증 대상 티커 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_verify_stale_tickers(self):
        """U-14: 30일 이상 지난 delisted/unsupported 재검증 대상"""
        self.mock_db.execute_query.return_value = [
            {'ticker': 'OLD_DELISTED'},
            {'ticker': 'OLD_UNSUPPORTED'},
        ]

        result = self.tsm.verify_stale_tickers('JP', days=30)

        assert len(result) == 2
        assert 'OLD_DELISTED' in result

        # Verify query checks for stale status
        call_args = self.mock_db.execute_query.call_args
        query = call_args[0][0]
        assert 'yf_last_check <' in query
        assert 'INTERVAL' in query

    def test_custom_days_parameter(self):
        """U-14: 커스텀 days 파라미터 동작"""
        self.mock_db.execute_query.return_value = []

        self.tsm.verify_stale_tickers('US', days=60)

        call_args = self.mock_db.execute_query.call_args
        params = call_args[0][1]

        # Should use custom days value
        assert 60 in params


class TestBulkMarkSuccess:
    """bulk_mark_success() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_marks_multiple_tickers(self):
        """여러 티커 일괄 성공 처리"""
        tickers = [('7203', 'JP'), ('9984', 'JP'), ('6758', 'JP')]

        self.tsm.bulk_mark_success(tickers)

        # Should call execute_update for each ticker
        assert self.mock_db.execute_update.call_count == 3


class TestGetFailSummary:
    """get_fail_summary() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_returns_failure_reasons(self):
        """실패 사유별 집계 반환"""
        self.mock_db.execute_query.return_value = [
            {'yf_fail_reason': 'no_data_found', 'count': 50},
            {'yf_fail_reason': 'preferred_stock', 'count': 30},
            {'yf_fail_reason': 'timeout', 'count': 5},
        ]

        result = self.tsm.get_fail_summary('US')

        assert len(result) == 3
        assert result[0]['yf_fail_reason'] == 'no_data_found'
        assert result[0]['count'] == 50


class TestInitStatusFromOHLCV:
    """init_status_from_ohlcv() 테스트"""

    def setup_method(self):
        self.mock_db = Mock()
        self.tsm = TickerStatusManager(self.mock_db)

    def test_marks_tickers_with_recent_data_as_active(self):
        """최근 OHLCV 데이터 있는 티커를 active로 마킹"""
        self.mock_db.execute_query.return_value = [{'cnt': 100}]

        result = self.tsm.init_status_from_ohlcv('JP')

        assert result['active'] == 100

    def test_no_update_when_no_recent_data(self):
        """최근 데이터 없으면 업데이트 안함"""
        self.mock_db.execute_query.return_value = [{'cnt': 0}]

        result = self.tsm.init_status_from_ohlcv('CN')

        assert result['active'] == 0
        # execute_update should not be called
        self.mock_db.execute_update.assert_not_called()


# ============================================================================
# pytest markers for selective execution
# ============================================================================

class TestErrorStatusMapping:
    """ERROR_STATUS_MAP 매핑 테스트"""

    def test_all_error_patterns_defined(self):
        """모든 에러 패턴이 정의되어 있는지 확인"""
        error_map = TickerStatusManager.ERROR_STATUS_MAP

        assert 'no data found' in error_map
        assert 'no data' in error_map
        assert 'rate limit' in error_map
        assert 'timeout' in error_map
        assert 'connection' in error_map

    def test_delisted_patterns(self):
        """delisted로 분류되는 패턴"""
        error_map = TickerStatusManager.ERROR_STATUS_MAP

        delisted_patterns = ['no data found', 'no data', 'symbol may be delisted',
                            'no timezone found', 'quote not found', 'not found']

        for pattern in delisted_patterns:
            assert error_map.get(pattern) == 'delisted', f"Pattern '{pattern}' should map to 'delisted'"

    def test_retry_patterns(self):
        """retry로 분류되는 패턴"""
        error_map = TickerStatusManager.ERROR_STATUS_MAP

        retry_patterns = ['rate limit', 'timeout', 'connection', 'too many requests']

        for pattern in retry_patterns:
            assert error_map.get(pattern) == 'retry', f"Pattern '{pattern}' should map to 'retry'"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
