#!/usr/bin/env python3
"""
ETF Data Collection Script

Purpose: Collect fundamental data for all Korean ETFs from multiple sources:
  - KRX ETF Portal: AUM, TER, tracking error
  - ETFCheck: Sector/theme, tracking index
  - Fund managers: Dividend yield

Usage:
    python3 scripts/collect_etf_data.py [--source krx|etfcheck|all] [--limit N] [--dry-run]

Arguments:
    --source: Data source to collect from (default: all)
    --limit: Number of ETFs to collect (default: all 1,208)
    --dry-run: Test without actual collection
    --rate-limit: Delay between requests in seconds (default: 1.0)

Prerequisites:
    - PostgreSQL database with etf_details table
    - Internet connection for web scraping
    - 1,208 ETFs in tickers table (asset_type='ETF')

Expected Output:
    - etf_details table populated with fundamental data
    - Collection duration: 20-30 minutes (with rate limiting)

Author: Spock Quant Platform
Phase: ETF Screening Tool - Phase 1
"""

import sys
import os
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.screening.etf_data_collector import ETFDataCollector
from dotenv import load_dotenv
from psycopg2 import extras

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner(title: str, width: int = 80):
    """Print formatted banner"""
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title: str):
    """Print section header"""
    print(f"\n{'─' * 80}")
    print(f"📊 {title}")
    print(f"{'─' * 80}")


async def main():
    """Main execution function"""

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Collect ETF fundamental data from multiple sources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all data for all ETFs (dry run)
  python3 scripts/collect_etf_data.py --dry-run

  # Collect only KRX data for 10 ETFs
  python3 scripts/collect_etf_data.py --source krx --limit 10

  # Collect all data with custom rate limit
  python3 scripts/collect_etf_data.py --source all --rate-limit 2.0
        """
    )
    parser.add_argument(
        '--source',
        choices=['krx', 'etfcheck', 'all'],
        default='all',
        help='Data source to collect from'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Number of ETFs to collect (default: all)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test without actual collection'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment
    load_dotenv()

    # Print header
    print_banner("ETF Data Collection Script")

    print("\nConfiguration:")
    print(f"   Source: {args.source}")
    print(f"   Limit: {args.limit or 'All ETFs'}")
    print(f"   Rate Limit: {args.rate_limit}s between requests")
    print(f"   Dry Run: {args.dry_run}")

    # Initialize database
    print_section("Initializing Database")
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        return 1

    # Get ETF list
    print_section("Fetching ETF List")
    try:
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                # Filter for standard 6-digit tickers only (to avoid non-standard formats)
                cursor.execute("""
                    SELECT ticker, name, asset_type
                    FROM tickers
                    WHERE region='KR' AND asset_type='ETF'
                      AND ticker SIMILAR TO '[0-9]{6}'
                    ORDER BY ticker
                """)
                etfs = cursor.fetchall()

        if not etfs:
            logger.error("❌ No ETFs found in database")
            return 1

        total_etfs = len(etfs)
        etf_list = etfs[:args.limit] if args.limit else etfs

        logger.info(f"📊 Total ETFs in database: {total_etfs:,}")
        logger.info(f"📊 Selected for collection: {len(etf_list):,}")

        # Show sample
        print("\nSample ETFs:")
        for i, etf in enumerate(etf_list[:5], 1):
            print(f"   {i}. {etf['ticker']}: {etf['name']}")
        if len(etf_list) > 5:
            print(f"   ... and {len(etf_list) - 5} more")

    except Exception as e:
        logger.error(f"❌ Failed to fetch ETF list: {e}")
        return 1

    # Check existing data
    print_section("Checking Existing Data")
    try:
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM etf_details
                    WHERE region='KR'
                """)
                existing_count = cursor.fetchone()['count']

        logger.info(f"📊 Existing ETF details: {existing_count:,}")

        if existing_count > 0:
            logger.warning(f"⚠️  {existing_count} ETFs already have data")
            logger.warning("   This collection will update existing records")

    except Exception as e:
        logger.error(f"❌ Failed to check existing data: {e}")
        return 1

    # Dry run check
    if args.dry_run:
        print_section("Dry Run Mode")
        print("\n🔍 DRY RUN - No actual collection will occur")
        print("\nCollection plan:")
        print(f"   Source: {args.source}")
        print(f"   ETFs to collect: {len(etf_list):,}")
        print(f"   Estimated time: {len(etf_list) * args.rate_limit / 60:.1f} minutes")
        print("\n✅ Dry run complete - ready for actual collection")
        return 0

    # Initialize collector
    print_section("Initializing ETF Data Collector")
    try:
        collector = ETFDataCollector(
            db_manager=db,
            rate_limit=args.rate_limit
        )
        logger.info("✅ ETF Data Collector initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize collector: {e}")
        return 1

    # Confirm execution
    print("\n⚠️  WARNING: This will collect data from external sources")
    print(f"   Estimated time: {len(etf_list) * args.rate_limit / 60:.1f} minutes")
    print("   Press Ctrl+C to cancel within 5 seconds...")

    try:
        for i in range(5, 0, -1):
            print(f"   Starting in {i}...", end='\r', flush=True)
            time.sleep(1)
        print("\n")
    except KeyboardInterrupt:
        print("\n\n❌ Collection cancelled by user")
        return 0

    # Start collection
    print_banner("STARTING ETF DATA COLLECTION")
    start_time = time.time()

    try:
        # Collect data based on source
        ticker_list = [etf['ticker'] for etf in etf_list]

        if args.source == 'krx':
            logger.info("📊 Collecting KRX data (AUM, TER, tracking error)...")
            success_count = await collector.collect_krx_data(ticker_list)

        elif args.source == 'etfcheck':
            logger.info("📊 Collecting ETFCheck data (sector, theme, tracking index)...")
            success_count = await collector.collect_etfcheck_data(ticker_list)

        else:  # all
            logger.info("📊 Collecting all data sources...")
            success_count = await collector.collect_all_data(ticker_list)

        elapsed_time = time.time() - start_time

        # Post-collection validation
        print_banner("COLLECTION COMPLETE")

        print(f"\n⏱️  Duration: {elapsed_time/60:.1f} minutes ({elapsed_time:.0f} seconds)")
        print(f"📊 Success Rate: {success_count}/{len(etf_list)} ETFs ({success_count/len(etf_list)*100:.1f}%)")

        # Verify data in database
        print_section("Database Verification")
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                # Total count
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM etf_details
                    WHERE region='KR'
                """)
                total_count = cursor.fetchone()['count']

                # Sample verification
                cursor.execute("""
                    SELECT
                        ticker,
                        issuer,
                        sector_theme,
                        aum,
                        ter,
                        tracking_error_20d
                    FROM etf_details
                    WHERE region='KR'
                    ORDER BY ticker
                    LIMIT 5
                """)
                samples = cursor.fetchall()

        print(f"\n💾 Database:")
        print(f"   Total ETF details: {total_count:,}")
        print(f"   New/Updated records: {success_count:,}")

        print(f"\n📋 Sample ETF details:")
        for sample in samples:
            print(f"   {sample['ticker']}: {sample['issuer']}")
            print(f"      Sector: {sample['sector_theme']}")
            print(f"      AUM: {sample['aum']:,} 원" if sample['aum'] else "      AUM: N/A")
            print(f"      TER: {sample['ter']}%" if sample['ter'] else "      TER: N/A")

        # Success criteria
        print_banner("COLLECTION SUMMARY")
        if success_count >= len(etf_list) * 0.9:
            print("✅ COLLECTION SUCCESSFUL")
            print(f"   → {success_count:,} ETFs with complete data")
            print(f"   → Phase 1 ready for Phase 2 (ETF Screening Tool)")
        elif success_count >= len(etf_list) * 0.5:
            print("⚠️  COLLECTION PARTIAL SUCCESS")
            print(f"   → {success_count}/{len(etf_list)} ETFs collected")
            print(f"   → Review failures and retry missing ETFs")
        else:
            print("❌ COLLECTION FAILED")
            print(f"   → Only {success_count}/{len(etf_list)} ETFs succeeded")
            print(f"   → Check network connection and data sources")

        return 0 if success_count >= len(etf_list) * 0.9 else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        elapsed_time = time.time() - start_time
        print(f"   Elapsed time: {elapsed_time/60:.1f} minutes")

        # Check partial results
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM etf_details
                    WHERE region='KR'
                """)
                partial_count = cursor.fetchone()['count']

        print(f"   Partial records saved: {partial_count:,}")
        return 1

    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
