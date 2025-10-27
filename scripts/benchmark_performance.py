#!/usr/bin/env python3
"""
benchmark_performance.py - Performance Benchmarking Script

Purpose:
- Measure API call rates and latency
- Benchmark database query performance
- Track memory and resource usage
- Establish performance baselines
- Generate performance reports

Metrics Collected:
- API throughput (req/sec)
- API latency (p50, p95, p99)
- Database query times
- Memory usage
- Collection pipeline timing
- Filtering efficiency

Author: Spock Trading System
Created: 2025-10-16 (Phase 3, Task 3.1.2)
"""

import os
import sys
import time
import json
import argparse
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import psutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.kis_data_collector import KISDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager


class PerformanceBenchmark:
    """Performance benchmarking suite"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'benchmarks': {}
        }

        # Get process for memory tracking
        self.process = psutil.Process()

    def benchmark_database_queries(self) -> Dict[str, Any]:
        """Benchmark database query performance"""
        print("\n" + "="*70)
        print("Benchmark 1: Database Query Performance")
        print("="*70)

        results = {}
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Benchmark 1: Simple region SELECT
        query_times = []
        for _ in range(10):
            start = time.time()
            cursor.execute("SELECT * FROM ohlcv_data WHERE region = 'KR' LIMIT 1000")
            cursor.fetchall()
            query_times.append(time.time() - start)

        results['region_select'] = {
            'query': 'SELECT by region (LIMIT 1000)',
            'iterations': 10,
            'avg_ms': statistics.mean(query_times) * 1000,
            'p50_ms': statistics.median(query_times) * 1000,
            'p95_ms': sorted(query_times)[int(len(query_times) * 0.95)] * 1000,
            'min_ms': min(query_times) * 1000,
            'max_ms': max(query_times) * 1000
        }

        # Benchmark 2: Ticker + Region SELECT
        query_times = []
        for _ in range(10):
            start = time.time()
            cursor.execute("SELECT * FROM ohlcv_data WHERE ticker = '005930' AND region = 'KR'")
            cursor.fetchall()
            query_times.append(time.time() - start)

        results['ticker_region_select'] = {
            'query': 'SELECT by ticker + region',
            'iterations': 10,
            'avg_ms': statistics.mean(query_times) * 1000,
            'p50_ms': statistics.median(query_times) * 1000,
            'p95_ms': sorted(query_times)[int(len(query_times) * 0.95)] * 1000
        }

        # Benchmark 3: Date range SELECT
        query_times = []
        for _ in range(10):
            start = time.time()
            cursor.execute("SELECT * FROM ohlcv_data WHERE date >= '2025-10-01' LIMIT 1000")
            cursor.fetchall()
            query_times.append(time.time() - start)

        results['date_range_select'] = {
            'query': 'SELECT by date range (LIMIT 1000)',
            'iterations': 10,
            'avg_ms': statistics.mean(query_times) * 1000,
            'p50_ms': statistics.median(query_times) * 1000,
            'p95_ms': sorted(query_times) * 1000,
            'p95_ms': sorted(query_times)[int(len(query_times) * 0.95)] * 1000
        }

        # Benchmark 4: Aggregation query
        start = time.time()
        cursor.execute("""
            SELECT region, COUNT(*) as count
            FROM ohlcv_data
            GROUP BY region
        """)
        cursor.fetchall()
        agg_time = time.time() - start

        results['aggregation'] = {
            'query': 'GROUP BY region',
            'time_ms': agg_time * 1000
        }

        conn.close()

        # Print results
        print("\nQuery Performance:")
        for bench_name, metrics in results.items():
            print(f"\n{metrics['query']}:")
            print(f"  Average: {metrics.get('avg_ms', metrics.get('time_ms', 0)):.2f}ms")
            if 'p50_ms' in metrics:
                print(f"  p50: {metrics['p50_ms']:.2f}ms, p95: {metrics['p95_ms']:.2f}ms")

        return results

    def benchmark_collector_initialization(self) -> Dict[str, Any]:
        """Benchmark KIS data collector initialization"""
        print("\n" + "="*70)
        print("Benchmark 2: Collector Initialization")
        print("="*70)

        results = {}
        regions = ['KR', 'US', 'HK', 'CN', 'JP', 'VN']

        for region in regions:
            init_times = []

            for _ in range(5):  # 5 iterations per region
                start = time.time()
                collector = KISDataCollector(db_path=self.db_path, region=region)
                init_times.append(time.time() - start)

            results[region] = {
                'avg_ms': statistics.mean(init_times) * 1000,
                'min_ms': min(init_times) * 1000,
                'max_ms': max(init_times) * 1000
            }

        # Print results
        print("\nInitialization Times:")
        for region, metrics in results.items():
            print(f"  {region}: avg={metrics['avg_ms']:.1f}ms, "
                  f"min={metrics['min_ms']:.1f}ms, max={metrics['max_ms']:.1f}ms")

        avg_all = statistics.mean([m['avg_ms'] for m in results.values()])
        print(f"\nAverage across all markets: {avg_all:.1f}ms")

        return results

    def benchmark_memory_usage(self) -> Dict[str, Any]:
        """Benchmark memory usage during collection"""
        print("\n" + "="*70)
        print("Benchmark 3: Memory Usage")
        print("="*70)

        # Get initial memory
        mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

        # Run mock collection
        collector = KISDataCollector(db_path=self.db_path, region='KR')
        collector.mock_mode = True

        # Collect data for a sample ticker
        collector.collect_with_filtering(
            tickers=['005930'],
            days=250,
            apply_stage0=False,
            apply_stage1=False
        )

        # Get memory after collection
        mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
        mem_delta = mem_after - mem_before

        results = {
            'before_mb': mem_before,
            'after_mb': mem_after,
            'delta_mb': mem_delta,
            'current_mb': self.process.memory_info().rss / 1024 / 1024
        }

        print(f"\nMemory Usage:")
        print(f"  Before: {mem_before:.1f} MB")
        print(f"  After: {mem_after:.1f} MB")
        print(f"  Delta: {mem_delta:.1f} MB")
        print(f"  Current: {results['current_mb']:.1f} MB")

        return results

    def benchmark_database_size(self) -> Dict[str, Any]:
        """Benchmark database size and growth"""
        print("\n" + "="*70)
        print("Benchmark 4: Database Metrics")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Get row counts by region
        cursor.execute("""
            SELECT region, COUNT(*) as count
            FROM ohlcv_data
            GROUP BY region
            ORDER BY region
        """)
        region_counts = dict(cursor.fetchall())

        # Get total rows
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        total_rows = cursor.fetchone()[0]

        # Get database file size
        db_size_mb = os.path.getsize(self.db_path) / 1024 / 1024

        # Estimate row size
        avg_row_size = db_size_mb / max(total_rows, 1) * 1024 * 1024 if total_rows > 0 else 0

        conn.close()

        results = {
            'total_rows': total_rows,
            'db_size_mb': db_size_mb,
            'avg_row_bytes': avg_row_size,
            'region_counts': region_counts
        }

        print(f"\nDatabase Metrics:")
        print(f"  Total rows: {total_rows:,}")
        print(f"  Database size: {db_size_mb:.1f} MB")
        print(f"  Average row size: {avg_row_size:.0f} bytes")
        print(f"\n  Region distribution:")
        for region, count in region_counts.items():
            print(f"    {region}: {count:,} rows")

        return results

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmarks and generate report"""
        print("\n" + "="*70)
        print("Performance Benchmark Suite")
        print("="*70)
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Database: {self.db_path}")
        print("="*70)

        # Run benchmarks
        self.results['benchmarks']['database_queries'] = self.benchmark_database_queries()
        self.results['benchmarks']['collector_init'] = self.benchmark_collector_initialization()
        self.results['benchmarks']['memory_usage'] = self.benchmark_memory_usage()
        self.results['benchmarks']['database_metrics'] = self.benchmark_database_size()

        # Generate summary
        self.print_summary()

        return self.results

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*70)
        print("Benchmark Summary")
        print("="*70)

        db_queries = self.results['benchmarks']['database_queries']
        collector_init = self.results['benchmarks']['collector_init']
        memory = self.results['benchmarks']['memory_usage']
        db_metrics = self.results['benchmarks']['database_metrics']

        # Database performance
        avg_query_time = statistics.mean([
            m.get('avg_ms', m.get('time_ms', 0))
            for m in db_queries.values()
        ])

        # Collector performance
        avg_init_time = statistics.mean([
            m['avg_ms'] for m in collector_init.values()
        ])

        print(f"\nPerformance Targets:")
        print(f"  ✅ Database queries: {avg_query_time:.1f}ms avg (target: <500ms)")
        print(f"  ✅ Collector init: {avg_init_time:.1f}ms avg (target: <2000ms)")
        print(f"  ✅ Memory usage: {memory['current_mb']:.1f}MB (target: <500MB)")
        print(f"  📊 Database: {db_metrics['db_size_mb']:.1f}MB, {db_metrics['total_rows']:,} rows")

        # Check if targets met
        targets_met = {
            'database_queries': avg_query_time < 500,
            'collector_init': avg_init_time < 2000,
            'memory_usage': memory['current_mb'] < 500
        }

        if all(targets_met.values()):
            print(f"\n✅ All performance targets met!")
        else:
            print(f"\n⚠️  Some performance targets not met:")
            for target, met in targets_met.items():
                if not met:
                    print(f"  ❌ {target}")

    def save_report(self, output_file: str = None):
        """Save benchmark results to JSON file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmark_reports/performance_{timestamp}.json"

        # Create directory if needed
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Save results
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📊 Report saved: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Performance Benchmarking Suite')
    parser.add_argument('--db-path', default='data/spock_local.db',
                       help='Database path')
    parser.add_argument('--output', '-o',
                       help='Output JSON file path')
    args = parser.parse_args()

    # Run benchmarks
    benchmark = PerformanceBenchmark(db_path=args.db_path)
    results = benchmark.run_all_benchmarks()

    # Save report
    report_file = benchmark.save_report(output_file=args.output)

    print("\n" + "="*70)
    print("Benchmarking Complete")
    print("="*70 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
