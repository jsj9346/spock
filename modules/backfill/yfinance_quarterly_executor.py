"""
YFinance Quarterly Backfill Executor

HK, CN, VN 리전의 분기별 재무제표 데이터를 yfinance에서 수집하여
ticker_fundamentals 테이블에 저장합니다.

주요 기능:
- yfinance quarterly_income_stmt, quarterly_balance_sheet, quarterly_cashflow 수집
- Income Statement, Balance Sheet, Cash Flow 매핑
- 자동 TTM 계산 트리거 지원
- Rate limiting 및 체크포인트 지원

사용 예시:
    from modules.backfill.yfinance_quarterly_executor import YFinanceQuarterlyExecutor
    from modules.db_manager_postgres import PostgresDatabaseManager

    db = PostgresDatabaseManager()
    executor = YFinanceQuarterlyExecutor(db, regions=['HK', 'CN', 'VN'])

    stats = executor.run_backfill(limit=100, calculate_ttm=True)
    print(f"성공: {stats.tickers_success}, 실패: {stats.tickers_failed}")

Author: Quant Platform Development Team
Date: 2025-12-11
"""

import logging
import time
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.data_structures import (
    TickerGapInfo,
    BackfillStats,
    GapPriority
)

logger = logging.getLogger(__name__)


class YFinanceQuarterlyExecutor(BackfillExecutor):
    """
    yfinance 분기별 재무제표 백필 실행기

    HK, CN, VN 리전의 분기별 데이터를 yfinance에서 수집하여
    ticker_fundamentals 테이블에 저장합니다.
    """

    SUPPORTED_REGIONS = ['HK', 'CN', 'VN']

    # yfinance Income Statement 필드 매핑
    INCOME_STMT_MAPPING = {
        'Total Revenue': 'revenue',
        'Cost Of Revenue': 'cogs',
        'Gross Profit': 'gross_profit',
        'Operating Income': 'operating_profit',
        'Net Income': 'net_income',
        'EBITDA': 'ebitda',
        'Interest Expense': 'interest_expense',
        'Interest Income': 'interest_income',
        'Research And Development': 'rd_expense',
        'Selling General And Administration': 'sga_expense',
        'Basic EPS': 'trailing_eps',
        'Basic Average Shares': 'shares_outstanding',
    }

    # yfinance Balance Sheet 필드 매핑
    BALANCE_SHEET_MAPPING = {
        'Total Assets': 'total_assets',
        'Total Liabilities Net Minority Interest': 'total_liabilities',
        'Stockholders Equity': 'total_equity',
        'Current Assets': 'current_assets',
        'Current Liabilities': 'current_liabilities',
        'Inventory': 'inventory',
        'Accounts Receivable': 'accounts_receivable',
        'Cash And Cash Equivalents': 'cash_and_equivalents',
        'Net PPE': 'pp_e',
        'Capital Stock': 'capital_stock',
        'Retained Earnings': 'retained_earnings',
        'Treasury Stock': 'treasury_stock',
    }

    # yfinance Cash Flow 필드 매핑
    CASHFLOW_MAPPING = {
        'Operating Cash Flow': 'operating_cash_flow',
        'Investing Cash Flow': 'investing_cf',
        'Financing Cash Flow': 'financing_cf',
        'Capital Expenditure': 'capex',
        'Free Cash Flow': 'fcf',
    }

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 0.5,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        regions: Optional[List[str]] = None
    ):
        """
        YFinance Quarterly Executor 초기화

        Args:
            db: PostgreSQL 데이터베이스 매니저
            dry_run: True이면 실제 저장 없이 미리보기만 수행
            rate_limit_delay: yfinance API 호출 간 지연 시간 (초, 기본 0.5s = 2 req/sec)
            max_retries: 실패 시 최대 재시도 횟수
            retry_delay: 재시도 간 지연 시간 (초)
            regions: 대상 리전 목록 (기본: ['HK', 'CN', 'VN'])
        """
        super().__init__(
            db=db,
            dry_run=dry_run,
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        # 리전 설정
        self.regions = regions or self.SUPPORTED_REGIONS

        # 지원하지 않는 리전 체크
        unsupported = set(self.regions) - set(self.SUPPORTED_REGIONS)
        if unsupported:
            raise ValueError(f"Unsupported regions: {unsupported}. Supported: {self.SUPPORTED_REGIONS}")

        # yfinance 라이브러리 체크
        try:
            import yfinance as yf
            self.yf = yf
        except ImportError:
            raise ImportError("yfinance library not installed: pip install yfinance")

        # 통계 확장
        self.quarterly_stats = {
            'quarters_saved': 0,
            'tickers_no_data': 0,
            'tickers_partial_data': 0,
        }

        logger.info(f"🌏 YFinanceQuarterlyExecutor 초기화 (regions={self.regions}, dry_run={dry_run})")

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        실행 전 사전 조건 검증

        Returns:
            (준비 완료 여부, 문제점 목록) 튜플
        """
        issues = []

        # 1. 데이터베이스 연결 확인
        try:
            result = self.db.execute_query("SELECT 1")
            if not result:
                issues.append("데이터베이스 연결 실패")
        except Exception as e:
            issues.append(f"데이터베이스 연결 에러: {e}")

        # 2. 대상 리전 ticker 존재 확인
        for region in self.regions:
            try:
                count_query = f"""
                SELECT COUNT(*) as cnt FROM tickers
                WHERE region = '{region}' AND asset_type = 'STOCK' AND is_active = TRUE
                """
                result = self.db.execute_query(count_query)
                if result and result[0]['cnt'] == 0:
                    issues.append(f"{region} 리전 활성 ticker가 없음")
            except Exception as e:
                issues.append(f"{region} ticker 조회 에러: {e}")

        # 3. yfinance 연결 테스트 (간단한 API 호출)
        try:
            test_ticker = self.yf.Ticker("0700.HK")
            info = test_ticker.info
            if not info or 'symbol' not in info:
                issues.append("yfinance API 연결 실패")
        except Exception as e:
            issues.append(f"yfinance API 에러: {e}")

        return (len(issues) == 0, issues)

    def _to_yf_ticker(self, ticker: str, region: str) -> str:
        """
        데이터베이스 ticker를 yfinance 형식으로 변환

        Args:
            ticker: 데이터베이스 ticker
            region: 리전 코드

        Returns:
            yfinance 호환 ticker
        """
        if region == 'HK':
            # HK: 이미 .HK 접미사 있음
            return ticker
        elif region == 'CN':
            # CN: 이미 .SS/.SZ 접미사 있음
            return ticker
        elif region == 'VN':
            # VN: .VN 접미사 추가 필요
            if not ticker.endswith('.VN'):
                return f"{ticker}.VN"
            return ticker
        else:
            return ticker

    def _is_valid_cn_ticker(self, ticker: str) -> bool:
        """
        CN ticker가 yfinance에서 유효한지 확인 (6자리 숫자만 지원)
        """
        import re
        match = re.match(r'^(\d+)\.(SZ|SS)$', ticker)
        if not match:
            return False

        numeric_part = match.group(1)
        if len(numeric_part) != 6:
            logger.debug(f"⏭️ [CN:{ticker}] 레거시 ticker 건너뜀 ({len(numeric_part)}자리 코드)")
            return False
        return True

    def get_tickers_for_backfill(
        self,
        region: str,
        limit: Optional[int] = None,
        force_refresh: bool = False
    ) -> List[TickerGapInfo]:
        """
        백필 대상 ticker 조회

        Args:
            region: 대상 리전 (HK, CN, VN)
            limit: 최대 ticker 수
            force_refresh: True면 이미 QUARTERLY 데이터가 있는 ticker도 포함

        Returns:
            TickerGapInfo 목록
        """
        if force_refresh:
            # force_refresh: 모든 활성 ticker
            query = f"""
            SELECT t.ticker, t.name, t.fund_status
            FROM tickers t
            WHERE t.region = '{region}'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
            ORDER BY t.ticker
            """
        else:
            # 일반 모드: QUARTERLY 데이터가 없는 ticker만
            query = f"""
            SELECT t.ticker, t.name, t.fund_status
            FROM tickers t
            WHERE t.region = '{region}'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM ticker_fundamentals tf
                  WHERE tf.ticker = t.ticker
                    AND tf.region = '{region}'
                    AND tf.period_type = 'QUARTERLY'
              )
            ORDER BY t.ticker
            """

        if limit:
            query += f" LIMIT {limit}"

        results = self.db.execute_query(query)

        tickers = []
        for row in results:
            tickers.append(TickerGapInfo(
                ticker=row['ticker'],
                name=row['name'] or row['ticker'],
                region=region,
                priority=GapPriority.FULLY_MISSING  # Default to FULLY_MISSING since we don't have gap analysis
            ))

        logger.info(f"📊 [{region}] {len(tickers)} tickers for QUARTERLY backfill")
        return tickers

    def _safe_get(self, df, field: str, date_col) -> Optional[Decimal]:
        """
        DataFrame에서 안전하게 값 추출

        Args:
            df: pandas DataFrame (또는 None)
            field: 필드명
            date_col: 날짜 컬럼

        Returns:
            Decimal 값 또는 None
        """
        if df is None or df.empty:
            return None

        try:
            if field not in df.index:
                return None

            value = df.loc[field, date_col]

            # NaN 체크
            if value is None or (hasattr(value, '__float__') and value != value):
                return None

            return Decimal(str(float(value)))
        except Exception:
            return None

    def fetch_quarterly_data(self, ticker: str, region: str) -> Optional[List[Dict]]:
        """
        yfinance에서 분기별 재무제표 수집

        Args:
            ticker: 데이터베이스 ticker
            region: 리전 코드

        Returns:
            분기별 데이터 리스트 (최대 8분기) 또는 None
        """
        yf_ticker = self._to_yf_ticker(ticker, region)

        try:
            stock = self.yf.Ticker(yf_ticker)

            # 분기별 손익계산서
            income_stmt = stock.quarterly_income_stmt

            if income_stmt is None or income_stmt.empty:
                logger.warning(f"⚠️ [{region}:{ticker}] yfinance에서 분기 데이터 없음")
                return None

            # 분기별 재무상태표
            balance_sheet = stock.quarterly_balance_sheet

            # 분기별 현금흐름표 (없을 수 있음)
            try:
                cashflow = stock.quarterly_cashflow
            except Exception:
                cashflow = None

            # 날짜별로 데이터 병합
            quarters = []
            for date_col in income_stmt.columns:
                quarter_data = {
                    'ticker': ticker,
                    'region': region,
                    'date': date_col.date() if hasattr(date_col, 'date') else date_col,
                    'period_type': 'QUARTERLY',
                    'data_source': 'yfinance',
                }

                # Income Statement 매핑
                for yf_field, db_field in self.INCOME_STMT_MAPPING.items():
                    quarter_data[db_field] = self._safe_get(income_stmt, yf_field, date_col)

                # Balance Sheet 매핑 (같은 날짜가 있는 경우)
                if balance_sheet is not None and not balance_sheet.empty and date_col in balance_sheet.columns:
                    for yf_field, db_field in self.BALANCE_SHEET_MAPPING.items():
                        value = self._safe_get(balance_sheet, yf_field, date_col)
                        # treasury_stock은 음수여야 함 (DB 제약조건)
                        if db_field == 'treasury_stock' and value is not None:
                            if value >= 0:
                                value = -abs(value) if value != 0 else None
                        quarter_data[db_field] = value

                # Cash Flow 매핑 (같은 날짜가 있는 경우)
                if cashflow is not None and not cashflow.empty and date_col in cashflow.columns:
                    for yf_field, db_field in self.CASHFLOW_MAPPING.items():
                        quarter_data[db_field] = self._safe_get(cashflow, yf_field, date_col)

                # 데이터 품질 검증
                if self._validate_quarterly_data(quarter_data):
                    quarters.append(quarter_data)

            if not quarters:
                logger.warning(f"⚠️ [{region}:{ticker}] 유효한 분기 데이터 없음 (검증 실패)")
                return None

            logger.info(f"✅ [{region}:{ticker}] {len(quarters)}개 분기 데이터 수집")
            return quarters

        except Exception as e:
            logger.error(f"❌ [{region}:{ticker}] yfinance API 실패: {e}")
            return None

    def _validate_quarterly_data(self, data: Dict) -> bool:
        """
        분기 데이터 품질 검증

        Args:
            data: 분기 데이터 dict

        Returns:
            True면 유효, False면 무효
        """
        # 필수 필드 확인 (revenue 또는 net_income 중 하나는 있어야 함)
        if not data.get('revenue') and not data.get('net_income'):
            return False

        # 비정상 값 필터링 (음수 매출)
        if data.get('revenue') and data['revenue'] < 0:
            return False

        return True

    def save_quarterly_data(self, data: Dict) -> bool:
        """
        분기별 데이터를 ticker_fundamentals 테이블에 저장

        Args:
            data: 분기 데이터 dict

        Returns:
            성공 여부
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would save QUARTERLY data for {data['region']}:{data['ticker']} ({data['date']})")
            return True

        try:
            # UPSERT 쿼리 구성
            fields = ['ticker', 'region', 'date', 'period_type', 'data_source']
            values = ['%(ticker)s', '%(region)s', '%(date)s', '%(period_type)s', '%(data_source)s']
            updates = []

            # 동적으로 필드 추가
            for db_field in list(self.INCOME_STMT_MAPPING.values()) + \
                           list(self.BALANCE_SHEET_MAPPING.values()) + \
                           list(self.CASHFLOW_MAPPING.values()):
                if data.get(db_field) is not None:
                    fields.append(db_field)
                    values.append(f'%({db_field})s')
                    updates.append(f'{db_field} = EXCLUDED.{db_field}')

            query = f"""
            INSERT INTO ticker_fundamentals ({', '.join(fields)})
            VALUES ({', '.join(values)})
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET {', '.join(updates)}, data_source = EXCLUDED.data_source
            """

            success = self.db.execute_update(query, data)

            if success:
                self.quarterly_stats['quarters_saved'] += 1
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"❌ [{data['region']}:{data['ticker']}] DB 저장 실패: {e}")
            return False

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """
        단일 ticker에 대한 QUARTERLY 백필 실행

        Args:
            ticker_info: ticker 정보

        Returns:
            성공 여부
        """
        ticker = ticker_info.ticker
        region = ticker_info.region

        # CN 레거시 ticker 건너뛰기
        if region == 'CN' and not self._is_valid_cn_ticker(ticker):
            self.quarterly_stats['tickers_no_data'] += 1
            return False

        # yfinance에서 분기 데이터 수집
        quarters = self.fetch_quarterly_data(ticker, region)

        if not quarters:
            self.quarterly_stats['tickers_no_data'] += 1
            return False

        # 각 분기 데이터 저장
        saved_count = 0
        for quarter in quarters:
            if self.save_quarterly_data(quarter):
                saved_count += 1

        if saved_count == 0:
            self.quarterly_stats['tickers_no_data'] += 1
            return False
        elif saved_count < len(quarters):
            self.quarterly_stats['tickers_partial_data'] += 1

        return True

    def run_backfill(
        self,
        regions: Optional[List[str]] = None,
        limit: Optional[int] = None,
        force_refresh: bool = False,
        calculate_ttm: bool = True,
        checkpoint_interval: int = 50
    ) -> BackfillStats:
        """
        QUARTERLY 백필 실행

        Args:
            regions: 대상 리전 목록 (None이면 초기화 시 설정된 리전 사용)
            limit: 리전별 최대 ticker 수
            force_refresh: True면 이미 QUARTERLY 데이터가 있는 ticker도 포함
            calculate_ttm: 백필 후 자동 TTM 계산 여부
            checkpoint_interval: 체크포인트 저장 주기

        Returns:
            BackfillStats
        """
        target_regions = regions or self.regions

        logger.info("=" * 80)
        logger.info("yfinance QUARTERLY 백필 시작")
        logger.info(f"대상 리전: {target_regions}")
        logger.info(f"모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info(f"Force Refresh: {force_refresh}")
        logger.info(f"자동 TTM 계산: {calculate_ttm}")
        logger.info("=" * 80)

        # 모든 리전의 ticker 수집
        all_tickers = []
        for region in target_regions:
            tickers = self.get_tickers_for_backfill(region, limit, force_refresh)
            all_tickers.extend(tickers)

        if not all_tickers:
            logger.warning("⚠️ 백필 대상 ticker가 없습니다")
            return self.stats

        # 배치 실행
        stats = self.execute_batch(
            tickers=all_tickers,
            checkpoint_interval=checkpoint_interval
        )

        # 확장 통계 출력
        logger.info("\n📊 QUARTERLY 백필 추가 통계:")
        logger.info(f"  분기 데이터 저장: {self.quarterly_stats['quarters_saved']}")
        logger.info(f"  데이터 없음: {self.quarterly_stats['tickers_no_data']}")
        logger.info(f"  부분 데이터: {self.quarterly_stats['tickers_partial_data']}")

        # 자동 TTM 계산
        if calculate_ttm and stats.tickers_success > 0 and not self.dry_run:
            logger.info("\n🔄 자동 TTM 계산 시작...")
            ttm_result = self._calculate_ttm(target_regions)
            if ttm_result:
                logger.info(f"✅ TTM 계산 완료")

        return stats

    def _calculate_ttm(self, regions: List[str]) -> bool:
        """
        QUARTERLY 데이터 기반 TTM 계산

        Args:
            regions: 대상 리전 목록

        Returns:
            성공 여부
        """
        try:
            from modules.fundamentals.ttm_service import TTMService

            ttm_service = TTMService(self.db)
            result = ttm_service.run_ttm_calculation(
                regions=regions,
                skip_calculated=False
            )

            success_cnt = result.get('tickers_success', 0)
            if success_cnt > 0:
                logger.info(f"  TTM 계산 성공: {success_cnt} tickers")
                return True
            else:
                logger.warning(f"  TTM 계산 대상 없음 또는 실패")
                return False

        except ImportError:
            logger.warning("⚠️ TTMService를 찾을 수 없습니다")
            return False
        except Exception as e:
            logger.error(f"❌ TTM 계산 에러: {e}")
            return False
