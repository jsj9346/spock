# Spock Trading System - Operations Runbook

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Phase**: Phase 3 - Validation & Monitoring
**Target Audience**: System Operators, DevOps Engineers, On-Call Personnel

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring & Alerting](#monitoring--alerting)
3. [Common Operational Tasks](#common-operational-tasks)
4. [Incident Response](#incident-response)
5. [Performance Tuning](#performance-tuning)
6. [Backup & Recovery](#backup--recovery)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Emergency Procedures](#emergency-procedures)

---

## Daily Operations

### Morning Health Check (9:00 AM KST)

**Before Market Open** (KOSPI opens at 09:00 KST):

```bash
# 1. Check system status
./scripts/verify_deployment.sh

# 2. Review overnight alerts
tail -50 alert_logs/alerts_*.json | grep -E 'CRITICAL|WARNING'

# 3. Check database health
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
conn = db._get_connection(); \
cursor = conn.cursor(); \
cursor.execute('SELECT COUNT(*) FROM ohlcv_data'); \
print(f'Total OHLCV rows: {cursor.fetchone()[0]:,}'); \
conn.close()"

# 4. Verify API connectivity
python3 scripts/test_kis_connection.py --basic

# 5. Check disk space
df -h | grep -E 'Filesystem|/Users/13ruce'
```

**Expected Results**:
- ✅ All verification checks pass
- ✅ No critical alerts overnight
- ✅ Database row count increasing
- ✅ API connection successful
- ✅ Disk usage < 90%

**Action Items if Issues Found**:
- Critical alerts → Follow [Incident Response](#incident-response)
- API connection failure → Check [API Connection Issues](#api-connection-issues)
- Disk space > 90% → Follow [Disk Space Management](#disk-space-management)

### End-of-Day Check (16:00 KST)

**After Market Close** (KOSPI closes at 15:30 KST):

```bash
# 1. Generate daily performance report
python3 scripts/benchmark_performance.py

# 2. Run data quality validation
python3 scripts/validate_data_quality.py --output validation_reports/daily_$(date +%Y%m%d).json

# 3. Check collection success rate
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
metrics = collector.collect_all_metrics(); \
print(f'Collection Success Rate: {metrics[\"collectors\"][\"collection_rates\"][\"overall\"][\"success_rate\"]}%')"

# 4. Backup database (if not automated)
tar -czf data/backups/spock_db_$(date +%Y%m%d).tar.gz data/spock_local.db

# 5. Clean up old logs
find logs/ -name "*.log" -mtime +7 -delete
find data/backups/ -name "*.tar.gz" -mtime +7 -delete
```

**Daily Checklist**:
- [ ] Morning health check completed
- [ ] Market hours monitoring active
- [ ] End-of-day validation passed
- [ ] Database backup created
- [ ] Performance report reviewed
- [ ] Alerts reviewed and addressed

---

## Monitoring & Alerting

### Real-Time Monitoring

**Dashboard Access**:
```bash
# Start dashboard server
python3 monitoring/serve_dashboard.py --port 8080

# Access URL: http://localhost:8080/dashboard.html
```

**Key Metrics to Monitor**:

| Metric | Normal Range | Warning | Critical | Action Required |
|--------|--------------|---------|----------|-----------------|
| **API Error Rate** | < 5% | 5-20% | > 20% | Check API logs, verify credentials |
| **API Latency (avg)** | < 200ms | 200-500ms | > 500ms | Check network, API status |
| **CPU Usage** | < 70% | 70-85% | > 85% | Identify processes, scale resources |
| **Memory Usage** | < 70% | 70-85% | > 85% | Check for memory leaks, restart services |
| **Disk Usage** | < 80% | 80-90% | > 90% | Clean logs, archive data, expand storage |
| **Database Query Time** | < 200ms | 200-500ms | > 500ms | Optimize queries, rebuild indexes |
| **Collection Success Rate** | > 95% | 80-95% | < 80% | Check API limits, network stability |

### Alert Management

**Check Active Alerts**:
```bash
# View recent alerts
python3 modules/alert_system.py

# Check alert history
ls -lth alert_logs/alerts_*.json | head -5

# View specific alert file
cat alert_logs/alerts_$(date +%Y%m%d)_*.json | python3 -m json.tool
```

**Alert Response Matrix**:

| Alert Level | Response Time | Escalation | Action |
|-------------|---------------|------------|--------|
| **INFO** | 24 hours | None | Review during next check |
| **WARNING** | 4 hours | Team Lead (if unresolved) | Investigate and monitor |
| **CRITICAL** | Immediate | On-call Engineer | Immediate investigation and fix |

**Common Alerts and Resolution**:

1. **High API Error Rate**
   ```bash
   # Check API logs
   python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
   db = SQLiteDatabaseManager(); \
   conn = db._get_connection(); \
   cursor = conn.cursor(); \
   cursor.execute('SELECT * FROM kis_api_logs WHERE status_code != 200 ORDER BY timestamp DESC LIMIT 10'); \
   for row in cursor.fetchall(): print(row); \
   conn.close()"

   # Verify credentials
   python3 scripts/validate_kis_credentials.py
   ```

2. **High Memory Usage**
   ```bash
   # Check memory by process
   ps aux | sort -nrk 4 | head -10

   # Restart data collector if needed
   pkill -f "python3.*kis_data_collector.py"
   ```

3. **Disk Space Critical**
   ```bash
   # Clean old backups
   find data/backups/ -name "*.tar.gz" -mtime +7 -delete

   # Clean old metrics
   find metrics_reports/ -name "metrics_*.json" -mtime +7 -delete

   # Clean old logs
   find logs/ -name "*.log" -mtime +7 -delete

   # Archive old OHLCV data (if needed)
   python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
   db = SQLiteDatabaseManager(); \
   db.cleanup_old_ohlcv_data(retention_days=250)"
   ```

---

## Common Operational Tasks

### Task 1: Manual Metrics Collection

**When**: On-demand or when automated collection fails

```bash
# Generate fresh metrics
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
output = collector.save_metrics(); \
print(f'Metrics saved: {output}')"

# Update latest symlink
cd metrics_reports
rm -f metrics_latest.json
ln -s $(ls -t metrics_*.json | head -1) metrics_latest.json
```

### Task 2: Run Data Quality Validation

**When**: Daily, after data collection, before trading decisions

```bash
# Full validation
python3 scripts/validate_data_quality.py

# Save to specific file
python3 scripts/validate_data_quality.py --output validation_reports/manual_$(date +%Y%m%d_%H%M%S).json

# Review validation report
cat validation_reports/data_quality_*.json | python3 -m json.tool | grep -A10 '"summary"'
```

### Task 3: Performance Benchmarking

**When**: Weekly, after system changes, investigating performance issues

```bash
# Run full benchmark
python3 scripts/benchmark_performance.py

# Compare with baseline
python3 -c "import json; \
baseline = json.load(open('benchmark_reports/baseline.json')); \
current = json.load(open('benchmark_reports/performance_$(date +%Y%m%d)_*.json')); \
print(f'Database queries: {baseline[\"database\"][\"avg_ms\"]} -> {current[\"database\"][\"avg_ms\"]} ms')"
```

### Task 4: Database Maintenance

**When**: Weekly (Sunday 2 AM), after large data imports

```bash
# Analyze database
sqlite3 data/spock_local.db "ANALYZE;"

# Rebuild indexes
sqlite3 data/spock_local.db "REINDEX;"

# Vacuum database (reclaim space)
sqlite3 data/spock_local.db "VACUUM;"

# Check database integrity
sqlite3 data/spock_local.db "PRAGMA integrity_check;"
```

**Expected Output**: `ok`

### Task 5: Log Rotation

**When**: Daily (automated), or manually when logs grow large

```bash
# Check log sizes
du -sh logs/*.log

# Rotate logs manually
cd logs
for log in *.log; do
    if [ -f "$log" ]; then
        mv "$log" "${log}.$(date +%Y%m%d)"
        gzip "${log}.$(date +%Y%m%d)"
    fi
done

# Clean old compressed logs
find logs/ -name "*.log.*.gz" -mtime +7 -delete
```

### Task 6: Restart Services

**When**: After configuration changes, memory leaks, scheduled maintenance

```bash
# Stop all Spock processes
pkill -f "python3.*spock"
pkill -f "python3.*modules"

# Verify processes stopped
ps aux | grep -E 'spock|kis_data_collector'

# Restart main service (example)
nohup python3 spock.py --dry-run --no-gpt >> logs/spock.log 2>&1 &

# Restart dashboard server
cd monitoring
nohup python3 serve_dashboard.py --port 8080 >> ../logs/dashboard.log 2>&1 &
```

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **P0 - Critical** | System down, data loss, trading halted | Immediate | CTO, Team Lead |
| **P1 - High** | Major functionality impaired | 1 hour | Team Lead |
| **P2 - Medium** | Minor functionality impaired | 4 hours | Team |
| **P3 - Low** | Cosmetic issues, non-urgent | 24 hours | None |

### Incident Response Workflow

```
1. DETECT   → Monitor alerts, user reports
2. ASSESS   → Severity, scope, impact
3. RESPOND  → Follow runbook procedures
4. RESOLVE  → Fix root cause
5. VERIFY   → Confirm resolution
6. DOCUMENT → Post-incident report
```

### Critical Incidents (P0)

#### Incident: Database Corruption

**Symptoms**:
- SQLite errors: "database disk image is malformed"
- Data integrity check fails
- Unable to read/write data

**Immediate Actions**:
```bash
# 1. Stop all processes immediately
pkill -f "python3.*spock"

# 2. Backup corrupted database
cp data/spock_local.db data/spock_local.db.corrupted.$(date +%Y%m%d_%H%M%S)

# 3. Restore from latest backup
cp data/backups/spock_db_$(date +%Y%m%d).tar.gz .
tar -xzf spock_db_$(date +%Y%m%d).tar.gz

# 4. Verify integrity
sqlite3 data/spock_local.db "PRAGMA integrity_check;"

# 5. If OK, restart services
./scripts/verify_deployment.sh
```

**Root Cause Analysis**:
- Check disk space (corruption often from full disk)
- Review system logs for crashes
- Check for concurrent write operations

#### Incident: API Rate Limit Exceeded

**Symptoms**:
- HTTP 429 errors in logs
- Data collection failures
- Alert: "Rate limit usage critical"

**Immediate Actions**:
```bash
# 1. Stop data collection
pkill -f "python3.*kis_data_collector.py"

# 2. Check rate limit usage
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
metrics = collector.collect_all_metrics(); \
print(f'Rate limit: {metrics[\"api\"][\"rate_limit_usage_pct\"]}%')"

# 3. Wait for rate limit reset (usually 1 minute)
sleep 60

# 4. Resume with throttling
# Edit data collector to reduce request rate
```

**Prevention**:
- Monitor rate limit usage proactively (< 80%)
- Implement exponential backoff
- Distribute requests over time

#### Incident: Memory Leak

**Symptoms**:
- Memory usage continuously increasing
- System slowdown
- OOM (Out of Memory) errors

**Immediate Actions**:
```bash
# 1. Identify memory-hungry process
ps aux | sort -nrk 4 | head -10

# 2. Kill problematic process
pkill -f "python3.*<process_name>"

# 3. Check for memory leaks in code
# Review recent code changes
# Check for unclosed database connections

# 4. Restart with monitoring
# Add memory profiling
```

**Investigation**:
```bash
# Enable memory profiling
pip install memory_profiler

# Profile specific function
python3 -m memory_profiler modules/kis_data_collector.py
```

### High Priority Incidents (P1)

#### Incident: Data Quality Failure

**Symptoms**:
- Validation reports show failures
- NULL values in critical columns
- Integrity violations detected

**Response**:
```bash
# 1. Run detailed validation
python3 scripts/validate_data_quality.py

# 2. Identify specific failures
cat validation_reports/data_quality_*.json | python3 -m json.tool | grep -B5 '"status": "critical"'

# 3. Query problematic data
sqlite3 data/spock_local.db "SELECT * FROM ohlcv_data WHERE <column> IS NULL LIMIT 10;"

# 4. Fix data or re-collect
# Option A: Delete bad data
sqlite3 data/spock_local.db "DELETE FROM ohlcv_data WHERE <condition>;"

# Option B: Re-collect for specific tickers
python3 modules/kis_data_collector.py --tickers <ticker_list> --days 250
```

#### Incident: API Authentication Failure

**Symptoms**:
- 401 Unauthorized errors
- Token refresh failures
- "Invalid credentials" messages

**Response**:
```bash
# 1. Verify credentials
python3 scripts/validate_kis_credentials.py

# 2. Check .env file
cat .env | grep KIS_

# 3. Check file permissions
ls -l .env
# Should be: -rw------- (600)

# 4. Regenerate token manually
python3 -c "from config.kis_api_config import KISAPIConfig; \
config = KISAPIConfig(); \
token = config.get_access_token(); \
print(f'Token: {token[:20]}...')"

# 5. If credentials invalid, update .env
# Obtain new credentials from KIS Developer Portal
```

---

## Performance Tuning

### Database Optimization

**Query Performance Tuning**:
```bash
# 1. Identify slow queries
sqlite3 data/spock_local.db "EXPLAIN QUERY PLAN SELECT * FROM ohlcv_data WHERE region = 'KR' AND date >= '2025-01-01';"

# 2. Check index usage
sqlite3 data/spock_local.db "SELECT * FROM sqlite_master WHERE type='index';"

# 3. Create missing indexes
sqlite3 data/spock_local.db "CREATE INDEX IF NOT EXISTS idx_region_date ON ohlcv_data(region, date);"

# 4. Analyze after index creation
sqlite3 data/spock_local.db "ANALYZE;"

# 5. Benchmark improvement
python3 scripts/benchmark_performance.py
```

**Database Vacuum**:
```bash
# Free up space after deletions
sqlite3 data/spock_local.db "VACUUM;"

# Expected: Database size reduced
du -h data/spock_local.db
```

### API Performance Tuning

**Optimize Request Batching**:
```python
# Edit modules/kis_data_collector.py
# Increase batch size for bulk operations
BATCH_SIZE = 100  # Adjust based on API limits

# Implement parallel requests (within rate limits)
# Use async/await for concurrent requests
```

**Rate Limit Optimization**:
```bash
# Monitor API usage pattern
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
metrics = collector.collect_all_metrics(); \
print(f'Requests/hour: {metrics[\"api\"][\"total_requests\"]}'); \
print(f'Rate limit usage: {metrics[\"api\"][\"rate_limit_usage_pct\"]}%')"

# Adjust request timing to stay below 80% usage
```

### System Resource Optimization

**CPU Optimization**:
```bash
# Identify CPU-intensive processes
top -o cpu | head -20

# Reduce Python process priority (if needed)
renice +10 $(pgrep -f python3)
```

**Memory Optimization**:
```bash
# Check memory usage by component
ps aux | awk '{print $4, $11}' | sort -rn | head -10

# Tune pandas memory usage
# Add to data collector:
# df = pd.read_csv(..., dtype={'column': 'category'})
```

**Disk I/O Optimization**:
```bash
# Check I/O performance
iostat -x 1 10

# Move database to SSD if on HDD
# Enable WAL mode for better concurrency
sqlite3 data/spock_local.db "PRAGMA journal_mode=WAL;"
```

---

## Backup & Recovery

### Backup Strategy

**Automated Daily Backup** (cron):
```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * cd /Users/13ruce/spock && tar -czf data/backups/spock_db_$(date +\%Y\%m\%d).tar.gz data/spock_local.db && find data/backups/ -name "spock_db_*.tar.gz" -mtime +7 -delete
```

**Manual Backup**:
```bash
# Full backup
tar -czf backups/spock_full_$(date +%Y%m%d_%H%M%S).tar.gz \
    data/ config/ .env logs/ metrics_reports/

# Database only
cp data/spock_local.db backups/spock_db_$(date +%Y%m%d_%H%M%S).db

# Compressed database backup
tar -czf backups/spock_db_$(date +%Y%m%d_%H%M%S).tar.gz data/spock_local.db
```

**Backup Verification**:
```bash
# Verify backup integrity
tar -tzf backups/spock_db_$(date +%Y%m%d).tar.gz

# Test restore to temporary location
mkdir -p /tmp/spock_restore
tar -xzf backups/spock_db_$(date +%Y%m%d).tar.gz -C /tmp/spock_restore

# Verify database integrity
sqlite3 /tmp/spock_restore/data/spock_local.db "PRAGMA integrity_check;"
```

### Recovery Procedures

**Scenario 1: Database Corruption**

```bash
# 1. Stop all processes
pkill -f "python3.*spock"

# 2. Backup corrupted database (for analysis)
mv data/spock_local.db data/spock_local.db.corrupted

# 3. Restore from backup
tar -xzf data/backups/spock_db_$(date +%Y%m%d).tar.gz

# 4. Verify integrity
sqlite3 data/spock_local.db "PRAGMA integrity_check;"

# 5. Check data completeness
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
conn = db._get_connection(); \
cursor = conn.cursor(); \
cursor.execute('SELECT COUNT(*), MAX(date) FROM ohlcv_data'); \
print(f'Rows: {cursor.fetchone()}'); \
conn.close()"

# 6. Restart services
./scripts/verify_deployment.sh
```

**Scenario 2: Configuration Loss**

```bash
# 1. Restore configuration files
tar -xzf backups/spock_full_*.tar.gz config/ .env

# 2. Verify credentials
cat .env | grep KIS_

# 3. Set correct permissions
chmod 600 .env
chmod 644 config/*.json

# 4. Test configuration
python3 scripts/validate_kis_credentials.py
```

**Scenario 3: Complete System Failure**

```bash
# 1. Reinstall from scratch
cd ~/
rm -rf spock
git clone <repository-url> spock
cd spock

# 2. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Restore full backup
tar -xzf /backup/location/spock_full_*.tar.gz

# 4. Verify and restart
./scripts/verify_deployment.sh
```

---

## Maintenance Procedures

### Weekly Maintenance (Sunday 2:00 AM)

```bash
#!/bin/bash
# weekly_maintenance.sh

# 1. Stop services
pkill -f "python3.*spock"

# 2. Database maintenance
sqlite3 data/spock_local.db "ANALYZE;"
sqlite3 data/spock_local.db "REINDEX;"
sqlite3 data/spock_local.db "VACUUM;"

# 3. Clean old data (250-day retention)
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
db.cleanup_old_ohlcv_data(retention_days=250)"

# 4. Clean old logs and reports
find logs/ -name "*.log" -mtime +7 -delete
find metrics_reports/ -name "metrics_*.json" -mtime +7 -delete
find alert_logs/ -name "alerts_*.json" -mtime +7 -delete
find validation_reports/ -name "*.json" -mtime +30 -delete

# 5. Backup database
tar -czf data/backups/spock_db_$(date +%Y%m%d).tar.gz data/spock_local.db

# 6. Performance benchmark
python3 scripts/benchmark_performance.py

# 7. Restart services
# (Add service restart commands here)

# 8. Verification
./scripts/verify_deployment.sh
```

### Monthly Maintenance

**Tasks**:
1. Review and update dependencies
2. Security audit
3. Performance trend analysis
4. Capacity planning
5. Disaster recovery drill

**Dependency Updates**:
```bash
# Check for updates
pip list --outdated

# Update specific packages (test in dev first)
pip install --upgrade pandas numpy psutil

# Regenerate requirements
pip freeze > requirements.txt

# Test after updates
pytest tests/
```

### Quarterly Maintenance

**Tasks**:
1. System architecture review
2. Code refactoring
3. Documentation updates
4. Stakeholder review
5. Capacity expansion planning

---

## Emergency Procedures

### Emergency Shutdown

**When**: Security breach, data corruption detected, regulatory requirement

```bash
# 1. Stop all processes immediately
pkill -9 -f "python3.*spock"

# 2. Disconnect from network (if security breach)
# sudo ifconfig en0 down

# 3. Backup current state
tar -czf emergency_backup_$(date +%Y%m%d_%H%M%S).tar.gz data/ logs/ config/

# 4. Secure credentials
chmod 000 .env

# 5. Document incident
echo "Emergency shutdown at $(date)" >> logs/emergency.log
echo "Reason: [SPECIFY REASON]" >> logs/emergency.log

# 6. Notify stakeholders
# (Add notification commands)
```

### Emergency Recovery

**Steps**:
1. Assess damage extent
2. Restore from last known good backup
3. Verify data integrity
4. Review security logs
5. Implement fixes
6. Gradual restart with monitoring
7. Post-incident report

### Emergency Contacts

| Role | Name | Phone | Email | Availability |
|------|------|-------|-------|--------------|
| **On-Call Engineer** | TBD | +82-XXX-XXXX | oncall@spock.local | 24/7 |
| **Team Lead** | TBD | +82-XXX-XXXX | lead@spock.local | 09:00-18:00 |
| **CTO** | TBD | +82-XXX-XXXX | cto@spock.local | Emergency only |
| **KIS API Support** | KIS | 1588-0365 | api@koreainvestment.com | 09:00-18:00 |

---

## Appendix

### Useful Commands Reference

```bash
# Quick system status
python3 -c "from modules.metrics_collector import MetricsCollector; \
m = MetricsCollector().get_metrics_summary(); \
print(f'Status: {m[\"overall_status\"]} ({m[\"overall_health_score\"]}/100)')"

# Database row count
sqlite3 data/spock_local.db "SELECT region, COUNT(*) FROM ohlcv_data GROUP BY region;"

# Recent alerts
ls -t alert_logs/alerts_*.json | head -1 | xargs cat | python3 -m json.tool

# API success rate
python3 -c "from modules.metrics_collector import MetricsCollector; \
m = MetricsCollector().collect_all_metrics(); \
print(f'API Success: {100 - m[\"api\"][\"error_rate\"]:.1f}%')"

# Disk usage
du -sh data/ logs/ metrics_reports/ alert_logs/
```

### Log File Locations

| Log Type | Location | Purpose | Retention |
|----------|----------|---------|-----------|
| **Application** | `logs/spock.log` | Main application logs | 7 days |
| **Metrics** | `logs/metrics.log` | Metrics collection logs | 7 days |
| **Alerts** | `logs/alerts.log` | Alert system logs | 7 days |
| **Validation** | `logs/validation.log` | Data quality validation logs | 7 days |
| **Dashboard** | `logs/dashboard.log` | Dashboard server logs | 7 days |

### Configuration Files

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `.env` | Credentials and secrets | Rarely (on credential change) |
| `config/kis_api_config.py` | API configuration | Rarely (on API changes) |
| `config/market_schedule.json` | Market hours | Annually (market calendar updates) |
| `config/*_holidays.yaml` | Holiday calendars | Annually (new year) |
| `config/alert_thresholds.json` | Alert thresholds | As needed (tuning) |

---

## Operations Checklist

### Daily
- [ ] Morning health check
- [ ] Review overnight alerts
- [ ] Monitor dashboard during market hours
- [ ] End-of-day validation
- [ ] Database backup verification

### Weekly
- [ ] Database maintenance (VACUUM, ANALYZE)
- [ ] Performance benchmarking
- [ ] Log cleanup
- [ ] Backup retention cleanup
- [ ] Review alert patterns

### Monthly
- [ ] Dependency updates (test first)
- [ ] Security audit
- [ ] Performance trend analysis
- [ ] Documentation review
- [ ] Disaster recovery drill

### Quarterly
- [ ] System architecture review
- [ ] Capacity planning
- [ ] Stakeholder review
- [ ] Major version updates
- [ ] Post-mortem reviews

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Next Review**: 2025-11-16
**Maintained By**: Spock Operations Team
