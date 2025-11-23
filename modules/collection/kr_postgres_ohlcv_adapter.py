#!/usr/bin/env python3
"""
KR PostgreSQL OHLCV Adapter

Direct PostgreSQL integration for KR market OHLCV data collection.
Eliminates SQLite dependency by storing data directly in PostgreSQL.

Features:
- KIS API integration for KR stock data
- Direct PostgreSQL storage (batch upsert)
- Incremental update support
- Rate limiting and retry logic
- Data validation
- Progress tracking and statistics

Author: Quant Investment Platform
Date: 2025-11-16
Phase: 1.1 - Critical Fixes
"""

import sys
import os
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
import pandas as pd
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.kis_data_collector import KISDataCollector
from modules.orchestration.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class KRPostgresOHLCVAdapter:
    """
    Direct PostgreSQL OHLCV adapter for KR market

    Architecture:
        KIS API → Adapter → PostgreSQL (direct insert)

    Replaces:
        KIS API → KISDataCollector → SQLite → ❌ No migration

    Usage:
        adapter = KRPostgresOHLCVAdapter(db, config)
        result = adapter.run_collection(incremental=True, limit=None)
    """

    def __init__(self, db: PostgresDatabaseManager, config: Dict = None):
        """
        Initialize KR PostgreSQL OHLCV Adapter

        Args:
            db: PostgreSQL database manager
            config: Configuration dict with optional settings:
                - dry_run: bool - Preview mode, no DB writes
                - rate_limit: float - Seconds between API calls
                - batch_size: int - Records per batch insert
                - validation_threshold: float - Min data quality (0.0-1.0)
        """
        self.db = db
        self.config = config or {}
        self.dry_run = self.config.get('dry_run', False)
        self.rate_limit = self.config.get('rate_limit', 0.05)  # 20 req/s
        self.batch_size = self.config.get('batch_size', 1000)
        self.validation_threshold = self.config.get('validation_threshold', 0.7)

        # Statistics
        self.stats = {
            'tickers_queried': 0,
            'tickers_collected': 0,
            'tickers_skipped': 0,
            'tickers_failed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'errors': 0,
            'duration': 0.0,
            'success': False
        }

        # Initialize KIS data collector (for API access only)
        self.kis_collector = KISDataCollector(region='KR')

        # Korean timezone
        self.kst = pytz.timezone('Asia/Seoul')

        # Week 4 QW2: Initialize TokenBucketRateLimiter
        if self.rate_limit > 0:
            max_rate = int(1 / self.rate_limit)  # Convert delay to rate (e.g., 0.05s -> 20 req/s)
            self.rate_limiter = TokenBucketRateLimiter(
                max_rate=max_rate,
                time_window=1.0,
                name="KIS_API"
            )
            logger.info(f"✅ TokenBucketRateLimiter initialized ({max_rate} req/s)")
        else:
            self.rate_limiter = None

        logger.info(f"✅ KRPostgresOHLCVAdapter initialized")
        logger.info(f"   Database: PostgreSQL ({self.db.database})")
        logger.info(f"   Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"   Rate limit: {self.rate_limit}s ({1/self.rate_limit:.0f} req/s)")
        logger.info(f"   Batch size: {self.batch_size} records")

    def _get_active_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get active KR tickers from PostgreSQL

        Args:
            limit: Optional limit on number of tickers

        Returns:
            List of ticker codes
        """
        query = """
        SELECT ticker
        FROM tickers
        WHERE region = 'KR'
          AND is_active = TRUE
          AND asset_type IN ('STOCK', 'ETF')
        ORDER BY ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = self.db.execute_query(query)
        tickers = [row['ticker'] for row in rows] if rows else []

        self.stats['tickers_queried'] = len(tickers)
        logger.info(f"📋 Retrieved {len(tickers)} active KR tickers from PostgreSQL")

        return tickers

    def _get_tickers_needing_update(self, incremental: bool = True, limit: Optional[int] = None,
                                     force_refresh: bool = False, stale_days: int = 2) -> List[str]:
        """
        Get tickers that need OHLCV updates with smart date filtering

        Args:
            incremental: If True, only return tickers with stale/missing data
            limit: Optional limit on number of tickers
            force_refresh: If True, update all tickers (ignores recency)
            stale_days: Consider data stale if older than this many days (default: 2)

        Returns:
            List of ticker codes to update

        Logic:
        - No data: Full backfill needed
        - Data older than stale_days: Incremental update needed
        - Recent data: Skip (unless force_refresh)
        - force_refresh: Update all tickers regardless of freshness
        """
        if not incremental:
            # Full refresh - return all active tickers
            return self._get_active_tickers(limit=limit)

        # Smart incremental - identify tickers needing updates
        # 1. Tickers with no OHLCV data at all
        # 2. Tickers with stale data (older than stale_days)
        # 3. force_refresh: all tickers (for corrections)

        if force_refresh:
            logger.info(f"🔄 Force refresh mode: updating all tickers")
            return self._get_active_tickers(limit=limit)

        query = """
        WITH latest_data AS (
            SELECT
                ticker,
                MAX(date) as last_date
            FROM ohlcv_data
            WHERE region = 'KR'
            GROUP BY ticker
        )
        SELECT
            t.ticker,
            CASE WHEN ld.last_date IS NULL THEN 0 ELSE 1 END as has_data,
            ld.last_date
        FROM tickers t
        LEFT JOIN latest_data ld ON t.ticker = ld.ticker
        WHERE t.region = 'KR'
          AND t.is_active = TRUE
          AND t.asset_type IN ('STOCK', 'ETF')
          AND (
              ld.last_date IS NULL  -- No data at all
              OR ld.last_date < CURRENT_DATE - INTERVAL '%s days'  -- Stale data
          )
        ORDER BY
            has_data ASC,  -- No data first (0 before 1)
            ld.last_date ASC NULLS FIRST  -- Oldest data next
        """

        if limit:
            query += f" LIMIT {limit}"

        rows = self.db.execute_query(query % stale_days)
        tickers = [row['ticker'] for row in rows] if rows else []

        # Count categories for logging
        no_data_query = """
        SELECT COUNT(DISTINCT t.ticker) as count
        FROM tickers t
        LEFT JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
        WHERE t.region = 'KR'
          AND t.is_active = TRUE
          AND t.asset_type IN ('STOCK', 'ETF')
          AND o.ticker IS NULL
        """
        no_data_count = self.db.execute_query(no_data_query)[0]['count'] if self.db.execute_query(no_data_query) else 0

        stale_data_query = """
        WITH latest_data AS (
            SELECT ticker, MAX(date) as last_date
            FROM ohlcv_data
            WHERE region = 'KR'
            GROUP BY ticker
        )
        SELECT COUNT(DISTINCT t.ticker) as count
        FROM tickers t
        INNER JOIN latest_data ld ON t.ticker = ld.ticker
        WHERE t.region = 'KR'
          AND t.is_active = TRUE
          AND t.asset_type IN ('STOCK', 'ETF')
          AND ld.last_date < CURRENT_DATE - INTERVAL '%s days'
        """
        stale_count = self.db.execute_query(stale_data_query % stale_days)[0]['count'] if self.db.execute_query(stale_data_query % stale_days) else 0

        logger.info(f"📋 Found {len(tickers)} KR tickers needing update (incremental mode)")
        logger.info(f"   - No data: {no_data_count} tickers")
        logger.info(f"   - Stale data (>{stale_days} days): {stale_count} tickers")
        logger.info(f"   - Total to update: {len(tickers)}")

        return tickers

    def _fetch_ohlcv_from_kis(self, ticker: str, days: int = 250) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from KIS API

        Args:
            ticker: Stock code (e.g., '005930')
            days: Number of days to fetch

        Returns:
            DataFrame with columns: open, high, low, close, volume, index=date
            None if fetch failed
        """
        try:
            df = self.kis_collector.safe_get_ohlcv(
                ticker=ticker,
                count=days,
                timeframe='D'
            )

            if df is None or df.empty:
                logger.warning(f"⚠️ {ticker}: No data returned from KIS API")
                return None

            # Validate data quality
            if len(df) < days * self.validation_threshold:
                logger.warning(
                    f"⚠️ {ticker}: Insufficient data ({len(df)}/{days} rows, "
                    f"threshold: {self.validation_threshold * 100:.0f}%)"
                )

            return df

        except Exception as e:
            logger.error(f"❌ {ticker}: KIS API fetch failed: {e}")
            return None

    def _prepare_batch_for_postgres(self, ticker: str, df: pd.DataFrame) -> List[tuple]:
        """
        Prepare OHLCV DataFrame for PostgreSQL batch insert

        Args:
            ticker: Stock code
            df: OHLCV DataFrame (index=date, columns=open/high/low/close/volume)

        Returns:
            List of tuples ready for executemany()
        """
        batch = []

        for date_idx, row in df.iterrows():
            # Convert pandas Timestamp to Python date
            if isinstance(date_idx, pd.Timestamp):
                trade_date = date_idx.date()
            else:
                trade_date = date_idx

            record = (
                ticker,                          # ticker
                'KR',                            # region
                trade_date,                      # date
                Decimal(str(row['open'])),       # open
                Decimal(str(row['high'])),       # high
                Decimal(str(row['low'])),        # low
                Decimal(str(row['close'])),      # close
                int(row['volume']),              # volume
                '1d'                             # timeframe
            )
            batch.append(record)

        return batch

    def _insert_batch_to_postgres(self, batch: List[tuple]) -> Dict[str, int]:
        """
        Insert OHLCV batch to PostgreSQL with upsert logic

        Args:
            batch: List of tuples (ticker, region, date, open, high, low, close, volume, timeframe)

        Returns:
            Dict with insert/update counts
        """
        if not batch:
            return {'inserted': 0, 'updated': 0}

        if self.dry_run:
            logger.info(f"🔍 DRY RUN: Would insert {len(batch)} records to PostgreSQL")
            return {'inserted': len(batch), 'updated': 0}

        # Upsert query
        upsert_query = """
        INSERT INTO ohlcv_data (ticker, region, date, open, high, low, close, volume, timeframe)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, timeframe)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            last_updated = CURRENT_TIMESTAMP
        """

        try:
            # Execute batch using connection pool
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(upsert_query, batch)
                rows_affected = cursor.rowcount
                conn.commit()

                # Estimate inserts vs updates (approximate)
                # executemany doesn't distinguish, so we estimate based on total rows
                inserted = rows_affected
                updated = 0  # Can't distinguish without individual row inspection

                logger.debug(f"✅ Batch insert: {rows_affected} rows affected")

                return {'inserted': inserted, 'updated': updated}

        except Exception as e:
            logger.error(f"❌ Batch insert failed: {e}")
            raise

    def collect_ticker(self, ticker: str, days: int = 250) -> bool:
        """
        Collect OHLCV data for a single ticker

        Args:
            ticker: Stock code
            days: Number of days to collect

        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch from KIS API
            df = self._fetch_ohlcv_from_kis(ticker, days=days)

            if df is None or df.empty:
                self.stats['tickers_skipped'] += 1
                return False

            # Prepare batch
            batch = self._prepare_batch_for_postgres(ticker, df)

            if not batch:
                self.stats['tickers_skipped'] += 1
                return False

            # Insert to PostgreSQL
            result = self._insert_batch_to_postgres(batch)

            self.stats['records_inserted'] += result['inserted']
            self.stats['records_updated'] += result['updated']
            self.stats['tickers_collected'] += 1

            logger.debug(
                f"✅ {ticker}: {len(batch)} records "
                f"(inserted: {result['inserted']}, updated: {result['updated']})"
            )

            return True

        except Exception as e:
            self.stats['tickers_failed'] += 1
            self.stats['errors'] += 1
            logger.error(f"❌ {ticker}: Collection failed: {e}")
            return False

    def run_collection(self, incremental: bool = True, limit: Optional[int] = None, days: int = 250,
                      force_refresh: bool = False, stale_days: int = 2) -> Dict:
        """
        Run OHLCV collection workflow with smart incremental updates

        Args:
            incremental: If True, only update tickers with stale data
            limit: Optional limit on number of tickers
            days: Number of days to collect per ticker
            force_refresh: If True, update all tickers regardless of freshness
            stale_days: Consider data stale if older than this many days (default: 2)

        Returns:
            Statistics dictionary
        """
        mode_str = 'FORCE REFRESH' if force_refresh else ('INCREMENTAL' if incremental else 'FULL REFRESH')
        logger.info("="*80)
        logger.info("KR PostgreSQL OHLCV Collection")
        logger.info("="*80)
        logger.info(f"Mode: {mode_str}")
        if incremental and not force_refresh:
            logger.info(f"Stale threshold: >{stale_days} days")
        logger.info(f"Limit: {limit if limit else 'None'}")
        logger.info(f"Days per ticker: {days}")
        logger.info("="*80)

        start_time = time.time()

        try:
            # Get tickers to update
            if incremental:
                tickers = self._get_tickers_needing_update(
                    incremental=True,
                    limit=limit,
                    force_refresh=force_refresh,
                    stale_days=stale_days
                )
            else:
                tickers = self._get_active_tickers(limit=limit)

            if not tickers:
                logger.warning("⚠️ No tickers to update")
                self.stats['success'] = True
                self.stats['duration'] = time.time() - start_time
                return self.stats

            logger.info(f"📊 Processing {len(tickers)} tickers...")

            # Process each ticker
            for idx, ticker in enumerate(tickers, 1):
                # Progress logging
                if idx % 100 == 0:
                    logger.info(f"Progress: {idx}/{len(tickers)} tickers ({idx/len(tickers)*100:.1f}%)")

                # Collect ticker data
                self.collect_ticker(ticker, days=days)

                # Week 4 QW2: Intelligent rate limiting (replaces fixed sleep)
                if self.rate_limiter:
                    self.rate_limiter.wait_if_needed()

            # Mark as successful
            self.stats['success'] = True

        except Exception as e:
            logger.error(f"❌ Collection failed: {e}")
            self.stats['success'] = False
            self.stats['errors'] += 1

        finally:
            # Calculate duration
            self.stats['duration'] = time.time() - start_time

            # Print summary
            logger.info("="*80)
            logger.info("Collection Summary")
            logger.info("="*80)
            logger.info(f"Duration: {self.stats['duration']:.2f}s")
            logger.info(f"Tickers queried: {self.stats['tickers_queried']}")
            logger.info(f"Tickers collected: {self.stats['tickers_collected']}")
            logger.info(f"Tickers skipped: {self.stats['tickers_skipped']}")
            logger.info(f"Tickers failed: {self.stats['tickers_failed']}")
            logger.info(f"Records inserted: {self.stats['records_inserted']}")
            logger.info(f"Records updated: {self.stats['records_updated']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info(f"Success: {'✅ YES' if self.stats['success'] else '❌ NO'}")
            logger.info("="*80)

        return self.stats


def main():
    """CLI entry point for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='KR PostgreSQL OHLCV Collector')
    parser.add_argument('--dry-run', action='store_true', help='Preview mode')
    parser.add_argument('--incremental', action='store_true', help='Only update stale data')
    parser.add_argument('--limit', type=int, help='Limit number of tickers')
    parser.add_argument('--days', type=int, default=250, help='Days to collect per ticker')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Initialize database
    db = PostgresDatabaseManager()

    # Run collection
    adapter = KRPostgresOHLCVAdapter(
        db=db,
        config={'dry_run': args.dry_run}
    )

    result = adapter.run_collection(
        incremental=args.incremental,
        limit=args.limit,
        days=args.days
    )

    # Exit with status code
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
