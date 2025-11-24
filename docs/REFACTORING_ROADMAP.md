# spock_refresh.py 리팩토링 로드맵

**프로젝트:** spock_refresh.py 성능 최적화 및 구조 개선
**시작일:** 2025-11-23
**예상 기간:** 2-4주
**목표:** 성능 50-80% 향상, 유지보수성 대폭 개선

---

## 📊 현재 상태 분석

### 주요 문제점
1. **DB 연결 남발** - 함수 호출마다 새 연결 생성 (10+ 연결/요청)
2. **비효율적 쿼리** - N+1 패턴 (10개 이상의 개별 쿼리)
3. **캐싱 없음** - 동일 데이터 반복 조회
4. **코드 중복** - 30% 이상 중복 코드
5. **순차 처리** - 병렬 가능한 작업도 순차 실행
6. **매직 넘버** - 하드코딩된 상수들
7. **일관성 없는 에러 처리** - try-except pass 남발

### 측정 지표 (Baseline)
- **파일 크기:** 3,981줄
- **상태 조회 시간:** ~500ms
- **DB 쿼리 수:** 10+ (상태 조회 시)
- **캐시 히트율:** 0%
- **코드 중복:** ~30%
- **테스트 커버리지:** 0%

---

## 🎯 우선순위별 작업 계획

### Priority 0: Quick Wins (Week 1)
**목표:** 1주 내 30-40% 성능 향상

#### Day 1 (월) - DB 연결 최적화 ⚡
**작업:** DB 컨텍스트 매니저 구현
**파일:** `spock_refresh_v2.py` (새 파일)

**예상 효과:**
- ✓ 연결 오버헤드 40% 감소
- ✓ 리소스 누수 방지
- ✓ 코드 간결성 30% 향상

**체크리스트:**
- [ ] DBConnectionManager 싱글톤 클래스 작성
- [ ] 컨텍스트 매니저 구현 (@contextmanager)
- [ ] get_database_status() 리팩토링
- [ ] get_listing_date_coverage() 리팩토링
- [ ] get_listing_date_coverage_detailed() 리팩토링
- [ ] get_macro_data_status() 리팩토링
- [ ] get_macro_data_status_unified() 리팩토링
- [ ] get_equity_backfill_status() 리팩토링
- [ ] print_database_status() 리팩토링
- [ ] print_listing_date_status() 리팩토링
- [ ] 기타 DB 조회 함수들 적용
- [ ] 성능 벤치마크 스크립트 작성
- [ ] Before/After 성능 측정
- [ ] 메모리 프로파일링

**검증 기준:**
- DB 연결 수: 10개 → 1-2개 재사용
- 응답 시간: 500ms → 300ms
- 메모리 누수: 0건
- 기능 회귀: 0건

**구현 상세:**
```python
# 1. DBConnectionManager 싱글톤
class DBConnectionManager:
    _instance = None
    _lock = threading.Lock()

    @contextmanager
    def session(self) -> Generator:
        db = PostgresDatabaseManager()
        try:
            yield db
        finally:
            db.close_pool()

# 2. 전역 인스턴스
db_manager = DBConnectionManager()

# 3. 사용 패턴
def get_database_status():
    with db_manager.session() as db:
        # 모든 쿼리 실행
        pass
```

---

#### Day 2 (화) - 쿼리 캐싱 구현 💾
**작업:** TTL 기반 쿼리 결과 캐싱

**예상 효과:**
- ✓ 반복 쿼리 90% 감소
- ✓ 메뉴 응답 즉시 (< 10ms)
- ✓ DB 부하 70% 감소

**체크리스트:**
- [ ] QueryCache 클래스 구현
- [ ] TTL 기반 만료 로직
- [ ] 스레드 안전성 보장 (threading.Lock)
- [ ] get_database_status() 캐싱 적용
- [ ] get_listing_date_coverage() 캐싱 적용
- [ ] interactive_menu()에 통합
- [ ] 캐시 무효화 로직 (업데이트 후)
- [ ] 캐시 히트율 측정 기능
- [ ] 성능 벤치마크

**검증 기준:**
- 두 번째 호출 시간: < 5ms
- 캐시 히트율: > 85%
- 메모리 증가: < 10MB

---

#### Day 3 (수) - 상수 추출 & 중복 함수 통합 🔧
**작업 A:** 매직 넘버 상수화 (반나절)

**체크리스트:**
- [ ] RefreshConstants 클래스 생성
- [ ] Freshness 임계값 (0, 3, 7, 14일)
- [ ] RegionTiming 처리 시간
- [ ] BatchSize 기본값
- [ ] CacheTTL 설정
- [ ] 전역 검색 & 치환 (days_old <= 3 등)
- [ ] 기존 REFRESH_CONFIG 통합

**작업 B:** 중복 함수 통합 (반나절)

**체크리스트:**
- [ ] select_regions() + select_regions_custom() → 통합
- [ ] print_*_status() 함수들 템플릿화
- [ ] run_*_backfill() 공통 로직 추출
- [ ] 중복 코드 제거

**검증 기준:**
- 코드 중복: 30% → 20%
- 유지보수 포인트: 50% 감소

---

#### Day 4 (목) - Week 1 통합 & 벤치마크 📊
**작업:** P0 작업 통합 및 성능 측정

**체크리스트:**
- [ ] 모든 P0 변경사항 통합 테스트
- [ ] 기능 회귀 테스트 (모든 메뉴 옵션)
- [ ] 종합 성능 벤치마크
- [ ] 메모리 프로파일링
- [ ] 코드 리뷰 및 정리
- [ ] Week 1 완료 보고서 작성

**벤치마크 항목:**
1. 상태 조회 시간: 500ms → <200ms
2. 메뉴 응답 시간: 500ms → <50ms
3. DB 연결 수: 함수당 1개 → 재사용
4. 캐시 히트율: 0% → >85%

**성공 기준:**
- ✅ 모든 기존 기능 100% 동작
- ✅ 성능 30% 이상 향상
- ✅ 위험 요소 0개
- ✅ 코드 품질 개선

---

### Priority 1: High Impact (Week 2)
**목표:** 2주 내 50-70% 성능 향상

#### Day 5-6 (월-화) - 쿼리 통합 (N+1 해결) 🚀
**작업:** 여러 쿼리를 단일 CTE 쿼리로 통합

**우선순위 함수:**
1. `get_database_status()` - 10개 쿼리 → 1개
2. `get_listing_date_coverage_detailed()` - 3개 쿼리 → 1개
3. `get_macro_data_status_unified()` - 4개 쿼리 → 1개

**예상 효과:**
- ✓ 쿼리 실행 시간 70% 감소
- ✓ DB 부하 60% 감소
- ✓ 네트워크 왕복 90% 감소

**Day 5 체크리스트:**
- [ ] OptimizedQueries 클래스 생성
- [ ] get_database_status_unified() CTE 쿼리 작성
- [ ] JSON 결과 파싱 로직 구현
- [ ] 기존 함수와 결과 비교 테스트
- [ ] 성능 벤치마크 (10개 쿼리 vs 1개)

**Day 6 체크리스트:**
- [ ] get_listing_date_coverage_unified() 구현
- [ ] get_macro_data_status_unified() 구현
- [ ] 모든 status 함수에 적용
- [ ] 에러 처리 추가
- [ ] 최종 성능 벤치마크

---

#### Day 7-8 (수-목) - 병렬 처리 구현 ⚡⚡
**작업:** 다중 지역 작업 병렬화

**대상 함수:**
1. `_run_technical_indicators_direct()` - 지역별 병렬
2. `run_listing_date_backfill()` - 해외 지역 병렬
3. 기타 다중 지역 작업

**예상 효과:**
- ✓ 다중 지역 작업 3-4배 빠름
- ✓ CPU 활용률 향상
- ✓ 전체 실행 시간 50% 감소

**Day 7 체크리스트:**
- [ ] ParallelExecutor 클래스 생성
- [ ] ThreadPoolExecutor 통합
- [ ] 진행률 추적 구현
- [ ] 에러 수집 메커니즘
- [ ] `_run_technical_indicators_direct()` 병렬화

**Day 8 체크리스트:**
- [ ] `run_listing_date_backfill()` 병렬화
- [ ] 다른 다중 지역 함수들 적용
- [ ] max_workers 튜닝 (4개 적정)
- [ ] 최종 성능 테스트
- [ ] 벤치마크 (순차 vs 병렬)

---

#### Day 9 (금) - 에러 처리 통일 🛡️
**작업:** 일관된 에러 처리 계층 구축

**현재 문제:**
- try-except pass (조용한 실패)
- 불일치한 에러 메시지
- 로깅 누락

**체크리스트:**
- [ ] 커스텀 예외 클래스 정의
  - RefreshError (기본)
  - DatabaseConnectionError
  - QueryExecutionError
  - DataNotFoundError
- [ ] ErrorHandler 데코레이터 구현
- [ ] loguru 로깅 설정
- [ ] 모든 DB 작업에 적용
- [ ] 에러 복구 메커니즘

---

#### Day 10 (토) - Week 2 통합 & 중간 점검 📊
**작업:** P1 완료 및 전체 성능 측정

**체크리스트:**
- [ ] Week 1 + Week 2 통합
- [ ] 전체 기능 회귀 테스트
- [ ] 종합 성능 벤치마크
- [ ] 코드 리뷰 및 리팩토링
- [ ] Week 2 완료 보고서

**성능 목표 검증:**
- ✓ 상태 조회: 500ms → <50ms (90% 향상)
- ✓ 다중 지역 작업: 3-4배 빠름
- ✓ 캐시 히트율: >85%
- ✓ 코드 중복: 30% → 15%
- ✓ DB 쿼리 수: 70% 감소

**Week 2 마일스톤:**
- ✅ 쿼리 통합 완료
- ✅ 병렬 처리 구현
- ✅ 에러 처리 통일
- ✅ 성능 50-70% 향상 달성

---

### Priority 2: Architecture (Week 3-4) - 조건부 진행
**조건:** Week 2까지 목표 달성 시에만 진행

#### Week 3: 서비스 레이어 분리
**목표:** 유지보수성 50% 향상

**체크리스트:**
- [ ] spock_refresh/ 디렉토리 구조 생성
- [ ] services/ 레이어 구현
  - [ ] database_service.py
  - [ ] status_service.py
  - [ ] backfill_service.py
- [ ] models/ 레이어 구현
  - [ ] status.py (데이터클래스)
  - [ ] enums.py (상수)
- [ ] 기존 함수 마이그레이션

#### Week 4: 모듈화 완성
**목표:** 테스트 가능성 80% 향상

**체크리스트:**
- [ ] db/ 레이어 완성
  - [ ] connection.py
  - [ ] queries.py
  - [ ] cache.py
- [ ] cli/ 레이어 분리
  - [ ] menu.py
  - [ ] prompts.py
  - [ ] formatters.py
- [ ] main.py 재작성
- [ ] 테스트 작성
- [ ] 문서화

---

## 📊 성공 지표 (KPI)

### Week 1 목표
| 지표 | 현재 | 목표 | 측정 방법 |
|------|------|------|----------|
| 상태 조회 시간 | 500ms | 200ms | benchmark_week1.py |
| 캐시 히트율 | 0% | 85% | query_cache.hit_rate |
| DB 연결 수 | 10+/요청 | 1-2 재사용 | 로그 모니터링 |
| 코드 중복 | 30% | 20% | jscpd |
| 메모리 누수 | ? | 0 | memory_profiler |

### Week 2 목표
| 지표 | Week 1 후 | 목표 | 측정 방법 |
|------|-----------|------|----------|
| 상태 조회 시간 | 200ms | <50ms | benchmark_week2.py |
| DB 쿼리 수 | 10+ | 1-2 | 쿼리 로깅 |
| 다중 지역 시간 | 100% | 25% (4배) | 실행 시간 비교 |
| 에러 추적 | 불가 | 가능 | 로그 품질 |
| 코드 중복 | 20% | 10% | jscpd |

---

## 🚨 위험 관리

### 주요 위험 요소

1. **기능 회귀 (High)**
   - **완화:** 광범위한 수동 테스트, 점진적 마이그레이션
   - **대응:** 즉시 롤백 가능한 Git 브랜치 관리

2. **성능 저하 (Medium)**
   - **완화:** 각 단계별 벤치마크
   - **대응:** 최적화 우선순위 재조정

3. **일정 지연 (Medium)**
   - **완화:** 주간 체크포인트, 우선순위 기반 진행
   - **대응:** P2 작업 스킵, Week 2까지만 진행

4. **데이터 손실 (Low)**
   - **완화:** DB 작업 최소화, 읽기 중심
   - **대응:** 백업 자동화

---

## 🔍 품질 게이트

### Week 1 완료 조건
- ✅ DB 연결 컨텍스트 매니저 동작
- ✅ 쿼리 캐싱 히트율 > 85%
- ✅ 모든 기존 기능 100% 동작
- ✅ 성능 30% 이상 향상
- ✅ 코드 리뷰 통과

### Week 2 완료 조건
- ✅ 통합 쿼리 < 100ms
- ✅ 병렬 처리 3배 이상 속도 향상
- ✅ 에러 처리 통일
- ✅ 성능 50-70% 향상
- ✅ 코드 중복 < 15%

### Week 3-4 진행 조건
- ✅ Week 2 모든 목표 달성
- ✅ 시간 여유 확보
- ✅ 팀 승인

---

## 📁 파일 구조

### 현재 (As-Is)
```
spock_refresh.py (3,981 lines)
```

### Week 1-2 후 (To-Be - Phase 1)
```
spock_refresh.py (3,981 lines) - 원본 유지
spock_refresh_v2.py (~2,500 lines) - 개선 버전
benchmark_week1.py - 성능 측정
benchmark_week2.py - 성능 측정
docs/REFACTORING_ROADMAP.md - 이 문서
docs/WEEK1_COMPLETION_REPORT.md - Week 1 보고서
docs/WEEK2_COMPLETION_REPORT.md - Week 2 보고서
```

### Week 3-4 후 (To-Be - Phase 2) - 선택적
```
spock_refresh/ (모듈화)
├── __init__.py
├── main.py
├── cli/
├── services/
├── models/
├── db/
└── utils/
```

---

## 🚀 시작하기

### 현재 진행 상황
- ✅ 분석 완료
- ✅ 로드맵 작성 완료
- 🔄 **Day 1 진행 중**

### 다음 단계
1. spock_refresh_v2.py 생성
2. DBConnectionManager 구현
3. 10개 함수 리팩토링
4. 벤치마크 실행

---

**마지막 업데이트:** 2025-11-23
**작성자:** Claude + 13ruce
**버전:** 1.0
