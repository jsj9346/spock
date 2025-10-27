# CLAUDE.md - Quant Investment Platform

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Quant Investment Platform** is a systematic quantitative research and portfolio management system designed for evidence-based investment strategy development. The platform pivots from automated trading execution (Spock) to comprehensive quant research, backtesting, and portfolio optimization.

### Core Philosophy
- **🎯 Backtesting Engine First**: Complete and validate backtesting infrastructure before strategy development
- **Engine-Driven Development**: Build reliable backtesting foundation (vectorbt + custom engine) as prerequisite for all research activities
- **Research-Driven Approach**: Strategy validation through rigorous backtesting before deployment
- **Evidence-Based Decision Making**: Data-driven factor analysis and systematic signal generation
- **Systematic Risk Management**: Quantitative risk assessment and portfolio-level constraints
- **Reproducible Results**: Version-controlled strategies with deterministic backtest results
- **Multi-Factor Framework**: Combine proven factors (Value, Momentum, Quality) for robust alpha generation

### Target Users
- **Primary**: Quantitative researchers developing and validating investment strategies
- **Secondary**: Portfolio managers seeking systematic asset allocation and rebalancing
- **Tertiary**: Individual investors building evidence-based factor portfolios

---

## Architectural Pivot: From Trading to Research

### What Changed
| Aspect | Spock (Trading System) | Quant Platform (Research) |
|--------|------------------------|---------------------------|
| **Primary Goal** | Real-time trade execution | Strategy development & validation |
| **Database** | SQLite (250-day retention) | PostgreSQL + TimescaleDB (unlimited history) |
| **Time Horizon** | Intraday to weeks | Years of historical data |
| **Core Engine** | LayeredScoringEngine (100-point) | Multi-Factor Analysis Engine |
| **Execution** | KIS API order submission | Backtesting simulation |
| **Interface** | CLI + monitoring dashboard | Streamlit research workbench |
| **Focus** | Single-stock signals | Portfolio-level optimization |

### What Stayed (70% Code Reuse)
- ✅ **Data Collection Infrastructure**: KIS API adapters, market-specific parsers
- ✅ **Technical Analysis Modules**: Moving averages, RSI, MACD, Bollinger Bands
- ✅ **Scoring System Foundation**: LayeredScoringEngine extended for multi-factor analysis
- ✅ **Risk Management**: Kelly Calculator, ATR-based position sizing
- ✅ **Database Schema**: Core tables (tickers, ohlcv_data, technical_analysis)
- ✅ **Monitoring Stack**: Prometheus + Grafana infrastructure

---

## Tech Stack

### Core Dependencies
**Language & Runtime**: Python 3.11+

**Data & Analysis**:
- pandas 2.0.3, numpy 1.24.3, scipy 1.11.0
- scikit-learn 1.3.0, pandas-ta 0.3.14b0, statsmodels 0.14.0

**Database**:
- PostgreSQL 15+ (relational data, unlimited retention)
- TimescaleDB 2.11+ (time-series optimization)
- psycopg2 2.9.7

**Backtesting Engines**:
- Custom Event-Driven Engine (production stability ✅)
- vectorbt 0.25.6 (research optimization, 100x faster 🎯 **Priority 1**)
- backtrader 1.9.78.123 (optional, live trading 📋)
- zipline-reloaded 2.4.0 (optional, institutional 📋)

**Portfolio Optimization**:
- cvxpy 1.3.2, PyPortfolioOpt 1.5.5, riskfolio-lib 4.3.0

**Web Framework**:
- FastAPI 0.103.1, Streamlit 1.27.0, uvicorn 0.23.2

**Visualization**:
- plotly 5.17.0, matplotlib 3.7.2, seaborn 0.12.2

**Configuration & Logging**:
- python-dotenv 1.0.0, pyyaml 6.0.1, loguru 0.7.0

**Monitoring** (Reused from Spock):
- prometheus-client 0.23.1, psutil 5.9.5

**For complete dependency list, see `requirements_quant.txt`**

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Research Dashboard                 │
│  Strategy Builder | Backtest Results | Portfolio Analytics      │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  /strategies | /backtest | /optimize | /risk | /data            │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────────────────────┐
│                    Core Engine Layer                             │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Multi-Factor    │  Backtesting     │  Portfolio Optimizer     │
│  Analysis Engine │  Engine          │  (cvxpy)                 │
│  - Value         │  - Custom ✅     │  - Mean-Variance         │
│  - Momentum      │  - vectorbt 🎯   │  - Risk Parity           │
│  - Quality       │  - backtrader 📋 │  - Black-Litterman       │
│  - Low Vol       │  - zipline 📋    │  - Kelly Multi-Asset     │
│  - Size          │                  │  - Constraint Handling   │
└──────────────────┴──────────────────┴──────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                Data Layer (PostgreSQL + TimescaleDB)             │
│  Hypertables: ohlcv_data (continuous aggregates)                │
│  Tables: tickers, factors, strategies, backtest_results         │
└──────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│              Data Collection (Reused from Spock)                 │
│  KIS API | Polygon.io | yfinance | Market Adapters             │
└──────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
~/spock/
   quant_platform.py                    # Main orchestrator

   modules/
      # Core Quant Components
      factors/                          # Factor Library
      backtest/                         # Backtesting Engine
      optimization/                     # Portfolio Optimization
      risk/                             # Risk Management
      strategies/                       # Strategy Definitions

      # Data Collection (Reused from Spock)
      api_clients/                      # API wrappers
      market_adapters/                  # Market-specific adapters
      parsers/                          # Data transformation

   api/                                 # FastAPI Backend
   dashboard/                           # Streamlit UI
   config/                              # Configuration files
   data/                                # PostgreSQL database
   logs/                                # Application logs
   tests/                               # Test suites
   docs/                                # Documentation

   examples/
      example_momentum_value_strategy.py
      example_backtest_workflow.py
      example_portfolio_optimization.py
```

---

## 📚 Documentation Index

Detailed documentation has been split into specialized files for better organization and performance:

### Core Documentation
- **[QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md)** - PostgreSQL + TimescaleDB schema design
  - Table structures, hypertables, continuous aggregates
  - Compression policies, query optimization patterns
  - Backup strategies, performance benchmarks

- **[QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)** - Development workflows with command examples
  - Backtesting engine setup (Priority 1)
  - Database setup and migration
  - Factor research, strategy development
  - Portfolio optimization, risk analysis
  - Dashboard and API usage examples

- **[QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md)** - 15-week development roadmap
  - Phase 1: Backtesting Engine (Week 1-2) 🎯 **HIGHEST PRIORITY**
  - Phase 2-11: Database through Production (Week 3-15)
  - Success criteria and quality gates

- **[QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md)** - Backtesting engine comparison
  - Custom Event-Driven Engine (production ✅)
  - vectorbt (research, 100x faster 🎯)
  - backtrader and zipline (optional 📋)
  - Performance benchmarks, code examples

- **[QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md)** - Operations and monitoring
  - Logging configuration and best practices
  - Prometheus metrics, Grafana dashboards
  - Alerting rules, troubleshooting guides
  - Daily/weekly/monthly operational procedures

---

## Quick Start

### 1. Environment Setup
```bash
# Clone repository
cd ~/spock

# Install dependencies
pip install -r requirements_quant.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database credentials
```

### 2. Database Setup
```bash
# Install PostgreSQL + TimescaleDB
brew install postgresql@17 timescaledb  # macOS

# Create database
createdb quant_platform

# Enable TimescaleDB
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Initialize schema
python3 scripts/init_postgres_schema.py
```

**For detailed setup instructions, see [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md#2-database-setup)**

### 3. Backtesting Engine Validation (Priority 1)
```bash
# Install backtesting engines
pip install vectorbt backtrader zipline-reloaded

# Test custom engine
python3 modules/backtest/backtest_engine.py --mode validate

# Test vectorbt integration
python3 modules/backtest/vectorbt_adapter.py --test-integration

# Run comprehensive tests
python3 tests/test_backtest_engine.py --comprehensive
```

**For complete engine setup guide, see [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md#1-backtesting-engine-setup)**

### 4. Run Example Backtest
```bash
# Simple momentum strategy (using vectorbt - fast)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --engine vectorbt
```

---

## Development Workflow Summary

**Current Focus**: Phase 1 - Backtesting Engine Development & Validation (Week 1-2)

### 🎯 Phase 1: Backtesting Engine (HIGHEST PRIORITY)
**Critical Foundation**: No strategy work until engine is validated

**Week 1**: Custom engine enhancement + vectorbt integration + performance metrics
**Week 2**: Walk-forward optimization + comprehensive testing + documentation

**Success Criteria**:
- ✅ Custom engine: <30s for 5-year simulation
- ✅ vectorbt: <1s for 5-year simulation
- ✅ >95% accuracy validation
- ✅ All performance metrics auto-calculated

**For complete roadmap, see [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md)**

### Workflow Phases
1. **Backtesting Engine Setup** (Week 1-2) → Current Phase
2. **Database Migration** (Week 3)
3. **Factor Research** (Week 5-6) - After engine validation
4. **Strategy Development** (Week 7+) - After engine + factors ready
5. **Portfolio Optimization** (Week 8+)
6. **Production Deployment** (Week 15)

**For detailed workflows and command examples, see [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)**

---

## Core Components

### 1. Multi-Factor Analysis Engine
**Purpose**: Systematic alpha generation through factor-based stock selection

**Factor Categories**:
- **Value**: P/E, P/B, EV/EBITDA, Dividend Yield
- **Momentum**: 12-month return, RSI, 52-week high
- **Quality**: ROE, Debt/Equity, Earnings Quality
- **Low-Volatility**: Volatility, Beta, Max Drawdown
- **Size**: Market Cap, Liquidity

**Output**: Composite alpha score (0-100) for each stock, updated daily

### 2. Backtesting Engine (Hybrid Strategy)
**Purpose**: Historical simulation with realistic transaction costs

**Production**: Custom Event-Driven Engine (stable, implemented ✅)
**Research**: vectorbt (100x faster parameter optimization 🎯 **Priority 1**)
**Optional**: backtrader (live trading), zipline (institutional) 📋

**For detailed engine comparison and examples, see [QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md)**

### 3. Portfolio Optimization
**Purpose**: Optimal asset allocation under risk constraints

**Methods**:
- Mean-Variance (Markowitz)
- Risk Parity
- Black-Litterman
- Kelly Criterion (Multi-Asset)

**Constraints**: Position limits, sector limits, turnover, cash reserve

### 4. Risk Management
**Purpose**: Quantitative risk assessment and monitoring

**Metrics**: VaR, CVaR, stress testing, correlation analysis, factor exposure

**Risk Limits**: Portfolio VaR <5%, single position VaR <1%, sector <40%

**For detailed risk management workflows, see [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md#risk-analysis)**

---

## Database Architecture

### PostgreSQL + TimescaleDB Design
**Philosophy**: Unlimited historical data retention with time-series optimization

**Key Tables**:
- `ohlcv_data` (hypertable) - Price and volume data
- `factor_scores` - Factor calculations
- `strategies` - Strategy definitions
- `backtest_results` - Simulation results
- `portfolio_holdings` - Position tracking

**Optimization**:
- Continuous aggregates for monthly/yearly data
- Compression (10x space savings after 1 year)
- Query performance <1s for 10-year data

**For complete schema and SQL examples, see [QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md)**

---

## Success Metrics

### 🎯 Backtesting Engine (Phase 1 - Critical)
- Custom Engine: <30s for 5-year simulation
- vectorbt: <1s for 5-year simulation
- Accuracy: >95% match with reference backtests
- Test Coverage: >90% code coverage

### Strategy Performance (Post-Engine Validation)
- Sharpe Ratio: >1.5
- Backtest Accuracy: >90% consistency
- Factor Independence: Correlation <0.5
- Minimum Trades: >100 for statistical significance

### Portfolio Performance
- Total Return: >15% annually
- Sharpe Ratio: >1.5
- Maximum Drawdown: <15%
- VaR (95%): <5% of portfolio value

### System Performance
- Database Query: <1s for 10-year data
- API Latency: <200ms (p95)
- Dashboard Load: <3s

**For complete metrics and targets, see [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md#success-metrics-summary)**

---

## Monitoring and Operations

### Log Files
- **Location**: `logs/YYYYMMDD_quant_platform.log`
- **Retention**: 30 days
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Performance Metrics (Prometheus)
- Backtest metrics (runtime, memory, cache hit rate)
- Optimization metrics (convergence time, constraint violations)
- Factor metrics (calculation time, data availability)
- Database metrics (query time, connection pool, disk usage)
- API metrics (request rate, latency, error rate)

### Alerts (Grafana)
- **Critical**: Database connection lost, API failures, optimization errors
- **Warning**: Slow backtest (>60s), factor failures, high memory
- **Info**: Daily updates, weekly reports, monthly rebalancing

**For complete operations guide, see [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md)**

---

## Research Best Practices

### Avoiding Common Pitfalls
- **Overfitting**: Use walk-forward optimization, not in-sample
- **Transaction Costs**: Always include realistic commission and slippage
- **Survivorship Bias**: Use point-in-time data (no look-ahead)
- **Data Quality**: Validate for splits, dividends, errors
- **Statistical Significance**: Require >100 trades for meaningful results

### Risk Warnings
- **Backtesting ≠ Future Results**: Past performance does not guarantee future returns
- **Model Risk**: Strategies can fail when market regimes change
- **Execution Risk**: Live trading may differ from backtest
- **Correlation Breakdown**: Asset correlations spike during crises
- **Leverage Risk**: Magnified losses possible

---

## Key Development Principles

### 🎯 Engine-First Approach
1. **No strategy development without validated backtesting engine**
2. **Engine validation gates**: Performance benchmarks, accuracy tests, stress tests
3. **Dual-engine strategy**: vectorbt for research speed, custom for production accuracy
4. **Continuous validation**: Automated testing and performance monitoring

### Quality Gates
- **Phase 1 Gate**: Backtesting engine must pass all tests before proceeding
- **Phase 4 Gate**: Factor library validated using backtesting engine
- **Phase 7 Gate**: Strategies show >100 trades and >1.0 Sharpe ratio
- **Phase 11 Gate**: Full integration test before production

**For complete quality gates and validation cycle, see [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md#key-development-principles)**

---

## Support & Resources

### Documentation
All detailed documentation is available in the `docs/` directory:
- [QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md) - Database design
- [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md) - Development guides
- [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md) - Project roadmap
- [QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md) - Engine comparison
- [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md) - Operations guide

### Code Examples
- **Strategy Development**: `examples/example_momentum_value_strategy.py`
- **Backtesting**: `examples/example_backtest_workflow.py`
- **Portfolio Optimization**: `examples/example_portfolio_optimization.py`

### External Resources
- **vectorbt**: https://vectorbt.dev/
- **backtrader**: https://www.backtrader.com/
- **zipline**: https://zipline.ml4trading.io/
- **PyPortfolioOpt**: https://pyportfolioopt.readthedocs.io/
- **TimescaleDB**: https://docs.timescale.com/

---

**Last Updated**: 2025-10-26
**Version**: 1.2.0 (Optimized)
**Status**: Engine-First Development Phase
**Current Focus**: Phase 1 - Backtesting Engine Development & Validation (Week 1-2)
