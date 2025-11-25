#!/usr/bin/env python3
"""
backfill_orphaned_tickers.py - Backfill Ticker Metadata for Orphaned OHLCV Records

This script identifies OHLCV records without ticker registry entries and backfills
the missing metadata using KIS API (primary) and pykrx (fallback).

Priority Tickers (from Week 4 investigation report):
41 high-priority orphaned tickers identified in WEEK4_PRICE_ANOMALY_INVESTIGATION.md

Usage:
    python3 scripts/backfill_orphaned_tickers.py [--dry-run] [--limit N] [--validate]
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import signal
from datetime import date, datetime
from typing import List, Dict, Optional
from loguru import logger
from pykrx import stock

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient

# Timeout handler
class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Operation timed out")

# Configure logger
logger.remove()
logger.add(
    f"log/backfill_orphaned_tickers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)
logger.add(sys.stdout, level="INFO")

# Priority tickers from Week 4 investigation (WEEK4_PRICE_ANOMALY_INVESTIGATION.md)
PRIORITY_TICKERS = [
    '0008Z0', '0010V0', '003000', '0037T0', '0044K0', '005290', '0072Z0', '007860',
    '041930', '051600', '081180', '091090', '119500', '125020', '177900', '188040',
    '222040', '226590', '232830', '303810', '318060', '373160', '393970', '397810',
    '398120', '432980', '435570', '450950', '460870', '463020', '474650', '475430',
    '475830', '476040', '476060', '482630', '484810', '488280', '493790', '496070',
    '498390'
]


class OrphanedTickerBackfiller:
    """
    Backfill ticker metadata for orphaned OHLCV records.

    Data Sources (priority order):
    1. pykrx: Korean stock market data (free, no API key)
    2. DART API: Official company names for delisted/suspended stocks (97.7% coverage)
    3. Database inference: Market from ticker pattern
    4. Manual registration: For special cases
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.dart_client = DARTApiClient()
        self.ticker_to_name = {}  # Ticker -> company name mapping from DART
        self.stats = {
            'total_processed': 0,
            'success': 0,
            'dart_success': 0,
            'no_metadata': 0,
            'already_exists': 0,
            'failed': 0
        }

        # Load DART corp codes for ticker lookup
        self._load_dart_corp_codes()

    def get_orphaned_tickers(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Query orphaned tickers from database.

        Returns list sorted by:
        1. Priority tickers first
        2. Record count descending (most data first)
        """
        query = """
        WITH orphaned AS (
            SELECT DISTINCT o.ticker, o.region,
                   MIN(o.date) as first_date,
                   MAX(o.date) as last_date,
                   COUNT(*) as record_count
            FROM ohlcv_data o
            LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
            WHERE t.ticker IS NULL
            GROUP BY o.ticker, o.region
        )
        SELECT ticker, region, first_date, last_date, record_count
        FROM orphaned
        ORDER BY record_count DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)

        # Separate priority and non-priority tickers
        priority = []
        non_priority = []

        for row in results:
            if row['ticker'] in PRIORITY_TICKERS:
                priority.append(row)
            else:
                non_priority.append(row)

        # Return priority first, then non-priority
        return priority + non_priority

    def _load_dart_corp_codes(self) -> None:
        """
        Load DART corporate codes and create ticker -> company name mapping.

        Creates reverse mapping from stock_code (ticker) to corp_name for lookup.
        """
        try:
            xml_path = "config/dart_corp_codes.xml"
            logger.info(f"Loading DART corp codes from {xml_path}")

            # Parse corp codes: corp_name -> {corp_code, stock_code}
            corp_mapping = self.dart_client.parse_corp_codes(xml_path)

            # Create reverse mapping: stock_code (ticker) -> corp_name
            for corp_name, info in corp_mapping.items():
                stock_code = info.get('stock_code')
                if stock_code:  # Only if ticker exists (some corps don't have stock codes)
                    self.ticker_to_name[stock_code] = corp_name

            logger.info(f"Loaded {len(self.ticker_to_name)} ticker-to-name mappings from DART")

        except Exception as e:
            logger.warning(f"Failed to load DART corp codes: {e}")
            logger.warning("DART lookup will be unavailable, falling back to inference")

    def fetch_ticker_metadata_pykrx(self, ticker: str, timeout: int = 10) -> Optional[Dict]:
        """
        Fetch ticker metadata from pykrx with timeout protection.

        Returns:
            {
                'ticker': str,
                'name': str,
                'market': str,  # 'KOSPI', 'KOSDAQ', 'KONEX'
                'lot_size': int
            }
        """
        # Set up timeout signal
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            # Get ticker name from market
            today = datetime.now().strftime('%Y%m%d')

            # Try KOSPI first
            kospi_tickers = stock.get_market_ticker_list(today, market="KOSPI")
            if ticker in kospi_tickers:
                name = stock.get_market_ticker_name(ticker)
                signal.alarm(0)  # Cancel timeout
                return {
                    'ticker': ticker,
                    'name': name,
                    'market': 'KOSPI',
                    'lot_size': 1  # Default
                }

            # Try KOSDAQ
            kosdaq_tickers = stock.get_market_ticker_list(today, market="KOSDAQ")
            if ticker in kosdaq_tickers:
                name = stock.get_market_ticker_name(ticker)
                signal.alarm(0)  # Cancel timeout
                return {
                    'ticker': ticker,
                    'name': name,
                    'market': 'KOSDAQ',
                    'lot_size': 1
                }

            # Try KONEX
            konex_tickers = stock.get_market_ticker_list(today, market="KONEX")
            if ticker in konex_tickers:
                name = stock.get_market_ticker_name(ticker)
                signal.alarm(0)  # Cancel timeout
                return {
                    'ticker': ticker,
                    'name': name,
                    'market': 'KONEX',
                    'lot_size': 1
                }

            # Try ETF (dedicated ETF list)
            etf_tickers = stock.get_etf_ticker_list(today)
            if ticker in etf_tickers:
                name = stock.get_etf_ticker_name(ticker)
                signal.alarm(0)  # Cancel timeout
                return {
                    'ticker': ticker,
                    'name': name,
                    'market': 'ETF',
                    'lot_size': 1
                }

            # Not found in any market
            signal.alarm(0)  # Cancel timeout
            logger.debug(f"{ticker}: Not found in pykrx (KOSPI/KOSDAQ/KONEX/ETF)")
            return None

        except TimeoutException:
            signal.alarm(0)  # Cancel timeout
            logger.warning(f"{ticker}: pykrx timeout after {timeout}s")
            return None
        except Exception as e:
            signal.alarm(0)  # Cancel timeout
            logger.debug(f"{ticker}: pykrx fetch error: {e}")
            return None

    def fetch_ticker_metadata_dart(self, ticker: str) -> Optional[Dict]:
        """
        Fetch ticker metadata from DART API (for delisted/suspended stocks).

        Uses pre-loaded ticker_to_name mapping from DART corp codes.

        Returns:
            {
                'ticker': str,
                'name': str,
                'market': str,  # Inferred from ticker pattern
                'lot_size': int
            }
        """
        try:
            # Look up company name from DART mapping
            company_name = self.ticker_to_name.get(ticker)

            if company_name:
                # Infer market from ticker pattern (DART doesn't provide market info)
                market = self.infer_market_from_ticker(ticker)

                logger.debug(f"{ticker}: Found in DART - {company_name}")
                return {
                    'ticker': ticker,
                    'name': company_name,
                    'market': market,
                    'lot_size': 1
                }
            else:
                logger.debug(f"{ticker}: Not found in DART corp codes")
                return None

        except Exception as e:
            logger.debug(f"{ticker}: DART lookup error: {e}")
            return None

    def infer_market_from_ticker(self, ticker: str) -> str:
        """
        Infer market from ticker pattern (fallback method).

        Korean ticker patterns:
        - KOSPI: Usually starts with 0 (e.g., 005930)
        - KOSDAQ: Usually starts with 1-9 (e.g., 122630)
        - ETF: Often 6 digits starting with 1-4
        - Special: Contains letters (e.g., 0008Z0, 0044K0)
        """
        if not ticker[0].isdigit():
            return 'UNKNOWN'

        # Contains letters → likely special derivative/ETF
        if any(c.isalpha() for c in ticker):
            return 'DERIVATIVE'

        # 6 digits starting with 0 → likely KOSPI
        if ticker.startswith('0') and len(ticker) == 6:
            return 'KOSPI'

        # 6 digits starting with 1-9 → likely KOSDAQ or ETF
        if ticker[0] in '123456789' and len(ticker) == 6:
            # ETFs often in 1xxxxx-4xxxxx range
            if ticker.startswith(('1', '2', '3', '4')):
                return 'ETF'
            else:
                return 'KOSDAQ'

        return 'UNKNOWN'

    def check_ticker_exists(self, ticker: str, region: str) -> bool:
        """Check if ticker already registered."""
        query = "SELECT 1 FROM tickers WHERE ticker = %s AND region = %s"
        result = self.db.execute_query(query, (ticker, region))
        return len(result) > 0

    def insert_ticker(self, metadata: Dict, region: str = 'KR', timeout_flag: bool = False, data_source: str = 'pykrx') -> bool:
        """
        Insert ticker into tickers table.

        Args:
            metadata: Dict with keys [ticker, name, market, lot_size]
                     market will be inserted into exchange column
            region: Region code (default: 'KR')
            timeout_flag: TRUE if ticker timed out during pykrx lookup (default: False)
            data_source: Source of metadata (pykrx, DART, inference) (default: 'pykrx')

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
            INSERT INTO tickers (ticker, name, region, exchange, currency, lot_size, asset_type, is_active, data_source, timeout_flag)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region) DO NOTHING
            """

            # Determine asset_type from market
            if metadata['market'] in ['KOSPI', 'KOSDAQ', 'KONEX']:
                asset_type = 'STOCK'
            elif metadata['market'] == 'ETF':
                asset_type = 'ETF'
            elif metadata['market'] == 'DERIVATIVE':
                asset_type = 'DERIVATIVE'
            else:
                asset_type = 'UNKNOWN'

            params = (
                metadata['ticker'],
                metadata['name'],
                region,
                metadata['market'],  # exchange column
                'KRW',  # currency
                metadata['lot_size'],
                asset_type,
                True,  # is_active
                data_source,  # data_source (pykrx, DART, inference)
                timeout_flag  # timeout_flag (TRUE for delisted/suspended)
            )

            self.db.execute_update(query, params)
            return True

        except Exception as e:
            logger.error(f"{metadata['ticker']}: Insert failed: {e}")
            return False

    def backfill_single_ticker(self, ticker: str, region: str, dry_run: bool = False) -> bool:
        """
        Backfill metadata for a single ticker.

        Data source priority:
        1. pykrx (active stocks/ETFs)
        2. DART API (delisted/suspended stocks)
        3. Inference (pattern-based fallback)

        Returns:
            True if successful, False otherwise
        """
        # Check if already exists
        if self.check_ticker_exists(ticker, region):
            logger.info(f"✓ {ticker}: Already registered in tickers table")
            self.stats['already_exists'] += 1
            return True

        # Track data source and timeout status
        timeout_occurred = False
        data_source = 'pykrx'

        # Try pykrx first
        metadata = self.fetch_ticker_metadata_pykrx(ticker)

        # If pykrx failed, try DART API (for delisted/suspended stocks)
        if not metadata:
            timeout_occurred = True  # pykrx timeout indicates delisted/suspended
            metadata = self.fetch_ticker_metadata_dart(ticker)

            if metadata:
                data_source = 'DART'
                self.stats['dart_success'] += 1
                logger.info(f"🎯 {ticker}: Found in DART - {metadata['name']}")

        # Final fallback to inference
        if not metadata:
            inferred_market = self.infer_market_from_ticker(ticker)
            metadata = {
                'ticker': ticker,
                'name': f"{ticker} (Inferred)",
                'market': inferred_market,
                'lot_size': 1
            }
            data_source = 'inference'
            logger.warning(f"⚠️  {ticker}: No pykrx/DART data, using inference (market={inferred_market})")

        # Log metadata
        if metadata:
            priority_marker = "🎯 PRIORITY" if ticker in PRIORITY_TICKERS else ""
            source_marker = f"[{data_source}]"
            timeout_marker = "⚠️ TIMEOUT" if timeout_occurred else ""
            logger.info(
                f"✅ {ticker}: {metadata['name']} "
                f"({metadata['market']}) {source_marker} {timeout_marker} {priority_marker}"
            )

            # Insert into database (unless dry run)
            if not dry_run:
                success = self.insert_ticker(metadata, region, timeout_flag=timeout_occurred, data_source=data_source)
                if success:
                    self.stats['success'] += 1
                    return True
                else:
                    self.stats['failed'] += 1
                    return False
            else:
                self.stats['success'] += 1
                return True
        else:
            logger.error(f"❌ {ticker}: No metadata found (all sources failed)")
            self.stats['no_metadata'] += 1
            return False

    def backfill_all_orphaned(self, dry_run: bool = False, limit: Optional[int] = None, rate_limit: float = 0.5):
        """
        Backfill all orphaned tickers.

        Args:
            dry_run: If True, don't insert into database
            limit: Max number of tickers to process (None = all)
            rate_limit: Delay between API calls (seconds)
        """
        orphans = self.get_orphaned_tickers(limit=limit)

        logger.info("=" * 80)
        logger.info(f"Orphaned Ticker Backfill {'(DRY RUN)' if dry_run else ''}")
        logger.info("=" * 80)
        logger.info(f"Total orphaned tickers: {len(orphans)}")
        logger.info(f"Priority tickers: {len([o for o in orphans if o['ticker'] in PRIORITY_TICKERS])}")
        logger.info(f"Rate limit: {rate_limit}s per ticker")
        logger.info("")

        for idx, orphan in enumerate(orphans, 1):
            ticker = orphan['ticker']
            region = orphan['region']
            record_count = orphan['record_count']

            logger.info(f"[{idx}/{len(orphans)}] Processing {ticker} ({record_count} records)...")

            self.backfill_single_ticker(ticker, region, dry_run=dry_run)
            self.stats['total_processed'] += 1

            # Rate limiting (skip on last iteration)
            if idx < len(orphans):
                time.sleep(rate_limit)

        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("Backfill Summary")
        logger.info("=" * 80)
        logger.info(f"Total processed: {self.stats['total_processed']}")
        logger.info(f"✅ Success: {self.stats['success']}")
        logger.info(f"  - pykrx: {self.stats['success'] - self.stats['dart_success']}")
        logger.info(f"  - DART: {self.stats['dart_success']}")
        logger.info(f"✓  Already exists: {self.stats['already_exists']}")
        logger.info(f"⚠️  No metadata: {self.stats['no_metadata']}")
        logger.info(f"❌ Failed: {self.stats['failed']}")
        logger.info("")

        success_rate = (self.stats['success'] + self.stats['already_exists']) / max(self.stats['total_processed'], 1) * 100
        dart_coverage = (self.stats['dart_success'] / max(self.stats['success'], 1)) * 100 if self.stats['success'] > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info(f"DART coverage: {dart_coverage:.1f}% of new tickers")

    def validate_backfill(self) -> bool:
        """
        Validate backfill completeness.

        Returns:
            True if validation passes, False otherwise
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("Validation Checks")
        logger.info("=" * 80)

        # Check 1: Orphan count should be 0
        orphans = self.get_orphaned_tickers()
        if len(orphans) > 0:
            logger.error(f"❌ Validation FAILED: {len(orphans)} orphaned tickers remain")
            logger.error(f"   Remaining orphans: {[o['ticker'] for o in orphans[:10]]}")
            return False
        else:
            logger.info("✅ Check 1 PASSED: No orphaned tickers remaining")

        # Check 2: No duplicate ticker entries
        query = """
        SELECT ticker, region, COUNT(*) as cnt
        FROM tickers
        GROUP BY ticker, region
        HAVING COUNT(*) > 1
        """
        duplicates = self.db.execute_query(query)

        if len(duplicates) > 0:
            logger.error(f"❌ Validation FAILED: {len(duplicates)} duplicate ticker entries")
            for dup in duplicates[:5]:
                logger.error(f"   {dup['ticker']}: {dup['cnt']} entries")
            return False
        else:
            logger.info("✅ Check 2 PASSED: No duplicate ticker entries")

        # Check 3: Priority tickers all registered
        query = """
        SELECT COUNT(*) as cnt
        FROM tickers
        WHERE ticker = ANY(%s) AND region = 'KR'
        """
        result = self.db.execute_query(query, (PRIORITY_TICKERS,))
        registered_count = result[0]['cnt']

        if registered_count < len(PRIORITY_TICKERS):
            logger.warning(f"⚠️  Check 3 WARNING: Only {registered_count}/{len(PRIORITY_TICKERS)} priority tickers registered")
            return False
        else:
            logger.info(f"✅ Check 3 PASSED: All {len(PRIORITY_TICKERS)} priority tickers registered")

        logger.info("")
        logger.info("✅ All validation checks PASSED")
        return True


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Backfill orphaned ticker metadata')
    parser.add_argument('--dry-run', action='store_true', help='Test without database writes')
    parser.add_argument('--limit', type=int, help='Limit number of tickers to process')
    parser.add_argument('--validate', action='store_true', help='Run validation checks only')
    parser.add_argument('--rate-limit', type=float, default=0.5, help='Delay between API calls (default: 0.5s)')

    args = parser.parse_args()

    # Initialize database and backfiller
    db = PostgresDatabaseManager()
    backfiller = OrphanedTickerBackfiller(db)

    if args.validate:
        # Validation only
        backfiller.validate_backfill()
    else:
        # Run backfill
        backfiller.backfill_all_orphaned(
            dry_run=args.dry_run,
            limit=args.limit,
            rate_limit=args.rate_limit
        )

        # Auto-validate after backfill (unless dry run)
        if not args.dry_run:
            logger.info("")
            backfiller.validate_backfill()


if __name__ == "__main__":
    main()
