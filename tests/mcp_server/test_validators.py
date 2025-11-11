# tests/mcp_server/test_validators.py
"""
Unit tests for input validators
"""

import pytest
from mcp_server.utils.validators import (
    validate_tickers,
    validate_date_range,
    validate_strategy_config,
    validate_project_context,
    validate_file_path,
)
from mcp_server.utils.errors import ValidationError, PathValidationError


class TestValidateTickers:
    """Test suite for validate_tickers()"""

    def test_valid_kr_tickers(self):
        """Test valid KR ticker validation"""
        validate_tickers(["005930"], "KR")
        validate_tickers(["005930", "000660", "035720"], "KR")

    def test_valid_us_tickers(self):
        """Test valid US ticker validation"""
        validate_tickers(["AAPL"], "US")
        validate_tickers(["AAPL", "GOOGL", "MSFT"], "US")
        validate_tickers(["A", "AB", "ABC", "ABCD", "ABCDE"], "US")

    def test_empty_list(self):
        """Test empty ticker list raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_tickers([], "KR")
        assert "cannot be empty" in exc_info.value.message

    def test_too_many_tickers(self):
        """Test max 1000 tickers limit"""
        tickers = [f"{i:06d}" for i in range(1001)]
        with pytest.raises(ValidationError) as exc_info:
            validate_tickers(tickers, "KR")
        assert "Too many tickers" in exc_info.value.message
        assert exc_info.value.details["provided_count"] == 1001

    def test_invalid_kr_format(self):
        """Test invalid KR ticker format"""
        with pytest.raises(ValidationError):
            validate_tickers(["AAPL"], "KR")  # Letters
        
        with pytest.raises(ValidationError):
            validate_tickers(["12345"], "KR")  # 5 digits
        
        with pytest.raises(ValidationError):
            validate_tickers(["1234567"], "KR")  # 7 digits

    def test_invalid_us_format(self):
        """Test invalid US ticker format"""
        with pytest.raises(ValidationError):
            validate_tickers(["005930"], "US")  # Numbers
        
        with pytest.raises(ValidationError):
            validate_tickers(["abcde"], "US")  # Lowercase
        
        with pytest.raises(ValidationError):
            validate_tickers(["ABCDEF"], "US")  # 6 letters

    def test_invalid_region(self):
        """Test invalid region raises error"""
        with pytest.raises(ValidationError) as exc_info:
            validate_tickers(["005930"], "JP")
        assert "Invalid region" in exc_info.value.message

    def test_mixed_invalid_tickers(self):
        """Test multiple invalid tickers"""
        with pytest.raises(ValidationError) as exc_info:
            validate_tickers(["005930", "INVALID", "123"], "KR")
        assert len(exc_info.value.details["invalid_tickers"]) == 2


class TestValidateDateRange:
    """Test suite for validate_date_range()"""

    def test_valid_date_range(self):
        """Test valid date range"""
        validate_date_range("2024-01-01", "2024-12-31")
        validate_date_range("2023-01-01", "2024-01-01")

    def test_invalid_start_date_format(self):
        """Test invalid start date format"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range("2024/01/01", "2024-12-31")
        assert "start_date format" in exc_info.value.message

    def test_invalid_end_date_format(self):
        """Test invalid end date format"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range("2024-01-01", "2024/12/31")
        assert "end_date format" in exc_info.value.message

    def test_start_after_end(self):
        """Test start_date after end_date"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range("2024-12-31", "2024-01-01")
        assert "before end_date" in exc_info.value.message

    def test_start_equals_end(self):
        """Test start_date equals end_date"""
        with pytest.raises(ValidationError):
            validate_date_range("2024-01-01", "2024-01-01")

    def test_max_range_exceeded(self):
        """Test date range exceeding 10 years"""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_range("2020-01-01", "2031-01-01")
        assert "cannot exceed 10 years" in exc_info.value.message
        assert exc_info.value.details["days_requested"] > 3650

    def test_max_range_boundary(self):
        """Test exactly 10 years (boundary condition)"""
        validate_date_range("2020-01-01", "2029-12-31")  # Should pass (< 3650 days)

    def test_leap_year_handling(self):
        """Test leap year date validation"""
        validate_date_range("2024-02-29", "2024-03-01")  # 2024 is leap year
        
        with pytest.raises(ValidationError):
            validate_date_range("2023-02-29", "2023-03-01")  # 2023 is not leap year


class TestValidateStrategyConfig:
    """Test suite for validate_strategy_config()"""

    def test_valid_momentum_strategy(self):
        """Test valid momentum strategy config"""
        config = {
            "type": "momentum",
            "universe": ["005930"]
        }
        validate_strategy_config(config)

    def test_valid_value_strategy(self):
        """Test valid value strategy config"""
        config = {
            "type": "value",
            "universe": ["005930", "000660"]
        }
        validate_strategy_config(config)

    def test_valid_multi_factor_strategy(self):
        """Test valid multi_factor strategy config"""
        config = {
            "type": "multi_factor",
            "universe": ["005930"]
        }
        validate_strategy_config(config)

    def test_valid_custom_strategy(self):
        """Test valid custom strategy config"""
        config = {
            "type": "custom",
            "universe": ["005930"]
        }
        validate_strategy_config(config)

    def test_missing_type_field(self):
        """Test missing type field"""
        config = {"universe": ["005930"]}
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_config(config)
        assert "Missing required field: type" in exc_info.value.message

    def test_missing_universe_field(self):
        """Test missing universe field"""
        config = {"type": "momentum"}
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_config(config)
        assert "Missing required field: universe" in exc_info.value.message

    def test_invalid_strategy_type(self):
        """Test invalid strategy type"""
        config = {
            "type": "invalid_type",
            "universe": ["005930"]
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_config(config)
        assert "Invalid strategy type" in exc_info.value.message
        assert "invalid_type" in exc_info.value.details["provided_type"]

    def test_universe_not_list(self):
        """Test universe is not a list"""
        config = {
            "type": "momentum",
            "universe": "005930"  # Should be list
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_config(config)
        assert "must be a list" in exc_info.value.message

    def test_empty_universe(self):
        """Test empty universe list"""
        config = {
            "type": "momentum",
            "universe": []
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_strategy_config(config)
        assert "cannot be empty" in exc_info.value.message
