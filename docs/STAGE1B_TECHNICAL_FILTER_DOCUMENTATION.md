# Stage 1-B: 기술적 필터링 (Technical Pre-Filter)

**모듈**: `modules/stock_pre_filter.py`
**목적**: Stage 0 결과에 OHLCV 기술 지표를 적용하여 거래 가능한 종목으로 압축
**입력**: ~600개 종목 (filter_cache_stage0)
**출력**: ~180개 종목 (filter_cache_stage1)
**통과율**: ~30% (600 → 180개)

---

## 📊 개요

Stage 1-B는 **기술적 분석 기반 사전 필터링** 단계로, Stage 0에서 선별된 종목에 대해 **5개의 기술 지표**를 적용하여 단기 거래에 적합한 종목을 선별합니다.

### 핵심 철학
- **Weinstein Stage 2 이론**: 상승 추세 시작 단계 포착
- **False Breakout 제거**: 과매수/과매도 구간 제외
- **거래량 검증**: 가격 움직임의 신뢰성 확인
- **다층 방어**: 5개 필터를 모두 통과해야 Stage 1 승인

---

## 🔍 필터링 프로세스

### 1. 데이터 로딩 및 검증

#### 1.1 Stage 0 결과 로딩
```python
# filter_cache_stage0에서 로드
SELECT ticker, name, market, region, currency,
       market_cap_krw, trading_value_krw, current_price_krw
FROM filter_cache_stage0
WHERE region = 'KR' AND stage0_passed = 1
ORDER BY market_cap_krw DESC
```

**입력 데이터 구조**:
- `ticker`: 종목 코드 (예: 005930)
- `name`: 종목명 (예: 삼성전자)
- `market_cap_krw`: 시가총액 (KRW 정규화)
- `trading_value_krw`: 거래대금 (KRW 정규화)
- `current_price_krw`: 현재가 (KRW 정규화)

#### 1.2 OHLCV 데이터 로딩
```sql
SELECT date, open, high, low, close, volume,
       ma5, ma20, ma60, ma120, ma200,
       rsi_14, macd, macd_signal, macd_histogram,
       volume_ma20
FROM ohlcv_data
WHERE ticker = ? AND timeframe = 'D'
ORDER BY date DESC
LIMIT 250
```

**데이터 요구사항**:
- **최소 기간**: 250일 (MA200 계산 위해)
- **데이터 연속성**: 60일 이상 공백 없음 (선택적)
- **기술 지표**: MA, RSI, MACD, Volume 사전 계산 완료

**데이터 부족 시 처리**:
```python
if len(ohlcv_data) < 250:
    logger.debug(f"⚠️ {ticker}: OHLCV 데이터 부족 ({len(ohlcv_data)}일)")
    failed_count += 1
    continue  # 다음 종목으로 스킵
```

---

## 🎯 5개 기술 필터 상세

### Filter 1: MA Alignment (이동평균선 정배열)

**목적**: 상승 추세 확인 (Weinstein Stage 2 핵심 조건)

**검증 로직**:
```python
def _check_ma_alignment(latest: Dict) -> Dict:
    """
    MA Alignment: 5 > 20 > 60 > 120 > 200 (bullish structure)

    Returns:
        {'passed': True/False, 'score': 0-100, 'reason': str}
    """
    ma5, ma20, ma60, ma120, ma200 = latest.get('ma5'), ...

    # Perfect alignment (100점)
    if ma5 > ma20 > ma60 > ma120 > ma200:
        return {'passed': True, 'score': 100, 'reason': ''}

    # Partial alignment (75점)
    elif ma5 > ma20 > ma60:
        return {'passed': True, 'score': 75, 'reason': ''}

    # Fail
    else:
        return {'passed': False, 'score': 0, 'reason': 'MA 정배열 아님'}
```

**점수 산정**:
- **100점**: 완벽한 정배열 (5 > 20 > 60 > 120 > 200)
- **75점**: 부분 정배열 (5 > 20 > 60)
- **0점**: 정배열 아님 → **필터 탈락**

**통과 조건**: score ≥ 75

---

### Filter 2: RSI Range (과매수/과매도 검증)

**목적**: False Breakout 제거 (지나치게 오르거나 떨어진 구간 제외)

**검증 로직**:
```python
def _check_rsi_range(latest: Dict, config: Dict) -> Dict:
    """
    RSI Range: 30-70 (not overbought/oversold)

    Args:
        config: stage1_filters.rsi_min, rsi_max (default: 30-70)

    Returns:
        {'passed': True/False, 'score': 0-100, 'reason': str}
    """
    rsi = latest.get('rsi')
    rsi_min = config.get('rsi_min', 30)  # 과매도 기준
    rsi_max = config.get('rsi_max', 70)  # 과매수 기준

    if rsi < rsi_min:
        return {'passed': False, 'score': 0, 'reason': f'RSI 과매도 ({rsi:.1f})'}

    elif rsi > rsi_max:
        return {'passed': False, 'score': 0, 'reason': f'RSI 과매수 ({rsi:.1f})'}

    else:
        # RSI=50이 최적 (중립), 멀수록 감점
        score = 100 - abs(rsi - 50) * 2
        return {'passed': True, 'score': int(score), 'reason': ''}
```

**점수 산정**:
- **RSI = 50**: 100점 (최적 중립 구간)
- **RSI = 40 or 60**: 80점
- **RSI = 30 or 70**: 60점
- **RSI < 30 or > 70**: 0점 → **필터 탈락**

**설정 가능 파라미터** (`kr_filter_config.yaml`):
```yaml
stage1_filters:
  rsi_min: 30   # 과매도 기준 (하한)
  rsi_max: 70   # 과매수 기준 (상한)
```

**통과 조건**: 30 ≤ RSI ≤ 70

---

### Filter 3: MACD Signal (추세 전환 확인)

**목적**: 상승 모멘텀 확인 (Bullish Crossover 검증)

**검증 로직**:
```python
def _check_macd_signal(latest: Dict, config: Dict) -> Dict:
    """
    MACD Signal: Bullish Crossover (MACD > Signal & Histogram > 0)

    Returns:
        {'passed': True/False, 'signal': 'BULLISH'|'BEARISH'|'UNKNOWN', 'reason': str}
    """
    macd = latest.get('macd')
    macd_signal = latest.get('macd_signal')
    macd_histogram = latest.get('macd_histogram')

    # Bullish condition: MACD > Signal AND Histogram > 0
    if macd > macd_signal and macd_histogram > 0:
        return {'passed': True, 'signal': 'BULLISH', 'reason': ''}

    else:
        return {'passed': False, 'signal': 'BEARISH', 'reason': 'MACD 약세'}
```

**MACD 구성 요소**:
- **MACD Line**: EMA(12) - EMA(26)
- **Signal Line**: EMA(MACD, 9)
- **Histogram**: MACD - Signal

**Bullish Crossover 조건**:
1. **MACD > Signal**: MACD 라인이 Signal 라인 위에 있음
2. **Histogram > 0**: 양수 히스토그램 (상승 모멘텀)

**통과 조건**: MACD > Signal AND Histogram > 0

---

### Filter 4: Volume Spike (거래량 급증 검증)

**목적**: 가격 움직임의 신뢰성 확인 (거래량 동반 상승)

**검증 로직**:
```python
def _check_volume_spike(latest: Dict, config: Dict) -> Dict:
    """
    Volume Spike: Recent volume > 20-day average × 1.5

    Args:
        config: stage1_filters.volume_spike_ratio (default: 1.5)

    Returns:
        {'passed': True/False, 'spike': True/False, 'reason': str}
    """
    volume = latest.get('volume')
    volume_ma20 = latest.get('volume_ma20')

    # Get threshold from config
    volume_spike_ratio = config.get('volume_spike_ratio', 1.5)

    if volume > volume_ma20 * volume_spike_ratio:
        return {'passed': True, 'spike': True, 'reason': ''}

    else:
        return {'passed': False, 'spike': False, 'reason': 'Volume 부족'}
```

**거래량 급증 기준**:
- **Default**: 현재 거래량 > 20일 평균 거래량 × 1.5
- **Configurable**: `volume_spike_ratio` 파라미터로 조정 가능

**설정 예시** (`kr_filter_config.yaml`):
```yaml
stage1_filters:
  volume_spike_ratio: 1.5   # 150% 이상 거래량 증가
```

**통과 조건**: volume > volume_ma20 × 1.5

---

### Filter 5: Price Above MA20 (지지선 확인)

**목적**: 단기 지지선 확인 (MA20 위 거래)

**검증 로직**:
```python
def _check_price_above_ma20(latest: Dict) -> Dict:
    """
    Price Above MA20: Current price > MA20 (support level)

    Returns:
        {'passed': True/False, 'reason': str}
    """
    close = latest.get('close')
    ma20 = latest.get('ma20')

    if close > ma20:
        return {'passed': True, 'reason': ''}

    else:
        return {'passed': False, 'reason': 'Price < MA20'}
```

**지지선 개념**:
- **MA20**: 20일 이동평균선 (단기 지지선)
- **Price > MA20**: 상승 추세 유지 중
- **Price < MA20**: 조정 또는 하락 추세

**통과 조건**: close > ma20

---

## 📈 Stage 1 점수 계산

### 가중치 기반 점수 산정

**5개 필터 가중치**:
```python
weights = {
    'ma_alignment': 0.30,      # 30% - 가장 중요 (추세 확인)
    'rsi': 0.25,               # 25% - 과매수/과매도 검증
    'macd': 0.20,              # 20% - 모멘텀 확인
    'volume': 0.15,            # 15% - 거래량 검증
    'price_position': 0.10     # 10% - 지지선 확인
}
```

**점수 계산 공식**:
```python
def _calculate_stage1_score(result: Dict) -> int:
    """
    Stage 1 Score = Σ (각 필터 점수 × 가중치)

    Returns:
        0-100 점수
    """
    ma_score = result['ma_alignment_score']          # 0-100
    rsi_score = result['rsi_score']                  # 0-100
    macd_score = 100 if result['macd_signal'] == 'BULLISH' else 0
    volume_score = 100 if result['volume_spike'] else 0
    price_score = 100  # Already validated in filter

    total_score = (
        ma_score * 0.30 +
        rsi_score * 0.25 +
        macd_score * 0.20 +
        volume_score * 0.15 +
        price_score * 0.10
    )

    return int(total_score)
```

**점수 예시**:
```python
# Example 1: Perfect Score
ma_score = 100, rsi_score = 100, macd = BULLISH, volume_spike = True, price_ok = True
→ Stage1 Score = 100 × 0.30 + 100 × 0.25 + 100 × 0.20 + 100 × 0.15 + 100 × 0.10 = 100

# Example 2: Good Score
ma_score = 75, rsi_score = 80, macd = BULLISH, volume_spike = True, price_ok = True
→ Stage1 Score = 75 × 0.30 + 80 × 0.25 + 100 × 0.20 + 100 × 0.15 + 100 × 0.10 = 87.5

# Example 3: Borderline Score
ma_score = 75, rsi_score = 60, macd = BULLISH, volume_spike = False, price_ok = True
→ Stage1 Score = 75 × 0.30 + 60 × 0.25 + 100 × 0.20 + 0 × 0.15 + 100 × 0.10 = 67.5
```

---

## 🗂️ 데이터베이스 저장

### filter_cache_stage1 테이블

**저장 항목**:
```sql
INSERT OR REPLACE INTO filter_cache_stage1 (
    ticker,                 -- 종목 코드
    region,                 -- 시장 지역 (KR, US, etc.)
    ma5, ma20, ma60,        -- 이동평균선 값
    rsi_14,                 -- RSI 값
    current_price_krw,      -- 현재가 (KRW)
    week_52_high_krw,       -- 52주 최고가 (KRW)
    volume_3d_avg,          -- 3일 평균 거래량
    volume_10d_avg,         -- 10일 평균 거래량
    filter_date,            -- 필터링 실행 날짜
    data_start_date,        -- OHLCV 데이터 시작 날짜
    data_end_date,          -- OHLCV 데이터 종료 날짜
    stage1_passed,          -- Stage 1 통과 여부 (1 = 통과)
    filter_reason           -- 실패 이유 (NULL if passed)
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**캐싱 전략**:
- **TTL (Time To Live)**:
  - 장중: 1시간
  - 장 마감 후: 24시간
- **갱신 조건**:
  - TTL 만료 시 자동 갱신
  - `--force-refresh` 플래그로 강제 갱신

**캐시 로딩**:
```python
def _load_from_cache() -> Optional[List[Dict]]:
    """
    Stage 1 캐시 로딩 (TTL 확인)

    Returns:
        캐시가 유효하면 종목 리스트, 아니면 None
    """
    # TTL 확인
    ttl_hours = 1 if is_market_hours() else 24
    age_hours = (now - last_update).total_seconds() / 3600

    if age_hours > ttl_hours:
        return None  # 캐시 만료

    # 캐시 로드
    cursor.execute("""
        SELECT * FROM filter_cache_stage1
        WHERE region = ? AND stage1_passed = 1
        ORDER BY stage1_score DESC
    """, (region,))

    return [dict(row) for row in cursor.fetchall()]
```

---

## 🔄 실행 흐름

### 전체 프로세스

```python
def run_stage1_filter(force_refresh: bool = False) -> List[Dict]:
    """
    Stage 1 Technical Pre-screen 실행

    Step 1: 캐시 확인 (TTL 검증)
    Step 2: Stage 0 결과 로딩 (filter_cache_stage0)
    Step 3: 각 종목별 OHLCV 데이터 로딩
    Step 4: 5개 기술 필터 적용
    Step 5: Stage 1 점수 계산
    Step 6: filter_cache_stage1에 저장
    Step 7: filter_execution_log에 실행 로그 기록

    Returns:
        통과한 종목 리스트 (stage1_passed = 1)
    """
    # Step 1: Cache check
    if not force_refresh:
        cached = _load_from_cache()
        if cached:
            return cached

    # Step 2: Load Stage 0 results
    stage0_tickers = _load_stage0_results()  # ~600 tickers

    # Step 3-6: Apply filters
    filtered_tickers = []
    for ticker_data in stage0_tickers:
        # Load OHLCV data
        ohlcv_data = _load_ohlcv_data(ticker)

        if len(ohlcv_data) < 250:
            continue  # Skip: insufficient data

        # Apply 5 technical filters
        filter_result = _apply_technical_filters(ticker, ticker_data, ohlcv_data)

        if filter_result['passed']:
            filtered_tickers.append(ticker_data)

    # Step 7: Save to cache
    _save_to_cache(filtered_tickers)

    # Step 8: Log execution
    _log_filter_execution(len(stage0_tickers), len(filtered_tickers), execution_time_ms)

    return filtered_tickers
```

### 필터 적용 흐름도

```
Stage 0 Results (600 tickers)
         ↓
[Load OHLCV Data (250 days)]
         ↓
[Filter 1: MA Alignment] → FAIL → ❌ 종목 탈락
         ↓ PASS
[Filter 2: RSI Range (30-70)] → FAIL → ❌ 종목 탈락
         ↓ PASS
[Filter 3: MACD Bullish] → FAIL → ❌ 종목 탈락
         ↓ PASS
[Filter 4: Volume Spike] → FAIL → ❌ 종목 탈락
         ↓ PASS
[Filter 5: Price > MA20] → FAIL → ❌ 종목 탈락
         ↓ PASS
[Calculate Stage 1 Score (0-100)]
         ↓
filter_cache_stage1 (180 tickers)
```

---

## 📊 필터링 통계 (예상)

| 단계 | 종목 수 | 감소율 | 주요 실패 사유 |
|------|---------|--------|----------------|
| **Stage 0 입력** | 600개 | - | - |
| **Filter 1 (MA Alignment)** | 480개 | 20% | MA 역배열, 횡보 추세 |
| **Filter 2 (RSI Range)** | 384개 | 20% | 과매수 (RSI>70), 과매도 (RSI<30) |
| **Filter 3 (MACD Signal)** | 288개 | 25% | MACD 약세 신호 |
| **Filter 4 (Volume Spike)** | 216개 | 25% | 거래량 부족 |
| **Filter 5 (Price > MA20)** | 180개 | 17% | 단기 지지선 이탈 |
| **최종 출력** | **180개** | **70% 감소** | - |

**통과율**: ~30% (600 → 180개)

---

## 🛠️ CLI 사용법

### 기본 실행
```bash
python3 modules/stock_pre_filter.py --region KR
```

### 강제 갱신 (캐시 무시)
```bash
python3 modules/stock_pre_filter.py --region KR --force-refresh
```

### 디버그 모드
```bash
python3 modules/stock_pre_filter.py --region KR --debug
```

### 출력 예시
```
================================================================================
[Stage 1: Technical Pre-Filter]
================================================================================
✅ Stage 0 결과 로드: 600개 종목
🔍 Stage 1 필터 시작: 600개 종목
📊 Stage 1 필터링 완료: 600 → 180개 종목 (통과: 180, 실패: 420, 83ms)

============================================================
✅ Stage 1 필터링 완료: 180개 종목 (region=KR)
============================================================

[Stage 1 점수 상위 10개 종목]
 1. 005930 삼성전자         Stage1=100 (MA=100, RSI=90, MACD=BULLISH, Vol=✅)
 2. 000660 SK하이닉스       Stage1=95  (MA=100, RSI=85, MACD=BULLISH, Vol=✅)
 3. 035420 NAVER           Stage1=92  (MA=100, RSI=80, MACD=BULLISH, Vol=✅)
 4. 005380 현대차           Stage1=88  (MA=75,  RSI=90, MACD=BULLISH, Vol=✅)
 5. 051910 LG화학           Stage1=87  (MA=75,  RSI=85, MACD=BULLISH, Vol=✅)
 ...

💾 DB 저장 위치: data/spock_local.db
📊 Stage 1 캐시 테이블: filter_cache_stage1
```

---

## 🔧 설정 파일 (kr_filter_config.yaml)

```yaml
region: KR
market_name: "Korea (KOSPI/KOSDAQ)"
currency: KRW

# Stage 1 필터 설정
stage1_filters:
  # RSI 범위
  rsi_min: 30           # RSI 하한 (과매도 기준)
  rsi_max: 70           # RSI 상한 (과매수 기준)

  # 거래량 급증 비율
  volume_spike_ratio: 1.5   # 20일 평균 대비 150% 이상

  # 데이터 완전성 검증
  data_completeness:
    min_ohlcv_days: 250     # 최소 OHLCV 데이터 일수
    max_gap_days: 60        # 최대 허용 공백 일수
    required_continuity: false  # 연속성 검증 여부 (false = 검증 안 함)
```

---

## 📚 참고 자료

### Weinstein Stage 2 Theory
- **Stage 1**: 바닥권 (Accumulation)
- **Stage 2**: 상승 추세 (Markup) ← **필터 타겟**
- **Stage 3**: 고점권 (Distribution)
- **Stage 4**: 하락 추세 (Markdown)

**Stage 2 핵심 조건**:
1. MA150 > MA200
2. MA50 > MA150
3. Price > MA50
4. MA50 기울기 > 0 (상승 중)

### RSI (Relative Strength Index)
- **Range**: 0-100
- **과매수**: RSI > 70
- **과매도**: RSI < 30
- **중립**: 30 ≤ RSI ≤ 70

### MACD (Moving Average Convergence Divergence)
- **MACD Line**: EMA(12) - EMA(26)
- **Signal Line**: EMA(MACD, 9)
- **Histogram**: MACD - Signal
- **Bullish Crossover**: MACD > Signal AND Histogram > 0

---

## 🚀 다음 단계

Stage 1-B 통과 후:
1. **Stage 2: LayeredScoringEngine** (100-point scoring system)
   - Layer 1 (Macro): Market regime, volume profile, price action (25 pts)
   - Layer 2 (Structural): Stage analysis, MA alignment, relative strength (45 pts)
   - Layer 3 (Micro): Pattern recognition, volume spike, momentum (30 pts)

2. **Stage 3: Kelly Position Sizing**
   - Pattern-based win rate mapping
   - Kelly Formula position calculation
   - Half Kelly conservative adjustment

3. **Stage 4: Trade Execution**
   - KIS API order execution
   - Tick size compliance
   - Portfolio sync

---

## 📝 버전 정보

- **Version**: 1.0.0
- **Author**: Spock Trading System
- **Last Updated**: 2025-10-16
- **Dependencies**: LayeredScoringEngine (Makenaide 95% reusable)
