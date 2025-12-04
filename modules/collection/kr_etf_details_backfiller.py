#!/usr/bin/env python3
"""
KR ETF Details Backfiller

KR 리전 ETF의 etf_details 테이블 NULL 필드를 채우는 백필러.

데이터 소스:
- 네이버 금융 (finance.naver.com) - 공개된 ETF 정보 페이지

채우는 필드:
- issuer: 자산운용사
- tracking_index: 추종지수
- inception_date: 상장일
- fund_type: 펀드유형
- aum: 순자산총액
- listed_shares: 상장주식수

사용법:
    from modules.collection.kr_etf_details_backfiller import KRETFDetailsBackfiller

    backfiller = KRETFDetailsBackfiller()
    result = backfiller.run(dry_run=True)  # 테스트
    result = backfiller.run()  # 실제 실행

Author: Quant Investment Platform
Date: 2024-12-04
"""

import os
import sys
import time
import re
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.db_manager_postgres import PostgresDatabaseManager


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ETFDetailsData:
    """ETF 상세 정보 데이터 클래스"""
    ticker: str
    issuer: Optional[str] = None
    tracking_index: Optional[str] = None
    inception_date: Optional[date] = None
    fund_type: Optional[str] = None
    aum: Optional[int] = None
    listed_shares: Optional[int] = None
    data_source: str = "naver_finance"


@dataclass
class BackfillResult:
    """백필 결과 데이터 클래스"""
    total_etfs: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    failed_tickers: List[str] = field(default_factory=list)
    field_stats: Dict[str, int] = field(default_factory=dict)


# =============================================================================
# Naver Finance ETF Scraper
# =============================================================================

class NaverETFDetailsScraper:
    """
    네이버 금융 ETF 상세정보 스크래퍼

    네이버 금융 개별 종목 페이지에서 ETF 상세 정보를 파싱합니다.
    - URL: https://finance.naver.com/item/main.naver?code={ticker}
    """

    BASE_URL = "https://finance.naver.com/item/main.naver"

    def __init__(self, rate_limit: float = 0.5):
        """
        Initialize scraper.

        Args:
            rate_limit: 요청 간 대기 시간 (초). 기본 0.5초.
        """
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        })
        self.last_request_time = 0

    def _wait_rate_limit(self):
        """Rate limiting 적용"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def scrape(self, ticker: str) -> Optional[ETFDetailsData]:
        """
        단일 ETF 상세정보 스크래핑

        Args:
            ticker: ETF 티커 코드 (예: '069500')

        Returns:
            ETFDetailsData 객체 또는 None (실패 시)
        """
        self._wait_rate_limit()

        url = f"{self.BASE_URL}?code={ticker}"

        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()

            # ETF 페이지인지 확인
            if 'ETF' not in resp.text and '펀드보수' not in resp.text:
                logger.debug(f"[{ticker}] ETF 페이지가 아님")
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            result = ETFDetailsData(ticker=ticker)

            # 모든 테이블에서 정보 추출
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if not th or not td:
                        continue

                    field_name = th.text.strip()
                    value = td.text.strip()

                    # 자산운용사
                    if '자산운용사' in field_name:
                        result.issuer = value.replace('(주)', '').replace('㈜', '').strip()

                    # 기초지수 (추종지수)
                    elif field_name == '기초지수':
                        span = td.find('span')
                        if span:
                            result.tracking_index = span.get('title') or span.text.strip()
                        else:
                            result.tracking_index = value

                    # 펀드유형
                    elif field_name == '유형':
                        span = td.find('span')
                        if span:
                            result.fund_type = span.get('title') or span.text.strip()
                        else:
                            result.fund_type = value

                    # 상장일
                    elif field_name == '상장일':
                        result.inception_date = self._parse_date(value)

                    # 시가총액 (AUM으로 사용)
                    elif '시가총액' in field_name:
                        result.aum = self._parse_market_cap(value)

                    # 상장주식수
                    elif '상장주식수' in field_name:
                        result.listed_shares = self._parse_number(value)

            # 최소 1개 필드라도 있으면 성공
            if any([result.issuer, result.tracking_index, result.inception_date,
                    result.fund_type, result.aum, result.listed_shares]):
                logger.debug(f"[{ticker}] 스크래핑 성공")
                return result
            else:
                logger.debug(f"[{ticker}] 데이터 없음")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"[{ticker}] 타임아웃")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"[{ticker}] 요청 실패: {e}")
            return None
        except Exception as e:
            logger.error(f"[{ticker}] 파싱 에러: {e}")
            return None

    def _parse_date(self, value: str) -> Optional[date]:
        """날짜 파싱: '2002년 10월 14일' -> date(2002, 10, 14)"""
        match = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', value)
        if match:
            try:
                y, m, d = match.groups()
                return date(int(y), int(m), int(d))
            except ValueError:
                pass
        return None

    def _parse_market_cap(self, value: str) -> Optional[int]:
        """
        시가총액 파싱

        네이버 금융의 복잡한 HTML 구조 처리:
        - '11조\n\t\t272\n억원' -> 11027200000000
        - '9조 6,954억원' -> 9695400000000
        - '5,750억원' -> 575000000000
        """
        # 모든 공백 문자(탭, 줄바꿈 등) 제거
        text = re.sub(r'\s+', '', value)
        # 쉼표 제거
        text = text.replace(',', '')

        logger.debug(f"Market cap parsing: '{value[:50]}...' -> '{text}'")

        trillion_match = re.search(r'(\d+)조', text)
        billion_match = re.search(r'(\d+)억', text)

        total = 0
        if trillion_match:
            total += int(trillion_match.group(1)) * 1_000_000_000_000
        if billion_match:
            total += int(billion_match.group(1)) * 100_000_000

        logger.debug(f"Parsed market cap: {total}")
        return total if total > 0 else None

    def _parse_number(self, value: str) -> Optional[int]:
        """숫자 파싱: '193,800,000' -> 193800000"""
        clean = re.sub(r'[^\d]', '', value)
        try:
            return int(clean) if clean else None
        except ValueError:
            return None


# =============================================================================
# KR ETF Details Backfiller
# =============================================================================

class KRETFDetailsBackfiller:
    """
    KR ETF Details 백필러

    etf_details 테이블의 NULL 필드를 네이버 금융 데이터로 채웁니다.
    """

    def __init__(
        self,
        db_manager: Optional[PostgresDatabaseManager] = None,
        rate_limit: float = 0.5
    ):
        """
        Initialize backfiller.

        Args:
            db_manager: PostgresDatabaseManager 인스턴스 (없으면 새로 생성)
            rate_limit: 스크래핑 요청 간 대기 시간 (초)
        """
        self.db = db_manager or PostgresDatabaseManager()
        self.scraper = NaverETFDetailsScraper(rate_limit=rate_limit)

    def get_null_field_etfs(self) -> List[str]:
        """
        NULL 필드가 있는 KR ETF 티커 목록 조회

        Returns:
            티커 목록
        """
        query = """
        SELECT ticker FROM etf_details
        WHERE region = 'KR'
          AND (
            issuer IS NULL
            OR tracking_index = 'Unknown'
            OR tracking_index IS NULL
            OR inception_date IS NULL
            OR aum IS NULL
            OR listed_shares IS NULL
          )
        ORDER BY ticker
        """

        result = self.db.execute_query(query)
        return [row['ticker'] for row in (result or [])]

    def get_coverage_stats(self) -> Dict[str, Tuple[int, int]]:
        """
        필드별 커버리지 통계 조회

        Returns:
            {필드명: (채워진 수, 전체 수)}
        """
        query = """
        SELECT
            COUNT(*) as total,
            COUNT(issuer) as has_issuer,
            SUM(CASE WHEN tracking_index IS NOT NULL AND tracking_index != 'Unknown' THEN 1 ELSE 0 END) as has_tracking_index,
            COUNT(inception_date) as has_inception_date,
            COUNT(fund_type) as has_fund_type,
            COUNT(aum) as has_aum,
            COUNT(listed_shares) as has_listed_shares
        FROM etf_details
        WHERE region = 'KR'
        """

        result = self.db.execute_query(query)
        if not result:
            return {}

        row = result[0]
        total = row['total']

        return {
            'issuer': (row['has_issuer'], total),
            'tracking_index': (row['has_tracking_index'], total),
            'inception_date': (row['has_inception_date'], total),
            'fund_type': (row['has_fund_type'], total),
            'aum': (row['has_aum'], total),
            'listed_shares': (row['has_listed_shares'], total),
        }

    def update_etf_details(self, data: ETFDetailsData, dry_run: bool = False) -> bool:
        """
        단일 ETF 상세정보 업데이트

        Args:
            data: ETFDetailsData 객체
            dry_run: True면 실제 업데이트 없이 시뮬레이션

        Returns:
            성공 여부
        """
        if dry_run:
            return True

        # COALESCE 패턴으로 NULL만 업데이트
        query = """
        UPDATE etf_details SET
            issuer = COALESCE(%s, issuer),
            tracking_index = CASE
                WHEN tracking_index IS NULL OR tracking_index = 'Unknown'
                THEN COALESCE(%s, tracking_index)
                ELSE tracking_index
            END,
            inception_date = COALESCE(%s, inception_date),
            sector_theme = COALESCE(%s, sector_theme),
            aum = COALESCE(%s, aum),
            listed_shares = COALESCE(%s, listed_shares),
            last_updated = NOW()
        WHERE ticker = %s AND region = 'KR'
        """

        try:
            return self.db.execute_update(query, (
                data.issuer,
                data.tracking_index,
                data.inception_date,
                data.fund_type,  # sector_theme으로 저장
                data.aum,
                data.listed_shares,
                data.ticker,
            ))
        except Exception as e:
            logger.error(f"[{data.ticker}] DB 업데이트 실패: {e}")
            return False

    def run(
        self,
        dry_run: bool = False,
        limit: Optional[int] = None,
        ticker: Optional[str] = None,
        force: bool = False
    ) -> BackfillResult:
        """
        백필 실행

        Args:
            dry_run: True면 실제 업데이트 없이 시뮬레이션
            limit: 처리할 최대 ETF 수
            ticker: 특정 티커만 처리
            force: True면 NULL이 아닌 필드도 업데이트

        Returns:
            BackfillResult 객체
        """
        result = BackfillResult()

        # 처리할 티커 목록
        if ticker:
            tickers = [ticker]
        elif force:
            # 전체 KR ETF
            query = "SELECT ticker FROM etf_details WHERE region = 'KR' ORDER BY ticker"
            rows = self.db.execute_query(query) or []
            tickers = [row['ticker'] for row in rows]
        else:
            tickers = self.get_null_field_etfs()

        if limit:
            tickers = tickers[:limit]

        result.total_etfs = len(tickers)

        if result.total_etfs == 0:
            logger.info("처리할 ETF가 없습니다.")
            return result

        # 시작 전 커버리지
        before_stats = self.get_coverage_stats()

        logger.info(f"{'[DRY RUN] ' if dry_run else ''}백필 시작: {result.total_etfs}개 ETF")
        logger.info(f"예상 소요 시간: ~{result.total_etfs * self.scraper.rate_limit / 60:.1f}분")

        # 처리
        for i, tkr in enumerate(tickers, 1):
            if i % 50 == 0 or i <= 5 or i == result.total_etfs:
                logger.info(f"진행: {i}/{result.total_etfs} ({i/result.total_etfs*100:.1f}%)")

            data = self.scraper.scrape(tkr)

            if data:
                if self.update_etf_details(data, dry_run=dry_run):
                    result.updated += 1
                    # 필드별 통계
                    for field in ['issuer', 'tracking_index', 'inception_date',
                                  'fund_type', 'aum', 'listed_shares']:
                        if getattr(data, field) is not None:
                            result.field_stats[field] = result.field_stats.get(field, 0) + 1
                else:
                    result.failed += 1
                    result.failed_tickers.append(tkr)
            else:
                result.skipped += 1

        # 완료 후 커버리지
        if not dry_run:
            after_stats = self.get_coverage_stats()
            self._log_coverage_change(before_stats, after_stats)

        logger.info(f"백필 완료: 업데이트={result.updated}, 스킵={result.skipped}, 실패={result.failed}")

        return result

    def _log_coverage_change(
        self,
        before: Dict[str, Tuple[int, int]],
        after: Dict[str, Tuple[int, int]]
    ):
        """커버리지 변화 로깅"""
        logger.info("=" * 60)
        logger.info("  필드별 커버리지 변화")
        logger.info("=" * 60)

        for field in before:
            b_count, b_total = before[field]
            a_count, a_total = after[field]
            diff = a_count - b_count

            b_pct = b_count / b_total * 100 if b_total > 0 else 0
            a_pct = a_count / a_total * 100 if a_total > 0 else 0

            status = f"+{diff}" if diff > 0 else str(diff)
            logger.info(f"  {field:18s}: {b_count:5d} → {a_count:5d} ({a_pct:5.1f}%) [{status}]")

        logger.info("=" * 60)

    def generate_report(self, result: BackfillResult) -> str:
        """백필 결과 리포트 생성"""
        stats = self.get_coverage_stats()

        report = []
        report.append("=" * 70)
        report.append("  KR ETF Details Backfill Report")
        report.append("=" * 70)
        report.append(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"  Source: Naver Finance (finance.naver.com)")
        report.append("=" * 70)
        report.append("")
        report.append("  Summary:")
        report.append(f"    Total ETFs:  {result.total_etfs}")
        report.append(f"    Updated:     {result.updated}")
        report.append(f"    Skipped:     {result.skipped}")
        report.append(f"    Failed:      {result.failed}")
        report.append("")
        report.append("  Current Coverage:")

        for field, (count, total) in stats.items():
            pct = count / total * 100 if total > 0 else 0
            report.append(f"    {field:18s}: {count:5d}/{total:5d} ({pct:5.1f}%)")

        report.append("")

        if result.failed_tickers:
            report.append("  Failed Tickers:")
            for tkr in result.failed_tickers[:20]:
                report.append(f"    - {tkr}")
            if len(result.failed_tickers) > 20:
                report.append(f"    ... and {len(result.failed_tickers) - 20} more")

        report.append("=" * 70)

        return "\n".join(report)


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KR ETF Details Backfiller")
    parser.add_argument('--dry-run', action='store_true', help='시뮬레이션 모드 (DB 변경 없음)')
    parser.add_argument('--limit', type=int, help='처리할 최대 ETF 수')
    parser.add_argument('--ticker', type=str, help='특정 티커만 처리')
    parser.add_argument('--force', action='store_true', help='NULL이 아닌 필드도 업데이트')
    parser.add_argument('--status', action='store_true', help='현재 상태만 확인')

    args = parser.parse_args()

    # 환경 변수 로드
    from dotenv import load_dotenv
    load_dotenv()

    backfiller = KRETFDetailsBackfiller()

    if args.status:
        stats = backfiller.get_coverage_stats()
        null_count = len(backfiller.get_null_field_etfs())

        print("\n" + "=" * 60)
        print("  KR ETF Details 현재 상태")
        print("=" * 60)

        for field, (count, total) in stats.items():
            pct = count / total * 100 if total > 0 else 0
            print(f"  {field:18s}: {count:5d}/{total:5d} ({pct:5.1f}%)")

        print()
        print(f"  NULL 필드가 있는 ETF: {null_count}개")
        print("=" * 60 + "\n")
    else:
        result = backfiller.run(
            dry_run=args.dry_run,
            limit=args.limit,
            ticker=args.ticker,
            force=args.force
        )

        print(backfiller.generate_report(result))
