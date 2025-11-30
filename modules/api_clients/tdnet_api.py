"""
TDnet (Timely Disclosure Network) API Client - JP Quarterly Financial Data

TDnet는 도쿄증권거래소(TSE)에서 운영하는 적시공시 시스템입니다.
일본 상장기업의 결산단신(決算短信)을 통해 분기별 재무 데이터를 제공합니다.

주요 기능:
- 결산단신(決算短信) PDF/XBRL 다운로드
- 분기별 재무 데이터 파싱
- TTM 계산을 위한 4분기 데이터 수집

데이터 소스:
- TDnet API (공식): https://www.release.tdnet.info/
- J-Quants API (대안): https://jpx-jquants.com/

참고: 일본 대기업들은 EDINET의 四半期報告書 대신 결산단신으로 분기 실적을 발표합니다.

Author: Quant Platform Development Team
Date: 2025-11-28
"""

import os
import re
import time
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import date, datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TDnetQuarterlyData:
    """TDnet에서 추출한 분기 재무 데이터"""
    ticker: str
    region: str = "JP"
    fiscal_year: int = 0
    fiscal_period: str = ""  # Q1, Q2, Q3, Q4
    period_type: str = "QUARTERLY"
    report_date: Optional[date] = None
    filed_date: Optional[date] = None
    data_source: str = "TDNET"

    # Income Statement (損益計算書) - 累計
    revenue: Optional[float] = None  # 売上高
    operating_profit: Optional[float] = None  # 営業利益
    ordinary_profit: Optional[float] = None  # 経常利益
    net_income: Optional[float] = None  # 当期純利益

    # Balance Sheet (貸借対照表)
    total_assets: Optional[float] = None  # 総資産
    total_equity: Optional[float] = None  # 純資産
    equity_ratio: Optional[float] = None  # 自己資本比率

    # Per Share
    eps: Optional[float] = None  # 1株当たり当期純利益
    dividend_per_share: Optional[float] = None  # 配当金

    # Guidance (業績予想)
    revenue_forecast: Optional[float] = None
    net_income_forecast: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'ticker': self.ticker,
            'region': self.region,
            'date': self.report_date,
            'period_type': self.period_type,
            'fiscal_year': self.fiscal_year,
            'data_source': self.data_source,
            'revenue': self.revenue,
            'operating_profit': self.operating_profit,
            'net_income': self.net_income,
            'total_assets': self.total_assets,
            'total_equity': self.total_equity,
            'trailing_eps': self.eps,
        }


class TDnetApiClient:
    """
    TDnet API 클라이언트

    도쿄증권거래소의 적시공시 시스템에서 결산단신 데이터를 수집합니다.
    EDINET의 분기보고서가 없는 대기업의 분기 데이터를 위해 사용합니다.

    데이터 소스 우선순위:
    1. J-Quants API (유료, 구조화된 데이터)
    2. TDnet 직접 스크래핑 (무료, PDF/XBRL 파싱 필요)
    3. yfinance (무료, 제한적 데이터)

    사용 예시:
        api = TDnetApiClient()

        # J-Quants API 사용 시
        api = TDnetApiClient(jquants_id="your_id", jquants_password="your_pw")

        # 분기 재무 데이터 조회
        data = api.get_quarterly_fundamentals("7203", start_year=2023)
    """

    # TDnet 공시 유형 코드
    DISCLOSURE_TYPES = {
        '10': '決算短信（通期）',      # Full-year results
        '20': '決算短信（第1四半期）',  # Q1 results
        '21': '決算短信（第2四半期）',  # Q2 results (半期)
        '22': '決算短信（第3四半期）',  # Q3 results
    }

    # 분기별 종료월 (3월 결산 기업 기준)
    QUARTER_END_MONTHS = {
        'Q1': 6,   # 4-6월 실적
        'Q2': 9,   # 7-9월 실적
        'Q3': 12,  # 10-12월 실적
        'Q4': 3,   # 1-3월 실적 (연간)
    }

    def __init__(
        self,
        jquants_id: Optional[str] = None,
        jquants_password: Optional[str] = None,
        rate_limit_delay: float = 1.0
    ):
        """
        TDnet API 클라이언트 초기화

        Args:
            jquants_id: J-Quants API 메일 주소 (선택, 없으면 yfinance 사용)
            jquants_password: J-Quants API 비밀번호
            rate_limit_delay: API 호출 간 지연 시간 (초)
        """
        self.jquants_id = jquants_id or os.getenv("JQUANTS_ID")
        self.jquants_password = jquants_password or os.getenv("JQUANTS_PASSWORD")
        self.rate_limit_delay = rate_limit_delay

        self.session = requests.Session()
        self._last_request_time: float = 0
        self._jquants_token: Optional[str] = None
        self._jquants_token_expiry: Optional[datetime] = None

        # J-Quants API 사용 가능 여부
        self.use_jquants = bool(self.jquants_id and self.jquants_password)

        if self.use_jquants:
            logger.info("🇯🇵 TDnetApiClient 초기화 (J-Quants API 모드)")
        else:
            logger.info("🇯🇵 TDnetApiClient 초기화 (yfinance fallback 모드)")

    def _rate_limit(self):
        """Rate limiting 적용"""
        if self.rate_limit_delay <= 0:
            return

        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        self._last_request_time = time.time()

    # ========================================================================
    # J-Quants API Methods
    # ========================================================================

    def _get_jquants_token(self) -> Optional[str]:
        """
        J-Quants API 인증 토큰 획득

        Returns:
            API 토큰 또는 None
        """
        if not self.use_jquants:
            return None

        # 토큰이 유효하면 재사용
        if self._jquants_token and self._jquants_token_expiry:
            if datetime.now() < self._jquants_token_expiry:
                return self._jquants_token

        try:
            # 1. Refresh Token 획득
            auth_url = "https://api.jquants.com/v1/token/auth_user"
            auth_data = {
                "mailaddress": self.jquants_id,
                "password": self.jquants_password
            }

            self._rate_limit()
            response = self.session.post(auth_url, json=auth_data, timeout=30)
            response.raise_for_status()

            refresh_token = response.json().get("refreshToken")
            if not refresh_token:
                logger.error("J-Quants Refresh Token 획득 실패")
                return None

            # 2. ID Token 획득
            token_url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"

            self._rate_limit()
            response = self.session.post(token_url, timeout=30)
            response.raise_for_status()

            id_token = response.json().get("idToken")
            if not id_token:
                logger.error("J-Quants ID Token 획득 실패")
                return None

            self._jquants_token = id_token
            self._jquants_token_expiry = datetime.now() + timedelta(hours=23)

            logger.info("✅ J-Quants API 인증 성공")
            return id_token

        except requests.exceptions.RequestException as e:
            logger.error(f"J-Quants 인증 실패: {e}")
            return None

    def get_quarterly_from_jquants(
        self,
        ticker: str,
        start_year: int = 2023,
        end_year: int = 2024
    ) -> List[TDnetQuarterlyData]:
        """
        J-Quants API에서 분기 재무 데이터 조회

        Args:
            ticker: JP 주식 티커 (4자리)
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            분기별 재무 데이터 리스트
        """
        token = self._get_jquants_token()
        if not token:
            return []

        results = []

        try:
            # J-Quants fins/statements 엔드포인트
            url = "https://api.jquants.com/v1/fins/statements"
            headers = {"Authorization": f"Bearer {token}"}
            params = {"code": f"{ticker}0"}  # J-Quants는 5자리 코드 사용

            self._rate_limit()
            response = self.session.get(url, headers=headers, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            statements = data.get("statements", [])

            for stmt in statements:
                fiscal_year = int(stmt.get("FiscalYear", 0))

                if fiscal_year < start_year or fiscal_year > end_year:
                    continue

                # 분기 결정
                type_of_document = stmt.get("TypeOfDocument", "")
                if "第1四半期" in type_of_document or "1Q" in type_of_document:
                    quarter = "Q1"
                    quarter_month = 6
                elif "第2四半期" in type_of_document or "2Q" in type_of_document:
                    quarter = "Q2"
                    quarter_month = 9
                elif "第3四半期" in type_of_document or "3Q" in type_of_document:
                    quarter = "Q3"
                    quarter_month = 12
                else:
                    quarter = "Q4"
                    quarter_month = 3
                    # Q4는 연간 데이터이므로 스킵 (EDINET에서 수집)
                    continue

                # 값 파싱 (단위: 백만엔 → 원)
                def parse_value(key: str) -> Optional[float]:
                    val = stmt.get(key)
                    if val is None or val == "":
                        return None
                    try:
                        return float(val) * 1_000_000  # 백만엔 → 엔
                    except (ValueError, TypeError):
                        return None

                quarter_data = TDnetQuarterlyData(
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    fiscal_period=quarter,
                    report_date=date(fiscal_year, quarter_month, 30 if quarter_month != 12 else 31),
                    data_source="JQUANTS",

                    revenue=parse_value("NetSales"),
                    operating_profit=parse_value("OperatingProfit"),
                    ordinary_profit=parse_value("OrdinaryProfit"),
                    net_income=parse_value("Profit"),

                    total_assets=parse_value("TotalAssets"),
                    total_equity=parse_value("Equity"),

                    eps=float(stmt.get("EarningsPerShare", 0)) if stmt.get("EarningsPerShare") else None,
                )

                results.append(quarter_data)
                logger.debug(f"[{ticker}] {fiscal_year}{quarter} 데이터 추출")

            logger.info(f"[{ticker}] {len(results)}개 분기 J-Quants 데이터 추출 완료")

        except requests.exceptions.RequestException as e:
            logger.error(f"[{ticker}] J-Quants API 요청 실패: {e}")

        return results

    # ========================================================================
    # yfinance Fallback Methods
    # ========================================================================

    def get_quarterly_from_yfinance(
        self,
        ticker: str,
        start_year: int = 2023,
        end_year: int = 2024
    ) -> List[TDnetQuarterlyData]:
        """
        yfinance에서 분기 재무 데이터 조회 (Fallback)

        주의: yfinance는 일본 주식의 분기 데이터를 제한적으로 제공합니다.

        Args:
            ticker: JP 주식 티커 (4자리)
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            분기별 재무 데이터 리스트 (제한적)
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance 미설치. pip install yfinance")
            return []

        results = []

        try:
            # 일본 주식은 .T 접미사 사용
            yf_ticker = f"{ticker}.T"
            stock = yf.Ticker(yf_ticker)

            # 분기 재무제표 조회
            quarterly_financials = stock.quarterly_financials
            quarterly_balance = stock.quarterly_balance_sheet

            if quarterly_financials is None or quarterly_financials.empty:
                logger.warning(f"[{ticker}] yfinance 분기 데이터 없음")
                return []

            for col_date in quarterly_financials.columns:
                fiscal_year = col_date.year
                quarter_month = col_date.month

                if fiscal_year < start_year or fiscal_year > end_year:
                    continue

                # 분기 결정
                if quarter_month <= 3:
                    quarter = "Q4"  # 1-3월
                elif quarter_month <= 6:
                    quarter = "Q1"  # 4-6월
                elif quarter_month <= 9:
                    quarter = "Q2"  # 7-9월
                else:
                    quarter = "Q3"  # 10-12월

                # Q4는 연간 데이터이므로 스킵
                if quarter == "Q4":
                    continue

                def get_value(df, key: str) -> Optional[float]:
                    try:
                        if key in df.index:
                            val = df.loc[key, col_date]
                            if pd.notna(val):
                                return float(val)
                    except Exception:
                        pass
                    return None

                import pandas as pd

                quarter_data = TDnetQuarterlyData(
                    ticker=ticker,
                    fiscal_year=fiscal_year,
                    fiscal_period=quarter,
                    report_date=col_date.date(),
                    data_source="YFINANCE",

                    revenue=get_value(quarterly_financials, "Total Revenue"),
                    operating_profit=get_value(quarterly_financials, "Operating Income"),
                    net_income=get_value(quarterly_financials, "Net Income"),

                    total_assets=get_value(quarterly_balance, "Total Assets") if quarterly_balance is not None else None,
                    total_equity=get_value(quarterly_balance, "Stockholders Equity") if quarterly_balance is not None else None,
                )

                if quarter_data.revenue or quarter_data.net_income:
                    results.append(quarter_data)
                    logger.debug(f"[{ticker}] {fiscal_year}{quarter} 데이터 추출 (yfinance)")

            logger.info(f"[{ticker}] {len(results)}개 분기 yfinance 데이터 추출 완료")

        except Exception as e:
            logger.error(f"[{ticker}] yfinance 조회 실패: {e}")

        return results

    # ========================================================================
    # Main Interface
    # ========================================================================

    def get_quarterly_fundamentals(
        self,
        ticker: str,
        start_year: int = 2023,
        end_year: int = 2024
    ) -> List[TDnetQuarterlyData]:
        """
        분기 재무 데이터 조회 (통합 인터페이스)

        J-Quants API가 설정되어 있으면 사용하고,
        그렇지 않으면 yfinance로 fallback합니다.

        Args:
            ticker: JP 주식 티커 (4자리)
            start_year: 시작 연도
            end_year: 종료 연도

        Returns:
            분기별 재무 데이터 리스트
        """
        if self.use_jquants:
            results = self.get_quarterly_from_jquants(ticker, start_year, end_year)
            if results:
                return results
            logger.warning(f"[{ticker}] J-Quants 데이터 없음, yfinance로 fallback")

        return self.get_quarterly_from_yfinance(ticker, start_year, end_year)

    def validate_connection(self) -> bool:
        """
        API 연결 검증

        Returns:
            연결 성공 여부
        """
        if self.use_jquants:
            token = self._get_jquants_token()
            if token:
                logger.info("✅ J-Quants API 연결 성공")
                return True
            logger.warning("⚠️ J-Quants API 연결 실패, yfinance 모드로 동작")

        # yfinance 테스트
        try:
            import yfinance as yf
            test = yf.Ticker("7203.T")
            info = test.info
            if info:
                logger.info("✅ yfinance 연결 성공")
                return True
        except Exception as e:
            logger.error(f"yfinance 연결 실패: {e}")

        return False

    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()
            self.session = None
            logger.info("🔒 TDnet 세션 종료")


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("TDnet API 클라이언트 테스트")
    print("=" * 80)

    # API 클라이언트 초기화
    api = TDnetApiClient()

    # 연결 테스트
    print("\n1. 연결 테스트...")
    if api.validate_connection():
        print("   ✅ 연결 성공")
    else:
        print("   ❌ 연결 실패")

    # 토요타(7203) 분기 데이터 테스트
    print("\n2. 토요타(7203) 분기 데이터 조회...")
    data = api.get_quarterly_fundamentals("7203", start_year=2023, end_year=2024)

    if data:
        print(f"   ✅ {len(data)}개 분기 데이터 수집")
        for d in data[:3]:
            print(f"      - {d.fiscal_year}{d.fiscal_period}: Revenue={d.revenue:,.0f}" if d.revenue else f"      - {d.fiscal_year}{d.fiscal_period}: No revenue data")
    else:
        print("   ⚠️ 분기 데이터 없음")

    # 세션 종료
    api.close()

    print("\n" + "=" * 80)
    print("테스트 완료")
    print("=" * 80)
