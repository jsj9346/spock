#!/usr/bin/env python3
"""
US Adapter Deployment Script (Week 2-3)

Deploys US market adapter with KIS API and monitoring integration.

Features:
- KIS API connection validation
- Stock ticker scanning (~3,000 tradable stocks)
- OHLCV data collection with technical indicators
- Prometheus metrics integration
- Market status checking
- Comprehensive error handling and logging

Usage:
    # Full deployment with data collection
    python3 deploy_us_adapter.py --full

    # Ticker scan only
    python3 deploy_us_adapter.py --scan-only

    # OHLCV collection for specific tickers
    python3 deploy_us_adapter.py --tickers AAPL MSFT --days 250

    # Dry run (validation only)
    python3 deploy_us_adapter.py --dry-run

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.market_adapters.us_adapter_kis import USAdapterKIS
from modules.db_manager_sqlite import SQLiteDatabaseManager
from dotenv import load_dotenv

# Prometheus instrumentation (optional, for real-time metrics)
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("prometheus_client not installed - metrics disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/us_adapter_deploy_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================================
# Prometheus Metrics (if available)
# ========================================
if PROMETHEUS_AVAILABLE:
    # Data collection metrics
    us_scan_attempts = Counter('spock_us_scan_attempts_total', 'US ticker scan attempts')
    us_scan_success = Counter('spock_us_scan_success_total', 'Successful US ticker scans')
    us_scan_tickers = Gauge('spock_us_scan_tickers_total', 'Total US tickers scanned')

    us_ohlcv_attempts = Counter('spock_us_ohlcv_attempts_total', 'US OHLCV collection attempts')
    us_ohlcv_success = Counter('spock_us_ohlcv_success_total', 'Successful US OHLCV collections')
    us_ohlcv_failed = Counter('spock_us_ohlcv_failed_total', 'Failed US OHLCV collections')

    # API metrics
    us_api_requests = Counter('spock_us_api_requests_total', 'US adapter API requests', ['endpoint'])
    us_api_errors = Counter('spock_us_api_errors_total', 'US adapter API errors', ['endpoint'])
    us_api_latency = Histogram('spock_us_api_latency_seconds', 'US adapter API latency', ['endpoint'])


class USAdapterDeployment:
    """US Market Adapter Deployment Manager"""

    def __init__(self,
                 db_path: str = '/Users/13ruce/spock/data/spock_local.db',
                 dry_run: bool = False):
        """
        Initialize US adapter deployment

        Args:
            db_path: Path to SQLite database
            dry_run: If True, validate only (no actual operations)
        """
        self.db_path = db_path
        self.dry_run = dry_run

        # Load environment variables
        load_dotenv()

        # Get KIS API credentials
        self.app_key = os.getenv('KIS_APP_KEY')
        self.app_secret = os.getenv('KIS_APP_SECRET')

        if not self.app_key or not self.app_secret:
            raise ValueError("KIS API credentials not found in .env file")

        # Initialize database and adapter
        self.db = SQLiteDatabaseManager(db_path=db_path)
        self.adapter = USAdapterKIS(
            db_manager=self.db,
            app_key=self.app_key,
            app_secret=self.app_secret
        )

        logger.info(f"🚀 US Adapter Deployment initialized")
        logger.info(f"   Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        logger.info(f"   Database: {db_path}")

    def validate_prerequisites(self) -> bool:
        """
        Validate all prerequisites before deployment

        Returns:
            True if all checks pass
        """
        logger.info("🔍 Validating prerequisites...")

        checks_passed = True

        # 1. Check database exists
        if not os.path.exists(self.db_path):
            logger.error(f"❌ Database not found: {self.db_path}")
            checks_passed = False
        else:
            logger.info(f"✅ Database exists: {self.db_path}")

        # 2. Check KIS API connection
        try:
            if self.adapter.check_connection():
                logger.info("✅ KIS API connection successful")
            else:
                logger.error("❌ KIS API connection failed")
                checks_passed = False
        except Exception as e:
            logger.error(f"❌ KIS API connection error: {e}")
            checks_passed = False

        # 3. Check market status
        try:
            market_status = self.adapter.get_market_status()
            is_open = market_status.get('is_open', False)
            logger.info(f"📊 US Market Status: {'OPEN' if is_open else 'CLOSED'}")
            if not is_open:
                next_open = market_status.get('next_open', 'Unknown')
                logger.info(f"   Next open: {next_open}")
        except Exception as e:
            logger.warning(f"⚠️ Could not get market status: {e}")

        # 4. Check database schema
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            # Check ohlcv_data has region column
            cursor.execute("PRAGMA table_info(ohlcv_data)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'region' in columns:
                logger.info("✅ Database schema has region column")
            else:
                logger.error("❌ Database schema missing region column")
                checks_passed = False

            conn.close()
        except Exception as e:
            logger.error(f"❌ Database schema check failed: {e}")
            checks_passed = False

        return checks_passed

    def scan_us_stocks(self, force_refresh: bool = False, max_count: int = None) -> int:
        """
        Scan US tradable stocks from KIS API

        Args:
            force_refresh: Skip cache and fetch fresh data
            max_count: Maximum tickers per exchange (for testing)

        Returns:
            Number of stocks scanned
        """
        logger.info("📊 Starting US stock scan...")

        if self.dry_run:
            logger.info("🔍 DRY RUN: Skipping actual scan")
            return 0

        try:
            # Increment Prometheus counter
            if PROMETHEUS_AVAILABLE:
                us_scan_attempts.inc()

            start_time = time.time()

            # Scan stocks
            stocks = self.adapter.scan_stocks(
                force_refresh=force_refresh,
                max_count=max_count
            )

            elapsed = time.time() - start_time

            # Update Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                us_scan_success.inc()
                us_scan_tickers.set(len(stocks))

            logger.info(f"✅ US stock scan complete: {len(stocks)} stocks in {elapsed:.1f}s")

            # Log exchange breakdown
            exchange_counts = {}
            for stock in stocks:
                exchange = stock.get('exchange', 'Unknown')
                exchange_counts[exchange] = exchange_counts.get(exchange, 0) + 1

            for exchange, count in sorted(exchange_counts.items()):
                logger.info(f"   {exchange}: {count} stocks")

            return len(stocks)

        except Exception as e:
            logger.error(f"❌ US stock scan failed: {e}")
            return 0

    def collect_ohlcv_data(self,
                          tickers: List[str] = None,
                          days: int = 250,
                          batch_size: int = 100) -> Dict:
        """
        Collect OHLCV data for US stocks

        Args:
            tickers: List of tickers (None = all active US stocks)
            days: Historical days to collect
            batch_size: Number of tickers to process per batch

        Returns:
            Dictionary with collection statistics
        """
        logger.info(f"📈 Starting OHLCV data collection ({days} days)...")

        if self.dry_run:
            logger.info("🔍 DRY RUN: Skipping actual collection")
            return {'success': 0, 'failed': 0, 'total': 0}

        # Get ticker list if not provided
        if tickers is None:
            db_tickers = self.db.get_tickers(
                region='US',
                asset_type='STOCK',
                is_active=True
            )
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ No US tickers to collect")
            return {'success': 0, 'failed': 0, 'total': 0}

        logger.info(f"📊 Collecting OHLCV for {len(tickers)} tickers...")

        success_count = 0
        failed_count = 0

        # Process in batches
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(tickers) + batch_size - 1) // batch_size

            logger.info(f"📦 Batch {batch_num}/{total_batches}: {len(batch)} tickers")

            for ticker in batch:
                try:
                    # Increment Prometheus counter
                    if PROMETHEUS_AVAILABLE:
                        us_ohlcv_attempts.inc()

                    # Determine exchange code (default to NASD for NASDAQ)
                    # Most US stocks are on NASDAQ, NYSE will be auto-detected by KIS API
                    exchange_code = 'NASD'  # Default

                    # Fetch OHLCV
                    start_time = time.time()

                    ohlcv_df = self.adapter.kis_api.get_ohlcv(
                        ticker=ticker,
                        exchange_code=exchange_code,
                        days=days
                    )

                    if PROMETHEUS_AVAILABLE:
                        us_api_latency.labels(endpoint='get_ohlcv').observe(time.time() - start_time)

                    if ohlcv_df.empty:
                        logger.warning(f"⚠️ [{ticker}] No OHLCV data")
                        failed_count += 1
                        if PROMETHEUS_AVAILABLE:
                            us_ohlcv_failed.inc()
                        continue

                    # Calculate technical indicators
                    ohlcv_df = self.adapter._calculate_technical_indicators(ohlcv_df)

                    # Save to database using base adapter method
                    inserted = self.adapter._save_ohlcv_to_db(
                        ticker=ticker,
                        ohlcv_df=ohlcv_df,
                        period_type='DAILY'
                    )

                    success_count += 1
                    if PROMETHEUS_AVAILABLE:
                        us_ohlcv_success.inc()

                    logger.info(f"✅ [{ticker}] {len(ohlcv_df)} days saved")

                except Exception as e:
                    logger.error(f"❌ [{ticker}] Collection failed: {e}")
                    failed_count += 1
                    if PROMETHEUS_AVAILABLE:
                        us_ohlcv_failed.inc()
                    continue

                # Rate limiting: 20 req/sec = 50ms delay
                time.sleep(0.05)

            # Batch complete
            logger.info(f"✅ Batch {batch_num} complete: {success_count} success, {failed_count} failed")

        # Final statistics
        stats = {
            'success': success_count,
            'failed': failed_count,
            'total': len(tickers),
            'success_rate': (success_count / len(tickers) * 100) if tickers else 0
        }

        logger.info(f"✅ OHLCV collection complete:")
        logger.info(f"   Success: {success_count}/{len(tickers)} ({stats['success_rate']:.1f}%)")
        logger.info(f"   Failed: {failed_count}/{len(tickers)}")

        return stats

    def validate_data_quality(self) -> Dict:
        """
        Validate collected data quality

        Returns:
            Dictionary with validation results
        """
        logger.info("🔍 Validating data quality...")

        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            # 1. Count US OHLCV rows
            cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region = 'US'")
            total_rows = cursor.fetchone()[0]

            # 2. Check for NULL regions (should be 0)
            cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL")
            null_regions = cursor.fetchone()[0]

            # 3. Check for cross-region contamination
            cursor.execute("""
                SELECT COUNT(DISTINCT ticker)
                FROM (
                    SELECT ticker, COUNT(DISTINCT region) as region_count
                    FROM ohlcv_data
                    WHERE ticker IN (SELECT ticker FROM tickers WHERE region = 'US')
                    GROUP BY ticker
                    HAVING region_count > 1
                )
            """)
            contamination = cursor.fetchone()[0]

            # 4. Unique US tickers
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE region = 'US'")
            unique_tickers = cursor.fetchone()[0]

            # 5. Date range
            cursor.execute("""
                SELECT MIN(date), MAX(date)
                FROM ohlcv_data
                WHERE region = 'US'
            """)
            date_range = cursor.fetchone()
            min_date, max_date = date_range if date_range else (None, None)

            conn.close()

            # Validation results
            results = {
                'total_rows': total_rows,
                'null_regions': null_regions,
                'contamination': contamination,
                'unique_tickers': unique_tickers,
                'date_range': (min_date, max_date),
                'passed': null_regions == 0 and contamination == 0
            }

            # Log results
            logger.info(f"📊 Data Quality Validation:")
            logger.info(f"   Total US OHLCV rows: {total_rows:,}")
            logger.info(f"   Unique tickers: {unique_tickers}")
            logger.info(f"   NULL regions: {null_regions} {'✅' if null_regions == 0 else '❌'}")
            logger.info(f"   Cross-region contamination: {contamination} {'✅' if contamination == 0 else '❌'}")
            if min_date and max_date:
                logger.info(f"   Date range: {min_date} to {max_date}")

            if results['passed']:
                logger.info(f"✅ Data quality validation PASSED")
            else:
                logger.error(f"❌ Data quality validation FAILED")

            return results

        except Exception as e:
            logger.error(f"❌ Data quality validation error: {e}")
            return {'passed': False, 'error': str(e)}

    def run_full_deployment(self,
                           force_scan: bool = False,
                           scan_only: bool = False,
                           days: int = 250) -> bool:
        """
        Run complete US adapter deployment

        Args:
            force_scan: Force ticker refresh
            scan_only: Only scan tickers (skip OHLCV collection)
            days: Historical days to collect

        Returns:
            True if deployment successful
        """
        logger.info("=" * 70)
        logger.info("🚀 US ADAPTER DEPLOYMENT - STARTING")
        logger.info("=" * 70)

        start_time = time.time()

        # Step 1: Prerequisites validation
        logger.info("\n📋 Step 1: Prerequisites Validation")
        if not self.validate_prerequisites():
            logger.error("❌ Prerequisites validation failed")
            return False

        # Step 2: Stock ticker scan
        logger.info("\n📋 Step 2: US Stock Ticker Scan")
        ticker_count = self.scan_us_stocks(force_refresh=force_scan)

        if ticker_count == 0:
            logger.error("❌ No tickers scanned")
            return False

        if scan_only:
            logger.info("\n✅ Scan-only mode: Deployment complete")
            elapsed = time.time() - start_time
            logger.info(f"⏱️  Total time: {elapsed:.1f}s")
            return True

        # Step 3: OHLCV data collection
        logger.info(f"\n📋 Step 3: OHLCV Data Collection ({days} days)")
        stats = self.collect_ohlcv_data(days=days)

        if stats['success'] == 0:
            logger.error("❌ OHLCV collection failed (no successful collections)")
            return False

        # Step 4: Data quality validation
        logger.info("\n📋 Step 4: Data Quality Validation")
        validation = self.validate_data_quality()

        if not validation.get('passed', False):
            logger.error("❌ Data quality validation failed")
            return False

        # Deployment complete
        elapsed = time.time() - start_time

        logger.info("\n" + "=" * 70)
        logger.info("✅ US ADAPTER DEPLOYMENT - COMPLETE")
        logger.info("=" * 70)
        logger.info(f"⏱️  Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        logger.info(f"📊 Tickers scanned: {ticker_count}")
        logger.info(f"📈 OHLCV collected: {stats['success']}/{stats['total']} ({stats['success_rate']:.1f}%)")
        logger.info(f"✅ Data quality: PASSED")

        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Deploy US Market Adapter with KIS API'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full deployment (scan + OHLCV collection)'
    )
    parser.add_argument(
        '--scan-only',
        action='store_true',
        help='Scan tickers only (skip OHLCV collection)'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Specific tickers to collect (e.g., AAPL MSFT)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=250,
        help='Historical days to collect (default: 250)'
    )
    parser.add_argument(
        '--force-scan',
        action='store_true',
        help='Force ticker refresh (skip cache)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate only (no actual operations)'
    )
    parser.add_argument(
        '--db-path',
        default='/Users/13ruce/spock/data/spock_local.db',
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--metrics-port',
        type=int,
        default=8002,
        help='Prometheus metrics port (default: 8002 for US adapter)'
    )

    args = parser.parse_args()

    # Start Prometheus metrics server if available
    if PROMETHEUS_AVAILABLE and not args.dry_run:
        try:
            start_http_server(args.metrics_port)
            logger.info(f"📊 Prometheus metrics: http://localhost:{args.metrics_port}/metrics")
        except Exception as e:
            logger.warning(f"⚠️ Could not start metrics server: {e}")

    # Initialize deployment
    try:
        deployment = USAdapterDeployment(
            db_path=args.db_path,
            dry_run=args.dry_run
        )
    except Exception as e:
        logger.error(f"❌ Deployment initialization failed: {e}")
        sys.exit(1)

    # Execute deployment
    success = False

    try:
        if args.full:
            success = deployment.run_full_deployment(
                force_scan=args.force_scan,
                scan_only=False,
                days=args.days
            )
        elif args.scan_only:
            success = deployment.run_full_deployment(
                force_scan=args.force_scan,
                scan_only=True
            )
        elif args.tickers:
            # Specific tickers collection
            logger.info(f"📊 Collecting OHLCV for {len(args.tickers)} specific tickers...")
            stats = deployment.collect_ohlcv_data(
                tickers=args.tickers,
                days=args.days
            )
            success = stats['success'] > 0
        else:
            # Default: validate prerequisites only
            success = deployment.validate_prerequisites()

    except KeyboardInterrupt:
        logger.info("\n⚠️ Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Deployment failed: {e}", exc_info=True)
        sys.exit(1)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
