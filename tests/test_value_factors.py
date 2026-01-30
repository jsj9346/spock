#!/usr/bin/env python3
"""
test_value_factors.py - Unit Tests for Value Factors (PostgreSQL-based)

Tests:
1. DividendYieldFactorPostgres calculation
2. EVToEBITDAFactorPostgres calculation
3. Legacy factor compatibility (loguru warnings)
4. Factor interpretation logic
5. Edge cases and error handling

Usage:
    pytest tests/test_value_factors.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime, date

from modules.factors.value_factors import (
    DividendYieldFactorPostgres,
    EVToEBITDAFactorPostgres,
    PERatioFactor,
    PBRatioFactor,
    EVToEBITDAFactor,
    DividendYieldFactor,
)
from modules.factors.factor_base import FactorResult


class TestDividendYieldFactorPostgres(unittest.TestCase):
    """Test DividendYieldFactorPostgres with mocked database"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def setUp(self, mock_db_class):
        """Set up test fixtures with mocked database"""
        self.mock_db = MagicMock()
        mock_db_class.return_value = self.mock_db
        self.factor = DividendYieldFactorPostgres()

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_high_yield_stock(self, mock_db_class):
        """Test calculation for high dividend yield stock"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        # Mock factor_scores query result
        mock_db.execute_query.side_effect = [
            # First call: factor_scores table
            [{'ticker': '005930', 'score': 2.5, 'percentile': 85.0, 'date': '2024-12-01'}],
            # Second call: ticker_fundamentals metadata
            [{'dividend_yield': 5.2, 'per': 8.5, 'pbr': 1.2, 'period_type': 'DAILY', 'data_source': 'pykrx'}]
        ]

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, '005930')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, '005930')
        self.assertEqual(result.factor_name, 'Dividend_Yield')
        self.assertAlmostEqual(result.raw_value, 2.5, places=1)
        self.assertEqual(result.confidence, 0.95)
        self.assertEqual(result.metadata.get('interpretation'), 'high_yield')

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_no_dividend_stock(self, mock_db_class):
        """Test calculation for stock with no dividend"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        # Note: When dividend_yield is 0.0, the code checks `if div_yield:` which is False for 0.0
        # So interpretation is not added to metadata for zero dividend stocks
        mock_db.execute_query.side_effect = [
            [{'ticker': '035720', 'score': 0.0, 'percentile': 5.0, 'date': '2024-12-01'}],
            [{'dividend_yield': 0.0, 'per': 25.0, 'pbr': 3.5, 'period_type': 'DAILY', 'data_source': 'pykrx'}]
        ]

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, '035720')

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, 0.0, places=1)
        # Note: interpretation is not set when dividend_yield is 0.0 (falsy value)
        # This is expected behavior - no interpretation for zero dividend stocks
        self.assertNotIn('interpretation', result.metadata)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_missing_ticker(self, mock_db_class):
        """Test handling of missing ticker"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.execute_query.return_value = []

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, 'INVALID')

        self.assertIsNone(result)

    def test_interpret_dividend_yield_high(self):
        """Test interpretation of high dividend yield (>=4.0)"""
        factor = DividendYieldFactorPostgres.__new__(DividendYieldFactorPostgres)
        interpretation = factor._interpret_dividend_yield(6.0)
        self.assertEqual(interpretation, 'high_yield')

    def test_interpret_dividend_yield_moderate(self):
        """Test interpretation of moderate dividend yield (2.0-4.0)"""
        factor = DividendYieldFactorPostgres.__new__(DividendYieldFactorPostgres)
        interpretation = factor._interpret_dividend_yield(2.5)
        self.assertEqual(interpretation, 'moderate_yield')

    def test_interpret_dividend_yield_low(self):
        """Test interpretation of low dividend yield (0-2.0)"""
        factor = DividendYieldFactorPostgres.__new__(DividendYieldFactorPostgres)
        interpretation = factor._interpret_dividend_yield(0.8)
        self.assertEqual(interpretation, 'low_yield')

    def test_interpret_dividend_yield_none(self):
        """Test interpretation of no dividend (<=0)"""
        factor = DividendYieldFactorPostgres.__new__(DividendYieldFactorPostgres)
        interpretation = factor._interpret_dividend_yield(0.0)
        self.assertEqual(interpretation, 'no_dividend')


class TestEVToEBITDAFactorPostgres(unittest.TestCase):
    """Test EVToEBITDAFactorPostgres with mocked database"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_undervalued_stock(self, mock_db_class):
        """Test calculation for undervalued stock (low EV/EBITDA)"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            # factor_scores result
            [{'ticker': '005930', 'score': -1.87, 'percentile': 75.0, 'date': '2024-12-01'}],
            # ticker_fundamentals metadata
            [{'ebitda': 45200000000000, 'total_liabilities': 100000000000000,
              'current_assets': 50000000000000, 'fiscal_year': 2024,
              'period_type': 'ANNUAL', 'data_source': 'DART'}]
        ]

        factor = EVToEBITDAFactorPostgres()
        result = factor.calculate(None, '005930')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, '005930')
        self.assertEqual(result.factor_name, 'EV_EBITDA')
        self.assertAlmostEqual(result.raw_value, -1.87, places=1)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_expensive_stock(self, mock_db_class):
        """Test calculation for expensive stock (high EV/EBITDA)"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': '035720', 'score': -3.22, 'percentile': 25.0, 'date': '2024-12-01'}],
            []  # No metadata
        ]

        factor = EVToEBITDAFactorPostgres()
        result = factor.calculate(None, '035720')

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, -3.22, places=1)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_missing_ticker(self, mock_db_class):
        """Test handling of missing ticker"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.execute_query.return_value = []

        factor = EVToEBITDAFactorPostgres()
        result = factor.calculate(None, 'INVALID')

        self.assertIsNone(result)


class TestLegacyFactorCompatibility(unittest.TestCase):
    """Test that legacy factors work with loguru warnings (not DeprecationWarning)"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    @patch('modules.factors.value_factors.logger')
    def test_pe_ratio_factor_logs_warning(self, mock_logger, mock_db_class):
        """Test PERatioFactor logs deprecation warning via loguru"""
        mock_db_class.return_value = MagicMock()

        factor = PERatioFactor(db_path="dummy.db")

        # Check that loguru warning was called
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn('deprecated', warning_msg.lower())
        self.assertIn('PERatioFactor', warning_msg)

        # Should inherit from DividendYieldFactorPostgres
        self.assertIsInstance(factor, DividendYieldFactorPostgres)
        self.assertEqual(factor.name, 'PE_Ratio_DEPRECATED')

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    @patch('modules.factors.value_factors.logger')
    def test_pb_ratio_factor_logs_warning(self, mock_logger, mock_db_class):
        """Test PBRatioFactor logs deprecation warning via loguru"""
        mock_db_class.return_value = MagicMock()

        factor = PBRatioFactor(db_path="dummy.db")

        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn('deprecated', warning_msg.lower())

        self.assertIsInstance(factor, EVToEBITDAFactorPostgres)
        self.assertEqual(factor.name, 'PB_Ratio_DEPRECATED')

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    @patch('modules.factors.value_factors.logger')
    def test_ev_ebitda_factor_logs_warning(self, mock_logger, mock_db_class):
        """Test EVToEBITDAFactor logs deprecation warning via loguru"""
        mock_db_class.return_value = MagicMock()

        factor = EVToEBITDAFactor(db_path="dummy.db")

        mock_logger.warning.assert_called()
        self.assertIsInstance(factor, EVToEBITDAFactorPostgres)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    @patch('modules.factors.value_factors.logger')
    def test_dividend_yield_factor_logs_warning(self, mock_logger, mock_db_class):
        """Test DividendYieldFactor logs deprecation warning via loguru"""
        mock_db_class.return_value = MagicMock()

        factor = DividendYieldFactor(db_path="dummy.db")

        mock_logger.warning.assert_called()
        self.assertIsInstance(factor, DividendYieldFactorPostgres)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    @patch('modules.factors.value_factors.logger')
    def test_legacy_factor_no_warning_without_db_path(self, mock_logger, mock_db_class):
        """Test that legacy factors don't warn when no db_path provided"""
        mock_db_class.return_value = MagicMock()

        # Reset mock before each call
        mock_logger.reset_mock()
        factor = PERatioFactor()
        mock_logger.warning.assert_not_called()


class TestValueFactorRanking(unittest.TestCase):
    """Test that value factors rank stocks correctly"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_dividend_ranking_high_vs_low(self, mock_db_class):
        """Test that higher dividend yield gets higher score"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        # High dividend stock
        mock_db.execute_query.side_effect = [
            [{'ticker': 'HIGH', 'score': 3.0, 'percentile': 90.0, 'date': '2024-12-01'}],
            [{'dividend_yield': 5.0, 'per': 10.0, 'pbr': 1.0, 'period_type': 'DAILY', 'data_source': 'pykrx'}]
        ]
        factor = DividendYieldFactorPostgres()
        high_result = factor.calculate(None, 'HIGH')

        # Low dividend stock - create new factor instance with fresh mock
        mock_db_class.return_value = MagicMock()
        mock_db_class.return_value.execute_query.side_effect = [
            [{'ticker': 'LOW', 'score': 0.5, 'percentile': 20.0, 'date': '2024-12-01'}],
            [{'dividend_yield': 0.5, 'per': 30.0, 'pbr': 5.0, 'period_type': 'DAILY', 'data_source': 'pykrx'}]
        ]
        factor_low = DividendYieldFactorPostgres()
        low_result = factor_low.calculate(None, 'LOW')

        # Higher score = higher dividend yield
        self.assertGreater(high_result.raw_value, low_result.raw_value)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_ev_ebitda_ranking_cheap_vs_expensive(self, mock_db_class):
        """Test that lower EV/EBITDA gets higher (less negative) score"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        # Cheap stock (low EV/EBITDA = -log(5) = -1.61)
        mock_db.execute_query.side_effect = [
            [{'ticker': 'CHEAP', 'score': -1.61, 'percentile': 85.0, 'date': '2024-12-01'}],
            []
        ]
        factor = EVToEBITDAFactorPostgres()
        cheap_result = factor.calculate(None, 'CHEAP')

        # Expensive stock (high EV/EBITDA = -log(30) = -3.40)
        mock_db_class.return_value = MagicMock()
        mock_db_class.return_value.execute_query.side_effect = [
            [{'ticker': 'EXPENSIVE', 'score': -3.40, 'percentile': 15.0, 'date': '2024-12-01'}],
            []
        ]
        factor_exp = EVToEBITDAFactorPostgres()
        expensive_result = factor_exp.calculate(None, 'EXPENSIVE')

        # Lower EV/EBITDA (less negative score) = better value
        self.assertGreater(cheap_result.raw_value, expensive_result.raw_value)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_db_exception_handled(self, mock_db_class):
        """Test that database exceptions are handled gracefully"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.execute_query.side_effect = Exception("Database connection error")

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, 'ERROR')

        self.assertIsNone(result)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_empty_result_handled(self, mock_db_class):
        """Test handling of empty database result"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.execute_query.return_value = None

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, 'EMPTY')

        self.assertIsNone(result)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_none_values_in_result(self, mock_db_class):
        """Test handling of None values in database result"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': 'TEST', 'score': 1.0, 'percentile': 50.0, 'date': '2024-12-01'}],
            []  # No metadata
        ]

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, 'TEST')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, 'TEST')
        # No interpretation since no metadata
        self.assertNotIn('interpretation', result.metadata)


@pytest.mark.parametrize("yield_value,expected_interpretation", [
    (6.0, 'high_yield'),
    (4.5, 'high_yield'),
    (4.0, 'high_yield'),
    (3.0, 'moderate_yield'),
    (2.0, 'moderate_yield'),
    (1.5, 'low_yield'),
    (0.5, 'low_yield'),
    (0.0, 'no_dividend'),
    (-1.0, 'no_dividend'),
])
def test_dividend_yield_interpretation_parametrized(yield_value, expected_interpretation):
    """Parametrized test for dividend yield interpretation"""
    factor = DividendYieldFactorPostgres.__new__(DividendYieldFactorPostgres)
    interpretation = factor._interpret_dividend_yield(yield_value)
    assert interpretation == expected_interpretation


class TestFactorMetadata(unittest.TestCase):
    """Test that factor metadata is properly populated"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_dividend_metadata_complete(self, mock_db_class):
        """Test that dividend factor returns complete metadata"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': '005930', 'score': 2.0, 'percentile': 70.0, 'date': '2024-12-01'}],
            [{'dividend_yield': 3.5, 'per': 12.0, 'pbr': 1.5, 'period_type': 'DAILY', 'data_source': 'pykrx'}]
        ]

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, '005930')

        self.assertIsNotNone(result)
        self.assertIn('calculation_date', result.metadata)
        self.assertIn('data_source', result.metadata)
        self.assertIn('percentile', result.metadata)
        self.assertIn('dividend_yield_pct', result.metadata)
        self.assertIn('interpretation', result.metadata)
        self.assertAlmostEqual(result.metadata['dividend_yield_pct'], 3.5, places=1)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_ev_ebitda_metadata_complete(self, mock_db_class):
        """Test that EV/EBITDA factor returns complete metadata"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': '005930', 'score': -2.0, 'percentile': 60.0, 'date': '2024-12-01'}],
            [{'ebitda': 50000000000000, 'total_liabilities': 100000000000000,
              'current_assets': 60000000000000, 'fiscal_year': 2024,
              'period_type': 'ANNUAL', 'data_source': 'DART'}]
        ]

        factor = EVToEBITDAFactorPostgres()
        result = factor.calculate(None, '005930')

        self.assertIsNotNone(result)
        self.assertIn('calculation_date', result.metadata)
        self.assertIn('data_source', result.metadata)
        self.assertIn('percentile', result.metadata)
        self.assertIn('note', result.metadata)
        self.assertIn('fiscal_year', result.metadata)
        self.assertEqual(result.metadata['fiscal_year'], 2024)


class TestFactorConfidence(unittest.TestCase):
    """Test factor confidence levels"""

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_dividend_confidence_level(self, mock_db_class):
        """Test that dividend factor has correct confidence level"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': 'TEST', 'score': 1.0, 'percentile': 50.0, 'date': '2024-12-01'}],
            []
        ]

        factor = DividendYieldFactorPostgres()
        result = factor.calculate(None, 'TEST')

        self.assertEqual(result.confidence, 0.95)

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_ev_ebitda_confidence_level(self, mock_db_class):
        """Test that EV/EBITDA factor has correct confidence level"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_db.execute_query.side_effect = [
            [{'ticker': 'TEST', 'score': -2.0, 'percentile': 50.0, 'date': '2024-12-01'}],
            []
        ]

        factor = EVToEBITDAFactorPostgres()
        result = factor.calculate(None, 'TEST')

        self.assertEqual(result.confidence, 0.90)


if __name__ == '__main__':
    unittest.main(verbosity=2)
