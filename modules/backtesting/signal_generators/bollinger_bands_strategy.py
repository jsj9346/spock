"""
Bollinger Bands Signal Generator

Generates entry/exit signals based on price interaction with Bollinger Bands.

Strategy Logic:
    - Entry: Price crosses below lower band (oversold, mean reversion)
    - Exit: Price crosses above middle band (return to mean)

Parameters:
    - period: Moving average period (default: 20)
    - num_std: Number of standard deviations (default: 2.0)

Usage:
    from modules.backtesting.signal_generators.bollinger_bands_strategy import bb_signal_generator

    entries, exits = bb_signal_generator(
        close=df['close'],
        period=20,
        num_std=2.0
    )
"""

import pandas as pd
from typing import Tuple, Dict


def calculate_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Dict[str, pd.Series]:
    """
    Calculate Bollinger Bands.

    Bollinger Bands consist of a middle band (SMA) and upper/lower bands
    (SMA ± num_std * standard deviation).

    Args:
        close: Close price series
        period: Moving average period (default: 20)
        num_std: Number of standard deviations for bands (default: 2.0)

    Returns:
        Dictionary with keys:
            'upper': Upper band (SMA + num_std * std)
            'middle': Middle band (SMA)
            'lower': Lower band (SMA - num_std * std)
            'bandwidth': Band width (upper - lower)
            'percent_b': %B indicator ((price - lower) / (upper - lower))

    Formula:
        Middle Band = SMA(close, period)
        Upper Band = Middle + (num_std * StdDev)
        Lower Band = Middle - (num_std * StdDev)
    """
    # Calculate middle band (SMA)
    middle_band = close.rolling(window=period).mean()

    # Calculate standard deviation
    std_dev = close.rolling(window=period).std()

    # Calculate upper and lower bands
    upper_band = middle_band + (num_std * std_dev)
    lower_band = middle_band - (num_std * std_dev)

    # Calculate bandwidth (volatility measure)
    bandwidth = upper_band - lower_band

    # Calculate %B (position within bands)
    # %B = 0 when price at lower band
    # %B = 1 when price at upper band
    # %B > 1 when price above upper band
    # %B < 0 when price below lower band
    percent_b = (close - lower_band) / (upper_band - lower_band)

    return {
        'upper': upper_band,
        'middle': middle_band,
        'lower': lower_band,
        'bandwidth': bandwidth,
        'percent_b': percent_b
    }


def bb_signal_generator(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Generate Bollinger Bands mean reversion signals.

    Entry Signal:
        Price crosses below lower band (oversold condition)

    Exit Signal:
        Price crosses above middle band (mean reversion complete)

    Args:
        close: Close price series (pd.Series with DatetimeIndex)
        period: Moving average period (default: 20)
        num_std: Number of standard deviations (default: 2.0)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
            entries: True when price crosses below lower band
            exits: True when price crosses above middle band

    Example:
        >>> entries, exits = bb_signal_generator(df['close'], period=20)
        >>> print(f"Entry signals: {entries.sum()}")
        >>> print(f"Exit signals: {exits.sum()}")
    """
    # Calculate Bollinger Bands
    bb_data = calculate_bollinger_bands(close, period, num_std)
    lower_band = bb_data['lower']
    middle_band = bb_data['middle']

    # Entry: Price crosses below lower band
    # (Price is now below lower band AND was above/at lower band in previous period)
    entries = (close < lower_band) & (close.shift(1) >= lower_band.shift(1))

    # Exit: Price crosses above middle band
    # (Price is now above middle band AND was below/at middle band in previous period)
    exits = (close > middle_band) & (close.shift(1) <= middle_band.shift(1))

    return entries, exits


def bb_breakout_signal_generator(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Bollinger Bands breakout strategy (trend-following).

    Entry Signal:
        Price breaks above upper band (strong momentum)

    Exit Signal:
        Price crosses below middle band (momentum fading)

    Args:
        close: Close price series
        period: Moving average period (default: 20)
        num_std: Number of standard deviations (default: 2.0)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
    """
    # Calculate Bollinger Bands
    bb_data = calculate_bollinger_bands(close, period, num_std)
    upper_band = bb_data['upper']
    middle_band = bb_data['middle']

    # Entry: Price breaks above upper band
    entries = (close > upper_band) & (close.shift(1) <= upper_band.shift(1))

    # Exit: Price crosses below middle band
    exits = (close < middle_band) & (close.shift(1) >= middle_band.shift(1))

    return entries, exits


def bb_squeeze_signal_generator(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
    squeeze_threshold: float = 0.02
) -> Tuple[pd.Series, pd.Series]:
    """
    Bollinger Band squeeze strategy (volatility breakout).

    Entry Signal:
        Bandwidth expands after squeeze (volatility returning)
        Combined with price crossing above middle band

    Exit Signal:
        Bandwidth contracts significantly (volatility decreasing)

    Args:
        close: Close price series
        period: Moving average period (default: 20)
        num_std: Number of standard deviations (default: 2.0)
        squeeze_threshold: Bandwidth threshold for squeeze (default: 0.02 = 2%)

    Returns:
        (entries, exits): Tuple of boolean pd.Series
    """
    # Calculate Bollinger Bands
    bb_data = calculate_bollinger_bands(close, period, num_std)
    middle_band = bb_data['middle']
    bandwidth = bb_data['bandwidth']

    # Normalize bandwidth by price
    bandwidth_pct = bandwidth / middle_band

    # Detect squeeze: bandwidth < threshold
    is_squeezed = bandwidth_pct < squeeze_threshold

    # Entry: Squeeze ending (bandwidth expanding) + price momentum
    # Previous bar was squeezed AND current bar is not squeezed
    was_squeezed = is_squeezed.shift(1).fillna(False)
    is_not_squeezed = ~is_squeezed
    squeeze_ending = was_squeezed & is_not_squeezed
    price_momentum = close > middle_band
    entries = squeeze_ending & price_momentum

    # Exit: New squeeze forming (volatility contracting)
    # Previous bar was not squeezed AND current bar is squeezed
    was_not_squeezed = (~was_squeezed).fillna(True)
    exits = was_not_squeezed & is_squeezed

    return entries, exits


def bb_dual_threshold_signal_generator(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
    entry_percent_b: float = 0.0,
    exit_percent_b: float = 0.5
) -> Tuple[pd.Series, pd.Series]:
    """
    Advanced Bollinger Bands strategy using %B indicator.

    Uses %B (percent B) to determine position within bands.

    Entry Signal:
        %B drops below entry_percent_b (default: 0 = at lower band)

    Exit Signal:
        %B rises above exit_percent_b (default: 0.5 = at middle band)

    Args:
        close: Close price series
        period: Moving average period (default: 20)
        num_std: Number of standard deviations (default: 2.0)
        entry_percent_b: %B threshold for entry (default: 0.0)
        exit_percent_b: %B threshold for exit (default: 0.5)

    Returns:
        (entries, exits): Tuple of boolean pd.Series

    %B Values:
        1.0 = At upper band
        0.5 = At middle band
        0.0 = At lower band
        >1.0 = Above upper band
        <0.0 = Below lower band
    """
    # Calculate Bollinger Bands
    bb_data = calculate_bollinger_bands(close, period, num_std)
    percent_b = bb_data['percent_b']

    # Entry: %B crosses below entry threshold
    entries = (percent_b < entry_percent_b) & (percent_b.shift(1) >= entry_percent_b)

    # Exit: %B crosses above exit threshold
    exits = (percent_b > exit_percent_b) & (percent_b.shift(1) <= exit_percent_b)

    return entries, exits
