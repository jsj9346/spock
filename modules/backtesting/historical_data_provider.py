"""
Historical Data Provider (DEPRECATED)

⚠️  DEPRECATION WARNING:
    This module is deprecated and will be removed in version 2.0.
    Use BaseDataProvider implementations instead:
      - SQLiteDataProvider for SQLite backend
      - PostgresDataProvider for PostgreSQL + TimescaleDB backend

Purpose: Efficient access to historical OHLCV data with caching for backtesting.

Key Features:
  - Load OHLCV data from SQLite database
  - In-memory caching for fast iteration
  - Point-in-time data snapshots (no look-ahead bias)
  - Handle missing data gracefully
  - Support multi-region queries

Design Philosophy:
  - Event-driven: Provide only data available at decision time
  - Performance: Cache all data upfront for O(1) lookup
  - Safety: Prevent future data leakage

Migration Guide:
    # Old approach (deprecated)
    >>> from modules.db_manager_sqlite import SQLiteDatabaseManager
    >>> from modules.backtesting.historical_data_provider import HistoricalDataProvider
    >>> db = SQLiteDatabaseManager('data/spock.db')
    >>> provider = HistoricalDataProvider(db)

    # New approach (recommended)
    >>> from modules.backtesting.data_providers import SQLiteDataProvider
    >>> from modules.db_manager_sqlite import SQLiteDatabaseManager
    >>> db = SQLiteDatabaseManager('data/spock.db')
    >>> provider = SQLiteDataProvider(db, cache_enabled=True)

    # Factory method (simplest)
    >>> from modules.backtesting.backtest_engine import BacktestEngine
    >>> engine = BacktestEngine.from_sqlite(config, db_path='data/spock.db')
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Set
import pandas as pd
import logging
import warnings

from modules.db_manager_sqlite import SQLiteDatabaseManager


logger = logging.getLogger(__name__)


class HistoricalDataProvider:
    """
    Efficient historical data access for backtesting.

    ⚠️  DEPRECATED: Use SQLiteDataProvider or PostgresDataProvider instead.
        This class will be removed in version 2.0.

    Attributes:
        db: SQLite database manager
        data_cache: In-memory cache {ticker: DataFrame}
        tickers: Set of available tickers
        start_date: Data start date
        end_date: Data end date
        regions: List of regions

    Migration:
        Replace with SQLiteDataProvider for identical functionality with BaseDataProvider interface.
    """

    def __init__(self, db: SQLiteDatabaseManager):
        """
        Initialize data provider.

        ⚠️  DEPRECATED: Use SQLiteDataProvider instead.

        Args:
            db: SQLite database manager

        Example Migration:
            # Before
            >>> provider = HistoricalDataProvider(db)

            # After
            >>> from modules.backtesting.data_providers import SQLiteDataProvider
            >>> provider = SQLiteDataProvider(db, cache_enabled=True)
        """
        warnings.warn(
            "HistoricalDataProvider is deprecated and will be removed in version 2.0. "
            "Use SQLiteDataProvider or PostgresDataProvider instead. "
            "See docstring for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )

        self.db = db
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.tickers: Set[str] = set()
        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.regions: List[str] = []

        logger.warning(
            "HistoricalDataProvider is deprecated. "
            "Migrate to SQLiteDataProvider for BaseDataProvider interface."
        )

    def load_data(
        self,
        tickers: Optional[List[str]],
        start_date: date,
        end_date: date,
        regions: List[str],
    ) -> Dict[str, pd.DataFrame]:
        """
        Load OHLCV data with technical indicators for specified tickers.

        Args:
            tickers: List of tickers to load (None = all tickers in regions)
            start_date: Start date for data loading
            end_date: End date for data loading
            regions: List of regions to load data from

        Returns:
            Dictionary mapping ticker to DataFrame with OHLCV + indicators

        Note:
            - Loads 250 days before start_date for technical indicator calculation
            - Caches data in memory for fast access
            - DataFrame index: date, Columns: open, high, low, close, volume, + indicators
        """
        self.start_date = start_date
        self.end_date = end_date
        self.regions = regions

        # Calculate extended start date for technical indicators
        # Need ~250 days for MA200 calculation
        extended_start = start_date - timedelta(days=300)

        logger.info(
            f"Loading data: tickers={len(tickers) if tickers else 'all'}, "
            f"date_range={extended_start} to {end_date}, regions={regions}"
        )

        # Get ticker list
        if tickers is None:
            tickers = self._get_all_tickers(regions)
        else:
            # Validate tickers exist
            tickers = self._validate_tickers(tickers, regions)

        self.tickers = set(tickers)
        logger.info(f"Loading data for {len(self.tickers)} tickers")

        # Load data for each ticker
        loaded_count = 0
        for ticker in self.tickers:
            try:
                df = self._load_ticker_data(ticker, extended_start, end_date, regions)
                if df is not None and len(df) > 0:
                    self.data_cache[ticker] = df
                    loaded_count += 1
            except Exception as e:
                logger.warning(f"Failed to load data for {ticker}: {e}")
                continue

        logger.info(
            f"Data loading complete: {loaded_count}/{len(self.tickers)} tickers loaded"
        )
        return self.data_cache

    def get_snapshot(self, ticker: str, as_of_date: date) -> Optional[pd.Series]:
        """
        Get point-in-time data snapshot for ticker (no look-ahead bias).

        Args:
            ticker: Stock ticker
            as_of_date: Date for data snapshot

        Returns:
            Series with OHLCV + indicators as of date, or None if not available

        Note:
            - Only returns data available at decision time
            - Returns None if ticker has no data or date is out of range
        """
        if ticker not in self.data_cache:
            return None

        df = self.data_cache[ticker]

        # Find latest data available on or before as_of_date
        available_dates = df.index[df.index <= pd.Timestamp(as_of_date)]
        if len(available_dates) == 0:
            return None

        latest_date = available_dates[-1]
        return df.loc[latest_date]

    def get_historical_window(
        self, ticker: str, end_date: date, window_days: int
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data window ending at specified date.

        Args:
            ticker: Stock ticker
            end_date: End date for window
            window_days: Number of days to look back

        Returns:
            DataFrame with OHLCV + indicators for window, or None if not available
        """
        if ticker not in self.data_cache:
            return None

        df = self.data_cache[ticker]
        start_date = end_date - timedelta(days=window_days)

        # Filter data in window
        mask = (df.index >= pd.Timestamp(start_date)) & (
            df.index <= pd.Timestamp(end_date)
        )
        window_df = df[mask]

        if len(window_df) == 0:
            return None

        return window_df

    def get_universe(self, as_of_date: date, regions: List[str]) -> List[str]:
        """
        Get list of available tickers as of date (handles delistings).

        Args:
            as_of_date: Date for universe snapshot
            regions: List of regions to include

        Returns:
            List of tickers with data available as of date
        """
        available_tickers = []

        for ticker in self.tickers:
            snapshot = self.get_snapshot(ticker, as_of_date)
            if snapshot is not None:
                available_tickers.append(ticker)

        logger.debug(
            f"Universe as of {as_of_date}: {len(available_tickers)} tickers available"
        )
        return available_tickers

    def get_latest_price(self, ticker: str, as_of_date: date) -> Optional[float]:
        """
        Get latest close price as of date.

        Args:
            ticker: Stock ticker
            as_of_date: Date for price lookup

        Returns:
            Latest close price, or None if not available
        """
        snapshot = self.get_snapshot(ticker, as_of_date)
        if snapshot is None:
            return None
        return snapshot.get("close")

    def has_data(self, ticker: str, as_of_date: date) -> bool:
        """
        Check if ticker has data available as of date.

        Args:
            ticker: Stock ticker
            as_of_date: Date to check

        Returns:
            True if data is available
        """
        return self.get_snapshot(ticker, as_of_date) is not None

    def _get_all_tickers(self, regions: List[str]) -> List[str]:
        """
        Get all tickers available in specified regions.

        Args:
            regions: List of regions

        Returns:
            List of all tickers
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" for _ in regions)
        query = f"""
            SELECT DISTINCT ticker
            FROM tickers
            WHERE region IN ({placeholders})
            ORDER BY ticker
        """
        cursor.execute(query, regions)
        tickers = [row[0] for row in cursor.fetchall()]

        conn.close()
        logger.info(f"Found {len(tickers)} tickers in regions {regions}")
        return tickers

    def _validate_tickers(
        self, tickers: List[str], regions: List[str]
    ) -> List[str]:
        """
        Validate that tickers exist in specified regions.

        Args:
            tickers: List of tickers to validate
            regions: List of regions

        Returns:
            List of valid tickers (may be smaller if some don't exist)
        """
        conn = self.db._get_connection()
        cursor = conn.cursor()

        placeholders_tickers = ",".join("?" for _ in tickers)
        placeholders_regions = ",".join("?" for _ in regions)
        query = f"""
            SELECT DISTINCT ticker
            FROM tickers
            WHERE ticker IN ({placeholders_tickers})
              AND region IN ({placeholders_regions})
        """
        cursor.execute(query, tickers + regions)
        valid_tickers = [row[0] for row in cursor.fetchall()]

        conn.close()

        invalid_tickers = set(tickers) - set(valid_tickers)
        if invalid_tickers:
            logger.warning(
                f"Invalid tickers (not found in regions {regions}): {invalid_tickers}"
            )

        return valid_tickers

    def _load_ticker_data(
        self, ticker: str, start_date: date, end_date: date, regions: List[str]
    ) -> Optional[pd.DataFrame]:
        """
        Load OHLCV data with technical indicators for single ticker.

        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date
            regions: List of regions

        Returns:
            DataFrame with OHLCV + indicators, or None if no data
        """
        conn = self.db._get_connection()

        # Query OHLCV data with technical indicators
        placeholders_regions = ",".join("?" for _ in regions)
        query = f"""
            SELECT
                date,
                open, high, low, close, volume,
                ma5, ma20, ma60, ma120, ma200,
                rsi, macd, macd_signal, macd_hist,
                bb_upper, bb_middle, bb_lower,
                atr
            FROM ohlcv_data
            WHERE ticker = ?
              AND region IN ({placeholders_regions})
              AND date >= ?
              AND date <= ?
            ORDER BY date
        """
        params = [ticker] + regions + [start_date.isoformat(), end_date.isoformat()]

        try:
            df = pd.read_sql_query(query, conn, parse_dates=["date"], index_col="date")
            conn.close()

            if len(df) == 0:
                logger.debug(f"No data found for {ticker}")
                return None

            # Ensure numeric types
            numeric_columns = [
                "open", "high", "low", "close", "volume",
                "ma5", "ma20", "ma60", "ma120", "ma200",
                "rsi", "macd", "macd_signal", "macd_hist",
                "bb_upper", "bb_middle", "bb_lower", "atr",
            ]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            logger.debug(
                f"Loaded {len(df)} rows for {ticker} "
                f"(date range: {df.index[0].date()} to {df.index[-1].date()})"
            )
            return df

        except Exception as e:
            logger.error(f"Error loading data for {ticker}: {e}")
            conn.close()
            return None

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_rows = sum(len(df) for df in self.data_cache.values())
        total_memory_mb = sum(
            df.memory_usage(deep=True).sum() for df in self.data_cache.values()
        ) / (1024 * 1024)

        return {
            "tickers_cached": len(self.data_cache),
            "total_rows": total_rows,
            "memory_usage_mb": round(total_memory_mb, 2),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "regions": self.regions,
        }

    def clear_cache(self):
        """Clear in-memory data cache."""
        self.data_cache.clear()
        self.tickers.clear()
        logger.info("Data cache cleared")
