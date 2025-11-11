"""
Signal Generator Strategies

Provides strategy-specific signal generators for backtesting with vectorbt.
All signal generators follow the standard vectorbt signature:
    fn(close: pd.Series, **kwargs) -> (entries: pd.Series, exits: pd.Series)
"""

from .signal_generators import (
    BaseSignalGenerator,
    MomentumSignalGenerator,
    ValueSignalGenerator,
    CombinedSignalGenerator,
    SignalGeneratorFactory,
)

__all__ = [
    "BaseSignalGenerator",
    "MomentumSignalGenerator",
    "ValueSignalGenerator",
    "CombinedSignalGenerator",
    "SignalGeneratorFactory",
]
