# mcp_server/utils/errors.py
"""
Error handling for MCP server

Defines error hierarchy and JSON-serializable error responses.
"""

from typing import Dict, Optional


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
    """Requested data not available"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """
        Initialize data not found error.

        Args:
            message: Human-readable error message
            details: Optional dict with query context

        Example:
            >>> error = DataNotFoundError("No OHLCV data", {"ticker": "005930", "date_range": "2024-01-01 to 2024-12-31"})
            >>> error.code
            'DATA_NOT_FOUND'
        """
        super().__init__("DATA_NOT_FOUND", message, details)


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
