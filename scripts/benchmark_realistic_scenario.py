#!/usr/bin/env python3
"""
Realistic Production Scenario Benchmark

Measures actual production performance with incremental updates.
This matches the Week 4 baseline conditions.

Scenario:
- Incremental mode (only stale data)
- 1-2 days stale threshold (realistic)
- Full dataset (all 3,932 tickers)
- Short data collection (1-3 days)

Author: Quant Investment Platform
Date: 2025-11-24
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta

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


class RealisticBenchmark:
    """Realistic production scenario benchmark"""

    def __init__(self):
        self.db = PostgresDatabaseManager()

    def get_stale_ticker_count(self, stale_days: int) -> int:
        """Get number of tickers with stale data"""
        query = """
        WITH latest_data AS (
            SELECT
                ticker,
                MAX(date) as last_date
            FROM ohlcv_data
            WHERE region = 'KR'
            GROUP BY ticker
        )
        SELECT COUNT(*) as stale_count
        FROM latest_data
        WHERE last_date < CURRENT_DATE - INTERVAL '%s days'
        """ % stale_days

        result = self.db.execute_query(query)
        return result[0]['stale_count'] if result else 0

    def run_realistic_benchmark(
        self,
        stale_days: int = 1,
        days_per_ticker: int = 3,
        limit: int = None
    ) -> dict:
        """
        Run realistic production scenario benchmark

        Args:
            stale_days: Consider data stale if older than this (default: 1)
            days_per_ticker: Number of days to collect per ticker (default: 3)
            limit: Optional limit on tickers (None = all)

        Returns:
            Performance metrics dict
        """
        logger.info("="*80)
        logger.info("Realistic Production Scenario Benchmark")
        logger.info("="*80)
        logger.info(f"Stale threshold: >{stale_days} days")
        logger.info(f"Days per ticker: {days_per_ticker}")
        logger.info(f"Limit: {limit if limit else 'None (all tickers)'}")
        logger.info("")

        # Check how many tickers are actually stale
        stale_count = self.get_stale_ticker_count(stale_days)
        logger.info(f"📊 Stale tickers (>{stale_days} days): {stale_count:,}")
        logger.info(f"📊 Fresh tickers: {3932 - stale_count:,}")
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
            days=days_per_ticker,
            force_refresh=False,
            stale_days=stale_days,
            max_workers=None  # OPT-5: Auto-detect
        )

        duration = time.time() - start_time

        # Calculate metrics
        tickers_processed = result.get('tickers_collected', 0) + result.get('tickers_skipped', 0)

        metrics = {
            'stale_days': stale_days,
            'days_per_ticker': days_per_ticker,
            'limit': limit,
            'stale_count_expected': stale_count,
            'duration_seconds': duration,
            'tickers_processed': tickers_processed,
            'tickers_collected': result.get('tickers_collected', 0),
            'tickers_skipped': result.get('tickers_skipped', 0),
            'tickers_failed': result.get('tickers_failed', 0),
            'records_inserted': result.get('records_inserted', 0),
            'records_updated': result.get('records_updated', 0),
            'throughput_tickers_per_sec': tickers_processed / duration if duration > 0 else 0,
            'throughput_records_per_sec': result.get('records_inserted', 0) / duration if duration > 0 else 0,
            'avg_time_per_ticker': duration / tickers_processed if tickers_processed > 0 else 0,
            'success_rate': result.get('tickers_collected', 0) / tickers_processed if tickers_processed > 0 else 0
        }

        # Print results
        logger.info("\n" + "="*80)
        logger.info("Realistic Benchmark Results")
        logger.info("="*80)
        logger.info(f"Duration: {metrics['duration_seconds']:.2f}s ({metrics['duration_seconds']/60:.2f} min)")
        logger.info(f"Tickers processed: {metrics['tickers_processed']:,}")
        logger.info(f"  - Collected: {metrics['tickers_collected']:,}")
        logger.info(f"  - Skipped: {metrics['tickers_skipped']:,}")
        logger.info(f"  - Failed: {metrics['tickers_failed']:,}")
        logger.info(f"Records inserted: {metrics['records_inserted']:,}")
        logger.info(f"Throughput: {metrics['throughput_tickers_per_sec']:.2f} tickers/s")
        logger.info(f"Avg time per ticker: {metrics['avg_time_per_ticker']:.2f}s")
        logger.info(f"Success rate: {metrics['success_rate']:.1%}")
        logger.info("="*80)

        return metrics

    def compare_with_baseline(self, metrics: dict) -> None:
        """Compare with Week 4 baseline"""
        logger.info("\n" + "="*80)
        logger.info("Comparison with Week 4 Baseline")
        logger.info("="*80)

        week4_baseline = 118  # seconds
        phase2_actual = metrics['duration_seconds']

        improvement = ((week4_baseline - phase2_actual) / week4_baseline) * 100

        logger.info(f"Week 4 Baseline: {week4_baseline}s (1.97 min)")
        logger.info(f"Phase 2 Actual:  {phase2_actual:.0f}s ({phase2_actual/60:.2f} min)")
        logger.info("")

        if phase2_actual < week4_baseline:
            logger.info(f"✅ IMPROVEMENT: {improvement:.1f}% faster!")
            logger.info(f"   Time saved: {week4_baseline - phase2_actual:.0f}s")
        elif phase2_actual > week4_baseline:
            logger.info(f"⚠️ SLOWER: {-improvement:.1f}% slower")
            logger.info(f"   Additional time: {phase2_actual - week4_baseline:.0f}s")
        else:
            logger.info(f"➖ SAME: No change")

        logger.info("")
        logger.info("Analysis:")
        logger.info(f"  - Stale tickers: {metrics['stale_count_expected']:,}")
        logger.info(f"  - Actually processed: {metrics['tickers_processed']:,}")
        logger.info(f"  - Days per ticker: {metrics['days_per_ticker']}")
        logger.info(f"  - Avg time/ticker: {metrics['avg_time_per_ticker']:.3f}s")
        logger.info("="*80)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Realistic Production Scenario Benchmark')
    parser.add_argument('--stale-days', type=int, default=1,
                       help='Stale threshold in days (default: 1)')
    parser.add_argument('--days', type=int, default=3,
                       help='Days to collect per ticker (default: 3)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of tickers (default: None)')
    parser.add_argument('--scenario', type=str, default='realistic',
                       choices=['realistic', 'week4-match'],
                       help='Benchmark scenario (default: realistic)')

    args = parser.parse_args()

    # Adjust parameters based on scenario
    if args.scenario == 'week4-match':
        logger.info("📊 Running Week 4 baseline matching scenario")
        logger.info("   (Attempting to reproduce Week 4 conditions)")
        # We don't know exact Week 4 conditions, so use reasonable estimates
        stale_days = 2
        days = 3
    else:
        stale_days = args.stale_days
        days = args.days

    benchmark = RealisticBenchmark()
    metrics = benchmark.run_realistic_benchmark(
        stale_days=stale_days,
        days_per_ticker=days,
        limit=args.limit
    )

    # Save results
    output_file = f'benchmark_realistic_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'scenario': args.scenario,
            'metrics': metrics
        }, f, indent=2)

    logger.info(f"\n📄 Results saved to: {output_file}")

    # Compare with Week 4 baseline
    benchmark.compare_with_baseline(metrics)


if __name__ == '__main__':
    main()
