"""
Backtest command for Quant Platform CLI.

Provides fast backtesting of trading strategies using vectorbt
with support for multiple strategies and performance analysis.
"""

import asyncio
import argparse
from typing import List, Optional
import sys
import pandas as pd
import numpy as np

from cli.utils.database import DatabaseManager
from cli.utils.ohlcv_loader import OHLCVLoader
from cli.utils.vectorbt_adapter import VectorbtAdapter, create_ma_crossover_signals
from cli.utils.query_formatter import QueryFormatter
from cli.utils.report_generator import ReportGenerator


async def backtest_command(args: argparse.Namespace) -> int:
    """
    Execute backtest command.

    Args:
        args: Parsed command line arguments with following attributes:
            - tickers: List of ticker symbols
            - start_date: Backtest start date
            - end_date: Backtest end date
            - region: Market region
            - strategy: Strategy name (ma-crossover, buy-hold)
            - initial_cash: Initial portfolio cash
            - commission: Commission rate
            - short_window: Short MA window (for MA crossover)
            - long_window: Long MA window (for MA crossover)
            - output: Output file path (CSV/JSON)

    Returns:
        Exit code (0 for success, 1 for error)

    Examples:
        # Simple buy-and-hold backtest
        backtest --tickers 005930 --start 2020-01-01 --end 2023-12-31 --strategy buy-hold

        # MA crossover strategy
        backtest --tickers 005930 000660 --start 2022-01-01 \\
                 --strategy ma-crossover --short 20 --long 60

        # Export results
        backtest --tickers 005930 --start 2023-01-01 --output results.csv
    """
    formatter = QueryFormatter()

    try:
        # Validate vectorbt availability
        try:
            from cli.utils.vectorbt_adapter import VectorbtAdapter
        except ImportError:
            formatter.print_error(
                "vectorbt is required for backtesting.\n"
                "Install with: pip install vectorbt"
            )
            return 1

        # Load data
        formatter.console.print("[cyan]Loading historical data...[/cyan]")
        loader = OHLCVLoader()
        await loader.connect()

        # Convert string dates to datetime objects
        from datetime import datetime
        start_dt = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end_date, '%Y-%m-%d')

        try:
            df = await loader.load_data(
                tickers=args.tickers,
                start_date=start_dt,
                end_date=end_dt,
                region=args.region,
                timeframe='1d',
                include_technicals=args.strategy == 'ma-crossover'
            )

            # Extract close prices and ensure numeric dtype
            prices = df['close'].unstack('ticker').astype(np.float64)

            formatter.console.print(
                f"[green]✓[/green] Loaded {len(df)} rows for {len(args.tickers)} ticker(s)"
            )

        except ValueError as e:
            formatter.print_error(f"Data loading failed: {e}")
            return 1
        finally:
            await loader.disconnect()

        # Generate strategy signals
        formatter.console.print(f"[cyan]Generating {args.strategy} signals...[/cyan]")

        if args.strategy == 'buy-hold':
            # Buy at start, hold until end (explicit int8 dtype for vectorbt compatibility)
            signals = pd.DataFrame(0, index=prices.index, columns=prices.columns, dtype=np.int8)
            signals.iloc[0, :] = 1   # Buy at start
            signals.iloc[-1, :] = -1  # Sell at end

        elif args.strategy == 'ma-crossover':
            signals = create_ma_crossover_signals(
                prices=prices,
                short_window=args.short_window,
                long_window=args.long_window
            )

        else:
            formatter.print_error(f"Unknown strategy: {args.strategy}")
            return 1

        # Run backtest
        formatter.console.print("[cyan]Running backtest...[/cyan]")
        adapter = VectorbtAdapter()

        portfolio = adapter.run_backtest(
            prices=prices,
            signals=signals,
            initial_cash=args.initial_cash,
            commission=args.commission,
            slippage=0.001
        )

        # Get metrics
        metrics = adapter.get_metrics(portfolio)

        # Display results
        formatter.console.print("\n[bold green]Backtest Results[/bold green]")
        formatter.console.print(f"Strategy: [cyan]{args.strategy}[/cyan]")
        formatter.console.print(f"Period: [cyan]{args.start_date}[/cyan] to [cyan]{args.end_date}[/cyan]")
        formatter.console.print(f"Tickers: [cyan]{', '.join(args.tickers)}[/cyan]\n")

        # Format metrics table
        from rich.table import Table
        table = Table(title="Performance Metrics", show_header=True, border_style="bright_blue")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")

        for key, value in metrics.items():
            # Format value based on type
            if 'return' in key or 'drawdown' in key or 'rate' in key:
                formatted_value = f"{value:.2f}%"
            elif 'ratio' in key or 'factor' in key:
                formatted_value = f"{value:.2f}"
            elif 'value' in key:
                formatted_value = f"{value:,.0f} KRW"
            elif 'trades' in key:
                formatted_value = f"{int(value):,}"
            else:
                formatted_value = f"{value:.2f}"

            # Color coding
            if 'return' in key:
                style = "green" if value > 0 else "red"
            elif 'drawdown' in key:
                style = "red" if value < -10 else "yellow"
            elif 'sharpe' in key:
                style = "green" if value > 1 else "yellow" if value > 0 else "red"
            else:
                style = "white"

            table.add_row(key.replace('_', ' ').title(), f"[{style}]{formatted_value}[/{style}]")

        formatter.console.print(table)

        # Get trade details
        trades = adapter.get_trades(portfolio)
        if len(trades) > 0:
            formatter.console.print(f"\n[bold]Trade Summary[/bold]")
            formatter.console.print(f"Total Trades: [cyan]{len(trades):,}[/cyan]")
            winning_trades = len(trades[trades['PnL'] > 0])
            formatter.console.print(f"Winning Trades: [green]{winning_trades:,}[/green]")
            losing_trades = len(trades[trades['PnL'] < 0])
            formatter.console.print(f"Losing Trades: [red]{losing_trades:,}[/red]")

        # Export if requested
        if args.output:
            if args.output.endswith('.csv'):
                # Export metrics to CSV
                metrics_df = pd.DataFrame([metrics])
                metrics_df.to_csv(args.output, index=False)
                formatter.console.print(f"\n[green]✓[/green] Results exported to [cyan]{args.output}[/cyan]")

            elif args.output.endswith('.json'):
                # Export metrics to JSON
                import json
                with open(args.output, 'w') as f:
                    json.dump(metrics, f, indent=2)
                formatter.console.print(f"\n[green]✓[/green] Results exported to [cyan]{args.output}[/cyan]")

            elif args.output.endswith('.html'):
                # Generate HTML report
                formatter.console.print("\n[cyan]Generating HTML report...[/cyan]")

                report_generator = ReportGenerator()
                returns = adapter.get_returns(portfolio)

                report_path = report_generator.generate_backtest_report(
                    portfolio_returns=returns,
                    metrics=metrics,
                    tickers=args.tickers,
                    strategy_name=args.strategy,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    initial_cash=args.initial_cash,
                    commission=args.commission,
                    trades=trades if len(trades) > 0 else None,
                    benchmark_returns=None,  # TODO: Add benchmark support
                    output_path=args.output,
                    title=f"{args.strategy.title()} Strategy Backtest"
                )

                formatter.console.print(f"[green]✓[/green] HTML report generated: [cyan]{report_path}[/cyan]")

            else:
                formatter.print_warning("Output file must be .csv, .json, or .html")

        return 0

    except Exception as e:
        formatter.print_error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def add_backtest_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add backtest command arguments to argument parser.

    Args:
        parser: Argument parser to add arguments to
    """
    parser.add_argument(
        '--tickers',
        nargs='+',
        required=True,
        help='List of ticker symbols to backtest (space-separated)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Backtest start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='Backtest end date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--region',
        type=str,
        default='KR',
        choices=['KR', 'US'],
        help='Market region (default: KR)'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        default='buy-hold',
        choices=['buy-hold', 'ma-crossover'],
        help='Strategy to backtest (default: buy-hold)'
    )

    parser.add_argument(
        '--initial-cash',
        type=float,
        default=10_000_000,
        help='Initial portfolio cash in KRW (default: 10,000,000)'
    )

    parser.add_argument(
        '--commission',
        type=float,
        default=0.0015,
        help='Commission rate (default: 0.0015 = 0.15%%)'
    )

    parser.add_argument(
        '--short-window',
        type=int,
        default=20,
        help='Short MA window for ma-crossover strategy (default: 20)'
    )

    parser.add_argument(
        '--long-window',
        type=int,
        default=60,
        help='Long MA window for ma-crossover strategy (default: 60)'
    )

    parser.add_argument(
        '--output',
        type=str,
        help='Export results to file (.csv, .json, or .html)'
    )


def run_backtest_sync(args: argparse.Namespace) -> int:
    """
    Synchronous wrapper for backtest_command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    return asyncio.run(backtest_command(args))


if __name__ == '__main__':
    # Standalone testing
    parser = argparse.ArgumentParser(description='Backtest trading strategies')
    add_backtest_arguments(parser)
    args = parser.parse_args()
    sys.exit(run_backtest_sync(args))
