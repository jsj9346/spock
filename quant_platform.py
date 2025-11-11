#!/usr/bin/env python3
"""
Quant Platform CLI - Main Entry Point

Multi-mode quantitative investment platform with:
- Research-driven strategy development
- Evidence-based backtesting
- Portfolio optimization
- Risk management

Supports both local and cloud deployment modes with flexible authentication.

Usage:
    python3 quant_platform.py setup                    # First-time setup
    python3 quant_platform.py auth login               # Login
    python3 quant_platform.py auth logout              # Logout
    python3 quant_platform.py auth status              # Check auth status
    python3 quant_platform.py query --top 20           # Query stocks (Sprint 1)
    python3 quant_platform.py backtest run             # Run backtest (Sprint 3)

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.utils.config_loader import get_config
from cli.utils.output_formatter import print_error, print_info
from cli.commands import setup, auth
from cli.commands.query import add_query_arguments, run_query_sync
from cli.commands.backtest import add_backtest_arguments, run_backtest_sync


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser with all subcommands

    Returns:
        ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Quant Platform CLI - Quantitative Investment Research Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First-time setup (create admin account)
  python3 quant_platform.py setup

  # Authentication
  python3 quant_platform.py auth login
  python3 quant_platform.py auth logout
  python3 quant_platform.py auth status

  # Stock Queries (Sprint 1 - Available Now!)
  python3 quant_platform.py query --top 20
  python3 quant_platform.py query --with-fundamentals --filter "f.per < 15" --top 20
  python3 quant_platform.py query --with-fundamentals --filter "f.pbr < 1" --csv value_stocks.csv

  # Backtesting (Sprint 3 - Available Now!)
  python3 quant_platform.py backtest --tickers 005930 --start 2020-01-01 --end 2023-12-31 --strategy buy-hold
  python3 quant_platform.py backtest --tickers 005930 000660 --start 2022-01-01 --end 2024-12-31 --strategy ma-crossover

  # Interactive Shell (Sprint 5 - Available Now!)
  python3 quant_platform.py shell

For more information, visit: https://github.com/quant-platform
        """
    )

    # Global options
    parser.add_argument(
        '--mode',
        choices=['local', 'cloud'],
        help='Deployment mode (overrides config)'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Custom configuration file path'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Setup command
    setup_parser = subparsers.add_parser(
        'setup',
        help='First-time setup wizard (create admin account)'
    )

    # Auth command
    auth_parser = subparsers.add_parser(
        'auth',
        help='Authentication commands'
    )

    auth_subparsers = auth_parser.add_subparsers(dest='auth_command', help='Auth subcommands')

    auth_subparsers.add_parser('login', help='Login with username/password')
    auth_subparsers.add_parser('logout', help='Logout and clear session')
    auth_subparsers.add_parser('status', help='Show authentication status')

    # Query command (Sprint 1)
    query_parser = subparsers.add_parser(
        'query',
        help='Query and screen stocks with filters'
    )
    add_query_arguments(query_parser)

    # Backtest command (Sprint 3)
    backtest_parser = subparsers.add_parser(
        'backtest',
        help='Run backtests on trading strategies'
    )
    add_backtest_arguments(backtest_parser)

    # Shell command (Sprint 5)
    shell_parser = subparsers.add_parser(
        'shell',
        help='Start interactive shell mode'
    )

    return parser


def main():
    """Main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load configuration
    try:
        config = get_config()

        # Override mode if specified
        if args.mode:
            config.config['mode'] = args.mode

    except Exception as e:
        print_error("Failed to load configuration", str(e))
        sys.exit(1)

    # Route to appropriate command handler
    try:
        if args.command == 'setup':
            setup.run_setup()

        elif args.command == 'auth':
            if not args.auth_command:
                parser.parse_args(['auth', '--help'])
                sys.exit(0)

            if args.auth_command == 'login':
                auth.login()
            elif args.auth_command == 'logout':
                auth.logout()
            elif args.auth_command == 'status':
                auth.status()

        elif args.command == 'query':
            exit_code = run_query_sync(args)
            sys.exit(exit_code)

        elif args.command == 'backtest':
            exit_code = run_backtest_sync(args)
            sys.exit(exit_code)

        elif args.command == 'shell':
            from cli.shell import run_shell
            run_shell()

        else:
            print_error(f"Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print_error("Command failed", str(e))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
