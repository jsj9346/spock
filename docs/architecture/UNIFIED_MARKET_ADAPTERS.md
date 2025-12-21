# Unified Market Adapters Architecture

## 문서 정보

- **작성일**: 2024-01-XX
- **버전**: 2.0 (Region-Based Architecture 개선)
- **대상**: Spock Trading System
- **목적**: Scanner와 Data Collector 통합 아키텍처 설계

---

## 1. Executive Summary

### 1.1 핵심 결정

**기존 제안 (분리)**:
- `scanner_adapters/` (ticker discovery) + `market_adapters/` (OHLCV collection)
- 6개 지역 × 2개 adapter types = **12개 adapter 모듈**

**최종 결정 (통합)**:
- 단일 `market_adapters/` 디렉토리
- 각 regional adapter가 scanning + data collection 모두 처리
- 6개 지역 × 1개 adapter = **6개 adapter 모듈 (50% 감소)**

### 1.2 설계 근거

**Scanner와 Data Collector는 Sequential Phases**:
```
Phase 1: Scanner → Ticker Discovery → tickers 테이블
Phase 2: Data Collector → OHLCV Fetching → ohlcv_data 테이블
```

**동일 지역 = 동일 리소스 사용**:
- API Clients: KRX API, KIS API
- Parsers: stock_parser, etf_parser
- Database: 같은 SQLite connection

**결론**: 분리할 이유가 없음 → **통합이 정답**

---

## 2. 최종 아키텍처

### 2.1 디렉토리 구조

```
modules/
├── market_adapters/                  # 📍 Regional adapters (단일 소스)
│   ├── __init__.py
│   ├── base_adapter.py               # Abstract base class
│   ├── kr_adapter.py                 # Korea (scan + collect + ETF)
│   ├── us_adapter.py                 # US (scan + collect + ETF)
│   ├── cn_adapter.py                 # China (scan + collect)
│   ├── hk_adapter.py                 # Hong Kong (scan + collect)
│   ├── jp_adapter.py                 # Japan (scan + collect)
│   └── vn_adapter.py                 # Vietnam (scan + collect)
│
├── api_clients/                      # 🔌 API wrappers (shared)
│   ├── __init__.py
│   ├── kis_domestic_stock_api.py     # KIS 국내주식 API
│   ├── kis_etf_api.py                # KIS ETF API
│   ├── kis_overseas_stock_api.py     # KIS 해외주식 API
│   ├── krx_data_api.py               # KRX Data API (Korea)
│   ├── pykrx_api.py                  # pykrx fallback (Korea)
│   ├── yahoo_finance_api.py          # Yahoo Finance (US/global)
│   └── sec_edgar_api.py              # SEC EDGAR (US official)
│
├── parsers/                          # 🔄 Data transformers (shared)
│   ├── __init__.py
│   ├── stock_parser.py               # Stock data normalization
│   └── etf_parser.py                 # ETF data normalization
│
├── scanner.py                        # 🎯 Thin wrapper → delegates to adapters
├── data_collector.py                 # 🎯 Thin wrapper → delegates to adapters
└── db_manager_sqlite.py              # 💾 Database layer (unchanged)
```

### 2.2 모듈 수 비교

| 구조 | Adapter 모듈 수 | API Client 모듈 수 | Parser 모듈 수 | 총합 |
|------|----------------|-------------------|---------------|------|
| **분리 (기존 제안)** | 12 (6×2) | 6 | 2 | **20** |
| **통합 (최종)** | 6 (6×1) | 6 | 2 | **14** |

**결과**: 30% 모듈 감소

---

## 3. 핵심 컴포넌트 설계

### 3.1 Base Adapter (Abstract Class)

```python
# modules/market_adapters/base_adapter.py

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
                # 1. Insert into tickers table
                self.db.insert_ticker({
                    'ticker': ticker_data['ticker'],
                    'name': ticker_data['name'],
                    'name_eng': ticker_data.get('name_eng'),
                    'exchange': ticker_data['exchange'],
                    'market_tier': ticker_data.get('market_tier', 'MAIN'),
                    'region': self.region_code,
                    'currency': ticker_data['currency'],
                    'asset_type': asset_type,
                    'listing_date': ticker_data.get('listing_date'),
                    'is_active': True,
                    'created_at': now,
                    'last_updated': now,
                    'data_source': ticker_data.get('data_source', 'Unknown'),
                })

                # 2. Insert into asset-specific table
                if asset_type == 'STOCK':
                    self.db.insert_stock_details({
                        'ticker': ticker_data['ticker'],
                        'sector': ticker_data.get('sector'),
                        'industry': ticker_data.get('industry'),
                        'is_preferred': ticker_data.get('is_preferred', False),
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
        if bb is not None:
            ohlcv_df['bb_upper'] = bb['BBU_20_2.0']
            ohlcv_df['bb_middle'] = bb['BBM_20_2.0']
            ohlcv_df['bb_lower'] = bb['BBL_20_2.0']

        # ATR
        ohlcv_df['atr_14'] = ta.atr(ohlcv_df['high'], ohlcv_df['low'], ohlcv_df['close'], length=14)

        return ohlcv_df
```

### 3.2 Korea Adapter (Concrete Implementation)

```python
# modules/market_adapters/kr_adapter.py

from .base_adapter import BaseMarketAdapter
from api_clients.krx_data_api import KRXDataAPI
from api_clients.kis_domestic_stock_api import KISDomesticStockAPI
from api_clients.kis_etf_api import KISEtfAPI
from api_clients.pykrx_api import PyKRXAPI
from parsers.stock_parser import StockParser
from parsers.etf_parser import ETFParser
import logging
import time

logger = logging.getLogger(__name__)

class KoreaAdapter(BaseMarketAdapter):
    """
    Korea market adapter (KOSPI, KOSDAQ, NXT)

    Handles:
    - Stock scanning (KRX Data API → tickers table)
    - Stock OHLCV collection (KIS API → ohlcv_data table)
    - ETF scanning (KRX Data API → tickers + etf_details tables)
    - ETF OHLCV collection (KIS ETF API → ohlcv_data table)
    - ETF enhanced data (AUM, tracking error, etc.)
    """

    def __init__(self, db_manager, kis_config: Dict):
        super().__init__(db_manager, region_code='KR')

        # API Clients (shared across all methods)
        self.krx_api = KRXDataAPI()
        self.kis_stock_api = KISDomesticStockAPI(**kis_config)
        self.kis_etf_api = KISEtfAPI(**kis_config)
        self.pykrx_api = PyKRXAPI()  # Fallback

        # Parsers
        self.stock_parser = StockParser()
        self.etf_parser = ETFParser()

    # ========================================
    # PHASE 1: SCANNING (TICKER DISCOVERY)
    # ========================================

    def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """
        Korea stock scanning

        Data sources (priority order):
        1. KRX Data API (official, no auth, real-time)
        2. pykrx (fallback, rate-limited)

        Filters:
        - Market cap >= 100억원
        - Exclude KONEX
        - Exclude ETF/ETN

        Returns:
            List of stock dictionaries
        """
        # Step 1: Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='STOCK')
            if cached:
                return cached

        # Step 2: Fetch from KRX Data API
        logger.info(f"🔄 [KR] Fetching stocks from KRX Data API...")

        try:
            raw_stocks = self.krx_api.get_stock_list()
            data_source = 'KRX Data API'
        except Exception as e:
            logger.error(f"❌ KRX Data API failed: {e}")
            logger.info("🔄 Fallback to pykrx...")
            raw_stocks = self.pykrx_api.get_stock_list()
            data_source = 'pykrx'

        # Step 3: Parse and filter
        stocks = []
        for item in raw_stocks:
            try:
                # Parse
                parsed = self.stock_parser.parse_krx_stock(item)

                # Filter 1: Market cap threshold
                if parsed.get('market_cap', 0) < 10_000_000_000:  # 100억원
                    continue

                # Filter 2: Exclude KONEX
                if parsed.get('exchange') == 'KONEX':
                    continue

                # Filter 3: Exclude ETF/ETN
                name = parsed.get('name', '')
                if any(kw in name for kw in ['ETF', 'ETN', 'KODEX', 'TIGER', 'KBSTAR']):
                    continue

                # Enrich
                parsed['region'] = 'KR'
                parsed['currency'] = 'KRW'
                parsed['market_tier'] = self._detect_market_tier(parsed)
                parsed['data_source'] = data_source

                stocks.append(parsed)

            except Exception as e:
                logger.error(f"❌ Parse failed: {item.get('ticker', 'UNKNOWN')} - {e}")

        # Step 4: Save to database
        self._save_tickers_to_db(stocks, asset_type='STOCK')

        logger.info(f"✅ [KR] {len(stocks)} stocks scanned")
        return stocks

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Korea ETF scanning

        Data source: KRX Data API (1,029 ETFs)

        Returns:
            List of ETF dictionaries
        """
        # Step 1: Check cache
        if not force_refresh:
            cached = self._load_tickers_from_cache(asset_type='ETF')
            if cached:
                return cached

        # Step 2: Fetch from KRX Data API
        logger.info(f"🔄 [KR] Fetching ETFs from KRX Data API...")

        try:
            raw_etfs = self.krx_api.get_etf_list()
            data_source = 'KRX Data API'
        except Exception as e:
            logger.error(f"❌ KRX ETF API failed: {e}")
            return []

        # Step 3: Parse
        etfs = []
        for item in raw_etfs:
            try:
                parsed = self.etf_parser.parse_krx_etf(item)

                # Enrich
                parsed['region'] = 'KR'
                parsed['currency'] = 'KRW'
                parsed['market_tier'] = 'MAIN'  # ETFs currently on main market
                parsed['data_source'] = data_source

                etfs.append(parsed)

            except Exception as e:
                logger.error(f"❌ ETF parse failed: {item.get('ticker', 'UNKNOWN')} - {e}")

        # Step 4: Save to database
        self._save_tickers_to_db(etfs, asset_type='ETF')

        logger.info(f"✅ [KR] {len(etfs)} ETFs scanned")
        return etfs

    # ========================================
    # PHASE 2: OHLCV COLLECTION
    # ========================================

    def collect_stock_ohlcv(self,
                           tickers: Optional[List[str]] = None,
                           days: int = 250) -> int:
        """
        Korea stock OHLCV collection

        Data source: KIS Domestic Stock API

        Args:
            tickers: Stock ticker codes (None = all KR stocks)
            days: Historical days (default: 250 for MA200)

        Returns:
            Number of stocks updated
        """
        # Get tickers
        if tickers is None:
            tickers = self.db.get_stock_tickers(region='KR')

        logger.info(f"🔄 [KR] Collecting OHLCV for {len(tickers)} stocks ({days} days)...")

        updated_count = 0
        for ticker in tickers:
            try:
                # Fetch OHLCV
                ohlcv_df = self.kis_stock_api.get_ohlcv(ticker, days=days)

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self.db.insert_ohlcv_bulk(ticker, ohlcv_df, timeframe='D')

                updated_count += 1

                # Rate limiting (20 req/sec)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")

        logger.info(f"✅ [KR] {updated_count}/{len(tickers)} stocks OHLCV collected")
        return updated_count

    def collect_etf_ohlcv(self,
                         tickers: Optional[List[str]] = None,
                         days: int = 250) -> int:
        """
        Korea ETF OHLCV collection

        Data source: KIS ETF API

        Args:
            tickers: ETF ticker codes (None = all KR ETFs)
            days: Historical days

        Returns:
            Number of ETFs updated
        """
        # Get tickers
        if tickers is None:
            tickers = self.db.get_etf_tickers(region='KR')

        logger.info(f"🔄 [KR] Collecting OHLCV for {len(tickers)} ETFs ({days} days)...")

        updated_count = 0
        for ticker in tickers:
            try:
                # Fetch OHLCV
                ohlcv_df = self.kis_etf_api.get_ohlcv(ticker, days=days)

                # Calculate indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self.db.insert_ohlcv_bulk(ticker, ohlcv_df, timeframe='D')

                updated_count += 1

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ [{ticker}] ETF OHLCV collection failed: {e}")

        logger.info(f"✅ [KR] {updated_count}/{len(tickers)} ETFs OHLCV collected")
        return updated_count

    # ========================================
    # PHASE 3: ENHANCED DATA (ETF-SPECIFIC)
    # ========================================

    def collect_etf_aum(self, tickers: Optional[List[str]] = None) -> int:
        """
        ETF AUM calculation (Phase 2 from ETF plan)

        Formula: AUM = listed_shares × current_price

        Returns:
            Number of ETFs updated
        """
        if tickers is None:
            tickers = self.db.get_etf_tickers(region='KR')

        logger.info(f"🔄 [KR] Calculating AUM for {len(tickers)} ETFs...")

        updated_count = 0
        for ticker in tickers:
            try:
                # Get listed shares
                listed_shares = self.db.get_etf_field(ticker, 'listed_shares')

                # Get current price
                price_data = self.kis_etf_api.get_current_price(ticker)
                current_price = int(price_data['stck_prpr'])

                # Calculate AUM
                aum = listed_shares * current_price

                # Update database
                self.db.update_etf_field(ticker, 'aum', aum)

                updated_count += 1

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ [{ticker}] AUM calculation failed: {e}")

        logger.info(f"✅ [KR] {updated_count}/{len(tickers)} ETFs AUM updated")
        return updated_count

    def collect_etf_tracking_error(self, tickers: Optional[List[str]] = None) -> int:
        """
        ETF tracking error calculation (Phase 3 from ETF plan)

        Data source: KIS ETF NAV comparison API

        Returns:
            Number of ETFs updated
        """
        if tickers is None:
            tickers = self.db.get_etf_tickers(region='KR')

        logger.info(f"🔄 [KR] Calculating tracking error for {len(tickers)} ETFs...")

        updated_count = 0
        for ticker in tickers:
            try:
                # Get NAV comparison trend
                nav_data = self.kis_etf_api.get_nav_comparison_trend(ticker)

                # Calculate tracking errors (20d, 60d, 120d, 250d)
                tracking_errors = self.etf_parser.calculate_tracking_error(nav_data)

                # Update database
                self.db.update_etf_tracking_errors(ticker, tracking_errors)

                updated_count += 1

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ [{ticker}] Tracking error calculation failed: {e}")

        logger.info(f"✅ [KR] {updated_count}/{len(tickers)} ETFs tracking error updated")
        return updated_count

    # ========================================
    # KOREA-SPECIFIC UTILITIES
    # ========================================

    def _detect_market_tier(self, stock_data: Dict) -> str:
        """
        Detect market tier (MAIN vs NXT vs KONEX)

        Uses KRX API market classification field
        """
        market_name = stock_data.get('market_classification', '')

        if 'NXT' in market_name:
            return 'NXT'
        elif 'KONEX' in market_name:
            return 'KONEX'
        else:
            return 'MAIN'

    def health_check(self) -> Dict:
        """
        Check API connectivity

        Returns:
            {'krx_api': True/False, 'kis_stock_api': True/False, ...}
        """
        return {
            'krx_api': self.krx_api.check_connection(),
            'kis_stock_api': self.kis_stock_api.check_connection(),
            'kis_etf_api': self.kis_etf_api.check_connection(),
            'pykrx_api': self.pykrx_api.check_connection(),
        }
```

### 3.3 scanner.py (Thin Wrapper)

```python
# modules/scanner.py

from typing import List, Dict, Optional
from market_adapters.kr_adapter import KoreaAdapter
# from market_adapters.us_adapter import USAdapter  # Phase 4
import logging

logger = logging.getLogger(__name__)

class UnifiedScanner:
    """
    Multi-region stock scanner (thin wrapper over market adapters)

    Delegates to regional adapters' scan_* methods

    Supported regions:
    - Korea (KOSPI, KOSDAQ, NXT) - Phase 1-3
    - US (NYSE, NASDAQ, AMEX) - Phase 4
    - China (SSE, SZSE) - Phase 5
    - Hong Kong (HKEX) - Phase 5
    - Japan (TSE) - Phase 6
    - Vietnam (HOSE, HNX) - Phase 6
    """

    def __init__(self, db_path: str = 'data/spock_local.db',
                 kis_config: Optional[Dict] = None):
        """
        Initialize unified scanner

        Args:
            db_path: SQLite database path
            kis_config: KIS API configuration (app_key, app_secret)
        """
        from modules.db_manager_sqlite import SQLiteDatabaseManager

        # Initialize database
        db = SQLiteDatabaseManager(db_path)

        # Initialize market adapters
        self.adapters = {
            'KR': KoreaAdapter(db, kis_config or {}),
            # 'US': USAdapter(db, {}),  # Phase 4
            # 'CN': ChinaAdapter(db, {}),  # Phase 5
        }

    def scan_region(self,
                   region: str,
                   asset_type: str = 'STOCK',
                   force_refresh: bool = False) -> List[Dict]:
        """
        Scan specific region

        Args:
            region: 'KR', 'US', 'CN', 'HK', 'JP', 'VN'
            asset_type: 'STOCK' or 'ETF'
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ticker dictionaries

        Example:
            scanner = UnifiedScanner(db_path, kis_config)

            # Scan Korea stocks
            kr_stocks = scanner.scan_region('KR', asset_type='STOCK')

            # Scan Korea ETFs
            kr_etfs = scanner.scan_region('KR', asset_type='ETF')

            # Scan US stocks (Phase 4)
            us_stocks = scanner.scan_region('US', asset_type='STOCK')
        """
        adapter = self.adapters.get(region)
        if not adapter:
            raise ValueError(f"Unsupported region: {region}")

        # Delegate to adapter's scan method
        if asset_type == 'STOCK':
            return adapter.scan_stocks(force_refresh=force_refresh)
        elif asset_type == 'ETF':
            return adapter.scan_etfs(force_refresh=force_refresh)
        else:
            raise ValueError(f"Unsupported asset_type: {asset_type}")

    def scan_all_regions(self,
                        asset_type: str = 'STOCK',
                        force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        Scan all supported regions

        Args:
            asset_type: 'STOCK' or 'ETF'
            force_refresh: Ignore cache

        Returns:
            {'KR': [...], 'US': [...], ...}
        """
        results = {}

        for region, adapter in self.adapters.items():
            try:
                if asset_type == 'STOCK':
                    tickers = adapter.scan_stocks(force_refresh=force_refresh)
                elif asset_type == 'ETF':
                    tickers = adapter.scan_etfs(force_refresh=force_refresh)
                else:
                    raise ValueError(f"Unsupported asset_type: {asset_type}")

                results[region] = tickers
                logger.info(f"✅ [{region}] {len(tickers)} {asset_type}s scanned")

            except Exception as e:
                logger.error(f"❌ [{region}] Scan failed: {e}")
                results[region] = []

        return results

    # ========================================
    # BACKWARD COMPATIBILITY
    # ========================================

    def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
        """
        Legacy method for backward compatibility

        Scans Korea stocks only (preserves existing behavior)

        Example:
            scanner = UnifiedScanner()
            tickers = scanner.scan_all_tickers()  # Same as before
        """
        return self.scan_region('KR', asset_type='STOCK', force_refresh=force_refresh)


# Alias for backward compatibility
StockScanner = UnifiedScanner
```

### 3.4 data_collector.py (Thin Wrapper)

```python
# modules/data_collector.py

from typing import List, Dict, Optional
from market_adapters.kr_adapter import KoreaAdapter
# from market_adapters.us_adapter import USAdapter  # Phase 4
import logging

logger = logging.getLogger(__name__)

class UnifiedDataCollector:
    """
    Multi-region OHLCV data collector (thin wrapper over market adapters)

    Delegates to regional adapters' collect_* methods
    """

    def __init__(self, db_path: str = 'data/spock_local.db',
                 kis_config: Dict = None):
        """
        Initialize unified data collector

        Args:
            db_path: SQLite database path
            kis_config: KIS API configuration (app_key, app_secret)
        """
        from modules.db_manager_sqlite import SQLiteDatabaseManager

        # Initialize database
        db = SQLiteDatabaseManager(db_path)

        # Initialize market adapters (same instances as scanner!)
        self.adapters = {
            'KR': KoreaAdapter(db, kis_config or {}),
            # 'US': USAdapter(db, {}),  # Phase 4
        }

    def collect_ohlcv(self,
                     region: str,
                     asset_type: str = 'STOCK',
                     tickers: Optional[List[str]] = None,
                     days: int = 250) -> int:
        """
        Collect OHLCV data for specific region

        Args:
            region: 'KR', 'US', 'CN', etc.
            asset_type: 'STOCK' or 'ETF'
            tickers: Specific tickers (None = all)
            days: Historical days to collect (default: 250 for MA200)

        Returns:
            Number of tickers successfully updated

        Example:
            collector = UnifiedDataCollector(db_path, kis_config)

            # Collect Korea stock OHLCV
            updated = collector.collect_ohlcv('KR', asset_type='STOCK', days=250)

            # Collect Korea ETF OHLCV
            updated = collector.collect_ohlcv('KR', asset_type='ETF', days=250)

            # Collect specific tickers
            updated = collector.collect_ohlcv('KR', tickers=['005930', '035720'])
        """
        adapter = self.adapters.get(region)
        if not adapter:
            raise ValueError(f"Unsupported region: {region}")

        # Delegate to adapter's collect method
        if asset_type == 'STOCK':
            return adapter.collect_stock_ohlcv(tickers=tickers, days=days)
        elif asset_type == 'ETF':
            return adapter.collect_etf_ohlcv(tickers=tickers, days=days)
        else:
            raise ValueError(f"Unsupported asset_type: {asset_type}")

    def collect_all_regions(self,
                           asset_type: str = 'STOCK',
                           days: int = 250) -> Dict[str, int]:
        """
        Collect OHLCV for all supported regions

        Args:
            asset_type: 'STOCK' or 'ETF'
            days: Historical days

        Returns:
            {'KR': 1500, 'US': 3000, ...} (updated counts)
        """
        results = {}

        for region, adapter in self.adapters.items():
            try:
                if asset_type == 'STOCK':
                    count = adapter.collect_stock_ohlcv(days=days)
                elif asset_type == 'ETF':
                    count = adapter.collect_etf_ohlcv(days=days)
                else:
                    raise ValueError(f"Unsupported asset_type: {asset_type}")

                results[region] = count
                logger.info(f"✅ [{region}] {count} {asset_type}s OHLCV collected")

            except Exception as e:
                logger.error(f"❌ [{region}] Collection failed: {e}")
                results[region] = 0

        return results

    # ========================================
    # ETF-SPECIFIC DATA COLLECTION
    # ========================================

    def collect_etf_enhanced_data(self,
                                  region: str,
                                  tickers: Optional[List[str]] = None) -> Dict:
        """
        Collect ETF enhanced data (AUM, tracking error, etc.)

        Args:
            region: 'KR', 'US', etc.
            tickers: Specific ETF tickers (None = all)

        Returns:
            {'aum': 1029, 'tracking_error': 1029, ...}
        """
        adapter = self.adapters.get(region)
        if not adapter:
            raise ValueError(f"Unsupported region: {region}")

        results = {}

        # Collect AUM
        try:
            if hasattr(adapter, 'collect_etf_aum'):
                results['aum'] = adapter.collect_etf_aum(tickers=tickers)
        except Exception as e:
            logger.error(f"❌ [{region}] AUM collection failed: {e}")
            results['aum'] = 0

        # Collect tracking error
        try:
            if hasattr(adapter, 'collect_etf_tracking_error'):
                results['tracking_error'] = adapter.collect_etf_tracking_error(tickers=tickers)
        except Exception as e:
            logger.error(f"❌ [{region}] Tracking error collection failed: {e}")
            results['tracking_error'] = 0

        return results

    # ========================================
    # BACKWARD COMPATIBILITY
    # ========================================

    def collect_all_korea(self, days: int = 250) -> Dict:
        """
        Legacy method for backward compatibility

        Collects all Korea data (stocks + ETFs)

        Example:
            collector = UnifiedDataCollector(db_path, kis_config)
            results = collector.collect_all_korea()
            # {'stocks': 1500, 'etfs': 1029}
        """
        results = {
            'stocks': self.collect_ohlcv('KR', asset_type='STOCK', days=days),
            'etfs': self.collect_ohlcv('KR', asset_type='ETF', days=days),
        }
        return results
```

---

## 4. 사용 예시

### 4.1 Full Workflow

```python
# ===== Phase 1: Ticker Discovery (Scanning) =====

from modules.scanner import UnifiedScanner

scanner = UnifiedScanner(
    db_path='data/spock_local.db',
    kis_config={
        'app_key': os.getenv('KIS_APP_KEY'),
        'app_secret': os.getenv('KIS_APP_SECRET'),
    }
)

# Scan Korea stocks
kr_stocks = scanner.scan_region('KR', asset_type='STOCK')
print(f"✅ {len(kr_stocks)} Korea stocks discovered")

# Scan Korea ETFs
kr_etfs = scanner.scan_region('KR', asset_type='ETF')
print(f"✅ {len(kr_etfs)} Korea ETFs discovered")

# ===== Phase 2: OHLCV Data Collection =====

from modules.data_collector import UnifiedDataCollector

collector = UnifiedDataCollector(
    db_path='data/spock_local.db',
    kis_config={
        'app_key': os.getenv('KIS_APP_KEY'),
        'app_secret': os.getenv('KIS_APP_SECRET'),
    }
)

# Collect OHLCV for stocks (250 days for MA200)
stock_count = collector.collect_ohlcv('KR', asset_type='STOCK', days=250)
print(f"✅ {stock_count} stocks OHLCV collected")

# Collect OHLCV for ETFs
etf_count = collector.collect_ohlcv('KR', asset_type='ETF', days=250)
print(f"✅ {etf_count} ETFs OHLCV collected")

# ===== Phase 3: ETF Enhanced Data =====

etf_enhanced = collector.collect_etf_enhanced_data('KR')
print(f"✅ AUM: {etf_enhanced['aum']} ETFs")
print(f"✅ Tracking Error: {etf_enhanced['tracking_error']} ETFs")
```

### 4.2 Direct Adapter Usage (Advanced)

```python
# Advanced: Use adapter directly for fine-grained control

from modules.market_adapters.kr_adapter import KoreaAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager('data/spock_local.db')
kr_adapter = KoreaAdapter(db, kis_config)

# Scan stocks
stocks = kr_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV for specific tickers
kr_adapter.collect_stock_ohlcv(tickers=['005930', '035720'], days=250)

# ETF-specific operations
kr_adapter.collect_etf_aum()
kr_adapter.collect_etf_tracking_error()

# Health check
health = kr_adapter.health_check()
print(health)  # {'krx_api': True, 'kis_stock_api': True, ...}
```

---

## 5. 마이그레이션 계획

### Phase 1: Base Adapter 구현 (1일)

**작업**:
- `base_adapter.py` 작성
- Abstract methods 정의
- Shared utilities 구현 (`_load_cache`, `_save_to_db`, `_calculate_indicators`)

**검증**:
- Abstract methods가 제대로 정의되었는지 확인
- Shared utilities 단위 테스트

### Phase 2: Korea Adapter 구현 (2일)

**작업**:
- `kr_adapter.py` 작성
- `scan_stocks()`, `scan_etfs()` 구현
- `collect_stock_ohlcv()`, `collect_etf_ohlcv()` 구현
- `collect_etf_aum()`, `collect_etf_tracking_error()` 구현

**검증**:
- 각 메서드 단위 테스트
- KRX API, KIS API mocking 테스트

### Phase 3: Thin Wrappers 구현 (1일)

**작업**:
- `scanner.py` 리팩토링 → `UnifiedScanner`
- `data_collector.py` 생성 → `UnifiedDataCollector`
- 역호환성 alias 추가 (`StockScanner = UnifiedScanner`)

**검증**:
- 기존 코드와의 호환성 테스트
- `scan_all_tickers()` 메서드 동작 확인

### Phase 4: 통합 테스트 (1일)

**작업**:
- End-to-end 워크플로우 테스트 (scan → collect → analyze)
- 성능 테스트 (caching, rate limiting)
- 에러 처리 테스트 (API failure, fallback)

**검증**:
- 모든 Phase가 정상 작동하는지 확인
- 데이터베이스에 올바른 데이터가 저장되는지 확인

**총 소요 시간**: 5일

---

## 6. 장점 요약

### ✅ Single Source of Truth
- 모든 Korea 로직이 `kr_adapter.py` 한 곳에 존재
- Bug fix 시 1개 파일만 수정

### ✅ Resource Sharing
- API clients, parsers, DB manager를 scan/collect 메서드가 공유
- 초기화 비용 절감, 메모리 효율

### ✅ Clear Separation
- **Adapter**: 실제 로직 (region-specific)
- **scanner.py**: API 편의 계층 (thin wrapper)
- **data_collector.py**: API 편의 계층 (thin wrapper)

### ✅ Module Count 50% 감소
- Separate: 1 base + 6 regions × 2 types = **13 modules**
- Unified: 1 base + 6 regions = **7 modules**

### ✅ Easier Testing
- kr_adapter 테스트 1번으로 scan + collect 모두 검증
- Mock API clients 한 번만 설정

### ✅ Scalability
- 새로운 국가 추가: 1개 adapter 파일만 생성
- US adapter 구현 시: `us_adapter.py` 1개만 추가

### ✅ Backward Compatibility
- `scanner.py`의 `scan_all_tickers()` 메서드 보존
- 기존 코드 변경 없이 작동

---

## 7. 참고 자료

### 관련 문서
- [REGION_BASED_ARCHITECTURE.md](REGION_BASED_ARCHITECTURE.md) - 초기 region-based 제안
- [SCANNER_ARCHITECTURE_ANALYSIS.md](SCANNER_ARCHITECTURE_ANALYSIS.md) - Scanner 문제점 분석
- [ETF_DATA_COLLECTION_DESIGN.md](ETF_DATA_COLLECTION_DESIGN.md) - ETF 수집 설계
- [NXT_SCHEMA_DESIGN.md](NXT_SCHEMA_DESIGN.md) - NXT 지원 스키마

### 코드 참조
- `modules/market_adapters/base_adapter.py` - Abstract base class
- `modules/market_adapters/kr_adapter.py` - Korea implementation
- `modules/scanner.py` - Thin wrapper
- `modules/data_collector.py` - Thin wrapper

---

**문서 작성**: Claude (SuperClaude Framework)
**작성일**: 2024-01-XX
**버전**: 2.0 (Unified Architecture)
