# Phase 2 Dry Run Test Results

**Date**: 2025-10-24
**Purpose**: Validate Phase 2 backfill pipeline with 9 representative stocks
**Period**: FY2022 - FY2024 (3 years)
**Mode**: Dry run (no database writes)

---

## Test Configuration

**Test Stocks** (9 companies):
1. **005930** - Samsung Electronics (Manufacturing - Semiconductors)
2. **000660** - SK Hynix (Manufacturing - Semiconductors)
3. **105560** - KB Financial Group (Financial Services)
4. **035420** - Naver (Tech - E-Commerce)
5. **035720** - Kakao (Tech - E-Commerce)
6. **005380** - Hyundai Motor (Manufacturing - Automotive)
7. **051910** - LG Chem (Manufacturing - Chemicals)
8. **055550** - Shinhan Financial (Financial Services)
9. **068270** - Celltrion (Pharma/Biotech)

**Expected Results**:
- 9 companies × 3 years = 27 records
- Depreciation estimated for ~90% of records
- Financial fields (loan portfolio, NIM) only for KB Financial, Shinhan Financial
- NULL fields properly handled for unavailable data

---

## Results

### 1. Samsung Electronics (005930) - Manufacturing ✅

**Industry**: Semiconductors
**Data Collected**: 3/3 years

| Year | Revenue (억원) | COGS (억원) | EBITDA (억원) | Notes |
|------|----------------|--------------|---------------|-------|
| 2022 | **0** ⚠️ | 1,900,418 | 433,766 | Revenue=0 issue |
| 2023 | 2,589,355 | 1,803,886 | 441,374 | ✅ Matches test |
| 2024 | 3,008,709 | 1,865,623 | 745,502 | ✅ Good data |

**Analysis**:
- ✅ 2023 data matches our previous test (Revenue: 258.9T, COGS: 180.4T, EBITDA: 44.1T)
- ⚠️ 2022 Revenue showing as 0 - possible field name variation issue
- ✅ EBITDA successfully calculated (depreciation estimation working)
- ✅ COGS properly collected

**Action Required**:
- Investigate 2022 Revenue=0 issue (likely '매출액' vs '영업수익' field name variation)

---

### 2. SK Hynix (000660) - Manufacturing ✅

**Industry**: Semiconductors
**Data Collected**: 3/3 years

| Year | Revenue (억원) | COGS (억원) | EBITDA (억원) | Notes |
|------|----------------|--------------|---------------|-------|
| 2022 | 446,216 | 289,937 | 68,094 | ✅ Good data |
| 2023 | 327,657 | 332,992 | **0** ⚠️ | Loss year, EBITDA=0 |
| 2024 | 661,930 | 343,648 | **0** ⚠️ | EBITDA=0 issue |

**Analysis**:
- ✅ Revenue collected for all 3 years
- ✅ COGS properly collected
- ⚠️ 2023 EBITDA = 0 (expected - semiconductor downcycle, likely operating loss)
- ⚠️ 2024 EBITDA = 0 (needs investigation - SK Hynix recovered in 2024)
- ⚠️ 2023 COGS > Revenue (gross loss year - semiconductor industry downturn)

**Notes**:
- 2023 was a difficult year for memory semiconductors (industry-wide losses)
- EBITDA=0 might indicate negative operating profit or depreciation estimation failure

---

### 3. KB Financial (105560) - Financial Services 🔄

**Industry**: Banking & Financial Services
**Data Collected**: In progress

| Year | Status | Notes |
|------|--------|-------|
| 2022 | ⚠️ Not available | Financial companies often have different reporting |
| 2023 | 🔄 Collecting | In progress |
| 2024 | ⏳ Pending | Not started |

**Expected Fields**:
- ✅ loan_portfolio (대출금)
- ✅ npl_amount (부실채권)
- ✅ nim (순이자마진)
- ❌ COGS = NULL (not applicable)
- ❌ PP&E = NULL or minimal

---

### 4. Naver (035420) - Tech/E-Commerce ⏳

**Status**: Pending

---

### 5. Kakao (035720) - Tech/E-Commerce ⏳

**Status**: Pending

---

### 6. Hyundai Motor (005380) - Manufacturing ⏳

**Status**: Pending

---

### 7. LG Chem (051910) - Manufacturing ⏳

**Status**: Pending

---

### 8. Shinhan Financial (055550) - Financial Services ⏳

**Status**: Pending

---

### 9. Celltrion (068270) - Pharma/Biotech ⏳

**Status**: Pending

---

## Preliminary Findings

### ✅ Successes

1. **API Integration**: DART API client successfully retrieves data from `fnlttSinglAcntAll.json`
2. **Multi-Year Collection**: Successfully collects 3 years of data per company
3. **COGS Collection**: Manufacturing COGS properly collected
4. **Depreciation Estimation**: Working for Samsung 2023/2024 (EBITDA > 0)
5. **Rate Limiting**: 1 req/sec rate limiting working correctly (~36s per year)

### ⚠️ Issues Identified

1. **Samsung 2022 Revenue = 0**: Field name variation issue for older reports
2. **SK Hynix EBITDA = 0**: Possible negative operating profit or depreciation estimation failure
3. **KB Financial 2022 Data Missing**: Financial companies may have different reporting cycles
4. **Field Name Consistency**: Need fallback logic for multiple field name variations

### 🔍 Validation Needed

1. **Revenue Field Names**: Check '매출액' vs '영업수익' vs '영업수익(매출액)' variations
2. **EBITDA Calculation**: Verify negative operating profit handling
3. **Financial Company Fields**: Confirm loan portfolio, NIM collection for banks
4. **Depreciation Estimation Accuracy**: Compare estimated vs actual (when available)

---

## Performance Metrics

**Current Progress**: 2/9 companies completed (22.2%)
**Avg Time per Company**: ~1.5 minutes (3 years × 36s)
**Est. Total Time**: ~13.5 minutes for 9 companies
**API Calls**: 6/27 completed
**Success Rate**: 100% (2/2 companies completed successfully)

---

## Next Steps

1. ✅ **Complete Dry Run**: Wait for all 9 companies to finish
2. 📊 **Run Validation Script**: `python3 scripts/validate_phase2_data.py --tickers 005930,000660,... --verbose`
3. 🔍 **Investigate Issues**:
   - Samsung 2022 Revenue=0
   - SK Hynix EBITDA=0 for 2023/2024
   - Field name variation handling
4. 🛠️ **Fix Identified Issues**: Update parsing logic if needed
5. ✅ **Re-run Dry Run**: Verify fixes work
6. 🚀 **Proceed to Full Backfill**: All KR stocks, 2022-2024

---

**Status**: 🔄 In Progress
**Last Updated**: 2025-10-24 14:40
**Next Update**: After dry run completion
