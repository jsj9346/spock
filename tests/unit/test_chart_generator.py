# tests/unit/test_chart_generator.py
"""
Unit tests for StockChartGenerator.

Tests chart generation functionality including:
- Basic candlestick chart generation
- Technical indicator rendering (MA, RSI, MACD, Bollinger)
- Different chart styles
- Error handling for invalid data
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

from mcp_server.generators.stock_chart_generator import StockChartGenerator


class TestStockChartGenerator:
    """Test suite for StockChartGenerator."""

    @pytest.fixture
    def generator(self):
        """Create StockChartGenerator instance."""
        return StockChartGenerator(dpi=100)

    @pytest.fixture
    def sample_ohlcv_df(self):
        """Create sample OHLCV DataFrame with 100 trading days."""
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='B')

        # Generate realistic price data
        base_price = 50000
        returns = np.random.normal(0.001, 0.02, 100)
        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 100)),
            'High': prices * (1 + np.random.uniform(0, 0.02, 100)),
            'Low': prices * (1 - np.random.uniform(0, 0.02, 100)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 10000000, 100)
        }, index=dates)

        return df

    @pytest.fixture
    def minimal_ohlcv_df(self):
        """Create minimal OHLCV DataFrame with 30 trading days."""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
        df = pd.DataFrame({
            'Open': [100 + i for i in range(30)],
            'High': [105 + i for i in range(30)],
            'Low': [95 + i for i in range(30)],
            'Close': [102 + i for i in range(30)],
            'Volume': [1000000] * 30
        }, index=dates)
        return df

    def test_generate_basic_chart(self, generator, sample_ohlcv_df):
        """Test basic candlestick chart generation."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["volume"],
            style="default",
            size=(1200, 800)
        )

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0
        # PNG signature check
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_all_indicators(self, generator, sample_ohlcv_df):
        """Test chart with all indicators."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            ticker_name="삼성전자",
            region="KR",
            indicators=["ma", "rsi", "macd", "bollinger", "volume"],
            style="default",
            size=(1200, 800)
        )

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_ma_only(self, generator, sample_ohlcv_df):
        """Test chart with moving averages only."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="AAPL",
            region="US",
            indicators=["ma"],
            style="default"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_rsi(self, generator, sample_ohlcv_df):
        """Test chart with RSI indicator (with volume for proper panel layout)."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["rsi", "volume"],  # Include volume for standard layout
            style="default"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_macd(self, generator, sample_ohlcv_df):
        """Test chart with MACD indicator (with volume for proper panel layout)."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["macd", "volume"],  # Include volume for standard layout
            style="default"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_generate_with_bollinger(self, generator, sample_ohlcv_df):
        """Test chart with Bollinger Bands."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["bollinger"],
            style="default"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_dark_style(self, generator, sample_ohlcv_df):
        """Test dark theme chart."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["ma", "volume"],
            style="dark"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_classic_style(self, generator, sample_ohlcv_df):
        """Test classic theme chart."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["ma", "volume"],
            style="classic"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_custom_image_size(self, generator, sample_ohlcv_df):
        """Test custom image dimensions."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["volume"],
            size=(800, 600)
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_minimal_data(self, generator, minimal_ohlcv_df):
        """Test chart generation with minimal data."""
        png_bytes = generator.generate(
            ohlcv_df=minimal_ohlcv_df,
            ticker="005930",
            indicators=["volume"],
            style="default"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_empty_dataframe_raises_error(self, generator):
        """Test that empty DataFrame raises ValueError."""
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="empty"):
            generator.generate(
                ohlcv_df=empty_df,
                ticker="005930"
            )

    def test_missing_columns_raises_error(self, generator):
        """Test that missing columns raise ValueError."""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='B')
        incomplete_df = pd.DataFrame({
            'Open': [100] * 30,
            'Close': [100] * 30
            # Missing High, Low, Volume
        }, index=dates)

        with pytest.raises(ValueError, match="Missing"):
            generator.generate(
                ohlcv_df=incomplete_df,
                ticker="005930"
            )

    def test_non_datetime_index_raises_error(self, generator):
        """Test that non-DatetimeIndex raises ValueError."""
        df = pd.DataFrame({
            'Open': [100] * 30,
            'High': [105] * 30,
            'Low': [95] * 30,
            'Close': [102] * 30,
            'Volume': [1000000] * 30
        }, index=range(30))  # Integer index instead of DatetimeIndex

        with pytest.raises(ValueError, match="DatetimeIndex"):
            generator.generate(
                ohlcv_df=df,
                ticker="005930"
            )

    def test_rsi_calculation(self, generator, sample_ohlcv_df):
        """Test RSI calculation accuracy."""
        rsi = generator._calculate_rsi(sample_ohlcv_df, period=14)

        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(sample_ohlcv_df)
        # RSI should be between 0 and 100 (excluding NaN)
        valid_rsi = rsi.dropna()
        assert all(0 <= v <= 100 for v in valid_rsi)

    def test_macd_calculation(self, generator, sample_ohlcv_df):
        """Test MACD calculation accuracy."""
        macd_data = generator._calculate_macd(sample_ohlcv_df)

        assert "macd" in macd_data
        assert "signal" in macd_data
        assert "histogram" in macd_data
        assert len(macd_data["macd"]) == len(sample_ohlcv_df)

    def test_moving_averages_calculation(self, generator, sample_ohlcv_df):
        """Test moving averages calculation."""
        mas = generator._create_ma_plots(sample_ohlcv_df, generator.STYLES["default"])

        # With 100 days of data, MA20 and MA50 can be calculated, but MA200 cannot
        # So we expect 2 MA plots
        assert len(mas) == 2  # MA20 and MA50 only (100 days < 200 days required for MA200)

    def test_bollinger_bands_calculation(self, generator, sample_ohlcv_df):
        """Test Bollinger Bands calculation."""
        bb_plots = generator._create_bollinger_plots(
            sample_ohlcv_df,
            generator.STYLES["default"]
        )

        # Should create 3 plots (upper, middle, lower)
        assert len(bb_plots) == 3

    def test_create_title(self, generator, sample_ohlcv_df):
        """Test chart title creation."""
        title = generator._create_title(
            ticker="005930",
            ticker_name="삼성전자",
            region="KR",
            df=sample_ohlcv_df
        )

        assert "005930" in title
        assert "삼성전자" in title
        assert "KR" in title

    def test_create_title_without_name(self, generator, sample_ohlcv_df):
        """Test chart title creation without ticker name."""
        title = generator._create_title(
            ticker="005930",
            ticker_name=None,
            region="KR",
            df=sample_ohlcv_df
        )

        assert "005930" in title
        assert "KR" in title

    def test_unknown_style_falls_back_to_default(self, generator, sample_ohlcv_df):
        """Test that unknown style falls back to default."""
        png_bytes = generator.generate(
            ohlcv_df=sample_ohlcv_df,
            ticker="005930",
            indicators=["volume"],
            style="unknown_style"
        )

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'


class TestChartGeneratorPerformance:
    """Performance tests for chart generation."""

    @pytest.fixture
    def generator(self):
        return StockChartGenerator(dpi=100)

    @pytest.fixture
    def large_ohlcv_df(self):
        """Create large OHLCV DataFrame with 500 trading days (~2 years)."""
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=500, freq='B')

        base_price = 50000
        returns = np.random.normal(0.001, 0.02, 500)
        prices = base_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 500)),
            'High': prices * (1 + np.random.uniform(0, 0.02, 500)),
            'Low': prices * (1 - np.random.uniform(0, 0.02, 500)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 10000000, 500)
        }, index=dates)

        return df

    def test_large_data_chart_generation(self, generator, large_ohlcv_df):
        """Test chart generation with large dataset."""
        import time
        start = time.time()

        png_bytes = generator.generate(
            ohlcv_df=large_ohlcv_df,
            ticker="005930",
            indicators=["ma", "rsi", "macd", "volume"],
            style="default",
            size=(1200, 800)
        )

        elapsed = time.time() - start

        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'
        # Should complete within 5 seconds
        assert elapsed < 5.0, f"Chart generation took {elapsed:.2f}s, expected < 5s"

    def test_image_size_reasonable(self, generator, large_ohlcv_df):
        """Test that generated image size is reasonable."""
        png_bytes = generator.generate(
            ohlcv_df=large_ohlcv_df,
            ticker="005930",
            indicators=["ma", "rsi", "macd", "volume"],
            style="default",
            size=(1200, 800)
        )

        # Image should be less than 1MB
        assert len(png_bytes) < 1024 * 1024, f"Image size {len(png_bytes)} bytes exceeds 1MB"
