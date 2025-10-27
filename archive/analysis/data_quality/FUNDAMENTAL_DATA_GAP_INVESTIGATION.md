# Fundamental Data Gap Investigation Report

**Date**: 2025-10-23
**Status**: ✅ Root Cause Identified
**Blocker**: Quality Factor Backfill
**Priority**: Week 4, Day 3 (Critical)

---

## Executive Summary

Investigated why `ticker_fundamentals` table has 179,019 records but all balance sheet and income statement columns (total_equity, revenue, net_income, etc.) are NULL.

**Root Cause**: The DART backfill script (`scripts/backfill_fundamentals_dart.py`) has a **critical bug** where the INSERT query only includes PER/PBR/PSR columns but **omits all fundamental data columns** that are needed for quality factor calculation.

**Impact**: Cannot calculate quality factors (ROE_Quality, Accruals_Quality, Dividend_Stability, Earnings_Quality) because required financial statement data is not being stored in the database.

---

## Investigation Timeline

### 1. Initial Database Analysis

**Query**: Check ticker_fundamentals table structure and data
```sql
-- Table has correct columns
\d ticker_fundamentals

-- Columns exist: net_income, total_equity, total_assets, revenue, operating_profit, etc.
```

**Finding**: Table structure is correct, columns exist, but all values are NULL.

---

### 2. Data Source Analysis

**Query**: Check what data sources are populating the table
```sql
SELECT data_source, COUNT(*) as count
FROM ticker_fundamentals
WHERE region = 'KR'
GROUP BY data_source
ORDER BY count DESC;
```

**Results**:
| Data Source | Record Count | Percentage |
|-------------|--------------|------------|
| pykrx | 178,732 | 99.8% |
| DART-2025-11012 | 253 | 0.1% |
| DART-2024-11011 | 32 | <0.1% |
| DART-2020/2021-11011 | 2 | <0.1% |

**Finding**:
- **pykrx is the dominant source** (99.8%) - but pykrx only provides PER/PBR ratios, not underlying financial data
- **DART is barely used** (287 records out of 179,019)
- Even DART records have NULL fundamental data

---

### 3. DART Backfill Script Execution History

**Log File**: `logs/20251022_backfill_fundamentals_dart.log`

**Execution Summary** (Oct 22, 2025, 10:19 AM):
- **Tickers Processed**: 139 (new/IPO stocks)
- **Success Rate**: 98.6% (137/139)
- **Duration**: 46 minutes 53 seconds
- **API Calls**: 139
- **Records Inserted**: 137

**Sample Debug Output** (Ticker 466100):
```
DEBUG: Params: ('466100', 'KR', '2025-10-22', 'SEMI-ANNUAL',
                None, None, 41950.0, None, None, None, 'DART-2025-11012')
```

**Finding**:
- Script is executing successfully
- DART API is returning data (successfully parsed Semi-Annual Report 2025)
- **BUT**: All fundamental data fields are being inserted as `None`

---

### 4. DART API Client Analysis

**File**: `modules/dart_api_client.py`

**Method**: `_parse_financial_statements()` (Lines 453-539)

**Code Review**:
```python
def _parse_financial_statements(self, ticker: str, items: List[Dict],
                                year: int, reprt_code: str) -> Dict:
    # ... parsing logic ...

    # Extract key financial items (Lines 509-517)
    total_assets = item_lookup.get('자산총계', 0)
    total_liabilities = item_lookup.get('부채총계', 0)
    total_equity = item_lookup.get('자본총계', 0)
    revenue = item_lookup.get('매출액', 0) or item_lookup.get('영업수익', 0)
    operating_profit = item_lookup.get('영업이익', 0)
    net_income = item_lookup.get('당기순이익', 0)

    # Store raw financial items (Lines 530-535)
    metrics['total_assets'] = total_assets
    metrics['total_liabilities'] = total_liabilities
    metrics['total_equity'] = total_equity
    metrics['revenue'] = revenue
    metrics['operating_profit'] = operating_profit
    metrics['net_income'] = net_income

    return metrics  # ✅ Returns all fundamental data
```

**Finding**:
- **DART API client is working correctly**
- Successfully parses Korean account names (자산총계, 부채총계, etc.)
- **Returns all fundamental data** in the metrics dict
- The problem is NOT in the API client

---

### 5. DART Backfill Script Analysis (THE BUG)

**File**: `scripts/backfill_fundamentals_dart.py`

**Method**: `insert_or_update_fundamental_data()` (Lines 351-451)

**Bug Location**: Lines 402-434 (INSERT query)

**Data Preparation** (Lines 374-399):
```python
# Prepare data for insertion
data = {
    'ticker': ticker,
    'region': 'KR',
    'date': metrics.get('date'),
    'period_type': metrics.get('period_type', 'ANNUAL'),
    'close_price': float(price),
    'data_source': metrics.get('data_source'),

    # From DART ✅ PREPARED BUT NOT INSERTED
    'total_assets': metrics.get('total_assets'),
    'total_liabilities': metrics.get('total_liabilities'),
    'total_equity': metrics.get('total_equity'),
    'revenue': metrics.get('revenue'),
    'operating_profit': metrics.get('operating_profit'),
    'net_income': metrics.get('net_income'),
    'roe': metrics.get('roe'),
    'roa': metrics.get('roa'),
    'debt_ratio': metrics.get('debt_ratio'),

    # Calculated ratios
    'per': ratios.get('per'),
    'pbr': ratios.get('pbr'),
    'psr': ratios.get('psr'),
    'market_cap': ratios.get('market_cap'),
    'shares_outstanding': metrics.get('shares_outstanding')
}
```

**INSERT Query** (Lines 402-424):
```python
query = """
INSERT INTO ticker_fundamentals (
    ticker, region, date, period_type,
    shares_outstanding, market_cap, close_price,
    per, pbr, psr,                           ← ONLY RATIOS INCLUDED
    data_source, created_at
)
VALUES (
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, NOW()
)
ON CONFLICT (ticker, region, date, period_type)
DO UPDATE SET
    shares_outstanding = EXCLUDED.shares_outstanding,
    market_cap = EXCLUDED.market_cap,
    close_price = EXCLUDED.close_price,
    per = EXCLUDED.per,                      ← ONLY RATIOS UPDATED
    pbr = EXCLUDED.pbr,
    psr = EXCLUDED.psr,
    data_source = EXCLUDED.data_source
"""
```

**ROOT CAUSE IDENTIFIED** ❌:
- **Data dict includes**: total_assets, total_liabilities, total_equity, revenue, operating_profit, net_income, roe, roa, debt_ratio
- **INSERT query only includes**: per, pbr, psr, market_cap, shares_outstanding
- **Missing from INSERT**: total_assets, total_liabilities, total_equity, revenue, operating_profit, net_income, roe, roa, debt_ratio, current_assets, current_liabilities

**This explains**:
1. Why ticker_fundamentals has PER/PBR values (they are inserted)
2. Why all fundamental data columns are NULL (they are prepared but never inserted)
3. Why quality factors cannot be calculated (no ROE, net_income, total_equity data)

---

## Impact Assessment

### Quality Factors Blocked

Cannot calculate the following quality factors without fundamental data:

1. **ROE_Quality** (Return on Equity)
   - **Requires**: net_income, total_equity
   - **Status**: ❌ BLOCKED (both columns NULL)

2. **Accruals_Quality** (Earnings Quality)
   - **Requires**: net_income, operating_cash_flow, total_assets
   - **Status**: ❌ BLOCKED (all columns NULL)

3. **Debt_Ratio_Quality** (Financial Stability)
   - **Requires**: total_liabilities, total_equity
   - **Status**: ❌ BLOCKED (both columns NULL)

4. **Dividend_Stability** (Dividend Consistency)
   - **Requires**: dividend_per_share, net_income
   - **Status**: ⚠️ PARTIAL (dividend data exists, but net_income NULL)

5. **Profit_Margin_Quality**
   - **Requires**: operating_profit, revenue
   - **Status**: ❌ BLOCKED (both columns NULL)

### Multi-Factor Analysis Blocked

**Week 4 Goal**: Calculate IC for 7+ factors (Value, Momentum, Quality)

**Current Status**:
- ✅ **Value Factors**: Complete (250 dates, PER/PBR available)
- ✅ **Momentum Factors**: Complete (262 dates, 94,194 records)
- ❌ **Quality Factors**: BLOCKED (0 records with fundamental data)

**Cannot proceed** with multi-factor IC comparison until quality factors are calculated.

---

## Solution Design

### Fix #1: Update INSERT Query in backfill_fundamentals_dart.py

**File**: `scripts/backfill_fundamentals_dart.py`
**Method**: `insert_or_update_fundamental_data()` (Lines 402-434)

**Required Changes**:

1. **Add missing columns to INSERT statement**:
```python
query = """
INSERT INTO ticker_fundamentals (
    ticker, region, date, period_type,
    shares_outstanding, market_cap, close_price,
    per, pbr, psr,
    data_source, created_at,

    -- ADD THESE COLUMNS ↓
    total_assets, total_liabilities, total_equity,
    revenue, operating_profit, net_income,
    current_assets, current_liabilities, inventory,
    fiscal_year
)
VALUES (
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, NOW(),

    -- ADD THESE PARAMS ↓
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s
)
...
```

2. **Update params tuple to include new values**:
```python
params = (
    data['ticker'], data['region'], data['date'], data['period_type'],
    data['shares_outstanding'], data['market_cap'], data['close_price'],
    data['per'], data['pbr'], data['psr'],
    data['data_source'],

    # ADD THESE PARAMS ↓
    data.get('total_assets'), data.get('total_liabilities'), data.get('total_equity'),
    data.get('revenue'), data.get('operating_profit'), data.get('net_income'),
    data.get('current_assets'), data.get('current_liabilities'), data.get('inventory'),
    data.get('fiscal_year')
)
```

3. **Update ON CONFLICT DO UPDATE clause**:
```python
ON CONFLICT (ticker, region, date, period_type)
DO UPDATE SET
    shares_outstanding = EXCLUDED.shares_outstanding,
    market_cap = EXCLUDED.market_cap,
    close_price = EXCLUDED.close_price,
    per = EXCLUDED.per,
    pbr = EXCLUDED.pbr,
    psr = EXCLUDED.psr,
    data_source = EXCLUDED.data_source,

    -- ADD THESE UPDATES ↓
    total_assets = EXCLUDED.total_assets,
    total_liabilities = EXCLUDED.total_liabilities,
    total_equity = EXCLUDED.total_equity,
    revenue = EXCLUDED.revenue,
    operating_profit = EXCLUDED.operating_profit,
    net_income = EXCLUDED.net_income,
    current_assets = EXCLUDED.current_assets,
    current_liabilities = EXCLUDED.current_liabilities,
    inventory = EXCLUDED.inventory,
    fiscal_year = EXCLUDED.fiscal_year
```

---

### Fix #2: Enhance DART API Parser (Optional)

**Current Limitation**: Parser only extracts 6 Korean account names

**Potential Enhancement**: Add more account names for better coverage
```python
# Current (Lines 510-517)
total_assets = item_lookup.get('자산총계', 0)
total_liabilities = item_lookup.get('부채총계', 0)
total_equity = item_lookup.get('자본총계', 0)
revenue = item_lookup.get('매출액', 0) or item_lookup.get('영업수익', 0)
operating_profit = item_lookup.get('영업이익', 0)
net_income = item_lookup.get('당기순이익', 0)

# Enhanced
current_assets = item_lookup.get('유동자산', 0)
current_liabilities = item_lookup.get('유동부채', 0)
inventory = item_lookup.get('재고자산', 0)
accounts_receivable = item_lookup.get('매출채권', 0)
operating_cash_flow = item_lookup.get('영업활동현금흐름', 0)
```

---

## Execution Plan

### Phase 1: Fix Backfill Script (30 minutes)

**Step 1**: Edit `scripts/backfill_fundamentals_dart.py`
- Update INSERT query (lines 402-424)
- Update params tuple (lines 426-432)
- Add missing columns to data dict if needed

**Step 2**: Test with dry-run
```bash
python3 scripts/backfill_fundamentals_dart.py --dry-run --limit 5
```

**Expected Output**: Dry-run should show fundamental data values (not None)

---

### Phase 2: Re-Run DART Backfill (1-2 hours)

**Step 1**: Re-backfill existing DART records
```bash
# Update existing 287 DART records with fundamental data
python3 scripts/backfill_fundamentals_dart.py --incremental
```

**Expected Result**: 287 records updated with total_equity, revenue, net_income values

**Step 2**: Verify database update
```sql
-- Check if fundamental data is now populated
SELECT
    COUNT(*) FILTER (WHERE total_equity IS NOT NULL) as has_equity,
    COUNT(*) FILTER (WHERE revenue IS NOT NULL) as has_revenue,
    COUNT(*) FILTER (WHERE net_income IS NOT NULL) as has_net_income
FROM ticker_fundamentals
WHERE region = 'KR' AND data_source LIKE 'DART%';

-- Expected: All counts should be >0 (ideally ~287)
```

---

### Phase 3: Full DART Backfill (8-12 hours)

**Challenge**: Only 287 out of 179,019 records are from DART

**Options**:

1. **Option A: pykrx Enhancement** (Recommended)
   - pykrx is already providing 178,732 records
   - Check if pykrx library has methods to fetch fundamental data
   - If yes, update `scripts/backfill_fundamentals_pykrx.py` to extract balance sheet data

2. **Option B: DART Corp Code Expansion**
   - Only 139 tickers have DART corp_code mappings currently
   - Download latest DART corp_code master (covers ~2,000+ listed companies)
   - Re-run backfill for all tickers with corp_codes
   - Estimated: 2,000+ tickers × 18 seconds/call = 10-12 hours

3. **Option C: Alternative Data Sources**
   - Investigate KIS API for fundamental data endpoints
   - yfinance (for international coverage)
   - Other Korean financial data providers

**Recommended Approach**: Start with pykrx investigation (Option A) as it already covers 99.8% of tickers.

---

## Verification Queries

### After Fix: Verify Fundamental Data Populated

```sql
-- Check overall coverage
SELECT
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE total_equity IS NOT NULL) as has_equity,
    COUNT(*) FILTER (WHERE revenue IS NOT NULL) as has_revenue,
    COUNT(*) FILTER (WHERE net_income IS NOT NULL) as has_net_income,
    ROUND(COUNT(*) FILTER (WHERE total_equity IS NOT NULL)::numeric / COUNT(*) * 100, 2) as equity_coverage_pct
FROM ticker_fundamentals
WHERE region = 'KR';
```

### Test Quality Factor Calculation

```sql
-- Test ROE calculation
WITH latest_fundamentals AS (
    SELECT
        ticker,
        total_equity,
        net_income,
        CASE
            WHEN total_equity > 0 AND net_income IS NOT NULL
            THEN (net_income / total_equity) * 100
        END as roe
    FROM ticker_fundamentals
    WHERE region = 'KR'
      AND date >= NOW() - INTERVAL '90 days'
      AND total_equity IS NOT NULL
      AND net_income IS NOT NULL
)
SELECT COUNT(*) as calculable_roe_records
FROM latest_fundamentals
WHERE roe IS NOT NULL;

-- Expected: >0 (ideally 100+ stocks)
```

---

## Lessons Learned

### 1. Always Verify Data Insertion

**Issue**: Script prepared data correctly but INSERT query didn't match.

**Learning**: After implementing data collection scripts, verify that:
- Data is prepared correctly ✅
- INSERT query includes all columns ✅
- Params tuple matches query placeholders ✅
- Database actually contains the data (not just logs saying "success") ✅

### 2. Incremental Testing

**Issue**: 179,019 records inserted but no one checked if fundamental data columns were populated.

**Learning**:
- Test with LIMIT 10 first, manually verify database records
- Check both success rate AND data completeness
- Don't trust "✅ Success" logs without verifying actual database contents

### 3. Data Source Transparency

**Issue**: ticker_fundamentals table had 99.8% pykrx data, but documentation claimed DART was the source.

**Learning**:
- Always check data_source column distribution
- Understand what each data source provides (pykrx = ratios only, DART = full statements)
- Document data source capabilities and limitations

---

## Next Steps

### Immediate (Day 3)
1. ✅ **Investigation Complete**: Root cause identified
2. ⏳ **Fix INSERT Query**: Update backfill_fundamentals_dart.py
3. ⏳ **Dry-Run Test**: Verify fix works correctly
4. ⏳ **Re-Backfill DART Records**: Update existing 287 records with fundamental data

### Short-Term (Days 4-5)
5. ⏳ **pykrx Investigation**: Check if pykrx can provide fundamental data
6. ⏳ **Corp Code Expansion**: Expand DART coverage to 2,000+ tickers
7. ⏳ **Full Fundamental Backfill**: Execute 8-12 hour backfill job

### Medium-Term (Week 5)
8. ⏳ **Quality Factor Calculation**: Calculate ROE, Accruals, Debt Ratio factors
9. ⏳ **Quality Factor Backfill**: Backfill 250 dates of quality factors
10. ⏳ **Multi-Factor IC Analysis**: Compare IC for all 7+ factors

---

**Report Created**: 2025-10-23
**Investigation Duration**: 45 minutes
**Status**: ✅ Root Cause Identified, Ready for Fix Implementation
**Next Action**: Fix INSERT query and re-run DART backfill
