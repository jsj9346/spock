# Phase 2 Orchestration Plan: DART Annual Data Backfill

**Date**: 2025-11-02
**Duration**: 1 week (5 working days)
**Priority**: CRITICAL - Unblocks fundamental screening
**Status**: 📋 PLANNED

---

## Executive Summary

Phase 2 fixes the fundamental screening data quality issue identified in Phase 1. The current database contains 99.8% DAILY data and 0% ANNUAL data, making fundamental screening unusable. This phase will:

1. Modify DART backfill script to collect ANNUAL financial statements
2. Backfill 2022-2024 fiscal_year data (~6,000 records)
3. Enable screening of 30-50 stocks in flexible mode, 5-10 in strict mode
4. Fix ROE calculations (currently 1.28% due to SEMI-ANNUAL data)

---

## Problem Statement

### Current State (Phase 1 Results)
```
Database Status:
- ANNUAL data:       0 records  ← Problem!
- SEMI-ANNUAL data: 90 records (inaccurate ROE: 1.28%)
- DAILY data:   44,361 records (not useful for fundamental screening)

Screening Results:
- Flexible mode:  0 stocks pass (ROE too low)
- Strict mode:    0 stocks pass (no YOY data)
```

### Target State (Phase 2 Goals)
```
Database Status:
- ANNUAL 2024: ~2,000 records ✅
- ANNUAL 2023: ~2,000 records ✅
- ANNUAL 2022: ~2,000 records ✅

Screening Results:
- Flexible mode: 30-50 stocks pass ✅
- Strict mode:    5-10 stocks pass ✅
- ROE accuracy:  10-15% (not 1.28%) ✅
```

---

## Task Breakdown & Dependencies

### Day 1-2: DART API Research & Script Modification (16 hours)

#### Task 1: Research DART API for Annual Financial Statements (3 hours)
**Objective**: Understand DART API endpoints for annual financial data

**Activities**:
1. Review DART Open API documentation
2. Identify endpoint for annual financial statements (연결재무제표)
3. Understand fiscal_year vs calendar_year mapping
4. Test API responses with sample requests
5. Document API rate limits and error handling

**Deliverables**:
- API endpoint documentation
- Sample API response JSON
- Rate limit analysis (requests/second, daily quota)

**Validation**: Successfully retrieve 2024 annual data for Samsung (005930)

---

#### Task 2: Analyze Current backfill_fundamentals_dart.py (2 hours)
**Objective**: Understand existing implementation and identify modification points

**Key Files**:
- `/Users/13ruce/spock/scripts/backfill_fundamentals_dart.py`
- `/Users/13ruce/spock/modules/dart_api_client.py`

**Analysis Points**:
1. How does script currently collect DAILY data?
2. Where is period_type determined?
3. How is fiscal_year extracted (currently NULL or SEMI-ANNUAL)?
4. Database insert logic - what needs to change?
5. Error handling and retry logic

**Deliverables**:
- Code flow diagram
- List of required modifications
- Impact assessment (schema changes needed?)

**Validation**: Clear understanding of modification scope

---

#### Task 3: Design Modifications for ANNUAL Data Collection (2 hours)
**Objective**: Plan code changes before implementation

**Design Decisions**:
1. **API Endpoint Change**:
   - Current: Daily stock info API
   - Target: Annual financial statements API

2. **Data Mapping**:
   - Map DART fiscal_year to database fiscal_year column
   - Ensure period_type = 'ANNUAL' (not 'DAILY')
   - Handle consolidated vs separate financial statements

3. **Data Quality**:
   - Validate ROE calculation with ANNUAL data
   - Ensure YOY growth is calculable (2024 vs 2023)
   - Handle missing data gracefully

4. **Schema Changes** (if needed):
   - Add indexes on fiscal_year?
   - Add constraints for ANNUAL data validation?

**Deliverables**:
- Modification specification document
- SQL schema changes (if any)
- Test plan

**Validation**: Design review - no coding yet

---

#### Task 4: Modify Script to Collect ANNUAL Data (4 hours)
**Objective**: Implement code changes to collect annual financial statements

**Code Changes**:
1. Update API endpoint call
2. Change period_type from 'DAILY' → 'ANNUAL'
3. Extract fiscal_year from API response
4. Map DART fields to database columns
5. Add validation for annual data integrity

**Files to Modify**:
- `scripts/backfill_fundamentals_dart.py` (primary changes)
- `modules/dart_api_client.py` (if endpoint changes needed)

**Example Code Pattern**:
```python
# Before (DAILY)
period_type = 'DAILY'
fiscal_year = None

# After (ANNUAL)
period_type = 'ANNUAL'
fiscal_year = extract_fiscal_year(dart_response)  # 2024, 2023, 2022
```

**Deliverables**:
- Modified backfill script
- Updated API client (if needed)
- Code comments explaining changes

**Validation**: Code compiles, no syntax errors

---

#### Task 5: Add Fiscal_Year Extraction & Validation Logic (3 hours)
**Objective**: Ensure fiscal_year is correctly extracted and validated

**Implementation**:
1. Parse fiscal_year from DART API response
2. Validate fiscal_year range (2020-2025 reasonable)
3. Handle edge cases (missing fiscal_year, invalid formats)
4. Add logging for fiscal_year extraction

**Validation Logic**:
```python
def validate_fiscal_year(fiscal_year: int) -> bool:
    """Validate fiscal_year is reasonable"""
    current_year = datetime.now().year
    return 2020 <= fiscal_year <= current_year + 1
```

**Deliverables**:
- Fiscal_year extraction function
- Validation logic
- Unit tests for edge cases

**Validation**: Unit tests pass for various fiscal_year formats

---

#### Task 6: Unit Test Modified Script with Dry-Run (2 hours)
**Objective**: Test script changes without database writes

**Test Scenarios**:
1. Dry-run for Samsung (005930) - 2024 data
2. Validate extracted fiscal_year = 2024
3. Validate period_type = 'ANNUAL'
4. Check ROE calculation accuracy (expect 10-15%, not 1.28%)
5. Test error handling (missing data, API failures)

**Dry-Run Command**:
```bash
python3 scripts/backfill_fundamentals_dart.py --dry-run --tickers 005930 --year 2024
```

**Expected Output**:
```
Ticker: 005930 (Samsung Electronics)
Fiscal Year: 2024
Period Type: ANNUAL
ROE: 12.34%  (not 1.28%)
Debt/Equity: 26.36%
Net Income: 30.5T KRW (annual)
Revenue: 258.9T KRW (annual)
```

**Deliverables**:
- Dry-run test results
- Validation report
- Bug fixes (if any)

**Validation Checkpoint**: Dry-run shows correct ANNUAL data with accurate ROE

---

### Day 3: Initial Data Backfill (8 hours)

#### Task 7: Test Backfill for 1-2 Sample Tickers (1 hour)
**Objective**: Validate end-to-end backfill with database writes

**Test Tickers**:
- 005930 (Samsung Electronics)
- 000660 (SK Hynix)

**Test Command**:
```bash
python3 scripts/backfill_fundamentals_dart.py --tickers 005930,000660 --year 2024
```

**Database Validation**:
```sql
SELECT ticker, fiscal_year, period_type,
       net_income, total_equity,
       (net_income / total_equity * 100) as roe
FROM ticker_fundamentals
WHERE ticker IN ('005930', '000660')
  AND fiscal_year = 2024
  AND period_type = 'ANNUAL'
ORDER BY ticker;
```

**Deliverables**:
- 2 records inserted into database
- Validation query results

**Validation Checkpoint**: Database contains correct ANNUAL records

---

#### Task 8: Validate ROE Accuracy (1 hour)
**Objective**: Confirm ROE calculation is accurate with ANNUAL data

**Test**:
1. Query Samsung 2024 ANNUAL data
2. Manual ROE calculation: (net_income / total_equity) * 100
3. Compare with expected ROE: 10-15% range
4. Verify against public financial reports

**Expected Result**:
```
Samsung Electronics (005930):
- Fiscal Year: 2024
- Net Income: ~30T KRW (annual)
- Total Equity: ~400T KRW
- ROE: ~7.5% (2024 was a tough year for Samsung)
- NOT 1.28% (which was from SEMI-ANNUAL data)
```

**Deliverables**:
- ROE validation report
- Comparison with public data

**Validation Checkpoint**: ROE is realistic, not 1.28%

---

#### Task 9: Full Backfill 2024 Fiscal_Year (~2,000 stocks) (4 hours)
**Objective**: Backfill all listed companies with 2024 annual data

**Execution Strategy**:
1. Get list of all KR tickers from database
2. Batch processing (100 tickers at a time)
3. Rate limiting (1 request/second to avoid API blocks)
4. Error handling and retry logic

**Backfill Command**:
```bash
python3 scripts/backfill_fundamentals_dart.py \
  --region KR \
  --year 2024 \
  --batch-size 100 \
  --rate-limit 1.0
```

**Expected Duration**: 2-4 hours (2,000 tickers × 1 sec/ticker = 33 minutes minimum)

**Deliverables**:
- ~2,000 ANNUAL records for 2024
- Backfill log file
- Error summary

**Validation Checkpoint**: >90% success rate for backfill

---

#### Task 10: Monitor Backfill Progress & Handle Errors (2 hours)
**Objective**: Ensure backfill completes successfully

**Monitoring**:
1. Track progress (records inserted / total tickers)
2. Log API errors (rate limits, missing data, server errors)
3. Retry failed tickers
4. Validate data integrity (no duplicate records)

**Error Handling**:
- API rate limit → Increase delay
- Missing data → Log ticker, skip
- Server error → Retry with exponential backoff

**SQL Validation**:
```sql
-- Check backfill progress
SELECT
    COUNT(*) as total_records,
    COUNT(DISTINCT ticker) as unique_tickers
FROM ticker_fundamentals
WHERE fiscal_year = 2024
  AND period_type = 'ANNUAL'
  AND region = 'KR';

-- Expected: ~2,000 records
```

**Deliverables**:
- Backfill completion report
- Error log analysis
- Retry results

**Validation Checkpoint**: 2024 backfill complete with >90% coverage

---

### Day 4: Historical Backfill & Validation (8 hours)

#### Task 11: Backfill 2023 Fiscal_Year Data (2 hours)
**Objective**: Collect 2023 annual data for YOY growth calculations

**Process**: Same as Task 9 but for 2023

**Command**:
```bash
python3 scripts/backfill_fundamentals_dart.py \
  --region KR \
  --year 2023 \
  --batch-size 100 \
  --rate-limit 1.0
```

**Deliverables**:
- ~2,000 ANNUAL records for 2023

**Validation Checkpoint**: 2023 backfill complete

---

#### Task 12: Backfill 2022 Fiscal_Year Data (2 hours)
**Objective**: Collect 2022 annual data for multi-year trend analysis

**Process**: Same as Task 9 but for 2022

**Command**:
```bash
python3 scripts/backfill_fundamentals_dart.py \
  --region KR \
  --year 2022 \
  --batch-size 100 \
  --rate-limit 1.0
```

**Deliverables**:
- ~2,000 ANNUAL records for 2022

**Validation Checkpoint**: 2022 backfill complete

---

#### Task 13: Validate YOY Growth Calculations (2 hours)
**Objective**: Ensure YOY growth is correctly calculated

**Test**:
```sql
WITH growth_calc AS (
    SELECT
        current.ticker,
        current.net_income as ni_2024,
        previous.net_income as ni_2023,
        ((current.net_income - previous.net_income) / ABS(previous.net_income) * 100) as ni_yoy_growth
    FROM ticker_fundamentals current
    JOIN ticker_fundamentals previous
        ON current.ticker = previous.ticker
        AND current.region = previous.region
        AND current.fiscal_year = previous.fiscal_year + 1
    WHERE current.ticker = '005930'
      AND current.fiscal_year = 2024
      AND current.period_type = 'ANNUAL'
      AND previous.period_type = 'ANNUAL'
)
SELECT * FROM growth_calc;
```

**Expected Result**:
- Samsung YOY net income growth: ~-30% to +30% (realistic range)
- NOT NULL (which was the Phase 1 problem)

**Deliverables**:
- YOY growth validation report
- Sample calculations for 10 tickers

**Validation Checkpoint**: YOY growth is calculable and realistic

---

#### Task 14: Check for Data Anomalies & Missing Records (2 hours)
**Objective**: Data quality assurance

**Checks**:
1. **Missing fiscal_year records**:
   ```sql
   -- Tickers with 2024 but missing 2023 (can't calculate YOY)
   SELECT ticker
   FROM ticker_fundamentals
   WHERE fiscal_year = 2024 AND period_type = 'ANNUAL'
     AND ticker NOT IN (
         SELECT ticker FROM ticker_fundamentals
         WHERE fiscal_year = 2023 AND period_type = 'ANNUAL'
     );
   ```

2. **Outlier detection** (ROE > 100% or < -50%):
   ```sql
   SELECT ticker, fiscal_year,
          (net_income / total_equity * 100) as roe
   FROM ticker_fundamentals
   WHERE fiscal_year >= 2022
     AND period_type = 'ANNUAL'
     AND (net_income / total_equity * 100) > 100
        OR (net_income / total_equity * 100) < -50;
   ```

3. **Duplicate records**:
   ```sql
   SELECT ticker, fiscal_year, COUNT(*)
   FROM ticker_fundamentals
   WHERE period_type = 'ANNUAL'
   GROUP BY ticker, fiscal_year
   HAVING COUNT(*) > 1;
   ```

**Deliverables**:
- Data quality report
- Anomaly list with explanations
- Remediation plan (if needed)

**Validation Checkpoint**: Data quality >95%, anomalies explained

---

### Day 5: Integration Testing & Documentation (8 hours)

#### Task 15: Run Integration Test with ANNUAL Data (2 hours)
**Objective**: Test fundamental screening with real ANNUAL data

**Test Script**: Use existing `test_fundamental_screening_modes.py`

**Command**:
```bash
python3 tests/integration/test_fundamental_screening_modes.py
```

**Expected Results**:
```
Flexible Mode (require_growth=False):
  ✅ Passed: 30-50 stocks
  Criteria: ROE ≥ 15%, Debt/Equity ≤ 100%

Strict Mode (require_growth=True):
  ✅ Passed: 5-10 stocks
  Criteria: ROE ≥ 15%, Debt ≤ 100%, NI Growth ≥ 10%, Revenue Growth ≥ 10%
```

**Deliverables**:
- Integration test results
- List of stocks passing flexible mode
- List of stocks passing strict mode

**Validation Checkpoint**: Screening works with expected results

---

#### Task 16: Validate Screening Results (2 hours)
**Objective**: Manual validation of screening results

**Validation Process**:
1. Review top 10 stocks from flexible mode screening
2. Manually verify ROE and Debt/Equity for 3 stocks
3. Check against public financial reports
4. Ensure no obvious errors (e.g., delisted stocks, data errors)

**Sample Validation**:
```sql
-- Top 10 stocks in flexible mode
SELECT
    ticker,
    (net_income / total_equity * 100) as roe,
    (total_liabilities / total_equity * 100) as debt_to_equity
FROM ticker_fundamentals
WHERE fiscal_year = 2024
  AND period_type = 'ANNUAL'
  AND (net_income / total_equity * 100) >= 15.0
  AND (total_liabilities / total_equity * 100) <= 100.0
ORDER BY (net_income / total_equity * 100) DESC
LIMIT 10;
```

**Deliverables**:
- Validation report
- Stock screening results
- Public data comparison

**Validation Checkpoint**: Screening results are accurate

---

#### Task 17: Update Database Schema Documentation (2 hours)
**Objective**: Document ANNUAL data in schema

**Files to Update**:
- `docs/QUANT_DATABASE_SCHEMA.md`

**Updates**:
1. Add ticker_fundamentals table documentation
2. Document fiscal_year column and ANNUAL period_type
3. Add example queries for fundamental screening
4. Update storage estimates (now includes ~6,000 ANNUAL records)

**Example Documentation**:
```markdown
### ticker_fundamentals Table

Stores fundamental financial data for stocks.

**Schema**:
```sql
CREATE TABLE ticker_fundamentals (
    ticker VARCHAR(20),
    region VARCHAR(2),
    fiscal_year INTEGER,  -- 2024, 2023, 2022, ...
    period_type VARCHAR(20),  -- 'ANNUAL', 'QUARTERLY', 'SEMI-ANNUAL', 'DAILY'
    net_income DECIMAL(20, 2),
    total_equity DECIMAL(20, 2),
    ...
);
```

**Data Availability**:
- ANNUAL: 2022-2024 (3 years, ~6,000 records)
- DAILY: 2024-2025 (~44,000 records)
```

**Deliverables**:
- Updated QUANT_DATABASE_SCHEMA.md
- Example queries

**Validation Checkpoint**: Documentation is accurate and complete

---

#### Task 18: Create Phase 2 Completion Report (2 hours)
**Objective**: Document Phase 2 achievements and outcomes

**Report Structure**:
1. Executive Summary
2. Implementation Completed
3. Database Analysis (before/after)
4. Screening Results (30-50 flexible, 5-10 strict)
5. Data Quality Validation
6. Next Steps (Phase 3-5)

**File**: `docs/PHASE2_DART_ANNUAL_BACKFILL_COMPLETION.md`

**Deliverables**:
- Completion report
- Performance metrics
- Lessons learned

**Validation Checkpoint**: Phase 2 complete and documented

---

## Dependencies & Critical Path

```
Day 1-2: Sequential Flow
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6

Day 3: Sequential with Validation
Task 7 (validate) → Task 8 (validate) → Task 9 (backfill) → Task 10 (monitor)

Day 4: Parallel Backfill, Sequential Validation
Tasks 11-12 (can run in parallel if 2023/2022 backfills are independent)
Task 13 (depends on 11-12 complete)
Task 14 (depends on 11-13 complete)

Day 5: Parallel Documentation
Tasks 15-16 (sequential - test then validate)
Tasks 17-18 (can run in parallel with 15-16)
```

**Critical Path**: Task 1 → Task 6 → Task 9 → Task 13 → Task 15 → Task 18

---

## Risk Management

### High Risk Items
1. **DART API Rate Limits**: May slow down backfill
   - Mitigation: Implement exponential backoff and rate limiting
   - Contingency: Run overnight if needed

2. **Data Quality Issues**: ANNUAL data may have gaps
   - Mitigation: Validate on sample before full backfill
   - Contingency: Fall back to SEMI-ANNUAL for missing tickers

3. **ROE Still Inaccurate**: ANNUAL data may not fix ROE calculation
   - Mitigation: Validate ROE on Day 3 Task 8 before full backfill
   - Contingency: Adjust ROE threshold if needed

### Medium Risk Items
1. **Schema Changes Needed**: May require database migration
   - Mitigation: Design review on Task 3
   - Contingency: Add indexes without downtime

2. **Backfill Duration**: May take longer than 4 hours per year
   - Mitigation: Optimize batch processing
   - Contingency: Run overnight or weekend

---

## Success Criteria

### Phase 2 Complete When:
1. ✅ ~6,000 ANNUAL records in database (2022-2024)
2. ✅ ROE accuracy validated (10-15% range, not 1.28%)
3. ✅ YOY growth calculations working (2024 vs 2023)
4. ✅ Flexible mode screening: 30-50 stocks pass
5. ✅ Strict mode screening: 5-10 stocks pass
6. ✅ Integration tests pass
7. ✅ Documentation updated
8. ✅ Completion report published

---

## Resource Estimates

### Time Allocation
- Day 1-2 (Research & Modification): 16 hours
- Day 3 (Initial Backfill): 8 hours
- Day 4 (Historical Backfill): 8 hours
- Day 5 (Testing & Docs): 8 hours
- **Total**: 40 hours (1 week)

### Computational Resources
- DART API calls: ~6,000 requests (3 years × 2,000 tickers)
- Rate limit: 1 request/second = ~1.7 hours minimum
- Database inserts: ~6,000 records = negligible
- Disk space: ~10 MB for ANNUAL data

---

## Next Steps After Phase 2

**Phase 3: Multi-Factor Library Expansion** (1 week)
- Implement 29 fundamental factors (Value, Momentum, Quality, Low-Vol, Size)
- Create factor scoring system
- Build factor combination strategies

**Phase 4: Multi-Source Integration** (1 week)
- Add FinanceDataReader for KR market data
- Add yfinance for US market data
- Implement data quality reconciliation

**Phase 5: Advanced Screening & Discovery** (1 week)
- Multi-factor screening UI
- Factor correlation analysis
- Portfolio construction tools

---

**Report Generated**: 2025-11-02
**Author**: Spock Development Team
**Status**: Phase 2 PLANNED 📋 | Ready for Execution ✅
