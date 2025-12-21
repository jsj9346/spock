# Comprehensive Data Pipeline Improvement Plan

## Executive Summary
**Goal**: Fix data update pipeline to ensure all regions have fresh, consistent data in PostgreSQL
**Timeline**: 3 phases over 2-3 days
**Priority**: P0 (Critical) - Data freshness directly impacts platform reliability

**Diagnosed Issues**:
1. 🔥 KR OHLCV data stored in SQLite only, not migrated to PostgreSQL (18 days stale)
2. 🔥 Incremental mode too conservative - only 12% of tickers updated (61/497)
3. ⚠️ Macro data not automated - Global Indices 27 days old, Market Sentiment missing

---

## Phase 1: Critical Fixes (Day 1 - 4 hours) 🔥 URGENT

### Task 1.1: KR OHLCV PostgreSQL Direct Integration
**Priority**: P0 - Highest
**Estimated Time**: 2 hours
**Owner**: orchestrator.py, kis_data_collector.py

**Current State**:
```python
# modules/orchestration/orchestrator.py line ~850
if region == "KR":
    # Delegates to kis_data_collector → SQLite only
    result = self._collect_kr_ohlcv_kis(...)  # ❌ SQLite
```

**Target State**:
```python
if region == "KR":
    # Direct PostgreSQL integration
    result = self._collect_kr_ohlcv_postgres(...)  # ✅ PostgreSQL
    # Fallback to SQLite + migration if needed
```

**Implementation Steps**:
1. Create new `KRPostgresOHLCVAdapter` class
2. Modify `kis_data_collector.py` to support dual output
3. Update orchestrator to use PostgreSQL adapter
4. Add validation after insert

**Success Criteria**:
- ✅ KR OHLCV data directly inserted to PostgreSQL
- ✅ Latest date = today's date (for market days)
- ✅ No SQLite dependency for new data

---

### Task 1.2: Incremental Mode Logic Fix
**Priority**: P0 - Highest
**Estimated Time**: 1.5 hours
**Owner**: modules/collection/yfinance_ohlcv_adapter.py

**Current Issue**:
```python
# Too conservative filtering
if ticker already has data for today:
    skip ticker  # ❌ Misses intraday updates, corrections
```

**Target Logic**:
```python
# Smart incremental update
last_available_date = get_last_trading_date(region, ticker)
last_db_date = get_last_db_date(ticker)

if last_db_date is None:
    # New ticker - full backfill (365 days)
    fetch_range = (today - 365 days, today)
elif last_db_date < last_available_date - 7 days:
    # Stale data - incremental catchup
    fetch_range = (last_db_date, today)
elif mode == "force_refresh":
    # Force refresh last 30 days (for corrections)
    fetch_range = (today - 30 days, today)
else:
    # Up to date
    skip ticker
```

**Implementation Steps**:
1. Add `get_last_trading_date()` helper per region
2. Modify incremental filtering logic
3. Add `--force-refresh` flag for corrections
4. Test with various ticker scenarios

**Success Criteria**:
- ✅ 90%+ tickers updated in incremental mode
- ✅ No false skips for outdated data
- ✅ Configurable refresh window

---

### Task 1.3: SQLite → PostgreSQL Migration Script
**Priority**: P1 - High
**Estimated Time**: 30 minutes
**Owner**: scripts/migrate_sqlite_to_postgres.py (new)

**Purpose**: Migrate existing KR data from SQLite to PostgreSQL

**Implementation**:
```python
#!/usr/bin/env python3
"""
Migrate OHLCV data from SQLite to PostgreSQL
Usage: python3 scripts/migrate_sqlite_to_postgres.py --region KR --dry-run
"""

def migrate_ohlcv(region, start_date, end_date, dry_run=True):
    # 1. Connect to SQLite
    sqlite_db = connect_sqlite("data/spock_local.db")

    # 2. Extract data
    data = extract_ohlcv(sqlite_db, region, start_date, end_date)

    # 3. Validate data
    validate_ohlcv_data(data)

    # 4. Upsert to PostgreSQL
    if not dry_run:
        postgres_db.upsert_ohlcv_batch(data)

    # 5. Validate migration
    verify_migration(region, start_date, end_date)
```

**Success Criteria**:
- ✅ All KR data from SQLite migrated to PostgreSQL
- ✅ Data integrity validated (no duplicates, no gaps)
- ✅ Dry-run mode for safety

---

## Phase 2: Macro Data & Automation (Day 1-2 - 3 hours)

### Task 2.1: Integrate Macro Data Collection
**Priority**: P1 - High
**Estimated Time**: 2 hours
**Owner**: modules/orchestration/orchestrator.py

**New Steps in Pipeline**:
```python
# Add to update_database.py workflow
steps = [
    'tickers',
    'ohlcv',
    'fundamentals',
    'macro_indices',      # ← NEW: Global market indices
    'macro_sentiment',    # ← NEW: Market sentiment
    'daily_valuation',
    'dividend',
    'fx_tracking'
]
```

**Implementation**:
1. Create `MacroDataAdapter` class
2. Integrate `scripts/collect_macro_data.py` logic
3. Add to orchestrator workflow
4. Schedule daily updates

**Data Sources**:
- **Global Indices**: yfinance (^GSPC, ^IXIC, ^DJI, ^N225, ^HSI, etc.)
- **Market Sentiment**: Fear & Greed Index, VIX, Put/Call ratio

**Success Criteria**:
- ✅ Global indices updated daily
- ✅ Market sentiment calculated daily
- ✅ Automated as part of standard pipeline

---

### Task 2.2: Add Data Freshness Monitoring
**Priority**: P2 - Medium
**Estimated Time**: 1 hour
**Owner**: modules/monitoring/data_freshness.py (new)

**Monitoring Rules**:
```python
FRESHNESS_THRESHOLDS = {
    'ohlcv': {
        'warning': 3,   # days
        'critical': 7,  # days
    },
    'fundamentals': {
        'warning': 7,
        'critical': 14,
    },
    'macro_indices': {
        'warning': 1,
        'critical': 3,
    }
}
```

**Implementation**:
1. Create monitoring class
2. Add to orchestrator validation step
3. Generate alerts (console + log)
4. Optional: Email/Slack notifications

**Success Criteria**:
- ✅ Automatic freshness checks after updates
- ✅ Clear warnings for stale data
- ✅ Actionable alerts

---

## Phase 3: Architecture Improvements (Day 2-3 - 4 hours)

### Task 3.1: Unified OHLCV Adapter Interface
**Priority**: P2 - Medium
**Estimated Time**: 2 hours
**Owner**: modules/collection/unified_ohlcv_adapter.py (new)

**Goal**: Single interface for all regions

**Current Architecture**:
```
KR  → kis_data_collector → SQLite
US  → yfinance_adapter → PostgreSQL
HK  → yfinance_adapter → PostgreSQL
...
```

**Target Architecture**:
```
All Regions → UnifiedOHLCVAdapter → PostgreSQL
                    ↓
          (region-specific collectors)
                    ↓
          KRCollector | YFinanceCollector
```

**Implementation**:
```python
class UnifiedOHLCVAdapter:
    def collect(self, region, tickers, start_date, end_date):
        # 1. Select appropriate collector
        collector = self._get_collector(region)

        # 2. Collect data
        data = collector.fetch(tickers, start_date, end_date)

        # 3. Standardize format
        standardized = self._standardize_data(data, region)

        # 4. Validate
        self._validate_data(standardized)

        # 5. Insert to PostgreSQL
        self.db.upsert_ohlcv_batch(standardized)

        # 6. Return result
        return CollectionResult(...)
```

**Success Criteria**:
- ✅ Consistent interface across all regions
- ✅ Easier to add new regions
- ✅ Centralized validation and error handling

---

### Task 3.2: Smart Retry & Fallback Logic
**Priority**: P2 - Medium
**Estimated Time**: 1.5 hours
**Owner**: modules/collection/retry_handler.py (new)

**Retry Strategy**:
```python
class SmartRetryHandler:
    def execute_with_retry(self, operation, max_retries=3):
        for attempt in range(max_retries):
            try:
                return operation()
            except RateLimitError:
                backoff = exponential_backoff(attempt)
                time.sleep(backoff)
            except DataNotFoundError:
                # Try alternative source
                return fallback_operation()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                log_retry_attempt(attempt, e)
```

**Success Criteria**:
- ✅ Automatic retry on transient failures
- ✅ Exponential backoff for rate limits
- ✅ Fallback to alternative sources

---

### Task 3.3: Post-Update Validation Pipeline
**Priority**: P2 - Medium
**Estimated Time**: 30 minutes
**Owner**: modules/validation/post_update_validator.py (new)

**Validation Checks**:
```python
def validate_update(region, date_range):
    checks = [
        check_data_completeness(region, date_range),
        check_price_anomalies(region, date_range),
        check_volume_sanity(region, date_range),
        check_date_gaps(region, date_range),
        check_duplicate_records(region, date_range)
    ]

    report = ValidationReport(checks)

    if report.has_critical_issues():
        rollback_update()
        raise ValidationError(report)

    return report
```

**Success Criteria**:
- ✅ Automatic validation after every update
- ✅ Data quality issues caught early
- ✅ Rollback capability for failed updates

---

## Implementation Timeline

### Day 1 (4 hours)
**Morning (2h)**:
- ✅ Task 1.1: KR PostgreSQL integration
- ✅ Task 1.3: Migration script

**Afternoon (2h)**:
- ✅ Task 1.2: Incremental mode fix
- ✅ Test end-to-end update

### Day 2 (3 hours)
**Morning (2h)**:
- ✅ Task 2.1: Macro data integration

**Afternoon (1h)**:
- ✅ Task 2.2: Freshness monitoring

### Day 3 (4 hours) - Optional Enhancements
**Morning (2h)**:
- ✅ Task 3.1: Unified adapter

**Afternoon (2h)**:
- ✅ Task 3.2: Retry logic
- ✅ Task 3.3: Validation pipeline

---

## Success Metrics

### Data Freshness (Primary Goal)
- ✅ KR: Latest date = trading day (within 1 day)
- ✅ US/HK/JP/CN/VN: Latest date = trading day (within 1 day)
- ✅ Macro indices: Latest date = today (within 1 day)
- ✅ Market sentiment: Latest date = today (within 1 day)

### Update Reliability
- ✅ 95%+ ticker coverage in incremental mode
- ✅ Zero silent failures (all errors logged & alerted)
- ✅ <5% data quality issues post-update

### Performance
- ✅ Full refresh: <60 minutes (all regions)
- ✅ Incremental update: <10 minutes (all regions)
- ✅ Macro data: <5 minutes

### Code Quality
- ✅ Single code path for all regions (unified adapter)
- ✅ 80%+ test coverage for critical paths
- ✅ Clear error messages and logging

---

## Risk Mitigation

### Risk 1: Data Loss During Migration
**Mitigation**:
- Always run dry-run first
- Backup SQLite database before migration
- Validate data counts before/after

### Risk 2: Breaking Existing Workflows
**Mitigation**:
- Maintain backward compatibility
- Feature flags for new adapters
- Gradual rollout (KR first, then others)

### Risk 3: API Rate Limits
**Mitigation**:
- Implement exponential backoff
- Monitor rate limit usage
- Distribute requests over time

### Risk 4: Database Performance Degradation
**Mitigation**:
- Batch inserts (1000 rows at a time)
- Use indexes appropriately
- Monitor query performance

---

## Next Steps

1. **Review & Approve Plan**: Stakeholder sign-off
2. **Setup Development Branch**: `feature/data-pipeline-improvements`
3. **Start Phase 1**: Critical fixes
4. **Daily Standups**: Track progress
5. **Testing**: Validate after each phase
6. **Documentation**: Update CLAUDE.md with new workflows
7. **Deploy**: Gradual rollout with monitoring

---

**Document Version**: 1.0
**Created**: 2025-11-16
**Last Updated**: 2025-11-16
**Status**: Approved for Implementation
