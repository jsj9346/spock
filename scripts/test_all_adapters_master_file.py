#!/usr/bin/env python3
"""
Test All Adapters Master File Integration

Tests master file integration and DB updates for all 5 market adapters.

Usage:
    python3 scripts/test_all_adapters_master_file.py
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters.us_adapter_kis import USAdapterKIS
from modules.market_adapters.hk_adapter_kis import HKAdapterKIS
from modules.market_adapters.jp_adapter_kis import JPAdapterKIS
from modules.market_adapters.cn_adapter_kis import CNAdapterKIS
from modules.market_adapters.vn_adapter_kis import VNAdapterKIS
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_adapter(adapter_name, adapter, db):
    """Test a single adapter"""
    logger.info(f"\n{'='*80}")
    logger.info(f"Testing {adapter_name} Adapter")
    logger.info(f"{'='*80}")

    try:
        # Scan stocks
        stocks = adapter.scan_stocks(force_refresh=True, use_master_file=True)

        if not stocks:
            logger.error(f"❌ {adapter_name}: No stocks returned from scan")
            return False

        logger.info(f"✅ {adapter_name}: {len(stocks)} stocks scanned")

        # Show sample
        if stocks:
            sample = stocks[0]
            logger.info(f"   Sample: {sample.get('ticker')} - {sample.get('name')}")

        # Check DB
        conn = db._get_connection()
        cursor = conn.cursor()

        region_code = adapter.REGION_CODE
        cursor.execute('SELECT COUNT(*) FROM tickers WHERE region=?', (region_code,))
        db_count = cursor.fetchone()[0]

        # Get ticker breakdown by exchange
        cursor.execute('''
            SELECT exchange, COUNT(*) as count
            FROM tickers
            WHERE region=?
            GROUP BY exchange
        ''', (region_code,))
        exchanges = cursor.fetchall()

        conn.close()

        logger.info(f"✅ {adapter_name}: {db_count:,} tickers in database")

        if exchanges:
            logger.info(f"   Exchange breakdown:")
            for exchange, count in exchanges:
                logger.info(f"     {exchange}: {count:,} tickers")

        # Validation
        if db_count == 0:
            logger.error(f"❌ {adapter_name}: No tickers in database!")
            return False

        if db_count != len(stocks):
            logger.warning(f"⚠️ {adapter_name}: Mismatch between scan ({len(stocks)}) and DB ({db_count})")

        return True

    except Exception as e:
        logger.error(f"❌ {adapter_name}: Test failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Test all adapters"""
    logger.info("="*80)
    logger.info("Master File Integration Test - All Adapters")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info("="*80)

    # Initialize
    db = SQLiteDatabaseManager()
    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        logger.error("❌ KIS API credentials not found in environment")
        logger.error("   Set KIS_APP_KEY and KIS_APP_SECRET environment variables")
        sys.exit(1)

    # Test all adapters
    results = {}

    # 1. US Adapter
    us_adapter = USAdapterKIS(db, app_key, app_secret)
    results['US'] = test_adapter('US', us_adapter, db)

    # 2. HK Adapter
    hk_adapter = HKAdapterKIS(db, app_key, app_secret)
    results['HK'] = test_adapter('HK', hk_adapter, db)

    # 3. JP Adapter
    jp_adapter = JPAdapterKIS(db, app_key, app_secret)
    results['JP'] = test_adapter('JP', jp_adapter, db)

    # 4. CN Adapter
    cn_adapter = CNAdapterKIS(db, app_key, app_secret)
    results['CN'] = test_adapter('CN', cn_adapter, db)

    # 5. VN Adapter
    vn_adapter = VNAdapterKIS(db, app_key, app_secret)
    results['VN'] = test_adapter('VN', vn_adapter, db)

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("Test Summary")
    logger.info(f"{'='*80}")

    passed = sum(1 for result in results.values() if result)
    failed = sum(1 for result in results.values() if not result)

    for region, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {region} Adapter")

    logger.info(f"\nTotal: {passed}/{len(results)} adapters passed ({passed/len(results)*100:.0f}%)")

    if failed > 0:
        logger.error(f"❌ {failed} adapters failed")
        sys.exit(1)
    else:
        logger.info("🎉 All adapters passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
