# Getting Started Guide

**A Friendly Guide for First-Time Users**

---

## 🎯 What is This Project?

**Quant Investment Platform** is a systematic research platform for developing and validating data-driven investment strategies.

### TL;DR (3 Key Points)

- 📊 **Backtesting**: Test and validate investment strategies using historical data
- 🔬 **Factor Analysis**: Statistically validated value, momentum, and quality factors
- 💼 **Portfolio Optimization**: Calculate optimal asset allocation with risk management

### What Can You Do?

✅ **Strategy Development**: Create your own investment strategies and test them with historical data
✅ **Performance Analysis**: Automatically calculate performance metrics (Sharpe ratio, max drawdown, win rate)
✅ **Risk Management**: Quantitative risk measurement (VaR, CVaR)
✅ **Portfolio Optimization**: Calculate Efficient Frontier
✅ **Multi-Factor Analysis**: Research combinations of value, momentum, and quality factors

### What Can't You Do?

❌ **Live Automated Trading**: This is currently for research and backtesting only
❌ **Investment Advice**: This software is not financial advice
❌ **Guaranteed Returns**: Past performance does not guarantee future results

---

## 👥 Who Is This For?

### Primary Users
- **Quantitative Researchers**: Developing and statistically validating investment strategies
- **Individual Investors**: Building evidence-based portfolios
- **Data Scientists**: Interested in financial data analysis and machine learning

### Required Background
- ✅ **Python Basics**: Basic syntax and package installation experience
- ✅ **Investment Fundamentals**: Understanding of stocks, returns, risk, etc.
- ⭐ **Statistics/Probability**: Helpful but not required
- ⭐ **Database Experience**: Helpful but automatically configured

---

## 🚀 Get Started in 3 Steps (15 minutes)

### Step 1: Environment Setup (5 minutes)

```bash
# 1. Clone repository
git clone https://github.com/jsj9346/spock.git
cd spock

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements_quant.txt
```

**Expected installation time**: 3-5 minutes (depending on internet speed)

### Step 2: Database Setup (5 minutes)

#### Install PostgreSQL + TimescaleDB

**macOS (Homebrew)**:
```bash
brew install postgresql@17 timescaledb
timescaledb-tune --quiet --yes
brew services start postgresql@17
```

**Ubuntu/Debian**:
```bash
sudo apt install postgresql-17 timescaledb-2-postgresql-17
sudo systemctl start postgresql
```

**Windows**:
- [PostgreSQL Install](https://www.postgresql.org/download/windows/)
- [TimescaleDB Install](https://docs.timescale.com/install/latest/self-hosted/installation-windows/)

#### Initialize Database

```bash
# 1. Create database
createdb quant_platform

# 2. Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 3. Initialize schema (create tables, indexes)
python3 scripts/init_postgres_schema.py
```

**Success message**:
```
✅ Database created: quant_platform
✅ TimescaleDB extension enabled
✅ Schema initialized: 12 tables, 8 indexes
✅ Hypertables created: ohlcv_data
```

### Step 3: Run Your First Backtest (5 minutes)

```bash
# Backtest momentum-value combined strategy (2020-2023)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt
```

**Expected output**:
```
🔄 Starting backtest...
✅ Data loaded: 3,000 tickers (5 seconds)
✅ Strategy executed: 150 rebalances (10 seconds)
✅ Performance calculated

📊 Backtest Results:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Return:     +45.2%
Annual Return:    +12.8%
Sharpe Ratio:     1.65
Max Drawdown:     -18.3%
Win Rate:         58.2%
Total Trades:     420
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📚 Next Steps - Learning Paths

### 🔰 Beginners (First-time users)

**Step 1**: [Quick Start Guide](QUICKSTART.md)
→ Experience basic features in 5 minutes

**Step 2**: [Project Overview](README.md)
→ Understand full features and architecture

**Step 3**: [CLI Usage Guide](docs/CLI_USAGE_GUIDE.md)
→ Command-line interface usage

**Step 4**: [Backtesting Guide](docs/BACKTESTING_GUIDE.md)
→ Learn proper backtesting methods

### 💻 Developers (Code contribution or customization)

**Step 1**: [Complete Project Guide](CLAUDE.md)
→ Project structure and development philosophy

**Step 2**: [Database Schema](docs/DATABASE_SCHEMA.md)
→ Data structure and query patterns

**Step 3**: [Backtesting Engines Comparison](docs/QUANT_BACKTESTING_ENGINES.md)
→ Engine features and selection guide

**Step 4**: [Factor Library](docs/FACTOR_LIBRARY_REFERENCE.md)
→ Factor definitions and calculation methods

**Step 5**: [Development Workflows](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)
→ Actual development procedures and commands

### 🚀 Operators (Production environment setup)

**Step 1**: [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
→ Server deployment and configuration

**Step 2**: [Operations Runbook](docs/OPERATIONS_RUNBOOK.md)
→ Daily operational procedures

**Step 3**: [Monitoring Guide](docs/QUANT_OPERATIONS.md)
→ Prometheus + Grafana setup

---

## ❓ Frequently Asked Questions (FAQ)

### General Questions

**Q1: Can I use this for live trading?**
A: No, the current version is **for research and backtesting only**. Live trading is not supported.

**Q2: Which markets are supported?**
A: We support 6 markets: Korea (KR), United States (US), China (CN), Hong Kong (HK), Japan (JP), Vietnam (VN).

**Q3: Is this free to use?**
A: Yes, it's free to use, modify, and distribute under the MIT License. However, **you are responsible for any investment losses**.

**Q4: Can I use this without programming experience?**
A: You need basic Python syntax and terminal usage knowledge. If you're a complete beginner, we recommend learning Python basics first.

### Technical Questions

**Q5: Why PostgreSQL? Can't I use SQLite?**
A:
- PostgreSQL + TimescaleDB: Unlimited historical data, time-series optimization, production stability
- SQLite: Suitable for testing, but inadequate for large-scale data processing

**Q6: Why multiple backtesting engines?**
A:
- **Custom Engine**: Production stability, fine-grained control
- **vectorbt**: Research use, 100x faster parameter optimization
- **backtrader/zipline**: Optional, special features

**Q7: Where does the data come from?**
A:
- Korean market: KIS API (Korea Investment & Securities)
- Global markets: Polygon.io, yfinance (configuration required)

**Q8: How much historical data do I need?**
A:
- **Minimum**: 2 years (low confidence)
- **Recommended**: 5+ years (statistical significance)
- **Ideal**: 10+ years (various market cycles)

### Performance Questions

**Q9: What constitutes good backtest results?**
A:
- Sharpe Ratio: >1.5 (industry standard: 1.0)
- Max Drawdown: <15%
- Win Rate: >55%
- Number of Trades: >100 (statistical significance)

**Q10: Can I expect backtest results in live trading?**
A: **No**. Backtests are based on historical data. In live trading, performance degrades due to slippage, commissions, and market impact. Conservatively expect only 50-70% of backtest performance.

### Troubleshooting

**Q11: I'm getting errors during installation**
A: See [Troubleshooting Guide](TROUBLESHOOTING_INDEX.md) or check the following:
```bash
# Check Python version (3.11+ required)
python3 --version

# Upgrade pip
pip install --upgrade pip

# Reinstall dependencies
pip install -r requirements_quant.txt --force-reinstall
```

**Q12: Database connection error**
A:
```bash
# Check PostgreSQL is running
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Linux

# Check database exists
psql -l | grep quant_platform

# Check .env file
cat .env | grep DB_
```

**Q13: Backtest is too slow**
A:
- **Use vectorbt**: `--engine vectorbt` (100x faster)
- **Reduce timeframe**: Test with 1 year first
- **Limit stocks**: Analyze top 500 only

---

## 🎓 Learning Resources

### Project Documentation
- 📖 [Complete Documentation List](DOCUMENTATION_INDEX.md)
- 🐛 [Troubleshooting Guide](TROUBLESHOOTING_INDEX.md)
- 🏗️ [Project Structure](PROJECT_INDEX.md)
- 🔧 [API Integration Guide](API_INTEGRATION_GUIDE.md)

### External Resources

**Backtesting Frameworks**:
- [vectorbt Official Docs](https://vectorbt.dev/)
- [backtrader Guide](https://www.backtrader.com/)
- [zipline Tutorial](https://zipline.ml4trading.io/)

**Portfolio Optimization**:
- [PyPortfolioOpt Documentation](https://pyportfolioopt.readthedocs.io/)
- [cvxpy Examples](https://www.cvxpy.org/examples/)

**Academic Papers** (Factor Research):
- Fama & French (1992) - Three-Factor Model
- Carhart (1997) - Momentum Factor
- Asness et al. (2013) - Value and Momentum Everywhere
- Novy-Marx (2013) - Quality Factor

### Online Courses
- [Quantopian Lectures](https://www.quantopian.com/lectures) - Free quant investment lectures
- [Coursera: Financial Engineering](https://www.coursera.org/learn/financial-engineering-1)
- [QuantConnect Tutorials](https://www.quantconnect.com/tutorials/)

---

## 💡 Tips and Best Practices

### Backtesting Tips
1. **Always include transaction costs**: Set realistic commissions and slippage
2. **Use walk-forward optimization**: Prevent overfitting
3. **Test various market conditions**: Validate in bull, bear, and sideways markets
4. **Require minimum 100 trades**: Ensure statistical significance

### Risk Management Tips
1. **Limit position sizes**: Max 5% per individual stock
2. **Sector diversification**: Max 40% per sector
3. **Set stop-losses**: Limit max drawdown to 15%
4. **Hold cash**: Maintain 10-20% cash in portfolio

### Development Tips
1. **Start small**: Begin with simple strategies, add complexity gradually
2. **Use version control**: Track strategy changes with Git
3. **Document thoroughly**: Clearly record strategy assumptions and logic
4. **Code review**: Have peers review strategy logic

---

## 📧 Need Help?

### Documentation and Support
- 📖 **Documentation**: `docs/` directory in project root
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/jsj9346/spock/issues)
- ✉️ **Email**: jsj9346@gmail.com
- 💬 **Discussions**: [GitHub Discussions](https://github.com/jsj9346/spock/discussions)

### Contributing
Want to contribute to project improvement?
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a Pull Request

See [Contributing Guidelines](CONTRIBUTING.md) (coming soon)

---

## ⚠️ Important Disclaimer

**Investment Risk Warning**:
- This software is provided **for educational and research purposes only**
- Past performance does not guarantee future results
- All investments carry risk of principal loss
- Consult a professional advisor before making investment decisions
- Developers are not responsible for investment losses

**License**:
- MIT License (commercial use allowed)
- Provided AS-IS (no warranty)
- See [LICENSE](LICENSE) file for details

---

## 🗺️ Next Steps

Congratulations! You're now ready to start with the Quant Investment Platform.

### Checklist
- [ ] Python 3.11+ installed
- [ ] PostgreSQL + TimescaleDB installed
- [ ] Project cloned and packages installed
- [ ] Database initialized
- [ ] First backtest executed successfully
- [ ] Next learning materials identified

### Recommended Learning Sequence
1. ✅ **GETTING_STARTED.md** (this document) ← Current location
2. ⏭️ [QUICKSTART.md](QUICKSTART.md) - 5-minute quick start
3. ⏭️ [README.md](README.md) - Complete project overview
4. ⏭️ [BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) - Backtesting best practices
5. ⏭️ [CLAUDE.md](CLAUDE.md) - Detailed developer guide

---

**Last Updated**: 2025-11-12
**Version**: 1.0.0 (English)
**Status**: Beginner guide complete ✅

**Happy quant researching! 📊✨**
