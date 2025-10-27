# Spock Trading System - Troubleshooting Index

**Complete troubleshooting guide for common issues and error resolution**
**Last Updated**: 2025-10-19

---

## Quick Links

- [Common Issues](#common-issues) - Frequent problems and solutions
- [Error Categories](#error-categories) - Organized by error type
- [Troubleshooting Reports](#troubleshooting-reports) - Historical issue investigations
- [Diagnostic Tools](#diagnostic-tools) - Tools for debugging
- [Recovery Procedures](#recovery-procedures) - Automated recovery system

---

## Common Issues

### API Connection Issues

#### Issue: KIS API Connection Failed
**Symptoms**:
- Connection timeout errors
- "401 Unauthorized" responses
- Empty response from API

**Solutions**:
1. **Verify Credentials**:
   ```bash
   python3 scripts/validate_kis_credentials.py
   ```

2. **Check Token Cache**:
   ```bash
   python3 scripts/check_token_cache.py
   ```

3. **Test Connection**:
   ```bash
   python3 scripts/test_kis_connection.py --basic
   ```

**Related Documentation**:
- [KIS API Credential Setup Guide](docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md:1)
- [Token Caching Implementation](docs/TOKEN_CACHING_IMPLEMENTATION.md:1)
- [Token Caching Verification Report](docs/TOKEN_CACHING_VERIFICATION_REPORT.md:1)

---

#### Issue: API Rate Limit Exceeded
**Symptoms**:
- "429 Too Many Requests" errors
- Slow data collection
- Request throttling

**Solutions**:
1. **Check Rate Limit Usage**:
   ```bash
   # View Prometheus metrics
   curl http://localhost:8000/metrics | grep kis_api_rate_limit
   ```

2. **Adjust Rate Limiting**:
   ```python
   # modules/api_clients/base_kis_api.py
   # Default: 20 req/sec, 1,000 req/min
   ```

3. **Use Batch Processing**:
   ```bash
   # Reduce concurrent requests
   python3 spock.py --batch-size 50
   ```

**Related Documentation**:
- [US Adapter Token Limit Issue](docs/US_ADAPTER_TOKEN_LIMIT_ISSUE.md:1)
- [Phase 6 Completion Report](docs/PHASE6_COMPLETION_REPORT.md:1) - KIS API optimization

---

### Data Quality Issues

#### Issue: NULL Region Values in OHLCV Data
**Symptoms**:
- NULL region column in ohlcv_data table
- Cross-region data contamination
- Data integrity validation failures

**Solutions**:
1. **Run Region Migration**:
   ```bash
   python3 scripts/migrate_region_column.py --dry-run
   python3 scripts/migrate_region_column.py  # If dry-run looks good
   ```

2. **Verify Region Propagation**:
   ```bash
   # Check NULL regions
   python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
   db = SQLiteDatabaseManager(); conn = db._get_connection(); \
   cursor = conn.cursor(); \
   cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL'); \
   print(f'NULL regions: {cursor.fetchone()[0]}'); conn.close()"
   ```

**Related Documentation**:
- [Region Propagation Migration Report](docs/REGION_PROPAGATION_MIGRATION_REPORT.md:1)
- [Global DB Architecture Analysis](docs/GLOBAL_DB_ARCHITECTURE_ANALYSIS.md:1)

---

#### Issue: ETF NULL Fields (TER, AUM, Holdings)
**Symptoms**:
- NULL total_expense_ratio (TER)
- NULL assets_under_management (AUM)
- Missing ETF holdings data

**Solutions**:
1. **Check Data Sources**:
   - KOFIA API (primary TER source)
   - KRX API (metadata)
   - Naver Finance (fallback TER)
   - Fund company websites (holdings)

2. **Run ETF Data Collection**:
   ```bash
   python3 modules/kr_etf_collector.py --tickers KODEX200,TIGER200 --include-holdings
   ```

3. **Backfill ETF AUM**:
   ```bash
   python3 scripts/backfill_etf_aum.py --dry-run --rate-limit 1.0
   ```

**Related Documentation**:
- [ETF NULL Fields Troubleshooting Report](docs/ETF_NULL_FIELDS_TROUBLESHOOTING_REPORT.md:1)
- [ETF NULL Columns Analysis Report](docs/ETF_NULL_COLUMNS_ANALYSIS_REPORT.md:1)
- [Alternative TER Data Sources Analysis](docs/ALTERNATIVE_TER_DATA_SOURCES_ANALYSIS.md:1)

---

#### Issue: Hong Kong Lot Size Errors
**Symptoms**:
- Incorrect lot sizes for HK stocks
- Order rejection due to lot size violations
- NULL lot_size values

**Solutions**:
1. **Update Lot Size Data**:
   ```bash
   python3 scripts/update_hk_lot_sizes.py --dry-run
   python3 scripts/update_hk_lot_sizes.py
   ```

2. **Verify Lot Sizes**:
   ```python
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   db = SQLiteDatabaseManager()

   # Check HK lot sizes
   cursor = db._get_connection().cursor()
   cursor.execute("SELECT ticker, lot_size FROM tickers WHERE region='HK' AND lot_size IS NULL")
   print(cursor.fetchall())
   ```

**Related Documentation**:
- [HK Lot Size Fix Completion Report](docs/HK_LOT_SIZE_FIX_COMPLETION_REPORT.md:1)
- [Lot Size Implementation Plan](docs/LOT_SIZE_IMPLEMENTATION_PLAN.md:1)
- [Week 1 Lot Size Completion Report](docs/WEEK1_LOT_SIZE_COMPLETION_REPORT.md:1)

---

### Database Issues

#### Issue: Database Lock Timeout
**Symptoms**:
- "database is locked" errors
- SQLite timeout errors
- Concurrent write failures

**Solutions**:
1. **Check Active Connections**:
   ```bash
   lsof | grep spock_local.db
   ```

2. **Increase Timeout**:
   ```python
   # modules/db_manager_sqlite.py
   conn = sqlite3.connect('data/spock_local.db', timeout=30.0)
   ```

3. **Use Transaction Retry**:
   ```python
   # Auto-recovery system handles this
   from modules.auto_recovery_system import AutoRecoverySystem
   recovery = AutoRecoverySystem(db)
   recovery.recover_from_error('DATABASE_LOCK')
   ```

**Related Documentation**:
- [Auto Cleanup Feature](docs/AUTO_CLEANUP_FEATURE.md:1)
- [Database Schema](docs/DATABASE_SCHEMA.md:1)

---

#### Issue: Database Corruption
**Symptoms**:
- "database disk image is malformed" errors
- Data integrity check failures
- Unexpected query results

**Solutions**:
1. **Run Integrity Check**:
   ```bash
   sqlite3 data/spock_local.db "PRAGMA integrity_check;"
   ```

2. **Restore from Backup**:
   ```bash
   # List available backups
   ls -lh data/backups/

   # Restore from backup
   cp data/backups/backup_20241018.db data/spock_local.db
   ```

3. **Rebuild Database**:
   ```bash
   python3 -c "from spock_init_db import SpockDatabaseInitializer; \
   SpockDatabaseInitializer().initialize_complete_database()"
   ```

**Related Documentation**:
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md:1) - Backup strategies

---

### Trading Execution Issues

#### Issue: Order Rejection (Tick Size Violations)
**Symptoms**:
- "Invalid price" errors
- Order rejection by KIS API
- Tick size compliance failures

**Solutions**:
1. **Check Tick Size Rules**:
   ```yaml
   KR (Korea):
     <10,000 KRW:     5 KRW tick
     10,000-50,000:   10 KRW tick
     50,000-200,000:  50 KRW tick
     200,000-500,000: 100 KRW tick
     500,000+:        1,000 KRW tick
   ```

2. **Enable Tick Size Adjustment**:
   ```python
   from modules.kis_trading_engine import KISTradingEngine
   engine = KISTradingEngine(db, auto_adjust_tick=True)
   ```

3. **Manual Price Adjustment**:
   ```python
   from modules.stock_utils import format_price
   adjusted_price = format_price(70123, region='KR')  # → 70,120
   ```

**Related Documentation**:
- [KIS Trading Engine Design](docs/KIS_TRADING_ENGINE_DESIGN.md:1)
- [Phase 5 Trading Execution Design](PHASE5_TRADING_EXECUTION_DESIGN.md:1)

---

#### Issue: Insufficient Balance
**Symptoms**:
- "Insufficient funds" errors
- Order rejection due to low balance
- Position limit exceeded

**Solutions**:
1. **Check Portfolio Balance**:
   ```bash
   python3 -c "from modules.portfolio_manager import PortfolioManager; \
   from modules.db_manager_sqlite import SQLiteDatabaseManager; \
   pm = PortfolioManager(SQLiteDatabaseManager()); \
   print(pm.get_current_balance())"
   ```

2. **Sync Portfolio with KIS API**:
   ```python
   from modules.kis_trading_engine import KISTradingEngine
   engine = KISTradingEngine(db)
   engine.sync_portfolio()
   ```

3. **Check Position Limits**:
   ```python
   from modules.risk_manager import RiskManager
   rm = RiskManager(db, risk_profile='moderate')
   can_buy = rm.check_position_limit('AAPL', quantity=10)
   ```

**Related Documentation**:
- [Portfolio Allocation System](docs/PORTFOLIO_ALLOCATION_SYSTEM.md:1)
- [Risk Manager Documentation](COMPONENT_REFERENCE.md:154)

---

### Market Adapter Issues

#### Issue: Master File Download Failed
**Symptoms**:
- Empty ticker lists
- Master file parsing errors
- HTTP 404/403 errors

**Solutions**:
1. **Verify Master File URLs**:
   ```bash
   # Test URL accessibility
   curl -I "https://new.real.download.dws.co.kr/common/master/nasdaqlst.cod"
   ```

2. **Force Cache Refresh**:
   ```python
   from modules.api_clients import KISMasterFileManager
   master_mgr = KISMasterFileManager()
   nasdaq_stocks = master_mgr.get_master_data('NASD', force_refresh=True)
   ```

3. **Check Master File Integration**:
   ```bash
   python3 tests/test_master_file_integration.py -v
   ```

**Related Documentation**:
- [KIS Overseas Master File Design](docs/KIS_OVERSEAS_MASTER_FILE_DESIGN.md:1)
- [Master File Integration Summary](docs/MASTER_FILE_INTEGRATION_SUMMARY.md:1)
- [Operational Runbook Master Files](docs/OPERATIONAL_RUNBOOK_MASTER_FILES.md:1)

---

#### Issue: Sector Mapping Errors
**Symptoms**:
- NULL sector values
- Incorrect sector assignments
- Unmapped industry codes

**Solutions**:
1. **Check Sector Mapping Configuration**:
   - Korea: `config/krx_to_gics_mapping.json`
   - China: `config/csrc_to_gics_mapping.json`
   - US: SIC → GICS (native)
   - Japan: TSE 33 → GICS
   - Vietnam: ICB → GICS

2. **Update Sector Mappings**:
   ```python
   from modules.parsers import CNStockParser
   parser = CNStockParser()
   sector = parser.map_sector('白酒')  # → 'Consumer Staples'
   ```

**Related Documentation**:
- [Global Adapter Design](docs/GLOBAL_ADAPTER_DESIGN.md:1)
- [US Stock Parser](COMPONENT_REFERENCE.md:1569)

---

### Monitoring & Metrics Issues

#### Issue: Grafana Dashboard No Data
**Symptoms**:
- Empty Grafana dashboards
- "No data" panels
- Metrics not appearing

**Solutions**:
1. **Check Metrics Exporter**:
   ```bash
   # Verify exporter is running
   curl http://localhost:8000/metrics | grep spock_

   # Restart if needed
   pkill -f spock_exporter
   python3 monitoring/exporters/spock_exporter.py --port 8000 &
   ```

2. **Verify Prometheus Scraping**:
   ```bash
   # Check Prometheus targets
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'
   ```

3. **Restart Monitoring Stack**:
   ```bash
   cd monitoring
   docker-compose down
   docker-compose up -d
   ```

**Related Documentation**:
- [Monitoring README](monitoring/README.md:1)
- [Week 1 Foundation Completion Report](docs/WEEK1_FOUNDATION_COMPLETION_REPORT.md:1)

---

## Error Categories

### 1. API Errors

| Error Code | Description | Auto-Recovery | Manual Fix |
|------------|-------------|---------------|------------|
| **API_TIMEOUT** | Connection timeout | ✅ Yes | Retry with backoff |
| **API_RATE_LIMIT** | Rate limit exceeded | ✅ Yes | Wait and retry |
| **API_AUTH_FAILED** | Authentication failed | ❌ No | Check credentials |
| **API_INVALID_RESPONSE** | Malformed response | ✅ Yes | Retry or fallback |

**Auto-Recovery Actions**:
- `API_RECONNECT`: Reconnect to KIS API
- `API_RATE_LIMIT`: Wait and retry with exponential backoff

---

### 2. Database Errors

| Error Code | Description | Auto-Recovery | Manual Fix |
|------------|-------------|---------------|------------|
| **DATABASE_LOCK** | SQLite lock timeout | ✅ Yes | Close connections |
| **DATABASE_CORRUPTION** | Database corrupted | ❌ No | Restore from backup |
| **DATABASE_CONSTRAINT** | Constraint violation | ❌ No | Fix data, retry |

**Auto-Recovery Actions**:
- `DATABASE_REPAIR`: Run VACUUM and integrity check
- `DATABASE_ROLLBACK`: Rollback failed transaction

---

### 3. Trading Errors

| Error Code | Description | Auto-Recovery | Manual Fix |
|------------|-------------|---------------|------------|
| **ORDER_REJECTED** | Order rejected by API | ❌ No | Check order params |
| **TICK_SIZE_VIOLATION** | Invalid tick size | ✅ Yes | Auto-adjust price |
| **INSUFFICIENT_BALANCE** | Low account balance | ❌ No | Add funds or reduce position |
| **POSITION_LIMIT_EXCEEDED** | Position limit hit | ❌ No | Reduce position size |

**Auto-Recovery Actions**:
- `TICK_SIZE_ADJUSTMENT`: Adjust price to nearest tick
- `ORDER_VALIDATION`: Re-validate order parameters

---

### 4. Data Quality Errors

| Error Code | Description | Auto-Recovery | Manual Fix |
|------------|-------------|---------------|------------|
| **NULL_REGION** | Missing region data | ✅ Yes | Run migration script |
| **NULL_SECTOR** | Missing sector data | ✅ Yes | Update sector mappings |
| **NULL_LOT_SIZE** | Missing lot size | ✅ Yes | Update lot size data |
| **STALE_DATA** | Data not updated | ❌ No | Force data refresh |

**Auto-Recovery Actions**:
- `REGION_INJECTION`: Auto-inject region column
- `SECTOR_MAPPING`: Apply sector mapping rules

---

## Troubleshooting Reports

### Phase Completion Reports
Historical troubleshooting and issue resolution documentation.

#### Phase 1-6 Completion
- [Phase 1 Validation Report](docs/PHASE1_VALIDATION_REPORT.md:1) - Korea market validation
- [Phase 3 Completion Report](docs/PHASE3_COMPLETION_REPORT.md:1) - China/HK integration issues
- [Phase 4 JP Completion Report](docs/PHASE4_JP_COMPLETION_REPORT.md:1) - Japan market issues
- [Phase 5 VN Completion Report](docs/PHASE5_VN_COMPLETION_REPORT.md:1) - Vietnam market issues
- [Phase 6 Completion Report](docs/PHASE6_COMPLETION_REPORT.md:1) - KIS API integration

#### Specific Issue Reports
- [ETF NULL Fields Troubleshooting](docs/ETF_NULL_FIELDS_TROUBLESHOOTING_REPORT.md:1)
- [HK Lot Size Fix](docs/HK_LOT_SIZE_FIX_COMPLETION_REPORT.md:1)
- [Region Propagation Migration](docs/REGION_PROPAGATION_MIGRATION_REPORT.md:1)
- [Token Caching Issues](docs/US_ADAPTER_TOKEN_LIMIT_ISSUE.md:1)
- [Master File Integration](docs/MASTER_FILE_INTEGRATION_TEST_REPORT.md:1)

#### Performance Optimization
- [Phase 3 Performance Optimization](docs/PHASE3_PERFORMANCE_OPTIMIZATION_COMPLETION_REPORT.md:1)
- [Token Caching Improvements](docs/TOKEN_CACHING_IMPROVEMENTS.md:1)

---

## Diagnostic Tools

### Built-in Scripts

#### Credential Validation
```bash
# Validate KIS API credentials
python3 scripts/validate_kis_credentials.py

# Expected output:
# ✅ Environment file exists
# ✅ APP_KEY loaded (20 chars)
# ✅ APP_SECRET loaded (40 chars)
# ✅ OAuth token obtained successfully
# ✅ US market data: Accessible
# 🎉 All validation checks passed!
```

#### Connection Testing
```bash
# Test KIS API connection
python3 scripts/test_kis_connection.py --basic

# Test with latency measurement
python3 scripts/test_kis_connection.py --latency

# Test multiple markets
python3 scripts/test_kis_connection.py --markets
```

#### Database Diagnostics
```bash
# Check database integrity
sqlite3 data/spock_local.db "PRAGMA integrity_check;"

# Check database size
du -h data/spock_local.db

# Check NULL regions
python3 scripts/check_data_quality.py --check-regions

# Check cross-region contamination
python3 scripts/check_data_quality.py --check-contamination
```

#### Token Cache Inspection
```bash
# Check token cache status
python3 scripts/check_token_cache.py

# Expected output:
# Token exists: True
# Expires at: 2024-10-19 23:59:59
# Time remaining: 12h 34m 56s
```

#### Metrics Inspection
```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep spock_

# Check specific metric
curl http://localhost:8000/metrics | grep spock_ohlcv_rows_total

# Check alert status
curl http://localhost:9093/api/v2/alerts | jq '.'
```

---

### Testing Tools

#### Unit Tests
```bash
# Run all tests
pytest

# Test specific adapter
pytest tests/test_us_adapter_kis.py -v

# Test with coverage
pytest --cov=modules --cov-report=html
```

#### Integration Tests
```bash
# Test multi-region integration
pytest tests/test_integration_multi_region.py -v

# Test master file integration
pytest tests/test_master_file_integration.py -v
```

#### E2E Tests
```bash
# Test full pipeline
pytest tests/test_e2e_all_markets.py -v

# Test specific market
pytest tests/test_e2e_us_market.py -v
```

---

## Recovery Procedures

### Automated Recovery System

The `AutoRecoverySystem` handles common errors automatically:

```python
from modules.auto_recovery_system import AutoRecoverySystem
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()
recovery = AutoRecoverySystem(db)

# Automatic recovery for supported errors
# - API_TIMEOUT → Reconnect with exponential backoff
# - API_RATE_LIMIT → Wait and retry
# - DATABASE_LOCK → Retry with backoff
# - TICK_SIZE_VIOLATION → Auto-adjust price
# - NULL_REGION → Auto-inject region column
```

**Supported Recovery Actions**:
- `API_RECONNECT`: Reconnect to KIS API
- `API_RATE_LIMIT`: Wait and retry with backoff
- `ORDER_VALIDATION`: Re-validate order parameters
- `TICK_SIZE_ADJUSTMENT`: Adjust price to nearest tick
- `DATABASE_REPAIR`: Run VACUUM and integrity check
- `PORTFOLIO_SYNC`: Re-sync portfolio with KIS API
- `REGION_INJECTION`: Auto-inject region column

---

### Manual Recovery Steps

#### Full System Recovery

1. **Stop All Processes**:
   ```bash
   pkill -f spock.py
   pkill -f spock_exporter.py
   ```

2. **Backup Database**:
   ```bash
   cp data/spock_local.db data/backups/backup_$(date +%Y%m%d_%H%M%S).db
   ```

3. **Restore from Backup** (if needed):
   ```bash
   # List backups
   ls -lh data/backups/

   # Restore
   cp data/backups/backup_20241018.db data/spock_local.db
   ```

4. **Reinitialize Database** (if needed):
   ```bash
   python3 -c "from spock_init_db import SpockDatabaseInitializer; \
   SpockDatabaseInitializer().initialize_complete_database()"
   ```

5. **Restart Services**:
   ```bash
   # Start monitoring
   cd monitoring && docker-compose up -d

   # Start metrics exporter
   python3 monitoring/exporters/spock_exporter.py --port 8000 &

   # Start main system
   python3 spock.py --dry-run  # Test first
   python3 spock.py --risk-level moderate
   ```

---

## Getting Help

### Documentation Resources
- [PROJECT_INDEX.md](PROJECT_INDEX.md:1) - Complete project navigation
- [COMPONENT_REFERENCE.md](COMPONENT_REFERENCE.md:1) - Module documentation
- [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md:1) - Production deployment
- [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md:1) - Daily operations

### Monitoring Dashboards
- **Grafana**: http://localhost:3000 (admin/spock2025)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### Log Files
- **Application Logs**: `logs/YYYYMMDD_spock.log` (7-day retention)
- **API Logs**: `kis_api_logs` table in database
- **Error Logs**: `failure_tracker` module

---

## Quick Troubleshooting Checklist

When encountering issues, follow this checklist:

- [ ] Check application logs: `tail -f logs/$(ls -t logs/ | head -1)`
- [ ] Verify KIS API credentials: `python3 scripts/validate_kis_credentials.py`
- [ ] Test connection: `python3 scripts/test_kis_connection.py --basic`
- [ ] Check database integrity: `sqlite3 data/spock_local.db "PRAGMA integrity_check;"`
- [ ] Verify NULL regions: `python3 scripts/check_data_quality.py --check-regions`
- [ ] Check monitoring metrics: `curl http://localhost:8000/metrics | grep error`
- [ ] Review recent alerts: `curl http://localhost:9093/api/v2/alerts`
- [ ] Check system resources: `df -h` and `free -h`
- [ ] Verify service status: `docker-compose ps` (for monitoring stack)
- [ ] Review error patterns: Check `failure_tracker` logs

---

**Last Updated**: 2025-10-19
**Maintained By**: Spock Development Team
**For Support**: Refer to [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md:1)
