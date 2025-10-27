# Master File Updates - Operational Runbook

**Purpose**: Operational guide for managing automated master file updates

**Audience**: DevOps, SRE, System Administrators

**Last Updated**: 2025-10-15

---

## Overview

Automated master file updates run daily at 6:00 AM KST to download fresh ticker data from KIS servers. This ensures the trading system has up-to-date stock listings for all supported markets.

### Supported Markets
- **US**: NASDAQ, NYSE, AMEX (~6,500 stocks)
- **HK**: Hong Kong Stock Exchange (~500-1,000 stocks)
- **JP**: Tokyo Stock Exchange (~500-1,000 stocks)
- **CN**: Shanghai + Shenzhen (~500-1,000 stocks)
- **VN**: Hanoi + Ho Chi Minh (~100-300 stocks)

### Update Schedule
- **Daily**: 6:00 AM KST (all regions)
- **Weekly**: Sunday 3:00 AM KST (full validation)

---

## Quick Reference

### Check Update Status
```bash
# View recent logs
tail -50 logs/master_file_updates.log

# Check last update time
tail -1 logs/master_file_updates.log | grep "Update Summary"

# View metrics
cat data/master_file_update_metrics.prom
```

### Manual Update
```bash
# Update all regions
python3 scripts/update_master_files.py

# Update specific region
python3 scripts/update_master_files.py --regions US

# Dry run (test mode)
python3 scripts/update_master_files.py --dry-run

# Skip validation (faster)
python3 scripts/update_master_files.py --no-validate
```

### Check Cron Jobs
```bash
# List installed cron jobs
crontab -l

# Edit cron jobs
crontab -e

# Check cron service (macOS)
sudo launchctl list | grep cron

# Check cron service (Linux)
systemctl status cron
```

---

## Automated Updates

### Schedule Configuration

**Daily Update** (6:00 AM KST):
```cron
0 6 * * * cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py >> logs/cron_master_file_updates.log 2>&1
```

**Weekly Full Refresh** (Sunday 3:00 AM KST):
```cron
0 3 * * 0 cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py --regions US HK JP CN VN >> logs/cron_weekly_updates.log 2>&1
```

### Installation Steps

1. **Open crontab editor**:
   ```bash
   crontab -e
   ```

2. **Add environment variables** (at the top):
   ```cron
   PATH=/usr/local/bin:/usr/bin:/bin
   SHELL=/bin/bash
   ```

3. **Add cron jobs** (copy from `config/cron_master_file_updates.sh`)

4. **Save and verify**:
   ```bash
   crontab -l
   ```

5. **Test manually**:
   ```bash
   cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py --dry-run
   ```

---

## Monitoring

### Logs

**Daily Update Log**:
```bash
# Real-time monitoring
tail -f logs/master_file_updates.log

# View last update
tail -50 logs/master_file_updates.log

# Search for errors
grep -i error logs/master_file_updates.log | tail -20

# Count successful updates today
grep "Update successful" logs/master_file_updates.log | grep "$(date +%Y-%m-%d)" | wc -l
```

**Cron Log**:
```bash
# View cron execution log
tail -50 logs/cron_master_file_updates.log

# Check for errors
grep -i error logs/cron_master_file_updates.log
```

### Prometheus Metrics

**Metrics File**: `data/master_file_update_metrics.prom`

**Available Metrics**:
- `spock_master_file_update_success{region}` - Update success (1=success, 0=failure)
- `spock_master_file_ticker_count{region}` - Total tickers after update
- `spock_master_file_update_duration_seconds{region}` - Update duration
- `spock_master_file_update_timestamp` - Last update timestamp

**Check Metrics**:
```bash
# View all metrics
cat data/master_file_update_metrics.prom

# Check US update status
grep 'region="US"' data/master_file_update_metrics.prom

# Check last update time
grep 'update_timestamp' data/master_file_update_metrics.prom
```

### Grafana Dashboard

**Access**: http://localhost:3000

**Dashboard**: "Spock - US Market" (or region-specific)

**Panels**:
- Master file update success rate
- Ticker count by region
- Update duration trends
- Data quality metrics

---

## Alerting

### Alert Conditions

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| **Update Failed** | `update_success == 0` | Critical | Investigate logs, run manual update |
| **Stale Data** | Last update >48h old | Warning | Check cron status, run manual update |
| **Low Ticker Count** | Count drops >10% | Warning | Check master files, validate data |
| **Data Quality** | Completeness <95% | Warning | Review validation logs |

### Alert Actions

**Update Failed**:
1. Check logs: `tail -50 logs/master_file_updates.log`
2. Check KIS API: `python3 scripts/test_kis_connection.py`
3. Run manual update: `python3 scripts/update_master_files.py`
4. If persistent, check credentials in `.env`

**Stale Data**:
1. Check cron status: `crontab -l`
2. Check cron service: `sudo launchctl list | grep cron`
3. Run manual update: `python3 scripts/update_master_files.py`
4. Review cron logs: `tail -50 logs/cron_master_file_updates.log`

**Low Ticker Count**:
1. Check master files: `ls -lh data/master_files/`
2. Force refresh: `python3 scripts/update_master_files.py --regions US`
3. Validate data: `python3 scripts/test_master_file_integration.py`

---

## Troubleshooting

### Issue 1: Update Script Fails

**Symptoms**:
- Log shows "Update failed" errors
- Metrics show `update_success == 0`

**Diagnosis**:
```bash
# Check recent logs
tail -100 logs/master_file_updates.log | grep -i error

# Test update manually
python3 scripts/update_master_files.py --dry-run

# Check KIS API connection
python3 scripts/test_kis_connection.py
```

**Common Causes**:
1. **KIS API credentials expired** → Check `.env` file
2. **Network connectivity** → Test internet connection
3. **Master file server down** → Check KIS server status
4. **Insufficient disk space** → Check `df -h`

**Resolution**:
```bash
# Verify credentials
grep KIS_APP_KEY .env
grep KIS_APP_SECRET .env

# Test API connection
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
api = KISOverseasStockAPI(os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))
print('Connected:', api.check_connection())
"

# Force refresh
python3 scripts/update_master_files.py --regions US
```

### Issue 2: Cron Job Not Running

**Symptoms**:
- No recent entries in cron logs
- Metrics timestamp is old

**Diagnosis**:
```bash
# Check if cron jobs are installed
crontab -l

# Check cron service (macOS)
sudo launchctl list | grep cron

# Check cron service (Linux)
systemctl status cron

# Check system logs
tail -50 /var/log/cron.log  # Linux
tail -50 /var/log/system.log | grep cron  # macOS
```

**Common Causes**:
1. **Cron not installed** → Install cron service
2. **Cron syntax error** → Validate crontab syntax
3. **Incorrect paths** → Use absolute paths
4. **Permission denied** → Check script permissions

**Resolution**:
```bash
# Verify cron syntax
crontab -l | grep update_master_files

# Test cron command manually
cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py

# Fix permissions
chmod +x scripts/update_master_files.py

# Reinstall cron job
crontab -e
# (Add job from config/cron_master_file_updates.sh)
```

### Issue 3: High Update Duration

**Symptoms**:
- Update takes >10 seconds
- Logs show slow performance

**Diagnosis**:
```bash
# Check update duration
grep "Update successful" logs/master_file_updates.log | tail -10

# Check metrics
grep "update_duration" data/master_file_update_metrics.prom

# Test performance
time python3 scripts/update_master_files.py --dry-run
```

**Common Causes**:
1. **Network latency** → Check KIS API latency
2. **Disk I/O** → Check disk performance
3. **Too many regions** → Update regions separately

**Resolution**:
```bash
# Test KIS API latency
python3 scripts/test_kis_connection.py --latency

# Update regions separately
python3 scripts/update_master_files.py --regions US
python3 scripts/update_master_files.py --regions HK
# etc.

# Use --no-validate for faster updates
python3 scripts/update_master_files.py --no-validate
```

### Issue 4: Data Quality Failed

**Symptoms**:
- Validation shows completeness <95%
- Alert: "Data Quality Warning"

**Diagnosis**:
```bash
# Run validation
python3 scripts/test_master_file_integration.py

# Check master files
ls -lh data/master_files/

# Test parser
python3 -c "
from modules.api_clients.kis_master_file_manager import KISMasterFileManager
mgr = KISMasterFileManager()
tickers = mgr.get_all_tickers('US', force_refresh=False)
print(f'US tickers: {len(tickers):,}')
"
```

**Common Causes**:
1. **Corrupted master files** → Force refresh
2. **Parser error** → Check recent code changes
3. **Missing data fields** → Validate file format

**Resolution**:
```bash
# Force refresh master files
python3 scripts/update_master_files.py --regions US

# Delete cached files and re-download
rm data/master_files/*.cod
python3 scripts/update_master_files.py

# Validate after refresh
python3 scripts/test_master_file_integration.py
```

---

## Maintenance

### Daily Tasks

**Automated** (no action needed):
- ✅ Daily update at 6:00 AM KST
- ✅ Metrics export
- ✅ Log rotation

**Manual** (as needed):
- Review update logs for errors
- Monitor Grafana dashboard
- Respond to alerts

### Weekly Tasks

**Automated**:
- ✅ Sunday 3:00 AM full refresh
- ✅ Comprehensive validation

**Manual**:
- Review weekly update summary
- Check data quality trends
- Archive old logs (>30 days)

### Monthly Tasks

**Manual**:
- Review update success rate (target: >99%)
- Check disk space usage
- Update documentation if needed
- Review and optimize cron schedule

### Quarterly Tasks

**Manual**:
- Test disaster recovery procedure
- Review and update credentials
- Performance optimization review
- Documentation audit

---

## Emergency Procedures

### Complete Service Failure

**Steps**:
1. **Assess Impact**:
   ```bash
   # Check all regions
   for region in US HK JP CN VN; do
       python3 -c "
       from modules.db_manager_sqlite import SQLiteDatabaseManager
       db = SQLiteDatabaseManager()
       count = len(db.get_tickers(region='$region'))
       print('$region:', count, 'tickers')
       "
   done
   ```

2. **Restore from Backup**:
   ```bash
   # List available backups
   ls -lh data/backups/

   # Restore from backup (if needed)
   cp data/backups/spock_local_YYYYMMDD.db data/spock_local.db
   ```

3. **Force Refresh All Regions**:
   ```bash
   python3 scripts/update_master_files.py --regions US HK JP CN VN
   ```

4. **Validate Recovery**:
   ```bash
   python3 scripts/test_master_file_integration.py
   ```

### KIS API Outage

**Symptoms**:
- All updates failing
- API connection tests fail

**Response**:
1. **Verify Outage**:
   ```bash
   python3 scripts/test_kis_connection.py
   ```

2. **Check KIS Status**:
   - Visit: https://apiportal.koreainvestment.com
   - Contact KIS support if needed

3. **Use Cached Data**:
   - System automatically uses cached master files
   - No immediate action needed
   - Monitor for KIS service restoration

4. **Monitor and Update**:
   - Check KIS status every hour
   - Run manual update once service restored
   - Validate data after restoration

---

## Best Practices

### DO

✅ Monitor daily update logs
✅ Keep credentials secure in `.env`
✅ Test updates before deploying changes
✅ Maintain regular backups
✅ Document any manual interventions
✅ Use dry-run mode for testing
✅ Keep logs for at least 30 days

### DON'T

❌ Disable updates without notification
❌ Run updates during market hours (if possible)
❌ Modify update script without testing
❌ Ignore failed update alerts
❌ Delete logs without archiving
❌ Share credentials in logs or docs
❌ Skip validation checks

---

## References

### Documentation
- `docs/MASTER_FILE_INTEGRATION_SUMMARY.md` - Integration overview
- `docs/MASTER_FILE_DEPLOYMENT_PLAN.md` - Deployment plan
- `docs/DEPLOYMENT_REPORT_P0_CRITICAL.md` - Deployment report
- `config/cron_master_file_updates.sh` - Cron configuration

### Scripts
- `scripts/update_master_files.py` - Main update script
- `scripts/test_master_file_integration.py` - Integration tests
- `scripts/test_kis_connection.py` - Connection tests

### Monitoring
- Grafana: http://localhost:3000
- Prometheus metrics: `data/master_file_update_metrics.prom`
- Logs: `logs/master_file_updates.log`

---

## Contact

**Technical Support**:
- Slack: #spock-operations
- Email: spock-ops@example.com

**Escalation**:
- Critical issues: Page on-call engineer
- Business hours: Contact DevOps team
- After hours: Follow on-call rotation

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-15 | 1.0 | Initial operational runbook for automated updates |

---

**Document Status**: ✅ Production Ready
**Last Review**: 2025-10-15
**Next Review**: 2025-11-15
