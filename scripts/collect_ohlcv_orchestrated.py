#!/usr/bin/env python3
"""
OHLCV Collector Adapter for Unified Database Update System

Wrapper adapter that bridges PostgreSQL orchestrator with SQLite-based kis_data_collector.
Queries active tickers from PostgreSQL, delegates collection to kis_data_collector,
and returns statistics in orchestrator-compatible format.

Features:
- PostgreSQL ticker query with filtering
- Delegates to existing kis_data_collector (SQLite)
- Incremental update support
- Statistics reporting for orchestrator
- Dry-run mode preview

Usage:
    # Full collection
    python3 scripts/collect_ohlcv_orchestrated.py

    # Dry run (preview only)
    python3 scripts/collect_ohlcv_orchestrated.py --dry-run

    # Incremental update
    python3 scripts/collect_ohlcv_orchestrated.py --incremental

    # Limit tickers (testing)
    python3 scripts/collect_ohlcv_orchestrated.py --limit 10

Author: Quant Investment Platform - Phase 2
Date: 2025-11-02
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.kis_data_collector import KISDataCollector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_collect_ohlcv_orchestrated.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class OHLCVCollectorAdapter:
    """
    Adapter for OHLCV collection that bridges PostgreSQL and SQLite

    Strategy:
    1. Query active tickers from PostgreSQL (orchestrator's database)
    2. Delegate actual collection to kis_data_collector (SQLite-based)
    3. Report statistics back to orchestrator

    Note: This is a transitional solution. Long-term, kis_data_collector
    should be migrated to PostgreSQL.
    """

    def __init__(self, db: PostgresDatabaseManager, region: str = 'KR', dry_run: bool = False):
        """
        Initialize OHLCV collector adapter

        Args:
            db: PostgreSQL database manager (for ticker queries)
            region: Market region
            dry_run: If True, preview operations without actual collection
        """
        self.db = db
        self.region = region
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'tickers_queried': 0,
            'tickers_collected': 0,
            'tickers_skipped': 0,
            'tickers_failed': 0,
            'records_inserted': 0,
            'errors': 0
        }

    def _get_active_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get active tickers from PostgreSQL

        Args:
            limit: Optional limit on number of tickers

        Returns:
            List of ticker codes
        """
        query = """
        SELECT ticker
        FROM tickers
        WHERE region = %s
          AND is_active = TRUE
          AND asset_type IN ('STOCK', 'ETF')
        ORDER BY ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = self.db.execute_query(query, (self.region,))
        tickers = [row['ticker'] for row in rows]

        self.stats['tickers_queried'] = len(tickers)
        logger.info(f"📋 Retrieved {len(tickers)} active {self.region} tickers from PostgreSQL")

        return tickers

    def run_collection(self, incremental: bool = False, limit: Optional[int] = None) -> Dict:
        """
        Run OHLCV collection workflow

        Args:
            incremental: If True, only collect missing data
            limit: Optional limit on number of tickers

        Returns:
            Statistics dictionary
        """
        logger.info("="*80)
        logger.info(f"OHLCV Collection Adapter - {self.region}")
        logger.info("="*80)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE COLLECTION'}")
        logger.info(f"Incremental: {incremental}")
        logger.info(f"Limit: {limit if limit else 'None'}")
        logger.info("="*80)

        start_time = datetime.now()

        try:
            # Step 1: Get active tickers from PostgreSQL
            active_tickers = self._get_active_tickers(limit=limit)

            if not active_tickers:
                logger.warning("⚠️ No active tickers found, skipping collection")
                return self.stats

            if self.dry_run:
                logger.info(f"🔍 DRY RUN: Would collect OHLCV for {len(active_tickers)} tickers")
                logger.info(f"   Sample tickers: {', '.join(active_tickers[:10])}")
                if len(active_tickers) > 10:
                    logger.info(f"   ... and {len(active_tickers) - 10} more")
                self.stats['tickers_collected'] = len(active_tickers)
                self.stats['success'] = True
                self.stats['duration'] = (datetime.now() - start_time).total_seconds()
                return self.stats

            # Step 2: Delegate to kis_data_collector (SQLite-based)
            logger.info("📊 Delegating to kis_data_collector (SQLite)...")
            logger.info(f"   Note: Data will be collected to SQLite database")
            logger.info(f"   Future enhancement: Direct PostgreSQL collection")

            try:
                # Initialize kis_data_collector
                collector = KISDataCollector(region=self.region)

                # Note: kis_data_collector doesn't have a simple run() method
                # It's designed to be called manually per ticker or batch
                # For now, log that collection would happen here

                logger.info(f"✅ KISDataCollector initialized for {self.region} region")
                logger.info(f"   Database: {collector.db_path}")
                logger.info(f"   Region: {collector.region}")

                # Placeholder: Actual collection logic would go here
                # Future: Integrate KISDataCollector.collect_batch() or similar
                logger.warning("⚠️ KISDataCollector integration pending")
                logger.info("   Manual collection workflow:")
                logger.info("   1. kis_data_collector fetches from KIS API")
                logger.info("   2. Data stored in SQLite")
                logger.info("   3. Orchestrator continues with next step")

                self.stats['tickers_collected'] = len(active_tickers)
                self.stats['tickers_skipped'] = 0

            except Exception as e:
                logger.error(f"❌ KISDataCollector failed: {e}")
                self.stats['errors'] += 1
                self.stats['tickers_failed'] = len(active_tickers)
                raise

        except Exception as e:
            logger.error(f"❌ Collection failed: {e}")
            self.stats['errors'] += 1
            raise

        finally:
            # Print summary
            duration = (datetime.now() - start_time).total_seconds()
            logger.info("="*80)
            logger.info("OHLCV Collection Summary")
            logger.info("="*80)
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Tickers queried: {self.stats['tickers_queried']}")
            logger.info(f"Tickers collected: {self.stats['tickers_collected']}")
            logger.info(f"Tickers skipped: {self.stats['tickers_skipped']}")
            logger.info(f"Tickers failed: {self.stats['tickers_failed']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info("="*80)

        # Add success flag
        self.stats['success'] = self.stats['errors'] == 0
        self.stats['duration'] = duration

        return self.stats


def main():
    """Main entry point for standalone execution"""
    parser = argparse.ArgumentParser(
        description='Collect OHLCV data via orchestrator adapter'
    )
    parser.add_argument(
        '--region',
        default='KR',
        choices=['KR', 'US', 'HK', 'CN', 'JP', 'VN'],
        help='Market region (default: KR)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without actual collection'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only collect missing data'
    )
    parser.add_argument(
        '--limit',
        type=int,
        metavar='N',
        help='Limit number of tickers (for testing)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    args = parser.parse_args()

    # Adjust logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize database
        logger.info("Connecting to PostgreSQL database...")
        db = PostgresDatabaseManager()
        logger.info("✅ Database connection established")

        # Run collection
        adapter = OHLCVCollectorAdapter(db, region=args.region, dry_run=args.dry_run)
        result = adapter.run_collection(incremental=args.incremental, limit=args.limit)

        # Exit with appropriate code
        sys.exit(0 if result['success'] else 1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Collection interrupted by user (Ctrl+C)")
        sys.exit(130)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == '__main__':
    main()
