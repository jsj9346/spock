"""
US Market Adapter (USAdapter)

Handles US stock market data collection from Polygon.io API.

Data Sources:
- Polygon.io REST API: Primary data source (free tier: 5 req/min)
- Yahoo Finance: Fallback data source (optional)

Markets Covered:
- NYSE (New York Stock Exchange)
- NASDAQ (NASDAQ Stock Market)
- AMEX (American Stock Exchange)

Author: Spock Trading System
"""

import logging
import time
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from .base_adapter import BaseMarketAdapter
from ..api_clients.polygon_api import PolygonAPI
from ..parsers.us_stock_parser import USStockParser
from ..market_adapters.sector_mappers.gics_mapper import GICSSectorMapper
from ..market_adapters.calendars.market_calendar import MarketCalendar

logger = logging.getLogger(__name__)


class USAdapter(BaseMarketAdapter):
    """
    US market data adapter

    Handles:
    1. Stock/ETF scanning via Polygon.io API
    2. OHLCV collection via Polygon.io aggregates API
    3. Company fundamentals (market cap, sector, employees)
    4. GICS sector classification from SIC codes
    """

    # US exchanges
    EXCHANGES = {
        'XNYS': 'NYSE',
        'XNAS': 'NASDAQ',
        'XASE': 'AMEX'
    }

    def __init__(self, db_manager, polygon_api_key: str):
        """
        Initialize US adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
            polygon_api_key: Polygon.io API key (free tier supported)
        """
        super().__init__(db_manager, region_code='US')

        # API clients
        self.polygon_api = PolygonAPI(api_key=polygon_api_key, rate_limit_per_minute=5)

        # Parsers
        self.stock_parser = USStockParser()

        # Sector mapper (GICS is native for US market)
        self.sector_mapper = GICSSectorMapper()

        # Market calendar
        self.calendar = MarketCalendar(region='US', holidays_file='config/holidays/us_holidays.yaml')

        logger.info(f"✅ [US] USAdapter initialized (Polygon.io free tier: 5 req/min)")

    # ========================================
    # PHASE 1: TICKER DISCOVERY (SCANNING)
    # ========================================

    def scan_stocks(self,
                   force_refresh: bool = False,
                   exchanges: Optional[List[str]] = None) -> List[Dict]:
        """
        Scan US stocks from Polygon.io API

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from Polygon.io (paginated, all exchanges)
        3. Parse and normalize with USStockParser
        4. Filter common stocks only (exclude ETFs, preferred stocks)
        5. Enrich with GICS sectors from SIC codes
        6. Save to tickers + stock_details tables

        Args:
            force_refresh: Ignore cache and force refresh
            exchanges: List of exchange codes (None = all US exchanges)

        Returns:
            List of stock ticker dictionaries

        Note:
            - ~8,000 US common stocks total (NYSE + NASDAQ + AMEX)
            - Polygon.io free tier: 5 req/min, pagination handled automatically
            - Estimated time: ~5 minutes for full scan (pagination)
        """
        # Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='STOCK', ttl_hours=24)
            if cached:
                logger.info(f"✅ [US] Using cached stock list: {len(cached)} stocks")
                return cached

        logger.info(f"🔍 [US] Scanning stocks from Polygon.io API...")

        # Default to all US exchanges
        if exchanges is None:
            exchanges = list(self.EXCHANGES.keys())

        all_stocks = []

        # Fetch from each exchange
        for exchange_code in exchanges:
            exchange_name = self.EXCHANGES.get(exchange_code, exchange_code)
            logger.info(f"📡 [US] Fetching {exchange_name} stocks...")

            try:
                # Fetch stock list from Polygon.io (paginated)
                raw_stocks = self.polygon_api.get_stock_list(
                    exchange=exchange_code,
                    active=True,
                    limit=1000  # Max per page
                )

                if not raw_stocks:
                    logger.warning(f"⚠️ [US] No stocks found for {exchange_name}")
                    continue

                # Parse with USStockParser
                parsed_stocks = self.stock_parser.parse_ticker_list(raw_stocks)
                logger.info(f"✅ [US] {exchange_name}: {len(parsed_stocks)} stocks parsed")

                all_stocks.extend(parsed_stocks)

            except Exception as e:
                logger.error(f"❌ [US] {exchange_name} scan failed: {e}")
                continue

        if not all_stocks:
            logger.error(f"❌ [US] Stock scanning failed for all exchanges")
            return []

        logger.info(f"📊 [US] Total stocks fetched: {len(all_stocks)}")

        # Filter common stocks only (exclude ETFs, preferred stocks, etc.)
        common_stocks = self.stock_parser.filter_common_stocks(all_stocks)
        logger.info(f"🔍 [US] Filtered to {len(common_stocks)} common stocks")

        # Enrich with company details (sector, market cap) for top stocks
        # Note: Rate limited to 5 req/min, so only enrich subset
        enriched_stocks = self._enrich_with_fundamentals(
            common_stocks,
            max_count=100  # Top 100 by market cap or alphabetically
        )

        # Save to database
        if enriched_stocks:
            self._save_tickers_to_db(enriched_stocks, asset_type='STOCK')

        logger.info(f"✅ [US] Stock scanning complete: {len(enriched_stocks)} stocks saved to DB")
        return enriched_stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan US ETFs from Polygon.io API

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from Polygon.io (all exchanges)
        3. Parse and normalize
        4. Filter ETFs only (asset_type='ETF')
        5. Save to tickers + etf_details tables

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ETF ticker dictionaries
        """
        # Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='ETF', ttl_hours=24)
            if cached:
                logger.info(f"✅ [US] Using cached ETF list: {len(cached)} ETFs")
                return cached

        logger.info(f"🔍 [US] Scanning ETFs from Polygon.io API...")

        try:
            # Fetch all US tickers (includes ETFs)
            raw_tickers = self.polygon_api.get_stock_list(active=True, limit=1000)

            if not raw_tickers:
                logger.warning(f"⚠️ [US] No tickers found")
                return []

            # Parse all tickers
            parsed_tickers = self.stock_parser.parse_ticker_list(raw_tickers)

            # Filter ETFs only (asset_type_code='ETF')
            etfs = [t for t in parsed_tickers if t.get('asset_type_code') == 'ETF']

            logger.info(f"✅ [US] Polygon.io: {len(etfs)} ETFs found")

            # Save to database
            if etfs:
                self._save_tickers_to_db(etfs, asset_type='ETF')

            return etfs

        except Exception as e:
            logger.error(f"❌ [US] ETF scanning failed: {e}")
            return []

    def _enrich_with_fundamentals(self,
                                  stocks: List[Dict],
                                  max_count: int = 100) -> List[Dict]:
        """
        Enrich stocks with fundamental data from Polygon.io

        Args:
            stocks: List of stock dictionaries
            max_count: Maximum number of stocks to enrich (rate limit consideration)

        Returns:
            Enriched stock list with sector, market cap, etc.

        Note:
            - Rate limited to 5 req/min (12 seconds between calls)
            - Only enriches top N stocks to respect free tier limits
        """
        logger.info(f"📊 [US] Enriching top {max_count} stocks with fundamentals...")

        enriched_stocks = []

        for idx, stock in enumerate(stocks[:max_count], 1):
            ticker = stock.get('ticker')

            try:
                # Fetch company details from Polygon.io
                details = self.polygon_api.get_ticker_details(ticker)

                if details:
                    # Parse details
                    parsed_details = self.stock_parser.parse_ticker_details(details)

                    if parsed_details:
                        # Merge parsed details into stock data
                        stock.update({
                            'sector': parsed_details.get('sector'),
                            'industry': parsed_details.get('industry'),
                            'market_cap': parsed_details.get('market_cap'),
                            'shares_outstanding': parsed_details.get('shares_outstanding'),
                            'description': parsed_details.get('description'),
                            'homepage_url': parsed_details.get('homepage_url'),
                            'total_employees': parsed_details.get('total_employees')
                        })

                        logger.info(f"✅ [{ticker}] Enriched ({idx}/{max_count}): {parsed_details.get('sector')}")

                enriched_stocks.append(stock)

            except Exception as e:
                logger.warning(f"⚠️ [{ticker}] Enrichment failed: {e}")
                enriched_stocks.append(stock)  # Keep stock even if enrichment fails

        logger.info(f"✅ [US] Enriched {len(enriched_stocks)}/{max_count} stocks")
        return enriched_stocks + stocks[max_count:]  # Add remaining unenriched stocks

    # ========================================
    # PHASE 2: OHLCV DATA COLLECTION
    # ========================================

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for US stocks via Polygon.io aggregates API

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Batch processing with rate limiting (5 req/min)
        3. Fetch OHLCV from Polygon.io
        4. Parse with USStockParser
        5. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        6. Save to ohlcv_data table

        Args:
            tickers: List of ticker symbols (None = all active US stocks)
            days: Historical days to collect (default: 250 for MA200)

        Returns:
            Number of stocks successfully updated

        Note:
            - Rate limit: 5 req/min = ~300 stocks/hour
            - Estimated time for 100 stocks: ~20 minutes
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='US', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [US] No stocks to collect")
            return 0

        logger.info(f"📊 [US] Collecting OHLCV for {len(tickers)} stocks ({days} days)...")
        logger.info(f"⏱️ [US] Estimated time: {len(tickers) * 12 / 60:.1f} minutes (5 req/min)")

        success_count = 0
        start_time = time.time()

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch OHLCV from Polygon.io
                raw_ohlcv = self.polygon_api.get_daily_ohlcv_last_n_days(ticker, days=days)

                if not raw_ohlcv:
                    logger.warning(f"⚠️ [{ticker}] No OHLCV data ({idx}/{len(tickers)})")
                    continue

                # Parse to DataFrame
                ohlcv_df = self.stock_parser.parse_ohlcv_data(raw_ohlcv, ticker)

                if ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] Parsing failed ({idx}/{len(tickers)})")
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')

                success_count += 1
                elapsed = time.time() - start_time
                eta = (elapsed / idx) * (len(tickers) - idx)

                logger.info(f"✅ [{ticker}] OHLCV collected ({idx}/{len(tickers)}, "
                          f"ETA: {eta/60:.1f} min)")

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")
                continue

        logger.info(f"✅ [US] OHLCV collection complete: {success_count}/{len(tickers)} stocks updated")
        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for US ETFs via Polygon.io

        Similar workflow to collect_stock_ohlcv() but for ETFs

        Args:
            tickers: List of ETF ticker symbols
            days: Historical days to collect

        Returns:
            Number of ETFs successfully updated
        """
        # Get ETF ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='US', asset_type='ETF', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [US] No ETFs to collect")
            return 0

        logger.info(f"📊 [US] Collecting OHLCV for {len(tickers)} ETFs...")

        # Reuse stock OHLCV collection logic (same API endpoints)
        return self.collect_stock_ohlcv(tickers=tickers, days=days)

    # ========================================
    # PHASE 3: ENHANCED DATA (OPTIONAL)
    # ========================================

    def collect_fundamentals(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect company fundamentals for US stocks

        Fetches from Polygon.io:
        - Company description, homepage, employees
        - Market cap, shares outstanding
        - SIC code → GICS sector mapping

        Args:
            tickers: List of ticker symbols (None = all stocks)

        Returns:
            Number of stocks successfully updated

        Note:
            - Rate limited to 5 req/min
            - Recommended: collect for subset of stocks (e.g., top 500 by volume)
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='US', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in ticker_data[:500]]  # Limit to top 500

        if not tickers:
            logger.warning(f"⚠️ [US] No stocks for fundamentals collection")
            return 0

        logger.info(f"📊 [US] Collecting fundamentals for {len(tickers)} stocks...")
        logger.info(f"⏱️ [US] Estimated time: {len(tickers) * 12 / 60:.1f} minutes")

        success_count = 0

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch company details
                details = self.polygon_api.get_ticker_details(ticker)

                if not details:
                    logger.warning(f"⚠️ [{ticker}] No details found ({idx}/{len(tickers)})")
                    continue

                # Parse details
                parsed_details = self.stock_parser.parse_ticker_details(details)

                if not parsed_details:
                    logger.warning(f"⚠️ [{ticker}] Parsing failed ({idx}/{len(tickers)})")
                    continue

                # Save to database (custom table for fundamentals)
                self._save_fundamentals_to_db(ticker, parsed_details)

                success_count += 1
                logger.info(f"✅ [{ticker}] Fundamentals collected ({idx}/{len(tickers)})")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Fundamentals collection failed: {e}")
                continue

        logger.info(f"✅ [US] Fundamentals collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    # ========================================
    # HELPER METHODS
    # ========================================

    def _save_fundamentals_to_db(self, ticker: str, details: Dict):
        """
        Save company fundamentals to database

        Args:
            ticker: Stock ticker symbol
            details: Parsed company details dictionary
        """
        # TODO: Implement database save logic
        # For now, just log the data
        logger.debug(f"[{ticker}] Fundamentals: {details.keys()}")

    def check_market_status(self) -> Dict:
        """
        Check if US market is currently open

        Returns:
            Market status dictionary with is_open, time_until_close, etc.
        """
        return self.calendar.get_market_status()
