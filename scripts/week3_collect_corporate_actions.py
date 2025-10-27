#!/usr/bin/env python3
"""
Week 3 Phase 3: Corporate Actions Collection Script

Collects corporate actions data for Korean stocks:
- Stock Splits: Automatic price/volume adjustments
- Dividends: Cash and stock dividends
- Rights Issues: New share offerings

Data Sources:
- pykrx: Dividend data from fundamentals (DIV, DPS)
- KRX announcements: Stock splits and rights issues (if available)
- Manual collection: Critical events for backtesting accuracy

Target: 350 tickers (KOSPI 200 + KOSDAQ 150)
Date Range: 2019-01-01 to 2024-12-31

Usage:
    # Full collection
    python3 scripts/week3_collect_corporate_actions.py --start 2019-01-01 --end 2024-12-31

    # Dry run
    python3 scripts/week3_collect_corporate_actions.py --dry-run --start 2019-01-01 --end 2024-12-31

    # Specific action types
    python3 scripts/week3_collect_corporate_actions.py --types dividends,splits --start 2019-01-01 --end 2024-12-31

Author: Spock Quant Platform - Week 3 Phase 3
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# pykrx library
try:
    from pykrx import stock
except ImportError:
    print("❌ pykrx library not installed")
    print("Install with: pip3 install pykrx")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_corporate_actions_week3.log"
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


class CorporateActionsCollector:
    """Corporate actions data collector for Korean stocks"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize collector

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'dividends_found': 0,
            'splits_found': 0,
            'rights_found': 0,
            'records_inserted': 0,
            'records_failed': 0
        }

        # Create corporate_actions table if not exists
        self._create_table()

    def _create_table(self):
        """Create corporate_actions table if not exists"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS corporate_actions (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL DEFAULT 'KR',
            action_date DATE NOT NULL,
            action_type VARCHAR(20) NOT NULL,  -- 'dividend', 'split', 'rights'

            -- Dividend fields
            dividend_type VARCHAR(10),  -- 'cash', 'stock'
            dividend_per_share DECIMAL(15, 4),
            dividend_yield DECIMAL(8, 4),

            -- Split fields
            split_ratio VARCHAR(20),  -- e.g., '1:2', '2:1'
            split_from INTEGER,
            split_to INTEGER,

            -- Rights issue fields
            rights_ratio VARCHAR(20),
            rights_price DECIMAL(15, 4),

            -- Metadata
            data_source VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(ticker, region, action_date, action_type)
        );

        CREATE INDEX IF NOT EXISTS idx_corporate_actions_ticker_date
        ON corporate_actions(ticker, action_date);

        CREATE INDEX IF NOT EXISTS idx_corporate_actions_type
        ON corporate_actions(action_type);
        """

        if not self.dry_run:
            try:
                self.db.execute_update(create_table_query)
                logger.info("✅ Corporate actions table created/verified")
            except Exception as e:
                logger.error(f"❌ Failed to create table: {e}")
                raise

    def collect_dividends(self, tickers: List[str], start_date: date, end_date: date):
        """
        Collect dividend data from pykrx fundamentals

        Args:
            tickers: List of ticker symbols
            start_date: Start date for collection
            end_date: End date for collection
        """
        logger.info(f"📊 Collecting dividends for {len(tickers)} tickers ({start_date} to {end_date})")

        for i, ticker in enumerate(tickers, 1):
            try:
                # Get fundamental data (includes DIV and DPS)
                logger.info(f"[{i}/{len(tickers)}] Processing {ticker}")

                # pykrx fundamentals include dividend yield (DIV) and dividend per share (DPS)
                # We'll collect annually to detect dividend events
                current_date = start_date
                dividends = []

                while current_date <= end_date:
                    try:
                        # Get fundamental data for this date
                        fundamental_df = stock.get_market_fundamental_by_ticker(
                            current_date.strftime('%Y%m%d'),
                            market='ALL'
                        )

                        if ticker in fundamental_df.index:
                            div_yield = fundamental_df.loc[ticker, 'DIV']
                            # Note: DPS (dividend per share) column may not be available in all pykrx versions

                            if pd.notna(div_yield) and div_yield > 0:
                                dividend_record = {
                                    'ticker': ticker,
                                    'action_date': current_date,
                                    'action_type': 'dividend',
                                    'dividend_type': 'cash',
                                    'dividend_yield': float(div_yield),
                                    'data_source': 'pykrx'
                                }
                                dividends.append(dividend_record)

                    except Exception as e:
                        # Skip dates with no data (weekends, holidays)
                        pass

                    # Move to next year
                    current_date = date(current_date.year + 1, current_date.month, current_date.day)

                # Insert collected dividends
                if dividends:
                    self._insert_corporate_actions(dividends)
                    self.stats['dividends_found'] += len(dividends)
                    logger.info(f"  ✅ Found {len(dividends)} dividend events for {ticker}")

                self.stats['tickers_processed'] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to process {ticker}: {e}")
                self.stats['records_failed'] += 1

    def collect_splits(self, tickers: List[str], start_date: date, end_date: date):
        """
        Collect stock split data

        Note: pykrx does not provide direct split data. This requires manual collection
        from KRX announcements or alternative data sources.

        Args:
            tickers: List of ticker symbols
            start_date: Start date for collection
            end_date: End date for collection
        """
        logger.info(f"📊 Stock split collection: Manual data source required")
        logger.info(f"   pykrx does not provide split data directly")
        logger.info(f"   Options: KRX announcements, financial news APIs, manual entry")
        logger.info(f"   For now, skipping split collection (Phase 3 enhancement)")

        # TODO: Implement split detection via:
        # 1. KRX market disclosure API (if available)
        # 2. Naver Finance API
        # 3. Manual CSV import of known splits

        self.stats['splits_found'] = 0

    def collect_rights_issues(self, tickers: List[str], start_date: date, end_date: date):
        """
        Collect rights issue data

        Note: Requires KRX disclosure or alternative sources

        Args:
            tickers: List of ticker symbols
            start_date: Start date for collection
            end_date: End date for collection
        """
        logger.info(f"📊 Rights issue collection: Manual data source required")
        logger.info(f"   Requires KRX disclosure or financial news sources")
        logger.info(f"   For now, skipping rights issue collection (Phase 3 enhancement)")

        # TODO: Implement rights issue detection

        self.stats['rights_found'] = 0

    def _insert_corporate_actions(self, actions: List[Dict]):
        """
        Insert corporate actions into database

        Args:
            actions: List of corporate action records
        """
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would insert {len(actions)} corporate actions")
            return

        insert_query = """
        INSERT INTO corporate_actions (
            ticker, region, action_date, action_type,
            dividend_type, dividend_per_share, dividend_yield,
            split_ratio, split_from, split_to,
            rights_ratio, rights_price,
            data_source
        ) VALUES (
            %(ticker)s, 'KR', %(action_date)s, %(action_type)s,
            %(dividend_type)s, %(dividend_per_share)s, %(dividend_yield)s,
            %(split_ratio)s, %(split_from)s, %(split_to)s,
            %(rights_ratio)s, %(rights_price)s,
            %(data_source)s
        )
        ON CONFLICT (ticker, region, action_date, action_type)
        DO UPDATE SET
            dividend_type = EXCLUDED.dividend_type,
            dividend_per_share = EXCLUDED.dividend_per_share,
            dividend_yield = EXCLUDED.dividend_yield,
            split_ratio = EXCLUDED.split_ratio,
            split_from = EXCLUDED.split_from,
            split_to = EXCLUDED.split_to,
            rights_ratio = EXCLUDED.rights_ratio,
            rights_price = EXCLUDED.rights_price,
            data_source = EXCLUDED.data_source,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            for action in actions:
                # Fill missing fields with None
                params = {
                    'ticker': action.get('ticker'),
                    'action_date': action.get('action_date'),
                    'action_type': action.get('action_type'),
                    'dividend_type': action.get('dividend_type'),
                    'dividend_per_share': action.get('dividend_per_share'),
                    'dividend_yield': action.get('dividend_yield'),
                    'split_ratio': action.get('split_ratio'),
                    'split_from': action.get('split_from'),
                    'split_to': action.get('split_to'),
                    'rights_ratio': action.get('rights_ratio'),
                    'rights_price': action.get('rights_price'),
                    'data_source': action.get('data_source', 'unknown')
                }

                self.db.execute_update(insert_query, params)
                self.stats['records_inserted'] += 1

        except Exception as e:
            logger.error(f"  ❌ Failed to insert corporate actions: {e}")
            self.stats['records_failed'] += len(actions)

    def run_collection(self, start_date: date, end_date: date, action_types: List[str] = None):
        """
        Run corporate actions collection

        Args:
            start_date: Start date for collection
            end_date: End date for collection
            action_types: List of action types to collect (dividends, splits, rights)
        """
        if action_types is None:
            action_types = ['dividends', 'splits', 'rights']

        logger.info("=" * 80)
        logger.info("CORPORATE ACTIONS COLLECTION - Week 3 Phase 3")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"Action Types: {', '.join(action_types)}")
        logger.info(f"Dry Run: {self.dry_run}")

        # Load ticker universe from Week 3
        universe_file = 'data/kr_universe_week3.csv'
        if not os.path.exists(universe_file):
            logger.error(f"❌ Universe file not found: {universe_file}")
            logger.error("Run scripts/week3_define_universe.py first")
            return

        universe_df = pd.read_csv(universe_file)
        tickers = universe_df['ticker'].tolist()
        logger.info(f"Loaded {len(tickers)} tickers from universe")

        # Collect each action type
        if 'dividends' in action_types:
            self.collect_dividends(tickers, start_date, end_date)

        if 'splits' in action_types:
            self.collect_splits(tickers, start_date, end_date)

        if 'rights' in action_types:
            self.collect_rights_issues(tickers, start_date, end_date)

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print collection summary"""
        logger.info("=" * 80)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Tickers Processed:    {self.stats['tickers_processed']:>6,}")
        logger.info(f"Dividends Found:      {self.stats['dividends_found']:>6,}")
        logger.info(f"Splits Found:         {self.stats['splits_found']:>6,}")
        logger.info(f"Rights Issues Found:  {self.stats['rights_found']:>6,}")
        logger.info(f"Records Inserted:     {self.stats['records_inserted']:>6,}")
        logger.info(f"Records Failed:       {self.stats['records_failed']:>6,}")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Collect corporate actions for KR stocks')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--types', default='dividends,splits,rights',
                       help='Action types to collect (comma-separated: dividends,splits,rights)')

    args = parser.parse_args()

    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        logger.error(f"❌ Invalid date format: {e}")
        logger.error("Use YYYY-MM-DD format")
        return 1

    # Parse action types
    action_types = [t.strip().lower() for t in args.types.split(',')]

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize and run collector
    try:
        collector = CorporateActionsCollector(db=db, dry_run=args.dry_run)
        collector.run_collection(start_date=start_date, end_date=end_date, action_types=action_types)
        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Collection interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
