# modules/screening/etf_fundamental_scorer.py
"""
ETFFundamentalScorer - Weighted scoring system for ETF screening.

Combines liquidity, momentum, and technical scores for ETF ranking:
- Liquidity Score (40%): Volume (proxy for AUM/liquidity)
- Momentum Score (30%): 1-month price change
- Technical Score (30%): RSI + MA Trend

Scoring Philosophy:
- Higher volume = Higher score (liquidity and popularity)
- Positive momentum = Higher score (performance)
- Stable RSI (30-70) = Higher score (avoid extremes)
- Bullish MA trend = Higher score (technical confirmation)

Output:
- Composite score 0-100 (higher = better investment opportunity)
- Sector-based normalization for fair comparison
- Z-score normalization for cross-sectional ranking

Author: Spock Quant Platform
Date: 2025-10-31
Phase: ETF Screening - Optional Enhancement
"""

from typing import List, Dict, Optional
import numpy as np
from loguru import logger


class ETFFundamentalScorer:
    """
    Calculate composite scores for ETF screening.

    Weights:
    - Liquidity: 40% (Volume as AUM proxy)
    - Momentum: 30% (1-month price change)
    - Technical: 30% (RSI: 15%, MA Trend: 15%)

    Example:
        >>> scorer = ETFFundamentalScorer()
        >>> scores = scorer.calculate_scores(etfs)
        >>> ranked = scorer.rank_by_sector(scores)
    """

    def __init__(
        self,
        liquidity_weight: float = 0.4,
        momentum_weight: float = 0.3,
        technical_weight: float = 0.3
    ):
        """
        Initialize ETFFundamentalScorer.

        Args:
            liquidity_weight: Weight for liquidity (default: 0.4)
            momentum_weight: Weight for momentum (default: 0.3)
            technical_weight: Weight for technical (default: 0.3)
        """
        if abs(liquidity_weight + momentum_weight + technical_weight - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0 (got {liquidity_weight + momentum_weight + technical_weight})")

        self.liquidity_weight = liquidity_weight
        self.momentum_weight = momentum_weight
        self.technical_weight = technical_weight

        # Sub-weights for technical factors
        self.rsi_weight = 0.15 / technical_weight  # Normalized within technical
        self.ma_trend_weight = 0.15 / technical_weight

        logger.info("etf_fundamental_scorer_initialized",
                   liquidity_weight=liquidity_weight,
                   momentum_weight=momentum_weight,
                   technical_weight=technical_weight)

    def calculate_scores(
        self,
        etfs: List[Dict],
        use_zscore: bool = True,
        sector_based: bool = False
    ) -> List[Dict]:
        """
        Calculate composite scores for ETFs.

        Args:
            etfs: List of ETF dicts with technical and performance data
            use_zscore: Use Z-score normalization (default: True)
            sector_based: Normalize within sectors (default: False)

        Returns:
            List of ETFs with added composite_score field, sorted by score

        Example:
            >>> etfs = [
            ...     {
            ...         "ticker": "091160",
            ...         "name": "KODEX 반도체",
            ...         "sector_theme": "Semiconductor",
            ...         "volume_avg_20d": 2500000,
            ...         "price_change_1m": 8.5,
            ...         "rsi": 65.0,
            ...         "ma_trend": "bullish"
            ...     },
            ...     ...
            ... ]
            >>> scored = scorer.calculate_scores(etfs, sector_based=True)
            >>> scored[0]["composite_score"]
            85.3
        """
        if not etfs:
            return []

        # Calculate individual scores
        for etf in etfs:
            # Liquidity score (volume as AUM proxy)
            liquidity_score = self._score_liquidity(etf.get("volume_avg_20d"))

            # Momentum score (1-month price change)
            momentum_score = self._score_momentum(etf.get("price_change_1m"))

            # Technical scores
            rsi_score = self._score_rsi(etf.get("rsi"))
            ma_score = self._score_ma_trend(etf.get("ma_trend"))

            technical_score = (
                rsi_score * self.rsi_weight +
                ma_score * self.ma_trend_weight
            )

            # Combine scores
            composite_score = (
                liquidity_score * self.liquidity_weight +
                momentum_score * self.momentum_weight +
                technical_score * self.technical_weight
            )

            etf["liquidity_score"] = round(liquidity_score, 2)
            etf["momentum_score"] = round(momentum_score, 2)
            etf["technical_score"] = round(technical_score, 2)
            etf["composite_score"] = round(composite_score, 2)

        # Apply Z-score normalization
        if use_zscore and len(etfs) > 1:
            if sector_based:
                self._normalize_by_sector(etfs)
            else:
                self._normalize_all(etfs)

        # Sort by composite score (descending)
        etfs_sorted = sorted(
            etfs,
            key=lambda x: x.get("composite_score", 0),
            reverse=True
        )

        logger.debug(f"Calculated scores for {len(etfs)} ETFs (sector_based={sector_based})")
        return etfs_sorted

    def _score_liquidity(self, volume_avg_20d: Optional[float]) -> float:
        """
        Score liquidity based on 20-day average volume.

        Scoring (volume as AUM proxy):
        - Volume > 5M: 100 points (highly liquid)
        - Volume 1M-5M: 80 points (liquid)
        - Volume 500K-1M: 60 points (moderate liquidity)
        - Volume 100K-500K: 40 points (low liquidity)
        - Volume < 100K: 20 points (very low liquidity)

        Args:
            volume_avg_20d: 20-day average volume

        Returns:
            Score 0-100
        """
        if volume_avg_20d is None or volume_avg_20d <= 0:
            return 0.0

        if volume_avg_20d > 5_000_000:
            return 100.0
        elif volume_avg_20d > 1_000_000:
            # Linear 80-100 for 1M-5M
            return 80 + ((volume_avg_20d - 1_000_000) / 4_000_000) * 20
        elif volume_avg_20d > 500_000:
            # Linear 60-80 for 500K-1M
            return 60 + ((volume_avg_20d - 500_000) / 500_000) * 20
        elif volume_avg_20d > 100_000:
            # Linear 40-60 for 100K-500K
            return 40 + ((volume_avg_20d - 100_000) / 400_000) * 20
        else:
            # Linear 0-40 for 0-100K
            return max(20.0, (volume_avg_20d / 100_000) * 20)

    def _score_momentum(self, price_change_1m: Optional[float]) -> float:
        """
        Score 1-month momentum (price change %).

        Scoring:
        - Price change > +20%: 100 points (strong momentum)
        - Price change +10% to +20%: 80 points (good momentum)
        - Price change 0% to +10%: 60 points (positive)
        - Price change -10% to 0%: 40 points (slight decline)
        - Price change < -10%: 20 points (weak)

        Args:
            price_change_1m: 1-month price change %

        Returns:
            Score 0-100
        """
        if price_change_1m is None:
            return 50.0  # Neutral if no data

        if price_change_1m > 20:
            return 100.0
        elif price_change_1m > 10:
            # Linear 80-100 for +10% to +20%
            return 80 + ((price_change_1m - 10) / 10) * 20
        elif price_change_1m > 0:
            # Linear 60-80 for 0% to +10%
            return 60 + (price_change_1m / 10) * 20
        elif price_change_1m > -10:
            # Linear 40-60 for -10% to 0%
            return 40 + ((price_change_1m + 10) / 10) * 20
        else:
            # Linear 20-40 for < -10%
            return max(20.0, 40 + ((price_change_1m + 10) / 10) * 20)

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
            return 50.0  # Neutral if no data

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
            return 50.0  # Neutral if no data

        trend_scores = {
            "bullish": 100.0,
            "neutral": 60.0,
            "bearish": 20.0
        }

        return trend_scores.get(trend, 50.0)

    def _normalize_all(self, etfs: List[Dict]) -> None:
        """
        Apply Z-score normalization across all ETFs.

        Adds z_score and normalized_score fields to each ETF.
        Normalized score: mean=50, std=15 (0-100 scale)

        Args:
            etfs: List of ETFs with composite_score
        """
        if len(etfs) < 2:
            return

        scores = np.array([e["composite_score"] for e in etfs])
        mean_score = np.mean(scores)
        std_score = np.std(scores)

        if std_score > 0:
            for etf in etfs:
                z_score = (etf["composite_score"] - mean_score) / std_score
                etf["z_score"] = round(z_score, 2)
                # Normalized score 0-100 (mean=50, std=15)
                etf["normalized_score"] = round(
                    max(0, min(100, 50 + (z_score * 15))),
                    2
                )
        else:
            for etf in etfs:
                etf["z_score"] = 0.0
                etf["normalized_score"] = 50.0

    def _normalize_by_sector(self, etfs: List[Dict]) -> None:
        """
        Apply Z-score normalization within each sector.

        This allows fair comparison within sectors (e.g., semiconductor ETFs
        compared only to other semiconductor ETFs).

        Adds z_score and normalized_score fields to each ETF.

        Args:
            etfs: List of ETFs with composite_score and sector_theme
        """
        # Group by sector
        sectors = {}
        for etf in etfs:
            sector = etf.get("sector_theme", "Unknown")
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(etf)

        # Normalize within each sector
        for sector, sector_etfs in sectors.items():
            if len(sector_etfs) < 2:
                # Not enough ETFs for normalization
                for etf in sector_etfs:
                    etf["z_score"] = 0.0
                    etf["normalized_score"] = 50.0
                continue

            scores = np.array([e["composite_score"] for e in sector_etfs])
            mean_score = np.mean(scores)
            std_score = np.std(scores)

            if std_score > 0:
                for etf in sector_etfs:
                    z_score = (etf["composite_score"] - mean_score) / std_score
                    etf["z_score"] = round(z_score, 2)
                    # Normalized score 0-100 (mean=50, std=15)
                    etf["normalized_score"] = round(
                        max(0, min(100, 50 + (z_score * 15))),
                        2
                    )
                    etf["sector_rank"] = None  # Will be set in rank_by_sector
            else:
                for etf in sector_etfs:
                    etf["z_score"] = 0.0
                    etf["normalized_score"] = 50.0
                    etf["sector_rank"] = None

        logger.debug(f"Normalized {len(etfs)} ETFs across {len(sectors)} sectors")

    def rank_by_sector(
        self,
        etfs: List[Dict],
        score_field: str = "normalized_score"
    ) -> List[Dict]:
        """
        Rank ETFs within their sectors.

        Args:
            etfs: List of ETFs with scores and sector_theme
            score_field: Field to rank by (default: "normalized_score")

        Returns:
            List of ETFs with sector_rank field added

        Example:
            >>> ranked = scorer.rank_by_sector(scored_etfs)
            >>> ranked[0]["sector_rank"]
            1
            >>> ranked[0]["sector_theme"]
            'Semiconductor'
        """
        # Group by sector
        sectors = {}
        for etf in etfs:
            sector = etf.get("sector_theme", "Unknown")
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(etf)

        # Rank within each sector
        for sector, sector_etfs in sectors.items():
            # Sort by score (descending)
            sorted_etfs = sorted(
                sector_etfs,
                key=lambda x: x.get(score_field, 0),
                reverse=True
            )

            # Add sector rank
            for i, etf in enumerate(sorted_etfs, 1):
                etf["sector_rank"] = i

        # Sort all ETFs by score for overall ranking
        all_sorted = sorted(
            etfs,
            key=lambda x: x.get(score_field, 0),
            reverse=True
        )

        # Add overall rank
        for i, etf in enumerate(all_sorted, 1):
            etf["overall_rank"] = i

        logger.debug(f"Ranked {len(etfs)} ETFs across {len(sectors)} sectors")
        return all_sorted

    def get_top_by_sector(
        self,
        etfs: List[Dict],
        top_n: int = 5,
        score_field: str = "normalized_score"
    ) -> Dict[str, List[Dict]]:
        """
        Get top N ETFs from each sector.

        Args:
            etfs: List of ETFs with scores and sector_theme
            top_n: Number of top ETFs to return per sector
            score_field: Field to rank by (default: "normalized_score")

        Returns:
            Dict mapping sector names to lists of top ETFs

        Example:
            >>> top_by_sector = scorer.get_top_by_sector(scored_etfs, top_n=3)
            >>> top_by_sector["Semiconductor"][:3]
            [
                {"ticker": "091160", "name": "KODEX 반도체", "normalized_score": 85.3, ...},
                ...
            ]
        """
        # Group by sector
        sectors = {}
        for etf in etfs:
            sector = etf.get("sector_theme", "Unknown")
            if sector not in sectors:
                sectors[sector] = []
            sectors[sector].append(etf)

        # Get top N from each sector
        top_by_sector = {}
        for sector, sector_etfs in sectors.items():
            # Sort by score (descending)
            sorted_etfs = sorted(
                sector_etfs,
                key=lambda x: x.get(score_field, 0),
                reverse=True
            )
            top_by_sector[sector] = sorted_etfs[:top_n]

        logger.debug(f"Got top {top_n} ETFs from {len(sectors)} sectors")
        return top_by_sector
