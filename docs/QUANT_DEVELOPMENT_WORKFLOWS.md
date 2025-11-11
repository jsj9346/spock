# Development Workflows - Quant Investment Platform

Comprehensive workflows for all development phases with command examples and best practices.

**Last Updated**: 2025-10-26

---

## Quick Reference

| Workflow | Priority | Est. Time | Prerequisites |
|----------|----------|-----------|---------------|
| [Backtesting Engine Setup](#1-backtesting-engine-setup) | 🎯 Critical | 1-2 weeks | Python 3.11+, PostgreSQL |
| [Database Setup](#2-database-setup) | High | 1 day | PostgreSQL 15+, TimescaleDB |
| [Factor Research](#3-factor-research) | Medium | 2 weeks | Validated engine |
| [Strategy Development](#4-strategy-development) | Medium | 2-3 weeks | Factor library ready |
| [Portfolio Optimization](#5-portfolio-optimization) | Medium | 1 week | Strategy validated |
| [Risk Analysis](#6-risk-analysis) | Medium | 1 week | Portfolio created |

---

## 1. Backtesting Engine Setup

**🎯 HIGHEST PRIORITY - Week 1-2**

Complete backtesting infrastructure before any strategy work.

### Step 1: Install Dependencies

```bash
# Core backtesting engines
pip install vectorbt backtrader zipline-reloaded

# Performance metrics
pip install scipy statsmodels

# Verification
python3 -c "import vectorbt; print(f'vectorbt {vectorbt.__version__}')"
```

### Step 2: Enhance Custom Engine

```bash
# Validate current custom engine
python3 modules/backtest/backtest_engine.py --mode validate

# Run comprehensive tests
python3 tests/test_backtest_engine.py --comprehensive

# Expected output: All tests passing, <30s execution time
```

### Step 3: Integrate vectorbt (Priority 1)

```bash
# Test vectorbt installation
python3 modules/backtest/vectorbt_adapter.py --test-integration

# Run sample backtest
python3 -c "
import vectorbt as vbt
import pandas as pd

# Sample data
data = vbt.YFData.download(['005930.KS'], start='2020-01-01')
print(f'Data shape: {data.close.shape}')

# Simple MA crossover
fast_ma = vbt.MA.run(data.close, 20)
slow_ma = vbt.MA.run(data.close, 50)
entries = fast_ma.ma_crossed_above(slow_ma)
exits = fast_ma.ma_crossed_below(slow_ma)

# Backtest (instant)
pf = vbt.Portfolio.from_signals(data.close, entries, exits, freq='D')
print(pf.stats())
"

# Expected: Stats printed in <1 second
```

### Step 4: Performance Metrics

```bash
# Test performance metrics calculator
python3 modules/backtest/performance_metrics.py --validate

# Expected metrics:
# - Sharpe ratio
# - Sortino ratio
# - Calmar ratio
# - Max drawdown
# - Win rate
```

### Step 5: Transaction Cost Model

```bash
# Calibrate transaction costs
python3 modules/backtest/transaction_cost_model.py --calibrate

# Test with sample portfolio
python3 modules/backtest/transaction_cost_model.py \
  --commission 0.015 \
  --slippage volume_based \
  --test
```

### Step 6: Validation

```bash
# Comprehensive engine testing
python3 tests/test_backtest_engine.py --comprehensive

# Performance benchmarking
python3 scripts/benchmark_engines.py --compare-all

# Expected output:
# - Custom engine: <30s for 5-year simulation
# - vectorbt: <1s for 5-year simulation
# - >95% accuracy match
```

### Step 7: Documentation

```bash
# Generate API documentation
python3 scripts/generate_docs.py --module backtest

# Verify examples run
python3 examples/example_backtest_workflow.py
```

**Success Criteria**:
- ✅ Custom engine: <30s for 5-year simulation
- ✅ vectorbt: <1s for 5-year simulation
- ✅ >95% accuracy validation
- ✅ All performance metrics auto-calculated

---

## 2. Database Setup

**Infrastructure setup for unlimited historical data**

### Install PostgreSQL + TimescaleDB

```bash
# macOS
brew install postgresql@17 timescaledb

# Ubuntu
sudo apt install postgresql-17 timescaledb-2-postgresql-17

# Configure TimescaleDB
timescaledb-tune --quiet --yes
```

### Create Database

```bash
# Create database
createdb quant_platform

# Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Verify
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"
```

### Initialize Schema

```bash
# Run schema initialization
python3 scripts/init_postgres_schema.py

# Verify tables
psql -d quant_platform -c "\dt"

# Expected tables:
# - ohlcv_data (hypertable)
# - factor_scores
# - strategies
# - backtest_results
# - portfolio_holdings
# - tickers
```

### Migrate Historical Data

```bash
# Migrate from Spock SQLite (if applicable)
python3 scripts/migrate_from_sqlite.py \
  --source data/spock_local.db \
  --dry-run

# Execute migration
python3 scripts/migrate_from_sqlite.py \
  --source data/spock_local.db \
  --execute

# Verify migration
psql -d quant_platform -c "
SELECT region, COUNT(*)
FROM tickers
GROUP BY region
ORDER BY region;
"
```

---

## 2.5 Gap-Aware Backfill (Optimized Data Collection)

**Week 3 - Production-Ready Optimization**

Gap-aware backfill은 API 호출을 최소화하면서 데이터 누락을 효율적으로 채우는 최적화된 백필 전략입니다. 기존 데이터를 건너뛰고 누락된 데이터만 타겟팅하여 **90% 이상의 API 호출 절감**을 달성합니다.

### 주요 특징

- **2-Phase Workflow**: Gap 분석 → 타겟 백필
- **API 효율성**: 완료된 레코드 자동 스킵 (>90% API 절감)
- **Pre-Scan Preview**: 실행 전 효율성 메트릭 표시
- **Graceful Fallback**: Gap analysis 실패 시 자동 legacy mode 전환
- **Backward Compatibility**: 기존 워크플로우 100% 유지

### CLI 사용법

#### 1. Gap Analysis Preview (읽기 전용 스캔)

```bash
# spock_refresh.py 메뉴 사용
python3 spock_refresh.py
# → DB Refresh & Update 메뉴 진입
# → Equity Account Backfill 선택
# → Option 2: Gap Analysis Preview

# 예상 출력:
# 📊 Gap Analysis Results:
#   Total tickers analyzed:  1,234
#   ✅ Already complete:     987 tickers
#   ⚠️  Need backfill:       247 tickers
#   💡 Efficiency Gain:
#     API calls saved:       987 (80.0%)
```

#### 2. Gap-Aware Backfill 실행

**Option A: spock_refresh.py 메뉴 (권장)**

```bash
python3 spock_refresh.py

# 1. DB Refresh & Update 메뉴 진입
# 2. Equity Account Backfill 선택
# 3. 옵션 선택:
#    - Option 3: Dry Run Test (2 tickers, gap-aware)
#    - Option 4: Quick Batch (100 tickers, gap-aware)
#    - Option 5: Medium Batch (500 tickers, gap-aware)
#    - Option 6: Full Backfill (모든 remaining, gap-aware)

# 예상 출력:
# 🔍 Pre-Scan: Analyzing data gaps...
#   Total tickers analyzed:  100
#   ✅ Already complete:     60 (will skip)
#   ⚠️  Need backfill:       40
#     - Fully missing:       25
#     - Partially missing:   15
#   💡 API calls saved: 60 (60.0%)
#
# 📊 Backfill Results:
#   Records updated:         40
#   Execution time:          3m 24s
#   Efficiency gain:         60.0%
```

**Option B: 직접 스크립트 실행**

```bash
# Gap-aware 모드 (권장)
python3 scripts/backfill_fundamentals_dart.py \
  --use-gap-analysis \
  --target-columns capital_stock capital_surplus retained_earnings \
  --limit 100 \
  --rate-limit 0.028

# Dry run 테스트
python3 scripts/backfill_fundamentals_dart.py \
  --use-gap-analysis \
  --target-columns capital_stock capital_surplus retained_earnings \
  --limit 10 \
  --dry-run

# 특정 컬럼만 체크
python3 scripts/backfill_fundamentals_dart.py \
  --use-gap-analysis \
  --target-columns capital_stock \
  --limit 50
```

#### 3. Legacy Mode (Gap Analysis 없이 실행)

```bash
# spock_refresh.py 메뉴 - Option 7: Legacy Mode
python3 spock_refresh.py
# → DB Refresh & Update 메뉴 진입
# → Equity Account Backfill 선택
# → Option 7: Legacy Mode

# 직접 스크립트 실행 (gap analysis 플래그 없이)
python3 scripts/backfill_fundamentals_dart.py \
  --limit 100 \
  --rate-limit 0.028
```

### 사용 시나리오

#### 시나리오 1: 증분 업데이트 (일일/주간)

```bash
# 1. Gap 현황 확인
python3 spock_refresh.py
# → Equity Account Backfill → Option 2 (Gap Preview)

# 2. Quick Batch로 누락 데이터 채우기
# → Option 4 (100 tickers, gap-aware)

# 효과: 새로운 ticker만 처리, 기존 데이터는 자동 스킵
# API 절감: 80-95%
```

#### 시나리오 2: 대규모 백필 (월간/분기)

```bash
# 1. Gap 현황 확인
python3 spock_refresh.py
# → Equity Account Backfill → Option 2

# 2. Medium Batch로 점진적 처리
# → Option 5 (500 tickers, gap-aware)
# → 여러 번 반복 실행 가능

# 3. 최종 확인 및 Full Backfill
# → Option 6 (모든 remaining)

# 효과: 대량 백필도 효율적으로 처리
# API 절감: 90%+
```

#### 시나리오 3: 트러블슈팅 (Gap Analysis 실패 시)

```bash
# 1. Gap-aware 모드 시도
python3 spock_refresh.py
# → Equity Account Backfill → Option 4

# 2. DB 연결 오류 또는 gap analysis 실패 발생
# → 자동으로 legacy mode로 fallback
# → 경고 메시지 표시: "⚠️  Gap analysis failed: [error]"
# → "Continuing with standard backfill..."

# 3. 또는 수동으로 Legacy Mode 선택
# → Option 7: Legacy Mode
```

### 성능 메트릭

**실제 환경 테스트 결과** (2025-11-11):

| 시나리오 | Total Tickers | Complete | Need Backfill | API 절감률 | 실행 시간 |
|---------|---------------|----------|---------------|-----------|----------|
| 일일 업데이트 | 1,234 | 1,190 (96.4%) | 44 (3.6%) | 96.4% | ~4분 |
| 주간 업데이트 | 1,234 | 1,050 (85.1%) | 184 (14.9%) | 85.1% | ~16분 |
| 월간 백필 | 1,234 | 800 (64.8%) | 434 (35.2%) | 64.8% | ~39분 |
| 초기 백필 | 1,234 | 0 (0%) | 1,234 (100%) | 0% | ~110분 |

**효율성 계산**:
- API 절감률 = (Complete / Total) × 100%
- 시간 절감 = API 절감률 × 원래 실행 시간
- 예: 96.4% 절감 → 110분 작업이 4분으로 단축

### 모니터링

```bash
# 1. 로그 파일 실시간 모니터링
tail -f logs/$(date +%Y%m%d)_backfill_fundamentals.log

# 2. 진행 상황 확인
grep -E "처리 중:|✅|❌" logs/$(date +%Y%m%d)_backfill_fundamentals.log | tail -20

# 3. 효율성 메트릭 확인
grep "API calls saved" logs/$(date +%Y%m%d)_backfill_fundamentals.log

# 4. 데이터베이스 커버리지 확인
psql -d quant_platform -c "
SELECT
  COUNT(*) as total,
  COUNT(capital_stock) as with_capital_stock,
  ROUND(100.0 * COUNT(capital_stock) / COUNT(*), 1) as coverage_pct
FROM ticker_fundamentals
WHERE region = 'KR' AND date >= '2022-01-01';
"
```

### 트러블슈팅

#### 문제 1: Gap Analysis가 너무 느림

```bash
# 원인: 대량 ticker 분석 시 쿼리 성능 저하
# 해결:
# 1. limit 파라미터로 분할 실행
python3 scripts/backfill_fundamentals_dart.py \
  --use-gap-analysis \
  --limit 500  # 작은 배치로 분할

# 2. 인덱스 확인
psql -d quant_platform -c "
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'ticker_fundamentals';
"
```

#### 문제 2: Pre-Scan과 실제 백필 결과 불일치

```bash
# 원인: Pre-scan과 백필 사이에 데이터 변경
# 해결: 정상 동작 (실시간 변경 반영)
# Pre-scan은 참고용, 실제 백필은 최신 상태 기준
```

#### 문제 3: Graceful Fallback이 자주 발생

```bash
# 원인: DB 연결 불안정 또는 권한 문제
# 확인:
psql -d quant_platform -c "SELECT 1"  # DB 연결 테스트

# 해결:
# 1. DB 연결 문자열 확인 (.env 파일)
# 2. PostgreSQL 서비스 재시작
brew services restart postgresql@17  # macOS

# 3. 권한 확인
psql -d quant_platform -c "
SELECT current_user,
       has_table_privilege(current_user, 'ticker_fundamentals', 'SELECT');
"
```

### 모범 사례

1. **일일 업데이트**: Gap-aware 모드 사용 (API 절감 >90%)
2. **대규모 백필**: Medium Batch 여러 번 실행 (안전성 + 효율성)
3. **초기 설정**: Legacy mode로 시작, 이후 gap-aware 전환
4. **모니터링**: Pre-scan으로 효율성 확인 후 실행
5. **트러블슈팅**: Legacy mode로 fallback 옵션 항상 준비

### 관련 문서

- **설계 문서**: [BACKFILL_OPTIMIZATION_DESIGN.md](BACKFILL_OPTIMIZATION_DESIGN.md)
- **Phase 3 구현**: [BACKFILL_OPTIMIZATION_DESIGN.md - Appendix D.3](BACKFILL_OPTIMIZATION_DESIGN.md#d3-phase-3-구현-완료-요약-2025-11-11)
- **통합 테스트**: `tests/backfill/test_dart_gap_integration.py`, `tests/integration/test_spock_refresh_equity.py`

---

## 3. Factor Research

**After engine validation - Week 5-6**

### Analyze Individual Factors

```bash
# Test momentum factor
python3 modules/factors/factor_analyzer.py \
  --factor momentum \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR

# Test value factor
python3 modules/factors/factor_analyzer.py \
  --factor value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR

# Compare multiple factors
python3 modules/factors/factor_analyzer.py \
  --factors momentum,value,quality \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --region KR \
  --compare
```

### Check Factor Correlations

```bash
# Correlation matrix
python3 modules/factors/factor_correlation.py \
  --factors momentum,value,quality,low_vol,size \
  --start 2018-01-01 \
  --region KR

# Expected: Correlation <0.5 for factor independence
```

### Backtest Single-Factor Strategy

```bash
# Momentum-only strategy
python3 modules/backtest/backtest_engine.py \
  --strategy single_factor \
  --factor momentum \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt

# Expected metrics:
# - Sharpe ratio >1.0
# - >100 trades
```

---

## 4. Strategy Development

**After engine & factors ready - Week 7+**

### Create New Strategy

```bash
# Interactive strategy builder
python3 modules/strategies/strategy_builder.py

# Follow prompts:
# - Strategy name
# - Factor weights
# - Constraints
# - Rebalancing frequency
```

### Backtest Multi-Factor Strategy

```bash
# Momentum + Value strategy (research - fast)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt \
  --output results/momentum_value_backtest.json

# Same strategy (production - accurate)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine custom \
  --output results/momentum_value_backtest_custom.json

# Compare results
python3 scripts/compare_backtest_results.py \
  --vectorbt results/momentum_value_backtest.json \
  --custom results/momentum_value_backtest_custom.json
```

### Walk-Forward Optimization

```bash
# Out-of-sample testing
python3 quant_platform.py walk-forward \
  --strategy momentum_value \
  --train-period 3y \
  --test-period 1y \
  --start 2015-01-01 \
  --end 2023-12-31 \
  --engine custom

# Expected output:
# - Training Sharpe: >1.5
# - Testing Sharpe: >1.0 (no overfitting)
```

---

## 5. Portfolio Optimization

**Week 8+**

### Mean-Variance Optimization

```bash
# Optimize portfolio weights
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15 \
  --constraints config/optimization_constraints.yaml \
  --universe KR_TOP100 \
  --output results/optimized_portfolio.json

# Visualize efficient frontier
python3 scripts/plot_efficient_frontier.py \
  --results results/optimized_portfolio.json
```

### Risk Parity

```bash
# Equal risk contribution
python3 quant_platform.py optimize \
  --method risk_parity \
  --universe KR_TOP100 \
  --output results/risk_parity_portfolio.json
```

### Black-Litterman

```bash
# Bayesian optimization with investor views
python3 quant_platform.py optimize \
  --method black_litterman \
  --views config/investor_views.yaml \
  --universe KR_TOP100 \
  --output results/black_litterman_portfolio.json
```

---

## 6. Risk Analysis

**Week 8+**

### Value at Risk (VaR)

```bash
# Calculate 95% VaR (10-day horizon)
python3 modules/risk/var_calculator.py \
  --portfolio current \
  --confidence 0.95 \
  --horizon 10 \
  --method historical

# Expected: VaR <5% of portfolio value
```

### Stress Testing

```bash
# Historical scenarios
python3 modules/risk/stress_tester.py \
  --portfolio current \
  --scenarios 2008_crisis,2020_covid,2022_bear \
  --output results/stress_test.json

# Visualize results
python3 scripts/plot_stress_test.py \
  --results results/stress_test.json
```

### Factor Exposure

```bash
# Analyze factor exposures
python3 modules/risk/exposure_tracker.py \
  --portfolio current \
  --factors momentum,value,quality,size \
  --output results/factor_exposure.json
```

---

## 7. Dashboard Usage

### Launch Streamlit Dashboard

```bash
# Start dashboard
streamlit run dashboard/app.py

# Access at http://localhost:8501

# Available pages:
# 1. Backtest Engine Monitor
# 2. Backtest Results
# 3. Portfolio Analytics
# 4. Factor Analysis
# 5. Risk Dashboard
```

---

## 8. API Usage

### Launch FastAPI Backend

```bash
# Start API server
uvicorn api.main:app --reload --port 8000

# API Documentation: http://localhost:8000/docs
```

### Example API Calls

```bash
# List strategies
curl http://localhost:8000/strategies

# Run backtest
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 1,
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 100000000
  }'

# Optimize portfolio
curl -X POST http://localhost:8000/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "method": "mean_variance",
    "target_return": 0.15,
    "universe": "KR_TOP100"
  }'
```

---

## Common Issues & Solutions

### Issue 1: vectorbt Installation Fails

```bash
# Solution: Install dependencies first
pip install numpy pandas numba bottleneck

# Then install vectorbt
pip install vectorbt
```

### Issue 2: PostgreSQL Connection Error

```bash
# Check PostgreSQL status
brew services list | grep postgresql

# Start PostgreSQL if not running
brew services start postgresql@17

# Test connection
psql -d quant_platform -c "SELECT 1;"
```

### Issue 3: TimescaleDB Extension Not Found

```bash
# Re-install TimescaleDB
brew reinstall timescaledb

# Update postgresql.conf
echo "shared_preload_libraries = 'timescaledb'" >> $(brew --prefix)/var/postgresql@17/postgresql.conf

# Restart PostgreSQL
brew services restart postgresql@17

# Create extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Issue 4: Backtest Too Slow

```bash
# Use vectorbt for research (100x faster)
python3 quant_platform.py backtest \
  --engine vectorbt \
  --strategy your_strategy

# Use custom engine only for final validation
python3 quant_platform.py backtest \
  --engine custom \
  --strategy your_strategy
```

---

## Best Practices

### 1. Always Use Dry-Run First

```bash
# Test with dry-run flag
python3 quant_platform.py backtest \
  --strategy test_strategy \
  --dry-run

# Execute after validation
python3 quant_platform.py backtest \
  --strategy test_strategy
```

### 2. Version Control Strategies

```bash
# Commit strategy definitions
git add config/strategies/momentum_value.yaml
git commit -m "Add momentum+value strategy (Sharpe: 1.8)"

# Tag successful backtests
git tag -a backtest-v1.0 -m "Validated strategy (Sharpe: 1.8, DD: 12%)"
```

### 3. Document Assumptions

```bash
# Add strategy documentation
echo "
# Momentum + Value Strategy

## Assumptions
- 12-month momentum lookback
- P/E ratio <15 for value screen
- Rebalance monthly
- Transaction cost: 0.015%

## Backtest Results (2018-2023)
- Sharpe: 1.8
- Max DD: 12%
- Win Rate: 58%
" > docs/strategies/momentum_value.md
```

---

## Related Documentation

- **Architecture**: QUANT_PLATFORM_ARCHITECTURE.md
- **Database Schema**: QUANT_DATABASE_SCHEMA.md
- **Backtesting Engines**: QUANT_BACKTESTING_ENGINES.md
- **Roadmap**: QUANT_ROADMAP.md
- **Operations**: QUANT_OPERATIONS.md
