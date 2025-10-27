# Fundamental Data Collection Module - Implementation Plan

**Date**: 2025-10-17
**Status**: Design Phase
**Priority**: Medium (Future Enhancement)

## 1. Executive Summary

This document outlines the implementation plan for adding fundamental data collection capabilities to the Spock trading system. The module will enable **optional** fundamental data collection for stocks that pass Stage 2 technical analysis filters, supporting future backtesting and user-driven fundamental information display.

### Key Design Principles
- **Non-Intrusive**: Does not affect existing 100% technical analysis trading logic
- **Optional Collection**: User-configurable, on-demand collection only
- **Phased Approach**: Start with Phase 1 schema (ticker_fundamentals table), expand to Phase 2 if needed
- **API Cost Optimization**: Minimize API calls through intelligent caching and selective collection
- **Multi-Region Support**: Unified approach for KR, US, CN, HK, JP, VN markets

## 2. Data Source Analysis

### 2.1 Available APIs

| API | Markets | Fundamental Data | Cost | Rate Limit | Recommendation |
|-----|---------|------------------|------|------------|----------------|
| **yfinance** | Global (US, HK, CN, JP, VN) | ✅ Rich (40+ fields) | ✅ Free | 1 req/sec | **PRIMARY** |
| **DART API** | Korea only | ✅ Detailed statements | ✅ Free | 1,000 req/day | **PRIMARY (KR)** |
| **KIS API** | KR + Global | ❌ No fundamentals | Free | 20 req/sec | N/A |
| **Polygon.io** | US only | ✅ Professional | ❌ Paid ($99+/mo) | API tier-based | ❌ Expensive |

### 2.2 yfinance Fundamental Fields (40+ Available)

**Valuation Metrics**:
- `priceToBook`, `priceToSalesTrailing12Months`, `enterpriseToRevenue`, `enterpriseToEbitda`
- `pegRatio`, `trailingPE`, `forwardPE`

**Profitability Metrics**:
- `returnOnEquity`, `returnOnAssets`, `profitMargins`
- `grossMargins`, `ebitdaMargins`, `operatingMargins`

**Financial Health**:
- `totalCash`, `totalCashPerShare`, `totalDebt`, `debtToEquity`
- `freeCashflow`, `operatingCashflow`

**Growth Metrics**:
- `earningsGrowth`, `revenueGrowth`, `earningsQuarterlyGrowth`

**Dividends**:
- `dividendRate`, `dividendYield`, `trailingAnnualDividendRate`
- `fiveYearAvgDividendYield`, `exDividendDate`

**Revenue & Earnings**:
- `totalRevenue`, `revenuePerShare`, `grossProfits`

**Ownership**:
- `heldPercentInsiders`, `heldPercentInstitutions`, `shortPercentOfFloat`

### 2.3 DART API Capabilities (Korea Only)

**Available Data**:
- Corporate financial disclosures (사업보고서, 분기보고서)
- Balance sheet (자산, 부채, 자본)
- Income statement (매출, 영업이익, 당기순이익)
- Cash flow statement (영업/투자/재무 활동 현금흐름)
- Key financial ratios from official disclosures

**Current Status**:
- `dart_api_client.py` already implemented but not used for fundamental collection
- Corporate code mapping exists
- API connection and rate limiting infrastructure ready

## 3. Database Architecture

### 3.1 Phase 1 Schema (Already Exists) ✅

**Table**: `ticker_fundamentals`

```sql
CREATE TABLE IF NOT EXISTS ticker_fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    period_type TEXT NOT NULL,  -- DAILY, QUARTERLY, ANNUAL

    # Basic metrics
    shares_outstanding BIGINT,
    market_cap BIGINT,
    close_price REAL,

    # Valuation ratios
    per REAL,     -- Price to Earnings Ratio
    pbr REAL,     -- Price to Book Ratio
    psr REAL,     -- Price to Sales Ratio
    pcr REAL,     -- Price to Cash Flow Ratio
    ev BIGINT,    -- Enterprise Value
    ev_ebitda REAL,

    # Dividend metrics
    dividend_yield REAL,
    dividend_per_share REAL,

    created_at TEXT NOT NULL,
    data_source TEXT,

    UNIQUE(ticker, date, period_type),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
)
```

**Usage**:
- Database method `insert_ticker_fundamentals()` already exists (db_manager_sqlite.py:572)
- Currently only used to store basic market_cap from market adapters

### 3.2 Phase 2 Schema (Designed, Not Implemented)

**Tables**: `balance_sheet`, `income_statement`, `cash_flow_statement`, `financial_ratios`

**Recommendation**:
- **Start with Phase 1** (ticker_fundamentals table is sufficient for most use cases)
- **Expand to Phase 2** only if:
  - User explicitly requests detailed financial statements
  - Backtesting requires quarterly/annual statement data
  - Advanced fundamental strategies need granular accounting data

## 4. Module Architecture

### 4.1 Core Components

```
modules/
├── fundamental_data_collector.py    # NEW: Main collector class
├── api_clients/
│   ├── yfinance_api.py              # EXISTS: Extend with fundamental methods
│   └── dart_api_client.py           # EXISTS: Extend for fundamental extraction
├── market_adapters/
│   └── base_adapter.py              # EXTEND: Add collect_fundamentals() method
└── db_manager_sqlite.py             # EXISTS: insert_ticker_fundamentals() ready
```

### 4.2 FundamentalDataCollector Class Design

```python
class FundamentalDataCollector:
    """
    Fundamental data collection orchestrator

    Features:
    - Multi-region support (KR, US, HK, CN, JP, VN)
    - API source routing (DART for KR, yfinance for global)
    - Intelligent caching (avoid duplicate API calls)
    - Batch processing with rate limiting
    - Error handling and retry logic
    """

    def __init__(self, db_manager: SQLiteDatabaseManager):
        self.db = db_manager
        self.yfinance_api = YFinanceAPI(rate_limit_per_second=1.0)
        self.dart_api = DARTApiClient()  # KR only

    def collect_fundamentals(self,
                            tickers: List[str],
                            region: str,
                            force_refresh: bool = False) -> Dict[str, bool]:
        """
        Collect fundamental data for tickers

        Args:
            tickers: List of ticker symbols
            region: Market region (KR, US, HK, CN, JP, VN)
            force_refresh: Skip cache and force new API calls

        Returns:
            Dict {ticker: success_status}
        """

    def _collect_from_yfinance(self, ticker: str, region: str) -> Optional[Dict]:
        """Collect fundamentals from Yahoo Finance"""

    def _collect_from_dart(self, ticker: str) -> Optional[Dict]:
        """Collect fundamentals from DART (KR only)"""

    def _should_skip_ticker(self, ticker: str) -> bool:
        """Check if ticker already has recent fundamental data"""
```

### 4.3 Integration Points

**1. Market Adapter Extension** (Optional)
```python
class BaseMarketAdapter:
    def collect_fundamentals(self, tickers: List[str]) -> int:
        """
        Collect fundamental data for tickers (optional)

        Called after Stage 2 technical analysis if user opts-in
        """
        collector = FundamentalDataCollector(self.db)
        results = collector.collect_fundamentals(tickers, self.region)
        return sum(1 for success in results.values() if success)
```

**2. spock.py Pipeline Integration** (User-Configurable)
```python
# In spock.py main pipeline
if args.collect_fundamentals and stage2_passed_tickers:
    logger.info(f"📊 Collecting fundamental data for {len(stage2_passed_tickers)} stocks")
    collector = FundamentalDataCollector(db_manager)
    collector.collect_fundamentals(stage2_passed_tickers, region='KR')
```

**3. Command-Line Interface**
```bash
# Collect fundamentals for specific tickers
python3 modules/fundamental_data_collector.py --tickers 005930 035720 --region KR

# Collect for all Stage 2 passed stocks
python3 spock.py --collect-fundamentals --region KR

# Force refresh existing data
python3 modules/fundamental_data_collector.py --force-refresh --tickers 005930
```

## 5. Data Collection Strategy

### 5.1 Collection Triggers (User-Configurable)

| Trigger | Description | Use Case |
|---------|-------------|----------|
| **Post-Stage 2** | After technical filter passes | Automated fundamental enrichment |
| **On-Demand** | User explicit request | Ad-hoc fundamental lookup |
| **Scheduled** | Daily/weekly cron job | Batch fundamental updates |
| **Watchlist Sync** | When adding to watchlist | Real-time fundamental display |

### 5.2 Caching Strategy

**Cache TTL by Data Type**:
- **Daily metrics** (PER, PBR, market_cap): 24 hours
- **Quarterly statements** (revenue, earnings): 90 days
- **Annual reports** (detailed financials): 365 days

**Cache Validation**:
```python
def _should_skip_ticker(self, ticker: str) -> bool:
    """Check if cached data is still fresh"""
    last_update = self.db.get_last_fundamental_update(ticker)
    if last_update:
        elapsed_hours = (datetime.now() - last_update).total_seconds() / 3600
        if elapsed_hours < 24:  # 24-hour cache
            logger.debug(f"[{ticker}] Using cached fundamental data ({elapsed_hours:.1f}h old)")
            return True
    return False
```

### 5.3 API Cost Optimization

**Batch Processing**:
```python
def collect_fundamentals_batch(self, tickers: List[str], batch_size: int = 100):
    """Process tickers in batches to respect rate limits"""
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        for ticker in batch:
            # Rate limiting: 1 req/sec for yfinance
            self._collect_from_yfinance(ticker)
            time.sleep(1.0)
```

**Smart Refresh**:
- Only refresh if data is stale (>24 hours for daily metrics)
- Skip tickers with recent fundamental updates
- Prioritize Stage 2 passed stocks over watchlist items

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Implement `FundamentalDataCollector` class
- [ ] Extend `yfinance_api.py` with fundamental extraction methods
- [ ] Add fundamental collection to `base_adapter.py`
- [ ] Unit tests for fundamental data parsing

### Phase 2: API Integration (Week 3)
- [ ] Implement yfinance fundamental extraction (40+ fields)
- [ ] Extend DART API for Korean fundamental data
- [ ] Test multi-region fundamental collection (KR, US, HK, CN, JP, VN)
- [ ] Validate data quality and field mapping

### Phase 3: Pipeline Integration (Week 4)
- [ ] Add `--collect-fundamentals` flag to spock.py
- [ ] Integrate with Stage 2 filter pipeline
- [ ] Implement caching and TTL logic
- [ ] Add CLI interface for standalone fundamental collection

### Phase 4: Testing & Validation (Week 5)
- [ ] Integration testing with real API data
- [ ] Validate database insertion and retrieval
- [ ] Performance testing (API rate limits, caching effectiveness)
- [ ] User acceptance testing

### Phase 5: Documentation & Deployment (Week 6)
- [ ] Update CLAUDE.md with fundamental module documentation
- [ ] Create user guide for fundamental data collection
- [ ] Add examples to `examples/` directory
- [ ] Production deployment

## 7. Usage Examples

### 7.1 Standalone Fundamental Collection

```python
from modules.fundamental_data_collector import FundamentalDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Initialize
db = SQLiteDatabaseManager()
collector = FundamentalDataCollector(db)

# Collect fundamentals for specific tickers
results = collector.collect_fundamentals(
    tickers=['005930', '035720', '000660'],
    region='KR',
    force_refresh=False
)

# Check results
for ticker, success in results.items():
    if success:
        print(f"✅ {ticker}: Fundamental data collected")
    else:
        print(f"❌ {ticker}: Collection failed")
```

### 7.2 Integration with Spock Pipeline

```bash
# Collect fundamentals after Stage 2 technical filter
python3 spock.py --region KR --collect-fundamentals

# Dry run (test without database writes)
python3 spock.py --dry-run --collect-fundamentals --tickers 005930
```

### 7.3 Retrieve Fundamental Data

```python
# Get latest fundamental data for a ticker
fundamentals = db.get_ticker_fundamentals(ticker='005930', limit=1)

if fundamentals:
    print(f"PER: {fundamentals[0]['per']}")
    print(f"PBR: {fundamentals[0]['pbr']}")
    print(f"Dividend Yield: {fundamentals[0]['dividend_yield']}%")
    print(f"Market Cap: {fundamentals[0]['market_cap']:,} KRW")
```

## 8. Future Enhancements

### 8.1 Advanced Fundamental Filtering (Future)

**Potential Use Case**: Add fundamental filters to Stage 0 or Stage 1
```python
# Example: Filter stocks by fundamental criteria
fundamental_filters = {
    'min_per': 5,      # PER >= 5
    'max_per': 20,     # PER <= 20
    'min_roe': 10,     # ROE >= 10%
    'max_debt_ratio': 100  # Debt/Equity <= 100%
}
```

**Implementation Note**:
- This would require fundamental data to be collected **before** Stage 2 technical analysis
- Current design focuses on **post-Stage 2 collection** to minimize API costs
- Can be added later if user demand exists

### 8.2 Fundamental + Technical Combined Scoring (Future)

**Potential Enhancement**: LayeredScoringEngine expansion
```python
# Add Layer 4 - Fundamental Analysis (optional, 20 points)
class FundamentalAnalysisModule:
    def analyze(self, ticker: str) -> Tuple[float, str]:
        """
        Score based on fundamental health

        Metrics:
        - Valuation (5 pts): PER, PBR relative to sector
        - Profitability (5 pts): ROE, margins
        - Growth (5 pts): Revenue/earnings growth
        - Financial Health (5 pts): Debt ratio, cash flow
        """
```

**Note**: This would increase total score from 100 to 120 points and require careful rebalancing of scoring thresholds.

### 8.3 Phase 2 Database Schema Activation

**Trigger Conditions**:
- User explicitly requests quarterly/annual statement data
- Backtesting framework requires detailed accounting data
- Advanced fundamental strategies need granular financial metrics

**Implementation Effort**: ~2 weeks
- Activate Phase 2 tables (balance_sheet, income_statement, cash_flow_statement, financial_ratios)
- Extend DART API integration for detailed Korean financial statements
- Add yfinance quarterly/annual data parsing
- Update database migration scripts

## 9. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API Rate Limits** | Medium | Implement caching, batch processing, rate limiting |
| **Data Quality** | Medium | Validate data, handle missing fields, fallback logic |
| **API Cost** (if using paid APIs) | Low | Use free APIs (yfinance, DART) for MVP |
| **Database Bloat** | Low | TTL-based cleanup, Phase 1 schema sufficient |
| **Integration Complexity** | Low | Non-intrusive design, optional feature |

## 10. Success Criteria

- [ ] Fundamental data successfully collected for all 6 markets (KR, US, HK, CN, JP, VN)
- [ ] API rate limits respected (no errors from excessive calls)
- [ ] Caching reduces API calls by >80% for repeat queries
- [ ] Database insertion success rate >95%
- [ ] User documentation complete with usage examples
- [ ] No impact on existing technical analysis pipeline performance

## 11. Dependencies

**Existing Components** (Ready):
- ✅ `ticker_fundamentals` table schema (init_db.py)
- ✅ `insert_ticker_fundamentals()` method (db_manager_sqlite.py)
- ✅ `yfinance_api.py` infrastructure (rate limiting, session management)
- ✅ `dart_api_client.py` infrastructure (OAuth, rate limiting)
- ✅ Market adapter base class (base_adapter.py)

**New Components** (To Be Built):
- FundamentalDataCollector class (~300 lines)
- yfinance fundamental field extraction (~100 lines)
- DART fundamental extraction (~200 lines)
- CLI interface and spock.py integration (~50 lines)
- Unit tests (~200 lines)

**Total Estimated Effort**: 4-6 weeks (including testing and documentation)

## 12. Conclusion

This implementation plan provides a **non-intrusive, optional fundamental data collection module** that:

1. **Leverages existing infrastructure**: Uses yfinance and DART APIs already in codebase
2. **Minimizes costs**: Free API sources with intelligent caching
3. **Supports future needs**: Enables backtesting and user-driven fundamental analysis
4. **Maintains system focus**: Does not alter existing 100% technical analysis trading logic
5. **Scales across markets**: Unified approach for all 6 supported regions

The module can be implemented incrementally and activated only when users explicitly opt-in, ensuring zero impact on current trading operations while providing a foundation for advanced fundamental analysis capabilities in the future.

---

**Next Steps**:
1. User approval of implementation plan
2. Begin Phase 1: Foundation (FundamentalDataCollector class)
3. Test fundamental data extraction with sample tickers
4. Integrate with spock.py pipeline as optional feature
