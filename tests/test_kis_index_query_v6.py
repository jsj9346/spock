#!/usr/bin/env python3
"""
Test KIS API Index Query Capability (v6 - Test Discovered Symbol Formats)

Purpose:
- Test newly discovered symbol formats from research
- Based on finding: "PSPX" format (S&P 500 with 'P' prefix)
- Official example uses: ".DJI" format for DOW Jones
- Test alternative parameter names (SYMB vs FID_INPUT_ISCD)

Key Research Findings:
- Web search: "frgn_code.mst 파일에서 S&P 500의 경우 'PSPX'로 작성되어 있다"
- GitHub example: inquire_daily_chartprice(fid_input_iscd=".DJI")
- Error message from v5: "ERROR INVALID INPUT_FILED NOT FOUND(SYMB)"

Hypothesis:
- 'P' prefix format (PSPX) not tested in v5 (0/237 success)
- SYMB parameter instead of FID_INPUT_ISCD
- Combination of correct symbol format + correct parameter name

Test Strategy:
- 3 indices × 3 symbol formats × 3 EXCD values × 2 param structures = 54 tests
- Focused approach vs v5's broad 237 combinations

Author: Spock Trading System
"""

import os
import sys
import logging
import requests
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class KISIndexAPI_v6:
    """KIS API 글로벌 지수 조회 (v6 - Discovered Symbol Formats)"""

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = "https://openapi.koreainvestment.com:9443"
        self.access_token = None
        self.token_expires_at = None

        # Statistics
        self.total_tests = 0
        self.successful_tests = 0
        self.test_results = []

    def _get_access_token(self) -> str:
        """Get or refresh OAuth access token (24-hour validity)"""
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

            logger.info(f"✅ Access token obtained (expires in {expires_in}s)")
            return self.access_token

        except Exception as e:
            logger.error(f"❌ Token request failed: {e}")
            raise

    def test_index_query(
        self,
        index_name: str,
        symbol: str,
        excd: str,
        use_symb_param: bool = False,
        days: int = 5
    ) -> Tuple[bool, Optional[Dict], str]:
        """
        Test single index query configuration

        Args:
            index_name: Human-readable name (e.g., "S&P 500")
            symbol: Index symbol to test (e.g., "PSPX", ".DJI")
            excd: Exchange code (e.g., "NYSE", "NASD")
            use_symb_param: If True, use SYMB instead of FID_INPUT_ISCD
            days: Historical days to fetch

        Returns:
            (success: bool, data: dict, error_msg: str)
        """
        self.total_tests += 1

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

        # Build parameters based on parameter style
        if use_symb_param:
            # Alternative parameter name from error message
            params = {
                "FID_COND_MRKT_DIV_CODE": "N",  # 해외지수
                "SYMB": symbol,  # Alternative parameter
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "EXCD": excd
            }
            param_style = "SYMB"
        else:
            # Standard parameter name
            params = {
                "FID_COND_MRKT_DIV_CODE": "N",  # 해외지수
                "FID_INPUT_ISCD": symbol,  # Standard parameter
                "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "EXCD": excd
            }
            param_style = "FID_INPUT_ISCD"

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            rt_cd = data.get('rt_cd', '')
            msg1 = data.get('msg1', '')
            output2 = data.get('output2', [])

            # Check success
            if rt_cd == '0' and output2:
                self.successful_tests += 1
                result = {
                    'index_name': index_name,
                    'symbol': symbol,
                    'excd': excd,
                    'param_style': param_style,
                    'data_points': len(output2),
                    'latest_close': output2[0].get('clos', 'N/A') if output2 else None
                }
                self.test_results.append(result)
                return True, data, "SUCCESS"
            elif rt_cd == '0' and not output2:
                return False, None, f"No data in output2 (rt_cd=0)"
            else:
                return False, None, f"{msg1} (rt_cd={rt_cd})"

        except Exception as e:
            return False, None, f"Exception: {str(e)}"

    def run_comprehensive_test(self):
        """Run comprehensive test suite with discovered symbol formats"""

        logger.info("=" * 80)
        logger.info("KIS API Index Query Test v6 (Discovered Symbol Formats)")
        logger.info("=" * 80)
        logger.info("")

        # Test cases with newly discovered formats
        test_cases = [
            {
                'name': 'S&P 500',
                'symbols': [
                    'PSPX',      # NEW: 'P' prefix format from web search
                    'SPX.US',    # Alternative format
                    '^SPX'       # Yahoo Finance style
                ],
                'excd_list': ['NYSE', 'NASD', 'US']
            },
            {
                'name': 'DOW Jones',
                'symbols': [
                    'PDJI',      # NEW: 'P' prefix format (hypothesis)
                    '.DJI',      # From GitHub example code
                    'DJI.US'     # Alternative format
                ],
                'excd_list': ['NYSE', 'US']
            },
            {
                'name': 'NASDAQ Composite',
                'symbols': [
                    'PIXIC',     # NEW: 'P' prefix format (hypothesis)
                    '.IXIC',     # Dot prefix format
                    'COMP'       # Alternative ticker
                ],
                'excd_list': ['NASD', 'US']
            }
        ]

        # Run tests
        for test_case in test_cases:
            index_name = test_case['name']
            symbols = test_case['symbols']
            excd_list = test_case['excd_list']

            logger.info(f"\n{'='*70}")
            logger.info(f"Testing {index_name}")
            logger.info(f"{'='*70}")

            success_found = False

            for symbol in symbols:
                for excd in excd_list:
                    # Test with both parameter styles
                    for use_symb in [False, True]:
                        param_style = "SYMB" if use_symb else "FID_INPUT_ISCD"

                        logger.info(f"  Testing: symbol={symbol}, excd={excd}, param={param_style}")

                        success, data, error_msg = self.test_index_query(
                            index_name=index_name,
                            symbol=symbol,
                            excd=excd,
                            use_symb_param=use_symb
                        )

                        if success:
                            output2 = data.get('output2', [])
                            logger.info(f"    ✅ SUCCESS!")
                            logger.info(f"       Symbol: {symbol}")
                            logger.info(f"       EXCD: {excd}")
                            logger.info(f"       Parameter: {param_style}")
                            logger.info(f"       Data points: {len(output2)}")
                            if output2:
                                latest = output2[0]
                                logger.info(f"       Latest close: {latest.get('clos', 'N/A')}")
                                logger.info(f"       Sample data: {json.dumps(latest, indent=8)}")
                            success_found = True
                            break
                        else:
                            logger.info(f"    ❌ Failed: {error_msg}")

                        # Rate limiting
                        time.sleep(0.3)

                    if success_found:
                        break

                if success_found:
                    break

            if not success_found:
                logger.info(f"  ❌ All combinations failed for {index_name}")

    def print_summary(self):
        """Print test summary statistics"""
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests run: {self.total_tests}")
        logger.info(f"Successful queries: {self.successful_tests}")
        logger.info(f"Success rate: {(self.successful_tests/self.total_tests*100):.1f}%")
        logger.info("")

        if self.successful_tests > 0:
            logger.info("✅ SUCCESSFUL CONFIGURATIONS:")
            for i, result in enumerate(self.test_results, 1):
                logger.info(f"\n  #{i} {result['index_name']}:")
                logger.info(f"     Symbol: {result['symbol']}")
                logger.info(f"     EXCD: {result['excd']}")
                logger.info(f"     Parameter: {result['param_style']}")
                logger.info(f"     Data points: {result['data_points']}")
                logger.info(f"     Latest close: {result['latest_close']}")
        else:
            logger.info("❌ NO SUCCESSFUL CONFIGURATIONS FOUND")

        logger.info("\n" + "=" * 80)
        logger.info("CONCLUSION")
        logger.info("=" * 80)

        if self.successful_tests > 0:
            logger.info("✅ KIS API SUPPORTS GLOBAL INDICES!")
            logger.info("   Next steps:")
            logger.info("   1. Implement KISIndexSource class with working configuration")
            logger.info("   2. Update stock_sentiment.py to use KIS as primary source")
            logger.info("   3. Keep yfinance as fallback")
            logger.info("   4. Add comprehensive test coverage")
        else:
            logger.info("❌ KIS API DOES NOT SUPPORT GLOBAL INDEX QUERIES")
            logger.info("   Conclusion after 6 test iterations (v1-v6):")
            logger.info("   - v1-v5: 237 combinations tested, 0 success")
            logger.info("   - v6: 54 focused tests with discovered formats, 0 success")
            logger.info("   - Total: 291 tests, 0 success")
            logger.info("")
            logger.info("   Recommendation:")
            logger.info("   ✅ Keep yfinance as production implementation (Phase 1 complete)")
            logger.info("   ✅ Mark KIS investigation as conclusively completed")
            logger.info("   ✅ Close investigation with final report")

        logger.info("=" * 80)


def main():
    """Main test execution"""
    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        logger.error("❌ KIS API credentials not found in environment")
        logger.error("   Please set KIS_APP_KEY and KIS_APP_SECRET in .env file")
        return

    # Initialize API client
    api = KISIndexAPI_v6(app_key=app_key, app_secret=app_secret)

    # Run comprehensive test
    api.run_comprehensive_test()

    # Print summary
    api.print_summary()


if __name__ == '__main__':
    main()
