# Factor Weighting Comparison Report - Quarterly Rebalancing

**Date**: 2025-10-26 15:17:02
**Analysis Period**: 2021-01-01 to 2024-12-31
**Factors**: Operating_Profit_Margin,RSI_Momentum,ROE_Proxy
**Train/Test Split**: 1 year / 1 year
**Top Percentile**: 45%
**Initial Capital**: ₩100,000,000

---

## Executive Summary

This report compares 4 factor weighting methods for quarterly rebalancing:

1. **IC-Weighted**: Dynamic weights based on rolling IC (current baseline)
2. **Equal-Weighted**: 1/3 each factor (simple, robust)
3. **Inverse-Volatility**: Weight by inverse IC volatility (favor stable factors)
4. **Rank-Based**: Combine factor ranks, not scores (outlier-robust)

**Hypothesis**: Equal-weighted may outperform IC-weighted by avoiding IC estimation error during regime changes.

---

## Results by Method

### IC-Weighted ❌

**Average Metrics**:
- Return: **-22.74%**
- Sharpe Ratio: **-3.26**
- Max Drawdown: **-22.74%**
- Win Rate: **0.0%**

**Period-by-Period Results**:

| Period | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------------|-------------|--------|--------|--------|----------|----------|
| 2 | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | -22.74% | -3.26 | -22.74% | 0.0% | 62 |

### Equal-Weighted ❌

**Average Metrics**:
- Return: **-8.62%**
- Sharpe Ratio: **-1.15**
- Max Drawdown: **-11.21%**
- Win Rate: **33.3%**

**Period-by-Period Results**:

| Period | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------------|-------------|--------|--------|--------|----------|----------|
| 2 | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | -8.62% | -1.15 | -11.21% | 33.3% | 62 |

### Inverse-Volatility ❌

**Average Metrics**:
- Return: **-8.27%**
- Sharpe Ratio: **-1.11**
- Max Drawdown: **-10.51%**
- Win Rate: **33.3%**

**Period-by-Period Results**:

| Period | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------------|-------------|--------|--------|--------|----------|----------|
| 2 | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | -8.27% | -1.11 | -10.51% | 33.3% | 62 |

### Rank-Based ❌

**Average Metrics**:
- Return: **-3.29%**
- Sharpe Ratio: **-1.07**
- Max Drawdown: **-13.48%**
- Win Rate: **33.3%**

**Period-by-Period Results**:

| Period | Train Period | Test Period | Return | Sharpe | Max DD | Win Rate | Holdings |
|--------|--------------|-------------|--------|--------|--------|----------|----------|
| 2 | 2022-01-02 to 2023-01-02 | 2023-01-03 to 2024-01-03 | -3.29% | -1.07 | -13.48% | 33.3% | 62 |

---

## Method Comparison Summary

| Method | Avg Return | Avg Sharpe | Avg Max DD | Avg Win Rate | Best Period | Worst Period |
|--------|------------|------------|------------|--------------|-------------|--------------|
| IC-Weighted | -22.74% | -3.26 | -22.74% | 0.0% | -22.74% | -22.74% |
| Equal-Weighted | -8.62% | -1.15 | -11.21% | 33.3% | -8.62% | -8.62% |
| Inverse-Volatility | -8.27% | -1.11 | -10.51% | 33.3% | -8.27% | -8.27% |
| Rank-Based | -3.29% | -1.07 | -13.48% | 33.3% | -3.29% | -3.29% |

---

## Key Findings

### Best Performing Method
**Rank-Based** achieved the highest average return of **-3.29%**.

### Worst Performing Method
**IC-Weighted** had the lowest average return of **-22.74%**.

### Period 1 (2022 Test Year) Performance

---

## Recommendations

1. **All methods failed to achieve positive returns** - consider abandoning IC-weighted approach entirely.
2. Explore alternative strategies: Single-factor strategies, buy-and-hold, or machine learning approaches.

---

## Next Steps

1. HALT further optimization of IC-weighted approach
2. Pivot to Alternative Strategies:
   - Equal-weighted multi-factor (no IC weighting)
   - Single-factor strategies (RSI_Momentum only, Operating_Profit_Margin only)
   - Buy-and-hold with fundamental screens
   - Machine learning factor combination

---

**Report Generated**: 2025-10-26 15:17:02
**Spock Quant Platform** - Phase 2.3 Factor Weighting Comparison
