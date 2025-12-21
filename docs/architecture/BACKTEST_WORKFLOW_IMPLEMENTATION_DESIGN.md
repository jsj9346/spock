# Backtest Workflow Optimization - Implementation Design

**Date**: 2025-11-01
**Based On**: [BACKTEST_WORKFLOW_ANALYSIS.md](file:///Users/13ruce/spock/docs/BACKTEST_WORKFLOW_ANALYSIS.md)
**Objective**: Prevent Claude Desktop from calling `query_ohlcv_data` before backtests
**Status**: 📐 **Design Phase**

---

## Executive Summary

### Problem
Claude Desktop calls `query_ohlcv_data` before `run_backtest`, causing:
- Context overflow (2.25MB wasted for 3-year backtests)
- Response interruption on long-term backtests
- 2x slower execution (unnecessary extra MCP call)

### Root Cause
`run_backtest` tool description doesn't explicitly state that:
1. Data loading is handled internally
2. `query_ohlcv_data` call is unnecessary
3. Response is compact and context-efficient

### Solution Approach
3-phase implementation with immediate, short-term, and optional improvements.

---

## Design Principles

### 1. Explicit Over Implicit
- Tool descriptions must explicitly state behavior
- Warnings about incorrect usage patterns
- Clear guidance on efficient workflows

### 2. User-Centric Communication
- Claude Desktop as primary user
- Clear instructions for LLM reasoning
- Human-readable for developers

### 3. Minimal Disruption
- No breaking changes to tool interface
- Backward compatible with existing users
- Optional documentation enhancements

### 4. Measurable Impact
- Track tool call sequences
- Measure context savings
- Verify behavior changes

---

## Solution 1: Tool Description Enhancement

### Priority: 🔴 **CRITICAL** (Immediate)

### Objective
Update `run_backtest` tool description to explicitly prevent `query_ohlcv_data` calls.

### Design Specification

#### Current Implementation
```python
# File: mcp_server/tools/backtest_tools.py
# Lines: 46-51

Tool(
    name="run_backtest",
    description=(
        "Run backtest for investment strategy with historical data. "
        "Supports momentum, value, and combined strategies. "
        "Returns performance metrics, trade statistics, and execution details. "
        "Uses vectorbt (fast) or custom engine (production accuracy)."
    ),
    ...
)
```

#### Proposed Implementation
```python
# File: mcp_server/tools/backtest_tools.py
# Lines: 46-51 (modify)

Tool(
    name="run_backtest",
    description=(
        "Run complete end-to-end backtest for investment strategy. "
        "\n\n"
        "⚠️ IMPORTANT: This is a self-contained tool. "
        "DO NOT call query_ohlcv_data before using this tool. "
        "All data loading, processing, and simulation are handled internally. "
        "\n\n"
        "What this tool does automatically: "
        "1. Loads historical OHLCV data for specified tickers and date range "
        "2. Applies strategy signals (momentum, value, or combined) "
        "3. Simulates portfolio performance with realistic transaction costs "
        "4. Calculates comprehensive performance metrics "
        "5. Returns ONLY compact results (performance + trades). "
        "\n\n"
        "Supports two engines: "
        "- vectorbt: 100x faster, ideal for research and optimization "
        "- custom: Production accuracy with event-driven simulation "
        "\n\n"
        "Response size: <1KB (efficient for multi-year backtests). "
        "No external data queries needed."
    ),
    ...
)
```

#### Key Design Elements

**1. Warning Section** ⚠️
- Positioned at the top for immediate visibility
- Explicit "DO NOT" instruction
- States self-contained nature

**2. Automated Steps Section**
- Numbered list of internal operations
- Shows data loading is step 1
- Emphasizes compact output (step 5)

**3. Technical Details Section**
- Engine options and characteristics
- Response size specification
- Efficiency claim for long-term backtests

**4. Final Reinforcement**
- "No external data queries needed"
- Closes the loop on the main message

### Implementation Details

**File Changes**:
```
mcp_server/tools/backtest_tools.py
├─ Line 47-51: Replace description string
└─ No other changes required
```

**Testing Strategy**:
1. Unit test: Tool description length validation
2. Integration test: MCP server tool listing
3. Manual test: Claude Desktop behavior with various prompts

**Rollback Plan**:
- Keep original description in git history
- Can revert in 1 commit if needed
- No data migration required

### Expected Impact

**Quantitative**:
- Context usage: 2.25MB → 500 bytes (99.98% reduction)
- MCP calls: 2 → 1 (50% reduction)
- Response time: ~5s → ~2s (60% improvement)

**Qualitative**:
- Eliminates response interruptions
- Enables 5+ year backtests
- Improves user confidence

---

## Solution 2: Usage Examples

### Priority: 🟡 **HIGH** (Short-term)

### Objective
Add concrete examples to guide Claude Desktop's tool usage.

### Design Specification

#### Proposed Implementation
```python
# File: mcp_server/tools/backtest_tools.py
# After inputSchema properties

inputSchema={
    "type": "object",
    "properties": {
        # ... existing properties ...
    },
    "required": ["strategy_type", "tickers", "start_date", "end_date"],

    # NEW: Add examples section
    "examples": [
        {
            "name": "efficient_longterm_backtest",
            "summary": "3-year value strategy backtest (context-efficient)",
            "description": (
                "Correct way to run long-term backtest. "
                "All data loading happens internally. "
                "Returns compact performance metrics only."
            ),
            "value": {
                "strategy_type": "value",
                "tickers": ["005930", "000660", "051910"],
                "start_date": "2021-01-01",
                "end_date": "2023-12-31",
                "region": "KR",
                "engine": "vectorbt",
                "initial_capital": 100000000,
                "risk_profile": "moderate"
            }
        },
        {
            "name": "momentum_strategy",
            "summary": "1-year momentum strategy with aggressive risk",
            "description": (
                "Fast backtest with momentum signals. "
                "No separate data query needed."
            ),
            "value": {
                "strategy_type": "momentum",
                "tickers": ["005930", "000660"],
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "region": "KR",
                "engine": "vectorbt",
                "risk_profile": "aggressive"
            }
        },
        {
            "name": "combined_strategy",
            "summary": "Combined momentum+value strategy",
            "description": (
                "Uses both momentum and value factors. "
                "Self-contained with internal data loading."
            ),
            "value": {
                "strategy_type": "momentum_value",
                "tickers": ["005930", "000660", "051910", "005380"],
                "start_date": "2022-01-01",
                "end_date": "2023-12-31",
                "region": "KR",
                "engine": "vectorbt"
            }
        }
    ]
}
```

#### Key Design Elements

**1. Example Structure**
- `name`: Machine-readable identifier
- `summary`: One-line human-readable description
- `description`: Emphasizes self-contained nature
- `value`: Complete, valid example payload

**2. Coverage**
- Example 1: Long-term (3 years) - addresses main use case
- Example 2: Short-term (1 year) - shows flexibility
- Example 3: Combined strategy - shows advanced usage

**3. Reinforcement**
- Each description mentions no external query needed
- Examples show complete parameter sets
- Valid, executable examples

### Implementation Details

**File Changes**:
```
mcp_server/tools/backtest_tools.py
├─ Line 132: Add examples after required fields
└─ Estimated: +60 lines
```

**Testing Strategy**:
1. JSON schema validation
2. Example execution tests
3. Claude Desktop prompt testing

**Compatibility**:
- MCP protocol supports examples (OpenAPI 3.0 format)
- Backward compatible (optional field)
- No breaking changes

---

## Solution 3: System Guidance Documentation

### Priority: 🟢 **MEDIUM** (Optional)

### Objective
Provide comprehensive user guidance for optimal MCP usage patterns.

### Design Specification

#### New File 1: MCP Server README Enhancement

```markdown
# File: mcp_server/README.md (new section)

## 🎯 Optimal Usage Patterns

### Backtesting Workflow

The `run_backtest` tool is designed as a complete end-to-end solution.

#### ✅ Correct Usage (Context-Efficient)

```
User Request:
"Run a 3-year backtest for Samsung (005930) and SK Hynix (000660)
 with value strategy from 2021 to 2023"

Expected Claude Behavior:
1. Call run_backtest with all parameters
2. Receive compact performance metrics (~500 bytes)
3. Present results to user

Context Usage: ~500 bytes
Response Time: ~2 seconds
```

#### ❌ Incorrect Usage (Context-Wasteful)

```
User Request:
"Run a 3-year backtest for Samsung and SK Hynix with value strategy"

Inefficient Claude Behavior:
1. Call query_ohlcv_data for 3 years of data
2. Receive 11,250 rows (~2.25MB)
3. Call run_backtest
4. Context overflow / Response interrupted

Context Usage: ~2.25MB (99% wasted)
Response Time: ~5 seconds + potential failure
```

#### Key Principle

> `run_backtest` is self-contained. Never call `query_ohlcv_data`
> before backtesting. All data loading happens internally.

### Why This Design?

1. **Context Efficiency**: Only metrics returned, not raw data
2. **Performance**: Single MCP call vs multiple calls
3. **Reliability**: No context overflow on long-term backtests
4. **Simplicity**: One tool does everything

### Technical Details

- Data loading: PostgreSQL with caching
- Response format: JSON (~500 bytes typical)
- Supports: 1 day to 10+ years
- Engine: vectorbt (fast) or custom (accurate)
```

#### New File 2: Comprehensive User Guide

```markdown
# File: docs/MCP_USER_GUIDE.md (new file)

# Spock MCP Server - User Guide

## Overview

This guide explains optimal usage patterns for the Spock MCP Server,
with focus on context efficiency and performance.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tool Usage Patterns](#tool-usage-patterns)
3. [Backtesting Best Practices](#backtesting-best-practices)
4. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Design Philosophy

The Spock MCP Server follows these principles:

1. **Self-Contained Tools**: Each tool handles its complete workflow
2. **Compact Responses**: Only essential data returned to Claude
3. **Internal Data Loading**: Raw data never leaves MCP server
4. **Context Efficiency**: Optimized for LLM token limits

### Data Flow

```
Claude Desktop
    ↓ (MCP call with parameters)
MCP Server
    ├─ Load data from PostgreSQL
    ├─ Process/analyze internally
    └─ Return compact metrics
    ↓ (500 bytes)
Claude Desktop
    └─ Present results to user
```

**Key Point**: Raw data (OHLCV) stays within MCP server boundaries.

## Tool Usage Patterns

### 1. run_backtest (Backtesting)

**Purpose**: Complete end-to-end strategy backtesting

**Self-Contained**: ✅ Yes
- Loads OHLCV data internally
- Runs strategy simulation
- Returns only performance metrics

**Usage**:
```json
{
  "strategy_type": "value",
  "tickers": ["005930", "000660"],
  "start_date": "2021-01-01",
  "end_date": "2023-12-31",
  "region": "KR",
  "engine": "vectorbt"
}
```

**Response** (~500 bytes):
```json
{
  "performance": { "total_return": 0.46, "sharpe_ratio": 2.34 },
  "trades": { "total_trades": 1, "win_rate": 1.0 }
}
```

**DO NOT** call `query_ohlcv_data` before this tool.

### 2. query_ohlcv_data (Data Query)

**Purpose**: Exploratory data analysis only

**Use Cases**:
- Manual data inspection
- Checking data availability
- Debugging data quality issues

**DO NOT Use For**:
- Backtesting preparation (use `run_backtest` directly)
- Strategy simulation (use `run_backtest` directly)

**Size Warning**: Can return up to 5000 rows (~1MB).
Use only when raw data inspection is truly needed.

### 3. screen_stocks (Stock Screening)

**Purpose**: Find stocks matching criteria

**Self-Contained**: ✅ Yes
- Loads fundamental data internally
- Applies filters
- Returns only ticker list + key metrics

**Usage**: Always safe to use directly.

## Backtesting Best Practices

### Do's ✅

1. **Use run_backtest directly**
   - All parameters in one call
   - No data pre-loading needed

2. **Specify complete date ranges**
   - start_date and end_date required
   - System handles data loading

3. **Choose appropriate engine**
   - vectorbt: For research and optimization (fast)
   - custom: For production accuracy (slower)

4. **Trust the compact response**
   - All essential metrics included
   - Raw data not needed for analysis

### Don'ts ❌

1. **Don't call query_ohlcv_data first**
   - Wastes context
   - Slows response
   - Risk of overflow

2. **Don't manually load data**
   - Tool handles it automatically
   - More efficient internally

3. **Don't worry about data size**
   - Tool manages memory internally
   - Response always compact

### Example Workflows

#### Workflow 1: Simple Backtest

```
User: "Backtest value strategy for Samsung 2020-2023"

Optimal:
└─ run_backtest(strategy=value, tickers=[005930],
                start=2020-01-01, end=2023-12-31)

Result: Fast, context-efficient response
```

#### Workflow 2: Multi-Year Comparison

```
User: "Compare momentum vs value for Samsung and SK Hynix, 2018-2023"

Optimal:
├─ run_backtest(strategy=momentum, tickers=[005930,000660],
│               start=2018-01-01, end=2023-12-31)
└─ run_backtest(strategy=value, tickers=[005930,000660],
                start=2018-01-01, end=2023-12-31)

Result: 2 compact responses, easy comparison
```

#### Workflow 3: Strategy Optimization

```
User: "Find best momentum parameters for Samsung 2022-2023"

Optimal:
├─ run_backtest(strategy=momentum, parameters={ma_short: 10, ma_long: 30})
├─ run_backtest(strategy=momentum, parameters={ma_short: 20, ma_long: 50})
└─ run_backtest(strategy=momentum, parameters={ma_short: 30, ma_long: 100})

Result: Multiple fast iterations
```

## Troubleshooting

### Issue 1: Response Interrupted on Long Backtest

**Symptoms**:
- Backtest request fails
- "Context limit exceeded" error
- Response cuts off mid-generation

**Likely Cause**:
Claude called `query_ohlcv_data` before `run_backtest`

**Solution**:
1. Verify tool description emphasizes self-contained nature
2. Use explicit instruction: "Run backtest directly without loading data first"
3. Check MCP server logs for tool call sequence

### Issue 2: Slow Backtest Response

**Symptoms**:
- Backtest takes >5 seconds
- Multiple MCP calls observed

**Likely Cause**:
- Multiple tool calls instead of single `run_backtest`
- Using custom engine instead of vectorbt

**Solution**:
1. Use vectorbt engine for faster results
2. Ensure single MCP call pattern
3. Check network latency to PostgreSQL

### Issue 3: Missing Data

**Symptoms**:
- Backtest returns "No data" error
- Empty result set

**Root Causes**:
- Ticker not in database
- Date range outside available data
- Region mismatch (KR vs US)

**Debugging**:
1. Use `list_available_tickers` to verify ticker exists
2. Check date range is reasonable (not future dates)
3. Verify region parameter matches ticker format

## Performance Benchmarks

### Context Usage

| Workflow | Context Used | Efficiency |
|----------|--------------|------------|
| run_backtest only | ~500 bytes | ✅ Optimal |
| query + run_backtest (1 year) | ~750KB | ⚠️ Wasteful |
| query + run_backtest (3 years) | ~2.25MB | ❌ Critical |

### Response Times

| Operation | vectorbt | custom | Notes |
|-----------|----------|--------|-------|
| 1-year backtest | ~1s | ~3s | 100 tickers |
| 3-year backtest | ~2s | ~8s | 100 tickers |
| 5-year backtest | ~3s | ~15s | 100 tickers |

## Advanced Topics

### Custom Strategy Parameters

Each strategy supports custom parameters:

**Momentum Strategy**:
```json
{
  "strategy_type": "momentum",
  "parameters": {
    "rsi_period": 14,
    "ma_short": 20,
    "ma_long": 50
  }
}
```

**Value Strategy**:
```json
{
  "strategy_type": "value",
  "parameters": {
    "pe_threshold": 15,
    "pb_threshold": 1.5,
    "dividend_yield_min": 0.02
  }
}
```

### Engine Selection Guide

**Use vectorbt when**:
- Research and exploration
- Parameter optimization
- Multiple iterations needed
- Speed is priority

**Use custom when**:
- Production backtesting
- Regulatory compliance needed
- Exact transaction simulation required
- Accuracy is priority

## Conclusion

The key to efficient Spock MCP Server usage:

> Use self-contained tools directly. Trust internal data loading.
> Never manually load data before backtesting.

Following these principles ensures:
- ✅ Fast responses
- ✅ Context efficiency
- ✅ Reliable long-term backtests
- ✅ Simple workflows

## Support

For issues or questions:
1. Check logs: `log/mcp_server.log`
2. Review tool descriptions in Claude Desktop
3. Verify MCP server is running
4. Consult [BACKTEST_WORKFLOW_ANALYSIS.md](file:///Users/13ruce/spock/docs/BACKTEST_WORKFLOW_ANALYSIS.md)
```

### Implementation Details

**File Changes**:
```
New Files:
├─ mcp_server/README.md (new section, ~50 lines)
└─ docs/MCP_USER_GUIDE.md (new file, ~400 lines)

Modified Files: None
```

**Effort Estimate**:
- Writing: 2 hours
- Review: 30 minutes
- Total: 2.5 hours

---

## Implementation Plan

### Phase 1: Critical (Immediate - Day 1)

**Goal**: Fix Claude Desktop's tool selection behavior

**Tasks**:
1. ✅ Update `run_backtest` tool description
2. ✅ Unit test: Tool description validation
3. ✅ Integration test: MCP server tool listing
4. ✅ Manual test: Claude Desktop behavior

**Deliverables**:
- Modified: `mcp_server/tools/backtest_tools.py` (1 file, ~20 lines)
- Test: 3 new test cases

**Effort**: 1 hour
**Owner**: Development Team
**Priority**: 🔴 CRITICAL

### Phase 2: High Priority (Short-term - Day 2-3)

**Goal**: Provide concrete usage examples

**Tasks**:
1. ✅ Add examples to inputSchema
2. ✅ Validate example JSON format
3. ✅ Test example execution
4. ✅ Update MCP server tests

**Deliverables**:
- Modified: `mcp_server/tools/backtest_tools.py` (1 file, ~60 lines)
- Test: 3 example execution tests

**Effort**: 2 hours
**Owner**: Development Team
**Priority**: 🟡 HIGH

### Phase 3: Medium Priority (Optional - Week 2)

**Goal**: Comprehensive documentation

**Tasks**:
1. ✅ Write MCP Server README section
2. ✅ Create MCP User Guide
3. ✅ Add troubleshooting section
4. ✅ Review and publish

**Deliverables**:
- New: `mcp_server/README.md` section (~50 lines)
- New: `docs/MCP_USER_GUIDE.md` (~400 lines)

**Effort**: 3 hours
**Owner**: Documentation Team
**Priority**: 🟢 MEDIUM

### Phase 4: Monitoring (Optional - Week 3+)

**Goal**: Track effectiveness and iterate

**Tasks**:
1. Add logging for tool call sequences
2. Monitor Claude Desktop behavior patterns
3. Analyze context usage before/after
4. Iterate on descriptions if needed

**Deliverables**:
- Modified: `mcp_server/adapters/backtest_adapter.py` (logging)
- Report: Monthly usage analysis

**Effort**: 4 hours initial + 1 hour/month
**Owner**: DevOps Team
**Priority**: 🔵 LOW

---

## Success Criteria

### Quantitative Metrics

| Metric | Before | Target After | Measurement Method |
|--------|--------|--------------|-------------------|
| Context Usage (3-year backtest) | 2.25MB | <1KB | Log analysis |
| MCP Calls per Backtest | 2 | 1 | Server logs |
| Response Time | ~5s | ~2s | Server metrics |
| Response Interruptions | >10%\* | 0% | Error logs |

\* Estimated based on user reports

### Qualitative Metrics

- ✅ Claude Desktop stops calling `query_ohlcv_data` before backtests
- ✅ Users can backtest 5+ years without interruption
- ✅ No user confusion about correct workflow
- ✅ Positive feedback on response reliability

### Testing Plan

**Phase 1 Testing**:
1. Unit test: Tool description length < 1000 chars
2. Schema test: Tool definition validates
3. Manual test: 5 backtest prompts with various phrasings
   - "Run 3-year backtest for Samsung"
   - "Backtest value strategy 2020-2023"
   - "Compare momentum vs value for SK Hynix"
   - "Analyze Samsung performance 2018-2023"
   - "Test combined strategy on 10 tickers"
4. Verify: Claude calls `run_backtest` directly (no `query_ohlcv_data`)

**Phase 2 Testing**:
1. Example validation: All examples execute successfully
2. Schema validation: Examples conform to inputSchema
3. Manual test: Claude references examples in tool selection

**Phase 3 Testing**:
1. Documentation review: Technical accuracy
2. User feedback: Clarity and completeness
3. Link validation: All file references work

---

## Risk Analysis

### Risk 1: Claude Still Calls query_ohlcv_data

**Probability**: Low (20%)
**Impact**: High
**Mitigation**:
- Make description even more explicit
- Add examples showing direct usage
- Consider MCP protocol-level constraints (if available)

### Risk 2: Description Too Long for MCP Protocol

**Probability**: Very Low (5%)
**Impact**: Medium
**Mitigation**:
- Test with actual MCP server
- Keep under 1000 characters
- Use examples instead if needed

### Risk 3: Breaking Changes for Existing Users

**Probability**: Very Low (5%)
**Impact**: Low
**Mitigation**:
- No interface changes, only description
- Backward compatible
- Existing code continues to work

---

## Rollback Plan

### If Phase 1 Fails
1. Revert `mcp_server/tools/backtest_tools.py` to previous version
2. Restart MCP server
3. Analyze Claude Desktop behavior logs
4. Redesign description with feedback

### If Phase 2 Fails
1. Remove examples from inputSchema
2. Fall back to Phase 1 only
3. No impact on core functionality

### If Phase 3 Fails
1. Documentation is optional
2. No code changes involved
3. Can update incrementally

---

## Future Enhancements

### Enhancement 1: Tool Chaining Prevention

**Idea**: MCP protocol-level prevention of `query_ohlcv_data` → `run_backtest` chain

**Feasibility**: Requires MCP protocol support
**Priority**: Research (if description approach insufficient)

### Enhancement 2: Usage Analytics

**Idea**: Dashboard showing tool call patterns, context usage, success rates

**Feasibility**: High (using existing logs)
**Priority**: Post-launch monitoring

### Enhancement 3: Auto-Detection of Inefficient Patterns

**Idea**: Warn user if Claude attempts to call `query_ohlcv_data` before backtest

**Feasibility**: Medium (requires MCP server hooks)
**Priority**: Future optimization

---

## Conclusion

This design provides a pragmatic, phased approach to solving the context efficiency problem:

1. **Immediate**: Fix tool description (1 hour, high impact)
2. **Short-term**: Add examples (2 hours, medium impact)
3. **Optional**: Documentation (3 hours, low impact but good practice)

**Total Effort**: 6 hours
**Expected Impact**: 99.98% context reduction, 60% faster responses, 100% reliability

**Recommendation**: Implement Phase 1 immediately, evaluate results, then proceed with Phase 2/3 based on effectiveness.

---

**Design Author**: Claude Code SuperClaude
**Review Required**: Development Team Lead
**Approval Required**: Product Owner
**Target Start Date**: 2025-11-01 (Immediate)
**Target Completion**: 2025-11-02 (Phase 1+2), 2025-11-08 (Phase 3)
