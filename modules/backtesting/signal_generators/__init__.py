"""
Signal Generators Module

Reusable trading signal generators for vectorbt backtesting.

Signal Generator Contract:
    All signal generators must follow this signature:

    def signal_generator(
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        '''
        Generate entry and exit signals.

        Args:
            close: Close price series (pd.Series with DatetimeIndex)
            **kwargs: Strategy-specific parameters

        Returns:
            (entries, exits): Tuple of boolean pd.Series
                entries: True when long position should be opened
                exits: True when long position should be closed
        '''
        ...
        return entries, exits

Available Generators:
    - Momentum Strategies: MA crossover, RSI, dual momentum
    - Mean Reversion: Bollinger Bands, RSI mean reversion
    - Multi-Factor: Combined factor signals

Design Philosophy:
    - Pure functions (no side effects)
    - Vectorized operations (pandas/numpy)
    - Consistent API across all generators
    - Easy to test and validate
    - Composable for multi-factor strategies
"""

__version__ = '0.1.0'

__all__ = []  # Populated as generators are implemented
