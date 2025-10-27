"""
PostgreSQL + TimescaleDB Database Manager

Provides backward-compatible interface with SQLiteDatabaseManager
while leveraging PostgreSQL-specific features:
- Connection pooling (ThreadedConnectionPool)
- Bulk insert optimization (COPY command)
- Hypertable and continuous aggregate support
- Region-aware composite keys

Author: Quant Platform Development Team
Date: 2025-10-20
"""

import psycopg2
from psycopg2 import pool, extras, sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
import pandas as pd
import logging
import os
from dotenv import load_dotenv
from io import StringIO

logger = logging.getLogger(__name__)


class PostgresConnection:
    """Context manager for PostgreSQL connection pooling"""

    def __init__(self, pool, conn):
        self.pool = pool
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Return connection to pool on exit"""
        if exc_type is not None:
            self.conn.rollback()
        self.pool.putconn(self.conn)
        return False  # Propagate exception

    def cursor(self, **kwargs):
        """Create cursor with RealDictCursor by default"""
        if 'cursor_factory' not in kwargs:
            kwargs['cursor_factory'] = extras.RealDictCursor
        return self.conn.cursor(**kwargs)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


class PostgresDatabaseManager:
    """
    PostgreSQL + TimescaleDB Database Manager

    Provides backward-compatible interface with SQLiteDatabaseManager
    while leveraging PostgreSQL-specific features.
    """

    def __init__(self,
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None,
                 pool_min_conn: int = 10,
                 pool_max_conn: int = 30):
        """
        Initialize PostgreSQL connection pool

        Args:
            host: PostgreSQL host (default: localhost)
            port: PostgreSQL port (default: 5432)
            database: Database name (default: quant_platform)
            user: Database user (default: from .env)
            password: Database password (default: from .env)
            pool_min_conn: Minimum connections in pool
            pool_max_conn: Maximum connections in pool
        """
        # Load from .env if not provided
        load_dotenv()

        self.host = host or os.getenv('POSTGRES_HOST', 'localhost')
        self.port = port or int(os.getenv('POSTGRES_PORT', 5432))
        self.database = database or os.getenv('POSTGRES_DB', 'quant_platform')
        self.user = user or os.getenv('POSTGRES_USER')
        self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        # Create connection pool
        try:
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                pool_min_conn,
                pool_max_conn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"✅ PostgreSQL connection pool created: {self.database}")
            logger.info(f"   Host: {self.host}:{self.port}")
            logger.info(f"   Pool: {pool_min_conn}-{pool_max_conn} connections")
        except Exception as e:
            logger.error(f"❌ Failed to create connection pool: {e}")
            raise

        # Track last cursor state (for backward compatibility with DART script)
        self._last_rowcount = 0
        self._last_statusmessage = ""

    def _get_connection(self):
        """Get connection from pool (context manager support)"""
        conn = self.pool.getconn()
        return PostgresConnection(self.pool, conn)

    def close_pool(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("🔒 PostgreSQL connection pool closed")

    # ========================================
    # Core Helper Methods
    # ========================================

    def _execute_query(self, query: str, params: tuple = None,
                       fetch_one: bool = False,
                       fetch_all: bool = False,
                       commit: bool = False) -> Any:
        """
        Execute query with connection pooling

        Args:
            query: SQL query (use %s placeholders)
            params: Query parameters
            fetch_one: Return single row
            fetch_all: Return all rows
            commit: Commit transaction

        Returns:
            Query result or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                cursor.execute(query, params)

                if commit:
                    conn.commit()

                if fetch_one:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch_all:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    return cursor.rowcount

            except psycopg2.IntegrityError as e:
                conn.rollback()
                logger.error(f"❌ Integrity constraint violation: {e}")
                logger.error(f"   Query: {query}")
                logger.error(f"   Params: {params}")
                raise

            except psycopg2.DataError as e:
                conn.rollback()
                logger.error(f"❌ Data type error: {e}")
                logger.error(f"   Query: {query}")
                logger.error(f"   Params: {params}")
                raise

            except psycopg2.OperationalError as e:
                conn.rollback()
                logger.error(f"❌ Operational error (connection/pool): {e}")
                raise

            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Unexpected error: {e}")
                logger.error(f"   Query: {query}")
                logger.error(f"   Params: {params}")
                raise

            finally:
                cursor.close()

    # ===============================================
    # Public Query Methods (for backfill scripts)
    # ===============================================

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Public method for SELECT queries (returns all rows)

        Args:
            query: SQL SELECT query
            params: Query parameters

        Returns:
            List of dictionaries (rows)
        """
        return self._execute_query(query, params, fetch_all=True) or []

    def execute_update(self, query: str, params: tuple = None) -> bool:
        """
        Public method for INSERT/UPDATE/DELETE queries
        Captures cursor.rowcount and cursor.statusmessage for UPSERT detection

        Args:
            query: SQL INSERT/UPDATE/DELETE query
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                # Use regular cursor for INSERT/UPDATE/DELETE
                # RealDictCursor has issues with ON CONFLICT/UPSERT queries
                cursor = conn.cursor()
                logger.debug(f"Created cursor type: {type(cursor)}")
                try:
                    logger.info(f"DEBUG: Query first 200 chars: {query[:200]}")
                    logger.info(f"DEBUG: Params: {params}")
                    cursor.execute(query, params)
                    conn.commit()

                    # Capture cursor state for backward compatibility
                    self._last_rowcount = cursor.rowcount
                    self._last_statusmessage = cursor.statusmessage or ""

                    return True
                except Exception as e:
                    conn.rollback()
                    logger.error(f"❌ Execute update failed: {e}")
                    logger.error(f"   Query placeholders: {query.count('%s') if query else 'N/A'}")
                    logger.error(f"   Params count: {len(params) if params else 0}")
                    import traceback
                    logger.error(f"   Traceback: {traceback.format_exc()}")
                    return False
                finally:
                    cursor.close()
        except Exception as e:
            logger.error(f"❌ Execute update failed (connection): {e}")
            return False

    @property
    def cursor(self):
        """
        Fake cursor object for backward compatibility with DART script
        Exposes rowcount and statusmessage from last execute_update() call
        """
        class CursorProxy:
            def __init__(self, rowcount, statusmessage):
                self.rowcount = rowcount
                self.statusmessage = statusmessage

        return CursorProxy(self._last_rowcount, self._last_statusmessage)

    def _convert_boolean(self, value: Any) -> Optional[bool]:
        """Convert SQLite 0/1 to PostgreSQL TRUE/FALSE"""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        if isinstance(value, str):
            return value.lower() in ('1', 'true', 't', 'yes', 'y')
        return bool(value)

    def _convert_datetime(self, value: Any) -> Optional[str]:
        """Convert datetime to ISO format string"""
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    def _infer_region(self, ticker: str) -> str:
        """
        Infer region from ticker format (best-effort)

        Args:
            ticker: Ticker symbol

        Returns:
            Region code (KR, US, HK, etc.)
        """
        if ticker.isdigit():
            if len(ticker) == 6:
                # Korean stocks (6 digits)
                return 'KR'
            elif ticker.startswith('00') or ticker.startswith('03'):
                # Hong Kong stocks
                return 'HK'
        elif ticker.isalpha():
            # US stocks (alphabetic)
            return 'US'

        # Default fallback
        return 'US'

    # ========================================
    # Ticker Management Methods
    # ========================================

    def insert_ticker(self, ticker_data: Dict) -> bool:
        """
        Insert or update ticker (PostgreSQL with ON CONFLICT)

        Args:
            ticker_data: Dictionary with ticker information
                Required: ticker, name, exchange, region
                Optional: name_eng, currency, asset_type, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now()

            self._execute_query("""
                INSERT INTO tickers (
                    ticker, name, name_eng, exchange, region, currency,
                    asset_type, listing_date, lot_size,
                    is_active, delisting_date, created_at, last_updated,
                    data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region) DO UPDATE SET
                    name = EXCLUDED.name,
                    name_eng = EXCLUDED.name_eng,
                    exchange = EXCLUDED.exchange,
                    currency = EXCLUDED.currency,
                    asset_type = EXCLUDED.asset_type,
                    listing_date = EXCLUDED.listing_date,
                    lot_size = EXCLUDED.lot_size,
                    is_active = EXCLUDED.is_active,
                    delisting_date = EXCLUDED.delisting_date,
                    last_updated = EXCLUDED.last_updated,
                    data_source = EXCLUDED.data_source
            """, (
                ticker_data['ticker'],
                ticker_data['name'],
                ticker_data.get('name_eng'),
                ticker_data['exchange'],
                ticker_data['region'],
                ticker_data.get('currency', 'KRW'),
                ticker_data.get('asset_type', 'STOCK'),
                ticker_data.get('listing_date'),
                ticker_data.get('lot_size', 1),
                self._convert_boolean(ticker_data.get('is_active', 1)),
                ticker_data.get('delisting_date'),
                now,
                now,
                ticker_data.get('data_source')
            ), commit=True)

            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert ticker {ticker_data.get('ticker')}: {e}")
            return False

    def get_ticker(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Get ticker details (region-aware)

        Args:
            ticker: Ticker symbol (005930, AAPL)
            region: Region code (KR, US, CN, HK, JP, VN)

        Returns:
            Ticker dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM tickers
            WHERE ticker = %s AND region = %s
        """, (ticker, region), fetch_one=True)

    def get_ticker_legacy(self, ticker: str, region: str = None) -> Optional[Dict]:
        """
        Legacy method for backward compatibility

        If region is None, attempt to infer from ticker format.

        Args:
            ticker: Ticker symbol
            region: Region code (optional)

        Returns:
            Ticker dictionary or None
        """
        if region is None:
            region = self._infer_region(ticker)

        return self.get_ticker(ticker, region)

    def get_tickers(self, region: str, asset_type: str = None,
                    is_active: bool = True) -> List[Dict]:
        """
        Get tickers by region and asset type

        Args:
            region: Region code (KR, US, CN, HK, JP, VN)
            asset_type: Asset type filter (STOCK, ETF, etc.)
            is_active: Active status filter

        Returns:
            List of ticker dictionaries
        """
        query = "SELECT * FROM tickers WHERE region = %s"
        params = [region]

        if asset_type:
            query += " AND asset_type = %s"
            params.append(asset_type)

        if is_active is not None:
            query += " AND is_active = %s"
            params.append(is_active)

        query += " ORDER BY ticker"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def update_ticker(self, ticker: str, region: str, update_data: Dict) -> bool:
        """
        Update ticker fields

        Args:
            ticker: Ticker symbol
            region: Region code
            update_data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build UPDATE SET clause dynamically
            set_clauses = []
            params = []

            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                if key == 'is_active':
                    params.append(self._convert_boolean(value))
                else:
                    params.append(value)

            # Add WHERE clause params
            params.extend([ticker, region])

            query = f"""
                UPDATE tickers
                SET {', '.join(set_clauses)}, last_updated = %s
                WHERE ticker = %s AND region = %s
            """
            params.insert(-2, datetime.now())

            self._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update ticker {ticker}: {e}")
            return False

    def delete_ticker(self, ticker: str, region: str) -> bool:
        """
        Delete ticker (CASCADE to related tables)

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                DELETE FROM tickers
                WHERE ticker = %s AND region = %s
            """, (ticker, region), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete ticker {ticker}: {e}")
            return False

    def count_tickers(self, region: str = None, asset_type: str = None) -> int:
        """
        Count tickers with optional filters

        Args:
            region: Region filter (optional)
            asset_type: Asset type filter (optional)

        Returns:
            Count of tickers
        """
        query = "SELECT COUNT(*) as count FROM tickers WHERE 1=1"
        params = []

        if region:
            query += " AND region = %s"
            params.append(region)

        if asset_type:
            query += " AND asset_type = %s"
            params.append(asset_type)

        result = self._execute_query(query, tuple(params) if params else None, fetch_one=True)
        return result['count'] if result else 0

    # ========================================
    # OHLCV Data Methods
    # ========================================

    def insert_ohlcv(self, ticker: str, region: str, timeframe: str,
                     date_str: str, open_price: float, high: float,
                     low: float, close: float, volume: int) -> bool:
        """
        Insert single OHLCV record

        Args:
            ticker: Ticker symbol
            region: Region code
            timeframe: Timeframe (D, W, M)
            date_str: Date string (YYYY-MM-DD)
            open_price: Open price
            high: High price
            low: Low price
            close: Close price
            volume: Volume

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO ohlcv_data (
                    ticker, region, timeframe, date,
                    open, high, low, close, volume, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, timeframe, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """, (
                ticker, region, timeframe, date_str,
                open_price, high, low, close, volume, datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert OHLCV for {ticker}: {e}")
            return False

    def insert_ohlcv_bulk(self, ticker: str, ohlcv_df: pd.DataFrame,
                          timeframe: str = 'D', region: str = None) -> int:
        """
        Bulk insert OHLCV data using PostgreSQL COPY command

        Performance: 10K rows <1 second (vs pandas.to_sql ~10 seconds)

        Args:
            ticker: Ticker symbol
            ohlcv_df: DataFrame with columns (date, open, high, low, close, volume)
            timeframe: Timeframe (D, W, M)
            region: Region code (KR, US, etc.)

        Returns:
            Number of rows inserted
        """
        if ohlcv_df.empty:
            return 0

        if region is None:
            region = self._infer_region(ticker)

        # Prepare DataFrame
        insert_df = ohlcv_df.copy()
        insert_df['ticker'] = ticker
        insert_df['timeframe'] = timeframe
        insert_df['region'] = region
        insert_df['created_at'] = datetime.now()

        # Required columns in correct order
        columns = ['ticker', 'region', 'timeframe', 'date',
                   'open', 'high', 'low', 'close', 'volume', 'created_at']

        # Add missing columns with None
        for col in columns:
            if col not in insert_df.columns:
                insert_df[col] = None

        # Reorder columns
        insert_df = insert_df[columns]

        # Convert to CSV in-memory (for COPY)
        buffer = StringIO()
        insert_df.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
        buffer.seek(0)

        # Execute COPY command
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.copy_expert(
                    """
                    COPY ohlcv_data (ticker, region, timeframe, date,
                                     open, high, low, close, volume, created_at)
                    FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')
                    """,
                    buffer
                )
                conn.commit()
                logger.info(f"✅ Bulk inserted {len(insert_df)} OHLCV rows for {ticker}")
                return len(insert_df)
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Bulk insert failed for {ticker}: {e}")
                raise
            finally:
                cursor.close()

    def get_ohlcv_data(self, ticker: str, start_date: str = None,
                       end_date: str = None, timeframe: str = 'D',
                       region: str = None) -> pd.DataFrame:
        """
        Get OHLCV data for ticker from PostgreSQL Hypertable

        Performance: Leverages TimescaleDB hypertable partitioning

        Args:
            ticker: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            timeframe: Timeframe (D, W, M)
            region: Region code (required for composite key)

        Returns:
            DataFrame with OHLCV data
        """
        if region is None:
            region = self._infer_region(ticker)

        query = """
            SELECT * FROM ohlcv_data
            WHERE ticker = %s AND timeframe = %s AND region = %s
        """
        params = [ticker, timeframe, region]

        if start_date:
            query += " AND date >= %s::DATE"
            params.append(start_date)

        if end_date:
            query += " AND date <= %s::DATE"
            params.append(end_date)

        query += " ORDER BY date ASC"

        # Use psycopg2 with pandas
        with self._get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=tuple(params))

        return df

    def get_latest_ohlcv(self, ticker: str, timeframe: str = 'D',
                         region: str = None) -> Optional[Dict]:
        """
        Get latest OHLCV record for ticker

        Args:
            ticker: Ticker symbol
            timeframe: Timeframe (D, W, M)
            region: Region code

        Returns:
            Latest OHLCV dictionary or None
        """
        if region is None:
            region = self._infer_region(ticker)

        return self._execute_query("""
            SELECT * FROM ohlcv_data
            WHERE ticker = %s AND timeframe = %s AND region = %s
            ORDER BY date DESC
            LIMIT 1
        """, (ticker, timeframe, region), fetch_one=True)

    def delete_old_ohlcv(self, days_to_keep: int = 250) -> int:
        """
        Delete OHLCV data older than specified days

        Note: For Quant Platform, we want unlimited retention,
        so this method is disabled by default.

        Args:
            days_to_keep: Number of days to retain (default: 250)

        Returns:
            Number of rows deleted
        """
        logger.warning(f"⚠️  delete_old_ohlcv() called - Quant Platform has unlimited retention policy")
        logger.warning(f"   Skipping deletion. Use manual cleanup if needed.")
        return 0

    # ========================================
    # Stock Details Methods
    # ========================================

    def insert_stock_details(self, stock_data: Dict) -> bool:
        """
        Insert or update stock details

        Args:
            stock_data: Dictionary with stock information
                Required: ticker, region
                Optional: sector, sector_code, industry, industry_code, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now()

            self._execute_query("""
                INSERT INTO stock_details (
                    ticker, region, sector, sector_code, industry, industry_code,
                    is_spac, is_preferred, par_value,
                    created_at, last_updated
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region) DO UPDATE SET
                    sector = EXCLUDED.sector,
                    sector_code = EXCLUDED.sector_code,
                    industry = EXCLUDED.industry,
                    industry_code = EXCLUDED.industry_code,
                    is_spac = EXCLUDED.is_spac,
                    is_preferred = EXCLUDED.is_preferred,
                    par_value = EXCLUDED.par_value,
                    last_updated = EXCLUDED.last_updated
            """, (
                stock_data['ticker'],
                stock_data['region'],
                stock_data.get('sector'),
                stock_data.get('sector_code'),
                stock_data.get('industry'),
                stock_data.get('industry_code'),
                self._convert_boolean(stock_data.get('is_spac', False)),
                self._convert_boolean(stock_data.get('is_preferred', False)),
                stock_data.get('par_value'),
                now,
                now
            ), commit=True)

            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert stock details for {stock_data.get('ticker')}: {e}")
            return False

    def get_stock_details(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Get stock details

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            Stock details dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM stock_details
            WHERE ticker = %s AND region = %s
        """, (ticker, region), fetch_one=True)

    def get_stocks_by_sector(self, sector_code: str, region: str = None) -> List[Dict]:
        """
        Get stocks by sector

        Args:
            sector_code: GICS sector code
            region: Region filter (optional)

        Returns:
            List of stock dictionaries
        """
        query = """
            SELECT t.*, sd.sector, sd.industry
            FROM tickers t
            JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE sd.sector_code = %s
        """
        params = [sector_code]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY t.ticker"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_stocks_by_industry(self, industry_code: str, region: str = None) -> List[Dict]:
        """
        Get stocks by industry

        Args:
            industry_code: Industry code
            region: Region filter (optional)

        Returns:
            List of stock dictionaries
        """
        query = """
            SELECT t.*, sd.sector, sd.industry
            FROM tickers t
            JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE sd.industry_code = %s
        """
        params = [industry_code]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY t.ticker"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def update_stock_details(self, ticker: str, region: str, update_data: Dict) -> bool:
        """
        Update stock details fields

        Args:
            ticker: Ticker symbol
            region: Region code
            update_data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            set_clauses = []
            params = []

            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                if key in ('is_spac', 'is_preferred'):
                    params.append(self._convert_boolean(value))
                else:
                    params.append(value)

            params.extend([datetime.now(), ticker, region])

            query = f"""
                UPDATE stock_details
                SET {', '.join(set_clauses)}, last_updated = %s
                WHERE ticker = %s AND region = %s
            """

            self._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update stock details for {ticker}: {e}")
            return False

    def delete_stock_details(self, ticker: str, region: str) -> bool:
        """
        Delete stock details

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                DELETE FROM stock_details
                WHERE ticker = %s AND region = %s
            """, (ticker, region), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete stock details for {ticker}: {e}")
            return False

    def count_stocks_by_sector(self, region: str = None) -> List[Dict]:
        """
        Count stocks by sector

        Args:
            region: Region filter (optional)

        Returns:
            List of {sector, sector_code, count} dictionaries
        """
        query = """
            SELECT sd.sector, sd.sector_code, COUNT(*) as count
            FROM stock_details sd
            JOIN tickers t ON sd.ticker = t.ticker AND sd.region = t.region
            WHERE t.is_active = TRUE
        """
        params = []

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " GROUP BY sd.sector, sd.sector_code ORDER BY count DESC"

        return self._execute_query(query, tuple(params) if params else None, fetch_all=True)

    # ========================================
    # ETF Details Methods
    # ========================================

    def insert_etf_details(self, etf_data: Dict) -> bool:
        """
        Insert or update ETF details

        Args:
            etf_data: Dictionary with ETF information
                Required: ticker, region, tracking_index, expense_ratio
                Optional: issuer, aum, sector_theme, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now()

            self._execute_query("""
                INSERT INTO etf_details (
                    ticker, region, issuer, inception_date, underlying_asset_class,
                    tracking_index, geographic_region, sector_theme, fund_type,
                    aum, listed_shares, underlying_asset_count,
                    expense_ratio, ter, leverage_ratio, currency_hedged,
                    tracking_error_20d, tracking_error_60d, tracking_error_120d, tracking_error_250d,
                    created_at, last_updated
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region) DO UPDATE SET
                    issuer = EXCLUDED.issuer,
                    inception_date = EXCLUDED.inception_date,
                    underlying_asset_class = EXCLUDED.underlying_asset_class,
                    tracking_index = EXCLUDED.tracking_index,
                    geographic_region = EXCLUDED.geographic_region,
                    sector_theme = EXCLUDED.sector_theme,
                    fund_type = EXCLUDED.fund_type,
                    aum = EXCLUDED.aum,
                    listed_shares = EXCLUDED.listed_shares,
                    underlying_asset_count = EXCLUDED.underlying_asset_count,
                    expense_ratio = EXCLUDED.expense_ratio,
                    ter = EXCLUDED.ter,
                    leverage_ratio = EXCLUDED.leverage_ratio,
                    currency_hedged = EXCLUDED.currency_hedged,
                    tracking_error_20d = EXCLUDED.tracking_error_20d,
                    tracking_error_60d = EXCLUDED.tracking_error_60d,
                    tracking_error_120d = EXCLUDED.tracking_error_120d,
                    tracking_error_250d = EXCLUDED.tracking_error_250d,
                    last_updated = EXCLUDED.last_updated
            """, (
                etf_data['ticker'],
                etf_data['region'],
                etf_data.get('issuer'),
                etf_data.get('inception_date'),
                etf_data.get('underlying_asset_class'),
                etf_data['tracking_index'],
                etf_data.get('geographic_region'),
                etf_data.get('sector_theme'),
                etf_data.get('fund_type'),
                etf_data.get('aum'),
                etf_data.get('listed_shares'),
                etf_data.get('underlying_asset_count'),
                etf_data['expense_ratio'],
                etf_data.get('ter'),
                etf_data.get('leverage_ratio'),
                self._convert_boolean(etf_data.get('currency_hedged')),
                etf_data.get('tracking_error_20d'),
                etf_data.get('tracking_error_60d'),
                etf_data.get('tracking_error_120d'),
                etf_data.get('tracking_error_250d'),
                now,
                now
            ), commit=True)

            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert ETF details for {etf_data.get('ticker')}: {e}")
            return False

    def get_etf_details(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Get ETF details

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            ETF details dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM etf_details
            WHERE ticker = %s AND region = %s
        """, (ticker, region), fetch_one=True)

    def get_etfs_by_theme(self, sector_theme: str, region: str = None) -> List[Dict]:
        """
        Get ETFs by sector/theme

        Args:
            sector_theme: Sector or theme (e.g., "semiconductor", "biotech")
            region: Region filter (optional)

        Returns:
            List of ETF dictionaries
        """
        query = """
            SELECT t.*, ed.tracking_index, ed.expense_ratio, ed.aum
            FROM tickers t
            JOIN etf_details ed ON t.ticker = ed.ticker AND t.region = ed.region
            WHERE ed.sector_theme ILIKE %s
        """
        params = [f'%{sector_theme}%']

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY ed.aum DESC NULLS LAST"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_etfs_by_expense_ratio(self, max_expense_ratio: float, region: str = None) -> List[Dict]:
        """
        Get ETFs with expense ratio below threshold

        Args:
            max_expense_ratio: Maximum expense ratio (e.g., 0.5 for 0.5%)
            region: Region filter (optional)

        Returns:
            List of ETF dictionaries sorted by expense ratio
        """
        query = """
            SELECT t.*, ed.tracking_index, ed.expense_ratio, ed.aum
            FROM tickers t
            JOIN etf_details ed ON t.ticker = ed.ticker AND t.region = ed.region
            WHERE ed.expense_ratio <= %s
        """
        params = [max_expense_ratio]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY ed.expense_ratio ASC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_top_etfs_by_aum(self, limit: int = 10, region: str = None) -> List[Dict]:
        """
        Get top ETFs by AUM (Assets Under Management)

        Args:
            limit: Number of ETFs to return
            region: Region filter (optional)

        Returns:
            List of ETF dictionaries sorted by AUM descending
        """
        query = """
            SELECT t.*, ed.tracking_index, ed.expense_ratio, ed.aum
            FROM tickers t
            JOIN etf_details ed ON t.ticker = ed.ticker AND t.region = ed.region
            WHERE ed.aum IS NOT NULL
        """
        params = []

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += f" ORDER BY ed.aum DESC LIMIT {limit}"

        return self._execute_query(query, tuple(params) if params else None, fetch_all=True)

    def update_etf_aum(self, ticker: str, region: str, aum: int, listed_shares: int = None) -> bool:
        """
        Update ETF AUM and listed shares

        Args:
            ticker: Ticker symbol
            region: Region code
            aum: Assets Under Management
            listed_shares: Listed shares (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            if listed_shares is not None:
                self._execute_query("""
                    UPDATE etf_details
                    SET aum = %s, listed_shares = %s, last_updated = %s
                    WHERE ticker = %s AND region = %s
                """, (aum, listed_shares, datetime.now(), ticker, region), commit=True)
            else:
                self._execute_query("""
                    UPDATE etf_details
                    SET aum = %s, last_updated = %s
                    WHERE ticker = %s AND region = %s
                """, (aum, datetime.now(), ticker, region), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update ETF AUM for {ticker}: {e}")
            return False

    def delete_etf_details(self, ticker: str, region: str) -> bool:
        """
        Delete ETF details

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                DELETE FROM etf_details
                WHERE ticker = %s AND region = %s
            """, (ticker, region), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete ETF details for {ticker}: {e}")
            return False

    def insert_etf_holdings(self, etf_ticker: str, stock_ticker: str, region: str,
                           weight: float, as_of_date: str, **kwargs) -> bool:
        """
        Insert ETF holding (ETF composition)

        Args:
            etf_ticker: ETF ticker symbol
            stock_ticker: Stock ticker symbol
            region: Region code
            weight: Weight percentage (0-100)
            as_of_date: Data date (YYYY-MM-DD)
            **kwargs: Additional fields (shares, market_value, rank_in_etf, etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO etf_holdings (
                    etf_ticker, stock_ticker, region, weight, as_of_date,
                    shares, market_value, rank_in_etf, weight_change_from_prev,
                    created_at, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (etf_ticker, stock_ticker, region, as_of_date) DO UPDATE SET
                    weight = EXCLUDED.weight,
                    shares = EXCLUDED.shares,
                    market_value = EXCLUDED.market_value,
                    rank_in_etf = EXCLUDED.rank_in_etf,
                    weight_change_from_prev = EXCLUDED.weight_change_from_prev,
                    data_source = EXCLUDED.data_source
            """, (
                etf_ticker,
                stock_ticker,
                region,
                weight,
                as_of_date,
                kwargs.get('shares'),
                kwargs.get('market_value'),
                kwargs.get('rank_in_etf'),
                kwargs.get('weight_change_from_prev'),
                datetime.now(),
                kwargs.get('data_source')
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert ETF holding {etf_ticker}/{stock_ticker}: {e}")
            return False

    def get_etf_holdings(self, etf_ticker: str, region: str, as_of_date: str = None) -> List[Dict]:
        """
        Get ETF holdings (composition)

        Args:
            etf_ticker: ETF ticker symbol
            region: Region code
            as_of_date: Data date (optional, defaults to latest)

        Returns:
            List of holdings sorted by weight descending
        """
        if as_of_date:
            query = """
                SELECT * FROM etf_holdings
                WHERE etf_ticker = %s AND region = %s AND as_of_date = %s
                ORDER BY weight DESC
            """
            params = (etf_ticker, region, as_of_date)
        else:
            query = """
                SELECT * FROM etf_holdings
                WHERE etf_ticker = %s AND region = %s
                  AND as_of_date = (
                      SELECT MAX(as_of_date) FROM etf_holdings
                      WHERE etf_ticker = %s AND region = %s
                  )
                ORDER BY weight DESC
            """
            params = (etf_ticker, region, etf_ticker, region)

        return self._execute_query(query, params, fetch_all=True)

    def get_stocks_in_etf(self, etf_ticker: str, region: str, min_weight: float = 0) -> List[Dict]:
        """
        Get stocks held by ETF

        Args:
            etf_ticker: ETF ticker symbol
            region: Region code
            min_weight: Minimum weight threshold (default: 0)

        Returns:
            List of stock tickers with weights
        """
        query = """
            SELECT eh.stock_ticker, eh.weight, eh.shares, t.name
            FROM etf_holdings eh
            JOIN tickers t ON eh.stock_ticker = t.ticker AND eh.region = t.region
            WHERE eh.etf_ticker = %s AND eh.region = %s
              AND eh.weight >= %s
              AND eh.as_of_date = (
                  SELECT MAX(as_of_date) FROM etf_holdings
                  WHERE etf_ticker = %s AND region = %s
              )
            ORDER BY eh.weight DESC
        """
        return self._execute_query(query, (etf_ticker, region, min_weight, etf_ticker, region), fetch_all=True)

    def get_etfs_holding_stock(self, stock_ticker: str, region: str, min_weight: float = 0) -> List[Dict]:
        """
        Get ETFs holding a specific stock

        Args:
            stock_ticker: Stock ticker symbol
            region: Region code
            min_weight: Minimum weight threshold (default: 0)

        Returns:
            List of ETFs with weights
        """
        query = """
            SELECT eh.etf_ticker, eh.weight, t.name, ed.aum
            FROM etf_holdings eh
            JOIN tickers t ON eh.etf_ticker = t.ticker AND eh.region = t.region
            LEFT JOIN etf_details ed ON eh.etf_ticker = ed.ticker AND eh.region = ed.region
            WHERE eh.stock_ticker = %s AND eh.region = %s
              AND eh.weight >= %s
              AND eh.as_of_date = (
                  SELECT MAX(as_of_date) FROM etf_holdings
                  WHERE stock_ticker = %s AND region = %s
              )
            ORDER BY ed.aum DESC NULLS LAST, eh.weight DESC
        """
        return self._execute_query(query, (stock_ticker, region, min_weight, stock_ticker, region), fetch_all=True)

    # ========================================
    # Technical Analysis Methods
    # ========================================

    def insert_technical_analysis(self, ta_data: Dict) -> bool:
        """
        Insert or update technical analysis data

        Args:
            ta_data: Dictionary with technical analysis information
                Required: ticker, region, analysis_date
                Optional: stage, scores, signals, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO technical_analysis (
                    ticker, region, analysis_date, stage, stage_confidence,
                    layer1_macro_score, layer2_structural_score, layer3_micro_score, total_score,
                    signal, signal_strength, gpt_pattern, gpt_confidence, gpt_analysis,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, analysis_date) DO UPDATE SET
                    stage = EXCLUDED.stage,
                    stage_confidence = EXCLUDED.stage_confidence,
                    layer1_macro_score = EXCLUDED.layer1_macro_score,
                    layer2_structural_score = EXCLUDED.layer2_structural_score,
                    layer3_micro_score = EXCLUDED.layer3_micro_score,
                    total_score = EXCLUDED.total_score,
                    signal = EXCLUDED.signal,
                    signal_strength = EXCLUDED.signal_strength,
                    gpt_pattern = EXCLUDED.gpt_pattern,
                    gpt_confidence = EXCLUDED.gpt_confidence,
                    gpt_analysis = EXCLUDED.gpt_analysis
            """, (
                ta_data['ticker'],
                ta_data['region'],
                ta_data['analysis_date'],
                ta_data.get('stage'),
                ta_data.get('stage_confidence'),
                ta_data.get('layer1_macro_score'),
                ta_data.get('layer2_structural_score'),
                ta_data.get('layer3_micro_score'),
                ta_data.get('total_score'),
                ta_data.get('signal'),
                ta_data.get('signal_strength'),
                ta_data.get('gpt_pattern'),
                ta_data.get('gpt_confidence'),
                ta_data.get('gpt_analysis'),
                datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert technical analysis for {ta_data.get('ticker')}: {e}")
            return False

    def get_technical_analysis(self, ticker: str, region: str, analysis_date: str = None) -> Optional[Dict]:
        """
        Get technical analysis data

        Args:
            ticker: Ticker symbol
            region: Region code
            analysis_date: Analysis date (optional, defaults to latest)

        Returns:
            Technical analysis dictionary or None
        """
        if analysis_date:
            return self._execute_query("""
                SELECT * FROM technical_analysis
                WHERE ticker = %s AND region = %s AND analysis_date = %s
            """, (ticker, region, analysis_date), fetch_one=True)
        else:
            return self._execute_query("""
                SELECT * FROM technical_analysis
                WHERE ticker = %s AND region = %s
                ORDER BY analysis_date DESC
                LIMIT 1
            """, (ticker, region), fetch_one=True)

    def get_stocks_by_signal(self, signal: str, region: str = None, min_score: float = 70) -> List[Dict]:
        """
        Get stocks by signal (BUY, WATCH, AVOID)

        Args:
            signal: Signal type (BUY, WATCH, AVOID)
            region: Region filter (optional)
            min_score: Minimum total score threshold

        Returns:
            List of stocks with latest technical analysis
        """
        query = """
            SELECT t.*, ta.total_score, ta.signal, ta.analysis_date
            FROM tickers t
            JOIN technical_analysis ta ON t.ticker = ta.ticker AND t.region = ta.region
            WHERE ta.signal = %s AND ta.total_score >= %s
              AND ta.analysis_date = (
                  SELECT MAX(analysis_date) FROM technical_analysis
                  WHERE ticker = t.ticker AND region = t.region
              )
        """
        params = [signal, min_score]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY ta.total_score DESC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_stocks_by_stage(self, stage: int, region: str = None) -> List[Dict]:
        """
        Get stocks by Weinstein stage

        Args:
            stage: Stage number (1, 2, 3, 4)
            region: Region filter (optional)

        Returns:
            List of stocks in specified stage
        """
        query = """
            SELECT t.*, ta.stage, ta.stage_confidence, ta.total_score
            FROM tickers t
            JOIN technical_analysis ta ON t.ticker = ta.ticker AND t.region = ta.region
            WHERE ta.stage = %s
              AND ta.analysis_date = (
                  SELECT MAX(analysis_date) FROM technical_analysis
                  WHERE ticker = t.ticker AND region = t.region
              )
        """
        params = [stage]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY ta.stage_confidence DESC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def update_technical_scores(self, ticker: str, region: str, analysis_date: str, scores: Dict) -> bool:
        """
        Update technical analysis scores

        Args:
            ticker: Ticker symbol
            region: Region code
            analysis_date: Analysis date
            scores: Dictionary of score fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            set_clauses = []
            params = []

            for key, value in scores.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)

            params.extend([ticker, region, analysis_date])

            query = f"""
                UPDATE technical_analysis
                SET {', '.join(set_clauses)}
                WHERE ticker = %s AND region = %s AND analysis_date = %s
            """

            self._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update technical scores for {ticker}: {e}")
            return False

    def delete_old_technical_analysis(self, days_to_keep: int = 90) -> int:
        """
        Delete technical analysis data older than specified days

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of rows deleted
        """
        try:
            result = self._execute_query("""
                DELETE FROM technical_analysis
                WHERE analysis_date < CURRENT_DATE - INTERVAL '%s days'
            """, (days_to_keep,), commit=True)
            logger.info(f"✅ Deleted {result} old technical analysis records (older than {days_to_keep} days)")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to delete old technical analysis: {e}")
            return 0

    # ========================================
    # Fundamentals Methods
    # ========================================

    def insert_fundamentals(self, fund_data: Dict) -> bool:
        """
        Insert or update fundamentals data

        Args:
            fund_data: Dictionary with fundamentals information
                Required: ticker, region, date, period_type
                Optional: market_cap, per, pbr, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO ticker_fundamentals (
                    ticker, region, date, period_type,
                    shares_outstanding, market_cap, close_price,
                    per, pbr, psr, pcr, ev, ev_ebitda,
                    dividend_yield, dividend_per_share,
                    created_at, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, period_type) DO UPDATE SET
                    shares_outstanding = EXCLUDED.shares_outstanding,
                    market_cap = EXCLUDED.market_cap,
                    close_price = EXCLUDED.close_price,
                    per = EXCLUDED.per,
                    pbr = EXCLUDED.pbr,
                    psr = EXCLUDED.psr,
                    pcr = EXCLUDED.pcr,
                    ev = EXCLUDED.ev,
                    ev_ebitda = EXCLUDED.ev_ebitda,
                    dividend_yield = EXCLUDED.dividend_yield,
                    dividend_per_share = EXCLUDED.dividend_per_share,
                    data_source = EXCLUDED.data_source
            """, (
                fund_data['ticker'],
                fund_data['region'],
                fund_data['date'],
                fund_data['period_type'],
                fund_data.get('shares_outstanding'),
                fund_data.get('market_cap'),
                fund_data.get('close_price'),
                fund_data.get('per'),
                fund_data.get('pbr'),
                fund_data.get('psr'),
                fund_data.get('pcr'),
                fund_data.get('ev'),
                fund_data.get('ev_ebitda'),
                fund_data.get('dividend_yield'),
                fund_data.get('dividend_per_share'),
                datetime.now(),
                fund_data.get('data_source')
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert fundamentals for {fund_data.get('ticker')}: {e}")
            return False

    def get_fundamentals(self, ticker: str, region: str, period_type: str = 'DAILY') -> List[Dict]:
        """
        Get fundamentals data

        Args:
            ticker: Ticker symbol
            region: Region code
            period_type: Period type (DAILY, QUARTERLY, ANNUAL)

        Returns:
            List of fundamentals sorted by date descending
        """
        return self._execute_query("""
            SELECT * FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND period_type = %s
            ORDER BY date DESC
        """, (ticker, region, period_type), fetch_all=True)

    def get_latest_fundamentals(self, ticker: str, region: str, period_type: str = 'DAILY') -> Optional[Dict]:
        """
        Get latest fundamentals data

        Args:
            ticker: Ticker symbol
            region: Region code
            period_type: Period type

        Returns:
            Latest fundamentals dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM ticker_fundamentals
            WHERE ticker = %s AND region = %s AND period_type = %s
            ORDER BY date DESC
            LIMIT 1
        """, (ticker, region, period_type), fetch_one=True)

    def get_stocks_by_per(self, max_per: float, region: str = None, min_market_cap: int = None) -> List[Dict]:
        """
        Get stocks with P/E ratio below threshold

        Args:
            max_per: Maximum P/E ratio
            region: Region filter (optional)
            min_market_cap: Minimum market cap filter (optional)

        Returns:
            List of stocks sorted by P/E ratio
        """
        query = """
            SELECT t.*, tf.per, tf.market_cap, tf.date
            FROM tickers t
            JOIN ticker_fundamentals tf ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE tf.per <= %s AND tf.per > 0
              AND tf.period_type = 'DAILY'
              AND tf.date = (
                  SELECT MAX(date) FROM ticker_fundamentals
                  WHERE ticker = t.ticker AND region = t.region AND period_type = 'DAILY'
              )
        """
        params = [max_per]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        if min_market_cap:
            query += " AND tf.market_cap >= %s"
            params.append(min_market_cap)

        query += " ORDER BY tf.per ASC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_stocks_by_pbr(self, max_pbr: float, region: str = None) -> List[Dict]:
        """
        Get stocks with P/B ratio below threshold

        Args:
            max_pbr: Maximum P/B ratio
            region: Region filter (optional)

        Returns:
            List of stocks sorted by P/B ratio
        """
        query = """
            SELECT t.*, tf.pbr, tf.market_cap, tf.date
            FROM tickers t
            JOIN ticker_fundamentals tf ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE tf.pbr <= %s AND tf.pbr > 0
              AND tf.period_type = 'DAILY'
              AND tf.date = (
                  SELECT MAX(date) FROM ticker_fundamentals
                  WHERE ticker = t.ticker AND region = t.region AND period_type = 'DAILY'
              )
        """
        params = [max_pbr]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY tf.pbr ASC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def get_dividend_stocks(self, min_yield: float, region: str = None) -> List[Dict]:
        """
        Get dividend stocks with yield above threshold

        Args:
            min_yield: Minimum dividend yield (%)
            region: Region filter (optional)

        Returns:
            List of dividend stocks sorted by yield descending
        """
        query = """
            SELECT t.*, tf.dividend_yield, tf.dividend_per_share, tf.date
            FROM tickers t
            JOIN ticker_fundamentals tf ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE tf.dividend_yield >= %s
              AND tf.period_type = 'DAILY'
              AND tf.date = (
                  SELECT MAX(date) FROM ticker_fundamentals
                  WHERE ticker = t.ticker AND region = t.region AND period_type = 'DAILY'
              )
        """
        params = [min_yield]

        if region:
            query += " AND t.region = %s"
            params.append(region)

        query += " ORDER BY tf.dividend_yield DESC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def update_fundamentals(self, ticker: str, region: str, date_str: str,
                           period_type: str, update_data: Dict) -> bool:
        """
        Update fundamentals fields

        Args:
            ticker: Ticker symbol
            region: Region code
            date_str: Date string
            period_type: Period type
            update_data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            set_clauses = []
            params = []

            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)

            params.extend([ticker, region, date_str, period_type])

            query = f"""
                UPDATE ticker_fundamentals
                SET {', '.join(set_clauses)}
                WHERE ticker = %s AND region = %s AND date = %s AND period_type = %s
            """

            self._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update fundamentals for {ticker}: {e}")
            return False

    def delete_old_fundamentals(self, days_to_keep: int = 365) -> int:
        """
        Delete old fundamentals data (DAILY period only)

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of rows deleted
        """
        try:
            result = self._execute_query("""
                DELETE FROM ticker_fundamentals
                WHERE period_type = 'DAILY'
                  AND date < CURRENT_DATE - INTERVAL '%s days'
            """, (days_to_keep,), commit=True)
            logger.info(f"✅ Deleted {result} old fundamentals records (older than {days_to_keep} days)")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to delete old fundamentals: {e}")
            return 0

    # ========================================
    # Trading & Portfolio Methods
    # ========================================

    def insert_trade(self, trade_data: Dict) -> bool:
        """
        Insert trade record

        Args:
            trade_data: Dictionary with trade information
                Required: ticker, region, side, order_type, quantity, price, amount
                Optional: entry_price, exit_price, fee, tax, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, exit_price, price, amount, fee, tax,
                    order_no, execution_no,
                    entry_timestamp, exit_timestamp, order_time, execution_time,
                    trade_status, sector, position_size_percent, reason,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                trade_data['ticker'],
                trade_data['region'],
                trade_data['side'],
                trade_data['order_type'],
                trade_data['quantity'],
                trade_data.get('entry_price'),
                trade_data.get('exit_price'),
                trade_data['price'],
                trade_data['amount'],
                trade_data.get('fee', 0),
                trade_data.get('tax', 0),
                trade_data.get('order_no'),
                trade_data.get('execution_no'),
                trade_data.get('entry_timestamp'),
                trade_data.get('exit_timestamp'),
                trade_data.get('order_time', datetime.now()),
                trade_data.get('execution_time'),
                trade_data.get('trade_status', 'OPEN'),
                trade_data.get('sector'),
                trade_data.get('position_size_percent'),
                trade_data.get('reason'),
                datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert trade for {trade_data.get('ticker')}: {e}")
            return False

    def get_trades(self, ticker: str = None, region: str = None,
                   trade_status: str = None, limit: int = 100) -> List[Dict]:
        """
        Get trades with optional filters

        Args:
            ticker: Ticker filter (optional)
            region: Region filter (optional)
            trade_status: Status filter (OPEN, CLOSED) (optional)
            limit: Maximum number of trades to return

        Returns:
            List of trades sorted by date descending
        """
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if ticker:
            query += " AND ticker = %s"
            params.append(ticker)

        if region:
            query += " AND region = %s"
            params.append(region)

        if trade_status:
            query += " AND trade_status = %s"
            params.append(trade_status)

        query += f" ORDER BY order_time DESC LIMIT {limit}"

        return self._execute_query(query, tuple(params) if params else None, fetch_all=True)

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict]:
        """
        Get trade by ID

        Args:
            trade_id: Trade ID

        Returns:
            Trade dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM trades WHERE id = %s
        """, (trade_id,), fetch_one=True)

    def get_open_positions(self, region: str = None) -> List[Dict]:
        """
        Get open positions (trades with status OPEN)

        Args:
            region: Region filter (optional)

        Returns:
            List of open trades
        """
        query = """
            SELECT * FROM trades
            WHERE trade_status = 'OPEN'
        """
        params = []

        if region:
            query += " AND region = %s"
            params.append(region)

        query += " ORDER BY entry_timestamp DESC"

        return self._execute_query(query, tuple(params) if params else None, fetch_all=True)

    def get_closed_positions(self, region: str = None, days: int = 30) -> List[Dict]:
        """
        Get recently closed positions

        Args:
            region: Region filter (optional)
            days: Number of days to look back

        Returns:
            List of closed trades
        """
        query = """
            SELECT * FROM trades
            WHERE trade_status = 'CLOSED'
              AND exit_timestamp >= CURRENT_DATE - INTERVAL '%s days'
        """
        params = [days]

        if region:
            query += " AND region = %s"
            params.append(region)

        query += " ORDER BY exit_timestamp DESC"

        return self._execute_query(query, tuple(params), fetch_all=True)

    def update_trade_status(self, trade_id: int, status: str, exit_price: float = None,
                           exit_timestamp: str = None) -> bool:
        """
        Update trade status (OPEN → CLOSED)

        Args:
            trade_id: Trade ID
            status: New status (CLOSED)
            exit_price: Exit price (optional)
            exit_timestamp: Exit timestamp (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            if exit_price and exit_timestamp:
                self._execute_query("""
                    UPDATE trades
                    SET trade_status = %s, exit_price = %s, exit_timestamp = %s
                    WHERE id = %s
                """, (status, exit_price, exit_timestamp, trade_id), commit=True)
            else:
                self._execute_query("""
                    UPDATE trades
                    SET trade_status = %s
                    WHERE id = %s
                """, (status, trade_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update trade status for ID {trade_id}: {e}")
            return False

    def get_portfolio(self, region: str = None) -> List[Dict]:
        """
        Get current portfolio positions

        Args:
            region: Region filter (optional)

        Returns:
            List of portfolio positions
        """
        query = "SELECT * FROM portfolio WHERE 1=1"
        params = []

        if region:
            query += " AND region = %s"
            params.append(region)

        query += " ORDER BY market_value DESC"

        return self._execute_query(query, tuple(params) if params else None, fetch_all=True)

    def update_portfolio_position(self, ticker: str, region: str, update_data: Dict) -> bool:
        """
        Update portfolio position

        Args:
            ticker: Ticker symbol
            region: Region code
            update_data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            set_clauses = []
            params = []

            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)

            params.extend([datetime.now(), ticker, region])

            query = f"""
                UPDATE portfolio
                SET {', '.join(set_clauses)}, last_updated = %s
                WHERE ticker = %s AND region = %s
            """

            self._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update portfolio position for {ticker}: {e}")
            return False

    def get_portfolio_value(self, region: str = None) -> float:
        """
        Calculate total portfolio value

        Args:
            region: Region filter (optional)

        Returns:
            Total portfolio market value
        """
        query = "SELECT COALESCE(SUM(market_value), 0) as total FROM portfolio WHERE 1=1"
        params = []

        if region:
            query += " AND region = %s"
            params.append(region)

        result = self._execute_query(query, tuple(params) if params else None, fetch_one=True)
        return float(result['total']) if result else 0.0

    def get_portfolio_pnl(self, region: str = None) -> Dict:
        """
        Calculate portfolio P&L (Profit and Loss)

        Args:
            region: Region filter (optional)

        Returns:
            Dictionary with total_pnl, total_pnl_pct
        """
        query = """
            SELECT
                COALESCE(SUM(unrealized_pnl), 0) as total_pnl,
                COALESCE(AVG(unrealized_pnl_pct), 0) as avg_pnl_pct
            FROM portfolio
            WHERE 1=1
        """
        params = []

        if region:
            query += " AND region = %s"
            params.append(region)

        result = self._execute_query(query, tuple(params) if params else None, fetch_one=True)
        return {
            'total_pnl': float(result['total_pnl']) if result else 0.0,
            'avg_pnl_pct': float(result['avg_pnl_pct']) if result else 0.0
        }

    def calculate_position_size(self, ticker: str, region: str, price: float,
                                portfolio_value: float, risk_percent: float) -> int:
        """
        Calculate position size (number of shares) based on risk percentage

        Args:
            ticker: Ticker symbol
            region: Region code
            price: Current price
            portfolio_value: Total portfolio value
            risk_percent: Risk percentage (e.g., 2.0 for 2%)

        Returns:
            Recommended number of shares
        """
        # Get lot size
        ticker_info = self.get_ticker(ticker, region)
        lot_size = ticker_info['lot_size'] if ticker_info else 1

        # Calculate position size
        risk_amount = portfolio_value * (risk_percent / 100)
        shares = int(risk_amount / price)

        # Round to lot size
        shares = (shares // lot_size) * lot_size

        return shares

    def delete_trade(self, trade_id: int) -> bool:
        """
        Delete trade record

        Args:
            trade_id: Trade ID

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                DELETE FROM trades WHERE id = %s
            """, (trade_id,), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete trade ID {trade_id}: {e}")
            return False

    # ========================================
    # Market Data Methods
    # ========================================

    def insert_market_sentiment(self, sentiment_data: Dict) -> bool:
        """
        Insert market sentiment data

        Args:
            sentiment_data: Dictionary with sentiment information
                Required: date
                Optional: vix, fear_greed_index, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO market_sentiment (
                    date, vix, fear_greed_index, kospi_index, kosdaq_index,
                    foreign_net_buying, institution_net_buying,
                    usd_krw, jpy_krw, oil_price, gold_price,
                    market_regime, sentiment_score, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date) DO UPDATE SET
                    vix = EXCLUDED.vix,
                    fear_greed_index = EXCLUDED.fear_greed_index,
                    kospi_index = EXCLUDED.kospi_index,
                    kosdaq_index = EXCLUDED.kosdaq_index,
                    foreign_net_buying = EXCLUDED.foreign_net_buying,
                    institution_net_buying = EXCLUDED.institution_net_buying,
                    usd_krw = EXCLUDED.usd_krw,
                    jpy_krw = EXCLUDED.jpy_krw,
                    oil_price = EXCLUDED.oil_price,
                    gold_price = EXCLUDED.gold_price,
                    market_regime = EXCLUDED.market_regime,
                    sentiment_score = EXCLUDED.sentiment_score
            """, (
                sentiment_data['date'],
                sentiment_data.get('vix'),
                sentiment_data.get('fear_greed_index'),
                sentiment_data.get('kospi_index'),
                sentiment_data.get('kosdaq_index'),
                sentiment_data.get('foreign_net_buying'),
                sentiment_data.get('institution_net_buying'),
                sentiment_data.get('usd_krw'),
                sentiment_data.get('jpy_krw'),
                sentiment_data.get('oil_price'),
                sentiment_data.get('gold_price'),
                sentiment_data.get('market_regime'),
                sentiment_data.get('sentiment_score'),
                datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert market sentiment: {e}")
            return False

    def get_latest_market_sentiment(self) -> Optional[Dict]:
        """
        Get latest market sentiment data

        Returns:
            Latest market sentiment dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM market_sentiment
            ORDER BY date DESC
            LIMIT 1
        """, fetch_one=True)

    def insert_global_index(self, index_data: Dict) -> bool:
        """
        Insert global market index data

        Args:
            index_data: Dictionary with index information
                Required: date, symbol, index_name, region, close_price, change_percent
                Optional: open_price, high_price, low_price, volume, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO global_market_indices (
                    date, symbol, index_name, region,
                    close_price, open_price, high_price, low_price, volume,
                    change_percent, trend_5d, consecutive_days, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date, symbol) DO UPDATE SET
                    close_price = EXCLUDED.close_price,
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    volume = EXCLUDED.volume,
                    change_percent = EXCLUDED.change_percent,
                    trend_5d = EXCLUDED.trend_5d,
                    consecutive_days = EXCLUDED.consecutive_days
            """, (
                index_data['date'],
                index_data['symbol'],
                index_data['index_name'],
                index_data['region'],
                index_data['close_price'],
                index_data.get('open_price'),
                index_data.get('high_price'),
                index_data.get('low_price'),
                index_data.get('volume'),
                index_data['change_percent'],
                index_data.get('trend_5d'),
                index_data.get('consecutive_days'),
                datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert global index: {e}")
            return False

    def get_global_indices(self, date_str: str = None, symbol: str = None) -> List[Dict]:
        """
        Get global market indices data

        Args:
            date_str: Date filter (optional, defaults to latest)
            symbol: Symbol filter (optional)

        Returns:
            List of global indices
        """
        if date_str:
            if symbol:
                query = """
                    SELECT * FROM global_market_indices
                    WHERE date = %s AND symbol = %s
                    ORDER BY symbol
                """
                params = (date_str, symbol)
            else:
                query = """
                    SELECT * FROM global_market_indices
                    WHERE date = %s
                    ORDER BY symbol
                """
                params = (date_str,)
        else:
            if symbol:
                query = """
                    SELECT * FROM global_market_indices
                    WHERE symbol = %s
                    ORDER BY date DESC
                    LIMIT 30
                """
                params = (symbol,)
            else:
                query = """
                    SELECT * FROM global_market_indices
                    WHERE date = (SELECT MAX(date) FROM global_market_indices)
                    ORDER BY symbol
                """
                params = None

        return self._execute_query(query, params, fetch_all=True)

    def insert_exchange_rate(self, rate_data: Dict) -> bool:
        """
        Insert exchange rate data

        Args:
            rate_data: Dictionary with exchange rate information
                Required: currency, rate, rate_date
                Optional: timestamp, source

        Returns:
            True if successful, False otherwise
        """
        try:
            self._execute_query("""
                INSERT INTO exchange_rate_history (
                    currency, rate, timestamp, rate_date, source, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                rate_data['currency'],
                rate_data['rate'],
                rate_data.get('timestamp', datetime.now()),
                rate_data['rate_date'],
                rate_data.get('source'),
                datetime.now()
            ), commit=True)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to insert exchange rate: {e}")
            return False

    def get_latest_exchange_rate(self, currency: str) -> Optional[Dict]:
        """
        Get latest exchange rate

        Args:
            currency: Currency pair (e.g., USD_KRW, HKD_KRW)

        Returns:
            Latest exchange rate dictionary or None
        """
        return self._execute_query("""
            SELECT * FROM exchange_rate_history
            WHERE currency = %s
            ORDER BY rate_date DESC, timestamp DESC
            LIMIT 1
        """, (currency,), fetch_one=True)

    # ========================================
    # Utility Methods
    # ========================================

    def bulk_insert_generic(self, table_name: str, df: pd.DataFrame,
                            columns: List[str]) -> int:
        """
        Generic bulk insert using PostgreSQL COPY command

        Args:
            table_name: Target table name
            df: DataFrame with data
            columns: List of column names in order

        Returns:
            Number of rows inserted
        """
        if df.empty:
            return 0

        # Prepare DataFrame
        insert_df = df[columns].copy()

        # Convert to CSV in-memory
        buffer = StringIO()
        insert_df.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
        buffer.seek(0)

        # Execute COPY command
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.copy_expert(
                    f"""
                    COPY {table_name} ({', '.join(columns)})
                    FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')
                    """,
                    buffer
                )
                conn.commit()
                logger.info(f"✅ Bulk inserted {len(insert_df)} rows into {table_name}")
                return len(insert_df)
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Bulk insert failed for {table_name}: {e}")
                raise
            finally:
                cursor.close()

    def test_connection(self) -> bool:
        """
        Test PostgreSQL connection

        Returns:
            True if connection successful, False otherwise
        """
        try:
            result = self._execute_query("SELECT version()", fetch_one=True)
            if result:
                logger.info(f"✅ PostgreSQL connection test successful")
                logger.info(f"   Version: {result['version'][:50]}...")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection test failed: {e}")
            return False


# ========================================
# Module-level functions for backward compatibility
# ========================================

def create_database_manager(**kwargs) -> PostgresDatabaseManager:
    """
    Create PostgreSQL database manager instance

    Args:
        **kwargs: Arguments for PostgresDatabaseManager

    Returns:
        PostgresDatabaseManager instance
    """
    return PostgresDatabaseManager(**kwargs)


if __name__ == '__main__':
    # Quick test
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    try:
        # Create database manager
        db_manager = PostgresDatabaseManager()

        # Test connection
        db_manager.test_connection()

        # Test ticker operations
        logger.info("\n=== Testing Ticker Operations ===")

        # Insert test ticker
        ticker_data = {
            'ticker': '005930',
            'name': 'Samsung Electronics',
            'name_eng': 'Samsung Electronics Co., Ltd.',
            'exchange': 'KOSPI',
            'region': 'KR',
            'currency': 'KRW',
            'asset_type': 'STOCK',
            'is_active': True,
            'data_source': 'Test Script'
        }
        result = db_manager.insert_ticker(ticker_data)
        logger.info(f"Insert ticker result: {result}")

        # Get ticker
        ticker = db_manager.get_ticker('005930', 'KR')
        logger.info(f"Get ticker result: {ticker['name'] if ticker else 'Not found'}")

        # Get tickers list
        tickers = db_manager.get_tickers('KR', asset_type='STOCK')
        logger.info(f"Get tickers count: {len(tickers)}")

        # Count tickers
        count = db_manager.count_tickers('KR')
        logger.info(f"Total KR tickers: {count}")

        # Test OHLCV operations
        logger.info("\n=== Testing OHLCV Operations ===")

        # Create sample OHLCV data
        dates = pd.date_range('2024-01-01', periods=10)
        ohlcv_df = pd.DataFrame({
            'date': dates,
            'open': 70000,
            'high': 71000,
            'low': 69000,
            'close': 70500,
            'volume': 10000000
        })

        # Bulk insert
        count = db_manager.insert_ohlcv_bulk('005930', ohlcv_df, timeframe='D', region='KR')
        logger.info(f"Bulk insert OHLCV count: {count}")

        # Get OHLCV data
        result_df = db_manager.get_ohlcv_data('005930', timeframe='D', region='KR')
        logger.info(f"Get OHLCV data count: {len(result_df)}")

        # Get latest OHLCV
        latest = db_manager.get_latest_ohlcv('005930', region='KR')
        logger.info(f"Latest OHLCV date: {latest['date'] if latest else 'Not found'}")

        logger.info("\n✅ All tests passed!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
    finally:
        if 'db_manager' in locals():
            db_manager.close_pool()
