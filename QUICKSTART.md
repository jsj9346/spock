# Spock Trading System - Quick Start Guide

**Get up and running in 5 minutes**

---

## Prerequisites

- Python 3.11+
- KIS API credentials ([Get API Key](https://apiportal.koreainvestment.com))
- 5 minutes of your time ⏱️

---

## Step 1: Setup KIS API Credentials (2 minutes)

### Interactive Setup (Recommended)
```bash
cd ~/spock
python3 scripts/setup_credentials.py
```

Follow the prompts to enter:
- **APP_KEY** (20 characters)
- **APP_SECRET** (40 characters)

### Manual Setup
```bash
# Create .env file
cat > .env << EOF
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
EOF

# Secure the file
chmod 600 .env
```

### Validate Credentials
```bash
python3 scripts/validate_kis_credentials.py
```

**Expected Output**:
```
✅ Environment file exists
✅ APP_KEY loaded (20 chars)
✅ APP_SECRET loaded (40 chars)
✅ OAuth token obtained successfully
✅ US market data: Accessible
🎉 All validation checks passed!
```

---

## Step 2: Initialize Database (1 minute)

```bash
python3 -c "from spock_init_db import SpockDatabaseInitializer; \
SpockDatabaseInitializer().initialize_complete_database()"
```

**Expected Output**:
```
✅ Database initialized: data/spock_local.db
✅ Tables created: 15 tables
✅ Indexes created: 8 indexes
```

---

## Step 3: Your First Stock Scan (2 minutes)

### Korea Market (Fastest)
```bash
# Dry run (no real API calls, safe to test)
python3 spock.py --dry-run --region KR --mode manual

# Real scan (uses KIS API)
python3 spock.py --region KR --mode manual
```

### US Market (Recommended for Global Investors)
```bash
# Scan US stocks (NASDAQ, NYSE, AMEX)
python3 scripts/deploy_us_adapter.py --scan-only
```

**Expected Output**:
```
🔍 Scanning US market...
✅ NASDAQ: 2,000 stocks
✅ NYSE: 800 stocks
✅ AMEX: 200 stocks
📊 Total: 3,000 tradable stocks
⏱️ Time: 3 minutes
```

---

## Step 4: Collect Historical Data (Optional, 5 minutes)

```bash
# Collect 250 days of OHLCV data for top 5 stocks
python3 scripts/deploy_us_adapter.py --tickers AAPL,MSFT,GOOGL,AMZN,TSLA --days 250
```

**Expected Output**:
```
📈 Collecting OHLCV data...
✅ AAPL: 250 days (200 req/sec)
✅ MSFT: 250 days
✅ GOOGL: 250 days
✅ AMZN: 250 days
✅ TSLA: 250 days
⏱️ Time: 2 minutes
```

---

## Step 5: Run Full Pipeline (Optional, 10 minutes)

```bash
# Full pipeline with moderate risk profile
python3 spock.py --risk-level moderate --region US
```

**Pipeline Stages**:
1. **Scanner** → Discover tradable stocks
2. **Data Collector** → Fetch 250-day OHLCV data
3. **Technical Filter** → Weinstein Stage 2 detection
4. **GPT Analyzer** (optional) → Chart pattern analysis
5. **Kelly Calculator** → Position sizing
6. **Trading Engine** → Order execution (dry-run mode by default)

---

## Common CLI Commands

### Data Collection
```bash
# Korea stocks
python3 modules/kis_data_collector.py --region KR --tickers 005930,000660 --days 250

# US stocks
python3 modules/kis_data_collector.py --region US --tickers AAPL,MSFT --days 250

# All regions
python3 modules/kis_data_collector.py --all-regions --days 250
```

### Stock Scanning
```bash
# Korea market (KOSPI, KOSDAQ)
python3 modules/scanner.py --region KR --min-market-cap 1000000000

# US market (NYSE, NASDAQ, AMEX)
python3 modules/scanner.py --region US --min-market-cap 1000000000

# Multiple regions
python3 modules/scanner.py --regions KR,US,CN,HK,JP,VN
```

### Technical Analysis
```bash
# Single stock
python3 modules/stock_pre_filter.py --ticker AAPL --region US

# Batch analysis
python3 modules/stock_pre_filter.py --tickers AAPL,MSFT,GOOGL --region US

# Full pipeline
python3 spock.py --dry-run --region US
```

### Testing & Validation
```bash
# Test KIS API connection
python3 scripts/test_kis_connection.py --basic

# Test with latency measurement
python3 scripts/test_kis_connection.py --latency

# Test multiple markets
python3 scripts/test_kis_connection.py --markets

# Run unit tests
pytest tests/test_us_adapter_kis.py -v
```

---

## Monitoring (Optional)

### Start Monitoring Stack
```bash
# Start Prometheus + Grafana + Alertmanager
cd monitoring
docker-compose up -d

# Start metrics exporter
python3 monitoring/exporters/spock_exporter.py --port 8000 &
```

### Access Dashboards
- **Grafana**: http://localhost:3000 (admin/spock2025)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

---

## Troubleshooting

### Issue: "KIS API Connection Failed"
```bash
# Validate credentials
python3 scripts/validate_kis_credentials.py

# Check token cache
python3 scripts/check_token_cache.py

# Test connection
python3 scripts/test_kis_connection.py --basic
```

### Issue: "Database Locked"
```bash
# Check active connections
lsof | grep spock_local.db

# Kill stuck processes
pkill -f spock.py
```

### Issue: "No Data in Grafana"
```bash
# Restart metrics exporter
pkill -f spock_exporter
python3 monitoring/exporters/spock_exporter.py --port 8000 &

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

**Complete Troubleshooting Guide**: [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md:1)

---

## Next Steps

### For Developers
1. Read [CLAUDE.md](CLAUDE.md:1) - Complete project overview
2. Study [COMPONENT_REFERENCE.md](COMPONENT_REFERENCE.md:1) - Module documentation
3. Review [Global Adapter Design](docs/GLOBAL_ADAPTER_DESIGN.md:1) - Adapter pattern
4. Explore [Phase 6 Completion Report](docs/PHASE6_COMPLETION_REPORT.md:1) - Latest architecture

### For Operators
1. Read [Deployment Guide](docs/DEPLOYMENT_GUIDE.md:1) - Production setup
2. Review [Operations Runbook](docs/OPERATIONS_RUNBOOK.md:1) - Daily operations
3. Setup [Monitoring](monitoring/README.md:1) - Grafana dashboards
4. Follow [US Adapter Deployment](docs/US_ADAPTER_DEPLOYMENT_GUIDE.md:1) - Deploy first market

### For Quant Analysts
1. Read [spock_PRD.md](spock_PRD.md:1) - Investor decision journey
2. Study [Filtering System Guide](FILTERING_SYSTEM_GUIDE.md:1) - Multi-stage filtering
3. Explore [Stock GPT Analyzer](docs/STOCK_GPT_ANALYZER_DESIGN.md:1) - AI chart analysis
4. Review [Backtesting Guide](docs/BACKTESTING_GUIDE.md:1) - Strategy testing

---

## Key Resources

### Documentation
- [PROJECT_INDEX.md](PROJECT_INDEX.md:1) - Complete navigation
- [COMPONENT_REFERENCE.md](COMPONENT_REFERENCE.md:1) - Module documentation
- [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md:1) - Issue resolution
- [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md:1) - KIS API reference

### Market Coverage
- **Phase 1**: Korea (KR) - KOSPI, KOSDAQ
- **Phase 2**: United States (US) - NYSE, NASDAQ, AMEX
- **Phase 3**: China (CN), Hong Kong (HK) - SSE, SZSE, HKEX
- **Phase 4**: Japan (JP) - Tokyo Stock Exchange
- **Phase 5**: Vietnam (VN) - HOSE, HNX
- **Phase 6**: KIS Global Integration - Unified API (13x-240x faster)

---

## Example Workflows

### Workflow 1: Daily Stock Screening (Korea)
```bash
# 1. Scan Korea market
python3 modules/scanner.py --region KR --min-market-cap 1e9

# 2. Collect OHLCV data (250 days)
python3 modules/kis_data_collector.py --region KR --days 250

# 3. Run technical filter (Weinstein Stage 2)
python3 modules/stock_pre_filter.py --region KR --min-score 70

# 4. Review results
sqlite3 data/spock_local.db "SELECT ticker, score FROM technical_analysis WHERE region='KR' AND score >= 70 ORDER BY score DESC LIMIT 10;"
```

### Workflow 2: Multi-Region Deployment (US)
```bash
# 1. Setup credentials
python3 scripts/setup_credentials.py

# 2. Deploy US adapter (full pipeline)
python3 scripts/deploy_us_adapter.py --full --days 250

# 3. Monitor progress
curl http://localhost:8002/metrics | grep spock_us

# 4. Verify data quality
python3 scripts/check_data_quality.py --region US
```

### Workflow 3: Backtesting Strategy
```bash
# 1. Collect historical data
python3 modules/kis_data_collector.py --region US --days 500

# 2. Run backtest
python3 -c "from modules.backtesting import BacktestEngine; \
from modules.db_manager_sqlite import SQLiteDatabaseManager; \
engine = BacktestEngine(SQLiteDatabaseManager()); \
results = engine.run_backtest('Weinstein Stage 2', '2023-01-01', '2024-10-19', 100_000_000, 'US'); \
print(f'Sharpe: {results[\"sharpe_ratio\"]:.2f}, Max DD: {results[\"max_drawdown\"]:.2%}, Win Rate: {results[\"win_rate\"]:.2%}')"

# 3. Review detailed results
# Open Jupyter Notebook for visualization
jupyter notebook notebooks/backtest_analysis.ipynb
```

---

## Performance Benchmarks

### API Performance (Phase 6 KIS vs Legacy)

| Market | KIS API | Legacy API | Speedup | Data Collection (250 days) |
|--------|---------|------------|---------|----------------------------|
| **US** | 20 req/sec | 5 req/min | **240x** | ~10 min (3,000 stocks) |
| **CN** | 20 req/sec | 1.5 req/sec | **13x** | ~5 min (500 stocks) |
| **HK** | 20 req/sec | 1.0 req/sec | **20x** | ~7 min (1,000 stocks) |
| **JP** | 20 req/sec | 1.0 req/sec | **20x** | ~7 min (1,000 stocks) |
| **VN** | 20 req/sec | 1.0 req/sec | **20x** | ~3 min (300 stocks) |

### Database Performance

| Operation | Time | Rows |
|-----------|------|------|
| Insert 250-day OHLCV | <1s | 250 rows |
| Query 250-day OHLCV | <100ms | 250 rows |
| Technical analysis (single stock) | <200ms | 1 row |
| Database VACUUM | <10s | 691,854 rows |

---

## Support

### Getting Help
- **Documentation**: [PROJECT_INDEX.md](PROJECT_INDEX.md:1)
- **Troubleshooting**: [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md:1)
- **API Reference**: [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md:1)
- **Operations**: [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md:1)

### Log Files
- **Application Logs**: `logs/YYYYMMDD_spock.log` (7-day retention)
- **API Logs**: `kis_api_logs` table in database
- **Error Tracking**: `failure_tracker` module

---

**Quick Start Complete! 🎉**

You're now ready to explore the Spock trading system. For detailed documentation, see [CLAUDE.md](CLAUDE.md:1) or [PROJECT_INDEX.md](PROJECT_INDEX.md:1).

---

**Last Updated**: 2025-10-19
**Markets Supported**: 6 (KR, US, CN, HK, JP, VN)
**Status**: ✅ Production-Ready
