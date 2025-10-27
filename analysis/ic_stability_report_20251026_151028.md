# IC Stability Analysis Report

**Date**: 2025-10-26 15:10:29
**Analysis Period**: 2021-01-01 to 2024-12-31
**Factors Analyzed**: Operating_Profit_Margin, RSI_Momentum, ROE_Proxy
**Region**: KR
**Holding Period**: 21 days

---

## Executive Summary

### Quarterly vs Monthly IC Comparison (window=252 days)

| Factor | Metric | Quarterly (Q) | Monthly (M) | Difference | Analysis |
|--------|--------|---------------|-------------|------------|-----------|

### Key Findings

#### Operating_Profit_Margin

#### RSI_Momentum

#### ROE_Proxy


---

## Detailed Results

### Stability Metrics (All Frequencies & Windows)

| Factor | Frequency | Window | Mean IC | Std IC | Autocorr(1) | Autocorr(3) | Volatility | n |
|--------|-----------|--------|---------|--------|-------------|-------------|------------|-|
| Operating_Profit_Margin | Quarterly | 126 | -0.0207 | 0.1833 | +0.000 | +0.000 | 8.85 | 3 |
| Operating_Profit_Margin | Quarterly | 252 | +0.0431 | 0.2068 | +0.000 | +0.000 | 4.80 | 2 |
| Operating_Profit_Margin | Quarterly | 378 | +0.0431 | 0.2068 | +0.000 | +0.000 | 4.80 | 2 |
| Operating_Profit_Margin | Quarterly | 504 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |
| ROE_Proxy | Quarterly | 126 | -0.0000 | 0.2576 | +0.000 | +0.000 | 9161.18 | 3 |
| ROE_Proxy | Quarterly | 252 | +0.0888 | 0.2921 | +0.000 | +0.000 | 3.29 | 2 |
| ROE_Proxy | Quarterly | 378 | +0.0888 | 0.2921 | +0.000 | +0.000 | 3.29 | 2 |
| ROE_Proxy | Quarterly | 504 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |
| RSI_Momentum | Quarterly | 126 | -0.2505 | 0.1779 | +0.000 | +0.000 | 0.71 | 3 |
| RSI_Momentum | Quarterly | 252 | -0.3350 | 0.1428 | +0.000 | +0.000 | 0.43 | 2 |
| RSI_Momentum | Quarterly | 378 | -0.3350 | 0.1428 | +0.000 | +0.000 | 0.43 | 2 |
| RSI_Momentum | Quarterly | 504 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |

---

## Hypothesis Validation

### H1: Monthly IC is unstable with low autocorrelation

**Status**: ❌ **REJECTED** - All factors show sufficient stability at monthly frequency

**Implication**: IC instability is NOT the root cause. Investigate other hypotheses.

---

## Recommendations

### Next Steps

1. **IC instability is NOT the root cause** - proceed to Phase 2 (Factor Performance Decomposition)
2. **Investigate alternative hypotheses**:
   - H2: Factor overfitting to training period
   - H3: IC weighting method inappropriate for monthly frequency
   - H4: Stock selection threshold (top 45%) causes excessive turnover
3. **Test alternative factor weighting methods** (Phase 2.2)

---

## Appendix

### Analysis Configuration

```yaml
factors: ['Operating_Profit_Margin', 'RSI_Momentum', 'ROE_Proxy']
frequencies: ['D', 'W', 'M', 'Q']
windows: [60, 126, 252, 504]
holding_period: 21
min_stocks: 10
region: KR
date_range: 2021-01-01 to 2024-12-31
```

### Output Files

- `ic_stability_timeseries_20251026_151028.csv` - IC time-series data
- `ic_autocorrelation_20251026_151028.csv` - Autocorrelation coefficients
- `ic_stability_metrics_20251026_151028.csv` - Summary statistics
- `plots/ic_timeseries_*.png` - IC time-series plots
- `plots/ic_autocorr_heatmap_20251026_151028.png` - Autocorrelation heatmap
- `ic_stability_report_20251026_151028.md` - This report

---

**Report Generated**: 2025-10-26 15:10:29
**Spock Quant Platform** - Phase 1.1 IC Stability Analysis
