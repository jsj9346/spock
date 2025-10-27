#!/usr/bin/env python3
"""
Week 3 Phase 3: Price Adjustment Application Script

Applies corporate actions adjustments to historical OHLCV data:
- Stock Splits: Adjust prices and volumes
- Dividends: Adjust prices for dividend payments
- Rights Issues: Adjust for new share offerings

Adjustment Method: Backward adjustment (adjust historical prices, keep current prices)

Usage:
    # Apply all adjustments
    python3 scripts/week3_adjust_prices.py

    # Dry run
    python3 scripts/week3_adjust_prices.py --dry-run

    # Specific action types
    python3 scripts/week3_adjust_prices.py --types splits,dividends

    # Specific tickers
    python3 scripts/week3_adjust_prices.py --tickers 005930,000660

Author: Spock Quant Platform - Week 3 Phase 3
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_price_adjustment_week3.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PriceAdjuster:
    """Apply corporate actions adjustments to OHLCV data"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize adjuster

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'splits_applied': 0,
            'dividends_applied': 0,
            'records_adjusted': 0,
            'records_failed': 0
        }

    def apply_split_adjustment(self, ticker: str, split_date: date, split_from: int, split_to: int):
        """
        Apply stock split adjustment to historical prices

        Backward adjustment: Adjust all prices BEFORE split date

        Args:
            ticker: Stock ticker
            split_date: Date of split
            split_from: Split ratio from (e.g., 1 in 1:2 split)
            split_to: Split ratio to (e.g., 2 in 1:2 split)
        """
        adjustment_factor = split_to / split_from

        logger.info(f"  Applying {split_from}:{split_to} split for {ticker} on {split_date}")
        logger.info(f"    Adjustment factor: {adjustment_factor:.4f}")

        if self.dry_run:
            logger.info(f"    [DRY RUN] Would adjust historical prices before {split_date}")
            return

        # Update prices before split date
        update_query = """
        UPDATE ohlcv_data
        SET
            open = open / %s,
            high = high / %s,
            low = low / %s,
            close = close / %s,
            volume = volume * %s
        WHERE ticker = %s
          AND region = 'KR'
          AND date < %s
        """

        try:
            affected_rows = self.db.execute_update(
                update_query,
                (adjustment_factor, adjustment_factor, adjustment_factor, adjustment_factor,
                 adjustment_factor, ticker, split_date)
            )
            self.stats['records_adjusted'] += affected_rows
            self.stats['splits_applied'] += 1
            logger.info(f"    ✅ Adjusted {affected_rows} records")

        except Exception as e:
            logger.error(f"    ❌ Failed to apply split adjustment: {e}")
            self.stats['records_failed'] += 1

    def apply_dividend_adjustment(self, ticker: str, dividend_date: date, dividend_amount: Decimal):
        """
        Apply dividend adjustment to historical prices

        Backward adjustment: Subtract dividend from prices BEFORE ex-dividend date

        Args:
            ticker: Stock ticker
            dividend_date: Ex-dividend date
            dividend_amount: Dividend per share amount
        """
        logger.info(f"  Applying dividend ₩{dividend_amount} for {ticker} on {dividend_date}")

        if self.dry_run:
            logger.info(f"    [DRY RUN] Would subtract dividend from historical prices before {dividend_date}")
            return

        # Get current price to calculate adjustment factor
        price_query = """
        SELECT close FROM ohlcv_data
        WHERE ticker = %s AND region = 'KR' AND date = %s
        LIMIT 1
        """

        try:
            result = self.db.execute_query(price_query, (ticker, dividend_date))
            if not result:
                logger.warning(f"    ⚠️  No price data found for {ticker} on {dividend_date}")
                return

            current_price = result[0]['close']
            adjustment_factor = (current_price - dividend_amount) / current_price

            # Update prices before dividend date
            update_query = """
            UPDATE ohlcv_data
            SET
                open = open * %s,
                high = high * %s,
                low = low * %s,
                close = close * %s
            WHERE ticker = %s
              AND region = 'KR'
              AND date < %s
            """

            affected_rows = self.db.execute_update(
                update_query,
                (adjustment_factor, adjustment_factor, adjustment_factor, adjustment_factor,
                 ticker, dividend_date)
            )
            self.stats['records_adjusted'] += affected_rows
            self.stats['dividends_applied'] += 1
            logger.info(f"    ✅ Adjusted {affected_rows} records (factor: {adjustment_factor:.6f})")

        except Exception as e:
            logger.error(f"    ❌ Failed to apply dividend adjustment: {e}")
            self.stats['records_failed'] += 1

    def run_adjustments(self, action_types: List[str] = None, tickers: List[str] = None):
        """
        Run price adjustments based on corporate actions

        Args:
            action_types: List of action types to process (splits, dividends)
            tickers: List of specific tickers to process (None = all)
        """
        if action_types is None:
            action_types = ['splits', 'dividends']

        logger.info("=" * 80)
        logger.info("PRICE ADJUSTMENT APPLICATION - Week 3 Phase 3")
        logger.info("=" * 80)
        logger.info(f"Action Types: {', '.join(action_types)}")
        logger.info(f"Dry Run: {self.dry_run}")

        # Load corporate actions from database
        where_clause = ""
        params = []

        if tickers:
            placeholders = ','.join(['%s'] * len(tickers))
            where_clause = f"WHERE ticker IN ({placeholders})"
            params = tickers

        query = f"""
        SELECT ticker, action_date, action_type,
               split_from, split_to,
               dividend_per_share
        FROM corporate_actions
        {where_clause}
        ORDER BY ticker, action_date
        """

        try:
            actions = self.db.execute_query(query, tuple(params) if params else None)
            logger.info(f"Loaded {len(actions)} corporate actions from database")

        except Exception as e:
            logger.error(f"❌ Failed to load corporate actions: {e}")
            return

        # Group by ticker
        actions_by_ticker = {}
        for action in actions:
            ticker = action['ticker']
            if ticker not in actions_by_ticker:
                actions_by_ticker[ticker] = []
            actions_by_ticker[ticker].append(action)

        # Process each ticker
        for ticker, ticker_actions in actions_by_ticker.items():
            logger.info(f"\n📊 Processing {ticker} ({len(ticker_actions)} actions)")

            for action in ticker_actions:
                action_type = action['action_type']

                if action_type == 'split' and 'splits' in action_types:
                    if action['split_from'] and action['split_to']:
                        self.apply_split_adjustment(
                            ticker,
                            action['action_date'],
                            action['split_from'],
                            action['split_to']
                        )

                elif action_type == 'dividend' and 'dividends' in action_types:
                    if action['dividend_per_share']:
                        self.apply_dividend_adjustment(
                            ticker,
                            action['action_date'],
                            Decimal(str(action['dividend_per_share']))
                        )

            self.stats['tickers_processed'] += 1

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print adjustment summary"""
        logger.info("\n" + "=" * 80)
        logger.info("ADJUSTMENT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Tickers Processed:    {self.stats['tickers_processed']:>6,}")
        logger.info(f"Splits Applied:       {self.stats['splits_applied']:>6,}")
        logger.info(f"Dividends Applied:    {self.stats['dividends_applied']:>6,}")
        logger.info(f"Records Adjusted:     {self.stats['records_adjusted']:>6,}")
        logger.info(f"Records Failed:       {self.stats['records_failed']:>6,}")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Apply corporate actions adjustments to OHLCV data')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--types', default='splits,dividends',
                       help='Action types to apply (comma-separated: splits,dividends)')
    parser.add_argument('--tickers', help='Specific tickers to process (comma-separated)')

    args = parser.parse_args()

    # Parse action types
    action_types = [t.strip().lower() for t in args.types.split(',')]

    # Parse tickers if specified
    tickers = None
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize and run adjuster
    try:
        adjuster = PriceAdjuster(db=db, dry_run=args.dry_run)
        adjuster.run_adjustments(action_types=action_types, tickers=tickers)
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Adjustment interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Adjustment failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
