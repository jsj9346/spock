# Monthly Rebalancing Failure - Troubleshooting Plan

**Date**: 2025-10-26
**Issue**: IC-weighted strategy fails catastrophically at monthly frequency (-87.66% vs +7.11% quarterly)
**Status**: 🔬 **SYSTEMATIC INVESTIGATION REQUIRED**

---

## 📊 Problem Statement

### Observed Symptoms
- **Quarterly rebalancing**: +7.11% return, 100% win rate (2 rebalances)
- **Monthly rebalancing**: -87.66% return, 0% win rate (9 rebalances)
- **Performance gap**: 94.77 percentage points
- **Transaction cost delta**: Only 0.44% (cannot explain gap)

### Core Question
**Why does the same IC-weighted factor strategy (Operating_Profit_Margin + RSI_Momentum + ROE_Proxy) produce opposite results at different rebalancing frequencies?**

---

## 🎯 Troubleshooting Strategy

### 5-Phase Approach

**Phase 1**: IC Stability Analysis (가장 유력한 가설)
**Phase 2**: Factor Performance Decomposition
**Phase 3**: Rebalancing Frequency Optimization
**Phase 4**: Alternative Strategy Testing
**Phase 5**: Production Decision Framework

---

## 📋 Phase 1: IC Stability Analysis (우선순위: 🔥 CRITICAL)

### 목표
IC(Information Coefficient) 계산이 리밸런싱 주기에 따라 얼마나 불안정한지 정량화

### 가설
- **H1**: 월간 IC는 노이즈가 많고 자기상관이 낮음 (신호 품질 저하)
- **H2**: 252일 롤링 윈도우가 월간 리밸런싱에는 부적합 (과거 데이터 과다 의존)
- **H3**: 팩터별 IC 안정성이 다름 (일부 팩터만 월간 주기에서 실패)

### 분석 작업

#### 1.1 IC 시계열 분석 (예상 시간: 2-3시간)

**작업 내용**:
```python
# scripts/analyze_ic_stability.py 생성
def calculate_ic_timeseries(
    factors: List[str],
    start_date: str,
    end_date: str,
    frequencies: List[str]  # ['D', 'W', 'M', 'Q']
):
    """
    각 주기별로 IC를 계산하고 시계열로 저장

    Output:
    - IC 시계열 그래프 (팩터별, 주기별)
    - IC 평균 및 표준편차
    - IC 자기상관 계수 (lag 1, 3, 6, 12)
    """
```

**분석 지표**:
- **IC 평균**: 양수면 예측력 있음
- **IC 표준편차**: 낮을수록 안정적
- **IC 자기상관**: 높을수록 신호 지속성 있음
- **IC 부호 변화 빈도**: 낮을수록 일관성 있음

**기대 결과**:
```
Factor: Operating_Profit_Margin
  Quarterly IC: mean=0.15, std=0.08, autocorr(lag=1)=0.65 ✅
  Monthly IC:   mean=0.02, std=0.25, autocorr(lag=1)=0.15 ❌

Factor: RSI_Momentum
  Quarterly IC: mean=0.12, std=0.10, autocorr(lag=1)=0.55 ✅
  Monthly IC:   mean=-0.05, std=0.30, autocorr(lag=1)=0.05 ❌
```

#### 1.2 IC 롤링 윈도우 최적화 (예상 시간: 2시간)

**작업 내용**:
현재 252일(1년) 고정 윈도우 대신 여러 윈도우 테스트

```python
def optimize_ic_window(
    rebalance_freq: str,  # 'M' or 'Q'
    test_windows: List[int]  # [60, 126, 252, 504]
):
    """
    각 롤링 윈도우별 백테스트 수익률 비교

    예상 발견:
    - 월간 리밸런싱: 60일 윈도우가 최적일 수 있음 (짧은 주기 → 짧은 윈도우)
    - 분기 리밸런싱: 252일 윈도우가 최적 (긴 주기 → 긴 윈도우)
    """
```

**테스트 윈도우**:
- 60일 (3개월): 단기 트렌드
- 126일 (6개월): 중기 트렌드
- 252일 (1년): 현재 설정
- 504일 (2년): 장기 트렌드

**Output**:
```
Rebalancing: Monthly, IC Window: 60 days  → Return: ??%
Rebalancing: Monthly, IC Window: 126 days → Return: ??%
Rebalancing: Monthly, IC Window: 252 days → Return: -87.66% (현재)
Rebalancing: Monthly, IC Window: 504 days → Return: ??%
```

#### 1.3 팩터별 IC 기여도 분석 (예상 시간: 3시간)

**작업 내용**:
각 팩터를 단독으로 사용했을 때 월간/분기별 성과 비교

```python
def backtest_single_factor(
    factor: str,
    rebalance_freq: str
):
    """
    단일 팩터 전략 백테스트

    예상 발견:
    - RSI_Momentum이 월간 주기에서 특히 실패할 가능성 (기술적 지표 노이즈)
    - Operating_Profit_Margin은 주기 영향 적을 수 있음 (펀더멘털 안정성)
    """
```

**테스트 케이스**:
```
Period: 2023-01-02 to 2024-01-02

1. Operating_Profit_Margin only:
   - Quarterly: ??%
   - Monthly: ??%

2. RSI_Momentum only:
   - Quarterly: ??%
   - Monthly: ??%

3. ROE_Proxy only:
   - Quarterly: ??%
   - Monthly: ??%

4. Equal-weighted (현재는 IC-weighted):
   - Quarterly: ??%
   - Monthly: ??%
```

### 성공 기준

**Phase 1 통과 조건**:
- ✅ IC 불안정성 정량화 완료 (평균, 표준편차, 자기상관 계산)
- ✅ 최적 IC 윈도우 발견 (월간 리밸런싱에서 양수 수익률 달성)
- ✅ 실패 원인 팩터 특정 (3개 팩터 중 주범 식별)

**Phase 1 실패 시**:
- IC 윈도우 최적화로도 월간 수익률 개선 안 되면 → Phase 2로 이동
- 모든 팩터가 월간 주기에서 실패하면 → 근본적 전략 재설계 필요

---

## 📋 Phase 2: Factor Performance Decomposition (우선순위: 🔥 HIGH)

### 목표
팩터 과적합 여부 및 out-of-sample 일반화 성능 검증

### 가설
- **H4**: 2022-2023 훈련 기간에 과적합되어 2023-2024 테스트 기간에서 실패
- **H5**: 팩터 조합 방식(IC-weighted)이 부적절함
- **H6**: Top 45 percentile 선택 기준이 월간 주기에 과다 거래 유발

### 분석 작업

#### 2.1 Walk-Forward IC 안정성 검증 (예상 시간: 2시간)

**작업 내용**:
```python
def validate_ic_out_of_sample():
    """
    In-sample IC vs Out-of-sample IC 비교

    예상 발견:
    - 훈련 기간 IC: 높음 (과적합)
    - 테스트 기간 IC: 낮거나 음수 (일반화 실패)
    """

    # Period 1
    train_ic = calculate_ic(period='2022-01-01 to 2023-01-01')  # 훈련
    test_ic = calculate_ic(period='2023-01-02 to 2024-01-02')   # 테스트

    print(f"IC Stability: {train_ic} → {test_ic}")
```

**기대 결과**:
```
Factor: Operating_Profit_Margin
  Train IC (2022-2023): 0.18 ✅
  Test IC (2023-2024):  0.03 ⚠️  (과적합 의심)

Factor: RSI_Momentum
  Train IC (2022-2023): 0.15 ✅
  Test IC (2023-2024): -0.08 ❌ (역전!)
```

#### 2.2 팩터 조합 방식 비교 (예상 시간: 3시간)

**작업 내용**:
IC-weighted 대신 다른 조합 방식 테스트

```python
def compare_factor_weighting_methods():
    """
    1. IC-weighted (현재)
    2. Equal-weighted (동일 가중치)
    3. Inverse-volatility weighted (변동성 역가중)
    4. Rank-based combination (순위 기반)
    """
```

**테스트 케이스**:
```
Rebalancing: Monthly (2023-01-02 to 2024-01-02)

1. IC-weighted (current):
   Return: -87.66% ❌

2. Equal-weighted (1/3 each):
   Return: ??%

3. Inverse-volatility:
   Return: ??%

4. Rank-based (combine ranks, not scores):
   Return: ??%
```

#### 2.3 Stock Selection Threshold 최적화 (예상 시간: 2시간)

**작업 내용**:
Top 45 percentile 대신 다른 임계값 테스트

```python
def optimize_selection_threshold():
    """
    Top X percentile 테스트: 20%, 30%, 40%, 45%, 50%

    가설: 월간 리밸런싱은 더 집중된 포트폴리오가 유리할 수 있음
    (거래 비용 대비 알파 극대화)
    """
```

**테스트 케이스**:
```
Rebalancing: Monthly, IC Window: 252 days

Top 20%: Avg holdings ~40 stocks → Return: ??%
Top 30%: Avg holdings ~55 stocks → Return: ??%
Top 40%: Avg holdings ~65 stocks → Return: ??%
Top 45%: Avg holdings ~68 stocks → Return: -87.66% (현재)
Top 50%: Avg holdings ~75 stocks → Return: ??%
```

### 성공 기준

**Phase 2 통과 조건**:
- ✅ IC 과적합 여부 확인 (train vs test IC 비교)
- ✅ 대안 팩터 조합 방식 발견 (equal-weighted가 나을 가능성)
- ✅ 최적 선택 임계값 발견 (월간 리밸런싱 양수 수익률)

**Phase 2 실패 시**:
- 모든 조합 방식이 실패하면 → 팩터 자체 문제 (Phase 4로 이동)

---

## 📋 Phase 3: Rebalancing Frequency Optimization (우선순위: 🟡 MEDIUM)

### 목표
최적 리밸런싱 주기 발견 (통계적 유의성 + 전략 안정성 균형)

### 가설
- **H7**: 격월(Bi-monthly) 주기가 최적 균형점일 수 있음
- **H8**: 반기(Semi-annual) 주기도 충분한 데이터 제공 가능

### 분석 작업

#### 3.1 중간 주기 백테스트 (예상 시간: 3시간)

**작업 내용**:
```python
def test_intermediate_frequencies():
    """
    테스트 주기:
    - W: Weekly (주간) - 52 rebalances/year
    - BM: Bi-monthly (격월) - 6 rebalances/year
    - Q: Quarterly (분기) - 4 rebalances/year (현재 성공)
    - SA: Semi-annual (반기) - 2 rebalances/year
    - A: Annual (연간) - 1 rebalance/year
    """
```

**테스트 매트릭스**:
```
Period: 2023-01-02 to 2024-01-02

Frequency | Num Rebalances | Expected Result
----------|----------------|------------------
Weekly    | 52             | ??? (과다 거래 우려)
Bi-monthly| 6              | ??? (균형점 후보)
Quarterly | 4              | +7.11% ✅ (검증됨)
Semi-annual| 2             | ??? (데이터 부족)
Annual    | 1              | ??? (극단적)
```

#### 3.2 Sharpe Ratio vs Frequency 분석 (예상 시간: 2시간)

**작업 내용**:
```python
def analyze_sharpe_vs_frequency():
    """
    각 주기별:
    1. 수익률
    2. Sharpe ratio (계산 가능한 경우)
    3. Max Drawdown
    4. 거래 비용
    5. 통계적 유의성 (rebalance 개수)

    목표: Sharpe > 1.0 + 충분한 샘플 (≥6 rebalances)
    """
```

**기대 결과**:
```
Frequency    | Return | Sharpe | Max DD | Rebalances | Usable?
-------------|--------|--------|--------|------------|--------
Weekly       | ??%    | ??     | ??%    | 52         | Too frequent?
Bi-monthly   | ??%    | ??     | ??%    | 6          | ✅ 후보
Quarterly    | +7.11% | 0.0*   | 0.0%*  | 4          | ⚠️ 데이터 부족
Semi-annual  | ??%    | N/A    | ??%    | 2          | ❌ 통계 무의미

* 0.0은 계산 불가를 의미 (rebalances < 10)
```

### 성공 기준

**Phase 3 통과 조건**:
- ✅ 격월 또는 반기 주기에서 양수 수익률 + Sharpe > 1.0
- ✅ ≥6 rebalances로 통계적 유의성 확보
- ✅ 거래 비용 < 2% of capital

**Phase 3 실패 시**:
- 분기 주기만 작동하면 → 통계적 유의성 포기하고 분기 사용
- 모든 주기 실패하면 → Phase 4 (전략 재설계)

---

## 📋 Phase 4: Alternative Strategy Testing (우선순위: 🟢 LOW)

### 목표
IC-weighted 방식의 근본적 한계 인정 시 대안 전략 탐색

### 대안 전략 후보

#### 4.1 Threshold-based Rebalancing (예상 시간: 4시간)

**개념**: 시간 기반이 아닌 이벤트 기반 리밸런싱

```python
def threshold_rebalancing():
    """
    리밸런싱 조건:
    1. IC 변화 > 20% (신호 품질 변화 시만 리밸런싱)
    2. 포트폴리오 drift > 10% (목표 비중에서 벗어날 때만)
    3. 변동성 급증 (VIX > 30 등)

    장점: 불필요한 거래 회피
    단점: 리밸런싱 시점 불규칙 (백테스트 복잡)
    """
```

#### 4.2 Buy-and-Hold with Factor Screens (예상 시간: 3시간)

**개념**: 초기 선택 후 리밸런싱 최소화

```python
def buy_and_hold_with_filters():
    """
    1. 초기: IC 기반 top 45% 선택
    2. 보유: 6개월 이상 홀드
    3. 제거: 팩터 점수가 bottom 70%로 떨어질 때만 매도
    4. 추가: 캐시로 신규 top 30% 매수

    장점: 거래 비용 최소화, 트렌드 포착
    단점: 시장 급변 시 대응 느림
    """
```

#### 4.3 Machine Learning Factor Combination (예상 시간: 8시간)

**개념**: XGBoost/RandomForest로 비선형 팩터 조합

```python
def ml_factor_model():
    """
    Features:
    - 3개 팩터 점수
    - 팩터 변화율 (1M, 3M, 6M)
    - 시장 체제 변수 (VIX, 수급 지표)

    Target: 1개월 후 수익률 (월간) 또는 3개월 후 수익률 (분기)

    장점: 비선형 관계 포착, 시장 체제 적응
    단점: 과적합 위험, 설명력 낮음
    """
```

### 성공 기준

**Phase 4 통과 조건**:
- ✅ 대안 전략 중 1개 이상 양수 수익률 + Sharpe > 1.0
- ✅ 분기별 전략보다 우수한 성과

**Phase 4 실패 시**:
- 모든 전략 실패 → 전략 포기, 다른 팩터 조합 탐색

---

## 📋 Phase 5: Production Decision Framework (우선순위: 🔴 CRITICAL)

### 목표
Phase 1-4 결과를 종합하여 프로덕션 배포 여부 결정

### 의사결정 기준

#### 5.1 최소 요구 사항 (ALL must pass)

```yaml
minimum_requirements:
  statistical_significance:
    - num_rebalances: ≥ 6
    - test_periods: ≥ 2 (walk-forward)
    - time_span: ≥ 2 years

  performance_metrics:
    - avg_return: > 0%
    - sharpe_ratio: > 1.0
    - max_drawdown: < -20%
    - win_rate: > 45%

  robustness:
    - positive_periods: > 60%
    - ic_autocorrelation: > 0.3
    - out_of_sample_ic: > 0.05

  risk_management:
    - transaction_costs: < 2% of capital
    - avg_holdings: > 50 (diversification)
    - volatility: < 30% (annualized)
```

#### 5.2 의사결정 트리

```
1. Phase 1 (IC 안정성) 통과?
   YES → 2번으로
   NO  → REJECT (IC-weighted 방식 근본적 결함)

2. Phase 2 (팩터 조합) 최적화 성공?
   YES → 3번으로
   NO  → REJECT (팩터 자체 문제)

3. Phase 3 (주기 최적화) 발견?
   YES → 4번으로
   NO  → CONDITIONAL (분기만 사용, 통계 유의성 희생)

4. 최소 요구 사항 ALL 통과?
   YES → APPROVE (Paper Trading 3개월)
   NO  → REJECT (프로덕션 부적합)

5. Paper Trading (3개월) 성공?
   YES → PRODUCTION (실제 자본 투입)
   NO  → REJECT (실거래 재현성 실패)
```

#### 5.3 배포 시나리오

**시나리오 A: 최적 주기 발견 (격월 성공)**
```yaml
deployment_plan:
  strategy: IC-weighted Tier 3
  rebalancing: Bi-monthly (6 rebalances/year)
  ic_window: 126 days (최적화 결과)
  selection: Top 40% (최적화 결과)

  paper_trading:
    duration: 3 months
    capital: ₩100M (가상)
    success_criteria:
      - Sharpe > 1.0
      - Return > 5%
      - Max DD < -15%

  production:
    initial_capital: ₩500M
    ramp_up: 3개월 (₩500M → ₩2B)
    monitoring: Daily Sharpe, weekly IC
```

**시나리오 B: 분기만 작동 (통계 유의성 부족)**
```yaml
conditional_approval:
  strategy: IC-weighted Tier 3
  rebalancing: Quarterly (4 rebalances/year)
  limitations:
    - Sharpe ratio 계산 불가 (rebalances < 10)
    - 통계적 유의성 낮음 (small sample)

  mitigation:
    - 5년 이상 장기 백테스트 (20+ rebalances)
    - 다른 시장 체제 검증 (bull, bear, neutral)
    - Monte Carlo 시뮬레이션 (1000+ scenarios)

  decision:
    - 추가 검증 통과 시 → Paper Trading
    - 실패 시 → REJECT
```

**시나리오 C: 모든 주기 실패**
```yaml
rejection_plan:
  reason: IC-weighted approach fundamentally flawed

  alternatives:
    1. 새로운 팩터 조합 탐색
    2. 머신러닝 모델 개발
    3. 다른 전략 프레임워크 (예: Pairs Trading)

  timeline:
    - 1개월: Alternative factor research
    - 2개월: New strategy development
    - 3개월: Validation
```

---

## 📅 실행 타임라인

### Week 1: Phase 1 (IC 안정성)
```
Day 1-2: IC 시계열 분석 스크립트 개발
Day 3:   팩터별 IC 계산 및 시각화
Day 4:   IC 롤링 윈도우 최적화
Day 5:   단일 팩터 백테스트
Day 6-7: Phase 1 결과 분석 및 보고서 작성
```

### Week 2: Phase 2 (팩터 조합)
```
Day 1-2: Walk-forward IC 검증
Day 3-4: 팩터 조합 방식 비교 백테스트
Day 5:   Stock selection threshold 최적화
Day 6-7: Phase 2 결과 분석 및 보고서
```

### Week 3: Phase 3 (주기 최적화)
```
Day 1-3: 중간 주기 백테스트 (격월, 반기, 주간)
Day 4-5: Sharpe ratio vs frequency 분석
Day 6-7: 최적 주기 선정 및 검증
```

### Week 4: Phase 4 & 5 (대안 전략 및 의사결정)
```
Day 1-3: 대안 전략 프로토타입 (threshold, buy-hold, ML)
Day 4-5: 종합 성과 비교 및 의사결정 트리 적용
Day 6-7: 최종 보고서 및 프로덕션 계획 수립
```

---

## 🛠️ 필요 도구 및 스크립트

### 신규 개발 필요
```
scripts/
  analyze_ic_stability.py          # Phase 1.1
  optimize_ic_window.py            # Phase 1.2
  backtest_single_factor.py        # Phase 1.3
  validate_ic_out_of_sample.py     # Phase 2.1
  compare_factor_weighting.py      # Phase 2.2
  optimize_selection_threshold.py  # Phase 2.3
  test_intermediate_frequencies.py # Phase 3.1
  analyze_sharpe_vs_frequency.py   # Phase 3.2
  threshold_rebalancing.py         # Phase 4.1 (optional)
  buy_hold_with_filters.py         # Phase 4.2 (optional)
  ml_factor_model.py               # Phase 4.3 (optional)
```

### 기존 재사용 가능
```
scripts/
  backtest_orthogonal_factors.py   # 백테스트 엔진 (재사용)
  walk_forward_validation.py       # Walk-forward 검증 (재사용)
  calculate_metrics_from_csv.py    # 사후 메트릭 계산 (재사용)
```

---

## 📊 예상 결과 및 시나리오

### 낙관적 시나리오 (70% 확률)
```
Phase 1: IC 윈도우 최적화로 월간 수익률 개선 (60일 윈도우 사용)
         → 월간: -87.66% → -10% ~ +5%

Phase 2: Equal-weighted 조합이 IC-weighted보다 우수
         → 월간: -10% → +8% ~ +12%

Phase 3: 격월 주기가 최적 균형점
         → 격월: +10% ~ +15%, Sharpe 1.2~1.8

결론: 격월 리밸런싱 + Equal-weighted + 60일 IC 윈도우 → APPROVE
```

### 현실적 시나리오 (20% 확률)
```
Phase 1: IC 윈도우 최적화로 월간 약간 개선
         → 월간: -87.66% → -30% ~ -15%

Phase 2: 팩터 조합 최적화로 손실 감소
         → 월간: -30% → -5% ~ +3%

Phase 3: 분기 주기만 안정적, 격월은 변동성 높음
         → 분기: +7.11%, 격월: -2% ~ +5%

결론: 분기 리밸런싱만 사용 (통계 유의성 희생) → CONDITIONAL APPROVE
      → 5년 백테스트 추가 검증 필요
```

### 비관적 시나리오 (10% 확률)
```
Phase 1: IC 윈도우 최적화 실패
         → 모든 윈도우에서 월간 손실

Phase 2: 모든 팩터 조합 방식 실패
         → IC-weighted, Equal-weighted, Rank-based 모두 손실

Phase 3: 분기만 작동 (그것도 n=2로 통계 무의미)
         → 분기 +7.11%는 운일 가능성

결론: IC-weighted 전략 전면 재설계 필요 → REJECT
      → Phase 4 대안 전략 또는 새로운 팩터 탐색
```

---

## ✅ 체크리스트

### Phase 1 완료 기준
- [ ] `analyze_ic_stability.py` 개발 완료
- [ ] 3개 팩터의 IC 시계열 분석 (일간, 주간, 월간, 분기별)
- [ ] IC 자기상관 계수 계산 (lag 1, 3, 6, 12)
- [ ] 최적 IC 롤링 윈도우 발견 (60, 126, 252, 504일 테스트)
- [ ] 단일 팩터 백테스트 완료 (3 factors × 2 frequencies)
- [ ] Phase 1 결과 보고서 작성

### Phase 2 완료 기준
- [ ] Walk-forward IC 안정성 검증 완료
- [ ] 4가지 팩터 조합 방식 백테스트 (IC-weighted, Equal, Inv-vol, Rank)
- [ ] Stock selection threshold 최적화 (20%, 30%, 40%, 45%, 50%)
- [ ] 최적 조합 발견 (월간 양수 수익률)
- [ ] Phase 2 결과 보고서 작성

### Phase 3 완료 기준
- [ ] 5가지 주기 백테스트 (주간, 격월, 분기, 반기, 연간)
- [ ] Sharpe ratio vs frequency 그래프 작성
- [ ] 최적 주기 선정 (통계 유의성 + 성과 균형)
- [ ] Phase 3 결과 보고서 작성

### Phase 4 완료 기준 (조건부)
- [ ] Threshold-based 리밸런싱 프로토타입
- [ ] Buy-and-hold with filters 프로토타입
- [ ] ML factor model 프로토타입
- [ ] 대안 전략 성과 비교
- [ ] Phase 4 결과 보고서 작성

### Phase 5 완료 기준
- [ ] 의사결정 트리 적용
- [ ] 최소 요구 사항 검증
- [ ] 배포 시나리오 선정 (A, B, or C)
- [ ] 최종 종합 보고서 작성
- [ ] Paper trading 계획 수립 (approve 시)

---

## 📝 보고서 양식

### 각 Phase별 보고서 포함 내용

```markdown
# Phase X Results

## Executive Summary
- 주요 발견 (3-5 bullet points)
- 가설 검증 결과 (H1, H2, ... 각각 통과/실패)
- 다음 Phase 진행 여부

## Detailed Analysis
- 백테스트 결과 (테이블 + 그래프)
- 통계적 유의성 검증
- 예상 vs 실제 비교

## Code & Methodology
- 사용 스크립트 경로
- 파라미터 설정
- 재현 가능성 (명령어)

## Conclusions
- 핵심 인사이트
- 제한사항
- 다음 단계 권장사항
```

---

## 🚨 리스크 및 예외 처리

### 리스크 1: Phase 1 조기 실패
**시나리오**: IC 최적화로도 월간 수익률 개선 안 됨

**대응**:
1. Phase 2로 즉시 이동 (팩터 조합 최적화)
2. Phase 1 결과를 Phase 2에 피드백 (어떤 팩터가 불안정한지)
3. Phase 2도 실패 시 → Phase 4 (대안 전략)

### 리스크 2: 데이터 부족
**시나리오**: DART API 2022-2025 데이터만으로 5년 백테스트 불가

**대응**:
1. FinanceDataReader 등 대안 데이터 소스 탐색
2. Monte Carlo 시뮬레이션으로 통계 유의성 보완
3. Cross-sectional validation (다른 시장/섹터 검증)

### 리스크 3: 모든 Phase 실패
**시나리오**: IC-weighted 전략 근본적 결함

**대응**:
1. 전략 폐기 후 새로운 접근법 탐색
2. 머신러닝 기반 팩터 조합
3. 다른 전략 프레임워크 (Pairs Trading, Statistical Arbitrage)

---

**Plan Created**: 2025-10-26
**Expected Completion**: 4 weeks (Phase 1-5)
**Critical Path**: Phase 1 → Phase 2 → Phase 3 → Phase 5
**Optional**: Phase 4 (대안 전략, 필요 시만)
**Author**: Spock Quant Platform Team
