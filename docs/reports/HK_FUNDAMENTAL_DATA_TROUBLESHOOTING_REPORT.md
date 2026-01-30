# Hong Kong Fundamental Data Troubleshooting Report

**Date**: 2025-12-18
**Issue**: HK fundamentals showing as "未가용 (Not Available)" in MCP queries
**Status**: ✅ Root cause identified, fix ready to implement

---

## 🔍 Problem Summary

When querying HK stocks (e.g., ticker 2318 - Ping An Insurance) through the MCP server, fundamental data shows as "❌ 미가용 (Not Available)" even though:
- ✅ OHLCV price data is available (265 days)
- ✅ Technical indicators are available (RSI, MA, volume)
- ✅ Dividend data is available

## 🧪 Diagnostic Tests Performed

### Test 1: AkShare API Functionality ✅
```bash
# Test Result: SUCCESS
ticker = '02318'
df = ak.stock_financial_hk_analysis_indicator_em(symbol=ticker)
# Returns: 9 periods × 36 financial indicators
```

**Key Data Retrieved**:
- BASIC_EPS: 7.16
- BPS: 51.28
- ROE_AVG: 13.85%
- ROA: 1.03%
- DEBT_ASSET_RATIO: 89.93%
- REVENUE: 1,142,184,000,000 (1.14T HKD)
- NET_INCOME: 126,607,000,000 (126.6B HKD)

### Test 2: Ticker Format in Database ✅
```sql
SELECT ticker, region, name FROM tickers WHERE ticker LIKE '%2318%';
```

**Result**:
- Database stores: `2318.HK` (yfinance format)
- AkShare requires: `02318` (5-digit format with leading zeros)
- ✅ Parser `normalize_ticker_akshare()` handles this correctly

### Test 3: Data Collection Test ✅
```python
adapter.collect_fundamentals(tickers=['2318.HK'])
# Result: 1 ticker updated
```

**Data Stored in Database**:
```
ticker: 2318.HK
region: HK
date: 2024-12-31
period_type: QUARTERLY
revenue: 1,142,184,000,000
net_income: 126,607,000,000
data_source: akshare
```

### Test 4: Database Schema Analysis ⚠️
```sql
\d ticker_fundamentals
```

**Problem Identified**: Limited columns inserted!

---

## 🎯 Root Cause Analysis

### Issue: Field Mapping Mismatch

**HK Parser Generates** (36 indicators):
```python
fundamentals = {
    'ticker': '2318.HK',
    'region': 'HK',
    'date': '2024-12-31',
    'period_type': 'QUARTERLY',
    'data_source': 'akshare',
    # Financial ratios (CALCULATED by AkShare)
    'eps': 7.16,                    # ❌ NOT inserted
    'bps': 51.28,                   # ❌ NOT inserted
    'roe': 13.85,                   # ❌ NOT inserted
    'roa': 1.03,                    # ❌ NOT inserted
    'debt_ratio': 89.93,            # ❌ NOT inserted
    'current_ratio': None,          # ❌ NOT inserted
    'gross_margin': None,           # ❌ NOT inserted
    'net_margin': 12.85,            # ❌ NOT inserted
    'eps_ttm': 6.95,                # ❌ NOT inserted
    'roe_yearly': 13.85,            # ❌ NOT inserted
    'roic': 1.15,                   # ❌ NOT inserted
    # Raw accounting data (from financial statements)
    'revenue': 1142184000000,       # ✅ INSERTED
    'revenue_yoy': 11.19,           # ❌ NOT inserted
    'net_income': 126607000000,     # ✅ INSERTED
    'net_income_yoy': 47.79,        # ❌ NOT inserted
}
```

**DB Insert Method** (`db_manager_postgres.py:1560-1633`):
```python
def insert_fundamentals(self, fund_data: Dict) -> bool:
    INSERT INTO ticker_fundamentals (
        ticker, region, date, period_type,
        shares_outstanding, market_cap, close_price,
        per, pbr, psr, pcr, ev, ev_ebitda,
        dividend_yield, dividend_per_share,
        capital_stock, capital_surplus, retained_earnings, treasury_stock,
        other_comprehensive_income, non_controlling_interest,
        unappropriated_retained_earnings, legal_reserve,
        revenue,           # ✅ INSERTED
        net_income,        # ✅ INSERTED
        operating_profit, total_assets, total_equity,
        gross_profit, ebitda,
        data_source
    )
```

**Missing Fields** (13 critical ratios):
1. `eps` → Should map to `trailing_eps`
2. `eps_ttm` → Should map to `trailing_eps`
3. `bps` → Need to add column or calculate from equity
4. `roe` → Need to add column or calculate
5. `roa` → Need to add column or calculate
6. `debt_ratio` → Need to add column or calculate
7. `current_ratio` → Need to add column or calculate
8. `gross_margin` → Need to add column or calculate
9. `net_margin` → Need to add column or calculate
10. `roe_yearly` → Need to add column
11. `roic` → Need to add column
12. `revenue_yoy` → Need to add column or calculate
13. `net_income_yoy` → Need to add column or calculate

---

## 📊 Database Schema Analysis

### Existing Columns in `ticker_fundamentals`:
```sql
-- Valuation Ratios (columns exist)
trailing_eps          numeric(15,4)  -- ✅ Can store eps/eps_ttm
per, pbr, psr, pcr    numeric(10,2)  -- ✅ Existing
ev_ebitda             numeric(10,2)  -- ✅ Existing

-- Raw Accounting Data (columns exist)
revenue               numeric(20,2)  -- ✅ USED
net_income            numeric(20,2)  -- ✅ USED
total_equity          numeric(20,2)  -- ⚠️ NOT populated by HK adapter
total_assets          numeric(20,2)  -- ⚠️ NOT populated by HK adapter
total_liabilities     numeric(20,2)  -- ⚠️ NOT populated by HK adapter
current_assets        numeric(20,2)  -- ⚠️ NOT populated by HK adapter
current_liabilities   numeric(20,2)  -- ⚠️ NOT populated by HK adapter
gross_profit          numeric(20,2)  -- ⚠️ NOT populated by HK adapter

-- Missing Ratio Columns (need to be added)
❌ eps                numeric(10,2)  -- NOT EXISTS
❌ bps                numeric(10,2)  -- NOT EXISTS
❌ roe                numeric(10,4)  -- NOT EXISTS (exists as index calculation only)
❌ roa                numeric(10,4)  -- NOT EXISTS (exists as index calculation only)
❌ debt_ratio         numeric(10,4)  -- NOT EXISTS
❌ current_ratio      numeric(10,2)  -- NOT EXISTS
❌ gross_margin       numeric(10,4)  -- NOT EXISTS
❌ net_margin         numeric(10,4)  -- NOT EXISTS
❌ roic               numeric(10,4)  -- NOT EXISTS
❌ revenue_yoy        numeric(10,4)  -- NOT EXISTS
❌ net_income_yoy     numeric(10,4)  -- NOT EXISTS
```

---

## 🔧 Solution Options

### Option A: Add Missing Columns to Database Schema (RECOMMENDED)
**Pros**:
- ✅ Direct storage of pre-calculated ratios from AkShare
- ✅ No runtime calculation overhead
- ✅ Historical ratio data preserved
- ✅ Matches what other adapters (CN, JP) might need

**Cons**:
- ❌ Database migration required
- ❌ Schema change (but minimal risk)

**Implementation**:
```sql
-- Add missing ratio columns
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS eps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS bps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roe numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roa numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS debt_ratio numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS current_ratio numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS gross_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roic numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS revenue_yoy numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_income_yoy numeric(10,4);

-- Update insert_fundamentals() to include these columns
```

### Option B: Update HK Parser to Map to Existing Columns
**Pros**:
- ✅ No schema changes
- ✅ Faster implementation

**Cons**:
- ❌ Loss of AkShare pre-calculated ratios
- ❌ Need to populate raw balance sheet data (not available from AkShare HK API)
- ❌ Runtime calculation required

**Implementation**:
```python
# Map HK parser fields to existing DB columns
fundamentals = {
    'ticker': ticker,
    'region': 'HK',
    'date': formatted_date,
    'period_type': 'QUARTERLY',
    'data_source': 'akshare',
    'trailing_eps': row.get('BASIC_EPS'),     # eps → trailing_eps
    'revenue': row.get('OPERATE_INCOME'),
    'net_income': row.get('HOLDER_PROFIT'),
    # ⚠️ Cannot populate: total_equity, total_assets, current_assets, etc.
    #    because AkShare HK API only provides ratios, not raw balance sheet data
}
```

### Option C: Hybrid Approach (RECOMMENDED)
**Pros**:
- ✅ Best of both worlds
- ✅ Minimal schema changes
- ✅ Preserves AkShare ratio data

**Cons**:
- ❌ Slightly more complex

**Implementation**:
1. Add only the most critical ratio columns (eps, roe, roa, roic)
2. Map eps → trailing_eps
3. Store revenue, net_income (already done)
4. Calculate other ratios on-the-fly in MCP/factor calculators if needed

---

## 📝 Recommended Solution: Option A (Full Schema Enhancement)

### Migration Script
```sql
-- File: migrations/add_hk_fundamental_columns.sql
BEGIN;

-- Add pre-calculated ratio columns
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS eps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS bps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roe numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roa numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS debt_ratio numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS current_ratio numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS gross_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roic numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS revenue_yoy numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_income_yoy numeric(10,4);

-- Add indexes for commonly queried ratios
CREATE INDEX IF NOT EXISTS idx_fundamentals_eps ON ticker_fundamentals(eps) WHERE eps IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_roe_stored ON ticker_fundamentals(roe) WHERE roe IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_roa_stored ON ticker_fundamentals(roa) WHERE roa IS NOT NULL;

COMMIT;
```

### Updated `db_manager_postgres.py`
```python
def insert_fundamentals(self, fund_data: Dict) -> bool:
    """
    Insert or update fundamentals data

    Enhanced to support AkShare pre-calculated ratios (HK, CN, VN)
    """
    try:
        self._execute_query("""
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr, pcr, ev, ev_ebitda,
                dividend_yield, dividend_per_share,
                -- Raw accounting data
                revenue, net_income, operating_profit,
                total_assets, total_equity, gross_profit, ebitda,
                current_assets, current_liabilities, total_liabilities,
                -- Pre-calculated ratios (from AkShare/yfinance)
                eps, bps, roe, roa, roic,
                debt_ratio, current_ratio,
                gross_margin, net_margin,
                revenue_yoy, net_income_yoy,
                trailing_eps,  -- Map eps_ttm here
                -- Equity components
                capital_stock, capital_surplus, retained_earnings, treasury_stock,
                other_comprehensive_income, non_controlling_interest,
                unappropriated_retained_earnings, legal_reserve,
                created_at, data_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (ticker, region, date, period_type) DO UPDATE SET
                shares_outstanding = EXCLUDED.shares_outstanding,
                market_cap = EXCLUDED.market_cap,
                -- ... (all fields)
                eps = EXCLUDED.eps,
                bps = EXCLUDED.bps,
                roe = EXCLUDED.roe,
                roa = EXCLUDED.roa,
                roic = EXCLUDED.roic,
                debt_ratio = EXCLUDED.debt_ratio,
                current_ratio = EXCLUDED.current_ratio,
                gross_margin = EXCLUDED.gross_margin,
                net_margin = EXCLUDED.net_margin,
                revenue_yoy = EXCLUDED.revenue_yoy,
                net_income_yoy = EXCLUDED.net_income_yoy,
                trailing_eps = EXCLUDED.trailing_eps,
                data_source = EXCLUDED.data_source
        """, (
            fund_data['ticker'],
            fund_data['region'],
            fund_data['date'],
            fund_data['period_type'],
            fund_data.get('shares_outstanding'),
            fund_data.get('market_cap'),
            fund_data.get('close_price'),
            fund_data.get('per'),
            fund_data.get('pbr'),
            fund_data.get('psr'),
            fund_data.get('pcr'),
            fund_data.get('ev'),
            fund_data.get('ev_ebitda'),
            fund_data.get('dividend_yield'),
            fund_data.get('dividend_per_share'),
            # Raw accounting data
            fund_data.get('revenue'),
            fund_data.get('net_income'),
            fund_data.get('operating_profit'),
            fund_data.get('total_assets'),
            fund_data.get('total_equity'),
            fund_data.get('gross_profit'),
            fund_data.get('ebitda'),
            fund_data.get('current_assets'),
            fund_data.get('current_liabilities'),
            fund_data.get('total_liabilities'),
            # Pre-calculated ratios
            fund_data.get('eps'),
            fund_data.get('bps'),
            fund_data.get('roe'),
            fund_data.get('roa'),
            fund_data.get('roic'),
            fund_data.get('debt_ratio'),
            fund_data.get('current_ratio'),
            fund_data.get('gross_margin'),
            fund_data.get('net_margin'),
            fund_data.get('revenue_yoy'),
            fund_data.get('net_income_yoy'),
            fund_data.get('eps_ttm'),  # Map to trailing_eps
            # Equity components
            fund_data.get('capital_stock'),
            fund_data.get('capital_surplus'),
            fund_data.get('retained_earnings'),
            fund_data.get('treasury_stock'),
            fund_data.get('other_comprehensive_income'),
            fund_data.get('non_controlling_interest'),
            fund_data.get('unappropriated_retained_earnings'),
            fund_data.get('legal_reserve'),
            datetime.now(),
            fund_data.get('data_source')
        ), commit=True)
        return True
    except Exception as e:
        logger.error(f"❌ Failed to insert fundamentals for {fund_data.get('ticker')}: {e}")
        return False
```

### Updated HK Parser (Minor Adjustment)
```python
# hk_stock_parser.py - No changes needed!
# Parser already generates correct field names
# Just need to ensure eps_ttm also maps to trailing_eps in DB layer
```

---

## ✅ Implementation Checklist

### Phase 1: Database Migration
- [ ] Create migration script `migrations/add_hk_fundamental_columns.sql`
- [ ] Run migration on PostgreSQL database
- [ ] Verify columns added successfully
- [ ] Test with sample insert

### Phase 2: Update DB Manager
- [ ] Update `insert_fundamentals()` in `db_manager_postgres.py`
- [ ] Add all 11 new ratio columns to INSERT statement
- [ ] Add columns to ON CONFLICT UPDATE clause
- [ ] Add columns to VALUES parameters
- [ ] Test insert with HK sample data

### Phase 3: Testing
- [ ] Test HK fundamental collection for ticker 2318
- [ ] Verify all 36 indicators stored correctly
- [ ] Query MCP to confirm data availability
- [ ] Test with multiple HK tickers (10-20)
- [ ] Verify TTM calculation integration

### Phase 4: Documentation
- [ ] Update `CLAUDE.md` with HK fundamental data status
- [ ] Document new columns in schema docs
- [ ] Update API documentation for MCP tools

---

## 🧪 Test Plan

### Test 1: Database Migration
```sql
-- Verify columns added
\d ticker_fundamentals

-- Check for eps, bps, roe, roa, etc.
```

### Test 2: Data Collection
```python
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.market_adapters.hk_adapter import HKAdapter

db = PostgresDatabaseManager()
adapter = HKAdapter(db)

# Collect fundamentals for test ticker
result = adapter.collect_fundamentals(tickers=['2318.HK'])

# Verify data
fundamentals = db.execute_query('''
    SELECT ticker, region, date,
           eps, bps, roe, roa, roic,
           debt_ratio, gross_margin, net_margin,
           revenue, net_income, revenue_yoy, net_income_yoy
    FROM ticker_fundamentals
    WHERE ticker = '2318.HK' AND region = 'HK'
    ORDER BY date DESC
    LIMIT 1
''')

# Should show all fields populated
```

### Test 3: MCP Query
```bash
# Through Claude Desktop
"중국평안보험(2318.HK)의 재무제표를 조회해줘"

# Expected: All fundamental indicators should show as available
```

---

## 📈 Expected Outcome

After implementing the fix:

### Before (Current State) ❌:
```
재무제표(Fundamentals)      ❌ 미가용    DB에 데이터 없음
재무비율                    ❌ 미가용    재무제표 의존
TTM 지표                    ❌ 미가용    재무제표 의존
CAGR 분석                   ❌ 미가용    재무제표 의존
```

### After (Fixed State) ✅:
```
재무제표(Fundamentals)      ✅ 가용      2024.12.31 (AkShare)
- EPS: 7.16 HKD
- BPS: 51.28 HKD
- Revenue: 1,142B HKD
- Net Income: 126.6B HKD

재무비율                    ✅ 가용      36개 지표
- ROE: 13.85%
- ROA: 1.03%
- Debt Ratio: 89.93%
- Net Margin: 12.85%

TTM 지표                    ✅ 가용      EPS TTM: 6.95
CAGR 분석                   ✅ 가용      Revenue YoY: +11.19%
```

---

## 📋 Timeline Estimate

- **Phase 1 (Migration)**: 10 minutes
- **Phase 2 (Code Update)**: 30 minutes
- **Phase 3 (Testing)**: 20 minutes
- **Phase 4 (Documentation)**: 15 minutes
- **Total**: ~75 minutes (1.25 hours)

---

## 🚀 Next Steps

1. ✅ Create migration script
2. ✅ Update `db_manager_postgres.py`
3. ✅ Run migration and test
4. ✅ Collect HK fundamentals for 2318
5. ✅ Verify MCP query shows data
6. ✅ Document changes

---

**Report Generated**: 2025-12-18
**Author**: Claude Code (Troubleshooting Agent)
**Status**: Ready for implementation
