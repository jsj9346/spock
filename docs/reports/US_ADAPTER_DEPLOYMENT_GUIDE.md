# US Adapter Deployment Guide (Week 2-3)

**Project**: Spock Trading System - Multi-Region Deployment
**Phase**: Week 2-3 - US Market Deployment
**Date**: 2025-10-15
**Status**: 🚀 **READY FOR DEPLOYMENT**

---

## Executive Summary

This guide provides step-by-step instructions for deploying the US market adapter with KIS API integration and Prometheus monitoring.

### Key Features
- ✅ **240x faster** data collection vs Polygon.io (20 req/sec vs 5 req/min)
- ✅ **~3,000 tradable stocks** (Korean investors only)
- ✅ **Integrated monitoring** with Prometheus metrics
- ✅ **Automated deployment** script with validation
- ✅ **Quality gates** for data integrity

### Deployment Timeline
- **Prerequisites**: 5 minutes
- **Ticker Scan**: 2-3 minutes (~3,000 stocks)
- **OHLCV Collection**: 2-3 minutes (250 days × 3,000 stocks)
- **Total Time**: ~10 minutes for complete deployment

---

## Prerequisites

### 1. System Requirements

**Software**:
- Python 3.11+
- KIS API credentials (app_key, app_secret)
- SQLite database with region column
- Monitoring infrastructure running (Prometheus + Grafana)

**Python Packages**:
```bash
pip install prometheus_client psutil pandas pandas-ta
```

### 2. KIS API Credentials Setup

**If you don't have KIS API credentials yet**, follow the complete setup guide:
```bash
# Complete credential registration and setup guide
docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md
```

**Quick credential setup (interactive helper)**:
```bash
# Interactive credential setup with secure storage
python3 scripts/setup_credentials.py

# This will:
# 1. Prompt for APP_KEY and APP_SECRET
# 2. Create .env file with secure permissions (600)
# 3. Update .gitignore to exclude credentials
# 4. Guide you through validation steps
```

**Manual `.env` file creation**:
```bash
# Create .env file in project root
cat > ~/spock/.env << 'EOF'
# KIS API Credentials
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
EOF

# Set secure permissions (owner read/write only)
chmod 600 ~/spock/.env
```

**Validate credentials**:
```bash
# Validate KIS API credentials and test connectivity
python3 scripts/validate_kis_credentials.py

# Expected output:
# ✅ Environment file exists
# ✅ APP_KEY loaded (20 chars)
# ✅ APP_SECRET loaded (40 chars)
# ✅ OAuth token obtained successfully
# ✅ US market data: Accessible
# 🎉 All validation checks passed!
```

### 3. Database Validation

Verify database has region column:
```bash
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(ohlcv_data)')
columns = [row[1] for row in cursor.fetchall()]
print('✅ Region column exists' if 'region' in columns else '❌ Region column missing')
conn.close()
"
```

Expected output: `✅ Region column exists`

### 4. Monitoring Stack

Ensure monitoring infrastructure is running:
```bash
# Check Prometheus
curl http://localhost:9090/-/healthy

# Check Grafana
curl http://localhost:3000/api/health

# Start if needed
cd monitoring && docker-compose up -d
```

---

## Deployment Steps

### Quick Deployment (Recommended)

**Full deployment with monitoring**:
```bash
cd ~/spock

# Run full deployment (scan + OHLCV collection)
python3 scripts/deploy_us_adapter.py --full --force-scan --days 250
```

This will:
1. ✅ Validate prerequisites
2. ✅ Scan ~3,000 US stocks from KIS API
3. ✅ Collect 250 days of OHLCV data
4. ✅ Calculate technical indicators
5. ✅ Validate data quality
6. ✅ Expose Prometheus metrics on port 8002

**Estimated time**: 10 minutes

### Step-by-Step Deployment

#### Step 1: Validate Prerequisites

```bash
python3 scripts/deploy_us_adapter.py --dry-run
```

Expected output:
```
🔍 Validating prerequisites...
✅ Database exists: /Users/13ruce/spock/data/spock_local.db
✅ KIS API connection successful
📊 US Market Status: OPEN/CLOSED
✅ Database schema has region column
```

If all checks pass, proceed to Step 2.

#### Step 2: Scan US Stocks

```bash
python3 scripts/deploy_us_adapter.py --scan-only --force-scan
```

Expected output:
```
📊 Scanning US stocks (KIS API, tradable only)...
📡 Fetching tradable tickers from NASD...
✅ NASD: 2,000 tradable tickers
📡 Fetching tradable tickers from NYSE...
✅ NYSE: 800 tradable tickers
📡 Fetching tradable tickers from AMEX...
✅ AMEX: 200 tradable tickers
💾 Saving 3,000 US stocks to database...
✅ US stock scan complete: 3,000 stocks
   NASDAQ: 2,000 stocks
   NYSE: 800 stocks
   AMEX: 200 stocks
```

#### Step 3: Collect OHLCV Data (Test with Sample Tickers)

Test with a few tickers first:
```bash
python3 scripts/deploy_us_adapter.py \
  --tickers AAPL MSFT GOOGL TSLA AMZN \
  --days 250
```

Expected output:
```
📈 Collecting OHLCV for 5 tickers (250 days)...
✅ [AAPL] 250 days saved
✅ [MSFT] 250 days saved
✅ [GOOGL] 250 days saved
✅ [TSLA] 250 days saved
✅ [AMZN] 250 days saved
✅ OHLCV collection complete: 5/5 (100.0%)
```

#### Step 4: Full OHLCV Collection

Once testing passes, collect all tickers:
```bash
python3 scripts/deploy_us_adapter.py --full --days 250
```

**Note**: This will take ~2-3 minutes for ~3,000 stocks at 20 req/sec.

Expected output:
```
📈 Collecting OHLCV for 3,000 US stocks (250 days)...
📦 Batch 1/30: 100 tickers
✅ Batch 1 complete: 98 success, 2 failed
📦 Batch 2/30: 100 tickers
...
✅ OHLCV collection complete: 2,950/3,000 (98.3%)
```

#### Step 5: Data Quality Validation

Validation runs automatically at the end of deployment:
```bash
🔍 Validating data quality...
📊 Data Quality Validation:
   Total US OHLCV rows: 737,500
   Unique tickers: 2,950
   NULL regions: 0 ✅
   Cross-region contamination: 0 ✅
   Date range: 2024-04-01 to 2025-10-15
✅ Data quality validation PASSED
```

---

## Monitoring Integration

### Prometheus Metrics

The deployment script exposes real-time metrics on port 8002:

**Data Collection Metrics**:
- `spock_us_scan_attempts_total`: Ticker scan attempts
- `spock_us_scan_success_total`: Successful ticker scans
- `spock_us_scan_tickers_total`: Total tickers scanned
- `spock_us_ohlcv_attempts_total`: OHLCV collection attempts
- `spock_us_ohlcv_success_total`: Successful collections
- `spock_us_ohlcv_failed_total`: Failed collections

**API Metrics**:
- `spock_us_api_requests_total{endpoint}`: API requests by endpoint
- `spock_us_api_errors_total{endpoint}`: API errors by endpoint
- `spock_us_api_latency_seconds{endpoint}`: API latency histogram

**Access Metrics**:
```bash
curl http://localhost:8002/metrics | grep spock_us
```

### Grafana Dashboard

**Access US Dashboard**:
1. Open Grafana: http://localhost:3000
2. Navigate to "Spock Trading System - US" dashboard
3. Verify panels show data:
   - Total OHLCV rows
   - Unique tickers
   - Adapter status (UP)
   - Data collection rate
   - API latency
   - API error rate

**Expected Metrics**:
- OHLCV rows: ~737,500 (250 days × 2,950 tickers)
- Unique tickers: ~2,950
- Adapter status: UP
- Data collection rate: 98%+
- API latency (p95): <500ms
- API error rate: <5%

### Alert Validation

Check that alerts are not firing:
```bash
# Check Prometheus alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.labels.region == "US")'

# Expected: No active alerts
```

---

## Troubleshooting

### Issue 0: Missing or Invalid Credentials

**Symptom**: `❌ KIS credentials not found in .env` or `❌ OAuth token failed`

**Solutions**:

1. **Check if .env file exists**:
   ```bash
   ls -la ~/spock/.env
   # Should show: -rw------- (permissions 600)
   ```

2. **Validate credentials format**:
   ```bash
   python3 scripts/validate_kis_credentials.py

   # This will check:
   # - .env file exists
   # - APP_KEY is 20 characters
   # - APP_SECRET is 40 characters
   # - OAuth token can be obtained
   # - Market data is accessible
   ```

3. **Interactive credential setup**:
   ```bash
   # Use setup helper for secure credential storage
   python3 scripts/setup_credentials.py

   # This will guide you through:
   # - Entering APP_KEY (20 chars)
   # - Entering APP_SECRET (40 chars, hidden input)
   # - Creating .env file
   # - Setting secure permissions
   # - Updating .gitignore
   ```

4. **Test connection**:
   ```bash
   # Run connection diagnostics
   python3 scripts/test_kis_connection.py

   # Or test specific components:
   python3 scripts/test_kis_connection.py --basic      # Basic connection
   python3 scripts/test_kis_connection.py --latency    # API latency
   python3 scripts/test_kis_connection.py --markets    # Multiple markets
   ```

5. **Get new credentials**:
   - See complete guide: `docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md`
   - KIS API Portal: https://apiportal.koreainvestment.com
   - Navigate: My Page → App Management → View App

### Issue 1: KIS API Connection Failed

**Symptom**: `❌ KIS API connection failed` (after credentials validated)

**Solutions**:
1. Check network connectivity:
   ```bash
   curl -I https://openapi.koreainvestment.com:9443
   ```

2. Check if overseas trading enabled:
   - Login to KIS HTS
   - Enable overseas trading permission
   - Menu: 해외주식 → 해외주식 신청

3. Verify token not expired:
   ```bash
   python3 scripts/test_kis_connection.py --check-token
   ```

### Issue 2: No Tickers Scanned

**Symptom**: `⚠️ No US stocks found`

**Solutions**:
1. Check market hours (US market: 09:30-16:00 ET)

2. Force cache refresh:
   ```bash
   python3 scripts/deploy_us_adapter.py --scan-only --force-scan
   ```

3. Test single exchange:
   ```python
   from modules.market_adapters.us_adapter_kis import USAdapterKIS
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   import os
   from dotenv import load_dotenv

   load_dotenv()
   db = SQLiteDatabaseManager()
   adapter = USAdapterKIS(db, os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))
   stocks = adapter.scan_stocks(exchanges=['NASD'], max_count=10)
   print(f"Found {len(stocks)} NASDAQ stocks")
   ```

### Issue 3: OHLCV Collection Slow

**Symptom**: Collection taking >5 minutes

**Solutions**:
1. Check API rate limiting:
   ```bash
   # Monitor API latency
   curl http://localhost:8002/metrics | grep spock_us_api_latency
   ```

2. Reduce concurrency (if rate limited):
   - KIS API limit: 20 req/sec
   - Default delay: 50ms (20 req/sec)
   - Increase delay if needed

3. Collect in smaller batches:
   ```bash
   # Collect top 500 tickers first
   python3 scripts/deploy_us_adapter.py \
     --tickers $(head -500 tickers.txt) \
     --days 250
   ```

### Issue 4: Data Quality Validation Failed

**Symptom**: `❌ Data quality validation FAILED`

**Check NULL regions**:
```bash
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL')
null_count = cursor.fetchone()[0]
print(f'NULL regions: {null_count}')
if null_count > 0:
    cursor.execute('SELECT DISTINCT ticker FROM ohlcv_data WHERE region IS NULL LIMIT 10')
    print('Sample tickers with NULL region:', [row[0] for row in cursor.fetchall()])
conn.close()
"
```

**Fix NULL regions** (if found):
```bash
python3 scripts/migrate_region_column.py
```

**Check cross-region contamination**:
```bash
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()
cursor.execute('''
    SELECT ticker, GROUP_CONCAT(DISTINCT region) as regions
    FROM ohlcv_data
    WHERE ticker IN (SELECT ticker FROM tickers WHERE region = \"US\")
    GROUP BY ticker
    HAVING COUNT(DISTINCT region) > 1
    LIMIT 10
''')
contaminated = cursor.fetchall()
if contaminated:
    print('Contaminated tickers:', contaminated)
else:
    print('No contamination found')
conn.close()
"
```

### Issue 5: Monitoring Dashboard Not Showing Data

**Symptom**: US dashboard panels show "No data"

**Solutions**:
1. Check metrics exporter is running:
   ```bash
   curl http://localhost:8000/metrics | grep spock_ohlcv_rows_total
   ```

2. Verify Prometheus is scraping:
   ```bash
   # Check targets
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job == "spock_us_adapter")'
   ```

3. Restart exporter:
   ```bash
   pkill -f spock_exporter.py
   python3 monitoring/exporters/spock_exporter.py --port 8000 &
   ```

4. Check Grafana data source:
   - Grafana → Configuration → Data Sources
   - Click "Test" on Prometheus
   - Should show "Data source is working"

---

## Performance Benchmarks

### Target Metrics

| Metric | Target | Actual (Expected) |
|--------|--------|-------------------|
| Ticker scan time | <5 min | ~2.5 min (3,000 stocks) |
| OHLCV collection time | <5 min | ~2.5 min (250 days × 3,000 stocks) |
| API latency (p95) | <500ms | ~200-300ms |
| Data collection success rate | >95% | ~98% |
| API error rate | <5% | <1% |
| NULL regions | 0 | 0 |
| Cross-region contamination | 0 | 0 |

### KIS API vs Polygon.io Comparison

| Feature | KIS API (20 req/sec) | Polygon.io (5 req/min) | Speed Improvement |
|---------|---------------------|------------------------|-------------------|
| Ticker scan | ~2.5 min | ~10 hours | **240x faster** |
| OHLCV collection | ~2.5 min | ~10 hours | **240x faster** |
| Total deployment | ~10 min | ~20 hours | **120x faster** |
| Tradable tickers | ~3,000 | ~8,000 | 60% fewer (more relevant) |
| API key management | Single KIS key | Separate Polygon key | Unified |

---

## Next Steps (Week 4-6)

After successful US deployment:

1. **CN/HK Deployment** (Week 4-5):
   - Deploy China adapter (KIS API, 13x faster)
   - Deploy Hong Kong adapter (KIS API, 20x faster)
   - Validate cross-market data integrity

2. **JP Deployment** (Week 6):
   - Deploy Japan adapter (KIS API, 20x faster)
   - TSE market integration
   - Sector mapping validation

3. **Performance Optimization** (Week 6):
   - Fine-tune alert thresholds based on actual metrics
   - Optimize data collection batch sizes
   - Implement adaptive rate limiting

4. **Multi-Region Portfolio** (Week 7-8):
   - Cross-market correlation analysis
   - Multi-region portfolio optimization
   - Global market sentiment integration

---

## Appendix A: Deployment Script Reference

### Command-Line Options

```
python3 scripts/deploy_us_adapter.py [OPTIONS]

Options:
  --full               Run full deployment (scan + OHLCV collection)
  --scan-only          Scan tickers only (skip OHLCV collection)
  --tickers AAPL MSFT  Specific tickers to collect
  --days 250           Historical days to collect (default: 250)
  --force-scan         Force ticker refresh (skip cache)
  --dry-run            Validate only (no actual operations)
  --db-path PATH       Path to SQLite database
  --metrics-port 8002  Prometheus metrics port (default: 8002)
```

### Usage Examples

**Dry run validation**:
```bash
python3 scripts/deploy_us_adapter.py --dry-run
```

**Scan tickers only**:
```bash
python3 scripts/deploy_us_adapter.py --scan-only --force-scan
```

**Collect specific tickers**:
```bash
python3 scripts/deploy_us_adapter.py \
  --tickers AAPL MSFT GOOGL AMZN TSLA \
  --days 250
```

**Full deployment**:
```bash
python3 scripts/deploy_us_adapter.py --full --days 250
```

**Test deployment (small subset)**:
```bash
python3 scripts/deploy_us_adapter.py --full --days 30
```

---

## Appendix B: Database Schema

### US Market Tables

**tickers table** (US stocks):
```sql
SELECT ticker, name, exchange, region, kis_exchange_code, is_active
FROM tickers
WHERE region = 'US'
LIMIT 5;

-- Example output:
-- AAPL  | Apple Inc.           | NASDAQ | US | NASD | 1
-- MSFT  | Microsoft Corporation| NASDAQ | US | NASD | 1
-- GOOGL | Alphabet Inc.        | NASDAQ | US | NASD | 1
-- TSLA  | Tesla Inc.           | NASDAQ | US | NASD | 1
-- AMZN  | Amazon.com Inc.      | NASDAQ | US | NASD | 1
```

**ohlcv_data table** (US market data):
```sql
SELECT ticker, region, date, open, high, low, close, volume
FROM ohlcv_data
WHERE region = 'US' AND ticker = 'AAPL'
ORDER BY date DESC
LIMIT 5;

-- Example output:
-- AAPL | US | 2025-10-15 | 175.50 | 178.20 | 175.00 | 177.80 | 52000000
-- AAPL | US | 2025-10-14 | 174.00 | 176.50 | 173.50 | 175.50 | 48000000
-- ...
```

**Expected row counts** (250 days × ~3,000 stocks):
- Total OHLCV rows: ~750,000
- Unique tickers: ~3,000
- Date range: ~250 days (1 year of trading days)

---

**Deployment Guide Version**: 1.0.0
**Last Updated**: 2025-10-15
**Status**: ✅ Ready for Production Deployment

**Related Documentation**:
- Week 1 Foundation: `docs/WEEK1_FOUNDATION_COMPLETION_REPORT.md`
- Multi-Region Design: `docs/MULTI_REGION_DEPLOYMENT_DESIGN.md`
- Monitoring Setup: `monitoring/README.md`
