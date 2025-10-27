"""
KIS Domestic Stock API Client

Korea Investment & Securities (한국투자증권) 국내주식 API 클라이언트
- OAuth 2.0 token authentication (24-hour validity)
- Daily OHLCV data collection
- Real-time quote retrieval
- Rate limiting: 20 req/sec, 1,000 req/min

Author: Spock Trading System
"""

import requests
import logging
import pandas as pd
from typing import Dict
from datetime import datetime, timedelta

from .base_kis_api import BaseKISAPI

logger = logging.getLogger(__name__)


class KISDomesticStockAPI(BaseKISAPI):
    """
    KIS 국내주식 API 클라이언트

    Features:
    - OAuth 2.0 token authentication (inherited from BaseKISAPI)
    - Daily OHLCV historical data (up to 250 days)
    - Current price quote
    - Automatic token refresh and caching
    - Rate limiting compliance

    Inherits:
        BaseKISAPI: Token management and caching functionality
    """

    def __init__(self,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443',
                 token_cache_path: str = 'data/.kis_token_cache.json'):
        """
        Initialize KIS Domestic Stock API client

        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            base_url: API base URL (default: production)
            token_cache_path: Path to token cache file (default: data/.kis_token_cache.json)
        """
        super().__init__(app_key, app_secret, base_url, token_cache_path)

    def get_ohlcv(self, ticker: str, days: int = 250) -> pd.DataFrame:
        """
        일별 OHLCV 데이터 조회 (pagination 지원)

        Endpoint: GET /uapi/domestic-stock/v1/quotations/inquire-daily-price
        TR_ID: FHKST03010100

        Note: KIS API returns max 100 rows per request, so we use pagination for days > 100

        Args:
            ticker: Stock ticker code (6 digits)
            days: Historical days to fetch (default: 250, will paginate if > 100)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"

        # Determine end date (today) and calculate start date
        end_date = datetime.now()
        # Account for weekends/holidays with 1.5x multiplier
        target_start_date = end_date - timedelta(days=int(days * 1.5))

        # KIS API returns max 100 rows per request, so we need pagination
        # We'll request 100 calendar days at a time (~70 trading days)
        all_data = []
        current_end_date = end_date
        chunk_calendar_days = 150  # Request 150 calendar days at a time (~100 trading days)

        while current_end_date > target_start_date:
            self._rate_limit()

            # Calculate chunk start date
            chunk_start_date = current_end_date - timedelta(days=chunk_calendar_days)
            if chunk_start_date < target_start_date:
                chunk_start_date = target_start_date

            # Format dates for KIS API
            chunk_start_str = chunk_start_date.strftime("%Y%m%d")
            chunk_end_str = current_end_date.strftime("%Y%m%d")

            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {self._get_access_token()}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST03010100",  # 국내주식기간별시세(일/주/월/년)
            }

            params = {
                "fid_cond_mrkt_div_code": "J",  # J: 주식
                "fid_input_iscd": ticker,
                "fid_input_date_1": chunk_start_str,  # Start date (YYYYMMDD format)
                "fid_input_date_2": chunk_end_str,  # End date
                "fid_period_div_code": "D",  # D: 일봉, W: 주봉, M: 월봉
                "fid_org_adj_prc": "0",  # 0: 수정주가, 1: 원주가
            }

            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Check response status
                if data.get('rt_cd') != '0':
                    error_msg = data.get('msg1', 'Unknown error')
                    logger.error(f"❌ [{ticker}] KIS API error: {error_msg}")
                    break

                # Parse OHLCV data
                ohlcv_list = data.get('output2', [])
                if not ohlcv_list:
                    logger.debug(f"📊 [{ticker}] No data for chunk {chunk_start_str} → {chunk_end_str}")
                    break

                # Add to collected data
                all_data.extend(ohlcv_list)
                logger.debug(f"📊 [{ticker}] Collected {len(ohlcv_list)} rows for chunk {chunk_start_str} → {chunk_end_str}")

                # Move to next chunk (go backwards in time)
                current_end_date = chunk_start_date - timedelta(days=1)

            except Exception as e:
                logger.error(f"❌ [{ticker}] API request failed: {e}")
                break

        if not all_data:
            logger.warning(f"⚠️ [{ticker}] No OHLCV data collected")
            return pd.DataFrame()

        # Convert all collected data to DataFrame
        df = pd.DataFrame(all_data)

        # Rename columns to standard format
        df = df.rename(columns={
            'stck_bsop_date': 'date',      # 영업일자
            'stck_oprc': 'open',            # 시가
            'stck_hgpr': 'high',            # 고가
            'stck_lwpr': 'low',             # 저가
            'stck_clpr': 'close',           # 종가
            'acml_vol': 'volume',           # 누적거래량
        })

        # Select and reorder columns
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

        # Convert to numeric (KIS returns strings)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Convert date to datetime
        df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

        # Sort by date ascending
        df = df.sort_values('date').reset_index(drop=True)

        # Remove duplicates (pagination may cause overlaps)
        df = df.drop_duplicates(subset=['date'], keep='first').reset_index(drop=True)

        # Limit to requested days
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)

        logger.info(f"✅ [{ticker}] {len(df)}일 OHLCV 데이터 조회 (KIS API, {len(all_data)} total rows collected)")
        return df

    def get_current_price(self, ticker: str) -> Dict:
        """
        현재가 시세 조회

        Endpoint: GET /uapi/domestic-stock/v1/quotations/inquire-price
        TR_ID: FHKST01010100

        Args:
            ticker: Stock ticker code

        Returns:
            Dictionary with current price data
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",  # 국내주식현재가시세
        }

        params = {
            "fid_cond_mrkt_div_code": "J",  # J: 주식
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check response status
            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS Price API error: {error_msg}")
                return {}

            # Extract current price data
            output = data.get('output', {})

            price_data = {
                'ticker': ticker,
                'stck_prpr': int(output.get('stck_prpr', 0)),  # 현재가
                'stck_oprc': int(output.get('stck_oprc', 0)),  # 시가
                'stck_hgpr': int(output.get('stck_hgpr', 0)),  # 고가
                'stck_lwpr': int(output.get('stck_lwpr', 0)),  # 저가
                'acml_vol': int(output.get('acml_vol', 0)),    # 누적거래량
                'acml_tr_pbmn': int(output.get('acml_tr_pbmn', 0)),  # 누적거래대금
            }

            logger.info(f"✅ [{ticker}] 현재가: {price_data['stck_prpr']:,}원")
            return price_data

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS Price API failed: {e}")
            return {}

    def get_stock_info(self, ticker: str) -> Dict:
        """
        [DEPRECATED] 종목 기본 정보 조회 (액면가 포함)

        ⚠️ WARNING: This API endpoint is NO LONGER AVAILABLE in KIS OpenAPI

        Original Endpoint: GET /uapi/domestic-stock/v1/quotations/inquire-search-stock-info
        TR_ID: CTPF1002R
        Status: ❌ Returns 404 Not Found (endpoint removed from official catalog)

        Args:
            ticker: Stock ticker code (6 digits)

        Returns:
            Empty dictionary {} - API endpoint is deprecated

        Alternatives:
            1. Use get_current_price() for current market data (working)
            2. Use KIS GitHub master files for par_value/listing_shares:
               https://github.com/koreainvestment/open-trading-api/tree/main/stocks_info
            3. Use alternative data sources (Naver Finance, etc.)

        Note:
            Par value is NOT critical for trading decisions. Sector classification
            (from KRX/PyKRX APIs) remains the primary data requirement.
        """
        logger.warning(
            f"⚠️ [{ticker}] get_stock_info() is DEPRECATED - "
            f"KIS API endpoint /inquire-search-stock-info is no longer available (404 Not Found)"
        )
        logger.info(
            f"💡 [{ticker}] Use get_current_price() for market data or "
            f"KIS GitHub master files for par_value"
        )

        # Return empty dict to maintain backward compatibility
        return {}
