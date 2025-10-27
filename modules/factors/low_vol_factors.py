#!/usr/bin/env python3
"""
low_vol_factors.py - Low-Volatility Factor Implementations

Low-Volatility Strategy:
- Defensive investment approach
- Seeks stocks with lower risk (lower volatility)
- Academic evidence: Low-vol stocks outperform high-vol stocks (anomaly)

Academic Foundation:
- Baker, Bradley, & Wurgler (2011): "Benchmarks as Limits to Arbitrage"
- Low-volatility anomaly: Lower risk stocks generate higher risk-adjusted returns

Factor Interpretation:
- LOWER volatility = HIGHER factor score (defensive)
- Factor is negatively related to risk
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from .factor_base import FactorBase, FactorResult, FactorCategory
import logging

logger = logging.getLogger(__name__)


class HistoricalVolatilityFactor(FactorBase):
    """
    Historical Volatility Factor (60-day)

    Calculation:
    - Annualized volatility = std(daily_returns) * sqrt(252)
    - Lower volatility = higher factor score (defensive strategy)
    - Factor value = -volatility (so low vol stocks rank higher)

    Interpretation:
    - Higher factor value = Lower volatility (defensive, stable)
    - Lower factor value = Higher volatility (aggressive, risky)
    - Suitable for risk-averse investors and bear markets
    """

    def __init__(self):
        super().__init__(
            name="Historical_Volatility",
            category=FactorCategory.LOW_VOL,
            lookback_days=60,
            min_required_days=60
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate historical volatility factor

        Args:
            data: Historical OHLCV data (minimum 60 days)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with volatility score (negated for ranking), or None
        """
        # Validate data
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            if len(data) < 60:
                return None

            # Sort by date
            data = data.sort_values('date').reset_index(drop=True)

            # Calculate daily returns
            returns = data['close'].pct_change().dropna()

            if len(returns) < 30:
                return None

            # Calculate volatility (annualized)
            # Standard deviation of daily returns * sqrt(252 trading days)
            daily_std = returns.std()
            annualized_volatility = daily_std * np.sqrt(252) * 100  # Convert to percentage

            # Negate volatility for ranking (lower vol = higher score)
            factor_value = -annualized_volatility

            # Calculate downside volatility (semi-deviation)
            # Only consider negative returns for downside risk
            negative_returns = returns[returns < 0]
            downside_volatility = 0.0
            if len(negative_returns) > 0:
                downside_volatility = negative_returns.std() * np.sqrt(252) * 100

            # Calculate confidence
            null_ratio = self._calculate_null_ratio(data, ['close'])
            confidence = self._calculate_confidence(
                data_length=len(returns),
                null_ratio=null_ratio,
                additional_factors={
                    'return_stability': float(1.0 - min(1.0, annualized_volatility / 100))  # Lower vol = higher stability
                }
            )

            # Metadata for debugging
            metadata = {
                'annualized_volatility': round(annualized_volatility, 2),
                'downside_volatility': round(downside_volatility, 2),
                'daily_std': round(daily_std, 4),
                'data_points': len(returns),
                'negative_days': len(negative_returns),
                'negative_ratio': round(len(negative_returns) / len(returns), 2) if len(returns) > 0 else 0.0
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,  # Negated volatility
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
        return ['date', 'close']


class BetaFactor(FactorBase):
    """
    Beta Factor (Market Sensitivity)

    Calculation:
    - Beta = Cov(stock_returns, market_returns) / Var(market_returns)
    - Requires market index data (KOSPI for KR market)
    - Lower beta = higher factor score (defensive)

    Interpretation:
    - Beta < 1.0 = Less volatile than market (defensive)
    - Beta = 1.0 = Market-level volatility
    - Beta > 1.0 = More volatile than market (aggressive)
    """

    def __init__(self):
        super().__init__(
            name="Beta",
            category=FactorCategory.LOW_VOL,
            lookback_days=252,
            min_required_days=60
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate beta factor

        Note: This is a placeholder. Requires market index data for proper implementation.
        Current implementation returns None (to be implemented in Phase 2).

        Args:
            data: Historical OHLCV data with market index
            ticker: Stock ticker symbol

        Returns:
            None (placeholder - requires market index integration)
        """
        logger.debug(f"{ticker} - {self.name}: Placeholder - requires market index data")
        return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['date', 'close', 'market_close']  # Requires market index data


class MaxDrawdownFactor(FactorBase):
    """
    Maximum Drawdown Factor

    Calculation:
    - Max drawdown = Maximum peak-to-trough decline
    - Lower drawdown = higher factor score (defensive)
    - Measures downside risk and capital preservation

    Interpretation:
    - Smaller drawdown = more stable stock (defensive)
    - Larger drawdown = higher risk stock
    """

    def __init__(self):
        super().__init__(
            name="Max_Drawdown",
            category=FactorCategory.LOW_VOL,
            lookback_days=252,
            min_required_days=60
        )

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """Calculate maximum drawdown factor"""
        is_valid, error_msg = self.validate_data(data)
        if not is_valid:
            logger.debug(f"{ticker} - {self.name}: {error_msg}")
            return None

        try:
            if len(data) < 60:
                return None

            data = data.sort_values('date').reset_index(drop=True)

            # Calculate cumulative maximum (running peak)
            prices = data['close']
            cummax = prices.cummax()

            # Calculate drawdown from peak
            drawdown = (prices - cummax) / cummax * 100  # Percentage

            # Maximum drawdown (most negative value)
            max_drawdown = drawdown.min()

            # Negate for ranking (smaller drawdown = higher score)
            factor_value = -max_drawdown

            # Calculate recovery time (days to recover from max drawdown)
            max_dd_idx = drawdown.idxmin()
            recovery_idx = None
            peak_price = cummax.iloc[max_dd_idx]

            for idx in range(max_dd_idx + 1, len(prices)):
                if prices.iloc[idx] >= peak_price:
                    recovery_idx = idx
                    break

            recovery_days = (recovery_idx - max_dd_idx) if recovery_idx else None

            # Confidence
            null_ratio = self._calculate_null_ratio(data, ['close'])
            confidence = self._calculate_confidence(
                data_length=len(data),
                null_ratio=null_ratio,
                additional_factors={
                    'drawdown_severity': float(1.0 - min(1.0, abs(max_drawdown) / 50))  # Penalize large drawdowns
                }
            )

            metadata = {
                'max_drawdown': round(max_drawdown, 2),
                'recovery_days': recovery_days,
                'current_drawdown': round(drawdown.iloc[-1], 2),
                'data_points': len(data)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,  # Negated drawdown
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
        return ['date', 'close']
