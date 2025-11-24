# Spock Refresh 사용 가이드

**날짜:** 2025-11-24
**버전:** 2.0 (Week 1-3 최적화 적용, v2 통합 완료)

---

## 📚 파일 구조

```
spock/
├── spock_refresh.py          # 🎯 메인 실행 파일 (UI + 최적화 통합)
└── modules/
    └── ticker_refresh/
        └── ticker_refresher.py
```

### 파일 역할

| 파일 | 역할 | 직접 실행? |
|------|------|----------|
| **spock_refresh.py** | 메인 UI + 최적화 함수 통합 (캐싱, 병렬) | ✅ 예 |

**Note:** v2.0부터 `spock_refresh_v2.py`는 `spock_refresh.py`에 통합되었습니다 (2025-11-24).

---

## 🚀 기본 사용법

### 1. 인터랙티브 메뉴 (권장)

```bash
python3 spock_refresh.py
```

**메뉴 옵션:**
```
1. 🚀 Quick Refresh (5분) - OHLCV + 기본적 + 기술적 지표
2. 📈 Full Refresh (30분) - 전체 데이터 업데이트
3. 🔄 Incremental (10분) - 누락된 데이터만
4. ⚙️  Custom - 직접 설정
5. 📅 Listing Date Setup - 상장일 관리
6. 📅 Schedule Setup - 자동화 설정
7. 📊 Status - 현재 데이터 상태 확인
8. 💰 Equity Backfill - 자본계정 백필
9. 📈 All Macro Data - 통합 매크로 데이터
10. 💹 Daily Valuation Multiples - 주가배수 업데이트
11. 📉 Technical Indicators - 기술적 지표 계산
12. 🔍 Data Validation - 백테스트 데이터 검증
13. 📊 Stock Screening - 종목 스크리닝
0. 🚪 종료
```

### 2. CLI 모드 (자동화/스크립트용)

#### Quick Refresh
```bash
python3 spock_refresh.py --quick
```

#### Full Refresh
```bash
python3 spock_refresh.py --full
```

#### Incremental Refresh
```bash
python3 spock_refresh.py --incremental
```

#### 상태 확인만
```bash
python3 spock_refresh.py --status
```

#### 특정 지역 지정
```bash
python3 spock_refresh.py --quick --regions KR US JP
```

#### Dry Run (미리보기)
```bash
python3 spock_refresh.py --full --dry-run
```

#### 자동 확인 (CI/CD용)
```bash
python3 spock_refresh.py --quick --yes
```

---

## ⚡ Week 1-3 최적화 적용됨

`spock_refresh.py`는 다음 최적화 기능들을 내장하고 있습니다:

### 적용된 최적화

| 최적화 | 성능 향상 | 설명 |
|--------|----------|------|
| **Week 1: 캐싱** | 72,603배 | 반복 쿼리 캐시 (TTL 60초) |
| **Week 2: 병렬 쿼리** | 18.3% | DB 쿼리 병렬 실행 (4 workers) |
| **Week 3: 병렬 지역** | 78% | 지역별 수집 병렬화 (6 workers) |

**전체 테스트:** 35/35 통과 (100%) ✅

---

## 📊 상태 확인

### 데이터베이스 상태 조회

```bash
python3 spock_refresh.py --status
```

**출력 예시:**
```
============================================================
📊 Database Status
============================================================

  Total Records:     1,369,467 ✓

  Regional OHLCV Breakdown:
    🇰🇷 KR: 500K records | Latest: 2025-11-23 (up to date)
    🇺🇸 US: 450K records | Latest: 2025-11-23 (up to date)
    🇭🇰 HK: 150K records | Latest: 2025-11-22 (1 days old)
    🇯🇵 JP: 120K records | Latest: 2025-11-23 (up to date)
    🇨🇳 CN: 100K records | Latest: 2025-11-22 (1 days old)
    🇻🇳 VN: 49K records  | Latest: 2025-11-23 (up to date)

  Fundamentals:   12,345 (latest: 2025-11-23)
  Factor Scores:  10,000 (latest: 2025-11-23)

  Macro Indicators:
    📊 Global Indices: 5.2K records | Latest: 2025-11-23 (up to date)
    🔍 Market Sentiment: 3.1K records | Latest: 2025-11-23 (up to date)
    💵 Bond Yields: 2.8K records | Latest: 2025-11-23 (up to date)
    🛢️  Commodities: 1.5K records | Latest: 2025-11-23 (up to date)
```

---

## 🔧 고급 사용법

### 환경 변수 설정

`.env` 파일 설정:
```bash
# PostgreSQL 설정
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_platform
DB_USER=your_user
DB_PASSWORD=your_password

# KIS API 설정
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NUMBER=your_account
```

### 성능 모니터링

캐시 통계 확인:
```python
from spock_refresh import query_cache

# 캐시 통계
print(query_cache.stats)
# {'hits': 150, 'misses': 10, 'hit_rate': 93.75}
```

DB 연결 통계:
```python
from spock_refresh import db_manager

# 연결 풀 통계
print(db_manager.get_stats())
# {'active': 2, 'idle': 3, 'total': 5}
```

---

## 🐛 문제 해결

### Q: 이전 `spock_refresh_v2.py` 파일은 어디 갔나요?

**A:** v2.0부터 `spock_refresh_v2.py`는 `spock_refresh.py`에 통합되었습니다. 모든 최적화 기능은 메인 파일에서 직접 사용 가능합니다:
```bash
python3 spock_refresh.py
```

### Q: DB 연결 오류가 발생해요

**A:** PostgreSQL이 실행 중인지 확인하고 `.env` 설정을 확인하세요:
```bash
# PostgreSQL 상태 확인
brew services list | grep postgresql

# PostgreSQL 시작
brew services start postgresql@17
```

### Q: 캐시를 초기화하고 싶어요

**A:** 프로그램을 재시작하거나 Python에서:
```python
from spock_refresh import query_cache
query_cache.invalidate()  # 전체 캐시 무효화
```

### Q: 병렬 처리를 비활성화하고 싶어요

**A:** 코드에서 `parallel=False` 옵션 사용:
```python
refresher.refresh_all_regions(incremental=True, parallel=False)
```

---

## 📈 성능 벤치마크

### 실제 측정 결과

| 작업 | Before | After | 개선 |
|------|--------|-------|------|
| **DB 상태 조회 (캐시 히트)** | 400ms | 0.01ms | **72,603배** ⚡ |
| **DB 상태 조회 (캐시 미스)** | 400ms | 327ms | **18.3%** ✓ |
| **6개 지역 수집 (병렬)** | 468ms | 103ms | **78%** ✓ |
| **평균 (90% 캐시 히트)** | 400ms | 33ms | **92%** 🎯 |

**테스트 환경:**
- PostgreSQL 17 + TimescaleDB
- 1,369,467 레코드
- MacBook Pro M1
- 측정: 10회 반복 평균

---

## 📝 자동화 예제

### Cron 작업 (일일 업데이트)

```bash
# crontab -e
# 매일 오전 9시 Quick Refresh
0 9 * * * cd /Users/13ruce/spock && python3 spock_refresh.py --quick --yes >> logs/daily_refresh.log 2>&1
```

### Python 스크립트

```python
#!/usr/bin/env python3
"""Daily automated refresh"""
import subprocess
import sys

def daily_refresh():
    """Run daily quick refresh"""
    result = subprocess.run([
        sys.executable,
        'spock_refresh.py',
        '--quick',
        '--yes'
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Daily refresh completed")
    else:
        print(f"❌ Daily refresh failed: {result.stderr}")
        sys.exit(1)

if __name__ == '__main__':
    daily_refresh()
```

---

## 🔗 관련 문서

- **[TEST_VALIDATION_REPORT.md](TEST_VALIDATION_REPORT.md)** - 테스트 검증 보고서
- **[WEEK1_COMPLETION_REPORT.md](WEEK1_COMPLETION_REPORT.md)** - Week 1 캐싱 최적화
- **[WEEK2_COMPLETION_REPORT.md](WEEK2_COMPLETION_REPORT.md)** - Week 2 병렬 쿼리
- **[WEEK3_DAY7_8_COMPLETION_REPORT.md](WEEK3_DAY7_8_COMPLETION_REPORT.md)** - Week 3 병렬 지역

---

## 📞 지원

**문제 발생 시:**
1. 로그 파일 확인: `logs/YYYYMMDD_spock_refresh.log`
2. PostgreSQL 상태 확인: `brew services list`
3. `.env` 설정 확인
4. 캐시 초기화 시도

**성능 문제:**
- 캐시 히트율 확인 (`query_cache.stats`)
- DB 연결 풀 확인 (`db_manager.get_stats()`)
- PostgreSQL 로그 확인

---

**작성자:** Claude + 13ruce
**최종 업데이트:** 2025-11-23
**버전:** 2.0 (Week 1-3 최적화)
