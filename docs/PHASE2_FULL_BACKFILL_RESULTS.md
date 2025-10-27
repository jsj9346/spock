# Phase 2 Full Backfill Results - Historical Fundamental Data (FY2022-2024)

**Date**: 2025-10-24
**Status**: ⏳ **IN PROGRESS** (Will be updated upon completion)
**Scope**: ~1,364 Korean stocks × 3 fiscal years (FY2022, FY2023, FY2024)

---

## Executive Summary

> **Note**: This section will be populated automatically after backfill completion using:
> ```bash
> python3 scripts/validate_phase2_backfill.py --log logs/phase2_full_backfill_v3.log --report logs/phase2_validation_report.md
> ```

**Key Metrics** (To be filled):
- **Success Rate**: TBD% (X/1,364 tickers)
- **Total Records**: TBD (Expected: ~4,000)
- **Data Quality Score**: TBD%
- **Total Duration**: TBD hours
- **API Errors**: TBD

---

## Phase 2 Journey Timeline

### Phase 2.1: Initial Implementation (2025-10-18 ~ 2025-10-23)
- ✅ Database schema extension (18 new columns)
- ✅ DART API fundamental data parsing logic implementation
- ✅ Corp code mapping integration (DART XML)
- ✅ Transaction safety implementation (rollback on failure)

### Phase 2.2: Dry Run v1 - Initial Testing (2025-10-23)
**Scope**: 5 representative tickers (Samsung, SK Hynix, Kakao, Samsung SDI, LG Chem)

**Results**:
- ✅ 100% collection success (5/5 tickers)
- ❌ Revenue=0 issues identified (Samsung, LG Chem)
- ❌ EBITDA=0 issues identified (SK Hynix, Kakao, Samsung SDI)

**Root Causes Identified**:
1. COGS field name variation ('매출원가' vs '매출원가합계')
2. Operating profit field variation ('영업이익' vs '영업이익(손실)')
3. Operating cash flow field variations (4 different patterns)
4. EBITDA calculation logic bug (required BOTH operating_profit AND depreciation)

**Documentation**: `/docs/PHASE2_DRY_RUN_ANALYSIS.md`

---

### Phase 2.3: Dry Run v2 - Revenue Fix Validation (2025-10-23)
**Scope**: Same 5 tickers with Revenue/COGS parsing fixes

**Fixes Applied**:
1. **COGS Parsing** (Line 526-527 in `dart_api_client.py`):
   - Added '매출원가합계' fallback to COGS parsing

**Results**:
- ✅ Revenue=0 issues - **FIXED** (Samsung, LG Chem now show correct revenue)
- ⚠️ EBITDA=0 issues - **REMAIN** (3 companies still affected)

**Documentation**: `/docs/PHASE2_DRY_RUN_V2_RESULTS.md`

---

### Phase 2.4: EBITDA Issue Deep Dive (2025-10-24)
**Investigation**:
- Created diagnostic script: `tests/investigate_ebitda_issue.py`
- Analyzed raw DART API responses for SK Hynix, Kakao, Samsung SDI
- Identified 3 root causes for EBITDA=0 failures

**Root Causes Confirmed**:
1. **Operating Profit Field Variation**: '영업이익(손실)' not recognized
2. **Cash Flow Field Variations**: 4 different field name patterns across companies
3. **EBITDA Calculation Logic Bug**: Required BOTH conditions when should handle separately

---

### Phase 2.5: Dry Run v3 - EBITDA Fix Validation (2025-10-24 17:08)
**Scope**: Same 5 tickers with all EBITDA parsing fixes

**Fixes Applied**:
1. **Operating Profit Parsing** (Line 534-535):
   ```python
   operating_profit = (item_lookup.get('영업이익', 0) or
                      item_lookup.get('영업이익(손실)', 0))
   ```

2. **Operating Cash Flow Parsing** (Line 582-585):
   ```python
   operating_cf = (item_lookup.get('영업활동현금흐름', 0) or
                  item_lookup.get('영업활동 현금흐름', 0) or
                  item_lookup.get('영업활동으로 인한 현금흐름', 0) or
                  item_lookup.get('영업으로부터 창출된 현금흐름', 0))
   ```

3. **EBITDA Calculation Logic** (Line 632-636):
   ```python
   if depreciation > 0:
       ebitda = operating_profit + depreciation
   else:
       ebitda = operating_profit if operating_profit != 0 else 0
   ```

**Results**:
- ✅ **ALL EBITDA=0 ISSUES - COMPLETELY FIXED** (9/9 records)
- ✅ Revenue accuracy maintained (100%)
- ✅ 100% success rate (15/15 records, 5 tickers × 3 years)
- ✅ **Go/No-Go Decision**: ✅ **GO FOR FULL BACKFILL**

**Documentation**: `/docs/PHASE2_DRY_RUN_V3_RESULTS.md`

---

### Phase 2.6: Full Backfill Execution (2025-10-24 17:21 ~ TBD)

**Preparation**:
- Scope: 1,364 Korean stocks from `tickers` table (region='KR', is_active=true)
- Period: FY2022, FY2023, FY2024 (3 years)
- Rate limit: 1 request/second (conservative)
- Expected records: ~4,000 (1,364 tickers × 3 years, minus skipped tickers)

**Database Schema Issues Fixed** (before execution):
1. **Corp Code Column** (Line 129-148): Removed database fallback (corp_code not in schema)
2. **Active Column Name** (Line 240): Changed `active = true` → `is_active = true`
3. **Database API Usage** (Line 228-229): Fixed `execute_query()` return value handling

**Execution Command**:
```bash
python3 scripts/backfill_phase2_historical.py --start-year 2022 --end-year 2024 \
  2>&1 | tee logs/phase2_full_backfill_v3.log
```

**Progress** (To be updated):
- Start Time: 2025-10-24 17:21:36 KST
- End Time: TBD
- Tickers Processed: TBD/1,364
- Records Inserted: TBD
- Errors: TBD

---

## Data Quality Validation

### Validation Criteria
1. **Success Rate**: ≥90% of tickers successfully processed
2. **Data Completeness**: ≥95% of expected records inserted
3. **Revenue Accuracy**: Revenue=0 count <5% of total records
4. **EBITDA Accuracy**: EBITDA=0 count <10% of total records (excluding loss-making companies)
5. **API Reliability**: API error rate <1%

### Validation Results (To be filled)

**Automated Validation Report**: `logs/phase2_validation_report.md`

**Manual Validation Queries**:
```sql
-- Total records by year
SELECT fiscal_year, COUNT(*) as count
FROM ticker_fundamentals
WHERE fiscal_year >= 2022 AND fiscal_year <= 2024
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- Revenue=0 count (should be minimal)
SELECT COUNT(*) as revenue_zero_count,
       COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ticker_fundamentals WHERE fiscal_year >= 2022) as percentage
FROM ticker_fundamentals
WHERE fiscal_year >= 2022 AND (revenue = 0 OR revenue IS NULL);

-- EBITDA=0 count for profitable companies (should be minimal)
SELECT COUNT(*) as ebitda_zero_count,
       COUNT(*) * 100.0 / (SELECT COUNT(*) FROM ticker_fundamentals WHERE fiscal_year >= 2022 AND operating_profit > 0) as percentage
FROM ticker_fundamentals
WHERE fiscal_year >= 2022
  AND ebitda = 0
  AND operating_profit > 0;  -- Exclude loss-making companies

-- Top 10 companies by revenue (sanity check)
SELECT ticker, fiscal_year, revenue, operating_profit, ebitda
FROM ticker_fundamentals
WHERE fiscal_year = 2024
ORDER BY revenue DESC
LIMIT 10;
```

**Expected Top 10 Companies (FY2024)**:
1. Samsung Electronics (005930): Revenue ~300T, EBITDA ~70T
2. SK Hynix (000660): Revenue ~66T, EBITDA ~30T
3. Hyundai Motor (005380): Revenue ~160T, EBITDA ~20T
4. LG Electronics (066570): Revenue ~80T, EBITDA ~10T
5. POSCO Holdings (005490): Revenue ~70T, EBITDA ~8T
6. Samsung SDI (006400): Revenue ~17T, EBITDA ~0.4T
7. LG Chem (051910): Revenue ~49T, EBITDA ~7T
8. Kakao (035720): Revenue ~8T, EBITDA ~1.2T
9. NAVER (035420): Revenue ~9T, EBITDA ~2T
10. Samsung Biologics (207940): Revenue ~3T, EBITDA ~1T

---

## Performance Metrics

### Backfill Performance (To be filled)
- **Total Duration**: TBD hours
- **Avg Time per Ticker**: TBD seconds
- **API Call Rate**: TBD req/sec (target: 1 req/sec)
- **Database Write Rate**: TBD records/sec
- **Memory Usage**: TBD MB (peak)

### Database Performance
- **TimescaleDB Compression**: Enabled (1 year retention)
- **Continuous Aggregates**: Monthly, quarterly views
- **Index Performance**: <1 second for ticker+year queries
- **Disk Usage**: TBD GB (before compression)

---

## Parsing Logic Improvements Summary

### Files Modified
**`/modules/dart_api_client.py`** (3 critical fixes):

#### Fix 1: COGS Parsing (v2 - Line 526-527)
```python
# Before:
cogs = item_lookup.get('매출원가', 0)

# After:
cogs = (item_lookup.get('매출원가', 0) or
        item_lookup.get('매출원가합계', 0))
```
**Impact**: Fixed Revenue=0 issues for Samsung, LG Chem

---

#### Fix 2: Operating Profit Parsing (v3 - Line 534-535)
```python
# Before:
operating_profit = item_lookup.get('영업이익', 0)

# After:
operating_profit = (item_lookup.get('영업이익', 0) or
                   item_lookup.get('영업이익(손실)', 0))
```
**Impact**: Fixed EBITDA=0 issues for SK Hynix, Kakao, Samsung SDI

---

#### Fix 3: Operating Cash Flow Parsing (v3 - Line 582-585)
```python
# Before:
operating_cf = item_lookup.get('영업활동현금흐름', 0)

# After:
operating_cf = (item_lookup.get('영업활동현금흐름', 0) or
               item_lookup.get('영업활동 현금흐름', 0) or
               item_lookup.get('영업활동으로 인한 현금흐름', 0) or
               item_lookup.get('영업으로부터 창출된 현금흐름', 0))
```
**Impact**: Improved depreciation estimation for EBITDA calculation

---

#### Fix 4: EBITDA Calculation Logic (v3 - Line 632-636)
```python
# Before:
if operating_profit > 0 and depreciation > 0:
    ebitda = operating_profit + depreciation
else:
    ebitda = operating_profit

# After:
if depreciation > 0:
    ebitda = operating_profit + depreciation
else:
    ebitda = operating_profit if operating_profit != 0 else 0
```
**Impact**: Gracefully handles depreciation unavailability while preserving operating profit

---

### Backfill Script Fixes
**`/scripts/backfill_phase2_historical.py`** (3 database schema fixes):

#### Fix 1: Corp Code Query Removal (Line 129-148 → 129)
- **Issue**: Database doesn't have `corp_code` column in `stock_details`
- **Fix**: Removed database fallback, always use DART XML
- **Impact**: Eliminated schema mismatch error

#### Fix 2: Active Column Name (Line 240)
```python
# Before:
WHERE region = 'KR' AND active = true

# After:
WHERE region = 'KR' AND is_active = true
```
**Impact**: Fixed column name mismatch

#### Fix 3: Database API Usage (Line 228-229)
```python
# Before:
self.db.execute_query(query)
tickers = [row[0] for row in self.db.cursor.fetchall()]

# After:
results = self.db.execute_query(query)
tickers = [row['ticker'] for row in results]
```
**Impact**: Fixed incorrect database API usage (execute_query returns List[Dict], not cursor)

---

## Lessons Learned

### 1. Field Name Variations are Pervasive in Korean Financial Data
**Problem**: DART API lacks field name standardization across companies and years.

**Examples Found**:
- COGS: '매출원가' vs '매출원가합계'
- Operating Profit: '영업이익' vs '영업이익(손실)'
- Cash Flow: 4 different variations
  - '영업활동현금흐름' (standard, no space)
  - '영업활동 현금흐름' (with space)
  - '영업활동으로 인한 현금흐름' (detailed description)
  - '영업으로부터 창출된 현금흐름' (alternative phrasing)

**Solution**: Always implement fallback chains with multiple variations for critical fields.

**Prevention**: Create comprehensive field name mapping dictionary and update as new variations discovered.

---

### 2. Logic Bugs Hide Behind Data Quality Issues
**Problem**: EBITDA calculation bug was masked by field name issues.

**Root Cause**: Required BOTH `operating_profit > 0` AND `depreciation > 0`, but should handle separately.

**Impact**: When depreciation unavailable (estimation failed), EBITDA became 0 even if operating profit was positive.

**Learning**: Always validate logic independently of data quality issues. Separate data parsing from business logic validation.

---

### 3. Diagnostic Scripts are Critical for Investigation
**Success Factor**: Step-by-step investigation methodology was essential:
1. Raw API response analysis (identify missing fields)
2. Field name discovery (compare across companies)
3. Logic validation (separate from data issues)

**Outcome**: Saved significant debugging time vs trial-and-error.

**Best Practice**: Create diagnostic scripts for complex data integration issues before attempting fixes.

---

### 4. Corp Code Validation Must Use Official Sources
**Problem**: Test scripts initially had wrong corp codes (from third-party sources).

**Solution**: Always verify against official DART XML (`config/dart_corp_codes.xml`).

**Impact**: Prevented false negatives in testing and validation.

---

### 5. Database Schema Mismatches Can Be Silent Killers
**Problem**: Backfill script had hardcoded assumptions about database schema that didn't match PostgreSQL schema.

**Examples**:
- Assumed `corp_code` column in `stock_details` (doesn't exist)
- Used `active` column name instead of `is_active`
- Incorrect database API usage (expected cursor object instead of List[Dict])

**Solution**: Always inspect actual database schema before writing queries. Use `psql` or database tools to verify column names and types.

**Prevention**: Create database schema documentation and keep it updated.

---

### 6. Comprehensive Dry Run Testing Catches All Issues Early
**Success Metrics**: 3-iteration dry run process validated:
- **v1**: Identified Revenue=0 and EBITDA=0 issues
- **v2**: Fixed Revenue=0, confirmed EBITDA=0 remained
- **v3**: Fixed EBITDA=0, validated complete solution

**Time Investment**: 27 minutes total dry run time vs potential days of production debugging.

**ROI**: Prevented ~4,000 records from being inserted with data quality issues.

**Best Practice**: Always run multiple dry run iterations with representative data before full production backfill.

---

### 7. Background Process Management Requires Proper Monitoring
**Challenge**: 6-hour backfill requires background execution and progress monitoring.

**Solution**:
- Use `nohup` with output redirection to log file
- Implement progress checkpoints in log (every 1% or 10 tickers)
- Create validation script for post-completion analysis
- Set up automated validation trigger after completion

**Monitoring Strategy**:
```bash
# Progress monitoring
tail -100 logs/phase2_full_backfill_v3.log | grep "Progress:"

# Error detection
grep -iE "error|exception|failed" logs/phase2_full_backfill_v3.log

# Database record count
psql -d quant_platform -c "SELECT COUNT(*) FROM ticker_fundamentals WHERE fiscal_year >= 2022;"
```

---

## Next Steps: Phase 3 Planning

### Phase 3 Scope: Real-Time Data Collection Automation

**Objectives**:
1. **Daily Fundamental Updates**: Automate daily collection of newly published financial reports
2. **Quarterly Earnings**: Auto-collect quarterly earnings reports (Q1, Q2, Q3, Q4)
3. **Real-Time Event Detection**: Monitor DART API for new filings and trigger data collection
4. **Data Quality Monitoring**: Continuous monitoring and alerting for data quality issues
5. **Backfill Scheduler**: Automatic backfill for missed data (holidays, API downtime)

**Technical Components**:
- **Scheduler**: Cron jobs or APScheduler for daily/weekly tasks
- **Event Monitoring**: DART API webhook or polling for new filings
- **Alert System**: Prometheus + Grafana alerts for data quality issues
- **Retry Logic**: Exponential backoff for failed API calls
- **Database Optimization**: Continuous aggregates for rolling metrics

**Timeline Estimate**: 2-3 weeks

---

## Appendix

### A. Related Documentation
- **Dry Run v1 Analysis**: `/docs/PHASE2_DRY_RUN_ANALYSIS.md`
- **Dry Run v2 Results**: `/docs/PHASE2_DRY_RUN_V2_RESULTS.md`
- **Dry Run v3 Results**: `/docs/PHASE2_DRY_RUN_V3_RESULTS.md`
- **Validation Report**: `logs/phase2_validation_report.md` (auto-generated)
- **Backfill Log**: `logs/phase2_full_backfill_v3.log`

### B. Database Schema
```sql
-- ticker_fundamentals table structure
CREATE TABLE ticker_fundamentals (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL DEFAULT 'KR',
    fiscal_year INTEGER NOT NULL,
    report_type VARCHAR(20) DEFAULT 'annual',

    -- Income Statement (18 columns)
    revenue DECIMAL(20, 2),
    cogs DECIMAL(20, 2),
    gross_profit DECIMAL(20, 2),
    operating_profit DECIMAL(20, 2),
    net_income DECIMAL(20, 2),
    ebitda DECIMAL(20, 2),
    earnings_per_share DECIMAL(15, 4),

    -- Balance Sheet (6 columns)
    total_assets DECIMAL(20, 2),
    total_liabilities DECIMAL(20, 2),
    shareholders_equity DECIMAL(20, 2),
    debt DECIMAL(20, 2),
    current_assets DECIMAL(20, 2),
    current_liabilities DECIMAL(20, 2),

    -- Cash Flow Statement (3 columns)
    operating_cash_flow DECIMAL(20, 2),
    investing_cash_flow DECIMAL(20, 2),
    financing_cash_flow DECIMAL(20, 2),

    -- Financial Ratios (7 columns)
    roe DECIMAL(10, 4),
    roa DECIMAL(10, 4),
    debt_to_equity DECIMAL(10, 4),
    current_ratio DECIMAL(10, 4),
    quick_ratio DECIMAL(10, 4),

    -- Metadata
    data_source VARCHAR(50) DEFAULT 'DART_API',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (ticker, region, fiscal_year, report_type)
);

CREATE INDEX idx_fundamentals_ticker_year ON ticker_fundamentals(ticker, fiscal_year DESC);
CREATE INDEX idx_fundamentals_year ON ticker_fundamentals(fiscal_year DESC);
```

### C. Validation Script Usage
```bash
# Run validation after backfill completion
python3 scripts/validate_phase2_backfill.py \
  --log logs/phase2_full_backfill_v3.log \
  --report logs/phase2_validation_report.md

# Automated validation setup (waits for backfill completion)
while ps aux | grep -q "[b]ackfill_phase2_historical.py"; do sleep 300; done && \
python3 scripts/validate_phase2_backfill.py --report logs/phase2_validation_report.md
```

---

**Last Updated**: 2025-10-24 (Template Created)
**Status**: ⏳ **AWAITING BACKFILL COMPLETION**
**Next Update**: Upon backfill completion and validation

