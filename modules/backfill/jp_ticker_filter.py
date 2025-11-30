"""
JP Ticker Smart Filtering System

EDINET API가 펀더멘털 데이터를 지원하지 않는 JP 종목들을
사전에 필터링하는 스마트 필터링 시스템.

주요 필터링 대상:
1. 알파벳 접미사 ticker (예: 131A, 142A) - 신규 IPO로 유가증권보고서 미제출
2. 펀드/ETF 종목 - EDINET에서 기업 재무 데이터 미제공
3. 이미 unavailable로 마킹된 종목 - 재시도 방지

US 리전의 SEC 6-K 필터링과 유사한 접근 방식을 적용합니다.

Author: Quant Platform Development Team
Date: 2025-11-27
"""

import re
import logging
from typing import List, Set, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class JPTickerFilterReason(Enum):
    """JP ticker 필터링 사유"""
    ALPHA_SUFFIX_IPO = "alpha_suffix_ipo"  # 알파벳 접미사 (신규 IPO)
    ETF_OR_FUND = "etf_or_fund"  # ETF/펀드 종목
    REIT = "reit"  # J-REIT 종목
    PREFERRED_STOCK = "preferred_stock"  # 우선주
    INFRASTRUCTURE_FUND = "infrastructure_fund"  # 인프라펀드
    ALREADY_UNAVAILABLE = "already_unavailable"  # 이미 unavailable 상태
    NO_EDINET_CODE = "no_edinet_code"  # EDINET 코드 미존재
    PASSED = "passed"  # 필터 통과


@dataclass
class JPTickerFilterResult:
    """JP ticker 필터링 결과"""
    ticker: str
    should_skip: bool
    reason: JPTickerFilterReason
    description: str

    def __str__(self) -> str:
        status = "SKIP" if self.should_skip else "PASS"
        return f"[{status}] {self.ticker}: {self.description}"


class JPTickerFilter:
    """
    JP Ticker 스마트 필터링 클래스

    EDINET API 호출 전 지원 불가 종목을 사전 필터링하여
    불필요한 API 호출을 방지하고 백필 효율성을 높입니다.

    사용 예시:
        filter = JPTickerFilter()

        # 단일 ticker 검사
        result = filter.check_ticker("131A")
        if result.should_skip:
            print(f"Skip: {result.description}")

        # 배치 필터링
        tickers = ["7203", "131A", "9434"]
        passed, skipped = filter.filter_tickers(tickers)
    """

    # 알파벳 접미사 패턴 (신규 IPO)
    # 일본 거래소는 신규 상장 시 임시로 숫자+알파벳 형식 부여
    # 예: 130A, 131A, 142A 등
    ALPHA_SUFFIX_PATTERN = re.compile(r'^[0-9]+[A-Z]$')

    # ETF 종목 코드 범위 (일본 거래소 기준)
    ETF_CODE_RANGES = [
        (1300, 1399),  # 국내 ETF 일부
        (1400, 1499),  # 일부 레버리지/인버스 ETF
        (1540, 1699),  # 해외 ETF, 레버리지 ETF
        (2500, 2699),  # ETF 추가 범위
    ]

    # J-REIT 종목 코드 범위
    REIT_CODE_RANGES = [
        (2971, 2999),  # 일부 J-REIT
        (3200, 3499),  # J-REIT 메인 범위
        (8951, 8999),  # J-REIT 추가 범위
    ]

    # 인프라펀드 코드 범위
    INFRA_FUND_CODE_RANGES = [
        (9281, 9299),  # 인프라펀드
    ]

    # 우선주 접미사 (예: 7201p)
    PREFERRED_STOCK_SUFFIXES = ['P', 'p']

    def __init__(self, db=None):
        """
        JP Ticker Filter 초기화

        Args:
            db: PostgresDatabaseManager 인스턴스 (optional, DB 조회용)
        """
        self.db = db
        self._unavailable_tickers: Set[str] = set()
        self._ticker_info_cache: Dict[str, dict] = {}

        # DB가 있으면 unavailable ticker 로드
        if db:
            self._load_unavailable_tickers()

    def _load_unavailable_tickers(self) -> None:
        """DB에서 이미 unavailable로 마킹된 ticker 로드"""
        if not self.db:
            return

        try:
            query = """
            SELECT ticker FROM tickers
            WHERE region = 'JP'
              AND is_active = TRUE
              AND fund_status = 'unavailable'
            """
            rows = self.db.execute_query(query)
            self._unavailable_tickers = {row['ticker'] for row in rows}
            logger.debug(f"Loaded {len(self._unavailable_tickers)} unavailable JP tickers")
        except Exception as e:
            logger.warning(f"Failed to load unavailable tickers: {e}")

    def _is_alpha_suffix_ticker(self, ticker: str) -> bool:
        """알파벳 접미사 ticker인지 확인 (신규 IPO)"""
        return bool(self.ALPHA_SUFFIX_PATTERN.match(ticker))

    def _is_in_code_range(self, ticker: str, ranges: List[Tuple[int, int]]) -> bool:
        """ticker가 특정 코드 범위에 속하는지 확인"""
        # 숫자만 추출
        numeric_part = re.sub(r'[^0-9]', '', ticker)
        if not numeric_part:
            return False

        try:
            code = int(numeric_part)
            for start, end in ranges:
                if start <= code <= end:
                    return True
            return False
        except ValueError:
            return False

    def _is_etf_or_fund(self, ticker: str) -> bool:
        """ETF/펀드 종목인지 확인"""
        return self._is_in_code_range(ticker, self.ETF_CODE_RANGES)

    def _is_reit(self, ticker: str) -> bool:
        """J-REIT 종목인지 확인"""
        return self._is_in_code_range(ticker, self.REIT_CODE_RANGES)

    def _is_infra_fund(self, ticker: str) -> bool:
        """인프라펀드인지 확인"""
        return self._is_in_code_range(ticker, self.INFRA_FUND_CODE_RANGES)

    def _is_preferred_stock(self, ticker: str) -> bool:
        """우선주인지 확인"""
        return any(ticker.endswith(suffix) for suffix in self.PREFERRED_STOCK_SUFFIXES)

    def _is_already_unavailable(self, ticker: str) -> bool:
        """이미 unavailable로 마킹되었는지 확인"""
        return ticker in self._unavailable_tickers

    def check_ticker(self, ticker: str) -> JPTickerFilterResult:
        """
        단일 ticker 필터링 검사

        Args:
            ticker: JP 주식 ticker

        Returns:
            JPTickerFilterResult 객체
        """
        # 1. 이미 unavailable 상태 확인
        if self._is_already_unavailable(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.ALREADY_UNAVAILABLE,
                description="이미 unavailable로 마킹됨 (이전 백필에서 데이터 없음 확인)"
            )

        # 2. 알파벳 접미사 확인 (신규 IPO)
        if self._is_alpha_suffix_ticker(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.ALPHA_SUFFIX_IPO,
                description="신규 IPO 종목 (알파벳 접미사) - 유가증권보고서 미제출 가능성 높음"
            )

        # 3. ETF/펀드 확인
        if self._is_etf_or_fund(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.ETF_OR_FUND,
                description="ETF/펀드 종목 - 기업 재무 데이터 형식 상이"
            )

        # 4. J-REIT 확인
        if self._is_reit(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.REIT,
                description="J-REIT 종목 - 부동산투자신탁 별도 보고서 형식"
            )

        # 5. 인프라펀드 확인
        if self._is_infra_fund(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.INFRASTRUCTURE_FUND,
                description="인프라펀드 종목 - 별도 보고서 형식"
            )

        # 6. 우선주 확인
        if self._is_preferred_stock(ticker):
            return JPTickerFilterResult(
                ticker=ticker,
                should_skip=True,
                reason=JPTickerFilterReason.PREFERRED_STOCK,
                description="우선주 종목 - 보통주 데이터로 처리 필요"
            )

        # 모든 필터 통과
        return JPTickerFilterResult(
            ticker=ticker,
            should_skip=False,
            reason=JPTickerFilterReason.PASSED,
            description="필터 통과 - EDINET API 조회 가능"
        )

    def filter_tickers(
        self,
        tickers: List[str],
        mark_skipped_unavailable: bool = True
    ) -> Tuple[List[str], List[JPTickerFilterResult]]:
        """
        ticker 목록 배치 필터링

        Args:
            tickers: JP ticker 목록
            mark_skipped_unavailable: True면 스킵된 종목을 DB에 unavailable로 마킹

        Returns:
            (통과된 ticker 목록, 스킵된 필터링 결과 목록) 튜플
        """
        passed = []
        skipped = []

        for ticker in tickers:
            result = self.check_ticker(ticker)

            if result.should_skip:
                skipped.append(result)

                # DB에 unavailable 마킹
                if mark_skipped_unavailable and self.db:
                    self._mark_ticker_filtered(ticker, result)
            else:
                passed.append(ticker)

        # 필터링 통계 로깅
        if skipped:
            skip_reasons = {}
            for r in skipped:
                reason_name = r.reason.value
                skip_reasons[reason_name] = skip_reasons.get(reason_name, 0) + 1

            logger.info(f"🔍 JP Ticker 필터링 결과: {len(passed)} 통과, {len(skipped)} 스킵")
            for reason, count in skip_reasons.items():
                logger.info(f"   - {reason}: {count}개")

        return passed, skipped

    def _mark_ticker_filtered(self, ticker: str, result: JPTickerFilterResult) -> None:
        """필터링된 ticker를 DB에 마킹"""
        if not self.db:
            return

        try:
            # fund_status를 'filtered'로 마킹하여 일반 unavailable과 구분
            # 이 종목들은 API 호출 없이 사전 필터링된 것
            reason_text = f"[PRE-FILTER] {result.description}"

            query = """
            UPDATE tickers
            SET fund_status = 'unavailable',
                fund_last_check = NOW(),
                fund_fail_reason = %s
            WHERE ticker = %s AND region = 'JP'
              AND (fund_status IS NULL OR fund_status = 'unknown')
            """
            self.db.execute_update(query, (reason_text[:200], ticker))

            # 캐시 업데이트
            self._unavailable_tickers.add(ticker)

        except Exception as e:
            logger.warning(f"[{ticker}] 필터링 마킹 실패: {e}")

    def get_filter_statistics(self, tickers: List[str]) -> Dict[str, int]:
        """
        ticker 목록의 필터링 통계 조회 (마킹 없이)

        Args:
            tickers: JP ticker 목록

        Returns:
            필터링 사유별 개수 딕셔너리
        """
        stats = {
            'total': len(tickers),
            'passed': 0,
            'alpha_suffix_ipo': 0,
            'etf_or_fund': 0,
            'reit': 0,
            'infrastructure_fund': 0,
            'preferred_stock': 0,
            'already_unavailable': 0,
        }

        for ticker in tickers:
            result = self.check_ticker(ticker)

            if not result.should_skip:
                stats['passed'] += 1
            else:
                reason_key = result.reason.value
                if reason_key in stats:
                    stats[reason_key] += 1

        return stats

    def refresh_unavailable_cache(self) -> None:
        """unavailable ticker 캐시 갱신"""
        self._unavailable_tickers.clear()
        self._load_unavailable_tickers()


def print_jp_filter_preview(db, limit: int = None) -> None:
    """
    JP ticker 필터링 미리보기 출력

    Args:
        db: PostgresDatabaseManager 인스턴스
        limit: 최대 출력 개수
    """
    from modules.db_manager_postgres import PostgresDatabaseManager

    # 백필 대상 ticker 조회
    query = """
    SELECT ticker, name FROM tickers
    WHERE region = 'JP'
      AND is_active = TRUE
      AND asset_type = 'STOCK'
      AND (fund_status IS NULL OR fund_status = 'unknown')
    ORDER BY ticker
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = db.execute_query(query)
    tickers = [row['ticker'] for row in rows]

    if not tickers:
        print("필터링 대상 ticker가 없습니다.")
        return

    # 필터링 실행
    jp_filter = JPTickerFilter(db)
    stats = jp_filter.get_filter_statistics(tickers)

    print("\n" + "=" * 70)
    print("🇯🇵 JP Ticker 필터링 미리보기")
    print("=" * 70)
    print(f"\n총 ticker: {stats['total']:,}개")
    print(f"API 조회 대상: {stats['passed']:,}개 ({stats['passed']/stats['total']*100:.1f}%)")
    print(f"\n필터링 대상:")
    print(f"  - 신규 IPO (알파벳 접미사): {stats['alpha_suffix_ipo']:,}개")
    print(f"  - ETF/펀드: {stats['etf_or_fund']:,}개")
    print(f"  - J-REIT: {stats['reit']:,}개")
    print(f"  - 인프라펀드: {stats['infrastructure_fund']:,}개")
    print(f"  - 우선주: {stats['preferred_stock']:,}개")
    print(f"  - 이미 unavailable: {stats['already_unavailable']:,}개")

    total_skipped = stats['total'] - stats['passed']
    print(f"\n예상 API 호출 절감: {total_skipped:,}건")
    print("=" * 70)


# 테스트 코드
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/13ruce/spock')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("JP Ticker Smart Filter 테스트")
    print("=" * 70)

    # 필터 초기화 (DB 없이)
    jp_filter = JPTickerFilter()

    # 테스트 케이스
    test_tickers = [
        "7203",   # 토요타 - 통과
        "9984",   # 소프트뱅크 - 통과
        "131A",   # 신규 IPO - 스킵
        "142A",   # 신규 IPO - 스킵
        "1540",   # ETF - 스킵 (코드 범위)
        "8951",   # J-REIT - 스킵
        "9281",   # 인프라펀드 - 스킵
    ]

    print("\n개별 필터링 테스트:")
    print("-" * 70)

    for ticker in test_tickers:
        result = jp_filter.check_ticker(ticker)
        print(result)

    print("\n" + "-" * 70)
    print("배치 필터링 테스트:")
    passed, skipped = jp_filter.filter_tickers(test_tickers, mark_skipped_unavailable=False)
    print(f"통과: {passed}")
    print(f"스킵: {len(skipped)}개")

    # DB 연결 테스트
    try:
        from modules.db_manager_postgres import PostgresDatabaseManager
        db = PostgresDatabaseManager()
        print("\n" + "-" * 70)
        print_jp_filter_preview(db, limit=500)
    except Exception as e:
        print(f"\nDB 연결 실패 (테스트 계속): {e}")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)
