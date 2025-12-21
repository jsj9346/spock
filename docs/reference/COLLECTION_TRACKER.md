# CollectionTracker - 중복 데이터 수집 방지 시스템

## 개요

`CollectionTracker`는 동일 날짜에 동일 데이터를 재수집하는 것을 방지하여 API 호출과 계산 시간을 절감하는 시스템입니다.

**적용 일자**: 2025-11-27
**버전**: 1.0.0

## 문제점 분석

### 기존 문제
- **Dividend History**: 매번 API 호출 → 동일 데이터 재수집
- **Fundamental Ratios**: 날짜 체크 없이 매번 재계산
- **Quick Refresh → Full Refresh**: 이미 수집된 데이터 중복 작업

### OHLCV 참조 (문제 없음)
OHLCV는 `MAX(date)` 체크를 통해 새로운 데이터만 수집:
```python
# kr_postgres_ohlcv_adapter.py
query = "SELECT MAX(date)::DATE FROM ohlcv_data WHERE ticker = %s"
```

## 해결책

### 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    spock_refresh.py                          │
│                    (force 옵션 제공)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               DatabaseUpdateOrchestrator                     │
│         (_calculate_dividend, force=False/True)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   DividendCollector                          │
│            (CollectionTracker 통합)                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              CollectionTracker                          ││
│  │  - should_skip_batch() → 스킵 대상 필터링               ││
│  │  - mark_collected() → 수집 완료 기록                    ││
│  │  - 메모리 캐시 + DB 조회                                ││
│  └─────────────────────────────────────────────────────────┘│
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  collection_tracker                          │
│                    (PostgreSQL)                              │
│  - ticker, region, data_type, last_collected                │
│  - status, records_count, duration_ms                        │
│  - UNIQUE (ticker, region, data_type, last_collected)       │
└─────────────────────────────────────────────────────────────┘
```

## 사용법

### 1. 기본 사용 (자동 스킵)

```python
from modules.collection.dividend_collector import DividendCollector

# 기본: skip_same_day=True (동일 날짜 수집 스킵)
collector = DividendCollector(db)

# 배치 수집 시 자동으로 이미 수집된 ticker 스킵
results = collector.collect_batch(
    tickers=['005930', '000660', '035720'],
    region='KR',
    years=5,
    force=False  # 기본값
)
# 출력: "⏭️ [KR] 2 tickers skipped (already collected today)"
```

### 2. 강제 재수집 (force=True)

```python
# 강제 재수집: 이미 수집된 데이터도 다시 수집
results = collector.collect_batch(
    tickers=['005930', '000660', '035720'],
    region='KR',
    years=5,
    force=True
)
# 출력: "🔄 [KR] Force mode - recollecting all 3 tickers"
```

### 3. CLI 사용 (spock_refresh.py)

```bash
python3 spock_refresh.py
# → 8. Financial Indicators Update 선택
# → 1. Dividend History 선택
# → Region 선택
# → "Force recollection (skip duplicate prevention)? (y/N):" 프롬프트
#   - N: 이미 수집된 ticker 스킵 (기본)
#   - y: 모든 ticker 강제 재수집
```

## API 레퍼런스

### CollectionTracker 클래스

```python
from modules.collection.collection_tracker import CollectionTracker, DataType

tracker = CollectionTracker(db, skip_same_day=True)
```

#### 메서드

| 메서드 | 설명 | 반환 |
|--------|------|------|
| `should_skip(ticker, region, data_type)` | 개별 ticker 스킵 여부 | `bool` |
| `should_skip_batch(tickers, region, data_type)` | 배치 스킵 확인 | `(to_process, to_skip)` |
| `mark_collected(ticker, region, data_type, ...)` | 수집 완료 기록 | `bool` |
| `get_collection_stats(region, data_type)` | 통계 조회 | `List[Dict]` |
| `get_today_summary()` | 오늘 요약 | `Dict` |
| `clear_cache()` | 메모리 캐시 초기화 | `None` |
| `invalidate_ticker(ticker, region, data_type)` | 특정 ticker 무효화 | `None` |

#### DataType Enum

```python
class DataType(Enum):
    DIVIDEND = 'dividend'
    RATIOS = 'ratios'
    CASH_BACKFILL = 'cash_backfill'
    TECHNICAL = 'technical'
    FUNDAMENTALS = 'fundamentals'
```

## 데이터베이스 스키마

### collection_tracker 테이블

```sql
CREATE TABLE collection_tracker (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(10) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    last_collected DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'success',
    records_count INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (ticker, region, data_type, last_collected)
);
```

### 인덱스

| 인덱스 | 용도 |
|--------|------|
| `idx_collection_tracker_lookup` | 배치 조회 (region + data_type + date) |
| `idx_collection_tracker_ticker` | 개별 ticker 조회 |
| `idx_collection_tracker_date` | 날짜 기반 정리 |
| `idx_collection_tracker_status` | 상태 필터링 |

### 통계 뷰

```sql
-- v_collection_stats: 수집 작업 통계
SELECT * FROM v_collection_stats;
-- region, data_type, last_collected, status, ticker_count, total_records, avg_duration_ms
```

## 테스트

### 단위 테스트 (27개)

```bash
python3 -m pytest tests/unit/test_collection_tracker.py -v
# 27 passed
```

### 통합 테스트 (10개)

```bash
python3 tests/integration/test_collection_tracker_integration.py
# 10 passed
```

## 성능 영향

### 예상 절감

| 시나리오 | 기존 | 개선 후 |
|---------|------|--------|
| Quick → Full Refresh | 2x API 호출 | 1x API 호출 |
| 동일 날짜 재실행 | 100% 재수집 | 0% 재수집 |
| 부분 실패 후 재시도 | 전체 재수집 | 실패분만 수집 |

### 캐싱 전략

1. **메모리 캐시**: 개별 ticker 조회 결과 캐싱
2. **배치 캐시**: region+data_type+date 단위 캐싱
3. **DB 조회 최소화**: 캐시 히트 시 DB 조회 생략

## 관련 파일

| 파일 | 설명 |
|------|------|
| `migrations/010_create_collection_tracker.sql` | 테이블 마이그레이션 |
| `modules/collection/collection_tracker.py` | CollectionTracker 클래스 |
| `modules/collection/dividend_collector.py` | DividendCollector 통합 |
| `modules/orchestration/orchestrator.py` | Orchestrator 통합 |
| `spock_refresh.py` | CLI force 옵션 |
| `tests/unit/test_collection_tracker.py` | 단위 테스트 |
| `tests/integration/test_collection_tracker_integration.py` | 통합 테스트 |

## 향후 계획

1. **Ratios 계산 통합**: `_calculate_fundamental_ratios`에 tracker 적용
2. **Cash Backfill 통합**: `_backfill_cash_data`에 tracker 적용
3. **Technical 지표 통합**: 기술적 지표 계산에 tracker 적용
4. **모니터링 대시보드**: Grafana에 수집 통계 패널 추가
