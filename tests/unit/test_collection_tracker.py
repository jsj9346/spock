"""
Unit Tests for CollectionTracker

수집 작업 추적기의 핵심 기능을 테스트합니다:
- 스킵 여부 확인 (should_skip)
- 배치 스킵 확인 (should_skip_batch)
- 수집 완료 기록 (mark_collected)
- 통계 조회 (get_collection_stats)

Author: Quant Investment Platform
Date: 2025-11-27
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.collection.collection_tracker import (
    CollectionTracker,
    DataType,
    CollectionStatus,
    create_tracker
)


class TestDataType:
    """DataType Enum 테스트"""

    def test_data_type_values(self):
        """데이터 유형 값 확인"""
        assert DataType.DIVIDEND.value == 'dividend'
        assert DataType.RATIOS.value == 'ratios'
        assert DataType.CASH_BACKFILL.value == 'cash_backfill'
        assert DataType.TECHNICAL.value == 'technical'
        assert DataType.FUNDAMENTALS.value == 'fundamentals'


class TestCollectionStatus:
    """CollectionStatus 데이터클래스 테스트"""

    def test_collection_status_creation(self):
        """CollectionStatus 생성 테스트"""
        status = CollectionStatus(
            ticker='005930',
            region='KR',
            data_type='dividend',
            last_collected=date.today(),
            status='success',
            records_count=5
        )

        assert status.ticker == '005930'
        assert status.region == 'KR'
        assert status.data_type == 'dividend'
        assert status.status == 'success'
        assert status.records_count == 5


class TestCollectionTracker:
    """CollectionTracker 메인 클래스 테스트"""

    @pytest.fixture
    def mock_db(self):
        """Mock DB 인스턴스"""
        db = Mock()
        db.execute_query = Mock(return_value=None)
        db.execute_update = Mock(return_value=True)
        return db

    @pytest.fixture
    def tracker(self, mock_db):
        """기본 트래커 인스턴스"""
        return CollectionTracker(mock_db)

    @pytest.fixture
    def tracker_no_skip(self, mock_db):
        """스킵 비활성화 트래커"""
        return CollectionTracker(mock_db, skip_same_day=False)

    # =========================================================================
    # should_skip 테스트
    # =========================================================================

    def test_should_skip_disabled(self, tracker_no_skip):
        """스킵 비활성화 시 항상 False 반환"""
        result = tracker_no_skip.should_skip('005930', 'KR', DataType.DIVIDEND)
        assert result is False

    def test_should_skip_not_collected(self, tracker, mock_db):
        """수집되지 않은 경우 False 반환"""
        mock_db.execute_query.return_value = None

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result is False
        mock_db.execute_query.assert_called_once()

    def test_should_skip_already_collected(self, tracker, mock_db):
        """이미 수집된 경우 True 반환"""
        mock_db.execute_query.return_value = [{'status': 'success'}]

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result is True

    def test_should_skip_failed_status(self, tracker, mock_db):
        """실패 상태인 경우 False 반환 (재시도 필요)"""
        mock_db.execute_query.return_value = [{'status': 'failed'}]

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result is False

    def test_should_skip_uses_cache(self, tracker, mock_db):
        """두 번째 호출은 캐시 사용"""
        mock_db.execute_query.return_value = [{'status': 'success'}]

        # 첫 번째 호출
        result1 = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)
        # 두 번째 호출
        result2 = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result1 is True
        assert result2 is True
        # DB는 한 번만 호출되어야 함
        assert mock_db.execute_query.call_count == 1

    def test_should_skip_with_specific_date(self, tracker, mock_db):
        """특정 날짜로 확인"""
        mock_db.execute_query.return_value = [{'status': 'success'}]
        yesterday = date.today() - timedelta(days=1)

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND, check_date=yesterday)

        assert result is True
        # 쿼리에 어제 날짜가 사용되었는지 확인
        call_args = mock_db.execute_query.call_args[0]
        assert yesterday in call_args[1]

    # =========================================================================
    # should_skip_batch 테스트
    # =========================================================================

    def test_should_skip_batch_empty_list(self, tracker):
        """빈 리스트 처리"""
        to_process, to_skip = tracker.should_skip_batch([], 'KR', DataType.DIVIDEND)

        assert to_process == []
        assert to_skip == []

    def test_should_skip_batch_disabled(self, tracker_no_skip):
        """스킵 비활성화 시 모두 처리 대상"""
        tickers = ['005930', '000660', '035720']

        to_process, to_skip = tracker_no_skip.should_skip_batch(
            tickers, 'KR', DataType.DIVIDEND
        )

        assert to_process == tickers
        assert to_skip == []

    def test_should_skip_batch_none_collected(self, tracker, mock_db):
        """아무것도 수집되지 않은 경우"""
        mock_db.execute_query.return_value = []
        tickers = ['005930', '000660', '035720']

        to_process, to_skip = tracker.should_skip_batch(
            tickers, 'KR', DataType.DIVIDEND
        )

        assert to_process == tickers
        assert to_skip == []

    def test_should_skip_batch_some_collected(self, tracker, mock_db):
        """일부만 수집된 경우"""
        mock_db.execute_query.return_value = [
            {'ticker': '005930'},
            {'ticker': '035720'}
        ]
        tickers = ['005930', '000660', '035720']

        to_process, to_skip = tracker.should_skip_batch(
            tickers, 'KR', DataType.DIVIDEND
        )

        assert to_process == ['000660']
        assert set(to_skip) == {'005930', '035720'}

    def test_should_skip_batch_all_collected(self, tracker, mock_db):
        """모두 수집된 경우"""
        mock_db.execute_query.return_value = [
            {'ticker': '005930'},
            {'ticker': '000660'},
            {'ticker': '035720'}
        ]
        tickers = ['005930', '000660', '035720']

        to_process, to_skip = tracker.should_skip_batch(
            tickers, 'KR', DataType.DIVIDEND
        )

        assert to_process == []
        assert set(to_skip) == set(tickers)

    def test_should_skip_batch_uses_cache(self, tracker, mock_db):
        """배치 캐시 사용 확인"""
        mock_db.execute_query.return_value = [{'ticker': '005930'}]
        tickers = ['005930', '000660']

        # 첫 번째 호출
        tracker.should_skip_batch(tickers, 'KR', DataType.DIVIDEND)
        # 두 번째 호출
        tracker.should_skip_batch(tickers, 'KR', DataType.DIVIDEND)

        # DB는 한 번만 호출
        assert mock_db.execute_query.call_count == 1

    # =========================================================================
    # mark_collected 테스트
    # =========================================================================

    def test_mark_collected_success(self, tracker, mock_db):
        """수집 성공 기록"""
        result = tracker.mark_collected(
            '005930', 'KR', DataType.DIVIDEND,
            status='success',
            records_count=5,
            duration_ms=1500
        )

        assert result is True
        mock_db.execute_update.assert_called_once()

    def test_mark_collected_failed(self, tracker, mock_db):
        """수집 실패 기록"""
        result = tracker.mark_collected(
            '005930', 'KR', DataType.DIVIDEND,
            status='failed',
            error_message='API timeout'
        )

        assert result is True
        call_args = mock_db.execute_update.call_args[0]
        assert 'failed' in call_args[1]
        assert 'API timeout' in call_args[1]

    def test_mark_collected_updates_cache(self, tracker, mock_db):
        """mark_collected 후 캐시 업데이트 확인"""
        tracker.mark_collected('005930', 'KR', DataType.DIVIDEND, status='success')

        # 캐시에서 바로 확인 가능
        # DB 호출 없이 should_skip이 True 반환해야 함
        mock_db.execute_query.reset_mock()

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result is True
        mock_db.execute_query.assert_not_called()  # 캐시 사용

    def test_mark_collected_updates_batch_cache(self, tracker, mock_db):
        """mark_collected 후 배치 캐시 업데이트 확인"""
        # 먼저 배치 캐시 생성
        mock_db.execute_query.return_value = []
        tracker.should_skip_batch(['000660'], 'KR', DataType.DIVIDEND)

        # 새 ticker 수집 완료 기록
        tracker.mark_collected('005930', 'KR', DataType.DIVIDEND, status='success')

        # 배치 캐시에 추가되었는지 확인
        mock_db.execute_query.reset_mock()
        to_process, to_skip = tracker.should_skip_batch(
            ['005930', '000660'], 'KR', DataType.DIVIDEND
        )

        assert '005930' in to_skip  # 새로 추가된 것도 스킵 대상

    # =========================================================================
    # mark_batch_collected 테스트
    # =========================================================================

    def test_mark_batch_collected(self, tracker, mock_db):
        """배치 수집 완료 기록"""
        tickers = ['005930', '000660', '035720']

        count = tracker.mark_batch_collected(tickers, 'KR', DataType.DIVIDEND)

        assert count == 3
        assert mock_db.execute_update.call_count == 3

    # =========================================================================
    # get_collection_stats 테스트
    # =========================================================================

    def test_get_collection_stats(self, tracker, mock_db):
        """통계 조회"""
        mock_db.execute_query.return_value = [
            {'region': 'KR', 'data_type': 'dividend', 'status': 'success',
             'count': 100, 'total_records': 500, 'avg_duration_ms': 150}
        ]

        stats = tracker.get_collection_stats(region='KR')

        assert len(stats) == 1
        assert stats[0]['count'] == 100

    def test_get_collection_stats_with_filters(self, tracker, mock_db):
        """필터링된 통계 조회"""
        mock_db.execute_query.return_value = []

        tracker.get_collection_stats(
            region='KR',
            data_type=DataType.DIVIDEND,
            check_date=date.today()
        )

        # 쿼리에 필터 조건이 포함되었는지 확인
        call_args = mock_db.execute_query.call_args[0]
        assert 'KR' in call_args[1]
        assert 'dividend' in call_args[1]

    # =========================================================================
    # get_today_summary 테스트
    # =========================================================================

    def test_get_today_summary(self, tracker, mock_db):
        """오늘 요약 조회"""
        mock_db.execute_query.return_value = [
            {'region': 'KR', 'data_type': 'dividend', 'status': 'success',
             'count': 100, 'total_records': 500, 'avg_duration_ms': 150},
            {'region': 'KR', 'data_type': 'ratios', 'status': 'success',
             'count': 200, 'total_records': 200, 'avg_duration_ms': 50}
        ]

        summary = tracker.get_today_summary()

        assert summary['total_tickers'] == 300
        assert summary['by_data_type']['dividend'] == 100
        assert summary['by_data_type']['ratios'] == 200
        assert summary['by_status']['success'] == 300

    # =========================================================================
    # cleanup_old_records 테스트
    # =========================================================================

    def test_cleanup_old_records(self, tracker, mock_db):
        """오래된 기록 정리"""
        result = tracker.cleanup_old_records(days_to_keep=30)

        mock_db.execute_update.assert_called_once()

    # =========================================================================
    # clear_cache 테스트
    # =========================================================================

    def test_clear_cache(self, tracker, mock_db):
        """캐시 초기화"""
        # 캐시에 데이터 추가
        mock_db.execute_query.return_value = [{'status': 'success'}]
        tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        # 캐시 초기화
        tracker.clear_cache()

        # 다시 호출하면 DB 쿼리 발생
        mock_db.execute_query.reset_mock()
        tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        mock_db.execute_query.assert_called_once()

    # =========================================================================
    # invalidate_ticker 테스트
    # =========================================================================

    def test_invalidate_ticker(self, tracker, mock_db):
        """특정 ticker 무효화"""
        # 캐시에 데이터 추가
        mock_db.execute_query.return_value = [{'status': 'success'}]
        tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        # 무효화
        tracker.invalidate_ticker('005930', 'KR', DataType.DIVIDEND)

        # 캐시가 비워졌는지 확인
        mock_db.execute_query.reset_mock()
        mock_db.execute_query.return_value = None
        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        assert result is False  # 캐시가 비워져서 DB 재조회


class TestCreateTracker:
    """create_tracker 헬퍼 함수 테스트"""

    def test_create_tracker(self):
        """트래커 생성 헬퍼"""
        mock_db = Mock()
        tracker = create_tracker(mock_db)

        assert isinstance(tracker, CollectionTracker)
        assert tracker.skip_same_day is True

    def test_create_tracker_no_skip(self):
        """스킵 비활성화 트래커 생성"""
        mock_db = Mock()
        tracker = create_tracker(mock_db, skip_same_day=False)

        assert tracker.skip_same_day is False


# =============================================================================
# 실행
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
