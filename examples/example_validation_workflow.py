"""
Validation Framework Example - Complete Validation Workflow

Demonstrates comprehensive usage of the Phase 3 Engine Validation Framework,
including cross-validation, regression testing, performance tracking, and
walk-forward optimization.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 examples/example_validation_workflow.py
"""

import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator
from modules.backtesting.backtest_engines.vectorbt_adapter import VECTORBT_AVAILABLE

# Phase 3 Validation Framework
from modules.backtesting.validation import (
    EngineValidator,
    RegressionTester,
    PerformanceTracker,
    ConsistencyMonitor,
    ValidationReportGenerator
)
from modules.backtesting.optimization import WalkForwardOptimizer


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print(f"{'='*70}\n")


def main():
    """Run validation framework examples."""
    print_section("VALIDATION FRAMEWORK EXAMPLES - Phase 3")

    # Check vectorbt availability
    if not VECTORBT_AVAILABLE:
        print("✗ vectorbt not available. Please install: pip install vectorbt")
        return

    # Database setup
    db_path = Path(__file__).parent.parent / 'data' / 'spock_local.db'

    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        return

    print(f"📁 Database: {db_path.name}")

    # Create data provider
    db_manager = SQLiteDatabaseManager(str(db_path))
    data_provider = SQLiteDataProvider(db_manager)

    # Configuration
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

    # ========================================================================
    # Example 1: Engine Validation
    # ========================================================================

    print_section("Example 1: Cross-Engine Validation")

    validator = EngineValidator(config, data_provider)

    print("🔍 Validating RSI strategy...")
    try:
        report = validator.validate(
            signal_generator=rsi_signal_generator,
            tolerance=0.05
        )

        print(f"\n📋 Validation Report:")
        print(f"  Status:              {'✅ PASSED' if report.validation_passed else '❌ FAILED'}")
        print(f"  Consistency Score:   {report.consistency_score:.1%}")
        print(f"  Discrepancies:       {len(report.discrepancies)} found")

        print(f"\n💡 Recommendations:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec}")

    except Exception as e:
        print(f"⚠️  Validation skipped: {e}")
        print("   (Custom engine requires full SQLite schema)")

    # ========================================================================
    # Example 2: Batch Validation
    # ========================================================================

    print_section("Example 2: Batch Validation (Multiple Strategies)")

    print("🔍 Validating multiple signal generators...")
    try:
        results = validator.validate_multiple(
            signal_generators=[rsi_signal_generator, macd_signal_generator],
            tolerance=0.05
        )

        print(f"\n📊 Batch Results:")
        for name, report in results.items():
            status = "✅ PASSED" if report.validation_passed else "❌ FAILED"
            print(f"  {name:30s} {status}  Consistency: {report.consistency_score:.1%}")

    except Exception as e:
        print(f"⚠️  Batch validation skipped: {e}")

    # ========================================================================
    # Example 3: Regression Testing
    # ========================================================================

    print_section("Example 3: Regression Testing")

    print("📦 Setting up regression testing...")
    reference_dir = Path(__file__).parent.parent / 'tests' / 'validation' / 'references'
    reference_dir.mkdir(parents=True, exist_ok=True)

    tester = RegressionTester(config, data_provider, reference_dir=reference_dir)

    # Create reference result
    print("\n1️⃣  Creating reference result for RSI strategy...")
    try:
        reference = tester.create_reference(
            test_name="rsi_strategy_baseline",
            signal_generator=rsi_signal_generator,
            description="RSI strategy baseline (30/70 thresholds)",
            tags=['rsi', 'mean_reversion', 'baseline'],
            overwrite=True  # Overwrite if exists
        )

        print(f"   ✅ Reference created:")
        print(f"      Return:     {reference.total_return:.2%}")
        print(f"      Sharpe:     {reference.sharpe_ratio:.2f}")
        print(f"      Trades:     {reference.total_trades}")

    except Exception as e:
        print(f"   ⚠️  Reference creation failed: {e}")

    # Run regression test
    print("\n2️⃣  Running regression test...")
    try:
        result = tester.test_regression(
            test_name="rsi_strategy_baseline",
            signal_generator=rsi_signal_generator,
            tolerance=0.10  # 10% tolerance
        )

        status = "✅ PASSED" if result.passed else "❌ FAILED"
        print(f"\n   📋 Regression Test: {status}")
        print(f"      Return Deviation:  {result.return_deviation:+.2%}")
        print(f"      Sharpe Deviation:  {result.sharpe_deviation:+.2f}")
        print(f"      Trade Deviation:   {result.trade_count_deviation:+d}")

        if result.failures:
            print(f"\n   ⚠️  Failures:")
            for failure in result.failures:
                print(f"      - {failure}")

        if result.warnings:
            print(f"\n   💡 Warnings:")
            for warning in result.warnings:
                print(f"      - {warning}")

    except FileNotFoundError:
        print("   ⚠️  Reference not found")
    except Exception as e:
        print(f"   ⚠️  Regression test failed: {e}")

    # ========================================================================
    # Example 4: Performance Tracking
    # ========================================================================

    print_section("Example 4: Performance Tracking")

    print("⏱️  Tracking backtest performance...")
    tracker = PerformanceTracker()

    # Track RSI backtest
    from modules.backtesting.backtest_runner import BacktestRunner
    runner = BacktestRunner(config, data_provider)

    with tracker.track("rsi_backtest"):
        result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)

    # Get metrics
    metrics = tracker.get_latest("rsi_backtest")
    if metrics:
        print(f"\n📊 Performance Metrics:")
        print(f"  Execution Time:  {metrics.execution_time:.3f}s")
        print(f"  Memory Usage:    {metrics.memory_usage_mb:.1f} MB")
        print(f"  CPU Usage:       {metrics.cpu_percent:.1f}%")
        print(f"  Success:         {'✅' if metrics.success else '❌'}")

    # ========================================================================
    # Example 5: Consistency Monitoring
    # ========================================================================

    print_section("Example 5: Consistency Monitoring")

    print("🔍 Real-time consistency monitoring...")
    monitor = ConsistencyMonitor(config, data_provider, alert_threshold=0.90)

    try:
        status = monitor.check_consistency(rsi_signal_generator, tolerance=0.05)

        print(f"\n📊 Consistency Status:")
        print(f"  Status:       {status['message']}")
        print(f"  Consistency:  {status['consistency_score']:.1%}")
        print(f"  Alert:        {'🚨 YES' if not status['passed'] else '✅ NO'}")

    except Exception as e:
        print(f"⚠️  Monitoring skipped: {e}")

    # ========================================================================
    # Example 6: Validation Report Generation
    # ========================================================================

    print_section("Example 6: Validation Report Generation")

    print("📄 Generating validation report...")

    # Get validation history
    history = validator.get_validation_history(limit=10)

    if history:
        generator = ValidationReportGenerator()
        markdown_report = generator.generate_markdown(history)

        # Save report
        report_path = Path(__file__).parent.parent / 'logs' / 'validation_report.md'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        generator.save_markdown(markdown_report, report_path)

        print(f"\n✅ Report generated: {report_path}")
        print(f"   Total validations: {len(history)}")
        print(f"   Report preview:")
        print("   " + "\n   ".join(markdown_report.split("\n")[:15]))
    else:
        print("⚠️  No validation history available")

    # ========================================================================
    # Summary
    # ========================================================================

    print_section("Summary & Next Steps")

    print("✅ Phase 3 Validation Framework Complete:")
    print("   1. Cross-engine validation with consistency scoring")
    print("   2. Automated regression testing")
    print("   3. Performance tracking and profiling")
    print("   4. Real-time consistency monitoring")
    print("   5. Validation report generation")

    print("\n📚 Framework Components:")
    print("   - EngineValidator: Cross-validation between engines")
    print("   - RegressionTester: Automated regression detection")
    print("   - PerformanceTracker: Performance benchmarking")
    print("   - ConsistencyMonitor: Real-time monitoring")
    print("   - ValidationReportGenerator: Comprehensive reports")
    print("   - WalkForwardOptimizer: Time-series cross-validation")

    print("\n🎯 Usage Patterns:")
    print("   1. Validate strategies before deployment")
    print("   2. Create reference results for CI/CD")
    print("   3. Monitor performance regressions")
    print("   4. Track consistency across versions")
    print("   5. Generate validation reports for stakeholders")

    print("\n💡 Best Practices:")
    print("   - Run validation on every strategy change")
    print("   - Maintain reference results for all production strategies")
    print("   - Monitor consistency scores (target: >0.95)")
    print("   - Use walk-forward optimization to prevent overfitting")
    print("   - Track performance metrics over time")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
