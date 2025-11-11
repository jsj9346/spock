# Stock Screening MCP Tool - Design Specification

**Version**: 1.0.0
**Date**: 2025-10-31
**Status**: Design Complete
**Author**: Spock Quant Platform Team

---

## 📋 Executive Summary

백테스트 기능 없이 펀더멘털 및 기술적 지표를 기반으로 종목을 스크리닝하는 MCP 도구 설계. 즉시 사용 가능한 실용적 기능을 제공하며, 점진적 확장 가능한 아키텍처를 채택합니다.

**핵심 가치**:
- ✅ **즉시 사용 가능**: Backtest 없이 독립적 동작
- ✅ **실용성**: 실제 투자 의사결정에 직접 활용
- ✅ **확장성**: 필터 종류를 쉽게 추가 가능
- ✅ **성능**: <5s 전체 시장 스크리닝

---

## 🎯 Use Cases

### Primary Use Cases

#### 1. 저평가 우량주 발굴
```json
{
  "region": "KR",
  "filters": {
    "fundamental": {
      "per": {"max": 10},
      "pbr": {"max": 1.0},
      "dividend_yield": {"min": 3.0}
    }
  },
  "ranking": {"by": "dividend_yield", "order": "desc"},
  "limit": 20
}
```
**결과**: P/E < 10, P/B < 1.0, 배당수익률 > 3% 종목 중 배당수익률 상위 20개

#### 2. 과매도 종목 발굴 (기술적)
```json
{
  "region": "KR",
  "filters": {
    "technical": {
      "rsi_14": {"max": 30},
      "volume_surge": {"threshold": 1.5, "period": 5}
    }
  },
  "ranking": {"by": "rsi_14", "order": "asc"},
  "limit": 30
}
```
**결과**: RSI < 30이고 최근 5일 거래량 1.5배 이상 급증한 종목 중 RSI 낮은 순 30개

#### 3. 고배당 대형주
```json
{
  "region": "KR",
  "filters": {
    "fundamental": {
      "market_cap": {"min": 1000000000000},
      "dividend_yield": {"min": 5.0}
    }
  },
  "ranking": {"by": "market_cap", "order": "desc"},
  "limit": 10
}
```
**결과**: 시가총액 1조 이상, 배당수익률 5% 이상 종목 중 시가총액 상위 10개

#### 4. 섹터별 밸류에이션 비교
```json
{
  "region": "KR",
  "filters": {
    "fundamental": {
      "sector": "IT",
      "per": {"min": 5, "max": 20}
    }
  },
  "ranking": {"by": "per", "order": "asc"},
  "limit": 50
}
```
**결과**: IT 섹터에서 P/E 5~20 구간 종목을 P/E 낮은 순으로 50개

---

## 🏗️ System Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code MCP                         │
│                   (User Interface)                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   MCP Tool: screen_stocks                    │
│  - Input validation                                          │
│  - Tool definition                                           │
│  - Output formatting                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   ScreeningAdapter                           │
│  - Filter orchestration                                      │
│  - Data provider coordination                                │
│  - Result ranking & pagination                               │
│  - Cache management                                          │
└───────────┬───────────────────────────┬─────────────────────┘
            │                           │
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────────────┐
│  FundamentalFilter    │   │  TechnicalFilter              │
│  - P/E, P/B, ROE      │   │  - RSI, MA, Volume            │
│  - Market Cap         │   │  - Price Change               │
│  - Dividend Yield     │   │  - MA Crossover               │
│  - EV/EBITDA          │   │  - Momentum                   │
│  - Sector/Industry    │   │                               │
└───────────┬───────────┘   └───────────┬───────────────────┘
            │                           │
            ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer                         │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │ PostgresDataProvider │  │ TechnicalCalculator      │    │
│  │ - OHLCV queries      │  │ - RSI calculation        │    │
│  │ - Fundamentals       │  │ - MA calculation         │    │
│  └──────────────────────┘  │ - Volume analysis        │    │
│                             └──────────────────────────┘    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│            PostgreSQL + TimescaleDB                          │
│  - ticker_fundamentals (P/E, P/B, dividend_yield, etc.)     │
│  - ohlcv_data (price, volume for technical indicators)      │
│  - stock_details (sector, industry)                         │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. MCP Tool Layer (`screen_stocks`)
**Responsibility**: MCP protocol integration
- Input validation and type checking
- Tool definition with JSONSchema
- Result formatting for MCP response
- Error handling and logging

#### 2. ScreeningAdapter
**Responsibility**: Business logic orchestration
- Parse and validate filter criteria
- Coordinate fundamental and technical filters
- Apply ranking and pagination
- Cache frequently used screens
- Performance optimization

#### 3. Filter System

**FundamentalFilter**:
- SQL-based filtering (efficient)
- Direct database queries
- Supports: P/E, P/B, dividend yield, market cap, EV/EBITDA, sector, industry

**TechnicalFilter**:
- Calculation-based filtering (heavier)
- OHLCV data retrieval → indicator calculation → filter
- Supports: RSI, MA, volume analysis, price momentum

**CompositeFilter**:
- Combines multiple filters with AND/OR logic
- Filter chain execution
- Early termination optimization

#### 4. Data Access Layer

**PostgresDataProvider** (existing):
- OHLCV data queries
- Batch optimization

**FundamentalDataProvider** (new):
- ticker_fundamentals queries
- JOIN with stock_details for sector/industry
- Efficient indexing

**TechnicalCalculator** (new or reuse existing):
- RSI calculation using pandas-ta
- Moving average calculation
- Volume analysis (avg, surge detection)
- Price momentum (% change over N days)

---

## 📡 API Design

### MCP Tool Definition

```python
Tool(
    name="screen_stocks",
    description="Screen stocks based on fundamental and technical criteria",
    inputSchema={
        "type": "object",
        "properties": {
            "region": {
                "type": "string",
                "enum": ["KR", "US"],
                "description": "Market region"
            },
            "filters": {
                "type": "object",
                "properties": {
                    "fundamental": {
                        "type": "object",
                        "properties": {
                            "per": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "pbr": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "dividend_yield": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "market_cap": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "ev_ebitda": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "sector": {"type": "string"},
                            "industry": {"type": "string"}
                        }
                    },
                    "technical": {
                        "type": "object",
                        "properties": {
                            "rsi_14": {"type": "object", "properties": {"min": {"type": "number"}, "max": {"type": "number"}}},
                            "ma_cross": {
                                "type": "object",
                                "properties": {
                                    "short": {"type": "number"},
                                    "long": {"type": "number"},
                                    "direction": {"type": "string", "enum": ["golden", "death"]}
                                }
                            },
                            "volume_surge": {
                                "type": "object",
                                "properties": {
                                    "threshold": {"type": "number"},
                                    "period": {"type": "number"}
                                }
                            },
                            "price_change": {
                                "type": "object",
                                "properties": {
                                    "period": {"type": "number"},
                                    "min": {"type": "number"},
                                    "max": {"type": "number"}
                                }
                            }
                        }
                    }
                }
            },
            "ranking": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "enum": ["per", "pbr", "dividend_yield", "market_cap", "ev_ebitda", "rsi_14", "volume", "price_change"]
                    },
                    "order": {"type": "string", "enum": ["asc", "desc"]}
                }
            },
            "limit": {"type": "number", "default": 50, "maximum": 500},
            "offset": {"type": "number", "default": 0}
        },
        "required": ["region"]
    }
)
```

### Response Format

```json
{
  "success": true,
  "stocks": [
    {
      "ticker": "005930",
      "name": "삼성전자",
      "fundamentals": {
        "per": 12.5,
        "pbr": 1.2,
        "dividend_yield": 2.8,
        "market_cap": 400000000000000,
        "ev_ebitda": 8.5
      },
      "technicals": {
        "rsi_14": 45.2,
        "ma_20": 58000,
        "ma_60": 57500,
        "volume_avg_20d": 25000000,
        "price_change_30d": 3.5
      },
      "details": {
        "sector": "전기전자",
        "industry": "반도체"
      },
      "rank": 1,
      "score": 85.3
    }
  ],
  "metadata": {
    "total_matches": 147,
    "filters_applied": {
      "fundamental": {"per": {"max": 15}, "dividend_yield": {"min": 2.0}},
      "technical": {"rsi_14": {"min": 30, "max": 70}}
    },
    "ranking": {"by": "dividend_yield", "order": "desc"},
    "execution_time_ms": 1250,
    "page": {"limit": 50, "offset": 0}
  }
}
```

---

## 🗄️ Database Schema Usage

### Existing Tables

#### ticker_fundamentals (Primary Source)
```sql
SELECT
    ticker,
    region,
    per,              -- P/E ratio
    pbr,              -- P/B ratio
    dividend_yield,   -- Dividend yield (%)
    market_cap,       -- Market capitalization
    ev_ebitda,        -- EV/EBITDA ratio
    date              -- Data date
FROM ticker_fundamentals
WHERE region = 'KR'
  AND date = (SELECT MAX(date) FROM ticker_fundamentals WHERE region = 'KR')
  AND per BETWEEN 5 AND 15
  AND dividend_yield > 3.0
ORDER BY dividend_yield DESC
LIMIT 50;
```

#### stock_details (Sector/Industry)
```sql
SELECT
    t.ticker,
    t.per,
    t.dividend_yield,
    s.sector,
    s.industry
FROM ticker_fundamentals t
JOIN stock_details s ON t.ticker = s.ticker AND t.region = s.region
WHERE t.region = 'KR'
  AND t.date = (SELECT MAX(date) FROM ticker_fundamentals WHERE region = 'KR')
  AND s.sector = 'IT'
  AND t.per < 20;
```

#### ohlcv_data (Technical Indicators)
```sql
-- Get latest 60 days for MA calculation
SELECT
    ticker,
    date,
    close,
    volume
FROM ohlcv_data
WHERE region = 'KR'
  AND ticker = '005930'
  AND date >= CURRENT_DATE - INTERVAL '60 days'
ORDER BY date DESC;
```

### Required Indexes

```sql
-- Fundamental filtering (critical for performance)
CREATE INDEX idx_ticker_fundamentals_screening
ON ticker_fundamentals(region, date, per, pbr, dividend_yield, market_cap);

-- Sector/Industry filtering
CREATE INDEX idx_stock_details_sector_industry
ON stock_details(region, sector, industry);

-- Technical data (already exists via TimescaleDB hypertable)
-- No additional index needed for ohlcv_data
```

---

## 🔧 Implementation Plan

### Phase 1: MVP - Fundamental Screening Only (Week 1)
**Estimated Effort**: 2 days

**Deliverables**:
1. ✅ ScreeningAdapter基础结构
2. ✅ FundamentalFilter implementation
3. ✅ MCP tool registration
4. ✅ Basic unit tests

**Features**:
- P/E, P/B, dividend yield, market cap filtering
- Sector/industry filtering
- Simple ranking (by one metric)
- Pagination support

**Success Criteria**:
- ✅ Screen 3,000+ KR stocks in <3s
- ✅ Accurate filtering results
- ✅ All unit tests passing

### Phase 2: Technical Indicators (Week 2)
**Estimated Effort**: 2 days

**Deliverables**:
1. ✅ TechnicalCalculator implementation
2. ✅ RSI, MA calculation
3. ✅ Volume analysis
4. ✅ Integration tests

**Features**:
- RSI (14-period) filtering
- Moving average crossover detection
- Volume surge detection
- Price momentum filtering

**Success Criteria**:
- ✅ Technical calculations accurate (validated against reference)
- ✅ Screen with technical filters in <10s
- ✅ Combined fundamental + technical filters working

### Phase 3: Advanced Features (Week 3)
**Estimated Effort**: 2 days

**Deliverables**:
1. ✅ Composite scoring system
2. ✅ Multi-metric ranking
3. ✅ Cache optimization
4. ✅ Performance benchmarks

**Features**:
- Combined score based on multiple metrics
- Custom weight assignment
- Advanced ranking algorithms
- Result caching (daily refresh)

**Success Criteria**:
- ✅ Composite scoring working correctly
- ✅ Cache hit rate >80%
- ✅ Performance <5s for complex screens

---

## 🚀 Performance Optimization

### Query Optimization

#### Strategy 1: Push-Down Filtering
```python
# Bad: Fetch all, filter in Python
all_stocks = fetch_all_fundamentals()
filtered = [s for s in all_stocks if s.per < 10]  # Slow!

# Good: Filter in SQL
filtered = fetch_fundamentals(where="per < 10")  # Fast!
```

#### Strategy 2: Batch Technical Calculations
```python
# Bad: Calculate indicators one by one
for ticker in tickers:
    rsi = calculate_rsi(ticker)  # 3000 DB queries!

# Good: Batch fetch and vectorized calculation
ohlcv_data = fetch_ohlcv_batch(tickers)
rsi_values = calculate_rsi_batch(ohlcv_data)  # 1 DB query, vectorized
```

#### Strategy 3: Caching Strategy
```python
# Cache levels:
# L1: In-memory cache (60s TTL) - for repeated screens
# L2: Daily cache (24h TTL) - for fundamental data
# L3: Hourly cache (1h TTL) - for technical indicators

cache_key = f"screen:{region}:{hash(filters)}"
if cache.exists(cache_key) and cache.ttl(cache_key) > 0:
    return cache.get(cache_key)

result = perform_screening(filters)
cache.set(cache_key, result, ttl=3600)
return result
```

### Performance Targets

| Operation | Target | Optimization |
|-----------|--------|--------------|
| Fundamental screen (all KR) | <3s | SQL WHERE pushdown, indexed queries |
| Technical screen (50 tickers) | <5s | Batch OHLCV fetch, vectorized calculation |
| Combined screen | <8s | Parallel fundamental + technical |
| Cache hit | <100ms | In-memory cache, pre-computed results |

---

## 🧪 Testing Strategy

### Unit Tests

#### FundamentalFilter
```python
def test_fundamental_filter_per():
    """Test P/E ratio filtering."""
    filter = FundamentalFilter(per={"max": 10})
    result = filter.apply(region="KR")

    assert all(stock.per <= 10 for stock in result)
    assert len(result) > 0

def test_fundamental_filter_combined():
    """Test multiple fundamental filters."""
    filter = FundamentalFilter(
        per={"max": 15},
        dividend_yield={"min": 3.0},
        market_cap={"min": 1000000000000}
    )
    result = filter.apply(region="KR")

    assert all(
        stock.per <= 15 and
        stock.dividend_yield >= 3.0 and
        stock.market_cap >= 1000000000000
        for stock in result
    )
```

#### TechnicalFilter
```python
def test_technical_rsi():
    """Test RSI calculation and filtering."""
    calculator = TechnicalCalculator()
    rsi = calculator.calculate_rsi("005930", period=14)

    assert 0 <= rsi <= 100

def test_technical_ma_cross():
    """Test moving average crossover detection."""
    calculator = TechnicalCalculator()
    is_golden = calculator.detect_ma_cross(
        "005930", short=20, long=60, direction="golden"
    )

    assert isinstance(is_golden, bool)
```

### Integration Tests

```python
def test_screening_end_to_end():
    """Test complete screening workflow."""
    adapter = ScreeningAdapter()
    result = await adapter.screen_stocks(
        region="KR",
        filters={
            "fundamental": {"per": {"max": 15}},
            "technical": {"rsi_14": {"max": 30}}
        },
        ranking={"by": "dividend_yield", "order": "desc"},
        limit=20
    )

    assert result["success"] == True
    assert len(result["stocks"]) <= 20
    assert result["metadata"]["execution_time_ms"] < 10000
```

### Performance Tests

```python
def test_performance_benchmark():
    """Benchmark screening performance."""
    adapter = ScreeningAdapter()

    start = time.time()
    result = await adapter.screen_stocks(
        region="KR",
        filters={"fundamental": {"per": {"max": 20}}},
        limit=100
    )
    duration = time.time() - start

    assert duration < 3.0  # Must complete in <3s
    assert len(result["stocks"]) > 0
```

---

## ⚠️ Risk Mitigation

### Risk 1: Data Quality Issues

**Problem**: ticker_fundamentals에 NULL 값이나 오래된 데이터
**Impact**: 부정확한 스크리닝 결과
**Mitigation**:
1. NULL 값 처리 로직 (default 값 또는 제외)
2. 데이터 업데이트 날짜 확인 (최신 30일 이내)
3. 데이터 품질 모니터링 대시보드

```python
# Validation logic
def validate_fundamentals(data):
    if data.per is None or data.per < 0:
        logger.warning(f"Invalid PER for {data.ticker}: {data.per}")
        return False

    if (datetime.now().date() - data.date).days > 30:
        logger.warning(f"Stale data for {data.ticker}: {data.date}")
        return False

    return True
```

### Risk 2: Performance Degradation

**Problem**: 기술적 지표 계산이 느려서 timeout
**Impact**: 사용자 경험 저하, MCP timeout
**Mitigation**:
1. 배치 처리 및 병렬 계산
2. 점진적 로딩 (먼저 fundamental, 그 다음 technical)
3. 계산 결과 캐싱 (1시간 TTL)

```python
# Progressive loading
async def screen_with_progress(filters):
    # Step 1: Fast fundamental filtering
    candidates = await filter_fundamental(filters)
    yield {"phase": "fundamental", "count": len(candidates)}

    # Step 2: Slower technical filtering
    if "technical" in filters:
        results = await filter_technical(candidates, filters)
        yield {"phase": "technical", "count": len(results)}
    else:
        results = candidates

    # Step 3: Ranking
    ranked = rank_results(results, filters.get("ranking"))
    yield {"phase": "complete", "results": ranked}
```

### Risk 3: Feature Creep

**Problem**: 필터 종류가 계속 증가하여 유지보수 어려움
**Impact**: 코드 복잡도 증가, 버그 증가
**Mitigation**:
1. Filter Factory Pattern 사용
2. 플러그인 아키텍처 (새 필터 추가 용이)
3. 철저한 단위 테스트 커버리지 (>90%)

```python
# Plugin architecture
class FilterRegistry:
    _filters = {}

    @classmethod
    def register(cls, name, filter_class):
        cls._filters[name] = filter_class

    @classmethod
    def create(cls, name, **kwargs):
        if name not in cls._filters:
            raise ValueError(f"Unknown filter: {name}")
        return cls._filters[name](**kwargs)

# Register filters
FilterRegistry.register("per", PERFilter)
FilterRegistry.register("rsi", RSIFilter)

# Easy to add new filters
FilterRegistry.register("quick_ratio", QuickRatioFilter)
```

---

## 📚 Code Examples

### Example 1: Simple Screening Adapter

```python
# mcp_server/adapters/screening_adapter.py
class ScreeningAdapter:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.db_manager = PostgresDatabaseManager(...)
        self.fundamental_filter = FundamentalFilter(self.db_manager)
        self.technical_calculator = TechnicalCalculator()
        self._cache = {}

    async def screen_stocks(
        self,
        region: str,
        filters: Dict[str, Any],
        ranking: Optional[Dict[str, str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Screen stocks based on filters."""
        start_time = time.time()

        # Step 1: Fundamental filtering (fast, SQL-based)
        candidates = []
        if "fundamental" in filters:
            candidates = await self.fundamental_filter.apply(
                region=region,
                criteria=filters["fundamental"]
            )
        else:
            # No fundamental filter, get all tickers
            candidates = await self._get_all_tickers(region)

        logger.info(f"Fundamental filter: {len(candidates)} candidates")

        # Step 2: Technical filtering (slower, calculation-based)
        if "technical" in filters and len(candidates) > 0:
            results = await self._apply_technical_filters(
                candidates, filters["technical"]
            )
        else:
            results = candidates

        logger.info(f"Technical filter: {len(results)} results")

        # Step 3: Ranking
        if ranking:
            results = self._rank_results(results, ranking)

        # Step 4: Pagination
        total = len(results)
        results = results[offset:offset + limit]

        execution_time = (time.time() - start_time) * 1000

        return {
            "success": True,
            "stocks": [self._format_stock(s) for s in results],
            "metadata": {
                "total_matches": total,
                "filters_applied": filters,
                "ranking": ranking,
                "execution_time_ms": execution_time,
                "page": {"limit": limit, "offset": offset}
            }
        }
```

### Example 2: Fundamental Filter

```python
# modules/screening/fundamental_filter.py
class FundamentalFilter:
    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db_manager = db_manager

    async def apply(
        self,
        region: str,
        criteria: Dict[str, Any]
    ) -> List[Stock]:
        """Apply fundamental filters via SQL."""
        # Build WHERE clause
        where_clauses = ["region = %s"]
        params = [region]

        # Add date filter (latest data)
        where_clauses.append(
            "date = (SELECT MAX(date) FROM ticker_fundamentals WHERE region = %s)"
        )
        params.append(region)

        # Add range filters
        if "per" in criteria:
            if "min" in criteria["per"]:
                where_clauses.append("per >= %s")
                params.append(criteria["per"]["min"])
            if "max" in criteria["per"]:
                where_clauses.append("per <= %s")
                params.append(criteria["per"]["max"])

        if "dividend_yield" in criteria:
            if "min" in criteria["dividend_yield"]:
                where_clauses.append("dividend_yield >= %s")
                params.append(criteria["dividend_yield"]["min"])

        # ... similar for other metrics

        # Build query
        query = f"""
            SELECT
                t.ticker,
                t.per,
                t.pbr,
                t.dividend_yield,
                t.market_cap,
                t.ev_ebitda,
                tk.name,
                sd.sector,
                sd.industry
            FROM ticker_fundamentals t
            JOIN tickers tk ON t.ticker = tk.ticker AND t.region = tk.region
            LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE {" AND ".join(where_clauses)}
        """

        # Execute query
        with self.db_manager._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [
                    Stock(
                        ticker=row[0],
                        per=row[1],
                        pbr=row[2],
                        dividend_yield=row[3],
                        market_cap=row[4],
                        ev_ebitda=row[5],
                        name=row[6],
                        sector=row[7],
                        industry=row[8]
                    )
                    for row in rows
                ]
```

### Example 3: Technical Calculator

```python
# modules/screening/technical_calculator.py
import pandas as pd
import pandas_ta as ta

class TechnicalCalculator:
    def __init__(self, data_provider: PostgresDataProvider):
        self.data_provider = data_provider

    async def calculate_rsi(
        self,
        ticker: str,
        region: str,
        period: int = 14
    ) -> float:
        """Calculate RSI for a ticker."""
        # Get OHLCV data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period * 3)  # Buffer

        df = self.data_provider.get_ohlcv(
            ticker=ticker,
            region=region,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty or len(df) < period:
            return None

        # Calculate RSI using pandas-ta
        df.ta.rsi(length=period, append=True)

        # Get latest RSI
        rsi = df[f'RSI_{period}'].iloc[-1]

        return rsi

    async def calculate_ma_cross(
        self,
        ticker: str,
        region: str,
        short: int = 20,
        long: int = 60
    ) -> str:
        """Detect moving average crossover."""
        # Get OHLCV data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=long * 2)

        df = self.data_provider.get_ohlcv(
            ticker=ticker,
            region=region,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty or len(df) < long:
            return None

        # Calculate moving averages
        df[f'MA_{short}'] = df['close'].rolling(window=short).mean()
        df[f'MA_{long}'] = df['close'].rolling(window=long).mean()

        # Detect crossover
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if prev[f'MA_{short}'] <= prev[f'MA_{long}'] and latest[f'MA_{short}'] > latest[f'MA_{long}']:
            return "golden"
        elif prev[f'MA_{short}'] >= prev[f'MA_{long}'] and latest[f'MA_{short}'] < latest[f'MA_{long}']:
            return "death"
        else:
            return None
```

---

## 📊 Success Metrics

### Performance Metrics
- ✅ Fundamental screen (<3s for full KR market)
- ✅ Technical screen (<10s for 50 tickers)
- ✅ Combined screen (<8s)
- ✅ Cache hit rate (>80%)

### Quality Metrics
- ✅ Test coverage (>90%)
- ✅ Accuracy (100% vs manual validation)
- ✅ Error rate (<0.1%)

### User Metrics
- ✅ Tool usage frequency
- ✅ Most popular filter combinations
- ✅ User satisfaction (feedback)

---

## 🎯 Next Steps

### Immediate (Week 1)
1. 🔲 Create ScreeningAdapter skeleton
2. 🔲 Implement FundamentalFilter (P/E, P/B, dividend)
3. 🔲 Register MCP tool
4. 🔲 Write unit tests
5. 🔲 Test with real data

### Short-term (Week 2)
6. 🔲 Implement TechnicalCalculator (RSI, MA)
7. 🔲 Add volume analysis
8. 🔲 Integration testing
9. 🔲 Performance optimization

### Medium-term (Week 3)
10. 🔲 Advanced ranking algorithms
11. 🔲 Composite scoring system
12. 🔲 Cache optimization
13. 🔲 User documentation

---

## 📚 References

- [MCP Test Report](MCP_TEST_REPORT.md) - Current MCP implementation status
- [PostgreSQL Schema](QUANT_DATABASE_SCHEMA.md) - Database structure
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta) - Technical indicator library
- [QUANT_ROADMAP.md](QUANT_ROADMAP.md) - Project roadmap

---

**Document Status**: ✅ Design Complete
**Ready for Implementation**: Yes
**Estimated Total Effort**: 6 days (3 phases × 2 days)
**Next Action**: Begin Phase 1 - Fundamental Screening MVP
