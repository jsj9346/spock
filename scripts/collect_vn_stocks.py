#!/usr/bin/env python3
"""
collect_vn_stocks.py - Vietnam Market OHLCV Data Collection Script

Purpose:
- Collect Vietnam stock OHLCV data with Stage 0-1 filtering
- Support HOSE (Ho Chi Minh) and HNX (Hanoi) exchanges
- Integrate with KIS Overseas API (20x faster than yfinance)
- Apply market-specific error handling and rate limiting

Market Characteristics:
- Market Hours: 09:00-11:30, 13:00-15:00 ICT (11:00-13:30, 15:00-17:00 KST)
- Trading Days: Mon-Fri (excluding Vietnam holidays)
- Lunch Break: 11:30-13:00 ICT
- API Rate Limit: 20 req/sec (KIS Overseas API)
- Ticker Format: 3-letter uppercase (e.g., VCB, TCB, VHM)

Author: Spock Trading System
Created: 2025-10-16
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.kis_data_collector import KISDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function for Vietnam market data collection"""
    parser = argparse.ArgumentParser(
        description='Vietnam Market OHLCV Data Collection (HOSE, HNX)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all VN stocks with filtering (default: 250 days)
  python3 scripts/collect_vn_stocks.py

  # Collect specific tickers (Vietcombank, Vinhomes)
  python3 scripts/collect_vn_stocks.py --tickers VCB VHM TCB

  # Collect with Stage 1 filter (technical pre-screen)
  python3 scripts/collect_vn_stocks.py --apply-stage1

  # Collect 30-day data (quick update)
  python3 scripts/collect_vn_stocks.py --days 30

  # Dry run (mock mode, no API calls)
  python3 scripts/collect_vn_stocks.py --dry-run

Market Info:
  - Trading Hours: 09:00-11:30, 13:00-15:00 ICT (lunch break 11:30-13:00)
  - API Rate Limit: 20 req/sec (KIS Overseas API)
  - Expected Tickers: ~100-300 tradable stocks (VN30 index + major stocks)
  - Collection Time: ~10-20 seconds for 100 tickers (with filtering)
        """
    )

    # Data collection options
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path (default: data/spock_local.db)'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific tickers to collect (e.g., VCB VHM TCB MBB FPT)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=250,
        help='Number of days to collect (default: 250 for MA200)'
    )

    # Filtering options
    parser.add_argument(
        '--no-stage0',
        action='store_true',
        help='Disable Stage 0 filter (collect all tickers)'
    )
    parser.add_argument(
        '--apply-stage1',
        action='store_true',
        help='Apply Stage 1 filter (technical pre-screen)'
    )

    # Execution options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (mock data, no API calls)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        logger.info("=" * 60)
        logger.info("Vietnam Market OHLCV Data Collection")
        logger.info("=" * 60)
        logger.info(f"Database: {args.db_path}")
        logger.info(f"Region: VN (HOSE, HNX)")
        logger.info(f"Days to collect: {args.days}")
        logger.info(f"Stage 0 filter: {'Disabled' if args.no_stage0 else 'Enabled'}")
        logger.info(f"Stage 1 filter: {'Enabled' if args.apply_stage1 else 'Disabled'}")
        logger.info(f"Mode: {'DRY RUN (Mock)' if args.dry_run else 'LIVE (KIS API)'}")
        logger.info("=" * 60)

        # Initialize database manager
        db_manager = SQLiteDatabaseManager(db_path=args.db_path)
        logger.info("✅ Database manager initialized")

        # Initialize KIS data collector for VN market
        collector = KISDataCollector(db_path=args.db_path, region='VN')

        # Override to dry-run mode if requested
        if args.dry_run:
            logger.info("⚠️ DRY RUN MODE: Using mock data (no API calls)")
            collector.mock_mode = True

        # Execute data collection with filtering
        logger.info("")
        logger.info("🚀 Starting OHLCV collection with filtering...")
        logger.info("")

        stats = collector.collect_with_filtering(
            tickers=args.tickers,
            days=args.days,
            apply_stage0=not args.no_stage0,
            apply_stage1=args.apply_stage1
        )

        # Print final summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 Vietnam Market Collection Summary")
        logger.info("=" * 60)
        logger.info(f"Input tickers:     {stats.get('input_count', 0):,}")
        logger.info(f"Stage 0 passed:    {stats.get('stage0_passed', 0):,} ({stats.get('stage0_passed', 0) / max(stats.get('input_count', 1), 1) * 100:.1f}%)")
        logger.info(f"OHLCV collected:   {stats.get('ohlcv_collected', 0):,} ({stats.get('ohlcv_collected', 0) / max(stats.get('stage0_passed', 1), 1) * 100:.1f}% of Stage 0)")

        if args.apply_stage1 and stats.get('stage1_passed', 0) > 0:
            logger.info(f"Stage 1 passed:    {stats.get('stage1_passed', 0):,} ({stats.get('stage1_passed', 0) / max(stats.get('ohlcv_collected', 1), 1) * 100:.1f}% of OHLCV)")

        logger.info(f"Failed:            {stats.get('ohlcv_failed', 0):,}")
        logger.info(f"Filtering enabled: {'Yes' if stats.get('filtering_enabled', False) else 'No'}")
        logger.info("=" * 60)

        # Success/failure summary
        total_success = stats.get('ohlcv_collected', 0)
        total_input = stats.get('input_count', 0)

        if total_success > 0:
            logger.info("")
            logger.info(f"✅ VN market data collection completed successfully!")
            logger.info(f"   Collected {total_success:,} tickers out of {total_input:,} input ({total_success/max(total_input, 1)*100:.1f}%)")
            return 0
        else:
            logger.warning("")
            logger.warning("⚠️ No data collected. Please check:")
            logger.warning("   1. KIS API credentials (.env file)")
            logger.warning("   2. Stage 0 cache data (run stock_scanner.py first)")
            logger.warning("   3. Market hours (VN: 09:00-11:30, 13:00-15:00 ICT)")
            return 1

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("⚠️ Collection interrupted by user (Ctrl+C)")
        return 130
    except Exception as e:
        logger.error("")
        logger.error(f"❌ VN market data collection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
