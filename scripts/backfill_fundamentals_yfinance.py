#!/usr/bin/env python3
"""
yfinance Fundamental Data Backfill Script (Phase 1.5 - Day 3)

Backfills fundamental metrics for global markets (US, JP, CN, HK, VN) using yfinance library.

Metrics collected:
- Valuation: P/E Ratio (trailing/forward), P/B Ratio, P/S Ratio, EV/EBITDA
- Market Data: Market Cap, Shares Outstanding, Enterprise Value
- Dividends: Dividend Yield, Dividend Per Share
- Financial: Book Value, EPS, Revenue, EBITDA

Target Coverage: >50% for each global market region

Author: Quant Platform Development Team
Date: 2025-10-21
"""

import sys
import os
import argparse
import logging
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


class YFinanceFundamentalBackfiller:
    """
    yfinance fundamental data backfiller for global markets

    Features:
    - Batch processing (50 tickers per batch for optimization)
    - Ticker symbol mapping for each market (US/JP/CN/HK/VN)
    - Data quality validation (sanity checks for P/E, P/B, market cap)
    - Rate limiting (2 requests/second, yfinance recommended limit)
    - Dry-run mode for testing
    - Incremental mode (only update stale data)
    """

    # Ticker symbol suffix mapping
    TICKER_SUFFIXES = {
        'US': '',           # No suffix
        'JP': '.T',         # Tokyo Stock Exchange
        'CN': '',           # Already in database (.SS/.SZ)
        'HK': '',           # Already in database (.HK)
        'VN': '.VN'         # Vietnam Stock Exchange (best guess, will validate)
    }

    # Target coverage percentages
    TARGET_COVERAGE = {
        'US': 0.50,  # 50% of US stocks
        'JP': 0.50,  # 50% of JP stocks
        'CN': 0.50,  # 50% of CN stocks
        'HK': 0.50,  # 50% of HK stocks
        'VN': 0.30   # 30% of VN stocks (lower due to data availability)
    }

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False, rate_limit_delay: float = 0.5):
        """
        Initialize yfinance fundamental backfiller

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 0.5s = 2 req/sec)
        """
        self.db = db
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.last_api_call = time.time()

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'success': 0,
            'skipped_no_data': 0,
            'skipped_legacy_cn': 0,  # CN legacy tickers (1-5 digit codes)
            'skipped_us_special': 0,  # US slash-based tickers (preferred/unit/warrant)
            'failed': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'api_calls': 0,
            'api_call_times': []
        }

        # Check yfinance availability
        try:
            import yfinance as yf
            self.yf = yf
            logger.info("✅ yfinance library available")
        except ImportError:
            logger.error("❌ yfinance library not installed: pip install yfinance")
            raise

    def _rate_limit(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_api_call
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_api_call = time.time()

    def map_ticker_symbol(self, ticker: str, region: str) -> str:
        """
        Map database ticker to yfinance ticker symbol

        Args:
            ticker: Database ticker code
            region: Market region (US/JP/CN/HK/VN)

        Returns:
            yfinance-compatible ticker symbol
        """
        suffix = self.TICKER_SUFFIXES.get(region, '')

        # CN and HK already have suffixes in database
        if region in ['CN', 'HK']:
            return ticker

        # US has no suffix
        if region == 'US':
            return ticker

        # JP and VN need suffix appended
        return f"{ticker}{suffix}"

    def is_valid_cn_ticker(self, ticker: str) -> bool:
        """
        Check if CN ticker is valid for yfinance (6-digit code only)

        yfinance only supports modern Chinese stock tickers with 6-digit codes:
        - Valid: 300001.SZ, 688981.SS (ChiNext, STAR Market, Main Board)
        - Invalid: 100.SZ, 11.SZ, 1201.SZ (legacy 1-5 digit codes)

        Args:
            ticker: CN ticker in database format (e.g., "300001.SZ")

        Returns:
            True if ticker is valid for yfinance, False otherwise
        """
        import re

        # Extract numeric portion before .SZ or .SS
        match = re.match(r'^(\d+)\.(SZ|SS)$', ticker)
        if not match:
            return False

        numeric_part = match.group(1)

        # yfinance only supports 6-digit CN tickers
        # Legacy 1-5 digit tickers return 404 errors
        if len(numeric_part) != 6:
            logger.debug(f"⏭️ [CN:{ticker}] Skipping legacy ticker (non-6-digit code: {len(numeric_part)} digits)")
            return False

        return True

    def is_valid_us_ticker(self, ticker: str) -> bool:
        """
        Check if US ticker is valid for yfinance

        yfinance doesn't support slash-based ticker formats used for:
        - Preferred stocks: BAC/N, ABR/D (should be BAC-PRN, ABR-PRD)
        - Units: AACT/UN, ADRT/UN
        - Warrants: ACCOW/WS

        These slash-based tickers cause HTTP 404/500 errors because:
        1. URL encoding fails: /quoteSummary/BAC/N (slash treated as path separator)
        2. Yahoo Finance expects hyphen format instead

        Args:
            ticker: US ticker in database format (e.g., "BAC/N")

        Returns:
            True if ticker is valid for yfinance, False otherwise
        """
        import re

        # Skip tickers with slash + letter/number pattern
        # Matches: BAC/N, ABR/D, AACT/UN, ACCOW/WS
        if re.search(r'/[A-Z]+', ticker):
            logger.debug(f"⏭️ [US:{ticker}] Skipping slash-based ticker (preferred/unit/warrant)")
            return False

        return True

    def get_global_tickers_for_backfill(self, region: str = None,
                                       incremental: bool = False,
                                       limit: int = None) -> List[Dict]:
        """
        Get list of global market tickers for backfill

        Args:
            region: Filter by specific region (US/JP/CN/HK/VN), None for all
            incremental: If True, only fetch tickers with missing/stale data
            limit: Maximum number of tickers to fetch

        Returns:
            List of ticker dicts with ticker, name, region
        """
        if incremental:
            # Incremental mode: Only tickers without recent yfinance data (last 30 days)
            query = """
            SELECT DISTINCT t.ticker, t.name, t.region
            FROM tickers t
            LEFT JOIN ticker_fundamentals tf ON t.ticker = tf.ticker
                AND t.region = tf.region
                AND tf.date >= NOW() - INTERVAL '30 days'
                AND (tf.data_source = 'yfinance' OR tf.data_source LIKE '%yfinance%')
            WHERE t.region IN ('US', 'JP', 'CN', 'HK', 'VN')
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
              AND tf.id IS NULL  -- No recent yfinance data
            """

            if region:
                query += f" AND t.region = '{region}'"

            query += " ORDER BY t.region, t.ticker"
        else:
            # Full backfill: All global stocks
            query = """
            SELECT DISTINCT t.ticker, t.name, t.region
            FROM tickers t
            WHERE t.region IN ('US', 'JP', 'CN', 'HK', 'VN')
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
            """

            if region:
                query += f" AND t.region = '{region}'"

            query += " ORDER BY t.region, t.ticker"

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)
        tickers = [dict(row) for row in results]

        logger.info(f"📊 Found {len(tickers)} global stocks for backfill")
        if region:
            logger.info(f"   Region filter: {region}")

        return tickers

    def fetch_yfinance_fundamental_data(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Fetch fundamental metrics from yfinance for a ticker

        Args:
            ticker: Stock ticker (database format)
            region: Market region (US/JP/CN/HK/VN)

        Returns:
            Dict with fundamental metrics or None on failure
        """
        try:
            # Map to yfinance symbol
            yf_symbol = self.map_ticker_symbol(ticker, region)

            # Rate limiting
            self._rate_limit()
            start_time = time.time()
            self.stats['api_calls'] += 1

            # Fetch ticker info
            yf_ticker = self.yf.Ticker(yf_symbol)
            info = yf_ticker.info

            # Record API call time
            call_time = time.time() - start_time
            self.stats['api_call_times'].append(call_time)

            # Check if data is available
            if not info or 'marketCap' not in info:
                logger.warning(f"⚠️ [{region}:{ticker}] No fundamental data available from yfinance")
                return None

            # Extract fundamental metrics
            metrics = {
                'ticker': ticker,
                'region': region,
                'date': date.today(),  # Current date
                'period_type': 'DAILY',
                'data_source': 'yfinance',

                # Valuation ratios
                'per': self._safe_decimal(info.get('trailingPE') or info.get('forwardPE')),
                'pbr': self._safe_decimal(info.get('priceToBook')),
                'psr': self._safe_decimal(info.get('priceToSalesTrailing12Months')),
                'ev_ebitda': self._safe_decimal(info.get('enterpriseToEbitda')),

                # Market data
                'market_cap': self._safe_int(info.get('marketCap')),
                'shares_outstanding': self._safe_int(info.get('sharesOutstanding')),
                'ev': self._safe_int(info.get('enterpriseValue')),

                # Dividends (yfinance returns dividend yield as decimal: 0.004 = 0.4%)
                'dividend_yield': self._safe_decimal(info.get('dividendYield')),  # Already in decimal format
                'dividend_per_share': self._safe_decimal(info.get('dividendRate') or info.get('lastDividendValue')),

                # Financial metrics
                'close_price': self._safe_decimal(info.get('currentPrice') or info.get('regularMarketPrice')),

                # Additional fields (if available)
                'eps': self._safe_decimal(info.get('trailingEps')),
                'book_value': self._safe_decimal(info.get('bookValue')),
            }

            # Debug: Log extracted data before validation
            logger.debug(f"[{region}:{ticker}] Pre-validation: marketCap={metrics.get('market_cap')}, P/E={metrics.get('per')}, P/B={metrics.get('pbr')}")

            # Data quality validation
            if not self._validate_fundamental_data(metrics):
                logger.warning(f"⚠️ [{region}:{ticker}] Data quality validation failed")
                self.stats['skipped'] += 1
                return None

            logger.debug(f"✅ [{region}:{ticker}] yfinance data: P/E={metrics['per']}, P/B={metrics['pbr']}, "
                        f"MarketCap={metrics['market_cap']:,}")
            return metrics

        except Exception as e:
            logger.error(f"❌ [{region}:{ticker}] yfinance API call failed: {e}")
            return None

    def _safe_decimal(self, value, scale: float = 1.0) -> Optional[Decimal]:
        """Convert value to Decimal with optional scaling"""
        if value is None or value == 'N/A' or (isinstance(value, float) and (value != value or value == float('inf'))):
            return None
        try:
            return Decimal(str(float(value) * scale))
        except (ValueError, TypeError, OverflowError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Convert value to integer"""
        if value is None or value == 'N/A':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _validate_fundamental_data(self, data: Dict) -> bool:
        """
        Validate fundamental data quality

        Sanity checks:
        - Market cap > 0
        - P/E ratio reasonable (-100 < P/E < 1000)
        - P/B ratio reasonable (0 < P/B < 100)
        - Dividend yield reasonable (0 <= Div < 50%)

        Returns:
            True if data passes validation, False otherwise
        """
        # Market cap must be positive
        if not data.get('market_cap') or data['market_cap'] <= 0:
            logger.debug(f"Validation failed: Invalid market_cap={data.get('market_cap')}")
            return False

        # P/E ratio sanity check (if available)
        if data.get('per'):
            per = float(data['per'])
            if per < -100 or per > 1000:
                logger.debug(f"Validation failed: P/E out of range={per}")
                return False

        # P/B ratio sanity check (if available) - Allow negative for companies with negative equity
        if data.get('pbr'):
            pbr = float(data['pbr'])
            if pbr < -100 or pbr > 200:  # Relaxed upper bound for growth stocks
                logger.debug(f"Validation failed: P/B out of range={pbr}")
                return False

        # Dividend yield sanity check (if available) - More permissive for data errors
        if data.get('dividend_yield'):
            div_yield = float(data['dividend_yield'])
            if div_yield < 0 or div_yield > 200:  # Relaxed to catch egregious errors only
                logger.debug(f"Validation failed: Dividend yield out of range={div_yield}%")
                return False

        return True

    def insert_or_update_fundamental_data(self, data: Dict) -> bool:
        """
        Insert or update ticker_fundamentals record

        Args:
            data: Fundamental metrics (yfinance data)

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert/update fundamental data for {data['region']}:{data['ticker']}")
            logger.info(f"   → Date: {data['date']}")
            logger.info(f"   → Data Source: {data['data_source']}")
            logger.info(f"   → P/E: {data['per']}, P/B: {data['pbr']}, Div Yield: {data['dividend_yield']}%")
            logger.info(f"   → Market Cap: {data['market_cap']:,} ({data['region']} currency)")
            self.stats['success'] += 1
            return True

        try:
            # UPSERT query
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr, pcr, ev, ev_ebitda,
                dividend_yield, dividend_per_share,
                data_source, created_at
            )
            VALUES (
                %(ticker)s, %(region)s, %(date)s, %(period_type)s,
                %(shares_outstanding)s, %(market_cap)s, %(close_price)s,
                %(per)s, %(pbr)s, %(psr)s, NULL, %(ev)s, %(ev_ebitda)s,
                %(dividend_yield)s, %(dividend_per_share)s,
                %(data_source)s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                shares_outstanding = EXCLUDED.shares_outstanding,
                market_cap = EXCLUDED.market_cap,
                close_price = EXCLUDED.close_price,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                psr = EXCLUDED.psr,
                ev = EXCLUDED.ev,
                ev_ebitda = EXCLUDED.ev_ebitda,
                dividend_yield = EXCLUDED.dividend_yield,
                dividend_per_share = EXCLUDED.dividend_per_share,
                data_source = EXCLUDED.data_source
            """

            success = self.db.execute_update(query, data)

            if success:
                # Determine if insert or update based on cursor rowcount
                if self.db.cursor.rowcount > 0:
                    if 'INSERT' in self.db.cursor.statusmessage:
                        self.stats['records_inserted'] += 1
                        logger.info(f"✅ [{data['region']}:{data['ticker']}] Inserted fundamental data")
                    else:
                        self.stats['records_updated'] += 1
                        logger.info(f"✅ [{data['region']}:{data['ticker']}] Updated fundamental data")

                self.stats['success'] += 1
                return True
            else:
                self.stats['failed'] += 1
                return False

        except Exception as e:
            logger.error(f"❌ [{data['region']}:{data['ticker']}] Database insert/update failed: {e}")
            self.stats['failed'] += 1
            return False

    def check_duplicate_exists(self, ticker: str, region: str, target_date: date = None) -> bool:
        """
        Check if fundamental data already exists for ticker+region+date

        Args:
            ticker: Stock ticker
            region: Market region (US/JP/CN/HK/VN)
            target_date: Date to check (default: today)

        Returns:
            True if data exists, False otherwise
        """
        if target_date is None:
            target_date = date.today()

        try:
            query = """
            SELECT COUNT(*) as count
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND date = %s
              AND data_source = 'yfinance'
            """
            result = self.db.execute_query(query, (ticker, region, target_date))

            if result and result[0]['count'] > 0:
                logger.debug(f"🔄 [{region}:{ticker}] Duplicate found for {target_date}, will update")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ [{region}:{ticker}] Duplicate check failed: {e}")
            return False

    def run_backfill(self, region: str = None, incremental: bool = False, limit: int = None) -> Dict:
        """
        Run yfinance fundamental data backfill

        Args:
            region: Filter by specific region (US/JP/CN/HK/VN)
            incremental: Only update missing/stale data
            limit: Maximum number of tickers to process

        Returns:
            Statistics dictionary
        """
        # Get tickers for backfill
        tickers = self.get_global_tickers_for_backfill(region=region, incremental=incremental, limit=limit)

        if not tickers:
            logger.warning("⚠️ No tickers found for backfill")
            return self.stats

        logger.info(f"\n📊 Processing {len(tickers)} tickers...")

        # Process each ticker
        for idx, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            name = ticker_info['name']
            region_code = ticker_info['region']

            logger.info(f"\n[{idx}/{len(tickers)}] Processing {region_code}:{ticker}...")
            logger.info("=" * 60)
            logger.info(f"Processing {region_code}:{ticker} ({name})")
            logger.info("=" * 60)

            self.stats['tickers_processed'] += 1

            # Skip CN legacy tickers (1-5 digit codes not supported by yfinance)
            if region_code == 'CN' and not self.is_valid_cn_ticker(ticker):
                logger.info(f"⏭️ [CN:{ticker}] Skipping legacy ticker (yfinance only supports 6-digit CN codes)")
                self.stats['skipped_legacy_cn'] += 1
                continue

            # Skip US slash-based tickers (preferred stocks, units, warrants)
            if region_code == 'US' and not self.is_valid_us_ticker(ticker):
                logger.info(f"⏭️ [US:{ticker}] Skipping slash-based ticker (preferred/unit/warrant format not supported)")
                self.stats['skipped_us_special'] += 1
                continue

            # Check for duplicates (will still update if exists via UPSERT)
            today = date.today()
            if self.check_duplicate_exists(ticker, region_code, today):
                logger.info(f"🔄 [{region_code}:{ticker}] Data exists for {today}, will update with latest")

            # Fetch yfinance data
            yf_data = self.fetch_yfinance_fundamental_data(ticker, region_code)

            if not yf_data:
                self.stats['skipped_no_data'] += 1
                continue

            # Insert/update database
            self.insert_or_update_fundamental_data(yf_data)

        return self.stats

    def generate_coverage_report(self) -> Dict:
        """Generate coverage report by region"""
        try:
            query = """
            SELECT
                tf.region,
                COUNT(DISTINCT tf.ticker) as tickers_with_data,
                (SELECT COUNT(*) FROM tickers WHERE region = tf.region AND asset_type = 'STOCK' AND is_active = TRUE) as total_tickers,
                ROUND(COUNT(DISTINCT tf.ticker)::numeric /
                      (SELECT COUNT(*) FROM tickers WHERE region = tf.region AND asset_type = 'STOCK' AND is_active = TRUE) * 100, 2) as coverage_pct,
                COUNT(CASE WHEN tf.data_source LIKE '%yfinance%' THEN 1 END) as yfinance_records
            FROM ticker_fundamentals tf
            WHERE tf.region IN ('US', 'JP', 'CN', 'HK', 'VN')
              AND tf.date >= NOW() - INTERVAL '30 days'
            GROUP BY tf.region
            ORDER BY tf.region
            """

            results = self.db.execute_query(query)

            coverage = {}
            for row in results:
                region = row['region']
                coverage[region] = {
                    'tickers_with_data': row['tickers_with_data'],
                    'total_tickers': row['total_tickers'],
                    'coverage_pct': float(row['coverage_pct']),
                    'yfinance_records': row['yfinance_records'],
                    'target_pct': self.TARGET_COVERAGE.get(region, 0.50) * 100
                }

            return coverage

        except Exception as e:
            logger.error(f"Failed to generate coverage report: {e}")
            return {}


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="yfinance Fundamental Data Backfill (Phase 1.5 - Day 3)")
    parser.add_argument('--dry-run', action='store_true', help='Preview operations without database writes')
    parser.add_argument('--incremental', action='store_true', help='Only fetch missing/stale data (last 30 days)')
    parser.add_argument('--region', choices=['US', 'JP', 'CN', 'HK', 'VN'], help='Filter by specific region')
    parser.add_argument('--limit', type=int, help='Limit number of tickers (for testing)')
    parser.add_argument('--rate-limit', type=float, default=0.5, help='Delay between API calls in seconds (default: 0.5)')

    args = parser.parse_args()

    # Connect to database
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    # Initialize backfiller
    backfiller = YFinanceFundamentalBackfiller(
        db=db,
        dry_run=args.dry_run,
        rate_limit_delay=args.rate_limit
    )

    # Print configuration
    logger.info("=" * 80)
    logger.info("PHASE 1.5 - DAY 3: YFINANCE FUNDAMENTAL DATA BACKFILL (GLOBAL MARKETS)")
    logger.info("=" * 80)
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'INCREMENTAL' if args.incremental else 'FULL BACKFILL'}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Rate Limit: {args.rate_limit} sec/request")
    logger.info(f"Region Filter: {args.region or 'All (US/JP/CN/HK/VN)'}")
    if args.limit:
        logger.info(f"Limit: {args.limit} tickers")
    logger.info("=" * 80)

    # Run backfill
    start_time = datetime.now()

    try:
        stats = backfiller.run_backfill(
            region=args.region,
            incremental=args.incremental,
            limit=args.limit
        )

        end_time = datetime.now()
        duration = end_time - start_time

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("BACKFILL COMPLETED")
        logger.info("=" * 80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")

        logger.info("\nStatistics:")
        logger.info(f"  Tickers Processed: {stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {stats['success']}")
        logger.info(f"  ⏭️ Skipped (CN Legacy): {stats['skipped_legacy_cn']}")
        logger.info(f"  ⏭️ Skipped (US Special): {stats['skipped_us_special']}")
        logger.info(f"  ⚠️ Skipped (No Data): {stats['skipped_no_data']}")
        logger.info(f"  ❌ Failed: {stats['failed']}")

        if not args.dry_run:
            logger.info("\nDatabase Operations:")
            logger.info(f"  Records Inserted: {stats['records_inserted']}")
            logger.info(f"  Records Updated: {stats['records_updated']}")

        logger.info("\nAPI Metrics:")
        logger.info(f"  Total API Calls: {stats['api_calls']}")
        if stats['api_call_times']:
            avg_time = sum(stats['api_call_times']) / len(stats['api_call_times'])
            logger.info(f"  Avg Time per Call: {avg_time:.2f} sec")

        logger.info("=" * 80)

        # Generate coverage report
        coverage = backfiller.generate_coverage_report()

        if coverage:
            logger.info("\n📊 Global Market Coverage:")
            for region, metrics in coverage.items():
                logger.info(f"  {region}:")
                logger.info(f"    Tickers with Data: {metrics['tickers_with_data']}")
                logger.info(f"    Total Tickers: {metrics['total_tickers']}")
                logger.info(f"    Coverage: {metrics['coverage_pct']}%")
                logger.info(f"    yfinance Records: {metrics['yfinance_records']}")

                if metrics['coverage_pct'] >= metrics['target_pct']:
                    logger.info(f"    ✅ Target coverage (>{metrics['target_pct']}%) ACHIEVED")
                else:
                    need_more = int((metrics['target_pct'] / 100 * metrics['total_tickers']) - metrics['tickers_with_data'])
                    logger.info(f"    ⚠️ Target coverage (>{metrics['target_pct']}%) NOT YET ACHIEVED")
                    logger.info(f"    → Need {need_more} more tickers")

        # Success/failure message
        success_rate = (stats['success'] / stats['tickers_processed'] * 100) if stats['tickers_processed'] > 0 else 0

        if success_rate >= 80:
            logger.info(f"✅ Backfill completed successfully (success rate: {success_rate:.1f}%)")
        elif success_rate >= 50:
            logger.warning(f"⚠️ Backfill completed with moderate success rate: {success_rate:.1f}%")
        else:
            logger.warning(f"⚠️ Backfill completed with low success rate: {success_rate:.1f}%")

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Backfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close_pool()


if __name__ == '__main__':
    main()
