# tests/mcp_server/test_formatters.py
"""
Unit tests for output formatters
"""

import json
import pytest
from mcp_server.utils.formatters import (
    format_ohlcv_response,
    format_backtest_response,
    format_portfolio_response,
)


class TestFormatOHLCVResponse:
    """Test suite for format_ohlcv_response()"""

    def test_single_ticker(self):
        """Test formatting single ticker OHLCV data"""
        data = {
            "005930": [
                {"date": "2024-01-01", "open": 70000, "high": 71000, "low": 69000, "close": 70500, "volume": 10000000}
            ]
        }
        result = format_ohlcv_response(data)
        
        # Parse JSON
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert "005930" in parsed["data"]
        assert parsed["metadata"]["record_count"] == 1
        assert parsed["metadata"]["tickers"] == ["005930"]

    def test_multiple_tickers(self):
        """Test formatting multiple tickers"""
        data = {
            "005930": [
                {"date": "2024-01-01", "open": 70000, "close": 70500}
            ],
            "000660": [
                {"date": "2024-01-01", "open": 50000, "close": 50500},
                {"date": "2024-01-02", "open": 50500, "close": 51000}
            ]
        }
        result = format_ohlcv_response(data)
        
        parsed = json.loads(result)
        assert parsed["metadata"]["record_count"] == 3
        assert len(parsed["metadata"]["tickers"]) == 2

    def test_empty_data(self):
        """Test formatting empty data"""
        data = {}
        result = format_ohlcv_response(data)
        
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["metadata"]["record_count"] == 0
        assert parsed["metadata"]["tickers"] == []

    def test_korean_characters(self):
        """Test Korean characters are preserved (ensure_ascii=False)"""
        data = {
            "005930": [
                {"date": "2024-01-01", "name": "삼성전자"}
            ]
        }
        result = format_ohlcv_response(data)
        
        # Should contain Korean characters, not Unicode escapes
        assert "삼성전자" in result
        assert "\\u" not in result  # No Unicode escapes

    def test_json_structure(self):
        """Test JSON has correct top-level structure"""
        data = {"005930": [{"date": "2024-01-01"}]}
        result = format_ohlcv_response(data)
        
        parsed = json.loads(result)
        assert "success" in parsed
        assert "data" in parsed
        assert "metadata" in parsed
        assert "record_count" in parsed["metadata"]
        assert "tickers" in parsed["metadata"]


class TestFormatBacktestResponse:
    """Test suite for format_backtest_response()"""

    def test_complete_results(self):
        """Test formatting complete backtest results"""
        results = {
            "backtest_id": "bt_20240115_abc123",
            "performance": {
                "cagr": 0.165,
                "sharpe_ratio": 1.65,
                "max_drawdown": -0.223,
                "win_rate": 0.583
            },
            "trades": {
                "total_trades": 125,
                "avg_holding_period_days": 45.0
            }
        }
        text = format_backtest_response(results)
        
        # Check Korean labels
        assert "백테스트 완료" in text
        assert "성과 지표" in text
        assert "거래 통계" in text
        
        # Check formatted values
        assert "16.50%" in text  # CAGR
        assert "1.65" in text  # Sharpe
        assert "-22.30%" in text  # Max DD
        assert "58.30%" in text  # Win rate
        assert "125회" in text  # Total trades
        assert "45.0일" in text  # Avg holding

    def test_missing_fields(self):
        """Test formatting with missing fields (defaults to 0)"""
        results = {
            "backtest_id": "bt_123"
        }
        text = format_backtest_response(results)
        
        assert "bt_123" in text
        assert "0.00%" in text  # Default CAGR

    def test_negative_cagr(self):
        """Test formatting negative CAGR"""
        results = {
            "backtest_id": "bt_123",
            "performance": {"cagr": -0.05}
        }
        text = format_backtest_response(results)
        
        assert "-5.00%" in text

    def test_percentage_formatting(self):
        """Test .2f percentage formatting"""
        results = {
            "backtest_id": "bt_123",
            "performance": {
                "cagr": 0.12345,
                "max_drawdown": -0.23456,
                "win_rate": 0.56789
            }
        }
        text = format_backtest_response(results)
        
        assert "12.35%" in text  # CAGR rounded to 2 decimals
        assert "-23.46%" in text  # Max DD rounded to 2 decimals
        assert "56.79%" in text  # Win rate rounded to 2 decimals

    def test_ratio_formatting(self):
        """Test .2f ratio formatting for Sharpe"""
        results = {
            "backtest_id": "bt_123",
            "performance": {"sharpe_ratio": 1.23456}
        }
        text = format_backtest_response(results)
        
        assert "1.23" in text  # Sharpe rounded to 2 decimals

    def test_days_formatting(self):
        """Test .1f days formatting"""
        results = {
            "backtest_id": "bt_123",
            "trades": {"avg_holding_period_days": 45.67}
        }
        text = format_backtest_response(results)
        
        assert "45.7일" in text  # Days rounded to 1 decimal


class TestFormatPortfolioResponse:
    """Test suite for format_portfolio_response()"""

    def test_deferred_implementation(self):
        """Test portfolio formatting returns Phase 2 message"""
        analysis = {"total_value": 10000000}
        result = format_portfolio_response(analysis)
        
        assert "Phase 2" in result
