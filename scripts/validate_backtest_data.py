#!/usr/bin/env python3
"""
Data Quality Validation Script for Backtesting

Validates and optionally fixes data quality issues before backtesting.

Usage:
    # Check data quality
    python3 scripts/validate_backtest_data.py --region KR

    # Check and automatically fix duplicates
    python3 scripts/validate_backtest_data.py --region KR --fix

Examples:
    # Validate KR market data
    python3 scripts/validate_backtest_data.py --region KR

    # Validate and fix HK market data
    python3 scripts/validate_backtest_data.py --region HK --fix
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import json
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.backtesting.backtest_runner import BacktestRunner
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.constants.regions import VALID_REGIONS


def colored(text: str, color: str = '') -> str:
    """Apply color to text (simple version)"""
    colors = {
        'green': '\033[92m',
        'yellow': '\033[93m',
        'red': '\033[91m',
        'blue': '\033[94m',
        'reset': '\033[0m'
    }

    if color in colors:
        return f"{colors[color]}{text}{colors['reset']}"
    return text


def main():
    parser = argparse.ArgumentParser(
        description='Validate data quality for backtesting'
    )
    parser.add_argument(
        '--region',
        type=str,
        default='KR',
        choices=VALID_REGIONS,
        help='Market region to validate (default: KR)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix duplicate data'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for validation report (JSON)'
    )

    args = parser.parse_args()

    # Initialize database
    logger.info(f"🚀 Starting data quality validation for {args.region}")
    db = PostgresDatabaseManager()

    # Run validation
    results = BacktestRunner.validate_data_quality(
        db=db,
        region=args.region,
        fix_duplicates=args.fix
    )

    # Print results
    print("\n" + "="*60)
    print(colored(f"📊 Data Quality Validation Report - {args.region}", 'blue'))
    print("="*60 + "\n")

    # Coverage
    print(colored("📈 Data Coverage:", 'blue'))
    if results['coverage']:
        print(f"  Total Tickers: {results['coverage']['total_tickers']:,}")
        print(f"  Date Range: {results['coverage']['date_range']}")
        print(f"  Total Records: {results['coverage']['total_records']:,}")
    print()

    # Duplicates
    if results['duplicates']:
        if 'factor_scores' in results['duplicates']:
            count = results['duplicates']['factor_scores']
            print(colored(f"⚠️  Duplicate Entries:", 'yellow'))
            print(f"  factor_scores: {count} duplicates found")

            if 'fixed' in results['duplicates']:
                fixed = results['duplicates']['fixed']
                print(colored(f"  ✅ Fixed: {fixed} duplicates removed", 'green'))
        print()

    # NULL values
    if results['null_values']:
        null_close = results['null_values']['null_close']
        if null_close > 0:
            print(colored(f"⚠️  NULL Values:", 'yellow'))
            print(f"  Close prices: {null_close} NULL values")
        print()

    # Warnings
    if results['warnings']:
        print(colored(f"⚠️  Warnings ({len(results['warnings'])}):", 'yellow'))
        for warning in results['warnings']:
            print(f"  - {warning}")
        print()

    # Overall status
    print("="*60)
    if results['passed']:
        print(colored("✅ VALIDATION PASSED", 'green'))
        print("\nData is ready for backtesting!")
    else:
        print(colored("❌ VALIDATION FAILED", 'red'))
        print(f"\nFound {len(results['warnings'])} issues.")

        if not args.fix:
            print("\nRun with --fix flag to automatically fix duplicate data:")
            print(colored(f"  python3 scripts/validate_backtest_data.py --region {args.region} --fix", 'blue'))
    print("="*60 + "\n")

    # Save to file if requested
    if args.output:
        # Convert datetime to string for JSON serialization
        results_copy = results.copy()
        results_copy['timestamp'] = results_copy['timestamp'].isoformat()

        with open(args.output, 'w') as f:
            json.dump(results_copy, f, indent=2)

        logger.info(f"📄 Validation report saved to: {args.output}")

    # Exit code
    sys.exit(0 if results['passed'] else 1)


if __name__ == "__main__":
    main()
