"""
SQLite Data Provider

Purpose:
    Adapter for SQLite database (backward compatibility with Spock).
    Implements BaseDataProvider interface using existing SQLite schema.

Design Philosophy:
    - Backward Compatibility: Reuse existing HistoricalDataProvider logic
    - Performance: Maintain in-memory caching for fast access
    - Migration Path: Enable gradual transition to PostgreSQL

Key Features:
    - Load OHLCV data with technical indicators from SQLite
    - In-memory caching for fast iteration
    - Point-in-time data snapshots (no look-ahead bias)
    - Support multi-region queries

Performance:
    - Query time: <1s for 250 days × 100 tickers
    - Memory usage: ~100-200 MB for typical backtest (5 years, 100 tickers)

Limitations:
    - 250-day data retention (Spock constraint)
    - No unlimited historical data (use PostgreSQL for this)

Author: Spock Quant Platform
Date: 2025-10-26
Version: 1.0.0
"""

from datetime import date, timedelta
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger

from .base_data_provider import BaseDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager


class SQLiteDataProvider(BaseDataProvider):
    """
    SQLite database provider for backtesting (legacy Spock compatibility).

    Attributes:
        db: SQLite database manager
        data_cache: In-memory cache {ticker: DataFrame} (inherited from base)
        extended_start: Start date for technical indicator calculation
    """

    def __init__(self, db: SQLiteDatabaseManager, cache_enabled: bool = True):
        """
        Initialize SQLite data provider.

        Args:
            db: SQLite database manager instance
            cache_enabled: Enable in-memory caching (default: True)
        """
        super().__init__(cache_enabled=cache_enabled)
        self.db = db
        self.extended_start: Optional[date] = None

        logger.info(f"Initialized SQLiteDataProvider with database: {db.db_path}")

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data for single ticker from SQLite.

        Args:
            ticker: Stock ticker symbol
            region: Market region code (KR, US, CN, HK, JP, VN)
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Data timeframe (only '1d' supported for SQLite)

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            Sorted by date ascending

        Performance:
            <100ms for typical single ticker query

        Note:
            SQLite only supports daily ('1d') timeframe.
            For intraday data, use PostgreSQL provider.
        """
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        if timeframe != '1d':
            logger.warning(f"SQLite only supports '1d' timeframe, got '{timeframe}'. Using '1d'.")

        # Check cache first
        cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit for {ticker} ({region}) [{start_date} to {end_date}]")
            return self.cache[cache_key].copy()

        # Query SQLite database
        conn = self.db._get_connection()
        try:
            # Check if region column exists (legacy schema compatibility)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(ohlcv_data)")
            columns = [row[1] for row in cursor.fetchall()]
            has_region = 'region' in columns

            if has_region:
                query = """
                    SELECT
                        date,
                        open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker = ?
                      AND region = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY date ASC
                """
                params = (ticker, region, start_date.isoformat(), end_date.isoformat())
            else:
                # Legacy schema without region column
                query = """
                    SELECT
                        date,
                        open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY date ASC
                """
                params = (ticker, start_date.isoformat(), end_date.isoformat())

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

            if len(df) == 0:
                logger.warning(f"No data found for {ticker} ({region}) [{start_date} to {end_date}]")
                return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

            # Ensure numeric types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Cache result
            if self.cache_enabled:
                self.cache[cache_key] = df.copy()

            logger.debug(f"Loaded {len(df)} rows for {ticker} ({region}) [{start_date} to {end_date}]")
            return df

        except Exception as e:
            logger.error(f"Error loading OHLCV data for {ticker}: {e}")
            raise
        finally:
            conn.close()

    def get_ohlcv_batch(
        self,
        tickers: List[str],
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple tickers (batch query optimization).

        Args:
            tickers: List of ticker symbols
            region: Market region code
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Data timeframe (only '1d' supported)

        Returns:
            Dictionary mapping ticker -> DataFrame

        Performance:
            10-20x faster than calling get_ohlcv() in loop.
            Uses single batch query with IN clause.
        """
        if not tickers:
            return {}

        if timeframe != '1d':
            logger.warning(f"SQLite only supports '1d' timeframe, got '{timeframe}'. Using '1d'.")

        result = {}

        # Check cache for each ticker
        uncached_tickers = []
        for ticker in tickers:
            cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
            if self.cache_enabled and cache_key in self.cache:
                result[ticker] = self.cache[cache_key].copy()
            else:
                uncached_tickers.append(ticker)

        if not uncached_tickers:
            logger.debug(f"All {len(tickers)} tickers in cache")
            return result

        # Batch query for uncached tickers
        conn = self.db._get_connection()
        try:
            # Check if region column exists (legacy schema compatibility)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(ohlcv_data)")
            columns = [row[1] for row in cursor.fetchall()]
            has_region = 'region' in columns

            placeholders = ','.join('?' for _ in uncached_tickers)

            if has_region:
                query = f"""
                    SELECT
                        ticker, date,
                        open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker IN ({placeholders})
                      AND region = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY ticker, date ASC
                """
                params = tuple(uncached_tickers) + (region, start_date.isoformat(), end_date.isoformat())
            else:
                # Legacy schema without region column
                query = f"""
                    SELECT
                        ticker, date,
                        open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE ticker IN ({placeholders})
                      AND date >= ?
                      AND date <= ?
                    ORDER BY ticker, date ASC
                """
                params = tuple(uncached_tickers) + (start_date.isoformat(), end_date.isoformat())

            df_all = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

            if len(df_all) == 0:
                logger.warning(f"No data found for {len(uncached_tickers)} tickers in batch query")
                # Return empty DataFrames for missing tickers
                for ticker in uncached_tickers:
                    result[ticker] = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                return result

            # Split by ticker
            for ticker in uncached_tickers:
                ticker_df = df_all[df_all['ticker'] == ticker].drop(columns=['ticker']).reset_index(drop=True)

                if len(ticker_df) == 0:
                    ticker_df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                else:
                    # Ensure numeric types
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        ticker_df[col] = pd.to_numeric(ticker_df[col], errors='coerce')

                result[ticker] = ticker_df

                # Cache result
                if self.cache_enabled:
                    cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
                    self.cache[cache_key] = ticker_df.copy()

            logger.debug(f"Loaded {len(uncached_tickers)} tickers from batch query")
            return result

        except Exception as e:
            logger.error(f"Error in batch OHLCV query: {e}")
            raise
        finally:
            conn.close()

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
            Empty DataFrame if table doesn't exist (legacy SQLite may not have this)

        Note:
            SQLite schema may not have ticker_fundamentals table.
            Returns empty DataFrame if table is missing.
        """
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        conn = self.db._get_connection()
        try:
            # Check if ticker_fundamentals table exists
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ticker_fundamentals'
            """)
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                logger.warning("ticker_fundamentals table not found in SQLite database")
                return pd.DataFrame(columns=['date', 'pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity'])

            # Query fundamentals
            query = """
                SELECT
                    date,
                    pe_ratio, pb_ratio, roe, debt_to_equity,
                    current_ratio, quick_ratio, gross_margin, operating_margin
                FROM ticker_fundamentals
                WHERE ticker = ?
                  AND region = ?
                  AND date >= ?
                  AND date <= ?
                ORDER BY date ASC
            """
            params = (ticker, region, start_date.isoformat(), end_date.isoformat())

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])
            return df

        except Exception as e:
            logger.error(f"Error loading fundamentals for {ticker}: {e}")
            return pd.DataFrame(columns=['date', 'pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity'])
        finally:
            conn.close()

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

        Available Indicators:
            - ma5, ma20, ma60, ma120, ma200 (Moving Averages)
            - rsi (Relative Strength Index)
            - macd, macd_signal, macd_hist (MACD)
            - bb_upper, bb_middle, bb_lower (Bollinger Bands)
            - atr (Average True Range)
        """
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        conn = self.db._get_connection()
        try:
            # Check if region column exists (legacy schema compatibility)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(ohlcv_data)")
            columns_info = [row[1] for row in cursor.fetchall()]
            has_region = 'region' in columns_info

            # Define available indicators
            all_indicators = [
                'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
                'rsi',
                'macd', 'macd_signal', 'macd_hist',
                'bb_upper', 'bb_middle', 'bb_lower',
                'atr'
            ]

            # Select indicators
            if indicators is None:
                selected_indicators = all_indicators
            else:
                # Validate requested indicators
                invalid_indicators = set(indicators) - set(all_indicators)
                if invalid_indicators:
                    logger.warning(f"Invalid indicators requested: {invalid_indicators}")
                selected_indicators = [ind for ind in indicators if ind in all_indicators]

            if not selected_indicators:
                return pd.DataFrame(columns=['date'])

            # Build query
            columns_str = ', '.join(selected_indicators)

            if has_region:
                query = f"""
                    SELECT
                        date, {columns_str}
                    FROM ohlcv_data
                    WHERE ticker = ?
                      AND region = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY date ASC
                """
                params = (ticker, region, start_date.isoformat(), end_date.isoformat())
            else:
                # Legacy schema without region column
                query = f"""
                    SELECT
                        date, {columns_str}
                    FROM ohlcv_data
                    WHERE ticker = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY date ASC
                """
                params = (ticker, start_date.isoformat(), end_date.isoformat())

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

            # Ensure numeric types
            for col in selected_indicators:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            logger.error(f"Error loading technical indicators for {ticker}: {e}")
            return pd.DataFrame(columns=['date'])
        finally:
            conn.close()

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

        Performance:
            <100ms for typical query (single region)
        """
        self._validate_date_range(start_date, end_date)

        conn = self.db._get_connection()
        try:
            # Check if region column exists (legacy schema compatibility)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(ohlcv_data)")
            columns = [row[1] for row in cursor.fetchall()]
            has_region = 'region' in columns

            # Base query
            if has_region:
                query = """
                    SELECT DISTINCT ticker
                    FROM ohlcv_data
                    WHERE region = ?
                      AND date >= ?
                      AND date <= ?
                """
                params = [region, start_date.isoformat(), end_date.isoformat()]

                # Add volume filter
                if min_volume is not None:
                    query += """
                        AND ticker IN (
                            SELECT ticker
                            FROM ohlcv_data
                            WHERE region = ?
                              AND date >= ?
                              AND date <= ?
                            GROUP BY ticker
                            HAVING AVG(volume) >= ?
                        )
                    """
                    params.extend([region, start_date.isoformat(), end_date.isoformat(), min_volume])

                # Add price filter
                if min_price is not None:
                    query += """
                        AND ticker IN (
                            SELECT ticker
                            FROM ohlcv_data
                            WHERE region = ?
                              AND date >= ?
                              AND date <= ?
                              AND close >= ?
                        )
                    """
                    params.extend([region, start_date.isoformat(), end_date.isoformat(), min_price])
            else:
                # Legacy schema without region column
                query = """
                    SELECT DISTINCT ticker
                    FROM ohlcv_data
                    WHERE date >= ?
                      AND date <= ?
                """
                params = [start_date.isoformat(), end_date.isoformat()]

                # Add volume filter
                if min_volume is not None:
                    query += """
                        AND ticker IN (
                            SELECT ticker
                            FROM ohlcv_data
                            WHERE date >= ?
                              AND date <= ?
                            GROUP BY ticker
                            HAVING AVG(volume) >= ?
                        )
                    """
                    params.extend([start_date.isoformat(), end_date.isoformat(), min_volume])

                # Add price filter
                if min_price is not None:
                    query += """
                        AND ticker IN (
                            SELECT ticker
                            FROM ohlcv_data
                            WHERE date >= ?
                              AND date <= ?
                              AND close >= ?
                        )
                    """
                    params.extend([start_date.isoformat(), end_date.isoformat(), min_price])

            query += " ORDER BY ticker"

            cursor = conn.cursor()
            cursor.execute(query, params)
            tickers = [row[0] for row in cursor.fetchall()]

            logger.debug(f"Found {len(tickers)} available tickers in {region} "
                        f"(volume>={min_volume}, price>={min_price})")
            return tickers

        except Exception as e:
            logger.error(f"Error getting available tickers: {e}")
            return []
        finally:
            conn.close()

    def load_data_with_indicators(
        self,
        tickers: List[str],
        region: str,
        start_date: date,
        end_date: date,
        lookback_days: int = 300
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data with technical indicators for backtesting.

        This method mimics the legacy HistoricalDataProvider.load_data()
        behavior for backward compatibility.

        Args:
            tickers: List of ticker symbols
            region: Market region code
            start_date: Start date for backtesting
            end_date: End date for backtesting
            lookback_days: Days to load before start_date (for indicator calculation)

        Returns:
            Dictionary mapping ticker -> DataFrame with OHLCV + indicators

        Note:
            Loads extra data before start_date for technical indicator calculation.
            Typical lookback: 300 days for MA200 calculation.
        """
        extended_start = start_date - timedelta(days=lookback_days)

        logger.info(f"Loading data with indicators: {len(tickers)} tickers, "
                   f"date range: {extended_start} to {end_date}")

        result = {}
        for ticker in tickers:
            try:
                # Get OHLCV data
                ohlcv_df = self.get_ohlcv(ticker, region, extended_start, end_date)
                if ohlcv_df.empty:
                    logger.warning(f"No OHLCV data for {ticker}, skipping")
                    continue

                # Get technical indicators
                indicators_df = self.get_technical_indicators(
                    ticker, region, extended_start, end_date
                )

                # Merge OHLCV + indicators
                if not indicators_df.empty:
                    df = ohlcv_df.merge(indicators_df, on='date', how='left')
                else:
                    df = ohlcv_df

                # Set date as index
                df = df.set_index('date')

                result[ticker] = df

            except Exception as e:
                logger.error(f"Error loading data for {ticker}: {e}")
                continue

        logger.info(f"Loaded data for {len(result)}/{len(tickers)} tickers")
        return result
