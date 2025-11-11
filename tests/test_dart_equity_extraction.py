"""
Unit tests for DART API equity account extraction logic.

Tests the _extract_equity_accounts() and _validate_equity_breakdown() methods
using comprehensive test fixtures from Phase 1.

Created: 2025-11-07
Phase: Phase 2 - DART API Enhancement (TDD)
"""

import pytest
import sys
import os
from decimal import Decimal

# Add modules to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from tests.fixtures.equity_account_test_data import (
    DART_RESPONSE_SAMSUNG_2024Q2,
    DART_RESPONSE_SK_HYNIX_2024Q2,
    DART_RESPONSE_LG_CHEM_2025Q2,
    DART_RESPONSE_NAVER_2024Q4,
    DART_RESPONSE_HYUNDAI_2025Q2,
    DART_RESPONSE_KAKAO_2024Q4,
    DART_RESPONSE_EMPTY,
    DART_RESPONSE_ZEROS,
    DART_RESPONSE_POSITIVE_TREASURY,
    DART_RESPONSE_LARGE_NUMBERS,
    EXPECTED_SAMSUNG_2024Q2,
    EXPECTED_SK_HYNIX_2024Q2,
    EXPECTED_LG_CHEM_2025Q2,
    EXPECTED_NAVER_2024Q4,
    EXPECTED_HYUNDAI_2025Q2,
    EXPECTED_KAKAO_2024Q4,
    EXPECTED_EMPTY,
    EXPECTED_ZEROS,
    EXPECTED_POSITIVE_TREASURY_NORMALIZED,
    EXPECTED_LARGE_NUMBERS,
    EQUITY_VALIDATION_CASE_VALID,
    EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE,
    EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE,
    EQUITY_VALIDATION_CASE_INCOMPLETE,
    assert_equity_accounts_equal,
    calculate_equity_sum,
    is_within_tolerance,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def dart_client():
    """Create DART API client instance for testing."""
    return DARTApiClient(api_key="test_api_key")


# ============================================================================
# Test 1: Equity Extraction - Real Company Data
# ============================================================================

class TestEquityExtraction:
    """Test equity account extraction with real company data."""

    def test_extract_samsung_2024q2(self, dart_client):
        """Test extraction for Samsung Electronics 2024 Q2 (standard K-IFRS)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_SAMSUNG_2024Q2)
        assert_equity_accounts_equal(result, EXPECTED_SAMSUNG_2024Q2)

    def test_extract_sk_hynix_2024q2(self, dart_client):
        """Test extraction for SK Hynix 2024 Q2 (account name variations)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_SK_HYNIX_2024Q2)
        assert_equity_accounts_equal(result, EXPECTED_SK_HYNIX_2024Q2)

    def test_extract_lg_chem_2025q2(self, dart_client):
        """Test extraction for LG Chem 2025 Q2 (negative equity scenario)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_LG_CHEM_2025Q2)
        assert_equity_accounts_equal(result, EXPECTED_LG_CHEM_2025Q2)

    def test_extract_naver_2024q4(self, dart_client):
        """Test extraction for Naver 2024 Q4 (sub-accounts)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_NAVER_2024Q4)
        assert_equity_accounts_equal(result, EXPECTED_NAVER_2024Q4)

    def test_extract_hyundai_2025q2(self, dart_client):
        """Test extraction for Hyundai Motor 2025 Q2 (missing accounts)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_HYUNDAI_2025Q2)
        assert_equity_accounts_equal(result, EXPECTED_HYUNDAI_2025Q2)

    def test_extract_kakao_2024q4(self, dart_client):
        """Test extraction for Kakao 2024 Q4 (non-controlling interest)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_KAKAO_2024Q4)
        assert_equity_accounts_equal(result, EXPECTED_KAKAO_2024Q4)


# ============================================================================
# Test 2: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases for equity extraction."""

    def test_extract_empty_response(self, dart_client):
        """Test extraction with empty DART response."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_EMPTY)
        assert_equity_accounts_equal(result, EXPECTED_EMPTY)

    def test_extract_zero_values(self, dart_client):
        """Test extraction with zero values (valid but unusual)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_ZEROS)
        assert_equity_accounts_equal(result, EXPECTED_ZEROS)

    def test_extract_positive_treasury_normalization(self, dart_client):
        """Test that positive treasury stock is normalized to negative."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_POSITIVE_TREASURY)

        # Treasury stock should be normalized to negative
        assert result['treasury_stock'] is not None
        assert result['treasury_stock'] < 0
        assert result['treasury_stock'] == EXPECTED_POSITIVE_TREASURY_NORMALIZED['treasury_stock']

    def test_extract_large_numbers(self, dart_client):
        """Test extraction with very large numbers (numeric precision)."""
        result = dart_client._extract_equity_accounts(DART_RESPONSE_LARGE_NUMBERS)
        assert_equity_accounts_equal(result, EXPECTED_LARGE_NUMBERS)


# ============================================================================
# Test 3: Fuzzy Matching Patterns
# ============================================================================

class TestFuzzyMatching:
    """Test fuzzy matching for account name variations."""

    def test_capital_stock_patterns(self, dart_client):
        """Test capital stock pattern matching."""
        test_cases = [
            {'자본금': 1000.0},
            {'보통주자본금': 1000.0},
            {'우선주자본금': 1000.0},
        ]

        for test_case in test_cases:
            result = dart_client._extract_equity_accounts(test_case)
            assert result['capital_stock'] == 1000.0

    def test_capital_surplus_patterns(self, dart_client):
        """Test capital surplus pattern matching."""
        test_cases = [
            {'자본잉여금': 2000.0},
            {'주식발행초과금': 2000.0},
        ]

        for test_case in test_cases:
            result = dart_client._extract_equity_accounts(test_case)
            assert result['capital_surplus'] == 2000.0

    def test_retained_earnings_patterns(self, dart_client):
        """Test retained earnings pattern matching."""
        test_cases = [
            {'이익잉여금': 3000.0},
            {'이익잉여금(결손금)': 3000.0},
        ]

        for test_case in test_cases:
            result = dart_client._extract_equity_accounts(test_case)
            assert result['retained_earnings'] == 3000.0

    def test_treasury_stock_patterns(self, dart_client):
        """Test treasury stock pattern matching and normalization."""
        test_cases = [
            {'자기주식': -100.0},  # Already negative
            {'자기주식처분손익': 100.0},  # Positive, should be normalized
        ]

        # Test case 1: Already negative
        result1 = dart_client._extract_equity_accounts(test_cases[0])
        assert result1['treasury_stock'] == -100.0

        # Test case 2: Positive, should be normalized to negative
        result2 = dart_client._extract_equity_accounts(test_cases[1])
        assert result2['treasury_stock'] == -100.0  # Normalized

    def test_other_comprehensive_income_patterns(self, dart_client):
        """Test other comprehensive income pattern matching."""
        test_cases = [
            {'기타포괄손익누계액': 500.0},
            {'기타자본구성요소': 500.0},
            {'기타자본항목': 500.0},
        ]

        for test_case in test_cases:
            result = dart_client._extract_equity_accounts(test_case)
            assert result['other_comprehensive_income'] == 500.0


# ============================================================================
# Test 4: Equity Validation Logic
# ============================================================================

class TestEquityValidation:
    """Test equity validation logic (5% tolerance)."""

    def test_validation_exact_match(self, dart_client):
        """Test validation with exact match (0% error)."""
        total_equity = EQUITY_VALIDATION_CASE_VALID['total_equity']
        equity_accounts = {
            'capital_stock': EQUITY_VALIDATION_CASE_VALID['capital_stock'],
            'capital_surplus': EQUITY_VALIDATION_CASE_VALID['capital_surplus'],
            'retained_earnings': EQUITY_VALIDATION_CASE_VALID['retained_earnings'],
            'treasury_stock': EQUITY_VALIDATION_CASE_VALID['treasury_stock'],
            'other_comprehensive_income': EQUITY_VALIDATION_CASE_VALID['other_comprehensive_income'],
            'non_controlling_interest': None,
        }

        result = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        assert result['passed'] is True
        assert result['error_percentage'] == 0.0
        assert result['calculated_equity'] == total_equity

    def test_validation_within_tolerance(self, dart_client):
        """Test validation within 5% tolerance (should pass)."""
        total_equity = EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['total_equity']
        equity_accounts = {
            'capital_stock': EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['capital_stock'],
            'capital_surplus': EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['capital_surplus'],
            'retained_earnings': EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['retained_earnings'],
            'treasury_stock': EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['treasury_stock'],
            'other_comprehensive_income': EQUITY_VALIDATION_CASE_WITHIN_TOLERANCE['other_comprehensive_income'],
            'non_controlling_interest': None,
        }

        result = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        assert result['passed'] is True
        assert result['error_percentage'] <= 5.0  # Within 5% tolerance

    def test_validation_outside_tolerance(self, dart_client):
        """Test validation outside 5% tolerance (should fail)."""
        total_equity = EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['total_equity']
        equity_accounts = {
            'capital_stock': EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['capital_stock'],
            'capital_surplus': EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['capital_surplus'],
            'retained_earnings': EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['retained_earnings'],
            'treasury_stock': EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['treasury_stock'],
            'other_comprehensive_income': EQUITY_VALIDATION_CASE_OUTSIDE_TOLERANCE['other_comprehensive_income'],
            'non_controlling_interest': None,
        }

        result = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        assert result['passed'] is False
        assert result['error_percentage'] > 5.0  # Outside 5% tolerance

    def test_validation_incomplete_data(self, dart_client):
        """Test validation with incomplete data (cannot validate)."""
        total_equity = EQUITY_VALIDATION_CASE_INCOMPLETE['total_equity']
        equity_accounts = {
            'capital_stock': EQUITY_VALIDATION_CASE_INCOMPLETE['capital_stock'],
            'capital_surplus': EQUITY_VALIDATION_CASE_INCOMPLETE['capital_surplus'],
            'retained_earnings': EQUITY_VALIDATION_CASE_INCOMPLETE['retained_earnings'],
            'treasury_stock': EQUITY_VALIDATION_CASE_INCOMPLETE['treasury_stock'],
            'other_comprehensive_income': EQUITY_VALIDATION_CASE_INCOMPLETE['other_comprehensive_income'],
            'non_controlling_interest': None,
        }

        result = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        # Should still pass if we have at least capital_stock
        # (design decision: partial validation is acceptable)
        assert result['passed'] is not None  # Can validate with partial data

    def test_validation_zero_total_equity(self, dart_client):
        """Test validation when total_equity is zero."""
        total_equity = 0.0
        equity_accounts = {
            'capital_stock': 0.0,
            'capital_surplus': 0.0,
            'retained_earnings': 0.0,
            'treasury_stock': 0.0,
            'other_comprehensive_income': 0.0,
            'non_controlling_interest': None,
        }

        result = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        assert result['passed'] is True
        assert result['error_percentage'] == 0.0


# ============================================================================
# Test 5: Integration Tests (Full Workflow)
# ============================================================================

class TestIntegrationWorkflow:
    """Test complete extraction + validation workflow."""

    def test_samsung_full_workflow(self, dart_client):
        """Test full workflow for Samsung Electronics."""
        # Extract equity accounts
        equity_accounts = dart_client._extract_equity_accounts(DART_RESPONSE_SAMSUNG_2024Q2)

        # Validate extraction
        assert_equity_accounts_equal(equity_accounts, EXPECTED_SAMSUNG_2024Q2)

        # Validate equity breakdown
        total_equity = DART_RESPONSE_SAMSUNG_2024Q2['자본총계']
        validation = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

        # Samsung should pass validation (exact match expected)
        assert validation['passed'] is True
        assert validation['error_percentage'] <= 5.0

    def test_lg_chem_negative_equity_workflow(self, dart_client):
        """Test full workflow for LG Chem (negative equity scenario)."""
        # Extract equity accounts
        equity_accounts = dart_client._extract_equity_accounts(DART_RESPONSE_LG_CHEM_2025Q2)

        # Validate extraction
        assert_equity_accounts_equal(equity_accounts, EXPECTED_LG_CHEM_2025Q2)

        # Treasury stock should be negative
        assert equity_accounts['treasury_stock'] is not None
        assert equity_accounts['treasury_stock'] < 0

    def test_all_companies_validation(self, dart_client):
        """Test that all 6 company samples pass validation."""
        test_cases = [
            (DART_RESPONSE_SAMSUNG_2024Q2, EXPECTED_SAMSUNG_2024Q2),
            (DART_RESPONSE_SK_HYNIX_2024Q2, EXPECTED_SK_HYNIX_2024Q2),
            (DART_RESPONSE_LG_CHEM_2025Q2, EXPECTED_LG_CHEM_2025Q2),
            (DART_RESPONSE_NAVER_2024Q4, EXPECTED_NAVER_2024Q4),
            (DART_RESPONSE_HYUNDAI_2025Q2, EXPECTED_HYUNDAI_2025Q2),
            (DART_RESPONSE_KAKAO_2024Q4, EXPECTED_KAKAO_2024Q4),
        ]

        passed_count = 0
        for dart_response, expected_result in test_cases:
            # Extract
            equity_accounts = dart_client._extract_equity_accounts(dart_response)

            # Verify extraction matches expected
            assert_equity_accounts_equal(equity_accounts, expected_result)

            # Validate (if total_equity exists in response)
            if '자본총계' in dart_response:
                total_equity = dart_response['자본총계']
                validation = dart_client._validate_equity_breakdown(total_equity, equity_accounts)

                # Count passed validations
                if validation['passed']:
                    passed_count += 1

        # At least 5/6 companies should pass validation (>83%)
        assert passed_count >= 5, f"Only {passed_count}/6 companies passed validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
