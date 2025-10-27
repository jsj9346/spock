#!/usr/bin/env python3
"""
Database Query Performance Benchmark Script

Purpose: Benchmark critical queries for Quant Platform
Created: 2025-10-21
Part of: Phase 1 Task 5 (Performance Tuning)

Usage:
    python3 scripts/benchmark_queries.py

Performance Targets:
    - OHLCV queries: <1s (10-year data)
    - Factor score queries: <500ms
    - Backtest result queries: <200ms
    - Continuous aggregate queries: <100ms
"""

import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.db_manager_postgres import PostgresDatabaseManager


class QueryBenchmark:
    """Query performance benchmark suite"""

    def __init__(self):
        """Initialize benchmark with database connection"""
        self.db = PostgresDatabaseManager()
        self.results = []

    def benchmark_query(self, name: str, query: str, params: tuple = None,
                       target_ms: int = 1000, runs: int = 3) -> Dict:
        """
        Benchmark a single query

        Args:
            name: Benchmark name
            query: SQL query to execute
            params: Query parameters (optional)
            target_ms: Performance target in milliseconds
            runs: Number of runs for averaging

        Returns:
            Dict with benchmark results
        """
        print(f"\n📊 Benchmarking: {name}")
        print(f"   Target: <{target_ms}ms")
        print(f"   Runs: {runs}")

        times = []
        row_counts = []

        for i in range(runs):
            start_time = time.time()

            try:
                if params:
                    results = self.db._execute_query(query, params, fetch_all=True)
                else:
                    results = self.db._execute_query(query, fetch_all=True)

                elapsed_ms = (time.time() - start_time) * 1000
                times.append(elapsed_ms)
                row_count = len(results) if results else 0
                row_counts.append(row_count)

                print(f"   Run {i+1}: {elapsed_ms:.2f}ms ({row_count} rows)")

            except Exception as e:
                print(f"   ❌ Error in run {i+1}: {e}")
                return None

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        avg_rows = sum(row_counts) / len(row_counts)

        # Check if target met
        passed = avg_time < target_ms
        status = "✅ PASS" if passed else "❌ FAIL"

        result = {
            'name': name,
            'query': query[:100] + '...' if len(query) > 100 else query,
            'target_ms': target_ms,
            'avg_ms': round(avg_time, 2),
            'min_ms': round(min_time, 2),
            'max_ms': round(max_time, 2),
            'avg_rows': int(avg_rows),
            'runs': runs,
            'passed': passed,
            'status': status
        }

        self.results.append(result)

        print(f"   {status}: Avg {avg_time:.2f}ms (Min: {min_time:.2f}ms, Max: {max_time:.2f}ms)")

        return result

    def benchmark_ohlcv_queries(self):
        """Benchmark OHLCV data queries"""
        print("\n" + "="*70)
        print("OHLCV DATA QUERIES BENCHMARK")
        print("="*70)

        # Query 1: 10-year data for single ticker
        self.benchmark_query(
            name="OHLCV: 10-year data (single ticker)",
            query="""
                SELECT ticker, date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s AND timeframe = 'D'
                  AND date >= CURRENT_DATE - INTERVAL '10 years'
                ORDER BY date DESC
            """,
            params=('005930', 'KR'),
            target_ms=1000
        )

        # Query 2: Recent data for multiple tickers
        self.benchmark_query(
            name="OHLCV: 1-year data (3 tickers)",
            query="""
                SELECT ticker, date, close, volume
                FROM ohlcv_data
                WHERE region = 'KR' AND timeframe = 'D'
                  AND ticker IN ('005930', '000660', '035420')
                  AND date >= CURRENT_DATE - INTERVAL '1 year'
                ORDER BY date DESC, ticker
            """,
            target_ms=500
        )

        # Query 3: Aggregate statistics
        self.benchmark_query(
            name="OHLCV: Aggregate stats (1 ticker, 5 years)",
            query="""
                SELECT
                    COUNT(*) as trading_days,
                    MIN(low) as min_price,
                    MAX(high) as max_price,
                    AVG(close) as avg_close,
                    SUM(volume) as total_volume
                FROM ohlcv_data
                WHERE ticker = %s AND region = %s AND timeframe = 'D'
                  AND date >= CURRENT_DATE - INTERVAL '5 years'
            """,
            params=('005930', 'KR'),
            target_ms=300
        )

    def benchmark_continuous_aggregate_queries(self):
        """Benchmark continuous aggregate queries"""
        print("\n" + "="*70)
        print("CONTINUOUS AGGREGATE QUERIES BENCHMARK")
        print("="*70)

        # Query 1: Monthly aggregate
        self.benchmark_query(
            name="Continuous Aggregate: Monthly (5 years)",
            query="""
                SELECT ticker, region, month::date, open, close, volume
                FROM ohlcv_monthly
                WHERE ticker = %s AND region = %s
                  AND month >= CURRENT_DATE - INTERVAL '5 years'
                ORDER BY month DESC
            """,
            params=('005930', 'KR'),
            target_ms=100
        )

        # Query 2: Quarterly aggregate
        self.benchmark_query(
            name="Continuous Aggregate: Quarterly (3 years)",
            query="""
                SELECT ticker, region, quarter::date, open, close, volume, trading_days
                FROM ohlcv_quarterly
                WHERE ticker = %s AND region = %s
                  AND quarter >= CURRENT_DATE - INTERVAL '3 years'
                ORDER BY quarter DESC
            """,
            params=('005930', 'KR'),
            target_ms=100
        )

        # Query 3: Yearly aggregate
        self.benchmark_query(
            name="Continuous Aggregate: Yearly (10 years)",
            query="""
                SELECT ticker, region, year::date, open, close, volume
                FROM ohlcv_yearly
                WHERE ticker = %s AND region = %s
                ORDER BY year DESC
                LIMIT 10
            """,
            params=('005930', 'KR'),
            target_ms=100
        )

    def benchmark_factor_score_queries(self):
        """Benchmark factor score queries"""
        print("\n" + "="*70)
        print("FACTOR SCORE QUERIES BENCHMARK")
        print("="*70)

        # Query 1: Single factor, recent data
        self.benchmark_query(
            name="Factor: Single factor (1 year)",
            query="""
                SELECT ticker, region, date, factor_name, score, percentile
                FROM factor_scores
                WHERE factor_name = %s
                  AND date >= CURRENT_DATE - INTERVAL '1 year'
                ORDER BY date DESC, score DESC
                LIMIT 100
            """,
            params=('momentum',),
            target_ms=500
        )

        # Query 2: Multiple factors for single ticker
        self.benchmark_query(
            name="Factor: Multiple factors (1 ticker, 2 years)",
            query="""
                SELECT ticker, region, date, factor_name, score
                FROM factor_scores
                WHERE ticker = %s AND region = %s
                  AND date >= CURRENT_DATE - INTERVAL '2 years'
                ORDER BY date DESC, factor_name
            """,
            params=('005930', 'KR'),
            target_ms=300
        )

    def benchmark_backtest_queries(self):
        """Benchmark backtest-related queries"""
        print("\n" + "="*70)
        print("BACKTEST QUERIES BENCHMARK")
        print("="*70)

        # Query 1: Strategy results lookup
        self.benchmark_query(
            name="Backtest: Strategy results",
            query="""
                SELECT id, strategy_id, start_date, end_date,
                       total_return, sharpe_ratio, max_drawdown, win_rate
                FROM backtest_results
                ORDER BY created_at DESC
                LIMIT 50
            """,
            target_ms=200
        )

        # Query 2: Portfolio transactions for a strategy
        self.benchmark_query(
            name="Backtest: Portfolio transactions",
            query="""
                SELECT date, ticker, region, transaction_type, shares, price, total_value
                FROM portfolio_transactions
                ORDER BY date DESC
                LIMIT 100
            """,
            target_ms=200
        )

        # Query 3: Walk-forward results
        self.benchmark_query(
            name="Backtest: Walk-forward results",
            query="""
                SELECT strategy_id, train_start_date, test_end_date,
                       in_sample_sharpe, out_sample_sharpe, overfitting_ratio
                FROM walk_forward_results
                ORDER BY train_start_date DESC
                LIMIT 20
            """,
            target_ms=100
        )

    def benchmark_join_queries(self):
        """Benchmark complex join queries"""
        print("\n" + "="*70)
        print("COMPLEX JOIN QUERIES BENCHMARK")
        print("="*70)

        # Query 1: OHLCV with stock details
        self.benchmark_query(
            name="Join: OHLCV + Stock Details",
            query="""
                SELECT o.ticker, o.region, o.date, o.close,
                       s.sector, s.industry
                FROM ohlcv_data o
                JOIN stock_details s ON o.ticker = s.ticker AND o.region = s.region
                WHERE o.date >= CURRENT_DATE - INTERVAL '1 month'
                  AND o.timeframe = 'D'
                ORDER BY o.date DESC
                LIMIT 1000
            """,
            target_ms=500
        )

        # Query 2: Portfolio holdings with current prices
        self.benchmark_query(
            name="Join: Holdings + Current Prices",
            query="""
                SELECT p.ticker, p.region, p.weight, p.shares,
                       o.close as current_price,
                       (p.shares * o.close) as current_value
                FROM portfolio_holdings p
                LEFT JOIN LATERAL (
                    SELECT close
                    FROM ohlcv_data
                    WHERE ticker = p.ticker AND region = p.region
                      AND timeframe = 'D'
                    ORDER BY date DESC
                    LIMIT 1
                ) o ON true
                LIMIT 100
            """,
            target_ms=300
        )

    def print_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*70)
        print("BENCHMARK SUMMARY")
        print("="*70)
        print("")

        if not self.results:
            print("No benchmarks were run.")
            return

        # Calculate statistics
        total_benchmarks = len(self.results)
        passed_benchmarks = sum(1 for r in self.results if r['passed'])
        failed_benchmarks = total_benchmarks - passed_benchmarks
        pass_rate = (passed_benchmarks / total_benchmarks * 100) if total_benchmarks > 0 else 0

        # Print summary table
        print(f"{'Benchmark':<50} {'Target':<10} {'Actual':<10} {'Status':<10}")
        print("-" * 80)

        for result in self.results:
            print(f"{result['name']:<50} "
                  f"<{result['target_ms']}ms{'':<5} "
                  f"{result['avg_ms']:.2f}ms{'':<5} "
                  f"{result['status']:<10}")

        print("-" * 80)
        print(f"\nTotal Benchmarks: {total_benchmarks}")
        print(f"✅ Passed: {passed_benchmarks} ({pass_rate:.1f}%)")
        print(f"❌ Failed: {failed_benchmarks} ({100-pass_rate:.1f}%)")

        # Performance categories
        print("\n" + "="*70)
        print("PERFORMANCE CATEGORIES")
        print("="*70)
        print("")

        categories = {
            'Excellent (<100ms)': [r for r in self.results if r['avg_ms'] < 100],
            'Good (100-500ms)': [r for r in self.results if 100 <= r['avg_ms'] < 500],
            'Acceptable (500-1000ms)': [r for r in self.results if 500 <= r['avg_ms'] < 1000],
            'Slow (>1000ms)': [r for r in self.results if r['avg_ms'] >= 1000]
        }

        for category, benchmarks in categories.items():
            count = len(benchmarks)
            pct = (count / total_benchmarks * 100) if total_benchmarks > 0 else 0
            print(f"{category:<30} {count:>3} benchmarks ({pct:>5.1f}%)")

        # Overall assessment
        print("\n" + "="*70)
        print("OVERALL ASSESSMENT")
        print("="*70)
        print("")

        if pass_rate == 100:
            print("✅ EXCELLENT: All performance targets met!")
        elif pass_rate >= 80:
            print("✅ GOOD: Most performance targets met.")
        elif pass_rate >= 60:
            print("⚠️ WARNING: Some performance issues detected.")
        else:
            print("❌ CRITICAL: Significant performance issues detected.")

        # Recommendations
        print("\nRecommendations:")
        if failed_benchmarks > 0:
            print("  1. Review slow queries with EXPLAIN ANALYZE")
            print("  2. Check index usage and add missing indexes")
            print("  3. Consider query optimization or data partitioning")
            print("  4. Monitor cache hit ratios")
        else:
            print("  1. Continue monitoring performance regularly")
            print("  2. Set up automated performance regression tests")
            print("  3. Document baseline performance metrics")

    def save_report(self, filename: str = '/tmp/benchmark_report.txt'):
        """Save benchmark report to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(filename, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("DATABASE QUERY PERFORMANCE BENCHMARK REPORT\n")
            f.write("=" * 70 + "\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Database: quant_platform\n")
            f.write(f"Total Benchmarks: {len(self.results)}\n")
            f.write("\n")

            # Detailed results
            for result in self.results:
                f.write(f"\nBenchmark: {result['name']}\n")
                f.write(f"  Target: <{result['target_ms']}ms\n")
                f.write(f"  Average: {result['avg_ms']:.2f}ms\n")
                f.write(f"  Min: {result['min_ms']:.2f}ms\n")
                f.write(f"  Max: {result['max_ms']:.2f}ms\n")
                f.write(f"  Rows: {result['avg_rows']}\n")
                f.write(f"  Runs: {result['runs']}\n")
                f.write(f"  Status: {result['status']}\n")

        print(f"\n✅ Report saved to: {filename}")


def main():
    """Run all benchmarks"""
    print("\n" + "="*70)
    print("QUANT PLATFORM - DATABASE QUERY PERFORMANCE BENCHMARK")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    benchmark = QueryBenchmark()

    try:
        # Run all benchmark suites
        benchmark.benchmark_ohlcv_queries()
        benchmark.benchmark_continuous_aggregate_queries()
        benchmark.benchmark_factor_score_queries()
        benchmark.benchmark_backtest_queries()
        benchmark.benchmark_join_queries()

        # Print summary
        benchmark.print_summary()

        # Save report
        benchmark.save_report()

        print(f"\n{'='*70}")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
