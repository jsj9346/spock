# ETF Details NULL Columns Analysis Report

**Generated**: 2025-10-14
**Database**: spock_local.db
**Total ETFs**: 1,029

---

## Executive Summary

### Current Status
- **✅ Complete (≥95%)**: 11 columns
- **⚠️ Partial (50-95%)**: 1 column (geographic_region: 66.8%)
- **❌ Incomplete (<50%)**: 10 columns (including 9 at 0% coverage)

### Key Findings
1. **Naver Finance scraping** successfully populated 7 fields (100% coverage for 7 core fields)
2. **Inference engine** achieved 98.3-100% for 5 fields, but only 27.8% for sector_theme
3. **External API dependency** prevents population of 9 fields (TER, tracking errors, etc.)

---

## Detailed Analysis

### Category 1: COMPLETE (≥95% Coverage) ✅

These 11 fields have been successfully populated through Naver Finance scraping + inference:

| Field | Coverage | Method |
|-------|----------|--------|
| issuer | 100.0% | Naver Finance direct extraction |
| inception_date | 100.0% | Naver Finance direct extraction |
| tracking_index | 100.0% | Naver Finance direct extraction |
| fund_type | 100.0% | Naver Finance direct extraction |
| expense_ratio | 100.0% | Naver Finance direct extraction |
| leverage_ratio | 100.0% | Inference from ETF name patterns |
| currency_hedged | 100.0% | Inference from hedging keywords |
| data_source | 100.0% | Manual attribution |
| aum | 99.8% | Naver Finance direct extraction (KRW parsing) |
| listed_shares | 99.8% | Naver Finance direct extraction |
| underlying_asset_class | 98.3% | Inference from fund_type mapping |

**Status**: ✅ **No action needed** - These fields meet production quality standards.

---

### Category 2: PARTIAL Coverage (50-95%) ⚠️

#### **geographic_region** (66.8% coverage, 342 NULL)

**Root Causes**:
1. **Missing Geographic Keywords**: Tracking indices lack clear geographic identifiers
   - Example: "iSelect 2차전지양극재 지수" → No KR/US/CN indicator
   - Example: "FnGuide 주주가치 지수" → Implicitly Korean but not explicitly stated

2. **Composite Indices**: Mixed or multi-regional ETFs
   - Example: "코스피 200 TR" → Clearly Korean but missed by current regex

3. **Korean-Only Names**: No English translation in tracking_index
   - Example: "KAP 26-06 특수채 총수익 지수(AAA이상)" → Bond indices

**Impact**:
- 342 ETFs (33.2%) lack regional classification
- Affects portfolio diversification analysis
- Prevents geographic exposure calculations

**Improvement Options**:

##### Option A: Enhanced Inference Rules (Quick Win)
**Effort**: ~1 hour | **Expected Improvement**: +15-20% coverage

Add fallback rules for Korean-only names:
```python
# Default to KR for Korean domestic indices
if any(keyword in combined_text for keyword in ['코스피', '코스닥', 'KAP', 'iSelect', 'FnGuide']):
    if not any(us_kw in combined_text for us_kw in ['미국', 'US', 'S&P', 'NASDAQ']):
        return 'KR'

# Bond indices default to issuer country
if 'Bond' in fund_type or '채권' in fund_type:
    if '한국' in name or not any(global_kw in name for global_kw in ['미국', '글로벌', 'Global']):
        return 'KR'

# Sector-specific Korean indices
if any(theme in name for theme in ['2차전지', '바이오', 'K-AI반도체']):
    return 'KR'
```

**Implementation**:
- Modify `infer_etf_fields.py` → `infer_geographic_region()` function
- Add Korean-centric fallback logic
- Re-run inference on 342 NULL records

##### Option B: Manual Classification (High Quality)
**Effort**: ~3-4 hours | **Expected Improvement**: +30-33% coverage

Create mapping file for ambiguous indices:
```json
{
  "geographic_region_overrides": {
    "iSelect 2차전지양극재 지수": "KR",
    "FnGuide 주주가치 지수": "KR",
    "KAP 26-06 특수채 총수익 지수": "KR",
    "코스피 200 TR": "KR"
  }
}
```

**Implementation**:
- Export 342 NULL records to CSV
- Manual review with domain expertise
- Create override mapping file
- Apply overrides in inference engine

---

### Category 3: INCOMPLETE Coverage (<50%) ❌

#### **sector_theme** (27.8% coverage, 743 NULL)

**Root Causes**:
1. **Broad Market Indices**: No sector classification applies
   - Examples: "코스피 200", "S&P 500", "NASDAQ 100"
   - **Status**: ✅ **Expected behavior** - These ETFs intentionally track broad markets

2. **Bond/Fixed Income ETFs**: Lack sector classification
   - Examples: "26-06 특수채", "회사채(AA-이상)"
   - **Status**: ⚠️ **Could add "Fixed Income" as sector**

3. **Limited Keyword Dictionary**: Only ~30 sector themes defined
   - Missing themes: "Value", "Growth", "Quality", "Momentum", "ESG sub-sectors"
   - Missing Korean terms: "주주가치", "미래전략기술", "디지털성장"

**Impact**:
- 743 ETFs (72.2%) lack sector classification
- Limits sector rotation analysis
- Prevents thematic investment strategies

**Improvement Options**:

##### Option A: Expand Keyword Dictionary (Recommended)
**Effort**: ~2 hours | **Expected Improvement**: +10-15% coverage

Add ~50 new sector themes:
```python
SECTOR_THEMES_EXPANSION = {
    # Factor-based
    '가치': 'Value',
    'Value': 'Value',
    '성장': 'Growth',
    'Growth': 'Growth',
    '퀄리티': 'Quality',
    'Quality': 'Quality',
    '모멘텀': 'Momentum',
    'Momentum': 'Momentum',
    '배당성장': 'Dividend Growth',

    # Korean themes
    '주주가치': 'Shareholder Value',
    '미래전략기술': 'Future Technology',
    '디지털성장': 'Digital Growth',
    '디지털전환': 'Digital Transformation',
    '스마트팩토리': 'Smart Factory',
    '우주항공': 'Aerospace',
    '방위산업': 'Defense',

    # ESG sub-sectors
    '친환경': 'Clean Energy',
    '탄소중립': 'Carbon Neutral',
    '수소': 'Hydrogen',
    '태양광': 'Solar',
    '풍력': 'Wind',

    # Emerging themes
    '양자컴퓨팅': 'Quantum Computing',
    '사이버보안': 'Cybersecurity',
    'Cybersecurity': 'Cybersecurity',
    '핀테크': 'Fintech',
    'Fintech': 'Fintech',
    '블록체인': 'Blockchain',
    'Blockchain': 'Blockchain'
}
```

**Implementation**:
- Update `infer_etf_fields.py` → `SECTOR_THEMES` dictionary
- Re-run inference on all 1,029 ETFs
- Validate new classifications

##### Option B: Accept as "Broad Market" (Practical)
**Effort**: Minimal | **Improvement**: Conceptual clarity

Add explicit "Broad Market" classification:
- ETFs tracking major indices get `sector_theme = "Broad Market"`
- Bond ETFs get `sector_theme = "Fixed Income"`
- Reduces NULL count by ~400 records (to ~340 NULL)

**Trade-off**: Not a true sector, but provides context for filtering.

---

### Category 4: ZERO Coverage (External API Required) ❌

These 9 fields require external data sources beyond Naver Finance:

#### **underlying_asset_count** (0% coverage)
- **Data Source**: Fund prospectus or asset manager API
- **Complexity**: High (requires parsing PDFs or API integration)
- **Priority**: Low (not critical for trading decisions)
- **Recommended Approach**: Future enhancement when KRX API becomes available

#### **ter** (Total Expense Ratio) (0% coverage)
- **Data Source**: Financial Supervisory Service (금융감독원) DART API
- **Complexity**: Medium (API integration required)
- **Priority**: Medium (useful for cost comparison)
- **Recommended Approach**:
  - Integrate FSS DART API: http://dart.fss.or.kr/api
  - Map ETF tickers to fund disclosure IDs
  - Extract TER from quarterly reports

#### **actual_expense_ratio** (0% coverage)
- **Data Source**: Asset manager annual reports
- **Complexity**: High (requires disclosure parsing)
- **Priority**: Low (expense_ratio already available at 100%)
- **Recommended Approach**: Defer until automated disclosure parsing is implemented

#### **tracking_error_20d/60d/120d/250d** (0% coverage)
- **Data Source**: Real-time calculation from OHLCV data
- **Complexity**: Medium (requires historical ETF + index data)
- **Priority**: Medium (useful for passive investing quality assessment)
- **Recommended Approach**:
  1. Collect daily ETF prices (already in spock_local.db via `ohlcv_data`)
  2. Collect daily index prices (requires KRX or Bloomberg API)
  3. Calculate rolling standard deviation of return differences
  4. Implementation: `scripts/calculate_tracking_errors.py`

**Formula**:
```python
tracking_error = std(etf_return - index_return) * sqrt(252)  # Annualized
```

#### **pension_eligible** (0% coverage)
- **Data Source**: Korean pension system regulator database
- **Complexity**: Low (simple boolean lookup)
- **Priority**: Low (not critical for most investors)
- **Recommended Approach**: Manual lookup for top 100 ETFs by AUM, rest marked as NULL

#### **investment_strategy** (0% coverage)
- **Data Source**: Fund prospectus or asset manager website
- **Complexity**: High (requires NLP for text extraction)
- **Priority**: Low (free-text field with limited analytics value)
- **Recommended Approach**: Future enhancement with GPT-4 prospectus parsing

---

## Recommended Action Plan

### Phase 1: Quick Wins (1-2 days effort)

**Target**: Improve geographic_region to 80%+ and sector_theme to 40%+

1. **Enhanced Geographic Inference** (~1 hour)
   - Add Korean-centric fallback rules
   - Expected: 342 → ~240 NULL (80-85% coverage)

2. **Expanded Sector Keywords** (~2 hours)
   - Add 50 new sector themes
   - Expected: 743 → ~620 NULL (40% coverage)

3. **Broad Market Classification** (~30 min)
   - Add explicit "Broad Market" and "Fixed Income" themes
   - Expected: 620 → ~340 NULL (67% coverage)

**Total Effort**: ~3.5 hours
**Expected Improvement**: geographic_region 66.8% → 82%, sector_theme 27.8% → 67%

### Phase 2: Medium-Term Enhancements (1-2 weeks)

1. **FSS DART API Integration** (TER extraction)
   - Effort: 2-3 days
   - Impact: 100% TER coverage

2. **Tracking Error Calculation Engine**
   - Effort: 3-5 days
   - Impact: 90%+ tracking error coverage (excluding newly listed ETFs)

3. **Manual Classification for Top 100 ETFs**
   - Effort: 1 day
   - Impact: High-AUM ETFs get complete metadata

### Phase 3: Long-Term Strategy (3+ months)

1. **KRX Open API Integration**
   - Comprehensive ETF metadata
   - Real-time index prices for tracking error calculation

2. **Automated Prospectus Parsing**
   - GPT-4 integration for investment_strategy extraction
   - underlying_asset_count parsing from disclosure documents

3. **Asset Manager API Partnerships**
   - Direct data feeds from top 5 issuers (Samsung, Mirae, KB, etc.)
   - Real-time actual_expense_ratio updates

---

## Cost-Benefit Analysis

| Field | Current | Achievable | Effort | Business Value |
|-------|---------|------------|--------|----------------|
| geographic_region | 66.8% | 82%+ | Low (1h) | High (diversification) |
| sector_theme | 27.8% | 67%+ | Low (2.5h) | High (rotation strategy) |
| ter | 0% | 100% | Medium (2-3d) | Medium (cost comparison) |
| tracking_error | 0% | 90%+ | Medium (3-5d) | Medium (quality assessment) |
| pension_eligible | 0% | Top 100 | Low (1d) | Low (niche use case) |
| underlying_asset_count | 0% | Limited | High (weeks) | Low (informational only) |
| actual_expense_ratio | 0% | Limited | High (weeks) | Low (expense_ratio sufficient) |
| investment_strategy | 0% | Limited | High (months) | Low (free text, limited analytics) |

---

## Implementation Priority

### Priority 1: IMMEDIATE (This Week)
✅ **Phase 1 Quick Wins** - 3.5 hours effort for 15-40% improvement

### Priority 2: NEXT SPRINT (This Month)
- FSS DART API integration (TER)
- Tracking error calculation engine

### Priority 3: BACKLOG (Future Enhancement)
- KRX API integration
- Prospectus parsing automation
- Asset manager partnerships

---

## Conclusion

### Current State Assessment
✅ **Strong Foundation**: 11/22 fields at ≥95% coverage (50% of schema)
⚠️ **Improvable**: 2 fields can reach 80%+ with minimal effort
❌ **API-Dependent**: 9 fields require external integrations (justified by complexity)

### Recommended Next Steps
1. Execute Phase 1 Quick Wins (3.5 hours) → Immediate 15-40% improvement
2. Evaluate FSS DART API for TER integration → Medium-term priority
3. Defer complex fields (investment_strategy, actual_expense_ratio) → ROI too low

### Success Metrics
- **Short-term goal**: 13/22 fields at ≥80% coverage (59% → 80% improvement)
- **Medium-term goal**: 15/22 fields at ≥80% coverage with API integrations
- **Long-term vision**: 18/22 fields at ≥90% coverage with full automation

---

**Report End**
