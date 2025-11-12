# 문서 인덱스 (Documentation Index)

**프로젝트 문서 통합 가이드 - 사용자 유형별 학습 경로**

---

## 📚 빠른 시작 (Start Here)

처음 프로젝트를 접하신다면 **아래 순서대로** 읽어주세요:

1. **[GETTING_STARTED.md](GETTING_STARTED.md)** ⭐ **처음 시작하는 분 필독**
   - 프로젝트가 무엇인지 이해하기
   - 15분 안에 설치 및 첫 실행
   - FAQ와 학습 경로

2. **[README.md](README.md)** - 프로젝트 전체 개요
   - 아키텍처 및 기능 소개
   - 설치 가이드
   - 성공 메트릭

3. **[QUICKSTART.md](QUICKSTART.md)** - 5분 빠른 시작
   - 최소한의 설정으로 빠르게 체험
   - 주요 명령어 치트시트

---

## 👤 사용자 유형별 문서 가이드

### 🔰 초보자 (처음 사용하는 분)

**학습 순서**: 순서대로 읽으면 가장 효율적입니다.

| 순서 | 문서 | 예상 시간 | 설명 |
|------|------|----------|------|
| 1 | [GETTING_STARTED.md](GETTING_STARTED.md) | 20분 | 프로젝트 이해 + 설치 + 첫 실행 |
| 2 | [README.md](README.md) | 15분 | 전체 기능과 아키텍처 개요 |
| 3 | [QUICKSTART.md](QUICKSTART.md) | 10분 | 핵심 명령어와 워크플로우 |
| 4 | [docs/CLI_USAGE_GUIDE.md](docs/CLI_USAGE_GUIDE.md) | 30분 | CLI 명령어 상세 가이드 |
| 5 | [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) | 45분 | 올바른 백테스팅 방법 |

**핵심 참고 자료**:
- [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md) - 문제 발생 시
- [FAQ 섹션](GETTING_STARTED.md#-자주-묻는-질문-faq) - 자주 묻는 질문

---

### 💻 개발자 (코드 기여 또는 커스터마이징)

**학습 순서**: 아키텍처 이해 → 데이터 구조 → 핵심 모듈 순서

| 순서 | 문서 | 예상 시간 | 설명 |
|------|------|----------|------|
| 1 | [CLAUDE.md](CLAUDE.md) | 60분 | 프로젝트 전체 구조와 개발 철학 |
| 2 | [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | 30분 | PostgreSQL + TimescaleDB 스키마 |
| 3 | [docs/QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md) | 45분 | 백테스팅 엔진 비교 및 선택 |
| 4 | [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md) | 30분 | 팩터 정의 및 계산 방법 |
| 5 | [docs/QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md) | 40분 | 실제 개발 워크플로우 |

**추가 개발 리소스**:
- [docs/QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md) - 15주 개발 로드맵
- [docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md](docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md) - Phase 1 상세 계획
- [docs/WEEK4_COMPLETION_REPORT.md](docs/WEEK4_COMPLETION_REPORT.md) - 최신 개발 현황

**코드 품질 및 테스팅**:
- [docs/VALIDATION_FRAMEWORK_GUIDE.md](docs/VALIDATION_FRAMEWORK_GUIDE.md) - 검증 프레임워크
- [docs/PERFORMANCE_TUNING_GUIDE.md](docs/PERFORMANCE_TUNING_GUIDE.md) - 성능 최적화

---

### 🚀 운영자 (프로덕션 환경 관리)

**학습 순서**: 배포 → 운영 → 모니터링 순서

| 순서 | 문서 | 예상 시간 | 설명 |
|------|------|----------|------|
| 1 | [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 45분 | 프로덕션 배포 가이드 |
| 2 | [docs/POSTGRES_SETUP_GUIDE.md](docs/POSTGRES_SETUP_GUIDE.md) | 30분 | PostgreSQL 설정 및 최적화 |
| 3 | [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) | 60분 | 일상 운영 절차 |
| 4 | [docs/QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md) | 40분 | 모니터링 및 알림 설정 |
| 5 | [docs/MIGRATION_RUNBOOK.md](docs/MIGRATION_RUNBOOK.md) | 30분 | 데이터 마이그레이션 |

**운영 관련 추가 자료**:
- [docs/POSTGRES_OPERATIONS.md](docs/POSTGRES_OPERATIONS.md) - PostgreSQL 운영
- [docs/DATABASE_MAINTENANCE_IMPLEMENTATION_REPORT.md](docs/DATABASE_MAINTENANCE_IMPLEMENTATION_REPORT.md) - DB 유지보수
- [docs/COMPRESSION_GUIDE.md](docs/COMPRESSION_GUIDE.md) - 데이터 압축 전략

**모니터링 및 알림**:
- Prometheus 메트릭 설정
- Grafana 대시보드 구성
- 알림 규칙 설정

---

### 📊 퀀트 연구자 (전략 개발 및 백테스팅)

**학습 순서**: 백테스팅 → 팩터 분석 → 포트폴리오 최적화

| 순서 | 문서 | 예상 시간 | 설명 |
|------|------|----------|------|
| 1 | [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) | 60분 | 백테스팅 모범 사례 및 함정 |
| 2 | [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md) | 45분 | 팩터 정의 및 사용법 |
| 3 | [docs/FACTOR_FORMULAS_AND_REFERENCES.md](docs/FACTOR_FORMULAS_AND_REFERENCES.md) | 30분 | 팩터 공식 및 학술 참고 |
| 4 | [docs/WALK_FORWARD_OPTIMIZATION.md](docs/WALK_FORWARD_OPTIMIZATION.md) | 40분 | Walk-forward 최적화 |
| 5 | [docs/OPTIMIZATION_COOKBOOK.md](docs/OPTIMIZATION_COOKBOOK.md) | 50분 | 포트폴리오 최적화 레시피 |

**전략 개발 워크플로우**:
- [docs/BACKTEST_WORKFLOW_IMPLEMENTATION_DESIGN.md](docs/BACKTEST_WORKFLOW_IMPLEMENTATION_DESIGN.md)
- [docs/SIGNAL_GENERATORS_COMPLETE.md](docs/SIGNAL_GENERATORS_COMPLETE.md)
- [docs/PORTFOLIO_ALLOCATION_SYSTEM.md](docs/PORTFOLIO_ALLOCATION_SYSTEM.md)

**리스크 관리**:
- [RISK_CALCULATOR_DESIGN.md](RISK_CALCULATOR_DESIGN.md) - 리스크 계산기
- [docs/FACTOR_INDEPENDENCE_VALIDATION.md](docs/FACTOR_INDEPENDENCE_VALIDATION.md) - 팩터 독립성

---

## 📂 문서 카테고리별 분류

### 1️⃣ 시작하기 (Getting Started)
- [GETTING_STARTED.md](GETTING_STARTED.md) - ⭐ **신규 사용자 필독**
- [README.md](README.md) - 프로젝트 개요
- [QUICKSTART.md](QUICKSTART.md) - 5분 빠른 시작
- [CLAUDE.md](CLAUDE.md) - 개발자용 상세 가이드 (한글)

### 2️⃣ 백테스팅 및 전략 개발
- [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) - 백테스팅 모범 사례
- [docs/QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md) - 엔진 비교
- [docs/BACKTEST_MODULE_DESIGN.md](docs/BACKTEST_MODULE_DESIGN.md) - 백테스트 모듈 설계
- [docs/BACKTEST_RUNNER_COMPLETE.md](docs/BACKTEST_RUNNER_COMPLETE.md) - 백테스트 러너
- [docs/WALK_FORWARD_OPTIMIZATION.md](docs/WALK_FORWARD_OPTIMIZATION.md) - Walk-forward 최적화

### 3️⃣ 팩터 분석
- [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md) - 팩터 라이브러리
- [docs/FACTOR_FORMULAS_AND_REFERENCES.md](docs/FACTOR_FORMULAS_AND_REFERENCES.md) - 팩터 공식
- [docs/FACTOR_BASED_ARCHITECTURE_DESIGN.md](docs/FACTOR_BASED_ARCHITECTURE_DESIGN.md) - 팩터 아키텍처
- [docs/FACTOR_INDEPENDENCE_VALIDATION.md](docs/FACTOR_INDEPENDENCE_VALIDATION.md) - 팩터 독립성

### 4️⃣ 포트폴리오 최적화
- [docs/OPTIMIZATION_COOKBOOK.md](docs/OPTIMIZATION_COOKBOOK.md) - 최적화 레시피
- [docs/PORTFOLIO_ALLOCATION_SYSTEM.md](docs/PORTFOLIO_ALLOCATION_SYSTEM.md) - 포트폴리오 시스템
- [RISK_CALCULATOR_DESIGN.md](RISK_CALCULATOR_DESIGN.md) - 리스크 계산기

### 5️⃣ 데이터베이스 및 데이터
- [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) - 데이터베이스 스키마
- [docs/POSTGRES_SETUP_GUIDE.md](docs/POSTGRES_SETUP_GUIDE.md) - PostgreSQL 설정
- [docs/POSTGRES_OPERATIONS.md](docs/POSTGRES_OPERATIONS.md) - PostgreSQL 운영
- [docs/COMPRESSION_GUIDE.md](docs/COMPRESSION_GUIDE.md) - 데이터 압축

### 6️⃣ 배포 및 운영
- [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - 배포 가이드
- [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) - 운영 매뉴얼
- [docs/QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md) - 퀀트 운영
- [docs/MIGRATION_RUNBOOK.md](docs/MIGRATION_RUNBOOK.md) - 마이그레이션

### 7️⃣ CLI 및 사용법
- [docs/CLI_USAGE_GUIDE.md](docs/CLI_USAGE_GUIDE.md) - CLI 사용 가이드
- [docs/CLI_DESIGN_SUMMARY.md](docs/CLI_DESIGN_SUMMARY.md) - CLI 설계
- [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) - API 통합

### 8️⃣ 개발 로드맵 및 계획
- [docs/QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md) - 15주 개발 로드맵
- [docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md](docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md) - Phase 1 계획
- [docs/WEEK4_COMPLETION_REPORT.md](docs/WEEK4_COMPLETION_REPORT.md) - Week 4 완료 보고서
- [docs/WEEK5_PHASE1_COMPLETION_REPORT.md](docs/WEEK5_PHASE1_COMPLETION_REPORT.md) - Week 5 완료

### 9️⃣ 트러블슈팅 및 문제 해결
- [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md) - 트러블슈팅 인덱스
- [docs/VALIDATION_FRAMEWORK_GUIDE.md](docs/VALIDATION_FRAMEWORK_GUIDE.md) - 검증 프레임워크
- [docs/PERFORMANCE_TUNING_GUIDE.md](docs/PERFORMANCE_TUNING_GUIDE.md) - 성능 튜닝

### 🔟 기타 참고 자료
- [PROJECT_INDEX.md](PROJECT_INDEX.md) - 프로젝트 구조
- [FILTERING_SYSTEM_GUIDE.md](FILTERING_SYSTEM_GUIDE.md) - 필터링 시스템
- [SPOCK_REFRESH_GUIDE.md](SPOCK_REFRESH_GUIDE.md) - Spock 리프레시

---

## 🎯 목적별 빠른 링크

### 🚀 빠르게 시작하고 싶어요
→ [GETTING_STARTED.md](GETTING_STARTED.md) → [QUICKSTART.md](QUICKSTART.md)

### 💡 백테스팅을 배우고 싶어요
→ [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) → [docs/QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md)

### 📊 팩터 분석을 하고 싶어요
→ [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md) → [docs/FACTOR_FORMULAS_AND_REFERENCES.md](docs/FACTOR_FORMULAS_AND_REFERENCES.md)

### 🔧 커스터마이징하고 싶어요
→ [CLAUDE.md](CLAUDE.md) → [docs/QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)

### 🏗️ 프로덕션 배포하고 싶어요
→ [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) → [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md)

### 🐛 문제가 발생했어요
→ [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md) → [FAQ](GETTING_STARTED.md#-자주-묻는-질문-faq)

### 📈 성과를 개선하고 싶어요
→ [docs/OPTIMIZATION_COOKBOOK.md](docs/OPTIMIZATION_COOKBOOK.md) → [docs/WALK_FORWARD_OPTIMIZATION.md](docs/WALK_FORWARD_OPTIMIZATION.md)

### 🔐 리스크를 관리하고 싶어요
→ [RISK_CALCULATOR_DESIGN.md](RISK_CALCULATOR_DESIGN.md) → [docs/QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md)

---

## 📝 문서 버전 및 상태

| 문서 | 버전 | 마지막 업데이트 | 상태 |
|------|------|----------------|------|
| GETTING_STARTED.md | 1.0.0 | 2025-11-12 | ✅ 최신 |
| README.md | 1.1.0 | 2025-10-27 | ✅ 최신 |
| QUICKSTART.md | 1.0.0 | 2025-10-19 | ✅ 최신 |
| CLAUDE.md | 1.2.0 | 2025-11-03 | ✅ 최신 |
| BACKTESTING_GUIDE.md | 1.0.0 | 2025-10-18 | ✅ 최신 |
| QUANT_ROADMAP.md | 1.0.0 | 2025-10-15 | ✅ 최신 |

---

## 🔍 문서 검색 팁

### 키워드로 찾기
```bash
# 특정 키워드가 포함된 문서 찾기
grep -r "백테스팅" docs/
grep -r "PostgreSQL" docs/
grep -r "팩터" docs/

# 파일명으로 찾기
find docs/ -name "*BACKTEST*"
find docs/ -name "*FACTOR*"
```

### 문서 카테고리
- **GUIDE**: 사용자 가이드 (초보자 친화적)
- **DESIGN**: 설계 문서 (개발자용)
- **REPORT**: 완료 보고서 (개발 이력)
- **REFERENCE**: 참고 자료 (API, 스키마 등)

---

## 📧 문서 개선 제안

문서가 불명확하거나 개선이 필요한 부분이 있다면:

1. **GitHub Issues**: [이슈 생성](https://github.com/jsj9346/spock/issues)
2. **이메일**: jsj9346@gmail.com
3. **Pull Request**: 직접 문서 개선 기여

---

## 🗺️ 학습 로드맵 요약

### Week 1: 기초 (초보자)
- Day 1-2: GETTING_STARTED.md + 설치
- Day 3-4: README.md + QUICKSTART.md
- Day 5-7: CLI_USAGE_GUIDE.md + 실습

### Week 2: 백테스팅 (중급)
- Day 1-3: BACKTESTING_GUIDE.md
- Day 4-5: QUANT_BACKTESTING_ENGINES.md
- Day 6-7: 백테스트 실습 및 분석

### Week 3: 팩터 분석 (중급)
- Day 1-3: FACTOR_LIBRARY_REFERENCE.md
- Day 4-5: FACTOR_FORMULAS_AND_REFERENCES.md
- Day 6-7: 팩터 전략 개발

### Week 4: 포트폴리오 최적화 (고급)
- Day 1-3: OPTIMIZATION_COOKBOOK.md
- Day 4-5: WALK_FORWARD_OPTIMIZATION.md
- Day 6-7: 최적화 실습

---

**마지막 업데이트**: 2025-11-12
**버전**: 1.0.0
**관리자**: jsj9346@gmail.com

**좋은 학습 되세요! 📚✨**
