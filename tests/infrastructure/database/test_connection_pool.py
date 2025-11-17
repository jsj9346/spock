"""
ConnectionPoolManager 단위 테스트

Tests:
    - 기본 연결 관리 (8 tests)
    - 건강 상태 체크 (6 tests)
    - 통계 추적 (5 tests)
    - 컨텍스트 관리 (4 tests)
    - 동시성 (4 tests)

Total: 27 tests
"""

import pytest
import psycopg2
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import threading
import time

from infrastructure.database.pool_manager import ConnectionPoolManager, PoolStatistics
from infrastructure.exceptions import (
    ConnectionPoolExhausted,
    ConnectionTimeout,
    ConnectionNotInitialized,
    DatabaseException
)


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def mock_pool():
    """Mock psycopg2 connection pool"""
    with patch('psycopg2.pool.ThreadedConnectionPool') as mock:
        yield mock


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
    return conn


@pytest.fixture
def pool_manager(mock_pool, mock_connection):
    """ConnectionPoolManager 인스턴스 생성"""
    # Mock pool이 연결을 반환하도록 설정
    pool_instance = Mock()
    pool_instance.getconn = Mock(return_value=mock_connection)
    pool_instance.putconn = Mock()
    pool_instance.closeall = Mock()
    mock_pool.return_value = pool_instance

    manager = ConnectionPoolManager(
        host='localhost',
        port=5432,
        database='test_db',
        user='test_user',
        password='test_pass',
        min_conn=5,
        max_conn=15
    )

    return manager


# ========================================
# 1. Basic Connection Management (8 tests)
# ========================================

def test_pool_initialization(mock_pool):
    """연결 풀 초기화 테스트"""
    # When: ConnectionPoolManager 생성
    manager = ConnectionPoolManager(
        host='localhost',
        port=5432,
        database='test_db',
        user='test_user',
        password='test_pass',
        min_conn=5,
        max_conn=15
    )

    # Then: Pool이 올바른 파라미터로 생성됨
    mock_pool.assert_called_once()
    call_kwargs = mock_pool.call_args[1]
    assert call_kwargs['host'] == 'localhost'
    assert call_kwargs['port'] == 5432
    assert call_kwargs['database'] == 'test_db'
    assert call_kwargs['user'] == 'test_user'
    assert call_kwargs['password'] == 'test_pass'

    # Pool size 확인
    assert manager.min_conn == 5
    assert manager.max_conn == 15


def test_pool_initialization_with_defaults(mock_pool):
    """기본값으로 연결 풀 초기화 테스트"""
    # When: 최소 파라미터로 생성
    with patch.dict('os.environ', {
        'POSTGRES_HOST': 'default_host',
        'POSTGRES_PORT': '5433',
        'POSTGRES_DB': 'default_db',
        'POSTGRES_USER': 'default_user',
        'POSTGRES_PASSWORD': 'default_pass'
    }):
        manager = ConnectionPoolManager()

    # Then: 환경변수 또는 기본값 사용
    assert manager.host == 'default_host'
    assert manager.port == 5433
    assert manager.database == 'default_db'
    assert manager.user == 'default_user'
    assert manager.password == 'default_pass'
    assert manager.min_conn == 10  # 기본값
    assert manager.max_conn == 30  # 기본값


def test_pool_initialization_failure(mock_pool):
    """연결 풀 초기화 실패 테스트"""
    # Given: Pool 생성이 실패하도록 설정
    mock_pool.side_effect = psycopg2.OperationalError("Connection refused")

    # When/Then: DatabaseException 발생
    with pytest.raises(DatabaseException) as exc_info:
        ConnectionPoolManager(
            host='invalid_host',
            database='test_db'
        )

    assert "Failed to initialize connection pool" in str(exc_info.value)


def test_connection_acquisition(pool_manager):
    """연결 획득 테스트"""
    # When: 연결 획득
    with pool_manager.get_connection() as conn:
        # Then: 연결 객체 반환
        assert conn is not None

    # Then: 통계 업데이트 확인
    stats = pool_manager.get_statistics()
    assert stats['total_requests'] == 1
    assert stats['successful_requests'] == 1
    assert stats['failed_requests'] == 0


def test_connection_return(pool_manager):
    """연결 반환 테스트"""
    # When: 연결 획득 후 자동 반환
    with pool_manager.get_connection() as conn:
        pass

    # Then: putconn 호출됨
    pool_manager._pool.putconn.assert_called_once()

    # Then: idle_connections 증가
    stats = pool_manager.get_statistics()
    assert stats['idle_connections'] == 1


def test_connection_reuse(pool_manager):
    """연결 재사용 테스트"""
    # When: 여러 번 연결 획득
    for i in range(3):
        with pool_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

    # Then: 모든 요청이 성공
    stats = pool_manager.get_statistics()
    assert stats['total_requests'] == 3
    assert stats['successful_requests'] == 3
    assert stats['success_rate'] == 100.0


def test_connection_pool_not_initialized():
    """연결 풀 미초기화 시 예외 테스트"""
    # Given: Pool이 None인 manager
    manager = ConnectionPoolManager.__new__(ConnectionPoolManager)
    manager._pool = None
    manager.host = 'localhost'
    manager.database = 'test_db'
    manager.statistics = PoolStatistics()

    # When/Then: ConnectionNotInitialized 발생
    with pytest.raises(ConnectionNotInitialized) as exc_info:
        with manager.get_connection() as conn:
            pass

    assert "not initialized" in str(exc_info.value)


def test_connection_pool_exhausted(pool_manager):
    """연결 풀 고갈 테스트"""
    # Given: getconn이 None 반환하도록 설정
    pool_manager._pool.getconn.return_value = None

    # When/Then: ConnectionPoolExhausted 발생
    with pytest.raises(ConnectionPoolExhausted) as exc_info:
        with pool_manager.get_connection() as conn:
            pass

    assert "Connection pool exhausted" in str(exc_info.value)
    # Note: ConnectionPoolExhausted는 psycopg2.Error가 아니므로
    # failed_requests가 증가하지 않음
    assert pool_manager.statistics.total_requests == 1


# ========================================
# 2. Health Check (6 tests)
# ========================================

def test_health_check_success(pool_manager, mock_connection):
    """Health check 성공 테스트"""
    # When: health_check 호출
    result = pool_manager.health_check()

    # Then: True 반환
    assert result is True

    # Then: SELECT 1 실행됨
    mock_connection.cursor().execute.assert_called_with("SELECT 1")


def test_health_check_connection_failure(pool_manager):
    """Health check 연결 실패 테스트"""
    # Given: getconn이 예외 발생하도록 설정
    pool_manager._pool.getconn.side_effect = psycopg2.OperationalError("Connection failed")

    # When: health_check 호출
    result = pool_manager.health_check()

    # Then: False 반환
    assert result is False


def test_health_check_query_failure(pool_manager, mock_connection):
    """Health check 쿼리 실패 테스트"""
    # Given: SELECT 1 실행이 실패하도록 설정
    mock_connection.cursor().execute.side_effect = psycopg2.DatabaseError("Query failed")

    # When: health_check 호출
    result = pool_manager.health_check()

    # Then: False 반환
    assert result is False


def test_health_check_cursor_failure(pool_manager, mock_connection):
    """Health check cursor 생성 실패 테스트"""
    # Given: cursor() 호출이 실패하도록 설정
    mock_connection.cursor.side_effect = psycopg2.InterfaceError("Cursor creation failed")

    # When: health_check 호출
    result = pool_manager.health_check()

    # Then: False 반환
    assert result is False


def test_health_check_timeout(pool_manager):
    """Health check 타임아웃 테스트"""
    # Given: getconn이 오래 걸리도록 설정 (타임아웃 시뮬레이션)
    def slow_getconn():
        time.sleep(0.1)
        raise psycopg2.OperationalError("Timeout")

    pool_manager._pool.getconn.side_effect = slow_getconn

    # When: health_check 호출
    result = pool_manager.health_check()

    # Then: False 반환
    assert result is False


def test_health_check_after_recovery(pool_manager, mock_connection):
    """Health check 복구 후 테스트"""
    # Given: 첫 번째 호출은 실패, 두 번째는 성공
    pool_manager._pool.getconn.side_effect = [
        psycopg2.OperationalError("Temporary failure"),
        mock_connection
    ]

    # When: 첫 번째 health_check (실패)
    result1 = pool_manager.health_check()
    assert result1 is False

    # When: 두 번째 health_check (성공)
    result2 = pool_manager.health_check()
    assert result2 is True


# ========================================
# 3. Statistics Tracking (5 tests)
# ========================================

def test_statistics_initialization(pool_manager):
    """통계 초기화 테스트"""
    # When: get_statistics 호출
    stats = pool_manager.get_statistics()

    # Then: 초기값 확인
    assert stats['min_connections'] == 5
    assert stats['max_connections'] == 15
    assert stats['active_connections'] == 0
    assert stats['idle_connections'] == 0
    assert stats['total_requests'] == 0
    assert stats['successful_requests'] == 0
    assert stats['failed_requests'] == 0
    assert stats['success_rate'] == 100.0  # 0/0 = 100%
    assert stats['utilization_rate'] == 0.0


def test_statistics_after_successful_connection(pool_manager):
    """성공적인 연결 후 통계 테스트"""
    # When: 연결 획득
    with pool_manager.get_connection() as conn:
        pass

    # When: 통계 확인
    stats = pool_manager.get_statistics()

    # Then: 통계 업데이트됨
    assert stats['total_requests'] == 1
    assert stats['successful_requests'] == 1
    assert stats['failed_requests'] == 0
    assert stats['success_rate'] == 100.0
    assert stats['idle_connections'] == 1


def test_statistics_after_failed_connection(pool_manager):
    """실패한 연결 후 통계 테스트"""
    # Given: getconn이 예외 발생하도록 설정
    pool_manager._pool.getconn.side_effect = psycopg2.OperationalError("Connection failed")

    # When: 연결 획득 시도
    with pytest.raises(ConnectionTimeout):
        with pool_manager.get_connection() as conn:
            pass

    # When: 통계 확인
    stats = pool_manager.get_statistics()

    # Then: 실패 통계 업데이트됨
    assert stats['total_requests'] == 1
    assert stats['successful_requests'] == 0
    assert stats['failed_requests'] == 1
    assert stats['success_rate'] == 0.0


def test_utilization_rate_calculation(pool_manager):
    """사용률 계산 테스트"""
    # Given: active_connections 설정
    pool_manager.statistics.active_connections = 10

    # When: 사용률 확인
    stats = pool_manager.get_statistics()

    # Then: 올바른 사용률 계산 (10/15 = 66.67%)
    assert abs(stats['utilization_rate'] - 66.67) < 0.01


def test_average_wait_time_calculation(pool_manager, mock_connection):
    """평균 대기 시간 계산 테스트"""
    # When: 여러 번 연결 획득 (대기 시간 누적)
    for i in range(3):
        with pool_manager.get_connection() as conn:
            pass

    # When: 통계 확인
    stats = pool_manager.get_statistics()

    # Then: average_wait_time이 설정됨
    assert stats['average_wait_time'] >= 0


# ========================================
# 4. Context Manager (4 tests)
# ========================================

def test_context_manager_normal_exit(pool_manager, mock_connection):
    """Context manager 정상 종료 테스트"""
    # When: Context manager 사용
    with pool_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")

    # Then: 연결이 자동 반환됨
    pool_manager._pool.putconn.assert_called_once_with(mock_connection)


def test_context_manager_exception_handling(pool_manager, mock_connection):
    """Context manager 예외 처리 테스트"""
    # When/Then: 예외 발생 시에도 연결 반환
    with pytest.raises(ValueError):
        with pool_manager.get_connection() as conn:
            raise ValueError("Test exception")

    # Then: 연결이 반환됨
    pool_manager._pool.putconn.assert_called_once_with(mock_connection)


def test_context_manager_connection_error_handling(pool_manager, mock_connection):
    """Context manager 연결 에러 처리 테스트"""
    # Given: putconn이 예외 발생하도록 설정
    pool_manager._pool.putconn.side_effect = Exception("Return failed")

    # When: Context manager 사용
    with pool_manager.get_connection() as conn:
        pass

    # Then: 예외가 발생해도 정상 종료 (에러 로깅만)
    # (finally 블록에서 예외를 catch하므로)


def test_context_manager_statistics_update(pool_manager):
    """Context manager 통계 업데이트 테스트"""
    # When: Context manager 사용
    before_time = datetime.now()

    with pool_manager.get_connection() as conn:
        pass

    # Then: last_updated가 업데이트됨
    stats = pool_manager.get_statistics()
    last_updated = datetime.fromisoformat(stats['last_updated'])
    assert last_updated >= before_time


# ========================================
# 5. Concurrency (4 tests)
# ========================================

def test_concurrent_connection_acquisition(pool_manager, mock_connection):
    """동시 연결 획득 테스트"""
    # Given: 여러 스레드에서 동시에 연결 획득
    results = []
    errors = []

    def acquire_connection():
        try:
            with pool_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                results.append(True)
        except Exception as e:
            errors.append(e)

    # When: 5개 스레드 동시 실행
    threads = [threading.Thread(target=acquire_connection) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Then: 모든 연결 획득 성공
    assert len(results) == 5
    assert len(errors) == 0


def test_thread_safety(pool_manager):
    """스레드 안전성 테스트"""
    # Given: 여러 스레드에서 통계 업데이트
    def update_stats():
        for _ in range(10):
            with pool_manager.get_connection() as conn:
                pass

    # When: 3개 스레드 동시 실행
    threads = [threading.Thread(target=update_stats) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Then: 통계가 정확히 업데이트됨
    stats = pool_manager.get_statistics()
    assert stats['total_requests'] == 30
    assert stats['successful_requests'] == 30


def test_pool_exhaustion_under_load(mock_pool, mock_connection):
    """부하 상황에서 풀 고갈 테스트"""
    # Given: 작은 풀 생성
    pool_instance = Mock()
    pool_instance.closeall = Mock()
    mock_pool.return_value = pool_instance

    manager = ConnectionPoolManager(
        host='localhost',
        database='test_db',
        min_conn=2,
        max_conn=3
    )

    # Given: 처음 3번은 성공, 4번째부터 None 반환 (고갈)
    pool_instance.getconn.side_effect = [
        mock_connection, mock_connection, mock_connection, None
    ]
    pool_instance.putconn = Mock()

    # When: 4번 연결 시도
    success_count = 0
    for i in range(4):
        try:
            with manager.get_connection() as conn:
                success_count += 1
        except ConnectionPoolExhausted:
            break

    # Then: 3번 성공, 4번째는 실패
    assert success_count == 3


def test_no_deadlock_on_error(pool_manager, mock_connection):
    """에러 발생 시 Deadlock 방지 테스트"""
    # Given: 첫 번째 연결은 쿼리 실패
    mock_connection.cursor().execute.side_effect = [
        psycopg2.DatabaseError("Query failed"),
        None,  # 두 번째는 성공
        None
    ]

    # When: 에러 발생 후에도 다음 연결 가능
    try:
        with pool_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
    except Exception:
        pass

    # Then: 다음 연결 획득 가능
    with pool_manager.get_connection() as conn:
        pass

    # Then: 통계 확인
    stats = pool_manager.get_statistics()
    assert stats['total_requests'] == 2


# ========================================
# Additional Tests
# ========================================

def test_close_all_connections(pool_manager):
    """모든 연결 종료 테스트"""
    # When: close_all_connections 호출
    pool_manager.close_all_connections()

    # Then: closeall 호출됨
    pool_manager._pool.closeall.assert_called_once()

    # Then: 통계 초기화
    stats = pool_manager.get_statistics()
    assert stats['active_connections'] == 0
    assert stats['idle_connections'] == 0


def test_repr(pool_manager):
    """__repr__ 테스트"""
    # When: repr 호출
    repr_str = repr(pool_manager)

    # Then: 정보 포함
    assert 'ConnectionPoolManager' in repr_str
    assert 'localhost' in repr_str
    assert 'test_db' in repr_str
    assert '5-15' in repr_str
