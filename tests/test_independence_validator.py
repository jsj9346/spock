#!/usr/bin/env python3
"""
test_independence_validator.py - Test suite for IndependenceValidator

Tests:
1. Basic validation with default parameters
2. Category-level independence analysis
3. Custom threshold testing
4. Report generation and saving
"""

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.factors.independence_validator import IndependenceValidator
from datetime import date
import os


def test_basic_validation():
    """Test basic independence validation"""
    print("=" * 70)
    print("Test 1: Basic Independence Validation")
    print("=" * 70)

    validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.5,
        min_sample_size=20
    )

    report = validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    print(report)

    # Assertions
    assert report.total_factor_pairs > 0, "Should have calculated correlations"
    assert report.independence_rate >= 0, "Independence rate should be non-negative"

    print("\n✅ Basic validation test passed!\n")

    return report


def test_category_analysis():
    """Test category-level independence analysis"""
    print("=" * 70)
    print("Test 2: Category-Level Independence Analysis")
    print("=" * 70)

    validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.5,
        min_sample_size=20
    )

    report = validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    # Print category summary
    print("\nCategory Independence Summary:")
    print("-" * 70)

    if report.category_summary:
        for category, stats in report.category_summary.items():
            independence_rate = (stats['independent_pairs'] / stats['total_pairs']) * 100
            status = "✅" if stats['correlated_pairs'] == 0 else "⚠️"
            print(
                f"{status} {category}:\n"
                f"   Total pairs: {stats['total_pairs']}\n"
                f"   Independent: {stats['independent_pairs']} ({independence_rate:.1f}%)\n"
                f"   Correlated: {stats['correlated_pairs']}"
            )
    else:
        print("No category summary available")

    print("\n✅ Category analysis test passed!\n")


def test_custom_threshold():
    """Test validation with custom correlation threshold"""
    print("=" * 70)
    print("Test 3: Custom Threshold Testing")
    print("=" * 70)

    # Test with stricter threshold
    strict_validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.3,  # More strict
        min_sample_size=20
    )

    strict_report = strict_validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    print(f"\nStrict Threshold (0.3):")
    print(f"  Independent pairs: {strict_report.independent_pairs}/{strict_report.total_factor_pairs}")
    print(f"  Independence rate: {strict_report.independence_rate:.1f}%")

    # Test with lenient threshold
    lenient_validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.7,  # More lenient
        min_sample_size=20
    )

    lenient_report = lenient_validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    print(f"\nLenient Threshold (0.7):")
    print(f"  Independent pairs: {lenient_report.independent_pairs}/{lenient_report.total_factor_pairs}")
    print(f"  Independence rate: {lenient_report.independence_rate:.1f}%")

    # Assertion: stricter threshold should result in lower independence rate
    assert strict_report.independence_rate <= lenient_report.independence_rate, \
        "Stricter threshold should have lower independence rate"

    print("\n✅ Custom threshold test passed!\n")


def test_report_generation():
    """Test report generation and saving"""
    print("=" * 70)
    print("Test 4: Report Generation and Saving")
    print("=" * 70)

    validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.5,
        min_sample_size=20
    )

    report = validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    # Save report with details
    output_path = 'results/test_independence_report_detailed.txt'
    validator.save_report(report, output_path, include_details=True)

    assert os.path.exists(output_path), "Report file should exist"
    print(f"✅ Detailed report saved: {output_path}")

    # Save report without details
    output_path_summary = 'results/test_independence_report_summary.txt'
    validator.save_report(report, output_path_summary, include_details=False)

    assert os.path.exists(output_path_summary), "Summary report file should exist"
    print(f"✅ Summary report saved: {output_path_summary}")

    # Check file sizes
    detailed_size = os.path.getsize(output_path)
    summary_size = os.path.getsize(output_path_summary)

    print(f"\nFile sizes:")
    print(f"  Detailed report: {detailed_size} bytes")
    print(f"  Summary report: {summary_size} bytes")

    print("\n✅ Report generation test passed!\n")


def test_correlated_factors():
    """Test identification of highly correlated factors"""
    print("=" * 70)
    print("Test 5: Correlated Factor Identification")
    print("=" * 70)

    validator = IndependenceValidator(
        region='KR',
        independence_threshold=0.5,
        min_sample_size=20
    )

    report = validator.validate_independence(
        start_date=date(2024, 9, 1),
        end_date=date(2024, 10, 22),
        tickers=None
    )

    # Find correlated pairs
    correlated_pairs = [c for c in report.correlations if not c.is_independent]

    print(f"\nFound {len(correlated_pairs)} correlated pairs:")
    for pair in sorted(correlated_pairs, key=lambda x: abs(x.correlation), reverse=True):
        print(f"  {pair}")

    # Print recommendations
    if report.recommendations:
        print("\nRecommendations:")
        for rec in report.recommendations[:10]:  # Print first 10 recommendations
            print(f"  {rec}")

    print("\n✅ Correlated factor identification test passed!\n")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("IndependenceValidator Test Suite")
    print("="*70 + "\n")

    try:
        # Run all tests
        report = test_basic_validation()
        test_category_analysis()
        test_custom_threshold()
        test_report_generation()
        test_correlated_factors()

        print("\n" + "="*70)
        print("✅ All tests passed!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
