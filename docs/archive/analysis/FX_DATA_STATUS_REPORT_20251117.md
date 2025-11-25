# 환율 데이터 현황 점검 리포트

**작성일**: 2025-11-17
**작성자**: Claude Code Analysis
**목적**: MCP 매크로 분석에서 보고된 JPY/HKD 데이터 최신화 문제 조사

---

## 📋 요약 (Executive Summary)

**MCP 서버 매크로 분석 결과**:
> "💱 통화 시장: 환율 데이터가 최신화되지 않아 (JPY, HKD는 1월 데이터) 현재 트렌드 분석이 제한적입니다."

**근본 원인**:
- **JPY, HKD 데이터**: 2025-01-10 이후 업데이트 중단 (**311일 지연**)
- **USD 데이터**: 2025-10-23까지 업데이트됨 (25일 지연)
- **원인**: FX 데이터 수집 스크립트(`collect_fx_data.py`) 미실행

**영향도**:
- 🔴 **Critical**: MCP 매크로 분석 신뢰도 심각 저하
- 🔴 **Critical**: JPY, HKD 기반 투자 의사결정 불가
- 🟡 **Medium**: USD 기반 분석은 부분적 가능 (25일 지연)

---

## 🔍 상세 조사 결과

### 1. 데이터베이스 테이블 현황

시스템에는 **3개의 환율 관련 테이블**이 존재:

| 테이블명 | 용도 | 데이터 소스 | MCP 사용 여부 |
|---------|------|------------|-------------|
| `exchange_rates` | 통화쌍 환율 데이터 | exchangerates_api | ❌ No |
| `exchange_rate_history` | 레거시 환율 히스토리 | BOK_API | ❌ No |
| `fx_valuation_signals` | FX 평가 신호 (매크로 분석용) | BOK_API (via FXDataCollector) | ✅ **Yes** |

**MCP 서버는 `fx_valuation_signals` 테이블을 사용**하여 매크로 분석 수행
- 경로: `mcp_server/adapters/macro_adapter.py` → `MacroAdapter._get_currencies()`
- 쿼리: `fx_valuation_signals` WHERE `data_quality = 'GOOD'`

---

### 2. fx_valuation_signals 테이블 상태 분석

#### 2.1 최신 데이터 날짜

| 통화 | 지역 | 최신 날짜 | 지연 일수 | 레코드 수 | 상태 |
|------|------|----------|----------|----------|------|
| USD | US | **2025-10-23** | 25일 | 270 | 🟡 Warning |
| JPY | JP | **2025-01-10** | **311일** | 269 | 🔴 Critical |
| HKD | HK | **2025-01-10** | **311일** | 269 | 🔴 Critical |

#### 2.2 JPY/HKD 최신 데이터 상세

```sql
SELECT currency, date, usd_rate, return_1m, trend_score, volatility, attractiveness_score
FROM fx_valuation_signals
WHERE currency IN ('JPY', 'HKD')
ORDER BY currency, date DESC LIMIT 3;
```

**결과**:
- **날짜**: 2025-01-10 (최신)
- **usd_rate**: 0.144089 (HKD), 0.007307 (JPY)
- **파생 메트릭**: `return_1m`, `trend_score`, `volatility`, `attractiveness_score` **모두 NULL**
- **data_quality**: `GOOD`
- **updated_at**: 2025-11-12 10:46:43 (백필 작업 시 업데이트됨)

**해석**:
- ✅ 2024년 데이터는 백필 완료 (2025-11-12에 실행)
- ❌ 2025년 1월 이후 신규 데이터 수집 중단
- ❌ 파생 메트릭 미계산 (return, trend, volatility 등)

---

### 3. exchange_rates 테이블 비교 분석

`exchange_rates` 테이블은 더 최신 데이터 보유:

| 통화쌍 | 최신 날짜 | 지연 | 소스 | 레코드 수 |
|-------|----------|------|------|----------|
| KRW/JPY | 2025-11-16 | 1일 | exchangerates_api | 6 |
| KRW/CNY | 2025-11-16 | 1일 | exchangerates_api | 6 |
| KRW/USD | 2025-11-16 | 1일 | exchangerates_api | 6 |
| KRW/EUR | 2025-11-16 | 1일 | exchangerates_api | 5 |
| JPY/USD | 2025-11-06 | 11일 | exchangerates_api | 2 |
| USD/JPY | 2025-11-06 | 11일 | exchangerates_api | 2 |

**주요 발견**:
- ✅ **KRW 기준 통화쌍**: 최신 상태 (11/16, 1일 지연)
- ⚠️ **JPY/USD 단독 쌍**: 11일 지연 (11/06)
- ❌ **HKD 관련 데이터**: 존재하지 않음

**문제점**:
- MCP 서버는 이 테이블을 사용하지 않음
- 데이터 형식 불일치 (통화쌍 vs 단일 통화)
- 파생 메트릭 부재 (trend_score, volatility 등)

---

### 4. exchange_rate_history 테이블 (레거시)

| 통화 | 최신 날짜 | 지연 | 소스 | 레코드 수 |
|------|----------|------|------|----------|
| USD | 2025-10-16 | 32일 | BOK_API | 1 |
| JPY | 2025-10-16 | 32일 | BOK_API | 1 |
| HKD | 2025-10-16 | 32일 | BOK_API | 1 |
| CNY | 2025-10-16 | 32일 | BOK_API | 1 |
| VND | 2025-10-16 | 32일 | BOK_API | 1 |

**상태**: 모두 동일하게 10월 16일 이후 업데이트 중단 (32일 지연)

---

## 🔧 근본 원인 분석

### FXDataCollector 설정

**스크립트**: `modules/fx_data_collector.py`
- **지원 통화**: `['USD', 'HKD', 'CNY', 'JPY', 'VND']` ✅ JPY, HKD 포함
- **데이터 소스**: Bank of Korea (BOK) Open API
- **타겟 테이블**: `fx_valuation_signals`
- **지역 매핑**:
  - USD → US
  - HKD → HK
  - JPY → JP
  - CNY → CN
  - VND → VN

**실행 스크립트**: `scripts/collect_fx_data.py`
```bash
# 기본 실행 (전체 통화)
python3 scripts/collect_fx_data.py

# 특정 통화만
python3 scripts/collect_fx_data.py --currencies USD,CNY,JPY

# Dry run
python3 scripts/collect_fx_data.py --dry-run
```

### 문제점 식별

1. **스크립트 미실행**
   - `log/fx_collection_*.log` 파일 없음
   - cron job 또는 수동 실행 기록 없음
   - 마지막 실행일: 추정 2025-01-10 (JPY/HKD 최신 날짜)

2. **자동화 설정 부재**
   - crontab 설정 확인 필요
   - systemd timer 설정 확인 필요
   - 스케줄러 등록 여부 확인 필요

3. **USD만 부분 업데이트**
   - USD는 2025-10-23까지 업데이트됨 (25일 전)
   - 다른 경로로 USD 데이터가 수집되었을 가능성
   - 백필 스크립트 또는 별도 프로세스 추정

---

## 📊 영향도 분석

### MCP 매크로 분석 기능 영향

**MacroAdapter.analyze_macro_environment()** 메서드:

```python
# mcp_server/adapters/macro_adapter.py:243-327
async def _get_currencies(self, analysis_date, start_date, regions):
    """fx_valuation_signals에서 통화 평가 데이터 조회"""
    query = """
        SELECT currency, region, date, usd_rate, trend_score, volatility,
               attractiveness_score, data_quality, ...
        FROM fx_valuation_signals
        WHERE date <= %s AND region = ANY(%s) AND data_quality = 'GOOD'
    """
```

**영향받는 메트릭**:
1. ❌ **latest_rate**: JPY/HKD는 311일 전 데이터 (신뢰도 0%)
2. ❌ **change_1d**: 계산 불가능 (최신 데이터 없음)
3. ❌ **change_1w**: 계산 불가능
4. ❌ **change_1m**: 계산 불가능
5. ❌ **trend_score**: NULL (계산 안됨)
6. ❌ **volatility**: NULL (계산 안됨)
7. ❌ **attractiveness_score**: NULL (계산 안됨)

**시장 레짐 분류 영향**:
- `_analyze_regime()` 메서드는 통화 트렌드 활용
- JPY/HKD 데이터 누락으로 Risk-On/Off 판단 왜곡
- 안전 자산 흐름(JPY) 분석 불가

---

## 🛠️ 해결 방안

### 즉시 조치 (Immediate Actions)

#### 1. 수동 FX 데이터 수집 (지금 바로)
```bash
# 1. 현재 디렉토리 확인
cd /Users/13ruce/spock

# 2. 환경변수 로드
source .env  # BOK_API_KEY 필요

# 3. 전체 통화 수집 (Dry run으로 먼저 테스트)
python3 scripts/collect_fx_data.py --dry-run

# 4. 실제 수집 실행
python3 scripts/collect_fx_data.py

# 5. 결과 확인
psql -d quant_platform -c "
SELECT currency, region, MAX(date) as last_date, COUNT(*) as records
FROM fx_valuation_signals
GROUP BY currency, region
ORDER BY last_date DESC;
"
```

**예상 결과**:
- JPY, HKD 데이터가 오늘 날짜(2025-11-17)까지 업데이트
- 지연 일수: 311일 → 0일

#### 2. 백필 (Historical Data Backfill)

JPY/HKD의 2025-01-11 ~ 2025-11-16 데이터 백필:

```bash
# 백필 스크립트 확인
ls -lh scripts/*backfill*fx*

# yfinance 백필 스크립트 사용 (존재 시)
python3 scripts/yfinance_fx_backfill.py \
  --currencies JPY,HKD \
  --start-date 2025-01-11 \
  --end-date 2025-11-16

# 또는 collect_fx_data.py로 날짜 범위 수집
# (코드 수정 필요: date range 파라미터 추가)
```

**목표**:
- 311일 데이터 갭 완전 복구
- return_1m, trend_score 등 파생 메트릭 계산

---

### 단기 조치 (Short-term Actions, 24시간 이내)

#### 3. cron Job 자동화 설정

```bash
# crontab 편집
crontab -e

# 매일 오전 9시 FX 데이터 수집 (한국시장 개장 후)
0 9 * * * cd /Users/13ruce/spock && /usr/local/bin/python3 scripts/collect_fx_data.py >> log/fx_collection_$(date +\%Y\%m\%d).log 2>&1

# cron 설정 확인
crontab -l
```

**대안 (systemd timer)**:
```bash
# /etc/systemd/system/fx-collection.service
[Unit]
Description=Daily FX Data Collection
After=network.target

[Service]
Type=oneshot
User=13ruce
WorkingDirectory=/Users/13ruce/spock
ExecStart=/usr/local/bin/python3 scripts/collect_fx_data.py
StandardOutput=append:/Users/13ruce/spock/log/fx_collection.log
StandardError=append:/Users/13ruce/spock/log/fx_collection_error.log

# /etc/systemd/system/fx-collection.timer
[Unit]
Description=Daily FX Collection Timer

[Timer]
OnCalendar=daily
OnCalendar=09:00
Persistent=true

[Install]
WantedBy=timers.target

# 활성화
sudo systemctl enable fx-collection.timer
sudo systemctl start fx-collection.timer
sudo systemctl status fx-collection.timer
```

#### 4. 모니터링 및 알림 설정

**Prometheus 알림 규칙 추가**:
```yaml
# prometheus/alerts/fx_data_freshness.yml
groups:
  - name: fx_data_quality
    interval: 1h
    rules:
      - alert: FXDataStale
        expr: |
          (time() - fx_valuation_signals_last_update_timestamp) > 86400 * 2
        for: 1h
        labels:
          severity: warning
          component: fx_data_collector
        annotations:
          summary: "FX data is stale ({{ $labels.currency }})"
          description: "{{ $labels.currency }} FX data has not been updated for >2 days"

      - alert: FXDataCriticallyStale
        expr: |
          (time() - fx_valuation_signals_last_update_timestamp) > 86400 * 7
        for: 1h
        labels:
          severity: critical
          component: fx_data_collector
        annotations:
          summary: "FX data critically stale ({{ $labels.currency }})"
          description: "{{ $labels.currency }} FX data has not been updated for >7 days. MCP analysis unreliable."
```

**데이터 신선도 Gauge 메트릭 추가**:
```python
# modules/fx_data_collector.py에 추가
if HAS_PROMETHEUS:
    data_last_update = Gauge(
        'fx_valuation_signals_last_update_timestamp',
        'Last update timestamp for FX valuation signals',
        ['currency']
    )

    # 수집 성공 시 업데이트
    data_last_update.labels(currency=currency).set(datetime.now().timestamp())
```

---

### 중기 조치 (Medium-term Actions, 1주일 이내)

#### 5. 데이터 통합 및 정리

현재 **3개 환율 테이블** 존재 → **단일화 필요**:

**추천 아키텍처**:
```
fx_valuation_signals (Main Table)
├── 소스: BOK API (기본) + exchangerates_api (백업)
├── 업데이트: 일일 자동 수집
├── 파생 메트릭: return, trend, volatility, attractiveness
└── MCP 매크로 분석용

exchange_rates (Backup/Reference)
└── 실시간 환율 조회용 (API 직접 호출)

exchange_rate_history (Deprecated)
└── 레거시, 마이그레이션 후 삭제 예정
```

**마이그레이션 계획**:
1. `exchange_rates`의 최신 데이터를 `fx_valuation_signals`로 이관
2. `exchange_rate_history` 데이터 아카이브 후 테이블 삭제
3. FXDataCollector를 exchangerates_api 백업 소스로 확장

#### 6. 데이터 품질 개선

**파생 메트릭 계산 활성화**:
- `return_1m`, `return_3m`, `return_6m`, `return_12m`
- `trend_score` (이동평균 기반 트렌드 점수)
- `volatility` (표준편차)
- `momentum_acceleration` (모멘텀 가속도)
- `attractiveness_score` (종합 투자 매력도)

**현재 상태**: 모두 NULL → 계산 로직 활성화 필요

**구현 방안**:
```python
# modules/fx_data_collector.py의 _calculate_derived_metrics() 활성화
# 또는 별도 스크립트로 배치 계산
python3 scripts/calculate_fx_metrics.py --currencies JPY,HKD --days 365
```

---

### 장기 조치 (Long-term Actions, 1개월 이내)

#### 7. 멀티 소스 통합 (Resilience)

**목표**: BOK API 장애 시 자동 폴백

```python
# modules/fx_data_collector.py 개선
class FXDataCollector:
    SOURCES = [
        {'name': 'BOK_API', 'priority': 1, 'reliability': 0.95},
        {'name': 'exchangerates_api', 'priority': 2, 'reliability': 0.99},
        {'name': 'yfinance', 'priority': 3, 'reliability': 0.90}
    ]

    def collect_with_fallback(self, currency, date):
        for source in sorted(self.SOURCES, key=lambda x: x['priority']):
            try:
                data = self._fetch_from_source(source['name'], currency, date)
                if data:
                    return data
            except Exception as e:
                logger.warning(f"{source['name']} failed: {e}")
                continue
        raise DataCollectionError(f"All sources failed for {currency}")
```

#### 8. 실시간 데이터 스트림 (선택사항)

**현재**: 일일 배치 수집 (T+1 데이터)
**개선**: 실시간 스트리밍 (T+0 데이터)

**구현 옵션**:
- Alpha Vantage FX API (실시간 환율)
- Polygon.io Forex WebSocket
- Interactive Brokers API (실시간 FX 가격)

---

## 📈 검증 체크리스트

수집 스크립트 실행 후 아래 확인:

### 1. 데이터 신선도 검증
```sql
-- 모든 통화의 최신 날짜 확인
SELECT
    currency,
    region,
    MAX(date) as last_date,
    CURRENT_DATE - MAX(date) as days_old,
    COUNT(*) as total_records
FROM fx_valuation_signals
GROUP BY currency, region
ORDER BY last_date DESC;

-- ✅ 기대값: JPY, HKD 모두 days_old = 0 또는 1
```

### 2. 파생 메트릭 계산 검증
```sql
-- 최신 데이터의 파생 메트릭 확인
SELECT
    currency,
    date,
    usd_rate,
    return_1m,
    trend_score,
    volatility,
    attractiveness_score
FROM fx_valuation_signals
WHERE date = (SELECT MAX(date) FROM fx_valuation_signals)
ORDER BY currency;

-- ✅ 기대값: return_1m, trend_score 등이 NULL이 아닌 실제 값
```

### 3. MCP 매크로 분석 기능 검증
```bash
# MCP 서버로 매크로 환경 분석 재실행
# (Claude Desktop 또는 MCP CLI 사용)

# 예상 결과:
# - JPY: latest_date = 2025-11-17, change_1m 계산됨
# - HKD: latest_date = 2025-11-17, change_1m 계산됨
# - "환율 데이터가 최신화되지 않아" 경고 사라짐
```

### 4. 자동화 검증
```bash
# cron job 다음 실행 예정 확인
grep -i fx /var/log/cron.log  # Linux
log show --predicate 'eventMessage contains "fx"' --last 1h  # macOS

# 로그 파일 생성 확인
ls -lh log/fx_collection_*.log

# 최근 로그 내용 확인
tail -50 log/fx_collection_$(date +%Y%m%d).log
```

---

## 🎯 성공 기준

### 즉시 조치 완료 기준
- ✅ JPY, HKD 최신 날짜 = 오늘 (2025-11-17)
- ✅ 지연 일수: 311일 → 0일
- ✅ return_1m, trend_score 등 파생 메트릭 계산됨
- ✅ MCP 매크로 분석에서 경고 메시지 사라짐

### 단기 조치 완료 기준
- ✅ cron job 설정 완료 및 동작 확인
- ✅ 내일(11/18) 자동 수집 성공 로그 생성
- ✅ Prometheus 알림 설정 완료

### 중장기 조치 완료 기준
- ✅ 데이터 통합 완료 (1개 메인 테이블)
- ✅ 멀티 소스 폴백 로직 구현
- ✅ 파생 메트릭 자동 계산 활성화

---

## 📎 참고 자료

### 관련 파일
- **MCP 서버**: `mcp_server/adapters/macro_adapter.py`
- **데이터 수집**: `modules/fx_data_collector.py`
- **실행 스크립트**: `scripts/collect_fx_data.py`
- **백필 스크립트**: `scripts/yfinance_fx_backfill.py`
- **스키마**: `scripts/init_postgres_schema.py` (fx_valuation_signals 정의)

### 데이터베이스 스키마
```sql
-- fx_valuation_signals 테이블 구조
\d fx_valuation_signals

-- 주요 컬럼:
-- - currency, region, date (PK)
-- - usd_rate (USD 정규화 환율)
-- - return_1m, return_3m, return_6m, return_12m (수익률)
-- - trend_score, volatility, attractiveness_score (파생 메트릭)
-- - data_quality (GOOD/PARTIAL/POOR/MISSING)
```

### API 문서
- **BOK Open API**: https://ecos.bok.or.kr/api/
- **exchangerates.host API**: https://exchangerates.host/
- **yfinance**: https://pypi.org/project/yfinance/

---

## 🚨 즉시 실행 권장 명령어

```bash
# 1. 현재 디렉토리 확인
cd /Users/13ruce/spock

# 2. 가상환경 활성화 (필요시)
# source venv/bin/activate

# 3. 환경변수 확인
echo $BOK_API_KEY  # 설정 안되어있으면 .env 파일에서 로드

# 4. Dry run으로 테스트
python3 scripts/collect_fx_data.py --dry-run

# 5. 실제 수집 (JPY, HKD 포함)
python3 scripts/collect_fx_data.py

# 6. 결과 즉시 확인
psql -d quant_platform -c "
SELECT currency, region, MAX(date) as last_date,
       CURRENT_DATE - MAX(date) as days_old
FROM fx_valuation_signals
GROUP BY currency, region
ORDER BY days_old;
"

# 7. MCP 매크로 분석 재실행 (Claude Desktop)
# → "환율 데이터가 최신화되지 않아" 경고 사라지는지 확인
```

---

**리포트 작성 완료**
**다음 단계**: 즉시 조치 실행 → 검증 → 자동화 설정
