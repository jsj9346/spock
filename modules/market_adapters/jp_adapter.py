"""
Japan Market Adapter - TSE Stock Market Integration

Handles ticker discovery, OHLCV collection, and fundamentals for Japanese stocks.

Data Source: yfinance (Yahoo Finance)
Market: Tokyo Stock Exchange (TSE)
Trading Hours: 09:00-11:30, 12:30-15:00 JST
Currency: JPY

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_adapter import BaseMarketAdapter
from ..api_clients.yfinance_api import YFinanceAPI
from ..parsers.jp_stock_parser import JPStockParser

logger = logging.getLogger(__name__)


class JPAdapter(BaseMarketAdapter):
    """
    Japan market adapter using yfinance

    Features:
    - Nikkei 225 constituents + TOPIX Core 30
    - OHLCV data collection (250-day history)
    - Company fundamentals
    - TSE holiday calendar support

    Usage:
        db = SQLiteDatabaseManager()
        adapter = JPAdapter(db)
        stocks = adapter.scan_stocks(force_refresh=True)
        adapter.collect_stock_ohlcv(days=250)
    """

    # Nikkei 225 major constituents + TOPIX Core 30 (sample list)
    # Top companies by market capitalization and sector representation
    DEFAULT_JP_TICKERS = [
        # Top 10 by Market Cap
        '7203',  # Toyota Motor
        '6758',  # Sony Group
        '9984',  # SoftBank Group
        '6861',  # Keyence
        '6501',  # Hitachi
        '8306',  # Mitsubishi UFJ Financial
        '9432',  # NTT (Nippon Telegraph & Telephone)
        '9433',  # KDDI
        '4502',  # Takeda Pharmaceutical
        '8035',  # Tokyo Electron

        # Auto & Transportation
        '7267',  # Honda Motor
        '7201',  # Nissan Motor
        '7269',  # Suzuki Motor
        '9201',  # Japan Airlines
        '9202',  # ANA Holdings

        # Technology & Electronics
        '6902',  # Denso
        '6594',  # Nidec
        '6857',  # Advantest
        '8035',  # Tokyo Electron
        '6920',  # Lasertec
        '4063',  # Shin-Etsu Chemical

        # Trading Companies (Sogo Shosha)
        '8058',  # Mitsubishi Corporation
        '8031',  # Mitsui & Co
        '8001',  # Itochu
        '8002',  # Marubeni
        '8053',  # Sumitomo Corporation

        # Financials
        '8316',  # Sumitomo Mitsui Financial
        '8411',  # Mizuho Financial
        '8604',  # Nomura Holdings
        '8750',  # Dai-ichi Life Holdings
        '8725',  # MS&AD Insurance

        # Consumer & Retail
        '9983',  # Fast Retailing (Uniqlo)
        '3382',  # Seven & i Holdings
        '4452',  # Kao
        '2503',  # Kirin Holdings
        '2502',  # Asahi Group Holdings
        '2801',  # Kikkoman
        '4911',  # Shiseido

        # Healthcare & Pharmaceuticals
        '4568',  # Daiichi Sankyo
        '4503',  # Astellas Pharma
        '4523',  # Eisai
        '6367',  # Daikin Industries
        '7974',  # Nintendo

        # Industrials & Manufacturing
        '6301',  # Komatsu
        '6954',  # Fanuc
        '6971',  # Kyocera
        '6702',  # Fujitsu
        '6503',  # Mitsubishi Electric

        # Materials & Chemicals
        '4042',  # Tosoh
        '4188',  # Mitsubishi Chemical
        '5401',  # Nippon Steel
        '5411',  # JFE Holdings
        '4043',  # Tokuyama

        # Real Estate
        '8801',  # Mitsui Fudosan
        '8802',  # Mitsubishi Estate
        '8830',  # Sumitomo Realty & Development

        # Utilities
        '9501',  # Tokyo Electric Power
        '9502',  # Chubu Electric Power
        '9503',  # Kansai Electric Power
        '9532',  # Osaka Gas

        # Communication Services
        '4689',  # Yahoo Japan (Z Holdings)
        '9434',  # SoftBank
        '4755',  # Rakuten Group
        '6098',  # Recruit Holdings
    ]

    def __init__(self, db_manager):
        """
        Initialize Japan adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
        """
        super().__init__(db_manager, region_code='JP')

        self.yfinance_api = YFinanceAPI(rate_limit_per_second=1.0)
        self.stock_parser = JPStockParser()

        logger.info("🇯🇵 JPAdapter initialized (yfinance data source)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    ticker_list: Optional[List[str]] = None,
                    max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan Japanese stocks and populate database

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from yfinance
        3. Parse and validate
        4. Filter common stocks (exclude REITs)
        5. Save to database

        Args:
            force_refresh: Ignore cache and fetch fresh data
            ticker_list: Custom ticker list (None = use DEFAULT_JP_TICKERS)
            max_count: Max stocks to scan (for testing)

        Returns:
            List of scanned stock dictionaries
        """
        logger.info(f"🔍 [JP] Scanning Japanese stocks...")

        # Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='STOCK', ttl_hours=24)
            if cached:
                logger.info(f"✅ [JP] Using cached data: {len(cached)} stocks")
                return cached

        # Use custom ticker list or default
        tickers_to_scan = ticker_list if ticker_list else self.DEFAULT_JP_TICKERS

        if max_count:
            tickers_to_scan = tickers_to_scan[:max_count]

        logger.info(f"📊 [JP] Fetching {len(tickers_to_scan)} stocks from yfinance...")

        scanned_stocks = []

        for i, ticker in enumerate(tickers_to_scan, 1):
            try:
                # Denormalize ticker for yfinance (7203 → 7203.T)
                yf_ticker = self.stock_parser.denormalize_ticker(ticker)

                # Get ticker info from yfinance
                ticker_info = self.yfinance_api.get_ticker_info(yf_ticker)

                if not ticker_info:
                    logger.warning(f"⚠️ [{ticker}] No info from yfinance")
                    continue

                # Parse to standardized format
                parsed = self.stock_parser.parse_ticker_info(ticker_info)

                if not parsed:
                    logger.warning(f"⚠️ [{ticker}] Failed to parse ticker info")
                    continue

                scanned_stocks.append(parsed)

                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(tickers_to_scan)} stocks")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Scan failed: {e}")
                continue

        logger.info(f"✅ [JP] Scanned {len(scanned_stocks)} stocks")

        # Filter common stocks (exclude REITs, preferred stocks)
        filtered_stocks = self.stock_parser.filter_common_stocks(scanned_stocks)
        logger.info(f"✅ [JP] Filtered: {len(filtered_stocks)} common stocks (excluded {len(scanned_stocks) - len(filtered_stocks)} special stocks)")

        # Save to database
        if filtered_stocks:
            self._save_tickers_to_db(filtered_stocks, asset_type='STOCK')

        return filtered_stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Japanese ETFs (not implemented yet)

        Args:
            force_refresh: Ignore cache

        Returns:
            Empty list (placeholder)
        """
        logger.info("ℹ️ [JP] ETF scanning not implemented yet")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for Japanese stocks

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Fetch OHLCV from yfinance (last N days)
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table

        Args:
            tickers: List of ticker codes (None = all JP stocks in DB)
            days: Historical days to collect (default: 250 for MA200)

        Returns:
            Number of stocks successfully updated
        """
        logger.info(f"📊 [JP] Collecting OHLCV data for {days} days...")

        # Get ticker list
        if not tickers:
            db_tickers = self.db.get_tickers(region='JP', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [JP] No tickers to collect")
            return 0

        logger.info(f"📈 [JP] Collecting OHLCV for {len(tickers)} stocks...")

        # Calculate date range (add buffer for weekends/holidays)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(days * 1.4))  # 1.4x buffer

        success_count = 0

        for i, ticker in enumerate(tickers, 1):
            try:
                # Denormalize ticker for yfinance
                yf_ticker = self.stock_parser.denormalize_ticker(ticker)

                # Fetch OHLCV data
                from_str = start_date.strftime('%Y-%m-%d')
                to_str = end_date.strftime('%Y-%m-%d')

                ohlcv_df = self.yfinance_api.get_ohlcv(
                    ticker=yf_ticker,
                    start_date=from_str,
                    end_date=to_str
                )

                if ohlcv_df is None or ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] No OHLCV data")
                    continue

                # Parse OHLCV data
                parsed_df = self.stock_parser.parse_ohlcv_data(ohlcv_df, ticker)

                if parsed_df is None or parsed_df.empty:
                    logger.warning(f"⚠️ [{ticker}] Failed to parse OHLCV")
                    continue

                # Calculate technical indicators
                parsed_df = self._calculate_technical_indicators(parsed_df)

                # Save to database using BaseAdapter method (auto-injects region)
                self._save_ohlcv_to_db(ticker, parsed_df, period_type='DAILY')

                success_count += 1
                logger.info(f"✅ [{ticker}] Saved {len(parsed_df)} days of OHLCV data")

                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(tickers)} stocks ({success_count} successful)")

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")
                continue

        logger.info(f"✅ [JP] OHLCV collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for Japanese ETFs (not implemented yet)

        Args:
            tickers: List of ETF ticker codes
            days: Historical days to collect

        Returns:
            0 (placeholder)
        """
        logger.info("ℹ️ [JP] ETF OHLCV collection not implemented yet")
        return 0

    def collect_fundamentals(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for Japanese stocks

        Fetches:
        - Market cap
        - P/E ratio
        - P/B ratio
        - Dividend yield
        - EPS, ROE, etc.

        Args:
            tickers: List of ticker codes (None = all JP stocks in DB)

        Returns:
            Number of stocks successfully updated
        """
        logger.info(f"📊 [JP] Collecting fundamental data...")

        # Get ticker list
        if not tickers:
            db_tickers = self.db.get_tickers(region='JP', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [JP] No tickers to collect")
            return 0

        logger.info(f"💰 [JP] Collecting fundamentals for {len(tickers)} stocks...")

        success_count = 0
        today = datetime.now().strftime('%Y-%m-%d')

        for i, ticker in enumerate(tickers, 1):
            try:
                # Denormalize ticker for yfinance
                yf_ticker = self.stock_parser.denormalize_ticker(ticker)

                # Fetch ticker info
                ticker_info = self.yfinance_api.get_ticker_info(yf_ticker)

                if not ticker_info:
                    continue

                # Extract fundamental data
                fundamentals = {
                    'ticker': ticker,
                    'date': today,
                    'period_type': 'DAILY',
                    'market_cap': ticker_info.get('marketCap'),
                    'pe_ratio': ticker_info.get('trailingPE') or ticker_info.get('forwardPE'),
                    'pb_ratio': ticker_info.get('priceToBook'),
                    'dividend_yield': ticker_info.get('dividendYield'),
                    'eps': ticker_info.get('trailingEps'),
                    'roe': ticker_info.get('returnOnEquity'),
                    'close_price': ticker_info.get('currentPrice') or ticker_info.get('regularMarketPrice'),
                    'data_source': 'yfinance'
                }

                # Save to database
                self.db.insert_ticker_fundamentals(fundamentals)
                success_count += 1

                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(tickers)} stocks")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Fundamentals collection failed: {e}")
                continue

        logger.info(f"✅ [JP] Fundamentals collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def add_custom_ticker(self, ticker: str) -> bool:
        """
        Add a custom ticker to the database

        Args:
            ticker: Normalized ticker code (e.g., "7203")

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"➕ [JP] Adding custom ticker: {ticker}")

            # Fetch and parse ticker info
            yf_ticker = self.stock_parser.denormalize_ticker(ticker)
            ticker_info = self.yfinance_api.get_ticker_info(yf_ticker)

            if not ticker_info:
                logger.error(f"❌ [{ticker}] No info from yfinance")
                return False

            parsed = self.stock_parser.parse_ticker_info(ticker_info)

            if not parsed:
                logger.error(f"❌ [{ticker}] Failed to parse ticker info")
                return False

            # Save to database
            self._save_tickers_to_db([parsed], asset_type='STOCK')

            logger.info(f"✅ [{ticker}] Custom ticker added successfully")
            return True

        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to add custom ticker: {e}")
            return False
