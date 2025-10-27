# Spock Trading System - Deployment Guide

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Phase**: Phase 3 - Validation & Monitoring

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Installation Steps](#installation-steps)
4. [Configuration](#configuration)
5. [Phase 3 Components Deployment](#phase-3-components-deployment)
6. [Verification](#verification)
7. [Post-Deployment Tasks](#post-deployment-tasks)
8. [Troubleshooting](#troubleshooting)
9. [Rollback Procedures](#rollback-procedures)

---

## System Requirements

### Hardware Requirements

**Minimum Specifications**:
- CPU: 2 cores (Intel/AMD x86_64)
- RAM: 4 GB
- Disk: 10 GB free space (SSD recommended)
- Network: Stable internet connection (≥10 Mbps)

**Recommended Specifications**:
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 50+ GB free space (SSD)
- Network: ≥50 Mbps

### Software Requirements

**Operating System**:
- macOS 10.15+ (Catalina or later)
- Linux (Ubuntu 20.04+, CentOS 8+, or equivalent)
- Windows 10+ (with WSL2 for Linux compatibility)

**Required Software**:
- Python 3.11 or higher
- SQLite 3.35+
- Git 2.30+

**Optional Software**:
- Docker 20.10+ (for containerized deployment)
- Nginx/Apache (for production dashboard hosting)

### Python Dependencies

See `requirements.txt` for complete list:
```bash
pandas==2.0.3
numpy==1.24.3
pandas-ta==0.3.14b0
psutil==5.9.0
python-dotenv==1.0.0
PyYAML==6.0
PyJWT==2.8.0
```

---

## Pre-Deployment Checklist

### 1. Environment Preparation

- [ ] Python 3.11+ installed and configured
- [ ] Virtual environment created and activated
- [ ] Git repository cloned
- [ ] Network access to KIS API endpoints verified
- [ ] Firewall rules configured (if applicable)

### 2. Credentials and Configuration

- [ ] KIS API credentials obtained (APP_KEY, APP_SECRET)
- [ ] `.env` file created with credentials
- [ ] File permissions set correctly (600 for .env)
- [ ] API credentials validated

### 3. Database Setup

- [ ] SQLite database directory exists (`data/`)
- [ ] Backup directory created (`data/backups/`)
- [ ] Database initialization completed
- [ ] Migration scripts executed (if upgrading)

### 4. Monitoring Infrastructure

- [ ] Metrics directory created (`metrics_reports/`)
- [ ] Alert logs directory created (`alert_logs/`)
- [ ] Monitoring dashboard directory exists (`monitoring/`)
- [ ] Log directory configured (`logs/`)

---

## Installation Steps

### Step 1: Clone Repository

```bash
# Clone repository
cd ~/
git clone <repository-url> spock
cd spock

# Verify directory structure
ls -la
```

**Expected Output**:
```
config/
data/
docs/
logs/
modules/
monitoring/
scripts/
tests/
requirements.txt
README.md
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows (WSL):
source venv/bin/activate
```

**Verification**:
```bash
which python3
# Expected: /Users/13ruce/spock/venv/bin/python3
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Verify installation
pip list | grep -E 'pandas|numpy|psutil'
```

**Expected Output**:
```
pandas         2.0.3
numpy          1.24.3
psutil         5.9.0
```

### Step 4: Configure Credentials

```bash
# Create .env file
cat > .env << 'EOF'
# KIS API Credentials
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=your_account_number_here
KIS_CANO=your_cano_here
KIS_ACNT_PRDT_CD=your_product_code_here

# API Endpoints
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
KIS_WEBSOCKET_URL=ws://ops.koreainvestment.com:21000

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF

# Set secure permissions
chmod 600 .env

# Verify permissions
ls -l .env
# Expected: -rw------- 1 user group 456 Oct 16 10:00 .env
```

**Important**: Replace placeholder values with actual credentials from KIS Developer Portal.

### Step 5: Initialize Database

```bash
# Create database directories
mkdir -p data/backups

# Initialize database schema
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
print('Database initialized successfully')"
```

**Verification**:
```bash
# Check database file
ls -lh data/spock_local.db
# Expected: -rw-r--r-- 1 user group 243M Oct 16 10:00 data/spock_local.db

# Check schema
sqlite3 data/spock_local.db "SELECT name FROM sqlite_master WHERE type='table';" | head -10
```

**Expected Tables**:
- tickers
- ohlcv_data
- technical_analysis
- trades
- portfolio
- kis_api_logs
- filter_cache_stage0
- exchange_rate_history
- (and more...)

---

## Configuration

### 1. API Configuration

**File**: `config/kis_api_config.py`

Verify API configuration:
```bash
python3 -c "from config.kis_api_config import KISAPIConfig; \
config = KISAPIConfig(); \
print(f'Base URL: {config.base_url}'); \
print(f'Environment: {config.environment}')"
```

### 2. Market Schedule Configuration

**Files**: `config/market_schedule.json`, `config/*_holidays.yaml`

Verify market schedules:
```bash
# Check Korean market schedule
python3 -c "import json; \
data = json.load(open('config/market_schedule.json')); \
print(f'KR trading hours: {data[\"KR\"][\"trading_hours\"]}')"
```

### 3. Logging Configuration

**Directory**: `logs/`

Configure log rotation:
```bash
# Create log directory
mkdir -p logs

# Set log level in .env
echo "LOG_LEVEL=INFO" >> .env
```

**Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

---

## Phase 3 Components Deployment

### Component 1: Metrics Collection System

**Purpose**: Real-time system metrics collection

**Deployment**:
```bash
# Test metrics collector
python3 modules/metrics_collector.py

# Expected output:
# ======================================================================
# Metrics Collection System - Live Demo
# ======================================================================
# 📊 Collecting all metrics...
# Overall Status: HEALTHY
# Overall Health Score: 95.0/100
```

**Verify Output**:
```bash
# Check metrics file
ls -lh metrics_reports/metrics_*.json | tail -1
```

### Component 2: Monitoring Dashboard

**Purpose**: Web-based metrics visualization

**Deployment**:

**Option A: Static File Server** (Development)
```bash
# Generate fresh metrics
python3 monitoring/serve_dashboard.py --generate-only

# Open dashboard in browser
open monitoring/dashboard.html
# Or: file:///Users/13ruce/spock/monitoring/dashboard.html
```

**Option B: Python HTTP Server** (Testing)
```bash
# Start dashboard server
python3 monitoring/serve_dashboard.py --port 8080

# Access dashboard
# URL: http://localhost:8080/dashboard.html
```

**Option C: Production Server** (Production)

For production deployment with Nginx:

```nginx
# /etc/nginx/sites-available/spock-monitoring
server {
    listen 80;
    server_name monitoring.spock.local;

    root /Users/13ruce/spock/monitoring;
    index dashboard.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /metrics_reports/ {
        alias /Users/13ruce/spock/metrics_reports/;
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }
}
```

Enable and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/spock-monitoring /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Component 3: Alert System

**Purpose**: Threshold-based alerting

**Deployment**:
```bash
# Test alert system
python3 modules/alert_system.py

# Expected output:
# ======================================================================
# Alert System - Live Demo
# ======================================================================
# 🔍 Checking all metrics against thresholds...
```

**Configure Alert Thresholds** (Optional):

Create custom threshold configuration:
```bash
cat > config/alert_thresholds.json << 'EOF'
{
  "api": {
    "error_rate_warning": 5.0,
    "error_rate_critical": 20.0,
    "latency_warning": 500.0,
    "latency_critical": 1000.0
  },
  "system": {
    "cpu_warning": 70.0,
    "cpu_critical": 85.0,
    "memory_warning": 70.0,
    "memory_critical": 85.0,
    "disk_warning": 80.0,
    "disk_critical": 90.0
  }
}
EOF
```

Load custom thresholds:
```python
from modules.alert_system import AlertSystem
alert_system = AlertSystem(config_file='config/alert_thresholds.json')
```

### Component 4: Data Quality Validation

**Purpose**: Automated data quality checks

**Deployment**:
```bash
# Run data quality validation
python3 scripts/validate_data_quality.py

# Expected output:
# ======================================================================
# Validation Summary
# ======================================================================
# Total Checks: 7
# Passed: 7
# Failed: 0
# Overall Pass Rate: 100.0%
```

**Schedule Automated Validation** (Optional):

Add to crontab for daily validation:
```bash
# Edit crontab
crontab -e

# Add daily validation at 1 AM
0 1 * * * cd /Users/13ruce/spock && /Users/13ruce/spock/venv/bin/python3 scripts/validate_data_quality.py >> logs/validation.log 2>&1
```

---

## Verification

### 1. System Health Check

Run comprehensive system check:
```bash
# Create verification script
cat > scripts/verify_deployment.sh << 'EOF'
#!/bin/bash
echo "======================================================================="
echo "Spock Trading System - Deployment Verification"
echo "======================================================================="

# Check Python version
echo -e "\n1. Python Version:"
python3 --version

# Check virtual environment
echo -e "\n2. Virtual Environment:"
which python3

# Check dependencies
echo -e "\n3. Critical Dependencies:"
pip list | grep -E 'pandas|numpy|psutil'

# Check database
echo -e "\n4. Database:"
ls -lh data/spock_local.db 2>/dev/null && echo "✅ Database exists" || echo "❌ Database not found"

# Check credentials
echo -e "\n5. Credentials:"
[ -f .env ] && echo "✅ .env file exists" || echo "❌ .env file not found"

# Check metrics directory
echo -e "\n6. Metrics Directory:"
ls -ld metrics_reports/ 2>/dev/null && echo "✅ Metrics directory exists" || echo "❌ Metrics directory not found"

# Test metrics collection
echo -e "\n7. Metrics Collection Test:"
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
metrics = collector.collect_all_metrics(); \
print(f'✅ Metrics collected: {len(metrics)} categories')"

# Test alert system
echo -e "\n8. Alert System Test:"
python3 -c "from modules.alert_system import AlertSystem; \
alert_system = AlertSystem(); \
print('✅ Alert system initialized')"

echo -e "\n======================================================================="
echo "Deployment Verification Complete"
echo "======================================================================="
EOF

chmod +x scripts/verify_deployment.sh
./scripts/verify_deployment.sh
```

**Expected Output**:
```
=======================================================================
Spock Trading System - Deployment Verification
=======================================================================

1. Python Version:
Python 3.11.x

2. Virtual Environment:
/Users/13ruce/spock/venv/bin/python3

3. Critical Dependencies:
pandas         2.0.3
numpy          1.24.3
psutil         5.9.0

4. Database:
✅ Database exists

5. Credentials:
✅ .env file exists

6. Metrics Directory:
✅ Metrics directory exists

7. Metrics Collection Test:
✅ Metrics collected: 5 categories

8. Alert System Test:
✅ Alert system initialized

=======================================================================
Deployment Verification Complete
=======================================================================
```

### 2. API Connectivity Test

```bash
# Test KIS API connection
python3 scripts/test_kis_connection.py --basic

# Expected output:
# ✅ Connection successful
# ✅ OAuth token obtained
# ✅ API accessible
```

### 3. Dashboard Accessibility Test

```bash
# Generate fresh metrics
python3 monitoring/serve_dashboard.py --generate-only

# Verify metrics file
ls -l metrics_reports/metrics_latest.json

# Check if symlink is correct
readlink metrics_reports/metrics_latest.json
# Expected: metrics_YYYYMMDD_HHMMSS.json
```

### 4. Data Quality Baseline

```bash
# Run initial data quality validation
python3 scripts/validate_data_quality.py --output validation_reports/baseline.json

# Check results
cat validation_reports/baseline.json | python3 -m json.tool | grep -A5 '"summary"'
```

---

## Post-Deployment Tasks

### 1. Performance Baseline

Establish performance baselines:
```bash
# Run performance benchmark
python3 scripts/benchmark_performance.py

# Save as baseline
cp benchmark_reports/performance_*.json benchmark_reports/baseline.json
```

### 2. Monitoring Setup

**Daily Metrics Collection** (Automated):
```bash
# Add to crontab
crontab -e

# Collect metrics every 30 minutes
*/30 * * * * cd /Users/13ruce/spock && /Users/13ruce/spock/venv/bin/python3 -c "from modules.metrics_collector import MetricsCollector; MetricsCollector().save_metrics()" >> logs/metrics.log 2>&1

# Run alerts every hour
0 * * * * cd /Users/13ruce/spock && /Users/13ruce/spock/venv/bin/python3 modules/alert_system.py >> logs/alerts.log 2>&1
```

### 3. Backup Configuration

**Database Backup** (Daily):
```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * cd /Users/13ruce/spock && tar -czf data/backups/spock_db_$(date +\%Y\%m\%d).tar.gz data/spock_local.db && find data/backups/ -name "spock_db_*.tar.gz" -mtime +7 -delete
```

### 4. Log Rotation

**Configure Log Rotation**:
```bash
# Create logrotate config (Linux)
sudo cat > /etc/logrotate.d/spock << 'EOF'
/Users/13ruce/spock/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 user group
}
EOF
```

**macOS Alternative** (using newsyslog):
```bash
# Add to /etc/newsyslog.conf
sudo echo "/Users/13ruce/spock/logs/*.log 644 7 * 24 GZ" >> /etc/newsyslog.conf
```

---

## Troubleshooting

### Issue 1: Database Initialization Fails

**Symptoms**:
```
FileNotFoundError: Database not found: data/spock_local.db
```

**Solution**:
```bash
# Create data directory
mkdir -p data

# Initialize database manually
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
print('Database initialized')"

# Verify
ls -lh data/spock_local.db
```

### Issue 2: Metrics Collection Fails

**Symptoms**:
```
sqlite3.OperationalError: no such table: kis_api_logs
```

**Solution**:
```bash
# Check if table exists
sqlite3 data/spock_local.db "SELECT name FROM sqlite_master WHERE type='table' AND name='kis_api_logs';"

# If table doesn't exist, recreate schema
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
db._create_tables()"
```

### Issue 3: Dashboard Not Loading Metrics

**Symptoms**:
- Dashboard shows "Error Loading Metrics"
- Browser console shows 404 error

**Solution**:
```bash
# Regenerate metrics_latest.json symlink
cd metrics_reports
rm -f metrics_latest.json

# Find latest metrics file
latest=$(ls -t metrics_*.json | head -1)

# Create symlink
ln -s "$latest" metrics_latest.json

# Verify
ls -l metrics_latest.json
readlink metrics_latest.json
```

### Issue 4: Alert System Not Sending Alerts

**Symptoms**:
- Alert system runs but no alerts generated
- No alert files in alert_logs/

**Solution**:
```bash
# Check if alert_logs directory exists
mkdir -p alert_logs

# Run alert system with verbose output
python3 modules/alert_system.py

# Check alert suppression
# Alerts may be suppressed if triggered within 15-minute window
# Wait 15 minutes and re-run
```

### Issue 5: Permission Denied Errors

**Symptoms**:
```
PermissionError: [Errno 13] Permission denied: 'data/spock_local.db'
```

**Solution**:
```bash
# Fix file permissions
chmod 644 data/spock_local.db
chmod 755 data/

# Fix directory permissions
chmod 755 metrics_reports/
chmod 755 alert_logs/
chmod 755 logs/

# Verify
ls -ld data/ metrics_reports/ alert_logs/ logs/
```

### Issue 6: API Credentials Invalid

**Symptoms**:
```
Unauthorized: Invalid credentials
```

**Solution**:
```bash
# Verify credentials in .env
cat .env | grep KIS_

# Check file permissions
ls -l .env
# Should be: -rw------- (600)

# Re-validate credentials
python3 scripts/validate_kis_credentials.py

# If invalid, obtain new credentials from KIS Developer Portal
# Update .env file with new credentials
```

---

## Rollback Procedures

### Rollback to Previous Version

**Before Rollback**:
1. Backup current database
2. Save current configuration files
3. Document current metrics baseline

**Rollback Steps**:

```bash
# 1. Stop all running processes
pkill -f "python3.*spock"

# 2. Backup current version
cd ~/
mv spock spock_backup_$(date +%Y%m%d)

# 3. Restore previous version
git clone <repository-url> spock
cd spock
git checkout <previous-commit-hash>

# 4. Restore database
cp ~/spock_backup_*/data/spock_local.db data/

# 5. Restore configuration
cp ~/spock_backup_*/.env .
cp -r ~/spock_backup_*/config/* config/

# 6. Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt

# 7. Verify
./scripts/verify_deployment.sh
```

### Database Rollback

**Restore from backup**:
```bash
# List available backups
ls -lh data/backups/

# Restore specific backup
cp data/backups/spock_db_20251015.tar.gz .
tar -xzf spock_db_20251015.tar.gz

# Verify restoration
sqlite3 data/spock_local.db "SELECT COUNT(*) FROM ohlcv_data;"
```

---

## Deployment Checklist

**Pre-Deployment**:
- [ ] System requirements met
- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Credentials configured
- [ ] Database initialized

**Deployment**:
- [ ] All Phase 3 components deployed
- [ ] Metrics collection tested
- [ ] Dashboard accessible
- [ ] Alert system configured
- [ ] Data quality validation passed

**Post-Deployment**:
- [ ] Performance baseline established
- [ ] Monitoring automation configured
- [ ] Backup schedule set
- [ ] Log rotation enabled
- [ ] Verification tests passed

**Production Readiness**:
- [ ] All health checks green
- [ ] API connectivity confirmed
- [ ] Dashboard functional
- [ ] Alerts configured
- [ ] Documentation complete
- [ ] Team training completed

---

## Support and Maintenance

### Documentation
- **Operations Runbook**: `docs/OPERATIONS_RUNBOOK.md`
- **Phase 3 Report**: `docs/PHASE3_COMPLETION_REPORT.md`
- **API Guide**: `docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md`

### Monitoring
- **Dashboard**: http://localhost:8080/dashboard.html
- **Metrics Reports**: `metrics_reports/`
- **Alert Logs**: `alert_logs/`

### Logs
- **Application Logs**: `logs/spock.log`
- **Metrics Logs**: `logs/metrics.log`
- **Alert Logs**: `logs/alerts.log`
- **Validation Logs**: `logs/validation.log`

---

## Conclusion

This deployment guide provides step-by-step instructions for deploying the Spock Trading System with Phase 3 Validation & Monitoring infrastructure. Follow all verification steps to ensure a successful deployment.

For operational procedures and ongoing maintenance, refer to the **Operations Runbook** (`docs/OPERATIONS_RUNBOOK.md`).

**Deployment Status**: ✅ **Production Ready**

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Next Review**: 2025-11-16
