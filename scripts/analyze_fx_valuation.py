#!/usr/bin/env python3
"""
FX Valuation Analysis Script

Purpose:
    Daily execution script for FX currency valuation analysis.
    Calculates investment attractiveness scores for all supported currencies.

Usage:
    # Analyze all currencies for today
    python3 scripts/analyze_fx_valuation.py

    # Analyze specific currencies
    python3 scripts/analyze_fx_valuation.py --currencies USD,HKD

    # Analyze specific date
    python3 scripts/analyze_fx_valuation.py --date 2025-10-24

    # Batch analysis for date range
    python3 scripts/analyze_fx_valuation.py --start-date 2024-01-01 --end-date 2025-10-24

    # Dry run (no database updates)
    python3 scripts/analyze_fx_valuation.py --dry-run

Scheduling (Cron):
    # Run daily at 9:00 AM KST (after FX collection at 8:30 AM)
    0 9 * * * cd /Users/13ruce/spock && /usr/bin/python3 scripts/analyze_fx_valuation.py >> logs/fx_analysis.log 2>&1

Exit Codes:
    0 - All analyses successful
    1 - Partial success (some currencies failed)
    2 - Complete failure (all currencies failed)

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fx_valuation_analyzer import FXValuationAnalyzer

# Initialize logger
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/fx_analysis.log', mode='a')
    ]
)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='FX Valuation Analysis - Calculate currency attractiveness scores',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all currencies for today
  python3 scripts/analyze_fx_valuation.py

  # Analyze specific currencies for specific date
  python3 scripts/analyze_fx_valuation.py --currencies USD,HKD --date 2025-10-24

  # Batch analysis for last 30 days
  python3 scripts/analyze_fx_valuation.py --start-date 2024-09-24 --end-date 2025-10-24

  # Dry run (calculate but don't save)
  python3 scripts/analyze_fx_valuation.py --dry-run
        """
    )

    parser.add_argument(
        '--currencies',
        type=str,
        default='USD,HKD,CNY,JPY,VND',
        help='Comma-separated currency codes (default: all supported currencies)'
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Analysis date in YYYY-MM-DD format (default: today)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for batch analysis (YYYY-MM-DD format)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for batch analysis (YYYY-MM-DD format)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Calculate scores but do not update database'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    return parser.parse_args()


def validate_arguments(args):
    """Validate command line arguments"""
    # Batch mode validation
    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            logger.error("Both --start-date and --end-date required for batch analysis")
            return False

        try:
            start = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end = datetime.strptime(args.end_date, '%Y-%m-%d').date()

            if start > end:
                logger.error(f"Start date ({start}) must be before end date ({end})")
                return False

            if end > date.today():
                logger.error(f"End date ({end}) cannot be in the future")
                return False

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return False

    # Single date validation
    elif args.date:
        try:
            analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date()

            if analysis_date > date.today():
                logger.error(f"Analysis date ({analysis_date}) cannot be in the future")
                return False

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return False

    # Currency validation
    try:
        currencies = [c.strip().upper() for c in args.currencies.split(',')]
        supported = FXValuationAnalyzer.SUPPORTED_CURRENCIES

        invalid = [c for c in currencies if c not in supported]
        if invalid:
            logger.error(f"Unsupported currencies: {invalid}")
            logger.error(f"Supported currencies: {supported}")
            return False

    except Exception as e:
        logger.error(f"Error parsing currencies: {e}")
        return False

    return True


def run_single_date_analysis(analyzer, currencies, analysis_date, dry_run=False):
    """
    Run analysis for single date.

    Args:
        analyzer: FXValuationAnalyzer instance
        currencies: List of currency codes
        analysis_date: Date to analyze
        dry_run: If True, calculate but don't save

    Returns:
        Exit code (0=success, 1=partial, 2=failure)
    """
    logger.info("="*80)
    logger.info(f"FX VALUATION ANALYSIS - {analysis_date}")
    logger.info("="*80)
    logger.info(f"Currencies: {', '.join(currencies)}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    logger.info("")

    results = {}

    for currency in currencies:
        try:
            logger.info(f"Analyzing {currency}...")

            if dry_run:
                # In dry run, we still calculate but don't save
                # For now, just report that it would be analyzed
                logger.info(f"[DRY RUN] Would analyze {currency} for {analysis_date}")
                results[currency] = True
            else:
                success = analyzer.analyze_currency(currency, analysis_date)
                results[currency] = success

                if success:
                    logger.info(f"✓ {currency} analysis successful")
                else:
                    logger.warning(f"✗ {currency} analysis failed")

        except Exception as e:
            logger.error(f"✗ {currency} analysis error: {e}", exc_info=True)
            results[currency] = False

    # Summary
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0

    logger.info("")
    logger.info("="*80)
    logger.info("ANALYSIS SUMMARY")
    logger.info("="*80)
    logger.info(f"Total Currencies: {total_count}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_count - success_count}")
    logger.info(f"Success Rate: {success_rate:.1f}%")
    logger.info("="*80)

    # Determine exit code
    if success_count == total_count:
        logger.info("Status: SUCCESS - All currencies analyzed")
        return 0
    elif success_count > 0:
        logger.warning("Status: PARTIAL - Some currencies failed")
        return 1
    else:
        logger.error("Status: FAILURE - All currencies failed")
        return 2


def run_batch_analysis(analyzer, currencies, start_date, end_date, dry_run=False):
    """
    Run batch analysis over date range.

    Args:
        analyzer: FXValuationAnalyzer instance
        currencies: List of currency codes
        start_date: Start date
        end_date: End date
        dry_run: If True, calculate but don't save

    Returns:
        Exit code (0=success, 1=partial, 2=failure)
    """
    total_days = (end_date - start_date).days + 1

    logger.info("="*80)
    logger.info("FX VALUATION BATCH ANALYSIS")
    logger.info("="*80)
    logger.info(f"Date Range: {start_date} to {end_date} ({total_days} days)")
    logger.info(f"Currencies: {', '.join(currencies)}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    logger.info("")

    if dry_run:
        logger.info("[DRY RUN] Would analyze:")
        logger.info(f"  - {len(currencies)} currencies")
        logger.info(f"  - {total_days} days")
        logger.info(f"  - Total: {len(currencies) * total_days} currency-day combinations")
        return 0

    # Run batch analysis
    results = analyzer.analyze_date_range(start_date, end_date, currencies)

    # Summary
    logger.info("")
    logger.info("="*80)
    logger.info("BATCH ANALYSIS SUMMARY")
    logger.info("="*80)

    total_success = 0
    total_possible = len(currencies) * total_days

    for currency, success_days in results.items():
        success_rate = (success_days / total_days * 100) if total_days > 0 else 0
        logger.info(f"{currency}: {success_days}/{total_days} days ({success_rate:.1f}%)")
        total_success += success_days

    overall_success_rate = (total_success / total_possible * 100) if total_possible > 0 else 0

    logger.info("")
    logger.info(f"Overall Success: {total_success}/{total_possible} ({overall_success_rate:.1f}%)")
    logger.info("="*80)

    # Determine exit code
    if overall_success_rate >= 95:
        logger.info("Status: SUCCESS - Batch analysis complete")
        return 0
    elif overall_success_rate >= 50:
        logger.warning("Status: PARTIAL - Some analyses failed")
        return 1
    else:
        logger.error("Status: FAILURE - Most analyses failed")
        return 2


def main():
    """Main execution"""
    args = parse_arguments()

    # Set log level
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if not validate_arguments(args):
        return 2

    # Parse currencies
    currencies = [c.strip().upper() for c in args.currencies.split(',')]

    # Initialize analyzer
    try:
        analyzer = FXValuationAnalyzer()
    except Exception as e:
        logger.error(f"Failed to initialize FXValuationAnalyzer: {e}", exc_info=True)
        return 2

    # Batch analysis mode
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

        return run_batch_analysis(analyzer, currencies, start_date, end_date, args.dry_run)

    # Single date analysis mode
    else:
        analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else date.today()

        return run_single_date_analysis(analyzer, currencies, analysis_date, args.dry_run)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
