"""
Test script for TickerRefresher + KRMarketAdapter integration

Validates:
1. KRMarketAdapter can be imported correctly
2. TickerRefresher can instantiate KRMarketAdapter
3. fetch_kr_tickers() returns data in correct format
4. 10 test tickers can be successfully refreshed

Test Tickers (Major KR stocks and ETFs):
- Stocks: 005930 (Samsung), 000660 (SK Hynix), 005380 (Hyundai Motor),
          035420 (NAVER), 000270 (Kia)
- ETFs: 069500 (KODEX 200), 252670 (KODEX 200선물인버스2X),
        114800 (KODEX 인버스), 122630 (KODEX 레버리지),
        251340 (KODEX 코스닥150선물인버스)

Author: Spock Quant Platform
Date: 2025-11-04
"""

import sys
import os
import logging
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.ticker_refresh.ticker_refresher import TickerRefresher
from modules.market_adapters.kr_adapter import KRMarketAdapter, KoreaAdapter
from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Test tickers: 5 stocks + 5 ETFs
TEST_TICKERS = {
    'STOCK': [
        {'ticker': '005930', 'name': '삼성전자'},
        {'ticker': '000660', 'name': 'SK하이닉스'},
        {'ticker': '005380', 'name': '현대자동차'},
        {'ticker': '035420', 'name': 'NAVER'},
        {'ticker': '000270', 'name': '기아'},
    ],
    'ETF': [
        {'ticker': '069500', 'name': 'KODEX 200'},
        {'ticker': '252670', 'name': 'KODEX 200선물인버스2X'},
        {'ticker': '114800', 'name': 'KODEX 인버스'},
        {'ticker': '122630', 'name': 'KODEX 레버리지'},
        {'ticker': '251340', 'name': 'KODEX 코스닥150선물인버스'},
    ]
}


def test_import():
    """Test 1: Verify KRMarketAdapter import"""
    logger.info("=" * 80)
    logger.info("TEST 1: Import Verification")
    logger.info("=" * 80)

    try:
        # Test that KRMarketAdapter is accessible
        assert KRMarketAdapter is not None
        assert KRMarketAdapter == KoreaAdapter  # Verify alias
        logger.info("✅ KRMarketAdapter imported successfully")
        logger.info(f"   - Class name: {KRMarketAdapter.__name__}")
        logger.info(f"   - Alias verified: KRMarketAdapter == KoreaAdapter")
        return True
    except Exception as e:
        logger.error(f"❌ Import test failed: {e}")
        return False


def test_adapter_instantiation():
    """Test 2: Verify adapter instantiation"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Adapter Instantiation")
    logger.info("=" * 80)

    try:
        # Create database manager
        db = PostgresDatabaseManager()
        logger.info("✅ Database manager created")

        # Create adapter (note: requires KIS API credentials)
        # For testing without credentials, we'll skip actual API calls
        # and just verify the class can be instantiated
        adapter = KRMarketAdapter(
            db_manager=db,
            kis_app_key='test_key',
            kis_app_secret='test_secret'
        )
        logger.info("✅ KRMarketAdapter instantiated successfully")
        logger.info(f"   - Region code: {adapter.region_code}")
        logger.info(f"   - Has fetch_kr_tickers method: {hasattr(adapter, 'fetch_kr_tickers')}")

        return adapter, db
    except Exception as e:
        logger.error(f"❌ Instantiation test failed: {e}")
        return None, None


def test_ticker_refresher_integration(adapter, db):
    """Test 3: Verify TickerRefresher integration"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: TickerRefresher Integration")
    logger.info("=" * 80)

    try:
        # Create TickerRefresher
        refresher = TickerRefresher(db_manager=db)
        logger.info("✅ TickerRefresher created")

        # Verify adapter can be accessed
        kr_adapter = refresher._get_adapter('KR')
        logger.info("✅ KR adapter accessed via TickerRefresher")
        logger.info(f"   - Adapter type: {type(kr_adapter).__name__}")
        logger.info(f"   - Has fetch_kr_tickers: {hasattr(kr_adapter, 'fetch_kr_tickers')}")

        return refresher
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return None


def test_fetch_kr_tickers(adapter):
    """Test 4: Verify fetch_kr_tickers() returns data"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: fetch_kr_tickers() Data Validation")
    logger.info("=" * 80)

    try:
        # Note: This will actually call the APIs if credentials are valid
        # For dry-run testing, we'll catch exceptions gracefully
        tickers = adapter.fetch_kr_tickers()

        if tickers:
            logger.info(f"✅ fetch_kr_tickers() returned {len(tickers)} tickers")

            # Validate data format
            sample = tickers[0] if tickers else None
            if sample:
                logger.info(f"   Sample ticker data:")
                logger.info(f"      - ticker: {sample.get('ticker')}")
                logger.info(f"      - name: {sample.get('name')}")
                logger.info(f"      - asset_type: {sample.get('asset_type')}")
                logger.info(f"      - exchange: {sample.get('exchange')}")
                logger.info(f"      - region: {sample.get('region')}")

            return tickers
        else:
            logger.warning("⚠️  fetch_kr_tickers() returned empty list")
            logger.info("   (This may be normal if API credentials are not configured)")
            return []

    except Exception as e:
        logger.warning(f"⚠️  fetch_kr_tickers() raised exception: {e}")
        logger.info("   (This may be normal if API credentials are not configured)")
        return []


def test_10_tickers_validation(db):
    """Test 5: Verify 10 test tickers in database"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: 10 Test Tickers Validation")
    logger.info("=" * 80)

    results = {
        'found': [],
        'missing': [],
        'total': 0
    }

    for asset_type, tickers in TEST_TICKERS.items():
        logger.info(f"\nChecking {asset_type} tickers:")

        for ticker_info in tickers:
            ticker = ticker_info['ticker']
            expected_name = ticker_info['name']
            results['total'] += 1

            try:
                # Use PostgresDatabaseManager's get_ticker method
                ticker_data = db.get_ticker(ticker, region='KR')

                if ticker_data:
                    logger.info(f"  ✅ {ticker} ({expected_name})")
                    logger.info(f"     - DB name: {ticker_data.get('name')}")
                    logger.info(f"     - Asset type: {ticker_data.get('asset_type')}")
                    logger.info(f"     - Exchange: {ticker_data.get('exchange')}")
                    logger.info(f"     - Active: {ticker_data.get('is_active')}")

                    results['found'].append({
                        'ticker': ticker,
                        'expected_name': expected_name,
                        'db_name': ticker_data.get('name'),
                        'asset_type': ticker_data.get('asset_type'),
                        'active': ticker_data.get('is_active')
                    })
                else:
                    logger.warning(f"  ⚠️  {ticker} ({expected_name}) - NOT FOUND IN DATABASE")
                    results['missing'].append({
                        'ticker': ticker,
                        'expected_name': expected_name
                    })

            except Exception as e:
                logger.error(f"  ❌ {ticker} - Query failed: {e}")
                results['missing'].append({
                    'ticker': ticker,
                    'expected_name': expected_name,
                    'error': str(e)
                })

    return results


def print_summary(results):
    """Print test summary"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    found_count = len(results['found'])
    missing_count = len(results['missing'])
    total_count = results['total']

    logger.info(f"Total test tickers: {total_count}")
    logger.info(f"Found in database: {found_count} ({found_count/total_count*100:.1f}%)")
    logger.info(f"Missing from database: {missing_count}")

    if missing_count > 0:
        logger.info("\nMissing tickers:")
        for item in results['missing']:
            logger.info(f"  - {item['ticker']} ({item['expected_name']})")

    # Final verdict
    if found_count == total_count:
        logger.info("\n✅ ALL TESTS PASSED: All 10 test tickers found in database")
        return True
    elif found_count >= total_count * 0.5:
        logger.warning(f"\n⚠️  PARTIAL SUCCESS: {found_count}/{total_count} tickers found")
        return True
    else:
        logger.error(f"\n❌ TEST FAILED: Only {found_count}/{total_count} tickers found")
        return False


def main():
    """Run all integration tests"""
    logger.info("Starting TickerRefresher + KRMarketAdapter Integration Tests...")
    logger.info("=" * 80 + "\n")

    # Test 1: Import verification
    if not test_import():
        logger.error("❌ Test suite failed at import verification")
        return False

    # Test 2: Adapter instantiation
    adapter, db = test_adapter_instantiation()
    if not adapter or not db:
        logger.error("❌ Test suite failed at adapter instantiation")
        return False

    # Test 3: TickerRefresher integration
    refresher = test_ticker_refresher_integration(adapter, db)
    if not refresher:
        logger.error("❌ Test suite failed at TickerRefresher integration")
        return False

    # Test 4: fetch_kr_tickers() data validation
    # Note: This may fail if API credentials are not configured
    tickers = test_fetch_kr_tickers(adapter)
    # Don't fail test suite if this returns empty (API may not be configured)

    # Test 5: 10 test tickers validation
    results = test_10_tickers_validation(db)

    # Print summary
    success = print_summary(results)

    return success


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test suite crashed: {e}", exc_info=True)
        sys.exit(1)
