# mcp_server/utils/errors.py
"""
Error handling for MCP server

Defines error hierarchy and JSON-serializable error responses.
Includes user-friendly message mapping for common error scenarios.
"""

from typing import Dict, Optional


# =============================================================================
# User-Friendly Error Message Mapping
# =============================================================================

FRIENDLY_ERROR_MESSAGES = {
    # TTM related errors
    "No TTM data available": {
        "message": "TTM 데이터가 아직 준비되지 않았습니다.",
        "hint": "ANNUAL 또는 QUARTERLY period_type을 사용해주세요.",
        "reason": "TTM(Trailing Twelve Months) 계산 배치가 아직 완전히 구현되지 않았습니다."
    },
    # Fundamentals related errors
    "No fundamental data available": {
        "message": "해당 종목의 재무 데이터를 찾을 수 없습니다.",
        "hint": "종목 코드를 확인하거나, 다른 기간(ANNUAL/QUARTERLY)을 시도해보세요.",
        "reason": "데이터베이스에 해당 종목의 재무 데이터가 존재하지 않습니다."
    },
    # OHLCV related errors
    "No OHLCV data available for requested tickers/dates": {
        "message": "요청한 기간의 주가 데이터를 찾을 수 없습니다.",
        "hint": "날짜 범위를 확인하거나, 휴장일이 포함되어 있는지 확인하세요.",
        "reason": "지정된 기간에 거래 데이터가 없거나, 종목 코드가 잘못되었을 수 있습니다."
    },
    # Cash flow related errors
    "Cash flow data not available": {
        "message": "현금흐름 데이터가 아직 수집되지 않았습니다.",
        "hint": "손익계산서 또는 재무상태표 데이터를 사용해주세요.",
        "reason": "DART 현금흐름표 파싱이 아직 구현되지 않았습니다."
    },
    # Screening related errors
    "No stocks match the screening criteria": {
        "message": "조건을 만족하는 종목이 없습니다.",
        "hint": "필터 조건을 완화해보세요 (예: PER < 20, PBR < 2).",
        "reason": "지정한 조건이 너무 엄격하거나, 해당 시장에 조건을 만족하는 종목이 없습니다."
    },
}


def get_friendly_error(original_message: str) -> Dict:
    """
    Get user-friendly error message for common error scenarios.

    Args:
        original_message: Original error message

    Returns:
        Dict with friendly message, hint, and reason if found,
        or original message wrapped in dict if not found.
    """
    # Check for exact match
    if original_message in FRIENDLY_ERROR_MESSAGES:
        return FRIENDLY_ERROR_MESSAGES[original_message]

    # Check for partial match
    for key, value in FRIENDLY_ERROR_MESSAGES.items():
        if key.lower() in original_message.lower():
            return value

    # Return original if no match found
    return {"message": original_message, "hint": None, "reason": None}


class SpockMCPError(Exception):
    """Base exception for all MCP errors"""

    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        """
        Initialize base error.

        Args:
            code: Error code (e.g., "VALIDATION_ERROR")
            message: Human-readable error message
            details: Optional dict with additional error context

        Example:
            >>> error = SpockMCPError("CUSTOM_ERROR", "Something went wrong", {"field": "value"})
            >>> error.code
            'CUSTOM_ERROR'
            >>> error.message
            'Something went wrong'
        """
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict:
        """
        Convert error to JSON-serializable dict.

        Returns:
            Dict with structure:
            {
                "success": False,
                "error": {
                    "code": str,
                    "message": str,
                    "details": dict
                }
            }

        Example:
            >>> error = SpockMCPError("TEST_ERROR", "Test message")
            >>> result = error.to_dict()
            >>> result["success"]
            False
            >>> result["error"]["code"]
            'TEST_ERROR'
        """
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }


class ValidationError(SpockMCPError):
    """Input validation failed"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize validation error.

        Args:
            message: Human-readable validation error message
            details: Optional dict with validation context

        Example:
            >>> error = ValidationError("Invalid ticker", {"ticker": "INVALID", "expected": "6-digit"})
            >>> error.code
            'VALIDATION_ERROR'
        """
        super().__init__("VALIDATION_ERROR", message, details)


class DataNotFoundError(SpockMCPError):
    """Requested data not available - with user-friendly messages"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize data not found error with user-friendly messaging.

        Automatically converts technical error messages to user-friendly
        versions with hints and reasons for common scenarios.

        Args:
            message: Human-readable error message
            details: Optional dict with query context

        Example:
            >>> error = DataNotFoundError("No TTM data available", {"ticker": "005930"})
            >>> error.friendly["hint"]
            'ANNUAL 또는 QUARTERLY period_type을 사용해주세요.'
        """
        self.friendly = get_friendly_error(message)
        enhanced_details = details or {}
        enhanced_details["friendly_message"] = self.friendly["message"]
        if self.friendly["hint"]:
            enhanced_details["hint"] = self.friendly["hint"]
        if self.friendly["reason"]:
            enhanced_details["reason"] = self.friendly["reason"]

        super().__init__("DATA_NOT_FOUND", message, enhanced_details)


class BacktestError(SpockMCPError):
    """Backtest execution failed"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize backtest error.

        Args:
            message: Human-readable error message
            details: Optional dict with backtest context

        Example:
            >>> error = BacktestError("Insufficient data", {"required_days": 252, "available_days": 100})
            >>> error.code
            'BACKTEST_ERROR'
        """
        super().__init__("BACKTEST_ERROR", message, details)


class DatabaseError(SpockMCPError):
    """Database operation failed"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize database error.

        Args:
            message: Human-readable error message
            details: Optional dict with database context

        Example:
            >>> error = DatabaseError("Connection timeout", {"host": "localhost", "timeout_seconds": 30})
            >>> error.code
            'DATABASE_ERROR'
        """
        super().__init__("DATABASE_ERROR", message, details)


class PortfolioError(SpockMCPError):
    """Portfolio operation failed"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize portfolio error.

        Args:
            message: Human-readable error message
            details: Optional dict with portfolio context

        Example:
            >>> error = PortfolioError("Insufficient cash", {"required": 1000000, "available": 500000})
            >>> error.code
            'PORTFOLIO_ERROR'
        """
        super().__init__("PORTFOLIO_ERROR", message, details)


class PathValidationError(SpockMCPError):
    """Path validation failed - operation outside allowed project"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize path validation error.

        Args:
            message: Human-readable error message
            details: Optional dict with path context

        Example:
            >>> error = PathValidationError(
            ...     "Operation outside allowed project path",
            ...     {"current_path": "/tmp", "allowed_path": "/Users/13ruce/spock"}
            ... )
            >>> error.code
            'PATH_VALIDATION_ERROR'
        """
        super().__init__("PATH_VALIDATION_ERROR", message, details)
