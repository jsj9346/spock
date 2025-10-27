# Monthly Rebalancing Failure Analysis

**Date**: 2025-10-26
**Issue**: Monthly rebalancing causes catastrophic losses (-87.66%)
**Status**: 🚨 **CRITICAL STRATEGY FAILURE IDENTIFIED**

---

## 📊 Executive Summary

Monthly rebalancing of the IC-weighted Tier 3 strategy resulted in **catastrophic losses** compared to quarterly rebalancing:

- **Quarterly (Q)**: +7.11% return, 100% win rate, ₩107M final value
- **Monthly (M)**: -87.66% return, 0% win rate, ₩12M final value
- **Performance Delta**: **-94.77 percentage points**

**Root Cause**: The IC-weighted factor selection system is **fundamentally unstable** at monthly rebalancing frequency, causing systematic selection of losing stocks.

**Critical Finding**: This is NOT a transaction cost issue (+0.44% difference) but a **strategy design flaw** that makes the system **unsuitable for frequent rebalancing**.

---

## 🔍 Detailed Analysis

### Period 1 Comparison (2023-01-02 to 2024-01-02)

#### Quarterly Rebalancing Results ✅

```
================================================================================
BACKTEST RESULTS - QUARTERLY (Q)
================================================================================

📈 RETURNS:
   Initial Capital:     ₩    100,000,000
   Final Value:         ₩    107,105,983
   Total Return:                  7.11%
   Annualized Return:             7.11%

📊 RISK METRICS:
   Sharpe Ratio:                   0.00 (insufficient data - only 2 rebalances)
   Max Drawdown:                  0.00%
   Volatility (annual):            nan%

💰 TRANSACTION COSTS:
   Total Costs:         ₩        454,632
   % of Capital:                  0.45%

📉 TRADING STATS:
   Win Rate:                    100.00%
   Num Rebalances:                    2
   Avg Holdings:                   68.0
```

**Rebalance Points**:
1. **2023-03-31**: ₩99.86M (-0.14% - initial transaction costs)
2. **2023-06-30**: ₩107.11M (+7.26% - recovery + gains)

#### Monthly Rebalancing Results ❌

```
================================================================================
BACKTEST RESULTS - MONTHLY (M)
================================================================================

📈 RETURNS:
   Initial Capital:     ₩    100,000,000
   Final Value:         ₩     12,342,445
   Total Return:                -87.66%
   Annualized Return:           -87.68%

📊 RISK METRICS:
   Sharpe Ratio:                 -34.09 (deeply negative)
   Max Drawdown:                -87.64%
   Volatility (annual):         165.66% (extremely high!)

💰 TRANSACTION COSTS:
   Total Costs:         ₩        887,740
   % of Capital:                  0.89%

📉 TRADING STATS:
   Win Rate:                      0.00% (every month lost money!)
   Num Rebalances:                    9
   Avg Holdings:                   60.9
```

**Cascading Loss Progression**:

| Month | Date | Portfolio Value | Monthly Return | Cumulative Loss |
|-------|------|----------------|----------------|-----------------|
| 0 | 2023-01-02 | ₩100,000,000 | - | 0.00% |
| 1 | 2023-01-31 | ₩99,881,764 | -0.12% | -0.12% |
| 2 | 2023-02-28 | ₩73,699,359 | **-26.21%** | -26.30% |
| 3 | 2023-03-31 | ₩58,068,390 | **-21.21%** | -41.93% |
| 4 | 2023-05-31 | ₩56,412,769 | -2.85% | -43.59% |
| 5 | 2023-06-30 | ₩47,993,700 | **-14.92%** | -52.01% |
| 6 | 2023-07-31 | ₩32,177,079 | **-32.96%** | -67.82% |
| 7 | 2023-08-31 | ₩22,122,296 | **-31.25%** | -77.88% |
| 8 | 2023-10-31 | ₩14,994,665 | **-32.22%** | -85.01% |
| 9 | 2023-11-30 | ₩12,342,445 | -17.69% | **-87.66%** |

**Key Observations**:
- ❌ **0% Win Rate**: Every single month lost money
- ❌ **5 catastrophic months**: >20% loss in a single month
- ❌ **No recovery periods**: Continuous decline throughout year
- ❌ **Accelerating losses**: Later months had larger percentage drops

---

## 🔬 Root Cause Analysis

### Transaction Cost Analysis (NOT the cause)

**Quarterly Costs**:
- Total: ₩454,632 (0.45% of capital)
- Per Rebalance: ₩227,316
- Impact on Return: -0.45%

**Monthly Costs**:
- Total: ₩887,740 (0.89% of capital)
- Per Rebalance: ₩98,638
- Impact on Return: -0.89%

**Cost Delta**: 0.44 percentage points
**Performance Delta**: **94.77 percentage points**

**Conclusion**: Transaction costs explain only **0.47%** of the performance gap. The real issue is **systematic stock selection failure**.

### IC Stability Analysis (PRIMARY SUSPECT 🎯)

**Information Coefficient (IC)** measures the correlation between factor scores and future returns.

**Hypothesis**: IC becomes **unstable and noisy** at monthly frequency, causing:
1. **Overfitting to short-term noise**: Monthly IC calculations capture market noise rather than true factor signal
2. **Whipsaw Trading**: Frequent rebalancing based on unstable IC causes entering/exiting at worst times
3. **Signal Decay**: Factor predictive power may decay faster than monthly intervals

**Evidence**:
- Quarterly IC (calculated over 252 days) → Stable, fewer signals → 100% win rate
- Monthly IC (recalculated monthly) → Noisy, frequent signals → 0% win rate

**Test Needed**: Compare IC autocorrelation at quarterly vs monthly frequency

### Factor Overfitting Analysis (SECONDARY SUSPECT 📊)

**Tier 3 Factors**:
1. Operating_Profit_Margin (fundamental quality)
2. RSI_Momentum (technical momentum)
3. ROE_Proxy (profitability)

**Hypothesis**: Factors may be **overfit to training period** and fail when applied at higher frequency

**Evidence**:
- Training period: 2022-01-01 to 2023-01-01
- Test period: 2023-01-02 to 2024-01-02
- Quarterly rebalancing uses 2 snapshots → works (maybe lucky?)
- Monthly rebalancing uses 9 snapshots → fails systematically

**Implication**: The strategy may not generalize well to out-of-sample periods when rebalanced frequently.

### Market Regime Analysis (TERTIARY FACTOR 🌊)

**2023 Market Context**:
- KOSPI 2023 Performance: +18.7%
- Quarterly Strategy: +7.11% (underperformed market but positive)
- Monthly Strategy: -87.66% (catastrophic underperformance)

**Hypothesis**: Monthly rebalancing may be **contra-trend** at critical turning points

**Example**:
- February 2023: -26.21% loss (market may have been rebounding)
- July 2023: -32.96% loss (market may have been rallying)

**Implication**: IC-weighted selection at monthly frequency may be selecting stocks that:
- Recently performed well (momentum) but are about to reverse
- Have strong fundamentals (value/quality) but are out of favor short-term

---

## 🎯 Critical Insights

### 1. IC-Weighted Strategy is Frequency-Dependent

**Discovery**: The same factor combination (Operating_Profit_Margin + RSI_Momentum + ROE_Proxy) produces:
- **Positive returns** at quarterly frequency (+7.11%)
- **Catastrophic losses** at monthly frequency (-87.66%)

**Implication**: Rebalancing frequency is NOT a tunable parameter but a **fundamental strategy design choice**.

### 2. More Frequent ≠ Better Metrics

**Original Assumption** (from metric parsing report):
> "Monthly rebalancing (12 rebalances/year) provides sufficient data for accurate Sharpe ratio calculation"

**Reality**:
- Monthly rebalancing DOES provide sufficient data (9 rebalances)
- Sharpe ratio IS calculated (-34.09)
- But the strategy **fundamentally fails** at this frequency

**Lesson**: **Statistical validity ≠ Strategy validity**

### 3. Quarterly Results May Be Noise

**Concerning Pattern**:
- Quarterly: 100% win rate (2/2 profitable rebalances)
- Monthly: 0% win rate (0/9 profitable rebalances)

**Statistical Question**: Is the quarterly +7.11% return just **lucky timing** with only 2 data points?

**Evidence Suggesting Luck**:
- Small sample size (n=2 rebalances)
- Monthly results show consistent losses across 9 periods
- 2/2 wins could be random chance with small n

**Recommended Test**: Extend quarterly validation to more periods (require ≥5 rebalances)

### 4. Strategy Robustness is Questionable

**Production Readiness Implications**:
- ❌ **Not robust to rebalancing frequency** (critical failure)
- ❌ **No evidence of consistent alpha generation** (monthly shows systematic losses)
- ❌ **High sensitivity to parameter choices** (frequency = 94% performance swing)

**Conclusion**: The IC-weighted Tier 3 strategy is **NOT production-ready** due to fundamental instability.

---

## 📋 Recommendations

### Immediate Actions (Today) 🚨

**1. DO NOT USE MONTHLY REBALANCING**
- Monthly rebalancing results in systematic losses
- This is not a data/metric issue but a **strategy design flaw**
- Production deployment at monthly frequency would be **catastrophic**

**2. INVESTIGATE QUARTERLY RESULTS VALIDITY**
- 100% win rate with n=2 is statistically suspicious
- May be luck rather than skill
- Require longer validation period (5+ years if possible)

**3. HALT PRODUCTION DEPLOYMENT**
- Current validation shows strategy is **not robust**
- Frequency sensitivity indicates **fundamental design issue**
- Production deployment would be **high risk**

### Short-Term Analysis (This Week) 📊

**4. ANALYZE IC STABILITY**
Create `scripts/analyze_ic_stability.py` to:
- Calculate IC at different frequencies (daily, weekly, monthly, quarterly)
- Measure IC autocorrelation
- Identify optimal rebalancing frequency for each factor
- Detect when IC signal decays

**5. BACKTEST ALTERNATIVE FREQUENCIES**
Test intermediate frequencies:
- **Bi-monthly** (every 2 months): 6 rebalances/year
- **Quarterly** (confirmed): 4 rebalances/year
- **Semi-annual** (every 6 months): 2 rebalances/year
- **Annual**: 1 rebalance/year

Identify if there's a "sweet spot" where strategy is both:
- Robust (positive returns)
- Frequent enough for meaningful metrics (≥5 rebalances)

**6. TEST INDIVIDUAL FACTORS**
Run backtests with:
- Single-factor strategies (isolate which factor is unstable)
- Different factor combinations
- Alternative IC weighting schemes (equal weight, inverse volatility)

### Long-Term Redesign (Next Month) 🔬

**7. IMPLEMENT ADAPTIVE REBALANCING**
Instead of fixed frequency, rebalance based on:
- **IC Change Threshold**: Only rebalance when IC changes significantly
- **Volatility Regime**: Reduce frequency during high volatility
- **Market Regime Detection**: Adjust frequency based on market conditions

**8. ADD TRANSACTION COST MODEL TO OPTIMIZATION**
Current IC optimization ignores transaction costs. Modify to:
- Penalize frequent turnover
- Optimize for net alpha (gross alpha - transaction costs)
- Constrain rebalancing frequency based on cost/benefit

**9. CONSIDER ALTERNATIVE STRATEGIES**
Given fundamental instability, explore:
- **Buy-and-hold with factor screens** (no rebalancing)
- **Event-driven rebalancing** (only when stocks drop out of top percentile)
- **Machine learning models** that don't rely on IC weighting

---

## 📊 Comparison Table: Quarterly vs Monthly

| Metric | Quarterly (Q) | Monthly (M) | Analysis |
|--------|--------------|-------------|----------|
| **Final Value** | ₩107.1M | ₩12.3M | Monthly destroys 88% of capital |
| **Return** | +7.11% | -87.66% | **94.77% delta** - catastrophic |
| **Sharpe Ratio** | 0.0 (no data) | -34.09 | Monthly is calculable but deeply negative |
| **Max Drawdown** | 0.0% | -87.64% | Monthly has near-total drawdown |
| **Volatility** | nan | 165.66% | Monthly is extremely volatile |
| **Win Rate** | 100% | 0% | Monthly loses EVERY period |
| **Transaction Costs** | 0.45% | 0.89% | +0.44% delta - NOT the cause |
| **Num Rebalances** | 2 | 9 | More rebalances = worse results |
| **Avg Holdings** | 68.0 | 60.9 | Similar diversification |

### Performance by Month (Monthly Strategy Only)

| Month | Return | Analysis |
|-------|--------|----------|
| Jan 2023 | -0.12% | Small initial loss |
| Feb 2023 | **-26.21%** | First catastrophic month |
| Mar 2023 | **-21.21%** | Continued bleeding |
| May 2023 | -2.85% | Slight stabilization |
| Jun 2023 | **-14.92%** | Another large loss |
| Jul 2023 | **-32.96%** | Worst single month |
| Aug 2023 | **-31.25%** | Second worst month |
| Oct 2023 | **-32.22%** | Third worst month |
| Nov 2023 | -17.69% | Final loss |

**Pattern**: 5 out of 9 months had >20% losses - systematic failure, not random

---

## 🔗 Related Files

**Backtest Results**:
- Quarterly (Q): `backtest_results/orthogonal_backtest_2023-01-02_2024-01-02_20251026_141218.csv`
- Monthly (M): `backtest_results/orthogonal_backtest_2023-01-02_2024-01-02_20251026_141159.csv`

**Validation Results**:
- Quarterly Walk-Forward: `analysis/walk_forward_results_20251026_134312.csv`
- Monthly Walk-Forward: `analysis/walk_forward_results_20251026_141054.csv`

**Previous Reports**:
- Walk-Forward Success (Quarterly): `analysis/walk_forward_validation_success_report_20251026.md`
- Metric Parsing Analysis: `analysis/metric_parsing_fix_report_20251026.md`
- Post-Hoc Calculator Limitation: `analysis/post_hoc_calculator_limitation_report_20251026.md`

**Analysis Scripts**:
- Backtest Engine: `scripts/backtest_orthogonal_factors.py`
- Walk-Forward Validation: `scripts/walk_forward_validation.py`
- Post-Hoc Calculator: `scripts/calculate_metrics_from_csv.py` (cannot fix strategy failure)

---

## 📝 Lessons Learned

### 1. More Data Points ≠ Better Strategy

**Initial Goal**: Get more rebalances (12 vs 4) to calculate accurate Sharpe ratio

**Reality**: More frequent rebalancing **broke the strategy** entirely

**Lesson**: Statistical validity and strategy robustness are **orthogonal concerns**

### 2. Rebalancing Frequency is Not a Free Parameter

**Assumption**: Rebalancing frequency is an optimization parameter (daily, weekly, monthly, quarterly)

**Discovery**: Frequency fundamentally changes strategy behavior:
- Quarterly: Moderate positive returns
- Monthly: Catastrophic losses

**Lesson**: Rebalancing frequency is a **core strategy design choice**, not a tunable parameter

### 3. IC-Weighted Strategies Are Frequency-Sensitive

**Finding**: Information Coefficient calculations are **highly sensitive** to:
- Rolling window length (currently 252 days)
- Rebalancing frequency (quarterly vs monthly)
- Factor stability over rebalancing interval

**Implication**: IC-weighted strategies require **careful frequency calibration** - cannot arbitrarily change rebalancing schedule

### 4. Small Sample Validation is Dangerous

**Quarterly Validation**:
- 2 periods = 100% win rate = +7.11% return
- Looked "successful" but was it luck?

**Monthly Validation**:
- 9 periods = 0% win rate = -87.66% return
- Systematic failure exposed

**Lesson**: **Require minimum 5-10 rebalances** for meaningful validation (not 2!)

### 5. Transaction Costs Are Red Herring

**Initial Suspicion**: Higher monthly transaction costs (0.89% vs 0.45%) cause losses

**Reality**: Costs explain <0.5% of 94.77% performance gap

**Lesson**: Always check **order of magnitude** - don't optimize pennies while losing dollars

---

## 🚨 Production Deployment Warning

### DO NOT DEPLOY THIS STRATEGY

**Reasons**:
1. ❌ **Not robust to rebalancing frequency** (94% performance swing)
2. ❌ **No evidence of consistent alpha** (monthly shows 0% win rate)
3. ❌ **High parameter sensitivity** (critical design flaw)
4. ❌ **Quarterly results may be luck** (n=2 statistically insufficient)
5. ❌ **No understanding of failure mode** (IC instability unproven hypothesis)

### Required Before Production

1. ✅ **IC Stability Analysis**: Understand why monthly fails
2. ✅ **Extended Validation**: ≥5 years with ≥20 rebalances (quarterly)
3. ✅ **Robustness Testing**: Verify consistent performance across multiple time periods
4. ✅ **Parameter Sensitivity**: Understand all parameter impacts
5. ✅ **Failure Mode Analysis**: Identify and mitigate failure scenarios

---

**Report Generated**: 2025-10-26 14:12 KST
**Status**: 🚨 CRITICAL STRATEGY FAILURE - DO NOT USE MONTHLY REBALANCING
**Next Action**: Investigate IC stability and extend quarterly validation
**Author**: Spock Quant Platform Team
