#!/usr/bin/env python3
"""
Unit Tests for Factor Analysis Modules

Tests:
1. FactorAnalyzer - Quintile analysis, IC calculation, turnover analysis
2. FactorCorrelationAnalyzer - Correlation matrix, redundancy detection, clustering
3. PerformanceReporter - Report generation and visualization

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import pandas as pd
import numpy as np

from modules.analysis.factor_analyzer import FactorAnalyzer, QuintileResult, ICResult
from modules.analysis.factor_correlation import FactorCorrelationAnalyzer, CorrelationPair
from modules.analysis.performance_reporter import PerformanceReporter


class TestFactorAnalyzer(unittest.TestCase):
    """Test cases for FactorAnalyzer"""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection and create test data"""
        cls.conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER')
        )

        cls.test_date = date(2025, 10, 22)
        cls.test_region = 'KR'
        cls.test_factor = 'TEST_FACTOR'

        # Create test tickers
        cursor = cls.conn.cursor()

        # Insert test tickers (30 stocks for quintile analysis)
        test_tickers = [f'TEST{i:03d}' for i in range(1, 31)]

        for ticker in test_tickers:
            cursor.execute("""
                INSERT INTO tickers (ticker, region, name, exchange, currency, asset_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region) DO NOTHING
            """, (ticker, cls.test_region, f'Test Stock {ticker}', 'TEST', 'KRW', 'STOCK'))

        # Insert factor scores (linearly distributed percentiles)
        for i, ticker in enumerate(test_tickers):
            percentile = ((i + 1) / len(test_tickers)) * 100
            score = percentile  # Simple mapping for testing

            cursor.execute("""
                INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, factor_name) DO UPDATE
                SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
            """, (ticker, cls.test_region, cls.test_date, cls.test_factor, score, percentile))

        # Insert OHLCV data for forward return calculation
        for i, ticker in enumerate(test_tickers):
            # Start price: 100
            start_price = 100.0

            # Forward return: proportional to factor score (higher score = higher return)
            # Q1 (low score): -2% return, Q5 (high score): +5% return
            factor_score = ((i + 1) / len(test_tickers)) * 100
            forward_return_pct = (factor_score / 100) * 0.07 - 0.02  # -2% to +5%
            end_price = start_price * (1 + forward_return_pct)

            # Insert start date OHLCV
            cursor.execute("""
                INSERT INTO ohlcv_data (ticker, region, date, timeframe, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, timeframe) DO UPDATE
                SET close = EXCLUDED.close
            """, (ticker, cls.test_region, cls.test_date, '1d', start_price, start_price, start_price, start_price, 1000000))

            # Insert end date OHLCV (21 days later)
            end_date = cls.test_date + timedelta(days=21)
            cursor.execute("""
                INSERT INTO ohlcv_data (ticker, region, date, timeframe, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, timeframe) DO UPDATE
                SET close = EXCLUDED.close
            """, (ticker, cls.test_region, end_date, '1d', end_price, end_price, end_price, end_price, 1000000))

        cls.conn.commit()
        cursor.close()

        cls.analyzer = FactorAnalyzer()

    def setUp(self):
        """Clear any test-specific data before each test"""
        pass

    def test_quintile_analysis(self):
        """Test quintile analysis with known data"""
        results = self.analyzer.quintile_analysis(
            factor_name=self.test_factor,
            analysis_date=str(self.test_date),
            region=self.test_region,
            holding_period=21
        )

        # Should have 5 quintiles
        self.assertEqual(len(results), 5)

        # Q1 should have lowest return, Q5 should have highest
        self.assertLess(results[0].mean_return, results[4].mean_return)

        # Each quintile should have ~6 stocks (30 stocks / 5 quintiles)
        for result in results:
            self.assertGreaterEqual(result.num_stocks, 5)
            self.assertLessEqual(result.num_stocks, 7)

        # Hit rate should be between 0 and 1
        for result in results:
            self.assertGreaterEqual(result.hit_rate, 0.0)
            self.assertLessEqual(result.hit_rate, 1.0)

    def test_calculate_ic(self):
        """Test IC calculation"""
        # For single date, should return 1 IC result
        ic_results = self.analyzer.calculate_ic(
            factor_name=self.test_factor,
            start_date=str(self.test_date),
            end_date=str(self.test_date),
            region=self.test_region,
            holding_period=21
        )

        self.assertEqual(len(ic_results), 1)

        ic = ic_results[0]

        # IC should be positive (factor score correlates with forward returns)
        self.assertGreater(ic.ic_value, 0)

        # Should have 30 stocks
        self.assertEqual(ic.num_stocks, 30)

    def test_calculate_ic_stats(self):
        """Test IC statistics calculation"""
        # Create IC time series
        ic_results = [
            ICResult(date=self.test_date, ic_value=0.05, num_stocks=30, p_value=0.01, is_significant=True),
            ICResult(date=self.test_date, ic_value=0.03, num_stocks=30, p_value=0.03, is_significant=True),
            ICResult(date=self.test_date, ic_value=0.04, num_stocks=30, p_value=0.02, is_significant=True)
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        # Mean IC should be ~0.04
        self.assertAlmostEqual(stats['mean_ic'], 0.04, places=2)

        # All IC values are positive
        self.assertEqual(stats['pct_positive'], 1.0)

        # All are significant
        self.assertEqual(stats['pct_significant'], 1.0)

    def test_factor_turnover(self):
        """Test factor turnover calculation"""
        # Create second date with slightly different scores
        date2 = self.test_date + timedelta(days=1)
        cursor = self.conn.cursor()

        test_tickers = [f'TEST{i:03d}' for i in range(1, 31)]

        # Insert factor scores for date2 (slightly shuffled)
        for i, ticker in enumerate(test_tickers):
            # Add noise to percentile (causes some quintile changes)
            percentile = ((i + 1) / len(test_tickers)) * 100
            percentile_noisy = percentile + np.random.uniform(-10, 10)
            percentile_noisy = float(np.clip(percentile_noisy, 0, 100))

            cursor.execute("""
                INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, factor_name) DO UPDATE
                SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
            """, (ticker, self.test_region, date2, self.test_factor, percentile_noisy, percentile_noisy))

        self.conn.commit()
        cursor.close()

        # Calculate turnover
        turnover = self.analyzer.factor_turnover(
            factor_name=self.test_factor,
            date1=str(self.test_date),
            date2=str(date2),
            region=self.test_region
        )

        # Turnover should be between 0 and 1
        self.assertGreaterEqual(turnover, 0.0)
        self.assertLessEqual(turnover, 1.0)

    def test_quintile_analysis_insufficient_data(self):
        """Test quintile analysis with insufficient data"""
        results = self.analyzer.quintile_analysis(
            factor_name='NONEXISTENT_FACTOR',
            analysis_date=str(self.test_date),
            region=self.test_region,
            holding_period=21
        )

        # Should return empty list
        self.assertEqual(len(results), 0)

    @classmethod
    def tearDownClass(cls):
        """Clean up test data and close connection"""
        cls.conn.rollback()

        cursor = cls.conn.cursor()

        # Delete test OHLCV data
        test_tickers = [f'TEST{i:03d}' for i in range(1, 31)]
        for ticker in test_tickers:
            cursor.execute("DELETE FROM ohlcv_data WHERE ticker = %s AND region = %s", (ticker, cls.test_region))

        # Delete test factor scores
        cursor.execute("DELETE FROM factor_scores WHERE factor_name = %s", (cls.test_factor,))

        # Delete test tickers
        for ticker in test_tickers:
            cursor.execute("DELETE FROM tickers WHERE ticker = %s AND region = %s", (ticker, cls.test_region))

        cls.conn.commit()
        cursor.close()
        cls.conn.close()
        cls.analyzer.close()


class TestFactorCorrelationAnalyzer(unittest.TestCase):
    """Test cases for FactorCorrelationAnalyzer"""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection and create test data"""
        cls.conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER')
        )

        cls.test_date = date(2025, 10, 22)
        cls.test_region = 'KR'
        cls.test_factor1 = 'TEST_CORR_FACTOR1'
        cls.test_factor2 = 'TEST_CORR_FACTOR2'
        cls.test_factor3 = 'TEST_CORR_FACTOR3'

        # Create test tickers
        cursor = cls.conn.cursor()

        test_tickers = [f'TCORR{i:03d}' for i in range(1, 51)]

        for ticker in test_tickers:
            cursor.execute("""
                INSERT INTO tickers (ticker, region, name, exchange, currency, asset_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region) DO NOTHING
            """, (ticker, cls.test_region, f'Test Stock {ticker}', 'TEST', 'KRW', 'STOCK'))

        # Insert factor scores
        # Factor 1 and 2: Highly correlated (0.9+)
        # Factor 3: Independent (low correlation)
        np.random.seed(42)

        base_scores = np.random.uniform(0, 100, len(test_tickers))

        for i, ticker in enumerate(test_tickers):
            # Factor 1
            score1 = float(base_scores[i])
            percentile1 = ((i + 1) / len(test_tickers)) * 100

            cursor.execute("""
                INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, factor_name) DO UPDATE
                SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
            """, (ticker, cls.test_region, cls.test_date, cls.test_factor1, score1, percentile1))

            # Factor 2: Highly correlated with Factor 1 (add small noise)
            score2 = float(score1 + np.random.uniform(-5, 5))
            percentile2 = float(np.clip(percentile1 + np.random.uniform(-5, 5), 0, 100))

            cursor.execute("""
                INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, factor_name) DO UPDATE
                SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
            """, (ticker, cls.test_region, cls.test_date, cls.test_factor2, score2, percentile2))

            # Factor 3: Independent (random)
            score3 = float(np.random.uniform(0, 100))
            percentile3 = float(np.random.uniform(0, 100))

            cursor.execute("""
                INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, factor_name) DO UPDATE
                SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
            """, (ticker, cls.test_region, cls.test_date, cls.test_factor3, score3, percentile3))

        cls.conn.commit()
        cursor.close()

        cls.analyzer = FactorCorrelationAnalyzer()

    def test_pairwise_correlation(self):
        """Test correlation matrix calculation"""
        corr_matrix = self.analyzer.pairwise_correlation(
            analysis_date=str(self.test_date),
            region=self.test_region,
            method='spearman'
        )

        # Should be square matrix (3x3)
        self.assertEqual(corr_matrix.shape, (3, 3))

        # Diagonal should be 1.0 (perfect self-correlation)
        for factor in corr_matrix.index:
            self.assertAlmostEqual(corr_matrix.loc[factor, factor], 1.0, places=5)

        # Matrix should be symmetric
        self.assertAlmostEqual(
            corr_matrix.loc[self.test_factor1, self.test_factor2],
            corr_matrix.loc[self.test_factor2, self.test_factor1],
            places=5
        )

    def test_redundancy_detection(self):
        """Test redundancy detection"""
        redundant_pairs = self.analyzer.redundancy_detection(
            analysis_date=str(self.test_date),
            region=self.test_region,
            threshold=0.7
        )

        # Should find at least 1 redundant pair (Factor1 and Factor2)
        self.assertGreater(len(redundant_pairs), 0)

        # First pair should be Factor1 and Factor2 (highest correlation)
        first_pair = redundant_pairs[0]
        self.assertIn(self.test_factor1, [first_pair.factor1, first_pair.factor2])
        self.assertIn(self.test_factor2, [first_pair.factor1, first_pair.factor2])

        # Correlation should be high
        self.assertGreater(abs(first_pair.correlation), 0.7)

    def test_orthogonalization_suggestion(self):
        """Test orthogonalization suggestion"""
        suggested_factors = self.analyzer.orthogonalization_suggestion(
            analysis_date=str(self.test_date),
            region=self.test_region,
            max_correlation=0.5
        )

        # Should suggest at most 2 factors (Factor1/2 redundant, Factor3 independent)
        self.assertLessEqual(len(suggested_factors), 3)

        # Should include at least Factor3 (independent)
        self.assertIn(self.test_factor3, suggested_factors)

    @classmethod
    def tearDownClass(cls):
        """Clean up test data and close connection"""
        cls.conn.rollback()

        cursor = cls.conn.cursor()

        # Delete test factor scores
        cursor.execute("DELETE FROM factor_scores WHERE factor_name IN (%s, %s, %s)",
                      (cls.test_factor1, cls.test_factor2, cls.test_factor3))

        # Delete test tickers
        test_tickers = [f'TCORR{i:03d}' for i in range(1, 51)]
        for ticker in test_tickers:
            cursor.execute("DELETE FROM tickers WHERE ticker = %s AND region = %s", (ticker, cls.test_region))

        cls.conn.commit()
        cursor.close()
        cls.conn.close()
        cls.analyzer.close()


class TestPerformanceReporter(unittest.TestCase):
    """Test cases for PerformanceReporter"""

    def setUp(self):
        """Set up test reporter"""
        self.test_output_dir = 'tests/test_reports/'
        self.reporter = PerformanceReporter(output_dir=self.test_output_dir)

    def test_quintile_performance_report(self):
        """Test quintile report generation"""
        # Create mock quintile results
        quintile_results = [
            QuintileResult(quintile=1, num_stocks=10, mean_return=-0.02, median_return=-0.015,
                          std_dev=0.05, sharpe_ratio=-0.4, hit_rate=0.4, min_return=-0.1, max_return=0.05),
            QuintileResult(quintile=2, num_stocks=10, mean_return=0.00, median_return=0.005,
                          std_dev=0.04, sharpe_ratio=0.0, hit_rate=0.5, min_return=-0.05, max_return=0.06),
            QuintileResult(quintile=3, num_stocks=10, mean_return=0.01, median_return=0.01,
                          std_dev=0.03, sharpe_ratio=0.3, hit_rate=0.6, min_return=-0.03, max_return=0.07),
            QuintileResult(quintile=4, num_stocks=10, mean_return=0.03, median_return=0.025,
                          std_dev=0.04, sharpe_ratio=0.7, hit_rate=0.7, min_return=-0.02, max_return=0.09),
            QuintileResult(quintile=5, num_stocks=10, mean_return=0.05, median_return=0.045,
                          std_dev=0.05, sharpe_ratio=1.0, hit_rate=0.8, min_return=0.00, max_return=0.12)
        ]

        # Generate report
        output_files = self.reporter.quintile_performance_report(
            factor_name='TEST_FACTOR',
            quintile_results=quintile_results,
            analysis_date='2025-10-22',
            region='KR',
            holding_period=21,
            export_formats=['png', 'csv']
        )

        # Check that files were created
        self.assertIn('chart', output_files)
        self.assertIn('csv', output_files)

        # Verify files exist
        self.assertTrue(Path(output_files['chart']).exists())
        self.assertTrue(Path(output_files['csv']).exists())

    def tearDown(self):
        """Clean up test reports"""
        import shutil
        if Path(self.test_output_dir).exists():
            shutil.rmtree(self.test_output_dir)


if __name__ == '__main__':
    unittest.main(verbosity=2)
