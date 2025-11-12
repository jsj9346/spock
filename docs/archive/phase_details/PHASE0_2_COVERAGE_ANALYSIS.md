# Phase 0.2 - Test Coverage Expansion Analysis

**Date**: 2025-10-30
**Current Coverage**: 5.48% (1,487 lines covered / 23,613 total)
**Target Coverage**: 70%+ (16,529 lines minimum)
**Gap**: 15,042 lines to cover

---

## Executive Summary

**Current Status**: Phase 0.1 complete (23/23 tests passing)
**Phase 0.2 Goal**: Expand coverage from 5.48% → 70%+ focusing on critical backtesting modules

**Key Findings**:
- Backtesting modules have partial coverage (41% backtest_runner, 58.5% layered_scoring_engine)
- Data providers have 0% coverage (postgres_data_provider, base_data_provider)
- 78 lines currently covered, need 15,042 more for 70% target

---

## Current Coverage Breakdown

### High Coverage Modules (>40%)
| Module | Coverage | Lines Covered | Total Lines |
|--------|----------|---------------|-------------|
| layered_scoring_engine.py | 58.50% | 168/264 | Good foundation |
| kelly_calculator.py | 17.36% | 105/515 | Partially covered |

### Critical Gaps (0% Coverage)
**Backtesting Core**:
- `modules/backtesting/data_providers/postgres_data_provider.py` (0%)
- `modules/backtesting/data_providers/base_data_provider.py` (0%)
- `modules/backtesting/optimization/walk_forward_optimizer.py` (0%)
- `modules/backtesting/validation/` (0% - all validation modules)

**Factors**:
- `modules/factors/value_factors.py` (0% - 132 lines)
- `modules/factors/momentum_factors.py` (0% - 204 lines)
- `modules/factors/quality_factors.py` (0% - 192 lines)
- `modules/factors/low_vol_factors.py` (0% - 79 lines)
- `modules/factors/size_factors.py` (0% - 86 lines)

**Other Critical Modules**:
- `modules/kis_data_collector.py` (0% - 590 lines)
- `modules/market_adapters/` (0% - all adapters)
- `modules/optimization/` (0% - all optimizers)

---

## Phase 0.2 Strategy

### Priority Tiers

**Tier 1 (Critical - Week 0)**: Backtesting Infrastructure
Target: 3 hours | Coverage Impact: +15%

1. **postgres_data_provider.py** (609 lines, 0% → 85%)
   - Connection management tests
   - Query performance tests
   - Cache hit rate tests
   - Batch loading tests
   - **Estimated**: 90 minutes, +600 lines

2. **base_data_provider.py** (85 lines, 0% → 90%)
   - Abstract interface tests
   - Cache mechanism tests
   - **Estimated**: 30 minutes, +75 lines

3. **backtest_config.py** (Current coverage unknown, expand edge cases)
   - Empty equity curve handling (done)
   - Configuration validation
   - **Estimated**: 60 minutes, +100 lines

**Total Tier 1**: 775 lines → +3.3% coverage

---

**Tier 2 (Important - Week 0)**: Validation & Optimization
Target: 2 hours | Coverage Impact: +10%

4. **walk_forward_optimizer.py** (379 lines, 0% → 75%)
   - Window creation tests
   - Rolling/anchored strategy tests
   - Overfitting detection tests
   - **Estimated**: 90 minutes, +280 lines
   - **Note**: 6 tests already exist but failing due to data issues

5. **engine_validator.py** (Currently failing tests)
   - Fix ValidationMetrics constructor issues
   - Comparison logic tests
   - **Estimated**: 30 minutes, +150 lines

**Total Tier 2**: 430 lines → +1.8% coverage

---

**Tier 3 (Optional - Week 1)**: Factor Library
Target: 3-4 hours | Coverage Impact: +2.7%

6. **value_factors.py** (132 lines, 0% → 80%)
7. **momentum_factors.py** (204 lines, 0% → 70%)
8. **quality_factors.py** (192 lines, 0% → 70%)
9. **low_vol_factors.py** (79 lines, 0% → 70%)
10. **size_factors.py** (86 lines, 0% → 70%)

**Total Tier 3**: 463 lines → +2.0% coverage

---

## Realistic Coverage Projection

### Conservative Estimate (Phase 0.2 Focus)
**Tier 1 + Tier 2 Only**: 1,205 lines → **10.6% total coverage**

| Tier | Lines Added | Coverage Gain | Total Coverage |
|------|-------------|---------------|----------------|
| Baseline | 1,487 | - | 5.48% |
| + Tier 1 | +775 | +3.3% | 8.78% |
| + Tier 2 | +430 | +1.8% | 10.58% |

**Reality Check**: 70% target requires 15,042 lines → **Not achievable in Phase 0**

---

## Revised Phase 0.2 Goals

### Must-Have (Achievable in 5-6 hours)
- ✅ **Tier 1**: PostgreSQL data provider coverage (85%)
- ✅ **Tier 2**: Walk-forward optimizer tests fixed + expanded
- ✅ **Target**: 10-12% overall coverage (realistic)

### Should-Have (Week 1 extension)
- **Tier 3**: Factor library coverage (70%+)
- **Target**: 15-20% overall coverage

### Long-Term (Week 2-4)
- Expand all backtesting modules to 85%+
- Add market adapter tests
- Add API client tests
- **Target**: 70% overall coverage

---

## Immediate Action Plan (Phase 0.2)

### Step 1: Fix Existing Failing Tests (30 min)
**Issue**: 6 walk-forward optimizer tests failing due to missing data (ticker 000020, 2024-01-01 to 2024-03-31)

**Solutions**:
A. Add test data for ticker 000020 in date range 2024-01-01 to 2024-03-31
B. Update tests to use existing data range (2024-10-10 to 2024-12-31)
C. Mock data provider in tests

**Recommended**: Option C (fastest, proper unit testing)

### Step 2: PostgreSQL Data Provider Tests (90 min)
**New File**: `tests/backtesting/data_providers/test_postgres_data_provider.py`

**Test Categories**:
- Connection management (10 tests)
- Query execution (15 tests)
- Cache operations (12 tests)
- Batch loading (8 tests)
- Error handling (10 tests)

**Estimated**: 55 new tests, +600 lines coverage

### Step 3: Walk-Forward Optimizer Expansion (90 min)
**Existing File**: `tests/backtesting/optimization/test_walk_forward_optimizer.py`

**Actions**:
- Fix 6 failing tests (mock data provider)
- Add window creation edge cases (5 tests)
- Add parameter grid validation (5 tests)
- Add robustness scoring tests (5 tests)

**Estimated**: 21 new/fixed tests, +280 lines coverage

### Step 4: Validation & Documentation (30 min)
- Run full test suite
- Generate coverage report
- Document achievements
- Update Phase 0.2 completion report

---

## Success Criteria (Revised)

### Phase 0.2 Completion (Must-Have)
- [ ] All backtest_runner tests passing (23/23) ✅ Already complete
- [ ] PostgreSQL data provider coverage >85%
- [ ] Walk-forward optimizer tests fixed + passing
- [ ] Overall coverage >10%
- [ ] <70% coverage failure acknowledged (deferred to Week 1-4)

### Phase 0.2 Extended (Should-Have)
- [ ] Factor library tests added
- [ ] Overall coverage >15%

---

## Risk Assessment

**High Risk**:
- **70% target unrealistic** for Phase 0 (24.9% baseline → 70% requires 10,650 new lines)
- Many modules outside backtesting scope (market adapters, parsers, etc.)

**Medium Risk**:
- Test data availability for walk-forward optimizer
- PostgreSQL connection in test environment

**Low Risk**:
- Backtesting module expansion (high ROI, focused scope)

---

## Recommendation

**Recommended Phase 0.2 Scope**:
1. Focus on Tier 1 + Tier 2 only (5-6 hours)
2. Target 10-12% coverage (achievable, meaningful)
3. Defer 70% target to **Phase 0.3-0.5** (Week 1-4)
4. Prioritize quality over quantity

**Rationale**:
- Phase 0 is "Code Stabilization", not "Comprehensive Testing"
- 70% coverage is a long-term goal requiring weeks of effort
- 10-12% coverage focused on critical paths provides solid foundation
- Allows progression to Phase 1 (MCP Development) sooner

---

**Report Status**: Draft v1.0
**Next Action**: Execute Tier 1 + Tier 2 test expansion
**Estimated Completion**: 5-6 hours
