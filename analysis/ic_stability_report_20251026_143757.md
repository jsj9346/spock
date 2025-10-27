# IC Stability Analysis Report

**Date**: 2025-10-26 14:37:58
**Analysis Period**: 2022-01-01 to 2025-01-02
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

🚨 **CRITICAL**: Monthly IC is **UNSTABLE** (autocorr=+0.000 < 0.2)
- IC signal quality degrades rapidly at monthly frequency
- Factor predictions become noisy and unreliable
- **Root Cause**: This factor cannot support monthly rebalancing

#### RSI_Momentum

🚨 **CRITICAL**: Monthly IC is **UNSTABLE** (autocorr=+0.000 < 0.2)
- IC signal quality degrades rapidly at monthly frequency
- Factor predictions become noisy and unreliable
- **Root Cause**: This factor cannot support monthly rebalancing

#### ROE_Proxy

🚨 **CRITICAL**: Monthly IC is **UNSTABLE** (autocorr=+0.000 < 0.2)
- IC signal quality degrades rapidly at monthly frequency
- Factor predictions become noisy and unreliable
- **Root Cause**: This factor cannot support monthly rebalancing


---

## Detailed Results

### Stability Metrics (All Frequencies & Windows)

| Factor | Frequency | Window | Mean IC | Std IC | Autocorr(1) | Autocorr(3) | Volatility | n |
|--------|-----------|--------|---------|--------|-------------|-------------|------------|-|
| Operating_Profit_Margin | Monthly | 60 | -0.0016 | 0.1574 | +0.000 | +0.000 | 99.46 | 11 |
| Operating_Profit_Margin | Monthly | 126 | -0.0207 | 0.1519 | +0.000 | +0.000 | 7.35 | 10 |
| Operating_Profit_Margin | Monthly | 252 | -0.0115 | 0.1582 | +0.000 | +0.000 | 13.75 | 9 |
| Operating_Profit_Margin | Monthly | 504 | +0.0213 | 0.1462 | +0.000 | +0.000 | 6.87 | 5 |
| Operating_Profit_Margin | Quarterly | 60 | +0.0431 | 0.2068 | +0.000 | +0.000 | 4.80 | 2 |
| Operating_Profit_Margin | Quarterly | 126 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |
| ROE_Proxy | Monthly | 60 | +0.0239 | 0.1982 | +0.000 | +0.000 | 8.30 | 11 |
| ROE_Proxy | Monthly | 126 | -0.0033 | 0.1862 | +0.000 | +0.000 | 57.08 | 10 |
| ROE_Proxy | Monthly | 252 | +0.0095 | 0.1928 | +0.000 | +0.000 | 20.38 | 9 |
| ROE_Proxy | Monthly | 504 | +0.0526 | 0.2154 | +0.000 | +0.000 | 4.10 | 5 |
| ROE_Proxy | Quarterly | 60 | +0.0888 | 0.2921 | +0.000 | +0.000 | 3.29 | 2 |
| ROE_Proxy | Quarterly | 126 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |
| RSI_Momentum | Monthly | 60 | -0.0618 | 0.2501 | +0.000 | +0.000 | 4.05 | 11 |
| RSI_Momentum | Monthly | 126 | -0.0446 | 0.2567 | +0.000 | +0.000 | 5.75 | 10 |
| RSI_Momentum | Monthly | 252 | -0.0011 | 0.2299 | +0.000 | +0.000 | 203.95 | 9 |
| RSI_Momentum | Monthly | 504 | -0.0406 | 0.1619 | +0.000 | +0.000 | 3.98 | 5 |
| RSI_Momentum | Quarterly | 60 | -0.3350 | 0.1428 | +0.000 | +0.000 | 0.43 | 2 |
| RSI_Momentum | Quarterly | 126 | +0.0000 | 0.0000 | +0.000 | +0.000 | 0.00 | 0 |

---

## Hypothesis Validation

### H1: Monthly IC is unstable with low autocorrelation

**Status**: ✅ **CONFIRMED** - 3/3 factors are unstable at monthly frequency

**Unstable Factors**:
- Operating_Profit_Margin (autocorr=+0.000)
- RSI_Momentum (autocorr=+0.000)
- ROE_Proxy (autocorr=+0.000)

**Implication**: Monthly rebalancing failure is caused by IC signal degradation.

---

## Recommendations

### Immediate Actions (High Priority)

1. **DO NOT USE MONTHLY REBALANCING** for unstable factors
2. **Stick with quarterly rebalancing** for current IC-weighted strategy
3. **Optimize IC rolling window** (Phase 1.2) to potentially stabilize monthly IC
4. **Test individual factors** (Phase 1.3) to isolate unstable factor contribution

### Next Steps (Phase 1.2)

**Test alternative IC windows for monthly rebalancing**:
- Hypothesis: Shorter window (60 days) may be more appropriate for monthly frequency
- Current window (252 days) may be too long for monthly signal updates
- Run `scripts/optimize_ic_window.py` to find optimal window per frequency

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
date_range: 2022-01-01 to 2025-01-02
```

### Output Files

- `ic_stability_timeseries_20251026_143757.csv` - IC time-series data
- `ic_autocorrelation_20251026_143757.csv` - Autocorrelation coefficients
- `ic_stability_metrics_20251026_143757.csv` - Summary statistics
- `plots/ic_timeseries_*.png` - IC time-series plots
- `plots/ic_autocorr_heatmap_20251026_143757.png` - Autocorrelation heatmap
- `ic_stability_report_20251026_143757.md` - This report

---

**Report Generated**: 2025-10-26 14:37:58
**Spock Quant Platform** - Phase 1.1 IC Stability Analysis
