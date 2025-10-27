# Quant Investment Platform - System Architecture

**Document Version**: 1.0.0
**Last Updated**: 2025-10-18
**Status**: Initial Design Phase

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Layers](#2-architecture-layers)
3. [Component Design](#3-component-design)
4. [Data Flow Architecture](#4-data-flow-architecture)
5. [Integration Patterns](#5-integration-patterns)
6. [Scalability & Performance](#6-scalability--performance)
7. [Security Architecture](#7-security-architecture)
8. [Deployment Architecture](#8-deployment-architecture)

---

## 1. System Overview

### 1.1 System Purpose

**Quant Investment Platform** is a comprehensive quantitative research and portfolio management system designed for systematic, evidence-based investment strategy development. The platform enables:

- **Multi-Factor Analysis**: Combine 25+ factors (Value, Momentum, Quality, Low-Vol, Size) for robust alpha generation
- **Rigorous Backtesting**: Historical simulation with realistic transaction costs and walk-forward validation
- **Portfolio Optimization**: Mean-variance, risk parity, Black-Litterman, and Kelly criterion allocation
- **Risk Management**: VaR/CVaR calculation, stress testing, and liquidity risk modeling
- **Research Productivity**: Interactive Streamlit dashboard and FastAPI backend for strategy development

### 1.2 Design Principles

1. **Research-Driven**: Strategy validation through rigorous backtesting before deployment
2. **Evidence-Based**: Data-driven factor analysis with statistical significance testing
3. **Systematic**: Reproducible results through version-controlled strategies
4. **Modular**: Pluggable components (factors, optimizers, backtesting engines)
5. **Scalable**: TimescaleDB for time-series data, vectorized backtesting for speed
6. **Robust**: Data quality monitoring, vendor fallback, error recovery

### 1.3 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 User Interface Layer                             │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Streamlit        │  │ FastAPI          │                    │
│  │ Research         │  │ REST API         │                    │
│  │ Dashboard        │  │ Backend          │                    │
│  └──────────────────┘  └──────────────────┘                    │
└────────────┬────────────────────┬────────────────────────────────┘
             │                    │
┌────────────▼────────────────────▼────────────────────────────────┐
│                 Application Layer                                │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐  │
│  │ Strategy     │ Backtest     │ Portfolio    │ Risk        │  │
│  │ Manager      │ Runner       │ Optimizer    │ Manager     │  │
│  └──────────────┴──────────────┴──────────────┴─────────────┘  │
└────────────┬─────────────────────────────────────────────────────┘
             │
┌────────────▼─────────────────────────────────────────────────────┐
│                 Core Engine Layer                                │
│  ┌──────────────────┬──────────────────┬──────────────────────┐ │
│  │ Multi-Factor     │ Backtesting      │ Portfolio Optimizer  │ │
│  │ Analysis Engine  │ Engine           │ (cvxpy)              │ │
│  │ - Value (5)      │ - backtrader     │ - Mean-Variance      │ │
│  │ - Momentum (5)   │ - zipline        │ - Risk Parity        │ │
│  │ - Quality (5)    │ - vectorbt       │ - Black-Litterman    │ │
│  │ - Low-Vol (5)    │ - Cost Model     │ - Kelly Multi-Asset  │ │
│  │ - Size (5)       │ - Walk-Forward   │ - Constraints        │ │
│  └──────────────────┴──────────────────┴──────────────────────┘ │
└────────────┬─────────────────────────────────────────────────────┘
             │
┌────────────▼─────────────────────────────────────────────────────┐
│                 Data Layer                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PostgreSQL + TimescaleDB                                 │  │
│  │ - Hypertables: ohlcv_data (continuous aggregates)        │  │
│  │ - Tables: factors, strategies, backtest_results          │  │
│  │ - Compression: 10x after 1 year                          │  │
│  │ - Retention: Unlimited                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────┬─────────────────────────────────────────────────────┘
             │
┌────────────▼─────────────────────────────────────────────────────┐
│                 Data Collection Layer (Reused from Spock)        │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐  │
│  │ KIS API      │ yfinance     │ Market       │ Parsers     │  │
│  │ (Primary)    │ (Fallback)   │ Adapters     │ (6 regions) │  │
│  └──────────────┴──────────────┴──────────────┴─────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Layers

### 2.1 User Interface Layer

**Components**:
- **Streamlit Research Dashboard**: Interactive web application for strategy development
- **FastAPI REST API**: Backend API for programmatic access and integration

**Responsibilities**:
- User authentication and session management
- Input validation and sanitization
- Response formatting and error handling
- Real-time updates and notifications

**Technology Stack**:
- Streamlit 1.27.0 (dashboard)
- FastAPI 0.103.1 (REST API)
- uvicorn 0.23.2 (ASGI server)
- plotly 5.17.0 (interactive charts)

### 2.2 Application Layer

**Components**:
- **Strategy Manager**: Strategy CRUD operations, version control, deployment
- **Backtest Runner**: Backtest orchestration, parameter optimization, result caching
- **Portfolio Optimizer**: Portfolio construction, rebalancing, constraint handling
- **Risk Manager**: Risk assessment, position limits, alert generation

**Responsibilities**:
- Business logic coordination
- Transaction management
- Caching and performance optimization
- Logging and monitoring integration

**Design Patterns**:
- **Strategy Pattern**: Pluggable backtesting engines (backtrader, zipline, vectorbt)
- **Factory Pattern**: Dynamic factor instantiation based on configuration
- **Observer Pattern**: Real-time backtest progress updates to dashboard
- **Repository Pattern**: Data access abstraction for database operations

### 2.3 Core Engine Layer

**Components**:
- **Multi-Factor Analysis Engine**: Factor calculation, combination, signal generation
- **Backtesting Engine**: Historical simulation with transaction costs
- **Portfolio Optimizer**: Mathematical optimization using cvxpy

**Responsibilities**:
- Core algorithmic logic
- Mathematical computations (NumPy, SciPy)
- Performance-critical operations (vectorization)
- Deterministic result generation

**Key Algorithms**:
- Factor scoring and normalization (z-score, percentile rank)
- Portfolio optimization (quadratic programming, convex optimization)
- Risk calculation (VaR, CVaR, Sharpe ratio, drawdown)
- Transaction cost modeling (Almgren-Chriss market impact)

### 2.4 Data Layer

**Components**:
- **PostgreSQL 15+**: Relational database for structured data
- **TimescaleDB 2.11+**: Time-series extension for OHLCV data
- **Continuous Aggregates**: Materialized views for monthly/yearly data

**Responsibilities**:
- Data persistence and retrieval
- Time-series data optimization
- Data compression and retention policies
- Backup and disaster recovery

**Schema Design**:
- **Hypertables**: `ohlcv_data` (partitioned by date)
- **Tables**: `tickers`, `factors`, `strategies`, `backtest_results`, `portfolio_holdings`
- **Indexes**: Optimized for time-series queries and factor lookups
- **Constraints**: Foreign keys, unique constraints, check constraints

### 2.5 Data Collection Layer (Reused from Spock)

**Components**:
- **KIS API Client**: Primary data source (20 req/sec, 6 markets)
- **yfinance API**: Fallback data source (1 req/sec, global coverage)
- **Market Adapters**: Region-specific adapters (KR, US, CN, HK, JP, VN)
- **Data Parsers**: Ticker normalization, sector mapping to GICS 11

**Responsibilities**:
- OHLCV data collection with incremental updates
- Fundamental data collection (P/E, P/B, ROE, etc.)
- Data quality validation and anomaly detection
- Rate limiting and error recovery

---

## 3. Component Design

### 3.1 Multi-Factor Analysis Engine

**Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│              Multi-Factor Analysis Engine                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Factor Library (5 Categories)             │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Value (5):      P/E, P/B, EV/EBITDA, DY, FCF      │    │
│  │ Momentum (5):   12M return, RSI, 52W high, ...    │    │
│  │ Quality (5):    ROE, D/E, Earnings Quality, ...   │    │
│  │ Low-Vol (5):    Volatility, Beta, Drawdown, ...   │    │
│  │ Size (5):       Market Cap, Liquidity, ...        │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Factor Calculation Pipeline                │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ 1. Raw Data Retrieval (OHLCV, Fundamentals)       │    │
│  │ 2. Factor Computation (vectorized NumPy)           │    │
│  │ 3. Normalization (z-score or percentile rank)     │    │
│  │ 4. Missing Data Handling (forward fill, median)   │    │
│  │ 5. Outlier Treatment (winsorization at 1st/99th)  │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Factor Combination Methods                 │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Equal Weight:    Avg(F₁, F₂, ..., Fₙ)             │    │
│  │ Optimization:    Max Sharpe via historical perf   │    │
│  │ Risk-Adjusted:   Inverse volatility weighting     │    │
│  │ ML-Based:        XGBoost/RandomForest ensemble    │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │         Signal Generation                          │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Composite Score: 0-100 (weighted factor average)  │    │
│  │ Signal:          BUY (≥70), WATCH (50-70), AVOID  │    │
│  │ Confidence:      Score percentile vs universe     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Key Interfaces**:

```python
# Factor base class
class FactorBase:
    def calculate(self, ticker: str, region: str, date: str) -> float
    def normalize(self, raw_scores: pd.Series) -> pd.Series
    def get_win_rate(self) -> float  # From historical backtest

# Factor combiner
class FactorCombiner:
    def combine_equal_weight(self, factors: List[FactorBase]) -> pd.Series
    def combine_optimized(self, factors: List[FactorBase], lookback: int) -> pd.Series
    def combine_ml(self, factors: List[FactorBase], target: pd.Series) -> pd.Series
```

**Data Dependencies**:
- **Input**: `ohlcv_data` (hypertable), `fundamental_data` (table)
- **Output**: `factor_scores` (table), `composite_signals` (table)

---

### 3.2 Backtesting Engine

**Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                  Backtesting Engine                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Backtesting Framework Selector                 │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ backtrader:  Event-driven, custom strategies      │    │
│  │ zipline:     Quantopian-style, pipeline API       │    │
│  │ vectorbt:    Vectorized, ultra-fast optimization  │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Historical Data Provider                       │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Query: SELECT * FROM ohlcv_data WHERE ...         │    │
│  │ Cache: 24-hour TTL for repeated backtests         │    │
│  │ Validation: Check for missing data, anomalies     │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Strategy Execution                             │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Signal Generation: Buy/Sell based on factors      │    │
│  │ Order Placement: Market/Limit orders              │    │
│  │ Portfolio Management: Position sizing, cash       │    │
│  │ Rebalancing: Monthly/quarterly/threshold-based    │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Transaction Cost Model                         │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Commission: 0.015% (KIS API standard)             │    │
│  │ Slippage: Almgren-Chriss market impact model      │    │
│  │ Spread: Bid-ask spread from historical data       │    │
│  │ Partial Fills: Probability-based simulation       │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Performance Metrics                            │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Returns: Total, annualized, rolling                │    │
│  │ Risk-Adjusted: Sharpe, Sortino, Calmar            │    │
│  │ Drawdown: Max, average, duration                  │    │
│  │ Win Rate: % profitable trades                     │    │
│  │ VaR/CVaR: 95% confidence, 1-day/10-day            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Walk-Forward Optimization**:

```
In-Sample Training (3 years)  →  Out-of-Sample Test (1 year)
├─ 2015-2017 train → 2018 test
├─ 2016-2018 train → 2019 test
├─ 2017-2019 train → 2020 test
├─ 2018-2020 train → 2021 test
├─ 2019-2021 train → 2022 test
└─ 2020-2022 train → 2023 test

Acceptance Criteria:
- Out-of-sample Sharpe > 0.8 × In-sample Sharpe
- Drawdown < 1.5 × In-sample Drawdown
```

**Key Interfaces**:

```python
# Backtesting engine
class BacktestEngine:
    def run_backtest(
        self,
        strategy: Strategy,
        start_date: str,
        end_date: str,
        initial_capital: float
    ) -> BacktestResult

    def walk_forward_optimize(
        self,
        strategy: Strategy,
        train_period: int,  # years
        test_period: int,   # years
        param_grid: Dict
    ) -> WalkForwardResult

# Transaction cost model
class TransactionCostModel:
    def calculate_commission(self, order_value: float) -> float
    def calculate_slippage(self, order_size: float, avg_daily_volume: float) -> float
    def calculate_spread_cost(self, order_size: float, spread: float) -> float
```

---

### 3.3 Portfolio Optimizer

**Architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                 Portfolio Optimizer (cvxpy)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Input Data Preparation                         │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Expected Returns: Historical mean, CAPM, BL views │    │
│  │ Covariance Matrix: Sample cov, shrinkage, robust  │    │
│  │ Constraints: Position/sector/turnover/cash limits │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Optimization Method Selection                  │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Mean-Variance:     Max Sharpe or min variance     │    │
│  │ Risk Parity:       Equal risk contribution        │    │
│  │ Black-Litterman:   Market equilibrium + views     │    │
│  │ Kelly Multi-Asset: Max geometric growth rate      │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Convex Optimization (cvxpy)                    │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Objective:    Maximize(returns - λ × risk)        │    │
│  │ Variables:    w (asset weights)                   │    │
│  │ Constraints:  Σw = 1, 0 ≤ w ≤ 0.15, etc.         │    │
│  │ Solver:       OSQP, ECOS, SCS (auto-select)      │    │
│  └────────────────────────────────────────────────────┘    │
│                         ↓                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │     Result Validation                              │    │
│  ├────────────────────────────────────────────────────┤    │
│  │ Feasibility: All constraints satisfied            │    │
│  │ Stability: Small changes in inputs → stable output│    │
│  │ Diversification: No over-concentration            │    │
│  │ Turnover: Acceptable rebalancing cost             │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Optimization Formulations**:

**Mean-Variance (Markowitz)**:
```python
# Maximize: E[R] - λ × Var[R]
returns = cp.Variable(n_assets)
risk = cp.quad_form(returns, cov_matrix)
objective = cp.Maximize(expected_returns @ returns - risk_aversion * risk)
constraints = [
    cp.sum(returns) == 1,      # Fully invested
    returns >= 0,              # Long-only
    returns <= 0.15            # Max 15% per asset
]
problem = cp.Problem(objective, constraints)
problem.solve()
```

**Risk Parity**:
```python
# Minimize: Σ(RC_i - RC_target)²
# where RC_i = w_i × (Σ_w)_i (risk contribution)
weights = cp.Variable(n_assets)
risk_contributions = cp.multiply(weights, cov_matrix @ weights)
target_rc = total_risk / n_assets
objective = cp.Minimize(cp.sum_squares(risk_contributions - target_rc))
```

**Key Interfaces**:

```python
# Portfolio optimizer
class PortfolioOptimizer:
    def optimize_mean_variance(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        constraints: Dict
    ) -> np.ndarray  # Optimal weights

    def optimize_risk_parity(
        self,
        cov_matrix: np.ndarray,
        constraints: Dict
    ) -> np.ndarray

    def optimize_black_litterman(
        self,
        market_caps: np.ndarray,
        views: Dict,
        cov_matrix: np.ndarray
    ) -> np.ndarray
```

---

## 4. Data Flow Architecture

### 4.1 Data Collection Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Data Collection Flow                        │
└─────────────────────────────────────────────────────────────┘

1. Ticker Discovery
   └─> KIS Master File API (24-hour cache)
   └─> yfinance fallback (if KIS unavailable)
   └─> Store in tickers table

2. OHLCV Collection
   ├─> KIS Overseas API (primary, 20 req/sec)
   ├─> yfinance (fallback, 1 req/sec)
   ├─> Rate limiting & retry with exponential backoff
   ├─> Data quality validation (missing data, anomalies)
   └─> Insert into ohlcv_data hypertable

3. Fundamental Data Collection
   ├─> DART API (Korea financial statements)
   ├─> SEC Edgar API (US financial statements)
   ├─> yfinance (global fallback)
   ├─> Calculate ratios (P/E, P/B, ROE, D/E)
   └─> Store in fundamental_data table

4. Technical Indicators
   ├─> Fetch OHLCV from hypertable
   ├─> Calculate MA, RSI, MACD, Bollinger Bands, ATR
   ├─> Vectorized computation (pandas-ta)
   └─> Update ohlcv_data with indicators

5. Factor Calculation
   ├─> Fetch OHLCV + fundamentals
   ├─> Calculate 25+ factors (Value, Momentum, Quality, Low-Vol, Size)
   ├─> Normalize (z-score or percentile rank)
   └─> Store in factor_scores table
```

### 4.2 Strategy Development Flow

```
┌─────────────────────────────────────────────────────────────┐
│               Strategy Development Flow                      │
└─────────────────────────────────────────────────────────────┘

1. Factor Research
   ├─> Analyze individual factor performance (Sharpe, IC)
   ├─> Check factor correlations (avoid redundancy)
   └─> Select factors for strategy

2. Strategy Definition
   ├─> Define factor weights (equal, optimized, ML)
   ├─> Set constraints (position, sector, turnover)
   ├─> Configure rebalancing (monthly, quarterly, threshold)
   └─> Store in strategies table

3. Backtesting
   ├─> Select backtesting engine (backtrader, zipline, vectorbt)
   ├─> Run historical simulation (5-10 years)
   ├─> Apply transaction cost model
   ├─> Calculate performance metrics
   └─> Store results in backtest_results table

4. Walk-Forward Optimization
   ├─> Split data into train/test windows (3y/1y)
   ├─> Optimize parameters on in-sample data
   ├─> Test on out-of-sample data
   ├─> Repeat with rolling windows
   └─> Validate: Out-of-sample Sharpe > 0.8 × In-sample

5. Portfolio Construction
   ├─> Select stocks based on factor scores
   ├─> Optimize portfolio weights (mean-variance, risk parity, etc.)
   ├─> Apply constraints (position/sector limits)
   ├─> Calculate expected risk/return
   └─> Store in portfolio_holdings table

6. Risk Analysis
   ├─> Calculate VaR/CVaR (95% confidence)
   ├─> Run stress tests (2008, 2020, 2022 scenarios)
   ├─> Check liquidity risk (days to liquidate)
   └─> Generate risk report

7. Strategy Deployment (Optional)
   ├─> Generate rebalancing orders
   ├─> Submit to KIS API (or paper trading)
   ├─> Monitor live performance vs backtest
   └─> Alert on significant deviations
```

### 4.3 Database Query Patterns

**OHLCV Data Retrieval** (Optimized for Time-Series):
```sql
-- Retrieve 5 years of daily data for US stocks (using hypertable)
SELECT ticker, date, open, high, low, close, volume
FROM ohlcv_data
WHERE region = 'US'
  AND date BETWEEN '2019-01-01' AND '2024-01-01'
  AND ticker IN ('AAPL', 'MSFT', 'GOOGL')
ORDER BY ticker, date;

-- Use continuous aggregate for monthly data (10x faster)
SELECT ticker, month, open, high, low, close, volume
FROM ohlcv_monthly
WHERE region = 'US'
  AND month BETWEEN '2019-01-01' AND '2024-01-01';
```

**Factor Score Retrieval**:
```sql
-- Get latest factor scores for all stocks in a region
SELECT ticker, factor_name, score, percentile
FROM factor_scores
WHERE region = 'US'
  AND date = (SELECT MAX(date) FROM factor_scores WHERE region = 'US')
ORDER BY score DESC;

-- Get composite scores (weighted average of factors)
SELECT ticker,
       AVG(CASE WHEN factor_name IN ('momentum_12m', 'rsi_momentum') THEN score END) AS momentum_score,
       AVG(CASE WHEN factor_name IN ('pe_ratio', 'pb_ratio') THEN score END) AS value_score
FROM factor_scores
WHERE region = 'US' AND date = CURRENT_DATE
GROUP BY ticker;
```

**Backtest Result Queries**:
```sql
-- Compare multiple strategies
SELECT s.name, br.sharpe_ratio, br.max_drawdown, br.total_return
FROM backtest_results br
JOIN strategies s ON br.strategy_id = s.id
WHERE br.start_date = '2019-01-01' AND br.end_date = '2024-01-01'
ORDER BY br.sharpe_ratio DESC;

-- Get detailed backtest metrics (JSON field)
SELECT strategy_id,
       results_json->>'total_trades' AS total_trades,
       results_json->>'win_rate' AS win_rate,
       results_json->>'avg_trade_duration_days' AS avg_duration
FROM backtest_results
WHERE strategy_id = 1;
```

---

## 5. Integration Patterns

### 5.1 API Integration

**KIS API Integration** (Primary Data Source):
```python
# Exponential backoff retry logic
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(KISAPIError)
)
def get_ohlcv_data(ticker, region, start_date, end_date):
    response = kis_api.get_daily_price(ticker, region, start_date, end_date)
    validate_data_quality(response)
    return response

# Rate limiting (20 req/sec)
rate_limiter = RateLimiter(max_calls=20, period=1)

@rate_limiter
def fetch_ticker_data(ticker):
    return kis_api.get_daily_price(ticker)
```

**Data Vendor Fallback**:
```python
# Multi-tier fallback strategy
class DataProvider:
    def get_ohlcv_data(self, ticker, region, start_date, end_date):
        # Tier 1: KIS API (primary)
        try:
            return kis_api.get_data(ticker, region, start_date, end_date)
        except KISAPIError as e:
            logger.warning(f"KIS API failed: {e}, trying yfinance")

        # Tier 2: yfinance (global fallback)
        try:
            return yfinance_api.get_data(ticker, start_date, end_date)
        except Exception as e:
            logger.error(f"All data sources failed: {e}")
            return None
```

### 5.2 Database Integration

**Connection Pooling** (psycopg2):
```python
# PostgreSQL connection pool
from psycopg2 import pool

db_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=20,
    host='localhost',
    database='quant_platform',
    user='postgres',
    password='***'
)

# Context manager for safe connection handling
@contextmanager
def get_db_connection():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)
```

**TimescaleDB Continuous Aggregates**:
```sql
-- Create continuous aggregate for monthly OHLCV data
CREATE MATERIALIZED VIEW ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT ticker, region,
       time_bucket('1 month', date) AS month,
       first(open, date) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close, date) AS close,
       sum(volume) AS volume
FROM ohlcv_data
GROUP BY ticker, region, month
WITH NO DATA;

-- Refresh policy (every night at 2am)
SELECT add_continuous_aggregate_policy('ohlcv_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

### 5.3 Monitoring Integration

**Prometheus Metrics**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
backtest_count = Counter('backtest_total', 'Total backtests run', ['strategy'])
backtest_duration = Histogram('backtest_duration_seconds', 'Backtest execution time')
portfolio_value = Gauge('portfolio_value_usd', 'Current portfolio value')

# Usage
@backtest_duration.time()
def run_backtest(strategy):
    result = backtest_engine.run(strategy)
    backtest_count.labels(strategy=strategy.name).inc()
    return result
```

**Grafana Dashboard**:
- Backtest performance (Sharpe ratio, drawdown, win rate)
- Factor performance (IC, factor returns)
- Data quality (completeness, freshness, anomalies)
- System health (CPU, memory, database size)

---

## 6. Scalability & Performance

### 6.1 Performance Optimization Strategies

**Vectorization** (NumPy):
```python
# Bad: Loop-based calculation (slow)
for i in range(len(prices)):
    returns[i] = (prices[i] - prices[i-1]) / prices[i-1]

# Good: Vectorized calculation (100x faster)
returns = np.diff(prices) / prices[:-1]
```

**Parallel Processing** (multiprocessing):
```python
from multiprocessing import Pool

# Parallelize backtest across multiple strategies
def run_backtest_parallel(strategies, n_workers=4):
    with Pool(n_workers) as pool:
        results = pool.map(run_backtest, strategies)
    return results
```

**Caching** (lru_cache):
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_factor_scores(ticker, region, date):
    # Cache factor scores to avoid repeated database queries
    return db.query_factor_scores(ticker, region, date)
```

### 6.2 Scalability Architecture

**Horizontal Scaling**:
- **Backtest Workers**: Multiple workers running backtests in parallel (Celery)
- **Database Sharding**: Partition `ohlcv_data` by region (KR, US, CN, etc.)
- **Read Replicas**: PostgreSQL read replicas for query-heavy workloads

**Vertical Scaling**:
- **Database**: 16-32 GB RAM, 8-16 CPU cores for TimescaleDB
- **Application**: 8-16 GB RAM, 4-8 CPU cores for backtesting

**Performance Targets**:
- Backtest (5-year, 100 stocks): <30 seconds
- Portfolio optimization (100 assets): <60 seconds
- Factor calculation (3,000 stocks): <5 minutes
- Database query (10-year OHLCV): <1 second

---

## 7. Security Architecture

### 7.1 Authentication & Authorization

**API Key Management**:
```python
# Secure API key storage (.env file with 600 permissions)
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here

# Access via environment variables
import os
from dotenv import load_dotenv

load_dotenv()
app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')
```

**User Authentication** (FastAPI):
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    # Verify JWT token
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

### 7.2 Data Security

**Database Encryption**:
- **At Rest**: PostgreSQL transparent data encryption (TDE)
- **In Transit**: SSL/TLS connections (require_ssl=True)

**Sensitive Data Handling**:
```python
# Never log sensitive data
logger.info(f"User {user.id} accessed strategy {strategy_id}")  # Good
logger.info(f"API key: {app_key}")  # Bad - never log credentials
```

### 7.3 Access Control

**Role-Based Access Control (RBAC)**:
```python
class Role(Enum):
    ADMIN = "admin"  # Full access
    RESEARCHER = "researcher"  # Read + backtest
    VIEWER = "viewer"  # Read-only

def require_role(required_role: Role):
    def decorator(func):
        def wrapper(user: User, *args, **kwargs):
            if user.role < required_role:
                raise PermissionError("Insufficient permissions")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

@require_role(Role.RESEARCHER)
def run_backtest(user: User, strategy: Strategy):
    # Only researchers and admins can run backtests
    pass
```

---

## 8. Deployment Architecture

### 8.1 Development Environment

```
Local Machine (macOS/Linux)
├── PostgreSQL 15 + TimescaleDB 2.11 (Docker or native)
├── Python 3.11 virtual environment
├── Streamlit dev server (http://localhost:8501)
├── FastAPI dev server (http://localhost:8000)
└── Prometheus + Grafana (http://localhost:3000)
```

### 8.2 Production Environment

```
AWS Architecture (Example)
├── RDS PostgreSQL + TimescaleDB (db.r5.2xlarge)
│   ├── Multi-AZ deployment for high availability
│   ├── Automated backups (daily)
│   └── Read replicas for query scaling
├── EC2 Instance (c5.2xlarge) - Application Server
│   ├── FastAPI (gunicorn + uvicorn workers)
│   ├── Streamlit (streamlit run app.py)
│   └── Celery workers for background tasks
├── S3 Buckets
│   ├── Database backups
│   └── Backtest result caching
├── CloudWatch Monitoring
│   ├── Application logs
│   ├── Database metrics
│   └── Custom metrics (Prometheus exporter)
└── Load Balancer (ALB)
    └── HTTPS termination, auto-scaling
```

### 8.3 CI/CD Pipeline

```
GitHub Actions Workflow
├── On Push to main:
│   ├── Linting (flake8, black)
│   ├── Type checking (mypy)
│   ├── Unit tests (pytest, >80% coverage)
│   ├── Integration tests
│   └── Build Docker image
├── On Pull Request:
│   ├── All checks from Push
│   └── Code review required
└── On Release Tag:
    ├── Deploy to staging
    ├── Run smoke tests
    ├── Manual approval
    └── Deploy to production
```

---

## Appendix A: Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI** | Streamlit 1.27.0 | Interactive research dashboard |
| **API** | FastAPI 0.103.1 | REST API backend |
| **Application** | Python 3.11+ | Business logic |
| **Backtesting** | backtrader, zipline, vectorbt | Historical simulation |
| **Optimization** | cvxpy 1.3.2 | Portfolio optimization |
| **Database** | PostgreSQL 15 + TimescaleDB 2.11 | Data persistence |
| **Caching** | lru_cache, Redis (optional) | Performance optimization |
| **Monitoring** | Prometheus + Grafana | Metrics and alerting |
| **Logging** | loguru 0.7.0 | Application logging |
| **Testing** | pytest, coverage.py | Test framework |
| **CI/CD** | GitHub Actions | Automation |

---

## Appendix B: Performance Benchmarks

| Operation | Target | Actual (Expected) |
|-----------|--------|-------------------|
| Backtest (5-year, 100 stocks) | <30s | ~20s (backtrader) |
| Portfolio optimization (100 assets) | <60s | ~40s (cvxpy) |
| Factor calculation (3,000 stocks) | <5min | ~3min (vectorized) |
| Database query (10-year OHLCV) | <1s | ~500ms (hypertable) |
| Factor score update (daily) | <10min | ~5min (bulk insert) |

---

**Document End**

**Next Documents**:
1. [FACTOR_LIBRARY_REFERENCE.md](FACTOR_LIBRARY_REFERENCE.md) - 25+ factor definitions
2. [BACKTESTING_GUIDE.md](BACKTESTING_GUIDE.md) - Best practices and pitfalls
3. [OPTIMIZATION_COOKBOOK.md](OPTIMIZATION_COOKBOOK.md) - Portfolio optimization recipes
4. [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - PostgreSQL schema DDL
