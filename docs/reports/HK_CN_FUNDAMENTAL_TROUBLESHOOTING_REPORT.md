# HK/CN Fundamental Data Troubleshooting Report

**Date**: 2025-12-19
**Issue**: HK/CN region fundamental data queries returning "DATA_NOT_FOUND" errors
**Affected Tickers**: All HK/CN tickers (e.g., 2318.HK, 600519.SS)
**Severity**: HIGH - Blocking MCP fundamental data queries

---

## Executive Summary

HK and CN region fundamental data collection is **partially functional** but missing critical balance sheet metrics (`total_assets`, `total_liabilities`) required by MCP queries. The root cause is incomplete data source coverage across existing backfill scripts.

**Database Status**: ✅ Data EXISTS (6,923 CN records, 11,460 HK records)
**Data Completeness**: ❌ INCOMPLETE (missing balance sheet data)
**Root Cause**: AkShare-only collection strategy missing quarterly balance sheet data

---

## Problem Analysis

### 1. Database Investigation

```sql
-- HK/CN fundamental data exists in database
SELECT region, COUNT(*) FROM ticker_fundamentals GROUP BY region;
```

| Region | Records |
|--------|---------|
| CN     | 6,923   |
| HK     | 11,460  |
| KR     | 162,310 |
| US     | 52,088  |

**Sample Data for 2318.HK**:
```sql
SELECT ticker, period_type, date, revenue, net_income, total_assets, total_liabilities
FROM ticker_fundamentals
WHERE ticker = '2318.HK'
ORDER BY date DESC LIMIT 1;
```

| ticker  | period_type | date       | revenue          | net_income      | total_assets | total_liabilities |
|---------|-------------|------------|------------------|-----------------|--------------|-------------------|
| 2318.HK | QUARTERLY   | 2024-12-31 | 1,142,184,000,000 | 126,607,000,000 | **NULL**     | **NULL**          |

**Finding**: Data exists but `total_assets` and `total_liabilities` are NULL, causing MCP queries to fail.

---

### 2. Data Collection Architecture

#### Current HK/CN Collection Strategy

**spock_refresh.py → run_akshare_fundamental_backfill()**
- Calls: `CNAdapter.collect_fundamentals()` and `HKAdapter.collect_fundamentals()`
- Data Source: **AkShare library only**
- Metrics: ~15-36 financial indicators (ratios, margins, per-share metrics)

#### AkShare Data Coverage

**CN (stock_financial_analysis_indicator)**:
- ✅ EPS, BPS, ROE, ROA
- ✅ Debt Ratio, Current Ratio, Quick Ratio
- ✅ Gross Margin, Net Margin, Operating Margin
- ✅ Revenue, Net Income (but not from balance sheet)
- ❌ **Total Assets** (not provided)
- ❌ **Total Liabilities** (not provided)

**HK (stock_financial_hk_analysis_indicator_em)**:
- ✅ EPS, BPS, ROE, ROA
- ✅ Debt Ratio, Current Ratio
- ✅ Gross Margin, Net Margin
- ✅ Revenue, Net Income
- ❌ **Total Assets** (not provided)
- ❌ **Total Liabilities** (not provided)

**Verification**: Examined parser code in:
- `modules/parsers/hk_stock_parser.py:parse_hk_financial_indicators()`
- `modules/parsers/cn_stock_parser.py:parse_cn_financial_indicators()`

Both parsers confirm: AkShare does NOT provide balance sheet absolute values.

---

### 3. Alternative Data Source Investigation

#### yfinance Library (QUARTERLY Data Available)

**Test Results**:

**HK Stock (2318.HK - Ping An Insurance)**:
```python
import yfinance as yf
ticker = yf.Ticker('2318.HK')
bs_q = ticker.quarterly_balance_sheet

# Output:
# ✅ Total Assets: 13,649,993,000,000
# ✅ Total Liabilities: 12,276,535,000,000
# ✅ Revenue: 302,521,000,000
# ✅ Net Income: 64,809,000,000
# ✅ 7 quarters of historical data
```

**CN Stock (600519.SS - Kweichow Moutai)**:
```python
ticker = yf.Ticker('600519.SS')
bs_q = ticker.quarterly_balance_sheet

# Output:
# ✅ Total Assets: 292,257,789,096
# ✅ Total Liabilities: 43,122,202,833
# ✅ 6 quarters of historical data
```

**Conclusion**: yfinance DOES provide quarterly balance sheet data for both HK and CN markets.

---

### 4. Existing Backfill Scripts Analysis

#### backfill_fundamentals_yfinance.py
**Status**: EXISTS
**Period Type**: **DAILY only**
**Metrics Collected**:
- Valuation ratios (P/E, P/B, P/S, EV/EBITDA)
- Market cap, shares outstanding
- Dividend yield, dividend per share
- Current price, EPS, book value

**Missing**:
- ❌ **No QUARTERLY balance sheet data**
- ❌ **No total_assets extraction**
- ❌ **No total_liabilities extraction**

**Code Location**: `scripts/backfill_fundamentals_yfinance.py:fetch_yfinance_fundamental_data()`

#### backfill_fundamentals_akshare.py
**Status**: EXISTS
**Period Type**: QUARTERLY
**Metrics Collected**:
- CN: 86 financial indicators (ratios, margins, per-share)
- HK: 36 financial indicators (ratios, margins, per-share)

**Missing**:
- ❌ **No balance sheet absolute values** (AkShare limitation)

---

## Root Cause Summary

| Script                             | Period Type | total_assets | total_liabilities | Current Status |
|---------------------------------------|-------------|--------------|-------------------|----------------|
| run_akshare_fundamental_backfill()   | QUARTERLY   | ❌            | ❌                 | ✅ Running      |
| backfill_fundamentals_yfinance.py    | DAILY       | ❌            | ❌                 | ✅ Running      |
| **Missing: QUARTERLY yfinance**      | QUARTERLY   | ✅ Available  | ✅ Available       | ❌ NOT IMPLEMENTED |

**Root Cause**: No backfill script exists to collect **quarterly balance sheet data** from yfinance for HK/CN regions.

---

## Proposed Solution

### Option A: Enhance Existing yfinance Script (Recommended)

**Modify**: `scripts/backfill_fundamentals_yfinance.py`

**Changes**:
1. Add `period_type` parameter: 'DAILY' (current) or 'QUARTERLY' (new)
2. When `period_type='QUARTERLY'`:
   - Call `ticker.quarterly_balance_sheet`
   - Call `ticker.quarterly_income_stmt`
   - Extract: `total_assets`, `total_liabilities`, `revenue`, `net_income`
   - Use most recent quarter's data
3. Update `fetch_yfinance_fundamental_data()` to support both modes

**Implementation Steps**:
```python
# In backfill_fundamentals_yfinance.py

def fetch_yfinance_quarterly_data(self, ticker: str, region: str) -> Optional[Dict]:
    """
    Fetch QUARTERLY balance sheet and income statement data from yfinance

    Collects:
    - total_assets
    - total_liabilities
    - revenue (quarterly)
    - net_income (quarterly)
    - current_assets
    - current_liabilities
    """
    yf_symbol = self.map_ticker_symbol(ticker, region)
    yf_ticker = self.yf.Ticker(yf_symbol)

    # Get quarterly balance sheet
    bs_q = yf_ticker.quarterly_balance_sheet
    inc_q = yf_ticker.quarterly_income_stmt

    if bs_q is None or bs_q.empty:
        return None

    # Extract most recent quarter (column 0)
    latest_date = bs_q.columns[0]

    metrics = {
        'ticker': ticker,
        'region': region,
        'date': latest_date.strftime('%Y-%m-%d'),
        'period_type': 'QUARTERLY',
        'data_source': 'yfinance',

        # Balance sheet
        'total_assets': self._safe_int(bs_q.loc['Total Assets', latest_date] if 'Total Assets' in bs_q.index else None),
        'total_liabilities': self._safe_int(bs_q.loc['Total Liabilities Net Minority Interest', latest_date] if 'Total Liabilities Net Minority Interest' in bs_q.index else None),
        'current_assets': self._safe_int(bs_q.loc['Current Assets', latest_date] if 'Current Assets' in bs_q.index else None),
        'current_liabilities': self._safe_int(bs_q.loc['Current Liabilities', latest_date] if 'Current Liabilities' in bs_q.index else None),

        # Income statement
        'revenue': self._safe_int(inc_q.loc['Total Revenue', latest_date] if not inc_q.empty and 'Total Revenue' in inc_q.index else None),
        'net_income': self._safe_int(inc_q.loc['Net Income', latest_date] if not inc_q.empty and 'Net Income' in inc_q.index else None),
    }

    return metrics
```

**Integration in spock_refresh.py**:
```python
def run_yfinance_quarterly_backfill(
    regions: List[str] = None,
    limit: int = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run yfinance QUARTERLY backfill for HK/CN/VN regions

    Collects balance sheet data (total_assets, total_liabilities)
    to complement AkShare fundamental data.
    """
    from scripts.backfill_fundamentals_yfinance import YFinanceFundamentalBackfiller

    target_regions = regions or ['HK', 'CN', 'VN']
    backfiller = YFinanceFundamentalBackfiller(db, dry_run=dry_run)

    for region in target_regions:
        stats = backfiller.run_quarterly_backfill(
            region=region,
            limit=limit
        )
```

**Menu Integration**:
```python
# In setup_fundamental_backfill_submenu()
print(f"  {colored('6.', Fore.WHITE)} 🌐 {colored('Other Markets (yfinance)', Fore.GREEN)} - HK/CN/VN 재무 데이터")
print(f"    → Option 1: DAILY (valuation ratios only)")
print(f"    → Option 2: QUARTERLY (balance sheet data) ⭐ NEW")
```

---

### Option B: Create New Dedicated Script

**Create**: `scripts/backfill_quarterly_balance_sheet.py`

**Scope**: Focused script specifically for quarterly balance sheet backfill (HK, CN, VN)

**Pros**:
- Clean separation of concerns
- No risk of breaking existing DAILY backfill
- Easier to test independently

**Cons**:
- Code duplication (ticker mapping, rate limiting, validation)
- More maintenance overhead

---

## Recommended Action Plan

### Phase 1: Immediate Fix (Day 1)

1. ✅ **Enhance backfill_fundamentals_yfinance.py**
   - Add `fetch_yfinance_quarterly_data()` method
   - Add `run_quarterly_backfill()` method
   - Test with 5 HK + 5 CN tickers

2. ✅ **Add to spock_refresh.py**
   - Create `run_yfinance_quarterly_backfill()` function
   - Add menu option: "QUARTERLY Balance Sheet (yfinance)"

3. ✅ **Run Backfill**
   ```bash
   # From spock_refresh.py menu:
   # 6 → Other Markets → 2 → QUARTERLY Balance Sheet
   # Limit: 100 tickers (test run)
   ```

### Phase 2: Validation (Day 2)

1. **Database Verification**
   ```sql
   SELECT ticker, date, period_type, total_assets, total_liabilities, revenue, net_income
   FROM ticker_fundamentals
   WHERE ticker IN ('2318.HK', '600519.SS')
     AND period_type = 'QUARTERLY'
     AND total_assets IS NOT NULL
   ORDER BY date DESC;
   ```

2. **MCP Query Test**
   ```python
   # Test query_fundamentals MCP tool
   {
     "region": "HK",
     "tickers": ["2318.HK"],
     "categories": ["all"],
     "period_type": "QUARTERLY"
   }

   # Expected: SUCCESS with total_assets, total_liabilities populated
   ```

3. **Calculate Financial Ratios**
   ```python
   # Test calculate_financial_ratios MCP tool
   {
     "region": "HK",
     "tickers": ["2318.HK"],
     "ratio_categories": ["all"]
   }

   # Expected: Debt-to-Asset Ratio = total_liabilities / total_assets
   ```

### Phase 3: Full Deployment (Day 3-5)

1. **Backfill All HK Tickers** (~4,600 stocks)
   - Estimated time: ~38 minutes (0.5s rate limit)
   - Command: `run_yfinance_quarterly_backfill(regions=['HK'])`

2. **Backfill All CN Tickers** (~5,900 stocks)
   - Estimated time: ~49 minutes
   - Command: `run_yfinance_quarterly_backfill(regions=['CN'])`

3. **Backfill VN Tickers** (~800 stocks)
   - Estimated time: ~7 minutes
   - Command: `run_yfinance_quarterly_backfill(regions=['VN'])`

---

## Expected Outcomes

### Before Fix
```json
{
  "success": false,
  "error": {
    "code": "DATA_NOT_FOUND",
    "message": "No fundamental data available",
    "details": {
      "tickers": ["2318.HK"],
      "reason": "데이터베이스에 해당 종목의 재무 데이터가 존재하지 않습니다."
    }
  }
}
```

### After Fix
```json
{
  "success": true,
  "data": {
    "2318.HK": {
      "ticker": "2318.HK",
      "region": "HK",
      "date": "2025-09-30",
      "period_type": "QUARTERLY",
      "total_assets": 13649993000000,
      "total_liabilities": 12276535000000,
      "revenue": 302521000000,
      "net_income": 64809000000,
      "data_source": "yfinance"
    }
  }
}
```

---

## Alternative Approaches Considered

### 1. Use AkShare for Balance Sheet (REJECTED)
**Reason**: AkShare `stock_financial_analysis_indicator()` only provides ratios (e.g., debt ratio 89.93%), NOT absolute values.

### 2. Calculate from Ratios (NOT RECOMMENDED)
**Example**: `total_assets = total_equity / (1 - debt_ratio)`
**Issues**:
- Requires multiple data points (equity, debt_ratio)
- Propagates errors across calculations
- Less accurate than direct balance sheet data
- yfinance provides direct values - use those instead

### 3. Hybrid Strategy (FUTURE ENHANCEMENT)
- AkShare: Detailed ratios, margins (QUARTERLY)
- yfinance: Balance sheet absolutes (QUARTERLY)
- Merge both sources in database (union of metrics)

**Benefits**:
- Maximum data coverage
- Cross-validation between sources
- Redundancy for reliability

**Implementation**: Phase 4 (after Phase 3 validation)

---

## Testing Checklist

- [ ] Test HK ticker with quarterly data: `2318.HK`, `00700.HK`, `09988.HK`
- [ ] Test CN ticker with quarterly data: `600519.SS`, `000001.SZ`, `600036.SS`
- [ ] Test VN ticker (if applicable): sample VN stock
- [ ] Verify MCP `query_fundamentals` returns success
- [ ] Verify MCP `calculate_financial_ratios` computes debt ratio correctly
- [ ] Verify MCP `get_cagr` works for balance sheet metrics
- [ ] Test edge cases: delisted tickers, IPO <1 year, no quarterly data
- [ ] Performance test: 100 tickers in <60 seconds

---

## Monitoring & Alerts

### Data Quality Metrics
```sql
-- Coverage check: % of tickers with balance sheet data
SELECT
    region,
    COUNT(*) FILTER (WHERE total_assets IS NOT NULL) * 100.0 / COUNT(*) as bs_coverage_pct
FROM ticker_fundamentals
WHERE period_type = 'QUARTERLY'
  AND region IN ('HK', 'CN')
GROUP BY region;
```

**Target**: >80% coverage for HK, CN regions

### Alert Conditions
- **Critical**: Balance sheet coverage <50% after backfill
- **Warning**: >10% failed API calls during backfill
- **Info**: Quarterly data older than 120 days

---

## Documentation Updates

After implementation, update:
1. `docs/guides/OPERATIONAL_RUNBOOK_MASTER_FILES.md` - Add quarterly backfill procedure
2. `docs/reference/FACTOR_FORMULAS_AND_REFERENCES.md` - Document balance sheet data sources
3. `CLAUDE.md` - Update HK/CN fundamental data status
4. `spock_refresh.py` docstring - Document new menu option

---

## Conclusion

The HK/CN fundamental data issue is **solvable** with a targeted enhancement to existing infrastructure. By adding quarterly balance sheet collection via yfinance, we can provide complete fundamental data coverage for MCP queries while maintaining existing AkShare-based ratio collection.

**Estimated Implementation Time**: 4-6 hours
**Risk Level**: LOW (isolated change, fallback to DAILY data)
**Impact**: HIGH (unblocks all MCP fundamental queries for HK/CN)

---

**Prepared by**: Claude Sonnet 4.5
**Next Action**: Implement Option A (Phase 1) and test with sample tickers
