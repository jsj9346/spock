#!/usr/bin/env python3
"""
yfinance QUARTERLY Backfill Script

HK, CN, VN 리전의 분기별 재무제표 데이터를 yfinance에서 수집합니다.
TTM(Trailing Twelve Months) 계산을 위한 QUARTERLY 데이터 확보가 목적입니다.

수집 데이터:
- Income Statement: revenue, gross_profit, operating_profit, net_income, ebitda 등
- Balance Sheet: total_assets, total_equity, current_assets, current_liabilities 등
- Cash Flow: operating_cash_flow, fcf, capex 등

사용법:
    # DRY RUN 테스트
    python scripts/backfill_quarterly_yfinance.py --region HK --limit 5 --dry-run

    # 실제 백필 (HK 리전)
    python scripts/backfill_quarterly_yfinance.py --region HK --limit 100

    # 전체 리전 백필 + TTM 계산
    python scripts/backfill_quarterly_yfinance.py --calculate-ttm

Author: Quant Platform Development Team
Date: 2025-12-11
"""

import sys
import os
import argparse
from datetime import datetime

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.yfinance_quarterly_executor import YFinanceQuarterlyExecutor
from loguru import logger

# Configure loguru logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="yfinance QUARTERLY Backfill (HK/CN/VN Regions)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # DRY RUN test for Hong Kong
  python scripts/backfill_quarterly_yfinance.py --region HK --limit 5 --dry-run

  # Backfill Vietnam with 100 tickers
  python scripts/backfill_quarterly_yfinance.py --region VN --limit 100

  # Full backfill for all regions with TTM calculation
  python scripts/backfill_quarterly_yfinance.py --calculate-ttm

  # Force refresh existing data
  python scripts/backfill_quarterly_yfinance.py --region HK --force-refresh --limit 50
        """
    )

    parser.add_argument(
        '--region',
        choices=['HK', 'CN', 'VN', 'ALL'],
        default='ALL',
        help='Target region (default: ALL)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum tickers per region (for testing)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database writes'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Re-fetch even if QUARTERLY data exists'
    )
    parser.add_argument(
        '--calculate-ttm',
        action='store_true',
        default=True,
        help='Calculate TTM after backfill (default: True)'
    )
    parser.add_argument(
        '--no-ttm',
        action='store_true',
        help='Skip TTM calculation after backfill'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=0.5,
        help='Delay between API calls in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=50,
        help='Save checkpoint every N tickers (default: 50)'
    )

    args = parser.parse_args()

    # Determine target regions
    if args.region == 'ALL':
        regions = ['HK', 'CN', 'VN']
    else:
        regions = [args.region]

    # Calculate TTM flag
    calculate_ttm = args.calculate_ttm and not args.no_ttm

    # Connect to database
    try:
        db = PostgresDatabaseManager()
        logger.info("Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)

    # Initialize executor
    try:
        executor = YFinanceQuarterlyExecutor(
            db=db,
            dry_run=args.dry_run,
            rate_limit_delay=args.rate_limit,
            regions=regions
        )
    except Exception as e:
        logger.error(f"Executor initialization failed: {e}")
        sys.exit(1)

    # Print configuration
    logger.info("=" * 80)
    logger.info("YFINANCE QUARTERLY BACKFILL (HK/CN/VN)")
    logger.info("=" * 80)
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Target Regions: {regions}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Force Refresh: {args.force_refresh}")
    logger.info(f"Calculate TTM: {calculate_ttm}")
    logger.info(f"Rate Limit: {args.rate_limit}s/request (2 req/sec)")
    logger.info(f"Checkpoint Interval: {args.checkpoint_interval} tickers")
    if args.limit:
        logger.info(f"Limit: {args.limit} tickers per region")
    logger.info("=" * 80)

    # Run backfill
    start_time = datetime.now()

    try:
        stats = executor.run_backfill(
            regions=regions,
            limit=args.limit,
            force_refresh=args.force_refresh,
            calculate_ttm=calculate_ttm,
            checkpoint_interval=args.checkpoint_interval
        )

        end_time = datetime.now()
        duration = end_time - start_time

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")

        logger.info("\nStatistics:")
        logger.info(f"  Tickers Processed: {stats.tickers_processed}")
        logger.info(f"  Success: {stats.tickers_success}")
        logger.info(f"  Failed: {stats.tickers_failed}")
        logger.info(f"  Skipped: {stats.tickers_skipped}")
        logger.info(f"  API Calls: {stats.api_calls}")

        if stats.errors:
            logger.warning(f"\nErrors ({len(stats.errors)}):")
            for err in stats.errors[:10]:  # Show first 10 errors
                logger.warning(f"  - {err}")
            if len(stats.errors) > 10:
                logger.warning(f"  ... and {len(stats.errors) - 10} more")

        logger.info("=" * 80)

        # Print coverage summary
        _print_coverage_summary(db, regions)

        # Success/failure message
        if stats.tickers_processed > 0:
            success_rate = stats.tickers_success / stats.tickers_processed * 100
            if success_rate >= 80:
                logger.info(f"Backfill completed successfully (success rate: {success_rate:.1f}%)")
            elif success_rate >= 50:
                logger.warning(f"Backfill completed with moderate success rate: {success_rate:.1f}%")
            else:
                logger.warning(f"Backfill completed with low success rate: {success_rate:.1f}%")
        else:
            logger.warning("No tickers were processed")

    except KeyboardInterrupt:
        logger.warning("\nBackfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close_pool()


def _print_coverage_summary(db: PostgresDatabaseManager, regions: list):
    """Print QUARTERLY data coverage summary"""
    logger.info("\nQUARTERLY Data Coverage:")

    for region in regions:
        try:
            # Total tickers
            total_query = f"""
            SELECT COUNT(*) as cnt FROM tickers
            WHERE region = '{region}' AND asset_type = 'STOCK' AND is_active = TRUE
            """
            total_result = db.execute_query(total_query)
            total_tickers = total_result[0]['cnt'] if total_result else 0

            # Tickers with QUARTERLY data
            quarterly_query = f"""
            SELECT COUNT(DISTINCT ticker) as cnt FROM ticker_fundamentals
            WHERE region = '{region}' AND period_type = 'QUARTERLY'
            """
            quarterly_result = db.execute_query(quarterly_query)
            quarterly_tickers = quarterly_result[0]['cnt'] if quarterly_result else 0

            # Tickers with TTM data
            ttm_query = f"""
            SELECT COUNT(DISTINCT ticker) as cnt FROM ticker_fundamentals_ttm
            WHERE region = '{region}'
            """
            ttm_result = db.execute_query(ttm_query)
            ttm_tickers = ttm_result[0]['cnt'] if ttm_result else 0

            # Coverage percentage
            quarterly_pct = (quarterly_tickers / total_tickers * 100) if total_tickers > 0 else 0
            ttm_pct = (ttm_tickers / total_tickers * 100) if total_tickers > 0 else 0

            logger.info(f"\n  {region}:")
            logger.info(f"    Total Tickers: {total_tickers:,}")
            logger.info(f"    QUARTERLY: {quarterly_tickers:,} ({quarterly_pct:.1f}%)")
            logger.info(f"    TTM: {ttm_tickers:,} ({ttm_pct:.1f}%)")

        except Exception as e:
            logger.error(f"  {region}: Failed to get coverage ({e})")


if __name__ == '__main__':
    main()
