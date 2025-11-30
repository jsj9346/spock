#!/usr/bin/env python3
"""
SEC EDGAR 재무 데이터 백필 스크립트

US 시장 종목의 재무 데이터를 SEC EDGAR API에서 수집하여
ticker_fundamentals 테이블에 저장합니다.

지원 보고서 유형:
- annual: 10-K (연간 보고서)
- quarterly: 10-Q (분기 보고서)
- all: 연간 + 분기 모두

사용 예시:
    # 연간 데이터 백필
    python3 scripts/backfill_fundamentals_sec.py --report-type annual --start-year 2020

    # 분기 데이터 백필 (TTM 계산용)
    python3 scripts/backfill_fundamentals_sec.py --report-type quarterly --start-year 2023

    # 전체 데이터 백필
    python3 scripts/backfill_fundamentals_sec.py --report-type all --limit 100

Author: Quant Platform Development Team
Date: 2025-11-27
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Optional, List

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.api_clients.sec_edgar_api import SECEdgarApiClient, SECFundamentalData

# 로그 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals_sec.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SECFundamentalsBackfiller:
    """SEC EDGAR 재무 데이터 백필러"""

    def __init__(
        self,
        db: PostgresDatabaseManager,
        sec_api: SECEdgarApiClient,
        dry_run: bool = False
    ):
        self.db = db
        self.sec_api = sec_api
        self.dry_run = dry_run

        # 통계
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_failed': 0,
            'records_inserted': 0,
            'records_skipped': 0,
        }

    def get_us_tickers(
        self,
        limit: Optional[int] = None,
        skip_existing: bool = True
    ) -> List[str]:
        """
        백필 대상 US ticker 목록 조회

        Args:
            limit: 최대 조회 개수
            skip_existing: True면 이미 데이터가 있는 ticker 제외

        Returns:
            ticker 목록
        """
        query = """
        SELECT DISTINCT t.ticker
        FROM tickers t
        WHERE t.region = 'US'
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
        """

        if skip_existing:
            query += """
          AND t.ticker NOT IN (
              SELECT DISTINCT ticker FROM ticker_fundamentals
              WHERE region = 'US' AND period_type = 'QUARTERLY'
          )
            """

        query += " ORDER BY t.ticker"

        if limit:
            query += f" LIMIT {limit}"

        try:
            rows = self.db.execute_query(query)
            tickers = [row['ticker'] for row in rows]
            logger.info(f"📋 US 백필 대상: {len(tickers)}개 ticker")
            return tickers
        except Exception as e:
            logger.error(f"ticker 목록 조회 실패: {e}")
            return []

    def insert_fundamental_data(self, data: SECFundamentalData) -> bool:
        """
        재무 데이터를 ticker_fundamentals 테이블에 UPSERT

        Args:
            data: SEC 재무 데이터

        Returns:
            성공 여부
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {data.ticker} {data.fiscal_year} {data.fiscal_period} 저장 스킵")
            return True

        try:
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year, data_source,
                revenue, gross_profit, operating_profit, net_income, ebitda,
                cogs, sga_expense,
                total_assets, total_liabilities, total_equity,
                current_assets, current_liabilities, inventory, pp_e, accounts_receivable,
                operating_cash_flow, investing_cf, financing_cf, capex, fcf,
                trailing_eps, shares_outstanding,
                capital_stock, retained_earnings,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                revenue = COALESCE(EXCLUDED.revenue, ticker_fundamentals.revenue),
                gross_profit = COALESCE(EXCLUDED.gross_profit, ticker_fundamentals.gross_profit),
                operating_profit = COALESCE(EXCLUDED.operating_profit, ticker_fundamentals.operating_profit),
                net_income = COALESCE(EXCLUDED.net_income, ticker_fundamentals.net_income),
                ebitda = COALESCE(EXCLUDED.ebitda, ticker_fundamentals.ebitda),
                cogs = COALESCE(EXCLUDED.cogs, ticker_fundamentals.cogs),
                sga_expense = COALESCE(EXCLUDED.sga_expense, ticker_fundamentals.sga_expense),
                total_assets = COALESCE(EXCLUDED.total_assets, ticker_fundamentals.total_assets),
                total_liabilities = COALESCE(EXCLUDED.total_liabilities, ticker_fundamentals.total_liabilities),
                total_equity = COALESCE(EXCLUDED.total_equity, ticker_fundamentals.total_equity),
                current_assets = COALESCE(EXCLUDED.current_assets, ticker_fundamentals.current_assets),
                current_liabilities = COALESCE(EXCLUDED.current_liabilities, ticker_fundamentals.current_liabilities),
                inventory = COALESCE(EXCLUDED.inventory, ticker_fundamentals.inventory),
                pp_e = COALESCE(EXCLUDED.pp_e, ticker_fundamentals.pp_e),
                accounts_receivable = COALESCE(EXCLUDED.accounts_receivable, ticker_fundamentals.accounts_receivable),
                operating_cash_flow = COALESCE(EXCLUDED.operating_cash_flow, ticker_fundamentals.operating_cash_flow),
                investing_cf = COALESCE(EXCLUDED.investing_cf, ticker_fundamentals.investing_cf),
                financing_cf = COALESCE(EXCLUDED.financing_cf, ticker_fundamentals.financing_cf),
                capex = COALESCE(EXCLUDED.capex, ticker_fundamentals.capex),
                fcf = COALESCE(EXCLUDED.fcf, ticker_fundamentals.fcf),
                trailing_eps = COALESCE(EXCLUDED.trailing_eps, ticker_fundamentals.trailing_eps),
                shares_outstanding = COALESCE(EXCLUDED.shares_outstanding, ticker_fundamentals.shares_outstanding),
                capital_stock = COALESCE(EXCLUDED.capital_stock, ticker_fundamentals.capital_stock),
                retained_earnings = COALESCE(EXCLUDED.retained_earnings, ticker_fundamentals.retained_earnings),
                data_source = EXCLUDED.data_source
            """

            params = (
                data.ticker, data.region, data.report_date, data.period_type,
                data.fiscal_year, data.data_source,
                data.revenue, data.gross_profit, data.operating_profit,
                data.net_income, data.ebitda,
                data.cogs, data.sga_expense,
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

    def backfill_ticker(
        self,
        ticker: str,
        report_type: str,
        start_year: int,
        end_year: int
    ) -> bool:
        """
        단일 ticker의 재무 데이터 백필

        Args:
            ticker: US ticker
            report_type: 'annual', 'quarterly', 'all'
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            성공 여부
        """
        try:
            records_inserted = 0

            # 연간 데이터
            if report_type in ('annual', 'all'):
                annual_data = self.sec_api.get_historical_fundamentals(
                    ticker=ticker,
                    start_year=start_year,
                    end_year=end_year,
                    period_type="ANNUAL"
                )

                for data in annual_data:
                    if self.insert_fundamental_data(data):
                        records_inserted += 1

            # 분기 데이터
            if report_type in ('quarterly', 'all'):
                quarterly_data = self.sec_api.get_quarterly_fundamentals(
                    ticker=ticker,
                    start_year=start_year,
                    end_year=end_year
                )

                for data in quarterly_data:
                    if self.insert_fundamental_data(data):
                        records_inserted += 1

            if records_inserted > 0:
                logger.info(f"✅ [{ticker}] {records_inserted}개 레코드 저장 완료")
                self.stats['records_inserted'] += records_inserted
                return True
            else:
                logger.warning(f"⚠️ [{ticker}] 저장된 데이터 없음")
                return False

        except Exception as e:
            logger.error(f"❌ [{ticker}] 백필 실패: {e}")
            return False

    def run_backfill(
        self,
        report_type: str = 'quarterly',
        start_year: int = 2023,
        end_year: int = 2024,
        limit: Optional[int] = None,
        tickers: Optional[List[str]] = None
    ):
        """
        SEC 재무 데이터 백필 실행

        Args:
            report_type: 'annual', 'quarterly', 'all'
            start_year: 시작 연도
            end_year: 종료 연도
            limit: 최대 ticker 수
            tickers: 특정 ticker 목록 (None이면 DB에서 조회)
        """
        logger.info("=" * 80)
        logger.info("🇺🇸 SEC EDGAR 재무 데이터 백필 시작")
        logger.info(f"   보고서 유형: {report_type.upper()}")
        logger.info(f"   기간: {start_year} ~ {end_year}")
        logger.info(f"   모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info("=" * 80)

        # ticker 목록 준비
        if tickers:
            target_tickers = tickers
        else:
            target_tickers = self.get_us_tickers(
                limit=limit,
                skip_existing=(report_type == 'quarterly')  # 분기만 스킵
            )

        if not target_tickers:
            logger.warning("백필 대상 ticker가 없습니다")
            return

        logger.info(f"📊 총 {len(target_tickers)}개 ticker 처리 예정")
        logger.info("")

        # 각 ticker 처리
        for i, ticker in enumerate(target_tickers, 1):
            logger.info(f"[{i}/{len(target_tickers)}] {ticker} 처리 중...")

            self.stats['tickers_processed'] += 1

            if self.backfill_ticker(ticker, report_type, start_year, end_year):
                self.stats['tickers_success'] += 1
            else:
                self.stats['tickers_failed'] += 1

            # 진행률 로그 (10개마다)
            if i % 10 == 0:
                logger.info(f"📈 진행률: {i}/{len(target_tickers)} ({i/len(target_tickers)*100:.1f}%)")

        # 결과 출력
        self._print_summary()

    def _print_summary(self):
        """백필 결과 요약 출력"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 백필 결과 요약")
        logger.info("=" * 80)
        logger.info(f"   처리된 ticker: {self.stats['tickers_processed']}")
        logger.info(f"   성공: {self.stats['tickers_success']}")
        logger.info(f"   실패: {self.stats['tickers_failed']}")
        logger.info(f"   저장된 레코드: {self.stats['records_inserted']}")
        logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='SEC EDGAR 재무 데이터 백필',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 분기 데이터 백필 (TTM 계산용)
  python3 scripts/backfill_fundamentals_sec.py --report-type quarterly --start-year 2023

  # 연간 데이터 백필
  python3 scripts/backfill_fundamentals_sec.py --report-type annual --start-year 2020

  # 특정 ticker만 백필
  python3 scripts/backfill_fundamentals_sec.py --tickers AAPL,MSFT,GOOGL --report-type all

  # Dry run 모드
  python3 scripts/backfill_fundamentals_sec.py --report-type quarterly --dry-run --limit 5
        """
    )

    parser.add_argument(
        '--report-type',
        type=str,
        choices=['annual', 'quarterly', 'all'],
        default='quarterly',
        help='보고서 유형 (기본값: quarterly)'
    )
    parser.add_argument(
        '--start-year',
        type=int,
        default=2023,
        help='시작 연도 (기본값: 2023)'
    )
    parser.add_argument(
        '--end-year',
        type=int,
        default=2024,
        help='종료 연도 (기본값: 2024)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='최대 ticker 수 (테스트용)'
    )
    parser.add_argument(
        '--tickers',
        type=str,
        default=None,
        help='특정 ticker 목록 (콤마로 구분, 예: AAPL,MSFT,GOOGL)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 저장 없이 테스트'
    )

    args = parser.parse_args()

    # 데이터베이스 연결
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ 데이터베이스 연결 성공")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        sys.exit(1)

    # SEC API 클라이언트 초기화
    sec_api = SECEdgarApiClient(
        user_agent=os.getenv("SEC_USER_AGENT", "SpockQuantPlatform/1.0 (quant@spock.dev)"),
        rate_limit_delay=0.15  # SEC 권장: 10 req/sec
    )

    # 연결 테스트
    if not sec_api.validate_connection():
        logger.error("❌ SEC API 연결 실패")
        sys.exit(1)
    logger.info("✅ SEC API 연결 성공")

    # 백필러 초기화
    backfiller = SECFundamentalsBackfiller(
        db=db,
        sec_api=sec_api,
        dry_run=args.dry_run
    )

    # ticker 목록 처리
    tickers = None
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]

    # 백필 실행
    try:
        backfiller.run_backfill(
            report_type=args.report_type,
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit,
            tickers=tickers
        )
    except KeyboardInterrupt:
        logger.info("\n⚠️ 사용자에 의해 중단됨")
    finally:
        sec_api.close()
        logger.info("🔒 세션 종료")


if __name__ == "__main__":
    main()
