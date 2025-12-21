# DART Ticker Update - Monitoring Guide

**Date**: 2025-10-29
**Phase**: Week 4 - Orphaned Ticker Backfill with DART Enhancement

---

## Overview

This guide provides commands for monitoring the orphaned ticker backfill process and the DART update workflow.

### Process Flow
```
1. Initial Backfill (IN PROGRESS)
   ├─ pykrx lookup for active stocks/ETFs
   ├─ Timeout tickers get placeholder names: "032850 (Inferred)"
   └─ Status: 743/1,936 (38%) - ETA ~2.5 hours

2. DART Update (READY TO EXECUTE)
   ├─ Identify inferred tickers
   ├─ Update with official DART names
   └─ Set timeout_flag = TRUE for filtering

3. Validation
   ├─ Check no inferred names remain
   ├─ Verify timeout flags set correctly
   └─ Confirm data source consistency
```

---

## 📊 Current Backfill Monitoring

### Real-time Progress Monitoring

**Watch live log output**:
```bash
tail -f log/backfill_orphaned_tickers_20251029_142617.log
```

**Check current progress**:
```bash
tail -20 log/backfill_orphaned_tickers_20251029_142617.log | grep "Processing"
```

**Count progress**:
```bash
grep -c "Processing" log/backfill_orphaned_tickers_20251029_142617.log
```

**Check timeout warnings** (tickers that will need DART updates):
```bash
grep "pykrx timeout" log/backfill_orphaned_tickers_20251029_142617.log | wc -l
```

**View recent successes**:
```bash
grep "✅" log/backfill_orphaned_tickers_20251029_142617.log | tail -10
```

### Process Status

**Check if backfill is still running**:
```bash
ps aux | grep backfill_orphaned_tickers.py | grep -v grep
```

**Kill hung process** (if needed):
```bash
pkill -f "backfill_orphaned_tickers.py"
```

### Database Queries

**Count tickers by data source**:
```sql
psql -d quant_platform -c "
SELECT data_source, COUNT(*) as count
FROM tickers
WHERE region = 'KR'
GROUP BY data_source
ORDER BY count DESC;
"
```

**Count inferred tickers** (need DART updates):
```sql
psql -d quant_platform -c "
SELECT COUNT(*) as inferred_count
FROM tickers
WHERE region = 'KR' AND name LIKE '%Inferred%';
"
```

**Sample inferred tickers**:
```sql
psql -d quant_platform -c "
SELECT ticker, name, exchange, data_source, timeout_flag
FROM tickers
WHERE region = 'KR' AND name LIKE '%Inferred%'
LIMIT 10;
"
```

---

## 🎯 DART Update Execution

### Phase 1: Dry Run Test (Recommended)

**Test on 20 tickers** (no database changes):
```bash
python3 scripts/update_inferred_tickers_with_dart.py --dry-run --limit 20
```

**Expected output**:
```
Loading DART corp codes from config/dart_corp_codes.xml
Loaded 3717 ticker-to-name mappings from DART
Found N tickers with inferred names

[1/20] Processing 000440...
✅ 000440: Updating name
   OLD: 000440 (Inferred)
   NEW: 중앙에너비스

Update Summary:
✅ Updated: X
✓  Already correct: Y
⚠️  Not in DART: Z
Success rate: XX.X%
DART coverage: XX.X%
```

### Phase 2: Full Update (After Backfill Completes)

**Update ALL inferred tickers**:
```bash
python3 scripts/update_inferred_tickers_with_dart.py
```

**Monitor update log**:
```bash
tail -f log/update_dart_tickers_YYYYMMDD_HHMMSS.log
```

**Update with limit** (incremental approach):
```bash
python3 scripts/update_inferred_tickers_with_dart.py --limit 100
```

### Phase 3: Validation

**Run validation checks**:
```bash
python3 scripts/update_inferred_tickers_with_dart.py --validate
```

**Expected validation output**:
```
Validation Checks
================================================================================
✅ Check 1 PASSED: No tickers with inferred names
✅ Check 2 PASSED: All DART tickers have timeout_flag = TRUE
✅ Check 3 PASSED: Data source consistency verified

✅ All validation checks PASSED
```

---

## 📈 Progress Tracking Queries

### Backfill Progress

**Overall progress**:
```sql
psql -d quant_platform -c "
SELECT
    COUNT(*) FILTER (WHERE name NOT LIKE '%Inferred%') as completed,
    COUNT(*) FILTER (WHERE name LIKE '%Inferred%') as pending,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE name NOT LIKE '%Inferred%') / COUNT(*), 1) as progress_pct
FROM tickers
WHERE region = 'KR' AND created_at > '2025-10-29 14:26:00';
"
```

**Data source breakdown**:
```sql
psql -d quant_platform -c "
SELECT
    data_source,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM tickers
WHERE region = 'KR'
GROUP BY data_source
ORDER BY count DESC;
"
```

### DART Update Progress

**Before DART update**:
```sql
psql -d quant_platform -c "
SELECT
    'Inferred names' as status,
    COUNT(*) as count
FROM tickers
WHERE region = 'KR' AND name LIKE '%Inferred%'
UNION ALL
SELECT
    'Timeout flags set' as status,
    COUNT(*) as count
FROM tickers
WHERE region = 'KR' AND timeout_flag = TRUE
ORDER BY status;
"
```

**After DART update**:
```sql
psql -d quant_platform -c "
SELECT
    CASE
        WHEN data_source = 'DART' THEN 'DART (official names)'
        WHEN data_source = 'pykrx' THEN 'pykrx (active)'
        WHEN data_source = 'inference' THEN 'Inference (fallback)'
        ELSE 'Other'
    END as source,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE timeout_flag = TRUE) as with_timeout_flag,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timeout_flag = TRUE) / COUNT(*), 1) as flag_pct
FROM tickers
WHERE region = 'KR'
GROUP BY data_source
ORDER BY count DESC;
"
```

---

## 🔍 Data Quality Checks

### Timeout Ticker Analysis

**Count timeout tickers by exchange**:
```sql
psql -d quant_platform -c "
SELECT
    exchange,
    COUNT(*) as timeout_count
FROM tickers
WHERE region = 'KR' AND timeout_flag = TRUE
GROUP BY exchange
ORDER BY timeout_count DESC;
"
```

**Sample timeout tickers**:
```sql
psql -d quant_platform -c "
SELECT
    ticker,
    name,
    exchange,
    data_source,
    last_updated
FROM tickers
WHERE region = 'KR' AND timeout_flag = TRUE
ORDER BY last_updated DESC
LIMIT 20;
"
```

### Backtesting Safety Check

**Count usable tickers** (exclude timeout tickers):
```sql
psql -d quant_platform -c "
SELECT
    exchange,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE timeout_flag = FALSE) as backtest_safe,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timeout_flag = FALSE) / COUNT(*), 1) as safe_pct
FROM tickers
WHERE region = 'KR' AND is_active = TRUE
GROUP BY exchange
ORDER BY total DESC;
"
```

**Example backtesting query** (filter out timeout tickers):
```sql
psql -d quant_platform -c "
SELECT t.ticker, t.name, o.close
FROM tickers t
JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
WHERE t.region = 'KR'
  AND t.timeout_flag = FALSE  -- Exclude delisted/suspended stocks
  AND o.date = '2025-10-28'
  AND t.exchange = 'KOSPI'
LIMIT 10;
"
```

---

## ⚠️ Troubleshooting

### Issue 1: Backfill Hangs

**Symptoms**: No log output for 5+ minutes

**Solution**:
```bash
# Check if process is hung
ps aux | grep backfill_orphaned_tickers.py

# Kill and restart
pkill -f "backfill_orphaned_tickers.py"
sleep 2

# Restart backfill (will skip already-processed tickers)
python3 scripts/backfill_orphaned_tickers.py --rate-limit 0.5
```

### Issue 2: DART Update Fails

**Symptoms**: "Failed to load DART corp codes" error

**Solution**:
```bash
# Verify DART corp codes file exists
ls -lh config/dart_corp_codes.xml

# Re-download if missing (27MB file)
# Run DART data collection script (if available)
```

### Issue 3: Database Connection Lost

**Symptoms**: "connection already closed" error

**Solution**:
```bash
# Check PostgreSQL status
brew services list | grep postgresql

# Restart PostgreSQL
brew services restart postgresql@17

# Verify connection
psql -d quant_platform -c "SELECT COUNT(*) FROM tickers;"
```

---

## 📋 Execution Checklist

### Pre-Execution
- [ ] Verify backfill process completed (100%)
- [ ] Check log for final summary statistics
- [ ] Query database for inferred ticker count
- [ ] Ensure DART corp codes loaded (3,717 mappings)

### Execution
- [ ] Run dry-run test with `--limit 20`
- [ ] Review dry-run output for correctness
- [ ] Execute full update without `--dry-run`
- [ ] Monitor log file for errors
- [ ] Verify no database connection issues

### Post-Execution
- [ ] Run validation checks (`--validate`)
- [ ] Query database for remaining inferred names (should be 0)
- [ ] Verify timeout_flag set correctly
- [ ] Check DART coverage percentage (target: >95%)
- [ ] Test sample backtesting query with timeout_flag filter

---

## 📊 Expected Results

### Backfill Completion
```
Total processed: 1,936
✅ Success: 1,900+
✓  Already exists: 489
⚠️  No metadata: <50
Success rate: >95%
```

### DART Update Completion
```
Total processed: ~128 (timeout tickers)
✅ Updated: ~125
⚠️  Not in DART: ~3 (2.3%)
Success rate: 100%
DART coverage: 97.7%
```

### Final Database State
```
Total KR tickers: ~2,900
- pykrx (active): ~1,800 (62%)
- DART (delisted): ~125 (4%)
- Inference (fallback): ~3 (0.1%)
- Pre-existing: ~972 (33%)

Timeout flags: ~128 (4.4% of total)
```

---

## 🎯 Next Steps

After DART update completes:

1. **Deploy Automated Anomaly Detection** (Task 10.3)
   - Cron job: Daily 09:00 KST
   - Query: Detect 500%+ price changes
   - Alert: Email/Slack notification

2. **Begin Factor Library Development** (Week 5)
   - Implement Quality factors (ROE, Debt/Equity)
   - Add Low-Volatility factors (Beta, Max DD)
   - Calculate composite factor scores

3. **Backtest Strategy Development** (Week 7+)
   - Value+Momentum strategy
   - Walk-forward optimization
   - Out-of-sample validation

---

**Last Updated**: 2025-10-29 15:37
**Status**: Backfill 38% complete (743/1,936), DART update script ready
**Next Action**: Monitor backfill completion, execute DART update
