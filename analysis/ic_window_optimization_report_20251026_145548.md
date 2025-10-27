# IC Window Optimization Report

**Date**: 2025-10-26 14:55:48
**Factor**: RSI_Momentum
**Rebalancing Frequency**: M
**Analysis Period**: 2022-01-01 to 2025-01-02
**Region**: KR
**Holding Period**: 21 days

---

## Executive Summary

⚠️ **CONDITIONAL**: Moderate stability found.

**Best Window**: 30 days
**Autocorrelation (lag-1)**: +0.469 (0.3-0.5 → MODERATE)
**Mean IC**: -0.0618
**Std IC**: 0.2501
**Observations**: 11

**Recommendation**: ⚠️ Monthly RSI_Momentum strategy may work but with caution. Consider quarterly frequency as safer alternative. Proceed to Phase 1.3 for validation backtest.

---

## Detailed Results

### IC Window Optimization Summary

| Window (days) | Mean IC | Std IC | Autocorr(1) | Autocorr(3) | Autocorr(6) | n | Status |
|---------------|---------|--------|-------------|-------------|-------------|---|---------|
| 30 | -0.0618 | 0.2501 | +0.469 | -0.794 | +0.775 | 11 | ⚠️ Moderate |
| 45 | -0.0618 | 0.2501 | +0.469 | -0.794 | +0.775 | 11 | ⚠️ Moderate |
| 60 | -0.0618 | 0.2501 | +0.469 | -0.794 | +0.775 | 11 | ⚠️ Moderate |
| 75 | -0.0618 | 0.2501 | +0.469 | -0.794 | +0.775 | 11 | ⚠️ Moderate |
| 90 | -0.0446 | 0.2567 | +0.425 | -0.782 | +0.925 | 10 | ⚠️ Moderate |
| 120 | -0.0446 | 0.2567 | +0.425 | -0.782 | +0.925 | 10 | ⚠️ Moderate |
| 150 | -0.0446 | 0.2567 | +0.425 | -0.782 | +0.925 | 10 | ⚠️ Moderate |

### Top 5 Windows by Autocorrelation

| Rank | Window | Autocorr(1) | Mean IC | Status |
|------|--------|-------------|---------|--------|
| 1 | 30 days | +0.469 | -0.0618 | ⚠️ Moderate |
| 2 | 45 days | +0.469 | -0.0618 | ⚠️ Moderate |
| 3 | 60 days | +0.469 | -0.0618 | ⚠️ Moderate |
| 4 | 75 days | +0.469 | -0.0618 | ⚠️ Moderate |
| 5 | 90 days | +0.425 | -0.0446 | ⚠️ Moderate |

---

## Key Findings

### Autocorrelation Distribution

- **Stable Windows** (autocorr ≥ 0.5): 0 windows
- **Moderate Windows** (autocorr 0.3-0.5): 7 windows
  - Windows: 30, 45, 60, 75, 90, 120, 150 days
- **Unstable Windows** (autocorr < 0.3): 0 windows

---

## Next Steps

### Phase 1.3: Conditional Backtest (MEDIUM PRIORITY)

Autocorr is moderate (+0.469). Proceed to backtest validation but be prepared for mixed results.

**Alternative**: Skip to Phase 2 (Quarterly Strategy Optimization) if risk tolerance is low.

---

## Appendix

### Optimization Configuration

```yaml
factor: RSI_Momentum
frequency: M
windows_tested: [30, 45, 60, 75, 90, 120, 150]
holding_period: 21
min_stocks: 10
region: KR
date_range: 2022-01-01 to 2025-01-02
```

### Output Files

- `ic_window_optimization_20251026_145548.csv` - Optimization summary
- `ic_window_optimization_timeseries_20251026_145548.csv` - IC time-series for top 3 windows
- `plots/ic_autocorr_vs_window_RSI_Momentum_20251026_145548.png` - Optimization curve
- `ic_window_optimization_report_20251026_145548.md` - This report

---

**Report Generated**: 2025-10-26 14:55:48
**Spock Quant Platform** - Phase 1.2 IC Window Optimization
