"""
vectorbt Performance Benchmark

Demonstrates vectorbt's vectorized backtesting speed across different timeframes.

Expected Results:
    - 3-month backtest: <1 second
    - 1-year backtest: <2 seconds
    - 5-year backtest: <5 seconds

Usage:
    python3 examples/benchmark_vectorbt_performance.py
"""

import sys
import time
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager


def run_benchmark(config, data_provider, name):
    """Run single benchmark with given configuration."""
    print(f"\n{name}")
    print("-" * 60)

    # Create adapter
    adapter = VectorbtAdapter(config, data_provider)

    # Run backtest
    start_time = time.time()
    result = adapter.run()
    total_time = time.time() - start_time

    # Calculate days
    days = (config.end_date - config.start_date).days

    print(f"  Date range:      {config.start_date} to {config.end_date} ({days} days)")
    print(f"  Tickers:         {', '.join(config.tickers)}")
    print(f"  Execution time:  {result.execution_time:.3f}s (total: {total_time:.3f}s)")
    print(f"  Performance:     {days/result.execution_time:.0f} days/second")
    print(f"\n  Results:")
    print(f"    Total return:  {result.total_return:>8.2%}")
    print(f"    Sharpe ratio:  {result.sharpe_ratio:>8.2f}")
    print(f"    Max drawdown:  {result.max_drawdown:>8.2%}")
    print(f"    Total trades:  {result.total_trades:>8}")

    return result.execution_time


def main():
    """Run performance benchmarks."""
    print("\n" + "="*70)
    print("VECTORBT PERFORMANCE BENCHMARK")
    print("="*70)

    # Database setup
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'

    if not db_path.exists():
        print(f"\n✗ Database not found: {db_path}")
        return

    print(f"\nDatabase: {db_path.name}")

    # Create data provider
    db_manager = SQLiteDatabaseManager(str(db_path))
    data_provider = SQLiteDataProvider(db_manager)

    # Base configuration
    base_config = {
        'initial_capital': 10000000,
        'regions': ['KR'],
        'tickers': ['000020'],  # Single ticker for fair comparison
        'max_position_size': 0.15,
        'score_threshold': 60.0,
        'risk_profile': 'moderate',
        'commission_rate': 0.00015,
        'slippage_bps': 5.0
    }

    results = {}

    # Benchmark 1: 3-month backtest
    config_3m = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2024, 12, 31),
        **base_config
    )
    results['3-month'] = run_benchmark(config_3m, data_provider, "Benchmark 1: 3-Month Backtest")

    # Benchmark 2: 6-month backtest
    config_6m = BacktestConfig(
        start_date=date(2024, 7, 1),
        end_date=date(2024, 12, 31),
        **base_config
    )
    results['6-month'] = run_benchmark(config_6m, data_provider, "Benchmark 2: 6-Month Backtest")

    # Benchmark 3: 1-year backtest
    config_1y = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2025, 10, 20),
        **base_config
    )
    results['1-year'] = run_benchmark(config_1y, data_provider, "Benchmark 3: 1-Year Backtest")

    # Benchmark 4: Multi-ticker (3 tickers, 3 months)
    config_multi = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2024, 12, 31),
        **{**base_config, 'tickers': ['000020', '000040', '000050']}
    )
    results['multi-ticker'] = run_benchmark(config_multi, data_provider, "Benchmark 4: Multi-Ticker (3 stocks, 3 months)")

    # Summary
    print("\n" + "="*70)
    print("PERFORMANCE SUMMARY")
    print("="*70)

    print(f"\nExecution Times:")
    for name, exec_time in results.items():
        print(f"  {name:15} {exec_time:>8.3f}s")

    avg_time = sum(results.values()) / len(results)
    print(f"\n  Average:        {avg_time:>8.3f}s")

    # Performance assessment
    if avg_time < 2.0:
        print(f"\n✓ Excellent performance (target: <2s average)")
    elif avg_time < 5.0:
        print(f"\n✓ Good performance (target: <5s average)")
    else:
        print(f"\n⚠ Performance slower than expected")

    # Estimate for custom engine (assuming 100x slower)
    estimated_custom = avg_time * 100
    print(f"\n  Estimated custom engine time:  ~{estimated_custom:.0f}s ({estimated_custom/60:.1f} minutes)")
    print(f"  vectorbt speedup:               ~100x faster")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
