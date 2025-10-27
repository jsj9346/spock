#!/usr/bin/env python3
"""
Unit Tests for Size Factors (Phase 2 Final)

Tests 3 Size factor implementations:
- Market Cap: Company size with small-cap tilt
- Liquidity: Trading volume and ease of execution
- Float: Free float percentage

Test Coverage:
- Factor calculation accuracy
- NULL value handling
- Edge cases (extreme values, missing data)
- Metadata and confidence scores
- Database + OHLCV hybrid data

Author: Spock Quant Platform - Phase 2 Complete
"""

import unittest
import sqlite3
import pandas as pd
import os
import tempfile
from datetime import datetime, timedelta
from modules.factors.size_factors import (
    MarketCapFactor,
    LiquidityFactor,
    FloatFactor
)


class TestSizeFactors(unittest.TestCase):
    """Unit tests for Size factor implementations"""

    @classmethod
    def setUpClass(cls):
        """Setup test database with sample data"""
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_path = cls.temp_db.name
        cls.temp_db.close()

        # Create test database schema
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE ticker_fundamentals (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                fiscal_year INTEGER,
                market_cap BIGINT,
                shares_outstanding BIGINT,
                close_price REAL,
                free_float_percentage REAL,
                PRIMARY KEY (ticker, date)
            )
        """)

        # Insert test data for 5 stocks with different size profiles
        test_data = [
            # Stock 1: Large Cap (Samsung-like)
            ('TEST001', '2023-12-31', 2023, 400000000000000, 5969783000, 67000, 45.5),

            # Stock 2: Mid Cap
            ('TEST002', '2023-12-31', 2023, 5000000000000, 100000000, 50000, 52.0),

            # Stock 3: Small Cap
            ('TEST003', '2023-12-31', 2023, 500000000000, 25000000, 20000, 38.5),

            # Stock 4: Micro Cap (very small)
            ('TEST004', '2023-12-31', 2023, 50000000000, 5000000, 10000, 25.0),

            # Stock 5: Large Cap with low float (chaebol)
            ('TEST005', '2023-12-31', 2023, 300000000000000, 4000000000, 75000, 28.0),
        ]

        cursor.executemany("""
            INSERT INTO ticker_fundamentals (
                ticker, date, fiscal_year, market_cap, shares_outstanding, close_price, free_float_percentage
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, test_data)

        conn.commit()
        conn.close()

        # Create sample OHLCV data for Liquidity factor testing
        cls.sample_ohlcv = cls._create_sample_ohlcv()

    @classmethod
    def _create_sample_ohlcv(cls):
        """Create sample OHLCV DataFrame for Liquidity testing"""
        dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]

        # High liquidity stock (Samsung-like)
        high_liquidity_df = pd.DataFrame({
            'date': dates,
            'close': [67000] * 30,
            'volume': [20000000] * 30,  # 20M shares/day × 67K = 1.34 trillion KRW/day
        })

        # Medium liquidity stock
        medium_liquidity_df = pd.DataFrame({
            'date': dates,
            'close': [50000] * 30,
            'volume': [120000] * 30,  # 120K shares × 50K = 6 billion KRW/day (60억원 - Medium)
        })

        # Low liquidity stock
        low_liquidity_df = pd.DataFrame({
            'date': dates,
            'close': [20000] * 30,
            'volume': [10000] * 30,  # 10K shares × 20K = 200 million KRW/day
        })

        return {
            'TEST001': high_liquidity_df,
            'TEST002': medium_liquidity_df,
            'TEST003': low_liquidity_df
        }

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database"""
        if os.path.exists(cls.db_path):
            os.unlink(cls.db_path)

    # ===========================
    # Market Cap Factor Tests
    # ===========================

    def test_market_cap_large_cap(self):
        """Test Market Cap calculation for large cap stock"""
        factor = MarketCapFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Market Cap')
        self.assertEqual(result.confidence, 0.95)
        self.assertIn('market_cap', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertEqual(result.metadata['category'], 'Large Cap')
        # Large cap should have negative score (for small-cap tilt)
        self.assertLess(result.raw_value, 0)

    def test_market_cap_mid_cap(self):
        """Test Market Cap for mid cap stock"""
        factor = MarketCapFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST002')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Mid Cap')
        # Mid cap has less negative score than large cap
        large_result = factor.calculate(None, ticker='TEST001')
        self.assertGreater(result.raw_value, large_result.raw_value)

    def test_market_cap_small_cap(self):
        """Test Market Cap for small cap stock"""
        factor = MarketCapFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST003')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Small Cap')
        # Small cap should have higher score than large cap (less negative or positive)
        large_result = factor.calculate(None, ticker='TEST001')
        self.assertGreater(result.raw_value, large_result.raw_value)

    def test_market_cap_micro_cap(self):
        """Test Market Cap for micro cap stock"""
        factor = MarketCapFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST004')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Small Cap')
        # Micro cap has highest score (most positive/least negative)
        small_result = factor.calculate(None, ticker='TEST003')
        self.assertGreater(result.raw_value, small_result.raw_value)

    def test_market_cap_metadata(self):
        """Test Market Cap metadata completeness"""
        factor = MarketCapFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('market_cap', result.metadata)
        self.assertIn('market_cap_trillion', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertIn('fiscal_year', result.metadata)
        self.assertEqual(result.metadata['fiscal_year'], 2023)

    # ===========================
    # Liquidity Factor Tests
    # ===========================

    def test_liquidity_high_liquidity(self):
        """Test Liquidity calculation for highly liquid stock"""
        factor = LiquidityFactor(db_path=self.db_path)
        result = factor.calculate(self.sample_ohlcv['TEST001'], ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Liquidity')
        self.assertEqual(result.confidence, 0.85)
        self.assertIn('avg_liquidity', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertEqual(result.metadata['category'], 'High Liquidity')
        # High liquidity = positive score
        self.assertGreater(result.raw_value, 0)

    def test_liquidity_medium_liquidity(self):
        """Test Liquidity for medium liquidity stock"""
        factor = LiquidityFactor(db_path=self.db_path)
        result = factor.calculate(self.sample_ohlcv['TEST002'], ticker='TEST002')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Medium Liquidity')
        # Medium liquidity has lower score than high liquidity
        high_result = factor.calculate(self.sample_ohlcv['TEST001'], ticker='TEST001')
        self.assertLess(result.raw_value, high_result.raw_value)

    def test_liquidity_low_liquidity(self):
        """Test Liquidity for low liquidity stock"""
        factor = LiquidityFactor(db_path=self.db_path)
        result = factor.calculate(self.sample_ohlcv['TEST003'], ticker='TEST003')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Low Liquidity')
        # Low liquidity has lowest score
        medium_result = factor.calculate(self.sample_ohlcv['TEST002'], ticker='TEST002')
        self.assertLess(result.raw_value, medium_result.raw_value)

    def test_liquidity_insufficient_data(self):
        """Test Liquidity with insufficient data points"""
        factor = LiquidityFactor(db_path=self.db_path)

        # Create DataFrame with only 10 days (less than min 20)
        dates = [datetime.now() - timedelta(days=i) for i in range(10, 0, -1)]
        insufficient_df = pd.DataFrame({
            'date': dates,
            'close': [50000] * 10,
            'volume': [100000] * 10
        })

        result = factor.calculate(insufficient_df, ticker='TEST_INSUF')
        self.assertIsNone(result)

    def test_liquidity_missing_columns(self):
        """Test Liquidity with missing required columns"""
        factor = LiquidityFactor(db_path=self.db_path)

        # DataFrame missing 'volume' column
        dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
        missing_col_df = pd.DataFrame({
            'date': dates,
            'close': [50000] * 30
        })

        result = factor.calculate(missing_col_df, ticker='TEST_MISSING')
        self.assertIsNone(result)

    def test_liquidity_metadata(self):
        """Test Liquidity metadata completeness"""
        factor = LiquidityFactor(db_path=self.db_path)
        result = factor.calculate(self.sample_ohlcv['TEST001'], ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('avg_liquidity', result.metadata)
        self.assertIn('avg_liquidity_billion', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertIn('days_calculated', result.metadata)
        self.assertEqual(result.metadata['days_calculated'], 30)

    # ===========================
    # Float Factor Tests
    # ===========================

    def test_float_high_float(self):
        """Test Float calculation for high float stock"""
        factor = FloatFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST002')

        self.assertIsNotNone(result)
        self.assertEqual(result.factor_name, 'Free Float')
        self.assertEqual(result.confidence, 0.80)
        self.assertIn('free_float_pct', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertEqual(result.metadata['category'], 'High Float')
        # High float = positive score (52%)
        self.assertGreater(result.raw_value, 50)

    def test_float_medium_float(self):
        """Test Float for medium float stock"""
        factor = FloatFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Medium Float')
        self.assertAlmostEqual(result.raw_value, 45.5, places=1)

    def test_float_low_float(self):
        """Test Float for low float stock (chaebol)"""
        factor = FloatFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST005')

        self.assertIsNotNone(result)
        self.assertEqual(result.metadata['category'], 'Low Float')
        # Low float has lowest score (28%)
        self.assertLess(result.raw_value, 30)

    def test_float_missing_data(self):
        """Test Float with missing ticker"""
        factor = FloatFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='NONEXISTENT')

        self.assertIsNone(result)

    def test_float_metadata(self):
        """Test Float metadata completeness"""
        factor = FloatFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='TEST001')

        self.assertIsNotNone(result)
        self.assertIn('free_float_pct', result.metadata)
        self.assertIn('category', result.metadata)
        self.assertIn('fiscal_year', result.metadata)
        self.assertEqual(result.metadata['fiscal_year'], 2023)

    # ===========================
    # Edge Cases Tests
    # ===========================

    def test_required_columns(self):
        """Test get_required_columns() for all factors"""
        market_cap_factor = MarketCapFactor(db_path=self.db_path)
        liquidity_factor = LiquidityFactor(db_path=self.db_path)
        float_factor = FloatFactor(db_path=self.db_path)

        # Market Cap uses DB only
        self.assertEqual(market_cap_factor.get_required_columns(), [])

        # Liquidity needs OHLCV data
        self.assertEqual(liquidity_factor.get_required_columns(), ['volume', 'close'])

        # Float uses DB only
        self.assertEqual(float_factor.get_required_columns(), [])

    def test_confidence_scores(self):
        """Test confidence scores for all factors"""
        market_cap_result = MarketCapFactor(db_path=self.db_path).calculate(None, 'TEST001')
        liquidity_result = LiquidityFactor(db_path=self.db_path).calculate(self.sample_ohlcv['TEST001'], 'TEST001')
        float_result = FloatFactor(db_path=self.db_path).calculate(None, 'TEST001')

        self.assertEqual(market_cap_result.confidence, 0.95)  # Highest - direct calculation
        self.assertEqual(liquidity_result.confidence, 0.85)  # Medium - 30-day average
        self.assertEqual(float_result.confidence, 0.80)  # Lowest - data availability issues


def run_tests():
    """Run all tests and print summary"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestSizeFactors)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*80)
    print("Size Factors Test Summary")
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
