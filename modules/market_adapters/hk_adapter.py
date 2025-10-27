"""
Hong Kong Market Adapter - HKEX Stock Market Integration

Handles ticker discovery, OHLCV collection, and fundamentals for HK stocks.

Data Source: yfinance (Yahoo Finance)
Market: Hong Kong Exchange (HKEX)
Trading Hours: 09:30-12:00, 13:00-16:00 HKT
Currency: HKD

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_adapter import BaseMarketAdapter
from ..api_clients.yfinance_api import YFinanceAPI
from ..parsers.hk_stock_parser import HKStockParser

logger = logging.getLogger(__name__)


class HKAdapter(BaseMarketAdapter):
    """
    Hong Kong market adapter using yfinance

    Features:
    - Hang Seng Index constituents + major H-shares
    - OHLCV data collection (250-day history)
    - Company fundamentals
    - HKEX holiday calendar support

    Usage:
        db = SQLiteDatabaseManager()
        adapter = HKAdapter(db)
        stocks = adapter.scan_stocks(force_refresh=True)
        adapter.collect_stock_ohlcv(days=250)
    """

    # Hang Seng Index constituents + major H-shares (sample list)
    # In production, fetch from external source or update manually
    DEFAULT_HK_TICKERS = [
        # Hang Seng Index Top 10
        '0700',  # Tencent Holdings
        '9988',  # Alibaba Group
        '0941',  # China Mobile
        '1299',  # AIA Group
        '0388',  # Hong Kong Exchanges
        '0005',  # HSBC Holdings
        '3690',  # Meituan
        '2318',  # Ping An Insurance
        '1398',  # ICBC
        '0011',  # Hang Seng Bank

        # Major H-Shares
        '0939',  # China Construction Bank
        '2628',  # China Life Insurance
        '0883',  # CNOOC
        '0386',  # China Petroleum & Chemical
        '1288',  # Agricultural Bank of China
        '0857',  # PetroChina
        '3988',  # Bank of China
        '2382',  # Sunny Optical Technology
        '1109',  # China Resources Land
        '0175',  # Geely Automobile

        # Technology
        '0772',  # China Literature
        '1810',  # Xiaomi Corporation
        '9961',  # Trip.com Group
        '9618',  # JD.com
        '9999',  # NetEase

        # Consumer
        '1211',  # BYD Company
        '2269',  # Wuxi Biologics
        '6618',  # JD Health International
        '0968',  # Xinyi Solar Holdings
        '2688',  # ENN Energy Holdings
    ]

    def __init__(self, db_manager):
        """
        Initialize Hong Kong adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
        """
        super().__init__(db_manager, region_code='HK')

        self.yfinance_api = YFinanceAPI(rate_limit_per_second=1.0)
        self.stock_parser = HKStockParser()

        logger.info("🇭🇰 HKAdapter initialized (yfinance data source)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    ticker_list: Optional[List[str]] = None) -> List[Dict]:
        """
        Scan Hong Kong stocks and populate database

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch ticker list (Hang Seng + H-shares)
        3. Get company info for each ticker via yfinance
        4. Parse and normalize data
        5. Filter common stocks (exclude ETFs)
        6. Save to database

        Args:
            force_refresh: Ignore cache and force refresh
            ticker_list: Custom ticker list (default: DEFAULT_HK_TICKERS)

        Returns:
            List of stock ticker dictionaries
        """
        logger.info(f"🔍 [HK] Starting stock scan (force_refresh={force_refresh})")

        # Step 1: Check cache
        if not force_refresh:
            cached_tickers = self._load_tickers_from_cache(asset_type='STOCK')
            if cached_tickers:
                return cached_tickers

        # Step 2: Use provided ticker list or default
        if ticker_list is None:
            ticker_list = self.DEFAULT_HK_TICKERS.copy()

        logger.info(f"📊 [HK] Fetching {len(ticker_list)} tickers...")

        # Step 3: Fetch company info for each ticker
        all_stocks = []
        success_count = 0

        for i, ticker in enumerate(ticker_list, 1):
            try:
                # Denormalize ticker for yfinance: "0700" → "0700.HK"
                yfinance_ticker = self.stock_parser.denormalize_ticker(ticker)

                logger.info(f"📈 ({i}/{len(ticker_list)}) Fetching {yfinance_ticker}...")

                # Fetch company info
                info = self.yfinance_api.get_ticker_info(yfinance_ticker)

                if not info:
                    logger.warning(f"⚠️ No data for {yfinance_ticker}")
                    continue

                # Parse to standardized format
                stock_data = self.stock_parser.parse_ticker_info(info)

                if stock_data:
                    all_stocks.append(stock_data)
                    success_count += 1
                else:
                    logger.warning(f"⚠️ Failed to parse {yfinance_ticker}")

            except Exception as e:
                logger.error(f"❌ Error fetching {ticker}: {e}")
                continue

        logger.info(f"✅ [HK] Fetched {success_count}/{len(ticker_list)} stocks")

        # Step 4: Filter common stocks (exclude ETFs)
        common_stocks = self.stock_parser.filter_common_stocks(all_stocks)

        # Step 5: Save to database
        if common_stocks:
            self._save_tickers_to_db(common_stocks, asset_type='STOCK')
            logger.info(f"💾 [HK] Saved {len(common_stocks)} stocks to database")
        else:
            logger.warning("⚠️ [HK] No stocks to save")

        return common_stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Hong Kong ETFs (not implemented - use KIS API for KR ETFs)

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            Empty list (HK ETFs not prioritized in Phase 3)
        """
        logger.info("⚠️ [HK] ETF scanning not implemented (use scan_stocks instead)")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for HK stocks

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Fetch OHLCV from yfinance (250-day default)
        3. Parse and normalize data
        4. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        5. Save to ohlcv_data table

        Args:
            tickers: List of ticker codes (None = all HK stocks in DB)
            days: Historical days to collect (default: 250 for MA200)

        Returns:
            Number of stocks successfully updated
        """
        logger.info(f"📊 [HK] Starting OHLCV collection (days={days})")

        # Step 1: Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='HK', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [HK] No tickers to collect OHLCV")
            return 0

        logger.info(f"📈 [HK] Collecting OHLCV for {len(tickers)} stocks...")

        # Step 2: Calculate date range (days back from today)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # +10 buffer for weekends/holidays

        success_count = 0

        for i, ticker in enumerate(tickers, 1):
            try:
                # Denormalize ticker for yfinance
                yfinance_ticker = self.stock_parser.denormalize_ticker(ticker)

                logger.info(f"📊 ({i}/{len(tickers)}) Fetching OHLCV for {yfinance_ticker}...")

                # Fetch OHLCV data
                ohlcv_df = self.yfinance_api.get_ohlcv(
                    ticker=yfinance_ticker,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )

                if ohlcv_df is None or ohlcv_df.empty:
                    logger.warning(f"⚠️ No OHLCV data for {yfinance_ticker}")
                    continue

                # Parse to standardized format
                parsed_df = self.stock_parser.parse_ohlcv_data(ohlcv_df, ticker)

                if parsed_df is None or parsed_df.empty:
                    logger.warning(f"⚠️ Failed to parse OHLCV for {yfinance_ticker}")
                    continue

                # Calculate technical indicators
                parsed_df = self._calculate_technical_indicators(parsed_df)

                # Save to database using BaseAdapter method (auto-injects region)
                self._save_ohlcv_to_db(ticker, parsed_df, period_type='DAILY')

                success_count += 1
                logger.info(f"✅ Saved {len(parsed_df)} days for {ticker}")

            except Exception as e:
                logger.error(f"❌ OHLCV collection failed for {ticker}: {e}")
                continue

        logger.info(f"✅ [HK] OHLCV collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for HK ETFs (not implemented)

        Args:
            tickers: List of ETF ticker codes
            days: Historical days to collect

        Returns:
            0 (not implemented)
        """
        logger.info("⚠️ [HK] ETF OHLCV collection not implemented")
        return 0

    def collect_fundamentals(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for HK stocks

        Fetches market cap, sector, industry from yfinance info.

        Args:
            tickers: List of ticker codes (None = all HK stocks)

        Returns:
            Number of tickers updated
        """
        logger.info("📊 [HK] Starting fundamentals collection")

        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='HK', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [HK] No tickers for fundamentals")
            return 0

        logger.info(f"📈 [HK] Collecting fundamentals for {len(tickers)} stocks...")

        success_count = 0
        today = datetime.now().strftime("%Y-%m-%d")

        for i, ticker in enumerate(tickers, 1):
            try:
                yfinance_ticker = self.stock_parser.denormalize_ticker(ticker)

                logger.info(f"📊 ({i}/{len(tickers)}) Fetching fundamentals for {yfinance_ticker}...")

                # Fetch company info
                info = self.yfinance_api.get_ticker_info(yfinance_ticker)

                if not info:
                    logger.warning(f"⚠️ No fundamentals for {yfinance_ticker}")
                    continue

                # Extract market cap and current price
                market_cap = info.get('market_cap')

                if market_cap:
                    self.db.insert_ticker_fundamentals({
                        'ticker': ticker,
                        'date': today,
                        'period_type': 'DAILY',
                        'market_cap': market_cap,
                        'data_source': 'yfinance'
                    })

                    success_count += 1
                    logger.info(f"✅ Saved fundamentals for {ticker}")

            except Exception as e:
                logger.error(f"❌ Fundamentals collection failed for {ticker}: {e}")
                continue

        logger.info(f"✅ [HK] Fundamentals complete: {success_count}/{len(tickers)}")
        return success_count

    def add_custom_tickers(self, tickers: List[str]) -> int:
        """
        Add custom tickers to the scan list

        Args:
            tickers: List of HK ticker codes (e.g., ['0700', '0941'])

        Returns:
            Number of tickers successfully added
        """
        logger.info(f"➕ [HK] Adding {len(tickers)} custom tickers...")

        # Scan the custom tickers
        stocks = self.scan_stocks(force_refresh=True, ticker_list=tickers)

        logger.info(f"✅ [HK] Added {len(stocks)} custom tickers")
        return len(stocks)
