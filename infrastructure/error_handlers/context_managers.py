"""
에러 처리 컨텍스트 매니저 (Error Handling Context Managers)

with 문과 함께 사용할 수 있는 에러 처리 컨텍스트 매니저를 제공합니다.

Context Managers:
    suppress_errors: 에러를 무시하고 계속 진행
    log_errors: 에러를 로깅하고 전파
    handle_errors_gracefully: 에러를 처리하고 기본값 반환

사용법:
    from infrastructure.error_handlers.context_managers import suppress_errors

    with suppress_errors(ValueError):
        # ValueError가 발생해도 무시됨
        int('invalid')
"""

from contextlib import contextmanager
from typing import Type, Tuple, Optional, Any
import logging

from infrastructure.exceptions import SpockBaseException

logger = logging.getLogger(__name__)


@contextmanager
def suppress_errors(*exceptions: Type[Exception]):
    """
    지정된 예외를 무시하는 컨텍스트 매니저

    Args:
        *exceptions: 무시할 예외 타입들

    사용 예제:
        >>> with suppress_errors(ValueError, TypeError):
        ...     int('invalid')  # ValueError 무시됨
        ...     print("계속 실행됨")
    """
    try:
        yield
    except exceptions:
        pass


@contextmanager
def log_errors(
    *exceptions: Type[Exception],
    log_level: int = logging.ERROR,
    reraise: bool = True
):
    """
    에러를 로깅하는 컨텍스트 매니저

    Args:
        *exceptions: 로깅할 예외 타입들 (비어있으면 모든 예외)
        log_level: 로깅 레벨
        reraise: 에러를 다시 발생시킬지 여부

    사용 예제:
        >>> with log_errors(ValueError, log_level=logging.WARNING):
        ...     int('invalid')  # ValueError 로깅 후 재발생
    """
    exceptions_to_catch = exceptions if exceptions else (Exception,)

    try:
        yield
    except exceptions_to_catch as e:
        logger.log(
            log_level,
            f"Error occurred: {type(e).__name__}: {str(e)}",
            exc_info=True
        )
        if reraise:
            raise


@contextmanager
def handle_errors_gracefully(
    default_value: Any = None,
    *exceptions: Type[Exception],
    log_errors_flag: bool = True
):
    """
    에러를 우아하게 처리하고 기본값을 제공하는 컨텍스트 매니저

    Args:
        default_value: 에러 발생 시 반환할 기본값
        *exceptions: 처리할 예외 타입들
        log_errors_flag: 에러를 로깅할지 여부

    사용 예제:
        >>> with handle_errors_gracefully(default_value=[], ValueError):
        ...     result = int('invalid')
        >>> # result는 []가 됨

    Note:
        이 컨텍스트 매니저는 값을 반환하지 않으므로,
        반환값이 필요한 경우 외부 변수를 사용해야 합니다.
    """
    exceptions_to_catch = exceptions if exceptions else (Exception,)

    try:
        yield
    except exceptions_to_catch as e:
        if log_errors_flag:
            logger.error(
                f"Handled error gracefully: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
        return default_value


@contextmanager
def transaction_scope(
    connection,
    commit_on_success: bool = True,
    rollback_on_error: bool = True
):
    """
    데이터베이스 트랜잭션 스코프를 관리하는 컨텍스트 매니저

    Args:
        connection: 데이터베이스 연결 객체
        commit_on_success: 성공 시 자동 커밋 여부
        rollback_on_error: 에러 시 자동 롤백 여부

    사용 예제:
        >>> with transaction_scope(conn) as cursor:
        ...     cursor.execute("INSERT INTO tickers ...")
        ...     cursor.execute("UPDATE ticker_fundamentals ...")
        ...     # 자동 COMMIT (또는 에러 시 ROLLBACK)
    """
    from infrastructure.exceptions import TransactionException

    cursor = connection.cursor()

    try:
        yield cursor

        if commit_on_success:
            connection.commit()
            logger.debug("Transaction committed successfully")

    except Exception as e:
        if rollback_on_error:
            connection.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")

        raise TransactionException(
            f"Transaction failed: {str(e)}",
            details={"rollback_performed": rollback_on_error},
            original_exception=e
        )

    finally:
        cursor.close()
