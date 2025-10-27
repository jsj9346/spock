"""
Performance Benchmarking Script for Backtesting Engines

Benchmarks and compares:
- VectorBT (vectorized, research-optimized)
- Custom Engine (event-driven, production-ready)

Metrics:
- Execution time (target: VectorBT <1s, Custom <30s for 5-year backtest)
- Memory usage
- Parameter sweep performance (100+ combinations)
- Accuracy consistency

Usage:
    python3 scripts/benchmark_backtest_engines.py --comprehensive
    python3 scripts/benchmark_backtest_engines.py --engine vectorbt
    python3 scripts/benchmark_backtest_engines.py --quick
"""

import sys
import time
import psutil
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import argparse
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.common.metrics import PerformanceMetrics
from modules.backtest.custom.orders import OrderExecutionEngine


class BenchmarkRunner:
    """
    Comprehensive benchmarking suite for backtesting engines.

    Tests performance across multiple dimensions:
    - Single backtest speed
    - Parameter sweep efficiency
    - Memory consumption
    - Accuracy validation
    """

    def __init__(self, tickers: List[str] = ['005930'], region: str = 'KR'):
        self.tickers = tickers
        self.region = region
        self.results = {}

        logger.info(f"BenchmarkRunner initialized: {len(tickers)} tickers, region={region}")

    def generate_test_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        use_db: bool = True
    ) -> pd.DataFrame:
        """
        Generate or load test data for benchmarking.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_db: Load from PostgreSQL database

        Returns:
            DataFrame with OHLCV data
        """
        if use_db:
            # Load from database
            adapter = VectorBTAdapter()
            data = adapter.load_data(
                tickers=[ticker],
                region=self.region,
                start_date=start_date,
                end_date=end_date
            )

            if ticker in data:
                logger.info(f"Loaded {len(data[ticker])} records for {ticker}")
                return data[ticker]

        # Generate synthetic data for testing
        logger.warning(f"Generating synthetic data for {ticker}")
        dates = pd.date_range(start_date, end_date, freq='D')
        n_days = len(dates)

        # Realistic price simulation
        np.random.seed(42)
        returns = np.random.randn(n_days) * 0.02  # 2% daily volatility
        close_prices = 60000 * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            'open': close_prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
            'high': close_prices * (1 + np.random.uniform(0, 0.02, n_days)),
            'low': close_prices * (1 - np.random.uniform(0, 0.02, n_days)),
            'close': close_prices,
            'volume': np.random.randint(500000, 2000000, n_days)
        }, index=dates)

        return df

    def generate_simple_signals(self, df: pd.DataFrame, ma_period: int = 20) -> pd.Series:
        """Generate simple moving average crossover signals"""
        ma = df['close'].rolling(window=ma_period).mean()
        signals = df['close'] > ma
        return signals

    def benchmark_vectorbt(
        self,
        data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.Series],
        n_runs: int = 3
    ) -> Dict:
        """
        Benchmark VectorBT performance.

        Args:
            data: Dictionary of OHLCV DataFrames
            signals: Dictionary of signal Series
            n_runs: Number of runs for averaging

        Returns:
            Benchmark results dictionary
        """
        logger.info("🔥 Benchmarking VectorBT...")

        execution_times = []
        memory_usage = []

        for run in range(n_runs):
            # Measure memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Run backtest with timing
            start_time = time.time()

            adapter = VectorBTAdapter(
                initial_capital=100_000_000,
                commission=0.00015,
                slippage=0.0005
            )

            portfolio = adapter.run_portfolio_backtest(
                data=data,
                signals=signals,
                size_type='percent',
                size=1.0
            )

            metrics = adapter.calculate_metrics(portfolio)

            execution_time = time.time() - start_time

            # Measure memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = mem_after - mem_before

            execution_times.append(execution_time)
            memory_usage.append(memory_used)

            logger.debug(f"Run {run+1}/{n_runs}: {execution_time:.3f}s, {memory_used:.1f}MB")

        # Extract metrics (handle Series)
        total_return = metrics['total_return']
        if isinstance(total_return, pd.Series):
            total_return = total_return.iloc[0]

        sharpe = metrics['sharpe_ratio']
        if isinstance(sharpe, pd.Series):
            sharpe = sharpe.iloc[0]

        results = {
            'engine': 'vectorbt',
            'avg_execution_time': np.mean(execution_times),
            'min_execution_time': np.min(execution_times),
            'max_execution_time': np.max(execution_times),
            'avg_memory_mb': np.mean(memory_usage),
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'total_trades': metrics['total_trades'],
            'n_periods': len(list(data.values())[0])
        }

        logger.info(f"✅ VectorBT: {results['avg_execution_time']:.3f}s avg, "
                   f"{results['avg_memory_mb']:.1f}MB, Sharpe={results['sharpe_ratio']:.2f}")

        return results

    def benchmark_custom_engine(
        self,
        data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.Series],
        n_runs: int = 3
    ) -> Dict:
        """
        Benchmark Custom Engine components (Order Execution).

        Note: Full event-driven engine not yet implemented.
        This benchmarks the order execution component only.

        Args:
            data: Dictionary of OHLCV DataFrames
            signals: Dictionary of signal Series
            n_runs: Number of runs for averaging

        Returns:
            Benchmark results dictionary
        """
        logger.info("🔧 Benchmarking Custom Engine Components...")
        logger.warning("Note: Full custom engine not yet implemented, testing order execution only")

        execution_times = []
        memory_usage = []

        from modules.backtest.common.costs import TransactionCostModel

        for run in range(n_runs):
            # Measure memory before
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Run order execution simulation
            start_time = time.time()

            cost_model = TransactionCostModel(broker='KIS', slippage_bps=5.0)
            order_engine = OrderExecutionEngine(
                cost_model=cost_model,
                partial_fill_enabled=True,
                max_participation_rate=0.1
            )

            # Simulate order processing for each bar
            total_fills = 0
            for ticker, df in data.items():
                ticker_signals = signals[ticker]

                for idx, (date, row) in enumerate(df.iterrows()):
                    # Submit orders based on signals
                    if idx > 0 and ticker_signals.iloc[idx]:
                        from modules.backtest.custom.orders import OrderType, OrderSide

                        order = order_engine.submit_order(
                            ticker=ticker,
                            order_type=OrderType.MARKET,
                            side=OrderSide.BUY,
                            quantity=100
                        )

                    # Process bar
                    fills = order_engine.process_bar(row, volume=row['volume'])
                    total_fills += len(fills)

            execution_time = time.time() - start_time

            # Measure memory after
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_used = mem_after - mem_before

            execution_times.append(execution_time)
            memory_usage.append(memory_used)

            logger.debug(f"Run {run+1}/{n_runs}: {execution_time:.3f}s, {memory_used:.1f}MB, {total_fills} fills")

        results = {
            'engine': 'custom_orders',
            'avg_execution_time': np.mean(execution_times),
            'min_execution_time': np.min(execution_times),
            'max_execution_time': np.max(execution_times),
            'avg_memory_mb': np.mean(memory_usage),
            'total_return': 0.0,  # N/A - order execution only
            'sharpe_ratio': 0.0,  # N/A - order execution only
            'total_trades': total_fills,
            'n_periods': len(list(data.values())[0])
        }

        logger.info(f"✅ Custom Orders: {results['avg_execution_time']:.3f}s avg, "
                   f"{results['avg_memory_mb']:.1f}MB, {total_fills} fills")

        return results

    def benchmark_parameter_sweep(
        self,
        data: Dict[str, pd.DataFrame],
        ma_periods: List[int] = [10, 20, 30, 50, 100]
    ) -> Dict:
        """
        Benchmark parameter sweep performance (VectorBT only).

        Tests ability to optimize across multiple parameter combinations.

        Args:
            data: Dictionary of OHLCV DataFrames
            ma_periods: List of MA periods to test

        Returns:
            Sweep benchmark results
        """
        logger.info(f"🔍 Benchmarking parameter sweep: {len(ma_periods)} combinations")

        start_time = time.time()

        results = []
        for ma_period in ma_periods:
            signals = {
                ticker: self.generate_simple_signals(df, ma_period)
                for ticker, df in data.items()
            }

            adapter = VectorBTAdapter(
                initial_capital=100_000_000,
                commission=0.00015,
                slippage=0.0005
            )

            portfolio = adapter.run_portfolio_backtest(
                data=data,
                signals=signals,
                size_type='percent',
                size=1.0
            )

            metrics = adapter.calculate_metrics(portfolio)

            sharpe = metrics['sharpe_ratio']
            if isinstance(sharpe, pd.Series):
                sharpe = sharpe.iloc[0]

            results.append({
                'ma_period': ma_period,
                'sharpe_ratio': sharpe
            })

        execution_time = time.time() - start_time

        # Find best parameters
        best_result = max(results, key=lambda x: x['sharpe_ratio'])

        sweep_results = {
            'n_combinations': len(ma_periods),
            'execution_time': execution_time,
            'time_per_combination': execution_time / len(ma_periods),
            'best_ma_period': best_result['ma_period'],
            'best_sharpe': best_result['sharpe_ratio']
        }

        logger.info(f"✅ Parameter sweep: {execution_time:.3f}s for {len(ma_periods)} combinations "
                   f"({sweep_results['time_per_combination']:.3f}s each)")

        return sweep_results

    def run_comprehensive_benchmark(
        self,
        start_date: str = '2020-01-01',
        end_date: str = '2024-12-31',
        use_db: bool = True
    ) -> pd.DataFrame:
        """
        Run comprehensive benchmark suite.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            use_db: Load from database

        Returns:
            DataFrame with benchmark results
        """
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE BACKTESTING ENGINE BENCHMARK")
        logger.info("=" * 80)

        # Load data
        logger.info(f"Loading data: {start_date} to {end_date}")
        data = {}
        for ticker in self.tickers:
            df = self.generate_test_data(ticker, start_date, end_date, use_db)
            data[ticker] = df

        # Generate signals
        signals = {
            ticker: self.generate_simple_signals(df, ma_period=20)
            for ticker, df in data.items()
        }

        # Benchmark VectorBT
        vbt_results = self.benchmark_vectorbt(data, signals, n_runs=3)

        # Benchmark Custom Engine
        custom_results = self.benchmark_custom_engine(data, signals, n_runs=3)

        # Benchmark parameter sweep (VectorBT only)
        sweep_results = self.benchmark_parameter_sweep(data, ma_periods=[10, 20, 30, 50, 100])

        # Compile results
        comparison_df = pd.DataFrame([vbt_results, custom_results])

        # Print comparison table
        logger.info("\n" + "=" * 80)
        logger.info("BENCHMARK RESULTS SUMMARY")
        logger.info("=" * 80)

        print("\n📊 Engine Comparison:")
        print(comparison_df.to_string(index=False))

        print(f"\n🔍 Parameter Sweep (VectorBT):")
        print(f"  Combinations: {sweep_results['n_combinations']}")
        print(f"  Total Time: {sweep_results['execution_time']:.3f}s")
        print(f"  Time/Combination: {sweep_results['time_per_combination']:.3f}s")
        print(f"  Best MA Period: {sweep_results['best_ma_period']}")
        print(f"  Best Sharpe: {sweep_results['best_sharpe']:.2f}")

        # Performance targets validation
        logger.info("\n" + "=" * 80)
        logger.info("PERFORMANCE TARGET VALIDATION")
        logger.info("=" * 80)

        vbt_time = vbt_results['avg_execution_time']
        custom_time = custom_results['avg_execution_time']

        vbt_target = 1.0  # <1s for 5-year backtest
        custom_target = 30.0  # <30s for 5-year backtest (N/A for order execution only)

        print(f"\n✅ VectorBT: {vbt_time:.3f}s (target: <{vbt_target}s) - " +
              ("PASS ✅" if vbt_time < vbt_target else "FAIL ❌"))
        print(f"ℹ️  Custom Orders: {custom_time:.3f}s (order execution component only)")
        print(f"   Note: Full custom engine target is <{custom_target}s for complete backtest")

        if vbt_time > 0:
            speedup = custom_time / vbt_time
            print(f"\n⚡ Performance Comparison: Custom order execution is {speedup:.1f}x " +
                  ("slower" if speedup > 1 else "faster") + " than VectorBT full backtest")

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"benchmark_results_{timestamp}.csv"
        comparison_df.to_csv(output_file, index=False)
        logger.info(f"\n💾 Results saved to: {output_file}")

        return comparison_df


def main():
    """Main benchmark execution"""
    parser = argparse.ArgumentParser(description='Benchmark backtesting engines')
    parser.add_argument('--engine', type=str, choices=['vectorbt', 'custom', 'both'],
                       default='both', help='Engine to benchmark')
    parser.add_argument('--tickers', nargs='+', default=['005930'],
                       help='Tickers to test (default: 005930)')
    parser.add_argument('--start', type=str, default='2020-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick benchmark (1 year, 1 run)')
    parser.add_argument('--comprehensive', action='store_true',
                       help='Comprehensive benchmark (5 years, 3 runs)')
    parser.add_argument('--no-db', action='store_true',
                       help='Use synthetic data instead of database')

    args = parser.parse_args()

    # Adjust parameters based on mode
    if args.quick:
        start_date = '2024-01-01'
        end_date = '2024-12-31'
        logger.info("🚀 Quick benchmark mode: 1 year")
    elif args.comprehensive:
        start_date = args.start
        end_date = args.end
        logger.info("🔬 Comprehensive benchmark mode: Full period")
    else:
        start_date = args.start
        end_date = args.end

    # Run benchmark
    runner = BenchmarkRunner(tickers=args.tickers)
    results = runner.run_comprehensive_benchmark(
        start_date=start_date,
        end_date=end_date,
        use_db=not args.no_db
    )

    logger.info("\n✅ Benchmark completed successfully!")


if __name__ == '__main__':
    main()
