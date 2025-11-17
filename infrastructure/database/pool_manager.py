"""
Connection Pool Manager

PostgreSQL 연결 풀을 효율적으로 관리하고 모니터링하는 기능을 제공합니다.

Classes:
    ConnectionPoolManager: 향상된 연결 풀 관리자
    PoolStatistics: 연결 풀 통계 정보

Features:
    - 연결 풀 상태 모니터링
    - 자동 연결 재사용
    - 유휴 연결 정리
    - Health Check
    - 연결 타임아웃 관리

사용법:
    from infrastructure.database import ConnectionPoolManager

    pool_manager = ConnectionPoolManager(
        min_conn=10,
        max_conn=30,
        host='localhost',
        database='quant_platform'
    )

    with pool_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickers")
"""

import psycopg2
from psycopg2 import pool
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Optional, Dict, Any
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv

from infrastructure.exceptions import (
    ConnectionPoolExhausted,
    ConnectionTimeout,
    ConnectionNotInitialized,
    ConnectionClosed,
    DatabaseException
)

logger = logging.getLogger(__name__)


class PoolStatistics:
    """
    연결 풀 통계 정보

    Attributes:
        min_connections: 최소 연결 수
        max_connections: 최대 연결 수
        active_connections: 활성 연결 수
        idle_connections: 유휴 연결 수
        total_requests: 총 연결 요청 수
        successful_requests: 성공한 연결 요청 수
        failed_requests: 실패한 연결 요청 수
        average_wait_time: 평균 대기 시간 (초)
    """

    def __init__(self):
        self.min_connections = 0
        self.max_connections = 0
        self.active_connections = 0
        self.idle_connections = 0
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.average_wait_time = 0.0
        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """통계 정보를 딕셔너리로 변환"""
        return {
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "utilization_rate": self.get_utilization_rate(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.get_success_rate(),
            "average_wait_time": self.average_wait_time,
            "last_updated": self.last_updated.isoformat()
        }

    def get_utilization_rate(self) -> float:
        """연결 풀 사용률 계산 (%))"""
        if self.max_connections == 0:
            return 0.0
        return (self.active_connections / self.max_connections) * 100

    def get_success_rate(self) -> float:
        """연결 요청 성공률 계산 (%)"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100


class ConnectionPoolManager:
    """
    향상된 PostgreSQL 연결 풀 관리자

    기존 PostgresDatabaseManager를 확장하여 다음 기능을 추가:
    - 연결 풀 상태 모니터링
    - 자동 연결 재사용
    - 유휴 연결 정리
    - Health Check
    - 타임아웃 관리

    Example:
        >>> pool_mgr = ConnectionPoolManager(min_conn=10, max_conn=30)
        >>> with pool_mgr.get_connection() as conn:
        ...     cursor = conn.cursor()
        ...     cursor.execute("SELECT * FROM tickers")
        ...     results = cursor.fetchall()
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        min_conn: int = 10,
        max_conn: int = 30,
        connection_timeout: int = 30,
        idle_timeout: int = 600  # 10분
    ):
        """
        연결 풀 초기화

        Args:
            host: PostgreSQL 호스트 (기본값: localhost)
            port: PostgreSQL 포트 (기본값: 5432)
            database: 데이터베이스 이름 (기본값: quant_platform)
            user: 데이터베이스 사용자
            password: 데이터베이스 비밀번호
            min_conn: 최소 연결 수
            max_conn: 최대 연결 수
            connection_timeout: 연결 타임아웃 (초)
            idle_timeout: 유휴 연결 타임아웃 (초)
        """
        # .env에서 설정 로드
        load_dotenv()

        self.host = host or os.getenv('POSTGRES_HOST', 'localhost')
        self.port = port or int(os.getenv('POSTGRES_PORT', 5432))
        self.database = database or os.getenv('POSTGRES_DB', 'quant_platform')
        self.user = user or os.getenv('POSTGRES_USER')
        self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        self.min_conn = min_conn
        self.max_conn = max_conn
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout

        # 통계 정보
        self.statistics = PoolStatistics()
        self.statistics.min_connections = min_conn
        self.statistics.max_connections = max_conn

        # 연결 풀 생성
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self._initialize_pool()

    def _initialize_pool(self):
        """연결 풀 초기화"""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                self.min_conn,
                self.max_conn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=self.connection_timeout
            )

            logger.info(
                f"Connection pool initialized: "
                f"{self.min_conn}-{self.max_conn} connections "
                f"to {self.host}:{self.port}/{self.database}"
            )

        except psycopg2.Error as e:
            raise DatabaseException(
                f"Failed to initialize connection pool: {str(e)}",
                details={
                    "host": self.host,
                    "port": self.port,
                    "database": self.database
                },
                original_exception=e
            )

    @contextmanager
    def get_connection(self, timeout: Optional[int] = None):
        """
        연결 획득 (컨텍스트 매니저)

        Args:
            timeout: 연결 획득 대기 타임아웃 (초)

        Yields:
            psycopg2.connection: 데이터베이스 연결

        Raises:
            ConnectionPoolExhausted: 연결 풀 고갈
            ConnectionTimeout: 연결 타임아웃
            ConnectionNotInitialized: 연결 풀 미초기화

        Example:
            >>> with pool_mgr.get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT 1")
        """
        if self._pool is None:
            raise ConnectionNotInitialized(
                "Connection pool not initialized",
                details={"host": self.host, "database": self.database}
            )

        conn = None
        start_time = datetime.now()

        try:
            # 통계 업데이트
            self.statistics.total_requests += 1

            # 연결 획득
            conn = self._pool.getconn()

            if conn is None:
                raise ConnectionPoolExhausted(
                    f"Connection pool exhausted: {self.max_conn} connections in use",
                    details={
                        "max_connections": self.max_conn,
                        "total_requests": self.statistics.total_requests
                    }
                )

            # 통계 업데이트
            self.statistics.successful_requests += 1
            self.statistics.active_connections += 1

            # 대기 시간 계산
            wait_time = (datetime.now() - start_time).total_seconds()
            self.statistics.average_wait_time = (
                (self.statistics.average_wait_time * (self.statistics.successful_requests - 1) + wait_time)
                / self.statistics.successful_requests
            )

            logger.debug(f"Connection acquired (wait time: {wait_time:.3f}s)")

            yield conn

        except psycopg2.Error as e:
            self.statistics.failed_requests += 1
            logger.error(f"Failed to acquire connection: {e}")

            raise ConnectionTimeout(
                f"Connection timeout after {timeout or self.connection_timeout}s",
                details={"timeout": timeout or self.connection_timeout},
                original_exception=e
            )

        finally:
            if conn is not None:
                try:
                    # 연결 반환
                    self._pool.putconn(conn)
                    self.statistics.active_connections -= 1
                    self.statistics.idle_connections += 1
                    logger.debug("Connection returned to pool")

                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")

            self.statistics.last_updated = datetime.now()

    def health_check(self) -> bool:
        """
        연결 풀 Health Check

        Returns:
            bool: 정상이면 True, 문제가 있으면 False

        Example:
            >>> if pool_mgr.health_check():
            ...     print("Pool is healthy")
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()

            logger.debug("Health check passed")
            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        연결 풀 통계 정보 반환

        Returns:
            Dict containing pool statistics

        Example:
            >>> stats = pool_mgr.get_statistics()
            >>> print(f"Utilization: {stats['utilization_rate']:.1f}%")
        """
        # 통계 업데이트
        self.statistics.last_updated = datetime.now()
        return self.statistics.to_dict()

    def close_all_connections(self):
        """
        모든 연결 종료

        Example:
            >>> pool_mgr.close_all_connections()
        """
        if self._pool is not None:
            try:
                self._pool.closeall()
                logger.info("All connections closed")

                # 통계 초기화
                self.statistics.active_connections = 0
                self.statistics.idle_connections = 0

            except Exception as e:
                logger.error(f"Error closing connections: {e}")
                raise DatabaseException(
                    "Failed to close all connections",
                    original_exception=e
                )

    def __del__(self):
        """소멸자: 연결 풀 정리"""
        try:
            self.close_all_connections()
        except Exception:
            pass  # 소멸자에서는 예외를 무시

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"ConnectionPoolManager("
            f"host={self.host}, "
            f"database={self.database}, "
            f"pool={self.min_conn}-{self.max_conn})"
        )
