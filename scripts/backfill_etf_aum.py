#!/usr/bin/env python3
"""
ETF AUM and Listed Shares Backfill Script

Specifically backfills AUM (순자산) and listed_shares fields for ETFs.
Reuses existing NaverFinanceETFScraper from backfill_etf_naver.py.

Author: Spock Trading System
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from scripts.backfill_etf_naver import NaverFinanceETFScraper

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_etf_aum_backfill.log')
    ]
)
logger = logging.getLogger(__name__)


def backfill_aum_and_shares(dry_run: bool = False, rate_limit: float = 1.0):
    """
    Backfill AUM and listed_shares for ETFs that don't have them

    Args:
        dry_run: If True, simulate without actual DB updates
        rate_limit: Seconds to wait between requests (default: 1.0)

    Returns:
        (success_count, skipped_count, failed_count)
    """
    db = SQLiteDatabaseManager()
    scraper = NaverFinanceETFScraper(rate_limit=rate_limit)

    # Get ETFs that need AUM/listed_shares update
    conn = db._get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT t.ticker, t.name
        FROM tickers t
        INNER JOIN etf_details ed ON t.ticker = ed.ticker
        WHERE t.asset_type = 'ETF'
          AND t.region = 'KR'
          AND t.is_active = 1
          AND (ed.aum IS NULL OR ed.listed_shares IS NULL)
        ORDER BY t.ticker
    """)
    etfs = [dict(row) for row in cursor.fetchall()]
    conn.close()

    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 ETF AUM & Listed Shares Backfill")
    logger.info("=" * 80)
    logger.info(f"📌 {len(etfs)}개 ETF AUM/상장주식수 업데이트 필요")
    logger.info(f"📌 Rate limit: {rate_limit}s/request")
    logger.info(f"📌 Estimated time: ~{len(etfs) * rate_limit / 60:.1f} minutes")

    if dry_run:
        logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

    logger.info("")

    success, skipped, failed = 0, 0, 0

    for idx, etf in enumerate(etfs):
        ticker = etf['ticker']
        name = etf['name']

        try:
            # Scrape ETF details from Naver
            etf_data = scraper.get_etf_details(ticker)

            if etf_data and (etf_data.get('aum') or etf_data.get('listed_shares')):
                if not dry_run:
                    # Update database with AUM and listed_shares
                    updates = {}
                    if etf_data.get('aum') is not None:
                        updates['aum'] = etf_data['aum']
                    if etf_data.get('listed_shares') is not None:
                        updates['listed_shares'] = etf_data['listed_shares']

                    if updates:
                        db.update_etf_details(ticker, updates)

                # Progress logging
                aum_str = f"{etf_data['aum']:,}" if etf_data.get('aum') else "N/A"
                shares_str = f"{etf_data['listed_shares']:,}" if etf_data.get('listed_shares') else "N/A"

                if success < 10 or success % 100 == 0 or success >= len(etfs) - 10:
                    logger.info(
                        f"  [{idx+1}/{len(etfs)}] ✅ [{ticker}] {name}: AUM={aum_str} KRW, Shares={shares_str}"
                        f"{' (DRY RUN)' if dry_run else ''}"
                    )
                elif success == 10:
                    logger.info(f"  ... (logging every 100 ETFs) ...")

                success += 1

            else:
                logger.warning(f"  [{idx+1}/{len(etfs)}] ⏭️ [{ticker}] {name}: No AUM/shares data")
                skipped += 1

        except KeyboardInterrupt:
            logger.warning("")
            logger.warning("=" * 80)
            logger.warning("🛑 Interrupted by user")
            logger.warning(f"💾 Progress: {success} success, {skipped} skipped, {failed} failed")
            logger.warning(f"📍 Resume from: {ticker}")
            logger.warning("=" * 80)
            raise

        except Exception as e:
            logger.error(f"  [{idx+1}/{len(etfs)}] ❌ [{ticker}] {name}: {e}")
            failed += 1

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"✅ Backfill Complete: Success={success}, Skipped={skipped}, Failed={failed}")
    logger.info("=" * 80)

    return (success, skipped, failed)


def show_coverage_report(db: SQLiteDatabaseManager):
    """Show AUM and listed_shares coverage statistics"""
    conn = db._get_connection()
    cursor = conn.cursor()

    # Total ETFs
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM tickers
        WHERE asset_type = 'ETF' AND region = 'KR' AND is_active = 1
    """)
    total = cursor.fetchone()['total']

    # Coverage by field
    cursor.execute("""
        SELECT
            SUM(CASE WHEN ed.aum IS NOT NULL AND ed.aum > 0 THEN 1 ELSE 0 END) as has_aum,
            SUM(CASE WHEN ed.listed_shares IS NOT NULL AND ed.listed_shares > 0 THEN 1 ELSE 0 END) as has_shares
        FROM tickers t
        INNER JOIN etf_details ed ON t.ticker = ed.ticker
        WHERE t.asset_type = 'ETF' AND t.region = 'KR' AND t.is_active = 1
    """)
    coverage = cursor.fetchone()

    conn.close()

    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 AUM & LISTED SHARES COVERAGE REPORT")
    logger.info("=" * 80)
    logger.info(f"Total ETFs: {total}")
    logger.info(f"AUM: {coverage['has_aum']}/{total} ({coverage['has_aum']/total*100:.1f}%)")
    logger.info(f"Listed Shares: {coverage['has_shares']}/{total} ({coverage['has_shares']/total*100:.1f}%)")
    logger.info("=" * 80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='ETF AUM & Listed Shares Backfill')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                       help='Seconds to wait between requests (default: 1.0)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 ETF AUM & Listed Shares Backfill")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Rate Limit: {args.rate_limit}s/request")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    show_coverage_report(db)

    # Execute backfill
    logger.info("")
    try:
        success, skipped, failed = backfill_aum_and_shares(
            dry_run=args.dry_run,
            rate_limit=args.rate_limit
        )

        # Show final coverage
        if not args.dry_run and success > 0:
            logger.info("")
            logger.info("Final Coverage (After Backfill):")
            show_coverage_report(db)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("User interrupted - exiting gracefully")

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ ETF AUM & Listed Shares Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
