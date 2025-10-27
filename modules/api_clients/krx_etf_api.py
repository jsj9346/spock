"""
KRX ETF API Client (Fallback for KIS API)

한국거래소(KRX) 공식 ETF 데이터 조회 클라이언트
- ETF 구성종목 공시 데이터
- OTP (One Time Password) 기반 인증
- 공공 데이터이므로 API Key 불필요

Data Source: http://data.krx.co.kr
Usage: KIS API fallback when ETF holdings not available

Author: Spock Trading System
Date: 2025-10-17
"""

import requests
import logging
import pandas as pd
from typing import List, Dict
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class KRXEtfAPI:
    """
    KRX ETF API 클라이언트 (공공 데이터)

    Features:
    - ETF 구성종목 조회 (OTP 기반)
    - ETF 목록 조회
    - API Key 불필요 (공공 데이터)

    Authentication:
    - OTP (One Time Password) 방식
    - Step 1: OTP 발급 요청
    - Step 2: OTP로 데이터 조회
    """

    def __init__(self):
        """Initialize KRX ETF API client"""
        self.base_url = 'http://data.krx.co.kr'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'http://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd',
        })
        self.last_request_time = 0
        self.rate_limit_interval = 1.0  # 1초당 1요청 (자체 제한)

    def _rate_limit(self):
        """Rate limiting to avoid overloading KRX servers"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_interval:
            time.sleep(self.rate_limit_interval - elapsed)
        self.last_request_time = time.time()

    def _get_otp(self, menu_id: str, params: Dict = None) -> str:
        """
        KRX OTP (One Time Password) 발급

        Args:
            menu_id: KRX 메뉴 ID (e.g., 'MDC020103010901')
            params: Additional OTP parameters

        Returns:
            OTP string or empty string on failure
        """
        self._rate_limit()

        otp_url = f"{self.base_url}/comm/bldAttendant/getJsonData.cmd"

        otp_params = {
            'bld': 'MKD/04/0406/04060100/mkd04060100_01',  # ETF 구성종목
            'name': 'form',
        }

        if params:
            otp_params.update(params)

        try:
            response = self.session.get(otp_url, params=otp_params, timeout=10)
            response.raise_for_status()

            # OTP는 response body에 plain text로 반환됨
            otp = response.text.strip()

            if not otp or len(otp) < 10:
                logger.error(f"❌ Invalid OTP received: {otp}")
                return ''

            logger.debug(f"✅ OTP 발급 성공: {otp[:20]}...")
            return otp

        except Exception as e:
            logger.error(f"❌ OTP 발급 실패: {e}")
            return ''

    def get_etf_holdings(self, ticker: str, as_of_date: str = None) -> List[Dict]:
        """
        ETF 구성종목 조회 (KRX 공시 데이터)

        Args:
            ticker: ETF ticker code (e.g., '152100')
            as_of_date: Date (YYYYMMDD). If None, uses latest available.

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
        """
        self._rate_limit()

        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y%m%d")

        # Step 1: Get OTP
        otp_params = {
            'isuCd': ticker,  # ETF 코드
            'trdDd': as_of_date,  # 조회일자
        }

        otp = self._get_otp(menu_id='MDC020103010901', params=otp_params)

        if not otp:
            logger.error(f"❌ [{ticker}] OTP 발급 실패 - 구성종목 조회 불가")
            return []

        # Step 2: Fetch data using OTP
        data_url = f"{self.base_url}/comm/bldAttendant/getJsonData.cmd"

        data_params = {
            'code': otp,
            'isuCd': ticker,
            'trdDd': as_of_date,
        }

        try:
            self._rate_limit()
            response = self.session.get(data_url, params=data_params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # KRX 응답 구조: {'output': [...]}
            if 'output' not in data:
                logger.warning(f"⚠️ [{ticker}] No output in KRX response")
                return []

            holdings_raw = data['output']

            if not holdings_raw:
                logger.warning(f"⚠️ [{ticker}] No holdings data for {as_of_date}")
                return []

            # Parse holdings
            holdings = []
            for idx, item in enumerate(holdings_raw, start=1):
                try:
                    holding = {
                        'stock_ticker': item.get('ISU_SRT_CD', '').strip(),  # 종목코드
                        'stock_name': item.get('ISU_ABBRV', '').strip(),      # 종목명
                        'weight': float(item.get('COMPST_RTO', 0)),           # 구성비율(%)
                        'shares': int(item.get('COMPST_AMT', 0)),             # 구성수량
                        'market_value': float(item.get('VALU_AMT', 0)),       # 평가금액
                        'rank_in_etf': idx,
                    }

                    # Validate
                    if holding['stock_ticker'] and holding['weight'] > 0:
                        holdings.append(holding)

                except (ValueError, TypeError) as e:
                    logger.debug(f"⚠️ Holding parse error: {e} - {item}")
                    continue

            logger.info(f"✅ [{ticker}] KRX API로 {len(holdings)}개 구성종목 조회 (기준일: {as_of_date})")
            return holdings

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ [{ticker}] KRX data fetch HTTP error: {e}")
            return []

        except Exception as e:
            logger.error(f"❌ [{ticker}] KRX ETF holdings failed: {e}")
            return []

    def get_etf_list(self, as_of_date: str = None) -> List[Dict]:
        """
        상장 ETF 목록 조회

        Args:
            as_of_date: Date (YYYYMMDD). If None, uses latest available.

        Returns:
            List of ETF dictionaries
        """
        self._rate_limit()

        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y%m%d")

        # Step 1: Get OTP
        otp_params = {
            'trdDd': as_of_date,
        }

        otp = self._get_otp(menu_id='MDC020103010101', params=otp_params)

        if not otp:
            logger.error("❌ ETF 목록 OTP 발급 실패")
            return []

        # Step 2: Fetch data
        data_url = f"{self.base_url}/comm/bldAttendant/getJsonData.cmd"

        data_params = {
            'code': otp,
            'trdDd': as_of_date,
        }

        try:
            self._rate_limit()
            response = self.session.get(data_url, params=data_params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if 'output' not in data:
                logger.warning("⚠️ No output in KRX ETF list response")
                return []

            etfs_raw = data['output']

            # Parse ETF list
            etfs = []
            for item in etfs_raw:
                try:
                    etf = {
                        'ticker': item.get('ISU_SRT_CD', '').strip(),
                        'name': item.get('ISU_ABBRV', '').strip(),
                        'exchange': 'KRX',
                        'total_assets': float(item.get('NAV', 0)),  # 순자산총액
                        'listed_shares': int(item.get('LIST_SHRS', 0)),  # 상장주식수
                    }

                    if etf['ticker']:
                        etfs.append(etf)

                except (ValueError, TypeError):
                    continue

            logger.info(f"✅ KRX에서 {len(etfs)}개 ETF 목록 조회 (기준일: {as_of_date})")
            return etfs

        except Exception as e:
            logger.error(f"❌ KRX ETF list failed: {e}")
            return []
