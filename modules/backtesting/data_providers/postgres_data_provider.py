"""
PostgreSQL Data Provider for Backtesting Engine

Implements BaseDataProvider interface for PostgreSQL + TimescaleDB backend.
Provides high-performance data access with connection pooling, hypertable
optimization, and multi-region support.

Key Features:
    - PostgreSQL + TimescaleDB integration
    - Connection pooling (10-30 connections)
    - Hypertable query optimization
    - Continuous aggregates support
    - Multi-region support (built-in)
    - Batch query optimization
    - In-memory caching via BaseDataProvider

Performance Targets:
    - Single ticker query: <100ms
    - Batch query (20 tickers): <500ms
    - Cache hit rate: >80%

Author: Spock Quant Platform
Date: 2025-10-26
"""

import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional
from loguru import logger

from .base_data_provider import BaseDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager


class PostgresDataProvider(BaseDataProvider):
    """
    PostgreSQL + TimescaleDB data provider for backtesting engine.

    Leverages existing PostgresDatabaseManager infrastructure for:
        - Connection pooling (ThreadedConnectionPool)
        - Hypertable queries with chunk exclusion
        - COPY command for bulk operations
        - Multi-region composite keys

    Inherits caching, validation, and helper methods from BaseDataProvider.

    Example:
        >>> from modules.db_manager_postgres import PostgresDatabaseManager
        >>> db_manager = PostgresDatabaseManager(
        ...     host='localhost',
        ...     database='quant_platform'
        ... )
        >>> provider = PostgresDataProvider(db_manager, cache_enabled=True)
        >>>
        >>> # Get OHLCV data for single ticker
        >>> df = provider.get_ohlcv('005930', 'KR', date(2024,1,1), date(2024,12,31))
        >>>
        >>> # Get OHLCV data for multiple tickers (optimized batch)
        >>> tickers = ['005930', '035420', '051910']
        >>> data = provider.get_ohlcv_batch(tickers, 'KR', date(2024,1,1), date(2024,12,31))
    """

    def __init__(self, db_manager: PostgresDatabaseManager, cache_enabled: bool = True):
        """
        Initialize PostgreSQL data provider.

        Args:
            db_manager: PostgresDatabaseManager instance with connection pooling
            cache_enabled: Enable in-memory caching (default: True)

        Raises:
            ValueError: If db_manager is None or invalid
            ConnectionError: If cannot connect to PostgreSQL
        """
        super().__init__(cache_enabled=cache_enabled)

        if db_manager is None:
            raise ValueError("db_manager cannot be None")

        self.db = db_manager

        # Test database connection
        try:
            if not self.db.test_connection():
                raise ConnectionError("Cannot connect to PostgreSQL database")
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            raise ConnectionError(f"PostgreSQL connection failed: {e}")

        logger.info(
            f"PostgresDataProvider initialized "
            f"(host={self.db.host}, database={self.db.database}, cache_enabled={cache_enabled})"
        )

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data for single ticker from PostgreSQL hypertable.

        Uses TimescaleDB chunk exclusion for fast queries on partitioned data.
        Results are cached for repeated queries.

        Args:
            ticker: Stock ticker symbol (e.g., '005930', 'AAPL')
            region: Market region code ('KR', 'US', 'CN', 'HK', 'JP', 'VN')
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Timeframe ('1d' for daily, '1h' for hourly)

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            Sorted by date ascending, date column as datetime64[ns]

        Raises:
            ValueError: If ticker/region invalid or date range invalid
            DatabaseError: If query fails

        Example:
            >>> provider = PostgresDataProvider(db_manager)
            >>> df = provider.get_ohlcv('005930', 'KR', date(2024,1,1), date(2024,12,31))
            >>> print(df.head())
                   date     open     high      low    close     volume
            0 2024-01-02  75000.0  76000.0  74500.0  75500.0  10000000
            1 2024-01-03  75500.0  76500.0  75000.0  76000.0  12000000
        """
        # Validate inputs
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        # Check cache
        cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit: {ticker} ({region})")
            return self.cache[cache_key].copy()

        # Query PostgreSQL hypertable
        try:
            logger.debug(
                f"Querying PostgreSQL: ticker={ticker}, region={region}, "
                f"start={start_date}, end={end_date}, timeframe={timeframe}"
            )

            # Leverage db_manager's get_ohlcv_data method
            # This method already handles:
            # - Hypertable queries with chunk exclusion
            # - Connection pooling
            # - Parameter binding
            # - Date conversion
            df = self.db.get_ohlcv_data(
                ticker=ticker,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                timeframe=timeframe,
                region=region
            )

            # Ensure date column is datetime
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)

            # Select and order required columns
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not df.empty and len(df) > 0:
                # Only select columns that exist in the DataFrame
                available_cols = [col for col in required_cols if col in df.columns]
                if available_cols:
                    df = df[available_cols]
                else:
                    # No required columns found
                    df = pd.DataFrame(columns=required_cols)
            else:
                # Return empty DataFrame with correct schema
                df = pd.DataFrame(columns=required_cols)

            # Cache result
            if self.cache_enabled:
                self.cache[cache_key] = df.copy()

            logger.debug(f"Retrieved {len(df)} rows for {ticker} ({region})")
            return df

        except Exception as e:
            logger.error(f"Failed to get OHLCV data for {ticker} ({region}): {e}")
            raise

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

        Uses SQL IN clause for 10-20x speedup over sequential queries.
        Leverages PostgreSQL connection pooling and TimescaleDB partitioning.

        Args:
            tickers: List of ticker symbols
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Timeframe ('1d' for daily)

        Returns:
            Dictionary mapping ticker -> DataFrame
            Each DataFrame has columns: [date, open, high, low, close, volume]

        Example:
            >>> tickers = ['005930', '035420', '051910']
            >>> data = provider.get_ohlcv_batch(tickers, 'KR', date(2024,1,1), date(2024,12,31))
            >>> print(data['005930'].head())
        """
        # Validate date range
        self._validate_date_range(start_date, end_date)

        if not tickers:
            return {}

        # Check for cached tickers
        result = {}
        uncached_tickers = []

        for ticker in tickers:
            try:
                self._validate_ticker(ticker, region)
                cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)

                if self.cache_enabled and cache_key in self.cache:
                    result[ticker] = self.cache[cache_key].copy()
                    logger.debug(f"Cache hit: {ticker} ({region})")
                else:
                    uncached_tickers.append(ticker)
            except ValueError as e:
                logger.warning(f"Skipping invalid ticker {ticker}: {e}")
                continue

        # Batch query for uncached tickers
        if uncached_tickers:
            try:
                logger.debug(
                    f"Batch query PostgreSQL: {len(uncached_tickers)} tickers, "
                    f"region={region}, start={start_date}, end={end_date}"
                )

                # Build batch query with IN clause
                query = """
                    SELECT ticker, date, open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker = ANY(%s)
                      AND region = %s
                      AND timeframe = %s
                      AND date >= %s::DATE
                      AND date <= %s::DATE
                    ORDER BY ticker, date ASC
                """

                params = (
                    uncached_tickers,
                    region,
                    timeframe,
                    start_date.isoformat(),
                    end_date.isoformat()
                )

                # Execute batch query
                with self.db._get_connection() as conn:
                    df_all = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

                # Split by ticker
                if not df_all.empty:
                    for ticker in uncached_tickers:
                        df_ticker = df_all[df_all['ticker'] == ticker].copy()
                        df_ticker = df_ticker.drop(columns=['ticker']).reset_index(drop=True)

                        # Select required columns
                        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                        df_ticker = df_ticker[required_cols]

                        result[ticker] = df_ticker

                        # Cache result
                        if self.cache_enabled:
                            cache_key = self._generate_cache_key(
                                ticker, region, start_date, end_date, timeframe
                            )
                            self.cache[cache_key] = df_ticker.copy()
                else:
                    # No data found for any ticker
                    for ticker in uncached_tickers:
                        result[ticker] = pd.DataFrame(
                            columns=['date', 'open', 'high', 'low', 'close', 'volume']
                        )

                logger.debug(f"Batch query completed: {len(uncached_tickers)} tickers")

            except Exception as e:
                logger.error(f"Batch query failed: {e}")
                # Fallback to sequential queries
                logger.warning("Falling back to sequential queries")
                for ticker in uncached_tickers:
                    try:
                        result[ticker] = self.get_ohlcv(ticker, region, start_date, end_date, timeframe)
                    except Exception as ticker_error:
                        logger.error(f"Failed to get data for {ticker}: {ticker_error}")
                        result[ticker] = pd.DataFrame(
                            columns=['date', 'open', 'high', 'low', 'close', 'volume']
                        )

        return result

    def get_fundamentals(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """
        Get fundamental data for single ticker from PostgreSQL.

        Queries ticker_fundamentals table for financial metrics.

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with columns: [date, pe_ratio, pb_ratio, roe, debt_to_equity, ...]
            Returns empty DataFrame if no fundamentals available

        Example:
            >>> df = provider.get_fundamentals('005930', 'KR', date(2024,1,1), date(2024,12,31))
            >>> print(df[['date', 'pe_ratio', 'roe']].head())
        """
        # Validate inputs
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        # Check cache
        cache_key = self._generate_cache_key(
            ticker, region, start_date, end_date, '1d', data_type='fundamentals'
        )
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit: fundamentals for {ticker} ({region})")
            return self.cache[cache_key].copy()

        # Query fundamentals table
        try:
            logger.debug(
                f"Querying fundamentals: ticker={ticker}, region={region}, "
                f"start={start_date}, end={end_date}"
            )

            # Leverage db_manager's get_fundamentals method
            df = self.db.get_fundamentals(
                ticker=ticker,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                region=region
            )

            # Ensure date column is datetime
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)

            # Cache result
            if self.cache_enabled:
                self.cache[cache_key] = df.copy()

            logger.debug(f"Retrieved {len(df)} fundamental records for {ticker} ({region})")
            return df

        except Exception as e:
            logger.error(f"Failed to get fundamentals for {ticker} ({region}): {e}")
            # Return empty DataFrame with date column
            return pd.DataFrame(columns=['date'])

    def get_technical_indicators(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get pre-calculated technical indicators from PostgreSQL.

        Queries technical_analysis table for indicators like RSI, MACD, Bollinger Bands.

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            indicators: List of indicator names (None = all indicators)
                       e.g., ['rsi', 'macd', 'bb_upper', 'bb_lower']

        Returns:
            DataFrame with columns: [date, rsi, macd, bb_upper, bb_lower, ...]
            Returns empty DataFrame if no indicators available

        Example:
            >>> df = provider.get_technical_indicators(
            ...     '005930', 'KR', date(2024,1,1), date(2024,12,31),
            ...     indicators=['rsi', 'macd']
            ... )
            >>> print(df[['date', 'rsi', 'macd']].head())
        """
        # Validate inputs
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        # Check cache
        indicators_key = ','.join(sorted(indicators)) if indicators else 'all'
        cache_key = self._generate_cache_key(
            ticker, region, start_date, end_date, '1d', data_type=f'indicators:{indicators_key}'
        )
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit: indicators for {ticker} ({region})")
            return self.cache[cache_key].copy()

        # Query technical_analysis table
        try:
            logger.debug(
                f"Querying technical indicators: ticker={ticker}, region={region}, "
                f"indicators={indicators}"
            )

            # Build query
            query = """
                SELECT *
                FROM technical_analysis
                WHERE ticker = %s
                  AND region = %s
                  AND date >= %s::DATE
                  AND date <= %s::DATE
                ORDER BY date ASC
            """

            params = (ticker, region, start_date.isoformat(), end_date.isoformat())

            # Execute query
            with self.db._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

            # Filter indicators if specified
            if not df.empty and indicators:
                # Keep date + requested indicators
                available_cols = set(df.columns)
                requested_cols = {'date'} | {ind for ind in indicators if ind in available_cols}
                df = df[list(requested_cols)]

            # Ensure date column is datetime
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)

            # Cache result
            if self.cache_enabled:
                self.cache[cache_key] = df.copy()

            logger.debug(f"Retrieved {len(df)} indicator records for {ticker} ({region})")
            return df

        except Exception as e:
            logger.error(f"Failed to get technical indicators for {ticker} ({region}): {e}")
            # Return empty DataFrame with date column
            return pd.DataFrame(columns=['date'])

    def get_available_tickers(
        self,
        region: str,
        start_date: date,
        end_date: date,
        min_volume: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> List[str]:
        """
        Get list of tickers available for trading in specified date range.

        Filters tickers by:
            - Data availability in date range
            - Minimum average volume (if specified)
            - Minimum price (if specified)

        Args:
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            min_volume: Minimum average daily volume (default: None)
            min_price: Minimum closing price (default: None)

        Returns:
            List of ticker symbols meeting criteria

        Example:
            >>> # Get all KR tickers with data in 2024
            >>> tickers = provider.get_available_tickers('KR', date(2024,1,1), date(2024,12,31))
            >>>
            >>> # Get liquid KR stocks (avg volume > 1M, price > 10000)
            >>> liquid = provider.get_available_tickers(
            ...     'KR', date(2024,1,1), date(2024,12,31),
            ...     min_volume=1000000, min_price=10000
            ... )
        """
        # Validate inputs
        if region not in ['KR', 'US', 'CN', 'HK', 'JP', 'VN']:
            raise ValueError(f"Invalid region: {region}")
        self._validate_date_range(start_date, end_date)

        # Check cache
        cache_key = self._generate_cache_key(
            region, region, start_date, end_date, '1d',
            data_type=f'tickers:vol={min_volume}:price={min_price}'
        )
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit: available tickers for {region}")
            return self.cache[cache_key].copy()

        # Query tickers with filters
        try:
            logger.debug(
                f"Querying available tickers: region={region}, "
                f"min_volume={min_volume}, min_price={min_price}"
            )

            # Build query with filters
            query = """
                SELECT DISTINCT ticker
                FROM ohlcv_data
                WHERE region = %s
                  AND date >= %s::DATE
                  AND date <= %s::DATE
            """
            params = [region, start_date.isoformat(), end_date.isoformat()]

            # Add volume filter
            if min_volume is not None:
                query += """
                    AND ticker IN (
                        SELECT ticker
                        FROM ohlcv_data
                        WHERE region = %s
                          AND date >= %s::DATE
                          AND date <= %s::DATE
                        GROUP BY ticker
                        HAVING AVG(volume) >= %s
                    )
                """
                params.extend([region, start_date.isoformat(), end_date.isoformat(), min_volume])

            # Add price filter
            if min_price is not None:
                query += """
                    AND ticker IN (
                        SELECT ticker
                        FROM ohlcv_data
                        WHERE region = %s
                          AND date >= %s::DATE
                          AND date <= %s::DATE
                          AND close >= %s
                    )
                """
                params.extend([region, start_date.isoformat(), end_date.isoformat(), min_price])

            query += " ORDER BY ticker ASC"

            # Execute query
            with self.db._get_connection() as conn:
                df = pd.read_sql_query(query, conn, params=tuple(params))

            tickers = df['ticker'].tolist() if not df.empty else []

            # Cache result
            if self.cache_enabled:
                self.cache[cache_key] = tickers.copy()

            logger.debug(f"Found {len(tickers)} available tickers for {region}")
            return tickers

        except Exception as e:
            logger.error(f"Failed to get available tickers for {region}: {e}")
            return []

    def __repr__(self) -> str:
        """String representation of provider."""
        return (
            f"PostgresDataProvider("
            f"host={self.db.host}, "
            f"database={self.db.database}, "
            f"cache_enabled={self.cache_enabled}, "
            f"cache_size={len(self.cache)}"
            f")"
        )
