# Phase 0 - Test Failure Analysis Report

**Date**: 2025-10-30
**Analyst**: Claude (Spock Team)
**Test Suite**: backtest_runner (23 tests)
**Result**: 3 FAILED, 20 PASSED (87% pass rate)

---

## Executive Summary

Test suite analysis reveals **3 primary failure categories** affecting backtest_runner tests:

1. **SQLite Schema Mismatch**: Missing `rsi` column causing SQL errors
2. **Type Assertion Issue**: numpy.bool_ vs Python bool type mismatch
3. **Edge Case Handling**: Empty tickers causing IndexError

**Good News**: 20/23 tests passing (87%), indicating core functionality is stable.

---

## Detailed Failure Analysis

### Failure 1: test_metrics_match_dict
**File**: `tests/backtesting/test_backtest_runner.py:238`
**Error**: `assert False` where `False = isinstance(np.False_, bool)`

**Root Cause**:
```python
# Line 238:
assert isinstance(value, bool)
# Problem: numpy.bool_ (from vectorbt) != Python bool
```

**Impact**: Medium (type checking too strict)

**Fix Strategy**:
```python
# Option A: Accept numpy bool
assert isinstance(value, (bool, np.bool_))

# Option B: Convert to Python bool
assert isinstance(bool(value), bool)
```

**Estimated Time**: 15 minutes

---

### Failure 2: test_validate_consistency
**File**: `tests/backtesting/test_backtest_runner.py` (TestValidation class)
**Error**: `AssertionError: assert False`

**Root Cause**: Likely related to consistency score calculation or comparison logic

**Dependencies**: May be related to Failure 1 (numpy bool issue)

**Fix Strategy**:
1. Review consistency calculation logic
2. Check threshold values
3. Verify test expectations match implementation

**Estimated Time**: 30 minutes

---

### Failure 3: test_empty_tickers
**File**: `tests/backtesting/test_backtest_runner.py` (TestEdgeCases class)
**Error**: `IndexError: single positional indexer is out-of-bounds`

**Root Cause**: Code attempts to access DataFrame index that doesn't exist when tickers list is empty

**Impact**: Low (edge case handling)

**Fix Strategy**:
```python
# Add guard clause
if not tickers or data.empty:
    raise ValueError("No tickers provided or no data available")
```

**Estimated Time**: 20 minutes

---

## Critical Issue: SQLite Schema Mismatch

### Problem
```python
ERROR: Execution failed on sql '
    SELECT date, open, high, low, close, volume,
           ma5, ma20, ma60, ma120, ma200, rsi
    FROM ohlcv_data
    WHERE ticker = ?
    ORDER BY date DESC
    LIMIT 300
    ': no such column: rsi
```

**Affected Module**: `modules/layered_scoring_engine.py:421`
**Frequency**: 27 occurrences in log
**Impact**: HIGH - Blocks LayeredScoringEngine from loading data

### Root Cause Analysis

**PostgreSQL Schema** (correct):
```sql
CREATE TABLE ohlcv_data (
    ...
    rsi DOUBLE PRECISION,
    ...
);
```

**SQLite Schema** (missing rsi):
```sql
CREATE TABLE ohlcv_data (
    date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    ma120 REAL,
    ma200 REAL
    -- ❌ rsi column missing
);
```

### Impact Assessment

**Affected Components**:
- LayeredScoringEngine (cannot load historical data with RSI)
- Any backtest using LayeredScoringEngine as signal generator
- Tests that depend on RSI-based strategies

**Not Affected**:
- PostgreSQL-based operations
- vectorbt-only backtests
- Tests using simple signal generators

---

## Fix Priority Matrix

| Issue | Priority | Impact | Effort | Est. Time |
|-------|----------|--------|--------|-----------|
| SQLite schema sync | **P0** | HIGH | Medium | 4 hours |
| numpy bool type | **P1** | Medium | Low | 15 min |
| validate_consistency | **P1** | Medium | Low | 30 min |
| empty_tickers edge | **P2** | Low | Low | 20 min |

**Total Estimated Time**: 5.25 hours

---

## Recommended Fix Sequence

### Phase 1: Schema Sync (P0)
**Goal**: Add missing `rsi` column to SQLite schema

**Steps**:
1. Compare PostgreSQL vs SQLite schemas
2. Create migration script: `scripts/sync_sqlite_schema.py`
3. Add rsi column: `ALTER TABLE ohlcv_data ADD COLUMN rsi REAL`
4. Backfill RSI values (if needed)
5. Test LayeredScoringEngine

**Script Template**:
```python
# scripts/sync_sqlite_schema.py
import sqlite3

def sync_schema():
    conn = sqlite3.connect('data/spock_local.db')
    cursor = conn.cursor()

    # Check if rsi column exists
    cursor.execute("PRAGMA table_info(ohlcv_data)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'rsi' not in columns:
        print("Adding rsi column...")
        cursor.execute("ALTER TABLE ohlcv_data ADD COLUMN rsi REAL")
        conn.commit()
        print("✅ rsi column added")
    else:
        print("✅ rsi column already exists")

    conn.close()

if __name__ == "__main__":
    sync_schema()
```

---

### Phase 2: Test Fixes (P1)
**Goal**: Fix 3 failing test assertions

**test_metrics_match_dict**:
```python
# tests/backtesting/test_backtest_runner.py:238
# Before:
assert isinstance(value, bool)

# After:
import numpy as np
assert isinstance(value, (bool, np.bool_))
```

**test_validate_consistency**:
- Review consistency score logic
- Adjust test expectations or fix calculation

**test_empty_tickers**:
```python
# modules/backtesting/backtest_runner.py
def run_backtest(self, tickers, ...):
    if not tickers:
        raise ValueError("Tickers list cannot be empty")
    # ... rest of code
```

---

## Coverage Analysis

**Current Coverage**: 5.24% (from test output)
**Target**: 70%

**Critical Gap**: Coverage failure indicates most modules/backtesting/ code is not tested

**Uncovered Modules** (likely):
- `modules/backtesting/walk_forward_optimizer.py` (0%)
- `modules/backtesting/backtest_engines/` (partial)
- `modules/factors/` (unknown)

---

## Success Criteria (Phase 0.1)

### Must-Have (Blocking):
- [x] Test suite runs to completion (no hanging)
- [x] SQLite schema includes `rsi` column
- [x] 0 LayeredScoringEngine SQL errors
- [x] 3 failing tests fixed → 23/23 passing

### Should-Have (Important):
- [ ] No test warnings
- [ ] Test execution time <2 minutes
- [ ] Clear error messages for edge cases

### Nice-to-Have (Optional):
- [ ] Parallel test execution
- [ ] Test fixtures refactored
- [ ] Test data generation scripts

---

## Regression Prevention

### Schema Sync Strategy
1. **Single Source of Truth**: PostgreSQL schema is authoritative
2. **Automated Sync**: Run sync script in CI/CD before tests
3. **Schema Tests**: Add test to verify SQLite matches PostgreSQL

**Test Template**:
```python
def test_sqlite_schema_matches_postgres():
    """Verify SQLite ohlcv_data schema matches PostgreSQL"""
    sqlite_cols = get_sqlite_columns('ohlcv_data')
    postgres_cols = get_postgres_columns('ohlcv_data')

    missing_cols = set(postgres_cols) - set(sqlite_cols)
    assert not missing_cols, f"SQLite missing columns: {missing_cols}"
```

### Type Checking Strategy
1. **Accept numpy types**: Use `isinstance(value, (bool, np.bool_))`
2. **Explicit conversion**: Convert numpy types to Python types when needed
3. **Type hints**: Add type hints to clarify expected types

---

## Next Steps

### Immediate (Today):
1. ✅ Create this analysis document
2. Run schema sync script
3. Fix 3 failing tests
4. Verify 23/23 tests pass

### Short-Term (This Week):
1. Expand test coverage from 5.24% → 70%+
2. Add schema sync to CI/CD
3. Document test strategy

### Long-Term (Next Week):
1. Begin Phase 1 (MCP MVP development)
2. Maintain >70% coverage
3. Add integration tests

---

## Lessons Learned

### What Went Well:
- ✅ Majority of tests passing (87%)
- ✅ Clear error messages from pytest
- ✅ Modular test structure

### What Needs Improvement:
- ⚠️ Schema drift between PostgreSQL and SQLite
- ⚠️ Low test coverage (5.24%)
- ⚠️ Type checking too strict for numpy types

### Recommendations:
1. **Automated schema validation** in CI/CD
2. **Coverage gates** (fail build if <70%)
3. **Type flexibility** for numpy/pandas types

---

## Phase 0.1 Completion Summary

**Status**: ✅ **COMPLETE** - All 23 tests passing (100%)
**Completion Date**: 2025-10-30
**Execution Time**: ~2 hours

### Fixes Implemented

#### 1. SQLite Schema Sync (P0 - 4 hours estimated, 1 hour actual)
**Problem**: SQLite missing `rsi` column causing 27 LayeredScoringEngine SQL errors

**Solution**:
- Created `scripts/sync_sqlite_schema.py` (automated schema sync script)
- Added `rsi REAL` column to ohlcv_data table
- Backfilled 912,371 records from existing `rsi_14` column
- Verified LayeredScoringEngine SQL query now succeeds

**Files Modified**:
- `scripts/sync_sqlite_schema.py` (created, 196 lines)
- `data/spock_local.db` (schema updated + backfilled)

#### 2. numpy Type Assertions (P1 - 15 min estimated, 10 min actual)
**Problem**: Tests failing with `isinstance(np.bool_, bool)` and `isinstance(np.float64, float)` returning False

**Solution**:
- Line 239: Changed `isinstance(value, bool)` to `isinstance(value, (bool, np.bool_))`
- Line 311: Changed `isinstance(report.validation_passed, bool)` to `isinstance(report.validation_passed, (bool, np.bool_))`
- Line 312: Changed `isinstance(report.consistency_score, float)` to `isinstance(report.consistency_score, (float, np.floating))`

**Files Modified**:
- `tests/backtesting/test_backtest_runner.py` (3 lines)

#### 3. Empty Tickers Edge Case (P2 - 20 min estimated, 45 min actual)
**Problem**: IndexError when processing empty tickers list (no trades scenario)

**Solution**:
- Added guard clause in `_calculate_return_metrics()` to return zero metrics
- Added guard clause in `_calculate_risk_metrics()` to return zero metrics
- Fixed `final_portfolio_value` property to return initial_capital when empty

**Files Modified**:
- `modules/backtesting/performance_analyzer.py` (2 guard clauses, 23 lines)
- `modules/backtesting/backtest_config.py` (1 guard clause, 3 lines)

### Test Results

**Before Fixes**:
- 20/23 passing (87%)
- 3 failures (test_metrics_match_dict, test_validate_consistency, test_empty_tickers)
- 27 LayeredScoringEngine SQL errors
- Coverage: 5.24%

**After Fixes**:
- 23/23 passing (100%) ✅
- 0 failures ✅
- 0 SQL errors ✅
- Coverage: 5.48% (target: 70% in Phase 0.2)

### Lessons Learned

**What Worked Well**:
- Systematic root cause analysis before implementing fixes
- Dry-run testing of schema sync script
- Comprehensive guard clauses for edge cases

**What Could Be Improved**:
- Initial schema sync could have detected missing columns earlier
- Test coverage expansion should happen alongside feature development

### Next Steps (Phase 0.2)

**Priority**: Expand test coverage from 5.48% to 70%+

**Target Modules** (in priority order):
1. `modules/backtesting/backtest_runner.py` (currently 41% → target 85%)
2. `modules/backtesting/data_providers/postgres_data_provider.py` (currently 0% → target 85%)
3. `modules/backtesting/performance_analyzer.py` (currently covered → target 90%)
4. `modules/factors/` (currently 0% → target 75%)

**Estimated Time**: 4-6 hours

---

**Report Status**: Final v2.0 ✅
**Phase 0.1 Status**: COMPLETE
**Sign-off**: Test fixes validated, all 23 tests passing
