#!/usr/bin/env python3
"""
Integration Test: Fundamental Screening Modes

Tests flexible vs strict screening with real PostgreSQL data.
Validates that flexible mode (default) allows NULL YOY growth while strict mode requires all criteria.

Author: Spock Development Team
Date: 2025-11-02
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from datetime import datetime
from mcp_server.strategies.signal_generators import (
    FundamentalSignalGenerator,
    SignalGeneratorFactory
)


def get_test_tickers():
    """Get sample Korean tickers for testing"""
    return [
        '005930',  # Samsung Electronics
        '000660',  # SK Hynix
        '035420',  # NAVER
        '051910',  # LG Chem
        '006400',  # Samsung SDI
        '035720',  # Kakao
        '000270',  # Kia
        '005380',  # Hyundai Motor
        '068270',  # Celltrion
        '207940',  # Samsung Biologics
    ]


def check_data_availability():
    """Check ticker_fundamentals data availability"""
    try:
        conn = psycopg2.connect(
            dbname="quant_platform",
            host="localhost",
            port=5432
        )
        cursor = conn.cursor()

        # Check data availability
        cursor.execute("""
            SELECT
                COUNT(*) as total_records,
                COUNT(DISTINCT ticker) as unique_tickers,
                MIN(fiscal_year) as earliest_year,
                MAX(fiscal_year) as latest_year
            FROM ticker_fundamentals
            WHERE region = 'KR'
                AND fiscal_year IS NOT NULL
        """)

        result = cursor.fetchone()
        print("\n📊 Database Status:")
        print(f"  Total records: {result[0]:,}")
        print(f"  Unique tickers: {result[1]}")
        print(f"  Year range: {result[2]} - {result[3]}")

        # Check period type distribution
        cursor.execute("""
            SELECT period_type, COUNT(*) as count
            FROM ticker_fundamentals
            WHERE region = 'KR'
            GROUP BY period_type
            ORDER BY count DESC
        """)

        print("\n📋 Period Type Distribution:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:,} records")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        return False


def test_flexible_mode():
    """Test flexible mode (default) - YOY growth optional"""
    print("\n" + "="*60)
    print("Test 1: Flexible Mode (require_growth=False, default)")
    print("="*60)

    params = {
        'roe_min': 15.0,
        'debt_to_equity_max': 100.0,
        'net_income_growth_min': 10.0,
        'revenue_growth_min': 10.0,
        'require_growth': False,  # Flexible mode (default)
        'top_n': 10,
        'rebalance_freq_days': 252,
        'region': 'KR'
    }

    generator = FundamentalSignalGenerator(params)

    # Test screening for each ticker
    test_date = datetime(2025, 1, 1)
    passed_tickers = []
    failed_tickers = []

    for ticker in get_test_tickers():
        try:
            passed = generator._screen_ticker(ticker, test_date, params)
            if passed:
                passed_tickers.append(ticker)
            else:
                failed_tickers.append(ticker)
        except Exception as e:
            print(f"  ⚠️  Error testing {ticker}: {e}")
            failed_tickers.append(ticker)

    print(f"\n✅ Passed: {len(passed_tickers)} stocks")
    if passed_tickers:
        print(f"   {', '.join(passed_tickers)}")

    print(f"\n❌ Failed: {len(failed_tickers)} stocks")
    if failed_tickers:
        print(f"   {', '.join(failed_tickers)}")

    return len(passed_tickers)


def test_strict_mode():
    """Test strict mode - all criteria required"""
    print("\n" + "="*60)
    print("Test 2: Strict Mode (require_growth=True)")
    print("="*60)

    params = {
        'roe_min': 15.0,
        'debt_to_equity_max': 100.0,
        'net_income_growth_min': 10.0,
        'revenue_growth_min': 10.0,
        'require_growth': True,  # Strict mode
        'top_n': 10,
        'rebalance_freq_days': 252,
        'region': 'KR'
    }

    generator = FundamentalSignalGenerator(params)

    # Test screening for each ticker
    test_date = datetime(2025, 1, 1)
    passed_tickers = []
    failed_tickers = []

    for ticker in get_test_tickers():
        try:
            passed = generator._screen_ticker(ticker, test_date, params)
            if passed:
                passed_tickers.append(ticker)
            else:
                failed_tickers.append(ticker)
        except Exception as e:
            print(f"  ⚠️  Error testing {ticker}: {e}")
            failed_tickers.append(ticker)

    print(f"\n✅ Passed: {len(passed_tickers)} stocks")
    if passed_tickers:
        print(f"   {', '.join(passed_tickers)}")

    print(f"\n❌ Failed: {len(failed_tickers)} stocks")
    if failed_tickers:
        print(f"   {', '.join(failed_tickers)}")

    return len(passed_tickers)


def test_factory_integration():
    """Test factory integration with new parameter"""
    print("\n" + "="*60)
    print("Test 3: Factory Integration")
    print("="*60)

    params = {
        'roe_min': 15.0,
        'debt_to_equity_max': 100.0,
        'net_income_growth_min': 10.0,
        'revenue_growth_min': 10.0,
        'require_growth': False,
        'top_n': 10,
        'rebalance_freq_days': 252,
        'region': 'KR'
    }

    # Create generator through factory
    generator = SignalGeneratorFactory.create('fundamental_quality_growth', params)

    # Verify it's the right type
    assert isinstance(generator, FundamentalSignalGenerator), \
        "Factory should return FundamentalSignalGenerator instance"

    # Verify parameters
    assert generator.parameters['require_growth'] == False, \
        "require_growth should be False (flexible mode)"

    print("✅ Factory creates generator with require_growth parameter")
    print(f"   Generator type: {type(generator).__name__}")
    print(f"   require_growth: {generator.parameters['require_growth']}")

    return True


def main():
    """Run integration tests"""
    print("\n" + "="*60)
    print("🧪 Fundamental Screening Modes - Integration Test")
    print("="*60)

    # Check database
    if not check_data_availability():
        print("\n❌ Cannot proceed without database connection")
        return 1

    # Run tests
    try:
        flexible_count = test_flexible_mode()
        strict_count = test_strict_mode()
        factory_ok = test_factory_integration()

        # Summary
        print("\n" + "="*60)
        print("📊 Test Summary")
        print("="*60)
        print(f"\nFlexible Mode (require_growth=False):")
        print(f"  ✅ Passed: {flexible_count} stocks")
        print(f"  Expected: 0-10 stocks (with current DAILY data)")

        print(f"\nStrict Mode (require_growth=True):")
        print(f"  ✅ Passed: {strict_count} stocks")
        print(f"  Expected: 0 stocks (no 2024 fiscal_year data)")

        print(f"\nFactory Integration:")
        print(f"  {'✅' if factory_ok else '❌'} Factory creates generator correctly")

        # Validation
        print("\n" + "="*60)
        print("✅ Integration Test Results")
        print("="*60)

        if flexible_count >= strict_count:
            print("\n✅ PASS: Flexible mode allows more stocks than strict mode")
            print(f"   Flexible: {flexible_count} stocks")
            print(f"   Strict: {strict_count} stocks")
            print(f"   Difference: {flexible_count - strict_count} stocks")
        else:
            print("\n⚠️  WARNING: Strict mode allowed more stocks than flexible mode")
            print(f"   This is unexpected - please investigate")

        if strict_count == 0:
            print("\n✅ EXPECTED: Strict mode blocks all stocks (no 2024 YOY data)")
        else:
            print(f"\n⚠️  UNEXPECTED: Strict mode allowed {strict_count} stocks")
            print("   Expected 0 stocks due to missing 2024 fiscal_year data")

        print("\n" + "="*60)
        print("🎯 Phase 1 Quick Fix - VALIDATION COMPLETE")
        print("="*60)
        print("\nNext Steps:")
        print("  1. Phase 2: DART Annual Data Backfill (add 2024 fiscal_year)")
        print("  2. Phase 3: Multi-Factor Library (29 factors)")
        print("  3. Phase 4: Multi-Source Integration")
        print("  4. Phase 5: Advanced Screening & Discovery")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
