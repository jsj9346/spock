# Stock Metadata Enricher Implementation Design

**Date**: 2025-10-17
**Module**: `modules/stock_metadata_enricher.py`
**Architecture**: KIS Master File + yfinance Hybrid
**Status**: Design Complete - Ready for Implementation

---

## 1. Executive Summary

### Purpose
Core metadata enrichment engine implementing hybrid KIS + yfinance architecture for 17,292 global stocks (US, CN, HK, JP, VN).

### Key Features
- **Hybrid Data Sources**: KIS sector_code (46% instant) → yfinance fallback (54%)
- **Batch Processing**: 100 stocks/batch with progress tracking
- **Rate Limiting**: 1 req/sec for yfinance API
- **Cache Management**: 24-hour TTL for enrichment results
- **Error Resilience**: Exponential backoff retry with circuit breaker
- **Database Integration**: Bulk updates via db_manager_sqlite.py

### Performance Targets
- **Throughput**: ~17,000 stocks in 4.8 hours (1 req/sec × 17,292 stocks)
- **Success Rate**: >95% enrichment completion
- **API Calls**: 9,461 yfinance calls (46% reduction via KIS mapping)
- **Cache Hit Rate**: >80% for repeated enrichment runs within 24 hours

---

## 2. Class Architecture

### 2.1 Main Class: `StockMetadataEnricher`

```python
class StockMetadataEnricher:
    """
    Hybrid metadata enrichment engine for global stocks.

    Architecture:
        Primary: KIS Master File sector_code → GICS mapping (46% instant)
        Secondary: yfinance API fallback (54% for sector, 100% for industry/SPAC/preferred)

    Usage:
        enricher = StockMetadataEnricher(db_manager, kis_api_client)

        # Enrich all global stocks
        results = enricher.enrich_all_regions(regions=['US', 'CN', 'HK', 'JP', 'VN'])

        # Enrich specific tickers
        results = enricher.enrich_tickers(tickers=['AAPL', 'MSFT'], region='US')

        # Incremental enrichment (only missing/stale data)
        results = enricher.enrich_incremental(region='US', max_age_days=30)
    """
```

### 2.2 Supporting Classes

```python
class EnrichmentCache:
    """
    24-hour TTL cache for enrichment results.
    Reduces redundant yfinance API calls.
    """

class RateLimiter:
    """
    Token bucket rate limiter for yfinance API.
    Target: 1 req/sec with burst capacity.
    """

class RetryHandler:
    """
    Exponential backoff retry logic with circuit breaker.
    Max retries: 3, Circuit breaker threshold: 5 consecutive failures.
    """
```

---

## 3. Core Methods Design

### 3.1 Constructor

```python
def __init__(
    self,
    db_manager: SQLiteDatabaseManager,
    kis_api_client: KISOverseasStockAPI,
    rate_limit: float = 1.0,  # yfinance: 1 req/sec
    batch_size: int = 100,
    cache_ttl_hours: int = 24,
    max_retries: int = 3
):
    """
    Initialize StockMetadataEnricher.

    Args:
        db_manager: SQLite database manager instance
        kis_api_client: KIS API client for master file access
        rate_limit: yfinance API rate limit (requests per second)
        batch_size: Number of stocks to process per batch
        cache_ttl_hours: Cache time-to-live in hours
        max_retries: Maximum retry attempts for failed API calls

    Initialization:
        1. Load KIS sector_code → GICS mapping from JSON
        2. Initialize yfinance rate limiter (1 req/sec)
        3. Setup enrichment cache (24-hour TTL)
        4. Configure retry handler with exponential backoff
        5. Initialize metrics tracking (success/fail counts)
    """
```

**Implementation Details**:
- Load `config/kis_sector_code_to_gics_mapping.json` into memory
- Validate mapping file structure (40 sector codes → GICS 11 sectors)
- Initialize token bucket rate limiter with 1 req/sec target
- Setup in-memory LRU cache with 24-hour expiration
- Configure logging with enrichment-specific logger

---

### 3.2 Primary Method: `enrich_single_stock()`

```python
def enrich_single_stock(
    self,
    ticker: str,
    region: str,
    sector_code: str,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Enrich metadata for a single stock using hybrid approach.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', '600519')
        region: Market region code (US, CN, HK, JP, VN)
        sector_code: KIS sector code from master file
        force_refresh: Skip cache and force yfinance API call

    Returns:
        {
            'ticker': str,
            'region': str,
            'sector': str,           # GICS sector name
            'sector_code': str,      # KIS sector code
            'industry': str,         # Detailed industry text
            'industry_code': str,    # Industry classification code
            'is_spac': bool,         # SPAC detection
            'is_preferred': bool,    # Preferred stock detection
            'data_source': str,      # 'kis_mapping' or 'yfinance'
            'enriched_at': datetime, # Timestamp
            'success': bool,         # Enrichment success flag
            'error': str             # Error message if failed
        }

    Workflow:
        1. Check cache for recent enrichment (skip if <24h old and not force_refresh)
        2. Try KIS sector_code mapping (instant, no API call)
           - If sector_code != '0' and exists in mapping:
             * Set sector from GICS mapping
             * Set data_source = 'kis_mapping'
        3. If KIS mapping failed, fallback to yfinance:
           - Apply rate limiting (1 req/sec)
           - Fetch yf.Ticker(ticker).info
           - Extract sector, industry, SPAC, preferred stock
           - Set data_source = 'yfinance'
        4. Handle errors with retry logic (max 3 attempts)
        5. Cache successful results (24-hour TTL)
        6. Return enrichment dictionary

    Error Handling:
        - KIS mapping not found → Log warning, proceed to yfinance
        - yfinance timeout → Retry with exponential backoff
        - yfinance 404 → Mark as 'ticker_not_found', skip retries
        - yfinance rate limit → Wait and retry
        - Circuit breaker → Skip after 5 consecutive failures

    Performance:
        - KIS mapping: <1ms (dictionary lookup)
        - yfinance API: ~500-1000ms per call (rate limited)
        - Cache hit: <1ms (in-memory lookup)
    """
```

**Implementation Notes**:
- **KIS Mapping Logic**: `sector_code in self.sector_mapping and sector_code != '0'`
- **yfinance Data Extraction**:
  ```python
  yf_data = yf.Ticker(ticker).info
  sector = yf_data.get('sector')
  industry = yf_data.get('industry')
  is_spac = 'SPAC' in yf_data.get('longBusinessSummary', '')
  is_preferred = 'Preferred' in yf_data.get('quoteType', '')
  ```
- **Cache Key Format**: `{region}:{ticker}:{sector_code}`
- **Rate Limiting**: Use token bucket with 1 token/sec refill rate

---

### 3.3 Batch Method: `enrich_batch()`

```python
def enrich_batch(
    self,
    tickers: List[str],
    region: str,
    sector_codes: Dict[str, str],
    force_refresh: bool = False
) -> BatchEnrichmentResult:
    """
    Enrich metadata for a batch of stocks.

    Args:
        tickers: List of ticker symbols
        region: Market region code
        sector_codes: Dictionary mapping ticker → sector_code
        force_refresh: Skip cache for all tickers

    Returns:
        BatchEnrichmentResult:
            - total: int (total stocks processed)
            - successful: int (successful enrichments)
            - failed: int (failed enrichments)
            - skipped: int (skipped due to cache/errors)
            - results: List[Dict] (enrichment results)
            - errors: List[Dict] (error details)
            - elapsed_time: float (processing time in seconds)
            - api_calls_made: int (yfinance API calls)
            - cache_hits: int (cache hit count)

    Workflow:
        1. Split tickers into batches of 100
        2. For each batch:
           a. Check cache for existing enrichments (<24h old)
           b. Separate into kis_mappable (sector_code != 0) and yfinance_required (sector_code = 0)
           c. Process kis_mappable first (instant, no API calls)
           d. Process yfinance_required with rate limiting (1 req/sec)
           e. Track metrics (success/fail/api_calls/cache_hits)
        3. Aggregate batch results
        4. Return BatchEnrichmentResult

    Progress Tracking:
        - Log progress every 10 stocks
        - Estimated time remaining based on current rate
        - Prometheus metrics: enrichment_rate, success_rate, api_latency

    Error Handling:
        - Individual failures don't stop batch processing
        - Circuit breaker activated after 5 consecutive failures
        - Failed tickers collected in errors list for retry
    """
```

**Batch Processing Optimization**:
- **KIS Mapping First**: Process all stocks with sector_code != 0 instantly
- **yfinance Rate Limited**: 1 req/sec for stocks with sector_code = 0
- **Progress Estimation**: `time_remaining = (total - processed) / rate`
- **Circuit Breaker**: Stop after 5 consecutive yfinance failures to prevent API ban

---

### 3.4 Region-Wide Method: `enrich_region()`

```python
def enrich_region(
    self,
    region: str,
    force_refresh: bool = False,
    incremental: bool = False,
    max_age_days: int = 30
) -> RegionEnrichmentResult:
    """
    Enrich all stocks in a specific region.

    Args:
        region: Market region code (US, CN, HK, JP, VN)
        force_refresh: Skip cache and re-enrich all stocks
        incremental: Only enrich missing/stale data
        max_age_days: Maximum age of enrichment data (for incremental mode)

    Returns:
        RegionEnrichmentResult:
            - region: str
            - total_stocks: int
            - enriched_stocks: int
            - failed_stocks: int
            - skipped_stocks: int
            - kis_mapping_used: int
            - yfinance_api_used: int
            - total_elapsed_time: float
            - average_time_per_stock: float

    Workflow:
        1. Query database for all tickers in region
        2. Retrieve existing enrichment status from stock_details
        3. If incremental mode:
           - Filter stocks with NULL metadata or enriched_at > max_age_days
        4. Load sector_code for each ticker from stock_details
        5. Process stocks in batches of 100
        6. Update database with bulk_update_stock_details()
        7. Return RegionEnrichmentResult

    SQL Query (Incremental Mode):
        SELECT ticker, sector_code, enriched_at
        FROM stock_details
        WHERE region = ?
          AND (
            sector IS NULL
            OR industry IS NULL
            OR enriched_at IS NULL
            OR enriched_at < datetime('now', '-' || ? || ' days')
          )

    Database Update Strategy:
        - Batch updates: 100 stocks per transaction
        - Use db_manager.bulk_update_stock_details()
        - Commit after each batch to prevent lock timeout

    Performance Estimates:
        - US (6,388 stocks): ~1.8 hours (46% KIS instant, 54% yfinance)
        - CN (3,450 stocks): ~1.0 hour
        - HK (2,722 stocks): ~0.75 hour
        - JP (4,036 stocks): ~1.1 hours
        - VN (696 stocks): ~0.2 hours
        - Total: ~4.8 hours for all regions
    """
```

**Incremental Mode Optimization**:
- Only process stocks with missing/stale metadata
- Skip stocks enriched within `max_age_days`
- Significantly reduces API calls for maintenance runs
- Example: Daily incremental run only processes ~50-100 new tickers

---

### 3.5 Master Method: `enrich_all_regions()`

```python
def enrich_all_regions(
    self,
    regions: List[str] = ['US', 'CN', 'HK', 'JP', 'VN'],
    force_refresh: bool = False,
    incremental: bool = False,
    max_age_days: int = 30,
    parallel: bool = False
) -> AllRegionsEnrichmentResult:
    """
    Enrich all stocks across multiple regions.

    Args:
        regions: List of region codes to process
        force_refresh: Skip cache and re-enrich all stocks
        incremental: Only enrich missing/stale data
        max_age_days: Maximum age of enrichment data (for incremental mode)
        parallel: Process regions in parallel (future enhancement)

    Returns:
        AllRegionsEnrichmentResult:
            - regions: List[RegionEnrichmentResult]
            - total_stocks: int
            - total_enriched: int
            - total_failed: int
            - total_elapsed_time: float
            - kis_mapping_percentage: float
            - yfinance_percentage: float
            - overall_success_rate: float

    Workflow:
        1. For each region in regions:
           a. Call enrich_region(region, force_refresh, incremental, max_age_days)
           b. Log progress and metrics
           c. Handle errors gracefully (don't stop processing other regions)
        2. Aggregate results across all regions
        3. Generate summary report
        4. Return AllRegionsEnrichmentResult

    Execution Order:
        - Sequential mode: Process regions one by one (default)
        - Parallel mode: Use multiprocessing to process regions concurrently (future)

    Error Handling:
        - Regional failures don't stop overall process
        - Collect errors per region for reporting
        - Continue to next region after circuit breaker activation

    Performance:
        - Sequential: ~4.8 hours for all 5 regions
        - Parallel (future): ~1.8 hours (limited by US region size)
    """
```

**Regional Processing Order** (Sequential):
1. US (largest, 6,388 stocks, ~1.8h)
2. JP (4,036 stocks, ~1.1h)
3. CN (3,450 stocks, ~1.0h)
4. HK (2,722 stocks, ~0.75h)
5. VN (smallest, 696 stocks, ~0.2h)

---

## 4. Helper Methods

### 4.1 `_load_sector_mapping()`

```python
def _load_sector_mapping(self) -> Dict[str, Dict]:
    """
    Load KIS sector_code → GICS mapping from JSON file.

    Returns:
        {
            '730': {
                'gics_sector': 'Information Technology',
                'description': 'Technology Hardware',
                'sample_tickers': ['AAPL', 'DELL', 'HPQ'],
                'coverage_pct': 1.4
            },
            ...
        }

    File Path: config/kis_sector_code_to_gics_mapping.json

    Validation:
        - Check file exists
        - Validate JSON structure
        - Ensure all sector codes are strings
        - Verify GICS sector names are valid (11 sectors)
        - Log mapping statistics (40 codes, 11 sectors)

    Error Handling:
        - FileNotFoundError → Log critical error, raise exception
        - JSON decode error → Log error, raise exception
        - Invalid mapping → Log warning, skip invalid entries
    """
```

### 4.2 `_fetch_yfinance_data()`

```python
def _fetch_yfinance_data(self, ticker: str, region: str) -> Dict:
    """
    Fetch metadata from yfinance API with rate limiting and retry.

    Args:
        ticker: Stock ticker symbol
        region: Market region code (for ticker normalization)

    Returns:
        {
            'sector': str,
            'industry': str,
            'is_spac': bool,
            'is_preferred': bool,
            'quote_type': str,
            'long_business_summary': str
        }

    Workflow:
        1. Normalize ticker for yfinance (e.g., HK: add .HK, CN: add .SS/.SZ)
        2. Apply rate limiting (wait for token)
        3. Call yf.Ticker(ticker).info
        4. Extract relevant fields
        5. Retry on failure (max 3 attempts)
        6. Return data dictionary

    Ticker Normalization:
        - US: Use as-is (e.g., 'AAPL')
        - HK: Add '.HK' suffix (e.g., '0700' → '0700.HK')
        - CN: Add '.SS' or '.SZ' based on exchange
        - JP: Add '.T' suffix (e.g., '7203' → '7203.T')
        - VN: Use as-is (e.g., 'VCB')

    SPAC Detection:
        - Check if 'SPAC' or 'Special Purpose Acquisition' in longBusinessSummary
        - Check if quoteType == 'SPAC'

    Preferred Stock Detection:
        - Check if 'Preferred' in quoteType
        - Check if ticker ends with '-P' or '.PR'

    Error Handling:
        - Rate limit error → Wait and retry
        - 404 Not Found → Return None (ticker doesn't exist)
        - Timeout → Retry with exponential backoff
        - Generic exception → Log error, return partial data
    """
```

### 4.3 `_normalize_ticker_for_yfinance()`

```python
def _normalize_ticker_for_yfinance(self, ticker: str, region: str) -> str:
    """
    Normalize ticker symbol for yfinance API.

    Args:
        ticker: Original ticker from database
        region: Market region code

    Returns:
        Normalized ticker for yfinance

    Normalization Rules:
        - US: No change (e.g., 'AAPL' → 'AAPL')
        - HK: Add '.HK' suffix (e.g., '0700' → '0700.HK')
        - CN: Add exchange suffix
          * Shanghai: '.SS' (e.g., '600000' → '600000.SS')
          * Shenzhen: '.SZ' (e.g., '000001' → '000001.SZ')
        - JP: Add '.T' suffix (e.g., '7203' → '7203.T')
        - VN: No change (e.g., 'VCB' → 'VCB')

    CN Exchange Detection:
        - 6xxxxx: Shanghai Stock Exchange (.SS)
        - 0xxxxx or 3xxxxx: Shenzhen Stock Exchange (.SZ)
    """
```

### 4.4 `_update_database_batch()`

```python
def _update_database_batch(self, enrichment_results: List[Dict]) -> int:
    """
    Update database with enriched metadata in batch.

    Args:
        enrichment_results: List of enrichment dictionaries

    Returns:
        Number of successfully updated records

    Workflow:
        1. Filter successful enrichments (success=True)
        2. Prepare bulk update data (ticker, region, sector, industry, etc.)
        3. Call db_manager.bulk_update_stock_details()
        4. Commit transaction
        5. Handle errors (log and continue)
        6. Return count of updated records

    SQL Update Pattern:
        UPDATE stock_details
        SET sector = ?,
            industry = ?,
            industry_code = ?,
            is_spac = ?,
            is_preferred = ?,
            enriched_at = ?
        WHERE ticker = ? AND region = ?

    Error Handling:
        - Database lock → Retry with backoff
        - Constraint violation → Log warning, skip record
        - Generic error → Log error, continue with next batch
    """
```

---

## 5. Data Structures

### 5.1 Enrichment Result

```python
@dataclass
class EnrichmentResult:
    """Single stock enrichment result."""
    ticker: str
    region: str
    sector: str
    sector_code: str
    industry: str
    industry_code: str
    is_spac: bool
    is_preferred: bool
    data_source: str  # 'kis_mapping' or 'yfinance'
    enriched_at: datetime
    success: bool
    error: Optional[str] = None
```

### 5.2 Batch Enrichment Result

```python
@dataclass
class BatchEnrichmentResult:
    """Batch enrichment summary."""
    total: int
    successful: int
    failed: int
    skipped: int
    results: List[EnrichmentResult]
    errors: List[Dict]
    elapsed_time: float
    api_calls_made: int
    cache_hits: int
```

### 5.3 Region Enrichment Result

```python
@dataclass
class RegionEnrichmentResult:
    """Region-wide enrichment summary."""
    region: str
    total_stocks: int
    enriched_stocks: int
    failed_stocks: int
    skipped_stocks: int
    kis_mapping_used: int
    yfinance_api_used: int
    total_elapsed_time: float
    average_time_per_stock: float
```

### 5.4 All Regions Enrichment Result

```python
@dataclass
class AllRegionsEnrichmentResult:
    """Multi-region enrichment summary."""
    regions: List[RegionEnrichmentResult]
    total_stocks: int
    total_enriched: int
    total_failed: int
    total_elapsed_time: float
    kis_mapping_percentage: float
    yfinance_percentage: float
    overall_success_rate: float
```

---

## 6. Configuration

### 6.1 Rate Limiting Configuration

```python
RATE_LIMITING_CONFIG = {
    'yfinance': {
        'requests_per_second': 1.0,
        'burst_capacity': 5,  # Allow 5 requests in burst
        'backoff_multiplier': 2.0,  # Exponential backoff
        'max_wait_time': 60.0  # Maximum wait time in seconds
    }
}
```

### 6.2 Cache Configuration

```python
CACHE_CONFIG = {
    'ttl_hours': 24,
    'max_entries': 20000,  # ~17,292 stocks + overhead
    'eviction_policy': 'LRU',  # Least Recently Used
    'persistence': False  # In-memory only
}
```

### 6.3 Retry Configuration

```python
RETRY_CONFIG = {
    'max_attempts': 3,
    'initial_delay': 1.0,  # 1 second
    'backoff_multiplier': 2.0,  # 1s, 2s, 4s
    'max_delay': 10.0,  # Maximum 10 seconds between retries
    'circuit_breaker_threshold': 5,  # Trip after 5 consecutive failures
    'circuit_breaker_timeout': 300  # Reset after 5 minutes
}
```

### 6.4 Batch Processing Configuration

```python
BATCH_CONFIG = {
    'batch_size': 100,
    'progress_log_interval': 10,  # Log every 10 stocks
    'database_commit_interval': 100,  # Commit every 100 stocks
    'parallel_regions': False  # Future enhancement
}
```

---

## 7. Error Handling Strategy

### 7.1 Error Categories

```python
class EnrichmentError(Exception):
    """Base exception for enrichment errors."""

class MappingNotFoundError(EnrichmentError):
    """KIS sector_code not found in mapping."""

class YFinanceError(EnrichmentError):
    """yfinance API error."""

class RateLimitError(YFinanceError):
    """yfinance rate limit exceeded."""

class TickerNotFoundError(YFinanceError):
    """Ticker not found on yfinance."""

class DatabaseError(EnrichmentError):
    """Database operation error."""
```

### 7.2 Error Recovery Actions

| Error Type | Recovery Action | Skip Ticker? |
|------------|-----------------|--------------|
| MappingNotFoundError | Fallback to yfinance | No |
| RateLimitError | Wait and retry (exponential backoff) | No |
| TickerNotFoundError | Log warning, mark as not_found | Yes |
| Timeout | Retry 3 times, then skip | Yes (after 3 retries) |
| CircuitBreakerOpen | Skip remaining batch, log critical | Yes (all in batch) |
| DatabaseError | Retry transaction, log error | No |

### 7.3 Circuit Breaker Logic

```python
class CircuitBreaker:
    """
    Circuit breaker for yfinance API failures.

    States:
        - CLOSED: Normal operation
        - OPEN: Failures exceeded threshold, block requests
        - HALF_OPEN: Test if service recovered

    Thresholds:
        - Failure threshold: 5 consecutive failures
        - Timeout: 5 minutes (300 seconds)
        - Success threshold (half-open): 2 consecutive successes

    Behavior:
        - CLOSED → OPEN: After 5 consecutive failures
        - OPEN → HALF_OPEN: After 5 minutes timeout
        - HALF_OPEN → CLOSED: After 2 consecutive successes
        - HALF_OPEN → OPEN: On failure
    """
```

---

## 8. Logging Strategy

### 8.1 Log Levels

```python
# INFO: Progress updates, successful enrichments
logger.info(f"Enriched {ticker} ({region}): sector={sector}, source={data_source}")

# WARNING: Fallback to yfinance, cache misses, retries
logger.warning(f"KIS mapping not found for {ticker} (sector_code={sector_code}), falling back to yfinance")

# ERROR: API failures, database errors, failed enrichments
logger.error(f"Failed to enrich {ticker} ({region}): {error}")

# CRITICAL: Circuit breaker activation, database corruption
logger.critical(f"Circuit breaker OPEN: 5 consecutive yfinance failures")
```

### 8.2 Structured Logging Format

```python
LOG_FORMAT = {
    'timestamp': '2025-10-17T10:30:45.123Z',
    'level': 'INFO',
    'module': 'stock_metadata_enricher',
    'method': 'enrich_single_stock',
    'ticker': 'AAPL',
    'region': 'US',
    'data_source': 'kis_mapping',
    'elapsed_ms': 12,
    'message': 'Enrichment successful'
}
```

### 8.3 Metrics Logging

```python
# Log metrics every 100 stocks
logger.info(f"""
Enrichment Progress:
  Processed: {processed}/{total} ({processed/total*100:.1f}%)
  Successful: {successful} ({successful/processed*100:.1f}%)
  Failed: {failed} ({failed/processed*100:.1f}%)
  KIS Mapping: {kis_count} ({kis_count/processed*100:.1f}%)
  yfinance API: {yf_count} ({yf_count/processed*100:.1f}%)
  Cache Hits: {cache_hits} ({cache_hits/processed*100:.1f}%)
  Elapsed: {elapsed:.1f}s
  Rate: {processed/elapsed:.1f} stocks/sec
  Estimated Remaining: {(total-processed)/(processed/elapsed)/60:.1f} min
""")
```

---

## 9. Integration Points

### 9.1 Database Manager Integration

```python
# Required new method in db_manager_sqlite.py
def bulk_update_stock_details(
    self,
    updates: List[Dict[str, Any]]
) -> int:
    """
    Bulk update stock_details table.

    Args:
        updates: List of update dictionaries
            [
                {
                    'ticker': 'AAPL',
                    'region': 'US',
                    'sector': 'Information Technology',
                    'industry': 'Consumer Electronics',
                    'industry_code': 'GICS45203010',
                    'is_spac': False,
                    'is_preferred': False,
                    'enriched_at': datetime.now()
                },
                ...
            ]

    Returns:
        Number of successfully updated records

    Implementation:
        - Use executemany() for batch updates
        - Wrap in transaction for atomicity
        - Handle constraint violations gracefully
    """
```

### 9.2 Market Adapter Integration

```python
# Required new method in base_adapter.py and all market adapters
def enrich_stock_metadata(
    self,
    tickers: Optional[List[str]] = None,
    force_refresh: bool = False,
    incremental: bool = False,
    max_age_days: int = 30
) -> RegionEnrichmentResult:
    """
    Enrich metadata for stocks in this region.

    Args:
        tickers: Optional list of specific tickers (None = all tickers)
        force_refresh: Skip cache and re-enrich all
        incremental: Only enrich missing/stale data
        max_age_days: Maximum age for incremental mode

    Returns:
        RegionEnrichmentResult with enrichment summary

    Implementation:
        1. Initialize StockMetadataEnricher
        2. Retrieve sector_code for tickers from database
        3. Call enricher.enrich_batch() or enricher.enrich_region()
        4. Return results
    """
```

### 9.3 KIS API Integration

```python
# Already exists in KISOverseasStockAPI
def get_tickers_with_details(
    self,
    region: str,
    force_refresh: bool = False
) -> List[Dict]:
    """
    Returns ticker dictionaries with metadata including sector_code.

    Returns:
        [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'sector_code': '730',  # ← Used by enricher
                'exchange': 'NASD',
                ...
            },
            ...
        ]
    """
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_metadata_enricher.py

def test_kis_mapping_success():
    """Test successful KIS sector_code mapping."""
    # sector_code = '730' → 'Information Technology'

def test_yfinance_fallback():
    """Test yfinance fallback when sector_code = 0."""

def test_cache_hit():
    """Test cache returns cached data within 24 hours."""

def test_cache_miss():
    """Test cache miss triggers fresh enrichment."""

def test_rate_limiting():
    """Test rate limiter enforces 1 req/sec."""

def test_retry_logic():
    """Test exponential backoff retry on transient errors."""

def test_circuit_breaker():
    """Test circuit breaker opens after 5 failures."""

def test_batch_processing():
    """Test batch processing with mixed success/failure."""

def test_database_update():
    """Test bulk database update."""

def test_ticker_normalization():
    """Test ticker normalization for each region."""
```

### 10.2 Integration Tests

```python
def test_enrich_single_stock_e2e():
    """End-to-end test for single stock enrichment."""

def test_enrich_region_us():
    """Test enriching entire US region (~6,000 stocks, sample)."""

def test_incremental_enrichment():
    """Test incremental mode only processes missing data."""

def test_all_regions_enrichment():
    """Test enriching all 5 regions (sample of 10 stocks per region)."""
```

### 10.3 Performance Tests

```python
def test_kis_mapping_performance():
    """Test KIS mapping is <1ms per stock."""

def test_yfinance_rate_limiting():
    """Test yfinance calls respect 1 req/sec limit."""

def test_batch_throughput():
    """Test batch processing achieves >1 stock/sec throughput."""
```

---

## 11. Deployment Workflow

### 11.1 Initial Deployment

```bash
# Step 1: Implement stock_metadata_enricher.py
touch modules/stock_metadata_enricher.py
# (Implement based on this design)

# Step 2: Add bulk_update_stock_details() to db_manager_sqlite.py
# (Edit existing file)

# Step 3: Create deployment script
cat > scripts/enrich_global_metadata.py << 'EOF'
#!/usr/bin/env python3
"""
Global stock metadata enrichment deployment script.

Usage:
    # Test with dry run
    python3 scripts/enrich_global_metadata.py --dry-run --limit 10

    # Enrich specific region
    python3 scripts/enrich_global_metadata.py --region US

    # Enrich all regions (full deployment, ~4.8 hours)
    python3 scripts/enrich_global_metadata.py --all-regions

    # Incremental enrichment (daily maintenance)
    python3 scripts/enrich_global_metadata.py --all-regions --incremental --max-age-days 30
"""
EOF

# Step 4: Run unit tests
pytest tests/test_metadata_enricher.py -v

# Step 5: Run integration tests with sample data (10 stocks per region)
python3 scripts/enrich_global_metadata.py --test --limit 10

# Step 6: Backup database before full deployment
cp data/spock_local.db data/backups/spock_local_pre_enrichment_$(date +%Y%m%d).db

# Step 7: Full deployment (overnight recommended, ~4.8 hours)
nohup python3 scripts/enrich_global_metadata.py --all-regions > logs/enrichment_$(date +%Y%m%d).log 2>&1 &

# Step 8: Monitor progress
tail -f logs/enrichment_$(date +%Y%m%d).log

# Step 9: Verify completion
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()
cursor.execute('''
    SELECT region,
           COUNT(*) as total,
           SUM(CASE WHEN sector IS NOT NULL THEN 1 ELSE 0 END) as with_sector,
           SUM(CASE WHEN industry IS NOT NULL THEN 1 ELSE 0 END) as with_industry
    FROM stock_details
    WHERE region IN ('US', 'CN', 'HK', 'JP', 'VN')
    GROUP BY region
''')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[2]}/{row[1]} sector, {row[3]}/{row[1]} industry')
conn.close()
"
```

### 11.2 Maintenance (Daily Incremental Enrichment)

```bash
# Cron job: Run daily at 2:00 AM KST
0 2 * * * cd ~/spock && python3 scripts/enrich_global_metadata.py --all-regions --incremental --max-age-days 1
```

### 11.3 Manual Re-Enrichment

```bash
# Force refresh specific region (ignore cache)
python3 scripts/enrich_global_metadata.py --region US --force-refresh

# Re-enrich failed tickers only
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager()
conn = db._get_connection()
cursor = conn.cursor()
cursor.execute('SELECT ticker FROM stock_details WHERE region=\"US\" AND sector IS NULL')
failed_tickers = [row[0] for row in cursor.fetchall()]
conn.close()
print('\n'.join(failed_tickers))
" > /tmp/failed_us_tickers.txt

python3 scripts/enrich_global_metadata.py --region US --tickers-file /tmp/failed_us_tickers.txt
```

---

## 12. Success Criteria

### 12.1 Functional Requirements

| Requirement | Target | Validation |
|-------------|--------|------------|
| Sector Coverage | 100% (17,292 stocks) | All stocks have sector value |
| Industry Coverage | >90% | >15,500 stocks with industry |
| Success Rate | >95% | <5% failed enrichments |
| KIS Mapping Coverage | 46% instant | ~7,800 stocks via KIS mapping |
| yfinance Coverage | 54% | ~9,500 stocks via yfinance |
| Data Source Tracking | 100% | All enrichments tagged with source |

### 12.2 Performance Requirements

| Metric | Target | Validation |
|--------|--------|------------|
| KIS Mapping Speed | <1ms per stock | Timing measurement |
| yfinance API Speed | ~1 req/sec | Rate limiter logs |
| Total Enrichment Time | <5 hours | End-to-end timing |
| Cache Hit Rate | >80% | Cache statistics |
| Database Update Speed | >100 stocks/sec | Bulk update timing |

### 12.3 Quality Requirements

| Metric | Target | Validation |
|--------|--------|------------|
| GICS Sector Accuracy | 100% | Manual spot check 100 stocks |
| Industry Text Accuracy | >95% | Manual spot check 100 stocks |
| SPAC Detection Accuracy | >90% | Cross-reference with known SPACs |
| Preferred Stock Detection | >90% | Cross-reference with known preferred |
| Mapping File Coverage | 40 codes → 11 sectors | JSON validation |

---

## 13. Next Steps

### 13.1 Phase 1: Core Implementation (Week 1)

**Deliverables**:
- [ ] Implement `modules/stock_metadata_enricher.py` (this design)
- [ ] Add `bulk_update_stock_details()` to `modules/db_manager_sqlite.py`
- [ ] Create `tests/test_metadata_enricher.py` with 15+ unit tests
- [ ] Validate KIS sector_code mapping with sample stocks

**Success Criteria**:
- All unit tests pass (>95% coverage)
- Single stock enrichment <2 seconds (KIS mapping <1ms, yfinance ~1s)
- Batch processing achieves >1 stock/sec throughput

### 13.2 Phase 2: Adapter Integration (Week 2)

**Deliverables**:
- [ ] Add `enrich_stock_metadata()` to 5 market adapters
  - USAdapterKIS, CNAdapterKIS, HKAdapterKIS, JPAdapterKIS, VNAdapterKIS
- [ ] Create integration tests with real API data (sample: 10 stocks per region)
- [ ] Validate GICS sector mapping accuracy (manual spot check)

**Success Criteria**:
- Integration tests pass for all 5 adapters
- GICS mapping accuracy >95% (spot check 100 stocks)
- API error handling works (rate limits, timeouts)

### 13.3 Phase 3: Batch Deployment (Week 3)

**Deliverables**:
- [ ] Create `scripts/enrich_global_metadata.py` deployment script
- [ ] Run overnight enrichment for all 5 regions (~4.8 hours)
- [ ] Validate data quality (100% sector coverage, >90% industry coverage)
- [ ] Setup daily incremental enrichment cron job

**Success Criteria**:
- All 17,292 stocks enriched successfully
- Success rate >95%
- Database validation: 0 NULL sectors, >90% industries populated

### 13.4 Phase 4: Monitoring & Automation (Week 4)

**Deliverables**:
- [ ] Add Prometheus metrics (enrichment_rate, success_rate, data_source_ratio)
- [ ] Create Grafana dashboard for enrichment monitoring
- [ ] Setup alerts for enrichment failures (>5% failure rate)
- [ ] Implement automated daily incremental enrichment

**Success Criteria**:
- Prometheus metrics collecting data
- Grafana dashboard visualizing enrichment status
- Alerts trigger on failures
- Daily incremental runs complete automatically

---

## 14. File Checklist

### 14.1 New Files to Create

- [ ] `modules/stock_metadata_enricher.py` (main module, ~800 lines)
- [ ] `tests/test_metadata_enricher.py` (unit tests, ~400 lines)
- [ ] `scripts/enrich_global_metadata.py` (deployment script, ~300 lines)

### 14.2 Files to Modify

- [ ] `modules/db_manager_sqlite.py` (add `bulk_update_stock_details()` method)
- [ ] `modules/market_adapters/us_adapter_kis.py` (add `enrich_stock_metadata()`)
- [ ] `modules/market_adapters/cn_adapter_kis.py` (add `enrich_stock_metadata()`)
- [ ] `modules/market_adapters/hk_adapter_kis.py` (add `enrich_stock_metadata()`)
- [ ] `modules/market_adapters/jp_adapter_kis.py` (add `enrich_stock_metadata()`)
- [ ] `modules/market_adapters/vn_adapter_kis.py` (add `enrich_stock_metadata()`)

### 14.3 Existing Files (Reference Only)

- ✅ `config/kis_sector_code_to_gics_mapping.json` (already created)
- ✅ `modules/api_clients/kis_overseas_stock_api.py` (already has sector_code)
- ✅ `modules/api_clients/kis_master_file_manager.py` (already extracts sector_code)
- ✅ `docs/GLOBAL_STOCK_METADATA_ENRICHMENT_DESIGN.md` (already created)
- ✅ `docs/HYBRID_METADATA_ENRICHMENT_SUMMARY.md` (already created)

---

## 15. Risk Assessment

### 15.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| yfinance API changes | Medium | High | Cache results, fallback to alternative sources |
| Rate limit violations | Low | Medium | Token bucket rate limiter, exponential backoff |
| Database lock timeout | Medium | Low | Batch commits, retry logic |
| Mapping file inaccuracy | Low | Medium | Manual validation, spot checks |
| Memory overflow (large batch) | Low | Low | Batch size limit (100 stocks) |

### 15.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Long enrichment time (>5h) | Low | Low | Overnight execution, progress monitoring |
| Failed enrichment (<95%) | Medium | Medium | Retry logic, manual investigation |
| Incomplete data (industry <90%) | Low | Medium | yfinance fallback, quarterly re-enrichment |
| Cache invalidation issues | Low | Low | 24-hour TTL, manual cache clear |

### 15.3 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Incorrect GICS classification | Low | Medium | Manual spot checks, user feedback |
| SPAC detection false positives | Medium | Low | Conservative detection criteria |
| Preferred stock misclassification | Low | Low | Cross-reference with official data |

---

## 16. Monitoring & Observability

### 16.1 Prometheus Metrics

```python
# Enrichment progress
spock_enrichment_total = Counter('spock_enrichment_total', 'Total enrichments attempted', ['region'])
spock_enrichment_success = Counter('spock_enrichment_success', 'Successful enrichments', ['region', 'data_source'])
spock_enrichment_failed = Counter('spock_enrichment_failed', 'Failed enrichments', ['region', 'error_type'])

# Performance metrics
spock_enrichment_duration_seconds = Histogram('spock_enrichment_duration_seconds', 'Enrichment duration', ['region', 'data_source'])
spock_yfinance_api_latency_seconds = Histogram('spock_yfinance_api_latency_seconds', 'yfinance API latency')
spock_database_update_duration_seconds = Histogram('spock_database_update_duration_seconds', 'Database batch update duration')

# Data quality metrics
spock_kis_mapping_coverage = Gauge('spock_kis_mapping_coverage', 'Percentage of stocks using KIS mapping', ['region'])
spock_yfinance_coverage = Gauge('spock_yfinance_coverage', 'Percentage of stocks using yfinance', ['region'])
spock_sector_coverage_percentage = Gauge('spock_sector_coverage_percentage', 'Sector coverage percentage', ['region'])
spock_industry_coverage_percentage = Gauge('spock_industry_coverage_percentage', 'Industry coverage percentage', ['region'])

# Cache metrics
spock_cache_hits = Counter('spock_cache_hits', 'Cache hits')
spock_cache_misses = Counter('spock_cache_misses', 'Cache misses')
spock_cache_hit_rate = Gauge('spock_cache_hit_rate', 'Cache hit rate percentage')
```

### 16.2 Grafana Dashboard Panels

```yaml
Dashboard: Stock Metadata Enrichment

Panel 1: Enrichment Progress
  - Gauge: Total enriched / Total stocks
  - Target: 17,292 stocks
  - Current: Real-time count

Panel 2: Success Rate by Region
  - Bar chart: Success percentage per region
  - Target line: 95%
  - Colors: Green (>95%), Yellow (90-95%), Red (<90%)

Panel 3: Data Source Distribution
  - Pie chart: KIS mapping (46%) vs yfinance (54%)
  - Actual percentages updated in real-time

Panel 4: Enrichment Rate
  - Time series: Stocks/second enrichment rate
  - Target line: 1 stock/sec average

Panel 5: API Latency (yfinance)
  - Heatmap: p50, p95, p99 latencies
  - Alert threshold: p95 > 2 seconds

Panel 6: Error Distribution
  - Table: Error type, count, percentage
  - Top 5 errors highlighted

Panel 7: Coverage by Region
  - Stacked bar: Sector coverage, Industry coverage
  - Target: 100% sector, 90% industry

Panel 8: Cache Performance
  - Time series: Cache hit rate
  - Target: >80%
```

### 16.3 Alert Rules

```yaml
- alert: EnrichmentSuccessRateLow
  expr: spock_enrichment_success / spock_enrichment_total < 0.95
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Enrichment success rate below 95%"

- alert: EnrichmentFailureRateHigh
  expr: rate(spock_enrichment_failed[5m]) > 0.1
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Enrichment failure rate exceeds 10%"

- alert: YFinanceAPILatencyHigh
  expr: histogram_quantile(0.95, spock_yfinance_api_latency_seconds) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "yfinance API p95 latency > 2 seconds"

- alert: CacheHitRateLow
  expr: spock_cache_hit_rate < 0.8
  for: 30m
  labels:
    severity: info
  annotations:
    summary: "Cache hit rate below 80%"
```

---

## 17. Documentation

### 17.1 Module Docstring

```python
"""
Stock Metadata Enricher - Hybrid KIS + yfinance Architecture

Purpose:
    Enrich global stock metadata (sector, industry, SPAC, preferred stock) for
    17,292 stocks across 5 regions (US, CN, HK, JP, VN) using a hybrid approach:

    - Primary: KIS Master File sector_code → GICS mapping (46% instant)
    - Secondary: yfinance API fallback (54% for sector, 100% for industry/SPAC/preferred)

Performance:
    - Total Stocks: 17,292 (US: 6,388, JP: 4,036, CN: 3,450, HK: 2,722, VN: 696)
    - Enrichment Time: ~4.8 hours (yfinance rate limited to 1 req/sec)
    - API Call Reduction: ~8,000 fewer yfinance calls (46% via KIS mapping)
    - Success Rate Target: >95%

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │ Stock Metadata Enricher                                         │
    │                                                                 │
    │ Step 1: Load KIS sector_code from database (100% coverage)     │
    │ Step 2: Try KIS sector_code → GICS mapping (46% instant)       │
    │ Step 3: Fallback to yfinance API (54% for sector, 100% other)  │
    │ Step 4: Update database with bulk_update_stock_details()       │
    └─────────────────────────────────────────────────────────────────┘

    Data Flow:
        stock_details.sector_code → kis_sector_code_to_gics_mapping.json
                                  → GICS sector name (instant, no API)

        yfinance fallback → yf.Ticker(ticker).info
                         → sector, industry, SPAC, preferred

Usage:
    from modules.stock_metadata_enricher import StockMetadataEnricher
    from modules.db_manager_sqlite import SQLiteDatabaseManager
    from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI

    # Initialize
    db = SQLiteDatabaseManager()
    kis_api = KISOverseasStockAPI(app_key, app_secret)
    enricher = StockMetadataEnricher(db, kis_api)

    # Enrich all regions (full deployment, ~4.8 hours)
    results = enricher.enrich_all_regions(regions=['US', 'CN', 'HK', 'JP', 'VN'])

    # Incremental enrichment (daily maintenance, <5 minutes)
    results = enricher.enrich_all_regions(incremental=True, max_age_days=1)

    # Enrich specific region
    results = enricher.enrich_region(region='US')

    # Enrich specific tickers
    results = enricher.enrich_tickers(tickers=['AAPL', 'MSFT'], region='US')

Configuration:
    - Mapping File: config/kis_sector_code_to_gics_mapping.json (40 codes)
    - Rate Limit: 1 req/sec for yfinance API
    - Batch Size: 100 stocks per batch
    - Cache TTL: 24 hours
    - Max Retries: 3 attempts with exponential backoff

Author: Spock Team
Created: 2025-10-17
Version: 1.0.0
"""
```

### 17.2 README.md Section

```markdown
## Stock Metadata Enrichment

### Overview
Automated enrichment of global stock metadata (sector, industry, SPAC detection, preferred stock detection) using a hybrid KIS Master File + yfinance architecture.

### Quick Start

```bash
# Test with dry run (10 stocks)
python3 scripts/enrich_global_metadata.py --dry-run --limit 10

# Enrich all regions (full deployment, ~4.8 hours)
python3 scripts/enrich_global_metadata.py --all-regions

# Daily incremental enrichment (<5 minutes)
python3 scripts/enrich_global_metadata.py --all-regions --incremental --max-age-days 1

# Enrich specific region
python3 scripts/enrich_global_metadata.py --region US

# Enrich specific tickers
python3 scripts/enrich_global_metadata.py --region US --tickers AAPL MSFT GOOGL
```

### Architecture
- **Primary**: KIS sector_code → GICS mapping (46% instant, 0 API calls)
- **Secondary**: yfinance API (54% for sector, 100% for industry/SPAC/preferred)

### Performance
- Total: 17,292 stocks across 5 regions
- Time: ~4.8 hours (1 req/sec yfinance rate limit)
- API Calls: ~9,500 (46% reduction via KIS mapping)
- Success Rate: >95% target

### Monitoring
- Grafana Dashboard: http://localhost:3000/d/enrichment
- Prometheus Metrics: http://localhost:9090
- Logs: `logs/enrichment_YYYYMMDD.log`

### Documentation
- Design: `docs/GLOBAL_STOCK_METADATA_ENRICHMENT_DESIGN.md`
- Implementation: `docs/STOCK_METADATA_ENRICHER_IMPLEMENTATION_DESIGN.md`
- Summary: `docs/HYBRID_METADATA_ENRICHMENT_SUMMARY.md`
```

---

## 18. Appendix

### 18.1 KIS Sector Code Reference

See `config/kis_sector_code_to_gics_mapping.json` for complete mapping (40 codes).

**Sample Mappings**:
- `730`: Information Technology (Technology Hardware)
- `610`: Financials (Banks)
- `520`: Health Care (Pharmaceuticals)
- `370`: Communication Services (Media & Entertainment)
- `10`: Energy (Oil & Gas)

### 18.2 GICS 11 Sector Reference

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

### 18.3 yfinance Data Fields

```python
yf_data = yf.Ticker('AAPL').info

# Relevant fields:
{
    'sector': 'Technology',                    # GICS sector (may differ from KIS)
    'industry': 'Consumer Electronics',        # Detailed industry
    'industryKey': 'consumer-electronics',     # Industry key
    'quoteType': 'EQUITY',                     # EQUITY, PREFERRED, SPAC, etc.
    'longBusinessSummary': '...',              # Business description
    'shortName': 'Apple Inc.',                 # Company name
    'symbol': 'AAPL',                          # Ticker symbol
    ...
}
```

### 18.4 Regional Ticker Normalization

| Region | Input Format | yfinance Format | Example |
|--------|--------------|-----------------|---------|
| US | AAPL | AAPL | AAPL → AAPL |
| HK | 0700 | 0700.HK | 0700 → 0700.HK |
| CN (SH) | 600519 | 600519.SS | 600519 → 600519.SS |
| CN (SZ) | 000858 | 000858.SZ | 000858 → 000858.SZ |
| JP | 7203 | 7203.T | 7203 → 7203.T |
| VN | VCB | VCB | VCB → VCB |

### 18.5 Implementation Checklist

**Phase 1: Core Implementation (Week 1)**
- [ ] Create `modules/stock_metadata_enricher.py`
- [ ] Implement `StockMetadataEnricher` class
- [ ] Implement `enrich_single_stock()` method
- [ ] Implement `enrich_batch()` method
- [ ] Implement `enrich_region()` method
- [ ] Implement `enrich_all_regions()` method
- [ ] Implement helper methods (_load_sector_mapping, _fetch_yfinance_data, etc.)
- [ ] Add `bulk_update_stock_details()` to `db_manager_sqlite.py`
- [ ] Create `tests/test_metadata_enricher.py`
- [ ] Write 15+ unit tests

**Phase 2: Adapter Integration (Week 2)**
- [ ] Add `enrich_stock_metadata()` to `USAdapterKIS`
- [ ] Add `enrich_stock_metadata()` to `CNAdapterKIS`
- [ ] Add `enrich_stock_metadata()` to `HKAdapterKIS`
- [ ] Add `enrich_stock_metadata()` to `JPAdapterKIS`
- [ ] Add `enrich_stock_metadata()` to `VNAdapterKIS`
- [ ] Create integration tests
- [ ] Validate GICS mapping accuracy

**Phase 3: Batch Deployment (Week 3)**
- [ ] Create `scripts/enrich_global_metadata.py`
- [ ] Backup database
- [ ] Run overnight enrichment
- [ ] Validate data quality
- [ ] Setup cron job for daily incremental

**Phase 4: Monitoring (Week 4)**
- [ ] Add Prometheus metrics
- [ ] Create Grafana dashboard
- [ ] Setup alerts
- [ ] Implement automated enrichment

---

**Design Complete**: 2025-10-17
**Next Step**: Implement `modules/stock_metadata_enricher.py` (Phase 1, Week 1)
**Estimated Implementation Time**: 4 weeks (design complete, ready for coding)
