#!/usr/bin/env python3
"""
AkShare Fundamental Data Backfill Script

Backfills fundamental metrics for CN and HK markets using AkShare library.
No API key required - completely free and open-source.

CN Metrics (86 financial indicators):
- Valuation: P/E Ratio, P/B Ratio
- Profitability: ROE, ROA, Gross Margin, Net Margin
- Solvency: Debt Ratio, Current Ratio
- Per-share: EPS, BPS

HK Metrics (36 financial indicators):
- Similar metrics via stock_financial_hk_analysis_indicator_em()

Collection Modes:
- batch: Fast batch collection for CN (~5,900 stocks, basic indicators)
- individual: Detailed per-ticker collection (CN: 86, HK: 36 indicators)
- hybrid: Batch first, then individual for detail (recommended for CN)

Author: Quant Platform Development Team
Date: 2025-12-17
"""

import sys
import os
import argparse
import time
from datetime import datetime
from typing import List, Optional

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.market_adapters.cn_adapter import CNAdapter
from modules.market_adapters.hk_adapter import HKAdapter
from loguru import logger

# Configure loguru logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


class AkShareFundamentalBackfiller:
    """
    AkShare fundamental data backfiller for CN/HK markets

    Features:
    - CN: Batch mode (~5,900 stocks) + Individual mode (86 indicators)
    - HK: Individual mode (36 indicators) with dynamic ticker expansion (~4,600 stocks)
    - yfinance fallback for reliability
    - Rate limiting (1.5 requests/second)
    - Dry-run mode for testing
    - Progress checkpointing
    """

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize AkShare fundamental backfiller

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Initialize adapters
        self.cn_adapter = CNAdapter(db, enable_fallback=True)
        self.hk_adapter = HKAdapter(db, enable_fallback=True)

        # Statistics
        self.stats = {
            'cn_batch_success': 0,
            'cn_individual_success': 0,
            'cn_fallback_used': 0,
            'hk_success': 0,
            'hk_fallback_used': 0,
            'total_records': 0,
            'start_time': None,
            'end_time': None
        }

    def backfill_cn(self,
                    mode: str = 'hybrid',
                    report_date: Optional[str] = None,
                    limit: Optional[int] = None,
                    tickers: Optional[List[str]] = None,
                    asset_types: List[str] = ['STOCK']) -> int:
        """
        Backfill CN fundamental data

        Args:
            mode: Collection mode ('batch', 'individual', 'hybrid')
            report_date: Report date for batch mode (YYYYMMDD)
            limit: Max number of tickers to process
            tickers: Specific tickers to process (overrides limit)
            asset_types: Asset types to include (default: ['STOCK'] only)
                        Options: ['STOCK'], ['ETF'], ['STOCK', 'ETF'], etc.

        Returns:
            Number of records inserted
        """
        logger.info(f"🇨🇳 Starting CN fundamentals backfill (mode={mode}, asset_types={asset_types})")

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No database writes will be performed")
            return self._preview_cn(mode, report_date, limit)

        self.stats['start_time'] = datetime.now()

        # Apply limit if specified
        if limit and not tickers:
            # Get all active tickers for the region
            all_tickers = self.db.get_tickers(region='CN', is_active=True)

            # Filter by asset_type
            db_tickers = [t for t in all_tickers if t.get('asset_type') in asset_types]

            # Log exclusion count
            excluded = len(all_tickers) - len(db_tickers)
            logger.info(f"   📊 [CN] Excluded {excluded} non-stock tickers (ETFs, funds, etc.)")
            logger.info(f"   📊 [CN] Processing {len(db_tickers)} tickers with asset_types={asset_types}")

            tickers = [t['ticker'] for t in db_tickers][:limit]

        # Run collection
        success_count = self.cn_adapter.collect_fundamentals(
            tickers=tickers,
            mode=mode,
            report_date=report_date,
            use_fallback=True
        )

        self.stats['end_time'] = datetime.now()
        self.stats['total_records'] += success_count

        # Log summary
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        logger.info(f"✅ CN backfill complete: {success_count} records in {duration:.1f}s")

        return success_count

    def backfill_hk(self,
                   limit: Optional[int] = None,
                   tickers: Optional[List[str]] = None,
                   scan_first: bool = True,
                   asset_types: List[str] = ['STOCK']) -> int:
        """
        Backfill HK fundamental data

        Args:
            limit: Max number of tickers to process
            tickers: Specific tickers to process (overrides limit)
            scan_first: Scan for new tickers via AkShare before collection
            asset_types: Asset types to include (default: ['STOCK'] only)
                        Options: ['STOCK'], ['ETF'], ['STOCK', 'ETF'], etc.

        Returns:
            Number of records inserted
        """
        logger.info(f"🇭🇰 Starting HK fundamentals backfill (asset_types={asset_types})")

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No database writes will be performed")
            return self._preview_hk(limit)

        self.stats['start_time'] = datetime.now()

        # Optionally scan for new tickers first
        if scan_first:
            logger.info("📊 Scanning for HK tickers via AkShare...")
            scanned = self.hk_adapter.scan_stocks(force_refresh=True, max_count=limit)
            logger.info(f"✅ Found {len(scanned)} HK tickers")

        # Apply limit if specified
        if limit and not tickers:
            # Get all active tickers for the region
            all_tickers = self.db.get_tickers(region='HK', is_active=True)

            # Filter by asset_type
            db_tickers = [t for t in all_tickers if t.get('asset_type') in asset_types]

            # Log exclusion count
            excluded = len(all_tickers) - len(db_tickers)
            logger.info(f"   📊 [HK] Excluded {excluded} non-stock tickers (ETFs, funds, etc.)")
            logger.info(f"   📊 [HK] Processing {len(db_tickers)} tickers with asset_types={asset_types}")

            tickers = [t['ticker'] for t in db_tickers][:limit]

        # Run collection
        success_count = self.hk_adapter.collect_fundamentals(
            tickers=tickers,
            use_fallback=True
        )

        self.stats['end_time'] = datetime.now()
        self.stats['total_records'] += success_count

        # Log summary
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        logger.info(f"✅ HK backfill complete: {success_count} records in {duration:.1f}s")

        return success_count

    def backfill_all(self,
                    cn_mode: str = 'hybrid',
                    report_date: Optional[str] = None,
                    limit: Optional[int] = None) -> int:
        """
        Backfill both CN and HK fundamental data

        Args:
            cn_mode: Collection mode for CN ('batch', 'individual', 'hybrid')
            report_date: Report date for CN batch mode
            limit: Max tickers per region

        Returns:
            Total number of records inserted
        """
        logger.info("🌏 Starting ALL regions fundamentals backfill")

        total = 0

        # CN first
        cn_count = self.backfill_cn(mode=cn_mode, report_date=report_date, limit=limit)
        total += cn_count

        # Then HK
        hk_count = self.backfill_hk(limit=limit)
        total += hk_count

        logger.info(f"✅ All regions complete: {total} total records (CN: {cn_count}, HK: {hk_count})")
        return total

    def _preview_cn(self, mode: str, report_date: Optional[str], limit: Optional[int]) -> int:
        """Preview CN collection without database writes"""
        db_tickers = self.db.get_tickers(region='CN', asset_type='STOCK', is_active=True)
        ticker_count = len(db_tickers)

        if limit:
            ticker_count = min(ticker_count, limit)

        logger.info(f"📋 CN Preview (mode={mode}):")
        logger.info(f"   - Total tickers in DB: {len(db_tickers)}")
        logger.info(f"   - Tickers to process: {ticker_count}")
        logger.info(f"   - Report date: {report_date or 'auto-detect'}")

        if mode == 'batch':
            logger.info(f"   - Estimated time: ~1 min (batch)")
        elif mode == 'individual':
            estimated_time = ticker_count * 0.67  # ~1.5 req/sec
            logger.info(f"   - Estimated time: ~{estimated_time/60:.1f} min (individual)")
        else:  # hybrid
            logger.info(f"   - Estimated time: ~1 min (batch) + remaining individual")

        return 0

    def _preview_hk(self, limit: Optional[int]) -> int:
        """Preview HK collection without database writes"""
        db_tickers = self.db.get_tickers(region='HK', asset_type='STOCK', is_active=True)
        ticker_count = len(db_tickers)

        if limit:
            ticker_count = min(ticker_count, limit)

        logger.info(f"📋 HK Preview:")
        logger.info(f"   - Current tickers in DB: {len(db_tickers)}")
        logger.info(f"   - AkShare can expand to: ~4,600 tickers")
        logger.info(f"   - Tickers to process: {ticker_count if limit else '~4,600'}")

        estimated_time = (limit or 4600) * 0.67  # ~1.5 req/sec
        logger.info(f"   - Estimated time: ~{estimated_time/60:.1f} min")

        return 0

    def print_summary(self):
        """Print collection summary"""
        logger.info("=" * 60)
        logger.info("📊 BACKFILL SUMMARY")
        logger.info("=" * 60)
        logger.info(f"   Total records: {self.stats['total_records']}")

        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            logger.info(f"   Duration: {duration:.1f} seconds")
            if self.stats['total_records'] > 0:
                rate = self.stats['total_records'] / duration
                logger.info(f"   Rate: {rate:.2f} records/sec")

        logger.info("=" * 60)


def main():
    """Main entry point with CLI argument parsing"""
    parser = argparse.ArgumentParser(
        description="AkShare Fundamental Data Backfill for CN/HK Markets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CN batch mode (fast, ~5,900 stocks)
  python backfill_fundamentals_akshare.py --region CN --mode batch

  # CN hybrid mode (recommended)
  python backfill_fundamentals_akshare.py --region CN --mode hybrid --report-date 20240930

  # HK with dynamic ticker expansion
  python backfill_fundamentals_akshare.py --region HK

  # All regions with limit
  python backfill_fundamentals_akshare.py --region ALL --limit 100

  # Dry run preview
  python backfill_fundamentals_akshare.py --region CN --mode batch --dry-run
        """
    )

    parser.add_argument(
        '--region',
        type=str,
        choices=['CN', 'HK', 'ALL'],
        default='ALL',
        help='Target region (CN, HK, or ALL). Default: ALL'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['batch', 'individual', 'hybrid'],
        default='hybrid',
        help='CN collection mode. batch=fast, individual=detailed, hybrid=both. Default: hybrid'
    )

    parser.add_argument(
        '--report-date',
        type=str,
        default=None,
        help='Report date for CN batch mode (YYYYMMDD, e.g., 20240930). Default: auto-detect'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Max tickers to process per region. Default: all'
    )

    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        default=None,
        help='Specific ticker codes to process (overrides --limit)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database writes'
    )

    parser.add_argument(
        '--no-scan',
        action='store_true',
        help='Skip HK ticker scanning (use existing DB tickers only)'
    )

    args = parser.parse_args()

    # Initialize database connection
    logger.info("🔌 Connecting to PostgreSQL database...")
    db = PostgresDatabaseManager()

    # Initialize backfiller
    backfiller = AkShareFundamentalBackfiller(db=db, dry_run=args.dry_run)

    try:
        # Run backfill based on region
        if args.region == 'CN':
            backfiller.backfill_cn(
                mode=args.mode,
                report_date=args.report_date,
                limit=args.limit,
                tickers=args.tickers
            )
        elif args.region == 'HK':
            backfiller.backfill_hk(
                limit=args.limit,
                tickers=args.tickers,
                scan_first=not args.no_scan
            )
        else:  # ALL
            backfiller.backfill_all(
                cn_mode=args.mode,
                report_date=args.report_date,
                limit=args.limit
            )

        # Print summary
        backfiller.print_summary()

    except KeyboardInterrupt:
        logger.warning("⚠️ Interrupted by user")
        backfiller.print_summary()
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
