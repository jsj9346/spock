"""
API 관련 예외 클래스 (API Exception Classes)

외부 API 호출(KIS, yfinance, DART 등) 중 발생하는
에러를 처리하기 위한 예외 클래스를 제공합니다.

Classes:
    APIException: API 관련 예외의 기본 클래스
    RateLimitExceeded: API 요청 한도 초과
    AuthenticationFailed: 인증 실패
    APITimeout: API 타임아웃
    InvalidAPIResponse: 유효하지 않은 API 응답
    ResourceNotFound: 리소스 없음 (404)
    ServerError: 서버 에러 (5xx)

사용법:
    from infrastructure.exceptions import RateLimitExceeded

    if response.status_code == 429:
        raise RateLimitExceeded(
            "API rate limit exceeded",
            details={"api": "KIS", "retry_after": retry_after}
        )
"""

from typing import Optional, Dict, Any
from .base import SpockBaseException


class APIException(SpockBaseException):
    """
    API 호출 중 발생하는 모든 에러의 기본 클래스

    KIS, yfinance, DART 등 외부 API 관련 에러는
    이 클래스를 상속해야 합니다.
    """
    error_code = "API_ERROR"


# ============================================================================
# Rate Limit Exceptions (요청 한도 관련 예외)
# ============================================================================

class RateLimitExceeded(APIException):
    """
    API 요청 한도 초과

    API 제공자의 요청 한도를 초과했을 때 발생합니다.
    재시도 전 적절한 대기 시간이 필요합니다.

    사용 예제:
        >>> if response.status_code == 429:
        ...     retry_after = response.headers.get('Retry-After', 60)
        ...     raise RateLimitExceeded(
        ...         f"API rate limit exceeded for {api_name}",
        ...         details={
        ...             "api": api_name,
        ...             "retry_after": retry_after,
        ...             "limit": rate_limit
        ...         }
        ...     )
    """
    error_code = "API_RATE_LIMIT_EXCEEDED"


class QuotaExceeded(APIException):
    """
    API 할당량 초과

    일일/월간 할당량을 초과했을 때 발생합니다.
    """
    error_code = "API_QUOTA_EXCEEDED"


# ============================================================================
# Authentication Exceptions (인증 관련 예외)
# ============================================================================

class AuthenticationFailed(APIException):
    """
    API 인증 실패

    API 키, 토큰, 자격 증명이 유효하지 않을 때 발생합니다.

    사용 예제:
        >>> if response.status_code == 401:
        ...     raise AuthenticationFailed(
        ...         f"API authentication failed for {api_name}",
        ...         details={"api": api_name, "status_code": 401}
        ...     )
    """
    error_code = "API_AUTH_FAILED"


class TokenExpired(AuthenticationFailed):
    """
    토큰 만료

    액세스 토큰이 만료되었을 때 발생합니다.
    토큰 갱신이 필요합니다.

    사용 예제:
        >>> if 'token_expired' in response.json():
        ...     raise TokenExpired(
        ...         "Access token expired",
        ...         details={"api": "KIS", "issued_at": issued_at}
        ...     )
    """
    error_code = "API_TOKEN_EXPIRED"


class InvalidAPIKey(AuthenticationFailed):
    """
    유효하지 않은 API 키

    제공된 API 키가 유효하지 않을 때 발생합니다.
    """
    error_code = "API_INVALID_KEY"


class PermissionDenied(AuthenticationFailed):
    """
    권한 거부

    인증은 성공했지만 요청한 리소스에 대한 권한이 없을 때 발생합니다.
    """
    error_code = "API_PERMISSION_DENIED"


# ============================================================================
# Request Exceptions (요청 관련 예외)
# ============================================================================

class APITimeout(APIException):
    """
    API 타임아웃

    API 요청이 지정된 타임아웃 시간을 초과했을 때 발생합니다.

    사용 예제:
        >>> try:
        ...     response = requests.get(url, timeout=timeout)
        ... except requests.Timeout:
        ...     raise APITimeout(
        ...         f"API request timed out after {timeout}s",
        ...         details={"url": url, "timeout": timeout}
        ...     )
    """
    error_code = "API_TIMEOUT"


class ConnectionError(APIException):
    """
    API 연결 실패

    네트워크 문제로 API에 연결할 수 없을 때 발생합니다.
    """
    error_code = "API_CONNECTION_ERROR"


class InvalidRequest(APIException):
    """
    유효하지 않은 요청

    API 요청 파라미터가 잘못되었을 때 발생합니다.
    """
    error_code = "API_INVALID_REQUEST"


# ============================================================================
# Response Exceptions (응답 관련 예외)
# ============================================================================

class InvalidAPIResponse(APIException):
    """
    유효하지 않은 API 응답

    API 응답 형식이 예상과 다르거나 파싱할 수 없을 때 발생합니다.

    사용 예제:
        >>> try:
        ...     data = response.json()
        ... except ValueError:
        ...     raise InvalidAPIResponse(
        ...         "Unable to parse API response",
        ...         details={"response_text": response.text[:200]}
        ...     )
    """
    error_code = "API_INVALID_RESPONSE"


class MissingRequiredField(InvalidAPIResponse):
    """
    필수 필드 누락

    API 응답에 필수 필드가 없을 때 발생합니다.

    사용 예제:
        >>> if 'ticker' not in data:
        ...     raise MissingRequiredField(
        ...         "Required field 'ticker' missing in API response",
        ...         details={"available_fields": list(data.keys())}
        ...     )
    """
    error_code = "API_MISSING_FIELD"


class UnexpectedDataFormat(InvalidAPIResponse):
    """
    예상하지 못한 데이터 형식

    API 응답 데이터의 형식이 예상과 다를 때 발생합니다.
    """
    error_code = "API_UNEXPECTED_FORMAT"


# ============================================================================
# HTTP Status Code Exceptions (HTTP 상태 코드 관련 예외)
# ============================================================================

class ResourceNotFound(APIException):
    """
    리소스 없음 (404)

    요청한 리소스를 찾을 수 없을 때 발생합니다.

    사용 예제:
        >>> if response.status_code == 404:
        ...     raise ResourceNotFound(
        ...         f"Resource not found: {ticker}",
        ...         details={"ticker": ticker, "api": api_name}
        ...     )
    """
    error_code = "API_RESOURCE_NOT_FOUND"


class ServerError(APIException):
    """
    서버 에러 (5xx)

    API 서버 측 에러가 발생했을 때 사용합니다.

    사용 예제:
        >>> if 500 <= response.status_code < 600:
        ...     raise ServerError(
        ...         f"API server error: {response.status_code}",
        ...         details={
        ...             "status_code": response.status_code,
        ...             "api": api_name
        ...         }
        ...     )
    """
    error_code = "API_SERVER_ERROR"


class ServiceUnavailable(ServerError):
    """
    서비스 이용 불가 (503)

    API 서비스가 일시적으로 이용 불가능할 때 발생합니다.
    """
    error_code = "API_SERVICE_UNAVAILABLE"


# ============================================================================
# API-Specific Exceptions (특정 API 관련 예외)
# ============================================================================

class KISAPIException(APIException):
    """한국투자증권 API 관련 예외"""
    error_code = "KIS_API_ERROR"


class KISTokenGenerationFailed(KISAPIException):
    """
    KIS 토큰 생성 실패

    한국투자증권 API 토큰 생성에 실패했을 때 발생합니다.

    사용 예제:
        >>> if 'access_token' not in response:
        ...     raise KISTokenGenerationFailed(
        ...         "Failed to generate KIS access token",
        ...         details={"response": response}
        ...     )
    """
    error_code = "KIS_TOKEN_GENERATION_FAILED"


class KISMarketClosed(KISAPIException):
    """
    KIS 시장 마감

    거래 시간 외에 실시간 데이터를 요청했을 때 발생합니다.
    """
    error_code = "KIS_MARKET_CLOSED"


class DARTAPIException(APIException):
    """DART(전자공시) API 관련 예외"""
    error_code = "DART_API_ERROR"


class DARTRateLimitExceeded(DARTAPIException, RateLimitExceeded):
    """
    DART API 요청 한도 초과

    DART API의 일일 10,000건 한도를 초과했을 때 발생합니다.
    """
    error_code = "DART_RATE_LIMIT_EXCEEDED"


class YFinanceException(APIException):
    """yfinance API 관련 예외"""
    error_code = "YFINANCE_ERROR"


class YFinanceDataNotAvailable(YFinanceException):
    """
    yfinance 데이터 없음

    요청한 ticker의 데이터를 yfinance에서 찾을 수 없을 때 발생합니다.
    """
    error_code = "YFINANCE_DATA_NOT_AVAILABLE"


# ============================================================================
# Market Data Exceptions (시장 데이터 관련 예외)
# ============================================================================

class MarketDataException(APIException):
    """시장 데이터 관련 예외"""
    error_code = "MARKET_DATA_ERROR"


class NoDataAvailable(MarketDataException):
    """
    데이터 없음

    요청한 기간/ticker에 대한 데이터가 없을 때 발생합니다.

    사용 예제:
        >>> if df.empty:
        ...     raise NoDataAvailable(
        ...         f"No data available for {ticker}",
        ...         details={
        ...             "ticker": ticker,
        ...             "start_date": start_date,
        ...             "end_date": end_date
        ...         }
        ...     )
    """
    error_code = "NO_DATA_AVAILABLE"


class DataQualityIssue(MarketDataException):
    """
    데이터 품질 문제

    데이터가 존재하지만 품질 문제가 있을 때 발생합니다.
    (예: 이상치, 누락값 과다, 비정상 가격 변동 등)
    """
    error_code = "DATA_QUALITY_ISSUE"


class StalDataError(MarketDataException):
    """
    오래된 데이터

    데이터가 너무 오래되어 사용할 수 없을 때 발생합니다.
    """
    error_code = "STALE_DATA_ERROR"
