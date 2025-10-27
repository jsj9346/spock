"""
US Market Adapter (KIS API)

Korea Investment & Securities (한국투자증권) 해외주식 API 기반 미국 시장 어댑터
- 한국인 거래 가능 종목만 제공 (~3,000 stocks)
- Rate limiting: 20 req/sec (Polygon.io 5 req/min 대비 240배 빠름)
- Exchange support: NYSE, NASDAQ, AMEX

Key Features:
- Tradable ticker filtering (Korean investors only)
- Fast data collection (20 req/sec vs Polygon.io 5 req/min)
- Unified GICS sector classification
- Technical indicator calculation (MA, RSI, MACD, BB, ATR)
- Market calendar integration (US holidays, trading hours)

Author: Spock Trading System
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd

from modules.market_adapters.base_adapter import BaseMarketAdapter
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from modules.parsers.us_stock_parser import USStockParser
from modules.market_adapters.calendars.market_calendar import MarketCalendar

logger = logging.getLogger(__name__)


class USAdapterKIS(BaseMarketAdapter):
    """
    US market data adapter using KIS API (tradable tickers only)

    Advantages over Polygon.io adapter:
    - 240x faster data collection (20 req/sec vs 5 req/min)
    - Only tradable tickers for Korean investors (~3,000 vs ~8,000)
    - Single API key management (no separate Polygon.io key)
    - Unified data format across all markets

    Exchange Coverage:
    - NASD: NASDAQ stocks
    - NYSE: New York Stock Exchange stocks
    - AMEX: American Stock Exchange stocks

    Data Sources:
    - Primary: KIS API (ticker list, OHLCV)
    - Fallback: yfinance (fundamentals, company info)
    """

    # KIS API exchange codes for US markets
    EXCHANGE_CODES = ['NASD', 'NYSE', 'AMEX']

    # Exchange name mapping
    EXCHANGE_NAMES = {
        'NASD': 'NASDAQ',
        'NYSE': 'NYSE',
        'AMEX': 'AMEX'
    }

    REGION_CODE = 'US'

    def __init__(self,
                 db_manager,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443'):
        """
        Initialize US market adapter with KIS API

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
        self.stock_parser = USStockParser()
        self.calendar = MarketCalendar(region='US')

        logger.info(f"📊 USAdapterKIS initialized (KIS API)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    exchanges: Optional[List[str]] = None,
                    max_count: Optional[int] = None,
                    use_master_file: bool = True) -> List[Dict]:
        """
        Scan US stocks from KIS Master Files or API (tradable tickers only)

        Data Source Priority:
        1. Master File: Instant, 6,527 US stocks, comprehensive metadata
        2. KIS API: 20 req/sec, real-time data (fallback)

        Process:
        1. Check cache (24-hour TTL) unless force_refresh
        2. Try master file first (instant, no API calls)
        3. Fallback to API if master file unavailable
        4. Parse ticker information with USStockParser (yfinance)
        5. Save to database (tickers + stock_details tables)
        6. Return list of stock dictionaries

        Args:
            force_refresh: Skip cache and fetch fresh data
            exchanges: List of exchange codes to scan (default: all)
            max_count: Maximum tickers per exchange (for testing)
            use_master_file: Try master file first (default: True)

        Returns:
            List of stock dictionaries with ticker, name, sector, etc.

        Performance:
        - Master File: Instant (no API calls), 6,527 stocks
        - API Method: ~2.5 minutes (20 req/sec), ~3,000 stocks
        - 240x faster than Polygon.io (5 req/min)
        """
        logger.info(f"📊 Scanning US stocks ({'Master File' if use_master_file else 'KIS API'})...")

        # Check cache unless force refresh
        if not force_refresh:
            cached_stocks = self._load_tickers_from_cache(
                asset_type='STOCK',
                ttl_hours=24
            )
            if cached_stocks:
                logger.info(f"✅ Loaded {len(cached_stocks)} US stocks from cache")
                return cached_stocks

        # Try master file first (instant, comprehensive)
        if use_master_file:
            all_stocks = self._scan_stocks_from_master_file(exchanges, max_count)
            if all_stocks:
                # Save to database
                logger.info(f"💾 Saving {len(all_stocks)} US stocks to database...")
                self._save_tickers_to_db(all_stocks, asset_type='STOCK')

                # Log exchange breakdown
                self._log_exchange_breakdown(all_stocks)
                return all_stocks

            logger.info("⚠️ Master file unavailable, falling back to API method")

        # Fallback to API method (legacy)
        return self._scan_stocks_from_api(exchanges, max_count)

    def _scan_stocks_from_master_file(self,
                                      exchanges: Optional[List[str]] = None,
                                      max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan US stocks from master files (instant, no API calls)

        Args:
            exchanges: List of exchange codes to scan (default: all)
            max_count: Maximum tickers per exchange (for testing)

        Returns:
            List of stock dictionaries

        Performance:
        - Instant: No API calls
        - Coverage: 6,527 US stocks (NASDAQ 3,813, NYSE 2,453, AMEX 262)
        """
        try:
            # Get detailed ticker information from master files
            us_tickers = self.kis_api.get_tickers_with_details(
                region=self.REGION_CODE,
                force_refresh=False
            )

            if not us_tickers:
                logger.warning("⚠️ No US tickers from master files")
                return []

            logger.info(f"✅ Master File: {len(us_tickers)} US tickers loaded (instant)")

            # Filter by exchanges if specified
            if exchanges:
                # Map KIS API exchange codes to exchange names
                exchange_names = [self.EXCHANGE_NAMES.get(code, code) for code in exchanges]
                us_tickers = [t for t in us_tickers if t.get('exchange') in exchange_names]
                logger.info(f"   Filtered to {len(us_tickers)} tickers for exchanges: {exchange_names}")

            # Apply max_count per exchange if specified
            if max_count:
                limited_tickers = []
                exchange_counts = {}
                for ticker in us_tickers:
                    exchange = ticker.get('exchange', 'Unknown')
                    count = exchange_counts.get(exchange, 0)
                    if count < max_count:
                        limited_tickers.append(ticker)
                        exchange_counts[exchange] = count + 1
                us_tickers = limited_tickers
                logger.info(f"   Limited to {max_count} tickers per exchange: {len(us_tickers)} total")

            # Convert master file data to stock dictionaries
            all_stocks = []
            for ticker_data in us_tickers:
                try:
                    # Use master file data directly (no yfinance enrichment required)
                    stock_info = {
                        'ticker': ticker_data['ticker'],
                        'name': ticker_data.get('name', ''),
                        'name_kor': ticker_data.get('name_kor', ''),
                        'exchange': ticker_data.get('exchange', ''),
                        'region': self.REGION_CODE,
                        'currency': ticker_data.get('currency', 'USD'),
                        'asset_type': 'STOCK',
                        'lot_size': 1,  # US: 1 share per lot
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
                             exchanges: Optional[List[str]] = None,
                             max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan US stocks from KIS API (legacy method)

        Args:
            exchanges: List of exchange codes to scan (default: all)
            max_count: Maximum tickers per exchange (for testing)

        Returns:
            List of stock dictionaries

        Performance:
        - ~2.5 minutes for ~3,000 stocks (20 req/sec)
        """
        # Determine exchanges to scan
        target_exchanges = exchanges if exchanges else self.EXCHANGE_CODES

        all_stocks = []
        for exchange_code in target_exchanges:
            try:
                logger.info(f"📡 Fetching tradable tickers from {exchange_code} (API)...")

                # Fetch tradable tickers from KIS API (use_master_file=False)
                tickers = self.kis_api.get_tradable_tickers(
                    exchange_code=exchange_code,
                    max_count=max_count,
                    use_master_file=False  # Force API method
                )

                if not tickers:
                    logger.warning(f"⚠️ No tickers returned for {exchange_code}")
                    continue

                logger.info(f"✅ {exchange_code}: {len(tickers)} tradable tickers")

                # Parse each ticker
                for ticker in tickers:
                    try:
                        # Get ticker info from yfinance (for fundamentals)
                        ticker_info = self.stock_parser.parse_ticker_info(ticker)

                        if ticker_info:
                            # Add exchange and region info
                            ticker_info['exchange'] = self.EXCHANGE_NAMES[exchange_code]
                            ticker_info['region'] = self.REGION_CODE
                            ticker_info['asset_type'] = 'STOCK'
                            ticker_info['lot_size'] = 1  # US: 1 share per lot
                            ticker_info['is_active'] = True
                            ticker_info['kis_exchange_code'] = exchange_code

                            all_stocks.append(ticker_info)

                    except Exception as e:
                        logger.debug(f"⚠️ Failed to parse {ticker}: {e}")
                        continue

            except Exception as e:
                logger.error(f"❌ Failed to scan {exchange_code}: {e}")
                continue

        if not all_stocks:
            logger.warning("⚠️ No US stocks found")
            return []

        # Save to database
        logger.info(f"💾 Saving {len(all_stocks)} US stocks to database...")
        self._save_tickers_to_db(all_stocks, asset_type='STOCK')

        logger.info(f"✅ API scan complete: {len(all_stocks)} stocks")

        # Log exchange breakdown
        self._log_exchange_breakdown(all_stocks)
        return all_stocks

    def _log_exchange_breakdown(self, stocks: List[Dict]):
        """Log exchange breakdown statistics"""
        exchange_counts = {}
        for stock in stocks:
            exchange = stock.get('exchange', 'Unknown')
            exchange_counts[exchange] = exchange_counts.get(exchange, 0) + 1

        for exchange, count in exchange_counts.items():
            logger.info(f"   {exchange}: {count} stocks")

    def scan_etfs(self,
                  force_refresh: bool = False,
                  max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan US ETFs from KIS API

        Note: ETF support to be implemented in future phase
        Current implementation returns empty list

        Args:
            force_refresh: Skip cache and fetch fresh data
            max_count: Maximum ETFs to return

        Returns:
            List of ETF dictionaries (empty for now)
        """
        logger.info("📊 US ETF scanning not yet implemented")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for US stocks via KIS API

        Process:
        1. Get ticker list from database (or use provided list)
        2. For each ticker, fetch OHLCV from KIS API
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table
        5. Return success count

        Args:
            tickers: List of tickers (None = all active US stocks)
            days: Historical days to collect (default: 250)

        Returns:
            Number of successfully collected tickers

        Performance:
        - Rate limit: 20 req/sec
        - ~3,000 stocks: ~2.5 minutes
        - 240x faster than Polygon.io
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
            logger.warning("⚠️ No US tickers to collect")
            return 0

        logger.info(f"📈 Collecting OHLCV for {len(tickers)} US stocks ({days} days)...")

        success_count = 0
        for i, ticker in enumerate(tickers, 1):
            try:
                # Get ticker's exchange code from database
                ticker_info = self.db.get_tickers(ticker=ticker)
                if not ticker_info:
                    logger.warning(f"⚠️ [{ticker}] Not found in database")
                    continue

                exchange_code = ticker_info[0].get('kis_exchange_code', 'NASD')

                # Fetch OHLCV from KIS API
                logger.info(f"📊 [{i}/{len(tickers)}] {ticker} ({exchange_code})...")

                ohlcv_df = self.kis_api.get_ohlcv(
                    ticker=ticker,
                    exchange_code=exchange_code,
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
        Collect OHLCV data for US ETFs

        Note: ETF support to be implemented in future phase

        Args:
            tickers: List of ETF tickers
            days: Historical days to collect

        Returns:
            Number of successfully collected ETFs (0 for now)
        """
        logger.info("📊 US ETF OHLCV collection not yet implemented")
        return 0

    def collect_fundamentals(self,
                            tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for US stocks

        Note: KIS API doesn't provide fundamentals for overseas stocks
        Uses yfinance as fallback data source

        Process:
        1. Get ticker list from database (or use provided list)
        2. Fetch fundamentals from yfinance
        3. Parse with USStockParser
        4. Save to ticker_fundamentals table

        Args:
            tickers: List of tickers (None = all active US stocks)

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
            logger.warning("⚠️ No US tickers for fundamentals")
            return 0

        logger.info(f"💰 Collecting fundamentals for {len(tickers)} US stocks...")
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

    def add_custom_ticker(self, ticker: str, exchange_code: str = 'NASD') -> bool:
        """
        Add a custom US stock ticker to the database

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            exchange_code: KIS exchange code (NASD, NYSE, AMEX)

        Returns:
            True if successfully added
        """
        logger.info(f"➕ Adding custom US ticker: {ticker} ({exchange_code})")

        try:
            # Validate exchange code
            if exchange_code not in self.EXCHANGE_CODES:
                logger.error(f"❌ Invalid exchange code: {exchange_code}")
                return False

            # Check if ticker is tradable via KIS API
            tradable_tickers = self.kis_api.get_tradable_tickers(
                exchange_code=exchange_code,
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
            ticker_info['exchange'] = self.EXCHANGE_NAMES[exchange_code]
            ticker_info['region'] = self.REGION_CODE
            ticker_info['asset_type'] = 'STOCK'
            ticker_info['lot_size'] = 1  # US: 1 share per lot
            ticker_info['is_active'] = True
            ticker_info['kis_exchange_code'] = exchange_code

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
        Get US market status (open/closed, next open time)

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
                'timezone': 'America/New_York',
                'trading_hours': '09:30-16:00 ET'
            }
        except Exception as e:
            logger.error(f"❌ Failed to get market status: {e}")
            return {}

    def enrich_stock_metadata(self,
                             tickers: Optional[List[str]] = None,
                             force_refresh: bool = False,
                             incremental: bool = False,
                             max_age_days: int = 30) -> Dict:
        """
        Enrich metadata for US stocks using hybrid approach (KIS + yfinance)

        Hybrid Strategy:
        1. KIS sector_code mapping → GICS sector (46% instant classification)
        2. yfinance fallback → sector, industry, SPAC/preferred detection (54%)

        Process:
        1. Initialize StockMetadataEnricher with db_manager and kis_api
        2. Query database for stocks needing enrichment
        3. Extract sector_codes from KIS master file data
        4. Call enricher.enrich_region() for batch processing
        5. Return RegionEnrichmentResult with summary statistics

        Args:
            tickers: List of tickers to enrich (None = all active US stocks)
            force_refresh: Skip cache and re-fetch all metadata
            incremental: Only enrich stocks without metadata or stale data
            max_age_days: Max age for incremental mode (default: 30 days)

        Returns:
            Dictionary with enrichment summary:
            {
                'region': 'US',
                'total_stocks': 3000,
                'enriched_count': 2850,
                'failed_count': 150,
                'kis_mapping_count': 1380,  # 46% from KIS
                'yfinance_count': 1470,      # 54% from yfinance
                'success_rate': 0.95,
                'execution_time': '15.2 minutes'
            }

        Performance:
        - KIS mapping: Instant (46% of stocks)
        - yfinance API: ~1,620 API calls at 1 req/sec = ~27 minutes
        - Total: ~27 minutes for ~3,000 US stocks
        """
        from modules.stock_metadata_enricher import StockMetadataEnricher

        logger.info(f"🔍 Enriching metadata for US stocks...")

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

        # Convert RegionEnrichmentResult to dictionary
        summary = {
            'region': result.region,
            'total_stocks': result.total_stocks,
            'enriched_count': result.enriched_count,
            'failed_count': result.failed_count,
            'kis_mapping_count': result.kis_mapping_count,
            'yfinance_count': result.yfinance_count,
            'success_rate': result.success_rate,
            'execution_time': f"{result.execution_time:.2f} seconds"
        }

        logger.info(f"✅ US metadata enrichment complete:")
        logger.info(f"   Total: {summary['total_stocks']} stocks")
        logger.info(f"   Enriched: {summary['enriched_count']} ({summary['success_rate']:.1%})")
        logger.info(f"   KIS mapping: {summary['kis_mapping_count']} (instant)")
        logger.info(f"   yfinance: {summary['yfinance_count']} (API calls)")
        logger.info(f"   Time: {summary['execution_time']}")

        return summary
