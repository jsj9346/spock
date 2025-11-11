"""
Database connection manager for Quant Platform CLI.

Provides async PostgreSQL connection pooling with singleton pattern
for efficient database access across CLI commands.
"""

import asyncpg
from typing import Optional, Dict, Any, List
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseManager:
    """
    Singleton database connection manager with asyncpg pooling.

    Features:
    - Connection pooling (min=2, max=10 connections)
    - Async/await support for non-blocking operations
    - Automatic connection lifecycle management
    - Error handling with graceful degradation

    Usage:
        db = DatabaseManager()
        await db.connect()
        result = await db.fetch("SELECT * FROM tickers LIMIT 10")
        await db.disconnect()
    """

    _instance: Optional['DatabaseManager'] = None
    _pool: Optional[asyncpg.Pool] = None

    def __new__(cls):
        """Singleton pattern: ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize connection pool to PostgreSQL database.

        Args:
            config: Optional database configuration override.
                   Defaults to environment variables or local settings.

        Raises:
            ConnectionError: If unable to connect to database.
        """
        if self._pool is not None:
            # Already connected
            return

        # Default configuration
        default_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'database': os.getenv('POSTGRES_DB', 'quant_platform'),
            'user': os.getenv('POSTGRES_USER', '13ruce'),
            'password': os.getenv('POSTGRES_PASSWORD', ''),
            'min_size': 2,
            'max_size': 10,
            'command_timeout': 60,
        }

        # Merge with provided config
        if config:
            default_config.update(config)

        try:
            self._pool = await asyncpg.create_pool(**default_config)

            # Test connection
            async with self._pool.acquire() as conn:
                await conn.fetchval('SELECT 1')

        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    async def disconnect(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args, timeout: float = 10.0) -> List[asyncpg.Record]:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query string (use $1, $2 for parameters)
            *args: Query parameters
            timeout: Query timeout in seconds (default: 10s)

        Returns:
            List of Record objects

        Raises:
            RuntimeError: If not connected to database
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args, timeout: float = 10.0) -> Any:
        """
        Execute query and fetch single value (first column of first row).

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Single value or None
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)

    async def fetchrow(self, query: str, *args, timeout: float = 10.0) -> Optional[asyncpg.Record]:
        """
        Execute query and fetch single row.

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Single Record or None
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def execute(self, query: str, *args, timeout: float = 10.0) -> str:
        """
        Execute query without returning results (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Status string (e.g., "INSERT 0 1")
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def executemany(self, query: str, args_list: List[tuple], timeout: float = 30.0) -> None:
        """
        Execute query multiple times with different parameters (batch insert).

        Args:
            query: SQL query string
            args_list: List of parameter tuples
            timeout: Query timeout in seconds
        """
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")

        async with self._pool.acquire() as conn:
            await conn.executemany(query, args_list, timeout=timeout)

    def is_connected(self) -> bool:
        """Check if database connection pool is active."""
        return self._pool is not None

    async def get_pool_stats(self) -> Dict[str, int]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool metrics (size, free, used)
        """
        if not self._pool:
            return {'size': 0, 'free': 0, 'used': 0}

        return {
            'size': self._pool.get_size(),
            'free': self._pool.get_idle_size(),
            'used': self._pool.get_size() - self._pool.get_idle_size(),
        }

    async def __aenter__(self):
        """Context manager entry: ensure connection."""
        if not self._pool:
            await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: optionally disconnect."""
        # Keep connection alive for reuse across commands
        # Only disconnect when explicitly called
        pass


# Convenience singleton instance
db = DatabaseManager()
