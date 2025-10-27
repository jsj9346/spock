#!/usr/bin/env python3
"""
FX Data Collector - Phase 1-C

Purpose:
- Collect daily FX rates from Bank of Korea (BOK) Open API
- Calculate USD-normalized rates for cross-market comparison
- Store in fx_valuation_signals table (PostgreSQL + TimescaleDB)
- Support incremental updates and error recovery

Features:
- 5 currency pairs: USD, HKD, CNY, JPY, VND (to KRW)
- USD-normalized rates: usd_rate = krw_rate / usd_krw_rate
- Data quality tracking: GOOD/PARTIAL/POOR/MISSING
- Prometheus metrics integration
- Dual-write to PostgreSQL + SQLite (backward compatibility)

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.exchange_rate_manager import ExchangeRateManager
from modules.db_manager_postgres import PostgresDatabaseManager

# Optional: Prometheus client (graceful degradation if not available)
try:
    from prometheus_client import Counter, Histogram, Gauge
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

logger = logging.getLogger(__name__)


class FXDataCollector:
    """
    FX data collector using BOK API with PostgreSQL persistence

    Architecture:
    1. Fetch FX rates from BOK API (via ExchangeRateManager)
    2. Calculate USD-normalized rates for cross-market comparison
    3. Insert/Update fx_valuation_signals table (PostgreSQL)
    4. Backward compatibility: Dual-write to SQLite exchange_rate_history
    5. Track data quality and export Prometheus metrics

    Supported Currencies:
    - USD: US Dollar (base for normalization)
    - HKD: Hong Kong Dollar
    - CNY: Chinese Yuan
    - JPY: Japanese Yen
    - VND: Vietnamese Dong

    Usage:
        >>> collector = FXDataCollector()
        >>> results = collector.collect_today()
        >>> print(f"Collected {results['success']} currencies")
    """

    # Supported currencies
    SUPPORTED_CURRENCIES = ['USD', 'HKD', 'CNY', 'JPY', 'VND']

    # Currency → Region mapping
    CURRENCY_REGION_MAP = {
        'USD': 'US',
        'HKD': 'HK',
        'CNY': 'CN',
        'JPY': 'JP',
        'VND': 'VN'
    }

    # Prometheus metrics (created only if library available)
    if HAS_PROMETHEUS:
        # Collection performance
        collection_duration = Histogram(
            'fx_collection_duration_seconds',
            'FX data collection duration',
            ['currency']
        )

        collection_success = Counter(
            'fx_collection_success_total',
            'Successful FX collections',
            ['currency']
        )

        collection_errors = Counter(
            'fx_collection_errors_total',
            'FX collection errors',
            ['currency', 'error_type']
        )

        # Data quality
        rate_change_daily = Gauge(
            'fx_rate_change_daily_percent',
            'Daily FX rate change percentage',
            ['currency']
        )

        data_quality_score = Gauge(
            'fx_data_quality_score',
            'FX data quality score (0.0-1.0)',
            ['currency']
        )

    def __init__(self,
                 bok_api_key: Optional[str] = None,
                 sqlite_db_path: str = 'data/spock_local.db'):
        """
        Initialize FX Data Collector

        Args:
            bok_api_key: BOK Open API key (optional, defaults to 'sample' mode)
            sqlite_db_path: Path to SQLite database (for backward compatibility)
        """
        # Initialize database managers
        self.db_postgres = PostgresDatabaseManager()
        self.sqlite_db_path = sqlite_db_path

        # Initialize exchange rate manager
        self.exchange_rate_manager = ExchangeRateManager(
            db_manager=None,  # Standalone mode (we handle persistence)
            bok_api_key=bok_api_key
        )

        # Statistics tracking
        self.stats = {
            'currencies_attempted': 0,
            'currencies_success': 0,
            'currencies_failed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'errors': []
        }

        logger.info("💱 FX Data Collector initialized")
        logger.info(f"   Supported currencies: {', '.join(self.SUPPORTED_CURRENCIES)}")
        logger.info(f"   BOK API: {'Enabled' if bok_api_key else 'Sample mode (10K req/day)'}")
        logger.info(f"   Prometheus: {'✅ Enabled' if HAS_PROMETHEUS else '⚠️ Disabled'}")

    def collect_today(self,
                     currencies: Optional[List[str]] = None,
                     force_refresh: bool = False) -> Dict:
        """
        Collect FX rates for today

        Args:
            currencies: List of currency codes (defaults to all supported)
            force_refresh: Force API calls (ignore cache)

        Returns:
            Dictionary with collection results:
            {
                'date': '2025-10-24',
                'success': 4,
                'failed': 1,
                'records_inserted': 2,
                'records_updated': 2,
                'errors': [...]
            }
        """
        currencies = currencies or self.SUPPORTED_CURRENCIES
        collection_date = date.today()

        logger.info(f"🔄 Starting FX collection for {collection_date}")
        logger.info(f"   Currencies: {', '.join(currencies)}")

        # Reset statistics
        self.stats = {
            'currencies_attempted': 0,
            'currencies_success': 0,
            'currencies_failed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'errors': []
        }

        # Collect each currency
        for currency in currencies:
            if currency not in self.SUPPORTED_CURRENCIES:
                logger.warning(f"⚠️ [{currency}] Unsupported currency, skipping")
                continue

            self.stats['currencies_attempted'] += 1

            try:
                # Collect single currency
                success = self._collect_currency(
                    currency=currency,
                    collection_date=collection_date,
                    force_refresh=force_refresh
                )

                if success:
                    self.stats['currencies_success'] += 1

                    # Export Prometheus metrics
                    if HAS_PROMETHEUS:
                        self.collection_success.labels(currency=currency).inc()
                else:
                    self.stats['currencies_failed'] += 1

            except Exception as e:
                self.stats['currencies_failed'] += 1
                error_msg = f"[{currency}] Collection error: {e}"
                self.stats['errors'].append(error_msg)
                logger.error(f"❌ {error_msg}")

                # Export Prometheus error metric
                if HAS_PROMETHEUS:
                    self.collection_errors.labels(
                        currency=currency,
                        error_type=type(e).__name__
                    ).inc()

        # Summary
        logger.info("=" * 70)
        logger.info(f"✅ FX Collection Complete - {collection_date}")
        logger.info(f"   Success: {self.stats['currencies_success']}/{self.stats['currencies_attempted']}")
        logger.info(f"   Failed: {self.stats['currencies_failed']}")
        logger.info(f"   Inserted: {self.stats['records_inserted']}")
        logger.info(f"   Updated: {self.stats['records_updated']}")

        if self.stats['errors']:
            logger.warning(f"⚠️ Errors encountered: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                logger.warning(f"   - {error}")

        logger.info("=" * 70)

        return {
            'date': collection_date.isoformat(),
            'success': self.stats['currencies_success'],
            'failed': self.stats['currencies_failed'],
            'records_inserted': self.stats['records_inserted'],
            'records_updated': self.stats['records_updated'],
            'errors': self.stats['errors']
        }

    def _collect_currency(self,
                         currency: str,
                         collection_date: date,
                         force_refresh: bool = False) -> bool:
        """
        Collect FX rate for a single currency

        Args:
            currency: Currency code (USD, HKD, CNY, JPY, VND)
            collection_date: Date of collection
            force_refresh: Force API call (ignore cache)

        Returns:
            True if successful, False otherwise
        """
        start_time = datetime.now()

        try:
            # Step 1: Fetch KRW exchange rate from BOK API
            krw_rate = self.exchange_rate_manager.get_rate(
                currency=currency,
                force_refresh=force_refresh
            )

            if krw_rate is None:
                logger.error(f"❌ [{currency}] Failed to fetch KRW rate")
                return False

            # Step 2: Calculate USD-normalized rate
            usd_rate, data_quality = self._calculate_usd_rate(currency, krw_rate)

            # Step 3: Calculate daily rate change (if previous data exists)
            rate_change_pct = self._calculate_daily_change(currency, usd_rate, collection_date)

            # Step 4: Insert/Update PostgreSQL (fx_valuation_signals)
            postgres_success = self._save_to_postgres(
                currency=currency,
                collection_date=collection_date,
                krw_rate=krw_rate,
                usd_rate=usd_rate,
                data_quality=data_quality
            )

            # Step 5: Dual-write to SQLite (backward compatibility)
            sqlite_success = self._save_to_sqlite(
                currency=currency,
                collection_date=collection_date,
                krw_rate=krw_rate
            )

            # Step 6: Export Prometheus metrics
            if HAS_PROMETHEUS and rate_change_pct is not None:
                self.rate_change_daily.labels(currency=currency).set(rate_change_pct)
                self.data_quality_score.labels(currency=currency).set(
                    1.0 if data_quality == 'GOOD' else 0.7 if data_quality == 'PARTIAL' else 0.3
                )

            # Success logging
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"✅ [{currency}] {krw_rate:.4f} KRW | "
                f"USD-norm: {usd_rate:.6f} | "
                f"Change: {rate_change_pct:+.2f}% | "
                f"Quality: {data_quality} | "
                f"Duration: {duration:.2f}s"
            )

            # Export duration metric
            if HAS_PROMETHEUS:
                self.collection_duration.labels(currency=currency).observe(duration)

            return postgres_success and sqlite_success

        except Exception as e:
            logger.error(f"❌ [{currency}] Unexpected error: {e}")
            return False

    def _calculate_usd_rate(self, currency: str, krw_rate: float) -> Tuple[float, str]:
        """
        Calculate USD-normalized exchange rate

        Formula:
            usd_rate = krw_rate / usd_krw_rate

        Example:
            HKD/KRW = 170.0 KRW
            USD/KRW = 1,300.0 KRW
            HKD/USD = 170.0 / 1,300.0 = 0.130769 USD

        Args:
            currency: Currency code
            krw_rate: Exchange rate to KRW

        Returns:
            Tuple of (usd_rate, data_quality)
            - usd_rate: USD-normalized rate
            - data_quality: 'GOOD', 'PARTIAL', 'POOR', or 'MISSING'
        """
        # USD is base currency (rate = 1.0)
        if currency == 'USD':
            return 1.000000, 'GOOD'

        # Get USD/KRW rate
        try:
            usd_krw_rate = self.exchange_rate_manager.get_rate('USD')

            if usd_krw_rate is None or usd_krw_rate <= 0:
                logger.warning(f"⚠️ [{currency}] Invalid USD/KRW rate, using default")
                usd_krw_rate = ExchangeRateManager.DEFAULT_RATES['USD']
                data_quality = 'PARTIAL'
            else:
                data_quality = 'GOOD'

            # Calculate USD-normalized rate
            usd_rate = krw_rate / usd_krw_rate

            return usd_rate, data_quality

        except Exception as e:
            logger.error(f"❌ [{currency}] USD rate calculation error: {e}")
            # Fallback: Use default USD rate
            usd_krw_rate = ExchangeRateManager.DEFAULT_RATES['USD']
            usd_rate = krw_rate / usd_krw_rate
            return usd_rate, 'POOR'

    def _calculate_daily_change(self,
                               currency: str,
                               current_rate: float,
                               current_date: date) -> Optional[float]:
        """
        Calculate daily rate change percentage

        Args:
            currency: Currency code
            current_rate: Current USD-normalized rate
            current_date: Current date

        Returns:
            Daily change percentage (e.g., 1.5 for +1.5% increase)
            None if no previous data available
        """
        try:
            # Get previous day's rate from PostgreSQL
            query = """
                SELECT usd_rate
                FROM fx_valuation_signals
                WHERE currency = %s
                  AND region = %s
                  AND date < %s
                ORDER BY date DESC
                LIMIT 1
            """

            region = self.CURRENCY_REGION_MAP.get(currency, 'US')

            result = self.db_postgres.execute_query(
                query,
                (currency, region, current_date)
            )

            if result and len(result) > 0:
                previous_rate = float(result[0][0])

                # Calculate percentage change
                change_pct = ((current_rate - previous_rate) / previous_rate) * 100

                return change_pct

            return None  # No previous data

        except Exception as e:
            logger.debug(f"ℹ️ [{currency}] Daily change calculation error: {e}")
            return None

    def _save_to_postgres(self,
                         currency: str,
                         collection_date: date,
                         krw_rate: float,
                         usd_rate: float,
                         data_quality: str) -> bool:
        """
        Save FX rate to PostgreSQL fx_valuation_signals table

        Upsert logic:
        - If record exists (currency, region, date): UPDATE
        - If record doesn't exist: INSERT

        Args:
            currency: Currency code
            collection_date: Date of collection
            krw_rate: KRW exchange rate
            usd_rate: USD-normalized rate
            data_quality: Data quality indicator

        Returns:
            True if successful, False otherwise
        """
        try:
            region = self.CURRENCY_REGION_MAP.get(currency, 'US')

            # Upsert query (INSERT ... ON CONFLICT ... DO UPDATE)
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

            result = self.db_postgres.execute_query(
                query,
                (currency, region, collection_date, usd_rate, data_quality)
            )

            if result and len(result) > 0:
                record_id, inserted = result[0]

                if inserted:
                    self.stats['records_inserted'] += 1
                    logger.debug(f"✅ [{currency}] Inserted to PostgreSQL (ID: {record_id})")
                else:
                    self.stats['records_updated'] += 1
                    logger.debug(f"✅ [{currency}] Updated PostgreSQL (ID: {record_id})")

                return True

            logger.error(f"❌ [{currency}] PostgreSQL upsert returned no result")
            return False

        except Exception as e:
            logger.error(f"❌ [{currency}] PostgreSQL save error: {e}")
            return False

    def _save_to_sqlite(self,
                       currency: str,
                       collection_date: date,
                       krw_rate: float) -> bool:
        """
        Save FX rate to SQLite exchange_rate_history table (backward compatibility)

        Args:
            currency: Currency code
            collection_date: Date of collection
            krw_rate: KRW exchange rate

        Returns:
            True if successful, False otherwise
        """
        try:
            import sqlite3

            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()

            # Insert or replace (unique constraint on currency + rate_date)
            insert_query = """
                INSERT OR REPLACE INTO exchange_rate_history
                (currency, rate, timestamp, rate_date, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """

            cursor.execute(insert_query, (
                currency,
                krw_rate,
                datetime.now().isoformat(),
                collection_date.strftime('%Y-%m-%d'),
                'BOK_API',
                datetime.now().isoformat()
            ))

            conn.commit()
            conn.close()

            logger.debug(f"✅ [{currency}] Saved to SQLite (backward compatibility)")

            return True

        except Exception as e:
            logger.warning(f"⚠️ [{currency}] SQLite save error (non-critical): {e}")
            # Non-critical - SQLite is for backward compatibility only
            return True  # Don't fail collection on SQLite error

    def get_latest_rates(self) -> Dict[str, float]:
        """
        Get latest USD-normalized rates for all currencies

        Returns:
            Dictionary of {currency: usd_rate}

        Example:
            >>> collector.get_latest_rates()
            {'USD': 1.0, 'HKD': 0.130769, 'CNY': 0.138462, ...}
        """
        query = """
            SELECT currency, usd_rate
            FROM mv_latest_fx_signals
            WHERE data_quality IN ('GOOD', 'PARTIAL')
            ORDER BY currency
        """

        try:
            results = self.db_postgres.execute_query(query)

            rates = {}
            for row in results:
                currency = row[0]
                usd_rate = float(row[1])
                rates[currency] = usd_rate

            return rates

        except Exception as e:
            logger.error(f"❌ Failed to get latest rates: {e}")
            return {}

    def refresh_materialized_view(self) -> bool:
        """
        Refresh mv_latest_fx_signals materialized view

        Should be called after bulk updates or backfills

        Returns:
            True if successful, False otherwise
        """
        try:
            query = "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_fx_signals"

            self.db_postgres.execute_query(query)

            logger.info("✅ Materialized view mv_latest_fx_signals refreshed")

            return True

        except Exception as e:
            logger.error(f"❌ Materialized view refresh error: {e}")
            return False


if __name__ == '__main__':
    """
    Standalone execution for manual testing

    Usage:
        python3 modules/fx_data_collector.py
    """
    import argparse
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'logs/fx_collection_{date.today().strftime("%Y%m%d")}.log')
        ]
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description='FX Data Collector')
    parser.add_argument('--currencies', type=str, help='Comma-separated currency codes (default: all)')
    parser.add_argument('--force-refresh', action='store_true', help='Force API calls (ignore cache)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no database writes)')

    args = parser.parse_args()

    # Parse currencies
    currencies = None
    if args.currencies:
        currencies = [c.strip().upper() for c in args.currencies.split(',')]

    # Initialize collector
    bok_api_key = os.getenv('BOK_API_KEY')  # Optional
    collector = FXDataCollector(bok_api_key=bok_api_key)

    # Dry run mode
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No database writes will be performed")
        logger.info(f"   Currencies: {', '.join(currencies or collector.SUPPORTED_CURRENCIES)}")
        logger.info("   Exiting...")
        sys.exit(0)

    # Run collection
    logger.info("=" * 70)
    logger.info("FX DATA COLLECTION - Standalone Execution")
    logger.info("=" * 70)

    results = collector.collect_today(
        currencies=currencies,
        force_refresh=args.force_refresh
    )

    # Exit code
    exit_code = 0 if results['failed'] == 0 else 1
    sys.exit(exit_code)
