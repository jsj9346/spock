"""
TTM (Trailing Twelve Months) Service

Provides TTM calculation and storage functionality for financial data.
Integrates TTMCalculator with PostgreSQL database for batch processing.

Author: Quant Platform Development Team
Date: 2025-11-28
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from modules.fundamentals.ttm_calculator import TTMCalculator, TTMResult

logger = logging.getLogger(__name__)


class TTMService:
    """
    TTM 계산 및 저장 서비스

    분기별 재무 데이터에서 TTM 지표를 계산하고 ticker_fundamentals_ttm 테이블에 저장합니다.

    Example:
        >>> from modules.db_manager_postgres import PostgresDatabaseManager
        >>> from modules.fundamentals.ttm_service import TTMService
        >>>
        >>> db = PostgresDatabaseManager()
        >>> service = TTMService(db)
        >>>
        >>> # 단일 ticker TTM 계산
        >>> result = service.calculate_and_save_ttm('005930', 'KR')
        >>>
        >>> # 배치 처리
        >>> stats = service.run_ttm_calculation(regions=['KR', 'US'], limit=100)
    """

    def __init__(self, db, dry_run: bool = False):
        """
        Initialize TTM Service

        Args:
            db: PostgresDatabaseManager instance
            dry_run: If True, skip DB writes
        """
        self.db = db
        self.calculator = TTMCalculator()
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped': 0,
            'tickers_failed': 0,
            'records_saved': 0,
        }

    def get_tickers_with_quarterly_data(
        self,
        region: str,
        limit: Optional[int] = None,
        skip_calculated: bool = True
    ) -> List[str]:
        """
        분기 데이터가 있는 ticker 목록 조회

        Args:
            region: 지역 코드 (KR, US, JP 등)
            limit: 최대 조회 개수
            skip_calculated: True면 이미 TTM이 계산된 ticker 제외

        Returns:
            ticker 목록
        """
        query = """
        SELECT DISTINCT tf.ticker
        FROM ticker_fundamentals tf
        JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
        WHERE tf.region = %s
          AND tf.period_type = 'QUARTERLY'
          AND t.is_active = TRUE
        """

        if skip_calculated:
            # 오늘 기준 TTM이 없는 ticker만 선택
            query += """
          AND tf.ticker NOT IN (
              SELECT ticker FROM ticker_fundamentals_ttm
              WHERE region = %s
                AND as_of_date >= CURRENT_DATE - INTERVAL '7 days'
          )
            """

        query += " ORDER BY tf.ticker"

        if limit:
            query += f" LIMIT {limit}"

        try:
            params = (region,) if not skip_calculated else (region, region)
            rows = self.db.execute_query(query, params)
            tickers = [row['ticker'] for row in rows]
            logger.info(f"[{region}] TTM 계산 대상: {len(tickers)}개 ticker")
            return tickers
        except Exception as e:
            logger.error(f"[{region}] ticker 목록 조회 실패: {e}")
            return []

    def get_quarterly_data(
        self,
        ticker: str,
        region: str,
        as_of_date: Optional[date] = None,
        quarters: int = 4
    ) -> List[Dict]:
        """
        ticker의 분기별 재무 데이터 조회

        Args:
            ticker: 종목 코드
            region: 지역 코드
            as_of_date: 기준일 (None이면 오늘)
            quarters: 조회할 분기 수 (기본 4)

        Returns:
            분기별 재무 데이터 리스트
        """
        if as_of_date is None:
            as_of_date = date.today()

        query = """
        SELECT
            ticker, region, date, period_type, fiscal_year,
            data_source,
            -- Income Statement
            revenue, gross_profit, operating_profit, net_income, ebitda,
            interest_expense, interest_income,
            -- Cash Flow
            operating_cash_flow, investing_cf, financing_cf, capex, fcf,
            -- Balance Sheet
            total_assets, total_liabilities, total_equity,
            current_assets, current_liabilities,
            inventory, accounts_receivable,
            -- Per Share
            trailing_eps, shares_outstanding
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = %s
          AND period_type = 'QUARTERLY'
          AND date <= %s
        ORDER BY date DESC
        LIMIT %s
        """

        try:
            rows = self.db.execute_query(
                query,
                (ticker, region, as_of_date, quarters)
            )

            # Convert to dict format with proper type handling
            result = []
            for row in rows:
                data = dict(row)
                # Convert Decimal to Decimal (keep as-is for calculator)
                for key, value in data.items():
                    if isinstance(value, Decimal):
                        data[key] = value
                result.append(data)

            return result

        except Exception as e:
            logger.error(f"[{ticker}] 분기 데이터 조회 실패: {e}")
            return []

    def save_ttm_result(self, result: TTMResult) -> bool:
        """
        TTM 계산 결과를 DB에 저장

        Args:
            result: TTMResult 객체

        Returns:
            성공 여부
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {result.ticker} TTM 저장 스킵")
            return True

        try:
            query = """
            INSERT INTO ticker_fundamentals_ttm (
                ticker, region, as_of_date,
                -- Income Statement TTM
                revenue_ttm, gross_profit_ttm, operating_profit_ttm,
                net_income_ttm, ebitda_ttm,
                interest_expense_ttm, interest_income_ttm,
                -- Cash Flow TTM
                operating_cash_flow_ttm, investing_cf_ttm, financing_cf_ttm,
                capex_ttm, fcf_ttm,
                -- Balance Sheet
                total_assets, total_liabilities, total_equity,
                current_assets, current_liabilities,
                -- Ratios
                roe_ttm, roa_ttm, operating_margin_ttm, net_margin_ttm,
                debt_ratio,
                -- Metadata
                quarters_included, data_completeness,
                calculated_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s,
                %s
            )
            ON CONFLICT (ticker, region, as_of_date)
            DO UPDATE SET
                revenue_ttm = EXCLUDED.revenue_ttm,
                gross_profit_ttm = EXCLUDED.gross_profit_ttm,
                operating_profit_ttm = EXCLUDED.operating_profit_ttm,
                net_income_ttm = EXCLUDED.net_income_ttm,
                ebitda_ttm = EXCLUDED.ebitda_ttm,
                interest_expense_ttm = EXCLUDED.interest_expense_ttm,
                interest_income_ttm = EXCLUDED.interest_income_ttm,
                operating_cash_flow_ttm = EXCLUDED.operating_cash_flow_ttm,
                investing_cf_ttm = EXCLUDED.investing_cf_ttm,
                financing_cf_ttm = EXCLUDED.financing_cf_ttm,
                capex_ttm = EXCLUDED.capex_ttm,
                fcf_ttm = EXCLUDED.fcf_ttm,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                roe_ttm = EXCLUDED.roe_ttm,
                roa_ttm = EXCLUDED.roa_ttm,
                operating_margin_ttm = EXCLUDED.operating_margin_ttm,
                net_margin_ttm = EXCLUDED.net_margin_ttm,
                debt_ratio = EXCLUDED.debt_ratio,
                quarters_included = EXCLUDED.quarters_included,
                data_completeness = EXCLUDED.data_completeness,
                calculated_at = EXCLUDED.calculated_at,
                updated_at = CURRENT_TIMESTAMP
            """

            params = (
                result.ticker, result.region, result.as_of_date,
                # Income Statement TTM
                result.revenue_ttm, result.gross_profit_ttm, result.operating_profit_ttm,
                result.net_income_ttm, result.ebitda_ttm,
                result.interest_expense_ttm, None,  # interest_income not in TTMResult yet
                # Cash Flow TTM
                result.operating_cash_flow_ttm, None, None,  # investing_cf, financing_cf
                result.capex_ttm, result.fcf_ttm,
                # Balance Sheet
                result.total_assets, result.total_liabilities, result.total_equity,
                result.current_assets, result.current_liabilities,
                # Ratios
                result.roe_ttm, result.roa_ttm, result.operating_margin_ttm, result.net_margin_ttm,
                result.debt_ratio,
                # Metadata
                result.quarters_included, result.data_completeness,
                result.calculated_at
            )

            if not self.db.execute_update(query, params):
                logger.warning(f"[{result.ticker}] TTM 저장: DB update가 0행에 영향 (ticker가 tickers 테이블에 없을 수 있음)")
                return False
            return True

        except Exception as e:
            logger.error(f"[{result.ticker}] TTM 저장 실패: {e}")
            return False

    def calculate_and_save_ttm(
        self,
        ticker: str,
        region: str,
        as_of_date: Optional[date] = None
    ) -> Optional[TTMResult]:
        """
        단일 ticker의 TTM 계산 및 저장

        Args:
            ticker: 종목 코드
            region: 지역 코드
            as_of_date: 기준일 (None이면 오늘)

        Returns:
            TTMResult 또는 None (실패시)
        """
        # 분기 데이터 조회
        quarterly_data = self.get_quarterly_data(ticker, region, as_of_date)

        if len(quarterly_data) < 4:
            logger.warning(f"[{ticker}] 분기 데이터 부족: {len(quarterly_data)}/4")
            self.stats['tickers_skipped'] += 1
            return None

        # TTM 계산
        result = self.calculator.calculate_ttm(
            ticker=ticker,
            region=region,
            quarterly_data=quarterly_data,
            as_of_date=as_of_date
        )

        # 저장
        if self.save_ttm_result(result):
            self.stats['records_saved'] += 1
            return result
        else:
            return None

    def run_ttm_calculation(
        self,
        regions: Optional[List[str]] = None,
        limit: Optional[int] = None,
        skip_calculated: bool = True,
        as_of_date: Optional[date] = None
    ) -> Dict:
        """
        배치 TTM 계산 실행

        Args:
            regions: 대상 지역 목록 (None이면 KR, US, JP)
            limit: 지역별 최대 ticker 수
            skip_calculated: 이미 계산된 ticker 스킵
            as_of_date: 기준일 (None이면 오늘)

        Returns:
            계산 통계 dict
        """
        if regions is None:
            regions = ['KR', 'US', 'JP']

        logger.info("=" * 80)
        logger.info("TTM 계산 배치 시작")
        logger.info(f"   지역: {', '.join(regions)}")
        logger.info(f"   모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info("=" * 80)

        start_time = datetime.now()

        for region in regions:
            logger.info(f"\n[{region}] TTM 계산 시작...")

            # 대상 ticker 조회
            tickers = self.get_tickers_with_quarterly_data(
                region=region,
                limit=limit,
                skip_calculated=skip_calculated
            )

            if not tickers:
                logger.info(f"[{region}] 계산 대상 ticker 없음")
                continue

            # 각 ticker 처리
            for i, ticker in enumerate(tickers, 1):
                self.stats['tickers_processed'] += 1

                result = self.calculate_and_save_ttm(
                    ticker=ticker,
                    region=region,
                    as_of_date=as_of_date
                )

                if result:
                    self.stats['tickers_success'] += 1
                    logger.debug(
                        f"[{i}/{len(tickers)}] {ticker} TTM 계산 완료 "
                        f"(완성도: {result.data_completeness:.0%})"
                    )
                else:
                    self.stats['tickers_failed'] += 1

                # 진행률 로그 (20개마다)
                if i % 20 == 0:
                    logger.info(
                        f"[{region}] 진행률: {i}/{len(tickers)} "
                        f"({i/len(tickers)*100:.1f}%)"
                    )

        elapsed = (datetime.now() - start_time).total_seconds()
        self.stats['elapsed_seconds'] = elapsed

        # 결과 출력
        self._print_summary()

        return self.stats

    def _print_summary(self):
        """결과 요약 출력"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("TTM 계산 결과 요약")
        logger.info("=" * 80)
        logger.info(f"   처리된 ticker: {self.stats['tickers_processed']}")
        logger.info(f"   성공: {self.stats['tickers_success']}")
        logger.info(f"   스킵 (데이터 부족): {self.stats['tickers_skipped']}")
        logger.info(f"   실패: {self.stats['tickers_failed']}")
        logger.info(f"   저장된 레코드: {self.stats['records_saved']}")
        if 'elapsed_seconds' in self.stats:
            logger.info(f"   소요 시간: {self.stats['elapsed_seconds']:.1f}초")
        logger.info("=" * 80)

    def get_ttm_summary(self, region: Optional[str] = None) -> Dict:
        """
        TTM 데이터 요약 조회

        Args:
            region: 지역 코드 (None이면 전체)

        Returns:
            요약 통계 dict
        """
        query = """
        SELECT
            region,
            COUNT(*) as total_records,
            COUNT(DISTINCT ticker) as unique_tickers,
            AVG(data_completeness) as avg_completeness,
            MIN(as_of_date) as earliest_date,
            MAX(as_of_date) as latest_date
        FROM ticker_fundamentals_ttm
        """

        if region:
            query += " WHERE region = %s"
            query += " GROUP BY region"
            params = (region,)
        else:
            query += " GROUP BY region ORDER BY region"
            params = None

        try:
            rows = self.db.execute_query(query, params)
            return {row['region']: dict(row) for row in rows}
        except Exception as e:
            logger.error(f"TTM 요약 조회 실패: {e}")
            return {}
