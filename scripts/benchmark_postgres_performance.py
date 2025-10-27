#!/usr/bin/env python3
"""
PostgreSQL Performance Benchmarking

Benchmarks query performance and validates against target metrics.

Target Metrics (from QUANT_DATABASE_SCHEMA.md):
- 250 days OHLCV:  < 100ms
- 1 year OHLCV:    < 500ms
- 10 years OHLCV:  < 1s

Usage:
    python3 scripts/benchmark_postgres_performance.py
    python3 scripts/benchmark_postgres_performance.py --ticker 005930 --region KR
    python3 scripts/benchmark_postgres_performance.py --comprehensive
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
import time
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from modules.db_manager_postgres import PostgresDatabaseManager


class PostgresPerformanceBenchmark:
    """
    Benchmarks PostgreSQL + TimescaleDB query performance.

    Tests:
    - OHLCV queries (various time ranges)
    - Aggregation queries
    - Join queries
    - Index effectiveness
    """

    def __init__(self, postgres_manager: PostgresDatabaseManager):
        """
        Initialize benchmark.

        Args:
            postgres_manager: PostgreSQL database manager
        """
        self.db = postgres_manager

        # Benchmark results
        self.results = {
            'ohlcv_queries': [],
            'aggregations': [],
            'joins': [],
            'complex_queries': []
        }

        # Performance targets (milliseconds)
        self.targets = {
            '250_days': 100,
            '1_year': 500,
            '10_years': 1000
        }

    def benchmark_ohlcv_query(self,
                              ticker: str,
                              region: str,
                              days: int,
                              runs: int = 5) -> Dict[str, Any]:
        """
        Benchmark OHLCV query for specific time range.

        Args:
            ticker: Ticker symbol
            region: Market region
            days: Number of days to query
            runs: Number of times to run query

        Returns:
            Dictionary with benchmark results
        """
        query = f"""
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = '{ticker}'
              AND region = '{region}'
              AND date >= CURRENT_DATE - INTERVAL '{days} days'
            ORDER BY date DESC
        """

        execution_times = []

        for i in range(runs):
            start = time.perf_counter()
            results = self.db.execute_query(query)
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            execution_times.append(elapsed)

        return {
            'query_type': f'OHLCV_{days}_days',
            'ticker': ticker,
            'region': region,
            'days': days,
            'rows_returned': len(results) if results else 0,
            'runs': runs,
            'mean_ms': statistics.mean(execution_times),
            'median_ms': statistics.median(execution_times),
            'min_ms': min(execution_times),
            'max_ms': max(execution_times),
            'std_dev_ms': statistics.stdev(execution_times) if len(execution_times) > 1 else 0,
            'all_times': execution_times
        }

    def benchmark_all_ohlcv_ranges(self,
                                   ticker: str = '005930',
                                   region: str = 'KR') -> List[Dict]:
        """
        Benchmark OHLCV queries for all standard time ranges.

        Args:
            ticker: Ticker to test
            region: Market region

        Returns:
            List of benchmark results
        """
        logger.info("=" * 70)
        logger.info("Benchmarking OHLCV Queries")
        logger.info("=" * 70)

        ranges = [
            ('250_days', 250),
            ('1_year', 365),
            ('3_years', 365 * 3),
            ('5_years', 365 * 5),
            ('10_years', 365 * 10)
        ]

        results = []

        for range_name, days in ranges:
            logger.info(f"\nTesting {range_name} ({days} days)...")

            result = self.benchmark_ohlcv_query(ticker, region, days, runs=5)
            results.append(result)

            # Check against target
            target = self.targets.get(range_name)
            if target:
                status = "✅" if result['mean_ms'] < target else "❌"
                logger.info(
                    f"{status} {range_name}: {result['mean_ms']:.1f}ms "
                    f"(target: <{target}ms, rows: {result['rows_returned']:,})"
                )
            else:
                logger.info(
                    f"ℹ️  {range_name}: {result['mean_ms']:.1f}ms "
                    f"(rows: {result['rows_returned']:,})"
                )

            self.results['ohlcv_queries'].append(result)

        return results

    def benchmark_aggregations(self,
                              ticker: str = '005930',
                              region: str = 'KR') -> List[Dict]:
        """
        Benchmark aggregation queries (monthly/yearly OHLCV).

        Args:
            ticker: Ticker to test
            region: Market region

        Returns:
            List of benchmark results
        """
        logger.info("=" * 70)
        logger.info("Benchmarking Aggregation Queries")
        logger.info("=" * 70)

        queries = [
            {
                'name': 'monthly_ohlcv',
                'query': f"""
                    SELECT
                        DATE_TRUNC('month', date) AS month,
                        FIRST(open, date) AS open,
                        MAX(high) AS high,
                        MIN(low) AS low,
                        LAST(close, date) AS close,
                        SUM(volume) AS volume
                    FROM ohlcv_data
                    WHERE ticker = '{ticker}' AND region = '{region}'
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 60
                """
            },
            {
                'name': 'yearly_ohlcv',
                'query': f"""
                    SELECT
                        DATE_TRUNC('year', date) AS year,
                        FIRST(open, date) AS open,
                        MAX(high) AS high,
                        MIN(low) AS low,
                        LAST(close, date) AS close,
                        SUM(volume) AS volume
                    FROM ohlcv_data
                    WHERE ticker = '{ticker}' AND region = '{region}'
                    GROUP BY year
                    ORDER BY year DESC
                """
            },
            {
                'name': 'moving_average_50',
                'query': f"""
                    SELECT
                        date,
                        close,
                        AVG(close) OVER (ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS sma_50
                    FROM ohlcv_data
                    WHERE ticker = '{ticker}' AND region = '{region}'
                    ORDER BY date DESC
                    LIMIT 250
                """
            }
        ]

        results = []

        for query_spec in queries:
            logger.info(f"\nTesting {query_spec['name']}...")

            execution_times = []
            for i in range(5):
                start = time.perf_counter()
                query_results = self.db.execute_query(query_spec['query'])
                elapsed = (time.perf_counter() - start) * 1000
                execution_times.append(elapsed)

            result = {
                'query_type': query_spec['name'],
                'ticker': ticker,
                'region': region,
                'rows_returned': len(query_results) if query_results else 0,
                'mean_ms': statistics.mean(execution_times),
                'median_ms': statistics.median(execution_times),
                'min_ms': min(execution_times),
                'max_ms': max(execution_times)
            }

            logger.info(
                f"✅ {query_spec['name']}: {result['mean_ms']:.1f}ms "
                f"(rows: {result['rows_returned']:,})"
            )

            results.append(result)
            self.results['aggregations'].append(result)

        return results

    def benchmark_joins(self) -> List[Dict]:
        """
        Benchmark join queries.

        Returns:
            List of benchmark results
        """
        logger.info("=" * 70)
        logger.info("Benchmarking Join Queries")
        logger.info("=" * 70)

        queries = [
            {
                'name': 'ohlcv_with_tickers',
                'query': """
                    SELECT o.ticker, o.region, o.date, o.close, t.name, t.sector
                    FROM ohlcv_data o
                    JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
                    WHERE o.date >= CURRENT_DATE - INTERVAL '30 days'
                    LIMIT 1000
                """
            },
            {
                'name': 'ohlcv_with_technical',
                'query': """
                    SELECT o.ticker, o.region, o.date, o.close,
                           ta.rsi_14, ta.macd, ta.sma_20, ta.sma_50
                    FROM ohlcv_data o
                    LEFT JOIN technical_analysis ta
                        ON o.ticker = ta.ticker
                        AND o.region = ta.region
                        AND o.date = ta.date
                    WHERE o.date >= CURRENT_DATE - INTERVAL '30 days'
                    LIMIT 1000
                """
            }
        ]

        results = []

        for query_spec in queries:
            logger.info(f"\nTesting {query_spec['name']}...")

            execution_times = []
            for i in range(5):
                start = time.perf_counter()
                query_results = self.db.execute_query(query_spec['query'])
                elapsed = (time.perf_counter() - start) * 1000
                execution_times.append(elapsed)

            result = {
                'query_type': query_spec['name'],
                'rows_returned': len(query_results) if query_results else 0,
                'mean_ms': statistics.mean(execution_times),
                'median_ms': statistics.median(execution_times),
                'min_ms': min(execution_times),
                'max_ms': max(execution_times)
            }

            logger.info(
                f"✅ {query_spec['name']}: {result['mean_ms']:.1f}ms "
                f"(rows: {result['rows_returned']:,})"
            )

            results.append(result)
            self.results['joins'].append(result)

        return results

    def benchmark_complex_queries(self) -> List[Dict]:
        """
        Benchmark complex analytical queries.

        Returns:
            List of benchmark results
        """
        logger.info("=" * 70)
        logger.info("Benchmarking Complex Analytical Queries")
        logger.info("=" * 70)

        queries = [
            {
                'name': 'top_gainers_daily',
                'query': """
                    WITH daily_returns AS (
                        SELECT
                            ticker,
                            region,
                            date,
                            close,
                            LAG(close) OVER (PARTITION BY ticker, region ORDER BY date) AS prev_close,
                            CASE
                                WHEN LAG(close) OVER (PARTITION BY ticker, region ORDER BY date) > 0
                                THEN (close - LAG(close) OVER (PARTITION BY ticker, region ORDER BY date)) /
                                     LAG(close) OVER (PARTITION BY ticker, region ORDER BY date)
                                ELSE NULL
                            END AS daily_return
                        FROM ohlcv_data
                        WHERE date = (SELECT MAX(date) FROM ohlcv_data)
                    )
                    SELECT ticker, region, daily_return
                    FROM daily_returns
                    WHERE daily_return IS NOT NULL
                    ORDER BY daily_return DESC
                    LIMIT 20
                """
            },
            {
                'name': 'volume_leaders',
                'query': """
                    SELECT
                        ticker,
                        region,
                        date,
                        volume,
                        close,
                        volume * close AS dollar_volume
                    FROM ohlcv_data
                    WHERE date = (SELECT MAX(date) FROM ohlcv_data)
                    ORDER BY dollar_volume DESC
                    LIMIT 20
                """
            },
            {
                'name': 'volatility_ranking',
                'query': """
                    WITH price_stats AS (
                        SELECT
                            ticker,
                            region,
                            STDDEV(close) / NULLIF(AVG(close), 0) AS volatility
                        FROM ohlcv_data
                        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY ticker, region
                    )
                    SELECT ticker, region, volatility
                    FROM price_stats
                    WHERE volatility IS NOT NULL
                    ORDER BY volatility DESC
                    LIMIT 20
                """
            }
        ]

        results = []

        for query_spec in queries:
            logger.info(f"\nTesting {query_spec['name']}...")

            execution_times = []
            for i in range(3):  # Fewer runs for complex queries
                start = time.perf_counter()
                query_results = self.db.execute_query(query_spec['query'])
                elapsed = (time.perf_counter() - start) * 1000
                execution_times.append(elapsed)

            result = {
                'query_type': query_spec['name'],
                'rows_returned': len(query_results) if query_results else 0,
                'mean_ms': statistics.mean(execution_times),
                'median_ms': statistics.median(execution_times),
                'min_ms': min(execution_times),
                'max_ms': max(execution_times)
            }

            logger.info(
                f"✅ {query_spec['name']}: {result['mean_ms']:.1f}ms "
                f"(rows: {result['rows_returned']:,})"
            )

            results.append(result)
            self.results['complex_queries'].append(result)

        return results

    def test_index_effectiveness(self) -> Dict[str, Any]:
        """
        Test index effectiveness using EXPLAIN ANALYZE.

        Returns:
            Dictionary with index analysis
        """
        logger.info("=" * 70)
        logger.info("Testing Index Effectiveness")
        logger.info("=" * 70)

        test_query = """
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = '005930'
              AND region = 'KR'
              AND date >= CURRENT_DATE - INTERVAL '1 year'
            ORDER BY date DESC
        """

        try:
            result = self.db.execute_query(test_query)
            plan = result[0]['QUERY PLAN'][0]

            execution_time = plan['Execution Time']
            planning_time = plan['Planning Time']

            logger.info(f"Planning time: {planning_time:.2f}ms")
            logger.info(f"Execution time: {execution_time:.2f}ms")

            # Check if index is used
            plan_str = str(plan)
            index_used = 'Index' in plan_str

            if index_used:
                logger.info("✅ Index is being used")
            else:
                logger.warning("⚠️  No index detected in query plan")

            return {
                'planning_time_ms': planning_time,
                'execution_time_ms': execution_time,
                'index_used': index_used
            }

        except Exception as e:
            logger.error(f"❌ Error analyzing index effectiveness: {e}")
            return {}

    def print_summary(self):
        """Print benchmark summary."""
        logger.info("=" * 70)
        logger.info("PERFORMANCE BENCHMARK SUMMARY")
        logger.info("=" * 70)

        # OHLCV queries
        if self.results['ohlcv_queries']:
            logger.info("\n📊 OHLCV Query Performance:")
            for result in self.results['ohlcv_queries']:
                target = self.targets.get(result['query_type'])
                if target:
                    status = "✅" if result['mean_ms'] < target else "❌"
                    logger.info(
                        f"  {status} {result['query_type']:20s}: {result['mean_ms']:7.1f}ms "
                        f"(target: <{target:4d}ms)"
                    )
                else:
                    logger.info(
                        f"  ℹ️  {result['query_type']:20s}: {result['mean_ms']:7.1f}ms"
                    )

        # Aggregations
        if self.results['aggregations']:
            logger.info("\n📈 Aggregation Performance:")
            for result in self.results['aggregations']:
                logger.info(
                    f"  ✅ {result['query_type']:25s}: {result['mean_ms']:7.1f}ms"
                )

        # Joins
        if self.results['joins']:
            logger.info("\n🔗 Join Query Performance:")
            for result in self.results['joins']:
                logger.info(
                    f"  ✅ {result['query_type']:25s}: {result['mean_ms']:7.1f}ms"
                )

        # Complex queries
        if self.results['complex_queries']:
            logger.info("\n🧮 Complex Query Performance:")
            for result in self.results['complex_queries']:
                logger.info(
                    f"  ✅ {result['query_type']:25s}: {result['mean_ms']:7.1f}ms"
                )

        logger.info("=" * 70)

        # Overall assessment
        ohlcv_targets_met = all(
            result['mean_ms'] < self.targets.get(result['query_type'], float('inf'))
            for result in self.results['ohlcv_queries']
            if result['query_type'] in self.targets
        )

        if ohlcv_targets_met:
            logger.info("✅ ALL PERFORMANCE TARGETS MET")
        else:
            logger.warning("⚠️  SOME PERFORMANCE TARGETS NOT MET")


def main():
    """Main benchmark workflow."""
    parser = argparse.ArgumentParser(description="Benchmark PostgreSQL performance")
    parser.add_argument(
        '--ticker',
        default='005930',
        help='Ticker to use for benchmarks (default: 005930)'
    )
    parser.add_argument(
        '--region',
        default='KR',
        help='Region to use for benchmarks (default: KR)'
    )
    parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='Run comprehensive benchmarks (all tests)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick benchmarks (OHLCV only)'
    )

    args = parser.parse_args()

    # Setup logging
    log_file = f"logs/{datetime.now().strftime('%Y%m%d')}_benchmark.log"
    logger.add(log_file, rotation="100 MB")

    logger.info("=" * 70)
    logger.info("PostgreSQL Performance Benchmark")
    logger.info("=" * 70)
    logger.info(f"Test ticker: {args.ticker} ({args.region})")

    # Initialize PostgreSQL
    try:
        postgres_db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    # Create benchmark
    benchmark = PostgresPerformanceBenchmark(postgres_db)

    # Run benchmarks
    if args.quick:
        # Quick: OHLCV only
        benchmark.benchmark_all_ohlcv_ranges(ticker=args.ticker, region=args.region)

    elif args.comprehensive:
        # Comprehensive: All tests
        benchmark.benchmark_all_ohlcv_ranges(ticker=args.ticker, region=args.region)
        benchmark.benchmark_aggregations(ticker=args.ticker, region=args.region)
        benchmark.benchmark_joins()
        benchmark.benchmark_complex_queries()
        benchmark.test_index_effectiveness()

    else:
        # Standard: OHLCV + aggregations
        benchmark.benchmark_all_ohlcv_ranges(ticker=args.ticker, region=args.region)
        benchmark.benchmark_aggregations(ticker=args.ticker, region=args.region)

    # Print summary
    benchmark.print_summary()

    return 0


if __name__ == '__main__':
    sys.exit(main())
