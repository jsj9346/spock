# Multi-Region Production Deployment Design

**Project**: Spock Trading System
**Design Type**: Production Deployment Architecture
**Date**: 2025-10-15
**Status**: 🎯 **DESIGN PHASE**
**Target**: Global Multi-Region Trading Platform (KR, US, CN, HK, JP, VN)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Deployment Strategy](#deployment-strategy)
4. [Database Architecture](#database-architecture)
5. [API Orchestration](#api-orchestration)
6. [Monitoring & Observability](#monitoring--observability)
7. [Security & Compliance](#security--compliance)
8. [Risk Mitigation](#risk-mitigation)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Performance Benchmarks](#performance-benchmarks)

---

## Executive Summary

### Design Goal
Design and implement a production-ready multi-region deployment for the Spock Trading System, enabling simultaneous trading across **6 global markets** (KR, US, CN, HK, JP, VN) with unified data management, automated failover, and region-specific optimization.

### Key Design Principles
1. **Single Source of Truth**: Unified SQLite database with region-aware architecture
2. **Adapter Independence**: Each region operates independently with shared infrastructure
3. **Progressive Rollout**: Phased deployment with validation gates
4. **Zero-Downtime**: Continuous operation during regional market hours
5. **Data Integrity**: 100% consistency across regions with automatic validation

### Success Criteria
- ✅ Support 6 simultaneous regions without data contamination
- ✅ <1s latency for cross-region data queries
- ✅ 99.9% uptime during regional market hours
- ✅ Automated failover within 30 seconds
- ✅ Zero data loss during regional transitions

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Spock Trading System                            │
│                   Multi-Region Architecture                          │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────── API Layer ────────────────────────────────┐
│                                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │   KIS    │  │ Polygon  │  │ AkShare  │  │ yfinance │          │
│  │   API    │  │   API    │  │   API    │  │   API    │          │
│  │ (KR/All) │  │   (US)   │  │   (CN)   │  │(HK/JP/VN)│          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │             │              │             │                 │
└───────┼─────────────┼──────────────┼─────────────┼─────────────────┘
        │             │              │             │
┌───────┼─────────────┼──────────────┼─────────────┼─────────────────┐
│       │             │              │             │                 │
│       ▼             ▼              ▼             ▼                 │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │           Adapter Orchestration Layer                     │     │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│     │
│  │  │   KR   │ │   US   │ │   CN   │ │   HK   │ │   JP   ││     │
│  │  │Adapter │ │Adapter │ │Adapter │ │Adapter │ │Adapter ││     │
│  │  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘│     │
│  │       │          │          │          │          │      │     │
│  │  ┌────┴──────────┴──────────┴──────────┴──────────┴────┐│     │
│  │  │         BaseAdapter (Region Auto-Injection)          ││     │
│  │  └──────────────────────┬───────────────────────────────┘│     │
│  └─────────────────────────┼──────────────────────────────────┘     │
│                            │                                       │
└────────────────────────────┼───────────────────────────────────────┘
                             │
┌────────────────────────────┼───────────────────────────────────────┐
│                            ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │        Unified Database Layer (SQLite)                    │     │
│  │                                                            │     │
│  │  ┌───────────┐  ┌────────────┐  ┌─────────────────┐     │     │
│  │  │  tickers  │  │ ohlcv_data │  │technical_analysis│     │     │
│  │  │ (region)  │  │ (region)   │  │    (region)      │     │     │
│  │  └───────────┘  └────────────┘  └─────────────────┘     │     │
│  │                                                            │     │
│  │  UNIQUE(ticker, region, timeframe, date)                  │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────── Analysis & Trading Layer ────────────────────┐
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │      LayeredScoringEngine (Region-Aware)                 │      │
│  │  - Multi-region relative strength                        │      │
│  │  - Cross-region correlation analysis                     │      │
│  │  - Region-specific thresholds                            │      │
│  └─────────────────────────────────────────────────────────┘      │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │      Trading Engine (Multi-Region)                       │      │
│  │  - Region-specific order execution                       │      │
│  │  - Market hours coordination                             │      │
│  │  - Currency conversion                                   │      │
│  └─────────────────────────────────────────────────────────┘      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌──────────────── Monitoring & Alerting Layer ──────────────────────┐
│                                                                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐          │
│  │  Prometheus │  │   Grafana    │  │  Alert Manager  │          │
│  │  (Metrics)  │  │ (Dashboard)  │  │   (Alerts)      │          │
│  └─────────────┘  └──────────────┘  └─────────────────┘          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. API Layer
**Purpose**: External data source integration
**Components**:
- **KIS API**: Primary (KR) + Overseas (US, HK, CN, JP, VN) - 20 req/sec
- **Polygon.io**: US market backup - 5 req/min
- **AkShare**: China market backup - 1.5 req/sec
- **yfinance**: Global markets backup - 1.0 req/sec

**Design Decision**: Prefer KIS API for all markets (13x-240x faster) with fallback to legacy APIs

#### 2. Adapter Orchestration Layer
**Purpose**: Region-specific data collection and normalization
**Components**:
- **BaseAdapter**: Common functionality + auto-region injection
- **Regional Adapters**: KR, US, CN, HK, JP, VN (12 total: 6 KIS + 6 legacy)

**Design Patterns**:
- **Strategy Pattern**: Pluggable adapters per region
- **Template Method**: BaseAdapter defines common workflow
- **Factory Pattern**: Dynamic adapter selection based on region

#### 3. Database Layer
**Purpose**: Unified data storage with region isolation
**Key Features**:
- **Region Column**: Auto-injected by adapters
- **Multi-Region Constraints**: `UNIQUE(ticker, region, timeframe, date)`
- **Indexing**: Optimized for region-filtered queries

**Capacity Planning**:
- **Current**: 691,854 rows (KR only)
- **Target**: ~4.2M rows (6 regions × ~700K rows)
- **Database Size**: ~2GB → ~12GB (6x growth)

#### 4. Analysis & Trading Layer
**Purpose**: Multi-region trading logic
**Components**:
- **LayeredScoringEngine**: Region-aware scoring with cross-region analysis
- **Kelly Calculator**: Region-specific position sizing
- **Trading Engine**: Multi-region order execution with market hours coordination

---

## Deployment Strategy

### Phase 1: Foundation (Week 1)
**Goal**: Validate infrastructure and establish baseline

#### Tasks
1. **Database Preparation**
   - ✅ Region column migration (COMPLETE)
   - ✅ UNIQUE constraint updated (COMPLETE)
   - ✅ Indexing optimization (COMPLETE)

2. **Monitoring Setup**
   - [ ] Install Prometheus for metrics collection
   - [ ] Configure Grafana dashboards (per region)
   - [ ] Setup alert rules for data quality

3. **Baseline Validation**
   - [ ] Run KR adapter for 1 week
   - [ ] Measure baseline performance metrics
   - [ ] Validate data integrity (0 NULL regions)

**Success Criteria**:
- ✅ 0 NULL regions in ohlcv_data
- ✅ KR adapter 99.9% uptime
- ✅ Monitoring dashboards operational

---

### Phase 2: US Market Deployment (Week 2-3)
**Goal**: Deploy first international market with full validation

#### Option A: KIS API (Recommended)
```python
# Deploy US adapter with KIS API (240x faster)
from modules.market_adapters.us_adapter_kis import USAdapterKIS

app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')

us_adapter = USAdapterKIS(db, app_key, app_secret)

# Step 1: Scan tradable stocks (~3,000 tickers)
us_stocks = us_adapter.scan_stocks(force_refresh=True)

# Step 2: Collect OHLCV (250 days)
us_adapter.collect_stock_ohlcv(days=250)  # 20 req/sec
```

#### Option B: Polygon.io (Legacy Fallback)
```python
# Fallback to Polygon.io if KIS API issues
from modules.market_adapters.us_adapter import USAdapter

polygon_api_key = os.getenv('POLYGON_API_KEY')
us_adapter = USAdapter(db, api_key=polygon_api_key)

us_stocks = us_adapter.scan_stocks(force_refresh=True)
us_adapter.collect_stock_ohlcv(days=250)  # 5 req/min (slower)
```

#### Validation Steps
1. **Data Collection Test** (1 day)
   - Collect 10 tickers (AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META, NFLX, JPM, V)
   - Verify 250 days of OHLCV data
   - Validate technical indicators (MA, RSI, MACD, BB, ATR)

2. **Multi-Region Validation** (1 day)
   - Query KR and US data simultaneously
   - Verify no data contamination (ticker='005930' KR vs ticker='AAPL' US)
   - Measure cross-region query performance (<1s)

3. **Full US Deployment** (3 days)
   - Scan all US stocks (~3,000 tickers)
   - Collect 250-day OHLCV history
   - Validate region='US' for all rows

4. **Integration Testing** (2 days)
   - Run LayeredScoringEngine on US stocks
   - Test cross-region relative strength (US vs KR)
   - Validate Kelly Calculator for US positions

**Success Criteria**:
- ✅ ~750,000 US OHLCV rows (3,000 tickers × 250 days)
- ✅ 0 NULL regions
- ✅ No KR/US data contamination
- ✅ <1s cross-region query latency

**Rollback Plan**:
- Database backup before US deployment
- Script to DELETE FROM ohlcv_data WHERE region='US'
- Restore from backup if integrity issues

---

### Phase 3: Asia Markets Deployment (Week 4-6)
**Goal**: Deploy CN, HK, JP simultaneously with regional coordination

#### CN Market (China) - Week 4
**Adapter**: CNAdapterKIS (preferred) or CNAdapter (fallback)
**Tickers**: ~1,500 (선강통/후강통 A-shares only)
**Expected Rows**: ~375,000 (1,500 × 250 days)

```python
# Deploy China adapter
from modules.market_adapters.cn_adapter_kis import CNAdapterKIS

cn_adapter = CNAdapterKIS(db, app_key, app_secret)
cn_stocks = cn_adapter.scan_stocks(force_refresh=True)
cn_adapter.collect_stock_ohlcv(days=250)
```

#### HK Market (Hong Kong) - Week 5
**Adapter**: HKAdapterKIS (preferred) or HKAdapter (fallback)
**Tickers**: ~800 (tradable via KIS)
**Expected Rows**: ~200,000 (800 × 250 days)

```python
# Deploy Hong Kong adapter
from modules.market_adapters.hk_adapter_kis import HKAdapterKIS

hk_adapter = HKAdapterKIS(db, app_key, app_secret)
hk_stocks = hk_adapter.scan_stocks(force_refresh=True)
hk_adapter.collect_stock_ohlcv(days=250)
```

#### JP Market (Japan) - Week 6
**Adapter**: JPAdapterKIS (preferred) or JPAdapter (fallback)
**Tickers**: ~700 (Nikkei 225 + TOPIX Core 30)
**Expected Rows**: ~175,000 (700 × 250 days)

```python
# Deploy Japan adapter
from modules.market_adapters.jp_adapter_kis import JPAdapterKIS

jp_adapter = JPAdapterKIS(db, app_key, app_secret)
jp_stocks = jp_adapter.scan_stocks(force_refresh=True)
jp_adapter.collect_stock_ohlcv(days=250)
```

**Success Criteria**:
- ✅ ~750,000 additional OHLCV rows (CN+HK+JP)
- ✅ 5 regions active (KR, US, CN, HK, JP)
- ✅ Cross-region correlation analysis functional

---

### Phase 4: VN Market Deployment (Week 7)
**Goal**: Complete global coverage with Vietnam market

**Adapter**: VNAdapterKIS (preferred) or VNAdapter (fallback)
**Tickers**: ~150 (VN30 index constituents)
**Expected Rows**: ~37,500 (150 × 250 days)

```python
# Deploy Vietnam adapter
from modules.market_adapters.vn_adapter_kis import VNAdapterKIS

vn_adapter = VNAdapterKIS(db, app_key, app_secret)
vn_stocks = vn_adapter.scan_stocks(force_refresh=True)
vn_adapter.collect_stock_ohlcv(days=250)
```

**Success Criteria**:
- ✅ ~37,500 VN OHLCV rows
- ✅ **6 regions operational** (KR, US, CN, HK, JP, VN)
- ✅ Total database: ~2.8M rows

---

### Phase 5: Production Optimization (Week 8)
**Goal**: Optimize performance and establish operational procedures

#### Tasks
1. **Database Optimization**
   - Analyze query patterns
   - Add composite indexes for common queries
   - Implement database VACUUM schedule

2. **Caching Strategy**
   - Implement Redis for ticker lists (24h TTL)
   - Cache LayeredScoringEngine results (1h TTL)
   - Pre-compute cross-region correlations (daily)

3. **Operational Procedures**
   - Daily data quality checks (NULL region validation)
   - Weekly backup rotation (7-day retention)
   - Monthly database optimization (VACUUM + ANALYZE)

**Success Criteria**:
- ✅ <500ms query latency for region-filtered queries
- ✅ Automated daily health checks
- ✅ Disaster recovery plan validated

---

## Database Architecture

### Multi-Region Data Model

```sql
-- Unified ohlcv_data table with region support
CREATE TABLE ohlcv_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,           -- KR, US, CN, HK, JP, VN
    timeframe TEXT NOT NULL,        -- D, W, M
    date TEXT NOT NULL,             -- YYYY-MM-DD

    -- OHLCV
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume BIGINT NOT NULL,

    -- Technical Indicators
    ma5 REAL, ma20 REAL, ma60 REAL, ma120 REAL, ma200 REAL,
    rsi_14 REAL,
    macd REAL, macd_signal REAL, macd_hist REAL,
    bb_upper REAL, bb_middle REAL, bb_lower REAL,
    atr_14 REAL,

    created_at TEXT NOT NULL,

    -- Multi-region unique constraint
    UNIQUE(ticker, region, timeframe, date),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);

-- Indexes for multi-region queries
CREATE INDEX idx_ohlcv_region ON ohlcv_data(region);
CREATE INDEX idx_ohlcv_region_ticker ON ohlcv_data(region, ticker);
CREATE INDEX idx_ohlcv_region_date ON ohlcv_data(region, date DESC);
CREATE INDEX idx_ohlcv_ticker_region_date ON ohlcv_data(ticker, region, date DESC);
```

### Query Patterns

```sql
-- Query 1: Single region stocks
SELECT * FROM ohlcv_data
WHERE region = 'US' AND ticker = 'AAPL'
ORDER BY date DESC LIMIT 250;

-- Query 2: Multi-region comparison
SELECT region, ticker, close, date
FROM ohlcv_data
WHERE ticker IN ('005930', 'AAPL', '600519')  -- Samsung (KR), Apple (US), Moutai (CN)
  AND date >= '2024-10-01'
ORDER BY region, date;

-- Query 3: Cross-region relative strength
SELECT
    o1.ticker,
    o1.region,
    (o1.close - o1.ma200) / o1.ma200 * 100 AS rs_score
FROM ohlcv_data o1
WHERE o1.date = (SELECT MAX(date) FROM ohlcv_data WHERE region = o1.region)
  AND o1.ma200 IS NOT NULL
ORDER BY rs_score DESC LIMIT 50;

-- Query 4: Region distribution
SELECT region, COUNT(*) as row_count, COUNT(DISTINCT ticker) as ticker_count
FROM ohlcv_data
GROUP BY region;
```

### Capacity Planning

| Region | Tickers | Days | Rows | Size (MB) | Status |
|--------|---------|------|------|-----------|--------|
| KR     | 2,758   | 250  | 689,500 | ~1,200 | ✅ LIVE |
| US     | 3,000   | 250  | 750,000 | ~1,300 | 🟡 PENDING |
| CN     | 1,500   | 250  | 375,000 | ~650   | 🟡 PENDING |
| HK     | 800     | 250  | 200,000 | ~350   | 🟡 PENDING |
| JP     | 700     | 250  | 175,000 | ~300   | 🟡 PENDING |
| VN     | 150     | 250  | 37,500  | ~65    | 🟡 PENDING |
| **Total** | **8,908** | **250** | **2,227,000** | **~3,865** | **Target** |

**Current Database**: 691,854 rows, ~1,200 MB
**Target Database**: 2,227,000 rows, ~3,865 MB (3.2x growth)
**Projected Query Time**: <500ms for region-filtered queries

---

## API Orchestration

### Multi-API Coordination Strategy

#### Primary: KIS API (Recommended)
**Advantage**: Single API key for all 6 markets, 20 req/sec

```python
class UnifiedKISOrchestrator:
    """
    Unified orchestration for all KIS API regions
    Manages rate limiting, failover, and region coordination
    """

    def __init__(self, app_key, app_secret):
        self.app_key = app_key
        self.app_secret = app_secret

        # Initialize all KIS adapters
        self.adapters = {
            'KR': KoreaAdapter(db, app_key, app_secret),
            'US': USAdapterKIS(db, app_key, app_secret),
            'CN': CNAdapterKIS(db, app_key, app_secret),
            'HK': HKAdapterKIS(db, app_key, app_secret),
            'JP': JPAdapterKIS(db, app_key, app_secret),
            'VN': VNAdapterKIS(db, app_key, app_secret),
        }

        # Global rate limiter: 20 req/sec, 1,000 req/min
        self.rate_limiter = RateLimiter(
            requests_per_second=20,
            requests_per_minute=1000
        )

    def collect_all_regions(self, days=250):
        """Collect OHLCV data for all regions sequentially"""
        results = {}

        for region, adapter in self.adapters.items():
            logger.info(f"🌍 Collecting {region} data...")

            try:
                # Rate limit: wait if needed
                self.rate_limiter.acquire()

                # Collect data
                count = adapter.collect_stock_ohlcv(days=days)
                results[region] = {'success': True, 'count': count}

                logger.info(f"✅ {region}: {count} stocks collected")

            except Exception as e:
                logger.error(f"❌ {region} collection failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results
```

#### Fallback: Legacy APIs
**Use Case**: KIS API outage or rate limiting

```python
class AdapterFactory:
    """
    Factory pattern for adapter selection with fallback logic
    """

    @staticmethod
    def get_adapter(region: str, prefer_kis: bool = True):
        """
        Get adapter for region with KIS preference

        Fallback Chain:
        - KIS API (if prefer_kis=True)
        - Legacy API (Polygon.io, AkShare, yfinance)
        - Raise exception if all fail
        """

        if prefer_kis:
            try:
                # Try KIS API first
                if region == 'KR':
                    return KoreaAdapter(db, app_key, app_secret)
                elif region == 'US':
                    return USAdapterKIS(db, app_key, app_secret)
                elif region == 'CN':
                    return CNAdapterKIS(db, app_key, app_secret)
                elif region == 'HK':
                    return HKAdapterKIS(db, app_key, app_secret)
                elif region == 'JP':
                    return JPAdapterKIS(db, app_key, app_secret)
                elif region == 'VN':
                    return VNAdapterKIS(db, app_key, app_secret)
            except Exception as e:
                logger.warning(f"KIS API unavailable for {region}: {e}, falling back to legacy API")

        # Fallback to legacy APIs
        if region == 'US':
            return USAdapter(db, api_key=polygon_api_key)
        elif region == 'CN':
            return CNAdapter(db)
        elif region == 'HK':
            return HKAdapter(db)
        elif region == 'JP':
            return JPAdapter(db)
        elif region == 'VN':
            return VNAdapter(db)
        else:
            raise ValueError(f"Unsupported region: {region}")
```

### Market Hours Coordination

```python
class MarketHoursCoordinator:
    """
    Coordinate data collection across different market hours
    """

    MARKET_HOURS = {
        'KR': {'open': '09:00', 'close': '15:30', 'timezone': 'Asia/Seoul'},
        'US': {'open': '09:30', 'close': '16:00', 'timezone': 'America/New_York'},
        'CN': {'open': '09:30', 'close': '15:00', 'timezone': 'Asia/Shanghai', 'lunch': True},
        'HK': {'open': '09:30', 'close': '16:00', 'timezone': 'Asia/Hong_Kong', 'lunch': True},
        'JP': {'open': '09:00', 'close': '15:00', 'timezone': 'Asia/Tokyo', 'lunch': True},
        'VN': {'open': '09:00', 'close': '15:00', 'timezone': 'Asia/Ho_Chi_Minh', 'lunch': True},
    }

    def get_active_markets(self) -> List[str]:
        """Return list of currently open markets"""
        active = []

        for region, hours in self.MARKET_HOURS.items():
            if self.is_market_open(region):
                active.append(region)

        return active

    def schedule_collection(self):
        """
        Schedule data collection based on market hours

        Collection Strategy:
        - KR: 15:30-16:00 KST (after market close)
        - US: 16:00-17:00 EST (after market close)
        - CN/HK: 16:00-17:00 HKT (after market close)
        - JP: 15:00-16:00 JST (after market close)
        - VN: 15:00-16:00 ICT (after market close)
        """
        pass
```

---

## Monitoring & Observability

### Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
api_requests_total = Counter('api_requests_total', 'Total API requests', ['region', 'adapter', 'status'])
data_collection_duration = Histogram('data_collection_duration_seconds', 'Data collection duration', ['region'])
ohlcv_rows_total = Gauge('ohlcv_rows_total', 'Total OHLCV rows', ['region'])
null_regions_total = Gauge('null_regions_total', 'Total NULL regions')

# Track metrics
@track_metrics
def collect_region_data(region: str, adapter):
    start_time = time.time()

    try:
        count = adapter.collect_stock_ohlcv()
        api_requests_total.labels(region=region, adapter=adapter.__class__.__name__, status='success').inc()
        ohlcv_rows_total.labels(region=region).set(count)

    except Exception as e:
        api_requests_total.labels(region=region, adapter=adapter.__class__.__name__, status='failure').inc()
        raise

    finally:
        duration = time.time() - start_time
        data_collection_duration.labels(region=region).observe(duration)
```

### Grafana Dashboards

#### Dashboard 1: Multi-Region Overview
```
┌────────────────────────────────────────────────────────────┐
│              Multi-Region Trading Dashboard                │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Region Status:                                            │
│  ┌──────┬─────────┬────────────┬─────────────────┐        │
│  │Region│ Status  │ Rows       │ Last Update     │        │
│  ├──────┼─────────┼────────────┼─────────────────┤        │
│  │ KR   │ 🟢 LIVE │ 691,854    │ 2 mins ago      │        │
│  │ US   │ 🟡 TEST │ 7,500      │ 5 mins ago      │        │
│  │ CN   │ ⚪ OFF  │ 0          │ N/A             │        │
│  │ HK   │ ⚪ OFF  │ 0          │ N/A             │        │
│  │ JP   │ ⚪ OFF  │ 0          │ N/A             │        │
│  │ VN   │ ⚪ OFF  │ 0          │ N/A             │        │
│  └──────┴─────────┴────────────┴─────────────────┘        │
│                                                            │
│  Data Quality:                                             │
│  - NULL Regions: 0 (0.00%) ✅                              │
│  - Data Integrity: 100% ✅                                 │
│  - Cross-Region Contamination: 0 ✅                        │
│                                                            │
│  API Performance:                                          │
│  - KIS API Success Rate: 99.8%                             │
│  - Average Response Time: 250ms                            │
│  - Rate Limit Usage: 65% (13/20 req/sec)                   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

#### Dashboard 2: Per-Region Metrics
```
Region: KR (Korea)
┌────────────────────────────────────────────────────────────┐
│  Ticker Count: 2,758                                       │
│  OHLCV Rows: 691,854                                       │
│  Data Coverage: 99.2% (250 days)                           │
│  Last Update: 2 mins ago                                   │
│                                                            │
│  Technical Indicators Completeness:                        │
│  - MA5/20/60/120/200: 97.64%                              │
│  - RSI: 98.83%                                            │
│  - MACD: 96.45%                                           │
│  - Bollinger Bands: 97.12%                                │
│  - ATR: 95.88%                                            │
│                                                            │
│  Collection Performance:                                   │
│  - Average Collection Time: 3.5 minutes                    │
│  - Success Rate: 99.6%                                    │
│  - Failed Tickers: 11 (0.4%)                              │
└────────────────────────────────────────────────────────────┘
```

### Alert Rules

```yaml
# Prometheus Alert Rules
groups:
  - name: multi_region_alerts
    interval: 1m
    rules:
      # Data Quality Alerts
      - alert: NullRegionsDetected
        expr: null_regions_total > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "NULL regions detected in database"
          description: "{{ $value }} rows have NULL region values"

      - alert: DataCollectionFailure
        expr: rate(api_requests_total{status="failure"}[5m]) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High failure rate for {{ $labels.region }}"
          description: "API failure rate > 10% for region {{ $labels.region }}"

      # Performance Alerts
      - alert: SlowDataCollection
        expr: data_collection_duration_seconds > 600
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow data collection for {{ $labels.region }}"
          description: "Collection taking > 10 minutes for region {{ $labels.region }}"

      # Capacity Alerts
      - alert: DatabaseSizeGrowth
        expr: database_size_bytes > 10737418240  # 10GB
        labels:
          severity: info
        annotations:
          summary: "Database size exceeding 10GB"
          description: "Database size: {{ humanize $value }}"
```

---

## Security & Compliance

### API Key Management

```python
# .env file (NOT committed to git)
KIS_APP_KEY=your_kis_app_key_here
KIS_APP_SECRET=your_kis_app_secret_here
POLYGON_API_KEY=your_polygon_api_key_here  # Backup

# Secure loading
from dotenv import load_dotenv

load_dotenv()
app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')

# Validate presence
if not app_key or not app_secret:
    raise ValueError("KIS API credentials not found in .env file")
```

### Data Privacy & Compliance
- **GDPR**: No personal data stored (only market data)
- **Korea**: Comply with FSS (Financial Supervisory Service) regulations
- **US**: SEC data usage compliance
- **China**: CSRC data usage regulations

### Rate Limiting Compliance
- **KIS API**: 20 req/sec, 1,000 req/min (enforced by exponential backoff)
- **Polygon.io**: 5 req/min (strict adherence to free tier limits)
- **AkShare**: 1.5 req/sec (self-imposed, no official limit)
- **yfinance**: 1.0 req/sec (self-imposed, no official limit)

---

## Risk Mitigation

### Risk Matrix

| Risk | Probability | Impact | Mitigation Strategy | Rollback Plan |
|------|-------------|--------|---------------------|---------------|
| **Data Contamination** | Low | Critical | UNIQUE constraint (ticker, region, date) + validation | DELETE WHERE region='XX' |
| **API Outage (KIS)** | Medium | High | Fallback to legacy APIs (Polygon, yfinance) | Auto-switch to backup API |
| **Database Corruption** | Low | Critical | Daily backups + WAL mode | Restore from backup |
| **Rate Limit Exceeded** | Medium | Medium | Exponential backoff + queue management | Pause + resume after cooldown |
| **Cross-Region Query Performance** | Medium | Medium | Indexed region column + query optimization | Add composite indexes |
| **Disk Space Exhaustion** | Low | High | Monitor disk usage + auto-cleanup | Delete old OHLCV data (retain 250 days) |

### Disaster Recovery Plan

```bash
#!/bin/bash
# Daily backup script

DATE=$(date +%Y%m%d)
BACKUP_DIR="/Users/13ruce/spock/data/backups"
DB_FILE="/Users/13ruce/spock/data/spock_local.db"

# Create backup
sqlite3 $DB_FILE ".backup $BACKUP_DIR/spock_backup_$DATE.db"

# Verify backup
sqlite3 $BACKUP_DIR/spock_backup_$DATE.db "PRAGMA integrity_check;"

# Compress backup
gzip $BACKUP_DIR/spock_backup_$DATE.db

# Cleanup old backups (retain 7 days)
find $BACKUP_DIR -name "spock_backup_*.db.gz" -mtime +7 -delete

echo "✅ Backup complete: spock_backup_$DATE.db.gz"
```

### Rollback Procedures

**Region-Specific Rollback**:
```sql
-- Rollback US deployment
DELETE FROM ohlcv_data WHERE region = 'US';
VACUUM;

-- Verify rollback
SELECT COUNT(*) FROM ohlcv_data WHERE region = 'US';  -- Should be 0
```

**Full Database Rollback**:
```bash
# Restore from backup
cp data/backups/spock_backup_20251015.db.gz data/
gunzip data/spock_backup_20251015.db.gz
mv data/spock_backup_20251015.db data/spock_local.db

# Verify integrity
sqlite3 data/spock_local.db "PRAGMA integrity_check;"
```

---

## Implementation Roadmap

### Week 1: Foundation
- [x] Database region migration (COMPLETE)
- [ ] Install Prometheus + Grafana
- [ ] Setup alert rules
- [ ] Baseline KR performance metrics

### Week 2-3: US Deployment
- [ ] Day 1: Test collection (10 tickers)
- [ ] Day 2: Multi-region validation
- [ ] Day 3-5: Full US deployment (3,000 tickers)
- [ ] Day 6-7: Integration testing

### Week 4: CN Deployment
- [ ] Day 1: Test collection (10 tickers)
- [ ] Day 2-4: Full CN deployment (1,500 tickers)
- [ ] Day 5: Validation

### Week 5: HK Deployment
- [ ] Day 1: Test collection (10 tickers)
- [ ] Day 2-4: Full HK deployment (800 tickers)
- [ ] Day 5: Validation

### Week 6: JP Deployment
- [ ] Day 1: Test collection (10 tickers)
- [ ] Day 2-4: Full JP deployment (700 tickers)
- [ ] Day 5: Validation

### Week 7: VN Deployment
- [ ] Day 1: Test collection (10 tickers)
- [ ] Day 2-3: Full VN deployment (150 tickers)
- [ ] Day 4-5: Final validation

### Week 8: Optimization
- [ ] Database optimization (indexes, VACUUM)
- [ ] Caching strategy implementation
- [ ] Operational procedures documentation
- [ ] Production readiness review

---

## Performance Benchmarks

### Target Metrics

| Metric | Target | Current (KR only) | Multi-Region |
|--------|--------|-------------------|--------------|
| **Query Latency** | <500ms | ~200ms | <500ms (projected) |
| **Data Collection Time** | <10 min/region | ~3.5 min (KR) | ~60 min (6 regions) |
| **Database Size** | <5GB | ~1.2GB | ~3.9GB (projected) |
| **API Success Rate** | >99% | 99.6% (KR) | >99% (target) |
| **NULL Regions** | 0 | 0 | 0 (enforced) |
| **Uptime** | 99.9% | 99.8% (KR) | 99.9% (target) |

### Scalability Projections

| Scenario | Tickers | Regions | Rows | Size | Query Time |
|----------|---------|---------|------|------|------------|
| **Current** | 2,758 | 1 | 691,854 | 1.2GB | ~200ms |
| **Phase 2** (US) | 5,758 | 2 | 1,441,854 | 2.5GB | ~300ms |
| **Phase 3** (CN/HK/JP) | 8,758 | 5 | 2,191,854 | 3.8GB | ~400ms |
| **Phase 4** (VN) | 8,908 | 6 | 2,227,000 | 3.9GB | ~450ms |
| **1 Year** | 10,000 | 6 | 2,500,000 | 4.3GB | ~500ms |

---

## Conclusion

### Design Summary
This multi-region deployment design provides a comprehensive roadmap for scaling the Spock Trading System from a single-region (KR) platform to a global multi-region trading system supporting 6 markets (KR, US, CN, HK, JP, VN).

### Key Advantages
1. ✅ **Unified Architecture**: Single database with region isolation
2. ✅ **Automatic Region Injection**: No manual region passing required
3. ✅ **Progressive Rollout**: Phased deployment with validation gates
4. ✅ **API Flexibility**: KIS API primary with legacy fallbacks
5. ✅ **Production Ready**: Built on successful migration (691,854 rows, 0 NULL regions)

### Next Steps
1. **Immediate** (Week 1): Install monitoring infrastructure (Prometheus + Grafana)
2. **Short-term** (Week 2-3): Deploy US market with full validation
3. **Medium-term** (Week 4-7): Deploy Asia markets (CN, HK, JP, VN)
4. **Long-term** (Week 8+): Production optimization and advanced features

### Final Recommendation
**Proceed with phased deployment starting with US market (Week 2-3) using KIS API as primary data source.**

---

**Design Document Version**: 1.0
**Date**: 2025-10-15
**Status**: Ready for Implementation Review
**Next Review**: After Phase 2 (US Deployment)
