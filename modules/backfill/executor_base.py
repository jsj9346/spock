"""
BackfillExecutor 기본 클래스

백필 실행을 위한 추상 기본 클래스로, 공통 유틸리티와 워크플로우를 제공합니다.

주요 기능:
- Rate limiting: API 호출 간 지연 제어
- Checkpointing: 진행 상태 저장 및 재개
- Progress tracking: 실시간 진행 상태 모니터링
- Error recovery: 자동 재시도 및 에러 처리

구현 예시:
    from modules.backfill.executor_base import BackfillExecutor

    class EquityBackfillExecutor(BackfillExecutor):
        def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
            # DART API에서 자본금 데이터 가져오기
            data = self.dart_api.get_equity_data(ticker_info.ticker)
            self.db.insert_equity_data(data)
            return True

        def validate_prerequisites(self) -> Tuple[bool, List[str]]:
            if not self.dart_api.is_authenticated():
                return (False, ["DART API 인증 필요"])
            return (True, [])

    # 사용
    executor = EquityBackfillExecutor(db, dry_run=False)
    stats = executor.execute_batch(gap_targets, checkpoint_interval=100)

작성자: Quant Platform Development Team
날짜: 2025-11-11
"""

import logging
import time
import json
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.data_structures import (
    TickerGapInfo,
    BackfillStats,
    GapPriority
)

logger = logging.getLogger(__name__)


class BackfillExecutor(ABC):
    """
    백필 실행을 위한 추상 기본 클래스

    모든 백필 실행기(EquityBackfillExecutor, ListingDateBackfillExecutor 등)는
    이 클래스를 상속하여 execute_ticker()와 validate_prerequisites()를
    구현해야 합니다.

    공통 기능:
    - execute_batch(): 배치 실행 워크플로우
    - rate_limit(): API 호출 속도 제한
    - save/load_checkpoint(): 진행 상태 저장/복구
    - track_progress(): 실시간 진행 상태 추적
    """

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """
        BackfillExecutor 초기화

        Args:
            db: PostgreSQL 데이터베이스 매니저
            dry_run: True이면 실제 실행 없이 미리보기만 수행
            rate_limit_delay: API 호출 간 지연 시간 (초)
            max_retries: 실패 시 최대 재시도 횟수
            retry_delay: 재시도 간 지연 시간 (초)
        """
        self.db = db
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 통계 추적
        self.stats = BackfillStats()

        # 진행 상태 추적
        self._last_rate_limit_time = 0.0
        self._start_time = None
        self._checkpoint_file = None

        logger.debug(f"BackfillExecutor 초기화: dry_run={dry_run}, rate_limit={rate_limit_delay}s")

    @abstractmethod
    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """
        단일 ticker에 대한 백필 실행 (추상 메서드)

        구현체는 다음을 수행해야 합니다:
        1. API에서 데이터 가져오기
        2. 데이터베이스에 저장
        3. 성공/실패 반환

        Args:
            ticker_info: 갭 메타데이터가 포함된 ticker 정보

        Returns:
            성공 시 True, 실패 시 False

        예시:
            def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
                try:
                    data = self.api.fetch_data(ticker_info.ticker)
                    self.db.insert_data(data)
                    return True
                except Exception as e:
                    logger.error(f"Failed to backfill {ticker_info.ticker}: {e}")
                    return False
        """
        pass

    @abstractmethod
    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        실행 전 사전 조건 검증 (추상 메서드)

        구현체는 다음을 확인해야 합니다:
        - API 인증 상태
        - 필수 데이터 가용성
        - 네트워크 연결
        - 데이터베이스 접근 권한

        Returns:
            (준비 완료 여부, 문제점 목록) 튜플

        예시:
            def validate_prerequisites(self) -> Tuple[bool, List[str]]:
                issues = []
                if not self.api.is_authenticated():
                    issues.append("API 인증 필요")
                if not self.db.is_connected():
                    issues.append("데이터베이스 연결 실패")
                return (len(issues) == 0, issues)
        """
        pass

    def execute_batch(
        self,
        tickers: List[TickerGapInfo],
        checkpoint_interval: int = 100,
        checkpoint_file: Optional[str] = None,
        resume: bool = False
    ) -> BackfillStats:
        """
        ticker 배치에 대한 백필 실행

        워크플로우:
        1. 사전 조건 검증
        2. 체크포인트에서 재개 (선택사항)
        3. 각 ticker에 대해:
           - Rate limiting 적용
           - execute_ticker() 호출
           - 재시도 로직 (실패 시)
           - 진행 상태 추적
           - 주기적으로 체크포인트 저장
        4. 최종 통계 반환

        Args:
            tickers: 백필할 ticker 목록
            checkpoint_interval: 체크포인트 저장 주기 (N개 ticker마다)
            checkpoint_file: 체크포인트 파일 경로 (None이면 자동 생성)
            resume: 체크포인트에서 재개 여부

        Returns:
            실행 결과를 포함한 BackfillStats
        """
        self._start_time = datetime.now()
        self._checkpoint_file = checkpoint_file or self._get_default_checkpoint_path()

        logger.info("=" * 80)
        logger.info(f"배치 백필 시작: {len(tickers):,} tickers")
        logger.info(f"모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info(f"Rate Limit: {self.rate_limit_delay}s/ticker")
        logger.info(f"Checkpoint Interval: {checkpoint_interval} tickers")
        logger.info(f"Checkpoint File: {self._checkpoint_file}")
        logger.info("=" * 80)

        # 1. 사전 조건 검증
        is_ready, issues = self.validate_prerequisites()
        if not is_ready:
            logger.error("사전 조건 검증 실패:")
            for issue in issues:
                logger.error(f"  - {issue}")
            self.stats.errors.append(f"Prerequisites failed: {', '.join(issues)}")
            return self.stats

        logger.info("✅ 사전 조건 검증 완료")

        # 2. 체크포인트에서 재개
        start_index = 0
        if resume:
            start_index = self._load_checkpoint()
            if start_index > 0:
                logger.info(f"체크포인트에서 재개: {start_index}/{len(tickers)} tickers 건너뜀")
                self.stats.tickers_skipped = start_index

        # 3. ticker 처리
        for i in range(start_index, len(tickers)):
            ticker_info = tickers[i]

            # 진행 상태 추적
            self._track_progress(i, len(tickers), ticker_info)

            # Rate limiting
            self._rate_limit()

            # DRY RUN 모드
            if self.dry_run:
                logger.debug(f"DRY RUN: {ticker_info.ticker} 건너뜀")
                self.stats.tickers_processed += 1
                continue

            # ticker 실행 (재시도 로직 포함)
            success = self._execute_ticker_with_retry(ticker_info)

            # 통계 업데이트
            self.stats.tickers_processed += 1
            if success:
                self.stats.tickers_success += 1
                self.stats.api_calls += 1
            else:
                self.stats.tickers_failed += 1

            # 체크포인트 저장
            if (i + 1) % checkpoint_interval == 0:
                self._save_checkpoint(i + 1)
                logger.info(f"💾 체크포인트 저장: {i + 1}/{len(tickers)} tickers")

        # 4. 최종 통계
        elapsed = (datetime.now() - self._start_time).total_seconds()
        self.stats.execution_time_sec = elapsed

        logger.info("\n" + "=" * 80)
        logger.info("배치 백필 완료")
        logger.info("=" * 80)
        logger.info(f"총 실행 시간: {elapsed:.1f}s")
        logger.info(f"처리된 tickers: {self.stats.tickers_processed}/{len(tickers)}")
        logger.info(f"성공: {self.stats.tickers_success}")
        logger.info(f"실패: {self.stats.tickers_failed}")
        logger.info(f"건너뜀: {self.stats.tickers_skipped}")
        logger.info(f"API 호출: {self.stats.api_calls}")
        if self.stats.tickers_failed > 0:
            logger.warning(f"⚠️  에러 {len(self.stats.errors)}개 발생")
        logger.info("=" * 80)

        return self.stats

    def _execute_ticker_with_retry(self, ticker_info: TickerGapInfo) -> bool:
        """
        재시도 로직이 포함된 ticker 실행

        최대 max_retries번까지 재시도하며, 각 재시도 사이에 exponential backoff 적용

        Args:
            ticker_info: 실행할 ticker 정보

        Returns:
            최종 성공 여부
        """
        for attempt in range(self.max_retries):
            try:
                success = self.execute_ticker(ticker_info)
                if success:
                    return True

                # 실패했지만 예외가 발생하지 않은 경우 (예: 데이터 없음)
                if attempt < self.max_retries - 1:
                    logger.warning(f"{ticker_info.ticker} 실패 (시도 {attempt + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    error_msg = f"{ticker_info.ticker}: 최대 재시도 횟수 초과"
                    logger.error(error_msg)
                    self.stats.errors.append(error_msg)
                    return False

            except Exception as e:
                error_msg = f"{ticker_info.ticker}: {str(e)}"
                if attempt < self.max_retries - 1:
                    logger.warning(f"{error_msg} (시도 {attempt + 1}/{self.max_retries}, 재시도 중...)")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"{error_msg} (최종 실패)")
                    self.stats.errors.append(error_msg)
                    return False

        return False

    def _rate_limit(self):
        """
        API 호출 속도 제한 적용

        마지막 호출 이후 rate_limit_delay 시간이 경과하지 않았으면 대기
        """
        if self.rate_limit_delay <= 0:
            return

        current_time = time.time()
        elapsed = current_time - self._last_rate_limit_time

        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            time.sleep(sleep_time)

        self._last_rate_limit_time = time.time()

    def _save_checkpoint(self, index: int):
        """
        현재 진행 상태를 체크포인트 파일에 저장

        Args:
            index: 다음 처리할 ticker의 인덱스
        """
        if not self._checkpoint_file:
            return

        checkpoint_data = {
            'last_processed_index': index,
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats.to_dict()
        }

        try:
            checkpoint_path = Path(self._checkpoint_file)
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.debug(f"체크포인트 저장 완료: {index} tickers")

        except Exception as e:
            logger.error(f"체크포인트 저장 실패: {e}")

    def _load_checkpoint(self) -> int:
        """
        체크포인트 파일에서 진행 상태 로드

        Returns:
            재개할 인덱스 (체크포인트 없으면 0)
        """
        if not self._checkpoint_file or not Path(self._checkpoint_file).exists():
            logger.debug("체크포인트 파일 없음, 처음부터 시작")
            return 0

        try:
            with open(self._checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)

            index = checkpoint_data.get('last_processed_index', 0)
            logger.info(f"체크포인트 로드 완료: {index} tickers 처리됨")

            # 통계 복구 (선택사항)
            if 'stats' in checkpoint_data:
                stats_dict = checkpoint_data['stats']
                self.stats.tickers_processed = stats_dict.get('tickers_processed', 0)
                self.stats.tickers_success = stats_dict.get('tickers_success', 0)
                self.stats.tickers_failed = stats_dict.get('tickers_failed', 0)
                self.stats.api_calls = stats_dict.get('api_calls', 0)
                self.stats.errors = stats_dict.get('errors', [])

            return index

        except Exception as e:
            logger.error(f"체크포인트 로드 실패: {e}")
            return 0

    def _track_progress(self, current: int, total: int, ticker_info: TickerGapInfo):
        """
        실시간 진행 상태 추적 및 로깅

        Args:
            current: 현재 인덱스
            total: 전체 ticker 수
            ticker_info: 현재 처리 중인 ticker 정보
        """
        progress_pct = (current / total * 100) if total > 0 else 0
        elapsed = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0

        # 매 10%마다 진행 상태 로깅
        if current % max(1, total // 10) == 0 or current == total - 1:
            logger.info(
                f"진행: {current + 1:,}/{total:,} ({progress_pct:.1f}%) | "
                f"경과: {elapsed:.0f}s | "
                f"현재: {ticker_info.ticker} ({ticker_info.name})"
            )

    def _get_default_checkpoint_path(self) -> str:
        """
        기본 체크포인트 파일 경로 생성

        Returns:
            체크포인트 파일 경로 (logs/checkpoints/{executor_name}_{timestamp}.json)
        """
        executor_name = self.__class__.__name__.lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"logs/checkpoints/{executor_name}_{timestamp}.json"

    def get_stats(self) -> BackfillStats:
        """
        현재 실행 통계 반환

        Returns:
            BackfillStats 객체
        """
        return self.stats

    def reset_stats(self):
        """통계 초기화"""
        self.stats = BackfillStats()
        logger.debug("통계 초기화 완료")
