#!/usr/bin/env python3
"""
Unit Test for EarningsMomentumFactor

Tests the Earnings Momentum factor calculation logic with synthetic data.

Author: Quant Platform Development Team
Date: 2025-10-23
"""

import sys
import os
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.factors.momentum_factors import EarningsMomentumFactor


class TestEarningsMomentumFactor(unittest.TestCase):
    """Test suite for EarningsMomentumFactor"""

    def setUp(self):
        """Set up test fixtures"""
        self.factor = EarningsMomentumFactor()

    def create_test_data(self, eps_values: list, dates: list = None) -> pd.DataFrame:
        """
        Create synthetic test data for EPS

        Args:
            eps_values: List of EPS values (oldest to newest)
            dates: Optional list of dates (defaults to quarterly dates)

        Returns:
            DataFrame with required columns for factor calculation
        """
        n = len(eps_values)

        if dates is None:
            # Generate quarterly dates (90 days apart)
            base_date = datetime(2024, 1, 1)
            dates = [base_date + timedelta(days=90*i) for i in range(n)]

        # Create data with required columns
        # Handle zero EPS by using arbitrary P/E ratio
        per_values = []
        for eps in eps_values:
            if eps != 0:
                per_values.append(100.0 / eps)
            else:
                per_values.append(np.nan)  # Use NaN for zero EPS

        data = pd.DataFrame({
            'date': dates,
            'close': [100.0 + i*10 for i in range(n)],  # Arbitrary prices
            'per': per_values,
            'trailing_eps': eps_values
        })

        return data

    def test_strong_earnings_growth(self):
        """Test case: Strong earnings growth (positive momentum)"""
        # EPS growing from $5 to $10 (YoY: 33% from 7.5 to 10)
        eps_values = [5.0, 6.0, 7.5, 10.0]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_STRONG_GROWTH')

        self.assertIsNotNone(result, "Should return result for valid data")
        self.assertGreater(result.raw_value, 20.0, "Strong growth should have positive momentum score")
        self.assertEqual(result.metadata['data_source'], 'trailing_eps')

        print(f"\n✓ Strong Growth Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  YoY Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Acceleration: {result.metadata['earnings_acceleration']:.2f}")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_declining_earnings(self):
        """Test case: Declining earnings (negative momentum)"""
        # EPS declining from $10 to $5 (-50% growth)
        eps_values = [10.0, 9.0, 7.0, 5.0]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_DECLINING')

        self.assertIsNotNone(result)
        self.assertLess(result.raw_value, 0.0, "Declining earnings should have negative momentum")

        print(f"\n✓ Declining Earnings Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  YoY Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Acceleration: {result.metadata['earnings_acceleration']:.2f}")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_stable_earnings(self):
        """Test case: Stable earnings (neutral momentum)"""
        # EPS stable around $8
        eps_values = [8.0, 8.1, 8.2, 8.1]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_STABLE')

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.raw_value, 0.0, delta=5.0,
                               msg="Stable earnings should have near-zero momentum")

        print(f"\n✓ Stable Earnings Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  YoY Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Acceleration: {result.metadata['earnings_acceleration']:.2f}")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_accelerating_growth(self):
        """Test case: Accelerating earnings growth"""
        # EPS growth rate accelerating: 10% -> 20% -> 40%
        eps_values = [10.0, 11.0, 13.2, 18.48]  # 10%, 20%, 40% growth rates
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_ACCELERATING')

        self.assertIsNotNone(result)
        self.assertGreater(result.metadata['earnings_acceleration'], 0.0,
                          "Accelerating growth should have positive acceleration")

        print(f"\n✓ Accelerating Growth Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  YoY Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Acceleration: {result.metadata['earnings_acceleration']:.2f}")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_calculated_eps_fallback(self):
        """Test case: Fallback to calculated EPS from P/E ratio"""
        # Data without trailing_eps column - should calculate from close/per
        eps_values = [5.0, 6.0, 7.5, 10.0]
        data = pd.DataFrame({
            'date': [datetime(2024, 1, 1) + timedelta(days=90*i) for i in range(4)],
            'close': [100.0, 120.0, 150.0, 200.0],
            'per': [20.0, 20.0, 20.0, 20.0]  # Constant P/E
        })

        result = self.factor.calculate(data, 'TEST_CALCULATED_EPS')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['data_source'], 'calculated')
        self.assertGreater(result.raw_value, 0.0, "Rising price with constant P/E = rising EPS")

        print(f"\n✓ Calculated EPS Test:")
        print(f"  Data Source: {result.metadata['data_source']}")
        print(f"  YoY Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_insufficient_data(self):
        """Test case: Insufficient data (< 2 data points)"""
        # Only 1 EPS value - should return None
        eps_values = [10.0]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_INSUFFICIENT')

        self.assertIsNone(result, "Should return None for insufficient data")

        print(f"\n✓ Insufficient Data Test: Correctly returned None")

    def test_extreme_growth_capping(self):
        """Test case: Extreme growth should be capped"""
        # EPS from $1 to $100 (9900% growth - should be capped)
        eps_values = [1.0, 10.0, 50.0, 100.0]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_EXTREME_GROWTH')

        self.assertIsNotNone(result)
        # Growth should be capped at 500%
        self.assertLessEqual(result.metadata['eps_growth_yoy'], 500.0,
                            "Extreme growth should be capped at 500%")

        print(f"\n✓ Extreme Growth Capping Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  Actual Growth: 9900%")
        print(f"  Capped Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Momentum Score: {result.raw_value:.2f}")

    def test_zero_eps_handling(self):
        """Test case: Handle zero/negative EPS transition"""
        # EPS from $0 to $5 (compares 5 vs 3, not 5 vs 0)
        eps_values = [0.0, 1.0, 3.0, 5.0]
        data = self.create_test_data(eps_values)

        result = self.factor.calculate(data, 'TEST_ZERO_EPS')

        self.assertIsNotNone(result)
        # YoY growth = (5 - 3) / 3 = 66.67%
        self.assertAlmostEqual(result.metadata['eps_growth_yoy'], 66.67, delta=0.1,
                              msg="YoY growth should be 66.67% (5 vs 3)")

        print(f"\n✓ Zero EPS Handling Test:")
        print(f"  EPS Series: {eps_values}")
        print(f"  Assigned Growth: {result.metadata['eps_growth_yoy']:.2f}%")
        print(f"  Momentum Score: {result.raw_value:.2f}")


def run_tests():
    """Run all tests and print results"""
    print("=" * 70)
    print("EarningsMomentumFactor Unit Tests")
    print("=" * 70)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEarningsMomentumFactor)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
