#!/usr/bin/env python3
"""
Phase 1.5 - Day 2: pykrx Fundamental Data Backfill for KR Market

Complements DART data with market-based valuation ratios from pykrx.
Extracts: PER, PBR, EPS, BPS, DIV (dividend yield), DPS, Market Cap, Shares Outstanding

Target Coverage: >80% of KR market (1,091+ stocks out of 1,364)
Data Source: pykrx (KRX market data via unofficial API)

Usage:
    # Full backfill (all KR stocks)
    python3 scripts/backfill_fundamentals_pykrx_kr.py

    # Dry run (preview only)
    python3 scripts/backfill_fundamentals_pykrx_kr.py --dry-run

    # Incremental update (only missing/stale data)
    python3 scripts/backfill_fundamentals_pykrx_kr.py --incremental

    # Limit processing (for testing)
    python3 scripts/backfill_fundamentals_pykrx_kr.py --limit 10

    # Rate limiting (requests per second)
    python3 scripts/backfill_fundamentals_pykrx_kr.py --rate-limit 0.5  # 2 sec delay

Author: Quant Investment Platform - Phase 1.5
"""

import sys
import os
import argparse
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals_pykrx.log"
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


class PyKRXFundamentalBackfiller:
    """pykrx fundamental data backfill orchestrator"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False, rate_limit_delay: float = 1.0):
        """
        Initialize backfiller

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 1.0 = 1 req/sec)
        """
        self.db = db
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.last_api_call = 0

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped_no_data': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'records_updated': 0
        }

        # Check pykrx availability
        self._check_pykrx()

    def _check_pykrx(self):
        """Check if pykrx is installed and working"""
        try:
            from pykrx import stock
            self.pykrx_available = True
            logger.info("✅ pykrx library available")
        except ImportError:
            logger.error("❌ pykrx not installed. Install with: pip install pykrx>=1.0.51")
            self.pykrx_available = False
            sys.exit(1)

    def _rate_limit(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_api_call = time.time()

    def get_kr_tickers_for_backfill(self, incremental: bool = False, limit: Optional[int] = None) -> List[Dict]:
        """
        Query KR tickers that need fundamental data backfill

        Args:
            incremental: If True, only fetch tickers with no pykrx data in last 7 days
            limit: Maximum number of tickers to return (for testing)

        Returns:
            List of ticker dicts with ticker, name
        """
        if incremental:
            # Incremental: Only tickers with no pykrx data in last 7 days
            query = """
            SELECT DISTINCT t.ticker, t.name
            FROM tickers t
            LEFT JOIN ticker_fundamentals tf ON t.ticker = tf.ticker
                AND t.region = tf.region
                AND tf.date >= NOW() - INTERVAL '7 days'
                AND (tf.data_source = 'pykrx' OR tf.data_source LIKE 'DART+pykrx%')
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
              AND tf.id IS NULL  -- No recent pykrx data
            ORDER BY t.ticker
            """
        else:
            # Full backfill: All KR stocks
            query = """
            SELECT DISTINCT t.ticker, t.name
            FROM tickers t
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
            ORDER BY t.ticker
            """

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)
        tickers = [dict(row) for row in results]

        logger.info(f"📊 Found {len(tickers)} KR stocks for backfill")
        return tickers

    def fetch_pykrx_fundamental_data(self, ticker: str, target_date: Optional[str] = None) -> Optional[Dict]:
        """
        Fetch fundamental metrics from pykrx for a specific date

        Args:
            ticker: Stock ticker (e.g., '005930')
            target_date: Target date (YYYYMMDD), defaults to yesterday (market close)

        Returns:
            Dict with fundamental metrics or None on failure
        """
        from pykrx import stock

        try:
            # Use yesterday as default (today's data may not be available yet)
            if not target_date:
                yesterday = datetime.now() - timedelta(days=1)
                target_date = yesterday.strftime('%Y%m%d')

            # Rate limiting
            self._rate_limit()
            self.stats['api_calls'] += 1

            # Fetch fundamental data (PER, PBR, EPS, BPS, DIV, DPS)
            df_fundamental = stock.get_market_fundamental(target_date, target_date, ticker)

            if df_fundamental is None or df_fundamental.empty:
                logger.warning(f"⚠️ [{ticker}] No fundamental data for {target_date}")
                return None

            # Fetch market cap and shares outstanding
            self._rate_limit()
            self.stats['api_calls'] += 1

            df_cap = stock.get_market_cap(target_date, target_date, ticker)

            if df_cap is None or df_cap.empty:
                logger.warning(f"⚠️ [{ticker}] No market cap data for {target_date}")
                return None

            # Fetch OHLCV for closing price
            self._rate_limit()
            self.stats['api_calls'] += 1

            df_ohlcv = stock.get_market_ohlcv_by_date(target_date, target_date, ticker)

            if df_ohlcv is None or df_ohlcv.empty:
                logger.warning(f"⚠️ [{ticker}] No OHLCV data for {target_date}")
                return None

            # Extract data from DataFrames
            fundamental_row = df_fundamental.iloc[0]
            cap_row = df_cap.iloc[0]
            ohlcv_row = df_ohlcv.iloc[0]

            metrics = {
                'ticker': ticker,
                'date': pd.to_datetime(target_date, format='%Y%m%d').date(),
                'period_type': 'DAILY',
                'data_source': 'pykrx',

                # Valuation ratios
                'per': float(fundamental_row['PER']) if pd.notna(fundamental_row['PER']) else None,
                'pbr': float(fundamental_row['PBR']) if pd.notna(fundamental_row['PBR']) else None,
                'eps': float(fundamental_row['EPS']) if pd.notna(fundamental_row['EPS']) else None,
                'bps': float(fundamental_row['BPS']) if pd.notna(fundamental_row['BPS']) else None,

                # Dividend data
                'dividend_yield': float(fundamental_row['DIV']) if pd.notna(fundamental_row['DIV']) else None,
                'dividend_per_share': float(fundamental_row['DPS']) if pd.notna(fundamental_row['DPS']) else None,

                # Market cap data
                'market_cap': int(cap_row['시가총액']) if pd.notna(cap_row['시가총액']) else None,
                'shares_outstanding': int(cap_row['상장주식수']) if pd.notna(cap_row['상장주식수']) else None,
                'close_price': int(ohlcv_row['종가']) if pd.notna(ohlcv_row['종가']) else None,
            }

            logger.debug(f"✅ [{ticker}] pykrx data: PER={metrics['per']}, PBR={metrics['pbr']}, "
                        f"Div={metrics['dividend_yield']}%, Cap={metrics['market_cap']:,}")
            return metrics

        except Exception as e:
            logger.error(f"❌ [{ticker}] pykrx API call failed: {e}")
            return None

    def merge_with_existing_data(self, ticker: str, pykrx_data: Dict) -> Dict:
        """
        Merge pykrx data with existing DART data (if any)

        Args:
            ticker: Stock ticker
            pykrx_data: pykrx fundamental metrics

        Returns:
            Merged data dict with appropriate data_source tag
        """
        try:
            # Check if existing data exists for this ticker on the same date
            query = """
            SELECT data_source
            FROM ticker_fundamentals
            WHERE ticker = %s AND region = 'KR' AND date = %s AND period_type = 'DAILY'
            """
            params = (ticker, pykrx_data['date'])
            result = self.db.execute_query(query, params)

            if result and len(result) > 0:
                existing_row = result[0]
                existing_source = existing_row['data_source']

                # If DART data exists, merge and update data_source
                if existing_source and 'DART' in existing_source:
                    pykrx_data['data_source'] = 'DART+pykrx'
                    logger.debug(f"📊 [{ticker}] Merging pykrx with existing {existing_source} data")

            return pykrx_data

        except Exception as e:
            logger.warning(f"⚠️ [{ticker}] Failed to check existing data: {e}")
            return pykrx_data

    def insert_or_update_fundamental_data(self, ticker: str, data: Dict) -> bool:
        """
        Insert or update ticker_fundamentals record

        Args:
            ticker: Stock ticker
            data: Fundamental metrics (pykrx + optional DART data)

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert/update fundamental data for {ticker}")
            logger.info(f"  → Date: {data.get('date')}")
            logger.info(f"  → Data Source: {data.get('data_source')}")
            logger.info(f"  → PER: {data.get('per')}, PBR: {data.get('pbr')}, Div Yield: {data.get('dividend_yield')}%")
            logger.info(f"  → Market Cap: {data.get('market_cap'):,} KRW")
            return True

        try:
            # UPSERT query
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                shares_outstanding, market_cap, close_price,
                per, pbr, eps, bps,
                dividend_yield, dividend_per_share,
                data_source, created_at
            )
            VALUES (
                %(ticker)s, 'KR', %(date)s, %(period_type)s,
                %(shares_outstanding)s, %(market_cap)s, %(close_price)s,
                %(per)s, %(pbr)s, %(eps)s, %(bps)s,
                %(dividend_yield)s, %(dividend_per_share)s,
                %(data_source)s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                shares_outstanding = EXCLUDED.shares_outstanding,
                market_cap = EXCLUDED.market_cap,
                close_price = EXCLUDED.close_price,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                eps = EXCLUDED.eps,
                bps = EXCLUDED.bps,
                dividend_yield = EXCLUDED.dividend_yield,
                dividend_per_share = EXCLUDED.dividend_per_share,
                data_source = CASE
                    WHEN ticker_fundamentals.data_source LIKE 'DART%'
                        AND EXCLUDED.data_source = 'pykrx'
                    THEN 'DART+pykrx'  -- Merge DART + pykrx
                    WHEN ticker_fundamentals.data_source = 'pykrx'
                        AND EXCLUDED.data_source LIKE 'DART+pykrx%'
                    THEN EXCLUDED.data_source  -- Keep DART+pykrx
                    ELSE EXCLUDED.data_source
                END
            """

            # Prepare data dict
            insert_data = {
                'ticker': ticker,
                'date': data.get('date'),
                'period_type': data.get('period_type', 'DAILY'),
                'shares_outstanding': data.get('shares_outstanding'),
                'market_cap': data.get('market_cap'),
                'close_price': data.get('close_price'),
                'per': data.get('per'),
                'pbr': data.get('pbr'),
                'eps': data.get('eps'),
                'bps': data.get('bps'),
                'dividend_yield': data.get('dividend_yield'),
                'dividend_per_share': data.get('dividend_per_share'),
                'data_source': data.get('data_source')
            }

            self.db.execute_update(query, insert_data)

            # Determine if insert or update
            if self.db.cursor.rowcount > 0:
                if 'INSERT' in str(self.db.cursor.statusmessage):
                    self.stats['records_inserted'] += 1
                    logger.info(f"✅ [{ticker}] Inserted pykrx fundamental data")
                else:
                    self.stats['records_updated'] += 1
                    logger.info(f"✅ [{ticker}] Updated pykrx fundamental data")
                return True
            else:
                logger.warning(f"⚠️ [{ticker}] No rows affected")
                return False

        except Exception as e:
            logger.error(f"❌ [{ticker}] Database insert/update failed: {e}")
            return False

    def process_ticker(self, ticker_info: Dict, target_date: Optional[str] = None) -> bool:
        """
        Process single ticker: fetch pykrx data, merge with DART, insert to database

        Args:
            ticker_info: Dict with ticker, name
            target_date: Target date (YYYYMMDD), defaults to yesterday

        Returns:
            True if successful, False otherwise
        """
        ticker = ticker_info['ticker']
        name = ticker_info.get('name', 'Unknown')

        logger.info(f"{'='*60}")
        logger.info(f"Processing {ticker} ({name})")
        logger.info(f"{'='*60}")

        # Step 1: Fetch pykrx fundamental data
        pykrx_data = self.fetch_pykrx_fundamental_data(ticker, target_date)
        if not pykrx_data:
            self.stats['tickers_skipped_no_data'] += 1
            return False

        # Step 2: Merge with existing DART data (if any)
        merged_data = self.merge_with_existing_data(ticker, pykrx_data)

        # Step 3: Insert/update database
        success = self.insert_or_update_fundamental_data(ticker, merged_data)

        if success:
            self.stats['tickers_success'] += 1
            return True
        else:
            self.stats['tickers_failed'] += 1
            return False

    def run_backfill(self, incremental: bool = False, limit: Optional[int] = None,
                    target_date: Optional[str] = None) -> Dict:
        """
        Run full backfill process

        Args:
            incremental: If True, only fetch missing/stale data
            limit: Maximum tickers to process (for testing)
            target_date: Specific date to backfill (YYYYMMDD), defaults to yesterday

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        logger.info("="*80)
        logger.info("PHASE 1.5 - DAY 2: PYKRX FUNDAMENTAL DATA BACKFILL (KR MARKET)")
        logger.info("="*80)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Mode: {'INCREMENTAL' if incremental else 'FULL BACKFILL'}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Rate Limit: {self.rate_limit_delay} sec/request")
        logger.info(f"Target Date: {target_date or 'Yesterday (market close)'}")
        if limit:
            logger.info(f"Limit: {limit} tickers")
        logger.info("="*80)

        # Get tickers for backfill
        tickers = self.get_kr_tickers_for_backfill(incremental=incremental, limit=limit)

        if not tickers:
            logger.warning("⚠️ No tickers to process")
            return self.stats

        logger.info(f"\n📊 Processing {len(tickers)} tickers...")

        # Process each ticker
        for idx, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            self.stats['tickers_processed'] += 1

            logger.info(f"\n[{idx}/{len(tickers)}] Processing {ticker}...")

            try:
                self.process_ticker(ticker_info, target_date)

            except Exception as e:
                logger.error(f"❌ [{ticker}] Unexpected error: {e}")
                self.stats['tickers_failed'] += 1
                continue

        # Final statistics
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETED")
        logger.info("="*80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")
        logger.info(f"\nStatistics:")
        logger.info(f"  Tickers Processed: {self.stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']}")
        logger.info(f"  ⚠️ Skipped (No Data): {self.stats['tickers_skipped_no_data']}")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']}")
        logger.info(f"\nDatabase Operations:")
        logger.info(f"  Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"  Records Updated: {self.stats['records_updated']}")
        logger.info(f"\nAPI Metrics:")
        logger.info(f"  Total API Calls: {self.stats['api_calls']}")
        logger.info(f"  Avg Time per Call: {duration.total_seconds() / max(self.stats['api_calls'], 1):.2f} sec")
        logger.info("="*80)

        # Calculate coverage
        self._print_coverage_report()

        return self.stats

    def _print_coverage_report(self):
        """Print data coverage report"""
        try:
            query = """
            SELECT
                COUNT(DISTINCT ticker) as tickers_with_data,
                (SELECT COUNT(*) FROM tickers WHERE region = 'KR' AND asset_type = 'STOCK' AND is_active = TRUE) as total_tickers,
                ROUND(COUNT(DISTINCT ticker)::numeric /
                      (SELECT COUNT(*) FROM tickers WHERE region = 'KR' AND asset_type = 'STOCK' AND is_active = TRUE) * 100, 2) as coverage_pct,
                COUNT(CASE WHEN data_source LIKE 'DART+pykrx%' THEN 1 END) as merged_records,
                COUNT(CASE WHEN data_source = 'pykrx' THEN 1 END) as pykrx_only_records
            FROM ticker_fundamentals
            WHERE region = 'KR' AND date >= NOW() - INTERVAL '7 days'
            """

            result = self.db.execute_query(query)

            if result:
                row = result[0]
                logger.info(f"\n📊 KR Market Coverage:")
                logger.info(f"  Tickers with Data: {row['tickers_with_data']}")
                logger.info(f"  Total Tickers: {row['total_tickers']}")
                logger.info(f"  Coverage: {row['coverage_pct']}%")
                logger.info(f"  DART+pykrx Merged: {row['merged_records']}")
                logger.info(f"  pykrx Only: {row['pykrx_only_records']}")

                target_coverage = 80.0
                if row['coverage_pct'] >= target_coverage:
                    logger.info(f"  ✅ Target coverage (>{target_coverage}%) ACHIEVED")
                else:
                    logger.info(f"  ⚠️ Target coverage (>{target_coverage}%) NOT YET ACHIEVED")
                    logger.info(f"  → Need {int(row['total_tickers'] * target_coverage / 100) - row['tickers_with_data']} more tickers")

        except Exception as e:
            logger.error(f"Failed to generate coverage report: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='pykrx Fundamental Data Backfill (Phase 1.5 - Day 2)')
    parser.add_argument('--dry-run', action='store_true', help='Preview operations without database writes')
    parser.add_argument('--incremental', action='store_true', help='Only fetch missing/stale data (last 7 days)')
    parser.add_argument('--limit', type=int, help='Limit number of tickers (for testing)')
    parser.add_argument('--rate-limit', type=float, default=1.0, help='Delay between API calls in seconds (default: 1.0)')
    parser.add_argument('--date', type=str, help='Target date (YYYYMMDD), defaults to yesterday')

    args = parser.parse_args()

    try:
        # Initialize database
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")

        # Run backfill
        backfiller = PyKRXFundamentalBackfiller(
            db=db,
            dry_run=args.dry_run,
            rate_limit_delay=args.rate_limit
        )

        stats = backfiller.run_backfill(
            incremental=args.incremental,
            limit=args.limit,
            target_date=args.date
        )

        # Exit code based on success rate
        success_rate = stats['tickers_success'] / max(stats['tickers_processed'], 1) * 100
        if success_rate >= 70:
            logger.info(f"✅ Backfill completed successfully (success rate: {success_rate:.1f}%)")
            sys.exit(0)
        else:
            logger.warning(f"⚠️ Backfill completed with low success rate: {success_rate:.1f}%")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⚠️ Backfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
