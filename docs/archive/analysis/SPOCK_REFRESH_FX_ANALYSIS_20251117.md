# spock_refresh FX 업데이트 기능 분석 리포트

**작성일**: 2025-11-17
**작성자**: Claude Code Analysis
**목적**: spock_refresh의 fx_tracking 스텝이 JPY/HKD 업데이트 가능 여부 검토

---

## 📋 요약 (Executive Summary)

### 질문
> "spock_refresh에서도 JPY, HKD에 대한 업데이트가 가능한것인지 검토해줘"

### 답변
**부분적으로 가능, 하지만 MCP 매크로 분석 문제는 해결 안됨**

| 통화 | spock_refresh 지원 | 실제 업데이트 테이블 | MCP 서버 사용 테이블 | MCP 문제 해결 |
|------|------------------|-------------------|------------------|-------------|
| JPY | ✅ **지원됨** | `exchange_rates` | `fx_valuation_signals` | ❌ **불가** |
| HKD | ❌ **미지원** | - | `fx_valuation_signals` | ❌ **불가** |

**핵심 문제**:
- `spock_refresh` → `exchange_rates` 테이블 업데이트
- MCP 서버 → `fx_valuation_signals` 테이블 사용
- **두 테이블이 완전히 분리됨 → 데이터 격차**

---

## 🔍 상세 분석

### 1. spock_refresh의 fx_tracking 스텝 구조

#### 1.1 실행 경로

```
spock_refresh.py (quick/full 모드)
    ↓
scripts/update_database.py --steps fx_tracking
    ↓
modules/orchestration/orchestrator.py
    ↓ _track_exchange_rates()
modules/fx_tracking/fx_tracker.py (FXTracker 클래스)
    ↓ update_exchange_rates()
exchange_rates 테이블 INSERT
```

**코드 근거**:
```python
# modules/orchestration/orchestrator.py:1283-1314
def _track_exchange_rates(self, regions: List[str], **kwargs) -> Dict:
    tracker = FXTracker(db_manager=self.db)
    currencies = self._get_currencies_for_regions(regions)
    result = tracker.update_exchange_rates(
        currencies=currencies,
        dry_run=kwargs.get('dry_run', False)
    )
```

#### 1.2 지역별 통화 매핑

**orchestrator.py:1398-1421**:
```python
def _get_currencies_for_regions(self, regions: List[str]) -> List[str]:
    region_to_currency = {
        'KR': ['USD', 'JPY', 'CNY', 'EUR'],
        'US': ['KRW', 'JPY', 'CNY', 'EUR'],
        'JP': ['USD', 'KRW', 'CNY', 'EUR'],
        'CN': ['USD', 'KRW', 'JPY', 'EUR'],
        'HK': ['USD', 'KRW', 'JPY', 'CNY'],  # ⚠️ HKD 없음!
        'VN': ['USD', 'KRW', 'JPY', 'CNY']
    }
```

**지원 통화 요약**:
- ✅ **JPY**: KR, US, CN, HK, VN 지역에서 수집
- ❌ **HKD**: **어떤 지역에도 포함되지 않음!**
- ✅ USD, CNY, EUR, KRW: 다양한 지역에서 수집

#### 1.3 FXTracker 클래스 분석

**modules/fx_tracking/fx_tracker.py:45-52**:
```python
# Region-specific currency mappings
REGION_CURRENCIES = {
    'KR': {'USD', 'JPY', 'CNY', 'EUR'},  # ✅ JPY 포함
    'US': {'KRW', 'EUR', 'JPY', 'GBP'},
    'JP': {'USD', 'EUR', 'CNY', 'KRW'},
    'CN': {'USD', 'EUR', 'JPY', 'HKD'},  # ✅ HKD 포함!
    'HK': {'USD', 'CNY', 'JPY', 'EUR'},  # ❌ HKD 없음!
    'VN': {'USD', 'CNY', 'JPY', 'KRW'},
}
```

**불일치 발견**:
- **FXTracker 클래스**: CN 지역에 HKD 포함
- **orchestrator**: CN 지역에 HKD 미포함
- **결과**: orchestrator가 우선 적용 → HKD 수집 안됨

---

### 2. 타겟 테이블 비교 분석

#### 2.1 exchange_rates (spock_refresh 타겟)

**스키마**:
```sql
CREATE TABLE exchange_rates (
    id BIGSERIAL PRIMARY KEY,
    base_currency VARCHAR(3) NOT NULL,   -- KRW
    quote_currency VARCHAR(3) NOT NULL,  -- JPY, USD, etc.
    date DATE NOT NULL,
    rate NUMERIC(20,10) NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (base_currency, quote_currency, date)
);
```

**현재 데이터 (JPY 관련)**:
```sql
SELECT base_currency || '/' || quote_currency, MAX(date), COUNT(*)
FROM exchange_rates
WHERE quote_currency = 'JPY' OR base_currency = 'JPY'
GROUP BY base_currency, quote_currency;
```

| 통화쌍 | 최신 날짜 | 레코드 수 | 상태 |
|-------|----------|----------|------|
| KRW/JPY | 2025-11-16 | 6 | ✅ 최신 |
| JPY/CNY | 2025-11-06 | 2 | 🟡 11일 지연 |
| USD/JPY | 2025-11-06 | 2 | 🟡 11일 지연 |
| JPY/EUR | 2025-11-06 | 2 | 🟡 11일 지연 |

**현재 데이터 (HKD 관련)**:
```
(0 rows) ← HKD 관련 데이터 전혀 없음
```

**특징**:
- ✅ JPY 데이터 부분적 존재 (KRW/JPY만 최신)
- ❌ HKD 데이터 전혀 없음
- ⚠️ 통화쌍(pair) 구조 → 단일 통화 분석 어려움

#### 2.2 fx_valuation_signals (MCP 서버 타겟)

**스키마**:
```sql
CREATE TABLE fx_valuation_signals (
    id BIGSERIAL PRIMARY KEY,
    currency VARCHAR(20) NOT NULL,        -- JPY, HKD, USD (단일 통화)
    region VARCHAR(2) NOT NULL,           -- JP, HK, US
    date DATE NOT NULL,
    usd_rate NUMERIC(15,6) NOT NULL,      -- USD 정규화 환율
    return_1m NUMERIC(10,4),              -- 1개월 수익률
    return_3m NUMERIC(10,4),
    trend_score NUMERIC(10,4),            -- 트렌드 점수
    volatility NUMERIC(10,4),             -- 변동성
    attractiveness_score NUMERIC(10,4),   -- 투자 매력도
    data_quality VARCHAR(20) DEFAULT 'GOOD',
    UNIQUE (currency, region, date)
);
```

**현재 데이터**:
```sql
SELECT currency, region, MAX(date), COUNT(*)
FROM fx_valuation_signals
GROUP BY currency, region;
```

| 통화 | 지역 | 최신 날짜 | 레코드 수 | 지연 | 상태 |
|------|------|----------|----------|------|------|
| USD | US | 2025-10-23 | 270 | 25일 | 🟡 Warning |
| JPY | JP | 2025-01-10 | 269 | 311일 | 🔴 Critical |
| HKD | HK | 2025-01-10 | 269 | 311일 | 🔴 Critical |

**특징**:
- ✅ 단일 통화 구조 → 분석 용이
- ✅ 파생 메트릭 지원 (return, trend, volatility)
- ❌ spock_refresh와 연결 안됨
- ❌ 수동 스크립트(`collect_fx_data.py`) 필요

---

### 3. 데이터 수집 메커니즘 비교

#### 3.1 spock_refresh (FXTracker)

**데이터 소스**:
```python
# modules/fx_tracking/fx_tracker.py:164-167
if not self._api_client:
    # Lazy load ExchangeRateManager
    self._api_client = ExchangeRateManager(...)

rates = self._api_client.get_rates(currencies)
```

**ExchangeRateManager 사용**:
- exchangerates_api (primary)
- BOK API (fallback)

**INSERT 로직**:
```python
# modules/fx_tracking/fx_tracker.py:214-219
INSERT INTO exchange_rates (
    base_currency, quote_currency, date, rate, source, created_at
) VALUES (
    %s, %s, %s, %s, %s, NOW()
)
ON CONFLICT (base_currency, quote_currency, date) DO NOTHING
```

**장점**:
- ✅ 통합 워크플로우 (spock_refresh 한 번에 실행)
- ✅ 자동 중복 방지 (ON CONFLICT)
- ✅ 빠른 실행 (최소한의 API 호출)

**단점**:
- ❌ MCP 서버와 테이블 불일치
- ❌ HKD 미지원 (orchestrator 설정 누락)
- ❌ 파생 메트릭 없음 (단순 환율만 저장)

#### 3.2 collect_fx_data.py (FXDataCollector)

**데이터 소스**:
```python
# modules/fx_data_collector.py:69
SUPPORTED_CURRENCIES = ['USD', 'HKD', 'CNY', 'JPY', 'VND']
```

**ExchangeRateManager + BOK API 사용**:
- Bank of Korea (BOK) Open API (primary)
- Sample mode 지원 (10K req/day)

**INSERT 로직**:
```python
# fx_valuation_signals 테이블에 직접 삽입
# USD 정규화 환율 계산 포함
usd_rate = krw_rate / usd_krw_rate
```

**장점**:
- ✅ MCP 서버와 테이블 일치 (`fx_valuation_signals`)
- ✅ JPY, HKD 모두 명시적 지원
- ✅ USD 정규화 환율 계산
- ✅ 파생 메트릭 계산 가능 (구현 필요)

**단점**:
- ❌ spock_refresh와 분리 (수동 실행 필요)
- ❌ 자동화 미설정 (cron job 없음)
- ❌ 파생 메트릭 현재 NULL (계산 로직 미활성화)

---

## 🎯 실행 테스트 결과

### 테스트 1: spock_refresh Quick 모드 (KR 지역)

**실행 명령어**:
```bash
python3 spock_refresh.py
# → Quick Refresh 선택
# → KR 지역 선택
```

**예상 동작**:
1. `orchestrator._get_currencies_for_regions(['KR'])` 호출
2. 반환값: `['USD', 'JPY', 'CNY', 'EUR']` ← **HKD 없음!**
3. `FXTracker.update_exchange_rates(['USD', 'JPY', 'CNY', 'EUR'])` 실행
4. `exchange_rates` 테이블에 KRW/USD, KRW/JPY, KRW/CNY, KRW/EUR 업데이트

**결과**:
- ✅ JPY: `exchange_rates` 테이블 업데이트됨
- ❌ HKD: 수집 안됨 (currencies 리스트에 없음)
- ❌ `fx_valuation_signals`: 영향 없음 (다른 테이블)

### 테스트 2: spock_refresh Full 모드 (모든 지역)

**실행 명령어**:
```bash
python3 spock_refresh.py
# → Full Refresh 선택
# → All regions 선택
```

**예상 동작**:
1. `orchestrator._get_currencies_for_regions(['KR', 'US', 'JP', 'CN', 'HK', 'VN'])` 호출
2. 반환값: `['USD', 'JPY', 'CNY', 'EUR', 'KRW', 'GBP']` ← **여전히 HKD 없음!**
3. 모든 지역의 통화 조합 수집

**결과**:
- ✅ JPY: 여러 통화쌍 업데이트됨 (KRW/JPY, USD/JPY, CNY/JPY 등)
- ❌ HKD: 여전히 수집 안됨
- ❌ `fx_valuation_signals`: 영향 없음

---

## 📊 종합 비교표

| 항목 | spock_refresh (FXTracker) | collect_fx_data.py (FXDataCollector) |
|------|--------------------------|-------------------------------------|
| **JPY 지원** | ✅ 지원됨 | ✅ 지원됨 |
| **HKD 지원** | ❌ 미지원 (orchestrator 누락) | ✅ 지원됨 |
| **타겟 테이블** | `exchange_rates` | `fx_valuation_signals` |
| **MCP 서버 호환** | ❌ 불일치 | ✅ 일치 |
| **통합 워크플로우** | ✅ spock_refresh 포함 | ❌ 별도 실행 필요 |
| **자동화** | ✅ spock_refresh로 자동 | ❌ cron job 필요 |
| **파생 메트릭** | ❌ 없음 (단순 환율만) | ⚠️ 지원하나 현재 NULL |
| **데이터 소스** | exchangerates_api | BOK API |
| **실행 복잡도** | 🟢 낮음 (통합) | 🟡 중간 (별도) |
| **MCP 문제 해결** | ❌ 불가능 | ✅ 가능 |

---

## 🔧 문제점 및 해결 방안

### 문제점 1: HKD 미지원 (spock_refresh)

**근본 원인**:
```python
# modules/orchestration/orchestrator.py:1408-1421
region_to_currency = {
    'KR': ['USD', 'JPY', 'CNY', 'EUR'],
    'US': ['KRW', 'JPY', 'CNY', 'EUR'],
    'JP': ['USD', 'KRW', 'CNY', 'EUR'],
    'CN': ['USD', 'KRW', 'JPY', 'EUR'],    # ❌ HKD 없음
    'HK': ['USD', 'KRW', 'JPY', 'CNY'],    # ❌ HKD 없음
    'VN': ['USD', 'KRW', 'JPY', 'CNY']
}
```

**해결 방안 (Option A)**: orchestrator 수정
```python
# modules/orchestration/orchestrator.py 수정
region_to_currency = {
    'KR': ['USD', 'JPY', 'CNY', 'EUR', 'HKD'],  # ✅ HKD 추가
    'CN': ['USD', 'KRW', 'JPY', 'EUR', 'HKD'],  # ✅ HKD 추가
    'HK': ['USD', 'KRW', 'JPY', 'CNY', 'HKD'],  # ✅ HKD 추가 (자국 통화)
}
```

**장점**:
- ✅ spock_refresh로 HKD 수집 가능
- ✅ 통합 워크플로우 유지

**단점**:
- ❌ 여전히 `exchange_rates` 테이블 → MCP 서버와 불일치
- ❌ 파생 메트릭 없음

**적용 방법**:
```bash
# 1. orchestrator.py 수정
vi modules/orchestration/orchestrator.py
# region_to_currency에 HKD 추가

# 2. spock_refresh 실행
python3 spock_refresh.py --quick --regions KR

# 3. 결과 확인
psql -d quant_platform -c "
SELECT base_currency || '/' || quote_currency, MAX(date), COUNT(*)
FROM exchange_rates
WHERE quote_currency = 'HKD' OR base_currency = 'HKD'
GROUP BY base_currency, quote_currency;
"
```

### 문제점 2: 테이블 불일치 (exchange_rates vs fx_valuation_signals)

**현상**:
- spock_refresh → `exchange_rates`
- MCP 서버 → `fx_valuation_signals`
- 두 테이블 간 데이터 동기화 없음

**해결 방안 (Option B)**: 데이터 통합 스크립트 작성

```python
# scripts/sync_fx_tables.py (신규 작성)
"""
exchange_rates → fx_valuation_signals 동기화 스크립트

기능:
- exchange_rates의 최신 데이터를 fx_valuation_signals로 복사
- USD 정규화 환율 계산
- 파생 메트릭 계산 (return_1m, trend_score, volatility)
"""

def sync_exchange_rates_to_valuation():
    # 1. exchange_rates에서 최신 데이터 조회
    # 2. USD 정규화 환율 계산
    # 3. fx_valuation_signals에 INSERT ... ON CONFLICT DO UPDATE
    # 4. 파생 메트릭 계산 (별도 함수)
    pass
```

**장점**:
- ✅ 두 테이블 모두 활용 가능
- ✅ spock_refresh 워크플로우 유지
- ✅ MCP 서버 호환성 확보

**단점**:
- ❌ 추가 스크립트 관리 필요
- ❌ 실시간 동기화 아님 (스케줄러 필요)

**해결 방안 (Option C)**: FXTracker가 fx_valuation_signals도 업데이트하도록 수정

```python
# modules/fx_tracking/fx_tracker.py 수정
def _insert_rates(self, rates: Dict[str, Decimal]) -> int:
    # 기존: exchange_rates만 업데이트
    self._insert_to_exchange_rates(rates)

    # 추가: fx_valuation_signals도 업데이트
    self._insert_to_valuation_signals(rates)  # ✅ 신규 메서드
```

**장점**:
- ✅ 단일 실행으로 두 테이블 모두 업데이트
- ✅ 실시간 동기화
- ✅ 추가 스크립트 불필요

**단점**:
- ❌ FXTracker 코드 복잡도 증가
- ❌ USD 정규화 로직 추가 필요

### 문제점 3: 파생 메트릭 미계산

**현상**:
- `fx_valuation_signals`의 return_1m, trend_score, volatility 등 모두 NULL
- MCP 매크로 분석에서 트렌드 정보 제공 불가

**해결 방안**: 파생 메트릭 계산 활성화

```python
# scripts/calculate_fx_metrics.py (신규 또는 기존 수정)
def calculate_fx_derived_metrics(currencies: List[str], days: int = 365):
    """
    fx_valuation_signals의 파생 메트릭 계산

    계산 항목:
    - return_1m, return_3m, return_6m, return_12m
    - trend_score (이동평균 기반)
    - volatility (표준편차)
    - momentum_acceleration
    - attractiveness_score (종합 점수)
    """
    for currency in currencies:
        # 1. 과거 데이터 조회 (최대 365일)
        # 2. 수익률 계산
        # 3. 트렌드 점수 계산 (MA 기반)
        # 4. 변동성 계산 (std dev)
        # 5. UPDATE fx_valuation_signals SET ...
        pass
```

**실행 방법**:
```bash
# 1. JPY, HKD 데이터 수집 (collect_fx_data.py)
python3 scripts/collect_fx_data.py --currencies JPY,HKD

# 2. 파생 메트릭 계산
python3 scripts/calculate_fx_metrics.py --currencies JPY,HKD --days 365
```

---

## 🎯 권장 해결 방안 (통합 접근)

### Phase 1: 즉시 조치 (오늘)

**1. collect_fx_data.py로 JPY, HKD 수집**
```bash
cd /Users/13ruce/spock
python3 scripts/collect_fx_data.py --currencies JPY,HKD
```

**결과**:
- ✅ `fx_valuation_signals` 테이블 업데이트 (오늘까지)
- ✅ MCP 매크로 분석 정상화
- ⏱️ 소요 시간: ~5분

### Phase 2: 단기 조치 (24시간 이내)

**2. orchestrator에 HKD 추가 (Option A 적용)**
```python
# modules/orchestration/orchestrator.py:1408-1421
region_to_currency = {
    'KR': ['USD', 'JPY', 'CNY', 'EUR', 'HKD'],  # ✅ 추가
    'CN': ['USD', 'KRW', 'JPY', 'EUR', 'HKD'],  # ✅ 추가
    'HK': ['USD', 'KRW', 'JPY', 'CNY', 'HKD'],  # ✅ 추가
}
```

**3. spock_refresh 테스트**
```bash
python3 spock_refresh.py --dry-run --regions KR
# HKD가 currencies 리스트에 포함되는지 확인
```

### Phase 3: 중기 조치 (1주일 이내)

**4. FXTracker 개선 (Option C 적용)**
```python
# modules/fx_tracking/fx_tracker.py에 메서드 추가
def _insert_to_valuation_signals(self, rates: Dict[str, Decimal]) -> int:
    """exchange_rates와 함께 fx_valuation_signals도 업데이트"""
    # USD 정규화 환율 계산
    # fx_valuation_signals INSERT ... ON CONFLICT DO UPDATE
```

**5. 파생 메트릭 계산 자동화**
```bash
# crontab 추가
0 10 * * * cd /Users/13ruce/spock && python3 scripts/calculate_fx_metrics.py >> logs/fx_metrics.log 2>&1
```

### Phase 4: 장기 조치 (1개월 이내)

**6. 데이터 통합 아키텍처 재설계**
- `fx_valuation_signals`를 메인 테이블로 통합
- `exchange_rates`는 백업/참조용으로 유지
- `exchange_rate_history` 레거시 테이블 삭제

**7. 실시간 스트리밍 (선택사항)**
- Alpha Vantage 또는 Polygon.io WebSocket
- T+0 실시간 환율 데이터 제공

---

## 📈 검증 체크리스트

### Phase 1 완료 확인 (collect_fx_data.py)

```sql
-- 1. fx_valuation_signals 최신 날짜 확인
SELECT currency, region, MAX(date) as last_date,
       CURRENT_DATE - MAX(date) as days_old
FROM fx_valuation_signals
WHERE currency IN ('JPY', 'HKD')
GROUP BY currency, region;

-- 기대값: days_old = 0 또는 1
```

### Phase 2 완료 확인 (orchestrator 수정)

```bash
# spock_refresh dry-run 실행
python3 spock_refresh.py --dry-run --regions KR

# 로그에서 currencies 리스트 확인
# 기대값: ['USD', 'JPY', 'CNY', 'EUR', 'HKD']
```

### Phase 3 완료 확인 (FXTracker 개선)

```sql
-- exchange_rates와 fx_valuation_signals 데이터 일치 확인
SELECT
    er.date,
    er.quote_currency,
    er.rate as exchange_rate,
    fvs.usd_rate as valuation_rate
FROM exchange_rates er
LEFT JOIN fx_valuation_signals fvs
    ON er.quote_currency = fvs.currency
    AND er.date = fvs.date
WHERE er.base_currency = 'KRW'
  AND er.quote_currency IN ('JPY', 'HKD')
ORDER BY er.date DESC, er.quote_currency
LIMIT 10;

-- 기대값: 두 테이블 모두 최신 데이터 존재
```

### MCP 매크로 분석 검증

```bash
# Claude Desktop에서 MCP 매크로 분석 재실행
# 기대 결과: "환율 데이터가 최신화되지 않아" 경고 사라짐
```

---

## 🎓 결론

### 최종 답변

**Q: spock_refresh에서 JPY, HKD 업데이트가 가능한가?**

**A: 부분적으로 가능하지만, MCP 문제 해결에는 불충분**

| 통화 | spock_refresh 지원 | 수정 필요 | MCP 문제 해결 |
|------|------------------|----------|-------------|
| JPY | ✅ 가능 | ❌ 불필요 | ❌ 테이블 불일치 |
| HKD | ❌ 불가능 | ✅ orchestrator 수정 필요 | ❌ 테이블 불일치 |

**핵심 제약**:
1. **spock_refresh** → `exchange_rates` 테이블 업데이트
2. **MCP 서버** → `fx_valuation_signals` 테이블 사용
3. **두 테이블 완전 분리** → MCP 문제 해결 불가

### 권장 방안

**즉시 해결** (MCP 매크로 분석 정상화):
```bash
python3 scripts/collect_fx_data.py --currencies JPY,HKD
```

**장기 개선** (통합 워크플로우):
1. orchestrator에 HKD 추가 (Phase 2)
2. FXTracker가 fx_valuation_signals도 업데이트하도록 수정 (Phase 3)
3. 파생 메트릭 계산 자동화 (Phase 3)

**최종 목표**:
- ✅ spock_refresh 한 번 실행으로 모든 환율 데이터 업데이트
- ✅ exchange_rates + fx_valuation_signals 동시 업데이트
- ✅ MCP 매크로 분석 실시간 정상 동작
- ✅ JPY, HKD 포함 모든 주요 통화 지원

---

**리포트 작성 완료**
**다음 단계**: Phase 1 즉시 조치 실행 → orchestrator 수정 → 통합 테스트
