# Blacklist System Integration Guide

Complete guide for integrating the dual-system blacklist into Spock trading pipeline.

**Version**: 2.0
**Last Updated**: 2025-10-17
**Status**: Ready for Integration

---

## Overview

The blacklist system provides **two-tier filtering** for unwanted tickers across all supported markets (KR, US, CN, HK, JP, VN):

1. **DB-based (Primary)**: Permanent deactivation via `is_active=False` in `tickers` table
2. **File-based (Secondary)**: Temporary exclusion via `config/stock_blacklist.json`

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              BlacklistManager                           │
│                                                         │
│  System 1 (DB)          System 2 (File)               │
│  ┌─────────────┐        ┌──────────────────┐          │
│  │ is_active=0 │        │ stock_blacklist  │          │
│  │ (Permanent) │        │ .json (Temp)     │          │
│  └─────────────┘        └──────────────────┘          │
│                                                         │
│  Unified API: is_blacklisted(ticker, region)          │
└─────────────────────────────────────────────────────────┘
                           ↓
     ┌──────────────────────────────────────────┐
     │         Trading Pipeline                  │
     ├──────────────────────────────────────────┤
     │ Phase 0: stock_scanner.py        ✅      │
     │ Phase 1: kis_data_collector.py   ✅      │
     │ Phase 2: technical_filter.py      ✅      │
     │ Phase 3: gpt_analyzer.py          ✅      │
     │ Kelly Calculator                  ✅      │
     │ Trading Engine (CRITICAL)         🚨      │
     └──────────────────────────────────────────┘
```

---

## Integration Points

### Phase 0: Stock Scanner (Ticker Discovery)

**File**: `modules/stock_scanner.py`

**Integration**:
```python
from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager

class StockScanner:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def scan_stocks(self) -> List[str]:
        """Scan stocks and filter blacklisted tickers"""
        # Step 1: Get all tickers from adapter
        raw_tickers = self.adapter.scan_stocks()

        # Step 2: Filter blacklisted tickers
        ticker_codes = [t['ticker'] for t in raw_tickers]
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=ticker_codes,
            region=self.region
        )

        logger.info(f"Scanned: {len(raw_tickers)}, Filtered: {len(filtered_tickers)}")
        return filtered_tickers
```

**Why**: Prevents blacklisted tickers from entering the pipeline early.

---

### Phase 1: Data Collector (OHLCV Collection)

**File**: `modules/kis_data_collector.py`

**Integration**:
```python
from modules.blacklist_manager import BlacklistManager

class KISDataCollector:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def collect_ohlcv(self, tickers: Optional[List[str]] = None) -> int:
        """Collect OHLCV data for non-blacklisted tickers"""
        # Step 1: Get ticker list
        if not tickers:
            tickers = self.db.get_stock_tickers(region=self.region)

        # Step 2: Filter blacklisted tickers
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=tickers,
            region=self.region
        )

        # Step 3: Collect data for filtered tickers
        success_count = 0
        for ticker in filtered_tickers:
            if self.collect_single_ticker(ticker):
                success_count += 1

        return success_count
```

**Why**: Avoids wasting API rate limits on blacklisted tickers.

---

### Phase 2: Technical Filter (Stage 2 Analysis)

**File**: `modules/stock_technical_filter.py`

**Integration**:
```python
from modules.blacklist_manager import BlacklistManager

class TechnicalFilter:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def filter_stage2_stocks(self, tickers: List[str]) -> List[Dict]:
        """Filter Stage 2 stocks, excluding blacklisted tickers"""
        # Step 1: Filter blacklisted tickers BEFORE analysis
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=tickers,
            region=self.region
        )

        # Step 2: Run technical analysis on filtered tickers
        stage2_stocks = []
        for ticker in filtered_tickers:
            score = self.analyze_ticker(ticker)
            if score >= 70:  # Stage 2 threshold
                stage2_stocks.append({
                    'ticker': ticker,
                    'score': score
                })

        return stage2_stocks
```

**Why**: Prevents computational waste on blacklisted tickers.

---

### Phase 3: GPT Analyzer (Chart Pattern Analysis)

**File**: `modules/stock_gpt_analyzer.py`

**Integration**:
```python
from modules.blacklist_manager import BlacklistManager

class GPTAnalyzer:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def analyze_charts(self, candidates: List[Dict]) -> List[Dict]:
        """Analyze chart patterns, excluding blacklisted tickers"""
        # Step 1: Extract ticker codes
        tickers = [c['ticker'] for c in candidates]

        # Step 2: Filter blacklisted tickers
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=tickers,
            region=self.region
        )

        # Step 3: Analyze only filtered tickers
        results = []
        for candidate in candidates:
            if candidate['ticker'] in filtered_tickers:
                analysis = self.analyze_single_chart(candidate['ticker'])
                results.append(analysis)

        return results
```

**Why**: Saves GPT-4 API costs by skipping blacklisted tickers.

---

### Kelly Calculator (Position Sizing)

**File**: `modules/kelly_calculator.py`

**Integration**:
```python
from modules.blacklist_manager import BlacklistManager

class KellyCalculator:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def calculate_position_sizes(self, candidates: List[Dict]) -> Dict[str, float]:
        """Calculate position sizes, excluding blacklisted tickers"""
        # Step 1: Extract ticker codes
        tickers = [c['ticker'] for c in candidates]

        # Step 2: Filter blacklisted tickers
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=tickers,
            region=self.region
        )

        # Step 3: Calculate positions for filtered tickers
        positions = {}
        for candidate in candidates:
            if candidate['ticker'] in filtered_tickers:
                position_size = self.calculate_kelly(candidate)
                positions[candidate['ticker']] = position_size

        return positions
```

**Why**: Prevents position sizing for tickers that won't be traded.

---

### Trading Engine (Order Execution) 🚨 CRITICAL

**File**: `modules/kis_trading_engine.py`

**Integration** (MANDATORY):
```python
from modules.blacklist_manager import BlacklistManager

class KISTradingEngine:
    def __init__(self, region: str):
        self.region = region
        self.db = SQLiteDatabaseManager()
        self.blacklist = BlacklistManager(self.db)

    def place_order(self, ticker: str, order_type: str, quantity: int, price: float) -> bool:
        """
        Place order with MANDATORY blacklist check

        CRITICAL: This is the LAST line of defense before real money
        """
        # STEP 1: MANDATORY BLACKLIST CHECK 🚨
        if self.blacklist.is_blacklisted(ticker, self.region):
            logger.error(f"🚫 ORDER REJECTED: {ticker} is blacklisted")
            return False

        # STEP 2: Tick size validation
        validated_price = self._adjust_tick_size(price)

        # STEP 3: Execute order via KIS API
        result = self.kis_api.place_order(
            ticker=ticker,
            order_type=order_type,
            quantity=quantity,
            price=validated_price
        )

        return result['success']

    def get_buy_candidates(self) -> List[str]:
        """Get buy candidates, excluding blacklisted tickers"""
        # Get candidates from analysis
        candidates = self.db.get_top_scored_stocks(region=self.region, limit=20)

        # Filter blacklisted tickers
        ticker_codes = [c['ticker'] for c in candidates]
        filtered_tickers = self.blacklist.filter_blacklisted_tickers(
            tickers=ticker_codes,
            region=self.region
        )

        return filtered_tickers
```

**Why**: Final safety check before placing real orders.

---

## CLI Usage Examples

### Add Ticker to Blacklist (Temporary)

```bash
# Korean stock with expiry
python3 scripts/manage_blacklist.py add \
  --ticker 005930 \
  --region KR \
  --reason "임시 제외 - 4분기 실적 분석 대기" \
  --expire 2025-12-31 \
  --notes "실적 발표 후 재검토"

# US stock (permanent until manually removed)
python3 scripts/manage_blacklist.py add \
  --ticker TSLA \
  --region US \
  --reason "변동성 과다" \
  --added-by analyst
```

### Remove from Blacklist

```bash
python3 scripts/manage_blacklist.py remove \
  --ticker 005930 \
  --region KR
```

### Deactivate in DB (Permanent)

```bash
# Delisted stock
python3 scripts/manage_blacklist.py deactivate \
  --ticker 000660 \
  --region KR \
  --reason "상장폐지 (2025-10-01)"

# Trading halted
python3 scripts/manage_blacklist.py deactivate \
  --ticker BABA \
  --region US \
  --reason "거래정지 - SEC 조사 중"
```

### Reactivate in DB

```bash
python3 scripts/manage_blacklist.py reactivate \
  --ticker 000660 \
  --region KR
```

### List Blacklisted Tickers

```bash
# All regions
python3 scripts/manage_blacklist.py list

# Specific region
python3 scripts/manage_blacklist.py list --region US
```

### Show Summary

```bash
python3 scripts/manage_blacklist.py summary
```

### Cleanup Expired Entries

```bash
python3 scripts/manage_blacklist.py cleanup
```

### Check Ticker Status

```bash
python3 scripts/manage_blacklist.py check \
  --ticker 005930 \
  --region KR
```

---

## Database Schema Impact

### `tickers` Table

**Existing Column**: `is_active BOOLEAN DEFAULT 1`

**Usage**:
- `is_active = 1` (True): Normal ticker, included in pipeline
- `is_active = 0` (False): Permanently deactivated, excluded from pipeline

**No schema changes required** ✅

---

## File Format: `config/stock_blacklist.json`

```json
{
  "version": "2.0",
  "last_updated": "2025-10-17T12:00:00+09:00",
  "blacklist": {
    "KR": {
      "005930": {
        "name": "삼성전자",
        "reason": "임시 제외 - 분석 대기",
        "added_date": "2025-10-15",
        "added_by": "system",
        "expire_date": "2025-12-31",
        "notes": "4분기 실적 발표 후 재검토"
      }
    },
    "US": {
      "TSLA": {
        "name": "Tesla Inc",
        "reason": "변동성 과다",
        "added_date": "2025-10-10",
        "added_by": "user",
        "expire_date": null,
        "notes": "매크로 환경 안정 시 재검토"
      }
    },
    "CN": {},
    "HK": {},
    "JP": {},
    "VN": {}
  }
}
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_blacklist_manager.py`

Test cases:
1. Add/remove tickers to file blacklist
2. Deactivate/reactivate tickers in DB
3. Check `is_blacklisted()` for both systems
4. Filter ticker lists
5. Validate ticker formats per region
6. Expiry date handling
7. Combined blacklist merging

### Integration Tests

Test scenarios:
1. **Scanner Integration**: Verify blacklisted tickers excluded from scan results
2. **Data Collector Integration**: Verify OHLCV collection skips blacklisted tickers
3. **Technical Filter Integration**: Verify Stage 2 analysis skips blacklisted tickers
4. **Trading Engine Integration**: Verify orders rejected for blacklisted tickers

### End-to-End Tests

Test full pipeline:
1. Add ticker to blacklist (file-based)
2. Run full pipeline (scanner → data collector → analysis → trading)
3. Verify ticker excluded at every stage
4. Verify no order placed for blacklisted ticker

---

## Performance Considerations

### Caching Strategy

**DB Blacklist**:
- Cached in memory during pipeline execution
- Refreshed at start of each trading session
- ~0.1ms lookup time (in-memory set)

**File Blacklist**:
- Loaded once at startup
- Kept in memory (JSON parsing ~5ms)
- ~0.1ms lookup time (in-memory dict)

**Combined Lookup**:
- Total overhead: ~0.2ms per ticker check
- Negligible impact on pipeline performance

### API Rate Limit Savings

**Assumption**: 10% of tickers blacklisted

**Savings per region**:
- KR: ~300 tickers × 10% = 30 tickers saved
- US: ~3,000 tickers × 10% = 300 tickers saved
- CN: ~1,000 tickers × 10% = 100 tickers saved

**KIS API rate limit**: 20 req/sec = 1,200 req/min

**Time saved per day**:
- 430 tickers × 250 days OHLCV = **107,500 API calls saved annually**
- At 20 req/sec: **~90 minutes saved per year**

---

## Migration Plan

### Phase 1: Setup (Week 1)

1. ✅ Create `BlacklistManager` class
2. ✅ Create `config/stock_blacklist.json`
3. ✅ Create `scripts/manage_blacklist.py`

### Phase 2: Integration (Week 2)

1. ⏳ Integrate into `stock_scanner.py`
2. ⏳ Integrate into `kis_data_collector.py`
3. ⏳ Integrate into `stock_technical_filter.py`
4. ⏳ Integrate into `stock_gpt_analyzer.py`
5. ⏳ Integrate into `kelly_calculator.py`
6. 🚨 **CRITICAL**: Integrate into `kis_trading_engine.py`

### Phase 3: Testing (Week 2-3)

1. ⏳ Write unit tests
2. ⏳ Write integration tests
3. ⏳ Run end-to-end tests
4. ⏳ Performance benchmarking

### Phase 4: Deployment (Week 3)

1. ⏳ Dry-run mode testing (1 week)
2. ⏳ Production deployment
3. ⏳ Monitoring and validation

---

## Error Handling

### Blacklist File Corruption

**Scenario**: `stock_blacklist.json` is corrupted or invalid JSON

**Behavior**:
1. Automatic backup created: `stock_blacklist.json.backup.YYYYMMDD_HHMMSS`
2. Empty blacklist initialized
3. Warning logged
4. Pipeline continues (fail-safe)

### Database Connection Failure

**Scenario**: Cannot query `tickers` table for `is_active` status

**Behavior**:
1. Warning logged
2. Fall back to file-based blacklist only
3. Pipeline continues (graceful degradation)

### Invalid Ticker Format

**Scenario**: Ticker format doesn't match region rules

**Behavior**:
1. Validation error logged
2. Operation rejected (add/remove/check)
3. User notified via CLI

---

## Compliance & Audit Trail

### Audit Requirements

For regulatory compliance, the blacklist system provides:

1. **Reason Tracking**: Every blacklist entry requires a reason
2. **Timestamp**: `added_date` recorded for all entries
3. **User Attribution**: `added_by` field (system, user, analyst)
4. **Version Control**: Git-tracked `stock_blacklist.json`
5. **Expiry Management**: Automatic cleanup of expired entries

### Compliance Reports

Generate compliance reports:

```python
from modules.blacklist_manager import BlacklistManager

blacklist = BlacklistManager(db)

# Get all blacklisted tickers with metadata
for region in ['KR', 'US', 'CN', 'HK', 'JP', 'VN']:
    file_blacklist = blacklist._file_blacklist.get(region, {})
    for ticker, info in file_blacklist.items():
        print(f"{region}:{ticker} | {info['reason']} | {info['added_by']} | {info['added_date']}")
```

---

## Security Considerations

### File Permissions

**Recommended**:
```bash
chmod 600 config/stock_blacklist.json  # Owner read/write only
```

**Why**: Prevent unauthorized modifications

### Git Tracking

**Recommended**: Track in Git for audit trail

**Caution**: If blacklist contains sensitive information, use `.gitignore` or encrypt

---

## FAQ

### Q1: What's the difference between DB and file blacklist?

**A**:
- **DB blacklist** (`is_active=False`): Permanent, used for delisted/halted stocks
- **File blacklist** (`stock_blacklist.json`): Temporary, used for personal judgment with expiry dates

### Q2: Can I use both systems simultaneously?

**A**: Yes! The `is_blacklisted()` method checks BOTH systems. If ticker is in either, it's considered blacklisted.

### Q3: What happens if blacklist file is deleted?

**A**: `BlacklistManager` automatically creates empty file on next run. No data loss.

### Q4: How do I bulk-import blacklisted tickers?

**A**: Edit `config/stock_blacklist.json` directly or write a script:

```python
from modules.blacklist_manager import BlacklistManager

blacklist = BlacklistManager(db)

bulk_tickers = [
    ('005930', 'KR', 'Reason 1'),
    ('000660', 'KR', 'Reason 2'),
    # ... more
]

for ticker, region, reason in bulk_tickers:
    blacklist.add_to_file_blacklist(ticker, region, reason)
```

### Q5: Can I blacklist an entire sector?

**A**: Not directly. Blacklist is ticker-based. For sector exclusion, add custom logic in scanner.

---

## Monitoring

### Key Metrics

Track these metrics in production:

1. **Total blacklisted tickers** per region
2. **API calls saved** per day (from blacklist filtering)
3. **Order rejection rate** due to blacklist
4. **Expired entry cleanup** frequency

### Grafana Dashboard

Add panels:
- Blacklist size (DB + file) per region
- Blacklist hit rate (% of tickers filtered)
- Order rejections due to blacklist

---

## Conclusion

The dual-system blacklist provides:

✅ **Safety**: Multi-layer filtering prevents unwanted trades
✅ **Efficiency**: Saves API rate limits and computational resources
✅ **Flexibility**: DB for permanent, file for temporary exclusions
✅ **Compliance**: Audit trail with reasons and timestamps
✅ **Maintainability**: Simple JSON format + CLI tool

**Status**: Ready for integration into trading pipeline.

---

**Next Steps**:
1. Review integration points with team
2. Write unit tests (`tests/test_blacklist_manager.py`)
3. Integrate into Phase 0-3 modules
4. **CRITICAL**: Integrate into trading engine with mandatory check
5. Run dry-run testing for 1 week
6. Deploy to production

**Contact**: Spock Trading System Team
**Documentation**: `docs/BLACKLIST_INTEGRATION_GUIDE.md`
