"""
TransactionManager 단위 테스트

Tests:
    - 트랜잭션 컨텍스트 (6 tests)
    - 격리 수준 (4 tests)
    - 통계 및 모니터링 (3 tests)
    - 에러 처리 (3 tests)

Total: 16 tests
"""

import pytest
import psycopg2
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

from infrastructure.database.transaction import TransactionManager, TransactionStatistics
from infrastructure.exceptions import (
    TransactionException,
    TransactionRollbackError,
    TransactionCommitError,
    DeadlockException
)


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def mock_connection():
    """Mock psycopg2 connection"""
    conn = Mock(spec=psycopg2.extensions.connection)
    cursor = Mock()
    cursor.execute = Mock()
    cursor.fetchone = Mock(return_value=(1,))
    cursor.fetchall = Mock(return_value=[(1,)])
    cursor.close = Mock()
    conn.cursor = Mock(return_value=cursor)
    conn.commit = Mock()
    conn.rollback = Mock()
    return conn


@pytest.fixture
def mock_pool_manager(mock_connection):
    """Mock ConnectionPoolManager"""
    pool_mgr = Mock()

    # get_connection()을 context manager로 동작하도록 설정
    cm = MagicMock()
    cm.__enter__ = Mock(return_value=mock_connection)
    cm.__exit__ = Mock(return_value=False)
    pool_mgr.get_connection = Mock(return_value=cm)

    return pool_mgr


@pytest.fixture
def tx_manager(mock_pool_manager):
    """TransactionManager 인스턴스 생성"""
    return TransactionManager(mock_pool_manager)


# ========================================
# 1. Transaction Context (6 tests)
# ========================================

def test_transaction_context_manager_normal_flow(tx_manager, mock_connection):
    """트랜잭션 컨텍스트 매니저 정상 흐름 테스트"""
    # When: transaction context manager 사용
    with tx_manager.transaction() as cursor:
        cursor.execute("INSERT INTO tickers VALUES (%s, %s)", ('AAPL', 'US'))

    # Then: commit 호출됨
    mock_connection.commit.assert_called_once()

    # Then: 통계 업데이트
    stats = tx_manager.get_statistics()
    assert stats['total_transactions'] == 1
    assert stats['committed_transactions'] == 1
    assert stats['rolled_back_transactions'] == 0


def test_transaction_auto_commit(tx_manager, mock_connection):
    """트랜잭션 자동 커밋 테스트"""
    # When: 정상적으로 트랜잭션 완료
    with tx_manager.transaction() as cursor:
        cursor.execute("SELECT 1")

    # Then: commit 호출됨
    mock_connection.commit.assert_called_once()

    # Then: cursor close 호출됨
    mock_connection.cursor().close.assert_called_once()


def test_transaction_auto_rollback_on_exception(tx_manager, mock_connection):
    """예외 발생 시 자동 롤백 테스트"""
    # When/Then: 예외 발생
    with pytest.raises(TransactionException):
        with tx_manager.transaction() as cursor:
            cursor.execute("INSERT INTO tickers VALUES ...")
            raise ValueError("Test error")

    # Then: rollback 호출됨
    mock_connection.rollback.assert_called_once()

    # Then: 통계 업데이트
    stats = tx_manager.get_statistics()
    assert stats['total_transactions'] == 1
    assert stats['committed_transactions'] == 0
    assert stats['rolled_back_transactions'] == 1


def test_transaction_cursor_cleanup(tx_manager, mock_connection):
    """트랜잭션 종료 시 cursor 정리 테스트"""
    # When: 트랜잭션 완료
    with tx_manager.transaction() as cursor:
        pass

    # Then: cursor close 호출됨
    mock_connection.cursor().close.assert_called_once()


def test_nested_transaction_savepoint(tx_manager, mock_connection):
    """Nested transaction (SAVEPOINT) 테스트"""
    # When: savepoint 사용
    with tx_manager.savepoint("test_sp") as cursor:
        cursor.execute("INSERT INTO tickers VALUES ...")

    # Then: SAVEPOINT 관련 SQL 실행됨
    calls = mock_connection.cursor().execute.call_args_list

    # SAVEPOINT 생성
    assert any("SAVEPOINT test_sp" in str(call) for call in calls)

    # RELEASE SAVEPOINT
    assert any("RELEASE SAVEPOINT test_sp" in str(call) for call in calls)


def test_savepoint_rollback_on_error(tx_manager, mock_connection):
    """Savepoint 에러 시 롤백 테스트"""
    # Given: execute가 예외 발생하도록 설정
    mock_connection.cursor().execute.side_effect = [
        None,  # SAVEPOINT 생성
        ValueError("Test error"),  # 실제 쿼리 실패
        None   # ROLLBACK TO SAVEPOINT
    ]

    # When/Then: 예외 발생
    with pytest.raises(TransactionException):
        with tx_manager.savepoint("test_sp") as cursor:
            cursor.execute("INSERT INTO tickers VALUES ...")

    # Then: ROLLBACK TO SAVEPOINT 호출됨
    calls = mock_connection.cursor().execute.call_args_list
    assert any("ROLLBACK TO SAVEPOINT test_sp" in str(call) for call in calls)


# ========================================
# 2. Isolation Levels (4 tests)
# ========================================

def test_transaction_read_committed(tx_manager, mock_connection):
    """READ COMMITTED isolation level 테스트"""
    # When: READ COMMITTED 트랜잭션
    with tx_manager.transaction(isolation_level='READ COMMITTED') as cursor:
        cursor.execute("SELECT 1")

    # Then: SET TRANSACTION 호출됨
    calls = mock_connection.cursor().execute.call_args_list
    assert any("SET TRANSACTION ISOLATION LEVEL READ COMMITTED" in str(call) for call in calls)


def test_transaction_repeatable_read(tx_manager, mock_connection):
    """REPEATABLE READ isolation level 테스트"""
    # When: REPEATABLE READ 트랜잭션
    with tx_manager.transaction(isolation_level='REPEATABLE READ') as cursor:
        cursor.execute("SELECT 1")

    # Then: SET TRANSACTION 호출됨
    calls = mock_connection.cursor().execute.call_args_list
    assert any("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" in str(call) for call in calls)


def test_transaction_serializable(tx_manager, mock_connection):
    """SERIALIZABLE isolation level 테스트"""
    # When: SERIALIZABLE 트랜잭션
    with tx_manager.transaction(isolation_level='SERIALIZABLE') as cursor:
        cursor.execute("SELECT 1")

    # Then: SET TRANSACTION 호출됨
    calls = mock_connection.cursor().execute.call_args_list
    assert any("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE" in str(call) for call in calls)


def test_transaction_readonly_deferrable(tx_manager, mock_connection):
    """READ ONLY + DEFERRABLE 트랜잭션 테스트"""
    # When: READ ONLY, DEFERRABLE 옵션 사용
    with tx_manager.transaction(
        isolation_level='SERIALIZABLE',
        readonly=True,
        deferrable=True
    ) as cursor:
        cursor.execute("SELECT 1")

    # Then: READ ONLY, DEFERRABLE 포함된 SQL 실행
    calls = mock_connection.cursor().execute.call_args_list
    # 첫 번째 execute가 SET TRANSACTION
    set_tx_call = str(calls[0])
    assert "READ ONLY" in set_tx_call
    assert "DEFERRABLE" in set_tx_call


# ========================================
# 3. Statistics & Monitoring (3 tests)
# ========================================

def test_statistics_initialization(tx_manager):
    """통계 초기화 테스트"""
    # When: get_statistics 호출
    stats = tx_manager.get_statistics()

    # Then: 초기값 확인
    assert stats['total_transactions'] == 0
    assert stats['committed_transactions'] == 0
    assert stats['rolled_back_transactions'] == 0
    assert stats['failed_transactions'] == 0
    assert stats['deadlocks'] == 0
    assert stats['success_rate'] == 100.0
    assert stats['average_duration'] == 0.0


def test_statistics_after_successful_transaction(tx_manager, mock_connection):
    """성공적인 트랜잭션 후 통계 테스트"""
    # When: 트랜잭션 성공
    with tx_manager.transaction() as cursor:
        cursor.execute("SELECT 1")

    # When: 통계 확인
    stats = tx_manager.get_statistics()

    # Then: 통계 업데이트됨
    assert stats['total_transactions'] == 1
    assert stats['committed_transactions'] == 1
    assert stats['rolled_back_transactions'] == 0
    assert stats['success_rate'] == 100.0
    assert stats['average_duration'] > 0


def test_statistics_success_rate_calculation(tx_manager, mock_connection):
    """성공률 계산 테스트"""
    # Given: 여러 트랜잭션 실행 (일부 실패)
    # 성공 2번
    for _ in range(2):
        with tx_manager.transaction() as cursor:
            cursor.execute("SELECT 1")

    # 실패 1번
    try:
        with tx_manager.transaction() as cursor:
            raise ValueError("Test error")
    except TransactionException:
        pass

    # When: 통계 확인
    stats = tx_manager.get_statistics()

    # Then: 성공률 계산 (2/3 = 66.67%)
    assert stats['total_transactions'] == 3
    assert stats['committed_transactions'] == 2
    assert stats['rolled_back_transactions'] == 1
    assert abs(stats['success_rate'] - 66.67) < 0.01


# ========================================
# 4. Error Handling (3 tests)
# ========================================

def test_transaction_commit_error(tx_manager, mock_connection):
    """커밋 실패 테스트"""
    # Given: commit이 예외 발생하도록 설정
    mock_connection.commit.side_effect = psycopg2.DatabaseError("Commit failed")

    # When/Then: 예외 발생
    with pytest.raises(TransactionException):
        with tx_manager.transaction() as cursor:
            cursor.execute("SELECT 1")

    # Then: rollback 호출됨
    mock_connection.rollback.assert_called_once()


def test_transaction_rollback_error(tx_manager, mock_connection):
    """롤백 실패 테스트"""
    # Given: rollback이 예외 발생하도록 설정
    mock_connection.cursor().execute.side_effect = ValueError("Query failed")
    mock_connection.rollback.side_effect = psycopg2.DatabaseError("Rollback failed")

    # When/Then: TransactionRollbackError 발생
    with pytest.raises(TransactionRollbackError) as exc_info:
        with tx_manager.transaction() as cursor:
            cursor.execute("INSERT INTO tickers VALUES ...")

    assert "Failed to rollback transaction" in str(exc_info.value)

    # Then: failed_transactions 증가
    stats = tx_manager.get_statistics()
    assert stats['failed_transactions'] == 1


def test_deadlock_detection(tx_manager, mock_connection):
    """데드락 감지 테스트"""
    # Given: execute가 deadlock 에러 발생하도록 설정
    mock_connection.cursor().execute.side_effect = psycopg2.DatabaseError(
        "deadlock detected"
    )

    # When/Then: DeadlockException 발생
    with pytest.raises(DeadlockException) as exc_info:
        with tx_manager.transaction() as cursor:
            cursor.execute("UPDATE tickers SET ...")

    assert "Deadlock detected" in str(exc_info.value)

    # Then: deadlocks 증가
    stats = tx_manager.get_statistics()
    assert stats['deadlocks'] == 1


# ========================================
# Additional Tests
# ========================================

def test_transaction_average_duration_calculation(tx_manager, mock_connection):
    """평균 실행 시간 계산 테스트"""
    # When: 여러 번 트랜잭션 실행
    for i in range(3):
        with tx_manager.transaction() as cursor:
            cursor.execute("SELECT 1")

    # Then: average_duration 설정됨
    stats = tx_manager.get_statistics()
    assert stats['average_duration'] > 0


def test_transaction_statistics_update_timestamp(tx_manager, mock_connection):
    """통계 업데이트 시각 테스트"""
    # Given: 시작 시각
    before_time = datetime.now()

    # When: 트랜잭션 실행
    with tx_manager.transaction() as cursor:
        cursor.execute("SELECT 1")

    # Then: last_updated 업데이트됨
    stats = tx_manager.get_statistics()
    last_updated = datetime.fromisoformat(stats['last_updated'])
    assert last_updated >= before_time


def test_repr(tx_manager):
    """__repr__ 테스트"""
    # When: repr 호출
    repr_str = repr(tx_manager)

    # Then: 정보 포함
    assert 'TransactionManager' in repr_str
    assert 'total=0' in repr_str
    assert 'committed=0' in repr_str
    assert 'rolled_back=0' in repr_str
