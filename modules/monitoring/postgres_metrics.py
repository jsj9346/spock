"""
PostgreSQL Prometheus Metrics Collector

Collects and exports PostgreSQL database metrics for Prometheus monitoring.

Metrics Categories:
- Database Size & Growth
- Query Performance
- Connection Pool Status
- Table Statistics
- Index Usage
- Replication Lag
- Data Quality Metrics
- TimescaleDB Metrics

Usage:
    from modules.monitoring import PostgresMetricsCollector

    collector = PostgresMetricsCollector(postgres_db)
    collector.start_metrics_server(port=8000)
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import threading

from prometheus_client import (
    Gauge, Counter, Histogram, Summary, Info,
    start_http_server, REGISTRY
)
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager


class PostgresMetricsCollector:
    """
    Collects PostgreSQL metrics and exports them for Prometheus.

    Monitors:
    - Database size and growth rate
    - Query performance and slow queries
    - Connection pool utilization
    - Table row counts and sizes
    - Index hit rates
    - Data freshness and quality
    - TimescaleDB hypertable statistics
    """

    def __init__(self,
                 postgres_manager: PostgresDatabaseManager,
                 collection_interval: int = 60):
        """
        Initialize metrics collector.

        Args:
            postgres_manager: PostgreSQL database manager
            collection_interval: Seconds between metric collections (default: 60)
        """
        self.db = postgres_manager
        self.collection_interval = collection_interval
        self._running = False
        self._collection_thread = None

        # Initialize Prometheus metrics
        self._init_metrics()

        logger.info("PostgresMetricsCollector initialized")

    def _init_metrics(self):
        """Initialize all Prometheus metrics."""

        # ===================================================================
        # Database Size Metrics
        # ===================================================================

        self.db_size_bytes = Gauge(
            'postgres_database_size_bytes',
            'Total database size in bytes',
            ['database']
        )

        self.table_size_bytes = Gauge(
            'postgres_table_size_bytes',
            'Table size in bytes',
            ['table']
        )

        self.table_row_count = Gauge(
            'postgres_table_rows',
            'Number of rows in table',
            ['table']
        )

        # ===================================================================
        # Query Performance Metrics
        # ===================================================================

        self.query_duration_seconds = Histogram(
            'postgres_query_duration_seconds',
            'Query execution time in seconds',
            ['query_type'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )

        self.slow_queries_total = Counter(
            'postgres_slow_queries_total',
            'Total number of slow queries (>1s)',
            ['table']
        )

        self.query_errors_total = Counter(
            'postgres_query_errors_total',
            'Total number of query errors',
            ['error_type']
        )

        # ===================================================================
        # Connection Pool Metrics
        # ===================================================================

        self.connection_pool_size = Gauge(
            'postgres_connection_pool_size',
            'Current connection pool size'
        )

        self.connection_pool_available = Gauge(
            'postgres_connection_pool_available',
            'Available connections in pool'
        )

        self.connection_pool_in_use = Gauge(
            'postgres_connection_pool_in_use',
            'Connections currently in use'
        )

        self.active_connections = Gauge(
            'postgres_active_connections',
            'Number of active database connections',
            ['state']
        )

        # ===================================================================
        # Index Usage Metrics
        # ===================================================================

        self.index_hit_rate = Gauge(
            'postgres_index_hit_rate',
            'Index cache hit rate (0-1)',
            ['table']
        )

        self.sequential_scans = Counter(
            'postgres_sequential_scans_total',
            'Total number of sequential scans',
            ['table']
        )

        self.index_scans = Counter(
            'postgres_index_scans_total',
            'Total number of index scans',
            ['table']
        )

        # ===================================================================
        # Data Quality Metrics
        # ===================================================================

        self.data_freshness_seconds = Gauge(
            'postgres_data_freshness_seconds',
            'Age of most recent data in seconds',
            ['region', 'data_type']
        )

        self.missing_dates_count = Gauge(
            'postgres_missing_dates_count',
            'Number of missing trading days detected',
            ['region']
        )

        self.duplicate_records_count = Gauge(
            'postgres_duplicate_records_count',
            'Number of duplicate records detected',
            ['table']
        )

        self.null_value_count = Gauge(
            'postgres_null_values_count',
            'Number of NULL values in critical columns',
            ['table', 'column']
        )

        # ===================================================================
        # TimescaleDB Metrics
        # ===================================================================

        self.hypertable_size_bytes = Gauge(
            'postgres_hypertable_size_bytes',
            'Hypertable size in bytes',
            ['hypertable']
        )

        self.hypertable_chunks = Gauge(
            'postgres_hypertable_chunks',
            'Number of chunks in hypertable',
            ['hypertable']
        )

        self.compression_ratio = Gauge(
            'postgres_compression_ratio',
            'Compression ratio for hypertable',
            ['hypertable']
        )

        self.compressed_chunks = Gauge(
            'postgres_compressed_chunks',
            'Number of compressed chunks',
            ['hypertable']
        )

        # ===================================================================
        # Business Metrics
        # ===================================================================

        self.total_tickers = Gauge(
            'postgres_total_tickers',
            'Total number of tickers',
            ['region', 'is_active']
        )

        self.ohlcv_coverage_days = Gauge(
            'postgres_ohlcv_coverage_days',
            'Number of days of OHLCV data available',
            ['ticker', 'region']
        )

        self.backtest_performance_seconds = Histogram(
            'postgres_backtest_query_seconds',
            'Backtest query performance',
            ['time_range'],
            buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0]
        )

        # ===================================================================
        # System Info
        # ===================================================================

        self.postgres_info = Info(
            'postgres_database',
            'PostgreSQL database information'
        )

        logger.info("Prometheus metrics initialized")

    def collect_database_size_metrics(self):
        """Collect database and table size metrics."""
        try:
            # Total database size
            db_size = self.db.execute_query(
                """
                SELECT pg_database_size(current_database()) AS size
                """
            )
            if db_size:
                self.db_size_bytes.labels(database='quant_platform').set(
                    db_size[0]['size']
                )

            # Table sizes
            table_sizes = self.db.execute_query(
                """
                SELECT
                    schemaname,
                    tablename,
                    pg_total_relation_size(schemaname||'.'||tablename) AS total_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY total_bytes DESC
                """
            )

            for table in table_sizes:
                self.table_size_bytes.labels(
                    table=table['tablename']
                ).set(table['total_bytes'])

            # Table row counts
            tables = ['tickers', 'ohlcv_data', 'technical_analysis',
                     'stock_details', 'etf_details']
            for table in tables:
                try:
                    count = self.db.execute_query(
                        f"SELECT COUNT(*) as count FROM {table}"
                    )
                    if count:
                        self.table_row_count.labels(table=table).set(count[0]['count'])
                except Exception as e:
                    logger.warning(f"Failed to count rows in {table}: {e}")

        except Exception as e:
            logger.error(f"Error collecting database size metrics: {e}")

    def collect_query_performance_metrics(self):
        """Collect query performance statistics."""
        try:
            # Test OHLCV query performance for different time ranges
            test_ranges = [
                ('250_days', 250),
                ('1_year', 365),
                ('10_years', 3650)
            ]

            for range_name, days in test_ranges:
                start = time.perf_counter()
                self.db.execute_query(
                    f"""
                    SELECT date, close
                    FROM ohlcv_data
                    WHERE ticker = '005930'
                      AND region = 'KR'
                      AND date >= CURRENT_DATE - INTERVAL '{days} days'
                    ORDER BY date DESC
                    LIMIT 1000
                    """
                )
                duration = time.perf_counter() - start

                self.query_duration_seconds.labels(
                    query_type=f'ohlcv_{range_name}'
                ).observe(duration)

                self.backtest_performance_seconds.labels(
                    time_range=range_name
                ).observe(duration)

        except Exception as e:
            logger.error(f"Error collecting query performance metrics: {e}")
            self.query_errors_total.labels(error_type='query_execution').inc()

    def collect_connection_metrics(self):
        """Collect connection pool and active connection metrics."""
        try:
            # Connection pool status
            if hasattr(self.db, 'pool'):
                # Get pool statistics (psycopg2 ThreadedConnectionPool)
                pool = self.db.pool
                # Note: ThreadedConnectionPool doesn't expose size directly
                # These are estimates based on configuration
                self.connection_pool_size.set(pool.maxconn if hasattr(pool, 'maxconn') else 0)

            # Active connections
            connections = self.db.execute_query(
                """
                SELECT state, COUNT(*) as count
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY state
                """
            )

            for conn in connections:
                self.active_connections.labels(
                    state=conn['state'] or 'unknown'
                ).set(conn['count'])

        except Exception as e:
            logger.error(f"Error collecting connection metrics: {e}")

    def collect_index_metrics(self):
        """Collect index usage statistics."""
        try:
            # Index hit rate per table
            index_stats = self.db.execute_query(
                """
                SELECT
                    schemaname,
                    tablename,
                    CASE
                        WHEN (idx_scan + seq_scan) > 0
                        THEN idx_scan::float / (idx_scan + seq_scan)
                        ELSE 0
                    END AS index_hit_rate,
                    idx_scan,
                    seq_scan
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                """
            )

            for stat in index_stats:
                self.index_hit_rate.labels(
                    table=stat['tablename']
                ).set(stat['index_hit_rate'])

                self.index_scans.labels(
                    table=stat['tablename']
                ).inc(stat['idx_scan'] or 0)

                self.sequential_scans.labels(
                    table=stat['tablename']
                ).inc(stat['seq_scan'] or 0)

        except Exception as e:
            logger.error(f"Error collecting index metrics: {e}")

    def collect_data_quality_metrics(self):
        """Collect data quality and freshness metrics."""
        try:
            # Data freshness by region
            freshness = self.db.execute_query(
                """
                SELECT
                    region,
                    MAX(date) AS latest_date,
                    EXTRACT(EPOCH FROM (NOW() - MAX(date))) AS age_seconds
                FROM ohlcv_data
                GROUP BY region
                """
            )

            for region_data in freshness:
                self.data_freshness_seconds.labels(
                    region=region_data['region'],
                    data_type='ohlcv'
                ).set(region_data['age_seconds'])

            # Missing dates (gaps > 3 days)
            gaps = self.db.execute_query(
                """
                WITH date_gaps AS (
                    SELECT
                        region,
                        date - LAG(date) OVER (PARTITION BY ticker, region ORDER BY date) AS gap_days
                    FROM ohlcv_data
                )
                SELECT region, COUNT(*) as gap_count
                FROM date_gaps
                WHERE gap_days > 3
                GROUP BY region
                """
            )

            for gap in gaps:
                self.missing_dates_count.labels(
                    region=gap['region']
                ).set(gap['gap_count'])

            # Duplicate records
            duplicates = self.db.execute_query(
                """
                SELECT 'ohlcv_data' as table_name, COUNT(*) as dup_count
                FROM (
                    SELECT ticker, region, date, timeframe
                    FROM ohlcv_data
                    GROUP BY ticker, region, date, timeframe
                    HAVING COUNT(*) > 1
                ) AS dups
                """
            )

            if duplicates:
                self.duplicate_records_count.labels(
                    table='ohlcv_data'
                ).set(duplicates[0]['dup_count'])

        except Exception as e:
            logger.error(f"Error collecting data quality metrics: {e}")

    def collect_timescaledb_metrics(self):
        """Collect TimescaleDB-specific metrics."""
        try:
            # Hypertable statistics
            hypertables = self.db.execute_query(
                """
                SELECT
                    hypertable_name,
                    hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass) AS total_bytes,
                    (SELECT COUNT(*) FROM timescaledb_information.chunks
                     WHERE hypertable_name = h.hypertable_name) AS chunk_count
                FROM timescaledb_information.hypertables h
                WHERE hypertable_schema = 'public'
                """
            )

            for ht in hypertables:
                self.hypertable_size_bytes.labels(
                    hypertable=ht['hypertable_name']
                ).set(ht['total_bytes'])

                self.hypertable_chunks.labels(
                    hypertable=ht['hypertable_name']
                ).set(ht['chunk_count'])

            # Compression statistics
            compression = self.db.execute_query(
                """
                SELECT
                    hypertable_name,
                    COALESCE(compression_status, 'Uncompressed') AS status,
                    COUNT(*) as chunk_count
                FROM timescaledb_information.chunks
                WHERE hypertable_schema = 'public'
                GROUP BY hypertable_name, compression_status
                """
            )

            for comp in compression:
                if comp['status'] == 'Compressed':
                    self.compressed_chunks.labels(
                        hypertable=comp['hypertable_name']
                    ).set(comp['chunk_count'])

        except Exception as e:
            logger.error(f"Error collecting TimescaleDB metrics: {e}")

    def collect_business_metrics(self):
        """Collect business-level metrics."""
        try:
            # Total tickers by region and status
            tickers = self.db.execute_query(
                """
                SELECT region, is_active, COUNT(*) as count
                FROM tickers
                GROUP BY region, is_active
                """
            )

            for ticker_stat in tickers:
                self.total_tickers.labels(
                    region=ticker_stat['region'],
                    is_active=str(ticker_stat['is_active'])
                ).set(ticker_stat['count'])

            # OHLCV coverage for sample tickers
            coverage = self.db.execute_query(
                """
                SELECT
                    ticker,
                    region,
                    MAX(date) - MIN(date) AS coverage_days
                FROM ohlcv_data
                WHERE ticker IN ('005930', 'AAPL', 'TIGER')
                GROUP BY ticker, region
                """
            )

            for cov in coverage:
                if cov['coverage_days']:
                    self.ohlcv_coverage_days.labels(
                        ticker=cov['ticker'],
                        region=cov['region']
                    ).set(cov['coverage_days'])

        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")

    def collect_system_info(self):
        """Collect PostgreSQL version and configuration info."""
        try:
            # PostgreSQL version
            version = self.db.execute_query("SELECT version()")
            if version:
                self.postgres_info.info({
                    'version': version[0]['version'],
                    'database': 'quant_platform',
                    'last_update': datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error collecting system info: {e}")

    def collect_all_metrics(self):
        """Collect all metrics in one pass."""
        logger.info("Collecting PostgreSQL metrics...")

        start = time.perf_counter()

        try:
            self.collect_database_size_metrics()
            self.collect_query_performance_metrics()
            self.collect_connection_metrics()
            self.collect_index_metrics()
            self.collect_data_quality_metrics()
            self.collect_timescaledb_metrics()
            self.collect_business_metrics()
            self.collect_system_info()

            duration = time.perf_counter() - start
            logger.info(f"Metrics collection completed in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Error during metrics collection: {e}")

    def _collection_loop(self):
        """Background thread for periodic metric collection."""
        logger.info(f"Starting metrics collection loop (interval: {self.collection_interval}s)")

        while self._running:
            try:
                self.collect_all_metrics()
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")

            # Sleep in small intervals to allow quick shutdown
            for _ in range(self.collection_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Metrics collection loop stopped")

    def start_metrics_server(self, port: int = 8000):
        """
        Start Prometheus metrics HTTP server.

        Args:
            port: HTTP port for metrics endpoint (default: 8000)
        """
        logger.info(f"Starting Prometheus metrics server on port {port}")

        try:
            # Start HTTP server for Prometheus scraping
            start_http_server(port)
            logger.info(f"Metrics available at http://localhost:{port}/metrics")

            # Start background collection thread
            self._running = True
            self._collection_thread = threading.Thread(
                target=self._collection_loop,
                daemon=True
            )
            self._collection_thread.start()

            logger.info("Metrics collector started successfully")

        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise

    def stop(self):
        """Stop metrics collection."""
        logger.info("Stopping metrics collector...")
        self._running = False

        if self._collection_thread:
            self._collection_thread.join(timeout=5)

        logger.info("Metrics collector stopped")


def main():
    """Standalone metrics server for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="PostgreSQL Prometheus Metrics")
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='HTTP port for metrics endpoint (default: 8000)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Metrics collection interval in seconds (default: 60)'
    )

    args = parser.parse_args()

    # Setup logging
    logger.add("logs/postgres_metrics.log", rotation="100 MB")

    logger.info("=" * 70)
    logger.info("PostgreSQL Prometheus Metrics Server")
    logger.info("=" * 70)

    # Initialize PostgreSQL
    try:
        postgres_db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    # Create and start metrics collector
    collector = PostgresMetricsCollector(
        postgres_manager=postgres_db,
        collection_interval=args.interval
    )

    try:
        collector.start_metrics_server(port=args.port)

        logger.info(f"Metrics server running. Press Ctrl+C to stop.")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        collector.stop()
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        collector.stop()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
