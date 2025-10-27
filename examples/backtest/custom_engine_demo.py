"""
Custom Backtesting Engine Demonstration

Shows complete workflow with custom event-driven engine:
1. Load or generate historical data
2. Create simple momentum strategy signals
3. Run custom engine backtest
4. Compare with VectorBT (optional)
5. Analyze detailed results and trade log

Custom Engine Advantages:
- Order-level execution detail
- Custom order types and logic
- Compliance auditing capabilities
- Production validation before live trading

Usage:
    python3 examples/backtest/custom_engine_demo.py
    python3 examples/backtest/custom_engine_demo.py --compare-vectorbt
    python3 examples/backtest/custom_engine_demo.py --start 2020-01-01 --end 2024-12-31
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

from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.common.costs import TransactionCostModel


def generate_sample_data(
    tickers: list,
    start_date: str = '2020-01-01',
    end_date: str = '2024-12-31'
) -> dict:
    """
    Generate realistic sample OHLCV data.

    Args:
        tickers: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dictionary of {ticker: OHLCV DataFrame}
    """
    logger.info(f"Generating sample data for {len(tickers)} tickers")

    dates = pd.date_range(start_date, end_date, freq='D')
    data = {}

    for i, ticker in enumerate(tickers):
        np.random.seed(42 + i)  # Deterministic per ticker
        n_days = len(dates)

        # Generate realistic price movements
        returns = np.random.randn(n_days) * 0.02  # 2% daily volatility
        close_prices = 50000 * np.exp(np.cumsum(returns))

        # Add trend component (some tickers up, some down)
        trend = np.linspace(0, 0.2 * (i % 3 - 1), n_days)
        close_prices = close_prices * np.exp(trend)

        df = pd.DataFrame({
            'open': close_prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
            'high': close_prices * (1 + np.random.uniform(0, 0.02, n_days)),
            'low': close_prices * (1 - np.random.uniform(0, 0.02, n_days)),
            'close': close_prices,
            'volume': np.random.randint(500000, 2000000, n_days)
        }, index=dates)

        data[ticker] = df

    logger.info(f"Generated {len(dates)} days of data")
    return data


def calculate_momentum_signals(
    data: dict,
    lookback_periods: int = 252,  # 12 months
    skip_recent: int = 21,  # Skip last month
    top_n: int = 3
) -> dict:
    """
    Calculate momentum signals for stock selection.

    Strategy:
    - Rank stocks by 12-month return (skip last month for reversal)
    - Hold top N stocks
    - Rebalance monthly

    Args:
        data: Dictionary of OHLCV DataFrames
        lookback_periods: Momentum calculation period
        skip_recent: Period to skip (avoid short-term reversal)
        top_n: Number of top stocks to hold

    Returns:
        Dictionary of {ticker: boolean signal Series}
    """
    logger.info(f"Calculating momentum signals: lookback={lookback_periods}d, top_n={top_n}")

    # Get close prices for all tickers
    close_prices = pd.DataFrame({
        ticker: df['close'] for ticker, df in data.items()
    })

    # Calculate momentum (skip recent period)
    shifted_prices = close_prices.shift(skip_recent)
    momentum = shifted_prices.pct_change(periods=lookback_periods)

    # Rank stocks by momentum
    momentum_ranks = momentum.rank(axis=1, ascending=False, method='first')

    # Generate signals (True for top N)
    signals = momentum_ranks <= top_n

    # Convert to dictionary
    signals_dict = {
        ticker: signals[ticker]
        for ticker in signals.columns
    }

    logger.info(f"Generated signals: {signals.sum().sum()} total buy signals")
    return signals_dict


def run_custom_engine_backtest(
    data: dict,
    signals: dict,
    initial_capital: float = 100_000_000
) -> dict:
    """
    Run backtest with custom event-driven engine.

    Args:
        data: Dictionary of OHLCV DataFrames
        signals: Dictionary of signal Series
        initial_capital: Starting capital (KRW)

    Returns:
        Dictionary with backtest results
    """
    logger.info("=" * 80)
    logger.info("RUNNING CUSTOM ENGINE BACKTEST")
    logger.info("=" * 80)

    # Create custom engine with KIS broker costs
    cost_model = TransactionCostModel(
        broker='KIS',
        slippage_bps=5.0  # 5 bps slippage
    )

    engine = BacktestEngine(
        initial_capital=initial_capital,
        cost_model=cost_model,
        size_type='equal_weight',
        target_positions=len([s for s in signals.values() if s.any()])
    )

    # Run backtest
    results = engine.run(data=data, signals=signals)

    return results


def run_vectorbt_backtest(
    data: dict,
    signals: dict,
    initial_capital: float = 100_000_000
) -> dict:
    """
    Run backtest with VectorBT (for comparison).

    Args:
        data: Dictionary of OHLCV DataFrames
        signals: Dictionary of signal Series
        initial_capital: Starting capital (KRW)

    Returns:
        Dictionary with backtest results
    """
    logger.info("=" * 80)
    logger.info("RUNNING VECTORBT BACKTEST (COMPARISON)")
    logger.info("=" * 80)

    adapter = VectorBTAdapter(
        initial_capital=initial_capital,
        commission=0.00015,
        slippage=0.0005
    )

    portfolio = adapter.run_portfolio_backtest(
        data=data,
        signals=signals,
        size_type='percent',
        size=1.0 / len(signals)  # Equal weight
    )

    metrics = adapter.calculate_metrics(portfolio)

    return {
        'portfolio': portfolio,
        'metrics': metrics
    }


def print_comparison(custom_results: dict, vbt_results: dict = None):
    """
    Print comparison between custom engine and VectorBT.

    Args:
        custom_results: Custom engine results
        vbt_results: VectorBT results (optional)
    """
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS COMPARISON")
    print("=" * 80)

    custom_metrics = custom_results['metrics']

    # Custom Engine Results
    print("\n📊 Custom Event-Driven Engine:")
    print(f"  Total Return:         {custom_metrics['total_return_pct']:>10.2%}")
    print(f"  Annualized Return:    {custom_metrics['annualized_return']:>10.2%}")
    print(f"  Sharpe Ratio:         {custom_metrics['sharpe_ratio']:>10.2f}")
    print(f"  Max Drawdown:         {custom_metrics['max_drawdown']:>10.2%}")
    print(f"  Total Trades:         {custom_results['trade_stats']['total_trades']:>10,}")
    print(f"  Win Rate:             {custom_results['trade_stats']['win_rate']:>10.2%}")
    print(f"  Execution Time:       {custom_results['execution_time']:>10.2f}s")

    if vbt_results:
        vbt_metrics = vbt_results['metrics']

        # Extract scalar values from Series
        vbt_total_return = vbt_metrics['total_return']
        if isinstance(vbt_total_return, pd.Series):
            vbt_total_return = vbt_total_return.iloc[0]

        vbt_sharpe = vbt_metrics['sharpe_ratio']
        if isinstance(vbt_sharpe, pd.Series):
            vbt_sharpe = vbt_sharpe.iloc[0]

        print("\n⚡ VectorBT (Vectorized Engine):")
        print(f"  Total Return:         {vbt_total_return:>10.2%}")
        print(f"  Sharpe Ratio:         {vbt_sharpe:>10.2f}")
        print(f"  Total Trades:         {vbt_metrics['total_trades']:>10,}")

        print("\n📈 Performance Comparison:")
        print(f"  Return Difference:    {abs(custom_metrics['total_return_pct'] - vbt_total_return):>10.2%}")
        print(f"  Note: Different signal models may cause different returns")

    # Trade Analysis
    print("\n💰 Trade Analysis (Custom Engine):")
    trade_stats = custom_results['trade_stats']
    print(f"  Winning Trades:       {trade_stats.get('winning_trades', 0):>10,}")
    print(f"  Losing Trades:        {trade_stats.get('losing_trades', 0):>10,}")
    print(f"  Average Win:          ₩{trade_stats.get('avg_win', 0):>10,.0f}")
    print(f"  Average Loss:         ₩{trade_stats.get('avg_loss', 0):>10,.0f}")
    print(f"  Average Hold Days:    {trade_stats.get('avg_holding_days', 0):>10.1f}")
    print(f"  Total Commission:     ₩{trade_stats.get('total_commission', 0):>10,.0f}")
    print(f"  Total Tax:            ₩{trade_stats.get('total_tax', 0):>10,.0f}")


def save_results(results: dict, output_prefix: str = 'custom_backtest'):
    """
    Save backtest results to CSV files.

    Args:
        results: Backtest results dictionary
        output_prefix: Prefix for output files
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save equity curve
    equity_file = f"{output_prefix}_equity_{timestamp}.csv"
    results['equity_curve'].to_csv(equity_file)
    logger.info(f"Equity curve saved to: {equity_file}")

    # Save trade log
    if len(results['trades']) > 0:
        trades_file = f"{output_prefix}_trades_{timestamp}.csv"
        results['trades'].to_csv(trades_file, index=False)
        logger.info(f"Trade log saved to: {trades_file}")


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Custom engine backtest demonstration')
    parser.add_argument('--tickers', nargs='+',
                       default=['005930', '000660', '035420', '005380', '051910',
                               '006400', '005490', '000270', '035720', '028260'],
                       help='Stock tickers (default: Top 10 KOSPI)')
    parser.add_argument('--start', type=str, default='2020-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100_000_000,
                       help='Initial capital (KRW)')
    parser.add_argument('--top-n', type=int, default=3,
                       help='Number of top momentum stocks to hold')
    parser.add_argument('--compare-vectorbt', action='store_true',
                       help='Run VectorBT comparison')
    parser.add_argument('--save-results', action='store_true',
                       help='Save results to CSV files')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("CUSTOM BACKTESTING ENGINE DEMONSTRATION")
    logger.info("=" * 80)
    logger.info(f"Tickers: {len(args.tickers)}")
    logger.info(f"Period: {args.start} to {args.end}")
    logger.info(f"Capital: ₩{args.capital:,.0f}")

    # Generate sample data
    data = generate_sample_data(args.tickers, args.start, args.end)

    # Calculate momentum signals
    signals = calculate_momentum_signals(data, top_n=args.top_n)

    # Run custom engine backtest
    custom_results = run_custom_engine_backtest(data, signals, args.capital)

    # Optional: Run VectorBT comparison
    vbt_results = None
    if args.compare_vectorbt:
        vbt_results = run_vectorbt_backtest(data, signals, args.capital)

    # Print comparison
    print_comparison(custom_results, vbt_results)

    # Optional: Save results
    if args.save_results:
        save_results(custom_results)

    logger.info("\n✅ Backtest demonstration completed successfully!")


if __name__ == '__main__':
    main()
