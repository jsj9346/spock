# Backtesting Guide - Quant Investment Platform

**Document Version**: 1.0.0
**Last Updated**: 2025-10-18
**Purpose**: Best practices, common pitfalls, and validation techniques for robust backtesting

---

## Table of Contents

1. [Backtesting Fundamentals](#1-backtesting-fundamentals)
2. [Common Pitfalls & How to Avoid Them](#2-common-pitfalls--how-to-avoid-them)
3. [Walk-Forward Optimization](#3-walk-forward-optimization)
4. [Transaction Cost Modeling](#4-transaction-cost-modeling)
5. [Statistical Validation](#5-statistical-validation)
6. [Backtest Framework Comparison](#6-backtest-framework-comparison)
7. [Best Practices Checklist](#7-best-practices-checklist)
8. [Example Workflows](#8-example-workflows)

---

## 1. Backtesting Fundamentals

### 1.1 What is Backtesting?

**Definition**: Backtesting is the process of testing a trading strategy on historical data to evaluate its performance before deploying it in live markets.

**Purpose**:
- Validate strategy logic and assumptions
- Estimate expected returns and risk
- Identify parameter sensitivity
- Detect overfitting and data snooping bias
- Build confidence before risking real capital

### 1.2 Key Principles

**1. Realism Over Optimism**:
- Include all transaction costs (commission, slippage, spread)
- Use point-in-time data (no look-ahead bias)
- Account for survivorship bias
- Model liquidity constraints

**2. Out-of-Sample Testing**:
- Reserve data for validation (never optimize on test set)
- Use walk-forward analysis for robustness
- Test across different market regimes (bull, bear, sideways)

**3. Statistical Rigor**:
- Require minimum number of trades (>100)
- Test statistical significance (p-value < 0.05)
- Account for multiple testing (Bonferroni correction)

### 1.3 Backtest Quality Metrics

| Metric | Good | Acceptable | Poor |
|--------|------|------------|------|
| **Sharpe Ratio** | >1.5 | 1.0-1.5 | <1.0 |
| **Max Drawdown** | <15% | 15-25% | >25% |
| **Win Rate** | >55% | 50-55% | <50% |
| **Profit Factor** | >1.5 | 1.2-1.5 | <1.2 |
| **Out-of-Sample Sharpe** | >0.8 × In-Sample | 0.6-0.8 × In-Sample | <0.6 × In-Sample |
| **Number of Trades** | >500 | 100-500 | <100 |

---

## 2. Common Pitfalls & How to Avoid Them

### 2.1 Look-Ahead Bias

**Definition**: Using information that would not have been available at the time of the trade.

**Examples**:
- Using adjusted prices without accounting for splits/dividends at trade time
- Calculating technical indicators with future data
- Using end-of-day data for intraday decisions
- Incorporating earnings announcements before public release

**How to Detect**:
```python
# Bad: Look-ahead bias (using future data)
def calculate_signal(prices):
    future_return = (prices.shift(-20) - prices) / prices  # Uses future data!
    return np.where(future_return > 0, 1, -1)

# Good: Point-in-time data only
def calculate_signal(prices):
    momentum = (prices - prices.shift(20)) / prices.shift(20)  # Uses past data only
    return np.where(momentum > 0, 1, -1)
```

**Prevention**:
- Use point-in-time databases (TimescaleDB with date-based queries)
- Validate all indicator calculations (no `.shift(-n)` for signals)
- Review data pipeline for unintentional future leakage
- Use separate train/test periods with strict cutoff dates

---

### 2.2 Survivorship Bias

**Definition**: Only including stocks that currently exist, excluding delisted/bankrupt companies.

**Impact**:
- Overstates backtest performance (excludes losers)
- Estimates suggest 1-3% annual return overstatement

**Example**:
```python
# Bad: Only stocks currently listed (survivorship bias)
tickers = get_current_sp500_constituents()  # Missing delisted stocks

# Good: Use point-in-time S&P 500 constituents
tickers = get_sp500_constituents_at_date('2020-01-01')  # Includes delisted
```

**Prevention**:
- Use survivorship-bias-free databases (CRSP, Compustat, KIS historical data)
- Include delisted stocks in backtest
- Verify ticker count matches historical universe size
- Add "delisting penalty" (assume -30% return on delisting event)

**KIS API Handling**:
```python
# KIS API automatically includes delisted stocks in master file
from modules.api_clients import KISOverseasStockAPI

kis_api = KISOverseasStockAPI(app_key, app_secret)
# Master file includes all stocks (active + delisted)
stocks = kis_api.get_master_data('NASD', include_delisted=True)
```

---

### 2.3 Data Snooping Bias

**Definition**: Testing many strategies on the same dataset until finding one that "works" by chance.

**Impact**:
- False discovery rate: With 20 strategies tested, 1 will appear significant (p<0.05) by chance
- Overfitting to historical noise rather than true patterns

**Example**:
```python
# Bad: Testing 100 different parameter combinations on same data
for ma_short in range(5, 50):
    for ma_long in range(50, 200):
        sharpe = backtest_strategy(ma_short, ma_long, data)
        if sharpe > 1.5:
            print(f"Found great strategy: {ma_short}/{ma_long}")  # Data snooping!
```

**Prevention**:
- **Reserve Out-of-Sample Data**: Never optimize on test set
- **Bonferroni Correction**: Divide p-value by number of tests
  - If testing 20 strategies, require p < 0.05/20 = 0.0025
- **Economic Rationale**: Only test strategies with logical explanation
- **Walk-Forward Validation**: Test on multiple non-overlapping periods

**Bonferroni Correction Example**:
```python
from scipy.stats import ttest_1samp

def test_strategy_significance(returns, n_strategies_tested=20):
    # Null hypothesis: strategy returns = 0
    t_stat, p_value = ttest_1samp(returns, 0)

    # Bonferroni correction
    adjusted_p_value = p_value * n_strategies_tested

    if adjusted_p_value < 0.05:
        print("Strategy is statistically significant after correction")
    else:
        print("Strategy may be due to chance (data snooping)")

    return adjusted_p_value
```

---

### 2.4 Overfitting

**Definition**: Strategy performs well in-sample but fails out-of-sample due to fitting noise.

**Warning Signs**:
- Sharpe ratio: In-sample 2.0, Out-of-sample 0.5 (>50% degradation)
- Too many parameters (>5 parameters for <1000 trades)
- Perfect equity curve in-sample (no drawdowns)
- Strategy logic is complex and unintuitive

**Prevention**:
- **Occam's Razor**: Prefer simpler strategies (fewer parameters)
- **Regularization**: Penalize complexity in ML models
- **Walk-Forward Optimization**: Validate on unseen data
- **Minimum Sample Size**: Require 10× trades per parameter
  - Example: 5 parameters → need 50+ trades minimum

**Complexity Penalty**:
```python
def penalized_sharpe(sharpe_ratio, n_parameters, n_trades):
    # Penalize strategies with too many parameters
    complexity_penalty = np.sqrt(n_parameters / n_trades)
    return sharpe_ratio * (1 - complexity_penalty)

# Example
in_sample_sharpe = 2.0
n_params = 10
n_trades = 100

penalized = penalized_sharpe(in_sample_sharpe, n_params, n_trades)
# 2.0 * (1 - sqrt(10/100)) = 2.0 * 0.68 = 1.36 (more realistic)
```

---

### 2.5 Transaction Costs Underestimation

**Definition**: Ignoring or underestimating trading costs (commission, slippage, spread).

**Impact**:
- High-frequency strategies often become unprofitable after costs
- Realistic cost model can reduce backtest returns by 2-5% annually

**Common Mistakes**:
```python
# Bad: No transaction costs
portfolio_value += shares * (sell_price - buy_price)

# Bad: Only commission, no slippage
transaction_cost = shares * price * 0.00015  # Commission only

# Good: Commission + Slippage + Spread
commission = shares * price * 0.00015
slippage = shares * price * 0.001  # Market impact
spread = shares * bid_ask_spread / 2
total_cost = commission + slippage + spread
```

**Realistic Transaction Cost Model** (See Section 4 for details):
- **Commission**: 0.015% (KIS API standard)
- **Slippage**: Almgren-Chriss model (volume-dependent)
- **Spread**: Bid-ask spread (0.05-0.20% for liquid stocks)
- **Partial Fills**: Probability-based modeling

---

### 2.6 Ignoring Market Impact

**Definition**: Assuming you can trade unlimited size without affecting prices.

**Reality**:
- Large orders move the market (price slippage)
- Liquidity is finite (can't buy $100M of a $10M stock)

**Market Impact Formula** (Almgren-Chriss):
```python
def calculate_market_impact(order_size, avg_daily_volume, price):
    """
    Almgren-Chriss market impact model

    Permanent Impact: k1 × (order_size / ADV)^0.5
    Temporary Impact: k2 × (order_size / ADV)

    Parameters:
        k1 = 0.1 (permanent impact coefficient)
        k2 = 0.5 (temporary impact coefficient)
    """
    volume_fraction = order_size / avg_daily_volume

    permanent_impact = 0.1 * (volume_fraction ** 0.5) * price
    temporary_impact = 0.5 * volume_fraction * price

    total_impact = permanent_impact + temporary_impact
    return total_impact

# Example
order_size = 10000  # shares
adv = 100000  # avg daily volume
price = 50.0

impact = calculate_market_impact(order_size, adv, price)
# volume_fraction = 0.1 (10% of ADV)
# permanent = 0.1 × 0.316 × 50 = 1.58
# temporary = 0.5 × 0.1 × 50 = 2.5
# total = 4.08 per share → $40,800 total cost
```

**Prevention**:
- Limit position size to <10% of average daily volume
- Use volume-based slippage model
- Implement participation rate limits (e.g., max 20% of market volume)

---

### 2.7 Parameter Sensitivity

**Definition**: Strategy performance changes dramatically with small parameter adjustments.

**Warning Sign**:
```python
# Example: Moving average crossover
MA_SHORT = 20  # Sharpe = 1.8
MA_SHORT = 21  # Sharpe = 0.5  # Too sensitive!
```

**Prevention**:
- **Robustness Test**: Vary each parameter ±20% and check performance degradation
- **Heatmap Analysis**: Visualize Sharpe ratio across parameter grid
- **Smooth Performance Surface**: Prefer parameters with stable neighborhoods

**Robustness Check**:
```python
def test_parameter_robustness(base_params, param_name, variation_range=0.2):
    """
    Test strategy performance across parameter range

    Returns:
        mean_sharpe: Average Sharpe across variations
        std_sharpe: Standard deviation of Sharpe
    """
    sharpe_ratios = []
    base_value = base_params[param_name]

    for multiplier in np.linspace(1 - variation_range, 1 + variation_range, 10):
        test_params = base_params.copy()
        test_params[param_name] = base_value * multiplier

        result = backtest_strategy(test_params)
        sharpe_ratios.append(result['sharpe_ratio'])

    mean_sharpe = np.mean(sharpe_ratios)
    std_sharpe = np.std(sharpe_ratios)

    # Robust if std < 20% of mean
    if std_sharpe / mean_sharpe < 0.2:
        print(f"{param_name} is robust")
    else:
        print(f"{param_name} is too sensitive (std/mean = {std_sharpe/mean_sharpe:.2f})")

    return mean_sharpe, std_sharpe
```

---

## 3. Walk-Forward Optimization

### 3.1 Concept

**Definition**: A method to validate strategy robustness by repeatedly training on in-sample data and testing on out-of-sample data.

**Process**:
```
In-Sample Training (3 years) → Out-of-Sample Test (1 year) → Roll Forward → Repeat

├─ 2015-2017 train → 2018 test
├─ 2016-2018 train → 2019 test
├─ 2017-2019 train → 2020 test
├─ 2018-2020 train → 2021 test
├─ 2019-2021 train → 2022 test
└─ 2020-2022 train → 2023 test
```

**Why It Works**:
- Prevents overfitting to single historical period
- Simulates real-world deployment (periodic reoptimization)
- Provides multiple out-of-sample tests (more robust than single train/test split)

### 3.2 Implementation

```python
class WalkForwardOptimizer:
    def __init__(self, db, strategy, param_grid):
        self.db = db
        self.strategy = strategy
        self.param_grid = param_grid

    def run_walk_forward(self, start_date, end_date, train_period_years=3, test_period_years=1):
        """
        Run walk-forward optimization

        Args:
            start_date: Overall start date
            end_date: Overall end date
            train_period_years: In-sample training period
            test_period_years: Out-of-sample test period

        Returns:
            results: List of out-of-sample test results
        """
        results = []
        current_date = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        while current_date + pd.DateOffset(years=train_period_years + test_period_years) <= end:
            # Define train and test windows
            train_start = current_date
            train_end = current_date + pd.DateOffset(years=train_period_years)
            test_start = train_end
            test_end = test_start + pd.DateOffset(years=test_period_years)

            # Optimize on in-sample data
            best_params = self._optimize_in_sample(train_start, train_end)

            # Test on out-of-sample data
            oos_result = self._backtest_out_of_sample(best_params, test_start, test_end)

            results.append({
                'train_period': f"{train_start.date()} to {train_end.date()}",
                'test_period': f"{test_start.date()} to {test_end.date()}",
                'best_params': best_params,
                'oos_sharpe': oos_result['sharpe_ratio'],
                'oos_total_return': oos_result['total_return'],
                'oos_max_drawdown': oos_result['max_drawdown']
            })

            # Roll forward by test_period_years
            current_date = test_start

        return pd.DataFrame(results)

    def _optimize_in_sample(self, start_date, end_date):
        """Optimize parameters on in-sample data (grid search)"""
        best_sharpe = -np.inf
        best_params = None

        for params in self._generate_param_combinations():
            result = self.strategy.backtest(params, start_date, end_date)
            if result['sharpe_ratio'] > best_sharpe:
                best_sharpe = result['sharpe_ratio']
                best_params = params

        return best_params

    def _backtest_out_of_sample(self, params, start_date, end_date):
        """Run backtest on out-of-sample data with fixed parameters"""
        return self.strategy.backtest(params, start_date, end_date)

    def _generate_param_combinations(self):
        """Generate all parameter combinations from param_grid"""
        import itertools
        keys = self.param_grid.keys()
        values = self.param_grid.values()
        for combination in itertools.product(*values):
            yield dict(zip(keys, combination))
```

**Usage Example**:
```python
# Define strategy and parameter grid
strategy = MomentumValueStrategy(db)
param_grid = {
    'momentum_lookback': [6, 12, 18],  # months
    'value_factor': ['PE', 'PB', 'EV_EBITDA'],
    'rebalance_freq': ['monthly', 'quarterly']
}

# Run walk-forward optimization
wfo = WalkForwardOptimizer(db, strategy, param_grid)
results = wfo.run_walk_forward(
    start_date='2015-01-01',
    end_date='2024-01-01',
    train_period_years=3,
    test_period_years=1
)

# Analyze results
print(results)
print(f"Average OOS Sharpe: {results['oos_sharpe'].mean():.2f}")
print(f"Sharpe Stability (std): {results['oos_sharpe'].std():.2f}")
```

### 3.3 Acceptance Criteria

**Out-of-Sample Performance Degradation**:
- **Excellent**: OOS Sharpe > 0.9 × In-Sample Sharpe
- **Good**: OOS Sharpe > 0.8 × In-Sample Sharpe
- **Acceptable**: OOS Sharpe > 0.7 × In-Sample Sharpe
- **Poor**: OOS Sharpe < 0.7 × In-Sample Sharpe (likely overfit)

**Other Checks**:
- Max Drawdown: OOS < 1.5 × In-Sample
- Win Rate: OOS > 0.9 × In-Sample
- Profit Factor: OOS > 0.8 × In-Sample

**Example Validation**:
```python
def validate_walk_forward_results(results):
    """
    Validate walk-forward optimization results

    Criteria:
        1. Average OOS Sharpe > 1.0
        2. OOS Sharpe std < 0.3 (stability)
        3. No period with OOS Sharpe < 0.5
    """
    avg_oos_sharpe = results['oos_sharpe'].mean()
    std_oos_sharpe = results['oos_sharpe'].std()
    min_oos_sharpe = results['oos_sharpe'].min()

    print("Walk-Forward Validation:")
    print(f"  Average OOS Sharpe: {avg_oos_sharpe:.2f}")
    print(f"  OOS Sharpe Stability (std): {std_oos_sharpe:.2f}")
    print(f"  Minimum OOS Sharpe: {min_oos_sharpe:.2f}")

    passed = True
    if avg_oos_sharpe < 1.0:
        print("  ❌ FAIL: Average OOS Sharpe < 1.0")
        passed = False
    if std_oos_sharpe > 0.3:
        print("  ❌ FAIL: OOS Sharpe too unstable (std > 0.3)")
        passed = False
    if min_oos_sharpe < 0.5:
        print("  ❌ FAIL: At least one period with OOS Sharpe < 0.5")
        passed = False

    if passed:
        print("  ✅ PASS: Strategy is robust")

    return passed
```

---

## 4. Transaction Cost Modeling

### 4.1 Components of Transaction Costs

**1. Commission** (Fixed):
- Korea: 0.015% (KIS API standard)
- US: $0.005/share or 0.015% (whichever higher)
- Other markets: 0.02-0.05%

**2. Slippage** (Variable):
- Market impact: Almgren-Chriss model
- Depends on order size vs average daily volume

**3. Bid-Ask Spread** (Variable):
- Direct measurement from order book
- Fallback: Estimated spread = 0.1% / √(market_cap_billions)

**4. Partial Fills** (Probabilistic):
- Probability of full fill = min(1, ADV / order_size)
- If partial, assume 50% fill rate, rest at VWAP + 0.5%

### 4.2 Complete Transaction Cost Model

```python
class TransactionCostModel:
    def __init__(self, commission_rate=0.00015, k1=0.1, k2=0.5):
        """
        Initialize transaction cost model

        Args:
            commission_rate: Fixed commission rate (0.015% = 0.00015)
            k1: Permanent market impact coefficient (default: 0.1)
            k2: Temporary market impact coefficient (default: 0.5)
        """
        self.commission_rate = commission_rate
        self.k1 = k1
        self.k2 = k2

    def calculate_total_cost(self, order_size, price, avg_daily_volume, spread=None, market_cap=None):
        """
        Calculate total transaction cost

        Args:
            order_size: Number of shares
            price: Current price
            avg_daily_volume: Average daily volume (shares)
            spread: Bid-ask spread (optional, estimated if not provided)
            market_cap: Market capitalization in billions (for spread estimation)

        Returns:
            total_cost: Total transaction cost in currency
        """
        # 1. Commission (fixed)
        order_value = order_size * price
        commission = order_value * self.commission_rate

        # 2. Market impact (Almgren-Chriss)
        volume_fraction = order_size / avg_daily_volume
        permanent_impact = self.k1 * (volume_fraction ** 0.5) * price
        temporary_impact = self.k2 * volume_fraction * price
        slippage = (permanent_impact + temporary_impact) * order_size

        # 3. Bid-ask spread
        if spread is None:
            # Estimate spread based on market cap
            if market_cap is not None:
                spread = (0.001 / np.sqrt(market_cap)) * price  # 0.1% / sqrt(mcap_billions)
            else:
                spread = 0.001 * price  # Default 0.1%

        spread_cost = order_size * spread / 2

        # Total cost
        total_cost = commission + slippage + spread_cost

        return {
            'commission': commission,
            'slippage': slippage,
            'spread_cost': spread_cost,
            'total_cost': total_cost,
            'cost_bps': (total_cost / order_value) * 10000  # Basis points
        }

# Usage example
cost_model = TransactionCostModel()

result = cost_model.calculate_total_cost(
    order_size=1000,  # shares
    price=50.0,  # USD
    avg_daily_volume=100000,  # shares
    market_cap=10.0  # $10 billion
)

print(f"Commission: ${result['commission']:.2f}")
print(f"Slippage: ${result['slippage']:.2f}")
print(f"Spread Cost: ${result['spread_cost']:.2f}")
print(f"Total Cost: ${result['total_cost']:.2f}")
print(f"Cost (bps): {result['cost_bps']:.2f}")
```

### 4.3 Integration with Backtesting Engine

```python
# backtrader integration
class RealisticCommissionScheme(bt.CommInfoBase):
    def __init__(self, cost_model):
        super().__init__()
        self.cost_model = cost_model

    def _getcommission(self, size, price, pseudoexec):
        # Get stock metadata
        avg_daily_volume = self.data.avg_volume  # From data feed
        market_cap = self.data.market_cap  # From data feed

        # Calculate realistic cost
        result = self.cost_model.calculate_total_cost(
            order_size=abs(size),
            price=price,
            avg_daily_volume=avg_daily_volume,
            market_cap=market_cap
        )

        return result['total_cost']
```

---

## 5. Statistical Validation

### 5.1 Minimum Sample Size

**Rule of Thumb**: Require at least 100 trades for meaningful statistics.

**Reasoning**:
- Sharpe ratio standard error: σ_sharpe ≈ 1 / √N
- With N=100 trades: σ_sharpe ≈ 0.1
- With N=25 trades: σ_sharpe ≈ 0.2 (too high)

**Check**:
```python
def check_minimum_sample_size(n_trades, min_trades=100):
    if n_trades < min_trades:
        print(f"⚠️  WARNING: Only {n_trades} trades (minimum {min_trades} recommended)")
        print(f"   Sharpe ratio standard error: ±{1/np.sqrt(n_trades):.2f}")
        return False
    else:
        print(f"✅ Sufficient sample size: {n_trades} trades")
        return True
```

### 5.2 Statistical Significance Testing

**Null Hypothesis**: Strategy returns = 0 (no edge)

**T-Test**:
```python
from scipy.stats import ttest_1samp

def test_strategy_significance(returns, alpha=0.05):
    """
    Test if strategy returns are significantly different from zero

    Args:
        returns: Series of strategy returns
        alpha: Significance level (default: 0.05)

    Returns:
        p_value: Probability that returns are due to chance
        is_significant: True if p_value < alpha
    """
    t_stat, p_value = ttest_1samp(returns, 0)

    print(f"T-statistic: {t_stat:.2f}")
    print(f"P-value: {p_value:.4f}")

    if p_value < alpha:
        print(f"✅ Strategy is statistically significant (p < {alpha})")
        return p_value, True
    else:
        print(f"❌ Strategy is NOT statistically significant (p = {p_value:.4f})")
        return p_value, False

# Example
strategy_returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.01, ...])  # Daily returns
p_value, is_significant = test_strategy_significance(strategy_returns)
```

### 5.3 Monte Carlo Simulation

**Purpose**: Test if backtest results could have occurred by chance.

**Method**:
1. Shuffle trade returns randomly (preserving distribution)
2. Recalculate Sharpe ratio
3. Repeat 1000 times
4. Compare actual Sharpe to distribution

```python
def monte_carlo_validation(trade_returns, n_simulations=1000):
    """
    Monte Carlo validation of backtest results

    Args:
        trade_returns: Actual trade returns from backtest
        n_simulations: Number of random shuffles

    Returns:
        p_value: Probability of achieving actual Sharpe by chance
    """
    actual_sharpe = np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(252)

    simulated_sharpes = []
    for _ in range(n_simulations):
        # Shuffle returns (preserving distribution)
        shuffled_returns = np.random.permutation(trade_returns)
        shuffled_sharpe = np.mean(shuffled_returns) / np.std(shuffled_returns) * np.sqrt(252)
        simulated_sharpes.append(shuffled_sharpe)

    # Calculate p-value: % of simulations with Sharpe >= actual
    p_value = (np.array(simulated_sharpes) >= actual_sharpe).sum() / n_simulations

    print(f"Actual Sharpe Ratio: {actual_sharpe:.2f}")
    print(f"Simulated Sharpe (mean): {np.mean(simulated_sharpes):.2f}")
    print(f"P-value: {p_value:.4f}")

    if p_value < 0.05:
        print("✅ Strategy unlikely due to chance")
    else:
        print("❌ Strategy may be due to luck")

    return p_value, simulated_sharpes
```

---

## 6. Backtest Framework Comparison

### 6.1 Framework Selection Guide

| Framework | Best For | Pros | Cons |
|-----------|----------|------|------|
| **backtrader** | Custom strategies, flexibility | Event-driven, extensive indicators, active community | Slower, complex API |
| **zipline** | Quantopian-style, institutional | Pipeline API, production-grade, factor analysis | Steep learning curve, less flexible |
| **vectorbt** | Parameter optimization, speed | 100x faster (vectorized), built-in metrics | Limited flexibility, newer project |

### 6.2 backtrader Example

```python
import backtrader as bt

class MomentumStrategy(bt.Strategy):
    params = (
        ('momentum_period', 12),  # 12-month momentum
        ('rebalance_freq', 'monthly'),
    )

    def __init__(self):
        # Calculate 12-month momentum for each stock
        self.momentum = {}
        for d in self.datas:
            self.momentum[d] = bt.indicators.ROC(d.close, period=self.params.momentum_period * 21)

    def next(self):
        # Monthly rebalancing
        if self.datetime.date().day != 1:
            return

        # Sort stocks by momentum
        ranked = sorted(self.datas, key=lambda d: self.momentum[d][0], reverse=True)

        # Buy top 20%, sell bottom 20%
        top_20 = ranked[:len(ranked)//5]
        bottom_20 = ranked[-len(ranked)//5:]

        # Execute trades
        for d in top_20:
            self.order_target_percent(d, target=0.05)  # 5% per stock

        for d in bottom_20:
            self.order_target_percent(d, target=0.0)  # Close position

# Run backtest
cerebro = bt.Cerebro()
cerebro.addstrategy(MomentumStrategy)

# Add data feeds (one per stock)
for ticker in ['AAPL', 'MSFT', 'GOOGL']:
    data = bt.feeds.PandasData(dataname=load_ohlcv_data(ticker))
    cerebro.adddata(data)

# Set initial capital and commission
cerebro.broker.setcash(100000)
cerebro.broker.setcommission(commission=0.00015)

# Run
results = cerebro.run()
cerebro.plot()
```

### 6.3 zipline Example

```python
from zipline import run_algorithm
from zipline.pipeline import Pipeline
from zipline.pipeline.factors import Returns

def initialize(context):
    # Define universe and factors
    pipeline = Pipeline()
    momentum = Returns(window_length=252)  # 12-month momentum
    pipeline.add(momentum, 'momentum')

    context.attach_pipeline(pipeline, 'factors')

def handle_data(context, data):
    # Get factor scores
    factors = context.pipeline_output('factors')

    # Rank stocks by momentum
    ranked = factors.sort_values('momentum', ascending=False)

    # Buy top 20%
    top_20 = ranked.head(len(ranked) // 5)

    for stock in top_20.index:
        order_target_percent(stock, 0.05)  # 5% per stock

# Run backtest
run_algorithm(
    start='2015-01-01',
    end='2024-01-01',
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000,
    bundle='quandl'
)
```

---

## 7. Best Practices Checklist

### 7.1 Pre-Backtest Checklist

- [ ] **Data Quality**:
  - [ ] Check for missing data (gaps, NaN values)
  - [ ] Validate OHLCV data (open ≤ high, low ≤ close)
  - [ ] Verify corporate actions (splits, dividends) are adjusted
  - [ ] Confirm survivorship-bias-free dataset

- [ ] **Strategy Definition**:
  - [ ] Strategy has economic rationale (not just curve-fitting)
  - [ ] Parameters have intuitive ranges
  - [ ] Signal calculation uses point-in-time data only

- [ ] **Universe Selection**:
  - [ ] Minimum liquidity filter (> $1M daily volume)
  - [ ] Market cap filter (avoid micro-caps if needed)
  - [ ] Sector diversification constraints

### 7.2 During-Backtest Checklist

- [ ] **Transaction Costs**:
  - [ ] Include commission (0.015%)
  - [ ] Model slippage (market impact)
  - [ ] Account for bid-ask spread
  - [ ] Limit position size to <10% ADV

- [ ] **Risk Management**:
  - [ ] Implement stop-loss rules
  - [ ] Position size limits (max 15% per stock)
  - [ ] Sector concentration limits (max 40%)
  - [ ] Cash reserve (min 10%)

- [ ] **Execution Constraints**:
  - [ ] Respect market hours (no after-hours trading)
  - [ ] Trading halt detection
  - [ ] Tick size compliance (if applicable)

### 7.3 Post-Backtest Checklist

- [ ] **Performance Metrics**:
  - [ ] Sharpe ratio > 1.0
  - [ ] Max drawdown < 20%
  - [ ] Win rate > 50%
  - [ ] Minimum 100 trades

- [ ] **Statistical Validation**:
  - [ ] P-value < 0.05 (t-test)
  - [ ] Monte Carlo validation passed
  - [ ] Walk-forward optimization passed

- [ ] **Robustness Tests**:
  - [ ] Parameter sensitivity < 20% degradation
  - [ ] Performance across market regimes (bull, bear, sideways)
  - [ ] Out-of-sample Sharpe > 0.8 × in-sample

- [ ] **Documentation**:
  - [ ] Strategy logic documented
  - [ ] Parameter choices explained
  - [ ] Assumptions stated
  - [ ] Known limitations acknowledged

---

## 8. Example Workflows

### 8.1 Complete Backtest Workflow

```python
# Step 1: Load data (survivorship-bias-free)
from modules.db_manager_postgres import PostgreSQLDatabaseManager

db = PostgreSQLDatabaseManager()
tickers = db.get_sp500_constituents_at_date('2015-01-01', include_delisted=True)
ohlcv_data = db.get_ohlcv_data(tickers, start_date='2015-01-01', end_date='2024-01-01')

# Step 2: Define strategy
class MomentumValueStrategy:
    def __init__(self, db, momentum_period=12, value_factor='PE'):
        self.db = db
        self.momentum_period = momentum_period
        self.value_factor = value_factor

    def generate_signals(self, date):
        # Calculate factors
        momentum_scores = self.calculate_momentum(date, period=self.momentum_period)
        value_scores = self.calculate_value(date, factor=self.value_factor)

        # Combine factors (equal weight)
        composite = (momentum_scores + value_scores) / 2

        # Select top 20%
        threshold = composite.quantile(0.8)
        signals = composite >= threshold
        return signals

# Step 3: Run backtest with transaction costs
from modules.backtest import BacktestEngine, TransactionCostModel

cost_model = TransactionCostModel(commission_rate=0.00015, k1=0.1, k2=0.5)
engine = BacktestEngine(db, cost_model=cost_model)

strategy = MomentumValueStrategy(db, momentum_period=12, value_factor='PE')
result = engine.run_backtest(
    strategy=strategy,
    start_date='2015-01-01',
    end_date='2024-01-01',
    initial_capital=100000
)

# Step 4: Validate results
print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {result['max_drawdown']:.2%}")
print(f"Total Return: {result['total_return']:.2%}")
print(f"Number of Trades: {result['num_trades']}")

# Step 5: Walk-forward optimization
wfo = WalkForwardOptimizer(db, strategy, param_grid={
    'momentum_period': [6, 12, 18],
    'value_factor': ['PE', 'PB', 'EV_EBITDA']
})

wf_results = wfo.run_walk_forward(
    start_date='2015-01-01',
    end_date='2024-01-01',
    train_period_years=3,
    test_period_years=1
)

print(f"Average OOS Sharpe: {wf_results['oos_sharpe'].mean():.2f}")

# Step 6: Statistical validation
from scipy.stats import ttest_1samp

t_stat, p_value = ttest_1samp(result['trade_returns'], 0)
print(f"P-value: {p_value:.4f}")

if p_value < 0.05:
    print("✅ Strategy is statistically significant")
else:
    print("❌ Strategy may be due to chance")
```

---

## Appendix: Common Backtest Mistakes

### Mistake 1: Using Adjusted Prices Incorrectly
```python
# Bad: Trading at adjusted prices (not realistic)
buy_price = adjusted_close['2020-01-01']  # Wrong

# Good: Use unadjusted prices for execution, adjust returns
buy_price = unadjusted_close['2020-01-01']
returns = adjusted_close.pct_change()  # Correct
```

### Mistake 2: Ignoring Trading Halts
```python
# Bad: Assuming you can always exit
sell_signal = True
exit_position()  # May fail if stock is halted

# Good: Check trading status
if not is_trading_halted(ticker, date):
    exit_position()
```

### Mistake 3: Unrealistic Fill Assumptions
```python
# Bad: Assume 100% fill at limit price
fill_price = limit_price

# Good: Model partial fills
fill_rate = min(1.0, avg_daily_volume / order_size)
if np.random.random() < fill_rate:
    fill_price = limit_price
else:
    fill_price = market_price + slippage
```

---

**Document End**

**Related Documents**:
1. [QUANT_PLATFORM_ARCHITECTURE.md](QUANT_PLATFORM_ARCHITECTURE.md) - System architecture
2. [FACTOR_LIBRARY_REFERENCE.md](FACTOR_LIBRARY_REFERENCE.md) - Factor definitions
3. [OPTIMIZATION_COOKBOOK.md](OPTIMIZATION_COOKBOOK.md) - Portfolio optimization
4. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database schema
