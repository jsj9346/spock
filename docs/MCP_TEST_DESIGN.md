# MCP Server Test Design Specification

**Version**: 1.0.0
**Date**: 2025-10-31
**Status**: Design Complete, Ready for Execution
**Author**: Spock Quant Platform Team

---

## 📋 Executive Summary

Comprehensive test specification for Spock MCP Server integration testing. This document defines test objectives, success criteria, validation checklists, and execution procedures for all 5 MCP tools.

**Test Scope**: Functional validation of MCP tools with real PostgreSQL database
**Out of Scope**: Performance benchmarking, stress testing, concurrent access (Phase 2)

---

## 🎯 Test Objectives

### Primary Objectives
1. **Functional Correctness**: Verify all 5 MCP tools execute without errors
2. **Data Integration**: Validate successful PostgreSQL database access
3. **Data Quality**: Ensure data freshness and completeness

### Secondary Objectives
4. **Error Handling**: Validate graceful error handling and meaningful error messages
5. **Consistency**: Verify cross-tool data consistency
6. **Documentation**: Collect evidence for production readiness assessment

---

## 🔧 Test Environment

### Prerequisites

#### Database Requirements
- PostgreSQL 15+ running on localhost:5432
- TimescaleDB extension enabled
- Database: `quant_platform`
- Minimum 1 KR ticker with OHLCV data
- Data range: ≥90 days for meaningful backtest

#### MCP Server Requirements
- MCP server running and connected to Claude Code
- All 5 tools registered: `query_ohlcv_data`, `run_backtest`, `list_available_tickers`, `get_system_status`, `optimize_strategy`
- Database credentials configured in `.env`
- Connection pool: 10-30 connections available

#### Test Data Requirements
**Recommended Test Tickers**:
- KR: `005930` (Samsung), `000660` (SK Hynix), `035720` (Kakao)
- Date Range: 2024-01-01 to latest
- Minimum: 60 trading days for momentum backtest

### Performance Expectations
| Operation | Expected Duration | Timeout |
|-----------|-------------------|---------|
| system_status | <1s | 5s |
| list_tickers | <1s | 5s |
| query_ohlcv (single) | <2s | 10s |
| query_ohlcv (batch 5) | <5s | 20s |
| backtest (90 days, 3 tickers) | <30s | 60s |
| optimization (simple grid) | <60s | 120s |

---

## ✅ Success Criteria

### Test 1: System Status

**Success Criteria** ✅:
- `status` = "healthy"
- `data_fresh` = true
- `total_tickers` > 0
- `latest_date` within 3 days of current date
- All required fields present: `database`, `data`, `timestamp`

**Warning Criteria** ⚠️:
- `status` = "stale_data"
- `latest_date` 3-7 days old
- `total_tickers` < expected (KR<50)

**Failure Criteria** ❌:
- Database connection failed
- `total_tickers` = 0
- `latest_date` > 7 days old
- Missing critical fields

---

### Test 2: List Available Tickers

**Success Criteria** ✅:
- `count` > 0 for both KR and US regions
- Each ticker contains required fields: `ticker`, `region`, `name`
- Ticker format validation: KR (6-digit), US (1-5 alpha)
- No duplicate tickers within same region

**Warning Criteria** ⚠️:
- `count` < expected (KR<50 or US<100)
- `sector` field missing for some tickers

**Failure Criteria** ❌:
- `count` = 0
- Required fields missing
- Invalid ticker format

---

### Test 3: OHLCV Query - Single Ticker

**Success Criteria** ✅:
- Data returned for requested ticker
- Date range matches request
- All OHLCV values valid: open, high, low, close > 0, volume ≥ 0
- Price sanity: high ≥ low, close between high and low
- No missing dates (max gap: 5 business days)

**Warning Criteria** ⚠️:
- Missing dates in range (gaps 3-5 business days)
- Volume = 0 for some dates
- Price changes > ±30% in single day

**Failure Criteria** ❌:
- No data returned
- Invalid ticker
- Date format error
- OHLCV values <= 0 (except volume)
- Price sanity violations

---

### Test 4: OHLCV Query - Batch Tickers

**Success Criteria** ✅:
- All requested tickers return data
- Consistent date ranges across tickers
- No duplicate (ticker, date, region) combinations
- Data completeness ≥ 90% for each ticker

**Warning Criteria** ⚠️:
- Partial data (1-2 tickers missing)
- Inconsistent date ranges (±5 days difference)
- Data completeness 70-90%

**Failure Criteria** ❌:
- No data for any ticker
- Query timeout
- Data completeness < 70%
- Multiple duplicates detected

---

### Test 5: Backtest Execution

**Success Criteria** ✅:
- `trades` > 0
- All metrics calculated: `sharpe_ratio`, `max_drawdown`, `total_return`, `win_rate`
- Metrics in realistic ranges:
  - Sharpe ratio: -2 to +5
  - Max drawdown: 0 to -50%
  - Total return: -50% to +200%
  - Win rate: 20% to 80%
- Execution time < 30s

**Warning Criteria** ⚠️:
- `trades` < 10 (insufficient statistical significance)
- Extreme metrics: Sharpe > 5 or < -2
- Max drawdown > -50%
- Execution time 30-60s

**Failure Criteria** ❌:
- `trades` = 0
- Error in calculation
- Unrealistic returns (> ±1000%)
- Missing required metrics
- Timeout (> 60s)

---

### Test 6: Strategy Optimization

**Success Criteria** ✅:
- `best_params` found
- In-sample vs out-of-sample gap < 50%
- Convergence achieved
- Optimization results stable (repeat test shows similar params)
- Execution time < 60s

**Warning Criteria** ⚠️:
- Overfitting detected: in-sample vs out-of-sample gap 50-100%
- `best_params` at boundary values
- Execution time 60-120s

**Failure Criteria** ❌:
- Optimization failed
- No convergence
- Gap > 100% (severe overfitting)
- Timeout (> 120s)
- Best params identical to initial params (no optimization occurred)

---

## 📝 Validation Checklists

### Data Freshness Checks
- [ ] `latest_date` within 3 days → **HEALTHY**
- [ ] `latest_date` 3-7 days → **WARNING**
- [ ] `latest_date` > 7 days → **STALE**
- [ ] `days_since_update` calculated correctly

### Data Completeness Checks
- [ ] All required fields present (ticker, region, date, OHLCV)
- [ ] No null values in critical fields
- [ ] Date ranges complete (max gap: 5 business days)
- [ ] OHLCV values within realistic bounds

### Data Consistency Checks
- [ ] Region consistency: KR tickers 6-digit, US tickers alpha
- [ ] Cross-tool consistency: `system_status` ticker count = `list_tickers` count
- [ ] Price sanity: high ≥ low, close between high/low, volume ≥ 0
- [ ] No duplicate (ticker, date, region) combinations

### Data Quality Checks
- [ ] No extreme price changes (>±50% in single day) without explanation
- [ ] Volume > 0 for at least 80% of dates
- [ ] Backtest metrics in realistic ranges
- [ ] No data corruption indicators (e.g., all zeros, repeated values)

---

## 🔄 Test Execution Flow

### Phase 1: Prerequisites Check
**Duration**: 1-2 minutes

```yaml
Steps:
  1. Verify PostgreSQL connection
  2. Verify TimescaleDB extension
  3. Verify quant_platform database exists
  4. Check MCP server connection
  5. Verify minimum data requirements (1+ ticker, 90+ days)

Exit Criteria:
  - STOP if database connection fails
  - STOP if MCP server not connected
  - STOP if no data available
```

---

### Phase 2: Basic Functionality Tests
**Duration**: 2-3 minutes
**Can Continue with Warnings**: Yes

#### Test 1: System Status + Data Freshness
```yaml
Tool: get_system_status
Input: None
Expected Output:
  - status: "healthy" or "stale_data"
  - database.connected: true
  - data.total_tickers: >0
  - data.latest_date: ISO date string
  - data.data_fresh: boolean

Validation:
  - Run Data Freshness Checks
  - Run Consistency Check (compare with Test 2 results)
```

#### Test 2: List Available Tickers
```yaml
Tool: list_available_tickers
Input:
  - region: "KR", limit: 10
  - region: "US", limit: 10
Expected Output:
  - success: true
  - tickers: array of objects
  - count: integer

Validation:
  - Run Completeness Checks
  - Run Consistency Check (ticker format)
```

---

### Phase 3: Data Access Tests
**Duration**: 5-10 minutes
**Can Continue with Warnings**: No - STOP if no data

#### Test 3: OHLCV Single Ticker Query
```yaml
Tool: query_ohlcv_data
Input:
  - tickers: ["005930"]
  - start_date: "2024-09-01"
  - end_date: "2024-09-30"
  - region: "KR"
  - timeframe: "1d"
Expected Output:
  - success: true
  - data: dictionary with ticker key
  - record_count: integer

Validation:
  - Run Completeness Checks
  - Run Quality Checks
  - Check date range completeness
  - Validate OHLCV values
```

#### Test 4: OHLCV Batch Ticker Query
```yaml
Tool: query_ohlcv_data
Input:
  - tickers: ["005930", "000660", "035720"]
  - start_date: "2024-08-01"
  - end_date: "2024-09-30"
  - region: "KR"
  - timeframe: "1d"
Expected Output:
  - success: true
  - data: dictionary with 3 ticker keys
  - record_count: >150 (3 tickers × ~60 days)

Validation:
  - Run Consistency Checks
  - Validate cross-ticker date alignment
  - Check for duplicates
```

---

### Phase 4: Advanced Feature Tests
**Duration**: 5-10 minutes
**Can Continue with Warnings**: Yes

#### Test 5: Backtest Execution
```yaml
Tool: run_backtest
Input:
  - strategy_type: "momentum"
  - tickers: ["005930", "000660", "035720"]
  - start_date: "2024-01-01"
  - end_date: "2024-09-30"
  - region: "KR"
  - engine: "vectorbt"
Expected Output:
  - success: true
  - metrics: object with sharpe_ratio, max_drawdown, etc.
  - trades: integer

Validation:
  - Check metrics in realistic ranges
  - Validate trade count > 0
  - Verify execution time < 30s
```

#### Test 6: Strategy Optimization
```yaml
Tool: optimize_strategy
Input:
  - strategy_type: "momentum"
  - tickers: ["005930", "000660"]
  - start_date: "2024-01-01"
  - end_date: "2024-06-30"
  - region: "KR"
Expected Output:
  - success: true
  - best_params: object
  - in_sample_sharpe: number
  - out_of_sample_sharpe: number

Validation:
  - Check overfitting (gap < 50%)
  - Verify convergence
  - Validate params not at boundaries
```

---

### Phase 5: Report Generation
**Duration**: 5 minutes

```yaml
Collect:
  - All test results (pass/warn/fail)
  - All validation check results
  - All error messages and warnings
  - Performance metrics
  - Issues discovered

Output:
  - Comprehensive test report
  - Issue tracking table
  - Recommendations for production readiness
```

---

## ⚠️ Error Handling Strategy

### Connection Errors
- **Retry Policy**: Retry once after 2-second delay
- **On Failure**: STOP test, capture diagnostic info (host, port, credentials check)
- **Logging**: Full error context including stack trace

### Query Timeouts
- **Action**: Log partial results if available
- **Classification**: Mark as WARNING
- **Continue**: Yes, but note in final report

### Data Validation Failures
- **Action**: Continue test, collect all validation issues
- **Classification**: Depends on severity (see success criteria)
- **Logging**: List all failed validation checks

### Tool Execution Errors
- **Action**: STOP current test phase
- **Classification**: FAIL
- **Logging**: Capture full error context, input parameters, partial results
- **Continue**: Proceed to next phase if possible

---

## 📊 Test Report Template

```markdown
# MCP Server Test Report

**Date**: YYYY-MM-DD
**Tester**: [Name]
**Test Duration**: XX minutes
**Overall Status**: PASS / WARN / FAIL

## Summary
- Tests Passed: X/6
- Tests with Warnings: X/6
- Tests Failed: X/6
- Data Freshness: HEALTHY / STALE
- Production Ready: YES / NO (with conditions) / NO

## Test Results

### Test 1: System Status
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **Data Fresh**: Yes / No
- **Total Tickers**: XXX
- **Latest Date**: YYYY-MM-DD
- **Issues**: [List any issues]

### Test 2: List Tickers
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **KR Count**: XXX
- **US Count**: XXX
- **Issues**: [List any issues]

### Test 3: OHLCV Single
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **Record Count**: XXX
- **Date Completeness**: XX%
- **Issues**: [List any issues]

### Test 4: OHLCV Batch
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **Tickers Returned**: X/X
- **Data Completeness**: XX%
- **Issues**: [List any issues]

### Test 5: Backtest
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **Trades**: XXX
- **Sharpe Ratio**: X.XX
- **Max Drawdown**: -XX%
- **Execution Time**: XXs
- **Issues**: [List any issues]

### Test 6: Optimization
- **Status**: ✅ PASS / ⚠️ WARN / ❌ FAIL
- **Best Params**: {...}
- **In-Sample Sharpe**: X.XX
- **Out-of-Sample Sharpe**: X.XX
- **Gap**: XX%
- **Issues**: [List any issues]

## Issues Discovered

| ID | Severity | Component | Description | Status |
|----|----------|-----------|-------------|--------|
| 1 | Critical | system_adapter | Method name mismatch | FIXED |
| 2 | High | ... | ... | ... |

## Validation Checklist Results

### Data Freshness: ✅ / ⚠️ / ❌
- [✅] latest_date within 3 days
- [✅] days_since_update calculated correctly

### Data Completeness: ✅ / ⚠️ / ❌
- [✅] All required fields present
- [✅] No null values
- [⚠️] Date ranges 95% complete

### Data Consistency: ✅ / ⚠️ / ❌
- [✅] Region consistency validated
- [✅] Cross-tool consistency verified
- [✅] Price sanity checks passed

### Data Quality: ✅ / ⚠️ / ❌
- [✅] No extreme anomalies
- [✅] Volume > 0 for 85% of dates
- [✅] Backtest metrics realistic

## Recommendations

1. **Production Readiness**: [READY / NOT READY]
2. **Required Actions**: [List must-fix issues]
3. **Suggested Improvements**: [List nice-to-have improvements]
4. **Next Steps**: [Phase 2 testing, performance benchmarks, etc.]

## Appendix

### Test Environment
- PostgreSQL Version: 15.X
- TimescaleDB Version: 2.11.X
- Database Size: XXX MB
- Total Tickers: XXX
- Date Range: YYYY-MM-DD to YYYY-MM-DD

### Performance Metrics
| Test | Duration | Expected | Status |
|------|----------|----------|--------|
| system_status | XXXms | <1s | ✅ |
| list_tickers | XXXms | <1s | ✅ |
| ... | ... | ... | ... |
```

---

## 🚀 Next Steps After Testing

### If All Tests Pass ✅
1. Document successful test run
2. Proceed to Phase 2: Performance benchmarking
3. Begin integration with production workflows
4. Schedule regular regression testing

### If Tests Pass with Warnings ⚠️
1. Document warnings and root causes
2. Assess impact on production usage
3. Create tickets for non-critical issues
4. Proceed with caution, monitor closely

### If Tests Fail ❌
1. Document failures with full context
2. Create high-priority fix tickets
3. Repeat prerequisite checks
4. DO NOT proceed to production
5. Schedule fix verification testing

---

## 📚 References

- [MCP Server Implementation](../mcp_server/server.py)
- [System Adapter](../mcp_server/adapters/system_adapter.py)
- [Data Adapter](../mcp_server/adapters/data_adapter.py)
- [Backtest Adapter](../mcp_server/adapters/backtest_adapter.py)
- [MCP User Guide](MCP_USER_GUIDE.md)
- [QUANT_ROADMAP.md](QUANT_ROADMAP.md)

---

**Document Status**: ✅ Design Complete
**Ready for Execution**: Yes
**Estimated Test Duration**: 20-30 minutes (including report)
**Next Action**: Execute Phase 1 - Prerequisites Check
