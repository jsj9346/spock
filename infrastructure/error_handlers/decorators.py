"""
에러 처리 데코레이터 (Error Handling Decorators)

함수 및 메서드에 적용할 수 있는 에러 처리 데코레이터를 제공합니다.

Decorators:
    handle_errors: 일반적인 에러 처리
    handle_database_errors: 데이터베이스 에러 전용 처리
    handle_api_errors: API 에러 전용 처리
    ignore_errors: 에러 무시 (경고만 로깅)
    raise_on_error: 에러 발생 시 커스텀 예외로 변환

사용법:
    from infrastructure.error_handlers.decorators import handle_errors
    from infrastructure.exceptions import DatabaseException

    @handle_errors(exceptions=(DatabaseException,), log_errors=True)
    def fetch_ticker_data(ticker: str):
        # 데이터베이스 조회 로직
        pass
"""

from functools import wraps
from typing import Callable, Optional, Tuple, Type, Any
import logging
import time

from infrastructure.exceptions import SpockBaseException

logger = logging.getLogger(__name__)


def handle_errors(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    default_return: Any = None,
    log_errors: bool = True,
    reraise: bool = False,
    log_level: int = logging.ERROR
) -> Callable:
    """
    일반적인 에러 처리 데코레이터

    함수 실행 중 발생하는 예외를 처리하고, 선택적으로
    로깅 및 기본 반환값을 제공합니다.

    Args:
        exceptions: 처리할 예외 타입 튜플
        default_return: 에러 발생 시 반환할 기본값
        log_errors: 에러를 로그에 기록할지 여부
        reraise: 에러를 다시 발생시킬지 여부
        log_level: 로깅 레벨 (logging.ERROR, logging.WARNING 등)

    사용 예제:
        >>> @handle_errors(exceptions=(ValueError,), default_return=[], log_errors=True)
        ... def parse_data(data):
        ...     return [int(x) for x in data]
        >>> result = parse_data(['1', '2', 'invalid'])
        >>> # 에러 로깅 후 [] 반환

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_errors:
                    logger.log(
                        log_level,
                        f"Error in {func.__name__}: {type(e).__name__}: {str(e)}",
                        extra={
                            "function": func.__name__,
                            "function_args": str(args),
                            "function_kwargs": str(kwargs)
                        },
                        exc_info=True
                    )

                if reraise:
                    raise

                return default_return
        return wrapper
    return decorator


def handle_database_errors(
    default_return: Any = None,
    log_errors: bool = True,
    reraise: bool = True
) -> Callable:
    """
    데이터베이스 에러 전용 처리 데코레이터

    DatabaseException 및 하위 예외를 처리합니다.

    Args:
        default_return: 에러 발생 시 반환할 기본값
        log_errors: 에러를 로그에 기록할지 여부
        reraise: 에러를 다시 발생시킬지 여부 (기본: True)

    사용 예제:
        >>> @handle_database_errors(reraise=False, default_return=None)
        ... def get_ticker_info(ticker: str):
        ...     # 데이터베이스 조회
        ...     pass

    Returns:
        데코레이터 함수
    """
    from infrastructure.exceptions import DatabaseException

    return handle_errors(
        exceptions=(DatabaseException,),
        default_return=default_return,
        log_errors=log_errors,
        reraise=reraise,
        log_level=logging.ERROR
    )


def handle_api_errors(
    default_return: Any = None,
    log_errors: bool = True,
    reraise: bool = False
) -> Callable:
    """
    API 에러 전용 처리 데코레이터

    APIException 및 하위 예외를 처리합니다.

    Args:
        default_return: 에러 발생 시 반환할 기본값
        log_errors: 에러를 로그에 기록할지 여부
        reraise: 에러를 다시 발생시킬지 여부 (기본: False)

    사용 예제:
        >>> @handle_api_errors(reraise=False, default_return={})
        ... def fetch_market_data(ticker: str):
        ...     # API 호출
        ...     pass

    Returns:
        데코레이터 함수
    """
    from infrastructure.exceptions import APIException

    return handle_errors(
        exceptions=(APIException,),
        default_return=default_return,
        log_errors=log_errors,
        reraise=reraise,
        log_level=logging.WARNING
    )


def ignore_errors(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_level: int = logging.WARNING
) -> Callable:
    """
    에러 무시 데코레이터 (경고만 로깅)

    에러를 무시하고 None을 반환하되, 경고 로그만 남깁니다.
    치명적이지 않은 작업에 사용합니다.

    Args:
        exceptions: 무시할 예외 타입 튜플
        log_level: 로깅 레벨 (기본: WARNING)

    사용 예제:
        >>> @ignore_errors(exceptions=(ValueError,))
        ... def optional_operation():
        ...     # 선택적 작업
        ...     pass

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.log(
                    log_level,
                    f"Ignored error in {func.__name__}: {type(e).__name__}: {str(e)}",
                    extra={"function": func.__name__}
                )
                return None
        return wrapper
    return decorator


def raise_on_error(
    original_exceptions: Tuple[Type[Exception], ...],
    new_exception: Type[SpockBaseException],
    message_template: str = "Error in {func_name}: {original_error}"
) -> Callable:
    """
    에러 발생 시 커스텀 예외로 변환하는 데코레이터

    특정 예외를 잡아서 Spock 커스텀 예외로 변환하여 발생시킵니다.

    Args:
        original_exceptions: 잡을 원본 예외 타입 튜플
        new_exception: 발생시킬 새로운 예외 클래스
        message_template: 에러 메시지 템플릿

    사용 예제:
        >>> from infrastructure.exceptions import DatabaseException
        >>> import psycopg2
        >>>
        >>> @raise_on_error(
        ...     original_exceptions=(psycopg2.Error,),
        ...     new_exception=DatabaseException,
        ...     message_template="Database error in {func_name}: {original_error}"
        ... )
        ... def execute_query(query):
        ...     # psycopg2 쿼리 실행
        ...     pass

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except original_exceptions as e:
                message = message_template.format(
                    func_name=func.__name__,
                    original_error=str(e)
                )
                raise new_exception(
                    message,
                    details={
                        "function": func.__name__,
                        "original_exception_type": type(e).__name__
                    },
                    original_exception=e
                )
        return wrapper
    return decorator


def retry_on_error(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    log_retries: bool = True
) -> Callable:
    """
    에러 발생 시 재시도하는 데코레이터

    지수 백오프(exponential backoff)를 사용하여 재시도합니다.

    Args:
        exceptions: 재시도할 예외 타입 튜플
        max_retries: 최대 재시도 횟수
        initial_delay: 초기 대기 시간 (초)
        backoff_factor: 백오프 승수 (각 재시도마다 delay * backoff_factor)
        max_delay: 최대 대기 시간 (초)
        log_retries: 재시도 시 로그 기록 여부

    사용 예제:
        >>> from infrastructure.exceptions import APIException
        >>>
        >>> @retry_on_error(
        ...     exceptions=(APIException,),
        ...     max_retries=3,
        ...     initial_delay=1.0,
        ...     backoff_factor=2.0
        ... )
        ... def call_api():
        ...     # API 호출 로직
        ...     pass

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        if log_retries:
                            logger.error(
                                f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                            )
                        raise

                    if log_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )

                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

        return wrapper
    return decorator


def measure_time(
    log_level: int = logging.DEBUG,
    threshold_seconds: Optional[float] = None
) -> Callable:
    """
    함수 실행 시간을 측정하고 로깅하는 데코레이터

    Args:
        log_level: 로깅 레벨
        threshold_seconds: 이 시간을 초과하면 WARNING으로 로깅

    사용 예제:
        >>> @measure_time(threshold_seconds=1.0)
        ... def slow_operation():
        ...     # 시간이 오래 걸리는 작업
        ...     pass

    Returns:
        데코레이터 함수
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                level = log_level

                if threshold_seconds and elapsed > threshold_seconds:
                    level = logging.WARNING

                logger.log(
                    level,
                    f"{func.__name__} took {elapsed:.3f}s to complete",
                    extra={"function": func.__name__, "elapsed_seconds": elapsed}
                )
        return wrapper
    return decorator


def validate_return_type(expected_type: Type) -> Callable:
    """
    함수 반환 타입을 검증하는 데코레이터

    Args:
        expected_type: 기대하는 반환 타입

    사용 예제:
        >>> @validate_return_type(expected_type=list)
        ... def get_tickers():
        ...     return ['AAPL', 'GOOGL']

    Returns:
        데코레이터 함수
    """
    from infrastructure.exceptions import ValidationException

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            if result is not None and not isinstance(result, expected_type):
                raise ValidationException(
                    f"Function {func.__name__} returned {type(result).__name__}, "
                    f"expected {expected_type.__name__}",
                    details={
                        "function": func.__name__,
                        "expected_type": expected_type.__name__,
                        "actual_type": type(result).__name__
                    }
                )

            return result
        return wrapper
    return decorator
