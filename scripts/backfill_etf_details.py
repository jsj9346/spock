#!/usr/bin/env python3
"""
ETF Details Backfill Script

다중 리전 ETF 상세정보를 수집하여 etf_details 테이블에 저장합니다.

지원 리전:
- KR: KIS API + yfinance fallback (1,045개 ETF)
- US: yfinance (주요 ETF 목록 등록 필요)
- JP: yfinance (주요 ETF 목록 등록 필요)
- HK: yfinance (주요 ETF 목록 등록 필요)
- CN: yfinance (주요 ETF 목록 등록 필요)
- VN: yfinance (제한적)

사용법:
    # KR ETF 전체 수집
    python scripts/backfill_etf_details.py --region KR

    # 특정 ETF만 수집
    python scripts/backfill_etf_details.py --region KR --ticker 069500

    # 강제 재수집
    python scripts/backfill_etf_details.py --region KR --force

    # US ETF 등록 및 수집
    python scripts/backfill_etf_details.py --region US --register-etfs

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
from modules.constants.regions import VALID_REGIONS


# =============================================================================
# Pre-defined ETF Lists for Registration
# =============================================================================

# 주요 US ETF 목록
US_MAJOR_ETFS = [
    # Broad Market
    ('SPY', 'SPDR S&P 500 ETF Trust'),
    ('IVV', 'iShares Core S&P 500 ETF'),
    ('VOO', 'Vanguard S&P 500 ETF'),
    ('QQQ', 'Invesco QQQ Trust'),
    ('VTI', 'Vanguard Total Stock Market ETF'),
    ('IWM', 'iShares Russell 2000 ETF'),
    ('DIA', 'SPDR Dow Jones Industrial Average ETF'),
    # Sector ETFs
    ('XLK', 'Technology Select Sector SPDR'),
    ('XLF', 'Financial Select Sector SPDR'),
    ('XLV', 'Health Care Select Sector SPDR'),
    ('XLE', 'Energy Select Sector SPDR'),
    ('XLI', 'Industrial Select Sector SPDR'),
    ('XLP', 'Consumer Staples Select Sector SPDR'),
    ('XLY', 'Consumer Discretionary Select Sector SPDR'),
    ('XLU', 'Utilities Select Sector SPDR'),
    ('XLRE', 'Real Estate Select Sector SPDR'),
    ('XLB', 'Materials Select Sector SPDR'),
    ('XLC', 'Communication Services Select Sector SPDR'),
    # International
    ('EEM', 'iShares MSCI Emerging Markets ETF'),
    ('VEA', 'Vanguard FTSE Developed Markets ETF'),
    ('VWO', 'Vanguard FTSE Emerging Markets ETF'),
    ('EFA', 'iShares MSCI EAFE ETF'),
    ('IEFA', 'iShares Core MSCI EAFE ETF'),
    # Bond ETFs
    ('BND', 'Vanguard Total Bond Market ETF'),
    ('AGG', 'iShares Core U.S. Aggregate Bond ETF'),
    ('LQD', 'iShares iBoxx $ Investment Grade Corporate Bond ETF'),
    ('HYG', 'iShares iBoxx $ High Yield Corporate Bond ETF'),
    ('TLT', 'iShares 20+ Year Treasury Bond ETF'),
    ('SHY', 'iShares 1-3 Year Treasury Bond ETF'),
    ('IEF', 'iShares 7-10 Year Treasury Bond ETF'),
    # Commodity & Alternative
    ('GLD', 'SPDR Gold Shares'),
    ('SLV', 'iShares Silver Trust'),
    ('USO', 'United States Oil Fund'),
    ('DBC', 'Invesco DB Commodity Index Tracking Fund'),
    # Dividend
    ('VYM', 'Vanguard High Dividend Yield ETF'),
    ('SCHD', 'Schwab U.S. Dividend Equity ETF'),
    ('DVY', 'iShares Select Dividend ETF'),
    # Growth & Value
    ('VUG', 'Vanguard Growth ETF'),
    ('VTV', 'Vanguard Value ETF'),
    ('IWF', 'iShares Russell 1000 Growth ETF'),
    ('IWD', 'iShares Russell 1000 Value ETF'),
    # Leveraged & Inverse
    ('TQQQ', 'ProShares UltraPro QQQ'),
    ('SQQQ', 'ProShares UltraPro Short QQQ'),
    ('UPRO', 'ProShares UltraPro S&P500'),
    ('SPXU', 'ProShares UltraPro Short S&P500'),
    ('SOXL', 'Direxion Daily Semiconductor Bull 3X'),
    ('SOXS', 'Direxion Daily Semiconductor Bear 3X'),
    # Country Specific
    ('FXI', 'iShares China Large-Cap ETF'),
    ('EWJ', 'iShares MSCI Japan ETF'),
    ('EWZ', 'iShares MSCI Brazil ETF'),
    ('EWY', 'iShares MSCI South Korea ETF'),
    ('VNM', 'VanEck Vietnam ETF'),
]

# 주요 JP ETF 목록 (TSE)
JP_MAJOR_ETFS = [
    ('1306', 'TOPIX ETF'),
    ('1321', 'Nikkei 225 ETF'),
    ('1330', 'Nikko TOPIX ETF'),
    ('1346', 'MAXIS Nikkei 225 ETF'),
    ('1348', 'MAXIS TOPIX ETF'),
    ('1570', 'Nikkei Leveraged ETF'),
    ('1357', 'Nikkei Inverse ETF'),
    ('1458', 'TOPIX Inverse ETF'),
    ('2523', 'MAXiS MSCI Japan High Dividend ETF'),
    ('2559', 'MAXIS All Country World Equity ETF'),
]

# 주요 HK ETF 목록 (HKEX)
HK_MAJOR_ETFS = [
    ('2800', 'Tracker Fund of Hong Kong'),
    ('2828', 'Hang Seng China Enterprises Index ETF'),
    ('2833', 'Hang Seng Index ETF'),
    ('3033', 'CSOP Hang Seng TECH Index ETF'),
    ('3067', 'iShares Hang Seng TECH ETF'),
    ('3188', 'China AMC CSI 300 Index ETF'),
    ('2823', 'iShares FTSE A50 China Index ETF'),
    ('3110', 'Global X Hang Seng High Dividend Yield ETF'),
    ('3115', 'iShares Core Hang Seng Index ETF'),
    ('2822', 'CSOP FTSE China A50 ETF'),
]

# 주요 CN ETF 목록 (SSE/SZSE)
CN_MAJOR_ETFS = [
    ('510050', 'China 50 ETF'),  # SSE
    ('510300', 'Huatai CSI 300 ETF'),  # SSE
    ('510500', 'CSI 500 ETF'),  # SSE
    ('510880', 'ICBC Dividend ETF'),  # SSE
    ('159901', 'SZSE 100 ETF'),  # SZSE
    ('159915', 'GEM ETF'),  # SZSE (Growth Enterprise Market)
    ('159919', 'CSI 300 ETF'),  # SZSE
    ('159922', 'CSI 500 ETF'),  # SZSE
    ('512000', 'Securities ETF'),  # SSE
    ('512880', 'Securities Industry ETF'),  # SSE
]


# =============================================================================
# ETF Registration Functions
# =============================================================================

def register_etf_tickers(db: PostgresDatabaseManager, etf_list: List[tuple], region: str) -> int:
    """
    ETF 목록을 tickers 테이블에 등록

    Args:
        db: Database manager
        etf_list: List of (ticker, name) tuples
        region: Region code

    Returns:
        Number of registered ETFs
    """
    # Region별 exchange와 currency 매핑
    region_config = {
        'US': {'exchange': 'NYSE', 'currency': 'USD'},
        'JP': {'exchange': 'TSE', 'currency': 'JPY'},
        'HK': {'exchange': 'HKEX', 'currency': 'HKD'},
        'CN': {'exchange': 'SSE', 'currency': 'CNY'},
        'VN': {'exchange': 'HOSE', 'currency': 'VND'},
        'KR': {'exchange': 'KRX', 'currency': 'KRW'},
    }

    config = region_config.get(region, {'exchange': 'UNKNOWN', 'currency': 'USD'})

    query = """
    INSERT INTO tickers (ticker, region, name, exchange, currency, asset_type, is_active, data_source)
    VALUES (%s, %s, %s, %s, %s, 'ETF', TRUE, 'manual')
    ON CONFLICT (ticker, region) DO UPDATE SET
        name = COALESCE(EXCLUDED.name, tickers.name),
        exchange = COALESCE(EXCLUDED.exchange, tickers.exchange),
        currency = COALESCE(EXCLUDED.currency, tickers.currency),
        asset_type = 'ETF',
        is_active = TRUE,
        last_updated = NOW()
    """

    registered = 0
    for ticker, name in etf_list:
        try:
            if db.execute_update(query, (ticker, region, name, config['exchange'], config['currency'])):
                registered += 1
                logger.info(f"✅ [{region}] Registered ETF: {ticker} - {name}")
        except Exception as e:
            logger.error(f"❌ [{region}] Failed to register {ticker}: {e}")

    return registered


def get_etf_count(db: PostgresDatabaseManager, region: str) -> int:
    """데이터베이스의 ETF 개수 조회"""
    query = """
    SELECT COUNT(*) as count FROM tickers
    WHERE region = %s AND asset_type = 'ETF' AND is_active = TRUE
    """
    result = db.execute_query(query, (region,))
    return result[0]['count'] if result else 0


def get_etf_details_count(db: PostgresDatabaseManager, region: str) -> int:
    """etf_details 테이블의 레코드 수 조회"""
    query = """
    SELECT COUNT(*) as count FROM etf_details WHERE region = %s
    """
    result = db.execute_query(query, (region,))
    return result[0]['count'] if result else 0


# =============================================================================
# Main Backfill Functions
# =============================================================================

def backfill_region(
    collector: ETFCollector,
    region: str,
    force: bool = False,
    limit: Optional[int] = None,
    ticker: Optional[str] = None
) -> Dict[str, int]:
    """
    특정 리전의 ETF 상세정보 백필

    Args:
        collector: ETFCollector instance
        region: Region code
        force: Force re-collection
        limit: Limit number of ETFs
        ticker: Specific ticker to collect

    Returns:
        Collection results
    """
    if ticker:
        # 단일 ETF 수집
        logger.info(f"[{region}] Collecting single ETF: {ticker}")
        success = collector.collect_and_save_details(ticker, region)
        return {
            'total': 1,
            'collected': 1 if success else 0,
            'skipped': 0,
            'failed': 0 if success else 1
        }

    # 배치 수집
    tickers = collector.get_etf_tickers_from_db(region)

    if not tickers:
        logger.warning(f"[{region}] No ETF tickers found in database")
        return {'total': 0, 'collected': 0, 'skipped': 0, 'failed': 0}

    if limit:
        tickers = tickers[:limit]

    logger.info(f"[{region}] Starting backfill for {len(tickers)} ETFs")

    return collector.collect_batch_details(tickers, region, force=force)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="ETF Details Backfill Script")
    parser.add_argument('--region', type=str, default='KR',
                        choices=VALID_REGIONS + ['ALL'],
                        help='Region to backfill')
    parser.add_argument('--ticker', type=str, help='Specific ETF ticker')
    parser.add_argument('--force', action='store_true', help='Force re-collection')
    parser.add_argument('--limit', type=int, help='Limit number of ETFs')
    parser.add_argument('--register-etfs', action='store_true',
                        help='Register pre-defined ETF list to tickers table')
    parser.add_argument('--status', action='store_true',
                        help='Show current ETF status only')

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Initialize database
    db = PostgresDatabaseManager()

    # Status check only
    if args.status:
        print(f"\n{'='*60}")
        print(f"  ETF Status Report ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        print(f"{'='*60}")

        for region in ['KR', 'US', 'JP', 'HK', 'CN', 'VN']:
            etf_count = get_etf_count(db, region)
            details_count = get_etf_details_count(db, region)
            print(f"  {region}: {etf_count:>5} ETFs in tickers, {details_count:>5} in etf_details")

        print(f"{'='*60}\n")
        return

    # Register ETFs if requested
    if args.register_etfs:
        regions_to_register = {
            'US': US_MAJOR_ETFS,
            'JP': JP_MAJOR_ETFS,
            'HK': HK_MAJOR_ETFS,
            'CN': CN_MAJOR_ETFS,
        }

        if args.region == 'ALL':
            for region, etf_list in regions_to_register.items():
                count = register_etf_tickers(db, etf_list, region)
                logger.info(f"[{region}] Registered {count} ETFs")
        elif args.region in regions_to_register:
            count = register_etf_tickers(db, regions_to_register[args.region], args.region)
            logger.info(f"[{args.region}] Registered {count} ETFs")
        else:
            logger.warning(f"[{args.region}] No pre-defined ETF list available")
        return

    # Initialize collector
    collector = ETFCollector(db_manager=db, skip_same_day=not args.force)

    # Determine regions to process
    if args.region == 'ALL':
        regions = ['KR', 'US', 'JP', 'HK', 'CN', 'VN']
    else:
        regions = [args.region]

    # Process each region
    total_results = {
        'total': 0,
        'collected': 0,
        'skipped': 0,
        'failed': 0
    }

    for region in regions:
        logger.info(f"\n{'='*50}")
        logger.info(f"  Processing Region: {region}")
        logger.info(f"{'='*50}")

        results = backfill_region(
            collector=collector,
            region=region,
            force=args.force,
            limit=args.limit,
            ticker=args.ticker
        )

        # Aggregate results
        for key in total_results:
            total_results[key] += results.get(key, 0)

        logger.info(f"[{region}] Results: {results}")

    # Final summary
    print(f"\n{'='*60}")
    print(f"  ETF Details Backfill Summary")
    print(f"{'='*60}")
    print(f"  Total:     {total_results['total']}")
    print(f"  Collected: {total_results['collected']}")
    print(f"  Skipped:   {total_results['skipped']}")
    print(f"  Failed:    {total_results['failed']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
