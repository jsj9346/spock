"""
KIS ETF API Client

Korea Investment & Securities (한국투자증권) ETF API 클라이언트
- ETF daily OHLCV data
- ETF current price
- ETF NAV comparison (tracking error calculation)
- ETF detailed information

Author: Spock Trading System
"""

import requests
import logging
import pandas as pd
from typing import Dict
from datetime import datetime

from .base_kis_api import BaseKISAPI

logger = logging.getLogger(__name__)


class KISEtfAPI(BaseKISAPI):
    """
    KIS ETF API 클라이언트

    Features:
    - ETF daily OHLCV data
    - ETF current price and NAV
    - ETF NAV comparison trend (for tracking error)
    - ETF detailed information
    - OAuth 2.0 token authentication (inherited from BaseKISAPI)

    Inherits:
        BaseKISAPI: Token management and caching functionality
    """

    def __init__(self,
                 app_key: str,
                 app_secret: str,
                 base_url: str = 'https://openapi.koreainvestment.com:9443',
                 token_cache_path: str = 'data/.kis_token_cache.json'):
        """
        Initialize KIS ETF API client

        Args:
            app_key: KIS API App Key
            app_secret: KIS API App Secret
            base_url: API base URL
            token_cache_path: Path to token cache file (default: data/.kis_token_cache.json)
        """
        super().__init__(app_key, app_secret, base_url, token_cache_path)

    def get_ohlcv(self, ticker: str, days: int = 250) -> pd.DataFrame:
        """
        ETF 일별 OHLCV 데이터 조회

        Endpoint: GET /uapi/domestic-stock/v1/quotations/inquire-daily-price
        TR_ID: FHKST03010100 (ETF도 동일 TR_ID 사용)

        Args:
            ticker: ETF ticker code
            days: Historical days (max: 250)

        Returns:
            DataFrame with OHLCV data
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"

        end_date_str = datetime.now().strftime("%Y%m%d")

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010100",
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
            "fid_input_date_1": "",
            "fid_input_date_2": end_date_str,
            "fid_period_div_code": "D",
            "fid_org_adj_prc": "0",
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS ETF OHLCV error: {error_msg}")
                return pd.DataFrame()

            ohlcv_list = data.get('output2', [])
            if not ohlcv_list:
                logger.warning(f"⚠️ [{ticker}] No ETF OHLCV data")
                return pd.DataFrame()

            df = pd.DataFrame(ohlcv_list)
            df = df.rename(columns={
                'stck_bsop_date': 'date',
                'stck_oprc': 'open',
                'stck_hgpr': 'high',
                'stck_lwpr': 'low',
                'stck_clpr': 'close',
                'acml_vol': 'volume',
            })

            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df = df.sort_values('date').reset_index(drop=True)

            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)

            logger.info(f"✅ [{ticker}] {len(df)}일 ETF OHLCV 데이터 조회")
            return df

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS ETF OHLCV failed: {e}")
            return pd.DataFrame()

    def get_current_price(self, ticker: str) -> Dict:
        """
        ETF 현재가 조회

        Endpoint: GET /uapi/domestic-stock/v1/quotations/inquire-price
        TR_ID: FHKST01010100

        Args:
            ticker: ETF ticker code

        Returns:
            Dictionary with price data
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100",
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS ETF Price error: {error_msg}")
                return {}

            output = data.get('output', {})

            price_data = {
                'ticker': ticker,
                'stck_prpr': int(output.get('stck_prpr', 0)),  # 현재가
                'acml_vol': int(output.get('acml_vol', 0)),    # 거래량
            }

            logger.info(f"✅ [{ticker}] ETF 현재가: {price_data['stck_prpr']:,}원")
            return price_data

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS ETF Price failed: {e}")
            return {}

    def get_nav_comparison_trend(self, ticker: str, days: int = 250) -> Dict:
        """
        ETF NAV 괴리율 추이 조회

        Endpoint: GET /uapi/domestic-stock/v1/quotations/etf-nav-comparison
        TR_ID: FHKST01010900

        Args:
            ticker: ETF ticker code
            days: Historical days for tracking error calculation

        Returns:
            Dictionary with NAV comparison data
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/etf-nav-comparison"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010900",
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS NAV comparison error: {error_msg}")
                return {}

            output_list = data.get('output2', [])
            if not output_list:
                logger.warning(f"⚠️ [{ticker}] No NAV comparison data")
                return {}

            # Parse NAV comparison data
            nav_data = []
            for item in output_list[:days]:  # Limit to requested days
                nav_data.append({
                    'date': item.get('stck_bsop_date'),
                    'etf_price': float(item.get('stck_prpr', 0)),
                    'nav': float(item.get('nav_avg_prpr', 0)),  # NAV 평균가
                    'tracking_error': float(item.get('drat', 0)),  # 괴리율(%)
                })

            logger.info(f"✅ [{ticker}] NAV 괴리율 데이터 {len(nav_data)}일 조회")
            return {'nav_comparison': nav_data}

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS NAV comparison failed: {e}")
            return {}

    def get_etf_details(self, ticker: str) -> Dict:
        """
        ETF 상세정보 조회

        Endpoint: GET /uapi/domestic-stock/v1/quotations/etf-info
        TR_ID: FHKST01010800

        Args:
            ticker: ETF ticker code

        Returns:
            Dictionary with ETF details
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/etf-info"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010800",
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS ETF details error: {error_msg}")
                return {}

            output = data.get('output', {})

            etf_details = {
                'ticker': ticker,
                'etf_name': output.get('etf_nm'),  # ETF명
                'issuer': output.get('aset_mgmt_comp_nm'),  # 자산운용사
                'tracking_index': output.get('idx_bztp_scl_itm_nm'),  # 추종지수
                'expense_ratio': float(output.get('tot_expn_rt', 0)),  # 총보수율
                'listed_shares': int(output.get('lstg_shr_numb', 0)),  # 상장주식수
            }

            logger.info(f"✅ [{ticker}] ETF 상세정보 조회: {etf_details['etf_name']}")
            return etf_details

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS ETF details failed: {e}")
            return {}

    def get_etf_tracking_error(self, ticker: str) -> Dict:
        """
        ETF/ETN 추적오차 조회 (기간별)

        Endpoint: GET /uapi/etfetn/v1/quotations/inquire-price
        TR_ID: FHPST02400000

        Args:
            ticker: ETF ticker code

        Returns:
            Dictionary with tracking error data:
            {
                'tracking_error_20d': float,
                'tracking_error_60d': float,
                'tracking_error_120d': float,
                'tracking_error_250d': float,
            }
        """
        self._rate_limit()

        url = f"{self.base_url}/uapi/etfetn/v1/quotations/inquire-price"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST02400000",
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.error(f"❌ [{ticker}] KIS ETF tracking error API error: {error_msg}")
                return {}

            output = data.get('output', {})

            # Extract tracking error fields
            # Try multiple possible field name patterns
            tracking_error = {}

            # Pattern 1: trc_errt_XXd format
            for period in ['20d', '60d', '120d', '250d']:
                field_name = f'trc_errt_{period}'
                if field_name in output:
                    tracking_error[f'tracking_error_{period}'] = float(output.get(field_name, 0))

            # Pattern 2: tracking_error_XXd format
            if not tracking_error:
                for period in ['20d', '60d', '120d', '250d']:
                    field_name = f'tracking_error_{period}'
                    if field_name in output:
                        tracking_error[field_name] = float(output.get(field_name, 0))

            # Pattern 3: Single trc_errt field (fallback - use for all periods)
            if not tracking_error and 'trc_errt' in output:
                trc_value = float(output.get('trc_errt', 0))
                tracking_error = {
                    'tracking_error_20d': trc_value,
                    'tracking_error_60d': trc_value,
                    'tracking_error_120d': trc_value,
                    'tracking_error_250d': trc_value,
                }
                logger.info(f"✅ [{ticker}] ETF 추적오차(단일): {trc_value}%")

            if tracking_error:
                logger.info(f"✅ [{ticker}] ETF 추적오차(기간별): 20d={tracking_error.get('tracking_error_20d', 0)}%, "
                          f"60d={tracking_error.get('tracking_error_60d', 0)}%, "
                          f"120d={tracking_error.get('tracking_error_120d', 0)}%, "
                          f"250d={tracking_error.get('tracking_error_250d', 0)}%")
                return tracking_error
            else:
                logger.warning(f"⚠️ [{ticker}] No tracking error fields found in response")
                logger.debug(f"Available fields: {list(output.keys())}")
                return {}

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS ETF tracking error failed: {e}")
            return {}

    def get_etf_holdings(self, ticker: str) -> list:
        """
        ETF 구성종목 조회 (Phase 2: 2025-10-17)

        Endpoint: GET /uapi/domestic-stock/v1/quotations/etf-component-stocks
        TR_ID: FHKST01010700 (예상 TR_ID - 실제 API 문서 확인 필요)

        Args:
            ticker: ETF ticker code

        Returns:
            List of holding dictionaries:
            [
                {
                    'stock_ticker': '005930',
                    'stock_name': '삼성전자',
                    'weight': 25.5,
                    'shares': 1000000,
                    'market_value': 75000000000,
                    'rank_in_etf': 1,
                },
                ...
            ]

        Note:
            - KIS API가 ETF 구성종목 API를 제공하지 않을 수 있음
            - 그 경우 빈 리스트 반환하고 KRX API fallback 사용
        """
        self._rate_limit()

        # Try endpoint 1: /uapi/domestic-stock/v1/quotations/etf-component-stocks
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/etf-component-stocks"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010700",  # 예상 TR_ID (실제 확인 필요)
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check if API is not supported (404, invalid TR_ID, etc.)
            if response.status_code == 404:
                logger.warning(f"⚠️ [{ticker}] KIS ETF holdings API not available (404)")
                return []

            if data.get('rt_cd') != '0':
                error_msg = data.get('msg1', 'Unknown error')
                logger.warning(f"⚠️ [{ticker}] KIS ETF holdings error: {error_msg}")

                # Try alternative TR_ID or endpoint
                return self._try_alternative_etf_holdings(ticker)

            # Parse holdings data
            holdings_list = data.get('output', [])
            if not holdings_list:
                logger.warning(f"⚠️ [{ticker}] No holdings data from KIS API")
                return []

            holdings = []
            for idx, item in enumerate(holdings_list, start=1):
                holding = {
                    'stock_ticker': item.get('stck_shrn_iscd', ''),  # 종목코드
                    'stock_name': item.get('hts_kor_isnm', ''),      # 종목명
                    'weight': float(item.get('etf_pstk_cstd_rt', 0)),  # 구성비율
                    'shares': int(item.get('etf_pstk_qty', 0)),     # 보유주식수
                    'market_value': float(item.get('etf_pstk_amt', 0)),  # 보유금액
                    'rank_in_etf': idx,
                }
                holdings.append(holding)

            logger.info(f"✅ [{ticker}] KIS API로 {len(holdings)}개 구성종목 조회")
            return holdings

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"⚠️ [{ticker}] KIS ETF holdings endpoint not found")
                return []
            else:
                logger.error(f"❌ [{ticker}] KIS ETF holdings HTTP error: {e}")
                return []

        except Exception as e:
            logger.error(f"❌ [{ticker}] KIS ETF holdings failed: {e}")
            return []

    def _try_alternative_etf_holdings(self, ticker: str) -> list:
        """
        Alternative ETF holdings endpoint (fallback within KIS API)

        Tries different TR_IDs or endpoints if primary fails

        Args:
            ticker: ETF ticker code

        Returns:
            List of holdings or empty list
        """
        # Try alternative endpoint: /uapi/etfetn/v1/quotations/component-stocks
        self._rate_limit()

        url = f"{self.base_url}/uapi/etfetn/v1/quotations/component-stocks"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST02500000",  # Alternative TR_ID
        }

        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_input_iscd": ticker,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 404:
                logger.info(f"ℹ️ [{ticker}] Alternative ETF holdings endpoint also not available")
                return []

            response.raise_for_status()
            data = response.json()

            if data.get('rt_cd') != '0':
                logger.info(f"ℹ️ [{ticker}] Alternative ETF holdings API not supported")
                return []

            # Parse holdings (same structure)
            holdings_list = data.get('output', [])
            if not holdings_list:
                return []

            holdings = []
            for idx, item in enumerate(holdings_list, start=1):
                holding = {
                    'stock_ticker': item.get('stck_shrn_iscd', ''),
                    'stock_name': item.get('hts_kor_isnm', ''),
                    'weight': float(item.get('etf_pstk_cstd_rt', 0)),
                    'shares': int(item.get('etf_pstk_qty', 0)),
                    'market_value': float(item.get('etf_pstk_amt', 0)),
                    'rank_in_etf': idx,
                }
                holdings.append(holding)

            logger.info(f"✅ [{ticker}] Alternative API로 {len(holdings)}개 구성종목 조회")
            return holdings

        except Exception as e:
            logger.debug(f"Alternative ETF holdings endpoint failed: {e}")
            return []
