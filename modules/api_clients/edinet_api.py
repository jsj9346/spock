"""
EDINET API Client - JP Financial Data Source

EDINET (Electronic Disclosure for Investors' NETwork) API 클라이언트.
일본 금융청(FSA)에 제출된 기업 재무 데이터를 수집합니다.

주요 기능:
- 문서 목록 조회 (날짜별)
- XBRL 문서 다운로드 및 파싱
- 有価証券報告書 (연간), 四半期報告書 (분기) 지원
- Rate limiting: ~1 req/sec

API 특징:
- API Key 필요 (무료 등록: https://disclosure2.edinet-fsa.go.jp/)
- Subscription-Key 헤더로 인증
- ZIP 파일 내 XBRL 데이터 파싱

Author: Quant Platform Development Team
Date: 2025-11-26
"""

import zipfile
import io
import time
import logging
import requests
from xml.etree import ElementTree
from typing import Dict, List, Optional, Any
from datetime import date, datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EDINETFundamentalData:
    """EDINET에서 추출한 재무 데이터 구조"""
    ticker: str
    edinet_code: str
    region: str = "JP"
    fiscal_year: int = 0
    fiscal_period: str = "FY"  # FY (Annual) or Q1/Q2/Q3/Q4
    period_type: str = "ANNUAL"
    report_date: Optional[date] = None
    filed_date: Optional[date] = None
    data_source: str = "EDINET"
    doc_id: Optional[str] = None

    # Income Statement (損益計算書)
    revenue: Optional[float] = None  # 売上高
    gross_profit: Optional[float] = None  # 売上総利益
    operating_profit: Optional[float] = None  # 営業利益
    net_income: Optional[float] = None  # 当期純利益
    ebitda: Optional[float] = None

    # Balance Sheet (貸借対照表)
    total_assets: Optional[float] = None  # 総資産
    total_liabilities: Optional[float] = None  # 負債合計
    total_equity: Optional[float] = None  # 純資産
    current_assets: Optional[float] = None  # 流動資産
    current_liabilities: Optional[float] = None  # 流動負債
    inventory: Optional[float] = None  # 棚卸資産
    pp_e: Optional[float] = None  # 有形固定資産
    accounts_receivable: Optional[float] = None  # 売掛金

    # Cash Flow (キャッシュフロー計算書)
    operating_cash_flow: Optional[float] = None  # 営業CF
    investing_cf: Optional[float] = None  # 投資CF
    financing_cf: Optional[float] = None  # 財務CF
    capex: Optional[float] = None
    fcf: Optional[float] = None

    # Per Share (1株当たり)
    trailing_eps: Optional[float] = None  # 1株当たり当期純利益
    shares_outstanding: Optional[float] = None  # 発行済株式数

    # Equity Breakdown
    capital_stock: Optional[float] = None  # 資本金
    retained_earnings: Optional[float] = None  # 利益剰余金

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
            'total_assets': self.total_assets,
            'total_liabilities': self.total_liabilities,
            'total_equity': self.total_equity,
            'current_assets': self.current_assets,
            'current_liabilities': self.current_liabilities,
            'inventory': self.inventory,
            'pp_e': self.pp_e,
            'accounts_receivable': self.accounts_receivable,
            'operating_cash_flow': self.operating_cash_flow,
            'investing_cf': self.investing_cf,
            'financing_cf': self.financing_cf,
            'capex': self.capex,
            'fcf': self.fcf,
            'trailing_eps': self.trailing_eps,
            'shares_outstanding': self.shares_outstanding,
            'capital_stock': self.capital_stock,
            'retained_earnings': self.retained_earnings,
        }


class EDINETApiClient:
    """
    EDINET API 클라이언트

    일본 기업의 재무 데이터를 EDINET에서 수집합니다.
    XBRL 형식의 有価証券報告書를 파싱하여 재무 지표를 추출합니다.

    사용 예시:
        api = EDINETApiClient(api_key="your-subscription-key")

        # 연간 재무 데이터 조회
        fundamentals = api.get_historical_fundamentals("7203", start_year=2020, end_year=2024)
        for data in fundamentals:
            print(f"{data.fiscal_year}: Revenue={data.revenue:,.0f}")
    """

    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"

    # 문서 유형 코드
    DOC_TYPE_CODES = {
        '120': '有価証券報告書',  # Annual Report
        '130': '四半期報告書',     # Quarterly Report
        '140': '半期報告書',       # Semi-Annual Report
    }

    # JP-GAAP/IFRS XBRL Taxonomy 매핑
    XBRL_NAMESPACES = {
        'jpcrp': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2023-02-01/jpcrp_cor',
        'jppfs': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-02-01/jppfs_cor',
        'jpigp': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2023-02-01/jpigp_cor',
        'xbrli': 'http://www.xbrl.org/2003/instance',
        'ix': 'http://www.xbrl.org/2013/inlineXBRL',
    }

    # XBRL 태그 매핑 (複数の可能なタグ名)
    XBRL_TAGS = {
        # Income Statement (損益計算書)
        'revenue': [
            'NetSales',
            'OperatingRevenuesOrdinaryRevenuesAndNOIOrdinary',
            'RevenuesFromOperations',
            'NetSalesOfFinishedGoodsAndSalesOfMerchandise',
        ],
        'gross_profit': ['GrossProfit', 'GrossProfitOnSales'],
        'operating_profit': [
            'OperatingIncome',
            'OperatingProfit',
            'OperatingIncomeIFRS',
        ],
        'net_income': [
            'ProfitLossAttributableToOwnersOfParent',
            'ProfitLoss',
            'NetIncome',
            'NetIncomeAttributableToOwnersOfTheParent',
        ],

        # Balance Sheet (貸借対照表)
        'total_assets': ['TotalAssets', 'Assets'],
        'total_liabilities': ['Liabilities', 'TotalLiabilities'],
        'total_equity': [
            'NetAssets',
            'Equity',
            'TotalEquity',
            'TotalNetAssets',
        ],
        'current_assets': ['CurrentAssets'],
        'current_liabilities': ['CurrentLiabilities'],
        'inventory': ['Inventories', 'MerchandiseAndFinishedGoods'],
        'pp_e': [
            'PropertyPlantAndEquipment',
            'PropertyPlantAndEquipmentNet',
            'TangibleFixedAssets',
        ],
        'accounts_receivable': [
            'NotesAndAccountsReceivableTrade',
            'AccountsReceivableTrade',
        ],

        # Cash Flow (キャッシュフロー計算書)
        'operating_cash_flow': [
            'NetCashProvidedByUsedInOperatingActivities',
            'CashFlowsFromUsedInOperatingActivities',
        ],
        'investing_cf': [
            'NetCashProvidedByUsedInInvestingActivities',
            'CashFlowsFromUsedInInvestingActivities',
        ],
        'financing_cf': [
            'NetCashProvidedByUsedInFinancingActivities',
            'CashFlowsFromUsedInFinancingActivities',
        ],

        # Per Share (1株当たり)
        'trailing_eps': [
            'BasicEarningsLossPerShare',
            'EarningsPerShare',
        ],
        'shares_outstanding': [
            'NumberOfIssuedSharesAsOfFilingDateCommonStock',
            'IssuedSharesTotalNumberOfSharesIssued',
            'TotalNumberOfIssuedShares',
        ],

        # Equity Breakdown
        'capital_stock': ['CapitalStock', 'ShareCapital'],
        'retained_earnings': [
            'RetainedEarnings',
            'RetainedEarningsBroughtForward',
        ],
    }

    def __init__(
        self,
        api_key: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3
    ):
        """
        EDINET API 클라이언트 초기화

        Args:
            api_key: EDINET Subscription-Key (https://disclosure2.edinet-fsa.go.jp/ 에서 무료 발급)
            rate_limit_delay: API 호출 간 지연 시간 (초, 기본 1초)
            max_retries: 실패 시 최대 재시도 횟수
        """
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries

        self.session = requests.Session()
        self.session.headers.update({
            'Ocp-Apim-Subscription-Key': api_key,  # EDINET v2 헤더
            'Accept': 'application/json',
        })

        self._last_request_time: float = 0

        logger.info(f"🇯🇵 EDINETApiClient 초기화 (rate: {1/rate_limit_delay:.1f} req/s)")

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
        params: Optional[Dict] = None,
        stream: bool = False
    ) -> Optional[requests.Response]:
        """
        재시도 로직이 포함된 HTTP GET 요청

        Args:
            url: 요청 URL
            params: 쿼리 파라미터
            stream: 스트림 모드 (대용량 파일 다운로드용)

        Returns:
            Response 객체 또는 None
        """
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()

                response = self.session.get(url, params=params, stream=stream, timeout=60)
                response.raise_for_status()

                return response

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.debug(f"리소스 없음 (404): {url}")
                    return None
                elif e.response.status_code == 429:
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

    def validate_connection(self) -> bool:
        """
        EDINET API 연결 검증

        Returns:
            연결 성공 여부
        """
        try:
            # 오늘 날짜로 문서 목록 조회 테스트
            test_date = date.today()
            url = f"{self.BASE_URL}/documents.json"
            params = {
                'date': test_date.strftime('%Y-%m-%d'),
                'type': 2
            }

            response = self._request_with_retry(url, params)
            if response:
                data = response.json()
                logger.info(f"✅ EDINET API 연결 성공 (오늘 문서: {len(data.get('results', []))}개)")
                return True
            return False

        except Exception as e:
            logger.error(f"EDINET API 연결 실패: {e}")
            return False

    def get_document_list(
        self,
        target_date: date,
        doc_type: int = 2
    ) -> List[Dict]:
        """
        특정 날짜에 제출된 문서 목록 조회

        Args:
            target_date: 대상 날짜
            doc_type: 1=메타데이터만, 2=제출서류일람

        Returns:
            문서 메타데이터 목록
        """
        url = f"{self.BASE_URL}/documents.json"
        params = {
            'date': target_date.strftime('%Y-%m-%d'),
            'type': doc_type
        }

        response = self._request_with_retry(url, params)
        if not response:
            return []

        try:
            data = response.json()
            results = data.get('results', [])
            logger.debug(f"[{target_date}] {len(results)}개 문서 조회")
            return results

        except Exception as e:
            logger.error(f"문서 목록 파싱 실패: {e}")
            return []

    def get_annual_reports(
        self,
        target_date: date
    ) -> List[Dict]:
        """
        특정 날짜에 제출된 有価証券報告書 (Annual Report) 목록

        Args:
            target_date: 대상 날짜

        Returns:
            연간 보고서 문서 목록
        """
        documents = self.get_document_list(target_date)

        # docTypeCode = 120 (有価証券報告書) 필터링
        annual_reports = [
            doc for doc in documents
            if doc.get('docTypeCode') == '120'
        ]

        return annual_reports

    def download_document(self, doc_id: str) -> Optional[bytes]:
        """
        문서 ZIP 파일 다운로드

        Args:
            doc_id: 문서 ID (예: 'S100ABCD')

        Returns:
            ZIP 파일 바이트 또는 None
        """
        url = f"{self.BASE_URL}/documents/{doc_id}"
        params = {'type': 1}  # 1 = 제출본문서 및 감사보고서

        response = self._request_with_retry(url, params, stream=True)
        if not response:
            return None

        return response.content

    def parse_xbrl_from_zip(self, zip_bytes: bytes) -> Dict[str, Any]:
        """
        ZIP 아카이브에서 XBRL 데이터 파싱

        Args:
            zip_bytes: ZIP 파일 내용

        Returns:
            추출된 재무 데이터 딕셔너리
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
                # XBRL 인스턴스 파일 찾기 (.xbrl 우선, .htm은 백업)
                xbrl_files = []
                ixbrl_files = []

                for f in z.namelist():
                    # PublicDoc 폴더 내의 XBRL/iXBRL 파일
                    if 'PublicDoc' in f:
                        if f.endswith('.xbrl'):
                            xbrl_files.append(f)
                        elif f.endswith('.htm') and 'ixbrl' in f.lower():
                            ixbrl_files.append(f)

                # .xbrl 파일 우선, 없으면 iXBRL 사용
                target_files = xbrl_files if xbrl_files else ixbrl_files

                if not target_files:
                    # PublicDoc이 없으면 전체에서 검색
                    target_files = [
                        f for f in z.namelist()
                        if f.endswith('.xbrl')
                    ]

                if not target_files:
                    logger.warning("ZIP 내 XBRL 파일 없음")
                    return {}

                # XBRL 파일 파싱
                logger.debug(f"XBRL 파일 파싱: {target_files[0]}")
                xbrl_content = z.read(target_files[0])
                return self._parse_xbrl_content(xbrl_content)

        except zipfile.BadZipFile:
            logger.error("잘못된 ZIP 파일")
            return {}
        except Exception as e:
            logger.error(f"ZIP 파싱 실패: {e}")
            return {}

    def _parse_xbrl_content(self, xbrl_content: bytes) -> Dict[str, Any]:
        """
        XBRL XML 내용 파싱

        Args:
            xbrl_content: XBRL 파일 내용

        Returns:
            추출된 재무 지표 딕셔너리
        """
        try:
            # XML 파싱 (UTF-8 또는 SHIFT-JIS)
            try:
                content_str = xbrl_content.decode('utf-8')
            except UnicodeDecodeError:
                content_str = xbrl_content.decode('shift-jis', errors='replace')

            root = ElementTree.fromstring(content_str.encode('utf-8'))

            extracted = {}

            # 각 메트릭 추출
            for metric_name, tags in self.XBRL_TAGS.items():
                for tag in tags:
                    # 다양한 네임스페이스에서 검색
                    value = self._find_tag_value(root, tag)
                    if value is not None:
                        extracted[metric_name] = value
                        break

            # FCF 계산 (Operating CF - CapEx)
            if 'operating_cash_flow' in extracted:
                capex = extracted.get('capex', 0) or 0
                extracted['fcf'] = extracted['operating_cash_flow'] - abs(capex)

            return extracted

        except ElementTree.ParseError as e:
            logger.error(f"XML 파싱 에러: {e}")
            return {}
        except Exception as e:
            logger.error(f"XBRL 내용 파싱 실패: {e}")
            return {}

    def _find_tag_value(self, root: ElementTree.Element, tag_name: str) -> Optional[float]:
        """
        XML 트리에서 태그 값 찾기

        여러 네임스페이스와 속성을 고려하여 검색합니다.
        """
        # 직접 태그 검색
        for element in root.iter():
            local_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag

            if local_name == tag_name or tag_name.lower() in local_name.lower():
                if element.text:
                    try:
                        # 숫자 변환 (콤마 제거)
                        value_str = element.text.replace(',', '').replace(' ', '')
                        return float(value_str)
                    except ValueError:
                        continue

        return None

    def get_historical_fundamentals(
        self,
        ticker: str,
        start_year: int = 2020,
        end_year: int = 2024,
        period_type: str = "ANNUAL"
    ) -> List[EDINETFundamentalData]:
        """
        기업의 역사적 재무 데이터 추출

        일본 기업의 有価証券報告書를 검색하여 재무 데이터를 추출합니다.
        대부분의 일본 기업은 3월 결산이며, 6월에 유가증권보고서를 제출합니다.

        Args:
            ticker: JP 주식 티커 (4자리, 예: '7203' = 토요타)
            start_year: 시작 연도
            end_year: 종료 연도
            period_type: 'ANNUAL' (有価証券報告書)

        Returns:
            연도별 재무 데이터 리스트
        """
        results = []

        # 연도별로 유가증권보고서 검색
        for year in range(start_year, end_year + 1):
            # 대부분의 일본 기업은 3월 결산, 6월에 보고서 제출
            # 4월~7월 사이 검색
            search_start = date(year, 4, 1)
            search_end = date(year, 8, 31)

            found_report = False
            current_date = search_start

            while current_date <= search_end and not found_report:
                # 해당 날짜의 유가증권보고서 목록 조회
                annual_reports = self.get_annual_reports(current_date)

                for doc in annual_reports:
                    # 증권코드 확인 (5자리 중 앞 4자리)
                    sec_code_raw = doc.get('secCode')
                    if not sec_code_raw:
                        continue  # secCode가 없는 문서(펀드 등)는 건너뛰기

                    sec_code = sec_code_raw[:4]

                    if sec_code != ticker:
                        continue

                    logger.info(f"[{ticker}] {year}년 유가증권보고서 발견 ({current_date})")

                    # 문서 다운로드 및 파싱
                    doc_id = doc.get('docID')
                    zip_content = self.download_document(doc_id)

                    if not zip_content:
                        logger.warning(f"[{ticker}] 문서 다운로드 실패: {doc_id}")
                        continue

                    metrics = self.parse_xbrl_from_zip(zip_content)

                    if metrics:
                        # EDINETFundamentalData 객체 생성
                        data = EDINETFundamentalData(
                            ticker=ticker,
                            edinet_code=doc.get('edinetCode', ''),
                            region="JP",
                            fiscal_year=year - 1,  # 보고서는 전년도 회계연도용
                            period_type="ANNUAL",
                            report_date=date(year - 1, 3, 31),  # 3월 결산 가정
                            filed_date=current_date,
                            data_source="EDINET",
                            doc_id=doc_id,
                            **{k: v for k, v in metrics.items() if hasattr(EDINETFundamentalData, k)}
                        )

                        results.append(data)
                        found_report = True
                        logger.info(f"[{ticker}] {year-1}년 데이터 추출 완료")
                        break

                current_date += timedelta(days=1)

            if not found_report:
                logger.debug(f"[{ticker}] {year}년 유가증권보고서 없음")

        logger.info(f"[{ticker}] {len(results)}년치 EDINET 데이터 추출 완료 ({start_year}-{end_year})")
        return results

    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()
            self.session = None
            logger.info("🔒 EDINET 세션 종료")


# 테스트 코드
if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("EDINET API 클라이언트 테스트")
    print("=" * 80)

    # API 키 확인
    api_key = os.getenv("EDINET_API_KEY")
    if not api_key:
        print("❌ EDINET_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   https://disclosure2.edinet-fsa.go.jp/ 에서 무료로 발급받으세요.")
        exit(1)

    # API 클라이언트 초기화
    api = EDINETApiClient(
        api_key=api_key,
        rate_limit_delay=1.0
    )

    # 연결 테스트
    print("\n1. 연결 테스트...")
    if api.validate_connection():
        print("   ✅ EDINET API 연결 성공")
    else:
        print("   ❌ EDINET API 연결 실패")
        exit(1)

    # 문서 목록 조회 테스트
    print("\n2. 오늘 문서 목록 조회...")
    documents = api.get_document_list(date.today())
    print(f"   ✅ {len(documents)}개 문서 조회")

    # 유가증권보고서 필터링
    annual_reports = [d for d in documents if d.get('docTypeCode') == '120']
    print(f"   📊 有価証券報告書: {len(annual_reports)}개")

    # 세션 종료
    api.close()

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)
