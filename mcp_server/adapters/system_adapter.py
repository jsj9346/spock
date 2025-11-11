# mcp_server/adapters/system_adapter.py
"""
SystemAdapter - MCP adapter for system information and health checks.

Provides lightweight access to system metadata, ticker listings, and database
health status.

Architecture Pattern (Direct Database Queries):
    MCP Tool -> SystemAdapter -> PostgreSQL queries

This adapter:
    - Lists available tickers with filtering
    - Provides system health status
    - Checks data freshness
    - Reports database statistics

Performance:
    - list_tickers: <1s
    - get_status: <500ms
    - Cached for 60 seconds

Author: Spock MCP Server
Date: 2025-10-30
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from mcp_server.config import Config
from mcp_server.utils.errors import (
    DatabaseError,
    SpockMCPError,
)
from modules.db_manager_postgres import PostgresDatabaseManager


class SystemAdapter:
    """
    MCP adapter for system information and health checks.

    Provides simple, fast queries for system metadata without heavy
    data processing overhead.

    Example:
        >>> adapter = SystemAdapter()
        >>> tickers = await adapter.list_available_tickers(region="KR")
        >>> status = await adapter.get_system_status()
    """

    def __init__(self, config: Optional[Config] = None):
        """
        Initialize SystemAdapter.

        Args:
            config: Optional MCP config (default: load from env)
        """
        self.config = config or Config.from_env()

        # Initialize database manager with small pool (MCP server doesn't need large pool)
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        # Cache for system info (60 second TTL)
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 60  # seconds

        logger.info("system_adapter_initialized")

    async def list_available_tickers(
        self,
        region: Optional[str] = None,
        ticker_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        List available tickers in database.

        Args:
            region: Filter by region (KR, US, etc.)
            ticker_type: Filter by type (stock, etf, etc.)
            limit: Maximum number of results

        Returns:
            Dictionary with ticker list and metadata

        Raises:
            DatabaseError: Database query failure
        """
        try:
            # Check cache
            cache_key = f"tickers:{region}:{ticker_type}:{limit}"
            if self._is_cache_valid(cache_key):
                logger.debug("cache_hit", key=cache_key)
                return self._cache[cache_key]

            logger.info("list_tickers_start",
                       region=region,
                       ticker_type=ticker_type,
                       limit=limit)

            # Build query
            query = "SELECT ticker, region, name, asset_type FROM tickers WHERE 1=1"
            params = []

            if region:
                query += " AND region = %s"
                params.append(region)

            if ticker_type:
                query += " AND ticker_type = %s"
                params.append(ticker_type)

            query += " ORDER BY ticker"

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            # Execute query
            with self.db_manager._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    tickers = [
                        {
                            "ticker": row[0],
                            "region": row[1],
                            "name": row[2],
                            "asset_type": row[3],
                        }
                        for row in rows
                    ]

            result = {
                "success": True,
                "tickers": tickers,
                "count": len(tickers),
                "filters": {
                    "region": region,
                    "ticker_type": ticker_type,
                    "limit": limit,
                },
            }

            # Update cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info("list_tickers_complete", count=len(tickers))

            return result

        except Exception as e:
            logger.error("list_tickers_error", error=str(e))
            raise DatabaseError(
                f"Failed to list tickers: {str(e)}",
                {"region": region, "ticker_type": ticker_type}
            )

    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get system health status and statistics.

        Returns:
            Dictionary with system status information

        Raises:
            DatabaseError: Database query failure
        """
        try:
            # Check cache
            cache_key = "system_status"
            if self._is_cache_valid(cache_key):
                logger.debug("cache_hit", key=cache_key)
                return self._cache[cache_key]

            logger.info("get_system_status_start")

            with self.db_manager._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Database version
                    cursor.execute("SELECT version()")
                    db_version = cursor.fetchone()[0]

                    # Ticker counts by region
                    cursor.execute("""
                        SELECT region, COUNT(*)
                        FROM tickers
                        GROUP BY region
                        ORDER BY region
                    """)
                    ticker_counts = {row[0]: row[1] for row in cursor.fetchall()}

                    # OHLCV record count
                    cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
                    ohlcv_count = cursor.fetchone()[0]

                    # Most recent data date
                    cursor.execute("""
                        SELECT MAX(date) FROM ohlcv_data
                    """)
                    latest_date_result = cursor.fetchone()
                    latest_date = latest_date_result[0] if latest_date_result[0] else None

                    # Database size
                    cursor.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database()))
                    """)
                    db_size = cursor.fetchone()[0]

            # Calculate data freshness
            data_fresh = False
            days_since_update = None
            if latest_date:
                days_since_update = (datetime.now().date() - latest_date).days
                data_fresh = days_since_update <= 3  # Fresh if updated within 3 days

            result = {
                "success": True,
                "status": "healthy" if data_fresh else "stale_data",
                "database": {
                    "version": db_version,
                    "size": db_size,
                    "connected": True,
                },
                "data": {
                    "ticker_counts": ticker_counts,
                    "total_tickers": sum(ticker_counts.values()),
                    "ohlcv_records": ohlcv_count,
                    "latest_date": latest_date.isoformat() if latest_date else None,
                    "days_since_update": days_since_update,
                    "data_fresh": data_fresh,
                },
                "timestamp": datetime.now().isoformat(),
            }

            # Update cache
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info("get_system_status_complete",
                       status=result["status"],
                       total_tickers=result["data"]["total_tickers"])

            return result

        except Exception as e:
            logger.error("get_system_status_error", error=str(e))
            raise DatabaseError(
                f"Failed to get system status: {str(e)}",
                {}
            )

    def _is_cache_valid(self, key: str) -> bool:
        """
        Check if cached result is still valid.

        Args:
            key: Cache key

        Returns:
            True if cache is valid
        """
        if key not in self._cache or key not in self._cache_time:
            return False

        age = (datetime.now() - self._cache_time[key]).total_seconds()
        return age < self._cache_ttl
