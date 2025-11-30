#!/usr/bin/env python3
"""
Collection Tracker Integration Tests

CollectionTracker의 실제 DB 연동 테스트:
- 테이블 존재 여부 확인
- 중복 방지 기능 검증
- DividendCollector와의 통합 테스트
- Orchestrator와의 통합 테스트

Author: Quant Investment Platform
Date: 2025-11-27
"""

import os
import sys
from datetime import date
from typing import Dict, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger


class CollectionTrackerIntegrationTests:
    """CollectionTracker 통합 테스트."""

    def __init__(self):
        self.results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "tests": []
        }
        self.db = None

    def setup(self):
        """테스트 환경 설정."""
        try:
            from modules.db_manager_postgres import PostgresDatabaseManager
            self.db = PostgresDatabaseManager()
            return True
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            return False

    def cleanup_test_data(self, pattern: str):
        """테스트 데이터 정리용 헬퍼 메서드."""
        try:
            # 직접 cursor를 사용하여 DELETE 실행
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM collection_tracker WHERE ticker LIKE %s",
                    (pattern,)
                )
                conn.commit()
                cursor.close()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")

    def record_result(self, test_name: str, passed: bool, message: str = "", skipped: bool = False):
        """테스트 결과 기록."""
        if skipped:
            self.results["skipped"] += 1
            status = "SKIPPED"
        elif passed:
            self.results["passed"] += 1
            status = "PASSED"
        else:
            self.results["failed"] += 1
            status = "FAILED"

        self.results["tests"].append({
            "name": test_name,
            "status": status,
            "message": message
        })
        logger.info(f"[{status}] {test_name}: {message}")

    # =========================================================================
    # Phase 1: 테이블 및 기본 기능 테스트
    # =========================================================================

    def test_collection_tracker_table_exists(self):
        """collection_tracker 테이블 존재 확인."""
        test_name = "collection_tracker_table_exists"
        try:
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'collection_tracker'
            ) as exists
            """
            result = self.db.execute_query(query)

            if result and result[0].get('exists'):
                self.record_result(test_name, True, "collection_tracker table exists")
            else:
                self.record_result(test_name, False, "collection_tracker table not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_collection_tracker_indexes(self):
        """collection_tracker 인덱스 존재 확인."""
        test_name = "collection_tracker_indexes"
        try:
            query = """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'collection_tracker'
            ORDER BY indexname
            """
            result = self.db.execute_query(query)

            if result and len(result) >= 2:  # 최소 2개 인덱스 (PK + lookup)
                index_names = [r['indexname'] for r in result]
                self.record_result(
                    test_name, True,
                    f"Found {len(result)} indexes: {', '.join(index_names)}"
                )
            else:
                self.record_result(test_name, False, f"Expected at least 2 indexes, found {len(result) if result else 0}")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_collection_tracker_view_exists(self):
        """v_collection_stats 뷰 존재 확인."""
        test_name = "v_collection_stats_view_exists"
        try:
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.views
                WHERE table_name = 'v_collection_stats'
            ) as exists
            """
            result = self.db.execute_query(query)

            if result and result[0].get('exists'):
                self.record_result(test_name, True, "v_collection_stats view exists")
            else:
                self.record_result(test_name, False, "v_collection_stats view not found")

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 2: CollectionTracker 클래스 기능 테스트
    # =========================================================================

    def test_tracker_mark_and_skip(self):
        """mark_collected 및 should_skip 통합 테스트."""
        test_name = "tracker_mark_and_skip"
        try:
            from modules.collection.collection_tracker import CollectionTracker, DataType

            tracker = CollectionTracker(self.db)

            # 테스트용 ticker (TEST_ prefix로 구분)
            test_ticker = "TEST_TRACKER_001"
            test_region = "KR"
            test_data_type = DataType.DIVIDEND

            # 1. 수집 전: should_skip = False
            should_skip_before = tracker.should_skip(test_ticker, test_region, test_data_type)

            # 2. 수집 완료 기록
            mark_result = tracker.mark_collected(
                test_ticker, test_region, test_data_type,
                status='success',
                records_count=5,
                duration_ms=1500
            )

            # 3. 수집 후: should_skip = True
            should_skip_after = tracker.should_skip(test_ticker, test_region, test_data_type)

            # 4. 정리: 테스트 데이터 삭제
            cleanup_query = """
            DELETE FROM collection_tracker
            WHERE ticker = %s AND region = %s
            """
            self.db.execute_update(cleanup_query, (test_ticker, test_region))

            if not should_skip_before and mark_result and should_skip_after:
                self.record_result(
                    test_name, True,
                    f"Mark/Skip cycle works: skip_before={should_skip_before}, mark={mark_result}, skip_after={should_skip_after}"
                )
            else:
                self.record_result(
                    test_name, False,
                    f"Expected (False, True, True), got ({should_skip_before}, {mark_result}, {should_skip_after})"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_tracker_batch_skip(self):
        """should_skip_batch 통합 테스트."""
        test_name = "tracker_batch_skip"
        try:
            from modules.collection.collection_tracker import CollectionTracker, DataType

            tracker = CollectionTracker(self.db)

            # 테스트용 tickers
            test_tickers = ["TEST_BATCH_001", "TEST_BATCH_002", "TEST_BATCH_003"]
            test_region = "US"
            test_data_type = DataType.RATIOS

            # 1. 일부만 수집 완료 기록
            tracker.mark_collected(test_tickers[0], test_region, test_data_type, status='success')

            # 캐시 클리어 (DB에서 다시 조회하도록)
            tracker.clear_cache()

            # 2. 배치 스킵 확인
            to_process, to_skip = tracker.should_skip_batch(
                test_tickers, test_region, test_data_type
            )

            # 3. 정리
            self.cleanup_test_data('TEST_BATCH_%')

            # 검증: TEST_BATCH_001은 skip, 나머지는 process
            expected_process = ["TEST_BATCH_002", "TEST_BATCH_003"]
            expected_skip = ["TEST_BATCH_001"]

            if set(to_process) == set(expected_process) and set(to_skip) == set(expected_skip):
                self.record_result(
                    test_name, True,
                    f"Batch skip works: to_process={to_process}, to_skip={to_skip}"
                )
            else:
                self.record_result(
                    test_name, False,
                    f"Expected process={expected_process}, skip={expected_skip}; "
                    f"Got process={to_process}, skip={to_skip}"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_tracker_force_mode(self):
        """force 모드 테스트 (skip_same_day=False)."""
        test_name = "tracker_force_mode"
        try:
            from modules.collection.collection_tracker import CollectionTracker, DataType

            # Force mode tracker (skip_same_day=False)
            force_tracker = CollectionTracker(self.db, skip_same_day=False)

            test_ticker = "TEST_FORCE_001"
            test_region = "JP"
            test_data_type = DataType.FUNDAMENTALS

            # 1. 수집 완료 기록 (DB에 저장)
            force_tracker.mark_collected(
                test_ticker, test_region, test_data_type,
                status='success'
            )

            # 2. Force mode에서는 항상 should_skip = False
            should_skip = force_tracker.should_skip(test_ticker, test_region, test_data_type)

            # 3. 정리
            cleanup_query = """
            DELETE FROM collection_tracker
            WHERE ticker = %s AND region = %s
            """
            self.db.execute_update(cleanup_query, (test_ticker, test_region))

            if not should_skip:
                self.record_result(
                    test_name, True,
                    "Force mode (skip_same_day=False) always returns False"
                )
            else:
                self.record_result(
                    test_name, False,
                    f"Expected should_skip=False in force mode, got {should_skip}"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 3: DividendCollector 통합 테스트
    # =========================================================================

    def test_dividend_collector_with_tracker(self):
        """DividendCollector의 tracker 통합 테스트."""
        test_name = "dividend_collector_with_tracker"
        try:
            from modules.collection.dividend_collector import DividendCollector

            # Collector 초기화 (skip_same_day=True)
            collector = DividendCollector(self.db, skip_same_day=True)

            # Tracker가 제대로 초기화되었는지 확인
            if hasattr(collector, 'tracker') and collector.tracker is not None:
                self.record_result(
                    test_name, True,
                    f"DividendCollector has tracker: skip_same_day={collector.tracker.skip_same_day}"
                )
            else:
                self.record_result(
                    test_name, False,
                    "DividendCollector does not have tracker attribute"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_dividend_collector_batch_skip(self):
        """DividendCollector 배치 스킵 테스트."""
        test_name = "dividend_collector_batch_skip"
        try:
            from modules.collection.dividend_collector import DividendCollector
            from modules.collection.collection_tracker import DataType

            collector = DividendCollector(self.db, skip_same_day=True)

            # 테스트용 ticker 기록 (이미 수집된 것으로 표시)
            test_ticker = "TEST_DIV_001"
            collector.tracker.mark_collected(
                test_ticker, "KR", DataType.DIVIDEND,
                status='success',
                records_count=3
            )

            # 배치 스킵 확인 (collect_batch 내부에서 사용되는 로직)
            test_tickers = [test_ticker, "TEST_DIV_002"]
            to_process, to_skip = collector.tracker.should_skip_batch(
                test_tickers, "KR", DataType.DIVIDEND
            )

            # 정리
            self.cleanup_test_data('TEST_DIV_%')

            if test_ticker in to_skip and "TEST_DIV_002" in to_process:
                self.record_result(
                    test_name, True,
                    f"DividendCollector batch skip works: skip={to_skip}, process={to_process}"
                )
            else:
                self.record_result(
                    test_name, False,
                    f"Unexpected result: skip={to_skip}, process={to_process}"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # Phase 4: 통계 및 정리 테스트
    # =========================================================================

    def test_collection_stats(self):
        """수집 통계 조회 테스트."""
        test_name = "collection_stats"
        try:
            from modules.collection.collection_tracker import CollectionTracker, DataType

            tracker = CollectionTracker(self.db)

            # 테스트 데이터 추가
            for i in range(3):
                tracker.mark_collected(
                    f"TEST_STATS_{i:03d}", "KR", DataType.DIVIDEND,
                    status='success',
                    records_count=i + 1,
                    duration_ms=100 * (i + 1)
                )

            # 통계 조회
            stats = tracker.get_collection_stats(region="KR", data_type=DataType.DIVIDEND)

            # 정리
            self.cleanup_test_data('TEST_STATS_%')

            if stats and len(stats) > 0:
                self.record_result(
                    test_name, True,
                    f"Stats retrieved: {len(stats)} rows"
                )
            else:
                self.record_result(
                    test_name, False,
                    "No stats returned"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    def test_today_summary(self):
        """오늘 요약 조회 테스트."""
        test_name = "today_summary"
        try:
            from modules.collection.collection_tracker import CollectionTracker, DataType

            tracker = CollectionTracker(self.db)

            # 테스트 데이터 추가 (여러 데이터 유형)
            tracker.mark_collected("TEST_SUM_001", "KR", DataType.DIVIDEND, status='success', records_count=5)
            tracker.mark_collected("TEST_SUM_002", "KR", DataType.RATIOS, status='success', records_count=3)
            tracker.mark_collected("TEST_SUM_003", "US", DataType.DIVIDEND, status='failed')

            # 요약 조회
            summary = tracker.get_today_summary()

            # 정리
            self.cleanup_test_data('TEST_SUM_%')

            if 'total_tickers' in summary and 'by_data_type' in summary:
                self.record_result(
                    test_name, True,
                    f"Summary retrieved: total={summary['total_tickers']}, types={list(summary['by_data_type'].keys())}"
                )
            else:
                self.record_result(
                    test_name, False,
                    f"Invalid summary format: {summary}"
                )

        except Exception as e:
            self.record_result(test_name, False, f"Error: {e}")

    # =========================================================================
    # 실행
    # =========================================================================

    def run_all_tests(self):
        """모든 테스트 실행."""
        logger.info("=" * 60)
        logger.info("Collection Tracker Integration Tests")
        logger.info("=" * 60)

        if not self.setup():
            logger.error("Failed to setup test environment")
            return self.results

        # Phase 1: 테이블 및 기본 기능
        logger.info("\n--- Phase 1: Table & Basic Tests ---")
        self.test_collection_tracker_table_exists()
        self.test_collection_tracker_indexes()
        self.test_collection_tracker_view_exists()

        # Phase 2: CollectionTracker 클래스
        logger.info("\n--- Phase 2: CollectionTracker Class Tests ---")
        self.test_tracker_mark_and_skip()
        self.test_tracker_batch_skip()
        self.test_tracker_force_mode()

        # Phase 3: DividendCollector 통합
        logger.info("\n--- Phase 3: DividendCollector Integration ---")
        self.test_dividend_collector_with_tracker()
        self.test_dividend_collector_batch_skip()

        # Phase 4: 통계 및 정리
        logger.info("\n--- Phase 4: Stats & Summary ---")
        self.test_collection_stats()
        self.test_today_summary()

        # 결과 요약
        logger.info("\n" + "=" * 60)
        logger.info("Test Results Summary")
        logger.info("=" * 60)
        logger.info(f"  Passed:  {self.results['passed']}")
        logger.info(f"  Failed:  {self.results['failed']}")
        logger.info(f"  Skipped: {self.results['skipped']}")
        logger.info(f"  Total:   {len(self.results['tests'])}")

        return self.results


def main():
    """메인 실행 함수."""
    tests = CollectionTrackerIntegrationTests()
    results = tests.run_all_tests()

    # 종료 코드 결정
    if results["failed"] > 0:
        logger.error(f"\n❌ {results['failed']} test(s) failed!")
        sys.exit(1)
    else:
        logger.success(f"\n✅ All {results['passed']} test(s) passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
