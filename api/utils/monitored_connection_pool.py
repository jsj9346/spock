"""
Monitored Database Connection Pool

Wrapper around psycopg2.pool.SimpleConnectionPool with Prometheus metrics collection.
Tracks connection pool status, wait times, and usage patterns.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 1.0.0
"""

import time
import threading
from typing import Optional

import psycopg2
from psycopg2 import pool
from prometheus_client import Gauge, Histogram, Counter
from loguru import logger


# Prometheus Metrics Definitions
# ================================

# Connection Pool Status Gauges
DB_CONNECTIONS_ACTIVE = Gauge(
    'db_connections_active',
    'Number of active database connections',
    ['database']
)

DB_CONNECTIONS_IDLE = Gauge(
    'db_connections_idle',
    'Number of idle database connections',
    ['database']
)

DB_CONNECTIONS_TOTAL = Gauge(
    'db_connections_total',
    'Total number of database connections in pool',
    ['database']
)

DB_POOL_UTILIZATION = Gauge(
    'db_pool_utilization_percent',
    'Database connection pool utilization percentage',
    ['database']
)

# Connection Wait Time Histogram
DB_CONNECTION_WAIT_TIME = Histogram(
    'db_connection_wait_seconds',
    'Time spent waiting for database connection',
    ['database'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Connection Events Counters
DB_CONNECTIONS_ACQUIRED = Counter(
    'db_connections_acquired_total',
    'Total number of database connections acquired',
    ['database']
)

DB_CONNECTIONS_RELEASED = Counter(
    'db_connections_released_total',
    'Total number of database connections released',
    ['database']
)

DB_CONNECTION_ERRORS = Counter(
    'db_connection_errors_total',
    'Total number of database connection errors',
    ['database', 'error_type']
)

DB_POOL_EXHAUSTED = Counter(
    'db_pool_exhausted_total',
    'Number of times connection pool was exhausted',
    ['database']
)


class MonitoredConnectionPool:
    """
    Prometheus-instrumented database connection pool.

    Wraps psycopg2.pool.SimpleConnectionPool to collect metrics:
    - Connection pool status (active, idle, utilization)
    - Connection wait time
    - Connection acquisition/release events
    - Pool exhaustion and error tracking

    Thread-safe implementation for concurrent FastAPI requests.

    Usage:
        pool = MonitoredConnectionPool(
            minconn=1,
            maxconn=10,
            host='localhost',
            database='quant_platform'
        )

        # Acquire connection
        conn = pool.getconn()

        # Use connection
        cursor = conn.cursor()
        cursor.execute("SELECT 1")

        # Release connection
        pool.putconn(conn)
    """

    def __init__(
        self,
        minconn: int,
        maxconn: int,
        database: str = 'unknown',
        **kwargs
    ):
        """
        Initialize monitored connection pool.

        Args:
            minconn: Minimum number of connections
            maxconn: Maximum number of connections
            database: Database name (for metrics labels AND psycopg2 connection)
            **kwargs: Additional psycopg2 connection parameters
        """
        # Store database name for metrics labels
        self.database = database

        # Add database to kwargs if not already present
        if 'database' not in kwargs:
            kwargs['database'] = database

        # Create underlying connection pool
        self._pool = psycopg2.pool.SimpleConnectionPool(
            minconn, maxconn, **kwargs
        )

        # Pool configuration
        self.min_connections = minconn
        self.max_connections = maxconn

        # Connection tracking (thread-safe)
        self._lock = threading.Lock()
        self._active_connections = 0

        # Initialize metrics
        self._update_metrics()

        logger.info(
            f"Monitored connection pool initialized: "
            f"database={database}, min={minconn}, max={maxconn}"
        )

    def getconn(self, key: Optional[str] = None) -> psycopg2.extensions.connection:
        """
        Acquire a connection from the pool.

        Tracks wait time and updates connection metrics.

        Args:
            key: Optional connection key (for pool keyed connections)

        Returns:
            PostgreSQL connection object

        Raises:
            pool.PoolError: If pool is exhausted
            psycopg2.Error: If connection fails
        """
        start_time = time.time()

        try:
            # Acquire connection from pool
            conn = self._pool.getconn(key)

            # Record wait time
            wait_time = time.time() - start_time
            DB_CONNECTION_WAIT_TIME.labels(database=self.database).observe(wait_time)

            # Update connection count
            with self._lock:
                self._active_connections += 1

            # Record acquisition
            DB_CONNECTIONS_ACQUIRED.labels(database=self.database).inc()

            # Update metrics
            self._update_metrics()

            logger.debug(
                f"Connection acquired: database={self.database}, "
                f"wait_time={wait_time:.4f}s, active={self._active_connections}"
            )

            return conn

        except pool.PoolError as e:
            # Pool exhausted
            DB_POOL_EXHAUSTED.labels(database=self.database).inc()
            DB_CONNECTION_ERRORS.labels(
                database=self.database,
                error_type='PoolExhausted'
            ).inc()

            logger.error(
                f"Connection pool exhausted: database={self.database}, "
                f"max_connections={self.max_connections}"
            )
            raise

        except psycopg2.Error as e:
            # Connection error
            DB_CONNECTION_ERRORS.labels(
                database=self.database,
                error_type=type(e).__name__
            ).inc()

            logger.error(f"Connection error: database={self.database}, error={e}")
            raise

        except Exception as e:
            # Unexpected error
            DB_CONNECTION_ERRORS.labels(
                database=self.database,
                error_type='UnexpectedError'
            ).inc()

            logger.error(
                f"Unexpected connection error: database={self.database}, error={e}",
                exc_info=True
            )
            raise

    def putconn(
        self,
        conn: psycopg2.extensions.connection,
        key: Optional[str] = None,
        close: bool = False
    ):
        """
        Release a connection back to the pool.

        Updates connection metrics after release.

        Args:
            conn: PostgreSQL connection object
            key: Optional connection key (for pool keyed connections)
            close: If True, close connection instead of returning to pool
        """
        try:
            # Return connection to pool
            self._pool.putconn(conn, key, close)

            # Update connection count
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)

            # Record release
            DB_CONNECTIONS_RELEASED.labels(database=self.database).inc()

            # Update metrics
            self._update_metrics()

            logger.debug(
                f"Connection released: database={self.database}, "
                f"active={self._active_connections}, closed={close}"
            )

        except Exception as e:
            logger.error(
                f"Error releasing connection: database={self.database}, error={e}",
                exc_info=True
            )

    def closeall(self):
        """
        Close all connections in the pool.

        Called during application shutdown.
        """
        try:
            self._pool.closeall()

            # Reset connection count
            with self._lock:
                self._active_connections = 0

            # Update metrics to zero
            self._update_metrics()

            logger.info(f"All connections closed: database={self.database}")

        except Exception as e:
            logger.error(
                f"Error closing connections: database={self.database}, error={e}",
                exc_info=True
            )

    def _update_metrics(self):
        """
        Update Prometheus metrics with current pool status.

        Thread-safe metric updates.
        """
        with self._lock:
            active = self._active_connections
            idle = self.max_connections - active
            total = self.max_connections
            utilization = (active / self.max_connections) * 100 if self.max_connections > 0 else 0

        # Update gauges
        DB_CONNECTIONS_ACTIVE.labels(database=self.database).set(active)
        DB_CONNECTIONS_IDLE.labels(database=self.database).set(idle)
        DB_CONNECTIONS_TOTAL.labels(database=self.database).set(total)
        DB_POOL_UTILIZATION.labels(database=self.database).set(utilization)

    def get_pool_status(self) -> dict:
        """
        Get current pool status (for debugging).

        Returns:
            Dictionary with pool status information
        """
        with self._lock:
            return {
                'database': self.database,
                'active_connections': self._active_connections,
                'idle_connections': self.max_connections - self._active_connections,
                'total_connections': self.max_connections,
                'min_connections': self.min_connections,
                'utilization_percent': (self._active_connections / self.max_connections) * 100
            }
