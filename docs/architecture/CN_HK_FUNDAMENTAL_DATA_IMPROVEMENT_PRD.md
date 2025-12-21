# CN/HK Fundamental Data Collection Improvement - PRD

**Document Version**: 1.0.0
**Date**: 2025-12-20
**Status**: Draft - Ready for Implementation
**Owner**: Quant Platform Development Team
**Estimated Implementation Time**: 1-2 weeks

---

## 📋 Executive Summary

### Problem Statement

Currently, only ~50% of CN and HK stocks have fundamental data available in the database, despite having 2,436 CN and 7,337 HK active tickers. Analysis reveals the primary cause is attempting to collect fundamental data for non-stock assets (ETFs, mutual funds, indices) which do not have financial statements.

### Solution Overview

Implement a 4-phase improvement plan focusing on:
1. **Asset Type Filtering**: Exclude ETFs/funds from fundamental collection
2. **Market Cap Prioritization**: Collect large-cap stocks first for high-quality coverage
3. **Multi-Source Fallback**: Enhance data source redundancy (AkShare → yfinance QUARTERLY → yfinance ANNUAL)
4. **Monitoring & Quality Assurance**: Real-time coverage tracking and data quality validation

### Success Metrics

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| **CN Coverage** | 50% | 98%+ | +48%p |
| **HK Coverage** | 50% | 98%+ | +48%p |
| **Large-Cap Coverage** | Unknown | 99%+ | High priority |
| **API Call Efficiency** | Baseline | -50% | Time/cost savings |
| **Data Quality** | Unknown | 95%+ | Measured by completeness |

---

## 🎯 Goals and Objectives

### Primary Goals

1. **Coverage**: Achieve 98%+ fundamental data coverage for stocks (excluding ETFs/funds)
2. **Quality**: Ensure 95%+ field completeness for collected data
3. **Efficiency**: Reduce unnecessary API calls by 50% (exclude non-stocks)
4. **Reliability**: Multi-source fallback with 99%+ uptime

### Secondary Goals

1. **Monitoring**: Real-time coverage dashboard
2. **Documentation**: Comprehensive troubleshooting guides
3. **Scalability**: Support for 10,000+ tickers per region

### Non-Goals

1. ETF fundamental data collection (ETFs don't have financial statements)
2. Real-time data updates (daily/weekly batch updates sufficient)
3. Alternative data sources beyond AkShare/yfinance/Naver (phase 4+)

---

## 📊 Current State Analysis

### Data Availability Statistics

```yaml
CN Region (China):
  Total Active Tickers: 2,436
  Tickers with Fundamentals: ~1,200 (50%)
  Tickers without Fundamentals: ~1,236 (50%)

  Sample Missing Tickers:
    - 510050 (China 50 ETF) → ETF, no financial statements
    - 510300 (Huatai CSI 300 ETF) → ETF
    - 510500 (CSI 500 ETF) → ETF
    - 159901 (SZSE 100 ETF) → ETF

HK Region (Hong Kong):
  Total Active Tickers: 7,337
  Tickers with Fundamentals: ~3,700 (50%)
  Tickers without Fundamentals: ~3,637 (50%)

  Sample Missing Tickers:
    - 00091 (金禧国际控股) → MUTUALFUND (yfinance), no data
    - 00260 (幸福控股) → Small-cap, delisted
    - 00278 (华厦置业) → Small-cap, inactive
```

### Root Cause Analysis

#### Issue 1: Asset Type Not Filtered (Primary Root Cause)

**Problem**:
- Current system collects fundamentals for ALL `is_active = TRUE` tickers
- Database includes ETFs, mutual funds, indices alongside stocks
- These non-stock assets do not have financial statements (P&L, balance sheet, cash flow)

**Evidence**:
```python
# Test: CN ETF (510050 - China 50 ETF)
df = ak.stock_financial_analysis_indicator(symbol='510050')
# Result: Empty DataFrame (0 records) ❌

# Test: CN Stock (600519 - Kweichow Moutai)
df = ak.stock_financial_analysis_indicator(symbol='600519')
# Result: 11 quarterly records ✅
```

**Impact**:
- 50% of API calls wasted on non-stocks
- Error logs cluttered with expected failures
- Lower perceived success rate

#### Issue 2: Data Source Limitations (Secondary)

**AkShare API**:
- ✅ Major listed stocks: 98-99% success
- ❌ ETFs: No fundamental data API
- ❌ Small-cap/delisted: Data gaps
- ❌ Funds/preferred shares: Out of API scope

**yfinance API**:
- ✅ Large-cap: 100% support
- ⚠️ Mid-cap: 80-90% support
- ❌ Small-cap: <50% support
- ❌ Inactive stocks: Data delays/missing

#### Issue 3: `asset_type` Field Underutilized

**Current State**:
```sql
-- Many tickers lack asset_type classification
SELECT asset_type, COUNT(*)
FROM tickers
WHERE region IN ('CN', 'HK') AND is_active = TRUE
GROUP BY asset_type;

-- Expected Result (estimated):
-- asset_type | count
-- -----------+-------
-- STOCK      | 4,000
-- ETF        | 500
-- NULL       | 5,273  ← Unclassified
```

**Required**:
- Auto-classify `asset_type` during ticker collection
- Filter by `asset_type = 'STOCK'` during fundamental collection

---

## 🏗️ System Architecture

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   spock_refresh.py (Menu)                   │
│          Fundamental Data Backfill → Other Markets          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│           backfill_fundamentals_akshare.py                  │
│  AkShareFundamentalBackfiller(db, dry_run)                  │
│    - backfill_cn(mode='hybrid')                             │
│    - backfill_hk()                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                 │
┌────────▼────────┐              ┌────────▼────────┐
│   CNAdapter     │              │   HKAdapter     │
│  (cn_adapter.py)│              │  (hk_adapter.py)│
└────────┬────────┘              └────────┬────────┘
         │                                 │
         ├──────────┬──────────────────────┤
         │          │                      │
┌────────▼──────┐   │         ┌───────────▼───────┐
│ AkShareAPI    │   │         │  yfinance API     │
│ (akshare_api.py)  │         │  (yf.Ticker)      │
└───────────────┘   │         └───────────────────┘
                    │
         ┌──────────▼──────────┐
         │ PostgresDatabaseMgr │
         │  insert_fundamentals│
         └─────────────────────┘
```

### Target Architecture (After Improvement)

```
┌─────────────────────────────────────────────────────────────┐
│                   spock_refresh.py (Menu)                   │
│          Fundamental Data Backfill → Other Markets          │
│  NEW: Asset Type Filter + Market Cap Priority Options      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│      NEW: backfill_fundamentals_prioritized.py              │
│  PrioritizedFundamentalBackfiller(db, dry_run)              │
│    - backfill_cn_prioritized(min_mcap, asset_types)         │
│    - backfill_hk_prioritized(min_mcap, asset_types)         │
│    - generate_coverage_report()                             │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                 │
┌────────▼────────┐              ┌────────▼────────┐
│   CNAdapter     │              │   HKAdapter     │
│  ENHANCED:      │              │  ENHANCED:      │
│  - classify_    │              │  - classify_    │
│    asset_type() │              │    asset_type() │
│  - multi_source_│              │  - multi_source_│
│    fallback()   │              │    fallback()   │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         ├──────────┬──────────┬───────────┤
         │          │          │           │
┌────────▼──────┐   │   ┌──────▼─────┐    │
│ AkShareAPI    │   │   │  yfinance  │    │
│ (Primary)     │   │   │ QUARTERLY  │    │
│ 86 indicators │   │   │ (Fallback) │    │
└───────────────┘   │   └────────────┘    │
                    │                      │
              ┌─────▼──────┐      ┌───────▼────────┐
              │  yfinance  │      │ Naver Finance  │
              │  ANNUAL    │      │  (Phase 4)     │
              │ (HK only)  │      │  (Optional)    │
              └────────────┘      └────────────────┘
                    │
         ┌──────────▼──────────┐
         │ PostgresDatabaseMgr │
         │  insert_fundamentals│
         │  NEW: Coverage      │
         │       Metrics       │
         └─────────────────────┘
```

---

## 🔧 Phase 1: Asset Type Filtering (P0 - Critical)

### Overview

**Goal**: Filter out non-stock assets (ETFs, funds, indices) from fundamental data collection
**Impact**: 50% → 98% success rate improvement
**Estimated Time**: 1-2 days
**Priority**: P0 (Critical - Must have)

### Requirements

#### FR-1.1: Auto-Classify Asset Type During Ticker Collection

**Requirement**: When collecting tickers via AkShare/yfinance, automatically determine and store `asset_type`

**Acceptance Criteria**:
- [ ] CN tickers: Classify as STOCK, ETF, or INDEX based on yfinance `quoteType` + name pattern
- [ ] HK tickers: Classify as STOCK, ETF, MUTUALFUND, or INDEX based on yfinance `quoteType`
- [ ] Store `asset_type` in `tickers` table
- [ ] Default to 'STOCK' for uncertain cases (fail-safe)

**Implementation**:

```python
# File: modules/market_adapters/cn_adapter.py
# Location: CNAdapter class

def _classify_asset_type(self, ticker_info: Dict) -> str:
    """
    Classify asset type from yfinance/AkShare response

    Args:
        ticker_info: Dictionary from yfinance Ticker.info or AkShare

    Returns:
        Asset type: 'STOCK', 'ETF', 'MUTUALFUND', 'INDEX', or 'UNKNOWN'

    Classification Logic:
        1. Check yfinance quoteType (if available)
        2. Check ticker name for ETF keywords (ETF, 指数, 基金)
        3. Check ticker code patterns (51xxxx for CN ETFs)
        4. Default to 'STOCK' (fail-safe)
    """
    # Step 1: yfinance quoteType (most reliable)
    quote_type = ticker_info.get('quoteType', '').upper()

    if quote_type in ['ETF', 'MUTUALFUND', 'INDEX']:
        return quote_type

    # Step 2: Name-based classification (fallback)
    name = ticker_info.get('name', '').upper()

    if any(keyword in name for keyword in ['ETF', '指数', '交易型开放式指数']):
        return 'ETF'

    if any(keyword in name for keyword in ['基金', 'FUND']):
        return 'MUTUALFUND'

    # Step 3: CN ticker code pattern (51xxxx = ETF)
    ticker = ticker_info.get('ticker', '')
    if ticker.startswith('51') and len(ticker) == 6:
        return 'ETF'

    # Step 4: Default (fail-safe)
    if quote_type == 'EQUITY':
        return 'STOCK'

    return 'STOCK'  # Conservative default
```

#### FR-1.2: Filter Fundamental Collection by Asset Type

**Requirement**: Only collect fundamental data for `asset_type = 'STOCK'`

**Acceptance Criteria**:
- [ ] `backfill_cn()`: Filter tickers to `asset_type = 'STOCK'`
- [ ] `backfill_hk()`: Filter tickers to `asset_type = 'STOCK'`
- [ ] Log filtered-out tickers with reason (DEBUG level)
- [ ] Report excluded count in summary

**Implementation**:

```python
# File: scripts/backfill_fundamentals_akshare.py
# Location: AkShareFundamentalBackfiller class

def backfill_cn(self,
                mode: str = 'hybrid',
                report_date: Optional[str] = None,
                limit: Optional[int] = None,
                tickers: Optional[List[str]] = None,
                asset_types: List[str] = ['STOCK']) -> int:  # NEW parameter
    """
    Backfill CN fundamental data (STOCKS ONLY)

    Args:
        mode: Collection mode ('batch', 'individual', 'hybrid')
        report_date: Report date for batch mode (YYYYMMDD)
        limit: Max number of tickers to process
        tickers: Specific tickers to process (overrides limit)
        asset_types: Asset types to include (default: ['STOCK'] only)

    Returns:
        Number of records inserted
    """
    logger.info(f"🇨🇳 Starting CN fundamentals backfill (mode={mode}, asset_types={asset_types})")

    # NEW: Filter by asset_type
    if not tickers:
        db_tickers = self.db.get_tickers(
            region='CN',
            asset_type=asset_types,  # NEW: Filter by asset type
            is_active=True
        )
        tickers = [t['ticker'] for t in db_tickers]

        # Log excluded tickers (DEBUG level)
        all_tickers = self.db.get_tickers(region='CN', is_active=True)
        excluded = len(all_tickers) - len(db_tickers)
        logger.info(f"   Excluded {excluded} non-stock tickers (ETFs, funds, etc.)")

    # Apply limit if specified
    if limit:
        tickers = tickers[:limit]

    # Run collection (unchanged)
    success_count = self.cn_adapter.collect_fundamentals(
        tickers=tickers,
        mode=mode,
        report_date=report_date,
        use_fallback=True
    )

    return success_count
```

#### FR-1.3: Update Database Schema for Asset Type

**Requirement**: Ensure `tickers.asset_type` column exists and is indexed

**Acceptance Criteria**:
- [ ] `asset_type` column exists in `tickers` table
- [ ] Index on `(region, asset_type, is_active)` for fast filtering
- [ ] Migration script tested on dev database
- [ ] Backward compatible (nullable column, default NULL)

**Implementation**:

```sql
-- File: migrations/add_asset_type_index.sql

-- Step 1: Ensure column exists (may already exist)
ALTER TABLE tickers
ADD COLUMN IF NOT EXISTS asset_type VARCHAR(20) DEFAULT NULL;

-- Step 2: Create composite index for filtering
CREATE INDEX IF NOT EXISTS idx_tickers_region_asset_type_active
ON tickers (region, asset_type, is_active)
WHERE is_active = TRUE;

-- Step 3: Add comment for documentation
COMMENT ON COLUMN tickers.asset_type IS
'Asset type: STOCK, ETF, MUTUALFUND, INDEX, or NULL (unclassified).
Used to filter fundamental data collection to stocks only.';

-- Verification query
SELECT
    region,
    asset_type,
    is_active,
    COUNT(*) as count
FROM tickers
WHERE region IN ('CN', 'HK')
GROUP BY region, asset_type, is_active
ORDER BY region, asset_type, is_active;
```

### Testing Requirements

#### Test Case 1.1: Asset Type Classification Accuracy

```python
# File: tests/unit/test_asset_type_classification.py

def test_cn_etf_classification():
    """Test CN ETF is correctly classified"""
    adapter = CNAdapter(db, enable_fallback=False)

    # Mock yfinance response for ETF
    ticker_info = {
        'ticker': '510050',
        'name': 'China 50 ETF',
        'quoteType': 'ETF'
    }

    asset_type = adapter._classify_asset_type(ticker_info)
    assert asset_type == 'ETF', "Failed to classify CN ETF"

def test_cn_stock_classification():
    """Test CN stock is correctly classified"""
    adapter = CNAdapter(db, enable_fallback=False)

    # Mock yfinance response for stock
    ticker_info = {
        'ticker': '600519',
        'name': 'Kweichow Moutai',
        'quoteType': 'EQUITY'
    }

    asset_type = adapter._classify_asset_type(ticker_info)
    assert asset_type == 'STOCK', "Failed to classify CN stock"

def test_hk_mutualfund_classification():
    """Test HK mutual fund is correctly classified"""
    adapter = HKAdapter(db, enable_fallback=False)

    # Mock yfinance response for mutual fund
    ticker_info = {
        'ticker': '00091',
        'name': '金禧国际控股',
        'quoteType': 'MUTUALFUND'
    }

    asset_type = adapter._classify_asset_type(ticker_info)
    assert asset_type == 'MUTUALFUND', "Failed to classify HK mutual fund"
```

#### Test Case 1.2: Fundamental Collection Filtering

```python
# File: tests/integration/test_fundamental_backfill_filtering.py

def test_backfill_excludes_etfs():
    """Test fundamental backfill excludes ETFs"""
    db = PostgresDatabaseManager()

    # Setup: Insert test tickers (1 stock, 1 ETF)
    db.execute_query("""
        INSERT INTO tickers (ticker, name, region, asset_type, is_active)
        VALUES
            ('600519', 'Moutai', 'CN', 'STOCK', TRUE),
            ('510050', 'China 50 ETF', 'CN', 'ETF', TRUE)
        ON CONFLICT (ticker, region) DO NOTHING;
    """)

    # Run backfill
    backfiller = AkShareFundamentalBackfiller(db, dry_run=False)
    count = backfiller.backfill_cn(limit=2, asset_types=['STOCK'])

    # Verify: Only 1 ticker (stock) should be collected
    result = db.execute_query("""
        SELECT COUNT(*) as count
        FROM ticker_fundamentals
        WHERE ticker IN ('600519', '510050') AND region = 'CN'
    """)

    assert result[0]['count'] == 1, "ETF should not have fundamentals"

    # Verify: Stock has fundamentals, ETF does not
    stock_fund = db.execute_query("""
        SELECT * FROM ticker_fundamentals
        WHERE ticker = '600519' AND region = 'CN'
        ORDER BY date DESC LIMIT 1
    """)
    assert len(stock_fund) == 1, "Stock should have fundamentals"

    etf_fund = db.execute_query("""
        SELECT * FROM ticker_fundamentals
        WHERE ticker = '510050' AND region = 'CN'
    """)
    assert len(etf_fund) == 0, "ETF should NOT have fundamentals"
```

### Rollout Plan

**Phase 1.1: Development** (Day 1)
- [ ] Implement `_classify_asset_type()` in CNAdapter
- [ ] Implement `_classify_asset_type()` in HKAdapter
- [ ] Add `asset_types` parameter to `backfill_cn()` and `backfill_hk()`
- [ ] Write unit tests (Test Case 1.1)

**Phase 1.2: Database Migration** (Day 1-2)
- [ ] Test migration on dev database
- [ ] Apply migration to staging database
- [ ] Verify index performance

**Phase 1.3: Integration Testing** (Day 2)
- [ ] Write integration tests (Test Case 1.2)
- [ ] Run test backfill (10 CN + 10 HK tickers)
- [ ] Verify success rate improvement

**Phase 1.4: Production Deployment** (Day 2)
- [ ] Deploy code to production
- [ ] Run full CN backfill (stocks only)
- [ ] Run full HK backfill (stocks only)
- [ ] Monitor success rate (target: 98%+)

---

## 📈 Phase 2: Market Cap Prioritization (P1 - High Priority)

### Overview

**Goal**: Collect large-cap stocks first to ensure high-quality coverage for most important stocks
**Impact**: 99%+ coverage for top 500 CN + top 300 HK stocks
**Estimated Time**: 2-3 days
**Priority**: P1 (High - Should have)

### Requirements

#### FR-2.1: Market Cap Based Ticker Sorting

**Requirement**: Sort tickers by market cap (largest first) before collection

**Acceptance Criteria**:
- [ ] Query tickers ordered by `market_cap DESC`
- [ ] Handle NULL market_cap (place at end)
- [ ] Support minimum market cap filter (e.g., > 1B CNY)
- [ ] Log market cap tiers in summary

**Implementation**:

```python
# File: scripts/backfill_fundamentals_prioritized.py (NEW FILE)

class PrioritizedFundamentalBackfiller:
    """
    Fundamental backfiller with market cap prioritization

    Features:
    - Sort tickers by market cap (largest first)
    - Filter by minimum market cap
    - Progressive backfill (stop at N tickers or time limit)
    - Coverage reporting by market cap tier
    """

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.cn_adapter = CNAdapter(db, enable_fallback=True)
        self.hk_adapter = HKAdapter(db, enable_fallback=True)

    def backfill_cn_prioritized(self,
                                min_market_cap: int = 0,
                                max_tickers: Optional[int] = None,
                                time_limit_seconds: Optional[int] = None) -> Dict:
        """
        Backfill CN fundamentals with market cap priority

        Args:
            min_market_cap: Minimum market cap in CNY (default: 0 = all)
            max_tickers: Max tickers to process (default: None = all)
            time_limit_seconds: Max execution time (default: None = unlimited)

        Returns:
            Dictionary with statistics:
                - total_tickers: Total eligible tickers
                - processed: Tickers processed
                - success: Successful collections
                - failed: Failed collections
                - by_tier: Success by market cap tier
        """
        logger.info(f"🇨🇳 Starting CN prioritized backfill (min_mcap={min_market_cap:,} CNY)")

        # Step 1: Get tickers ordered by market cap
        tickers = self.db.execute_query("""
            SELECT
                ticker,
                name,
                market_cap,
                CASE
                    WHEN market_cap >= 100000000000 THEN 'MEGA'   -- 1000亿+ (Large)
                    WHEN market_cap >= 10000000000 THEN 'LARGE'   -- 100亿+ (Mid-Large)
                    WHEN market_cap >= 1000000000 THEN 'MID'      -- 10亿+ (Mid)
                    ELSE 'SMALL'                                   -- <10亿 (Small)
                END as tier
            FROM tickers
            WHERE region = 'CN'
              AND asset_type = 'STOCK'
              AND is_active = TRUE
              AND (market_cap >= %s OR market_cap IS NULL)
            ORDER BY
                market_cap DESC NULLS LAST
        """, (min_market_cap,))

        # Step 2: Apply max_tickers limit
        if max_tickers:
            tickers = tickers[:max_tickers]

        # Step 3: Collect with time limit
        start_time = time.time()
        stats = {
            'total_tickers': len(tickers),
            'processed': 0,
            'success': 0,
            'failed': 0,
            'by_tier': {'MEGA': 0, 'LARGE': 0, 'MID': 0, 'SMALL': 0}
        }

        for ticker_data in tickers:
            # Check time limit
            if time_limit_seconds and (time.time() - start_time) > time_limit_seconds:
                logger.warning(f"⏰ Time limit reached ({time_limit_seconds}s)")
                break

            # Collect fundamentals
            try:
                result = self.cn_adapter.collect_fundamentals(
                    tickers=[ticker_data['ticker']],
                    mode='hybrid',
                    use_fallback=True
                )

                if result > 0:
                    stats['success'] += 1
                    stats['by_tier'][ticker_data['tier']] += 1
                else:
                    stats['failed'] += 1

            except Exception as e:
                logger.error(f"❌ Failed {ticker_data['ticker']}: {e}")
                stats['failed'] += 1

            stats['processed'] += 1

            # Progress log (every 10 tickers)
            if stats['processed'] % 10 == 0:
                logger.info(f"Progress: {stats['processed']}/{stats['total_tickers']} "
                           f"({stats['success']} success, {stats['failed']} failed)")

        # Step 4: Summary
        logger.info("=" * 60)
        logger.info("📊 PRIORITIZED BACKFILL SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tickers: {stats['total_tickers']}")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Success: {stats['success']} ({stats['success']/stats['processed']*100:.1f}%)")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"By Tier: {stats['by_tier']}")

        return stats
```

#### FR-2.2: Market Cap Tier Reporting

**Requirement**: Generate coverage report by market cap tier

**Acceptance Criteria**:
- [ ] Define market cap tiers (MEGA, LARGE, MID, SMALL)
- [ ] Report coverage % for each tier
- [ ] Save report to markdown file
- [ ] Include date range of collected data

**Implementation**:

```python
# File: scripts/backfill_fundamentals_prioritized.py
# Location: PrioritizedFundamentalBackfiller class

def generate_coverage_report(self, region: str = 'CN') -> str:
    """
    Generate fundamental data coverage report by market cap tier

    Args:
        region: Target region ('CN' or 'HK')

    Returns:
        Markdown formatted report string
    """
    # Query coverage by tier
    result = self.db.execute_query("""
        WITH ticker_tiers AS (
            SELECT
                t.ticker,
                t.name,
                t.market_cap,
                CASE
                    WHEN t.market_cap >= 100000000000 THEN 'MEGA'
                    WHEN t.market_cap >= 10000000000 THEN 'LARGE'
                    WHEN t.market_cap >= 1000000000 THEN 'MID'
                    ELSE 'SMALL'
                END as tier,
                CASE
                    WHEN tf.ticker IS NOT NULL THEN 1
                    ELSE 0
                END as has_fundamentals
            FROM tickers t
            LEFT JOIN ticker_fundamentals tf
                ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE t.region = %s
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
        )
        SELECT
            tier,
            COUNT(*) as total_tickers,
            SUM(has_fundamentals) as with_fundamentals,
            ROUND(SUM(has_fundamentals)::numeric / COUNT(*) * 100, 2) as coverage_pct,
            MIN(market_cap) as min_mcap,
            MAX(market_cap) as max_mcap
        FROM ticker_tiers
        GROUP BY tier
        ORDER BY
            CASE tier
                WHEN 'MEGA' THEN 1
                WHEN 'LARGE' THEN 2
                WHEN 'MID' THEN 3
                WHEN 'SMALL' THEN 4
            END;
    """, (region,))

    # Format as markdown
    report = f"""# {region} Fundamental Data Coverage Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Region**: {region}

## Coverage by Market Cap Tier

| Tier | Market Cap Range | Total Tickers | With Fundamentals | Coverage % |
|------|------------------|---------------|-------------------|------------|
"""

    for row in result:
        tier = row['tier']
        mcap_range = self._format_mcap_range(row['min_mcap'], row['max_mcap'], region)
        total = row['total_tickers']
        with_fund = row['with_fundamentals']
        coverage = row['coverage_pct']

        report += f"| **{tier}** | {mcap_range} | {total:,} | {with_fund:,} | {coverage}% |\n"

    # Overall stats
    overall = self.db.execute_query("""
        SELECT
            COUNT(DISTINCT t.ticker) as total,
            COUNT(DISTINCT tf.ticker) as with_fund
        FROM tickers t
        LEFT JOIN ticker_fundamentals tf
            ON t.ticker = tf.ticker AND t.region = tf.region
        WHERE t.region = %s AND t.asset_type = 'STOCK' AND t.is_active = TRUE
    """, (region,))[0]

    overall_pct = overall['with_fund'] / overall['total'] * 100 if overall['total'] > 0 else 0

    report += f"""
## Overall Statistics

- **Total Stock Tickers**: {overall['total']:,}
- **With Fundamental Data**: {overall['with_fund']:,}
- **Overall Coverage**: {overall_pct:.2f}%

## Recommendations

"""

    # Add recommendations based on coverage
    for row in result:
        if row['coverage_pct'] < 90:
            report += f"- ⚠️ **{row['tier']}**: Coverage below 90% ({row['coverage_pct']}%). Consider re-running backfill.\n"
        elif row['coverage_pct'] < 95:
            report += f"- ✅ **{row['tier']}**: Coverage acceptable ({row['coverage_pct']}%).\n"
        else:
            report += f"- ✅ **{row['tier']}**: Excellent coverage ({row['coverage_pct']}%).\n"

    return report

def _format_mcap_range(self, min_mcap: float, max_mcap: float, region: str) -> str:
    """Format market cap range for display"""
    currency = 'CNY' if region == 'CN' else 'HKD'

    def format_mcap(mcap):
        if mcap >= 1e12:
            return f"{mcap/1e12:.1f}T {currency}"
        elif mcap >= 1e9:
            return f"{mcap/1e9:.1f}B {currency}"
        elif mcap >= 1e6:
            return f"{mcap/1e6:.1f}M {currency}"
        else:
            return f"{mcap:,.0f} {currency}"

    return f"{format_mcap(min_mcap)} - {format_mcap(max_mcap)}"
```

### Testing Requirements

#### Test Case 2.1: Market Cap Sorting

```python
# File: tests/unit/test_market_cap_prioritization.py

def test_tickers_sorted_by_market_cap():
    """Test tickers are sorted by market cap descending"""
    db = PostgresDatabaseManager()

    # Insert test tickers with different market caps
    test_data = [
        ('TEST001', 'Small Cap', 'CN', 'STOCK', 500000000),      # 5亿
        ('TEST002', 'Large Cap', 'CN', 'STOCK', 50000000000),    # 500亿
        ('TEST003', 'Mega Cap', 'CN', 'STOCK', 200000000000),    # 2000亿
        ('TEST004', 'Mid Cap', 'CN', 'STOCK', 5000000000),       # 50亿
    ]

    for ticker, name, region, asset_type, mcap in test_data:
        db.execute_query("""
            INSERT INTO tickers (ticker, name, region, asset_type, is_active, market_cap)
            VALUES (%s, %s, %s, %s, TRUE, %s)
            ON CONFLICT (ticker, region) DO UPDATE SET market_cap = EXCLUDED.market_cap
        """, (ticker, name, region, asset_type, mcap))

    # Query tickers sorted by market cap
    tickers = db.execute_query("""
        SELECT ticker, market_cap
        FROM tickers
        WHERE ticker LIKE 'TEST%'
        ORDER BY market_cap DESC NULLS LAST
    """)

    # Verify sorting
    assert tickers[0]['ticker'] == 'TEST003', "Mega cap should be first"
    assert tickers[1]['ticker'] == 'TEST002', "Large cap should be second"
    assert tickers[2]['ticker'] == 'TEST004', "Mid cap should be third"
    assert tickers[3]['ticker'] == 'TEST001', "Small cap should be last"
```

### Rollout Plan

**Phase 2.1: Development** (Day 1-2)
- [ ] Create `backfill_fundamentals_prioritized.py`
- [ ] Implement `backfill_cn_prioritized()`
- [ ] Implement `generate_coverage_report()`
- [ ] Write unit tests

**Phase 2.2: Testing** (Day 2)
- [ ] Test on 100 tickers (all market cap tiers)
- [ ] Verify sorting order
- [ ] Generate test coverage report

**Phase 2.3: Production Deployment** (Day 3)
- [ ] Run prioritized backfill for CN (top 1000)
- [ ] Run prioritized backfill for HK (top 500)
- [ ] Generate and review coverage report
- [ ] Target: 99%+ coverage for MEGA/LARGE tiers

---

## 🔄 Phase 3: Multi-Source Fallback Enhancement (P2 - Medium Priority)

### Overview

**Goal**: Improve data source redundancy with yfinance ANNUAL (HK) and Naver Finance (optional)
**Impact**: +3%p HK coverage, +1.5%p CN coverage
**Estimated Time**: 2-4 days
**Priority**: P2 (Medium - Nice to have)

### Requirements

#### FR-3.1: yfinance ANNUAL Fallback (HK Only)

**Requirement**: Add yfinance ANNUAL balance sheet as fallback for HK stocks (QUARTERLY not available)

**Rationale**:
- HK stocks on yfinance do NOT have QUARTERLY balance sheets
- But ANNUAL balance sheets are available for most HK stocks
- Can provide yearly total_assets, total_liabilities, etc.

**Acceptance Criteria**:
- [ ] Fetch yfinance `stock.balance_sheet` (annual)
- [ ] Parse to database format (same as QUARTERLY)
- [ ] Set `period_type = 'ANNUAL'`
- [ ] Only activate for HK region
- [ ] Fallback order: AkShare → yfinance ANNUAL

**Implementation**:

```python
# File: scripts/backfill_fundamentals_yfinance.py
# Location: Add new method to existing class

def fetch_yfinance_annual_data(self, ticker: str, region: str) -> Optional[Dict]:
    """
    Fetch yfinance ANNUAL balance sheet (HK only, CN has QUARTERLY)

    Args:
        ticker: Stock ticker (e.g., '00700' for HK)
        region: Must be 'HK' (CN should use QUARTERLY)

    Returns:
        Dictionary ready for DB insertion or None if failed

    Note:
        - HK stocks don't have QUARTERLY data on yfinance
        - ANNUAL data is better than no data
        - Will be marked with period_type = 'ANNUAL'
    """
    if region != 'HK':
        logger.warning(f"⚠️ yfinance ANNUAL only supported for HK (got {region})")
        return None

    # Format ticker for yfinance (e.g., '00700' → '0700.HK')
    yf_ticker = f"{ticker.lstrip('0')}.HK"

    try:
        stock = yf.Ticker(yf_ticker)

        # Get ANNUAL balance sheet
        bs_annual = stock.balance_sheet  # NOT quarterly_balance_sheet

        if bs_annual is None or bs_annual.empty:
            logger.debug(f"No ANNUAL balance sheet for {yf_ticker}")
            return None

        # Get most recent annual report
        latest_date = bs_annual.columns[0]
        latest_data = bs_annual[latest_date]

        # Parse balance sheet data
        fundamentals = {
            'ticker': ticker,
            'region': region,
            'date': latest_date.strftime('%Y-%m-%d'),
            'period_type': 'ANNUAL',  # Mark as annual
            'data_source': 'yfinance_annual',

            # Balance Sheet (absolute values)
            'total_assets': self._safe_float(latest_data.get('Total Assets')),
            'total_liabilities': self._safe_float(latest_data.get('Total Liabilities Net Minority Interest')),
            'total_equity': self._safe_float(latest_data.get('Stockholders Equity')),
            'current_assets': self._safe_float(latest_data.get('Current Assets')),
            'current_liabilities': self._safe_float(latest_data.get('Current Liabilities')),
            'cash_and_equivalents': self._safe_float(latest_data.get('Cash And Cash Equivalents')),
            'accounts_receivable': self._safe_float(latest_data.get('Accounts Receivable')),
            'inventory': self._safe_float(latest_data.get('Inventory')),
            'pp_e': self._safe_float(latest_data.get('Net PPE')),
            'retained_earnings': self._safe_float(latest_data.get('Retained Earnings')),
        }

        # Get income statement (ANNUAL)
        income = stock.financials  # Annual income statement
        if income is not None and not income.empty and latest_date in income.columns:
            income_data = income[latest_date]

            fundamentals.update({
                'revenue': self._safe_float(income_data.get('Total Revenue')),
                'net_income': self._safe_float(income_data.get('Net Income')),
                'operating_profit': self._safe_float(income_data.get('Operating Income')),
                'gross_profit': self._safe_float(income_data.get('Gross Profit')),
                'ebitda': self._safe_float(income_data.get('EBITDA')),
            })

        # Get cash flow (ANNUAL)
        cashflow = stock.cashflow  # Annual cash flow
        if cashflow is not None and not cashflow.empty and latest_date in cashflow.columns:
            cf_data = cashflow[latest_date]

            fundamentals.update({
                'operating_cash_flow': self._safe_float(cf_data.get('Operating Cash Flow')),
                'capex': self._safe_float(cf_data.get('Capital Expenditure')),
                'fcf': self._safe_float(cf_data.get('Free Cash Flow')),
            })

        logger.debug(f"✅ Fetched ANNUAL data for {ticker} ({latest_date.strftime('%Y')})")
        return fundamentals

    except Exception as e:
        logger.error(f"❌ yfinance ANNUAL failed for {ticker}: {e}")
        return None
```

#### FR-3.2: Naver Finance Integration (Optional)

**Requirement**: Add Naver Finance as supplementary data source for CN/HK stocks popular in Korea

**Acceptance Criteria**:
- [ ] Scrape Naver Finance overseas stock page
- [ ] Support ~500 popular CN/HK stocks
- [ ] Parse Korean financial terms to English
- [ ] Set `data_source = 'naver'`
- [ ] Fallback order: AkShare → yfinance → Naver

**Implementation**:

```python
# File: modules/api_clients/naver_finance_api.py (NEW FILE)

import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class NaverFinanceAPI:
    """
    Naver Finance API wrapper for overseas stocks (CN/HK)

    Features:
    - Scrapes Naver Finance overseas stock pages
    - Supports ~500 popular CN/HK stocks traded by Korean investors
    - Parses Korean financial terms to English

    Limitations:
    - Only covers stocks popular in Korea (not full CN/HK universe)
    - Requires web scraping (no official API)
    - Rate limiting needed (1 req/2sec recommended)

    Data Source:
        https://finance.naver.com/world/sise.naver?symbol={ticker}
    """

    BASE_URL = "https://finance.naver.com/world"

    def __init__(self, rate_limit_per_second: float = 0.5):
        """
        Initialize Naver Finance API wrapper

        Args:
            rate_limit_per_second: Max requests per second (default: 0.5 = 1 req per 2 sec)
        """
        self.rate_limit = rate_limit_per_second
        self.last_request_time = 0

    def get_ticker_symbol(self, ticker: str, region: str) -> Optional[str]:
        """
        Convert CN/HK ticker to Naver Finance symbol

        Args:
            ticker: Stock ticker (e.g., '600519' for CN, '00700' for HK)
            region: 'CN' or 'HK'

        Returns:
            Naver symbol (e.g., 'HKS00700' for Tencent) or None if not found

        Mapping:
            - CN: 'SHS{ticker}' for Shanghai (6xxxxx)
            - CN: 'SZS{ticker}' for Shenzhen (0xxxxx, 3xxxxx)
            - HK: 'HKS{ticker}' for Hong Kong
        """
        if region == 'HK':
            return f"HKS{ticker.zfill(5)}"
        elif region == 'CN':
            if ticker.startswith('6'):
                return f"SHS{ticker}"  # Shanghai
            elif ticker.startswith(('0', '3')):
                return f"SZS{ticker}"  # Shenzhen

        return None

    def get_fundamental_data(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Fetch fundamental data from Naver Finance

        Args:
            ticker: Stock ticker
            region: 'CN' or 'HK'

        Returns:
            Dictionary with fundamental data or None if not available

        Note:
            - Only covers ~500 popular stocks
            - Returns None for stocks not tracked by Naver
        """
        naver_symbol = self.get_ticker_symbol(ticker, region)
        if not naver_symbol:
            return None

        try:
            # Fetch page
            url = f"{self.BASE_URL}/sise.naver?symbol={naver_symbol}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.debug(f"Naver Finance: {ticker} not found (HTTP {response.status_code})")
                return None

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract financial data (simplified - actual implementation needs more robust parsing)
            # This is a placeholder - real implementation would parse Naver's HTML structure

            fundamentals = {
                'ticker': ticker,
                'region': region,
                'date': None,  # Parse from page
                'period_type': 'QUARTERLY',
                'data_source': 'naver',
                # Parse Korean financial terms:
                # '매출액' → revenue
                # '영업이익' → operating_profit
                # '당기순이익' → net_income
                # '자산총계' → total_assets
                # ... (full implementation needed)
            }

            logger.debug(f"✅ Fetched Naver data for {ticker}")
            return fundamentals

        except Exception as e:
            logger.error(f"❌ Naver Finance failed for {ticker}: {e}")
            return None
```

**Note**: Naver Finance integration is **optional** and requires significant web scraping work. Recommend prioritizing Phase 1-2 first, then evaluate if Naver data is needed based on coverage gaps.

### Testing Requirements

#### Test Case 3.1: yfinance ANNUAL for HK

```python
# File: tests/integration/test_yfinance_annual_hk.py

def test_yfinance_annual_hk_tencent():
    """Test yfinance ANNUAL data collection for HK stock (Tencent)"""
    from scripts.backfill_fundamentals_yfinance import YFinanceFundamentalBackfiller

    db = PostgresDatabaseManager()
    backfiller = YFinanceFundamentalBackfiller(db, dry_run=False)

    # Fetch ANNUAL data for Tencent (00700)
    data = backfiller.fetch_yfinance_annual_data(ticker='00700', region='HK')

    # Verify data structure
    assert data is not None, "Should fetch ANNUAL data for Tencent"
    assert data['ticker'] == '00700'
    assert data['region'] == 'HK'
    assert data['period_type'] == 'ANNUAL'
    assert data['data_source'] == 'yfinance_annual'

    # Verify balance sheet fields
    assert data['total_assets'] is not None, "Should have total_assets"
    assert data['total_liabilities'] is not None, "Should have total_liabilities"
    assert data['total_equity'] is not None, "Should have total_equity"

    # Verify income statement fields
    assert data['revenue'] is not None, "Should have revenue"
    assert data['net_income'] is not None, "Should have net_income"
```

### Rollout Plan

**Phase 3.1: yfinance ANNUAL (HK)** (Day 1-2)
- [ ] Implement `fetch_yfinance_annual_data()`
- [ ] Integrate into HKAdapter fallback chain
- [ ] Test on 10 HK stocks
- [ ] Full HK backfill

**Phase 3.2: Naver Finance (Optional)** (Day 3-4)
- [ ] Evaluate coverage gap after Phase 1-2
- [ ] If gap > 5%: Implement Naver scraper
- [ ] If gap < 5%: Skip (diminishing returns)

---

## 📊 Phase 4: Monitoring & Quality Assurance (P2 - Medium Priority)

### Overview

**Goal**: Real-time coverage monitoring and data quality validation
**Impact**: Proactive issue detection, continuous improvement
**Estimated Time**: 2-3 days
**Priority**: P2 (Medium - Nice to have)

### Requirements

#### FR-4.1: Coverage Dashboard

**Requirement**: Real-time fundamental data coverage dashboard

**Acceptance Criteria**:
- [ ] Coverage by region (CN, HK)
- [ ] Coverage by market cap tier (MEGA, LARGE, MID, SMALL)
- [ ] Coverage by data source (AkShare, yfinance QUARTERLY, yfinance ANNUAL, Naver)
- [ ] Trend chart (coverage over time)
- [ ] Missing ticker list (top 100 by market cap)

**Implementation**:

```python
# File: scripts/generate_coverage_dashboard.py (NEW FILE)

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.db_manager_postgres import PostgresDatabaseManager
from datetime import datetime, timedelta

def generate_coverage_dashboard(output_path: str = 'reports/coverage_dashboard.html'):
    """
    Generate interactive coverage dashboard using Plotly

    Features:
    - Coverage by region and tier
    - Coverage trend over time
    - Missing ticker analysis
    - Data source breakdown

    Output:
        HTML file with interactive dashboard
    """
    db = PostgresDatabaseManager()

    # Query 1: Coverage by region and tier
    coverage_data = db.execute_query("""
        WITH ticker_tiers AS (
            SELECT
                t.region,
                t.ticker,
                t.name,
                t.market_cap,
                CASE
                    WHEN t.market_cap >= 100000000000 THEN 'MEGA'
                    WHEN t.market_cap >= 10000000000 THEN 'LARGE'
                    WHEN t.market_cap >= 1000000000 THEN 'MID'
                    ELSE 'SMALL'
                END as tier,
                CASE
                    WHEN tf.ticker IS NOT NULL THEN 1
                    ELSE 0
                END as has_fundamentals,
                tf.data_source
            FROM tickers t
            LEFT JOIN ticker_fundamentals tf
                ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE t.region IN ('CN', 'HK')
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
        )
        SELECT
            region,
            tier,
            COUNT(*) as total,
            SUM(has_fundamentals) as with_fund,
            ROUND(SUM(has_fundamentals)::numeric / COUNT(*) * 100, 2) as coverage_pct
        FROM ticker_tiers
        GROUP BY region, tier
        ORDER BY region,
            CASE tier
                WHEN 'MEGA' THEN 1
                WHEN 'LARGE' THEN 2
                WHEN 'MID' THEN 3
                WHEN 'SMALL' THEN 4
            END;
    """)

    df_coverage = pd.DataFrame(coverage_data)

    # Query 2: Coverage trend (last 30 days)
    trend_data = db.execute_query("""
        SELECT
            DATE(created_at) as date,
            region,
            COUNT(DISTINCT ticker) as new_tickers
        FROM ticker_fundamentals
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at), region
        ORDER BY date, region;
    """)

    df_trend = pd.DataFrame(trend_data)

    # Query 3: Missing tickers (top 100 by market cap)
    missing_data = db.execute_query("""
        SELECT
            t.region,
            t.ticker,
            t.name,
            t.market_cap,
            CASE
                WHEN t.market_cap >= 100000000000 THEN 'MEGA'
                WHEN t.market_cap >= 10000000000 THEN 'LARGE'
                WHEN t.market_cap >= 1000000000 THEN 'MID'
                ELSE 'SMALL'
            END as tier
        FROM tickers t
        LEFT JOIN ticker_fundamentals tf
            ON t.ticker = tf.ticker AND t.region = tf.region
        WHERE t.region IN ('CN', 'HK')
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
          AND tf.ticker IS NULL
        ORDER BY t.market_cap DESC NULLS LAST
        LIMIT 100;
    """)

    df_missing = pd.DataFrame(missing_data)

    # Create dashboard
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Coverage by Region and Tier',
            'Coverage Trend (Last 30 Days)',
            'Missing Tickers by Tier',
            'Data Source Breakdown'
        ),
        specs=[
            [{'type': 'bar'}, {'type': 'scatter'}],
            [{'type': 'bar'}, {'type': 'pie'}]
        ]
    )

    # Plot 1: Coverage by region and tier
    for region in df_coverage['region'].unique():
        df_region = df_coverage[df_coverage['region'] == region]

        fig.add_trace(
            go.Bar(
                x=df_region['tier'],
                y=df_region['coverage_pct'],
                name=region,
                text=df_region['coverage_pct'].apply(lambda x: f"{x:.1f}%"),
                textposition='auto'
            ),
            row=1, col=1
        )

    # Plot 2: Coverage trend
    for region in df_trend['region'].unique():
        df_region = df_trend[df_trend['region'] == region]

        fig.add_trace(
            go.Scatter(
                x=df_region['date'],
                y=df_region['new_tickers'].cumsum(),
                mode='lines+markers',
                name=f"{region} Cumulative"
            ),
            row=1, col=2
        )

    # Plot 3: Missing tickers by tier
    missing_counts = df_missing.groupby('tier').size().reset_index(name='count')

    fig.add_trace(
        go.Bar(
            x=missing_counts['tier'],
            y=missing_counts['count'],
            text=missing_counts['count'],
            textposition='auto',
            marker_color='red',
            showlegend=False
        ),
        row=2, col=1
    )

    # Plot 4: Data source breakdown (placeholder - implement based on actual data)
    # ...

    # Update layout
    fig.update_layout(
        title_text="Fundamental Data Coverage Dashboard",
        height=800,
        showlegend=True
    )

    # Save to HTML
    fig.write_html(output_path)
    print(f"✅ Dashboard saved to {output_path}")
```

#### FR-4.2: Data Quality Validation

**Requirement**: Automated data quality checks for collected fundamentals

**Acceptance Criteria**:
- [ ] Detect NULL/missing critical fields (EPS, revenue, total_assets)
- [ ] Detect anomalous values (negative total_assets, revenue)
- [ ] Detect stale data (last update > 90 days)
- [ ] Generate quality report with actionable recommendations

**Implementation**:

```python
# File: scripts/validate_fundamental_data_quality.py (NEW FILE)

from modules.db_manager_postgres import PostgresDatabaseManager
from datetime import datetime, timedelta
import pandas as pd

def validate_data_quality(region: str = 'CN') -> Dict:
    """
    Validate fundamental data quality for a region

    Checks:
    1. Missing critical fields (EPS, revenue, total_assets)
    2. Anomalous values (negative assets, extreme ratios)
    3. Stale data (last update > 90 days)
    4. Data consistency (e.g., assets = liabilities + equity)

    Args:
        region: Target region ('CN' or 'HK')

    Returns:
        Dictionary with validation results and recommendations
    """
    db = PostgresDatabaseManager()

    results = {
        'region': region,
        'timestamp': datetime.now().isoformat(),
        'checks': {},
        'recommendations': []
    }

    # Check 1: Missing critical fields
    missing_fields = db.execute_query("""
        SELECT
            COUNT(*) as total,
            COUNT(eps) as has_eps,
            COUNT(revenue) as has_revenue,
            COUNT(total_assets) as has_total_assets,
            COUNT(net_income) as has_net_income
        FROM ticker_fundamentals
        WHERE region = %s
          AND period_type = 'QUARTERLY'
          AND date >= CURRENT_DATE - INTERVAL '1 year';
    """, (region,))[0]

    results['checks']['missing_fields'] = {
        'total_records': missing_fields['total'],
        'eps_coverage': missing_fields['has_eps'] / missing_fields['total'] * 100 if missing_fields['total'] > 0 else 0,
        'revenue_coverage': missing_fields['has_revenue'] / missing_fields['total'] * 100 if missing_fields['total'] > 0 else 0,
        'total_assets_coverage': missing_fields['has_total_assets'] / missing_fields['total'] * 100 if missing_fields['total'] > 0 else 0,
    }

    # Recommendation: If any coverage < 90%, flag for re-collection
    for field, coverage in results['checks']['missing_fields'].items():
        if field.endswith('_coverage') and coverage < 90:
            results['recommendations'].append({
                'priority': 'HIGH',
                'issue': f"{field.replace('_coverage', '')} coverage is {coverage:.1f}% (target: 90%+)",
                'action': f"Re-run backfill with multi-source fallback for {region}"
            })

    # Check 2: Anomalous values
    anomalies = db.execute_query("""
        SELECT
            COUNT(*) FILTER (WHERE total_assets < 0) as negative_assets,
            COUNT(*) FILTER (WHERE revenue < 0 AND revenue IS NOT NULL) as negative_revenue,
            COUNT(*) FILTER (WHERE ABS((total_assets - total_liabilities - total_equity) / NULLIF(total_assets, 0)) > 0.01) as balance_sheet_mismatch
        FROM ticker_fundamentals
        WHERE region = %s
          AND period_type = 'QUARTERLY'
          AND date >= CURRENT_DATE - INTERVAL '1 year';
    """, (region,))[0]

    results['checks']['anomalies'] = anomalies

    if anomalies['negative_assets'] > 0:
        results['recommendations'].append({
            'priority': 'CRITICAL',
            'issue': f"{anomalies['negative_assets']} records with negative total_assets",
            'action': "Review data source and parser logic for balance sheet fields"
        })

    # Check 3: Stale data
    stale_data = db.execute_query("""
        SELECT
            t.ticker,
            t.name,
            MAX(tf.date) as latest_date,
            CURRENT_DATE - MAX(tf.date) as days_since_update
        FROM tickers t
        LEFT JOIN ticker_fundamentals tf
            ON t.ticker = tf.ticker AND t.region = tf.region
        WHERE t.region = %s
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
        GROUP BY t.ticker, t.name
        HAVING MAX(tf.date) < CURRENT_DATE - INTERVAL '90 days'
           OR MAX(tf.date) IS NULL
        ORDER BY days_since_update DESC NULLS FIRST
        LIMIT 50;
    """, (region,))

    results['checks']['stale_data'] = {
        'count': len(stale_data),
        'samples': stale_data[:10]  # Top 10 stale tickers
    }

    if len(stale_data) > 10:
        results['recommendations'].append({
            'priority': 'MEDIUM',
            'issue': f"{len(stale_data)} tickers with stale data (>90 days old or missing)",
            'action': f"Schedule weekly backfill for {region} to keep data fresh"
        })

    return results

def generate_quality_report(regions: List[str] = ['CN', 'HK']) -> str:
    """
    Generate data quality report for multiple regions

    Args:
        regions: List of regions to validate

    Returns:
        Markdown formatted quality report
    """
    report = f"""# Fundamental Data Quality Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

"""

    for region in regions:
        results = validate_data_quality(region)

        report += f"""## {region} Region

### Missing Field Coverage

| Field | Coverage | Status |
|-------|----------|--------|
"""

        for field, value in results['checks']['missing_fields'].items():
            if field.endswith('_coverage'):
                field_name = field.replace('_coverage', '').upper()
                status = '✅ PASS' if value >= 90 else '❌ FAIL'
                report += f"| {field_name} | {value:.1f}% | {status} |\n"

        report += f"""
### Data Anomalies

- Negative Assets: {results['checks']['anomalies']['negative_assets']}
- Negative Revenue: {results['checks']['anomalies']['negative_revenue']}
- Balance Sheet Mismatches: {results['checks']['anomalies']['balance_sheet_mismatch']}

### Stale Data

- Tickers with stale data (>90 days): {results['checks']['stale_data']['count']}

### Recommendations

"""

        if results['recommendations']:
            for rec in results['recommendations']:
                priority_icon = '🔴' if rec['priority'] == 'CRITICAL' else '🟡' if rec['priority'] == 'HIGH' else '🟢'
                report += f"{priority_icon} **{rec['priority']}**: {rec['issue']}\n  → {rec['action']}\n\n"
        else:
            report += "✅ No issues detected. Data quality is excellent.\n\n"

        report += "---\n\n"

    return report
```

### Testing Requirements

#### Test Case 4.1: Coverage Dashboard Generation

```python
# File: tests/integration/test_coverage_dashboard.py

def test_coverage_dashboard_generates():
    """Test coverage dashboard generates without errors"""
    from scripts.generate_coverage_dashboard import generate_coverage_dashboard

    # Generate dashboard
    output_path = 'test_coverage_dashboard.html'
    generate_coverage_dashboard(output_path=output_path)

    # Verify file exists
    assert os.path.exists(output_path), "Dashboard file should be created"

    # Verify file is not empty
    assert os.path.getsize(output_path) > 1000, "Dashboard should have content"

    # Cleanup
    os.remove(output_path)
```

### Rollout Plan

**Phase 4.1: Coverage Dashboard** (Day 1-2)
- [ ] Implement `generate_coverage_dashboard.py`
- [ ] Test with current data
- [ ] Schedule daily dashboard generation (cron)

**Phase 4.2: Data Quality Validation** (Day 2-3)
- [ ] Implement `validate_fundamental_data_quality.py`
- [ ] Run validation for CN and HK
- [ ] Fix any critical issues identified
- [ ] Schedule weekly quality reports

---

## 📏 Success Metrics & KPIs

### Primary Metrics

| Metric | Baseline | Phase 1 Target | Phase 2 Target | Phase 3-4 Target |
|--------|----------|---------------|---------------|-----------------|
| **CN Coverage** | 50% | 98%+ | 99%+ (MEGA/LARGE) | 99.5%+ |
| **HK Coverage** | 50% | 98%+ | 99%+ (MEGA/LARGE) | 98%+ (+ ANNUAL) |
| **API Efficiency** | 100% | 50% (exclude non-stocks) | 40% (prioritization) | 40% |
| **Data Quality** | Unknown | 95%+ field completeness | 98%+ (top tier) | 99%+ |

### Secondary Metrics

| Metric | Target |
|--------|--------|
| **Large-Cap Coverage (MEGA tier)** | 99.9%+ |
| **Mid-Cap Coverage (LARGE tier)** | 99%+ |
| **Small-Cap Coverage (MID tier)** | 95%+ |
| **Micro-Cap Coverage (SMALL tier)** | 70%+ (best-effort) |
| **Data Freshness** | <30 days for 95% of stocks |
| **Multi-Source Fallback Rate** | <5% (primary source succeeds 95%+) |

### Quality Gates

**Phase 1 Gate** (Required to proceed to Phase 2):
- [x] Asset type classification implemented
- [x] ETFs/funds excluded from backfill
- [x] CN coverage ≥ 95%
- [x] HK coverage ≥ 95%
- [x] No critical bugs in production

**Phase 2 Gate** (Required to proceed to Phase 3):
- [ ] Market cap sorting working correctly
- [ ] MEGA tier coverage ≥ 99%
- [ ] Coverage report generates successfully
- [ ] No performance degradation

**Phase 3 Gate** (Optional - can skip if coverage sufficient):
- [ ] yfinance ANNUAL working for HK
- [ ] Total HK coverage ≥ 98%
- [ ] Evaluate Naver Finance ROI (implement only if gap > 5%)

**Phase 4 Gate** (Required for production readiness):
- [ ] Coverage dashboard operational
- [ ] Data quality validation passes for all regions
- [ ] <5 critical/high priority recommendations
- [ ] Documentation complete

---

## 🚀 Implementation Timeline

### Week 1: Foundation (Phase 1)

**Day 1-2**: Asset Type Filtering
- Implement `_classify_asset_type()` in adapters
- Add `asset_types` parameter to backfill scripts
- Write unit tests
- Run database migration

**Day 3**: Testing & Validation
- Integration tests for filtering
- Test backfill (100 tickers CN + 100 HK)
- Verify success rate improvement

**Day 4-5**: Production Deployment
- Deploy Phase 1 to production
- Full CN backfill (stocks only, ~2,000 tickers)
- Full HK backfill (stocks only, ~4,000 tickers)
- Monitor success rate (target: 98%+)

### Week 2: Prioritization & Monitoring (Phase 2 + Phase 4)

**Day 1-2**: Market Cap Prioritization
- Implement `backfill_fundamentals_prioritized.py`
- Test on 100 tickers (all tiers)
- Generate coverage report

**Day 3**: Production Deployment
- Prioritized backfill for CN (top 1000)
- Prioritized backfill for HK (top 500)
- Verify 99%+ coverage for MEGA/LARGE tiers

**Day 4-5**: Monitoring Dashboard
- Implement coverage dashboard
- Implement data quality validation
- Schedule daily/weekly automated reports

### Week 3 (Optional): Multi-Source Enhancement (Phase 3)

**Day 1-2**: yfinance ANNUAL (HK)
- Implement `fetch_yfinance_annual_data()`
- Test on 10 HK stocks
- Full HK ANNUAL backfill

**Day 3-4**: Evaluate Naver Finance
- Measure coverage gap after Phase 1-2
- If gap > 5%: Implement Naver scraper
- If gap < 5%: Skip (diminishing returns)

**Day 5**: Final Validation
- Full system test (all phases integrated)
- Quality gate validation
- Production readiness review

---

## 🔒 Risk Management

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **API rate limiting** | Medium | High | Implement conservative rate limits (1.5 req/s), retry logic |
| **yfinance data unavailable** | Low | Medium | Multi-source fallback (AkShare primary) |
| **Database performance degradation** | Low | High | Index optimization, batch inserts, monitoring |
| **Asset type misclassification** | Medium | Medium | Conservative defaults, manual review of edge cases |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Production downtime during migration** | Low | High | Blue-green deployment, rollback plan |
| **Data quality issues after deployment** | Medium | Medium | Comprehensive testing, staged rollout |
| **User confusion (asset type filtering)** | Low | Low | Clear documentation, changelog |

### Rollback Plan

If critical issues occur post-deployment:

1. **Phase 1 Rollback**:
   - Remove `asset_type` filter from backfill scripts
   - Revert to collecting all tickers (including ETFs)
   - Database schema changes are backward compatible (no rollback needed)

2. **Phase 2 Rollback**:
   - Revert to non-prioritized backfill (random order)
   - Coverage report generation is optional (can disable)

3. **Phase 3-4 Rollback**:
   - Disable yfinance ANNUAL fallback
   - Disable Naver Finance integration
   - Dashboard/validation are read-only (no rollback impact)

---

## 📝 Documentation Requirements

### Code Documentation

- [ ] Docstrings for all new functions/methods
- [ ] Inline comments for complex logic
- [ ] Type hints for all parameters and return values
- [ ] Usage examples in docstrings

### User Documentation

- [ ] **User Guide**: How to run prioritized backfill
- [ ] **Troubleshooting Guide**: Common errors and solutions
- [ ] **Coverage Report Guide**: How to interpret coverage dashboard
- [ ] **Changelog**: What changed in each phase

### Technical Documentation

- [ ] **Architecture Diagram**: Updated with new components
- [ ] **API Reference**: New parameters and methods
- [ ] **Database Schema**: New columns and indexes
- [ ] **Testing Guide**: How to run tests

### Files to Create/Update

1. **NEW**: `docs/architecture/CN_HK_FUNDAMENTAL_DATA_IMPROVEMENT_PRD.md` (this document)
2. **NEW**: `docs/guides/FUNDAMENTAL_BACKFILL_PRIORITIZED_GUIDE.md`
3. **UPDATE**: `docs/architecture/QUANT_DATABASE_SCHEMA.md` (add `asset_type` column)
4. **UPDATE**: `docs/guides/QUANT_DEVELOPMENT_WORKFLOWS.md` (add prioritized backfill examples)
5. **NEW**: `docs/reports/CN_HK_COVERAGE_REPORT_TEMPLATE.md`

---

## 🎓 Appendix

### A. Market Cap Tier Definitions

| Tier | CN (CNY) | HK (HKD) | Description |
|------|---------|---------|-------------|
| **MEGA** | ≥ 1000亿 (100B) | ≥ 100B | Largest companies (top 50-100) |
| **LARGE** | ≥ 100亿 (10B) | ≥ 10B | Large-cap companies (top 500) |
| **MID** | ≥ 10亿 (1B) | ≥ 1B | Mid-cap companies |
| **SMALL** | < 10亿 (1B) | < 1B | Small-cap companies |

### B. Data Source Comparison

| Data Source | CN Coverage | HK Coverage | Fields | Cost | Reliability |
|------------|------------|------------|--------|------|-------------|
| **AkShare** | 98% (stocks) | 95% (stocks) | 86 (CN), 36 (HK) | Free | High (98%+) |
| **yfinance QUARTERLY** | 100% (large-cap) | N/A | 22 (balance sheet) | Free | High (99%+) |
| **yfinance ANNUAL** | N/A | 90% (all cap) | 22 (balance sheet) | Free | Medium (85%+) |
| **Naver Finance** | 30% (popular) | 30% (popular) | 15 (limited) | Free | Medium (scraping) |

### C. Glossary

- **Asset Type**: Classification of security (STOCK, ETF, MUTUALFUND, INDEX)
- **Market Cap Tier**: Category based on market capitalization (MEGA, LARGE, MID, SMALL)
- **Coverage**: Percentage of tickers with fundamental data available
- **Prioritized Backfill**: Data collection sorted by importance (market cap)
- **Multi-Source Fallback**: Trying multiple data sources in order until success
- **Period Type**: Reporting period (QUARTERLY, ANNUAL, TTM)

---

## ✅ Approval & Sign-off

### Stakeholders

| Role | Name | Approval Date | Signature |
|------|------|---------------|-----------|
| **Product Owner** | [TBD] | [Date] | [Signature] |
| **Tech Lead** | [TBD] | [Date] | [Signature] |
| **QA Lead** | [TBD] | [Date] | [Signature] |

### Approval Checklist

- [ ] Technical feasibility validated
- [ ] Resource allocation confirmed
- [ ] Timeline agreed upon
- [ ] Success metrics defined
- [ ] Risk mitigation plan approved
- [ ] Quality gates established
- [ ] Documentation plan approved

---

**Document Status**: ✅ Ready for Implementation
**Next Steps**: Begin Phase 1 Development (Week 1, Day 1)
**Version**: 1.0.0
**Last Updated**: 2025-12-20

---

**End of PRD**
