#!/usr/bin/env python3
"""
Blacklist Management CLI Tool

Command-line interface for managing stock blacklist (DB-based and file-based).

Usage:
    # Add ticker to file blacklist (temporary exclusion)
    python3 scripts/manage_blacklist.py add --ticker 005930 --region KR --reason "임시 제외 - 분석 대기"

    # Add with expiry date
    python3 scripts/manage_blacklist.py add --ticker TSLA --region US --reason "변동성 과다" --expire 2025-12-31

    # Remove from file blacklist
    python3 scripts/manage_blacklist.py remove --ticker 005930 --region KR

    # Deactivate in DB (permanent)
    python3 scripts/manage_blacklist.py deactivate --ticker 005930 --region KR --reason "상장폐지"

    # Reactivate in DB
    python3 scripts/manage_blacklist.py reactivate --ticker 005930 --region KR

    # List blacklisted tickers
    python3 scripts/manage_blacklist.py list --region KR

    # Show summary
    python3 scripts/manage_blacklist.py summary

    # Cleanup expired entries
    python3 scripts/manage_blacklist.py cleanup

Author: Spock Trading System
Created: 2025-10-17
"""

import argparse
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.stock_utils import setup_logger

logger = setup_logger()


def cmd_add(args, blacklist_manager: BlacklistManager):
    """Add ticker to file-based blacklist"""
    success = blacklist_manager.add_to_file_blacklist(
        ticker=args.ticker,
        region=args.region,
        reason=args.reason,
        added_by=args.added_by or "user",
        expire_date=args.expire,
        notes=args.notes
    )

    if success:
        print(f"✅ Added to file blacklist: {args.region}:{args.ticker}")
        if args.expire:
            print(f"   Expires: {args.expire}")
    else:
        print(f"❌ Failed to add {args.region}:{args.ticker}")
        sys.exit(1)


def cmd_remove(args, blacklist_manager: BlacklistManager):
    """Remove ticker from file-based blacklist"""
    success = blacklist_manager.remove_from_file_blacklist(
        ticker=args.ticker,
        region=args.region
    )

    if success:
        print(f"✅ Removed from file blacklist: {args.region}:{args.ticker}")
    else:
        print(f"❌ Failed to remove {args.region}:{args.ticker}")
        sys.exit(1)


def cmd_deactivate(args, blacklist_manager: BlacklistManager):
    """Deactivate ticker in DB (permanent)"""
    success = blacklist_manager.deactivate_ticker_db(
        ticker=args.ticker,
        region=args.region,
        reason=args.reason
    )

    if success:
        print(f"✅ Deactivated in DB: {args.region}:{args.ticker}")
        if args.reason:
            print(f"   Reason: {args.reason}")
    else:
        print(f"❌ Failed to deactivate {args.region}:{args.ticker}")
        sys.exit(1)


def cmd_reactivate(args, blacklist_manager: BlacklistManager):
    """Reactivate ticker in DB"""
    success = blacklist_manager.reactivate_ticker_db(
        ticker=args.ticker,
        region=args.region
    )

    if success:
        print(f"✅ Reactivated in DB: {args.region}:{args.ticker}")
    else:
        print(f"❌ Failed to reactivate {args.region}:{args.ticker}")
        sys.exit(1)


def cmd_list(args, blacklist_manager: BlacklistManager):
    """List blacklisted tickers"""
    print(f"\n{'='*60}")
    print(f"  BLACKLIST REPORT - {args.region or 'ALL REGIONS'}")
    print(f"{'='*60}\n")

    # Get DB blacklist
    db_blacklist = blacklist_manager.get_db_blacklist(region=args.region)

    # Get file blacklist
    file_blacklist_all = blacklist_manager._file_blacklist

    regions_to_show = [args.region] if args.region else blacklist_manager.VALID_REGIONS

    for region in regions_to_show:
        print(f"📍 {region} Market")
        print(f"{'-'*60}")

        # DB blacklist (permanent)
        db_tickers = db_blacklist.get(region, [])
        if db_tickers:
            print(f"\n  🔒 DB Blacklist (Permanent - is_active=False): {len(db_tickers)}")
            for ticker in db_tickers:
                print(f"     - {ticker}")
        else:
            print(f"\n  🔒 DB Blacklist: None")

        # File blacklist (temporary)
        file_tickers = file_blacklist_all.get(region, {})
        if file_tickers:
            print(f"\n  📄 File Blacklist (Temporary): {len(file_tickers)}")
            for ticker, info in file_tickers.items():
                expire_info = f" (expires: {info.get('expire_date')})" if info.get('expire_date') else ""
                print(f"     - {ticker}: {info.get('reason')}{expire_info}")
                if info.get('notes'):
                    print(f"       Notes: {info.get('notes')}")
        else:
            print(f"\n  📄 File Blacklist: None")

        print()


def cmd_summary(args, blacklist_manager: BlacklistManager):
    """Show blacklist summary"""
    summary = blacklist_manager.get_blacklist_summary()

    print(f"\n{'='*60}")
    print(f"  BLACKLIST SUMMARY")
    print(f"{'='*60}\n")

    print(f"Total DB Blacklist (Permanent): {summary['total_db_blacklist']}")
    print(f"Total File Blacklist (Temporary): {summary['total_file_blacklist']}")
    print(f"Total Blacklisted: {summary['total_db_blacklist'] + summary['total_file_blacklist']}")
    print()

    print(f"{'Region':<10} {'DB':<10} {'File':<10} {'Total':<10}")
    print(f"{'-'*40}")

    for region, counts in summary['by_region'].items():
        print(f"{region:<10} {counts['db_blacklist']:<10} {counts['file_blacklist']:<10} {counts['total']:<10}")

    print()


def cmd_cleanup(args, blacklist_manager: BlacklistManager):
    """Cleanup expired entries"""
    removed_count = blacklist_manager.cleanup_expired_entries()

    if removed_count > 0:
        print(f"✅ Removed {removed_count} expired entries")
    else:
        print(f"ℹ️ No expired entries found")


def cmd_check(args, blacklist_manager: BlacklistManager):
    """Check if ticker is blacklisted"""
    is_blacklisted = blacklist_manager.is_blacklisted(
        ticker=args.ticker,
        region=args.region
    )

    if is_blacklisted:
        print(f"🚫 {args.region}:{args.ticker} is BLACKLISTED")

        # Check where it's blacklisted
        db_blacklist = blacklist_manager.get_db_blacklist(region=args.region)
        file_blacklist_all = blacklist_manager._file_blacklist

        if args.ticker in db_blacklist.get(args.region, []):
            print(f"   - DB Blacklist: YES (is_active=False)")

        if args.ticker in file_blacklist_all.get(args.region, {}):
            info = file_blacklist_all[args.region][args.ticker]
            print(f"   - File Blacklist: YES")
            print(f"     Reason: {info.get('reason')}")
            if info.get('expire_date'):
                print(f"     Expires: {info.get('expire_date')}")

        sys.exit(1)  # Exit with error code
    else:
        print(f"✅ {args.region}:{args.ticker} is NOT blacklisted")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description='Blacklist Management CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add to file blacklist
  %(prog)s add --ticker 005930 --region KR --reason "임시 제외"

  # Add with expiry
  %(prog)s add --ticker TSLA --region US --reason "변동성 과다" --expire 2025-12-31

  # Remove from file blacklist
  %(prog)s remove --ticker 005930 --region KR

  # Deactivate in DB (permanent)
  %(prog)s deactivate --ticker 005930 --region KR --reason "상장폐지"

  # Reactivate in DB
  %(prog)s reactivate --ticker 005930 --region KR

  # List blacklisted tickers
  %(prog)s list --region KR

  # Show summary
  %(prog)s summary

  # Cleanup expired
  %(prog)s cleanup

  # Check ticker status
  %(prog)s check --ticker 005930 --region KR
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Add command
    parser_add = subparsers.add_parser('add', help='Add ticker to file blacklist')
    parser_add.add_argument('--ticker', required=True, help='Ticker code')
    parser_add.add_argument('--region', required=True, choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                           help='Region code')
    parser_add.add_argument('--reason', required=True, help='Exclusion reason')
    parser_add.add_argument('--added-by', default='user', help='Who added it (default: user)')
    parser_add.add_argument('--expire', help='Expiry date (YYYY-MM-DD)')
    parser_add.add_argument('--notes', help='Additional notes')

    # Remove command
    parser_remove = subparsers.add_parser('remove', help='Remove ticker from file blacklist')
    parser_remove.add_argument('--ticker', required=True, help='Ticker code')
    parser_remove.add_argument('--region', required=True, choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                              help='Region code')

    # Deactivate command
    parser_deactivate = subparsers.add_parser('deactivate', help='Deactivate ticker in DB (permanent)')
    parser_deactivate.add_argument('--ticker', required=True, help='Ticker code')
    parser_deactivate.add_argument('--region', required=True, choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                                  help='Region code')
    parser_deactivate.add_argument('--reason', help='Deactivation reason')

    # Reactivate command
    parser_reactivate = subparsers.add_parser('reactivate', help='Reactivate ticker in DB')
    parser_reactivate.add_argument('--ticker', required=True, help='Ticker code')
    parser_reactivate.add_argument('--region', required=True, choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                                  help='Region code')

    # List command
    parser_list = subparsers.add_parser('list', help='List blacklisted tickers')
    parser_list.add_argument('--region', choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                            help='Filter by region (default: all)')

    # Summary command
    parser_summary = subparsers.add_parser('summary', help='Show blacklist summary')

    # Cleanup command
    parser_cleanup = subparsers.add_parser('cleanup', help='Remove expired entries')

    # Check command
    parser_check = subparsers.add_parser('check', help='Check if ticker is blacklisted')
    parser_check.add_argument('--ticker', required=True, help='Ticker code')
    parser_check.add_argument('--region', required=True, choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                             help='Region code')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize database and blacklist manager
    db = SQLiteDatabaseManager()
    blacklist_manager = BlacklistManager(db)

    # Execute command
    commands = {
        'add': cmd_add,
        'remove': cmd_remove,
        'deactivate': cmd_deactivate,
        'reactivate': cmd_reactivate,
        'list': cmd_list,
        'summary': cmd_summary,
        'cleanup': cmd_cleanup,
        'check': cmd_check
    }

    if args.command in commands:
        commands[args.command](args, blacklist_manager)
    else:
        print(f"❌ Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
