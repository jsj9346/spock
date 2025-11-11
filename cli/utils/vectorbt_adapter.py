"""
vectorbt adapter for fast backtesting.

Provides a simplified interface to vectorbt for portfolio simulation
with support for multiple strategies and performance metrics.
"""

from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
import pandas as pd
import numpy as np

try:
    import vectorbt as vbt
    VBT_AVAILABLE = True
except ImportError:
    VBT_AVAILABLE = False
    print("Warning: vectorbt not installed. Run: pip install vectorbt")


class VectorbtAdapter:
    """
    Adapter for vectorbt backtesting engine.

    Features:
    - Fast vectorized backtesting (100x faster than event-driven)
    - Multiple strategy support
    - Portfolio-level metrics (Sharpe, drawdown, returns)
    - Transaction cost modeling
    - Position sizing strategies

    Usage:
        adapter = VectorbtAdapter()
        pf = adapter.run_backtest(
            prices=df['close'],
            signals=signals,
            initial_cash=10000000
        )
        metrics = adapter.get_metrics(pf)
    """

    def __init__(self):
        """Initialize vectorbt adapter."""
        if not VBT_AVAILABLE:
            raise ImportError(
                "vectorbt is required for this adapter. "
                "Install with: pip install vectorbt"
            )

    def run_backtest(
        self,
        prices: pd.DataFrame,
        signals: pd.DataFrame,
        initial_cash: float = 10_000_000,
        commission: float = 0.0015,
        slippage: float = 0.001,
        freq: str = '1D'
    ) -> Any:
        """
        Run vectorized backtest.

        Args:
            prices: DataFrame with prices (MultiIndex: date, ticker or just date)
            signals: DataFrame with buy/sell signals (1=buy, -1=sell, 0=hold)
            initial_cash: Initial portfolio cash (default: 10M KRW)
            commission: Commission rate (default: 0.15%)
            slippage: Slippage rate (default: 0.1%)
            freq: Data frequency (default: 1D for daily)

        Returns:
            vectorbt Portfolio object

        Example:
            prices = df['close']
            signals = pd.DataFrame(index=prices.index, columns=prices.columns)
            signals[:] = 0  # Initialize to hold
            signals.iloc[10, 0] = 1  # Buy signal
            signals.iloc[20, 0] = -1  # Sell signal

            pf = adapter.run_backtest(prices, signals)
        """
        # Create portfolio from signals
        pf = vbt.Portfolio.from_signals(
            close=prices,
            entries=signals > 0,  # Buy signals
            exits=signals < 0,     # Sell signals
            init_cash=initial_cash,
            fees=commission,
            slippage=slippage,
            freq=freq
        )

        return pf

    def run_backtest_from_orders(
        self,
        prices: pd.DataFrame,
        size: pd.DataFrame,
        initial_cash: float = 10_000_000,
        commission: float = 0.0015,
        slippage: float = 0.001,
        freq: str = '1D'
    ) -> Any:
        """
        Run backtest from order sizes (more flexible).

        Args:
            prices: DataFrame with prices
            size: DataFrame with order sizes (positive=buy, negative=sell, 0=hold)
            initial_cash: Initial portfolio cash
            commission: Commission rate
            slippage: Slippage rate
            freq: Data frequency

        Returns:
            vectorbt Portfolio object
        """
        pf = vbt.Portfolio.from_orders(
            close=prices,
            size=size,
            init_cash=initial_cash,
            fees=commission,
            slippage=slippage,
            freq=freq
        )

        return pf

    def get_metrics(
        self,
        portfolio: Any,
        benchmark_returns: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        Extract performance metrics from portfolio.

        Args:
            portfolio: vectorbt Portfolio object
            benchmark_returns: Optional benchmark returns for comparison

        Returns:
            Dictionary of performance metrics

        Metrics:
            - total_return: Total return percentage
            - annualized_return: Annualized return
            - sharpe_ratio: Risk-adjusted return
            - max_drawdown: Maximum drawdown percentage
            - win_rate: Percentage of winning trades
            - profit_factor: Gross profit / gross loss
            - total_trades: Number of trades
            - final_value: Final portfolio value
        """
        stats = portfolio.stats()

        metrics = {
            'total_return': stats['Total Return [%]'],
            'annualized_return': stats.get('Annual Return [%]', 0),
            'sharpe_ratio': stats.get('Sharpe Ratio', 0),
            'max_drawdown': stats['Max Drawdown [%]'],
            'win_rate': stats.get('Win Rate [%]', 0),
            'profit_factor': stats.get('Profit Factor', 0),
            'total_trades': stats.get('Total Trades', 0),
            'final_value': stats['End Value'],
        }

        # Add benchmark comparison if provided
        if benchmark_returns is not None:
            pf_returns = portfolio.returns()
            alpha = pf_returns.mean() - benchmark_returns.mean()
            metrics['alpha'] = alpha * 252  # Annualized

        return metrics

    def get_returns(self, portfolio: Any) -> pd.Series:
        """
        Get portfolio returns series.

        Args:
            portfolio: vectorbt Portfolio object

        Returns:
            Series of daily returns
        """
        return portfolio.returns()

    def get_cumulative_returns(self, portfolio: Any) -> pd.Series:
        """
        Get cumulative returns series.

        Args:
            portfolio: vectorbt Portfolio object

        Returns:
            Series of cumulative returns
        """
        return portfolio.cumulative_returns()

    def get_drawdowns(self, portfolio: Any) -> pd.Series:
        """
        Get drawdowns series.

        Args:
            portfolio: vectorbt Portfolio object

        Returns:
            Series of drawdowns (negative values)
        """
        return portfolio.drawdowns()

    def get_trades(self, portfolio: Any) -> pd.DataFrame:
        """
        Get trade details.

        Args:
            portfolio: vectorbt Portfolio object

        Returns:
            DataFrame with trade information (entry, exit, pnl, etc.)
        """
        return portfolio.trades.records_readable

    def optimize_parameters(
        self,
        prices: pd.DataFrame,
        strategy_func: Callable,
        param_grid: Dict[str, List[Any]],
        initial_cash: float = 10_000_000,
        commission: float = 0.0015,
        metric: str = 'sharpe_ratio'
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters using grid search.

        Args:
            prices: DataFrame with prices
            strategy_func: Function that generates signals given parameters
                         Signature: strategy_func(prices, **params) -> signals
            param_grid: Dictionary of parameter names and values to try
            initial_cash: Initial portfolio cash
            commission: Commission rate
            metric: Metric to optimize ('sharpe_ratio', 'total_return', etc.)

        Returns:
            Dictionary with best parameters and performance

        Example:
            def ma_crossover(prices, short_window, long_window):
                signals = pd.DataFrame(index=prices.index, columns=prices.columns)
                signals[:] = 0
                short_ma = prices.rolling(short_window).mean()
                long_ma = prices.rolling(long_window).mean()
                signals[short_ma > long_ma] = 1
                signals[short_ma < long_ma] = -1
                return signals

            param_grid = {
                'short_window': [5, 10, 20],
                'long_window': [20, 50, 100]
            }

            best = adapter.optimize_parameters(prices, ma_crossover, param_grid)
        """
        import itertools

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))

        best_score = -np.inf
        best_params = None
        best_metrics = None

        # Test each combination
        for param_combo in param_combinations:
            params = dict(zip(param_names, param_combo))

            try:
                # Generate signals
                signals = strategy_func(prices, **params)

                # Run backtest
                pf = self.run_backtest(
                    prices=prices,
                    signals=signals,
                    initial_cash=initial_cash,
                    commission=commission
                )

                # Get metrics
                metrics = self.get_metrics(pf)

                # Check if better
                score = metrics.get(metric, -np.inf)
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_metrics = metrics

            except Exception as e:
                print(f"Warning: Failed to test params {params}: {e}")
                continue

        return {
            'best_params': best_params,
            'best_score': best_score,
            'best_metrics': best_metrics
        }

    def plot_performance(
        self,
        portfolio: Any,
        title: str = "Portfolio Performance",
        show: bool = True
    ):
        """
        Plot portfolio performance.

        Args:
            portfolio: vectorbt Portfolio object
            title: Plot title
            show: Whether to show the plot immediately
        """
        fig = portfolio.plot(title=title)

        if show:
            fig.show()

        return fig


# Convenience functions
def create_simple_strategy(
    prices: pd.DataFrame,
    buy_condition: pd.DataFrame,
    sell_condition: pd.DataFrame
) -> pd.DataFrame:
    """
    Create signals from buy/sell conditions.

    Args:
        prices: DataFrame with prices
        buy_condition: Boolean DataFrame (True = buy signal)
        sell_condition: Boolean DataFrame (True = sell signal)

    Returns:
        DataFrame with signals (1=buy, -1=sell, 0=hold)
    """
    # Explicit int8 dtype to ensure vectorbt/numba compatibility
    signals = pd.DataFrame(0, index=prices.index, columns=prices.columns, dtype=np.int8)
    signals[buy_condition] = 1
    signals[sell_condition] = -1
    return signals


def create_ma_crossover_signals(
    prices: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60
) -> pd.DataFrame:
    """
    Create moving average crossover signals.

    Args:
        prices: DataFrame with prices
        short_window: Short MA window
        long_window: Long MA window

    Returns:
        DataFrame with signals
    """
    short_ma = prices.rolling(short_window).mean()
    long_ma = prices.rolling(long_window).mean()

    buy_condition = short_ma > long_ma
    sell_condition = short_ma < long_ma

    return create_simple_strategy(prices, buy_condition, sell_condition)


if __name__ == '__main__':
    # Test the adapter
    print("Testing vectorbt adapter...")

    # Create sample data
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
    prices = pd.DataFrame({
        'AAPL': np.random.randn(len(dates)).cumsum() + 100,
        'GOOGL': np.random.randn(len(dates)).cumsum() + 200
    }, index=dates)

    # Create simple buy-and-hold signals
    signals = pd.DataFrame(0, index=prices.index, columns=prices.columns)
    signals.iloc[0, :] = 1  # Buy at start
    signals.iloc[-1, :] = -1  # Sell at end

    # Test backtest
    adapter = VectorbtAdapter()
    pf = adapter.run_backtest(prices, signals)

    # Get metrics
    metrics = adapter.get_metrics(pf)
    print("\nPerformance Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value:.2f}")

    # Test MA crossover
    print("\nTesting MA crossover strategy...")
    ma_signals = create_ma_crossover_signals(prices, short_window=10, long_window=30)
    pf_ma = adapter.run_backtest(prices, ma_signals)
    metrics_ma = adapter.get_metrics(pf_ma)
    print("\nMA Crossover Metrics:")
    for key, value in metrics_ma.items():
        print(f"  {key}: {value:.2f}")
