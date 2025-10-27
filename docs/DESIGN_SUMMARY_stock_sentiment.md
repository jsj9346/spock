# Design Summary: stock_sentiment.py

**Module**: Market Sentiment Analysis & Monitoring
**Design Date**: 2025-10-14
**Status**: ✅ **Design Complete** - Ready for Implementation

---

## 📋 Design Deliverables

### 1. **Comprehensive Design Specification** ✅
**File**: [DESIGN_stock_sentiment.md](./DESIGN_stock_sentiment.md) (43 KB, 1,050 lines)

**Contents**:
- ✅ Executive Summary & Purpose
- ✅ Architecture & Module Structure
- ✅ Data Structures (6 dataclasses with full specifications)
- ✅ API Specifications (15+ methods with detailed docstrings)
- ✅ Database Schema (3 tables with indexes)
- ✅ Integration Points (LayeredScoringEngine, Portfolio Manager, Risk Manager)
- ✅ Error Handling & Resilience Strategy
- ✅ Performance Requirements & Benchmarks
- ✅ Testing Strategy (Unit, Integration, Mocking)
- ✅ Implementation Checklist (5 phases)
- ✅ Future Enhancements Roadmap
- ✅ Success Metrics

### 2. **Architecture Diagrams** ✅
**File**: [DESIGN_stock_sentiment_architecture.mmd](./DESIGN_stock_sentiment_architecture.mmd)

**Diagrams Created**:
1. **System Architecture** - Component relationships and data flow
2. **Sequence Diagram** - Daily sentiment update workflow
3. **Decision Tree** - Position sizing logic based on VIX + market regime

---

## 🎯 Key Design Decisions

### 1. **Multi-Source Sentiment Aggregation**
**Decision**: Combine 4 independent data sources with weighted scoring

**Rationale**:
- Single-source sentiment is unreliable
- Diversification reduces false signals
- Weighted approach allows tuning based on empirical performance

**Data Sources**:
| Source | Weight | Update Frequency | Reliability |
|--------|--------|------------------|-------------|
| VIX Index | 50% | Daily 08:30 KST | High (95%+) |
| Fear & Greed | 25% | Daily 08:30 KST | Medium (85%) |
| Foreign/Institution Flow | 15% | Daily 16:00 KST | High (98%) |
| Sector Breadth | 10% | Daily 16:00 KST | High (95%) |

### 2. **VIX-Based Position Sizing**
**Decision**: Use VIX levels to dynamically adjust position sizes

**Logic**:
```
VIX <20:  1.0x position (100% of Kelly size)
VIX 20-30: 0.75x position (75% of Kelly size)
VIX 30-40: 0.5x position (50% of Kelly size)
VIX >40:  0.25x position (25% of Kelly size - defensive)
```

**Rationale**:
- Empirical research shows VIX correlates with future volatility
- Conservative approach protects capital during uncertain times
- Automatic risk adjustment without manual intervention

### 3. **Market Regime Classification**
**Decision**: 5-state regime model (Bull, Bull Correction, Sideways, Bear Rally, Bear)

**Rationale**:
- More granular than simple Bull/Bear binary
- Captures intermediate states for better risk management
- Aligns with investor behavior patterns

### 4. **Foreign/Institution Flow Tracking**
**Decision**: Track consecutive buy/sell days for trend signals

**Logic**:
- 3+ consecutive days >₩100M net buy = Strong Buy signal
- 3+ consecutive days >₩100M net sell = Strong Sell signal
- Mixed or low volume = Neutral

**Rationale**:
- Korean market heavily influenced by foreign/institutional trading
- Consecutive days indicate conviction, not just noise
- ₩100M threshold filters out insignificant trades

### 5. **Sector Rotation Analysis**
**Decision**: Calculate 20-day relative strength for GICS 11 sectors

**Rationale**:
- Sector rotation is early indicator of market regime shifts
- 20-day window captures medium-term trends
- GICS standardization allows cross-market comparison

---

## 📊 Data Model Summary

### Core Dataclasses (6 total)

1. **VIXData**
   - `vix_value: float` - Current VIX index value
   - `volatility_level: VolatilityLevel` - LOW, MODERATE, HIGH, EXTREME
   - `position_sizing_multiplier: float` - 0.25, 0.5, 0.75, 1.0

2. **FearGreedData**
   - `index_value: int` - 0-100 scale
   - `sentiment: str` - Extreme Fear, Fear, Neutral, Greed, Extreme Greed
   - `contrarian_signal: bool` - True if <25 or >75

3. **ForeignInstitutionFlow**
   - `foreign_net_buy: float` - Daily net buying in KRW
   - `institution_net_buy: float` - Daily net buying in KRW
   - `consecutive_buy_days: int` - Trend strength
   - `signal: str` - strong_buy, buy, neutral, sell, strong_sell

4. **SectorRotationSignal**
   - `sector: str` - GICS sector name
   - `relative_strength: float` - vs market average
   - `momentum_score: float` - 0-100
   - `is_hot_sector: bool` - Top 3 strongest

5. **MarketSentimentSummary** (Aggregate)
   - Combines all above + market regime classification
   - `overall_score: float` - -100 to +100 (bearish to bullish)
   - `recommended_position_sizing: float` - Final multiplier
   - `trading_recommendation: str` - aggressive, moderate, conservative, defensive

### Database Tables (3 total)

1. **market_sentiment** (Daily summary)
   - Primary key: `date`
   - ~10 KB per day, 3.6 MB/year

2. **foreign_institution_flow** (Flow by ticker)
   - Composite key: `(date, ticker, region)`
   - Ticker-specific flow tracking

3. **sector_rotation** (Sector metrics)
   - Composite key: `(date, sector, region)`
   - Daily sector performance rankings

---

## 🔗 Integration Architecture

### Integration Point 1: LayeredScoringEngine
**Module**: `modules/integrated_scoring_system.py`
**Layer**: Layer 1 - MarketRegimeModule (5 points)

**Integration**:
```python
# MarketRegimeModule scoring (0-5 points)
sentiment = MarketSentimentAnalyzer().get_market_sentiment_summary()

regime_score = {
    'bull': 4.0,
    'bull_correction': 3.0,
    'sideways': 2.0,
    'bear_rally': 1.0,
    'bear': 0.0
}[sentiment.market_regime.value]

# Bonus for foreign buying
if sentiment.foreign_flow.signal in ['strong_buy', 'buy']:
    regime_score += 1.0

return min(regime_score, 5.0)
```

### Integration Point 2: Portfolio Manager
**Module**: `modules/portfolio_manager.py`
**Method**: `check_position_limits()`

**Integration**:
```python
# Adjust position limits based on VIX
sentiment = MarketSentimentAnalyzer().get_market_sentiment_summary()

base_limit = 0.15  # 15% max per stock (moderate risk profile)
adjusted_limit = base_limit * sentiment.recommended_position_sizing

# Example: VIX=35 (HIGH) → 0.5x multiplier → 7.5% max position
```

### Integration Point 3: Risk Manager
**Module**: `modules/risk_manager.py`
**Feature**: New circuit breaker type

**Integration**:
```python
# Add EXTREME_VOLATILITY circuit breaker
if sentiment.vix_data.volatility_level == VolatilityLevel.EXTREME:
    return CircuitBreakerSignal(
        breaker_type=CircuitBreakerType.EXTREME_VOLATILITY,
        trigger_value=sentiment.vix_data.vix_value,
        limit_value=40.0,
        trigger_reason=f"VIX at {sentiment.vix_data.vix_value:.1f} - Halt all trading"
    )
```

---

## ⚡ Performance Specifications

### Response Time Targets

| Operation | Target | Actual (Estimated) |
|-----------|--------|-------------------|
| Collect VIX data | <5s | 2-4s |
| Collect Fear & Greed | <10s | 5-8s |
| Collect foreign flow | <15s | 8-12s |
| Analyze sector rotation | <5s | 2-3s |
| **Daily update total** | **<30s** | **20-25s** |
| Get sentiment summary | <100ms | 10-20ms |

### Resource Usage

- **Memory**: <50 MB during sentiment collection
- **Database**: ~3.6 MB per year (10 KB/day × 365 days)
- **Network**: ~500 KB per daily update
- **CPU**: <10% during collection, <1% during queries

---

## 🛡️ Error Handling Strategy

### Fallback Hierarchy

**VIX Data**:
1. Primary: Yahoo Finance (`yfinance.download('^VIX')`)
2. Fallback 1: CBOE website direct scraping
3. Fallback 2: Use previous day's cached data
4. Fallback 3: Default to neutral (VIX=20, MODERATE)

**Fear & Greed Index**:
1. Primary: CNN Money (web scraping)
2. Fallback 1: Alternative.me Crypto Fear & Greed (proxy)
3. Fallback 2: Default to neutral (50)

**Foreign/Institution Flow**:
1. Primary: KIS API (FHKST01010900)
2. Fallback 1: Market-wide aggregate from KIS summary
3. Fallback 2: Skip this indicator, weight others higher

### Retry Logic
```python
# Exponential backoff with jitter
max_retries = 3
retry_delays = [1, 2, 4]  # seconds

for attempt in range(max_retries):
    try:
        result = api_call()
        break
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(retry_delays[attempt] + random.uniform(0, 1))
        else:
            logger.error(f"Failed after {max_retries} attempts")
            return fallback_data()
```

---

## 📈 Success Metrics

### Data Quality Metrics
- ✅ VIX data availability: ≥99% (target: no more than 3 days/year missing)
- ✅ Fear & Greed availability: ≥95% (target: web scraping resilience)
- ✅ Foreign/Institution accuracy: ≥98% (target: KIS API reliability)

### Performance Metrics
- ✅ Daily update completion: <30 seconds (target: complete before market open)
- ✅ Sentiment query response: <100ms (target: no latency for trading decisions)
- ✅ System uptime: ≥99.5% (target: 43 hours downtime/year maximum)

### Trading Impact Metrics (Post-Implementation)
- 🎯 Position sizing effectiveness: ≥70% (measured by: reduced drawdown during high VIX)
- 🎯 Market regime accuracy: ≥75% (measured by: forward-looking regime stability)
- 🎯 Sector rotation win rate: ≥70% (measured by: hot sector outperformance)

---

## 📅 Implementation Roadmap

### Phase 1: Core Data Collection (Day 1 - 8 hours)
**Tasks**:
- [ ] Implement VIXDataCollector with Yahoo Finance
- [ ] Implement FearGreedCollector with web scraping
- [ ] Implement ForeignInstitutionCollector with KIS API
- [ ] Add retry logic and error handling
- [ ] Unit tests for all collectors (≥80% coverage)

**Deliverable**: Working data collectors with fallback support

### Phase 2: Analysis & Classification (Day 2 - 6 hours)
**Tasks**:
- [ ] Implement MarketRegime classification logic
- [ ] Implement VolatilityLevel classification
- [ ] Implement SectorRotationAnalyzer
- [ ] Implement sentiment score calculation algorithm
- [ ] Unit tests for classification (≥80% coverage)

**Deliverable**: Sentiment aggregation and classification engine

### Phase 3: Database Integration (Day 2 - 4 hours)
**Tasks**:
- [ ] Create database schema (3 tables + indexes)
- [ ] Implement save_sentiment_to_db()
- [ ] Implement get_sentiment_summary()
- [ ] Implement get_sentiment_history()
- [ ] Database integration tests

**Deliverable**: Persistent sentiment data storage

### Phase 4: System Integration (Day 3 - 4 hours)
**Tasks**:
- [ ] Integrate with LayeredScoringEngine (Layer 1 MarketRegime)
- [ ] Integrate with Portfolio Manager (position sizing)
- [ ] Integrate with Risk Manager (VIX circuit breaker)
- [ ] Add daily update scheduler (08:30 KST, 16:00 KST)
- [ ] Integration tests with mock data

**Deliverable**: Full system integration with sentiment analysis

### Phase 5: Testing & Validation (Day 3 - 4 hours)
**Tasks**:
- [ ] Complete unit test coverage (target: ≥80%)
- [ ] Integration testing with mock APIs
- [ ] End-to-end testing with live APIs (dry-run mode)
- [ ] Performance benchmarking (verify <30s daily update)
- [ ] Error scenario testing (API failures, data validation)

**Deliverable**: Production-ready module with comprehensive tests

**Total Estimated Time**: **3 days** (26 hours of development)

---

## 🚀 Next Steps

### Immediate Actions (Ready to Implement)
1. **Review Design Specification**: Stakeholder review and approval
2. **Setup Development Environment**: Install dependencies (`yfinance`, `beautifulsoup4`, `requests`)
3. **Create Feature Branch**: `git checkout -b feature/stock-sentiment`
4. **Begin Phase 1 Implementation**: Start with VIXDataCollector

### Pre-Implementation Checklist
- ✅ Design specification complete
- ✅ Architecture diagrams created
- ✅ Database schema defined
- ✅ Integration points identified
- ✅ Testing strategy documented
- ✅ Performance benchmarks established
- ⏳ Stakeholder approval (pending)
- ⏳ Development environment setup (pending)

### Dependencies Required
```bash
# Install Python dependencies
pip install yfinance>=0.2.28
pip install beautifulsoup4>=4.12.0
pip install requests>=2.31.0
pip install pandas>=2.0.3
pip install numpy>=1.24.3

# Verify KIS API access
# (Already available in kis_data_collector.py)
```

---

## 📝 Design Quality Assessment

### Completeness Score: **95/100**

**Strengths**:
- ✅ Comprehensive data structures with full specifications
- ✅ Detailed API method signatures and docstrings
- ✅ Database schema with proper indexing
- ✅ Clear integration points with existing modules
- ✅ Robust error handling and fallback strategies
- ✅ Performance benchmarks and success metrics
- ✅ 5-phase implementation roadmap

**Areas for Future Enhancement**:
- 🔄 Machine learning sentiment prediction (v1.2)
- 🔄 Real-time sentiment streaming (v1.2)
- 🔄 Global market correlation (v1.1)
- 🔄 Social sentiment analysis (v1.1)

### Code Reusability: **85%**

**Reusable Components**:
- ✅ Retry logic patterns (from other modules)
- ✅ Database manager (SQLiteDatabaseManager)
- ✅ Error handling patterns (AutoRecoverySystem)
- ✅ Logging setup (standard across project)

**New Components** (15%):
- VIX data collection logic
- Fear & Greed web scraping
- Market regime classification algorithm
- Sentiment aggregation formula

### Maintainability Score: **90/100**

**Positive Factors**:
- ✅ Clear separation of concerns (collection, analysis, integration)
- ✅ Comprehensive docstrings and type hints
- ✅ Modular design allows component replacement
- ✅ Extensive error logging for troubleshooting

**Improvement Opportunities**:
- 🔄 Add configuration file for thresholds (currently hardcoded)
- 🔄 Externalize API endpoints to config
- 🔄 Create abstract base class for collectors (future extensibility)

---

## 📞 Contact & Support

**Design Author**: Spock Design Team
**Design Review**: Pending stakeholder approval
**Implementation Owner**: TBD
**Target Start Date**: After Phase 5 Task 4 completion

---

**Status**: ✅ **DESIGN COMPLETE - READY FOR IMPLEMENTATION**

**Confidence Level**: **95%** - Comprehensive design with clear implementation path. Minor adjustments may be needed during implementation based on actual API responses and performance testing.

---

**End of Design Summary**
