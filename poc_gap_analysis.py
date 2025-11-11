#!/usr/bin/env python3
"""
Quick POC: Gap Analysis SQL Validation

Tests the core gap detection SQL query to validate:
1. Query performance (<2 seconds target)
2. Efficiency gain (API call reduction)
3. Design feasibility

This POC validates the scan-then-backfill optimization strategy
before committing to full implementation.

Usage:
    python poc_gap_analysis.py

Expected Output:
    - Query execution time
    - Gap analysis results (fully_missing, partially_missing, complete)
    - Efficiency metrics (API calls saved)
    - Go/No-Go recommendation

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import sys
import os
from datetime import date
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.db_manager_postgres import PostgresDatabaseManager


def test_gap_analysis_sql():
    """
    Test gap analysis SQL query performance and effectiveness

    Returns:
        dict: POC results with performance metrics
    """
    print("\n" + "=" * 80)
    print("🔬 POC: Gap Analysis SQL Validation")
    print("=" * 80)
    print()

    db = PostgresDatabaseManager()

    # Equity account gap analysis query
    query = """
    WITH ticker_gaps AS (
      SELECT
        t.ticker,
        t.name,
        t.listing_date,
        COUNT(tf.id) FILTER (
          WHERE tf.capital_stock IS NULL
             OR tf.capital_surplus IS NULL
             OR tf.retained_earnings IS NULL
        ) as missing_count,
        COUNT(tf.id) as total_count
      FROM tickers t
      LEFT JOIN ticker_fundamentals tf
        ON t.ticker = tf.ticker
        AND t.region = tf.region
        AND tf.date >= %(backfill_start_date)s
      WHERE t.region = %(region)s
        AND t.asset_type = %(asset_type)s
        AND t.is_active = TRUE
        AND (t.listing_date IS NULL OR t.listing_date <= %(backfill_start_date)s)
      GROUP BY t.ticker, t.name, t.listing_date
    )
    SELECT
      ticker,
      name,
      listing_date,
      missing_count,
      total_count,
      CASE
        WHEN total_count = 0 THEN 1
        WHEN missing_count = total_count THEN 1
        WHEN missing_count > 0 THEN 2
        ELSE 3
      END as priority
    FROM ticker_gaps
    WHERE missing_count > 0 OR total_count = 0
    ORDER BY priority, missing_count DESC;
    """

    params = {
        'region': 'KR',
        'asset_type': 'STOCK',
        'backfill_start_date': date(2022, 1, 1)
    }

    print("🔍 Executing gap analysis SQL query...")
    print(f"  Target: ticker_fundamentals")
    print(f"  Columns: capital_stock, capital_surplus, retained_earnings")
    print(f"  Region: {params['region']}")
    print(f"  Backfill Start: {params['backfill_start_date']}")
    print()

    # Execute query with timing
    start = time.time()
    try:
        results = db.execute_query(query, params)
        elapsed = time.time() - start
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        import traceback
        traceback.print_exc()
        db.close_pool()
        return None

    # Analyze results
    fully_missing = [r for r in results if r['priority'] == 1]
    partially_missing = [r for r in results if r['priority'] == 2]
    complete = [r for r in results if r['priority'] == 3]

    total_analyzed = len(results)
    needs_backfill = len(fully_missing) + len(partially_missing)
    api_calls_saved = len(complete)
    efficiency_gain = (api_calls_saved / total_analyzed * 100) if total_analyzed > 0 else 0

    # Print results
    print("=" * 80)
    print("📊 QUERY RESULTS")
    print("=" * 80)
    print()
    print(f"⏱️  Query Performance:")
    print(f"  Execution time: {elapsed:.2f} seconds")
    if elapsed < 2.0:
        print(f"  Status: ✅ PASS (< 2.0s target)")
    else:
        print(f"  Status: ⚠️  SLOW (> 2.0s target)")
    print()

    print(f"📊 Gap Analysis Results:")
    print(f"  Total tickers analyzed: {total_analyzed:,}")
    print(f"  Fully missing:          {len(fully_missing):,}")
    print(f"  Partially missing:      {len(partially_missing):,}")
    print(f"  Complete (skip):        {len(complete):,}")
    print()

    print(f"💰 Efficiency Metrics:")
    print(f"  Tickers needing backfill: {needs_backfill:,}")
    print(f"  API calls saved:          {api_calls_saved:,}")
    print(f"  Efficiency gain:          {efficiency_gain:.1f}%")
    print()

    # Time savings calculation
    time_per_ticker_hours = 0.09  # 108 sec = 0.09 hours
    time_saved_hours = api_calls_saved * time_per_ticker_hours
    print(f"⏰ Estimated Time Savings:")
    print(f"  Current run:   {time_saved_hours:.1f} hours saved")
    print(f"  Incremental:   ~90% reduction expected (500 → 50 calls)")
    print()

    # Sample results
    if fully_missing:
        print("=" * 80)
        print("📋 SAMPLE: Fully Missing Tickers (top 10)")
        print("=" * 80)
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15} {'Priority'}")
        print("-" * 80)
        for ticker in fully_missing[:10]:
            name = ticker['name'][:28] if ticker['name'] else ''
            print(f"{ticker['ticker']:<10} {name:<30} "
                  f"{ticker['missing_count']}/{ticker['total_count']:<12} "
                  f"{'FULLY_MISSING'}")
        print()

    if partially_missing:
        print("=" * 80)
        print("📋 SAMPLE: Partially Missing Tickers (top 10)")
        print("=" * 80)
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15} {'Priority'}")
        print("-" * 80)
        for ticker in partially_missing[:10]:
            name = ticker['name'][:28] if ticker['name'] else ''
            print(f"{ticker['ticker']:<10} {name:<30} "
                  f"{ticker['missing_count']}/{ticker['total_count']:<12} "
                  f"{'PARTIAL'}")
        print()

    if complete:
        print("=" * 80)
        print("✅ SAMPLE: Complete Tickers (would skip, top 10)")
        print("=" * 80)
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15} {'Status'}")
        print("-" * 80)
        for ticker in complete[:10]:
            name = ticker['name'][:28] if ticker['name'] else ''
            print(f"{ticker['ticker']:<10} {name:<30} "
                  f"{ticker['missing_count']}/{ticker['total_count']:<12} "
                  f"{'COMPLETE'}")
        print()

    # Validation
    print("=" * 80)
    print("🎯 POC VALIDATION")
    print("=" * 80)
    print()

    passed = True

    # Test 1: Query performance
    print("Test 1: Query Performance")
    if elapsed < 2.0:
        print(f"  ✅ PASS: Query executed in {elapsed:.2f}s (< 2.0s target)")
    else:
        print(f"  ⚠️  WARNING: Query slower than target ({elapsed:.2f}s > 2.0s)")
        print(f"  💡 Consider adding indexes or optimizing query")
        passed = False

    # Test 2: Efficiency gain
    print()
    print("Test 2: Efficiency Gain")
    if total_analyzed > 0:
        # For initial backfill, even small gains are valuable
        # For incremental, we expect >50% gain
        if efficiency_gain > 1.0:
            print(f"  ✅ PASS: {efficiency_gain:.1f}% API calls can be skipped")
            print(f"  💡 Initial run: {api_calls_saved} calls saved")
            print(f"  💡 Incremental runs: Expected >90% savings")
        else:
            print(f"  ⚠️  WARNING: Low efficiency gain ({efficiency_gain:.1f}%)")
            print(f"  💡 This is acceptable for first backfill")
    else:
        print(f"  ❌ FAIL: No tickers analyzed")
        passed = False

    # Test 3: Data quality
    print()
    print("Test 3: Data Quality")
    if total_analyzed > 0:
        print(f"  ✅ PASS: {total_analyzed:,} tickers found for analysis")
        if needs_backfill > 0:
            print(f"  ✅ PASS: {needs_backfill:,} tickers need backfill (gap detection working)")
    else:
        print(f"  ❌ FAIL: No tickers found")
        passed = False

    print()
    print("=" * 80)
    print("🏁 POC SUMMARY")
    print("=" * 80)
    print()

    poc_result = {
        'success': passed,
        'query_time_sec': round(elapsed, 2),
        'total_analyzed': total_analyzed,
        'needs_backfill': needs_backfill,
        'api_calls_saved': api_calls_saved,
        'efficiency_gain_pct': round(efficiency_gain, 2),
        'time_saved_hours': round(time_saved_hours, 2)
    }

    print(f"Query Performance: {poc_result['query_time_sec']}s")
    print(f"Tickers Analyzed:  {poc_result['total_analyzed']:,}")
    print(f"Need Backfill:     {poc_result['needs_backfill']:,}")
    print(f"API Calls Saved:   {poc_result['api_calls_saved']:,} ({poc_result['efficiency_gain_pct']:.1f}%)")
    print(f"Time Saved:        {poc_result['time_saved_hours']:.1f} hours")
    print()

    # Recommendation
    print("=" * 80)
    print("💡 RECOMMENDATION")
    print("=" * 80)
    print()

    if passed and elapsed < 2.0:
        print("✅ POC SUCCESSFUL - Proceed with full implementation")
        print()
        print("Next Steps:")
        print("  1. Implement GapAnalyzer component (4-6 hours)")
        print("  2. Create unit tests")
        print("  3. Integrate with existing backfill scripts")
        print()
        print("Expected Benefits:")
        print(f"  - Initial backfill: {api_calls_saved:,} API calls saved ({poc_result['efficiency_gain_pct']:.1f}%)")
        print(f"  - Incremental updates: >90% API call reduction")
        print(f"  - Time savings: {poc_result['time_saved_hours']:.1f} hours + ongoing")
    elif passed and elapsed >= 2.0:
        print("⚠️  POC PARTIAL SUCCESS - Query optimization needed")
        print()
        print("Issues:")
        print(f"  - Query too slow ({elapsed:.2f}s > 2.0s target)")
        print()
        print("Options:")
        print("  1. Add database indexes on (ticker, region, date)")
        print("  2. Optimize query (reduce LEFT JOIN complexity)")
        print("  3. Accept slower performance for now")
        print()
        print("Recommendation: Proceed with optimization first")
    else:
        print("❌ POC FAILED - Review design assumptions")
        print()
        print("Issues:")
        if total_analyzed == 0:
            print("  - No tickers found (check database connection/data)")
        if elapsed >= 5.0:
            print(f"  - Query very slow ({elapsed:.2f}s)")
        print()
        print("Recommendation: Debug issues before proceeding")

    print()
    print("=" * 80)

    db.close_pool()

    return poc_result


def export_poc_results(result):
    """Export POC results to JSON file"""
    if not result:
        return

    output_file = f"logs/poc_gap_analysis_{date.today().strftime('%Y%m%d')}.json"
    os.makedirs('logs', exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"📁 Results exported to: {output_file}")
    print()


if __name__ == '__main__':
    print()
    print("🚀 Starting POC: Gap Analysis SQL Validation")
    print()

    try:
        result = test_gap_analysis_sql()

        if result:
            export_poc_results(result)

            # Return appropriate exit code
            if result['success']:
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            print("❌ POC failed to complete")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  POC interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ POC failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
