"""
기본 예외 클래스 (Base Exception Classes)

Spock 플랫폼의 모든 커스텀 예외를 위한 기본 클래스를 제공합니다.

Classes:
    SpockBaseException: 모든 Spock 예외의 기본 클래스
    SpockWarning: 경고 수준의 예외

사용법:
    from infrastructure.exceptions import SpockBaseException

    class MyCustomException(SpockBaseException):
        error_code = "MY_ERROR"

    try:
        raise MyCustomException("Something went wrong", details={"key": "value"})
    except SpockBaseException as e:
        print(e.to_dict())
"""

from typing import Dict, Optional, Any
import traceback
import logging

logger = logging.getLogger(__name__)


class SpockBaseException(Exception):
    """
    모든 Spock 커스텀 예외의 기본 클래스

    모든 Spock 예외는 이 클래스를 상속해야 하며, 에러 코드와
    구조화된 컨텍스트 정보를 제공합니다.

    Attributes:
        error_code (str): 고유한 에러 코드 (예: "DB_CONNECTION_FAILED")
        message (str): 사람이 읽을 수 있는 에러 메시지
        details (Dict): 에러 컨텍스트 정보 (선택사항)
        original_exception (Optional[Exception]): 원본 예외 (체이닝용)
        traceback_str (str): 스택 트레이스 문자열

    사용 예제:
        >>> try:
        ...     raise SpockBaseException(
        ...         "Database connection failed",
        ...         details={"host": "localhost", "port": 5432}
        ...     )
        ... except SpockBaseException as e:
        ...     print(e.to_dict())
        {'error_code': 'SPOCK_ERROR', 'message': 'Database connection failed', ...}
    """

    # 기본 에러 코드 (서브클래스에서 오버라이드)
    error_code: str = "SPOCK_ERROR"

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Args:
            message: 사람이 읽을 수 있는 에러 메시지
            details: 에러 컨텍스트 정보 (딕셔너리)
            original_exception: 원본 예외 (체이닝 시)
        """
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        self.traceback_str = traceback.format_exc()

        # Exception 초기화
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        예외를 딕셔너리로 직렬화

        로깅, API 응답, 에러 추적 시스템에 사용됩니다.

        Returns:
            Dict containing error information:
                - error_code: 에러 코드
                - message: 에러 메시지
                - details: 컨텍스트 정보
                - traceback: 스택 트레이스 (디버그 모드)
        """
        result = {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }

        # 원본 예외 정보 포함
        if self.original_exception:
            result["original_error"] = {
                "type": type(self.original_exception).__name__,
                "message": str(self.original_exception)
            }

        return result

    def log_error(self, logger_instance: Optional[logging.Logger] = None):
        """
        에러를 로거를 통해 기록

        Args:
            logger_instance: 사용할 로거 (None이면 기본 로거 사용)
        """
        log = logger_instance or logger
        log.error(
            f"{self.error_code}: {self.message}",
            extra={"error_details": self.details}
        )

        # 원본 예외가 있으면 함께 기록
        if self.original_exception:
            log.error(
                f"Original exception: {type(self.original_exception).__name__}: "
                f"{str(self.original_exception)}"
            )

    def __str__(self) -> str:
        """문자열 표현"""
        base = f"[{self.error_code}] {self.message}"
        if self.details:
            base += f" | Details: {self.details}"
        return base

    def __repr__(self) -> str:
        """개발자용 표현"""
        return (
            f"{self.__class__.__name__}("
            f"error_code='{self.error_code}', "
            f"message='{self.message}', "
            f"details={self.details})"
        )


class SpockWarning(SpockBaseException):
    """
    경고 수준의 예외

    치명적이지 않지만 주의가 필요한 상황을 나타냅니다.
    프로그램 실행은 계속되지만 로그에 기록됩니다.

    사용 예제:
        >>> if ticker_count > 1000:
        ...     raise SpockWarning(
        ...         "Large ticker count may impact performance",
        ...         details={"ticker_count": ticker_count}
        ...     )
    """
    error_code = "SPOCK_WARNING"

    def log_error(self, logger_instance: Optional[logging.Logger] = None):
        """경고는 WARNING 레벨로 로깅"""
        log = logger_instance or logger
        log.warning(
            f"{self.error_code}: {self.message}",
            extra={"warning_details": self.details}
        )


class SpockConfigurationError(SpockBaseException):
    """
    설정 관련 에러

    잘못된 설정 파일, 누락된 설정 값, 또는 유효하지 않은
    설정 파라미터를 나타냅니다.
    """
    error_code = "CONFIG_ERROR"


class SpockNotImplementedError(SpockBaseException):
    """
    미구현 기능 에러

    아직 구현되지 않은 기능이나 추상 메서드 호출 시 발생합니다.
    """
    error_code = "NOT_IMPLEMENTED"


class InfrastructureException(SpockBaseException):
    """
    인프라 레이어 에러

    데이터베이스 연결, DI Container, 설정 관리 등
    인프라 레이어에서 발생하는 일반적인 에러입니다.
    """
    error_code = "INFRASTRUCTURE_ERROR"
