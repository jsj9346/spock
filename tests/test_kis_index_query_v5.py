#!/usr/bin/env python3
"""
Test KIS API Index Query Capability (v5 - Comprehensive Investigation)

Purpose:
- 토큰 캐싱 사용하여 rate limit 회피
- 다양한 EXCD 값 체계적으로 테스트
- TR_ID 변경 시도
- 상세한 에러 메시지 로깅

Previous Findings:
- v1-v2: 잘못된 endpoint 사용
- v3: EXCD 파라미터 누락 발견
- v4: Rate limit으로 테스트 중단

Key Hypothesis:
1. EXCD는 거래소 코드일 가능성 (NYSE, NASD, etc.)
2. 지수는 특별한 EXCD 값 필요할 수 있음 (IDX, INDEX, 공백, etc.)
3. TR_ID가 잘못되었을 가능성
4. FID_INPUT_ISCD 형식이 잘못되었을 가능성

Strategy:
- 토큰 캐싱으로 빠른 연속 테스트 가능
- 다양한 조합 체계적으로 시도
- 각 응답 상세 로깅

Author: Spock Trading System
Date: 2025-10-15
"""

import os
import sys
import logging
import requests
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class KISIndexAPIV5:
    """KIS API 글로벌 지수 조회 (v5 - 토큰 캐싱 + 체계적 테스트)"""

    TOKEN_CACHE_FILE = 'data/.kis_token_cache.json'

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = "https://openapi.koreainvestment.com:9443"
        self.access_token = None
        self.token_expires_at = None

        # Load cached token
        self._load_cached_token()

    def _load_cached_token(self) -> bool:
        """Load cached token from file"""
        if not os.path.exists(self.TOKEN_CACHE_FILE):
            logger.info("⚠️ No token cache found")
            return False

        try:
            with open(self.TOKEN_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)

            expiry = datetime.fromisoformat(cache_data['expiry'])

            # Check if token is still valid (with 1-hour buffer)
            if datetime.now() >= expiry - timedelta(hours=1):
                logger.info("⏰ Cached token expired")
                return False

            self.access_token = cache_data['access_token']
            self.token_expires_at = expiry

            logger.info(f"✅ Loaded cached token (expires: {expiry.strftime('%Y-%m-%d %H:%M')})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load cached token: {e}")
            return False

    def _save_token_cache(self):
        """Save token to cache file"""
        try:
            cache_data = {
                'access_token': self.access_token,
                'expiry': self.token_expires_at.isoformat()
            }

            os.makedirs(os.path.dirname(self.TOKEN_CACHE_FILE), exist_ok=True)

            with open(self.TOKEN_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"💾 Token cached until {self.token_expires_at.strftime('%Y-%m-%d %H:%M')}")

        except Exception as e:
            logger.error(f"❌ Failed to save token cache: {e}")

    def _get_access_token(self) -> str:
        """Get access token (from cache or request new)"""
        # Check if current token is still valid
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token

        # Request new token
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {'content-type': 'application/json'}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            logger.info("🔄 Requesting new access token...")
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()

            self.access_token = data['access_token']
            expires_in = int(data.get('expires_in', 86400))
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Save to cache
            self._save_token_cache()

            logger.info(f"✅ New access token obtained (valid for {expires_in}s)")
            return self.access_token

        except Exception as e:
            logger.error(f"❌ Token request failed: {e}")
            raise

    def test_index_query(self, index_code: str, excd: str, tr_id: str = "HHDFS76240000") -> dict:
        """
        Test index query with specific parameters

        Args:
            index_code: e.g., "DJI@DJI", "IXIC@IXIC", "US500@SPX"
            excd: Exchange code to try
            tr_id: Transaction ID (default: HHDFS76240000)

        Returns:
            dict with 'success', 'data', 'error', 'response_json'
        """
        url = f"{self.base_url}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"

        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)

        params = {
            "FID_COND_MRKT_DIV_CODE": "N",  # 해외지수
            "FID_INPUT_ISCD": index_code,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "EXCD": excd
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response_json = response.json()

            rt_cd = response_json.get('rt_cd', '')
            msg1 = response_json.get('msg1', '')
            msg_cd = response_json.get('msg_cd', '')

            # Check for success
            if rt_cd == '0':
                output2 = response_json.get('output2', [])
                if output2:
                    return {
                        'success': True,
                        'data': output2,
                        'error': None,
                        'response_json': response_json
                    }
                else:
                    return {
                        'success': False,
                        'data': None,
                        'error': f"No data in output2 (rt_cd=0 but empty response)",
                        'response_json': response_json
                    }
            else:
                return {
                    'success': False,
                    'data': None,
                    'error': f"{msg1} (rt_cd={rt_cd}, msg_cd={msg_cd})",
                    'response_json': response_json
                }

        except Exception as e:
            return {
                'success': False,
                'data': None,
                'error': str(e),
                'response_json': None
            }


def test_comprehensive_kis_index_api():
    """Comprehensive KIS API index query test"""
    logger.info("=" * 80)
    logger.info("KIS API Index Query Test v5 (Comprehensive Investigation)")
    logger.info("=" * 80)

    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        logger.error("❌ KIS_APP_KEY or KIS_APP_SECRET not found in environment")
        return

    api = KISIndexAPIV5(app_key=app_key, app_secret=app_secret)

    # Test configurations
    test_configs = [
        # US Indices
        {
            'name': 'DOW Jones',
            'codes': ['DJI@DJI', 'DJI', '.DJI'],
            'excd_candidates': ['NYS', 'NYSE', 'NASD', 'NAS', 'IDX', 'INDEX', '', 'US', 'USA']
        },
        {
            'name': 'NASDAQ Composite',
            'codes': ['IXIC@IXIC', 'IXIC', '.IXIC'],
            'excd_candidates': ['NASD', 'NAS', 'NASDAQ', 'NYS', 'IDX', 'INDEX', '', 'US']
        },
        {
            'name': 'S&P 500',
            'codes': ['US500@SPX', 'SPX', '.SPX', 'SPY'],
            'excd_candidates': ['NYS', 'NYSE', 'SPX', 'IDX', 'INDEX', '', 'US']
        },
    ]

    # TR_ID candidates (different transaction IDs to try)
    tr_id_candidates = [
        "HHDFS76240000",  # Current default
        "HHDFS76950200",  # Alternative (from overseas stock API)
        "FHKST66900400",  # Another alternative
    ]

    total_tests = 0
    success_count = 0
    results = []

    for config in test_configs:
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing {config['name']}")
        logger.info(f"{'='*70}")

        for index_code in config['codes']:
            for excd in config['excd_candidates']:
                for tr_id in tr_id_candidates:
                    total_tests += 1

                    logger.info(f"\n  [Test {total_tests}] code={index_code}, EXCD={excd!r}, TR_ID={tr_id}")

                    result = api.test_index_query(index_code, excd, tr_id)

                    if result['success']:
                        success_count += 1
                        data_points = len(result['data'])
                        latest = result['data'][0] if result['data'] else {}

                        logger.info(f"    ✅ SUCCESS!")
                        logger.info(f"       Data points: {data_points}")
                        logger.info(f"       Latest close: {latest.get('clos', 'N/A')}")
                        logger.info(f"       Latest date: {latest.get('xymd', 'N/A')}")

                        results.append({
                            'index_name': config['name'],
                            'index_code': index_code,
                            'excd': excd,
                            'tr_id': tr_id,
                            'status': 'SUCCESS',
                            'data_points': data_points
                        })

                        # Found working combination, skip remaining TR_IDs
                        break
                    else:
                        logger.info(f"    ❌ Failed: {result['error']}")

                        results.append({
                            'index_name': config['name'],
                            'index_code': index_code,
                            'excd': excd,
                            'tr_id': tr_id,
                            'status': 'FAILED',
                            'error': result['error']
                        })

                    # Small delay to avoid rate limiting
                    time.sleep(0.2)

                # If found success for this code+excd combo, skip remaining EXCDs
                if results and results[-1]['status'] == 'SUCCESS':
                    break

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total tests run: {total_tests}")
    logger.info(f"Successful queries: {success_count}")
    logger.info(f"Success rate: {(success_count/total_tests*100) if total_tests > 0 else 0:.1f}%")

    if success_count > 0:
        logger.info("\n✅ WORKING CONFIGURATIONS:")
        for result in results:
            if result['status'] == 'SUCCESS':
                logger.info(f"  {result['index_name']:15s} | code={result['index_code']:15s} | EXCD={result['excd']!r:10s} | TR_ID={result['tr_id']}")

    logger.info("\n" + "=" * 80)
    logger.info("CONCLUSION")
    logger.info("=" * 80)

    if success_count == 0:
        logger.info("❌ KIS API does NOT support global index queries")
        logger.info("   Recommendation: Use yfinance as primary data source")
        logger.info("   Reason: No valid parameter combination found after comprehensive testing")
    else:
        logger.info("✅ KIS API SUPPORTS global index queries!")
        logger.info("   Next steps:")
        logger.info("   1. Implement KISIndexSource using working configurations")
        logger.info("   2. Switch primary data source from yfinance to KIS API")
        logger.info("   3. Use yfinance as fallback")

    logger.info("=" * 80)


if __name__ == '__main__':
    test_comprehensive_kis_index_api()
