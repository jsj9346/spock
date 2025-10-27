"""
Vietnam Market Adapter - HOSE/HNX Stock Market Integration

Handles ticker discovery, OHLCV collection, and fundamentals for Vietnamese stocks.

Data Source: yfinance (Yahoo Finance)
Markets: HOSE (Ho Chi Minh Stock Exchange), HNX (Hanoi Stock Exchange)
Trading Hours: HOSE 09:15-14:30, HNX 09:00-14:30 ICT
Currency: VND

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .base_adapter import BaseMarketAdapter
from ..api_clients.yfinance_api import YFinanceAPI
from ..parsers.vn_stock_parser import VNStockParser

logger = logging.getLogger(__name__)


class VNAdapter(BaseMarketAdapter):
    """
    Vietnam market adapter using yfinance

    Features:
    - VN30 index constituents (30 major stocks)
    - OHLCV data collection (250-day history)
    - Company fundamentals
    - HOSE/HNX holiday calendar support

    Usage:
        db = SQLiteDatabaseManager()
        adapter = VNAdapter(db)
        stocks = adapter.scan_stocks(force_refresh=True)
        adapter.collect_stock_ohlcv(days=250)
    """

    # VN30 index constituents (top 30 stocks by market cap and liquidity)
    # Based on HOSE VN30 index composition as of 2025
    DEFAULT_VN_TICKERS = [
        # Top 10 by Market Cap
        'VCB',   # Vietcombank (Joint Stock Commercial Bank for Foreign Trade of Vietnam)
        'TCB',   # Techcombank (Vietnam Technological and Commercial Joint Stock Bank)
        'MBB',   # Military Bank (Military Commercial Joint Stock Bank)
        'VIC',   # Vingroup (Vingroup Joint Stock Company)
        'FPT',   # FPT Corporation (Technology conglomerate)
        'VPB',   # VPBank (Vietnam Prosperity Joint-Stock Commercial Bank)
        'HPG',   # Hoa Phat Group (Steel and construction materials)
        'VNM',   # Vinamilk (Vietnam Dairy Products Joint Stock Company)
        'GAS',   # PetroVietnam Gas (PetroVietnam Gas Joint Stock Corporation)
        'MSN',   # Masan Group (Consumer goods conglomerate)

        # 11-20: Large Cap Stocks
        'VHM',   # Vinhomes (Vinhomes Joint Stock Company - Real estate)
        'BID',   # BIDV (Bank for Investment and Development of Vietnam)
        'CTG',   # Vietinbank (Vietnam Joint Stock Commercial Bank for Industry and Trade)
        'VRE',   # VinRE (Vincom Retail Joint Stock Company)
        'PLX',   # Petrolimex (Vietnam National Petroleum Group)
        'HDB',   # HDBank (Ho Chi Minh City Development Joint Stock Commercial Bank)
        'MWG',   # Mobile World (Mobile World Investment Corporation - Retail)
        'SSI',   # SSI Securities (Saigon Securities Inc.)
        'SAB',   # Sabeco (Saigon Beer-Alcohol-Beverage Corporation)
        'POW',   # PetroVietnam Power (PetroVietnam Power Corporation)

        # 21-30: Mid-Large Cap Stocks
        'PDR',   # Phat Dat Real Estate Development Corporation
        'STB',   # Sacombank (Saigon Thuong Tin Commercial Joint Stock Bank)
        'VCI',   # VCI Securities (Vietcap Securities Joint Stock Company)
        'VIB',   # VIB (Vietnam International Commercial Joint Stock Bank)
        'GVR',   # Cao Su Dau Tien (Golden Victory Resources Corporation)
        'TPB',   # TPBank (Tien Phong Commercial Joint Stock Bank)
        'BCM',   # Investment and Industrial Development Corporation
        'ACB',   # Asia Commercial Bank (Asia Commercial Joint Stock Bank)
        'HVN',   # Vietnam Airlines (Vietnam Airlines Joint Stock Company)
        'VJC',   # Vietjet Air (VietJet Aviation Joint Stock Company)
    ]

    def __init__(self, db_manager, api_client: Optional[YFinanceAPI] = None):
        """
        Initialize VN adapter

        Args:
            db_manager: Database manager instance
            api_client: Optional YFinanceAPI instance (creates new if None)
        """
        super().__init__(db_manager, region_code='VN')

        self.yf_api = api_client or YFinanceAPI()
        self.parser = VNStockParser()
        self.default_tickers = self.DEFAULT_VN_TICKERS.copy()

        logger.info("✅ VNAdapter initialized (HOSE + HNX, yfinance)")

    def scan_stocks(self,
                   force_refresh: bool = False,
                   ticker_list: Optional[List[str]] = None,
                   max_count: Optional[int] = None) -> List[Dict]:
        """
        Scan Vietnamese stocks and save to database

        Args:
            force_refresh: Force refresh even if cached
            ticker_list: Specific tickers to scan (None = use DEFAULT_VN_TICKERS)
            max_count: Maximum number of stocks to scan

        Returns:
            List of successfully scanned stock dictionaries
        """
        logger.info("📊 Scanning Vietnamese stocks...")

        # Determine ticker list
        tickers = ticker_list if ticker_list else self.default_tickers

        if max_count:
            tickers = tickers[:max_count]

        logger.info(f"   Target: {len(tickers)} stocks")

        scanned_stocks = []
        failed_tickers = []

        for ticker in tickers:
            try:
                # Convert to yfinance format (add .VN suffix)
                yf_ticker = self.parser.denormalize_ticker(ticker)

                # Fetch ticker info
                info = self.yf_api.get_ticker_info(yf_ticker)

                if not info:
                    logger.warning(f"⚠️  No data for {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Parse to standardized format
                ticker_data = self.parser.parse_ticker_info(info)

                if not ticker_data:
                    logger.warning(f"⚠️  Failed to parse {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Filter common stocks (exclude REITs, preferred, ETFs)
                if not self.parser.filter_common_stocks(ticker_data):
                    logger.info(f"   Filtered out {ticker} (REIT/Preferred/ETF)")
                    continue

                # Save to database
                self.db.save_ticker(**ticker_data)
                scanned_stocks.append(ticker_data)

                logger.info(f"✅ {ticker}: {ticker_data['name']} ({ticker_data['sector']})")

            except Exception as e:
                logger.error(f"❌ Failed to scan {ticker}: {e}")
                failed_tickers.append(ticker)

        # Summary
        logger.info(f"\n📊 Scan Summary:")
        logger.info(f"   Success: {len(scanned_stocks)}")
        logger.info(f"   Failed: {len(failed_tickers)}")

        if failed_tickers:
            logger.warning(f"   Failed tickers: {', '.join(failed_tickers)}")

        return scanned_stocks

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for Vietnamese stocks

        Args:
            tickers: List of tickers (None = all active VN stocks in DB)
            days: Number of days of historical data

        Returns:
            Number of successfully updated stocks
        """
        logger.info(f"📈 Collecting OHLCV data ({days} days)...")

        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='VN', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️  No tickers to collect")
            return 0

        logger.info(f"   Target: {len(tickers)} stocks")

        success_count = 0
        failed_tickers = []

        for ticker in tickers:
            try:
                # Convert to yfinance format
                yf_ticker = self.parser.denormalize_ticker(ticker)

                # Fetch OHLCV data
                history = self.yf_api.get_ohlcv_data(yf_ticker, days=days)

                if history is None or history.empty:
                    logger.warning(f"⚠️  No OHLCV data for {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Parse to standardized format
                ohlcv_df = self.parser.parse_ohlcv_data(history, ticker)

                if ohlcv_df is None or ohlcv_df.empty:
                    logger.warning(f"⚠️  Failed to parse OHLCV for {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database using BaseAdapter method (auto-injects region)
                self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')
                success_count += 1

                logger.info(f"✅ {ticker}: {len(ohlcv_df)} days")

            except Exception as e:
                logger.error(f"❌ Failed to collect OHLCV for {ticker}: {e}")
                failed_tickers.append(ticker)

        # Summary
        logger.info(f"\n📈 OHLCV Collection Summary:")
        logger.info(f"   Success: {success_count}/{len(tickers)}")

        if failed_tickers:
            logger.warning(f"   Failed: {', '.join(failed_tickers)}")

        return success_count

    def collect_fundamentals(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data for Vietnamese stocks

        Args:
            tickers: List of tickers (None = all active VN stocks in DB)

        Returns:
            Number of successfully updated stocks
        """
        logger.info("💰 Collecting fundamental data...")

        # Get ticker list
        if tickers is None:
            db_tickers = self.db.get_tickers(region='VN', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in db_tickers]

        if not tickers:
            logger.warning("⚠️  No tickers to collect")
            return 0

        logger.info(f"   Target: {len(tickers)} stocks")

        success_count = 0
        failed_tickers = []

        for ticker in tickers:
            try:
                # Convert to yfinance format
                yf_ticker = self.parser.denormalize_ticker(ticker)

                # Fetch ticker info (contains fundamentals)
                info = self.yf_api.get_ticker_info(yf_ticker)

                if not info:
                    logger.warning(f"⚠️  No data for {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Parse fundamentals
                fundamentals = self.parser.parse_fundamentals(info, ticker)

                if not fundamentals:
                    logger.warning(f"⚠️  Failed to parse fundamentals for {ticker}")
                    failed_tickers.append(ticker)
                    continue

                # Save to database
                self.db.save_fundamentals(**fundamentals)
                success_count += 1

                pe = fundamentals.get('pe_ratio')
                pb = fundamentals.get('pb_ratio')
                logger.info(f"✅ {ticker}: P/E={pe:.2f if pe else 'N/A'}, P/B={pb:.2f if pb else 'N/A'}")

            except Exception as e:
                logger.error(f"❌ Failed to collect fundamentals for {ticker}: {e}")
                failed_tickers.append(ticker)

        # Summary
        logger.info(f"\n💰 Fundamentals Collection Summary:")
        logger.info(f"   Success: {success_count}/{len(tickers)}")

        if failed_tickers:
            logger.warning(f"   Failed: {', '.join(failed_tickers)}")

        return success_count

    def add_custom_ticker(self, ticker: str) -> bool:
        """
        Add a custom Vietnamese ticker to the default list

        Args:
            ticker: Vietnamese ticker code (e.g., "VCB", "FPT")

        Returns:
            True if successfully added and validated
        """
        try:
            # Normalize ticker
            normalized = self.parser.normalize_ticker(ticker)

            if not normalized:
                logger.error(f"❌ Invalid ticker format: {ticker}")
                return False

            # Check if already in default list
            if normalized in self.default_tickers:
                logger.info(f"ℹ️  {normalized} already in default list")
                return True

            # Validate by fetching info
            yf_ticker = self.parser.denormalize_ticker(normalized)
            info = self.yf_api.get_ticker_info(yf_ticker)

            if not info:
                logger.error(f"❌ Unable to fetch data for {normalized}")
                return False

            # Parse and save
            ticker_data = self.parser.parse_ticker_info(info)

            if not ticker_data:
                logger.error(f"❌ Failed to parse {normalized}")
                return False

            # Add to default list
            self.default_tickers.append(normalized)
            self.db.save_ticker(**ticker_data)

            logger.info(f"✅ Added {normalized}: {ticker_data['name']}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add {ticker}: {e}")
            return False

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Vietnamese ETFs (not implemented - minimal ETF market)

        Args:
            force_refresh: Force refresh even if cached

        Returns:
            Empty list (Vietnamese ETF market is underdeveloped)
        """
        logger.warning("⚠️  Vietnamese ETF scanning not implemented (minimal ETF market)")
        return []

    def collect_etf_ohlcv(self, days: int = 250) -> int:
        """
        Collect ETF OHLCV data (not implemented)

        Args:
            days: Number of days of historical data

        Returns:
            0 (not implemented)
        """
        logger.warning("⚠️  Vietnamese ETF OHLCV collection not implemented")
        return 0
