# Spock CLI Usage Guide

**Complete command-line interface documentation for individual module execution**

## Overview

This guide covers command-line usage for running individual Spock modules outside the main pipeline. Each module can be executed independently for testing, debugging, or specific workflows.

---

## Table of Contents

1. [Main Pipeline Execution](#1-main-pipeline-execution)
2. [Data Collection](#2-data-collection)
3. [Market Adapters](#3-market-adapters)
4. [Deployment Scripts](#4-deployment-scripts)
5. [Testing & Validation](#5-testing--validation)
6. [Demo & Examples](#6-demo--examples)

---

## 1. Main Pipeline Execution

### spock.py - Trading System Orchestrator

**Purpose**: Run the complete 7-stage trading pipeline (scan, collect, analyze, size, execute, sync).

**Required Arguments**:
- `--mode`: Execution mode (required, mutually exclusive)
  - `--dry-run`: Safe testing mode (no real trades)
  - `--live`: Live trading mode
  - `--after-hours`: Data collection only
  - `--backtest`: Historical backtesting mode
- `--region`: Trading region (required)
  - Choices: `KR`, `US`, `CN`, `HK`, `JP`, `VN`

**Optional Arguments**:
- `--risk-level {conservative,moderate,aggressive}`: Risk profile (default: moderate)
- `--enable-sentiment`: Enable market sentiment analysis
- `--max-positions INT`: Maximum concurrent positions (default: 10)
- `--scoring-threshold FLOAT`: Minimum technical score (default: 70.0)
- `--config-path PATH`: Configuration directory (default: ./config)
- `--db-path PATH`: SQLite database path (default: ./data/spock_local.db)
- `--log-path PATH`: Log directory (default: ./logs)
- `--debug`: Enable debug logging

**Examples**:

```bash
# Dry run for Korean market (safe testing)
python3 spock.py --dry-run --region KR --risk-level moderate

# Live trading with conservative risk profile
python3 spock.py --live --region KR --risk-level conservative

# After-hours data collection (no trading)
python3 spock.py --after-hours --region KR

# US market with sentiment analysis enabled
python3 spock.py --dry-run --region US --enable-sentiment

# Debug mode with custom scoring threshold
python3 spock.py --dry-run --region KR --debug --scoring-threshold 75.0

# Backtest mode for Chinese market
python3 spock.py --backtest --region CN --risk-level aggressive
```

**Output**:
- Log file: `logs/YYYYMMDD_spock.log`
- Exit code: 0 (success), 1 (failure)
- Pipeline summary with candidates scanned/filtered/analyzed/executed

---

## 2. Data Collection

### kis_data_collector.py - OHLCV Data Collector

**Purpose**: Fetch historical OHLCV data from KIS API with technical indicators.

**Arguments**:
- `--db-path PATH`: SQLite database path (default: data/spock_local.db)
- `--region REGION`: Market region (default: KR)
- `--tickers TICKER [TICKER ...]`: Specific tickers to collect (optional)
- `--force-full`: Force full 250-day collection (ignore gap analysis)
- `--retention-days INT`: Data retention period (default: 250)
- `--cleanup`: Run data retention policy cleanup
- `--debug`: Enable debug logging

**Examples**:

```bash
# Collect data for all Stage 0 cached tickers (incremental update)
python3 modules/kis_data_collector.py

# Collect specific tickers (Korean market)
python3 modules/kis_data_collector.py --tickers 005930 000660 035420

# Force full 250-day collection (ignore existing data)
python3 modules/kis_data_collector.py --force-full

# Collect US market data (requires US adapter setup)
python3 modules/kis_data_collector.py --region US --tickers AAPL MSFT GOOGL

# Run data retention cleanup (delete data older than 250 days)
python3 modules/kis_data_collector.py --cleanup --retention-days 250

# Debug mode with custom database path
python3 modules/kis_data_collector.py --debug --db-path /path/to/custom.db
```

**Output**:
- OHLCV data saved to `ohlcv_data` table
- Technical indicators: MA5/20/60/120/200, RSI-14, MACD, BB, ATR, volume_ma20
- Log: Collection statistics (success/failed/skipped)

**Notes**:
- Uses KIS API rate limiting: 20 req/sec, 1,000 req/min
- Automatic retry with exponential backoff
- Gap detection for incremental updates
- Mock mode if credentials not available

---

## 3. Market Adapters

### US Adapter Demo - Polygon.io Integration

**Script**: `examples/us_adapter_demo.py`

**Purpose**: Demonstrate US market data collection using Polygon.io API (legacy).

**Arguments**:
- `--polygon-key KEY`: Polygon.io API key (required)
- `--db-path PATH`: SQLite database path (default: data/spock_local.db)
- `--scan-only`: Only scan tickers, skip OHLCV collection
- `--max-stocks INT`: Maximum stocks to process (default: 100)
- `--days INT`: Historical days to collect (default: 250)

**Examples**:

```bash
# Full demo (scan + OHLCV + fundamentals)
python3 examples/us_adapter_demo.py --polygon-key YOUR_API_KEY

# Scan tickers only (no OHLCV collection)
python3 examples/us_adapter_demo.py --polygon-key YOUR_API_KEY --scan-only

# Collect OHLCV for top 50 stocks
python3 examples/us_adapter_demo.py --polygon-key YOUR_API_KEY --max-stocks 50 --days 250

# Use environment variable for API key
export POLYGON_API_KEY="your_api_key"
python3 examples/us_adapter_demo.py
```

**Output**:
- Ticker scan: NYSE, NASDAQ, AMEX
- OHLCV data with technical indicators
- Company fundamentals (market cap, sector, SIC codes)
- Database verification report

**Rate Limits**: Polygon.io free tier: 5 requests/minute

---

### CN/HK Adapter Demos

**Scripts**: `examples/cn_adapter_demo.py`, `examples/hk_adapter_demo.py`

**Purpose**: Demonstrate China/Hong Kong market data collection.

**Common Arguments**:
- `--db-path PATH`: SQLite database path
- `--scan-only`: Only scan tickers
- `--max-stocks INT`: Maximum stocks to process
- `--days INT`: Historical days to collect

**Examples**:

```bash
# China market demo (AkShare + yfinance)
python3 examples/cn_adapter_demo.py --max-stocks 100

# Hong Kong market demo (yfinance)
python3 examples/hk_adapter_demo.py --scan-only

# Custom database and date range
python3 examples/cn_adapter_demo.py --db-path custom.db --days 500
```

**Similar Demos**:
- `examples/jp_adapter_demo.py` - Japan market (TSE)
- `examples/vn_adapter_demo.py` - Vietnam market (HOSE/HNX)

---

## 4. Deployment Scripts

### deploy_us_adapter.py - US Market Deployment

**Purpose**: Deploy US market adapter with KIS API (Phase 6, 240x faster than Polygon.io).

**Arguments**:
- `--full`: Run full deployment (scan + OHLCV collection)
- `--scan-only`: Scan tickers only (skip OHLCV)
- `--tickers TICKER [TICKER ...]`: Specific tickers to collect
- `--days INT`: Historical days to collect (default: 250)
- `--force-scan`: Force ticker refresh (skip 24h cache)
- `--dry-run`: Validate only (no actual operations)
- `--db-path PATH`: SQLite database path
- `--metrics-port INT`: Prometheus metrics port (default: 8002)

**Examples**:

```bash
# Full deployment (scan ~3,000 stocks + OHLCV collection)
python3 scripts/deploy_us_adapter.py --full --days 250

# Scan tickers only (2-3 minutes)
python3 scripts/deploy_us_adapter.py --scan-only --force-scan

# Collect specific tickers (FAANG stocks)
python3 scripts/deploy_us_adapter.py --tickers AAPL MSFT GOOGL AMZN TSLA --days 250

# Dry run validation (check prerequisites)
python3 scripts/deploy_us_adapter.py --dry-run

# Force cache refresh + metrics on port 8003
python3 scripts/deploy_us_adapter.py --full --force-scan --metrics-port 8003
```

**Output**:
- Deployment log: `logs/us_adapter_deploy_YYYYMMDD_HHMMSS.log`
- Prometheus metrics: `http://localhost:8002/metrics`
- Data quality validation report
- Deployment success/failure status

**Deployment Steps**:
1. Prerequisites validation (DB schema, KIS API connection)
2. Ticker scanning (~3,000 tradable US stocks)
3. OHLCV collection (250 days × 3,000 stocks)
4. Data quality validation (NULL regions, contamination check)

**Performance**:
- Ticker scan: <5 minutes
- OHLCV collection: <5 minutes (20 req/sec)
- Total time: ~10 minutes
- Success rate: >95% target

---

## 5. Testing & Validation

### test_kis_connection.py - KIS API Diagnostics

**Purpose**: Comprehensive KIS API connection testing and diagnostics.

**Arguments**:
- `--basic`: Basic connection test only
- `--latency`: API latency measurement
- `--markets`: Test multiple markets (US, HK, CN, JP, VN)
- `--check-token`: Verify token expiration status

**Examples**:

```bash
# Full diagnostics (all tests)
python3 scripts/test_kis_connection.py

# Basic connection test
python3 scripts/test_kis_connection.py --basic

# Latency measurement
python3 scripts/test_kis_connection.py --latency

# Multi-market validation
python3 scripts/test_kis_connection.py --markets

# Token expiration check
python3 scripts/test_kis_connection.py --check-token
```

**Output**:
- Connection status (✅/❌)
- API latency (p50, p95, p99)
- Token expiration time
- Market accessibility status
- Rate limit validation

---

### validate_kis_credentials.py - Credential Validation

**Purpose**: Validate KIS API credentials and market access.

**Arguments**: None (uses `.env` file)

**Example**:

```bash
# Validate credentials from .env
python3 scripts/validate_kis_credentials.py
```

**Output**:
- ✅ Environment file exists
- ✅ APP_KEY loaded (20 chars)
- ✅ APP_SECRET loaded (40 chars)
- ✅ OAuth token obtained successfully
- ✅ US market data: Accessible
- 🎉 All validation checks passed!

---

### setup_credentials.py - Interactive Setup

**Purpose**: Interactive KIS API credential setup with secure storage.

**Arguments**: None (interactive prompts)

**Example**:

```bash
# Interactive credential setup
python3 scripts/setup_credentials.py
```

**Process**:
1. Prompt for APP_KEY (20 characters)
2. Prompt for APP_SECRET (40 characters)
3. Create `.env` file with secure permissions (600)
4. Update `.gitignore` to exclude credentials
5. Validate credentials with test API call

---

## 6. Demo & Examples

### Trading Engine Test

**Script**: `modules/kis_trading_engine.py` (has `__main__` block)

**Purpose**: Test trading engine with mock orders.

**Example**:

```bash
# Run built-in test (mock mode)
python3 modules/kis_trading_engine.py
```

**Output**:
- Mock buy order for Samsung Electronics (005930)
- Position tracking
- Portfolio management summary

**Note**: No CLI arguments; uses dry_run=True by default.

---

## Common Patterns

### Pattern 1: Incremental Data Update

```bash
# 1. Scan new tickers (Stage 0)
python3 modules/stock_scanner.py --force-refresh

# 2. Collect OHLCV data (incremental, only missing dates)
python3 modules/kis_data_collector.py

# 3. Run technical analysis
python3 spock.py --dry-run --region KR
```

### Pattern 2: Fresh Full Collection

```bash
# Force full 250-day collection for all tickers
python3 modules/kis_data_collector.py --force-full --debug
```

### Pattern 3: Multi-Region Deployment

```bash
# Deploy US market
python3 scripts/deploy_us_adapter.py --full

# Deploy CN market (future Phase 7)
python3 scripts/deploy_cn_adapter.py --full

# Deploy all regions sequentially
for region in US CN HK JP VN; do
    python3 scripts/deploy_${region,,}_adapter.py --full
done
```

### Pattern 4: Monitoring Setup

```bash
# Terminal 1: Start metrics exporter
python3 monitoring/exporters/spock_exporter.py --port 8000

# Terminal 2: Start deployment with metrics
python3 scripts/deploy_us_adapter.py --full --metrics-port 8002

# Terminal 3: Monitor metrics
watch -n 5 "curl -s http://localhost:8002/metrics | grep spock_us"
```

---

## Environment Variables

### Required for KIS API

```bash
# .env file
KIS_APP_KEY=your_20_char_app_key
KIS_APP_SECRET=your_40_char_app_secret
KIS_ACCOUNT_NO=your_account_number  # Optional for data collection
```

### Optional for External APIs

```bash
# Polygon.io (US market, legacy)
POLYGON_API_KEY=your_polygon_api_key

# OpenAI GPT-4 (chart pattern analysis)
OPENAI_API_KEY=your_openai_api_key
```

---

## Error Handling

### Common Issues

1. **KIS API Connection Failed**
   ```bash
   # Validate credentials
   python3 scripts/validate_kis_credentials.py

   # Check token cache
   python3 scripts/check_token_cache.py
   ```

2. **Database Lock Timeout**
   ```bash
   # Check for other processes using database
   lsof data/spock_local.db

   # Kill blocking processes if safe
   kill -9 <PID>
   ```

3. **Rate Limit Exceeded**
   ```bash
   # KIS API: 20 req/sec, 1,000 req/min
   # Wait 60 seconds and retry
   sleep 60 && python3 modules/kis_data_collector.py
   ```

4. **NULL Region Detected**
   ```bash
   # Run region migration script
   python3 scripts/migrate_region_column.py
   ```

---

## Best Practices

### 1. Always Use Dry Run First

```bash
# Test configuration before live trading
python3 spock.py --dry-run --region KR --risk-level moderate
```

### 2. Enable Debug for Troubleshooting

```bash
# Verbose logging for issue diagnosis
python3 modules/kis_data_collector.py --debug --tickers 005930
```

### 3. Validate Credentials Before Deployment

```bash
# Comprehensive validation
python3 scripts/test_kis_connection.py
```

### 4. Monitor Data Quality

```bash
# Check NULL regions and contamination
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); conn = db._get_connection(); \
cursor = conn.cursor(); \
cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL'); \
print(f'NULL regions: {cursor.fetchone()[0]}'); conn.close()"
```

### 5. Regular Database Cleanup

```bash
# Run weekly data retention cleanup
python3 modules/kis_data_collector.py --cleanup --retention-days 250
```

---

## Quick Reference

| Module | Purpose | Example |
|--------|---------|---------|
| `spock.py` | Main pipeline | `python3 spock.py --dry-run --region KR` |
| `kis_data_collector.py` | OHLCV collection | `python3 modules/kis_data_collector.py --tickers 005930` |
| `deploy_us_adapter.py` | US deployment | `python3 scripts/deploy_us_adapter.py --full` |
| `test_kis_connection.py` | API diagnostics | `python3 scripts/test_kis_connection.py` |
| `validate_kis_credentials.py` | Credential check | `python3 scripts/validate_kis_credentials.py` |
| `us_adapter_demo.py` | US demo | `python3 examples/us_adapter_demo.py --polygon-key KEY` |

---

## See Also

- **Architecture**: `spock_architecture.mmd` - System design diagram
- **PRD**: `spock_PRD.md` - Product requirements
- **Setup Guide**: `docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md` - Credential configuration
- **Deployment Guide**: `docs/US_ADAPTER_DEPLOYMENT_GUIDE.md` - US market deployment
- **Monitoring**: `monitoring/README.md` - Prometheus/Grafana setup
- **Phase Reports**: `docs/PHASE*_COMPLETION_REPORT.md` - Implementation progress

---

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review test reports in `test_reports/`
- Consult `CLAUDE.md` for project context
- Validate with `--dry-run` before live operations
