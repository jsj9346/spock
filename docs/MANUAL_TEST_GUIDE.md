# Technical Indicator Integration - 수동 테스트 가이드

**목적**: Week 2 구현 (2-phase execution pattern) 검증
**날짜**: 2025-11-15

---

## 📋 사전 준비

### 1. 터미널 2개 준비

**터미널 1**: spock_refresh.py 실행용
**터미널 2**: 실시간 모니터링용

### 2. 터미널 2에서 모니터링 시작

```bash
cd ~/spock

# KR 시장 technical_analysis 커버리지 실시간 확인
watch -n 5 "psql -d quant_platform -c \"
SELECT
    COUNT(DISTINCT t.ticker) as total,
    COUNT(DISTINCT ta.ticker) as with_indicators,
    ROUND(100.0 * COUNT(DISTINCT ta.ticker) / NULLIF(COUNT(DISTINCT t.ticker), 0), 2) as pct
FROM tickers t
LEFT JOIN technical_analysis ta ON t.ticker = ta.ticker AND t.region = ta.region
WHERE t.region = 'KR';
\""
```

---

## 🧪 Test 1: Quick Refresh (소규모 - 권장)

**목표**: 2-phase execution 패턴 검증 + 실시간 진행률 확인

### 실행 방법

#### 터미널 1
```bash
cd ~/spock
python3 spock_refresh.py
```

**Menu 선택**:
1. 숫자 `1` 입력 (Quick Refresh)
2. Region: `KR` 입력
3. 실행 확인: `y` 또는 Enter

### 예상 출력

```
🚀 Quick Refresh - Select regions:
  Available: KR US HK JP CN VN
  Examples:
    KR         - Korea only
    KR US      - Korea and United States
    ALL        - All regions

Enter regions [KR]:  KR

Phase 1: Data Update
============================================================
[subprocess 실행 로그...]

Phase 2: Technical Indicators Calculation (Incremental)
============================================================

📊 Processing: KR
============================================================
Batch 1/39 (100 tickers): [진행률 표시]
  ✅ Success: 98/100 | Failed: 2

Batch 2/39 (100 tickers): [진행률 표시]
  ✅ Success: 100/100 | Failed: 0

...

✅ Completed: KR
   Success: 3,850/3,925 tickers
   Failed: 75 tickers
   Duration: 18.5 minutes

✅ Quick Refresh Complete!
============================================================
Regions: KR
Technical Indicators: 3,850/3,925 tickers
Total Time: 25.3 minutes
============================================================
```

### 검증 체크리스트

- [ ] Phase 1 subprocess 정상 실행
- [ ] Phase 2 direct calculation 시작
- [ ] Batch 단위 진행률 표시
- [ ] 실시간 성공/실패 카운트
- [ ] 터미널 2에서 커버리지 증가 확인
- [ ] 최종 summary 표시
- [ ] 실행 시간 측정

---

## 🧪 Test 2: Technical Indicators Only (멀티 region)

**목표**: 멀티 region + batch size + dry-run 옵션 검증

### 실행 방법

#### 터미널 1
```bash
cd ~/spock
python3 spock_refresh.py
```

**Menu 선택**:
1. 숫자 `11` 입력 (Technical Indicators Only)
2. Regions: `KR HK` 입력 (2개 마켓)
3. Calculation Mode: `1` 입력 (Incremental)
4. Batch Size: `2` 입력 (Medium - 100)
5. Dry-run: `y` 입력 (미리보기 모드)
6. 확인: `y` 또는 Enter

### 예상 출력 (Dry-run)

```
Configuration Summary:
============================================================
  Regions: KR, HK
  Mode: Incremental
  Batch Size: 100 tickers
  Dry Run: Yes
============================================================

Proceed with technical indicators calculation? [Y/n]:  y

Starting Technical Indicators Calculation...
============================================================

📊 Processing: KR
============================================================
DRY RUN MODE - No actual calculation performed

✅ Completed: KR
   Total tickers: 3,925
   (Dry-run - no changes made)

📊 Processing: HK
============================================================
DRY RUN MODE - No actual calculation performed

✅ Completed: HK
   Total tickers: 2,723
   (Dry-run - no changes made)

✅ Technical Indicators Calculation Complete!
============================================================
Regions: KR, HK
Mode: Incremental
Total Tickers: 6,648 (dry-run)
Total Time: 0.2 minutes
============================================================
```

### 검증 체크리스트

- [ ] Multi-region 입력 처리
- [ ] Batch size 선택 동작
- [ ] Dry-run 모드 동작
- [ ] 설정 요약 정확성
- [ ] Database 수정 없음 (dry-run)
- [ ] Region별 순차 처리

---

## 🧪 Test 3: Full Refresh (주의: 오래 걸림)

**목표**: Full recalculation 모드 검증

**⚠️ 주의**: 전체 KR 시장 재계산 시 약 30-40분 소요

### 실행 방법 (권장하지 않음 - 시간 소요)

```bash
cd ~/spock
python3 spock_refresh.py
```

**Menu 선택**:
1. 숫자 `2` 입력 (Full Refresh)
2. Region: `KR` 입력
3. Listing date 경고 확인 후 계속: `y`
4. 실행 확인: `y`

### 예상 동작

- Phase 1: tickers, ohlcv, fundamentals, daily_valuation 업데이트
- Phase 2: Technical Indicators **완전 재계산** (`incremental=False`)

### 검증 체크리스트

- [ ] Listing date coverage 체크 동작
- [ ] Phase 1 모든 steps 실행
- [ ] Phase 2 full recalculation 동작
- [ ] 기존 indicators 덮어쓰기 확인

---

## 🧪 Test 4: Custom Refresh (조건부 로직)

**목표**: technical_indicators 스마트 감지 검증

### Case A: technical_indicators 포함

```bash
cd ~/spock
python3 spock_refresh.py
```

**Menu 선택**:
1. 숫자 `4` 입력 (Custom Refresh)
2. Regions: `KR` 입력
3. Steps: `ohlcv technical_indicators` 입력
4. Incremental: `y` (Enter)
5. Dry-run: `n` (Enter)

**예상 동작**:
- ✅ 2-phase execution 실행
- Phase 1: ohlcv (subprocess)
- Phase 2: technical_indicators (direct)

### Case B: technical_indicators 미포함

```bash
cd ~/spock
python3 spock_refresh.py
```

**Menu 선택**:
1. 숫자 `4` 입력
2. Regions: `KR`
3. Steps: `ohlcv fundamentals` 입력 (technical_indicators 제외)
4. Incremental: `y`
5. Dry-run: `n`

**예상 동작**:
- ✅ 1-phase (기존 subprocess 방식)
- technical_indicators가 없으므로 2-phase 패턴 스킵

### 검증 체크리스트

- [ ] Case A: 2-phase execution 실행
- [ ] Case B: 1-phase (기존 방식) 실행
- [ ] technical_indicators 스마트 감지 동작
- [ ] 조건부 로직 정확성

---

## 📊 테스트 결과 수집

### Database 쿼리로 검증

#### 1. Technical Analysis 데이터 확인
```sql
-- Region별 indicator 개수
SELECT
    region,
    COUNT(DISTINCT ticker) as ticker_count,
    COUNT(*) as total_indicators,
    COUNT(*) / NULLIF(COUNT(DISTINCT ticker), 0) as avg_indicators_per_ticker
FROM technical_analysis
GROUP BY region
ORDER BY region;
```

#### 2. 최근 계산된 지표 확인
```sql
-- KR 시장 최근 계산된 지표 (상위 10개)
SELECT
    ticker,
    indicator_name,
    indicator_value,
    timestamp,
    created_at
FROM technical_analysis
WHERE region = 'KR'
ORDER BY created_at DESC
LIMIT 10;
```

#### 3. 실패한 ticker 확인 (있을 경우)
```sql
-- OHLCV 데이터는 있지만 technical_analysis가 없는 ticker
SELECT t.ticker, COUNT(o.timestamp) as data_points
FROM tickers t
INNER JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
LEFT JOIN technical_analysis ta ON t.ticker = ta.ticker AND t.region = ta.region
WHERE t.region = 'KR'
  AND ta.ticker IS NULL
GROUP BY t.ticker
HAVING COUNT(o.timestamp) >= 200
ORDER BY COUNT(o.timestamp) DESC
LIMIT 20;
```

---

## 🐛 문제 해결

### 문제 1: Import Error

**증상**:
```
ModuleNotFoundError: No module named 'scripts.calculate_technical_indicators'
```

**해결**:
```bash
# spock 디렉토리에서 실행하는지 확인
cd ~/spock
python3 spock_refresh.py
```

---

### 문제 2: Database Connection Error

**증상**:
```
psycopg2.OperationalError: could not connect to server
```

**해결**:
```bash
# PostgreSQL 서비스 확인
brew services list | grep postgresql

# PostgreSQL 재시작
brew services restart postgresql@17

# 연결 테스트
psql -d quant_platform -c "SELECT 1;"
```

---

### 문제 3: Lock Timeout

**증상**:
```
ERROR: Lock 'quick_refresh' is currently held by another process
```

**해결**:
```bash
# 실행 중인 프로세스 확인
ps aux | grep python3 | grep spock

# 필요시 종료 (PID 확인 후)
kill -9 [PID]
```

---

## 📈 성능 벤치마크 템플릿

테스트 완료 후 아래 템플릿에 결과 기록:

| Test | Region | Tickers | Mode | Batch Size | Duration | Success Rate |
|------|--------|---------|------|------------|----------|--------------|
| Quick Refresh | KR | 3,925 | Incremental | 100 | __ min | __% |
| Full Refresh | KR | 3,925 | Full | 100 | __ min | __% |
| Technical Only | KR HK | 6,648 | Incremental | 100 | __ min | __% |
| Custom (2-phase) | KR | 3,925 | Incremental | 100 | __ min | __% |

---

## ✅ 테스트 완료 체크리스트

Week 2 구현 검증:

### 기능 검증
- [ ] Phase 1 subprocess 정상 실행
- [ ] Phase 2 direct calculation 정상 실행
- [ ] Multi-region 순차 처리
- [ ] Incremental vs Full mode 차이
- [ ] Batch size 설정 적용
- [ ] Dry-run 모드 동작
- [ ] Custom refresh 조건부 로직

### UX 검증
- [ ] 실시간 진행률 표시
- [ ] Batch 단위 업데이트
- [ ] Region별 결과 표시
- [ ] 설정 요약 정확성
- [ ] 에러 메시지 명확성

### 안정성 검증
- [ ] Database 연결 안정성
- [ ] Ticker 단위 에러 처리
- [ ] Lock 메커니즘 동작
- [ ] Memory leak 없음

---

**작성일**: 2025-11-15
**테스트 담당**: [이름]
**테스트 일자**: [YYYY-MM-DD]
**테스트 환경**: macOS, PostgreSQL 17, Python 3.11
