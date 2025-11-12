# 매크로 분석 Tool - 최적화 설계 문서

**버전**: 2.0 (최적화)
**작성일**: 2025-01-12
**상태**: 설계 완료

---

## 📋 설계 개요

### 핵심 원칙
1. **기존 인프라 최대 활용**: 신규 테이블 최소화 (3개만)
2. **데이터 재사용**: global_market_indices, exchange_rates, fx_valuation_signals
3. **계산 기반**: 섹터 성과는 기존 ohlcv_data에서 계산
4. **점진적 구축**: Phase 0부터 단계적 구현

### 아키텍처 변경사항

| 구분 | 기존 설계 | 최적화 설계 | 절감 |
|------|----------|------------|------|
| 신규 테이블 | 6개 | 3개 | 50% |
| 데이터 수집 | 5개 소스 | 2개 소스 | 60% |
| 개발 기간 | 11-17일 | 9-13일 | 25% |

---

## 🗄️ 데이터베이스 설계

### 기존 테이블 활용 (수정 불필요)

#### 1. global_market_indices (재사용)
**상태**: ✅ 이미 5년치 데이터 존재 (2020-10-22 ~ 2025-10-20)

```sql
-- 현재 스키마 (수정 불필요)
CREATE TABLE global_market_indices (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    index_name VARCHAR(100),
    region VARCHAR(20),
    close_price DECIMAL(15,4),
    open_price DECIMAL(15,4),
    high_price DECIMAL(15,4),
    low_price DECIMAL(15,4),
    volume BIGINT,
    change_percent DECIMAL(10,4),
    trend_5d VARCHAR(10),
    consecutive_days INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (date, symbol)
);

-- 커버된 지수 (10개)
-- KR: ^KS11 (KOSPI), ^KQ11 (KOSDAQ)
-- US: ^GSPC (S&P 500), ^IXIC (NASDAQ), ^DJI (DOW)
-- JP: ^N225 (Nikkei 225)
-- HK: ^HSI (Hang Seng)
-- CN: 000001.SS (Shanghai)
-- EU: ^STOXX (STOXX 600)
-- UK: ^FTSE (FTSE 100)
```

**퀀트 분석 활용**:
- ✅ 베타 계산 (Low-Volatility 팩터)
- ✅ 시장 상관관계 분석
- ✅ 포트폴리오 리스크 관리
- ✅ 시장 regime 분류

#### 2. exchange_rates (재사용, 데이터 보충)
**상태**: ⚠️ 24개 레코드만 존재 → 백필 필요

```sql
-- 현재 스키마 (수정 불필요)
CREATE TABLE exchange_rates (
    id BIGSERIAL PRIMARY KEY,
    base_currency VARCHAR(3) NOT NULL,
    quote_currency VARCHAR(3) NOT NULL,
    date DATE NOT NULL,
    rate DECIMAL(20,10) NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (base_currency, quote_currency, date)
);

-- 현재 커버된 페어 (12개)
-- USD/KRW, USD/JPY, USD/EUR, USD/GBP
-- KRW/USD, KRW/JPY, KRW/EUR, KRW/CNY
-- JPY/USD, JPY/KRW, JPY/EUR, JPY/CNY
```

**필요한 작업**:
```bash
# 과거 1년 백필
python3 scripts/backfill_fx_history.py \
  --start-date 2024-01-01 \
  --end-date 2025-01-12
```

#### 3. fx_valuation_signals (재사용, 데이터 보충)
**상태**: ⚠️ 1개 레코드만 → 백필 필요

```sql
-- 현재 스키마 (수정 불필요)
CREATE TABLE fx_valuation_signals (
    id BIGSERIAL PRIMARY KEY,
    currency VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    usd_rate DECIMAL(15,6) NOT NULL,
    return_1m DECIMAL(10,4),
    return_3m DECIMAL(10,4),
    return_6m DECIMAL(10,4),
    return_12m DECIMAL(10,4),
    trend_score DECIMAL(10,4),           -- -100 to +100
    volatility DECIMAL(10,4),
    momentum_acceleration DECIMAL(10,4),
    attractiveness_score DECIMAL(10,4),  -- 0 to 100
    confidence DECIMAL(5,4),
    data_quality VARCHAR(20) DEFAULT 'GOOD',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    UNIQUE (currency, region, date)
);
```

**퀀트 분석 활용**:
- ✅ 환율 밸류에이션 (attractiveness_score)
- ✅ 모멘텀 분석 (trend_score, momentum_acceleration)
- ✅ 변동성 분석 (volatility)
- ✅ 수출주 분석 (USD/KRW 추세)

---

### 신규 테이블 (추가 필요)

#### 1. bond_yields (채권 수익률)

```sql
CREATE TABLE bond_yields (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,        -- US10Y, US2Y, KR10Y
    country VARCHAR(10) NOT NULL,       -- US, KR, JP, DE
    maturity VARCHAR(10) NOT NULL,      -- 2Y, 10Y, 30Y
    date DATE NOT NULL,
    yield DECIMAL(10, 6) NOT NULL,      -- 수익률 (%)
    change_bps DECIMAL(10, 2),          -- 변화 (basis points)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- TimescaleDB 최적화
SELECT create_hypertable('bond_yields', 'date');

-- 인덱스
CREATE INDEX idx_bond_yields_symbol ON bond_yields(symbol, date DESC);
CREATE INDEX idx_bond_yields_country ON bond_yields(country, maturity, date DESC);

-- 압축 정책 (1년 후)
SELECT add_compression_policy('bond_yields', INTERVAL '365 days');
```

**데이터 소스**: yfinance
```python
BOND_SYMBOLS = {
    '^TNX': {'country': 'US', 'maturity': '10Y', 'name': 'US 10Y Treasury'},
    '^TYX': {'country': 'US', 'maturity': '30Y', 'name': 'US 30Y Treasury'},
    '^FVX': {'country': 'US', 'maturity': '5Y', 'name': 'US 5Y Treasury'},
    # KR bonds: 대체 소스 필요 (한국투자증권 API)
}
```

**퀀트 분석 활용**:
- ✅ Yield curve 분석 (10Y-2Y spread)
- ✅ 금리 추세 파악
- ✅ 리스크 환경 평가

#### 2. commodities (원자재 가격)

```sql
CREATE TABLE commodities (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,        -- GC=F, CL=F, SI=F
    name VARCHAR(50) NOT NULL,          -- Gold, Crude Oil, Silver
    category VARCHAR(20) NOT NULL,      -- Metals, Energy, Agriculture
    date DATE NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    volume BIGINT,
    change_pct DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- TimescaleDB 최적화
SELECT create_hypertable('commodities', 'date');

-- 인덱스
CREATE INDEX idx_commodities_symbol ON commodities(symbol, date DESC);
CREATE INDEX idx_commodities_category ON commodities(category, date DESC);

-- 압축 정책
SELECT add_compression_policy('commodities', INTERVAL '365 days');
```

**데이터 소스**: yfinance
```python
COMMODITY_SYMBOLS = {
    'GC=F': {'name': 'Gold Futures', 'category': 'Metals'},
    'SI=F': {'name': 'Silver Futures', 'category': 'Metals'},
    'CL=F': {'name': 'Crude Oil WTI', 'category': 'Energy'},
    'BZ=F': {'name': 'Brent Crude', 'category': 'Energy'},
    'HG=F': {'name': 'Copper Futures', 'category': 'Metals'},
    'NG=F': {'name': 'Natural Gas', 'category': 'Energy'},
}
```

**퀀트 분석 활용**:
- ✅ 인플레이션 지표 (금, 원유)
- ✅ 안전자산 수요 (금)
- ✅ 경제 활동 지표 (구리, 원유)

#### 3. sector_performance (섹터 성과)

```sql
CREATE TABLE sector_performance (
    id BIGSERIAL,
    region VARCHAR(10) NOT NULL,        -- KR, US
    sector VARCHAR(50) NOT NULL,        -- Technology, Healthcare, ...
    date DATE NOT NULL,
    avg_return_1d DECIMAL(10, 4),       -- 1일 평균 수익률
    avg_return_1w DECIMAL(10, 4),       -- 1주 평균 수익률
    avg_return_1m DECIMAL(10, 4),       -- 1개월 평균 수익률
    avg_return_3m DECIMAL(10, 4),       -- 3개월 평균 수익률
    num_stocks INTEGER,                  -- 섹터 내 종목 수
    strong_stocks INTEGER,               -- 상승 종목 수
    weak_stocks INTEGER,                 -- 하락 종목 수
    momentum VARCHAR(20),                -- strong/moderate/weak/negative
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (region, sector, date)
);

-- TimescaleDB 최적화
SELECT create_hypertable('sector_performance', 'date');

-- 인덱스
CREATE INDEX idx_sector_perf_region ON sector_performance(region, date DESC);
CREATE INDEX idx_sector_perf_sector ON sector_performance(region, sector, date DESC);
CREATE INDEX idx_sector_perf_momentum ON sector_performance(momentum, date DESC);

-- 압축 정책
SELECT add_compression_policy('sector_performance', INTERVAL '365 days');
```

**데이터 소스**: 기존 ohlcv_data 테이블 (계산)
```python
# 외부 수집 불필요! 기존 데이터 활용
KR_SECTORS = {
    "Technology": ["005930", "000660"],      # 삼성전자, SK하이닉스
    "Battery": ["373220", "066970"],         # LG에너지, 에코프로
    "Automobiles": ["005380", "000270"],     # 현대차, 기아
    "Financials": ["055550", "105560"],      # 신한, KB
    "Healthcare": ["207940", "068270"],      # 삼성바이오, 셀트리온
    "Steel": ["005490", "004020"],           # POSCO, 현대제철
    "Chemicals": ["051910", "009830"],       # LG화학, 한화솔루션
    "Retail": ["051900", "069960"],          # LG생활건강, 현대백화점
    "Construction": ["000720", "028260"],    # 현대건설, 삼성물산
    "Utilities": ["015760"],                 # 한국전력
}
```

**퀀트 분석 활용**:
- ✅ 섹터 rotation 분석
- ✅ 강세/약세 섹터 식별
- ✅ 포트폴리오 섹터 배분

---

## 📊 데이터 아키텍처

### 데이터 흐름도

```
┌─────────────────────────────────────────────────────────────┐
│                  Data Collection Layer                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  [기존] backfill_market_indices.py                           │
│    └─> global_market_indices (10 indices) ✅                 │
│                                                               │
│  [기존] collect_fx_data.py                                   │
│    ├─> exchange_rates (12 pairs) ⚠️ 백필 필요               │
│    └─> fx_valuation_signals (5 currencies) ⚠️ 백필 필요     │
│                                                               │
│  [신규] collect_macro_data.py                                │
│    ├─> bond_yields (yfinance)                                │
│    └─> commodities (yfinance)                                │
│                                                               │
│  [신규] calculate_sector_performance.py                      │
│    └─> sector_performance (계산: ohlcv_data → sectors)      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL + TimescaleDB                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  [기존 테이블]                                               │
│    • global_market_indices (12,383 rows) ✅                  │
│    • exchange_rates (24 rows) ⚠️                            │
│    • fx_valuation_signals (1 row) ⚠️                        │
│                                                               │
│  [신규 테이블]                                               │
│    • bond_yields                                             │
│    • commodities                                             │
│    • sector_performance                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Analysis Layer                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  RegimeAnalyzer                                              │
│    └─> market_sentiment (시장 regime 분류)                  │
│                                                               │
│  CorrelationAnalyzer                                         │
│    └─> 자산 간 상관관계 분석                                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    MCP Tool Layer                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  MacroAdapter.analyze_macro_environment()                    │
│    ├─> 환율 (exchange_rates + fx_valuation_signals)         │
│    ├─> 지수 (global_market_indices)                         │
│    ├─> 채권 (bond_yields)                                   │
│    ├─> 원자재 (commodities)                                 │
│    ├─> 섹터 (sector_performance)                            │
│    └─> 시장 regime (market_sentiment)                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    Claude Desktop 응답
```

---

## 🔧 섹터 계산 로직 설계

### 섹터 매핑 전략

```python
# modules/macro/sector_calculator.py

class SectorPerformanceCalculator:
    """
    기존 ohlcv_data 테이블로 섹터 성과 계산
    외부 데이터 수집 불필요
    """

    # 한국 시장 섹터 매핑
    KR_SECTORS = {
        "Technology": {
            "tickers": ["005930", "000660", "035420", "035720"],
            "description": "반도체, 전자"
        },
        "Battery": {
            "tickers": ["373220", "066970", "247540", "086520"],
            "description": "2차전지, 배터리 소재"
        },
        "Automobiles": {
            "tickers": ["005380", "000270", "012330"],
            "description": "완성차, 부품"
        },
        "Financials": {
            "tickers": ["055550", "105560", "086790", "138930"],
            "description": "은행, 증권, 보험"
        },
        "Healthcare": {
            "tickers": ["207940", "068270", "326030", "302440"],
            "description": "바이오, 제약"
        },
        "Steel": {
            "tickers": ["005490", "004020"],
            "description": "철강"
        },
        "Chemicals": {
            "tickers": ["051910", "009830", "096770"],
            "description": "화학, 정유"
        },
        "Retail": {
            "tickers": ["051900", "069960", "006400"],
            "description": "유통, 백화점"
        },
        "Construction": {
            "tickers": ["000720", "028260", "042660"],
            "description": "건설"
        },
        "Utilities": {
            "tickers": ["015760"],
            "description": "전력, 가스"
        }
    }

    # 미국 시장 섹터 매핑 (S&P 500 섹터)
    US_SECTORS = {
        "Technology": {
            "description": "Information Technology",
            "calculate_from": "^SP500-45"  # Technology Select Sector SPDR ETF
        },
        "Healthcare": {
            "description": "Healthcare",
            "calculate_from": "^SP500-35"
        },
        "Financials": {
            "description": "Financials",
            "calculate_from": "^SP500-40"
        },
        # ... 11개 섹터
    }

    async def calculate_daily_performance(
        self,
        region: str,
        date: str
    ) -> dict:
        """
        일일 섹터 성과 계산

        Args:
            region: 'KR' or 'US'
            date: 계산 날짜 (YYYY-MM-DD)

        Returns:
            섹터별 성과 딕셔너리
        """
        if region == "KR":
            return await self._calculate_kr_sectors(date)
        elif region == "US":
            return await self._calculate_us_sectors(date)

    async def _calculate_kr_sectors(self, date: str) -> dict:
        """
        한국 섹터 성과 계산 (ohlcv_data 직접 쿼리)

        SQL 로직:
        1. 각 섹터별 ticker 리스트로 ohlcv_data 조회
        2. 1일, 1주, 1개월, 3개월 수익률 계산
        3. 평균 수익률 및 상승/하락 종목 수 계산
        """
        results = {}

        for sector, info in self.KR_SECTORS.items():
            tickers = info["tickers"]

            # SQL: 섹터 평균 수익률 계산
            query = """
            WITH sector_returns AS (
                SELECT
                    o.ticker,
                    o.date,
                    o.close,
                    LAG(o.close, 1) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1d_ago,
                    LAG(o.close, 7) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1w_ago,
                    LAG(o.close, 30) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1m_ago,
                    LAG(o.close, 90) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_3m_ago
                FROM ohlcv_data o
                WHERE o.ticker = ANY(:tickers)
                  AND o.region = 'KR'
                  AND o.date <= :date
                  AND o.date >= :date - INTERVAL '90 days'
            )
            SELECT
                AVG((close / close_1d_ago - 1) * 100) as avg_return_1d,
                AVG((close / close_1w_ago - 1) * 100) as avg_return_1w,
                AVG((close / close_1m_ago - 1) * 100) as avg_return_1m,
                AVG((close / close_3m_ago - 1) * 100) as avg_return_3m,
                COUNT(*) as num_stocks,
                COUNT(*) FILTER (WHERE close > close_1m_ago) as strong_stocks,
                COUNT(*) FILTER (WHERE close < close_1m_ago) as weak_stocks
            FROM sector_returns
            WHERE date = :date
            """

            sector_data = await self.db.fetch_one(
                query,
                {"tickers": tickers, "date": date}
            )

            # 모멘텀 분류
            momentum = self._classify_momentum(sector_data["avg_return_1m"])

            results[sector] = {
                "avg_return_1d": sector_data["avg_return_1d"],
                "avg_return_1w": sector_data["avg_return_1w"],
                "avg_return_1m": sector_data["avg_return_1m"],
                "avg_return_3m": sector_data["avg_return_3m"],
                "num_stocks": sector_data["num_stocks"],
                "strong_stocks": sector_data["strong_stocks"],
                "weak_stocks": sector_data["weak_stocks"],
                "momentum": momentum
            }

        return results

    def _classify_momentum(self, return_1m: float) -> str:
        """
        모멘텀 분류

        Args:
            return_1m: 1개월 수익률

        Returns:
            'strong' / 'moderate' / 'weak' / 'negative'
        """
        if return_1m >= 10:
            return "strong"
        elif return_1m >= 3:
            return "moderate"
        elif return_1m >= 0:
            return "weak"
        else:
            return "negative"

    async def identify_rotation(self, sector_perf: dict) -> dict:
        """
        섹터 rotation 패턴 식별

        Returns:
            {
                "rotation_type": "cyclical_to_growth",
                "leaders": ["Technology", "Battery"],
                "laggards": ["Utilities", "Construction"],
                "intensity": 0.75
            }
        """
        # 성과 순위 정렬
        ranked = sorted(
            sector_perf.items(),
            key=lambda x: x[1]["avg_return_1m"],
            reverse=True
        )

        leaders = [s[0] for s in ranked[:3]]
        laggards = [s[0] for s in ranked[-3:]]

        # Rotation 강도 (표준편차 기반)
        returns = [s[1]["avg_return_1m"] for s in ranked]
        intensity = min(np.std(returns) / 10, 1.0)

        # Rotation 타입 분류
        rotation_type = self._classify_rotation_type(leaders, laggards)

        return {
            "rotation_type": rotation_type,
            "leaders": leaders,
            "laggards": laggards,
            "intensity": intensity
        }
```

---

## 📅 구현 로드맵

### Phase 0: 데이터 정상화 (1-2일) 🔴 최우선

**목표**: 기존 테이블 데이터 보충

**작업**:
1. 환율 백필
```bash
python3 scripts/backfill_fx_history.py \
  --start-date 2024-01-01 \
  --end-date 2025-01-12 \
  --currencies USD,HKD,CNY,JPY,VND
```

2. 글로벌 지수 최신화 (이미 5년치, 최근만 업데이트)
```bash
python3 scripts/backfill_market_indices.py --days 90
```

3. 검증
```bash
# 데이터 확인
psql -d quant_platform -c "
SELECT
  'exchange_rates' as table_name,
  COUNT(*) as rows,
  MIN(date) as earliest,
  MAX(date) as latest
FROM exchange_rates
UNION ALL
SELECT 'fx_valuation_signals', COUNT(*), MIN(date), MAX(date)
FROM fx_valuation_signals;
"

# 목표
# exchange_rates: >4,000 rows (12 pairs × 365 days)
# fx_valuation_signals: >1,800 rows (5 currencies × 365 days)
```

4. 일일 수집 활성화
```bash
# crontab 설정
0 19 * * * cd /Users/13ruce/spock && python3 scripts/collect_fx_data.py
0 19 * * * cd /Users/13ruce/spock && python3 scripts/backfill_market_indices.py --days 1
```

---

### Phase 1: 신규 테이블 생성 (0.5일)

**파일**: `scripts/schema/macro_new_tables.sql`

```sql
-- 1. bond_yields 테이블
CREATE TABLE bond_yields (
    -- (위 스키마 참조)
);
SELECT create_hypertable('bond_yields', 'date');
-- 인덱스 생성
-- 압축 정책

-- 2. commodities 테이블
CREATE TABLE commodities (
    -- (위 스키마 참조)
);
SELECT create_hypertable('commodities', 'date');
-- 인덱스 생성
-- 압축 정책

-- 3. sector_performance 테이블
CREATE TABLE sector_performance (
    -- (위 스키마 참조)
);
SELECT create_hypertable('sector_performance', 'date');
-- 인덱스 생성
-- 압축 정책
```

**실행**:
```bash
psql -d quant_platform -f scripts/schema/macro_new_tables.sql
```

---

### Phase 2: 섹터 계산기 구현 (2일)

**파일**: `modules/macro/sector_calculator.py`

**구조**:
```python
class SectorPerformanceCalculator:
    KR_SECTORS = {...}
    US_SECTORS = {...}

    async def calculate_daily_performance(region, date)
    async def _calculate_kr_sectors(date)
    async def _calculate_us_sectors(date)
    def _classify_momentum(return_1m)
    async def identify_rotation(sector_perf)
    async def save_to_db(region, date, sector_data)
```

**실행 스크립트**: `scripts/calculate_sector_performance.py`
```bash
python3 scripts/calculate_sector_performance.py \
  --region KR \
  --date 2025-01-12
```

---

### Phase 3: 데이터 수집 확장 (2일)

**파일**: `scripts/collect_macro_data.py`

**구조**:
```python
class MacroDataCollector:
    BOND_SYMBOLS = {...}
    COMMODITY_SYMBOLS = {...}

    async def collect_bonds(date)
    async def collect_commodities(date)
    async def run_daily_collection()
```

**실행**:
```bash
# 과거 데이터 백필
python3 scripts/collect_macro_data.py \
  --start-date 2024-01-01 \
  --end-date 2025-01-12 \
  --components bonds,commodities

# 일일 수집
python3 scripts/collect_macro_data.py --date today
```

---

### Phase 4: MCP Tool 구현 (2-3일)

**파일**:
- `mcp_server/adapters/macro_adapter.py`
- `mcp_server/tools/macro_tool.py`
- `mcp_server/server.py` (등록)

**구조**:
```python
# macro_adapter.py
class MacroAdapter:
    async def analyze_macro_environment(**kwargs)
    async def _get_indices(date, lookback)
    async def _get_currencies(date, lookback)
    async def _get_bonds(date, lookback)
    async def _get_commodities(date, lookback)
    async def _get_sectors(date, regions)
    async def _analyze_regime(date)

# macro_tool.py
def get_macro_analysis_tool_def() -> Tool
async def handle_analyze_macro_environment(adapter, arguments)

# server.py
self.macro_adapter = MacroAdapter()  # Line 88
tools.append(get_macro_analysis_tool_def())  # Line 111
elif name == "analyze_macro_environment":  # Line 145
    return await handle_analyze_macro_environment(...)
```

---

### Phase 5: 시장 Regime 분석기 (2-3일)

**파일**: `modules/macro/regime_analyzer.py`

**구조**:
```python
class MarketRegimeAnalyzer:
    def classify_regime(macro_data) -> dict
    def _calculate_risk_score(data) -> float
    def _calculate_rotation_score(data) -> float
    def _generate_summary(regime_data) -> str
```

---

## 🎯 성공 기준

### 데이터 커버리지
- ✅ 글로벌 지수: 10개 (5년 히스토리)
- ✅ 환율: 12 pairs (1년 히스토리)
- ✅ 채권: 3개 (미국 국채)
- ✅ 원자재: 6개 (금, 은, 원유 등)
- ✅ 섹터: KR 10개, US 11개

### 성능 목표
- MCP Tool 응답: <2초
- 섹터 계산: <1분
- 일일 수집: <3분

### 데이터 품질
- 정확도: >99%
- 가용성: >99.9%
- 지연시간: <1일

---

## 📝 다음 단계

1. **Phase 0 실행**: 환율 백필 및 검증
2. **SQL 스키마 생성**: 신규 3개 테이블
3. **섹터 계산기 구현**: ohlcv_data 활용
4. **데이터 수집 확장**: 채권 + 원자재
5. **MCP Tool 통합**: 기존 테이블 쿼리

---

**문서 버전**: 2.0
**최종 수정**: 2025-01-12
**다음 검토**: Phase 0 완료 후
