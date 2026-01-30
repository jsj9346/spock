# mcp_server/adapters/chart_adapter.py
"""
Chart Generation Adapter for MCP Server

Connects data retrieval (DataAdapter) with chart rendering (StockChartGenerator)
to produce stock chart images for MCP tool responses.

Author: Spock MCP Server
Date: 2026-01-19
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

import pandas as pd
import structlog

from .data_adapter import DataAdapter
from ..generators.stock_chart_generator import StockChartGenerator
from ..utils.errors import DataNotFoundError, ValidationError

logger = structlog.get_logger()


class ChartAdapter:
    """
    Chart generation adapter.

    Orchestrates data retrieval and chart generation for MCP tool responses.

    Usage:
        adapter = ChartAdapter()
        png_bytes = await adapter.generate_chart(
            ticker="005930",
            region="KR",
            indicators=["ma", "rsi", "volume"]
        )
    """

    # Minimum trading days required for chart generation
    MIN_TRADING_DAYS = 20

    # Supported regions
    SUPPORTED_REGIONS = {"KR", "US", "HK", "CN", "JP", "VN"}

    # Ticker suffix mapping for regions that require exchange suffix
    # HK: Hong Kong Stock Exchange (.HK)
    # CN: Shanghai (.SS) or Shenzhen (.SZ) based on ticker prefix
    TICKER_SUFFIX_MAP = {
        "HK": ".HK",
        # CN is handled separately based on ticker prefix
    }

    def __init__(self, data_adapter: Optional[DataAdapter] = None):
        """
        Initialize ChartAdapter.

        Args:
            data_adapter: DataAdapter instance (creates new if not provided)
        """
        self.data_adapter = data_adapter or DataAdapter()
        self.chart_generator = StockChartGenerator()

    async def generate_chart(
        self,
        ticker: str,
        region: str = "KR",
        period_days: int = 365,
        indicators: Optional[List[str]] = None,
        chart_style: str = "default",
        image_size: Tuple[int, int] = (1200, 800)
    ) -> bytes:
        """
        Generate stock chart image.

        Args:
            ticker: Stock ticker symbol
            region: Market region (KR, US, HK, CN, JP, VN)
            period_days: Number of days to fetch (default: 365)
            indicators: List of indicators ("ma", "rsi", "macd", "bollinger", "volume")
            chart_style: Chart style ("default", "dark", "classic")
            image_size: Image dimensions (width, height) in pixels

        Returns:
            PNG image bytes

        Raises:
            ValidationError: Invalid input parameters
            DataNotFoundError: No data found for ticker
        """
        if indicators is None:
            indicators = ["ma", "volume"]

        # Validate inputs
        self._validate_inputs(ticker, region, period_days, indicators, image_size)

        # Normalize ticker for database lookup (HK, CN need exchange suffix)
        original_ticker = ticker
        db_ticker = self._normalize_ticker(ticker, region)
        display_ticker = self._get_display_ticker(db_ticker, region)

        logger.info(
            "chart_generation_started",
            ticker=original_ticker,
            db_ticker=db_ticker,
            region=region,
            period_days=period_days,
            indicators=indicators
        )

        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        # Fetch OHLCV data using normalized ticker
        ohlcv_df = await self._fetch_ohlcv_data(db_ticker, region, start_date, end_date)

        # Get ticker name (optional enhancement)
        ticker_name = await self._get_ticker_name(db_ticker, region)

        # Generate chart with display-friendly ticker
        try:
            png_bytes = self.chart_generator.generate(
                ohlcv_df=ohlcv_df,
                ticker=display_ticker,
                ticker_name=ticker_name,
                region=region,
                indicators=indicators,
                style=chart_style,
                size=image_size
            )

            logger.info(
                "chart_generation_completed",
                ticker=original_ticker,
                db_ticker=db_ticker,
                region=region,
                trading_days=len(ohlcv_df),
                image_size_bytes=len(png_bytes)
            )

            return png_bytes

        except Exception as e:
            logger.error(
                "chart_generation_failed",
                ticker=original_ticker,
                db_ticker=db_ticker,
                region=region,
                error=str(e)
            )
            raise

    def _validate_inputs(
        self,
        ticker: str,
        region: str,
        period_days: int,
        indicators: List[str],
        image_size: Tuple[int, int]
    ) -> None:
        """Validate input parameters."""
        # Ticker validation
        if not ticker or not isinstance(ticker, str):
            raise ValidationError("Ticker must be a non-empty string")

        ticker = ticker.strip()
        if len(ticker) < 1 or len(ticker) > 20:
            raise ValidationError(f"Invalid ticker length: {len(ticker)}")

        # Region validation
        if region not in self.SUPPORTED_REGIONS:
            raise ValidationError(
                f"Unsupported region: {region}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_REGIONS))}"
            )

        # Period validation
        if not 30 <= period_days <= 730:
            raise ValidationError(
                f"period_days must be between 30 and 730, got: {period_days}"
            )

        # Indicators validation
        valid_indicators = {"ma", "rsi", "macd", "bollinger", "volume"}
        invalid = set(indicators) - valid_indicators
        if invalid:
            raise ValidationError(
                f"Invalid indicators: {invalid}. "
                f"Valid options: {', '.join(sorted(valid_indicators))}"
            )

        # Image size validation
        width, height = image_size
        if not (800 <= width <= 2400 and 600 <= height <= 1600):
            raise ValidationError(
                f"Image size out of bounds: {width}x{height}. "
                "Width: 800-2400, Height: 600-1600"
            )

    async def _fetch_ohlcv_data(
        self,
        ticker: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data and convert to mplfinance format.

        Returns:
            DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume

        Raises:
            DataNotFoundError: If no data found or insufficient data
        """
        # Call DataAdapter to get OHLCV data
        result = await self.data_adapter.get_ohlcv(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe="1d"
        )

        # DataAdapter returns data directly as {ticker: [records]}
        # Check if result contains ticker data
        if result is None:
            raise DataNotFoundError(
                message=f"Failed to fetch OHLCV data: No response",
                details={
                    "ticker": ticker,
                    "region": region,
                    "period": f"{start_date} ~ {end_date}"
                }
            )

        # Handle both response formats:
        # Format 1: {ticker: [records]} (direct data)
        # Format 2: {"success": True, "data": {ticker: [records]}} (wrapped)
        if "success" in result and "data" in result:
            # Wrapped format
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                raise DataNotFoundError(
                    message=f"Failed to fetch OHLCV data: {error_msg}",
                    details={
                        "ticker": ticker,
                        "region": region,
                        "period": f"{start_date} ~ {end_date}"
                    }
                )
            data = result.get("data", {})
        else:
            # Direct format - result is already the data dict
            data = result

        if ticker not in data or not data[ticker]:
            raise DataNotFoundError(
                message=f"No OHLCV data found for ticker: {ticker}",
                details={
                    "ticker": ticker,
                    "region": region,
                    "period": f"{start_date} ~ {end_date}",
                    "hint": "종목 코드와 지역 설정을 확인해주세요."
                }
            )

        # Convert to mplfinance format
        ohlcv_list = data[ticker]
        df = self._to_mplfinance_df(ohlcv_list)

        # Validate sufficient data
        if len(df) < self.MIN_TRADING_DAYS:
            raise DataNotFoundError(
                message=f"Insufficient data for chart generation. "
                        f"Found {len(df)} days, minimum required: {self.MIN_TRADING_DAYS}",
                details={
                    "ticker": ticker,
                    "available_days": len(df),
                    "required_days": self.MIN_TRADING_DAYS
                }
            )

        logger.info(
            "ohlcv_data_fetched",
            ticker=ticker,
            region=region,
            trading_days=len(df),
            date_range=f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}"
        )

        return df

    def _to_mplfinance_df(self, ohlcv_data: List[Dict]) -> pd.DataFrame:
        """
        Convert OHLCV list to mplfinance-compatible DataFrame.

        Args:
            ohlcv_data: List of dicts with keys: date, open, high, low, close, volume

        Returns:
            DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume
        """
        df = pd.DataFrame(ohlcv_data)

        # Standardize column names (handle both lowercase and mixed case)
        column_mapping = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }

        # Apply mapping for lowercase columns
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # Ensure required columns exist
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in OHLCV data: {missing}")

        # Convert Date to datetime and set as index
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df = df.sort_index()

        # Select only required columns
        df = df[["Open", "High", "Low", "Close", "Volume"]]

        # Ensure numeric types
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Remove rows with NaN values
        df = df.dropna()

        return df

    async def _get_ticker_name(self, ticker: str, region: str) -> Optional[str]:
        """
        Get ticker name from database (optional enhancement).

        Returns:
            Ticker name or None if not found
        """
        try:
            # Try to get ticker info from system adapter or database
            # This is an optional enhancement - returns None if not available
            return None  # TODO: Implement ticker name lookup
        except Exception:
            return None

    async def get_available_indicators(self) -> Dict[str, str]:
        """
        Get list of available indicators with descriptions.

        Returns:
            Dict of indicator_code -> description
        """
        return {
            "ma": "Moving Averages (MA20, MA50, MA200) - Trend indicators",
            "rsi": "Relative Strength Index (14-period) - Momentum oscillator",
            "macd": "MACD (12, 26, 9) - Trend and momentum indicator",
            "bollinger": "Bollinger Bands (20, 2) - Volatility indicator",
            "volume": "Volume bars - Trading activity"
        }

    async def get_supported_regions(self) -> List[str]:
        """Get list of supported market regions."""
        return sorted(self.SUPPORTED_REGIONS)

    def _normalize_ticker(self, ticker: str, region: str) -> str:
        """
        Normalize ticker format for database lookup.

        Different regions store tickers with different formats:
        - HK: 0700 → 0700.HK (Hong Kong Stock Exchange)
        - CN: 600519 → 600519.SS (Shanghai), 000001 → 000001.SZ (Shenzhen)
        - Other regions: No transformation needed

        Args:
            ticker: User-provided ticker symbol
            region: Market region code

        Returns:
            Normalized ticker for database lookup
        """
        # Skip if ticker already has suffix
        if "." in ticker:
            return ticker

        ticker = ticker.strip().upper()

        if region == "HK":
            # Hong Kong: Add .HK suffix
            # Pad with leading zeros if needed (e.g., 700 → 0700.HK)
            ticker_num = ticker.lstrip("0") or "0"
            padded = ticker_num.zfill(4)
            return f"{padded}.HK"

        elif region == "CN":
            # China: Determine exchange based on ticker prefix
            # Shanghai (SS): Starts with 6 (main board), 9 (B-shares)
            # Shenzhen (SZ): Starts with 0 (main board), 3 (ChiNext), 2 (B-shares)
            if ticker.startswith(("6", "9")):
                return f"{ticker}.SS"
            elif ticker.startswith(("0", "3", "2")):
                return f"{ticker}.SZ"
            else:
                # Unknown prefix, try Shanghai first
                logger.warning(
                    "cn_ticker_unknown_prefix",
                    ticker=ticker,
                    message="Unknown CN ticker prefix, defaulting to Shanghai (.SS)"
                )
                return f"{ticker}.SS"

        # Other regions (KR, US, JP, VN): No transformation needed
        return ticker

    def _get_display_ticker(self, normalized_ticker: str, region: str) -> str:
        """
        Get display-friendly ticker (without exchange suffix).

        Args:
            normalized_ticker: Database ticker format
            region: Market region

        Returns:
            User-friendly ticker for display
        """
        if region in ("HK", "CN"):
            # Remove exchange suffix for display
            return normalized_ticker.split(".")[0]
        return normalized_ticker
