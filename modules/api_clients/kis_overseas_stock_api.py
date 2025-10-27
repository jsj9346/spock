"""
KIS Overseas Stock API Client

Korea Investment & Securities (한국투자증권) 해외주식 API 클라이언트
- OAuth 2.0 token authentication (24-hour validity)
- Global stock markets: US, HK, CN, JP, VN, SG
- Tradable ticker filtering (한국인 거래 가능 종목만)
- Rate limiting: 20 req/sec, 1,000 req/min

Supported Markets:
- US: NASD (NASDAQ), NYSE, AMEX
- HK: SEHK (Hong Kong Stock Exchange)
- CN: SHAA (Shanghai), SZAA (Shenzhen) - 선강통/후강통 경로
- JP: TKSE (Tokyo Stock Exchange)
- VN: HASE (Ho Chi Minh), VNSE (Hanoi)
- SG: SGXC (Singapore Exchange) - 시세 조회 중심

Author: Spock Trading System
"""

import requests
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .base_kis_api import BaseKISAPI

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_MASTER_FILE_MANAGER = None

def _get_master_file_manager():
    """Lazy initialization of KISMasterFileManager"""
    global _MASTER_FILE_MANAGER
    if _MASTER_FILE_MANAGER is None:
        try:
            from modules.api_clients.kis_master_file_manager import KISMasterFileManager
            _MASTER_FILE_MANAGER = KISMasterFileManager()
            logger.info("✅ KISMasterFileManager initialized (lazy load)")
        except Exception as e:
            logger.warning(f"⚠️ KISMasterFileManager not available: {e}")
            _MASTER_FILE_MANAGER = False  # Mark as unavailable
    return _MASTER_FILE_MANAGER if _MASTER_FILE_MANAGER is not False else None


class KISOverseasStockAPI(BaseKISAPI):
    """
    KIS 해외주식 API 클라이언트

    Features:
    - OAuth 2.0 token authentication (inherited from BaseKISAPI)
    - Multi-market support (US, HK, CN, JP, VN, SG)
    - Tradable ticker list retrieval
    - Daily OHLCV historical data
    - Current price quote
    - Automatic token refresh and caching
    - Rate limiting compliance (20 req/sec)

    Exchange Codes:
    - NASD: NASDAQ
    - NYSE: New York Stock Exchange
    - AMEX: American Stock Exchange
    - SEHK: Hong Kong Stock Exchange
    - SHAA: Shanghai Stock Exchange (A-shares)
    - SZAA: Shenzhen Stock Exchange (A-shares)
    - TKSE: Tokyo Stock Exchange
    - HASE: Ho Chi Minh Stock Exchange
    - VNSE: Hanoi Stock Exchange
    - SGXC: Singapore Exchange

    Inherits:
        BaseKISAPI: Token management and caching functionality
    """

    # Exchange code mapping
    EXCHANGE_CODES = {
        'US': ['NASD', 'NYSE', 'AMEX'],
        'HK': ['SEHK'],
        'CN': ['SHAA', 'SZAA'],
        'JP': ['TKSE'],
        'VN': ['HASE', 'VNSE'],
        'SG': ['SGXC']
    }

    def __init__(self,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443',
                 token_cache_path: str = 'data/.kis_token_cache.json'):
        """
        Initialize KIS Overseas Stock API client

        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            base_url: API base URL (default: production)
            token_cache_path: Path to token cache file (default: data/.kis_token_cache.json)
        """
        super().__init__(app_key, app_secret, base_url, token_cache_path)

    def get_tradable_tickers(self,
                            exchange_code: str,
                            max_count: Optional[int] = None,
                            use_master_file: bool = True) -> List[str]:
        """
        거래소별 거래 가능 종목 리스트 조회 (Master File 우선, API 폴백)

        Data Source Priority:
        1. Master File: Instant, 6,500+ US stocks, no API calls
        2. KIS API: 20 req/sec, real-time data (fallback)

        Endpoint: GET /uapi/overseas-price/v1/quotations/inquire-search
        TR_ID varies by exchange

        Args:
            exchange_code: Exchange code (NASD, NYSE, SEHK, etc.)
            max_count: Maximum tickers to return (None = all)
            use_master_file: Try master file first (default: True)

        Returns:
            List of ticker symbols tradable through KIS

        Note:
            Returns only tickers available for trading by Korean investors

        Performance:
        - Master File: Instant (no API calls)
        - API Method: 20 req/sec (legacy fallback)
        """
        # Try master file first (if enabled)
        if use_master_file:
            tickers = self._get_tickers_from_master_file(exchange_code, max_count)
            if tickers:
                return tickers
            # Fall through to API method if master file fails
            logger.info(f"⚠️ [{exchange_code}] Master file unavailable, using API method")

        # API-based method (legacy fallback)
        return self._get_tickers_from_api(exchange_code, max_count)

    def _get_tickers_from_master_file(self,
                                      exchange_code: str,
                                      max_count: Optional[int] = None) -> List[str]:
        """
        Get tradable tickers from master file (instant, no API calls)

        Args:
            exchange_code: KIS exchange code (NASD, NYSE, AMEX, etc.)
            max_count: Maximum tickers to return (None = all)

        Returns:
            List of ticker symbols from master file

        Performance:
        - Instant: No API calls, reads from cached .cod file
        - Coverage: 6,527 US stocks, 500-1,000 HK/CN/JP/VN stocks

        Exchange Code to Market Code Mapping:
        - NASD → nas, NYSE → nys, AMEX → ams
        - SEHK → hks (Hong Kong)
        - SHAA → shs, SZAA → szs (China)
        - TKSE → tse (Japan)
        - HASE/VNSE → hnx/hsx (Vietnam)
        """
        try:
            master_mgr = _get_master_file_manager()
            if not master_mgr:
                return []

            # Map KIS API exchange code to master file market code
            exchange_to_market = {
                'NASD': 'nas',  # NASDAQ
                'NYSE': 'nys',  # New York Stock Exchange
                'AMEX': 'ams',  # American Stock Exchange
                'SEHK': 'hks',  # Hong Kong Stock Exchange
                'SHAA': 'shs',  # Shanghai Stock Exchange
                'SZAA': 'szs',  # Shenzhen Stock Exchange
                'TKSE': 'tse',  # Tokyo Stock Exchange
                'HASE': 'hnx',  # Hanoi Stock Exchange
                'VNSE': 'hsx',  # Ho Chi Minh Stock Exchange
            }

            market_code = exchange_to_market.get(exchange_code)
            if not market_code:
                logger.warning(f"⚠️ Unknown exchange code for master file: {exchange_code}")
                return []

            # Parse master file (cached, instant)
            df = master_mgr.parse_market(market_code)

            if df.empty:
                logger.warning(f"⚠️ [{market_code}] No data in master file")
                return []

            # Extract tickers
            tickers = df['Symbol'].dropna().tolist()

            # Apply max_count limit
            if max_count and len(tickers) > max_count:
                tickers = tickers[:max_count]

            logger.info(f"✅ [{exchange_code}] {len(tickers)} tickers from master file (instant)")
            return tickers

        except Exception as e:
            logger.warning(f"⚠️ [{exchange_code}] Master file read failed: {e}")
            return []

    def _get_tickers_from_api(self, exchange_code: str, max_count: Optional[int] = None) -> List[str]:
        """
        Get tradable tickers from KIS API (legacy method)

        Endpoint: GET /uapi/overseas-price/v1/quotations/inquire-search
        TR_ID varies by exchange

        Args:
            exchange_code: Exchange code (NASD, NYSE, SEHK, etc.)
            max_count: Maximum tickers to return (None = all)

        Returns:
            List of ticker symbols from KIS API

        Note:
            This is the original API-based method, kept as fallback
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/inquire-search"

        # TR_ID mapping for each exchange
        tr_id_map = {
            'NASD': 'HHDFS76240000',  # NASDAQ ticker search
            'NYSE': 'HHDFS76240000',  # NYSE ticker search
            'AMEX': 'HHDFS76240000',  # AMEX ticker search
            'SEHK': 'HHDFS76240000',  # HK ticker search
            'SHAA': 'HHDFS76240000',  # Shanghai ticker search
            'SZAA': 'HHDFS76240000',  # Shenzhen ticker search
            'TKSE': 'HHDFS76240000',  # Tokyo ticker search
            'HASE': 'HHDFS76240000',  # Vietnam ticker search
            'VNSE': 'HHDFS76240000',  # Vietnam ticker search
        }

        tr_id = tr_id_map.get(exchange_code, 'HHDFS76240000')

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

        params = {
            "AUTH": "",
            "EXCD": exchange_code,
            "CO_YN_PRICECUR": "",
            "CO_ST_PRICECUR": "",
            "CO_EN_PRICECUR": "",
            "CO_YN_RATE": "",
            "CO_ST_RATE": "",
            "CO_EN_RATE": "",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check response status
            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{exchange_code}] KIS ticker search error: {error_msg}")
                return []

            # Parse ticker list
            ticker_list_raw = data.get('output', [])
            if not ticker_list_raw:
                logger.warning(f"⚠️ [{exchange_code}] No tickers returned")
                return []

            # Extract ticker symbols
            tickers = [item.get('symb', '').strip() for item in ticker_list_raw if item.get('symb')]

            # Apply max_count limit
            if max_count and len(tickers) > max_count:
                tickers = tickers[:max_count]

            logger.info(f"✅ [{exchange_code}] {len(tickers)} tradable tickers retrieved")
            return tickers

        except Exception as e:
            logger.error(f"❌ [{exchange_code}] KIS ticker search failed: {e}")
            return []

    def get_ohlcv(self, ticker: str, exchange_code: str, days: int = 250) -> pd.DataFrame:
        """
        일별 OHLCV 데이터 조회 (해외주식)

        Endpoint: GET /uapi/overseas-price/v1/quotations/inquire-daily-chartprice
        TR_ID: HHDFS76240000 (unified for all exchanges)

        Args:
            ticker: Stock ticker symbol
            exchange_code: Exchange code (NASD, NYSE, SEHK, etc.)
            days: Historical days to fetch (max: varies by exchange)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDFS76240000",  # Unified TR_ID for all overseas markets
        }

        # Calculate period (YYYYMMDD format)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days+30)  # Add buffer for trading days

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # J: 해외주식 (N: 해외지수)
            "SYMB": ticker,                  # Stock ticker symbol (SYMB for stocks)
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),  # Start date
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),    # End date
            "FID_PERIOD_DIV_CODE": "D",     # D: Daily
            "EXCD": exchange_code,          # Exchange code
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check response status
            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS OHLCV error: {error_msg}")
                return pd.DataFrame()

            # Parse OHLCV data
            ohlcv_list = data.get('output2', [])
            if not ohlcv_list:
                logger.warning(f"⚠️ [{ticker}] No OHLCV data returned")
                return pd.DataFrame()

            # Convert to DataFrame
            df = pd.DataFrame(ohlcv_list)

            # Rename columns to standard format (KIS overseas format)
            df = df.rename(columns={
                'xymd': 'date',      # Date (YYYYMMDD)
                'open': 'open',      # Open
                'high': 'high',      # High
                'low': 'low',        # Low
                'clos': 'close',     # Close
                'tvol': 'volume',    # Volume
            })

            # Select and reorder columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

            # Sort by date ascending
            df = df.sort_values('date').reset_index(drop=True)

            # Limit to requested days
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)

            logger.info(f"✅ [{ticker}] {len(df)}일 OHLCV 데이터 조회 (KIS Overseas API)")
            return df

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS Overseas OHLCV failed: {e}")
            return pd.DataFrame()

    def get_current_price(self, ticker: str, exchange_code: str) -> Dict:
        """
        현재가 시세 조회 (해외주식)

        Endpoint: GET /uapi/overseas-price/v1/quotations/price
        TR_ID varies by exchange

        Args:
            ticker: Stock ticker symbol
            exchange_code: Exchange code

        Returns:
            Dictionary with current price data
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/price"

        tr_id_map = {
            'NASD': 'HHDFS00000300',  # US current price
            'NYSE': 'HHDFS00000300',
            'AMEX': 'HHDFS00000300',
            'SEHK': 'HHDFS00000300',  # HK current price
            'SHAA': 'HHDFS00000300',  # CN current price
            'SZAA': 'HHDFS00000300',
            'TKSE': 'HHDFS00000300',  # JP current price
            'HASE': 'HHDFS00000300',  # VN current price
            'VNSE': 'HHDFS00000300',
        }

        tr_id = tr_id_map.get(exchange_code, 'HHDFS00000300')

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

        params = {
            "AUTH": "",
            "EXCD": exchange_code,
            "SYMB": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check response status
            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS Price error: {error_msg}")
                return {}

            # Extract price data
            output = data.get('output', {})

            price_data = {
                'ticker': ticker,
                'exchange_code': exchange_code,
                'last': float(output.get('last', 0)),    # Current price
                'open': float(output.get('open', 0)),    # Open
                'high': float(output.get('high', 0)),    # High
                'low': float(output.get('low', 0)),      # Low
                'tvol': int(output.get('tvol', 0)),      # Volume
                'tamt': float(output.get('tamt', 0)),    # Amount
            }

            logger.info(f"✅ [{ticker}] 현재가: {price_data['last']}")
            return price_data

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS Price API failed: {e}")
            return {}

    def get_all_tradable_tickers(self,
                                 region: str,
                                 max_count: Optional[int] = None,
                                 use_master_file: bool = True) -> List[str]:
        """
        Get all tradable tickers for a region (combines all exchanges)

        Args:
            region: Region code (US, HK, CN, JP, VN, SG)
            max_count: Maximum tickers per exchange
            use_master_file: Try master file first (default: True)

        Returns:
            Combined list of tradable tickers

        Performance:
        - Master File: Instant (no API calls)
        - API Method: 20 req/sec × N exchanges
        """
        exchange_codes = self.EXCHANGE_CODES.get(region, [])
        if not exchange_codes:
            logger.error(f"❌ Unknown region: {region}")
            return []

        all_tickers = []
        for exchange_code in exchange_codes:
            tickers = self.get_tradable_tickers(
                exchange_code,
                max_count,
                use_master_file=use_master_file
            )
            all_tickers.extend(tickers)

        # Remove duplicates
        all_tickers = list(set(all_tickers))

        logger.info(f"✅ [{region}] Total {len(all_tickers)} unique tradable tickers")
        return all_tickers

    def get_tickers_with_details(self,
                                 region: str,
                                 force_refresh: bool = False) -> List[Dict]:
        """
        Get detailed ticker information from master files

        Args:
            region: Region code (US, HK, CN, JP, VN)
            force_refresh: Force download new master files

        Returns:
            List of ticker dictionaries with metadata:
            {
                'ticker': str,
                'name': str,
                'name_kor': str,
                'exchange': str,
                'region': str,
                'currency': str,
                'sector_code': str,
                'market_code': str
            }

        Performance:
        - Instant: Reads from cached .cod files (no API calls)
        - Coverage: ~6,500 US, ~500-1,000 per other region

        Example:
            >>> api = KISOverseasStockAPI(app_key, app_secret)
            >>> us_tickers = api.get_tickers_with_details('US')
            >>> print(f"Found {len(us_tickers)} US stocks")
            >>> print(us_tickers[0])
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'name_kor': '애플',
                'exchange': 'NASDAQ',
                'region': 'US',
                'currency': 'USD',
                'sector_code': '...',
                'market_code': 'nas'
            }
        """
        try:
            master_mgr = _get_master_file_manager()
            if not master_mgr:
                logger.warning("⚠️ Master file manager not available")
                return []

            # Get all tickers with details from master file manager
            tickers = master_mgr.get_all_tickers(region, force_refresh=force_refresh)

            logger.info(f"✅ [{region}] {len(tickers)} tickers with details from master files")
            return tickers

        except Exception as e:
            logger.error(f"❌ [{region}] Failed to get tickers with details: {e}")
            return []
