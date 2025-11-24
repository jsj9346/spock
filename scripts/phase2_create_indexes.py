#!/usr/bin/env python3
"""
Phase 2 OPT-6: PostgreSQL Index Optimization

Creates optimized composite indexes for common query patterns.

Usage:
    python3 scripts/phase2_create_indexes.py --analyze
    python3 scripts/phase2_create_indexes.py --create
    python3 scripts/phase2_create_indexes.py --verify

Author: Quant Investment Platform
Date: 2025-11-23
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndexOptimizer:
    """PostgreSQL index optimizer for OHLCV data"""

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db

    def analyze_current_indexes(self) -> None:
        """Analyze current index status"""
        logger.info("="*80)
        logger.info("Step 1: Analyzing Current Indexes")
        logger.info("="*80)

        # Get current indexes
        query = """
        SELECT
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = 'ohlcv_data'
        ORDER BY indexname
        """

        indexes = self.db.execute_query(query)

        if indexes:
            logger.info(f"Found {len(indexes)} existing indexes:")
            for idx in indexes:
                logger.info(f"  - {idx['indexname']}")
                logger.info(f"    {idx['indexdef']}")
        else:
            logger.info("No indexes found on ohlcv_data table")

        # Get table statistics
        stats_query = """
        SELECT
            schemaname,
            tablename,
            attname,
            n_distinct,
            correlation
        FROM pg_stats
        WHERE tablename = 'ohlcv_data'
        ORDER BY attname
        """

        stats = self.db.execute_query(stats_query)

        if stats:
            logger.info(f"\nTable statistics ({len(stats)} columns):")
            for stat in stats[:5]:  # Show first 5
                logger.info(
                    f"  - {stat['attname']}: n_distinct={stat['n_distinct']}, "
                    f"correlation={stat['correlation']:.4f}"
                )

    def create_optimized_indexes(self) -> None:
        """Create optimized composite indexes"""
        logger.info("\n" + "="*80)
        logger.info("Step 2: Creating Optimized Indexes")
        logger.info("="*80)

        indexes_to_create = [
            {
                'name': 'idx_ohlcv_ticker_region_date',
                'description': 'Ticker + Region + Date (time-series queries)',
                'sql': """
                CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_region_date
                ON ohlcv_data (ticker, region, date DESC)
                WHERE region = 'KR'
                """
            },
            {
                'name': 'idx_ohlcv_region_date',
                'description': 'Region + Date (cross-ticker analysis)',
                'sql': """
                CREATE INDEX IF NOT EXISTS idx_ohlcv_region_date
                ON ohlcv_data (region, date DESC)
                """
            },
            {
                'name': 'idx_ohlcv_ticker_region_latest',
                'description': 'Ticker + Region + Latest Date (staleness checks)',
                'sql': """
                CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_region_latest
                ON ohlcv_data (ticker, region, date DESC)
                INCLUDE (close, volume)
                """
            },
            {
                'name': 'idx_ohlcv_recent_data',
                'description': 'Partial index for recent data (since 2023-01-01)',
                'sql': """
                CREATE INDEX IF NOT EXISTS idx_ohlcv_recent_data
                ON ohlcv_data (ticker, date DESC)
                WHERE region = 'KR' AND date >= '2023-01-01'
                """
            }
        ]

        for idx_info in indexes_to_create:
            logger.info(f"\n▶ Creating {idx_info['name']}...")
            logger.info(f"  Purpose: {idx_info['description']}")

            try:
                start_time = datetime.now()
                self.db.execute_update(idx_info['sql'])
                duration = (datetime.now() - start_time).total_seconds()

                logger.info(f"  ✅ Created in {duration:.2f}s")

            except Exception as e:
                logger.error(f"  ❌ Failed: {e}")

        # Run ANALYZE to update statistics
        logger.info("\n▶ Running ANALYZE to update statistics...")
        try:
            self.db.execute_update("ANALYZE ohlcv_data")
            logger.info("  ✅ ANALYZE completed")
        except Exception as e:
            logger.error(f"  ❌ ANALYZE failed: {e}")

    def verify_indexes(self) -> None:
        """Verify index creation and show sizes"""
        logger.info("\n" + "="*80)
        logger.info("Step 3: Verifying Indexes")
        logger.info("="*80)

        # Get index sizes
        query = """
        SELECT
            indexrelname AS indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public' AND relname = 'ohlcv_data'
        ORDER BY pg_relation_size(indexrelid) DESC
        """

        indexes = self.db.execute_query(query)

        if indexes:
            logger.info(f"Index sizes and usage:")
            for idx in indexes:
                logger.info(
                    f"  - {idx['indexname']}: {idx['index_size']} "
                    f"(scans: {idx['idx_scan']}, reads: {idx['idx_tup_read']})"
                )
        else:
            logger.info("No indexes found")

    def test_query_performance(self) -> None:
        """Test query performance with EXPLAIN ANALYZE"""
        logger.info("\n" + "="*80)
        logger.info("Step 4: Testing Query Performance")
        logger.info("="*80)

        test_queries = [
            {
                'name': 'Single ticker time-series',
                'expected_index': 'idx_ohlcv_ticker_region_date',
                'sql': """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = '005930'
                  AND region = 'KR'
                  AND date >= '2024-01-01'
                  AND date <= '2024-12-31'
                ORDER BY date DESC
                """
            },
            {
                'name': 'Market-wide snapshot',
                'expected_index': 'idx_ohlcv_region_date',
                'sql': """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT ticker, close, volume
                FROM ohlcv_data
                WHERE region = 'KR'
                  AND date = '2024-11-22'
                ORDER BY ticker
                LIMIT 100
                """
            },
            {
                'name': 'Latest date lookup',
                'expected_index': 'idx_ohlcv_ticker_region_latest',
                'sql': """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT ticker, MAX(date) as last_date
                FROM ohlcv_data
                WHERE region = 'KR'
                GROUP BY ticker
                LIMIT 100
                """
            }
        ]

        for test in test_queries:
            logger.info(f"\n▶ Testing: {test['name']}")
            logger.info(f"  Expected index: {test['expected_index']}")

            try:
                result = self.db.execute_query(test['sql'])

                # Extract execution time from EXPLAIN output
                for row in result:
                    plan_line = row.get('QUERY PLAN', '')
                    if 'Execution Time:' in plan_line:
                        logger.info(f"  {plan_line}")
                    elif 'Index Scan' in plan_line or 'Index Only Scan' in plan_line:
                        logger.info(f"  ✅ {plan_line}")

            except Exception as e:
                logger.error(f"  ❌ Failed: {e}")


def main():
    parser = argparse.ArgumentParser(description='PostgreSQL Index Optimizer (Phase 2 OPT-6)')
    parser.add_argument('--analyze', action='store_true', help='Analyze current indexes')
    parser.add_argument('--create', action='store_true', help='Create optimized indexes')
    parser.add_argument('--verify', action='store_true', help='Verify index creation')
    parser.add_argument('--test', action='store_true', help='Test query performance')
    parser.add_argument('--all', action='store_true', help='Run all steps')

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager()
    optimizer = IndexOptimizer(db)

    # Run requested operations
    if args.all or args.analyze:
        optimizer.analyze_current_indexes()

    if args.all or args.create:
        optimizer.create_optimized_indexes()

    if args.all or args.verify:
        optimizer.verify_indexes()

    if args.all or args.test:
        optimizer.test_query_performance()

    logger.info("\n" + "="*80)
    logger.info("Index Optimization Complete")
    logger.info("="*80)


if __name__ == '__main__':
    main()
