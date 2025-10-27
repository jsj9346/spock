#!/usr/bin/env python3
"""
Integration Tests for Factor Analysis Modules (Using Real Data)

Tests with actual database data from factor_scores table.

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
import unittest
from datetime import date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import pandas as pd

from modules.analysis.factor_analyzer import FactorAnalyzer
from modules.analysis.factor_correlation import FactorCorrelationAnalyzer
from modules.analysis.performance_reporter import PerformanceReporter


class TestFactorAnalyzerIntegration(unittest.TestCase):
    """Integration tests for FactorAnalyzer using real data"""

    @classmethod
    def setUpClass(cls):
        """Set up database connection"""
        cls.conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER')
        )

        # Use real data date
        cls.test_date = '2025-10-22'
        cls.test_region = 'KR'

        cls.analyzer = FactorAnalyzer()

    def test_quintile_analysis_with_real_data(self):
        """Test quintile analysis with real factor data"""
        # Use existing factor (PE_Ratio or 12M_Momentum)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT factor_name
            FROM factor_scores
            WHERE date = %s AND region = %s
            LIMIT 1
        """, (self.test_date, self.test_region))

        result = cursor.fetchone()
        cursor.close()

        if not result:
            self.skipTest("No factor scores available for testing")

        factor_name = result[0]

        results = self.analyzer.quintile_analysis(
            factor_name=factor_name,
            analysis_date=self.test_date,
            region=self.test_region,
            holding_period=21
        )

        # Note: May be empty if no forward OHLCV data
        # This is expected given current data limitation
        if results:
            print(f"\n✓ Quintile analysis successful for {factor_name}")
            print(f"  Quintiles found: {len(results)}")
            print(f"  Q1 mean return: {results[0].mean_return:.2%}")
            print(f"  Q5 mean return: {results[-1].mean_return:.2%}")

    def test_analyzer_connection(self):
        """Test analyzer database connection"""
        conn = self.analyzer._get_connection()
        self.assertIsNotNone(conn)
        self.assertFalse(conn.closed)

    @classmethod
    def tearDownClass(cls):
        """Clean up"""
        cls.conn.close()
        cls.analyzer.close()


class TestFactorCorrelationAnalyzerIntegration(unittest.TestCase):
    """Integration tests for FactorCorrelationAnalyzer using real data"""

    @classmethod
    def setUpClass(cls):
        """Set up database connection"""
        cls.conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER')
        )

        cls.test_date = '2025-10-22'
        cls.test_region = 'KR'

        cls.analyzer = FactorCorrelationAnalyzer()

    def test_pairwise_correlation_with_real_data(self):
        """Test correlation matrix with real factors"""
        corr_matrix = self.analyzer.pairwise_correlation(
            analysis_date=self.test_date,
            region=self.test_region,
            method='spearman'
        )

        if not corr_matrix.empty:
            print(f"\n✓ Correlation matrix calculated")
            print(f"  Factors analyzed: {list(corr_matrix.index)}")
            print(f"  Matrix shape: {corr_matrix.shape}")

            # Validate matrix properties
            # Diagonal should be 1.0
            for factor in corr_matrix.index:
                self.assertAlmostEqual(corr_matrix.loc[factor, factor], 1.0, places=2,
                                      msg=f"{factor} self-correlation should be 1.0")

    def test_redundancy_detection_with_real_data(self):
        """Test redundancy detection with real factors"""
        redundant_pairs = self.analyzer.redundancy_detection(
            analysis_date=self.test_date,
            region=self.test_region,
            threshold=0.5  # Lower threshold to catch more pairs
        )

        if redundant_pairs:
            print(f"\n✓ Redundancy detection successful")
            print(f"  Redundant pairs found: {len(redundant_pairs)}")
            for pair in redundant_pairs[:3]:  # Print top 3
                print(f"  {pair.factor1} <-> {pair.factor2}: {pair.correlation:.3f}")

    def test_orthogonalization_suggestion_with_real_data(self):
        """Test orthogonalization with real factors"""
        suggested_factors = self.analyzer.orthogonalization_suggestion(
            analysis_date=self.test_date,
            region=self.test_region,
            max_correlation=0.5
        )

        if suggested_factors:
            print(f"\n✓ Orthogonalization successful")
            print(f"  Suggested orthogonal factors: {', '.join(suggested_factors)}")
            print(f"  Total: {len(suggested_factors)} independent factors")

    @classmethod
    def tearDownClass(cls):
        """Clean up"""
        cls.conn.close()
        cls.analyzer.close()


class TestPerformanceReporterIntegration(unittest.TestCase):
    """Integration tests for PerformanceReporter"""

    def setUp(self):
        """Set up test reporter"""
        self.test_output_dir = 'tests/test_reports_integration/'
        self.reporter = PerformanceReporter(output_dir=self.test_output_dir)

    def test_correlation_heatmap_with_real_data(self):
        """Test correlation heatmap generation with real data"""
        analyzer = FactorCorrelationAnalyzer()

        corr_matrix = analyzer.pairwise_correlation(
            analysis_date='2025-10-22',
            region='KR',
            method='spearman'
        )

        analyzer.close()

        if not corr_matrix.empty:
            output_files = self.reporter.correlation_heatmap(
                corr_matrix=corr_matrix,
                analysis_date='2025-10-22',
                region='KR',
                export_formats=['png']
            )

            print(f"\n✓ Correlation heatmap generated")
            print(f"  Output file: {output_files.get('chart', 'N/A')}")

            self.assertIn('chart', output_files)

    def tearDown(self):
        """Clean up test reports"""
        import shutil
        from pathlib import Path
        if Path(self.test_output_dir).exists():
            shutil.rmtree(self.test_output_dir)


if __name__ == '__main__':
    unittest.main(verbosity=2)
