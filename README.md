# Quant Investment Platform

A systematic quantitative research and portfolio management platform for evidence-based investment strategy development.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-316192.svg)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2.11+-orange.svg)](https://www.timescale.com/)

## ⚠️ Investment Disclaimer

**THIS SOFTWARE IS FOR EDUCATIONAL AND RESEARCH PURPOSES ONLY.**

- Past performance does not guarantee future results
- The authors are not responsible for any financial losses incurred using this platform
- Trading and investing carry risk of loss, including loss of principal
- This software does not constitute financial, investment, legal, or tax advice
- Consult a licensed financial advisor before making any investment decisions
- Backtesting results may not reflect actual trading conditions (slippage, liquidity, market impact)
- All investment strategies involve risk, and there is no guarantee of profit

**BY USING THIS SOFTWARE, YOU ACKNOWLEDGE THAT YOU UNDERSTAND AND ACCEPT THESE RISKS.**

---

## 🎯 Overview

The Quant Investment Platform is a comprehensive research framework designed for systematic strategy development, backtesting, and portfolio optimization. The platform pivots from automated trading execution to focus on rigorous quantitative research and evidence-based decision making.

### Core Philosophy

- **🎯 Backtesting Engine First**: Complete and validate backtesting infrastructure before strategy development
- **📊 Research-Driven Approach**: Strategy validation through rigorous backtesting before deployment
- **🔬 Evidence-Based Decision Making**: Data-driven factor analysis and systematic signal generation
- **⚖️ Systematic Risk Management**: Quantitative risk assessment and portfolio-level constraints
- **🔄 Reproducible Results**: Version-controlled strategies with deterministic backtest results
- **📈 Multi-Factor Framework**: Combine proven factors (Value, Momentum, Quality) for robust alpha generation

### Target Users

- **Quantitative Researchers**: Developing and validating investment strategies
- **Portfolio Managers**: Seeking systematic asset allocation and rebalancing
- **Individual Investors**: Building evidence-based factor portfolios
- **Academic Researchers**: Studying factor performance and portfolio optimization

---

## ✨ Key Features

### 1. Multi-Factor Analysis Engine

Systematic alpha generation through factor-based stock selection:

- **Value Factors**: P/E, P/B, EV/EBITDA, Dividend Yield, Free Cash Flow Yield
- **Momentum Factors**: 12-month return, RSI momentum, 52-week high proximity
- **Quality Factors**: ROE, Debt-to-Equity, Earnings quality, Profit margin stability
- **Low-Volatility Factors**: Historical volatility, Beta, Maximum drawdown, CVaR
- **Size Factors**: Market capitalization, Trading volume, Free float

**Factor Combination Methods**:
- Equal weighting
- Optimization-based weighting (maximize Sharpe ratio)
- Risk-adjusted weighting (inverse volatility)
- Machine learning (XGBoost/RandomForest)

### 2. Hybrid Backtesting Engine

**Production**: Custom Event-Driven Engine (stable, already implemented ✅)
- Full control over execution logic
- Realistic transaction cost simulation
- Suitable for live portfolio tracking

**Research**: vectorbt Integration (100x faster parameter optimization 🎯)
- Vectorized backtesting (NumPy-based)
- Ideal for parameter tuning
- Built-in performance metrics
- Minimal integration effort

**Advanced**: backtrader/zipline Support (optional 📋)
- backtrader: Live trading broker integration
- zipline: Institutional-grade risk models

**Performance Metrics**:
- Returns: Total, annualized, rolling
- Risk-Adjusted: Sharpe, Sortino, Calmar ratios
- Drawdown: Maximum, average, duration
- Win Rate, Risk Metrics (VaR, CVaR, Volatility, Beta)

### 3. Portfolio Optimization

Optimal asset allocation under risk constraints:

- **Mean-Variance Optimization** (Markowitz): Efficient frontier calculation
- **Risk Parity**: Equal risk contribution from each asset
- **Black-Litterman Model**: Bayesian approach combining market equilibrium + investor views
- **Kelly Criterion**: Multi-asset extension for geometric growth maximization

**Constraint Types**:
- Position limits (min/max per asset)
- Sector limits (max 40% per sector)
- Turnover constraints (max 20% rebalancing)
- Cash reserve requirements
- Long-only or long-short

### 4. Risk Management System

Quantitative risk assessment and monitoring:

- **Value at Risk (VaR)**: Historical, Parametric, Monte Carlo methods
- **Conditional VaR (CVaR)**: Tail risk capture
- **Stress Testing**: Historical scenarios (2008 Crisis, 2020 COVID, 2022 Bear)
- **Correlation Analysis**: Asset correlation matrix, factor exposure
- **Risk Limits**: Portfolio VaR <5%, Single position VaR <1%, Sector concentration <40%

### 5. Interactive Dashboard

Streamlit-based research workbench:

- **Backtest Engine Monitor**: Engine performance & validation
- **Backtest Results**: Strategy performance visualization
- **Portfolio Analytics**: Current holdings & risk metrics
- **Factor Analysis**: Factor performance & correlation
- **Risk Dashboard**: VaR, CVaR, stress tests

---

## 🏗️ Architecture

### System Overview

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
│  - Size          │  - Transaction   │  - Constraint Handling   │
│                  │    Cost Model    │                          │
└──────────────────┴──────────────────┴──────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                    Data Layer (PostgreSQL + TimescaleDB)         │
│  Hypertables: ohlcv_data (continuous aggregates)                │
│  Tables: tickers, factors, strategies, backtest_results         │
│  Retention: Unlimited (compression after 1 year)                │
└──────────────────────────────────────────────────────────────────┘
```

### Tech Stack

**Core**:
- Python 3.11+
- PostgreSQL 15+ with TimescaleDB 2.11+
- pandas, NumPy, scipy, scikit-learn

**Backtesting**:
- Custom Event-Driven Engine (production)
- vectorbt 0.25.6 (research, 100x faster)
- backtrader, zipline (optional)

**Optimization**:
- cvxpy, PyPortfolioOpt, riskfolio-lib

**Web Framework**:
- FastAPI 0.103.1
- Streamlit 1.27.0
- uvicorn 0.23.2

**Visualization**:
- plotly, matplotlib, seaborn

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- TimescaleDB 2.11+

### Installation

```bash
# Clone repository
git clone https://github.com/jsj9346/spock.git
cd spock

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements_quant.txt

# Install PostgreSQL + TimescaleDB (macOS)
brew install postgresql timescaledb
timescaledb-tune --quiet --yes

# Create database
createdb quant_platform
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Initialize schema
python3 scripts/init_postgres_schema.py

# Configure environment
cp .env.example .env
# Edit .env with your database credentials and API keys
```

### Usage

**Launch Dashboard**:
```bash
streamlit run dashboard/app.py
# Access at http://localhost:8501
```

**Launch API**:
```bash
uvicorn api.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

**Run Backtest**:
```bash
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt
```

**Optimize Portfolio**:
```bash
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15 \
  --constraints config/optimization_constraints.yaml
```

---

## 📊 Development Workflow

### Phase 1: Backtesting Engine Setup (Week 1-2) 🎯 **PRIORITY**

```bash
# Step 1: Install backtesting dependencies
pip install vectorbt backtrader zipline-reloaded

# Step 2: Enhance custom event-driven engine
python3 modules/backtest/backtest_engine.py --mode validate

# Step 3: Integrate vectorbt for fast research
python3 modules/backtest/vectorbt_adapter.py --test-integration

# Step 4: Validate engine accuracy
python3 tests/test_backtest_engine.py --comprehensive
```

### Phase 2: Factor Research (After Engine Validation)

```bash
# Analyze individual factor performance
python3 modules/factors/factor_analyzer.py --factor momentum --start 2018-01-01

# Check factor correlations
python3 modules/factors/factor_correlation.py --factors momentum,value,quality

# Backtest single-factor strategy
python3 modules/backtest/backtest_engine.py \
  --strategy single_factor \
  --factor momentum \
  --start 2018-01-01 \
  --end 2023-12-31
```

### Phase 3: Strategy Development (After Factors Ready)

```bash
# Create new strategy
python3 modules/strategies/strategy_builder.py

# Walk-forward optimization
python3 quant_platform.py walk-forward \
  --strategy momentum_value \
  --train-period 3y \
  --test-period 1y \
  --start 2015-01-01
```

---

## 📁 Project Structure

```
spock/
├── quant_platform.py           # Main orchestrator
├── modules/
│   ├── factors/                # Factor library
│   ├── backtest/               # Backtesting engines
│   ├── optimization/           # Portfolio optimization
│   ├── risk/                   # Risk management
│   ├── strategies/             # Strategy definitions
│   ├── api_clients/            # API wrappers
│   └── market_adapters/        # Market-specific adapters
├── api/                        # FastAPI backend
├── dashboard/                  # Streamlit UI
├── config/                     # Configuration files
├── data/                       # Data storage
├── logs/                       # Application logs
├── tests/                      # Test code
├── docs/                       # Documentation
└── examples/                   # Usage examples
```

---

## 📈 Success Metrics

### Backtesting Engine (Phase 1 - Critical)
- ✅ Custom Engine: <30 seconds for 5-year simulation
- ✅ vectorbt: <1 second for 5-year simulation (100x faster)
- ✅ Accuracy Validation: >95% match with reference backtests
- ✅ Performance Metrics: Auto-calculation of Sharpe, Sortino, Calmar, Max DD

### Strategy Development
- Target Sharpe Ratio: >1.5 (industry standard: 1.0)
- Backtest Accuracy: >90% consistency with live trading
- Factor Independence: Correlation <0.5
- Minimum Trades: >100 for statistical significance

### Portfolio Performance
- Total Return: >15% annually (vs KOSPI ~8%)
- Sharpe Ratio: >1.5
- Maximum Drawdown: <15%
- Win Rate: >55%
- VaR (95%): <5% of portfolio value

---

## 🧪 Research Best Practices

- **Avoid Overfitting**: Use walk-forward optimization, not in-sample optimization
- **Transaction Costs**: Always include realistic commission and slippage
- **Survivorship Bias**: Use point-in-time data (no look-ahead bias)
- **Data Quality**: Validate OHLCV data for splits, dividends, errors
- **Statistical Significance**: Require >100 trades for meaningful results

---

## 🔧 Configuration

### Environment Variables

Create `.env` file:
```
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_platform
DB_USER=your_user
DB_PASSWORD=your_password

# API Keys
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
POLYGON_API_KEY=your_polygon_key
```

### Factor Configuration

Edit `config/factor_definitions.yaml`:
```yaml
factors:
  value:
    enabled: true
    weight: 0.3
    metrics: [pe_ratio, pb_ratio, ev_ebitda]

  momentum:
    enabled: true
    weight: 0.4
    lookback_period: 252
    skip_recent: 21
```

---

## 📚 Documentation

- **Architecture**: [docs/QUANT_PLATFORM_ARCHITECTURE.md](docs/QUANT_PLATFORM_ARCHITECTURE.md)
- **Factor Library**: [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md)
- **Backtesting Guide**: [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md)
- **Optimization Cookbook**: [docs/OPTIMIZATION_COOKBOOK.md](docs/OPTIMIZATION_COOKBOOK.md)
- **Database Schema**: [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Please ensure**:
- All tests pass (`pytest tests/`)
- Code follows PEP 8 style guide
- Documentation is updated
- Backtesting results are reproducible

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Key Points**:
- ✅ Free to use, modify, and distribute
- ✅ Commercial use allowed
- ✅ No warranty provided
- ⚠️ Authors not liable for investment losses

---

## 🙏 Acknowledgments

**Reused Components from Spock (70%)**:
- Data collection infrastructure (KIS API adapters, market parsers)
- Technical analysis modules (MA, RSI, MACD, Bollinger Bands)
- Risk management (Kelly Calculator, ATR-based position sizing)
- Monitoring infrastructure (Prometheus + Grafana)

**Libraries & Frameworks**:
- [pandas](https://pandas.pydata.org/) - Data manipulation
- [NumPy](https://numpy.org/) - Numerical computing
- [vectorbt](https://vectorbt.dev/) - Fast backtesting
- [cvxpy](https://www.cvxpy.org/) - Convex optimization
- [TimescaleDB](https://www.timescale.com/) - Time-series database
- [Streamlit](https://streamlit.io/) - Interactive dashboard
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework

**Research References**:
- Fama & French (1992) - Three-Factor Model
- Carhart (1997) - Four-Factor Model (Momentum)
- Asness, Moskowitz & Pedersen (2013) - Value and Momentum Everywhere
- Novy-Marx (2013) - Quality Factor
- Ang, Hodrick, Xing & Zhang (2006) - Low-Volatility Anomaly

---

## 📧 Contact

- GitHub: [@jsj9346](https://github.com/jsj9346)
- Email: jsj9346@gmail.com

---

## 🗓️ Project Status

**Last Updated**: 2025-10-27
**Version**: 1.1.0
**Current Phase**: Phase 1 - Backtesting Engine Development & Validation (Week 1-2)
**Development Stage**: Engine-First Development Phase

**Roadmap**:
- ✅ Phase 0: Project cleanup & Git setup
- 🔄 Phase 1: Backtesting engine (in progress - **PRIORITY**)
- 📋 Phase 2: Database migration
- 📋 Phase 3: Factor library
- 📋 Phase 4: Strategy development
- 📋 Phase 5: Web interface

---

**Built with ❤️ for quantitative research and systematic investing**
