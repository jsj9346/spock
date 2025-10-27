#!/usr/bin/env python3
"""
Test KIS API Index Query Capability (v4 - Add EXCD Parameter)

Purpose:
- Test with EXCD parameter added (exchange code)
- Error from v3: "ERROR INVALID INPUT_FILED NOT FOUND(EXCD)"

Key Finding from v3:
- Correct endpoint: inquire-daily-chartprice
- Missing parameter: EXCD (거래소 코드)
- Need to determine correct EXCD values for indices

Hypothesis:
- Indices might use special EXCD codes
- Try common values: 'IDX', 'NAS', 'NYS', 'HKG', 'TYO'

Author: Spock Trading System
"""

import os
import sys
import logging
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


class KISIndexAPI:
    """KIS API 글로벌 지수 조회 (v4 - EXCD 파라미터 추가)"""

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = "https://openapi.koreainvestment.com:9443"
        self.access_token = None
        self.token_expires_at = None

    def _get_access_token(self) -> str:
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {'content-type': 'application/json'}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()

            self.access_token = data['access_token']
            expires_in = int(data.get('expires_in', 86400))
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"✅ Access token obtained")
            return self.access_token

        except Exception as e:
            logger.error(f"❌ Token request failed: {e}")
            raise

    def get_index_data(self, index_code: str, excd: str, days: int = 5) -> dict:
        """
        Get index data with EXCD parameter

        Args:
            index_code: e.g., "DJI@DJI"
            excd: Exchange code (trying different values)
            days: Historical days
        """
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "HHDFS76240000",
        }

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days+10)

        params = {
            "FID_COND_MRKT_DIV_CODE": "N",  # 해외지수
            "FID_INPUT_ISCD": index_code,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "EXCD": excd  # NEW: Exchange code
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            rt_cd = data.get('rt_cd', '')
            msg1 = data.get('msg1', '')

            if rt_cd != '0':
                return None, f"{msg1} (rt_cd={rt_cd})"

            return data, None

        except Exception as e:
            return None, str(e)


def test_kis_index_api_v4():
    """Test with EXCD parameter (try multiple values)"""
    logger.info("=" * 80)
    logger.info("KIS API Index Query Test v4 (With EXCD Parameter)")
    logger.info("=" * 80)

    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        logger.error("❌ Credentials not found")
        return

    kis_api = KISIndexAPI(app_key=app_key, app_secret=app_secret)

    # Test with various EXCD values
    test_cases = [
        {'name': 'DOW Jones', 'code': 'DJI@DJI', 'excd_candidates': ['IDX', 'NYS', 'NYSE', 'NAS', 'NASD']},
        {'name': 'NASDAQ', 'code': 'IXIC@IXIC', 'excd_candidates': ['IDX', 'NAS', 'NASD', 'NYSE']},
        {'name': 'S&P 500', 'code': 'US500@SPX', 'excd_candidates': ['IDX', 'NYS', 'NYSE', 'SPX']},
    ]

    for test_case in test_cases:
        index_name = test_case['name']
        index_code = test_case['code']
        excd_list = test_case['excd_candidates']

        logger.info(f"\n{'='*70}")
        logger.info(f"Testing {index_name} ({index_code})")
        logger.info(f"{'='*70}")

        success = False

        for excd in excd_list:
            logger.info(f"  Trying EXCD={excd}...")

            data, error = kis_api.get_index_data(index_code, excd, days=5)

            if data:
                output2 = data.get('output2', [])
                if output2:
                    logger.info(f"    ✅ SUCCESS with EXCD={excd}")
                    logger.info(f"       Data points: {len(output2)}")
                    latest = output2[0]
                    logger.info(f"       Latest close: {latest.get('clos', 'N/A')}")
                    success = True
                    break
                else:
                    logger.info(f"    ⚠️ No data (EXCD={excd})")
            else:
                logger.info(f"    ❌ Failed: {error}")

            time.sleep(0.3)

        if not success:
            logger.info(f"  ❌ All EXCD values failed for {index_name}")

    logger.info("\n" + "=" * 80)
    logger.info("Conclusion")
    logger.info("=" * 80)
    logger.info("If no EXCD value worked, KIS API may not support index queries.")
    logger.info("Recommendation: Use yfinance as primary data source.")
    logger.info("=" * 80)


if __name__ == '__main__':
    test_kis_index_api_v4()
