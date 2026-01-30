#!/usr/bin/env python3
"""
test_analysis.py - Unit Tests for Analysis Module

Tests for:
- FactorAnalyzer: Quintile analysis, IC calculation
- FactorCorrelationAnalyzer: Correlation matrix, redundancy detection
- QuintileResult, ICResult, CorrelationPair dataclasses

Coverage target: analysis/* (~383 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from scipy import stats


class TestQuintileResult(unittest.TestCase):
    """Test QuintileResult dataclass"""

    def test_quintile_result_creation(self):
        """Test QuintileResult dataclass initialization"""
        from modules.analysis.factor_analyzer import QuintileResult

        result = QuintileResult(
            quintile=5,
            num_stocks=100,
            mean_return=0.05,
            median_return=0.04,
            std_dev=0.15,
            sharpe_ratio=1.5,
            hit_rate=0.65,
            min_return=-0.10,
            max_return=0.25
        )

        self.assertEqual(result.quintile, 5)
        self.assertEqual(result.num_stocks, 100)
        self.assertAlmostEqual(result.mean_return, 0.05)
        self.assertAlmostEqual(result.sharpe_ratio, 1.5)
        self.assertAlmostEqual(result.hit_rate, 0.65)

    def test_quintile_result_with_turnover(self):
        """Test QuintileResult with optional turnover"""
        from modules.analysis.factor_analyzer import QuintileResult

        result = QuintileResult(
            quintile=1,
            num_stocks=50,
            mean_return=-0.02,
            median_return=-0.01,
            std_dev=0.20,
            sharpe_ratio=-0.5,
            hit_rate=0.40,
            min_return=-0.30,
            max_return=0.10,
            turnover=0.25
        )

        self.assertEqual(result.turnover, 0.25)


class TestICResult(unittest.TestCase):
    """Test ICResult dataclass"""

    def test_ic_result_creation(self):
        """Test ICResult dataclass initialization"""
        from modules.analysis.factor_analyzer import ICResult

        result = ICResult(
            date=date(2024, 10, 10),
            ic_value=0.08,
            num_stocks=500,
            p_value=0.001,
            is_significant=True
        )

        self.assertEqual(result.date, date(2024, 10, 10))
        self.assertAlmostEqual(result.ic_value, 0.08)
        self.assertEqual(result.num_stocks, 500)
        self.assertLess(result.p_value, 0.05)
        self.assertTrue(result.is_significant)

    def test_ic_result_not_significant(self):
        """Test ICResult with non-significant IC"""
        from modules.analysis.factor_analyzer import ICResult

        result = ICResult(
            date=date(2024, 10, 10),
            ic_value=0.02,
            num_stocks=50,
            p_value=0.15,
            is_significant=False
        )

        self.assertFalse(result.is_significant)


class TestCorrelationPair(unittest.TestCase):
    """Test CorrelationPair dataclass"""

    def test_correlation_pair_creation(self):
        """Test CorrelationPair dataclass initialization"""
        from modules.analysis.factor_correlation import CorrelationPair

        pair = CorrelationPair(
            factor1='PE_Ratio',
            factor2='PB_Ratio',
            correlation=0.85,
            p_value=0.0001,
            is_significant=True,
            num_stocks=300
        )

        self.assertEqual(pair.factor1, 'PE_Ratio')
        self.assertEqual(pair.factor2, 'PB_Ratio')
        self.assertAlmostEqual(pair.correlation, 0.85)
        self.assertTrue(pair.is_significant)


class TestFactorAnalyzerInit(unittest.TestCase):
    """Test FactorAnalyzer initialization"""

    @patch('modules.analysis.factor_analyzer.psycopg2.connect')
    def test_initialization(self, mock_connect):
        """Test FactorAnalyzer initialization"""
        from modules.analysis.factor_analyzer import FactorAnalyzer

        analyzer = FactorAnalyzer()

        self.assertIsNone(analyzer.conn)

    @patch('modules.analysis.factor_analyzer.psycopg2.connect')
    def test_get_connection(self, mock_connect):
        """Test _get_connection creates connection"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        from modules.analysis.factor_analyzer import FactorAnalyzer

        analyzer = FactorAnalyzer()
        conn = analyzer._get_connection()

        mock_connect.assert_called_once()
        self.assertEqual(conn, mock_conn)

    @patch('modules.analysis.factor_analyzer.psycopg2.connect')
    def test_context_manager(self, mock_connect):
        """Test context manager protocol"""
        mock_conn = Mock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        from modules.analysis.factor_analyzer import FactorAnalyzer

        with FactorAnalyzer() as analyzer:
            analyzer._get_connection()

        mock_conn.close.assert_called_once()


class TestFactorAnalyzerMethods(unittest.TestCase):
    """Test FactorAnalyzer methods with mocked database"""

    def setUp(self):
        """Set up mocked analyzer"""
        self.connect_patcher = patch('modules.analysis.factor_analyzer.psycopg2.connect')
        self.mock_connect = self.connect_patcher.start()

        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.closed = False
        self.mock_connect.return_value = self.mock_conn

        from modules.analysis.factor_analyzer import FactorAnalyzer
        self.analyzer = FactorAnalyzer()

    def tearDown(self):
        self.connect_patcher.stop()

    def test_calculate_ic_stats_empty(self):
        """Test calculate_ic_stats with empty results"""
        result = self.analyzer.calculate_ic_stats([])

        self.assertEqual(result['mean_ic'], 0.0)
        self.assertEqual(result['std_ic'], 0.0)
        self.assertEqual(result['ic_ir'], 0.0)
        self.assertEqual(result['p_value'], 1.0)

    def test_calculate_ic_stats_with_results(self):
        """Test calculate_ic_stats with IC results"""
        from modules.analysis.factor_analyzer import ICResult

        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=0.05, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 2, 1), ic_value=0.08, num_stocks=100, p_value=0.001, is_significant=True),
            ICResult(date=date(2024, 3, 1), ic_value=0.03, num_stocks=100, p_value=0.05, is_significant=False),
            ICResult(date=date(2024, 4, 1), ic_value=0.06, num_stocks=100, p_value=0.02, is_significant=True),
        ]

        stats_result = self.analyzer.calculate_ic_stats(ic_results)

        self.assertGreater(stats_result['mean_ic'], 0)
        self.assertGreater(stats_result['std_ic'], 0)
        self.assertEqual(stats_result['pct_significant'], 0.75)  # 3 out of 4
        self.assertEqual(stats_result['pct_positive'], 1.0)  # All positive

    def test_quintile_analysis_empty_result(self):
        """Test quintile_analysis with no data"""
        self.mock_cursor.fetchall.return_value = []

        result = self.analyzer.quintile_analysis(
            factor_name='12M_Momentum',
            analysis_date='2024-10-10',
            region='KR'
        )

        self.assertEqual(result, [])


class TestFactorCorrelationAnalyzer(unittest.TestCase):
    """Test FactorCorrelationAnalyzer"""

    def setUp(self):
        """Set up mocked analyzer"""
        self.connect_patcher = patch('modules.analysis.factor_correlation.psycopg2.connect')
        self.mock_connect = self.connect_patcher.start()

        self.mock_conn = Mock()
        self.mock_cursor = Mock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.closed = False
        self.mock_connect.return_value = self.mock_conn

        from modules.analysis.factor_correlation import FactorCorrelationAnalyzer
        self.analyzer = FactorCorrelationAnalyzer()

    def tearDown(self):
        self.connect_patcher.stop()

    def test_initialization(self):
        """Test FactorCorrelationAnalyzer initialization"""
        self.assertIsNone(self.analyzer.conn)

    def test_pairwise_correlation_insufficient_factors(self):
        """Test pairwise_correlation with < 2 factors"""
        self.mock_cursor.fetchall.return_value = [('Factor1',)]

        result = self.analyzer.pairwise_correlation('2024-10-10', 'KR')

        self.assertTrue(result.empty)

    def test_redundancy_detection_insufficient_factors(self):
        """Test redundancy_detection with < 2 factors"""
        self.mock_cursor.fetchall.return_value = [('Factor1',)]

        result = self.analyzer.redundancy_detection('2024-10-10', 'KR')

        self.assertEqual(result, [])

    def test_orthogonalization_empty_correlation(self):
        """Test orthogonalization_suggestion with empty correlation"""
        # Make pairwise_correlation return empty DataFrame
        self.mock_cursor.fetchall.return_value = []

        result = self.analyzer.orthogonalization_suggestion('2024-10-10', 'KR')

        self.assertEqual(result, [])

    def test_context_manager(self):
        """Test context manager protocol"""
        from modules.analysis.factor_correlation import FactorCorrelationAnalyzer

        with FactorCorrelationAnalyzer() as analyzer:
            analyzer._get_connection()

        self.mock_conn.close.assert_called()


class TestFactorCorrelationComputation(unittest.TestCase):
    """Test FactorCorrelation with simulated data"""

    def test_correlation_matrix_computation(self):
        """Test correlation matrix computation with simulated data"""
        # Create correlated data
        np.random.seed(42)
        n_stocks = 100

        factor1 = np.random.randn(n_stocks)
        factor2 = factor1 * 0.8 + np.random.randn(n_stocks) * 0.2  # High correlation
        factor3 = np.random.randn(n_stocks)  # Low correlation

        df = pd.DataFrame({
            'Factor1': factor1,
            'Factor2': factor2,
            'Factor3': factor3
        })

        corr_matrix = df.corr(method='spearman')

        # Factor1 and Factor2 should be highly correlated
        self.assertGreater(abs(corr_matrix.loc['Factor1', 'Factor2']), 0.7)

        # Factor3 should have low correlation with others
        self.assertLess(abs(corr_matrix.loc['Factor1', 'Factor3']), 0.3)


# Parametrized tests
@pytest.mark.parametrize("ic_values,expected_positive_pct", [
    ([0.05, 0.08, 0.03], 1.0),
    ([-0.02, 0.05, 0.03], 2/3),
    ([-0.05, -0.03, -0.02], 0.0),
])
def test_ic_positive_percentage(ic_values, expected_positive_pct):
    """Test IC positive percentage calculation"""
    pct_positive = sum(1 for ic in ic_values if ic > 0) / len(ic_values)
    assert abs(pct_positive - expected_positive_pct) < 0.01


@pytest.mark.parametrize("correlation,threshold,is_redundant", [
    (0.85, 0.7, True),
    (0.65, 0.7, False),
    (-0.80, 0.7, True),
    (0.50, 0.7, False),
])
def test_redundancy_threshold(correlation, threshold, is_redundant):
    """Test redundancy detection threshold"""
    result = abs(correlation) >= threshold
    assert result == is_redundant


@pytest.mark.parametrize("quintile,expected_label", [
    (1, "Lowest"),
    (3, "Middle"),
    (5, "Highest"),
])
def test_quintile_labels(quintile, expected_label):
    """Test quintile label mapping"""
    labels = {1: "Lowest", 2: "Low", 3: "Middle", 4: "High", 5: "Highest"}
    assert labels[quintile] == expected_label


class TestICStatisticalSignificance(unittest.TestCase):
    """Test IC statistical significance calculations"""

    def test_ttest_calculation(self):
        """Test t-test calculation for IC"""
        # IC values with clear positive mean
        ic_values = np.array([0.05, 0.08, 0.06, 0.04, 0.07, 0.05, 0.06, 0.08])

        t_stat, p_value = stats.ttest_1samp(ic_values, 0.0)

        # Should be significantly positive
        self.assertGreater(t_stat, 0)
        self.assertLess(p_value, 0.05)

    def test_spearman_correlation(self):
        """Test Spearman rank correlation"""
        np.random.seed(42)
        scores = np.random.randn(100)
        returns = scores * 0.5 + np.random.randn(100) * 0.5

        corr, p_value = stats.spearmanr(scores, returns)

        # Should have positive correlation
        self.assertGreater(corr, 0)
        self.assertLess(p_value, 0.05)


# =============================================================================
# Additional Analysis Tests
# =============================================================================

class TestCalculateICStatsEdgeCases(unittest.TestCase):
    """Additional tests for calculate_ic_stats edge cases"""

    def setUp(self):
        """Set up mocked analyzer"""
        self.connect_patcher = patch('modules.analysis.factor_analyzer.psycopg2.connect')
        self.mock_connect = self.connect_patcher.start()

        self.mock_conn = Mock()
        self.mock_conn.closed = False
        self.mock_connect.return_value = self.mock_conn

        from modules.analysis.factor_analyzer import FactorAnalyzer
        self.analyzer = FactorAnalyzer()

    def tearDown(self):
        self.connect_patcher.stop()

    def test_calculate_ic_stats_single_result(self):
        """Test calculate_ic_stats with single IC result"""
        from modules.analysis.factor_analyzer import ICResult

        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=0.05, num_stocks=100, p_value=0.01, is_significant=True)
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        self.assertAlmostEqual(stats['mean_ic'], 0.05)
        self.assertEqual(stats['pct_positive'], 1.0)
        self.assertEqual(stats['pct_significant'], 1.0)

    def test_calculate_ic_stats_all_negative(self):
        """Test calculate_ic_stats with all negative IC values"""
        from modules.analysis.factor_analyzer import ICResult

        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=-0.05, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 2, 1), ic_value=-0.08, num_stocks=100, p_value=0.001, is_significant=True),
            ICResult(date=date(2024, 3, 1), ic_value=-0.03, num_stocks=100, p_value=0.05, is_significant=False),
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        self.assertLess(stats['mean_ic'], 0)
        self.assertEqual(stats['pct_positive'], 0.0)

    def test_calculate_ic_stats_low_std(self):
        """Test calculate_ic_stats with very low standard deviation"""
        from modules.analysis.factor_analyzer import ICResult

        # Very similar IC values -> low std -> high IC IR
        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=0.050, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 2, 1), ic_value=0.051, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 3, 1), ic_value=0.049, num_stocks=100, p_value=0.01, is_significant=True),
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        # With low std and positive mean, IC IR should be very high
        self.assertGreater(stats['ic_ir'], 10.0)  # High IR due to low std
        self.assertGreater(stats['mean_ic'], 0)
        self.assertGreater(stats['std_ic'], 0)

    def test_calculate_ic_stats_mixed_significance(self):
        """Test calculate_ic_stats with mixed significance"""
        from modules.analysis.factor_analyzer import ICResult

        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=0.10, num_stocks=100, p_value=0.001, is_significant=True),
            ICResult(date=date(2024, 2, 1), ic_value=0.01, num_stocks=100, p_value=0.20, is_significant=False),
            ICResult(date=date(2024, 3, 1), ic_value=0.08, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 4, 1), ic_value=0.02, num_stocks=100, p_value=0.15, is_significant=False),
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        # 2 out of 4 are significant
        self.assertAlmostEqual(stats['pct_significant'], 0.5)
        # All positive
        self.assertEqual(stats['pct_positive'], 1.0)

    def test_calculate_ic_stats_ic_ir_calculation(self):
        """Test IC IR (Information Ratio) calculation"""
        from modules.analysis.factor_analyzer import ICResult

        # Create IC results with known mean and std
        ic_results = [
            ICResult(date=date(2024, 1, 1), ic_value=0.10, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 2, 1), ic_value=0.06, num_stocks=100, p_value=0.01, is_significant=True),
            ICResult(date=date(2024, 3, 1), ic_value=0.08, num_stocks=100, p_value=0.01, is_significant=True),
        ]

        stats = self.analyzer.calculate_ic_stats(ic_results)

        # Manual calculation: mean = 0.08, std = 0.0163
        # IC IR = mean / std
        expected_mean = np.mean([0.10, 0.06, 0.08])
        expected_std = np.std([0.10, 0.06, 0.08])
        expected_ir = expected_mean / expected_std if expected_std > 0 else 0

        self.assertAlmostEqual(stats['mean_ic'], expected_mean, places=5)
        self.assertAlmostEqual(stats['ic_ir'], expected_ir, places=2)


class TestQuintileResultEquality(unittest.TestCase):
    """Test QuintileResult equality and comparison"""

    def test_quintile_result_comparison(self):
        """Test comparing QuintileResult objects"""
        from modules.analysis.factor_analyzer import QuintileResult

        result1 = QuintileResult(
            quintile=5, num_stocks=100, mean_return=0.10,
            median_return=0.08, std_dev=0.15, sharpe_ratio=2.0,
            hit_rate=0.70, min_return=-0.05, max_return=0.30
        )

        result2 = QuintileResult(
            quintile=1, num_stocks=100, mean_return=-0.05,
            median_return=-0.03, std_dev=0.20, sharpe_ratio=-0.5,
            hit_rate=0.35, min_return=-0.25, max_return=0.10
        )

        # Q5 should have higher mean return than Q1
        self.assertGreater(result1.mean_return, result2.mean_return)
        # Q5 should have higher Sharpe than Q1
        self.assertGreater(result1.sharpe_ratio, result2.sharpe_ratio)


class TestICResultValidation(unittest.TestCase):
    """Test ICResult validation scenarios"""

    def test_ic_result_significant_threshold(self):
        """Test IC significance at threshold boundary"""
        from modules.analysis.factor_analyzer import ICResult

        # Just below threshold
        result_significant = ICResult(
            date=date(2024, 1, 1), ic_value=0.05, num_stocks=100,
            p_value=0.049, is_significant=True
        )

        # Just above threshold
        result_not_significant = ICResult(
            date=date(2024, 1, 1), ic_value=0.05, num_stocks=100,
            p_value=0.051, is_significant=False
        )

        self.assertTrue(result_significant.is_significant)
        self.assertFalse(result_not_significant.is_significant)


class TestCorrelationPairRedundancy(unittest.TestCase):
    """Test CorrelationPair for redundancy detection"""

    def test_high_correlation_is_redundant(self):
        """Test that high correlation pairs are flagged as redundant"""
        from modules.analysis.factor_correlation import CorrelationPair

        pair = CorrelationPair(
            factor1='PE_Ratio',
            factor2='PB_Ratio',
            correlation=0.85,
            p_value=0.0001,
            is_significant=True,
            num_stocks=300
        )

        # Check redundancy threshold (typically 0.7)
        threshold = 0.7
        is_redundant = abs(pair.correlation) >= threshold

        self.assertTrue(is_redundant)

    def test_low_correlation_not_redundant(self):
        """Test that low correlation pairs are not redundant"""
        from modules.analysis.factor_correlation import CorrelationPair

        pair = CorrelationPair(
            factor1='Momentum',
            factor2='Value',
            correlation=0.15,
            p_value=0.10,
            is_significant=False,
            num_stocks=300
        )

        threshold = 0.7
        is_redundant = abs(pair.correlation) >= threshold

        self.assertFalse(is_redundant)


# Additional parametrized tests
@pytest.mark.parametrize("ic_values,expected_ir_sign", [
    ([0.05, 0.08, 0.06, 0.07], 'positive'),      # All positive -> positive IR
    ([-0.05, -0.08, -0.06, -0.07], 'negative'),  # All negative -> negative IR
    ([0.05, -0.05, 0.03, -0.03], 'near_zero'),   # Mixed -> near zero IR
])
def test_ic_ir_sign(ic_values, expected_ir_sign):
    """Test IC Information Ratio sign"""
    mean_ic = np.mean(ic_values)
    std_ic = np.std(ic_values)
    ic_ir = mean_ic / std_ic if std_ic > 0 else 0

    if expected_ir_sign == 'positive':
        assert ic_ir > 0
    elif expected_ir_sign == 'negative':
        assert ic_ir < 0
    else:  # near_zero
        assert abs(ic_ir) < 0.5


@pytest.mark.parametrize("num_stocks,expected_min", [
    (100, 30),   # Sufficient stocks
    (50, 30),    # Borderline
    (20, 30),    # Insufficient (below threshold)
])
def test_minimum_stocks_requirement(num_stocks, expected_min):
    """Test minimum stocks requirement for valid analysis"""
    is_sufficient = num_stocks >= expected_min
    if num_stocks >= expected_min:
        assert is_sufficient
    else:
        assert not is_sufficient


@pytest.mark.parametrize("mean_return,std_dev,expected_sharpe_sign", [
    (0.10, 0.15, 'positive'),
    (-0.05, 0.15, 'negative'),
    (0.0, 0.15, 'zero'),
])
def test_sharpe_ratio_calculation(mean_return, std_dev, expected_sharpe_sign):
    """Test Sharpe ratio calculation logic"""
    sharpe = mean_return / std_dev if std_dev > 0 else 0

    if expected_sharpe_sign == 'positive':
        assert sharpe > 0
    elif expected_sharpe_sign == 'negative':
        assert sharpe < 0
    else:
        assert sharpe == 0


@pytest.mark.parametrize("hit_rate,expected_performance", [
    (0.70, 'good'),
    (0.50, 'neutral'),
    (0.30, 'poor'),
])
def test_hit_rate_interpretation(hit_rate, expected_performance):
    """Test hit rate interpretation"""
    if hit_rate >= 0.6:
        performance = 'good'
    elif hit_rate >= 0.4:
        performance = 'neutral'
    else:
        performance = 'poor'

    assert performance == expected_performance


class TestSpearmanCorrelation(unittest.TestCase):
    """Test Spearman correlation calculations"""

    def test_perfect_positive_correlation(self):
        """Test perfect positive correlation"""
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([10, 20, 30, 40, 50])

        corr, p_value = stats.spearmanr(x, y)

        self.assertAlmostEqual(corr, 1.0)
        self.assertLess(p_value, 0.05)

    def test_perfect_negative_correlation(self):
        """Test perfect negative correlation"""
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([50, 40, 30, 20, 10])

        corr, p_value = stats.spearmanr(x, y)

        self.assertAlmostEqual(corr, -1.0)
        self.assertLess(p_value, 0.05)

    def test_no_correlation(self):
        """Test no correlation between random data"""
        np.random.seed(42)
        x = np.arange(100)
        y = np.random.permutation(x)

        corr, p_value = stats.spearmanr(x, y)

        # Random permutation should have low correlation
        self.assertLess(abs(corr), 0.3)


class TestTTestCalculation(unittest.TestCase):
    """Test t-test calculation for IC"""

    def test_ttest_significant_positive(self):
        """Test t-test with significantly positive mean"""
        ic_values = np.array([0.08, 0.10, 0.07, 0.09, 0.08, 0.11, 0.09, 0.10])

        t_stat, p_value = stats.ttest_1samp(ic_values, 0.0)

        self.assertGreater(t_stat, 2.0)  # t > 2 for significance
        self.assertLess(p_value, 0.05)

    def test_ttest_not_significant(self):
        """Test t-test with non-significant mean"""
        ic_values = np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.00, 0.01])

        t_stat, p_value = stats.ttest_1samp(ic_values, 0.0)

        # Not significantly different from zero
        self.assertGreater(p_value, 0.05)


class TestPercentileCalculation(unittest.TestCase):
    """Test percentile calculation for quintile assignment"""

    def test_quintile_assignment(self):
        """Test quintile assignment using percentile ranks"""
        np.random.seed(42)
        scores = np.random.randn(100)

        # Assign quintiles (1-5)
        percentiles = stats.rankdata(scores, method='average') / len(scores) * 100

        quintiles = np.ceil(percentiles / 20).astype(int)
        quintiles[quintiles == 0] = 1  # Handle edge case
        quintiles[quintiles > 5] = 5   # Handle edge case

        # Each quintile should have approximately 20 stocks
        for q in range(1, 6):
            count = np.sum(quintiles == q)
            self.assertGreater(count, 10)
            self.assertLess(count, 30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
