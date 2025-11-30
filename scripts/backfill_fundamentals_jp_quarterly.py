#!/usr/bin/env python3
"""
JP 분기 재무 데이터 백필 스크립트 (TDnet/yfinance 기반)

일본 대기업들은 EDINET의 四半期報告書를 제출하지 않고
결산단신(決算短信)으로 분기 실적을 발표합니다.

이 스크립트는 TDnet API (또는 yfinance fallback)를 통해
분기별 재무 데이터를 수집하여 TTM 계산을 가능하게 합니다.

데이터 소스 우선순위:
1. J-Quants API (유료, 구조화된 데이터)
2. yfinance (무료, 제한적 데이터)

사용 예시:
    # 분기 데이터 백필 (yfinance 사용)
    python3 scripts/backfill_fundamentals_jp_quarterly.py --start-year 2023

    # J-Quants API 사용
    export JQUANTS_ID="your@email.com"
    export JQUANTS_PASSWORD="your_password"
    python3 scripts/backfill_fundamentals_jp_quarterly.py --start-year 2023 --limit 100

Author: Quant Platform Development Team
Date: 2025-11-28
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date
from typing import Optional, List

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.api_clients.tdnet_api import TDnetApiClient, TDnetQuarterlyData

# 로그 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals_jp_quarterly.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class JPQuarterlyBackfiller:
    """JP 분기 재무 데이터 백필러 (TDnet/yfinance 기반)"""

    def __init__(
        self,
        db: PostgresDatabaseManager,
        tdnet_api: TDnetApiClient,
        dry_run: bool = False
    ):
        self.db = db
        self.tdnet_api = tdnet_api
        self.dry_run = dry_run

        # 통계
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_failed': 0,
            'records_inserted': 0,
            'records_skipped': 0,
        }

    def get_jp_tickers(
        self,
        limit: Optional[int] = None,
        skip_existing: bool = True
    ) -> List[str]:
        """
        백필 대상 JP ticker 목록 조회

        Args:
            limit: 최대 조회 개수
            skip_existing: True면 이미 분기 데이터가 있는 ticker 제외

        Returns:
            ticker 목록
        """
        query = """
        SELECT DISTINCT t.ticker
        FROM tickers t
        WHERE t.region = 'JP'
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
        """

        if skip_existing:
            query += """
          AND t.ticker NOT IN (
              SELECT DISTINCT ticker FROM ticker_fundamentals
              WHERE region = 'JP' AND period_type = 'QUARTERLY'
          )
            """

        query += " ORDER BY t.ticker"

        if limit:
            query += f" LIMIT {limit}"

        try:
            rows = self.db.execute_query(query)
            tickers = [row['ticker'] for row in rows]
            logger.info(f"🇯🇵 JP 분기 백필 대상: {len(tickers)}개 ticker")
            return tickers
        except Exception as e:
            logger.error(f"ticker 목록 조회 실패: {e}")
            return []

    def insert_fundamental_data(self, data: TDnetQuarterlyData) -> bool:
        """
        재무 데이터를 ticker_fundamentals 테이블에 UPSERT

        Args:
            data: TDnet 분기 재무 데이터

        Returns:
            성공 여부
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] {data.ticker} {data.fiscal_year}{data.fiscal_period} 저장 스킵")
            return True

        try:
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year, data_source,
                revenue, operating_profit, net_income,
                total_assets, total_equity,
                trailing_eps,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                revenue = COALESCE(EXCLUDED.revenue, ticker_fundamentals.revenue),
                operating_profit = COALESCE(EXCLUDED.operating_profit, ticker_fundamentals.operating_profit),
                net_income = COALESCE(EXCLUDED.net_income, ticker_fundamentals.net_income),
                total_assets = COALESCE(EXCLUDED.total_assets, ticker_fundamentals.total_assets),
                total_equity = COALESCE(EXCLUDED.total_equity, ticker_fundamentals.total_equity),
                trailing_eps = COALESCE(EXCLUDED.trailing_eps, ticker_fundamentals.trailing_eps),
                data_source = EXCLUDED.data_source
            """

            params = (
                data.ticker, data.region, data.report_date, data.period_type,
                data.fiscal_year, data.data_source,
                data.revenue, data.operating_profit, data.net_income,
                data.total_assets, data.total_equity,
                data.eps,
            )

            self.db.execute_update(query, params)
            return True

        except Exception as e:
            logger.error(f"[{data.ticker}] DB 저장 실패: {e}")
            return False

    def backfill_ticker(
        self,
        ticker: str,
        start_year: int,
        end_year: int
    ) -> bool:
        """
        단일 ticker의 분기 재무 데이터 백필

        Args:
            ticker: JP ticker (4자리)
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            성공 여부
        """
        try:
            records_inserted = 0

            # TDnet API에서 분기 데이터 조회
            quarterly_data = self.tdnet_api.get_quarterly_fundamentals(
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
        start_year: int = 2023,
        end_year: int = 2024,
        limit: Optional[int] = None,
        tickers: Optional[List[str]] = None,
        skip_existing: bool = True
    ):
        """
        JP 분기 재무 데이터 백필 실행

        Args:
            start_year: 시작 연도
            end_year: 종료 연도
            limit: 최대 ticker 수
            tickers: 특정 ticker 목록 (None이면 DB에서 조회)
            skip_existing: 기존 데이터가 있는 ticker 스킵
        """
        logger.info("=" * 80)
        logger.info("🇯🇵 JP 분기 재무 데이터 백필 시작 (TDnet/yfinance)")
        logger.info(f"   기간: {start_year} ~ {end_year}")
        logger.info(f"   모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info(f"   데이터 소스: {self.tdnet_api.use_jquants and 'J-Quants API' or 'yfinance'}")
        logger.info("=" * 80)

        # ticker 목록 준비
        if tickers:
            target_tickers = tickers
        else:
            target_tickers = self.get_jp_tickers(
                limit=limit,
                skip_existing=skip_existing
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

            if self.backfill_ticker(ticker, start_year, end_year):
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
        description='JP 분기 재무 데이터 백필 (TDnet/yfinance)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 분기 데이터 백필 (yfinance 사용)
  python3 scripts/backfill_fundamentals_jp_quarterly.py --start-year 2023 --limit 50

  # 특정 ticker만 백필
  python3 scripts/backfill_fundamentals_jp_quarterly.py --tickers 7203,9984,6758

  # Dry run 모드
  python3 scripts/backfill_fundamentals_jp_quarterly.py --dry-run --limit 5

  # J-Quants API 사용
  export JQUANTS_ID="your@email.com"
  export JQUANTS_PASSWORD="your_password"
  python3 scripts/backfill_fundamentals_jp_quarterly.py --start-year 2023

데이터 소스:
  - J-Quants API: 유료 서비스, 구조화된 분기 데이터 제공
    (https://jpx-jquants.com/)
  - yfinance: 무료, 일부 분기 데이터 제공 (제한적)

참고:
  일본 대기업들은 EDINET의 四半期報告書 대신 결산단신(決算短信)으로
  분기 실적을 발표합니다. 이 스크립트는 그 데이터를 수집합니다.
        """
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
        help='특정 ticker 목록 (콤마로 구분, 예: 7203,9984,6758)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 저장 없이 테스트'
    )
    parser.add_argument(
        '--include-existing',
        action='store_true',
        help='이미 분기 데이터가 있는 ticker도 포함'
    )

    args = parser.parse_args()

    # 데이터베이스 연결
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ 데이터베이스 연결 성공")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        sys.exit(1)

    # TDnet API 클라이언트 초기화
    tdnet_api = TDnetApiClient(
        jquants_id=os.getenv("JQUANTS_ID"),
        jquants_password=os.getenv("JQUANTS_PASSWORD"),
        rate_limit_delay=1.0
    )

    # 연결 테스트
    if not tdnet_api.validate_connection():
        logger.error("❌ TDnet/yfinance 연결 실패")
        sys.exit(1)
    logger.info("✅ TDnet/yfinance 연결 성공")

    # 백필러 초기화
    backfiller = JPQuarterlyBackfiller(
        db=db,
        tdnet_api=tdnet_api,
        dry_run=args.dry_run
    )

    # ticker 목록 처리
    tickers = None
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]

    # 백필 실행
    try:
        backfiller.run_backfill(
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit,
            tickers=tickers,
            skip_existing=not args.include_existing
        )
    except KeyboardInterrupt:
        logger.info("\n⚠️ 사용자에 의해 중단됨")
    finally:
        tdnet_api.close()
        logger.info("🔒 세션 종료")


if __name__ == "__main__":
    main()
