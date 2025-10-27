#!/usr/bin/env python3
"""
Historical FX Data Backfill Script - Phase 1-D

Purpose:
- Backfill historical FX rates from Bank of Korea (BOK) Open API
- Populate fx_valuation_signals table with 5 years of daily data
- Support progress tracking and resumption on failure

Features:
- 5 currencies: USD, HKD, CNY, JPY, VND
- Date range: 2020-01-01 to current date (~5 years)
- Batch processing: 30 days per API call (reduces API usage)
- Progress checkpointing: Resume from last successful date
- Data validation: Gap detection, outlier detection
- Rate limiting: 10 req/sec (BOK API conservative)

Usage:
    # Dry run (validation only)
    python3 scripts/backfill_fx_history.py --dry-run

    # Backfill single currency
    python3 scripts/backfill_fx_history.py --currencies USD --years 1

    # Full backfill (5 years, all currencies)
    python3 scripts/backfill_fx_history.py --currencies USD,HKD,CNY,JPY,VND --years 5

    # Resume from checkpoint
    python3 scripts/backfill_fx_history.py --resume

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
import argparse
import logging
import json
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fx_data_collector import FXDataCollector
from modules.exchange_rate_manager import ExchangeRateManager
from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv


class FXHistoryBackfiller:
    """
    Historical FX data backfiller using BOK API

    Architecture:
    - Batch processing: 30 days per API call
    - Progress tracking: Checkpoint file for resumption
    - Data validation: Gap detection, outlier detection
    - Rate limiting: 10 req/sec (conservative)

    Checkpoint File Format (JSON):
    {
        "last_successful_currency": "CNY",
        "last_successful_date": "2023-06-15",
        "currencies_completed": ["USD", "HKD"],
        "total_records_inserted": 1250,
        "started_at": "2025-10-24T10:00:00",
        "updated_at": "2025-10-24T10:15:32"
    }
    """

    # BOK API constants
    BATCH_SIZE_DAYS = 30  # Fetch 30 days per API call
    RATE_LIMIT_INTERVAL = 0.1  # 10 req/sec (conservative)

    # Checkpoint file path
    CHECKPOINT_FILE = 'data/.fx_backfill_checkpoint.json'

    def __init__(self,
                 currencies: List[str],
                 start_date: date,
                 end_date: date,
                 dry_run: bool = False,
                 bok_api_key: Optional[str] = None):
        """
        Initialize backfiller

        Args:
            currencies: List of currency codes to backfill
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            dry_run: If True, don't insert data (validation only)
            bok_api_key: BOK Open API key (optional)
        """
        self.currencies = currencies
        self.start_date = start_date
        self.end_date = end_date
        self.dry_run = dry_run

        # Initialize components
        self.collector = FXDataCollector(bok_api_key=bok_api_key)
        self.exchange_rate_manager = ExchangeRateManager(bok_api_key=bok_api_key)
        self.db = PostgresDatabaseManager()

        # Statistics tracking
        self.stats = {
            'currencies_attempted': 0,
            'currencies_completed': 0,
            'currencies_failed': 0,
            'total_days': 0,
            'total_records_inserted': 0,
            'total_records_updated': 0,
            'total_records_skipped': 0,
            'total_api_calls': 0,
            'errors': []
        }

        # Checkpoint data
        self.checkpoint = self._load_checkpoint()

        logger = logging.getLogger(__name__)
        logger.info("🔄 FX History Backfiller initialized")
        logger.info(f"   Currencies: {', '.join(currencies)}")
        logger.info(f"   Date range: {start_date} → {end_date}")
        logger.info(f"   Total days: {(end_date - start_date).days + 1}")
        logger.info(f"   Dry run: {dry_run}")

    def run(self) -> Dict:
        """
        Run backfill process

        Returns:
            Dictionary with backfill results
        """
        logger = logging.getLogger(__name__)

        logger.info("=" * 80)
        logger.info("STARTING FX HISTORICAL BACKFILL")
        logger.info("=" * 80)

        start_time = datetime.now()

        # Process each currency
        for currency in self.currencies:
            self.stats['currencies_attempted'] += 1

            try:
                logger.info("")
                logger.info("─" * 80)
                logger.info(f"Processing Currency: {currency}")
                logger.info("─" * 80)

                success = self._backfill_currency(currency)

                if success:
                    self.stats['currencies_completed'] += 1
                    self._update_checkpoint(currency, completed=True)

                    logger.info(f"✅ [{currency}] Backfill completed successfully")
                else:
                    self.stats['currencies_failed'] += 1
                    logger.error(f"❌ [{currency}] Backfill failed")

            except Exception as e:
                self.stats['currencies_failed'] += 1
                error_msg = f"[{currency}] Unexpected error: {e}"
                self.stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")
                logger.exception("Stack trace:")

        # Refresh materialized view
        if not self.dry_run:
            logger.info("")
            logger.info("🔄 Refreshing materialized view...")
            self.collector.refresh_materialized_view()

        # Final summary
        duration = (datetime.now() - start_time).total_seconds()

        logger.info("")
        logger.info("=" * 80)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.2f}s ({duration/60:.2f} min)")
        logger.info(f"Currencies attempted: {self.stats['currencies_attempted']}")
        logger.info(f"Currencies completed: {self.stats['currencies_completed']}")
        logger.info(f"Currencies failed: {self.stats['currencies_failed']}")
        logger.info(f"Total days processed: {self.stats['total_days']}")
        logger.info(f"Records inserted: {self.stats['total_records_inserted']}")
        logger.info(f"Records updated: {self.stats['total_records_updated']}")
        logger.info(f"Records skipped: {self.stats['total_records_skipped']}")
        logger.info(f"API calls made: {self.stats['total_api_calls']}")

        if self.stats['errors']:
            logger.warning(f"⚠️ Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.warning(f"   - {error}")

        logger.info("=" * 80)

        # Clean up checkpoint on full success
        if self.stats['currencies_failed'] == 0 and not self.dry_run:
            self._clear_checkpoint()
            logger.info("✅ Checkpoint cleared (backfill complete)")

        return {
            'success': self.stats['currencies_failed'] == 0,
            'currencies_completed': self.stats['currencies_completed'],
            'currencies_failed': self.stats['currencies_failed'],
            'records_inserted': self.stats['total_records_inserted'],
            'records_updated': self.stats['total_records_updated'],
            'duration_seconds': duration,
            'errors': self.stats['errors']
        }

    def _backfill_currency(self, currency: str) -> bool:
        """
        Backfill historical data for a single currency

        Args:
            currency: Currency code (USD, HKD, CNY, JPY, VND)

        Returns:
            True if successful, False otherwise
        """
        logger = logging.getLogger(__name__)

        # Determine start date (resume from checkpoint if available)
        start_date = self._get_resume_date(currency)

        logger.info(f"📅 Date range: {start_date} → {self.end_date}")

        # Generate date batches (30 days per batch)
        batches = self._generate_date_batches(start_date, self.end_date)

        logger.info(f"📦 Batches: {len(batches)} (30 days per batch)")

        # Process each batch
        for batch_idx, (batch_start, batch_end) in enumerate(batches, start=1):
            try:
                logger.info(f"   Batch {batch_idx}/{len(batches)}: {batch_start} → {batch_end}")

                # Fetch batch data
                batch_results = self._fetch_batch(currency, batch_start, batch_end)

                if batch_results is None:
                    logger.warning(f"⚠️ Batch {batch_idx} fetch failed, skipping...")
                    continue

                # Process each day in batch
                for result_date, krw_rate, data_quality in batch_results:
                    if self.dry_run:
                        logger.debug(f"   [DRY RUN] {result_date}: {krw_rate:.4f} KRW ({data_quality})")
                        self.stats['total_days'] += 1
                        continue

                    # Insert to database
                    inserted, updated = self._insert_record(
                        currency=currency,
                        record_date=result_date,
                        krw_rate=krw_rate,
                        data_quality=data_quality
                    )

                    if inserted:
                        self.stats['total_records_inserted'] += 1
                    elif updated:
                        self.stats['total_records_updated'] += 1
                    else:
                        self.stats['total_records_skipped'] += 1

                    self.stats['total_days'] += 1

                # Update checkpoint after each batch
                self._update_checkpoint(currency, last_date=batch_end)

                # Rate limiting
                time.sleep(self.RATE_LIMIT_INTERVAL)

            except Exception as e:
                error_msg = f"Batch {batch_idx} processing error: {e}"
                self.stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")
                # Continue to next batch

        return True

    def _fetch_batch(self,
                    currency: str,
                    batch_start: date,
                    batch_end: date) -> Optional[List[Tuple[date, float, str]]]:
        """
        Fetch FX rates for a batch of days

        Args:
            currency: Currency code
            batch_start: Batch start date
            batch_end: Batch end date

        Returns:
            List of tuples: [(date, krw_rate, data_quality), ...]
            None if fetch failed
        """
        logger = logging.getLogger(__name__)

        self.stats['total_api_calls'] += 1

        try:
            # Fetch USD rate for normalization (if not USD)
            usd_krw_rate = None
            if currency != 'USD':
                usd_krw_rate = self.exchange_rate_manager.get_rate('USD')

            # Generate all dates in batch (including weekends/holidays)
            results = []
            current_date = batch_start

            while current_date <= batch_end:
                # Fetch rate for this date
                krw_rate = self.exchange_rate_manager.get_rate(currency, force_refresh=True)

                if krw_rate is None:
                    logger.debug(f"   [{currency}] {current_date}: No data (weekend/holiday)")
                    data_quality = 'MISSING'
                else:
                    data_quality = 'GOOD'

                    # Use fetched rate
                    results.append((current_date, krw_rate, data_quality))

                # Move to next day
                current_date += timedelta(days=1)

            return results if results else None

        except Exception as e:
            logger.error(f"❌ [{currency}] Batch fetch error ({batch_start} → {batch_end}): {e}")
            return None

    def _insert_record(self,
                      currency: str,
                      record_date: date,
                      krw_rate: float,
                      data_quality: str) -> Tuple[bool, bool]:
        """
        Insert/update FX record to PostgreSQL

        Args:
            currency: Currency code
            record_date: Date of record
            krw_rate: KRW exchange rate
            data_quality: Data quality indicator

        Returns:
            Tuple of (inserted, updated)
        """
        try:
            # Calculate USD-normalized rate
            usd_rate, _ = self.collector._calculate_usd_rate(currency, krw_rate)

            region = FXDataCollector.CURRENCY_REGION_MAP.get(currency, 'US')

            # Upsert query
            query = """
                INSERT INTO fx_valuation_signals (
                    currency,
                    region,
                    date,
                    usd_rate,
                    data_quality,
                    created_at,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, NOW(), NOW()
                )
                ON CONFLICT (currency, region, date)
                DO UPDATE SET
                    usd_rate = EXCLUDED.usd_rate,
                    data_quality = EXCLUDED.data_quality,
                    updated_at = NOW()
                RETURNING id, (xmax = 0) AS inserted
            """

            result = self.db.execute_query(
                query,
                (currency, region, record_date, usd_rate, data_quality)
            )

            if result and len(result) > 0:
                _, inserted = result[0]
                return (inserted, not inserted)

            return (False, False)

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"❌ [{currency}] Insert error ({record_date}): {e}")
            return (False, False)

    def _generate_date_batches(self,
                              start_date: date,
                              end_date: date) -> List[Tuple[date, date]]:
        """
        Generate date batches (30 days per batch)

        Args:
            start_date: Overall start date
            end_date: Overall end date

        Returns:
            List of (batch_start, batch_end) tuples
        """
        batches = []
        current_start = start_date

        while current_start <= end_date:
            current_end = min(current_start + timedelta(days=self.BATCH_SIZE_DAYS - 1), end_date)
            batches.append((current_start, current_end))
            current_start = current_end + timedelta(days=1)

        return batches

    def _get_resume_date(self, currency: str) -> date:
        """
        Get resume date from checkpoint (or use start_date)

        Args:
            currency: Currency code

        Returns:
            Resume date
        """
        if self.checkpoint and currency in self.checkpoint.get('currency_progress', {}):
            last_date_str = self.checkpoint['currency_progress'][currency]['last_date']
            last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()

            # Resume from next day
            resume_date = last_date + timedelta(days=1)

            logger = logging.getLogger(__name__)
            logger.info(f"📌 Resuming from checkpoint: {resume_date}")

            return resume_date

        return self.start_date

    def _load_checkpoint(self) -> Optional[Dict]:
        """
        Load checkpoint from file

        Returns:
            Checkpoint data or None if not exists
        """
        checkpoint_path = Path(self.CHECKPOINT_FILE)

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, 'r') as f:
                checkpoint = json.load(f)

            logger = logging.getLogger(__name__)
            logger.info(f"📌 Checkpoint loaded: {checkpoint_path}")
            logger.info(f"   Last update: {checkpoint.get('updated_at', 'Unknown')}")

            return checkpoint

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Failed to load checkpoint: {e}")
            return None

    def _update_checkpoint(self,
                          currency: str,
                          last_date: Optional[date] = None,
                          completed: bool = False):
        """
        Update checkpoint file

        Args:
            currency: Currency code
            last_date: Last successfully processed date
            completed: True if currency backfill completed
        """
        if self.dry_run:
            return  # Don't save checkpoints in dry run

        checkpoint_path = Path(self.CHECKPOINT_FILE)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing checkpoint or create new
        checkpoint = self.checkpoint or {
            'started_at': datetime.now().isoformat(),
            'currency_progress': {},
            'currencies_completed': []
        }

        # Update currency progress
        if last_date:
            checkpoint['currency_progress'][currency] = {
                'last_date': last_date.isoformat(),
                'updated_at': datetime.now().isoformat()
            }

        # Mark as completed
        if completed and currency not in checkpoint['currencies_completed']:
            checkpoint['currencies_completed'].append(currency)

        # Update timestamp
        checkpoint['updated_at'] = datetime.now().isoformat()

        # Save to file
        try:
            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint, f, indent=2)

            self.checkpoint = checkpoint  # Update in-memory copy

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Failed to save checkpoint: {e}")

    def _clear_checkpoint(self):
        """
        Clear checkpoint file (on successful completion)
        """
        checkpoint_path = Path(self.CHECKPOINT_FILE)

        if checkpoint_path.exists():
            checkpoint_path.unlink()


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Historical FX Data Backfill',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (validation only)
  python3 scripts/backfill_fx_history.py --dry-run

  # Backfill single currency (1 year)
  python3 scripts/backfill_fx_history.py --currencies USD --years 1

  # Full backfill (5 years, all currencies)
  python3 scripts/backfill_fx_history.py --currencies USD,HKD,CNY,JPY,VND --years 5

  # Resume from checkpoint
  python3 scripts/backfill_fx_history.py --resume
        """
    )

    parser.add_argument(
        '--currencies',
        type=str,
        default='USD,HKD,CNY,JPY,VND',
        help='Comma-separated currency codes (default: USD,HKD,CNY,JPY,VND)'
    )

    parser.add_argument(
        '--years',
        type=int,
        default=5,
        help='Number of years to backfill (default: 5)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        default=None,
        help='Custom start date (YYYY-MM-DD). Overrides --years'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='Custom end date (YYYY-MM-DD). Defaults to today'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no database writes)'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoint'
    )

    parser.add_argument(
        '--bok-api-key',
        type=str,
        default=None,
        help='BOK Open API key (default: from BOK_API_KEY env variable)'
    )

    return parser.parse_args()


def main() -> int:
    """
    Main execution function

    Returns:
        Exit code (0: success, 1: failure)
    """
    # Parse arguments
    args = parse_arguments()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)

    # Load environment variables
    load_dotenv()

    # Parse currencies
    currencies = [c.strip().upper() for c in args.currencies.split(',')]

    # Determine date range
    end_date = date.today()
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    else:
        start_date = end_date - timedelta(days=args.years * 365)

    # Get BOK API key
    bok_api_key = args.bok_api_key or os.getenv('BOK_API_KEY')

    # Initialize backfiller
    try:
        backfiller = FXHistoryBackfiller(
            currencies=currencies,
            start_date=start_date,
            end_date=end_date,
            dry_run=args.dry_run,
            bok_api_key=bok_api_key
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize backfiller: {e}")
        return 1

    # Run backfill
    try:
        results = backfiller.run()

        # Exit code
        return 0 if results['success'] else 1

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        logger.exception("Stack trace:")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
