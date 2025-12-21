# IMPLEMENTATION_PLAN.md

Detailed implementation plan for Quant Investment Platform development (10-week roadmap).

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: Database Setup (Week 1)](#phase-1-database-setup-week-1)
3. [Phase 2: Factor Implementation (Week 2-3)](#phase-2-factor-implementation-week-2-3)
4. [Phase 3: Backtesting Engine (Week 4-5)](#phase-3-backtesting-engine-week-4-5)
5. [Phase 4: Portfolio Optimizer (Week 6)](#phase-4-portfolio-optimizer-week-6)
6. [Phase 5: Risk Management (Week 7)](#phase-5-risk-management-week-7)
7. [Phase 6: Web Interface (Week 8)](#phase-6-web-interface-week-8)
8. [Phase 7: Testing & Validation (Week 9)](#phase-7-testing--validation-week-9)
9. [Phase 8: Production Deployment (Week 10)](#phase-8-production-deployment-week-10)
10. [Progress Tracking](#progress-tracking)

---

## Overview

### Project Goals

Transform Spock from an automated trading system into a research-driven quantitative investment platform with:
- Multi-factor analysis engine (25+ factors)
- Sophisticated backtesting framework (walk-forward validation)
- Portfolio optimization (4 methods: Markowitz, Risk Parity, Black-Litterman, Kelly)
- Advanced risk management (VaR/CVaR, stress testing)
- Web-based research dashboard (Streamlit)

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Development Time** | 10 weeks | Calendar time |
| **Code Reuse** | 70% | Lines of code from Spock |
| **Strategy Sharpe Ratio** | >1.5 | Backtest performance |
| **Backtest Speed** | <30 sec | 5-year simulation |
| **Test Coverage** | >80% | pytest coverage report |

### Architecture Reference

All implementation details reference the following documents:
- [QUANT_PLATFORM_ARCHITECTURE.md](QUANT_PLATFORM_ARCHITECTURE.md) - System design
- [FACTOR_LIBRARY_REFERENCE.md](FACTOR_LIBRARY_REFERENCE.md) - Factor definitions
- [BACKTESTING_GUIDE.md](BACKTESTING_GUIDE.md) - Backtesting best practices
- [OPTIMIZATION_COOKBOOK.md](OPTIMIZATION_COOKBOOK.md) - Portfolio optimization
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - PostgreSQL schema

---

## Phase 1: Database Setup (Week 1)

**Duration**: 5 days
**Parallel Work**: Data quality monitoring + Data vendor fallback
**Goal**: Operational PostgreSQL + TimescaleDB with migrated historical data

### Day 1: PostgreSQL + TimescaleDB Installation

**Tasks**:

1. **Install PostgreSQL 15+** (2 hours)
   ```bash
   # macOS
   brew install postgresql@15
   brew services start postgresql@15

   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install postgresql-15 postgresql-client-15

   # Verify installation
   psql --version  # Should show PostgreSQL 15.x
   ```

2. **Install TimescaleDB 2.11+** (1 hour)
   ```bash
   # macOS
   brew install timescaledb
   timescaledb-tune --quiet --yes

   # Ubuntu/Debian
   sudo add-apt-repository ppa:timescale/timescaledb-ppa
   sudo apt update
   sudo apt install timescaledb-2-postgresql-15

   # Configure PostgreSQL
   sudo timescaledb-tune --quiet --yes
   sudo systemctl restart postgresql
   ```

3. **Create Database** (30 minutes)
   ```bash
   # Run database_init.sql from DATABASE_SCHEMA.md
   createdb quant_platform
   psql -d quant_platform -f docs/sql/database_init.sql

   # Verify TimescaleDB extension
   psql -d quant_platform -c "SELECT * FROM timescaledb_information.hypertables;"
   ```

**Deliverables**:
- ✅ PostgreSQL 15+ running
- ✅ TimescaleDB 2.11+ enabled
- ✅ `quant_platform` database created
- ✅ Extensions installed (timescaledb, pg_stat_statements, pgcrypto)

---

### Day 2-3: Database Schema Implementation

**Tasks**:

1. **Create Core Tables** (4 hours)
   ```bash
   # Run DDL from DATABASE_SCHEMA.md
   psql -d quant_platform -f docs/sql/create_tables.sql
   ```

   **Tables to Create**:
   - `tickers` - Ticker universe
   - `ohlcv_data` - Price and volume data (hypertable)
   - `factor_scores` - Multi-factor analysis results (hypertable)
   - `backtest_results` - Backtesting simulation results (hypertable)
   - `portfolio` - Current portfolio holdings
   - `trades` - Trade execution history
   - `portfolio_snapshots` - Daily portfolio snapshots (hypertable)
   - `api_logs` - KIS API call logs
   - `system_logs` - System event logs

2. **Create Hypertables** (1 hour)
   ```sql
   -- Convert time-series tables to hypertables
   SELECT create_hypertable('ohlcv_data', 'date', chunk_time_interval => INTERVAL '1 month');
   SELECT create_hypertable('factor_scores', 'calculation_date', chunk_time_interval => INTERVAL '1 month');
   SELECT create_hypertable('backtest_results', 'simulation_date', chunk_time_interval => INTERVAL '3 months');
   SELECT create_hypertable('portfolio_snapshots', 'snapshot_date', chunk_time_interval => INTERVAL '3 months');
   ```

3. **Create Indexes** (2 hours)
   ```bash
   psql -d quant_platform -f docs/sql/create_indexes.sql
   ```

4. **Setup Compression Policies** (1 hour)
   ```sql
   -- Enable compression (compress data older than 90 days)
   ALTER TABLE ohlcv_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'ticker,region');
   SELECT add_compression_policy('ohlcv_data', INTERVAL '90 days');
   ```

**Deliverables**:
- ✅ 9 core tables created
- ✅ 4 hypertables configured
- ✅ All indexes created
- ✅ Compression policies enabled

---

### Day 4: Data Migration from SQLite

**Tasks**:

1. **Create Migration Script** (3 hours)
   ```python
   # scripts/migrate_sqlite_to_postgres.py
   # See DATABASE_SCHEMA.md Section 9.1 for complete script

   import sqlite3
   import psycopg2
   from psycopg2.extras import execute_batch
   import pandas as pd
   from tqdm import tqdm

   def migrate_tickers():
       """Migrate tickers table from SQLite to PostgreSQL."""
       # Read from Spock SQLite
       sqlite_conn = sqlite3.connect("data/spock_local.db")
       df = pd.read_sql_query("SELECT * FROM tickers", sqlite_conn)

       # Write to PostgreSQL
       pg_conn = psycopg2.connect(
           host="localhost", database="quant_platform",
           user="quant_user", password="secure_password"
       )
       # Batch insert with ON CONFLICT handling
       # ...

   def migrate_ohlcv_data():
       """Migrate OHLCV data (batch processing for large datasets)."""
       # Use batch_size=10000 for optimal performance
       # ...

   def migrate_all():
       migrate_tickers()
       migrate_ohlcv_data()
       # Add more tables as needed
   ```

2. **Run Migration** (2-4 hours depending on data size)
   ```bash
   python3 scripts/migrate_sqlite_to_postgres.py
   ```

3. **Validate Migration** (1 hour)
   ```sql
   -- Check row counts
   SELECT 'tickers' AS table_name, COUNT(*) FROM tickers
   UNION ALL
   SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data;

   -- Verify data integrity
   SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL;  -- Should be 0
   SELECT MIN(date), MAX(date) FROM ohlcv_data;
   ```

**Deliverables**:
- ✅ Migration script created
- ✅ Historical data migrated (tickers, OHLCV)
- ✅ Data validation passed (no NULL regions, correct date ranges)

---

### Day 5: Data Quality Monitoring + Vendor Fallback

**Parallel Tasks**:

#### A. Data Quality Monitoring (4 hours)

1. **Create Continuous Aggregates**
   ```sql
   -- Daily data quality summary
   CREATE MATERIALIZED VIEW data_quality_daily
   WITH (timescaledb.continuous) AS
   SELECT
       time_bucket('1 day', date) AS day,
       region,
       COUNT(*) AS row_count,
       COUNT(DISTINCT ticker) AS unique_tickers,
       COUNT(CASE WHEN volume = 0 THEN 1 END) AS zero_volume_count,
       MAX(date) AS latest_data_timestamp
   FROM ohlcv_data
   GROUP BY day, region;

   -- Add refresh policy
   SELECT add_continuous_aggregate_policy('data_quality_daily',
       start_offset => INTERVAL '3 days',
       end_offset => INTERVAL '1 hour',
       schedule_interval => INTERVAL '1 hour');
   ```

2. **Setup Grafana Alerts** (2 hours)
   - Completeness < 95% → Warning
   - Freshness > 24 hours → Critical
   - Zero volumes > 10% → Warning

#### B. Data Vendor Fallback (4 hours)

1. **Create Data Provider Abstraction**
   ```python
   # modules/data/data_provider.py
   class DataProvider:
       """Unified data provider with fallback logic."""

       def __init__(self, db, app_key, app_secret):
           self.db = db
           self.primary = KISOverseasStockAPI(app_key, app_secret)
           self.secondary = YFinanceAPI()
           self.tertiary = {
               'CN': AkShareAPI(),
               'US': PolygonAPI(api_key) if api_key else None
           }

       def get_ohlcv_data(self, ticker, region, start_date, end_date):
           """Get OHLCV data with automatic fallback."""
           # Try primary (KIS API)
           try:
               data = self.primary.get_daily_price(ticker, region, start_date, end_date)
               if data is not None and len(data) > 0:
                   return data
           except Exception as e:
               logger.warning(f"KIS API failed: {e}, falling back to yfinance")

           # Try secondary (yfinance)
           try:
               data = self.secondary.get_daily_price(ticker, start_date, end_date)
               if data is not None and len(data) > 0:
                   return data
           except Exception as e:
               logger.warning(f"yfinance failed: {e}")

           # Try tertiary (market-specific)
           if region in self.tertiary and self.tertiary[region]:
               try:
                   return self.tertiary[region].get_daily_price(ticker, start_date, end_date)
               except Exception as e:
                   logger.error(f"All data sources failed for {ticker}: {e}")

           return None
   ```

2. **Test Fallback Logic** (1 hour)
   ```python
   # tests/test_data_provider.py
   def test_fallback_on_primary_failure():
       provider = DataProvider(db, app_key, app_secret)
       # Mock KIS API failure
       with patch.object(provider.primary, 'get_daily_price', side_effect=Exception):
           data = provider.get_ohlcv_data('AAPL', 'US', '2024-01-01', '2024-12-31')
           assert data is not None  # Should fallback to yfinance
   ```

**Deliverables**:
- ✅ Data quality continuous aggregates created
- ✅ Grafana alerts configured
- ✅ Data provider abstraction implemented
- ✅ Fallback logic tested

---

### Week 1 Summary

**Completed Deliverables**:
- ✅ PostgreSQL + TimescaleDB operational
- ✅ Database schema implemented (9 tables, 4 hypertables)
- ✅ Data quality monitoring (continuous aggregates + Grafana alerts)
- ✅ Data vendor fallback logic (3-tier hierarchy)
- ✅ Migration script from Spock SQLite
- ✅ Week 1 completion report

**Validation Checklist**:
```bash
# Database operational
psql -d quant_platform -c "SELECT version();"

# Hypertables created
psql -d quant_platform -c "SELECT * FROM timescaledb_information.hypertables;"

# Data migrated
psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"

# Continuous aggregates working
psql -d quant_platform -c "SELECT * FROM data_quality_daily ORDER BY day DESC LIMIT 7;"

# Fallback logic tested
pytest tests/test_data_provider.py -v
```

---

## Phase 2: Factor Implementation (Week 2-3)

**Duration**: 10 days
**Parallel Work**: Factor library + Streamlit prototype
**Goal**: 25+ factors implemented with historical performance validation

### Top 5 Priority Factors

Based on [FACTOR_LIBRARY_REFERENCE.md](FACTOR_LIBRARY_REFERENCE.md), implement highest-impact factors first:

1. **P/E Ratio** (Value) - Win Rate: 58%, Sharpe: 0.4-0.6
2. **12M Momentum** (Momentum) - Win Rate: 65%, Sharpe: 0.7-0.9
3. **ROE** (Quality) - Win Rate: 59%, Sharpe: 0.5-0.7
4. **Historical Volatility** (Low-Volatility) - Win Rate: 57%, Sharpe: 0.8-1.0
5. **Market Cap** (Size) - Win Rate: 54%, Sharpe: 0.3-0.5

---

### Day 1-2: Factor Base Class & Infrastructure

**Tasks**:

1. **Create Factor Base Class** (4 hours)
   ```python
   # modules/factors/base_factor.py
   from abc import ABC, abstractmethod
   import pandas as pd
   import numpy as np
   from typing import Dict

   class FactorBase(ABC):
       """Abstract base class for all factors."""

       def __init__(self, db):
           self.db = db
           self.factor_name = self.__class__.__name__

       @abstractmethod
       def calculate(self, ticker: str, region: str, date: str) -> float:
           """
           Calculate raw factor value for a single stock.

           Args:
               ticker: Stock ticker symbol
               region: Market region (KR, US, CN, HK, JP, VN)
               date: Calculation date (YYYY-MM-DD)

           Returns:
               Raw factor value (or np.nan if calculation fails)
           """
           pass

       def normalize(self, raw_scores: pd.Series) -> pd.Series:
           """
           Normalize raw factor scores to z-scores.

           Args:
               raw_scores: Series of raw factor values

           Returns:
               Normalized z-scores (mean=0, std=1)
           """
           return (raw_scores - raw_scores.mean()) / raw_scores.std()

       def get_win_rate(self) -> float:
           """Return historical win rate from backtesting."""
           # Override in subclasses with actual backtest results
           return 0.55  # Default 55% win rate

       def get_historical_performance(self) -> Dict:
           """Return historical performance metrics."""
           return {
               'win_rate': self.get_win_rate(),
               'sharpe_ratio': 0.5,  # Default, override in subclasses
               'avg_annual_premium': 0.05  # Default 5% premium
           }
   ```

2. **Create Factor Calculator** (3 hours)
   ```python
   # modules/factors/factor_calculator.py
   class FactorCalculator:
       """Calculate factor scores for multiple stocks."""

       def __init__(self, db):
           self.db = db
           self.factors = {}

       def register_factor(self, factor: FactorBase):
           """Register a factor for calculation."""
           self.factors[factor.factor_name] = factor

       def calculate_all_factors(
           self,
           tickers: list,
           region: str,
           date: str
       ) -> pd.DataFrame:
           """
           Calculate all registered factors for given stocks.

           Returns:
               DataFrame with tickers as rows, factors as columns
           """
           results = {}

           for factor_name, factor in self.factors.items():
               scores = []
               for ticker in tickers:
                   try:
                       score = factor.calculate(ticker, region, date)
                       scores.append(score)
                   except Exception as e:
                       logger.warning(f"Factor {factor_name} failed for {ticker}: {e}")
                       scores.append(np.nan)

               # Normalize scores
               raw_scores = pd.Series(scores, index=tickers)
               results[factor_name] = factor.normalize(raw_scores)

           return pd.DataFrame(results)
   ```

**Deliverables**:
- ✅ `FactorBase` abstract class created
- ✅ `FactorCalculator` implemented
- ✅ Unit tests for base infrastructure

---

### Day 3-4: Value Factors Implementation

**Tasks**:

1. **P/E Ratio Factor** (2 hours)
   ```python
   # modules/factors/value/pe_ratio.py
   class PERatioFactor(FactorBase):
       """P/E Ratio: Price-to-Earnings ratio."""

       def calculate(self, ticker: str, region: str, date: str) -> float:
           # Get current price
           price = self.db.get_price(ticker, region, date)

           # Get trailing 12-month EPS
           eps = self.db.get_eps(ticker, region, date, trailing_12m=True)

           if eps <= 0:
               return np.nan  # Invalid for negative earnings

           return price / eps

       def normalize(self, raw_scores: pd.Series) -> pd.Series:
           # Lower P/E is better → invert before normalization
           inverted = 1 / raw_scores
           return (inverted - inverted.mean()) / inverted.std()

       def get_win_rate(self) -> float:
           return 0.58  # From FACTOR_LIBRARY_REFERENCE.md

       def get_historical_performance(self) -> Dict:
           return {
               'win_rate': 0.58,
               'sharpe_ratio': 0.5,
               'avg_annual_premium': 0.04  # 4% annual premium
           }
   ```

2. **P/B Ratio Factor** (2 hours)
   ```python
   # modules/factors/value/pb_ratio.py
   class PBRatioFactor(FactorBase):
       """P/B Ratio: Price-to-Book ratio."""

       def calculate(self, ticker: str, region: str, date: str) -> float:
           price = self.db.get_price(ticker, region, date)
           book_value_per_share = self.db.get_book_value_per_share(ticker, region, date)

           if book_value_per_share <= 0:
               return np.nan

           return price / book_value_per_share

       def normalize(self, raw_scores: pd.Series) -> pd.Series:
           inverted = 1 / raw_scores
           return (inverted - inverted.mean()) / inverted.std()
   ```

3. **Dividend Yield Factor** (1 hour)
4. **FCF Yield Factor** (1 hour)
5. **Test Value Factors** (2 hours)

**Deliverables**:
- ✅ 5 value factors implemented (P/E, P/B, EV/EBITDA, Dividend Yield, FCF Yield)
- ✅ Unit tests with sample data
- ✅ Historical performance validation

---

### Day 5-6: Momentum Factors Implementation

**Tasks**:

1. **12-Month Momentum** (2 hours)
   ```python
   # modules/factors/momentum/momentum_12m.py
   class Momentum12MFactor(FactorBase):
       """12-Month Momentum: Price change from 12 months ago to 1 month ago."""

       def calculate(self, ticker: str, region: str, date: str) -> float:
           from datetime import datetime, timedelta

           date_obj = datetime.strptime(date, '%Y-%m-%d')
           date_t_minus_1m = (date_obj - timedelta(days=30)).strftime('%Y-%m-%d')
           date_t_minus_12m = (date_obj - timedelta(days=365)).strftime('%Y-%m-%d')

           price_t_minus_1m = self.db.get_price(ticker, region, date_t_minus_1m)
           price_t_minus_12m = self.db.get_price(ticker, region, date_t_minus_12m)

           if price_t_minus_12m is None or price_t_minus_12m == 0:
               return np.nan

           return (price_t_minus_1m - price_t_minus_12m) / price_t_minus_12m * 100

       def get_win_rate(self) -> float:
           return 0.65  # Highest win rate among all factors
   ```

2. **RSI Factor** (2 hours)
3. **52-Week High Proximity** (2 hours)
4. **MACD Factor** (2 hours)
5. **Test Momentum Factors** (2 hours)

**Deliverables**:
- ✅ 6 momentum factors implemented
- ✅ Backtesting validation (win rate ~65%)

---

### Day 7-8: Quality & Low-Vol Factors

**Tasks**:

1. **Quality Factors** (6 hours)
   - ROE (Return on Equity)
   - Debt-to-Equity Ratio
   - Earnings Quality
   - Margin Stability
   - FCF Consistency
   - Revenue Growth

2. **Low-Volatility Factors** (4 hours)
   - Historical Volatility
   - Beta
   - Max Drawdown
   - Downside Deviation
   - CVaR

**Deliverables**:
- ✅ 11 quality & low-vol factors implemented
- ✅ Performance validation

---

### Day 9: Size Factors & Factor Combiner

**Tasks**:

1. **Size Factors** (3 hours)
   - Market Cap
   - Trading Volume
   - Free Float
   - Turnover Ratio
   - Dollar Volume

2. **Factor Combiner** (5 hours)
   ```python
   # modules/factors/factor_combiner.py
   class FactorCombiner:
       """Combine multiple factors into a single score."""

       def __init__(self, method='equal_weight'):
           self.method = method  # 'equal_weight', 'performance_weight', 'optimization'

       def combine(self, factor_scores: pd.DataFrame) -> pd.Series:
           """
           Combine factor scores into composite score.

           Args:
               factor_scores: DataFrame with stocks × factors

           Returns:
               Series of composite scores (0-100 scale)
           """
           if self.method == 'equal_weight':
               return factor_scores.mean(axis=1) * 10 + 50

           elif self.method == 'performance_weight':
               # Weight by historical Sharpe ratios
               weights = self._get_performance_weights(factor_scores.columns)
               return (factor_scores @ weights) * 10 + 50

           elif self.method == 'optimization':
               # Optimize weights using Markowitz
               weights = self._optimize_weights(factor_scores)
               return (factor_scores @ weights) * 10 + 50
   ```

**Deliverables**:
- ✅ 5 size factors implemented
- ✅ Factor combiner with 3 methods
- ✅ All 27 factors integrated

---

### Day 10: Streamlit Prototype (Parallel Work)

**Tasks**:

1. **Create Streamlit App** (6 hours)
   ```python
   # app/streamlit_app.py
   import streamlit as st
   import pandas as pd
   import plotly.express as px

   st.set_page_config(page_title="Quant Platform", layout="wide")

   # Sidebar
   st.sidebar.title("Quant Investment Platform")
   page = st.sidebar.selectbox("Page", ["Overview", "Factors", "Backtests", "Portfolio", "Risk"])

   if page == "Overview":
       st.title("📊 Platform Overview")
       col1, col2, col3 = st.columns(3)
       col1.metric("Total Strategies", "5")
       col2.metric("Avg Sharpe Ratio", "1.8")
       col3.metric("Total Return YTD", "15.2%")

   elif page == "Factors":
       st.title("🔍 Factor Analysis")

       # Factor scores table
       factor_scores = load_factor_scores()  # Mock data for now
       st.dataframe(factor_scores)

       # Factor performance chart
       fig = px.bar(factor_scores, x='Factor', y='Sharpe_Ratio', title="Factor Performance")
       st.plotly_chart(fig)
   ```

2. **Create 5 Pages** (2 hours)
   - Overview: Platform metrics
   - Factors: Factor analysis and scores
   - Backtests: Backtest results and comparisons
   - Portfolio: Current portfolio and performance
   - Risk: Risk metrics and stress tests

**Deliverables**:
- ✅ Streamlit app with 5 pages
- ✅ Mock data for visualization
- ✅ Local deployment ready

---

### Week 2-3 Summary

**Completed Deliverables**:
- ✅ Factor base infrastructure (`FactorBase`, `FactorCalculator`, `FactorCombiner`)
- ✅ 27 factors implemented across 5 categories
- ✅ Historical performance validation (win rates, Sharpe ratios)
- ✅ Streamlit prototype with 5 pages
- ✅ Factor analysis dashboard operational

**Validation Checklist**:
```bash
# Test factor calculations
pytest tests/test_factors.py -v

# Verify factor scores in database
psql -d quant_platform -c "SELECT COUNT(*) FROM factor_scores;"

# Run Streamlit app
streamlit run app/streamlit_app.py
```

---

## Phase 3: Backtesting Engine (Week 4-5)

**Duration**: 10 days
**Goal**: Production-ready backtesting framework with walk-forward validation

### Day 1-2: Backtrader Integration

**Tasks**:

1. **Install Backtrader** (30 minutes)
   ```bash
   pip install backtrader matplotlib
   ```

2. **Create Strategy Base Class** (4 hours)
   ```python
   # modules/backtest/strategy_base.py
   import backtrader as bt

   class FactorStrategyBase(bt.Strategy):
       """Base class for factor-based strategies."""

       params = (
           ('min_score', 70),  # Minimum factor score to buy
           ('max_positions', 20),  # Maximum number of positions
           ('rebalance_frequency', 'monthly'),  # Rebalancing frequency
       )

       def __init__(self):
           self.order_list = []
           self.factor_scores = {}

       def next(self):
           """Execute on each bar."""
           # Check if rebalancing is needed
           if self.should_rebalance():
               self.rebalance_portfolio()

       def should_rebalance(self):
           """Determine if rebalancing is needed."""
           if self.params.rebalance_frequency == 'monthly':
               return self.datas[0].datetime.date().day == 1
           return False

       def rebalance_portfolio(self):
           """Rebalance portfolio based on factor scores."""
           # Get top stocks by factor score
           top_stocks = self.get_top_stocks(self.params.min_score, self.params.max_positions)

           # Close positions not in top stocks
           for data in self.datas:
               if data._name not in top_stocks and self.getposition(data).size > 0:
                   self.close(data)

           # Open/adjust positions in top stocks
           target_weight = 1.0 / len(top_stocks)
           for stock in top_stocks:
               data = self.getdatabyname(stock)
               self.order_target_percent(data, target=target_weight)
   ```

3. **Test Basic Strategy** (3 hours)

**Deliverables**:
- ✅ Backtrader installed and configured
- ✅ Strategy base class implemented
- ✅ Basic backtest running successfully

---

### Day 3-4: Transaction Cost Model

**Tasks**:

1. **Implement Almgren-Chriss Model** (6 hours)
   ```python
   # modules/backtest/transaction_cost_model.py
   class AlmgrenChrissModel:
       """Almgren-Chriss market impact model (2000)."""

       def __init__(self, commission_rate=0.00015, k1=0.1, k2=0.5):
           self.commission_rate = commission_rate
           self.k1 = k1  # Permanent impact coefficient
           self.k2 = k2  # Temporary impact coefficient

       def calculate_total_cost(
           self,
           order_size: float,
           price: float,
           avg_daily_volume: float,
           spread: float = None,
           market_cap: float = None
       ):
           """
           Calculate total transaction cost.

           Components:
           1. Commission (fixed percentage)
           2. Market impact (volume-based)
           3. Bid-ask spread

           Returns:
               Dictionary with cost breakdown
           """
           # 1. Commission
           order_value = order_size * price
           commission = order_value * self.commission_rate

           # 2. Market impact (Almgren-Chriss)
           volume_fraction = order_size / avg_daily_volume
           permanent_impact = self.k1 * (volume_fraction ** 0.5) * price
           temporary_impact = self.k2 * volume_fraction * price
           slippage = (permanent_impact + temporary_impact) * order_size

           # 3. Bid-ask spread (estimated if not provided)
           if spread is None:
               if market_cap is not None:
                   spread = (0.001 / np.sqrt(market_cap / 1e9)) * price
               else:
                   spread = 0.001 * price
           spread_cost = order_size * spread / 2

           total = commission + slippage + spread_cost

           return {
               'commission': commission,
               'slippage': slippage,
               'spread_cost': spread_cost,
               'total_cost': total,
               'cost_bps': (total / order_value) * 10000  # Basis points
           }
   ```

2. **Integrate with Backtrader** (4 hours)
   ```python
   # Custom commission class for backtrader
   class AlmgrenChrissCommission(bt.CommInfoBase):
       params = (
           ('commission_rate', 0.00015),
           ('k1', 0.1),
           ('k2', 0.5),
       )

       def _getcommission(self, size, price, pseudoexec):
           """Calculate commission based on Almgren-Chriss model."""
           # Implementation here
           pass
   ```

**Deliverables**:
- ✅ Almgren-Chriss model implemented
- ✅ Backtrader integration complete
- ✅ Transaction cost validation (realistic slippage)

---

### Day 5-7: Walk-Forward Optimization

**Tasks**:

1. **Implement Walk-Forward Framework** (8 hours)
   ```python
   # modules/backtest/walk_forward.py
   class WalkForwardOptimizer:
       """Walk-forward optimization framework."""

       def __init__(
           self,
           strategy_class,
           data_provider,
           train_period_years=3,
           test_period_years=1
       ):
           self.strategy_class = strategy_class
           self.data_provider = data_provider
           self.train_period_years = train_period_years
           self.test_period_years = test_period_years

       def run_walk_forward(self, start_date, end_date):
           """
           Run walk-forward optimization.

           Process:
           1. Train on 3-year window → optimize parameters
           2. Test on 1-year forward period → evaluate performance
           3. Roll window forward 1 year
           4. Repeat until end_date

           Example:
           - 2015-2017: Train → Test 2018
           - 2016-2018: Train → Test 2019
           - 2017-2019: Train → Test 2020
           ...
           """
           results = []
           current_date = pd.to_datetime(start_date)
           end = pd.to_datetime(end_date)

           while current_date + pd.DateOffset(
               years=self.train_period_years + self.test_period_years
           ) <= end:
               # Define train and test windows
               train_start = current_date
               train_end = current_date + pd.DateOffset(years=self.train_period_years)
               test_start = train_end
               test_end = test_start + pd.DateOffset(years=self.test_period_years)

               # Optimize on in-sample data
               best_params = self._optimize_in_sample(train_start, train_end)

               # Test on out-of-sample data
               oos_result = self._backtest_out_of_sample(
                   best_params, test_start, test_end
               )

               results.append({
                   'train_period': f"{train_start.date()} to {train_end.date()}",
                   'test_period': f"{test_start.date()} to {test_end.date()}",
                   'best_params': best_params,
                   'oos_sharpe': oos_result['sharpe_ratio'],
                   'oos_return': oos_result['total_return'],
                   'oos_drawdown': oos_result['max_drawdown']
               })

               # Roll forward
               current_date = test_start

           return pd.DataFrame(results)

       def _optimize_in_sample(self, start_date, end_date):
           """Optimize strategy parameters on in-sample data."""
           # Grid search over parameter space
           best_sharpe = -np.inf
           best_params = None

           for min_score in [60, 65, 70, 75]:
               for max_positions in [10, 15, 20, 25]:
                   params = {
                       'min_score': min_score,
                       'max_positions': max_positions
                   }

                   result = self._backtest(params, start_date, end_date)

                   if result['sharpe_ratio'] > best_sharpe:
                       best_sharpe = result['sharpe_ratio']
                       best_params = params

           return best_params
   ```

2. **Test Walk-Forward** (6 hours)
   - Use 5 years of historical data (2019-2024)
   - Validate out-of-sample Sharpe > 0.8 × in-sample

**Deliverables**:
- ✅ Walk-forward framework operational
- ✅ 5-year backtest completed
- ✅ Out-of-sample validation passed

---

### Day 8-9: Multiple Framework Support

**Tasks**:

1. **Add Zipline Support** (6 hours)
2. **Add Vectorbt Support** (4 hours)
3. **Create Framework Comparison** (4 hours)

**Deliverables**:
- ✅ 3 backtesting frameworks integrated
- ✅ Performance comparison report

---

### Day 10: Backtest Analysis & Reporting

**Tasks**:

1. **Performance Metrics Calculator** (4 hours)
   ```python
   # modules/backtest/performance_metrics.py
   def calculate_performance_metrics(returns: pd.Series) -> Dict:
       """Calculate comprehensive performance metrics."""
       total_return = (1 + returns).prod() - 1
       annual_return = (1 + total_return) ** (252 / len(returns)) - 1
       volatility = returns.std() * np.sqrt(252)
       sharpe_ratio = annual_return / volatility if volatility > 0 else 0

       # Max drawdown
       cumulative = (1 + returns).cumprod()
       running_max = cumulative.cummax()
       drawdown = (cumulative - running_max) / running_max
       max_drawdown = drawdown.min()

       return {
           'total_return': total_return,
           'annual_return': annual_return,
           'volatility': volatility,
           'sharpe_ratio': sharpe_ratio,
           'max_drawdown': max_drawdown
       }
   ```

2. **Create Backtest Report Generator** (4 hours)

**Deliverables**:
- ✅ Performance metrics module
- ✅ Automated report generation

---

### Week 4-5 Summary

**Completed Deliverables**:
- ✅ Backtrader, zipline, vectorbt integrated
- ✅ Almgren-Chriss transaction cost model
- ✅ Walk-forward optimization framework
- ✅ 5-year backtest validation
- ✅ Performance reporting automated

**Validation Checklist**:
```bash
# Run backtest
python3 modules/backtest/run_backtest.py --strategy FactorStrategy --start 2019-01-01 --end 2024-12-31

# Validate results
pytest tests/test_backtesting.py -v

# Check database
psql -d quant_platform -c "SELECT COUNT(*) FROM backtest_results;"
```

---

## Phase 4: Portfolio Optimizer (Week 6)

**Duration**: 5 days
**Goal**: 4 optimization methods operational (Markowitz, Risk Parity, Black-Litterman, Kelly)

### Day 1-2: Mean-Variance Optimization

**Tasks**:

1. **Install cvxpy** (30 minutes)
   ```bash
   pip install cvxpy scipy
   ```

2. **Implement Markowitz Optimizer** (6 hours)
   ```python
   # See OPTIMIZATION_COOKBOOK.md Section 2.2 for complete implementation
   # modules/optimization/markowitz.py
   import cvxpy as cp

   class MarkowitzOptimizer:
       def optimize(self, returns, target_return=None, max_weight=0.20):
           """Optimize portfolio using Mean-Variance approach."""
           # Implementation from OPTIMIZATION_COOKBOOK.md
           pass
   ```

3. **Test with Historical Data** (3 hours)

**Deliverables**:
- ✅ Markowitz optimizer implemented
- ✅ Efficient frontier calculation
- ✅ Max Sharpe portfolio finder

---

### Day 3: Risk Parity

**Tasks**:

1. **Implement Risk Parity** (5 hours)
   ```python
   # modules/optimization/risk_parity.py
   class RiskParityOptimizer:
       """Equal risk contribution portfolio."""
       # See OPTIMIZATION_COOKBOOK.md Section 3
   ```

2. **Validate Equal Risk Contribution** (3 hours)

**Deliverables**:
- ✅ Risk Parity optimizer working
- ✅ Risk contribution validated (<5% deviation)

---

### Day 4: Black-Litterman Model

**Tasks**:

1. **Implement Black-Litterman** (6 hours)
   ```python
   # modules/optimization/black_litterman.py
   # See OPTIMIZATION_COOKBOOK.md Section 4
   ```

2. **Test with Investor Views** (2 hours)

**Deliverables**:
- ✅ Black-Litterman with view integration
- ✅ Posterior returns calculation

---

### Day 5: Kelly Criterion & Integration

**Tasks**:

1. **Implement Kelly Multi-Asset** (4 hours)
2. **Create Optimizer Selector** (4 hours)
   ```python
   # modules/optimization/optimizer_selector.py
   class OptimizerSelector:
       """Select optimal portfolio optimizer based on criteria."""

       def select_optimizer(self, market_conditions):
           if market_conditions['volatility'] > 0.30:
               return RiskParityOptimizer()
           elif market_conditions['trend'] == 'strong_uptrend':
               return KellyCriterionOptimizer(kelly_fraction=0.5)
           else:
               return MarkowitzOptimizer()
   ```

**Deliverables**:
- ✅ Kelly Criterion operational
- ✅ Optimizer selector working
- ✅ All 4 methods integrated

---

### Week 6 Summary

**Completed Deliverables**:
- ✅ Mean-Variance (Markowitz) optimizer
- ✅ Risk Parity optimizer
- ✅ Black-Litterman with views
- ✅ Kelly Criterion multi-asset
- ✅ Optimizer comparison framework

**Validation Checklist**:
```bash
# Test optimizers
pytest tests/test_optimization.py -v

# Run comparison
python3 modules/optimization/compare_optimizers.py
```

---

## Phase 5: Risk Management (Week 7)

**Duration**: 5 days
**Goal**: Comprehensive risk framework (VaR/CVaR, stress testing, liquidity risk)

### Day 1-2: VaR/CVaR Implementation

**Tasks**:

1. **Historical VaR** (3 hours)
2. **Parametric VaR** (3 hours)
3. **Monte Carlo VaR** (4 hours)
4. **CVaR (Expected Shortfall)** (2 hours)

**Deliverables**:
- ✅ 3 VaR methods implemented
- ✅ CVaR calculator

---

### Day 3-4: Stress Testing

**Tasks**:

1. **Historical Scenarios** (6 hours)
   - 2008 Financial Crisis (-50% equity, correlation → 0.9)
   - 2020 COVID Crash (-35% equity, volatility × 3)
   - 2022 Bear Market (-25% equity, rate shock +3%)

2. **Hypothetical Scenarios** (4 hours)
   - Flash crash, sector rotation, correlation breakdown

**Deliverables**:
- ✅ 6 stress test scenarios
- ✅ Portfolio impact analysis

---

### Day 5: Liquidity Risk & Integration

**Tasks**:

1. **Liquidity Risk Model** (4 hours)
2. **Risk Dashboard** (4 hours)

**Deliverables**:
- ✅ Liquidity risk scoring
- ✅ Integrated risk framework

---

## Phase 6: Web Interface (Week 8)

**Duration**: 5 days (Parallel: Streamlit + FastAPI)
**Goal**: Production-ready web interface

### Streamlit Dashboard (5 pages)

1. **Overview Page** (1 day)
2. **Factor Analysis Page** (1 day)
3. **Backtesting Page** (1 day)
4. **Portfolio Page** (1 day)
5. **Risk Management Page** (1 day)

### FastAPI Backend (Parallel)

1. **CRUD Endpoints** (3 days)
2. **Authentication** (2 days)

**Deliverables**:
- ✅ Streamlit dashboard (5 pages)
- ✅ FastAPI backend (REST API)
- ✅ Local deployment ready

---

## Phase 7: Testing & Validation (Week 9)

**Duration**: 5 days
**Goal**: >80% test coverage

### Testing Plan

1. **Unit Tests** (3 days)
   - Factor calculations
   - Optimization algorithms
   - Risk metrics

2. **Integration Tests** (2 days)
   - End-to-end backtesting
   - Database operations
   - API endpoints

**Deliverables**:
- ✅ 80%+ test coverage
- ✅ All critical paths tested

---

## Phase 8: Production Deployment (Week 10)

**Duration**: 5 days
**Goal**: Production-ready deployment

### Deployment Checklist

1. **CI/CD Pipeline** (2 days)
   - GitHub Actions setup
   - Automated testing
   - Docker containerization

2. **Production Database** (2 days)
   - AWS RDS PostgreSQL
   - Backup automation
   - Performance tuning

3. **Monitoring** (1 day)
   - Prometheus + Grafana
   - Alert configuration

**Deliverables**:
- ✅ CI/CD operational
- ✅ Production database deployed
- ✅ Monitoring stack active

---

## Progress Tracking

### Weekly Checkpoints

| Week | Phase | Key Deliverable | Status |
|------|-------|----------------|--------|
| 1 | Database Setup | PostgreSQL + TimescaleDB operational | ⏳ |
| 2-3 | Factor Library | 27 factors implemented | ⏳ |
| 4-5 | Backtesting | Walk-forward validation | ⏳ |
| 6 | Optimization | 4 optimizers operational | ⏳ |
| 7 | Risk Management | Stress testing complete | ⏳ |
| 8 | Web Interface | Streamlit + FastAPI deployed | ⏳ |
| 9 | Testing | 80%+ coverage | ⏳ |
| 10 | Production | Deployment complete | ⏳ |

### Success Criteria

✅ **Phase Complete** when:
- All deliverables checked off
- Validation checklist passed
- Tests passing (>80% coverage)
- Documentation updated

---

## Next Steps

**Immediate Actions** (Start Week 1):

```bash
# 1. Setup database
createdb quant_platform
psql -d quant_platform -f docs/sql/database_init.sql

# 2. Run migration
python3 scripts/migrate_sqlite_to_postgres.py

# 3. Verify setup
psql -d quant_platform -c "SELECT * FROM timescaledb_information.hypertables;"

# 4. Start factor implementation
pytest tests/test_factors.py -v
```

**Weekly Reporting**:
- Create `docs/weekly_reports/WEEKN_REPORT.md` at end of each week
- Include: Completed deliverables, blockers, next week plan

**Communication**:
- Daily standups (async via Slack/Discord)
- Weekly review meetings (30 min)
- Monthly retrospectives

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-19
**Next Review**: End of Week 1 (Database Setup Phase)
