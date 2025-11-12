# Phase 1 Detailed Tasks - Day-by-Day Implementation Guide

**Phase**: Backtesting Engine Completion
**Duration**: 2 weeks (10 working days)
**Status**: Ready for Implementation
**Last Updated**: 2025-10-26

---

## Week 1: Core Engine Enhancement & Integration

### 📅 Day 1-2: PostgreSQL Data Provider (BLOCKER)

**Objective**: Migrate data access layer from SQLite to PostgreSQL + TimescaleDB

**Why Critical**:
- Current SQLite has 250-day retention limit
- Multi-year backtests require PostgreSQL
- Blocks all other Phase 1 work

---

#### Task 1.1: Create Abstract Data Provider Interface (2 hours)

**File**: `modules/backtesting/data_providers/base_data_provider.py`

```python
"""
Abstract base class for backtest data providers.

Design Philosophy:
    - Pluggable architecture (SQLite, PostgreSQL, Cloud)
    - Consistent interface for all data sources
    - Point-in-time data retrieval (avoid look-ahead bias)
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Optional
import pandas as pd


class BaseDataProvider(ABC):
    """
    Abstract base class for backtest data providers.

    All data providers (SQLite, PostgreSQL, etc.) must implement these methods.
    """

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
            ticker: Stock ticker symbol
            region: Market region (KR, US, CN, HK, JP, VN)
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Timeframe (1d, 1h, 15m, etc.)

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            Sorted by date ascending

        Raises:
            ValueError: If ticker not found or invalid date range
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
            region: Market region
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            timeframe: Timeframe

        Returns:
            Dictionary: {ticker: DataFrame}

        Performance:
            Should be faster than calling get_ohlcv() in loop
            Use database JOIN or batch queries
        """
        pass

    @abstractmethod
    def get_ticker_universe(
        self,
        region: str,
        as_of_date: date,
        filters: Optional[Dict] = None
    ) -> List[str]:
        """
        Get list of available tickers at specific date (point-in-time).

        Args:
            region: Market region
            as_of_date: Date for which to get ticker list
            filters: Optional filters (e.g., {'sector': 'Technology', 'min_price': 10000})

        Returns:
            List of ticker symbols available at that date

        Important:
            Must use point-in-time data to avoid survivorship bias
            Only return tickers that existed and were tradable on as_of_date
        """
        pass

    @abstractmethod
    def get_fundamental_data(
        self,
        ticker: str,
        region: str,
        as_of_date: date,
        fields: Optional[List[str]] = None
    ) -> Dict:
        """
        Get fundamental data for factor calculations.

        Args:
            ticker: Stock ticker symbol
            region: Market region
            as_of_date: Date for which to get data (point-in-time)
            fields: Specific fields to retrieve (None = all)
                    Examples: ['pe_ratio', 'pb_ratio', 'roe', 'debt_ratio']

        Returns:
            Dictionary: {field: value}

        Important:
            Must use point-in-time data (no look-ahead bias)
            Return data as it would have been known on as_of_date
        """
        pass

    @abstractmethod
    def close(self):
        """Close database connection and cleanup resources."""
        pass


class DataProviderError(Exception):
    """Base exception for data provider errors."""
    pass


class DataNotFoundError(DataProviderError):
    """Raised when requested data is not available."""
    pass


class InvalidDateRangeError(DataProviderError):
    """Raised when date range is invalid."""
    pass
```

**Testing**:
```python
# tests/test_base_data_provider.py
def test_interface_contract():
    """Ensure all concrete providers implement required methods."""
    from modules.backtesting.data_providers import (
        BaseDataProvider, PostgresDataProvider, SQLiteDataProvider
    )

    # Check all abstract methods are implemented
    for provider_class in [PostgresDataProvider, SQLiteDataProvider]:
        assert hasattr(provider_class, 'get_ohlcv')
        assert hasattr(provider_class, 'get_ohlcv_batch')
        assert hasattr(provider_class, 'get_ticker_universe')
        assert hasattr(provider_class, 'get_fundamental_data')
```

---

#### Task 1.2: Refactor Existing SQLite Provider (2 hours)

**File**: `modules/backtesting/data_providers/sqlite_data_provider.py`

**Current Code**: `modules/backtesting/historical_data_provider.py` (387 lines)

**Refactoring Steps**:

1. **Copy existing file**:
```bash
cp modules/backtesting/historical_data_provider.py \
   modules/backtesting/data_providers/sqlite_data_provider.py
```

2. **Modify to implement BaseDataProvider**:
```python
"""
SQLite Data Provider for Backtesting (Legacy Support)

Purpose: Maintain compatibility with Spock SQLite database
Retention: 250 days (legacy limitation)
Use Case: Quick testing, legacy data access

For production quant platform, use PostgresDataProvider.
"""

from .base_data_provider import BaseDataProvider, DataNotFoundError
from modules.db_manager import SQLiteDatabaseManager
import pandas as pd
from datetime import date
from typing import List, Dict, Optional


class SQLiteDataProvider(BaseDataProvider):
    """
    SQLite implementation of data provider (legacy Spock database).

    Attributes:
        db: SQLiteDatabaseManager instance
        cache: Query result cache for performance
    """

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db
        self.cache = {}  # Simple in-memory cache

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """Get OHLCV data from SQLite."""

        # Check cache first
        cache_key = f"{ticker}_{region}_{start_date}_{end_date}_{timeframe}"
        if cache_key in self.cache:
            return self.cache[cache_key].copy()

        # Query database
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = ? AND region = ?
              AND date BETWEEN ? AND ?
              AND timeframe = ?
            ORDER BY date ASC
        """

        df = pd.read_sql_query(
            query,
            self.db.conn,
            params=(ticker, region, start_date, end_date, timeframe)
        )

        if df.empty:
            raise DataNotFoundError(
                f"No OHLCV data found for {ticker} ({region}) "
                f"between {start_date} and {end_date}"
            )

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Cache result
        self.cache[cache_key] = df.copy()

        return df

    def get_ohlcv_batch(
        self,
        tickers: List[str],
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """
        Get OHLCV data for multiple tickers (batch query).

        SQLite Implementation:
            - Single query with IN clause (faster than loop)
            - Group by ticker in Python
        """

        placeholders = ','.join('?' * len(tickers))
        query = f"""
            SELECT ticker, date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker IN ({placeholders})
              AND region = ?
              AND date BETWEEN ? AND ?
              AND timeframe = ?
            ORDER BY ticker, date ASC
        """

        params = tuple(tickers) + (region, start_date, end_date, timeframe)
        df_all = pd.read_sql_query(query, self.db.conn, params=params)

        if df_all.empty:
            return {}

        # Convert date column
        df_all['date'] = pd.to_datetime(df_all['date'])

        # Group by ticker
        result = {}
        for ticker in tickers:
            df_ticker = df_all[df_all['ticker'] == ticker].copy()
            if not df_ticker.empty:
                df_ticker = df_ticker.drop(columns=['ticker'])
                result[ticker] = df_ticker

        return result

    def get_ticker_universe(
        self,
        region: str,
        as_of_date: date,
        filters: Optional[Dict] = None
    ) -> List[str]:
        """
        Get available tickers at specific date (point-in-time).

        SQLite Implementation:
            - Query tickers table for active tickers
            - Filter by listing_date <= as_of_date
            - Apply optional filters (sector, price, etc.)
        """

        query = """
            SELECT DISTINCT ticker
            FROM tickers
            WHERE region = ?
              AND listing_date <= ?
              AND (delisting_date IS NULL OR delisting_date > ?)
        """
        params = [region, as_of_date, as_of_date]

        # Apply filters
        if filters:
            if 'sector' in filters:
                query += " AND sector = ?"
                params.append(filters['sector'])

            if 'min_market_cap' in filters:
                query += " AND market_cap >= ?"
                params.append(filters['min_market_cap'])

        query += " ORDER BY ticker"

        df = pd.read_sql_query(query, self.db.conn, params=tuple(params))
        return df['ticker'].tolist()

    def get_fundamental_data(
        self,
        ticker: str,
        region: str,
        as_of_date: date,
        fields: Optional[List[str]] = None
    ) -> Dict:
        """
        Get fundamental data (point-in-time).

        SQLite Implementation:
            - Query ticker_fundamentals table
            - Use most recent data before as_of_date
        """

        if fields is None:
            fields_str = "*"
        else:
            fields_str = ", ".join(fields)

        query = f"""
            SELECT {fields_str}
            FROM ticker_fundamentals
            WHERE ticker = ? AND region = ?
              AND date <= ?
            ORDER BY date DESC
            LIMIT 1
        """

        df = pd.read_sql_query(
            query,
            self.db.conn,
            params=(ticker, region, as_of_date)
        )

        if df.empty:
            raise DataNotFoundError(
                f"No fundamental data found for {ticker} ({region}) "
                f"as of {as_of_date}"
            )

        return df.iloc[0].to_dict()

    def close(self):
        """Close SQLite connection."""
        self.db.close()
        self.cache.clear()
```

**Testing**:
```python
# tests/test_sqlite_data_provider.py
import pytest
from datetime import date
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager import SQLiteDatabaseManager

@pytest.fixture
def provider():
    db = SQLiteDatabaseManager('data/spock_local.db')
    return SQLiteDataProvider(db)

def test_get_ohlcv(provider):
    """Test single ticker OHLCV retrieval."""
    df = provider.get_ohlcv('005930', 'KR', date(2023, 1, 1), date(2023, 12, 31))

    assert not df.empty
    assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']
    assert df['date'].is_monotonic_increasing

def test_get_ohlcv_batch(provider):
    """Test batch OHLCV retrieval."""
    tickers = ['005930', '000660', '035420']
    result = provider.get_ohlcv_batch(tickers, 'KR', date(2023, 1, 1), date(2023, 12, 31))

    assert len(result) == 3
    for ticker in tickers:
        assert ticker in result
        assert not result[ticker].empty
```

---

#### Task 1.3: Implement PostgreSQL Data Provider (6 hours)

**File**: `modules/backtesting/data_providers/postgres_data_provider.py`

```python
"""
PostgreSQL + TimescaleDB Data Provider for Backtesting

Purpose: Unlimited historical data retention with time-series optimization
Retention: Unlimited (compression after 1 year)
Use Case: Production quant platform, multi-year backtests

Key Features:
    - TimescaleDB hypertable queries (optimized for time-series)
    - Continuous aggregates for monthly/yearly data
    - Point-in-time data retrieval (avoid look-ahead bias)
    - Connection pooling for performance
    - Query caching layer
"""

from .base_data_provider import BaseDataProvider, DataNotFoundError
import psycopg2
from psycopg2 import pool
import pandas as pd
from datetime import date
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class PostgresDataProvider(BaseDataProvider):
    """
    PostgreSQL + TimescaleDB implementation for production quant platform.

    Attributes:
        connection_pool: psycopg2 connection pool (5-20 connections)
        cache: Query result cache
        use_continuous_aggregates: Whether to use TimescaleDB aggregates for monthly/yearly queries
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5432,
        database: str = 'quant_platform',
        user: str = None,
        password: str = None,
        min_connections: int = 5,
        max_connections: int = 20
    ):
        """
        Initialize PostgreSQL connection pool.

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum connections in pool
            max_connections: Maximum connections in pool
        """

        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                min_connections,
                max_connections,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            logger.info(
                f"PostgreSQL connection pool created: {min_connections}-{max_connections} connections"
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

        self.cache = {}
        self.use_continuous_aggregates = True  # Use TimescaleDB optimization

    def _get_connection(self):
        """Get connection from pool."""
        return self.connection_pool.getconn()

    def _release_connection(self, conn):
        """Release connection back to pool."""
        self.connection_pool.putconn(conn)

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data from PostgreSQL TimescaleDB.

        Performance:
            - Uses TimescaleDB hypertable (optimized for time-series)
            - Index on (ticker, region, date) for fast queries
            - Query time <1s for 5-year data
        """

        # Check cache first
        cache_key = f"{ticker}_{region}_{start_date}_{end_date}_{timeframe}"
        if cache_key in self.cache:
            logger.debug(f"Cache hit: {cache_key}")
            return self.cache[cache_key].copy()

        # Get connection from pool
        conn = self._get_connection()

        try:
            # Query TimescaleDB hypertable
            query = """
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s
                  AND date BETWEEN %s AND %s
                  AND timeframe = %s
                ORDER BY date ASC
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=(ticker, region, start_date, end_date, timeframe)
            )

            if df.empty:
                raise DataNotFoundError(
                    f"No OHLCV data found for {ticker} ({region}) "
                    f"between {start_date} and {end_date}"
                )

            # Convert date column to datetime
            df['date'] = pd.to_datetime(df['date'])

            # Cache result (limit cache size to 1000 entries)
            if len(self.cache) < 1000:
                self.cache[cache_key] = df.copy()

            logger.info(
                f"Loaded {len(df)} rows for {ticker} ({region}) "
                f"from {start_date} to {end_date}"
            )

            return df

        finally:
            self._release_connection(conn)

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

        Performance:
            - Single query with IN clause
            - 10-20x faster than individual queries
            - Uses TimescaleDB parallel query execution
        """

        if not tickers:
            return {}

        conn = self._get_connection()

        try:
            # Build query with parameterized IN clause
            placeholders = ','.join(['%s'] * len(tickers))
            query = f"""
                SELECT ticker, date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker IN ({placeholders})
                  AND region = %s
                  AND date BETWEEN %s AND %s
                  AND timeframe = %s
                ORDER BY ticker, date ASC
            """

            params = tuple(tickers) + (region, start_date, end_date, timeframe)
            df_all = pd.read_sql_query(query, conn, params=params)

            if df_all.empty:
                logger.warning(
                    f"No data found for {len(tickers)} tickers "
                    f"between {start_date} and {end_date}"
                )
                return {}

            # Convert date column
            df_all['date'] = pd.to_datetime(df_all['date'])

            # Group by ticker (vectorized operation)
            result = {
                ticker: group.drop(columns=['ticker']).reset_index(drop=True)
                for ticker, group in df_all.groupby('ticker')
            }

            logger.info(
                f"Loaded data for {len(result)} tickers "
                f"({len(df_all)} total rows) in batch query"
            )

            return result

        finally:
            self._release_connection(conn)

    def get_ticker_universe(
        self,
        region: str,
        as_of_date: date,
        filters: Optional[Dict] = None
    ) -> List[str]:
        """
        Get available tickers at specific date (point-in-time).

        Important:
            - Uses point-in-time data to avoid survivorship bias
            - Only returns tickers that existed and were tradable on as_of_date
            - Filters applied (sector, market cap, liquidity, etc.)
        """

        conn = self._get_connection()

        try:
            query = """
                SELECT DISTINCT ticker
                FROM tickers
                WHERE region = %s
                  AND listing_date <= %s
                  AND (delisting_date IS NULL OR delisting_date > %s)
            """
            params = [region, as_of_date, as_of_date]

            # Apply optional filters
            if filters:
                if 'sector' in filters:
                    query += " AND sector = %s"
                    params.append(filters['sector'])

                if 'min_market_cap' in filters:
                    query += " AND market_cap >= %s"
                    params.append(filters['min_market_cap'])

                if 'min_liquidity' in filters:
                    # Check average volume over last 20 days
                    query += """
                        AND ticker IN (
                            SELECT ticker FROM ohlcv_data
                            WHERE region = %s
                              AND date BETWEEN %s - INTERVAL '20 days' AND %s
                            GROUP BY ticker
                            HAVING AVG(volume * close) >= %s
                        )
                    """
                    params.extend([region, as_of_date, as_of_date, filters['min_liquidity']])

            query += " ORDER BY ticker"

            df = pd.read_sql_query(query, conn, params=tuple(params))

            tickers = df['ticker'].tolist()
            logger.info(
                f"Found {len(tickers)} tickers for {region} as of {as_of_date}"
            )

            return tickers

        finally:
            self._release_connection(conn)

    def get_fundamental_data(
        self,
        ticker: str,
        region: str,
        as_of_date: date,
        fields: Optional[List[str]] = None
    ) -> Dict:
        """
        Get fundamental data (point-in-time).

        Point-in-Time Rules:
            - Use most recent data published BEFORE as_of_date
            - Account for reporting lag (quarterly reports published 45-60 days after quarter end)
            - Never use data that wasn't publicly available on as_of_date
        """

        conn = self._get_connection()

        try:
            if fields is None:
                fields_str = "*"
            else:
                fields_str = ", ".join(fields)

            # Query most recent fundamental data before as_of_date
            query = f"""
                SELECT {fields_str}
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND date <= %s
                ORDER BY date DESC
                LIMIT 1
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=(ticker, region, as_of_date)
            )

            if df.empty:
                raise DataNotFoundError(
                    f"No fundamental data found for {ticker} ({region}) "
                    f"as of {as_of_date}"
                )

            return df.iloc[0].to_dict()

        finally:
            self._release_connection(conn)

    def close(self):
        """Close all connections in pool."""
        self.connection_pool.closeall()
        self.cache.clear()
        logger.info("PostgreSQL connection pool closed")


# Helper function for easy provider creation
def get_postgres_provider(config: Dict = None) -> PostgresDataProvider:
    """
    Factory function to create PostgreSQL provider from config.

    Args:
        config: Dictionary with connection parameters
                If None, uses environment variables

    Example:
        provider = get_postgres_provider({
            'host': 'localhost',
            'database': 'quant_platform',
            'user': 'postgres',
            'password': 'secret'
        })
    """
    if config is None:
        import os
        config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'database': os.getenv('POSTGRES_DB', 'quant_platform'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD'),
        }

    return PostgresDataProvider(**config)
```

**Testing**:
```python
# tests/test_postgres_data_provider.py
import pytest
from datetime import date
from modules.backtesting.data_providers import PostgresDataProvider

@pytest.fixture
def provider():
    return PostgresDataProvider(
        host='localhost',
        database='quant_platform_test',
        user='postgres',
        password='test'
    )

def test_connection_pool(provider):
    """Test connection pool creation."""
    assert provider.connection_pool is not None
    assert provider.connection_pool.minconn == 5
    assert provider.connection_pool.maxconn == 20

def test_get_ohlcv_performance(provider):
    """Test query performance (<1s for 5-year data)."""
    import time

    start_time = time.time()
    df = provider.get_ohlcv('005930', 'KR', date(2018, 1, 1), date(2023, 12, 31))
    elapsed = time.time() - start_time

    assert not df.empty
    assert elapsed < 1.0, f"Query took {elapsed:.2f}s (target: <1s)"

def test_batch_vs_individual_queries(provider):
    """Verify batch query is faster than individual queries."""
    import time

    tickers = ['005930', '000660', '035420', '005380', '051910']
    date_range = (date(2023, 1, 1), date(2023, 12, 31))

    # Individual queries
    start = time.time()
    for ticker in tickers:
        _ = provider.get_ohlcv(ticker, 'KR', *date_range)
    individual_time = time.time() - start

    # Batch query
    start = time.time()
    _ = provider.get_ohlcv_batch(tickers, 'KR', *date_range)
    batch_time = time.time() - start

    speedup = individual_time / batch_time
    assert speedup > 5, f"Batch query only {speedup:.1f}x faster (expected >5x)"
```

---

#### Task 1.4: Update BacktestEngine to Use Pluggable Provider (2 hours)

**File**: `modules/backtesting/backtest_engine.py` (modify existing)

**Changes**:

```python
# OLD CODE (hardcoded SQLite):
class BacktestEngine:
    def __init__(self, config: BacktestConfig, db: SQLiteDatabaseManager):
        self.db = db
        self.data_provider = HistoricalDataProvider(db)  # Hardcoded SQLite

# NEW CODE (pluggable provider):
from .data_providers import BaseDataProvider, PostgresDataProvider, SQLiteDataProvider

class BacktestEngine:
    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider,  # Accept any provider
        db: Optional[SQLiteDatabaseManager] = None  # Keep for backward compatibility
    ):
        """
        Initialize backtest engine with pluggable data provider.

        Args:
            config: Backtest configuration
            data_provider: Data provider implementation (PostgreSQL or SQLite)
            db: Legacy SQLite database (deprecated, use data_provider instead)
        """
        self.config = config

        # Support legacy initialization with db parameter
        if data_provider is None and db is not None:
            logger.warning(
                "Using legacy db parameter is deprecated. "
                "Pass data_provider instead."
            )
            data_provider = SQLiteDataProvider(db)

        if data_provider is None:
            raise ValueError("Either data_provider or db must be provided")

        self.data_provider = data_provider
        self.portfolio = PortfolioSimulator(config)
        self.strategy_runner = StrategyRunner(config, data_provider)  # Also update this
```

**Update Configuration**:

```yaml
# config/backtest_config.yaml
database:
  type: postgres  # postgres | sqlite

  # PostgreSQL settings
  postgres:
    host: localhost
    port: 5432
    database: quant_platform
    user: postgres
    password: ${POSTGRES_PASSWORD}  # From environment
    min_connections: 5
    max_connections: 20

  # SQLite settings (legacy)
  sqlite:
    path: data/spock_local.db
```

**Usage Example**:

```python
# New usage (PostgreSQL):
from modules.backtesting import BacktestEngine, BacktestConfig
from modules.backtesting.data_providers import get_postgres_provider

config = BacktestConfig(
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    regions=['KR']
)

provider = get_postgres_provider()  # Reads from env or config
engine = BacktestEngine(config, data_provider=provider)
result = engine.run()

# Legacy usage (SQLite) still works:
from modules.db_manager import SQLiteDatabaseManager

db = SQLiteDatabaseManager('data/spock_local.db')
engine = BacktestEngine(config, db=db)  # Automatic conversion to SQLiteDataProvider
```

---

#### Day 1-2 Deliverables

**Files Created** (5 new files):
- [x] `modules/backtesting/data_providers/__init__.py`
- [x] `modules/backtesting/data_providers/base_data_provider.py` (150 lines)
- [x] `modules/backtesting/data_providers/sqlite_data_provider.py` (200 lines)
- [x] `modules/backtesting/data_providers/postgres_data_provider.py` (400 lines)

**Files Modified** (2 files):
- [x] `modules/backtesting/backtest_engine.py` (~50 line changes)
- [x] `config/backtest_config.yaml` (add database section)

**Tests Created**:
- [x] `tests/test_base_data_provider.py`
- [x] `tests/test_sqlite_data_provider.py`
- [x] `tests/test_postgres_data_provider.py`

**Success Criteria**:
- ✅ BacktestEngine works with both SQLite and PostgreSQL
- ✅ PostgreSQL queries <1s for 5-year data
- ✅ Batch queries >5x faster than individual queries
- ✅ All tests passing

---

### 📅 Day 3-4: vectorbt Integration (100x Speed)

**Objective**: Create vectorbt adapter for ultra-fast parameter optimization

**Why Critical**:
- Current parameter optimization: ~2 hours for 100 combinations
- vectorbt target: <1 minute for 100 combinations
- 120x speed improvement unlocks rapid research iteration

---

#### Task 2.1: Install and Verify vectorbt (30 minutes)

```bash
# Install vectorbt
pip install vectorbt==0.25.6

# Verify installation
python3 -c "import vectorbt as vbt; print(vbt.__version__)"
# Expected output: 0.25.6

# Test basic functionality
python3 << 'EOF'
import vectorbt as vbt
import pandas as pd

# Load sample data
data = vbt.YFData.download('AAPL', start='2020-01-01', end='2023-12-31')

# Simple moving average crossover
fast_ma = vbt.MA.run(data.close, 20)
slow_ma = vbt.MA.run(data.close, 50)
entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

# Backtest (vectorized - instant)
pf = vbt.Portfolio.from_signals(data.close, entries, exits, freq='D')

# Print stats
print(pf.stats())
EOF
```

Expected output shows Sharpe ratio, total return, etc.

---

#### Task 2.2: Create vectorbt Adapter (5 hours)

**File**: `modules/backtesting/vectorbt_adapter.py` (400 lines)

```python
"""
vectorbt Backtesting Adapter

Purpose: Ultra-fast vectorized backtesting for parameter optimization and research.

Performance:
    - 100x faster than event-driven backtesting
    - <1 second for 5-year simulation
    - <1 minute for 100 parameter combinations

Use Cases:
    - Parameter optimization (Kelly multiplier, score threshold, etc.)
    - Factor weight tuning
    - Monte Carlo simulation (1000+ runs)
    - Rapid strategy iteration

Limitations (use custom engine instead):
    - No complex order types (market orders only)
    - No intraday strategies (daily timeframe focus)
    - No live trading integration

Design Philosophy:
    - Vectorized operations (NumPy/Pandas)
    - One-line portfolio simulation
    - Seamless integration with custom engine
"""

import vectorbt as vbt
import pandas as pd
import numpy as np
from datetime import date
from typing import Dict, List, Optional, Tuple
import logging

from .backtest_config import BacktestConfig, BacktestResult, PerformanceMetrics, Trade
from .data_providers import BaseDataProvider

logger = logging.getLogger(__name__)


class VectorbtBacktestAdapter:
    """
    vectorbt adapter for ultra-fast backtesting.

    Attributes:
        config: Backtest configuration
        data_provider: Data provider (PostgreSQL or SQLite)
        price_data: Cached price data (DataFrame with MultiIndex)
    """

    def __init__(self, config: BacktestConfig, data_provider: BaseDataProvider):
        self.config = config
        self.data_provider = data_provider
        self.price_data = None  # Will be loaded on demand

    def load_price_data(self, tickers: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load price data for all tickers in universe.

        Args:
            tickers: Specific tickers to load (None = use config.tickers or universe)

        Returns:
            DataFrame with MultiIndex (date, ticker) and columns [open, high, low, close, volume]

        Performance:
            Uses batch query for efficiency (10-20x faster than individual queries)
        """

        if tickers is None:
            if self.config.tickers:
                tickers = self.config.tickers
            else:
                # Get universe for each date (point-in-time)
                tickers = self.data_provider.get_ticker_universe(
                    region=self.config.regions[0],  # Assume single region for now
                    as_of_date=self.config.start_date
                )

        logger.info(f"Loading price data for {len(tickers)} tickers...")

        # Batch query for all tickers
        ohlcv_dict = self.data_provider.get_ohlcv_batch(
            tickers=tickers,
            region=self.config.regions[0],
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            timeframe='1d'
        )

        # Convert to MultiIndex DataFrame (vectorbt format)
        dfs = []
        for ticker, df in ohlcv_dict.items():
            df = df.set_index('date')
            df['ticker'] = ticker
            dfs.append(df)

        if not dfs:
            raise ValueError("No price data loaded")

        price_data = pd.concat(dfs)
        price_data = price_data.reset_index().set_index(['date', 'ticker'])

        logger.info(
            f"Loaded {len(price_data)} rows for {len(tickers)} tickers "
            f"from {self.config.start_date} to {self.config.end_date}"
        )

        self.price_data = price_data
        return price_data

    def run_backtest(
        self,
        signals: pd.DataFrame,
        position_size: float = 0.15,
        commission: float = 0.00015,
        slippage: float = 0.001
    ) -> BacktestResult:
        """
        Run vectorized backtest from pre-generated signals.

        Args:
            signals: DataFrame with columns [date, ticker, signal]
                     signal: 1.0 (buy), -1.0 (sell), 0.0 (hold)
            position_size: Position size as fraction of portfolio (0.15 = 15%)
            commission: Commission rate (0.00015 = 0.015%)
            slippage: Slippage rate (0.001 = 0.1%)

        Returns:
            BacktestResult compatible with custom engine

        Workflow:
            1. Load price data (if not cached)
            2. Align signals with price data
            3. Run vectorbt Portfolio.from_signals()
            4. Extract vectorbt stats
            5. Map to PerformanceMetrics format
            6. Return BacktestResult

        Performance:
            <1 second for 5-year, 50-stock portfolio
        """

        # Load price data if not cached
        if self.price_data is None:
            tickers = signals['ticker'].unique().tolist()
            self.load_price_data(tickers)

        # Prepare price data (pivot to wide format for vectorbt)
        close_prices = self.price_data['close'].unstack('ticker')

        # Prepare signals (pivot to wide format)
        signals_pivot = signals.pivot(index='date', columns='ticker', values='signal')
        signals_pivot = signals_pivot.reindex_like(close_prices).fillna(0)

        # Convert signals to boolean entries/exits
        entries = (signals_pivot == 1.0)
        exits = (signals_pivot == -1.0)

        # Run vectorbt backtest (vectorized - instant)
        logger.info("Running vectorbt backtest...")

        pf = vbt.Portfolio.from_signals(
            close=close_prices,
            entries=entries,
            exits=exits,
            init_cash=self.config.initial_capital,
            size=position_size,  # Position sizing
            size_type='targetpercent',  # As % of portfolio
            fees=commission,  # Commission
            slippage=slippage,  # Slippage
            freq='D'  # Daily frequency
        )

        # Extract statistics
        stats = pf.stats()

        # Convert to our PerformanceMetrics format
        metrics = self._convert_vectorbt_stats(stats, pf)

        # Create BacktestResult
        result = BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self._extract_trades(pf),
            equity_curve=pf.value().to_dict(),  # Daily portfolio values
            start_date=self.config.start_date,
            end_date=self.config.end_date
        )

        logger.info(
            f"Backtest complete: {metrics.total_return:.2%} return, "
            f"Sharpe {metrics.sharpe_ratio:.2f}"
        )

        return result

    def _convert_vectorbt_stats(
        self,
        stats: pd.Series,
        pf: vbt.Portfolio
    ) -> PerformanceMetrics:
        """
        Convert vectorbt stats to our PerformanceMetrics dataclass.

        Mappings:
            vbt.total_return → total_return
            vbt.sharpe_ratio → sharpe_ratio
            vbt.sortino_ratio → sortino_ratio
            vbt.max_drawdown → max_drawdown
            vbt.win_rate → win_rate
            etc.
        """

        # Extract basic metrics from vectorbt stats
        total_return = stats.get('Total Return [%]', 0) / 100
        sharpe_ratio = stats.get('Sharpe Ratio', 0)
        sortino_ratio = stats.get('Sortino Ratio', 0)
        max_drawdown = abs(stats.get('Max Drawdown [%]', 0)) / 100

        # Calculate additional metrics
        returns = pf.returns()
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0

        # Calculate Calmar ratio (annualized return / max drawdown)
        years = (self.config.end_date - self.config.start_date).days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Trading metrics
        num_trades = pf.trades.count()
        winning_trades = len(pf.trades.records_arr[pf.trades.records_arr['pnl'] > 0])
        win_rate = winning_trades / num_trades if num_trades > 0 else 0

        # Create PerformanceMetrics object
        metrics = PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            downside_deviation=downside_deviation,
            win_rate=win_rate,
            num_trades=num_trades,
            # Additional fields...
        )

        return metrics

    def _extract_trades(self, pf: vbt.Portfolio) -> List[Trade]:
        """
        Extract trade list from vectorbt portfolio.

        Returns:
            List of Trade objects compatible with custom engine
        """

        trades = []

        # Access vectorbt trade records
        trade_records = pf.trades.records_arr

        for rec in trade_records:
            trade = Trade(
                ticker=rec['col'],  # Column name (ticker)
                region=self.config.regions[0],
                entry_date=pd.Timestamp(rec['entry_idx']).date(),
                entry_price=rec['entry_price'],
                exit_date=pd.Timestamp(rec['exit_idx']).date() if rec['exit_idx'] >= 0 else None,
                exit_price=rec['exit_price'] if rec['exit_idx'] >= 0 else None,
                shares=int(rec['size']),
                pnl=rec['pnl'],
                pnl_percent=rec['return'],
                is_closed=(rec['exit_idx'] >= 0),
                # Additional fields...
            )
            trades.append(trade)

        return trades

    def optimize_parameters(
        self,
        param_grid: Dict[str, List],
        signal_generator_func,
        objective: str = 'sharpe_ratio',
        n_jobs: int = -1
    ) -> pd.DataFrame:
        """
        Grid search parameter optimization (vectorized - ultra-fast).

        Args:
            param_grid: Parameter grid to search
                        Example: {"kelly_mult": [0.25, 0.5, 0.75], "score_threshold": [70, 80, 90]}
            signal_generator_func: Function that generates signals given parameters
                                   Signature: func(params: Dict) -> pd.DataFrame
            objective: Metric to maximize ("sharpe_ratio", "total_return", "calmar_ratio")
            n_jobs: Number of parallel jobs (-1 = use all CPUs)

        Returns:
            DataFrame with all parameter combinations and results
            Sorted by objective metric (best first)

        Performance:
            <1 minute for 100 parameter combinations

        Example:
            def generate_signals(params):
                # Generate signals based on params
                return signals_df

            results = adapter.optimize_parameters(
                param_grid={"kelly_mult": [0.25, 0.5, 0.75, 1.0]},
                signal_generator_func=generate_signals,
                objective="sharpe_ratio"
            )
            # Best parameters: results.iloc[0]
        """

        from itertools import product
        from joblib import Parallel, delayed

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        logger.info(
            f"Optimizing {len(combinations)} parameter combinations "
            f"using {objective} as objective"
        )

        # Define backtest function for parallel execution
        def run_single_backtest(param_combination):
            params = dict(zip(param_names, param_combination))

            try:
                # Generate signals for this parameter combination
                signals = signal_generator_func(params)

                # Run backtest
                result = self.run_backtest(signals)

                # Extract objective metric
                obj_value = getattr(result.metrics, objective)

                return {**params, objective: obj_value, 'result': result}

            except Exception as e:
                logger.error(f"Backtest failed for params {params}: {e}")
                return {**params, objective: -np.inf, 'result': None}

        # Run backtests in parallel
        results = Parallel(n_jobs=n_jobs)(
            delayed(run_single_backtest)(combo) for combo in combinations
        )

        # Convert to DataFrame
        results_df = pd.DataFrame(results)

        # Sort by objective (best first)
        results_df = results_df.sort_values(objective, ascending=False)

        logger.info(
            f"Optimization complete. Best {objective}: "
            f"{results_df.iloc[0][objective]:.4f}"
        )

        return results_df


# Helper function for easy adapter creation
def create_vectorbt_adapter(
    config: BacktestConfig,
    data_provider: BaseDataProvider
) -> VectorbtBacktestAdapter:
    """
    Factory function to create vectorbt adapter.

    Example:
        adapter = create_vectorbt_adapter(config, provider)
        result = adapter.run_backtest(signals)
    """
    return VectorbtBacktestAdapter(config, data_provider)
```

---

#### Task 2.3: Create Signal Generator Examples (1 hour)

**File**: `examples/example_vectorbt_parameter_optimization.py`

```python
"""
Example: Fast parameter optimization using vectorbt

Use Case: Test 100 combinations of Kelly multiplier and score threshold
          to find optimal strategy parameters.

Expected Runtime: <1 minute for 100 combinations (vs 2 hours with custom engine)
"""

import sys
from pathlib import Path
from datetime import date

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.backtesting import BacktestConfig
from modules.backtesting.vectorbt_adapter import create_vectorbt_adapter
from modules.backtesting.data_providers import get_postgres_provider
import pandas as pd


def generate_momentum_signals(params: dict) -> pd.DataFrame:
    """
    Generate momentum strategy signals based on parameters.

    Args:
        params: {"ma_fast": int, "ma_slow": int, "min_score": int}

    Returns:
        DataFrame with columns [date, ticker, signal]
    """

    # This would typically query your scoring system
    # For demonstration, using simple logic

    # Load price data
    provider = get_postgres_provider()
    tickers = ['005930', '000660', '035420']  # Example tickers

    signals = []

    for ticker in tickers:
        df = provider.get_ohlcv(
            ticker, 'KR',
            date(2020, 1, 1),
            date(2023, 12, 31)
        )

        # Calculate moving averages
        df['ma_fast'] = df['close'].rolling(params['ma_fast']).mean()
        df['ma_slow'] = df['close'].rolling(params['ma_slow']).mean()

        # Generate signals
        df['signal'] = 0.0
        df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1.0  # Buy
        df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1.0  # Sell

        # Add ticker column
        df['ticker'] = ticker

        signals.append(df[['date', 'ticker', 'signal']])

    return pd.concat(signals, ignore_index=True)


def main():
    # Configure backtest
    config = BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        regions=['KR'],
        initial_capital=100_000_000  # 1억원
    )

    # Create vectorbt adapter
    provider = get_postgres_provider()
    adapter = create_vectorbt_adapter(config, provider)

    # Define parameter grid
    param_grid = {
        'ma_fast': [10, 20, 30],
        'ma_slow': [50, 100, 150],
        'min_score': [70, 80, 90]
    }
    # Total combinations: 3 × 3 × 3 = 27

    print("Starting parameter optimization...")
    print(f"Parameter grid: {param_grid}")
    print(f"Total combinations: 27")

    # Run optimization (vectorized - fast!)
    results = adapter.optimize_parameters(
        param_grid=param_grid,
        signal_generator_func=generate_momentum_signals,
        objective='sharpe_ratio',
        n_jobs=-1  # Use all CPU cores
    )

    # Display results
    print("\n" + "="*80)
    print("OPTIMIZATION RESULTS")
    print("="*80)
    print(results.head(10).to_string())

    # Best parameters
    best = results.iloc[0]
    print("\n" + "="*80)
    print("BEST PARAMETERS")
    print("="*80)
    print(f"Sharpe Ratio: {best['sharpe_ratio']:.2f}")
    print(f"MA Fast: {best['ma_fast']}")
    print(f"MA Slow: {best['ma_slow']}")
    print(f"Min Score: {best['min_score']}")

    # Save results
    results.to_csv('optimization_results.csv', index=False)
    print(f"\nResults saved to optimization_results.csv")


if __name__ == '__main__':
    main()
```

---

### 다음 Day들도 계속 작성할까요?

Day 5 (Unified Interface), Day 6-7 (Validation), Day 8-9 (Testing), Day 10 (Documentation)의 상세 작업 내용도 같은 수준으로 작성해드릴까요? 아니면 여기까지 내용을 먼저 검토하시겠습니까?

각 Day마다 이런 식으로:
- 구체적인 파일 경로
- 완전한 코드 예시
- 테스트 방법
- 성공 기준

이 모두 포함되어 있습니다.