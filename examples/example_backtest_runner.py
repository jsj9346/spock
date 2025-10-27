"""
BacktestRunner Example - Unified Backtesting Interface

Demonstrates how to use BacktestRunner to:
1. Run backtests with vectorbt engine (fast research)
2. Run backtests with custom engine (production accuracy)
3. Compare both engines for validation
4. Validate engine consistency
5. Benchmark performance differences

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 examples/example_backtest_runner.py
"""

import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator
from modules.backtesting.backtest_engines.vectorbt_adapter import VECTORBT_AVAILABLE


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}\n")


def main():
    """Run BacktestRunner examples."""
    print_section("BACKTEST RUNNER EXAMPLES")

    # Check vectorbt availability
    if not VECTORBT_AVAILABLE:
        print("✗ vectorbt not available. Please install: pip install vectorbt")
        return

    # Database setup
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'

    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        print("  Please ensure spock_local.db exists with OHLCV data")
        return

    print(f"📁 Database: {db_path.name}")

    # Create data provider
    db_manager = SQLiteDatabaseManager(str(db_path))
    data_provider = SQLiteDataProvider(db_manager)

    # Base configuration
    config = BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2024, 12, 31),
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000020'],
        max_position_size=0.15,
        score_threshold=60.0,
        risk_profile='moderate',
        commission_rate=0.00015,
        slippage_bps=5.0
    )

    print(f"\n⚙️  Configuration:")
    print(f"  Period:        {config.start_date} to {config.end_date}")
    print(f"  Tickers:       {', '.join(config.tickers)}")
    print(f"  Capital:       ${config.initial_capital:,}")

    # Initialize BacktestRunner
    runner = BacktestRunner(config, data_provider)

    # ========================================================================
    # Example 1: Run with vectorbt (Fast Research)
    # ========================================================================

    print_section("Example 1: vectorbt Engine (Fast Research)")

    result_vbt = runner.run(
        engine='vectorbt',
        signal_generator=rsi_signal_generator
    )

    print("📊 vectorbt Results:")
    print(f"  Total Return:        {result_vbt.total_return:>10.2%}")
    print(f"  Sharpe Ratio:        {result_vbt.sharpe_ratio:>10.2f}")
    print(f"  Max Drawdown:        {result_vbt.max_drawdown:>10.2%}")
    print(f"  Win Rate:            {result_vbt.win_rate:>10.2%}")
    print(f"  Total Trades:        {result_vbt.total_trades:>10}")
    print(f"  Execution Time:      {result_vbt.execution_time:>10.3f}s")

    # ========================================================================
    # Example 2: Different Signal Generators
    # ========================================================================

    print_section("Example 2: Different Signal Generators")

    # RSI Strategy
    print("🔍 RSI Strategy (Oversold/Overbought)")
    rsi_result = runner.run(
        engine='vectorbt',
        signal_generator=rsi_signal_generator
    )
    print(f"  Return: {rsi_result.total_return:>8.2%}  |  Sharpe: {rsi_result.sharpe_ratio:>6.2f}  |  Trades: {rsi_result.total_trades:>4}")

    # MACD Strategy
    print("\n🔍 MACD Strategy (Trend Following)")
    macd_result = runner.run(
        engine='vectorbt',
        signal_generator=macd_signal_generator
    )
    print(f"  Return: {macd_result.total_return:>8.2%}  |  Sharpe: {macd_result.sharpe_ratio:>6.2f}  |  Trades: {macd_result.total_trades:>4}")

    # ========================================================================
    # Example 3: Engine Validation
    # ========================================================================

    print_section("Example 3: Engine Validation")

    print("⚖️  Validating consistency between engines...")
    print("   (This compares custom event-driven vs vectorbt vectorized)")

    try:
        validation_report = runner.validate_consistency(
            signal_generator=rsi_signal_generator,
            tolerance=0.05  # 5% tolerance
        )

        print(f"\n📋 Validation Report:")
        print(f"  Status:              {'✅ PASSED' if validation_report.validation_passed else '❌ FAILED'}")
        print(f"  Consistency Score:   {validation_report.consistency_score:.1%}")
        print(f"  Discrepancies:       {len(validation_report.discrepancies)} found")
        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(validation_report.recommendations, 1):
            print(f"  {i}. {rec}")

    except Exception as e:
        print(f"⚠️  Validation skipped: {e}")
        print("   (Custom engine requires full SQLite schema with technical indicators)")

    # ========================================================================
    # Example 4: Performance Benchmark
    # ========================================================================

    print_section("Example 4: Performance Benchmark")

    print("⏱️  Benchmarking engine performance...")

    try:
        perf_report = runner.benchmark_performance(
            signal_generator=rsi_signal_generator
        )

        print(f"\n📊 Performance Report:")
        print(f"  Custom Engine:       {perf_report.custom_time:>10.3f}s")
        print(f"  vectorbt Engine:     {perf_report.vectorbt_time:>10.3f}s")
        print(f"  Speedup Factor:      {perf_report.speedup_factor:>10.1f}x")
        print(f"  Throughput:          {perf_report.throughput_days_per_sec:>10.0f} days/s")
        print(f"  Memory Usage:        {perf_report.memory_usage_mb:>10.0f} MB (estimated)")

        print(f"\n💡 Performance Insight:")
        if perf_report.speedup_factor > 10:
            print(f"  vectorbt is {perf_report.speedup_factor:.0f}x faster - ideal for parameter optimization")
        elif perf_report.speedup_factor > 5:
            print(f"  vectorbt is {perf_report.speedup_factor:.0f}x faster - good for research iterations")
        else:
            print(f"  Similar performance - both engines suitable")

    except Exception as e:
        print(f"⚠️  Benchmark skipped: {e}")
        print("   (Custom engine requires full SQLite schema with technical indicators)")

    # ========================================================================
    # Summary
    # ========================================================================

    print_section("Summary & Recommendations")

    print("✅ BacktestRunner provides unified interface for:")
    print("   - Fast research with vectorbt (100x faster parameter optimization)")
    print("   - Production accuracy with custom engine (event-driven, no look-ahead)")
    print("   - Automatic validation and performance benchmarking")
    print("\n📚 Usage Patterns:")
    print("   1. Use vectorbt for strategy research and parameter optimization")
    print("   2. Validate with custom engine before production deployment")
    print("   3. Monitor consistency score (should be >0.95 for good strategies)")
    print("   4. Use validation reports to identify signal generator issues")
    print("\n🎯 Next Steps:")
    print("   - Explore different signal generators (see examples/example_signal_generators.py)")
    print("   - Implement custom signal generators with your trading logic")
    print("   - Use walk-forward optimization for robust parameter selection")
    print("   - Monitor performance metrics across different market regimes")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
