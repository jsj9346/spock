"""
Abstract Base Class for Backtest Data Providers

Purpose:
    Define consistent interface for all data sources used in backtesting.
    Supports pluggable architecture (SQLite, PostgreSQL, Cloud, APIs).

Design Philosophy:
    - Pluggable Architecture: Easy to add new data sources
    - Consistent Interface: All providers implement same methods
    - Point-in-Time Data: Prevent look-ahead bias
    - Performance: Support batch queries and caching

Key Methods:
    - get_ohlcv(): Get OHLCV data for single ticker
    - get_ohlcv_batch(): Get OHLCV data for multiple tickers (optimized)
    - get_fundamentals(): Get fundamental data (P/E, ROE, etc.)
    - get_technical_indicators(): Get pre-calculated indicators
    - get_available_tickers(): Get tradable universe for date range

Interface Contract:
    All implementations must:
    1. Return data sorted by date ascending
    2. Handle missing data gracefully (return empty DataFrame)
    3. Support point-in-time data retrieval (no look-ahead bias)
    4. Implement efficient batch queries when possible
    5. Document query performance characteristics

Author: Spock Quant Platform
Date: 2025-10-26
Version: 1.0.0
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Optional, Set
import pandas as pd
from loguru import logger


class BaseDataProvider(ABC):
    """
    Abstract base class for backtest data providers.

    All data providers (SQLite, PostgreSQL, Cloud) must implement this interface.

    Attributes:
        cache_enabled (bool): Whether to enable in-memory caching
        cache (dict): In-memory cache for repeated queries
    """

    def __init__(self, cache_enabled: bool = True):
        """
        Initialize data provider.

        Args:
            cache_enabled: Enable in-memory caching for repeated queries
        """
        self.cache_enabled = cache_enabled
        self.cache: Dict[str, pd.DataFrame] = {}
        logger.info(f"Initialized {self.__class__.__name__} (cache={'enabled' if cache_enabled else 'disabled'})")

    @abstractmethod
    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data for single ticker.

        Args:
            ticker: Stock ticker symbol (e.g., '005930', 'AAPL')
            region: Market region code (KR, US, CN, HK, JP, VN)
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Data timeframe ('1d', '1h', '15m', etc.)

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            - Sorted by date ascending
            - Empty DataFrame if no data available

        Raises:
            ValueError: If parameters are invalid
            ConnectionError: If database/API connection fails

        Performance:
            Implementation-specific. Document expected query time.

        Point-in-Time Guarantee:
            Must return data available as of each date (no look-ahead bias).
        """
        pass

    @abstractmethod
    def get_ohlcv_batch(
        self,
        tickers: List[str],
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple tickers (optimized batch query).

        Args:
            tickers: List of ticker symbols
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Data timeframe

        Returns:
            Dictionary mapping ticker -> DataFrame
            - Each DataFrame has same format as get_ohlcv()
            - Missing tickers return empty DataFrame

        Performance:
            Should be 10-20x faster than calling get_ohlcv() in loop.
            Implementations should use bulk queries when possible.

        Example:
            data = provider.get_ohlcv_batch(
                tickers=['005930', '035420'],
                region='KR',
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31)
            )
            samsung_df = data['005930']
            naver_df = data['035420']
        """
        pass

    @abstractmethod
    def get_fundamentals(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """
        Get fundamental data for single ticker.

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with columns: [date, pe_ratio, pb_ratio, roe, debt_to_equity, ...]
            - Sorted by date ascending
            - Empty DataFrame if no data available

        Point-in-Time Guarantee:
            Must return data available as of each date (e.g., quarterly reports
            are only available after filing date, not report date).

        Note:
            Fundamental data typically updated quarterly or annually.
            Forward-fill to daily frequency may be needed for backtesting.
        """
        pass

    @abstractmethod
    def get_technical_indicators(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get pre-calculated technical indicators.

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            indicators: List of indicator names (e.g., ['rsi', 'macd', 'bb_upper'])
                       If None, return all available indicators

        Returns:
            DataFrame with columns: [date, indicator1, indicator2, ...]
            - Sorted by date ascending
            - Empty DataFrame if no data available

        Performance:
            Using pre-calculated indicators is 10-100x faster than
            calculating on-the-fly during backtesting.

        Example:
            indicators = provider.get_technical_indicators(
                ticker='005930',
                region='KR',
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31),
                indicators=['rsi', 'macd_signal', 'bb_upper']
            )
        """
        pass

    @abstractmethod
    def get_available_tickers(
        self,
        region: str,
        start_date: date,
        end_date: date,
        min_volume: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> List[str]:
        """
        Get list of tickers available for trading in date range.

        Args:
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            min_volume: Minimum average daily volume filter (optional)
            min_price: Minimum price filter (optional, exclude penny stocks)

        Returns:
            List of ticker symbols that have data in the date range
            and meet the filter criteria

        Point-in-Time Guarantee:
            Must return tickers that were actually tradable during the period.
            Exclude delisted stocks, stocks added after start_date, etc.

        Performance:
            Should be fast (<1s) for typical queries.

        Example:
            # Get all liquid KR stocks (>1M daily volume, price >5,000)
            tickers = provider.get_available_tickers(
                region='KR',
                start_date=date(2020, 1, 1),
                end_date=date(2023, 12, 31),
                min_volume=1_000_000,
                min_price=5000
            )
        """
        pass

    def clear_cache(self):
        """
        Clear in-memory cache.

        Use when memory pressure is high or when fresh data is required.
        """
        if self.cache_enabled:
            cache_size = len(self.cache)
            self.cache.clear()
            logger.info(f"Cleared cache ({cache_size} entries)")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - enabled: Whether caching is enabled
            - size: Number of cached queries
            - memory_mb: Approximate memory usage in MB
        """
        if not self.cache_enabled:
            return {'enabled': False, 'size': 0, 'memory_mb': 0}

        # Estimate memory usage (rough approximation)
        memory_mb = sum(
            df.memory_usage(deep=True).sum() / (1024 * 1024)
            for df in self.cache.values()
        )

        return {
            'enabled': True,
            'size': len(self.cache),
            'memory_mb': round(memory_mb, 2)
        }

    def _generate_cache_key(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str,
        data_type: str = 'ohlcv'
    ) -> str:
        """
        Generate cache key for query parameters.

        Args:
            ticker: Ticker symbol
            region: Region code
            start_date: Start date
            end_date: End date
            timeframe: Timeframe
            data_type: Type of data ('ohlcv', 'fundamentals', 'indicators')

        Returns:
            Cache key string
        """
        return f"{data_type}_{ticker}_{region}_{start_date}_{end_date}_{timeframe}"

    def _validate_date_range(self, start_date: date, end_date: date):
        """
        Validate date range parameters.

        Args:
            start_date: Start date
            end_date: End date

        Raises:
            ValueError: If date range is invalid
        """
        if start_date > end_date:
            raise ValueError(f"Invalid date range: start_date ({start_date}) > end_date ({end_date})")

    def _validate_ticker(self, ticker: str, region: str):
        """
        Validate ticker and region parameters.

        Args:
            ticker: Ticker symbol
            region: Region code

        Raises:
            ValueError: If ticker or region is invalid
        """
        if not ticker or not isinstance(ticker, str):
            raise ValueError(f"Invalid ticker: {ticker}")

        valid_regions = {'KR', 'US', 'CN', 'HK', 'JP', 'VN'}
        if region not in valid_regions:
            raise ValueError(f"Invalid region: {region}. Must be one of {valid_regions}")

    def __repr__(self) -> str:
        """String representation of data provider."""
        cache_stats = self.get_cache_stats()
        return (
            f"{self.__class__.__name__}("
            f"cache_enabled={self.cache_enabled}, "
            f"cache_size={cache_stats['size']}, "
            f"cache_memory_mb={cache_stats['memory_mb']})"
        )
