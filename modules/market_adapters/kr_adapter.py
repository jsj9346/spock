"""
Korea Market Adapter (KoreaAdapter)

Handles Korean stock market data collection from KRX and KIS APIs.

Data Sources:
- KRX Data API: Ticker scanning (no auth required)
- pykrx: Fallback ticker scanning
- KIS API: OHLCV data collection (OAuth 2.0)

Author: Spock Trading System
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from .base_adapter import BaseMarketAdapter
from ..api_clients import KRXDataAPI, PyKRXAPI, KISDomesticStockAPI, KISEtfAPI
from ..parsers import StockParser, ETFParser

logger = logging.getLogger(__name__)


class KoreaAdapter(BaseMarketAdapter):
    """
    Korea market data adapter

    Handles:
    1. Stock/ETF scanning via KRX Data API (fallback: pykrx)
    2. OHLCV collection via KIS API
    3. ETF enhanced data (tracking error, NAV comparison)
    4. Market tier detection (MAIN, NXT, KONEX)
    """

    def __init__(self, db_manager, kis_app_key: str, kis_app_secret: str):
        """
        Initialize Korea adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
            kis_app_key: KIS API App Key
            kis_app_secret: KIS API App Secret
        """
        super().__init__(db_manager, region_code='KR')

        # API clients
        self.krx_api = KRXDataAPI()
        self.pykrx_api = PyKRXAPI()
        self.kis_stock_api = KISDomesticStockAPI(kis_app_key, kis_app_secret)
        self.kis_etf_api = KISEtfAPI(kis_app_key, kis_app_secret)

        # Parsers
        self.stock_parser = StockParser()
        self.etf_parser = ETFParser()

    # ========================================
    # PHASE 1: TICKER DISCOVERY (SCANNING)
    # ========================================

    def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Korean stocks from KRX Data API (fallback: pykrx)

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from KRX Data API
        3. Fallback to pykrx if KRX fails
        4. Parse and enrich data
        5. Save to tickers + stock_details tables

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of stock ticker dictionaries
        """
        # Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='STOCK', ttl_hours=24)
            if cached:
                return cached

        logger.info(f"🔍 [KR] Scanning stocks from KRX Data API...")

        # Try KRX Data API first
        try:
            raw_stocks = self.krx_api.get_stock_list(market='ALL')
            logger.info(f"✅ [KR] KRX Data API: {len(raw_stocks)} stocks")
        except Exception as e:
            logger.warning(f"⚠️ [KR] KRX Data API failed: {e}")
            logger.info(f"🔄 [KR] Falling back to pykrx...")

            # Fallback to pykrx
            try:
                raw_stocks = self.pykrx_api.get_stock_list()
                logger.info(f"✅ [KR] pykrx: {len(raw_stocks)} stocks")
            except Exception as e2:
                logger.error(f"❌ [KR] pykrx fallback failed: {e2}")
                return []

        # Get sector classification map from KRX API (once for all stocks)
        sector_map = {}
        try:
            sector_map = self.krx_api.get_sector_classification(market='ALL')
            logger.info(f"📊 [KR] Sector classification map loaded: {len(sector_map)} stocks")
        except Exception as e:
            logger.warning(f"⚠️ [KR] Sector classification API failed: {e}")
            logger.info(f"🔄 [KR] Falling back to pykrx for sector info...")

        # Parse stocks
        stocks = []
        for raw_stock in raw_stocks:
            try:
                # Parse based on data source
                if raw_stock.get('data_source') == 'KRX Data API':
                    parsed = self.stock_parser.parse_krx_stock(raw_stock)
                else:  # pykrx
                    parsed = self.stock_parser.parse_pykrx_stock(raw_stock)

                ticker = parsed.get('ticker')

                # Strategy 1: Use KRX sector classification map (preferred - includes codes)
                if ticker and ticker in sector_map:
                    krx_sector_info = sector_map[ticker]

                    # Map KRX sector to GICS
                    krx_sector = krx_sector_info.get('sector')
                    if krx_sector:
                        gics_sector = self.pykrx_api._map_krx_to_gics(krx_sector)
                        parsed['sector'] = gics_sector

                    parsed['sector_code'] = krx_sector_info.get('sector_code')
                    parsed['industry'] = krx_sector_info.get('industry')
                    parsed['industry_code'] = krx_sector_info.get('industry_code')

                    logger.info(f"✅ [{ticker}] Sector from KRX API: {parsed.get('sector')} ({parsed.get('sector_code')})")

                # Strategy 2: Fallback to pykrx (slower but more reliable for sector names)
                elif ticker:
                    try:
                        sector_info = self.pykrx_api.get_stock_sector_info(ticker)
                        if sector_info:
                            # Update parsed data with sector info
                            if sector_info.get('sector'):
                                parsed['sector'] = sector_info['sector']
                            if sector_info.get('industry'):
                                parsed['industry'] = sector_info['industry']
                            if sector_info.get('sector_code'):
                                parsed['sector_code'] = sector_info['sector_code']
                            if sector_info.get('industry_code'):
                                parsed['industry_code'] = sector_info['industry_code']
                            if sector_info.get('par_value'):
                                parsed['par_value'] = sector_info['par_value']
                    except Exception as e:
                        logger.warning(f"⚠️ [{ticker}] Sector enrichment failed: {e}")

                # Add lot_size for Korea
                parsed['lot_size'] = 1  # Korea: 1 share per lot

                stocks.append(parsed)

            except Exception as e:
                logger.error(f"❌ [{raw_stock.get('ticker', 'UNKNOWN')}] Parse failed: {e}")

        # Enrich with market cap data (if available)
        try:
            market_cap_data = self.krx_api.get_market_cap_data(market='ALL')
            market_cap_map = {item['ticker']: item for item in market_cap_data}

            for stock in stocks:
                ticker = stock['ticker']
                if ticker in market_cap_map:
                    cap_data = self.stock_parser.parse_market_cap_data(market_cap_map[ticker])
                    stock.update(cap_data)

            logger.info(f"💰 [KR] Enriched {len(market_cap_map)} stocks with market cap data")

        except Exception as e:
            logger.warning(f"⚠️ [KR] Market cap enrichment failed: {e}")

        # Save to database
        if stocks:
            self._save_tickers_to_db(stocks, asset_type='STOCK')

        logger.info(f"✅ [KR] Stock scanning complete: {len(stocks)} stocks")
        return stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Korean ETFs from KRX Data API

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from KRX Data API
        3. Parse and enrich data
        4. Save to tickers + etf_details tables

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ETF ticker dictionaries
        """
        # Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='ETF', ttl_hours=24)
            if cached:
                return cached

        logger.info(f"🔍 [KR] Scanning ETFs from KRX Data API...")

        # Fetch from KRX Data API
        try:
            raw_etfs = self.krx_api.get_etf_list()
            logger.info(f"✅ [KR] KRX Data API: {len(raw_etfs)} ETFs")
        except Exception as e:
            logger.error(f"❌ [KR] KRX ETF API failed: {e}")
            return []

        # Enrich ETF data with required fields
        # (KRX API already returns normalized data, just add required fields)
        etfs = []
        for etf in raw_etfs:
            try:
                # Add required fields for database
                etf['asset_type'] = 'ETF'
                etf['region'] = 'KR'
                etf['currency'] = 'KRW'
                etf['exchange'] = 'KOSPI'  # All ETFs trade on KOSPI
                etf['lot_size'] = 1  # Korea: 1 share per lot
                etf['is_active'] = True

                # Add parser-based classification
                etf['geographic_region'] = self.etf_parser._detect_region(etf['name'])
                etf['sector_theme'] = self.etf_parser._detect_sector(etf['name'])
                etf['fund_type'] = self.etf_parser._detect_fund_type(etf['name'])

                etfs.append(etf)

            except Exception as e:
                logger.error(f"❌ [{etf.get('ticker', 'UNKNOWN')}] Enrichment failed: {e}")

        # Save to database
        if etfs:
            self._save_tickers_to_db(etfs, asset_type='ETF')

        logger.info(f"✅ [KR] ETF scanning complete: {len(etfs)} ETFs")
        return etfs

    # ========================================
    # PHASE 2: OHLCV DATA COLLECTION
    # ========================================

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for Korean stocks via KIS API

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Fetch OHLCV from KIS API
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table

        Args:
            tickers: List of ticker codes (None = all stocks)
            days: Historical days to collect (default: 250)

        Returns:
            Number of stocks successfully updated
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='KR', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [KR] No stocks to collect")
            return 0

        logger.info(f"📊 [KR] Collecting OHLCV for {len(tickers)} stocks ({days} days)...")

        success_count = 0

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch OHLCV
                ohlcv_df = self.kis_stock_api.get_ohlcv(ticker, days=days)

                if ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] No OHLCV data")
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')

                success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 [KR] Progress: {idx}/{len(tickers)} stocks")

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")

        logger.info(f"✅ [KR] Stock OHLCV complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for Korean ETFs via KIS ETF API

        Args:
            tickers: List of ETF ticker codes (None = all ETFs)
            days: Historical days to collect

        Returns:
            Number of ETFs successfully updated
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [KR] No ETFs to collect")
            return 0

        logger.info(f"📊 [KR] Collecting OHLCV for {len(tickers)} ETFs ({days} days)...")

        success_count = 0

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch OHLCV using stock API (ETFs trade on same exchanges with identical data format)
                ohlcv_df = self.kis_stock_api.get_ohlcv(ticker, days=days)

                if ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] No ETF OHLCV data")
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')

                success_count += 1

                if idx % 50 == 0:
                    logger.info(f"📊 [KR] Progress: {idx}/{len(tickers)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] ETF OHLCV collection failed: {e}")

        logger.info(f"✅ [KR] ETF OHLCV complete: {success_count}/{len(tickers)} ETFs")
        return success_count

    # ========================================
    # ETF-SPECIFIC ENHANCED DATA
    # ========================================

    def collect_etf_tracking_error(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect ETF tracking error data via KIS ETF/ETN API

        Uses new KIS API endpoint: /uapi/etfetn/v1/quotations/inquire-price
        TR_ID: FHPST02400000

        Directly provides period-based tracking error:
        - 20d, 60d, 120d, 250d averages

        Args:
            tickers: List of ETF ticker codes (None = all ETFs)

        Returns:
            Number of ETFs successfully updated
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [KR] No ETFs for tracking error")
            return 0

        logger.info(f"📊 [KR] Collecting tracking error for {len(tickers)} ETFs...")

        success_count = 0
        now = datetime.now().isoformat()

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch tracking error data directly from ETF/ETN API
                tracking_error = self.kis_etf_api.get_etf_tracking_error(ticker)

                if not tracking_error:
                    logger.warning(f"⚠️ [{ticker}] No tracking error data")
                    continue

                # Update etf_details table
                self.db.update_etf_details(ticker, {
                    'tracking_error_20d': tracking_error.get('tracking_error_20d'),
                    'tracking_error_60d': tracking_error.get('tracking_error_60d'),
                    'tracking_error_120d': tracking_error.get('tracking_error_120d'),
                    'tracking_error_250d': tracking_error.get('tracking_error_250d'),
                    'last_updated': now,
                })

                success_count += 1

                if idx % 50 == 0:
                    logger.info(f"📊 [KR] Progress: {idx}/{len(tickers)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Tracking error collection failed: {e}")

        logger.info(f"✅ [KR] Tracking error complete: {success_count}/{len(tickers)} ETFs")
        return success_count

    def collect_par_value(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect par value (액면가) data via KIS Stock Info API

        Collects: par_value, listing_shares, market_cap

        Args:
            tickers: List of stock ticker codes (None = all stocks)

        Returns:
            Number of stocks successfully updated
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='KR', asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [KR] No stocks for par value collection")
            return 0

        logger.info(f"📊 [KR] Collecting par value for {len(tickers)} stocks...")

        success_count = 0
        now = datetime.now().isoformat()

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch stock info from KIS API
                stock_info = self.kis_stock_api.get_stock_info(ticker)

                if not stock_info:
                    logger.warning(f"⚠️ [{ticker}] No stock info")
                    continue

                # Update stock_details table
                updates = {}
                if stock_info.get('par_value'):
                    updates['par_value'] = stock_info['par_value']

                if updates:
                    self.db.update_stock_details(ticker, updates)
                    success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 [KR] Progress: {idx}/{len(tickers)} stocks")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Par value collection failed: {e}")

        logger.info(f"✅ [KR] Par value collection complete: {success_count}/{len(tickers)} stocks")
        return success_count

    def collect_etf_details(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect ETF detailed information via KIS ETF API

        Collects: issuer, tracking_index, expense_ratio, listed_shares

        Args:
            tickers: List of ETF ticker codes (None = all ETFs)

        Returns:
            Number of ETFs successfully updated
        """
        # Get ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        if not tickers:
            logger.warning(f"⚠️ [KR] No ETFs for details")
            return 0

        logger.info(f"📊 [KR] Collecting details for {len(tickers)} ETFs...")

        success_count = 0
        now = datetime.now().isoformat()

        for idx, ticker in enumerate(tickers, 1):
            try:
                # Fetch ETF details
                raw_details = self.kis_etf_api.get_etf_details(ticker)

                if not raw_details:
                    logger.warning(f"⚠️ [{ticker}] No ETF details")
                    continue

                # Parse details
                parsed_details = self.etf_parser.parse_kis_etf_details(raw_details)

                if not parsed_details:
                    logger.warning(f"⚠️ [{ticker}] ETF details parsing failed")
                    continue

                # Update etf_details table
                self.db.update_etf_details(ticker, {
                    'issuer': parsed_details.get('issuer'),
                    'tracking_index': parsed_details.get('tracking_index'),
                    'expense_ratio': parsed_details.get('expense_ratio'),
                    'listed_shares': parsed_details.get('listed_shares'),
                    'last_updated': now,
                })

                success_count += 1

                if idx % 50 == 0:
                    logger.info(f"📊 [KR] Progress: {idx}/{len(tickers)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] ETF details collection failed: {e}")

        logger.info(f"✅ [KR] ETF details complete: {success_count}/{len(tickers)} ETFs")
        return success_count

    # ========================================
    # UTILITIES
    # ========================================

    def _detect_market_tier(self, ticker: str) -> str:
        """
        Detect market tier (MAIN, NXT, KONEX) for a stock

        Args:
            ticker: Stock ticker code

        Returns:
            Market tier string
        """
        try:
            ticker_data = self.db.get_ticker(ticker)
            return ticker_data.get('market_tier', 'MAIN')
        except Exception as e:
            logger.warning(f"⚠️ [{ticker}] Market tier detection failed: {e}")
            return 'MAIN'

    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all API connections

        Returns:
            Dictionary with health status for each API
        """
        logger.info(f"🏥 [KR] Running health check...")

        health = {
            'krx_data_api': False,
            'pykrx_api': False,
            'kis_stock_api': False,
            'kis_etf_api': False,
        }

        # KRX Data API
        try:
            health['krx_data_api'] = self.krx_api.check_connection()
        except Exception as e:
            logger.warning(f"⚠️ [KR] KRX Data API health check failed: {e}")

        # pykrx API
        try:
            health['pykrx_api'] = self.pykrx_api.check_connection()
        except Exception as e:
            logger.warning(f"⚠️ [KR] pykrx health check failed: {e}")

        # KIS Stock API
        try:
            health['kis_stock_api'] = self.kis_stock_api.check_connection()
        except Exception as e:
            logger.warning(f"⚠️ [KR] KIS Stock API health check failed: {e}")

        # KIS ETF API
        try:
            health['kis_etf_api'] = self.kis_etf_api.check_connection()
        except Exception as e:
            logger.warning(f"⚠️ [KR] KIS ETF API health check failed: {e}")

        # Summary
        all_healthy = all(health.values())
        status = "✅ HEALTHY" if all_healthy else "⚠️ DEGRADED"
        logger.info(f"🏥 [KR] Health check: {status}")
        logger.info(f"   - KRX Data API: {'✅' if health['krx_data_api'] else '❌'}")
        logger.info(f"   - pykrx API: {'✅' if health['pykrx_api'] else '❌'}")
        logger.info(f"   - KIS Stock API: {'✅' if health['kis_stock_api'] else '❌'}")
        logger.info(f"   - KIS ETF API: {'✅' if health['kis_etf_api'] else '❌'}")

        return health
