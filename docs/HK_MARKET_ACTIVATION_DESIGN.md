# 🇭🇰 Hong Kong Market Activation Design

**Project**: Spock Quant Platform
**Target**: Enable production-grade HK market support
**Date**: 2025-11-12
**Status**: Design Phase
**Priority**: Medium (after KR/US stabilization)

---

## Executive Summary

### Objective
Enable **Hong Kong (HK) stock market** as a **production-supported region** in Spock platform, expanding from current KR/US-only support to include HKEX (Hong Kong Exchange).

### Current State Analysis

**✅ Strengths**:
- HK adapter infrastructure exists (`modules/market_adapters/hk_adapter.py`)
- 2,723 tickers in database (0001.HK ~ 9999.HK)
- 111,584 OHLCV records (614 active tickers)
- **Excellent data quality**: Top 20 tickers show 0 invalid records
- 94.5% fundamental data coverage (2,573/2,723 tickers)
- 1-year historical data (2024-11-12 ~ 2025-11-11)

**❌ Gaps**:
- **22.5% OHLCV coverage** (614/2,723 tickers) - **Critical**
- **0 ETF data** - Missing asset class
- **No backtesting validation** - Production blocker
- **MCP server unsupported** - Integration gap
- **No data quality framework** - Risk management gap

### Success Criteria

| Metric | Target | Current | Gap |
|--------|--------|---------|-----|
| **OHLCV Coverage** | ≥90% (2,451 tickers) | 22.5% (614 tickers) | **+1,837 tickers** |
| **Data Quality** | <0.1% invalid records | 0% (top 20) | ✅ Meeting target |
| **Backtesting Engine** | >95% accuracy | Not tested | ❌ Critical gap |
| **MCP Integration** | Full support | Not supported | ❌ Blocking issue |
| **ETF Coverage** | ≥50 major ETFs | 0 ETFs | ❌ Missing data |
| **Fundamental Data** | ≥90% coverage | 94.5% | ✅ Exceeding target |

---

## Phase 1: Data Quality & Coverage Enhancement (Week 1-2)

### 1.1 OHLCV Backfill Strategy

**Problem**: Only 614/2,723 tickers (22.5%) have OHLCV data

**Root Cause Analysis**:
```sql
-- Find tickers without OHLCV data
SELECT
    t.ticker,
    t.name,
    sd.market_cap,
    sd.sector
FROM tickers t
LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
LEFT JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
WHERE t.region = 'HK' AND o.ticker IS NULL
ORDER BY sd.market_cap DESC NULLS LAST
LIMIT 20;
```

**Solution**: Prioritized backfill strategy

**Tier 1: Hang Seng Index Constituents** (Target: 100% coverage)
- Priority: Critical
- Count: ~80 constituents
- Backfill period: 5 years (2020-01-01 ~ present)
- Data source: yfinance API
- Estimated time: 2 hours

**Tier 2: High Market Cap Stocks** (Market cap >$1B)
- Priority: High
- Count: ~500 tickers
- Backfill period: 3 years (2022-01-01 ~ present)
- Data source: yfinance API
- Estimated time: 12 hours

**Tier 3: Mid-Cap Stocks** (Market cap $100M-$1B)
- Priority: Medium
- Count: ~800 tickers
- Backfill period: 2 years (2023-01-01 ~ present)
- Data source: yfinance API
- Estimated time: 20 hours

**Tier 4: Small-Cap & Remaining** (Market cap <$100M)
- Priority: Low
- Count: ~1,343 tickers
- Backfill period: 1 year (2024-01-01 ~ present)
- Data source: yfinance API (best effort)
- Estimated time: 30 hours

**Implementation**:
```bash
# scripts/backfill_hk_ohlcv_tiered.py
python3 scripts/backfill_hk_ohlcv_tiered.py \
  --tier 1 \
  --start-date 2020-01-01 \
  --end-date 2025-11-12 \
  --rate-limit 1.0 \
  --validate-quality
```

### 1.2 Data Quality Validation Framework

**Quality Gates** (same as KR/US markets):
1. **Completeness**: No missing dates (holidays excluded)
2. **Validity**: All OHLCV values >0, High ≥ Low
3. **Consistency**: No extreme price jumps (>50% single day)
4. **Accuracy**: Volume >0 for active trading days

**Implementation**:
```python
# modules/data_quality/hk_validator.py
class HKDataQualityValidator:
    """
    HK market data quality validation

    Checks:
    - HKEX holiday calendar compliance
    - Price anomaly detection (>50% jumps)
    - Volume validation (exclude half-day sessions)
    - Corporate action verification (splits, dividends)
    """

    def validate_ohlcv(self, ticker: str, df: pd.DataFrame) -> Dict:
        """Run comprehensive OHLCV validation"""
        return {
            'completeness_score': self._check_completeness(df),
            'validity_score': self._check_validity(df),
            'consistency_score': self._check_consistency(df),
            'anomalies': self._detect_anomalies(ticker, df)
        }
```

**Quality Report**:
```sql
-- scripts/generate_hk_quality_report.sql
SELECT
    ticker,
    COUNT(*) as total_days,
    COUNT(CASE WHEN close IS NULL THEN 1 END) as null_close,
    COUNT(CASE WHEN volume = 0 THEN 1 END) as zero_volume,
    MAX(close/LAG(close) OVER (ORDER BY date)) as max_price_jump,
    MIN(close/LAG(close) OVER (ORDER BY date)) as max_price_drop
FROM ohlcv_data
WHERE region = 'HK'
GROUP BY ticker
HAVING COUNT(*) >= 100  -- At least 100 trading days
ORDER BY max_price_jump DESC;
```

### 1.3 ETF Data Collection

**Target**: 50+ major HKEX ETFs

**Priority ETFs**:
- **Hang Seng Index ETFs**: 2800.HK (Tracker Fund), 3115.HK (iShares HSI)
- **China A-Share ETFs**: 2822.HK, 2823.HK, 2828.HK
- **Tech ETFs**: 3067.HK (HSTECH), 3033.HK (CSOP HSTECH)
- **Sector ETFs**: Healthcare, Financials, Consumer

**Data Source**: yfinance + HKEX official website

**Implementation**:
```bash
# scripts/collect_hk_etfs.py
python3 scripts/collect_hk_etfs.py \
  --source yfinance \
  --start-date 2020-01-01 \
  --validate-nav
```

---

## Phase 2: Backtesting Engine Validation (Week 3)

### 2.1 Test Strategy

**Validation Framework** (same as KR/US):
1. **Unit Tests**: Data provider, signal generators
2. **Integration Tests**: Full backtest pipeline
3. **Regression Tests**: Known strategy results
4. **Performance Tests**: 5-year simulation <30s

**Test Strategies**:
- **Momentum**: 12-month price momentum
- **Value**: P/E, P/B ratio screening
- **Combined**: Multi-factor scoring

**Success Criteria**:
- ✅ All unit tests pass (>90% coverage)
- ✅ 5-year backtest completes <30s (custom engine)
- ✅ 5-year backtest completes <1s (vectorbt)
- ✅ Sharpe ratio >1.0 on test strategy
- ✅ >100 trades for statistical significance

### 2.2 Implementation

**Test Data Preparation**:
```python
# tests/fixtures/hk_backtest_data.py
def setup_hk_test_data():
    """
    Prepare HK backtest test data

    Test Universe:
    - 50 HSI constituents
    - 5 years historical data (2020-2025)
    - Validated OHLCV quality
    """
    tickers = [
        '0700.HK', '9988.HK', '0941.HK', '1299.HK', '0388.HK',
        '0005.HK', '3690.HK', '2318.HK', '1398.HK', '0011.HK'
        # ... 40 more
    ]

    for ticker in tickers:
        load_ohlcv(ticker, start='2020-01-01', end='2025-11-12')
```

**Backtest Validation**:
```bash
# tests/backtesting/test_hk_engine.py
pytest tests/backtesting/test_hk_engine.py \
  --cov=modules/backtesting \
  --cov-report=html \
  -v
```

---

## Phase 3: MCP Server Integration (Week 4)

### 3.1 MCP Server Updates

**Current Limitation**:
```python
# mcp_server/utils/validators.py:63
{"provided_region": region, "allowed_regions": ["KR", "US"]}
```

**Required Changes**:

**1. Update Validators**:
```python
# mcp_server/utils/validators.py
ALLOWED_REGIONS = ["KR", "US", "HK"]  # Add HK

def validate_region(region: str) -> None:
    if region not in ALLOWED_REGIONS:
        raise ValidationError(
            f"Unsupported region: {region}",
            {"provided_region": region, "allowed_regions": ALLOWED_REGIONS}
        )
```

**2. Update Data Adapter**:
```python
# mcp_server/adapters/data_adapter.py
def query_ohlcv_data(self, tickers: List[str], region: str, ...):
    # Add HK-specific logic
    if region == 'HK':
        # Use HKAdapter for data fetching
        adapter = HKAdapter(self.db_manager)
        return adapter.get_ohlcv_batch(tickers, start_date, end_date)
```

**3. Update Screening Tool**:
```python
# mcp_server/tools/screening_tool.py
def screen_stocks(region: str, filters: Dict, ...):
    # Add HK market screening support
    if region == 'HK':
        return self.screening_adapter.screen_hk_stocks(filters)
```

### 3.2 Testing

**MCP Integration Tests**:
```bash
# tests/mcp_server/test_hk_integration.py
pytest tests/mcp_server/test_hk_integration.py -v

# Test cases:
# 1. query_ohlcv_data with region='HK'
# 2. screen_stocks with HK filters
# 3. run_backtest with HK universe
# 4. get_technical_indicators for HK tickers
```

---

## Phase 4: Production Deployment (Week 5)

### 4.1 Deployment Checklist

**Pre-Deployment**:
- [ ] All Phase 1-3 tasks completed
- [ ] 90%+ OHLCV coverage achieved
- [ ] Backtesting engine validated (>95% accuracy)
- [ ] MCP server integration tested
- [ ] Data quality monitoring enabled
- [ ] Documentation updated

**Deployment Steps**:
1. **Database Migration**: Update production database with HK data
2. **MCP Server Restart**: Deploy updated MCP server with HK support
3. **Monitoring Setup**: Enable HK market metrics in Grafana
4. **Smoke Testing**: Run production validation suite

**Rollback Plan**:
- Revert MCP server to previous version
- Disable HK region in `ALLOWED_REGIONS`
- Maintain HK data in database (read-only)

### 4.2 Monitoring

**Key Metrics**:
- **Data Freshness**: Last update timestamp per ticker
- **API Success Rate**: yfinance API call success (target: >95%)
- **Backtest Performance**: Daily validation backtest (target: <30s)
- **MCP Query Latency**: HK data queries (target: <500ms p95)

**Alerts**:
- 🚨 **Critical**: Data collection failure >24 hours
- ⚠️ **Warning**: OHLCV coverage drops below 85%
- ℹ️ **Info**: Daily data quality report

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **yfinance API rate limits** | High | High | Implement exponential backoff, use multiple API keys |
| **Incomplete OHLCV data** | Medium | High | Prioritized backfill (HSI first), fallback to manual collection |
| **Backtesting failures** | Low | Critical | Comprehensive testing, phased rollout |
| **MCP integration bugs** | Medium | Medium | Extensive testing, feature flags for gradual rollout |
| **Data quality issues** | Medium | High | Automated validation, manual review of top 100 tickers |

---

## Resource Requirements

### Time Estimate

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| **Phase 1** | Data backfill + quality validation | 64 hours (8 days) |
| **Phase 2** | Backtesting validation | 24 hours (3 days) |
| **Phase 3** | MCP server integration | 16 hours (2 days) |
| **Phase 4** | Production deployment | 8 hours (1 day) |
| **Total** | | **112 hours (14 days)** |

### Infrastructure

**Database Storage**:
- Current: 111,584 OHLCV records
- Target: 1,500,000 OHLCV records (2,451 tickers × 3 years × 250 days)
- Additional storage: ~500 MB

**API Rate Limits**:
- yfinance: 2,000 requests/hour (free tier)
- Estimated backfill time: ~64 hours (with rate limiting)

---

## Success Metrics

**Phase 1 Completion**:
- ✅ OHLCV coverage ≥90% (2,451/2,723 tickers)
- ✅ Data quality score ≥95% (invalid records <5%)
- ✅ ETF coverage ≥50 ETFs
- ✅ Quality validation framework operational

**Phase 2 Completion**:
- ✅ All backtesting unit tests pass (>90% coverage)
- ✅ 5-year backtest <30s (custom engine)
- ✅ 5-year backtest <1s (vectorbt)
- ✅ Test strategy Sharpe >1.0

**Phase 3 Completion**:
- ✅ MCP server supports HK region
- ✅ All MCP tools work with HK data
- ✅ Integration tests pass (>95% success rate)

**Phase 4 Completion**:
- ✅ Production deployment successful
- ✅ Monitoring dashboards operational
- ✅ Documentation updated
- ✅ User guide published

---

## Next Steps

### Immediate Actions (Week 1)

1. **Create backfill script**: `scripts/backfill_hk_ohlcv_tiered.py`
2. **Set up quality validator**: `modules/data_quality/hk_validator.py`
3. **Run Tier 1 backfill**: HSI constituents (80 tickers, 5 years)
4. **Generate quality report**: Initial data quality assessment

### Ready to Proceed?

Execute the following command to begin:

```bash
# Start HK market activation
python3 scripts/activate_hk_market.py --phase 1 --dry-run
```

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-12
**Author**: Spock Platform Team
**Review Status**: ✅ Design Complete, Ready for Implementation
