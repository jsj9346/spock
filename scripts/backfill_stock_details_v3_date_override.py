#!/usr/bin/env python3
"""
Sector Backfill Script v3 - Date Override Edition

System date workaround: Uses 2024-10-13 as reference date for API calls
instead of datetime.now() to avoid future date issues.

This allows sector backfill to work even when system date is 2025.

Author: Spock Trading System
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.api_clients.krx_data_api import KRXDataAPI
from modules.api_clients.pykrx_api import PyKRXAPI
from modules.api_clients.kis_domestic_stock_api import KISDomesticStockAPI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_sector_backfill_v3.log')
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# DATE OVERRIDE CONFIGURATION
# ==========================================
# Use 2024-10-13 as reference date instead of system date
REFERENCE_DATE = datetime(2024, 10, 13)

logger.warning("=" * 80)
logger.warning("⚠️ DATE OVERRIDE MODE ACTIVE")
logger.warning(f"System Date: {datetime.now().strftime('%Y-%m-%d')}")
logger.warning(f"Reference Date (for APIs): {REFERENCE_DATE.strftime('%Y-%m-%d')}")
logger.warning("This allows sector backfill to work with 2025 system date")
logger.warning("=" * 80)


class KRXDataAPIDateOverride(KRXDataAPI):
    """KRX Data API with date override for get_sector_classification"""

    def get_sector_classification(self, market: str = 'ALL') -> Dict[str, Dict]:
        """
        업종 분류 현황 조회 (날짜 오버라이드 버전)

        Uses REFERENCE_DATE (2024-10-13) instead of datetime.now()
        to avoid future date issues when system date is 2025.
        """
        # Try multiple dates going backwards from REFERENCE_DATE
        for days_back in [0, 1, 2, 3, 7, 14, 30, 60, 90, 180, 280]:
            try_date = (REFERENCE_DATE - timedelta(days=days_back)).strftime("%Y%m%d")

            data = {
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT03901',
                'locale': 'ko_KR',
                'mktId': market,
                'trdDd': try_date,
                'csvxls_isNo': 'false',
            }

            try:
                response = self.session.post(self.BASE_URL, data=data, timeout=10)
                response.raise_for_status()
                result = response.json()

                data_block = result.get('OutBlock_1', result.get('block1', []))

                sector_map = {}
                for item in data_block:
                    ticker = item.get('ISU_SRT_CD')
                    if not ticker:
                        continue

                    sector_map[ticker] = {
                        'sector': item.get('IDX_IND_NM'),
                        'sector_code': item.get('IDX_IND_CD'),
                        'industry': item.get('IDX_NM'),
                        'industry_code': item.get('IDX_CD'),
                    }

                if sector_map:
                    logger.info(f"✅ KRX API (Date Override): {len(sector_map)}개 종목 업종 조회 (date: {try_date})")
                    return sector_map

                if days_back < 280:
                    logger.debug(f"⚠️ KRX API returned 0 results for {try_date}, trying older date...")
                    continue
                else:
                    logger.warning(f"⚠️ KRX API returned 0 results for all attempted dates")
                    return {}

            except Exception as e:
                if days_back < 280:
                    logger.debug(f"⚠️ KRX API failed for {try_date}: {e}, trying next...")
                    continue
                else:
                    logger.error(f"❌ KRX API failed for all dates: {e}")
                    raise

        return {}


class PyKRXAPIDateOverride(PyKRXAPI):
    """PyKRX API with date override for get_stock_sector_info"""

    def get_stock_sector_info(self, ticker: str) -> Dict:
        """
        종목 업종 분류 조회 (날짜 오버라이드 버전)

        Uses REFERENCE_DATE (2024-10-13) instead of datetime.now()
        """
        from pykrx import stock

        # Try dates: yesterday, -2d, -3d, -7d, -14d, -30d, -60d, -90d, -180d, -280d
        for days_back in [1, 2, 3, 7, 14, 30, 60, 90, 180, 280]:
            try_date = (REFERENCE_DATE - timedelta(days=days_back)).strftime("%Y%m%d")

            try:
                sector_info = stock.get_market_sector_classifications(ticker, try_date)

                if not sector_info.empty and '섹터' in sector_info.columns:
                    sector = sector_info['섹터'].iloc[0]
                    industry = sector_info.get('산업', pd.Series([None])).iloc[0]

                    logger.debug(f"✅ [{ticker}] PyKRX (Date Override): 섹터={sector}, 업종={industry} (date: {try_date})")

                    return {
                        'sector': sector,
                        'industry': industry or sector,
                        'data_source': 'PyKRX',
                        'retrieved_date': try_date
                    }

                # Empty result, try next date
                if days_back < 280:
                    continue
                else:
                    logger.warning(f"⚠️ [{ticker}] PyKRX returned no sector for all dates")
                    return {}

            except Exception as e:
                if days_back < 280:
                    logger.debug(f"⚠️ [{ticker}] PyKRX failed for {try_date}: {e}, trying next...")
                    continue
                else:
                    logger.warning(f"⚠️ [{ticker}] PyKRX failed for all dates: {e}")
                    return {}

        return {}


def backfill_sectors_with_krx(
    db: SQLiteDatabaseManager,
    krx_api: KRXDataAPIDateOverride,
    dry_run: bool = False,
    limit: int = None
) -> Tuple[int, int, int]:
    """
    KRX API를 사용한 섹터 일괄 백필 (날짜 오버라이드)

    Returns:
        (success_count, skipped_count, failed_count)
    """
    logger.info("=" * 80)
    logger.info("📊 Phase 1: KRX API Sector Backfill (Batch Mode)")
    logger.info("=" * 80)

    try:
        # Fetch sector classification from KRX (all stocks at once)
        sector_map = krx_api.get_sector_classification(market='ALL')

        if not sector_map:
            logger.error("❌ KRX API returned no sector data")
            return (0, 0, 0)

        logger.info(f"✅ KRX API: {len(sector_map)}개 종목 업종 분류 조회 완료")

        # Get stocks that need sector update
        stocks = db.get_stocks_without_sector(limit=limit)
        logger.info(f"📌 DB에서 {len(stocks)}개 종목 섹터 업데이트 필요")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        success, skipped, failed = 0, 0, 0

        for stock in stocks:
            ticker = stock['ticker']

            # Check if sector exists in KRX data
            if ticker not in sector_map:
                logger.debug(f"⏭️ [{ticker}] KRX 데이터에 없음 (ETF 또는 비상장 종목)")
                skipped += 1
                continue

            sector_info = sector_map[ticker]

            if not dry_run:
                # Update database
                db.update_stock_sector(
                    ticker=ticker,
                    sector=sector_info['sector'],
                    industry=sector_info['industry'],
                    sector_code=sector_info['sector_code'],
                    industry_code=sector_info['industry_code']
                )

            logger.info(
                f"✅ [{ticker}] {stock['name']}: "
                f"섹터={sector_info['sector']}, 업종={sector_info['industry']}"
                f"{' (DRY RUN)' if dry_run else ''}"
            )
            success += 1

        logger.info("=" * 80)
        logger.info(f"✅ Phase 1 Complete: Success={success}, Skipped={skipped}, Failed={failed}")
        logger.info("=" * 80)

        return (success, skipped, failed)

    except Exception as e:
        logger.error(f"❌ KRX API Sector Backfill failed: {e}")
        return (0, 0, 0)


def backfill_sectors_with_pykrx(
    db: SQLiteDatabaseManager,
    pykrx_api: PyKRXAPIDateOverride,
    dry_run: bool = False,
    limit: int = None
) -> Tuple[int, int, int]:
    """
    PyKRX API를 사용한 섹터 백필 (개별 조회, 날짜 오버라이드)

    Note: Rate limit 1 req/sec due to PyKRX implementation

    Returns:
        (success_count, skipped_count, failed_count)
    """
    import time

    logger.info("=" * 80)
    logger.info("📊 Phase 2: PyKRX API Sector Backfill (Individual Mode)")
    logger.info("⚠️ Rate Limit: 1 request/sec (will take ~30 min for 2,000 stocks)")
    logger.info("=" * 80)

    # Get stocks that still need sector
    stocks = db.get_stocks_without_sector(limit=limit)

    if not stocks:
        logger.info("✅ All stocks already have sector information")
        return (0, 0, 0)

    logger.info(f"📌 {len(stocks)}개 종목 처리 필요")

    if dry_run:
        logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

    success, skipped, failed = 0, 0, 0

    for idx, stock in enumerate(stocks, 1):
        ticker = stock['ticker']

        try:
            # Rate limiting: 1 request per second
            if idx > 1:
                time.sleep(1.0)

            # Fetch sector info
            sector_info = pykrx_api.get_stock_sector_info(ticker)

            if not sector_info:
                logger.warning(f"⏭️ [{ticker}] {stock['name']}: 섹터 정보 없음")
                skipped += 1
                continue

            if not dry_run:
                # Update database
                db.update_stock_sector(
                    ticker=ticker,
                    sector=sector_info['sector'],
                    industry=sector_info.get('industry', sector_info['sector']),
                    sector_code=None,
                    industry_code=None
                )

            logger.info(
                f"✅ [{idx}/{len(stocks)}] [{ticker}] {stock['name']}: "
                f"섹터={sector_info['sector']}"
                f"{' (DRY RUN)' if dry_run else ''}"
            )
            success += 1

        except Exception as e:
            logger.error(f"❌ [{ticker}] {stock['name']}: {e}")
            failed += 1

    logger.info("=" * 80)
    logger.info(f"✅ Phase 2 Complete: Success={success}, Skipped={skipped}, Failed={failed}")
    logger.info("=" * 80)

    return (success, skipped, failed)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Sector Backfill v3 - Date Override Edition')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--limit', type=int, help='Limit number of stocks to process')
    parser.add_argument('--pykrx-only', action='store_true', help='Use only PyKRX API (skip KRX batch)')
    parser.add_argument('--skip-pykrx', action='store_true', help='Skip PyKRX fallback (KRX only)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Sector Backfill v3 - Date Override Edition")
    logger.info("=" * 80)
    logger.info(f"Reference Date: {REFERENCE_DATE.strftime('%Y-%m-%d')}")
    logger.info(f"System Date: {datetime.now().strftime('%Y-%m-%d')}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    if args.limit:
        logger.info(f"Limit: {args.limit} stocks")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    krx_api = KRXDataAPIDateOverride()
    pykrx_api = PyKRXAPIDateOverride()

    total_success, total_skipped, total_failed = 0, 0, 0

    # Phase 1: KRX API (batch mode)
    if not args.pykrx_only:
        success1, skipped1, failed1 = backfill_sectors_with_krx(
            db=db,
            krx_api=krx_api,
            dry_run=args.dry_run,
            limit=args.limit
        )
        total_success += success1
        total_skipped += skipped1
        total_failed += failed1

    # Phase 2: PyKRX API (fallback for remaining stocks)
    if not args.skip_pykrx:
        success2, skipped2, failed2 = backfill_sectors_with_pykrx(
            db=db,
            pykrx_api=pykrx_api,
            dry_run=args.dry_run,
            limit=args.limit
        )
        total_success += success2
        total_skipped += skipped2
        total_failed += failed2

    # Final Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("📊 FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Success: {total_success}")
    logger.info(f"⏭️ Skipped: {total_skipped}")
    logger.info(f"❌ Failed: {total_failed}")
    logger.info("=" * 80)

    # Show updated coverage
    stats = db.get_sector_coverage_stats()
    logger.info(f"📈 Current Sector Coverage: {stats['with_sector']}/{stats['total']} "
                f"({stats['coverage_percent']:.1f}%)")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
