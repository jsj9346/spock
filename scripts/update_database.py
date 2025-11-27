#!/usr/bin/env python3
"""
Unified Database Update Script

Single entry point for all database update operations.
Coordinates ticker updates, OHLCV collection, fundamental data backfill,
and dividend yield calculation across multiple markets.

Features:
- Single command execution for full DB update
- Checkpoint-based recovery
- Incremental updates
- Dry-run mode
- Step/region selection
- Progress tracking

Usage:
    # Full update (all regions, all steps)
    python3 scripts/update_database.py

    # Specific regions
    python3 scripts/update_database.py --regions KR US

    # Specific steps
    python3 scripts/update_database.py --steps tickers ohlcv fundamentals

    # Dry run (preview only)
    python3 scripts/update_database.py --dry-run

    # Incremental update (only missing data)
    python3 scripts/update_database.py --incremental

    # Resume from checkpoint
    python3 scripts/update_database.py --resume

    # Background execution
    nohup python3 scripts/update_database.py > log/db_update_$(date +%Y%m%d).log 2>&1 &

Author: Quant Investment Platform
Date: 2025-11-01
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Setup logging configuration

    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional log file path
    """
    # Log level
    log_level = logging.DEBUG if verbose else logging.INFO

    # Log format
    log_format = '%(asctime)s | %(levelname)-8s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Handlers
    handlers = [logging.StreamHandler(sys.stdout)]

    # Add file handler if specified
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    # Configure logging
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    # Suppress verbose libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('psycopg2').setLevel(logging.WARNING)


def print_banner():
    """Print application banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║      📊 Quant Investment Platform - Database Update Tool         ║
║                                                                   ║
║      Unified database update script for all markets              ║
║      Version: 1.0.0                                               ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Unified Database Update Script - Quant Investment Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full update (all regions, all steps)
  %(prog)s

  # Specific regions only
  %(prog)s --regions KR US

  # Specific steps only
  %(prog)s --steps tickers ohlcv fundamentals

  # Dry run (preview without changes)
  %(prog)s --dry-run

  # Incremental update (only missing data)
  %(prog)s --incremental

  # Resume from latest checkpoint
  %(prog)s --resume

  # Limit processing (for testing)
  %(prog)s --limit 10

  # Background execution
  nohup %(prog)s > log/db_update_$(date +%%Y%%m%%d).log 2>&1 &

For more information, see docs/DB_UPDATE_UNIFIED_SCRIPT_GUIDE.md
        """
    )

    # Region selection
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['KR', 'US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to update (default: all)'
    )

    # Step selection
    parser.add_argument(
        '--steps',
        nargs='+',
        choices=['tickers', 'ohlcv', 'fundamentals', 'cash_backfill', 'fundamental_ratios',
                 'daily_valuation', 'technical_indicators', 'dividend', 'quarterly', 'fx_tracking'],
        help='Steps to execute (default: all except quarterly)'
    )

    # Execution modes
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database writes'
    )

    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only update missing data (skip existing)'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from latest checkpoint'
    )

    # Error handling
    parser.add_argument(
        '--fail-fast',
        action='store_true',
        help='Stop immediately on first error (default: continue)'
    )

    # Performance
    parser.add_argument(
        '--limit',
        type=int,
        metavar='N',
        help='Limit number of tickers per step (for testing)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=250,
        metavar='N',
        help='Number of days to collect per ticker (default: 250, use 7 for quick refresh)'
    )

    # Validation
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip data quality validation'
    )

    # Logging
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (DEBUG) logging'
    )

    parser.add_argument(
        '--log-file',
        metavar='PATH',
        help='Log file path (default: log/db_update_YYYYMMDD_HHMMSS.log)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()

    # Setup logging
    log_file = args.log_file or f"log/db_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    setup_logging(verbose=args.verbose, log_file=log_file)

    logger = logging.getLogger(__name__)

    try:
        # Print banner
        print_banner()

        # Log arguments
        logger.info(f"Arguments: {vars(args)}")

        # Initialize database connection
        logger.info("Connecting to PostgreSQL database...")
        db = PostgresDatabaseManager()
        logger.info("✅ Database connection established")

        # Initialize orchestrator
        orchestrator = DatabaseUpdateOrchestrator(db, config={
            'fail_fast': args.fail_fast,
            'limit': args.limit,
            'validate': not args.no_validate
        })

        # Determine regions
        regions = args.regions or ['KR', 'US', 'HK', 'JP', 'CN', 'VN']

        # Determine steps
        steps = args.steps  # None means default (all except quarterly)

        # Run pipeline
        result = orchestrator.run_pipeline(
            regions=regions,
            steps=steps,
            dry_run=args.dry_run,
            incremental=args.incremental,
            resume=args.resume,
            days=args.days  # Pass days parameter for OHLCV collection
        )

        # Check success
        if result['steps_failed']:
            logger.error(f"❌ Pipeline completed with errors: {result['steps_failed']}")
            sys.exit(1)
        else:
            logger.info("✅ Pipeline completed successfully")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Pipeline interrupted by user (Ctrl+C)")
        logger.info("💡 Use --resume to continue from last checkpoint")
        sys.exit(130)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

        # Print full traceback in verbose mode
        if args.verbose:
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")

        sys.exit(1)

    finally:
        # Close database connection pool
        try:
            db.close_pool()
            logger.info("Database connection pool closed")
        except:
            pass


if __name__ == '__main__':
    main()
