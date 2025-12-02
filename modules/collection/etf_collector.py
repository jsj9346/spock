"""
ETF Data Collector - ETF 상세 정보 및 구성종목 수집

다중 리전(KR, US, JP, CN, HK, VN) ETF 데이터를 수집하여
etf_details 및 etf_holdings 테이블에 저장합니다.

데이터 소스:
- KR: KIS API (상세정보, 추적오차), KRX API (구성종목)
- US/JP/HK/CN/VN: yfinance (상세정보)

사용 예:
    from modules.collection.etf_collector import ETFCollector

    collector = ETFCollector(db)

    # 단일 ETF 수집
    collector.collect_etf_details('069500', 'KR')

    # 배치 수집
    collector.collect_batch_details(['069500', '114800'], 'KR')

    # KR ETF Holdings 수집
    collector.collect_kr_holdings('069500')

Author: Quant Investment Platform
Date: 2025-11-28
"""

import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.collection.collection_tracker import CollectionTracker, DataType


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ETFDetails:
    """ETF 상세 정보 데이터 클래스"""
    ticker: str
    region: str
    tracking_index: str  # Required field
    expense_ratio: float  # Required field

    # Optional fields
    issuer: Optional[str] = None
    inception_date: Optional[date] = None
    underlying_asset_class: Optional[str] = None
    geographic_region: Optional[str] = None
    sector_theme: Optional[str] = None
    fund_type: Optional[str] = None
    aum: Optional[int] = None  # Assets Under Management
    listed_shares: Optional[int] = None
    underlying_asset_count: Optional[int] = None
    ter: Optional[float] = None  # Total Expense Ratio
    leverage_ratio: Optional[str] = None  # '1x', '2x', '-1x', etc.
    currency_hedged: Optional[bool] = None
    tracking_error_20d: Optional[float] = None
    tracking_error_60d: Optional[float] = None
    tracking_error_120d: Optional[float] = None
    tracking_error_250d: Optional[float] = None
    data_source: str = "unknown"


@dataclass
class ETFHolding:
    """ETF 구성종목 데이터 클래스"""
    etf_ticker: str
    stock_ticker: str
    region: str
    as_of_date: date
    weight: float

    # Optional fields
    shares: Optional[int] = None
    market_value: Optional[float] = None
    rank_in_etf: Optional[int] = None
    weight_change_from_prev: Optional[float] = None
    data_source: str = "unknown"


# =============================================================================
# Currency Mapping
# =============================================================================

CURRENCY_MAP = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "HK": "HKD",
    "CN": "CNY",
    "VN": "VND",
}


# =============================================================================
# ETF Collector Class
# =============================================================================

class ETFCollector:
    """
    ETF 데이터 수집기

    지원 기능:
    - ETF 상세 정보 수집 (etf_details)
    - ETF 구성종목 수집 (etf_holdings) - KR만 지원
    - CollectionTracker 연동으로 중복 수집 방지
    - 배치 수집 지원
    """

    def __init__(
        self,
        db_manager: Optional[PostgresDatabaseManager] = None,
        skip_same_day: bool = True
    ):
        """
        Initialize ETFCollector.

        Args:
            db_manager: PostgresDatabaseManager instance. Creates new if not provided.
            skip_same_day: True면 같은 날 수집된 ETF 스킵 (기본: True)
        """
        self.db = db_manager or PostgresDatabaseManager()
        self.collected_count = 0
        self.error_count = 0
        self.skipped_count = 0

        # CollectionTracker 초기화
        self.tracker = CollectionTracker(self.db, skip_same_day=skip_same_day)

        # API 클라이언트 초기화 (lazy loading)
        self._kis_etf_api = None
        self._krx_etf_api = None
        self._yfinance_api = None

    # =========================================================================
    # Lazy API Client Initialization
    # =========================================================================

    @property
    def kis_etf_api(self):
        """KIS ETF API 클라이언트 (lazy init)"""
        if self._kis_etf_api is None:
            try:
                from modules.api_clients.kis_etf_api import KISEtfAPI
                app_key = os.getenv('KIS_APP_KEY')
                app_secret = os.getenv('KIS_APP_SECRET')
                if app_key and app_secret:
                    self._kis_etf_api = KISEtfAPI(app_key, app_secret)
                    logger.info("KIS ETF API 클라이언트 초기화 완료")
                else:
                    logger.warning("KIS API 키가 설정되지 않음")
            except ImportError as e:
                logger.warning(f"KIS ETF API 모듈 import 실패: {e}")
        return self._kis_etf_api

    @property
    def krx_etf_api(self):
        """KRX ETF API 클라이언트 (lazy init)"""
        if self._krx_etf_api is None:
            try:
                from modules.api_clients.krx_etf_api import KRXEtfAPI
                self._krx_etf_api = KRXEtfAPI()
                logger.info("KRX ETF API 클라이언트 초기화 완료")
            except ImportError as e:
                logger.warning(f"KRX ETF API 모듈 import 실패: {e}")
        return self._krx_etf_api

    @property
    def yfinance_api(self):
        """YFinance API 클라이언트 (lazy init)"""
        if self._yfinance_api is None:
            try:
                from modules.api_clients.yfinance_api import YFinanceAPI
                self._yfinance_api = YFinanceAPI(rate_limit_per_second=1.0)
                logger.info("YFinance API 클라이언트 초기화 완료")
            except ImportError as e:
                logger.warning(f"YFinance API 모듈 import 실패: {e}")
        return self._yfinance_api

    # =========================================================================
    # ETF Details Collection - KR
    # =========================================================================

    def collect_kr_etf_details(self, ticker: str) -> Optional[ETFDetails]:
        """
        KR ETF 상세정보 수집 (KIS API 사용)

        Args:
            ticker: KR ETF ticker (6자리)

        Returns:
            ETFDetails object or None
        """
        if not self.kis_etf_api:
            logger.warning(f"[{ticker}] KIS API 사용 불가 - yfinance로 fallback")
            return self.collect_yfinance_etf_details(ticker, 'KR')

        try:
            # 1. ETF 상세정보 조회
            details = self.kis_etf_api.get_etf_details(ticker)
            if not details:
                logger.warning(f"[{ticker}] KIS API에서 상세정보 조회 실패")
                return self.collect_yfinance_etf_details(ticker, 'KR')

            # 2. 추적오차 조회
            tracking_error = self.kis_etf_api.get_etf_tracking_error(ticker)

            # 3. ETFDetails 객체 생성
            etf_details = ETFDetails(
                ticker=ticker,
                region='KR',
                tracking_index=details.get('tracking_index', 'Unknown'),
                expense_ratio=details.get('expense_ratio', 0.0),
                issuer=details.get('issuer'),
                listed_shares=details.get('listed_shares'),
                tracking_error_20d=tracking_error.get('tracking_error_20d'),
                tracking_error_60d=tracking_error.get('tracking_error_60d'),
                tracking_error_120d=tracking_error.get('tracking_error_120d'),
                tracking_error_250d=tracking_error.get('tracking_error_250d'),
                data_source='kis_api'
            )

            logger.info(f"✅ [{ticker}] KR ETF 상세정보 수집 완료")
            return etf_details

        except Exception as e:
            logger.error(f"❌ [{ticker}] KR ETF 상세정보 수집 실패: {e}")
            return None

    # =========================================================================
    # ETF Details Collection - yfinance (US, JP, HK, CN, VN)
    # =========================================================================

    def _format_yfinance_ticker(self, ticker: str, region: str) -> str:
        """yfinance용 ticker 포맷팅"""
        if region == "US":
            # US preferred stocks/classes: DB uses '/' but yfinance uses '.'
            # e.g., BRK/B → BRK.B, MS/A → MS.A
            return ticker.replace('/', '-') if '/' in ticker else ticker
        elif region == "JP":
            return f"{ticker}.T"
        elif region == "HK":
            # HK tickers need 4-digit padding and .HK suffix
            return f"{ticker.zfill(4)}.HK"
        elif region == "KR":
            return f"{ticker}.KS"
        elif region == "CN":
            # Shanghai: .SS, Shenzhen: .SZ
            if ticker.startswith("6"):
                return f"{ticker}.SS"
            else:
                return f"{ticker}.SZ"
        elif region == "VN":
            return f"{ticker}.VN"
        else:
            return ticker

    def collect_yfinance_etf_details(self, ticker: str, region: str) -> Optional[ETFDetails]:
        """
        yfinance를 사용하여 ETF 상세정보 수집

        Args:
            ticker: ETF ticker
            region: Region code (US, JP, HK, CN, VN)

        Returns:
            ETFDetails object or None
        """
        try:
            import yfinance as yf

            yf_ticker = self._format_yfinance_ticker(ticker, region)
            stock = yf.Ticker(yf_ticker)
            info = stock.info

            if not info or 'symbol' not in info:
                logger.warning(f"[{ticker}] yfinance에서 정보 조회 실패")
                return None

            # Check if it's actually an ETF
            quote_type = info.get('quoteType', '')
            if quote_type != 'ETF':
                logger.debug(f"[{ticker}] ETF가 아님 (quoteType: {quote_type})")
                # Continue anyway, some ETFs may be misclassified

            # Parse inception date
            inception_date = None
            inception_ts = info.get('fundInceptionDate')
            if inception_ts:
                try:
                    inception_date = datetime.fromtimestamp(inception_ts).date()
                except (ValueError, OSError):
                    pass

            # Create ETFDetails object
            etf_details = ETFDetails(
                ticker=ticker,
                region=region,
                tracking_index=info.get('category', 'Unknown'),  # yfinance uses 'category'
                expense_ratio=info.get('annualReportExpenseRatio', 0.0) or 0.0,
                issuer=info.get('fundFamily'),
                inception_date=inception_date,
                aum=info.get('totalAssets'),
                fund_type=quote_type,
                sector_theme=info.get('category'),
                data_source='yfinance'
            )

            logger.info(f"✅ [{ticker}] {region} ETF 상세정보 수집 완료 (yfinance)")
            return etf_details

        except ImportError:
            logger.error("yfinance 설치 필요: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"❌ [{ticker}] yfinance ETF 상세정보 수집 실패: {e}")
            return None

    # =========================================================================
    # ETF Details Collection - Generic
    # =========================================================================

    def collect_etf_details(self, ticker: str, region: str) -> Optional[ETFDetails]:
        """
        ETF 상세정보 수집 (리전별 적절한 API 선택)

        Args:
            ticker: ETF ticker
            region: Region code

        Returns:
            ETFDetails object or None
        """
        if region == 'KR':
            return self.collect_kr_etf_details(ticker)
        else:
            return self.collect_yfinance_etf_details(ticker, region)

    # =========================================================================
    # ETF Holdings Collection - KR
    # =========================================================================

    def collect_kr_holdings(
        self,
        ticker: str,
        as_of_date: Optional[str] = None
    ) -> List[ETFHolding]:
        """
        KR ETF 구성종목 수집 (KRX API 사용)

        Args:
            ticker: KR ETF ticker (6자리)
            as_of_date: 조회 기준일 (YYYYMMDD, None이면 오늘)

        Returns:
            List of ETFHolding objects
        """
        holdings = []

        if not self.krx_etf_api:
            logger.error(f"[{ticker}] KRX API 사용 불가")
            return holdings

        try:
            # KRX API 호출
            raw_holdings = self.krx_etf_api.get_etf_holdings(ticker, as_of_date)

            if not raw_holdings:
                logger.warning(f"[{ticker}] KRX API에서 구성종목 조회 실패")
                return holdings

            # 기준일 파싱
            if as_of_date:
                parsed_date = datetime.strptime(as_of_date, "%Y%m%d").date()
            else:
                parsed_date = date.today()

            # ETFHolding 객체 생성
            for item in raw_holdings:
                holding = ETFHolding(
                    etf_ticker=ticker,
                    stock_ticker=item.get('stock_ticker', ''),
                    region='KR',
                    as_of_date=parsed_date,
                    weight=item.get('weight', 0.0),
                    shares=item.get('shares'),
                    market_value=item.get('market_value'),
                    rank_in_etf=item.get('rank_in_etf'),
                    data_source='krx_api'
                )
                holdings.append(holding)

            logger.info(f"✅ [{ticker}] KR ETF 구성종목 {len(holdings)}개 수집 완료")

        except Exception as e:
            logger.error(f"❌ [{ticker}] KR ETF 구성종목 수집 실패: {e}")

        return holdings

    # =========================================================================
    # Database Save Methods
    # =========================================================================

    def save_etf_details(self, details: ETFDetails) -> bool:
        """
        ETF 상세정보를 데이터베이스에 저장

        Args:
            details: ETFDetails object

        Returns:
            True if successful, False otherwise
        """
        query = """
        INSERT INTO etf_details (
            ticker, region, issuer, inception_date,
            underlying_asset_class, tracking_index, geographic_region,
            sector_theme, fund_type, aum, listed_shares,
            underlying_asset_count, expense_ratio, ter,
            leverage_ratio, currency_hedged,
            tracking_error_20d, tracking_error_60d,
            tracking_error_120d, tracking_error_250d,
            last_updated
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            NOW()
        )
        ON CONFLICT (ticker, region)
        DO UPDATE SET
            issuer = COALESCE(EXCLUDED.issuer, etf_details.issuer),
            inception_date = COALESCE(EXCLUDED.inception_date, etf_details.inception_date),
            underlying_asset_class = COALESCE(EXCLUDED.underlying_asset_class, etf_details.underlying_asset_class),
            tracking_index = EXCLUDED.tracking_index,
            geographic_region = COALESCE(EXCLUDED.geographic_region, etf_details.geographic_region),
            sector_theme = COALESCE(EXCLUDED.sector_theme, etf_details.sector_theme),
            fund_type = COALESCE(EXCLUDED.fund_type, etf_details.fund_type),
            aum = COALESCE(EXCLUDED.aum, etf_details.aum),
            listed_shares = COALESCE(EXCLUDED.listed_shares, etf_details.listed_shares),
            underlying_asset_count = COALESCE(EXCLUDED.underlying_asset_count, etf_details.underlying_asset_count),
            expense_ratio = EXCLUDED.expense_ratio,
            ter = COALESCE(EXCLUDED.ter, etf_details.ter),
            leverage_ratio = COALESCE(EXCLUDED.leverage_ratio, etf_details.leverage_ratio),
            currency_hedged = COALESCE(EXCLUDED.currency_hedged, etf_details.currency_hedged),
            tracking_error_20d = COALESCE(EXCLUDED.tracking_error_20d, etf_details.tracking_error_20d),
            tracking_error_60d = COALESCE(EXCLUDED.tracking_error_60d, etf_details.tracking_error_60d),
            tracking_error_120d = COALESCE(EXCLUDED.tracking_error_120d, etf_details.tracking_error_120d),
            tracking_error_250d = COALESCE(EXCLUDED.tracking_error_250d, etf_details.tracking_error_250d),
            last_updated = NOW();
        """

        try:
            success = self.db.execute_update(query, (
                details.ticker,
                details.region,
                details.issuer,
                details.inception_date,
                details.underlying_asset_class,
                details.tracking_index,
                details.geographic_region,
                details.sector_theme,
                details.fund_type,
                details.aum,
                details.listed_shares,
                details.underlying_asset_count,
                details.expense_ratio,
                details.ter,
                details.leverage_ratio,
                details.currency_hedged,
                details.tracking_error_20d,
                details.tracking_error_60d,
                details.tracking_error_120d,
                details.tracking_error_250d,
            ))
            return success
        except Exception as e:
            logger.error(f"[{details.ticker}] ETF 상세정보 저장 실패: {e}")
            return False

    def save_etf_holding(self, holding: ETFHolding) -> bool:
        """
        ETF 구성종목을 데이터베이스에 저장

        Args:
            holding: ETFHolding object

        Returns:
            True if successful, False otherwise
        """
        query = """
        INSERT INTO etf_holdings (
            etf_ticker, stock_ticker, region, weight,
            as_of_date, shares, market_value, rank_in_etf,
            weight_change_from_prev, data_source
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (etf_ticker, stock_ticker, region, as_of_date)
        DO UPDATE SET
            weight = EXCLUDED.weight,
            shares = COALESCE(EXCLUDED.shares, etf_holdings.shares),
            market_value = COALESCE(EXCLUDED.market_value, etf_holdings.market_value),
            rank_in_etf = COALESCE(EXCLUDED.rank_in_etf, etf_holdings.rank_in_etf),
            weight_change_from_prev = COALESCE(EXCLUDED.weight_change_from_prev, etf_holdings.weight_change_from_prev),
            data_source = EXCLUDED.data_source;
        """

        try:
            success = self.db.execute_update(query, (
                holding.etf_ticker,
                holding.stock_ticker,
                holding.region,
                holding.weight,
                holding.as_of_date,
                holding.shares,
                holding.market_value,
                holding.rank_in_etf,
                holding.weight_change_from_prev,
                holding.data_source,
            ))
            return success
        except Exception as e:
            logger.error(f"[{holding.etf_ticker}] ETF 구성종목 저장 실패: {e}")
            return False

    def save_etf_holdings(self, holdings: List[ETFHolding]) -> int:
        """
        다수의 ETF 구성종목을 데이터베이스에 저장

        Args:
            holdings: List of ETFHolding objects

        Returns:
            Number of successfully saved holdings
        """
        saved = 0
        for holding in holdings:
            if self.save_etf_holding(holding):
                saved += 1
        return saved

    # =========================================================================
    # Batch Collection Methods
    # =========================================================================

    def collect_and_save_details(
        self,
        ticker: str,
        region: str
    ) -> bool:
        """
        단일 ETF 상세정보 수집 및 저장

        Args:
            ticker: ETF ticker
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()

        details = self.collect_etf_details(ticker, region)
        if details:
            success = self.save_etf_details(details)
            duration_ms = int((time.time() - start_time) * 1000)

            # CollectionTracker에 기록
            self.tracker.mark_collected(
                ticker=ticker,
                region=region,
                data_type=DataType.ETF_DETAILS,
                status='success' if success else 'failed',
                records_count=1 if success else 0,
                duration_ms=duration_ms
            )

            if success:
                self.collected_count += 1
                return True

        self.error_count += 1
        return False

    def collect_and_save_holdings(
        self,
        ticker: str,
        region: str = 'KR',
        as_of_date: Optional[str] = None
    ) -> int:
        """
        단일 ETF 구성종목 수집 및 저장 (KR만 지원)

        Args:
            ticker: ETF ticker
            region: Region code (현재 KR만 지원)
            as_of_date: 조회 기준일 (YYYYMMDD)

        Returns:
            Number of holdings saved
        """
        if region != 'KR':
            logger.warning(f"[{ticker}] {region} 리전의 Holdings 수집은 현재 지원되지 않음")
            return 0

        start_time = time.time()

        holdings = self.collect_kr_holdings(ticker, as_of_date)
        saved = self.save_etf_holdings(holdings)
        duration_ms = int((time.time() - start_time) * 1000)

        # CollectionTracker에 기록
        self.tracker.mark_collected(
            ticker=ticker,
            region=region,
            data_type=DataType.ETF_HOLDINGS,
            status='success' if saved > 0 else 'failed',
            records_count=saved,
            duration_ms=duration_ms
        )

        return saved

    def collect_batch_details(
        self,
        tickers: List[str],
        region: str,
        force: bool = False
    ) -> Dict[str, int]:
        """
        다수의 ETF 상세정보 배치 수집

        Args:
            tickers: List of ETF tickers
            region: Region code
            force: True면 이미 수집된 ticker도 재수집

        Returns:
            Dictionary with collection results
        """
        results = {
            'total': len(tickers),
            'collected': 0,
            'skipped': 0,
            'failed': 0
        }

        # 중복 체크
        if force:
            to_process = tickers
            to_skip = []
        else:
            to_process, to_skip = self.tracker.should_skip_batch(
                tickers=tickers,
                region=region,
                data_type=DataType.ETF_DETAILS
            )

        results['skipped'] = len(to_skip)
        self.skipped_count += len(to_skip)

        if to_skip:
            logger.info(f"[{region}] {len(to_skip)}개 ETF 스킵 (오늘 이미 수집됨)")

        # 수집 진행
        for i, ticker in enumerate(to_process, 1):
            logger.info(f"[{region}] ETF 상세정보 수집 중 ({i}/{len(to_process)}): {ticker}")

            if self.collect_and_save_details(ticker, region):
                results['collected'] += 1
            else:
                results['failed'] += 1

            # Rate limiting (API 보호)
            time.sleep(0.5)

        logger.info(
            f"[{region}] ETF 상세정보 배치 수집 완료: "
            f"수집={results['collected']}, 스킵={results['skipped']}, 실패={results['failed']}"
        )

        return results

    def collect_batch_holdings(
        self,
        tickers: List[str],
        region: str = 'KR',
        as_of_date: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, int]:
        """
        다수의 ETF 구성종목 배치 수집 (KR만 지원)

        Args:
            tickers: List of ETF tickers
            region: Region code (현재 KR만 지원)
            as_of_date: 조회 기준일
            force: True면 이미 수집된 ticker도 재수집

        Returns:
            Dictionary with collection results
        """
        if region != 'KR':
            logger.warning(f"{region} 리전의 Holdings 배치 수집은 현재 지원되지 않음")
            return {'total': len(tickers), 'collected': 0, 'skipped': 0, 'failed': len(tickers)}

        results = {
            'total': len(tickers),
            'collected': 0,
            'skipped': 0,
            'failed': 0,
            'total_holdings': 0
        }

        # 중복 체크
        if force:
            to_process = tickers
            to_skip = []
        else:
            to_process, to_skip = self.tracker.should_skip_batch(
                tickers=tickers,
                region=region,
                data_type=DataType.ETF_HOLDINGS
            )

        results['skipped'] = len(to_skip)

        if to_skip:
            logger.info(f"[{region}] {len(to_skip)}개 ETF Holdings 스킵 (오늘 이미 수집됨)")

        # 수집 진행
        for i, ticker in enumerate(to_process, 1):
            logger.info(f"[{region}] ETF 구성종목 수집 중 ({i}/{len(to_process)}): {ticker}")

            saved = self.collect_and_save_holdings(ticker, region, as_of_date)
            if saved > 0:
                results['collected'] += 1
                results['total_holdings'] += saved
            else:
                results['failed'] += 1

            # Rate limiting
            time.sleep(1.0)  # KRX API는 좀 더 보수적으로

        logger.info(
            f"[{region}] ETF 구성종목 배치 수집 완료: "
            f"ETF={results['collected']}, 구성종목={results['total_holdings']}, "
            f"스킵={results['skipped']}, 실패={results['failed']}"
        )

        return results

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_etf_tickers_from_db(self, region: str) -> List[str]:
        """
        데이터베이스에서 해당 리전의 ETF ticker 목록 조회

        Args:
            region: Region code

        Returns:
            List of ETF tickers
        """
        query = """
        SELECT ticker FROM tickers
        WHERE region = %s AND asset_type = 'ETF' AND is_active = TRUE
        ORDER BY ticker
        """
        try:
            result = self.db.execute_query(query, (region,))
            return [row['ticker'] for row in (result or [])]
        except Exception as e:
            logger.error(f"ETF ticker 목록 조회 실패: {e}")
            return []

    def get_collection_summary(self) -> Dict[str, int]:
        """수집 결과 요약"""
        return {
            'collected': self.collected_count,
            'skipped': self.skipped_count,
            'errors': self.error_count
        }

    def reset_counts(self):
        """수집 카운터 초기화"""
        self.collected_count = 0
        self.skipped_count = 0
        self.error_count = 0


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ETF Data Collector")
    parser.add_argument('--region', type=str, default='KR', help='Region code (KR, US, JP, HK, CN, VN)')
    parser.add_argument('--ticker', type=str, help='Single ETF ticker to collect')
    parser.add_argument('--type', type=str, choices=['details', 'holdings', 'both'], default='details',
                        help='Type of data to collect')
    parser.add_argument('--force', action='store_true', help='Force re-collection')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of ETFs for batch')

    args = parser.parse_args()

    # 환경 변수 로드
    from dotenv import load_dotenv
    load_dotenv()

    # Collector 초기화
    collector = ETFCollector()

    if args.ticker:
        # 단일 ETF 수집
        if args.type in ['details', 'both']:
            logger.info(f"Collecting ETF details for {args.ticker} ({args.region})")
            collector.collect_and_save_details(args.ticker, args.region)

        if args.type in ['holdings', 'both'] and args.region == 'KR':
            logger.info(f"Collecting ETF holdings for {args.ticker}")
            collector.collect_and_save_holdings(args.ticker, args.region)
    else:
        # 배치 수집
        tickers = collector.get_etf_tickers_from_db(args.region)
        if not tickers:
            logger.warning(f"No ETF tickers found for region {args.region}")
        else:
            tickers = tickers[:args.limit]
            logger.info(f"Batch collecting {len(tickers)} ETFs for region {args.region}")

            if args.type in ['details', 'both']:
                collector.collect_batch_details(tickers, args.region, force=args.force)

            if args.type in ['holdings', 'both'] and args.region == 'KR':
                collector.collect_batch_holdings(tickers, args.region, force=args.force)

    # 결과 출력
    summary = collector.get_collection_summary()
    print(f"\n{'='*50}")
    print(f"  ETF Collection Summary")
    print(f"{'='*50}")
    print(f"  Collected: {summary['collected']}")
    print(f"  Skipped:   {summary['skipped']}")
    print(f"  Errors:    {summary['errors']}")
    print(f"{'='*50}\n")
