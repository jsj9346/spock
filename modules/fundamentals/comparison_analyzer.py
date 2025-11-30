"""
Comparison Analyzer for Fundamental Data

Provides:
- Year-over-Year (YoY) growth rate calculation
- CAGR (Compound Annual Growth Rate) calculation
- Trend classification (improving/stable/declining)
- Multi-year comparison analysis
"""

from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class ComparisonAnalyzer:
    """연도별 비교 분석기"""

    # Trend thresholds
    IMPROVING_THRESHOLD = 0.05   # >5%
    DECLINING_THRESHOLD = -0.05  # <-5%

    # Default metrics to analyze
    DEFAULT_METRICS = [
        'revenue',
        'operating_profit',
        'net_income',
        'ebitda',
        'total_assets',
        'total_equity'
    ]

    def __init__(self):
        pass

    def calculate_yoy_growth(
        self,
        current_value: Optional[Decimal],
        previous_value: Optional[Decimal]
    ) -> Optional[float]:
        """
        YoY 성장률 계산

        Formula: (current - previous) / abs(previous)

        Args:
            current_value: Current year value
            previous_value: Previous year value

        Returns:
            Growth rate as decimal (0.15 = 15%), or None if calculation not possible

        Examples:
            >>> calculate_yoy_growth(Decimal('115'), Decimal('100'))
            0.15  # 15% growth
            >>> calculate_yoy_growth(Decimal('85'), Decimal('100'))
            -0.15  # 15% decline
            >>> calculate_yoy_growth(Decimal('100'), Decimal('-50'))
            3.0  # 300% growth (from negative)
        """
        # Handle None values
        if current_value is None or previous_value is None:
            logger.debug("Cannot calculate YoY: None value encountered")
            return None

        # Handle zero previous value
        if previous_value == 0:
            logger.debug("Cannot calculate YoY: previous value is zero")
            return None

        try:
            # Convert to float for calculation
            current = float(current_value)
            previous = float(previous_value)

            # Use absolute value in denominator to handle negative previous values
            growth = (current - previous) / abs(previous)

            # Round to 4 decimal places
            return round(growth, 4)

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"Error calculating YoY growth: {e}")
            return None

    def calculate_cagr(
        self,
        start_value: Optional[Decimal],
        end_value: Optional[Decimal],
        years: int
    ) -> Optional[float]:
        """
        CAGR 계산

        Formula: (end_value / start_value)^(1/years) - 1

        Args:
            start_value: Starting year value
            end_value: Ending year value
            years: Number of years in the period

        Returns:
            CAGR as decimal (0.05 = 5% annual growth), or None if calculation not possible

        Examples:
            >>> calculate_cagr(Decimal('100'), Decimal('121'), 2)
            0.1  # 10% annual growth
            >>> calculate_cagr(Decimal('100'), Decimal('80'), 2)
            -0.105  # -10.5% annual decline
        """
        # Handle None values
        if start_value is None or end_value is None:
            logger.debug("Cannot calculate CAGR: None value encountered")
            return None

        # Handle invalid years
        if years <= 0:
            logger.warning(f"Cannot calculate CAGR: invalid years={years}")
            return None

        # Handle zero or negative start value
        if start_value <= 0:
            logger.debug(f"Cannot calculate CAGR: start_value={start_value} <= 0")
            return None

        # Handle negative end value (negative-to-positive or positive-to-negative transitions)
        if end_value <= 0:
            logger.debug(f"Cannot calculate CAGR: end_value={end_value} <= 0")
            return None

        try:
            # Convert to float for calculation
            start = float(start_value)
            end = float(end_value)

            # Calculate CAGR: (end/start)^(1/years) - 1
            cagr = (end / start) ** (1 / years) - 1

            # Round to 4 decimal places
            return round(cagr, 4)

        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as e:
            logger.warning(f"Error calculating CAGR: {e}")
            return None

    def classify_trend(self, growth_rate: Optional[float]) -> str:
        """
        성장률 기반 추세 분류

        Args:
            growth_rate: Growth rate as decimal (0.15 = 15%)

        Returns:
            'improving' (>5%), 'declining' (<-5%), 'stable' (between), or 'unknown' (None)

        Examples:
            >>> classify_trend(0.15)
            'improving'
            >>> classify_trend(-0.10)
            'declining'
            >>> classify_trend(0.03)
            'stable'
        """
        if growth_rate is None:
            return 'unknown'

        if growth_rate > self.IMPROVING_THRESHOLD:
            return 'improving'
        elif growth_rate < self.DECLINING_THRESHOLD:
            return 'declining'
        else:
            return 'stable'

    def analyze_annual_comparison(
        self,
        annual_data: List[Dict],
        metrics: List[str] = None
    ) -> Dict:
        """
        연간 데이터 비교 분석

        Args:
            annual_data: List of annual records sorted by fiscal_year DESC
                [{'fiscal_year': 2024, 'revenue': Decimal('300T'), ...}, ...]
            metrics: Metrics to analyze (default: DEFAULT_METRICS)

        Returns:
            {
                'yoy': {
                    'revenue': {'2024_vs_2023': 0.162, '2023_vs_2022': -0.143, ...},
                    'net_income': {...}
                },
                'cagr': {
                    'revenue': {'3y': 0.002, '2y': 0.08},
                    'net_income': {...}
                },
                'trends': {
                    'revenue': 'improving',
                    'net_income': 'stable'
                },
                'summary': {
                    'overall_trend': 'improving',
                    'strongest_metric': 'revenue',
                    'weakest_metric': 'net_income',
                    'years_analyzed': 5
                }
            }

        Raises:
            ValueError: If annual_data is empty or invalid
        """
        if not annual_data:
            raise ValueError("annual_data cannot be empty")

        # Use default metrics if not specified
        if metrics is None:
            metrics = self.DEFAULT_METRICS

        logger.info(f"Analyzing {len(annual_data)} years of data for {len(metrics)} metrics")

        # Sort by fiscal_year DESC to ensure correct ordering
        sorted_data = sorted(annual_data, key=lambda x: x.get('fiscal_year', 0), reverse=True)

        result = {
            'yoy': defaultdict(dict),
            'cagr': defaultdict(dict),
            'trends': {},
            'summary': {}
        }

        # Calculate YoY growth for each metric
        for metric in metrics:
            yoy_rates = []

            for i in range(len(sorted_data) - 1):
                current_year = sorted_data[i].get('fiscal_year')
                previous_year = sorted_data[i + 1].get('fiscal_year')

                current_value = sorted_data[i].get(metric)
                previous_value = sorted_data[i + 1].get(metric)

                if current_year and previous_year:
                    yoy_key = f"{current_year}_vs_{previous_year}"
                    yoy_growth = self.calculate_yoy_growth(current_value, previous_value)

                    if yoy_growth is not None:
                        result['yoy'][metric][yoy_key] = yoy_growth
                        yoy_rates.append(yoy_growth)
                        logger.debug(f"{metric} {yoy_key}: {yoy_growth:.2%}")

            # Calculate CAGR for 2Y and 3Y periods
            if len(sorted_data) >= 3:
                # 2-year CAGR (most recent 2 years)
                cagr_2y = self.calculate_cagr(
                    sorted_data[2].get(metric),
                    sorted_data[0].get(metric),
                    2
                )
                if cagr_2y is not None:
                    result['cagr'][metric]['2y'] = cagr_2y
                    logger.debug(f"{metric} 2Y CAGR: {cagr_2y:.2%}")

            if len(sorted_data) >= 4:
                # 3-year CAGR (most recent 3 years)
                cagr_3y = self.calculate_cagr(
                    sorted_data[3].get(metric),
                    sorted_data[0].get(metric),
                    3
                )
                if cagr_3y is not None:
                    result['cagr'][metric]['3y'] = cagr_3y
                    logger.debug(f"{metric} 3Y CAGR: {cagr_3y:.2%}")

            # Classify trend based on most recent YoY
            if yoy_rates:
                most_recent_yoy = yoy_rates[0]  # Most recent YoY
                result['trends'][metric] = self.classify_trend(most_recent_yoy)
            else:
                result['trends'][metric] = 'unknown'

        # Generate summary
        result['summary'] = self._generate_summary(result, sorted_data)

        logger.info(f"Analysis complete. Overall trend: {result['summary'].get('overall_trend')}")

        return dict(result)

    def _generate_summary(self, analysis_result: Dict, sorted_data: List[Dict]) -> Dict:
        """
        분석 결과 요약 생성

        Args:
            analysis_result: Analysis result dictionary
            sorted_data: Sorted annual data

        Returns:
            Summary dictionary with overall trend, strongest/weakest metrics
        """
        summary = {
            'years_analyzed': len(sorted_data),
            'overall_trend': 'unknown',
            'strongest_metric': None,
            'weakest_metric': None
        }

        trends = analysis_result.get('trends', {})

        if not trends:
            return summary

        # Count trend types
        trend_counts = defaultdict(int)
        for trend in trends.values():
            trend_counts[trend] += 1

        # Determine overall trend
        if trend_counts['improving'] > trend_counts['declining']:
            summary['overall_trend'] = 'improving'
        elif trend_counts['declining'] > trend_counts['improving']:
            summary['overall_trend'] = 'declining'
        elif trend_counts['stable'] > 0:
            summary['overall_trend'] = 'stable'

        # Find strongest and weakest metrics based on most recent YoY
        yoy_data = analysis_result.get('yoy', {})
        metric_scores = {}

        for metric, yoy_dict in yoy_data.items():
            if yoy_dict:
                # Get most recent YoY (first in sorted order)
                most_recent_yoy = list(yoy_dict.values())[0]
                metric_scores[metric] = most_recent_yoy

        if metric_scores:
            # Strongest metric (highest growth)
            summary['strongest_metric'] = max(metric_scores, key=metric_scores.get)
            # Weakest metric (lowest/most negative growth)
            summary['weakest_metric'] = min(metric_scores, key=metric_scores.get)

        return summary

    def compare_with_sector(
        self,
        ticker_data: Dict,
        sector_avg: Dict,
        metrics: List[str]
    ) -> Dict:
        """
        섹터 평균 대비 비교 (향후 확장용)

        Args:
            ticker_data: Ticker's fundamental data
            sector_avg: Sector average data
            metrics: Metrics to compare

        Returns:
            Comparison result with relative performance

        Note:
            This is a placeholder for future sector comparison functionality.
            Requires sector average data collection and storage.
        """
        logger.info("Sector comparison is not yet implemented")
        return {
            'status': 'not_implemented',
            'message': 'Sector comparison will be available in future release'
        }


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example annual data (Samsung Electronics)
    sample_data = [
        {'fiscal_year': 2024, 'revenue': Decimal('258700000000000'), 'net_income': Decimal('22700000000000')},
        {'fiscal_year': 2023, 'revenue': Decimal('222600000000000'), 'net_income': Decimal('14900000000000')},
        {'fiscal_year': 2022, 'revenue': Decimal('302200000000000'), 'net_income': Decimal('55300000000000')},
        {'fiscal_year': 2021, 'revenue': Decimal('279600000000000'), 'net_income': Decimal('39900000000000')},
        {'fiscal_year': 2020, 'revenue': Decimal('236800000000000'), 'net_income': Decimal('26400000000000')},
    ]

    analyzer = ComparisonAnalyzer()
    result = analyzer.analyze_annual_comparison(sample_data, metrics=['revenue', 'net_income'])

    print("\n=== YoY Growth ===")
    for metric, yoy_dict in result['yoy'].items():
        print(f"\n{metric}:")
        for period, growth in yoy_dict.items():
            print(f"  {period}: {growth:.2%}")

    print("\n=== CAGR ===")
    for metric, cagr_dict in result['cagr'].items():
        print(f"\n{metric}:")
        for period, cagr in cagr_dict.items():
            print(f"  {period}: {cagr:.2%}")

    print("\n=== Trends ===")
    for metric, trend in result['trends'].items():
        print(f"{metric}: {trend}")

    print("\n=== Summary ===")
    for key, value in result['summary'].items():
        print(f"{key}: {value}")
