# Vietnam Market Data Source Strategy

**Date**: 2025-11-14
**Status**: Planning Phase
**Priority**: Medium (Phase 2 enhancement)

---

## Current Situation

### Coverage Statistics
| Metric | Value |
|--------|-------|
| Total VN Tickers | 557 |
| yfinance Supported | 310 (55.7%) |
| yfinance Unsupported | 247 (44.3%) |
| Actual Coverage (with OHLCV) | 309/310 (99.7% of supported) |

### Root Cause
- **yfinance API limitation**: 247 Vietnamese stocks are not available in yfinance database
- **Current coverage**: 55.5% overall (below 80% quality threshold)
- **Supported stocks**: Near-perfect coverage (99.7%) for available tickers

### Impact Assessment
- **High**: Missing nearly half of VN market (247 stocks)
- **Medium**: May exclude important mid-cap and small-cap stocks
- **Low**: Major stocks (VN30 index) likely covered by yfinance

---

## Alternative Data Sources

### Option 1: Official Exchange APIs (Recommended ⭐)

#### HOSE/HNX Direct APIs
**Description**: Official APIs from Ho Chi Minh Stock Exchange (HOSE) and Hanoi Stock Exchange (HNX)

**Pros**:
- ✅ Most reliable and comprehensive data source
- ✅ 100% coverage for all listed stocks
- ✅ Real-time and historical data
- ✅ Official source - no third-party dependency

**Cons**:
- ❌ May require registration and API key
- ❌ Documentation may be limited or in Vietnamese
- ❌ Potentially higher latency than global providers

**Implementation Effort**: High (2-3 weeks)
- Exchange API integration
- Authentication handling
- Data format parsing (likely proprietary format)
- Error handling and retry logic

**Links**:
- HOSE: https://www.hsx.vn/
- HNX: https://www.hnx.vn/

---

### Option 2: Vietnamese Broker APIs

#### SSI Securities API
**Description**: API provided by SSI Securities Corporation (major Vietnamese broker)

**Pros**:
- ✅ Comprehensive Vietnam market coverage
- ✅ Well-documented API
- ✅ Includes fundamental data and market indices
- ✅ Free tier available

**Cons**:
- ❌ Requires registration
- ❌ Rate limits on free tier
- ❌ Dependency on third-party broker

**Implementation Effort**: Medium (1-2 weeks)
- Similar to KIS API adapter pattern
- RESTful API integration
- Standard OHLCV data normalization

**Links**:
- SSI API: https://api.ssi.com.vn/

#### VND Direct API
**Description**: Financial data provider specializing in Vietnam market

**Pros**:
- ✅ Vietnam market specialist
- ✅ Good data coverage
- ✅ Modern API design

**Cons**:
- ❌ May require paid subscription
- ❌ Less established than SSI

**Implementation Effort**: Medium (1-2 weeks)

---

### Option 3: Multi-Market Data Libraries

#### AkShare (Python Library)
**Description**: Open-source Python library with multi-market support including Vietnam

**Pros**:
- ✅ Free and open-source
- ✅ Python-native (easy integration)
- ✅ Supports multiple Asian markets (CN, HK, VN, etc.)
- ✅ Active community maintenance

**Cons**:
- ❌ May have reliability issues
- ❌ Data quality not guaranteed
- ❌ Scraping-based (may break with website changes)

**Implementation Effort**: Low (3-5 days)
- Simple pip install
- Wrapper adapter for our data model
- Error handling for unreliable data

**Links**:
- GitHub: https://github.com/akfamily/akshare
- Documentation: https://akshare.akfamily.xyz/

---

## Recommended Approach: Hybrid Strategy

### Phase 1: Quick Win (Priority: High) 🎯
**Action**: Implement AkShare for VN market
**Timeline**: 1 week
**Expected Coverage**: 80-90% (additional 150-200 tickers)

**Rationale**:
1. Fast implementation (3-5 days development + 2 days testing)
2. Immediate improvement from 55.5% to ~80% coverage
3. Low risk - can revert to yfinance if issues arise
4. Python-native - minimal infrastructure changes

**Implementation Steps**:
```python
# 1. Install AkShare
pip install akshare

# 2. Create VN adapter (similar to KR adapter)
class VNAkShareAdapter:
    def get_ohlcv(self, ticker, start_date, end_date):
        # Use akshare.stock_vn_spot() or similar
        pass

# 3. Update orchestrator to use VN adapter for unsupported yfinance tickers
if region == 'VN' and ticker in yfinance_unavailable:
    use VNAkShareAdapter
else:
    use YFinanceAPI
```

### Phase 2: Production-Grade (Priority: Medium) 📋
**Action**: Implement SSI Securities API or HOSE/HNX Direct API
**Timeline**: 3-4 weeks (after Phase 1 proves value)
**Expected Coverage**: 100%

**Rationale**:
1. More reliable than scraping-based solutions
2. Official data source with SLA guarantees
3. Future-proof for production deployment
4. Better data quality and timeliness

**Implementation Steps**:
1. Research SSI API vs HOSE/HNX capabilities
2. Register for API access and obtain credentials
3. Develop VN market adapter following KIS adapter pattern
4. Implement authentication, rate limiting, error handling
5. Add to orchestrator's market adapter registry
6. Comprehensive testing with historical and real-time data

---

## Implementation Plan

### Week 1: AkShare Integration (Quick Win)
**Tasks**:
- [x] Research AkShare VN market support
- [ ] Install and test AkShare library
- [ ] Create `VNAkShareAdapter` class
- [ ] Integrate with `spock_refresh.py` pipeline
- [ ] Test with 10 sample yfinance-unavailable tickers
- [ ] Run full backfill for 247 unsupported tickers
- [ ] Validate data quality (compare with yfinance for overlap)

**Success Criteria**:
- ≥80% VN market coverage (450+ tickers with OHLCV)
- Data quality validation passes for AkShare-sourced data
- No regression in existing yfinance-sourced tickers

### Week 2-4: Production API Research (Optional)
**Tasks**:
- [ ] Evaluate SSI API capabilities and registration process
- [ ] Compare HOSE/HNX direct API vs SSI API
- [ ] Document API endpoints, authentication, rate limits
- [ ] Cost analysis (if paid tier required)
- [ ] Create implementation roadmap

**Decision Point**: Go/No-Go based on:
- AkShare reliability in production
- SSI/HOSE API availability and cost
- VN market importance to trading strategy

---

## Risk Assessment

### AkShare Risks (Phase 1)
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Library maintenance stops | Low | Medium | Monitor GitHub activity, have fallback plan |
| Data quality issues | Medium | Medium | Validate against yfinance overlap, implement quality checks |
| API breaking changes | Medium | Low | Pin library version, test before upgrades |
| Missing tickers | Low | Low | Document coverage gaps, use yfinance as primary |

### SSI/HOSE API Risks (Phase 2)
| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Registration delays | Medium | Low | Start early, have timeline buffer |
| Unexpected costs | Low | Medium | Research pricing upfront, budget approval |
| API reliability | Low | High | Implement robust error handling, caching |
| Rate limit constraints | Medium | Medium | Efficient batching, request optimization |

---

## Testing Strategy

### Unit Tests
```python
def test_akshare_vn_adapter():
    """Test VN AkShare adapter OHLCV retrieval"""
    adapter = VNAkShareAdapter()

    # Test single ticker
    data = adapter.get_ohlcv('VNM', '2024-01-01', '2024-12-31')
    assert len(data) > 200  # ~250 trading days
    assert all(col in data.columns for col in ['open', 'high', 'low', 'close', 'volume'])

    # Test yfinance-unavailable ticker
    data = adapter.get_ohlcv('AAA', '2024-01-01', '2024-12-31')
    assert data is not None
```

### Integration Tests
```python
def test_vn_hybrid_collection():
    """Test hybrid yfinance + AkShare collection"""
    orchestrator = DatabaseUpdateOrchestrator(db)

    # Run OHLCV collection for VN
    result = orchestrator.run_pipeline(
        regions=['VN'],
        steps=['ohlcv'],
        dry_run=False
    )

    # Verify coverage improved
    validator = DataQualityValidator(db)
    vn_result = validator._validate_region('VN')

    assert vn_result['ohlcv_coverage'] >= 0.80  # 80% threshold
```

### Data Quality Validation
```python
def test_akshare_vs_yfinance_overlap():
    """Validate AkShare data quality against yfinance for overlap tickers"""
    # Get tickers supported by both sources
    overlap_tickers = ['VNM.VN', 'FPT.VN']  # Major stocks

    for ticker in overlap_tickers:
        yf_data = yfinance.download(ticker)
        ak_data = akshare.stock_vn_spot(ticker)

        # Compare closing prices (allow 1% variance)
        price_diff = abs(yf_data['Close'] - ak_data['close']) / yf_data['Close']
        assert price_diff.mean() < 0.01  # <1% average difference
```

---

## Success Metrics

### Phase 1 (AkShare) - Target: 80% Coverage
| Metric | Baseline | Target | Stretch Goal |
|--------|----------|--------|--------------|
| VN OHLCV Coverage | 55.5% | 80% | 90% |
| Additional Tickers | 0 | 150 | 200 |
| Data Quality | N/A | >95% accuracy | >98% accuracy |
| Collection Time | N/A | <10 min/day | <5 min/day |

### Phase 2 (SSI/HOSE) - Target: 100% Coverage
| Metric | Baseline | Target | Stretch Goal |
|--------|----------|--------|--------------|
| VN OHLCV Coverage | 80% | 100% | 100% |
| API Reliability | N/A | >99% uptime | >99.9% uptime |
| Data Latency | N/A | <15 min | <5 min |
| Cost per Month | $0 | <$50 | $0 (free tier) |

---

## Next Steps

### Immediate Actions (This Week)
1. [ ] Install AkShare and test VN market support
2. [ ] Create proof-of-concept for 10 sample tickers
3. [ ] Document AkShare VN API usage patterns

### Short-term (Next 2 Weeks)
4. [ ] Implement `VNAkShareAdapter` class
5. [ ] Integrate with `spock_refresh.py` orchestrator
6. [ ] Run full backfill for 247 yfinance-unavailable tickers
7. [ ] Validate data quality and coverage metrics

### Medium-term (1-2 Months)
8. [ ] Evaluate production API options (SSI vs HOSE/HNX)
9. [ ] Make Phase 2 go/no-go decision
10. [ ] Document VN market data strategy in main project docs

---

## References

### External Resources
- **AkShare**: https://github.com/akfamily/akshare
- **SSI API**: https://api.ssi.com.vn/
- **HOSE**: https://www.hsx.vn/
- **HNX**: https://www.hnx.vn/
- **yfinance**: https://github.com/ranaroussi/yfinance

### Internal Documentation
- [TROUBLESHOOTING_REPORT_20251114.md](TROUBLESHOOTING_REPORT_20251114.md) - Full troubleshooting analysis
- [QUANT_DEVELOPMENT_WORKFLOWS.md](QUANT_DEVELOPMENT_WORKFLOWS.md) - Data collection workflows
- [modules/market_adapters/kr_adapter.py](../modules/market_adapters/kr_adapter.py) - Reference adapter pattern

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Next Review**: After Phase 1 completion (1 week)
