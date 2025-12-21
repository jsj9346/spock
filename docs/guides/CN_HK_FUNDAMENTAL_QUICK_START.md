# CN/HK Fundamental Data Improvement - Quick Start Guide

**Version**: 1.0.0
**Date**: 2025-12-20
**Status**: Ready to Implement

---

## 🎯 TL;DR - What You Need to Know

### Problem
- Only **50%** of CN/HK stocks have fundamental data
- Main cause: System collects data for **ETFs and mutual funds** (which have no financial statements)
- Result: Wasted API calls, cluttered logs, low perceived success rate

### Solution
- **Phase 1**: Filter to stocks only (98%+ coverage) ⭐ **Start here**
- **Phase 2**: Prioritize large-cap stocks (99%+ for top tiers)
- **Phase 3**: Add yfinance ANNUAL fallback for HK (optional)
- **Phase 4**: Monitoring dashboard (nice to have)

### Impact
- Coverage: **50% → 98%+** (+48 percentage points)
- API efficiency: **50% fewer calls** (exclude non-stocks)
- Data quality: **95%+ field completeness**

---

## 🚀 Phase 1: Quick Win (2-3 hours implementation)

### What to Do

**Step 1**: Add asset type classification (30 min)

```python
# File: modules/market_adapters/cn_adapter.py
# Add this method to CNAdapter class

def _classify_asset_type(self, ticker_info: Dict) -> str:
    """Classify asset type from API response"""
    quote_type = ticker_info.get('quoteType', '').upper()

    # Direct classification
    if quote_type in ['ETF', 'MUTUALFUND', 'INDEX']:
        return quote_type

    # Name-based fallback
    name = ticker_info.get('name', '').upper()
    if any(kw in name for kw in ['ETF', '指数', '基金']):
        return 'ETF'

    # Code pattern (CN ETFs start with 51xxxx)
    ticker = ticker_info.get('ticker', '')
    if ticker.startswith('51') and len(ticker) == 6:
        return 'ETF'

    return 'STOCK'  # Default
```

**Step 2**: Update backfill to filter by asset type (30 min)

```python
# File: scripts/backfill_fundamentals_akshare.py
# Modify backfill_cn() method

def backfill_cn(self,
                mode: str = 'hybrid',
                asset_types: List[str] = ['STOCK']):  # NEW parameter

    # Get STOCKS only (exclude ETFs, funds, etc.)
    db_tickers = self.db.get_tickers(
        region='CN',
        asset_type=asset_types,  # NEW filter
        is_active=True
    )

    # Log excluded count
    all_tickers = self.db.get_tickers(region='CN', is_active=True)
    excluded = len(all_tickers) - len(db_tickers)
    logger.info(f"Excluded {excluded} non-stock tickers")

    # Rest of method unchanged...
```

**Step 3**: Database migration (10 min)

```sql
-- File: migrations/add_asset_type_index.sql

-- Add column if not exists
ALTER TABLE tickers
ADD COLUMN IF NOT EXISTS asset_type VARCHAR(20) DEFAULT NULL;

-- Create index for fast filtering
CREATE INDEX IF NOT EXISTS idx_tickers_region_asset_type_active
ON tickers (region, asset_type, is_active)
WHERE is_active = TRUE;
```

**Step 4**: Test (30 min)

```bash
# Test with 10 tickers
python3 scripts/backfill_fundamentals_akshare.py --region CN --limit 10

# Verify success rate improved
# Expected: 9-10/10 success (vs previous 5/10)
```

**Step 5**: Production run (1 hour)

```bash
# Full CN backfill (stocks only)
python3 scripts/backfill_fundamentals_akshare.py --region CN

# Full HK backfill (stocks only)
python3 scripts/backfill_fundamentals_akshare.py --region HK

# Expected result:
# - CN: ~2,000 stocks collected (vs previous ~2,400 all types)
# - HK: ~4,000 stocks collected (vs previous ~7,300 all types)
# - Success rate: 98%+ (vs previous 50%)
```

### Expected Results

| Metric | Before | After Phase 1 | Improvement |
|--------|--------|---------------|-------------|
| CN Tickers Attempted | 2,436 | ~2,000 | -18% (ETFs excluded) |
| CN Success Rate | 50% | 98%+ | +48%p |
| HK Tickers Attempted | 7,337 | ~4,000 | -45% (ETFs/funds excluded) |
| HK Success Rate | 50% | 98%+ | +48%p |
| API Calls | 9,773 | ~6,000 | -38% |
| Success Count | ~4,887 | ~5,880 | +20% |

---

## 📈 Phase 2: Quality Focus (2-3 days)

### What to Do

**Goal**: Ensure 99%+ coverage for large-cap stocks (most important for trading)

**Implementation**:
1. Create `scripts/backfill_fundamentals_prioritized.py`
2. Sort tickers by `market_cap DESC`
3. Collect large-cap first, then mid-cap, then small-cap
4. Generate coverage report by tier

**Usage**:

```bash
# Prioritized backfill (largest stocks first)
python3 scripts/backfill_fundamentals_prioritized.py \
  --region CN \
  --min-mcap 1000000000 \  # 10亿 CNY minimum
  --max-tickers 1000       # Top 1000 only

# Coverage report
python3 scripts/backfill_fundamentals_prioritized.py \
  --generate-report \
  --output docs/reports/CN_HK_COVERAGE_REPORT.md
```

**Expected Results**:

| Market Cap Tier | CN Coverage | HK Coverage |
|-----------------|-------------|-------------|
| MEGA (>100B) | 99.9% | 99.9% |
| LARGE (>10B) | 99.5% | 99.0% |
| MID (>1B) | 98.0% | 97.0% |
| SMALL (<1B) | 90.0% | 85.0% |
| **Overall** | **98%+** | **98%+** |

---

## 🔄 Phase 3: Fallback Enhancement (Optional, 2 days)

### yfinance ANNUAL for HK (Recommended)

**Problem**: HK stocks don't have QUARTERLY data on yfinance, but ANNUAL is available

**Solution**:

```python
# File: scripts/backfill_fundamentals_yfinance.py
# Add new method

def fetch_yfinance_annual_data(self, ticker: str, region: str):
    """Fetch ANNUAL balance sheet for HK stocks"""
    if region != 'HK':
        return None

    stock = yf.Ticker(f"{ticker.lstrip('0')}.HK")
    bs_annual = stock.balance_sheet  # Annual (not quarterly)

    # Parse and return...
```

**Usage**:

```bash
# Run yfinance ANNUAL backfill for HK
python3 scripts/backfill_fundamentals_yfinance.py \
  --region HK \
  --period ANNUAL
```

**Impact**: HK coverage 98% → 98.5% (+0.5%p)

### Naver Finance Integration (Optional)

**When to use**: Only if Phase 1-2 coverage < 95%

**Effort**: 2-3 days (web scraping complexity)

**ROI**: Low (only covers ~500 popular stocks, diminishing returns)

**Recommendation**: Skip unless specific requirement

---

## 📊 Phase 4: Monitoring (2 days)

### Coverage Dashboard

**What it shows**:
- Coverage % by region (CN, HK)
- Coverage % by market cap tier (MEGA, LARGE, MID, SMALL)
- Trend over time (last 30 days)
- Missing ticker list (top 100 by market cap)

**Implementation**:

```bash
# Generate interactive dashboard (Plotly HTML)
python3 scripts/generate_coverage_dashboard.py

# Output: reports/coverage_dashboard.html
# Open in browser to view
```

### Data Quality Validation

**What it checks**:
- Missing critical fields (EPS, revenue, total_assets)
- Anomalous values (negative assets, extreme ratios)
- Stale data (last update > 90 days)
- Data consistency (assets = liabilities + equity)

**Usage**:

```bash
# Run quality validation
python3 scripts/validate_fundamental_data_quality.py \
  --region CN \
  --output docs/reports/CN_QUALITY_REPORT.md

# Expected output:
# - ✅ EPS coverage: 98.5%
# - ✅ Revenue coverage: 97.2%
# - ✅ Total assets coverage: 95.8%
# - ⚠️ 5 records with negative assets (investigate)
# - ✅ 12 tickers with stale data (>90 days)
```

---

## 🎯 Recommended Implementation Path

### For Immediate Results (1 day)
✅ **Do Phase 1 only**
- Fastest impact (2-3 hours)
- Biggest improvement (50% → 98%)
- No complex dependencies

### For Production Quality (1 week)
✅ **Do Phase 1 + Phase 2**
- Ensures high-quality coverage for large-caps (99%+)
- Coverage reporting for monitoring
- Production-ready solution

### For Complete Solution (2 weeks)
✅ **Do Phase 1 + Phase 2 + Phase 4**
- All features except optional fallbacks
- Monitoring and quality assurance
- Long-term maintainability

### Only if Necessary
⚠️ **Phase 3 (Multi-source fallback)**
- Evaluate after Phase 1-2 completion
- Only if coverage gaps > 5%
- yfinance ANNUAL (HK) is quick win
- Naver Finance is time-consuming (skip unless required)

---

## 📋 Quick Reference: Files to Modify

### Phase 1: Asset Type Filtering

**New Files**:
- `migrations/add_asset_type_index.sql`

**Modified Files**:
- `modules/market_adapters/cn_adapter.py` (+20 lines: `_classify_asset_type()`)
- `modules/market_adapters/hk_adapter.py` (+20 lines: `_classify_asset_type()`)
- `scripts/backfill_fundamentals_akshare.py` (+10 lines: `asset_types` parameter)

### Phase 2: Prioritization

**New Files**:
- `scripts/backfill_fundamentals_prioritized.py` (~200 lines)
- `docs/reports/CN_HK_COVERAGE_REPORT.md` (generated)

### Phase 3: Fallback Enhancement

**Modified Files**:
- `scripts/backfill_fundamentals_yfinance.py` (+80 lines: `fetch_yfinance_annual_data()`)

**New Files** (optional):
- `modules/api_clients/naver_finance_api.py` (~150 lines, if needed)

### Phase 4: Monitoring

**New Files**:
- `scripts/generate_coverage_dashboard.py` (~150 lines)
- `scripts/validate_fundamental_data_quality.py` (~200 lines)
- `reports/coverage_dashboard.html` (generated)

---

## 🔍 Troubleshooting

### Issue: Still getting ~50% success rate after Phase 1

**Diagnosis**:
```bash
# Check if asset_type is populated
psql -d quant_platform -c "
SELECT asset_type, COUNT(*)
FROM tickers
WHERE region = 'CN' AND is_active = TRUE
GROUP BY asset_type;
"

# Expected: Mostly 'STOCK', some 'ETF', 'MUTUALFUND'
# If all NULL: asset_type classification not running
```

**Solution**: Ensure `_classify_asset_type()` is called during ticker collection

### Issue: Large-cap stocks missing data

**Diagnosis**:
```bash
# Find large-cap stocks without fundamentals
psql -d quant_platform -c "
SELECT t.ticker, t.name, t.market_cap
FROM tickers t
LEFT JOIN ticker_fundamentals tf ON t.ticker = tf.ticker AND t.region = tf.region
WHERE t.region = 'CN'
  AND t.asset_type = 'STOCK'
  AND t.market_cap > 10000000000
  AND tf.ticker IS NULL
ORDER BY t.market_cap DESC
LIMIT 10;
"
```

**Solution**: Re-run backfill for specific tickers, check API errors

### Issue: yfinance QUARTERLY not working for CN

**Diagnosis**: CN ticker format issue

**Solution**:
```python
# Correct format for yfinance
ticker = '600519'  # CN ticker
yf_ticker = f"{ticker}.SS"  # Shanghai (starts with 6)
# OR
yf_ticker = f"{ticker}.SZ"  # Shenzhen (starts with 0 or 3)
```

---

## 📞 Support & Resources

### Documentation
- **Full PRD**: `docs/architecture/CN_HK_FUNDAMENTAL_DATA_IMPROVEMENT_PRD.md`
- **Database Schema**: `docs/architecture/QUANT_DATABASE_SCHEMA.md`
- **Development Workflows**: `docs/guides/QUANT_DEVELOPMENT_WORKFLOWS.md`

### Code References
- **CN Adapter**: `modules/market_adapters/cn_adapter.py`
- **HK Adapter**: `modules/market_adapters/hk_adapter.py`
- **AkShare API**: `modules/api_clients/akshare_api.py`
- **Backfill Script**: `scripts/backfill_fundamentals_akshare.py`

### Recent Reports
- **Fix Complete**: `docs/reports/HK_CN_FUNDAMENTAL_FIX_COMPLETE.md`
- **Troubleshooting**: `docs/reports/HK_CN_FUNDAMENTAL_TROUBLESHOOTING_REPORT.md`

---

## ✅ Success Criteria

### Phase 1 Complete When:
- [ ] Asset type classification implemented (CN + HK)
- [ ] Backfill filters by `asset_type = 'STOCK'`
- [ ] CN success rate ≥ 95%
- [ ] HK success rate ≥ 95%
- [ ] ETFs/funds excluded from logs

### Phase 2 Complete When:
- [ ] Market cap sorting working
- [ ] MEGA tier coverage ≥ 99%
- [ ] LARGE tier coverage ≥ 99%
- [ ] Coverage report generated successfully

### Phase 3 Complete When:
- [ ] yfinance ANNUAL working for HK
- [ ] Total HK coverage ≥ 98%
- [ ] (Optional) Naver Finance integrated if gap > 5%

### Phase 4 Complete When:
- [ ] Coverage dashboard operational
- [ ] Data quality validation passes
- [ ] <5 high-priority issues identified
- [ ] Documentation complete

---

**Ready to Start?** → Begin with **Phase 1** (2-3 hours implementation)

**Questions?** → See full PRD: `docs/architecture/CN_HK_FUNDAMENTAL_DATA_IMPROVEMENT_PRD.md`

**Version**: 1.0.0
**Last Updated**: 2025-12-20

---

**End of Quick Start Guide**
