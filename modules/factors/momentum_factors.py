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
from loguru import logger as loguru_logger
from modules.db_manager_postgres import PostgresDatabaseManager

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


# ================================
# HK Market Momentum Factors
# ================================

class RSIMomentumFactorHK(FactorBase):
    """
    RSI Momentum Factor for HK Market
    
    Data Source: ohlcv_data.rsi_14, region='HK'
    Coverage: 96.09% (2,533/2,636 tickers) ✅ Very high coverage
    
    Calculation:
    - Uses 14-day RSI as momentum indicator
    - Optimal momentum zone: RSI 50-70 (uptrend without overbought)
    - Avoids extreme zones: RSI >80 (overbought), RSI <30 (oversold)
    
    Interpretation:
    - RSI 50-70 = strong bullish momentum (highest score)
    - RSI 30-50 = neutral momentum
    - RSI <30 or >80 = extreme zones (lower score)
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        super().__init__(
            name=f"RSI_Momentum_{region}",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,
            min_required_days=30
        )
        self.region = region
        self.db = db if db is not None else PostgresDatabaseManager()
    
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate RSI-based momentum factor for HK market
        
        Args:
            data: Not used (queries database directly)
            ticker: Stock ticker symbol
            
        Returns:
            FactorResult with RSI momentum score, or None if calculation fails
        """
        try:
            # Normalize ticker format for HK market
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker
            
            # Query recent RSI data from ohlcv_data
            query = """
            SELECT ticker, region, date, close, rsi_14
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s AND rsi_14 IS NOT NULL
            ORDER BY date DESC
            LIMIT 60
            """
            
            result = self.db.execute_query(query, (ticker_for_query, self.region))
            
            if not result or len(result) == 0:
                loguru_logger.debug(f"{ticker} - {self.name}: No RSI data available")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(result)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Get latest RSI value
            rsi_value = float(df['rsi_14'].iloc[-1])
            
            # Validate RSI range (0-100)
            if rsi_value < 0 or rsi_value > 100:
                loguru_logger.warning(f"{ticker} - {self.name}: Invalid RSI value {rsi_value}")
                return None
            
            # Calculate RSI momentum score (migrated from RelativeStrengthModule)
            rsi_momentum_score = self._calculate_rsi_score(rsi_value)
            
            # Calculate RSI stability (penalize extreme volatility)
            rsi_values = df['rsi_14'].values
            rsi_std = float(np.std(rsi_values))
            rsi_stability = float(1.0 - min(rsi_std / 20, 1.0))  # Normalize by 20
            
            # Calculate confidence
            confidence = 0.85 + (rsi_stability * 0.10)  # 0.85 to 0.95
            
            # Metadata
            metadata = {
                'rsi_value': round(rsi_value, 2),
                'rsi_score': round(rsi_momentum_score, 2),
                'rsi_zone': self._classify_rsi_zone(rsi_value),
                'rsi_std': round(rsi_std, 2),
                'data_points': len(df),
                'latest_date': str(df['date'].iloc[-1])
            }
            
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=rsi_momentum_score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - {self.name}: Error - {str(e)}")
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
        """Required DataFrame columns (not used for direct DB query)"""
        return ['rsi_14']


class MACDMomentumFactorHK(FactorBase):
    """
    MACD Momentum Factor for HK Market
    
    Data Source: ohlcv_data.macd, macd_signal, macd_hist, region='HK'
    Coverage: 96.09% (2,533/2,636 tickers) ✅ Very high coverage
    
    Calculation:
    - MACD Line = EMA(12) - EMA(26)
    - Signal Line = EMA(9) of MACD
    - Histogram = MACD - Signal
    
    Momentum Signals:
    - MACD > Signal (positive histogram) = bullish momentum
    - MACD < Signal (negative histogram) = bearish momentum
    - Histogram increasing = momentum strengthening
    - Histogram decreasing = momentum weakening
    
    Score Components:
    1. Histogram value (primary signal)
    2. MACD/Signal crossover position
    3. Histogram trend (increasing/decreasing)
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        super().__init__(
            name=f"MACD_Momentum_{region}",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,
            min_required_days=30
        )
        self.region = region
        self.db = db if db is not None else PostgresDatabaseManager()
    
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate MACD-based momentum factor for HK market
        
        Args:
            data: Not used (queries database directly)
            ticker: Stock ticker symbol
            
        Returns:
            FactorResult with MACD momentum score, or None if calculation fails
        """
        try:
            # Normalize ticker format
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker
            
            # Query MACD data from ohlcv_data
            query = """
            SELECT ticker, region, date, close, macd, macd_signal, macd_hist
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s 
              AND macd IS NOT NULL 
              AND macd_signal IS NOT NULL 
              AND macd_hist IS NOT NULL
            ORDER BY date DESC
            LIMIT 60
            """
            
            result = self.db.execute_query(query, (ticker_for_query, self.region))
            
            if not result or len(result) == 0:
                loguru_logger.debug(f"{ticker} - {self.name}: No MACD data available")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(result)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Get latest MACD values
            macd = float(df['macd'].iloc[-1])
            macd_signal = float(df['macd_signal'].iloc[-1])
            macd_hist = float(df['macd_hist'].iloc[-1])
            
            # Calculate histogram trend (last 5 days)
            if len(df) >= 5:
                hist_recent = df['macd_hist'].iloc[-5:].values
                hist_trend = float(np.mean(np.diff(hist_recent)))  # Average change
            else:
                hist_trend = 0.0
            
            # Calculate MACD momentum score
            macd_score = self._calculate_macd_score(macd_hist, hist_trend)
            
            # Calculate confidence based on MACD stability
            hist_values = df['macd_hist'].values
            hist_std = float(np.std(hist_values))
            close_price = float(df['close'].iloc[-1])
            
            # Normalize histogram std by price
            normalized_std = hist_std / close_price if close_price > 0 else 1.0
            macd_stability = float(1.0 - min(normalized_std * 100, 1.0))
            
            confidence = 0.80 + (macd_stability * 0.15)  # 0.80 to 0.95
            
            # Metadata
            metadata = {
                'macd': round(macd, 4),
                'macd_signal': round(macd_signal, 4),
                'macd_hist': round(macd_hist, 4),
                'hist_trend': round(hist_trend, 4),
                'macd_score': round(macd_score, 2),
                'crossover': 'bullish' if macd > macd_signal else 'bearish',
                'trend': 'strengthening' if hist_trend > 0 else 'weakening',
                'data_points': len(df),
                'latest_date': str(df['date'].iloc[-1])
            }
            
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=macd_score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - {self.name}: Error - {str(e)}")
            return None
    
    def _calculate_macd_score(self, macd_hist: float, hist_trend: float) -> float:
        """
        Calculate MACD momentum score
        
        Args:
            macd_hist: MACD histogram value
            hist_trend: Histogram trend (positive = strengthening)
            
        Returns:
            Momentum score (0-100)
        """
        # Base score from histogram
        if macd_hist > 0:
            # Positive histogram (bullish)
            base_score = 60.0
            # Add bonus for strong positive histogram
            if macd_hist > 0.5:
                base_score = 80.0
            elif macd_hist > 1.0:
                base_score = 90.0
        else:
            # Negative histogram (bearish)
            base_score = 40.0
            # Penalize strong negative histogram
            if macd_hist < -0.5:
                base_score = 20.0
            elif macd_hist < -1.0:
                base_score = 10.0
        
        # Adjust for trend
        if hist_trend > 0:
            # Momentum strengthening
            trend_bonus = min(hist_trend * 20, 20.0)
        else:
            # Momentum weakening
            trend_bonus = max(hist_trend * 20, -20.0)
        
        # Final score (0-100)
        final_score = float(np.clip(base_score + trend_bonus, 0.0, 100.0))
        
        return final_score
    
    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (not used for direct DB query)"""
        return ['macd', 'macd_signal', 'macd_hist']


class Week52HighFactorHK(FactorBase):
    """
    52-Week High Momentum Factor for HK Market
    
    Data Source: ohlcv_data.high, region='HK'
    Coverage: 100% (all tickers with >252 days history)
    
    Calculation:
    - 52-week high = maximum of last 252 trading days
    - Ratio = Current Price / 52-week High
    - Score = ratio * 100 (0-100)
    
    Interpretation:
    - Score > 95: Near 52-week high (strong momentum)
    - Score 80-95: Good momentum
    - Score 60-80: Moderate momentum
    - Score < 60: Weak momentum
    
    Academic Foundation:
    - George & Hwang (2004): "52-Week High and Momentum Investing"
    - Stocks near 52-week highs tend to continue outperforming
    - Combines anchoring bias with momentum effect
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        super().__init__(
            name=f"Week52High_{region}",
            category=FactorCategory.MOMENTUM,
            lookback_days=252,  # 52 weeks = ~252 trading days
            min_required_days=252
        )
        self.region = region
        self.db = db if db is not None else PostgresDatabaseManager()
    
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate 52-week high momentum factor for HK market
        
        Args:
            data: Not used (queries database directly)
            ticker: Stock ticker symbol
            
        Returns:
            FactorResult with 52-week high score, or None if calculation fails
        """
        try:
            # Normalize ticker format
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker
            
            # Query 52 weeks of price data
            query = """
            SELECT ticker, region, date, close, high
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s AND high IS NOT NULL
            ORDER BY date DESC
            LIMIT 252
            """
            
            result = self.db.execute_query(query, (ticker_for_query, self.region))
            
            if not result or len(result) < 252:
                loguru_logger.debug(f"{ticker} - {self.name}: Insufficient data (need 252 days, got {len(result) if result else 0})")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(result)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Get current price and 52-week high
            current_price = float(df['close'].iloc[-1])
            week_52_high = float(df['high'].max())
            
            # Validate prices
            if current_price <= 0 or week_52_high <= 0:
                loguru_logger.warning(f"{ticker} - {self.name}: Invalid price data")
                return None
            
            # Calculate 52-week high ratio
            high_ratio = float(current_price / week_52_high)
            
            # Calculate score (0-100)
            week_52_score = float(high_ratio * 100)
            
            # Find when 52-week high was reached
            high_date_idx = df['high'].idxmax()
            days_since_high = len(df) - high_date_idx - 1
            
            # Calculate distance from high (for metadata)
            distance_from_high = float((1.0 - high_ratio) * 100)  # Percentage below high
            
            # Calculate confidence based on data recency and quality
            recency_factor = float(1.0 - min(days_since_high / 252, 1.0))
            confidence = 0.85 + (recency_factor * 0.10)  # 0.85 to 0.95
            
            # Metadata
            metadata = {
                'current_price': round(current_price, 2),
                'week_52_high': round(week_52_high, 2),
                'high_ratio': round(high_ratio, 4),
                'week_52_score': round(week_52_score, 2),
                'distance_from_high': round(distance_from_high, 2),
                'days_since_high': days_since_high,
                'high_date': str(df['date'].iloc[high_date_idx]),
                'data_points': len(df),
                'latest_date': str(df['date'].iloc[-1])
            }
            
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=week_52_score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - {self.name}: Error - {str(e)}")
            return None
    
    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (not used for direct DB query)"""
        return ['date', 'close', 'high']


class ShortTermMomentumFactorHK(FactorBase):
    """
    Short-Term Momentum Factor for HK Market (1-month)
    
    Data Source: ohlcv_data.close, volume, region='HK'
    Coverage: 100% (all tickers with >30 days history)
    
    Calculation:
    - 20-day return (approximately 1 month)
    - Volume confirmation (recent volume vs 30-day average)
    - Less prone to long-term mean reversion
    
    Interpretation:
    - Complements long-term momentum
    - Useful for tactical trading
    - Higher scores = recent price strength with volume support
    
    Academic Foundation:
    - Short-term momentum persists for 1-3 months
    - Volume confirmation increases signal reliability
    - Combines price and volume momentum
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        super().__init__(
            name=f"1M_Momentum_{region}",
            category=FactorCategory.MOMENTUM,
            lookback_days=60,
            min_required_days=30
        )
        self.region = region
        self.db = db if db is not None else PostgresDatabaseManager()
    
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate 1-month short-term momentum factor for HK market
        
        Args:
            data: Not used (queries database directly)
            ticker: Stock ticker symbol
            
        Returns:
            FactorResult with short-term momentum score, or None if calculation fails
        """
        try:
            # Normalize ticker format
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker
            
            # Query 60 days of price and volume data
            query = """
            SELECT ticker, region, date, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s 
              AND close IS NOT NULL 
              AND volume IS NOT NULL
            ORDER BY date DESC
            LIMIT 60
            """
            
            result = self.db.execute_query(query, (ticker_for_query, self.region))
            
            if not result or len(result) < 30:
                loguru_logger.debug(f"{ticker} - {self.name}: Insufficient data (need 30 days, got {len(result) if result else 0})")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(result)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Calculate 20-day return (1 month)
            if len(df) >= 21:
                price_20d_ago = float(df['close'].iloc[-21])
                current_price = float(df['close'].iloc[-1])
            else:
                # Fallback to available data
                price_20d_ago = float(df['close'].iloc[0])
                current_price = float(df['close'].iloc[-1])
            
            # Validate prices
            if price_20d_ago <= 0 or current_price <= 0:
                loguru_logger.warning(f"{ticker} - {self.name}: Invalid price data")
                return None
            
            # Calculate momentum return (percentage)
            momentum_return = float((current_price / price_20d_ago - 1) * 100)
            
            # Volume confirmation
            recent_volume = float(df['volume'].iloc[-5:].mean())  # Last 5 days
            avg_volume = float(df['volume'].iloc[-30:].mean())     # Last 30 days
            
            volume_confirmed = 1.0
            if avg_volume > 0:
                volume_ratio = float(recent_volume / avg_volume)
                # Bonus if recent volume is higher (>1.2x)
                volume_confirmed = 1.2 if volume_ratio > 1.2 else 1.0
            
            # Final momentum score
            final_momentum = float(momentum_return * volume_confirmed)
            
            # Calculate confidence
            null_count = df[['close', 'volume']].isnull().sum().sum()
            null_ratio = float(null_count / (len(df) * 2))
            confidence = float(max(0.75, 0.95 - null_ratio))
            
            # Metadata
            metadata = {
                'momentum_return': round(momentum_return, 2),
                'volume_ratio': round(volume_ratio if avg_volume > 0 else 1.0, 2),
                'volume_confirmed': volume_confirmed > 1.0,
                'final_momentum': round(final_momentum, 2),
                'price_20d_ago': round(price_20d_ago, 2),
                'current_price': round(current_price, 2),
                'days_used': len(df),
                'data_points': len(df),
                'latest_date': str(df['date'].iloc[-1])
            }
            
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=final_momentum,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - {self.name}: Error - {str(e)}")
            return None
    
    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (not used for direct DB query)"""
        return ['date', 'close', 'volume']


class LongTermMomentumFactorHK(FactorBase):
    """
    Long-Term Momentum Factor for HK Market (6-12 months, excl. last month)
    
    Data Source: ohlcv_data.close, volume, ma20, ma60, region='HK'
    Coverage: ~90% (tickers with >252 days history)
    
    Calculation:
    - 12-month price return (T-252 to T-21, excluding last month)
    - Volume-weighted adjustment (recent volume vs 12-month average)
    - MA trend confirmation (MA20/MA60 slopes)
    - Final score = base momentum * volume weight * (1 + trend bonus)
    
    Interpretation:
    - Higher scores = strong long-term upward trend
    - Excludes last month to avoid short-term reversal
    - Combines price, volume, and trend momentum
    
    Academic Foundation:
    - Jegadeesh & Titman (1993): 12-month momentum (excl. last month)
    - Strongest academic support among momentum strategies
    - Persistence period: 3-12 months after signal
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        super().__init__(
            name=f"12M_Momentum_{region}",
            category=FactorCategory.MOMENTUM,
            lookback_days=252,  # 12 months
            min_required_days=252
        )
        self.region = region
        self.db = db if db is not None else PostgresDatabaseManager()
    
    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate 12-month long-term momentum factor for HK market
        
        Args:
            data: Not used (queries database directly)
            ticker: Stock ticker symbol
            
        Returns:
            FactorResult with long-term momentum score, or None if calculation fails
        """
        try:
            # Normalize ticker format
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker
            
            # Query 252 days of price, volume, and MA data
            query = """
            SELECT ticker, region, date, close, volume, ma20, ma60
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s AND close IS NOT NULL
            ORDER BY date DESC
            LIMIT 252
            """
            
            result = self.db.execute_query(query, (ticker_for_query, self.region))
            
            if not result or len(result) < 252:
                loguru_logger.debug(f"{ticker} - {self.name}: Insufficient data (need 252 days, got {len(result) if result else 0})")
                return None
            
            # Convert to DataFrame and sort
            df = pd.DataFrame(result)
            df = df.sort_values('date').reset_index(drop=True)
            
            # Step 1: Calculate base 12M momentum (T-252 to T-21)
            price_12m_ago = float(df['close'].iloc[-252])  # 12 months ago
            price_1m_ago = float(df['close'].iloc[-21])    # 1 month ago (exclude last month)
            
            # Validate prices
            if price_12m_ago <= 0 or price_1m_ago <= 0:
                loguru_logger.warning(f"{ticker} - {self.name}: Invalid price data")
                return None
            
            # Base momentum return (percentage)
            momentum_return = float((price_1m_ago / price_12m_ago - 1) * 100)
            
            # Step 2: Volume-weighted adjustment
            recent_volume = float(df['volume'].iloc[-21:].mean())  # Last month average
            avg_volume_12m = float(df['volume'].iloc[-252:].mean())  # 12-month average
            
            if avg_volume_12m > 0:
                volume_ratio = float(recent_volume / avg_volume_12m)
                # Cap volume weight between 0.5 and 1.5
                volume_weight = float(min(1.5, max(0.5, volume_ratio)))
            else:
                volume_weight = 1.0
            
            adjusted_momentum = float(momentum_return * volume_weight)
            
            # Step 3: Moving Average trend confirmation
            trend_score = self._calculate_trend_confirmation(df)
            
            # Final momentum = base * volume adjustment * (1 + trend bonus)
            final_momentum = float(adjusted_momentum * (1 + trend_score * 0.1))
            
            # Calculate confidence
            null_count = df[['close', 'volume']].isnull().sum().sum()
            total_cells = len(df) * 2
            null_ratio = float(null_count / total_cells)
            
            # Penalize extreme volume spikes, reward strong trend
            volume_consistency = float(min(1.0, volume_weight))
            trend_strength = float(abs(trend_score))
            
            confidence = 0.80 + (0.05 * volume_consistency) + (0.05 * trend_strength) - (0.10 * null_ratio)
            confidence = float(max(0.70, min(0.95, confidence)))
            
            # Metadata
            metadata = {
                'base_momentum_return': round(momentum_return, 2),
                'volume_ratio': round(volume_ratio if avg_volume_12m > 0 else 1.0, 2),
                'volume_weight': round(volume_weight, 2),
                'trend_score': round(trend_score, 2),
                'final_momentum': round(final_momentum, 2),
                'price_12m_ago': round(price_12m_ago, 2),
                'price_1m_ago': round(price_1m_ago, 2),
                'data_points': len(df),
                'latest_date': str(df['date'].iloc[-1])
            }
            
            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=final_momentum,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - {self.name}: Error - {str(e)}")
            return None
    
    def _calculate_trend_confirmation(self, df: pd.DataFrame) -> float:
        """
        Calculate trend confirmation score using MA slopes
        
        Args:
            df: DataFrame with ma20 and ma60 columns
            
        Returns:
            Trend score (-1.0 to 1.0)
            Positive = bullish trend, Negative = bearish trend
        """
        trend_score = 0.0
        
        try:
            # MA20 slope (short-term trend)
            if 'ma20' in df.columns:
                ma20_values = df['ma20'].dropna()
                if len(ma20_values) >= 20:
                    ma20_slope = float((ma20_values.iloc[-1] / ma20_values.iloc[-20] - 1) * 100)
                    # Normalize to -0.5 to 0.5 range
                    trend_score += float(np.clip(ma20_slope / 10, -0.5, 0.5))
            
            # MA60 slope (medium-term trend)
            if 'ma60' in df.columns:
                ma60_values = df['ma60'].dropna()
                if len(ma60_values) >= 20:
                    ma60_slope = float((ma60_values.iloc[-1] / ma60_values.iloc[-20] - 1) * 100)
                    # Normalize to -0.5 to 0.5 range
                    trend_score += float(np.clip(ma60_slope / 10, -0.5, 0.5))
            
            # Return trend score (-1.0 to 1.0)
            return float(np.clip(trend_score, -1.0, 1.0))
            
        except Exception:
            return 0.0
    
    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (not used for direct DB query)"""
        return ['date', 'close', 'volume', 'ma20', 'ma60']


class MomentumFactorCalculatorHK:
    """
    Composite Momentum Score Calculator for HK Market
    
    Combines 5 momentum factors with optimized weights:
    - 12M_Momentum (30%): Long-term momentum (strongest academic support)
    - Week52High (25%): Anchoring bias + momentum effect
    - 1M_Momentum (20%): Short-term trend
    - RSI_Momentum (15%): Technical confirmation
    - MACD_Momentum (10%): Trend confirmation
    
    Minimum: 3 factors required for composite score
    Dynamic weight renormalization for missing factors
    
    Cross-sectional ranking provides relative momentum strength
    """
    
    def __init__(self, region: str = 'HK', db: Optional[PostgresDatabaseManager] = None):
        self.region = region
        self.shared_db = db if db is not None else PostgresDatabaseManager()
        self.long_term_factor = LongTermMomentumFactorHK(region=region, db=self.shared_db)
        self.week52_factor = Week52HighFactorHK(region=region, db=self.shared_db)
        self.short_term_factor = ShortTermMomentumFactorHK(region=region, db=self.shared_db)
        self.rsi_factor = RSIMomentumFactorHK(region=region, db=self.shared_db)
        self.macd_factor = MACDMomentumFactorHK(region=region, db=self.shared_db)
        
        # Optimal weights based on academic research and practical testing
        self.weights = {
            '12M_Momentum_HK': 0.30,    # Strongest predictor (Jegadeesh & Titman)
            'Week52High_HK': 0.25,       # Behavioral bias exploitation
            '1M_Momentum_HK': 0.20,      # Recent trend
            'RSI_Momentum_HK': 0.15,     # Technical confirmation
            'MACD_Momentum_HK': 0.10     # Trend confirmation
        }
        
        self.results = {}
    
    def calculate_single_ticker(self, ticker: str, data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Calculate all momentum factors for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            data: Optional DataFrame (not used, queries DB directly)
            
        Returns:
            Dictionary with factor results and composite score
        """
        try:
            # Calculate all 5 factors
            factor_results = {}
            
            # Long-term momentum (12M)
            result_12m = self.long_term_factor.calculate(data, ticker)
            if result_12m:
                factor_results['12M_Momentum_HK'] = result_12m
            
            # 52-week high
            result_52w = self.week52_factor.calculate(data, ticker)
            if result_52w:
                factor_results['Week52High_HK'] = result_52w
            
            # Short-term momentum (1M)
            result_1m = self.short_term_factor.calculate(data, ticker)
            if result_1m:
                factor_results['1M_Momentum_HK'] = result_1m
            
            # RSI momentum
            result_rsi = self.rsi_factor.calculate(data, ticker)
            if result_rsi:
                factor_results['RSI_Momentum_HK'] = result_rsi
            
            # MACD momentum
            result_macd = self.macd_factor.calculate(data, ticker)
            if result_macd:
                factor_results['MACD_Momentum_HK'] = result_macd
            
            # Check minimum factors requirement
            if len(factor_results) < 3:
                loguru_logger.debug(f"{ticker} - MomentumFactorCalculatorHK: Insufficient factors ({len(factor_results)}/5)")
                return None
            
            # Calculate weighted composite score
            total_weight = 0.0
            weighted_sum = 0.0
            available_factors = []
            
            for factor_name, result in factor_results.items():
                weight = self.weights.get(factor_name, 0.0)
                total_weight += weight
                weighted_sum += result.raw_value * weight
                available_factors.append(factor_name)
            
            # Renormalize weights
            if total_weight > 0:
                composite_score = float(weighted_sum / total_weight)
            else:
                return None
            
            # Calculate composite confidence (weighted average)
            confidence_sum = sum(result.confidence * self.weights.get(result.factor_name, 0.0) 
                               for result in factor_results.values())
            composite_confidence = float(confidence_sum / total_weight) if total_weight > 0 else 0.80
            
            # Store results
            self.results[ticker] = {
                'ticker': ticker,
                'composite_score': composite_score,
                'confidence': composite_confidence,
                'factor_count': len(factor_results),
                'available_factors': available_factors,
                'factor_results': factor_results
            }
            
            return self.results[ticker]
            
        except Exception as e:
            loguru_logger.error(f"{ticker} - MomentumFactorCalculatorHK: Error - {str(e)}")
            return None
    
    def calculate_all_tickers(self, tickers: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Calculate composite momentum scores for multiple tickers
        
        Args:
            tickers: List of ticker symbols (optional, fetches all HK tickers if None)
            
        Returns:
            DataFrame with composite momentum scores and percentile rankings
        """
        try:
            # Fetch all HK tickers if not provided
            if tickers is None:
                db = PostgresDatabaseManager()
                query = "SELECT DISTINCT ticker FROM tickers WHERE region = 'HK' AND is_active = true ORDER BY ticker"
                result = db.execute_query(query)
                tickers = [row['ticker'].replace('.HK', '') for row in result]  # Remove .HK suffix
                loguru_logger.info(f"Fetched {len(tickers)} HK tickers for momentum calculation")
            
            # Calculate factors for each ticker
            results = []
            for i, ticker in enumerate(tickers, 1):
                if i % 50 == 0:
                    loguru_logger.info(f"Progress: {i}/{len(tickers)} tickers processed...")
                
                result = self.calculate_single_ticker(ticker)
                if result:
                    results.append({
                        'ticker': result['ticker'],
                        'momentum_score': result['composite_score'],
                        'confidence': result['confidence'],
                        'factor_count': result['factor_count'],
                        'available_factors': ', '.join(result['available_factors'])
                    })
            
            # Convert to DataFrame
            df = pd.DataFrame(results)
            
            if len(df) == 0:
                loguru_logger.warning("No tickers with valid momentum factors")
                return df
            
            # Calculate cross-sectional percentiles
            df['percentile'] = df['momentum_score'].rank(pct=True) * 100
            
            # Sort by momentum score (descending)
            df = df.sort_values('momentum_score', ascending=False).reset_index(drop=True)
            
            loguru_logger.info(f"✅ Calculated momentum scores for {len(df)} tickers")
            
            return df
            
        except Exception as e:
            loguru_logger.error(f"MomentumFactorCalculatorHK - Error calculating all tickers: {str(e)}")
            return pd.DataFrame()
    
    def get_factor_coverage_report(self) -> Dict[str, Any]:
        """
        Generate factor coverage report
        
        Returns:
            Dictionary with coverage statistics
        """
        if not self.results:
            return {'error': 'No results calculated yet'}
        
        total_tickers = len(self.results)
        
        # Count factor availability
        factor_counts = {
            '12M_Momentum_HK': 0,
            'Week52High_HK': 0,
            '1M_Momentum_HK': 0,
            'RSI_Momentum_HK': 0,
            'MACD_Momentum_HK': 0
        }
        
        for result in self.results.values():
            for factor_name in result['available_factors']:
                if factor_name in factor_counts:
                    factor_counts[factor_name] += 1
        
        # Calculate coverage percentages
        coverage = {name: f"{count}/{total_tickers} ({count*100/total_tickers:.2f}%)" 
                   for name, count in factor_counts.items()}
        
        # Factor combination stats
        combo_stats = {}
        for result in self.results.values():
            count = result['factor_count']
            combo_stats[count] = combo_stats.get(count, 0) + 1
        
        return {
            'total_tickers': total_tickers,
            'factor_coverage': coverage,
            'factor_combination_stats': combo_stats,
            'weights': self.weights
        }
