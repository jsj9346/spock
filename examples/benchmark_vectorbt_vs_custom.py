"""
Benchmark: vectorbt vs Custom Event-Driven Engine

Compares performance of vectorized (vectorbt) vs event-driven (custom) backtesting.

Expected Results:
    - vectorbt: <1 second (vectorized numpy operations)
    - Custom engine: ~30 seconds (sequential event processing)
    - Speedup: ~100x

Usage:
    python3 examples/benchmark_vectorbt_vs_custom.py
"""

import sys
import time
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engine import BacktestEngine
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager


def benchmark_custom_engine(config, data_provider):
    """Benchmark custom event-driven backtest engine."""
    print("\n" + "="*70)
    print("CUSTOM EVENT-DRIVEN ENGINE")
    print("="*70)

    start_time = time.time()

    # Create engine
    engine = BacktestEngine(config, data_provider=data_provider)

    # Run backtest
    result = engine.run()

    execution_time = time.time() - start_time

    print(f"\n✓ Backtest completed")
    print(f"  Execution time: {execution_time:.3f}s")
    print(f"  Total trades: {len(result.get('trades', []))}")
    print(f"  Final portfolio value: ${result.get('final_portfolio_value', 0):,.2f}")

    return execution_time, result


def benchmark_vectorbt_engine(config, data_provider):
    """Benchmark vectorbt vectorized engine."""
    print("\n" + "="*70)
    print("VECTORBT VECTORIZED ENGINE")
    print("="*70)

    start_time = time.time()

    # Create adapter
    adapter = VectorbtAdapter(config, data_provider)

    # Run backtest
    result = adapter.run()

    execution_time = time.time() - start_time

    print(f"\n✓ Backtest completed")
    print(f"  Execution time: {result.execution_time:.3f}s")
    print(f"  Total trades: {result.total_trades}")
    print(f"  Total return: {result.total_return:.2%}")
    print(f"  Sharpe ratio: {result.sharpe_ratio:.2f}")
    print(f"  Max drawdown: {result.max_drawdown:.2%}")

    return result.execution_time, result


def main():
    """Run performance benchmark."""
    print("\n" + "="*70)
    print("BACKTESTING ENGINE PERFORMANCE BENCHMARK")
    print("="*70)

    # Configuration
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'

    if not db_path.exists():
        print(f"\n✗ Database not found: {db_path}")
        print("  Please ensure spock_local.db exists with OHLCV data")
        return

    # Backtest parameters (1-year timeframe)
    config = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2025, 10, 20),  # ~1 year
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000020', '000040', '000050'],  # 3 tickers for realistic test
        max_position_size=0.15,
        score_threshold=60.0,
        risk_profile='moderate',
        commission_rate=0.00015,
        slippage_bps=5.0
    )

    print(f"\nConfiguration:")
    print(f"  Date range: {config.start_date} to {config.end_date}")
    print(f"  Tickers: {', '.join(config.tickers)}")
    print(f"  Initial capital: ${config.initial_capital:,}")
    print(f"  Database: {db_path.name}")

    # Create database manager and data provider
    db_manager = SQLiteDatabaseManager(str(db_path))
    data_provider = SQLiteDataProvider(db_manager)

    # Benchmark 1: Custom Event-Driven Engine
    try:
        custom_time, custom_result = benchmark_custom_engine(config, data_provider)
    except Exception as e:
        print(f"\n✗ Custom engine failed: {e}")
        custom_time = None
        custom_result = None

    # Benchmark 2: vectorbt Vectorized Engine
    try:
        vectorbt_time, vectorbt_result = benchmark_vectorbt_engine(config, data_provider)
    except Exception as e:
        print(f"\n✗ vectorbt engine failed: {e}")
        vectorbt_time = None
        vectorbt_result = None

    # Results summary
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON")
    print("="*70)

    if custom_time and vectorbt_time:
        speedup = custom_time / vectorbt_time
        print(f"\nExecution Time:")
        print(f"  Custom engine:  {custom_time:>8.3f}s")
        print(f"  vectorbt:       {vectorbt_time:>8.3f}s")
        print(f"  Speedup:        {speedup:>8.1f}x")

        if speedup >= 50:
            print(f"\n✓ vectorbt is {speedup:.0f}x faster (target: 100x)")
        elif speedup >= 10:
            print(f"\n⚠ vectorbt is {speedup:.0f}x faster (below 100x target)")
        else:
            print(f"\n✗ vectorbt speedup lower than expected ({speedup:.1f}x)")
    else:
        print("\n✗ Could not compare - one or both engines failed")

    # Trade comparison (if both succeeded)
    if custom_result and vectorbt_result:
        custom_trades = len(custom_result.get('trades', []))
        vectorbt_trades = vectorbt_result.total_trades

        print(f"\nTrade Count:")
        print(f"  Custom engine:  {custom_trades:>8}")
        print(f"  vectorbt:       {vectorbt_trades:>8}")

        if abs(custom_trades - vectorbt_trades) <= 2:
            print(f"  ✓ Trade counts similar (difference: {abs(custom_trades - vectorbt_trades)})")
        else:
            print(f"  ⚠ Trade count mismatch (difference: {abs(custom_trades - vectorbt_trades)})")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
