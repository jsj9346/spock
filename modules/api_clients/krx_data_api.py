"""
KRX Data API Client (data.krx.co.kr)

Official Korea Exchange data API wrapper
- No API key required
- Public endpoints for stock and ETF data
- Market tier detection (MAIN, NXT, KONEX)

Author: Spock Trading System
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class KRXDataAPI:
    """
    KRX 정보데이터시스템 API (data.krx.co.kr)

    Features:
    - Stock list (KOSPI, KOSDAQ, KONEX)
    - ETF list
    - Market information
    - No authentication required
    """

    BASE_URL = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'http://data.krx.co.kr/',
        })

    def get_stock_list(self, market: str = 'ALL') -> List[Dict]:
        """
        전체 종목 조회

        Args:
            market: 'ALL', 'KOSPI', 'KOSDAQ', 'KONEX'

        Returns:
            List of stock dictionaries with ticker, name, market, listing_date, shares

        Endpoint: MDCSTAT01901 (상장종목현황)
        """
        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',
            'locale': 'ko_KR',
            'mktId': market,
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'share': '1',
            'money': '1',
            'csvxls_isNo': 'false',
        }

        try:
            response = self.session.post(self.BASE_URL, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            tickers = []
            for item in result.get('OutBlock_1', []):
                market_map = {'KOSPI': 'KOSPI', 'KOSDAQ': 'KOSDAQ', 'KONEX': 'KONEX'}
                market_name = market_map.get(item.get('MKT_TP_NM', ''), 'UNKNOWN')

                tickers.append({
                    'ticker': item['ISU_SRT_CD'],
                    'name': item['ISU_ABBRV'],
                    'name_eng': item.get('ISU_ENG_NM'),
                    'market': market_name,
                    'market_classification': item.get('MKT_TP_NM', ''),  # For NXT detection
                    'listing_date': item.get('LIST_DD'),
                    'shares': self._parse_number(item.get('LIST_SHRS', '0')),
                    'data_source': 'KRX Data API',
                })

            logger.info(f"✅ KRX Data API: {len(tickers)}개 종목 조회")
            return tickers

        except Exception as e:
            logger.error(f"❌ KRX Data API failed: {e}")
            raise

    def get_etf_list(self) -> List[Dict]:
        """
        ETF 전체 목록 조회

        Returns:
            List of ETF dictionaries

        Endpoint: MDCSTAT04601 (ETF 종목 현황)
        """
        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT04601',
            'locale': 'ko_KR',
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'csvxls_isNo': 'false',
        }

        try:
            response = self.session.post(self.BASE_URL, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            # KRX ETF API uses 'output' key instead of 'OutBlock_1'
            etf_data = result.get('output', result.get('OutBlock_1', []))

            etfs = []
            for item in etf_data:
                etfs.append({
                    'ticker': item['ISU_SRT_CD'],
                    'name': item['ISU_ABBRV'],
                    'name_eng': item.get('ISU_ENG_NM'),
                    'market': 'KOSPI',  # ETFs trade on KOSPI
                    'issuer': item.get('COMPANY_NM'),  # 운용사
                    'tracking_index': item.get('OBJ_TP_NM'),  # 추종지수
                    'listed_shares': self._parse_number(item.get('LIST_SHRS', '0')),
                    'listing_date': item.get('LIST_DD'),
                    'data_source': 'KRX Data API',
                })

            logger.info(f"✅ KRX Data API: {len(etfs)}개 ETF 조회")
            return etfs

        except Exception as e:
            logger.error(f"❌ KRX ETF API failed: {e}")
            raise

    def get_market_cap_data(self, market: str = 'ALL') -> List[Dict]:
        """
        시가총액 데이터 조회 (종목별 시가총액, 종가)

        Args:
            market: 'ALL', 'KOSPI', 'KOSDAQ'

        Returns:
            List of market cap dictionaries

        Endpoint: MDCSTAT01501 (전종목시세)
        """
        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01501',
            'locale': 'ko_KR',
            'mktId': market,
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'csvxls_isNo': 'false',
        }

        try:
            response = self.session.post(self.BASE_URL, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()

            market_data = []
            for item in result.get('OutBlock_1', []):
                market_data.append({
                    'ticker': item['ISU_SRT_CD'],
                    'name': item['ISU_ABBRV'],
                    'close_price': self._parse_number(item.get('TDD_CLSPRC', '0')),
                    'market_cap': self._parse_number(item.get('MKTCAP', '0')),  # Already in 원 (KRW)
                    'volume': self._parse_number(item.get('ACC_TRDVOL', '0')),
                    'trading_value': self._parse_number(item.get('ACC_TRDVAL', '0')),  # Already in 원 (KRW)
                })

            logger.info(f"✅ KRX Market Cap API: {len(market_data)}개 종목 시가총액 조회")
            return market_data

        except Exception as e:
            logger.error(f"❌ KRX Market Cap API failed: {e}")
            raise

    def check_connection(self) -> bool:
        """
        API 연결 상태 확인

        Returns:
            True if API is accessible
        """
        try:
            # Simple connection test - fetch KOSPI stock list with 1-second timeout
            data = {
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',
                'locale': 'ko_KR',
                'mktId': 'STK',  # KOSPI only for quick test
                'trdDd': datetime.now().strftime("%Y%m%d"),
                'share': '1',
                'csvxls_isNo': 'false',
            }

            response = self.session.post(self.BASE_URL, data=data, timeout=1)
            response.raise_for_status()
            result = response.json()

            return 'OutBlock_1' in result and len(result['OutBlock_1']) > 0

        except Exception as e:
            logger.warning(f"⚠️ KRX Data API health check failed: {e}")
            return False

    def get_sector_classification(self, market: str = 'ALL') -> Dict[str, Dict]:
        """
        업종 분류 현황 조회 (섹터/업종 코드 포함)

        Args:
            market: 'ALL', 'KOSPI', 'KOSDAQ'

        Returns:
            Dictionary mapping ticker to sector/industry info
            {
                '005930': {
                    'sector': '전기전자',
                    'sector_code': 'G25',
                    'industry': '반도체',
                    'industry_code': 'G2520'
                }
            }

        Endpoint: MDCSTAT03901 (업종분류현황)
        Note: Uses progressive date fallback to handle system date issues
        """
        from datetime import timedelta

        # Try multiple dates going backwards (workaround for future date issues)
        # System date may be incorrect, try far back dates (up to ~300 days)
        for days_back in [0, 1, 2, 3, 7, 14, 30, 60, 90, 180, 280]:
            try_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

            data = {
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT03901',
                'locale': 'ko_KR',
                'mktId': market,
                'trdDd': try_date,
                'csvxls_isNo': 'false',
            }

            try:
                response = self.session.post(self.BASE_URL, data=data, timeout=10)
                response.raise_for_status()
                result = response.json()

                # KRX API may return data in 'OutBlock_1' or 'block1' depending on endpoint version
                data_block = result.get('OutBlock_1', result.get('block1', []))

                sector_map = {}
                for item in data_block:
                    ticker = item.get('ISU_SRT_CD')
                    if not ticker:
                        continue

                    sector_map[ticker] = {
                        'sector': item.get('IDX_IND_NM'),        # 섹터명 (e.g., "전기전자")
                        'sector_code': item.get('IDX_IND_CD'),   # 섹터코드 (e.g., "G25")
                        'industry': item.get('IDX_NM'),          # 업종명 (e.g., "반도체")
                        'industry_code': item.get('IDX_CD'),     # 업종코드 (e.g., "G2520")
                    }

                # If we got data, return it
                if sector_map:
                    logger.info(f"✅ KRX Sector Classification API: {len(sector_map)}개 종목 업종 분류 조회 (date: {try_date})")
                    return sector_map

                # Empty result, try next date
                if days_back < 280:
                    logger.debug(f"⚠️ KRX API returned 0 results for date {try_date}, trying older date...")
                    continue
                else:
                    logger.warning(f"⚠️ KRX API returned 0 results for all attempted dates")
                    return {}

            except Exception as e:
                if days_back < 280:
                    logger.debug(f"⚠️ KRX API failed for date {try_date}: {e}, trying next date...")
                    continue
                else:
                    logger.error(f"❌ KRX Sector Classification API failed for all dates: {e}")
                    raise

        # Should not reach here, but return empty dict as fallback
        return {}

    def _parse_number(self, value: str) -> int:
        """
        숫자 파싱 (콤마 제거)

        Args:
            value: String with commas (e.g., "1,234,567")

        Returns:
            Integer value
        """
        if not value or value == '-':
            return 0
        return int(value.replace(',', ''))
