# NXT 지원을 위한 데이터베이스 스키마 설계 문서

## 문서 정보

- **작성일**: 2024-01-XX
- **버전**: 1.0
- **대상**: Spock Trading System
- **목적**: NXT (Next Exchange) 지원을 위한 스키마 변경 사항 문서화

---

## 1. 배경 및 목적

### 1.1 NXT (Next Exchange)란?

**NXT**는 2024년 한국에 새롭게 출범한 **제2의 주식거래소**입니다.

**특징**:
- 성장 기업 및 스타트업 중심 시장
- 기존 KOSPI, KOSDAQ과 병행 운영
- 두 개의 하위 시장: **KOSPI NXT**, **KOSDAQ NXT**
- 미국의 NASDAQ과 NYSE 관계와 유사

**출범 배경**:
- 기존 거래소의 높은 상장 기준으로 인한 진입 장벽
- 혁신 기업 및 Pre-IPO 단계 기업에게 자금 조달 기회 제공
- 글로벌 트렌드 (NASDAQ의 성공 사례 벤치마킹)

### 1.2 스키마 변경 필요성

**기존 스키마의 한계**:
```sql
exchange TEXT NOT NULL  -- 값: KOSPI, KOSDAQ, NYSE, NASDAQ 등
```

**문제점**:
1. KOSPI NXT와 전통 KOSPI를 구분할 수 없음
2. `exchange` 필드에 'KOSPI_NXT', 'KOSDAQ_NXT' 추가 시 타입 폭발
3. 향후 시장 계층 추가 시 확장 불가능 (예: KOSDAQ_GLOBAL)

**해결 방안**:
- **`market_tier`** 필드 추가: 거래소 내 시장 계층을 표현
- 계층적 분류: `exchange` (거래소) + `market_tier` (시장 계층)

---

## 2. 스키마 변경 사항

### 2.1 tickers 테이블 변경

#### Before (기존)
```sql
CREATE TABLE tickers (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_eng TEXT,

    exchange TEXT NOT NULL,       -- KOSPI, KOSDAQ, NYSE 등
    region TEXT NOT NULL,          -- KR, US, HK 등
    currency TEXT NOT NULL DEFAULT 'KRW',

    asset_type TEXT NOT NULL DEFAULT 'STOCK',
    listing_date TEXT,

    is_active BOOLEAN DEFAULT 1,
    delisting_date TEXT,

    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    data_source TEXT
);
```

#### After (변경 후)
```sql
CREATE TABLE tickers (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_eng TEXT,

    exchange TEXT NOT NULL,               -- KOSPI, KOSDAQ, NYSE 등
    market_tier TEXT DEFAULT 'MAIN',      -- ← NEW: MAIN, NXT, KONEX 등
    region TEXT NOT NULL,                 -- KR, US, HK 등
    currency TEXT NOT NULL DEFAULT 'KRW',

    asset_type TEXT NOT NULL DEFAULT 'STOCK',
    listing_date TEXT,

    is_active BOOLEAN DEFAULT 1,
    delisting_date TEXT,

    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    data_source TEXT
);
```

### 2.2 market_tier 필드 상세 스펙

| 속성 | 값 |
|------|-----|
| **컬럼명** | `market_tier` |
| **데이터 타입** | `TEXT` |
| **기본값** | `'MAIN'` |
| **NULL 허용** | NO (기본값으로 방지) |
| **허용 값** | 'MAIN', 'NXT', 'KONEX', 'KOSDAQ_GLOBAL' (향후 확장) |

**허용 값 설명**:
- **'MAIN'**: 전통적인 주시장 (코스피, 코스닥 메인보드)
- **'NXT'**: Next Exchange (코스피 NXT, 코스닥 NXT)
- **'KONEX'**: Korea New Exchange (중소기업 전용 시장)
- **'KOSDAQ_GLOBAL'**: 코스닥 글로벌 시장 (향후 지원)

### 2.3 인덱스 변경

#### 추가된 인덱스

```sql
-- 복합 인덱스: exchange + market_tier
CREATE INDEX idx_tickers_exchange_tier ON tickers(exchange, market_tier);
```

**목적**:
- 특정 거래소의 특정 시장 계층 조회 성능 최적화
- 예: "KOSPI의 MAIN 시장만 조회" 쿼리 가속화

**쿼리 예시**:
```sql
-- 인덱스 활용 쿼리
SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'MAIN';
SELECT * FROM tickers WHERE exchange = 'KOSDAQ' AND market_tier = 'NXT';
```

---

## 3. 데이터 예시

### 3.1 주식 데이터 샘플

```sql
-- ===== 코스피 메인 시장 =====
INSERT INTO tickers (ticker, name, name_eng, exchange, market_tier, region, currency, asset_type, listing_date, is_active, created_at, last_updated, data_source)
VALUES
('005930', '삼성전자', 'Samsung Electronics', 'KOSPI', 'MAIN', 'KR', 'KRW', 'STOCK', '1975-06-11', 1, '2024-01-15 09:00:00', '2024-01-15 09:00:00', 'KRX Official API');

-- ===== 코스닥 메인 시장 =====
INSERT INTO tickers VALUES
('035720', '카카오', 'Kakao Corp.', 'KOSDAQ', 'MAIN', 'KR', 'KRW', 'STOCK', '2017-07-10', 1, '2024-01-15 09:00:00', '2024-01-15 09:00:00', 'KRX Official API');

-- ===== 코스피 NXT 시장 (가상 예시) =====
INSERT INTO tickers VALUES
('400001', 'NXT성장기업A', 'NXT Growth A', 'KOSPI', 'NXT', 'KR', 'KRW', 'STOCK', '2024-03-15', 1, '2024-03-15 10:00:00', '2024-03-15 10:00:00', 'KRX Official API');

-- ===== 코스닥 NXT 시장 (가상 예시) =====
INSERT INTO tickers VALUES
('400100', 'NXT바이오B', 'NXT Bio B', 'KOSDAQ', 'NXT', 'KR', 'KRW', 'STOCK', '2024-04-01', 1, '2024-04-01 10:00:00', '2024-04-01 10:00:00', 'KRX Official API');

-- ===== KONEX 시장 =====
INSERT INTO tickers VALUES
('290000', '중소기업C', 'SME C', 'KONEX', 'MAIN', 'KR', 'KRW', 'STOCK', '2020-05-20', 1, '2024-01-15 09:00:00', '2024-01-15 09:00:00', 'KRX Official API');
```

### 3.2 market_tier 분포 (예상)

| exchange | market_tier | 예상 종목 수 | 비율 |
|----------|------------|------------|------|
| KOSPI | MAIN | ~900 | 90% |
| KOSPI | NXT | ~100 | 10% |
| KOSDAQ | MAIN | ~1,500 | 95% |
| KOSDAQ | NXT | ~80 | 5% |
| KONEX | MAIN | ~150 | 100% |

---

## 4. 쿼리 예시

### 4.1 기본 쿼리

```sql
-- 1. 모든 한국 주식 조회 (메인 + NXT 포함)
SELECT * FROM tickers WHERE region = 'KR';

-- 2. 코스피 전체 조회 (메인 + NXT)
SELECT * FROM tickers WHERE exchange = 'KOSPI';

-- 3. 코스피 메인 시장만 조회
SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'MAIN';

-- 4. 모든 NXT 주식 조회 (코스피 + 코스닥)
SELECT * FROM tickers WHERE market_tier = 'NXT';

-- 5. 코스피 NXT만 조회
SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'NXT';

-- 6. 코스닥 NXT만 조회
SELECT * FROM tickers WHERE exchange = 'KOSDAQ' AND market_tier = 'NXT';
```

### 4.2 통계 쿼리

```sql
-- market_tier별 종목 수
SELECT market_tier, COUNT(*) as stock_count
FROM tickers
WHERE region = 'KR'
GROUP BY market_tier
ORDER BY stock_count DESC;

-- 거래소 × 시장 계층 교차표
SELECT
    exchange,
    market_tier,
    COUNT(*) as stock_count
FROM tickers
WHERE region = 'KR'
GROUP BY exchange, market_tier
ORDER BY exchange, market_tier;

-- NXT 시장 점유율
SELECT
    CASE
        WHEN market_tier = 'NXT' THEN 'NXT'
        ELSE 'Main'
    END as market_group,
    COUNT(*) as stock_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tickers WHERE region = 'KR'), 2) as percentage
FROM tickers
WHERE region = 'KR'
GROUP BY market_group;
```

### 4.3 JOIN 쿼리 (기술적 분석 연계)

```sql
-- NXT 주식의 기술적 분석 점수 조회
SELECT
    t.ticker,
    t.name,
    t.exchange,
    t.market_tier,
    ta.total_score,
    ta.signal
FROM tickers t
JOIN technical_analysis ta ON t.ticker = ta.ticker
WHERE t.market_tier = 'NXT'
  AND ta.analysis_date = (SELECT MAX(analysis_date) FROM technical_analysis WHERE ticker = t.ticker)
ORDER BY ta.total_score DESC
LIMIT 10;

-- 코스피 NXT 고점수 종목
SELECT
    t.ticker,
    t.name,
    ta.total_score,
    ta.signal
FROM tickers t
JOIN technical_analysis ta ON t.ticker = ta.ticker
WHERE t.exchange = 'KOSPI'
  AND t.market_tier = 'NXT'
  AND ta.total_score >= 70
ORDER BY ta.total_score DESC;
```

---

## 5. KIS API 파라미터 매핑

### 5.1 API 파라미터 대응표

| Exchange | market_tier | KIS API `mkt_id` | KRX Data API Code |
|----------|-------------|------------------|-------------------|
| KOSPI | MAIN | `'STK'` | `'KOSPI'` |
| KOSPI | NXT | `'NXT'` | `'KOSPI_NXT'` (추정) |
| KOSDAQ | MAIN | `'SQ'` | `'KOSDAQ'` |
| KOSDAQ | NXT | `'NXT'` | `'KOSDAQ_NXT'` (추정) |
| KONEX | MAIN | `'KONEX'` | `'KONEX'` |

**중요 사항**:
- KIS API는 **KOSPI NXT와 KOSDAQ NXT를 'NXT' 단일 코드**로 제공
- 세부 구분은 **KRX Data API** 또는 **Ticker 범위** 패턴으로 판별 필요

### 5.2 Python 코드 예시

```python
# config/market_tiers.yaml 로드
import yaml

with open('config/market_tiers.yaml', 'r') as f:
    market_config = yaml.safe_load(f)

# KIS API mkt_id 매핑
def get_kis_mkt_id(exchange: str, market_tier: str) -> str:
    """
    exchange + market_tier 조합에 대한 KIS API mkt_id 반환

    Args:
        exchange: 'KOSPI', 'KOSDAQ', 'KONEX'
        market_tier: 'MAIN', 'NXT'

    Returns:
        KIS API mkt_id 파라미터 값
    """
    tier_config = market_config['korea']['exchanges'][exchange]['tiers'][market_tier]
    return tier_config['kis_api_code']

# 사용 예
kis_code = get_kis_mkt_id('KOSPI', 'MAIN')  # 'STK'
kis_code = get_kis_mkt_id('KOSPI', 'NXT')   # 'NXT'
kis_code = get_kis_mkt_id('KOSDAQ', 'NXT')  # 'NXT'
```

---

## 6. 데이터 수집 로직 변경

### 6.1 NXT 주식 수집 플로우

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: KIS API 호출 (mkt_id='NXT')                        │
│  → KOSPI NXT + KOSDAQ NXT 통합 목록 반환                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 각 종목별 KRX Data API 조회                        │
│  → market_classification 필드로 KOSPI vs KOSDAQ 구분       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Database 삽입                                       │
│  - exchange: 'KOSPI' 또는 'KOSDAQ'                         │
│  - market_tier: 'NXT'                                      │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 kr_adapter.py 구현 예시

```python
# modules/market_adapters/kr_adapter.py

class KoreaAdapter:
    """Korea market data collector (KOSPI, KOSDAQ, NXT)"""

    SUPPORTED_EXCHANGES = ['KOSPI', 'KOSDAQ', 'KONEX']
    SUPPORTED_MARKET_TIERS = ['MAIN', 'NXT']

    def __init__(self, db_manager, kis_config: Dict):
        self.db = db_manager
        self.kis_stock_api = KISDomesticStockAPI(**kis_config)
        self.krx_api = KRXDataAPI()
        self.stock_parser = StockParser()

    # ========== 메인 시장 수집 ==========
    def collect_main_market_stocks(self) -> int:
        """
        메인 시장 주식 수집 (KOSPI MAIN, KOSDAQ MAIN)

        Returns:
            수집된 주식 수
        """
        total_count = 0

        for exchange in ['KOSPI', 'KOSDAQ']:
            # KRX Data API로 주식 목록 조회
            raw_data = self.krx_api.get_stock_list(exchange=exchange)

            for item in raw_data:
                stock_data = {
                    'ticker': item['ticker'],
                    'name': item['name'],
                    'exchange': exchange,
                    'market_tier': 'MAIN',  # 메인 시장 명시
                    'region': 'KR',
                    'asset_type': 'STOCK',
                }

                self.db.insert_ticker(stock_data)
                total_count += 1

        logger.info(f"✅ 메인 시장 주식 {total_count}개 수집 완료")
        return total_count

    # ========== NXT 시장 수집 ==========
    def collect_nxt_stocks(self) -> int:
        """
        NXT 거래소 주식 수집

        Note:
            KIS API는 KOSPI NXT와 KOSDAQ NXT를 'NXT' 코드로 통합 제공
            KRX Data API로 세부 구분 필요

        Returns:
            수집된 NXT 주식 수
        """
        # Step 1: KIS API로 NXT 전체 목록 조회
        raw_data = self.kis_stock_api.get_stock_list(mkt_id='NXT')

        collected = 0
        for item in raw_data:
            ticker = item['ticker']

            try:
                # Step 2: KRX Data API로 exchange 구분
                krx_info = self.krx_api.get_stock_info(ticker)

                # Step 3: Market classification 파싱
                market_name = krx_info.get('market_name', '')

                if 'KOSPI' in market_name:
                    exchange = 'KOSPI'
                elif 'KOSDAQ' in market_name:
                    exchange = 'KOSDAQ'
                else:
                    logger.warning(f"⚠️ {ticker}: Unknown NXT market ({market_name})")
                    continue

                # Step 4: Database 삽입
                stock_data = {
                    'ticker': ticker,
                    'name': item['name'],
                    'exchange': exchange,
                    'market_tier': 'NXT',  # NXT 시장 명시
                    'region': 'KR',
                    'asset_type': 'STOCK',
                }

                self.db.insert_ticker(stock_data)
                collected += 1

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} NXT 수집 실패: {e}")

        logger.info(f"✅ NXT 주식 {collected}개 수집 완료")
        return collected

    # ========== 전체 수집 ==========
    def collect_all_korean_stocks(self) -> Dict:
        """모든 한국 주식 수집 (메인 + NXT)"""
        results = {
            'main_markets': self.collect_main_market_stocks(),
            'nxt_markets': self.collect_nxt_stocks(),
        }

        logger.info(f"✅ 한국 주식 전체 수집 완료: {sum(results.values())}개")
        return results
```

---

## 7. 마이그레이션 전략

### 7.1 신규 설치 (Fresh Installation)

**방법**: `init_db.py` 실행

```bash
# 데이터베이스 생성 (market_tier 필드 포함)
python init_db.py

# 검증
python init_db.py --verify
```

**결과**:
- `tickers` 테이블에 `market_tier` 컬럼 자동 생성
- 기본값 'MAIN' 적용

### 7.2 기존 데이터베이스 마이그레이션

**방법**: 마이그레이션 스크립트 실행

```bash
# 마이그레이션 실행
python migrations/001_add_market_tier.py

# 검증
python migrations/001_add_market_tier.py --verify-only
```

**마이그레이션 단계**:
1. `tickers` 테이블에 `market_tier TEXT DEFAULT 'MAIN'` 컬럼 추가
2. 기존 모든 레코드에 `market_tier = 'MAIN'` 설정
3. 복합 인덱스 `idx_tickers_exchange_tier` 생성
4. 검증: NULL 값 확인, 인덱스 확인

### 7.3 롤백 (개발/테스트 전용)

```bash
# 마이그레이션 롤백
python migrations/001_add_market_tier.py --rollback
```

**경고**:
- 프로덕션 환경에서는 백업에서 복원하는 것을 권장
- 롤백 시 NXT 관련 데이터 손실 가능

---

## 8. 역호환성 보장

### 8.1 기존 코드 동작 유지

```python
# ===== 기존 쿼리 (market_tier 필터 없음) - 여전히 작동 =====
old_query = "SELECT * FROM tickers WHERE exchange = 'KOSPI'"
# 결과: 코스피 메인 + 코스피 NXT 모두 반환

# ===== 기존 scanner 로직 - 변경 없이 작동 =====
exchanges = ['KOSPI', 'KOSDAQ']
for exchange in exchanges:
    stocks = db.get_stocks(exchange)  # market_tier='MAIN' + 'NXT' 모두 포함
```

### 8.2 기존 데이터 보호

- 모든 기존 레코드는 자동으로 `market_tier='MAIN'` 설정
- NULL 값 발생 불가 (DEFAULT 제약 조건)
- Foreign key 관계 유지 (stock_details, etf_details와의 관계 변경 없음)

### 8.3 점진적 업그레이드

```python
# Phase 1: 마이그레이션만 실행 (코드 변경 없음)
python migrations/001_add_market_tier.py

# Phase 2: NXT 수집 로직 추가 (기존 로직과 병행)
kr_adapter.collect_main_market_stocks()  # 기존 로직
kr_adapter.collect_nxt_stocks()          # 신규 로직

# Phase 3: 쿼리 최적화 (market_tier 필터 추가)
# SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'MAIN'
```

---

## 9. 테스트 계획

### 9.1 단위 테스트

```python
# tests/test_nxt_schema.py

import pytest
from modules.db_manager_sqlite import SQLiteDatabaseManager

def test_market_tier_default_value():
    """market_tier 기본값 테스트"""
    db = SQLiteDatabaseManager('data/test.db')

    # market_tier 없이 삽입
    db.insert_ticker({
        'ticker': 'TEST01',
        'name': 'Test Stock',
        'exchange': 'KOSPI',
        'region': 'KR',
    })

    # 기본값 'MAIN' 확인
    ticker = db.get_ticker('TEST01')
    assert ticker['market_tier'] == 'MAIN'

def test_nxt_stock_insertion():
    """NXT 주식 삽입 테스트"""
    db = SQLiteDatabaseManager('data/test.db')

    # NXT 주식 삽입
    db.insert_ticker({
        'ticker': 'NXT001',
        'name': 'NXT Growth Company',
        'exchange': 'KOSPI',
        'market_tier': 'NXT',
        'region': 'KR',
    })

    # 조회 확인
    ticker = db.get_ticker('NXT001')
    assert ticker['market_tier'] == 'NXT'
    assert ticker['exchange'] == 'KOSPI'

def test_market_tier_query():
    """market_tier 필터 쿼리 테스트"""
    db = SQLiteDatabaseManager('data/test.db')

    # 코스피 NXT만 조회
    nxt_stocks = db.query("""
        SELECT * FROM tickers
        WHERE exchange = 'KOSPI' AND market_tier = 'NXT'
    """)

    assert all(s['market_tier'] == 'NXT' for s in nxt_stocks)
    assert all(s['exchange'] == 'KOSPI' for s in nxt_stocks)
```

### 9.2 통합 테스트

```python
# tests/test_kr_adapter_nxt.py

def test_nxt_stock_collection():
    """NXT 주식 수집 통합 테스트"""
    kr_adapter = KoreaAdapter(db_manager, kis_config)

    # NXT 주식 수집
    collected = kr_adapter.collect_nxt_stocks()

    # 검증
    assert collected > 0

    # Database 확인
    nxt_stocks = db.query("SELECT * FROM tickers WHERE market_tier = 'NXT'")
    assert len(nxt_stocks) == collected
    assert all(s['market_tier'] == 'NXT' for s in nxt_stocks)
```

### 9.3 성능 테스트

```python
# tests/test_performance.py

def test_index_performance():
    """복합 인덱스 성능 테스트"""
    import time

    # 인덱스 없이 쿼리 (시간 측정)
    start = time.time()
    db.query("SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'NXT'")
    no_index_time = time.time() - start

    # 인덱스 생성 후 쿼리
    db.execute("CREATE INDEX idx_test ON tickers(exchange, market_tier)")

    start = time.time()
    db.query("SELECT * FROM tickers WHERE exchange = 'KOSPI' AND market_tier = 'NXT'")
    with_index_time = time.time() - start

    # 인덱스로 성능 향상 확인 (최소 2배 이상)
    assert no_index_time > with_index_time * 2
```

---

## 10. 주의사항 및 제약사항

### 10.1 KIS API 제약

1. **NXT 통합 코드 문제**:
   - KIS API는 KOSPI NXT와 KOSDAQ NXT를 'NXT' 단일 코드로 제공
   - **해결책**: KRX Data API 병행 사용하여 세부 구분

2. **API Rate Limiting**:
   - KIS API: 20 req/sec, 1,000 req/min
   - NXT 주식 수집 시 `time.sleep(0.05)` 필수

### 10.2 데이터 불확실성

1. **NXT 출범 초기 데이터 부족**:
   - 상장 종목 수 적을 수 있음 (예상: ~100-200개)
   - 데이터 품질 검증 필요

2. **Ticker 범위 패턴 미확인**:
   - NXT 종목코드 범위 공식 발표 대기
   - 현재는 KRX Data API 응답 기준으로 판별

### 10.3 거래 규칙 차이

1. **틱 사이즈 (Tick Size)**:
   - NXT 시장의 틱 사이즈가 메인과 다를 수 있음
   - 주문 실행 시 별도 처리 필요 (추후 확인)

2. **거래 시간**:
   - NXT 시장의 거래 시간이 메인과 다를 수 있음
   - 현재는 동일하다고 가정 (09:00-15:30 KST)

3. **유동성 및 변동성**:
   - NXT 시장은 초기 단계로 유동성 낮을 가능성
   - 포지션 사이징 및 리스크 관리 시 별도 고려 필요

### 10.4 향후 확장 고려사항

1. **ETF 상장 가능성**:
   - 향후 NXT 시장에도 ETF 상장 가능
   - `etf_details` 테이블에 `market_tier` 컬럼 추가 검토

2. **글로벌 시장 계층**:
   - 미국, 중국 등 해외 시장도 자체 계층 구조 존재 가능
   - `market_tier`는 한국 전용이 아닌 범용 설계

---

## 11. 참고 자료

### 11.1 관련 파일

- `init_db.py`: 스키마 정의
- `migrations/001_add_market_tier.py`: 마이그레이션 스크립트
- `config/market_tiers.yaml`: 시장 계층 설정 파일
- `modules/market_adapters/kr_adapter.py`: 한국 시장 데이터 수집 어댑터

### 11.2 외부 참조

- [KRX 공식 웹사이트](http://www.krx.co.kr/)
- [KIS API 개발자 포털](https://apiportal.koreainvestment.com/)
- [KRX Data API 문서](http://data.krx.co.kr/)

### 11.3 용어 정리

| 용어 | 설명 |
|------|------|
| **NXT** | Next Exchange - 한국의 제2 거래소 (2024년 출범) |
| **market_tier** | 거래소 내 시장 계층 (MAIN, NXT, KONEX 등) |
| **KOSPI NXT** | 코스피 시장의 NXT 하위 시장 |
| **KOSDAQ NXT** | 코스닥 시장의 NXT 하위 시장 |
| **KONEX** | Korea New Exchange - 중소기업 전용 시장 (2013년 출범) |
| **mkt_id** | KIS API의 시장 구분 파라미터 |
| **excd** | KIS API의 해외 거래소 코드 파라미터 |

---

## 12. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0 | 2024-01-XX | 초안 작성 | Claude |

---

**문서 끝**
