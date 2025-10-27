# Phase 2 Data Validation Guide

**Script**: `scripts/validate_phase2_data.py`
**Purpose**: Automated quality checks for Phase 2 fundamental data after backfill
**Version**: 1.0.0
**Date**: 2025-10-24

---

## Overview

The Phase 2 validation script performs comprehensive quality checks on fundamental data collected from DART API, ensuring mathematical consistency, data completeness, and industry-specific correctness.

---

## Validation Checks

### 1. Mathematical Consistency (🧮)

Verifies that calculated fields match expected formulas within 1% tolerance.

| Check | Formula | Tolerance |
|-------|---------|-----------|
| **Gross Profit** | Revenue - COGS | ±1% |
| **EBITDA** | Operating Profit + Depreciation | ±1% |
| **Operating Expense** | COGS + SG&A | ±1% |
| **EBITDA Margin** | (EBITDA / Revenue) × 100 | ±1% |

**Pass Criteria**: ≥95% of records pass each check

**Example**:
```
Revenue:          258,935,494,000,000 won
COGS:             180,388,580,000,000 won
Gross Profit:      78,546,914,000,000 won
Expected GP:       78,546,914,000,000 won (Revenue - COGS)
Difference:                         0 won (0.00%) ✅ PASS
```

---

### 2. Data Completeness (📋)

Measures field availability across all records.

| Field Group | Fields | Target Completeness |
|-------------|--------|-------------------|
| **Core** | revenue, operating_profit, net_income | ≥95% |
| **Manufacturing** | cogs, pp_e, accounts_receivable | ≥85% |
| **Retail** | sga_expense | ≥85% |
| **Financial** | interest_income, interest_expense | ≥85% |
| **Cash Flow** | investing_cf, financing_cf | ≥95% |
| **Calculated** | gross_profit, ebitda, ebitda_margin | ≥85% |

**Pass Criteria**: ≥85% completeness for core fields

**Example Output**:
```
📋 Check 2: Data Completeness
--------------------------------------------------------------------------------
  ✅ revenue: 450/500 (90.0%)
  ✅ cogs: 425/500 (85.0%)
  ✅ gross_profit: 420/500 (84.0%)
  ✅ depreciation: 380/500 (76.0%)
  ⚠️ rd_expense: 120/500 (24.0%)  # Expected - rarely disclosed
```

---

### 3. Data Quality (🔍)

Identifies anomalies and validates estimation algorithms.

| Quality Check | Threshold | Action |
|---------------|-----------|--------|
| **Negative Gross Profit** | <5% of records | Flag as anomaly |
| **Unreasonable EBITDA Margin** | Outside -50% to 100% | Flag as anomaly |
| **Depreciation Estimation** | ≥75% success rate | Validate algorithm |
| **NULL vs 0 Handling** | ≥90% correct | Check industry logic |

**Pass Criteria**: <5% anomaly rate

**Anomaly Example**:
```json
{
  "ticker": "123456",
  "year": 2023,
  "check": "negative_gross_profit",
  "value": -5000000000,
  "note": "Possible data error or special circumstances"
}
```

---

### 4. Industry-Specific Validation (🏭)

Verifies that industry-specific fields are correctly populated.

#### Manufacturing Companies
- ✅ COGS > 0
- ✅ PP&E > 0
- ✅ Depreciation estimated
- ❌ Loan Portfolio = NULL

#### Financial Companies
- ✅ Loan Portfolio > 0
- ✅ NIM calculated
- ✅ Interest Income/Expense > 0
- ❌ COGS = NULL or 0

#### All Companies
- ✅ Investing CF populated
- ✅ Financing CF populated
- ✅ Revenue > 0

**Pass Criteria**: ≥85% field availability per industry

---

## Usage Examples

### Basic Validation (All Data)
```bash
python3 scripts/validate_phase2_data.py
```

**Output**:
```
================================================================================
🔍 Phase 2 Data Validation
================================================================================
✅ Loaded 1,523 records for validation

📊 Running validation checks...
================================================================================

🧮 Check 1: Mathematical Consistency
--------------------------------------------------------------------------------
  ✅ gross_profit: 1,420/1,450 passed (97.9%)
  ✅ ebitda: 1,380/1,450 passed (95.2%)
  ✅ operating_expense: 1,440/1,450 passed (99.3%)
  ✅ ebitda_margin: 1,385/1,450 passed (95.5%)

📋 Check 2: Data Completeness
--------------------------------------------------------------------------------
  ✅ revenue: 1,523/1,523 (100.0%)
  ✅ cogs: 1,420/1,523 (93.2%)
  ✅ gross_profit: 1,415/1,523 (92.9%)
  ...

🔍 Check 3: Data Quality
--------------------------------------------------------------------------------
  Negative Gross Profit: 12 (0.8%)
  Unreasonable EBITDA Margin: 8 (0.5%)
  Depreciation Estimated: 1,380/1,523 (90.6%)
  NULL Handling Correct: 1,450/1,523 (95.2%)

🏭 Check 4: Industry-Specific Validation
--------------------------------------------------------------------------------
  Manufacturing Companies: 1,250
    - COGS populated: 1,200/1,250 (96.0%)
    - PP&E populated: 1,180/1,250 (94.4%)
  Financial Companies: 85
    - Loan Portfolio populated: 82/85 (96.5%)
    - NIM populated: 80/85 (94.1%)
  All Companies: 1,523
    - Cash Flows populated: 1,500/1,523 (98.5%)

================================================================================
📊 Validation Summary
================================================================================
Total Records: 1,523
Total Checks: 5,800
Pass Rate: 96.3%
Anomalies: 20

✅ Validation PASSED - Data quality is excellent
================================================================================
```

---

### Validate Specific Year Range
```bash
python3 scripts/validate_phase2_data.py --start-year 2022 --end-year 2024
```

---

### Validate Specific Tickers
```bash
# Single ticker
python3 scripts/validate_phase2_data.py --tickers 005930

# Multiple tickers
python3 scripts/validate_phase2_data.py --tickers 005930,000660,105560
```

---

### Verbose Mode (Detailed Anomaly Logging)
```bash
python3 scripts/validate_phase2_data.py --verbose
```

**Verbose Output Example**:
```
  ⚠️ [123456] 2023: Gross Profit mismatch (5.2%)
  ⚠️ [234567] 2023: EBITDA mismatch (2.8%)
  ⚠️ [345678] 2022: Negative gross profit (-5,000,000,000)
  ⚠️ [456789] 2023: Unreasonable EBITDA margin (120.5%)
```

---

### Generate JSON Report
```bash
python3 scripts/validate_phase2_data.py \
  --verbose \
  --output reports/phase2_validation_$(date +%Y%m%d).json
```

**Report Structure**:
```json
{
  "total_records": 1523,
  "passed_records": 5586,
  "failed_records": 214,
  "warnings": 20,
  "checks": {
    "mathematical_consistency": {
      "gross_profit": {"passed": 1420, "failed": 30, "na": 73},
      "ebitda": {"passed": 1380, "failed": 70, "na": 73},
      ...
    },
    "data_completeness": {
      "revenue": {"total": 1523, "populated": 1523, "rate": 100.0},
      "cogs": {"total": 1523, "populated": 1420, "rate": 93.2},
      ...
    },
    "data_quality": {
      "negative_gross_profit": 12,
      "unreasonable_ebitda_margin": 8,
      "depreciation_estimated": 1380,
      "null_vs_zero_correct": 1450
    },
    "industry_specific": {
      "manufacturing": {"count": 1250, "cogs_populated": 1200, "ppe_populated": 1180},
      "financial": {"count": 85, "loan_populated": 82, "nim_populated": 80},
      "all": {"count": 1523, "cf_populated": 1500}
    }
  },
  "anomalies": [
    {
      "ticker": "123456",
      "year": 2023,
      "check": "gross_profit",
      "expected": 78546914000000,
      "actual": 74500000000000,
      "diff_percent": 5.2
    },
    ...
  ],
  "summary": {
    "total_records": 1523,
    "total_checks": 5800,
    "pass_rate": 96.3,
    "anomaly_count": 20
  }
}
```

---

## Integration with Backfill Workflow

### Recommended Workflow

1. **Dry Run** (10 stocks)
```bash
# Step 1: Backfill dry run
python3 scripts/backfill_phase2_historical.py \
  --start-year 2022 --end-year 2024 \
  --tickers 005930,000660,105560,035420,035720 \
  --dry-run

# Step 2: Validate dry run data
python3 scripts/validate_phase2_data.py \
  --tickers 005930,000660,105560,035420,035720 \
  --verbose
```

2. **Full Backfill** (all stocks)
```bash
# Step 1: Run full backfill
python3 scripts/backfill_phase2_historical.py \
  --start-year 2022 --end-year 2024 \
  --checkpoint-file data/phase2_checkpoint.json

# Step 2: Validate all data
python3 scripts/validate_phase2_data.py \
  --start-year 2022 --end-year 2024 \
  --output reports/phase2_validation_full.json
```

3. **Incremental Updates**
```bash
# Step 1: Update recent data
python3 scripts/backfill_fundamentals_dart.py --region KR

# Step 2: Validate recent year only
python3 scripts/validate_phase2_data.py --start-year 2024 --end-year 2024
```

---

## Interpreting Results

### Pass Rate Thresholds

| Pass Rate | Status | Action |
|-----------|--------|--------|
| **≥95%** | ✅ Excellent | Proceed to production |
| **85-95%** | ⚠️ Good | Review anomalies, acceptable for use |
| **70-85%** | ⚠️ Fair | Investigate issues, limited use |
| **<70%** | ❌ Poor | Do not use, fix data collection |

### Common Anomalies

#### 1. Negative Gross Profit
**Cause**:
- Data error (incorrect COGS or Revenue)
- Special industry (trading companies with net revenue reporting)

**Action**:
- Verify DART API response for affected companies
- Check if company uses net revenue vs gross revenue

#### 2. EBITDA Mismatch
**Cause**:
- Depreciation estimation error
- Operating profit classification differences

**Action**:
- Review depreciation estimation formula
- Compare with manual calculation from cash flow statement

#### 3. Low Depreciation Estimation Rate
**Cause**:
- Missing cash flow data
- Working capital change data unavailable

**Action**:
- Check DART API response completeness
- Consider using industry-average depreciation rates as fallback

#### 4. NULL Handling Errors
**Cause**:
- Industry classification error
- Field availability mismatch

**Action**:
- Verify industry classification logic
- Check DART API account names for variations

---

## Troubleshooting

### Issue: All Checks Fail
**Symptom**: Pass rate <10%

**Diagnosis**:
```bash
# Check if data exists
psql -d quant_platform -c "SELECT COUNT(*) FROM ticker_fundamentals WHERE fiscal_year >= 2022;"
```

**Solution**: Re-run backfill script

---

### Issue: Low Completeness for Core Fields
**Symptom**: Revenue <85% populated

**Diagnosis**:
```bash
# Check specific records
psql -d quant_platform -c "
SELECT ticker, fiscal_year, revenue, cogs, operating_profit
FROM ticker_fundamentals
WHERE revenue IS NULL OR revenue = 0
LIMIT 10;"
```

**Solution**: Investigate DART API response parsing

---

### Issue: High Anomaly Count
**Symptom**: >5% anomalies

**Diagnosis**:
```bash
# Generate verbose report
python3 scripts/validate_phase2_data.py --verbose --output reports/anomalies.json

# Review specific anomalies
cat reports/anomalies.json | jq '.anomalies[] | select(.check == "gross_profit")'
```

**Solution**: Manual review of flagged companies

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| **0** | Validation passed (≥85% pass rate) | Proceed |
| **1** | Validation failed (<85% pass rate) | Fix issues |

**Usage in Scripts**:
```bash
if python3 scripts/validate_phase2_data.py; then
    echo "✅ Validation passed - proceeding to next step"
    python3 scripts/run_backtest.py
else
    echo "❌ Validation failed - aborting"
    exit 1
fi
```

---

## Performance

- **Processing Speed**: ~1,000 records/second
- **Memory Usage**: ~500MB for 10,000 records
- **Typical Runtime**:
  - 10 stocks, 3 years: <1 second
  - 100 stocks, 3 years: ~3 seconds
  - 2,000 stocks, 3 years: ~60 seconds

---

## Best Practices

1. **Always validate after backfill**: Catch data issues early
2. **Use verbose mode for dry runs**: Identify specific problems
3. **Save reports for production runs**: Audit trail and trend analysis
4. **Review anomalies manually**: Some "anomalies" may be valid (e.g., trading companies)
5. **Set up automated validation**: Integrate into CI/CD pipeline

---

## Related Documentation

- `docs/DART_ACCOUNT_NAME_MAPPING.md` - Account name reference
- `docs/PHASE2_COMPLETION_SUMMARY.md` - Phase 2 overview
- `docs/DATABASE_SCHEMA.md` - Database schema details

---

**Last Updated**: 2025-10-24
**Version**: 1.0.0
**Maintained By**: Quant Investment Platform Team
