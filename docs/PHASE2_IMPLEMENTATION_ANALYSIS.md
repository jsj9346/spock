# Phase 2 Implementation Analysis: Unified DB Update System

**Date**: 2025-11-02  
**Analyst**: Claude Code  
**Status**: Ready for Implementation

---

## Executive Summary

### Phase 2 Scope
Complete the unified database update orchestrator by implementing three critical gaps:

1. **Task 1: KR Ticker Updater** (`scripts/update_kr_tickers.py`) - NEW FILE
2. **Task 2: OHLCV Integration** - MODIFY `kis_data_collector.py` + orchestrator integration
3. **Task 3: Quarterly Financials** (Optional) - NEW FILE

### Implementation Readiness: ✅ **95% Ready**

**Key Findings**:
- Phase 1 orchestrator infrastructure is complete and working
- Clear patterns exist from `backfill_fundamentals_dart.py` and `calculate_dividend_yield.py`
- `kis_data_collector.py` already has 90% of needed functionality
- pykrx patterns well-established in codebase

**Estimated Effort**: 6-8 hours total
- Task 1: 2-3 hours
- Task 2: 2-3 hours  
- Task 3: 2 hours (optional)

---

## 1. Current State Analysis

### 1.1 Phase 1 Infrastructure (Complete ✅)

**File**: `/Users/13ruce/spock/modules/orchestration/orchestrator.py`

**Key Features**:
- `DatabaseUpdateOrchestrator` class with 5-step pipeline
- Checkpoint-based recovery (`CheckpointManager`)
- Multi-region support (KR, US, HK, JP, CN, VN)
- Rate limiting (`MultiRateLimiter`)
- Data quality validation (`DataQualityValidator`)
- Dry-run and incremental modes

**Step Execution Order**:
```python
STEP_ORDER = [
    'tickers',      # ⚠️ KR region not implemented
    'ohlcv',        # ⚠️ Placeholder, needs kis_data_collector integration
    'fundamentals', # ✅ Complete (DARTFundamentalBackfiller)
    'dividend',     # ✅ Complete (DividendYieldCalculator)
    'quarterly'     # ❌ Not implemented
]
```

### 1.2 Integration Patterns from Existing Scripts

**Pattern A: External Script with `run()` Method** (DARTFundamentalBackfiller)

```python
# File: scripts/backfill_fundamentals_dart.py
class DARTFundamentalBackfiller:
    def __init__(self, db, dart, dry_run=False, rate_limit_delay=1.0):
        self.db = db
        self.dart = dart
        self.dry_run = dry_run
        self.stats = {...}
    
    def run_backfill(self, incremental=False, limit=None) -> Dict:
        """Main entry point called by orchestrator"""
        # 1. Load tickers
        # 2. Process each ticker
        # 3. Return statistics
        return {
            'tickers_success': ...,
            'tickers_failed': ...,
            'records_inserted': ...
        }

# Orchestrator integration:
def _update_fundamentals(self, regions, **kwargs):
    dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))
    backfiller = DARTFundamentalBackfiller(self.db, dart, dry_run=kwargs.get('dry_run'))
    result = backfiller.run_backfill(incremental=kwargs.get('incremental'))
    return results
```

**Pattern B: Integrated Calculator** (DividendYieldCalculator)

```python
# File: scripts/calculate_dividend_yield.py
class DividendYieldCalculator:
    def __init__(self, db, dry_run=False):
        self.db = db
        self.dry_run = dry_run
        self.stats = {...}
    
    def calculate_all_tickers(self) -> Dict:
        """Main entry point"""
        # 1. Query tickers with dividend data
        # 2. Calculate yield for each
        # 3. Return statistics
        return self.stats

# Orchestrator integration:
def _calculate_dividend(self, regions, **kwargs):
    calculator = DividendYieldCalculator(self.db, dry_run=kwargs.get('dry_run'))
    result = calculator.calculate_all_tickers()
    return results
```

**Pattern C: Data Collector with Filtering** (kis_data_collector.py - Current)

```python
# File: modules/kis_data_collector.py
class KISDataCollector:
    def __init__(self, db_path='data/spock_local.db', region='KR'):
        self.db_path = db_path
        self.region = region
        # No orchestrator pattern - uses sqlite directly
    
    def collect_data(self, tickers=None, force_full=False):
        """Legacy collection method"""
        # Incremental gap analysis
        # Fetch from KIS API
        # Save to sqlite with upsert
    
    def collect_with_filtering(self, tickers=None, ...):
        """Phase 2 filtering method"""
        # Not designed for orchestrator integration
```

**Key Observation**: kis_data_collector.py needs adapter wrapper for orchestrator pattern.

---

## 2. Task-by-Task Implementation Plan

### Task 1: KR Ticker Updater (`scripts/update_kr_tickers.py`)

**Status**: NEW FILE  
**Complexity**: MODERATE  
**Estimated Time**: 2-3 hours

#### 2.1 Requirements Analysis

**Input**:
- pykrx API (no authentication required)
- Date parameter (default: today)
- Markets: KOSPI, KOSDAQ, KONEX

**Output**:
- Upsert to `tickers` table (region='KR')
- Detect new listings, delistings, name changes
- Return statistics dict

**Database Schema** (from orchestrator pattern):
```sql
-- tickers table columns used:
ticker, region, name, asset_type, market, is_active, 
listing_date, delisting_date, updated_at
```

#### 2.2 Implementation Design

**File Structure**:
```python
#!/usr/bin/env python3
"""
scripts/update_kr_tickers.py - KR Market Ticker Incremental Update

Fetches KR stock/ETF tickers from pykrx and updates tickers table.
Designed for integration with DatabaseUpdateOrchestrator.

Usage:
    # Standalone
    python3 scripts/update_kr_tickers.py
    
    # Dry run
    python3 scripts/update_kr_tickers.py --dry-run
    
    # From orchestrator
    orchestrator._update_tickers(regions=['KR'])
"""

import sys
import os
from datetime import date
from typing import Dict, List
from pykrx import stock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.db_manager_postgres import PostgresDatabaseManager

class KRTickerUpdater:
    """pykrx-based KR ticker updater for orchestrator integration"""
    
    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.stats = {
            'fetched': 0,
            'new_listings': 0,
            'delistings': 0,
            'name_changes': 0,
            'unchanged': 0,
            'errors': 0
        }
    
    def fetch_current_tickers(self, target_date: date = None) -> Dict[str, Dict]:
        """
        Fetch current KR tickers from pykrx
        
        Returns:
            {ticker: {'name': str, 'market': str, 'asset_type': str}}
        """
        target_date = target_date or date.today()
        date_str = target_date.strftime('%Y%m%d')
        
        tickers = {}
        
        # KOSPI stocks
        for ticker in stock.get_market_ticker_list(date_str, market="KOSPI"):
            name = stock.get_market_ticker_name(ticker)
            tickers[ticker] = {
                'name': name,
                'market': 'KOSPI',
                'asset_type': 'ETF' if 'ETF' in name else 'STOCK'
            }
        
        # KOSDAQ stocks (similar pattern)
        # KONEX stocks (similar pattern)
        
        return tickers
    
    def get_existing_tickers(self) -> Dict[str, Dict]:
        """Query existing KR tickers from database"""
        query = """
        SELECT ticker, name, market, asset_type, is_active
        FROM tickers
        WHERE region = 'KR'
        """
        results = self.db.execute_query(query)
        
        return {row['ticker']: dict(row) for row in results}
    
    def run_update(self) -> Dict:
        """
        Main entry point for orchestrator
        
        Returns:
            Statistics dictionary
        """
        logger.info("🔄 Updating KR tickers from pykrx...")
        
        # 1. Fetch current tickers
        current_tickers = self.fetch_current_tickers()
        self.stats['fetched'] = len(current_tickers)
        
        # 2. Get existing tickers
        existing_tickers = self.get_existing_tickers()
        
        # 3. Detect new listings
        new_tickers = set(current_tickers.keys()) - set(existing_tickers.keys())
        for ticker in new_tickers:
            if not self.dry_run:
                self._insert_ticker(ticker, current_tickers[ticker])
            self.stats['new_listings'] += 1
        
        # 4. Detect delistings
        delisted_tickers = set(existing_tickers.keys()) - set(current_tickers.keys())
        for ticker in delisted_tickers:
            if existing_tickers[ticker]['is_active']:
                if not self.dry_run:
                    self._mark_delisted(ticker)
                self.stats['delistings'] += 1
        
        # 5. Detect name changes
        for ticker in set(current_tickers.keys()) & set(existing_tickers.keys()):
            if current_tickers[ticker]['name'] != existing_tickers[ticker]['name']:
                if not self.dry_run:
                    self._update_name(ticker, current_tickers[ticker]['name'])
                self.stats['name_changes'] += 1
            else:
                self.stats['unchanged'] += 1
        
        logger.info(f"✅ KR ticker update complete: {self.stats}")
        return self.stats
    
    def _insert_ticker(self, ticker: str, data: Dict):
        """Insert new ticker to database"""
        query = """
        INSERT INTO tickers (ticker, region, name, market, asset_type, is_active)
        VALUES (%s, 'KR', %s, %s, %s, TRUE)
        ON CONFLICT (ticker, region) DO NOTHING
        """
        self.db.execute_update(query, (ticker, data['name'], data['market'], data['asset_type']))
    
    def _mark_delisted(self, ticker: str):
        """Mark ticker as delisted"""
        query = """
        UPDATE tickers
        SET is_active = FALSE, delisting_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
        WHERE ticker = %s AND region = 'KR'
        """
        self.db.execute_update(query, (ticker,))
    
    def _update_name(self, ticker: str, new_name: str):
        """Update ticker name"""
        query = """
        UPDATE tickers
        SET name = %s, updated_at = CURRENT_TIMESTAMP
        WHERE ticker = %s AND region = 'KR'
        """
        self.db.execute_update(query, (new_name, ticker))

def main():
    # CLI interface for standalone execution
    pass

if __name__ == '__main__':
    main()
```

#### 2.3 Orchestrator Integration

**File**: `modules/orchestration/orchestrator.py`

**Modify `_update_tickers()` method**:

```python
def _update_tickers(self, regions: List[str], **kwargs) -> Dict:
    """Update ticker tables for all regions"""
    logger.info("🔄 Updating tickers...")
    
    results = {}
    
    for region in regions:
        if region == 'KR':
            # NEW: Use KRTickerUpdater
            try:
                from scripts.update_kr_tickers import KRTickerUpdater
                
                updater = KRTickerUpdater(
                    self.db,
                    dry_run=kwargs.get('dry_run', False)
                )
                
                result = updater.run_update()
                
                results[region] = result
                logger.info(
                    f"  ✅ [{region}] {result['fetched']} fetched, "
                    f"{result['new_listings']} new, {result['delistings']} delisted"
                )
                
            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}
        
        else:
            # Existing overseas ticker logic
            try:
                from scripts.update_master_files import update_region
                
                result = update_region(
                    region,
                    force_refresh=True,
                    dry_run=kwargs.get('dry_run', False)
                )
                
                results[region] = result
                # ... existing logging
                
            except Exception as e:
                # ... existing error handling
    
    return results
```

#### 2.4 Testing Strategy

**Unit Tests**:
```bash
# Test pykrx fetching
python3 -c "from pykrx import stock; print(len(stock.get_market_ticker_list('20251102', market='KOSPI')))"

# Test updater standalone
python3 scripts/update_kr_tickers.py --dry-run

# Test orchestrator integration
python3 scripts/update_database.py --regions KR --steps tickers --dry-run
```

**Expected Output**:
```
🔄 Updating KR tickers from pykrx...
📊 Fetched 2,500 tickers (KOSPI: 800, KOSDAQ: 1,600, KONEX: 100)
✅ New listings: 5
✅ Delistings: 2
✅ Name changes: 3
✅ Unchanged: 2,490
✅ KR ticker update complete in 8.3s
```

---

### Task 2: OHLCV Integration

**Status**: MODIFY EXISTING  
**Complexity**: MODERATE  
**Estimated Time**: 2-3 hours

#### 2.1 Current State Analysis

**File**: `modules/kis_data_collector.py`

**Key Issues**:
1. Uses SQLite (`db_path='data/spock_local.db'`) instead of PostgreSQL
2. No orchestrator-compatible `run()` method
3. `collect_data()` is designed for standalone execution
4. Incremental mode uses custom gap analysis

**Existing Functionality (Reusable)**:
- ✅ KIS API integration with retry logic
- ✅ Technical indicator calculation
- ✅ Incremental gap analysis (`analyze_data_gap()`)
- ✅ Rate limiting (20 req/sec)
- ✅ Mock mode for testing
- ✅ Multi-stage filtering support

#### 2.2 Implementation Design

**Strategy**: Create adapter wrapper instead of modifying kis_data_collector.py

**File**: `scripts/collect_ohlcv_orchestrated.py` (NEW)

```python
#!/usr/bin/env python3
"""
OHLCV Data Collection - Orchestrator Integration

Adapter wrapper for kis_data_collector.py to work with DatabaseUpdateOrchestrator.
Bridges sqlite-based collector to PostgreSQL orchestrator.

Usage:
    # From orchestrator
    orchestrator._update_ohlcv(regions=['KR'])
"""

import sys
import os
from typing import Dict, List, Optional
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.kis_data_collector import KISDataCollector
from modules.db_manager_postgres import PostgresDatabaseManager

logger = logging.getLogger(__name__)


class OHLCVCollectorAdapter:
    """
    Adapter for KISDataCollector to work with orchestrator
    
    Responsibilities:
    1. Query tickers from PostgreSQL
    2. Delegate OHLCV collection to KISDataCollector (sqlite)
    3. Copy results back to PostgreSQL (optional future enhancement)
    4. Return orchestrator-compatible statistics
    """
    
    def __init__(self, db: PostgresDatabaseManager, region: str, dry_run: bool = False):
        self.db = db  # PostgreSQL (orchestrator)
        self.region = region
        self.dry_run = dry_run
        
        # Initialize sqlite-based collector
        self.collector = KISDataCollector(
            db_path='data/spock_local.db',
            region=region
        )
        self.collector.mock_mode = dry_run  # Use mock mode for dry runs
    
    def run_collection(self, incremental: bool = True, limit: Optional[int] = None) -> Dict:
        """
        Main entry point for orchestrator
        
        Args:
            incremental: If True, only update missing/gap data
            limit: Limit number of tickers (for testing)
        
        Returns:
            Statistics dictionary
        """
        logger.info(f"🔄 Collecting OHLCV data for region {self.region}...")
        
        # Step 1: Get ticker list from PostgreSQL
        tickers = self._get_active_tickers(limit)
        
        if not tickers:
            logger.warning(f"⚠️ No active tickers found for region {self.region}")
            return {
                'success': False,
                'message': 'No active tickers',
                'tickers_total': 0
            }
        
        logger.info(f"📊 Found {len(tickers)} active tickers for {self.region}")
        
        # Step 2: Delegate to KISDataCollector
        # Note: collector uses sqlite internally, orchestrator uses PostgreSQL
        self.collector.collect_data(
            tickers=tickers,
            force_full=not incremental
        )
        
        # Step 3: Gather statistics from collector's internal stats
        stats = {
            'success': True,
            'tickers_total': self.collector.stats.get('total', len(tickers)),
            'tickers_success': self.collector.stats.get('success', 0),
            'tickers_skipped': self.collector.stats.get('skipped', 0),
            'tickers_failed': self.collector.stats.get('failed', 0),
            'duration': 0.0  # TODO: calculate from collector
        }
        
        logger.info(
            f"✅ OHLCV collection complete: {stats['tickers_success']}/{stats['tickers_total']} success, "
            f"{stats['tickers_skipped']} skipped, {stats['tickers_failed']} failed"
        )
        
        return stats
    
    def _get_active_tickers(self, limit: Optional[int] = None) -> List[str]:
        """Query active tickers from PostgreSQL tickers table"""
        query = """
        SELECT ticker
        FROM tickers
        WHERE region = %s
          AND is_active = TRUE
          AND asset_type = 'STOCK'
        ORDER BY ticker
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = self.db.execute_query(query, (self.region,))
        return [row['ticker'] for row in results]


# Optional: Future enhancement for PostgreSQL-native collection
class PostgresOHLCVCollector:
    """
    PostgreSQL-native OHLCV collector (future enhancement)
    
    Would eliminate sqlite dependency and store directly to ohlcv_data table.
    Currently not needed as kis_data_collector.py works well with sqlite.
    """
    pass
```

#### 2.3 Orchestrator Integration

**File**: `modules/orchestration/orchestrator.py`

**Modify `_update_ohlcv()` method**:

```python
def _update_ohlcv(self, regions: List[str], **kwargs) -> Dict:
    """Update OHLCV data for all regions"""
    logger.info("🔄 Updating OHLCV data...")
    
    results = {}
    
    for region in regions:
        try:
            if region == 'KR':
                # NEW: Use OHLCVCollectorAdapter
                from scripts.collect_ohlcv_orchestrated import OHLCVCollectorAdapter
                
                adapter = OHLCVCollectorAdapter(
                    self.db,
                    region=region,
                    dry_run=kwargs.get('dry_run', False)
                )
                
                result = adapter.run_collection(
                    incremental=kwargs.get('incremental', True),
                    limit=self.config.get('limit')
                )
                
                results[region] = result
                
                logger.info(
                    f"  ✅ [{region}] {result['tickers_success']} success, "
                    f"{result['tickers_skipped']} skipped, {result['tickers_failed']} failed"
                )
            
            else:
                # Overseas markets - to be implemented
                logger.info(f"  [{region}] Overseas OHLCV collection not implemented")
                results[region] = {
                    'success': False,
                    'message': 'Overseas OHLCV collector not implemented'
                }
        
        except Exception as e:
            logger.error(f"  ❌ [{region}] Failed: {e}")
            results[region] = {'success': False, 'error': str(e)}
    
    return results
```

#### 2.4 Testing Strategy

```bash
# Test adapter standalone
python3 -c "
from scripts.collect_ohlcv_orchestrated import OHLCVCollectorAdapter
from modules.db_manager_postgres import PostgresDatabaseManager

db = PostgresDatabaseManager()
adapter = OHLCVCollectorAdapter(db, region='KR', dry_run=True)
result = adapter.run_collection(incremental=True, limit=10)
print(result)
"

# Test orchestrator integration
python3 scripts/update_database.py --regions KR --steps ohlcv --dry-run --limit 10
```

**Expected Output**:
```
🔄 Collecting OHLCV data for region KR...
📊 Found 2,500 active tickers for KR
⏭️ [1/2500] 005930 Skipped (up to date)
✅ [2/2500] 000660 Success (250 rows)
...
✅ OHLCV collection complete: 1,200/2,500 success, 1,250 skipped, 50 failed
```

---

### Task 3: Quarterly Financials (Optional)

**Status**: NEW FILE  
**Complexity**: MODERATE  
**Estimated Time**: 2 hours

#### 3.1 Requirements Analysis

**Input**:
- DART API (quarterly financial statements)
- Target field: `equity` (순자산) from balance sheet

**Output**:
- Update `ticker_fundamentals.equity` for period_type='QUARTERLY'
- Support incremental mode (only missing quarters)

**DART API Endpoints**:
- `/api/fnlttSinglAcnt.json` - Single Account Financial Statements
- Filter: `fs_div=CFS` (Consolidated), `sj_div=BS` (Balance Sheet)
- Extract: `thstrm_amount` where `account_nm='자본총계'`

#### 3.2 Implementation Design (Abbreviated)

**File**: `scripts/update_quarterly_financials.py` (NEW)

```python
class QuarterlyFinancialsUpdater:
    """DART quarterly equity updater for orchestrator integration"""
    
    def __init__(self, db: PostgresDatabaseManager, dart: DARTApiClient, dry_run: bool = False):
        self.db = db
        self.dart = dart
        self.dry_run = dry_run
    
    def run_update(self, incremental: bool = True, limit: Optional[int] = None) -> Dict:
        """
        Main entry point for orchestrator
        
        Process:
        1. Query tickers with corp_code
        2. Fetch quarterly financial statements from DART
        3. Extract equity (자본총계) from balance sheet
        4. Upsert to ticker_fundamentals (period_type='QUARTERLY')
        """
        # Implementation similar to DARTFundamentalBackfiller
        pass
```

**Orchestrator Integration**:
```python
def _update_quarterly_financials(self, regions: List[str], **kwargs) -> Dict:
    if region == 'KR':
        from scripts.update_quarterly_financials import QuarterlyFinancialsUpdater
        
        dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))
        updater = QuarterlyFinancialsUpdater(self.db, dart, dry_run=kwargs.get('dry_run'))
        result = updater.run_update(incremental=kwargs.get('incremental'))
        return results
```

---

## 3. Execution Strategy

### 3.1 Parallel vs Sequential Execution

**Current Orchestrator**: Sequential only

**Opportunities for Parallelization**:
- ❌ **tickers**: Must run first (dependency for all others)
- ❌ **ohlcv**: Depends on tickers
- ✅ **fundamentals + dividend**: Can run in parallel (both depend on tickers + ohlcv)
- ✅ **quarterly**: Can run in parallel with fundamentals + dividend

**Recommended Approach**: Keep sequential for Phase 2, add parallelization in Phase 3

### 3.2 Critical Path Analysis

```
tickers (KR: 10s, Overseas: 20s) [REQUIRED]
    ↓
ohlcv (60s, rate-limited by KIS API 20 req/sec) [REQUIRED]
    ↓
fundamentals (300s, rate-limited by DART 1 req/sec) [PARALLEL]
dividend (30s, DB-only) [PARALLEL]
quarterly (200s, rate-limited by DART 1 req/sec) [PARALLEL]
```

**Total Sequential Time**: ~10 minutes  
**Total Parallel Time**: ~7 minutes (30% improvement)

### 3.3 Task Dependencies

| Task | Depends On | Estimated Time |
|------|------------|----------------|
| Task 1: KR Tickers | None | 2-3 hours |
| Task 2: OHLCV Integration | Task 1 complete | 2-3 hours |
| Task 3: Quarterly (Optional) | None (independent) | 2 hours |

**Execution Order**:
1. Implement Task 1 (KR tickers) - Test standalone and orchestrator
2. Implement Task 2 (OHLCV) - Test standalone and orchestrator
3. Run full pipeline test (tickers → ohlcv → fundamentals → dividend)
4. (Optional) Implement Task 3 (quarterly financials)

---

## 4. Testing & Validation Plan

### 4.1 Unit Tests

```bash
# Task 1: KR Ticker Updater
python3 scripts/update_kr_tickers.py --dry-run
python3 scripts/update_kr_tickers.py --dry-run --verbose

# Task 2: OHLCV Integration
python3 scripts/collect_ohlcv_orchestrated.py --test-adapter --limit 10
```

### 4.2 Integration Tests

```bash
# Test individual steps
python3 scripts/update_database.py --regions KR --steps tickers --dry-run
python3 scripts/update_database.py --regions KR --steps ohlcv --dry-run --limit 10

# Test full pipeline
python3 scripts/update_database.py --regions KR --dry-run --limit 10

# Test with real data (small sample)
python3 scripts/update_database.py --regions KR --limit 10
```

### 4.3 Success Criteria

**Task 1: KR Ticker Updater**
- ✅ Fetches 2,500+ tickers from pykrx
- ✅ Detects new listings, delistings, name changes
- ✅ Upserts to PostgreSQL tickers table
- ✅ Dry-run mode works correctly
- ✅ Orchestrator integration successful

**Task 2: OHLCV Integration**
- ✅ Queries tickers from PostgreSQL
- ✅ Delegates to kis_data_collector (sqlite)
- ✅ Returns orchestrator-compatible statistics
- ✅ Incremental mode works (skips up-to-date tickers)
- ✅ Rate limiting respected (20 req/sec)

**Task 3: Quarterly Financials (Optional)**
- ✅ Fetches quarterly equity from DART API
- ✅ Upserts to ticker_fundamentals (period_type='QUARTERLY')
- ✅ Incremental mode works (only missing quarters)

---

## 5. Risk Analysis

### 5.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **pykrx API changes** | High | Low | Wrap in try-except, fallback to KIS API |
| **Rate limiting violations** | Medium | Low | Use orchestrator's MultiRateLimiter |
| **Data inconsistency (sqlite vs PostgreSQL)** | Medium | Medium | Future: Migrate kis_data_collector to PostgreSQL |
| **DART API timeout** | Low | Medium | Existing retry logic in DARTApiClient |

### 5.2 Operational Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Long execution time** | Medium | Background execution with nohup, checkpoint recovery |
| **Incomplete updates** | High | Checkpoint-based recovery, --resume flag |
| **Missing API keys** | High | Validation in orchestrator __init__ |

---

## 6. Next Steps

### 6.1 Immediate Actions (Today)

1. **Create Task 1 file**: `scripts/update_kr_tickers.py`
2. **Modify orchestrator**: Update `_update_tickers()` method
3. **Test Task 1**: Standalone and orchestrator integration

### 6.2 Short-term Actions (Tomorrow)

1. **Create Task 2 adapter**: `scripts/collect_ohlcv_orchestrated.py`
2. **Modify orchestrator**: Update `_update_ohlcv()` method
3. **Test Task 2**: Standalone and orchestrator integration
4. **Run full pipeline test**: tickers → ohlcv → fundamentals → dividend

### 6.3 Optional Actions (Next Week)

1. **Create Task 3 file**: `scripts/update_quarterly_financials.py` (if needed)
2. **Add parallelization**: Modify orchestrator for parallel step execution
3. **Migrate kis_data_collector**: Replace sqlite with PostgreSQL (future enhancement)

---

## 7. Code Structure Summary

### Files to Create

1. **`scripts/update_kr_tickers.py`** (Task 1) - 200 lines
   - Class: `KRTickerUpdater`
   - Methods: `fetch_current_tickers()`, `get_existing_tickers()`, `run_update()`

2. **`scripts/collect_ohlcv_orchestrated.py`** (Task 2) - 150 lines
   - Class: `OHLCVCollectorAdapter`
   - Methods: `_get_active_tickers()`, `run_collection()`

3. **`scripts/update_quarterly_financials.py`** (Task 3, Optional) - 300 lines
   - Class: `QuarterlyFinancialsUpdater`
   - Methods: `run_update()`, `fetch_quarterly_equity()`, `upsert_equity()`

### Files to Modify

1. **`modules/orchestration/orchestrator.py`**
   - Method: `_update_tickers()` - Add KR region handling
   - Method: `_update_ohlcv()` - Replace placeholder with adapter
   - Method: `_update_quarterly_financials()` - Add implementation (optional)

---

## 8. Conclusion

### Phase 2 Readiness: ✅ 95%

**Ready to Implement**:
- Task 1: Clear pykrx patterns, PostgreSQL schema known
- Task 2: kis_data_collector.py works, just needs adapter wrapper
- Task 3: DARTApiClient ready, similar to fundamentals backfiller

**Estimated Completion**: 1-2 days (including testing)

**Key Success Factors**:
1. Follow existing patterns (DARTFundamentalBackfiller, DividendYieldCalculator)
2. Use orchestrator's infrastructure (checkpoint, rate limiting, validation)
3. Comprehensive testing at each step
4. Dry-run mode for safe testing

**Post-Implementation**:
- ✅ Unified database update via single command
- ✅ Checkpoint-based recovery
- ✅ Consistent error handling
- ✅ Multi-region support
- ✅ Production-ready automation

