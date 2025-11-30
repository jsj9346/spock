"""
Unit tests for ComparisonAnalyzer

Tests YoY growth, CAGR calculation, trend classification, and annual comparison analysis.
"""

import pytest
from decimal import Decimal
from modules.fundamentals.comparison_analyzer import ComparisonAnalyzer


class TestYoYGrowth:
    """Test calculate_yoy_growth method"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    def test_positive_growth(self):
        """Test positive YoY growth calculation"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('115'),
            Decimal('100')
        )
        assert result == 0.15  # 15% growth

    def test_negative_growth(self):
        """Test negative YoY growth (decline)"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('85'),
            Decimal('100')
        )
        assert result == -0.15  # 15% decline

    def test_zero_growth(self):
        """Test zero growth (no change)"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100'),
            Decimal('100')
        )
        assert result == 0.0

    def test_negative_to_positive(self):
        """Test growth from negative to positive value"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100'),
            Decimal('-50')
        )
        assert result == 3.0  # 300% growth

    def test_negative_to_negative(self):
        """Test growth between two negative values"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('-30'),
            Decimal('-50')
        )
        assert result == 0.4  # 40% improvement (less negative)

    def test_none_current_value(self):
        """Test with None current value"""
        result = self.analyzer.calculate_yoy_growth(
            None,
            Decimal('100')
        )
        assert result is None

    def test_none_previous_value(self):
        """Test with None previous value"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100'),
            None
        )
        assert result is None

    def test_zero_previous_value(self):
        """Test with zero previous value (division by zero)"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100'),
            Decimal('0')
        )
        assert result is None

    def test_rounding(self):
        """Test result is rounded to 4 decimal places"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100.12345'),
            Decimal('100')
        )
        assert result == 0.0012  # Rounded to 4 decimals


class TestCAGR:
    """Test calculate_cagr method"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    def test_positive_cagr(self):
        """Test positive CAGR calculation"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('121'),
            2
        )
        assert result == 0.1  # 10% annual growth

    def test_negative_cagr(self):
        """Test negative CAGR (decline)"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('81'),
            2
        )
        assert abs(result - (-0.1)) < 0.0001  # ~10% annual decline

    def test_zero_cagr(self):
        """Test zero CAGR (no change)"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('100'),
            5
        )
        assert result == 0.0

    def test_3year_cagr(self):
        """Test 3-year CAGR calculation"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('133.1'),
            3
        )
        assert abs(result - 0.1) < 0.001  # ~10% annual growth

    def test_none_start_value(self):
        """Test with None start value"""
        result = self.analyzer.calculate_cagr(
            None,
            Decimal('121'),
            2
        )
        assert result is None

    def test_none_end_value(self):
        """Test with None end value"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            None,
            2
        )
        assert result is None

    def test_zero_start_value(self):
        """Test with zero start value"""
        result = self.analyzer.calculate_cagr(
            Decimal('0'),
            Decimal('100'),
            2
        )
        assert result is None

    def test_negative_start_value(self):
        """Test with negative start value"""
        result = self.analyzer.calculate_cagr(
            Decimal('-100'),
            Decimal('100'),
            2
        )
        assert result is None

    def test_negative_end_value(self):
        """Test with negative end value"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('-100'),
            2
        )
        assert result is None

    def test_zero_years(self):
        """Test with zero years"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('121'),
            0
        )
        assert result is None

    def test_negative_years(self):
        """Test with negative years"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('121'),
            -2
        )
        assert result is None

    def test_rounding(self):
        """Test result is rounded to 4 decimal places"""
        result = self.analyzer.calculate_cagr(
            Decimal('100'),
            Decimal('121.123456'),
            2
        )
        assert isinstance(result, float)
        # Check it's rounded to 4 decimals
        assert len(str(result).split('.')[-1]) <= 4


class TestTrendClassification:
    """Test classify_trend method"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    def test_improving_trend(self):
        """Test improving trend classification (>5%)"""
        assert self.analyzer.classify_trend(0.15) == 'improving'
        assert self.analyzer.classify_trend(0.06) == 'improving'
        assert self.analyzer.classify_trend(0.0501) == 'improving'

    def test_declining_trend(self):
        """Test declining trend classification (<-5%)"""
        assert self.analyzer.classify_trend(-0.15) == 'declining'
        assert self.analyzer.classify_trend(-0.06) == 'declining'
        assert self.analyzer.classify_trend(-0.0501) == 'declining'

    def test_stable_trend(self):
        """Test stable trend classification (-5% to 5%)"""
        assert self.analyzer.classify_trend(0.03) == 'stable'
        assert self.analyzer.classify_trend(-0.03) == 'stable'
        assert self.analyzer.classify_trend(0.0) == 'stable'
        assert self.analyzer.classify_trend(0.05) == 'stable'
        assert self.analyzer.classify_trend(-0.05) == 'stable'

    def test_unknown_trend(self):
        """Test unknown trend (None value)"""
        assert self.analyzer.classify_trend(None) == 'unknown'


class TestAnnualComparison:
    """Test analyze_annual_comparison method"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    @pytest.fixture
    def sample_annual_data(self):
        """Sample annual data for testing (Samsung Electronics style)"""
        return [
            {'fiscal_year': 2024, 'revenue': Decimal('258700000000000'), 'net_income': Decimal('22700000000000')},
            {'fiscal_year': 2023, 'revenue': Decimal('222600000000000'), 'net_income': Decimal('14900000000000')},
            {'fiscal_year': 2022, 'revenue': Decimal('302200000000000'), 'net_income': Decimal('55300000000000')},
            {'fiscal_year': 2021, 'revenue': Decimal('279600000000000'), 'net_income': Decimal('39900000000000')},
        ]

    def test_yoy_calculation(self, sample_annual_data):
        """Test YoY growth calculation for multiple years"""
        result = self.analyzer.analyze_annual_comparison(
            sample_annual_data,
            metrics=['revenue', 'net_income']
        )

        # Check YoY structure exists
        assert 'yoy' in result
        assert 'revenue' in result['yoy']
        assert 'net_income' in result['yoy']

        # Check 2024 vs 2023 revenue YoY
        revenue_yoy = result['yoy']['revenue']
        assert '2024_vs_2023' in revenue_yoy
        expected_yoy = (258700000000000 - 222600000000000) / 222600000000000
        assert abs(revenue_yoy['2024_vs_2023'] - expected_yoy) < 0.0001

    def test_cagr_calculation(self, sample_annual_data):
        """Test CAGR calculation for 2Y and 3Y periods"""
        result = self.analyzer.analyze_annual_comparison(
            sample_annual_data,
            metrics=['revenue']
        )

        # Check CAGR structure exists
        assert 'cagr' in result
        assert 'revenue' in result['cagr']

        # Check 2Y CAGR exists (2024, 2023, 2022)
        assert '2y' in result['cagr']['revenue']

        # Check 3Y CAGR exists (2024, 2023, 2022, 2021)
        assert '3y' in result['cagr']['revenue']

    def test_trend_classification(self, sample_annual_data):
        """Test trend classification for each metric"""
        result = self.analyzer.analyze_annual_comparison(
            sample_annual_data,
            metrics=['revenue', 'net_income']
        )

        # Check trends structure exists
        assert 'trends' in result
        assert 'revenue' in result['trends']
        assert 'net_income' in result['trends']

        # Trends should be one of: improving, declining, stable, unknown
        valid_trends = {'improving', 'declining', 'stable', 'unknown'}
        assert result['trends']['revenue'] in valid_trends
        assert result['trends']['net_income'] in valid_trends

    def test_summary_generation(self, sample_annual_data):
        """Test summary generation"""
        result = self.analyzer.analyze_annual_comparison(
            sample_annual_data,
            metrics=['revenue', 'net_income']
        )

        # Check summary structure
        assert 'summary' in result
        assert 'years_analyzed' in result['summary']
        assert 'overall_trend' in result['summary']
        assert 'strongest_metric' in result['summary']
        assert 'weakest_metric' in result['summary']

        # Check years analyzed
        assert result['summary']['years_analyzed'] == 4

        # Check overall trend is valid
        valid_trends = {'improving', 'declining', 'stable', 'unknown'}
        assert result['summary']['overall_trend'] in valid_trends

    def test_empty_data(self):
        """Test with empty annual data"""
        with pytest.raises(ValueError, match="annual_data cannot be empty"):
            self.analyzer.analyze_annual_comparison([])

    def test_single_year_data(self):
        """Test with only one year of data (no comparison possible)"""
        single_year = [
            {'fiscal_year': 2024, 'revenue': Decimal('100'), 'net_income': Decimal('10')}
        ]
        result = self.analyzer.analyze_annual_comparison(single_year, metrics=['revenue'])

        # Should have structure but no YoY data
        assert 'yoy' in result
        assert len(result['yoy']['revenue']) == 0

    def test_unsorted_data(self):
        """Test with unsorted data (should be auto-sorted)"""
        unsorted_data = [
            {'fiscal_year': 2021, 'revenue': Decimal('100')},
            {'fiscal_year': 2024, 'revenue': Decimal('130')},
            {'fiscal_year': 2023, 'revenue': Decimal('120')},
            {'fiscal_year': 2022, 'revenue': Decimal('110')},
        ]
        result = self.analyzer.analyze_annual_comparison(unsorted_data, metrics=['revenue'])

        # Check YoY is calculated correctly despite unsorted input
        assert '2024_vs_2023' in result['yoy']['revenue']
        assert '2023_vs_2022' in result['yoy']['revenue']
        assert '2022_vs_2021' in result['yoy']['revenue']

    def test_missing_metric_values(self):
        """Test with missing metric values (None)"""
        data_with_none = [
            {'fiscal_year': 2024, 'revenue': Decimal('100'), 'net_income': None},
            {'fiscal_year': 2023, 'revenue': Decimal('90'), 'net_income': Decimal('10')},
            {'fiscal_year': 2022, 'revenue': None, 'net_income': Decimal('8')},
        ]
        result = self.analyzer.analyze_annual_comparison(
            data_with_none,
            metrics=['revenue', 'net_income']
        )

        # Should handle None values gracefully
        assert 'yoy' in result
        # Revenue 2024 vs 2023 should exist
        assert '2024_vs_2023' in result['yoy']['revenue']
        # Revenue 2023 vs 2022 should NOT exist (None value)
        assert '2023_vs_2022' not in result['yoy']['revenue']

    def test_default_metrics(self, sample_annual_data):
        """Test with default metrics (no metrics specified)"""
        result = self.analyzer.analyze_annual_comparison(sample_annual_data)

        # Should use DEFAULT_METRICS
        assert 'yoy' in result
        # Should have at least revenue and net_income from sample data
        assert 'revenue' in result['yoy']
        assert 'net_income' in result['yoy']


class TestSectorComparison:
    """Test compare_with_sector method (placeholder)"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    def test_not_implemented(self):
        """Test sector comparison placeholder"""
        result = self.analyzer.compare_with_sector(
            ticker_data={'revenue': Decimal('100')},
            sector_avg={'revenue': Decimal('80')},
            metrics=['revenue']
        )

        assert result['status'] == 'not_implemented'
        assert 'message' in result


class TestEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        self.analyzer = ComparisonAnalyzer()

    def test_very_large_numbers(self):
        """Test with very large numbers (Korean Won amounts)"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('302200000000000'),  # 302.2 trillion
            Decimal('279600000000000')   # 279.6 trillion
        )
        assert result is not None
        assert result > 0  # Should show growth

    def test_very_small_numbers(self):
        """Test with very small numbers"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('0.00001'),
            Decimal('0.00002')
        )
        assert result == -0.5  # 50% decline

    def test_precision_handling(self):
        """Test decimal precision is maintained"""
        result = self.analyzer.calculate_yoy_growth(
            Decimal('100.123456789'),
            Decimal('100.123456780')
        )
        assert result is not None
        # Should handle precision correctly


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
