# 프로덕션 통합 테스트 실행 가이드

**작성일**: 2025-11-05
**버전**: 1.0
**목적**: 프로덕션 환경에서 Database Refresh System 통합 테스트 실행 방법

---

## 📋 목차

1. [테스트 환경 준비](#1-테스트-환경-준비)
2. [Tier 1: 개별 모듈 테스트](#2-tier-1-개별-모듈-테스트)
3. [Tier 2: Orchestrator 통합 테스트](#3-tier-2-orchestrator-통합-테스트)
4. [Tier 3: 데이터 품질 검증](#4-tier-3-데이터-품질-검증)
5. [테스트 결과 분석](#5-테스트-결과-분석)
6. [문제 해결](#6-문제-해결)

---

## 1. 테스트 환경 준비

### 1.1 필수 사전 조건

```bash
# 1. Python 환경 확인
python3 --version  # Python 3.11+ 필요

# 2. 필수 패키지 설치 확인
pip3 list | grep -E 'pytest|psycopg2|pykrx|yfinance'

# 3. 패키지 설치 (필요 시)
pip3 install pytest pytest-cov psycopg2 pykrx yfinance requests python-dotenv
```

### 1.2 데이터베이스 연결 확인

```bash
# PostgreSQL 연결 테스트
psql -d quant_platform -c "SELECT version();"

# TimescaleDB 확장 확인
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"

# 필수 테이블 존재 확인
psql -d quant_platform -c "
SELECT table_name
FROM information_schema.tables
WHERE table_name IN ('tickers', 'stock_details', 'etf_details', 'etf_holdings', 'exchange_rates', 'ohlcv_data')
ORDER BY table_name;
"
```

### 1.3 환경 변수 설정

`.env` 파일에 다음 설정이 있는지 확인:

```bash
# .env 파일 확인
cat .env | grep -E 'POSTGRES|KIS_APP_KEY|ALPHA_VANTAGE'

# 필수 환경 변수:
# - POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
# - KIS_APP_KEY, KIS_APP_SECRET (KR 시장용)
# - ALPHA_VANTAGE_API_KEY (선택사항)
```

---

## 2. Tier 1: 개별 모듈 테스트

**예상 소요 시간**: 30분
**목적**: FXTracker, StockClassifier, ETFUpdater 각 모듈의 프로덕션 동작 검증

### 2.1 FXTracker 프로덕션 테스트

```bash
# 테스트 실행
cd /Users/13ruce/spock
python3 -m pytest tests/integration/production/test_fx_tracker_production.py -v -s

# 예상 결과:
# - 6개 테스트 모두 통과
# - 실행 시간: 약 5-10분
# - 최소 4개 통화(USD, JPY, EUR, CNY) 데이터 수집 확인
```

**주요 검증 항목**:
- ✅ PostgreSQL 연결 및 `exchange_rates` 테이블 존재
- ✅ exchangerate.host API 호출 및 환율 데이터 수집
- ✅ 데이터베이스 레코드 삽입 (오늘 날짜 데이터)
- ✅ FX 시그널 생성 (급격한 환율 변동 시)
- ✅ 성능 기준 (<30초)
- ✅ 다중 지역 통화 지원

### 2.2 StockClassifier 프로덕션 테스트

```bash
# 테스트 실행
python3 -m pytest tests/integration/production/test_stock_classifier_production.py -v -s

# 예상 결과:
# - 8개 테스트 모두 통과 (US 테스트 제외 가능)
# - 실행 시간: 약 10-15분
# - 최소 100개 종목 분류 완료
```

**주요 검증 항목**:
- ✅ `tickers`, `stock_details` 테이블 존재
- ✅ KR 종목 분류 실행 (limit=100)
- ✅ SPAC 탐지 (5가지 패턴)
- ✅ 우선주 탐지 (ticker 패턴)
- ✅ 섹터/업종 분류 (키워드 기반)
- ✅ 분류 완전성 (80%+ 목표)
- ✅ 성능 기준 (<5분)
- ⚠️  US 종목 분류 (선택사항, 데이터 부족 시 스킵)

### 2.3 ETFUpdater 프로덕션 테스트

```bash
# 테스트 실행
python3 -m pytest tests/integration/production/test_etf_updater_production.py -v -s

# 예상 결과:
# - 8개 테스트 모두 통과 (US 테스트 제외 가능)
# - 실행 시간: 약 15-20분
# - 최소 50개 ETF 업데이트 완료
```

**주요 검증 항목**:
- ✅ `etf_details`, `etf_holdings` 테이블 존재
- ✅ KR ETF 업데이트 (limit=50, holdings 포함)
- ✅ ETF 메타데이터 완전성 (AUM, 보수율, 상장일, 벤치마크)
- ✅ ETF 보유종목 검증 (비중 합계 ~100%)
- ✅ 추적오차 계산 (4개 기간: 20d, 60d, 120d, 250d)
- ✅ 데이터 신선도 (30일 이내 업데이트)
- ✅ 성능 기준 (<10분)
- ⚠️  US ETF 업데이트 (선택사항)

---

## 3. Tier 2: Orchestrator 통합 테스트

**예상 소요 시간**: 45분
**목적**: DatabaseUpdateOrchestrator의 파이프라인 통합 동작 검증

### 3.1 Orchestrator 프로덕션 테스트

```bash
# 테스트 실행
python3 -m pytest tests/integration/production/test_orchestrator_production.py -v -s

# 예상 결과:
# - 10개 테스트 모두 통과
# - 실행 시간: 약 30-45분
# - 전체 파이프라인 (4개 스텝) 성공 확인
```

**주요 검증 항목**:

#### 3.1.1 단일 스텝 실행 (테스트 01-03)
- ✅ FX Tracking 스텝 단독 실행
- ✅ Classification 스텝 단독 실행
- ✅ ETF Data 스텝 단독 실행

#### 3.1.2 전체 파이프라인 실행 (테스트 04-05)
- ✅ 4개 스텝 순차 실행 (`ticker_refresh → fx_tracking → classification → etf_data`)
- ✅ 파이프라인 성능 메트릭 (<15분, limit=50)

#### 3.1.3 재시도 로직 검증 (테스트 06-07)
- ✅ 임시 실패 시 재시도 (exponential backoff: 5s → 10s → 20s)
- ✅ 체크포인트 복구 (중간 실패 후 재개)

#### 3.1.4 Rich UI 진행률 표시 (테스트 08-09)
- ✅ Rich UI 프로그레스 바 표시
- ✅ 에러 핸들링 메시지 표시

#### 3.1.5 실행 통계 (테스트 10)
- ✅ 실행 시간, 완료/실패 스텝, 성공률 수집

---

## 4. Tier 3: 데이터 품질 검증

**예상 소요 시간**: 15분
**목적**: 프로덕션 환경에서 수집된 데이터의 무결성 검증

### 4.1 데이터 품질 검증 테스트

```bash
# 테스트 실행
python3 -m pytest tests/integration/production/test_data_quality_validation.py -v -s

# 예상 결과:
# - 10개 테스트 모두 통과
# - 실행 시간: 약 10-15분
# - 데이터 품질 점수 80%+ 목표
```

**주요 검증 항목**:

#### 4.1.1 환율 데이터 품질 (테스트 01-03)
- ✅ 최근 7일 데이터 완전성 (4개 통화 모두 존재)
- ✅ 환율 데이터 유효성 (USD: 800-2000, JPY: 5-20, EUR: 1000-2000, CNY: 100-300)
- ✅ 중복 레코드 검증 (중복 없음)

#### 4.1.2 종목 분류 데이터 품질 (테스트 04-05)
- ✅ 분류 완전성 (80%+ 분류율 목표)
- ✅ SPAC/우선주 탐지 정확성

#### 4.1.3 ETF 데이터 품질 (테스트 06-08)
- ✅ ETF 메타데이터 완전성 (AUM, 보수율, 상장일, 벤치마크)
- ✅ 보유종목 유효성 (비중 합계 ~100%, 음수 비중 없음)
- ✅ 데이터 신선도 (30일 이내 업데이트)

#### 4.1.4 전체 품질 종합 (테스트 09-10)
- ✅ 데이터베이스 통계 (테이블별 레코드 수)
- ✅ 데이터 품질 종합 점수 (FX, Stock, ETF 평균 80%+ 목표)

---

## 5. 테스트 결과 분석

### 5.1 성공 메트릭

| 구분 | 목표 | 검증 방법 |
|------|------|-----------|
| **Tier 1: 개별 모듈** | 100% 통과 | 각 모듈별 6-8개 테스트 통과 |
| **Tier 2: Orchestrator** | 100% 통과 | 10개 통합 테스트 통과 |
| **Tier 3: 데이터 품질** | 80%+ 품질 점수 | 10개 검증 테스트 통과 |
| **전체 실행 시간** | <90분 | Tier 1 (30분) + Tier 2 (45분) + Tier 3 (15분) |

### 5.2 결과 요약 출력

```bash
# 전체 테스트 한 번에 실행
python3 -m pytest tests/integration/production/ -v -s --tb=short

# 결과 요약 예시:
# ========================= test session starts =========================
# collected 24 items
#
# test_fx_tracker_production.py::TestFXTrackerProduction::test_01_database_connection PASSED [  4%]
# test_fx_tracker_production.py::TestFXTrackerProduction::test_02_fetch_exchange_rates PASSED [  8%]
# ...
# test_data_quality_validation.py::TestDataQualityOverall::test_10_data_quality_summary PASSED [100%]
#
# ========================= 24 passed in 90.00s =========================
```

### 5.3 테스트 보고서 생성

```bash
# pytest-html을 사용한 HTML 보고서 생성 (선택사항)
pip3 install pytest-html

python3 -m pytest tests/integration/production/ \
  -v \
  --html=results/production_test_report.html \
  --self-contained-html

# 보고서 확인
open results/production_test_report.html
```

---

## 6. 문제 해결

### 6.1 일반적인 오류

#### 오류 1: 데이터베이스 연결 실패
```
Error: could not connect to server
```

**해결 방법**:
```bash
# PostgreSQL 서비스 상태 확인
brew services list | grep postgresql

# 서비스 시작 (필요 시)
brew services start postgresql@17

# 연결 테스트
psql -d quant_platform -c "SELECT 1;"
```

#### 오류 2: API 호출 실패 (exchangerate.host)
```
Error: Failed to fetch exchange rates
```

**해결 방법**:
```bash
# 1. 인터넷 연결 확인
curl -I https://api.exchangerate.host/latest

# 2. Mock 데이터 폴백 확인 (코드 내장)
# FXTracker는 API 실패 시 자동으로 mock 데이터 사용
```

#### 오류 3: KIS API 토큰 만료
```
Error: KIS API token expired
```

**해결 방법**:
```bash
# 토큰 캐시 삭제
rm data/.kis_token_cache.json

# 테스트 재실행 (새 토큰 자동 발급)
python3 -m pytest tests/integration/production/test_stock_classifier_production.py -v -s
```

#### 오류 4: pykrx 데이터 수집 실패
```
Error: pykrx failed to fetch ETF data
```

**해결 방법**:
```bash
# pykrx는 KRX 서버 점검 시간(주말, 평일 16:00-18:00 KST) 동안 사용 불가
# 1. 현재 시간 확인
date

# 2. 평일 영업 시간(09:00-16:00 KST)에 재실행
# 3. 또는 yfinance 폴백 사용 (ETFUpdater 자동 전환)
```

### 6.2 성능 이슈

#### 느린 테스트 실행
```bash
# limit 파라미터 조정 (테스트용)
# test_stock_classifier_production.py:
# result = classifier.classify_region(region='KR', limit=50)  # 100 → 50

# test_etf_updater_production.py:
# result = etf_updater.update_region(region='KR', limit=25)  # 50 → 25
```

#### 데이터베이스 쿼리 최적화
```sql
-- 인덱스 확인
SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public';

-- 느린 쿼리 확인
SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

### 6.3 테스트 데이터 정리

```bash
# 테스트 데이터 정리 (주의: 프로덕션에서 실행 금지)
psql -d quant_platform <<EOF
-- 테스트 중 생성된 최근 데이터만 삭제 (선택사항)
DELETE FROM exchange_rates WHERE date = CURRENT_DATE AND base_currency = 'KRW';
DELETE FROM stock_details WHERE updated_at >= CURRENT_DATE;
DELETE FROM etf_details WHERE updated_at >= CURRENT_DATE;
EOF
```

---

## 📊 체크리스트

실행 전 체크리스트:

- [ ] Python 3.11+ 설치 확인
- [ ] PostgreSQL + TimescaleDB 실행 중
- [ ] `.env` 파일 설정 완료 (데이터베이스 자격증명, API 키)
- [ ] 필수 테이블 존재 확인 (tickers, stock_details, etf_details, exchange_rates)
- [ ] 인터넷 연결 확인 (API 호출용)

실행 후 체크리스트:

- [ ] Tier 1 테스트 (개별 모듈) 100% 통과
- [ ] Tier 2 테스트 (Orchestrator) 100% 통과
- [ ] Tier 3 테스트 (데이터 품질) 80%+ 품질 점수
- [ ] 전체 실행 시간 <90분
- [ ] 데이터베이스 레코드 증가 확인
- [ ] 에러 로그 확인 및 분석

---

## 🚀 다음 단계

테스트 완료 후:

1. **프로덕션 배포 준비**:
   - 테스트 결과 보고서 작성
   - 성능 병목 지점 분석 및 개선
   - 데이터 품질 이슈 해결

2. **자동화 설정**:
   - CI/CD 파이프라인 통합 (GitHub Actions, Jenkins 등)
   - 일일 자동 테스트 스케줄링 (cron, Airflow 등)
   - Slack/이메일 알림 설정

3. **모니터링 강화**:
   - Grafana 대시보드 설정
   - 데이터 품질 메트릭 추적
   - 알림 규칙 설정 (품질 점수 <80% 시)

---

**마지막 업데이트**: 2025-11-05
**문서 버전**: 1.0
**작성자**: Database Refresh System Team
