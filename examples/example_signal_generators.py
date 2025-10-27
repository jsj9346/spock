"""
Signal Generator Examples

Demonstrates how to use RSI, MACD, and Bollinger Bands signal generators
with the vectorbt backtesting engine.

Usage:
    python3 examples/example_signal_generators.py
"""

import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter, VECTORBT_AVAILABLE
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Import all signal generators
from modules.backtesting.signal_generators.rsi_strategy import (
    rsi_signal_generator,
    rsi_mean_reversion_signal_generator
)
from modules.backtesting.signal_generators.macd_strategy import (
    macd_signal_generator,
    macd_histogram_signal_generator,
    macd_trend_following_signal_generator
)
from modules.backtesting.signal_generators.bollinger_bands_strategy import (
    bb_signal_generator,
    bb_breakout_signal_generator,
    bb_squeeze_signal_generator,
    bb_dual_threshold_signal_generator
)


def run_strategy(name, signal_generator, config, data_provider):
    """Run backtest with given signal generator."""
    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")

    # Create adapter
    adapter = VectorbtAdapter(config, data_provider, signal_generator=signal_generator)

    # Run backtest
    result = adapter.run()

    # Display results
    print(f"\n📊 Performance Metrics:")
    print(f"  Total Return:        {result.total_return:>10.2%}")
    print(f"  Sharpe Ratio:        {result.sharpe_ratio:>10.2f}")
    print(f"  Max Drawdown:        {result.max_drawdown:>10.2%}")
    print(f"  Win Rate:            {result.win_rate:>10.2%}")
    print(f"  Total Trades:        {result.total_trades:>10}")
    print(f"  Execution Time:      {result.execution_time:>10.3f}s")

    return result


def main():
    """Run example backtests with different signal generators."""
    print("\n" + "="*70)
    print("SIGNAL GENERATOR EXAMPLES")
    print("="*70)

    # Check vectorbt availability
    if not VECTORBT_AVAILABLE:
        print("\n✗ vectorbt not available. Please install: pip install vectorbt")
        return

    # Database setup
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'

    if not db_path.exists():
        print(f"\n✗ Database not found: {db_path}")
        print("  Please ensure spock_local.db exists with OHLCV data")
        return

    print(f"\n📁 Database: {db_path.name}")

    # Create data provider
    db_manager = SQLiteDatabaseManager(str(db_path))
    data_provider = SQLiteDataProvider(db_manager)

    # Base configuration (3-month backtest)
    base_config = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2024, 12, 31),
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000020'],  # Single ticker for comparison
        max_position_size=0.15,
        score_threshold=60.0,
        risk_profile='moderate',
        commission_rate=0.00015,
        slippage_bps=5.0
    )

    print(f"\n⚙️  Configuration:")
    print(f"  Period:        {base_config.start_date} to {base_config.end_date}")
    print(f"  Tickers:       {', '.join(base_config.tickers)}")
    print(f"  Capital:       ${base_config.initial_capital:,}")

    results = {}

    # ========================================================================
    # RSI Strategies
    # ========================================================================

    # 1. Standard RSI Oversold/Overbought
    results['RSI Standard'] = run_strategy(
        "1. RSI Standard Strategy (Oversold/Overbought)",
        rsi_signal_generator,
        base_config,
        data_provider
    )

    # 2. RSI Mean Reversion
    results['RSI Mean Reversion'] = run_strategy(
        "2. RSI Mean Reversion Strategy",
        rsi_mean_reversion_signal_generator,
        base_config,
        data_provider
    )

    # ========================================================================
    # MACD Strategies
    # ========================================================================

    # 3. Standard MACD Crossover
    results['MACD Crossover'] = run_strategy(
        "3. MACD Crossover Strategy",
        macd_signal_generator,
        base_config,
        data_provider
    )

    # 4. MACD Histogram
    results['MACD Histogram'] = run_strategy(
        "4. MACD Histogram Zero-Cross Strategy",
        macd_histogram_signal_generator,
        base_config,
        data_provider
    )

    # 5. MACD Trend Following (filtered)
    results['MACD Trend'] = run_strategy(
        "5. MACD Trend Following Strategy (Filtered)",
        macd_trend_following_signal_generator,
        base_config,
        data_provider
    )

    # ========================================================================
    # Bollinger Bands Strategies
    # ========================================================================

    # 6. Bollinger Bands Mean Reversion
    results['BB Mean Reversion'] = run_strategy(
        "6. Bollinger Bands Mean Reversion Strategy",
        bb_signal_generator,
        base_config,
        data_provider
    )

    # 7. Bollinger Bands Breakout
    results['BB Breakout'] = run_strategy(
        "7. Bollinger Bands Breakout Strategy",
        bb_breakout_signal_generator,
        base_config,
        data_provider
    )

    # 8. Bollinger Bands Squeeze
    results['BB Squeeze'] = run_strategy(
        "8. Bollinger Bands Squeeze Strategy",
        bb_squeeze_signal_generator,
        base_config,
        data_provider
    )

    # 9. Bollinger Bands Dual Threshold
    results['BB Dual Threshold'] = run_strategy(
        "9. Bollinger Bands Dual Threshold Strategy (%B)",
        bb_dual_threshold_signal_generator,
        base_config,
        data_provider
    )

    # ========================================================================
    # Results Comparison
    # ========================================================================

    print("\n" + "="*70)
    print("STRATEGY COMPARISON")
    print("="*70)

    # Sort by Sharpe Ratio
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1].sharpe_ratio if x[1].sharpe_ratio is not None else -999,
        reverse=True
    )

    print(f"\n{'Strategy':<30} {'Return':>10} {'Sharpe':>8} {'Trades':>8} {'Win Rate':>10}")
    print("-" * 70)

    for name, result in sorted_results:
        print(
            f"{name:<30} "
            f"{result.total_return:>10.2%} "
            f"{result.sharpe_ratio:>8.2f} "
            f"{result.total_trades:>8} "
            f"{result.win_rate:>10.2%}"
        )

    # Best strategy
    best_name, best_result = sorted_results[0]
    print(f"\n🏆 Best Strategy: {best_name}")
    print(f"   Sharpe Ratio: {best_result.sharpe_ratio:.2f}")
    print(f"   Total Return: {best_result.total_return:.2%}")
    print(f"   Max Drawdown: {best_result.max_drawdown:.2%}")

    print("\n" + "="*70)

    # Strategy Recommendations
    print("\n💡 Strategy Characteristics:")
    print("\nMean Reversion (Good for ranging markets):")
    print("  - RSI Mean Reversion")
    print("  - BB Mean Reversion")
    print("  - BB Dual Threshold")

    print("\nTrend Following (Good for trending markets):")
    print("  - MACD Crossover")
    print("  - MACD Trend Following")
    print("  - BB Breakout")

    print("\nVolatility-Based (Good for volatility trading):")
    print("  - BB Squeeze")
    print("  - MACD Histogram")

    print("\nMomentum Indicators:")
    print("  - RSI Standard")
    print("  - All MACD variants")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
