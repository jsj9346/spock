#!/usr/bin/env python3
"""
Historical Fundamental Data Backfill Script - Phase 2

Collects detailed financial data for multiple fiscal years from DART API.

Usage:
    # Dry run with 10 tickers
    python3 scripts/backfill_phase2_historical.py --dry-run --limit 10

    # Full backfill: All KR stocks, 3 years (2022-2024)
    python3 scripts/backfill_phase2_historical.py --start-year 2022 --end-year 2024

    # Resume from checkpoint
    python3 scripts/backfill_phase2_historical.py --checkpoint data/backfill_checkpoint.json

    # Specific tickers
    python3 scripts/backfill_phase2_historical.py --tickers 005930,000660,035720

Author: Spock Quant Platform - Phase 2
Date: 2025-10-24
"""

import sys
import os
import argparse
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/phase2_historical_backfill_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Phase2HistoricalBackfiller:
    """
    Multi-year fundamental data backfiller with checkpoint support

    Features:
    - Multi-year data collection (2022-2024)
    - Rate limiting (1 req/sec default)
    - Checkpoint/resume functionality
    - Dry-run mode for testing
    - Progress tracking
    """

    def __init__(self, start_year: int = 2022, end_year: int = 2024,
                 rate_limit: float = 1.0, dry_run: bool = False,
                 checkpoint_file: Optional[str] = None):
        """
        Initialize backfiller

        Args:
            start_year: Start fiscal year (inclusive)
            end_year: End fiscal year (inclusive)
            rate_limit: Requests per second (default: 1.0)
            dry_run: Test mode without database writes
            checkpoint_file: Path to checkpoint file for resume
        """
        self.start_year = start_year
        self.end_year = end_year
        self.rate_limit = rate_limit
        self.dry_run = dry_run
        self.checkpoint_file = checkpoint_file or 'data/phase2_checkpoint.json'

        # Initialize DART API client
        dart_api_key = os.getenv('DART_API_KEY')
        if not dart_api_key:
            raise ValueError("DART_API_KEY not found in environment variables")

        self.dart_client = DARTApiClient(api_key=dart_api_key)

        # Initialize database (only if not dry run)
        if not dry_run:
            self.db = PostgresDatabaseManager()
        else:
            self.db = None
            logger.info("🧪 DRY RUN MODE: No database writes will be performed")

        # Statistics
        self.stats = {
            'total_tickers': 0,
            'tickers_processed': 0,
            'tickers_failed': 0,
            'tickers_skipped_no_corp_code': 0,
            'api_calls': 0,
            'api_errors': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'start_time': datetime.now()
        }

        # Load corp_code mapping
        self.corp_code_map = self._load_corp_code_mapping()

        # Load checkpoint
        self.checkpoint = self._load_checkpoint()

    def _load_corp_code_mapping(self) -> Dict[str, str]:
        """
        Load DART corp_code mapping from database or DART XML

        Returns:
            Dict mapping ticker -> corp_code
        """
        logger.info("Loading DART corp_code mapping...")

        # Note: corp_code is not stored in database, always use DART XML
        # Download and parse DART corp codes XML
        try:
            logger.info("Downloading DART corp codes XML...")
            xml_path = self.dart_client.download_corp_codes()

            if not xml_path or not os.path.exists(xml_path):
                raise Exception("Failed to download corp codes XML")

            # Parse corp codes
            corp_data = self.dart_client.parse_corp_codes(xml_path)

            # Create mapping: stock_code -> corp_code
            mapping = {}
            for corp_name, data in corp_data.items():
                stock_code = data.get('stock_code')
                corp_code = data.get('corp_code')

                if stock_code and corp_code and stock_code.strip():
                    # Normalize to 6 digits
                    stock_code_normalized = stock_code.strip().zfill(6)
                    mapping[stock_code_normalized] = corp_code

            logger.info(f"✅ Loaded {len(mapping)} corp codes from DART XML")
            return mapping

        except Exception as e:
            logger.error(f"Failed to load corp codes from DART XML: {e}")

        # If all else fails, return empty dict
        logger.warning("⚠️ No corp code mapping available")
        return {}

    def _load_checkpoint(self) -> Dict:
        """Load checkpoint from file (resume support)"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                logger.info(f"📂 Loaded checkpoint: {checkpoint.get('tickers_processed', 0)} tickers processed")
                return checkpoint
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

        return {
            'tickers_processed': 0,
            'processed_tickers': [],
            'last_update': datetime.now().isoformat()
        }

    def _save_checkpoint(self):
        """Save current progress to checkpoint file"""
        if self.dry_run:
            return  # Skip checkpoint in dry run

        self.checkpoint['tickers_processed'] = self.stats['tickers_processed']
        self.checkpoint['last_update'] = datetime.now().isoformat()

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)

        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def get_kr_tickers(self, limit: Optional[int] = None,
                       specific_tickers: Optional[List[str]] = None) -> List[str]:
        """
        Get list of KR tickers from database

        Args:
            limit: Limit number of tickers (for testing)
            specific_tickers: Specific ticker list (overrides database query)

        Returns:
            List of ticker symbols
        """
        if specific_tickers:
            logger.info(f"Using specific tickers: {len(specific_tickers)} tickers")
            return specific_tickers

        if self.dry_run:
            # For dry run, use a small test set
            test_tickers = ['005930', '000660', '035720', '051910', '006400'][:limit or 10]
            logger.info(f"🧪 DRY RUN: Using test tickers: {test_tickers}")
            return test_tickers

        try:
            query = """
            SELECT DISTINCT ticker
            FROM tickers
            WHERE region = 'KR'
              AND is_active = true
              AND asset_type = 'STOCK'  -- Only process stocks (exclude ETF, REIT, PREFERRED)
            ORDER BY ticker
            """

            if limit:
                query += f" LIMIT {limit}"

            results = self.db.execute_query(query)
            tickers = [row['ticker'] for row in results]

            logger.info(f"📋 Retrieved {len(tickers)} KR tickers from database")
            return tickers

        except Exception as e:
            logger.error(f"Failed to get tickers: {e}")
            return []

    def process_ticker_historical(self, ticker: str) -> bool:
        """
        Process historical data for a single ticker (multiple years)

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if successful, False otherwise
        """
        # Skip if already processed
        if ticker in self.checkpoint.get('processed_tickers', []):
            logger.debug(f"⏭️  {ticker}: Already processed (from checkpoint)")
            return True

        try:
            logger.info(f"🔄 [{ticker}] Fetching {self.end_year - self.start_year + 1} years of data...")

            # Rate limiting
            time.sleep(1.0 / self.rate_limit)

            # Look up corp_code from mapping
            corp_code = self.corp_code_map.get(ticker)
            if not corp_code:
                logger.warning(f"⚠️  [{ticker}] Corp code not found in mapping - skipping")
                self.stats['tickers_skipped_no_corp_code'] += 1
                return False

            # Fetch all years in one API call
            metrics_list = self.dart_client.get_historical_fundamentals(
                ticker=ticker,
                corp_code=corp_code,
                start_year=self.start_year,
                end_year=self.end_year
            )
            self.stats['api_calls'] += 1

            if not metrics_list:
                logger.warning(f"⚠️  [{ticker}] No historical data found")
                self.stats['tickers_failed'] += 1
                return False

            # Process each year's data
            success_count = 0
            for metrics in metrics_list:
                year = metrics.get('fiscal_year', 'Unknown')

                try:
                    # In dry run, just log the data
                    if self.dry_run:
                        revenue = metrics.get('revenue', 0)
                        cogs = metrics.get('cogs', 0)
                        ebitda = metrics.get('ebitda', 0)
                        logger.info(f"🧪 [{ticker}] FY{year}: Revenue={revenue:,.0f}, "
                                  f"COGS={cogs:,.0f}, EBITDA={ebitda:,.0f}")
                        success_count += 1
                        continue

                    # Insert/update database
                    self._upsert_fundamental_data(ticker, metrics)
                    success_count += 1

                    logger.info(f"✅ [{ticker}] FY{year}: Saved to database")

                except Exception as e:
                    logger.error(f"❌ [{ticker}] FY{year}: Error - {e}")
                    self.stats['api_errors'] += 1

            # Mark ticker as processed
            if success_count > 0:
                self.checkpoint.setdefault('processed_tickers', []).append(ticker)
                self.stats['tickers_processed'] += 1
                logger.info(f"✅ [{ticker}] Completed: {success_count}/{len(metrics_list)} years successful")
                return True
            else:
                self.stats['tickers_failed'] += 1
                logger.error(f"❌ [{ticker}] Failed: No data saved")
                return False

        except Exception as e:
            logger.error(f"❌ [{ticker}] Fatal error: {e}")
            self.stats['tickers_failed'] += 1
            return False

    def _upsert_fundamental_data(self, ticker: str, metrics: Dict):
        """
        Insert or update fundamental data in database

        Args:
            ticker: Stock ticker symbol
            metrics: Metrics dict from DART API client
        """
        try:
            # Prepare data dict with all 54 columns
            data = {
                'ticker': ticker,
                'region': 'KR',
                'date': metrics.get('date', datetime.now().strftime('%Y-%m-%d')),
                'period_type': metrics.get('period_type', 'ANNUAL'),
                'fiscal_year': metrics.get('fiscal_year'),
                'data_source': metrics.get('data_source', 'DART'),

                # Valuation metrics
                'shares_outstanding': metrics.get('shares_outstanding'),
                'market_cap': metrics.get('market_cap'),
                'close_price': metrics.get('close_price'),
                'per': metrics.get('per'),
                'pbr': metrics.get('pbr'),
                'psr': metrics.get('psr'),

                # Financial statements (existing)
                'total_assets': metrics.get('total_assets'),
                'total_liabilities': metrics.get('total_liabilities'),
                'total_equity': metrics.get('total_equity'),
                'revenue': metrics.get('revenue'),
                'operating_profit': metrics.get('operating_profit'),
                'net_income': metrics.get('net_income'),
                'current_assets': metrics.get('current_assets'),
                'current_liabilities': metrics.get('current_liabilities'),
                'inventory': metrics.get('inventory'),

                # Phase 2: Detailed financial items (18 new columns)
                'cogs': metrics.get('cogs'),
                'gross_profit': metrics.get('gross_profit'),
                'pp_e': metrics.get('pp_e'),
                'depreciation': metrics.get('depreciation'),
                'accounts_receivable': metrics.get('accounts_receivable'),
                'accumulated_depreciation': metrics.get('accumulated_depreciation'),
                'sga_expense': metrics.get('sga_expense'),
                'rd_expense': metrics.get('rd_expense'),
                'operating_expense': metrics.get('operating_expense'),
                'interest_income': metrics.get('interest_income'),
                'interest_expense': metrics.get('interest_expense'),
                'loan_portfolio': metrics.get('loan_portfolio'),
                'npl_amount': metrics.get('npl_amount'),
                'nim': metrics.get('nim'),
                'investing_cf': metrics.get('investing_cf'),
                'financing_cf': metrics.get('financing_cf'),
                'ebitda': metrics.get('ebitda'),
                'ebitda_margin': metrics.get('ebitda_margin')
            }

            # UPSERT query (same as backfill_fundamentals_dart.py)
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr,
                total_assets, total_liabilities, total_equity,
                revenue, operating_profit, net_income,
                current_assets, current_liabilities, inventory,
                cogs, gross_profit, pp_e, depreciation, accounts_receivable, accumulated_depreciation,
                sga_expense, rd_expense, operating_expense,
                interest_income, interest_expense, loan_portfolio, npl_amount, nim,
                investing_cf, financing_cf, ebitda, ebitda_margin,
                fiscal_year,
                data_source, created_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                shares_outstanding = EXCLUDED.shares_outstanding,
                market_cap = EXCLUDED.market_cap,
                close_price = EXCLUDED.close_price,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                psr = EXCLUDED.psr,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                revenue = EXCLUDED.revenue,
                operating_profit = EXCLUDED.operating_profit,
                net_income = EXCLUDED.net_income,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                inventory = EXCLUDED.inventory,
                cogs = EXCLUDED.cogs,
                gross_profit = EXCLUDED.gross_profit,
                pp_e = EXCLUDED.pp_e,
                depreciation = EXCLUDED.depreciation,
                accounts_receivable = EXCLUDED.accounts_receivable,
                accumulated_depreciation = EXCLUDED.accumulated_depreciation,
                sga_expense = EXCLUDED.sga_expense,
                rd_expense = EXCLUDED.rd_expense,
                operating_expense = EXCLUDED.operating_expense,
                interest_income = EXCLUDED.interest_income,
                interest_expense = EXCLUDED.interest_expense,
                loan_portfolio = EXCLUDED.loan_portfolio,
                npl_amount = EXCLUDED.npl_amount,
                nim = EXCLUDED.nim,
                investing_cf = EXCLUDED.investing_cf,
                financing_cf = EXCLUDED.financing_cf,
                ebitda = EXCLUDED.ebitda,
                ebitda_margin = EXCLUDED.ebitda_margin,
                fiscal_year = EXCLUDED.fiscal_year,
                data_source = EXCLUDED.data_source
            """

            params = (
                data['ticker'], data['region'], data['date'], data['period_type'],
                data['shares_outstanding'], data['market_cap'], data['close_price'],
                data['per'], data['pbr'], data['psr'],
                data['total_assets'], data['total_liabilities'], data['total_equity'],
                data['revenue'], data['operating_profit'], data['net_income'],
                data['current_assets'], data['current_liabilities'], data['inventory'],
                data['cogs'], data['gross_profit'], data['pp_e'],
                data['depreciation'], data['accounts_receivable'], data['accumulated_depreciation'],
                data['sga_expense'], data['rd_expense'], data['operating_expense'],
                data['interest_income'], data['interest_expense'], data['loan_portfolio'],
                data['npl_amount'], data['nim'],
                data['investing_cf'], data['financing_cf'], data['ebitda'], data['ebitda_margin'],
                data['fiscal_year'],
                data['data_source']
            )

            self.db.execute_update(query, params)

            # Track insert vs update
            if 'INSERT' in self.db.cursor.statusmessage:
                self.stats['records_inserted'] += 1
            else:
                self.stats['records_updated'] += 1

        except Exception as e:
            logger.error(f"Failed to upsert data for {ticker}: {e}")
            raise

    def run(self, limit: Optional[int] = None, tickers: Optional[List[str]] = None):
        """
        Run historical backfill process

        Args:
            limit: Limit number of tickers (for testing)
            tickers: Specific ticker list
        """
        logger.info("=" * 80)
        logger.info("🚀 Phase 2: Historical Fundamental Data Backfill")
        logger.info("=" * 80)
        logger.info(f"📅 Period: FY{self.start_year} - FY{self.end_year}")
        logger.info(f"⚡ Rate limit: {self.rate_limit} req/sec")
        logger.info(f"🧪 Dry run: {self.dry_run}")
        logger.info("=" * 80)

        # Get ticker list
        ticker_list = self.get_kr_tickers(limit=limit, specific_tickers=tickers)
        self.stats['total_tickers'] = len(ticker_list)

        if not ticker_list:
            logger.error("No tickers to process")
            return

        logger.info(f"📋 Processing {len(ticker_list)} tickers...")

        # Process each ticker
        for idx, ticker in enumerate(ticker_list, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Progress: {idx}/{len(ticker_list)} ({idx/len(ticker_list)*100:.1f}%)")
            logger.info(f"{'='*60}")

            success = self.process_ticker_historical(ticker)

            # Save checkpoint every 10 tickers
            if idx % 10 == 0:
                self._save_checkpoint()
                self._print_stats()

        # Final checkpoint and stats
        self._save_checkpoint()
        self._print_final_stats()

    def _print_stats(self):
        """Print current statistics"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        logger.info(f"\n📊 Progress Stats:")
        logger.info(f"   Tickers: {self.stats['tickers_processed']}/{self.stats['total_tickers']}")
        logger.info(f"   API Calls: {self.stats['api_calls']} (Errors: {self.stats['api_errors']})")
        logger.info(f"   Records: {self.stats['records_inserted']} inserted, "
                   f"{self.stats['records_updated']} updated")
        logger.info(f"   Time: {elapsed/60:.1f} minutes")

    def _print_final_stats(self):
        """Print final statistics"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()

        logger.info("\n" + "="*80)
        logger.info("✅ BACKFILL COMPLETE")
        logger.info("="*80)
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   Total Tickers: {self.stats['total_tickers']}")
        logger.info(f"   Processed: {self.stats['tickers_processed']}")
        logger.info(f"   Failed: {self.stats['tickers_failed']}")
        logger.info(f"   Success Rate: {self.stats['tickers_processed']/self.stats['total_tickers']*100:.1f}%")
        logger.info(f"   API Calls: {self.stats['api_calls']}")
        logger.info(f"   API Errors: {self.stats['api_errors']}")
        logger.info(f"   Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"   Records Updated: {self.stats['records_updated']}")
        logger.info(f"   Total Time: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
        logger.info(f"   Avg Time/Ticker: {elapsed/self.stats['total_tickers']:.1f} seconds")
        logger.info("="*80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Phase 2: Historical Fundamental Data Backfill (DART API)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with 10 tickers
  python3 scripts/backfill_phase2_historical.py --dry-run --limit 10

  # Full backfill: 3 years (2022-2024)
  python3 scripts/backfill_phase2_historical.py --start-year 2022 --end-year 2024

  # Resume from checkpoint
  python3 scripts/backfill_phase2_historical.py --checkpoint data/phase2_checkpoint.json

  # Specific tickers
  python3 scripts/backfill_phase2_historical.py --tickers 005930,000660,035720
        """
    )

    parser.add_argument('--start-year', type=int, default=2022,
                       help='Start fiscal year (default: 2022)')
    parser.add_argument('--end-year', type=int, default=2024,
                       help='End fiscal year (default: 2024)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of tickers (for testing)')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Comma-separated ticker list (e.g., 005930,000660)')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                       help='API requests per second (default: 1.0)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Test mode without database writes')
    parser.add_argument('--checkpoint', type=str, default='data/phase2_checkpoint.json',
                       help='Checkpoint file path (default: data/phase2_checkpoint.json)')

    args = parser.parse_args()

    # Parse tickers
    ticker_list = None
    if args.tickers:
        ticker_list = [t.strip() for t in args.tickers.split(',')]

    # Initialize backfiller
    backfiller = Phase2HistoricalBackfiller(
        start_year=args.start_year,
        end_year=args.end_year,
        rate_limit=args.rate_limit,
        dry_run=args.dry_run,
        checkpoint_file=args.checkpoint
    )

    # Run backfill
    try:
        backfiller.run(limit=args.limit, tickers=ticker_list)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user")
        backfiller._save_checkpoint()
        backfiller._print_stats()
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        backfiller._save_checkpoint()
        sys.exit(1)


if __name__ == '__main__':
    main()
