"""
BackfillExecutor 기본 클래스 단위 테스트

추상 클래스의 공통 기능 테스트:
- execute_batch() 워크플로우
- Rate limiting
- Checkpointing (저장/로드)
- 재시도 로직
- Progress tracking
- DRY RUN 모드

작성자: Quant Platform Development Team
날짜: 2025-11-11
"""

import pytest
import time
import json
import tempfile
from pathlib import Path
from typing import List, Tuple
from unittest.mock import Mock, MagicMock, patch
from datetime import date

from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.data_structures import (
    TickerGapInfo,
    GapPriority,
    BackfillStats
)
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# 테스트용 구체 클래스
# ============================================================================

class MockBackfillExecutor(BackfillExecutor):
    """테스트용 BackfillExecutor 구현체"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_tickers = []
        self.should_fail = False
        self.fail_on_ticker = None

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """Mock ticker 실행"""
        self.executed_tickers.append(ticker_info.ticker)

        # 특정 ticker에서 실패
        if self.fail_on_ticker and ticker_info.ticker == self.fail_on_ticker:
            raise Exception(f"Mock failure on {ticker_info.ticker}")

        # 전체 실패 모드
        if self.should_fail:
            return False

        return True

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """Mock 사전 조건 검증"""
        return (True, [])


class FailingPrerequisitesExecutor(BackfillExecutor):
    """사전 조건 검증 실패 테스트용 executor"""

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        return True

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        return (False, ["Mock API not authenticated", "Database connection failed"])


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock PostgresDatabaseManager"""
    return Mock(spec=PostgresDatabaseManager)


@pytest.fixture
def executor(mock_db):
    """MockBackfillExecutor 인스턴스"""
    return MockBackfillExecutor(mock_db, dry_run=False, rate_limit_delay=0.01)


@pytest.fixture
def sample_tickers():
    """샘플 ticker 목록"""
    return [
        TickerGapInfo(
            ticker='005930',
            name='Samsung Electronics',
            region='KR',
            listing_date=date(1975, 6, 11),
            missing_count=10,
            total_count=10,
            priority=GapPriority.FULLY_MISSING,
            target_columns=['capital_stock']
        ),
        TickerGapInfo(
            ticker='000660',
            name='SK Hynix',
            region='KR',
            listing_date=date(1996, 12, 26),
            missing_count=5,
            total_count=10,
            priority=GapPriority.PARTIALLY_MISSING,
            target_columns=['capital_stock']
        ),
        TickerGapInfo(
            ticker='005380',
            name='Hyundai Motor',
            region='KR',
            listing_date=date(1974, 1, 26),
            missing_count=10,
            total_count=10,
            priority=GapPriority.FULLY_MISSING,
            target_columns=['capital_stock']
        )
    ]


# ============================================================================
# 초기화 테스트
# ============================================================================

class TestBackfillExecutorInitialization:
    """BackfillExecutor 초기화 테스트"""

    def test_initialization_default_params(self, mock_db):
        """기본 파라미터로 초기화"""
        executor = MockBackfillExecutor(mock_db)

        assert executor.db == mock_db
        assert executor.dry_run == False
        assert executor.rate_limit_delay == 1.0
        assert executor.max_retries == 3
        assert executor.retry_delay == 5.0
        assert isinstance(executor.stats, BackfillStats)

    def test_initialization_custom_params(self, mock_db):
        """커스텀 파라미터로 초기화"""
        executor = MockBackfillExecutor(
            mock_db,
            dry_run=True,
            rate_limit_delay=2.0,
            max_retries=5,
            retry_delay=10.0
        )

        assert executor.dry_run == True
        assert executor.rate_limit_delay == 2.0
        assert executor.max_retries == 5
        assert executor.retry_delay == 10.0


# ============================================================================
# execute_batch() 워크플로우 테스트
# ============================================================================

class TestExecuteBatch:
    """execute_batch() 워크플로우 테스트"""

    def test_execute_batch_success(self, executor, sample_tickers):
        """성공적인 배치 실행"""
        stats = executor.execute_batch(
            sample_tickers,
            checkpoint_interval=10
        )

        # 모든 ticker 처리 확인
        assert stats.tickers_processed == 3
        assert stats.tickers_success == 3
        assert stats.tickers_failed == 0
        assert stats.api_calls == 3

        # 실행된 ticker 확인
        assert len(executor.executed_tickers) == 3
        assert '005930' in executor.executed_tickers
        assert '000660' in executor.executed_tickers
        assert '005380' in executor.executed_tickers

    def test_execute_batch_with_failures(self, executor, sample_tickers):
        """일부 ticker 실패 시 배치 실행"""
        # 특정 ticker에서 실패 설정
        executor.fail_on_ticker = '000660'

        stats = executor.execute_batch(
            sample_tickers,
            checkpoint_interval=10
        )

        # 통계 확인
        assert stats.tickers_processed == 3
        assert stats.tickers_success == 2  # 2개 성공 (005930, 005380)
        assert stats.tickers_failed == 1  # 1개 실패 (000660)
        assert len(stats.errors) >= 1

    def test_execute_batch_dry_run(self, mock_db, sample_tickers):
        """DRY RUN 모드 테스트"""
        executor = MockBackfillExecutor(mock_db, dry_run=True)

        stats = executor.execute_batch(
            sample_tickers,
            checkpoint_interval=10
        )

        # DRY RUN에서는 실행되지 않음
        assert stats.tickers_processed == 3
        assert stats.tickers_success == 0
        assert stats.tickers_failed == 0
        assert len(executor.executed_tickers) == 0  # 실제 실행 안 됨

    def test_execute_batch_empty_list(self, executor):
        """빈 ticker 목록으로 실행"""
        stats = executor.execute_batch([])

        assert stats.tickers_processed == 0
        assert stats.tickers_success == 0
        assert stats.tickers_failed == 0


# ============================================================================
# 사전 조건 검증 테스트
# ============================================================================

class TestPrerequisitesValidation:
    """사전 조건 검증 테스트"""

    def test_prerequisites_failure(self, mock_db, sample_tickers):
        """사전 조건 검증 실패 시 중단"""
        executor = FailingPrerequisitesExecutor(mock_db)

        stats = executor.execute_batch(sample_tickers)

        # 실행되지 않아야 함
        assert stats.tickers_processed == 0
        assert len(stats.errors) > 0
        assert "Prerequisites failed" in stats.errors[0]


# ============================================================================
# Rate Limiting 테스트
# ============================================================================

class TestRateLimiting:
    """Rate limiting 테스트"""

    def test_rate_limiting_applied(self, mock_db, sample_tickers):
        """Rate limiting이 적용되는지 확인"""
        executor = MockBackfillExecutor(mock_db, rate_limit_delay=0.1)

        start_time = time.time()
        executor.execute_batch(sample_tickers, checkpoint_interval=10)
        elapsed = time.time() - start_time

        # 최소 실행 시간 = (ticker 수 - 1) * rate_limit_delay
        # (첫 ticker는 지연 없음)
        min_expected_time = (len(sample_tickers) - 1) * 0.1
        assert elapsed >= min_expected_time

    def test_no_rate_limiting_when_disabled(self, mock_db, sample_tickers):
        """Rate limiting 비활성화 시 빠른 실행"""
        executor = MockBackfillExecutor(mock_db, rate_limit_delay=0.0)

        start_time = time.time()
        executor.execute_batch(sample_tickers, checkpoint_interval=10)
        elapsed = time.time() - start_time

        # Rate limiting 없이 빠르게 실행
        assert elapsed < 0.5  # 매우 빠르게 완료


# ============================================================================
# Checkpointing 테스트
# ============================================================================

class TestCheckpointing:
    """Checkpointing 테스트"""

    def test_checkpoint_save(self, executor, sample_tickers):
        """체크포인트 저장 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_file = f"{tmpdir}/test_checkpoint.json"

            # checkpoint_interval=2로 설정 (2개마다 저장)
            executor.execute_batch(
                sample_tickers,
                checkpoint_interval=2,
                checkpoint_file=checkpoint_file
            )

            # 체크포인트 파일 생성 확인
            assert Path(checkpoint_file).exists()

            # 체크포인트 내용 확인
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)

            assert 'last_processed_index' in checkpoint_data
            assert 'timestamp' in checkpoint_data
            assert 'stats' in checkpoint_data

    def test_checkpoint_load_and_resume(self, mock_db, sample_tickers):
        """체크포인트 로드 및 재개 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_file = f"{tmpdir}/resume_checkpoint.json"

            # 첫 번째 실행: 2개 처리 후 중단 시뮬레이션
            executor1 = MockBackfillExecutor(mock_db, rate_limit_delay=0.0)
            executor1.execute_batch(
                sample_tickers[:2],  # 처음 2개만
                checkpoint_interval=1,
                checkpoint_file=checkpoint_file
            )

            # 체크포인트 파일 확인
            assert Path(checkpoint_file).exists()
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            assert 'last_processed_index' in checkpoint_data

            # 두 번째 실행: 체크포인트에서 재개
            executor2 = MockBackfillExecutor(mock_db, rate_limit_delay=0.0)
            stats = executor2.execute_batch(
                sample_tickers,
                checkpoint_interval=1,
                checkpoint_file=checkpoint_file,
                resume=True
            )

            # 재개 후 검증
            # checkpoint에서 stats를 복원하므로, tickers_processed는 누적됨
            # 첫 번째 실행: 2개 처리 (tickers_processed=2)
            # 두 번째 실행: checkpoint 로드 (tickers_processed=2) + 1개 더 처리 (tickers_processed=3)
            assert stats.tickers_skipped == 2  # 재개 시 2개 건너뜀
            assert stats.tickers_processed == 3  # 전체 3개 처리됨 (누적)
            assert stats.tickers_success == 3  # 모두 성공


# ============================================================================
# 재시도 로직 테스트
# ============================================================================

class TestRetryLogic:
    """재시도 로직 테스트"""

    def test_retry_on_exception(self, mock_db, sample_tickers):
        """예외 발생 시 재시도"""
        executor = MockBackfillExecutor(
            mock_db,
            rate_limit_delay=0.0,
            max_retries=3,
            retry_delay=0.01
        )
        executor.fail_on_ticker = '000660'

        stats = executor.execute_batch([sample_tickers[1]], checkpoint_interval=10)  # '000660'만

        # 실패 확인 (재시도 후에도 실패)
        assert stats.tickers_failed == 1
        assert len(stats.errors) > 0
        assert '000660' in stats.errors[0]

    def test_success_after_retry(self, mock_db, sample_tickers):
        """재시도 후 성공 시나리오"""
        executor = MockBackfillExecutor(mock_db, max_retries=3, retry_delay=0.01)

        # execute_ticker를 mock하여 첫 2번은 실패, 3번째는 성공
        call_count = {'count': 0}

        original_execute = executor.execute_ticker

        def execute_with_failure(ticker_info):
            call_count['count'] += 1
            if call_count['count'] < 3:
                raise Exception("Temporary failure")
            return original_execute(ticker_info)

        executor.execute_ticker = execute_with_failure

        stats = executor.execute_batch([sample_tickers[0]], checkpoint_interval=10)

        # 재시도 후 성공
        assert stats.tickers_success == 1
        assert stats.tickers_failed == 0


# ============================================================================
# 통계 및 기타 테스트
# ============================================================================

class TestStatistics:
    """통계 테스트"""

    def test_get_stats(self, executor, sample_tickers):
        """get_stats() 메서드 테스트"""
        executor.execute_batch(sample_tickers, checkpoint_interval=10)
        stats = executor.get_stats()

        assert isinstance(stats, BackfillStats)
        assert stats.tickers_processed == 3
        assert stats.execution_time_sec > 0

    def test_reset_stats(self, executor, sample_tickers):
        """reset_stats() 메서드 테스트"""
        executor.execute_batch(sample_tickers, checkpoint_interval=10)

        # 통계 초기화
        executor.reset_stats()
        stats = executor.get_stats()

        assert stats.tickers_processed == 0
        assert stats.tickers_success == 0
        assert stats.tickers_failed == 0


# ============================================================================
# 진행 상태 추적 테스트
# ============================================================================

class TestProgressTracking:
    """진행 상태 추적 테스트"""

    def test_progress_tracking_logs(self, executor, sample_tickers, caplog):
        """진행 상태 로깅 확인"""
        import logging
        caplog.set_level(logging.INFO)

        executor.execute_batch(sample_tickers, checkpoint_interval=10)

        # 로그에 진행 상태가 기록되었는지 확인
        log_text = caplog.text
        assert "배치 백필 시작" in log_text
        assert "배치 백필 완료" in log_text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
