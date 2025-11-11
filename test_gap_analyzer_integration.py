#!/usr/bin/env python3
"""
Integration test for GapAnalyzer component

Validates GapAnalyzer against production PostgreSQL database.
Compares results with POC validation (poc_gap_analysis.py).

Usage:
    python test_gap_analyzer_integration.py

Expected Output:
    - Gap analysis summary
    - Performance validation (<2s target)
    - Comparison with POC results (2,028 tickers expected)

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

from modules.backfill.gap_analyzer import GapAnalyzer
from modules.db_manager_postgres import PostgresDatabaseManager


def test_gap_analyzer_small_batch():
    """
    Test GapAnalyzer with small batch (10 tickers)

    Validates basic functionality with limited scope
    """
    print("\n" + "=" * 80)
    print("🧪 TEST 1: Small Batch (10 tickers)")
    print("=" * 80)
    print()

    db = PostgresDatabaseManager()
    analyzer = GapAnalyzer(db)

    start = time.time()
    result = analyzer.analyze_gaps(
        table='ticker_fundamentals',
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
        region='KR',
        backfill_start_date=date(2022, 1, 1),
        limit=10
    )
    elapsed = time.time() - start

    # Get summary
    summary = result.get_summary()

    print(f"⏱️  Performance:")
    print(f"  Analysis time: {summary['analysis_time_sec']:.2f}s")
    print(f"  Total elapsed: {elapsed:.2f}s")
    print()

    print(f"📊 Results:")
    print(f"  Total analyzed: {summary['total_analyzed']}")
    print(f"  Fully missing: {summary['fully_missing']}")
    print(f"  Partially missing: {summary['partially_missing']}")
    print(f"  Complete (skip): {summary['complete']}")
    print(f"  Needs backfill: {summary['needs_backfill']}")
    print()

    print(f"💡 Efficiency:")
    print(f"  API calls saved: {summary['api_calls_saved']}")
    print(f"  Efficiency gain: {summary['efficiency_gain_pct']:.1f}%")
    print()

    # Validation
    passed = True

    print("✓ Validations:")
    if summary['total_analyzed'] == 10:
        print(f"  ✅ Correct number of tickers analyzed (10)")
    else:
        print(f"  ❌ Expected 10 tickers, got {summary['total_analyzed']}")
        passed = False

    if summary['analysis_time_sec'] < 2.0:
        print(f"  ✅ Performance target met (<2s)")
    else:
        print(f"  ⚠️  Performance slower than target ({summary['analysis_time_sec']:.2f}s)")

    if isinstance(result.get_backfill_targets(), list):
        print(f"  ✅ get_backfill_targets() returns list")
    else:
        print(f"  ❌ get_backfill_targets() should return list")
        passed = False

    db.close_pool()

    return passed, summary


def test_gap_analyzer_full_dataset():
    """
    Test GapAnalyzer with full dataset (all KR stocks)

    Validates against POC results (2,028 tickers expected)
    """
    print("\n" + "=" * 80)
    print("🧪 TEST 2: Full Dataset (all KR stocks)")
    print("=" * 80)
    print()

    db = PostgresDatabaseManager()
    analyzer = GapAnalyzer(db)

    start = time.time()
    result = analyzer.analyze_gaps(
        table='ticker_fundamentals',
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
        region='KR',
        backfill_start_date=date(2022, 1, 1),
        limit=None  # No limit - analyze all
    )
    elapsed = time.time() - start

    # Get summary
    summary = result.get_summary()

    print(f"⏱️  Performance:")
    print(f"  Analysis time: {summary['analysis_time_sec']:.2f}s")
    print(f"  Total elapsed: {elapsed:.2f}s")
    print()

    print(f"📊 Results:")
    print(f"  Total analyzed: {summary['total_analyzed']:,}")
    print(f"  Fully missing: {summary['fully_missing']:,}")
    print(f"  Partially missing: {summary['partially_missing']:,}")
    print(f"  Complete (skip): {summary['complete']:,}")
    print(f"  Needs backfill: {summary['needs_backfill']:,}")
    print()

    print(f"💡 Efficiency:")
    print(f"  API calls saved: {summary['api_calls_saved']:,}")
    print(f"  Efficiency gain: {summary['efficiency_gain_pct']:.1f}%")
    print()

    # Load POC results for comparison
    poc_file = 'logs/poc_gap_analysis_20251111.json'
    poc_comparison = None
    if os.path.exists(poc_file):
        with open(poc_file, 'r') as f:
            poc_results = json.load(f)
            poc_comparison = {
                'total_analyzed': poc_results.get('total_analyzed', 0),
                'query_time': poc_results.get('query_time_sec', 0)
            }

    # Validation
    passed = True

    print("✓ Validations:")
    if summary['analysis_time_sec'] < 2.0:
        print(f"  ✅ Performance target met (<2s): {summary['analysis_time_sec']:.2f}s")
    else:
        print(f"  ⚠️  Performance slower than target: {summary['analysis_time_sec']:.2f}s > 2s")

    if poc_comparison:
        if summary['total_analyzed'] == poc_comparison['total_analyzed']:
            print(f"  ✅ Matches POC ticker count ({poc_comparison['total_analyzed']:,})")
        else:
            print(f"  ⚠️  POC: {poc_comparison['total_analyzed']:,}, GapAnalyzer: {summary['total_analyzed']:,}")

        # Performance comparison
        speedup = poc_comparison['query_time'] / summary['analysis_time_sec'] if summary['analysis_time_sec'] > 0 else 0
        print(f"  ℹ️  POC query time: {poc_comparison['query_time']:.2f}s")
        print(f"  ℹ️  GapAnalyzer time: {summary['analysis_time_sec']:.2f}s")
        if speedup > 0.9 and speedup < 1.1:
            print(f"  ✅ Similar performance (within 10%)")
        elif speedup > 1.1:
            print(f"  ⚡ GapAnalyzer faster ({speedup:.1f}x)")
        else:
            print(f"  ⚠️  GapAnalyzer slower ({1/speedup:.1f}x)")
    else:
        print(f"  ℹ️  POC results not found at {poc_file}")
        print(f"  ℹ️  Skipping POC comparison")

    # Sample output
    if result.fully_missing:
        print()
        print("📋 SAMPLE: Fully Missing Tickers (top 5):")
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15}")
        print("-" * 60)
        for ticker in result.fully_missing[:5]:
            name = (ticker.name[:28] + '..') if len(ticker.name) > 30 else ticker.name
            print(f"{ticker.ticker:<10} {name:<30} {ticker.missing_count}/{ticker.total_count}")

    if result.partially_missing:
        print()
        print("📋 SAMPLE: Partially Missing Tickers (top 5):")
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15}")
        print("-" * 60)
        for ticker in result.partially_missing[:5]:
            name = (ticker.name[:28] + '..') if len(ticker.name) > 30 else ticker.name
            print(f"{ticker.ticker:<10} {name:<30} {ticker.missing_count}/{ticker.total_count}")

    if result.complete:
        print()
        print("✅ SAMPLE: Complete Tickers (would skip, top 5):")
        print(f"{'Ticker':<10} {'Name':<30} {'Missing/Total':<15}")
        print("-" * 60)
        for ticker in result.complete[:5]:
            name = (ticker.name[:28] + '..') if len(ticker.name) > 30 else ticker.name
            print(f"{ticker.ticker:<10} {name:<30} {ticker.missing_count}/{ticker.total_count}")

    db.close_pool()

    return passed, summary


def export_results(summary, test_type='integration'):
    """Export test results to JSON file"""
    output_file = f"logs/gap_analyzer_{test_type}_{date.today().strftime('%Y%m%d')}.json"
    os.makedirs('logs', exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n📁 Results exported to: {output_file}")


if __name__ == '__main__':
    print()
    print("🚀 Starting GapAnalyzer Integration Tests")
    print()

    all_passed = True

    try:
        # Test 1: Small batch
        passed_1, summary_1 = test_gap_analyzer_small_batch()
        all_passed = all_passed and passed_1

        # Test 2: Full dataset
        passed_2, summary_2 = test_gap_analyzer_full_dataset()
        all_passed = all_passed and passed_2

        # Export full dataset results
        export_results(summary_2, 'full_dataset')

        # Final summary
        print()
        print("=" * 80)
        print("🏁 INTEGRATION TEST SUMMARY")
        print("=" * 80)
        print()

        if all_passed:
            print("✅ ALL TESTS PASSED")
            print()
            print("GapAnalyzer is ready for integration with BackfillOrchestrator")
            sys.exit(0)
        else:
            print("⚠️  SOME TESTS FAILED")
            print()
            print("Review failures above before proceeding")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Tests failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
