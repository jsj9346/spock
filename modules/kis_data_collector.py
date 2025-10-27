#!/usr/bin/env python3
"""
kis_data_collector.py - Phase 1 데이터 수집기 (KIS API 연동)

Purpose:
- Load Stage 0 results from filter_cache_stage0 (600 tickers)
- Fetch 250-day OHLCV data from KIS API (incremental updates)
- Calculate technical indicators (MA5/20/60/120/200, RSI, MACD, volume_ma20)
- Save to ohlcv_data table with upsert logic

KIS API Integration:
- OAuth 2.0 authentication (24-hour token validity)
- Rate limiting: 20 req/sec, 1,000 req/min
- Automatic retry with exponential backoff
- Gap detection for incremental updates

Author: Spock Trading System
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import json
import time
import requests
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any
import logging
import pytz
from dotenv import load_dotenv

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# KIS API Library (mojito recommended)
try:
    from mojito import KoreaInvestment
    HAS_MOJITO = True
except ImportError:
    HAS_MOJITO = False
    print("⚠️ mojito library not available, using custom KIS wrapper")

# pandas_ta for technical indicators
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    print("⚠️ pandas_ta not available, using basic indicators")

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KISDataCollector:
    """
    KIS API OHLCV Data Collector with Multi-Stage Filtering

    Features (Phase 2 - Task 2.1):
    1. Stage 0 filter integration (market cap, trading value)
    2. Stage 1 filter integration (technical pre-screen)
    3. Multi-market support (KR, US, HK, CN, JP, VN)
    4. Batch collection with filtering statistics
    """

    def __init__(self, db_path: str = 'data/spock_local.db', region: str = 'KR'):
        """
        Initialize KIS Data Collector

        Args:
            db_path: Path to SQLite database
            region: Market region ('KR', 'US', 'HK', 'CN', 'JP', 'VN')
        """
        self.db_path = db_path
        self.region = region
        self.kst = pytz.timezone('Asia/Seoul')

        # Initialize filter managers (Phase 2 integration)
        try:
            from modules.exchange_rate_manager import ExchangeRateManager
            from modules.market_filter_manager import MarketFilterManager

            self.exchange_rate_manager = ExchangeRateManager(db_manager=None)  # Standalone mode
            self.filter_manager = MarketFilterManager(
                config_dir='config/market_filters',
                exchange_rate_manager=self.exchange_rate_manager
            )

            # Get market config
            self.market_config = self.filter_manager.get_config(region)
            if not self.market_config:
                logger.warning(f"⚠️ No market config found for region: {region}, filtering disabled")
                self.filtering_enabled = False
            else:
                logger.info(f"✅ Market filter config loaded for {region} (currency: {self.market_config.currency})")
                self.filtering_enabled = True

        except Exception as e:
            logger.warning(f"⚠️ Filter managers initialization failed: {e}, filtering disabled")
            self.exchange_rate_manager = None
            self.filter_manager = None
            self.market_config = None
            self.filtering_enabled = False

        # Phase 6: Initialize BlacklistManager
        try:
            from modules.blacklist_manager import BlacklistManager
            from modules.db_manager_sqlite import SQLiteDatabaseManager

            db_manager = SQLiteDatabaseManager(db_path=db_path)
            self.blacklist_manager = BlacklistManager(db_manager=db_manager)
            logger.info("✅ BlacklistManager initialized for Data Collector")

        except Exception as e:
            logger.warning(f"⚠️ BlacklistManager initialization failed: {e}, blacklist filtering disabled")
            self.blacklist_manager = None

        # KIS API Authentication
        self.kis_app_key = os.getenv('KIS_APP_KEY')
        self.kis_app_secret = os.getenv('KIS_APP_SECRET')
        self.kis_account_number = os.getenv('KIS_ACCOUNT_NUMBER', 'mock')  # Not needed for data collection

        if not self.kis_app_key or not self.kis_app_secret:
            logger.warning("⚠️ KIS_APP_KEY and KIS_APP_SECRET not set - using mock mode")
            self.mock_mode = True
        else:
            self.mock_mode = False

        # Initialize KIS API client
        if not self.mock_mode:
            if HAS_MOJITO:
                try:
                    self.kis = KoreaInvestment(
                        api_key=self.kis_app_key,
                        api_secret=self.kis_app_secret,
                        acc_no=self.kis_account_number
                    )
                    logger.info("✅ Using mojito library for KIS API")
                except Exception as e:
                    logger.warning(f"⚠️ mojito initialization failed: {e}")
                    self.kis = None
                    self.mock_mode = True
            else:
                self.kis = None
                logger.info("📦 Using custom KIS API wrapper")
        else:
            self.kis = None

        # Token management (for custom implementation)
        self.access_token = None
        self.token_expiry = None
        self.token_cache_file = 'data/.kis_token_cache.json'

        if not self.mock_mode and not HAS_MOJITO:
            try:
                # Try to load cached token first (KIS API: 1분당 1회 제한)
                if self._load_cached_token():
                    logger.info("✅ Using cached KIS API token")
                else:
                    self._refresh_access_token()
            except Exception as e:
                logger.warning(f"⚠️ Token refresh failed: {e}. Falling back to mock mode.")
                self.mock_mode = True

        # Database initialization
        self.init_database()

        mode_str = "MOCK MODE" if self.mock_mode else "LIVE MODE"
        logger.info(f"✅ KISDataCollector initialized (region={region}, {mode_str}, KST timezone)")

    def _load_cached_token(self) -> bool:
        """
        Load cached KIS API token from file

        Returns:
            True if valid cached token loaded, False otherwise
        """
        try:
            import json

            if not os.path.exists(self.token_cache_file):
                return False

            with open(self.token_cache_file, 'r') as f:
                cache_data = json.load(f)

            # Validate cache structure
            if 'access_token' not in cache_data or 'expiry' not in cache_data:
                return False

            # Check expiry (with 1-hour buffer)
            expiry = datetime.fromisoformat(cache_data['expiry'])
            if datetime.now() >= expiry - timedelta(hours=1):
                logger.debug("⏰ Cached token expired or expiring soon")
                return False

            # Load cached token
            self.access_token = cache_data['access_token']
            self.token_expiry = expiry

            logger.debug(f"✅ Cached token loaded (expires: {expiry})")
            return True

        except Exception as e:
            logger.debug(f"⚠️ Failed to load cached token: {e}")
            return False

    def _save_token_cache(self):
        """Save current token to cache file"""
        try:
            import json

            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.token_cache_file), exist_ok=True)

            cache_data = {
                'access_token': self.access_token,
                'expiry': self.token_expiry.isoformat()
            }

            with open(self.token_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"💾 Token cached to {self.token_cache_file}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to save token cache: {e}")

    def _refresh_access_token(self):
        """Refresh KIS API OAuth 2.0 access token (24-hour validity, 1분당 1회 제한)"""
        try:
            if HAS_MOJITO:
                # mojito handles token refresh automatically
                logger.debug("✅ Using mojito library (automatic token management)")
                return

            # Custom token refresh for requests-based implementation
            url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
            headers = {"content-type": "application/json"}
            body = {
                "grant_type": "client_credentials",
                "appkey": self.kis_app_key,
                "appsecret": self.kis_app_secret
            }

            response = requests.post(url, headers=headers, json=body, timeout=10)

            # Check response status
            if response.status_code != 200:
                logger.error(f"❌ Token request failed: HTTP {response.status_code}, {response.text}")
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            token_data = response.json()

            # Validate token response
            if 'access_token' not in token_data:
                logger.error(f"❌ Invalid token response: {token_data}")
                raise Exception(f"Invalid token response: missing access_token")

            self.access_token = token_data['access_token']
            self.token_expiry = datetime.now() + timedelta(hours=24)

            logger.info(f"✅ KIS API access token refreshed (expires: {token_data.get('access_token_token_expired', 'N/A')})")

            # Save token to cache (KIS API: 1분당 1회 제한 대응)
            self._save_token_cache()

        except Exception as e:
            logger.error(f"❌ Token refresh failed: {e}")
            # Re-raise to be caught by __init__ for mock mode fallback
            raise

    def init_database(self):
        """Initialize ohlcv_data table with stock market schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # ohlcv_data table with volume_ma20 (Phase 3 optimization)
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume BIGINT NOT NULL,

                -- Moving Averages
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                ma120 REAL,
                ma200 REAL,

                -- Momentum Indicators
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,

                -- Volume Analysis
                volume_ma20 BIGINT,
                volume_ratio REAL,

                -- Volatility
                atr REAL,
                bb_upper REAL,
                bb_middle REAL,
                bb_lower REAL,

                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY (ticker, region, timeframe, date)
            );
            """

            cursor.execute(create_table_sql)

            # Add missing columns if table exists (ALTER TABLE for backward compatibility)
            missing_columns = [
                ('region', 'TEXT'),  # Multi-market support (KR, US, HK, CN, JP)
                ('volume_ma20', 'BIGINT'),
                ('volume_ratio', 'REAL'),
                ('atr', 'REAL'),
                ('bb_upper', 'REAL'),
                ('bb_middle', 'REAL'),
                ('bb_lower', 'REAL')
            ]

            for column_name, column_type in missing_columns:
                try:
                    cursor.execute(f"ALTER TABLE ohlcv_data ADD COLUMN {column_name} {column_type};")
                    logger.info(f"✅ Added {column_name} column to ohlcv_data")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug(f"📋 {column_name} column already exists")
                    else:
                        logger.warning(f"⚠️ Failed to add {column_name} column: {e}")

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_region ON ohlcv_data(ticker, region);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv_data(date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv_data(timeframe);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date ON ohlcv_data(ticker, date);")

            # Create unique index for UPSERT operations
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ohlcv_unique ON ohlcv_data(ticker, timeframe, date);")
                logger.debug("✅ Created unique index for UPSERT operations")
            except sqlite3.OperationalError as e:
                logger.debug(f"ℹ️ Unique index may already exist: {e}")

            conn.commit()
            conn.close()

            logger.info("✅ Database initialized (ohlcv_data table ready)")

        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise

    def safe_get_ohlcv(self, ticker: str, count: int = 250, timeframe: str = 'D', max_retries: int = 5) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from KIS API with error handling and retry logic

        Args:
            ticker: 6-digit stock code (e.g., '005930' for Samsung)
            count: Number of days to fetch (default: 250)
            timeframe: 'D' (daily), 'W' (weekly), 'M' (monthly)
            max_retries: Maximum retry attempts (default: 5)

        Returns:
            DataFrame with columns: open, high, low, close, volume, index=date
        """
        # Mock mode for development
        if self.mock_mode:
            return self._get_mock_ohlcv(ticker, count)

        # Retry loop with exponential backoff
        for attempt in range(1, max_retries + 1):
            try:
                # Check token expiry (refresh if <1 hour remaining)
                if not HAS_MOJITO and self.token_expiry:
                    if (self.token_expiry - datetime.now()).total_seconds() < 3600:
                        self._refresh_access_token()

                # KIS API call (mojito library)
                if HAS_MOJITO and self.kis:
                    df = self.kis.get_ohlcv(
                        ticker=ticker,
                        timeframe=timeframe,
                        adj_price=True,  # Adjusted for splits/dividends
                        count=count
                    )
                else:
                    # Custom KIS API implementation
                    df = self._custom_kis_get_ohlcv(ticker, timeframe, count)

                if df is None or df.empty:
                    if attempt < max_retries:
                        wait_time = min(2 ** (attempt - 1), 8)  # Exponential backoff (max 8s)
                        logger.debug(f"⚠️ {ticker} No data (attempt {attempt}/{max_retries}), retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"⚠️ {ticker} No data returned from KIS API (all {max_retries} attempts failed)")
                        return None

                # Data quality validation
                if len(df) < count * 0.7:  # At least 70% of requested data
                    logger.warning(f"⚠️ {ticker} Insufficient data: {len(df)}/{count}")

                logger.debug(f"✅ {ticker} KIS API success: {len(df)} rows (attempt {attempt})")
                return df

            except Exception as e:
                if attempt < max_retries:
                    wait_time = min(2 ** (attempt - 1), 8)  # Exponential backoff (max 8s)
                    logger.warning(f"⚠️ {ticker} KIS API error (attempt {attempt}/{max_retries}): {e}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ {ticker} KIS API call failed after {max_retries} attempts: {e}")
                    return None

        return None

    def _custom_kis_get_ohlcv(self, ticker: str, timeframe: str, count: int) -> Optional[pd.DataFrame]:
        """
        Custom KIS API implementation with pagination support (fallback if mojito not available)

        Overcomes KIS API 100-row limit by:
        1. Splitting requests into 150 calendar day chunks (~100 trading days)
        2. Making multiple API calls with backward time traversal
        3. Combining and deduplicating results

        KIS API Documentation:
        - Endpoint: /uapi/domestic-stock/v1/quotations/inquire-daily-price
        - Headers: authorization (Bearer token), appkey, appsecret, tr_id
        - Parameters: FID_COND_MRKT_DIV_CODE, FID_INPUT_ISCD, FID_PERIOD_DIV_CODE, FID_ORG_ADJ_PRC
        - Limitation: Maximum 100 rows per request
        """
        try:
            if not self.access_token:
                raise ValueError("Access token not available")

            url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-daily-price"

            # Pagination setup
            from datetime import datetime, timedelta
            import time

            chunk_calendar_days = 150  # ~100 trading days per chunk
            all_data = []
            current_end_date = datetime.now()
            target_start_date = current_end_date - timedelta(days=int(count * 1.5))

            logger.debug(f"📊 {ticker} Pagination: target {count} days, date range {target_start_date.strftime('%Y-%m-%d')} → {current_end_date.strftime('%Y-%m-%d')}")

            # Pagination loop - backward time traversal
            chunk_num = 0
            while current_end_date > target_start_date:
                chunk_num += 1

                # Rate limiting (20 req/sec = 50ms interval)
                time.sleep(0.05)

                # Calculate chunk range
                chunk_start_date = current_end_date - timedelta(days=chunk_calendar_days)
                if chunk_start_date < target_start_date:
                    chunk_start_date = target_start_date

                headers = {
                    "content-type": "application/json; charset=utf-8",
                    "authorization": f"Bearer {self.access_token}",
                    "appkey": self.kis_app_key,
                    "appsecret": self.kis_app_secret,
                    "tr_id": "FHKST03010100",  # 국내주식 기간별 시세 조회
                    "custtype": "P"  # 개인
                }

                params = {
                    "fid_cond_mrkt_div_code": "J",  # J: 주식
                    "fid_input_iscd": ticker,
                    "fid_input_date_1": chunk_start_date.strftime("%Y%m%d"),
                    "fid_input_date_2": current_end_date.strftime("%Y%m%d"),
                    "fid_period_div_code": "D" if timeframe == 'D' else "W" if timeframe == 'W' else "M",
                    "fid_org_adj_prc": "0"  # 0: 수정주가
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)
                logger.debug(f"📡 {ticker} Chunk {chunk_num}: HTTP {response.status_code}, {chunk_start_date.strftime('%Y%m%d')} → {current_end_date.strftime('%Y%m%d')}")
                response.raise_for_status()

                data = response.json()

                # Enhanced error handling
                rt_cd = data.get('rt_cd', '')

                if rt_cd == '' or rt_cd is None:
                    logger.warning(f"⚠️ {ticker} Chunk {chunk_num}: Empty rt_cd (상장폐지/거래정지 가능성)")
                    break

                if rt_cd != '0':
                    error_msg = data.get('msg1', '') or data.get('msg', '') or f'KIS API error (rt_cd={rt_cd})'
                    logger.error(f"❌ {ticker} Chunk {chunk_num}: {error_msg}")
                    break

                # Parse chunk data
                output2 = data.get('output2', [])

                if not output2:
                    logger.debug(f"📊 {ticker} Chunk {chunk_num}: No data (reached end)")
                    break

                # Collect chunk records
                for item in output2:
                    all_data.append({
                        'date': pd.to_datetime(item['stck_bsop_date']),
                        'open': float(item['stck_oprc']),
                        'high': float(item['stck_hgpr']),
                        'low': float(item['stck_lwpr']),
                        'close': float(item['stck_clpr']),
                        'volume': int(item['acml_vol'])
                    })

                logger.debug(f"📊 {ticker} Chunk {chunk_num}: Collected {len(output2)} rows")

                # Move to next chunk (backward)
                current_end_date = chunk_start_date - timedelta(days=1)

            # Combine all chunks
            if not all_data:
                logger.warning(f"⚠️ {ticker} No data collected from pagination")
                return None

            df = pd.DataFrame(all_data)

            # Remove duplicates (keep first occurrence)
            df = df.drop_duplicates(subset=['date'], keep='first')

            # Sort by date
            df = df.sort_values('date').reset_index(drop=True)
            df.set_index('date', inplace=True)

            # Trim to requested count (take most recent N days)
            if len(df) > count:
                df = df.tail(count)

            logger.info(f"✅ {ticker} Pagination complete: {len(df)} rows from {chunk_num} chunks ({len(all_data)} total collected)")
            return df

        except Exception as e:
            logger.error(f"❌ {ticker} Custom KIS API call failed: {e}")
            return None

    def _get_mock_ohlcv(self, ticker: str, count: int) -> Optional[pd.DataFrame]:
        """
        Generate mock OHLCV data for development/testing

        Args:
            ticker: Stock code
            count: Number of days

        Returns:
            Mock DataFrame with realistic-looking OHLCV data
        """
        try:
            # Generate dates (excluding weekends)
            end_date = datetime.now()
            dates = pd.bdate_range(end=end_date, periods=count, freq='B')

            # Generate realistic-looking price data
            base_price = 50000  # Starting price
            volatility = 0.02   # 2% daily volatility

            prices = [base_price]
            for _ in range(count - 1):
                change = prices[-1] * volatility * (2 * np.random.random() - 1)
                new_price = prices[-1] + change
                prices.append(max(new_price, base_price * 0.5))  # Prevent negative prices

            df = pd.DataFrame({
                'open': prices,
                'high': [p * (1 + abs(np.random.random() * 0.01)) for p in prices],
                'low': [p * (1 - abs(np.random.random() * 0.01)) for p in prices],
                'close': [p * (1 + (np.random.random() * 0.02 - 0.01)) for p in prices],
                'volume': [int(np.random.randint(1000000, 10000000)) for _ in prices]
            }, index=dates)

            logger.debug(f"✅ {ticker} Mock data generated: {len(df)} rows")
            return df

        except Exception as e:
            logger.error(f"❌ {ticker} Mock data generation failed: {e}")
            return None

    def analyze_data_gap(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze data gap for incremental update strategy

        Returns:
            {
                'strategy': 'skip' | 'yesterday_update' | 'incremental' | 'full_collection',
                'gap_days': int,
                'reason': str
            }
        """
        try:
            from modules.stock_utils import check_market_hours

            # Get market status
            market_status = check_market_hours()
            current_date_kst = market_status['market_date']

            # Query latest data from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT MAX(date) as latest_date
                FROM ohlcv_data
                WHERE ticker = ? AND region = ? AND timeframe = 'D'
            """, (ticker, self.region))

            result = cursor.fetchone()
            conn.close()

            if not result or not result[0]:
                return {
                    'strategy': 'full_collection',
                    'gap_days': 250,
                    'reason': 'No existing data'
                }

            latest_date = datetime.strptime(result[0], '%Y-%m-%d').date()
            gap_days = (current_date_kst - latest_date).days

            # Stock market consideration: only trading days count
            if market_status['status'] == 'market_closed':
                # Weekend or holiday - use previous business day
                effective_gap = gap_days
            elif market_status['status'] in ['pre_market', 'market_open']:
                # During trading session - today's data not yet final
                effective_gap = gap_days - 1
            else:
                # After-hours - today's data should be available
                effective_gap = gap_days

            logger.debug(f"   • {ticker} Latest data: {latest_date}, Gap: {gap_days} days, Effective: {effective_gap} days")

            if effective_gap <= 0:
                return {
                    'strategy': 'skip',
                    'gap_days': gap_days,
                    'reason': 'Data is up to date'
                }
            elif effective_gap == 1:
                return {
                    'strategy': 'yesterday_update',
                    'gap_days': gap_days,
                    'reason': 'Yesterday data needs update'
                }
            else:
                return {
                    'strategy': 'incremental',
                    'gap_days': gap_days,
                    'reason': f'{effective_gap} days gap detected'
                }

        except Exception as e:
            logger.error(f"❌ {ticker} Gap analysis failed: {e}")
            return {
                'strategy': 'incremental',
                'gap_days': 1,
                'reason': f'Analysis failed: {e}'
            }

    def calculate_technical_indicators(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Calculate technical indicators for OHLCV data

        Indicators:
        - MA5, MA20, MA60, MA120, MA200
        - RSI-14
        - MACD (12, 26, 9)
        - volume_ma20 (Phase 3 optimization)
        - Bollinger Bands (20, 2)
        - ATR (14)
        """
        try:
            df_with_indicators = df.copy()

            # Moving Averages
            df_with_indicators['ma5'] = df['close'].rolling(window=5, min_periods=5).mean()
            df_with_indicators['ma20'] = df['close'].rolling(window=20, min_periods=20).mean()
            df_with_indicators['ma60'] = df['close'].rolling(window=60, min_periods=60).mean()
            df_with_indicators['ma120'] = df['close'].rolling(window=120, min_periods=120).mean()
            df_with_indicators['ma200'] = df['close'].rolling(window=200, min_periods=200).mean()

            # Volume MA20 (Phase 3 optimization - 22% performance gain)
            df_with_indicators['volume_ma20'] = df['volume'].rolling(window=20, min_periods=20).mean()

            # RSI-14
            if HAS_PANDAS_TA:
                df_with_indicators['rsi_14'] = ta.rsi(df['close'], length=14)
            else:
                # Manual RSI calculation
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df_with_indicators['rsi_14'] = 100 - (100 / (1 + rs))

            # MACD (12, 26, 9)
            if HAS_PANDAS_TA:
                macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
                df_with_indicators['macd'] = macd_result['MACD_12_26_9']
                df_with_indicators['macd_signal'] = macd_result['MACDs_12_26_9']
                df_with_indicators['macd_hist'] = macd_result['MACDh_12_26_9']
            else:
                # Manual MACD calculation
                ema12 = df['close'].ewm(span=12, adjust=False).mean()
                ema26 = df['close'].ewm(span=26, adjust=False).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9, adjust=False).mean()
                df_with_indicators['macd'] = macd
                df_with_indicators['macd_signal'] = signal
                df_with_indicators['macd_hist'] = macd - signal

            # Volume Ratio (current volume / 20-day average)
            df_with_indicators['volume_ratio'] = (
                df['volume'] / df_with_indicators['volume_ma20']
            ).fillna(1.0)

            # Bollinger Bands (20, 2)
            if HAS_PANDAS_TA:
                bb = ta.bbands(df['close'], length=20, std=2)
                # Handle different pandas_ta versions with flexible column names
                bb_cols = list(bb.columns)
                bb_upper_col = [c for c in bb_cols if c.startswith('BBU')][0]
                bb_middle_col = [c for c in bb_cols if c.startswith('BBM')][0]
                bb_lower_col = [c for c in bb_cols if c.startswith('BBL')][0]
                df_with_indicators['bb_upper'] = bb[bb_upper_col]
                df_with_indicators['bb_middle'] = bb[bb_middle_col]
                df_with_indicators['bb_lower'] = bb[bb_lower_col]
            else:
                # Manual Bollinger Bands calculation
                bb_middle = df['close'].rolling(window=20).mean()
                bb_std = df['close'].rolling(window=20).std()
                df_with_indicators['bb_upper'] = bb_middle + (bb_std * 2)
                df_with_indicators['bb_middle'] = bb_middle
                df_with_indicators['bb_lower'] = bb_middle - (bb_std * 2)

            # ATR (14)
            if HAS_PANDAS_TA:
                df_with_indicators['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            else:
                # Manual ATR calculation
                high_low = df['high'] - df['low']
                high_close = abs(df['high'] - df['close'].shift())
                low_close = abs(df['low'] - df['close'].shift())
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                df_with_indicators['atr'] = tr.rolling(window=14).mean()

            logger.debug(f"✅ {ticker} Technical indicators calculated")
            return df_with_indicators

        except Exception as e:
            logger.error(f"❌ {ticker} Indicator calculation failed: {e}")
            return df

    def save_to_db(self, ticker: str, df: pd.DataFrame, timeframe: str = 'D'):
        """
        Save OHLCV data to database with UPSERT logic

        Args:
            ticker: Stock code
            df: DataFrame with OHLCV and indicators
            timeframe: 'D', 'W', 'M'
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Prepare data for insertion
            records = []
            for date_idx, row in df.iterrows():
                record = (
                    ticker,
                    self.region,
                    timeframe,
                    date_idx.strftime('%Y-%m-%d'),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    float(row.get('ma5')) if pd.notna(row.get('ma5')) else None,
                    float(row.get('ma20')) if pd.notna(row.get('ma20')) else None,
                    float(row.get('ma60')) if pd.notna(row.get('ma60')) else None,
                    float(row.get('ma120')) if pd.notna(row.get('ma120')) else None,
                    float(row.get('ma200')) if pd.notna(row.get('ma200')) else None,
                    float(row.get('rsi_14')) if pd.notna(row.get('rsi_14')) else None,
                    float(row.get('macd')) if pd.notna(row.get('macd')) else None,
                    float(row.get('macd_signal')) if pd.notna(row.get('macd_signal')) else None,
                    float(row.get('macd_hist')) if pd.notna(row.get('macd_hist')) else None,
                    int(row.get('volume_ma20')) if pd.notna(row.get('volume_ma20')) else None,
                    float(row.get('volume_ratio')) if pd.notna(row.get('volume_ratio')) else None,
                    float(row.get('atr')) if pd.notna(row.get('atr')) else None,
                    float(row.get('bb_upper')) if pd.notna(row.get('bb_upper')) else None,
                    float(row.get('bb_middle')) if pd.notna(row.get('bb_middle')) else None,
                    float(row.get('bb_lower')) if pd.notna(row.get('bb_lower')) else None,
                )
                records.append(record)

            # UPSERT with SQLite ON CONFLICT
            # Note: Existing table uses 'id' as PRIMARY KEY, so we use ticker+timeframe+date for conflict
            upsert_sql = """
            INSERT INTO ohlcv_data (
                ticker, region, timeframe, date,
                open, high, low, close, volume,
                ma5, ma20, ma60, ma120, ma200,
                rsi_14, macd, macd_signal, macd_hist,
                volume_ma20, volume_ratio, atr,
                bb_upper, bb_middle, bb_lower,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker, timeframe, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                ma5=excluded.ma5,
                ma20=excluded.ma20,
                ma60=excluded.ma60,
                ma120=excluded.ma120,
                ma200=excluded.ma200,
                rsi_14=excluded.rsi_14,
                macd=excluded.macd,
                macd_signal=excluded.macd_signal,
                macd_hist=excluded.macd_hist,
                volume_ma20=excluded.volume_ma20,
                volume_ratio=excluded.volume_ratio,
                atr=excluded.atr,
                bb_upper=excluded.bb_upper,
                bb_middle=excluded.bb_middle,
                bb_lower=excluded.bb_lower
            """

            cursor.executemany(upsert_sql, records)
            conn.commit()
            conn.close()

            logger.info(f"✅ {ticker} Saved {len(records)} rows to database")

        except Exception as e:
            logger.error(f"❌ {ticker} Database save failed: {e}")
            raise

    def collect_data(self, tickers: Optional[List[str]] = None, force_full: bool = False):
        """
        Main data collection orchestrator

        Args:
            tickers: List of tickers to collect (None = load from Stage 0 cache)
            force_full: Force full collection (ignore gap analysis)
        """
        try:
            # Load tickers from Stage 0 cache if not provided
            if tickers is None:
                tickers = self._load_stage0_tickers()

            if not tickers:
                logger.warning("⚠️ No tickers to collect")
                return

            logger.info(f"🚀 Starting data collection: {len(tickers)} tickers")

            stats = {
                'total': len(tickers),
                'success': 0,
                'skipped': 0,
                'failed': 0,
                'start_time': datetime.now(),
                'consecutive_failures': 0,
                'mock_mode_activated': False
            }

            for idx, ticker in enumerate(tickers, 1):
                try:
                    # Circuit Breaker: Check if we should switch to mock mode
                    if not stats['mock_mode_activated'] and idx >= 10:
                        failure_rate = stats['failed'] / idx
                        if failure_rate >= 0.9:  # 90%+ failure rate
                            logger.warning(f"⚠️ High failure rate detected ({failure_rate:.1%}) - switching to MOCK MODE")
                            logger.warning(f"   KIS API calls failing for all tickers. Using mock data generation.")
                            stats['mock_mode_activated'] = True
                            self.mock_mode = True

                    # Gap analysis
                    if not force_full and not stats['mock_mode_activated']:
                        gap_info = self.analyze_data_gap(ticker)

                        if gap_info['strategy'] == 'skip':
                            logger.debug(f"⏭️ [{idx}/{len(tickers)}] {ticker} Skipped (up to date)")
                            stats['skipped'] += 1
                            stats['consecutive_failures'] = 0  # Reset on skip
                            continue

                        count = min(gap_info['gap_days'] + 50, 250)  # +50 buffer for indicators
                    else:
                        count = 250

                    # Fetch OHLCV data from KIS API or mock
                    df = self.safe_get_ohlcv(ticker, count=count, timeframe='D')

                    if df is None or df.empty:
                        logger.warning(f"❌ [{idx}/{len(tickers)}] {ticker} No data")
                        stats['failed'] += 1
                        stats['consecutive_failures'] += 1

                        # Circuit Breaker: Abort after 50 consecutive failures
                        if stats['consecutive_failures'] >= 50:
                            logger.error(f"🚨 CIRCUIT BREAKER: 50 consecutive failures detected!")
                            logger.error(f"   Aborting data collection. Processed {idx}/{len(tickers)} tickers.")
                            logger.error(f"   Success: {stats['success']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}")
                            break
                        continue

                    # Calculate technical indicators
                    df = self.calculate_technical_indicators(df, ticker)

                    # Save to database
                    self.save_to_db(ticker, df, timeframe='D')

                    logger.info(f"✅ [{idx}/{len(tickers)}] {ticker} Success ({len(df)} rows)")
                    stats['success'] += 1
                    stats['consecutive_failures'] = 0  # Reset on success

                    # KIS API rate limiting (20 req/sec max) - skip if in mock mode
                    if not stats['mock_mode_activated']:
                        time.sleep(0.05)  # 50ms between requests = 20 req/sec

                except Exception as e:
                    logger.error(f"❌ [{idx}/{len(tickers)}] {ticker} Failed: {e}")
                    stats['failed'] += 1
                    continue

            # Final statistics
            elapsed_time = (datetime.now() - stats['start_time']).total_seconds()
            mock_indicator = " (MOCK MODE)" if stats['mock_mode_activated'] else ""
            logger.info(f"📊 Collection complete{mock_indicator}: {stats['success']}/{stats['total']} success, "
                       f"{stats['skipped']} skipped, {stats['failed']} failed ({elapsed_time:.1f}s)")

        except Exception as e:
            logger.error(f"❌ Data collection failed: {e}")
            raise

    def collect_with_filtering(
        self,
        tickers: Optional[List[str]] = None,
        days: int = 250,
        apply_stage0: bool = True,
        apply_stage1: bool = False
    ) -> Dict[str, Any]:
        """
        Data collection with multi-stage filtering (Phase 2 - Task 2.1)

        Args:
            tickers: List of tickers to process (None = load from database)
            days: Number of days to collect (default: 250)
            apply_stage0: Apply Stage 0 filter (market cap, trading value)
            apply_stage1: Apply Stage 1 filter (technical pre-screen)

        Returns:
            Statistics dictionary with filtering results
        """
        try:
            logger.info(f"🚀 Starting OHLCV collection with filtering (region={self.region})")
            logger.info(f"   • Stage 0 filter: {'✅ Enabled' if apply_stage0 else '❌ Disabled'}")
            logger.info(f"   • Stage 1 filter: {'✅ Enabled' if apply_stage1 else '❌ Disabled'}")

            stats = {
                'start_time': datetime.now(),
                'input_count': 0,
                'stage0_passed': 0,
                'stage0_failed': 0,
                'ohlcv_collected': 0,
                'ohlcv_failed': 0,
                'stage1_passed': 0,
                'stage1_failed': 0,
                'filtering_enabled': self.filtering_enabled
            }

            # Step 1: Load ticker list (from Stage 0 cache or provided list)
            if tickers is None:
                tickers = self._load_stage0_tickers()

            if not tickers:
                logger.warning("⚠️ No tickers to process")
                return stats

            stats['input_count'] = len(tickers)
            logger.info(f"📊 Input: {stats['input_count']} tickers")

            # Step 2: Apply Blacklist Filter (Phase 6 - BEFORE API calls)
            if self.blacklist_manager:
                blacklist_filtered = self.blacklist_manager.filter_blacklisted_tickers(tickers, self.region)
                blacklist_rejected = len(tickers) - len(blacklist_filtered)

                if blacklist_rejected > 0:
                    logger.info(f"🚫 Blacklist filter: Removed {blacklist_rejected} blacklisted tickers")
                    logger.debug(f"   Blacklisted: {set(tickers) - set(blacklist_filtered)}")

                tickers = blacklist_filtered

                stats['blacklist_passed'] = len(tickers)
                stats['blacklist_rejected'] = blacklist_rejected
            else:
                stats['blacklist_passed'] = len(tickers)
                stats['blacklist_rejected'] = 0
                logger.debug("⏭️ Blacklist filter skipped (BlacklistManager not available)")

            if not tickers:
                logger.warning("⚠️ No tickers passed blacklist filter")
                return stats

            # Step 3: Apply Stage 0 filter (market cap, trading value)
            if apply_stage0 and self.filtering_enabled:
                filtered_tickers = self._run_stage0_filter(tickers)
                stats['stage0_passed'] = len(filtered_tickers)
                stats['stage0_failed'] = len(tickers) - len(filtered_tickers)

                logger.info(f"✅ Stage 0 complete: {stats['stage0_passed']}/{len(tickers)} passed "
                           f"({stats['stage0_passed']/len(tickers)*100:.1f}%)")

                tickers = filtered_tickers
            else:
                # No Stage 0 filtering
                stats['stage0_passed'] = len(tickers)
                logger.info(f"⏭️ Stage 0 skipped (filtering disabled)")

            if not tickers:
                logger.warning("⚠️ No tickers passed Stage 0 filter")
                return stats

            # Step 3: Collect OHLCV data for filtered tickers
            logger.info(f"🔄 Collecting OHLCV data for {len(tickers)} tickers...")

            for idx, ticker in enumerate(tickers, 1):
                try:
                    # Fetch OHLCV data
                    df = self.safe_get_ohlcv(ticker, count=days, timeframe='D')

                    if df is None or df.empty:
                        logger.warning(f"❌ [{idx}/{len(tickers)}] {ticker} No OHLCV data")
                        stats['ohlcv_failed'] += 1
                        continue

                    # Calculate technical indicators
                    df = self.calculate_technical_indicators(df, ticker)

                    # Save to database
                    self.save_to_db(ticker, df, timeframe='D')

                    stats['ohlcv_collected'] += 1
                    logger.info(f"✅ [{idx}/{len(tickers)}] {ticker} OHLCV collected ({len(df)} rows)")

                    # Rate limiting (20 req/sec)
                    if not self.mock_mode:
                        time.sleep(0.05)  # 50ms between requests

                except Exception as e:
                    logger.error(f"❌ [{idx}/{len(tickers)}] {ticker} Failed: {e}")
                    stats['ohlcv_failed'] += 1
                    continue

            logger.info(f"✅ OHLCV collection complete: {stats['ohlcv_collected']}/{len(tickers)} success "
                       f"({stats['ohlcv_collected']/len(tickers)*100:.1f}%)")

            # Step 4: Apply Stage 1 filter (technical pre-screen) - Optional
            if apply_stage1 and stats['ohlcv_collected'] > 0:
                try:
                    from modules.stock_pre_filter import StockPreFilter

                    pre_filter = StockPreFilter(db_path=self.db_path)
                    stage1_results = pre_filter.apply_stage1_filter(
                        region=self.region,
                        stage0_passed_tickers=[t for t in tickers if t]  # Only tickers with OHLCV data
                    )

                    stats['stage1_passed'] = len([r for r in stage1_results if r.get('stage1_passed')])
                    stats['stage1_failed'] = stats['ohlcv_collected'] - stats['stage1_passed']

                    logger.info(f"✅ Stage 1 complete: {stats['stage1_passed']}/{stats['ohlcv_collected']} passed "
                               f"({stats['stage1_passed']/stats['ohlcv_collected']*100:.1f}%)")

                except ImportError:
                    logger.warning("⚠️ StockPreFilter not available, Stage 1 skipped")
                except Exception as e:
                    logger.error(f"❌ Stage 1 filter failed: {e}")
            else:
                logger.info(f"⏭️ Stage 1 skipped")

            # Final statistics
            elapsed_time = (datetime.now() - stats['start_time']).total_seconds()
            logger.info(f"")
            logger.info(f"{'='*60}")
            logger.info(f"📊 OHLCV Collection Summary (region={self.region}, {elapsed_time:.1f}s)")
            logger.info(f"{'='*60}")
            logger.info(f"• Input tickers:          {stats['input_count']}")

            # Phase 6: Display blacklist statistics
            if 'blacklist_passed' in stats:
                logger.info(f"• Blacklist passed:       {stats['blacklist_passed']} ({stats['blacklist_passed']/stats['input_count']*100:.1f}%)")
                logger.info(f"• Blacklist rejected:     {stats['blacklist_rejected']}")

            logger.info(f"• Stage 0 passed:         {stats['stage0_passed']} ({stats['stage0_passed']/stats.get('blacklist_passed', stats['input_count'])*100:.1f}%)")
            logger.info(f"• OHLCV collected:        {stats['ohlcv_collected']} ({stats['ohlcv_collected']/stats['stage0_passed']*100:.1f}% of Stage 0)" if stats['stage0_passed'] > 0 else "• OHLCV collected:        0")
            if apply_stage1 and stats['ohlcv_collected'] > 0:
                logger.info(f"• Stage 1 passed:         {stats['stage1_passed']} ({stats['stage1_passed']/stats['ohlcv_collected']*100:.1f}% of OHLCV)")
            logger.info(f"{'='*60}")

            return stats

        except Exception as e:
            logger.error(f"❌ OHLCV collection with filtering failed: {e}")
            raise

    def _run_stage0_filter(self, tickers: List[str]) -> List[str]:
        """
        Execute Stage 0 filter on ticker list

        Args:
            tickers: List of tickers to filter

        Returns:
            List of tickers that passed Stage 0 filter
        """
        try:
            if not self.filtering_enabled:
                logger.warning("⚠️ Filtering disabled, returning all tickers")
                return tickers

            passed_tickers = []

            logger.info(f"🔍 Running Stage 0 filter for {len(tickers)} tickers...")

            for idx, ticker in enumerate(tickers, 1):
                try:
                    # Query ticker data from database or Stage 0 cache
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()

                    # Try to get data from filter_cache_stage0 first
                    cursor.execute("""
                        SELECT market_cap_local, trading_value_local, price_local, asset_type
                        FROM filter_cache_stage0
                        WHERE ticker = ? AND region = ?
                    """, (ticker, self.region))

                    result = cursor.fetchone()
                    conn.close()

                    if not result:
                        logger.debug(f"⚠️ [{idx}/{len(tickers)}] {ticker} No Stage 0 cache data")
                        continue

                    # Build stock data for filter
                    stock_data = {
                        'ticker': ticker,
                        'market_cap_local': result[0],
                        'trading_value_local': result[1],
                        'price_local': result[2],
                        'asset_type': result[3] or 'STOCK'
                    }

                    # Apply Stage 0 filter
                    filter_result = self.filter_manager.apply_stage0_filter(self.region, stock_data)

                    if filter_result.passed:
                        passed_tickers.append(ticker)
                        logger.debug(f"✅ [{idx}/{len(tickers)}] {ticker} Passed Stage 0")
                    else:
                        logger.debug(f"❌ [{idx}/{len(tickers)}] {ticker} Failed Stage 0: {filter_result.reason}")

                except Exception as e:
                    logger.error(f"❌ [{idx}/{len(tickers)}] {ticker} Stage 0 filter error: {e}")
                    continue

            logger.info(f"✅ Stage 0 filter complete: {len(passed_tickers)}/{len(tickers)} passed "
                       f"({len(passed_tickers)/len(tickers)*100:.1f}%)")

            return passed_tickers

        except Exception as e:
            logger.error(f"❌ Stage 0 filter execution failed: {e}")
            return tickers  # Fallback to all tickers on error

    def _load_stage0_tickers(self) -> List[str]:
        """Load tickers from Stage 0 cache (filter_cache_stage0)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ticker
                FROM filter_cache_stage0
                WHERE region = ? AND stage0_passed = 1
                ORDER BY market_cap_krw DESC
            """, (self.region,))

            tickers = [row[0] for row in cursor.fetchall()]
            conn.close()

            logger.info(f"📊 Loaded {len(tickers)} tickers from Stage 0 cache")
            return tickers

        except Exception as e:
            logger.error(f"❌ Failed to load Stage 0 tickers: {e}")
            return []

    def apply_data_retention_policy(self, retention_days: int = 250) -> Dict[str, Any]:
        """
        Apply data retention policy - delete data older than 250 days

        Args:
            retention_days: Data retention period (default: 250 days for MA200 + buffer)

        Returns:
            Cleanup statistics
        """
        try:
            logger.info(f"🗑️ Data retention policy started (retention: {retention_days} days)")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')

            # Query deletion statistics
            cursor.execute("""
                SELECT
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT ticker) as affected_tickers,
                    MIN(date) as oldest_date,
                    MAX(date) as latest_date
                FROM ohlcv_data
                WHERE date < ?
            """, (cutoff_date,))

            stats = cursor.fetchone()

            if stats[0] == 0:
                logger.info("✅ No old data to clean up")
                conn.close()
                return {
                    'deleted_rows': 0,
                    'affected_tickers': 0,
                    'size_reduction_pct': 0.0
                }

            # Delete old data
            cursor.execute("DELETE FROM ohlcv_data WHERE date < ?", (cutoff_date,))
            deleted_rows = cursor.rowcount

            conn.commit()

            # VACUUM to reclaim disk space
            logger.info("🔧 Running VACUUM to optimize database...")
            cursor.execute("VACUUM")

            conn.close()

            size_reduction_pct = (deleted_rows / (deleted_rows + stats[0])) * 100 if deleted_rows > 0 else 0.0

            logger.info(f"✅ Cleanup complete: {deleted_rows:,} rows deleted from {stats[1]} tickers")
            logger.info(f"💾 Database optimized, estimated size reduction: {size_reduction_pct:.1f}%")

            return {
                'deleted_rows': deleted_rows,
                'affected_tickers': stats[1],
                'oldest_date': stats[2],
                'latest_date': stats[3],
                'size_reduction_pct': size_reduction_pct
            }

        except Exception as e:
            logger.error(f"❌ Data retention policy failed: {e}")
            raise


# CLI interface for standalone execution
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='KIS Data Collector - OHLCV data collection with multi-stage filtering')
    parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite database path')
    parser.add_argument('--region', default='KR', help='Market region (KR, US, HK, CN, JP, VN)')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to collect (optional)')
    parser.add_argument('--days', type=int, default=250, help='Number of days to collect (default: 250)')
    parser.add_argument('--force-full', action='store_true', help='Force full collection (ignore gap analysis)')

    # Phase 2 filtering options
    parser.add_argument('--with-filtering', action='store_true', help='Enable multi-stage filtering (Phase 2)')
    parser.add_argument('--apply-stage0', action='store_true', default=True, help='Apply Stage 0 filter (market cap, trading value)')
    parser.add_argument('--apply-stage1', action='store_true', help='Apply Stage 1 filter (technical pre-screen)')

    # Maintenance options
    parser.add_argument('--retention-days', type=int, default=250, help='Data retention days (default: 250)')
    parser.add_argument('--cleanup', action='store_true', help='Run data retention policy cleanup')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        collector = KISDataCollector(db_path=args.db_path, region=args.region)

        if args.cleanup:
            # Run data retention policy
            result = collector.apply_data_retention_policy(retention_days=args.retention_days)
            logger.info(f"Cleanup result: {result}")
        elif args.with_filtering:
            # Run data collection with filtering (Phase 2)
            logger.info("🚀 Starting OHLCV collection with multi-stage filtering (Phase 2)")
            stats = collector.collect_with_filtering(
                tickers=args.tickers,
                days=args.days,
                apply_stage0=args.apply_stage0,
                apply_stage1=args.apply_stage1
            )
            logger.info(f"📊 Final statistics: {stats}")
        else:
            # Run legacy data collection (Phase 1)
            logger.info("🚀 Starting legacy OHLCV collection (Phase 1, no filtering)")
            collector.collect_data(tickers=args.tickers, force_full=args.force_full)

        logger.info("✅ KIS Data Collector finished successfully")

    except Exception as e:
        logger.error(f"❌ KIS Data Collector failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
