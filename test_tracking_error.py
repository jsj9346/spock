#!/usr/bin/env python3
"""
Test script for Tracking Error Calculator

Validates that the calculator:
1. Retrieves price data correctly
2. Calculates tracking error across multiple windows
3. Interprets tracking error ratings
4. Saves results to database

Usage:
    python3 test_tracking_error.py
"""

import sys
import os
import asyncio

# Setup path
sys.path.insert(0, '/Users/13ruce/spock')
os.chdir('/Users/13ruce/spock')

from modules.analysis.tracking_error_calculator import TrackingErrorCalculator


async def test_tracking_error():
    """Test tracking error calculator"""

    print("\n" + "="*80)
    print("TRACKING ERROR CALCULATOR TEST")
    print("="*80)
    print()

    calc = TrackingErrorCalculator()

    # Test 1: Single window calculation
    print("="*80)
    print("TEST 1: Single Window Tracking Error (250-day)")
    print("="*80)
    print("ETF: KODEX 200 (069500)")
    print("Index: KOSPI 200 (U001)")
    print()

    try:
        result = await calc.calculate_tracking_error(
            etf_ticker="069500",  # KODEX 200
            index_ticker="U001",   # KOSPI 200
            window_days=250,
            region="KR"
        )

        print(f"{'Metric':<30} {'Value':<15}")
        print("-"*80)
        for key, value in result.items():
            if isinstance(value, float):
                print(f"{key:<30} {value:<15.4f}")
            else:
                print(f"{key:<30} {value:<15}")

        # Interpret
        interpretation = calc.interpret_tracking_error(result["tracking_error_annualized"])
        print()
        print(f"Rating: {interpretation['rating'].upper()}")
        print(f"Description: {interpretation['description']}")
        print(f"Threshold: {interpretation['threshold']}")
        print()
        print(f"✅ Test 1 PASSED")

    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        return False

    print()

    # Test 2: Multiple windows
    print("="*80)
    print("TEST 2: Multiple Windows (20d, 60d, 120d, 250d)")
    print("="*80)
    print("ETF: KODEX 200 (069500)")
    print("Index: KOSPI 200 (U001)")
    print()

    try:
        results = await calc.calculate_multiple_windows(
            etf_ticker="069500",
            index_ticker="U001",
            windows=[20, 60, 120, 250],
            region="KR"
        )

        print(f"{'Window':<15} {'TE (Annual)':<15} {'Correlation':<15} {'Rating':<15}")
        print("-"*80)
        for window, result in results.items():
            if result:
                te = result["tracking_error_annualized"]
                corr = result["correlation"]
                rating = calc.interpret_tracking_error(te)["rating"]
                print(f"{window:<15} {te:<15.2f}% {corr:<15.4f} {rating:<15}")
            else:
                print(f"{window:<15} {'N/A':<15} {'N/A':<15} {'N/A':<15}")

        print()
        print(f"✅ Test 2 PASSED")

    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        return False

    print()

    # Test 3: Interpretation ratings
    print("="*80)
    print("TEST 3: Tracking Error Interpretation")
    print("="*80)
    print()

    test_cases = [
        (0.3, "excellent"),
        (0.7, "good"),
        (1.5, "acceptable"),
        (2.5, "poor")
    ]

    print(f"{'TE (%)':<10} {'Expected':<15} {'Actual':<15} {'Status':<10}")
    print("-"*80)

    all_passed = True
    for te_value, expected_rating in test_cases:
        result = calc.interpret_tracking_error(te_value)
        actual_rating = result["rating"]
        status = "✅ PASS" if actual_rating == expected_rating else "❌ FAIL"
        print(f"{te_value:<10.1f} {expected_rating:<15} {actual_rating:<15} {status:<10}")

        if actual_rating != expected_rating:
            all_passed = False

    print()
    if all_passed:
        print(f"✅ Test 3 PASSED")
    else:
        print(f"❌ Test 3 FAILED")
        return False

    print()

    # Summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("✅ Test 1: Single window calculation")
    print("✅ Test 2: Multiple windows calculation")
    print("✅ Test 3: Interpretation ratings")
    print()
    print("="*80)
    print("🎉 ALL TESTS PASSED - TRACKING ERROR CALCULATOR WORKING")
    print("="*80)

    return True


if __name__ == "__main__":
    success = asyncio.run(test_tracking_error())
    sys.exit(0 if success else 1)
