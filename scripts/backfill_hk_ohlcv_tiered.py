#!/usr/bin/env python3
"""
HK OHLCV Tiered Backfill Script

Prioritized backfill strategy for Hong Kong market:
- Tier 1: HSI constituents (80 tickers, 5 years)
- Tier 2: High market cap (500 tickers, 3 years)
- Tier 3: Mid market cap (800 tickers, 2 years)
- Tier 4: Small cap & remaining (1,343 tickers, 1 year)

Usage:
    python3 scripts/backfill_hk_ohlcv_tiered.py \\
      --tier 1 \\
      --tickers-file data/hk_hsi_constituents.csv \\
      --start-date 2020-01-01 \\
      --end-date 2025-11-12 \\
      --rate-limit 1.0 \\
      --validate-quality \\
      --log-file logs/hk_tier1_backfill.log
"""

import argparse
import logging
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.market_adapters.hk_adapter import HKAdapter
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.data_quality.hk_validator import HKDataQualityValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HKTieredBackfiller:
    """
    Tiered backfill strategy for HK market data
    """

    TIER_CONFIG = {
        1: {
            'name': 'HSI Constituents',
            'years': 5,
            'priority': 'critical'
        },
        2: {
            'name': 'High Market Cap (>$1B)',
            'years': 3,
            'priority': 'high'
        },
        3: {
            'name': 'Mid Market Cap ($100M-$1B)',
            'years': 2,
            'priority': 'medium'
        },
        4: {
            'name': 'Small Cap & Remaining',
            'years': 1,
            'priority': 'low'
        }
    }

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize backfiller

        Args:
            rate_limit: Requests per second (yfinance limit)
        """
        # Database manager
        self.db_manager = PostgresDatabaseManager()

        # HK adapter
        self.hk_adapter = HKAdapter(self.db_manager)

        # Override yfinance rate limit
        self.hk_adapter.yfinance_api.rate_limit = rate_limit

        # Validator
        self.validator = HKDataQualityValidator()

        logger.info(f"🇭🇰 HK Tiered Backfiller initialized (rate limit: {rate_limit} req/s)")

    def load_tickers_from_file(self, file_path: str) -> List[str]:
        """
        Load tickers from CSV file

        Args:
            file_path: Path to CSV file with 'ticker' column

        Returns:
            List of tickers
        """
        logger.info(f"Loading tickers from: {file_path}")

        df = pd.read_csv(file_path)

        if 'ticker' not in df.columns:
            raise ValueError(f"CSV must have 'ticker' column. Found: {df.columns.tolist()}")

        tickers = df['ticker'].astype(str).str.zfill(4).tolist()

        logger.info(f"✅ Loaded {len(tickers)} tickers from file")

        return tickers

    def get_tier_tickers(self, tier: int, tickers_file: Optional[str] = None) -> List[str]:
        """
        Get tickers for specified tier

        Args:
            tier: Tier number (1-4)
            tickers_file: Optional CSV file with tickers (for Tier 1)

        Returns:
            List of tickers for this tier
        """
        if tier == 1:
            if tickers_file:
                return self.load_tickers_from_file(tickers_file)
            else:
                # Use default HSI list from HKAdapter
                return self.hk_adapter.DEFAULT_HK_TICKERS

        elif tier == 2:
            # High market cap (>$1B)
            if tickers_file:
                return self.load_tickers_from_file(tickers_file)
            else:
                # Query from database (not supported yet - requires SQLAlchemy engine)
                raise NotImplementedError(
                    "Tier 2 database query not yet supported. Please provide --tickers-file option."
                )

        elif tier == 3:
            # Mid market cap ($100M-$1B)
            if tickers_file:
                return self.load_tickers_from_file(tickers_file)
            else:
                raise NotImplementedError(
                    "Tier 3 database query not yet supported. Please provide --tickers-file option."
                )

        elif tier == 4:
            # Small cap & remaining
            if tickers_file:
                return self.load_tickers_from_file(tickers_file)
            else:
                raise NotImplementedError(
                    "Tier 4 database query not yet supported. Please provide --tickers-file option."
                )

        else:
            raise ValueError(f"Invalid tier: {tier}. Must be 1-4.")

    def backfill_tier(self,
                      tier: int,
                      tickers_file: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      validate: bool = True) -> Dict:
        """
        Backfill OHLCV data for specified tier

        Args:
            tier: Tier number (1-4)
            tickers_file: CSV file with tickers (Tier 1 only)
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            validate: Run quality validation after backfill

        Returns:
            {
                'tier': 1,
                'tier_name': 'HSI Constituents',
                'total_tickers': 80,
                'success_count': 78,
                'failed_tickers': ['0001', '0002'],
                'duration_seconds': 7200,
                'validation_results': {...}
            }
        """
        config = self.TIER_CONFIG[tier]

        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Tier {tier}: {config['name']}")
        logger.info(f"Priority: {config['priority']}")
        logger.info(f"{'='*60}\n")

        # Get tickers for this tier
        tickers = self.get_tier_tickers(tier, tickers_file)
        logger.info(f"Found {len(tickers)} tickers for Tier {tier}")

        # Calculate date range
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        if start_date is None:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            start_dt = end_dt - timedelta(days=config['years'] * 365)
            start_date = start_dt.strftime('%Y-%m-%d')

        logger.info(f"Date range: {start_date} to {end_date}")

        # Calculate days
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end_dt - start_dt).days

        # Backfill each ticker
        start_time = time.time()
        success_count = 0
        failed_tickers = []

        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"[{i}/{len(tickers)}] Backfilling {ticker}...")

                # Use HKAdapter to collect OHLCV
                count = self.hk_adapter.collect_stock_ohlcv(
                    tickers=[ticker],
                    days=days
                )

                if count > 0:
                    success_count += 1
                    logger.info(f"✅ {ticker}: {count} records saved")
                else:
                    failed_tickers.append(ticker)
                    logger.warning(f"⚠️ {ticker}: No data collected")

            except Exception as e:
                logger.error(f"❌ Failed to backfill {ticker}: {e}")
                failed_tickers.append(ticker)

        duration = time.time() - start_time

        # Results
        results = {
            'tier': tier,
            'tier_name': config['name'],
            'total_tickers': len(tickers),
            'success_count': success_count,
            'failed_count': len(failed_tickers),
            'failed_tickers': failed_tickers,
            'duration_seconds': duration,
            'start_date': start_date,
            'end_date': end_date,
            'validation_results': None
        }

        # Validation
        if validate and success_count > 0:
            logger.info(f"\nRunning quality validation for Tier {tier}...")

            # Only validate successfully backfilled tickers
            successful_tickers = [t for t in tickers if t not in failed_tickers]

            try:
                from modules.data_quality.hk_validator import validate_hk_market_data
                validation_df = validate_hk_market_data(tickers=successful_tickers)

                results['validation_results'] = {
                    'total_validated': len(validation_df),
                    'passed': int(validation_df['passed'].sum()),
                    'failed': int((~validation_df['passed']).sum()),
                    'avg_completeness': float(validation_df['completeness_score'].mean()),
                    'avg_validity': float(validation_df['validity_score'].mean()),
                    'avg_consistency': float(validation_df['consistency_score'].mean())
                }

                logger.info(f"✅ Validation complete: {results['validation_results']['passed']}/{results['validation_results']['total_validated']} passed")

            except Exception as e:
                logger.error(f"❌ Validation failed: {e}")
                results['validation_results'] = {'error': str(e)}

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"Tier {tier} Backfill Complete")
        logger.info(f"Success: {success_count}/{len(tickers)} ({success_count/len(tickers)*100:.1f}%)")
        logger.info(f"Duration: {duration/3600:.1f} hours")
        if results['validation_results'] and 'passed' in results['validation_results']:
            val = results['validation_results']
            logger.info(f"Validation: {val['passed']}/{val['total_validated']} passed ({val['passed']/val['total_validated']*100:.1f}%)")
        logger.info(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(description='HK OHLCV Tiered Backfill')
    parser.add_argument('--tier', type=int, required=True, choices=[1, 2, 3, 4],
                        help='Tier to backfill (1=HSI, 2=High Cap, 3=Mid Cap, 4=Small Cap)')
    parser.add_argument('--tickers-file', type=str, default=None,
                        help='CSV file with ticker list (for Tier 1)')
    parser.add_argument('--start-date', type=str, default=None,
                        help='Start date (YYYY-MM-DD). If not provided, calculated from tier config.')
    parser.add_argument('--end-date', type=str, default=None,
                        help='End date (YYYY-MM-DD). Default: today')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                        help='API requests per second (default: 1.0)')
    parser.add_argument('--validate-quality', action='store_true',
                        help='Run quality validation after backfill')
    parser.add_argument('--log-file', type=str, default=None,
                        help='Log file path')

    args = parser.parse_args()

    # Configure logging
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    # Run backfill
    backfiller = HKTieredBackfiller(rate_limit=args.rate_limit)
    results = backfiller.backfill_tier(
        tier=args.tier,
        tickers_file=args.tickers_file,
        start_date=args.start_date,
        end_date=args.end_date,
        validate=args.validate_quality
    )

    # Save results
    results_file = f'reports/hk_tier{args.tier}_backfill_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    os.makedirs('reports', exist_ok=True)

    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to: {results_file}")

    # Exit with error code if backfill failed significantly
    if results['success_count'] < results['total_tickers'] * 0.8:
        logger.error(f"⚠️ Backfill success rate < 80%. Exiting with error code 1.")
        sys.exit(1)
    else:
        logger.info(f"✅ Backfill completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
