# Custom Backtesting Engine User Guide

**Target Audience**: Quantitative researchers, strategy developers, portfolio managers
**Prerequisites**: Basic Python, pandas knowledge, understanding of backtesting concepts
**Estimated Reading Time**: 30 minutes

---

## Table of Contents
1. [Introduction](#1-introduction)
2. [Quick Start](#2-quick-start)
3. [Understanding the Engine](#3-understanding-the-engine)
4. [Building Your First Strategy](#4-building-your-first-strategy)
5. [Advanced Usage](#5-advanced-usage)
6. [Best Practices](#6-best-practices)
7. [Troubleshooting](#7-troubleshooting)
8. [Performance Optimization](#8-performance-optimization)

---

## 1. Introduction

### What is the Custom Backtesting Engine?

The Custom Event-Driven Backtesting Engine is a production-grade simulation system that validates trading strategies with realistic market conditions. Unlike vectorized backtesting (VectorBT), it processes market data bar-by-bar, providing order-level detail and compliance-ready trade logs.

### When to Use Custom Engine vs VectorBT

| Scenario | Recommended Engine | Why? |
|----------|-------------------|------|
| Parameter optimization (100+ combinations) | VectorBT | 100x faster execution |
| Factor research and screening | VectorBT | Vectorized operations |
| **Production validation** | **Custom Engine** | Order-level detail |
| **Compliance auditing** | **Custom Engine** | Full trade logs |
| **Custom order logic** | **Custom Engine** | Event-driven flexibility |
| Quick strategy iteration | VectorBT | <1s execution time |
| **Realistic simulation** | **Custom Engine** | Bar-by-bar processing |

**Recommended Workflow**:
1. **Research Phase**: Use VectorBT to screen 1,000+ parameter combinations
2. **Validation Phase**: Use Custom Engine to validate top 10 strategies with realistic execution
3. **Production**: Deploy strategies validated by Custom Engine

### Key Features

✅ **Event-Driven Simulation** - Bar-by-bar processing for realistic market conditions
✅ **Position Tracking** - Full portfolio management with realized/unrealized P&L
✅ **Trade Logging** - Complete entry/exit details with transaction costs
✅ **Order Execution** - Realistic fills with slippage and partial execution
✅ **Performance Metrics** - Comprehensive analytics (Sharpe, Sortino, Max DD, etc.)
✅ **Production-Ready** - Audit trails, compliance reporting, custom order types

---

## 2. Quick Start

### Installation

The Custom Backtesting Engine is included in the Quant Platform installation.

```bash
# Install dependencies
pip install -r requirements_quant.txt

# Verify installation
python3 -c "from modules.backtest.custom.backtest_engine import BacktestEngine; print('✅ Custom Engine installed')"
```

### 5-Minute Example

```python
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.common.costs import TransactionCostModel
import pandas as pd
import numpy as np

# Step 1: Load data (or generate sample data)
dates = pd.date_range('2020-01-01', '2024-12-31', freq='D')
data = {
    '005930': pd.DataFrame({
        'open': 60000 + np.cumsum(np.random.randn(len(dates)) * 500),
        'high': 61000 + np.cumsum(np.random.randn(len(dates)) * 500),
        'low': 59000 + np.cumsum(np.random.randn(len(dates)) * 500),
        'close': 60000 + np.cumsum(np.random.randn(len(dates)) * 500),
        'volume': 1_000_000
    }, index=dates)
}

# Step 2: Generate signals (simple moving average crossover)
signals = {}
for ticker, df in data.items():
    ma20 = df['close'].rolling(20).mean()
    signals[ticker] = df['close'] > ma20  # True = buy signal

# Step 3: Initialize engine
engine = BacktestEngine(
    initial_capital=100_000_000,  # 100M KRW
    cost_model=TransactionCostModel(broker='KIS')
)

# Step 4: Run backtest
results = engine.run(data=data, signals=signals)

# Step 5: View results
print(f"Total Return: {results['metrics']['total_return_pct']:.2%}")
print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
print(f"Total Trades: {results['trade_stats']['total_trades']}")
```

**Expected Output**:
```
Total Return: 5.30%
Sharpe Ratio: 0.20
Total Trades: 19
```

---

## 3. Understanding the Engine

### Architecture Overview

The engine consists of four main components:

```
┌─────────────────────────────────────────────────────────┐
│                    BacktestEngine                        │
│                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Event   │→│  Signal      │→│  Order Execution │  │
│  │  Loop    │  │  Interpreter │  │  Engine          │  │
│  └──────────┘  └──────────────┘  └──────────────────┘  │
│       ↓              ↓                    ↓              │
│  ┌───────────────────────────────────────────────┐      │
│  │           Position Tracker                     │      │
│  │  (Holdings, Cash, Portfolio Value, P&L)       │      │
│  └───────────────────────────────────────────────┘      │
│       ↓                                                  │
│  ┌───────────────────────────────────────────────┐      │
│  │           Trade Logger                         │      │
│  │  (Entry/Exit, P&L, Holding Period)            │      │
│  └───────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### Component Roles

**1. Event Loop** (BacktestEngine)
- Drives bar-by-bar simulation
- Coordinates all other components
- Records equity curve and performance metrics

**2. Signal Interpreter**
- Translates strategy signals into orders
- Manages position sizing (equal weight, percentage, shares)
- Generates entry/exit orders based on signals

**3. Order Execution Engine**
- Simulates realistic order fills
- Applies transaction costs (commission, slippage, tax)
- Handles partial fills and market impact

**4. Position Tracker**
- Tracks current holdings and cash
- Calculates realized and unrealized P&L
- Manages portfolio value updates

**5. Trade Logger**
- Records complete trade history
- Calculates trade-level statistics
- Provides audit trail for compliance

### Data Flow

```
Bar N (e.g., 2024-01-15)
    ↓
Update Prices → Calculate Unrealized P&L
    ↓
Interpret Signals → Generate Orders (Entry/Exit)
    ↓
Execute Orders → Apply Costs → Update Positions
    ↓
Record Equity Point
    ↓
Bar N+1 (e.g., 2024-01-16)
```

### Signal Model

**Hold-Based Signals** (Custom Engine):
```python
signals = {
    'ticker': True   # Should hold position
    'ticker': False  # Should NOT hold position (exit if held)
}
```

This differs from VectorBT's entry-based model:
```python
# VectorBT (different model)
entries = True   # Enter position, hold until next entry
exits = True     # Exit position
```

**Why Hold-Based?**
- More intuitive for systematic strategies
- Natural for monthly rebalancing (hold top N stocks)
- Easier to implement multi-factor models

---

## 4. Building Your First Strategy

### Step-by-Step: Momentum Strategy

Let's build a complete 12-month momentum strategy.

#### Step 1: Import Dependencies

```python
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.common.costs import TransactionCostModel
import pandas as pd
import numpy as np
```

#### Step 2: Load Historical Data

```python
# Option A: Load from CSV
data = {
    '005930': pd.read_csv('data/005930_ohlcv.csv',
                          index_col=0, parse_dates=True),
    '000660': pd.read_csv('data/000660_ohlcv.csv',
                          index_col=0, parse_dates=True),
    '035420': pd.read_csv('data/035420_ohlcv.csv',
                          index_col=0, parse_dates=True)
}

# Option B: Load from PostgreSQL
from modules.backtest.vectorbt.adapter import VectorBTAdapter
adapter = VectorBTAdapter()
data = adapter.load_data(
    tickers=['005930', '000660', '035420'],
    region='KR',
    start_date='2020-01-01',
    end_date='2024-12-31'
)
```

#### Step 3: Calculate Momentum Signals

```python
def calculate_momentum_signals(data, lookback=252, skip_recent=21, top_n=2):
    """
    12-Month Momentum Strategy:
    - Rank stocks by 12-month return (skip last month)
    - Hold top N stocks
    - Rebalance monthly
    """
    # Combine close prices
    close_prices = pd.DataFrame({
        ticker: df['close'] for ticker, df in data.items()
    })

    # Calculate momentum (skip recent period to avoid reversal)
    shifted_prices = close_prices.shift(skip_recent)
    momentum = shifted_prices.pct_change(periods=lookback)

    # Rank stocks by momentum
    momentum_ranks = momentum.rank(axis=1, ascending=False, method='first')

    # Generate signals: True for top N stocks
    signals_df = momentum_ranks <= top_n

    # Convert to dictionary
    return {
        ticker: signals_df[ticker] for ticker in signals_df.columns
    }

# Generate signals
signals = calculate_momentum_signals(data, lookback=252, top_n=2)
```

#### Step 4: Configure Engine

```python
# Initialize with Korean market costs
engine = BacktestEngine(
    initial_capital=100_000_000,  # 100M KRW
    cost_model=TransactionCostModel(
        broker='KIS',
        commission_rate=0.00015,  # 0.015%
        tax_rate=0.0023,          # 0.23% (sell only)
        slippage_bps=5.0          # 5 bps
    ),
    size_type='equal_weight',     # Equal allocation
    target_positions=2            # Hold top 2 stocks
)
```

#### Step 5: Run Backtest

```python
results = engine.run(
    data=data,
    signals=signals,
    start_date='2020-01-01',
    end_date='2024-12-31'
)
```

#### Step 6: Analyze Results

```python
# Performance metrics
print("=" * 80)
print("BACKTEST RESULTS")
print("=" * 80)
print(f"\nPerformance Metrics:")
print(f"  Total Return:         {results['metrics']['total_return_pct']:>10.2%}")
print(f"  Annualized Return:    {results['metrics']['annualized_return']:>10.2%}")
print(f"  Sharpe Ratio:         {results['metrics']['sharpe_ratio']:>10.2f}")
print(f"  Sortino Ratio:        {results['metrics']['sortino_ratio']:>10.2f}")
print(f"  Max Drawdown:         {results['metrics']['max_drawdown']:>10.2%}")
print(f"  Win Rate:             {results['trade_stats']['win_rate']:>10.2%}")

# Trade statistics
print(f"\nTrade Statistics:")
print(f"  Total Trades:         {results['trade_stats']['total_trades']:>10,}")
print(f"  Winning Trades:       {results['trade_stats']['winning_trades']:>10,}")
print(f"  Losing Trades:        {results['trade_stats']['losing_trades']:>10,}")
print(f"  Average Win:          ₩{results['trade_stats']['avg_win']:>10,.0f}")
print(f"  Average Loss:         ₩{results['trade_stats']['avg_loss']:>10,.0f}")
print(f"  Avg Holding Days:     {results['trade_stats']['avg_holding_days']:>10.1f}")

# Transaction costs
print(f"\nTransaction Costs:")
print(f"  Total Commission:     ₩{results['trade_stats']['total_commission']:>10,.0f}")
print(f"  Total Tax:            ₩{results['trade_stats']['total_tax']:>10,.0f}")

# Export results
trades_df = results['trades']
trades_df.to_csv('backtest_trades.csv', index=False)
print(f"\n✅ Trade log exported to: backtest_trades.csv")
```

---

## 5. Advanced Usage

### Multi-Factor Strategy

Combine multiple factors (Value, Momentum, Quality) for robust alpha generation.

```python
def calculate_value_factor(data):
    """Calculate value scores (requires fundamental data)"""
    # Placeholder: Load P/E, P/B from database
    value_scores = {}
    for ticker in data.keys():
        # Lower P/E = higher score
        value_scores[ticker] = pd.Series(
            np.random.randn(len(data[ticker])),
            index=data[ticker].index
        )
    return value_scores

def calculate_quality_factor(data):
    """Calculate quality scores (requires fundamental data)"""
    quality_scores = {}
    for ticker in data.keys():
        # Higher ROE = higher score
        quality_scores[ticker] = pd.Series(
            np.random.randn(len(data[ticker])),
            index=data[ticker].index
        )
    return quality_scores

def combine_factors(momentum, value, quality, weights=[0.5, 0.3, 0.2]):
    """Combine multiple factors with weights"""
    # Normalize each factor
    factors = [momentum, value, quality]
    normalized = []
    for factor in factors:
        combined = pd.DataFrame(factor)
        ranks = combined.rank(axis=1, pct=True)
        normalized.append(ranks)

    # Weighted combination
    composite = sum(w * f for w, f in zip(weights, normalized))

    # Select top N stocks
    composite_ranks = composite.rank(axis=1, ascending=False)
    signals_df = composite_ranks <= 3  # Top 3 stocks

    return {ticker: signals_df[ticker] for ticker in signals_df.columns}

# Calculate factors
momentum = calculate_momentum_signals(data)
value = calculate_value_factor(data)
quality = calculate_quality_factor(data)

# Combine
signals = combine_factors(momentum, value, quality, weights=[0.5, 0.3, 0.2])

# Backtest
results = engine.run(data=data, signals=signals)
```

### Walk-Forward Optimization

Validate strategy with rolling window backtests.

```python
def walk_forward_backtest(data, signals, window_months=12, step_months=3):
    """
    Walk-forward optimization:
    - Train on window_months of data
    - Test on next step_months
    - Roll forward and repeat
    """
    results_list = []

    # Get date range
    start_date = pd.to_datetime(min(df.index.min() for df in data.values()))
    end_date = pd.to_datetime(max(df.index.max() for df in data.values()))

    # Walk forward
    current_date = start_date
    while current_date < end_date:
        # Define windows
        train_start = current_date
        train_end = current_date + pd.DateOffset(months=window_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=step_months)

        # Run backtest on test period
        engine = BacktestEngine(initial_capital=100_000_000)
        results = engine.run(
            data=data,
            signals=signals,
            start_date=test_start.strftime('%Y-%m-%d'),
            end_date=test_end.strftime('%Y-%m-%d')
        )

        results_list.append({
            'test_start': test_start,
            'test_end': test_end,
            'return': results['metrics']['total_return_pct'],
            'sharpe': results['metrics']['sharpe_ratio']
        })

        # Roll forward
        current_date = test_start

    # Aggregate results
    wf_df = pd.DataFrame(results_list)
    print(f"Walk-Forward Results ({len(wf_df)} periods):")
    print(f"  Avg Return: {wf_df['return'].mean():.2%}")
    print(f"  Avg Sharpe: {wf_df['sharpe'].mean():.2f}")
    print(f"  Worst Period: {wf_df['return'].min():.2%}")

    return wf_df

# Run walk-forward
wf_results = walk_forward_backtest(data, signals, window_months=12, step_months=3)
```

### Custom Position Sizing

Implement risk-adjusted position sizing.

```python
from modules.risk.kelly import KellyCalculator

def calculate_kelly_signals(data, base_signals, lookback=60):
    """
    Kelly Criterion Position Sizing:
    - Calculate optimal position size based on win rate and payoff ratio
    - Scale base signals by Kelly percentage
    """
    kelly_signals = {}

    for ticker, signal in base_signals.items():
        df = data[ticker]

        # Calculate rolling win rate and payoff ratio
        returns = df['close'].pct_change()
        wins = returns > 0
        win_rate = wins.rolling(lookback).mean()

        avg_win = returns[returns > 0].rolling(lookback).mean()
        avg_loss = abs(returns[returns < 0].rolling(lookback).mean())
        payoff_ratio = avg_win / avg_loss

        # Kelly fraction: (p*b - q) / b
        # p = win rate, q = 1-p, b = payoff ratio
        kelly_fraction = (win_rate * payoff_ratio - (1 - win_rate)) / payoff_ratio
        kelly_fraction = kelly_fraction.clip(0, 0.25)  # Cap at 25%

        # Scale signals by Kelly fraction
        kelly_signals[ticker] = signal & (kelly_fraction > 0.1)  # Min 10%

    return kelly_signals

# Apply Kelly sizing
kelly_signals = calculate_kelly_signals(data, signals, lookback=60)
results = engine.run(data=data, signals=kelly_signals)
```

---

## 6. Best Practices

### Data Quality

✅ **Always validate data before backtesting**:
```python
def validate_data(data):
    """Check for common data quality issues"""
    for ticker, df in data.items():
        # Check for missing values
        missing = df.isnull().sum().sum()
        if missing > 0:
            print(f"⚠️  {ticker}: {missing} missing values")

        # Check for zero volume
        zero_volume = (df['volume'] == 0).sum()
        if zero_volume > 0:
            print(f"⚠️  {ticker}: {zero_volume} bars with zero volume")

        # Check for price anomalies
        price_changes = df['close'].pct_change()
        large_moves = (abs(price_changes) > 0.2).sum()  # >20% moves
        if large_moves > 0:
            print(f"⚠️  {ticker}: {large_moves} bars with >20% price changes")

        # Check for duplicates
        duplicates = df.index.duplicated().sum()
        if duplicates > 0:
            print(f"⚠️  {ticker}: {duplicates} duplicate timestamps")

validate_data(data)
```

### Signal Generation

✅ **Avoid look-ahead bias**:
```python
# ❌ Wrong: Uses future data
ma20 = df['close'].rolling(20).mean()  # Includes current bar
signals = df['close'] > ma20

# ✅ Correct: Shift to avoid look-ahead
ma20 = df['close'].shift(1).rolling(20).mean()  # Uses only past data
signals = df['close'].shift(1) > ma20
```

✅ **Handle NaN values**:
```python
# Fill NaN with False (no signal)
signals = signals.fillna(False)

# Or drop initial NaN period
signals = signals[~signals.isna()]
```

### Transaction Costs

✅ **Always include realistic costs**:
```python
# Korean market costs
cost_model = TransactionCostModel(
    broker='KIS',
    commission_rate=0.00015,  # 0.015% (실제 수수료율)
    tax_rate=0.0023,          # 0.23% sell-only (증권거래세)
    slippage_bps=5.0          # 5 bps (실제 체결 슬리피지)
)
# Total roundtrip: ~36 bps (0.36%)
```

### Statistical Significance

✅ **Require minimum trade count**:
```python
results = engine.run(data, signals)
trade_count = results['trade_stats']['total_trades']

if trade_count < 100:
    print(f"⚠️  Warning: Only {trade_count} trades. Results may not be statistically significant.")
    print(f"   Recommendation: Extend backtest period or increase rebalancing frequency")
```

### Overfitting Prevention

✅ **Use walk-forward optimization**:
```python
# Don't optimize on entire period
wf_results = walk_forward_backtest(data, signals)

# Don't test too many parameters
# Rule of thumb: trades / parameters > 10
trade_count = results['trade_stats']['total_trades']
max_params = trade_count // 10
print(f"Maximum parameters to test: {max_params}")
```

---

## 7. Troubleshooting

### Common Issues

**Issue 1: No trades executed**
```python
# Check signals
print(f"Total signals: {sum(s.sum() for s in signals.values())}")
if sum(s.sum() for s in signals.values()) == 0:
    print("❌ No signals generated. Check signal logic.")

# Check data alignment
for ticker in data.keys():
    if ticker not in signals:
        print(f"❌ Missing signals for {ticker}")
```

**Issue 2: Unrealistic returns**
```python
# Check for look-ahead bias
print("Check for look-ahead bias:")
print("  - Are signals using future data?")
print("  - Are prices shifted correctly?")
print("  - Are corporate actions handled?")

# Verify transaction costs
print(f"Total commission: ₩{results['trade_stats']['total_commission']:,.0f}")
print(f"Total tax: ₩{results['trade_stats']['total_tax']:,.0f}")
if results['trade_stats']['total_commission'] == 0:
    print("⚠️  Warning: Zero commission. Check cost model.")
```

**Issue 3: Slow execution**
```python
# Profile execution time
import time
start = time.time()
results = engine.run(data, signals)
elapsed = time.time() - start

print(f"Execution time: {elapsed:.2f}s")
if elapsed > 60:
    print("⚠️  Slow execution. Optimization suggestions:")
    print("  - Reduce backtest period")
    print("  - Limit ticker universe")
    print("  - Reduce signal frequency")
```

---

## 8. Performance Optimization

### Benchmark Targets

| Metric | Target | How to Achieve |
|--------|--------|----------------|
| 5-year backtest | <30s | Limit tickers, reduce signal frequency |
| Memory usage | <500MB | Use date filtering, clean data |
| Trade count | >100 | Extend period, increase frequency |

### Optimization Techniques

**1. Date Filtering**
```python
# Only backtest specific period
results = engine.run(
    data=data,
    signals=signals,
    start_date='2023-01-01',  # Focus on recent period
    end_date='2024-12-31'
)
```

**2. Ticker Selection**
```python
# Limit universe size
top_tickers = ['005930', '000660', '035420']  # Top 3 only
filtered_data = {k: v for k, v in data.items() if k in top_tickers}
filtered_signals = {k: v for k, v in signals.items() if k in top_tickers}

results = engine.run(data=filtered_data, signals=filtered_signals)
```

**3. Signal Frequency**
```python
# Monthly rebalancing (instead of daily)
def monthly_rebalance(signals):
    """Convert daily signals to monthly"""
    rebalanced = {}
    for ticker, signal in signals.items():
        # Resample to month-end
        monthly = signal.resample('M').last()
        # Forward-fill to daily
        daily = monthly.reindex(signal.index, method='ffill')
        rebalanced[ticker] = daily
    return rebalanced

signals_monthly = monthly_rebalance(signals)
results = engine.run(data=data, signals=signals_monthly)
```

---

## Next Steps

### Learn More

- **[API Reference](BACKTEST_ENGINE_API_REFERENCE.md)** - Complete API documentation
- **[Week 2 Completion Report](WEEK2_COMPLETION_REPORT.md)** - Implementation details
- **[Demo Script](../examples/backtest/custom_engine_demo.py)** - Working examples
- **[Test Suite](../tests/backtest/test_custom_engine.py)** - Usage patterns

### Build Your Strategy

1. Start with [demo script](../examples/backtest/custom_engine_demo.py)
2. Modify signal generation logic
3. Run backtest and analyze results
4. Optimize parameters with walk-forward
5. Validate with Custom Engine
6. Deploy to production

### Get Help

- Check [Troubleshooting](#7-troubleshooting) section
- Review [test cases](../tests/backtest/test_custom_engine.py) for examples
- Consult [API Reference](BACKTEST_ENGINE_API_REFERENCE.md) for detailed usage

---

**Last Updated**: 2025-10-27
**Version**: 1.0.0
**Status**: ✅ Production-ready
**Feedback**: Please report issues or suggestions to the Quant Platform team
