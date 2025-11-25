#!/usr/bin/env python3
"""
Week 3 Phase 3: Corporate Actions Collection from DART API

Uses OpenDartReader to collect comprehensive corporate actions data:
- Dividends (cash and stock)
- Stock splits
- Rights issues
- Bonus shares
- Capital reductions

Data Source: DART (전자공시시스템) OpenAPI
Library: OpenDartReader

Usage:
    # Collect all corporate actions
    python3 scripts/week3_collect_corporate_actions_dart.py

    # Dry run
    python3 scripts/week3_collect_corporate_actions_dart.py --dry-run

    # Specific date range
    python3 scripts/week3_collect_corporate_actions_dart.py --start 2020-01-01 --end 2023-12-31

    # Specific tickers
    python3 scripts/week3_collect_corporate_actions_dart.py --tickers 005930,000660

Author: Spock Quant Platform - Week 3 Phase 3 (DART Enhanced)
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
import pandas as pd
import time
from typing import Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Import OpenDartReader (module itself is the class via __init__.py magic)
try:
    import OpenDartReader
except ImportError:
    print("❌ OpenDartReader not installed. Run: pip install OpenDartReader")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_corporate_actions_dart.log"
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


class DARTCorporateActionsCollector:
    """Corporate actions collector using DART API"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize collector

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Initialize DART API
        dart_api_key = os.getenv('DART_API_KEY')
        if not dart_api_key:
            raise ValueError("DART_API_KEY not found in .env file")

        self.dart = OpenDartReader(dart_api_key)
        logger.info(f"✅ DART API initialized with API key")

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'dividends_found': 0,
            'splits_found': 0,
            'rights_found': 0,
            'bonus_shares_found': 0,
            'records_inserted': 0,
            'records_failed': 0
        }

        # Create table
        self._create_table()

    def _create_table(self):
        """Create corporate_actions table if not exists"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS corporate_actions (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL DEFAULT 'KR',
            action_date DATE NOT NULL,
            action_type VARCHAR(20) NOT NULL,  -- 'dividend', 'split', 'rights', 'bonus'

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

            -- DART specific fields
            dart_receipt_no VARCHAR(20),  -- 공시접수번호
            dart_report_name TEXT,        -- 보고서명

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

        CREATE INDEX IF NOT EXISTS idx_corporate_actions_dart
        ON corporate_actions(dart_receipt_no);
        """

        if not self.dry_run:
            try:
                self.db.execute_update(create_table_query)
                logger.info("✅ Corporate actions table created/verified")
            except Exception as e:
                logger.error(f"❌ Failed to create table: {e}")
                raise

    def collect_dividends(self, ticker: str, start_date: date, end_date: date):
        """
        Collect dividend data from DART

        Args:
            ticker: Stock ticker (6-digit code)
            start_date: Start date for collection
            end_date: End date for collection
        """
        try:
            # Get dividend reports from DART
            # Note: DART uses fiscal year-based reporting
            years = range(start_date.year, end_date.year + 1)

            dividends = []
            for year in years:
                try:
                    # Get dividend report for this year
                    div_data = self.dart.report(ticker, '배당', year)

                    if div_data is not None and len(div_data) > 0:
                        # Extract cash dividend rows
                        cash_div_rows = div_data[div_data['se'] == '주당 현금배당금(원)']

                        for _, row in cash_div_rows.iterrows():
                            cash_div_str = str(row.get('thstrm', '0')).strip()

                            # Skip if no dividend or '-'
                            if cash_div_str == '-' or cash_div_str == '' or cash_div_str == '0':
                                continue

                            try:
                                # Remove commas and convert to float
                                cash_div = float(cash_div_str.replace(',', ''))

                                if cash_div > 0:
                                    dividend_record = {
                                        'ticker': ticker,
                                        'action_date': date(year, 12, 31),  # Use year-end as placeholder
                                        'action_type': 'dividend',
                                        'dividend_type': 'cash',
                                        'dividend_per_share': cash_div,
                                        'dart_receipt_no': row.get('rcept_no'),
                                        'data_source': 'DART'
                                    }
                                    dividends.append(dividend_record)
                            except (ValueError, AttributeError):
                                continue

                        # Extract stock dividend rows
                        stock_div_rows = div_data[div_data['se'] == '주당 주식배당(주)']

                        for _, row in stock_div_rows.iterrows():
                            stock_div_str = str(row.get('thstrm', '0')).strip()

                            # Skip if no dividend or '-'
                            if stock_div_str == '-' or stock_div_str == '' or stock_div_str == '0':
                                continue

                            try:
                                stock_div = float(stock_div_str.replace(',', ''))

                                if stock_div > 0:
                                    dividend_record = {
                                        'ticker': ticker,
                                        'action_date': date(year, 12, 31),
                                        'action_type': 'dividend',
                                        'dividend_type': 'stock',
                                        'dividend_per_share': stock_div,
                                        'dart_receipt_no': row.get('rcept_no'),
                                        'data_source': 'DART'
                                    }
                                    dividends.append(dividend_record)
                            except (ValueError, AttributeError):
                                continue

                    # Rate limiting
                    time.sleep(0.1)

                except Exception as e:
                    logger.debug(f"  No dividend data for {ticker} in {year}: {e}")
                    continue

            return dividends

        except Exception as e:
            logger.error(f"  ❌ Failed to collect dividends for {ticker}: {e}")
            return []

    def collect_capital_increases(self, ticker: str, start_date: date, end_date: date):
        """
        Collect capital increase events (paid-in, bonus shares) from DART

        Args:
            ticker: Stock ticker (6-digit code)
            start_date: Start date for collection
            end_date: End date for collection
        """
        try:
            records = []

            # Paid-in capital increases (유상증자)
            try:
                paid_in = self.dart.event(ticker, '유상증자', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))

                if paid_in is not None and len(paid_in) > 0:
                    for _, row in paid_in.iterrows():
                        record = {
                            'ticker': ticker,
                            'action_date': pd.to_datetime(row['rcept_dt']).date() if pd.notna(row.get('rcept_dt')) else start_date,
                            'action_type': 'rights',
                            'dart_receipt_no': row.get('rcept_no'),
                            'dart_report_name': row.get('report_nm'),
                            'data_source': 'DART'
                        }
                        records.append(record)

                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"  No paid-in capital increase for {ticker}: {e}")

            # Bonus shares (무상증자)
            try:
                bonus = self.dart.event(ticker, '무상증자', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))

                if bonus is not None and len(bonus) > 0:
                    for _, row in bonus.iterrows():
                        record = {
                            'ticker': ticker,
                            'action_date': pd.to_datetime(row['rcept_dt']).date() if pd.notna(row.get('rcept_dt')) else start_date,
                            'action_type': 'bonus',
                            'dart_receipt_no': row.get('rcept_no'),
                            'dart_report_name': row.get('report_nm'),
                            'data_source': 'DART'
                        }
                        records.append(record)

                time.sleep(0.1)
            except Exception as e:
                logger.debug(f"  No bonus shares for {ticker}: {e}")

            return records

        except Exception as e:
            logger.error(f"  ❌ Failed to collect capital increases for {ticker}: {e}")
            return []

    def collect_splits(self, ticker: str, start_date: date, end_date: date):
        """
        Collect stock split data from DART

        Note: DART may not have direct split data in all cases.
        This uses registration statements (정정신고서) to detect splits.

        Args:
            ticker: Stock ticker (6-digit code)
            start_date: Start date for collection
            end_date: End date for collection
        """
        try:
            # Search for split-related registration statements
            splits = self.dart.regstate(ticker, '분할', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))

            records = []
            if splits is not None and len(splits) > 0:
                for _, row in splits.iterrows():
                    record = {
                        'ticker': ticker,
                        'action_date': pd.to_datetime(row['rcept_dt']).date() if pd.notna(row.get('rcept_dt')) else start_date,
                        'action_type': 'split',
                        'dart_receipt_no': row.get('rcept_no'),
                        'dart_report_name': row.get('report_nm'),
                        'data_source': 'DART'
                    }
                    records.append(record)

            time.sleep(0.1)
            return records

        except Exception as e:
            logger.debug(f"  No split data for {ticker}: {e}")
            return []

    def _insert_corporate_actions(self, records: List[Dict]):
        """Insert corporate action records into database"""
        if not records or self.dry_run:
            return

        insert_query = """
        INSERT INTO corporate_actions
        (ticker, region, action_date, action_type,
         dividend_type, dividend_per_share, dividend_yield,
         split_ratio, split_from, split_to,
         rights_ratio, rights_price,
         dart_receipt_no, dart_report_name, data_source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, action_date, action_type) DO NOTHING
        """

        for record in records:
            try:
                params = (
                    record['ticker'],
                    record.get('region', 'KR'),
                    record['action_date'],
                    record['action_type'],
                    record.get('dividend_type'),
                    record.get('dividend_per_share'),
                    record.get('dividend_yield'),
                    record.get('split_ratio'),
                    record.get('split_from'),
                    record.get('split_to'),
                    record.get('rights_ratio'),
                    record.get('rights_price'),
                    record.get('dart_receipt_no'),
                    record.get('dart_report_name'),
                    record['data_source']
                )

                self.db.execute_update(insert_query, params)
                self.stats['records_inserted'] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to insert record: {e}")
                self.stats['records_failed'] += 1

    def run_collection(self, tickers: List[str], start_date: date, end_date: date):
        """
        Run full corporate actions collection

        Args:
            tickers: List of ticker codes
            start_date: Start date for collection
            end_date: End date for collection
        """
        logger.info("=" * 80)
        logger.info("DART CORPORATE ACTIONS COLLECTION - Week 3 Phase 3")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Tickers: {len(tickers)}")
        logger.info("")

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] Processing {ticker}")

            try:
                # Collect dividends
                dividends = self.collect_dividends(ticker, start_date, end_date)
                if dividends:
                    self._insert_corporate_actions(dividends)
                    self.stats['dividends_found'] += len(dividends)
                    logger.info(f"  ✅ Dividends: {len(dividends)}")

                # Collect capital increases
                capital_increases = self.collect_capital_increases(ticker, start_date, end_date)
                if capital_increases:
                    self._insert_corporate_actions(capital_increases)
                    rights_count = sum(1 for r in capital_increases if r['action_type'] == 'rights')
                    bonus_count = sum(1 for r in capital_increases if r['action_type'] == 'bonus')
                    self.stats['rights_found'] += rights_count
                    self.stats['bonus_shares_found'] += bonus_count
                    logger.info(f"  ✅ Rights: {rights_count}, Bonus: {bonus_count}")

                # Collect splits
                splits = self.collect_splits(ticker, start_date, end_date)
                if splits:
                    self._insert_corporate_actions(splits)
                    self.stats['splits_found'] += len(splits)
                    logger.info(f"  ✅ Splits: {len(splits)}")

                self.stats['tickers_processed'] += 1

            except Exception as e:
                logger.error(f"  ❌ Failed to process {ticker}: {e}")
                self.stats['records_failed'] += 1

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print collection summary"""
        logger.info("\n" + "=" * 80)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Tickers Processed:       {self.stats['tickers_processed']:>6,}")
        logger.info(f"Dividends Found:         {self.stats['dividends_found']:>6,}")
        logger.info(f"Splits Found:            {self.stats['splits_found']:>6,}")
        logger.info(f"Rights Issues Found:     {self.stats['rights_found']:>6,}")
        logger.info(f"Bonus Shares Found:      {self.stats['bonus_shares_found']:>6,}")
        logger.info(f"Records Inserted:        {self.stats['records_inserted']:>6,}")
        logger.info(f"Records Failed:          {self.stats['records_failed']:>6,}")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Collect corporate actions from DART API')
    parser.add_argument('--start', type=str, default='2019-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--tickers', type=str, help='Specific tickers to process (comma-separated)')

    args = parser.parse_args()

    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        logger.error(f"❌ Invalid date format: {e}")
        return 1

    # Load tickers
    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(',')]
    else:
        # Load from universe file
        universe_file = 'data/kr_universe_week3.csv'
        if not os.path.exists(universe_file):
            logger.error(f"❌ Universe file not found: {universe_file}")
            return 1

        df = pd.read_csv(universe_file)
        tickers = [str(ticker).zfill(6) for ticker in df['ticker'].tolist()]
        logger.info(f"Loaded {len(tickers)} tickers from universe")

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Run collection
    try:
        collector = DARTCorporateActionsCollector(db=db, dry_run=args.dry_run)
        collector.run_collection(tickers=tickers, start_date=start_date, end_date=end_date)
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
