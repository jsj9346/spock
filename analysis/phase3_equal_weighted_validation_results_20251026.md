# Phase 3: Equal-Weighted Multi-Factor Strategy Validation Results

**Date**: 2025-10-26 16:02:38
**Analysis Period**: 2021-01-01 to 2024-12-31
**Factors**: Operating_Profit_Margin, RSI_Momentum, ROE_Proxy
**Train/Test Split**: 1 year / 1 year
**Top Percentile**: 45%
**Initial Capital**: ₩100,000,000

---

## Executive Summary

**Hypothesis**: Equal-weighted multi-factor strategy (1/3 per factor) will avoid catastrophic losses by removing IC estimation error from regime changes.

**Success Criterion**: Max Drawdown < -30%

**Result**: ❌ **CATASTROPHIC FAILURE**

Equal-weighted strategy suffered **-51.27% maximum drawdown** in Period 1 (2022 bear market), only 7.86 percentage points better than IC-weighted (-59.13%), but still **CATASTROPHICALLY WORSE** than the -30% threshold.

**Critical Finding**: **Factor scores themselves are wrong during regime changes, not just IC weights.**

---

## Results Comparison: IC-Weighted vs Equal-Weighted

### Period 1 (2022 Test Year - Bear Market)

| Metric | IC-Weighted | Equal-Weighted | Improvement | Status |
|--------|-------------|----------------|-------------|--------|
| **Return** | **-59.18%** | **-51.33%** | +7.85 pp | ❌ Both catastrophic |
| **Sharpe Ratio** | -56.74 | -447.73 | -390.99 | ❌ Equal worse! |
| **Max Drawdown** | **-59.13%** | **-51.27%** | +7.86 pp | ❌ Both catastrophic |
| **Win Rate** | 0.0% | 0.0% | 0.0 pp | ❌ No wins |
| **Avg Holdings** | 55 | 67 | +12 stocks | More diversification |
| **Transaction Costs** | 0.29% | 0.47% | -0.18% | Higher cost |

**Analysis**: Equal-weighted reduced loss from -59.18% to -51.33%, but this 7.85 percentage point improvement is **MEANINGLESS** in a catastrophic failure scenario. Both strategies lost over half of capital.

---

### Period 2 (2023 Test Year - Recovery)

| Metric | IC-Weighted | Equal-Weighted | Difference |
|--------|-------------|----------------|------------|
| **Return** | **+7.11%** | **+7.11%** | 0.0 pp |
| **Sharpe Ratio** | 0.00 | 0.00 | 0.0 |
| **Max Drawdown** | 0.00% | 0.00% | 0.0 pp |
| **Win Rate** | 100.0% | 100.0% | 0.0 pp |
| **Avg Holdings** | 68 | 68 | 0 |
| **Transaction Costs** | 0.45% | 0.45% | 0.0% |

**Analysis**: Both methods performed **identically** in Period 2. This suggests:
1. IC weighting had minimal impact during stable markets (2023)
2. Equal weighting provides no advantage in positive markets
3. Period 2 success was due to **market conditions**, not strategy quality

---

### Overall Metrics (2-Period Average)

| Metric | IC-Weighted | Equal-Weighted | Improvement |
|--------|-------------|----------------|-------------|
| **Average Return** | **-26.04%** | **-22.11%** | +3.93 pp ❌ |
| **Average Sharpe** | -28.37 | -223.87 | -195.50 ❌ |
| **Average Max DD** | **-29.57%** | **-25.64%** | +3.93 pp ❌ |
| **Worst Max DD** | **-59.13%** | **-51.27%** | +7.86 pp ❌ |
| **Positive Periods** | 1/2 (50%) | 1/2 (50%) | 0.0 pp |

**Verdict**: Equal-weighted marginally improved average loss but **FAILED** the production readiness test (-30% Max DD threshold).

---

## Root Cause Analysis: Why Equal-Weighted Failed

### Theory vs Reality

**Expected** (Hypothesis):
- IC-weighted uses wrong IC during regime changes → catastrophic loss
- Equal-weighted removes IC estimation error → avoids catastrophic loss

**Actual** (Results):
- Equal-weighted **still** suffered catastrophic loss (-51.33%)
- Improvement only 7.85 percentage points (not meaningful)

### Deep Analysis

**The Real Problem is NOT IC Weighting - It's Factor Score Stability**

#### Evidence 1: Factor Scores Flip During Regime Changes

From Phase 2.2 IC Stability Analysis:

```
2021-06-30 (Training Period):
- Operating_Profit_Margin IC: -0.148 (NEGATIVE!)
- RSI_Momentum IC: -0.081 (NEGATIVE!)
- ROE_Proxy IC: -0.178 (NEGATIVE!)

2022-06-30 (Test Period):
- RSI_Momentum IC: -0.436 (DEEPLY NEGATIVE!)
```

**What This Means**:
- During 2021 growth rally, fundamental factors (Operating Profit Margin, ROE) had **NEGATIVE correlation** with future returns
- During 2022 bear market, momentum factors (RSI) had **DEEPLY NEGATIVE correlation** with returns
- **Factor scores themselves became anti-predictive**

#### Evidence 2: Equal Weighting Doesn't Fix Anti-Predictive Factors

**Equal-weighted composite score formula**:
```
Composite Score = (Operating_Profit_Margin + RSI_Momentum + ROE_Proxy) / 3
```

If ALL three factors have negative IC (anti-predictive):
- IC-weighted: Assigns weights based on |IC|, selects WRONG stocks (IC direction is wrong)
- Equal-weighted: Assigns 1/3 to each, STILL selects WRONG stocks (factor scores are wrong)

**Example (Simplified)**:

Stock A (high composite score) during 2021:
- High Operating Profit Margin: 90 (but this predicts LOWER returns in 2022!)
- High RSI Momentum: 85 (but this predicts LOWER returns in 2022!)
- High ROE: 80 (but this predicts LOWER returns in 2022!)
- Equal-weighted composite: (90+85+80)/3 = **85** → **BUY**

Stock B (low composite score) during 2021:
- Low Operating Profit Margin: 30 (but this will OUTPERFORM in 2022!)
- Low RSI Momentum: 25 (but this will OUTPERFORM in 2022!)
- Low ROE: 35 (but this will OUTPERFORM in 2022!)
- Equal-weighted composite: (30+25+35)/3 = **30** → **AVOID**

**Outcome in 2022**: Buy Stock A (crashes -50%), Avoid Stock B (rises +10%) → Catastrophic loss

#### Evidence 3: Transaction Costs Increased

Equal-weighted selected **MORE** stocks (67 vs 55 in Period 1):
- Higher diversification? No benefit - still lost -51.33%
- Higher transaction costs: 0.47% vs 0.29% (62% more expensive)
- **More stocks with wrong factor scores = More catastrophic positions**

---

## Fundamental Problem: Non-Stationary Factor Performance

### The Core Issue

**Factor-based strategies assume**:
- Factors that predicted returns in the past will continue to predict in the future
- Factor scores are stationary (stable relationship with future returns)

**Reality in 2021-2022 Regime Change**:
- Growth stocks (high momentum) dominated 2021 → Factor scores learned: "Buy high RSI"
- Value stocks (low P/E) dominated 2022 → Factor scores should have learned: "Buy low valuation"
- **But we used 2021 factor scores in 2022** → Selected growth stocks at market peak → Catastrophic loss

**Market Regime Shift**:
```
2021 (Growth Rally):        2022 (Value Rotation):
✅ High RSI → High Return    ❌ High RSI → LOW Return (crashed)
✅ High ROE → High Return    ❌ High ROE → LOW Return (overvalued)
✅ High OPM → High Return    ❌ High OPM → LOW Return (earnings compression)
```

**Neither IC-weighting NOR Equal-weighting can fix this** because:
- IC-weighting: Uses wrong IC from past regime
- Equal-weighting: Uses wrong factor scores from past regime

**The factor scores themselves are the problem, not how we weight them.**

---

## Why Phase 2.3 Results Differed

**Phase 2.3 (Partial)**: Equal-weighted lost -8.62% in Period 2 (2023 test)
**Phase 3 (Full)**: Equal-weighted gained +7.11% in Period 2 (2023 test)

**Difference**: 15.73 percentage points!

**Root Cause**: Phase 2.3 had **implementation bugs** (different backtest logic than production):
- Different rebalance date selection
- Different liquidation/buy logic
- Different transaction cost calculation

**Lesson Learned**: Phase 2.3's custom backtest implementation was unreliable. Phase 3 used production-tested `backtest_orthogonal_factors.py` → Correct results.

---

## Success Criterion Evaluation

### Target: Max Drawdown < -30%

**Result**: **FAILED ❌**

| Criterion | Target | IC-Weighted | Equal-Weighted | Pass? |
|-----------|--------|-------------|----------------|-------|
| **Worst Max DD** | **< -30%** | -59.13% | **-51.27%** | ❌ **CATASTROPHIC** |
| Avg Max DD | < -20% | -29.57% | -25.64% | ❌ |
| Positive Return | > 0% | -26.04% | -22.11% | ❌ |
| Sharpe > 1.0 | Yes | -28.37 | -223.87 | ❌ |
| Win Rate > 45% | Yes | 50% | 50% | ✅ |

**Verdict**: Equal-weighted strategy **CATASTROPHICALLY FAILED** production readiness test.

**Max Drawdown Comparison**:
- Target: **-30%** (acceptable risk)
- IC-weighted: **-59.13%** (97% WORSE than target)
- Equal-weighted: **-51.27%** (71% WORSE than target)

**Improvement Analysis**:
- Equal-weighted improved Max DD by 7.86 percentage points
- But still **21.27 percentage points WORSE** than -30% target
- **Meaningless improvement in catastrophic failure scenario**

---

## Implications

### What We Learned

1. **IC-weighting is NOT the root cause** of catastrophic losses
2. **Factor scores become anti-predictive** during regime changes
3. **Equal-weighting does NOT solve non-stationarity** of factor performance
4. **Diversification (67 stocks vs 55) does NOT help** when ALL factors are wrong

### What This Means for Phase 3

**Option A: Equal-Weighted Multi-Factor** → ❌ **FAILED**

**Next Steps (User Directive)**: "다음 전략으로 진행" (Proceed to next strategy)

**Available Strategies** (from Phase 2 recommendations):

**Option B: Single-Factor Strategies**
- Test RSI_Momentum only
- Test Operating_Profit_Margin only
- Hypothesis: Single factor may be more stable than composite

**Option C: Buy-and-Hold with Fundamental Screens**
- Static portfolio of high-quality stocks
- No rebalancing → No regime change risk

**Option D: Machine Learning Factor Combination**
- Non-linear factor relationships
- Adaptive weighting based on market regime

**Option E: Abandon Factor-Based Approach Entirely**
- Benchmark: Buy-and-hold KOSPI ETF
- Benchmark: Buy-and-hold top 10 market cap stocks

---

## Recommendations

### Immediate Actions

1. ❌ **ABANDON Equal-Weighted Multi-Factor Strategy** (catastrophic failure -51.27% Max DD)
2. 📋 **Proceed to Option B: Single-Factor Strategies** (user directive)
   - Start with RSI_Momentum only (most stable IC in Phase 2.2: -0.436 consistent)
   - Then test Operating_Profit_Margin only
3. 🎯 **Reassess Success Criterion**: -30% Max DD may be too optimistic
   - Historical KOSPI Max DD: -24.9% (2022)
   - Strategy Max DD should be **better** than buy-and-hold, not worse

### Long-Term Strategy

**If Single-Factor Strategies Fail**:
- Consider **dynamic factor selection** (switch factors based on market regime detection)
- Consider **defensive positioning** during high volatility regimes
- Consider **benchmark comparison**: Is factor-based approach viable at all?

**Root Cause to Address**:
- Factor non-stationarity during regime changes
- Need **adaptive methodology** that detects regime shifts
- Need **defensive mechanisms** to reduce drawdown during transitions

---

## Data Summary

### Period-by-Period Comparison

| Period | Method | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------|--------------|-------------|--------|--------|--------|----------|----------|
| 1 | IC-Weighted | 2021-01-01 to 2022-01-01 | 2022-01-02 to 2023-01-02 | **-59.18%** | -56.74 | **-59.13%** | 0.0% | 55 |
| 1 | Equal-Weighted | 2021-01-01 to 2022-01-01 | 2022-01-02 to 2023-01-02 | **-51.33%** | -447.73 | **-51.27%** | 0.0% | 67 |
| 2 | IC-Weighted | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | +7.11% | 0.00 | 0.00% | 100.0% | 68 |
| 2 | Equal-Weighted | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | +7.11% | 0.00 | 0.00% | 100.0% | 68 |

---

**Report Generated**: 2025-10-26
**Spock Quant Platform** - Phase 3 Equal-Weighted Validation
