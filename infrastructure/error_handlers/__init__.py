"""
Error Handlers Module

에러 처리 데코레이터 및 컨텍스트 매니저를 제공합니다.

Modules:
    decorators: 에러 처리 데코레이터
    context_managers: 에러 처리 컨텍스트 매니저

사용법:
    from infrastructure.error_handlers import (
        handle_errors,
        handle_database_errors,
        retry_on_error,
        suppress_errors,
        log_errors
    )

    @handle_database_errors(reraise=True)
    def fetch_data(ticker: str):
        # 데이터베이스 조회
        pass

    with suppress_errors(ValueError):
        # ValueError 무시
        pass
"""

from .decorators import (
    handle_errors,
    handle_database_errors,
    handle_api_errors,
    ignore_errors,
    raise_on_error,
    retry_on_error,
    measure_time,
    validate_return_type,
)

from .context_managers import (
    suppress_errors,
    log_errors,
    handle_errors_gracefully,
    transaction_scope,
)

__all__ = [
    # Decorators
    "handle_errors",
    "handle_database_errors",
    "handle_api_errors",
    "ignore_errors",
    "raise_on_error",
    "retry_on_error",
    "measure_time",
    "validate_return_type",

    # Context Managers
    "suppress_errors",
    "log_errors",
    "handle_errors_gracefully",
    "transaction_scope",
]
