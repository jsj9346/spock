# Spock Backtesting Module Design

**Purpose**: Enable power users to validate trading strategies with historical data before live deployment

**Design Date**: 2025-10-17
**Status**: Design Phase
**Target Users**: Heavy users and power users seeking strategy validation

---

## Table of Contents
1. [Design Overview](#design-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Database Schema](#database-schema)
5. [Performance Metrics](#performance-metrics)
6. [Parameter Optimization](#parameter-optimization)
7. [Multi-Region Support](#multi-region-support)
8. [User Interface](#user-interface)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Integration Points](#integration-points)

---

## Design Overview

### Goals
- **Validate Strategies**: Test LayeredScoringEngine + Kelly Formula with historical data
- **Avoid Pitfalls**: Prevent look-ahead bias, survivorship bias, unrealistic execution
- **Optimize Parameters**: Grid/random search, walk-forward analysis, Monte Carlo simulation
- **Multi-Region**: Support all 6 markets (KR, US, CN, HK, JP, VN)
- **Realistic Modeling**: Transaction costs, slippage, tick size compliance, market hours

### Design Philosophy
- **Event-Driven**: Process data chronologically to avoid look-ahead bias
- **Reuse Existing Code**: 80%+ reuse from Spock core modules
- **Fast Iteration**: In-memory data structures for rapid parameter testing
- **Extensible**: Plugin architecture for custom strategies
- **Evidence-Based**: Comprehensive metrics aligned with spock_PRD.md success criteria

### Success Criteria Alignment
From `spock_PRD.md`:
- ✅ Total Return: ≥15% annually (backtested validation)
- ✅ Sharpe Ratio: ≥1.5 (risk-adjusted performance)
- ✅ Max Drawdown: ≤15% (risk management validation)
- ✅ Win Rate: ≥55% (strategy effectiveness)

---

## Architecture

### High-Level Flow
```
User Input (CLI/Config)
    ↓
BacktestEngine (Orchestrator)
    ↓
HistoricalDataProvider → SQLite DB (250-day OHLCV)
    ↓
Event-Driven Loop (Day-by-Day)
    ├→ StrategyRunner → LayeredScoringEngine (100-point scoring)
    ├→ PortfolioSimulator → Kelly Calculator (position sizing)
    ├→ TransactionCostModel → Commission + Slippage
    └→ Trade Execution (simulated)
    ↓
PerformanceAnalyzer → Metrics Calculation
    ↓
BacktestReporter → Console/JSON/HTML/CSV
```

### Key Architectural Decisions

#### 1. Event-Driven Backtesting
- **Why**: Prevents look-ahead bias by processing data chronologically
- **How**: Iterator pattern over sorted dates, point-in-time data snapshots
- **Trade-off**: Slightly slower than vectorized backtesting, but more realistic

#### 2. In-Memory Data Loading
- **Why**: Fast parameter iteration (grid search requires 100+ runs)
- **How**: Load 250-day OHLCV + technical indicators into pandas DataFrames
- **Trade-off**: Memory usage ~500MB-1GB for 3,000 stocks (acceptable for power users)

#### 3. Strategy Reuse
- **Why**: Validate production code, not separate backtest logic
- **How**: Import LayeredScoringEngine, KellyCalculator directly
- **Trade-off**: None - this is pure advantage

#### 4. Pluggable Transaction Cost Model
- **Why**: Different users have different broker fee structures
- **How**: Abstract base class with default KIS API rates
- **Trade-off**: Slight complexity increase, major flexibility gain

---

## Core Components

### 1. BacktestEngine (`backtest_engine.py`)

**Purpose**: Main orchestrator coordinating all backtesting components

**Responsibilities**:
- Initialize data provider, portfolio simulator, strategy runner
- Execute event-driven loop (day-by-day iteration)
- Coordinate multi-region backtests
- Handle start/end date boundaries
- Manage backtest configuration

**Key Methods**:
```python
class BacktestEngine:
    def __init__(self, config: BacktestConfig, db: SQLiteDatabaseManager):
        """Initialize backtest engine with configuration and database"""

    def run(self) -> BacktestResult:
        """Execute backtest and return results"""

    def run_optimization(self, param_grid: dict) -> List[BacktestResult]:
        """Run parameter optimization across grid"""

    def compare_strategies(self, configs: List[BacktestConfig]) -> ComparisonReport:
        """Compare multiple strategy configurations"""
```

**Configuration Structure**:
```python
@dataclass
class BacktestConfig:
    # Time period
    start_date: date
    end_date: date

    # Region and tickers
    regions: List[str]  # ['KR', 'US', 'CN', 'HK', 'JP', 'VN']
    tickers: Optional[List[str]]  # None = all tickers

    # Strategy parameters
    score_threshold: int = 70  # LayeredScoringEngine threshold
    risk_profile: str = 'moderate'  # conservative, moderate, aggressive

    # Position sizing
    kelly_multiplier: float = 0.5  # Half Kelly (conservative)
    max_position_size: float = 0.15  # 15% max per stock
    max_sector_exposure: float = 0.40  # 40% max per sector
    cash_reserve: float = 0.20  # 20% min cash

    # Risk management
    stop_loss_atr_multiplier: float = 1.0  # 1.0 × ATR
    stop_loss_min: float = 0.05  # 5% min stop loss
    stop_loss_max: float = 0.15  # 15% max stop loss
    profit_target: float = 0.20  # 20% profit taking

    # Transaction costs
    commission_rate: float = 0.00015  # 0.015% (KIS default)
    slippage_bps: float = 5.0  # 5 basis points

    # Initial capital
    initial_capital: float = 100_000_000  # 100M KRW
```

### 2. HistoricalDataProvider (`historical_data_provider.py`)

**Purpose**: Efficient access to historical OHLCV data with caching

**Responsibilities**:
- Load OHLCV data from SQLite database
- Cache data in memory for fast iteration
- Provide point-in-time data snapshots (no look-ahead)
- Handle missing data gracefully
- Support multi-region queries

**Key Methods**:
```python
class HistoricalDataProvider:
    def __init__(self, db: SQLiteDatabaseManager):
        """Initialize data provider with database connection"""

    def load_data(self, tickers: List[str], start_date: date, end_date: date,
                  regions: List[str]) -> Dict[str, pd.DataFrame]:
        """Load OHLCV + technical indicators for tickers"""

    def get_snapshot(self, ticker: str, as_of_date: date) -> Optional[pd.Series]:
        """Get point-in-time data for ticker (no future data)"""

    def get_universe(self, as_of_date: date, regions: List[str]) -> List[str]:
        """Get available tickers as of date (handles delistings)"""
```

**Caching Strategy**:
- Load all data at backtest start (one-time cost)
- Index by (ticker, date) for O(1) lookup
- Memory usage: ~500MB for 3,000 stocks × 250 days

### 3. PortfolioSimulator (`portfolio_simulator.py`)

**Purpose**: Track positions, cash, and P&L throughout backtest

**Responsibilities**:
- Maintain current positions and cash balance
- Execute simulated trades (buy/sell)
- Calculate P&L (realized and unrealized)
- Enforce position limits (max position size, sector exposure)
- Track transaction costs
- Generate trade log

**Key Methods**:
```python
class PortfolioSimulator:
    def __init__(self, initial_capital: float, config: BacktestConfig):
        """Initialize portfolio with starting capital"""

    def buy(self, ticker: str, price: float, date: date,
            kelly_fraction: float, pattern_type: str) -> Optional[Trade]:
        """Execute buy order with position sizing"""

    def sell(self, ticker: str, price: float, date: date,
             reason: str) -> Optional[Trade]:
        """Execute sell order and realize P&L"""

    def update_positions(self, date: date, current_prices: Dict[str, float]):
        """Update unrealized P&L and check exit conditions"""

    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value (cash + positions)"""

    def get_current_positions(self) -> List[Position]:
        """Get list of open positions"""
```

**Position Tracking**:
```python
@dataclass
class Position:
    ticker: str
    region: str
    entry_date: date
    entry_price: float
    shares: int
    stop_loss_price: float
    profit_target_price: float
    pattern_type: str  # 'Stage2', 'VCP', 'CupHandle', etc.
    entry_score: int  # LayeredScoringEngine score at entry
```

**Trade Log**:
```python
@dataclass
class Trade:
    ticker: str
    region: str
    entry_date: date
    exit_date: Optional[date]
    entry_price: float
    exit_price: Optional[float]
    shares: int
    commission: float
    slippage: float
    pnl: Optional[float]  # Realized P&L
    pnl_pct: Optional[float]  # Return %
    pattern_type: str
    exit_reason: str  # 'profit_target', 'stop_loss', 'stage3_exit', 'manual'
```

### 4. StrategyRunner (`strategy_runner.py`)

**Purpose**: Execute LayeredScoringEngine and generate buy/sell signals

**Responsibilities**:
- Run LayeredScoringEngine on all candidates
- Filter stocks by score threshold
- Generate buy signals for top-ranked stocks
- Monitor open positions for exit signals (Stage 3, stop loss, profit target)
- Integrate with Kelly Calculator for position sizing

**Key Methods**:
```python
class StrategyRunner:
    def __init__(self, config: BacktestConfig,
                 scoring_engine: LayeredScoringEngine,
                 kelly_calc: KellyCalculator):
        """Initialize strategy runner with scoring and position sizing"""

    def scan_candidates(self, date: date, universe: List[str],
                        data_provider: HistoricalDataProvider) -> List[ScoredStock]:
        """Score all stocks and return ranked candidates"""

    def generate_buy_signals(self, candidates: List[ScoredStock],
                             portfolio: PortfolioSimulator) -> List[BuySignal]:
        """Generate buy signals for top-ranked stocks within limits"""

    def check_exit_signals(self, positions: List[Position], date: date,
                           data_provider: HistoricalDataProvider) -> List[SellSignal]:
        """Check exit conditions for open positions"""
```

**Integration with Existing Modules**:
- ✅ Reuse `LayeredScoringEngine` from `modules/layered_scoring_engine.py`
- ✅ Reuse `KellyCalculator` from `modules/kelly_calculator.py`
- ✅ Reuse pattern detection logic from `modules/stock_gpt_analyzer.py` (if enabled)

### 5. PerformanceAnalyzer (`performance_analyzer.py`)

**Purpose**: Calculate comprehensive performance metrics

**Responsibilities**:
- Calculate return metrics (total, annualized, CAGR)
- Calculate risk metrics (Sharpe, Sortino, Calmar, max drawdown)
- Calculate trading metrics (win rate, profit factor, avg hold time)
- Generate equity curve and drawdown series
- Compare against benchmark (KOSPI for KR, S&P500 for US, etc.)

**Key Methods**:
```python
class PerformanceAnalyzer:
    def __init__(self, trades: List[Trade], portfolio_values: pd.Series,
                 benchmark_returns: Optional[pd.Series] = None):
        """Initialize analyzer with trade log and portfolio history"""

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate all performance metrics"""

    def calculate_pattern_metrics(self) -> Dict[str, PatternMetrics]:
        """Calculate metrics by pattern type (Stage2, VCP, etc.)"""

    def calculate_region_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Calculate metrics by region (KR, US, CN, etc.)"""
```

**Metrics Structure**:
```python
@dataclass
class PerformanceMetrics:
    # Return metrics
    total_return: float
    annualized_return: float
    cagr: float

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: int
    std_returns: float
    downside_deviation: float

    # Trading metrics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    avg_win_loss_ratio: float
    avg_holding_period_days: float

    # Kelly validation
    kelly_accuracy: float  # Actual win rate vs predicted

    # Benchmark comparison (optional)
    alpha: Optional[float]
    beta: Optional[float]
    information_ratio: Optional[float]
```

### 6. ParameterOptimizer (`parameter_optimizer.py`)

**Purpose**: Automated parameter tuning for strategy optimization

**Responsibilities**:
- Grid search over parameter space
- Random search for high-dimensional spaces
- Walk-forward analysis (in-sample → out-of-sample)
- Monte Carlo simulation for robustness testing
- Parallel execution for faster optimization

**Key Methods**:
```python
class ParameterOptimizer:
    def __init__(self, base_config: BacktestConfig, db: SQLiteDatabaseManager):
        """Initialize optimizer with base configuration"""

    def grid_search(self, param_grid: Dict[str, List],
                    metric: str = 'sharpe_ratio') -> OptimizationResult:
        """Systematic parameter grid search"""

    def random_search(self, param_ranges: Dict[str, tuple],
                      n_iterations: int = 100) -> OptimizationResult:
        """Random sampling from parameter space"""

    def walk_forward_analysis(self, train_months: int = 12,
                              test_months: int = 3) -> WalkForwardResult:
        """Rolling window train/test validation"""

    def monte_carlo_simulation(self, n_simulations: int = 1000) -> MonteCarloResult:
        """Randomize trade sequence to test robustness"""
```

**Grid Search Example**:
```python
param_grid = {
    'score_threshold': [60, 65, 70, 75, 80],
    'kelly_multiplier': [0.25, 0.5, 0.75, 1.0],
    'stop_loss_atr_multiplier': [0.75, 1.0, 1.25, 1.5],
    'profit_target': [0.15, 0.20, 0.25, 0.30]
}
# Total combinations: 5 × 4 × 4 × 4 = 320 backtests
```

### 7. TransactionCostModel (`transaction_cost_model.py`)

**Purpose**: Realistic modeling of trading costs

**Responsibilities**:
- Calculate commission (region-specific rates)
- Model slippage (volume-based)
- Apply tick size constraints
- Support custom fee structures

**Key Methods**:
```python
class TransactionCostModel:
    def __init__(self, config: BacktestConfig):
        """Initialize cost model with configuration"""

    def calculate_commission(self, price: float, shares: int,
                             region: str) -> float:
        """Calculate broker commission"""

    def calculate_slippage(self, price: float, shares: int,
                           volume: int, side: str) -> float:
        """Model slippage based on market impact"""

    def apply_tick_size(self, price: float, region: str) -> float:
        """Round price to valid tick size"""
```

**Default Commission Rates**:
```python
DEFAULT_COMMISSION_RATES = {
    'KR': 0.00015,  # 0.015% (KIS API)
    'US': 0.0,      # Zero commission (most US brokers)
    'CN': 0.0003,   # 0.03%
    'HK': 0.0003,   # 0.03%
    'JP': 0.0003,   # 0.03%
    'VN': 0.0015,   # 0.15%
}
```

**Slippage Model**:
```python
# Market impact formula (simplified Almgren-Chriss)
slippage_bps = base_slippage_bps × (order_size / avg_daily_volume) ** 0.5
slippage_amount = price × shares × (slippage_bps / 10000)
```

### 8. BacktestReporter (`backtest_reporter.py`)

**Purpose**: Generate comprehensive backtest reports in multiple formats

**Responsibilities**:
- Console summary (quick feedback)
- JSON export (machine-readable)
- CSV trade log (Excel compatibility)
- HTML report with charts (professional presentation)
- Database persistence (historical tracking)

**Key Methods**:
```python
class BacktestReporter:
    def __init__(self, result: BacktestResult):
        """Initialize reporter with backtest result"""

    def print_console_summary(self):
        """Print formatted summary to console"""

    def export_json(self, filepath: str):
        """Export full results to JSON"""

    def export_csv_trades(self, filepath: str):
        """Export trade log to CSV"""

    def generate_html_report(self, filepath: str):
        """Generate HTML report with charts"""

    def save_to_database(self, db: SQLiteDatabaseManager):
        """Persist results to backtest_results table"""
```

**Report Sections**:
1. Executive Summary (key metrics)
2. Equity Curve (cumulative returns chart)
3. Drawdown Analysis (underwater chart)
4. Trade Analysis (win rate by pattern, sector, region)
5. Risk Metrics (Sharpe, Sortino, Calmar)
6. Monthly Returns Heatmap
7. Top Winners/Losers
8. Parameter Sensitivity (if optimization run)

---

## Database Schema

### New Tables

#### 1. `backtest_results` Table
```sql
CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_hash TEXT NOT NULL,              -- SHA256 of config for deduplication
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    regions TEXT NOT NULL,                  -- JSON array: ["KR", "US"]

    -- Strategy parameters (JSON)
    config_json TEXT NOT NULL,

    -- Performance metrics
    total_return REAL,
    annualized_return REAL,
    cagr REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    calmar_ratio REAL,
    max_drawdown REAL,

    -- Trading metrics
    total_trades INTEGER,
    win_rate REAL,
    profit_factor REAL,
    avg_win_loss_ratio REAL,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_seconds REAL,

    UNIQUE(config_hash, start_date, end_date)
);

CREATE INDEX idx_backtest_results_created ON backtest_results(created_at);
CREATE INDEX idx_backtest_results_sharpe ON backtest_results(sharpe_ratio);
```

#### 2. `backtest_trades` Table
```sql
CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,

    -- Trade details
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    exit_date TEXT,
    entry_price REAL NOT NULL,
    exit_price REAL,
    shares INTEGER NOT NULL,

    -- Costs
    commission REAL NOT NULL,
    slippage REAL NOT NULL,

    -- P&L
    pnl REAL,
    pnl_pct REAL,

    -- Strategy context
    pattern_type TEXT,                      -- 'Stage2', 'VCP', etc.
    entry_score INTEGER,                    -- LayeredScoringEngine score
    exit_reason TEXT,                       -- 'profit_target', 'stop_loss', etc.

    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id) ON DELETE CASCADE
);

CREATE INDEX idx_backtest_trades_backtest ON backtest_trades(backtest_id);
CREATE INDEX idx_backtest_trades_ticker ON backtest_trades(ticker);
CREATE INDEX idx_backtest_trades_pattern ON backtest_trades(pattern_type);
```

#### 3. `backtest_equity_curve` Table
```sql
CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    portfolio_value REAL NOT NULL,
    cash REAL NOT NULL,
    positions_value REAL NOT NULL,
    daily_return REAL,

    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id) ON DELETE CASCADE
);

CREATE INDEX idx_backtest_equity_backtest ON backtest_equity_curve(backtest_id);
```

### Database Migration Script
```python
# modules/db_manager_sqlite.py (add method)
def create_backtest_tables(self):
    """Create backtesting tables if they don't exist"""
    conn = self._get_connection()
    cursor = conn.cursor()

    # backtest_results table
    cursor.execute("""...""")

    # backtest_trades table
    cursor.execute("""...""")

    # backtest_equity_curve table
    cursor.execute("""...""")

    conn.commit()
    conn.close()
```

---

## Performance Metrics

### Return Metrics

#### 1. Total Return
```python
total_return = (final_portfolio_value - initial_capital) / initial_capital
```

#### 2. Annualized Return
```python
years = (end_date - start_date).days / 365.25
annualized_return = (1 + total_return) ** (1 / years) - 1
```

#### 3. CAGR (Compound Annual Growth Rate)
```python
cagr = (final_portfolio_value / initial_capital) ** (1 / years) - 1
```

### Risk Metrics

#### 4. Sharpe Ratio (Risk-Adjusted Return)
```python
sharpe_ratio = (annualized_return - risk_free_rate) / std_annualized_returns
# Target: ≥1.5 (from spock_PRD.md)
```

#### 5. Sortino Ratio (Downside Risk)
```python
sortino_ratio = (annualized_return - risk_free_rate) / downside_deviation
# Only penalizes downside volatility
```

#### 6. Calmar Ratio (Return vs Max Drawdown)
```python
calmar_ratio = cagr / abs(max_drawdown)
# Higher is better (reward/risk)
```

#### 7. Maximum Drawdown
```python
# Peak-to-trough decline
cumulative_returns = (1 + daily_returns).cumprod()
running_max = cumulative_returns.cummax()
drawdown = (cumulative_returns - running_max) / running_max
max_drawdown = drawdown.min()
# Target: ≤15% (from spock_PRD.md)
```

#### 8. Value at Risk (VaR)
```python
# 95% VaR: Maximum expected loss in 5% of worst cases
var_95 = daily_returns.quantile(0.05)
```

### Trading Metrics

#### 9. Win Rate
```python
win_rate = winning_trades / total_trades
# Target: ≥55% (from spock_PRD.md)
```

#### 10. Profit Factor
```python
profit_factor = total_gross_profit / total_gross_loss
# >1.0 = profitable, >2.0 = excellent
```

#### 11. Average Win/Loss Ratio
```python
avg_win_loss_ratio = avg_winning_trade / abs(avg_losing_trade)
```

#### 12. Recovery Factor
```python
recovery_factor = net_profit / abs(max_drawdown_amount)
```

### Pattern-Specific Metrics

#### 13. Win Rate by Pattern Type
```python
pattern_metrics = {
    'Stage2': {'win_rate': 0.65, 'avg_return': 0.18, 'trades': 45},
    'VCP': {'win_rate': 0.62, 'avg_return': 0.21, 'trades': 32},
    'CupHandle': {'win_rate': 0.58, 'avg_return': 0.16, 'trades': 28},
    'TriangleBreakout': {'win_rate': 0.55, 'avg_return': 0.14, 'trades': 22}
}
```

#### 14. Kelly Accuracy
```python
# Compare actual win rate vs Kelly Calculator prediction
kelly_accuracy = 1 - abs(actual_win_rate - predicted_win_rate) / predicted_win_rate
```

---

## Parameter Optimization

### 1. Grid Search

**Purpose**: Systematic exploration of parameter space

**Example Usage**:
```python
from modules.backtesting import ParameterOptimizer

optimizer = ParameterOptimizer(base_config, db)

param_grid = {
    'score_threshold': [60, 65, 70, 75, 80],
    'kelly_multiplier': [0.25, 0.5, 0.75, 1.0],
    'stop_loss_atr_multiplier': [0.75, 1.0, 1.25, 1.5],
    'profit_target': [0.15, 0.20, 0.25, 0.30]
}

results = optimizer.grid_search(
    param_grid=param_grid,
    metric='sharpe_ratio',  # Optimize for Sharpe ratio
    parallel=True,  # Use multiprocessing
    n_jobs=4
)

best_config = results.best_config
print(f"Best Sharpe Ratio: {results.best_score:.2f}")
print(f"Optimal Parameters: {best_config}")
```

**Output**:
```
Grid Search Results:
  Total Combinations: 320
  Completed: 320/320 (100%)
  Best Sharpe Ratio: 1.82

Optimal Parameters:
  score_threshold: 70
  kelly_multiplier: 0.5
  stop_loss_atr_multiplier: 1.0
  profit_target: 0.20

Parameter Sensitivity:
  score_threshold: High impact (±0.3 Sharpe per 5-point change)
  kelly_multiplier: Medium impact (±0.15 Sharpe per 0.25 change)
  stop_loss_atr_multiplier: Low impact (±0.08 Sharpe)
  profit_target: Medium impact (±0.12 Sharpe)
```

### 2. Walk-Forward Analysis

**Purpose**: Validate strategy robustness with out-of-sample testing

**Methodology**:
```
Train Period 1 (12 months) → Test Period 1 (3 months)
  Train Period 2 (12 months) → Test Period 2 (3 months)
    Train Period 3 (12 months) → Test Period 3 (3 months)
      ...
```

**Example Usage**:
```python
wf_result = optimizer.walk_forward_analysis(
    train_months=12,
    test_months=3,
    param_grid=param_grid,
    metric='sharpe_ratio'
)

print(f"Average Out-of-Sample Sharpe: {wf_result.avg_oos_sharpe:.2f}")
print(f"In-Sample Sharpe: {wf_result.avg_is_sharpe:.2f}")
print(f"Efficiency: {wf_result.efficiency:.1%}")  # OOS / IS performance
```

**Interpretation**:
- **Efficiency > 80%**: Robust strategy (out-of-sample close to in-sample)
- **Efficiency 50-80%**: Moderate overfitting
- **Efficiency < 50%**: Significant overfitting (parameters too fitted to training data)

### 3. Monte Carlo Simulation

**Purpose**: Test robustness by randomizing trade sequence

**Methodology**:
1. Run base backtest to get trade list
2. Randomly shuffle trade order 1,000 times
3. Recalculate P&L for each permutation
4. Analyze distribution of outcomes

**Example Usage**:
```python
mc_result = optimizer.monte_carlo_simulation(
    n_simulations=1000,
    base_trades=backtest_result.trades
)

print(f"95% Confidence Interval:")
print(f"  Total Return: {mc_result.ci_95_return_low:.1%} to {mc_result.ci_95_return_high:.1%}")
print(f"  Max Drawdown: {mc_result.ci_95_dd_low:.1%} to {mc_result.ci_95_dd_high:.1%}")
print(f"Risk of Ruin: {mc_result.risk_of_ruin:.2%}")  # Probability of >50% drawdown
```

---

## Multi-Region Support

### Region-Specific Configuration

#### 1. Market Hours Enforcement
```python
MARKET_HOURS = {
    'KR': {'open': time(9, 0), 'close': time(15, 30), 'lunch_break': None},
    'US': {'open': time(9, 30), 'close': time(16, 0), 'lunch_break': None},
    'HK': {'open': time(9, 30), 'close': time(16, 0), 'lunch_break': (time(12, 0), time(13, 0))},
    'CN': {'open': time(9, 30), 'close': time(15, 0), 'lunch_break': (time(11, 30), time(13, 0))},
    'JP': {'open': time(9, 0), 'close': time(15, 0), 'lunch_break': (time(11, 30), time(12, 30))},
    'VN': {'open': time(9, 0), 'close': time(15, 0), 'lunch_break': (time(11, 30), time(13, 0))}
}
```

#### 2. Holiday Calendars
```python
# Load from existing YAML configs
from modules.stock_utils import load_market_holidays

holidays = {
    'KR': load_market_holidays('config/market_schedule.json', 'KR'),
    'US': load_market_holidays('config/market_schedule.json', 'US'),
    'CN': load_market_holidays('config/cn_holidays.yaml'),
    'HK': load_market_holidays('config/hk_holidays.yaml'),
    'JP': load_market_holidays('config/jp_holidays.yaml'),
    'VN': load_market_holidays('config/vn_holidays.yaml')
}
```

#### 3. Transaction Costs by Region
```python
TRANSACTION_COSTS = {
    'KR': {'commission': 0.00015, 'slippage_bps': 5},
    'US': {'commission': 0.0, 'slippage_bps': 3},
    'CN': {'commission': 0.0003, 'slippage_bps': 8},
    'HK': {'commission': 0.0003, 'slippage_bps': 6},
    'JP': {'commission': 0.0003, 'slippage_bps': 5},
    'VN': {'commission': 0.0015, 'slippage_bps': 10}
}
```

### Multi-Region Backtesting

#### Example 1: Single Region (Korea)
```python
config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    regions=['KR'],
    initial_capital=100_000_000  # 100M KRW
)

engine = BacktestEngine(config, db)
result = engine.run()
```

#### Example 2: Multi-Region Portfolio
```python
config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    regions=['KR', 'US', 'JP'],  # Multi-region
    initial_capital=100_000_000,
    max_region_exposure={'KR': 0.5, 'US': 0.3, 'JP': 0.2}  # Region allocation
)

engine = BacktestEngine(config, db)
result = engine.run()

# Performance by region
for region, metrics in result.region_metrics.items():
    print(f"{region}: Return={metrics.total_return:.1%}, Sharpe={metrics.sharpe_ratio:.2f}")
```

#### Example 3: Region Comparison
```python
regions_to_test = ['KR', 'US', 'CN', 'HK', 'JP', 'VN']
results = []

for region in regions_to_test:
    config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        regions=[region],
        initial_capital=100_000_000
    )
    result = engine.run()
    results.append((region, result))

# Compare performance
comparison = pd.DataFrame([
    {
        'Region': region,
        'Return': result.metrics.total_return,
        'Sharpe': result.metrics.sharpe_ratio,
        'MaxDD': result.metrics.max_drawdown,
        'WinRate': result.metrics.win_rate
    }
    for region, result in results
])

print(comparison.sort_values('Sharpe', ascending=False))
```

---

## User Interface

### CLI Interface

#### Basic Backtest
```bash
# Single region backtest
python3 spock.py --backtest \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --region KR

# Multi-region backtest
python3 spock.py --backtest \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --regions KR,US,JP

# Specific tickers
python3 spock.py --backtest \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --tickers 005930,000660,035420
```

#### Parameter Optimization
```bash
# Grid search
python3 spock.py --backtest --optimize \
  --param-range score_threshold:60-80:5 \
  --param-range kelly_multiplier:0.25-1.0:0.25 \
  --metric sharpe_ratio

# Walk-forward analysis
python3 spock.py --backtest --walk-forward \
  --train-months 12 \
  --test-months 3 \
  --param-range score_threshold:60-80:5

# Monte Carlo simulation
python3 spock.py --backtest --monte-carlo \
  --simulations 1000 \
  --start-date 2023-01-01 \
  --end-date 2024-12-31
```

#### Report Generation
```bash
# Console summary only
python3 spock.py --backtest --report console

# Full HTML report
python3 spock.py --backtest --report html --output reports/backtest_20241017.html

# Export trade log
python3 spock.py --backtest --export-trades trades.csv

# Export to JSON
python3 spock.py --backtest --export-json result.json
```

### Configuration File

**`config/backtest_default.yaml`**:
```yaml
# Default backtest configuration
backtest:
  # Time period
  start_date: "2023-01-01"
  end_date: "2024-12-31"

  # Region and tickers
  regions: ["KR"]
  tickers: null  # null = all tickers

  # Strategy parameters
  score_threshold: 70
  risk_profile: "moderate"  # conservative, moderate, aggressive

  # Position sizing
  kelly_multiplier: 0.5
  max_position_size: 0.15
  max_sector_exposure: 0.40
  cash_reserve: 0.20

  # Risk management
  stop_loss_atr_multiplier: 1.0
  stop_loss_min: 0.05
  stop_loss_max: 0.15
  profit_target: 0.20

  # Transaction costs
  commission_rate: 0.00015  # 0.015% (KIS default)
  slippage_bps: 5.0

  # Initial capital
  initial_capital: 100000000  # 100M KRW

  # Output
  output_format: ["console", "html"]
  output_dir: "reports/backtests"
```

**Usage**:
```bash
# Use config file
python3 spock.py --backtest --config config/backtest_default.yaml

# Override config values
python3 spock.py --backtest \
  --config config/backtest_default.yaml \
  --score-threshold 75 \
  --kelly-multiplier 0.75
```

### Console Output Example

```
================================================================================
Spock Backtest Report
================================================================================

Configuration:
  Period: 2023-01-01 to 2024-12-31 (730 days)
  Regions: KR
  Initial Capital: ₩100,000,000
  Risk Profile: Moderate

Strategy Parameters:
  Score Threshold: 70
  Kelly Multiplier: 0.5 (Half Kelly)
  Stop Loss: 1.0 × ATR (5-15% range)
  Profit Target: 20%

================================================================================
Performance Summary
================================================================================

Return Metrics:
  Total Return:           +18.5%
  Annualized Return:      +17.2%
  CAGR:                   +17.2%

Risk Metrics:
  Sharpe Ratio:           1.68   ✅ (Target: ≥1.5)
  Sortino Ratio:          2.34
  Calmar Ratio:           1.41
  Max Drawdown:          -12.3%  ✅ (Target: ≤15%)
  Std Dev (Annual):       10.2%

Trading Metrics:
  Total Trades:           87
  Win Rate:               58.6%  ✅ (Target: ≥55%)
  Profit Factor:          2.12
  Avg Win:               +14.8%
  Avg Loss:               -7.2%
  Win/Loss Ratio:         2.06
  Avg Hold Time:          32 days

Kelly Validation:
  Predicted Win Rate:     62% (Stage2), 58% (VCP)
  Actual Win Rate:        58.6%
  Kelly Accuracy:         94.5%  ✅

================================================================================
Performance by Pattern Type
================================================================================

Pattern          Trades  Win Rate  Avg Return  Total P&L
─────────────────────────────────────────────────────────
Stage2 Breakout     42    61.9%     +15.2%     ₩8,420,000
VCP Pattern         28    57.1%     +16.8%     ₩6,230,000
Cup & Handle        17    52.9%     +12.4%     ₩2,180,000

================================================================================
Top 10 Winners
================================================================================

Ticker  Entry Date  Exit Date   Hold Days  Return    P&L
─────────────────────────────────────────────────────────
005930  2023-03-15  2023-05-22     68     +28.5%   ₩1,420,000
035420  2023-07-10  2023-09-05     57     +24.3%   ₩   980,000
000660  2023-11-02  2024-01-18     77     +22.1%   ₩   890,000
...

================================================================================
Monthly Returns
================================================================================

       Jan    Feb    Mar    Apr    May    Jun    Jul    Aug    Sep    Oct    Nov    Dec
2023   +2.1%  +3.5%  +4.2%  +1.8%  -0.5%  +2.8%  +1.2%  -2.1%  +3.7%  +2.4%  +1.9%  +3.2%
2024   +2.8%  +1.5%  +3.1%  +2.9%  +1.8%  +2.4%  +3.5%  +1.2%  +2.7%  +3.8%  +2.1%  +1.6%

================================================================================
Benchmark Comparison
================================================================================

Metric              Strategy    KOSPI     Alpha
─────────────────────────────────────────────
Total Return        +18.5%      +8.2%    +10.3%
Sharpe Ratio         1.68       0.85     +0.83
Max Drawdown       -12.3%     -18.5%     +6.2%

Beta: 0.68 (Lower volatility than market)
Information Ratio: 1.24

================================================================================
Equity Curve
================================================================================

[ASCII chart of portfolio value over time]

================================================================================
Report saved to: reports/backtests/backtest_20241017_143052.html
Trade log saved to: reports/backtests/backtest_20241017_143052_trades.csv
================================================================================
```

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
**Goal**: Basic event-driven backtesting engine

- [ ] Create module structure (`modules/backtesting/`)
- [ ] Implement `BacktestConfig` dataclass
- [ ] Implement `HistoricalDataProvider` (data loading + caching)
- [ ] Implement `PortfolioSimulator` (position tracking, P&L)
- [ ] Implement `BacktestEngine` (event-driven loop)
- [ ] Add database schema (backtest_results, backtest_trades tables)
- [ ] Basic unit tests (data loading, position tracking)

**Deliverable**: Run simple backtest with fixed parameters

### Phase 2: Strategy Integration (Week 2)
**Goal**: Connect existing Spock modules

- [ ] Implement `StrategyRunner` (LayeredScoringEngine integration)
- [ ] Integrate `KellyCalculator` for position sizing
- [ ] Implement exit signal detection (Stage 3, stop loss, profit target)
- [ ] Add `TransactionCostModel` (commission, slippage, tick size)
- [ ] Region-specific parameter loading (market hours, holidays)
- [ ] Integration tests with real data

**Deliverable**: Full backtest with realistic execution

### Phase 3: Performance Analysis (Week 3)
**Goal**: Comprehensive metrics calculation

- [ ] Implement `PerformanceAnalyzer` (return, risk, trading metrics)
- [ ] Calculate Sharpe, Sortino, Calmar ratios
- [ ] Maximum drawdown analysis
- [ ] Pattern-specific metrics (win rate by pattern)
- [ ] Region-specific metrics
- [ ] Kelly accuracy validation
- [ ] Unit tests for all metrics

**Deliverable**: Detailed performance report

### Phase 4: Reporting (Week 4)
**Goal**: Multi-format output generation

- [ ] Implement `BacktestReporter` base class
- [ ] Console summary (formatted tables)
- [ ] JSON export (machine-readable)
- [ ] CSV trade log (Excel compatibility)
- [ ] HTML report with charts (matplotlib/mplfinance)
- [ ] Database persistence
- [ ] CLI interface (`spock.py --backtest`)

**Deliverable**: Professional backtest reports

### Phase 5: Parameter Optimization (Week 5-6)
**Goal**: Automated parameter tuning

- [ ] Implement `ParameterOptimizer` base class
- [ ] Grid search (with parallel execution)
- [ ] Random search
- [ ] Walk-forward analysis
- [ ] Monte Carlo simulation
- [ ] Parameter sensitivity analysis
- [ ] Configuration file support (YAML)

**Deliverable**: Optimized strategy parameters

### Phase 6: Multi-Region Support (Week 7)
**Goal**: Global market backtesting

- [ ] Region-specific configuration loading
- [ ] Multi-region portfolio allocation
- [ ] Cross-region performance comparison
- [ ] Currency conversion (optional)
- [ ] Region-specific transaction costs
- [ ] Integration tests for all 6 regions

**Deliverable**: Multi-region backtesting capability

### Phase 7: Documentation & Testing (Week 8)
**Goal**: Production-ready release

- [ ] Comprehensive documentation (this file + user guide)
- [ ] Example scripts (`examples/backtest_demo.py`)
- [ ] Full test coverage (≥80% code coverage)
- [ ] Performance benchmarks (backtest speed)
- [ ] User acceptance testing with power users
- [ ] Integration with monitoring (Prometheus metrics)

**Deliverable**: Production-ready backtesting module

---

## Integration Points

### Reuse from Existing Modules (80%+ Reuse)

#### 1. `modules/layered_scoring_engine.py`
**Usage**: Stock scoring and ranking
**Integration**: `StrategyRunner.scan_candidates()`
```python
from modules.layered_scoring_engine import LayeredScoringEngine

scoring_engine = LayeredScoringEngine(db, config)
scores = scoring_engine.score_stock(ticker, as_of_date)
```

#### 2. `modules/kelly_calculator.py`
**Usage**: Position sizing based on pattern win rates
**Integration**: `PortfolioSimulator.buy()`
```python
from modules.kelly_calculator import KellyCalculator

kelly_calc = KellyCalculator()
kelly_fraction = kelly_calc.calculate_kelly_fraction(
    pattern_type='Stage2',
    win_rate=0.65,
    avg_win_loss_ratio=2.0
)
position_size = kelly_fraction * kelly_multiplier * portfolio_value
```

#### 3. `modules/db_manager_sqlite.py`
**Usage**: Database access for OHLCV data
**Integration**: `HistoricalDataProvider.load_data()`
```python
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()
ohlcv_data = db.get_ohlcv_data(ticker, start_date, end_date, region)
```

#### 4. `modules/integrated_scoring_system.py`
**Usage**: Technical indicator calculations
**Integration**: `HistoricalDataProvider` (pre-calculate indicators)
```python
from modules.integrated_scoring_system import calculate_technical_indicators

indicators = calculate_technical_indicators(ohlcv_df)
```

#### 5. `modules/kis_trading_engine.py`
**Usage**: Tick size compliance rules
**Integration**: `TransactionCostModel.apply_tick_size()`
```python
from modules.kis_trading_engine import get_tick_size

tick_size = get_tick_size(price, region)
adjusted_price = round(price / tick_size) * tick_size
```

#### 6. `modules/stock_utils.py`
**Usage**: Market hours, holiday calendars
**Integration**: `BacktestEngine` (trading day validation)
```python
from modules.stock_utils import is_trading_day, get_market_hours

if is_trading_day(date, region):
    # Process backtest day
```

### New Dependencies

#### Optional: Visualization
```bash
pip install matplotlib mplfinance seaborn
```

**Usage**: HTML report charts (equity curve, drawdown, monthly returns)

#### Optional: Parallel Optimization
```bash
pip install joblib
```

**Usage**: `ParameterOptimizer.grid_search(parallel=True)`

---

## Testing Strategy

### Unit Tests

#### 1. Data Provider Tests
```python
# tests/test_backtest_data_provider.py
def test_load_data():
    """Test OHLCV data loading and caching"""

def test_point_in_time_snapshot():
    """Test no look-ahead bias in data access"""

def test_missing_data_handling():
    """Test graceful handling of missing data"""
```

#### 2. Portfolio Simulator Tests
```python
# tests/test_backtest_portfolio.py
def test_buy_position():
    """Test position creation and tracking"""

def test_sell_position():
    """Test position closing and P&L calculation"""

def test_position_limits():
    """Test max position size and sector exposure limits"""

def test_transaction_costs():
    """Test commission and slippage calculation"""
```

#### 3. Performance Analyzer Tests
```python
# tests/test_backtest_performance.py
def test_sharpe_ratio_calculation():
    """Test Sharpe ratio calculation"""

def test_max_drawdown_calculation():
    """Test maximum drawdown calculation"""

def test_pattern_metrics():
    """Test pattern-specific win rate calculation"""
```

### Integration Tests

#### 4. Full Backtest Tests
```python
# tests/test_backtest_integration.py
def test_simple_backtest():
    """Test complete backtest flow with known data"""

def test_multi_region_backtest():
    """Test backtest across multiple regions"""

def test_parameter_optimization():
    """Test grid search and walk-forward analysis"""
```

### Performance Tests

#### 5. Backtest Speed Benchmarks
```python
# tests/test_backtest_performance.py
def test_backtest_speed():
    """Benchmark: 2-year backtest should complete in <60 seconds"""

def test_optimization_speed():
    """Benchmark: 100-iteration grid search should complete in <30 minutes"""
```

**Target Performance**:
- Single backtest (2 years, 100 stocks): <60 seconds
- Grid search (100 iterations): <30 minutes with parallel execution

---

## Risk Warnings

### Common Backtesting Pitfalls

#### 1. Look-Ahead Bias
**Problem**: Using future data in decisions
**Mitigation**: Event-driven architecture, point-in-time data snapshots

#### 2. Survivorship Bias
**Problem**: Only backtesting stocks that survived
**Mitigation**: Include delisted stocks (if available), be aware of data limitations

#### 3. Overfitting
**Problem**: Parameters too fitted to historical data
**Mitigation**: Walk-forward analysis, out-of-sample testing, Monte Carlo validation

#### 4. Unrealistic Execution
**Problem**: Assuming perfect execution (no slippage, instant fills)
**Mitigation**: Transaction cost model, tick size compliance, volume-based slippage

#### 5. Market Regime Changes
**Problem**: Strategy works in bull market but fails in bear market
**Mitigation**: Test across different market regimes, compare to benchmark

### Disclaimer

**Backtesting results do not guarantee future performance.**

- Past performance is not indicative of future results
- Market conditions change over time
- Backtesting cannot account for all real-world factors
- Always paper trade before live deployment
- Start with small position sizes in live trading

---

## Next Steps

1. **Review Design**: Get feedback from power users on requirements
2. **Phase 1 Implementation**: Build core infrastructure (Week 1)
3. **Iterative Development**: Follow 8-week roadmap
4. **User Testing**: Beta test with power users after Phase 4
5. **Production Release**: Full release after Phase 7 completion

---

## Appendix

### A. Example Backtest Script

```python
#!/usr/bin/env python3
"""
Example: Simple backtest script for Spock
"""
from datetime import date
from modules.backtesting import BacktestEngine, BacktestConfig
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Initialize database
db = SQLiteDatabaseManager()

# Configure backtest
config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    regions=['KR'],
    score_threshold=70,
    risk_profile='moderate',
    initial_capital=100_000_000
)

# Run backtest
engine = BacktestEngine(config, db)
result = engine.run()

# Print summary
result.print_console_summary()

# Export to HTML
result.export_html_report('reports/backtest_20241017.html')

# Save to database
result.save_to_database(db)

print(f"\n✅ Backtest complete!")
print(f"Total Return: {result.metrics.total_return:.1%}")
print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.metrics.max_drawdown:.1%}")
print(f"Win Rate: {result.metrics.win_rate:.1%}")
```

### B. Example Parameter Optimization

```python
#!/usr/bin/env python3
"""
Example: Parameter optimization with grid search
"""
from modules.backtesting import ParameterOptimizer, BacktestConfig

# Base configuration
base_config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2024, 12, 31),
    regions=['KR'],
    initial_capital=100_000_000
)

# Parameter grid
param_grid = {
    'score_threshold': [60, 65, 70, 75, 80],
    'kelly_multiplier': [0.25, 0.5, 0.75, 1.0],
    'stop_loss_atr_multiplier': [0.75, 1.0, 1.25],
    'profit_target': [0.15, 0.20, 0.25]
}

# Run optimization
optimizer = ParameterOptimizer(base_config, db)
results = optimizer.grid_search(
    param_grid=param_grid,
    metric='sharpe_ratio',
    parallel=True,
    n_jobs=4
)

# Print best configuration
print(f"Best Sharpe Ratio: {results.best_score:.2f}")
print(f"Optimal Parameters:")
for param, value in results.best_config.items():
    print(f"  {param}: {value}")

# Export results
results.export_csv('reports/optimization_results.csv')
```

### C. Example Walk-Forward Analysis

```python
#!/usr/bin/env python3
"""
Example: Walk-forward analysis for robustness validation
"""

# Run walk-forward analysis
wf_result = optimizer.walk_forward_analysis(
    train_months=12,
    test_months=3,
    param_grid={'score_threshold': [65, 70, 75]},
    metric='sharpe_ratio'
)

# Print results
print(f"Walk-Forward Analysis Results:")
print(f"  In-Sample Sharpe: {wf_result.avg_is_sharpe:.2f}")
print(f"  Out-of-Sample Sharpe: {wf_result.avg_oos_sharpe:.2f}")
print(f"  Efficiency: {wf_result.efficiency:.1%}")

# Check for overfitting
if wf_result.efficiency < 0.5:
    print("⚠️ Warning: Significant overfitting detected!")
elif wf_result.efficiency < 0.8:
    print("⚠️ Moderate overfitting detected")
else:
    print("✅ Strategy appears robust")
```

---

**Document Version**: 1.0
**Last Updated**: 2025-10-17
**Author**: Claude Code (claude.ai/code)
**Status**: Design Complete, Ready for Implementation
