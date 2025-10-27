# 기술적 지표 전체 재계산 시스템 설계

**작성일**: 2025-10-20
**목적**: 데이터 수집 완료 후 모든 기술적 지표를 효율적으로 재계산
**대상**: 3,745개 KR 종목 × 16개 지표

---

## 1. 시스템 개요

### 1.1 설계 목표

**Primary Goals**:
1. **완전성**: 모든 기술적 지표 재계산 (MA, RSI, MACD, BB, ATR, Volume 지표)
2. **효율성**: 배치 처리로 빠른 재계산 (목표: 3,745 종목 < 5분)
3. **안정성**: 오류 처리 및 롤백 메커니즘
4. **검증**: 재계산 전후 품질 검증

**Success Metrics**:
- MA200 NULL: 74.25% → <1% (목표: 0%)
- MA120 NULL: 31.91% → <1% (목표: 0%)
- 모든 지표 NULL: <5% (데이터 부족 종목 제외)
- 처리 속도: >12 종목/초 (3,745 종목 ÷ 300초)

### 1.2 재계산 대상 지표

```yaml
이동평균선 (Moving Averages):
  - ma5: 5일 이동평균 (min_periods=5)
  - ma20: 20일 이동평균 (min_periods=20)
  - ma60: 60일 이동평균 (min_periods=60)
  - ma120: 120일 이동평균 (min_periods=120)
  - ma200: 200일 이동평균 (min_periods=200)

모멘텀 지표 (Momentum):
  - rsi_14: RSI 14일 (Relative Strength Index)
  - macd: MACD Line (12, 26, 9)
  - macd_signal: Signal Line
  - macd_hist: Histogram

변동성 지표 (Volatility):
  - bb_upper: Bollinger Bands 상단 (20, 2σ)
  - bb_middle: Bollinger Bands 중간 (= MA20)
  - bb_lower: Bollinger Bands 하단 (20, 2σ)
  - atr: Average True Range 14일
  - atr_14: ATR 14일 (중복, 통합 필요)

거래량 지표 (Volume):
  - volume_ma20: 거래량 20일 이동평균
  - volume_ratio: 현재 거래량 / MA20 비율
```

**총 16개 지표** (atr/atr_14 중복 포함)

---

## 2. 시스템 아키텍처

### 2.1 구조 설계

```
┌─────────────────────────────────────────────────────────────────┐
│              recalculate_technical_indicators.py                 │
│                    (Main Orchestrator)                           │
└───────────────────┬─────────────────────────────────────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
┌─────────────────────┐   ┌─────────────────────┐
│  Pre-Validation     │   │  Post-Validation    │
│  - Data coverage    │   │  - NULL check       │
│  - NULL analysis    │   │  - Completeness     │
└─────────────────────┘   └─────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ Batch 1 │  │ Batch 2 │  │ Batch N │
│ (500개) │  │ (500개) │  │ (500개) │
└─────────┘  └─────────┘  └─────────┘
    │               │               │
    └───────────────┼───────────────┘
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
┌─────────────────────┐   ┌─────────────────────┐
│  Indicator Engine   │   │   Database Layer    │
│  (Vectorized Calc)  │   │   (Batch UPSERT)    │
└─────────────────────┘   └─────────────────────┘
```

### 2.2 처리 흐름 (Workflow)

```
Step 1: Pre-Validation (사전 검증)
├─ 데이터베이스 연결 확인
├─ 종목 목록 조회 (region='KR')
├─ 데이터 커버리지 분석
│  ├─ 평균 데이터 기간 확인
│  ├─ 최소 데이터 요구사항 체크 (≥200일)
│  └─ 부족 종목 필터링
├─ 현재 NULL 비율 측정
│  ├─ MA120, MA200 NULL 카운트
│  ├─ 전체 지표 NULL 통계
│  └─ 재계산 필요 종목 식별
└─ 백업 생성 (선택적)

Step 2: Batch Processing (배치 처리)
├─ 종목 목록을 배치로 분할 (500개/배치)
├─ 각 배치에 대해:
│  ├─ DB에서 OHLCV 데이터 로드
│  ├─ Pandas DataFrame으로 변환
│  ├─ 기술적 지표 계산 (벡터화)
│  │  ├─ Moving Averages (5개)
│  │  ├─ RSI-14
│  │  ├─ MACD (3개 값)
│  │  ├─ Bollinger Bands (3개 값)
│  │  ├─ ATR-14
│  │  └─ Volume 지표 (2개)
│  ├─ 결과 검증 (NaN 체크)
│  └─ DB에 UPSERT (배치 업데이트)
├─ 진행 상황 로깅 (100개마다)
└─ 에러 처리 및 재시도

Step 3: Post-Validation (사후 검증)
├─ NULL 비율 재측정
├─ 개선 효과 계산
│  ├─ MA200 NULL: Before → After
│  ├─ MA120 NULL: Before → After
│  └─ 전체 지표 NULL: Before → After
├─ 데이터 품질 평가
│  ├─ EXCELLENT: MA200 NULL <1%
│  ├─ GOOD: MA200 NULL <5%
│  └─ INSUFFICIENT: MA200 NULL ≥5%
└─ 최종 리포트 생성

Step 4: Cleanup (정리)
├─ 임시 파일 삭제
├─ 데이터베이스 최적화 (VACUUM)
└─ 로그 아카이빙
```

---

## 3. 상세 설계

### 3.1 데이터 로딩 전략

**Challenge**: 3,745개 종목 × 평균 248행 = ~929,000행 메모리 로딩 부담

**Solution**: 배치 처리 + 메모리 최적화

```python
# Option A: 종목별 순차 처리 (메모리 효율)
for ticker in tickers:
    df = load_ohlcv(ticker)  # ~248 rows
    df_with_indicators = calculate_indicators(df)
    save_to_db(ticker, df_with_indicators)
    # 장점: 메모리 사용량 일정 (~10 MB)
    # 단점: DB I/O 많음 (3,745회 SELECT + 3,745회 UPDATE)

# Option B: 배치 처리 (성능 최적화) ⭐ 권장
for batch in split_into_batches(tickers, batch_size=500):
    df_batch = load_ohlcv_batch(batch)  # 500 tickers × 248 rows = ~124,000 rows
    df_with_indicators = calculate_indicators_batch(df_batch)
    save_to_db_batch(df_with_indicators)
    # 장점: DB I/O 최소화 (8회 SELECT + 8회 UPDATE)
    # 단점: 메모리 사용량 증가 (~50 MB/배치)

# Option C: 하이브리드 (균형) ⭐ 최적
for batch in split_into_batches(tickers, batch_size=100):
    for ticker in batch:
        df = load_ohlcv(ticker)
        df_with_indicators = calculate_indicators(df)
        buffer.append(df_with_indicators)
    save_to_db_batch(buffer)
    buffer.clear()
    # 장점: 메모리 효율 + DB I/O 최적화
    # 단점: 구현 복잡도 증가
```

**선택**: **Option B (배치 처리)** - 성능 우선, 메모리 여유 충분

### 3.2 지표 계산 최적화

**Vectorized Calculation** (Pandas 벡터 연산 활용)

```python
def calculate_indicators_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """
    벡터화된 지표 계산 (Pandas Native Operations)

    Performance: 100x faster than row-by-row iteration
    Memory: O(n) where n = number of rows
    """
    # Moving Averages (병렬 계산 가능)
    df['ma5'] = df['close'].rolling(5, min_periods=5).mean()
    df['ma20'] = df['close'].rolling(20, min_periods=20).mean()
    df['ma60'] = df['close'].rolling(60, min_periods=60).mean()
    df['ma120'] = df['close'].rolling(120, min_periods=120).mean()
    df['ma200'] = df['close'].rolling(200, min_periods=200).mean()

    # RSI (delta → gain/loss → RS → RSI)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))

    # MACD (EMA 기반)
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # Bollinger Bands
    bb_middle = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    df['bb_upper'] = bb_middle + (bb_std * 2)
    df['bb_middle'] = bb_middle
    df['bb_lower'] = bb_middle - (bb_std * 2)

    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_14'] = df['atr']  # 중복 컬럼 동기화

    # Volume indicators
    df['volume_ma20'] = df['volume'].rolling(20, min_periods=20).mean()
    df['volume_ratio'] = (df['volume'] / df['volume_ma20']).fillna(1.0)

    return df
```

**Performance Comparison**:
- Row-by-row iteration: ~500 ms/ticker
- Vectorized calculation: ~5 ms/ticker (**100x faster**)
- 3,745 tickers: 1,872 seconds → **18.7 seconds**

### 3.3 데이터베이스 업데이트 전략

**Challenge**: 3,745개 종목 × 16개 지표 × 평균 248행 = ~14,900,000 개 값 업데이트

**Solution**: Batch UPSERT with Transaction

```python
def batch_update_indicators(tickers: List[str], batch_size: int = 100):
    """
    배치 단위 UPSERT로 성능 최적화

    Performance:
    - Single UPDATE: ~10 ms/row
    - Batch UPDATE (100 rows): ~50 ms (0.5 ms/row) = 20x faster
    """
    conn = sqlite3.connect('data/spock_local.db')
    cursor = conn.cursor()

    for batch in split_batches(tickers, batch_size):
        try:
            # Begin transaction
            cursor.execute('BEGIN TRANSACTION')

            for ticker in batch:
                # Load OHLCV data
                df = load_ohlcv(ticker)

                # Calculate indicators
                df_with_indicators = calculate_indicators_vectorized(df)

                # Prepare batch update
                for _, row in df_with_indicators.iterrows():
                    cursor.execute('''
                        UPDATE ohlcv_data
                        SET ma5=?, ma20=?, ma60=?, ma120=?, ma200=?,
                            rsi_14=?, macd=?, macd_signal=?, macd_hist=?,
                            bb_upper=?, bb_middle=?, bb_lower=?,
                            atr=?, atr_14=?,
                            volume_ma20=?, volume_ratio=?
                        WHERE ticker=? AND region=? AND date=?
                    ''', (
                        row['ma5'], row['ma20'], row['ma60'], row['ma120'], row['ma200'],
                        row['rsi_14'], row['macd'], row['macd_signal'], row['macd_hist'],
                        row['bb_upper'], row['bb_middle'], row['bb_lower'],
                        row['atr'], row['atr_14'],
                        row['volume_ma20'], row['volume_ratio'],
                        ticker, 'KR', row['date']
                    ))

            # Commit transaction
            conn.commit()
            logger.info(f"✅ Batch {batch_idx}: {len(batch)} tickers updated")

        except Exception as e:
            # Rollback on error
            conn.rollback()
            logger.error(f"❌ Batch {batch_idx} failed: {e}")
            continue

    conn.close()
```

**Transaction Benefits**:
- **Atomicity**: 배치 전체 성공 or 전체 실패 (부분 업데이트 방지)
- **Performance**: 디스크 I/O 최소화 (커밋 횟수 감소)
- **Consistency**: 데이터 일관성 보장

### 3.4 에러 처리 및 복구

**Error Scenarios**:

```python
# Scenario 1: 데이터 부족 (< 200일)
if len(df) < 200:
    logger.warning(f"⚠️ {ticker}: Insufficient data ({len(df)} days)")
    # Action: Skip MA120/MA200, calculate other indicators
    df['ma120'] = None
    df['ma200'] = None

# Scenario 2: 계산 오류 (Division by zero, NaN)
try:
    df['rsi_14'] = calculate_rsi(df)
except Exception as e:
    logger.error(f"❌ {ticker}: RSI calculation failed - {e}")
    df['rsi_14'] = None

# Scenario 3: DB 업데이트 실패
try:
    save_to_db(ticker, df)
except sqlite3.Error as e:
    logger.error(f"❌ {ticker}: DB update failed - {e}")
    # Action: Retry 3 times with exponential backoff
    for attempt in range(3):
        time.sleep(2 ** attempt)
        try:
            save_to_db(ticker, df)
            break
        except:
            continue
```

**Rollback Mechanism**:

```python
def create_backup():
    """재계산 전 현재 상태 백업"""
    backup_path = f'data/spock_local.db.backup_before_recalc_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy('data/spock_local.db', backup_path)
    return backup_path

def rollback(backup_path: str):
    """문제 발생 시 백업에서 복구"""
    shutil.copy(backup_path, 'data/spock_local.db')
    logger.info(f"✅ Rolled back to: {backup_path}")
```

---

## 4. 성능 최적화

### 4.1 병렬 처리 (Optional)

**Multi-Threading** (I/O Bound 작업에 효과적)

```python
from concurrent.futures import ThreadPoolExecutor

def recalculate_parallel(tickers: List[str], num_workers: int = 4):
    """
    병렬 처리로 성능 향상

    Performance:
    - Single-threaded: ~300 seconds
    - Multi-threaded (4 workers): ~75 seconds (4x faster)
    """
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []

        for ticker in tickers:
            future = executor.submit(recalculate_ticker, ticker)
            futures.append(future)

        # Wait for all tasks
        for future in futures:
            try:
                result = future.result()
            except Exception as e:
                logger.error(f"Task failed: {e}")
```

**주의사항**:
- SQLite는 **Write Lock** 때문에 동시 쓰기 제한
- 해결: 각 워커가 독립적으로 계산 → Main thread에서 순차 저장

### 4.2 메모리 최적화

```python
# Pandas dtype 최적화 (메모리 50% 절약)
df = df.astype({
    'open': 'float32',   # float64 → float32
    'high': 'float32',
    'low': 'float32',
    'close': 'float32',
    'volume': 'int32',   # int64 → int32
})

# 불필요한 컬럼 제거
df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

# 메모리 해제
del df_with_indicators
gc.collect()
```

### 4.3 데이터베이스 최적화

```sql
-- 인덱스 활용 (UPDATE 속도 향상)
CREATE INDEX IF NOT EXISTS idx_ticker_region_date
ON ohlcv_data(ticker, region, date);

-- VACUUM (디스크 공간 회수 + 성능 향상)
VACUUM;

-- ANALYZE (쿼리 플래너 최적화)
ANALYZE;
```

---

## 5. 검증 및 모니터링

### 5.1 품질 검증 체크리스트

```yaml
Pre-Validation:
  - ✅ 데이터베이스 연결 확인
  - ✅ 종목 수 확인 (3,745개)
  - ✅ 평균 데이터 기간 (≥240일)
  - ✅ MA200 계산 가능 종목 수 (≥200일 데이터)

Post-Validation:
  - ✅ MA200 NULL 비율 (<1%)
  - ✅ MA120 NULL 비율 (<1%)
  - ✅ 전체 지표 NULL 비율 (<5%)
  - ✅ 계산 값 유효성 (NaN, Inf 체크)
  - ✅ 데이터 일관성 (bb_middle == ma20)

Consistency Checks:
  - bb_middle == ma20 (볼린저 밴드 중간선 = MA20)
  - atr == atr_14 (중복 컬럼 동기화)
  - volume_ratio = volume / volume_ma20
  - macd_hist = macd - macd_signal
```

### 5.2 진행 상황 모니터링

```python
# Progress Logging (100개마다)
if ticker_count % 100 == 0:
    elapsed = time.time() - start_time
    progress = ticker_count / total_tickers * 100
    eta = (elapsed / ticker_count) * (total_tickers - ticker_count)

    print(f"""
    {'='*80}
    진행률: {ticker_count}/{total_tickers} ({progress:.1f}%)
    성공: {success_count}, 실패: {failed_count}
    경과 시간: {elapsed:.1f}초
    예상 남은 시간: {eta:.1f}초
    {'='*80}
    """)
```

### 5.3 최종 리포트

```
================================================================================
기술적 지표 재계산 완료 리포트
================================================================================

처리 통계:
  총 종목: 3,745개
  성공: 3,720개 (99.3%)
  실패: 25개 (0.7%)
  소요 시간: 4분 32초

품질 개선:
  MA200 NULL: 74.25% → 0.8% (✅ -73.45%p)
  MA120 NULL: 31.91% → 0.5% (✅ -31.41%p)
  RSI NULL: 5.2% → 0.3% (✅ -4.9%p)
  MACD NULL: 6.1% → 0.4% (✅ -5.7%p)
  BB NULL: 5.8% → 0.3% (✅ -5.5%p)
  ATR NULL: 7.2% → 0.6% (✅ -6.6%p)

데이터 품질: EXCELLENT ✅
→ LayeredScoringEngine 실행 가능

실패 종목 (25개):
  - 0000H0: 데이터 부족 (129일)
  - 0000J0: 데이터 부족 (196일)
  ... (상세 목록 생략)

다음 단계:
  1. ✅ 검증 스크립트 실행: python3 scripts/validate_kr_ohlcv_quality.py
  2. ⏳ LayeredScoringEngine 실행: python3 modules/stock_technical_filter.py --region KR
================================================================================
```

---

## 6. 구현 가이드

### 6.1 파일 구조

```
scripts/
  recalculate_technical_indicators.py      # Main script

modules/
  indicator_calculator.py                  # Indicator calculation engine
  batch_processor.py                       # Batch processing utilities

logs/
  indicator_recalculation_YYYYMMDD.log    # Execution logs

data/
  spock_local.db                           # Main database
  spock_local.db.backup_before_recalc_*    # Backup files
```

### 6.2 의존성

```python
# Required packages (already installed)
import pandas as pd               # 2.0.3
import numpy as np                # 1.24.3
import sqlite3                    # Built-in
import logging                    # Built-in
from datetime import datetime     # Built-in
from typing import List, Dict     # Built-in

# Optional (for performance)
import pandas_ta as ta            # 0.3.14b0 (if available)
from concurrent.futures import ThreadPoolExecutor  # Built-in
```

### 6.3 실행 방법

```bash
# 기본 실행
python3 scripts/recalculate_technical_indicators.py

# 배치 크기 지정
python3 scripts/recalculate_technical_indicators.py --batch-size 100

# 백업 생성
python3 scripts/recalculate_technical_indicators.py --backup

# 특정 종목만 재계산
python3 scripts/recalculate_technical_indicators.py --tickers 005930,000660,373220

# 병렬 처리 (4 workers)
python3 scripts/recalculate_technical_indicators.py --parallel --workers 4

# Dry-run (실제 업데이트 없이 테스트)
python3 scripts/recalculate_technical_indicators.py --dry-run
```

---

## 7. 리스크 및 완화 방안

### 7.1 주요 리스크

| 리스크 | 영향 | 확률 | 완화 방안 |
|--------|------|------|-----------|
| 대량 데이터 처리 중 메모리 부족 | High | Low | 배치 크기 조정 (500 → 100) |
| SQLite Write Lock 경합 | Medium | Medium | 순차 저장 or PostgreSQL 마이그레이션 |
| 계산 오류로 잘못된 값 저장 | High | Low | 사전 백업 + 검증 체크 |
| 장시간 실행 중 중단 | Medium | Low | 체크포인트 저장 + 재시작 지원 |
| 디스크 공간 부족 | Medium | Very Low | 사전 공간 확인 (최소 500 MB) |

### 7.2 롤백 계획

```bash
# 문제 발생 시 백업에서 복구
cp data/spock_local.db.backup_before_recalc_20251020_103516 data/spock_local.db

# 또는 스크립트 실행
python3 scripts/rollback_database.py --backup data/spock_local.db.backup_before_recalc_20251020_103516
```

---

## 8. 예상 성능

### 8.1 시간 추정

```
단일 종목 처리 시간:
  - 데이터 로드: ~2 ms
  - 지표 계산: ~5 ms (벡터화)
  - DB 업데이트: ~3 ms
  - 합계: ~10 ms/종목

전체 처리 시간:
  - 3,745 종목 × 10 ms = 37.45초
  - 오버헤드 (로깅, 검증) = ~30초
  - 총 예상 시간: ~70초 (1.2분)

배치 처리 시간 (batch_size=100):
  - 38 배치 × (100 종목 × 10 ms + 트랜잭션 오버헤드 50 ms)
  - 38 × 1.05초 = 39.9초
  - 총 예상 시간: ~60초 (1분)
```

### 8.2 리소스 사용량

```
메모리:
  - 배치당 최대: ~50 MB (500 종목)
  - 총 피크: ~100 MB (버퍼 포함)

디스크:
  - 백업 파일: ~172 MB
  - 로그 파일: ~5 MB
  - 임시 공간: ~50 MB
  - 총 필요 공간: ~230 MB

CPU:
  - 사용률: 20-40% (단일 코어)
  - 병렬 처리 시: 60-80% (4 코어)
```

---

## 9. 다음 단계

### 9.1 즉시 실행 가능한 작업

1. ✅ **스크립트 구현**: `recalculate_technical_indicators.py` 작성
2. ✅ **단위 테스트**: 10개 종목으로 먼저 테스트
3. ✅ **전체 실행**: 3,745개 전체 재계산
4. ✅ **검증**: `validate_kr_ohlcv_quality.py` 실행
5. ⏳ **LayeredScoringEngine 실행**: 100점 점수 시스템 적용

### 9.2 향후 개선 사항

```yaml
Phase 1 (현재):
  - 단일 region (KR) 지원
  - 순차 처리
  - SQLite 사용

Phase 2 (향후):
  - Multi-region 지원 (US, CN, HK, JP, VN)
  - 병렬 처리 최적화
  - PostgreSQL 마이그레이션

Phase 3 (미래):
  - 증분 업데이트 (변경된 종목만)
  - 실시간 지표 계산
  - 분산 처리 (Celery, Redis)
```

---

**설계 완료일**: 2025-10-20
**예상 구현 시간**: 10-15분
**예상 실행 시간**: 1-2분
**품질 개선 목표**: MA200 NULL 74.25% → <1%
