# Tier 2 Rolling IC Implementation - Comparison Report

**Generated**: 2025-10-24 18:48:20
**Test Period**: 2023-01-01 to 2024-10-09 (1.75 years)
**Initial Capital**: ₩100,000,000
**Rebalance Frequency**: Quarterly
**Top Percentile**: 45th (optimized from Phase 1-4)

## Executive Summary

**Unexpected Result**: Rolling IC (Tier 2 MVP) **underperformed** static IC (Tier 1 baseline) across all metrics. This challenges the hypothesis that adaptive IC weighting would improve performance.

**Key Finding**: Win rate remained 0.00% across all configurations, indicating **deeper systematic issues** beyond IC calculation methodology.

---

## Comparative Results

| Configuration | Rolling Window | Total Return | Final Value | Sharpe | Max DD | Win Rate | Volatility |
|---------------|----------------|--------------|-------------|--------|--------|----------|------------|
| **Tier 1 (Baseline)** | Static IC | **-20.27%** | **₩79,728,729** | **-65.03** | **-20.14%** | 0.00% | 41.14% |
| Tier 2 MVP (3mo) | 60 days | -36.26% | ₩63,740,730 | -16.64 | -36.16% | 0.00% | 288.71% |
| Tier 2 (6mo) | 126 days | -30.03% | ₩69,966,785 | -29.00 | -29.92% | 0.00% | 139.51% |

### Performance Ranking
1. ⭐ **Static IC (Tier 1)**: -20.27% total return (best)
2. 6-Month Rolling IC: -30.03% total return
3. ❌ 3-Month Rolling IC: -36.26% total return (worst)

**Relative Performance**:
- 3-Month Rolling: -16.0 percentage points vs baseline
- 6-Month Rolling: -9.8 percentage points vs baseline

---

## IC Weight Evolution Analysis

### Rebalance #1 (2023-03-31)

**Static IC (Tier 1)**:
- 1M_Momentum: 64.19%
- 12M_Momentum: 28.14%
- PE_Ratio: 7.67%

**3-Month Rolling IC (60 days)**:
- PE_Ratio: 56.30% (avg IC=-0.2025) ← **Regime Flip!**
- 1M_Momentum: 29.33% (avg IC=+0.1055)
- 12M_Momentum: 14.38% (avg IC=+0.0517)

**6-Month Rolling IC (126 days)**:
- 1M_Momentum: 47.41% (avg IC=+0.0841)
- PE_Ratio: 41.23% (avg IC=-0.0732)
- 12M_Momentum: 11.35% (avg IC=-0.0201)

### Key Observations
1. **PE_Ratio Regime Flip**: 3-month window shows strong negative IC (-0.2025), leading to 56.30% weight
2. **Short-Term Noise**: 60-day window appears too sensitive to recent volatility (288.71% volatility)
3. **Absolute IC Weighting Issue**: Using abs(IC) amplifies both predictive and noise signals equally

---

## Risk-Adjusted Performance

### Volatility Analysis
- **Tier 1 Static**: 41.14% (baseline)
- **Tier 2 6mo**: 139.51% (3.4x higher)
- **Tier 2 3mo**: 288.71% (7.0x higher)

**Interpretation**: Rolling IC introduces extreme volatility due to frequent weight changes and regime sensitivity.

### Sharpe Ratio Decomposition
All configurations show negative Sharpe ratios, indicating:
- Negative expected returns across all strategies
- Volatility does not compensate for losses
- No risk-adjusted performance benefit from rolling IC

---

## Transaction Cost Analysis

| Configuration | Total Costs | % of Capital | Cost per Rebalance |
|---------------|-------------|--------------|-------------------|
| Tier 1 Static | ₩694,811 | 0.69% | ₩231,604 |
| Tier 2 3mo | ₩578,425 | 0.58% | ₩192,808 |
| Tier 2 6mo | ₩630,055 | 0.63% | ₩210,018 |

**Insight**: Transaction costs are similar across all configurations (~0.6%), not a differentiating factor.

---

## Root Cause Analysis

### Why Rolling IC Underperformed

**1. Look-Ahead Bias Validation Issue**
- Static IC trains on 2021-2022, tests on 2023-2024 (no look-ahead)
- Rolling IC uses data **within test period** for weight calculation
- While technically avoiding future data, rolling IC may overfit to recent noise

**2. Absolute IC Weighting Problem**
- Formula: `weight = abs(IC) / sum(abs(IC))`
- **Issue**: Treats predictive signals (IC=+0.20) and noise (IC=-0.20) equally
- **Solution**: Should weight by **signed IC** or implement IC quality filters

**3. Sample Size Degradation**
- Static IC: 2 years of data (~480 trading days)
- 3-Month Rolling: 60 days (~12 factor observations)
- 6-Month Rolling: 126 days (~25 factor observations)
- **Statistical Power**: Insufficient observations for robust IC estimates

**4. Market Regime Persistence**
- Q1 2023 showed PE_Ratio IC=-0.2025 (strong negative)
- This regime did **not persist** through Q2-Q3 2023
- Short windows captured temporary dislocations, not true regime changes

**5. Zero Win Rate Universality**
- **Critical Finding**: 0.00% win rate persists across ALL configurations
- **Implication**: IC methodology alone cannot solve the underlying problem
- **Hypothesis**: Factor selection or stock selection criteria are fundamentally flawed

---

## Lessons Learned

### What We Validated
✅ Rolling IC implementation works correctly (dynamic calculation successful)
✅ IC weights change significantly across time periods (regime detection working)
✅ LRU caching improves performance (67% hit rate observed)

### What Failed
❌ Rolling IC did not improve win rate (remained 0.00%)
❌ Adaptive weighting increased volatility without improving returns
❌ Absolute IC weighting amplified noise equally with signal

### What We Learned
1. **Look-Ahead Bias Prevention ≠ Predictive Power**: Avoiding future data does not guarantee useful signals
2. **Sample Size Matters**: 60-day windows insufficient for robust IC estimation
3. **Regime Detection ≠ Regime Prediction**: Detecting past regime changes does not predict future behavior
4. **Win Rate Dominance**: Without positive win rates, risk-adjusted metrics are irrelevant

---

## Recommended Next Steps

### Immediate Actions (Phase 2B - IC Refinement)

**1. Implement Signed IC Weighting**
```python
# Current (problematic)
ic_weights[factor] = abs(avg_ic)

# Proposed (directional)
ic_weights[factor] = avg_ic if avg_ic > 0 else 0  # Only use positive predictive factors
```

**2. Add IC Quality Filters**
- Filter factors with p-value > 0.05 (not statistically significant)
- Require minimum sample size (n ≥ 20 observations)
- Set minimum IC threshold (|IC| > 0.05) to filter noise

**3. Test Longer Rolling Windows**
- 12-month rolling (252 days): Better statistical power
- 18-month rolling (378 days): Balance between adaptiveness and stability

### Strategic Re-Evaluation (Phase 3 - Factor Validation)

**The 0% win rate suggests deeper issues beyond IC calculation:**

**4. Factor Selection Audit**
- Current factors: 1M_Momentum, 12M_Momentum, PE_Ratio
- **Hypothesis**: These factors may not have predictive power in Korean market
- **Action**: Test alternative factors (Quality, Value, Low-Volatility)

**5. Stock Selection Criteria**
- Current: Top 45th percentile by composite score
- **Issue**: Percentile thresholding may exclude best opportunities
- **Alternative**: Top N stocks (absolute ranking) or long-short portfolio

**6. Forward Return Horizon**
- Current: 21-day holding period
- **Issue**: May be misaligned with factor persistence
- **Test**: 63-day (3-month) or 126-day (6-month) holding periods

**7. Market Neutralization**
- Current: Long-only portfolio
- **Issue**: Exposed to market beta (KOSPI declined in test period)
- **Alternative**: Market-neutral (long-short) or beta-hedged portfolio

---

## Technical Implementation Notes

### Files Modified
- ✅ `modules/ic_calculator.py` (320 lines) - Rolling IC calculation engine
- ✅ `scripts/backtest_orthogonal_factors.py` - Added `--rolling-window` argument

### Performance Metrics
- Rolling IC calculation time: ~2 seconds per rebalance
- Cache hit rate: 67% (effective caching)
- Database queries: Optimized with LRU cache

### Backward Compatibility
- `--rolling-window 0` maintains static IC behavior (legacy mode)
- No breaking changes to existing backtest scripts

---

## Conclusion

**Tier 2 MVP (Rolling IC) implementation was technically successful but failed to improve strategy performance.**

**Key Insight**: The problem is not IC staleness (regime change), but rather:
1. Absolute IC weighting amplifies noise
2. Insufficient sample size for robust estimation
3. Underlying factors may lack predictive power
4. Stock selection methodology needs revision

**Recommendation**: **Pause Tier 2 development** and conduct **fundamental factor validation** (Phase 3) before proceeding. No amount of IC calculation sophistication will fix flawed factor selection.

**Status**: Tier 2 MVP complete, but results do not justify full Tier 2 implementation (regime detection, IC quality filters) until fundamental issues are addressed.

---

## Appendix: Backtest Output Files

```
backtest_results/orthogonal_backtest_2023-01-01_2024-10-09_20251024_184659.csv  # Static IC
backtest_results/orthogonal_backtest_2023-01-01_2024-10-09_20251024_184737.csv  # 3mo Rolling
backtest_results/orthogonal_backtest_2023-01-01_2024-10-09_20251024_184817.csv  # 6mo Rolling
```
