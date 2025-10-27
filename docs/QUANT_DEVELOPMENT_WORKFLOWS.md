# Development Workflows - Quant Investment Platform

Comprehensive workflows for all development phases with command examples and best practices.

**Last Updated**: 2025-10-26

---

## Quick Reference

| Workflow | Priority | Est. Time | Prerequisites |
|----------|----------|-----------|---------------|
| [Backtesting Engine Setup](#1-backtesting-engine-setup) | 🎯 Critical | 1-2 weeks | Python 3.11+, PostgreSQL |
| [Database Setup](#2-database-setup) | High | 1 day | PostgreSQL 15+, TimescaleDB |
| [Factor Research](#3-factor-research) | Medium | 2 weeks | Validated engine |
| [Strategy Development](#4-strategy-development) | Medium | 2-3 weeks | Factor library ready |
| [Portfolio Optimization](#5-portfolio-optimization) | Medium | 1 week | Strategy validated |
| [Risk Analysis](#6-risk-analysis) | Medium | 1 week | Portfolio created |

---

## 1. Backtesting Engine Setup

**🎯 HIGHEST PRIORITY - Week 1-2**

Complete backtesting infrastructure before any strategy work.

### Step 1: Install Dependencies

```bash
# Core backtesting engines
pip install vectorbt backtrader zipline-reloaded

# Performance metrics
pip install scipy statsmodels

# Verification
python3 -c "import vectorbt; print(f'vectorbt {vectorbt.__version__}')"
```

### Step 2: Enhance Custom Engine

```bash
# Validate current custom engine
python3 modules/backtest/backtest_engine.py --mode validate

# Run comprehensive tests
python3 tests/test_backtest_engine.py --comprehensive

# Expected output: All tests passing, <30s execution time
```

### Step 3: Integrate vectorbt (Priority 1)

```bash
# Test vectorbt installation
python3 modules/backtest/vectorbt_adapter.py --test-integration

# Run sample backtest
python3 -c "
import vectorbt as vbt
import pandas as pd

# Sample data
data = vbt.YFData.download(['005930.KS'], start='2020-01-01')
print(f'Data shape: {data.close.shape}')

# Simple MA crossover
fast_ma = vbt.MA.run(data.close, 20)
slow_ma = vbt.MA.run(data.close, 50)
entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

# Backtest (instant)
pf = vbt.Portfolio.from_signals(data.close, entries, exits, freq='D')
print(pf.stats())
"

# Expected: Stats printed in <1 second
```

### Step 4: Performance Metrics

```bash
# Test performance metrics calculator
python3 modules/backtest/performance_metrics.py --validate

# Expected metrics:
# - Sharpe ratio
# - Sortino ratio
# - Calmar ratio
# - Max drawdown
# - Win rate
```

### Step 5: Transaction Cost Model

```bash
# Calibrate transaction costs
python3 modules/backtest/transaction_cost_model.py --calibrate

# Test with sample portfolio
python3 modules/backtest/transaction_cost_model.py \
  --commission 0.015 \
  --slippage volume_based \
  --test
```

### Step 6: Validation

```bash
# Comprehensive engine testing
python3 tests/test_backtest_engine.py --comprehensive

# Performance benchmarking
python3 scripts/benchmark_engines.py --compare-all

# Expected output:
# - Custom engine: <30s for 5-year simulation
# - vectorbt: <1s for 5-year simulation
# - >95% accuracy match
```

### Step 7: Documentation

```bash
# Generate API documentation
python3 scripts/generate_docs.py --module backtest

# Verify examples run
python3 examples/example_backtest_workflow.py
```

**Success Criteria**:
- ✅ Custom engine: <30s for 5-year simulation
- ✅ vectorbt: <1s for 5-year simulation
- ✅ >95% accuracy validation
- ✅ All performance metrics auto-calculated

---

## 2. Database Setup

**Infrastructure setup for unlimited historical data**

### Install PostgreSQL + TimescaleDB

```bash
# macOS
brew install postgresql@17 timescaledb

# Ubuntu
sudo apt install postgresql-17 timescaledb-2-postgresql-17

# Configure TimescaleDB
timescaledb-tune --quiet --yes
```

### Create Database

```bash
# Create database
createdb quant_platform

# Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Verify
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"
```

### Initialize Schema

```bash
# Run schema initialization
python3 scripts/init_postgres_schema.py

# Verify tables
psql -d quant_platform -c "\dt"

# Expected tables:
# - ohlcv_data (hypertable)
# - factor_scores
# - strategies
# - backtest_results
# - portfolio_holdings
# - tickers
```

### Migrate Historical Data

```bash
# Migrate from Spock SQLite (if applicable)
python3 scripts/migrate_from_sqlite.py \
  --source data/spock_local.db \
  --dry-run

# Execute migration
python3 scripts/migrate_from_sqlite.py \
  --source data/spock_local.db \
  --execute

# Verify migration
psql -d quant_platform -c "
SELECT region, COUNT(*)
FROM tickers
GROUP BY region
ORDER BY region;
"
```

---

## 3. Factor Research

**After engine validation - Week 5-6**

### Analyze Individual Factors

```bash
# Test momentum factor
python3 modules/factors/factor_analyzer.py \
  --factor momentum \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR

# Test value factor
python3 modules/factors/factor_analyzer.py \
  --factor value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR

# Compare multiple factors
python3 modules/factors/factor_analyzer.py \
  --factors momentum,value,quality \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR \
  --compare
```

### Check Factor Correlations

```bash
# Correlation matrix
python3 modules/factors/factor_correlation.py \
  --factors momentum,value,quality,low_vol,size \
  --start 2018-01-01 \
  --region KR

# Expected: Correlation <0.5 for factor independence
```

### Backtest Single-Factor Strategy

```bash
# Momentum-only strategy
python3 modules/backtest/backtest_engine.py \
  --strategy single_factor \
  --factor momentum \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt

# Expected metrics:
# - Sharpe ratio >1.0
# - >100 trades
```

---

## 4. Strategy Development

**After engine & factors ready - Week 7+**

### Create New Strategy

```bash
# Interactive strategy builder
python3 modules/strategies/strategy_builder.py

# Follow prompts:
# - Strategy name
# - Factor weights
# - Constraints
# - Rebalancing frequency
```

### Backtest Multi-Factor Strategy

```bash
# Momentum + Value strategy (research - fast)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt \
  --output results/momentum_value_backtest.json

# Same strategy (production - accurate)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine custom \
  --output results/momentum_value_backtest_custom.json

# Compare results
python3 scripts/compare_backtest_results.py \
  --vectorbt results/momentum_value_backtest.json \
  --custom results/momentum_value_backtest_custom.json
```

### Walk-Forward Optimization

```bash
# Out-of-sample testing
python3 quant_platform.py walk-forward \
  --strategy momentum_value \
  --train-period 3y \
  --test-period 1y \
  --start 2015-01-01 \
  --end 2023-12-31 \
  --engine custom

# Expected output:
# - Training Sharpe: >1.5
# - Testing Sharpe: >1.0 (no overfitting)
```

---

## 5. Portfolio Optimization

**Week 8+**

### Mean-Variance Optimization

```bash
# Optimize portfolio weights
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15 \
  --constraints config/optimization_constraints.yaml \
  --universe KR_TOP100 \
  --output results/optimized_portfolio.json

# Visualize efficient frontier
python3 scripts/plot_efficient_frontier.py \
  --results results/optimized_portfolio.json
```

### Risk Parity

```bash
# Equal risk contribution
python3 quant_platform.py optimize \
  --method risk_parity \
  --universe KR_TOP100 \
  --output results/risk_parity_portfolio.json
```

### Black-Litterman

```bash
# Bayesian optimization with investor views
python3 quant_platform.py optimize \
  --method black_litterman \
  --views config/investor_views.yaml \
  --universe KR_TOP100 \
  --output results/black_litterman_portfolio.json
```

---

## 6. Risk Analysis

**Week 8+**

### Value at Risk (VaR)

```bash
# Calculate 95% VaR (10-day horizon)
python3 modules/risk/var_calculator.py \
  --portfolio current \
  --confidence 0.95 \
  --horizon 10 \
  --method historical

# Expected: VaR <5% of portfolio value
```

### Stress Testing

```bash
# Historical scenarios
python3 modules/risk/stress_tester.py \
  --portfolio current \
  --scenarios 2008_crisis,2020_covid,2022_bear \
  --output results/stress_test.json

# Visualize results
python3 scripts/plot_stress_test.py \
  --results results/stress_test.json
```

### Factor Exposure

```bash
# Analyze factor exposures
python3 modules/risk/exposure_tracker.py \
  --portfolio current \
  --factors momentum,value,quality,size \
  --output results/factor_exposure.json
```

---

## 7. Dashboard Usage

### Launch Streamlit Dashboard

```bash
# Start dashboard
streamlit run dashboard/app.py

# Access at http://localhost:8501

# Available pages:
# 1. Backtest Engine Monitor
# 2. Backtest Results
# 3. Portfolio Analytics
# 4. Factor Analysis
# 5. Risk Dashboard
```

---

## 8. API Usage

### Launch FastAPI Backend

```bash
# Start API server
uvicorn api.main:app --reload --port 8000

# API Documentation: http://localhost:8000/docs
```

### Example API Calls

```bash
# List strategies
curl http://localhost:8000/strategies

# Run backtest
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 100000000
  }'

# Optimize portfolio
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mean_variance",
    "target_return": 0.15,
    "universe": "KR_TOP100"
  }'
```

---

## Common Issues & Solutions

### Issue 1: vectorbt Installation Fails

```bash
# Solution: Install dependencies first
pip install numpy pandas numba bottleneck

# Then install vectorbt
pip install vectorbt
```

### Issue 2: PostgreSQL Connection Error

```bash
# Check PostgreSQL status
brew services list | grep postgresql

# Start PostgreSQL if not running
brew services start postgresql@17

# Test connection
psql -d quant_platform -c "SELECT 1;"
```

### Issue 3: TimescaleDB Extension Not Found

```bash
# Re-install TimescaleDB
brew reinstall timescaledb

# Update postgresql.conf
echo "shared_preload_libraries = 'timescaledb'" >> $(brew --prefix)/var/postgresql@17/postgresql.conf

# Restart PostgreSQL
brew services restart postgresql@17

# Create extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Issue 4: Backtest Too Slow

```bash
# Use vectorbt for research (100x faster)
python3 quant_platform.py backtest \
  --engine vectorbt \
  --strategy your_strategy

# Use custom engine only for final validation
python3 quant_platform.py backtest \
  --engine custom \
  --strategy your_strategy
```

---

## Best Practices

### 1. Always Use Dry-Run First

```bash
# Test with dry-run flag
python3 quant_platform.py backtest \
  --strategy test_strategy \
  --dry-run

# Execute after validation
python3 quant_platform.py backtest \
  --strategy test_strategy
```

### 2. Version Control Strategies

```bash
# Commit strategy definitions
git add config/strategies/momentum_value.yaml
git commit -m "Add momentum+value strategy (Sharpe: 1.8)"

# Tag successful backtests
git tag -a backtest-v1.0 -m "Validated strategy (Sharpe: 1.8, DD: 12%)"
```

### 3. Document Assumptions

```bash
# Add strategy documentation
echo "
# Momentum + Value Strategy

## Assumptions
- 12-month momentum lookback
- P/E ratio <15 for value screen
- Rebalance monthly
- Transaction cost: 0.015%

## Backtest Results (2018-2023)
- Sharpe: 1.8
- Max DD: 12%
- Win Rate: 58%
" > docs/strategies/momentum_value.md
```

---

## Related Documentation

- **Architecture**: QUANT_PLATFORM_ARCHITECTURE.md
- **Database Schema**: QUANT_DATABASE_SCHEMA.md
- **Backtesting Engines**: QUANT_BACKTESTING_ENGINES.md
- **Roadmap**: QUANT_ROADMAP.md
- **Operations**: QUANT_OPERATIONS.md
