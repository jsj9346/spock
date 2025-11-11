# CLAUDE_KR.md - Quant Investment Platform (한국어)

이 파일은 Claude Code (claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드입니다.

## 프로젝트 개요

**Quant Investment Platform**은 증거 기반 투자 전략 개발을 위해 설계된 체계적인 정량적 연구 및 포트폴리오 관리 시스템입니다. 이 플랫폼은 자동화된 매매 실행(Spock)에서 종합적인 퀀트 연구, 백테스팅, 포트폴리오 최적화로 전환되었습니다.

### 핵심 철학
- **🎯 백테스팅 엔진 우선**: 전략 개발 전 백테스팅 인프라 완성 및 검증
- **엔진 중심 개발**: 모든 연구 활동의 전제조건으로 신뢰할 수 있는 백테스팅 기반(vectorbt + 커스텀 엔진) 구축
- **연구 중심 접근**: 배포 전 엄격한 백테스팅을 통한 전략 검증
- **증거 기반 의사결정**: 데이터 기반 팩터 분석 및 체계적 신호 생성
- **체계적 리스크 관리**: 정량적 리스크 평가 및 포트폴리오 수준 제약
- **재현 가능한 결과**: 결정론적 백테스트 결과를 가진 버전 관리 전략
- **멀티팩터 프레임워크**: 강건한 알파 생성을 위한 검증된 팩터(Value, Momentum, Quality) 결합

### 타겟 사용자
- **주 사용자**: 투자 전략을 개발하고 검증하는 정량적 연구자
- **부 사용자**: 체계적인 자산 배분 및 리밸런싱을 추구하는 포트폴리오 관리자
- **3차 사용자**: 증거 기반 팩터 포트폴리오를 구축하는 개인 투자자

---

## 🎯 현재 상태: Phase 0 코드 안정화

**Phase 0.1**: ✅ **완료** - 모든 backtest_runner 테스트 통과 (23/23, 100%)
**Phase 0.2**: ✅ **완료** - 테스트 커버리지 확장 (71/77 테스트, 92% 통과율)
**전체 커버리지**: 6.81% (현실적인 기준선, 5.48%에서 상승)

### Phase 0.2 성과 (2025-10-30)

#### Tier 1: 데이터 프로바이더 테스트 (100% 완료)
- ✅ **Base Data Provider**: 17/17 테스트 통과, 85.71% 커버리지
- ✅ **PostgreSQL Data Provider**: 19/19 테스트 통과, 47.99% 커버리지
- **총계**: 36/36 테스트 통과 (100%)

#### Tier 2: Walk-Forward Optimizer (67% 완료 - Option A)
- ✅ **핵심 로직 테스트**: 12/18 테스트 통과
- ⚠️ **통합 테스트**: 6개 테스트 스킵 (환경 의존 데이터 요구사항)
- **근거**: 테스트에는 프로덕션에는 존재하지만 로컬 SQLite 테스트 데이터베이스에는 없는 ticker 000020 데이터(2024-01-01 ~ 2024-03-31)가 필요함

#### 적용된 주요 수정사항
1. **캐시 히트 테스트**: 카운터 증가 전 캐시 체크 이동 → 정확한 히트/미스 추적
2. **패치 경로 오류**: `BackfillOrchestrator` 패치 경로 수정 → 19개 PostgreSQL 테스트 통과
3. **윈도우 오버랩 로직**: 인접 윈도우에 대해 `<`를 `<=`로 변경 → 테스트 통과

### Phase 0 요약
| Phase | 테스트 | 통과율 | 커버리지 영향 |
|-------|-------|--------|--------------|
| 0.1 | 23/23 | 100% ✅ | 기준선 |
| 0.2 Tier 1 | 36/36 | 100% ✅ | +85.71% base, +47.99% postgres |
| 0.2 Tier 2 | 12/18 | 67% ⚠️ | 핵심 로직 검증됨 |
| **총계** | **71/77** | **92%** | **6.81%** |

**자세한 Phase 0.2 분석은 [PHASE0_2_COMPLETION_REPORT.md](docs/PHASE0_2_COMPLETION_REPORT.md) 참조**

---

## 🎯 Week 4 성과 (Phase 1 완료)

**상태**: ✅ **73% 완료** (8/11 작업) - 백테스팅 엔진 검증 완료 및 전략 개발 준비 완료

### 주요 성과

#### 1. 데이터베이스 인프라 (작업 1-2)
- **PostgreSQL + TimescaleDB**: 무제한 보존 기간을 가진 프로덕션 데이터베이스
- **데이터 품질**: 1,369,467개 레코드 표준화 (timeframe '1d', 고유 제약 적용)
- **PostgresDataProvider**: >85% 캐시 히트율을 가진 609줄 구현
- **성능**: 단일 ticker <100ms, 배치(20 ticker) <500ms
- **테스팅**: 27개 단위 테스트 + 16개 통합 테스트 (모두 통과)

#### 2. 이중 엔진 전략 (작업 3)
- **vectorbt 어댑터**: 100배 속도 향상 (5년 백테스트 <1초 vs 30초)
- **커스텀 엔진**: 프로덕션 정확도를 위한 BaseDataProvider 패턴
- **통합 인터페이스**: 원활한 엔진 전환을 위한 포트폴리오 래퍼
- **메트릭**: 샤프 비율, 낙폭, 승률, 이익 팩터 자동 계산

#### 3. Walk-Forward 최적화 (작업 8 - 기존 존재)
- **프레임워크**: 379줄 WalkForwardOptimizer (rolling/anchored 전략)
- **검증**: 2022-2025 데이터에 대한 5번 최적화 (25개 윈도우)
- **과적합 탐지**: 표본 내 vs 표본 외 성능 저하 분석
- **결과**: 검증 보고서에 문서화 (견고성 점수, 최적 파라미터)

#### 4. 데이터 품질 모니터링 (작업 10)
- **이상 징후 조사**: 42개 가격 이상 징후 분석
  - **범주 1**: 41개 고아 ticker (레지스트리 없는 OHLCV)
  - **범주 2**: 1개 심각한 손상 (ticker 091090, +4,824% 후 -97.9%)
  - **범주 3**: 35개 거짓 양성 (ETF 소수점 정밀도)
- **자동 탐지**: 일일 모니터링을 위한 4-쿼리 스크립트
- **문서화**: 개선 계획이 포함된 포괄적인 조사 보고서

### 다음 단계 (Week 5 - Phase 0.3)
1. **팩터 라이브러리 테스트**: 높은 가치의 간단한 단위 테스트 (4-6시간)
2. **테스트 데이터 백필**: SQLite에 ticker 000020 2024년 1분기 데이터 추가 (30분)
3. **통합 테스트 스위트**: walk-forward optimizer를 위한 포괄적인 통합 테스트 (2-3시간)
4. **커버리지 확장**: 팩터 라이브러리 테스트로 15-20% 목표
5. **팩터 라이브러리 개발 시작**: Value, momentum, quality 팩터 (Week 5-6 집중)

**자세한 Week 4 요약은 [WEEK4_COMPLETION_REPORT.md](docs/WEEK4_COMPLETION_REPORT.md) 참조**

---

## 아키텍처 전환: 트레이딩에서 리서치로

### 변경 사항
| 측면 | Spock (트레이딩 시스템) | Quant Platform (리서치) |
|------|------------------------|-------------------------|
| **주요 목표** | 실시간 거래 실행 | 전략 개발 및 검증 |
| **데이터베이스** | SQLite (250일 보존) | PostgreSQL + TimescaleDB (무제한 히스토리) |
| **시간 범위** | 일중에서 주간 | 수년의 과거 데이터 |
| **핵심 엔진** | LayeredScoringEngine (100점) | Multi-Factor Analysis Engine |
| **실행** | KIS API 주문 제출 | 백테스팅 시뮬레이션 |
| **인터페이스** | CLI + 모니터링 대시보드 | Streamlit 연구 워크벤치 |
| **초점** | 단일 종목 신호 | 포트폴리오 수준 최적화 |

### 유지된 부분 (70% 코드 재사용)
- ✅ **데이터 수집 인프라**: KIS API 어댑터, 시장별 파서
- ✅ **기술적 분석 모듈**: 이동평균, RSI, MACD, 볼린저 밴드
- ✅ **스코어링 시스템 기반**: 멀티팩터 분석을 위해 확장된 LayeredScoringEngine
- ✅ **리스크 관리**: 켈리 계산기, ATR 기반 포지션 사이징
- ✅ **데이터베이스 스키마**: 핵심 테이블(tickers, ohlcv_data, technical_analysis)
- ✅ **모니터링 스택**: Prometheus + Grafana 인프라

---

## 기술 스택

### 핵심 종속성
**언어 및 런타임**: Python 3.11+

**데이터 및 분석**:
- pandas 2.0.3, numpy 1.24.3, scipy 1.11.0
- scikit-learn 1.3.0, pandas-ta 0.3.14b0, statsmodels 0.14.0

**데이터베이스**:
- PostgreSQL 15+ (관계형 데이터, 무제한 보존)
- TimescaleDB 2.11+ (시계열 최적화)
- psycopg2 2.9.7

**백테스팅 엔진**:
- Custom Event-Driven Engine (프로덕션 안정성 ✅)
- vectorbt 0.25.6 (연구 최적화, 100배 빠름 🎯 **우선순위 1**)
- backtrader 1.9.78.123 (선택사항, 실시간 트레이딩 📋)
- zipline-reloaded 2.4.0 (선택사항, 기관용 📋)

**포트폴리오 최적화**:
- cvxpy 1.3.2, PyPortfolioOpt 1.5.5, riskfolio-lib 4.3.0

**웹 프레임워크**:
- FastAPI 0.103.1, Streamlit 1.27.0, uvicorn 0.23.2

**시각화**:
- plotly 5.17.0, matplotlib 3.7.2, seaborn 0.12.2

**설정 및 로깅**:
- python-dotenv 1.0.0, pyyaml 6.0.1, loguru 0.7.0

**모니터링** (Spock에서 재사용):
- prometheus-client 0.23.1, psutil 5.9.5

**전체 종속성 목록은 `requirements_quant.txt` 참조**

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Research Dashboard                 │
│  Strategy Builder | Backtest Results | Portfolio Analytics      │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  /strategies | /backtest | /optimize | /risk | /data            │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────────────────────┐
│                    Core Engine Layer                             │
├──────────────────┬──────────────────┬──────────────────────────┤
│  Multi-Factor    │  Backtesting     │  Portfolio Optimizer     │
│  Analysis Engine │  Engine          │  (cvxpy)                 │
│  - Value         │  - Custom ✅     │  - Mean-Variance         │
│  - Momentum      │  - vectorbt 🎯   │  - Risk Parity           │
│  - Quality       │  - backtrader 📋 │  - Black-Litterman       │
│  - Low Vol       │  - zipline 📋    │  - Kelly Multi-Asset     │
│  - Size          │                  │  - Constraint Handling   │
└──────────────────┴──────────────────┴──────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                Data Layer (PostgreSQL + TimescaleDB)             │
│  Hypertables: ohlcv_data (continuous aggregates)                │
│  Tables: tickers, factors, strategies, backtest_results         │
└──────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│              Data Collection (Reused from Spock)                 │
│  KIS API | Polygon.io | yfinance | Market Adapters             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 프로젝트 구조

```
~/spock/
   quant_platform.py                    # 메인 오케스트레이터

   modules/
      # 핵심 Quant 컴포넌트
      factors/                          # 팩터 라이브러리
      backtest/                         # 백테스팅 엔진
      optimization/                     # 포트폴리오 최적화
      risk/                             # 리스크 관리
      strategies/                       # 전략 정의

      # 데이터 수집 (Spock에서 재사용)
      api_clients/                      # API 래퍼
      market_adapters/                  # 시장별 어댑터
      parsers/                          # 데이터 변환

   api/                                 # FastAPI 백엔드
   dashboard/                           # Streamlit UI
   config/                              # 설정 파일
   data/                                # PostgreSQL 데이터베이스
   logs/                                # 애플리케이션 로그
   tests/                               # 테스트 스위트
   docs/                                # 문서

   examples/
      example_momentum_value_strategy.py
      example_backtest_workflow.py
      example_portfolio_optimization.py
```

---

## 📚 문서 인덱스

더 나은 구성과 성능을 위해 자세한 문서가 전문 파일로 분리되었습니다:

### 핵심 문서
- **[QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md)** - PostgreSQL + TimescaleDB 스키마 설계
  - 테이블 구조, 하이퍼테이블, 연속 집계
  - 압축 정책, 쿼리 최적화 패턴
  - 백업 전략, 성능 벤치마크

- **[QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)** - 명령 예제가 포함된 개발 워크플로우
  - 백테스팅 엔진 설정 (우선순위 1)
  - 데이터베이스 설정 및 마이그레이션
  - 팩터 연구, 전략 개발
  - 포트폴리오 최적화, 리스크 분석
  - 대시보드 및 API 사용 예제

- **[QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md)** - 15주 개발 로드맵
  - Phase 1: 백테스팅 엔진 (Week 1-2) 🎯 **최우선 순위**
  - Phase 2-11: 데이터베이스부터 프로덕션까지 (Week 3-15)
  - 성공 기준 및 품질 게이트

- **[QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md)** - 백테스팅 엔진 비교
  - Custom Event-Driven Engine (프로덕션 ✅)
  - vectorbt (연구, 100배 빠름 🎯)
  - backtrader 및 zipline (선택사항 📋)
  - 성능 벤치마크, 코드 예제

- **[QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md)** - 운영 및 모니터링
  - 로깅 설정 및 모범 사례
  - Prometheus 메트릭, Grafana 대시보드
  - 알림 규칙, 문제 해결 가이드
  - 일일/주간/월간 운영 절차

---

## 빠른 시작

### 1. 환경 설정
```bash
# 저장소 클론
cd ~/spock

# 종속성 설치
pip install -r requirements_quant.txt

# 환경 설정
cp .env.example .env
# API 키와 데이터베이스 자격증명으로 .env 편집
```

### 2. 데이터베이스 설정
```bash
# PostgreSQL + TimescaleDB 설치
brew install postgresql@17 timescaledb  # macOS

# 데이터베이스 생성
createdb quant_platform

# TimescaleDB 활성화
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 스키마 초기화
python3 scripts/init_postgres_schema.py
```

**자세한 설정 지침은 [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md#2-database-setup) 참조**

### 3. 백테스팅 엔진 검증 (우선순위 1)
```bash
# 백테스팅 엔진 설치
pip install vectorbt backtrader zipline-reloaded

# 커스텀 엔진 테스트
python3 modules/backtest/backtest_engine.py --mode validate

# vectorbt 통합 테스트
python3 modules/backtest/vectorbt_adapter.py --test-integration

# 포괄적인 테스트 실행
python3 tests/test_backtest_engine.py --comprehensive
```

**완전한 엔진 설정 가이드는 [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md#1-backtesting-engine-setup) 참조**

### 4. 예제 백테스트 실행
```bash
# 단순 모멘텀 전략 (vectorbt 사용 - 빠름)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --engine vectorbt
```

---

## 개발 워크플로우 요약

**현재 초점**: Phase 1 - 백테스팅 엔진 개발 및 검증 (Week 1-2)

### 🎯 Phase 1: 백테스팅 엔진 (최우선 순위)
**핵심 기반**: 엔진 검증 없이 전략 작업 금지

**Week 1**: 커스텀 엔진 개선 + vectorbt 통합 + 성능 메트릭
**Week 2**: Walk-forward 최적화 + 포괄적인 테스팅 + 문서화

**성공 기준**:
- ✅ 커스텀 엔진: 5년 시뮬레이션 <30초
- ✅ vectorbt: 5년 시뮬레이션 <1초
- ✅ >95% 정확도 검증
- ✅ 모든 성능 메트릭 자동 계산

**전체 로드맵은 [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md) 참조**

### 워크플로우 단계
1. **백테스팅 엔진 설정** (Week 1-2) → 현재 단계
2. **데이터베이스 마이그레이션** (Week 3)
3. **팩터 연구** (Week 5-6) - 엔진 검증 후
4. **전략 개발** (Week 7+) - 엔진 + 팩터 준비 후
5. **포트폴리오 최적화** (Week 8+)
6. **프로덕션 배포** (Week 15)

**자세한 워크플로우 및 명령 예제는 [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md) 참조**

---

## 핵심 컴포넌트

### 1. Multi-Factor Analysis Engine
**목적**: 팩터 기반 종목 선정을 통한 체계적 알파 생성

**팩터 범주**:
- **가치(Value)**: P/E, P/B, EV/EBITDA, 배당수익률
- **모멘텀(Momentum)**: 12개월 수익률, RSI, 52주 고점
- **품질(Quality)**: ROE, 부채비율, 이익 품질
- **저변동성(Low-Volatility)**: 변동성, 베타, 최대 낙폭
- **규모(Size)**: 시가총액, 유동성

**출력**: 각 종목에 대한 복합 알파 점수(0-100), 일일 업데이트

### 2. 백테스팅 엔진 (하이브리드 전략)
**목적**: 현실적인 거래 비용을 반영한 과거 시뮬레이션

**프로덕션**: Custom Event-Driven Engine (안정적, 구현됨 ✅)
**연구**: vectorbt (100배 빠른 파라미터 최적화 🎯 **우선순위 1**)
**선택사항**: backtrader (실시간 트레이딩), zipline (기관용) 📋

**자세한 엔진 비교 및 예제는 [QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md) 참조**

### 3. 포트폴리오 최적화
**목적**: 리스크 제약 하의 최적 자산 배분

**방법론**:
- Mean-Variance (Markowitz)
- Risk Parity
- Black-Litterman
- Kelly Criterion (Multi-Asset)

**제약조건**: 포지션 한도, 섹터 한도, 회전율, 현금 준비금

### 4. 리스크 관리
**목적**: 정량적 리스크 평가 및 모니터링

**메트릭**: VaR, CVaR, 스트레스 테스팅, 상관관계 분석, 팩터 익스포저

**리스크 한도**: 포트폴리오 VaR <5%, 단일 포지션 VaR <1%, 섹터 <40%

**자세한 리스크 관리 워크플로우는 [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md#risk-analysis) 참조**

---

## 데이터베이스 아키텍처

### PostgreSQL + TimescaleDB 설계
**철학**: 시계열 최적화와 함께 무제한 과거 데이터 보존

**주요 테이블**:
- `ohlcv_data` (하이퍼테이블) - 가격 및 거래량 데이터
- `factor_scores` - 팩터 계산
- `strategies` - 전략 정의
- `backtest_results` - 시뮬레이션 결과
- `portfolio_holdings` - 포지션 추적

**최적화**:
- 월별/연별 데이터를 위한 연속 집계
- 압축 (1년 후 10배 공간 절약)
- 쿼리 성능: 10년 데이터 <1초

**완전한 스키마 및 SQL 예제는 [QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md) 참조**

---

## 성공 메트릭

### 🎯 백테스팅 엔진 (Phase 1 - 핵심)
- 커스텀 엔진: 5년 시뮬레이션 <30초
- vectorbt: 5년 시뮬레이션 <1초
- 정확도: 참조 백테스트와 >95% 일치
- 테스트 커버리지: >90% 코드 커버리지

### 전략 성능 (엔진 검증 후)
- 샤프 비율: >1.5
- 백테스트 정확도: >90% 일관성
- 팩터 독립성: 상관관계 <0.5
- 최소 거래 수: 통계적 유의성을 위해 >100

### 포트폴리오 성능
- 총 수익률: 연간 >15%
- 샤프 비율: >1.5
- 최대 낙폭: <15%
- VaR (95%): 포트폴리오 가치의 <5%

### 시스템 성능
- 데이터베이스 쿼리: 10년 데이터 <1초
- API 지연시간: <200ms (p95)
- 대시보드 로드: <3초

**완전한 메트릭 및 목표는 [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md#success-metrics-summary) 참조**

---

## 모니터링 및 운영

### 로그 파일
- **위치**: `logs/YYYYMMDD_quant_platform.log`
- **보존 기간**: 30일
- **레벨**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### 성능 메트릭 (Prometheus)
- 백테스트 메트릭 (실행시간, 메모리, 캐시 히트율)
- 최적화 메트릭 (수렴 시간, 제약 위반)
- 팩터 메트릭 (계산 시간, 데이터 가용성)
- 데이터베이스 메트릭 (쿼리 시간, 연결 풀, 디스크 사용량)
- API 메트릭 (요청 속도, 지연시간, 오류율)

### 알림 (Grafana)
- **심각**: 데이터베이스 연결 끊김, API 실패, 최적화 오류
- **경고**: 느린 백테스트 (>60초), 팩터 실패, 높은 메모리
- **정보**: 일일 업데이트, 주간 보고서, 월간 리밸런싱

**완전한 운영 가이드는 [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md) 참조**

---

## 연구 모범 사례

### 일반적인 함정 회피
- **과적합**: 표본 내가 아닌 walk-forward 최적화 사용
- **거래 비용**: 항상 현실적인 수수료 및 슬리피지 포함
- **생존 편향**: 시점 데이터 사용 (선행 금지)
- **데이터 품질**: 분할, 배당, 오류 검증
- **통계적 유의성**: 의미 있는 결과를 위해 >100 거래 필요

### 리스크 경고
- **백테스팅 ≠ 미래 결과**: 과거 성과가 미래 수익을 보장하지 않음
- **모델 리스크**: 시장 체제 변화 시 전략 실패 가능
- **실행 리스크**: 실제 트레이딩이 백테스트와 다를 수 있음
- **상관관계 붕괴**: 위기 시 자산 상관관계 급등
- **레버리지 리스크**: 손실 확대 가능

---

## 주요 개발 원칙

### 🎯 엔진 우선 접근법
1. **검증된 백테스팅 엔진 없이 전략 개발 금지**
2. **엔진 검증 게이트**: 성능 벤치마크, 정확도 테스트, 스트레스 테스트
3. **이중 엔진 전략**: 연구 속도를 위한 vectorbt, 프로덕션 정확도를 위한 커스텀
4. **지속적 검증**: 자동화된 테스팅 및 성능 모니터링

### 품질 게이트
- **Phase 1 게이트**: 진행 전 백테스팅 엔진이 모든 테스트 통과해야 함
- **Phase 4 게이트**: 백테스팅 엔진을 사용한 팩터 라이브러리 검증
- **Phase 7 게이트**: 전략이 >100 거래 및 >1.0 샤프 비율 표시
- **Phase 11 게이트**: 프로덕션 전 완전한 통합 테스트

**완전한 품질 게이트 및 검증 사이클은 [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md#key-development-principles) 참조**

---

## 지원 및 리소스

### 문서
모든 자세한 문서는 `docs/` 디렉토리에서 확인 가능:
- [QUANT_DATABASE_SCHEMA.md](docs/QUANT_DATABASE_SCHEMA.md) - 데이터베이스 설계
- [QUANT_DEVELOPMENT_WORKFLOWS.md](docs/QUANT_DEVELOPMENT_WORKFLOWS.md) - 개발 가이드
- [QUANT_ROADMAP.md](docs/QUANT_ROADMAP.md) - 프로젝트 로드맵
- [QUANT_BACKTESTING_ENGINES.md](docs/QUANT_BACKTESTING_ENGINES.md) - 엔진 비교
- [QUANT_OPERATIONS.md](docs/QUANT_OPERATIONS.md) - 운영 가이드

### 코드 예제
- **전략 개발**: `examples/example_momentum_value_strategy.py`
- **백테스팅**: `examples/example_backtest_workflow.py`
- **포트폴리오 최적화**: `examples/example_portfolio_optimization.py`

### 외부 리소스
- **vectorbt**: https://vectorbt.dev/
- **backtrader**: https://www.backtrader.com/
- **zipline**: https://zipline.ml4trading.io/
- **PyPortfolioOpt**: https://pyportfolioopt.readthedocs.io/
- **TimescaleDB**: https://docs.timescale.com/

---

**마지막 업데이트**: 2025-10-26
**버전**: 1.2.0 (최적화)
**상태**: 엔진 우선 개발 단계
**현재 초점**: Phase 1 - 백테스팅 엔진 개발 및 검증 (Week 1-2)
- KIS API를 이용할 경우에는 반드시 이전 토큰 발급 이력을 확인할 것.(KIS API는 24시간동안 유효하며, 짧은 시간에 많은 토큰 발급 요청시 접근 제한에 걸리는 문제가 있음.)
