# Master File Integration - Prioritized Deployment Plan

**Created**: 2025-10-15
**Status**: Ready for execution
**Total Duration**: 2-3 weeks (7 phases)

---

## Executive Summary

**Current State**: US master file integration complete and tested (4/5 tests passing, 100% data quality)

**Goal**: Production deployment + multi-region rollout (HK, CN, JP, VN)

**Strategy**: Phased deployment with validation gates, risk mitigation, and incremental rollout

---

## Priority Matrix

### Risk vs Value Analysis

| Task | Business Value | Risk Level | Effort | Priority | Dependencies |
|------|----------------|------------|--------|----------|--------------|
| **US Production Deploy** | ⭐⭐⭐⭐⭐ | 🔴 Medium | 1 day | **P0 - Critical** | None |
| **Automated Updates** | ⭐⭐⭐⭐⭐ | 🟢 Low | 0.5 day | **P0 - Critical** | US Deploy |
| **HK Market** | ⭐⭐⭐⭐ | 🟡 Low-Med | 1-2 days | **P1 - High** | US Deploy |
| **JP Market** | ⭐⭐⭐⭐ | 🟡 Low-Med | 1-2 days | **P1 - High** | US Deploy |
| **CN Market** | ⭐⭐⭐ | 🟡 Low-Med | 1-2 days | **P2 - Medium** | US Deploy |
| **VN Market** | ⭐⭐ | 🟢 Low | 1 day | **P3 - Low** | US Deploy |

### Decision Rationale

**P0 - Critical (Deploy immediately)**:
- US Production: Highest ROI (77x coverage, instant scan), validates architecture
- Automated Updates: Prevents stale data, operational excellence

**P1 - High (Deploy within 1 week)**:
- HK/JP Markets: Established markets, moderate volume, similar architecture to US

**P2 - Medium (Deploy within 2 weeks)**:
- CN Market: Complex (2 exchanges), regional restrictions, lower priority for Korean investors

**P3 - Low (Deploy within 3 weeks)**:
- VN Market: Smallest market (~100-300 stocks), lowest complexity

---

## Phase-Based Deployment Plan

### 📋 Phase 0: Pre-Deployment Validation (Day 1, Morning)

**Objective**: Ensure US integration is production-ready

**Duration**: 2-4 hours

**Tasks**:
1. ✅ Run full integration test suite
2. ✅ Validate data quality (>95% completeness)
3. ✅ Check database schema compatibility
4. ✅ Verify error handling and fallback logic
5. ✅ Review security (file permissions, credentials)
6. ✅ Performance benchmarking (scan time <1s)

**Validation Checklist**:
```bash
# 1. Integration tests
python3 scripts/test_master_file_integration.py
# Expected: 4/5 tests passing, 100% data quality

# 2. Database validation
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()

# Check region column exists
cursor.execute('PRAGMA table_info(ohlcv_data)')
columns = [row[1] for row in cursor.fetchall()]
assert 'region' in columns, 'Region column missing'

# Check NULL regions
cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL')
null_count = cursor.fetchone()[0]
assert null_count == 0, f'Found {null_count} NULL regions'

print('✅ Database validation passed')
conn.close()
"

# 3. Performance benchmark
python3 -c "
import time
from modules.market_adapters.us_adapter_kis import USAdapterKIS
from modules.db_manager_sqlite import SQLiteDatabaseManager
import os
from dotenv import load_dotenv

load_dotenv()
db = SQLiteDatabaseManager()
adapter = USAdapterKIS(db, os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))

start = time.time()
stocks = adapter.scan_stocks(force_refresh=True, max_count=10)
elapsed = time.time() - start

assert elapsed < 5.0, f'Scan too slow: {elapsed:.2f}s'
assert len(stocks) == 10, f'Expected 10 stocks, got {len(stocks)}'
print(f'✅ Performance benchmark passed: {elapsed:.2f}s for 10 stocks')
"

# 4. Security audit
ls -la data/.kis_token_cache.json  # Should be 600 permissions
ls -la .env  # Should be 600 permissions
ls -la data/master_files/*.cod  # Should exist and be readable
```

**Success Criteria**:
- ✅ All tests passing
- ✅ Database compatible
- ✅ Security verified
- ✅ Performance acceptable

**Rollback Plan**: Not applicable (pre-deployment validation)

---

### 🚀 Phase 1: US Production Deployment (Day 1, Afternoon)

**Objective**: Deploy US master file integration to production

**Priority**: **P0 - Critical**

**Duration**: 4 hours

**Risk Level**: 🔴 Medium (first deployment, new architecture)

**Tasks**:

1. **Backup Current State** (30 min)
   ```bash
   # Backup database
   python3 -c "
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   db = SQLiteDatabaseManager()
   db.backup_database()
   print('✅ Database backed up')
   "

   # Backup tickers table
   sqlite3 data/spock_local.db ".dump tickers" > data/backups/tickers_pre_master_file.sql
   ```

2. **Deploy Master File Manager** (30 min)
   ```bash
   # Already deployed (code complete)
   # Verify installation
   python3 -c "
   from modules.api_clients.kis_master_file_manager import KISMasterFileManager
   mgr = KISMasterFileManager()
   print('✅ KISMasterFileManager available')
   "
   ```

3. **Deploy API Client Integration** (30 min)
   ```bash
   # Already deployed (code complete)
   # Verify integration
   python3 -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI

   api = KISOverseasStockAPI(os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))
   tickers = api.get_tradable_tickers('NASD', use_master_file=True)
   assert len(tickers) > 3000, f'Expected >3000 tickers, got {len(tickers)}'
   print(f'✅ API integration working: {len(tickers):,} NASDAQ tickers')
   "
   ```

4. **Deploy US Adapter Updates** (30 min)
   ```bash
   # Already deployed (code complete)
   # Verify adapter
   python3 -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   from modules.market_adapters.us_adapter_kis import USAdapterKIS
   from modules.db_manager_sqlite import SQLiteDatabaseManager

   db = SQLiteDatabaseManager()
   adapter = USAdapterKIS(db, os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))

   # Test with small sample
   stocks = adapter.scan_stocks(force_refresh=True, max_count=5)
   assert len(stocks) == 5, f'Expected 5 stocks, got {len(stocks)}'
   print(f'✅ Adapter working: {len(stocks)} stocks scanned')
   "
   ```

5. **Full US Stock Scan** (1 hour)
   ```bash
   # Production scan (all 6,527 US stocks)
   python3 -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   from modules.market_adapters.us_adapter_kis import USAdapterKIS
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   import time

   db = SQLiteDatabaseManager()
   adapter = USAdapterKIS(db, os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))

   print('📊 Starting full US stock scan...')
   start = time.time()

   stocks = adapter.scan_stocks(force_refresh=True, use_master_file=True)

   elapsed = time.time() - start
   print(f'✅ Scan complete: {len(stocks):,} stocks in {elapsed:.2f}s')
   print(f'   Performance: {len(stocks)/elapsed:.1f} stocks/sec')

   # Verify database
   db_stocks = db.get_tickers(region='US', asset_type='STOCK')
   print(f'✅ Database: {len(db_stocks):,} US stocks')
   "
   ```

6. **Post-Deployment Validation** (30 min)
   ```bash
   # Validate deployment
   python3 scripts/test_master_file_integration.py

   # Check database stats
   python3 -c "
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   db = SQLiteDatabaseManager()
   conn = db._get_connection()
   cursor = conn.cursor()

   # US ticker count
   cursor.execute('SELECT COUNT(*) FROM tickers WHERE region=\"US\"')
   us_count = cursor.fetchone()[0]
   print(f'US tickers: {us_count:,}')
   assert us_count > 6000, f'Expected >6000, got {us_count}'

   # OHLCV data check
   cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region=\"US\"')
   ohlcv_count = cursor.fetchone()[0]
   print(f'US OHLCV rows: {ohlcv_count:,}')

   # NULL region check
   cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL')
   null_count = cursor.fetchone()[0]
   assert null_count == 0, f'Found {null_count} NULL regions'

   print('✅ Post-deployment validation passed')
   conn.close()
   "
   ```

7. **Monitoring Setup** (30 min)
   ```bash
   # Start Prometheus exporter
   python3 monitoring/exporters/spock_exporter.py --port 8000 &

   # Check metrics
   curl http://localhost:8000/metrics | grep spock_ohlcv_rows_total
   # Expected: spock_ohlcv_rows_total{region="US"} > 0

   # Check Grafana dashboard
   # Open: http://localhost:3000
   # Verify: US dashboard showing data
   ```

**Success Criteria**:
- ✅ 6,000+ US stocks in database
- ✅ Scan time <1 second
- ✅ 0 NULL regions
- ✅ Integration tests passing
- ✅ Monitoring active

**Rollback Plan**:
```bash
# If deployment fails, restore from backup
sqlite3 data/spock_local.db < data/backups/tickers_pre_master_file.sql

# Verify restoration
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
count = len(db.get_tickers(region='US'))
print(f'Restored {count} US tickers')
"
```

**Risk Mitigation**:
- ✅ Backup before deployment
- ✅ Graceful fallback to API method
- ✅ Validation gates at each step
- ✅ Rollback procedure tested

---

### ⏰ Phase 2: Automated Daily Updates (Day 2, Morning)

**Objective**: Set up automated master file updates (6AM KST)

**Priority**: **P0 - Critical**

**Duration**: 2-4 hours

**Risk Level**: 🟢 Low (non-invasive, improves reliability)

**Tasks**:

1. **Create Update Script** (1 hour)
   ```bash
   # Create automated update script
   cat > scripts/update_master_files.py << 'EOF'
   #!/usr/bin/env python3
   """
   Automated Master File Update Script

   Runs daily at 6AM KST to download new master files
   and refresh ticker database.

   Schedule: Daily 6AM KST (after US market close, before Asia open)
   """

   import sys
   import os
   import logging
   from datetime import datetime

   # Add project root to path
   sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

   from modules.api_clients.kis_master_file_manager import KISMasterFileManager
   from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
   from dotenv import load_dotenv

   # Setup logging
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s [%(levelname)s] %(message)s',
       handlers=[
           logging.FileHandler('logs/master_file_updates.log'),
           logging.StreamHandler()
       ]
   )
   logger = logging.getLogger(__name__)

   load_dotenv()

   def update_region(region: str):
       """Update master files for a region"""
       try:
           logger.info(f"🔄 Updating {region} master files...")

           # Initialize API
           api = KISOverseasStockAPI(
               os.getenv('KIS_APP_KEY'),
               os.getenv('KIS_APP_SECRET')
           )

           # Force refresh master files
           tickers = api.get_tickers_with_details(region, force_refresh=True)

           if tickers:
               logger.info(f"✅ {region}: {len(tickers):,} tickers updated")
               return True
           else:
               logger.warning(f"⚠️ {region}: No tickers returned")
               return False

       except Exception as e:
           logger.error(f"❌ {region} update failed: {e}")
           return False

   def main():
       """Main update routine"""
       logger.info("=" * 80)
       logger.info(f"Master File Daily Update - {datetime.now()}")
       logger.info("=" * 80)

       # Update all regions
       regions = ['US', 'HK', 'JP', 'CN', 'VN']
       results = {}

       for region in regions:
           results[region] = update_region(region)

       # Summary
       logger.info("=" * 80)
       logger.info("Update Summary")
       logger.info("=" * 80)

       for region, success in results.items():
           status = "✅ SUCCESS" if success else "❌ FAILED"
           logger.info(f"  {status}: {region}")

       passed = sum(1 for v in results.values() if v)
       total = len(results)
       logger.info(f"\nTotal: {passed}/{total} regions updated successfully")
       logger.info("=" * 80)

       return passed == total

   if __name__ == '__main__':
       success = main()
       sys.exit(0 if success else 1)
   EOF

   chmod +x scripts/update_master_files.py
   ```

2. **Test Update Script** (30 min)
   ```bash
   # Test manual execution
   python3 scripts/update_master_files.py
   # Expected: All regions updated successfully
   ```

3. **Set Up Cron Job** (30 min)
   ```bash
   # Create cron job for daily 6AM KST
   # Note: Adjust for your server's timezone

   # Add to crontab (edit with: crontab -e)
   # Daily at 6AM KST (adjust if server is not in KST)
   0 6 * * * cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py >> logs/cron_master_file_updates.log 2>&1

   # Weekly full refresh at 3AM KST on Sundays
   0 3 * * 0 cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py >> logs/cron_master_file_updates.log 2>&1
   ```

4. **Set Up systemd Timer** (Alternative, 1 hour)
   ```bash
   # For production Linux servers, use systemd timer instead of cron

   # Create service file
   sudo tee /etc/systemd/system/spock-master-file-update.service << EOF
   [Unit]
   Description=Spock Master File Daily Update
   After=network.target

   [Service]
   Type=oneshot
   User=spock
   WorkingDirectory=/home/spock/spock
   ExecStart=/usr/bin/python3 /home/spock/spock/scripts/update_master_files.py
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   EOF

   # Create timer file
   sudo tee /etc/systemd/system/spock-master-file-update.timer << EOF
   [Unit]
   Description=Spock Master File Daily Update Timer
   Requires=spock-master-file-update.service

   [Timer]
   OnCalendar=daily
   OnCalendar=*-*-* 06:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   EOF

   # Enable and start timer
   sudo systemctl daemon-reload
   sudo systemctl enable spock-master-file-update.timer
   sudo systemctl start spock-master-file-update.timer

   # Check status
   sudo systemctl status spock-master-file-update.timer
   sudo systemctl list-timers --all | grep spock
   ```

5. **Monitoring Integration** (30 min)
   ```bash
   # Add Prometheus metrics for update monitoring
   # Already included in spock_exporter.py

   # Create Grafana alert for failed updates
   # Alert condition: spock_last_data_update_timestamp{region="US"} > 48 hours
   ```

**Success Criteria**:
- ✅ Update script created and tested
- ✅ Cron job or systemd timer configured
- ✅ First automated update successful
- ✅ Monitoring and alerting configured
- ✅ Logs properly rotating

**Rollback Plan**: Disable cron job or systemd timer

**Documentation**:
```markdown
# Master File Update Schedule

## Daily Updates
- **Time**: 6:00 AM KST
- **Frequency**: Daily
- **Scope**: All regions (US, HK, JP, CN, VN)
- **Method**: Force refresh master files
- **Duration**: ~1-2 minutes

## Weekly Full Refresh
- **Time**: 3:00 AM KST (Sunday)
- **Frequency**: Weekly
- **Scope**: All regions + full validation
- **Method**: Force refresh + data quality check

## Monitoring
- **Logs**: `logs/master_file_updates.log`
- **Metrics**: Prometheus (port 8000)
- **Alerts**: Grafana (failed updates, stale data)

## Manual Update
```bash
# Manual update all regions
python3 scripts/update_master_files.py

# Manual update specific region
python3 -c "
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
import os
from dotenv import load_dotenv

load_dotenv()
api = KISOverseasStockAPI(os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))
tickers = api.get_tickers_with_details('US', force_refresh=True)
print(f'Updated {len(tickers):,} US tickers')
"
```
```

---

### 🌏 Phase 3: Hong Kong Market (Week 2, Days 3-4)

**Objective**: Extend master file integration to HK market

**Priority**: **P1 - High**

**Duration**: 1-2 days

**Risk Level**: 🟡 Low-Medium

**Tasks**:
1. Update `hk_adapter_kis.py` with master file support (4 hours)
2. Create HK integration test script (2 hours)
3. Test with real HK data (2 hours)
4. Deploy to production (2 hours)
5. Validate in production (2 hours)

**Expected Results**:
- 500-1,000 HK stocks
- Scan time <1 second
- 100% data quality

**Reference**: `docs/MASTER_FILE_MULTI_REGION_GUIDE.md`

---

### 🗾 Phase 4: Japan Market (Week 2, Days 5-6)

**Objective**: Extend master file integration to JP market

**Priority**: **P1 - High**

**Duration**: 1-2 days

**Risk Level**: 🟡 Low-Medium

**Tasks**:
1. Update `jp_adapter_kis.py` with master file support (4 hours)
2. Create JP integration test script (2 hours)
3. Test with real JP data (2 hours)
4. Deploy to production (2 hours)
5. Validate in production (2 hours)

**Expected Results**:
- 500-1,000 JP stocks
- Scan time <1 second
- 100% data quality

---

### 🇨🇳 Phase 5: China Market (Week 3, Days 7-8)

**Objective**: Extend master file integration to CN market

**Priority**: **P2 - Medium**

**Duration**: 1-2 days

**Risk Level**: 🟡 Low-Medium

**Complexity**: Higher (2 exchanges: Shanghai + Shenzhen)

**Tasks**:
1. Update `cn_adapter_kis.py` with master file support (4 hours)
2. Create CN integration test script (2 hours)
3. Test with real CN data (3 hours)
4. Deploy to production (2 hours)
5. Validate in production (2 hours)

**Expected Results**:
- 500-1,000 CN stocks (선강통/후강통)
- Scan time <1 second
- 100% data quality

---

### 🇻🇳 Phase 6: Vietnam Market (Week 3, Day 9)

**Objective**: Extend master file integration to VN market

**Priority**: **P3 - Low**

**Duration**: 1 day

**Risk Level**: 🟢 Low

**Tasks**:
1. Update `vn_adapter_kis.py` with master file support (3 hours)
2. Create VN integration test script (1 hour)
3. Test with real VN data (1 hour)
4. Deploy to production (1 hour)
5. Validate in production (1 hour)

**Expected Results**:
- 100-300 VN stocks
- Scan time <1 second
- 100% data quality

---

### 📊 Phase 7: Final Validation & Reporting (Week 3, Day 10)

**Objective**: Complete validation and performance reporting

**Duration**: 1 day

**Tasks**:

1. **Multi-Region Validation** (2 hours)
   ```bash
   # Test all regions
   for region in US HK JP CN VN; do
       python3 -c "
       from modules.db_manager_sqlite import SQLiteDatabaseManager
       db = SQLiteDatabaseManager()
       tickers = db.get_tickers(region='$region')
       print(f'$region: {len(tickers):,} tickers')
       "
   done
   ```

2. **Performance Benchmarking** (2 hours)
   - Measure scan times per region
   - Compare vs API method
   - Document speedup metrics

3. **Data Quality Report** (2 hours)
   - Run quality validation for all regions
   - Document completeness percentages
   - Identify any data gaps

4. **API Call Reduction Report** (1 hour)
   - Calculate total API calls saved
   - Project weekly/monthly savings
   - Cost-benefit analysis

5. **Final Documentation** (2 hours)
   - Update deployment documentation
   - Create operational runbook
   - Document lessons learned

**Deliverables**:
- ✅ Multi-region deployment report
- ✅ Performance metrics dashboard
- ✅ Data quality scorecard
- ✅ API savings analysis
- ✅ Operational runbook

---

## Timeline Summary

| Phase | Tasks | Duration | Dependencies |
|-------|-------|----------|--------------|
| **Phase 0** | Pre-deployment validation | 0.5 day | None |
| **Phase 1** | US production deploy | 1 day | Phase 0 |
| **Phase 2** | Automated updates | 0.5 day | Phase 1 |
| **Phase 3** | HK market | 1-2 days | Phase 1 |
| **Phase 4** | JP market | 1-2 days | Phase 1 |
| **Phase 5** | CN market | 1-2 days | Phase 1 |
| **Phase 6** | VN market | 1 day | Phase 1 |
| **Phase 7** | Final validation | 1 day | All above |
| **Total** | Complete rollout | **8-11 days** | Sequential |

**Recommended Schedule**:
- **Week 1**: Phases 0-2 (US + automation)
- **Week 2**: Phases 3-4 (HK + JP)
- **Week 3**: Phases 5-7 (CN + VN + validation)

---

## Risk Management

### High-Risk Items

**Risk 1**: US production deployment fails
- **Probability**: Low (code tested, fallback available)
- **Impact**: High (blocks all subsequent phases)
- **Mitigation**: Pre-deployment validation, backup, rollback plan
- **Contingency**: Use API method, investigate and fix

**Risk 2**: Master file format changes
- **Probability**: Low (stable KIS format)
- **Impact**: Medium (region-specific failure)
- **Mitigation**: Graceful fallback to API method
- **Contingency**: Update parser, notify KIS API support

### Medium-Risk Items

**Risk 3**: yfinance enrichment fails
- **Probability**: Medium (external dependency)
- **Impact**: Low (optional enrichment)
- **Mitigation**: Use master file data directly
- **Contingency**: Make enrichment fully optional

**Risk 4**: Automated updates fail
- **Probability**: Low (simple script)
- **Impact**: Medium (stale data)
- **Mitigation**: Monitoring and alerting
- **Contingency**: Manual update, investigate and fix

---

## Success Metrics

### Technical Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| **US Ticker Coverage** | 85 | 6,527 | ✅ 77x |
| **Scan Time (US)** | ~2.5 min | <1s | ✅ 99.5% faster |
| **API Calls (scan)** | ~3,000 | 0 | ✅ 100% reduction |
| **Data Quality** | - | >95% | ✅ 100% |
| **Multi-Region Support** | US only | 5 regions | 🔄 In progress |

### Business Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Cost Reduction** | 100% (ticker scan) | Weekly API call count |
| **Operational Efficiency** | <1s scan time | Average scan duration |
| **Data Freshness** | Daily updates | Last update timestamp |
| **System Reliability** | >99% uptime | Monitoring dashboard |

---

## Communication Plan

### Stakeholders

**Technical Team**:
- Daily standup updates during deployment
- Slack notifications for milestones
- Incident alerts for failures

**Business Team**:
- Weekly progress reports
- Final deployment summary
- ROI analysis and metrics

### Status Updates

**Daily** (during deployment):
- Phase completion status
- Blockers and risks
- Next day plans

**Weekly**:
- Overall progress
- Performance metrics
- Business impact

**Final Report**:
- Complete deployment summary
- Performance improvements
- Lessons learned
- Future recommendations

---

## Appendix

### Quick Reference Commands

```bash
# Deploy US production
python3 scripts/deploy_us_adapter.py --full --days 250

# Test integration
python3 scripts/test_master_file_integration.py

# Manual update
python3 scripts/update_master_files.py

# Check database stats
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
for region in ['US', 'HK', 'JP', 'CN', 'VN']:
    count = len(db.get_tickers(region=region))
    print(f'{region}: {count:,} tickers')
"

# Monitor metrics
curl http://localhost:8000/metrics | grep spock_ohlcv_rows_total

# Check logs
tail -f logs/master_file_updates.log
```

### Contact Information

**Technical Support**:
- Email: spock-dev@example.com
- Slack: #spock-development

**Escalation**:
- Critical issues: Page on-call engineer
- Business questions: Product owner

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-15 | Spock Trading System | Initial prioritized deployment plan |

**Status**: ✅ Ready for execution
**Next Review**: After Phase 1 (US deployment)
