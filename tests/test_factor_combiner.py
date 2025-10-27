#!/usr/bin/env python3
"""
Unit Tests for Factor Combination Engine

Tests 3 combiner implementations and factor score calculator:
- EqualWeightCombiner: Simple arithmetic mean
- CategoryWeightCombiner: Category-weighted average
- OptimizationCombiner: Historical optimization
- FactorScoreCalculator: All-in-one calculator

Test Coverage: 80%+ with 20+ tests

Author: Spock Quant Platform - Phase 2 Multi-Factor
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import sqlite3
import tempfile
import numpy as np
import pandas as pd
from modules.factors.factor_combiner import (
    EqualWeightCombiner,
    CategoryWeightCombiner,
    OptimizationCombiner,
    DEFAULT_CATEGORY_WEIGHTS
)
from modules.factors.factor_score_calculator import FactorScoreCalculator


class TestFactorCombiner(unittest.TestCase):
    """Unit tests for Factor Combiner implementations"""

    @classmethod
    def setUpClass(cls):
        """Setup test database with sample data"""
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_path = cls.temp_db.name
        cls.temp_db.close()

        # Create test database schema
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create tables (minimal schema for testing)
        cursor.execute("""
            CREATE TABLE ticker_fundamentals (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                fiscal_year INTEGER,
                market_cap BIGINT,
                pe_ratio REAL,
                pb_ratio REAL,
                roe REAL,
                debt_to_equity REAL,
                free_float_percentage REAL,
                PRIMARY KEY (ticker, date)
            )
        """)

        cursor.execute("""
            CREATE TABLE ohlcv_data (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume BIGINT,
                PRIMARY KEY (ticker, region, date)
            )
        """)

        # Insert sample fundamental data
        cursor.execute("""
            INSERT INTO ticker_fundamentals
            (ticker, date, fiscal_year, market_cap, pe_ratio, pb_ratio, roe, debt_to_equity, free_float_percentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('TEST001', '2023-12-31', 2023, 400000000000000, 12.5, 1.8, 15.5, 45.0, 48.5))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database"""
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)

    # ===========================
    # EqualWeightCombiner Tests
    # ===========================

    def test_equal_weight_simple(self):
        """Test equal weight with 3 factors"""
        combiner = EqualWeightCombiner()
        scores = {'momentum': 75.0, 'value': 60.0, 'quality': 90.0}

        result = combiner.combine(scores)

        expected = (75.0 + 60.0 + 90.0) / 3
        self.assertAlmostEqual(result, expected, places=2)

    def test_equal_weight_all_22_factors(self):
        """Test with all 22 factors"""
        combiner = EqualWeightCombiner()
        scores = self._generate_sample_scores()

        result = combiner.combine(scores)

        expected = sum(scores.values()) / 22
        self.assertAlmostEqual(result, expected, places=2)

    def test_equal_weight_with_missing_factors(self):
        """Test with some missing factor scores (None values)"""
        combiner = EqualWeightCombiner()
        scores = {'momentum': 75.0, 'value': None, 'quality': 90.0}

        result = combiner.combine(scores)

        # Should filter out None and calculate with valid only
        expected = (75.0 + 90.0) / 2
        self.assertAlmostEqual(result, expected, places=2)

    def test_equal_weight_get_weights(self):
        """Test get_weights returns equal weights"""
        combiner = EqualWeightCombiner()
        scores = {'momentum': 75.0, 'value': 60.0, 'quality': 90.0}

        weights = combiner.get_weights(scores)

        # All weights should be equal
        self.assertEqual(len(weights), 3)
        for weight in weights.values():
            self.assertAlmostEqual(weight, 1/3, places=6)

        # Weights should sum to 1.0
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

    # ===========================
    # CategoryWeightCombiner Tests
    # ===========================

    def test_category_weight_default(self):
        """Test category weighting with default weights (0.20 each)"""
        combiner = CategoryWeightCombiner()

        # Check default weights
        self.assertEqual(combiner.category_weights, DEFAULT_CATEGORY_WEIGHTS)

        # All should be 0.20
        for weight in combiner.category_weights.values():
            self.assertAlmostEqual(weight, 0.20, places=2)

    def test_category_weight_balanced(self):
        """Test category weighting with balanced custom weights"""
        category_weights = {
            'MOMENTUM': 0.30,
            'VALUE': 0.25,
            'QUALITY': 0.25,
            'LOW_VOL': 0.15,
            'SIZE': 0.05
        }
        combiner = CategoryWeightCombiner(category_weights)

        factor_scores = {
            'momentum_12m': 75.0,
            'rsi_momentum': 68.0,  # Momentum avg: 71.5
            'pe_ratio': 60.0,
            'pb_ratio': 55.0,      # Value avg: 57.5
            'roe': 85.0,
            'roa': 90.0,           # Quality avg: 87.5
            'volatility': 45.0,    # Low-vol avg: 45.0
            'market_cap': 20.0     # Size avg: 20.0
        }

        result = combiner.combine(factor_scores)

        expected = 71.5*0.30 + 57.5*0.25 + 87.5*0.25 + 45.0*0.15 + 20.0*0.05
        self.assertAlmostEqual(result, expected, places=2)

    def test_category_weight_validation_invalid_sum(self):
        """Test weight validation (must sum to 1.0)"""
        invalid_weights = {
            'MOMENTUM': 0.50,
            'VALUE': 0.30,
            'QUALITY': 0.30  # Sum = 1.1 (invalid)
        }

        with self.assertRaises(ValueError):
            CategoryWeightCombiner(invalid_weights)

    def test_category_weight_validation_negative(self):
        """Test weight validation (no negative weights)"""
        invalid_weights = {
            'MOMENTUM': 0.60,
            'VALUE': 0.30,
            'QUALITY': -0.10,  # Negative (invalid)
            'LOW_VOL': 0.10,
            'SIZE': 0.10
        }

        with self.assertRaises(ValueError):
            CategoryWeightCombiner(invalid_weights)

    def test_category_weight_aggressive_strategy(self):
        """Test aggressive growth strategy weights"""
        category_weights = {
            'MOMENTUM': 0.40,      # Aggressive momentum focus
            'VALUE': 0.35,
            'QUALITY': 0.15,
            'LOW_VOL': 0.05,
            'SIZE': 0.05
        }
        combiner = CategoryWeightCombiner(category_weights)

        # Verify momentum gets highest weight
        self.assertEqual(combiner.category_weights['MOMENTUM'], 0.40)
        self.assertGreater(
            combiner.category_weights['MOMENTUM'],
            combiner.category_weights['QUALITY']
        )

    def test_category_weight_get_weights(self):
        """Test get_weights returns correct factor-level weights"""
        category_weights = {
            'MOMENTUM': 0.40,  # 2 factors → 0.20 each
            'VALUE': 0.30,     # 2 factors → 0.15 each
            'QUALITY': 0.30    # 2 factors → 0.15 each
        }
        combiner = CategoryWeightCombiner(category_weights)

        factor_scores = {
            'momentum_12m': 75.0,
            'rsi_momentum': 68.0,
            'pe_ratio': 60.0,
            'pb_ratio': 55.0,
            'roe': 85.0,
            'roa': 90.0
        }

        weights = combiner.get_weights(factor_scores)

        # Verify momentum factors get higher weight
        self.assertAlmostEqual(weights['momentum_12m'], 0.20, places=2)
        self.assertAlmostEqual(weights['rsi_momentum'], 0.20, places=2)
        self.assertAlmostEqual(weights['pe_ratio'], 0.15, places=2)

        # All weights sum to 1.0
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

    # ===========================
    # OptimizationCombiner Tests
    # ===========================

    def test_optimization_before_fit_error(self):
        """Test that combine() fails before fit()"""
        combiner = OptimizationCombiner(db_path=self.db_path)
        scores = {'momentum': 75.0, 'value': 60.0}

        with self.assertRaises(ValueError):
            combiner.combine(scores)

    def test_optimization_get_weights_before_fit_error(self):
        """Test that get_weights() fails before fit()"""
        combiner = OptimizationCombiner(db_path=self.db_path)
        scores = {'momentum': 75.0}

        with self.assertRaises(ValueError):
            combiner.get_weights(scores)

    def test_optimization_fit_success(self):
        """Test optimization fit completes successfully"""
        combiner = OptimizationCombiner(db_path=self.db_path)

        # Fit (currently uses equal weight fallback)
        combiner.fit(
            start_date='2018-01-01',
            end_date='2023-12-31',
            objective='max_sharpe'
        )

        # Should be fitted
        self.assertTrue(combiner._is_fitted)
        self.assertIsNotNone(combiner.optimal_weights)

    def test_optimization_combine_after_fit(self):
        """Test combine() works after fit()"""
        combiner = OptimizationCombiner(db_path=self.db_path)

        combiner.fit()

        scores = {'momentum_12m': 75.0, 'value': 60.0, 'quality': 90.0}
        result = combiner.combine(scores)

        # Should return valid composite score
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0)
        self.assertLessEqual(result, 100)

    def test_optimization_get_optimal_weights(self):
        """Test get_optimal_weights() returns valid weights"""
        combiner = OptimizationCombiner(db_path=self.db_path)
        combiner.fit()

        weights = combiner.get_optimal_weights()

        # Weights should sum to 1.0
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

        # All weights non-negative
        self.assertTrue(all(w >= 0 for w in weights.values()))

    def test_optimization_weight_normalization(self):
        """Test weight renormalization when factors missing"""
        combiner = OptimizationCombiner(db_path=self.db_path)
        combiner.fit()

        # Only 3 factors available (out of 22)
        scores = {'momentum_12m': 75.0, 'pe_ratio': 60.0, 'roe': 90.0}

        weights = combiner.get_weights(scores)

        # Weights should still sum to 1.0 after renormalization
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)

        # Only 3 factors in weights
        self.assertEqual(len(weights), 3)

    # ===========================
    # FactorScoreCalculator Tests (Integration)
    # ===========================

    def test_calculator_initialization(self):
        """Test calculator initializes with 22 factors"""
        calculator = FactorScoreCalculator(db_path=self.db_path)

        # Should have 22 factor instances
        self.assertEqual(len(calculator.factors), 22)

        # Check factor names
        expected_categories = {
            'momentum_12m', 'rsi_momentum', 'short_term_momentum',
            'volatility', 'beta', 'max_drawdown',
            'pe_ratio', 'pb_ratio', 'ev_ebitda', 'dividend_yield',
            'roe', 'roa', 'operating_margin', 'net_margin',
            'current_ratio', 'quick_ratio', 'debt_to_equity',
            'accruals_ratio', 'cf_to_ni',
            'market_cap', 'liquidity', 'float'
        }

        self.assertEqual(set(calculator.factors.keys()), expected_categories)

    def test_calculator_calculate_all_scores(self):
        """Test calculate_all_scores returns 22 factors"""
        calculator = FactorScoreCalculator(db_path=self.db_path)

        scores = calculator.calculate_all_scores('TEST001')

        # Should return 22 factors (some may be None)
        self.assertEqual(len(scores), 22)

        # Ticker key should exist
        self.assertIn('pe_ratio', scores)
        self.assertIn('roe', scores)
        self.assertIn('market_cap', scores)

    def test_calculator_composite_score_integration(self):
        """Integration test: calculator + combiner"""
        calculator = FactorScoreCalculator(db_path=self.db_path)
        combiner = EqualWeightCombiner()

        composite = calculator.calculate_composite_score('TEST001', combiner)

        # Should return float between 0-100
        self.assertIsInstance(composite, float)
        self.assertGreaterEqual(composite, 0)
        self.assertLessEqual(composite, 100)

    def test_calculator_batch_calculate_composite(self):
        """Test batch composite calculation"""
        calculator = FactorScoreCalculator(db_path=self.db_path)
        combiner = EqualWeightCombiner()

        tickers = ['TEST001']
        df = calculator.batch_calculate_composite(tickers, combiner)

        # Should return DataFrame with required columns
        self.assertIn('ticker', df.columns)
        self.assertIn('alpha_score', df.columns)
        self.assertIn('valid_factors_count', df.columns)

        # Should have 1 row
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['ticker'], 'TEST001')

    # ===========================
    # Edge Cases
    # ===========================

    def test_all_combiners_with_empty_scores(self):
        """Test all combiners handle empty scores gracefully"""
        equal_combiner = EqualWeightCombiner()
        category_combiner = CategoryWeightCombiner()

        empty_scores = {}

        # All should return neutral 50.0
        self.assertEqual(equal_combiner.combine(empty_scores), 50.0)
        self.assertEqual(category_combiner.combine(empty_scores), 50.0)

    def test_all_combiners_with_all_none(self):
        """Test all combiners handle all None scores"""
        equal_combiner = EqualWeightCombiner()
        category_combiner = CategoryWeightCombiner()

        all_none = {'momentum': None, 'value': None, 'quality': None}

        # All should return neutral 50.0
        self.assertEqual(equal_combiner.combine(all_none), 50.0)
        self.assertEqual(category_combiner.combine(all_none), 50.0)

    def test_weight_sum_validation(self):
        """Test all combiners produce weights that sum to 1.0"""
        scores = self._generate_sample_scores()

        # Equal weight
        equal_combiner = EqualWeightCombiner()
        equal_weights = equal_combiner.get_weights(scores)
        self.assertAlmostEqual(sum(equal_weights.values()), 1.0, places=6)

        # Category weight
        category_combiner = CategoryWeightCombiner()
        category_weights = category_combiner.get_weights(scores)
        self.assertAlmostEqual(sum(category_weights.values()), 1.0, places=6)

        # Optimization weight
        opt_combiner = OptimizationCombiner(db_path=self.db_path)
        opt_combiner.fit()
        opt_weights = opt_combiner.get_weights(scores)
        self.assertAlmostEqual(sum(opt_weights.values()), 1.0, places=6)

    # ===========================
    # Helper Methods
    # ===========================

    def _generate_sample_scores(self) -> dict:
        """Generate realistic sample scores for all 22 factors"""
        return {
            # Momentum (3)
            'momentum_12m': 75.5,
            'rsi_momentum': 68.2,
            'short_term_momentum': 72.0,

            # Low-volatility (3)
            'volatility': 45.0,
            'beta': 50.0,
            'max_drawdown': 55.0,

            # Value (4)
            'pe_ratio': 60.0,
            'pb_ratio': 55.0,
            'ev_ebitda': 58.0,
            'dividend_yield': 65.0,

            # Quality (9)
            'roe': 85.0,
            'roa': 80.0,
            'operating_margin': 82.0,
            'net_margin': 78.0,
            'current_ratio': 75.0,
            'quick_ratio': 72.0,
            'debt_to_equity': 90.0,
            'accruals_ratio': 70.0,
            'cf_to_ni': 88.0,

            # Size (3)
            'market_cap': 20.0,
            'liquidity': 85.0,
            'float': 52.0
        }


def run_tests():
    """Run all tests and print summary"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFactorCombiner)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*80)
    print("Factor Combiner Test Summary")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.testsRun > 0:
        print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    else:
        print("Success rate: N/A (no tests run)")
    print("="*80)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
