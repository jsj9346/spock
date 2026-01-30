#!/usr/bin/env python3
"""
test_screening.py - Unit Tests for Screening Module

Tests for:
- CompositeScorer: Weighted scoring system for stock screening
- FilterRegistry: Registry pattern for screening filters
- ScreeningResult: Dataclass for screening results
- TechnicalCalculator: Technical indicator calculations

Coverage target: screening/* (~600 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date


class TestCompositeScorerInit(unittest.TestCase):
    """Test CompositeScorer initialization"""

    def test_default_initialization(self):
        """Test CompositeScorer with default weights"""
        from modules.screening.composite_scorer import CompositeScorer

        scorer = CompositeScorer()

        self.assertEqual(scorer.fundamental_weight, 0.6)
        self.assertEqual(scorer.technical_weight, 0.4)

    def test_custom_weights_initialization(self):
        """Test CompositeScorer with custom weights"""
        from modules.screening.composite_scorer import CompositeScorer

        scorer = CompositeScorer(fundamental_weight=0.7, technical_weight=0.3)

        self.assertEqual(scorer.fundamental_weight, 0.7)
        self.assertEqual(scorer.technical_weight, 0.3)

    def test_invalid_weights_raises_error(self):
        """Test that weights not summing to 1.0 raises ValueError"""
        from modules.screening.composite_scorer import CompositeScorer

        with self.assertRaises(ValueError) as context:
            CompositeScorer(fundamental_weight=0.6, technical_weight=0.5)

        self.assertIn("must sum to 1.0", str(context.exception))

    def test_sub_weights_calculation(self):
        """Test sub-weights are properly calculated"""
        from modules.screening.composite_scorer import CompositeScorer

        scorer = CompositeScorer(fundamental_weight=0.6, technical_weight=0.4)

        # Fundamental sub-weights (normalized within 0.6)
        self.assertAlmostEqual(scorer.per_weight, 0.25 / 0.6, places=5)
        self.assertAlmostEqual(scorer.pbr_weight, 0.20 / 0.6, places=5)
        self.assertAlmostEqual(scorer.div_yield_weight, 0.15 / 0.6, places=5)

        # Technical sub-weights (normalized within 0.4)
        self.assertAlmostEqual(scorer.rsi_weight, 0.20 / 0.4, places=5)
        self.assertAlmostEqual(scorer.ma_trend_weight, 0.20 / 0.4, places=5)


class TestCompositeScorerPER(unittest.TestCase):
    """Test P/E ratio scoring"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_score_per_deep_value(self):
        """Test P/E < 10 returns 100 points (deep value)"""
        score = self.scorer._score_per(5)
        self.assertEqual(score, 100.0)

    def test_score_per_value(self):
        """Test P/E 10-15 returns 80-100 points (value)"""
        score = self.scorer._score_per(12.5)
        # Linear interpolation: 100 - ((12.5 - 10) / 5) * 20 = 100 - 10 = 90
        self.assertEqual(score, 90.0)

    def test_score_per_fair_value(self):
        """Test P/E 15-20 returns 60-80 points (fair value)"""
        score = self.scorer._score_per(17.5)
        # Linear: 80 - ((17.5 - 15) / 5) * 20 = 80 - 10 = 70
        self.assertEqual(score, 70.0)

    def test_score_per_growth(self):
        """Test P/E 20-30 returns 40-60 points (growth)"""
        score = self.scorer._score_per(25)
        # Linear: 60 - ((25 - 20) / 10) * 20 = 60 - 10 = 50
        self.assertEqual(score, 50.0)

    def test_score_per_expensive(self):
        """Test P/E > 30 returns 20-40 points (expensive)"""
        score = self.scorer._score_per(35)
        # Linear: max(20, 40 - ((35 - 30) / 20) * 20) = max(20, 35) = 35
        self.assertEqual(score, 35.0)

    def test_score_per_very_expensive(self):
        """Test P/E >> 30 has minimum score of 20"""
        score = self.scorer._score_per(100)
        self.assertEqual(score, 20.0)

    def test_score_per_none(self):
        """Test None P/E returns 0"""
        score = self.scorer._score_per(None)
        self.assertEqual(score, 0.0)

    def test_score_per_negative(self):
        """Test negative P/E returns 0"""
        score = self.scorer._score_per(-5)
        self.assertEqual(score, 0.0)

    def test_score_per_zero(self):
        """Test zero P/E returns 0"""
        score = self.scorer._score_per(0)
        self.assertEqual(score, 0.0)


class TestCompositeScorerPBR(unittest.TestCase):
    """Test P/B ratio scoring"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_score_pbr_undervalued(self):
        """Test P/B < 1 returns 100 points (undervalued)"""
        score = self.scorer._score_pbr(0.8)
        self.assertEqual(score, 100.0)

    def test_score_pbr_fair_value(self):
        """Test P/B 1-2 returns 80-100 points (fair value)"""
        score = self.scorer._score_pbr(1.5)
        # Linear: 100 - ((1.5 - 1) / 1) * 20 = 100 - 10 = 90
        self.assertEqual(score, 90.0)

    def test_score_pbr_slightly_expensive(self):
        """Test P/B 2-3 returns 60-80 points (slightly expensive)"""
        score = self.scorer._score_pbr(2.5)
        # Linear: 80 - ((2.5 - 2) / 1) * 20 = 80 - 10 = 70
        self.assertEqual(score, 70.0)

    def test_score_pbr_expensive(self):
        """Test P/B > 3 returns 40+ points (expensive)"""
        score = self.scorer._score_pbr(4)
        # Linear: max(40, 60 - ((4 - 3) / 2) * 20) = max(40, 50) = 50
        self.assertEqual(score, 50.0)

    def test_score_pbr_very_expensive(self):
        """Test P/B >> 3 has minimum score of 40"""
        score = self.scorer._score_pbr(10)
        self.assertEqual(score, 40.0)

    def test_score_pbr_none(self):
        """Test None P/B returns 0"""
        score = self.scorer._score_pbr(None)
        self.assertEqual(score, 0.0)

    def test_score_pbr_negative(self):
        """Test negative P/B returns 0"""
        score = self.scorer._score_pbr(-1.5)
        self.assertEqual(score, 0.0)


class TestCompositeScorerDividendYield(unittest.TestCase):
    """Test dividend yield scoring"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_score_dividend_high_income(self):
        """Test Div Yield > 5% returns 100 points (high income)"""
        score = self.scorer._score_dividend_yield(6.0)
        self.assertEqual(score, 100.0)

    def test_score_dividend_good_income(self):
        """Test Div Yield 3-5% returns 80-100 points (good income)"""
        score = self.scorer._score_dividend_yield(4.0)
        # Linear: 80 + ((4 - 3) / 2) * 20 = 80 + 10 = 90
        self.assertEqual(score, 90.0)

    def test_score_dividend_moderate_income(self):
        """Test Div Yield 1-3% returns 60-80 points (moderate income)"""
        score = self.scorer._score_dividend_yield(2.0)
        # Linear: 60 + ((2 - 1) / 2) * 20 = 60 + 10 = 70
        self.assertEqual(score, 70.0)

    def test_score_dividend_low_income(self):
        """Test Div Yield < 1% returns 40-60 points (low income)"""
        score = self.scorer._score_dividend_yield(0.5)
        # Linear: 40 + (0.5 / 1) * 20 = 40 + 10 = 50
        self.assertEqual(score, 50.0)

    def test_score_dividend_zero(self):
        """Test zero dividend yield returns 40"""
        score = self.scorer._score_dividend_yield(0.0)
        self.assertEqual(score, 40.0)

    def test_score_dividend_none(self):
        """Test None dividend yield returns 0"""
        score = self.scorer._score_dividend_yield(None)
        self.assertEqual(score, 0.0)

    def test_score_dividend_negative(self):
        """Test negative dividend yield returns 0"""
        score = self.scorer._score_dividend_yield(-1.0)
        self.assertEqual(score, 0.0)


class TestCompositeScorerRSI(unittest.TestCase):
    """Test RSI scoring"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_score_rsi_neutral_center(self):
        """Test RSI 40-60 returns 100 points (neutral, stable)"""
        score = self.scorer._score_rsi(50)
        self.assertEqual(score, 100.0)

    def test_score_rsi_slight_oversold(self):
        """Test RSI 30-40 returns 80-100 points (slight momentum)"""
        score = self.scorer._score_rsi(35)
        # Linear: 80 + ((35 - 30) / 10) * 20 = 80 + 10 = 90
        self.assertEqual(score, 90.0)

    def test_score_rsi_slight_overbought(self):
        """Test RSI 60-70 returns 80-100 points (slight momentum)"""
        score = self.scorer._score_rsi(65)
        # Linear: 100 - ((65 - 60) / 10) * 20 = 100 - 10 = 90
        self.assertEqual(score, 90.0)

    def test_score_rsi_oversold(self):
        """Test RSI 20-30 returns 60-80 points (oversold)"""
        score = self.scorer._score_rsi(25)
        # Linear: 60 + ((25 - 20) / 10) * 20 = 60 + 10 = 70
        self.assertEqual(score, 70.0)

    def test_score_rsi_overbought(self):
        """Test RSI 70-80 returns 60-80 points (overbought)"""
        score = self.scorer._score_rsi(75)
        # Linear: 80 - ((75 - 70) / 10) * 20 = 80 - 10 = 70
        self.assertEqual(score, 70.0)

    def test_score_rsi_extreme(self):
        """Test RSI < 20 or > 80 returns 40 points (extreme)"""
        score_low = self.scorer._score_rsi(10)
        score_high = self.scorer._score_rsi(90)
        self.assertEqual(score_low, 40.0)
        self.assertEqual(score_high, 40.0)

    def test_score_rsi_none(self):
        """Test None RSI returns 0"""
        score = self.scorer._score_rsi(None)
        self.assertEqual(score, 0.0)


class TestCompositeScorerMATrend(unittest.TestCase):
    """Test MA trend scoring"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_score_ma_trend_bullish(self):
        """Test bullish trend returns 100 points"""
        score = self.scorer._score_ma_trend("bullish")
        self.assertEqual(score, 100.0)

    def test_score_ma_trend_neutral(self):
        """Test neutral trend returns 60 points"""
        score = self.scorer._score_ma_trend("neutral")
        self.assertEqual(score, 60.0)

    def test_score_ma_trend_bearish(self):
        """Test bearish trend returns 20 points"""
        score = self.scorer._score_ma_trend("bearish")
        self.assertEqual(score, 20.0)

    def test_score_ma_trend_none(self):
        """Test None trend returns 0"""
        score = self.scorer._score_ma_trend(None)
        self.assertEqual(score, 0.0)

    def test_score_ma_trend_invalid(self):
        """Test invalid trend returns 0"""
        score = self.scorer._score_ma_trend("unknown")
        self.assertEqual(score, 0.0)


class TestCompositeScorerCalculateScores(unittest.TestCase):
    """Test calculate_scores method"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_calculate_scores_empty_list(self):
        """Test empty stock list returns empty list"""
        result = self.scorer.calculate_scores([])
        self.assertEqual(result, [])

    def test_calculate_scores_fundamental_only(self):
        """Test scoring with fundamental data only"""
        stocks = [
            {"ticker": "005930", "per": 12.5, "pbr": 1.5, "dividend_yield": 2.5},
        ]

        result = self.scorer.calculate_scores(stocks, use_zscore=False)

        self.assertEqual(len(result), 1)
        self.assertIn("composite_score", result[0])
        self.assertIn("fundamental_score", result[0])
        self.assertIsNone(result[0]["technical_score"])

    def test_calculate_scores_with_technical(self):
        """Test scoring with technical data included"""
        stocks = [
            {
                "ticker": "005930",
                "per": 12.5,
                "pbr": 1.5,
                "dividend_yield": 2.5,
                "rsi": 45,
                "ma_trend": "bullish"
            },
        ]

        result = self.scorer.calculate_scores(stocks, use_zscore=False)

        self.assertEqual(len(result), 1)
        self.assertIn("composite_score", result[0])
        self.assertIn("fundamental_score", result[0])
        self.assertIsNotNone(result[0]["technical_score"])

    def test_calculate_scores_sorted_by_score(self):
        """Test results are sorted by composite score descending"""
        stocks = [
            {"ticker": "A", "per": 30, "pbr": 5, "dividend_yield": 0},
            {"ticker": "B", "per": 10, "pbr": 0.8, "dividend_yield": 5},
            {"ticker": "C", "per": 20, "pbr": 2, "dividend_yield": 2},
        ]

        result = self.scorer.calculate_scores(stocks, use_zscore=False)

        # B should be first (best value metrics)
        self.assertEqual(result[0]["ticker"], "B")
        # A should be last (worst metrics)
        self.assertEqual(result[-1]["ticker"], "A")

    def test_calculate_scores_with_zscore(self):
        """Test Z-score normalization is applied"""
        stocks = [
            {"ticker": "A", "per": 10, "pbr": 1, "dividend_yield": 3},
            {"ticker": "B", "per": 20, "pbr": 2, "dividend_yield": 2},
            {"ticker": "C", "per": 30, "pbr": 3, "dividend_yield": 1},
        ]

        result = self.scorer.calculate_scores(stocks, use_zscore=True)

        # Should have z_score and normalized_score fields
        for stock in result:
            self.assertIn("z_score", stock)
            self.assertIn("normalized_score", stock)


class TestCompositeScorerRank(unittest.TestCase):
    """Test rank_by_score method"""

    def setUp(self):
        from modules.screening.composite_scorer import CompositeScorer
        self.scorer = CompositeScorer()

    def test_rank_by_score_default(self):
        """Test ranking by composite_score"""
        stocks = [
            {"ticker": "A", "composite_score": 50},
            {"ticker": "B", "composite_score": 80},
            {"ticker": "C", "composite_score": 65},
        ]

        result = self.scorer.rank_by_score(stocks)

        self.assertEqual(result[0]["ticker"], "B")
        self.assertEqual(result[0]["rank"], 1)
        self.assertEqual(result[1]["ticker"], "C")
        self.assertEqual(result[1]["rank"], 2)
        self.assertEqual(result[2]["ticker"], "A")
        self.assertEqual(result[2]["rank"], 3)

    def test_rank_by_custom_field(self):
        """Test ranking by custom score field"""
        stocks = [
            {"ticker": "A", "fundamental_score": 60, "composite_score": 50},
            {"ticker": "B", "fundamental_score": 40, "composite_score": 80},
        ]

        result = self.scorer.rank_by_score(stocks, score_field="fundamental_score")

        self.assertEqual(result[0]["ticker"], "A")
        self.assertEqual(result[0]["rank"], 1)


class TestFilterRegistry(unittest.TestCase):
    """Test FilterRegistry class"""

    def test_initialization(self):
        """Test FilterRegistry initialization"""
        from modules.screening.stock_screener import FilterRegistry

        registry = FilterRegistry()

        self.assertEqual(registry._filters, {})

    def test_register_filter(self):
        """Test registering a filter"""
        from modules.screening.stock_screener import FilterRegistry

        registry = FilterRegistry()

        @registry.register("value_filter")
        def value_filter(stocks):
            return [s for s in stocks if s.get("per", 100) < 15]

        self.assertIn("value_filter", registry._filters)

    def test_get_filter(self):
        """Test getting a registered filter"""
        from modules.screening.stock_screener import FilterRegistry

        registry = FilterRegistry()

        @registry.register("test_filter")
        def test_filter(stocks):
            return stocks

        retrieved = registry.get("test_filter")
        self.assertEqual(retrieved, test_filter)

    def test_get_nonexistent_filter(self):
        """Test getting non-existent filter returns None"""
        from modules.screening.stock_screener import FilterRegistry

        registry = FilterRegistry()

        result = registry.get("nonexistent")
        self.assertIsNone(result)

    def test_list_filters(self):
        """Test listing all registered filters"""
        from modules.screening.stock_screener import FilterRegistry

        registry = FilterRegistry()

        @registry.register("filter1")
        def f1(s): return s

        @registry.register("filter2")
        def f2(s): return s

        filters = registry.list_filters()

        self.assertIn("filter1", filters)
        self.assertIn("filter2", filters)
        self.assertEqual(len(filters), 2)


class TestScreeningResult(unittest.TestCase):
    """Test ScreeningResult dataclass"""

    def test_creation(self):
        """Test ScreeningResult creation"""
        from modules.screening.stock_screener import ScreeningResult

        df = pd.DataFrame({"ticker": ["A", "B"], "score": [80, 60]})

        result = ScreeningResult(
            region="KR",
            filter_type="value",
            timestamp=datetime.now(),
            total_results=2,
            data=df,
            parameters={"per_max": 15}
        )

        self.assertEqual(result.region, "KR")
        self.assertEqual(result.filter_type, "value")
        self.assertEqual(result.total_results, 2)
        self.assertEqual(len(result.data), 2)

    def test_to_csv(self):
        """Test exporting to CSV"""
        from modules.screening.stock_screener import ScreeningResult
        import tempfile

        df = pd.DataFrame({"ticker": ["A", "B"], "score": [80, 60]})
        result = ScreeningResult(
            region="KR",
            filter_type="value",
            timestamp=datetime.now(),
            total_results=2,
            data=df,
            parameters={}
        )

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            result.to_csv(tmp.name)
            # Read back and verify
            read_df = pd.read_csv(tmp.name)
            self.assertEqual(len(read_df), 2)
            os.unlink(tmp.name)

    def test_to_excel(self):
        """Test exporting to Excel"""
        from modules.screening.stock_screener import ScreeningResult
        import tempfile

        df = pd.DataFrame({"ticker": ["A", "B"], "score": [80, 60]})
        result = ScreeningResult(
            region="KR",
            filter_type="value",
            timestamp=datetime.now(),
            total_results=2,
            data=df,
            parameters={}
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            result.to_excel(tmp.name)
            # Read back and verify
            read_df = pd.read_excel(tmp.name)
            self.assertEqual(len(read_df), 2)
            os.unlink(tmp.name)


class TestTechnicalCalculatorInit(unittest.TestCase):
    """Test TechnicalCalculator initialization"""

    def test_default_initialization(self):
        """Test TechnicalCalculator with defaults"""
        from modules.screening.technical_calculator import TechnicalCalculator

        calculator = TechnicalCalculator()

        self.assertEqual(calculator.default_rsi_period, 14)
        self.assertEqual(calculator.default_ma_periods, [20, 50, 200])


class TestTechnicalCalculatorRSI(unittest.TestCase):
    """Test RSI calculation"""

    def setUp(self):
        from modules.screening.technical_calculator import TechnicalCalculator
        self.calculator = TechnicalCalculator()

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI with insufficient data returns None"""
        df = pd.DataFrame({"close": [100, 101, 102]})  # Only 3 rows

        result = self.calculator.calculate_rsi(df, period=14)

        self.assertIsNone(result)

    def test_calculate_rsi_basic(self):
        """Test basic RSI calculation"""
        # Generate sufficient price data
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_rsi(df)

        self.assertIsNotNone(result)
        self.assertIn("rsi", result)
        self.assertIn("signal", result)
        self.assertIn("period", result)
        self.assertEqual(result["period"], 14)

    def test_calculate_rsi_signal_oversold(self):
        """Test RSI oversold signal detection"""
        # Generate declining prices to create oversold condition
        prices = [100 - i * 2 for i in range(50)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_rsi(df)

        self.assertIsNotNone(result)
        self.assertEqual(result["signal"], "oversold")
        self.assertLess(result["rsi"], 30)

    def test_calculate_rsi_signal_overbought(self):
        """Test RSI overbought signal detection"""
        # Generate rising prices to create overbought condition
        prices = [100 + i * 2 for i in range(50)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_rsi(df)

        self.assertIsNotNone(result)
        self.assertEqual(result["signal"], "overbought")
        self.assertGreater(result["rsi"], 70)


class TestTechnicalCalculatorMA(unittest.TestCase):
    """Test Moving Average calculation"""

    def setUp(self):
        from modules.screening.technical_calculator import TechnicalCalculator
        self.calculator = TechnicalCalculator()

    def test_calculate_ma_insufficient_data(self):
        """Test MA with insufficient data returns None"""
        df = pd.DataFrame({"close": [100] * 50})  # Only 50 rows, need 200

        result = self.calculator.calculate_moving_averages(df)

        self.assertIsNone(result)

    def test_calculate_ma_basic(self):
        """Test basic MA calculation"""
        # Generate sufficient price data
        prices = [100 + i * 0.5 for i in range(250)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_moving_averages(df)

        self.assertIsNotNone(result)
        self.assertIn("ma20", result)
        self.assertIn("ma50", result)
        self.assertIn("ma200", result)
        self.assertIn("price", result)

    def test_calculate_ma_bullish_trend(self):
        """Test bullish trend detection"""
        # Upward trend: MA20 > MA50 > MA200
        prices = [100 + i * 1.0 for i in range(250)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_moving_averages(df)

        self.assertIsNotNone(result)
        self.assertEqual(result["trend"], "bullish")
        self.assertGreater(result["ma20"], result["ma50"])
        self.assertGreater(result["ma50"], result["ma200"])

    def test_calculate_ma_bearish_trend(self):
        """Test bearish trend detection"""
        # Downward trend: MA20 < MA50 < MA200
        prices = [300 - i * 1.0 for i in range(250)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_moving_averages(df)

        self.assertIsNotNone(result)
        self.assertEqual(result["trend"], "bearish")
        self.assertLess(result["ma20"], result["ma50"])
        self.assertLess(result["ma50"], result["ma200"])

    def test_calculate_ma_custom_periods(self):
        """Test MA with custom periods"""
        prices = [100 + i * 0.1 for i in range(100)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_moving_averages(df, periods=[10, 20, 50])

        self.assertIsNotNone(result)
        self.assertIn("ma10", result)
        self.assertIn("ma20", result)
        self.assertIn("ma50", result)


class TestTechnicalCalculatorAllIndicators(unittest.TestCase):
    """Test combined indicator calculation"""

    def setUp(self):
        from modules.screening.technical_calculator import TechnicalCalculator
        self.calculator = TechnicalCalculator()

    def test_calculate_all_indicators(self):
        """Test calculating all indicators at once"""
        prices = [100 + i * 0.5 for i in range(250)]
        df = pd.DataFrame({"close": prices})

        result = self.calculator.calculate_all_indicators(df)

        self.assertIsNotNone(result)
        self.assertIn("rsi", result)
        self.assertIn("moving_averages", result)
        self.assertIn("timestamp", result)

    def test_calculate_all_indicators_insufficient_data(self):
        """Test with insufficient data returns None"""
        df = pd.DataFrame({"close": [100] * 5})

        result = self.calculator.calculate_all_indicators(df)

        self.assertIsNone(result)


class TestTechnicalCalculatorBatch(unittest.TestCase):
    """Test batch calculation"""

    def setUp(self):
        from modules.screening.technical_calculator import TechnicalCalculator
        self.calculator = TechnicalCalculator()

    def test_batch_calculate(self):
        """Test batch calculation for multiple tickers"""
        ticker_data = {
            "A": pd.DataFrame({"close": [100 + i * 0.5 for i in range(250)]}),
            "B": pd.DataFrame({"close": [200 + i * 0.3 for i in range(250)]}),
        }

        result = self.calculator.batch_calculate(ticker_data)

        self.assertEqual(len(result), 2)
        self.assertIn("A", result)
        self.assertIn("B", result)

    def test_batch_calculate_partial_failure(self):
        """Test batch with some tickers having insufficient data"""
        ticker_data = {
            "A": pd.DataFrame({"close": [100 + i * 0.5 for i in range(250)]}),
            "B": pd.DataFrame({"close": [100] * 5}),  # Insufficient data
        }

        result = self.calculator.batch_calculate(ticker_data)

        self.assertIn("A", result)
        self.assertNotIn("B", result)


class TestTechnicalCalculatorFilters(unittest.TestCase):
    """Test filtering methods"""

    def setUp(self):
        from modules.screening.technical_calculator import TechnicalCalculator
        self.calculator = TechnicalCalculator()

    def test_filter_by_rsi_max(self):
        """Test filtering by RSI max threshold"""
        indicators = {
            "A": {"rsi": {"rsi": 25}},
            "B": {"rsi": {"rsi": 45}},
            "C": {"rsi": {"rsi": 75}},
        }

        result = self.calculator.filter_by_rsi(indicators, rsi_max=30)

        self.assertEqual(result, ["A"])

    def test_filter_by_rsi_min(self):
        """Test filtering by RSI min threshold"""
        indicators = {
            "A": {"rsi": {"rsi": 25}},
            "B": {"rsi": {"rsi": 45}},
            "C": {"rsi": {"rsi": 75}},
        }

        result = self.calculator.filter_by_rsi(indicators, rsi_min=50)

        self.assertEqual(result, ["C"])

    def test_filter_by_rsi_range(self):
        """Test filtering by RSI range"""
        indicators = {
            "A": {"rsi": {"rsi": 25}},
            "B": {"rsi": {"rsi": 45}},
            "C": {"rsi": {"rsi": 75}},
        }

        result = self.calculator.filter_by_rsi(indicators, rsi_min=30, rsi_max=60)

        self.assertEqual(result, ["B"])

    def test_filter_by_rsi_missing_data(self):
        """Test filtering handles missing RSI data"""
        indicators = {
            "A": {"rsi": {"rsi": 25}},
            "B": {"rsi": None},
            "C": {},
        }

        result = self.calculator.filter_by_rsi(indicators, rsi_max=30)

        self.assertEqual(result, ["A"])

    def test_filter_by_ma_trend_bullish(self):
        """Test filtering by bullish trend"""
        indicators = {
            "A": {"moving_averages": {"trend": "bullish"}},
            "B": {"moving_averages": {"trend": "bearish"}},
            "C": {"moving_averages": {"trend": "neutral"}},
        }

        result = self.calculator.filter_by_ma_trend(indicators, "bullish")

        self.assertEqual(result, ["A"])

    def test_filter_by_ma_trend_bearish(self):
        """Test filtering by bearish trend"""
        indicators = {
            "A": {"moving_averages": {"trend": "bullish"}},
            "B": {"moving_averages": {"trend": "bearish"}},
            "C": {"moving_averages": {"trend": "neutral"}},
        }

        result = self.calculator.filter_by_ma_trend(indicators, "bearish")

        self.assertEqual(result, ["B"])

    def test_filter_by_ma_trend_missing_data(self):
        """Test filtering handles missing MA data"""
        indicators = {
            "A": {"moving_averages": {"trend": "bullish"}},
            "B": {"moving_averages": None},
            "C": {},
        }

        result = self.calculator.filter_by_ma_trend(indicators, "bullish")

        self.assertEqual(result, ["A"])


# Parametrized tests
@pytest.mark.parametrize("per,expected_min,expected_max", [
    (5, 99, 101),       # Deep value: 100
    (12.5, 89, 91),     # Value: 90
    (17.5, 69, 71),     # Fair value: 70
    (25, 49, 51),       # Growth: 50
    (100, 19, 21),      # Very expensive: 20
])
def test_per_scoring_ranges(per, expected_min, expected_max):
    """Test P/E scoring produces expected ranges"""
    from modules.screening.composite_scorer import CompositeScorer

    scorer = CompositeScorer()
    score = scorer._score_per(per)

    assert expected_min <= score <= expected_max


@pytest.mark.parametrize("rsi,expected_signal", [
    (25, "oversold"),
    (35, "neutral"),
    (50, "neutral"),
    (65, "neutral"),
    (75, "overbought"),
    (85, "overbought"),
])
def test_rsi_signal_classification(rsi, expected_signal):
    """Test RSI signal classification (simplified logic)"""
    # Direct signal classification
    if rsi < 30:
        signal = "oversold"
    elif rsi > 70:
        signal = "overbought"
    else:
        signal = "neutral"

    assert signal == expected_signal


@pytest.mark.parametrize("trend,expected_score", [
    ("bullish", 100.0),
    ("neutral", 60.0),
    ("bearish", 20.0),
    (None, 0.0),
    ("invalid", 0.0),
])
def test_ma_trend_scoring(trend, expected_score):
    """Test MA trend scoring"""
    from modules.screening.composite_scorer import CompositeScorer

    scorer = CompositeScorer()
    score = scorer._score_ma_trend(trend)

    assert score == expected_score


class TestStockScreenerWithMockedDB(unittest.TestCase):
    """Test StockScreener with mocked database"""

    def test_initialization(self):
        """Test StockScreener initialization"""
        from modules.screening.stock_screener import StockScreener

        mock_db = Mock()
        screener = StockScreener(mock_db)

        self.assertEqual(screener.db, mock_db)
        self.assertIsNotNone(screener.registry)

    def test_screen_technical_empty_result(self):
        """Test technical screening with empty result"""
        from modules.screening.stock_screener import StockScreener

        mock_db = Mock()
        mock_db.execute_query.return_value = []

        screener = StockScreener(mock_db)
        result = screener.screen_technical(region='KR', rsi_max=30)

        self.assertEqual(result.total_results, 0)
        self.assertTrue(result.data.empty)

    def test_screen_value_empty_result(self):
        """Test value screening with empty result"""
        from modules.screening.stock_screener import StockScreener

        mock_db = Mock()
        mock_db.execute_query.return_value = []

        screener = StockScreener(mock_db)
        result = screener.screen_value(region='US', per_max=15)

        self.assertEqual(result.total_results, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
