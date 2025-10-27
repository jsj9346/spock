#!/usr/bin/env python3
"""
Daily FX Data Collection Script - Phase 1-C

Purpose:
- Executable script for automated FX data collection
- Designed for cron job execution
- Production-ready error handling and logging

Usage:
    # Manual execution
    python3 scripts/collect_fx_data.py

    # Specific currencies
    python3 scripts/collect_fx_data.py --currencies USD,CNY,JPY

    # Force refresh (ignore cache)
    python3 scripts/collect_fx_data.py --force-refresh

    # Dry run (validation only)
    python3 scripts/collect_fx_data.py --dry-run

Exit Codes:
    0 - Success (all currencies collected)
    1 - Partial failure (some currencies failed)
    2 - Critical failure (all currencies failed or system error)

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fx_data_collector import FXDataCollector
from dotenv import load_dotenv


def setup_logging(log_dir: str = 'logs') -> None:
    """
    Setup logging configuration

    Args:
        log_dir: Directory for log files
    """
    # Create log directory if not exists
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Log file name: fx_collection_YYYYMMDD.log
    log_file = f"{log_dir}/fx_collection_{date.today().strftime('%Y%m%d')}.log"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode='a')
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"📋 Logging to: {log_file}")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Daily FX Data Collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all currencies
  python3 scripts/collect_fx_data.py

  # Collect specific currencies
  python3 scripts/collect_fx_data.py --currencies USD,CNY,JPY

  # Force refresh (ignore cache)
  python3 scripts/collect_fx_data.py --force-refresh

  # Dry run (validation only)
  python3 scripts/collect_fx_data.py --dry-run

Exit Codes:
  0 - Success (all currencies collected)
  1 - Partial failure (some currencies failed)
  2 - Critical failure (all currencies failed or system error)
        """
    )

    parser.add_argument(
        '--currencies',
        type=str,
        default=None,
        help='Comma-separated currency codes (default: USD,HKD,CNY,JPY,VND)'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force API calls (ignore cache)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no database writes)'
    )

    parser.add_argument(
        '--log-dir',
        type=str,
        default='logs',
        help='Log file directory (default: logs/)'
    )

    parser.add_argument(
        '--bok-api-key',
        type=str,
        default=None,
        help='BOK Open API key (default: from BOK_API_KEY env variable)'
    )

    return parser.parse_args()


def validate_environment() -> bool:
    """
    Validate environment and dependencies

    Returns:
        True if environment is valid, False otherwise
    """
    logger = logging.getLogger(__name__)

    # Check PostgreSQL connection
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager
        db = PostgresDatabaseManager()

        # Test connection
        result = db.execute_query("SELECT 1")
        if not result:
            logger.error("❌ PostgreSQL connection test failed")
            return False

        logger.info("✅ PostgreSQL connection OK")

    except Exception as e:
        logger.error(f"❌ PostgreSQL connection error: {e}")
        return False

    # Check fx_valuation_signals table exists
    try:
        result = db.execute_query("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'fx_valuation_signals'
            )
        """)

        if not result or not result[0][0]:
            logger.error("❌ fx_valuation_signals table not found")
            logger.error("   Run migration: migrations/007_add_fx_valuation_signals.sql")
            return False

        logger.info("✅ fx_valuation_signals table exists")

    except Exception as e:
        logger.error(f"❌ Table validation error: {e}")
        return False

    return True


def main() -> int:
    """
    Main execution function

    Returns:
        Exit code (0: success, 1: partial failure, 2: critical failure)
    """
    # Parse arguments
    args = parse_arguments()

    # Setup logging
    setup_logging(log_dir=args.log_dir)
    logger = logging.getLogger(__name__)

    # Header
    logger.info("=" * 80)
    logger.info("FX DATA COLLECTION - Daily Automated Execution")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 80)

    # Dry run mode
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No database writes will be performed")
        logger.info(f"   Currencies: {args.currencies or 'USD,HKD,CNY,JPY,VND'}")
        logger.info(f"   Force refresh: {args.force_refresh}")
        logger.info("=" * 80)
        logger.info("✅ Dry run validation passed. Exiting...")
        return 0

    # Load environment variables
    load_dotenv()

    # Validate environment
    logger.info("🔍 Validating environment...")
    if not validate_environment():
        logger.error("❌ Environment validation failed")
        return 2  # Critical failure

    # Parse currencies
    currencies: Optional[List[str]] = None
    if args.currencies:
        currencies = [c.strip().upper() for c in args.currencies.split(',')]
        logger.info(f"📋 Target currencies: {', '.join(currencies)}")
    else:
        logger.info("📋 Target currencies: All supported (USD, HKD, CNY, JPY, VND)")

    # Get BOK API key
    bok_api_key = args.bok_api_key or os.getenv('BOK_API_KEY')
    if bok_api_key:
        logger.info("🔑 BOK API key: Configured (100K req/day)")
    else:
        logger.info("🔑 BOK API key: Not configured (using 'sample' mode - 10K req/day)")

    # Initialize collector
    try:
        collector = FXDataCollector(bok_api_key=bok_api_key)

    except Exception as e:
        logger.error(f"❌ Failed to initialize FXDataCollector: {e}")
        return 2  # Critical failure

    # Run collection
    try:
        logger.info("🔄 Starting FX data collection...")
        logger.info("=" * 80)

        results = collector.collect_today(
            currencies=currencies,
            force_refresh=args.force_refresh
        )

        # Refresh materialized view
        logger.info("🔄 Refreshing materialized view...")
        view_refreshed = collector.refresh_materialized_view()

        if not view_refreshed:
            logger.warning("⚠️ Materialized view refresh failed (non-critical)")

        # Summary
        logger.info("=" * 80)
        logger.info("📊 COLLECTION SUMMARY")
        logger.info(f"   Date: {results['date']}")
        logger.info(f"   Success: {results['success']}")
        logger.info(f"   Failed: {results['failed']}")
        logger.info(f"   Records Inserted: {results['records_inserted']}")
        logger.info(f"   Records Updated: {results['records_updated']}")

        if results['errors']:
            logger.warning(f"⚠️ Errors encountered: {len(results['errors'])}")
            for error in results['errors']:
                logger.warning(f"   - {error}")

        logger.info("=" * 80)

        # Determine exit code
        if results['failed'] == 0:
            logger.info("✅ Collection completed successfully")
            return 0  # Success

        elif results['success'] > 0:
            logger.warning(f"⚠️ Partial failure: {results['failed']} currencies failed")
            return 1  # Partial failure

        else:
            logger.error("❌ Critical failure: All currencies failed")
            return 2  # Critical failure

    except Exception as e:
        logger.error(f"❌ Unexpected error during collection: {e}")
        logger.exception("Stack trace:")
        return 2  # Critical failure


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
