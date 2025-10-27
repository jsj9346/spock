# Validation Framework Guide - Phase 3

Comprehensive guide to the backtesting engine validation and quality assurance framework.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Usage Patterns](#usage-patterns)
5. [Integration Guide](#integration-guide)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Validation Framework provides comprehensive quality assurance for backtesting operations, ensuring:

- **Cross-Engine Consistency**: Validate that vectorbt and custom engine produce similar results
- **Regression Prevention**: Automated detection of performance degradations
- **Performance Monitoring**: Track execution time, memory usage, and CPU utilization
- **Real-Time Alerts**: Monitor consistency scores and alert on threshold violations
- **Historical Tracking**: Maintain validation history for trend analysis

### Key Features

- ✅ **Automated Validation**: Cross-engine comparison with configurable tolerance
- ✅ **Reference Testing**: Create and test against reference results
- ✅ **Performance Profiling**: Context manager pattern for automatic tracking
- ✅ **Consistency Monitoring**: Real-time monitoring with alert thresholds
- ✅ **Report Generation**: Markdown reports for stakeholder communication

### Framework Components

**Validation Framework** (`modules/backtesting/validation/`):
- `EngineValidator` - Cross-engine validation with consistency scoring
- `RegressionTester` - Automated regression testing framework
- `PerformanceTracker` - Performance monitoring and profiling
- `ConsistencyMonitor` - Real-time consistency monitoring
- `ValidationReportGenerator` - Report generation in Markdown

**Optimization Framework** (`modules/backtesting/optimization/`):
- `WalkForwardOptimizer` - Time-series cross-validation
- `ParameterScanner` - Grid search and sensitivity analysis
- `OverfittingDetector` - Overfitting detection and robustness scoring

---

## Architecture

### Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                  Validation Framework                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ EngineValidator  │───→│ BacktestRunner   │             │
│  │                  │    │ (Phase 2)        │             │
│  │ - validate()     │    │                  │             │
│  │ - validate_multi │    │ - run()          │             │
│  │ - get_history()  │    │ - validate()     │             │
│  └──────────────────┘    └──────────────────┘             │
│         │                                                   │
│         ├─→ ValidationMetrics (dataclass)                  │
│         └─→ ValidationReport (dataclass)                   │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │RegressionTester  │    │PerformanceTracker│             │
│  │                  │    │                  │             │
│  │ - create_ref()   │    │ - track()        │             │
│  │ - test_regress() │    │ - get_latest()   │             │
│  │ - list_refs()    │    │ - get_average()  │             │
│  └──────────────────┘    └──────────────────┘             │
│         │                         │                         │
│         ├─→ ReferenceResult       ├─→ PerformanceMetrics   │
│         └─→ RegressionTestResult  └─→ context manager      │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ConsistencyMonitor│    │ValidationReport  │             │
│  │                  │    │Generator         │             │
│  │ - check()        │    │                  │             │
│  │ - alert()        │    │ - markdown()     │             │
│  └──────────────────┘    │ - save()         │             │
│                          └──────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Request
    │
    ▼
┌────────────────────┐
│ EngineValidator    │
│ validate()         │
└────────┬───────────┘
         │
         ├─→ Run Custom Engine    ─┐
         └─→ Run vectorbt Engine   ─┤
                                    │
                            ┌───────▼────────┐
                            │ Compare Results│
                            │ - Returns      │
                            │ - Sharpe       │
                            │ - Drawdown     │
                            │ - Trade Count  │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │Consistency Score│
                            │ 0.0 - 1.0      │
                            └───────┬────────┘
                                    │
                            ┌───────▼────────┐
                            │ValidationReport│
                            │ + Recommends   │
                            └────────────────┘
```

---

## Core Components

### 1. EngineValidator

**Purpose**: Cross-validate vectorbt and custom engine results

**Location**: `modules/backtesting/validation/engine_validator.py`

#### Key Classes

```python
@dataclass
class ValidationMetrics:
    """Detailed validation metrics for a single run."""
    timestamp: datetime
    signal_generator_name: str
    config_hash: str

    # Engine results
    custom_total_return: float
    custom_sharpe_ratio: float
    custom_max_drawdown: float
    custom_total_trades: int
    custom_execution_time: float

    vectorbt_total_return: float
    vectorbt_sharpe_ratio: float
    vectorbt_max_drawdown: float
    vectorbt_total_trades: int
    vectorbt_execution_time: float

    # Consistency metrics
    consistency_score: float
    return_difference: float
    sharpe_difference: float
    drawdown_difference: float
    trade_count_difference: int
    speedup_factor: float

    # Validation results
    validation_passed: bool
    tolerance_used: float
    discrepancies: Dict[str, Any]
    recommendations: List[str]
```

#### Basic Usage

```python
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.backtesting.validation import EngineValidator
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator

# Configuration
config = BacktestConfig(
    start_date=date(2024, 10, 10),
    end_date=date(2024, 12, 31),
    initial_capital=10000000,
    regions=['KR'],
    tickers=['000020']
)

# Create validator
validator = EngineValidator(config, data_provider)

# Single validation
report = validator.validate(
    signal_generator=rsi_signal_generator,
    tolerance=0.05  # 5% tolerance
)

print(f"Validation: {'✅ PASSED' if report.validation_passed else '❌ FAILED'}")
print(f"Consistency: {report.consistency_score:.1%}")
print(f"Discrepancies: {len(report.discrepancies)}")
```

#### Batch Validation

```python
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator

# Validate multiple strategies
results = validator.validate_multiple(
    signal_generators=[rsi_signal_generator, macd_signal_generator],
    tolerance=0.05
)

for name, report in results.items():
    status = "✅ PASSED" if report.validation_passed else "❌ FAILED"
    print(f"{name:30s} {status}  Consistency: {report.consistency_score:.1%}")
```

#### Validation History

```python
# Get all validation history
history = validator.get_validation_history()

# Filter by signal generator
rsi_history = validator.get_validation_history(
    signal_generator_name='rsi_signal_generator'
)

# Get recent validations
recent = validator.get_validation_history(limit=10)

# Analyze trend
avg_consistency = sum(m.consistency_score for m in recent) / len(recent)
print(f"Average consistency (last 10): {avg_consistency:.1%}")
```

#### Consistency Scoring Algorithm

The consistency score is calculated as a weighted average:

```python
consistency_score = (
    0.4 * (1 - abs(return_diff) / max(abs(custom_return), abs(vectorbt_return))) +
    0.3 * (1 - abs(trade_diff) / max(custom_trades, vectorbt_trades)) +
    0.2 * (1 - abs(sharpe_diff) / max(abs(custom_sharpe), abs(vectorbt_sharpe))) +
    0.1 * (1 - abs(drawdown_diff) / max(abs(custom_dd), abs(vectorbt_dd)))
)
```

**Weight Rationale**:
- **Return (40%)**: Most important metric for strategy performance
- **Trade Count (30%)**: Critical for statistical significance
- **Sharpe Ratio (20%)**: Risk-adjusted performance indicator
- **Max Drawdown (10%)**: Risk metric, less sensitive to small variations

---

### 2. RegressionTester

**Purpose**: Automated regression testing against reference results

**Location**: `modules/backtesting/validation/regression_tester.py`

#### Key Classes

```python
@dataclass
class ReferenceResult:
    """Reference backtest result for regression testing."""
    test_name: str
    signal_generator_name: str
    created_at: datetime
    config_hash: str
    description: str
    tags: List[str]

    # Performance metrics
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_trade_duration: float
    execution_time: float

@dataclass
class RegressionTestResult:
    """Result from regression test."""
    test_name: str
    timestamp: datetime
    passed: bool

    # Current vs reference
    current_total_return: float
    reference_total_return: float
    return_deviation: float

    current_sharpe_ratio: float
    reference_sharpe_ratio: float
    sharpe_deviation: float

    current_total_trades: int
    reference_total_trades: int
    trade_count_deviation: int

    # Test results
    tolerance_used: float
    failures: List[str]
    warnings: List[str]
```

#### Creating Reference Results

```python
from modules.backtesting.validation import RegressionTester

# Create tester
tester = RegressionTester(config, data_provider)

# Create reference result
reference = tester.create_reference(
    test_name="rsi_strategy_baseline",
    signal_generator=rsi_signal_generator,
    description="RSI strategy baseline (30/70 thresholds)",
    tags=['rsi', 'mean_reversion', 'baseline'],
    overwrite=True  # Overwrite if exists
)

print(f"Reference created:")
print(f"  Return:     {reference.total_return:.2%}")
print(f"  Sharpe:     {reference.sharpe_ratio:.2f}")
print(f"  Trades:     {reference.total_trades}")
```

#### Running Regression Tests

```python
# Test against reference
result = tester.test_regression(
    test_name="rsi_strategy_baseline",
    signal_generator=rsi_signal_generator,
    tolerance=0.10  # 10% tolerance
)

status = "✅ PASSED" if result.passed else "❌ FAILED"
print(f"\nRegression Test: {status}")
print(f"  Return Deviation:  {result.return_deviation:+.2%}")
print(f"  Sharpe Deviation:  {result.sharpe_deviation:+.2f}")
print(f"  Trade Deviation:   {result.trade_count_deviation:+d}")

if result.failures:
    print(f"\n⚠️  Failures:")
    for failure in result.failures:
        print(f"  - {failure}")

if result.warnings:
    print(f"\n💡 Warnings:")
    for warning in result.warnings:
        print(f"  - {warning}")
```

#### Managing References

```python
# List all references
references = tester.list_references()
print(f"\nAvailable references: {len(references)}")
for ref in references:
    print(f"  - {ref.test_name} ({ref.signal_generator_name})")
    print(f"    Created: {ref.created_at}")
    print(f"    Tags: {', '.join(ref.tags)}")

# Filter by tags
rsi_refs = [r for r in references if 'rsi' in r.tags]
```

#### Reference Storage

References are stored as JSON files in the reference directory (default: `tests/validation/references/`):

```
tests/validation/references/
    rsi_strategy_baseline.json
    macd_strategy_baseline.json
    momentum_value_strategy.json
```

**JSON Structure**:
```json
{
  "test_name": "rsi_strategy_baseline",
  "signal_generator_name": "rsi_signal_generator",
  "created_at": "2025-10-27T10:30:00",
  "config_hash": "abc123...",
  "description": "RSI strategy baseline (30/70 thresholds)",
  "tags": ["rsi", "mean_reversion", "baseline"],
  "total_return": 0.1234,
  "sharpe_ratio": 1.56,
  "max_drawdown": -0.0987,
  "win_rate": 0.55,
  "total_trades": 25,
  "avg_trade_duration": 5.2,
  "execution_time": 1.234
}
```

---

### 3. PerformanceTracker

**Purpose**: Monitor execution time, memory usage, and CPU utilization

**Location**: `modules/backtesting/validation/performance_tracker.py`

#### Basic Usage

```python
from modules.backtesting.validation import PerformanceTracker

tracker = PerformanceTracker()

# Context manager pattern
with tracker.track("rsi_backtest"):
    result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)

# Get latest metrics
metrics = tracker.get_latest("rsi_backtest")
if metrics:
    print(f"\nPerformance Metrics:")
    print(f"  Execution Time:  {metrics.execution_time:.3f}s")
    print(f"  Memory Usage:    {metrics.memory_usage_mb:.1f} MB")
    print(f"  CPU Usage:       {metrics.cpu_percent:.1f}%")
    print(f"  Success:         {'✅' if metrics.success else '❌'}")
```

#### Averaging Multiple Runs

```python
# Run multiple times
for i in range(5):
    with tracker.track("rsi_backtest"):
        result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)

# Get average metrics
avg = tracker.get_average("rsi_backtest")
print(f"\nAverage Performance (5 runs):")
print(f"  Execution Time:  {avg['execution_time']:.3f}s ± {avg['execution_time_std']:.3f}s")
print(f"  Memory Usage:    {avg['memory_usage_mb']:.1f} MB ± {avg['memory_usage_mb_std']:.1f} MB")
print(f"  CPU Usage:       {avg['cpu_percent']:.1f}%")
```

#### Performance Metrics Class

```python
@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation."""
    operation_name: str
    timestamp: datetime
    execution_time: float  # seconds
    memory_usage_mb: float  # MB
    cpu_percent: float  # percentage
    success: bool
    error_message: Optional[str] = None
```

---

### 4. ConsistencyMonitor

**Purpose**: Real-time consistency monitoring with alerts

**Location**: `modules/backtesting/validation/consistency_monitor.py`

#### Basic Usage

```python
from modules.backtesting.validation import ConsistencyMonitor

# Create monitor with alert threshold
monitor = ConsistencyMonitor(
    config=config,
    data_provider=data_provider,
    alert_threshold=0.90  # Alert if consistency <90%
)

# Check consistency
status = monitor.check_consistency(
    signal_generator=rsi_signal_generator,
    tolerance=0.05
)

print(f"\nConsistency Status:")
print(f"  Status:       {status['message']}")
print(f"  Consistency:  {status['consistency_score']:.1%}")
print(f"  Alert:        {'🚨 YES' if not status['passed'] else '✅ NO'}")
```

#### Alert Mechanism

The monitor automatically logs warnings when consistency falls below the threshold:

```python
# Example output when alert is triggered:
# WARNING - 🚨 Consistency alert: rsi_signal_generator scored 0.87 (below 0.90 threshold)
```

---

### 5. ValidationReportGenerator

**Purpose**: Generate comprehensive validation reports

**Location**: `modules/backtesting/validation/validation_report_generator.py`

#### Generating Reports

```python
from modules.backtesting.validation import ValidationReportGenerator

# Get validation history
history = validator.get_validation_history(limit=10)

# Generate report
generator = ValidationReportGenerator()
markdown_report = generator.generate_markdown(history)

# Save to file
report_path = Path('logs/validation_report.md')
generator.save_markdown(markdown_report, report_path)

print(f"✅ Report generated: {report_path}")
```

#### Report Structure

```markdown
# Validation Report

Generated: 2025-10-27 10:30:00

## Summary

- Total Validations: 10
- Passed: 9
- Failed: 1
- Pass Rate: 90.0%
- Average Consistency: 0.94

## Validation Results

### rsi_signal_generator (2025-10-27 10:25:00)

**Status**: ✅ PASSED
**Consistency Score**: 0.96

**Custom Engine**:
- Total Return: 12.34%
- Sharpe Ratio: 1.56
- Max Drawdown: -9.87%
- Total Trades: 25

**vectorbt Engine**:
- Total Return: 12.56%
- Sharpe Ratio: 1.58
- Max Drawdown: -9.45%
- Total Trades: 26

**Differences**:
- Return: +0.22%
- Sharpe: +0.02
- Drawdown: +0.42%
- Trades: +1

**Performance**:
- Speedup: 100.5x
- Custom Execution: 10.2s
- vectorbt Execution: 0.1s

**Recommendations**:
- Engines show good consistency
- vectorbt recommended for parameter optimization
```

---

## Usage Patterns

### Pattern 1: Strategy Development Workflow

```python
from modules.backtesting.validation import (
    EngineValidator,
    RegressionTester,
    PerformanceTracker
)

# 1. Develop strategy
def my_new_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
    # Strategy logic
    return buy_signals, sell_signals

# 2. Create reference result
tester = RegressionTester(config, data_provider)
reference = tester.create_reference(
    test_name="my_new_strategy_v1",
    signal_generator=my_new_strategy,
    description="Initial implementation",
    tags=['momentum', 'v1']
)

# 3. Validate cross-engine consistency
validator = EngineValidator(config, data_provider)
report = validator.validate(my_new_strategy, tolerance=0.05)

if not report.validation_passed:
    print("⚠️ Validation failed - check discrepancies")
    for key, value in report.discrepancies.items():
        print(f"  {key}: {value}")
else:
    print("✅ Validation passed")

# 4. Track performance
tracker = PerformanceTracker()
with tracker.track("my_new_strategy"):
    result = runner.run(engine='vectorbt', signal_generator=my_new_strategy)

metrics = tracker.get_latest("my_new_strategy")
print(f"Execution time: {metrics.execution_time:.2f}s")
```

### Pattern 2: CI/CD Integration

```python
# ci_validation.py - Run in CI pipeline

def validate_all_strategies():
    """Validate all strategies in CI/CD pipeline."""
    tester = RegressionTester(config, data_provider)

    strategies = [
        ('rsi_strategy', rsi_signal_generator),
        ('macd_strategy', macd_signal_generator),
        ('momentum_value', momentum_value_generator)
    ]

    failed = []
    for name, generator in strategies:
        try:
            result = tester.test_regression(
                test_name=f"{name}_baseline",
                signal_generator=generator,
                tolerance=0.10
            )

            if not result.passed:
                failed.append((name, result.failures))
        except Exception as e:
            failed.append((name, [str(e)]))

    if failed:
        print("❌ Regression tests failed:")
        for name, failures in failed:
            print(f"\n  {name}:")
            for failure in failures:
                print(f"    - {failure}")
        sys.exit(1)
    else:
        print("✅ All regression tests passed")
        sys.exit(0)

if __name__ == '__main__':
    validate_all_strategies()
```

### Pattern 3: Continuous Monitoring

```python
# monitoring_service.py - Production monitoring

def monitor_production_strategies():
    """Monitor production strategies continuously."""
    monitor = ConsistencyMonitor(
        config=config,
        data_provider=data_provider,
        alert_threshold=0.90
    )

    strategies = get_production_strategies()

    for strategy_name, generator in strategies:
        status = monitor.check_consistency(generator, tolerance=0.05)

        if not status['passed']:
            # Send alert via email/Slack/PagerDuty
            send_alert(
                title=f"Consistency Alert: {strategy_name}",
                message=f"Consistency score: {status['consistency_score']:.1%}",
                severity='warning'
            )

        # Log to metrics system (Prometheus)
        metrics.gauge(
            'strategy_consistency_score',
            status['consistency_score'],
            labels={'strategy': strategy_name}
        )
```

### Pattern 4: Performance Benchmarking

```python
# benchmark_engines.py

def benchmark_engines():
    """Benchmark different engines and configurations."""
    tracker = PerformanceTracker()

    # Test configurations
    configs = [
        ('vectorbt_default', 'vectorbt', {}),
        ('custom_default', 'custom', {}),
        ('vectorbt_optimized', 'vectorbt', {'cache': True})
    ]

    results = []
    for name, engine, options in configs:
        with tracker.track(name):
            result = runner.run(
                engine=engine,
                signal_generator=rsi_signal_generator,
                **options
            )

        metrics = tracker.get_latest(name)
        results.append({
            'name': name,
            'time': metrics.execution_time,
            'memory': metrics.memory_usage_mb,
            'cpu': metrics.cpu_percent
        })

    # Print comparison
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
```

---

## Integration Guide

### With BacktestRunner (Phase 2)

The validation framework integrates seamlessly with BacktestRunner:

```python
from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.validation import EngineValidator

# BacktestRunner already has validate_consistency() method
runner = BacktestRunner(config, data_provider)

# Direct validation
report = runner.validate_consistency(
    signal_generator=rsi_signal_generator,
    tolerance=0.05
)

# EngineValidator uses BacktestRunner internally
validator = EngineValidator(config, data_provider)
report = validator.validate(rsi_signal_generator, tolerance=0.05)
# Both produce identical ValidationReport objects
```

### With Signal Generators (Phase 2)

All signal generators from Phase 2 are compatible:

```python
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator
from modules.backtesting.signal_generators.bollinger_strategy import bollinger_signal_generator

# Validate any signal generator
strategies = [
    rsi_signal_generator,
    macd_signal_generator,
    bollinger_signal_generator
]

for strategy in strategies:
    report = validator.validate(strategy, tolerance=0.05)
    print(f"{strategy.__name__}: {report.consistency_score:.1%}")
```

### With Custom Signal Generators

```python
def my_custom_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """Custom strategy implementation."""
    # Calculate indicators
    sma_20 = prices.rolling(20).mean()
    sma_50 = prices.rolling(50).mean()

    # Generate signals
    buy_signals = (sma_20 > sma_50) & (sma_20.shift(1) <= sma_50.shift(1))
    sell_signals = (sma_20 < sma_50) & (sma_20.shift(1) >= sma_50.shift(1))

    return buy_signals, sell_signals

# Validate custom strategy
report = validator.validate(my_custom_strategy, tolerance=0.05)
```

---

## Best Practices

### 1. Validation Standards

**Always validate new strategies**:
```python
# Before deploying any strategy
def deploy_strategy(strategy_name, signal_generator):
    # 1. Create reference
    tester.create_reference(
        test_name=f"{strategy_name}_baseline",
        signal_generator=signal_generator,
        description=f"Baseline for {strategy_name}"
    )

    # 2. Validate consistency
    report = validator.validate(signal_generator, tolerance=0.05)
    if not report.validation_passed:
        raise ValueError(f"Validation failed: {report.discrepancies}")

    # 3. Check performance
    with tracker.track(strategy_name):
        result = runner.run(engine='vectorbt', signal_generator=signal_generator)

    # 4. Deploy
    deploy_to_production(strategy_name, signal_generator)
```

### 2. Tolerance Settings

**Choose appropriate tolerance based on strategy type**:

```python
# Strict tolerance for simple strategies (±5%)
simple_strategy_tolerance = 0.05

# Moderate tolerance for complex strategies (±10%)
complex_strategy_tolerance = 0.10

# Loose tolerance for experimental strategies (±20%)
experimental_tolerance = 0.20

# Example
if strategy_complexity == 'simple':
    tolerance = 0.05
elif strategy_complexity == 'complex':
    tolerance = 0.10
else:
    tolerance = 0.20

report = validator.validate(signal_generator, tolerance=tolerance)
```

### 3. Reference Result Management

**Maintain versioned references**:

```python
# Version references for tracking changes
tester.create_reference(
    test_name=f"rsi_strategy_v1_0",
    signal_generator=rsi_signal_generator_v1,
    description="RSI strategy version 1.0",
    tags=['rsi', 'v1.0', 'production']
)

tester.create_reference(
    test_name=f"rsi_strategy_v1_1",
    signal_generator=rsi_signal_generator_v1_1,
    description="RSI strategy version 1.1 - optimized thresholds",
    tags=['rsi', 'v1.1', 'experimental']
)

# Compare versions
v1_0 = tester._load_reference("rsi_strategy_v1_0")
v1_1 = tester._load_reference("rsi_strategy_v1_1")

print(f"Version comparison:")
print(f"  v1.0 Sharpe: {v1_0.sharpe_ratio:.2f}")
print(f"  v1.1 Sharpe: {v1_1.sharpe_ratio:.2f}")
print(f"  Improvement: {(v1_1.sharpe_ratio / v1_0.sharpe_ratio - 1):.1%}")
```

### 4. Performance Monitoring

**Track performance trends over time**:

```python
# Daily validation job
def daily_validation():
    strategies = get_all_strategies()

    for name, generator in strategies:
        with tracker.track(f"{name}_daily"):
            report = validator.validate(generator, tolerance=0.05)

        # Store metrics in time-series database
        store_metrics(
            timestamp=datetime.now(),
            strategy=name,
            consistency_score=report.consistency_score,
            execution_time=tracker.get_latest(f"{name}_daily").execution_time
        )

    # Generate weekly report
    if datetime.now().weekday() == 0:  # Monday
        generate_weekly_report()
```

### 5. Alert Configuration

**Set appropriate alert thresholds**:

```python
# Conservative: High alert threshold
production_monitor = ConsistencyMonitor(
    config, data_provider,
    alert_threshold=0.95  # Alert if <95%
)

# Standard: Moderate alert threshold
development_monitor = ConsistencyMonitor(
    config, data_provider,
    alert_threshold=0.90  # Alert if <90%
)

# Permissive: Low alert threshold
experimental_monitor = ConsistencyMonitor(
    config, data_provider,
    alert_threshold=0.80  # Alert if <80%
)
```

---

## Troubleshooting

### Common Issues

#### 1. "Custom engine requires full SQLite schema"

**Problem**: Custom engine validation fails with schema error

**Solution**: This is expected if the full SQLite schema from Phase 2 is not available. The custom engine requires complete indicator columns in the database.

**Workaround**:
```python
# Use vectorbt-only validation
try:
    report = validator.validate(signal_generator, tolerance=0.05)
except Exception as e:
    if "no such column" in str(e):
        logger.warning("Custom engine unavailable, using vectorbt only")
        # Run vectorbt-only backtest
        result = runner.run(engine='vectorbt', signal_generator=signal_generator)
    else:
        raise
```

#### 2. Inconsistent Results Between Engines

**Problem**: Low consistency scores (<0.90) between engines

**Diagnosis**:
```python
report = validator.validate(signal_generator, tolerance=0.05)

if report.consistency_score < 0.90:
    print("Discrepancies found:")
    for key, value in report.discrepancies.items():
        print(f"  {key}: {value}")

    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")
```

**Common Causes**:
- Different floating-point rounding
- Order execution timing differences
- Commission/slippage calculation differences

**Solutions**:
- Increase tolerance if differences are minor
- Check signal generator logic for determinism
- Verify commission/slippage settings match

#### 3. Reference Not Found

**Problem**: `FileNotFoundError` when running regression test

**Solution**:
```python
# Check if reference exists
try:
    result = tester.test_regression(test_name, signal_generator)
except FileNotFoundError:
    # Create reference if it doesn't exist
    logger.info("Creating missing reference")
    tester.create_reference(
        test_name=test_name,
        signal_generator=signal_generator,
        description="Auto-created reference"
    )
    result = tester.test_regression(test_name, signal_generator)
```

#### 4. High Memory Usage

**Problem**: Performance tracker shows high memory consumption

**Diagnosis**:
```python
with tracker.track("memory_test"):
    result = runner.run(engine='vectorbt', signal_generator=signal_generator)

metrics = tracker.get_latest("memory_test")
if metrics.memory_usage_mb > 500:  # 500 MB threshold
    logger.warning(f"High memory usage: {metrics.memory_usage_mb:.1f} MB")
```

**Solutions**:
- Use smaller date ranges for backtests
- Clear cached data between runs
- Use vectorbt's memory-efficient mode

#### 5. Slow Validation Performance

**Problem**: Validation takes too long (>30s)

**Optimization**:
```python
# Use vectorbt-only for parameter optimization
if optimization_mode:
    # Fast: vectorbt only (~1s)
    result = runner.run(engine='vectorbt', signal_generator=signal_generator)
else:
    # Comprehensive: validate both engines (~30s)
    report = validator.validate(signal_generator, tolerance=0.05)
```

---

## Summary

The Validation Framework provides comprehensive quality assurance for backtesting operations:

**Core Components**:
- ✅ **EngineValidator**: Cross-engine consistency validation
- ✅ **RegressionTester**: Automated regression detection
- ✅ **PerformanceTracker**: Execution profiling
- ✅ **ConsistencyMonitor**: Real-time monitoring
- ✅ **ValidationReportGenerator**: Stakeholder reports

**Key Benefits**:
- Automated quality assurance
- Regression prevention
- Performance optimization
- Historical tracking
- CI/CD integration

**Next Steps**:
- See [WALK_FORWARD_OPTIMIZATION.md](WALK_FORWARD_OPTIMIZATION.md) for optimization framework
- See [PHASE_3_COMPLETE.md](PHASE_3_COMPLETE.md) for Phase 3 summary
- Run `examples/example_validation_workflow.py` for complete demonstration

---

**Last Updated**: 2025-10-27
**Version**: 1.0.0
**Status**: Complete
