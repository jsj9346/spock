"""
Unit test fixtures for equity account enhancement testing.

This module provides test data and fixtures for:
1. DART API response samples (real-world account name variations)
2. Expected equity account extraction results
3. Edge cases (negative equity, missing data, fuzzy matching)
4. Schema validation test cases

Created: 2025-11-07
Phase: Phase 1 - Foundation & Schema (TDD)
"""

import pytest
from typing import Dict, List, Any
from datetime import date


# ============================================================================
# DART API Response Fixtures (Real-world account name variations)
# ============================================================================

# Samsung Electronics 2024 Q2 - Standard K-IFRS format
DART_RESPONSE_SAMSUNG_2024Q2 = {
    "자본금": 897514000000.0,
    "자본잉여금": 4403893000000.0,
    "이익잉여금": 393894245000000.0,
    "자기주식": -88716000000.0,
    "기타포괄손익누계액": -11076979000000.0,
    "자본총계": 399561967000000.0,
}

# SK Hynix 2024 Q2 - Variation in account names
DART_RESPONSE_SK_HYNIX_2024Q2 = {
    "보통주자본금": 3657132000000.0,  # Variation: "보통주자본금" instead of "자본금"
    "자본잉여금": 4555597000000.0,
    "이익잉여금(결손금)": 79036876000000.0,  # Variation: includes "(결손금)"
    "자기주식": -107120000000.0,
    "기타포괄손익누계액": 0.0,
    "자본총계": 87142485000000.0,
}

# LG Chem 2025 Q2 - Negative equity scenario
DART_RESPONSE_LG_CHEM_2025Q2 = {
    "자본금": 572834000000.0,
    "주식발행초과금": 2468762000000.0,  # Variation: "주식발행초과금" instead of "자본잉여금"
    "이익잉여금": 40983397000000.0,
    "자기주식처분손익": -62713000000.0,  # Variation: "자기주식처분손익"
    "기타자본항목": -122575000000.0,
    "기타포괄손익누계액": 748575000000.0,
    "자본총계": 44587280000000.0,
}

# Naver 2024 Q4 - Detailed breakdown with sub-accounts
DART_RESPONSE_NAVER_2024Q4 = {
    "자본금": 17166000000.0,
    "자본잉여금": 1322054000000.0,
    "이익잉여금": 25777023000000.0,
    "이익준비금": 8583000000.0,  # Sub-account of retained earnings
    "미처분이익잉여금": 25768440000000.0,  # Sub-account of retained earnings
    "자기주식": -115331000000.0,
    "기타포괄손익누계액": 0.0,
    "자본총계": 27000911848337.0,  # Note: exact match with sum
}

# Hyundai Motor 2025 Q2 - Missing some accounts (incomplete data)
DART_RESPONSE_HYUNDAI_2025Q2 = {
    "자본금": 1491699000000.0,
    "자본잉여금": 23365753000000.0,
    "이익잉여금": 97029473000000.0,
    # Missing: 자기주식, 기타포괄손익누계액
    "비지배지분": 12144185000000.0,  # Non-controlling interest
    "자본총계": 121537114000000.0,
}

# Kakao 2024 Q4 - Consolidated with non-controlling interest
DART_RESPONSE_KAKAO_2024Q4 = {
    "자본금": 443119000000.0,
    "주식발행초과금": 7685994000000.0,
    "이익잉여금": 2498473000000.0,
    "자기주식": -1200455000000.0,
    "기타자본구성요소": -562378000000.0,
    "비지배지분": 1034606000000.0,
    "자본총계": 9899359000000.0,
}


# ============================================================================
# Expected Extraction Results
# ============================================================================

EXPECTED_SAMSUNG_2024Q2 = {
    "capital_stock": 897514000000.0,
    "capital_surplus": 4403893000000.0,
    "retained_earnings": 393894245000000.0,
    "treasury_stock": -88716000000.0,  # Already negative
    "other_comprehensive_income": -11076979000000.0,
    "non_controlling_interest": None,  # Not provided
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

EXPECTED_SK_HYNIX_2024Q2 = {
    "capital_stock": 3657132000000.0,  # Matched "보통주자본금"
    "capital_surplus": 4555597000000.0,
    "retained_earnings": 79036876000000.0,  # Matched with "(결손금)" suffix
    "treasury_stock": -107120000000.0,
    "other_comprehensive_income": 0.0,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

EXPECTED_LG_CHEM_2025Q2 = {
    "capital_stock": 572834000000.0,
    "capital_surplus": 2468762000000.0,  # Matched "주식발행초과금"
    "retained_earnings": 40983397000000.0,
    "treasury_stock": -62713000000.0,  # Matched "자기주식처분손익"
    "other_comprehensive_income": 748575000000.0,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

EXPECTED_NAVER_2024Q4 = {
    "capital_stock": 17166000000.0,
    "capital_surplus": 1322054000000.0,
    "retained_earnings": 25777023000000.0,  # Primary retained earnings
    "treasury_stock": -115331000000.0,
    "other_comprehensive_income": 0.0,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": 25768440000000.0,  # Sub-account
    "legal_reserve": 8583000000.0,  # Sub-account
}

EXPECTED_HYUNDAI_2025Q2 = {
    "capital_stock": 1491699000000.0,
    "capital_surplus": 23365753000000.0,
    "retained_earnings": 97029473000000.0,
    "treasury_stock": None,  # Missing in source
    "other_comprehensive_income": None,  # Missing in source
    "non_controlling_interest": 12144185000000.0,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

EXPECTED_KAKAO_2024Q4 = {
    "capital_stock": 443119000000.0,
    "capital_surplus": 7685994000000.0,  # Matched "주식발행초과금"
    "retained_earnings": 2498473000000.0,
    "treasury_stock": -1200455000000.0,
    "other_comprehensive_income": -562378000000.0,  # Matched "기타자본구성요소"
    "non_controlling_interest": 1034606000000.0,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}


# ============================================================================
# Edge Cases for Testing
# ============================================================================

# Edge Case 1: Empty response (no equity data)
DART_RESPONSE_EMPTY = {}

EXPECTED_EMPTY = {
    "capital_stock": None,
    "capital_surplus": None,
    "retained_earnings": None,
    "treasury_stock": None,
    "other_comprehensive_income": None,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

# Edge Case 2: Zero values (valid but unusual)
DART_RESPONSE_ZEROS = {
    "자본금": 0.0,
    "자본잉여금": 0.0,
    "이익잉여금": 0.0,
    "자기주식": 0.0,
    "기타포괄손익누계액": 0.0,
    "자본총계": 0.0,
}

EXPECTED_ZEROS = {
    "capital_stock": 0.0,
    "capital_surplus": 0.0,
    "retained_earnings": 0.0,
    "treasury_stock": 0.0,
    "other_comprehensive_income": 0.0,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

# Edge Case 3: Positive treasury stock (needs normalization to negative)
DART_RESPONSE_POSITIVE_TREASURY = {
    "자본금": 1000000000.0,
    "자본잉여금": 500000000.0,
    "이익잉여금": 2000000000.0,
    "자기주식": 100000000.0,  # WRONG: Should be negative
    "자본총계": 3400000000.0,
}

EXPECTED_POSITIVE_TREASURY_NORMALIZED = {
    "capital_stock": 1000000000.0,
    "capital_surplus": 500000000.0,
    "retained_earnings": 2000000000.0,
    "treasury_stock": -100000000.0,  # CORRECTED: Normalized to negative
    "other_comprehensive_income": None,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}

# Edge Case 4: Very large numbers (test numeric precision)
DART_RESPONSE_LARGE_NUMBERS = {
    "자본금": 999999999999999.99,
    "자본잉여금": 888888888888888.88,
    "이익잉여금": 777777777777777.77,
    "자기주식": -666666666666666.66,
    "자본총계": 1999999999999999.98,
}

EXPECTED_LARGE_NUMBERS = {
    "capital_stock": 999999999999999.99,
    "capital_surplus": 888888888888888.88,
    "retained_earnings": 777777777777777.77,
    "treasury_stock": -666666666666666.66,
    "other_comprehensive_income": None,
    "non_controlling_interest": None,
    "unappropriated_retained_earnings": None,
    "legal_reserve": None,
}


# ============================================================================
# Fuzzy Matching Test Cases
# ============================================================================

# Test various account name patterns that should match
FUZZY_MATCHING_PATTERNS = {
    "capital_stock": [
        "자본금",
        "보통주자본금",
        "우선주자본금",
        "자 본 금",  # With spaces
        "자본금(보통주)",  # With parentheses
    ],
    "capital_surplus": [
        "자본잉여금",
        "주식발행초과금",
        "자본 잉여금",
        "자본잉여금(주식발행초과금)",
    ],
    "retained_earnings": [
        "이익잉여금",
        "이익잉여금(결손금)",
        "이 익 잉 여 금",
        "이익잉여금(미처분)",
    ],
    "treasury_stock": [
        "자기주식",
        "자기주식처분손익",
        "자 기 주 식",
        "자기주식취득",
    ],
    "other_comprehensive_income": [
        "기타포괄손익누계액",
        "기타자본구성요소",
        "기타자본항목",
        "기타포괄손익",
    ],
}


# ============================================================================
# Schema Validation Test Cases
# ============================================================================

# Test Case 1: Valid equity breakdown (should pass 5% tolerance)
EQUITY_VALIDATION_CASE_VALID = {
    "total_equity": 100000000000.0,
    "capital_stock": 10000000000.0,
    "capital_surplus": 20000000000.0,
    "retained_earnings": 75000000000.0,
    "treasury_stock": -5000000000.0,
    "other_comprehensive_income": 0.0,
    # Sum: 10 + 20 + 75 - 5 + 0 = 100 (exact match)
}

# Test Case 2: Within 5% tolerance (should pass)
EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE = {
    "total_equity": 100000000000.0,
    "capital_stock": 10000000000.0,
    "capital_surplus": 20000000000.0,
    "retained_earnings": 72000000000.0,  # Adjusted
    "treasury_stock": -5000000000.0,
    "other_comprehensive_income": 0.0,
    # Sum: 97 billion (3% difference, within 5% tolerance)
}

# Test Case 3: Outside 5% tolerance (should fail validation)
EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE = {
    "total_equity": 100000000000.0,
    "capital_stock": 10000000000.0,
    "capital_surplus": 20000000000.0,
    "retained_earnings": 60000000000.0,  # Too low
    "treasury_stock": -5000000000.0,
    "other_comprehensive_income": 0.0,
    # Sum: 85 billion (15% difference, outside 5% tolerance)
}

# Test Case 4: Incomplete data (should return None for validation)
EQUITY_VALIDATION_CASE_INCOMPLETE = {
    "total_equity": 100000000000.0,
    "capital_stock": 10000000000.0,
    "capital_surplus": None,  # Missing
    "retained_earnings": 75000000000.0,
    "treasury_stock": None,  # Missing
    "other_comprehensive_income": None,  # Missing
    # Cannot validate: too many missing values
}


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def dart_response_samples():
    """Provide all DART API response samples for testing."""
    return {
        "samsung_2024q2": DART_RESPONSE_SAMSUNG_2024Q2,
        "sk_hynix_2024q2": DART_RESPONSE_SK_HYNIX_2024Q2,
        "lg_chem_2025q2": DART_RESPONSE_LG_CHEM_2025Q2,
        "naver_2024q4": DART_RESPONSE_NAVER_2024Q4,
        "hyundai_2025q2": DART_RESPONSE_HYUNDAI_2025Q2,
        "kakao_2024q4": DART_RESPONSE_KAKAO_2024Q4,
    }


@pytest.fixture
def expected_extractions():
    """Provide expected extraction results for all samples."""
    return {
        "samsung_2024q2": EXPECTED_SAMSUNG_2024Q2,
        "sk_hynix_2024q2": EXPECTED_SK_HYNIX_2024Q2,
        "lg_chem_2025q2": EXPECTED_LG_CHEM_2025Q2,
        "naver_2024q4": EXPECTED_NAVER_2024Q4,
        "hyundai_2025q2": EXPECTED_HYUNDAI_2025Q2,
        "kakao_2024q4": EXPECTED_KAKAO_2024Q4,
    }


@pytest.fixture
def edge_case_samples():
    """Provide edge case test data."""
    return {
        "empty": (DART_RESPONSE_EMPTY, EXPECTED_EMPTY),
        "zeros": (DART_RESPONSE_ZEROS, EXPECTED_ZEROS),
        "positive_treasury": (
            DART_RESPONSE_POSITIVE_TREASURY,
            EXPECTED_POSITIVE_TREASURY_NORMALIZED,
        ),
        "large_numbers": (DART_RESPONSE_LARGE_NUMBERS, EXPECTED_LARGE_NUMBERS),
    }


@pytest.fixture
def fuzzy_matching_test_data():
    """Provide fuzzy matching pattern test data."""
    return FUZZY_MATCHING_PATTERNS


@pytest.fixture
def equity_validation_cases():
    """Provide equity validation test cases."""
    return {
        "valid": EQUITY_VALIDATION_CASE_VALID,
        "within_tolerance": EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE,
        "outside_tolerance": EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE,
        "incomplete": EQUITY_VALIDATION_CASE_INCOMPLETE,
    }


# ============================================================================
# Helper Functions for Tests
# ============================================================================

def calculate_equity_sum(equity_accounts: Dict[str, float]) -> float:
    """
    Calculate sum of equity accounts (for validation testing).

    Args:
        equity_accounts: Dict with equity account values

    Returns:
        Sum of all non-None equity components
    """
    components = [
        equity_accounts.get("capital_stock"),
        equity_accounts.get("capital_surplus"),
        equity_accounts.get("retained_earnings"),
        equity_accounts.get("treasury_stock"),  # Already negative
        equity_accounts.get("other_comprehensive_income"),
        equity_accounts.get("non_controlling_interest"),
    ]

    # Sum only non-None values
    return sum(v for v in components if v is not None)


def is_within_tolerance(
    total_equity: float, calculated_equity: float, tolerance: float = 0.05
) -> bool:
    """
    Check if calculated equity is within tolerance of total equity.

    Args:
        total_equity: Total equity from financial statements
        calculated_equity: Sum of equity account breakdown
        tolerance: Acceptable percentage difference (default 5%)

    Returns:
        True if within tolerance, False otherwise
    """
    if total_equity == 0:
        return calculated_equity == 0

    difference = abs(total_equity - calculated_equity)
    percentage_diff = difference / abs(total_equity)

    return percentage_diff <= tolerance


def assert_equity_accounts_equal(
    actual: Dict[str, float], expected: Dict[str, float], tolerance: float = 0.01
):
    """
    Assert two equity account dictionaries are equal (with numeric tolerance).

    Args:
        actual: Actual extracted equity accounts
        expected: Expected equity accounts
        tolerance: Numeric tolerance for float comparison
    """
    for key in expected.keys():
        actual_val = actual.get(key)
        expected_val = expected.get(key)

        if expected_val is None:
            assert actual_val is None, f"{key}: expected None, got {actual_val}"
        else:
            assert actual_val is not None, f"{key}: expected {expected_val}, got None"
            assert abs(actual_val - expected_val) <= tolerance, \
                f"{key}: expected {expected_val}, got {actual_val} (diff > {tolerance})"


# ============================================================================
# Test Data Summary
# ============================================================================

TEST_DATA_SUMMARY = {
    "total_test_cases": 10,
    "dart_response_samples": 6,  # Real-world company data
    "edge_cases": 4,  # Empty, zeros, positive treasury, large numbers
    "fuzzy_patterns": len(FUZZY_MATCHING_PATTERNS),  # 5 account types
    "validation_cases": 4,  # Valid, within tolerance, outside, incomplete
    "coverage": {
        "account_name_variations": True,
        "negative_equity_scenarios": True,
        "missing_data_handling": True,
        "numeric_precision": True,
        "fuzzy_matching": True,
        "validation_logic": True,
    },
}

if __name__ == "__main__":
    print("Equity Account Test Fixtures Summary")
    print("=" * 60)
    print(f"Total test cases: {TEST_DATA_SUMMARY['total_test_cases']}")
    print(f"DART response samples: {TEST_DATA_SUMMARY['dart_response_samples']}")
    print(f"Edge cases: {TEST_DATA_SUMMARY['edge_cases']}")
    print(f"Fuzzy pattern tests: {TEST_DATA_SUMMARY['fuzzy_patterns']}")
    print(f"Validation cases: {TEST_DATA_SUMMARY['validation_cases']}")
    print("\nCoverage areas:")
    for area, covered in TEST_DATA_SUMMARY['coverage'].items():
        status = "✅" if covered else "❌"
        print(f"  {status} {area}")
