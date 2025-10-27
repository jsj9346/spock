# Quant Platform Implementation Design

**Project**: Systematic Quantitative Research Platform
**Timeline**: 12 weeks (9 phases)
**Start Date**: 2025-10-23
**Target Completion**: 2026-01-15
**Version**: 1.0.0
**Status**: Design Complete → Implementation Ready

---

## Executive Summary

This document provides a comprehensive implementation plan for transitioning from the Spock trading system to a full-featured Quantitative Investment Platform focused on quantitative research, backtesting, and portfolio optimization.

### Strategic Decision: Why Quant Platform?

**Problem**: Spock Trading System is 80% complete but limited by:
- 250-day data retention (SQLite constraint)
- Single-stock signal focus (no portfolio optimization)
- Real-time trading focus (limited research capabilities)
- No factor validation framework

**Solution**: Build comprehensive Quant Platform with:
- Unlimited historical data (PostgreSQL + TimescaleDB)
- Multi-factor analysis engine
- Portfolio-level optimization and risk management
- Research-driven strategy development workflow

### Code Reuse Strategy (70% Reuse from Spock)

**Reusable Components**:
- ✅ Data collection infrastructure (KIS API clients, market adapters, parsers)
- ✅ Technical analysis modules (MA, RSI, MACD, Bollinger Bands)
- ✅ Risk management (Kelly calculator, ATR position sizing)
- ✅ Monitoring stack (Prometheus + Grafana)

**New Components (30%)**:
- Database migration to PostgreSQL + TimescaleDB
- Factor analyzer and correlation analyzer
- Unified backtesting interface
- Streamlit dashboard and FastAPI backend

### 12-Week Timeline Overview

| Phase | Duration | Focus Area | Key Deliverables |
|-------|----------|------------|------------------|
| Phase 1 | Week 1 | Database Migration | PostgreSQL schema, data migration (700K+ rows) |
| Phase 2 | Week 2-3 | Factor Library Enhancement | Enhanced factors, factor analyzer, correlation analyzer |
| Phase 3 | Week 4-5 | Backtesting Integration | Unified interface, transaction cost model, performance metrics |
| Phase 4 | Week 6 | Portfolio Optimization | Mean-variance, risk parity, Black-Litterman, Kelly multi-asset |
| Phase 5 | Week 7 | Risk Management | VaR/CVaR calculators, stress testing, exposure tracking |
| Phase 6 | Week 8-9 | Web Interface | Streamlit dashboard (5 pages) |
| Phase 7 | Week 10 | API Layer | FastAPI backend (6 route modules) |
| Phase 8 | Week 11 | Testing & Documentation | Unit tests, integration tests, comprehensive docs |
| Phase 9 | Week 12 | Production Readiness | CI/CD, monitoring, deployment automation |

### Success Criteria

**Technical Metrics**:
- Database query: <1s for 10-year OHLCV data retrieval
- Backtest speed: <30s for 5-year simulation (100 stocks)
- Portfolio optimization: <60s for 100-asset mean-variance
- API latency: <200ms (p95) for all endpoints
- Dashboard load: <3s initial page load

**Research Metrics**:
- Factor library: 20+ factors across 5 categories (Value, Momentum, Quality, Low-Vol, Size)
- Factor IC (Information Coefficient): >0.05 for strong factors
- Factor independence: Correlation <0.5 between factors
- Backtesting: >100 trades per strategy for statistical significance
- Portfolio optimization: 6+ methods supported

**Development Metrics**:
- Code coverage: >80% for core modules
- Documentation: 100% API documentation
- Deployment: One-click deployment to production

---

## System Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                       │
│  ┌────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Streamlit Dashboard│  │      FastAPI REST API             │   │
│  │ - Strategy Builder │  │  - Strategy CRUD                  │   │
│  │ - Backtest Results │  │  - Backtest Execution             │   │
│  │ - Portfolio Analytics│ │  - Portfolio Optimization        │   │
│  │ - Factor Analysis  │  │  - Risk Analysis                  │   │
│  │ - Risk Dashboard   │  │  - Data Retrieval                 │   │
│  └────────────────────┘  └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────┐
│                     Application Logic Layer                        │
│  ┌──────────────────┬───────────────────┬─────────────────────┐  │
│  │ Multi-Factor     │  Backtesting      │  Portfolio Optimizer│  │
│  │ Analysis Engine  │  Engine           │                     │  │
│  │                  │                   │                     │  │
│  │ - Value Factors  │  - backtrader     │  - Mean-Variance    │  │
│  │ - Momentum       │  - zipline        │  - Risk Parity      │  │
│  │ - Quality        │  - vectorbt       │  - Black-Litterman  │  │
│  │ - Low-Vol        │  - Transaction    │  - Kelly Multi-Asset│  │
│  │ - Size           │    Cost Model     │  - Constraint Handler│ │
│  │                  │  - Performance    │                     │  │
│  │ - Factor Combiner│    Metrics        │                     │  │
│  └──────────────────┴───────────────────┴─────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────┐
│                      Data Access Layer                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  db_manager_postgres.py                                     │  │
│  │  - Connection pooling                                        │  │
│  │  - Query optimization                                        │  │
│  │  - Transaction management                                    │  │
│  └────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────┐
│          Database Layer (PostgreSQL + TimescaleDB)                 │
│  ┌───────────────────────┬───────────────────────────────────┐   │
│  │  Hypertables          │  Regular Tables                    │   │
│  │  - ohlcv_data         │  - tickers                         │   │
│  │  - factor_scores      │  - strategies                      │   │
│  │  - portfolio_holdings │  - backtest_results                │   │
│  │                       │  - optimization_results            │   │
│  │  Continuous Aggregates│  - risk_metrics                    │   │
│  │  - ohlcv_weekly       │                                    │   │
│  │  - ohlcv_monthly      │                                    │   │
│  │  - factor_stats       │                                    │   │
│  └───────────────────────┴───────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────┐
│           Data Collection Layer (Reused from Spock)                │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Market Adapters (kr_adapter, us_adapter_kis, etc.)       │   │
│  │  API Clients (KIS API, Polygon.io, yfinance)              │   │
│  │  Data Parsers (cn_stock_parser, hk_stock_parser, etc.)    │   │
│  └───────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### Component Interaction Diagram (Example: Strategy Creation and Backtest)

```
User Action: "Create Momentum+Value Strategy"
     │
     ▼
┌──────────────────────────────────────────┐
│  Streamlit Dashboard                      │
│  (pages/1_strategy_builder.py)           │
└──────────────┬───────────────────────────┘
               │ HTTP POST /strategies
               ▼
┌──────────────────────────────────────────┐
│  FastAPI Backend                          │
│  (api/routes/strategy_routes.py)         │
└──────────────┬───────────────────────────┘
               │ StrategyModel validation
               ▼
┌──────────────────────────────────────────┐
│  Multi-Factor Analysis Engine             │
│  (modules/factors/factor_combiner.py)    │
│  - Combine momentum + value factors       │
│  - Set weights: momentum 0.6, value 0.4   │
└──────────────┬───────────────────────────┘
               │ Store strategy definition
               ▼
┌──────────────────────────────────────────┐
│  Database Layer                           │
│  INSERT INTO strategies (...)             │
└──────────────┬───────────────────────────┘
               │ Return strategy_id
               ▼
┌──────────────────────────────────────────┐
│  Backtest Execution                       │
│  POST /backtest?strategy_id=X             │
└──────────────┬───────────────────────────┘
               │ Load historical data
               ▼
┌──────────────────────────────────────────┐
│  Backtesting Engine                       │
│  (modules/backtest/backtest_engine.py)   │
│  - Load OHLCV data from PostgreSQL        │
│  - Calculate factor scores daily          │
│  - Generate buy/sell signals              │
│  - Simulate trades with transaction costs │
└──────────────┬───────────────────────────┘
               │ Performance metrics
               ▼
┌──────────────────────────────────────────┐
│  Results Storage                          │
│  INSERT INTO backtest_results (...)       │
└──────────────┬───────────────────────────┘
               │ Display results
               ▼
┌──────────────────────────────────────────┐
│  Streamlit Dashboard                      │
│  (pages/2_backtest_results.py)           │
│  - Performance chart (cumulative returns) │
│  - Drawdown chart                         │
│  - Metrics table (Sharpe, Sortino, etc.) │
└──────────────────────────────────────────┘
```

---

## Phase 1: Database Migration (Week 1)

**Objective**: Migrate from SQLite (250-day retention) to PostgreSQL + TimescaleDB (unlimited retention)

### Timeline Breakdown

**Days 1-2**: PostgreSQL + TimescaleDB Setup
- Install PostgreSQL 17 and TimescaleDB 2.11+ extension
- Configure database server (connection limits, memory settings)
- Create `quant_platform` database
- Enable TimescaleDB extension

**Days 3-5**: Schema Design and Data Migration
- Implement complete PostgreSQL schema with hypertables
- Develop migration script from SQLite to PostgreSQL
- Run migration and validate data integrity (expected: 700K+ rows)
- Create continuous aggregates for weekly/monthly data

### Database Schema Design

**Full schema** located at: `scripts/init_postgres_schema.sql`

**Key Tables**:

1. **ohlcv_data** (Hypertable - TimescaleDB)
   - Unlimited historical price data
   - Automatic compression after 1 year (10x space savings)
   - Continuous aggregates for weekly/monthly views

2. **factor_scores** (Hypertable)
   - Factor scores for all stocks, all dates
   - Supports z-scores, percentiles, raw values
   - Enables fast factor analysis queries

3. **portfolio_holdings** (Hypertable)
   - Portfolio composition over time
   - Supports rebalancing analysis
   - Tracks cost basis and unrealized P&L

4. **strategies** (Regular Table)
   - Strategy definitions (factor weights, constraints)
   - JSONB storage for flexible configuration

5. **backtest_results** (Regular Table)
   - Complete backtest performance metrics
   - JSONB storage for detailed trade logs

6. **optimization_results** (Regular Table)
   - Portfolio optimization results
   - Efficient frontier data

7. **risk_metrics** (Regular Table)
   - VaR, CVaR, stress test results
   - Portfolio risk tracking over time

**Sample Schema (Key Parts)**:

```sql
-- Hypertable for OHLCV data
CREATE TABLE ohlcv_data (
    id BIGSERIAL,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    timeframe VARCHAR(10) DEFAULT '1d',
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    close DECIMAL(15, 4),
    volume BIGINT,
    adj_close DECIMAL(15, 4),
    split_factor DECIMAL(10, 4) DEFAULT 1.0,
    dividend DECIMAL(10, 4) DEFAULT 0.0,
    PRIMARY KEY (ticker, region, date, timeframe)
);

SELECT create_hypertable('ohlcv_data', 'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region',
    timescaledb.compress_orderby = 'date DESC'
);

-- Automatic compression policy
SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days');

-- Continuous aggregate for monthly data
CREATE MATERIALIZED VIEW ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT ticker, region,
       time_bucket('1 month', date) AS month_start,
       first(open, date) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close, date) AS close,
       sum(volume) AS volume
FROM ohlcv_data
GROUP BY ticker, region, month_start;

-- Refresh policy
SELECT add_continuous_aggregate_policy('ohlcv_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day'
);
```

### Migration Script Design

**File**: `scripts/migrate_from_sqlite_to_postgres.py`

**Key Features**:
- Batch processing (10,000 rows per batch) for memory efficiency
- Progress tracking with percentage complete
- Data validation (row counts, date ranges, sample data spot checks)
- Rollback capability on failure

**Sample Migration Code**:

```python
class SQLiteToPostgresMigrator:
    def __init__(self, sqlite_path: str, postgres_conn_str: str):
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.pg_conn = psycopg2.connect(postgres_conn_str)
        self.pg_cursor = self.pg_conn.cursor()

    def migrate_ohlcv_data(self, batch_size: int = 10000) -> int:
        """Migrate OHLCV data in batches"""
        total_rows = self.sqlite_conn.execute(
            "SELECT COUNT(*) FROM ohlcv_data"
        ).fetchone()[0]

        offset = 0
        total_migrated = 0

        while offset < total_rows:
            df = pd.read_sql_query(f"""
                SELECT ticker, region, date, timeframe,
                       open, high, low, close, volume,
                       adj_close, split_factor, dividend
                FROM ohlcv_data
                ORDER BY date
                LIMIT {batch_size} OFFSET {offset}
            """, self.sqlite_conn)

            if df.empty:
                break

            insert_query = """
                INSERT INTO ohlcv_data (...)
                VALUES (%s, %s, ...)
                ON CONFLICT (ticker, region, date, timeframe) DO UPDATE SET ...
            """

            execute_batch(self.pg_cursor, insert_query,
                         [tuple(row) for row in df.values],
                         page_size=1000)
            self.pg_conn.commit()

            total_migrated += len(df)
            offset += batch_size

            progress_pct = (total_migrated / total_rows) * 100
            logger.info(f"Progress: {total_migrated:,}/{total_rows:,} ({progress_pct:.1f}%)")

        return total_migrated

    def validate_migration(self) -> Dict[str, bool]:
        """Validate migration integrity"""
        results = {}

        # Check row counts
        sqlite_count = self.sqlite_conn.execute(
            "SELECT COUNT(*) FROM ohlcv_data"
        ).fetchone()[0]

        self.pg_cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        pg_count = self.pg_cursor.fetchone()[0]

        results['row_count_match'] = (sqlite_count == pg_count)

        # Check date ranges
        sqlite_date_range = self.sqlite_conn.execute(
            "SELECT MIN(date), MAX(date) FROM ohlcv_data"
        ).fetchone()

        self.pg_cursor.execute("SELECT MIN(date), MAX(date) FROM ohlcv_data")
        pg_date_range = self.pg_cursor.fetchone()

        results['date_range_match'] = (sqlite_date_range == pg_date_range)

        # Spot check 100 random rows
        sample_data = pd.read_sql_query("""
            SELECT ticker, region, date, close
            FROM ohlcv_data
            ORDER BY RANDOM()
            LIMIT 100
        """, self.sqlite_conn)

        mismatches = 0
        for _, row in sample_data.iterrows():
            self.pg_cursor.execute("""
                SELECT close FROM ohlcv_data
                WHERE ticker = %s AND region = %s AND date = %s
            """, (row['ticker'], row['region'], row['date']))

            pg_close = self.pg_cursor.fetchone()
            if pg_close is None or abs(float(pg_close[0]) - row['close']) > 0.01:
                mismatches += 1

        results['data_integrity'] = (mismatches == 0)

        return results
```

### Validation Criteria

**Data Integrity Checks**:
1. Row counts match 100% between SQLite and PostgreSQL
2. Date ranges match (earliest and latest dates)
3. Sample data spot checks (100 random rows, <1% error tolerance)
4. No NULL values in critical columns (ticker, region, date, close)

**Performance Validation**:
1. Query performance: <1s for 10-year OHLCV data retrieval
2. Insertion performance: >10,000 rows/second during migration
3. Compression ratio: >10x space savings after compression

**Success Metrics**:
- Migration completes in <2 hours for 700K+ rows
- Zero data loss (100% row count match)
- All validation checks pass

---

## Phase 2: Factor Library Enhancement (Week 2-3)

**Objective**: Enhance existing factor modules with missing factors and add factor analysis tools

### Timeline Breakdown

**Days 1-3**: Factor Enhancements
- Add Dividend Yield and Free Cash Flow Yield to `value_factors.py`
- Add Earnings Momentum to `momentum_factors.py`
- Add Earnings Quality (Accruals) to `quality_factors.py`
- Update `factor_score_calculator.py` to use enhanced factors

**Days 4-7**: Factor Analyzer Implementation
- Implement `FactorAnalyzer` class for historical performance analysis
- Calculate quintile returns, Information Coefficient (IC), factor decay
- Generate factor performance reports with visualization

**Days 8-10**: Factor Correlation Analyzer
- Implement `FactorCorrelationAnalyzer` class
- Calculate pairwise factor correlations
- Identify redundant factors (correlation >0.7)
- Generate correlation heatmaps

### Enhanced Value Factors

**File**: `modules/factors/value_factors.py`

**New Factors**:
1. **Dividend Yield**
   - Formula: `Annual Dividends per Share / Current Price * 100`
   - Scoring: >5% = 100pts, 3-5% = 80pts, 1-3% = 60pts, <1% = 40pts, No dividend = 20pts

2. **Free Cash Flow (FCF) Yield**
   - Formula: `Free Cash Flow / Market Cap * 100`
   - Scoring: >10% = 100pts, 5-10% = 80pts, 2-5% = 60pts, 0-2% = 40pts, Negative = 20pts

**Sample Code**:

```python
class ValueFactors(FactorBase):
    def calculate_dividend_yield_score(self, ticker: str, region: str, date: str) -> float:
        """Calculate dividend yield score"""
        # Fetch annual dividends (sum of last 12 months)
        query = """
            SELECT SUM(dividend) as annual_dividend
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
              AND date BETWEEN %s::date - INTERVAL '12 months' AND %s::date
        """
        result = self.db_manager.execute_query(query, (ticker, region, date, date))
        annual_dividend = result[0]['annual_dividend'] if result else 0.0

        # Fetch current price
        price_query = """
            SELECT close FROM ohlcv_data
            WHERE ticker = %s AND region = %s AND date = %s
        """
        price_result = self.db_manager.execute_query(price_query, (ticker, region, date))
        current_price = price_result[0]['close'] if price_result else None

        if not current_price or current_price <= 0:
            return 0.0

        # Calculate yield
        dividend_yield = (annual_dividend / current_price) * 100

        # Score based on yield
        if dividend_yield >= 5.0:
            score = 100
        elif dividend_yield >= 3.0:
            score = 80
        elif dividend_yield >= 1.0:
            score = 60
        elif dividend_yield > 0:
            score = 40
        else:
            score = 20

        return score
```

### Factor Analyzer Implementation

**File**: `modules/factors/factor_analyzer.py`

**Key Features**:
1. **Quintile Returns Analysis**
   - Sort stocks by factor score into quintiles (Q1-Q5)
   - Calculate forward returns for each quintile
   - Measure spread (Q5 - Q1) to assess factor effectiveness
   - Target: Spread >5% annually

2. **Information Coefficient (IC)**
   - Correlation between factor score and forward return
   - Target: IC >0.05 for strong factors, >50% positive months

3. **Factor Decay Analysis**
   - Measure signal decay over different holding periods
   - Identify optimal rebalancing frequency

**Sample Code**:

```python
class FactorAnalyzer:
    def calculate_factor_returns(self, factor_name: str, start_date: str, end_date: str,
                                 quintiles: int = 5, holding_period: int = 20) -> pd.DataFrame:
        """Calculate quintile returns for a factor"""
        # Fetch factor scores and forward returns
        query = """
            SELECT fs.ticker, fs.region, fs.date, fs.score,
                   o1.close as current_price,
                   o2.close as future_price
            FROM factor_scores fs
            JOIN ohlcv_data o1 ON fs.ticker = o1.ticker AND fs.date = o1.date
            LEFT JOIN ohlcv_data o2 ON fs.ticker = o2.ticker
                AND o2.date = fs.date + INTERVAL '%s days'
            WHERE fs.factor_name = %s AND fs.date BETWEEN %s AND %s
        """

        df = pd.read_sql_query(query, self.db_manager.get_connection(),
                               params=(holding_period, factor_name, start_date, end_date))

        # Calculate forward return
        df['forward_return'] = (df['future_price'] - df['current_price']) / df['current_price']
        df = df.dropna(subset=['future_price'])

        # Calculate quintiles for each date
        results = []
        for date, group in df.groupby('date'):
            group['quintile'] = pd.qcut(group['score'], q=quintiles, labels=False, duplicates='drop') + 1
            quintile_returns = group.groupby('quintile').agg({
                'forward_return': 'mean',
                'ticker': 'count'
            }).reset_index()
            quintile_returns['date'] = date
            results.append(quintile_returns)

        result_df = pd.concat(results, ignore_index=True)

        # Calculate summary
        summary = result_df.groupby('quintile').agg({
            'avg_return': ['mean', 'std'],
            'num_stocks': 'mean'
        })

        # Calculate spread
        q5_return = summary.loc[5, 'avg_return']['mean']
        q1_return = summary.loc[1, 'avg_return']['mean']
        spread = q5_return - q1_return

        print(f"\nFactor Spread (Q5 - Q1): {spread*100:.2f}%")
        print(f"Annualized Spread: {(spread * 252 / holding_period) * 100:.2f}%")

        return result_df

    def calculate_information_coefficient(self, factor_name: str,
                                         start_date: str, end_date: str,
                                         holding_period: int = 20) -> Dict:
        """Calculate IC (correlation between factor score and forward return)"""
        # Fetch data
        query = """
            SELECT fs.date, fs.ticker, fs.score,
                   o1.close as current_price,
                   o2.close as future_price
            FROM factor_scores fs
            JOIN ohlcv_data o1 ON fs.ticker = o1.ticker AND fs.date = o1.date
            LEFT JOIN ohlcv_data o2 ON fs.ticker = o2.ticker
                AND o2.date = fs.date + INTERVAL '%s days'
            WHERE fs.factor_name = %s AND fs.date BETWEEN %s AND %s
        """

        df = pd.read_sql_query(query, self.db_manager.get_connection(),
                               params=(holding_period, factor_name, start_date, end_date))

        df['forward_return'] = (df['future_price'] - df['current_price']) / df['current_price']
        df = df.dropna(subset=['future_price'])

        # Calculate monthly IC
        df['year_month'] = pd.to_datetime(df['date']).dt.to_period('M')

        monthly_ics = []
        for period, group in df.groupby('year_month'):
            ic, _ = stats.spearmanr(group['score'], group['forward_return'])
            monthly_ics.append({
                'period': str(period),
                'ic': ic,
                'num_stocks': len(group)
            })

        ic_df = pd.DataFrame(monthly_ics)

        result = {
            'mean_ic': ic_df['ic'].mean(),
            'ic_std': ic_df['ic'].std(),
            'pct_positive': (ic_df['ic'] > 0).sum() / len(ic_df) * 100,
            'monthly_ic': ic_df.to_dict('records')
        }

        return result
```

### Factor Correlation Analyzer

**File**: `modules/factors/factor_correlation_analyzer.py`

**Key Features**:
1. **Correlation Matrix Calculation**
   - Spearman rank correlation between all factor pairs
   - Target: Correlation <0.5 for factor independence

2. **Redundancy Detection**
   - Identify highly correlated factor pairs (correlation >0.7)
   - Recommend factor subset with low correlations

3. **Visualization**
   - Interactive correlation heatmap (Plotly)
   - Export to HTML for sharing

**Sample Code**:

```python
class FactorCorrelationAnalyzer:
    def calculate_factor_correlations(self, factor_names: List[str],
                                     start_date: str, end_date: str) -> pd.DataFrame:
        """Calculate pairwise correlations between factors"""
        query = """
            SELECT ticker, region, date, factor_name, score
            FROM factor_scores
            WHERE factor_name = ANY(%s) AND date BETWEEN %s AND %s
        """

        df = pd.read_sql_query(query, self.db_manager.get_connection(),
                               params=(factor_names, start_date, end_date))

        # Pivot to wide format
        pivot_df = df.pivot_table(
            index=['ticker', 'region', 'date'],
            columns='factor_name',
            values='score'
        ).reset_index()

        # Calculate correlation matrix
        corr_matrix = pivot_df[factor_names].corr(method='spearman')

        # Identify highly correlated pairs
        high_corr_pairs = []
        for i in range(len(factor_names)):
            for j in range(i+1, len(factor_names)):
                corr = corr_matrix.iloc[i, j]
                if abs(corr) > 0.7:
                    high_corr_pairs.append({
                        'factor_1': factor_names[i],
                        'factor_2': factor_names[j],
                        'correlation': corr
                    })

        if not high_corr_pairs:
            print("✓ No highly correlated pairs (good diversification)")
        else:
            print(f"⚠ Found {len(high_corr_pairs)} highly correlated pairs")

        return corr_matrix

    def recommend_factor_subset(self, corr_matrix: pd.DataFrame,
                               max_correlation: float = 0.5) -> List[str]:
        """Recommend factor subset with low correlations"""
        avg_corr = corr_matrix.abs().mean().sort_values()

        selected_factors = []
        for factor in avg_corr.index:
            if not selected_factors:
                selected_factors.append(factor)
            else:
                max_corr_with_selected = max([
                    abs(corr_matrix.loc[factor, sel])
                    for sel in selected_factors
                ])

                if max_corr_with_selected < max_correlation:
                    selected_factors.append(factor)

        return selected_factors
```

### Validation Criteria (Phase 2)

**Factor Performance Targets**:
- Information Coefficient (IC) > 0.05 for strong factors
- Factor spread (Q5 - Q1) > 5% annually
- >50% positive months for consistent signal
- Factor correlations < 0.5 for independence

**Code Quality**:
- Unit tests for all new factor calculations
- Validation against known values (e.g., dividend yield matches financial statements)
- Performance: Factor calculation <100ms per stock

---

## Phase 3-9: Remaining Phases (Summary)

Due to token limits, full designs for Phases 3-9 are provided in separate documents:

### Phase 3: Backtesting Integration (Week 4-5)
- **Deliverables**: Unified backtesting interface, transaction cost model, performance metrics
- **Success Criteria**: <30s backtest speed for 5-year simulation

### Phase 4: Portfolio Optimization (Week 6)
- **Deliverables**: Mean-variance, risk parity, Black-Litterman, Kelly multi-asset optimizers
- **Success Criteria**: <60s optimization time for 100-asset portfolio

### Phase 5: Risk Management (Week 7)
- **Deliverables**: VaR/CVaR calculators, stress testing, exposure tracking
- **Success Criteria**: <5s VaR calculation

### Phase 6: Web Interface (Week 8-9)
- **Deliverables**: Streamlit dashboard with 5 pages
- **Success Criteria**: <3s dashboard load time

### Phase 7: API Layer (Week 10)
- **Deliverables**: FastAPI backend with 6 route modules
- **Success Criteria**: <200ms API latency (p95)

### Phase 8: Testing & Documentation (Week 11)
- **Deliverables**: Unit tests, integration tests, comprehensive docs
- **Success Criteria**: >80% test coverage

### Phase 9: Production Readiness (Week 12)
- **Deliverables**: CI/CD, monitoring, deployment automation
- **Success Criteria**: One-click deployment, >99.5% uptime

**Complete designs for Phases 3-9** available in:
- `docs/PHASE_3_BACKTESTING_DESIGN.md`
- `docs/PHASE_4_OPTIMIZATION_DESIGN.md`
- `docs/PHASE_5_RISK_DESIGN.md`
- `docs/PHASE_6_UI_DESIGN.md`
- `docs/PHASE_7_API_DESIGN.md`
- `docs/PHASE_8_TESTING_DESIGN.md`
- `docs/PHASE_9_PRODUCTION_DESIGN.md`

---

## Development Timeline (Detailed)

### Week-by-Week Breakdown

| Week | Phase | Key Milestones | Success Metrics |
|------|-------|----------------|-----------------|
| 1 | Phase 1 | PostgreSQL setup, data migration | 700K+ rows migrated, <1s query time |
| 2 | Phase 2.1 | Enhanced factors (Dividend Yield, FCF Yield) | 20+ factors, IC > 0.05 |
| 3 | Phase 2.2 | Factor analyzer, correlation analyzer | Factor reports generated |
| 4 | Phase 3.1 | Unified backtesting interface | 3 frameworks integrated |
| 5 | Phase 3.2 | Transaction cost model, performance metrics | <30s backtest speed |
| 6 | Phase 4 | Portfolio optimization (4 methods) | <60s optimization time |
| 7 | Phase 5 | Risk management (VaR, CVaR, stress tests) | <5s VaR calculation |
| 8 | Phase 6.1 | Streamlit pages 1-3 (Strategy, Backtest, Portfolio) | <3s page load |
| 9 | Phase 6.2 | Streamlit pages 4-5 (Factor, Risk) | Interactive charts <500ms |
| 10 | Phase 7 | FastAPI backend (6 route modules) | <200ms API latency |
| 11 | Phase 8 | Testing, documentation | >80% test coverage |
| 12 | Phase 9 | Production deployment, monitoring | >99.5% uptime |

### Critical Path Dependencies

```
Phase 1 (Database) → Phase 2 (Factors) → Phase 3 (Backtesting) → Phase 6 (Dashboard)
                                     ↓
                              Phase 4 (Optimization)
                                     ↓
                              Phase 5 (Risk)
                                     ↓
                              Phase 7 (API)
                                     ↓
                              Phase 8 (Testing)
                                     ↓
                              Phase 9 (Production)
```

---

## Getting Started

### Prerequisites

```bash
# Install PostgreSQL 17 and TimescaleDB 2.11+
brew install postgresql@17 timescaledb  # macOS
# OR
sudo apt install postgresql-17 timescaledb-postgresql-17  # Ubuntu

# Install Python 3.11+
brew install python@3.11  # macOS
# OR
sudo apt install python3.11  # Ubuntu

# Install Python dependencies
pip3 install -r requirements_quant.txt
```

### Initial Setup

```bash
# 1. Configure PostgreSQL with TimescaleDB
timescaledb-tune --quiet --yes
brew services start postgresql@17  # macOS
# OR
sudo systemctl start postgresql  # Ubuntu

# 2. Create database
createdb quant_platform

# 3. Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 4. Initialize schema (Phase 1)
python3 scripts/init_postgres_schema.py

# 5. Migrate data from Spock (Phase 1)
python3 scripts/migrate_from_sqlite_to_postgres.py \
  --source data/spock_local.db \
  --target postgresql://localhost:5432/quant_platform
```

### Development Workflow

```bash
# Phase 2: Run factor analysis
python3 modules/factors/factor_analyzer.py \
  --factor momentum_12m \
  --start 2020-01-01 \
  --end 2023-12-31

# Phase 3: Run backtest
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000

# Phase 4: Optimize portfolio
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15

# Phase 6: Launch dashboard
streamlit run dashboard/app.py

# Phase 7: Launch API
uvicorn api.main:app --reload --port 8000
```

---

## Appendix A: Technology Stack Rationale

### Database: PostgreSQL + TimescaleDB

**Why PostgreSQL over SQLite**:
- Unlimited data retention (vs 250-day limit)
- Better performance for large datasets (>1M rows)
- Concurrent access support
- Advanced features (CTEs, window functions, JSONB)

**Why TimescaleDB**:
- 10x faster time-series queries
- Automatic compression (10x space savings)
- Continuous aggregates (pre-computed views)
- Built-in time-series functions

### Backtesting: Multiple Frameworks

**backtrader** (Primary): Event-driven, flexible strategies
**zipline** (Secondary): Quantopian-style, institutional-grade
**vectorbt** (Tertiary): 100x faster, ideal for optimization

---

## Appendix B: Code Reuse from Spock (70%)

**Reusable Modules**:
- ✅ Data collection (KIS API clients, market adapters, parsers) - 100% reuse
- ✅ Technical analysis (MA, RSI, MACD, Bollinger Bands) - 90% reuse
- ✅ Risk management (Kelly calculator, optimization, risk modules) - 80% reuse
- ✅ Monitoring (Prometheus + Grafana) - 100% reuse

**New Modules (30%)**:
- Database migration (db_manager_postgres.py)
- Factor analysis (factor_analyzer.py, factor_correlation_analyzer.py)
- Unified backtesting (backtest_engine.py)
- Web interface (Streamlit dashboard, FastAPI backend)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-23
**Status**: Design Complete → Ready for Implementation
**Next Step**: Begin Phase 1 (Database Migration) - Week 1
