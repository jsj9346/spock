"""
EDINET Backfill Executor

EDINET API를 사용하여 JP 시장 재무 데이터를 백필하는 실행기.
BackfillExecutor 추상 클래스를 상속하여 EDINET 특화 로직을 구현합니다.

주요 기능:
- JP 시장 ticker의 재무 데이터 백필
- ticker_fundamentals 테이블에 UPSERT
- 체크포인트 기반 재개 지원
- Rate limiting 및 재시도 로직

사용 예시:
    from modules.backfill.edinet_executor import EDINETBackfillExecutor
    from modules.db_manager_postgres import PostgresDatabaseManager

    db = PostgresDatabaseManager()
    executor = EDINETBackfillExecutor(db, dry_run=False)

    # 사전 조건 검증
    is_ready, issues = executor.validate_prerequisites()
    if is_ready:
        stats = executor.run_backfill(start_year=2020, end_year=2024)
        print(f"성공: {stats.tickers_success}, 실패: {stats.tickers_failed}")

Author: Quant Platform Development Team
Date: 2025-11-26
"""

import os
import logging
from typing import List, Tuple, Optional
from datetime import datetime

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.data_structures import (
    TickerGapInfo,
    BackfillStats,
    GapPriority
)
from modules.api_clients.edinet_api import EDINETApiClient, EDINETFundamentalData
from modules.backfill.jp_ticker_filter import JPTickerFilter, JPTickerFilterResult

logger = logging.getLogger(__name__)


class EDINETBackfillExecutor(BackfillExecutor):
    """
    EDINET 재무 데이터 백필 실행기

    JP 시장 종목의 재무 데이터를 EDINET API에서 가져와
    ticker_fundamentals 테이블에 저장합니다.
    """

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        api_key: Optional[str] = None
    ):
        """
        EDINET Backfill Executor 초기화

        Args:
            db: PostgreSQL 데이터베이스 매니저
            dry_run: True이면 실제 저장 없이 미리보기만 수행
            rate_limit_delay: EDINET API 호출 간 지연 시간 (초)
            max_retries: 실패 시 최대 재시도 횟수
            retry_delay: 재시도 간 지연 시간 (초)
            api_key: EDINET API Key (None이면 환경변수 사용)
        """
        super().__init__(
            db=db,
            dry_run=dry_run,
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        # API Key 설정 (환경변수 우선)
        self.api_key = api_key or os.getenv("EDINET_API_KEY")

        # EDINET API 클라이언트 (지연 초기화)
        self._edinet_api: Optional[EDINETApiClient] = None

        # 스마트 필터링 (신규 IPO, ETF, REIT 등 사전 필터링)
        self._jp_filter: Optional[JPTickerFilter] = None
        self.enable_smart_filter = True  # 스마트 필터링 활성화 여부

        # 백필 설정
        self.start_year = 2020
        self.end_year = 2024
        self.period_type = "ANNUAL"

        # 필터링 통계
        self.filter_stats = {
            'pre_filtered': 0,
            'api_queried': 0,
            'api_unavailable': 0
        }

        logger.info(f"🇯🇵 EDINETBackfillExecutor 초기화 완료 (dry_run={dry_run}, smart_filter={self.enable_smart_filter})")

    @property
    def edinet_api(self) -> EDINETApiClient:
        """EDINET API 클라이언트 (지연 초기화, 캐싱 및 최적화 활성화)"""
        if self._edinet_api is None:
            if not self.api_key:
                raise ValueError(
                    "EDINET_API_KEY가 설정되지 않았습니다. "
                    "https://disclosure2.edinet-fsa.go.jp/ 에서 무료로 발급받으세요."
                )

            self._edinet_api = EDINETApiClient(
                api_key=self.api_key,
                rate_limit_delay=self.rate_limit_delay,
                max_retries=self.max_retries,
                use_cache=True  # 문서 목록 캐싱 활성화 (재조회 시 0 API 호출)
            )
        return self._edinet_api

    @property
    def jp_filter(self) -> JPTickerFilter:
        """JP Ticker 스마트 필터 (지연 초기화)"""
        if self._jp_filter is None:
            self._jp_filter = JPTickerFilter(db=self.db)
        return self._jp_filter

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        실행 전 사전 조건 검증

        Returns:
            (준비 완료 여부, 문제점 목록) 튜플
        """
        issues = []

        # 1. EDINET API Key 확인
        if not self.api_key:
            issues.append(
                "EDINET_API_KEY 환경변수가 설정되지 않았습니다. "
                "https://disclosure2.edinet-fsa.go.jp/ 에서 무료로 발급받으세요."
            )

        # 2. 데이터베이스 연결 확인
        try:
            result = self.db.execute_query("SELECT 1")
            if not result:
                issues.append("데이터베이스 연결 실패")
        except Exception as e:
            issues.append(f"데이터베이스 연결 에러: {e}")

        # 3. EDINET API 연결 확인 (API 키가 있는 경우에만)
        if self.api_key:
            try:
                if not self.edinet_api.validate_connection():
                    issues.append("EDINET API 연결 실패 (API 키 확인 필요)")
            except Exception as e:
                issues.append(f"EDINET API 연결 에러: {e}")

        # 4. JP 리전 ticker 존재 확인
        try:
            count_query = """
            SELECT COUNT(*) as cnt FROM tickers
            WHERE region = 'JP' AND asset_type = 'STOCK' AND is_active = TRUE
            """
            result = self.db.execute_query(count_query)
            if result and result[0]['cnt'] == 0:
                issues.append("JP 리전 활성 ticker가 없음")
        except Exception as e:
            issues.append(f"JP ticker 조회 에러: {e}")

        is_ready = len(issues) == 0
        return (is_ready, issues)

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """
        단일 ticker에 대한 EDINET 데이터 백필

        스마트 필터링이 활성화된 경우, API 호출 전
        신규 IPO, ETF, REIT 등 미지원 종목을 사전 필터링합니다.

        Args:
            ticker_info: 백필할 ticker 정보

        Returns:
            성공 시 True, 실패 시 False
        """
        ticker = ticker_info.ticker

        try:
            # 스마트 필터링 적용 (API 호출 전 사전 검사)
            if self.enable_smart_filter:
                filter_result = self.jp_filter.check_ticker(ticker)

                if filter_result.should_skip:
                    logger.info(f"[{ticker}] 🔍 사전 필터링: {filter_result.description}")
                    self.filter_stats['pre_filtered'] += 1

                    # dry_run이 아니면 DB에 마킹
                    if not self.dry_run:
                        reason = f"[PRE-FILTER] {filter_result.description}"
                        self._mark_ticker_unavailable(ticker, reason[:200])

                    return False  # 필터링된 종목은 False 반환 (실패 아님, 스킵)

            # API 조회 통계 업데이트
            self.filter_stats['api_queried'] += 1

            # EDINET에서 재무 데이터 조회
            fundamentals = self.edinet_api.get_historical_fundamentals(
                ticker=ticker,
                start_year=self.start_year,
                end_year=self.end_year,
                period_type=self.period_type
            )

            if not fundamentals:
                logger.warning(f"[{ticker}] EDINET 데이터 없음 - unavailable로 마킹")
                self._mark_ticker_unavailable(ticker, "EDINET 데이터 없음 (EDINET 코드 미존재 또는 XBRL 데이터 없음)")
                self.filter_stats['api_unavailable'] += 1
                return False

            # 각 연도 데이터 저장
            years_inserted = 0
            for data in fundamentals:
                if self._insert_fundamental_data(data):
                    years_inserted += 1
                    self.stats.records_inserted += 1

            if years_inserted > 0:
                logger.info(f"[{ticker}] {years_inserted}년치 데이터 저장 완료")
                # 성공 시 available로 마킹
                self._mark_ticker_available(ticker)
                return True
            else:
                logger.warning(f"[{ticker}] 저장된 데이터 없음")
                self._mark_ticker_unavailable(ticker, "데이터 파싱 결과 없음")
                self.filter_stats['api_unavailable'] += 1
                return False

        except Exception as e:
            logger.error(f"[{ticker}] 백필 실패: {e}")
            self._mark_ticker_error(ticker, str(e)[:100])
            return False

    def _mark_ticker_unavailable(self, ticker: str, reason: str):
        """
        API 데이터 미제공 ticker를 unavailable로 마킹

        Args:
            ticker: 대상 ticker
            reason: 미제공 사유
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {ticker} unavailable 마킹 스킵")
            return

        try:
            query = """
            UPDATE tickers
            SET fund_status = 'unavailable',
                fund_last_check = NOW(),
                fund_fail_reason = %s,
                fund_fail_count = COALESCE(fund_fail_count, 0) + 1
            WHERE ticker = %s AND region = 'JP'
            """
            self.db.execute_update(query, (reason, ticker))
            logger.debug(f"[{ticker}] unavailable 마킹 완료")
        except Exception as e:
            logger.error(f"[{ticker}] unavailable 마킹 실패: {e}")

    def _mark_ticker_available(self, ticker: str):
        """
        데이터 수집 성공 ticker를 available로 마킹

        Args:
            ticker: 대상 ticker
        """
        if self.dry_run:
            return

        try:
            query = """
            UPDATE tickers
            SET fund_status = 'available',
                fund_last_check = NOW(),
                fund_fail_reason = NULL,
                fund_fail_count = 0
            WHERE ticker = %s AND region = 'JP'
            """
            self.db.execute_update(query, (ticker,))
        except Exception as e:
            logger.error(f"[{ticker}] available 마킹 실패: {e}")

    def _mark_ticker_error(self, ticker: str, error_msg: str):
        """
        API 에러 발생 ticker를 error로 마킹

        Args:
            ticker: 대상 ticker
            error_msg: 에러 메시지
        """
        if self.dry_run:
            return

        try:
            query = """
            UPDATE tickers
            SET fund_status = 'error',
                fund_last_check = NOW(),
                fund_fail_reason = %s,
                fund_fail_count = COALESCE(fund_fail_count, 0) + 1
            WHERE ticker = %s AND region = 'JP'
            """
            self.db.execute_update(query, (error_msg, ticker))
        except Exception as e:
            logger.error(f"[{ticker}] error 마킹 실패: {e}")

    def _insert_fundamental_data(self, data: EDINETFundamentalData) -> bool:
        """
        재무 데이터를 ticker_fundamentals 테이블에 UPSERT

        Args:
            data: EDINET 재무 데이터

        Returns:
            성공 시 True
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {data.ticker} {data.fiscal_year}년 저장 스킵")
            return True

        try:
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year, data_source,
                revenue, gross_profit, operating_profit, net_income, ebitda,
                total_assets, total_liabilities, total_equity,
                current_assets, current_liabilities, inventory, pp_e, accounts_receivable,
                operating_cash_flow, investing_cf, financing_cf, capex, fcf,
                trailing_eps, shares_outstanding,
                capital_stock, retained_earnings,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                revenue = EXCLUDED.revenue,
                gross_profit = EXCLUDED.gross_profit,
                operating_profit = EXCLUDED.operating_profit,
                net_income = EXCLUDED.net_income,
                ebitda = EXCLUDED.ebitda,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                inventory = EXCLUDED.inventory,
                pp_e = EXCLUDED.pp_e,
                accounts_receivable = EXCLUDED.accounts_receivable,
                operating_cash_flow = EXCLUDED.operating_cash_flow,
                investing_cf = EXCLUDED.investing_cf,
                financing_cf = EXCLUDED.financing_cf,
                capex = EXCLUDED.capex,
                fcf = EXCLUDED.fcf,
                trailing_eps = EXCLUDED.trailing_eps,
                shares_outstanding = EXCLUDED.shares_outstanding,
                capital_stock = EXCLUDED.capital_stock,
                retained_earnings = EXCLUDED.retained_earnings,
                data_source = EXCLUDED.data_source,
                last_updated = NOW()
            """

            params = (
                data.ticker, data.region, data.report_date, data.period_type,
                data.fiscal_year, data.data_source,
                data.revenue, data.gross_profit, data.operating_profit,
                data.net_income, data.ebitda,
                data.total_assets, data.total_liabilities, data.total_equity,
                data.current_assets, data.current_liabilities, data.inventory,
                data.pp_e, data.accounts_receivable,
                data.operating_cash_flow, data.investing_cf, data.financing_cf,
                data.capex, data.fcf,
                data.trailing_eps, data.shares_outstanding,
                data.capital_stock, data.retained_earnings
            )

            self.db.execute_update(query, params)
            return True

        except Exception as e:
            logger.error(f"[{data.ticker}] DB 저장 실패: {e}")
            return False

    def get_jp_tickers_for_backfill(
        self,
        limit: Optional[int] = None,
        include_unavailable: bool = False,
        retry_errors: bool = True
    ) -> List[TickerGapInfo]:
        """
        백필 대상 JP ticker 목록 조회

        Args:
            limit: 최대 조회 개수 (None이면 전체)
            include_unavailable: True면 unavailable ticker도 포함 (재시도용)
            retry_errors: True면 error 상태 ticker도 포함

        Returns:
            TickerGapInfo 목록
        """
        # 상태 필터 조건 생성
        status_conditions = ["fund_status IS NULL", "fund_status = 'unknown'"]

        if include_unavailable:
            status_conditions.append("fund_status = 'unavailable'")

        if retry_errors:
            # 에러 발생 후 재시도 (fail_count < 3인 경우만)
            status_conditions.append("(fund_status = 'error' AND COALESCE(fund_fail_count, 0) < 3)")

        status_filter = " OR ".join(status_conditions)

        query = f"""
        SELECT DISTINCT t.ticker, t.name, t.fund_status, t.fund_fail_count
        FROM tickers t
        WHERE t.region = 'JP'
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
          AND ({status_filter})
        ORDER BY t.ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        try:
            rows = self.db.execute_query(query)

            tickers = []
            for row in rows:
                ticker_info = TickerGapInfo(
                    ticker=row['ticker'],
                    name=row.get('name', row['ticker']),
                    region='JP',
                    priority=GapPriority.FULLY_MISSING,
                    missing_count=1,
                    total_count=1
                )
                tickers.append(ticker_info)

            logger.info(f"📋 JP 백필 대상: {len(tickers)}개 ticker")
            return tickers

        except Exception as e:
            logger.error(f"JP ticker 목록 조회 실패: {e}")
            return []

    def run_backfill(
        self,
        start_year: int = 2020,
        end_year: int = 2024,
        limit: Optional[int] = None,
        checkpoint_interval: int = 50,
        resume: bool = False,
        enable_smart_filter: bool = True
    ) -> BackfillStats:
        """
        EDINET 재무 데이터 백필 실행

        Args:
            start_year: 시작 연도
            end_year: 종료 연도
            limit: 최대 ticker 수 (테스트용)
            checkpoint_interval: 체크포인트 저장 간격
            resume: 체크포인트에서 재개 여부
            enable_smart_filter: 스마트 필터링 활성화 여부

        Returns:
            실행 통계
        """
        # 백필 설정 저장
        self.start_year = start_year
        self.end_year = end_year
        self.enable_smart_filter = enable_smart_filter

        # 필터링 통계 초기화
        self.filter_stats = {
            'pre_filtered': 0,
            'api_queried': 0,
            'api_unavailable': 0
        }

        logger.info("=" * 80)
        logger.info("🇯🇵 EDINET 재무 데이터 백필 시작")
        logger.info(f"   기간: {start_year} ~ {end_year}")
        logger.info(f"   모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info(f"   스마트 필터링: {'활성화' if enable_smart_filter else '비활성화'}")
        logger.info("=" * 80)

        # 백필 대상 ticker 조회
        tickers = self.get_jp_tickers_for_backfill(limit=limit)

        if not tickers:
            logger.warning("백필 대상 ticker가 없습니다")
            return self.stats

        # 스마트 필터링 미리보기 (활성화된 경우)
        if enable_smart_filter:
            ticker_codes = [t.ticker for t in tickers]
            filter_preview = self.jp_filter.get_filter_statistics(ticker_codes)
            logger.info(f"🔍 스마트 필터링 미리보기:")
            logger.info(f"   - 총 ticker: {filter_preview['total']:,}개")
            logger.info(f"   - API 조회 예정: {filter_preview['passed']:,}개")
            logger.info(f"   - 사전 필터링: {filter_preview['total'] - filter_preview['passed']:,}개")
            if filter_preview['alpha_suffix_ipo'] > 0:
                logger.info(f"     • 신규 IPO: {filter_preview['alpha_suffix_ipo']}개")
            if filter_preview['etf_or_fund'] > 0:
                logger.info(f"     • ETF/펀드: {filter_preview['etf_or_fund']}개")
            if filter_preview['reit'] > 0:
                logger.info(f"     • J-REIT: {filter_preview['reit']}개")
            if filter_preview['already_unavailable'] > 0:
                logger.info(f"     • 이미 unavailable: {filter_preview['already_unavailable']}개")

        # 배치 실행
        result = self.execute_batch(
            tickers=tickers,
            checkpoint_interval=checkpoint_interval,
            resume=resume
        )

        # 필터링 통계 출력
        logger.info("=" * 80)
        logger.info("📊 필터링 통계:")
        logger.info(f"   사전 필터링: {self.filter_stats['pre_filtered']:,}개 (API 호출 절감)")
        logger.info(f"   API 조회: {self.filter_stats['api_queried']:,}개")
        logger.info(f"   API 미제공: {self.filter_stats['api_unavailable']:,}개")
        if self.filter_stats['api_queried'] > 0:
            success_rate = (self.filter_stats['api_queried'] - self.filter_stats['api_unavailable']) / self.filter_stats['api_queried'] * 100
            logger.info(f"   API 성공률: {success_rate:.1f}%")
        logger.info("=" * 80)

        return result

    def close(self):
        """리소스 정리"""
        if self._edinet_api:
            self._edinet_api.close()
            self._edinet_api = None
        logger.info("🔒 EDINETBackfillExecutor 종료")


# 테스트 코드
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/13ruce/spock')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 80)
    print("EDINET Backfill Executor 테스트")
    print("=" * 80)

    # 데이터베이스 연결
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager
        db = PostgresDatabaseManager()
        print("✅ 데이터베이스 연결 성공")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        exit(1)

    # Executor 초기화 (DRY RUN 모드)
    executor = EDINETBackfillExecutor(
        db=db,
        dry_run=True,  # 테스트는 DRY RUN으로
        rate_limit_delay=1.0
    )

    # 사전 조건 검증
    print("\n1. 사전 조건 검증...")
    is_ready, issues = executor.validate_prerequisites()
    if is_ready:
        print("   ✅ 모든 사전 조건 충족")
    else:
        print("   ❌ 사전 조건 미충족:")
        for issue in issues:
            print(f"      - {issue}")
        exit(1)

    # 백필 대상 조회
    print("\n2. 백필 대상 조회...")
    tickers = executor.get_jp_tickers_for_backfill(limit=5)
    print(f"   대상 ticker: {[t.ticker for t in tickers]}")

    # 백필 실행 (DRY RUN, 3개만)
    print("\n3. 백필 실행 (DRY RUN)...")
    stats = executor.run_backfill(
        start_year=2022,
        end_year=2024,
        limit=3
    )

    print("\n4. 실행 결과:")
    print(f"   처리: {stats.tickers_processed}")
    print(f"   성공: {stats.tickers_success}")
    print(f"   실패: {stats.tickers_failed}")
    print(f"   레코드: {stats.records_inserted}")

    # 정리
    executor.close()

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)
