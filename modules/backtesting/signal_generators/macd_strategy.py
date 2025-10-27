"""
MACD (Moving Average Convergence Divergence) Signal Generator

Generates entry/exit signals based on MACD line crossovers with signal line.

Strategy Logic:
    - Entry: MACD line crosses above signal line (bullish crossover)
    - Exit: MACD line crosses below signal line (bearish crossover)

Parameters:
    - fast_period: Fast EMA period (default: 12)
    - slow_period: Slow EMA period (default: 26)
    - signal_period: Signal line EMA period (default: 9)

Usage:
    from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator

    entries, exits = macd_signal_generator(
        close=df['close'],
        fast_period=12,
        slow_period=26,
        signal_period=9
    )
"""

import pandas as pd
from typing import Tuple, Dict


def calculate_macd(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD is a trend-following momentum indicator showing relationship
    between two moving averages of prices.

    Args:
        close: Close price series
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        Dictionary with keys:
            'macd': MACD line (fast_ema - slow_ema)
            'signal': Signal line (EMA of MACD)
            'histogram': MACD histogram (macd - signal)

    Formula:
        MACD = EMA(12) - EMA(26)
        Signal = EMA(MACD, 9)
        Histogram = MACD - Signal
    """
    # Calculate EMAs
    fast_ema = close.ewm(span=fast_period, adjust=False).mean()
    slow_ema = close.ewm(span=slow_period, adjust=False).mean()

    # Calculate MACD line
    macd_line = fast_ema - slow_ema

    # Calculate signal line (EMA of MACD)
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    # Calculate histogram
    histogram = macd_line - signal_line

    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def macd_signal_generator(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[pd.Series, pd.Series]:
    """
    Generate MACD crossover signals.

    Entry Signal:
        MACD line crosses above signal line (bullish crossover)

    Exit Signal:
        MACD line crosses below signal line (bearish crossover)

    Args:
        close: Close price series (pd.Series with DatetimeIndex)
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
            entries: True when MACD crosses above signal
            exits: True when MACD crosses below signal

    Example:
        >>> entries, exits = macd_signal_generator(df['close'])
        >>> print(f"Entry signals: {entries.sum()}")
        >>> print(f"Exit signals: {exits.sum()}")
    """
    # Calculate MACD components
    macd_data = calculate_macd(close, fast_period, slow_period, signal_period)
    macd_line = macd_data['macd']
    signal_line = macd_data['signal']

    # Entry: MACD crosses above signal line
    # (MACD is now above signal AND was below signal in previous period)
    entries = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))

    # Exit: MACD crosses below signal line
    # (MACD is now below signal AND was above signal in previous period)
    exits = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

    return entries, exits


def macd_histogram_signal_generator(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    histogram_threshold: float = 0.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Generate signals based on MACD histogram zero crossovers.

    Alternative strategy focusing on histogram momentum.

    Entry Signal:
        Histogram crosses above zero (momentum turning positive)

    Exit Signal:
        Histogram crosses below zero (momentum turning negative)

    Args:
        close: Close price series
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        histogram_threshold: Threshold for signals (default: 0.0)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
    """
    # Calculate MACD components
    macd_data = calculate_macd(close, fast_period, slow_period, signal_period)
    histogram = macd_data['histogram']

    # Entry: Histogram crosses above threshold
    entries = (histogram > histogram_threshold) & (histogram.shift(1) <= histogram_threshold)

    # Exit: Histogram crosses below threshold
    exits = (histogram < histogram_threshold) & (histogram.shift(1) >= histogram_threshold)

    return entries, exits


def macd_trend_following_signal_generator(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    min_histogram: float = 0.5
) -> Tuple[pd.Series, pd.Series]:
    """
    Trend-following strategy using MACD with confirmation filter.

    Requires stronger MACD histogram for entry to filter weak signals.

    Args:
        close: Close price series
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        min_histogram: Minimum histogram value for entry (default: 0.5)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
    """
    # Calculate MACD components
    macd_data = calculate_macd(close, fast_period, slow_period, signal_period)
    macd_line = macd_data['macd']
    signal_line = macd_data['signal']
    histogram = macd_data['histogram']

    # Entry: MACD crossover with strong histogram
    crossover = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    strong_signal = histogram > min_histogram
    entries = crossover & strong_signal

    # Exit: MACD crosses below signal (standard exit)
    exits = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))

    return entries, exits
