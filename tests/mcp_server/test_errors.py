# tests/mcp_server/test_errors.py
"""
Unit tests for MCP error handling
"""

import pytest
from mcp_server.utils.errors import (
    SpockMCPError,
    ValidationError,
    DataNotFoundError,
    BacktestError,
    DatabaseError,
    PortfolioError,
)


class TestSpockMCPError:
    """Test suite for base SpockMCPError"""

    def test_initialization(self):
        """Test error initialization with all parameters"""
        error = SpockMCPError("TEST_CODE", "Test message", {"key": "value"})
        
        assert error.code == "TEST_CODE"
        assert error.message == "Test message"
        assert error.details == {"key": "value"}
        assert str(error) == "Test message"

    def test_initialization_without_details(self):
        """Test error initialization without details dict"""
        error = SpockMCPError("TEST_CODE", "Test message")
        
        assert error.code == "TEST_CODE"
        assert error.message == "Test message"
        assert error.details == {}

    def test_to_dict_structure(self):
        """Test error to_dict() returns correct JSON structure"""
        error = SpockMCPError("TEST_CODE", "Test message", {"field": "value"})
        result = error.to_dict()
        
        assert result["success"] is False
        assert "error" in result
        assert result["error"]["code"] == "TEST_CODE"
        assert result["error"]["message"] == "Test message"
        assert result["error"]["details"]["field"] == "value"

    def test_to_dict_without_details(self):
        """Test to_dict() with empty details"""
        error = SpockMCPError("TEST_CODE", "Test message")
        result = error.to_dict()
        
        assert result["success"] is False
        assert result["error"]["details"] == {}

    def test_exception_hierarchy(self):
        """Test that SpockMCPError inherits from Exception"""
        error = SpockMCPError("TEST_CODE", "Test message")
        assert isinstance(error, Exception)

    def test_raises_properly(self):
        """Test that error can be raised and caught"""
        with pytest.raises(SpockMCPError) as exc_info:
            raise SpockMCPError("TEST_CODE", "Test message")
        
        assert exc_info.value.code == "TEST_CODE"


class TestValidationError:
    """Test suite for ValidationError"""

    def test_initialization(self):
        """Test ValidationError initialization"""
        error = ValidationError("Invalid input", {"field": "ticker"})
        
        assert error.code == "VALIDATION_ERROR"
        assert error.message == "Invalid input"
        assert error.details["field"] == "ticker"

    def test_inheritance(self):
        """Test ValidationError inherits from SpockMCPError"""
        error = ValidationError("Invalid input")
        assert isinstance(error, SpockMCPError)

    def test_to_dict(self):
        """Test ValidationError to_dict() structure"""
        error = ValidationError("Invalid ticker format", {"ticker": "INVALID"})
        result = error.to_dict()
        
        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert result["error"]["message"] == "Invalid ticker format"
        assert result["error"]["details"]["ticker"] == "INVALID"


class TestDataNotFoundError:
    """Test suite for DataNotFoundError"""

    def test_initialization(self):
        """Test DataNotFoundError initialization"""
        error = DataNotFoundError("No data available", {"ticker": "005930"})
        
        assert error.code == "DATA_NOT_FOUND"
        assert error.message == "No data available"
        assert error.details["ticker"] == "005930"

    def test_inheritance(self):
        """Test DataNotFoundError inherits from SpockMCPError"""
        error = DataNotFoundError("No data")
        assert isinstance(error, SpockMCPError)


class TestBacktestError:
    """Test suite for BacktestError"""

    def test_initialization(self):
        """Test BacktestError initialization"""
        error = BacktestError("Backtest failed", {"reason": "insufficient_data"})
        
        assert error.code == "BACKTEST_ERROR"
        assert error.message == "Backtest failed"
        assert error.details["reason"] == "insufficient_data"

    def test_inheritance(self):
        """Test BacktestError inherits from SpockMCPError"""
        error = BacktestError("Backtest failed")
        assert isinstance(error, SpockMCPError)


class TestDatabaseError:
    """Test suite for DatabaseError"""

    def test_initialization(self):
        """Test DatabaseError initialization"""
        error = DatabaseError("Connection failed", {"host": "localhost"})
        
        assert error.code == "DATABASE_ERROR"
        assert error.message == "Connection failed"
        assert error.details["host"] == "localhost"

    def test_inheritance(self):
        """Test DatabaseError inherits from SpockMCPError"""
        error = DatabaseError("Connection failed")
        assert isinstance(error, SpockMCPError)


class TestPortfolioError:
    """Test suite for PortfolioError"""

    def test_initialization(self):
        """Test PortfolioError initialization"""
        error = PortfolioError("Insufficient funds", {"required": 1000000})
        
        assert error.code == "PORTFOLIO_ERROR"
        assert error.message == "Insufficient funds"
        assert error.details["required"] == 1000000

    def test_inheritance(self):
        """Test PortfolioError inherits from SpockMCPError"""
        error = PortfolioError("Insufficient funds")
        assert isinstance(error, SpockMCPError)
