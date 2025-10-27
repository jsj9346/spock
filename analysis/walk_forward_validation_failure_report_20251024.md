# Walk-Forward Validation Failure Analysis Report

**Date**: 2025-10-24
**Strategy**: Tier 3 (Operating_Profit_Margin + RSI_Momentum + ROE_Proxy)
**Validation Period**: 2018-01-01 to 2024-10-09
**Status**: ❌ **VALIDATION FAILED - CRITICAL DATA ISSUES**

---

## Executive Summary

Walk-Forward validation of Tier 3 strategy revealed **critical data availability issues** that invalidate all prior backtesting results. The strategy is **NOT production-ready** and requires fundamental data infrastructure fixes before any further validation.

### Results Overview

| Period | Train Period | Test Period | Result | Return | Sharpe | Max DD |
|--------|--------------|-------------|--------|--------|--------|--------|
| **1** | 2018-2020 | 2020 | ❌ **FAILED** | N/A | N/A | N/A |
| **2** | 2020-2021 | 2022 | ❌ **CATASTROPHIC** | -59.18% | -56.74 | -59.13% |

**Production Readiness: 0/5 criteria passed**

---

## Root Cause Analysis

### Issue 1: Complete Absence of Historical Data (2018-2020)

**Database Investigation Results**:
```sql
SELECT MIN(date), MAX(date), COUNT(*)
FROM ticker_fundamentals
WHERE region = 'KR';

Result:
  Earliest: 2020-01-01
  Latest:   2024-10-09
  Records:  142,433
```

**Impact**:
- Period 1 Walk-Forward required IC calculation for 2018-2020
- Database only contains data from 2020-01-01 onwards
- **2 years of required historical data completely missing**

**Why Period 1 Failed**:
```python
# Backtest script attempted IC calculation for 2018-2020
# Found zero records → empty DataFrame → KeyError on 'portfolio_value'
results_df['returns'] = results_df['portfolio_value'].pct_change()
# KeyError: 'portfolio_value' (column doesn't exist in empty DataFrame)
```

---

### Issue 2: Zero Fundamental Factor Availability

**Tier 3 Factor Requirements**:
1. ✅ `RSI_Momentum` - Technical indicator (calculated from OHLCV)
2. ❌ `Operating_Profit_Margin` - Requires `revenue` + `operating_profit`
3. ❌ `ROE_Proxy` - Requires `net_income` + `total_equity`

**Actual Data Availability (2020-2022 IC period)**:
```sql
SELECT
    COUNT(*) as total_records,
    COUNT(CASE WHEN revenue IS NOT NULL AND operating_profit IS NOT NULL THEN 1 END) as has_oper_margin,
    COUNT(CASE WHEN net_income IS NOT NULL AND total_equity IS NOT NULL THEN 1 END) as has_roe
FROM ticker_fundamentals
WHERE region = 'KR' AND date BETWEEN '2020-01-01' AND '2022-01-01';

Result:
  Total Records: 112
  Operating Margin Data: 0 (0.00%)
  ROE Data: 0 (0.00%)
```

**Impact**:
- Tier 3 intended as **3-factor strategy** (Value + Momentum + Quality)
- Actually operated as **1-factor strategy** (RSI_Momentum only)
- No fundamental data = no Operating_Profit_Margin or ROE_Proxy calculation
- Single technical momentum factor without value/quality anchors

---

### Issue 3: Period 2 Catastrophic Loss (-59.18%)

**Context: 2022 Korean Stock Market**:
- KOSPI Index: -25% decline (bear market year)
- Interest rate hikes, recession fears, China COVID lockdowns

**Tier 3 Performance vs Market**:
```
KOSPI 2022:      -25%
Tier 3 2022:     -59.18%
Relative Loss:   -34.18% (2.4x worse than market)
```

**Root Cause Breakdown**:

1. **RSI Momentum-Only Strategy**:
   - Without fundamental anchors, selected pure momentum stocks
   - Momentum stocks amplify losses during reversals
   - No defensive quality or value factors to cushion downside

2. **Bear Market Exposure**:
   - RSI picked stocks with recent uptrends
   - These were exactly the stocks that crashed hardest in bear market
   - No protection mechanism (no low-volatility, no quality screens)

3. **0% Win Rate**:
   - 55 holdings, but 0% profitable rebalances
   - Every single rebalancing period was a loss
   - No holdings provided downside protection

**Why This Happened**:
```python
# Intended Strategy (Tier 3 design)
score = 0.33 * Operating_Profit_Margin + 0.33 * RSI_Momentum + 0.33 * ROE_Proxy

# Actual Execution (due to missing data)
score = 0.00 * Operating_Profit_Margin + 1.00 * RSI_Momentum + 0.00 * ROE_Proxy
#       ^^^^^ zero data                                      ^^^^^ zero data

# Result: Pure momentum strategy with no fundamental validation
```

---

## Data Availability Summary

### Current Database State

| Data Type | Earliest Date | Latest Date | Tickers | Records | Coverage |
|-----------|---------------|-------------|---------|---------|----------|
| **OHLCV** | 2020-01-02 | 2024-10-08 | 130 | 134,129 | ✅ Good |
| **Fundamentals** | 2020-01-01 | 2024-10-09 | 130 | 142,433 | ⚠️ Incomplete |
| **Technical Analysis** | N/A | N/A | 0 | 0 | ❌ Missing |

### Fundamental Data Completeness

**Raw Fields Available**:
- ✅ `per`, `pbr`, `psr`, `pcr` (valuation ratios)
- ✅ `dividend_yield`, `dividend_per_share`
- ✅ `market_cap`, `shares_outstanding`
- ⚠️ `revenue`, `operating_profit` (exist but **100% NULL** for 2020-2022)
- ⚠️ `net_income`, `total_equity` (exist but **100% NULL** for 2020-2022)
- ⚠️ `gross_profit`, `total_assets`, `total_liabilities` (exist but **100% NULL**)

**Calculated Factors Possible**:
- ✅ `PE_Ratio` (from `per` field)
- ✅ `PB_Ratio` (from `pbr` field)
- ✅ `Dividend_Yield` (from `dividend_yield` field)
- ✅ `Market_Cap` (from `market_cap` field)
- ❌ `Operating_Profit_Margin` (requires revenue + operating_profit)
- ❌ `ROE` (requires net_income + total_equity)
- ❌ `Debt_to_Equity` (requires total_liabilities + total_equity)
- ❌ `Current_Ratio` (requires current_assets + current_liabilities)

---

## Implications for Tier 3

### Invalid Prior Results

All previous Tier 3 backtesting results are **invalid**:

1. **Comprehensive Optimization Report (2025-10-24)**:
   - Reported: Tier 3 +2.42% return, 2.78 Sharpe ratio (2023-2024)
   - Reality: This was RSI_Momentum-only performance, not Tier 3
   - Fundamental factors contributed **nothing** (0% data)

2. **Phase 3-1 IC Analysis**:
   - Reported: Operating_Profit_Margin IC = +0.065
   - Reported: ROE_Proxy IC = +0.048
   - Reality: These ICs were likely calculated from partial data or proxies
   - The actual fundamental values used in backtesting were **all NULL**

3. **Factor Selection**:
   - Tier 3 was selected as optimal combination
   - Selection based on incomplete data representation
   - True multi-factor performance unknown

### Why Recent Backtest "Succeeded" (2023-2024)

**Context**: 2023-2024 was a strong recovery period (KOSPI +20%)

**Why RSI Momentum-Only Worked**:
- Bull market favors momentum strategies
- Recent trends continued (momentum worked)
- No need for defensive quality/value factors
- Low-hanging fruit: any momentum strategy would have worked

**This Masked the Problem**:
- Appeared as successful 3-factor strategy
- Actually was 1-factor strategy that got lucky in bull market
- Walk-Forward validation exposed this by testing bear market (2022)

---

## Recommended Actions

### Priority 1: Data Infrastructure Fix (CRITICAL)

**A. Backfill Historical Fundamental Data (2018-2020)**

```bash
# Required: Backfill 2+ years of historical fundamental data
python3 scripts/backfill_fundamentals_dart.py \
  --start-date 2018-01-01 \
  --end-date 2020-01-01 \
  --rate-limit 1.0
```

**Estimated Time**:
- 130 tickers × 2 years × 4 quarters = ~1,000 DART API calls
- At 1.0 req/sec = ~17 minutes

**B. Fix Fundamental Data NULL Issues (2020-2024)**

**Investigation Required**:
```bash
# Why are revenue, operating_profit, net_income all NULL?
# Possible causes:
# 1. DART API parsing bug
# 2. Data source mismatch (DART vs KIS API)
# 3. Field mapping error
# 4. Incomplete backfill
```

**Action**:
1. Inspect `scripts/backfill_fundamentals_dart.py` for parsing bugs
2. Verify DART API response structure
3. Check field mapping in `modules/parsers/kr_stock_parser.py`
4. Re-run backfill with debug logging

---

### Priority 2: Validate Available Factors Only

**Use Factors with Confirmed Data Availability**:

**Option A: Valuation + Momentum (Partial Tier 3)**
```python
factors = [
    'PE_Ratio',         # Available from PER field
    'PB_Ratio',         # Available from PBR field
    'RSI_Momentum',     # Available from OHLCV
]
```

**Option B: Pure Technical Momentum**
```python
factors = [
    'RSI_Momentum',     # 14-day RSI
    '12M_Momentum',     # 12-month price return
    '1M_Momentum',      # 1-month price return
]
```

**Option C: Valuation-Only (Defensive)**
```python
factors = [
    'PE_Ratio',         # Price-to-Earnings
    'PB_Ratio',         # Price-to-Book
    'Dividend_Yield',   # Dividend yield
]
```

**Re-run Walk-Forward with Validated Factors**:
```bash
# Test Option A first (most similar to Tier 3 intent)
python3 scripts/walk_forward_validation.py \
  --factors PE_Ratio,PB_Ratio,RSI_Momentum \
  --train-years 2 \
  --test-years 1 \
  --start 2020-01-01 \
  --end 2024-10-09 \
  --capital 100000000
```

**Expected Outcome**:
- Should complete without KeyError
- Will reveal true multi-factor performance
- Provides baseline for comparison

---

### Priority 3: Fix and Re-validate Tier 3

**After Data Infrastructure Fixed**:

1. **Verify Factor Calculation**:
```bash
# Test factor calculation on sample data
python3 scripts/test_factor_calculation.py \
  --factors Operating_Profit_Margin,ROE_Proxy \
  --tickers 005930,000660,035720 \
  --start 2020-01-01 \
  --end 2024-10-09
```

2. **Re-run IC Analysis (Phase 3-1)**:
```bash
# Recalculate ICs with complete fundamental data
python3 scripts/calculate_ic_time_series.py \
  --start-date 2020-01-01 \
  --end-date 2024-10-09 \
  --region KR \
  --holding-period 21
```

3. **Re-run Walk-Forward Validation**:
```bash
# Full 3-factor Tier 3 validation
python3 scripts/walk_forward_validation.py \
  --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy \
  --train-years 2 \
  --test-years 1 \
  --start 2020-01-01 \
  --end 2024-10-09 \
  --capital 100000000
```

---

## Lessons Learned

### 1. Data Validation is Critical

**Issue**: Assumed database had required data based on schema existence
**Reality**: Schema existed but columns were 100% NULL
**Lesson**: **Always validate data availability before strategy development**

**Prevention**:
```python
# Add data validation to backtest script
def validate_factor_data(factors, start_date, end_date):
    for factor in factors:
        coverage = check_data_coverage(factor, start_date, end_date)
        if coverage < 0.8:  # Require 80%+ coverage
            raise ValueError(f"Factor {factor} has only {coverage:.1%} coverage")
```

### 2. Single-Period Validation is Insufficient

**Issue**: Tier 3 validated only on 2023-2024 bull market period
**Reality**: Strategy failed catastrophically in 2022 bear market (-59%)
**Lesson**: **Out-of-sample testing across multiple market regimes is mandatory**

**Best Practice**:
- Test across at least 3 market regimes (bull, bear, sideways)
- Require positive returns in >60% of periods
- Maximum drawdown threshold: -20%
- Validate on most recent data AND historical crashes

### 3. Factor Availability ≠ Factor Usability

**Issue**: Database had `revenue`, `operating_profit` columns
**Reality**: All values were NULL, factor calculation impossible
**Lesson**: **Check actual data values, not just schema**

**Checklist**:
- ✅ Schema exists?
- ✅ Data populated (not NULL)?
- ✅ Data quality validated (no outliers, reasonable ranges)?
- ✅ Data freshness confirmed (recent dates)?
- ✅ Historical coverage sufficient (required lookback period)?

### 4. "Good Results" Need Skepticism

**Issue**: Tier 3 showed excellent results (+2.42%, 2.78 Sharpe)
**Reality**: Results were from RSI-only in bull market, not 3-factor strategy
**Lesson**: **Exceptional results warrant deeper investigation, not celebration**

**Red Flags to Watch**:
- Sharpe ratio >3.0 (suspiciously high)
- Zero losing rebalances (too perfect)
- Win rate >80% (likely overfitting or data leak)
- Returns >50% annually (unrealistic for equity factors)

---

## Next Steps

### Immediate (This Week)

1. ✅ ~~Walk-Forward validation attempted~~ → Revealed data issues
2. ⚠️ Fix fundamental data NULL issue (Priority 1)
3. ⚠️ Backfill 2018-2020 historical data (Priority 1)
4. ⚠️ Re-run validation with available factors only (Priority 2)

### Short-Term (Next Week)

1. Verify factor calculation pipeline end-to-end
2. Re-run Phase 3-1 IC analysis with complete data
3. Re-validate Tier 3 strategy with Walk-Forward
4. Document data quality checks in backtest pipeline

### Long-Term (Month)

1. Implement automated data quality monitoring
2. Setup alerts for NULL value increases
3. Add data validation to all backtesting scripts
4. Build data availability dashboard

---

## Conclusion

Walk-Forward validation successfully identified **critical data infrastructure issues** that invalidated all prior Tier 3 results. The strategy is not production-ready and requires fundamental data fixes before any further validation.

**Current Status**: ❌ **NOT READY FOR PRODUCTION**

**Blockers**:
1. Zero fundamental data availability (2020-2024)
2. Missing historical data (2018-2020)
3. Actual strategy performance unknown (tested RSI-only, not Tier 3)

**Resolution Path**:
1. Fix fundamental data pipeline
2. Backfill historical data
3. Re-validate with complete multi-factor strategy
4. Require 3/3 Walk-Forward periods to pass (not just 1/2)

---

**Report Generated**: 2025-10-24 23:59 KST
**Next Review**: After fundamental data fixes complete
**Contact**: Spock Quant Platform Team
