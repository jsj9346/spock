#!/usr/bin/env python3
"""
KR ETF Details Backfill Script

KR 리전 ETF의 etf_details 테이블 NULL 필드를 네이버 금융 데이터로 백필합니다.

채우는 필드:
- issuer: 자산운용사
- tracking_index: 추종지수
- inception_date: 상장일
- fund_type (sector_theme): 펀드유형
- aum: 순자산총액 (시가총액)
- listed_shares: 상장주식수

사용법:
    # 현재 상태 확인
    python scripts/backfill_kr_etf_details.py --status

    # Dry-run 테스트 (10개만)
    python scripts/backfill_kr_etf_details.py --dry-run --limit 10

    # 실제 백필 실행
    python scripts/backfill_kr_etf_details.py

    # 특정 티커만 처리
    python scripts/backfill_kr_etf_details.py --ticker 069500

    # 강제 업데이트 (기존 값도 덮어쓰기)
    python scripts/backfill_kr_etf_details.py --force --limit 10

Author: Quant Investment Platform
Date: 2024-12-04
"""

import os
import sys
import argparse
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

from modules.collection.kr_etf_details_backfiller import KRETFDetailsBackfiller


def setup_logging(verbose: bool = False):
    """로깅 설정"""
    log_level = "DEBUG" if verbose else "INFO"

    # 기존 핸들러 제거
    logger.remove()

    # 콘솔 출력
    logger.add(
        sys.stdout,
        level=log_level,
        format="<level>{level: <8}</level> | {message}",
        colorize=True
    )

    # 파일 로깅
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y%m%d')}_kr_etf_backfill.log")

    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation="1 day",
        retention="30 days"
    )


def show_status(backfiller: KRETFDetailsBackfiller):
    """현재 상태 출력"""
    stats = backfiller.get_coverage_stats()
    null_etfs = backfiller.get_null_field_etfs()

    print()
    print("=" * 70)
    print("  KR ETF Details 현재 상태")
    print("=" * 70)
    print(f"  조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("  필드별 커버리지:")

    for field, (count, total) in stats.items():
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        status = "✅" if pct >= 95 else "⚠️" if pct >= 50 else "❌"
        print(f"    {field:18s}: {count:5d}/{total:5d} ({pct:5.1f}%) {bar} {status}")

    print()
    print(f"  NULL 필드가 있는 ETF: {len(null_etfs)}개")

    if null_etfs and len(null_etfs) <= 10:
        print(f"  목록: {', '.join(null_etfs)}")
    elif null_etfs:
        print(f"  샘플: {', '.join(null_etfs[:10])} ...")

    print("=" * 70)
    print()


def main():
    """메인 실행"""
    parser = argparse.ArgumentParser(
        description="KR ETF Details Backfill Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 현재 상태 확인
  python scripts/backfill_kr_etf_details.py --status

  # Dry-run 테스트 (10개만)
  python scripts/backfill_kr_etf_details.py --dry-run --limit 10

  # 실제 백필 실행
  python scripts/backfill_kr_etf_details.py

  # 특정 티커만 처리
  python scripts/backfill_kr_etf_details.py --ticker 069500
        """
    )

    parser.add_argument('--status', action='store_true',
                        help='현재 상태만 확인 (백필 실행 안함)')
    parser.add_argument('--dry-run', action='store_true',
                        help='시뮬레이션 모드 (DB 변경 없음)')
    parser.add_argument('--limit', type=int,
                        help='처리할 최대 ETF 수')
    parser.add_argument('--ticker', type=str,
                        help='특정 티커만 처리')
    parser.add_argument('--force', action='store_true',
                        help='NULL이 아닌 필드도 업데이트')
    parser.add_argument('--rate-limit', type=float, default=0.5,
                        help='요청 간 대기 시간 (초, 기본: 0.5)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='상세 로그 출력')

    args = parser.parse_args()

    # 환경 변수 로드
    load_dotenv()

    # 로깅 설정
    setup_logging(args.verbose)

    # 백필러 초기화
    backfiller = KRETFDetailsBackfiller(rate_limit=args.rate_limit)

    # 상태 확인 모드
    if args.status:
        show_status(backfiller)
        return

    # 시작 메시지
    print()
    print("=" * 70)
    print("  KR ETF Details Backfill")
    print("=" * 70)
    print(f"  모드: {'DRY RUN (시뮬레이션)' if args.dry_run else 'PRODUCTION'}")
    print(f"  Rate Limit: {args.rate_limit}초/요청")
    if args.limit:
        print(f"  Limit: {args.limit}개")
    if args.ticker:
        print(f"  Ticker: {args.ticker}")
    if args.force:
        print(f"  Force: 기존 값도 업데이트")
    print("=" * 70)
    print()

    # 시작 전 상태
    logger.info("시작 전 상태 확인...")
    show_status(backfiller)

    # 백필 실행
    logger.info("백필 시작...")
    result = backfiller.run(
        dry_run=args.dry_run,
        limit=args.limit,
        ticker=args.ticker,
        force=args.force
    )

    # 결과 리포트
    print()
    print(backfiller.generate_report(result))

    # 종료 상태 (dry-run이 아닌 경우)
    if not args.dry_run and result.updated > 0:
        logger.info("백필 후 상태 확인...")
        show_status(backfiller)


if __name__ == "__main__":
    main()
