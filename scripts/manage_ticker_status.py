#!/usr/bin/env python3
"""
Ticker Status Management CLI

Manage yfinance ticker status for data collection optimization.

Usage:
    # View status summary for all regions
    python3 scripts/manage_ticker_status.py --summary

    # View status summary for specific region
    python3 scripts/manage_ticker_status.py --region JP --summary

    # View failure reasons
    python3 scripts/manage_ticker_status.py --region US --fail-summary

    # List skip tickers
    python3 scripts/manage_ticker_status.py --region US --list-skip

    # Add to blacklist
    python3 scripts/manage_ticker_status.py --region US --blacklist ABR/D --reason "preferred_stock"

    # Remove from blacklist
    python3 scripts/manage_ticker_status.py --region US --unblacklist ABR/D

    # Reset ticker status (for re-verification)
    python3 scripts/manage_ticker_status.py --region JP --reset 9224

    # Auto-detect unsupported tickers (US preferred stocks)
    python3 scripts/manage_ticker_status.py --region US --auto-detect

    # Initialize status from OHLCV data
    python3 scripts/manage_ticker_status.py --region JP --init-from-ohlcv

    # List stale tickers (need re-verification)
    python3 scripts/manage_ticker_status.py --region JP --list-stale --days 30
"""

import sys
import os
import argparse
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.ticker_status_manager import TickerStatusManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_summary(tsm: TickerStatusManager, regions: list):
    """Print status summary for regions"""
    print("\n" + "=" * 70)
    print("                    TICKER STATUS SUMMARY")
    print("=" * 70)
    print(f"{'Region':^8} | {'Total':^8} | {'Active':^8} | {'Unknown':^8} | {'Delisted':^8} | {'Unsupported':^11} | {'Blacklist':^9} | {'Skip':^8}")
    print("-" * 70)

    totals = {'total': 0, 'active': 0, 'unknown': 0, 'delisted': 0, 'unsupported': 0, 'blacklist': 0, 'skip': 0}

    for region in regions:
        s = tsm.get_status_summary(region)
        print(f"{region:^8} | {s['total']:>8,} | {s['active']:>8,} | {s['unknown']:>8,} | {s.get('delisted', 0):>8,} | {s.get('unsupported', 0):>11,} | {s.get('blacklist', 0):>9,} | {s['skip_count']:>8,}")

        totals['total'] += s['total']
        totals['active'] += s['active']
        totals['unknown'] += s['unknown']
        totals['delisted'] += s.get('delisted', 0)
        totals['unsupported'] += s.get('unsupported', 0)
        totals['blacklist'] += s.get('blacklist', 0)
        totals['skip'] += s['skip_count']

    print("-" * 70)
    print(f"{'TOTAL':^8} | {totals['total']:>8,} | {totals['active']:>8,} | {totals['unknown']:>8,} | {totals['delisted']:>8,} | {totals['unsupported']:>11,} | {totals['blacklist']:>9,} | {totals['skip']:>8,}")
    print("=" * 70 + "\n")


def print_fail_summary(tsm: TickerStatusManager, region: str):
    """Print failure reason summary"""
    print(f"\n=== Failure Summary for {region} ===")

    fails = tsm.get_fail_summary(region)
    if not fails:
        print("  No failures recorded")
        return

    print(f"{'Reason':<30} | {'Count':>8}")
    print("-" * 42)
    for row in fails:
        print(f"{row['yf_fail_reason']:<30} | {row['count']:>8,}")


def print_skip_tickers(tsm: TickerStatusManager, region: str, limit: int = 50):
    """Print list of skip tickers"""
    tickers = tsm.get_skip_tickers(region)
    print(f"\n=== Skip Tickers for {region} ({len(tickers)} total) ===")

    if not tickers:
        print("  No skip tickers")
        return

    # Show first N tickers
    for ticker in tickers[:limit]:
        status = tsm.get_status(ticker, region)
        if status:
            print(f"  {ticker:<12} | {status['yf_status']:<12} | {status.get('yf_fail_reason', '-')}")

    if len(tickers) > limit:
        print(f"  ... and {len(tickers) - limit} more")


def print_stale_tickers(tsm: TickerStatusManager, region: str, days: int):
    """Print list of stale tickers needing re-verification"""
    tickers = tsm.verify_stale_tickers(region, days)
    print(f"\n=== Stale Tickers for {region} (>{days} days, {len(tickers)} total) ===")

    if not tickers:
        print("  No stale tickers")
        return

    for ticker in tickers[:50]:
        status = tsm.get_status(ticker, region)
        if status:
            last_check = status.get('yf_last_check')
            last_check_str = last_check.strftime('%Y-%m-%d') if last_check else 'Never'
            print(f"  {ticker:<12} | {status['yf_status']:<12} | Last check: {last_check_str}")

    if len(tickers) > 50:
        print(f"  ... and {len(tickers) - 50} more")


def main():
    parser = argparse.ArgumentParser(
        description='Manage yfinance ticker status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('--region', type=str, default=None,
                        help='Target region (KR, JP, US, HK, CN, VN). Default: all')

    # View commands
    parser.add_argument('--summary', action='store_true',
                        help='Show status summary')
    parser.add_argument('--fail-summary', action='store_true',
                        help='Show failure reason summary')
    parser.add_argument('--list-skip', action='store_true',
                        help='List skip tickers')
    parser.add_argument('--list-stale', action='store_true',
                        help='List stale tickers needing re-verification')
    parser.add_argument('--days', type=int, default=30,
                        help='Days threshold for stale detection (default: 30)')

    # Modify commands
    parser.add_argument('--blacklist', type=str,
                        help='Add ticker to blacklist')
    parser.add_argument('--unblacklist', type=str,
                        help='Remove ticker from blacklist')
    parser.add_argument('--reset', type=str,
                        help='Reset ticker status to unknown')
    parser.add_argument('--reason', type=str, default='manual',
                        help='Reason for blacklist (default: manual)')

    # Batch commands
    parser.add_argument('--auto-detect', action='store_true',
                        help='Auto-detect unsupported tickers (e.g., US preferred stocks)')
    parser.add_argument('--init-from-ohlcv', action='store_true',
                        help='Initialize status from existing OHLCV data')

    args = parser.parse_args()

    # Initialize
    db = PostgresDatabaseManager()
    tsm = TickerStatusManager(db)

    # Define regions
    all_regions = ['KR', 'JP', 'US', 'HK', 'CN', 'VN']
    regions = [args.region] if args.region else all_regions

    # Execute commands
    if args.summary:
        print_summary(tsm, regions)

    elif args.fail_summary:
        if not args.region:
            print("Error: --region required for --fail-summary")
            return 1
        print_fail_summary(tsm, args.region)

    elif args.list_skip:
        if not args.region:
            print("Error: --region required for --list-skip")
            return 1
        print_skip_tickers(tsm, args.region)

    elif args.list_stale:
        if not args.region:
            print("Error: --region required for --list-stale")
            return 1
        print_stale_tickers(tsm, args.region, args.days)

    elif args.blacklist:
        if not args.region:
            print("Error: --region required for --blacklist")
            return 1
        tsm.set_blacklist(args.blacklist, args.region, args.reason)
        print(f"✅ Added {args.blacklist} ({args.region}) to blacklist: {args.reason}")

    elif args.unblacklist:
        if not args.region:
            print("Error: --region required for --unblacklist")
            return 1
        tsm.clear_blacklist(args.unblacklist, args.region)
        print(f"✅ Removed {args.unblacklist} ({args.region}) from blacklist")

    elif args.reset:
        if not args.region:
            print("Error: --region required for --reset")
            return 1
        tsm.reset_status(args.reset, args.region)
        print(f"✅ Reset {args.reset} ({args.region}) to unknown status")

    elif args.auto_detect:
        if args.region:
            regions = [args.region]

        total = 0
        for region in regions:
            count = tsm.auto_detect_unsupported(region)
            if count > 0:
                print(f"  {region}: {count} unsupported tickers detected")
                total += count

        print(f"✅ Total: {total} unsupported tickers detected")

    elif args.init_from_ohlcv:
        if args.region:
            regions = [args.region]

        for region in regions:
            result = tsm.init_status_from_ohlcv(region)
            print(f"  {region}: {result['active']} tickers marked as active")

        print("✅ Status initialization complete")

    else:
        # Default: show summary
        print_summary(tsm, regions)

    return 0


if __name__ == "__main__":
    sys.exit(main())
