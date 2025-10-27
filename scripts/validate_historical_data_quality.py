#!/usr/bin/env python3
"""
Comprehensive data quality validation for historical fundamental data

Usage:
    python3 scripts/validate_historical_data_quality.py
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager


def validate_data_quality():
    """Run comprehensive data quality validation tests"""

    print("=" * 70)
    print("📊 HISTORICAL FUNDAMENTAL DATA - QUALITY VALIDATION")
    print("=" * 70)
    print(f"Validation Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    db = SQLiteDatabaseManager()
    conn = db._get_connection()
    cursor = conn.cursor()

    test_results = []

    # Test 1: Check for NULL fiscal_year in historical data
    print("\n[Test 1/10] NULL fiscal_year Detection")
    cursor.execute('''
        SELECT COUNT(*) FROM ticker_fundamentals
        WHERE period_type = 'ANNUAL' AND fiscal_year IS NULL
    ''')
    null_count = cursor.fetchone()[0]
    test_results.append(("NULL fiscal_year check", null_count == 0, f"{null_count} rows"))
    print(f"  Result: {'✅ PASS' if null_count == 0 else f'❌ FAIL ({null_count} NULL rows)'}")

    # Test 2: Verify uniqueness constraint
    print("\n[Test 2/10] Uniqueness Constraint Validation")
    cursor.execute('''
        SELECT ticker, fiscal_year, period_type, COUNT(*) as dup_count
        FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
        GROUP BY ticker, fiscal_year, period_type
        HAVING dup_count > 1
    ''')
    duplicates = cursor.fetchall()
    test_results.append(("Uniqueness constraint", len(duplicates) == 0, f"{len(duplicates)} duplicates"))
    print(f"  Result: {'✅ PASS' if len(duplicates) == 0 else f'❌ FAIL ({len(duplicates)} duplicates)'}")

    # Test 3: Check data completeness (all years present)
    print("\n[Test 3/10] Data Completeness (2020-2024)")
    cursor.execute('''
        SELECT ticker, COUNT(DISTINCT fiscal_year) as year_count
        FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL AND period_type = 'ANNUAL'
        GROUP BY ticker
        HAVING year_count < 5
    ''')
    incomplete_tickers = cursor.fetchall()
    test_results.append(("Data completeness", len(incomplete_tickers) == 0,
                        f"{len(incomplete_tickers)} incomplete tickers"))
    print(f"  Result: {'✅ PASS' if len(incomplete_tickers) == 0 else f'❌ FAIL'}")
    if incomplete_tickers:
        for ticker, count in incomplete_tickers:
            print(f"    ⚠️  {ticker}: {count}/5 years")

    # Test 4: Verify data_source format
    print("\n[Test 4/10] Data Source Format Validation")
    cursor.execute('''
        SELECT COUNT(*) FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND period_type = 'ANNUAL'
          AND data_source NOT LIKE 'DART-%-11011'
    ''')
    invalid_source = cursor.fetchone()[0]
    test_results.append(("Data source format", invalid_source == 0, f"{invalid_source} invalid"))
    print(f"  Result: {'✅ PASS' if invalid_source == 0 else f'❌ FAIL ({invalid_source} invalid)'}")

    # Test 5: Check fiscal_year range
    print("\n[Test 5/10] Fiscal Year Range (2020-2024)")
    cursor.execute('''
        SELECT COUNT(*) FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND (fiscal_year < 2020 OR fiscal_year > 2024)
    ''')
    out_of_range = cursor.fetchone()[0]
    test_results.append(("Fiscal year range", out_of_range == 0, f"{out_of_range} out of range"))
    print(f"  Result: {'✅ PASS' if out_of_range == 0 else f'❌ FAIL ({out_of_range} out of range)'}")

    # Test 6: Verify year distribution
    print("\n[Test 6/10] Year Distribution Consistency")
    cursor.execute('''
        SELECT fiscal_year, COUNT(*) as count
        FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL AND period_type = 'ANNUAL'
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    ''')
    year_distribution = cursor.fetchall()
    counts = [count for _, count in year_distribution]
    consistent = len(set(counts)) == 1  # All years have same count
    test_results.append(("Year distribution", consistent, "All years consistent" if consistent else "Inconsistent"))
    print(f"  Result: {'✅ PASS' if consistent else '⚠️  WARNING'}")
    for year, count in year_distribution:
        print(f"    {year}: {count} rows")

    # Test 7: Check created_at timestamps
    print("\n[Test 7/10] Created_at Timestamp Validation")
    cursor.execute('''
        SELECT COUNT(*) FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND (created_at IS NULL OR created_at = '')
    ''')
    missing_timestamps = cursor.fetchone()[0]
    test_results.append(("Created_at timestamps", missing_timestamps == 0,
                        f"{missing_timestamps} missing"))
    print(f"  Result: {'✅ PASS' if missing_timestamps == 0 else f'❌ FAIL ({missing_timestamps} missing)'}")

    # Test 8: Verify period_type consistency
    print("\n[Test 8/10] Period Type Consistency")
    cursor.execute('''
        SELECT DISTINCT period_type FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
    ''')
    period_types = [row[0] for row in cursor.fetchall()]
    all_annual = period_types == ['ANNUAL']
    test_results.append(("Period type consistency", all_annual,
                        "All ANNUAL" if all_annual else f"Multiple types: {period_types}"))
    print(f"  Result: {'✅ PASS' if all_annual else f'❌ FAIL (Found: {period_types})'}")

    # Test 9: Check ticker format
    print("\n[Test 9/10] Ticker Format Validation (Korean 6-digit)")
    cursor.execute('''
        SELECT DISTINCT ticker FROM ticker_fundamentals
        WHERE fiscal_year IS NOT NULL
          AND (LENGTH(ticker) != 6 OR ticker NOT GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]')
    ''')
    invalid_tickers = cursor.fetchall()
    test_results.append(("Ticker format", len(invalid_tickers) == 0,
                        f"{len(invalid_tickers)} invalid"))
    print(f"  Result: {'✅ PASS' if len(invalid_tickers) == 0 else f'❌ FAIL'}")
    if invalid_tickers:
        for (ticker,) in invalid_tickers:
            print(f"    ⚠️  Invalid ticker: {ticker}")

    # Test 10: Database index verification
    print("\n[Test 10/10] Database Index Verification")
    cursor.execute('''
        SELECT name FROM sqlite_master
        WHERE type = 'index'
          AND tbl_name = 'ticker_fundamentals'
          AND (name LIKE '%fiscal_year%' OR name LIKE '%ticker_year%')
    ''')
    indexes = cursor.fetchall()
    has_indexes = len(indexes) >= 2
    test_results.append(("Database indexes", has_indexes, f"{len(indexes)} fiscal_year indexes"))
    print(f"  Result: {'✅ PASS' if has_indexes else '❌ FAIL (Missing indexes)'}")
    for (index_name,) in indexes:
        print(f"    ✅ {index_name}")

    conn.close()

    # Summary
    print("\n" + "=" * 70)
    print("📊 VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result, _ in test_results if result)
    total = len(test_results)
    pass_rate = (passed / total * 100) if total > 0 else 0

    print(f"\n✅ Passed: {passed}/{total} tests ({pass_rate:.1f}%)")
    print(f"❌ Failed: {total - passed}/{total} tests")

    print("\n📋 Test Results:")
    for test_name, result, details in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}: {details}")

    print("\n" + "=" * 70)

    if passed == total:
        print("🎉 ALL TESTS PASSED - Data quality is excellent!")
    elif passed >= total * 0.9:
        print("⚠️  MOSTLY PASSED - Minor issues detected, review failures")
    else:
        print("❌ CRITICAL ISSUES - Data quality needs attention")

    print("=" * 70)

    return passed == total


if __name__ == '__main__':
    success = validate_data_quality()
    sys.exit(0 if success else 1)
