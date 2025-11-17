"""
검증 관련 예외 클래스 (Validation Exception Classes)

데이터 검증, 설정 검증, 입력 유효성 검사 중 발생하는
에러를 처리하기 위한 예외 클래스를 제공합니다.

Classes:
    ValidationException: 검증 관련 예외의 기본 클래스
    InvalidInputError: 유효하지 않은 입력
    InvalidDateRangeError: 유효하지 않은 날짜 범위
    InvalidTickerError: 유효하지 않은 ticker
    InvalidRegionError: 유효하지 않은 region
    MissingRequiredParameter: 필수 파라미터 누락
    InvalidParameterType: 유효하지 않은 파라미터 타입
    ValueOutOfRange: 값 범위 초과

사용법:
    from infrastructure.exceptions import InvalidTickerError

    if not ticker.isalnum():
        raise InvalidTickerError(
            f"Invalid ticker format: {ticker}",
            details={"ticker": ticker, "expected": "alphanumeric"}
        )
"""

from typing import Optional, Dict, Any, List
from .base import SpockBaseException


class ValidationException(SpockBaseException):
    """
    검증 관련 예외의 기본 클래스

    데이터 유효성 검사, 설정 검증 등 모든 검증 에러는
    이 클래스를 상속해야 합니다.
    """
    error_code = "VALIDATION_ERROR"


# ============================================================================
# Input Validation Exceptions (입력 검증 관련 예외)
# ============================================================================

class InvalidInputError(ValidationException):
    """
    유효하지 않은 입력

    사용자 입력 또는 API 파라미터가 유효하지 않을 때 발생합니다.

    사용 예제:
        >>> if not ticker:
        ...     raise InvalidInputError(
        ...         "Ticker cannot be empty",
        ...         details={"parameter": "ticker"}
        ...     )
    """
    error_code = "INVALID_INPUT"


class MissingRequiredParameter(ValidationException):
    """
    필수 파라미터 누락

    필수 파라미터가 제공되지 않았을 때 발생합니다.

    사용 예제:
        >>> required = ['ticker', 'region', 'start_date']
        ... missing = [p for p in required if p not in params]
        ... if missing:
        ...     raise MissingRequiredParameter(
        ...         f"Missing required parameters: {missing}",
        ...         details={"missing": missing, "required": required}
        ...     )
    """
    error_code = "MISSING_REQUIRED_PARAMETER"


class InvalidParameterType(ValidationException):
    """
    유효하지 않은 파라미터 타입

    파라미터의 타입이 기대한 것과 다를 때 발생합니다.

    사용 예제:
        >>> if not isinstance(limit, int):
        ...     raise InvalidParameterType(
        ...         f"Parameter 'limit' must be int, got {type(limit).__name__}",
        ...         details={
        ...             "parameter": "limit",
        ...             "expected_type": "int",
        ...             "actual_type": type(limit).__name__
        ...         }
        ...     )
    """
    error_code = "INVALID_PARAMETER_TYPE"


class ValueOutOfRange(ValidationException):
    """
    값 범위 초과

    파라미터 값이 허용된 범위를 벗어났을 때 발생합니다.

    사용 예제:
        >>> if not (1 <= batch_size <= 1000):
        ...     raise ValueOutOfRange(
        ...         f"batch_size must be between 1 and 1000, got {batch_size}",
        ...         details={
        ...             "parameter": "batch_size",
        ...             "value": batch_size,
        ...             "min": 1,
        ...             "max": 1000
        ...         }
        ...     )
    """
    error_code = "VALUE_OUT_OF_RANGE"


# ============================================================================
# Date Validation Exceptions (날짜 검증 관련 예외)
# ============================================================================

class InvalidDateError(ValidationException):
    """
    유효하지 않은 날짜

    날짜 형식이 잘못되었거나 유효하지 않을 때 발생합니다.

    사용 예제:
        >>> try:
        ...     date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        ... except ValueError:
        ...     raise InvalidDateError(
        ...         f"Invalid date format: {date_str}",
        ...         details={"date": date_str, "expected_format": "YYYY-MM-DD"}
        ...     )
    """
    error_code = "INVALID_DATE"


class InvalidDateRangeError(ValidationException):
    """
    유효하지 않은 날짜 범위

    시작일이 종료일보다 늦거나, 날짜 범위가 너무 클 때 발생합니다.

    사용 예제:
        >>> if start_date > end_date:
        ...     raise InvalidDateRangeError(
        ...         f"Start date must be before end date",
        ...         details={"start_date": start_date, "end_date": end_date}
        ...     )
    """
    error_code = "INVALID_DATE_RANGE"


class FutureDateNotAllowed(InvalidDateError):
    """
    미래 날짜 불가

    미래 날짜가 허용되지 않는 컨텍스트에서 미래 날짜를 사용했을 때 발생합니다.
    """
    error_code = "FUTURE_DATE_NOT_ALLOWED"


# ============================================================================
# Ticker Validation Exceptions (Ticker 검증 관련 예외)
# ============================================================================

class InvalidTickerError(ValidationException):
    """
    유효하지 않은 ticker

    ticker 형식이 올바르지 않을 때 발생합니다.

    사용 예제:
        >>> if not ticker.isalnum():
        ...     raise InvalidTickerError(
        ...         f"Ticker must be alphanumeric: {ticker}",
        ...         details={"ticker": ticker}
        ...     )
    """
    error_code = "INVALID_TICKER"


class TickerNotFoundError(InvalidTickerError):
    """
    Ticker 없음

    데이터베이스에 ticker가 존재하지 않을 때 발생합니다.
    """
    error_code = "TICKER_NOT_FOUND"


class InactiveTickerError(InvalidTickerError):
    """
    비활성 Ticker

    상장폐지되었거나 비활성 상태의 ticker를 사용하려 할 때 발생합니다.
    """
    error_code = "INACTIVE_TICKER"


# ============================================================================
# Region Validation Exceptions (Region 검증 관련 예외)
# ============================================================================

class InvalidRegionError(ValidationException):
    """
    유효하지 않은 region

    지원하지 않는 region을 사용했을 때 발생합니다.

    사용 예제:
        >>> valid_regions = ['KR', 'US', 'JP', 'HK', 'CN', 'VN']
        ... if region not in valid_regions:
        ...     raise InvalidRegionError(
        ...         f"Unsupported region: {region}",
        ...         details={
        ...             "region": region,
        ...             "supported_regions": valid_regions
        ...         }
        ...     )
    """
    error_code = "INVALID_REGION"


# ============================================================================
# Configuration Validation Exceptions (설정 검증 관련 예외)
# ============================================================================

class ConfigurationValidationError(ValidationException):
    """
    설정 검증 에러

    설정 파일 또는 설정 값이 유효하지 않을 때 발생합니다.

    사용 예제:
        >>> if config.max_workers < 1 or config.max_workers > 16:
        ...     raise ConfigurationValidationError(
        ...         f"max_workers must be between 1 and 16",
        ...         details={"max_workers": config.max_workers}
        ...     )
    """
    error_code = "CONFIG_VALIDATION_ERROR"


class InvalidConfigFormat(ConfigurationValidationError):
    """
    유효하지 않은 설정 형식

    설정 파일의 형식(YAML, JSON 등)이 잘못되었을 때 발생합니다.
    """
    error_code = "INVALID_CONFIG_FORMAT"


class MissingConfigParameter(ConfigurationValidationError):
    """
    설정 파라미터 누락

    필수 설정 파라미터가 설정 파일에 없을 때 발생합니다.
    """
    error_code = "MISSING_CONFIG_PARAMETER"


# ============================================================================
# Data Validation Exceptions (데이터 검증 관련 예외)
# ============================================================================

class DataValidationError(ValidationException):
    """
    데이터 검증 에러

    데이터베이스 또는 API에서 가져온 데이터가 유효하지 않을 때 발생합니다.
    """
    error_code = "DATA_VALIDATION_ERROR"


class EmptyDataError(DataValidationError):
    """
    빈 데이터

    데이터가 비어있거나 레코드가 없을 때 발생합니다.

    사용 예제:
        >>> if df.empty:
        ...     raise EmptyDataError(
        ...         "No data returned for query",
        ...         details={"query": query}
        ...     )
    """
    error_code = "EMPTY_DATA"


class IncompleteDataError(DataValidationError):
    """
    불완전한 데이터

    필수 컬럼이 누락되었거나 데이터가 불완전할 때 발생합니다.

    사용 예제:
        >>> required_columns = ['ticker', 'date', 'close']
        ... missing = [c for c in required_columns if c not in df.columns]
        ... if missing:
        ...     raise IncompleteDataError(
        ...         f"Missing required columns: {missing}",
        ...         details={"missing": missing, "required": required_columns}
        ...     )
    """
    error_code = "INCOMPLETE_DATA"


class DuplicateDataError(DataValidationError):
    """
    중복 데이터

    중복되지 말아야 할 데이터가 중복되었을 때 발생합니다.
    """
    error_code = "DUPLICATE_DATA"


class InvalidDataFormat(DataValidationError):
    """
    유효하지 않은 데이터 형식

    데이터의 형식이 기대한 것과 다를 때 발생합니다.
    """
    error_code = "INVALID_DATA_FORMAT"


# ============================================================================
# Business Logic Validation Exceptions (비즈니스 로직 검증 관련 예외)
# ============================================================================

class BusinessRuleViolation(ValidationException):
    """
    비즈니스 규칙 위반

    비즈니스 로직 규칙을 위반했을 때 발생합니다.

    사용 예제:
        >>> if ticker_count > 10000:
        ...     raise BusinessRuleViolation(
        ...         "Cannot process more than 10,000 tickers at once",
        ...         details={"ticker_count": ticker_count, "max_allowed": 10000}
        ...     )
    """
    error_code = "BUSINESS_RULE_VIOLATION"


class InsufficientDataError(ValidationException):
    """
    데이터 부족

    분석 또는 계산에 필요한 최소 데이터가 부족할 때 발생합니다.

    사용 예제:
        >>> if len(prices) < 20:
        ...     raise InsufficientDataError(
        ...         "Need at least 20 data points for MA20 calculation",
        ...         details={"available": len(prices), "required": 20}
        ...     )
    """
    error_code = "INSUFFICIENT_DATA"


class ConstraintViolation(ValidationException):
    """
    제약 조건 위반

    시스템 제약 조건을 위반했을 때 발생합니다.
    """
    error_code = "CONSTRAINT_VIOLATION"
