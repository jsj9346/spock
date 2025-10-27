"""
RSI (Relative Strength Index) Signal Generator

Generates entry/exit signals based on RSI oversold/overbought conditions.

Strategy Logic:
    - Entry: RSI crosses above oversold threshold (default: 30)
    - Exit: RSI crosses below overbought threshold (default: 70)

Parameters:
    - rsi_period: RSI calculation period (default: 14)
    - oversold: Oversold threshold for entry (default: 30)
    - overbought: Overbought threshold for exit (default: 70)

Usage:
    from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator

    entries, exits = rsi_signal_generator(
        close=df['close'],
        rsi_period=14,
        oversold=30,
        overbought=70
    )
"""

import pandas as pd
from typing import Tuple


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    RSI measures the magnitude of recent price changes to evaluate
    overbought or oversold conditions.

    Args:
        close: Close price series
        period: RSI calculation period (default: 14)

    Returns:
        RSI series (0-100 scale)

    Formula:
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
    """
    # Calculate price changes
    delta = close.diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)

    # Calculate exponential moving averages
    avg_gains = gains.ewm(span=period, adjust=False).mean()
    avg_losses = losses.ewm(span=period, adjust=False).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    return rsi


def rsi_signal_generator(
    close: pd.Series,
    rsi_period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Generate RSI-based entry and exit signals.

    Entry Signal:
        RSI crosses above oversold threshold (bullish reversal)

    Exit Signal:
        RSI crosses below overbought threshold (take profit)

    Args:
        close: Close price series (pd.Series with DatetimeIndex)
        rsi_period: RSI calculation period (default: 14)
        oversold: Oversold threshold for entry (default: 30)
        overbought: Overbought threshold for exit (default: 70)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
            entries: True when RSI crosses above oversold
            exits: True when RSI crosses below overbought

    Example:
        >>> entries, exits = rsi_signal_generator(df['close'], rsi_period=14)
        >>> print(f"Entry signals: {entries.sum()}")
        >>> print(f"Exit signals: {exits.sum()}")
    """
    # Calculate RSI
    rsi = calculate_rsi(close, period=rsi_period)

    # Entry: RSI crosses above oversold threshold
    # (RSI is now above threshold AND was below threshold in previous period)
    entries = (rsi > oversold) & (rsi.shift(1) <= oversold)

    # Exit: RSI crosses below overbought threshold
    # (RSI is now below threshold AND was above threshold in previous period)
    exits = (rsi < overbought) & (rsi.shift(1) >= overbought)

    return entries, exits


def rsi_mean_reversion_signal_generator(
    close: pd.Series,
    rsi_period: int = 14,
    oversold_entry: float = 30.0,
    oversold_exit: float = 50.0,
    overbought_entry: float = 70.0,
    overbought_exit: float = 50.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Mean reversion strategy using RSI extremes.

    Long positions when oversold, exit when RSI normalizes.
    Can be extended for short positions when overbought.

    Args:
        close: Close price series
        rsi_period: RSI calculation period (default: 14)
        oversold_entry: Entry threshold for long (default: 30)
        oversold_exit: Exit threshold for long (default: 50)
        overbought_entry: Entry threshold for short (default: 70) [not implemented]
        overbought_exit: Exit threshold for short (default: 50) [not implemented]

    Returns:
        (entries, exits): Tuple of boolean pd.Series
    """
    # Calculate RSI
    rsi = calculate_rsi(close, period=rsi_period)

    # Entry: RSI drops below oversold threshold
    entries = (rsi < oversold_entry) & (rsi.shift(1) >= oversold_entry)

    # Exit: RSI rises back above 50 (mean reversion complete)
    exits = (rsi > oversold_exit) & (rsi.shift(1) <= oversold_exit)

    return entries, exits
