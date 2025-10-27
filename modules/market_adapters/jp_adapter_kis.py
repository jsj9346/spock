"""
Japan Market Adapter (KIS API)

Korea Investment & Securities (한국투자증권) 해외주식 API 기반 일본 시장 어댑터
- 한국인 거래 가능 종목만 제공
- Rate limiting: 20 req/sec (yfinance 1 req/sec 대비 20배 빠름)
- Exchange: TSE (Tokyo Stock Exchange)

Key Features:
- Tradable ticker filtering (Korean investors only)
- Fast data collection (20 req/sec vs yfinance 1 req/sec)
- Unified GICS sector classification (TSE 33 Sectors → GICS 11)
- Technical indicator calculation (MA, RSI, MACD, BB, ATR)
- Market calendar integration (JP holidays, lunch break)

Trading Hours: 09:00-11:30, 12:30-15:00 JST (lunch break 11:30-12:30)
Currency: JPY
Ticker Format: 4-digit codes (e.g., "7203" for Toyota)

Author: Spock Trading System
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

from modules.market_adapters.base_adapter import BaseMarketAdapter
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from modules.parsers.jp_stock_parser import JPStockParser
from modules.market_adapters.calendars.market_calendar import MarketCalendar

logger = logging.getLogger(__name__)


class JPAdapterKIS(BaseMarketAdapter):
    """
    Japan market data adapter using KIS API (tradable tickers only)

    Advantages over yfinance adapter:
    - 20x faster data collection (20 req/sec vs 1 req/sec)
    - Only tradable tickers for Korean investors
    - Single API key management (no separate API key)
    - Unified data format across all markets

    Exchange Coverage:
    - TKSE: Tokyo Stock Exchange (TSE)

    Market Characteristics:
    - Trading hours: 09:00-11:30, 12:30-15:00 JST (lunch break)
    - Ticker format: 4-digit codes (e.g., "7203" for Toyota Motor Corp)
    - Currency: JPY
    - Major indices: Nikkei 225, TOPIX

    Data Sources:
    - Primary: KIS API (ticker list, OHLCV)
    - Fallback: yfinance (fundamentals, company info)
    """

    # KIS API exchange code for Japan
    EXCHANGE_CODE = 'TKSE'  # Tokyo Stock Exchange

    REGION_CODE = 'JP'

    def __init__(self,
                 db_manager,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443'):
        """
        Initialize Japan market adapter with KIS API

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
        self.stock_parser = JPStockParser()
        self.calendar = MarketCalendar(region='JP')

        logger.info(f"🇯🇵 JPAdapterKIS initialized (KIS API)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    max_count: Optional[int] = None,
                    use_master_file: bool = True) -> List[Dict]:
        """
        Scan Japan stocks from KIS Master Files or API (tradable tickers only)

        Data Source Priority:
        1. Master File: Instant, ~500-1,000 JP stocks, comprehensive metadata
        2. KIS API: 20 req/sec, real-time data (fallback)

        Process:
        1. Check cache (24-hour TTL) unless force_refresh
        2. Try master file first (instant, no API calls)
        3. Fallback to API if master file unavailable
        4. Parse ticker information with JPStockParser (yfinance)
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
        logger.info(f"🇯🇵 Scanning JP stocks ({'Master File' if use_master_file else 'KIS API'})...")

        # Check cache unless force refresh
        if not force_refresh:
            cached_stocks = self._load_tickers_from_cache(
                asset_type='STOCK',
                ttl_hours=24
            )
            if cached_stocks:
                logger.info(f"✅ Loaded {len(cached_stocks)} JP stocks from cache")
                return cached_stocks

        # Try master file first (instant, comprehensive)
        if use_master_file:
            all_stocks = self._scan_stocks_from_master_file(max_count)
            if all_stocks:
                # Save to database
                logger.info(f"💾 Saving {len(all_stocks)} JP stocks to database...")
                self._save_tickers_to_db(all_stocks, asset_type='STOCK')
                logger.info(f"✅ Master File scan complete: {len(all_stocks)} stocks")
                return all_stocks

            logger.info("⚠️ Master file unavailable, falling back to API method")

        # Fallback to API method (legacy)
        return self._scan_stocks_from_api(max_count)

    def _scan_stocks_from_master_file(self,
                                      max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan JP stocks from master files (instant, no API calls)

        Args:
            max_count: Maximum tickers to return (for testing)

        Returns:
            List of stock dictionaries

        Performance:
        - Instant: No API calls
        - Coverage: ~500-1,000 JP stocks
        """
        try:
            # Get detailed ticker information from master files
            jp_tickers = self.kis_api.get_tickers_with_details(
                region=self.REGION_CODE,
                force_refresh=False
            )

            if not jp_tickers:
                logger.warning("⚠️ No JP tickers from master files")
                return []

            logger.info(f"✅ Master File: {len(jp_tickers)} JP tickers loaded (instant)")

            # Apply max_count if specified
            if max_count:
                jp_tickers = jp_tickers[:max_count]
                logger.info(f"   Limited to {max_count} tickers")

            # Convert master file data to stock dictionaries
            all_stocks = []
            for ticker_data in jp_tickers:
                try:
                    # Fetch lot_size from KIS Master File (JP has variable board lots)
                    lot_size = self._fetch_lot_size(ticker_data['ticker'])

                    # Use master file data directly (no yfinance enrichment required)
                    stock_info = {
                        'ticker': ticker_data['ticker'],
                        'name': ticker_data.get('name', ''),
                        'name_kor': ticker_data.get('name_kor', ''),
                        'exchange': ticker_data.get('exchange', ''),  # From master file
                        'region': self.REGION_CODE,
                        'currency': ticker_data.get('currency', 'JPY'),
                        'asset_type': 'STOCK',
                        'lot_size': lot_size,  # Phase 7: Board lot (ticker-specific)
                        'is_active': True,
                        'kis_exchange_code': ticker_data.get('market_code', '').upper(),
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
        Scan JP stocks from KIS API (legacy method)

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
                    # Fetch lot_size from KIS Master File (JP has variable board lots)
                    lot_size = self._fetch_lot_size(ticker)

                    # Get ticker info from yfinance (for fundamentals)
                    ticker_info = self.stock_parser.parse_ticker_info(ticker)

                    if ticker_info:
                        # Add exchange and region info
                        ticker_info['exchange'] = 'TSE'
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
                logger.warning("⚠️ No JP stocks found")
                return []

            # Save to database
            logger.info(f"💾 Saving {len(all_stocks)} JP stocks to database...")
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
        Scan Japan ETFs from KIS API

        Note: ETF support to be implemented in future phase
        Current implementation returns empty list

        Args:
            force_refresh: Skip cache and fetch fresh data
            max_count: Maximum ETFs to return

        Returns:
            List of ETF dictionaries (empty for now)
        """
        logger.info("📊 JP ETF scanning not yet implemented")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for Japan stocks via KIS API

        Process:
        1. Get ticker list from database (or use provided list)
        2. For each ticker, fetch OHLCV from KIS API
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table
        5. Return success count

        Args:
            tickers: List of tickers (None = all active JP stocks)
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
            logger.warning("⚠️ No JP tickers to collect")
            return 0

        logger.info(f"📈 Collecting OHLCV for {len(tickers)} JP stocks ({days} days)...")

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
        Collect OHLCV data for Japan ETFs

        Note: ETF support to be implemented in future phase

        Args:
            tickers: List of ETF tickers
            days: Historical days to collect

        Returns:
            Number of successfully collected ETFs (0 for now)
        """
        logger.info("📊 JP ETF OHLCV collection not yet implemented")
        return 0

    def collect_fundamentals(self,
                            tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for Japan stocks

        Note: KIS API doesn't provide fundamentals for overseas stocks
        Uses yfinance as fallback data source

        Process:
        1. Get ticker list from database (or use provided list)
        2. Fetch fundamentals from yfinance
        3. Parse with JPStockParser
        4. Save to ticker_fundamentals table

        Args:
            tickers: List of tickers (None = all active JP stocks)

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
            logger.warning("⚠️ No JP tickers for fundamentals")
            return 0

        logger.info(f"💰 Collecting fundamentals for {len(tickers)} JP stocks...")
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
        Add a custom Japan stock ticker to the database

        Args:
            ticker: Stock ticker symbol (e.g., '7203' for Toyota)

        Returns:
            True if successfully added
        """
        logger.info(f"➕ Adding custom JP ticker: {ticker}")

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

            # Fetch lot_size from KIS Master File (JP has variable board lots)
            lot_size = self._fetch_lot_size(ticker)

            # Add exchange and region info
            ticker_info['exchange'] = 'TSE'
            ticker_info['region'] = self.REGION_CODE
            ticker_info['asset_type'] = 'STOCK'
            ticker_info['lot_size'] = lot_size  # Phase 7: Board lot (ticker-specific)
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
        Get Japan market status (open/closed, next open time)

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
                'timezone': 'Asia/Tokyo',
                'trading_hours': '09:00-11:30, 12:30-15:00 JST',
                'lunch_break': '11:30-12:30'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get market status: {e}")
            return {}

    # ========================================
    # LOT SIZE FETCHING (Phase 7: 2025-10-17)
    # ========================================

    def _fetch_lot_size(self, ticker: str) -> int:
        """
        Fetch JP board lot (lot_size) from KIS Master File

        Japan has ticker-specific board lots after 2018 TSE reform:
        - 98.4% use 100 shares/lot (standard post-reform)
        - 1.6% use 1 share/lot (penny stocks, special securities)
        - 0.0% use 1,000 shares/lot (legacy exceptions)

        This is critical for order execution compliance

        Args:
            ticker: Stock ticker (e.g., '7203' for Toyota, '9984' for SoftBank)

        Returns:
            Board lot size (1, 100, or 1000)

        Data Source:
        - KIS Master File (tsemst.cod): "Bid order size" = lot_size
        - Instant lookup, no API calls required
        - Fallback: Conservative default 100 (standard lot)

        Performance:
        - Instant: No API calls
        - Cached in database for reuse
        """
        try:
            # Get master file manager (lazy import to avoid circular dependency)
            from modules.api_clients.kis_master_file_manager import KISMasterFileManager

            mgr = KISMasterFileManager()

            # Parse JP master file
            df = mgr.parse_market('tse')

            if df.empty:
                logger.warning(f"[{ticker}] JP master file is empty")
                return self._get_default_lot_size('JP')

            # Normalize ticker: Remove leading zeros for matching
            # Examples: '7203' → '7203', '0700' → '700', '005930' → '5930'
            ticker_normalized = ticker.lstrip('0') or '0'  # Keep '0' if all zeros

            # Find ticker in master file
            matches = df[df['Symbol'].astype(str) == ticker_normalized]

            if matches.empty:
                # Try with original ticker (some tickers may have leading zeros preserved)
                matches = df[df['Symbol'].astype(str) == ticker]

            if matches.empty:
                logger.warning(f"[{ticker}] Not found in master file (normalized: {ticker_normalized})")
                return self._get_default_lot_size('JP')

            # Extract lot_size from "Bid order size" column
            # (In JP market, Bid order size = Board Lot after 2018 reform)
            lot_size_raw = matches.iloc[0]['Bid order size']

            try:
                lot_size = int(lot_size_raw)

                # Validate lot_size range (JP allows 1, 100, 1000, 10000)
                if self._validate_lot_size(lot_size, 'JP'):
                    logger.debug(f"[{ticker}] Lot_size from master file: {lot_size}")
                    return lot_size
                else:
                    logger.warning(
                        f"[{ticker}] Invalid lot_size from master file: {lot_size}, "
                        f"using default"
                    )
                    return self._get_default_lot_size('JP')

            except (ValueError, TypeError) as e:
                logger.warning(
                    f"[{ticker}] Failed to parse lot_size '{lot_size_raw}': {e}, "
                    f"using default"
                )
                return self._get_default_lot_size('JP')

        except Exception as e:
            logger.warning(f"[{ticker}] Master file lot_size fetch failed: {e}")
            return self._get_default_lot_size('JP')

    def enrich_stock_metadata(self,
                             tickers: Optional[List[str]] = None,
                             force_refresh: bool = False,
                             incremental: bool = False,
                             max_age_days: int = 30) -> Dict:
        """
        Enrich metadata for Japan stocks using hybrid approach (KIS + yfinance)

        Hybrid Strategy:
        1. KIS sector_code mapping → GICS sector (46% instant classification)
        2. yfinance fallback → sector, industry, SPAC/preferred detection (54%)

        Process:
        1. Initialize StockMetadataEnricher with db_manager and kis_api
        2. Query database for JP stocks needing enrichment
        3. Extract sector_codes from KIS master file data
        4. Call enricher.enrich_region() for batch processing
        5. Return RegionEnrichmentResult with summary statistics

        Args:
            tickers: List of tickers to enrich (None = all active JP stocks)
            force_refresh: Skip cache and re-fetch all metadata
            incremental: Only enrich stocks without metadata or stale data
            max_age_days: Max age for incremental mode (default: 30 days)

        Returns:
            Dictionary with enrichment summary:
            {
                'region': 'JP',
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
        - Total: ~9 minutes for ~1,000 JP stocks
        """
        from modules.stock_metadata_enricher import StockMetadataEnricher

        logger.info(f"🔍 Enriching metadata for JP stocks...")

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

        logger.info(f"✅ JP metadata enrichment complete:")
        logger.info(f"   Total: {summary['total_stocks']} stocks")
        logger.info(f"   Enriched: {summary['enriched_count']} ({summary['success_rate']:.1%})")
        logger.info(f"   KIS mapping: {summary['kis_mapping_count']} (instant)")
        logger.info(f"   yfinance: {summary['yfinance_count']} (API calls)")
        logger.info(f"   Time: {summary['execution_time']}")

        return summary
