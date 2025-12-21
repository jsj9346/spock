# Quant Platform 통합 개발 로드맵

**문서 버전**: 1.1.0
**최종 업데이트**: 2025-10-25
**상태**: 🔄 **진행 중** - Phase 1 개발 필요

---

## 📊 현재 구현 상태 요약 (2025-10-25 기준)

### ✅ 완료된 주요 기능
- **P0.1**: Database Migration (PostgreSQL + TimescaleDB)
- **P0.2**: CLI Infrastructure (cli/, api/, config/)
- **P0.4**: API Communication Layer (FastAPI backend)
- **P0.5**: Basic Data Collection (Spock modules 재사용)
- **P1.1**: Factor Library (30+ factors across 7 categories)
- **P2.1**: Portfolio Optimization (Mean-Variance, Risk Parity, Black-Litterman, Kelly)
- **P2.2**: Risk Management (VaR, CVaR calculators)

### 🔄 부분 완료
- **P0.3**: Authentication System (API routes 있으나 CLI commands 미구현)
- **P2.4**: Streamlit Dashboard (기본 구조만 완료)

### ❌ 주요 미완료 항목 (CRITICAL)
- **P1.2**: ❌ **Backtesting Engine** - 전략 검증 핵심 기능
- **P1.3**: ❌ CLI Backtest Commands - P1.2 dependency
- **P1.4**: ⏳ Strategy Management
- **P1.5**: ❌ Performance Metrics - P1.2 dependency
- **P2.3**: ❌ TUI Interface (선택사항)
- **P3.x**: ❌ Optional Enhancements (AWS Auth, Additional Engines, Walk-Forward, Cloud)

### 📈 완성도
- **Phase 0 (MVP Foundation)**: 75% 완료 (3/4 tasks)
- **Phase 1 (Core Features)**: 20% 완료 (1/5 tasks) - **백테스팅 엔진 블로커**
- **Phase 2 (Advanced Features)**: 50% 완료 (2/4 tasks)
- **Phase 3 (Optional)**: 0% 완료 (선택사항)

### 🎯 다음 우선순위
1. **P1.2 Backtesting Engine** 구현 (backtrader adapter) - CRITICAL
2. **P1.3 CLI Backtest Commands** 구현
3. **P1.4 Strategy Management** 완료
4. **P0.3 Authentication** 완료 (선택적)

---

## 목차

1. [개요](#개요)
2. [우선순위 매트릭스](#우선순위-매트릭스)
3. [통합 타임라인](#통합-타임라인)
4. [Phase별 상세 계획](#phase별-상세-계획)
5. [의존성 맵](#의존성-맵)
6. [검증 체크포인트](#검증-체크포인트)
7. [리스크 관리](#리스크-관리)

---

## 개요

### 프로젝트 목표

**Quant Investment Platform**: 체계적인 퀀트 투자 연구 및 포트폴리오 관리 시스템

**핵심 가치**:
- Evidence-Based: 백테스팅을 통한 전략 검증
- Multi-Interface: CLI, TUI, WebUI 동시 지원
- Scalable: Local → Cloud 하이브리드 아키텍처
- Production-Ready: 실제 운용 가능한 품질

### 개발 트랙 통합

기존 2개의 독립적인 로드맵을 **의존성 기반으로 통합**:

| 트랙 | 기간 | 상태 | 핵심 산출물 |
|-----|------|------|------------|
| **CLI/TUI Track** | 2-4주 | 구현 플랜 완료 | quant_platform.py, API backend |
| **Quant Core Track** | 12주 | 설계 완료 | Factor library, Backtest engine, Optimizer |

**통합 전략**: CLI는 Quant Core 기능을 래핑 → **병렬 개발 가능**

---

## 우선순위 매트릭스

### Priority 정의

| Priority | 목표 | 비즈니스 가치 | 기술 리스크 | 예상 소요 |
|----------|------|--------------|------------|-----------|
| **P0 (Critical)** | MVP 기반 구축 | 매우 높음 | 낮음 | 1-2주 |
| **P1 (High)** | 핵심 기능 완성 | 높음 | 중간 | 3-4주 |
| **P2 (Medium)** | 고급 기능 추가 | 중간 | 중간 | 5-8주 |
| **P3 (Low)** | 선택 기능 | 낮음 | 낮음 | 9-12주 |

### 작업 우선순위 (Priority-Based)

```
P0: MVP Foundation (Week 1-2)
├─ P0.1: Database Migration (PostgreSQL + TimescaleDB)
├─ P0.2: CLI Infrastructure (Config, Output, Main Entry)
├─ P0.3: Authentication System (Simple Auth)
├─ P0.4: API Communication Layer
└─ P0.5: Basic Data Collection (Reuse Spock modules)

P1: Core Features (Week 3-4)
├─ P1.1: Factor Library (Value, Momentum, Quality)
├─ P1.2: Backtesting Engine (backtrader integration)
├─ P1.3: CLI Backtest Command
├─ P1.4: Strategy Management (CRUD)
└─ P1.5: Performance Metrics Calculator

P2: Advanced Features (Week 5-8)
├─ P2.1: Portfolio Optimization (Mean-Variance, Risk Parity)
├─ P2.2: Risk Management (VaR, CVaR)
├─ P2.3: Walk-Forward Optimizer
├─ P2.4: TUI Interface (Textual)
└─ P2.5: Streamlit Dashboard

P3: Optional Enhancements (Week 9-12)
├─ P3.1: AWS CLI Authentication
├─ P3.2: Additional Backtesting Engines (zipline, vectorbt)
├─ P3.3: Machine Learning Factors
├─ P3.4: Cloud Deployment (AWS EC2 + RDS)
└─ P3.5: Advanced Reporting (PDF/HTML)
```

---

## 통합 타임라인

### Week-by-Week Breakdown

```
┌────────────────────────────────────────────────────────────────────┐
│                        12-Week Roadmap                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Week 1-2: P0 - MVP Foundation                                     │
│  ├─ Database Migration (PostgreSQL + TimescaleDB)                 │
│  ├─ CLI Infrastructure (Config, Output, Auth)                     │
│  ├─ API Backend (FastAPI + Auth Routes)                           │
│  └─ Data Collection (Reuse Spock modules)                         │
│  ✓ Milestone: Login → Data Query → Display Works                  │
│                                                                     │
│  Week 3-4: P1 - Core Quant Features                               │
│  ├─ Factor Library (5 categories, 22 factors)                     │
│  ├─ Backtesting Engine (backtrader)                               │
│  ├─ CLI Backtest Command                                          │
│  └─ Strategy Management (CRUD)                                    │
│  ✓ Milestone: End-to-End Backtest Works                           │
│                                                                     │
│  Week 5-6: P2.1 - Portfolio Optimization                          │
│  ├─ Mean-Variance Optimizer (cvxpy)                               │
│  ├─ Risk Parity Optimizer                                         │
│  ├─ CLI Optimize Command                                          │
│  └─ Constraint Handler                                            │
│  ✓ Milestone: Portfolio Optimization Works                        │
│                                                                     │
│  Week 7-8: P2.2 - Risk Management & TUI                           │
│  ├─ VaR/CVaR Calculator                                           │
│  ├─ Stress Testing Framework                                      │
│  ├─ TUI Dashboard (Textual)                                       │
│  └─ CLI Risk Commands                                             │
│  ✓ Milestone: Production-Ready MVP                                │
│                                                                     │
│  Week 9-10: P2.3 - Advanced Backtesting                           │
│  ├─ Walk-Forward Optimizer                                        │
│  ├─ Monte Carlo Simulator                                         │
│  ├─ Streamlit Dashboard                                           │
│  └─ Performance Attribution                                       │
│  ✓ Milestone: Research Platform Complete                          │
│                                                                     │
│  Week 11-12: P3 - Optional Enhancements                           │
│  ├─ AWS CLI Auth (if needed)                                      │
│  ├─ Cloud Deployment (AWS)                                        │
│  ├─ Additional Engines (zipline, vectorbt)                        │
│  └─ ML Factors (optional)                                         │
│  ✓ Milestone: Full-Featured Platform                              │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### Critical Path (최소 실행 경로)

**목표**: 4주 안에 실제 사용 가능한 시스템

```
Week 1 → Database + CLI Infrastructure
Week 2 → Authentication + API Backend
Week 3 → Factor Library + Backtesting Engine
Week 4 → Backtest Command + Strategy Management
```

**결과**: Backtest 실행 → 결과 분석 → 전략 저장 가능

---

## Phase별 상세 계획

### Phase 0: MVP Foundation (Week 1-2) - 🔄 **진행 중**

**목표**: 로그인 → 데이터 조회 → 결과 출력 동작

#### P0.1: Database Migration (Week 1, Day 1-2, 8h) - ✅ **완료**

**작업**:
1. PostgreSQL 15 설치 및 TimescaleDB extension 활성화
2. Spock SQLite 데이터 마이그레이션 (250일 → 전체 이력)
3. Authentication schema 추가 (users, sessions, audit_log)
4. Continuous aggregates 설정 (monthly, yearly)

**산출물**:
- `scripts/migrate_from_sqlite.py` - 마이그레이션 스크립트
- `scripts/init_auth_schema.py` - 인증 스키마 초기화
- `docs/DATABASE_SCHEMA.md` - 스키마 문서

**검증**:
```bash
psql -d quant_platform -c "\dt"
psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"
```

#### P0.2: CLI Infrastructure (Week 1, Day 3-4, 12h) - ✅ **완료**

**작업**:
1. ✅ 디렉토리 구조 생성 (cli/, api/, config/)
2. ✅ ConfigLoader 구현 (YAML + env vars)
3. ✅ OutputFormatter 구현 (Rich tables, panels, progress)
4. ✅ Main entry point (quant_platform.py with argparse)

**산출물**:
- `cli/utils/config_loader.py` - 설정 관리
- `cli/utils/output_formatter.py` - 출력 포매팅
- `quant_platform.py` - 메인 진입점
- `config/cli_config.yaml` - 설정 파일

**검증**:
```bash
python3 quant_platform.py --help
python3 quant_platform.py --version
```

#### P0.3: Authentication System (Week 1, Day 5, 8h) - ⏳ **미완료**

**작업**:
1. ⏳ AuthManager 구현 (Simple Auth mode)
2. ⏳ Setup command (첫 번째 admin 계정 생성)
3. ⏳ Auth command (login, logout, status)
4. ⏳ Session 파일 저장/로드

**산출물**:
- `cli/utils/auth_manager.py` - 인증 관리
- `cli/commands/setup.py` - Setup wizard
- `cli/commands/auth.py` - Auth commands

**검증**:
```bash
python3 quant_platform.py setup
python3 quant_platform.py auth login
python3 quant_platform.py auth status
```

#### P0.4: API Communication Layer (Week 2, Day 1-2, 10h) - ✅ **완료**

**작업**:
1. ✅ API Client wrapper (httpx with retry logic)
2. ✅ FastAPI backend setup (main.py, CORS, logging)
3. 🔄 Auth routes (/login, /logout, /me) - 부분 구현
4. ✅ Database connection pool

**산출물**:
- `cli/utils/api_client.py` - HTTP client
- `api/main.py` - FastAPI app
- `api/routes/auth_routes.py` - Auth endpoints

**검증**:
```bash
# Terminal 1
uvicorn api.main:app --reload

# Terminal 2
python3 quant_platform.py auth login
curl http://localhost:8000/docs
```

#### P0.5: Basic Data Collection (Week 2, Day 3, 4h) - ✅ **완료**

**작업**:
1. ✅ Reuse Spock data collection modules (70% 재사용)
2. ✅ Extend retention policy (250 days → unlimited) - PostgreSQL/TimescaleDB 사용
3. 🔄 Setup daily data update cron job - 수동 실행 가능

**산출물**:
- No new files (reuse existing)
- Update `modules/kis_data_collector.py` retention config

**검증**:
```bash
python3 modules/kis_data_collector.py --region KR --update
psql -d quant_platform -c "SELECT MAX(date) FROM ohlcv_data;"
```

#### P0 완료 기준

- [x] PostgreSQL database 실행 중 - ✅ 완료
- [ ] Setup → Login → Status 플로우 동작 - ⏳ Auth 미구현
- [x] API backend 실행 가능 - ✅ 완료
- [x] 데이터 조회 가능 (CLI 또는 API) - ✅ 완료

**예상 소요**: 42시간 (Week 1-2, 약 10일)

---

### Phase 1: Core Quant Features (Week 3-4) - 🔄 **진행 중**

**목표**: Backtest 실행 → 결과 분석 가능

#### P1.1: Factor Library (Week 3, Day 1-3, 12h) - ✅ **완료**

**작업**:
1. ✅ Factor base class 정의 (`modules/factors/factor_base.py`)
2. ✅ 5개 카테고리 구현:
   - ✅ Value: P/E, P/B, EV/EBITDA, Dividend Yield
   - ✅ Momentum: 12-month return, RSI momentum
   - ✅ Quality: ROE, Debt/Equity
   - ✅ Low-Volatility: Historical vol, Beta
   - ✅ Size: Market cap
   - ✅ **추가 완료**: Growth, Efficiency factors

3. ✅ Factor combiner (weighted average)
4. ✅ Factor analyzer (historical performance)

**산출물**:
- `modules/factors/factor_base.py`
- `modules/factors/value_factors.py`
- `modules/factors/momentum_factors.py`
- `modules/factors/quality_factors.py`
- `modules/factors/low_vol_factors.py`
- `modules/factors/size_factors.py`
- `modules/factors/factor_combiner.py`

**검증**:
```python
from modules.factors.value_factors import PERatio
factor = PERatio()
score = factor.calculate('005930', 'KR')
print(f"Samsung PE Ratio: {score}")
```

#### P1.2: Backtesting Engine (Week 3, Day 4-5, 10h) - ❌ **미완료** (CRITICAL)

**작업**:
1. ❌ backtrader adapter 구현
2. ❌ Transaction cost model (commission, slippage)
3. ❌ Performance metrics calculator
4. ❌ Database integration (backtest_results 테이블)

**⚠️ 우선순위 높음**: 백테스팅 엔진 없이는 전략 검증 불가

**산출물**:
- `modules/backtest/backtest_engine.py`
- `modules/backtest/backtrader_adapter.py`
- `modules/backtest/transaction_cost_model.py`
- `modules/backtest/performance_metrics.py`

**검증**:
```python
from modules.backtest.backtest_engine import BacktestEngine
engine = BacktestEngine()
results = engine.run(strategy='momentum_value', start='2020-01-01', end='2023-12-31')
print(f"Total Return: {results['total_return']:.2%}")
```

#### P1.3: CLI Backtest Command (Week 4, Day 1-2, 8h) - ❌ **미완료** (Blocked by P1.2)

**작업**:
1. ❌ Backtest command 구현 (run, list, show, delete)
2. ❌ API backend routes (/api/v1/backtest)
3. ❌ Results formatting (tables, charts)
4. ❌ Progress bar for long-running backtests

**⚠️ Dependency**: P1.2 백테스팅 엔진 필요

**산출물**:
- `cli/commands/backtest.py`
- `api/routes/backtest_routes.py`
- `api/services/backtest_service.py`

**검증**:
```bash
python3 quant_platform.py backtest run \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31

python3 quant_platform.py backtest list
```

#### P1.4: Strategy Management (Week 4, Day 3, 6h) - ⏳ **미완료**

**작업**:
1. ⏳ Strategy CRUD commands
2. ⏳ YAML strategy definition parsing
3. ⏳ Database storage (strategies table)

**산출물**:
- `cli/commands/strategy.py`
- `api/routes/strategy_routes.py`

**검증**:
```bash
python3 quant_platform.py strategy list
python3 quant_platform.py strategy create --name test --file strategies/test.yaml
```

#### P1.5: Performance Metrics (Week 4, Day 4, 4h) - ❌ **미완료** (Blocked by P1.2)

**작업**:
1. ❌ Sharpe, Sortino, Calmar ratio calculators
2. ❌ Drawdown analysis
3. ❌ Trade analysis (win rate, avg profit)

**⚠️ Dependency**: P1.2 백테스팅 엔진의 일부로 구현 필요

**산출물**:
- `modules/backtest/performance_metrics.py` (extend)

**검증**:
```python
from modules.backtest.performance_metrics import calculate_sharpe_ratio
sharpe = calculate_sharpe_ratio(returns)
print(f"Sharpe Ratio: {sharpe:.2f}")
```

#### P1 완료 기준

- [x] 22개 factor 계산 가능 - ✅ 완료 (30+ factors)
- [ ] Backtest 실행 → 결과 저장 - ❌ **CRITICAL** (P1.2 블로커)
- [ ] CLI로 backtest run/list/show 동작 - ❌ **CRITICAL** (P1.3 블로커)
- [ ] Strategy CRUD 동작 - ⏳ 미완료

**예상 소요**: 40시간 (Week 3-4, 약 10일)

---

### Phase 2: Advanced Features (Week 5-8) - 🔄 **부분 완료**

#### P2.1: Portfolio Optimization (Week 5-6, 16h) - ✅ **완료**

**작업**:
1. ✅ Mean-Variance optimizer (cvxpy)
2. ✅ Risk Parity optimizer
3. ✅ Black-Litterman model
4. ✅ Constraint handler (position/sector limits)
5. ⏳ CLI optimize command - 미완료

**산출물**:
- `modules/optimization/mean_variance_optimizer.py`
- `modules/optimization/risk_parity_optimizer.py`
- `modules/optimization/black_litterman_optimizer.py`
- `modules/optimization/constraint_handler.py`
- `cli/commands/optimize.py`

**검증**:
```bash
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15
```

#### P2.2: Risk Management (Week 7, Day 1-3, 12h) - 🔄 **부분 완료**

**작업**:
1. ✅ VaR calculator (Historical, Parametric, Monte Carlo)
2. ✅ CVaR calculator
3. ⏳ Stress testing framework - 미완료
4. ⏳ Correlation analyzer - 미완료

**산출물**:
- `modules/risk/var_calculator.py`
- `modules/risk/cvar_calculator.py`
- `modules/risk/stress_tester.py`
- `modules/risk/correlation_analyzer.py`
- `cli/commands/risk.py`

**검증**:
```bash
python3 quant_platform.py risk var --confidence 0.95 --horizon 10
```

#### P2.3: TUI Interface (Week 7, Day 4-5 + Week 8, 20h) - ❌ **미완료**

**작업**:
1. ❌ Textual app framework
2. ❌ 5 screens (Dashboard, Strategies, Backtests, Portfolio, Settings)
3. ❌ Widgets (ASCII charts, tables, progress)
4. ❌ Key bindings

**⚠️ 참고**: TUI는 선택 기능, 우선순위 낮음

**산출물**:
- `tui/app.py`
- `tui/screens/dashboard.py`
- `tui/screens/strategies.py`
- `tui/screens/backtests.py`
- `tui/screens/portfolio.py`
- `tui/screens/settings.py`

**검증**:
```bash
python3 quant_platform.py --tui
```

#### P2.4: Streamlit Dashboard (Week 8, 8h) - 🔄 **부분 완료**

**작업**:
1. ✅ Dashboard layout - 기본 구조 완료
2. 🔄 Interactive charts (Plotly) - 일부 완료
3. ⏳ Strategy builder page - 미완료
4. ⏳ Backtest results viewer - 미완료 (P1.2 dependency)

**산출물**:
- `dashboard/app.py`
- `dashboard/pages/1_strategy_builder.py`
- `dashboard/pages/2_backtest_results.py`

**검증**:
```bash
streamlit run dashboard/app.py
```

#### P2 완료 기준

- [x] Portfolio optimization 3가지 방법 동작 - ✅ 완료 (Mean-Variance, Risk Parity, Black-Litterman)
- [x] VaR/CVaR 계산 가능 - ✅ 완료
- [ ] TUI dashboard 실행 가능 - ❌ 미구현 (선택사항)
- [x] Streamlit dashboard 실행 가능 - 🔄 부분 완료

**예상 소요**: 56시간 (Week 5-8, 약 14일)

---

### Phase 3: Optional Enhancements (Week 9-12) - ❌ **미구현** (Optional)

#### P3.1: AWS CLI Authentication (Week 9, 8h) - ❌ **미구현**

**작업**:
1. AWS STS integration
2. boto3 credential detection
3. AWS ARN-based user provisioning

**산출물**:
- `cli/utils/aws_auth.py`
- Update `api/routes/auth_routes.py`

**검증**:
```bash
python3 quant_platform.py --auth aws auth login
```

#### P3.2: Additional Backtesting Engines (Week 10, 12h) - ❌ **미구현**

**작업**:
1. zipline adapter
2. vectorbt adapter
3. Engine comparison utilities

**산출물**:
- `modules/backtest/zipline_adapter.py`
- `modules/backtest/vectorbt_adapter.py`

#### P3.3: Walk-Forward Optimizer (Week 11, 10h) - ❌ **미구현**

**작업**:
1. Out-of-sample testing framework
2. Rolling window optimization
3. Performance degradation detection

**산출물**:
- `modules/optimization/walk_forward_optimizer.py`

#### P3.4: Cloud Deployment (Week 12, 8h) - ❌ **미구현**

**작업**:
1. AWS EC2 setup scripts
2. RDS PostgreSQL configuration
3. HTTPS with Let's Encrypt
4. Deployment guide

**산출물**:
- `scripts/deploy_aws.sh`
- `docs/CLOUD_DEPLOYMENT_GUIDE.md`

#### P3 완료 기준 (모두 선택사항)

- [ ] AWS Auth 동작 (선택) - ❌ 미구현
- [ ] 3가지 백테스팅 엔진 사용 가능 (선택) - ❌ 미구현
- [ ] Walk-forward optimization 동작 (선택) - ❌ 미구현
- [ ] Cloud deployment 가능 (선택) - ❌ 미구현

**예상 소요**: 38시간 (Week 9-12, 약 10일)

---

## 의존성 맵

### Component Dependencies

```
Database (P0.1)
    ↓
┌───────────────────────────────────────┐
│ CLI Infrastructure (P0.2)             │
│    ↓                                  │
│ Authentication (P0.3) → API Layer (P0.4) → Data Collection (P0.5)
│    ↓                        ↓                   ↓
│ Factor Library (P1.1) ←─────┴───────────────────┘
│    ↓
│ Backtesting Engine (P1.2) → Backtest Command (P1.3)
│    ↓                              ↓
│ Strategy Management (P1.4) ←──────┘
│    ↓
│ Portfolio Optimization (P2.1)
│    ↓
│ Risk Management (P2.2)
│    ↓
│ TUI (P2.3) + Streamlit (P2.4)
│    ↓
│ Optional Features (P3.1-P3.4)
└───────────────────────────────────────┘
```

### Parallel Development Opportunities

**병렬 가능**:
- P0.2 (CLI) + P0.5 (Data Collection)
- P1.1 (Factors) + P1.4 (Strategy Management)
- P2.1 (Optimization) + P2.2 (Risk)
- P2.3 (TUI) + P2.4 (Streamlit)

**순차 필수**:
- P0.1 → P0.3 (Database → Auth)
- P1.1 → P1.2 (Factors → Backtest)
- P1.2 → P1.3 (Engine → CLI Command)

---

## 검증 체크포인트

### Milestone 1: MVP Alpha (Week 2 완료)

**검증 항목**:
```bash
# 1. Database 동작
psql -d quant_platform -c "SELECT COUNT(*) FROM users;"

# 2. Authentication 플로우
python3 quant_platform.py setup
python3 quant_platform.py auth login
python3 quant_platform.py auth status

# 3. API 통신
curl http://localhost:8000/api/v1/auth/me

# 4. 데이터 조회
psql -d quant_platform -c "SELECT * FROM ohlcv_data LIMIT 5;"
```

**통과 기준**: 모든 명령 성공, 에러 없음

---

### Milestone 2: MVP 1.0 (Week 4 완료)

**검증 항목**:
```bash
# 1. Factor 계산
python3 -c "from modules.factors.value_factors import PERatio; print(PERatio().calculate('005930', 'KR'))"

# 2. Backtest 실행
python3 quant_platform.py backtest run \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31

# 3. 결과 조회
python3 quant_platform.py backtest list
python3 quant_platform.py backtest show <backtest_id>

# 4. Strategy 관리
python3 quant_platform.py strategy list
```

**통과 기준**:
- Backtest 완료 → 결과 DB 저장
- Sharpe ratio >1.0 (실제 전략 성능)
- 실행 시간 <60초 (5년 시뮬레이션)

---

### Milestone 3: Production Ready (Week 8 완료)

**검증 항목**:
```bash
# 1. Portfolio optimization
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15

# 2. Risk analysis
python3 quant_platform.py risk var --confidence 0.95

# 3. TUI 실행
python3 quant_platform.py --tui

# 4. Streamlit 실행
streamlit run dashboard/app.py
```

**통과 기준**:
- Optimization 수렴 (최적 해 발견)
- VaR <5% (95% 신뢰구간)
- TUI/Streamlit 정상 로드

---

### Milestone 4: Full Featured (Week 12 완료)

**선택사항**, 필요시 구현:
- AWS Auth 동작
- Cloud deployment 성공
- 3가지 백테스팅 엔진 비교

---

## 리스크 관리

### 주요 리스크

| 리스크 | 영향도 | 가능성 | 완화 전략 |
|-------|-------|-------|----------|
| **Database 마이그레이션 실패** | High | Medium | SQLite 백업 유지, 점진적 마이그레이션 |
| **Backtest 성능 저하** | High | Low | 벡터화 연산, 캐싱 전략 |
| **Factor 데이터 부족** | Medium | Medium | yfinance fallback, 데이터 보간 |
| **API 응답 시간 초과** | Medium | Low | 비동기 처리, 타임아웃 설정 |
| **AWS 비용 초과** | Low | Low | Local 우선 개발, Cloud는 선택 |

### 대응 방안

**Database 마이그레이션 실패**:
- 백업: SQLite 원본 보관
- 검증: 마이그레이션 후 row count 비교
- Rollback: 마이그레이션 스크립트 되돌리기 지원

**Backtest 성능 저하**:
- Profiling: cProfile로 병목 지점 식별
- 최적화: NumPy vectorization, pandas apply 제거
- 캐싱: 중간 계산 결과 Redis 캐싱

**Factor 데이터 부족**:
- Fallback: yfinance → Polygon.io → KIS API 순서
- 보간: 선형 보간 또는 forward fill
- 알림: 데이터 누락 시 경고 로그

---

## 실행 지침

### Quick Start (Week 1 시작)

```bash
# 1. PostgreSQL 설치 및 설정
brew install postgresql timescaledb
brew services start postgresql
createdb quant_platform

# 2. Python 환경 설정
cd ~/spock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_cli.txt

# 3. Database 마이그레이션
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db
python3 scripts/init_auth_schema.py

# 4. CLI 실행 확인
python3 quant_platform.py --help
python3 quant_platform.py setup
python3 quant_platform.py auth login
```

### 일일 개발 루틴

```bash
# Morning: Pull latest, check status
git pull
python3 quant_platform.py auth status
uvicorn api.main:app --reload &  # Background

# Development: Implement feature
# ... coding ...

# Testing: Run tests
pytest tests/ -v

# Evening: Commit and push
git add .
git commit -m "feat: implement <feature>"
git push
```

### 주간 검증 (매주 금요일)

```bash
# 1. 통합 테스트
pytest tests/integration/ -v

# 2. 성능 테스트
pytest tests/performance/ --benchmark-only

# 3. Coverage 확인
pytest --cov=cli --cov=api --cov=modules tests/

# 4. Backtest 샘플 실행
python3 quant_platform.py backtest run --strategy momentum_value \
  --start $(date -d '-1 year' +%Y-%m-%d) --end $(date +%Y-%m-%d)
```

---

## 참조 문서

**설계 문서**:
- `QUANT_PLATFORM_CLI_DESIGN.md` - CLI 전체 설계
- `AUTHENTICATION_ARCHITECTURE.md` - 인증 시스템 설계
- `QUANT_PLATFORM_CLI_IMPLEMENTATION_PLAN.md` - CLI 구현 플랜
- `IMPLEMENTATION_CHECKLIST_CLI.md` - 원본 체크리스트
- `CLAUDE.md` - Quant Platform 전체 개요

**실행 가이드**:
- `CLI_DESIGN_SUMMARY.md` - 빠른 참조
- `AUTHENTICATION_REVIEW_SUMMARY_KR.md` - 인증 한글 요약

---

## 버전 이력

| 버전 | 날짜 | 변경 사항 |
|-----|------|----------|
| 1.0.0 | 2025-10-22 | 초기 통합 로드맵 작성 |

---

**최종 업데이트**: 2025-10-22
**작성자**: Quant Platform Development Team
**상태**: 실행 준비 완료 - Week 1 Day 1부터 시작 가능
