# Full Refresh Troubleshooting Report
**Date**: 2025-11-14
**Pipeline Duration**: 945m 11s (15h 45m)
**Regions**: KR, US, HK, JP, CN, VN
**Status**: ⚠️ Partial Success (6/7 steps completed, validation issues found)

---

## Executive Summary

Full refresh pipeline completed successfully for 7 data collection steps (tickers, ohlcv, fundamentals, daily_valuation, technical_indicators, dividend, fx_tracking). However, data quality validation revealed **2 critical issues**:

1. **❌ Schema Error**: `is_etf` column reference in validators.py (KR validation failed)
2. **⚠️ Low OHLCV Coverage**: CN (70.2%), VN (55.5%) below 80% threshold

**Overall Validation**: 0/6 regions passed quality gates

---

## Issue 1: Schema Mismatch - `is_etf` Column

### Problem
```
ERROR: column "is_etf" does not exist
LINE 4: WHERE region = 'KR' AND is_etf = FALSE
```

### Root Cause
- **File**: [modules/orchestration/validators.py:210](../modules/orchestration/validators.py#L210)
- **Issue**: Code references non-existent `is_etf` column
- **Database Schema**: Uses `asset_type` column instead (`'STOCK'`, `'ETF'`, etc.)

### Impact
- ❌ KR region validation completely failed
- ℹ️ Other regions validated successfully (did not check fundamental coverage)

### Resolution ✅
**Fixed** in commit [validators.py:210](../modules/orchestration/validators.py#L210)

```python
# BEFORE
WHERE region = %s AND is_etf = FALSE

# AFTER
WHERE region = %s AND asset_type = 'STOCK'
```

### Verification
```bash
# Test validation after fix
psql -d quant_platform -c "
SELECT COUNT(*) as stock_count
FROM tickers
WHERE region = 'KR' AND asset_type = 'STOCK';
"
# Expected: ~2,500 stocks
```

---

## Issue 2: CN Market - Low OHLCV Coverage (70.2%)

### Statistics
| Metric | Value |
|--------|-------|
| Total Tickers | 3,451 |
| Tickers with OHLCV | 2,425 |
| Coverage | 70.2% |
| Missing OHLCV | 1,026 (29.8%) |

### Root Cause Analysis

#### Ticker Format Distribution
| Format | Total | With OHLCV | Coverage |
|--------|-------|------------|----------|
| Shanghai (.SS) | 1,455 | 1,455 | **100.0%** ✅ |
| Shenzhen (.SZ) | 1,995 | 969 | **48.6%** ❌ |
| No Suffix | 1 | 1 | 100.0% |

#### Shenzhen (.SZ) Breakdown by Ticker Length
| Ticker Length | Total | With OHLCV | Coverage |
|---------------|-------|------------|----------|
| 6-digit (e.g., 000001.SZ) | 970 | 969 | **99.9%** ✅ |
| 4-digit (e.g., 1201.SZ) | 736 | 0 | **0.0%** ❌ |
| 3-digit (e.g., 100.SZ) | 248 | 0 | **0.0%** ❌ |
| 2-digit (e.g., 12.SZ) | 36 | 0 | **0.0%** ❌ |
| 1-digit (e.g., 1.SZ) | 5 | 0 | **0.0%** ❌ |

### Findings
1. **Shanghai (.SS)**: ✅ Perfect coverage (all 1,455 tickers)
2. **Shenzhen 6-digit**: ✅ Near-perfect coverage (969/970, 99.9%)
3. **Shenzhen Short Tickers**: ❌ **yfinance does NOT support tickers with <6 digits**
   - 1,025 invalid tickers (1+2+3+4 digit formats)
   - yfinance returns: `"possibly delisted"` or `"No data found"`

### Example Validation
```python
# Valid CN ticker formats
✅ 600000.SS  → Shanghai 6-digit (supported)
✅ 000001.SZ  → Shenzhen 6-digit (supported)

# Invalid CN ticker formats
❌ 100.SZ     → Too short (not supported)
❌ 12.SZ      → Too short (not supported)
❌ 1.SZ       → Too short (not supported)
```

### Recommendations

#### Option A: Data Source Cleanup (Recommended) ⭐
**Action**: Remove invalid short-format tickers from database

```sql
-- Preview invalid tickers
SELECT COUNT(*) FROM tickers
WHERE region = 'CN'
  AND ticker LIKE '%.SZ'
  AND LENGTH(REPLACE(ticker, '.SZ', '')) < 6;
-- Expected: 1,025 tickers

-- Mark as inactive (safer than deletion)
UPDATE tickers
SET is_active = FALSE,
    data_source = 'invalid_format_yfinance_unsupported'
WHERE region = 'CN'
  AND ticker LIKE '%.SZ'
  AND LENGTH(REPLACE(ticker, '.SZ', '')) < 6;
```

**Impact**: CN coverage would increase to **99.9%** (2,424/2,426 valid tickers)

#### Option B: Alternative Data Source
**Action**: Implement direct China exchange API integration
- **Source**: AkShare, Tushare, or direct SSE/SZSE APIs
- **Effort**: High (new adapter development required)
- **Benefit**: Support for all ticker formats including delisted stocks

#### Option C: Accept Current State
**Action**: Document limitation and proceed with 70.2% coverage
- **Risk**: Missing data for 1,026 tickers
- **Mitigation**: Exclude CN from quant strategies or use only valid tickers

### Recommended Action
✅ **Option A**: Clean up invalid ticker formats (safest, fastest)

---

## Issue 3: VN Market - Low OHLCV Coverage (55.5%)

### Statistics
| Metric | Value |
|--------|-------|
| Total Tickers | 557 |
| Tickers with OHLCV | 309 |
| Coverage | 55.5% |
| Missing OHLCV | 248 (44.5%) |

### Root Cause Analysis

#### Data Source Distribution
| Source Category | Total | With OHLCV | Coverage |
|-----------------|-------|------------|----------|
| Unknown/NULL | 310 | 309 | **99.7%** ✅ |
| yfinance_unavailable | 247 | 0 | **0.0%** ❌ |

### Findings
1. **yfinance-supported tickers**: ✅ 99.7% coverage (309/310)
2. **yfinance-unavailable tickers**: ❌ 247 tickers explicitly marked as unsupported
   - These tickers likely failed during initial data collection
   - yfinance API does not provide data for these VN stocks

### Example Validation
```python
# yfinance VN ticker support
✅ VNM.VN  → Supported (Vinamilk)
✅ FPT.VN  → Supported (FPT Corp)
✅ AAA     → Supported (with or without .VN suffix)

❌ 247 tickers → Not available in yfinance database
```

### Recommendations

#### Option A: Alternative Data Source (Recommended) ⭐
**Action**: Implement Vietnam stock exchange API integration

**Suggested Sources**:
- **HOSE/HNX Official APIs**: Direct exchange data (most reliable)
- **SSI API**: Vietnamese broker API (comprehensive coverage)
- **VND Direct API**: Vietnamese financial data provider
- **AkShare**: Python library with VN stock support

**Implementation Priority**: Medium
- **Effort**: Moderate (new adapter required, similar to KR adapter)
- **Benefit**: Full coverage for all 557 VN tickers
- **Estimated Time**: 1-2 weeks development

#### Option B: Accept Limited Coverage
**Action**: Proceed with 309 yfinance-supported tickers (55.5% coverage)
- **Risk**: Missing nearly half of VN market
- **Mitigation**: Document limitation, focus on major stocks (VN30)

#### Option C: Hybrid Approach
**Action**:
1. Keep current 309 tickers with yfinance data
2. Implement VN exchange API for remaining 247 tickers
3. Prioritize based on market cap/liquidity

### Recommended Action
✅ **Option A**: Implement VN exchange API adapter (future Phase 2 work)

---

## Validation Metrics Summary

### Regional Coverage
| Region | Tickers | OHLCV Coverage | Anomalies | Status |
|--------|---------|----------------|-----------|--------|
| **KR** | - | - | - | ❌ Validation Error (Fixed) |
| **US** | 6,532 | **92.7%** | 96 | ⚠️ Below threshold |
| **HK** | 2,723 | **102.3%** | 27 | ⚠️ Duplicate data issue |
| **JP** | 4,036 | **99.4%** | 13 | ✅ Near-perfect |
| **CN** | 3,451 | **70.2%** | 3 | ❌ Invalid ticker formats |
| **VN** | 557 | **55.5%** | 0 | ❌ yfinance unsupported |

### Quality Gate Thresholds
- ✅ OHLCV Coverage: **≥80%**
- ✅ Anomaly Threshold: **≤10**
- ⚠️ Current Pass Rate: **0/6 regions** (all have issues)

---

## Action Items

### Immediate (Priority 1) ✅
1. [x] **Fix schema error** in validators.py (`is_etf` → `asset_type`)
2. [ ] **Re-run validation** after fix to verify KR region
3. [ ] **Clean CN invalid tickers** (1,025 short-format .SZ tickers)

### Short-term (Priority 2) 📋
4. [ ] **Investigate HK 102.3% coverage** (duplicate OHLCV records?)
5. [ ] **Analyze US 92.7% coverage** (missing ~480 tickers)
6. [ ] **Document VN limitation** in project docs

### Medium-term (Priority 3) 🔮
7. [ ] **Implement VN exchange API adapter** (full 557 ticker coverage)
8. [ ] **Consider CN alternative API** (AkShare/Tushare) for comprehensive coverage
9. [ ] **Add data quality monitoring** to daily pipeline

---

## SQL Cleanup Scripts

### 1. Mark Invalid CN Tickers as Inactive
```sql
-- Preview count
SELECT
    LENGTH(REPLACE(ticker, '.SZ', '')) as len,
    COUNT(*) as cnt
FROM tickers
WHERE region = 'CN' AND ticker LIKE '%.SZ'
GROUP BY len
ORDER BY len;

-- Mark as inactive (reversible)
BEGIN;

UPDATE tickers
SET
    is_active = FALSE,
    data_source = 'invalid_format_yfinance_unsupported',
    last_updated = NOW()
WHERE region = 'CN'
  AND ticker LIKE '%.SZ'
  AND LENGTH(REPLACE(ticker, '.SZ', '')) < 6;

-- Verify (should show 1,025 updated)
SELECT COUNT(*) FROM tickers
WHERE region = 'CN'
  AND data_source = 'invalid_format_yfinance_unsupported';

COMMIT;
```

### 2. Verify HK Duplicate OHLCV Data
```sql
-- Check for duplicate OHLCV records
SELECT
    ticker,
    region,
    date,
    timeframe,
    COUNT(*) as dup_count
FROM ohlcv_data
WHERE region = 'HK'
GROUP BY ticker, region, date, timeframe
HAVING COUNT(*) > 1
LIMIT 20;

-- If found, delete duplicates (keep latest)
-- (Uncomment only after verification)
-- DELETE FROM ohlcv_data
-- WHERE ctid NOT IN (
--     SELECT MAX(ctid)
--     FROM ohlcv_data
--     WHERE region = 'HK'
--     GROUP BY ticker, region, date, timeframe
-- );
```

### 3. Re-run Validation
```bash
# After fixes, re-run validation
python3 -c "
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.validators import DataQualityValidator

db = PostgresDatabaseManager()
validator = DataQualityValidator(db)

results = validator.validate_pipeline_output(['KR', 'US', 'HK', 'JP', 'CN', 'VN'])

print('\\n📊 Validation Results:')
for region, result in results.items():
    status = '✅' if result['passed'] else '❌'
    print(f'{status} {region}: {result.get(\"ticker_count\", 0)} tickers, '
          f'OHLCV: {result.get(\"ohlcv_coverage\", 0):.1%}')
"
```

---

## Lessons Learned

### Code Quality
1. **Schema Validation**: Always validate schema queries against actual database structure
2. **Type Safety**: Consider using ORM (SQLAlchemy) to prevent column name errors
3. **Integration Tests**: Add validation tests to CI/CD pipeline

### Data Quality
1. **Ticker Format Validation**: Validate ticker formats before database insertion
2. **API Coverage Checks**: Document API limitations during data source selection
3. **Coverage Monitoring**: Add automated alerts for coverage drops below 80%

### Process Improvements
1. **Incremental Validation**: Run validation after each pipeline step, not just at end
2. **Dry-run Mode**: Test validation logic before 15-hour production runs
3. **Rollback Strategy**: Implement checkpoint-based recovery for failed validations

---

## References

### Modified Files
- ✅ [modules/orchestration/validators.py:210](../modules/orchestration/validators.py#L210) - Fixed `is_etf` → `asset_type`

### Related Documentation
- [QUANT_DATABASE_SCHEMA.md](QUANT_DATABASE_SCHEMA.md) - Database schema reference
- [QUANT_DEVELOPMENT_WORKFLOWS.md](QUANT_DEVELOPMENT_WORKFLOWS.md) - Data quality workflows
- [spock_refresh.py](../spock_refresh.py) - Full refresh pipeline

### External Resources
- **yfinance Documentation**: https://github.com/ranaroussi/yfinance
- **China Stock APIs**: AkShare (https://github.com/akfamily/akshare), Tushare
- **Vietnam APIs**: SSI API, HOSE/HNX official APIs

---

**Report Generated**: 2025-11-14
**Author**: Quant Platform Troubleshooting System
**Next Review**: After implementing Priority 1 fixes
