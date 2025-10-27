# Global Stock Metadata Enrichment Design

**Document Version**: 1.0
**Date**: 2025-10-17
**Status**: Design Phase
**Author**: Spock Trading System

## Executive Summary

해외 주식(US, CN, HK, JP, VN)의 **stock_details** 테이블에 누락된 메타데이터(sector, industry, industry_code, is_spac, is_preferred)를 보강하는 시스템 설계입니다.

**Current Status**:
- ✅ **KR**: 100% coverage (141 stocks, all fields populated)
- ❌ **Global Markets**: Partial coverage (17,292 stocks)
  - ✅ **sector_code**: 100% (from KIS Master File)
  - ❌ **sector text**: 0%
  - ❌ **industry text**: 0%
  - ❌ **is_spac, is_preferred**: 0%

**Key Discovery** 🔍:
- KIS Master File already provides `sector_code` (업종분류코드) for **100% of global stocks**
- sector_code: 3-digit numeric code (e.g., 730=IT Hardware, 610=Banks)
- **46% of stocks** have mappable sector_code (sector_code != 0) → Instant GICS classification
- **54% of stocks** have sector_code = 0 (SPAC/Unclassified) → yfinance fallback required

**Hybrid Architecture** ✨:
1. **Primary**: KIS sector_code → GICS 11 mapping (46% instant, 0 API calls)
2. **Secondary**: yfinance API fallback (54% for sector, 100% for industry/SPAC/preferred)

**Goal**: Enrich 17,292 global stocks with complete metadata using hybrid KIS + yfinance approach.

**Performance Benefit**:
- ⚡ **46% faster** sector classification (instant KIS mapping)
- 📉 **~8,000 fewer** yfinance calls for sector field
- 🎯 **Still need yfinance** for industry text, SPAC, and preferred detection

---

## 1. Problem Analysis

### 1.1 Current Data Gap

| Region | Total Stocks | Sector Coverage | Industry Coverage | Industry Code | SPAC Flag | Preferred Flag |
|--------|--------------|-----------------|-------------------|---------------|-----------|----------------|
| KR     | 141          | 100%            | 100%              | 100%          | 100%      | 100%           |
| US     | 6,388        | **0%**          | **0%**            | **0%**        | 100%      | 100%           |
| JP     | 4,036        | **0%**          | **0%**            | **0%**        | 100%      | 100%           |
| CN     | 3,450        | **0%**          | **0%**            | **0%**        | 100%      | 100%           |
| HK     | 2,722        | **0%**          | **0%**            | **0%**        | 100%      | 100%           |
| VN     | 696          | **0%**          | **0%**            | **0%**        | 100%      | 100%           |

**Critical Issue**: Global stocks have **ZERO** sector and industry data, preventing:
- Sector rotation analysis
- Industry-specific filtering
- GICS classification-based portfolio management
- Risk diversification by sector

### 1.2 Root Cause Analysis

**Master File Limitation** (`us_adapter_kis.py:210-226`):
```python
# Master file provides minimal metadata
stock_info = {
    'ticker': ticker_data['ticker'],
    'sector': '',  # ❌ Empty - Will be enriched later
    'industry': '',  # ❌ Empty - Will be enriched later
    'market_cap': 0,  # ❌ Empty - Will be enriched later
}
```

**Design Decision**:
- **Phase 6** prioritized **speed** (instant ticker scanning via master files)
- **Metadata enrichment** was deferred to **Phase 7** (yfinance/API-based)

**Current Workflow Gap**:
1. ✅ Ticker scanning: Complete (master files)
2. ✅ OHLCV collection: Complete (KIS API)
3. ❌ **Metadata enrichment**: NOT IMPLEMENTED

---

## 2. Design Goals

### 2.1 Functional Requirements

| Requirement | Description | Priority |
|-------------|-------------|----------|
| **FR-1** | Enrich sector and industry for all global stocks | P0 (Critical) |
| **FR-2** | Populate industry_code with standardized classification | P1 (High) |
| **FR-3** | Detect SPAC and preferred stock status | P1 (High) |
| **FR-4** | Support incremental enrichment (new tickers only) | P2 (Medium) |
| **FR-5** | Cache enrichment results (avoid re-fetching) | P2 (Medium) |
| **FR-6** | Retry logic for API failures | P3 (Low) |

### 2.2 Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| **Performance** | 17,292 stocks in <30 minutes | yfinance rate limit: ~1 req/sec |
| **Reliability** | >95% success rate | Handle transient failures gracefully |
| **Data Quality** | 100% GICS sector mapping | Leverage existing parsers |
| **Maintainability** | Reuse existing adapter pattern | Minimal code changes |

---

## 3. Architecture Design

### 3.1 System Overview (Hybrid Architecture)

```
┌──────────────────────────────────────────────────────────────────────┐
│              Global Metadata Enrichment System (Hybrid)              │
└──────────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────────────┐
                    │                           │
         ┌──────────▼──────────┐      ┌─────── ▼──────────────────────┐
         │  Enrichment Engine  │      │  Data Sources (Priority)      │
         │  (Hybrid Logic)     │      │                               │
         │                     │      │  1️⃣ KIS Master File          │
         │ - KIS mapping first │      │     • sector_code (100%)      │
         │ - yfinance fallback │      │     • 업종분류코드 → GICS     │
         │ - Batch processing  │      │                               │
         │ - Rate limiting     │      │  2️⃣ yfinance API (Fallback)  │
         │ - Error handling    │      │     • sector (sector_code=0)  │
         │ - Cache management  │      │     • industry (always)       │
         └──────────┬──────────┘      │     • is_spac (always)        │
                    │                 │     • is_preferred (always)   │
                    │                 └───────────────────────────────┘
                    │
         ┌──────────▼──────────────────────────────────┐
         │   KIS Sector Code Mapping                   │
         │   (config/kis_sector_code_to_gics_mapping)  │
         │                                             │
         │   46% Instant GICS: sector_code → GICS     │
         │   54% yfinance Fallback: sector_code = 0   │
         └──────────┬──────────────────────────────────┘
                    │
         ┌──────────▼───────────────┐
         │   Market Adapters        │
         │   (Enhanced)             │
         │                          │
         │ - USAdapterKIS           │
         │ - CNAdapterKIS           │
         │ - HKAdapterKIS           │
         │ - JPAdapterKIS           │
         │ - VNAdapterKIS           │
         │                          │
         │ Each adapter:            │
         │ 1. Read sector_code (DB) │
         │ 2. Map → GICS (instant)  │
         │ 3. Fallback yfinance     │
         │ 4. Update stock_details  │
         └──────────┬───────────────┘
                    │
         ┌──────────▼───────────────┐
         │   Database Manager       │
         │                          │
         │ - stock_details UPDATE   │
         │ - Bulk operations        │
         │ - Transaction management │
         └──────────────────────────┘
```

**Performance Impact**:
- ⚡ **46% faster** sector enrichment (KIS mapping, no API)
- 🔄 **Still 17,292 yfinance calls** (industry/SPAC/preferred)
- 📊 **Hybrid benefit**: Sector processing accelerated by instant mapping

### 3.2 Component Design

#### 3.2.1 Enrichment Engine (New Module)

**Location**: `modules/stock_metadata_enricher.py`

**Responsibilities**:
- Batch processing of stocks (100 stocks/batch)
- Rate limiting (1 req/sec for yfinance)
- Retry logic (3 attempts, exponential backoff)
- Progress tracking and logging
- Cache management (24-hour TTL)

**Key Methods**:
```python
class StockMetadataEnricher:
    def enrich_region(self, region: str, force_refresh: bool = False) -> int:
        """Enrich all stocks in a region"""

    def enrich_batch(self, tickers: List[str], parser) -> Dict[str, Dict]:
        """Enrich a batch of tickers with rate limiting"""

    def _check_cache(self, ticker: str) -> Optional[Dict]:
        """Check if ticker metadata is already cached"""

    def _save_to_cache(self, ticker: str, metadata: Dict):
        """Save metadata to cache"""

    def _retry_with_backoff(self, func, max_retries: int = 3):
        """Retry function with exponential backoff"""
```

#### 3.2.2 Adapter Enhancement

**Location**: `modules/market_adapters/*_adapter_kis.py`

**New Method** (add to each adapter):
```python
def enrich_stock_metadata(self,
                         tickers: Optional[List[str]] = None,
                         force_refresh: bool = False) -> int:
    """
    Enrich stock metadata (sector, industry, industry_code, is_spac, is_preferred)

    Data Source Priority:
    1. Master file sector_code (if available)
    2. yfinance API (sector, industry, SPAC/preferred detection)
    3. Local parser (GICS mapping, industry_code normalization)

    Args:
        tickers: List of tickers (None = all stocks without metadata)
        force_refresh: Re-fetch even if metadata exists

    Returns:
        Number of stocks successfully enriched
    """
```

**Integration Points**:
- **USAdapterKIS**: USStockParser.parse_fundamentals() + GICS mapping
- **CNAdapterKIS**: CNStockParser.normalize_sector() + CSRC→GICS
- **HKAdapterKIS**: HKStockParser.normalize_sector() + local→GICS
- **JPAdapterKIS**: JPStockParser.map_tse_to_gics()
- **VNAdapterKIS**: VNStockParser.map_icb_to_gics()

#### 3.2.3 Database Operations

**Location**: `modules/db_manager_sqlite.py`

**Enhanced Method** (already exists at line 240-300):
```python
def update_stock_details(self, ticker: str, updates: Dict) -> bool:
    """
    Update specific fields in stock_details table

    Supports fields:
    - sector, sector_code
    - industry, industry_code
    - is_spac, is_preferred
    - par_value
    """
```

**Bulk Update Method** (new):
```python
def bulk_update_stock_details(self, updates: List[Dict]) -> int:
    """
    Bulk update stock_details for efficiency

    Args:
        updates: List of {ticker, sector, industry, ...} dicts

    Returns:
        Number of rows updated
    """
```

---

## 4. Data Source Strategy (Hybrid Architecture)

### 4.1 Data Source Matrix

**NEW: Hybrid Master File + yfinance Approach** 🚀

| Region | Primary Source | Secondary Source | Classification System |
|--------|----------------|------------------|-----------------------|
| US     | **KIS Master File** sector_code | yfinance API (fallback) | KIS Code → GICS 11 |
| CN     | **KIS Master File** sector_code | yfinance API (fallback) | KIS Code → GICS 11 |
| HK     | **KIS Master File** sector_code | yfinance API (fallback) | KIS Code → GICS 11 |
| JP     | **KIS Master File** sector_code | yfinance API (fallback) | KIS Code → GICS 11 |
| VN     | **KIS Master File** sector_code | yfinance API (fallback) | KIS Code → GICS 11 |

**Key Discovery**: KIS Master File already provides `sector_code` (업종분류코드) for **100% of stocks**!

**Coverage Analysis**:
- ✅ **sector_code available**: 100% (17,292 stocks)
  - sector_code != 0: 46% (7,831 stocks) → **Instant GICS mapping**
  - sector_code = 0: 54% (9,461 stocks) → **yfinance fallback**
- ❌ **sector text**: 0% → Always use yfinance
- ❌ **industry text**: 0% → Always use yfinance
- ❌ **is_spac, is_preferred**: 0% → Always use yfinance

**Performance Benefit**:
- **46% faster** sector classification (no yfinance calls for sector_code != 0)
- **yfinance calls reduced** by ~8,000 for sector field
- **Still require yfinance** for industry, SPAC, preferred detection

### 4.2 Hybrid Data Extraction Workflow

**Step 1: KIS Master File sector_code → GICS Mapping** (Primary)
```python
# Load mapping table
with open('config/kis_sector_code_to_gics_mapping.json') as f:
    sector_mapping = json.load(f)['mapping']

# Extract sector_code from stock_details (already in database!)
sector_code = stock_details.get('sector_code', '0')

# Map to GICS sector
if sector_code != '0' and sector_code in sector_mapping:
    gics_sector = sector_mapping[sector_code]['gics_sector']
    # ✅ Success! No yfinance call needed for sector
else:
    gics_sector = None  # Need yfinance fallback
```

**Step 2: yfinance Fallback + Additional Fields** (Secondary)
```python
import yfinance as yf

ticker_obj = yf.Ticker("AAPL")
info = ticker_obj.info

# Sector (only if KIS mapping failed or sector_code=0)
if not gics_sector:
    gics_sector = info.get('sector')  # GICS Level 1

# Industry (always from yfinance - not in master file)
industry = info.get('industry')  # GICS Level 2 (sub-industry)

# SPAC Detection (always from yfinance)
is_spac = 'SPAC' in info.get('longBusinessSummary', '') or \
          'acquisition' in info.get('longName', '').lower()

# Preferred Stock Detection (always from yfinance)
is_preferred = 'Preferred' in info.get('quoteType', '') or \
               '-P' in ticker or ' PR' in ticker
```

**Complete Hybrid Logic**:
```python
def enrich_metadata(ticker: str, sector_code: str) -> Dict:
    """
    Hybrid enrichment: KIS sector_code → GICS first, yfinance fallback

    Args:
        ticker: Stock ticker
        sector_code: KIS Master File sector code

    Returns:
        {
            'sector': str,      # From KIS mapping OR yfinance
            'industry': str,    # Always from yfinance
            'industry_code': str,  # sector_code (from master file)
            'is_spac': bool,    # Always from yfinance
            'is_preferred': bool  # Always from yfinance
        }
    """
    metadata = {}

    # Step 1: Try KIS sector_code mapping (instant, no API call)
    if sector_code != '0' and sector_code in SECTOR_MAPPING:
        metadata['sector'] = SECTOR_MAPPING[sector_code]['gics_sector']
        metadata['industry_code'] = sector_code
        logger.info(f"✅ [{ticker}] Sector from KIS mapping: {metadata['sector']}")
    else:
        # Step 2: Fallback to yfinance for sector
        yf_data = yf.Ticker(ticker).info
        metadata['sector'] = yf_data.get('sector')
        metadata['industry_code'] = sector_code  # Keep original code
        logger.info(f"⚠️ [{ticker}] Sector from yfinance: {metadata['sector']}")

    # Step 3: Always get industry, SPAC, preferred from yfinance
    metadata['industry'] = yf_data.get('industry')
    metadata['is_spac'] = 'SPAC' in yf_data.get('longBusinessSummary', '')
    metadata['is_preferred'] = 'Preferred' in yf_data.get('quoteType', '')

    return metadata
```

### 4.3 Performance Optimization

**yfinance Call Reduction**:
- **Before (yfinance-only)**: 17,292 API calls for sector
- **After (hybrid)**:
  - KIS mapping: 7,831 stocks (46%) - **Instant, 0 API calls**
  - yfinance: 9,461 stocks (54%) - **API calls only**
  - **Net reduction**: ~8,000 fewer yfinance calls for sector field

**Still Require yfinance** (100% of stocks):
- industry text (not in master file)
- is_spac detection (not in master file)
- is_preferred detection (not in master file)

**Total yfinance API Calls**: Still 17,292 (for industry/SPAC/preferred), but sector processing is 46% faster

---

## 5. Implementation Plan

### 5.1 Phase 1: Core Infrastructure (Week 1) - **UPDATED for Hybrid**

**Tasks**:
1. ✅ **COMPLETED**: KIS sector_code → GICS mapping
   - `config/kis_sector_code_to_gics_mapping.json` (✅ Created)
   - 40 sector codes mapped to GICS 11
   - 46% instant coverage, 54% yfinance fallback

2. Create `modules/stock_metadata_enricher.py` (Hybrid Logic)
   - **Step 1**: Load KIS sector mapping from JSON
   - **Step 2**: Try sector_code → GICS mapping (instant)
   - **Step 3**: Fallback to yfinance for sector_code=0 or unmapped
   - **Step 4**: Always fetch industry/SPAC/preferred from yfinance
   - Batch processing (100 stocks/batch)
   - Rate limiting (1 req/sec for yfinance only)
   - Retry logic (3 attempts, exponential backoff)
   - Cache management (24-hour TTL)

3. Add `bulk_update_stock_details()` to db_manager_sqlite.py
   - Batch UPDATE operations
   - Transaction support
   - Row count validation

4. Create unit tests
   - `tests/test_metadata_enricher.py`
   - Test KIS mapping priority
   - Test yfinance fallback
   - Test batch processing, rate limiting, cache

**Deliverables**:
- ✅ KIS sector_code mapping JSON (COMPLETED)
- ✅ StockMetadataEnricher class with hybrid logic (100% unit test coverage)
- ✅ Bulk database update method
- ✅ Test suite passing (including hybrid workflow tests)

### 5.2 Phase 2: Adapter Integration (Week 2)

**Tasks**:
1. Add `enrich_stock_metadata()` to each adapter:
   - `us_adapter_kis.py`
   - `cn_adapter_kis.py`
   - `hk_adapter_kis.py`
   - `jp_adapter_kis.py`
   - `vn_adapter_kis.py`

2. Integration testing per region:
   - Test 10 sample stocks per region
   - Verify GICS mapping accuracy
   - Validate SPAC/preferred detection

**Deliverables**:
- ✅ 5 adapters enhanced
- ✅ Integration tests passing (50 stocks total)

### 5.3 Phase 3: Batch Enrichment (Week 3)

**Tasks**:
1. Create deployment script:
   - `scripts/enrich_global_metadata.py`
   - Region-by-region execution
   - Progress reporting
   - Error summary

2. Production deployment:
   - US: 6,388 stocks (~1.8 hours at 1 req/sec)
   - JP: 4,036 stocks (~1.1 hours)
   - CN: 3,450 stocks (~1.0 hour)
   - HK: 2,722 stocks (~45 minutes)
   - VN: 696 stocks (~12 minutes)
   - **Total**: ~4.8 hours (can run overnight)

3. Data quality validation:
   - Verify 100% coverage for all regions
   - Spot-check 100 random stocks for accuracy
   - Generate completion report

**Deliverables**:
- ✅ 17,292 stocks enriched (>95% success rate)
- ✅ Data quality report
- ✅ Performance metrics logged

### 5.4 Phase 4: Automation (Week 4)

**Tasks**:
1. Incremental enrichment logic:
   - Auto-detect new tickers (NULL sector)
   - Daily enrichment job (cron)

2. Monitoring and alerts:
   - Prometheus metrics for enrichment success rate
   - Grafana dashboard for coverage tracking
   - Alert if coverage drops below 95%

**Deliverables**:
- ✅ Automated daily enrichment
- ✅ Monitoring dashboard
- ✅ Alert configuration

---

## 6. Performance Optimization

### 6.1 Rate Limiting Strategy

**yfinance Constraints**:
- No official rate limit documentation
- Recommended: 1 req/sec to avoid IP bans
- Batch requests NOT supported

**Optimization**:
```python
# Bad: Sequential with delays
for ticker in tickers:
    data = yf.Ticker(ticker).info
    time.sleep(1)  # 17,292 seconds = 4.8 hours

# Good: Batched with intelligent retry
batch_size = 100
for batch in chunks(tickers, batch_size):
    results = []
    for ticker in batch:
        try:
            data = yf.Ticker(ticker).info
            results.append(data)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Retry {ticker}: {e}")
            # Retry with exponential backoff

    # Bulk database update (100 stocks/batch)
    db.bulk_update_stock_details(results)
```

### 6.2 Caching Strategy

**Cache Key**: `ticker_metadata:{region}:{ticker}`
**Cache TTL**: 24 hours
**Cache Storage**: SQLite table `metadata_cache`

**Schema**:
```sql
CREATE TABLE metadata_cache (
    ticker TEXT PRIMARY KEY,
    region TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    industry_code TEXT,
    is_spac BOOLEAN,
    is_preferred BOOLEAN,
    cached_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

**Benefit**: Avoid re-fetching metadata for recently enriched stocks.

### 6.3 Parallel Processing (Optional)

**Multi-Region Parallel Execution**:
```bash
# Run 5 regions in parallel (5 terminals or background processes)
python3 scripts/enrich_global_metadata.py --region US &
python3 scripts/enrich_global_metadata.py --region JP &
python3 scripts/enrich_global_metadata.py --region CN &
python3 scripts/enrich_global_metadata.py --region HK &
python3 scripts/enrich_global_metadata.py --region VN &

# Total time: ~1.8 hours (limited by US region)
```

---

## 7. Error Handling

### 7.1 Error Categories

| Error Type | Cause | Retry Strategy | Fallback |
|------------|-------|----------------|----------|
| **Network Timeout** | Slow yfinance response | 3 retries, exponential backoff | Skip ticker, log warning |
| **Rate Limit** | Too many requests | Wait 60 seconds, retry | N/A |
| **Invalid Ticker** | Delisted or invalid | No retry | Mark as inactive |
| **Missing Data** | yfinance returns NULL | No retry | Leave fields NULL |
| **Database Lock** | Concurrent writes | Retry 3 times | Fail batch, rollback |

### 7.2 Retry Logic

```python
def retry_with_backoff(func, max_retries=3, base_delay=1):
    """Exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {e}")
            time.sleep(delay)
```

### 7.3 Error Recovery

**Resumable Execution**:
```python
# Save progress after each batch
progress_file = 'data/enrichment_progress.json'

# Resume from last checkpoint
with open(progress_file, 'r') as f:
    progress = json.load(f)

processed_tickers = progress.get('processed', [])
remaining_tickers = [t for t in all_tickers if t not in processed_tickers]
```

---

## 8. Data Quality Validation

### 8.1 Validation Rules

| Field | Validation Rule | Action on Failure |
|-------|-----------------|-------------------|
| sector | Must be one of GICS 11 sectors | Log warning, set NULL |
| industry | Non-empty string | Allow NULL (yfinance may not have) |
| industry_code | Region-specific format | Allow NULL |
| is_spac | Boolean (0 or 1) | Default to 0 (False) |
| is_preferred | Boolean (0 or 1) | Default to 0 (False) |

### 8.2 Post-Enrichment Checks

```sql
-- Check coverage by region
SELECT
    t.region,
    COUNT(*) as total,
    SUM(CASE WHEN sd.sector IS NOT NULL THEN 1 ELSE 0 END) as has_sector,
    SUM(CASE WHEN sd.industry IS NOT NULL THEN 1 ELSE 0 END) as has_industry
FROM tickers t
INNER JOIN stock_details sd ON t.ticker = sd.ticker
WHERE t.asset_type = 'STOCK'
GROUP BY t.region;

-- Target: 100% sector coverage, >90% industry coverage
```

### 8.3 Sample Validation

**Spot Check 100 Random Stocks**:
```python
# US stocks
'AAPL' → Sector: 'Technology', Industry: 'Consumer Electronics'
'TSLA' → Sector: 'Consumer Cyclical', Industry: 'Auto Manufacturers'

# CN stocks
'600519' → Sector: 'Consumer Staples', Industry: '白酒制造' (Baijiu)
'000858' → Sector: 'Consumer Staples', Industry: '白酒制造' (Baijiu)

# SPAC detection
'AACB' → is_spac: True (ARTIUS II ACQUISITION INC)
'AACI' → is_spac: True (ARMADA ACQUISITION CORP II)

# Preferred stock detection
'AAL-PB' → is_preferred: True (American Airlines Preferred B)
```

---

## 9. Monitoring and Metrics

### 9.1 Prometheus Metrics

**New Metrics**:
```python
# Enrichment progress
spock_metadata_enrichment_total{region="US",status="success|failed"}
spock_metadata_enrichment_duration_seconds{region="US"}

# Coverage metrics
spock_stock_metadata_coverage_percent{region="US",field="sector|industry"}

# Cache metrics
spock_metadata_cache_hit_rate{region="US"}
spock_metadata_cache_size_total
```

### 9.2 Grafana Dashboard

**Panel 1: Enrichment Progress**
- Line chart: Enrichment rate (stocks/hour) by region
- Bar chart: Success vs failed enrichments

**Panel 2: Coverage Status**
- Gauge: Sector coverage % by region (target: 100%)
- Gauge: Industry coverage % by region (target: >90%)

**Panel 3: Cache Performance**
- Line chart: Cache hit rate (target: >80%)
- Bar chart: Cache size by region

---

## 10. Deployment Plan

### 10.1 Pre-Deployment Checklist

- [ ] Unit tests passing (modules/stock_metadata_enricher.py)
- [ ] Integration tests passing (50 stocks across 5 regions)
- [ ] Adapter methods implemented (5 adapters)
- [ ] Database migration (add metadata_cache table)
- [ ] Deployment script tested (scripts/enrich_global_metadata.py)
- [ ] Monitoring dashboard deployed
- [ ] Backup database before enrichment

### 10.2 Deployment Steps

**Step 1: Database Backup**
```bash
cp data/spock_local.db data/backups/spock_local_pre_enrichment_$(date +%Y%m%d).db
```

**Step 2: Deploy Code**
```bash
# Copy new modules
git pull origin main

# Verify dependencies
pip install -r requirements.txt
```

**Step 3: Run Enrichment (Overnight Job)**
```bash
# Option 1: Sequential (4.8 hours)
python3 scripts/enrich_global_metadata.py --all-regions

# Option 2: Parallel (1.8 hours)
./scripts/enrich_global_metadata_parallel.sh
```

**Step 4: Validation**
```bash
# Check coverage
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
print(db.get_sector_coverage_stats())"

# Expected output:
# {
#   'KR': {'total': 141, 'with_sector': 141, 'coverage_percent': 100.0},
#   'US': {'total': 6388, 'with_sector': 6388, 'coverage_percent': 100.0},
#   'JP': {'total': 4036, 'with_sector': 4036, 'coverage_percent': 100.0},
#   ...
# }
```

**Step 5: Monitoring**
```bash
# Start metrics exporter (if not running)
python3 monitoring/exporters/spock_exporter.py --port 8000

# Check Grafana dashboard
open http://localhost:3000/d/spock-metadata-enrichment
```

### 10.3 Rollback Plan

**If enrichment fails with <95% success rate**:
```bash
# Restore database backup
cp data/backups/spock_local_pre_enrichment_YYYYMMDD.db data/spock_local.db

# Review logs
tail -f logs/enrichment_YYYYMMDD.log

# Fix issues and retry
python3 scripts/enrich_global_metadata.py --region US --force-refresh
```

---

## 11. Future Enhancements

### 11.1 Advanced SPAC Detection

**Current**: Keyword matching in company name
**Future**: Real-time SPAC tracker API integration
- Data Source: spacresearch.com API
- Benefit: 100% accurate SPAC classification

### 11.2 Preferred Stock Detection

**Current**: Ticker suffix pattern matching (`-P`, ` PR`)
**Future**: KIS API preferred stock flag (if available)

### 11.3 Industry Code Standardization

**Current**: Region-specific codes (CSRC, TSE, ICB, etc.)
**Future**: Unified GICS industry codes (4-digit)
- Benefit: Cross-region industry comparison

### 11.4 Real-time Metadata Updates

**Current**: 24-hour cache TTL
**Future**: Webhook-based updates on corporate actions
- Trigger: Sector reclassification, SPAC merger completion

---

## 12. Risk Assessment

### 12.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| yfinance API rate limit | Medium | High | Implement 1 req/sec throttling, retry logic |
| Database lock during enrichment | Low | Medium | Use batch transactions, OFF-PEAK execution |
| Missing yfinance data for obscure stocks | Medium | Low | Allow NULL values, log warnings |
| GICS mapping errors (CN/HK/JP/VN) | Low | Medium | Validate with existing parsers, spot-check 100 stocks |

### 12.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Overnight job fails midway | Low | Medium | Resumable execution, progress checkpoints |
| IP ban from yfinance | Low | High | Rate limiting, distributed execution (if needed) |
| Data quality issues post-enrichment | Low | High | Pre-deployment testing on 50 stocks, validation SQL |

---

## 13. Success Criteria

### 13.1 Quantitative Metrics

- ✅ **Sector Coverage**: 100% for all regions (17,292 stocks)
- ✅ **Industry Coverage**: >90% for all regions
- ✅ **Enrichment Success Rate**: >95% (max 865 failures allowed)
- ✅ **Execution Time**: <5 hours for all regions
- ✅ **Cache Hit Rate**: >80% on subsequent runs
- ✅ **Zero Database Corruption**: Pre/post backup checksums match

### 13.2 Qualitative Metrics

- ✅ **Code Reusability**: 100% reuse of existing parsers (no new mapping logic)
- ✅ **Maintainability**: <300 lines of new code (StockMetadataEnricher)
- ✅ **Documentation**: This design doc + inline comments
- ✅ **Monitoring**: Grafana dashboard operational

---

## 14. Appendix

### 14.1 GICS 11 Sector List

1. Energy
2. Materials
3. Industrials
4. Consumer Discretionary
5. Consumer Staples
6. Health Care
7. Financials
8. Information Technology
9. Communication Services
10. Utilities
11. Real Estate

### 14.2 KIS Sector Code → GICS Mapping

**Mapping File**: `config/kis_sector_code_to_gics_mapping.json`

**Summary Statistics** (US Market):
- **Total US stocks**: 6,388
- **sector_code = 0** (Unclassified/SPAC): 3,461 (54.2%)
- **sector_code mapped**: 2,927 (45.8%)
- **Mapping coverage**: 40 unique KIS codes → GICS 11 sectors

**Sample Mappings**:
| KIS Code | GICS Sector | Description | Sample Tickers |
|----------|-------------|-------------|----------------|
| 10 | Energy | Oil & Gas | XOM, CVX, COP |
| 370 | Communication Services | Media & Entertainment | GOOGL, META, DIS |
| 520 | Health Care | Pharmaceuticals | JNJ, PFE, MRK |
| 610 | Financials | Banks | JPM, BAC, WFC |
| 710 | Information Technology | Semiconductors | NVDA, AMD, INTC |
| 720 | Information Technology | Software & IT Services | MSFT, ORCL, V |
| 730 | Information Technology | Technology Hardware | AAPL, DELL, HPQ |

**Usage**:
```python
import json

with open('config/kis_sector_code_to_gics_mapping.json') as f:
    mapping = json.load(f)

sector_code = "730"  # From master file
gics_sector = mapping['mapping'][sector_code]['gics_sector']
# → "Information Technology"
```

### 14.3 Sample Database Queries

**Get stocks without sector**:
```sql
SELECT t.region, COUNT(*) as missing_sector
FROM tickers t
INNER JOIN stock_details sd ON t.ticker = sd.ticker
WHERE t.asset_type = 'STOCK'
  AND (sd.sector IS NULL OR sd.sector = '')
GROUP BY t.region;
```

**Update single stock**:
```sql
UPDATE stock_details
SET sector = 'Technology',
    industry = 'Consumer Electronics',
    industry_code = '45301010',
    is_spac = 0,
    is_preferred = 0,
    last_updated = '2025-10-17T10:00:00'
WHERE ticker = 'AAPL';
```

### 14.3 File Structure

```
~/spock/
├── modules/
│   ├── stock_metadata_enricher.py       # NEW - Core enrichment engine
│   ├── db_manager_sqlite.py             # ENHANCED - Add bulk_update_stock_details()
│   └── market_adapters/
│       ├── us_adapter_kis.py            # ENHANCED - Add enrich_stock_metadata()
│       ├── cn_adapter_kis.py            # ENHANCED - Add enrich_stock_metadata()
│       ├── hk_adapter_kis.py            # ENHANCED - Add enrich_stock_metadata()
│       ├── jp_adapter_kis.py            # ENHANCED - Add enrich_stock_metadata()
│       └── vn_adapter_kis.py            # ENHANCED - Add enrich_stock_metadata()
├── scripts/
│   ├── enrich_global_metadata.py        # NEW - Deployment script
│   └── enrich_global_metadata_parallel.sh  # NEW - Parallel execution wrapper
├── tests/
│   └── test_metadata_enricher.py        # NEW - Unit tests
├── monitoring/
│   └── grafana/dashboards/
│       └── metadata_enrichment.json     # NEW - Grafana dashboard
└── docs/
    └── GLOBAL_STOCK_METADATA_ENRICHMENT_DESIGN.md  # This document
```

---

## 15. References

- **Phase 6 Completion Report**: `docs/PHASE6_COMPLETION_REPORT.md`
- **Global Adapter Design**: `docs/GLOBAL_ADAPTER_DESIGN.md`
- **Database Architecture**: `docs/GLOBAL_DB_ARCHITECTURE_ANALYSIS.md`
- **yfinance Documentation**: https://pypi.org/project/yfinance/
- **GICS Classification**: https://www.msci.com/our-solutions/indexes/gics
