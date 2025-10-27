# Walk-Forward Validation Guide

## Overview

Walk-Forward 검증은 **Out-of-Sample Testing**의 표준 방법론으로, 전략이 다양한 시장 체제에서 robust한지 검증합니다.

**현재 상태**: Tier 3 전략은 단일 기간(2023-2024)에서만 검증되었으므로, 프로덕션 배포 전 필수적으로 Walk-Forward 검증이 필요합니다.

---

## Methodology

### Walk-Forward 방식

```
Period 1:
  IC Calculation (Train): 2018-2019 (2년)
  Backtest (Test):        2020 (1년)

Period 2:
  IC Calculation (Train): 2020-2021 (2년, rolled forward)
  Backtest (Test):        2022 (1년)

Period 3:
  IC Calculation (Train): 2022-2023 (2년)
  Backtest (Test):        2024 (1년)
```

**핵심 원칙**:
- Train 기간(IC 계산)은 **항상 Test 기간(백테스트) 이전**
- Look-Ahead Bias 방지
- 다양한 시장 체제 검증 (2020 코로나, 2022 베어마켓, 2024 회복)

---

## Usage

### 1. Tier 3 검증 (권장)

```bash
python3 scripts/walk_forward_validation.py \
  --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy \
  --train-years 2 \
  --test-years 1 \
  --start 2018-01-01 \
  --end 2024-10-09 \
  --capital 100000000 \
  --top-percentile 45 \
  --rebalance-freq Q
```

**예상 실행시간**: 약 10-15분 (3개 백테스트 실행)

**출력**:
```
================================================================================
WALK-FORWARD VALIDATION SUMMARY
================================================================================

📊 Configuration:
   Factors: Operating_Profit_Margin, RSI_Momentum, ROE_Proxy
   Periods: 3
   Successful: 3/3

📈 RETURNS:
   Average:       2.15%
   Std Dev:       1.20%
   Min:          -0.50%
   Max:           3.80%
   Positive:      2/3 periods
   Negative:      1/3 periods

📊 RISK METRICS:
   Avg Sharpe:    2.45
   Std Sharpe:    0.35
   Avg Win Rate:  53.3%
   Avg Max DD:   -5.20%
   Worst Max DD: -7.50%

💰 COSTS:
   Avg Transaction Cost: 0.75% of capital

🎯 PRODUCTION READINESS CHECK:
   ✅ Positive Avg Return
   ✅ Sharpe > 1.0
   ✅ Win Rate > 45%
   ✅ Max DD < 20%
   ✅ Positive Majority

🚀 READY FOR PRODUCTION
================================================================================
```

---

### 2. 커스텀 검증

#### A. 더 긴 학습 기간 (3년)

```bash
python3 scripts/walk_forward_validation.py \
  --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy \
  --train-years 3 \  # 3년 학습
  --test-years 1 \
  --start 2015-01-01 \
  --end 2024-10-09
```

#### B. 더 긴 테스트 기간 (2년)

```bash
python3 scripts/walk_forward_validation.py \
  --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy \
  --train-years 2 \
  --test-years 2 \  # 2년 테스트
  --start 2016-01-01 \
  --end 2024-10-09
```

#### C. 다른 팩터 조합 테스트

```bash
python3 scripts/walk_forward_validation.py \
  --factors 12M_Momentum,1M_Momentum,PE_Ratio \
  --train-years 2 \
  --test-years 1 \
  --start 2018-01-01 \
  --end 2024-10-09
```

---

## Output Files

### CSV Results

**Location**: `analysis/walk_forward_results_YYYYMMDD_HHMMSS.csv`

**Columns**:
- `period`: Period number
- `train_start`, `train_end`: IC calculation period
- `test_start`, `test_end`: Backtest period
- `return`: Total return (%)
- `sharpe`: Sharpe ratio
- `win_rate`: Win rate (%)
- `max_drawdown`: Maximum drawdown (%)
- `transaction_costs`: Transaction costs (% of capital)
- `avg_holdings`: Average number of holdings

**Example**:
```csv
period,train_start,train_end,test_start,test_end,return,sharpe,win_rate,max_drawdown,transaction_costs,avg_holdings
1,2018-01-01,2020-01-01,2020-01-02,2021-01-01,3.5,2.8,60.0,-3.2,0.75,68.5
2,2020-01-02,2022-01-01,2022-01-02,2023-01-02,-0.8,0.2,45.0,-7.5,0.78,70.2
3,2022-01-02,2024-01-01,2024-01-02,2024-10-09,2.4,2.7,50.0,-4.4,0.73,69.1
```

---

## Interpretation Guide

### Production Readiness Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| **Positive Avg Return** | > 0% | Strategy must be profitable on average |
| **Sharpe > 1.0** | > 1.0 | Risk-adjusted returns must be acceptable |
| **Win Rate > 45%** | > 45% | Majority of rebalance periods profitable |
| **Max DD < 20%** | > -20% | Losses must be manageable |
| **Positive Majority** | >50% positive periods | More winning periods than losing |

**Decision Matrix**:
- **All criteria passed**: ✅ Ready for production
- **1-2 criteria failed**: ⚠️  Needs improvement (parameter tuning)
- **3+ criteria failed**: ❌ Not production ready (back to research)

### Expected Results for Tier 3

Based on current single-period validation (+2.42%, 2.78 Sharpe):

**Optimistic Scenario** (all periods succeed):
- Avg Return: 2.0-3.0%
- Avg Sharpe: 2.5-3.0
- Win Rate: 55-65%
- Max DD: -5% to -8%

**Realistic Scenario** (some periods fail):
- Avg Return: 1.0-2.0%
- Avg Sharpe: 1.5-2.5
- Win Rate: 45-55%
- Max DD: -8% to -12%

**Pessimistic Scenario** (frequent failures):
- Avg Return: 0.0-1.0%
- Avg Sharpe: 0.5-1.5
- Win Rate: 35-45%
- Max DD: -12% to -20%

---

## Troubleshooting

### Error: "Backtest failed"

**Cause**: Insufficient data for some periods

**Solution**:
```bash
# Check data availability
python3 scripts/check_data_availability.py \
  --start 2018-01-01 \
  --end 2024-10-09 \
  --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy
```

### Error: "No periods generated"

**Cause**: Not enough data for train+test years

**Solution**: Reduce train/test years or extend date range
```bash
# Reduce to 1 year train + 1 year test
python3 scripts/walk_forward_validation.py \
  --train-years 1 \
  --test-years 1 \
  --start 2020-01-01 \
  --end 2024-10-09
```

### Warning: "High variability in returns"

**Cause**: Strategy performance inconsistent across periods

**Interpretation**:
- High `Std Dev` in returns indicates regime dependency
- Consider dynamic factor allocation based on market conditions

---

## Next Steps After Validation

### If Validation Passes ✅

1. **Parameter Optimization**:
   - Test different `top_percentile` (30%, 40%, 50%)
   - Test different `rebalance_freq` (M, Q, SA)
   - Test different IC holding periods (10d, 21d, 42d)

2. **Stress Testing**:
   - Test in 2008 Financial Crisis
   - Test in 2020 COVID Crash
   - Test in 2022 Bear Market

3. **Production Deployment**:
   - Start with conservative position sizing (50% of target)
   - Monitor IC monthly
   - Setup alert system for IC degradation

### If Validation Fails ❌

1. **Diagnose Failures**:
   - Which periods failed? (bear market, recovery, crash?)
   - Which factors underperformed?
   - Were IC quality filters too strict/relaxed?

2. **Iterate on Strategy**:
   - Test alternative factor combinations
   - Adjust weighting schemes (risk parity, volatility-weighted)
   - Consider regime-based factor rotation

3. **Research New Factors**:
   - Expand factor library (earnings momentum, cash flow yield)
   - Test factors with higher IC (> 0.08)
   - Validate new factors using Phase 3-1 IC analysis

---

## Technical Details

### Period Generation Logic

```python
def generate_walk_forward_periods(start_date, end_date, train_years, test_years):
    """
    Generate non-overlapping walk-forward periods

    Example: start=2018, end=2024, train=2, test=1

    Period 1: Train(2018-2019) → Test(2020)
    Period 2: Train(2020-2021) → Test(2022)  # Rolled forward by test_years
    Period 3: Train(2022-2023) → Test(2024)

    Returns: List of (train_start, train_end, test_start, test_end) tuples
    """
```

**Key Features**:
- No overlap between train and test periods (Look-Ahead Bias prevention)
- Rolling window approach (train period slides forward)
- Stops when test period exceeds end_date

### Result Aggregation

```python
def aggregate_results(all_results):
    """
    Aggregate results across all periods

    Calculates:
    - Average, std dev, min, max returns
    - Average, std dev Sharpe ratios
    - Positive/negative period counts
    - Worst max drawdown
    - Average transaction costs
    """
```

---

## FAQ

### Q: Walk-Forward 검증에서 "Train"은 ML 학습인가요?

**A**: 아닙니다. "Train"은 **IC 계산 기간**을 의미합니다. Tier 3는 단순 균등 가중치(Equal Weighting)를 사용하며, ML 학습은 없습니다.

### Q: 몇 개의 Period가 적절한가요?

**A**: 최소 3개, 권장 5개 이상입니다. 더 많은 Period일수록 통계적 유의성이 높아집니다.

### Q: 모든 Period에서 양수 수익이 필요한가요?

**A**: 아닙니다. 평균 수익이 양수이고, 양수 Period가 과반수이면 충분합니다. 일부 Period(예: 베어마켓)에서 손실은 정상입니다.

### Q: Tier 3가 검증을 통과하지 못하면?

**A**: 다음 옵션을 고려하세요:
1. 파라미터 최적화 (top percentile, rebalance freq)
2. 대체 가중치 방식 (risk parity, volatility-weighted)
3. 새로운 팩터 조합 연구

### Q: 언제 ML을 적용해야 하나요?

**A**: Walk-Forward 검증이 **완전히 통과**한 후에만 고려하세요. 단순 균등 가중치가 실패하면 ML도 실패할 가능성이 높습니다.

---

## References

- **Comprehensive Optimization Report**: `analysis/comprehensive_optimization_report_20251024.md`
- **ML Skeleton Code**: `modules/ml/factor_ml_combiner.py` (향후 확장용)
- **Test Code**: `tests/test_walk_forward_validation.py`

---

**Author**: Spock Quant Platform
**Date**: 2025-10-24
**Status**: Production Ready (Script)
**Next**: Run validation on Tier 3, analyze results, make Go/No-Go decision
