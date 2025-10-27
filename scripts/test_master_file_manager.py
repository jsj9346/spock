#!/usr/bin/env python3
"""
Test script for KIS Master File Manager

Tests download, parsing, and caching functionality for overseas stock master files.

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def test_cache_status(manager: KISMasterFileManager):
    """Test cache status reporting"""
    print("\n" + "=" * 80)
    print("Test 1: Cache Status")
    print("=" * 80)

    status = manager.get_cache_status()

    for market_code, info in sorted(status.items()):
        if info['cached']:
            print(
                f"[{market_code}] {info['exchange']:10} | "
                f"Region: {info['region']:2} | "
                f"{info['ticker_count']:5,} stocks | "
                f"{info['file_size']:10,} bytes | "
                f"Modified: {info['modified']}"
            )
        else:
            print(
                f"[{market_code}] {info['exchange']:10} | "
                f"Region: {info['region']:2} | "
                f"Not cached"
            )

    print()


def test_download_single_market(manager: KISMasterFileManager, market_code: str):
    """Test downloading single market"""
    print("\n" + "=" * 80)
    print(f"Test 2: Download Single Market ({market_code.upper()})")
    print("=" * 80)

    try:
        # Download (with size check)
        cod_path = manager.download_market(market_code)
        print(f"✅ Download completed: {cod_path}")

        # Parse
        df = manager.parse_market(market_code)
        print(f"✅ Parsed {len(df):,} stocks")

        # Show sample
        print("\nSample stocks (first 5):")
        for idx, row in df.head(5).iterrows():
            print(
                f"  {row['Symbol']:10} | "
                f"{row['English name'][:40]:40} | "
                f"{row['Korea name'][:15]:15}"
            )

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_all_tickers_region(manager: KISMasterFileManager, region: str):
    """Test getting all tickers for region"""
    print("\n" + "=" * 80)
    print(f"Test 3: Get All Tickers ({region})")
    print("=" * 80)

    try:
        tickers = manager.get_all_tickers(region, force_refresh=False)
        print(f"✅ Collected {len(tickers):,} tickers from {region} region")

        # Group by exchange
        from collections import defaultdict
        by_exchange = defaultdict(int)
        for ticker in tickers:
            by_exchange[ticker['exchange']] += 1

        print("\nBreakdown by exchange:")
        for exchange, count in sorted(by_exchange.items()):
            print(f"  {exchange:10}: {count:5,} stocks")

        # Show sample
        print("\nSample tickers (first 10):")
        for ticker in tickers[:10]:
            print(
                f"  {ticker['ticker']:15} | "
                f"{ticker['name'][:35]:35} | "
                f"{ticker['exchange']:8} | "
                f"{ticker['currency']}"
            )

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ticker_normalization(manager: KISMasterFileManager):
    """Test ticker normalization"""
    print("\n" + "=" * 80)
    print("Test 4: Ticker Normalization")
    print("=" * 80)

    test_cases = [
        ('AAPL', 'nas', 'AAPL'),           # US: no change
        ('aapl', 'nas', 'AAPL'),           # US: uppercase
        ('700', 'hks', '0700.HK'),         # HK: pad and add suffix
        ('0700', 'hks', '0700.HK'),        # HK: add suffix only
        ('600000', 'shs', '600000.SS'),    # CN: add SSE suffix
        ('000001', 'szs', '000001.SZ'),    # CN: add SZSE suffix
        ('7203', 'tse', '7203'),           # JP: no change
        ('vcb', 'hnx', 'VCB'),             # VN: uppercase
    ]

    print("\nNormalization test cases:")
    all_pass = True

    for raw, market_code, expected in test_cases:
        normalized = manager._normalize_ticker(raw, market_code)
        status = "✅" if normalized == expected else "❌"
        print(f"  {status} [{market_code}] {raw:15} → {normalized:15} (expected: {expected})")

        if normalized != expected:
            all_pass = False

    return all_pass


def test_size_comparison(manager: KISMasterFileManager, market_code: str):
    """Test file size comparison logic"""
    print("\n" + "=" * 80)
    print(f"Test 5: Size Comparison ({market_code.upper()})")
    print("=" * 80)

    try:
        # First download (should download)
        print("\n1st attempt (should download):")
        needs_update_1 = manager._needs_update(market_code)
        print(f"  Needs update: {needs_update_1}")

        cod_path = manager.download_market(market_code, force=True)
        print(f"  Downloaded: {cod_path}")

        # Second check (should skip)
        print("\n2nd attempt (should skip):")
        needs_update_2 = manager._needs_update(market_code)
        print(f"  Needs update: {needs_update_2}")

        if not needs_update_2:
            print("  ✅ Size comparison working - skipped download")
            return True
        else:
            print("  ❌ Size comparison failed - should have skipped")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_backup_restore(manager: KISMasterFileManager, market_code: str):
    """Test backup and restore functionality"""
    print("\n" + "=" * 80)
    print(f"Test 6: Backup and Restore ({market_code.upper()})")
    print("=" * 80)

    try:
        # Ensure file exists
        manager.download_market(market_code, force=True)

        # Create backup
        backup_path = manager._backup_file(market_code)
        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        else:
            print("❌ Backup creation failed")
            return False

        # List backups
        backups = manager._list_backups(market_code)
        print(f"✅ Found {len(backups)} backup(s)")

        # Test restore
        if manager._restore_from_backup(market_code):
            print(f"✅ Restore successful")
            return True
        else:
            print("❌ Restore failed")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("KIS Master File Manager - Test Suite")
    print("=" * 80)

    manager = KISMasterFileManager()

    results = {}

    # Test 1: Cache status
    test_cache_status(manager)

    # Test 2: Download single market (NASDAQ)
    results['download_nasdaq'] = test_download_single_market(manager, 'nas')

    # Test 3: Get all US tickers
    results['get_us_tickers'] = test_get_all_tickers_region(manager, 'US')

    # Test 4: Ticker normalization
    results['ticker_normalization'] = test_ticker_normalization(manager)

    # Test 5: Size comparison
    results['size_comparison'] = test_size_comparison(manager, 'nas')

    # Test 6: Backup and restore
    results['backup_restore'] = test_backup_restore(manager, 'nas')

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 80)

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
