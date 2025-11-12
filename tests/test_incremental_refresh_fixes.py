#!/usr/bin/env python3
"""
Test Incremental Refresh Fixes

Verifies the two critical fixes for spock_refresh.py:
1. PostgresDatabaseManager.execute_many() implementation
2. stock_details.corp_code column addition

Author: Quant Platform Development Team
Date: 2025-11-12
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def test_execute_many():
    """Test 1: Verify execute_many() method works for batch ticker upsert"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: execute_many() Batch Ticker Upsert")
    logger.info("="*70)

    try:
        db = PostgresDatabaseManager()

        # Test query (same pattern as update_kr_tickers.py)
        upsert_query = """
        INSERT INTO tickers (ticker, name, region, exchange, currency, asset_type, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (ticker, region)
        DO UPDATE SET
            name = EXCLUDED.name,
            exchange = EXCLUDED.exchange,
            asset_type = EXCLUDED.asset_type,
            last_updated = NOW()
        """

        # Test records (sample Korean tickers)
        # Note: 6 values per tuple (last_updated is populated by NOW() in query)
        test_records = [
            ('TEST001', '테스트1', 'KR', 'KOSPI', 'KRW', 'STOCK'),
            ('TEST002', '테스트2', 'KR', 'KOSDAQ', 'KRW', 'STOCK'),
            ('TEST003', '테스트3', 'KR', 'KOSPI', 'KRW', 'ETF'),
        ]

        logger.info(f"Upserting {len(test_records)} test tickers...")
        rowcount = db.execute_many(upsert_query, test_records)

        logger.info(f"✅ execute_many() completed: {rowcount} rows affected")

        # Verify insertion
        verify_query = "SELECT ticker, name, region FROM tickers WHERE ticker LIKE 'TEST%' ORDER BY ticker"
        results = db.execute_query(verify_query)

        logger.info(f"\nVerification - Found {len(results)} test tickers:")
        for row in results:
            logger.info(f"   {row['ticker']}: {row['name']} ({row['region']})")

        # Cleanup
        cleanup_query = "DELETE FROM tickers WHERE ticker LIKE 'TEST%'"
        db.execute_update(cleanup_query)
        logger.info(f"\n✅ Cleanup completed")

        db.close_pool()
        return True

    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_corp_code_column():
    """Test 2: Verify stock_details.corp_code column exists and is queryable"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: stock_details.corp_code Column")
    logger.info("="*70)

    try:
        db = PostgresDatabaseManager()

        # Test 1: Verify column exists
        schema_query = """
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'stock_details' AND column_name = 'corp_code'
        """

        result = db.execute_query(schema_query)

        if not result:
            logger.error("❌ corp_code column not found in stock_details table")
            return False

        col_info = result[0]
        logger.info(f"✅ Column found: {col_info['column_name']}")
        logger.info(f"   Type: {col_info['data_type']}")
        logger.info(f"   Max Length: {col_info['character_maximum_length']}")

        # Test 2: Verify query works (same as backfill_fundamentals_dart.py)
        query_test = """
        SELECT ticker, corp_code
        FROM stock_details
        WHERE region = 'KR' AND corp_code IS NOT NULL
        LIMIT 5
        """

        results = db.execute_query(query_test)
        logger.info(f"\n✅ Query executed successfully")
        logger.info(f"   Found {len(results)} Korean stocks with corp_code")

        if results:
            for row in results:
                logger.info(f"   {row['ticker']}: {row['corp_code']}")
        else:
            logger.info("   (No corp_codes populated yet - this is expected)")

        # Test 3: Insert test data (must create ticker first due to foreign key)
        # Create ticker
        ticker_insert = """
        INSERT INTO tickers (ticker, name, region, exchange, currency, asset_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region) DO NOTHING
        """
        db.execute_update(ticker_insert, ('TEST004', '테스트주식', 'KR', 'KOSPI', 'KRW', 'STOCK'))

        # Insert stock_details with corp_code
        stock_details_insert = """
        INSERT INTO stock_details (ticker, region, sector, corp_code)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker, region)
        DO UPDATE SET corp_code = EXCLUDED.corp_code
        """

        db.execute_update(stock_details_insert, ('TEST004', 'KR', '테스트', '00000001'))
        logger.info(f"\n✅ Insert test passed")

        # Verify insertion
        verify = db.execute_query(
            "SELECT ticker, corp_code FROM stock_details WHERE ticker = 'TEST004'"
        )

        if verify and verify[0]['corp_code'] == '00000001':
            logger.info(f"✅ corp_code value correctly stored: {verify[0]['corp_code']}")
        else:
            logger.error(f"❌ corp_code verification failed")
            return False

        # Cleanup (CASCADE will delete stock_details automatically)
        db.execute_update("DELETE FROM tickers WHERE ticker = 'TEST004'")
        logger.info(f"\n✅ Cleanup completed")

        db.close_pool()
        return True

    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "="*70)
    logger.info("🧪 INCREMENTAL REFRESH FIXES VERIFICATION")
    logger.info("="*70)

    results = {
        'execute_many': test_execute_many(),
        'corp_code_column': test_corp_code_column()
    }

    logger.info("\n" + "="*70)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("="*70)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        logger.info("\n🎉 ALL TESTS PASSED - Incremental refresh fixes verified!")
        return 0
    else:
        logger.error("\n❌ SOME TESTS FAILED - Please review errors above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
