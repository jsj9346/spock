# Blacklist Integration - Phases 5-8 TODO

**Status**: Pending (waiting for dependent modules)
**Created**: 2025-10-17
**Last Updated**: 2025-10-17

---

## Overview

Phases 1-4 완료 (24/24 tests passed ✅):
- ✅ Phase 1: Trading Engine integration (6/6 tests)
- ✅ Phase 2: Stock Scanner integration (6/6 tests)
- ✅ Phase 3: Data Collector integration (6/6 tests)
- ✅ Phase 4: Technical Filter integration (6/6 tests)

이 문서는 나머지 Phase 5-8의 작업 계획을 담고 있습니다.

---

## Phase 5: GPT Analyzer Integration

### 의존성
- **모듈**: `modules/stock_gpt_analyzer.py`
- **상태**: ⚠️ 모듈 완성 필요
- **GPT API**: OpenAI GPT-4 API 통합 필요

### 작업 내용

#### 1. 코드 통합 (`modules/stock_gpt_analyzer.py`)
```python
# In __init__ method:
try:
    from modules.blacklist_manager import BlacklistManager
    from modules.db_manager_sqlite import SQLiteDatabaseManager

    db_manager = SQLiteDatabaseManager(db_path=db_path)
    self.blacklist_manager = BlacklistManager(db_manager=db_manager)
    logger.info("✅ BlacklistManager initialized for GPT Analyzer")

except Exception as e:
    logger.warning(f"⚠️ BlacklistManager initialization failed: {e}")
    self.blacklist_manager = None
```

#### 2. 블랙리스트 필터링 로직
- **위치**: GPT 분석 요청 전 (API 호출 비용 절감)
- **방식**: Bulk filtering (`filter_blacklisted_tickers()`)
- **통계**: blacklist_passed, blacklist_rejected 추적

```python
# In analyze_stocks method (before GPT API calls):
if self.blacklist_manager:
    ticker_codes = [t['ticker'] for t in tickers]
    blacklist_filtered = self.blacklist_manager.filter_blacklisted_tickers(ticker_codes, self.region)
    blacklist_rejected = len(ticker_codes) - len(blacklist_filtered)

    if blacklist_rejected > 0:
        logger.info(f"🚫 Blacklist filter: Removed {blacklist_rejected} tickers")
        tickers = [t for t in tickers if t['ticker'] in blacklist_filtered]
```

#### 3. 통계 로깅
```python
logger.info(f"📊 GPT Analysis Summary:")
logger.info(f"   • Input tickers:          {total_input}")
logger.info(f"   • Blacklist rejected:     {blacklist_rejected}")
logger.info(f"   • Blacklist passed:       {len(tickers)}")
logger.info(f"   • GPT analyzed:           {analyzed_count}")
```

#### 4. 단위 테스트 (`tests/test_gpt_analyzer_blacklist.py`)

**Test Cases** (6 tests):
1. `test_01_db_blacklist_filtering_before_gpt_analysis`
2. `test_02_file_blacklist_filtering_before_gpt_analysis`
3. `test_03_non_blacklisted_pass_through`
4. `test_04_blacklist_filter_before_gpt_api_calls`
5. `test_05_bulk_filtering_used`
6. `test_06_statistics_logging`

### 예상 작업 시간
- 코드 통합: 30분
- 테스트 작성: 45분
- 테스트 실행 및 디버깅: 30분
- **총 예상**: 1.5-2시간

---

## Phase 6: Kelly Calculator Integration

### 의존성
- **모듈**: `modules/kelly_calculator.py`
- **상태**: ⚠️ 모듈 완성 필요
- **통합**: Pattern-based position sizing 계산기

### 작업 내용

#### 1. 코드 통합 (`modules/kelly_calculator.py`)
```python
# In __init__ method:
try:
    from modules.blacklist_manager import BlacklistManager
    from modules.db_manager_sqlite import SQLiteDatabaseManager

    db_manager = SQLiteDatabaseManager(db_path=db_path)
    self.blacklist_manager = BlacklistManager(db_manager=db_manager)
    logger.info("✅ BlacklistManager initialized for Kelly Calculator")

except Exception as e:
    logger.warning(f"⚠️ BlacklistManager initialization failed: {e}")
    self.blacklist_manager = None
```

#### 2. 블랙리스트 필터링 로직
- **위치**: Position sizing 계산 전
- **방식**: Bulk filtering (`filter_blacklisted_tickers()`)
- **통계**: blacklist_passed, blacklist_rejected 추적

```python
# In calculate_positions method (before Kelly formula):
if self.blacklist_manager:
    ticker_codes = [t['ticker'] for t in tickers]
    blacklist_filtered = self.blacklist_manager.filter_blacklisted_tickers(ticker_codes, self.region)
    blacklist_rejected = len(ticker_codes) - len(blacklist_filtered)

    if blacklist_rejected > 0:
        logger.info(f"🚫 Blacklist filter: Removed {blacklist_rejected} tickers")
        tickers = [t for t in tickers if t['ticker'] in blacklist_filtered]
```

#### 3. 통계 로깅
```python
logger.info(f"📊 Kelly Calculator Summary:")
logger.info(f"   • Input tickers:          {total_input}")
logger.info(f"   • Blacklist rejected:     {blacklist_rejected}")
logger.info(f"   • Blacklist passed:       {len(tickers)}")
logger.info(f"   • Position calculated:    {calculated_count}")
```

#### 4. 단위 테스트 (`tests/test_kelly_calculator_blacklist.py`)

**Test Cases** (6 tests):
1. `test_01_db_blacklist_filtering_before_kelly_calculation`
2. `test_02_file_blacklist_filtering_before_kelly_calculation`
3. `test_03_non_blacklisted_pass_through`
4. `test_04_blacklist_filter_before_kelly_formula`
5. `test_05_bulk_filtering_used`
6. `test_06_statistics_logging`

### 예상 작업 시간
- 코드 통합: 30분
- 테스트 작성: 45분
- 테스트 실행 및 디버깅: 30분
- **총 예상**: 1.5-2시간

---

## Phase 7: Remove Legacy Blacklist Code

### 의존성
- **Phase 1-6 완료**: 모든 모듈이 BlacklistManager로 마이그레이션 완료
- **E2E 테스트 완료**: Phase 8 완료 후 안전하게 제거

### 작업 내용

#### 1. Legacy 코드 제거 (`modules/stock_utils.py`)

**제거 대상** (lines 498-610):
- `load_stock_blacklist()` 함수
- `is_blacklisted()` 함수
- `add_to_blacklist()` 함수
- `remove_from_blacklist()` 함수
- Legacy blacklist 관련 주석 및 문서

#### 2. 영향 분석
```bash
# Legacy 함수 사용 여부 확인
grep -r "load_stock_blacklist" modules/ tests/
grep -r "is_blacklisted" modules/ tests/ | grep -v "blacklist_manager"
grep -r "add_to_blacklist" modules/ tests/ | grep -v "blacklist_manager"
grep -r "remove_from_blacklist" modules/ tests/ | grep -v "blacklist_manager"
```

#### 3. 마이그레이션 가이드 생성

**문서**: `docs/BLACKLIST_MIGRATION_GUIDE.md`

**내용**:
- Legacy 코드에서 BlacklistManager로 마이그레이션 가이드
- API 변경 사항 정리
- 예제 코드 변환

**Before (Legacy)**:
```python
from modules.stock_utils import is_blacklisted

if is_blacklisted(ticker):
    # Skip processing
    pass
```

**After (New)**:
```python
from modules.blacklist_manager import BlacklistManager

blacklist_manager = BlacklistManager(db_manager)
if blacklist_manager.is_blacklisted(ticker, region):
    # Skip processing
    pass
```

#### 4. 검증 테스트
```bash
# All tests should still pass after removal
python3 -m pytest tests/test_*_blacklist.py -v

# E2E tests should pass
python3 tests/test_e2e_blacklist_integration.py -v
```

### 예상 작업 시간
- Legacy 코드 분석: 30분
- 코드 제거: 15분
- 마이그레이션 가이드 작성: 1시간
- 검증 테스트: 30분
- **총 예상**: 2-2.5시간

---

## Phase 8: E2E Integration Tests

### 의존성
- **Phase 1-6 완료**: 모든 모듈이 BlacklistManager 통합 완료
- **전체 시스템 구축**: spock.py 메인 파이프라인 완성

### 작업 내용

#### 1. E2E 테스트 시나리오 설계

**Test Scenarios**:

##### Scenario 1: 전체 파이프라인 (블랙리스트 포함)
```
Stock Scanner → Data Collector → Technical Filter → GPT Analyzer → Kelly Calculator → Trading Engine
     ↓               ↓                  ↓                  ↓                 ↓              ↓
 Blacklist      Blacklist          Blacklist         Blacklist         Blacklist      Blacklist
   Filter         Filter             Filter            Filter            Filter         Filter
```

##### Scenario 2: DB 블랙리스트 (영구 제외)
- 상장폐지 종목이 모든 단계에서 자동 필터링되는지 확인

##### Scenario 3: File 블랙리스트 (임시 제외)
- 만료일이 있는 블랙리스트가 올바르게 처리되는지 확인
- 만료 후 자동으로 제거되는지 확인

##### Scenario 4: 크로스 리전 블랙리스트
- KR, US, HK, CN, JP, VN 각 시장별 블랙리스트 독립성 확인

#### 2. E2E 테스트 파일 생성

**파일**: `tests/test_e2e_blacklist_integration.py`

```python
"""
E2E Blacklist Integration Tests

Tests the end-to-end blacklist functionality across the entire Spock pipeline.
Validates that blacklisted tickers are filtered out at every stage.

Author: Spock Trading System
Created: 2025-10-17
"""

class TestE2EBlacklistIntegration(unittest.TestCase):
    """E2E test suite for blacklist integration"""

    def test_01_full_pipeline_db_blacklist(self):
        """Test full pipeline with DB blacklist (permanent exclusion)"""
        pass

    def test_02_full_pipeline_file_blacklist(self):
        """Test full pipeline with file blacklist (temporary exclusion)"""
        pass

    def test_03_blacklist_expiry_handling(self):
        """Test that expired blacklist entries are automatically removed"""
        pass

    def test_04_cross_region_blacklist_independence(self):
        """Test that blacklists are independent across regions"""
        pass

    def test_05_statistics_aggregation(self):
        """Test that blacklist statistics are properly aggregated"""
        pass

    def test_06_performance_benchmark(self):
        """Test that blacklist filtering doesn't significantly impact performance"""
        pass
```

#### 3. 통합 통계 리포트

**출력 예시**:
```
============================================================
E2E BLACKLIST INTEGRATION REPORT
============================================================

Pipeline Stage               Input   Blacklist   Passed   Success Rate
--------------------------------------------------------------------
1. Stock Scanner             2,500        50     2,450       98.0%
2. Data Collector            2,450        10     2,440       99.6%
3. Technical Filter          2,440         5     2,435       99.8%
4. GPT Analyzer                250         2       248       99.2%
5. Kelly Calculator            248         1       247       99.6%
6. Trading Engine              247         0       247      100.0%
--------------------------------------------------------------------
Total Blacklist Filtered: 68 tickers
Overall Success Rate: 98.9%

Performance Metrics:
- Total execution time: 45.2s
- Blacklist overhead: 0.8s (1.8%)
- Database queries: 156
- API calls saved: 68 (blocked before execution)
============================================================
```

#### 4. 성능 벤치마크

**측정 항목**:
- 블랙리스트 필터링 오버헤드 (<2% 목표)
- 절약된 API 호출 횟수
- 데이터베이스 쿼리 최적화 효과
- 메모리 사용량 비교

### 예상 작업 시간
- E2E 시나리오 설계: 1시간
- 테스트 코드 작성: 2시간
- 통계 리포트 구현: 1시간
- 테스트 실행 및 디버깅: 1.5시간
- **총 예상**: 5-6시간

---

## 작업 순서 및 일정

### 권장 작업 순서
1. **Phase 5**: GPT Analyzer integration (GPT API 통합 완료 후)
2. **Phase 6**: Kelly Calculator integration (Kelly 모듈 완성 후)
3. **Phase 8**: E2E integration tests (Phase 5-6 완료 후)
4. **Phase 7**: Remove legacy code (Phase 8 검증 완료 후)

### 의존성 체크리스트

#### Phase 5 시작 조건
- [ ] `modules/stock_gpt_analyzer.py` 모듈 완성
- [ ] OpenAI GPT-4 API 키 설정 완료
- [ ] GPT 분석 기본 기능 동작 확인

#### Phase 6 시작 조건
- [ ] `modules/kelly_calculator.py` 모듈 완성
- [ ] Pattern-based position sizing 로직 완성
- [ ] Kelly Formula 계산 기능 동작 확인

#### Phase 8 시작 조건
- [ ] Phase 1-6 모두 완료 (36/36 tests passed)
- [ ] `spock.py` 메인 파이프라인 완성
- [ ] 전체 시스템 통합 동작 확인

#### Phase 7 시작 조건
- [ ] Phase 1-6 완료
- [ ] Phase 8 E2E 테스트 통과
- [ ] 모든 모듈이 BlacklistManager 사용 확인
- [ ] Legacy 코드 사용처 0개 확인

---

## 테스트 목표

### 최종 목표
- **단위 테스트**: 36/36 tests passed (Phase 1-6)
- **E2E 테스트**: 6/6 tests passed (Phase 8)
- **총 테스트**: 42/42 tests passed (100% success rate)
- **코드 커버리지**: >80% (blacklist 관련 코드)

### 성능 목표
- 블랙리스트 필터링 오버헤드: <2%
- API 호출 절감: >95% (블랙리스트 종목 대상)
- 데이터베이스 쿼리 최적화: Bulk operations (N→1 쿼리)

---

## 참고 문서

### 완료된 작업
- `modules/blacklist_manager.py` - Core blacklist manager (lines 1-651)
- `modules/blacklist_cli.py` - CLI management tool (lines 1-343)
- `scripts/manage_blacklist.py` - Standalone CLI script (lines 1-343)
- `tests/test_blacklist_manager.py` - Unit tests (18/18 passed)
- `tests/test_trading_engine_blacklist.py` - Phase 1 tests (6/6 passed)
- `tests/test_scanner_blacklist.py` - Phase 2 tests (6/6 passed)
- `tests/test_data_collector_blacklist.py` - Phase 3 tests (6/6 passed)
- `tests/test_technical_filter_blacklist.py` - Phase 4 tests (6/6 passed)

### 설계 문서
- `spock_PRD.md` - Product Requirements Document
- `GLOBAL_MARKET_EXPANSION.md` - Multi-region architecture
- `docs/BLACKLIST_SYSTEM_DESIGN.md` - Blacklist system architecture

---

## 연락처

**작성자**: Claude Code SuperClaude
**프로젝트**: Spock Trading System
**마지막 업데이트**: 2025-10-17

---

## 버전 히스토리

- **v1.0** (2025-10-17): 초안 작성, Phase 5-8 TODO 정리
