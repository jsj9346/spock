# ETF Holdings Database Design

**Purpose**: 양방향 ETF-종목 관계 조회를 위한 데이터베이스 설계
**Date**: 2025-10-17
**Status**: Design Specification

---

## 1. Executive Summary

### Business Requirements
- **종목 → ETF 조회**: "삼성전자는 어떤 ETF에 포함되어 있나?"
- **ETF → 종목 조회**: "TIGER 200 ETF는 어떤 종목들로 구성되어 있나?"
- **구성 비중 추적**: 시간에 따른 ETF 구성 변화 추적
- **투자 전략 활용**: ETF 자금 흐름 분석, 섹터 로테이션 파악

### Key Design Decisions
- **Many-to-Many 관계**: 중간 테이블(etf_holdings)을 통한 정규화
- **시계열 데이터**: as_of_date 컬럼으로 구성 변화 추적
- **기존 스키마 확장**: Spock의 tickers 테이블 활용
- **성능 최적화**: 4개의 전략적 인덱스 설계

---

## 2. Database Schema Design

### 2.1 Table: `etfs` (ETF 기본 정보)

**Purpose**: ETF 메타데이터 저장 (tickers 테이블의 ETF 레코드와 1:1 관계)

```sql
CREATE TABLE etfs (
    ticker TEXT PRIMARY KEY,                    -- ETF 티커 (tickers.ticker FK)
    name TEXT NOT NULL,                         -- ETF 이름 (한글)
    name_eng TEXT,                              -- ETF 영문명
    region TEXT NOT NULL,                       -- 시장 지역 (KR, US, CN, HK, JP, VN)
    exchange TEXT,                              -- 거래소 (KOSPI, NYSE, etc.)

    -- ETF 분류
    category TEXT,                              -- ETF 카테고리 (INDEX, SECTOR, THEME, LEVERAGED, INVERSE)
    subcategory TEXT,                           -- 세부 카테고리 (예: IT, 반도체, ESG, etc.)
    tracking_index TEXT,                        -- 추종 지수 (KOSPI 200, S&P 500, etc.)

    -- 재무 정보
    total_assets REAL,                          -- 순자산 (AUM, 원화 기준)
    expense_ratio REAL,                         -- 총보수율 (%)
    listed_shares INTEGER,                      -- 상장 주식 수

    -- 운용사 정보
    issuer TEXT,                                -- 운용사 (삼성자산운용, BlackRock, etc.)
    inception_date TEXT,                        -- 설정일 (YYYY-MM-DD)

    -- 투자 전략
    leverage_ratio REAL,                        -- 레버리지 배수 (1.0=일반, 2.0=2배, etc.)
    is_inverse BOOLEAN DEFAULT 0,               -- 인버스 여부
    currency_hedged BOOLEAN DEFAULT 0,          -- 환헤지 여부

    -- 성과 지표
    tracking_error_20d REAL,                    -- 20일 추적 오차 (%)
    tracking_error_60d REAL,                    -- 60일 추적 오차 (%)
    tracking_error_120d REAL,                   -- 120일 추적 오차 (%)
    tracking_error_250d REAL,                   -- 250일 추적 오차 (%)
    premium_discount REAL,                      -- 괴리율 (시장가 vs NAV, %)

    -- 거래 정보
    avg_daily_volume REAL,                      -- 일평균 거래량 (최근 20일)
    avg_daily_value REAL,                       -- 일평균 거래대금 (최근 20일, 원화)

    -- 메타데이터
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    data_source TEXT,                           -- 데이터 출처 (KIS_API, etfcheck.co.kr, etc.)

    FOREIGN KEY (ticker) REFERENCES tickers(ticker) ON DELETE CASCADE
);

CREATE INDEX idx_etfs_region ON etfs(region);
CREATE INDEX idx_etfs_category ON etfs(category);
CREATE INDEX idx_etfs_issuer ON etfs(issuer);
CREATE INDEX idx_etfs_total_assets ON etfs(total_assets DESC);
```

### 2.2 Table: `etf_holdings` (ETF 구성 종목 관계)

**Purpose**: ETF와 종목 간의 Many-to-Many 관계 + 구성 비중 정보

```sql
CREATE TABLE etf_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 관계 정의
    etf_ticker TEXT NOT NULL,                   -- ETF 티커 (etfs.ticker FK)
    stock_ticker TEXT NOT NULL,                 -- 종목 티커 (tickers.ticker FK)

    -- 구성 정보
    weight REAL NOT NULL,                       -- 구성 비중 (%)
    shares INTEGER,                             -- 보유 주식 수
    market_value REAL,                          -- 시장 가치 (shares × price, 원화)

    -- 순위 및 변화
    rank_in_etf INTEGER,                        -- ETF 내 비중 순위
    weight_change_from_prev REAL,              -- 이전 대비 비중 변화 (percentage points)

    -- 시계열 추적
    as_of_date TEXT NOT NULL,                   -- 기준일 (YYYY-MM-DD)

    -- 메타데이터
    created_at TEXT NOT NULL,
    data_source TEXT,                           -- 데이터 출처

    -- Foreign Keys
    FOREIGN KEY (etf_ticker) REFERENCES etfs(ticker) ON DELETE CASCADE,
    FOREIGN KEY (stock_ticker) REFERENCES tickers(ticker) ON DELETE CASCADE,

    -- Constraints
    UNIQUE(etf_ticker, stock_ticker, as_of_date)  -- 동일 날짜에 중복 방지
);

-- 성능 최적화 인덱스
CREATE INDEX idx_holdings_stock_date_weight
    ON etf_holdings(stock_ticker, as_of_date DESC, weight DESC);
    -- 용도: "이 종목은 어떤 ETF에 포함되어 있나?"

CREATE INDEX idx_holdings_etf_date_weight
    ON etf_holdings(etf_ticker, as_of_date DESC, weight DESC);
    -- 용도: "이 ETF는 어떤 종목들로 구성되어 있나?"

CREATE INDEX idx_holdings_date
    ON etf_holdings(as_of_date DESC);
    -- 용도: 특정 날짜 데이터 조회

CREATE INDEX idx_holdings_weight
    ON etf_holdings(weight DESC);
    -- 용도: 고비중 구성 종목 필터링
```

### 2.3 Modification: `tickers` 테이블 확장

**Purpose**: ETF와 종목을 구분하기 위한 컬럼 추가 (이미 구현됨)

```sql
-- 기존 tickers 테이블에 asset_type 컬럼 이미 존재
-- asset_type: 'STOCK' | 'ETF'
-- ✅ 추가 마이그레이션 불필요
```

---

## 3. Query Patterns & Performance

### 3.1 종목 → ETF 조회

**Query**: "삼성전자(005930)는 어떤 ETF에 포함되어 있나?"

```sql
-- 최신 데이터 기준 조회
SELECT
    eh.etf_ticker,
    e.name AS etf_name,
    eh.weight,
    eh.rank_in_etf,
    e.total_assets,
    e.category
FROM etf_holdings eh
JOIN etfs e ON eh.etf_ticker = e.ticker
WHERE eh.stock_ticker = '005930'
  AND eh.as_of_date = (
      SELECT MAX(as_of_date)
      FROM etf_holdings
      WHERE stock_ticker = '005930'
  )
ORDER BY eh.weight DESC
LIMIT 20;

-- 사용 인덱스: idx_holdings_stock_date_weight
-- 예상 실행 시간: <10ms (10만 레코드 기준)
```

### 3.2 ETF → 종목 조회

**Query**: "TIGER 200 ETF는 어떤 종목들로 구성되어 있나?"

```sql
-- 최신 구성 종목 조회
SELECT
    eh.stock_ticker,
    t.name AS stock_name,
    eh.weight,
    eh.rank_in_etf,
    sd.sector,
    eh.market_value
FROM etf_holdings eh
JOIN tickers t ON eh.stock_ticker = t.ticker
LEFT JOIN stock_details sd ON t.ticker = sd.ticker
WHERE eh.etf_ticker = '152100'  -- TIGER 200
  AND eh.as_of_date = (
      SELECT MAX(as_of_date)
      FROM etf_holdings
      WHERE etf_ticker = '152100'
  )
ORDER BY eh.rank_in_etf ASC
LIMIT 200;

-- 사용 인덱스: idx_holdings_etf_date_weight
-- 예상 실행 시간: <15ms (200개 구성 종목)
```

### 3.3 구성 비중 변화 추적

**Query**: "삼성전자의 TIGER 200 ETF 내 비중이 어떻게 변했나?"

```sql
SELECT
    as_of_date,
    weight,
    rank_in_etf,
    shares,
    market_value,
    weight_change_from_prev
FROM etf_holdings
WHERE etf_ticker = '152100'
  AND stock_ticker = '005930'
ORDER BY as_of_date DESC
LIMIT 30;

-- 사용 인덱스: UNIQUE(etf_ticker, stock_ticker, as_of_date)
-- 예상 실행 시간: <5ms
```

### 3.4 ETF 자금 흐름 분석

**Query**: "최근 30일간 순자산이 가장 많이 증가한 ETF는?"

```sql
WITH etf_aum_changes AS (
    SELECT
        ticker,
        name,
        category,
        total_assets AS current_aum,
        LAG(total_assets) OVER (PARTITION BY ticker ORDER BY last_updated) AS prev_aum
    FROM etfs
    WHERE region = 'KR'
)
SELECT
    ticker,
    name,
    category,
    current_aum,
    (current_aum - prev_aum) AS aum_change,
    ((current_aum - prev_aum) / prev_aum * 100) AS aum_change_percent
FROM etf_aum_changes
WHERE aum_change IS NOT NULL
ORDER BY aum_change DESC
LIMIT 20;

-- 용도: ETF 자금 유입 상위 종목 → 구성 종목 매수 압력 예측
```

### 3.5 고비중 종목 필터링

**Query**: "5% 이상 비중을 차지하는 ETF 구성 종목"

```sql
SELECT
    eh.etf_ticker,
    e.name AS etf_name,
    eh.stock_ticker,
    t.name AS stock_name,
    eh.weight,
    e.total_assets,
    (eh.weight / 100 * e.total_assets) AS exposure_value
FROM etf_holdings eh
JOIN etfs e ON eh.etf_ticker = e.ticker
JOIN tickers t ON eh.stock_ticker = t.ticker
WHERE eh.weight >= 5.0
  AND eh.as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
ORDER BY exposure_value DESC;

-- 용도: 대형 ETF의 고비중 종목 리스크 관리
-- 사용 인덱스: idx_holdings_weight
```

---

## 4. Data Collection Strategy

### 4.1 데이터 소스 (시장별)

| Region | Data Source | API Rate Limit | Update Frequency |
|--------|-------------|----------------|------------------|
| KR | etfcheck.co.kr | No limit (web scraping) | Daily |
| KR | KIS API | 20 req/sec | Daily |
| US | ETF.com API | TBD | Weekly |
| US | Polygon.io | 5 req/min | Weekly |
| CN/HK | AkShare | 1.5 req/sec | Weekly |
| JP | JPX API | TBD | Weekly |
| VN | VNDirect API | TBD | Weekly |

### 4.2 업데이트 주기

```yaml
major_etfs:
  description: "주요 대형 ETF (AUM 1조원 이상)"
  update_frequency: DAILY
  examples: [TIGER200, KODEX200, SPY, QQQ]

standard_etfs:
  description: "일반 ETF (AUM 1조원 미만)"
  update_frequency: WEEKLY
  examples: [섹터 ETF, 테마 ETF]

long_term_etfs:
  description: "장기 인덱스 ETF (구성 변화 적음)"
  update_frequency: QUARTERLY
  examples: [배당 ETF, 채권 ETF]
```

### 4.3 데이터 보관 정책

**Retention Strategy**: 최근 데이터는 상세하게, 과거 데이터는 압축

```sql
-- 보관 정책 적용 쿼리
DELETE FROM etf_holdings
WHERE as_of_date < date('now', '-90 days')  -- 90일 이전 데이터 삭제
  AND strftime('%w', as_of_date) != '5';    -- 금요일 데이터는 보존 (주간 스냅샷)

DELETE FROM etf_holdings
WHERE as_of_date < date('now', '-365 days')  -- 1년 이전 데이터 삭제
  AND strftime('%d', as_of_date) != '01';    -- 월초 데이터는 보존 (월간 스냅샷)
```

**Expected Storage**:
- 최근 30일: ~300MB (모든 ETF × 일일 업데이트)
- 31-90일: ~150MB (주간 스냅샷만)
- 90일-1년: ~50MB (월간 스냅샷만)
- **Total**: ~500MB (1년 데이터)

---

## 5. Integration with Spock Trading Strategy

### 5.1 LayeredScoringEngine 통합

**Module**: `RelativeStrengthModule` (Layer 2 - Structural, 15 points)

```python
# 예시: ETF 편입 개수 기반 가산점
def calculate_etf_preference_score(ticker: str) -> float:
    """ETF 편입 개수 기반 기관 선호도 점수 (0-5점)"""

    query = """
        SELECT COUNT(DISTINCT eh.etf_ticker) AS etf_count,
               SUM(e.total_assets * eh.weight / 100) AS total_exposure
        FROM etf_holdings eh
        JOIN etfs e ON eh.etf_ticker = e.ticker
        WHERE eh.stock_ticker = ?
          AND eh.as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
          AND e.total_assets > 1000000000000  -- 1조원 이상 ETF만
    """

    result = db.execute(query, (ticker,)).fetchone()
    etf_count = result['etf_count']
    total_exposure = result['total_exposure'] or 0

    # 점수 계산
    count_score = min(etf_count / 5, 3.0)  -- 5개 이상 ETF 편입 = 3점
    exposure_score = min(total_exposure / 10_000_000_000, 2.0)  -- 100억원 이상 노출 = 2점

    return count_score + exposure_score  -- 최대 5점
```

### 5.2 Market Sentiment Analysis

**Module**: `stock_sentiment.py` 확장

```python
def analyze_etf_fund_flow(region: str = 'KR') -> Dict:
    """ETF 자금 흐름 분석"""

    query = """
        WITH aum_changes AS (
            SELECT
                e1.ticker,
                e1.name,
                e1.category,
                e1.total_assets AS current_aum,
                e2.total_assets AS prev_aum,
                (e1.total_assets - e2.total_assets) AS flow
            FROM etfs e1
            LEFT JOIN etfs e2 ON e1.ticker = e2.ticker
                AND date(e1.last_updated) = date(e2.last_updated, '+1 day')
            WHERE e1.region = ?
        )
        SELECT
            category,
            SUM(flow) AS net_flow,
            COUNT(*) AS etf_count
        FROM aum_changes
        WHERE flow IS NOT NULL
        GROUP BY category
        ORDER BY net_flow DESC
    """

    results = db.execute(query, (region,)).fetchall()

    return {
        'top_inflow_sectors': results[:3],      -- 자금 유입 상위 섹터
        'top_outflow_sectors': results[-3:],    -- 자금 유출 상위 섹터
        'signal': 'ROTATION' if len(results) > 5 else 'STABLE'
    }
```

### 5.3 Risk Management

**Module**: `kelly_calculator.py` 확장

```python
def calculate_etf_concentration_risk(portfolio: List[str]) -> Dict:
    """포트폴리오의 ETF 집중도 리스크 계산"""

    query = """
        SELECT
            eh.etf_ticker,
            e.name AS etf_name,
            COUNT(DISTINCT eh.stock_ticker) AS overlap_count,
            SUM(eh.weight) AS total_weight
        FROM etf_holdings eh
        JOIN etfs e ON eh.etf_ticker = e.ticker
        WHERE eh.stock_ticker IN ({})
          AND eh.as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
        GROUP BY eh.etf_ticker
        HAVING overlap_count >= 2  -- 2종목 이상 중복
        ORDER BY overlap_count DESC, total_weight DESC
    """.format(','.join('?' * len(portfolio)))

    results = db.execute(query, portfolio).fetchall()

    # 리스크 평가
    high_risk_etfs = [r for r in results if r['overlap_count'] >= 3]

    return {
        'concentrated_etfs': high_risk_etfs,
        'risk_level': 'HIGH' if high_risk_etfs else 'LOW',
        'recommendation': '포트폴리오 분산 필요' if high_risk_etfs else '적정 분산'
    }
```

---

## 6. Implementation Plan

### Phase 1: Database Schema Migration (Week 1)

**Tasks**:
1. ✅ Verify tickers.asset_type column exists (이미 구현됨)
2. Create etfs table with indexes
3. Create etf_holdings table with indexes
4. Write migration script for existing data (if any)
5. Add data validation constraints

**Script**: `scripts/migrate_etf_schema.py`

```python
def migrate_etf_schema(db_path: str):
    """ETF 스키마 마이그레이션"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create etfs table
    cursor.execute("""...""")  # etfs table DDL

    # Create etf_holdings table
    cursor.execute("""...""")  # etf_holdings table DDL

    # Create indexes
    cursor.execute("""...""")  # 4개 인덱스 생성

    conn.commit()
    conn.close()

    logger.info("✅ ETF schema migration completed")
```

### Phase 2: Data Collection Module (Week 2)

**New Module**: `modules/etf_data_collector.py`

```python
class ETFDataCollector:
    """ETF 구성 종목 데이터 수집기"""

    def __init__(self, db_manager: SQLiteDatabaseManager):
        self.db = db_manager
        self.data_sources = {
            'KR': ETFCheckKRScraper(),
            'US': PolygonETFAPI(),
            # ... 기타 시장
        }

    def collect_etf_list(self, region: str = 'KR') -> List[str]:
        """ETF 목록 수집"""
        pass

    def collect_etf_holdings(self, etf_ticker: str, force_refresh: bool = False) -> bool:
        """ETF 구성 종목 수집"""
        pass

    def update_all_etfs(self, region: str = 'KR', incremental: bool = True):
        """전체 ETF 업데이트"""
        pass
```

### Phase 3: Database Manager Extension (Week 2)

**Extend**: `modules/db_manager_sqlite.py`

```python
class SQLiteDatabaseManager:
    # ... 기존 메서드

    # ========================================
    # ETF HOLDINGS OPERATIONS
    # ========================================

    def insert_etf_info(self, etf_data: Dict) -> bool:
        """ETF 기본 정보 삽입"""
        pass

    def insert_etf_holding(self, holding_data: Dict) -> bool:
        """ETF 구성 종목 삽입"""
        pass

    def get_etfs_by_stock(self, stock_ticker: str, as_of_date: str = None) -> List[Dict]:
        """종목 → ETF 조회"""
        pass

    def get_stocks_by_etf(self, etf_ticker: str, as_of_date: str = None) -> List[Dict]:
        """ETF → 종목 조회"""
        pass

    def get_etf_weight_history(self, etf_ticker: str, stock_ticker: str, days: int = 30) -> List[Dict]:
        """구성 비중 변화 추적"""
        pass

    def cleanup_old_etf_holdings(self, retention_days: int = 90) -> int:
        """오래된 ETF 구성 데이터 정리"""
        pass
```

### Phase 4: Trading Strategy Integration (Week 3)

**Modules to Update**:
- `modules/layered_scoring_engine.py`: RelativeStrengthModule 확장
- `modules/stock_sentiment.py`: ETF 자금 흐름 분석 추가
- `modules/kelly_calculator.py`: ETF 집중도 리스크 계산 추가

### Phase 5: Testing & Validation (Week 4)

**Test Suite**: `tests/test_etf_holdings.py`

```python
def test_etf_stock_relationship():
    """ETF-종목 관계 테스트"""

    # 1. 종목 → ETF 조회
    etfs = db.get_etfs_by_stock('005930')
    assert len(etfs) > 0
    assert all('weight' in etf for etf in etfs)

    # 2. ETF → 종목 조회
    stocks = db.get_stocks_by_etf('152100')
    assert len(stocks) == 200  # TIGER 200 = 200개 종목

    # 3. 구성 비중 변화 추적
    history = db.get_etf_weight_history('152100', '005930', days=30)
    assert len(history) > 0
```

---

## 7. Monitoring & Metrics

### 7.1 Prometheus Metrics

**New Metrics**: `monitoring/exporters/spock_exporter.py`

```python
# ETF 데이터 품질 메트릭
spock_etf_total = Gauge('spock_etf_total', 'Total number of ETFs', ['region'])
spock_etf_holdings_total = Gauge('spock_etf_holdings_total', 'Total ETF holdings records')
spock_etf_last_update = Gauge('spock_etf_last_update_timestamp', 'Last ETF data update', ['region'])

# ETF 데이터 수집 메트릭
spock_etf_collection_duration = Histogram('spock_etf_collection_duration_seconds',
                                          'ETF data collection duration', ['region'])
spock_etf_collection_errors = Counter('spock_etf_collection_errors_total',
                                       'ETF collection errors', ['region', 'error_type'])
```

### 7.2 Grafana Dashboard

**New Dashboard**: `monitoring/grafana/dashboards/etf_dashboard.json`

**Panels**:
- ETF 총 개수 (by region)
- ETF 구성 종목 레코드 수
- 최근 업데이트 시각
- 데이터 수집 성공률
- ETF 자금 흐름 (Top 10 Inflow/Outflow)
- 고비중 종목 경고 (weight >5%)

---

## 8. Performance Benchmarks

### 8.1 Query Performance Targets

| Query Type | Target Time | Index Used | Expected Scale |
|------------|-------------|------------|----------------|
| 종목 → ETF | <10ms | idx_holdings_stock_date_weight | 100K records |
| ETF → 종목 | <15ms | idx_holdings_etf_date_weight | 200 stocks |
| 비중 변화 추적 | <5ms | UNIQUE index | 30 days |
| 자금 흐름 분석 | <50ms | idx_etfs_total_assets | 500 ETFs |

### 8.2 Storage Estimates

**1년 데이터 기준**:
- 한국 ETF: ~500개 ETF × 평균 100 종목 × 365일 = ~18M records
- 미국 ETF: ~3,000개 ETF × 평균 50 종목 × 52주 = ~7.8M records
- **Total**: ~26M records → ~2-3GB (인덱스 포함)

---

## 9. Risk Mitigation

### 9.1 Data Quality Risks

**Risk**: ETF 구성 종목 데이터 불일치

**Mitigation**:
- 여러 데이터 소스 크로스 체크
- 구성 비중 합계 100% 검증
- 일일 데이터 검증 스크립트 실행

```python
def validate_etf_holdings(etf_ticker: str, as_of_date: str) -> bool:
    """ETF 구성 데이터 검증"""

    query = """
        SELECT SUM(weight) AS total_weight
        FROM etf_holdings
        WHERE etf_ticker = ? AND as_of_date = ?
    """

    result = db.execute(query, (etf_ticker, as_of_date)).fetchone()
    total_weight = result['total_weight']

    # 허용 오차: ±0.5%
    if abs(total_weight - 100.0) > 0.5:
        logger.error(f"❌ [{etf_ticker}] Weight sum: {total_weight}% (expected: 100%)")
        return False

    return True
```

### 9.2 Performance Risks

**Risk**: 대량 데이터 쿼리 시 성능 저하

**Mitigation**:
- 쿼리 최적화 (EXPLAIN QUERY PLAN 사용)
- 적절한 LIMIT 설정
- 배치 처리 (100-1000 레코드)
- 정기적 VACUUM 및 ANALYZE 실행

---

## 10. Future Enhancements

### 10.1 Phase 2 Features (3-6 months)

- **Real-time ETF 자금 흐름 추적**: WebSocket API 통합
- **AI 기반 ETF 구성 예측**: GPT-4 활용 재구성 예측
- **포트폴리오 시뮬레이션**: ETF 자금 흐름 기반 백테스팅

### 10.2 Phase 3 Features (6-12 months)

- **글로벌 ETF 확대**: 유럽(UCITS), 신흥시장 ETF
- **크로스 섹터 분석**: ETF를 통한 섹터 로테이션 신호
- **기관 매매 패턴 분석**: ETF 창설/환매 데이터 활용

---

## 11. Conclusion

### Key Takeaways

1. **Normalized Schema**: Many-to-Many 관계를 통한 유연한 데이터 모델링
2. **Performance Optimized**: 4개의 전략적 인덱스로 빠른 쿼리 성능 보장
3. **Time-Series Ready**: as_of_date를 통한 구성 변화 추적 가능
4. **Trading Strategy Integration**: LayeredScoringEngine과 자연스러운 통합

### Implementation Timeline

- **Week 1**: Database schema migration
- **Week 2**: Data collection module + DB manager extension
- **Week 3**: Trading strategy integration
- **Week 4**: Testing & validation

**Total Effort**: 4 weeks (1 developer)

### Success Metrics

- ✅ Query performance: 95% of queries <50ms
- ✅ Data freshness: Daily updates for major ETFs
- ✅ Coverage: >90% of major ETFs per region
- ✅ Data quality: <1% weight sum deviation

---

**Next Steps**: Proceed to Phase 1 implementation with schema migration script.
