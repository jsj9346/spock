"""
TTM (Trailing Twelve Months) Calculator

Calculates TTM metrics by aggregating quarterly financial data.
Supports income statement aggregation (sum) and balance sheet point-in-time values.

Author: Quant Platform Development Team
Date: 2025-11-27
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class TTMResult:
    """TTM 계산 결과"""
    ticker: str
    region: str
    as_of_date: date

    # Income Statement (합산)
    revenue_ttm: Optional[Decimal] = None
    operating_profit_ttm: Optional[Decimal] = None
    net_income_ttm: Optional[Decimal] = None
    ebitda_ttm: Optional[Decimal] = None
    gross_profit_ttm: Optional[Decimal] = None
    interest_expense_ttm: Optional[Decimal] = None

    # Cash Flow (합산)
    operating_cash_flow_ttm: Optional[Decimal] = None
    capex_ttm: Optional[Decimal] = None
    fcf_ttm: Optional[Decimal] = None

    # Balance Sheet (최신값)
    total_assets: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    current_assets: Optional[Decimal] = None
    current_liabilities: Optional[Decimal] = None

    # Derived Ratios
    roe_ttm: Optional[float] = None
    roa_ttm: Optional[float] = None
    operating_margin_ttm: Optional[float] = None
    net_margin_ttm: Optional[float] = None
    debt_ratio: Optional[float] = None

    # Metadata
    quarters_included: List[str] = None
    data_completeness: float = 0.0
    calculated_at: datetime = None

    def __post_init__(self):
        if self.quarters_included is None:
            self.quarters_included = []
        if self.calculated_at is None:
            self.calculated_at = datetime.now()


class TTMCalculator:
    """
    TTM (Trailing Twelve Months) Calculator

    최근 4분기 재무 데이터를 집계하여 연환산 지표를 계산합니다.

    계산 방식:
    - 손익계산서 지표: 4분기 합산 (revenue, net_income 등)
    - 재무상태표 지표: 최신 분기 값 사용 (total_assets, total_equity 등)
    - 파생 비율: TTM 데이터 기반 계산 (ROE, ROA, 마진 등)

    Example:
        >>> calculator = TTMCalculator()
        >>> quarterly_data = [
        ...     {'fiscal_year': 2024, 'quarter': 3, 'revenue': Decimal('100'), ...},
        ...     {'fiscal_year': 2024, 'quarter': 2, 'revenue': Decimal('95'), ...},
        ...     {'fiscal_year': 2024, 'quarter': 1, 'revenue': Decimal('90'), ...},
        ...     {'fiscal_year': 2023, 'quarter': 4, 'revenue': Decimal('85'), ...},
        ... ]
        >>> result = calculator.calculate_ttm(
        ...     ticker='005930',
        ...     region='KR',
        ...     quarterly_data=quarterly_data
        ... )
        >>> print(result.revenue_ttm)  # 370 (100+95+90+85)
    """

    # 합산 대상 지표 (손익계산서, 현금흐름표)
    SUM_METRICS = [
        'revenue',
        'operating_profit',
        'net_income',
        'ebitda',
        'gross_profit',
        'interest_expense',
        'interest_income',
        'operating_cash_flow',
        'capex',
        'fcf',
        'investing_cf',
        'financing_cf',
    ]

    # 시점 데이터 (재무상태표) - 최신값 사용
    POINT_IN_TIME_METRICS = [
        'total_assets',
        'total_equity',
        'total_liabilities',
        'current_assets',
        'current_liabilities',
        'inventory',
        'accounts_receivable',
        'total_debt',
        'cash_and_equivalents',
        'retained_earnings',
        'capital_stock',
    ]

    def __init__(self):
        """Initialize TTM Calculator"""
        pass

    def calculate_ttm(
        self,
        ticker: str,
        region: str,
        quarterly_data: List[Dict],
        as_of_date: Optional[date] = None
    ) -> TTMResult:
        """
        TTM 지표 계산

        Args:
            ticker: 종목 코드
            region: 지역 코드 (KR, US 등)
            quarterly_data: 분기별 재무 데이터 리스트 (날짜 기준 내림차순 정렬 권장)
            as_of_date: TTM 계산 기준일 (기본값: 가장 최근 분기)

        Returns:
            TTMResult 객체
        """
        if not quarterly_data:
            logger.warning(f"[{ticker}] No quarterly data provided")
            return TTMResult(
                ticker=ticker,
                region=region,
                as_of_date=as_of_date or date.today(),
                data_completeness=0.0
            )

        # 날짜 기준 정렬 (내림차순)
        sorted_data = self._sort_quarterly_data(quarterly_data)

        # 기준일 설정
        if as_of_date is None:
            as_of_date = self._get_latest_date(sorted_data)

        # 최근 4분기 선택
        recent_4q = self._select_recent_quarters(sorted_data, as_of_date, n=4)

        if len(recent_4q) < 4:
            logger.warning(
                f"[{ticker}] Insufficient quarterly data: {len(recent_4q)}/4 quarters available"
            )

        # 손익계산서/현금흐름표 지표 합산
        sum_metrics = self._calculate_sum_metrics(recent_4q)

        # 재무상태표 지표 (최신값)
        point_metrics = self._get_point_in_time_metrics(recent_4q)

        # 파생 비율 계산
        ratios = self._calculate_derived_ratios(sum_metrics, point_metrics, recent_4q)

        # 데이터 완성도 계산
        completeness = self._calculate_completeness(recent_4q, sum_metrics)

        # 포함된 분기 목록 생성
        quarters_included = self._format_quarters_included(recent_4q)

        return TTMResult(
            ticker=ticker,
            region=region,
            as_of_date=as_of_date,

            # Income Statement TTM
            revenue_ttm=sum_metrics.get('revenue'),
            operating_profit_ttm=sum_metrics.get('operating_profit'),
            net_income_ttm=sum_metrics.get('net_income'),
            ebitda_ttm=sum_metrics.get('ebitda'),
            gross_profit_ttm=sum_metrics.get('gross_profit'),
            interest_expense_ttm=sum_metrics.get('interest_expense'),

            # Cash Flow TTM
            operating_cash_flow_ttm=sum_metrics.get('operating_cash_flow'),
            capex_ttm=sum_metrics.get('capex'),
            fcf_ttm=sum_metrics.get('fcf'),

            # Balance Sheet (point-in-time)
            total_assets=point_metrics.get('total_assets'),
            total_equity=point_metrics.get('total_equity'),
            total_liabilities=point_metrics.get('total_liabilities'),
            current_assets=point_metrics.get('current_assets'),
            current_liabilities=point_metrics.get('current_liabilities'),

            # Ratios
            roe_ttm=ratios.get('roe_ttm'),
            roa_ttm=ratios.get('roa_ttm'),
            operating_margin_ttm=ratios.get('operating_margin_ttm'),
            net_margin_ttm=ratios.get('net_margin_ttm'),
            debt_ratio=ratios.get('debt_ratio'),

            # Metadata
            quarters_included=quarters_included,
            data_completeness=completeness,
            calculated_at=datetime.now()
        )

    def _sort_quarterly_data(self, data: List[Dict]) -> List[Dict]:
        """분기 데이터를 날짜 기준 내림차순 정렬"""
        def get_sort_key(record):
            # date 필드 우선
            if 'date' in record and record['date']:
                d = record['date']
                if isinstance(d, str):
                    return d
                return d.isoformat() if hasattr(d, 'isoformat') else str(d)

            # fiscal_year + quarter로 정렬
            year = record.get('fiscal_year', 0)
            quarter = record.get('quarter', 0)
            return f"{year}Q{quarter}"

        return sorted(data, key=get_sort_key, reverse=True)

    def _get_latest_date(self, sorted_data: List[Dict]) -> date:
        """정렬된 데이터에서 최신 날짜 추출"""
        if not sorted_data:
            return date.today()

        first = sorted_data[0]
        if 'date' in first and first['date']:
            d = first['date']
            if isinstance(d, date):
                return d
            if isinstance(d, str):
                return date.fromisoformat(d)

        # fallback: fiscal_year + quarter 기반 추정
        year = first.get('fiscal_year', date.today().year)
        quarter = first.get('quarter', 4)
        month = quarter * 3
        return date(year, month, 1)

    def _select_recent_quarters(
        self,
        sorted_data: List[Dict],
        as_of_date: date,
        n: int = 4
    ) -> List[Dict]:
        """기준일 기준 최근 n개 분기 선택"""
        recent = []

        for record in sorted_data:
            record_date = self._get_record_date(record)

            # 기준일 이전 데이터만 선택
            if record_date and record_date <= as_of_date:
                recent.append(record)
                if len(recent) >= n:
                    break

        return recent

    def _get_record_date(self, record: Dict) -> Optional[date]:
        """레코드에서 날짜 추출"""
        d = record.get('date')
        if d:
            if isinstance(d, date):
                return d
            if isinstance(d, str):
                try:
                    return date.fromisoformat(d)
                except ValueError:
                    pass
        return None

    def _calculate_sum_metrics(self, quarters: List[Dict]) -> Dict[str, Optional[Decimal]]:
        """손익계산서/현금흐름표 지표 합산"""
        result = {}

        for metric in self.SUM_METRICS:
            values = []
            for q in quarters:
                val = q.get(metric)
                if val is not None:
                    try:
                        values.append(Decimal(str(val)))
                    except (ValueError, TypeError):
                        pass

            if len(values) == len(quarters) and len(quarters) == 4:
                result[metric] = sum(values)
            elif values:
                # 부분 데이터: 비율 조정하여 연환산 추정
                result[metric] = sum(values) * Decimal(4) / Decimal(len(values))
                logger.debug(f"Metric {metric}: annualized from {len(values)} quarters")
            else:
                result[metric] = None

        return result

    def _get_point_in_time_metrics(self, quarters: List[Dict]) -> Dict[str, Optional[Decimal]]:
        """재무상태표 지표 (최신 분기 값)"""
        result = {}

        if not quarters:
            return result

        # 최신 분기 (첫 번째)
        latest = quarters[0]

        for metric in self.POINT_IN_TIME_METRICS:
            val = latest.get(metric)
            if val is not None:
                try:
                    result[metric] = Decimal(str(val))
                except (ValueError, TypeError):
                    result[metric] = None
            else:
                result[metric] = None

        return result

    def _calculate_derived_ratios(
        self,
        sum_metrics: Dict[str, Optional[Decimal]],
        point_metrics: Dict[str, Optional[Decimal]],
        quarters: List[Dict]
    ) -> Dict[str, Optional[float]]:
        """파생 비율 계산"""
        ratios = {}

        # 평균 자산/자본 계산 (첫 분기와 마지막 분기의 평균)
        avg_equity = self._calculate_average_balance(quarters, 'total_equity')
        avg_assets = self._calculate_average_balance(quarters, 'total_assets')

        net_income_ttm = sum_metrics.get('net_income')
        operating_profit_ttm = sum_metrics.get('operating_profit')
        revenue_ttm = sum_metrics.get('revenue')
        total_liabilities = point_metrics.get('total_liabilities')
        total_equity = point_metrics.get('total_equity')

        # ROE (TTM)
        if net_income_ttm and avg_equity and avg_equity > 0:
            ratios['roe_ttm'] = round(float(net_income_ttm / avg_equity), 4)

        # ROA (TTM)
        if net_income_ttm and avg_assets and avg_assets > 0:
            ratios['roa_ttm'] = round(float(net_income_ttm / avg_assets), 4)

        # Operating Margin (TTM)
        if operating_profit_ttm and revenue_ttm and revenue_ttm > 0:
            ratios['operating_margin_ttm'] = round(float(operating_profit_ttm / revenue_ttm), 4)

        # Net Margin (TTM)
        if net_income_ttm and revenue_ttm and revenue_ttm > 0:
            ratios['net_margin_ttm'] = round(float(net_income_ttm / revenue_ttm), 4)

        # Debt Ratio
        if total_liabilities and total_equity and total_equity > 0:
            ratios['debt_ratio'] = round(float(total_liabilities / total_equity), 4)

        return ratios

    def _calculate_average_balance(
        self,
        quarters: List[Dict],
        metric: str
    ) -> Optional[Decimal]:
        """기초/기말 평균 계산"""
        if len(quarters) < 2:
            if quarters and quarters[0].get(metric) is not None:
                return Decimal(str(quarters[0][metric]))
            return None

        latest = quarters[0].get(metric)
        oldest = quarters[-1].get(metric)

        if latest is not None and oldest is not None:
            try:
                return (Decimal(str(latest)) + Decimal(str(oldest))) / Decimal(2)
            except (ValueError, TypeError):
                pass

        return None

    def _calculate_completeness(
        self,
        quarters: List[Dict],
        sum_metrics: Dict[str, Optional[Decimal]]
    ) -> float:
        """데이터 완성도 계산 (0.0 ~ 1.0)"""
        # 분기 수 기준 (4분기 = 100%)
        quarter_score = min(len(quarters) / 4.0, 1.0)

        # 핵심 지표 존재 여부
        core_metrics = ['revenue', 'net_income', 'operating_profit']
        core_count = sum(1 for m in core_metrics if sum_metrics.get(m) is not None)
        metric_score = core_count / len(core_metrics)

        # 가중 평균 (분기 수 60%, 지표 완성도 40%)
        completeness = quarter_score * 0.6 + metric_score * 0.4

        return round(completeness, 2)

    def _format_quarters_included(self, quarters: List[Dict]) -> List[str]:
        """포함된 분기 목록 포맷팅"""
        result = []

        for q in quarters:
            year = q.get('fiscal_year')
            quarter = q.get('quarter')
            d = q.get('date')

            if year and quarter:
                result.append(f"{year}Q{quarter}")
            elif d:
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                if isinstance(d, date):
                    q_num = (d.month - 1) // 3 + 1
                    result.append(f"{d.year}Q{q_num}")

        return result

    def validate_quarterly_continuity(
        self,
        quarters: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        분기 연속성 검증

        Returns:
            (is_continuous, missing_quarters)
        """
        if len(quarters) < 4:
            return False, [f"Only {len(quarters)} quarters available"]

        # 분기 추출 및 정렬
        quarter_set = set()
        for q in quarters[:4]:  # 최근 4분기만
            year = q.get('fiscal_year')
            qtr = q.get('quarter')
            if year and qtr:
                quarter_set.add((year, qtr))

        if len(quarter_set) < 4:
            return False, ["Incomplete quarter data"]

        # 연속성 검사
        sorted_quarters = sorted(quarter_set, reverse=True)
        missing = []

        for i in range(len(sorted_quarters) - 1):
            curr_year, curr_q = sorted_quarters[i]
            next_year, next_q = sorted_quarters[i + 1]

            # 예상되는 이전 분기
            expected_q = curr_q - 1 if curr_q > 1 else 4
            expected_year = curr_year if curr_q > 1 else curr_year - 1

            if (next_year, next_q) != (expected_year, expected_q):
                missing.append(f"{expected_year}Q{expected_q}")

        return len(missing) == 0, missing
