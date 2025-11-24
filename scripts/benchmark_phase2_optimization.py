#!/usr/bin/env python3
"""
Phase 2 Optimization Benchmark

Measures actual performance improvement from Phase 2 optimizations.

Benchmark scenarios:
1. Small batch: 10 tickers (quick test)
2. Medium batch: 50 tickers (realistic scenario)
3. Large batch: 100 tickers (stress test)

Author: Quant Investment Platform
Date: 2025-11-23
"""

import sys
import os
import time
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.collection.kr_postgres_ohlcv_adapter import KRPostgresOHLCVAdapter
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase2Benchmark:
    """Benchmark Phase 2 optimizations"""

    def __init__(self):
        self.db = PostgresDatabaseManager()
        self.results = {}

    def run_benchmark(self, scenario: str, limit: int, days: int = 30) -> dict:
        """
        Run a single benchmark scenario

        Args:
            scenario: Scenario name
            limit: Number of tickers to process
            days: Number of days to collect per ticker

        Returns:
            Performance metrics dict
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Benchmark Scenario: {scenario}")
        logger.info(f"{'='*80}")
        logger.info(f"Tickers: {limit}")
        logger.info(f"Days per ticker: {days}")
        logger.info("")

        # Initialize adapter with Phase 2 optimizations
        adapter = KRPostgresOHLCVAdapter(
            db=self.db,
            config={
                'dry_run': False,
                'rate_limit': 0.05,  # 20 req/s
                'batch_size': 500,  # OPT-2
                'validation_threshold': 0.7,
                'warm_cache': True  # OPT-3
            }
        )

        # Run collection with timing
        start_time = time.time()

        result = adapter.run_collection_parallel(
            incremental=True,
            limit=limit,
            days=days,
            force_refresh=False,
            stale_days=2,
            max_workers=None  # OPT-5: Auto-detect
        )

        duration = time.time() - start_time

        # Calculate metrics
        metrics = {
            'scenario': scenario,
            'limit': limit,
            'days': days,
            'duration_seconds': duration,
            'tickers_collected': result.get('tickers_collected', 0),
            'tickers_skipped': result.get('tickers_skipped', 0),
            'tickers_failed': result.get('tickers_failed', 0),
            'records_inserted': result.get('records_inserted', 0),
            'records_updated': result.get('records_updated', 0),
            'throughput_tickers_per_sec': result.get('tickers_collected', 0) / duration if duration > 0 else 0,
            'throughput_records_per_sec': result.get('records_inserted', 0) / duration if duration > 0 else 0,
            'avg_time_per_ticker': duration / result.get('tickers_collected', 1) if result.get('tickers_collected') > 0 else 0,
            'success_rate': result.get('tickers_collected', 0) / limit if limit > 0 else 0
        }

        logger.info(f"\nResults:")
        logger.info(f"  Duration: {metrics['duration_seconds']:.2f}s")
        logger.info(f"  Tickers collected: {metrics['tickers_collected']}")
        logger.info(f"  Records inserted: {metrics['records_inserted']}")
        logger.info(f"  Throughput: {metrics['throughput_tickers_per_sec']:.2f} tickers/s")
        logger.info(f"  Avg time per ticker: {metrics['avg_time_per_ticker']:.2f}s")
        logger.info(f"  Success rate: {metrics['success_rate']:.1%}")

        return metrics

    def run_all_benchmarks(self) -> dict:
        """Run all benchmark scenarios"""
        logger.info("="*80)
        logger.info("Phase 2 Optimization Benchmark Suite")
        logger.info("="*80)
        logger.info("")
        logger.info("Phase 2 Optimizations Applied:")
        logger.info("  ✅ OPT-1: DB connection pool (20×60)")
        logger.info("  ✅ OPT-2: Batch insert size (500)")
        logger.info("  ✅ OPT-3: Cache warming")
        logger.info("  ✅ OPT-4: PostgreSQL tuning")
        logger.info("  ✅ OPT-5: Parallelism (auto-detect workers)")
        logger.info("  ✅ OPT-6: Index optimization")
        logger.info("")

        scenarios = [
            {'name': 'Small Batch', 'limit': 10, 'days': 30},
            {'name': 'Medium Batch', 'limit': 50, 'days': 30},
            {'name': 'Large Batch', 'limit': 100, 'days': 30}
        ]

        results = []

        for scenario in scenarios:
            metrics = self.run_benchmark(
                scenario['name'],
                scenario['limit'],
                scenario['days']
            )
            results.append(metrics)

            # Cooldown between scenarios
            time.sleep(2)

        # Save results
        output_file = 'benchmark_phase2_results.json'
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'optimizations_applied': [
                    'OPT-1: DB connection pool (20×60)',
                    'OPT-2: Batch insert size (500)',
                    'OPT-3: Cache warming',
                    'OPT-4: PostgreSQL tuning',
                    'OPT-5: Parallelism (auto-detect)',
                    'OPT-6: Index optimization'
                ],
                'results': results
            }, f, indent=2)

        logger.info(f"\n{'='*80}")
        logger.info(f"Benchmark results saved to: {output_file}")
        logger.info(f"{'='*80}")

        # Print summary
        self.print_summary(results)

        return results

    def print_summary(self, results: list) -> None:
        """Print benchmark summary"""
        logger.info("\n" + "="*80)
        logger.info("Benchmark Summary")
        logger.info("="*80)
        logger.info("")
        logger.info(f"{'Scenario':<20} {'Tickers':<10} {'Duration':<12} {'Throughput':<15} {'Success Rate':<15}")
        logger.info("-" * 80)

        for r in results:
            logger.info(
                f"{r['scenario']:<20} "
                f"{r['tickers_collected']:<10} "
                f"{r['duration_seconds']:>10.2f}s "
                f"{r['throughput_tickers_per_sec']:>13.2f}/s "
                f"{r['success_rate']:>13.1%}"
            )

        logger.info("="*80)

        # Extrapolate to full dataset
        if results:
            avg_time_per_ticker = sum(r['avg_time_per_ticker'] for r in results) / len(results)
            estimated_full_time = avg_time_per_ticker * 3932  # Total KR tickers

            logger.info(f"\nExtrapolated Performance (3,932 tickers):")
            logger.info(f"  Estimated duration: {estimated_full_time:.0f}s ({estimated_full_time/60:.1f} min)")
            logger.info(f"  Week 4 baseline: 118s (1.97 min)")
            logger.info(f"  Phase 2 target: 87s (1.45 min)")

            if estimated_full_time <= 87:
                logger.info(f"  ✅ Target achieved! ({((118 - estimated_full_time) / 118 * 100):.1f}% improvement)")
            else:
                logger.info(f"  ⚠️  Close to target ({((118 - estimated_full_time) / 118 * 100):.1f}% improvement)")


def main():
    benchmark = Phase2Benchmark()
    benchmark.run_all_benchmarks()


if __name__ == '__main__':
    main()
