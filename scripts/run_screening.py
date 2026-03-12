#!/usr/bin/env python3
"""
Stock Screening CLI - Phase 2.2

Command-line interface for stock screening with technical and fundamental filters.

Usage:
    # Technical screening - oversold stocks
    python3 scripts/run_screening.py technical --region HK --rsi-max 35

    # Value screening - undervalued stocks
    python3 scripts/run_screening.py value --region US --per-max 15 --pbr-max 3

    # Export results to file
    python3 scripts/run_screening.py technical --region HK --output /tmp/oversold.csv

Examples:
    # HK oversold stocks (RSI < 35)
    python3 scripts/run_screening.py technical --region HK --rsi-max 35 --limit 50

    # US value stocks (PER <= 15, PBR <= 3, MCap > $1B)
    python3 scripts/run_screening.py value --region US --per-max 15 --pbr-max 3

    # KR downtrend stocks with low RSI
    python3 scripts/run_screening.py technical --region KR --rsi-max 30 --ma-trend downtrend
"""

import sys
import argparse
from pathlib import Path
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.screening import StockScreener
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.constants.regions import VALID_REGIONS


def colored(text: str, color: str = '') -> str:
    """Apply color to text."""
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


def print_results(result):
    """Print screening results in a formatted table."""
    print("\n" + "="*60)
    print(colored(f"📊 Screening Results - {result.region} | {result.filter_type.upper()}", 'blue'))
    print("="*60 + "\n")

    # Summary
    print(colored("Summary:", 'blue'))
    print(f"  Total Results: {result.total_results}")
    print(f"  Filter Type: {result.filter_type}")
    print(f"  Region: {result.region}")
    print(f"  Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Parameters
    print(colored("Parameters:", 'blue'))
    for key, value in result.parameters.items():
        print(f"  {key}: {value}")
    print()

    # Top results
    if len(result.data) > 0:
        print(colored(f"Top {min(20, len(result.data))} Results:", 'blue'))
        print()

        # Display first 20 rows
        display_df = result.data.head(20)
        print(display_df.to_string(index=False))
        print()

        if len(result.data) > 20:
            print(colored(f"... and {len(result.data) - 20} more results", 'yellow'))
            print()
    else:
        print(colored("❌ No results found", 'red'))
        print()

    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Stock screening with technical and fundamental filters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Technical screening - oversold stocks:
    python3 scripts/run_screening.py technical --region HK --rsi-max 35

  Value screening - undervalued stocks:
    python3 scripts/run_screening.py value --region US --per-max 15 --pbr-max 3

  Export to CSV:
    python3 scripts/run_screening.py technical --region HK --output /tmp/oversold.csv
        """
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='filter_type', required=True)

    # Technical screening
    technical = subparsers.add_parser(
        'technical',
        help='Screen stocks based on technical indicators'
    )
    technical.add_argument('--region', type=str, default='HK', choices=VALID_REGIONS)
    technical.add_argument('--rsi-min', type=float, default=0.0, help='Minimum RSI (default: 0.0)')
    technical.add_argument('--rsi-max', type=float, default=35.0, help='Maximum RSI (default: 35.0)')
    technical.add_argument('--ma-trend', type=str, choices=['uptrend', 'downtrend'], help='MA trend filter')
    technical.add_argument('--limit', type=int, default=100, help='Max results (default: 100)')
    technical.add_argument('--output', type=str, help='Output file (CSV or Excel)')

    # Value screening
    value = subparsers.add_parser(
        'value',
        help='Screen stocks based on value factors'
    )
    value.add_argument('--region', type=str, default='US', choices=VALID_REGIONS)
    value.add_argument('--per-max', type=float, default=15.0, help='Max P/E ratio (default: 15.0)')
    value.add_argument('--pbr-max', type=float, default=3.0, help='Max P/B ratio (default: 3.0)')
    value.add_argument('--market-cap-min', type=float, default=1e9, help='Min market cap (default: $1B)')
    value.add_argument('--dividend-yield-min', type=float, default=0.0, help='Min dividend yield % (default: 0.0)')
    value.add_argument('--limit', type=int, default=100, help='Max results (default: 100)')
    value.add_argument('--output', type=str, help='Output file (CSV or Excel)')

    args = parser.parse_args()

    # Initialize database
    logger.info("🚀 Starting stock screening...")
    db = PostgresDatabaseManager()

    # Initialize screener
    screener = StockScreener(db)

    # Execute screening
    if args.filter_type == 'technical':
        result = screener.screen_technical(
            region=args.region,
            rsi_min=args.rsi_min,
            rsi_max=args.rsi_max,
            ma_trend=args.ma_trend,
            limit=args.limit
        )
    elif args.filter_type == 'value':
        result = screener.screen_value(
            region=args.region,
            per_max=args.per_max,
            pbr_max=args.pbr_max,
            market_cap_min=args.market_cap_min,
            dividend_yield_min=args.dividend_yield_min,
            limit=args.limit
        )
    else:
        print(colored(f"❌ Unknown filter type: {args.filter_type}", 'red'))
        sys.exit(1)

    # Print results
    print_results(result)

    # Export if requested
    if args.output:
        if args.output.endswith('.xlsx'):
            result.to_excel(args.output)
        else:
            result.to_csv(args.output)

        print(colored(f"✅ Results exported to: {args.output}", 'green'))
        print()


if __name__ == "__main__":
    main()
