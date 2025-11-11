"""
Signal Generator Implementations

Provides strategy-specific signal generators compatible with vectorbt.
All generators follow the standard signature:
    fn(close: pd.Series, **kwargs) -> (entries: pd.Series, exits: pd.Series)

Author: Spock MCP Server
Date: 2025-10-31
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Callable
import pandas as pd
import numpy as np
from loguru import logger


class BaseSignalGenerator(ABC):
    """
    Abstract base class for signal generators.

    All signal generators must implement generate_signals() with
    vectorbt-compatible signature.
    """

    def __init__(self, parameters: Dict[str, Any]):
        """
        Initialize signal generator with strategy parameters.

        Args:
            parameters: Strategy-specific parameters (e.g., RSI period, MA windows)
        """
        self.parameters = parameters
        logger.debug(
            "signal_generator_init",
            generator=self.__class__.__name__,
            parameters=parameters
        )

    @abstractmethod
    def generate_signals(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate entry and exit signals.

        Args:
            close: Close price series with DatetimeIndex
            **kwargs: Additional parameters (overrides self.parameters)

        Returns:
            (entries, exits): Boolean series for buy/sell signals
        """
        pass

    def __call__(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Make generator callable (vectorbt compatibility).

        Allows usage: signal_generator(close, **kwargs)
        """
        return self.generate_signals(close, **kwargs)


class MomentumSignalGenerator(BaseSignalGenerator):
    """
    Momentum strategy using RSI and moving average crossover.

    Entry Signals:
    - RSI crosses above oversold threshold (default: 30)
    - Fast MA > Slow MA (trend confirmation)

    Exit Signals:
    - RSI crosses below overbought threshold (default: 70)
    - Fast MA < Slow MA (trend reversal)

    Parameters:
        rsi_period: RSI calculation period (default: 14)
        rsi_oversold: RSI oversold threshold (default: 30)
        rsi_overbought: RSI overbought threshold (default: 70)
        ma_fast: Fast MA period (default: 20)
        ma_slow: Slow MA period (default: 50)
    """

    def generate_signals(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate momentum signals based on RSI and MA crossover."""
        # Merge parameters (kwargs override self.parameters)
        params = {**self.parameters, **kwargs}
        rsi_period = params.get('rsi_period', 14)
        rsi_oversold = params.get('rsi_oversold', 30)
        rsi_overbought = params.get('rsi_overbought', 70)
        ma_fast = params.get('ma_fast', 20)
        ma_slow = params.get('ma_slow', 50)

        logger.info(
            "momentum_signal_generation",
            ticker=close.name,
            rows=len(close),
            rsi_period=rsi_period,
            ma_fast=ma_fast,
            ma_slow=ma_slow
        )

        # Calculate RSI
        rsi = self._calculate_rsi(close, rsi_period)

        # Calculate moving averages
        ma_fast_series = close.rolling(ma_fast).mean()
        ma_slow_series = close.rolling(ma_slow).mean()

        # Entry signals: RSI oversold + bullish trend
        rsi_entry = (rsi < rsi_oversold) & (rsi.shift(1) >= rsi_oversold)
        trend_bullish = ma_fast_series > ma_slow_series
        entries = rsi_entry & trend_bullish

        # Exit signals: RSI overbought + bearish trend
        rsi_exit = (rsi > rsi_overbought) & (rsi.shift(1) <= rsi_overbought)
        trend_bearish = ma_fast_series < ma_slow_series
        exits = rsi_exit | trend_bearish

        logger.info(
            "momentum_signals_generated",
            ticker=close.name,
            entry_count=entries.sum(),
            exit_count=exits.sum()
        )

        return entries, exits

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            close: Close price series
            period: RSI period (default: 14)

        Returns:
            RSI series (0-100 scale)
        """
        # Calculate price changes
        delta = close.diff()

        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = -delta.where(delta < 0, 0.0)

        # Calculate exponential moving averages
        avg_gains = gains.ewm(span=period, min_periods=period).mean()
        avg_losses = losses.ewm(span=period, min_periods=period).mean()

        # Calculate RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        # Fill NaN with 50 (neutral)
        rsi = rsi.fillna(50)

        return rsi


class ValueSignalGenerator(BaseSignalGenerator):
    """
    Value strategy placeholder (buy-and-hold).

    This is a temporary implementation until fundamental data is integrated.
    Currently implements a simple buy-and-hold strategy:
    - Enter at the start
    - Hold until the end

    Future Implementation:
    - P/E ratio filtering
    - P/B ratio filtering
    - Dividend yield screening
    - Rebalancing logic

    Parameters:
        None (placeholder)
    """

    def generate_signals(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate value signals (currently buy-and-hold).

        TODO: Integrate fundamental data for proper value screening.
        """
        logger.warning(
            "value_signal_placeholder",
            message="Using buy-and-hold placeholder. Integrate fundamental data for real value strategy.",
            ticker=close.name
        )

        # Buy at the start
        entries = pd.Series(False, index=close.index)
        entries.iloc[0] = True

        # No exits (hold until end)
        exits = pd.Series(False, index=close.index)

        logger.info(
            "value_signals_generated",
            ticker=close.name,
            entry_count=entries.sum(),
            exit_count=exits.sum()
        )

        return entries, exits


class CombinedSignalGenerator(BaseSignalGenerator):
    """
    Combined momentum + value strategy.

    Combines signals from both momentum and value strategies:
    - Entry: Both momentum AND value signals agree
    - Exit: Either momentum OR value signals exit

    This conservative approach reduces false signals but may miss opportunities.

    Parameters:
        Inherits all parameters from MomentumSignalGenerator
    """

    def __init__(self, parameters: Dict[str, Any]):
        """Initialize with sub-generators."""
        super().__init__(parameters)
        self.momentum_gen = MomentumSignalGenerator(parameters)
        self.value_gen = ValueSignalGenerator(parameters)

    def generate_signals(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """Generate combined momentum + value signals."""
        logger.info(
            "combined_signal_generation",
            ticker=close.name,
            rows=len(close)
        )

        # Get momentum signals
        momentum_entries, momentum_exits = self.momentum_gen.generate_signals(close, **kwargs)

        # Get value signals
        value_entries, value_exits = self.value_gen.generate_signals(close, **kwargs)

        # Combined entry: Both strategies agree (AND logic)
        entries = momentum_entries & value_entries

        # Combined exit: Either strategy exits (OR logic)
        exits = momentum_exits | value_exits

        logger.info(
            "combined_signals_generated",
            ticker=close.name,
            entry_count=entries.sum(),
            exit_count=exits.sum(),
            momentum_entries=momentum_entries.sum(),
            value_entries=value_entries.sum()
        )

        return entries, exits


class FundamentalSignalGenerator(BaseSignalGenerator):
    """
    Fundamental quality + growth strategy with annual rebalancing.

    Screens stocks by fundamental criteria:
    - High ROE (Return on Equity) - profitability
    - Low debt-to-equity ratio - financial health
    - High net income growth YOY - profit growth
    - High revenue growth YOY - sales growth

    Strategy Logic:
    1. Screen universe by fundamental criteria
    2. Select top N stocks by composite score
    3. Allocate equal weight to selected stocks
    4. Rebalance annually (or custom frequency)

    Parameters:
        roe_min: Minimum ROE threshold (%) (default: 15.0)
        debt_to_equity_max: Maximum debt-to-equity ratio (%) (default: 100.0)
        net_income_growth_min: Minimum net income growth YOY (%) (default: 10.0)
        revenue_growth_min: Minimum revenue growth YOY (%) (default: 10.0)
        require_growth: If True, YOY growth is required; if False, optional (default: False)
        top_n: Number of stocks to select (default: 10)
        rebalance_freq_days: Days between rebalances (default: 252 for annual)
        region: Market region (default: 'KR')

    Example:
        >>> generator = FundamentalSignalGenerator({
        ...     'roe_min': 15.0,
        ...     'debt_to_equity_max': 100.0,
        ...     'net_income_growth_min': 10.0,
        ...     'revenue_growth_min': 10.0,
        ...     'top_n': 10,
        ...     'rebalance_freq_days': 252
        ... })
        >>> entries, exits = generator(close_prices)
    """

    def __init__(self, parameters: Dict[str, Any]):
        """Initialize with strategy parameters."""
        super().__init__(parameters)

        # Internal state for rebalancing
        self._last_rebalance_date = None
        self._current_holdings = set()

        logger.info(
            "fundamental_signal_generator_init",
            roe_min=parameters.get('roe_min', 15.0),
            debt_max=parameters.get('debt_to_equity_max', 100.0),
            ni_growth_min=parameters.get('net_income_growth_min', 10.0),
            revenue_growth_min=parameters.get('revenue_growth_min', 10.0),
            top_n=parameters.get('top_n', 10),
            rebalance_freq_days=parameters.get('rebalance_freq_days', 252)
        )

    def generate_signals(
        self,
        close: pd.Series,
        **kwargs
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate entry/exit signals based on fundamental screening.

        Args:
            close: Close price series with DatetimeIndex
            **kwargs: Additional parameters (overrides self.parameters)

        Returns:
            (entries, exits): Boolean series for buy/sell signals
        """
        # Merge parameters
        params = {**self.parameters, **kwargs}
        rebalance_freq_days = params.get('rebalance_freq_days', 252)

        # Get current date
        current_date = close.index[-1] if len(close) > 0 else pd.Timestamp.now()

        # Initialize signals
        entries = pd.Series(False, index=close.index)
        exits = pd.Series(False, index=close.index)

        # Check if rebalancing is needed
        if self._should_rebalance(current_date, rebalance_freq_days):
            logger.info(
                "fundamental_rebalancing",
                date=current_date.date(),
                last_rebalance=self._last_rebalance_date.date() if self._last_rebalance_date else None
            )

            # Get ticker from close series name
            ticker = close.name if close.name else None

            if ticker:
                # Screen by fundamentals and determine if this ticker passes
                passes_screening = self._screen_ticker(
                    ticker=ticker,
                    as_of_date=current_date.date(),
                    params=params
                )

                # Generate signals based on screening result
                if passes_screening and ticker not in self._current_holdings:
                    # Entry signal: ticker passes screening and not already held
                    entries.iloc[-1] = True
                    self._current_holdings.add(ticker)
                    logger.info(
                        "fundamental_entry_signal",
                        ticker=ticker,
                        date=current_date.date()
                    )
                elif not passes_screening and ticker in self._current_holdings:
                    # Exit signal: ticker no longer passes screening
                    exits.iloc[-1] = True
                    self._current_holdings.discard(ticker)
                    logger.info(
                        "fundamental_exit_signal",
                        ticker=ticker,
                        date=current_date.date()
                    )

            # Update last rebalance date
            self._last_rebalance_date = current_date

        logger.info(
            "fundamental_signals_generated",
            ticker=close.name,
            entry_count=entries.sum(),
            exit_count=exits.sum(),
            current_holdings=len(self._current_holdings)
        )

        return entries, exits

    def _should_rebalance(self, current_date: pd.Timestamp, freq_days: int) -> bool:
        """Check if rebalancing is needed."""
        if self._last_rebalance_date is None:
            return True

        days_since_rebalance = (current_date - self._last_rebalance_date).days
        return days_since_rebalance >= freq_days

    def _screen_ticker(
        self,
        ticker: str,
        as_of_date: pd.Timestamp,
        params: Dict[str, Any]
    ) -> bool:
        """
        Screen ticker by fundamental criteria.

        Args:
            ticker: Stock ticker symbol
            as_of_date: Date for fundamental data
            params: Strategy parameters

        Returns:
            True if ticker passes all screening criteria
        """
        region = params.get('region', 'KR')
        roe_min = params.get('roe_min', 15.0)
        debt_max = params.get('debt_to_equity_max', 100.0)
        ni_growth_min = params.get('net_income_growth_min', 10.0)
        revenue_growth_min = params.get('revenue_growth_min', 10.0)
        require_growth = params.get('require_growth', False)  # Flexible mode by default

        try:
            import psycopg2
            import os

            # Connect to PostgreSQL
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()

            # Query fundamental data (most recent fiscal year)
            cursor.execute("""
                WITH latest_fundamentals AS (
                    SELECT
                        current.ticker,
                        current.fiscal_year AS current_year,
                        current.net_income,
                        current.total_equity,
                        current.total_liabilities,
                        current.revenue AS current_revenue,
                        previous.net_income AS prev_net_income,
                        previous.revenue AS prev_revenue
                    FROM ticker_fundamentals current
                    LEFT JOIN ticker_fundamentals previous
                        ON current.ticker = previous.ticker
                        AND current.region = previous.region
                        AND current.fiscal_year = previous.fiscal_year + 1
                    WHERE current.ticker = %s
                      AND current.region = %s
                    ORDER BY current.fiscal_year DESC
                    LIMIT 1
                )
                SELECT
                    ticker,
                    current_year,
                    -- ROE (%)
                    CASE
                        WHEN total_equity > 0 THEN (net_income / total_equity) * 100
                        ELSE NULL
                    END AS roe,
                    -- Debt-to-Equity (%)
                    CASE
                        WHEN total_equity > 0 THEN (total_liabilities / total_equity) * 100
                        ELSE NULL
                    END AS debt_to_equity,
                    -- Net Income Growth YOY (%)
                    CASE
                        WHEN prev_net_income IS NOT NULL AND prev_net_income != 0
                        THEN ((net_income - prev_net_income) / ABS(prev_net_income)) * 100
                        ELSE NULL
                    END AS ni_growth_yoy,
                    -- Revenue Growth YOY (%)
                    CASE
                        WHEN prev_revenue IS NOT NULL AND prev_revenue > 0
                        THEN ((current_revenue - prev_revenue) / prev_revenue) * 100
                        ELSE NULL
                    END AS revenue_growth_yoy
                FROM latest_fundamentals;
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(
                    "fundamental_screening_no_data",
                    ticker=ticker,
                    region=region
                )
                return False

            # Unpack results
            _, _, roe, debt_to_equity, ni_growth, revenue_growth = result

            # Check if all criteria pass
            # Flexible mode (default): YOY growth is optional (bonus if present)
            # Strict mode (require_growth=True): All 4 criteria required
            if require_growth:
                # Strict mode: All criteria must be satisfied
                passes = all([
                    roe is not None and roe >= roe_min,
                    debt_to_equity is not None and debt_to_equity <= debt_max,
                    ni_growth is not None and ni_growth >= ni_growth_min,
                    revenue_growth is not None and revenue_growth >= revenue_growth_min
                ])
            else:
                # Flexible mode: ROE + Debt required, YOY optional
                passes = all([
                    roe is not None and roe >= roe_min,
                    debt_to_equity is not None and debt_to_equity <= debt_max,
                    ni_growth is None or ni_growth >= ni_growth_min,
                    revenue_growth is None or revenue_growth >= revenue_growth_min
                ])

            logger.debug(
                "fundamental_screening_result",
                ticker=ticker,
                passes=passes,
                roe=f"{roe:.2f}%" if roe else None,
                debt_to_equity=f"{debt_to_equity:.2f}%" if debt_to_equity else None,
                ni_growth=f"{ni_growth:.2f}%" if ni_growth else None,
                revenue_growth=f"{revenue_growth:.2f}%" if revenue_growth else None,
                criteria={
                    'roe_min': f"{roe_min}%",
                    'debt_max': f"{debt_max}%",
                    'ni_growth_min': f"{ni_growth_min}%",
                    'revenue_growth_min': f"{revenue_growth_min}%"
                }
            )

            return passes

        except Exception as e:
            logger.error(
                "fundamental_screening_error",
                ticker=ticker,
                error=str(e)
            )
            return False


class SignalGeneratorFactory:
    """
    Factory for creating strategy-specific signal generators.

    Ensures all generators match vectorbt signature and provides
    centralized strategy registration.

    Example:
        >>> factory = SignalGeneratorFactory()
        >>> generator = factory.create('momentum', {'rsi_period': 14})
        >>> entries, exits = generator(close_prices)
    """

    # Strategy registry
    _strategies = {
        'momentum': MomentumSignalGenerator,
        'value': ValueSignalGenerator,
        'momentum_value': CombinedSignalGenerator,
        'fundamental_quality_growth': FundamentalSignalGenerator,
    }

    @classmethod
    def create(
        cls,
        strategy_type: str,
        parameters: Dict[str, Any] | None = None
    ) -> BaseSignalGenerator:
        """
        Create signal generator for strategy type.

        Args:
            strategy_type: Strategy name (momentum, value, momentum_value)
            parameters: Strategy-specific parameters (optional)

        Returns:
            Signal generator instance (callable)

        Raises:
            ValueError: If strategy_type is not registered
        """
        if strategy_type not in cls._strategies:
            raise ValueError(
                f"Unknown strategy type: {strategy_type}. "
                f"Available: {list(cls._strategies.keys())}"
            )

        generator_class = cls._strategies[strategy_type]
        generator = generator_class(parameters or {})

        logger.info(
            "signal_generator_created",
            strategy_type=strategy_type,
            generator_class=generator_class.__name__,
            parameters=parameters
        )

        return generator

    @classmethod
    def register_strategy(
        cls,
        name: str,
        generator_class: type[BaseSignalGenerator]
    ) -> None:
        """
        Register custom strategy.

        Args:
            name: Strategy name
            generator_class: Signal generator class (must inherit BaseSignalGenerator)

        Raises:
            ValueError: If generator_class doesn't inherit BaseSignalGenerator
        """
        if not issubclass(generator_class, BaseSignalGenerator):
            raise ValueError(
                f"{generator_class.__name__} must inherit from BaseSignalGenerator"
            )

        cls._strategies[name] = generator_class
        logger.info(
            "strategy_registered",
            name=name,
            generator_class=generator_class.__name__
        )

    @classmethod
    def list_strategies(cls) -> list[str]:
        """List available strategies."""
        return list(cls._strategies.keys())
