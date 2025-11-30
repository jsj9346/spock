"""
PyKRX API Wrapper

Fallback data source using pykrx library
- Rate-limited to prevent KRX blocking (1 sec interval)
- Used when KRX Data API is unavailable
- Suitable for individual investors

Author: Spock Trading System
"""

import time
import logging
from typing import List, Dict
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def suppress_pykrx_logging():
    """
    pykrx 라이브러리의 로깅 버그를 우회하기 위한 컨텍스트 매니저.

    pykrx의 util.py에서 `logging.info(args, kwargs)` 형태로 잘못된
    로깅 호출을 하여 TypeError가 발생함. 이를 우회하기 위해
    pykrx 호출 시 logging 레벨을 임시로 WARNING으로 올림.
    """
    root_logger = logging.getLogger()
    original_level = root_logger.level
    try:
        root_logger.setLevel(logging.WARNING)
        yield
    finally:
        root_logger.setLevel(original_level)


class PyKRXAPI:
    """
    pykrx 기반 데이터 수집 (개인 투자자용)

    Features:
    - Rate limiting (1초 간격)
    - KOSPI, KOSDAQ ticker lists
    - Fallback for KRX Data API failures
    """

    def __init__(self):
        self.last_call_time = None
        self.min_interval = 1.0  # 1초 간격 (KRX 차단 방지)
        self._check_import()

    def _check_import(self):
        """Check if pykrx is installed"""
        try:
            import pykrx
            self.pykrx_available = True
        except ImportError:
            logger.warning("⚠️ pykrx not installed. Install with: pip install pykrx>=1.0.51")
            self.pykrx_available = False

    def get_stock_list(self) -> List[Dict]:
        """
        전체 종목 조회 (KOSPI + KOSDAQ)

        Returns:
            List of stock dictionaries

        Note: Slow operation due to rate limiting (~1 second per ticker for name lookup)
        """
        if not self.pykrx_available:
            raise ImportError("pykrx가 설치되지 않음. pip install pykrx>=1.0.51")

        from pykrx import stock

        today = datetime.now().strftime("%Y%m%d")

        # KOSPI 조회 (suppress pykrx logging bug)
        self._rate_limit()
        with suppress_pykrx_logging():
            kospi = stock.get_market_ticker_list(today, market="KOSPI")
        logger.info(f"📊 pykrx: {len(kospi)}개 KOSPI 종목")

        # KOSDAQ 조회 (suppress pykrx logging bug)
        self._rate_limit()
        with suppress_pykrx_logging():
            kosdaq = stock.get_market_ticker_list(today, market="KOSDAQ")
        logger.info(f"📊 pykrx: {len(kosdaq)}개 KOSDAQ 종목")

        # 종목명 조회 (병목 구간 - 각 종목당 API 호출)
        tickers = []
        total_count = len(kospi) + len(kosdaq)

        for idx, ticker in enumerate(kospi + kosdaq, 1):
            try:
                self._rate_limit()
                with suppress_pykrx_logging():
                    name = stock.get_market_ticker_name(ticker)
                market = "KOSPI" if ticker in kospi else "KOSDAQ"

                tickers.append({
                    'ticker': ticker,
                    'name': name,
                    'market': market,
                    'region': 'KR',
                    'currency': 'KRW',
                    'is_active': True,
                    'data_source': 'pykrx',
                })

                # Progress logging every 100 tickers
                if idx % 100 == 0:
                    logger.info(f"📊 pykrx: {idx}/{total_count} 종목 조회 중...")

            except Exception as e:
                logger.error(f"❌ [{ticker}] pykrx name lookup failed: {e}")

        elapsed_time = int(total_count * self.min_interval)
        logger.info(f"✅ pykrx: {len(tickers)}개 종목 조회 완료 (소요: ~{elapsed_time}초)")
        return tickers

    def get_ohlcv(self, ticker: str, days: int = 250) -> List[Dict]:
        """
        종목별 OHLCV 데이터 조회

        Args:
            ticker: Stock ticker code
            days: Historical days to fetch

        Returns:
            List of OHLCV dictionaries
        """
        if not self.pykrx_available:
            raise ImportError("pykrx가 설치되지 않음")

        from pykrx import stock
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        try:
            self._rate_limit()
            with suppress_pykrx_logging():
                df = stock.get_market_ohlcv(start_str, end_str, ticker)

            if df is None or df.empty:
                logger.warning(f"⚠️ [{ticker}] No OHLCV data from pykrx")
                return []

            # Convert DataFrame to list of dicts
            df = df.reset_index()
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']

            ohlcv_data = df.to_dict('records')
            logger.info(f"✅ [{ticker}] {len(ohlcv_data)}일 OHLCV 데이터 조회 (pykrx)")
            return ohlcv_data

        except Exception as e:
            logger.error(f"❌ [{ticker}] pykrx OHLCV failed: {e}")
            return []

    def check_connection(self) -> bool:
        """
        pykrx 사용 가능 여부 확인

        Returns:
            True if pykrx is available and working
        """
        if not self.pykrx_available:
            return False

        try:
            from pykrx import stock
            today = datetime.now().strftime("%Y%m%d")

            # Quick test - fetch KOSPI ticker count only
            self._rate_limit()
            with suppress_pykrx_logging():
                kospi = stock.get_market_ticker_list(today, market="KOSPI")

            return len(kospi) > 0

        except Exception as e:
            logger.warning(f"⚠️ pykrx health check failed: {e}")
            return False

    def get_stock_sector_info(self, ticker: str) -> Dict:
        """
        종목의 섹터/업종 정보 조회 (pykrx 활용)

        Args:
            ticker: Stock ticker code (6 digits)

        Returns:
            Dictionary with sector, industry, sector_code, industry_code
            {
                'sector': 'Information Technology',
                'sector_code': 'G25',
                'industry': '반도체',
                'industry_code': 'G2520',
                'par_value': 100
            }

        Note:
        - pykrx doesn't provide GICS sector directly, uses KRX classification
        - Returns KRX sector and maps to GICS using SECTOR_MAP
        - Uses progressive date fallback (tries multiple dates if data unavailable)
        """
        if not self.pykrx_available:
            logger.warning(f"⚠️ [{ticker}] pykrx not available")
            return {}

        try:
            from pykrx import stock
            from datetime import timedelta

            # Get sector classification with progressive date fallback
            self._rate_limit()

            # Try multiple dates going backwards (workaround for future date issues)
            # System date may be incorrect, try far back dates (up to ~300 days)
            sector_info = {}
            successful_date = None

            # Try dates: yesterday, -2d, -3d, -7d, -14d, -30d, -60d, -90d, -180d, -280d (Jan 2025)
            for days_back in [1, 2, 3, 7, 14, 30, 60, 90, 180, 280]:
                try_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

                try:
                    with suppress_pykrx_logging():
                        sector_info = stock.get_market_sector_classifications(ticker, try_date)
                    if sector_info and '섹터' in sector_info:
                        successful_date = try_date
                        break
                except Exception as e:
                    # Continue to next date
                    if days_back == 280:  # Last attempt
                        logger.warning(f"⚠️ [{ticker}] Sector classification unavailable for all dates")
                    continue

            if successful_date:
                logger.debug(f"✅ [{ticker}] Found sector data using date: {successful_date}")

            # Extract sector and industry
            krx_sector = sector_info.get('섹터', None) if sector_info else None
            krx_industry = sector_info.get('업종', None) if sector_info else None

            # Map KRX sector to GICS
            gics_sector = self._map_krx_to_gics(krx_sector) if krx_sector else None

            result = {
                'sector': gics_sector,
                'sector_code': None,  # pykrx doesn't provide codes
                'industry': krx_industry,
                'industry_code': None,  # pykrx doesn't provide codes
                'par_value': None,  # pykrx doesn't provide par_value
            }

            if gics_sector or krx_industry:
                logger.info(f"✅ [{ticker}] Sector: {gics_sector}, Industry: {krx_industry}")
            else:
                logger.warning(f"⚠️ [{ticker}] No sector/industry data available")

            return result

        except Exception as e:
            logger.error(f"❌ [{ticker}] get_stock_sector_info failed: {e}")
            return {}

    def _map_krx_to_gics(self, krx_sector: str) -> str:
        """
        Map KRX sector classification to GICS 11 sectors

        Args:
            krx_sector: KRX sector name (Korean)

        Returns:
            GICS sector name (English)
        """
        # KRX → GICS mapping
        SECTOR_MAP = {
            '에너지화학': 'Energy',
            '에너지': 'Energy',
            '비철금속': 'Materials',
            '철강금속': 'Materials',
            '금속': 'Materials',
            '소재': 'Materials',
            '화학': 'Materials',
            '건설': 'Industrials',
            '기계': 'Industrials',
            '조선운송': 'Industrials',
            '운수장비': 'Industrials',
            '산업재': 'Industrials',
            '섬유의복': 'Consumer Discretionary',
            '종이목재': 'Materials',
            '의약품': 'Health Care',
            '제약': 'Health Care',
            '바이오': 'Health Care',
            '건강관리': 'Health Care',
            '음식료담배': 'Consumer Staples',
            '음식료품': 'Consumer Staples',
            '필수소비재': 'Consumer Staples',
            '서비스업': 'Consumer Discretionary',
            '유통업': 'Consumer Staples',
            '전기전자': 'Information Technology',
            '반도체': 'Information Technology',
            '정보기술': 'Information Technology',
            'IT': 'Information Technology',
            '통신업': 'Communication Services',
            '통신서비스': 'Communication Services',
            '미디어': 'Communication Services',
            '금융업': 'Financials',
            '은행': 'Financials',
            '증권': 'Financials',
            '보험': 'Financials',
            '금융': 'Financials',
            '운수창고': 'Industrials',
            '전기가스': 'Utilities',
            '유틸리티': 'Utilities',
            '전기': 'Utilities',
            '가스': 'Utilities',
            '건설업': 'Real Estate',
            '부동산': 'Real Estate',
        }

        if not krx_sector:
            return None

        # Exact match first
        if krx_sector in SECTOR_MAP:
            return SECTOR_MAP[krx_sector]

        # Partial match (contains)
        for keyword, gics in SECTOR_MAP.items():
            if keyword in krx_sector:
                return gics

        # No match
        logger.warning(f"⚠️ Unknown KRX sector: {krx_sector}")
        return 'Unknown'

    def _rate_limit(self):
        """
        API 호출 간 1초 지연 (KRX 차단 방지)

        KRX는 과도한 요청 시 IP를 차단하므로 반드시 rate limiting 필요
        """
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)

        self.last_call_time = time.time()
