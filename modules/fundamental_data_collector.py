#!/usr/bin/env python3
"""
Fundamental Data Collector - Multi-Region Support

Orchestrates fundamental data collection for stocks across multiple markets.
Supports Korean market (DART API) and global markets (yfinance).

Key Features:
- Multi-region support (KR, US, HK, CN, JP, VN)
- API source routing (DART for KR, yfinance for global)
- Intelligent caching (24-hour TTL for daily metrics)
- Batch processing with rate limiting
- Error handling and retry logic

Author: Spock Trading System
"""

import os
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from .db_manager_sqlite import SQLiteDatabaseManager
from .dart_api_client import DARTApiClient
from .api_clients.yfinance_api import YFinanceAPI

logger = logging.getLogger(__name__)


class FundamentalDataCollector:
    """
    Fundamental data collection orchestrator

    Workflow:
    1. Detect market region (KR vs global)
    2. Route to appropriate API (DART for KR, yfinance for global)
    3. Extract fundamental metrics
    4. Apply caching logic (skip if data fresh <24h)
    5. Store to ticker_fundamentals table

    Usage:
        collector = FundamentalDataCollector(db_manager)

        # Korean stocks
        results = collector.collect_fundamentals(['005930', '035720'], region='KR')

        # US stocks
        results = collector.collect_fundamentals(['AAPL', 'MSFT'], region='US')
    """

    # Supported regions
    SUPPORTED_REGIONS = ['KR', 'US', 'HK', 'CN', 'JP', 'VN']

    # Cache TTL by data type (hours)
    CACHE_TTL = {
        'DAILY': 24,       # Daily metrics: 24 hours
        'QUARTERLY': 2160,  # Quarterly statements: 90 days
        'ANNUAL': 8760      # Annual reports: 365 days
    }

    def __init__(self, db_manager: SQLiteDatabaseManager):
        """
        Initialize fundamental data collector

        Args:
            db_manager: SQLiteDatabaseManager instance
        """
        self.db = db_manager

        # API clients (lazy initialization)
        self._dart_api = None
        self._yfinance_api = None

        # Corporate ID mappers (lazy initialization)
        self._kr_mapper = None
        self._us_mapper = None
        self._cn_mapper = None
        self._hk_mapper = None
        self._jp_mapper = None
        self._vn_mapper = None

        logger.info("📊 FundamentalDataCollector initialized")

    @property
    def dart_api(self) -> Optional[DARTApiClient]:
        """Lazy initialization of DART API client"""
        if self._dart_api is None:
            dart_api_key = os.getenv('DART_API_KEY')
            if dart_api_key:
                self._dart_api = DARTApiClient(api_key=dart_api_key)
                logger.info("✅ DART API client initialized")
            else:
                logger.warning("⚠️ DART_API_KEY not found in environment")
        return self._dart_api

    @property
    def yfinance_api(self) -> YFinanceAPI:
        """Lazy initialization of yfinance API client"""
        if self._yfinance_api is None:
            self._yfinance_api = YFinanceAPI(rate_limit_per_second=1.0)
            logger.info("✅ yfinance API client initialized")
        return self._yfinance_api

    @property
    def kr_mapper(self):
        """Lazy initialization of Korean corporate ID mapper"""
        if self._kr_mapper is None:
            try:
                from .mappers import KRCorporateIDMapper
                self._kr_mapper = KRCorporateIDMapper()
                logger.info("✅ KRCorporateIDMapper initialized")
            except Exception as e:
                logger.warning(f"⚠️ KRCorporateIDMapper initialization failed: {e}")
                self._kr_mapper = False  # Mark as unavailable
        return self._kr_mapper if self._kr_mapper is not False else None

    @property
    def us_mapper(self):
        """Lazy initialization of US corporate ID mapper"""
        # TODO: Phase 2 - Implement USCorporateIDMapper
        return None

    @property
    def cn_mapper(self):
        """Lazy initialization of China corporate ID mapper"""
        # TODO: Phase 2 - Implement CNCorporateIDMapper
        return None

    @property
    def hk_mapper(self):
        """Lazy initialization of Hong Kong corporate ID mapper"""
        # TODO: Phase 2 - Implement HKCorporateIDMapper
        return None

    @property
    def jp_mapper(self):
        """Lazy initialization of Japan corporate ID mapper"""
        # TODO: Phase 2 - Implement JPCorporateIDMapper
        return None

    @property
    def vn_mapper(self):
        """Lazy initialization of Vietnam corporate ID mapper"""
        # TODO: Phase 2 - Implement VNCorporateIDMapper
        return None

    def collect_fundamentals(self,
                            tickers: List[str],
                            region: str,
                            force_refresh: bool = False,
                            batch_size: int = 100) -> Dict[str, bool]:
        """
        Collect fundamental data for tickers

        Args:
            tickers: List of ticker symbols
            region: Market region (KR, US, HK, CN, JP, VN)
            force_refresh: Skip cache and force new API calls
            batch_size: Number of tickers per batch

        Returns:
            Dict {ticker: success_status}

        Example:
            results = collector.collect_fundamentals(
                tickers=['005930', '035720'],
                region='KR',
                force_refresh=False
            )
            # {'005930': True, '035720': True}
        """
        # Validate region
        if region not in self.SUPPORTED_REGIONS:
            logger.error(f"❌ Unsupported region: {region}")
            return {ticker: False for ticker in tickers}

        logger.info(f"📊 [{region}] Collecting fundamentals for {len(tickers)} tickers")

        results = {}
        total_collected = 0
        total_skipped = 0
        total_failed = 0

        # Process tickers in batches
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            logger.info(f"🔄 [{region}] Processing batch {i//batch_size + 1} ({len(batch)} tickers)")

            for ticker in batch:
                try:
                    # Check cache (skip if fresh data exists)
                    if not force_refresh and self._should_skip_ticker(ticker, region):
                        logger.debug(f"⏭️ [{region}] {ticker}: Using cached data")
                        results[ticker] = True
                        total_skipped += 1
                        continue

                    # Route to appropriate API based on region
                    if region == 'KR':
                        success = self._collect_from_dart(ticker)
                    else:
                        success = self._collect_from_yfinance(ticker, region)

                    results[ticker] = success

                    if success:
                        total_collected += 1
                        logger.debug(f"✅ [{region}] {ticker}: Fundamental data collected")
                    else:
                        total_failed += 1
                        logger.warning(f"⚠️ [{region}] {ticker}: Collection failed")

                except Exception as e:
                    logger.error(f"❌ [{region}] {ticker}: Unexpected error - {e}")
                    results[ticker] = False
                    total_failed += 1

        # Summary
        logger.info(
            f"📊 [{region}] Fundamental collection complete: "
            f"Collected={total_collected}, Cached={total_skipped}, Failed={total_failed}"
        )

        return results

    def collect_historical_fundamentals(self,
                                       tickers: List[str],
                                       region: str,
                                       start_year: int = 2020,
                                       end_year: int = 2024,
                                       force_refresh: bool = False) -> Dict[str, Dict[int, bool]]:
        """
        Collect historical annual fundamental data for backtesting

        Args:
            tickers: List of ticker symbols
            region: Market region (currently only 'KR' supported)
            start_year: Start fiscal year (default: 2020)
            end_year: End fiscal year (default: 2024)
            force_refresh: Skip cache and force fresh collection

        Returns:
            Dict[ticker, Dict[year, success_bool]]

        Example:
            collector = FundamentalDataCollector(db)

            # Collect 2020-2024 annual data for Korean stocks
            results = collector.collect_historical_fundamentals(
                tickers=['005930', '035720'],
                region='KR',
                start_year=2020,
                end_year=2024
            )

            # results = {
            #     '005930': {2020: True, 2021: True, 2022: True, 2023: True, 2024: True},
            #     '035720': {2020: True, 2021: False, ...}
            # }

        Note:
            - Only annual reports collected for efficiency
            - Korean market only in Phase 1 (DART API)
            - Global markets: Phase 2 (yfinance has limited historical support)
        """
        if region.upper() != 'KR':
            logger.error(f"❌ Historical collection currently only supports Korean market (KR)")
            logger.info(f"💡 Global market historical data: Phase 2 enhancement")
            return {}

        logger.info(
            f"📊 [HISTORICAL] Starting collection: "
            f"{len(tickers)} tickers, {start_year}-{end_year} ({end_year - start_year + 1} years)"
        )

        results = {}
        total_years = end_year - start_year + 1
        total_expected = len(tickers) * total_years

        for ticker in tickers:
            results[ticker] = {}

            try:
                # Get corp_code from mapper
                if not self.kr_mapper:
                    logger.error(f"❌ [KR] {ticker}: KRCorporateIDMapper not available")
                    for year in range(start_year, end_year + 1):
                        results[ticker][year] = False
                    continue

                corp_code = self.kr_mapper.get_corporate_id(ticker)

                if not corp_code:
                    logger.warning(f"⚠️ [KR] {ticker}: Corp code not found")
                    for year in range(start_year, end_year + 1):
                        results[ticker][year] = False
                    continue

                # Check cache unless force_refresh
                if not force_refresh:
                    cached_years = self._get_cached_historical_years(ticker, start_year, end_year)
                    if len(cached_years) == total_years:
                        logger.info(f"⏭️ [KR] {ticker}: All years cached, skipping")
                        for year in range(start_year, end_year + 1):
                            results[ticker][year] = True
                        continue
                    else:
                        logger.info(f"📊 [KR] {ticker}: {len(cached_years)}/{total_years} years cached")

                # Collect historical data from DART
                metrics_list = self.dart_api.get_historical_fundamentals(
                    ticker=ticker,
                    corp_code=corp_code,
                    start_year=start_year,
                    end_year=end_year
                )

                # Store each year's data
                for metrics in metrics_list:
                    year = metrics.get('fiscal_year')
                    success = self.db.insert_ticker_fundamentals(metrics)
                    results[ticker][year] = success

                # Mark missing years as failed
                collected_years = [m.get('fiscal_year') for m in metrics_list]
                for year in range(start_year, end_year + 1):
                    if year not in collected_years:
                        results[ticker][year] = False

                logger.info(f"✅ [KR] {ticker}: Collected {len(metrics_list)}/{total_years} years")

            except Exception as e:
                logger.error(f"❌ [KR] {ticker}: Historical collection failed - {e}")
                for year in range(start_year, end_year + 1):
                    results[ticker][year] = False

        # Summary
        total_collected = sum(
            1 for ticker_results in results.values()
            for success in ticker_results.values()
            if success
        )

        logger.info(
            f"📊 [HISTORICAL] Collection complete: "
            f"{total_collected}/{total_expected} data points "
            f"({total_collected / total_expected * 100:.1f}% success rate)"
        )

        return results

    def _get_cached_historical_years(self, ticker: str,
                                    start_year: int,
                                    end_year: int) -> List[int]:
        """
        Get list of years that already have cached fundamental data

        Args:
            ticker: Ticker symbol
            start_year: Start year to check
            end_year: End year to check

        Returns:
            List of years with cached data
        """
        cached_years = []

        for year in range(start_year, end_year + 1):
            try:
                fundamentals = self.db.get_ticker_fundamentals(
                    ticker=ticker,
                    period_type='ANNUAL',
                    fiscal_year=year,
                    limit=1
                )

                if fundamentals:
                    cached_years.append(year)

            except Exception:
                continue

        return cached_years

    def _should_skip_ticker(self, ticker: str, region: str) -> bool:
        """
        Check if ticker has fresh cached fundamental data

        Args:
            ticker: Ticker symbol
            region: Market region

        Returns:
            True if cached data is fresh (within TTL), False otherwise
        """
        try:
            # Get latest fundamental data for ticker
            fundamentals = self.db.get_ticker_fundamentals(
                ticker=ticker,
                region=region,
                limit=1
            )

            if not fundamentals:
                return False

            latest = fundamentals[0]
            last_update = datetime.fromisoformat(latest['created_at'])
            period_type = latest.get('period_type', 'DAILY')

            # Calculate cache TTL
            ttl_hours = self.CACHE_TTL.get(period_type, 24)
            elapsed_hours = (datetime.now() - last_update).total_seconds() / 3600

            if elapsed_hours < ttl_hours:
                logger.debug(
                    f"⏭️ [{region}] {ticker}: Cache hit "
                    f"(age: {elapsed_hours:.1f}h, TTL: {ttl_hours}h)"
                )
                return True

            return False

        except Exception as e:
            logger.debug(f"Cache check failed for {ticker}: {e}")
            return False

    def _collect_from_dart(self, ticker: str) -> bool:
        """
        Collect fundamental data from DART API (Korean stocks)

        Args:
            ticker: Korean stock ticker (6-digit code)

        Returns:
            True if successful

        Note:
            Phase 1 Week 2: Implemented with corp_code mapping ✅
            Uses KRCorporateIDMapper for ticker → corp_code lookup
        """
        if not self.dart_api:
            logger.error(f"❌ [KR] {ticker}: DART API not available")
            return False

        try:
            # Step 1: Get corp_code from mapper
            if not self.kr_mapper:
                logger.error(f"❌ [KR] {ticker}: KRCorporateIDMapper not available")
                return False

            corp_code = self.kr_mapper.get_corporate_id(ticker)

            if not corp_code:
                logger.warning(f"⚠️ [KR] {ticker}: Corp code not found in mapping")
                return False

            logger.debug(f"🔍 [KR] {ticker} → corp_code: {corp_code}")

            # Step 2: Get fundamental metrics from DART
            metrics = self.dart_api.get_fundamental_metrics(ticker, corp_code=corp_code)

            if not metrics:
                logger.warning(f"⚠️ [KR] {ticker}: No DART fundamental data")
                return False

            # Step 3: Filter out extra fields (debt_ratio, roe, roa) not in DB schema
            # Database expects these 36 fields only
            db_fields = [
                'ticker', 'date', 'period_type', 'fiscal_year',
                'shares_outstanding', 'market_cap', 'close_price',
                'per', 'pbr', 'psr', 'pcr', 'ev', 'ev_ebitda',
                'dividend_yield', 'dividend_per_share',
                'total_assets', 'total_liabilities', 'total_equity',
                'revenue', 'operating_profit', 'net_income', 'ebitda',
                'cogs', 'gross_profit', 'depreciation', 'interest_expense',
                'current_assets', 'current_liabilities', 'inventory',
                'accounts_receivable', 'cash_and_equivalents',
                'operating_cash_flow', 'capital_expenditure',
                'free_float_percentage', 'created_at', 'data_source'
            ]
            filtered_metrics = {k: v for k, v in metrics.items() if k in db_fields}

            # Step 4: Store to database
            success = self.db.insert_ticker_fundamentals(filtered_metrics)

            if success:
                logger.debug(f"✅ [KR] {ticker}: DART fundamentals stored to database")
            else:
                logger.warning(f"⚠️ [KR] {ticker}: Database insertion failed")

            return success

        except Exception as e:
            logger.error(f"❌ [KR] {ticker}: DART collection failed - {e}")
            return False

    def _collect_from_yfinance(self, ticker: str, region: str) -> bool:
        """
        Collect fundamental data from yfinance (global stocks)

        Args:
            ticker: Ticker symbol (e.g., 'AAPL', '0700.HK')
            region: Market region (US, HK, CN, JP, VN)

        Returns:
            True if successful

        Note:
            This is a placeholder for Phase 3.
            yfinance fundamental extraction will be implemented in Phase 3 Week 5.
        """
        try:
            # Get ticker info from yfinance
            info = self.yfinance_api.get_ticker_info(ticker)

            if not info:
                logger.warning(f"⚠️ [{region}] {ticker}: No data from yfinance")
                return False

            # Extract fundamental fields
            fundamental_data = self._extract_yfinance_fundamentals(ticker, region, info)

            if not fundamental_data:
                logger.warning(f"⚠️ [{region}] {ticker}: Failed to extract fundamentals")
                return False

            # Store to database
            success = self.db.insert_ticker_fundamentals(fundamental_data)

            if success:
                logger.debug(f"✅ [{region}] {ticker}: Fundamentals stored to database")
            else:
                logger.warning(f"⚠️ [{region}] {ticker}: Database insertion failed")

            return success

        except Exception as e:
            logger.error(f"❌ [{region}] {ticker}: yfinance collection failed - {e}")
            return False

    def _extract_yfinance_fundamentals(self,
                                      ticker: str,
                                      region: str,
                                      info: Dict) -> Optional[Dict]:
        """
        Extract fundamental metrics from yfinance info dict

        Args:
            ticker: Ticker symbol
            region: Market region
            info: Raw yfinance info dictionary

        Returns:
            Formatted fundamental data dict for database insertion

        Note:
            Phase 1: Basic metrics only (market_cap, close_price)
            Phase 3: Full 40+ field extraction (PER, PBR, ROE, etc.)
        """
        try:
            # Basic extraction (Phase 1)
            fundamental_data = {
                'ticker': ticker,
                'region': region,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'period_type': 'DAILY',
                'market_cap': info.get('marketCap'),
                'close_price': info.get('currentPrice') or info.get('regularMarketPrice'),
                'created_at': datetime.now().isoformat(),
                'data_source': 'yfinance'
            }

            # TODO: Phase 3 - Add comprehensive field extraction
            # PER, PBR, ROE, margins, debt ratios, dividends, etc.

            return fundamental_data

        except Exception as e:
            logger.error(f"❌ [{region}] {ticker}: Field extraction failed - {e}")
            return None

    def get_fundamentals(self,
                        ticker: str,
                        region: str,
                        limit: int = 1) -> Optional[List[Dict]]:
        """
        Retrieve fundamental data for a ticker from database

        Args:
            ticker: Ticker symbol
            region: Market region
            limit: Number of records to return (default: 1 = latest)

        Returns:
            List of fundamental data dictionaries or None

        Example:
            fundamentals = collector.get_fundamentals('005930', 'KR')
            if fundamentals:
                print(f"PER: {fundamentals[0]['per']}")
                print(f"PBR: {fundamentals[0]['pbr']}")
        """
        try:
            return self.db.get_ticker_fundamentals(
                ticker=ticker,
                region=region,
                limit=limit
            )
        except Exception as e:
            logger.error(f"❌ [{region}] {ticker}: Failed to retrieve fundamentals - {e}")
            return None


def main():
    """
    CLI interface for standalone fundamental data collection

    Usage:
        # Korean stocks
        python3 modules/fundamental_data_collector.py --tickers 005930 035720 --region KR

        # US stocks
        python3 modules/fundamental_data_collector.py --tickers AAPL MSFT --region US --force-refresh

        # Batch mode (read from file)
        python3 modules/fundamental_data_collector.py --file tickers.txt --region KR
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Fundamental Data Collector - Multi-Region Support'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='List of ticker symbols (e.g., 005930 035720)'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Path to file containing ticker list (one per line)'
    )
    parser.add_argument(
        '--region',
        required=True,
        choices=['KR', 'US', 'HK', 'CN', 'JP', 'VN'],
        help='Market region'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh (skip cache)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for processing (default: 100)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run (do not save to database)'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Collect tickers
    tickers = []
    if args.tickers:
        tickers.extend(args.tickers)
    if args.file:
        with open(args.file, 'r') as f:
            tickers.extend([line.strip() for line in f if line.strip()])

    if not tickers:
        logger.error("❌ No tickers provided. Use --tickers or --file")
        return 1

    logger.info(f"📊 Starting fundamental collection for {len(tickers)} tickers")
    logger.info(f"📍 Region: {args.region}")
    logger.info(f"🔄 Force refresh: {args.force_refresh}")
    logger.info(f"🏃 Dry run: {args.dry_run}")

    # Initialize collector
    db = SQLiteDatabaseManager()
    collector = FundamentalDataCollector(db)

    # Collect fundamentals
    if args.dry_run:
        logger.info("🏃 DRY RUN: Skipping database operations")
        results = {ticker: True for ticker in tickers}
    else:
        results = collector.collect_fundamentals(
            tickers=tickers,
            region=args.region,
            force_refresh=args.force_refresh,
            batch_size=args.batch_size
        )

    # Report results
    success_count = sum(1 for success in results.values() if success)
    fail_count = len(results) - success_count

    logger.info("\n" + "="*60)
    logger.info(f"📊 Fundamental Collection Report")
    logger.info("="*60)
    logger.info(f"Total tickers: {len(tickers)}")
    logger.info(f"✅ Success: {success_count}")
    logger.info(f"❌ Failed: {fail_count}")
    logger.info(f"📈 Success rate: {success_count/len(tickers)*100:.1f}%")
    logger.info("="*60)

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    exit(main())
