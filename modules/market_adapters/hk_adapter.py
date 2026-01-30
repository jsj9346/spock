"""
Hong Kong Market Adapter - HKEX Stock Market Integration

Handles ticker discovery, OHLCV collection, and fundamentals for HK stocks.

Hybrid Data Strategy:
- Primary: AkShare (open-source, ~4,600 stocks, 36 financial indicators)
- Fallback: yfinance (Yahoo Finance)

Market: Hong Kong Exchange (HKEX)
Trading Hours: 09:30-12:00, 13:00-16:00 HKT
Currency: HKD

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_adapter import BaseMarketAdapter
from ..api_clients.akshare_api import AkShareAPI
from ..api_clients.yfinance_api import YFinanceAPI
from ..parsers.hk_stock_parser import HKStockParser

logger = logging.getLogger(__name__)


class HKAdapter(BaseMarketAdapter):
    """
    Hong Kong market adapter with hybrid data strategy (AkShare + yfinance)

    Features:
    - Dynamic ticker discovery via AkShare (~4,600 stocks)
    - 36 financial indicators via AkShare
    - OHLCV data collection (250-day history)
    - yfinance fallback for reliability
    - HKEX holiday calendar support

    Usage:
        db = SQLiteDatabaseManager()
        adapter = HKAdapter(db)
        stocks = adapter.scan_stocks(force_refresh=True)  # ~4,600 stocks from AkShare
        adapter.collect_fundamentals()  # 36 financial indicators
        adapter.collect_stock_ohlcv(days=250)
    """

    # Fallback ticker list when AkShare fails
    # Hang Seng Index constituents + major H-shares
    # Format: XXXX.HK (unified database format)
    FALLBACK_HK_TICKERS = [
        # Hang Seng Index Top 10
        '0700.HK',  # Tencent Holdings
        '9988.HK',  # Alibaba Group
        '0941.HK',  # China Mobile
        '1299.HK',  # AIA Group
        '0388.HK',  # Hong Kong Exchanges
        '0005.HK',  # HSBC Holdings
        '3690.HK',  # Meituan
        '2318.HK',  # Ping An Insurance
        '1398.HK',  # ICBC
        '0011.HK',  # Hang Seng Bank

        # Major H-Shares
        '0939.HK',  # China Construction Bank
        '2628.HK',  # China Life Insurance
        '0883.HK',  # CNOOC
        '0386.HK',  # China Petroleum & Chemical
        '1288.HK',  # Agricultural Bank of China
        '0857.HK',  # PetroChina
        '3988.HK',  # Bank of China
        '2382.HK',  # Sunny Optical Technology
        '1109.HK',  # China Resources Land
        '0175.HK',  # Geely Automobile

        # Technology
        '0772.HK',  # China Literature
        '1810.HK',  # Xiaomi Corporation
        '9961.HK',  # Trip.com Group
        '9618.HK',  # JD.com
        '9999.HK',  # NetEase

        # Consumer
        '1211.HK',  # BYD Company
        '2269.HK',  # Wuxi Biologics
        '6618.HK',  # JD Health International
        '0968.HK',  # Xinyi Solar Holdings
        '2688.HK',  # ENN Energy Holdings
    ]

    def __init__(self, db_manager, enable_fallback: bool = True):
        """
        Initialize Hong Kong adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
            enable_fallback: Enable yfinance fallback (default: True)
        """
        super().__init__(db_manager, region_code='HK')

        self.akshare_api = AkShareAPI(rate_limit_per_second=1.5)
        self.yfinance_api = YFinanceAPI(rate_limit_per_second=1.0) if enable_fallback else None
        self.stock_parser = HKStockParser()
        self.enable_fallback = enable_fallback

        logger.info("🇭🇰 HKAdapter initialized (AkShare primary + yfinance fallback)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    ticker_list: Optional[List[str]] = None,
                    max_count: Optional[int] = None,
                    use_akshare: bool = True) -> List[Dict]:
        """
        Scan Hong Kong stocks and populate database

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch ticker list from AkShare (~4,600 stocks) or use fallback
        3. Parse and normalize data
        4. Filter common stocks (exclude warrants, CBBCs)
        5. Apply max_count limit if specified
        6. Save to database

        Args:
            force_refresh: Ignore cache and force refresh
            ticker_list: Custom ticker list (overrides AkShare fetch)
            max_count: Max number of stocks to return (default: None = all)
            use_akshare: Use AkShare for dynamic ticker list (default: True)

        Returns:
            List of stock ticker dictionaries
        """
        logger.info(f"🔍 [HK] Starting stock scan (force_refresh={force_refresh}, use_akshare={use_akshare})")

        # Step 1: Check cache
        if not force_refresh:
            cached_tickers = self._load_tickers_from_cache(asset_type='STOCK')
            if cached_tickers:
                if max_count:
                    return cached_tickers[:max_count]
                return cached_tickers

        # Step 2: Get ticker list
        all_stocks = []

        if ticker_list:
            # Use provided custom ticker list with yfinance
            logger.info(f"📊 [HK] Using custom ticker list ({len(ticker_list)} tickers)")
            all_stocks = self._scan_stocks_yfinance(ticker_list)

        elif use_akshare:
            # Try AkShare first for dynamic expansion (~4,600 stocks)
            logger.info("📊 [HK] Fetching stock list from AkShare...")

            akshare_df = self.akshare_api.get_hk_stock_list()

            if akshare_df is not None and not akshare_df.empty:
                logger.info(f"✅ [HK] Fetched {len(akshare_df)} stocks from AkShare")

                # Parse to standardized format
                all_stocks = self.stock_parser.parse_hk_stock_list(akshare_df)
                logger.info(f"✅ [HK] Parsed {len(all_stocks)} stocks")
            else:
                logger.warning("⚠️ [HK] AkShare failed, falling back to default tickers")
                all_stocks = self._scan_stocks_yfinance(self.FALLBACK_HK_TICKERS)

        else:
            # Use fallback ticker list with yfinance
            logger.info(f"📊 [HK] Using fallback ticker list ({len(self.FALLBACK_HK_TICKERS)} tickers)")
            all_stocks = self._scan_stocks_yfinance(self.FALLBACK_HK_TICKERS)

        # Step 3: Filter common stocks (exclude warrants, CBBCs, etc.)
        common_stocks = self.stock_parser.filter_common_stocks(all_stocks)
        logger.info(f"📊 [HK] Filtered to {len(common_stocks)} common stocks")

        # Step 4: Apply max_count limit
        if max_count and len(common_stocks) > max_count:
            logger.info(f"📊 [HK] Limiting to {max_count}/{len(common_stocks)} stocks")
            common_stocks = common_stocks[:max_count]

        # Step 5: Classify asset types and save to database
        if common_stocks:
            # Classify each ticker and group by asset_type
            asset_type_counts = {}
            classified_stocks = []

            for stock in common_stocks:
                asset_type = self.stock_parser.classify_asset_type(stock)
                stock['asset_type'] = asset_type
                classified_stocks.append(stock)

                # Track counts for logging
                asset_type_counts[asset_type] = asset_type_counts.get(asset_type, 0) + 1

            # Log classification summary
            logger.info(f"📊 [HK] Classification summary: {asset_type_counts}")

            # Save all tickers (will be saved with their classified asset_type)
            self._save_tickers_to_db(classified_stocks, asset_type=None)
            logger.info(f"💾 [HK] Saved {len(classified_stocks)} tickers to database")
        else:
            logger.warning("⚠️ [HK] No stocks to save")

        return common_stocks

    def _scan_stocks_yfinance(self, ticker_list: List[str]) -> List[Dict]:
        """
        Scan stocks using yfinance (fallback method)

        Args:
            ticker_list: List of HK ticker codes

        Returns:
            List of stock ticker dictionaries
        """
        all_stocks = []

        for i, ticker in enumerate(ticker_list, 1):
            try:
                # Denormalize ticker for yfinance: "00700" → "0700.HK"
                yfinance_ticker = self.stock_parser.denormalize_ticker(ticker)

                if i % 10 == 0:
                    logger.info(f"📈 [HK] yfinance progress: {i}/{len(ticker_list)}")

                # Fetch company info
                info = self.yfinance_api.get_ticker_info(yfinance_ticker)

                if not info:
                    logger.debug(f"⚠️ No data for {yfinance_ticker}")
                    continue

                # Parse to standardized format
                stock_data = self.stock_parser.parse_ticker_info(info)

                if stock_data:
                    all_stocks.append(stock_data)

            except Exception as e:
                logger.debug(f"⚠️ Error fetching {ticker}: {e}")
                continue

        logger.info(f"✅ [HK] yfinance fetched {len(all_stocks)}/{len(ticker_list)} stocks")
        return all_stocks

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

    def collect_fundamentals(self,
                            tickers: Optional[List[str]] = None,
                            use_fallback: bool = True,
                            report_date: Optional[str] = None) -> int:
        """
        Collect fundamental data for HK stocks with hybrid strategy

        Primary: AkShare (36 financial indicators)
        Fallback: yfinance (market cap only)

        Args:
            tickers: List of ticker codes (None = all HK stocks)
            use_fallback: Use yfinance fallback if AkShare fails
            report_date: Target report date (YYYY-MM-DD format, default: today)

        Returns:
            Number of tickers updated
        """
        logger.info("📊 [HK] Starting fundamentals collection (AkShare primary)")

        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='HK', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [HK] No tickers for fundamentals")
            return 0

        logger.info(f"📈 [HK] Collecting fundamentals for {len(tickers)} stocks...")

        success_count = 0
        fallback_count = 0
        today = datetime.now().strftime("%Y-%m-%d")

        for i, ticker in enumerate(tickers, 1):
            try:
                if i % 100 == 0:
                    logger.info(f"📊 [HK] Progress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%)")

                # Normalize ticker for AkShare API: "0001.HK" → "00001" (5 digits)
                akshare_ticker = self.stock_parser.normalize_ticker_akshare(ticker)
                if not akshare_ticker:
                    logger.debug(f"⚠️ Invalid ticker format for AkShare: {ticker}")
                    # Fall through to yfinance fallback
                else:
                    # Try AkShare first (36 financial indicators)
                    indicators_df = self.akshare_api.get_hk_financial_indicators(akshare_ticker)

                    if indicators_df is not None and not indicators_df.empty:
                        # Parse to database format
                        record = self.stock_parser.parse_hk_financial_indicators(
                            indicators_df,
                            ticker,  # Use original ticker for DB storage
                            report_date=report_date
                        )

                        if record:
                            # Check insertion result
                            if self.db.insert_ticker_fundamentals(record):
                                success_count += 1
                                continue
                            else:
                                logger.debug(f"⚠️ [HK] Failed to insert {ticker}")

                # Fallback to yfinance if AkShare fails
                if use_fallback and self.yfinance_api:
                    logger.debug(f"⚠️ AkShare failed for {ticker}, trying yfinance...")

                    yfinance_ticker = self.stock_parser.denormalize_ticker(ticker)
                    info = self.yfinance_api.get_ticker_info(yfinance_ticker)

                    if info:
                        market_cap = info.get('market_cap')

                        if market_cap:
                            # Normalize ticker to database format (XXXX.HK)
                            db_ticker = self.stock_parser.normalize_ticker_db(ticker)
                            if not db_ticker:
                                logger.debug(f"⚠️ Invalid ticker for yfinance fallback: {ticker}")
                                continue

                            # Check insertion result
                            if self.db.insert_ticker_fundamentals({
                                'ticker': db_ticker,
                                'region': 'HK',
                                'date': today,
                                'period_type': 'QUARTERLY',
                                'market_cap': market_cap,
                                'data_source': 'yfinance'
                            }):
                                fallback_count += 1
                                success_count += 1
                            else:
                                logger.debug(f"⚠️ [HK] Failed to insert {db_ticker} (yfinance fallback)")

            except Exception as e:
                logger.debug(f"⚠️ Fundamentals collection failed for {ticker}: {e}")
                continue

        logger.info(f"✅ [HK] Fundamentals complete: {success_count}/{len(tickers)}")

        if fallback_count > 0:
            logger.info(f"📊 [HK] yfinance fallback used for {fallback_count} stocks")

        return success_count

    def collect_fundamentals_legacy(self, tickers: Optional[List[str]] = None) -> int:
        """
        Legacy fundamentals collection using yfinance only (market cap)

        Kept for backward compatibility. Use collect_fundamentals() for
        comprehensive fundamental data collection with AkShare.

        Args:
            tickers: List of ticker codes (None = all HK stocks)

        Returns:
            Number of tickers updated
        """
        logger.info("📊 [HK] Starting legacy fundamentals collection (yfinance only)")

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
                        'region': 'HK',
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

        logger.info(f"✅ [HK] Legacy fundamentals complete: {success_count}/{len(tickers)}")
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
