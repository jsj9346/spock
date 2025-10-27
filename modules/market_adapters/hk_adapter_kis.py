"""
Hong Kong Market Adapter (KIS API)

Korea Investment & Securities (한국투자증권) 해외주식 API 기반 홍콩 시장 어댑터
- 한국인 거래 가능 종목만 제공
- Rate limiting: 20 req/sec (yfinance 1 req/sec 대비 20배 빠름)
- Exchange: HKEX (Hong Kong Stock Exchange)

Key Features:
- Tradable ticker filtering (Korean investors only)
- Fast data collection (20 req/sec vs yfinance 1 req/sec)
- Unified GICS sector classification
- Technical indicator calculation (MA, RSI, MACD, BB, ATR)
- Market calendar integration (HK holidays, lunch break)

Trading Hours: 09:30-12:00, 13:00-16:00 HKT (lunch break 12:00-13:00)
Currency: HKD

Author: Spock Trading System
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

from modules.market_adapters.base_adapter import BaseMarketAdapter
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from modules.parsers.hk_stock_parser import HKStockParser
from modules.market_adapters.calendars.market_calendar import MarketCalendar

logger = logging.getLogger(__name__)


class HKAdapterKIS(BaseMarketAdapter):
    """
    Hong Kong market data adapter using KIS API (tradable tickers only)

    Advantages over yfinance adapter:
    - 20x faster data collection (20 req/sec vs 1 req/sec)
    - Only tradable tickers for Korean investors
    - Single API key management (no separate API key)
    - Unified data format across all markets

    Exchange Coverage:
    - SEHK: Hong Kong Stock Exchange (HKEX)

    Market Characteristics:
    - Trading hours: 09:30-12:00, 13:00-16:00 HKT (lunch break)
    - Ticker format: 4-digit codes (e.g., "0700" for Tencent)
    - Currency: HKD
    - Major indices: Hang Seng Index (HSI), Hang Seng Tech Index

    Data Sources:
    - Primary: KIS API (ticker list, OHLCV)
    - Fallback: yfinance (fundamentals, company info)
    """

    # KIS API exchange code for Hong Kong
    EXCHANGE_CODE = 'SEHK'  # Hong Kong Stock Exchange

    REGION_CODE = 'HK'

    def __init__(self,
                 db_manager,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443'):
        """
        Initialize Hong Kong market adapter with KIS API

        Args:
            db_manager: Database manager instance
            app_key: KIS API app key
            app_secret: KIS API app secret
            base_url: KIS API base URL (default: production)
        """
        super().__init__(db_manager, region_code=self.REGION_CODE)

        # Initialize KIS API client
        self.kis_api = KISOverseasStockAPI(
            app_key=app_key,
            app_secret=app_secret,
            base_url=base_url
        )

        # Initialize parser and utilities
        self.stock_parser = HKStockParser()
        self.calendar = MarketCalendar(region='HK')

        logger.info(f"🇭🇰 HKAdapterKIS initialized (KIS API)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    max_count: Optional[int] = None,
                    use_master_file: bool = True) -> List[Dict]:
        """
        Scan Hong Kong stocks from KIS Master Files or API (tradable tickers only)

        Data Source Priority:
        1. Master File: Instant, ~500-1,000 HK stocks, comprehensive metadata
        2. KIS API: 20 req/sec, real-time data (fallback)

        Process:
        1. Check cache (24-hour TTL) unless force_refresh
        2. Try master file first (instant, no API calls)
        3. Fallback to API if master file unavailable
        4. Parse ticker information with HKStockParser (yfinance)
        5. Save to database (tickers + stock_details tables)
        6. Return list of stock dictionaries

        Args:
            force_refresh: Skip cache and fetch fresh data
            max_count: Maximum tickers to return (for testing)
            use_master_file: Try master file first (default: True)

        Returns:
            List of stock dictionaries with ticker, name, sector, etc.

        Performance:
        - Master File: Instant (no API calls), ~500-1,000 stocks
        - API Method: ~25-50 seconds (20 req/sec)
        - 20x faster than yfinance (1 req/sec)
        """
        logger.info(f"🇭🇰 Scanning HK stocks ({'Master File' if use_master_file else 'KIS API'})...")

        # Check cache unless force refresh
        if not force_refresh:
            cached_stocks = self._load_tickers_from_cache(
                asset_type='STOCK',
                ttl_hours=24
            )
            if cached_stocks:
                logger.info(f"✅ Loaded {len(cached_stocks)} HK stocks from cache")
                return cached_stocks

        # Try master file first (instant, comprehensive)
        if use_master_file:
            all_stocks = self._scan_stocks_from_master_file(max_count)
            if all_stocks:
                # Save to database
                logger.info(f"💾 Saving {len(all_stocks)} HK stocks to database...")
                self._save_tickers_to_db(all_stocks, asset_type='STOCK')
                logger.info(f"✅ Master File scan complete: {len(all_stocks)} stocks")
                return all_stocks

            logger.info("⚠️ Master file unavailable, falling back to API method")

        # Fallback to API method (legacy)
        return self._scan_stocks_from_api(max_count)

    def _scan_stocks_from_master_file(self,
                                      max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan HK stocks from master files (instant, no API calls)

        Args:
            max_count: Maximum tickers to return (for testing)

        Returns:
            List of stock dictionaries

        Performance:
        - Instant: No API calls
        - Coverage: ~500-1,000 HK stocks
        """
        try:
            # Get detailed ticker information from master files
            hk_tickers = self.kis_api.get_tickers_with_details(
                region=self.REGION_CODE,
                force_refresh=False
            )

            if not hk_tickers:
                logger.warning("⚠️ No HK tickers from master files")
                return []

            logger.info(f"✅ Master File: {len(hk_tickers)} HK tickers loaded (instant)")

            # Apply max_count if specified
            if max_count:
                hk_tickers = hk_tickers[:max_count]
                logger.info(f"   Limited to {max_count} tickers")

            # Convert master file data to stock dictionaries
            all_stocks = []
            for ticker_data in hk_tickers:
                try:
                    # Fetch lot_size from KIS API (HK has variable board lots)
                    lot_size = self._fetch_lot_size(ticker_data['ticker'])

                    # Use master file data directly (no yfinance enrichment required)
                    stock_info = {
                        'ticker': ticker_data['ticker'],
                        'name': ticker_data.get('name', ''),
                        'name_kor': ticker_data.get('name_kor', ''),
                        'exchange': 'HKEX',
                        'region': self.REGION_CODE,
                        'currency': ticker_data.get('currency', 'HKD'),
                        'asset_type': 'STOCK',
                        'lot_size': lot_size,  # Phase 7: Board lot (ticker-specific)
                        'is_active': True,
                        'kis_exchange_code': self.EXCHANGE_CODE,
                        'sector_code': ticker_data.get('sector_code', ''),
                        # Optional: yfinance enrichment can be done later via collect_fundamentals()
                        'sector': '',  # Will be enriched later
                        'industry': '',  # Will be enriched later
                        'market_cap': 0,  # Will be enriched later
                    }
                    all_stocks.append(stock_info)

                except Exception as e:
                    logger.debug(f"⚠️ Failed to process {ticker_data.get('ticker')}: {e}")
                    continue

            logger.info(f"✅ Master File scan complete: {len(all_stocks)} stocks processed")
            return all_stocks

        except Exception as e:
            logger.error(f"❌ Master file scan failed: {e}")
            return []

    def _scan_stocks_from_api(self,
                             max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan HK stocks from KIS API (legacy method)

        Args:
            max_count: Maximum tickers to return (for testing)

        Returns:
            List of stock dictionaries

        Performance:
        - ~25-50 seconds for ~500-1,000 stocks (20 req/sec)
        """
        try:
            logger.info(f"📡 Fetching tradable tickers from {self.EXCHANGE_CODE} (API)...")

            # Fetch tradable tickers from KIS API (use_master_file=False)
            tickers = self.kis_api.get_tradable_tickers(
                exchange_code=self.EXCHANGE_CODE,
                max_count=max_count,
                use_master_file=False  # Force API method
            )

            if not tickers:
                logger.warning(f"⚠️ No tickers returned for {self.EXCHANGE_CODE}")
                return []

            logger.info(f"✅ {self.EXCHANGE_CODE}: {len(tickers)} tradable tickers")

            # Parse each ticker
            all_stocks = []
            for ticker in tickers:
                try:
                    # Fetch lot_size from KIS API (HK has variable board lots)
                    lot_size = self._fetch_lot_size(ticker)

                    # Get ticker info from yfinance (for fundamentals)
                    ticker_info = self.stock_parser.parse_ticker_info(ticker)

                    if ticker_info:
                        # Add exchange and region info
                        ticker_info['exchange'] = 'HKEX'
                        ticker_info['region'] = self.REGION_CODE
                        ticker_info['asset_type'] = 'STOCK'
                        ticker_info['lot_size'] = lot_size  # Phase 7: Board lot (ticker-specific)
                        ticker_info['is_active'] = True
                        ticker_info['kis_exchange_code'] = self.EXCHANGE_CODE

                        all_stocks.append(ticker_info)

                except Exception as e:
                    logger.debug(f"⚠️ Failed to parse {ticker}: {e}")
                    continue

            if not all_stocks:
                logger.warning("⚠️ No HK stocks found")
                return []

            # Save to database
            logger.info(f"💾 Saving {len(all_stocks)} HK stocks to database...")
            self._save_tickers_to_db(all_stocks, asset_type='STOCK')

            logger.info(f"✅ API scan complete: {len(all_stocks)} stocks")
            return all_stocks

        except Exception as e:
            logger.error(f"❌ Failed to scan {self.EXCHANGE_CODE}: {e}")
            return []

    def scan_etfs(self,
                  force_refresh: bool = False,
                  max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan Hong Kong ETFs from KIS API

        Note: ETF support to be implemented in future phase
        Current implementation returns empty list

        Args:
            force_refresh: Skip cache and fetch fresh data
            max_count: Maximum ETFs to return

        Returns:
            List of ETF dictionaries (empty for now)
        """
        logger.info("📊 HK ETF scanning not yet implemented")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for Hong Kong stocks via KIS API

        Process:
        1. Get ticker list from database (or use provided list)
        2. For each ticker, fetch OHLCV from KIS API
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table
        5. Return success count

        Args:
            tickers: List of tickers (None = all active HK stocks)
            days: Historical days to collect (default: 250)

        Returns:
            Number of successfully collected tickers

        Performance:
        - Rate limit: 20 req/sec
        - ~1,000 stocks: ~50 seconds
        - 20x faster than yfinance
        """
        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(
                region=self.REGION_CODE,
                asset_type='STOCK',
                is_active=True
            )
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ No HK tickers to collect")
            return 0

        logger.info(f"📈 Collecting OHLCV for {len(tickers)} HK stocks ({days} days)...")

        success_count = 0
        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"📊 [{i}/{len(tickers)}] {ticker} ({self.EXCHANGE_CODE})...")

                # Fetch OHLCV from KIS API
                ohlcv_df = self.kis_api.get_ohlcv(
                    ticker=ticker,
                    exchange_code=self.EXCHANGE_CODE,
                    days=days
                )

                if ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] No OHLCV data")
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Add ticker and period type
                ohlcv_df['ticker'] = ticker
                ohlcv_df['period_type'] = 'DAILY'

                # Save to database
                self.db.save_ohlcv_batch(ohlcv_df)

                success_count += 1
                logger.info(f"✅ [{ticker}] {len(ohlcv_df)} days saved")

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")
                continue

        logger.info(f"✅ OHLCV collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for Hong Kong ETFs

        Note: ETF support to be implemented in future phase

        Args:
            tickers: List of ETF tickers
            days: Historical days to collect

        Returns:
            Number of successfully collected ETFs (0 for now)
        """
        logger.info("📊 HK ETF OHLCV collection not yet implemented")
        return 0

    def collect_fundamentals(self,
                            tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for Hong Kong stocks

        Note: KIS API doesn't provide fundamentals for overseas stocks
        Uses yfinance as fallback data source

        Process:
        1. Get ticker list from database (or use provided list)
        2. Fetch fundamentals from yfinance
        3. Parse with HKStockParser
        4. Save to ticker_fundamentals table

        Args:
            tickers: List of tickers (None = all active HK stocks)

        Returns:
            Number of successfully collected tickers

        Data Points:
        - Market cap
        - P/E ratio, P/B ratio
        - Dividend yield
        - EPS, ROE
        - 52-week high/low
        """
        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(
                region=self.REGION_CODE,
                asset_type='STOCK',
                is_active=True
            )
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ No HK tickers for fundamentals")
            return 0

        logger.info(f"💰 Collecting fundamentals for {len(tickers)} HK stocks...")
        logger.info(f"   Data source: yfinance (KIS API doesn't provide fundamentals)")

        success_count = 0
        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"💰 [{i}/{len(tickers)}] {ticker}...")

                # Parse fundamentals from yfinance
                fundamentals = self.stock_parser.parse_fundamentals(ticker)

                if not fundamentals:
                    logger.warning(f"⚠️ [{ticker}] No fundamentals data")
                    continue

                # Add ticker and date
                fundamentals['ticker'] = ticker
                fundamentals['date'] = datetime.now().strftime('%Y-%m-%d')

                # Save to database
                self.db.save_fundamentals(fundamentals)

                success_count += 1
                logger.info(f"✅ [{ticker}] Fundamentals saved")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Fundamentals collection failed: {e}")
                continue

        logger.info(f"✅ Fundamentals collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def add_custom_ticker(self, ticker: str) -> bool:
        """
        Add a custom Hong Kong stock ticker to the database

        Args:
            ticker: Stock ticker symbol (e.g., '0700' for Tencent)

        Returns:
            True if successfully added
        """
        logger.info(f"➕ Adding custom HK ticker: {ticker}")

        try:
            # Check if ticker is tradable via KIS API
            tradable_tickers = self.kis_api.get_tradable_tickers(
                exchange_code=self.EXCHANGE_CODE,
                max_count=None
            )

            if ticker not in tradable_tickers:
                logger.warning(f"⚠️ {ticker} not in KIS tradable list")
                logger.info(f"   Attempting to add anyway via yfinance...")

            # Parse ticker info from yfinance
            ticker_info = self.stock_parser.parse_ticker_info(ticker)

            if not ticker_info:
                logger.error(f"❌ Failed to get info for {ticker}")
                return False

            # Add exchange and region info
            ticker_info['exchange'] = 'HKEX'
            ticker_info['region'] = self.REGION_CODE
            ticker_info['asset_type'] = 'STOCK'
            ticker_info['is_active'] = True
            ticker_info['kis_exchange_code'] = self.EXCHANGE_CODE

            # Save to database
            self._save_tickers_to_db([ticker_info], asset_type='STOCK')

            logger.info(f"✅ Custom ticker {ticker} added successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add custom ticker {ticker}: {e}")
            return False

    def check_connection(self) -> bool:
        """
        Check KIS API connection status

        Returns:
            True if API is accessible
        """
        try:
            return self.kis_api.check_connection()
        except Exception as e:
            logger.error(f"❌ KIS API connection check failed: {e}")
            return False

    def get_market_status(self) -> Dict:
        """
        Get Hong Kong market status (open/closed, next open time)

        Returns:
            Dictionary with market status information
        """
        try:
            is_open = self.calendar.is_market_open()
            next_open = self.calendar.get_next_market_open()
            next_close = self.calendar.get_next_market_close()

            return {
                'region': self.REGION_CODE,
                'is_open': is_open,
                'next_open': next_open,
                'next_close': next_close,
                'timezone': 'Asia/Hong_Kong',
                'trading_hours': '09:30-12:00, 13:00-16:00 HKT',
                'lunch_break': '12:00-13:00'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get market status: {e}")
            return {}

    # ========================================
    # LOT SIZE FETCHING (Phase 7: 2025-10-17)
    # ========================================

    def _fetch_lot_size(self, ticker: str) -> int:
        """
        Fetch HK board lot (lot_size) from KIS Master File

        Hong Kong has ticker-specific board lots (100-2000 shares)
        This is critical for order execution compliance

        Args:
            ticker: Stock ticker (e.g., '0700' for Tencent, '0005' for HSBC)

        Returns:
            Board lot size (100, 200, 400, 500, 1000, 2000, etc.)

        Data Source:
        - KIS Master File (hks.cod): "Bid order size" = lot_size
        - Instant lookup, no API calls required
        - Fallback: Conservative default 500 (mid-range)

        Performance:
        - Instant: No API calls
        - Cached in database for reuse
        """
        try:
            # Get master file manager (lazy import to avoid circular dependency)
            from modules.api_clients.kis_master_file_manager import KISMasterFileManager

            mgr = KISMasterFileManager()

            # Parse HK master file
            df = mgr.parse_market('hks')

            if df.empty:
                logger.warning(f"[{ticker}] HK master file is empty")
                return self._get_default_lot_size('HK')

            # Normalize ticker: Remove .HK suffix and leading zeros for matching
            # Examples: '0700.HK' → '700', '0005.HK' → '5', '9988.HK' → '9988'
            ticker_clean = ticker.replace('.HK', '').replace('.hk', '')
            ticker_normalized = ticker_clean.lstrip('0') or '0'  # Keep '0' if all zeros

            # Find ticker in master file
            matches = df[df['Symbol'].astype(str) == ticker_normalized]

            if matches.empty:
                logger.warning(f"[{ticker}] Not found in master file (normalized: {ticker_normalized})")
                return self._get_default_lot_size('HK')

            # Extract lot_size from "Bid order size" column
            # (In HK market, Bid order size = Ask order size = Board Lot)
            lot_size_raw = matches.iloc[0]['Bid order size']

            try:
                lot_size = int(lot_size_raw)

                # Validate lot_size range
                if self._validate_lot_size(lot_size, 'HK'):
                    logger.debug(f"[{ticker}] Lot_size from master file: {lot_size}")
                    return lot_size
                else:
                    logger.warning(
                        f"[{ticker}] Invalid lot_size from master file: {lot_size}, "
                        f"using default"
                    )
                    return self._get_default_lot_size('HK')

            except (ValueError, TypeError) as e:
                logger.warning(
                    f"[{ticker}] Failed to parse lot_size '{lot_size_raw}': {e}, "
                    f"using default"
                )
                return self._get_default_lot_size('HK')

        except Exception as e:
            logger.warning(f"[{ticker}] Master file lot_size fetch failed: {e}")
            return self._get_default_lot_size('HK')

    def enrich_stock_metadata(self,
                             tickers: Optional[List[str]] = None,
                             force_refresh: bool = False,
                             incremental: bool = False,
                             max_age_days: int = 30) -> Dict:
        """
        Enrich metadata for Hong Kong stocks using hybrid approach (KIS + yfinance)

        Hybrid Strategy:
        1. KIS sector_code mapping → GICS sector (46% instant classification)
        2. yfinance fallback → sector, industry, SPAC/preferred detection (54%)

        Process:
        1. Initialize StockMetadataEnricher with db_manager and kis_api
        2. Query database for HK stocks needing enrichment
        3. Extract sector_codes from KIS master file data
        4. Call enricher.enrich_region() for batch processing
        5. Return RegionEnrichmentResult with summary statistics

        Args:
            tickers: List of tickers to enrich (None = all active HK stocks)
            force_refresh: Skip cache and re-fetch all metadata
            incremental: Only enrich stocks without metadata or stale data
            max_age_days: Max age for incremental mode (default: 30 days)

        Returns:
            Dictionary with enrichment summary:
            {
                'region': 'HK',
                'total_stocks': 1000,
                'enriched_count': 950,
                'failed_count': 50,
                'kis_mapping_count': 460,  # 46% from KIS
                'yfinance_count': 490,     # 54% from yfinance
                'success_rate': 0.95,
                'execution_time': '8.5 minutes'
            }

        Performance:
        - KIS mapping: Instant (46% of stocks)
        - yfinance API: ~540 API calls at 1 req/sec = ~9 minutes
        - Total: ~9 minutes for ~1,000 HK stocks
        """
        from modules.stock_metadata_enricher import StockMetadataEnricher

        logger.info(f"🔍 Enriching metadata for HK stocks...")

        # Initialize enricher with KIS API client
        enricher = StockMetadataEnricher(
            db_manager=self.db,
            kis_api_client=self.kis_api,
            rate_limit=1.0,  # yfinance rate limit: 1 req/sec
            batch_size=100
        )

        # Enrich region (handles incremental mode internally)
        result = enricher.enrich_region(
            region=self.REGION_CODE,
            force_refresh=force_refresh,
            incremental=incremental,
            max_age_days=max_age_days
        )

        # Convert RegionEnrichmentResult to dictionary (field name mapping)
        summary = {
            'region': result.region,
            'total_stocks': result.total_stocks,
            'enriched_count': result.enriched_stocks,          # enriched_stocks → enriched_count
            'failed_count': result.failed_stocks,               # failed_stocks → failed_count
            'kis_mapping_count': result.kis_mapping_used,       # kis_mapping_used → kis_mapping_count
            'yfinance_count': result.yfinance_api_used,         # yfinance_api_used → yfinance_count
            'success_rate': result.enriched_stocks / result.total_stocks if result.total_stocks > 0 else 0.0,
            'execution_time': f"{result.total_elapsed_time:.2f} seconds"  # total_elapsed_time → execution_time
        }

        logger.info(f"✅ HK metadata enrichment complete:")
        logger.info(f"   Total: {summary['total_stocks']} stocks")
        logger.info(f"   Enriched: {summary['enriched_count']} ({summary['success_rate']:.1%})")
        logger.info(f"   KIS mapping: {summary['kis_mapping_count']} (instant)")
        logger.info(f"   yfinance: {summary['yfinance_count']} (API calls)")
        logger.info(f"   Time: {summary['execution_time']}")

        return summary
