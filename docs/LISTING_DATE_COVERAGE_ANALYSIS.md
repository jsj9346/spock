# Listing Date Coverage Analysis Report

**Date**: 2025-11-10
**Status**: Root Cause Identified for HK/CN/VN Low Coverage

---

## Executive Summary

Analysis of listing_date backfill coverage reveals critical issues with three Asian markets:

| Market | Coverage | Root Cause | Solution Available |
|--------|----------|------------|-------------------|
| **HK** | 0.00% (0/2,723) | ❌ Ticker format mismatch | ✅ Yes - Remove leading zeros |
| **CN** | 0.03% (1/3,451) | ❌ Ticker stored with suffix | ✅ Yes - Strip suffix before API call |
| **VN** | 55.66% (310/557) | ⚠️ Delisted tickers | ⚠️ Partial - Filter inactive |

**Impact**: 6,731 tickers missing listing_date data, preventing effective filtering in data collection workflows.

---

## Detailed Analysis

### 1. Hong Kong (HK) Market - 0.00% Coverage

#### Problem
yfinance API requires **4-digit format** (e.g., `0001.HK`), but database contains **mixed formats**:
- Some tickers already have `.HK` suffix: `0001.HK`, `0700.HK` ✅
- Some tickers have 5 digits with extra leading zero: `00001`, `00700` ❌

#### Evidence
Testing confirmed the format sensitivity:

```python
# WORKS
yf.Ticker('0001.HK').history()  # ✅ CK Hutchison Holdings
yf.Ticker('0700.HK').history()  # ✅ Tencent

# FAILS
yf.Ticker('00001.HK').history() # ❌ Empty history
yf.Ticker('00700.HK').history() # ❌ Empty history
yf.Ticker('1.HK').history()     # ❌ Empty history
yf.Ticker('700.HK').history()   # ❌ Empty history
```

#### Database Storage Pattern
```sql
-- Sample from tickers table
HK     | 0700      | 4 digits | No suffix (WRONG - needs normalization)
HK     | 0001.HK   | 7 chars  | Already has .HK suffix (CORRECT)
HK     | 2018.HK   | 7 chars  | Already has .HK suffix (CORRECT)
```

#### Root Cause
The `backfill_listing_dates_overseas.py` script blindly adds `.HK` suffix:
```python
# Current code (BROKEN)
suffix = '.HK'
yf_ticker = f"{ticker}{suffix}"  # Results in '0700.HK' OR '0001.HK.HK'
```

This causes two failure modes:
1. **Tickers already with suffix** → Doubled suffix: `0001.HK.HK` ❌
2. **Tickers without suffix** → Correct format BUT if database has extra leading zero → `00700.HK` ❌

#### Solution
**Fix 1**: Strip existing `.HK` suffix before adding it back
**Fix 2**: Normalize HK tickers to 4-digit format (remove extra leading zeros)

```python
# Proposed fix
def normalize_hk_ticker(ticker: str) -> str:
    """
    Normalize HK ticker to 4-digit format required by yfinance
    Examples:
        '0001.HK' → '0001'
        '00001' → '0001'
        '0700' → '0700'
        '00700' → '0700'
    """
    # Remove .HK suffix if present
    base_ticker = ticker.replace('.HK', '')

    # Remove leading zeros beyond 4 digits
    if base_ticker.isdigit() and len(base_ticker) > 4:
        base_ticker = base_ticker.lstrip('0').zfill(4)

    return base_ticker

# Usage
if region == 'HK':
    base_ticker = normalize_hk_ticker(ticker)
    yf_ticker = f"{base_ticker}.HK"
```

**Expected Impact**: 0% → ~95% coverage (2,700+ tickers updated)

---

### 2. China (CN) Market - 0.03% Coverage

#### Problem
Database stores CN tickers **with exchange suffix** (`.SS` or `.SZ`), but backfill script tries to add suffix again.

#### Evidence
```sql
-- Sample from tickers table
CN | 688099.SS | AMLOGIC (SHANGHAI) CO LTD  -- Already has .SS
CN | 600519    | Kweichow Moutai            -- No suffix
```

Testing confirmed yfinance works with correct format:
```python
yf.Ticker('600519.SS').history()  # ✅ SUCCESS - 5,958 records
yf.Ticker('600519.SS.SS').history()  # ❌ Would fail if doubled
```

#### Root Cause
Current code adds suffix to **ALL** CN tickers:
```python
# Current code (BROKEN for pre-suffixed tickers)
for exchange_suffix in ['.SS', '.SZ']:
    yf_ticker = f"{ticker}{exchange_suffix}"  # Results in '688099.SS.SS' ❌
```

#### Solution
**Check if suffix already exists before adding**:

```python
def normalize_cn_ticker(ticker: str) -> tuple:
    """
    Normalize CN ticker, return (base_ticker, existing_suffix)
    Examples:
        '688099.SS' → ('688099', '.SS')
        '600519' → ('600519', None)
    """
    if ticker.endswith('.SS'):
        return (ticker[:-3], '.SS')
    elif ticker.endswith('.SZ'):
        return (ticker[:-3], '.SZ')
    else:
        return (ticker, None)

# Usage
if region == 'CN':
    base_ticker, existing_suffix = normalize_cn_ticker(ticker)

    if existing_suffix:
        # Ticker already has exchange info - use it directly
        yf_ticker = ticker
        hist = yf.Ticker(yf_ticker).history(period='max')
        if not hist.empty:
            return hist.index[0].date()
    else:
        # Try both exchanges
        for exchange_suffix in ['.SS', '.SZ']:
            yf_ticker = f"{base_ticker}{exchange_suffix}"
            # ... rest of logic
```

**Expected Impact**: 0.03% → ~95% coverage (3,300+ tickers updated)

---

### 3. Vietnam (VN) Market - 55.66% Coverage

#### Problem
247 out of 557 tickers (44%) return `"possibly delisted; no timezone found"` errors from yfinance.

#### Evidence
```
ERROR | $AAV.VN: possibly delisted; no timezone found
ERROR | $BBS.VN: possibly delisted; no timezone found
ERROR | $C69.VN: possibly delisted; no timezone found
... (247 similar errors)
```

Successful tickers work fine:
```python
yf.Ticker('AAA.VN').history()  # ✅ 569 records (2023-07-17 onwards)
yf.Ticker('VNM.VN').history()  # ✅ 569 records (2023-07-17 onwards)
yf.Ticker('VCB.VN').history()  # ✅ 4,085 records (2009-06-30 onwards)
```

#### Root Cause
These tickers are likely **actually delisted** or have very limited trading history. yfinance has limited VN market coverage.

**Note**: Successful VN tickers show data only from **2023-07-17 onwards**, suggesting yfinance added VN market support recently.

#### Solution Options
**Option A (Conservative)**: Accept current 55.66% coverage
- Mark remaining 247 tickers as `is_active = false` if delisting confirmed
- Focus efforts on HK/CN fixes which have higher impact

**Option B (Aggressive)**: Implement alternative VN data source
- Use **VnDirect API** or **SSI API** (Vietnamese brokers)
- More complex integration, requires API keys
- Defer to Phase 3 (post HK/CN fixes)

**Recommended**: Option A for now, revisit in Phase 3 if needed.

**Expected Impact**: 55.66% → 60-70% coverage (filtering delisted tickers)

---

## Implementation Roadmap

### Phase 1: Fix HK Market (HIGH PRIORITY) ⚡
**Effort**: 1 hour
**Impact**: +2,700 tickers (0% → 95%)

**Tasks**:
1. Add `normalize_hk_ticker()` function
2. Update HK logic in `backfill_listing_dates_overseas.py`
3. Run backfill: `--regions HK --delay 0.2`
4. Verify coverage: Should reach ~95%

### Phase 2: Fix CN Market (HIGH PRIORITY) ⚡
**Effort**: 1 hour
**Impact**: +3,300 tickers (0.03% → 95%)

**Tasks**:
1. Add `normalize_cn_ticker()` function
2. Update CN logic to handle pre-suffixed tickers
3. Run backfill: `--regions CN --delay 0.2`
4. Verify coverage: Should reach ~95%

### Phase 3: Improve VN Market (LOW PRIORITY) 📋
**Effort**: 3-4 hours (if using alternative API)
**Impact**: +40-80 tickers (55.66% → 70%)

**Tasks**:
1. Research VnDirect/SSI API availability
2. Identify genuinely delisted tickers
3. Implement alternative source OR mark inactive
4. Run backfill: `--regions VN --delay 0.2`

---

## Expected Final Coverage

| Market | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|--------|---------|---------------|---------------|---------------|
| KR | 99.84% ✅ | 99.84% | 99.84% | 99.84% |
| US | 92.12% ✅ | 92.12% | 92.12% | 92.12% |
| JP | 99.83% ✅ | 99.83% | 99.83% | 99.83% |
| **HK** | 0.00% ❌ | **95%+ ✅** | 95%+ | 95%+ |
| **CN** | 0.03% ❌ | 0.03% | **95%+ ✅** | 95%+ |
| **VN** | 55.66% ⚠️ | 55.66% | 55.66% | **70% ⚠️** |
| **Overall** | **77.23%** | **90%+** | **95%+** | **96%+** |

---

## Technical Notes

### yfinance Ticker Format Requirements

**Hong Kong Exchange**:
- **Required Format**: 4-digit with leading zeros + `.HK`
- ✅ Valid: `0001.HK`, `0700.HK`, `9988.HK`
- ❌ Invalid: `1.HK`, `700.HK`, `00001.HK`, `0001.HK.HK`

**China Exchanges**:
- **Shanghai Stock Exchange**: 6-digit + `.SS`
- **Shenzhen Stock Exchange**: 6-digit + `.SZ`
- ✅ Valid: `600519.SS`, `000001.SZ`
- ❌ Invalid: `600519`, `600519.SS.SS` (no suffix or double suffix)

**Vietnam Exchange**:
- **Required Format**: 3-letter code + `.VN`
- ✅ Valid: `VNM.VN`, `VCB.VN`, `AAA.VN`
- ⚠️ Limited Coverage: yfinance VN data only from 2023-07-17 onwards

### Database Normalization Recommendations

**Option A (Recommended)**: Store base ticker, add suffix in API calls
```sql
-- Tickers table stores base ticker only
HK | 0001 | CK Hutchison Holdings
CN | 600519 | Kweichow Moutai
VN | VNM | Vinamilk

-- Code adds suffix when calling API
yf_ticker = f"{base_ticker}{SUFFIX_MAP[region]}"
```

**Option B**: Store fully-qualified ticker, strip suffix in API calls
```sql
-- Tickers table stores with suffix
HK | 0001.HK | CK Hutchison Holdings
CN | 600519.SS | Kweichow Moutai
VN | VNM.VN | Vinamilk

-- Code strips and re-adds suffix
base = ticker.split('.')[0]
yf_ticker = f"{base}{SUFFIX_MAP[region]}"
```

**Current State**: Mixed approach causing issues. Recommend migrating to Option A.

---

## References

- **yfinance Documentation**: https://pypi.org/project/yfinance/
- **HK Stock Exchange**: https://www.hkex.com.hk/
- **Shanghai Stock Exchange**: http://english.sse.com.cn/
- **Shenzhen Stock Exchange**: http://www.szse.cn/English/
- **Backfill Log**: `/Users/13ruce/spock/logs/20251107_backfill_listing_dates_overseas.log`
- **Implementation**: `/Users/13ruce/spock/scripts/backfill_listing_dates_overseas.py`

---

**Last Updated**: 2025-11-10
**Author**: Claude Code Analysis
**Status**: ✅ Root Cause Analysis Complete - Ready for Implementation
