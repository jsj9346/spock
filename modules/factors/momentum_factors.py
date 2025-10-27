#!/usr/bin/env python3
"""
momentum_factors.py - Momentum Factor Implementations

Migrated from LayeredScoringEngine (basic_scoring_modules.py):
- TwelveMonthMomentumFactor: Combines MarketRegimeModule + VolumeProfileModule + MovingAverageModule
- RSIMomentumFactor: Migrated from RelativeStrengthModule

Momentum Strategy:
- Captures trend-following signals
- Identifies stocks with strong recent performance
- Combines price momentum with volume confirmation and trend validation

Academic Foundation:
- Jegadeesh & Titman (1993): "Returns to Buying Winners and Selling Losers"
- 12-month momentum (excl. last month) has strongest academic support
"""

from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np
from .factor_base import FactorBase, FactorResult, FactorCategory
import logging

logger = logging.getLogger(__name__)


class TwelveMonthMomentumFactor(FactorBase):
    """
    12-Month Price Momentum Factor (excluding last month)

    Migrated from LayeredScoringEngine components:
    - MarketRegimeModule: Recent return calculation
    - VolumeProfileModule: Volume-weighted adjustments
    - MovingAverageModule: Trend confirmation via MA slopes

    Calculation:
    1. Base Momentum: (Price_T-21 / Price_T-252) - 1
    2. Volume Adjustment: Scale by recent volume / avg volume
    3. Trend Confirmation: Adjust by MA20/MA60 slopes
    4. Z-score normalization for cross-sectional ranking

    Academic Source:
    - Jegadeesh & Titman (1993): 12M momentum strategy
    - Excludes last month to avoid short-term reversal effect

    Interpretation:
    - Higher values = stronger momentum (bullish)
    - Lower values = weaker momentum (bearish)
    - Z-score > 1.0 = top quintile momentum stocks
    """

    def __init__(self):
        super().__init__(
            name="12M_Momentum",
            category=FactorCategory.MOMENTUM,
            lookback_days=252,  # 1 year of trading days
            min_required_days=252
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate 12-month momentum with volume and trend adjustments

        Args:
            data: Historical OHLCV data (minimum 252 days)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with momentum score, or None if calculation fails
        """
        # Validate data
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            # Ensure we have sufficient data
            if len(data) < 252:
                return None

            # Sort by date to ensure correct ordering
            data = data.sort_values('date').reset_index(drop=True)

            # Step 1: Calculate base 12M momentum (T-252 to T-21)
            price_12m_ago = float(data['close'].iloc[-252])  # 12 months ago
            price_1m_ago = float(data['close'].iloc[-21])     # 1 month ago (exclude last month)

            if price_12m_ago <= 0 or price_1m_ago <= 0:
                return None

            # Base momentum return (percentage)
            momentum_return = float((price_1m_ago / price_12m_ago - 1) * 100)

            # Step 2: Volume-weighted adjustment (from VolumeProfileModule)
            recent_volume = float(data['volume'].iloc[-21:].mean())  # Last month average
            avg_volume_12m = float(data['volume'].iloc[-252:].mean())  # 12-month average

            if avg_volume_12m <= 0:
                volume_weight = 1.0
            else:
                volume_ratio = float(recent_volume / avg_volume_12m)
                # Cap volume weight between 0.5 and 1.5
                volume_weight = float(min(1.5, max(0.5, volume_ratio)))

            adjusted_momentum = float(momentum_return * volume_weight)

            # Step 3: Moving Average trend confirmation (from MovingAverageModule)
            trend_score = float(self._calculate_trend_confirmation(data))

            # Final momentum = base * volume adjustment * (1 + trend bonus)
            final_momentum = float(adjusted_momentum * (1 + trend_score * 0.1))

            # Step 4: Calculate confidence
            null_ratio = self._calculate_null_ratio(data, ['close', 'volume', 'ma20', 'ma60'])
            confidence = self._calculate_confidence(
                data_length=len(data),
                null_ratio=null_ratio,
                additional_factors={
                    'volume_consistency': float(min(1.0, volume_weight)),  # Penalize extreme volume spikes
                    'trend_strength': float(abs(trend_score))  # Stronger trend = higher confidence
                }
            )

            # Metadata for debugging and attribution
            metadata = {
                'base_momentum_return': round(momentum_return, 2),
                'volume_ratio': round(volume_ratio, 2) if avg_volume_12m > 0 else 1.0,
                'volume_weight': round(volume_weight, 2),
                'trend_score': round(trend_score, 2),
                'final_momentum': round(final_momentum, 2),
                'price_12m_ago': price_12m_ago,
                'price_1m_ago': price_1m_ago,
                'data_points': len(data)
            }

            # Create result (z-score and percentile will be calculated at portfolio level)
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=final_momentum,
                z_score=0.0,  # To be calculated cross-sectionally
                percentile=50.0,  # To be calculated cross-sectionally
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _calculate_trend_confirmation(self, data: pd.DataFrame) -> float:
        """
        Calculate trend confirmation score using MA slopes

        Migrated from MovingAverageModule logic

        Args:
            data: Historical OHLCV data with MA indicators

        Returns:
            Trend score (-1.0 to 1.0)
            Positive = bullish trend, Negative = bearish trend
        """
        trend_score = 0.0

        # MA20 slope (short-term trend)
        if 'ma20' in data.columns:
            ma20_values = data['ma20'].dropna()
            if len(ma20_values) >= 20:
                ma20_slope = (ma20_values.iloc[-1] / ma20_values.iloc[-20] - 1) * 100
                # Normalize to -1 to 1 range
                trend_score += np.clip(ma20_slope / 10, -0.5, 0.5)

        # MA60 slope (medium-term trend)
        if 'ma60' in data.columns:
            ma60_values = data['ma60'].dropna()
            if len(ma60_values) >= 20:
                ma60_slope = (ma60_values.iloc[-1] / ma60_values.iloc[-20] - 1) * 100
                # Normalize to -1 to 1 range
                trend_score += np.clip(ma60_slope / 10, -0.5, 0.5)

        # Return trend score (-1.0 to 1.0)
        return float(np.clip(trend_score, -1.0, 1.0))

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['date', 'close', 'volume', 'ma20', 'ma60']


class RSIMomentumFactor(FactorBase):
    """
    RSI-Based Momentum Factor

    Migrated from RelativeStrengthModule RSI logic

    Calculation:
    - Uses 14-day RSI as momentum indicator
    - Optimal momentum zone: RSI 50-70 (uptrend without overbought)
    - Avoids extreme zones: RSI >80 (overbought), RSI <30 (oversold)

    Interpretation:
    - RSI 50-70 = strong bullish momentum (highest score)
    - RSI 30-50 = neutral momentum
    - RSI <30 or >80 = extreme zones (lower score)
    """

    def __init__(self):
        super().__init__(
            name="RSI_Momentum",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,  # Need 60 days for stable RSI calculation
            min_required_days=30
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate RSI-based momentum factor

        Args:
            data: Historical OHLCV data with RSI-14 indicator
            ticker: Stock ticker symbol

        Returns:
            FactorResult with RSI momentum score, or None if calculation fails
        """
        # Validate data
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            # Check for RSI column (rsi_14 or rsi)
            rsi_column = None
            if 'rsi_14' in data.columns:
                rsi_column = 'rsi_14'
            elif 'rsi' in data.columns:
                rsi_column = 'rsi'
            else:
                logger.debug(f"{ticker} - {self.name}: RSI column not found")
                return None

            # Get latest RSI value
            rsi_values = data[rsi_column].dropna()
            if len(rsi_values) == 0:
                return None

            rsi_value = rsi_values.iloc[-1]

            # Calculate RSI momentum score
            # Migrated from RelativeStrengthModule scoring logic
            rsi_momentum_score = self._calculate_rsi_score(rsi_value)

            # Calculate confidence
            null_ratio = self._calculate_null_ratio(data, [rsi_column])
            confidence = self._calculate_confidence(
                data_length=len(rsi_values),
                null_ratio=null_ratio,
                additional_factors={
                    'rsi_stability': float(1.0 - abs(rsi_value - 50) / 50)  # Penalize extreme RSI
                }
            )

            # Metadata
            metadata = {
                'rsi_value': round(rsi_value, 2),
                'rsi_score': round(rsi_momentum_score, 2),
                'rsi_zone': self._classify_rsi_zone(rsi_value),
                'data_points': len(rsi_values)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=rsi_momentum_score,
                z_score=0.0,  # To be calculated cross-sectionally
                percentile=50.0,  # To be calculated cross-sectionally
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _calculate_rsi_score(self, rsi_value: float) -> float:
        """
        Calculate RSI momentum score

        Migrated from RelativeStrengthModule scoring logic

        Args:
            rsi_value: RSI value (0-100)

        Returns:
            Momentum score (0-100)
        """
        # Optimal momentum zone: RSI 50-70
        if 50 <= rsi_value <= 70:
            return 100.0
        # Good momentum zone: RSI 45-75
        elif 45 <= rsi_value <= 75:
            return 75.0
        # Acceptable zone: RSI 40-80
        elif 40 <= rsi_value <= 80:
            return 50.0
        # Overbought zone: RSI >80
        elif rsi_value > 80:
            return 25.0  # Penalize overbought
        # Oversold zone: RSI <30
        elif rsi_value < 30:
            return 30.0  # Slightly better than overbought (potential reversal)
        # Neutral zone
        else:
            return 40.0

    def _classify_rsi_zone(self, rsi_value: float) -> str:
        """Classify RSI into zones for debugging"""
        if rsi_value >= 70:
            return "overbought"
        elif rsi_value >= 50:
            return "bullish_momentum"
        elif rsi_value >= 30:
            return "neutral"
        else:
            return "oversold"

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['rsi_14']  # Will also accept 'rsi' column


class ShortTermMomentumFactor(FactorBase):
    """
    Short-Term Momentum Factor (1-month)

    Complements 12-month momentum with shorter timeframe
    Useful for tactical trading and market timing

    Calculation:
    - 20-day return (approximately 1 month)
    - Volume confirmation
    - Less prone to long-term mean reversion
    """

    def __init__(self):
        super().__init__(
            name="1M_Momentum",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,
            min_required_days=30
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """Calculate 1-month momentum"""
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            if len(data) < 30:
                return None

            data = data.sort_values('date').reset_index(drop=True)

            # 20-day return
            price_20d_ago = data['close'].iloc[-21]
            current_price = data['close'].iloc[-1]

            if price_20d_ago <= 0 or current_price <= 0:
                return None

            momentum_return = (current_price / price_20d_ago - 1) * 100

            # Volume confirmation
            recent_volume = data['volume'].iloc[-5:].mean()
            avg_volume = data['volume'].iloc[-30:].mean()

            volume_confirmed = 1.0
            if avg_volume > 0:
                volume_ratio = recent_volume / avg_volume
                volume_confirmed = 1.2 if volume_ratio > 1.2 else 1.0

            final_momentum = momentum_return * volume_confirmed

            # Confidence
            null_ratio = self._calculate_null_ratio(data, ['close', 'volume'])
            confidence = self._calculate_confidence(
                data_length=len(data),
                null_ratio=null_ratio
            )

            metadata = {
                'momentum_return': round(momentum_return, 2),
                'volume_confirmed': volume_confirmed > 1.0,
                'price_20d_ago': price_20d_ago,
                'current_price': current_price
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=final_momentum,
                z_score=0.0,
                percentile=50.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['date', 'close', 'volume']


class EarningsMomentumFactor(FactorBase):
    """
    Earnings Momentum Factor

    Captures earnings growth acceleration and positive earnings surprises

    Calculation Strategy:
    1. Year-over-Year EPS Growth: (Current EPS - Prior EPS) / |Prior EPS|
    2. Earnings Acceleration: Growth rate of EPS growth rate
    3. Momentum Score: Weighted combination of growth + acceleration

    Data Sources (in priority order):
    - ticker_fundamentals.trailing_eps (preferred)
    - ticker_fundamentals.forward_eps (for forward-looking momentum)
    - Calculated EPS = close_price / per (fallback)

    Academic Foundation:
    - Chan, Jegadeesh & Lakonishok (1996): "Momentum Strategies"
    - Earnings momentum has 6-12 month predictive power
    - Stronger predictor than price momentum in some markets

    Interpretation:
    - Positive values: Accelerating earnings growth (bullish)
    - >10%: Strong earnings momentum
    - 0-10%: Moderate earnings momentum
    - <0%: Decelerating or negative earnings (bearish)
    """

    def __init__(self):
        super().__init__(
            name="Earnings_Momentum",
            category=FactorCategory.MOMENTUM,
            lookback_days=365,  # Prefer 1 year for YoY comparison
            min_required_days=2  # Minimum 2 EPS data points for growth calculation
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate earnings momentum factor

        Args:
            data: Historical fundamental data (ticker_fundamentals joined with ohlcv)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with earnings momentum score, or None if calculation fails
        """
        # Validate data
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            # Ensure data is sorted by date
            data = data.sort_values('date').reset_index(drop=True)

            # Step 1: Get EPS data (trailing_eps preferred, calculate from PER as fallback)
            eps_series = self._get_eps_series(data)

            if eps_series is None or len(eps_series) < 2:
                logger.debug(f"{ticker} - {self.name}: Insufficient EPS data")
                return None

            # Step 2: Calculate Year-over-Year EPS Growth
            eps_growth_yoy = self._calculate_eps_growth_yoy(eps_series)

            if eps_growth_yoy is None:
                return None

            # Step 3: Calculate Earnings Acceleration (if enough history)
            earnings_acceleration = 0.0
            if len(eps_series) >= 4:
                earnings_acceleration = self._calculate_earnings_acceleration(eps_series)

            # Step 4: Calculate Earnings Momentum Score
            # Weighted combination: 70% current growth + 30% acceleration
            earnings_momentum = float(eps_growth_yoy * 0.7 + earnings_acceleration * 0.3)

            # Step 5: Calculate confidence
            null_ratio = self._calculate_null_ratio(data, ['trailing_eps', 'per', 'close'])
            confidence = self._calculate_confidence(
                data_length=len(eps_series),
                null_ratio=null_ratio,
                additional_factors={
                    'eps_data_quality': float(1.0 if 'trailing_eps' in data.columns else 0.7),  # Penalize calculated EPS
                    'earnings_consistency': float(min(1.0, 1.0 / (1.0 + abs(earnings_acceleration) / 20)))  # Penalize volatile earnings
                }
            )

            # Metadata for debugging
            metadata = {
                'eps_growth_yoy': round(eps_growth_yoy, 2),
                'earnings_acceleration': round(earnings_acceleration, 2),
                'earnings_momentum': round(earnings_momentum, 2),
                'current_eps': round(eps_series.iloc[-1], 4) if len(eps_series) > 0 else None,
                'prior_eps': round(eps_series.iloc[-2], 4) if len(eps_series) > 1 else None,
                'data_source': 'trailing_eps' if 'trailing_eps' in data.columns and pd.notna(data['trailing_eps'].iloc[-1]) else 'calculated',
                'data_points': len(eps_series)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=earnings_momentum,
                z_score=0.0,  # To be calculated cross-sectionally
                percentile=50.0,  # To be calculated cross-sectionally
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _get_eps_series(self, data: pd.DataFrame) -> Optional[pd.Series]:
        """
        Get EPS time series from available data sources

        Priority:
        1. trailing_eps column (direct EPS data)
        2. Calculated EPS = close_price / per (fallback)

        Args:
            data: Historical fundamental data

        Returns:
            EPS time series, or None if unavailable
        """
        # Priority 1: Use trailing_eps if available
        if 'trailing_eps' in data.columns:
            eps_series = data['trailing_eps'].dropna()
            if len(eps_series) > 0:
                return eps_series

        # Priority 2: Calculate EPS from Price/PER
        if 'close' in data.columns and 'per' in data.columns:
            # EPS = Price / P/E Ratio
            calculated_eps = data['close'] / data['per']
            calculated_eps = calculated_eps.replace([np.inf, -np.inf], np.nan).dropna()

            if len(calculated_eps) > 0:
                return calculated_eps

        return None

    def _calculate_eps_growth_yoy(self, eps_series: pd.Series) -> Optional[float]:
        """
        Calculate Year-over-Year EPS Growth

        Args:
            eps_series: EPS time series

        Returns:
            YoY EPS growth percentage, or None if calculation fails
        """
        if len(eps_series) < 2:
            return None

        # Get most recent and prior year EPS
        current_eps = float(eps_series.iloc[-1])
        prior_eps = float(eps_series.iloc[-2])

        # Handle edge cases
        if prior_eps == 0:
            # If prior EPS was 0, return large growth if current is positive
            return 100.0 if current_eps > 0 else -100.0

        # Calculate YoY growth percentage
        eps_growth_yoy = float(((current_eps - prior_eps) / abs(prior_eps)) * 100)

        # Cap extreme values (-200% to +500%)
        eps_growth_yoy = float(np.clip(eps_growth_yoy, -200.0, 500.0))

        return eps_growth_yoy

    def _calculate_earnings_acceleration(self, eps_series: pd.Series) -> float:
        """
        Calculate Earnings Acceleration (growth rate of growth rate)

        Measures whether earnings growth is accelerating or decelerating

        Args:
            eps_series: EPS time series (minimum 4 data points)

        Returns:
            Earnings acceleration score
        """
        if len(eps_series) < 4:
            return 0.0

        # Calculate recent growth rate (last 2 periods)
        recent_eps_1 = float(eps_series.iloc[-1])
        recent_eps_2 = float(eps_series.iloc[-2])

        if recent_eps_2 != 0:
            recent_growth = float((recent_eps_1 / recent_eps_2 - 1) * 100)
        else:
            recent_growth = 0.0

        # Calculate prior growth rate (periods 2-3)
        prior_eps_2 = float(eps_series.iloc[-2])
        prior_eps_3 = float(eps_series.iloc[-3])

        if prior_eps_3 != 0:
            prior_growth = float((prior_eps_2 / prior_eps_3 - 1) * 100)
        else:
            prior_growth = 0.0

        # Acceleration = change in growth rate
        acceleration = float(recent_growth - prior_growth)

        # Cap extreme values (-100% to +100%)
        acceleration = float(np.clip(acceleration, -100.0, 100.0))

        return acceleration

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['date', 'close', 'per']  # trailing_eps is optional
