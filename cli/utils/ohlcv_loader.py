"""
OHLCV data loader for backtesting.

Provides efficient loading of historical price data from PostgreSQL
with support for multiple tickers and date ranges.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import pandas as pd
import asyncpg
from cli.utils.database import DatabaseManager


class OHLCVLoader:
    """
    OHLCV data loader with async PostgreSQL support.

    Features:
    - Batch loading for multiple tickers
    - Date range filtering
    - Automatic data validation
    - pandas DataFrame output for vectorbt compatibility
    - Caching for repeated queries

    Usage:
        loader = OHLCVLoader()
        await loader.connect()
        df = await loader.load_data(['005930', '000660'], start_date='2020-01-01')
    """

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initialize OHLCV loader.

        Args:
            db: Optional DatabaseManager instance. Creates new one if not provided.
        """
        self.db = db or DatabaseManager()
        self._cache: Dict[str, pd.DataFrame] = {}

    async def connect(self) -> None:
        """Connect to database."""
        await self.db.connect()

    async def disconnect(self) -> None:
        """Disconnect from database."""
        await self.db.disconnect()

    async def load_data(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        region: str = 'KR',
        timeframe: str = '1d',
        include_technicals: bool = False
    ) -> pd.DataFrame:
        """
        Load OHLCV data for multiple tickers.

        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD format). Default: all available data
            end_date: End date (YYYY-MM-DD format). Default: today
            region: Market region (KR, US)
            timeframe: Data timeframe (1d, 1h, etc.)
            include_technicals: Include technical indicators (MA, RSI, MACD)

        Returns:
            DataFrame with MultiIndex (date, ticker) and columns (open, high, low, close, volume)

        Raises:
            ValueError: If no data found for tickers
            ConnectionError: If database connection fails
        """
        # Build query
        columns = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
        if include_technicals:
            columns.extend(['ma5', 'ma20', 'ma60', 'rsi_14', 'macd', 'macd_signal'])

        query = f"""
            SELECT {', '.join(columns)}
            FROM ohlcv_data
            WHERE ticker = ANY($1)
              AND region = $2
              AND timeframe = $3
        """
        params = [tickers, region, timeframe]

        # Add date filters
        param_counter = 4
        if start_date:
            query += f" AND date >= ${param_counter}"
            params.append(start_date)
            param_counter += 1

        if end_date:
            query += f" AND date <= ${param_counter}"
            params.append(end_date)

        query += " ORDER BY date ASC, ticker ASC"

        # Execute query
        try:
            rows = await self.db.fetch(query, *params, timeout=60.0)
        except Exception as e:
            raise ConnectionError(f"Failed to load OHLCV data: {e}")

        if not rows:
            raise ValueError(
                f"No data found for tickers: {tickers} "
                f"(region={region}, timeframe={timeframe}, start={start_date}, end={end_date})"
            )

        # Convert to DataFrame
        data = []
        for row in rows:
            row_dict = dict(row)
            data.append(row_dict)

        df = pd.DataFrame(data)

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Set MultiIndex (date, ticker)
        df.set_index(['date', 'ticker'], inplace=True)

        # Sort index
        df.sort_index(inplace=True)

        return df

    async def load_single_ticker(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        region: str = 'KR',
        timeframe: str = '1d',
        include_technicals: bool = False,
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Load OHLCV data for a single ticker.

        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            region: Market region
            timeframe: Data timeframe
            include_technicals: Include technical indicators
            use_cache: Use cached data if available

        Returns:
            DataFrame with DatetimeIndex and columns (open, high, low, close, volume)
        """
        cache_key = f"{ticker}_{region}_{timeframe}_{start_date}_{end_date}_{include_technicals}"

        # Check cache
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()

        # Load data
        df = await self.load_data(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe=timeframe,
            include_technicals=include_technicals
        )

        # Reset ticker index (keep only date)
        df = df.reset_index('ticker', drop=True)

        # Cache result
        if use_cache:
            self._cache[cache_key] = df.copy()

        return df

    async def get_available_tickers(
        self,
        region: str = 'KR',
        timeframe: str = '1d',
        min_data_points: int = 252  # 1 year of trading days
    ) -> List[str]:
        """
        Get list of tickers with sufficient historical data.

        Args:
            region: Market region
            timeframe: Data timeframe
            min_data_points: Minimum number of data points required

        Returns:
            List of ticker symbols
        """
        query = """
            SELECT ticker, COUNT(*) as data_points
            FROM ohlcv_data
            WHERE region = $1
              AND timeframe = $2
            GROUP BY ticker
            HAVING COUNT(*) >= $3
            ORDER BY ticker ASC
        """

        rows = await self.db.fetch(query, region, timeframe, min_data_points)

        tickers = [row['ticker'] for row in rows]
        return tickers

    async def get_date_range(
        self,
        ticker: str,
        region: str = 'KR',
        timeframe: str = '1d'
    ) -> Tuple[date, date]:
        """
        Get available date range for a ticker.

        Args:
            ticker: Ticker symbol
            region: Market region
            timeframe: Data timeframe

        Returns:
            Tuple of (start_date, end_date)

        Raises:
            ValueError: If no data found for ticker
        """
        query = """
            SELECT MIN(date) as start_date, MAX(date) as end_date
            FROM ohlcv_data
            WHERE ticker = $1
              AND region = $2
              AND timeframe = $3
        """

        rows = await self.db.fetch(query, ticker, region, timeframe)

        if not rows or not rows[0]['start_date']:
            raise ValueError(f"No data found for ticker: {ticker}")

        start_date = rows[0]['start_date']
        end_date = rows[0]['end_date']

        return start_date, end_date

    def clear_cache(self) -> None:
        """Clear cached data."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached queries."""
        return len(self._cache)


# Convenience functions
async def load_backtest_data(
    tickers: List[str],
    start_date: str,
    end_date: str,
    region: str = 'KR'
) -> pd.DataFrame:
    """
    Convenience function to load data for backtesting.

    Args:
        tickers: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        region: Market region

    Returns:
        DataFrame with MultiIndex suitable for vectorbt
    """
    loader = OHLCVLoader()
    try:
        await loader.connect()
        df = await loader.load_data(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe='1d',
            include_technicals=False
        )
        return df
    finally:
        await loader.disconnect()


if __name__ == '__main__':
    # Test the loader
    import asyncio

    async def test():
        loader = OHLCVLoader()
        await loader.connect()

        # Test single ticker
        print("Loading single ticker data...")
        df = await loader.load_single_ticker(
            ticker='005930',
            start_date='2024-01-01',
            end_date='2024-12-31',
            region='KR'
        )
        print(f"Loaded {len(df)} rows for 005930")
        print(df.head())

        # Test multiple tickers
        print("\nLoading multiple tickers...")
        df = await loader.load_data(
            tickers=['005930', '000660', '035420'],
            start_date='2024-01-01',
            end_date='2024-12-31',
            region='KR'
        )
        print(f"Loaded {len(df)} rows for 3 tickers")
        print(df.head())

        # Test available tickers
        print("\nGetting available tickers...")
        tickers = await loader.get_available_tickers(region='KR', min_data_points=100)
        print(f"Found {len(tickers)} tickers with 100+ data points")

        await loader.disconnect()

    asyncio.run(test())
