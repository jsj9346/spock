"""
국내주식 종목 스캐너 (하이브리드 전략)

우선순위:
1. SQLite Cache (24시간 유효) - API 호출 최소화
2. KRX Official API (openapi.krx.co.kr) - 사업자 등록 후 사용
3. KRX Data API (data.krx.co.kr) - API Key 없어도 사용 가능
4. pykrx (rate-limited) - 개인 투자자용 (차단 방지 로직 포함)
5. FinanceDataReader - 최후 수단

Author: Spock Trading System
"""

import os
import sys
import time
import logging
import sqlite3
import requests
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Phase 3: MarketFilterManager Integration
# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.market_filter_manager import MarketFilterManager, FilterResult

# Phase 4: Pipeline Integration
from modules.stock_utils import check_market_hours

# Phase 6: Blacklist Manager Integration
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class KRXOfficialAPI:
    """
    KRX 공식 OPEN API (openapi.krx.co.kr)
    - 사업자 등록 필요
    - API Key 필수
    """

    BASE_URL = "https://openapi.krx.co.kr/openapi"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def get_stock_list(self, market: str = 'ALL') -> List[Dict]:
        """전체 종목 조회"""
        endpoint = f"{self.BASE_URL}/stock/master"

        params = {
            'apikey': self.api_key,
            'market': market
        }

        response = self.session.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        tickers = []
        for item in data.get('result', []):
            tickers.append({
                'ticker': item['short_code'],
                'name': item['stock_name'],
                'market': item['market_id'],
                'market_cap': int(item.get('market_cap', 0)),
            })

        logger.info(f"✅ KRX Official API: {len(tickers)}개 종목 조회")
        return tickers


class KRXDataAPI:
    """
    KRX 정보데이터시스템 API (data.krx.co.kr)
    - API Key 불필요
    - 공개 엔드포인트
    - 2단계 호출: 상장 정보 + 시세 정보
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
        self.last_call_time = None
        self.min_interval = 0.5  # 500ms 간격 (Rate limiting)

    def _rate_limit(self):
        """Rate limiting (500ms 간격)"""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self.last_call_time = time.time()

    def get_stock_list(self, market: str = 'ALL') -> List[Dict]:
        """
        전체 종목 조회 (2단계)

        1단계: 상장 정보 조회 (상장주식수)
        2단계: 시세 정보 조회 (현재가, 거래대금, 시가총액)
        """
        # Step 1: 상장 정보 조회
        logger.info(f"🔄 [Step 1/2] 상장 정보 조회 중...")
        listing_data = self._get_listing_info(market)

        # Step 2: 시세 정보 조회 및 병합
        logger.info(f"🔄 [Step 2/2] 시세 정보 조회 중...")
        tickers = self._merge_market_data(listing_data)

        logger.info(f"✅ KRX Data API: {len(tickers)}개 종목 조회 완료 (시가총액/거래대금 포함)")
        return tickers

    def _get_listing_info(self, market: str) -> List[Dict]:
        """Step 1: 상장 정보 조회 (MDCSTAT01901)"""
        self._rate_limit()

        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01901',
            'locale': 'ko_KR',
            'mktId': market,
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'share': '1',
            'money': '1',
            'csvxls_isNo': 'false',
        }

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
                'listing_date': item.get('LIST_DD'),
                'shares': self._parse_number(item.get('LIST_SHRS', '0')),
            })

        return tickers

    def _merge_market_data(self, listing_data: List[Dict]) -> List[Dict]:
        """Step 2: 시세 정보 조회 및 병합 (MDCSTAT01501)"""
        self._rate_limit()

        # 시세 정보 조회
        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT01501',
            'locale': 'ko_KR',
            'mktId': 'ALL',
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'share': '1',
            'money': '1',
            'csvxls_isNo': 'false',
        }

        response = self.session.post(self.BASE_URL, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()

        # 시세 정보 인덱싱 (ticker → market data)
        market_data_map = {}
        for item in result.get('OutBlock_1', []):
            ticker = item.get('ISU_SRT_CD')
            market_data_map[ticker] = {
                'close_price': self._parse_number(item.get('TDD_CLSPRC', '0')),
                'market_cap': self._parse_number(item.get('MKTCAP', '0')),
                'trading_value': self._parse_number(item.get('ACC_TRDVAL', '0')),
            }

        # 병합
        merged_tickers = []
        missing_count = 0

        for ticker_data in listing_data:
            ticker = ticker_data['ticker']
            market_info = market_data_map.get(ticker)

            if market_info:
                ticker_data.update(market_info)
            else:
                # 시세 정보 없음 (상장폐지/거래정지 가능성)
                ticker_data['close_price'] = 0
                ticker_data['market_cap'] = 0
                ticker_data['trading_value'] = 0
                missing_count += 1
                logger.debug(f"⚠️ {ticker} ({ticker_data['name']}): 시세 정보 없음")

            merged_tickers.append(ticker_data)

        if missing_count > 0:
            logger.warning(f"⚠️ 시세 정보 없는 종목: {missing_count}개 (상장폐지/거래정지 가능성)")

        return merged_tickers

    def _parse_number(self, value: str) -> int:
        """숫자 파싱 (콤마 제거)"""
        if not value or value == '-':
            return 0
        return int(value.replace(',', '')) if value else 0


class PyKRXFallback:
    """
    pykrx 기반 데이터 수집 (개인 투자자용)
    - Rate Limiting 적용 (KRX 차단 방지)
    - 1초 간격 호출
    """

    def __init__(self):
        self.last_call_time = None
        self.min_interval = 1.0  # 1초 간격

    def get_stock_list(self) -> List[Dict]:
        """전체 종목 조회 (rate-limited)"""
        try:
            from pykrx import stock
        except ImportError:
            raise ImportError("pykrx가 설치되지 않음. pip install pykrx>=1.0.51")

        today = datetime.now().strftime("%Y%m%d")

        # KOSPI 조회
        self._rate_limit()
        kospi = stock.get_market_ticker_list(today, market="KOSPI")

        # KOSDAQ 조회
        self._rate_limit()
        kosdaq = stock.get_market_ticker_list(today, market="KOSDAQ")

        # 종목명 조회 (병목 구간 - 각 종목당 API 호출)
        tickers = []
        for ticker in kospi + kosdaq:
            self._rate_limit()
            name = stock.get_market_ticker_name(ticker)
            market = "KOSPI" if ticker in kospi else "KOSDAQ"

            tickers.append({
                'ticker': ticker,
                'name': name,
                'market': market,
                'region': 'KR',
                'currency': 'KRW',
                'is_active': True
            })

        logger.info(f"✅ pykrx: {len(tickers)}개 종목 조회 (소요: {len(tickers)}초)")
        return tickers

    def _rate_limit(self):
        """API 호출 간 1초 지연"""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)

        self.last_call_time = time.time()


class FinanceDataReaderFallback:
    """
    FinanceDataReader 기반 데이터 수집 (최후 수단)
    """

    def get_stock_list(self) -> List[Dict]:
        """전체 종목 조회"""
        try:
            import FinanceDataReader as fdr
            import pandas as pd
        except ImportError:
            raise ImportError("FinanceDataReader가 설치되지 않음. pip install finance-datareader")

        # KOSPI
        kospi = fdr.StockListing('KOSPI')
        kospi['market'] = 'KOSPI'

        # KOSDAQ
        kosdaq = fdr.StockListing('KOSDAQ')
        kosdaq['market'] = 'KOSDAQ'

        # 합치기
        all_tickers = pd.concat([kospi, kosdaq], ignore_index=True)
        all_tickers = all_tickers.rename(columns={
            'Code': 'ticker',
            'Name': 'name',
            'Market': 'market'
        })

        result = all_tickers[['ticker', 'name', 'market']].to_dict('records')

        logger.info(f"✅ FinanceDataReader: {len(result)}개 종목 조회")
        return result


class StockScanner:
    """
    국내주식 종목 스캐너 (하이브리드 전략)

    데이터 소스 우선순위:
    1. SQLite Cache (24시간)
    2. KRX Official API (사업자 등록 후)
    3. KRX Data API (API Key 불필요)
    4. pykrx (개인 투자자용, rate-limited)
    5. FinanceDataReader (최후 수단)
    """

    def __init__(self, db_path: str = 'data/spock_local.db', region: str = 'KR'):
        self.db_path = db_path
        self.region = region
        self.krx_api_key = os.getenv('KRX_API_KEY')  # 환경변수에서 로드

        # Phase 3: MarketFilterManager 초기화
        self.filter_manager = MarketFilterManager(config_dir='config/market_filters')

        # Phase 6: BlacklistManager 초기화
        db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.blacklist_manager = BlacklistManager(db_manager=db_manager)
        logger.info("✅ BlacklistManager initialized for Stock Scanner")

        # 데이터 소스 초기화
        self.sources = self._initialize_sources()

    def _initialize_sources(self) -> List[tuple]:
        """사용 가능한 데이터 소스 초기화"""
        sources = []

        # Layer 1: KRX Official API (API Key 있으면)
        if self.krx_api_key:
            sources.append(('KRX Official API', KRXOfficialAPI(self.krx_api_key)))
            logger.info("✅ KRX Official API 활성화 (사업자 등록)")

        # Layer 2: KRX Data API (항상 시도)
        sources.append(('KRX Data API', KRXDataAPI()))

        # Layer 3: pykrx (fallback)
        sources.append(('pykrx', PyKRXFallback()))

        # Layer 4: FinanceDataReader (최후 수단)
        sources.append(('FinanceDataReader', FinanceDataReaderFallback()))

        return sources

    def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
        """
        전체 종목 스캔 (다층 방어)

        Args:
            force_refresh: 캐시 무시하고 강제 갱신

        Returns:
            [{'ticker': '005930', 'name': '삼성전자', 'market': 'KOSPI', ...}]
        """
        # Layer 0: Cache 확인 (최우선)
        if not force_refresh:
            cached = self._load_from_cache()
            if cached:
                logger.info(f"✅ [Cache] {len(cached)}개 종목 로드 (캐시 사용)")
                return cached

        # Layer 1-4: 순차적으로 시도
        for source_name, source_api in self.sources:
            try:
                logger.info(f"🔄 [{source_name}] 종목 조회 시도...")
                tickers = source_api.get_stock_list()

                if not tickers:
                    logger.warning(f"⚠️ [{source_name}] 데이터 없음, 다음 소스 시도")
                    continue

                # Phase 3: Stage 0 필터링 적용
                filtered = self._apply_spock_filters(tickers)

                # Phase 3: filter_cache_stage0 테이블에 저장
                self._save_to_cache(filtered, source=source_name)

                # filter_execution_log에 실행 로그 기록
                self._log_filter_execution(
                    filter_stage=0,
                    input_count=len(tickers),
                    output_count=len(filtered),
                    execution_time_ms=0,  # TODO: 실제 실행 시간 측정
                    source=source_name
                )

                logger.info(f"✅ [{source_name}] Stage 0 필터링 완료: {len(tickers)} → {len(filtered)}개 종목")
                return filtered

            except Exception as e:
                logger.error(f"❌ [{source_name}] 실패: {e}")
                continue

        # 모든 소스 실패
        raise Exception("❌ 모든 데이터 소스 실패. 네트워크 확인 필요.")

    def _apply_spock_filters(self, tickers: List[Dict]) -> List[Dict]:
        """
        Phase 3: Stage 0 필터링 (MarketFilterManager 사용)
        Phase 6: Blacklist filtering integration
        - Configuration-driven market-specific filtering
        - Currency normalization to KRW
        - Blacklist filtering (DB + file-based)
        - Multi-market support (KR, US, HK, CN, JP, VN)
        """
        logger.info(f"🔍 Stage 0 필터 적용 중... (입력: {len(tickers)}개 종목)")

        # Phase 6: Extract ticker codes for bulk blacklist check
        ticker_codes = [t.get('ticker') for t in tickers if t.get('ticker')]

        # Phase 6: Filter out blacklisted tickers BEFORE applying other filters
        blacklist_filtered = self.blacklist_manager.filter_blacklisted_tickers(ticker_codes, self.region)
        blacklisted_count = len(ticker_codes) - len(blacklist_filtered)

        if blacklisted_count > 0:
            logger.info(f"🚫 Blacklist filter: Removed {blacklisted_count} blacklisted tickers")

        # Create set for fast lookup
        allowed_tickers = set(blacklist_filtered)

        filtered = []
        passed_count = 0
        failed_count = 0
        blacklist_rejected = 0

        for ticker_data in tickers:
            # Phase 6: Skip blacklisted tickers early
            ticker_code = ticker_data.get('ticker')
            if ticker_code not in allowed_tickers:
                blacklist_rejected += 1
                logger.debug(f"🚫 {ticker_code} ({ticker_data.get('name')}): Blacklisted")
                continue
            # MarketFilterManager 입력 포맷 변환
            filter_input = {
                'ticker': ticker_data.get('ticker'),
                'name': ticker_data.get('name', ''),
                'market_cap_local': ticker_data.get('market_cap', 0),
                'trading_value_local': ticker_data.get('trading_value', 0),
                'price_local': ticker_data.get('close_price', 0),
                'shares': ticker_data.get('shares', 0),
                'market': ticker_data.get('market'),
                'listing_date': ticker_data.get('listing_date'),
                'is_active': ticker_data.get('is_active', True),
                'name_eng': ticker_data.get('name_eng'),
            }

            # Stage 0 필터 적용
            result: FilterResult = self.filter_manager.apply_stage0_filter(
                region=self.region,
                ticker_data=filter_input
            )

            if result.passed:
                # 필터 통과 - normalized 데이터 병합
                ticker_data.update(result.normalized_data)
                ticker_data['region'] = self.region
                ticker_data['filter_score'] = 100  # Default pass score
                ticker_data['filter_reason'] = result.reason
                filtered.append(ticker_data)
                passed_count += 1
            else:
                # 필터 실패 - 로그만 기록
                logger.debug(f"❌ {ticker_data.get('ticker')} ({ticker_data.get('name')}): {result.reason}")
                failed_count += 1

        logger.info(f"📊 Stage 0 필터링 완료: {len(tickers)} → {len(filtered)}개 종목")
        logger.info(f"   🚫 Blacklist: {blacklist_rejected}개 제외")
        logger.info(f"   ✅ Market filter: {passed_count}개 통과, {failed_count}개 실패")
        return filtered

    def _load_from_cache(self) -> Optional[List[Dict]]:
        """Phase 3: filter_cache_stage0에서 종목 로드 (TTL 확인)"""
        try:
            if not os.path.exists(self.db_path):
                return None

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # TTL 확인 (1시간 장중, 24시간 장 마감 후)
            from modules.stock_utils import check_market_hours
            is_market_hours = check_market_hours()
            ttl_hours = 1 if is_market_hours else 24

            # 최근 업데이트 확인
            cursor.execute("""
                SELECT MAX(created_at) as last_update
                FROM filter_cache_stage0
                WHERE region = ?
            """, (self.region,))
            result = cursor.fetchone()

            if not result or not result['last_update']:
                logger.debug(f"캐시 없음 (region={self.region})")
                conn.close()
                return None

            last_update = datetime.fromisoformat(result['last_update'])
            age_hours = (datetime.now() - last_update).total_seconds() / 3600

            if age_hours > ttl_hours:
                logger.info(f"⏰ 캐시 만료 ({age_hours:.1f}시간 경과, TTL={ttl_hours}시간)")
                conn.close()
                return None

            # filter_cache_stage0에서 로드
            cursor.execute("""
                SELECT
                    ticker,
                    name,
                    market,
                    region,
                    currency,
                    market_cap_krw,
                    market_cap_local,
                    trading_value_krw,
                    trading_value_local,
                    current_price_krw,
                    current_price_local,
                    exchange_rate_to_krw,
                    passed_filters,
                    failed_filters,
                    filter_score
                FROM filter_cache_stage0
                WHERE region = ? AND passed_filters = 1
                ORDER BY market_cap_krw DESC
            """, (self.region,))

            tickers = []
            for row in cursor.fetchall():
                ticker_data = {
                    'ticker': row['ticker'],
                    'name': row['name'],
                    'market': row['market'],
                    'region': row['region'],
                    'currency': row['currency'],
                    'market_cap': row['market_cap_local'],
                    'market_cap_krw': row['market_cap_krw'],
                    'trading_value': row['trading_value_local'],
                    'trading_value_krw': row['trading_value_krw'],
                    'close_price': row['current_price_local'],
                    'current_price_krw': row['current_price_krw'],
                    'exchange_rate_to_krw': row['exchange_rate_to_krw'],
                    'filter_score': row['filter_score'],
                    'is_active': True
                }
                tickers.append(ticker_data)

            conn.close()

            logger.info(f"✅ Stage 0 캐시 히트: {age_hours:.1f}시간 전 데이터 ({len(tickers)}개 종목, TTL={ttl_hours}시간)")
            return tickers

        except Exception as e:
            logger.warning(f"캐시 로드 실패: {e}")
            return None

    def _save_to_cache(self, tickers: List[Dict], source: str):
        """Phase 3: filter_cache_stage0 테이블에 저장 (Stage 0 필터 결과 캐싱)"""
        try:
            # DB 디렉토리 생성
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 기존 region 데이터 삭제
            cursor.execute("DELETE FROM filter_cache_stage0 WHERE region = ?", (self.region,))

            # 새 데이터 삽입
            now = datetime.now().isoformat()
            today = datetime.now().strftime("%Y-%m-%d")

            for ticker_data in tickers:
                ticker = ticker_data['ticker']

                # filter_cache_stage0 테이블에 저장
                cursor.execute("""
                    INSERT OR REPLACE INTO filter_cache_stage0 (
                        ticker, region, name, exchange,
                        market_cap_krw, market_cap_local,
                        trading_value_krw, trading_value_local,
                        current_price_krw, current_price_local,
                        currency, exchange_rate_to_krw, exchange_rate_date, exchange_rate_source,
                        filter_date, stage0_passed, filter_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker,
                    self.region,
                    ticker_data.get('name'),
                    ticker_data.get('market', 'UNKNOWN'),  # market → exchange
                    ticker_data.get('market_cap_krw', 0),
                    ticker_data.get('market_cap', 0),
                    ticker_data.get('trading_value_krw', 0),
                    ticker_data.get('trading_value', 0),
                    ticker_data.get('current_price_krw', 0),
                    ticker_data.get('close_price', 0),
                    ticker_data.get('currency', 'KRW'),
                    ticker_data.get('exchange_rate_to_krw', 1.0),
                    today,
                    source,
                    today,  # filter_date
                    True,   # stage0_passed (통과한 종목만 저장)
                    ticker_data.get('filter_reason', '')
                ))

                # tickers 테이블에도 저장 (기존 호환성 유지)
                asset_type = self._classify_asset_type(ticker_data['name'])
                cursor.execute("""
                    INSERT OR REPLACE INTO tickers
                    (ticker, name, name_eng, exchange, region, currency, asset_type,
                     listing_date, is_active, created_at, last_updated, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker,
                    ticker_data['name'],
                    ticker_data.get('name_eng'),
                    ticker_data.get('market', 'UNKNOWN'),
                    self.region,
                    ticker_data.get('currency', 'KRW'),
                    asset_type,
                    ticker_data.get('listing_date'),
                    ticker_data.get('is_active', True),
                    now,
                    now,
                    source
                ))

            conn.commit()
            conn.close()

            logger.info(f"💾 Stage 0 캐시 저장 완료: {len(tickers)}개 종목 (출처: {source})")

        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")

    def _classify_asset_type(self, name: str) -> str:
        """종목명으로 자산 유형 분류"""
        if any(keyword in name for keyword in ['ETF', 'KODEX', 'TIGER', 'KBSTAR', 'ARIRANG']):
            return 'ETF'
        elif 'ETN' in name:
            return 'ETN'
        elif 'REIT' in name or '리츠' in name:
            return 'REIT'
        elif '우' in name:  # 우선주
            return 'PREFERRED'
        else:
            return 'STOCK'

    def _log_filter_execution(self, filter_stage: int, input_count: int, output_count: int, execution_time_ms: int, source: str):
        """filter_execution_log 테이블에 실행 로그 기록"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime("%Y-%m-%d")
            reduction_rate = round((1 - output_count / input_count) * 100, 2) if input_count > 0 else 0
            execution_time_sec = execution_time_ms / 1000.0  # Convert ms to seconds

            cursor.execute("""
                INSERT INTO filter_execution_log (
                    execution_date, stage, region,
                    input_count, output_count, reduction_rate,
                    execution_time_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                today,
                filter_stage,
                self.region,
                input_count,
                output_count,
                reduction_rate,
                execution_time_sec
            ))

            conn.commit()
            conn.close()

            logger.debug(f"📊 필터 실행 로그 기록: Stage {filter_stage}, {input_count} → {output_count} ({reduction_rate}% 감소)")

        except Exception as e:
            logger.warning(f"필터 실행 로그 기록 실패: {e}")

    # ========== Phase 4: Pipeline Orchestration Methods ==========

    def run_full_pipeline(
        self,
        force_refresh: bool = False,
        auto_stage1: bool = False,
        skip_data_collection: bool = False,
        test_sample: int = None
    ) -> Dict[str, any]:
        """
        Execute complete pipeline: Stage 0 → Stage 1 (data collection + pre-filter)

        Args:
            force_refresh: Force Stage 0 cache refresh
            auto_stage1: Automatically execute Stage 1
            skip_data_collection: Skip OHLCV collection (use existing data)
            test_sample: Limit to first N tickers for testing (optional)

        Returns:
            {
                'stage0': {'passed': 600, 'execution_time_ms': 5000, 'source': 'pykrx'},
                'stage1_collection': {'collected': 598, 'execution_time_ms': 120000},
                'stage1_filter': {'passed': 182, 'execution_time_ms': 83},
                'total_execution_time_ms': 125083,
                'pipeline_status': 'success'
            }
        """
        logger.info("🚀 Spock Pipeline Execution Started")
        logger.info("=" * 70)

        pipeline_result = {
            'pipeline_status': 'success',
            'total_execution_time_ms': 0
        }
        start_time = time.time()

        try:
            # Stage 0: Market Scanning
            logger.info("\n[Stage 0: Market Scanning]")
            stage0_result = self._execute_stage0(force_refresh=force_refresh)
            pipeline_result['stage0'] = stage0_result

            # Apply test_sample limit if specified
            if test_sample and test_sample > 0:
                logger.info(f"\n🧪 TEST MODE: Limiting to first {test_sample} tickers")
                # Load tickers from cache
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ticker FROM filter_cache_stage0
                    WHERE region = ? AND stage0_passed = 1
                    ORDER BY filter_date DESC
                    LIMIT ?
                """, (self.region, test_sample))
                limited_tickers = [row[0] for row in cursor.fetchall()]
                conn.close()
                logger.info(f"   Selected tickers: {', '.join(limited_tickers[:10])}{'...' if len(limited_tickers) > 10 else ''}")
                # Store for Stage 1
                self._test_sample_tickers = limited_tickers
            else:
                self._test_sample_tickers = None

            if not auto_stage1:
                logger.info("\n✅ Pipeline complete (Stage 0 only)")
                pipeline_result['total_execution_time_ms'] = int((time.time() - start_time) * 1000)
                return pipeline_result

            # Stage 1: Data Collection
            if not skip_data_collection:
                logger.info("\n[Stage 1: Data Collection]")
                stage1_collection_result = self._execute_stage1_collection(
                    tickers=self._test_sample_tickers if hasattr(self, '_test_sample_tickers') else None
                )
                pipeline_result['stage1_collection'] = stage1_collection_result

                if stage1_collection_result['status'] == 'failed':
                    pipeline_result['pipeline_status'] = 'partial_failure'
                    logger.warning("⚠️  Stage 1 data collection failed, skipping filter")
                    return pipeline_result

            # Stage 1: Technical Pre-Filter
            logger.info("\n[Stage 1: Technical Pre-Filter]")
            stage1_filter_result = self._execute_stage1_filter()
            pipeline_result['stage1_filter'] = stage1_filter_result

            # Final summary
            pipeline_result['total_execution_time_ms'] = int((time.time() - start_time) * 1000)
            logger.info("\n" + "=" * 70)
            logger.info(f"✅ Pipeline execution complete!")
            logger.info(f"Total time: {pipeline_result['total_execution_time_ms'] / 1000:.1f}s")
            if 'stage1_filter' in pipeline_result:
                logger.info(f"Final output: {pipeline_result['stage1_filter']['passed_count']} tickers passed Stage 1")

            return pipeline_result

        except Exception as e:
            logger.error(f"❌ Pipeline execution failed: {e}")
            pipeline_result['pipeline_status'] = 'failed'
            pipeline_result['error'] = str(e)
            pipeline_result['total_execution_time_ms'] = int((time.time() - start_time) * 1000)
            return pipeline_result

    def run_stage2_scoring(
        self,
        tickers: Optional[List[str]] = None,
        min_score: int = 50
    ) -> Dict[str, any]:
        """
        Execute Stage 2: LayeredScoringEngine (100-point scoring system) + Kelly Calculator

        Args:
            tickers: List of tickers to score (if None, load from Stage 1 cache)
            min_score: Minimum score threshold (default: 50)

        Returns:
            {
                'buy_signals': List[Dict],      # score ≥70, with Kelly position sizing
                'watch_list': List[Dict],        # 50 ≤ score < 70
                'avoid_list': List[Dict],        # score < 50
                'scoring_results': List[Dict],   # All detailed results
                'stats': {
                    'total_scored': int,
                    'buy_count': int,
                    'watch_count': int,
                    'avoid_count': int,
                    'avg_score': float,
                    'execution_time_ms': int
                }
            }
        """
        logger.info("=" * 70)
        logger.info("[Stage 2: LayeredScoringEngine + Kelly Position Sizing]")
        logger.info("=" * 70)

        start_time = time.time()

        # Import scoring system and Kelly calculator
        try:
            from modules.integrated_scoring_system import IntegratedScoringSystem
            from modules.stock_kelly_calculator import StockKellyCalculator, RiskLevel
        except ImportError as e:
            logger.error(f"❌ Failed to import required modules: {e}")
            logger.error("ℹ️  Make sure integrated_scoring_system.py and stock_kelly_calculator.py exist in modules/")
            return {
                'status': 'failed',
                'error': 'Required modules not available',
                'buy_signals': [],
                'watch_list': [],
                'avoid_list': []
            }

        # Load tickers from Stage 1 cache if not provided
        if tickers is None:
            logger.info("📊 Loading tickers from Stage 1 cache...")
            tickers = self._load_stage1_tickers()

            if not tickers:
                logger.warning("⚠️  No tickers found in Stage 1 cache")
                return {
                    'status': 'no_input',
                    'buy_signals': [],
                    'watch_list': [],
                    'avoid_list': [],
                    'stats': {'total_scored': 0}
                }

        logger.info(f"📈 Scoring {len(tickers)} tickers...")

        # Initialize scoring system
        scorer = IntegratedScoringSystem(db_path=self.db_path)

        # Initialize Kelly Calculator
        risk_level_map = {
            'conservative': RiskLevel.CONSERVATIVE,
            'moderate': RiskLevel.MODERATE,
            'aggressive': RiskLevel.AGGRESSIVE
        }
        kelly_risk_level = risk_level_map.get(self.risk_level, RiskLevel.MODERATE)
        kelly_calculator = StockKellyCalculator(
            db_path=self.db_path,
            risk_level=kelly_risk_level
        )
        logger.info(f"💰 Kelly Calculator initialized (risk level: {self.risk_level})")

        # Results containers
        results = {
            'buy_signals': [],      # score ≥70, with Kelly position sizing
            'watch_list': [],       # 50 ≤ score < 70
            'avoid_list': [],       # score < 50
            'scoring_results': []
        }

        # Score each ticker
        total_score_sum = 0
        scored_count = 0

        for i, ticker in enumerate(tickers, 1):
            try:
                logger.info(f"  [{i}/{len(tickers)}] Scoring {ticker}...")

                # Analyze ticker asynchronously
                integrated_result = asyncio.run(scorer.analyze_ticker(ticker))

                if integrated_result is None:
                    logger.warning(f"    ⚠️  Scoring failed for {ticker}, skipping")
                    continue

                total_score = integrated_result.total_score
                total_score_sum += total_score
                scored_count += 1

                # Classify by score
                recommendation = integrated_result.recommendation  # BUY, WATCH, or AVOID

                if recommendation == 'BUY':
                    # Calculate Kelly position for BUY signals
                    kelly_result = None
                    kelly_position = 0.0
                    kelly_pattern = 'UNKNOWN'
                    kelly_reasoning = ''

                    try:
                        # Prepare Stage 2 result for Kelly Calculator
                        stage2_for_kelly = {
                            'ticker': ticker,
                            'region': self.region,
                            'total_score': total_score,
                            'details': {
                                'layers': {
                                    'macro': {
                                        'score': integrated_result.macro_score
                                    },
                                    'structural': {
                                        'score': integrated_result.structural_score,
                                        'modules': {}
                                    },
                                    'micro': {
                                        'score': integrated_result.micro_score
                                    }
                                }
                            }
                        }

                        # Calculate Kelly position
                        kelly_result = kelly_calculator.calculate_position_size(stage2_for_kelly)
                        kelly_position = kelly_result.recommended_position_size
                        kelly_pattern = kelly_result.pattern_type.value
                        kelly_reasoning = (
                            f"{kelly_pattern} (win rate: {kelly_result.win_rate*100:.0f}%, "
                            f"quality: {kelly_result.quality_multiplier:.1f}x)"
                        )

                    except Exception as kelly_error:
                        logger.warning(f"    ⚠️  Kelly calculation failed for {ticker}: {kelly_error}")
                        # Continue with default position
                        kelly_position = 5.0  # Default fallback position
                        kelly_pattern = 'DEFAULT'
                        kelly_reasoning = 'Kelly calculation failed, using default position'

                    results['buy_signals'].append({
                        'ticker': ticker,
                        'score': total_score,
                        'recommendation': recommendation,
                        'detected_pattern': integrated_result.details.get('detected_pattern'),
                        'layer1_total': integrated_result.macro_score,
                        'layer2_total': integrated_result.structural_score,
                        'layer3_total': integrated_result.micro_score,
                        'kelly_position': kelly_position,
                        'kelly_pattern': kelly_pattern,
                        'kelly_reasoning': kelly_reasoning
                    })
                    logger.info(f"    🟢 BUY signal: {ticker} (score: {total_score}, Kelly: {kelly_position:.2f}%)")

                elif recommendation == 'WATCH':
                    results['watch_list'].append({
                        'ticker': ticker,
                        'score': total_score,
                        'recommendation': recommendation,
                        'layer1_total': integrated_result.macro_score,
                        'layer2_total': integrated_result.structural_score,
                        'layer3_total': integrated_result.micro_score
                    })
                    logger.info(f"    🟡 WATCH: {ticker} (score: {total_score})")

                else:  # AVOID
                    results['avoid_list'].append({
                        'ticker': ticker,
                        'score': total_score,
                        'recommendation': recommendation
                    })
                    logger.info(f"    🔴 AVOID: {ticker} (score: {total_score})")

                # Store in scoring_results for reference
                results['scoring_results'].append({
                    'ticker': ticker,
                    'total_score': total_score,
                    'recommendation': recommendation,
                    'layer1_total': integrated_result.macro_score,
                    'layer2_total': integrated_result.structural_score,
                    'layer3_total': integrated_result.micro_score,
                    'pattern': integrated_result.details.get('detected_pattern'),
                    'pattern_confidence': integrated_result.details.get('pattern_confidence', 0)
                })

                # Save to database (convert IntegratedFilterResult to dict-like structure)
                score_result_dict = {
                    'total_score': total_score,
                    'macro_score': integrated_result.macro_score,
                    'structural_score': integrated_result.structural_score,
                    'micro_score': integrated_result.micro_score,
                    'market_regime': integrated_result.details.get('market_regime'),
                    'volatility_regime': integrated_result.details.get('volatility_regime'),
                    'detected_pattern': integrated_result.details.get('detected_pattern'),
                    'pattern_confidence': integrated_result.details.get('pattern_confidence', 0)
                }
                self._save_stage2_result(ticker, score_result_dict, recommendation)

            except Exception as e:
                logger.error(f"    ❌ Error scoring {ticker}: {e}")
                continue

        # Sort buy_signals by Kelly position (highest first)
        if results['buy_signals']:
            results['buy_signals'].sort(key=lambda x: x.get('kelly_position', 0), reverse=True)
            logger.info(f"\n💰 BUY signals sorted by Kelly position (highest first)")

        # Calculate statistics
        execution_time_ms = int((time.time() - start_time) * 1000)
        avg_score = total_score_sum / scored_count if scored_count > 0 else 0

        results['stats'] = {
            'total_scored': scored_count,
            'buy_count': len(results['buy_signals']),
            'watch_count': len(results['watch_list']),
            'avoid_count': len(results['avoid_list']),
            'avg_score': round(avg_score, 1),
            'execution_time_ms': execution_time_ms
        }

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("✅ Stage 2 Scoring + Kelly Position Sizing Complete")
        logger.info(f"   Total scored: {scored_count}")
        logger.info(f"   🟢 BUY signals: {results['stats']['buy_count']}")
        logger.info(f"   🟡 WATCH list: {results['stats']['watch_count']}")
        logger.info(f"   🔴 AVOID: {results['stats']['avoid_count']}")
        logger.info(f"   Average score: {avg_score:.1f}/100")
        logger.info(f"   ⏱️  Execution time: {execution_time_ms / 1000:.1f}s")

        # Print top Kelly positions
        if results['buy_signals']:
            logger.info(f"\n   Top Kelly Positions:")
            for i, signal in enumerate(results['buy_signals'][:5], 1):
                logger.info(f"     {i}. {signal['ticker']}: "
                           f"{signal['kelly_position']:.2f}% "
                           f"({signal['kelly_pattern']})")

        logger.info("=" * 70)

        return results

    def _load_stage1_tickers(self) -> List[str]:
        """Load tickers from Stage 1 cache (filter_cache_stage1)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ticker
                FROM filter_cache_stage1
                WHERE region = ?
                AND stage1_passed = 1
                ORDER BY created_at DESC
            """, (self.region,))

            tickers = [row[0] for row in cursor.fetchall()]
            conn.close()

            logger.info(f"✅ Loaded {len(tickers)} tickers from Stage 1 cache")
            return tickers

        except Exception as e:
            logger.error(f"❌ Failed to load Stage 1 tickers: {e}")
            return []

    def _save_stage2_result(self, ticker: str, score_result: Dict, recommendation: str):
        """Save Stage 2 scoring result to filter_cache_stage2"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Extract scores from score_result
            total_score = score_result.get('total_score', 0)

            # Layer scores (from integrated_scoring_system results)
            macro_score = score_result.get('macro_score', 0)
            structural_score = score_result.get('structural_score', 0)
            micro_score = score_result.get('micro_score', 0)

            # Market context
            market_regime = score_result.get('market_regime')
            volatility_regime = score_result.get('volatility_regime')

            # Execution metadata
            execution_time_ms = score_result.get('execution_time_ms', 0)

            # Prepare score_explanations as JSON
            import json
            score_explanations = json.dumps({
                'recommendation': recommendation,
                'detected_pattern': score_result.get('detected_pattern'),
                'pattern_confidence': score_result.get('pattern_confidence', 0),
                'macro_score': macro_score,
                'structural_score': structural_score,
                'micro_score': micro_score
            })

            # Get current timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO filter_cache_stage2 (
                    ticker, region, timestamp, total_score,
                    market_regime_score, volume_profile_score, price_action_score,
                    stage_analysis_score, moving_average_score, relative_strength_score,
                    pattern_recognition_score, volume_spike_score, momentum_score,
                    market_regime, volatility_regime,
                    score_explanations, execution_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, self.region, timestamp, total_score,
                # For now, set individual module scores to 0 (can be enhanced later)
                0, 0, 0,  # market_regime, volume_profile, price_action
                0, 0, 0,  # stage_analysis, moving_average, relative_strength
                0, 0, 0,  # pattern_recognition, volume_spike, momentum
                market_regime, volatility_regime,
                score_explanations, execution_time_ms
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Failed to save Stage 2 result for {ticker}: {e}")

    def _execute_stage0(self, force_refresh: bool = False) -> Dict[str, any]:
        """
        Execute Stage 0: Market scanning with filters

        Returns:
            {
                'passed_count': int,
                'source': str,
                'execution_time_ms': int,
                'cache_hit': bool
            }
        """
        start_time = time.time()
        cache_hit = False

        try:
            # Check cache first
            if not force_refresh:
                cached = self._load_from_cache()
                if cached:
                    cache_hit = True
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(f"✅ [Cache] {len(cached)} tickers loaded (cache hit)")
                    logger.info(f"⏱️  Execution time: {execution_time_ms}ms")

                    return {
                        'passed_count': len(cached),
                        'source': 'cache',
                        'execution_time_ms': execution_time_ms,
                        'cache_hit': True
                    }

            # No cache, scan from sources
            tickers = self.scan_all_tickers(force_refresh=force_refresh)
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(f"✅ Stage 0 complete: {len(tickers)} tickers")
            logger.info(f"⏱️  Execution time: {execution_time_ms / 1000:.1f}s")

            return {
                'passed_count': len(tickers),
                'source': 'api',
                'execution_time_ms': execution_time_ms,
                'cache_hit': False
            }

        except Exception as e:
            logger.error(f"❌ Stage 0 execution failed: {e}")
            raise

    def _execute_stage1_collection(self, tickers: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Execute Stage 1: OHLCV data collection

        Args:
            tickers: Specific tickers (optional, auto-loads from Stage 0 if None)

        Returns:
            {
                'collected_count': int,
                'failed_count': int,
                'execution_time_ms': int,
                'status': 'success' | 'partial' | 'failed'
            }
        """
        start_time = time.time()

        try:
            # Lazy import to avoid circular dependencies
            from modules.kis_data_collector import KISDataCollector

            collector = KISDataCollector(db_path=self.db_path, region=self.region)

            logger.info(f"🔄 Collecting OHLCV data from KIS API...")

            # Run data collection
            collector.collect_data(tickers=tickers, force_full=False)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Get collection stats from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(DISTINCT ticker) as ticker_count
                FROM ohlcv_data
                WHERE region = ? AND timeframe = 'D'
            """, (self.region,))
            result = cursor.fetchone()
            collected_count = result[0] if result else 0
            conn.close()

            logger.info(f"✅ Data collection complete: {collected_count} tickers collected")
            logger.info(f"⏱️  Execution time: {execution_time_ms / 1000:.1f}s")

            return {
                'collected_count': collected_count,
                'failed_count': 0,  # kis_data_collector doesn't track this yet
                'execution_time_ms': execution_time_ms,
                'status': 'success'
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Stage 1 data collection failed: {e}")

            return {
                'collected_count': 0,
                'failed_count': 0,
                'execution_time_ms': execution_time_ms,
                'status': 'failed',
                'error': str(e)
            }

    def _execute_stage1_filter(self) -> Dict[str, any]:
        """
        Execute Stage 1: Technical pre-filter (Weinstein + 4-gate)

        Returns:
            {
                'input_count': int,
                'passed_count': int,
                'execution_time_ms': int,
                'pass_rate': float,
                'status': 'success' | 'failed'
            }
        """
        start_time = time.time()

        try:
            # Lazy import to avoid circular dependencies
            from modules.stock_pre_filter import StockPreFilter

            pre_filter = StockPreFilter(db_path=self.db_path, region=self.region)

            logger.info(f"🔄 Running Weinstein Stage 2 detection + 4-gate filtering...")

            # Run Stage 1 filter
            results = pre_filter.run_stage1_filter()

            execution_time_ms = int((time.time() - start_time) * 1000)

            input_count = len(results) if results else 0
            passed_count = len([r for r in results if r.get('stage1_passed', False)]) if results else 0
            pass_rate = (passed_count / input_count * 100) if input_count > 0 else 0

            logger.info(f"✅ Pre-filter complete: {input_count} → {passed_count} tickers ({pass_rate:.1f}% pass rate)")
            logger.info(f"⏱️  Execution time: {execution_time_ms}ms")

            return {
                'input_count': input_count,
                'passed_count': passed_count,
                'execution_time_ms': execution_time_ms,
                'pass_rate': pass_rate,
                'status': 'success'
            }

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ Stage 1 filter execution failed: {e}")

            return {
                'input_count': 0,
                'passed_count': 0,
                'execution_time_ms': execution_time_ms,
                'pass_rate': 0.0,
                'status': 'failed',
                'error': str(e)
            }

    def get_pipeline_status(self) -> Dict[str, any]:
        """
        Get current pipeline execution status

        Returns:
            {
                'stage0': {'cache_age_hours': 2.5, 'ticker_count': 600, 'status': 'fresh'},
                'stage1_data': {'completeness': 0.95, 'ticker_count': 598, 'status': 'ready'},
                'stage1_filter': {'cache_age_hours': 2.5, 'passed_count': 182, 'status': 'fresh'},
                'pipeline_health': 'healthy'
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            status = {
                'stage0': {},
                'stage1_data': {},
                'stage1_filter': {},
                'pipeline_health': 'unknown'
            }

            # Stage 0 status
            cursor.execute("""
                SELECT
                    COUNT(*) as ticker_count,
                    MAX(created_at) as last_update
                FROM filter_cache_stage0
                WHERE region = ?
            """, (self.region,))
            stage0 = cursor.fetchone()

            if stage0 and stage0['last_update']:
                age_hours = (datetime.now() - datetime.fromisoformat(stage0['last_update'])).total_seconds() / 3600
                status['stage0'] = {
                    'cache_age_hours': round(age_hours, 1),
                    'ticker_count': stage0['ticker_count'],
                    'source': 'cache',
                    'status': 'fresh' if age_hours < 24 else 'stale'
                }

            # Stage 1 OHLCV data status
            cursor.execute("""
                SELECT
                    COUNT(DISTINCT ticker) as ticker_count,
                    MAX(date) as latest_date
                FROM ohlcv_data
                WHERE region = ? AND timeframe = 'D'
            """, (self.region,))
            stage1_data = cursor.fetchone()

            if stage1_data and stage1_data['ticker_count']:
                market_status = check_market_hours()
                latest_market_date = market_status['market_date']
                latest_data_date = datetime.strptime(stage1_data['latest_date'], '%Y-%m-%d').date() if stage1_data['latest_date'] else None

                data_freshness = 'ready' if latest_data_date == latest_market_date else 'stale'

                status['stage1_data'] = {
                    'ticker_count': stage1_data['ticker_count'],
                    'latest_date': stage1_data['latest_date'],
                    'status': data_freshness
                }

            # Stage 1 filter cache status
            cursor.execute("""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN stage1_passed = 1 THEN 1 ELSE 0 END) as passed_count,
                    MAX(created_at) as last_update
                FROM filter_cache_stage1
                WHERE region = ?
            """, (self.region,))
            stage1_filter = cursor.fetchone()

            if stage1_filter and stage1_filter['last_update']:
                age_hours = (datetime.now() - datetime.fromisoformat(stage1_filter['last_update'])).total_seconds() / 3600
                status['stage1_filter'] = {
                    'cache_age_hours': round(age_hours, 1),
                    'passed_count': stage1_filter['passed_count'] or 0,
                    'status': 'fresh' if age_hours < 24 else 'stale'
                }

            conn.close()

            # Overall pipeline health
            stage0_ok = status['stage0'].get('status') == 'fresh'
            stage1_data_ok = status['stage1_data'].get('status') == 'ready'
            stage1_filter_ok = status['stage1_filter'].get('status') == 'fresh'

            if stage0_ok and stage1_data_ok and stage1_filter_ok:
                status['pipeline_health'] = 'healthy'
            elif stage0_ok:
                status['pipeline_health'] = 'partial'
            else:
                status['pipeline_health'] = 'stale'

            return status

        except Exception as e:
            logger.error(f"❌ Pipeline status check failed: {e}")
            return {
                'pipeline_health': 'error',
                'error': str(e)
            }


# CLI 테스트
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Phase 4: Stock Scanner with Pipeline Orchestration')
    parser.add_argument('--force-refresh', action='store_true', help='Force Stage 0 cache refresh')
    parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite database path')
    parser.add_argument('--region', default='KR', choices=['KR', 'US', 'HK', 'CN', 'JP', 'VN'], help='Market region code')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    # Phase 4: Pipeline control arguments
    parser.add_argument('--pipeline', choices=['stage0', 'stage1', 'full'],
                       default='stage0', help='Pipeline execution mode (stage0=scanner only, stage1=scanner+data+filter, full=all stages)')
    parser.add_argument('--auto-stage1', action='store_true',
                       help='Shorthand for --pipeline stage1')
    parser.add_argument('--skip-data-collection', action='store_true',
                       help='Skip OHLCV data collection (use existing data)')
    parser.add_argument('--pipeline-status', action='store_true',
                       help='Show pipeline status and exit')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    scanner = StockScanner(db_path=args.db_path, region=args.region)

    try:
        # Phase 4: Pipeline status check
        if args.pipeline_status:
            status = scanner.get_pipeline_status()
            print("\n📊 Spock Pipeline Status (Region: {})".format(args.region))
            print("=" * 70)

            if 'stage0' in status and status['stage0']:
                stage0 = status['stage0']
                print(f"\n[Stage 0: Market Scanning]")
                print(f"  Status: {'✅ Fresh' if stage0['status'] == 'fresh' else '⚠️  Stale'} (cached {stage0['cache_age_hours']}h ago)")
                print(f"  Tickers: {stage0['ticker_count']}")
                print(f"  Source: {stage0.get('source', 'N/A')}")

            if 'stage1_data' in status and status['stage1_data']:
                stage1_data = status['stage1_data']
                print(f"\n[Stage 1: OHLCV Data]")
                print(f"  Status: {'✅ Ready' if stage1_data['status'] == 'ready' else '⚠️  Stale'}")
                print(f"  Tickers: {stage1_data['ticker_count']}")
                print(f"  Latest Data: {stage1_data.get('latest_date', 'N/A')}")

            if 'stage1_filter' in status and status['stage1_filter']:
                stage1_filter = status['stage1_filter']
                print(f"\n[Stage 1: Technical Filter]")
                print(f"  Status: {'✅ Fresh' if stage1_filter['status'] == 'fresh' else '⚠️  Stale'} (cached {stage1_filter['cache_age_hours']}h ago)")
                print(f"  Passed: {stage1_filter['passed_count']} tickers")

            health = status.get('pipeline_health', 'unknown')
            health_emoji = '🟢' if health == 'healthy' else '🟡' if health == 'partial' else '🔴'
            print(f"\nPipeline Health: {health_emoji} {health.upper()}")
            print("=" * 70)
            sys.exit(0)

        # Phase 4: Pipeline mode routing
        pipeline_mode = args.pipeline
        if args.auto_stage1:
            pipeline_mode = 'stage1'

        if pipeline_mode == 'stage0':
            # Original behavior: Stage 0 only
            tickers = scanner.scan_all_tickers(force_refresh=args.force_refresh)

            print("\n" + "="*70)
            print(f"✅ Stage 0 filtering complete: {len(tickers)} tickers (region={args.region})")
            print("="*70)

            # Top 10 tickers
            print("\n[Top 10 Tickers by Market Cap]")
            for i, ticker in enumerate(tickers[:10], 1):
                market_cap_krw = ticker.get('market_cap_krw', 0)
                market_cap_str = f"{market_cap_krw / 1_000_000_000:.0f}B KRW" if market_cap_krw else 'N/A'
                filter_score = ticker.get('filter_score', 0)
                print(f"{i:2d}. {ticker['ticker']:6s} {ticker['name']:15s} ({ticker['market']:6s}) {market_cap_str:>12s} [Score: {filter_score}]")

            print(f"\n💾 Database: {args.db_path}")
            print(f"📊 Stage 0 Cache: filter_cache_stage0")

        elif pipeline_mode in ['stage1', 'full']:
            # Phase 4: Full pipeline execution
            result = scanner.run_full_pipeline(
                force_refresh=args.force_refresh,
                auto_stage1=True,
                skip_data_collection=args.skip_data_collection
            )

            # Summary output
            print("\n" + "=" * 70)
            print("📊 Pipeline Execution Summary")
            print("=" * 70)

            if 'stage0' in result:
                stage0 = result['stage0']
                print(f"\n[Stage 0] ✅ {stage0['passed_count']} tickers ({stage0['execution_time_ms']/1000:.1f}s)")

            if 'stage1_collection' in result:
                stage1_col = result['stage1_collection']
                print(f"[Stage 1 Collection] ✅ {stage1_col['collected_count']} tickers ({stage1_col['execution_time_ms']/1000:.1f}s)")

            if 'stage1_filter' in result:
                stage1_flt = result['stage1_filter']
                print(f"[Stage 1 Filter] ✅ {stage1_flt['passed_count']} tickers passed ({stage1_flt['execution_time_ms']}ms)")

            print(f"\n💾 Database: {args.db_path}")
            print(f"📊 Final Cache: filter_cache_stage1")

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        sys.exit(1)
