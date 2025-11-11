# modules/screening/composite_scorer.py
"""
CompositeScorer - Weighted scoring system for stock screening.

Combines fundamental and technical scores into a unified ranking metric:
- Fundamental Score (60%): P/E, P/B, Dividend Yield
- Technical Score (40%): RSI, MA Trend

Scoring Philosophy:
- Lower P/E = Higher score (value investing)
- Lower P/B = Higher score (value investing)
- Higher Dividend Yield = Higher score (income investing)
- RSI 30-70 = Higher score (avoid extremes)
- Bullish MA Trend = Higher score (momentum confirmation)

Output:
- Composite score 0-100 (higher = better investment opportunity)
- Z-score normalization for cross-sectional comparison

Author: Spock Quant Platform
Date: 2025-10-31
"""

from typing import List, Dict, Optional
import numpy as np
from loguru import logger


class CompositeScorer:
    """
    Calculate composite scores for stock screening.

    Weights:
    - Fundamental: 60% (P/E: 25%, P/B: 20%, Div Yield: 15%)
    - Technical: 40% (RSI: 20%, MA Trend: 20%)

    Example:
        >>> scorer = CompositeScorer()
        >>> scores = scorer.calculate_scores(stocks)
        >>> ranked = scorer.rank_by_score(scores)
    """

    def __init__(
        self,
        fundamental_weight: float = 0.6,
        technical_weight: float = 0.4
    ):
        """
        Initialize CompositeScorer.

        Args:
            fundamental_weight: Weight for fundamental factors (default: 0.6)
            technical_weight: Weight for technical factors (default: 0.4)
        """
        if fundamental_weight + technical_weight != 1.0:
            raise ValueError("Weights must sum to 1.0")

        self.fundamental_weight = fundamental_weight
        self.technical_weight = technical_weight

        # Sub-weights for fundamental factors
        self.per_weight = 0.25 / fundamental_weight  # Normalized within fundamental
        self.pbr_weight = 0.20 / fundamental_weight
        self.div_yield_weight = 0.15 / fundamental_weight

        # Sub-weights for technical factors
        self.rsi_weight = 0.20 / technical_weight  # Normalized within technical
        self.ma_trend_weight = 0.20 / technical_weight

        logger.info("composite_scorer_initialized",
                   fundamental_weight=fundamental_weight,
                   technical_weight=technical_weight)

    def calculate_scores(
        self,
        stocks: List[Dict],
        use_zscore: bool = True
    ) -> List[Dict]:
        """
        Calculate composite scores for stocks.

        Args:
            stocks: List of stock dicts with fundamental and technical data
            use_zscore: Use Z-score normalization (default: True)

        Returns:
            List of stocks with added composite_score field, sorted by score

        Example:
            >>> stocks = [
            ...     {"ticker": "005930", "per": 12.5, "pbr": 1.8, "dividend_yield": 3.2,
            ...      "rsi": 45.0, "ma_trend": "bullish"},
            ...     ...
            ... ]
            >>> scored = scorer.calculate_scores(stocks)
            >>> scored[0]["composite_score"]
            82.5
        """
        if not stocks:
            return []

        # Calculate individual scores
        for stock in stocks:
            # Fundamental scores
            per_score = self._score_per(stock.get("per"))
            pbr_score = self._score_pbr(stock.get("pbr"))
            div_score = self._score_dividend_yield(stock.get("dividend_yield"))

            # Weight fundamental scores
            fundamental_score = (
                per_score * self.per_weight +
                pbr_score * self.pbr_weight +
                div_score * self.div_yield_weight
            )

            # Technical scores (if available)
            technical_score = 0.0
            if stock.get("rsi") is not None or stock.get("ma_trend") is not None:
                rsi_score = self._score_rsi(stock.get("rsi"))
                ma_score = self._score_ma_trend(stock.get("ma_trend"))

                technical_score = (
                    rsi_score * self.rsi_weight +
                    ma_score * self.ma_trend_weight
                )

            # Combine scores
            if technical_score > 0:
                composite_score = (
                    fundamental_score * self.fundamental_weight +
                    technical_score * self.technical_weight
                )
            else:
                # No technical data - use fundamental only
                composite_score = fundamental_score

            stock["fundamental_score"] = round(fundamental_score, 2)
            stock["technical_score"] = round(technical_score, 2) if technical_score > 0 else None
            stock["composite_score"] = round(composite_score, 2)

        # Apply Z-score normalization if requested
        if use_zscore and len(stocks) > 1:
            scores = np.array([s["composite_score"] for s in stocks])
            mean_score = np.mean(scores)
            std_score = np.std(scores)

            if std_score > 0:
                for stock in stocks:
                    z_score = (stock["composite_score"] - mean_score) / std_score
                    stock["z_score"] = round(z_score, 2)
                    # Normalized score 0-100 (mean=50, std=15)
                    stock["normalized_score"] = round(50 + (z_score * 15), 2)
            else:
                for stock in stocks:
                    stock["z_score"] = 0.0
                    stock["normalized_score"] = 50.0

        # Sort by composite score (descending)
        stocks_sorted = sorted(
            stocks,
            key=lambda x: x.get("composite_score", 0),
            reverse=True
        )

        logger.debug(f"Calculated scores for {len(stocks)} stocks")
        return stocks_sorted

    def _score_per(self, per: Optional[float]) -> float:
        """
        Score P/E ratio (lower is better for value investing).

        Scoring:
        - P/E < 10: 100 points (deep value)
        - P/E 10-15: 80 points (value)
        - P/E 15-20: 60 points (fair value)
        - P/E 20-30: 40 points (growth)
        - P/E > 30: 20 points (expensive)

        Args:
            per: P/E ratio

        Returns:
            Score 0-100
        """
        if per is None or per <= 0:
            return 0.0

        if per < 10:
            return 100.0
        elif per < 15:
            return 100 - ((per - 10) / 5) * 20  # Linear 100-80
        elif per < 20:
            return 80 - ((per - 15) / 5) * 20   # Linear 80-60
        elif per < 30:
            return 60 - ((per - 20) / 10) * 20  # Linear 60-40
        else:
            return max(20.0, 40 - ((per - 30) / 20) * 20)  # Linear 40-20

    def _score_pbr(self, pbr: Optional[float]) -> float:
        """
        Score P/B ratio (lower is better for value investing).

        Scoring:
        - P/B < 1: 100 points (undervalued)
        - P/B 1-2: 80 points (fair value)
        - P/B 2-3: 60 points (slightly expensive)
        - P/B > 3: 40 points (expensive)

        Args:
            pbr: P/B ratio

        Returns:
            Score 0-100
        """
        if pbr is None or pbr <= 0:
            return 0.0

        if pbr < 1:
            return 100.0
        elif pbr < 2:
            return 100 - ((pbr - 1) / 1) * 20  # Linear 100-80
        elif pbr < 3:
            return 80 - ((pbr - 2) / 1) * 20   # Linear 80-60
        else:
            return max(40.0, 60 - ((pbr - 3) / 2) * 20)  # Linear 60-40

    def _score_dividend_yield(self, div_yield: Optional[float]) -> float:
        """
        Score dividend yield (higher is better for income investing).

        Scoring:
        - Div Yield > 5%: 100 points (high income)
        - Div Yield 3-5%: 80 points (good income)
        - Div Yield 1-3%: 60 points (moderate income)
        - Div Yield < 1%: 40 points (low income)

        Args:
            div_yield: Dividend yield %

        Returns:
            Score 0-100
        """
        if div_yield is None or div_yield < 0:
            return 0.0

        if div_yield > 5:
            return 100.0
        elif div_yield > 3:
            return 80 + ((div_yield - 3) / 2) * 20  # Linear 80-100
        elif div_yield > 1:
            return 60 + ((div_yield - 1) / 2) * 20  # Linear 60-80
        else:
            return 40 + (div_yield / 1) * 20  # Linear 0-60

    def _score_rsi(self, rsi: Optional[float]) -> float:
        """
        Score RSI (30-70 is best, avoid extremes).

        Scoring:
        - RSI 40-60: 100 points (neutral, stable)
        - RSI 30-40 or 60-70: 80 points (slight momentum)
        - RSI 20-30 or 70-80: 60 points (oversold/overbought)
        - RSI < 20 or > 80: 40 points (extreme)

        Args:
            rsi: RSI value 0-100

        Returns:
            Score 0-100
        """
        if rsi is None:
            return 0.0

        if 40 <= rsi <= 60:
            return 100.0
        elif 30 <= rsi < 40:
            return 80 + ((rsi - 30) / 10) * 20  # Linear 80-100
        elif 60 < rsi <= 70:
            return 100 - ((rsi - 60) / 10) * 20  # Linear 100-80
        elif 20 <= rsi < 30:
            return 60 + ((rsi - 20) / 10) * 20  # Linear 60-80
        elif 70 < rsi <= 80:
            return 80 - ((rsi - 70) / 10) * 20  # Linear 80-60
        else:
            return 40.0

    def _score_ma_trend(self, trend: Optional[str]) -> float:
        """
        Score MA trend.

        Scoring:
        - Bullish: 100 points (positive momentum)
        - Neutral: 60 points (sideways)
        - Bearish: 20 points (negative momentum)

        Args:
            trend: "bullish", "bearish", or "neutral"

        Returns:
            Score 0-100
        """
        if trend is None:
            return 0.0

        trend_scores = {
            "bullish": 100.0,
            "neutral": 60.0,
            "bearish": 20.0
        }

        return trend_scores.get(trend, 0.0)

    def rank_by_score(
        self,
        stocks: List[Dict],
        score_field: str = "composite_score"
    ) -> List[Dict]:
        """
        Rank stocks by specified score field.

        Args:
            stocks: List of stocks with scores
            score_field: Field to rank by (default: "composite_score")

        Returns:
            Sorted list with rank field added

        Example:
            >>> ranked = scorer.rank_by_score(scored_stocks)
            >>> ranked[0]["rank"]
            1
        """
        # Sort by score (descending)
        sorted_stocks = sorted(
            stocks,
            key=lambda x: x.get(score_field, 0),
            reverse=True
        )

        # Add rank
        for i, stock in enumerate(sorted_stocks, 1):
            stock["rank"] = i

        return sorted_stocks
