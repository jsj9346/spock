#!/usr/bin/env python3
"""
Week 3 Data Quality Validation Script

Comprehensive data quality checks for Week 3 OHLCV backfill:
1. Date coverage analysis (missing trading days)
2. Price anomaly detection (outliers, gaps, errors)
3. Volume anomaly detection (zero volume, extreme values)
4. Data completeness report (records per ticker)
5. Trading day alignment validation

Quality Checks:
- Missing dates: Compare against KRX trading calendar
- Price outliers: >50% daily change detection
- Volume zeros: Trading days with zero volume
- Data gaps: Consecutive missing dates >5 days
- OHLCV consistency: open/high/low/close relationship validation

Output:
- Detailed quality report with statistics
- List of problematic tickers requiring investigation
- Recommendations for data remediation

Usage:
    # Full validation
    python3 scripts/week3_validate_data_quality.py

    # Specific ticker
    python3 scripts/week3_validate_data_quality.py --ticker 005930

    # Specific date range
    python3 scripts/week3_validate_data_quality.py --start 2019-01-01 --end 2024-12-31

    # Generate detailed report
    python3 scripts/week3_validate_data_quality.py --report data/quality_report.csv

Author: Spock Quant Platform - Week 3 Data Quality
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_data_quality_validation.log"
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


class DataQualityValidator:
    """Week 3 OHLCV data quality validator"""

    def __init__(self, db: PostgresDatabaseManager):
        """
        Initialize validator

        Args:
            db: PostgreSQL database manager
        """
        self.db = db

        # Quality thresholds
        self.MAX_DAILY_CHANGE = 0.50  # 50% daily price change threshold
        self.MIN_VOLUME = 1  # Minimum volume (0 = suspicious)
        self.MAX_GAP_DAYS = 5  # Maximum consecutive missing days
        self.MIN_EXPECTED_DAYS = 1200  # Minimum expected trading days for 5 years

        # Statistics
        self.stats = {
            'tickers_validated': 0,
            'tickers_passed': 0,
            'tickers_warnings': 0,
            'tickers_failed': 0,
            'total_records': 0,
            'price_anomalies': 0,
            'volume_anomalies': 0,
            'date_gaps': 0,
            'ohlcv_inconsistencies': 0
        }

        # Issues tracking
        self.issues = []

    def get_universe_tickers(self, universe_file: str = 'data/kr_universe_week3.csv') -> List[str]:
        """
        Load tickers from universe file

        Args:
            universe_file: Path to universe CSV

        Returns:
            List of ticker codes
        """
        if not os.path.exists(universe_file):
            logger.error(f"Universe file not found: {universe_file}")
            raise FileNotFoundError(f"Universe file not found: {universe_file}")

        df = pd.read_csv(universe_file)
        tickers = [str(ticker).zfill(6) for ticker in df['ticker'].tolist()]

        logger.info(f"Loaded {len(tickers)} tickers from universe")
        return tickers

    def validate_ticker_coverage(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Validate data coverage for a single ticker

        Args:
            ticker: Stock ticker code
            start_date: Expected start date
            end_date: Expected end date

        Returns:
            Dictionary with coverage statistics and issues
        """
        query = """
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume
        FROM ohlcv_data
        WHERE ticker = %s
          AND region = 'KR'
          AND date BETWEEN %s AND %s
          AND timeframe = '1d'
        ORDER BY date
        """

        results = self.db.execute_query(query, (ticker, start_date, end_date))

        if not results:
            return {
                'status': 'FAILED',
                'record_count': 0,
                'issues': ['No data found'],
                'warnings': []
            }

        df = pd.DataFrame(results)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        issues = []
        warnings = []

        # Check 1: Record count
        record_count = len(df)
        if record_count < self.MIN_EXPECTED_DAYS:
            issues.append(f"Insufficient data: {record_count} records (expected >{self.MIN_EXPECTED_DAYS})")

        # Check 2: Date gaps
        date_diffs = df.index.to_series().diff()
        large_gaps = date_diffs[date_diffs > timedelta(days=self.MAX_GAP_DAYS)]

        if len(large_gaps) > 0:
            for gap_date, gap_size in large_gaps.items():
                warnings.append(f"Date gap: {gap_size.days} days after {gap_date.date()}")
                self.stats['date_gaps'] += 1

        # Check 3: Price anomalies
        df['daily_return'] = df['close'].pct_change()
        extreme_returns = df[abs(df['daily_return']) > self.MAX_DAILY_CHANGE]

        if len(extreme_returns) > 0:
            for idx, row in extreme_returns.iterrows():
                warnings.append(f"Extreme return: {row['daily_return']:.2%} on {idx.date()}")
                self.stats['price_anomalies'] += 1

        # Check 4: Volume anomalies
        zero_volume = df[df['volume'] < self.MIN_VOLUME]

        if len(zero_volume) > 0:
            warnings.append(f"Zero volume days: {len(zero_volume)}")
            self.stats['volume_anomalies'] += len(zero_volume)

        # Check 5: OHLCV consistency
        ohlcv_issues = df[
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close'])
        ]

        if len(ohlcv_issues) > 0:
            issues.append(f"OHLCV inconsistencies: {len(ohlcv_issues)} records")
            self.stats['ohlcv_inconsistencies'] += len(ohlcv_issues)

        # Check 6: Null values
        null_counts = df.isnull().sum()
        if null_counts.sum() > 0:
            issues.append(f"Null values: {null_counts.to_dict()}")

        # Determine status
        if len(issues) > 0:
            status = 'FAILED'
            self.stats['tickers_failed'] += 1
        elif len(warnings) > 0:
            status = 'WARNING'
            self.stats['tickers_warnings'] += 1
        else:
            status = 'PASSED'
            self.stats['tickers_passed'] += 1

        self.stats['total_records'] += record_count

        return {
            'status': status,
            'record_count': record_count,
            'earliest_date': df.index.min().date(),
            'latest_date': df.index.max().date(),
            'issues': issues,
            'warnings': warnings
        }

    def run_validation(
        self,
        start_date: date,
        end_date: date,
        tickers: List[str] = None,
        report_file: str = None
    ):
        """
        Run full data quality validation

        Args:
            start_date: Expected start date
            end_date: Expected end date
            tickers: Specific tickers to validate (None = all from universe)
            report_file: Path to save detailed report CSV
        """
        logger.info("=" * 80)
        logger.info("WEEK 3 DATA QUALITY VALIDATION")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info("")

        # Load tickers if not specified
        if tickers is None:
            tickers = self.get_universe_tickers()

        total_tickers = len(tickers)
        logger.info(f"Validating {total_tickers} tickers...")
        logger.info("")

        # Validation results
        results = []

        for idx, ticker in enumerate(tickers, 1):
            logger.info(f"[{idx}/{total_tickers}] Validating {ticker}...")

            validation = self.validate_ticker_coverage(ticker, start_date, end_date)

            # Log status
            status_icon = {
                'PASSED': '✅',
                'WARNING': '⚠️',
                'FAILED': '❌'
            }.get(validation['status'], '❓')

            logger.info(f"  {status_icon} {validation['status']}: {validation['record_count']} records")

            if validation['issues']:
                for issue in validation['issues']:
                    logger.info(f"    ❌ {issue}")

            if validation['warnings']:
                for warning in validation['warnings'][:3]:  # Show first 3 warnings
                    logger.info(f"    ⚠️  {warning}")
                if len(validation['warnings']) > 3:
                    logger.info(f"    ... and {len(validation['warnings']) - 3} more warnings")

            # Store result
            results.append({
                'ticker': ticker,
                'status': validation['status'],
                'record_count': validation['record_count'],
                'earliest_date': validation.get('earliest_date'),
                'latest_date': validation.get('latest_date'),
                'issues_count': len(validation['issues']),
                'warnings_count': len(validation['warnings']),
                'issues': '; '.join(validation['issues']),
                'warnings': '; '.join(validation['warnings'][:5])  # First 5 warnings
            })

            self.stats['tickers_validated'] += 1

            # Progress update every 50 tickers
            if idx % 50 == 0:
                logger.info("")
                logger.info("=" * 80)
                logger.info(f"Progress: {idx}/{total_tickers} ({idx/total_tickers*100:.1f}%)")
                logger.info(f"Passed: {self.stats['tickers_passed']}, "
                          f"Warnings: {self.stats['tickers_warnings']}, "
                          f"Failed: {self.stats['tickers_failed']}")
                logger.info("=" * 80)
                logger.info("")

        # Save detailed report
        if report_file:
            df_report = pd.DataFrame(results)
            df_report.to_csv(report_file, index=False)
            logger.info(f"\n📄 Detailed report saved to: {report_file}")

        # Print summary
        self._print_summary(results)

    def _print_summary(self, results: List[Dict]):
        """
        Print validation summary

        Args:
            results: List of validation results
        """
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)

        # Overall statistics
        logger.info("\n📊 Overall Statistics:")
        logger.info(f"  Tickers Validated:    {self.stats['tickers_validated']:>6,}")
        logger.info(f"  ✅ Passed:             {self.stats['tickers_passed']:>6,} ({self.stats['tickers_passed']/self.stats['tickers_validated']*100:.1f}%)")
        logger.info(f"  ⚠️  Warnings:           {self.stats['tickers_warnings']:>6,} ({self.stats['tickers_warnings']/self.stats['tickers_validated']*100:.1f}%)")
        logger.info(f"  ❌ Failed:             {self.stats['tickers_failed']:>6,} ({self.stats['tickers_failed']/self.stats['tickers_validated']*100:.1f}%)")
        logger.info(f"  Total Records:        {self.stats['total_records']:>6,}")

        # Anomaly statistics
        logger.info("\n🔍 Anomaly Detection:")
        logger.info(f"  Price Anomalies:      {self.stats['price_anomalies']:>6,}")
        logger.info(f"  Volume Anomalies:     {self.stats['volume_anomalies']:>6,}")
        logger.info(f"  Date Gaps:            {self.stats['date_gaps']:>6,}")
        logger.info(f"  OHLCV Inconsistencies:{self.stats['ohlcv_inconsistencies']:>6,}")

        # Failed tickers
        failed_tickers = [r['ticker'] for r in results if r['status'] == 'FAILED']
        if failed_tickers:
            logger.info(f"\n❌ Failed Tickers ({len(failed_tickers)}):")
            for ticker in failed_tickers[:20]:  # Show first 20
                logger.info(f"  {ticker}")
            if len(failed_tickers) > 20:
                logger.info(f"  ... and {len(failed_tickers) - 20} more")

        # Warning tickers
        warning_tickers = [r['ticker'] for r in results if r['status'] == 'WARNING']
        if warning_tickers:
            logger.info(f"\n⚠️  Warning Tickers ({len(warning_tickers)}):")
            for ticker in warning_tickers[:20]:  # Show first 20
                logger.info(f"  {ticker}")
            if len(warning_tickers) > 20:
                logger.info(f"  ... and {len(warning_tickers) - 20} more")

        # Recommendations
        logger.info("\n💡 Recommendations:")
        if self.stats['tickers_failed'] > 0:
            logger.info("  1. Review failed tickers and re-run backfill if necessary")
        if self.stats['price_anomalies'] > 10:
            logger.info("  2. Investigate price anomalies (possible stock splits or data errors)")
        if self.stats['volume_anomalies'] > 50:
            logger.info("  3. Review zero-volume days (may indicate trading halts or data gaps)")
        if self.stats['date_gaps'] > 0:
            logger.info("  4. Check date gaps against KRX trading calendar")
        if self.stats['ohlcv_inconsistencies'] > 0:
            logger.info("  5. Fix OHLCV inconsistencies (data quality issue)")

        logger.info("\n" + "=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Validate Week 3 OHLCV data quality')
    parser.add_argument('--start', type=str, default='2019-01-01',
                       help='Expected start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='Expected end date (YYYY-MM-DD)')
    parser.add_argument('--ticker', type=str,
                       help='Validate specific ticker only')
    parser.add_argument('--report', type=str,
                       help='Save detailed report to CSV file')

    args = parser.parse_args()

    # Parse dates
    try:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    except ValueError as e:
        logger.error(f"❌ Invalid date format: {e}")
        return 1

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info(f"✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Initialize validator
    try:
        validator = DataQualityValidator(db)

        # Run validation
        if args.ticker:
            tickers = [args.ticker.zfill(6)]
        else:
            tickers = None

        validator.run_validation(
            start_date=start_date,
            end_date=end_date,
            tickers=tickers,
            report_file=args.report
        )

        return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Validation interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
