# mcp_server/adapters/return_comparison_adapter.py
"""
Return Comparison Adapter for MCP Server

Connects data retrieval (DataAdapter) with chart rendering (ReturnComparisonGenerator)
to produce multi-stock return comparison charts for MCP tool responses.

Author: Spock MCP Server
Date: 2026-01-20
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

import pandas as pd
import structlog

from .data_adapter import DataAdapter
from ..generators.return_comparison_generator import ReturnComparisonGenerator
from ..utils.errors import DataNotFoundError, ValidationError

logger = structlog.get_logger()


class ReturnComparisonAdapter:
    """
    Return comparison adapter.

    Orchestrates data retrieval and chart generation for multi-stock
    return comparison visualization.

    Usage:
        adapter = ReturnComparisonAdapter()
        png_bytes, metrics, names = await adapter.generate_comparison(
            tickers=["005930", "000660"],
            region="KR",
            period_days=365,
            include_benchmark=True,
            benchmark_info={"ticker": "069500", "name": "KODEX 200"}
        )
    """

    # Minimum trading days required for comparison
    MIN_TRADING_DAYS = 10

    # Supported regions
    SUPPORTED_REGIONS = {"KR", "US", "HK", "CN", "JP", "VN"}

    def __init__(self, data_adapter: Optional[DataAdapter] = None):
        """
        Initialize ReturnComparisonAdapter.

        Args:
            data_adapter: DataAdapter instance (creates new if not provided)
        """
        self.data_adapter = data_adapter or DataAdapter()
        self.chart_generator = ReturnComparisonGenerator()

    async def generate_comparison(
        self,
        tickers: List[str],
        region: str = "KR",
        period_days: int = 365,
        include_benchmark: bool = True,
        benchmark_info: Optional[Dict[str, str]] = None
    ) -> Tuple[bytes, Dict[str, Any], Dict[str, str]]:
        """
        Generate return comparison chart (Google Finance style).

        Args:
            tickers: List of ticker symbols to compare
            region: Market region (KR, US, HK, CN, JP, VN)
            period_days: Number of days for comparison period
            include_benchmark: Whether to include market benchmark
            benchmark_info: Dict with 'ticker' and 'name' for benchmark

        Returns:
            Tuple of:
                - PNG image bytes
                - Metrics dict with return statistics
                - Ticker names dict {ticker: display_name}

        Raises:
            ValidationError: Invalid input parameters
            DataNotFoundError: No data found for ticker(s)
        """
        # Validate inputs
        self._validate_inputs(tickers, region)

        # Normalize tickers for database lookup
        normalized_tickers = [
            self._normalize_ticker(t, region) for t in tickers
        ]
        ticker_mapping = dict(zip(normalized_tickers, tickers))

        logger.info(
            "return_comparison_started",
            tickers=tickers,
            normalized_tickers=normalized_tickers,
            region=region,
            period_days=period_days,
            include_benchmark=include_benchmark
        )

        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")

        # Fetch OHLCV data for all tickers
        price_data = {}
        ticker_names = {}

        for norm_ticker, orig_ticker in ticker_mapping.items():
            try:
                df = await self._fetch_ohlcv_data(
                    norm_ticker, region, start_date, end_date
                )
                price_data[orig_ticker] = df

                # Try to get ticker name
                name = await self._get_ticker_name(norm_ticker, region)
                ticker_names[orig_ticker] = name or orig_ticker

            except DataNotFoundError as e:
                logger.warning(
                    "ticker_data_not_found",
                    ticker=norm_ticker,
                    original=orig_ticker,
                    error=str(e)
                )
                # Continue with other tickers, but need at least 2
                continue

        # Validate we have enough tickers
        if len(price_data) < 2:
            found_tickers = list(price_data.keys())
            missing_tickers = [t for t in tickers if t not in price_data]
            raise DataNotFoundError(
                message=f"데이터를 찾을 수 있는 종목이 2개 미만입니다.",
                details={
                    "found_tickers": found_tickers,
                    "missing_tickers": missing_tickers,
                    "region": region,
                    "period": f"{start_date} ~ {end_date}"
                }
            )

        # Fetch benchmark data if requested
        benchmark_data = None
        if include_benchmark and benchmark_info:
            try:
                benchmark_ticker = benchmark_info["ticker"]
                norm_benchmark = self._normalize_ticker(benchmark_ticker, region)
                benchmark_data = await self._fetch_ohlcv_data(
                    norm_benchmark, region, start_date, end_date
                )
                logger.info(
                    "benchmark_data_fetched",
                    ticker=benchmark_ticker,
                    trading_days=len(benchmark_data)
                )
            except Exception as e:
                logger.warning(
                    "benchmark_data_failed",
                    ticker=benchmark_info.get("ticker"),
                    error=str(e)
                )
                benchmark_data = None

        # Generate chart (Google Finance style)
        try:
            png_bytes, metrics = self.chart_generator.generate(
                price_data=price_data,
                ticker_names=ticker_names,
                benchmark_data=benchmark_data,
                benchmark_name=benchmark_info["name"] if benchmark_info else "Benchmark",
                region=region
            )

            logger.info(
                "return_comparison_completed",
                tickers=list(price_data.keys()),
                region=region,
                image_size_bytes=len(png_bytes)
            )

            return png_bytes, metrics, ticker_names

        except Exception as e:
            logger.error(
                "return_comparison_failed",
                tickers=tickers,
                region=region,
                error=str(e)
            )
            raise

    def _validate_inputs(self, tickers: List[str], region: str) -> None:
        """Validate input parameters."""
        if not tickers:
            raise ValidationError("At least one ticker is required")

        if len(tickers) < 2:
            raise ValidationError("At least 2 tickers required for comparison")

        if len(tickers) > 5:
            raise ValidationError(
                f"Maximum 5 tickers allowed, got {len(tickers)}"
            )

        if region not in self.SUPPORTED_REGIONS:
            raise ValidationError(
                f"Unsupported region: {region}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_REGIONS))}"
            )

    def _normalize_ticker(self, ticker: str, region: str) -> str:
        """
        Normalize ticker format for database lookup.

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
            ticker_num = ticker.lstrip("0") or "0"
            padded = ticker_num.zfill(4)
            return f"{padded}.HK"

        elif region == "CN":
            # China: Determine exchange based on ticker prefix
            if ticker.startswith(("6", "9")):
                return f"{ticker}.SS"
            elif ticker.startswith(("0", "3", "2")):
                return f"{ticker}.SZ"
            else:
                return f"{ticker}.SS"

        # Other regions (KR, US, JP, VN): No transformation needed
        return ticker

    async def _fetch_ohlcv_data(
        self,
        ticker: str,
        region: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data and convert to DataFrame format.

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

        if result is None:
            raise DataNotFoundError(
                message=f"Failed to fetch OHLCV data: No response",
                details={
                    "ticker": ticker,
                    "region": region,
                    "period": f"{start_date} ~ {end_date}"
                }
            )

        # Handle both response formats
        if "success" in result and "data" in result:
            if not result.get("success", False):
                raise DataNotFoundError(
                    message=f"Failed to fetch OHLCV data: {result.get('error', 'Unknown')}",
                    details={"ticker": ticker, "region": region}
                )
            data = result.get("data", {})
        else:
            data = result

        if ticker not in data or not data[ticker]:
            raise DataNotFoundError(
                message=f"No OHLCV data found for ticker: {ticker}",
                details={
                    "ticker": ticker,
                    "region": region,
                    "period": f"{start_date} ~ {end_date}"
                }
            )

        # Convert to DataFrame
        ohlcv_list = data[ticker]
        df = self._to_dataframe(ohlcv_list)

        # Validate sufficient data
        if len(df) < self.MIN_TRADING_DAYS:
            raise DataNotFoundError(
                message=f"Insufficient data for comparison. "
                        f"Found {len(df)} days, minimum required: {self.MIN_TRADING_DAYS}",
                details={
                    "ticker": ticker,
                    "available_days": len(df),
                    "required_days": self.MIN_TRADING_DAYS
                }
            )

        return df

    def _to_dataframe(self, ohlcv_data: List[Dict]) -> pd.DataFrame:
        """
        Convert OHLCV list to DataFrame.

        Args:
            ohlcv_data: List of dicts with keys: date, open, high, low, close, volume

        Returns:
            DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume
        """
        df = pd.DataFrame(ohlcv_data)

        # Standardize column names
        column_mapping = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }

        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # Ensure required columns
        required = ["Date", "Close"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in OHLCV data: {missing}")

        # Convert Date and set as index
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
        df = df.sort_index()

        # Ensure Close is numeric
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

        # Remove rows with NaN Close values
        df = df.dropna(subset=["Close"])

        return df

    async def _get_ticker_name(self, ticker: str, region: str) -> Optional[str]:
        """
        Get ticker name from database.

        Returns:
            Ticker name or None if not found
        """
        try:
            # Try to get ticker info from tickers table
            # This would require a new method in DataAdapter
            # For now, return None and use ticker as display name
            return None
        except Exception:
            return None


# Singleton instance for reuse
_adapter_instance: Optional[ReturnComparisonAdapter] = None


def get_return_comparison_adapter(
    data_adapter: Optional[DataAdapter] = None
) -> ReturnComparisonAdapter:
    """
    Get ReturnComparisonAdapter instance (singleton pattern).

    Args:
        data_adapter: Optional DataAdapter to inject

    Returns:
        ReturnComparisonAdapter instance
    """
    global _adapter_instance
    if _adapter_instance is None or data_adapter is not None:
        _adapter_instance = ReturnComparisonAdapter(data_adapter)
    return _adapter_instance
