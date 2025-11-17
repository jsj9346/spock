"""
데이터베이스 관련 예외 클래스 (Database Exception Classes)

PostgreSQL, TimescaleDB 데이터베이스 작업 중 발생하는
에러를 처리하기 위한 예외 클래스를 제공합니다.

Classes:
    DatabaseException: 데이터베이스 관련 예외의 기본 클래스
    ConnectionException: 연결 관련 예외
    ConnectionPoolExhausted: 연결 풀 고갈
    ConnectionTimeout: 연결 시간 초과
    QueryException: 쿼리 실행 관련 예외
    QueryTimeout: 쿼리 시간 초과
    QuerySyntaxError: SQL 구문 오류
    TransactionException: 트랜잭션 관련 예외
    DeadlockException: 데드락 발생
    IntegrityException: 데이터 무결성 위반
    MigrationException: 마이그레이션 관련 예외

사용법:
    from infrastructure.exceptions import ConnectionPoolExhausted

    if pool.active_connections >= pool.max_connections:
        raise ConnectionPoolExhausted(
            f"Connection pool exhausted: {pool.active_connections}/{pool.max_connections}",
            details={"active": pool.active_connections, "max": pool.max_connections}
        )
"""

from typing import Optional, Dict, Any
from .base import SpockBaseException


class DatabaseException(SpockBaseException):
    """
    데이터베이스 작업 중 발생하는 모든 에러의 기본 클래스

    PostgreSQL, TimescaleDB와 관련된 모든 에러는 이 클래스를
    상속해야 합니다.
    """
    error_code = "DB_ERROR"


# ============================================================================
# Connection Exceptions (연결 관련 예외)
# ============================================================================

class ConnectionException(DatabaseException):
    """데이터베이스 연결 관련 예외"""
    error_code = "DB_CONNECTION_ERROR"


class ConnectionPoolExhausted(ConnectionException):
    """
    연결 풀 고갈

    사용 가능한 데이터베이스 연결이 없을 때 발생합니다.
    연결 풀 크기를 늘리거나 연결 재사용을 개선해야 합니다.

    사용 예제:
        >>> if self._active_connections >= self._max_connections:
        ...     raise ConnectionPoolExhausted(
        ...         f"Connection pool exhausted: {active}/{max}",
        ...         details={"active": active, "max": max}
        ...     )
    """
    error_code = "DB_POOL_EXHAUSTED"


class ConnectionTimeout(ConnectionException):
    """
    연결 시간 초과

    데이터베이스 연결 시도가 타임아웃 시간을 초과했을 때 발생합니다.
    """
    error_code = "DB_CONNECTION_TIMEOUT"


class ConnectionNotInitialized(ConnectionException):
    """
    연결 미초기화

    데이터베이스 연결이 초기화되지 않은 상태에서 작업을 시도할 때 발생합니다.
    """
    error_code = "DB_CONNECTION_NOT_INITIALIZED"


class ConnectionClosed(ConnectionException):
    """
    연결 종료됨

    이미 종료된 연결에 대해 작업을 시도할 때 발생합니다.
    """
    error_code = "DB_CONNECTION_CLOSED"


# ============================================================================
# Query Exceptions (쿼리 관련 예외)
# ============================================================================

class QueryException(DatabaseException):
    """쿼리 실행 관련 예외"""
    error_code = "DB_QUERY_ERROR"


class QueryTimeout(QueryException):
    """
    쿼리 시간 초과

    쿼리 실행 시간이 허용된 타임아웃을 초과했을 때 발생합니다.

    사용 예제:
        >>> # Query took too long
        ... raise QueryTimeout(
        ...     f"Query timeout after {timeout}s: {query[:50]}...",
        ...     details={"query": query, "timeout": timeout}
        ... )
    """
    error_code = "DB_QUERY_TIMEOUT"


class QuerySyntaxError(QueryException):
    """
    SQL 구문 오류

    잘못된 SQL 구문으로 인해 쿼리가 실패했을 때 발생합니다.
    """
    error_code = "DB_QUERY_SYNTAX_ERROR"


class QueryExecutionError(QueryException):
    """
    쿼리 실행 실패

    유효한 SQL이지만 실행 중 에러가 발생했을 때 사용합니다.
    """
    error_code = "DB_QUERY_EXECUTION_ERROR"


class RecordNotFoundError(QueryException):
    """
    레코드 없음

    조회 결과가 없을 때 발생합니다.

    사용 예제:
        >>> result = cursor.fetchone()
        ... if not result:
        ...     raise RecordNotFoundError(
        ...         f"Ticker not found: {ticker}",
        ...         details={"ticker": ticker, "region": region}
        ...     )
    """
    error_code = "DB_RECORD_NOT_FOUND"


class MultipleRecordsFoundError(QueryException):
    """
    다중 레코드 발견

    단일 레코드를 기대했지만 여러 레코드가 반환되었을 때 발생합니다.
    """
    error_code = "DB_MULTIPLE_RECORDS_FOUND"


# ============================================================================
# Transaction Exceptions (트랜잭션 관련 예외)
# ============================================================================

class TransactionException(DatabaseException):
    """트랜잭션 관련 예외"""
    error_code = "DB_TRANSACTION_ERROR"


class TransactionRollbackError(TransactionException):
    """
    트랜잭션 롤백 실패

    트랜잭션 롤백 시도가 실패했을 때 발생합니다.
    """
    error_code = "DB_TRANSACTION_ROLLBACK_ERROR"


class TransactionCommitError(TransactionException):
    """
    트랜잭션 커밋 실패

    트랜잭션 커밋 시도가 실패했을 때 발생합니다.
    """
    error_code = "DB_TRANSACTION_COMMIT_ERROR"


class DeadlockException(TransactionException):
    """
    데드락 발생

    두 개 이상의 트랜잭션이 서로의 자원을 기다리면서
    무한 대기 상태에 빠졌을 때 발생합니다.

    사용 예제:
        >>> try:
        ...     cursor.execute(query)
        ... except psycopg2.extensions.TransactionRollbackError as e:
        ...     raise DeadlockException(
        ...         "Deadlock detected",
        ...         details={"query": query},
        ...         original_exception=e
        ...     )
    """
    error_code = "DB_DEADLOCK"


# ============================================================================
# Integrity Exceptions (데이터 무결성 관련 예외)
# ============================================================================

class IntegrityException(DatabaseException):
    """데이터 무결성 위반 예외"""
    error_code = "DB_INTEGRITY_ERROR"


class UniqueViolationError(IntegrityException):
    """
    고유 제약 조건 위반

    UNIQUE 제약 조건을 위반하는 데이터 삽입/업데이트 시 발생합니다.

    사용 예제:
        >>> # Duplicate ticker insertion
        ... raise UniqueViolationError(
        ...     f"Ticker already exists: {ticker}",
        ...     details={"ticker": ticker, "region": region}
        ... )
    """
    error_code = "DB_UNIQUE_VIOLATION"


class ForeignKeyViolationError(IntegrityException):
    """
    외래 키 제약 조건 위반

    FOREIGN KEY 제약 조건을 위반하는 데이터 삽입/업데이트/삭제 시 발생합니다.
    """
    error_code = "DB_FOREIGN_KEY_VIOLATION"


class CheckConstraintViolationError(IntegrityException):
    """
    CHECK 제약 조건 위반

    CHECK 제약 조건을 위반하는 데이터 삽입/업데이트 시 발생합니다.
    """
    error_code = "DB_CHECK_CONSTRAINT_VIOLATION"


class NotNullViolationError(IntegrityException):
    """
    NOT NULL 제약 조건 위반

    NOT NULL 컬럼에 NULL 값을 삽입/업데이트하려 할 때 발생합니다.
    """
    error_code = "DB_NOT_NULL_VIOLATION"


# ============================================================================
# Migration Exceptions (마이그레이션 관련 예외)
# ============================================================================

class MigrationException(DatabaseException):
    """데이터베이스 마이그레이션 관련 예외"""
    error_code = "DB_MIGRATION_ERROR"


class MigrationAlreadyApplied(MigrationException):
    """
    마이그레이션 이미 적용됨

    이미 적용된 마이그레이션을 다시 적용하려 할 때 발생합니다.
    """
    error_code = "DB_MIGRATION_ALREADY_APPLIED"


class MigrationNotFound(MigrationException):
    """
    마이그레이션 파일 없음

    요청한 마이그레이션 파일을 찾을 수 없을 때 발생합니다.
    """
    error_code = "DB_MIGRATION_NOT_FOUND"


class MigrationRollbackError(MigrationException):
    """
    마이그레이션 롤백 실패

    마이그레이션 롤백 시도가 실패했을 때 발생합니다.
    """
    error_code = "DB_MIGRATION_ROLLBACK_ERROR"


# ============================================================================
# Schema Exceptions (스키마 관련 예외)
# ============================================================================

class SchemaException(DatabaseException):
    """스키마 관련 예외"""
    error_code = "DB_SCHEMA_ERROR"


class TableNotFoundError(SchemaException):
    """
    테이블 없음

    요청한 테이블이 존재하지 않을 때 발생합니다.
    """
    error_code = "DB_TABLE_NOT_FOUND"


class ColumnNotFoundError(SchemaException):
    """
    컬럼 없음

    요청한 컬럼이 존재하지 않을 때 발생합니다.
    """
    error_code = "DB_COLUMN_NOT_FOUND"


class InvalidSchemaError(SchemaException):
    """
    유효하지 않은 스키마

    스키마 정의가 유효하지 않을 때 발생합니다.
    """
    error_code = "DB_INVALID_SCHEMA"
