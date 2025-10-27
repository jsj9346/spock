# IC Time Series Analysis Report

**Date**: 2025-10-23
**Analysis Period**: 2024-10-10 to 2025-09-18 (155 trading dates)
**Factors Analyzed**: PE_Ratio, PB_Ratio
**Holding Period**: 21 trading days (~1 month forward returns)
**Region**: KR (Korea)

---

## Executive Summary

This report analyzes the Information Coefficient (IC) time series for two value factors (PE_Ratio and PB_Ratio) to assess their predictive power for future stock returns in the Korean market.

**Key Findings**:
1. **Both factors show positive average IC**, indicating predictive power for forward returns
2. **PE_Ratio is the stronger predictor** with higher average IC and more consistent positive signals
3. **Factor performance varies significantly by market regime** - strong in Feb/Jun 2025, weak/negative in Apr/Jul-Sep 2025
4. **Statistical significance is inconsistent** - only 23-31% of dates show statistically significant IC (p < 0.05)

---

## Overall Statistics

### PE_Ratio (Price-to-Earnings Ratio)
| Metric | Value |
|--------|-------|
| Average IC | **+0.0509** |
| Standard Deviation | 0.1944 |
| IC Range | -0.3429 to +0.4867 |
| % Positive IC | **56.8%** (88/155 dates) |
| % Statistically Significant | **31.0%** (48/155 dates) |
| Num Stocks (avg) | ~79 |

**Interpretation**: PE_Ratio shows moderate predictive power with positive average IC. More than half of trading dates show positive correlation between PE ratio and forward returns, suggesting value investing principles hold in the Korean market on average.

### PB_Ratio (Price-to-Book Ratio)
| Metric | Value |
|--------|-------|
| Average IC | **+0.0309** |
| Standard Deviation | 0.2030 |
| IC Range | -0.4342 to +0.4744 |
| % Positive IC | **51.0%** (79/155 dates) |
| % Statistically Significant | **23.9%** (37/155 dates) |
| Num Stocks (avg) | ~79 |

**Interpretation**: PB_Ratio shows weaker predictive power than PE_Ratio. Barely more than half of trading dates show positive IC, and statistical significance is less frequent. This suggests PB_Ratio may be less reliable as a standalone factor.

---

## Monthly Performance Analysis

### Strong Performance Periods

#### February 2025 (Best Month)
- **PB_Ratio**: avg IC = **+0.3131** (87.5% positive, 75% significant)
- **PE_Ratio**: avg IC = **+0.2904** (93.8% positive, 75% significant)
- **Context**: Strong factor performance with high statistical significance
- **Sample Size**: 16 trading dates

#### June 2025 (Second Best)
- **PB_Ratio**: avg IC = **+0.2391** (100% positive, 50% significant)
- **PE_Ratio**: avg IC = **+0.2348** (93.8% positive, 75% significant)
- **Context**: Consistently positive IC across all dates
- **Sample Size**: 16 trading dates

#### October 2024 (Initial Period)
- **PB_Ratio**: avg IC = **+0.1122** (100% positive, 0% significant)
- **PE_Ratio**: avg IC = **+0.1024** (100% positive, 0% significant)
- **Context**: 100% positive IC but not reaching statistical significance
- **Sample Size**: 13 trading dates

### Weak/Negative Performance Periods

#### July 2025 (Worst Month)
- **PB_Ratio**: avg IC = **-0.1302** (10.5% positive, 15.8% significant)
- **PE_Ratio**: avg IC = **-0.2034** (0% positive, 47.4% significant)
- **Context**: PE_Ratio had 0% positive IC - complete reversal of value premium
- **Sample Size**: 19 trading dates

#### April 2025 (Second Worst)
- **PB_Ratio**: avg IC = **-0.1925** (0% positive, 27.8% significant)
- **PE_Ratio**: avg IC = **-0.0741** (22.2% positive, 11.1% significant)
- **Context**: PB_Ratio showed 0% positive IC
- **Sample Size**: 18 trading dates

#### August 2025 (Recent Weakness)
- **PB_Ratio**: avg IC = **-0.0606** (18.8% positive, 0% significant)
- **PE_Ratio**: avg IC = **-0.0457** (18.8% positive, 0% significant)
- **Context**: Both factors negative with minimal positive occurrences
- **Sample Size**: 16 trading dates

#### September 2025 (Most Recent)
- **PB_Ratio**: avg IC = **-0.0660** (16.7% positive, 0% significant)
- **PE_Ratio**: avg IC = **-0.1189** (25.0% positive, 8.3% significant)
- **Context**: Continued weakness from August
- **Sample Size**: 12 trading dates

---

## Factor Comparison

| Aspect | PE_Ratio | PB_Ratio | Winner |
|--------|----------|----------|--------|
| **Average IC** | +0.0509 | +0.0309 | PE_Ratio |
| **IC Stability (Std Dev)** | 0.1944 | 0.2030 | PE_Ratio (lower volatility) |
| **% Positive IC** | 56.8% | 51.0% | PE_Ratio |
| **% Significant IC** | 31.0% | 23.9% | PE_Ratio |
| **Best Month IC** | +0.2904 (Feb) | +0.3131 (Feb) | PB_Ratio |
| **Worst Month IC** | -0.2034 (Jul) | -0.1925 (Apr) | PB_Ratio (worse) |

**Conclusion**: PE_Ratio is the more reliable factor overall, showing higher average IC, more consistent positive signals, and greater statistical significance. However, PB_Ratio can show stronger performance in specific market conditions (e.g., February 2025).

---

## Market Regime Analysis

### Regime 1: Value Premium Period (Oct 2024, Feb-Mar 2025, May-Jun 2025)
- **Characteristics**: Positive IC for both factors, frequent statistical significance
- **Duration**: ~70-80 trading dates (45% of sample)
- **Performance**: PE avg IC ~0.15-0.29, PB avg IC ~0.11-0.31
- **Implication**: Value factors work well during these periods

### Regime 2: Value Reversal Period (Apr 2025, Jul-Sep 2025)
- **Characteristics**: Negative IC for both factors, low/zero positive occurrences
- **Duration**: ~65 trading dates (42% of sample)
- **Performance**: PE avg IC -0.20 to -0.05, PB avg IC -0.19 to -0.06
- **Implication**: Value factors fail or reverse during these periods

### Regime 3: Neutral Period (Nov 2024)
- **Characteristics**: Mixed IC, moderate positive occurrences
- **Duration**: ~15 trading dates (10% of sample)
- **Performance**: PE avg IC +0.13, PB avg IC +0.05
- **Implication**: Weak but positive factor signals

---

## Statistical Significance Analysis

### PE_Ratio Significance
- **Overall**: 31.0% of dates (48/155) show statistically significant IC (p < 0.05)
- **Best Months**: June 2025 (75%), February 2025 (75%)
- **Worst Months**: October 2024 (0%), August 2025 (0%)
- **Observation**: Significance is inconsistent and cluster in specific months

### PB_Ratio Significance
- **Overall**: 23.9% of dates (37/155) show statistically significant IC (p < 0.05)
- **Best Months**: February 2025 (75%), March 2025 (50%), June 2025 (50%)
- **Worst Months**: October 2024 (0%), May 2025 (0%), August 2025 (0%), September 2025 (0%)
- **Observation**: Lower and less consistent significance than PE_Ratio

**Key Insight**: The low overall significance rates (23-31%) suggest that:
1. Sample sizes (~78-80 stocks) may be too small for consistent significance
2. Factor signals are noisy and require larger universes for robust results
3. Market conditions heavily influence whether factors reach statistical significance

---

## Recommendations

### For Factor Strategy Development

1. **Primary Factor**: **Use PE_Ratio as the primary value factor**
   - Higher average IC (+0.0509 vs +0.0309)
   - More consistent positive signals (56.8% vs 51.0%)
   - Better statistical significance (31.0% vs 23.9%)

2. **Complementary Factor**: **Consider PB_Ratio as complementary factor**
   - Can show strong performance in specific regimes (Feb 2025: IC=+0.3131)
   - Provides diversification benefit when combined with PE_Ratio
   - May capture different value dimensions

3. **Market Regime Awareness**:
   - **Monitor monthly IC trends** - if IC turns negative for 2+ consecutive months, reduce factor exposure
   - **Consider market regime indicators** - identify characteristics of value premium vs. value reversal periods
   - **Implement dynamic factor weighting** - increase exposure during value premium periods, decrease during reversals

4. **Expand Factor Universe**:
   - Current analysis limited to PE_Ratio and PB_Ratio
   - **Need to calculate IC for momentum factors** (12M_Momentum, 1M_Momentum, RSI_Momentum) once sufficient historical data available
   - **Need quality factors** after fundamental data backfill
   - Multi-factor combination likely to improve consistency

### For Risk Management

1. **Factor Timing Risk**:
   - 42% of sample shows negative factor performance (Apr, Jul-Sep 2025)
   - **Implement stop-loss for factor strategies** when IC turns negative for 20+ consecutive days
   - **Use ensemble approaches** combining multiple factors to reduce single-factor risk

2. **Sample Size Concerns**:
   - Current universe: ~78-80 stocks (likely KR market cap-weighted top stocks)
   - **Statistical power is limited** - consider expanding universe to top 200-300 stocks
   - Larger universe may improve IC consistency and statistical significance

3. **Forward Return Period**:
   - Current analysis: 21-day holding period (~1 month)
   - **Test alternative holding periods** (5 days, 10 days, 63 days) to find optimal IC horizon
   - Shorter periods may show higher IC, longer periods may be more stable

### For Portfolio Construction

1. **Factor Weighting**:
   - If combining PE and PB factors: **Weight PE_Ratio higher** (e.g., 60-70% PE, 30-40% PB)
   - Based on IC ratio: PE IC / (PE IC + PB IC) = 0.0509 / (0.0509 + 0.0309) = **62.2% PE weight**

2. **Rebalancing Frequency**:
   - Given daily IC volatility, **monthly rebalancing** appears appropriate
   - Aligns with 21-day holding period used in IC calculation
   - Reduces transaction costs while capturing factor signals

3. **Position Sizing**:
   - **IC-weighted position sizing**: Use current month's avg IC to scale factor exposure
   - High IC months (Feb, Jun): Increase factor exposure to 1.5x base
   - Low/negative IC months (Apr, Jul-Sep): Reduce factor exposure to 0.5x base or market-neutral

---

## Next Steps

### Immediate (Week 3-4)
1. ✅ **IC Time Series Calculation**: Completed for PE_Ratio and PB_Ratio (310 records, 155 dates)
2. ⏳ **Momentum Factor IC**: Wait for sufficient OHLCV history, then calculate IC for momentum factors
3. ⏳ **Quality Factor IC**: Requires fundamental data backfill first
4. **IC Visualization**: Create time series charts showing IC trends over time
5. **Factor Correlation**: Analyze correlation between PE_Ratio and PB_Ratio IC time series

### Short-term (Week 5-8)
1. **Alternative Holding Periods**: Calculate IC for 5, 10, 63-day holding periods
2. **Expanded Universe**: Increase stock universe to top 200-300 stocks for better statistical power
3. **Market Regime Classification**: Develop rules to classify value premium vs. reversal regimes
4. **Multi-Factor IC**: Calculate IC for factor combinations (PE + PB, PE + Momentum, etc.)

### Medium-term (Week 9-12)
1. **Backtest Value Strategy**: Build strategy using IC-weighted factor scores
2. **Walk-Forward Optimization**: Test strategy with out-of-sample validation
3. **Factor Timing Rules**: Develop rules for dynamic factor exposure based on IC trends
4. **Risk-Adjusted Performance**: Calculate Sharpe ratio, Sortino ratio, max drawdown for factor strategies

---

## Appendix: Methodology

### IC Calculation
- **Definition**: IC (Information Coefficient) = Spearman rank correlation between factor scores and forward returns
- **Formula**: IC = ρ(factor_scores, forward_returns)
- **Holding Period**: 21 trading days (~1 month)
- **Significance**: p-value < 0.05 (two-tailed test)
- **Sample Size**: Minimum 10 stocks per date (actual: 78-82 stocks)

### Forward Return Calculation
```sql
forward_return = (price_t+21 / price_t) - 1
```
- Uses actual trading day count (not calendar days)
- Filters for base_close > 0 and future_close > 0
- Handles missing data by skipping dates without sufficient forward price data

### Factor Score Normalization
- **Z-score normalization**: (raw_value - mean) / std_dev
- **Cross-sectional**: Computed across all stocks on each date
- **Percentile ranking**: 0-100 scale for interpretability

### Database Schema
```sql
CREATE TABLE ic_time_series (
    id BIGSERIAL PRIMARY KEY,
    factor_name VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    region VARCHAR(2) NOT NULL,
    holding_period INTEGER NOT NULL,
    ic DECIMAL(10, 6),
    p_value DECIMAL(10, 6),
    num_stocks INTEGER,
    is_significant BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (factor_name, date, region, holding_period)
);
```

---

**Report Generated**: 2025-10-23 13:17:19
**Total IC Records**: 310 (155 dates × 2 factors)
**Analysis Script**: `/Users/13ruce/spock/scripts/calculate_ic_time_series.py`
**Database**: PostgreSQL + TimescaleDB (quant_platform)
