"""
China Market Adapter - SSE/SZSE Stock Market Integration

Handles ticker discovery, OHLCV collection, and fundamentals for Chinese A-shares.

Hybrid Data Strategy:
- Primary: AkShare (open-source, no API key)
- Fallback: yfinance (Yahoo Finance)

Markets: Shanghai Stock Exchange (SSE) + Shenzhen Stock Exchange (SZSE)
Trading Hours: 09:30-11:30, 13:00-15:00 CST
Currency: CNY

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_adapter import BaseMarketAdapter
from ..api_clients.akshare_api import AkShareAPI
from ..api_clients.yfinance_api import YFinanceAPI
from ..parsers.cn_stock_parser import CNStockParser

logger = logging.getLogger(__name__)


class CNAdapter(BaseMarketAdapter):
    """
    China market adapter with hybrid data strategy (AkShare + yfinance)

    Features:
    - SSE + SZSE stock coverage (~4,000 stocks)
    - AkShare primary data source (free, no API key)
    - yfinance fallback for reliability
    - OHLCV data collection (250-day history)
    - CSRC industry → GICS sector mapping
    - Chinese holiday calendar support

    Usage:
        db = SQLiteDatabaseManager()
        adapter = CNAdapter(db)
        stocks = adapter.scan_stocks(force_refresh=True, max_count=100)
        adapter.collect_stock_ohlcv(days=250)
    """

    def __init__(self, db_manager, enable_fallback: bool = True):
        """
        Initialize China adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
            enable_fallback: Enable yfinance fallback (default: True)
        """
        super().__init__(db_manager, region_code='CN')

        self.akshare_api = AkShareAPI(rate_limit_per_second=1.5)
        self.yfinance_api = YFinanceAPI(rate_limit_per_second=1.0) if enable_fallback else None
        self.stock_parser = CNStockParser()
        self.enable_fallback = enable_fallback

        logger.info("🇨🇳 CNAdapter initialized (AkShare primary + yfinance fallback)")

    def scan_stocks(self,
                    force_refresh: bool = False,
                    max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan Chinese stocks and populate database

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch stock list from AkShare (real-time)
        3. Parse and normalize data
        4. Filter common stocks (exclude ST, B-shares)
        5. Apply max_count limit if specified
        6. Save to database

        Args:
            force_refresh: Ignore cache and force refresh
            max_count: Max number of stocks to return (default: None = all)

        Returns:
            List of stock ticker dictionaries
        """
        logger.info(f"🔍 [CN] Starting stock scan (force_refresh={force_refresh}, max_count={max_count})")

        # Step 1: Check cache
        if not force_refresh:
            cached_tickers = self._load_tickers_from_cache(asset_type='STOCK')
            if cached_tickers:
                if max_count:
                    return cached_tickers[:max_count]
                return cached_tickers

        # Step 2: Fetch stock list from AkShare
        logger.info("📊 [CN] Fetching stock list from AkShare...")

        akshare_df = self.akshare_api.get_stock_list_realtime()

        if akshare_df is None or akshare_df.empty:
            logger.error("❌ [CN] Failed to fetch stock list from AkShare")

            # Fallback to yfinance not implemented for stock list
            # (yfinance doesn't provide exchange-wide ticker lists)
            return []

        logger.info(f"✅ [CN] Fetched {len(akshare_df)} stocks from AkShare")

        # Step 3: Parse to standardized format
        all_stocks = self.stock_parser.parse_akshare_stock_list(akshare_df)

        # Step 4: Filter common stocks (exclude ST, B-shares, etc.)
        common_stocks = self.stock_parser.filter_common_stocks(all_stocks)

        # Step 5: Apply max_count limit
        if max_count and len(common_stocks) > max_count:
            logger.info(f"📊 [CN] Limiting to {max_count}/{len(common_stocks)} stocks")
            common_stocks = common_stocks[:max_count]

        # Step 6: Save to database
        if common_stocks:
            self._save_tickers_to_db(common_stocks, asset_type='STOCK')
            logger.info(f"💾 [CN] Saved {len(common_stocks)} stocks to database")
        else:
            logger.warning("⚠️ [CN] No stocks to save")

        return common_stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Chinese ETFs (not implemented - focus on stocks first)

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            Empty list (CN ETFs not prioritized in Phase 3)
        """
        logger.info("⚠️ [CN] ETF scanning not implemented (use scan_stocks instead)")
        return []

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250,
                           use_fallback: bool = True) -> int:
        """
        Collect OHLCV data for CN stocks with hybrid strategy

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Try AkShare first for each ticker
        3. If AkShare fails, try yfinance (fallback)
        4. Parse and normalize data
        5. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        6. Save to ohlcv_data table

        Args:
            tickers: List of ticker codes (None = all CN stocks in DB)
            days: Historical days to collect (default: 250 for MA200)
            use_fallback: Use yfinance fallback if AkShare fails (default: True)

        Returns:
            Number of stocks successfully updated
        """
        logger.info(f"📊 [CN] Starting OHLCV collection (days={days}, fallback={use_fallback})")

        # Step 1: Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='CN', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [CN] No tickers to collect OHLCV")
            return 0

        logger.info(f"📈 [CN] Collecting OHLCV for {len(tickers)} stocks...")

        # Step 2: Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10)  # +10 buffer

        success_count = 0
        fallback_count = 0

        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"📊 ({i}/{len(tickers)}) Fetching OHLCV for {ticker}...")

                # Step 3: Try AkShare first
                ohlcv_df = self.akshare_api.get_stock_daily_ohlcv(
                    ticker=ticker,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d')
                )

                data_source = 'akshare'

                # Step 4: Fallback to yfinance if AkShare fails
                if (ohlcv_df is None or ohlcv_df.empty) and use_fallback and self.yfinance_api:
                    logger.warning(f"⚠️ AkShare failed for {ticker}, trying yfinance...")

                    # Convert to yfinance format
                    yf_ticker = self.stock_parser.denormalize_ticker_yfinance(ticker)

                    ohlcv_df = self.yfinance_api.get_ohlcv(
                        ticker=yf_ticker,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d')
                    )

                    if ohlcv_df is not None and not ohlcv_df.empty:
                        data_source = 'yfinance'
                        fallback_count += 1
                        logger.info(f"✅ yfinance fallback successful for {ticker}")

                if ohlcv_df is None or ohlcv_df.empty:
                    logger.warning(f"⚠️ No OHLCV data for {ticker} (both sources failed)")
                    continue

                # Step 5: Parse to standardized format
                parsed_df = self.stock_parser.parse_ohlcv_data(
                    ohlcv_df,
                    ticker,
                    source=data_source
                )

                if parsed_df is None or parsed_df.empty:
                    logger.warning(f"⚠️ Failed to parse OHLCV for {ticker}")
                    continue

                # Step 6: Calculate technical indicators
                parsed_df = self._calculate_technical_indicators(parsed_df)

                # Step 7: Save to database using BaseAdapter method (auto-injects region)
                self._save_ohlcv_to_db(ticker, parsed_df, period_type='DAILY')

                success_count += 1
                logger.info(f"✅ Saved {len(parsed_df)} days for {ticker} (source: {data_source})")

            except Exception as e:
                logger.error(f"❌ OHLCV collection failed for {ticker}: {e}")
                continue

        logger.info(f"✅ [CN] OHLCV collection complete: {success_count}/{len(tickers)} stocks")

        if fallback_count > 0:
            logger.info(f"📊 [CN] yfinance fallback used for {fallback_count} stocks ({fallback_count/len(tickers)*100:.1f}%)")

        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for CN ETFs (not implemented)

        Args:
            tickers: List of ETF ticker codes
            days: Historical days to collect

        Returns:
            0 (not implemented)
        """
        logger.info("⚠️ [CN] ETF OHLCV collection not implemented")
        return 0

    def collect_fundamentals(self,
                            tickers: Optional[List[str]] = None,
                            use_fallback: bool = True) -> int:
        """
        Collect fundamental data for CN stocks

        Fetches industry classification and market cap from AkShare.
        Falls back to yfinance if AkShare fails.

        Args:
            tickers: List of ticker codes (None = all CN stocks)
            use_fallback: Use yfinance fallback if AkShare fails

        Returns:
            Number of tickers updated
        """
        logger.info("📊 [CN] Starting fundamentals collection")

        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='CN', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️ [CN] No tickers for fundamentals")
            return 0

        logger.info(f"📈 [CN] Collecting fundamentals for {len(tickers)} stocks...")

        success_count = 0
        fallback_count = 0
        today = datetime.now().strftime("%Y-%m-%d")

        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"📊 ({i}/{len(tickers)}) Fetching fundamentals for {ticker}...")

                # Try AkShare first
                info = self.akshare_api.get_stock_info(ticker)

                if info:
                    # Parse AkShare info
                    stock_data = self.stock_parser.parse_akshare_stock_info(info, ticker)

                    if stock_data and stock_data.get('market_cap'):
                        self.db.insert_ticker_fundamentals({
                            'ticker': ticker,
                            'date': today,
                            'period_type': 'DAILY',
                            'market_cap': stock_data['market_cap'],
                            'data_source': 'akshare'
                        })

                        # Update stock_details with sector/industry
                        if stock_data.get('sector') or stock_data.get('industry'):
                            self.db.update_stock_details(ticker, {
                                'sector': stock_data.get('sector'),
                                'industry': stock_data.get('industry')
                            })

                        success_count += 1
                        logger.info(f"✅ Saved fundamentals for {ticker}")
                        continue

                # Fallback to yfinance
                if use_fallback and self.yfinance_api:
                    logger.warning(f"⚠️ AkShare failed for {ticker}, trying yfinance...")

                    yf_ticker = self.stock_parser.denormalize_ticker_yfinance(ticker)
                    yf_info = self.yfinance_api.get_ticker_info(yf_ticker)

                    if yf_info:
                        stock_data = self.stock_parser.parse_yfinance_info(yf_info, ticker)

                        if stock_data and stock_data.get('market_cap'):
                            self.db.insert_ticker_fundamentals({
                                'ticker': ticker,
                                'date': today,
                                'period_type': 'DAILY',
                                'market_cap': stock_data['market_cap'],
                                'data_source': 'yfinance'
                            })

                            fallback_count += 1
                            success_count += 1
                            logger.info(f"✅ yfinance fallback successful for {ticker}")

            except Exception as e:
                logger.error(f"❌ Fundamentals collection failed for {ticker}: {e}")
                continue

        logger.info(f"✅ [CN] Fundamentals complete: {success_count}/{len(tickers)}")

        if fallback_count > 0:
            logger.info(f"📊 [CN] yfinance fallback used for {fallback_count} stocks")

        return success_count

    def add_custom_tickers(self, tickers: List[str]) -> int:
        """
        Add custom tickers to the scan list

        Args:
            tickers: List of CN ticker codes (e.g., ['600519', '000001'])

        Returns:
            Number of tickers successfully added
        """
        logger.info(f"➕ [CN] Adding {len(tickers)} custom tickers...")

        # Fetch stock list
        akshare_df = self.akshare_api.get_stock_list_realtime()

        if akshare_df is None or akshare_df.empty:
            logger.error("❌ Failed to fetch stock list")
            return 0

        # Filter to custom tickers
        akshare_df['code'] = akshare_df['code'].astype(str).str.zfill(6)
        filtered_df = akshare_df[akshare_df['code'].isin(tickers)]

        # Parse and save
        stocks = self.stock_parser.parse_akshare_stock_list(filtered_df)

        if stocks:
            self._save_tickers_to_db(stocks, asset_type='STOCK')
            logger.info(f"✅ [CN] Added {len(stocks)} custom tickers")

        return len(stocks)

    def get_fallback_stats(self) -> Dict:
        """
        Get statistics on fallback usage

        Returns:
            Dictionary with fallback statistics
        """
        # This would be tracked during operations
        # For now, return placeholder
        return {
            'fallback_enabled': self.enable_fallback,
            'fallback_available': self.yfinance_api is not None
        }
