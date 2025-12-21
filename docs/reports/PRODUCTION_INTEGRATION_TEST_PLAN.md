# 프로덕션 통합 테스트 플랜

**작성일**: 2025-11-05
**대상**: Phase 1-3 완료 후 Database Refresh System
**목적**: 실제 PostgreSQL 데이터베이스 환경에서 전체 파이프라인 검증

---

## 📋 테스트 개요

### 목표
- **기능 검증**: FXTracker, StockClassifier, ETFUpdater, Orchestrator 통합 동작 확인
- **데이터 품질**: 데이터베이스에 저장된 데이터의 정확성 및 완전성 검증
- **성능 측정**: 실제 환경에서 파이프라인 실행 시간 및 리소스 사용량 측정
- **에러 핸들링**: 재시도 로직, 에러 복구, Checkpoint 기능 검증

### 범위
- ✅ Phase 1: FXTracker (환율 추적)
- ✅ Phase 2: StockClassifier (종목 분류)
- ✅ Phase 3: Orchestrator 통합
- ✅ 추가: ETFUpdater (ETF 데이터)

---

## 🏗️ 테스트 환경 구성

### 1. 데이터베이스 환경

#### 옵션 A: 테스트 전용 데이터베이스 (권장)
```bash
# 1. 테스트 DB 생성
createdb quant_platform_test

# 2. 스키마 복사
pg_dump quant_platform --schema-only | psql quant_platform_test

# 3. 최소 테스트 데이터 삽입 (10-20 ticker)
psql quant_platform_test << EOF
-- 테스트용 ticker 삽입
INSERT INTO tickers (ticker, name, region, exchange, asset_type, is_active)
VALUES
  ('005930', '삼성전자', 'KR', 'KOSPI', 'STOCK', true),
  ('000660', 'SK하이닉스', 'KR', 'KOSPI', 'STOCK', true),
  ('005932', '삼성전자우', 'KR', 'KOSPI', 'STOCK', true),
  ('069500', 'KODEX 200', 'KR', 'KOSPI', 'ETF', true),
  ('325550', '미래에셋특수목적인수1호', 'KR', 'KOSDAQ', 'STOCK', true);
EOF
```

**장점**:
- 프로덕션 데이터 영향 없음
- 테스트 데이터 완전 제어 가능
- 롤백 걱정 없이 자유로운 테스트

**설정**:
```bash
# .env.test 파일 생성
cp .env .env.test
# POSTGRES_DB 수정
sed -i '' 's/POSTGRES_DB=quant_platform/POSTGRES_DB=quant_platform_test/' .env.test
```

---

#### 옵션 B: Dry-Run 모드 (프로덕션 DB 사용)
```python
# 데이터베이스 쓰기 없이 API 호출만 테스트
orchestrator.run_pipeline(
    regions=['KR'],
    steps=['fx_tracking', 'classification'],
    dry_run=True  # DB에 쓰지 않음
)
```

**장점**:
- 실제 프로덕션 데이터로 테스트
- DB 백업 불필요
- 빠른 검증 가능

**단점**:
- 데이터베이스 무결성 검증 불가
- UPSERT/UPDATE 로직 검증 제한

---

### 2. API 키 확인

**필수 API 키**:
```bash
# .env 파일 확인
grep -E "ALPHA_VANTAGE_API_KEY|DART_API_KEY|KIS_APP_KEY" .env

# 예상 출력:
# ALPHA_VANTAGE_API_KEY=FYIQQY5DKS0NSHIQ  ✅
# KIS_APP_KEY=PSBUu4h43WcP3aHElcJwWyo1NhxqBfRvxQn0  ✅
# DART_API_KEY=b0caf1311160f3418835bd6a9fc0e7ba6e4cc30b  ✅
```

**FXTracker**: `exchangerate.host` (API 키 불필요, 무료)
**StockClassifier**: pykrx (API 키 불필요)
**ETFUpdater**: pykrx (KR), yfinance (US) - API 키 불필요

---

## 🧪 테스트 시나리오

### **Tier 1: 개별 모듈 통합 테스트** (30분 예상)

#### Test 1.1: FXTracker 프로덕션 테스트
**목적**: 실제 환율 데이터 수집 및 DB 저장 검증

```python
# scripts/test_fx_tracker_production.py
import os
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.fx_tracking.fx_tracker import FXTracker

def test_fx_tracker_production():
    """FXTracker 프로덕션 통합 테스트"""

    # 1. DB 연결
    db = PostgresDatabaseManager()
    tracker = FXTracker(db_manager=db, base_currency='KRW')

    # 2. 환율 업데이트 실행
    currencies = ['USD', 'JPY', 'EUR', 'CNY']
    result = tracker.update_exchange_rates(
        currencies=currencies,
        dry_run=False  # 실제 DB에 저장
    )

    # 3. 결과 검증
    assert result['success'], "FX update failed"
    assert result['updated'] > 0, "No rates updated"

    print(f"✅ FX Tracker Test Passed")
    print(f"   - Updated: {result['updated']} rates")
    print(f"   - Signals: {result['signals']} FX signals")
    print(f"   - Rates: {result['rates']}")

    # 4. 데이터베이스 검증
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT quote_currency, rate, date
            FROM exchange_rates
            WHERE base_currency = 'KRW'
              AND date = CURRENT_DATE
            ORDER BY quote_currency
        """)

        rows = cursor.fetchall()
        assert len(rows) >= len(currencies), "Missing exchange rates in DB"

        print(f"\n📊 Database Verification:")
        for row in rows:
            print(f"   - {row[0]}: {row[1]:.2f} KRW (Date: {row[2]})")

    return result

if __name__ == '__main__':
    test_fx_tracker_production()
```

**예상 결과**:
```
✅ FX Tracker Test Passed
   - Updated: 4 rates
   - Signals: 0 FX signals
   - Rates: {'USD': Decimal('1350.50'), 'JPY': Decimal('10.25'), ...}

📊 Database Verification:
   - CNY: 185.30 KRW (Date: 2025-11-05)
   - EUR: 1450.75 KRW (Date: 2025-11-05)
   - JPY: 10.25 KRW (Date: 2025-11-05)
   - USD: 1350.50 KRW (Date: 2025-11-05)
```

**성공 기준**:
- ✅ `result['success'] == True`
- ✅ `result['updated'] >= len(currencies)`
- ✅ DB에 오늘 날짜 환율 데이터 존재
- ✅ Rate 값이 합리적 범위 (USD: 1200-1500 KRW)

---

#### Test 1.2: StockClassifier 프로덕션 테스트
**목적**: 실제 종목 분류 및 SPAC/우선주 탐지 검증

```python
# scripts/test_stock_classifier_production.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.classification.stock_classifier import StockClassifier

def test_stock_classifier_production():
    """StockClassifier 프로덕션 통합 테스트"""

    # 1. DB 연결
    db = PostgresDatabaseManager()
    classifier = StockClassifier(db_manager=db)

    # 2. KR 지역 분류 실행
    result = classifier.classify_region('KR')

    # 3. 결과 검증
    assert result['success'], "Classification failed"
    assert result['classified'] > 0, "No stocks classified"

    print(f"✅ Stock Classifier Test Passed")
    print(f"   - Classified: {result['classified']} stocks")
    print(f"   - SPAC: {result['spac_count']}")
    print(f"   - Preferred: {result['preferred_count']}")

    # 4. 데이터베이스 검증
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # 우선주 확인
        cursor.execute("""
            SELECT ticker, name, is_preferred, sector
            FROM tickers
            WHERE region = 'KR' AND is_preferred = TRUE
            LIMIT 5
        """)
        preferred_stocks = cursor.fetchall()

        # SPAC 확인
        cursor.execute("""
            SELECT ticker, name, is_spac, sector
            FROM tickers
            WHERE region = 'KR' AND is_spac = TRUE
            LIMIT 5
        """)
        spac_stocks = cursor.fetchall()

        print(f"\n📊 Database Verification:")
        print(f"   Preferred Stocks: {len(preferred_stocks)}")
        for row in preferred_stocks:
            print(f"     - {row[0]} ({row[1]}): Sector={row[3]}")

        print(f"   SPAC Stocks: {len(spac_stocks)}")
        for row in spac_stocks:
            print(f"     - {row[0]} ({row[1]}): Sector={row[3]}")

    return result

if __name__ == '__main__':
    test_stock_classifier_production()
```

**예상 결과**:
```
✅ Stock Classifier Test Passed
   - Classified: 2500 stocks
   - SPAC: 8
   - Preferred: 150

📊 Database Verification:
   Preferred Stocks: 5
     - 005932 (삼성전자우): Sector=Technology
     - 005387 (현대차2우B): Sector=Industrial
   SPAC Stocks: 2
     - 325550 (미래에셋특수목적인수1호): Sector=None
```

**성공 기준**:
- ✅ `result['success'] == True`
- ✅ `result['classified'] > 100`
- ✅ DB에 `is_preferred=true`, `is_spac=true` 레코드 존재
- ✅ 섹터 분류 일부 완료 (KR 시장)

---

#### Test 1.3: ETFUpdater 프로덕션 테스트
**목적**: ETF 메타데이터 및 보유 종목 수집 검증

```python
# scripts/test_etf_updater_production.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.etf_update.etf_updater import ETFUpdater

def test_etf_updater_production():
    """ETFUpdater 프로덕션 통합 테스트"""

    # 1. DB 연결
    db = PostgresDatabaseManager()
    updater = ETFUpdater(db_manager=db)

    # 2. KR 지역 ETF 업데이트
    result = updater.update_region(
        'KR',
        incremental=True,
        update_holdings=True
    )

    # 3. 결과 검증
    assert result['success'], "ETF update failed"
    assert result['etf_count'] > 0, "No ETFs updated"

    print(f"✅ ETF Updater Test Passed")
    print(f"   - ETFs: {result['etf_count']}")
    print(f"   - Holdings: {result['holdings_updated']}")

    # 4. 데이터베이스 검증
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # ETF 상세 확인
        cursor.execute("""
            SELECT ticker, name, total_assets, expense_ratio
            FROM etf_details
            WHERE region = 'KR'
            LIMIT 5
        """)
        etf_details = cursor.fetchall()

        # 보유 종목 확인
        cursor.execute("""
            SELECT etf_ticker, holding_ticker, weight
            FROM etf_holdings
            WHERE region = 'KR'
            LIMIT 10
        """)
        holdings = cursor.fetchall()

        print(f"\n📊 Database Verification:")
        print(f"   ETF Details: {len(etf_details)}")
        for row in etf_details:
            print(f"     - {row[0]} ({row[1]}): AUM={row[2]}, TER={row[3]}")

        print(f"   ETF Holdings: {len(holdings)} records")
        for row in holdings[:5]:
            print(f"     - {row[0]} holds {row[1]} ({row[2]:.2%})")

    return result

if __name__ == '__main__':
    test_etf_updater_production()
```

---

### **Tier 2: Orchestrator 통합 테스트** (45분 예상)

#### Test 2.1: 단일 Step 실행
**목적**: Orchestrator를 통한 개별 step 실행 검증

```python
# scripts/test_orchestrator_single_step.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator

def test_orchestrator_single_step():
    """Orchestrator 단일 step 테스트"""

    db = PostgresDatabaseManager()
    orchestrator = DatabaseUpdateOrchestrator(db, config={'limit': 10})

    # Test 1: FX Tracking
    result = orchestrator.run_pipeline(
        regions=['KR'],
        steps=['fx_tracking'],
        dry_run=False,
        incremental=True
    )

    assert 'fx_tracking' in result['steps_completed'], "FX tracking step not completed"
    print(f"✅ FX Tracking Step: {result['step_results']['fx_tracking']}")

    # Test 2: Classification
    result = orchestrator.run_pipeline(
        regions=['KR'],
        steps=['classification'],
        dry_run=False,
        incremental=True
    )

    assert 'classification' in result['steps_completed'], "Classification step not completed"
    print(f"✅ Classification Step: {result['step_results']['classification']}")

    # Test 3: ETF Data
    result = orchestrator.run_pipeline(
        regions=['KR'],
        steps=['etf_data'],
        dry_run=False,
        incremental=True
    )

    assert 'etf_data' in result['steps_completed'], "ETF data step not completed"
    print(f"✅ ETF Data Step: {result['step_results']['etf_data']}")

    return result

if __name__ == '__main__':
    test_orchestrator_single_step()
```

---

#### Test 2.2: 전체 파이프라인 실행
**목적**: 신규 모듈 통합한 전체 파이프라인 실행 검증

```python
# scripts/test_orchestrator_full_pipeline.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
import time

def test_full_pipeline():
    """전체 파이프라인 프로덕션 테스트"""

    db = PostgresDatabaseManager()
    orchestrator = DatabaseUpdateOrchestrator(
        db,
        config={
            'limit': 10,  # 테스트용 제한
            'validate': True,
            'fail_fast': False
        }
    )

    print("🚀 Starting Full Pipeline Test...")
    print("="*80)

    start_time = time.time()

    # 신규 모듈만 포함한 파이프라인
    result = orchestrator.run_pipeline(
        regions=['KR'],
        steps=[
            'ticker_refresh',  # 새 시스템
            'fx_tracking',     # Phase 1
            'classification',  # Phase 2
            'etf_data'         # Phase 3
        ],
        dry_run=False,
        incremental=True,
        use_rich_ui=True
    )

    duration = time.time() - start_time

    # 결과 검증
    print("\n" + "="*80)
    print("📊 Pipeline Execution Summary")
    print("="*80)
    print(f"Duration: {duration:.2f}s")
    print(f"Steps Completed: {len(result['steps_completed'])}/4")
    print(f"Steps Failed: {len(result['steps_failed'])}")

    for step in result['steps_completed']:
        print(f"  ✅ {step}: {result['step_results'][step]}")

    for step in result['steps_failed']:
        print(f"  ❌ {step}: {result['step_results'][step].get('error', 'Unknown')}")

    # 성공 기준
    assert len(result['steps_completed']) >= 3, "Less than 3 steps completed"
    assert len(result['steps_failed']) == 0, "Some steps failed"

    print("\n✅ Full Pipeline Test Passed!")
    return result

if __name__ == '__main__':
    test_full_pipeline()
```

**예상 실행 시간**:
- ticker_refresh: ~5분 (limit=10)
- fx_tracking: ~10초
- classification: ~30초 (limit=10)
- etf_data: ~1분 (limit=10)
- **총 예상**: 6-7분

---

#### Test 2.3: 재시도 로직 검증
**목적**: 네트워크 오류 시 exponential backoff 재시도 검증

```python
# scripts/test_orchestrator_retry_logic.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
from unittest.mock import patch

def test_retry_logic():
    """재시도 로직 프로덕션 검증"""

    db = PostgresDatabaseManager()
    orchestrator = DatabaseUpdateOrchestrator(db)

    # Mock FXTracker to fail twice, then succeed
    from modules.fx_tracking.fx_tracker import FXTracker
    original_update = FXTracker.update_exchange_rates

    call_count = 0
    def mock_update_with_failure(self, currencies, dry_run=False):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception(f"Simulated network error (attempt {call_count})")
        return original_update(self, currencies, dry_run)

    with patch.object(FXTracker, 'update_exchange_rates', mock_update_with_failure):
        result = orchestrator.run_pipeline(
            regions=['KR'],
            steps=['fx_tracking'],
            dry_run=False
        )

    # 3번째 시도에서 성공해야 함
    assert call_count == 3, f"Expected 3 attempts, got {call_count}"
    assert 'fx_tracking' in result['steps_completed'], "FX tracking should succeed on retry"

    print(f"✅ Retry Logic Test Passed")
    print(f"   - Total attempts: {call_count}")
    print(f"   - Final result: {result['step_results']['fx_tracking']}")

    return result

if __name__ == '__main__':
    test_retry_logic()
```

---

### **Tier 3: 데이터 품질 검증** (15분 예상)

#### Test 3.1: 데이터 무결성 검증

```python
# scripts/test_data_quality_validation.py
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.validators import DataQualityValidator

def test_data_quality():
    """데이터 품질 검증 테스트"""

    db = PostgresDatabaseManager()
    validator = DataQualityValidator(db)

    # 파이프라인 출력 검증
    validation_results = validator.validate_pipeline_output(['KR'])

    print("📊 Data Quality Validation Results")
    print("="*80)

    for region, result in validation_results.items():
        print(f"\n[{region}]")
        print(f"  Passed: {result.get('passed', False)}")

        for check_name, check_result in result.items():
            if check_name != 'passed':
                print(f"  - {check_name}: {check_result}")

    # 성공 기준
    assert validation_results['KR']['passed'], "Data quality validation failed for KR"

    print("\n✅ Data Quality Test Passed!")
    return validation_results

if __name__ == '__main__':
    test_data_quality()
```

---

## 📊 성공 메트릭 및 검증 기준

### 기능 검증
| 모듈 | 검증 항목 | 성공 기준 |
|------|----------|----------|
| **FXTracker** | 환율 수집 | ≥4개 통화 데이터 수집 |
| | DB 저장 | `exchange_rates` 테이블에 오늘 날짜 레코드 존재 |
| | FX 시그널 | 변동폭 >2% 시 시그널 생성 |
| **StockClassifier** | 종목 분류 | ≥100개 종목 분류 |
| | SPAC 탐지 | 특수목적인수 패턴 감지 |
| | 우선주 탐지 | Ticker suffix 2-9 감지 |
| | 섹터 분류 | Technology, Finance 등 8개 섹터 분류 |
| **ETFUpdater** | ETF 수집 | ≥50개 ETF 메타데이터 |
| | Holdings 업데이트 | ETF당 평균 ≥10개 보유 종목 |
| **Orchestrator** | 파이프라인 실행 | 4개 step 중 ≥3개 성공 |
| | 재시도 로직 | 2회 실패 후 3회째 성공 |
| | Checkpoint | 중단 후 resume 가능 |

### 성능 메트릭
| 항목 | 목표 | 측정 방법 |
|------|------|----------|
| **FX Tracking** | <30초 | `result['duration']` |
| **Classification** | <5분 (전체) | 단위: 초/종목 |
| **ETF Update** | <10분 (전체) | 단위: 초/ETF |
| **Full Pipeline** | <30분 | limit=100 기준 |
| **메모리 사용량** | <1GB | `psutil.Process().memory_info()` |

### 데이터 품질
| 검증 항목 | 기준 |
|----------|------|
| **NULL 비율** | <5% (필수 필드) |
| **중복 레코드** | 0개 (UNIQUE 제약) |
| **날짜 유효성** | 오늘 또는 최근 30일 이내 |
| **범위 검증** | USD: 1000-1500 KRW |

---

## 🚀 실행 가이드

### 1단계: 환경 준비 (5분)
```bash
# 1. 테스트 DB 생성 (옵션 A)
createdb quant_platform_test
pg_dump quant_platform --schema-only | psql quant_platform_test

# 2. 환경 변수 설정
export POSTGRES_DB=quant_platform_test
export TEST_MODE=production

# 3. 의존성 확인
python3 -c "from modules.fx_tracking.fx_tracker import FXTracker; print('✅ FXTracker OK')"
python3 -c "from modules.classification.stock_classifier import StockClassifier; print('✅ StockClassifier OK')"
python3 -c "from modules.etf_update.etf_updater import ETFUpdater; print('✅ ETFUpdater OK')"
```

### 2단계: Tier 1 테스트 실행 (30분)
```bash
# 개별 모듈 테스트
python3 scripts/test_fx_tracker_production.py
python3 scripts/test_stock_classifier_production.py
python3 scripts/test_etf_updater_production.py
```

### 3단계: Tier 2 통합 테스트 (45분)
```bash
# Orchestrator 통합
python3 scripts/test_orchestrator_single_step.py
python3 scripts/test_orchestrator_full_pipeline.py
python3 scripts/test_orchestrator_retry_logic.py
```

### 4단계: Tier 3 품질 검증 (15분)
```bash
# 데이터 품질 검증
python3 scripts/test_data_quality_validation.py
```

### 5단계: 결과 리포트 생성
```bash
# 테스트 결과 수집
python3 scripts/generate_test_report.py --output results/production_test_report_$(date +%Y%m%d).md
```

---

## 📝 테스트 체크리스트

### 사전 확인
- [ ] PostgreSQL 데이터베이스 실행 중
- [ ] TimescaleDB extension 활성화
- [ ] API 키 설정 완료 (.env 파일)
- [ ] 테스트 DB 준비 (quant_platform_test)
- [ ] 충분한 디스크 공간 (≥1GB)

### Tier 1: 개별 모듈
- [ ] FXTracker: 환율 수집 및 DB 저장
- [ ] StockClassifier: 종목 분류 및 탐지
- [ ] ETFUpdater: ETF 메타데이터 및 holdings

### Tier 2: Orchestrator
- [ ] 단일 step 실행 (fx_tracking, classification, etf_data)
- [ ] 전체 파이프라인 실행 (4개 step)
- [ ] 재시도 로직 검증 (exponential backoff)
- [ ] Checkpoint resume 검증

### Tier 3: 품질
- [ ] 데이터 무결성 (NULL, 중복, 범위)
- [ ] 성능 메트릭 (실행 시간, 메모리)
- [ ] 에러 핸들링 (예외 상황 복구)

### 사후 확인
- [ ] 테스트 DB 정리 (필요시)
- [ ] 테스트 리포트 생성 및 검토
- [ ] 발견된 이슈 문서화

---

## 🔧 트러블슈팅

### 문제 1: API 호출 실패
**증상**: `update_exchange_rates()` 실패, "API request failed"
**해결**:
```bash
# 1. 네트워크 연결 확인
curl -I https://api.exchangerate.host

# 2. API 키 확인 (Alpha Vantage)
echo $ALPHA_VANTAGE_API_KEY

# 3. Mock 모드로 대체 테스트
# fx_tracker.py에서 _get_mock_rates() 사용
```

### 문제 2: 데이터베이스 연결 실패
**증상**: `psycopg2.OperationalError: could not connect to server`
**해결**:
```bash
# 1. PostgreSQL 실행 상태 확인
pg_isready -h localhost -p 5432

# 2. 데이터베이스 존재 확인
psql -l | grep quant_platform_test

# 3. 권한 확인
psql quant_platform_test -c "\du"
```

### 문제 3: 테스트 timeout
**증상**: 테스트가 5분 이상 실행됨
**해결**:
```python
# config에 limit 추가
orchestrator = DatabaseUpdateOrchestrator(
    db,
    config={'limit': 5}  # 5개만 테스트
)
```

---

## 📄 다음 단계

### 테스트 통과 후
1. ✅ **프로덕션 배포 승인**: 모든 Tier 통과 시
2. 🔄 **스케줄링 설정**: `spock_refresh.py` 일일 실행 설정
3. 📊 **모니터링 설정**: Prometheus + Grafana 대시보드
4. 📚 **사용자 문서 작성**: 운영 가이드 작성

### 테스트 실패 시
1. 🐛 **이슈 분석**: 실패 원인 파악 및 문서화
2. 🔧 **코드 수정**: 필요 시 모듈 수정
3. 🔁 **재테스트**: 수정 후 전체 테스트 재실행

---

**테스트 플랜 버전**: 1.0
**마지막 업데이트**: 2025-11-05
**담당자**: Spock Quant Platform Team
