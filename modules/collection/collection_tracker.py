"""
Collection Tracker - 중복 데이터 수집 방지 시스템

동일 날짜에 동일 데이터 재수집을 방지하여 API 호출과 계산 시간을 절감합니다.

사용 예:
    from modules.collection.collection_tracker import CollectionTracker, DataType

    tracker = CollectionTracker(db)

    # 배치 스킵 확인
    to_process, to_skip = tracker.should_skip_batch(
        tickers=['005930', '000660'],
        region='KR',
        data_type=DataType.DIVIDEND
    )

    # 수집 완료 기록
    tracker.mark_collected('005930', 'KR', DataType.DIVIDEND, records_count=5)

Author: Quant Investment Platform
Date: 2025-11-27
"""

import logging
import time
from datetime import date, datetime
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DataType(Enum):
    """수집 데이터 유형"""
    DIVIDEND = 'dividend'           # 배당 히스토리
    RATIOS = 'ratios'              # 재무 비율
    CASH_BACKFILL = 'cash_backfill'  # 현금 데이터 백필
    TECHNICAL = 'technical'         # 기술적 지표
    FUNDAMENTALS = 'fundamentals'   # 펀더멘털 데이터
    ETF_DETAILS = 'etf_details'     # ETF 상세 정보
    ETF_HOLDINGS = 'etf_holdings'   # ETF 구성종목


@dataclass
class CollectionStatus:
    """수집 상태 정보"""
    ticker: str
    region: str
    data_type: str
    last_collected: date
    status: str
    records_count: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None


class CollectionTracker:
    """
    수집 작업 추적기 - 중복 API 호출/계산 방지

    기능:
    - 동일 날짜 수집 여부 확인 (should_skip)
    - 배치 단위 스킵 확인 (should_skip_batch)
    - 수집 완료 기록 (mark_collected)
    - 수집 통계 조회 (get_collection_stats)
    - 오래된 기록 정리 (cleanup_old_records)
    """

    def __init__(self, db, skip_same_day: bool = True):
        """
        초기화

        Args:
            db: PostgresDatabaseManager 인스턴스
            skip_same_day: True면 같은 날 수집된 데이터 스킵
        """
        self.db = db
        self.skip_same_day = skip_same_day
        self._cache: Dict[str, CollectionStatus] = {}
        self._batch_cache: Dict[str, set] = {}  # 배치 캐시

    def should_skip(
        self,
        ticker: str,
        region: str,
        data_type: DataType,
        check_date: date = None
    ) -> bool:
        """
        오늘(또는 지정일) 이미 수집된 경우 True 반환

        Args:
            ticker: 종목 코드
            region: 지역 (KR, US, JP 등)
            data_type: 데이터 유형
            check_date: 확인할 날짜 (기본: 오늘)

        Returns:
            True면 스킵 필요, False면 수집 필요
        """
        if not self.skip_same_day:
            return False

        check_date = check_date or date.today()
        cache_key = f"{ticker}:{region}:{data_type.value}:{check_date}"

        # 메모리 캐시 확인
        if cache_key in self._cache:
            return self._cache[cache_key].status == 'success'

        # DB 확인
        query = """
        SELECT status FROM collection_tracker
        WHERE ticker = %s AND region = %s
          AND data_type = %s AND last_collected = %s
        LIMIT 1
        """
        try:
            result = self.db.execute_query(
                query, (ticker, region, data_type.value, check_date)
            )

            if result and result[0]['status'] == 'success':
                # 캐시에 저장
                self._cache[cache_key] = CollectionStatus(
                    ticker=ticker,
                    region=region,
                    data_type=data_type.value,
                    last_collected=check_date,
                    status='success'
                )
                return True

        except Exception as e:
            logger.warning(f"CollectionTracker.should_skip 오류: {e}")

        return False

    def should_skip_batch(
        self,
        tickers: List[str],
        region: str,
        data_type: DataType,
        check_date: date = None
    ) -> Tuple[List[str], List[str]]:
        """
        배치 스킵 확인 - 효율적인 대량 조회

        Args:
            tickers: 종목 코드 목록
            region: 지역
            data_type: 데이터 유형
            check_date: 확인할 날짜 (기본: 오늘)

        Returns:
            (to_process, to_skip): 처리할 ticker 목록, 스킵할 ticker 목록
        """
        if not self.skip_same_day or not tickers:
            return tickers, []

        check_date = check_date or date.today()

        # 배치 캐시 키
        batch_cache_key = f"{region}:{data_type.value}:{check_date}"

        # 배치 캐시에서 이미 수집된 ticker 확인
        if batch_cache_key not in self._batch_cache:
            # DB에서 한 번에 조회
            query = """
            SELECT ticker FROM collection_tracker
            WHERE region = %s AND data_type = %s
              AND last_collected = %s AND status = 'success'
            """
            try:
                result = self.db.execute_query(
                    query, (region, data_type.value, check_date)
                )
                self._batch_cache[batch_cache_key] = {
                    row['ticker'] for row in (result or [])
                }
            except Exception as e:
                logger.warning(f"CollectionTracker.should_skip_batch 오류: {e}")
                self._batch_cache[batch_cache_key] = set()

        already_collected = self._batch_cache[batch_cache_key]

        to_process = [t for t in tickers if t not in already_collected]
        to_skip = [t for t in tickers if t in already_collected]

        return to_process, to_skip

    def mark_collected(
        self,
        ticker: str,
        region: str,
        data_type: DataType,
        status: str = 'success',
        records_count: int = 0,
        duration_ms: int = 0,
        error_message: str = None
    ) -> bool:
        """
        수집 완료 기록

        Args:
            ticker: 종목 코드
            region: 지역
            data_type: 데이터 유형
            status: 상태 ('success', 'failed', 'skipped')
            records_count: 수집된 레코드 수
            duration_ms: 소요 시간 (밀리초)
            error_message: 오류 메시지 (실패 시)

        Returns:
            성공 여부
        """
        today = date.today()
        query = """
        INSERT INTO collection_tracker
            (ticker, region, data_type, last_collected, status,
             records_count, duration_ms, error_message, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (ticker, region, data_type, last_collected)
        DO UPDATE SET
            status = EXCLUDED.status,
            records_count = EXCLUDED.records_count,
            duration_ms = EXCLUDED.duration_ms,
            error_message = EXCLUDED.error_message,
            updated_at = NOW()
        """
        try:
            success = self.db.execute_update(query, (
                ticker, region, data_type.value, today,
                status, records_count, duration_ms, error_message
            ))

            # 캐시 업데이트
            if success and status == 'success':
                cache_key = f"{ticker}:{region}:{data_type.value}:{today}"
                self._cache[cache_key] = CollectionStatus(
                    ticker=ticker,
                    region=region,
                    data_type=data_type.value,
                    last_collected=today,
                    status=status,
                    records_count=records_count
                )

                # 배치 캐시 업데이트
                batch_cache_key = f"{region}:{data_type.value}:{today}"
                if batch_cache_key in self._batch_cache:
                    self._batch_cache[batch_cache_key].add(ticker)

            return success

        except Exception as e:
            logger.error(f"CollectionTracker.mark_collected 오류: {e}")
            return False

    def mark_batch_collected(
        self,
        tickers: List[str],
        region: str,
        data_type: DataType,
        status: str = 'success'
    ) -> int:
        """
        배치 수집 완료 기록

        Args:
            tickers: 종목 코드 목록
            region: 지역
            data_type: 데이터 유형
            status: 상태

        Returns:
            성공적으로 기록된 수
        """
        count = 0
        for ticker in tickers:
            if self.mark_collected(ticker, region, data_type, status):
                count += 1
        return count

    def get_collection_stats(
        self,
        region: str = None,
        data_type: DataType = None,
        check_date: date = None
    ) -> List[Dict[str, Any]]:
        """
        수집 통계 조회

        Args:
            region: 지역 필터 (선택)
            data_type: 데이터 유형 필터 (선택)
            check_date: 날짜 필터 (기본: 오늘)

        Returns:
            통계 목록: [{'region', 'data_type', 'status', 'count', ...}, ...]
        """
        check_date = check_date or date.today()

        query = """
        SELECT
            region, data_type, status,
            COUNT(*) as count,
            SUM(records_count) as total_records,
            AVG(duration_ms)::INTEGER as avg_duration_ms
        FROM collection_tracker
        WHERE last_collected = %s
        """
        params = [check_date]

        if region:
            query += " AND region = %s"
            params.append(region)
        if data_type:
            query += " AND data_type = %s"
            params.append(data_type.value)

        query += " GROUP BY region, data_type, status ORDER BY region, data_type"

        try:
            return self.db.execute_query(query, tuple(params)) or []
        except Exception as e:
            logger.error(f"CollectionTracker.get_collection_stats 오류: {e}")
            return []

    def get_today_summary(self, region: str = None) -> Dict[str, Any]:
        """
        오늘의 수집 요약

        Args:
            region: 지역 필터 (선택)

        Returns:
            요약 정보: {
                'total_tickers': 1234,
                'by_data_type': {'dividend': 500, 'ratios': 734},
                'by_status': {'success': 1200, 'failed': 34},
                'total_duration_minutes': 15.5
            }
        """
        stats = self.get_collection_stats(region=region)

        summary = {
            'total_tickers': 0,
            'by_data_type': {},
            'by_status': {},
            'total_duration_minutes': 0.0
        }

        total_duration_ms = 0

        for stat in stats:
            count = stat['count']
            data_type = stat['data_type']
            status = stat['status']
            avg_duration = stat.get('avg_duration_ms', 0) or 0

            summary['total_tickers'] += count

            if data_type not in summary['by_data_type']:
                summary['by_data_type'][data_type] = 0
            summary['by_data_type'][data_type] += count

            if status not in summary['by_status']:
                summary['by_status'][status] = 0
            summary['by_status'][status] += count

            total_duration_ms += avg_duration * count

        summary['total_duration_minutes'] = round(total_duration_ms / 60000, 2)

        return summary

    def cleanup_old_records(self, days_to_keep: int = 30) -> int:
        """
        오래된 추적 기록 정리

        Args:
            days_to_keep: 보관할 일수 (기본: 30일)

        Returns:
            삭제된 레코드 수
        """
        query = """
        DELETE FROM collection_tracker
        WHERE last_collected < CURRENT_DATE - INTERVAL '%s days'
        """
        try:
            # PostgreSQL에서 rowcount 가져오기
            result = self.db.execute_update(query, (days_to_keep,))
            logger.info(f"CollectionTracker: {days_to_keep}일 이전 기록 정리 완료")
            return 1 if result else 0
        except Exception as e:
            logger.error(f"CollectionTracker.cleanup_old_records 오류: {e}")
            return 0

    def clear_cache(self):
        """메모리 캐시 초기화"""
        self._cache.clear()
        self._batch_cache.clear()

    def invalidate_ticker(
        self,
        ticker: str,
        region: str,
        data_type: DataType = None
    ):
        """
        특정 ticker의 캐시 무효화 (강제 재수집 필요 시)

        Args:
            ticker: 종목 코드
            region: 지역
            data_type: 데이터 유형 (None이면 모든 유형)
        """
        today = date.today()

        # 메모리 캐시에서 제거
        keys_to_remove = []
        for key in self._cache:
            if key.startswith(f"{ticker}:{region}:"):
                if data_type is None or data_type.value in key:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

        # 배치 캐시에서 제거
        for batch_key, tickers_set in self._batch_cache.items():
            if region in batch_key:
                if data_type is None or data_type.value in batch_key:
                    tickers_set.discard(ticker)

        # DB에서도 제거 (선택적)
        if data_type:
            query = """
            DELETE FROM collection_tracker
            WHERE ticker = %s AND region = %s
              AND data_type = %s AND last_collected = %s
            """
            if not self.db.execute_update(query, (ticker, region, data_type.value, today)):
                logger.debug(f"invalidate_ticker: no DB row to delete for {ticker}/{region}/{data_type.value}")
        else:
            query = """
            DELETE FROM collection_tracker
            WHERE ticker = %s AND region = %s AND last_collected = %s
            """
            if not self.db.execute_update(query, (ticker, region, today)):
                logger.debug(f"invalidate_ticker: no DB row to delete for {ticker}/{region}")


# =============================================================================
# 유틸리티 함수
# =============================================================================

def create_tracker(db, skip_same_day: bool = True) -> CollectionTracker:
    """
    CollectionTracker 인스턴스 생성 헬퍼

    Args:
        db: PostgresDatabaseManager 인스턴스
        skip_same_day: 같은 날 스킵 여부

    Returns:
        CollectionTracker 인스턴스
    """
    return CollectionTracker(db, skip_same_day=skip_same_day)


def print_collection_summary(db, region: str = None):
    """
    오늘의 수집 요약 출력

    Args:
        db: PostgresDatabaseManager 인스턴스
        region: 지역 필터 (선택)
    """
    tracker = CollectionTracker(db)
    summary = tracker.get_today_summary(region=region)

    print(f"\n{'='*50}")
    print(f"  Collection Summary ({date.today()})")
    print(f"{'='*50}")
    print(f"  Total Tickers: {summary['total_tickers']:,}")
    print(f"\n  By Data Type:")
    for dt, count in summary['by_data_type'].items():
        print(f"    - {dt}: {count:,}")
    print(f"\n  By Status:")
    for status, count in summary['by_status'].items():
        print(f"    - {status}: {count:,}")
    print(f"\n  Total Duration: {summary['total_duration_minutes']:.1f} minutes")
    print(f"{'='*50}\n")
