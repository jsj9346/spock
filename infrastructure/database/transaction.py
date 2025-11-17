"""
Transaction Manager

명시적 트랜잭션 관리를 위한 컨텍스트 매니저를 제공합니다.

Classes:
    TransactionManager: 트랜잭션 관리자
    TransactionContext: 트랜잭션 컨텍스트 (내부 사용)

Features:
    - 자동 COMMIT/ROLLBACK
    - Isolation Level 제어
    - Nested Transaction 지원 (SAVEPOINT)
    - 트랜잭션 통계 추적

사용법:
    from infrastructure.database import ConnectionPoolManager, TransactionManager

    pool_mgr = ConnectionPoolManager()
    tx_mgr = TransactionManager(pool_mgr)

    with tx_mgr.transaction() as cursor:
        cursor.execute("INSERT INTO tickers ...")
        cursor.execute("UPDATE ticker_fundamentals ...")
        # 자동 COMMIT (예외 발생 시 ROLLBACK)
"""

from contextlib import contextmanager
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from psycopg2.extensions import ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE

from infrastructure.exceptions import (
    TransactionException,
    TransactionRollbackError,
    TransactionCommitError,
    DeadlockException
)

logger = logging.getLogger(__name__)


class TransactionStatistics:
    """
    트랜잭션 통계 정보

    Attributes:
        total_transactions: 총 트랜잭션 수
        committed_transactions: 커밋된 트랜잭션 수
        rolled_back_transactions: 롤백된 트랜잭션 수
        failed_transactions: 실패한 트랜잭션 수
        deadlocks: 데드락 발생 횟수
        average_duration: 평균 트랜잭션 실행 시간 (초)
    """

    def __init__(self):
        self.total_transactions = 0
        self.committed_transactions = 0
        self.rolled_back_transactions = 0
        self.failed_transactions = 0
        self.deadlocks = 0
        self.average_duration = 0.0
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """통계 정보를 딕셔너리로 변환"""
        return {
            "total_transactions": self.total_transactions,
            "committed_transactions": self.committed_transactions,
            "rolled_back_transactions": self.rolled_back_transactions,
            "failed_transactions": self.failed_transactions,
            "deadlocks": self.deadlocks,
            "success_rate": self.get_success_rate(),
            "average_duration": self.average_duration,
            "last_updated": self.last_updated.isoformat()
        }

    def get_success_rate(self) -> float:
        """트랜잭션 성공률 계산 (%)"""
        if self.total_transactions == 0:
            return 100.0
        return (self.committed_transactions / self.total_transactions) * 100


class TransactionManager:
    """
    트랜잭션 관리자

    명시적 트랜잭션 관리를 위한 컨텍스트 매니저를 제공합니다.

    Example:
        >>> tx_mgr = TransactionManager(pool_manager)
        >>> with tx_mgr.transaction() as cursor:
        ...     cursor.execute("INSERT INTO tickers VALUES (%s, %s)", ('AAPL', 'US'))
        ...     cursor.execute("UPDATE ticker_fundamentals SET ...")
        ...     # 자동 COMMIT
    """

    def __init__(self, pool_manager):
        """
        트랜잭션 관리자 초기화

        Args:
            pool_manager: ConnectionPoolManager 인스턴스
        """
        self.pool_manager = pool_manager
        self.statistics = TransactionStatistics()

    @contextmanager
    def transaction(
        self,
        isolation_level: Optional[str] = None,
        readonly: bool = False,
        deferrable: bool = False
    ):
        """
        트랜잭션 컨텍스트 매니저

        Args:
            isolation_level: 격리 수준
                - 'READ UNCOMMITTED'
                - 'READ COMMITTED' (기본값)
                - 'REPEATABLE READ'
                - 'SERIALIZABLE'
            readonly: 읽기 전용 트랜잭션 여부
            deferrable: 지연 가능 트랜잭션 여부

        Yields:
            psycopg2.cursor: 데이터베이스 커서

        Raises:
            TransactionCommitError: 커밋 실패
            TransactionRollbackError: 롤백 실패
            DeadlockException: 데드락 발생

        Example:
            >>> with tx_mgr.transaction(isolation_level='SERIALIZABLE') as cursor:
            ...     cursor.execute("SELECT * FROM tickers FOR UPDATE")
            ...     # 트랜잭션 처리
        """
        start_time = datetime.now()
        self.statistics.total_transactions += 1

        with self.pool_manager.get_connection() as conn:
            cursor = None

            try:
                cursor = conn.cursor()

                # Isolation Level 설정
                if isolation_level:
                    self._set_isolation_level(cursor, isolation_level, readonly, deferrable)

                # 트랜잭션 시작
                logger.debug(
                    f"Transaction started (isolation={isolation_level or 'default'}, "
                    f"readonly={readonly})"
                )

                yield cursor

                # COMMIT
                conn.commit()
                self.statistics.committed_transactions += 1

                # 실행 시간 계산
                duration = (datetime.now() - start_time).total_seconds()
                self._update_average_duration(duration)

                logger.debug(f"Transaction committed (duration: {duration:.3f}s)")

            except Exception as e:
                # ROLLBACK
                try:
                    conn.rollback()
                    self.statistics.rolled_back_transactions += 1
                    logger.warning(f"Transaction rolled back: {type(e).__name__}: {str(e)}")

                except Exception as rollback_error:
                    self.statistics.failed_transactions += 1
                    logger.error(f"Rollback failed: {rollback_error}")

                    raise TransactionRollbackError(
                        f"Failed to rollback transaction: {str(rollback_error)}",
                        details={
                            "original_error": str(e),
                            "rollback_error": str(rollback_error)
                        },
                        original_exception=rollback_error
                    )

                # 데드락 감지
                if "deadlock" in str(e).lower():
                    self.statistics.deadlocks += 1
                    raise DeadlockException(
                        "Deadlock detected during transaction",
                        details={"error_message": str(e)},
                        original_exception=e
                    )

                # 일반 트랜잭션 예외로 래핑
                raise TransactionException(
                    f"Transaction failed: {str(e)}",
                    details={
                        "isolation_level": isolation_level,
                        "readonly": readonly
                    },
                    original_exception=e
                )

            finally:
                if cursor is not None:
                    cursor.close()

                self.statistics.last_updated = datetime.now()

    @contextmanager
    def savepoint(self, name: str = None):
        """
        Nested Transaction (SAVEPOINT) 지원

        Args:
            name: Savepoint 이름 (기본값: 자동 생성)

        Yields:
            psycopg2.cursor: 데이터베이스 커서

        Example:
            >>> with tx_mgr.transaction() as cursor:
            ...     cursor.execute("INSERT INTO tickers ...")
            ...
            ...     with tx_mgr.savepoint("before_update") as sp_cursor:
            ...         sp_cursor.execute("UPDATE ticker_fundamentals ...")
            ...         # 이 부분만 롤백 가능
        """
        savepoint_name = name or f"sp_{datetime.now().timestamp()}"

        with self.pool_manager.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # SAVEPOINT 생성
                cursor.execute(f"SAVEPOINT {savepoint_name}")
                logger.debug(f"Savepoint created: {savepoint_name}")

                yield cursor

                # RELEASE SAVEPOINT
                cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                logger.debug(f"Savepoint released: {savepoint_name}")

            except Exception as e:
                # ROLLBACK TO SAVEPOINT
                try:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    logger.warning(f"Rolled back to savepoint: {savepoint_name}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback to savepoint: {rollback_error}")

                raise TransactionException(
                    f"Savepoint operation failed: {str(e)}",
                    details={"savepoint": savepoint_name},
                    original_exception=e
                )

            finally:
                cursor.close()

    def _set_isolation_level(
        self,
        cursor,
        isolation_level: str,
        readonly: bool,
        deferrable: bool
    ):
        """
        트랜잭션 Isolation Level 설정

        Args:
            cursor: 데이터베이스 커서
            isolation_level: 격리 수준
            readonly: 읽기 전용 여부
            deferrable: 지연 가능 여부
        """
        isolation_map = {
            'READ UNCOMMITTED': 'READ UNCOMMITTED',
            'READ COMMITTED': 'READ COMMITTED',
            'REPEATABLE READ': 'REPEATABLE READ',
            'SERIALIZABLE': 'SERIALIZABLE'
        }

        level = isolation_map.get(isolation_level.upper(), 'READ COMMITTED')
        query = f"SET TRANSACTION ISOLATION LEVEL {level}"

        if readonly:
            query += " READ ONLY"

        if deferrable:
            query += " DEFERRABLE"

        cursor.execute(query)
        logger.debug(f"Isolation level set: {query}")

    def _update_average_duration(self, duration: float):
        """평균 실행 시간 업데이트"""
        committed = self.statistics.committed_transactions
        if committed == 0:
            self.statistics.average_duration = 0.0
        else:
            self.statistics.average_duration = (
                (self.statistics.average_duration * (committed - 1) + duration) / committed
            )

    def get_statistics(self) -> Dict[str, Any]:
        """
        트랜잭션 통계 정보 반환

        Returns:
            Dict containing transaction statistics

        Example:
            >>> stats = tx_mgr.get_statistics()
            >>> print(f"Success rate: {stats['success_rate']:.1f}%")
        """
        self.statistics.last_updated = datetime.now()
        return self.statistics.to_dict()

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"TransactionManager("
            f"total={self.statistics.total_transactions}, "
            f"committed={self.statistics.committed_transactions}, "
            f"rolled_back={self.statistics.rolled_back_transactions})"
        )
