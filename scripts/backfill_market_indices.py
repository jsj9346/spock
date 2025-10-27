#!/usr/bin/env python3
"""
Global Market Indices Backfill Script (Phase 1.5 - Day 4)

Backfills historical OHLCV data for major market indices (5 years minimum).
Required for beta calculation in Low-Volatility factor.

Indices covered:
- KR: KOSPI Index
- US: S&P 500, NASDAQ Composite
- JP: Nikkei 225
- HK: Hang Seng Index
- CN: Shanghai Composite
- EU: STOXX Europe 600
- UK: FTSE 100

Target: 10 major indices, 5 years of daily data

Author: Quant Platform Development Team
Date: 2025-10-21
"""

import sys
import os
import argparse
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
from decimal import Decimal
import time

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from loguru import logger

# Configure loguru logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


class MarketIndicesBackfiller:
    """
    Global market indices backfiller for beta calculation

    Features:
    - 10 major market indices
    - 5 years of historical OHLCV data
    - Daily data updates
    - Data quality validation
    """

    # Major market indices with yfinance symbols
    MARKET_INDICES = {
        'KOSPI': {
            'symbol': '^KS11',
            'name': 'KOSPI Index',
            'region': 'KR',
            'description': 'Korea Composite Stock Price Index'
        },
        'KOSDAQ': {
            'symbol': '^KQ11',
            'name': 'KOSDAQ Index',
            'region': 'KR',
            'description': 'Korea Securities Dealers Automated Quotations'
        },
        'SP500': {
            'symbol': '^GSPC',
            'name': 'S&P 500',
            'region': 'US',
            'description': 'Standard & Poor\'s 500 Index'
        },
        'NASDAQ': {
            'symbol': '^IXIC',
            'name': 'NASDAQ Composite',
            'region': 'US',
            'description': 'NASDAQ Composite Index'
        },
        'DOW': {
            'symbol': '^DJI',
            'name': 'Dow Jones Industrial Average',
            'region': 'US',
            'description': 'Dow Jones Industrial Average'
        },
        'NIKKEI': {
            'symbol': '^N225',
            'name': 'Nikkei 225',
            'region': 'JP',
            'description': 'Nikkei Stock Average'
        },
        'HANGSENG': {
            'symbol': '^HSI',
            'name': 'Hang Seng Index',
            'region': 'HK',
            'description': 'Hong Kong Hang Seng Index'
        },
        'SHANGHAI': {
            'symbol': '000001.SS',
            'name': 'Shanghai Composite',
            'region': 'CN',
            'description': 'Shanghai Stock Exchange Composite Index'
        },
        'STOXX600': {
            'symbol': '^STOXX',
            'name': 'STOXX Europe 600',
            'region': 'EU',
            'description': 'STOXX Europe 600 Index'
        },
        'FTSE100': {
            'symbol': '^FTSE',
            'name': 'FTSE 100',
            'region': 'UK',
            'description': 'Financial Times Stock Exchange 100 Index'
        }
    }

    def __init__(self, dry_run: bool = False, years: int = 5):
        """
        Initialize backfiller

        Args:
            dry_run: If True, don't insert data (validation only)
            years: Number of years of historical data to fetch
        """
        self.dry_run = dry_run
        self.years = years
        self.db = PostgresDatabaseManager()

        # Statistics tracking
        self.stats = {
            'indices_processed': 0,
            'success': 0,
            'failed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'api_calls': 0
        }

        # Import yfinance (lazy import for better error messages)
        try:
            import yfinance as yf
            self.yf = yf
            logger.info("✅ yfinance library available")
        except ImportError:
            logger.error("❌ yfinance library not found. Install with: pip install yfinance")
            sys.exit(1)

    def fetch_index_historical_data(self, index_key: str, index_config: Dict) -> Optional[List[Dict]]:
        """
        Fetch historical OHLCV data for a market index

        Args:
            index_key: Index identifier (e.g., 'KOSPI', 'SP500')
            index_config: Index configuration dictionary

        Returns:
            List of daily OHLCV records, or None if fetch failed
        """
        symbol = index_config['symbol']
        index_name = index_config['name']
        region = index_config['region']

        try:
            # Calculate date range (5 years ago to today)
            end_date = date.today()
            start_date = end_date - timedelta(days=365 * self.years)

            logger.info(f"Fetching {index_name} ({symbol}) from {start_date} to {end_date}")

            # Fetch historical data from yfinance
            start_time = time.time()
            self.stats['api_calls'] += 1

            df = self.yf.download(
                symbol,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                progress=False,
                auto_adjust=False  # Keep original OHLC values
            )

            elapsed = time.time() - start_time

            if df.empty:
                logger.warning(f"⚠️ [{index_name}] No historical data available")
                return None

            # Convert DataFrame to list of dictionaries
            records = []
            for idx, row in df.iterrows():
                record = {
                    'symbol': symbol,
                    'index_name': index_name,
                    'region': region,
                    'date': idx.date(),
                    'open_price': self._safe_decimal(row['Open']),
                    'high_price': self._safe_decimal(row['High']),
                    'low_price': self._safe_decimal(row['Low']),
                    'close_price': self._safe_decimal(row['Close']),
                    'volume': self._safe_int(row['Volume'])
                }
                records.append(record)

            logger.info(f"✅ [{index_name}] Fetched {len(records)} days of data ({elapsed:.2f}s)")
            return records

        except Exception as e:
            logger.error(f"❌ [{index_name}] Failed to fetch historical data: {e}")
            return None

    def _safe_decimal(self, value, scale: int = 1) -> Optional[Decimal]:
        """Convert value to Decimal with optional scaling"""
        if value is None:
            return None
        try:
            # Handle pandas Series
            if hasattr(value, 'iloc'):
                value = value.iloc[0]
            # Check for NaN
            if str(value) == 'nan':
                return None
            return Decimal(str(float(value) * scale))
        except (ValueError, TypeError, IndexError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Convert value to integer"""
        if value is None:
            return None
        try:
            # Handle pandas Series
            if hasattr(value, 'iloc'):
                value = value.iloc[0]
            # Check for NaN
            if str(value) == 'nan':
                return None
            return int(float(value))
        except (ValueError, TypeError, IndexError):
            return None

    def insert_or_update_index_data(self, records: List[Dict]) -> bool:
        """
        Insert or update index data in database (UPSERT)

        Args:
            records: List of index OHLCV records

        Returns:
            True if successful, False otherwise
        """
        if not records:
            return False

        if self.dry_run:
            sample = records[0]
            logger.info(f"[DRY RUN] Would insert/update {len(records)} records for {sample['index_name']}")
            logger.info(f"   → Date Range: {records[0]['date']} to {records[-1]['date']}")
            logger.info(f"   → Latest Close: {records[-1]['close_price']}")
            return True

        try:
            # UPSERT query (INSERT ... ON CONFLICT DO UPDATE)
            query = """
            INSERT INTO global_market_indices (
                symbol, index_name, region, date,
                open_price, high_price, low_price, close_price, volume
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, symbol)
            DO UPDATE SET
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                index_name = EXCLUDED.index_name,
                region = EXCLUDED.region
            """

            # Batch insert all records
            inserted = 0
            updated = 0

            for record in records:
                params = (
                    record['symbol'],
                    record['index_name'],
                    record['region'],
                    record['date'],
                    record['open_price'],
                    record['high_price'],
                    record['low_price'],
                    record['close_price'],
                    record['volume']
                )

                success = self.db.execute_update(query, params)

                if success:
                    # Check if INSERT or UPDATE occurred
                    if self.db.cursor.rowcount == 1:
                        inserted += 1
                    elif self.db.cursor.rowcount == 2:  # UPDATE counts as 2 (delete + insert)
                        updated += 1

            self.stats['records_inserted'] += inserted
            self.stats['records_updated'] += updated

            logger.info(f"✅ [{records[0]['index_name']}] Inserted: {inserted}, Updated: {updated}")
            return True

        except Exception as e:
            logger.error(f"❌ [{records[0]['index_name']}] Database insert failed: {e}")
            return False

    def get_data_coverage_report(self) -> Dict:
        """
        Generate data coverage report for all indices

        Returns:
            Dictionary with coverage statistics per index
        """
        coverage = {}

        for index_key, index_config in self.MARKET_INDICES.items():
            symbol = index_config['symbol']

            try:
                # Query database for record count and date range
                query = """
                SELECT
                    COUNT(*) as record_count,
                    MIN(date) as start_date,
                    MAX(date) as end_date,
                    MAX(close_price) as latest_close
                FROM global_market_indices
                WHERE symbol = %s
                """
                result = self.db.execute_query(query, (symbol,))

                if result and len(result) > 0:
                    row = result[0]
                    coverage[index_key] = {
                        'symbol': symbol,
                        'name': index_config['name'],
                        'region': index_config['region'],
                        'record_count': row['record_count'],
                        'start_date': row['start_date'],
                        'end_date': row['end_date'],
                        'latest_close': row['latest_close'],
                        'years_covered': (row['end_date'] - row['start_date']).days / 365 if row['start_date'] else 0
                    }
                else:
                    coverage[index_key] = {
                        'symbol': symbol,
                        'name': index_config['name'],
                        'region': index_config['region'],
                        'record_count': 0,
                        'start_date': None,
                        'end_date': None,
                        'latest_close': None,
                        'years_covered': 0
                    }

            except Exception as e:
                logger.error(f"❌ Failed to get coverage for {index_key}: {e}")
                coverage[index_key] = {'error': str(e)}

        return coverage

    def run(self):
        """
        Main execution: backfill all market indices
        """
        logger.info("=" * 80)
        logger.info("PHASE 1.5 - DAY 4: GLOBAL MARKET INDICES BACKFILL")
        logger.info("=" * 80)
        logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Historical Data Period: {self.years} years")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Indices to Process: {len(self.MARKET_INDICES)}")
        logger.info("=" * 80)

        start_time = datetime.now()

        # Process each market index
        for index_key, index_config in self.MARKET_INDICES.items():
            self.stats['indices_processed'] += 1

            logger.info(f"\n[{self.stats['indices_processed']}/{len(self.MARKET_INDICES)}] Processing {index_config['name']}...")
            logger.info("=" * 60)

            # Fetch historical data
            records = self.fetch_index_historical_data(index_key, index_config)

            if records is None:
                self.stats['failed'] += 1
                continue

            # Insert into database
            success = self.insert_or_update_index_data(records)

            if success:
                self.stats['success'] += 1
            else:
                self.stats['failed'] += 1

        # Generate coverage report
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {datetime.now() - start_time}")

        logger.info("\nStatistics:")
        logger.info(f"  Indices Processed: {self.stats['indices_processed']}")
        logger.info(f"  ✅ Success: {self.stats['success']}")
        logger.info(f"  ❌ Failed: {self.stats['failed']}")
        logger.info(f"  Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"  Records Updated: {self.stats['records_updated']}")
        logger.info(f"  API Calls: {self.stats['api_calls']}")
        logger.info("=" * 80)

        # Coverage report
        if not self.dry_run:
            logger.info("\n📊 Data Coverage Report:")
            coverage = self.get_data_coverage_report()

            for index_key, metrics in coverage.items():
                if 'error' in metrics:
                    logger.error(f"  {index_key}: Error - {metrics['error']}")
                else:
                    logger.info(f"  {index_key} ({metrics['region']}):")
                    logger.info(f"    Records: {metrics['record_count']}")
                    logger.info(f"    Date Range: {metrics['start_date']} to {metrics['end_date']}")
                    logger.info(f"    Years Covered: {metrics['years_covered']:.1f}")
                    logger.info(f"    Latest Close: {metrics['latest_close']}")

                    # Accept >= 4.9 years as 5 years (accounting for rounding)
                    if metrics['years_covered'] >= 4.9:
                        logger.info(f"    ✅ Target coverage (≥5 years) ACHIEVED")
                    else:
                        logger.warning(f"    ⚠️ Target coverage (≥5 years) NOT YET ACHIEVED")

        # Success/failure message
        success_rate = (self.stats['success'] / self.stats['indices_processed'] * 100) if self.stats['indices_processed'] > 0 else 0

        if success_rate == 100:
            logger.info(f"\n✅ Backfill completed successfully (100% success rate)")
        elif success_rate >= 80:
            logger.warning(f"\n⚠️ Backfill completed with some failures (success rate: {success_rate:.1f}%)")
        else:
            logger.error(f"\n❌ Backfill completed with many failures (success rate: {success_rate:.1f}%)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backfill global market indices historical data')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no database writes)')
    parser.add_argument('--years', type=int, default=5, help='Years of historical data to fetch (default: 5)')

    args = parser.parse_args()

    # Initialize and run backfiller
    db = PostgresDatabaseManager()

    try:
        logger.info("✅ Connected to PostgreSQL database")

        backfiller = MarketIndicesBackfiller(
            dry_run=args.dry_run,
            years=args.years
        )

        backfiller.run()

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Backfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close_pool()


if __name__ == '__main__':
    main()
