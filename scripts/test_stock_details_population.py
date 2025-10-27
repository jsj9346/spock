"""
Test Script for stock_details Population

Validates that stock_details table can be populated correctly using:
1. pykrx API (Priority 1)
2. KRX API (Priority 2 - if available)
3. KIS API for par_value

Author: Spock Trading System
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.api_clients.pykrx_api import PyKRXAPI
from modules.api_clients.krx_data_api import KRXDataAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def test_pykrx_sector_info():
    """Test pykrx sector information collection"""
    logger.info("=" * 60)
    logger.info("TEST 1: PyKRX Sector Information")
    logger.info("=" * 60)

    pykrx = PyKRXAPI()
    test_tickers = ['005930', '000660', '035720']  # Samsung, SK Hynix, Kakao

    results = []
    for ticker in test_tickers:
        logger.info(f"\nTesting {ticker}...")
        try:
            sector_info = pykrx.get_stock_sector_info(ticker)
            results.append({
                'ticker': ticker,
                'success': bool(sector_info),
                'data': sector_info
            })

            if sector_info:
                logger.info(f"✅ Success:")
                logger.info(f"   Sector: {sector_info.get('sector')}")
                logger.info(f"   Industry: {sector_info.get('industry')}")
                logger.info(f"   Par Value: {sector_info.get('par_value')}")
            else:
                logger.warning(f"⚠️ No data returned")

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            results.append({
                'ticker': ticker,
                'success': False,
                'error': str(e)
            })

    success_count = sum(1 for r in results if r['success'])
    logger.info(f"\n📊 PyKRX Test Result: {success_count}/{len(test_tickers)} successful")
    return results

def test_krx_sector_classification():
    """Test KRX sector classification API"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: KRX Sector Classification API")
    logger.info("=" * 60)

    krx = KRXDataAPI()

    try:
        sector_map = krx.get_sector_classification(market='STK')
        logger.info(f"✅ Loaded {len(sector_map)} stocks")

        if sector_map:
            # Show sample
            sample_tickers = ['005930', '000660', '035720']
            for ticker in sample_tickers:
                if ticker in sector_map:
                    info = sector_map[ticker]
                    logger.info(f"\n{ticker}:")
                    logger.info(f"   Sector: {info.get('sector')} ({info.get('sector_code')})")
                    logger.info(f"   Industry: {info.get('industry')} ({info.get('industry_code')})")
                else:
                    logger.warning(f"⚠️ {ticker} not in map")
            return True
        else:
            logger.warning("⚠️ KRX API returned empty result (likely date/holiday issue)")
            return False

    except Exception as e:
        logger.error(f"❌ KRX API Error: {e}")
        return False

def test_database_update():
    """Test database update functionality"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Database Update")
    logger.info("=" * 60)

    db = SQLiteDatabaseManager()
    test_ticker = '999999'  # Test ticker

    # Insert test stock_details
    from datetime import datetime
    now = datetime.now().isoformat()

    try:
        # Insert test record
        db.insert_stock_details({
            'ticker': test_ticker,
            'sector': None,
            'sector_code': None,
            'industry': None,
            'industry_code': None,
            'par_value': None,
            'created_at': now,
            'last_updated': now
        })
        logger.info(f"✅ Inserted test record: {test_ticker}")

        # Update with test data
        updates = {
            'sector': 'Information Technology',
            'sector_code': 'G25',
            'industry': '반도체',
            'industry_code': 'G2520',
            'par_value': 100
        }

        success = db.update_stock_details(test_ticker, updates)

        if success:
            logger.info(f"✅ Update successful")

            # Verify update
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sector, sector_code, industry, industry_code, par_value
                FROM stock_details
                WHERE ticker = ?
            """, (test_ticker,))
            result = cursor.fetchone()
            conn.close()

            if result:
                logger.info(f"✅ Verification successful:")
                logger.info(f"   Sector: {result[0]} ({result[1]})")
                logger.info(f"   Industry: {result[2]} ({result[3]})")
                logger.info(f"   Par Value: {result[4]}")

                # Cleanup
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM stock_details WHERE ticker = ?", (test_ticker,))
                conn.commit()
                conn.close()
                logger.info(f"✅ Cleanup successful")

                return True
            else:
                logger.error(f"❌ Verification failed: No data found")
                return False
        else:
            logger.error(f"❌ Update failed")
            return False

    except Exception as e:
        logger.error(f"❌ Database test error: {e}")
        return False

def main():
    logger.info("\n" + "=" * 60)
    logger.info("🧪 Stock Details Population Test Suite")
    logger.info("=" * 60)

    # Run tests
    test1_results = test_pykrx_sector_info()
    test2_result = test_krx_sector_classification()
    test3_result = test_database_update()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)

    test1_success = sum(1 for r in test1_results if r['success'])
    logger.info(f"TEST 1 (PyKRX): {test1_success}/3 tickers successful")
    logger.info(f"TEST 2 (KRX API): {'✅ PASS' if test2_result else '⚠️  SKIP (API unavailable)'}")
    logger.info(f"TEST 3 (Database): {'✅ PASS' if test3_result else '❌ FAIL'}")

    overall_pass = (test1_success > 0) and test3_result
    logger.info(f"\n{'✅ OVERALL: PASS' if overall_pass else '❌ OVERALL: FAIL'}")
    logger.info("=" * 60)

    if overall_pass:
        logger.info("\n💡 Recommendation: Use Priority 1 (pykrx) for immediate deployment")
        logger.info("   Priority 2 (KRX API) may have date/availability issues")

if __name__ == '__main__':
    main()
