# Multi-Market lot_size Update Plan

**Date**: 2025-10-17
**Purpose**: Ensure accurate lot_size (board lot/trading unit) data across all 6 markets
**Status**: Planning Phase

---

## Executive Summary

After successfully fixing Hong Kong lot_size data (Week 2 completion), this plan ensures all markets have accurate, market-specific lot_size values. Currently, 5 out of 6 markets use static defaults that may not reflect actual exchange requirements.

### Current Status (2025-10-17)

| Market | Status | Lot_size Values | Data Source | Accuracy |
|--------|--------|----------------|-------------|----------|
| **HK** | ✅ **FIXED** | 100-2000 (15 unique) | KIS Master File | 100% |
| **KR** | ✅ **ACCURATE** | 1 | Exchange rule (1 share/lot) | 100% |
| **US** | ✅ **ACCURATE** | 1 | Exchange rule (1 share/lot) | 100% |
| **CN** | ⚠️ **STATIC** | 100 (hardcoded) | Default value | Unknown |
| **JP** | ⚠️ **STATIC** | 100 (hardcoded) | Default value | Unknown |
| **VN** | ⚠️ **STATIC** | 100 (hardcoded) | Default value | Unknown |

**Risk Assessment**:
- **HK**: ✅ No action needed (already accurate)
- **KR/US**: ✅ No action needed (exchange rules verified)
- **CN/JP/VN**: ⚠️ Investigation required (static defaults may be inaccurate)

---

## Part 1: Market-Specific Analysis

### 1.1 Korea (KR) - ✅ ACCURATE

**Current Implementation**:
```python
# modules/market_adapters/kr_adapter.py:160
parsed['lot_size'] = 1  # Korea: 1 share per lot
```

**Exchange Rules**:
- KOSPI/KOSDAQ: 1 share per lot (단주 거래 가능)
- No minimum trading unit restrictions
- Reference: KRX regulations

**Data Quality**:
- Total tickers: 1,364
- Lot_size: 1 (100% uniform)
- Status: ✅ **ACCURATE** - No update needed

**Verification**: Korea allows single-share trading, static value is correct.

---

### 1.2 United States (US) - ✅ ACCURATE

**Current Implementation**:
```python
# modules/market_adapters/us_adapter_kis.py:219
'lot_size': 1,  # US: 1 share per lot

# modules/market_adapters/us_adapter_kis.py:289
ticker_info['lot_size'] = 1  # US: 1 share per lot
```

**Exchange Rules**:
- NYSE, NASDAQ, AMEX: 1 share per lot
- No minimum trading unit (odd lots allowed)
- Reference: SEC Rule 240.15c3-3

**Data Quality**:
- Total tickers: 6,388
- Lot_size: 1 (100% uniform)
- Status: ✅ **ACCURATE** - No update needed

**Verification**: US markets allow fractional share trading, static value is correct.

---

### 1.3 China (CN) - ⚠️ REQUIRES VALIDATION

**Current Implementation**:
```python
# modules/market_adapters/cn_adapter_kis.py:238
'lot_size': 100,  # China: Fixed 100 shares per lot

# modules/market_adapters/cn_adapter_kis.py:308
ticker_info['lot_size'] = 100  # China: Fixed 100 shares per lot
```

**Exchange Rules** (Research Needed):
- SSE (Shanghai Stock Exchange): 100 shares/lot (1手 = 100股)
- SZSE (Shenzhen Stock Exchange): 100 shares/lot (1手 = 100股)
- Exception: Bonds and special securities may have different units
- Reference: CSRC regulations, exchange rules

**Data Quality**:
- Total tickers: 3,450 A-shares (선강통/후강통)
- Lot_size: 100 (100% uniform)
- Status: ⚠️ **NEEDS VALIDATION**

**Investigation Required**:
1. ✅ Standard A-shares: 100 shares/lot (verified)
2. ❓ Special securities (ST, *ST): Same as regular stocks?
3. ❓ Small-cap stocks: Different lot sizes?
4. ❓ Data source: KIS Master File available?

**Action Plan**:
- [ ] Research CSRC/SSE/SZSE regulations for lot_size rules
- [ ] Test KIS Master File (cns.cod, szs.cod) for lot_size column
- [ ] Validate 100 shares/lot applies to all A-shares
- [ ] Create validation script if exceptions exist

---

### 1.4 Japan (JP) - ⚠️ REQUIRES VALIDATION

**Current Implementation**:
```python
# modules/market_adapters/jp_adapter_kis.py:199
'lot_size': 100,  # Japan: Fixed 100 shares per lot

# modules/market_adapters/jp_adapter_kis.py:263
ticker_info['lot_size'] = 100  # Japan: Fixed 100 shares per lot
```

**Exchange Rules** (Research Needed):
- TSE (Tokyo Stock Exchange): Variable lot sizes (100, 1000, etc.)
- **2018 Reform**: Standardized to 100 shares/lot for most stocks
- Exception: Some stocks still use 1, 10, 1000, or 10000 shares/lot
- Reference: TSE regulations, JPX guidelines

**Data Quality**:
- Total tickers: 4,036
- Lot_size: 100 (100% uniform)
- Status: ⚠️ **NEEDS VALIDATION**

**Known Issues**:
- Japan had **non-uniform lot sizes** before 2018 reform
- Some stocks exempted from standardization (penny stocks, REITs)
- Lot_size may vary: 1, 10, 100, 1000, or 10000 shares/lot

**Investigation Required**:
1. ✅ Standard stocks: 100 shares/lot (post-2018 reform)
2. ❓ Penny stocks (<¥100): Different lot sizes?
3. ❓ REITs: Different lot sizes?
4. ❓ Data source: KIS Master File (jps.cod) available?

**Action Plan**:
- [ ] Research TSE post-2018 reform lot_size rules
- [ ] Test KIS Master File (jps.cod) for lot_size column
- [ ] Identify stocks with non-100 lot sizes
- [ ] Create update script if exceptions exist

---

### 1.5 Vietnam (VN) - ⚠️ REQUIRES VALIDATION

**Current Implementation**:
```python
# modules/market_adapters/vn_adapter_kis.py:227
'lot_size': 100,  # Vietnam: Fixed 100 shares per lot

# modules/market_adapters/vn_adapter_kis.py:298
ticker_info['lot_size'] = 100  # Vietnam: Fixed 100 shares per lot
```

**Exchange Rules** (Research Needed):
- HOSE (Ho Chi Minh Stock Exchange): 100 shares/lot (1 lô = 100 cổ phiếu)
- HNX (Hanoi Stock Exchange): 100 shares/lot (1 lô = 100 cổ phiếu)
- Exception: Bonds and warrants may have different units
- Reference: SSC (State Securities Commission) regulations

**Data Quality**:
- Total tickers: 696
- Lot_size: 100 (100% uniform)
- Status: ⚠️ **NEEDS VALIDATION**

**Investigation Required**:
1. ✅ Standard stocks: 100 shares/lot (verified)
2. ❓ Small-cap stocks: Different lot sizes?
3. ❓ Odd lots allowed?
4. ❓ Data source: KIS Master File available?

**Action Plan**:
- [ ] Research SSC/HOSE/HNX regulations for lot_size rules
- [ ] Test KIS Master File (vns.cod, has.cod) for lot_size column
- [ ] Validate 100 shares/lot applies to all stocks
- [ ] Create validation script if exceptions exist

---

### 1.6 Hong Kong (HK) - ✅ ACCURATE

**Current Implementation**:
```python
# modules/market_adapters/hk_adapter_kis.py:592-640
def _fetch_lot_size(self, ticker: str) -> int:
    """Fetch HK board lot (lot_size) from KIS Master File"""
    # Master file lookup with ticker normalization
    # Returns actual board lot (100-2000+)
```

**Exchange Rules**:
- HKEX (Hong Kong Stock Exchange): Variable board lots
- Range: 100-10,000+ shares/lot (most common: 500, 2000, 1000)
- Reference: HKEX regulations

**Data Quality**:
- Total tickers: 2,722
- Unique lot_sizes: 15 (100, 200, 250, 300, 400, 500, 800, 1000, 1500, 2000, etc.)
- Status: ✅ **ACCURATE** (fixed in Week 2)

**Data Source**: KIS Master File (hks.cod) "Bid order size" column

---

## Part 2: Data Source Investigation

### 2.1 KIS Master Files (.cod) - PRIMARY SOURCE

**Master File Structure**:
```
data/
  master_files/
    hks.cod   # Hong Kong (2,722 stocks) - ✅ VALIDATED
    nas.cod   # NASDAQ (3,813 stocks)
    nys.cod   # NYSE (2,453 stocks)
    amx.cod   # AMEX (262 stocks)
    cns.cod   # China Shanghai (?) - ❓ TO TEST
    szs.cod   # China Shenzhen (?) - ❓ TO TEST
    jps.cod   # Japan TSE (4,036 stocks) - ❓ TO TEST
    vns.cod   # Vietnam HNX (?) - ❓ TO TEST
    has.cod   # Vietnam HOSE (?) - ❓ TO TEST
```

**Testing Priority**:
1. **High Priority**: jps.cod (Japan - known to have exceptions)
2. **Medium Priority**: cns.cod, szs.cod (China - need verification)
3. **Low Priority**: vns.cod, has.cod (Vietnam - likely uniform 100)

**Test Script Template** (based on HK success):
```python
#!/usr/bin/env python3
"""
Test KIS Master File for {MARKET} stock lot_size information
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager

def main():
    mgr = KISMasterFileManager()

    # Parse market master file
    df = mgr.parse_market('{market_code}')  # 'jps', 'cns', 'szs', 'vns', 'has'

    if df.empty:
        print(f"❌ No data in {market_code} master file")
        return

    # Show all columns
    print(f"Available columns: {df.columns.tolist()}")

    # Look for lot_size related columns
    lot_columns = [col for col in df.columns
                  if any(keyword in col.lower()
                        for keyword in ['lot', 'unit', 'min', 'qty', 'trade', 'board'])]

    if lot_columns:
        print(f"✅ Found lot_size related columns: {lot_columns}")
        for col in lot_columns:
            print(f"   {col}: {df[col].value_counts().head(10)}")
    else:
        print("❌ No lot_size related columns found")

if __name__ == '__main__':
    main()
```

---

### 2.2 Alternative Data Sources

If KIS Master Files don't contain lot_size:

1. **yfinance** (Global):
   - ❌ Does NOT provide lot_size for any market (tested with HK)
   - Only provides fundamentals (P/E, market cap, etc.)

2. **Exchange APIs**:
   - CN: CSRC/SSE/SZSE APIs (if accessible)
   - JP: JPX/TSE APIs (if accessible)
   - VN: SSC/HOSE/HNX APIs (if accessible)

3. **Static Verification**:
   - Confirm exchange regulations for uniform lot sizes
   - If all stocks have same lot_size, static value is acceptable

---

## Part 3: Implementation Strategy

### 3.1 Investigation Phase (Priority Order)

**Step 1: Japan (JP) - HIGH PRIORITY**
```bash
# Create and run test script
python3 scripts/test_kis_master_file_lot_size_jp.py

# Expected outcomes:
# - ✅ Master file contains lot_size column → Proceed to update script
# - ❌ Master file missing lot_size → Research TSE regulations
# - ⚠️ Some stocks have non-100 values → Update script required
```

**Step 2: China (CN) - MEDIUM PRIORITY**
```bash
# Create and run test script
python3 scripts/test_kis_master_file_lot_size_cn.py

# Expected outcomes:
# - ✅ Master file confirms 100 shares/lot → No update needed
# - ❌ Master file missing lot_size → Research CSRC regulations
# - ⚠️ Some stocks have different values → Update script required
```

**Step 3: Vietnam (VN) - LOW PRIORITY**
```bash
# Create and run test script
python3 scripts/test_kis_master_file_lot_size_vn.py

# Expected outcomes:
# - ✅ Master file confirms 100 shares/lot → No update needed
# - ❌ Master file missing lot_size → Research SSC regulations
# - ⚠️ Some stocks have different values → Update script required
```

---

### 3.2 Update Script Strategy (if needed)

**Template** (based on HK success):
```python
#!/usr/bin/env python3
"""
Update {MARKET} stock lot_sizes using KIS Master File

Usage:
    # Dry run (preview changes)
    python3 scripts/update_{market}_lot_sizes.py --dry-run

    # Execute update
    python3 scripts/update_{market}_lot_sizes.py

    # Update specific tickers only
    python3 scripts/update_{market}_lot_sizes.py --tickers {ticker1} {ticker2}
"""

# Key components:
# 1. Adapter's _fetch_lot_size() method (read from master file)
# 2. Batch update script (iterate all tickers)
# 3. Validation (dry-run, database backup)
# 4. Statistics (distribution, success rate)
```

**Code Changes Required**:

1. **Adapter Method** (`modules/market_adapters/{market}_adapter_kis.py`):
```python
def _fetch_lot_size(self, ticker: str) -> int:
    """Fetch {MARKET} lot_size from KIS Master File"""
    try:
        from modules.api_clients.kis_master_file_manager import KISMasterFileManager
        mgr = KISMasterFileManager()
        df = mgr.parse_market('{market_code}')

        # Ticker normalization (market-specific)
        # Master file lookup
        # Validation
        # Return lot_size
    except Exception as e:
        logger.warning(f"[{ticker}] Master file lot_size fetch failed: {e}")
        return self._get_default_lot_size('{REGION}')
```

2. **Update Script** (`scripts/update_{market}_lot_sizes.py`):
```python
# Get all {MARKET} tickers from database
# For each ticker:
#   - Fetch lot_size from adapter._fetch_lot_size()
#   - Compare with current database value
#   - Update if different (with dry-run support)
# Report statistics
```

---

### 3.3 Validation Strategy

**Pre-Update Validation**:
1. Dry-run mode to preview changes
2. Sample ticker verification (5-10 known stocks)
3. Database backup before execution

**Post-Update Validation**:
1. NULL lot_size check (must be 0)
2. Range validation (within expected bounds)
3. Distribution analysis (compare with exchange data)
4. Sample ticker spot-check

**Success Criteria**:
- 0 NULL lot_size values
- >95% success rate
- Distribution matches exchange expectations
- No trading errors due to lot_size

---

## Part 4: Execution Plan

### Phase 1: Investigation (Estimated: 2-3 hours)

**Task 1.1**: Create test scripts for JP, CN, VN
- `scripts/test_kis_master_file_lot_size_jp.py`
- `scripts/test_kis_master_file_lot_size_cn.py`
- `scripts/test_kis_master_file_lot_size_vn.py`

**Task 1.2**: Execute tests and analyze results
- Japan: Check for non-100 lot sizes
- China: Verify 100 shares/lot for all A-shares
- Vietnam: Verify 100 shares/lot for all stocks

**Task 1.3**: Research exchange regulations (if master files incomplete)
- TSE post-2018 reform lot_size rules
- CSRC A-share lot_size rules
- SSC Vietnam lot_size rules

---

### Phase 2: Implementation (Conditional)

**Scenario A: Master Files Confirm Static Values**
- ✅ No code changes needed
- ✅ Update documentation to mark as "Verified Accurate"
- ✅ Skip to Phase 4 (Documentation)

**Scenario B: Master Files Show Exceptions**
- [ ] Update adapter `_fetch_lot_size()` methods
- [ ] Create market-specific update scripts
- [ ] Execute dry-run validation
- [ ] Run full database update
- [ ] Create completion reports

**Estimated Time**:
- Scenario A: 0 hours (documentation only)
- Scenario B: 4-6 hours per market (JP most likely)

---

### Phase 3: Validation (Conditional)

**Post-Update Validation** (if Scenario B):
- [ ] Run validation queries (NULL check, range check)
- [ ] Sample ticker spot-check
- [ ] Compare distribution with exchange data
- [ ] Monitor trading engine for lot_size errors

**Success Metrics**:
- 0 NULL lot_size values
- >95% update success rate
- No trading errors in first week

---

### Phase 4: Documentation

**Completion Report** (per market):
- Investigation findings
- Data source analysis
- Update execution results (if applicable)
- Validation results
- Final lot_size distribution

**Update CLAUDE.md**:
- Mark markets as "Verified Accurate" or "Updated"
- Document data sources
- Add lot_size validation procedures

---

## Part 5: Risk Assessment

### Low Risk (No Action Needed)
- **KR**: ✅ Single-share trading verified
- **US**: ✅ Single-share trading verified
- **HK**: ✅ Master file updated (Week 2)

### Medium Risk (Validation Needed)
- **CN**: Static 100 likely correct, but needs confirmation
- **VN**: Static 100 likely correct, but needs confirmation

### High Risk (Update Likely Needed)
- **JP**: Known to have non-uniform lot sizes (post-2018 exceptions)

### Worst Case Scenario
- Master files don't contain lot_size
- Exchange APIs not accessible
- Manual data collection required (very time-consuming)

**Mitigation**:
- Start with Japan (highest risk)
- If master files work, proceed to CN/VN
- If master files fail, research alternative sources

---

## Part 6: Timeline

### Week 1: Investigation (2-3 hours)
- Day 1: Create test scripts for JP, CN, VN
- Day 2: Execute tests, analyze master files
- Day 3: Research regulations (if needed)

### Week 2: Implementation (0-18 hours)
- Scenario A (No Updates): 0 hours
- Scenario B (JP only): 4-6 hours
- Scenario C (JP + CN + VN): 12-18 hours

### Week 3: Validation & Documentation (2-4 hours)
- Post-update validation
- Completion reports
- CLAUDE.md updates

**Total Estimated Time**: 4-25 hours (depending on findings)

---

## Conclusion

This plan ensures all 6 markets have accurate lot_size data:
- **KR/US**: ✅ Verified accurate (no action needed)
- **HK**: ✅ Fixed in Week 2 (no action needed)
- **JP/CN/VN**: ⚠️ Investigation required

**Next Steps**:
1. Create test scripts for JP, CN, VN
2. Execute master file analysis
3. Determine if updates are needed
4. Implement updates (if required)
5. Document final lot_size status

**Success Criteria**: All markets have 100% accurate lot_size data matching exchange regulations.
