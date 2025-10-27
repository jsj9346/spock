#!/usr/bin/env python3
"""
Collect fundamental data for Korean stocks using DART API

Usage:
    python3 scripts/collect_kr_fundamentals.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.fundamental_data_collector import FundamentalDataCollector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Collect fundamental data for 5 major Korean stocks"""

    # Target tickers
    tickers = [
        '005930',  # Samsung Electronics
        '000660',  # SK Hynix
        '035720',  # Kakao
        '051910',  # LG Chem
        '006400'   # Samsung SDI
    ]

    logger.info("="*70)
    logger.info("📊 Collecting fundamental data for Korean stocks")
    logger.info("="*70)
    logger.info(f"Tickers: {', '.join(tickers)}")
    logger.info(f"Region: KR")
    logger.info(f"API: DART (Korean Financial Supervisory Service)")
    logger.info("="*70)

    # Initialize database and collector
    db = SQLiteDatabaseManager()
    collector = FundamentalDataCollector(db)

    # Collect fundamentals
    results = collector.collect_fundamentals(
        tickers=tickers,
        region='KR',
        force_refresh=True,
        batch_size=5
    )

    # Report results
    logger.info("\n" + "="*70)
    logger.info("📊 COLLECTION RESULTS")
    logger.info("="*70)

    for ticker, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"{ticker}: {status}")

    success_count = sum(1 for s in results.values() if s)
    logger.info("="*70)
    logger.info(f"Total: {len(tickers)} tickers")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {len(tickers) - success_count}")
    logger.info(f"Success rate: {success_count/len(tickers)*100:.1f}%")
    logger.info("="*70)

    return 0 if success_count == len(tickers) else 1

if __name__ == '__main__':
    exit(main())
