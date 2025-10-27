"""
Base Market Adapter - Abstract Base Class for Regional Markets

All regional adapters (KoreaAdapter, USAdapter, etc.) inherit from this class.

Each adapter handles:
1. Ticker Discovery (scanning) → tickers table
2. OHLCV Collection (data collection) → ohlcv_data table
3. Enhanced Data (fundamentals, ETF-specific) → various tables

Author: Spock Trading System
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseMarketAdapter(ABC):
    """
    Abstract base adapter for regional markets

    Each regional adapter handles:
    1. Ticker Discovery (scanning) → tickers table
    2. OHLCV Collection (data collection) → ohlcv_data table
    3. Enhanced Data (fundamentals, ETF-specific) → various tables

    Shared resources:
    - Database manager
    - Region code
    - Common caching logic
    - Common database operations
    """

    def __init__(self, db_manager, region_code: str):
        """
        Initialize regional adapter

        Args:
            db_manager: SQLiteDatabaseManager instance
            region_code: 'KR', 'US', 'CN', 'HK', 'JP', 'VN'
        """
        self.db = db_manager
        self.region_code = region_code

    # ========================================
    # PHASE 1: TICKER DISCOVERY (SCANNING)
    # ========================================

    @abstractmethod
    def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """
        Discover stock tickers and populate tickers + stock_details tables

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from region-specific data sources
        3. Apply region-specific filters
        4. Parse and enrich data
        5. Save to tickers + stock_details tables

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of stock ticker dictionaries

        Example return:
            [
                {
                    'ticker': '005930',
                    'name': '삼성전자',
                    'exchange': 'KOSPI',
                    'market_tier': 'MAIN',
                    'region': 'KR',
                    'currency': 'KRW',
                    'market_cap': 500000000000000,
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Discover ETF tickers and populate tickers + etf_details tables

        Similar workflow to scan_stocks() but for ETFs

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ETF ticker dictionaries
        """
        pass

    # ========================================
    # PHASE 2: OHLCV DATA COLLECTION
    # ========================================

    @abstractmethod
    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Collect OHLCV data for stocks and populate ohlcv_data table

        Workflow:
        1. Get ticker list (from DB if not provided)
        2. Fetch OHLCV from region-specific API
        3. Calculate technical indicators (MA, RSI, MACD, BB, ATR)
        4. Save to ohlcv_data table

        Args:
            tickers: List of ticker codes (None = all stocks in region)
            days: Historical days to collect (default: 250 for MA200)

        Returns:
            Number of stocks successfully updated
        """
        pass

    @abstractmethod
    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Collect OHLCV data for ETFs and populate ohlcv_data table

        Similar to collect_stock_ohlcv() but for ETFs

        Args:
            tickers: List of ETF ticker codes (None = all ETFs in region)
            days: Historical days to collect

        Returns:
            Number of ETFs successfully updated
        """
        pass

    # ========================================
    # PHASE 3: ENHANCED DATA (OPTIONAL)
    # ========================================

    def collect_fundamentals(self, tickers: Optional[List[str]] = None) -> int:
        """
        Collect fundamental data (market cap, P/E, P/B, dividend yield, etc.)

        Optional: Can be implemented by regional adapters if data available

        Args:
            tickers: List of ticker codes (None = all)

        Returns:
            Number of tickers updated
        """
        logger.info(f"[{self.region_code}] Fundamentals collection not implemented")
        return 0

    # ========================================
    # SHARED UTILITIES (COMMON LOGIC)
    # ========================================

    def _load_tickers_from_cache(self,
                                 asset_type: str = 'STOCK',
                                 ttl_hours: int = 24) -> Optional[List[Dict]]:
        """
        Load tickers from SQLite cache with TTL check

        Shared logic for all regional adapters

        Args:
            asset_type: 'STOCK' or 'ETF'
            ttl_hours: Cache time-to-live in hours (default: 24)

        Returns:
            List of cached tickers or None if cache miss/expired
        """
        try:
            # Check last update time
            last_update = self.db.get_last_update_time(
                region=self.region_code,
                asset_type=asset_type
            )

            if not last_update:
                return None

            # Check TTL
            from datetime import datetime, timedelta
            age = datetime.now() - last_update

            if age > timedelta(hours=ttl_hours):
                logger.info(f"[{self.region_code}] Cache expired ({age.total_seconds()/3600:.1f}h)")
                return None

            # Load tickers
            tickers = self.db.get_tickers(
                region=self.region_code,
                asset_type=asset_type,
                is_active=True
            )

            logger.info(f"✅ [{self.region_code}] Cache hit: {len(tickers)} {asset_type}s")
            return tickers

        except Exception as e:
            logger.warning(f"⚠️ [{self.region_code}] Cache load failed: {e}")
            return None

    def _save_tickers_to_db(self, tickers: List[Dict], asset_type: str = 'STOCK'):
        """
        Save tickers to database (tickers + stock_details/etf_details tables)

        Shared logic for all regional adapters

        Args:
            tickers: List of ticker dictionaries
            asset_type: 'STOCK' or 'ETF'
        """
        from datetime import datetime

        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")

        # Delete existing tickers for this region + asset_type
        self.db.delete_tickers(region=self.region_code, asset_type=asset_type)

        for ticker_data in tickers:
            try:
                # Validate lot_size before insertion
                lot_size = ticker_data.get('lot_size', 1)
                if not self._validate_lot_size(lot_size, self.region_code):
                    logger.warning(
                        f"[{ticker_data['ticker']}] Invalid lot_size: {lot_size}, using default"
                    )
                    lot_size = self._get_default_lot_size(self.region_code)

                # 1. Insert into tickers table
                self.db.insert_ticker({
                    'ticker': ticker_data['ticker'],
                    'name': ticker_data['name'],
                    'name_eng': ticker_data.get('name_eng'),
                    'exchange': ticker_data['exchange'],
                    'region': self.region_code,
                    'currency': ticker_data['currency'],
                    'asset_type': asset_type,
                    'listing_date': ticker_data.get('listing_date'),
                    'lot_size': lot_size,
                    'is_active': True,
                    'created_at': now,
                    'last_updated': now,
                    'data_source': ticker_data.get('data_source', 'Unknown'),
                })

                # 2. Insert into asset-specific table
                if asset_type == 'STOCK':
                    self.db.insert_stock_details({
                        'ticker': ticker_data['ticker'],
                        'region': self.region_code,  # ✅ Auto-inject region from adapter
                        'sector': ticker_data.get('sector'),
                        'sector_code': ticker_data.get('sector_code'),
                        'industry': ticker_data.get('industry'),
                        'industry_code': ticker_data.get('industry_code'),
                        'is_spac': ticker_data.get('is_spac', False),
                        'is_preferred': ticker_data.get('is_preferred', False),
                        'par_value': ticker_data.get('par_value'),
                        'created_at': now,
                        'last_updated': now,
                    })
                elif asset_type == 'ETF':
                    self.db.insert_etf_details({
                        'ticker': ticker_data['ticker'],
                        'issuer': ticker_data.get('issuer'),
                        'tracking_index': ticker_data.get('tracking_index'),
                        'expense_ratio': ticker_data.get('expense_ratio'),
                        'created_at': now,
                        'last_updated': now,
                    })

                # 3. Insert into ticker_fundamentals (if available)
                if ticker_data.get('market_cap') or ticker_data.get('close_price'):
                    self.db.insert_ticker_fundamentals({
                        'ticker': ticker_data['ticker'],
                        'date': today,
                        'period_type': 'DAILY',
                        'market_cap': ticker_data.get('market_cap'),
                        'close_price': ticker_data.get('close_price'),
                        'created_at': now,
                        'data_source': ticker_data.get('data_source', 'Unknown'),
                    })

            except Exception as e:
                logger.error(f"❌ [{ticker_data['ticker']}] Save failed: {e}")

        logger.info(f"💾 [{self.region_code}] Saved {len(tickers)} {asset_type}s to DB")

    def _calculate_technical_indicators(self, ohlcv_df):
        """
        Calculate technical indicators from OHLCV DataFrame

        Shared logic using pandas-ta

        Args:
            ohlcv_df: pandas DataFrame with columns [open, high, low, close, volume]

        Returns:
            DataFrame with added indicator columns
        """
        import pandas_ta as ta

        # Moving Averages
        ohlcv_df['ma5'] = ta.sma(ohlcv_df['close'], length=5)
        ohlcv_df['ma20'] = ta.sma(ohlcv_df['close'], length=20)
        ohlcv_df['ma60'] = ta.sma(ohlcv_df['close'], length=60)
        ohlcv_df['ma120'] = ta.sma(ohlcv_df['close'], length=120)
        ohlcv_df['ma200'] = ta.sma(ohlcv_df['close'], length=200)

        # RSI
        ohlcv_df['rsi_14'] = ta.rsi(ohlcv_df['close'], length=14)

        # MACD
        macd = ta.macd(ohlcv_df['close'])
        if macd is not None:
            ohlcv_df['macd'] = macd['MACD_12_26_9']
            ohlcv_df['macd_signal'] = macd['MACDs_12_26_9']
            ohlcv_df['macd_hist'] = macd['MACDh_12_26_9']

        # Bollinger Bands
        bb = ta.bbands(ohlcv_df['close'], length=20)
        if bb is not None and not bb.empty:
            # pandas-ta column names vary by version
            bb_cols = bb.columns.tolist()
            if len(bb_cols) >= 3:
                ohlcv_df['bb_lower'] = bb.iloc[:, 0]   # Lower band
                ohlcv_df['bb_middle'] = bb.iloc[:, 1]  # Middle band (SMA)
                ohlcv_df['bb_upper'] = bb.iloc[:, 2]   # Upper band

        # ATR
        ohlcv_df['atr_14'] = ta.atr(ohlcv_df['high'], ohlcv_df['low'], ohlcv_df['close'], length=14)

        return ohlcv_df

    def _save_ohlcv_to_db(self, ticker: str, ohlcv_df, period_type: str = 'DAILY'):
        """
        Save OHLCV DataFrame to ohlcv_data table with region information

        Shared method used by all regional adapters to ensure consistent
        region propagation to database layer.

        This method automatically injects the region code from self.region_code
        when calling db.insert_ohlcv_bulk(), ensuring all OHLCV data is tagged
        with the correct market region.

        Args:
            ticker: Ticker code
            ohlcv_df: OHLCV DataFrame with technical indicators
            period_type: 'DAILY', 'WEEKLY', 'MONTHLY'

        Usage Example:
            # In regional adapter (KoreaAdapter, USAdapterKIS, etc.)
            ohlcv_df = self.api.get_ohlcv(ticker, days=250)
            ohlcv_df = self._calculate_technical_indicators(ohlcv_df)
            self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')
        """
        import pandas as pd

        # Convert period_type to timeframe ('DAILY' -> 'D', 'WEEKLY' -> 'W', 'MONTHLY' -> 'M')
        timeframe_map = {'DAILY': 'D', 'WEEKLY': 'W', 'MONTHLY': 'M'}
        timeframe = timeframe_map.get(period_type, 'D')

        # Use bulk insert method from db_manager with automatic region injection
        inserted_count = self.db.insert_ohlcv_bulk(
            ticker,
            ohlcv_df,
            timeframe=timeframe,
            region=self.region_code  # ✅ Auto-inject region from adapter
        )

        if inserted_count > 0:
            logger.info(f"✅ [{ticker}] {inserted_count} OHLCV rows saved (region={self.region_code})")
        else:
            logger.warning(f"⚠️ [{ticker}] No OHLCV rows saved")

    # ========================================
    # LOT SIZE VALIDATION (Phase 7: 2025-10-17)
    # ========================================

    def _validate_lot_size(self, lot_size: Optional[int], region: str) -> bool:
        """
        Validate lot_size before storage

        Args:
            lot_size: Trading unit (shares per lot)
            region: Region code (KR, US, CN, HK, JP, VN)

        Returns:
            True if valid, False otherwise
        """
        if lot_size is None:
            return True  # NULL allowed

        if lot_size <= 0:
            return False  # Must be positive

        # Region-specific validation
        valid_ranges = {
            'KR': (1, 1),           # Only 1
            'US': (1, 1),           # Only 1
            'CN': (100, 100),       # Only 100
            'JP': (1, 10000),       # Variable (1, 100, 1000, 10000) - Post-2018 TSE reform
            'VN': (100, 100),       # Only 100
            'HK': (100, 2000),      # Variable (100-2000)
        }

        min_lot, max_lot = valid_ranges.get(region, (1, 999999))
        return min_lot <= lot_size <= max_lot

    def _get_default_lot_size(self, region: str) -> int:
        """
        Get default lot_size for region

        Args:
            region: Region code (KR, US, CN, HK, JP, VN)

        Returns:
            Default lot_size for region
        """
        defaults = {
            'KR': 1,
            'US': 1,
            'CN': 100,
            'HK': 500,   # Conservative mid-range default for HK
            'JP': 100,
            'VN': 100,
        }

        return defaults.get(region, 1)
