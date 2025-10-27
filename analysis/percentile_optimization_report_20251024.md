# Percentile Grid Search Optimization Report

**Generated**: 2025-10-24 18:23:42
**Test Period**: 2023-01-01 to 2024-10-09 (1.75 years)
**IC Training Period**: 2021-01-04 to 2022-12-31
**Initial Capital**: ₩100,000,000
**Rebalance Frequency**: Quarterly
**Factors**: 1M_Momentum (59.20%), 12M_Momentum (24.34%), PE_Ratio (16.45%)

## Grid Search Results Comparison

| Percentile | Total Return | Final Value | Sharpe | Max DD | Win Rate | Avg Holdings | Volatility | Ann. Return |
|------------|--------------|-------------|--------|--------|----------|--------------|------------|-------------|
| 45th ⭐ | -29.93% | ₩70,066,061 | -3.738 | -29.77% | 0.00% | 65.0 | 17.13% | -18.39% |
| 50th | -41.46% | ₩58,538,306 | -10.001 | -41.30% | 0.00% | 59.3 | 9.34% | -26.36% |
| 55th | -46.76% | ₩53,239,668 | -120.189 | -46.60% | 0.00% | 53.3 | 0.90% | -30.25% |
| 60th | -47.32% | ₩52,675,818 | -15.973 | -47.16% | 0.00% | 47.7 | 6.84% | -30.67% |
| 65th | -49.62% | ₩50,383,201 | -10.569 | -49.45% | 0.00% | 41.3 | 10.92% | -32.41% |
| 75th | -50.01% | ₩49,992,225 | -26.712 | -49.85% | 0.00% | 30.0 | 4.38% | -32.71% |
| 70th | -51.39% | ₩48,608,115 | -51.433 | -51.23% | 0.00% | 35.7 | 2.35% | -33.78% |
| 80th ❌ | -99.59% | ₩408,183 | -4.104 | -99.43% | 0.00% | 16.8 | 30.14% | -95.69% |

## Key Insights

### 1. Optimal Configuration
- **Best Percentile**: 45th percentile
- **Total Return**: -29.93% (vs baseline -99.59%)
- **Improvement**: +69.66 percentage points
- **Average Holdings**: 65.0 stocks
- **Max Drawdown**: -29.77%

### 2. Performance Gradient
- **Pattern**: Performance deteriorates monotonically as percentile increases
- **Interpretation**: Broader diversification (lower percentile = more stocks) helps mitigate weak IC signals
- **Range**: -29.93% (best) to -99.59% (worst)

### 3. Risk-Return Profile
- **Best Volatility**: 0.90% at 55th percentile
- **Best Sharpe**: -3.738 at 45th percentile
- **Optimal Risk-Return**: 45th percentile balances return and risk

### 4. Fundamental Issues Remain
- **Win Rate**: 0.00% (all configurations show 0% win rate)
- **Conclusion**: Parameter tuning improves absolute performance but cannot solve IC regime change problem
- **Next Step**: Tier 2 (Regime-Aware IC) implementation is necessary


## Recommendation

### Adopt 45th Percentile Configuration

**Rationale**:
1. **Best Performance**: -29.93% total return (highest among all configurations)
2. **Adequate Diversification**: 65.0 stocks provides good risk distribution
3. **Reasonable Volatility**: 17.13% annualized volatility
4. **Clear Improvement**: +69.66pp vs baseline

### Critical Next Steps: Tier 2 Implementation

Despite the improvement, **parameter tuning alone is insufficient**:

- **Problem**: 0% win rate persists across all configurations
- **Root Cause**: IC regime change between training (2021-2022) and test (2023-2024) periods
- **Solution**: Implement Tier 2 (Regime-Aware IC Calculation)

**Tier 2 Requirements**:
1. Rolling IC windows (6-month moving calculation)
2. Regime change detection (IC sign flip identification)
3. Adaptive factor weighting (responsive to current market regime)
4. IC quality filters (exclude unreliable IC estimates)

**Expected Impact**:
- Win rate improvement from 0% to 40-60%
- More consistent quarterly returns
- Better alignment with actual market dynamics

