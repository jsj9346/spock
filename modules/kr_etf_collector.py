"""
Korean ETF Data Collector (Hybrid Strategy)

하이브리드 ETF 데이터 수집 전략:
- Primary: KIS API (실시간성, 기존 인프라)
- Fallback: KRX API (공식 공시 데이터, 신뢰성)

Workflow:
1. ETF 목록 스캔 (KIS or KRX)
2. ETF 구성종목 수집:
   - Step 1: KIS API 시도
   - Step 2: 실패 시 KRX API fallback
   - Step 3: 데이터 병합 및 저장

Author: Spock Trading System
Date: 2025-10-17
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from .etf_data_collector import ETFDataCollector
from .api_clients.kis_etf_api import KISEtfAPI
from .api_clients.krx_etf_api import KRXEtfAPI

logger = logging.getLogger(__name__)


class KoreanETFCollector(ETFDataCollector):
    """
    한국 ETF 데이터 수집기 (하이브리드 전략)

    Features:
    - KIS API (primary): 실시간성, 기존 인프라 활용
    - KRX API (fallback): 공식 공시 데이터, 신뢰성
    - Automatic fallback on KIS API failure
    - Data validation and quality checks
    """

    def __init__(self, db_manager, app_key: str, app_secret: str):
        """
        Initialize Korean ETF collector with hybrid strategy

        Args:
            db_manager: SQLiteDatabaseManager instance
            app_key: KIS API App Key
            app_secret: KIS API App Secret
        """
        super().__init__(db_manager, region_code='KR')

        # Initialize API clients
        self.kis_api = KISEtfAPI(app_key=app_key, app_secret=app_secret)
        self.krx_api = KRXEtfAPI()

        # Statistics
        self.stats = {
            'kis_success': 0,
            'krx_fallback': 0,
            'total_failed': 0,
        }

    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan Korean ETFs (KRX 공식 데이터 우선)

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from KRX API (공식 데이터)
        3. Enrich with KIS API data
        4. Save to database

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ETF dictionaries
        """
        # Step 1: Check cache
        if not force_refresh:
            cached_etfs = self._load_etfs_from_cache(ttl_hours=24)
            if cached_etfs:
                logger.info(f"✅ [KR] Cache에서 {len(cached_etfs)}개 ETF 로드")
                return cached_etfs

        # Step 2: Fetch from KRX (공식 데이터가 더 신뢰성 높음)
        logger.info("📡 [KR] KRX API로 ETF 목록 스캔 중...")

        try:
            etfs_krx = self.krx_api.get_etf_list()

            if not etfs_krx:
                logger.warning("⚠️ [KR] KRX API에서 ETF 목록 조회 실패")
                return []

            # Step 3: Enrich with KIS API details (optional)
            logger.info(f"✅ [KR] KRX에서 {len(etfs_krx)}개 ETF 발견")

            # Save to database
            for etf in etfs_krx:
                etf_data = {
                    'ticker': etf['ticker'],
                    'name': etf['name'],
                    'region': 'KR',
                    'category': 'Equity',  # KRX API에서는 카테고리 제공 안 함
                    'total_assets': etf.get('total_assets'),
                    'shares_outstanding': etf.get('listed_shares'),
                    'data_source': 'KRX',
                }

                self._save_etf_to_db(etf_data)

            logger.info(f"💾 [KR] {len(etfs_krx)}개 ETF 정보 저장 완료")
            return etfs_krx

        except Exception as e:
            logger.error(f"❌ [KR] ETF 스캔 실패: {e}")
            return []

    def collect_etf_holdings(
        self,
        etf_tickers: Optional[List[str]] = None,
        as_of_date: str = None
    ) -> int:
        """
        ETF 구성종목 수집 (하이브리드 전략)

        Workflow:
        1. Get ETF list (from DB if not provided)
        2. For each ETF:
           - Try KIS API (primary)
           - If failed, try KRX API (fallback)
           - Validate and save holdings
        3. Return success count

        Args:
            etf_tickers: List of ETF ticker codes (None = all ETFs in DB)
            as_of_date: Date (YYYY-MM-DD). If None, uses today.

        Returns:
            Number of ETFs successfully updated
        """
        # Step 1: Get ETF list
        if etf_tickers is None:
            etf_tickers = self.db.get_etf_tickers(region='KR')

        if not etf_tickers:
            logger.warning("⚠️ [KR] 수집할 ETF가 없습니다")
            return 0

        # Prepare as_of_date
        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y-%m-%d")

        as_of_date_krx = as_of_date.replace('-', '')  # YYYYMMDD for KRX

        logger.info(f"📡 [KR] {len(etf_tickers)}개 ETF 구성종목 수집 시작 (기준일: {as_of_date})")

        success_count = 0

        for ticker in etf_tickers:
            try:
                holdings = self._collect_single_etf_holdings(
                    ticker=ticker,
                    as_of_date=as_of_date,
                    as_of_date_krx=as_of_date_krx
                )

                if holdings:
                    # Save to database
                    inserted = self._save_holdings_bulk(holdings)

                    if inserted > 0:
                        success_count += 1
                        logger.info(f"✅ [{ticker}] {inserted}개 구성종목 저장 완료")
                    else:
                        logger.warning(f"⚠️ [{ticker}] 구성종목 저장 실패")

                else:
                    logger.warning(f"⚠️ [{ticker}] 구성종목 조회 실패 (KIS + KRX 모두 실패)")
                    self.stats['total_failed'] += 1

            except Exception as e:
                logger.error(f"❌ [{ticker}] ETF 구성종목 수집 중 오류: {e}")
                self.stats['total_failed'] += 1

        # Print statistics
        logger.info(
            f"📊 [KR] ETF 구성종목 수집 완료\n"
            f"  ✅ 성공: {success_count}/{len(etf_tickers)}\n"
            f"  📡 KIS API: {self.stats['kis_success']}\n"
            f"  🔄 KRX Fallback: {self.stats['krx_fallback']}\n"
            f"  ❌ 실패: {self.stats['total_failed']}"
        )

        return success_count

    def _collect_single_etf_holdings(
        self,
        ticker: str,
        as_of_date: str,
        as_of_date_krx: str
    ) -> List[Dict]:
        """
        단일 ETF 구성종목 수집 (하이브리드 로직)

        Args:
            ticker: ETF ticker code
            as_of_date: Date (YYYY-MM-DD)
            as_of_date_krx: Date (YYYYMMDD) for KRX API

        Returns:
            List of holding dictionaries
        """
        # Step 1: Try KIS API (Primary)
        logger.debug(f"🔍 [{ticker}] KIS API 시도...")

        holdings_kis = self.kis_api.get_etf_holdings(ticker)

        if holdings_kis:
            logger.info(f"✅ [{ticker}] KIS API 성공 ({len(holdings_kis)}개)")
            self.stats['kis_success'] += 1

            # Add required fields
            for holding in holdings_kis:
                holding['etf_ticker'] = ticker
                holding['as_of_date'] = as_of_date
                holding['data_source'] = 'KIS API'

            return holdings_kis

        # Step 2: KIS API failed → Try KRX API (Fallback)
        logger.info(f"🔄 [{ticker}] KIS API 실패 → KRX API fallback...")

        holdings_krx = self.krx_api.get_etf_holdings(ticker, as_of_date=as_of_date_krx)

        if holdings_krx:
            logger.info(f"✅ [{ticker}] KRX API 성공 ({len(holdings_krx)}개)")
            self.stats['krx_fallback'] += 1

            # Add required fields
            for holding in holdings_krx:
                holding['etf_ticker'] = ticker
                holding['as_of_date'] = as_of_date
                holding['data_source'] = 'KRX API'

            return holdings_krx

        # Both failed
        logger.warning(f"❌ [{ticker}] KIS + KRX 모두 실패")
        return []

    def update_etf_metadata(self, etf_tickers: Optional[List[str]] = None) -> int:
        """
        ETF 메타데이터 업데이트 (KIS API 활용)

        Args:
            etf_tickers: List of ETF ticker codes (None = all ETFs)

        Returns:
            Number of ETFs updated
        """
        if etf_tickers is None:
            etf_tickers = self.db.get_etf_tickers(region='KR')

        if not etf_tickers:
            logger.warning("⚠️ [KR] 업데이트할 ETF가 없습니다")
            return 0

        logger.info(f"📡 [KR] {len(etf_tickers)}개 ETF 메타데이터 업데이트 중...")

        update_count = 0

        for ticker in etf_tickers:
            try:
                # Get ETF details from KIS API
                details = self.kis_api.get_etf_details(ticker)

                if not details:
                    logger.debug(f"⚠️ [{ticker}] KIS API에서 상세정보 조회 실패")
                    continue

                # Update etfs table
                etf_data = {
                    'ticker': ticker,
                    'name': details.get('etf_name', ''),
                    'region': 'KR',
                    'issuer': details.get('issuer'),
                    'tracking_index': details.get('tracking_index'),
                    'expense_ratio': details.get('expense_ratio'),
                    'shares_outstanding': details.get('listed_shares'),
                    'data_source': 'KIS API',
                }

                success = self._save_etf_to_db(etf_data)

                if success:
                    update_count += 1

            except Exception as e:
                logger.error(f"❌ [{ticker}] 메타데이터 업데이트 실패: {e}")

        logger.info(f"✅ [KR] {update_count}개 ETF 메타데이터 업데이트 완료")
        return update_count
