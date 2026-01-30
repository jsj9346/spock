# tests/unit/test_return_comparison.py
"""
Unit tests for ReturnComparisonGenerator and related components.

Tests:
- ReturnComparisonGenerator chart generation
- Return calculation and metrics
- Input validation
- Edge cases
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

# Import the components to test
from mcp_server.generators.return_comparison_generator import ReturnComparisonGenerator
from mcp_server.tools.return_comparison_tool import (
    get_return_comparison_tool_def,
    _generate_filename,
    _build_summary,
    PERIOD_DAYS,
    BENCHMARK_TICKERS
)


class TestReturnComparisonGenerator:
    """Tests for ReturnComparisonGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return ReturnComparisonGenerator(dpi=72)  # Lower DPI for faster tests

    @pytest.fixture
    def sample_price_data(self):
        """Create sample price data for testing."""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")

        # Stock 1: Steady growth
        stock1 = pd.DataFrame({
            "Close": 100 * (1 + np.cumsum(np.random.randn(100) * 0.01 + 0.001))
        }, index=dates)

        # Stock 2: More volatile, higher growth
        stock2 = pd.DataFrame({
            "Close": 100 * (1 + np.cumsum(np.random.randn(100) * 0.02 + 0.002))
        }, index=dates)

        return {
            "STOCK1": stock1,
            "STOCK2": stock2
        }

    @pytest.fixture
    def sample_benchmark_data(self):
        """Create sample benchmark data."""
        dates = pd.date_range(start="2025-01-01", periods=100, freq="B")
        return pd.DataFrame({
            "Close": 100 * (1 + np.cumsum(np.random.randn(100) * 0.01))
        }, index=dates)

    def test_generator_initialization(self, generator):
        """Test generator initializes with correct defaults."""
        assert generator.dpi == 72
        assert generator.MAX_STOCKS == 5
        assert len(generator.STOCK_COLORS) >= 5

    def test_generate_basic_chart(self, generator, sample_price_data):
        """Test basic chart generation (Google Finance style)."""
        png_bytes, metrics = generator.generate(
            price_data=sample_price_data,
            ticker_names={"STOCK1": "Stock One", "STOCK2": "Stock Two"}
        )

        # Check PNG output
        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'  # PNG magic bytes

        # Check metrics
        assert "stocks" in metrics
        assert "STOCK1" in metrics["stocks"]
        assert "STOCK2" in metrics["stocks"]

    def test_generate_with_benchmark(self, generator, sample_price_data, sample_benchmark_data):
        """Test chart generation with benchmark."""
        png_bytes, metrics = generator.generate(
            price_data=sample_price_data,
            benchmark_data=sample_benchmark_data,
            benchmark_name="Test Benchmark"
        )

        assert isinstance(png_bytes, bytes)
        assert metrics["benchmark"] is not None
        assert "total_return_pct" in metrics["benchmark"]

    def test_generate_with_all_features(self, generator, sample_price_data, sample_benchmark_data):
        """Test chart generation with benchmark and custom size."""
        png_bytes, metrics = generator.generate(
            price_data=sample_price_data,
            ticker_names={"STOCK1": "Stock One", "STOCK2": "Stock Two"},
            benchmark_data=sample_benchmark_data,
            benchmark_name="Benchmark",
            size=(1200, 600)
        )

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 1000  # Should be a reasonable size

    def test_generate_different_size(self, generator, sample_price_data):
        """Test chart generation with different size."""
        png_bytes, _ = generator.generate(
            price_data=sample_price_data,
            size=(800, 400)
        )

        assert isinstance(png_bytes, bytes)

    def test_metrics_calculation(self, generator, sample_price_data):
        """Test that metrics are calculated correctly (Google Finance style)."""
        _, metrics = generator.generate(
            price_data=sample_price_data
        )

        for ticker in ["STOCK1", "STOCK2"]:
            stock_metrics = metrics["stocks"][ticker]

            # Check all expected metrics exist (simplified for Google Finance style)
            assert "total_return_pct" in stock_metrics
            assert "volatility_pct" in stock_metrics
            assert "trading_days" in stock_metrics
            assert "start_date" in stock_metrics
            assert "end_date" in stock_metrics
            assert "start_price" in stock_metrics
            assert "end_price" in stock_metrics

            # Validate metric types
            assert isinstance(stock_metrics["total_return_pct"], (int, float))
            assert isinstance(stock_metrics["volatility_pct"], (int, float))

    def test_validation_empty_data(self, generator):
        """Test validation rejects empty data."""
        with pytest.raises(ValueError, match="price_data cannot be empty"):
            generator.generate(price_data={})

    def test_validation_single_stock(self, generator, sample_price_data):
        """Test validation rejects single stock."""
        single_stock = {"STOCK1": sample_price_data["STOCK1"]}

        with pytest.raises(ValueError, match="At least 2 stocks required"):
            generator.generate(price_data=single_stock)

    def test_validation_too_many_stocks(self, generator):
        """Test validation rejects more than 5 stocks."""
        dates = pd.date_range(start="2025-01-01", periods=50, freq="B")
        many_stocks = {
            f"STOCK{i}": pd.DataFrame({"Close": np.random.randn(50) + 100}, index=dates)
            for i in range(6)
        }

        with pytest.raises(ValueError, match="Maximum 5 stocks allowed"):
            generator.generate(price_data=many_stocks)

    def test_validation_missing_close_column(self, generator):
        """Test validation rejects data without close column."""
        dates = pd.date_range(start="2025-01-01", periods=50, freq="B")
        bad_data = {
            "STOCK1": pd.DataFrame({"Open": np.random.randn(50)}, index=dates),
            "STOCK2": pd.DataFrame({"Open": np.random.randn(50)}, index=dates)
        }

        with pytest.raises(ValueError, match="Missing 'close' column"):
            generator.generate(price_data=bad_data)


class TestReturnComparisonToolDef:
    """Tests for tool definition."""

    def test_tool_definition_structure(self):
        """Test tool definition has correct structure."""
        tool_def = get_return_comparison_tool_def()

        assert tool_def.name == "compare_stock_returns"
        assert "여러 종목의 수익률" in tool_def.description
        assert "Google Finance" in tool_def.description
        assert "토큰 효율적" in tool_def.description

        schema = tool_def.inputSchema
        assert schema["type"] == "object"
        assert "tickers" in schema["properties"]
        assert "region" in schema["properties"]
        assert "period" in schema["properties"]
        assert "tickers" in schema["required"]

        # Verify simplified schema (no show_volatility, show_drawdown)
        assert "show_volatility" not in schema["properties"]
        assert "show_drawdown" not in schema["properties"]

    def test_ticker_constraints(self):
        """Test ticker constraints in schema."""
        tool_def = get_return_comparison_tool_def()
        tickers_schema = tool_def.inputSchema["properties"]["tickers"]

        assert tickers_schema["minItems"] == 2
        assert tickers_schema["maxItems"] == 5

    def test_period_options(self):
        """Test period options are defined."""
        assert "1M" in PERIOD_DAYS
        assert "1Y" in PERIOD_DAYS
        assert PERIOD_DAYS["1Y"] == 365

    def test_benchmark_tickers_defined(self):
        """Test benchmark tickers are defined for all regions."""
        for region in ["KR", "US", "HK", "CN", "JP", "VN"]:
            assert region in BENCHMARK_TICKERS
            assert "ticker" in BENCHMARK_TICKERS[region]
            assert "name" in BENCHMARK_TICKERS[region]


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_generate_filename(self):
        """Test filename generation."""
        filename = _generate_filename(
            tickers=["005930", "000660"],
            region="KR",
            period="1Y"
        )

        assert "return_comparison" in filename
        assert "KR" in filename
        assert "1Y" in filename
        assert filename.endswith(".png")

    def test_generate_filename_many_tickers(self):
        """Test filename with many tickers."""
        filename = _generate_filename(
            tickers=["A", "B", "C", "D", "E"],
            region="US",
            period="6M"
        )

        assert "etc2" in filename  # 5 tickers, shows first 3 + etc2

    def test_build_summary(self):
        """Test summary building (Google Finance style - simplified)."""
        metrics = {
            "stocks": {
                "005930": {
                    "total_return_pct": 12.5,
                    "volatility_pct": 18.5,
                    "trading_days": 250,
                    "start_date": "2025-01-20",
                    "end_date": "2026-01-20",
                    "start_price": 55000.0,
                    "end_price": 61875.0
                },
                "000660": {
                    "total_return_pct": 28.3,
                    "volatility_pct": 25.2,
                    "trading_days": 250,
                    "start_date": "2025-01-20",
                    "end_date": "2026-01-20",
                    "start_price": 120000.0,
                    "end_price": 153960.0
                }
            },
            "benchmark": {
                "total_return_pct": 8.2
            }
        }

        summary = _build_summary(
            tickers=["005930", "000660"],
            ticker_names={"005930": "삼성전자", "000660": "SK하이닉스"},
            region="KR",
            period="1Y",
            metrics=metrics,
            benchmark_info={"ticker": "069500", "name": "KODEX 200"},
            suggested_filename="test.png",
            saved_path=None,
            image_size_bytes=150000
        )

        assert summary["success"] is True
        assert "comparison" in summary
        assert len(summary["comparison"]["stocks"]) == 2
        assert summary["comparison"]["ranking_by_return"][0] == "000660"
        assert summary["comparison"]["benchmark"]["ticker"] == "069500"
        # Verify no sharpe_ratio in response (Google Finance style)
        assert "sharpe_ratio" not in summary["comparison"]["stocks"][0]


class TestReturnComparisonAdapter:
    """Tests for ReturnComparisonAdapter (with mocked data)."""

    @pytest.fixture
    def mock_data_adapter(self):
        """Create mock data adapter."""
        adapter = Mock()
        adapter.get_ohlcv = AsyncMock()
        return adapter

    @pytest.mark.asyncio
    async def test_adapter_validation(self, mock_data_adapter):
        """Test adapter input validation."""
        from mcp_server.adapters.return_comparison_adapter import ReturnComparisonAdapter
        from mcp_server.utils.errors import ValidationError

        adapter = ReturnComparisonAdapter(data_adapter=mock_data_adapter)

        # Test single ticker rejection
        with pytest.raises(ValidationError, match="At least 2 tickers required"):
            await adapter.generate_comparison(
                tickers=["005930"],
                region="KR"
            )

        # Test too many tickers rejection
        with pytest.raises(ValidationError, match="Maximum 5 tickers allowed"):
            await adapter.generate_comparison(
                tickers=["A", "B", "C", "D", "E", "F"],
                region="KR"
            )

    @pytest.mark.asyncio
    async def test_ticker_normalization(self, mock_data_adapter):
        """Test ticker normalization for different regions."""
        from mcp_server.adapters.return_comparison_adapter import ReturnComparisonAdapter

        adapter = ReturnComparisonAdapter(data_adapter=mock_data_adapter)

        # Test HK normalization
        assert adapter._normalize_ticker("700", "HK") == "0700.HK"
        assert adapter._normalize_ticker("0700", "HK") == "0700.HK"

        # Test CN normalization
        assert adapter._normalize_ticker("600519", "CN") == "600519.SS"  # Shanghai
        assert adapter._normalize_ticker("000858", "CN") == "000858.SZ"  # Shenzhen

        # Test KR/US (no change)
        assert adapter._normalize_ticker("005930", "KR") == "005930"
        assert adapter._normalize_ticker("AAPL", "US") == "AAPL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
