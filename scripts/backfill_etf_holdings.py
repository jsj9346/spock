#!/usr/bin/env python3
"""
ETF Holdings Backfill Script

ETF 구성종목 데이터를 수집하여 etf_holdings 테이블에 저장합니다.

지원 리전:
- KR: KRX API (구성종목 공시 데이터)
- 기타 리전: 현재 미지원 (추후 확장 예정)

사용법:
    # KR ETF 전체 구성종목 수집
    python scripts/backfill_etf_holdings.py --region KR

    # 특정 ETF만 수집
    python scripts/backfill_etf_holdings.py --region KR --ticker 069500

    # 특정 기준일로 수집
    python scripts/backfill_etf_holdings.py --region KR --date 20251128

    # 주요 ETF만 수집 (limit)
    python scripts/backfill_etf_holdings.py --region KR --limit 50

    # 강제 재수집
    python scripts/backfill_etf_holdings.py --region KR --force

Author: Quant Investment Platform
Date: 2025-11-28
"""

import os
import sys
import argparse
import time
from datetime import datetime
from typing import List, Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.collection.etf_collector import ETFCollector


# =============================================================================
# Priority ETF Lists (Holdings 수집 우선순위)
# =============================================================================

# KR 주요 ETF 목록 (Holdings 우선 수집 대상)
KR_PRIORITY_ETFS = [
    # KOSPI 200 관련
    '069500',  # KODEX 200
    '102110',  # TIGER 200
    '152100',  # ARIRANG 200
    '105190',  # KINDEX 200
    '114800',  # KODEX 인버스
    '145670',  # KODEX 레버리지 2X
    '252670',  # KODEX 레버리지 인버스 2X
    # KOSDAQ
    '229200',  # KODEX KOSDAQ150
    '232080',  # TIGER KOSDAQ150
    '251340',  # KODEX KOSDAQ150 레버리지
    # 섹터 ETF
    '091170',  # KODEX 반도체
    '091180',  # KODEX 자동차
    '091160',  # KODEX 바이오
    '091220',  # KODEX 은행
    '139260',  # TIGER 2차전지
    '305540',  # TIGER 2차전지테마
    # 배당 ETF
    '161510',  # ARIRANG 고배당주
    '279530',  # KODEX 배당성장
    '104530',  # KODEX 고배당
    # 해외 투자
    '133690',  # TIGER 미국S&P500
    '143850',  # TIGER 미국나스닥100
    '360750',  # TIGER 미국S&P500선물(H)
    '381170',  # TIGER 미국테크TOP10 INDXX
    # 채권
    '130730',  # KOSEF 국고채10년
    '148070',  # KOSEF 단기자금
]


# =============================================================================
# Utility Functions
# =============================================================================

def get_etf_holdings_count(db: PostgresDatabaseManager, region: str) -> int:
    """etf_holdings 테이블의 레코드 수 조회"""
    query = """
    SELECT COUNT(*) as count FROM etf_holdings WHERE region = %s
    """
    result = db.execute_query(query, (region,))
    return result[0]['count'] if result else 0


def get_etf_holdings_summary(db: PostgresDatabaseManager, region: str) -> Dict:
    """etf_holdings 테이블 요약 조회"""
    query = """
    SELECT
        COUNT(DISTINCT etf_ticker) as etf_count,
        COUNT(*) as holding_count,
        MAX(as_of_date) as latest_date
    FROM etf_holdings
    WHERE region = %s
    """
    result = db.execute_query(query, (region,))
    if result:
        return {
            'etf_count': result[0]['etf_count'],
            'holding_count': result[0]['holding_count'],
            'latest_date': result[0]['latest_date']
        }
    return {'etf_count': 0, 'holding_count': 0, 'latest_date': None}


def get_etfs_with_holdings(db: PostgresDatabaseManager, region: str) -> List[str]:
    """이미 holdings가 수집된 ETF 목록 조회"""
    query = """
    SELECT DISTINCT etf_ticker FROM etf_holdings WHERE region = %s
    """
    result = db.execute_query(query, (region,))
    return [row['etf_ticker'] for row in (result or [])]


# =============================================================================
# Main Backfill Functions
# =============================================================================

def backfill_kr_holdings(
    collector: ETFCollector,
    force: bool = False,
    limit: Optional[int] = None,
    ticker: Optional[str] = None,
    as_of_date: Optional[str] = None,
    priority_only: bool = False
) -> Dict[str, int]:
    """
    KR ETF 구성종목 백필

    Args:
        collector: ETFCollector instance
        force: Force re-collection
        limit: Limit number of ETFs
        ticker: Specific ticker to collect
        as_of_date: As-of date (YYYYMMDD)
        priority_only: Only collect priority ETFs

    Returns:
        Collection results
    """
    region = 'KR'

    if ticker:
        # 단일 ETF 수집
        logger.info(f"[{region}] Collecting holdings for single ETF: {ticker}")
        saved = collector.collect_and_save_holdings(ticker, region, as_of_date)
        return {
            'total': 1,
            'collected': 1 if saved > 0 else 0,
            'skipped': 0,
            'failed': 0 if saved > 0 else 1,
            'total_holdings': saved
        }

    # ETF 목록 결정
    if priority_only:
        tickers = KR_PRIORITY_ETFS
        logger.info(f"[{region}] Using priority ETF list ({len(tickers)} ETFs)")
    else:
        tickers = collector.get_etf_tickers_from_db(region)

    if not tickers:
        logger.warning(f"[{region}] No ETF tickers found")
        return {'total': 0, 'collected': 0, 'skipped': 0, 'failed': 0, 'total_holdings': 0}

    if limit:
        tickers = tickers[:limit]

    logger.info(f"[{region}] Starting holdings backfill for {len(tickers)} ETFs")

    return collector.collect_batch_holdings(
        tickers=tickers,
        region=region,
        as_of_date=as_of_date,
        force=force
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="ETF Holdings Backfill Script")
    parser.add_argument('--region', type=str, default='KR',
                        choices=['KR'],  # 현재 KR만 지원
                        help='Region to backfill (currently only KR supported)')
    parser.add_argument('--ticker', type=str, help='Specific ETF ticker')
    parser.add_argument('--date', type=str, help='As-of date (YYYYMMDD)')
    parser.add_argument('--force', action='store_true', help='Force re-collection')
    parser.add_argument('--limit', type=int, help='Limit number of ETFs')
    parser.add_argument('--priority', action='store_true',
                        help='Only collect priority ETFs')
    parser.add_argument('--status', action='store_true',
                        help='Show current holdings status only')

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize database
    db = PostgresDatabaseManager()

    # Status check only
    if args.status:
        print(f"\n{'='*60}")
        print(f"  ETF Holdings Status Report ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'='*60}")

        summary = get_etf_holdings_summary(db, 'KR')
        print(f"  KR Region:")
        print(f"    - ETFs with holdings: {summary['etf_count']}")
        print(f"    - Total holdings:     {summary['holding_count']}")
        print(f"    - Latest date:        {summary['latest_date']}")

        # List ETFs with holdings
        etfs_with_holdings = get_etfs_with_holdings(db, 'KR')
        if etfs_with_holdings:
            print(f"\n  ETFs with holdings ({len(etfs_with_holdings)}):")
            for i, etf in enumerate(etfs_with_holdings[:20], 1):
                print(f"    {i:>3}. {etf}")
            if len(etfs_with_holdings) > 20:
                print(f"    ... and {len(etfs_with_holdings) - 20} more")

        print(f"{'='*60}\n")
        return

    # Validate region
    if args.region != 'KR':
        logger.error(f"Holdings collection for {args.region} is not yet supported")
        logger.info("Currently only KR is supported via KRX API")
        return

    # Initialize collector
    collector = ETFCollector(db_manager=db, skip_same_day=not args.force)

    # Process KR holdings
    logger.info(f"\n{'='*50}")
    logger.info(f"  Processing KR ETF Holdings")
    logger.info(f"{'='*50}")

    results = backfill_kr_holdings(
        collector=collector,
        force=args.force,
        limit=args.limit,
        ticker=args.ticker,
        as_of_date=args.date,
        priority_only=args.priority
    )

    # Final summary
    print(f"\n{'='*60}")
    print(f"  ETF Holdings Backfill Summary")
    print(f"{'='*60}")
    print(f"  Total ETFs:      {results.get('total', 0)}")
    print(f"  Collected:       {results.get('collected', 0)}")
    print(f"  Skipped:         {results.get('skipped', 0)}")
    print(f"  Failed:          {results.get('failed', 0)}")
    print(f"  Total Holdings:  {results.get('total_holdings', 0)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
