# Backtesting Engine API Reference

**Module**: `modules.backtest.custom.backtest_engine`
**Purpose**: Production-grade event-driven backtesting engine with order-level detail
**Performance**: <30s for 5-year backtest (10 stocks)
**Status**: ✅ Production-ready (Week 2 completed)

---

## Table of Contents
1. [Overview](#overview)
2. [Core Classes](#core-classes)
3. [Data Structures](#data-structures)
4. [Usage Examples](#usage-examples)
5. [Performance Characteristics](#performance-characteristics)
6. [Integration Guide](#integration-guide)

---

## Overview

The Custom Event-Driven Backtesting Engine provides realistic bar-by-bar simulation with full order execution detail, complementing VectorBT's vectorized approach.

### Key Features
- ✅ **Event-Driven Simulation**: Bar-by-bar processing for realistic market conditions
- ✅ **Position Tracking**: Full portfolio management with realized/unrealized P&L
- ✅ **Trade Logging**: Complete entry/exit details with transaction costs
- ✅ **Order Execution**: Integration with OrderExecutionEngine for realistic fills
- ✅ **Performance Metrics**: Comprehensive analytics (Sharpe, Sortino, Max DD, etc.)

### Use Cases
- **Production Validation**: Validate strategies before live trading
- **Compliance Auditing**: Full trade log with entry/exit timestamps
- **Custom Order Logic**: Implement complex order types and execution rules
- **Realistic Simulation**: Account for market microstructure (slippage, partial fills)

---

## Core Classes

### 1. BacktestEngine

Main orchestrator for event-driven backtesting.

#### Constructor

```python
BacktestEngine(
    initial_capital: float,
    cost_model: Optional[TransactionCostModel] = None,
    size_type: str = 'equal_weight',
    target_positions: Optional[int] = None
)
```

**Parameters**:
- `initial_capital` (float): Starting portfolio value in base currency (KRW)
- `cost_model` (TransactionCostModel, optional): Transaction cost model (default: KIS broker)
- `size_type` (str, optional): Position sizing method ('equal_weight', 'percent', 'shares')
- `target_positions` (int, optional): Number of positions to hold simultaneously

**Example**:
```python
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.common.costs import TransactionCostModel

engine = BacktestEngine(
    initial_capital=100_000_000,  # 100M KRW
    cost_model=TransactionCostModel(broker='KIS', slippage_bps=5.0),
    size_type='equal_weight',
    target_positions=3
)
```

#### Methods

##### `run()`

Execute backtest with provided data and signals.

```python
run(
    data: Dict[str, pd.DataFrame],
    signals: Dict[str, pd.Series],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict
```

**Parameters**:
- `data` (Dict[str, pd.DataFrame]): OHLCV data for each ticker
  - Keys: Ticker symbols (e.g., '005930')
  - Values: DataFrames with columns ['open', 'high', 'low', 'close', 'volume']
  - Index: DatetimeIndex
- `signals` (Dict[str, pd.Series]): Boolean signals for each ticker
  - Keys: Ticker symbols (matching data keys)
  - Values: Boolean Series (True = should hold position)
  - Index: DatetimeIndex (matching data index)
- `start_date` (str, optional): Backtest start date (YYYY-MM-DD)
- `end_date` (str, optional): Backtest end date (YYYY-MM-DD)

**Returns**: Dictionary with the following keys:
```python
{
    'metrics': {
        'total_return_pct': float,      # Total return percentage
        'annualized_return': float,     # Annualized return
        'sharpe_ratio': float,          # Risk-adjusted return
        'sortino_ratio': float,         # Downside risk-adjusted return
        'calmar_ratio': float,          # Return / max drawdown
        'max_drawdown': float,          # Maximum portfolio decline
        'volatility': float,            # Annualized volatility
        'win_rate': float,              # Percentage of winning trades
        'profit_factor': float,         # Gross profit / gross loss
        ...
    },
    'equity_curve': pd.DataFrame,       # Portfolio value over time
    'trades': pd.DataFrame,             # Complete trade log
    'trade_stats': {
        'total_trades': int,            # Number of completed trades
        'winning_trades': int,          # Number of profitable trades
        'losing_trades': int,           # Number of losing trades
        'win_rate': float,              # winning_trades / total_trades
        'avg_win': float,               # Average profit per winning trade
        'avg_loss': float,              # Average loss per losing trade
        'avg_holding_days': float,      # Average trade duration
        'total_commission': float,      # Total commission paid
        'total_tax': float,             # Total tax paid (KR: 0.23% sell-only)
        ...
    },
    'execution_time': float             # Backtest runtime in seconds
}
```

**Example**:
```python
# Prepare data
data = {
    '005930': pd.DataFrame({
        'open': [...],
        'high': [...],
        'low': [...],
        'close': [...],
        'volume': [...]
    }, index=pd.date_range('2020-01-01', '2024-12-31'))
}

# Generate signals (e.g., momentum strategy)
signals = {
    '005930': data['005930']['close'] > data['005930']['close'].rolling(20).mean()
}

# Run backtest
results = engine.run(
    data=data,
    signals=signals,
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# Access results
print(f"Total Return: {results['metrics']['total_return_pct']:.2%}")
print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
print(f"Total Trades: {results['trade_stats']['total_trades']}")
```

---

### 2. PositionTracker

Portfolio position and cash management system.

#### Constructor

```python
PositionTracker(initial_capital: float)
```

**Parameters**:
- `initial_capital` (float): Starting cash balance

#### Key Methods

##### `add_position()`
Add new position or scale existing position (average up).

```python
add_position(
    ticker: str,
    quantity: int,
    price: float,
    date: datetime
) -> None
```

##### `reduce_position()`
Reduce or close position (FIFO accounting).

```python
reduce_position(
    ticker: str,
    quantity: int
) -> Optional[Position]
```

**Returns**: Closed Position object if fully exited, None if still holding

##### `update_prices()`
Update current prices and unrealized P&L for all positions.

```python
update_prices(prices: Dict[str, float]) -> None
```

##### `get_portfolio_value()`
Calculate total portfolio value (cash + holdings).

```python
get_portfolio_value() -> float
```

##### `record_equity()`
Record equity curve point for performance tracking.

```python
record_equity(date: datetime) -> None
```

**Example**:
```python
tracker = PositionTracker(initial_capital=100_000_000)

# Enter position
tracker.cash -= 60_000 * 100  # Deduct purchase cost
tracker.add_position('005930', 100, 60000, datetime(2024, 1, 1))

# Update prices
tracker.update_prices({'005930': 66000})

# Check unrealized P&L
position = tracker.get_position('005930')
print(f"Unrealized P&L: ₩{position.unrealized_pnl:,.0f}")  # ₩600,000

# Get portfolio value
portfolio_value = tracker.get_portfolio_value()
print(f"Portfolio Value: ₩{portfolio_value:,.0f}")

# Exit position
closed_position = tracker.reduce_position('005930', 100)
if closed_position:
    print(f"Position closed: {closed_position.ticker}")
```

---

### 3. SignalInterpreter

Translates strategy signals into order submissions.

#### Constructor

```python
SignalInterpreter(
    tracker: PositionTracker,
    order_engine: OrderExecutionEngine,
    target_positions: Optional[int] = None,
    size_type: str = 'equal_weight'
)
```

**Parameters**:
- `tracker` (PositionTracker): Portfolio tracker instance
- `order_engine` (OrderExecutionEngine): Order execution engine
- `target_positions` (int, optional): Max positions to hold
- `size_type` (str): Position sizing method

#### Key Methods

##### `interpret_signals()`
Generate orders from current signals and positions.

```python
interpret_signals(
    signals: Dict[str, bool],
    prices: Dict[str, float],
    date: datetime
) -> List[Order]
```

**Parameters**:
- `signals` (Dict[str, bool]): Current signals for each ticker
- `prices` (Dict[str, float]): Current prices for each ticker
- `date` (datetime): Current bar timestamp

**Returns**: List of Order objects to execute

**Signal Interpretation Logic**:
1. **Exit Orders**: Generate SELL orders for positions with False signals
2. **Entry Orders**: Generate BUY orders for tickers with True signals (not currently held)
3. **Position Sizing**: Calculate quantity based on equal weight allocation

**Example**:
```python
interpreter = SignalInterpreter(
    tracker=position_tracker,
    order_engine=execution_engine,
    target_positions=3,
    size_type='equal_weight'
)

# Current state: Holding 005930, signals for 000660 and 035420
signals = {
    '005930': False,  # Exit
    '000660': True,   # Enter
    '035420': True    # Enter
}
prices = {
    '005930': 66000,
    '000660': 45000,
    '035420': 50000
}

orders = interpreter.interpret_signals(signals, prices, datetime(2024, 1, 15))
# Returns: [SELL 005930, BUY 000660, BUY 035420]
```

---

### 4. TradeLogger

Records and analyzes completed trades.

#### Constructor

```python
TradeLogger()
```

#### Key Methods

##### `record_trade()`
Log completed trade with full details.

```python
record_trade(
    ticker: str,
    entry_date: datetime,
    exit_date: datetime,
    entry_price: float,
    exit_price: float,
    quantity: int,
    commission: float,
    tax: float
) -> None
```

##### `get_trade_stats()`
Calculate aggregate trade statistics.

```python
get_trade_stats() -> Dict
```

**Returns**:
```python
{
    'total_trades': int,
    'winning_trades': int,
    'losing_trades': int,
    'win_rate': float,
    'avg_win': float,
    'avg_loss': float,
    'avg_holding_days': float,
    'total_commission': float,
    'total_tax': float
}
```

##### `get_trades_df()`
Convert trade log to DataFrame for analysis.

```python
get_trades_df() -> pd.DataFrame
```

**Example**:
```python
logger = TradeLogger()

# Record trade
logger.record_trade(
    ticker='005930',
    entry_date=datetime(2024, 1, 1),
    exit_date=datetime(2024, 2, 1),
    entry_price=60000,
    exit_price=66000,
    quantity=100,
    commission=900,
    tax=15180
)

# Get statistics
stats = logger.get_trade_stats()
print(f"Win Rate: {stats['win_rate']:.2%}")
print(f"Average Win: ₩{stats['avg_win']:,.0f}")

# Export to DataFrame
trades_df = logger.get_trades_df()
print(trades_df[['ticker', 'entry_date', 'exit_date', 'pnl', 'pnl_pct']])
```

---

## Data Structures

### Position

```python
@dataclass
class Position:
    ticker: str              # Stock ticker symbol
    quantity: int            # Number of shares
    entry_price: float       # Average entry price
    entry_date: datetime     # Initial entry timestamp
    current_price: float     # Latest market price
    unrealized_pnl: float    # Unrealized profit/loss
```

### Trade

```python
@dataclass
class Trade:
    ticker: str              # Stock ticker symbol
    side: str                # 'LONG' or 'SHORT'
    entry_date: datetime     # Entry timestamp
    exit_date: datetime      # Exit timestamp
    entry_price: float       # Entry price
    exit_price: float        # Exit price
    quantity: int            # Number of shares
    pnl: float               # Realized profit/loss
    pnl_pct: float           # Return percentage
    commission: float        # Total commission paid
    tax: float               # Transaction tax (KR: 0.23% sell)
    holding_days: int        # Trade duration in days
```

---

## Usage Examples

### Basic Backtest Workflow

```python
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.common.costs import TransactionCostModel
import pandas as pd

# 1. Prepare OHLCV data
data = {
    '005930': pd.read_csv('005930_ohlcv.csv', index_col=0, parse_dates=True),
    '000660': pd.read_csv('000660_ohlcv.csv', index_col=0, parse_dates=True)
}

# 2. Generate strategy signals (momentum example)
signals = {}
for ticker, df in data.items():
    ma20 = df['close'].rolling(20).mean()
    signals[ticker] = df['close'] > ma20

# 3. Initialize engine
engine = BacktestEngine(
    initial_capital=100_000_000,
    cost_model=TransactionCostModel(broker='KIS', slippage_bps=5.0),
    size_type='equal_weight',
    target_positions=2
)

# 4. Run backtest
results = engine.run(
    data=data,
    signals=signals,
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# 5. Analyze results
print(f"Total Return: {results['metrics']['total_return_pct']:.2%}")
print(f"Sharpe Ratio: {results['metrics']['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {results['metrics']['max_drawdown']:.2%}")
print(f"Total Trades: {results['trade_stats']['total_trades']}")
print(f"Win Rate: {results['trade_stats']['win_rate']:.2%}")

# 6. Export trade log
trades_df = results['trades']
trades_df.to_csv('backtest_trades.csv', index=False)

# 7. Plot equity curve
equity_curve = results['equity_curve']
equity_curve['portfolio_value'].plot(title='Portfolio Equity Curve')
```

### Comparison with VectorBT

```python
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.vectorbt.adapter import VectorBTAdapter

# Run VectorBT (research - fast)
vbt = VectorBTAdapter(initial_capital=100_000_000)
vbt_portfolio = vbt.run_portfolio_backtest(data, signals)
vbt_metrics = vbt.calculate_metrics(vbt_portfolio)

# Run Custom Engine (production - detailed)
custom = BacktestEngine(initial_capital=100_000_000)
custom_results = custom.run(data, signals)

# Compare results
print("VectorBT (Research):")
print(f"  Total Return: {vbt_metrics['total_return']:.2%}")
print(f"  Sharpe Ratio: {vbt_metrics['sharpe_ratio']:.2f}")
print(f"  Execution Time: <1s")

print("\nCustom Engine (Production):")
print(f"  Total Return: {custom_results['metrics']['total_return_pct']:.2%}")
print(f"  Sharpe Ratio: {custom_results['metrics']['sharpe_ratio']:.2f}")
print(f"  Total Trades: {custom_results['trade_stats']['total_trades']}")
print(f"  Execution Time: {custom_results['execution_time']:.2f}s")

# Access detailed trade log (Custom Engine only)
trades = custom_results['trades']
print(f"\nTrade Log: {len(trades)} trades with full entry/exit details")
```

### Custom Position Sizing

```python
# Equal weight (default)
engine = BacktestEngine(
    initial_capital=100_000_000,
    size_type='equal_weight',
    target_positions=3  # 33.3% per position
)

# Percentage allocation
engine = BacktestEngine(
    initial_capital=100_000_000,
    size_type='percent'
    # Requires signals with position size values
)

# Fixed share count
engine = BacktestEngine(
    initial_capital=100_000_000,
    size_type='shares'
    # Requires signals with share quantities
)
```

---

## Performance Characteristics

### Benchmarks

| Scenario | Execution Time | Memory Usage | Trade Count |
|----------|---------------|--------------|-------------|
| 2-year, 10 tickers | 0.03s | <100MB | ~20 trades |
| 5-year, 10 tickers | <30s ✅ | <500MB | ~60 trades |
| 5-year, 100 tickers | ~5 min | ~2GB | ~600 trades |

### Optimization Tips

1. **Date Filtering**: Use `start_date` and `end_date` to limit backtest period
2. **Ticker Selection**: Limit universe size for faster execution
3. **Signal Frequency**: Reduce rebalancing frequency (monthly vs daily)
4. **Parallel Backtests**: Run multiple backtests in parallel for parameter sweeps

---

## Integration Guide

### With VectorBT

```python
# Research workflow: VectorBT → Custom Engine
# 1. Use VectorBT for parameter optimization (fast)
# 2. Validate top strategies with Custom Engine (detailed)

from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.custom.backtest_engine import BacktestEngine

# Step 1: Screen parameters with VectorBT
vbt = VectorBTAdapter()
best_params = vbt.optimize_parameters(data, param_grid)

# Step 2: Validate with Custom Engine
engine = BacktestEngine(initial_capital=100_000_000)
for params in best_params[:5]:  # Top 5 strategies
    signals = generate_signals(data, params)
    results = engine.run(data, signals)
    print(f"Params: {params}, Sharpe: {results['metrics']['sharpe_ratio']:.2f}")
```

### With OrderExecutionEngine

```python
# Custom Engine uses OrderExecutionEngine internally
from modules.backtest.custom.backtest_engine import BacktestEngine
from modules.backtest.common.costs import TransactionCostModel

# Transaction cost model is passed to OrderExecutionEngine
engine = BacktestEngine(
    initial_capital=100_000_000,
    cost_model=TransactionCostModel(
        broker='KIS',
        commission_rate=0.00015,  # 0.015%
        tax_rate=0.0023,          # 0.23% (sell only)
        slippage_bps=5.0          # 5 bps
    )
)
```

### With PerformanceMetrics

```python
# Custom Engine uses PerformanceMetrics for calculations
from modules.backtest.custom.backtest_engine import BacktestEngine

results = engine.run(data, signals)

# Metrics are auto-calculated and included in results
metrics = results['metrics']
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}")
print(f"Calmar Ratio: {metrics['calmar_ratio']:.2f}")
print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
```

---

## API Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-19 | Initial release (Week 2 completion) |
|  |  | - BacktestEngine, PositionTracker, SignalInterpreter, TradeLogger |
|  |  | - Performance target met (<30s for 5-year) |
|  |  | - 18/18 tests passing |

---

## See Also

- [Week 2 Completion Report](WEEK2_COMPLETION_REPORT.md) - Detailed implementation summary
- [Backtesting Engine User Guide](BACKTEST_ENGINE_USER_GUIDE.md) - Step-by-step tutorial
- [QUANT_BACKTESTING_ENGINES.md](QUANT_BACKTESTING_ENGINES.md) - Engine comparison
- [Test Suite](../tests/backtest/test_custom_engine.py) - Comprehensive test examples
- [Demo Script](../examples/backtest/custom_engine_demo.py) - End-to-end workflow

---

**Last Updated**: 2025-10-27
**Version**: 1.0.0
**Status**: ✅ Production-ready
**Maintainer**: Quant Platform Team
