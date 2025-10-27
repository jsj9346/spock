"""
Momentum Strategy Example with Korean Stocks

Demonstrates complete backtesting workflow:
1. Load historical data from PostgreSQL
2. Calculate momentum signals (12-month return ranking)
3. Run vectorbt backtest with realistic costs
4. Analyze performance metrics
5. Visualize results

Strategy:
- Universe: Top 10 KOSPI stocks by market cap
- Signal: Buy top 3 stocks with highest 12-month momentum
- Rebalance: Monthly
- Position sizing: Equal weight
- Costs: KIS commission (0.015%), slippage (0.05%), tax (0.23%)

Usage:
    python3 examples/backtest/momentum_strategy_example.py
    python3 examples/backtest/momentum_strategy_example.py --start 2020-01-01 --end 2024-12-31
    python3 examples/backtest/momentum_strategy_example.py --tickers 005930 000660 035420
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.common.metrics import PerformanceMetrics


class MomentumStrategy:
    """
    12-Month Momentum Strategy Implementation.

    Academic Foundation:
    - Jegadeesh & Titman (1993): "Returns to Buying Winners and Selling Losers"
    - Fama & French (2012): Momentum factor in asset pricing

    Implementation:
    - Lookback: 12 months (252 trading days)
    - Holding period: 1 month (21 trading days)
    - Ranking: Top N stocks by momentum
    """

    def __init__(
        self,
        lookback_periods: int = 252,  # 12 months
        rebalance_periods: int = 21,   # 1 month
        top_n_stocks: int = 3,
        skip_most_recent: int = 21     # Skip last month (reversal)
    ):
        self.lookback_periods = lookback_periods
        self.rebalance_periods = rebalance_periods
        self.top_n_stocks = top_n_stocks
        self.skip_most_recent = skip_most_recent

        logger.info(f"MomentumStrategy initialized: lookback={lookback_periods}d, "
                   f"rebalance={rebalance_periods}d, top_n={top_n_stocks}")

    def calculate_momentum(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate momentum score for each stock.

        Momentum = (Price[t] - Price[t-252]) / Price[t-252]
        Skip most recent month to avoid short-term reversal.

        Args:
            prices: DataFrame with close prices (columns=tickers, index=dates)

        Returns:
            DataFrame with momentum scores
        """
        # Shift to skip most recent period
        shifted_prices = prices.shift(self.skip_most_recent)

        # Calculate momentum: return over lookback period
        momentum = shifted_prices.pct_change(periods=self.lookback_periods)

        return momentum

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy signals based on momentum ranking.

        Buy top N stocks by momentum, hold for rebalance period.

        Args:
            prices: DataFrame with close prices

        Returns:
            DataFrame with boolean signals (True=buy, False=no position)
        """
        momentum = self.calculate_momentum(prices)

        # Rank stocks by momentum (higher is better)
        # -1 = best, -2 = second best, etc.
        momentum_ranks = momentum.rank(axis=1, ascending=False, method='first')

        # Buy top N stocks
        signals = momentum_ranks <= self.top_n_stocks

        # Apply rebalancing: hold signals for rebalance_periods
        # This prevents daily rebalancing (high turnover)
        rebalanced_signals = pd.DataFrame(
            False,
            index=signals.index,
            columns=signals.columns
        )

        for i in range(0, len(signals), self.rebalance_periods):
            # Get signal at rebalance date
            rebalance_signal = signals.iloc[i]

            # Hold this signal for next rebalance_periods days
            end_idx = min(i + self.rebalance_periods, len(signals))
            rebalanced_signals.iloc[i:end_idx] = rebalance_signal.values

        return rebalanced_signals

    def run_backtest(
        self,
        data: dict,
        initial_capital: float = 100_000_000,
        commission: float = 0.00015,
        slippage: float = 0.0005
    ) -> dict:
        """
        Run momentum strategy backtest.

        Args:
            data: Dictionary of OHLCV DataFrames {ticker: df}
            initial_capital: Starting capital (default: 100M KRW)
            commission: Commission rate (default: 0.015%)
            slippage: Slippage rate (default: 0.05%)

        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Running backtest: {len(data)} stocks, capital={initial_capital:,.0f}")

        # Combine close prices
        close_prices = pd.DataFrame({
            ticker: df['close'] for ticker, df in data.items()
        })

        # Generate signals
        signals = self.generate_signals(close_prices)

        logger.info(f"Generated signals: {signals.sum().sum()} buy signals across all dates")

        # Run vectorbt backtest
        adapter = VectorBTAdapter(
            initial_capital=initial_capital,
            commission=commission,
            slippage=slippage
        )

        # Equal weight for selected stocks
        portfolio = adapter.run_portfolio_backtest(
            data=data,
            signals={ticker: signals[ticker] for ticker in signals.columns},
            size_type='percent',
            size=1.0 / self.top_n_stocks  # Equal weight among top N
        )

        # Calculate metrics
        metrics = adapter.calculate_metrics(portfolio)

        # Extract cumulative returns
        cum_returns = metrics['cumulative_returns']

        results = {
            'portfolio': portfolio,
            'metrics': metrics,
            'signals': signals,
            'cumulative_returns': cum_returns,
            'close_prices': close_prices
        }

        return results

    def print_results(self, results: dict):
        """Print formatted backtest results"""
        metrics = results['metrics']

        # Extract values (handle Series)
        total_return = metrics['total_return']
        if isinstance(total_return, pd.Series):
            total_return = total_return.iloc[0]

        sharpe = metrics['sharpe_ratio']
        if isinstance(sharpe, pd.Series):
            sharpe = sharpe.iloc[0]

        sortino = metrics['sortino_ratio']
        if isinstance(sortino, pd.Series):
            sortino = sortino.iloc[0]

        calmar = metrics['calmar_ratio']
        if isinstance(calmar, pd.Series):
            calmar = calmar.iloc[0]

        max_dd = metrics['max_drawdown']
        if isinstance(max_dd, pd.Series):
            max_dd = max_dd.iloc[0]

        ann_return = metrics['annualized_return']
        if isinstance(ann_return, pd.Series):
            ann_return = ann_return.iloc[0]

        volatility = metrics['volatility']
        if isinstance(volatility, pd.Series):
            volatility = volatility.iloc[0]

        print("\n" + "=" * 80)
        print("MOMENTUM STRATEGY BACKTEST RESULTS")
        print("=" * 80)

        print(f"\n📊 Performance Metrics:")
        print(f"  Total Return:         {total_return:>10.2%}")
        print(f"  Annualized Return:    {ann_return:>10.2%}")
        print(f"  Annualized Volatility:{volatility:>10.2%}")
        print(f"  Sharpe Ratio:         {sharpe:>10.2f}")
        print(f"  Sortino Ratio:        {sortino:>10.2f}")
        print(f"  Calmar Ratio:         {calmar:>10.2f}")
        print(f"  Max Drawdown:         {max_dd:>10.2%}")

        print(f"\n📈 Trade Statistics:")
        print(f"  Total Trades:         {metrics['total_trades']:>10,}")
        print(f"  Win Rate:             {metrics['win_rate']:>10.2%}")
        print(f"  Profit Factor:        {metrics['profit_factor']:>10.2f}")

        # Signal statistics
        signals = results['signals']
        n_signals = signals.sum().sum()
        n_days = len(signals)
        avg_positions = n_signals / n_days

        print(f"\n🎯 Strategy Statistics:")
        print(f"  Total Buy Signals:    {n_signals:>10,.0f}")
        print(f"  Average Positions:    {avg_positions:>10.1f} stocks/day")
        print(f"  Backtest Period:      {n_days:>10,} days")


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Run momentum strategy backtest')
    parser.add_argument('--tickers', nargs='+',
                       default=['005930', '000660', '035420', '005380', '051910',
                               '006400', '005490', '000270', '035720', '028260'],
                       help='Stock tickers (default: Top 10 KOSPI)')
    parser.add_argument('--start', type=str, default='2020-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--lookback', type=int, default=252,
                       help='Momentum lookback period (days)')
    parser.add_argument('--rebalance', type=int, default=21,
                       help='Rebalance period (days)')
    parser.add_argument('--top-n', type=int, default=3,
                       help='Number of top momentum stocks to hold')
    parser.add_argument('--capital', type=float, default=100_000_000,
                       help='Initial capital (KRW)')
    parser.add_argument('--no-db', action='store_true',
                       help='Use synthetic data instead of database')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("MOMENTUM STRATEGY BACKTEST")
    logger.info("=" * 80)

    # Load data
    logger.info(f"Loading data: {len(args.tickers)} tickers, {args.start} to {args.end}")

    if args.no_db:
        # Generate synthetic data for testing
        logger.warning("Using synthetic data (--no-db flag)")
        dates = pd.date_range(args.start, args.end, freq='D')
        data = {}

        for ticker in args.tickers:
            np.random.seed(int(ticker) % 10000)  # Deterministic per ticker
            returns = np.random.randn(len(dates)) * 0.02
            close_prices = 50000 * np.exp(np.cumsum(returns))

            data[ticker] = pd.DataFrame({
                'open': close_prices * (1 + np.random.uniform(-0.01, 0.01, len(dates))),
                'high': close_prices * (1 + np.random.uniform(0, 0.02, len(dates))),
                'low': close_prices * (1 - np.random.uniform(0, 0.02, len(dates))),
                'close': close_prices,
                'volume': np.random.randint(500000, 2000000, len(dates))
            }, index=dates)
    else:
        # Load from PostgreSQL database
        adapter = VectorBTAdapter()
        data = adapter.load_data(
            tickers=args.tickers,
            region='KR',
            start_date=args.start,
            end_date=args.end
        )

        if len(data) == 0:
            logger.error("No data loaded from database. Check PostgreSQL connection.")
            logger.info("Try running with --no-db to use synthetic data")
            return

    logger.info(f"Loaded {len(data)} tickers with data")

    # Initialize strategy
    strategy = MomentumStrategy(
        lookback_periods=args.lookback,
        rebalance_periods=args.rebalance,
        top_n_stocks=args.top_n
    )

    # Run backtest
    results = strategy.run_backtest(
        data=data,
        initial_capital=args.capital,
        commission=0.00015,  # KIS standard
        slippage=0.0005       # 5 bps
    )

    # Print results
    strategy.print_results(results)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"momentum_backtest_{timestamp}.csv"

    # Save cumulative returns
    cum_returns = results['cumulative_returns']
    if isinstance(cum_returns, pd.Series):
        cum_returns.to_csv(output_file)
    else:
        cum_returns.to_csv(output_file)

    logger.info(f"\n💾 Results saved to: {output_file}")
    logger.info("\n✅ Backtest completed successfully!")


if __name__ == '__main__':
    main()
