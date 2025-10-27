# Walk-Forward Optimization Guide - Phase 3

Comprehensive guide to walk-forward optimization, parameter scanning, and overfitting detection.

---

## Table of Contents

1. [Overview](#overview)
2. [Walk-Forward Optimization](#walk-forward-optimization)
3. [Parameter Scanning](#parameter-scanning)
4. [Overfitting Detection](#overfitting-detection)
5. [Practical Examples](#practical-examples)
6. [Best Practices](#best-practices)
7. [Integration Patterns](#integration-patterns)

---

## Overview

### Purpose

The Optimization Framework provides tools for robust parameter optimization and overfitting prevention:

- **Walk-Forward Optimization**: Time-series cross-validation using rolling/anchored windows
- **Parameter Scanning**: Systematic grid search and sensitivity analysis
- **Overfitting Detection**: Analyze in-sample vs out-of-sample performance degradation

### Why Walk-Forward Optimization?

**Traditional Optimization Problem**:
```
Full Dataset (2020-2023)
└─→ Optimize parameters
    └─→ Test on SAME data
        └─→ ❌ Overfitting: Great backtest, poor live results
```

**Walk-Forward Solution**:
```
Window 1: Train (2020) → Test (2021) ✅
Window 2: Train (2021) → Test (2022) ✅
Window 3: Train (2022) → Test (2023) ✅
└─→ Robust parameters that work across time periods
```

### Key Benefits

- ✅ **Prevents Overfitting**: Out-of-sample validation on unseen data
- ✅ **Realistic Performance**: Simulates real-world parameter selection
- ✅ **Robustness Validation**: Tests strategy across different market regimes
- ✅ **Automated Detection**: Identifies degradation and sensitivity issues

---

## Walk-Forward Optimization

### Concept

Walk-forward optimization divides historical data into multiple overlapping or non-overlapping windows:

1. **Train Period**: Optimize parameters on historical data
2. **Test Period**: Validate optimized parameters on future data (out-of-sample)
3. **Repeat**: Move forward and repeat for next window

**Two Strategies**:

**Rolling Window**:
```
Window 1: |--- Train ---|--- Test ---|
Window 2:      |--- Train ---|--- Test ---|
Window 3:           |--- Train ---|--- Test ---|
```

**Anchored Window**:
```
Window 1: |--- Train ---|--- Test ---|
Window 2: |--------- Train --------|--- Test ---|
Window 3: |--------------- Train --------------|--- Test ---|
```

### Implementation

**Location**: `modules/backtesting/optimization/walk_forward_optimizer.py`

#### Key Classes

```python
@dataclass
class WalkForwardWindow:
    """Single walk-forward window definition."""
    window_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date

@dataclass
class WalkForwardResult:
    """Walk-forward optimization result."""
    best_params: Dict[str, Any]
    all_results: List[Dict]
    windows: List[WalkForwardWindow]

    # Performance summary
    in_sample_performance: Dict[str, float]
    out_of_sample_performance: Dict[str, float]

    # Robustness metrics
    degradation_pct: float
    robustness_score: float
    overfitting_detected: bool

    # Recommendations
    recommendations: List[str]
```

#### Basic Usage

```python
from modules.backtesting.optimization import WalkForwardOptimizer

# Create optimizer
optimizer = WalkForwardOptimizer(config, data_provider)

# Define parameter grid
param_grid = {
    'rsi_period': [10, 14, 20],
    'oversold': [20, 30, 40],
    'overbought': [60, 70, 80]
}

# Define signal generator factory
def create_rsi_generator(rsi_period=14, oversold=30, overbought=70):
    def rsi_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        rsi = calculate_rsi(prices, period=rsi_period)
        buy_signals = rsi < oversold
        sell_signals = rsi > overbought
        return buy_signals, sell_signals
    return rsi_strategy

# Run walk-forward optimization
result = optimizer.optimize(
    signal_generator_factory=create_rsi_generator,
    param_grid=param_grid,
    train_period_days=252,  # 1 year training
    test_period_days=63,    # 3 months testing
    metric='sharpe_ratio',
    anchored=False  # Use rolling windows
)

# Check results
print(f"Best parameters: {result.best_params}")
print(f"In-sample Sharpe: {result.in_sample_performance['sharpe_ratio']:.2f}")
print(f"Out-of-sample Sharpe: {result.out_of_sample_performance['sharpe_ratio']:.2f}")
print(f"Degradation: {result.degradation_pct:.1%}")
print(f"Robustness score: {result.robustness_score:.2f}")

if result.overfitting_detected:
    print("\n⚠️ Overfitting detected!")
    for rec in result.recommendations:
        print(f"  - {rec}")
```

### Window Creation

```python
# Create windows manually
windows = optimizer.create_windows(
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    train_period_days=252,  # 1 year
    test_period_days=63,    # 3 months
    step_days=126,          # Move forward 6 months
    anchored=False
)

print(f"Created {len(windows)} windows:")
for window in windows:
    print(f"Window {window.window_id}:")
    print(f"  Train: {window.train_start} to {window.train_end}")
    print(f"  Test:  {window.test_start} to {window.test_end}")
```

### Optimization Metrics

**Available metrics**:
- `sharpe_ratio` - Risk-adjusted return (recommended)
- `total_return` - Absolute return
- `win_rate` - Percentage of winning trades
- `profit_factor` - Gross profit / gross loss

**Choosing the right metric**:

```python
# For risk-adjusted optimization (recommended)
result = optimizer.optimize(
    signal_generator_factory=create_generator,
    param_grid=param_grid,
    metric='sharpe_ratio'
)

# For absolute return (use with caution)
result = optimizer.optimize(
    signal_generator_factory=create_generator,
    param_grid=param_grid,
    metric='total_return'
)

# For consistency focus
result = optimizer.optimize(
    signal_generator_factory=create_generator,
    param_grid=param_grid,
    metric='win_rate'
)
```

### Robustness Scoring

The robustness score combines degradation penalty and consistency:

```python
# Degradation: How much worse is out-of-sample vs in-sample?
degradation_pct = (in_sample_sharpe - out_of_sample_sharpe) / in_sample_sharpe

# Penalty increases with degradation
degradation_penalty = min(degradation_pct, 1.0)

# Consistency: How stable are results across windows?
consistency_score = 1.0 - std_dev_across_windows / mean_across_windows

# Final robustness score
robustness_score = (1.0 - degradation_penalty) * consistency_score

# Overfitting detection
overfitting_detected = (
    degradation_pct > 0.20 or      # >20% degradation
    robustness_score < 0.5 or       # Low robustness
    param_sensitivity > 0.7          # High sensitivity
)
```

---

## Parameter Scanning

### Concept

Systematic exploration of parameter space through grid search:

```python
param_grid = {
    'rsi_period': [10, 14, 20],           # 3 values
    'oversold': [20, 30, 40],             # 3 values
    'overbought': [60, 70, 80]            # 3 values
}
# Total combinations: 3 × 3 × 3 = 27
```

### Implementation

**Location**: `modules/backtesting/optimization/parameter_scanner.py`

#### Key Classes

```python
@dataclass
class ParameterSearchResult:
    """Result from parameter search."""
    params: Dict[str, Any]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float
```

#### Grid Search

```python
from modules.backtesting.optimization import ParameterScanner

# Create scanner
scanner = ParameterScanner(config, data_provider)

# Run grid search
results = scanner.grid_search(
    signal_generator_factory=create_rsi_generator,
    param_grid={
        'rsi_period': [10, 14, 20],
        'oversold': [20, 30, 40],
        'overbought': [60, 70, 80]
    }
)

# Find best parameters
best_result = max(results, key=lambda x: x.sharpe_ratio)
print(f"Best parameters: {best_result.params}")
print(f"Best Sharpe: {best_result.sharpe_ratio:.2f}")

# Convert to DataFrame for analysis
df = scanner.to_dataframe(results)
print("\nTop 5 parameter combinations:")
print(df.nlargest(5, 'sharpe_ratio'))
```

#### Parameter Analysis

```python
# Analyze parameter impact
df = scanner.to_dataframe(results)

# Average performance by parameter value
for param in ['rsi_period', 'oversold', 'overbought']:
    avg_sharpe = df.groupby(param)['sharpe_ratio'].mean()
    print(f"\nAverage Sharpe by {param}:")
    print(avg_sharpe.to_string())

# Parameter correlations
import matplotlib.pyplot as plt
import seaborn as sns

# Heatmap of parameter combinations
pivot = df.pivot_table(
    values='sharpe_ratio',
    index='oversold',
    columns='overbought',
    aggfunc='mean'
)

sns.heatmap(pivot, annot=True, fmt='.2f', cmap='RdYlGn')
plt.title('Sharpe Ratio by Oversold/Overbought Thresholds')
plt.show()
```

### Sensitivity Analysis

**Purpose**: Identify parameters that significantly impact performance

```python
# Test parameter sensitivity
base_params = {'rsi_period': 14, 'oversold': 30, 'overbought': 70}

# Vary one parameter at a time
rsi_period_range = range(5, 31, 5)  # 5, 10, 15, 20, 25, 30
results_by_period = []

for period in rsi_period_range:
    params = base_params.copy()
    params['rsi_period'] = period

    generator = create_rsi_generator(**params)
    result = runner.run(engine='vectorbt', signal_generator=generator)

    results_by_period.append({
        'rsi_period': period,
        'sharpe_ratio': result.sharpe_ratio
    })

# Analyze sensitivity
df_sensitivity = pd.DataFrame(results_by_period)
sharpe_std = df_sensitivity['sharpe_ratio'].std()
sharpe_mean = df_sensitivity['sharpe_ratio'].mean()
sensitivity = sharpe_std / sharpe_mean

print(f"RSI Period Sensitivity: {sensitivity:.2f}")
if sensitivity > 0.5:
    print("⚠️ High sensitivity - results unstable across parameter values")
else:
    print("✅ Low sensitivity - robust parameter range")
```

---

## Overfitting Detection

### Concept

Overfitting occurs when a strategy is over-optimized on historical data and fails on new data:

**Signs of Overfitting**:
- High in-sample performance, poor out-of-sample performance
- Performance degrades significantly (>20%) on test data
- High parameter sensitivity (small changes cause large performance swings)
- Too many parameters relative to data points

### Implementation

**Location**: `modules/backtesting/optimization/overfitting_detector.py`

#### Key Classes

```python
@dataclass
class OverfittingReport:
    """Overfitting detection report."""
    is_overfit: bool
    degradation_pct: float
    robustness_score: float
    warning_flags: List[str]
    recommendations: List[str]
```

#### Basic Usage

```python
from modules.backtesting.optimization import OverfittingDetector

# Create detector
detector = OverfittingDetector(
    degradation_threshold=0.20,  # 20% degradation threshold
    robustness_threshold=0.5     # Minimum robustness score
)

# Test for overfitting
report = detector.detect_overfitting(
    in_sample_sharpe=2.5,
    out_of_sample_sharpe=0.8,
    param_sensitivity=0.7  # Optional
)

if report.is_overfit:
    print("⚠️ Overfitting detected!")
    print(f"Degradation: {report.degradation_pct:.1%}")
    print(f"Robustness: {report.robustness_score:.2f}")

    print("\nWarning flags:")
    for flag in report.warning_flags:
        print(f"  - {flag}")

    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")
else:
    print("✅ No overfitting detected")
    print(f"Robustness score: {report.robustness_score:.2f}")
```

#### Degradation Analysis

```python
# Calculate degradation
def calculate_degradation(in_sample_result, out_of_sample_result):
    """Calculate performance degradation."""
    in_sharpe = in_sample_result.sharpe_ratio
    out_sharpe = out_of_sample_result.sharpe_ratio

    degradation_pct = (in_sharpe - out_sharpe) / in_sharpe

    if degradation_pct > 0.20:
        print(f"⚠️ High degradation: {degradation_pct:.1%}")
        print("In-sample Sharpe: {in_sharpe:.2f}")
        print("Out-of-sample Sharpe: {out_sharpe:.2f}")
    elif degradation_pct > 0.10:
        print(f"⚠️ Moderate degradation: {degradation_pct:.1%}")
    else:
        print(f"✅ Low degradation: {degradation_pct:.1%}")

    return degradation_pct
```

---

## Practical Examples

### Example 1: RSI Strategy Optimization

```python
from modules.backtesting.optimization import WalkForwardOptimizer

# Define RSI generator factory
def create_rsi_generator(rsi_period=14, oversold=30, overbought=70):
    def rsi_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        # Calculate RSI
        rsi = calculate_rsi(prices, period=rsi_period)

        # Generate signals
        buy_signals = rsi < oversold
        sell_signals = rsi > overbought

        return buy_signals, sell_signals

    rsi_strategy.__name__ = f"rsi_{rsi_period}_{oversold}_{overbought}"
    return rsi_strategy

# Parameter grid
param_grid = {
    'rsi_period': [10, 14, 20],
    'oversold': [20, 30, 40],
    'overbought': [60, 70, 80]
}

# Run optimization
optimizer = WalkForwardOptimizer(config, data_provider)
result = optimizer.optimize(
    signal_generator_factory=create_rsi_generator,
    param_grid=param_grid,
    train_period_days=252,  # 1 year
    test_period_days=63,    # 3 months
    metric='sharpe_ratio',
    anchored=False
)

# Analyze results
print(f"Optimization Results:")
print(f"  Best Parameters: {result.best_params}")
print(f"  In-Sample Sharpe: {result.in_sample_performance['sharpe_ratio']:.2f}")
print(f"  Out-of-Sample Sharpe: {result.out_of_sample_performance['sharpe_ratio']:.2f}")
print(f"  Degradation: {result.degradation_pct:.1%}")
print(f"  Robustness: {result.robustness_score:.2f}")

if result.overfitting_detected:
    print("\n⚠️ Overfitting Warning!")
    for rec in result.recommendations:
        print(f"  - {rec}")
else:
    print("\n✅ Parameters appear robust")
```

### Example 2: Moving Average Crossover Optimization

```python
def create_ma_crossover_generator(fast_period=20, slow_period=50):
    def ma_crossover_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        # Calculate moving averages
        fast_ma = prices.rolling(fast_period).mean()
        slow_ma = prices.rolling(slow_period).mean()

        # Generate signals
        buy_signals = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
        sell_signals = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        return buy_signals, sell_signals
    return ma_crossover_strategy

# Parameter grid
param_grid = {
    'fast_period': [10, 20, 30],
    'slow_period': [40, 50, 60, 100]
}

# Optimize
result = optimizer.optimize(
    signal_generator_factory=create_ma_crossover_generator,
    param_grid=param_grid,
    train_period_days=252,
    test_period_days=63,
    metric='sharpe_ratio'
)
```

### Example 3: Multi-Parameter Bollinger Bands

```python
def create_bollinger_generator(bb_period=20, bb_std=2.0, rsi_period=14):
    def bollinger_strategy(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        # Calculate Bollinger Bands
        sma = prices.rolling(bb_period).mean()
        std = prices.rolling(bb_period).std()
        upper = sma + (bb_std * std)
        lower = sma - (bb_std * std)

        # Calculate RSI
        rsi = calculate_rsi(prices, period=rsi_period)

        # Combined signals
        buy_signals = (prices < lower) & (rsi < 30)
        sell_signals = (prices > upper) & (rsi > 70)

        return buy_signals, sell_signals
    return bollinger_strategy

# Parameter grid
param_grid = {
    'bb_period': [15, 20, 25],
    'bb_std': [1.5, 2.0, 2.5],
    'rsi_period': [10, 14, 20]
}

# Optimize
result = optimizer.optimize(
    signal_generator_factory=create_bollinger_generator,
    param_grid=param_grid,
    train_period_days=252,
    test_period_days=63,
    metric='sharpe_ratio'
)
```

### Example 4: Comparing Anchored vs Rolling Windows

```python
# Test both strategies
strategies = {
    'anchored': True,
    'rolling': False
}

results_comparison = {}

for name, anchored in strategies.items():
    result = optimizer.optimize(
        signal_generator_factory=create_rsi_generator,
        param_grid=param_grid,
        train_period_days=252,
        test_period_days=63,
        metric='sharpe_ratio',
        anchored=anchored
    )

    results_comparison[name] = {
        'degradation': result.degradation_pct,
        'robustness': result.robustness_score,
        'out_sharpe': result.out_of_sample_performance['sharpe_ratio']
    }

# Compare
df_comparison = pd.DataFrame(results_comparison).T
print("\nAnchored vs Rolling Window Comparison:")
print(df_comparison.to_string())
```

---

## Best Practices

### 1. Window Size Selection

**Training Period**:
- **Too Short** (<6 months): Insufficient data for optimization
- **Optimal** (6-12 months): Balance between data and adaptability
- **Too Long** (>2 years): May include outdated market regimes

**Test Period**:
- **Too Short** (<1 month): High variance, unreliable results
- **Optimal** (1-3 months): Sufficient trades for validation
- **Too Long** (>6 months): Reduces number of windows

**Example**:
```python
# Conservative: Long training, short testing
optimizer.optimize(
    train_period_days=365,  # 1 year
    test_period_days=30,    # 1 month
    step_days=90            # Quarterly reoptimization
)

# Aggressive: Short training, frequent reoptimization
optimizer.optimize(
    train_period_days=180,  # 6 months
    test_period_days=60,    # 2 months
    step_days=30            # Monthly reoptimization
)
```

### 2. Parameter Grid Design

**Start Wide, Then Narrow**:

```python
# Phase 1: Wide exploration
initial_grid = {
    'rsi_period': [5, 10, 15, 20, 25, 30],
    'oversold': [10, 20, 30, 40],
    'overbought': [60, 70, 80, 90]
}

result_phase1 = optimizer.optimize(
    signal_generator_factory=create_rsi_generator,
    param_grid=initial_grid
)

# Phase 2: Narrow refinement around best parameters
best = result_phase1.best_params
refined_grid = {
    'rsi_period': [best['rsi_period'] - 2, best['rsi_period'], best['rsi_period'] + 2],
    'oversold': [best['oversold'] - 5, best['oversold'], best['oversold'] + 5],
    'overbought': [best['overbought'] - 5, best['overbought'], best['overbought'] + 5]
}

result_phase2 = optimizer.optimize(
    signal_generator_factory=create_rsi_generator,
    param_grid=refined_grid
)
```

### 3. Overfitting Prevention

**Rules**:
1. Always use walk-forward optimization (never optimize on full dataset)
2. Require minimum trades (>30) on each test window
3. Limit number of parameters (<5 for most strategies)
4. Use conservative tolerance (degradation <20%)
5. Prefer simpler strategies over complex ones

**Example**:
```python
def validate_optimization_result(result: WalkForwardResult):
    """Validate optimization result against overfitting criteria."""
    issues = []

    # Check degradation
    if result.degradation_pct > 0.20:
        issues.append(f"High degradation: {result.degradation_pct:.1%}")

    # Check robustness
    if result.robustness_score < 0.5:
        issues.append(f"Low robustness: {result.robustness_score:.2f}")

    # Check minimum trades per window
    for window_result in result.all_results:
        if window_result['test_trades'] < 30:
            issues.append(f"Insufficient trades in window {window_result['window_id']}")

    # Check parameter count
    if len(result.best_params) > 5:
        issues.append(f"Too many parameters: {len(result.best_params)}")

    if issues:
        print("⚠️ Potential overfitting issues:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ Validation passed")
        return True

# Use in workflow
result = optimizer.optimize(...)
if validate_optimization_result(result):
    deploy_strategy(result.best_params)
else:
    print("Strategy requires further refinement")
```

### 4. Performance Monitoring

**Track Key Metrics**:

```python
def monitor_optimization_performance(result: WalkForwardResult):
    """Monitor optimization performance metrics."""

    # In-sample vs out-of-sample
    print(f"Performance Comparison:")
    print(f"  In-Sample Sharpe:     {result.in_sample_performance['sharpe_ratio']:.2f}")
    print(f"  Out-of-Sample Sharpe: {result.out_of_sample_performance['sharpe_ratio']:.2f}")
    print(f"  Degradation:          {result.degradation_pct:.1%}")

    # Consistency across windows
    window_sharpes = [w['test_sharpe'] for w in result.all_results]
    avg_sharpe = np.mean(window_sharpes)
    std_sharpe = np.std(window_sharpes)

    print(f"\nConsistency Metrics:")
    print(f"  Average Test Sharpe:  {avg_sharpe:.2f}")
    print(f"  Std Dev:              {std_sharpe:.2f}")
    print(f"  Coefficient of Var:   {std_sharpe/avg_sharpe:.2f}")

    # Robustness
    print(f"\nRobustness:")
    print(f"  Robustness Score:     {result.robustness_score:.2f}")
    print(f"  Overfitting Detected: {'Yes ⚠️' if result.overfitting_detected else 'No ✅'}")
```

### 5. Documentation and Version Control

**Document Optimization Results**:

```python
def save_optimization_report(result: WalkForwardResult, strategy_name: str):
    """Save optimization report for future reference."""

    report = {
        'strategy_name': strategy_name,
        'timestamp': datetime.now().isoformat(),
        'best_params': result.best_params,
        'performance': {
            'in_sample': result.in_sample_performance,
            'out_of_sample': result.out_of_sample_performance,
            'degradation_pct': result.degradation_pct,
            'robustness_score': result.robustness_score
        },
        'windows': [
            {
                'window_id': w.window_id,
                'train_period': f"{w.train_start} to {w.train_end}",
                'test_period': f"{w.test_start} to {w.test_end}"
            }
            for w in result.windows
        ],
        'overfitting_detected': result.overfitting_detected,
        'recommendations': result.recommendations
    }

    # Save as JSON
    import json
    output_path = f"optimization_reports/{strategy_name}_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✅ Optimization report saved: {output_path}")
```

---

## Integration Patterns

### With Validation Framework

```python
from modules.backtesting.validation import EngineValidator, RegressionTester
from modules.backtesting.optimization import WalkForwardOptimizer

# 1. Optimize parameters
optimizer = WalkForwardOptimizer(config, data_provider)
opt_result = optimizer.optimize(
    signal_generator_factory=create_rsi_generator,
    param_grid=param_grid
)

# 2. Create strategy with best parameters
best_generator = create_rsi_generator(**opt_result.best_params)

# 3. Validate cross-engine consistency
validator = EngineValidator(config, data_provider)
val_report = validator.validate(best_generator, tolerance=0.05)

# 4. Create regression reference
tester = RegressionTester(config, data_provider)
reference = tester.create_reference(
    test_name="rsi_optimized_v1",
    signal_generator=best_generator,
    description=f"Optimized RSI: {opt_result.best_params}"
)

# 5. Deploy if all validations pass
if val_report.validation_passed and not opt_result.overfitting_detected:
    print("✅ All validations passed - ready for deployment")
    deploy_strategy(best_generator)
else:
    print("⚠️ Validations failed - requires refinement")
```

### With CI/CD Pipeline

```python
# ci_optimization.py

def ci_optimization_workflow(strategy_name, generator_factory, param_grid):
    """Complete optimization workflow for CI/CD."""

    # 1. Run walk-forward optimization
    optimizer = WalkForwardOptimizer(config, data_provider)
    result = optimizer.optimize(
        signal_generator_factory=generator_factory,
        param_grid=param_grid
    )

    # 2. Check for overfitting
    if result.overfitting_detected:
        print("❌ Overfitting detected - failing build")
        sys.exit(1)

    # 3. Validate degradation threshold
    if result.degradation_pct > 0.20:
        print(f"❌ High degradation ({result.degradation_pct:.1%}) - failing build")
        sys.exit(1)

    # 4. Validate robustness
    if result.robustness_score < 0.5:
        print(f"❌ Low robustness ({result.robustness_score:.2f}) - failing build")
        sys.exit(1)

    # 5. Create regression reference
    tester = RegressionTester(config, data_provider)
    best_generator = generator_factory(**result.best_params)
    tester.create_reference(
        test_name=f"{strategy_name}_optimized",
        signal_generator=best_generator,
        description=f"Optimized {strategy_name}",
        overwrite=True
    )

    # 6. Save optimization report
    save_optimization_report(result, strategy_name)

    print("✅ Optimization workflow complete - build passed")
    sys.exit(0)
```

---

## Summary

The Optimization Framework provides robust tools for parameter selection and overfitting prevention:

**Core Components**:
- ✅ **WalkForwardOptimizer**: Time-series cross-validation with rolling/anchored windows
- ✅ **ParameterScanner**: Systematic grid search and sensitivity analysis
- ✅ **OverfittingDetector**: Performance degradation detection

**Key Benefits**:
- Prevents overfitting through out-of-sample validation
- Identifies robust parameter ranges
- Automates parameter selection
- Provides degradation and robustness metrics

**Best Practices**:
- Use walk-forward optimization (never optimize on full dataset)
- Start with wide parameter grid, then narrow
- Require minimum 30 trades per test window
- Limit parameters to <5 for most strategies
- Document optimization results

**Next Steps**:
- See [VALIDATION_FRAMEWORK_GUIDE.md](VALIDATION_FRAMEWORK_GUIDE.md) for validation tools
- See [PHASE_3_COMPLETE.md](PHASE_3_COMPLETE.md) for Phase 3 summary
- Run `examples/example_validation_workflow.py` for complete demonstration

---

**Last Updated**: 2025-10-27
**Version**: 1.0.0
**Status**: Complete
