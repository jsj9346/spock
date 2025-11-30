"""
SEC EDGAR API Client - US Financial Data Source

SEC EDGAR (Electronic Data Gathering, Analysis, and Retrieval) API 클라이언트.
미국 증권거래위원회(SEC)에 제출된 기업 재무 데이터를 수집합니다.

주요 기능:
- CIK(Central Index Key) 매핑: ticker → CIK 변환
- Company Facts API: XBRL 기반 재무 데이터 조회
- 10-K/20-F (연간 보고서), 10-Q/6-K (분기 보고서) 지원
- ADR/외국 기업 양식(20-F, 6-K) 자동 포함
- Rate limiting: 10 req/sec (SEC 권장)
- 자동 재시도 및 에러 처리

API 특징:
- 인증 불필요 (무료)
- User-Agent 헤더 필수 (이메일 포함)
- XBRL→JSON 변환된 데이터 제공

Author: Quant Platform Development Team
Date: 2025-11-26
"""

import time
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import date, datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SECFundamentalData:
    """SEC EDGAR에서 추출한 재무 데이터 구조"""
    ticker: str
    cik: str
    region: str = "US"
    fiscal_year: int = 0
    fiscal_period: str = "FY"  # FY (Annual) or Q1/Q2/Q3/Q4
    period_type: str = "ANNUAL"
    report_date: Optional[date] = None
    filed_date: Optional[date] = None
    data_source: str = "SEC_EDGAR"

    # Income Statement
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    net_income: Optional[float] = None
    ebitda: Optional[float] = None
    cogs: Optional[float] = None
    sga_expense: Optional[float] = None

    # Balance Sheet
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    inventory: Optional[float] = None
    pp_e: Optional[float] = None
    accounts_receivable: Optional[float] = None
    cash_and_equivalents: Optional[float] = None

    # Cash Flow
    operating_cash_flow: Optional[float] = None
    investing_cf: Optional[float] = None
    financing_cf: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None

    # Per Share & Equity Breakdown
    trailing_eps: Optional[float] = None
    shares_outstanding: Optional[float] = None
    capital_stock: Optional[float] = None
    retained_earnings: Optional[float] = None
    treasury_stock: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (데이터베이스 INSERT용)"""
        return {
            'ticker': self.ticker,
            'region': self.region,
            'date': self.report_date,
            'period_type': self.period_type,
            'fiscal_year': self.fiscal_year,
            'data_source': self.data_source,
            'revenue': self.revenue,
            'gross_profit': self.gross_profit,
            'operating_profit': self.operating_profit,
            'net_income': self.net_income,
            'ebitda': self.ebitda,
            'cogs': self.cogs,
            'sga_expense': self.sga_expense,
            'total_assets': self.total_assets,
            'total_liabilities': self.total_liabilities,
            'total_equity': self.total_equity,
            'current_assets': self.current_assets,
            'current_liabilities': self.current_liabilities,
            'inventory': self.inventory,
            'pp_e': self.pp_e,
            'accounts_receivable': self.accounts_receivable,
            'cash_and_equivalents': self.cash_and_equivalents,
            'operating_cash_flow': self.operating_cash_flow,
            'investing_cf': self.investing_cf,
            'financing_cf': self.financing_cf,
            'capex': self.capex,
            'fcf': self.fcf,
            'trailing_eps': self.trailing_eps,
            'shares_outstanding': self.shares_outstanding,
            'capital_stock': self.capital_stock,
            'retained_earnings': self.retained_earnings,
            'treasury_stock': self.treasury_stock,
        }


class SECEdgarApiClient:
    """
    SEC EDGAR API 클라이언트

    US-GAAP XBRL 데이터를 JSON 형식으로 제공하는 SEC API를 활용합니다.

    사용 예시:
        api = SECEdgarApiClient(user_agent="MyApp/1.0 (email@example.com)")

        # CIK 조회
        cik = api.get_cik("AAPL")

        # 재무 데이터 조회
        fundamentals = api.get_historical_fundamentals("AAPL", start_year=2020, end_year=2024)
        for data in fundamentals:
            print(f"{data.fiscal_year}: Revenue={data.revenue:,.0f}")
    """

    BASE_URL = "https://data.sec.gov"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    # US-GAAP XBRL 태그 매핑 (여러 변형 태그 지원)
    XBRL_TAGS = {
        # Income Statement
        'revenue': [
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'RevenueFromContractWithCustomerIncludingAssessedTax',
            'SalesRevenueNet',
            'SalesRevenueGoodsNet',
            'TotalRevenuesAndOtherIncome',
        ],
        'gross_profit': ['GrossProfit'],
        'operating_profit': [
            'OperatingIncomeLoss',
            'IncomeLossFromOperations',
        ],
        'net_income': [
            'NetIncomeLoss',
            'NetIncomeLossAvailableToCommonStockholdersBasic',
            'ProfitLoss',
        ],
        'cogs': [
            'CostOfRevenue',
            'CostOfGoodsAndServicesSold',
            'CostOfGoodsSold',
        ],
        'sga_expense': [
            'SellingGeneralAndAdministrativeExpense',
            'GeneralAndAdministrativeExpense',
        ],

        # Balance Sheet
        'total_assets': ['Assets'],
        'total_liabilities': ['Liabilities'],
        'total_equity': [
            'StockholdersEquity',
            'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
        ],
        'current_assets': ['AssetsCurrent'],
        'current_liabilities': ['LiabilitiesCurrent'],
        'inventory': ['InventoryNet', 'Inventories'],
        'pp_e': [
            'PropertyPlantAndEquipmentNet',
            'PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization',
        ],
        'accounts_receivable': [
            'AccountsReceivableNetCurrent',
            'ReceivablesNetCurrent',
        ],
        'cash_and_equivalents': [
            'CashAndCashEquivalentsAtCarryingValue',
            'Cash',
        ],

        # Cash Flow
        'operating_cash_flow': [
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
        ],
        'investing_cf': [
            'NetCashProvidedByUsedInInvestingActivities',
            'NetCashProvidedByUsedInInvestingActivitiesContinuingOperations',
        ],
        'financing_cf': [
            'NetCashProvidedByUsedInFinancingActivities',
            'NetCashProvidedByUsedInFinancingActivitiesContinuingOperations',
        ],
        'capex': [
            'PaymentsToAcquirePropertyPlantAndEquipment',
            'PaymentsToAcquireProductiveAssets',
        ],

        # Per Share
        'trailing_eps': [
            'EarningsPerShareBasic',
            'EarningsPerShareDiluted',
        ],
        'shares_outstanding': [
            'CommonStockSharesOutstanding',
            'WeightedAverageNumberOfSharesOutstandingBasic',
        ],

        # Equity Breakdown
        'capital_stock': [
            'CommonStockValue',
            'CommonStockValueOutstanding',
        ],
        'retained_earnings': [
            'RetainedEarningsAccumulatedDeficit',
        ],
        'treasury_stock': [
            'TreasuryStockValue',
            'TreasuryStockCommonValue',
        ],
    }

    def __init__(
        self,
        user_agent: str = "SpockQuantPlatform/1.0 (quant@spock.dev)",
        rate_limit_delay: float = 0.1,
        max_retries: int = 3
    ):
        """
        SEC EDGAR API 클라이언트 초기화

        Args:
            user_agent: SEC API 요청에 필요한 User-Agent (이메일 포함 권장)
            rate_limit_delay: API 호출 간 지연 시간 (초, 기본 100ms)
            max_retries: 실패 시 최대 재시도 횟수
        """
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json',
        })

        # CIK 매핑 캐시
        self._cik_map: Optional[Dict[str, str]] = None
        self._last_request_time: float = 0

        logger.info(f"🇺🇸 SECEdgarApiClient 초기화 (rate: {1/rate_limit_delay:.1f} req/s)")

    def _rate_limit(self):
        """Rate limiting 적용"""
        if self.rate_limit_delay <= 0:
            return

        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        self._last_request_time = time.time()

    def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        재시도 로직이 포함된 HTTP GET 요청

        Args:
            url: 요청 URL
            params: 쿼리 파라미터

        Returns:
            JSON 응답 또는 None
        """
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                return response.json()

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.debug(f"리소스 없음 (404): {url}")
                    return None
                elif e.response.status_code == 429:
                    # Rate limit exceeded
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limit 초과, {wait_time}초 대기 중...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP 에러 {e.response.status_code}: {url}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)

            except requests.exceptions.RequestException as e:
                logger.error(f"요청 실패: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"예상치 못한 에러: {e}")
                return None

        return None

    def load_cik_mapping(self) -> Dict[str, str]:
        """
        SEC에서 ticker → CIK 매핑 로드

        Returns:
            {ticker: cik} 딕셔너리
        """
        if self._cik_map is not None:
            return self._cik_map

        logger.info("📥 SEC ticker→CIK 매핑 로드 중...")

        try:
            data = self._request_with_retry(self.TICKERS_URL)

            if not data:
                logger.error("CIK 매핑 로드 실패")
                return {}

            # ticker → CIK 매핑 구성 (CIK는 10자리로 패딩)
            self._cik_map = {}
            for entry in data.values():
                ticker = entry['ticker'].upper()
                cik = str(entry['cik_str']).zfill(10)
                self._cik_map[ticker] = cik

            logger.info(f"✅ {len(self._cik_map):,}개 ticker→CIK 매핑 로드 완료")
            return self._cik_map

        except Exception as e:
            logger.error(f"CIK 매핑 로드 실패: {e}")
            return {}

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Ticker에 해당하는 CIK 조회

        Args:
            ticker: US 주식 티커 (예: 'AAPL')

        Returns:
            10자리 CIK 문자열 또는 None
        """
        cik_map = self.load_cik_mapping()
        return cik_map.get(ticker.upper())

    def get_company_facts(self, cik: str) -> Optional[Dict]:
        """
        기업의 모든 XBRL 데이터 조회

        SEC Company Facts API는 해당 기업의 모든 역사적 재무 데이터를
        XBRL 형식으로 제공합니다.

        Args:
            cik: 10자리 CIK

        Returns:
            XBRL 데이터 딕셔너리 또는 None
        """
        url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"

        data = self._request_with_retry(url)

        if data:
            logger.debug(f"CIK {cik} 재무 데이터 조회 성공")

        return data

    def _extract_metric_value(
        self,
        us_gaap: Dict,
        metric_name: str,
        target_year: int,
        form_type: str = "10-K"
    ) -> Optional[float]:
        """
        US-GAAP 데이터에서 특정 메트릭 값 추출

        Args:
            us_gaap: US-GAAP XBRL 데이터
            metric_name: 추출할 메트릭 이름
            target_year: 대상 회계연도
            form_type: 보고서 유형 ('10-K' 또는 '10-Q')

        Returns:
            메트릭 값 또는 None
        """
        xbrl_tags = self.XBRL_TAGS.get(metric_name, [])

        for tag in xbrl_tags:
            if tag not in us_gaap:
                continue

            units = us_gaap[tag].get('units', {})

            # USD 또는 shares 단위 확인
            values = units.get('USD', units.get('USD/shares', units.get('shares', [])))

            if not values:
                continue

            # 해당 연도의 값 찾기 (가장 최근 제출된 것 우선)
            best_match = None
            best_filed_date = ""

            for entry in values:
                form = entry.get('form', '')

                # 보고서 유형 필터링 (ADR/외국기업 양식 포함)
                # 미국 국내 기업: 10-K (연간), 10-Q (분기)
                # 외국 기업/ADR: 20-F (연간), 6-K (분기/임시)
                if form_type == "10-K" and form not in ("10-K", "20-F"):
                    continue
                if form_type == "10-Q" and form not in ("10-Q", "6-K"):
                    continue

                # 날짜에서 연도 추출
                end_date = entry.get('end', '')
                if not end_date:
                    continue

                try:
                    entry_year = int(end_date[:4])
                except (ValueError, IndexError):
                    continue

                if entry_year != target_year:
                    continue

                # 가장 최근 제출된 값 사용
                filed_date = entry.get('filed', '')
                if filed_date > best_filed_date:
                    best_match = entry.get('val')
                    best_filed_date = filed_date

            if best_match is not None:
                return float(best_match)

        return None

    def get_historical_fundamentals(
        self,
        ticker: str,
        start_year: int = 2020,
        end_year: int = 2024,
        period_type: str = "ANNUAL"
    ) -> List[SECFundamentalData]:
        """
        기업의 역사적 재무 데이터 추출

        Args:
            ticker: US 주식 티커 (예: 'AAPL')
            start_year: 시작 연도
            end_year: 종료 연도
            period_type: 'ANNUAL' (10-K) 또는 'QUARTERLY' (10-Q)

        Returns:
            연도별 재무 데이터 리스트
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"[{ticker}] CIK를 찾을 수 없음")
            return []

        facts = self.get_company_facts(cik)
        if not facts:
            logger.warning(f"[{ticker}] Company Facts 데이터 없음")
            return []

        # US-GAAP 데이터 추출
        us_gaap = facts.get('facts', {}).get('us-gaap', {})

        if not us_gaap:
            logger.warning(f"[{ticker}] US-GAAP 데이터 없음")
            return []

        form_type = "10-K" if period_type == "ANNUAL" else "10-Q"
        results = []

        for year in range(start_year, end_year + 1):
            data = SECFundamentalData(
                ticker=ticker,
                cik=cik,
                region="US",
                fiscal_year=year,
                period_type=period_type,
                report_date=date(year, 12, 31),  # 대부분의 US 기업은 12월 결산
                data_source="SEC_EDGAR"
            )

            # 각 메트릭 추출
            metrics_found = 0
            for metric_name in self.XBRL_TAGS.keys():
                value = self._extract_metric_value(us_gaap, metric_name, year, form_type)
                if value is not None:
                    setattr(data, metric_name, value)
                    metrics_found += 1

            # FCF 계산 (Operating CF - CapEx)
            if data.operating_cash_flow and data.capex:
                data.fcf = data.operating_cash_flow - abs(data.capex)

            # Treasury Stock 부호 변환 (SEC는 양수로 보고, DB는 음수로 저장)
            # Treasury stock은 자본의 차감 항목이므로 음수여야 함
            if data.treasury_stock is not None and data.treasury_stock > 0:
                data.treasury_stock = -abs(data.treasury_stock)

            # 데이터가 있는 경우에만 추가
            if metrics_found > 0:
                results.append(data)
                logger.debug(f"[{ticker}] {year}년 데이터 추출: {metrics_found}개 메트릭")

        logger.info(f"[{ticker}] {len(results)}년치 SEC 데이터 추출 완료 ({start_year}-{end_year})")
        return results

    def _extract_quarterly_metric_value(
        self,
        us_gaap: Dict,
        metric_name: str,
        target_year: int,
        target_quarter: int
    ) -> Optional[float]:
        """
        US-GAAP 데이터에서 특정 분기의 메트릭 값 추출

        Args:
            us_gaap: US-GAAP XBRL 데이터
            metric_name: 추출할 메트릭 이름
            target_year: 대상 회계연도
            target_quarter: 대상 분기 (1, 2, 3, 4)

        Returns:
            메트릭 값 또는 None
        """
        xbrl_tags = self.XBRL_TAGS.get(metric_name, [])

        # 분기별 종료월 매핑 (대부분 기업이 12월 결산 가정)
        quarter_end_months = {1: 3, 2: 6, 3: 9, 4: 12}
        target_month = quarter_end_months.get(target_quarter)
        if not target_month:
            return None

        for tag in xbrl_tags:
            if tag not in us_gaap:
                continue

            units = us_gaap[tag].get('units', {})
            values = units.get('USD', units.get('USD/shares', units.get('shares', [])))

            if not values:
                continue

            best_match = None
            best_filed_date = ""

            for entry in values:
                form = entry.get('form', '')

                # 10-Q 또는 6-K(외국기업) 필터링
                if form not in ("10-Q", "6-K"):
                    continue

                end_date = entry.get('end', '')
                start_date = entry.get('start', '')
                if not end_date:
                    continue

                try:
                    end_year = int(end_date[:4])
                    end_month = int(end_date[5:7])

                    # 기간 확인 (분기 데이터는 약 3개월)
                    if start_date:
                        start_parts = start_date.split('-')
                        if len(start_parts) >= 2:
                            period_months = (end_year * 12 + end_month) - \
                                          (int(start_parts[0]) * 12 + int(start_parts[1]))
                            # 3~4개월 기간의 데이터만 (분기 데이터)
                            if period_months > 4:
                                continue
                except (ValueError, IndexError):
                    continue

                # 연도 및 분기 매칭
                if end_year != target_year:
                    continue

                # 분기 추정 (월 기준)
                if end_month <= 3:
                    estimated_quarter = 1
                elif end_month <= 6:
                    estimated_quarter = 2
                elif end_month <= 9:
                    estimated_quarter = 3
                else:
                    estimated_quarter = 4

                if estimated_quarter != target_quarter:
                    continue

                # 가장 최근 제출된 값 사용
                filed_date = entry.get('filed', '')
                if filed_date > best_filed_date:
                    best_match = entry.get('val')
                    best_filed_date = filed_date

            if best_match is not None:
                return float(best_match)

        return None

    def get_quarterly_fundamentals(
        self,
        ticker: str,
        start_year: int = 2023,
        end_year: int = 2024
    ) -> List[SECFundamentalData]:
        """
        기업의 분기별 재무 데이터 추출

        SEC 10-Q 보고서에서 분기별 데이터를 추출합니다.
        TTM 계산을 위해 최근 4분기 데이터가 필요합니다.

        Args:
            ticker: US 주식 티커 (예: 'AAPL')
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            분기별 재무 데이터 리스트
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"[{ticker}] CIK를 찾을 수 없음")
            return []

        facts = self.get_company_facts(cik)
        if not facts:
            logger.warning(f"[{ticker}] Company Facts 데이터 없음")
            return []

        us_gaap = facts.get('facts', {}).get('us-gaap', {})
        if not us_gaap:
            logger.warning(f"[{ticker}] US-GAAP 데이터 없음")
            return []

        results = []

        # 분기별 종료일 매핑
        quarter_end_dates = {
            1: (3, 31),   # Q1: 3월 31일
            2: (6, 30),   # Q2: 6월 30일
            3: (9, 30),   # Q3: 9월 30일
            4: (12, 31),  # Q4: 12월 31일
        }

        for year in range(start_year, end_year + 1):
            for quarter in range(1, 5):
                month, day = quarter_end_dates[quarter]

                data = SECFundamentalData(
                    ticker=ticker,
                    cik=cik,
                    region="US",
                    fiscal_year=year,
                    fiscal_period=f"Q{quarter}",
                    period_type="QUARTERLY",
                    report_date=date(year, month, day),
                    data_source="SEC_EDGAR"
                )

                # 각 메트릭 추출
                metrics_found = 0
                for metric_name in self.XBRL_TAGS.keys():
                    value = self._extract_quarterly_metric_value(
                        us_gaap, metric_name, year, quarter
                    )
                    if value is not None:
                        setattr(data, metric_name, value)
                        metrics_found += 1

                # FCF 계산
                if data.operating_cash_flow and data.capex:
                    data.fcf = data.operating_cash_flow - abs(data.capex)

                # Treasury Stock 부호 변환
                if data.treasury_stock is not None and data.treasury_stock > 0:
                    data.treasury_stock = -abs(data.treasury_stock)

                # 데이터가 있는 경우에만 추가
                if metrics_found > 0:
                    results.append(data)
                    logger.debug(f"[{ticker}] {year}Q{quarter} 데이터 추출: {metrics_found}개 메트릭")

        logger.info(f"[{ticker}] {len(results)}개 분기 SEC 데이터 추출 완료 ({start_year}-{end_year})")
        return results

    def validate_connection(self) -> bool:
        """
        SEC API 연결 검증

        Returns:
            연결 성공 여부
        """
        try:
            # CIK 매핑 로드로 연결 테스트
            cik_map = self.load_cik_mapping()
            return len(cik_map) > 0
        except Exception as e:
            logger.error(f"SEC API 연결 실패: {e}")
            return False

    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()
            self.session = None
            logger.info("🔒 SEC EDGAR 세션 종료")


# 테스트 코드
if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SEC EDGAR API 클라이언트 테스트")
    print("=" * 80)

    # API 클라이언트 초기화
    api = SECEdgarApiClient(
        user_agent="SpockQuantPlatform/1.0 (test@spock.dev)",
        rate_limit_delay=0.2
    )

    # 연결 테스트
    print("\n1. 연결 테스트...")
    if api.validate_connection():
        print("   ✅ SEC API 연결 성공")
    else:
        print("   ❌ SEC API 연결 실패")
        exit(1)

    # CIK 조회 테스트
    print("\n2. CIK 조회 테스트...")
    test_tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker in test_tickers:
        cik = api.get_cik(ticker)
        print(f"   {ticker}: CIK={cik}")

    # 재무 데이터 조회 테스트
    print("\n3. 재무 데이터 조회 테스트 (AAPL)...")
    fundamentals = api.get_historical_fundamentals(
        ticker="AAPL",
        start_year=2022,
        end_year=2024,
        period_type="ANNUAL"
    )

    if fundamentals:
        for data in fundamentals:
            print(f"\n   📊 {data.fiscal_year}년:")
            print(f"      Revenue:     ${data.revenue:>15,.0f}" if data.revenue else "      Revenue:     N/A")
            print(f"      Net Income:  ${data.net_income:>15,.0f}" if data.net_income else "      Net Income:  N/A")
            print(f"      Total Assets:${data.total_assets:>15,.0f}" if data.total_assets else "      Total Assets: N/A")
            print(f"      FCF:         ${data.fcf:>15,.0f}" if data.fcf else "      FCF:         N/A")
    else:
        print("   ⚠️ 재무 데이터 없음")

    # 세션 종료
    api.close()

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)
