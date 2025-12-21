# Stock GPT Analyzer Design Specification

## Document Information
- **Version**: 1.0
- **Created**: 2025-10-15
- **Status**: Design Complete
- **Module**: `modules/stock_gpt_analyzer.py`

---

## 1. Executive Summary

### 1.1 Purpose
GPT-4 기반 차트 패턴 분석 모듈로, Weinstein Stage 2 이론과 Mark Minervini VCP 패턴을 자동으로 감지하여 매수 결정의 정확도를 높입니다.

### 1.2 Key Features
- ✅ **VCP (Volatility Contraction Pattern)** 감지
- ✅ **Cup & Handle** 패턴 감지
- ✅ **Stage 2 Breakout** 검증
- ✅ **3단계 캐싱 시스템** (메모리 → DB(72시간) → API)
- ✅ **비용 최적화** (GPT-4o-mini: $0.15/1M input tokens)
- ✅ **Kelly Calculator 연동** (position sizing adjustment)

### 1.3 Integration Point
```
IntegratedScoringSystem (70+ points)
→ StockGPTAnalyzer (pattern confidence)
→ KellyCalculator (GPT adjustment × position%)
→ KISTradingEngine (order execution)
```

---

## 2. Architecture Design

### 2.1 System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   StockGPTAnalyzer                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐                 │
│  │  CostManager    │  │  CacheManager    │                 │
│  │  - Daily budget │  │  - Memory cache  │                 │
│  │  - Usage track  │  │  - DB cache 72h  │                 │
│  └─────────────────┘  └──────────────────┘                 │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │            Pattern Detection Engine               │      │
│  │  - VCP Analysis (volatility contraction)         │      │
│  │  - Cup & Handle (base depth, handle duration)    │      │
│  │  - Stage 2 Validation (MA alignment, volume)     │      │
│  └──────────────────────────────────────────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────┐      │
│  │         OpenAI GPT-4o-mini Integration            │      │
│  │  - Structured prompt engineering                  │      │
│  │  - JSON response parsing                          │      │
│  │  - Retry logic (max 2 attempts)                  │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Database Schema

```sql
CREATE TABLE IF NOT EXISTS gpt_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    analysis_date TEXT NOT NULL,

    -- VCP Pattern Analysis
    vcp_detected BOOLEAN DEFAULT 0,
    vcp_confidence REAL DEFAULT 0.0,
    vcp_stage INTEGER DEFAULT 0,              -- 1-4 contraction stages
    vcp_volatility_ratio REAL DEFAULT 0.0,    -- Volatility reduction %
    vcp_reasoning TEXT DEFAULT '',

    -- Cup & Handle Pattern Analysis
    cup_handle_detected BOOLEAN DEFAULT 0,
    cup_handle_confidence REAL DEFAULT 0.0,
    cup_depth_ratio REAL DEFAULT 0.0,         -- Cup depth as % of base
    handle_duration_days INTEGER DEFAULT 0,   -- Handle formation days
    cup_handle_reasoning TEXT DEFAULT '',

    -- Stage 2 Breakout Validation
    stage2_confirmed BOOLEAN DEFAULT 0,
    stage2_confidence REAL DEFAULT 0.0,
    stage2_ma_alignment BOOLEAN DEFAULT 0,    -- MA5 > MA20 > MA60 > MA120
    stage2_volume_surge BOOLEAN DEFAULT 0,    -- Volume > 1.5x avg
    stage2_reasoning TEXT DEFAULT '',

    -- GPT Recommendation
    gpt_recommendation TEXT DEFAULT 'HOLD',   -- STRONG_BUY/BUY/HOLD/AVOID
    gpt_confidence REAL DEFAULT 0.0,          -- 0.0-1.0
    gpt_reasoning TEXT DEFAULT '',
    position_adjustment REAL DEFAULT 1.0,     -- Kelly multiplier (0.5-1.5)

    -- Cost Tracking
    api_cost_usd REAL DEFAULT 0.0,
    processing_time_ms INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),

    UNIQUE(ticker, analysis_date)
);

CREATE INDEX idx_gpt_ticker ON gpt_analysis(ticker);
CREATE INDEX idx_gpt_date ON gpt_analysis(analysis_date);
CREATE INDEX idx_gpt_recommendation ON gpt_analysis(gpt_recommendation);
```

---

## 3. Core Data Structures

### 3.1 Pattern Analysis Results

```python
@dataclass
class VCPAnalysis:
    """VCP Pattern Detection Result"""
    detected: bool
    confidence: float  # 0.0-1.0
    stage: int  # 1-4 contraction stages
    volatility_ratio: float  # Volatility reduction %
    reasoning: str

@dataclass
class CupHandleAnalysis:
    """Cup & Handle Pattern Detection Result"""
    detected: bool
    confidence: float  # 0.0-1.0
    cup_depth_ratio: float  # Cup depth as % of base
    handle_duration_days: int  # Handle formation days
    reasoning: str

@dataclass
class Stage2Analysis:
    """Stage 2 Breakout Validation Result"""
    confirmed: bool
    confidence: float  # 0.0-1.0
    ma_alignment: bool  # MA5 > MA20 > MA60 > MA120
    volume_surge: bool  # Volume > 1.5x average
    reasoning: str

@dataclass
class GPTAnalysisResult:
    """Comprehensive GPT Analysis Result"""
    ticker: str
    analysis_date: str
    vcp_analysis: VCPAnalysis
    cup_handle_analysis: CupHandleAnalysis
    stage2_analysis: Stage2Analysis
    recommendation: GPTRecommendation  # STRONG_BUY/BUY/HOLD/AVOID
    confidence: float  # 0.0-1.0
    reasoning: str
    position_adjustment: float  # Kelly multiplier (0.5-1.5)
    api_cost_usd: float
    processing_time_ms: int
```

### 3.2 Recommendation Enum

```python
class GPTRecommendation(Enum):
    """GPT Recommendation Levels"""
    STRONG_BUY = "STRONG_BUY"  # Position adjustment: 1.3-1.5x
    BUY = "BUY"                # Position adjustment: 1.0-1.2x
    HOLD = "HOLD"              # Position adjustment: 0.8-1.0x
    AVOID = "AVOID"            # Position adjustment: 0.5-0.7x
```

---

## 4. API Integration

### 4.1 OpenAI GPT-4o-mini Configuration

```python
OPENAI_CONFIG = {
    "model": "gpt-4o-mini",
    "temperature": 0.3,  # Low temperature for consistent analysis
    "max_tokens": 1000,
    "response_format": {"type": "json_object"},

    # Cost optimization
    "pricing": {
        "input": 0.00015,   # $0.15/1M tokens
        "output": 0.0006    # $0.60/1M tokens
    },

    # Daily limits
    "daily_budget_usd": 0.50,  # $0.50/day = $15/month
    "max_requests_per_day": 100
}
```

### 4.2 GPT Prompt Engineering

```python
SYSTEM_PROMPT = """You are an expert stock chart pattern analyst specializing in:
1. Weinstein Stage 2 Theory (uptrend identification)
2. Mark Minervini VCP (Volatility Contraction Pattern)
3. William O'Neil Cup & Handle pattern

Analyze the provided OHLCV data and identify patterns with confidence scores.
Respond ONLY in JSON format with the following structure:

{
    "vcp_analysis": {
        "detected": boolean,
        "confidence": 0.0-1.0,
        "stage": 1-4,
        "volatility_ratio": 0.0-1.0,
        "reasoning": "string"
    },
    "cup_handle_analysis": {
        "detected": boolean,
        "confidence": 0.0-1.0,
        "cup_depth_ratio": 0.0-1.0,
        "handle_duration_days": integer,
        "reasoning": "string"
    },
    "stage2_analysis": {
        "confirmed": boolean,
        "confidence": 0.0-1.0,
        "ma_alignment": boolean,
        "volume_surge": boolean,
        "reasoning": "string"
    },
    "recommendation": "STRONG_BUY|BUY|HOLD|AVOID",
    "confidence": 0.0-1.0,
    "reasoning": "string",
    "position_adjustment": 0.5-1.5
}
"""

USER_PROMPT_TEMPLATE = """
Analyze {ticker} for chart patterns:

Price Information:
- Current: {current_price:,.0f} KRW
- MA20: {ma20:,.0f} KRW ({ma20_pct:+.1f}%)
- MA60: {ma60:,.0f} KRW ({ma60_pct:+.1f}%)
- 30D High: {high_30d:,.0f} KRW ({high_pct:+.1f}%)
- 30D Low: {low_30d:,.0f} KRW ({low_pct:+.1f}%)

Volume:
- Current: {volume_current:,.0f}
- Average: {volume_avg:,.0f}
- Ratio: {volume_ratio:.1f}x

Volatility: {volatility:.1f}%

Recent 20-Day Price Movement:
{price_history}

Identify VCP, Cup & Handle, and Stage 2 breakout patterns.
"""
```

---

## 5. Cost Management

### 5.1 Budget Control System

```python
class CostManager:
    """GPT API Cost Management"""

    def __init__(self, daily_limit: float = 0.50):
        self.daily_limit = daily_limit  # $0.50/day
        self.gpt_4o_mini_input_cost = 0.00015  # $0.15/1M tokens
        self.gpt_4o_mini_output_cost = 0.0006  # $0.60/1M tokens

    def estimate_cost(self, text_length: int) -> float:
        """Estimate API call cost"""
        # Average 2.5 tokens per character (Korean/English mixed)
        tokens = text_length * 2.5
        input_cost = (tokens / 1_000_000) * self.gpt_4o_mini_input_cost

        # Output tokens ~20% of input
        output_tokens = tokens * 0.2
        output_cost = (output_tokens / 1_000_000) * self.gpt_4o_mini_output_cost

        return input_cost + output_cost

    def get_daily_usage(self) -> float:
        """Query today's total API cost"""
        # Query from gpt_analysis table
        today = datetime.now().strftime('%Y-%m-%d')
        query = """
            SELECT COALESCE(SUM(api_cost_usd), 0)
            FROM gpt_analysis
            WHERE DATE(created_at) = ?
        """
        # Return daily total

    def check_budget_available(self, estimated_cost: float) -> bool:
        """Verify budget before API call"""
        daily_usage = self.get_daily_usage()
        remaining = self.daily_limit - daily_usage
        return estimated_cost <= remaining
```

### 5.2 Intelligent Filtering

```python
def should_analyze_with_gpt(self, ticker: str, technical_score: float) -> bool:
    """Determine if GPT analysis is warranted"""

    # Rule 1: Technical score must be ≥70 (IntegratedScoringSystem)
    if technical_score < 70.0:
        logger.info(f"⏭️ {ticker}: Score {technical_score} < 70, skip GPT")
        return False

    # Rule 2: Check daily budget
    estimated_cost = self.cost_manager.estimate_cost(text_length=2000)
    if not self.cost_manager.check_budget_available(estimated_cost):
        logger.warning(f"💰 {ticker}: Daily budget exceeded")
        return False

    # Rule 3: Check cache (72-hour validity)
    cached_result = self.cache_manager.get_cached_analysis(ticker)
    if cached_result:
        logger.info(f"💾 {ticker}: Cache hit, skip API call")
        return False

    return True
```

---

## 6. Caching Strategy

### 6.1 3-Tier Cache System

```python
class CacheManager:
    """3-Tier Caching: Memory → DB(72h) → API"""

    def __init__(self, db_path: str):
        self.memory_cache: Dict[str, GPTAnalysisResult] = {}
        self.db_path = db_path
        self.cache_ttl_hours = 72  # 3 days validity

    def get_cached_analysis(self, ticker: str) -> Optional[GPTAnalysisResult]:
        """Retrieve from cache (Memory → DB)"""

        # Level 1: Memory cache (fastest)
        cache_key = f"{ticker}_{datetime.now().strftime('%Y-%m-%d')}"
        if cache_key in self.memory_cache:
            logger.info(f"💨 {ticker}: Memory cache hit")
            return self.memory_cache[cache_key]

        # Level 2: Database cache (72-hour validity)
        cutoff_time = datetime.now() - timedelta(hours=self.cache_ttl_hours)
        query = """
            SELECT * FROM gpt_analysis
            WHERE ticker = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
        """
        result = self.db.query(query, (ticker, cutoff_time))

        if result:
            logger.info(f"💾 {ticker}: DB cache hit")
            parsed_result = self._parse_db_row(result)
            self.memory_cache[cache_key] = parsed_result
            return parsed_result

        # Level 3: No cache, API call required
        logger.debug(f"🔍 {ticker}: Cache miss, API call needed")
        return None
```

---

## 7. Integration with Kelly Calculator

### 7.1 Position Sizing Adjustment

```python
# In kelly_calculator.py
@dataclass
class KellyResult:
    # ... existing fields ...

    # GPT Adjustment (optional)
    gpt_confidence: Optional[float] = None
    gpt_recommendation: Optional[str] = None
    gpt_adjustment: float = 1.0  # Multiplier: 0.5-1.5
    final_position_pct: float = None

def apply_gpt_adjustment(self, kelly_result: KellyResult,
                        gpt_result: GPTAnalysisResult) -> KellyResult:
    """Apply GPT confidence to position size"""

    # Extract GPT adjustment multiplier
    kelly_result.gpt_confidence = gpt_result.confidence
    kelly_result.gpt_recommendation = gpt_result.recommendation.value
    kelly_result.gpt_adjustment = gpt_result.position_adjustment

    # Calculate final position
    technical_position = kelly_result.technical_position_pct
    kelly_result.final_position_pct = technical_position * gpt_result.position_adjustment

    # Apply bounds (1%-15% per position)
    kelly_result.final_position_pct = max(1.0, min(15.0, kelly_result.final_position_pct))

    logger.info(
        f"🎯 Position Sizing: {technical_position:.1f}% "
        f"× {gpt_result.position_adjustment:.2f} "
        f"= {kelly_result.final_position_pct:.1f}%"
    )

    return kelly_result
```

### 7.2 Recommendation to Multiplier Mapping

```python
GPT_ADJUSTMENT_MAP = {
    GPTRecommendation.STRONG_BUY: (1.3, 1.5),  # Increase 30-50%
    GPTRecommendation.BUY: (1.1, 1.2),         # Increase 10-20%
    GPTRecommendation.HOLD: (0.9, 1.0),        # Neutral to slight reduction
    GPTRecommendation.AVOID: (0.5, 0.7)        # Reduce 30-50%
}

def calculate_position_adjustment(self,
                                 recommendation: GPTRecommendation,
                                 confidence: float) -> float:
    """Calculate Kelly multiplier based on GPT recommendation"""

    min_mult, max_mult = GPT_ADJUSTMENT_MAP[recommendation]

    # Interpolate based on confidence
    adjustment = min_mult + (max_mult - min_mult) * confidence

    return round(adjustment, 2)
```

---

## 8. Error Handling & Retry Logic

### 8.1 API Call Resilience

```python
def _call_openai_api(self, chart_text: str, ticker: str,
                     max_retries: int = 2) -> GPTAnalysisResult:
    """OpenAI API call with retry logic"""

    last_exception = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"🔄 {ticker}: API attempt {attempt + 1}/{max_retries}")

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": chart_text}
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            # Parse JSON response
            result_json = json.loads(response.choices[0].message.content)

            # Calculate cost
            usage = response.usage
            cost = self._calculate_api_cost(usage.prompt_tokens,
                                           usage.completion_tokens)

            logger.info(f"✅ {ticker}: API success (${cost:.6f})")
            return self._parse_gpt_response(result_json, ticker, cost)

        except openai.RateLimitError as e:
            logger.warning(f"⏳ {ticker}: Rate limit, wait 5s")
            time.sleep(5)
            last_exception = e

        except openai.APIError as e:
            logger.error(f"❌ {ticker}: API error - {e}")
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff

        except json.JSONDecodeError as e:
            logger.error(f"❌ {ticker}: JSON parse error - {e}")
            last_exception = e
            break  # No retry on parse errors

    # All retries failed
    logger.error(f"❌ {ticker}: API failed after {max_retries} attempts")
    raise last_exception
```

---

## 9. Usage Example

### 9.1 Basic Usage

```python
from modules.stock_gpt_analyzer import StockGPTAnalyzer
from modules.integrated_scoring_system import IntegratedScoringSystem

# Initialize
gpt_analyzer = StockGPTAnalyzer(
    db_path="data/spock_local.db",
    enable_gpt=True,
    daily_cost_limit=0.50
)

# Stage 1: Technical scoring
scoring_system = IntegratedScoringSystem("data/spock_local.db")
score = scoring_system.calculate_score("005930")  # Samsung Electronics

if score >= 70.0:
    # Stage 2: GPT pattern analysis
    gpt_result = gpt_analyzer.analyze_ticker("005930")

    if gpt_result:
        print(f"VCP Detected: {gpt_result.vcp_analysis.detected}")
        print(f"Confidence: {gpt_result.confidence:.2f}")
        print(f"Recommendation: {gpt_result.recommendation.value}")
        print(f"Position Adjustment: {gpt_result.position_adjustment:.2f}x")
```

### 9.2 Batch Analysis

```python
def analyze_top_candidates(self, tickers: List[str],
                          min_score: float = 70.0) -> List[GPTAnalysisResult]:
    """Analyze multiple tickers with budget control"""

    results = []
    daily_usage = self.cost_manager.get_daily_usage()

    for ticker in tickers:
        # Check budget before each analysis
        if daily_usage >= self.cost_manager.daily_limit:
            logger.warning(f"💰 Daily budget exhausted at ${daily_usage:.2f}")
            break

        # Get technical score
        score = self.scoring_system.calculate_score(ticker)

        if score >= min_score:
            gpt_result = self.analyze_ticker(ticker)
            if gpt_result:
                results.append(gpt_result)
                daily_usage += gpt_result.api_cost_usd

    logger.info(f"📊 Analyzed {len(results)} tickers, spent ${daily_usage:.4f}")
    return results
```

---

## 10. Performance Metrics

### 10.1 Expected Performance

```python
PERFORMANCE_TARGETS = {
    # API Performance
    "avg_response_time_ms": 2000,  # 2 seconds per ticker
    "max_response_time_ms": 5000,  # 5 seconds timeout

    # Cost Efficiency
    "avg_cost_per_analysis": 0.005,  # $0.005 per ticker
    "daily_analysis_capacity": 100,   # 100 tickers @ $0.50/day

    # Cache Hit Rate
    "target_cache_hit_rate": 0.70,   # 70% cache hits
    "actual_api_calls_per_day": 30,  # ~30 new analyses/day

    # Accuracy (vs manual analysis)
    "pattern_detection_accuracy": 0.85,  # 85% agreement
    "recommendation_precision": 0.80      # 80% precision
}
```

### 10.2 Cost Breakdown

```python
# Monthly Cost Estimation
MONTHLY_COST_ESTIMATE = {
    "daily_budget": 0.50,           # $0.50/day
    "monthly_budget": 15.00,        # $15/month
    "avg_analyses_per_day": 30,    # 30 new analyses
    "avg_cost_per_analysis": 0.005, # $0.005/analysis
    "actual_daily_cost": 0.15,      # 30 × $0.005 = $0.15
    "actual_monthly_cost": 4.50,    # $0.15 × 30 days = $4.50
    "budget_utilization": 0.30      # 30% of budget
}
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/test_stock_gpt_analyzer.py

def test_vcp_pattern_detection():
    """Test VCP pattern detection accuracy"""
    # Load known VCP examples
    # Verify detection and confidence scores

def test_cup_handle_detection():
    """Test Cup & Handle pattern detection"""
    # Load known Cup & Handle examples
    # Verify detection and confidence scores

def test_cache_hit_ratio():
    """Verify cache system effectiveness"""
    # Analyze same ticker twice
    # Verify second call uses cache

def test_budget_enforcement():
    """Verify daily budget limits"""
    # Attempt to exceed daily budget
    # Verify API calls are blocked

def test_position_adjustment_calculation():
    """Verify Kelly multiplier calculation"""
    # Test all recommendation levels
    # Verify adjustment ranges (0.5-1.5)
```

### 11.2 Integration Tests

```python
# tests/test_gpt_kelly_integration.py

def test_end_to_end_analysis():
    """Test complete pipeline: Scoring → GPT → Kelly"""
    ticker = "005930"

    # Stage 1: Technical scoring
    score = scoring_system.calculate_score(ticker)
    assert score >= 70.0

    # Stage 2: GPT analysis
    gpt_result = gpt_analyzer.analyze_ticker(ticker)
    assert gpt_result is not None
    assert 0.0 <= gpt_result.confidence <= 1.0

    # Stage 3: Kelly calculation with GPT adjustment
    kelly_result = kelly_calculator.calculate_position(
        ticker=ticker,
        quality_score=score,
        gpt_result=gpt_result
    )
    assert 1.0 <= kelly_result.final_position_pct <= 15.0
```

---

## 12. Monitoring & Observability

### 12.1 Key Metrics to Track

```python
MONITORING_METRICS = {
    # API Health
    "api_success_rate": "COUNT(success) / COUNT(total_calls)",
    "api_avg_latency_ms": "AVG(processing_time_ms)",
    "api_timeout_rate": "COUNT(timeouts) / COUNT(total_calls)",

    # Cost Tracking
    "daily_api_cost": "SUM(api_cost_usd WHERE DATE = today)",
    "monthly_api_cost": "SUM(api_cost_usd WHERE MONTH = current)",
    "cost_per_recommendation": "SUM(api_cost_usd) / COUNT(recommendations)",

    # Cache Efficiency
    "cache_hit_rate": "COUNT(cache_hits) / COUNT(total_requests)",
    "avg_cache_age_hours": "AVG(NOW() - created_at)",

    # Pattern Detection
    "vcp_detection_rate": "COUNT(vcp_detected=1) / COUNT(total)",
    "cup_handle_detection_rate": "COUNT(cup_handle_detected=1) / COUNT(total)",
    "strong_buy_rate": "COUNT(recommendation='STRONG_BUY') / COUNT(total)"
}
```

### 12.2 Logging Strategy

```python
# Cost tracking log
logger.info(
    f"💰 GPT Analysis: {ticker} | "
    f"Cost: ${cost:.6f} | "
    f"Daily Total: ${daily_usage:.4f}/{daily_limit:.2f} | "
    f"Remaining: ${daily_limit - daily_usage:.4f}"
)

# Pattern detection log
logger.info(
    f"🎯 Pattern Detection: {ticker} | "
    f"VCP: {vcp_detected} ({vcp_confidence:.0%}) | "
    f"Cup&Handle: {cup_detected} ({cup_confidence:.0%}) | "
    f"Recommendation: {recommendation}"
)

# Performance log
logger.info(
    f"⏱️ Performance: {ticker} | "
    f"Processing: {processing_time_ms}ms | "
    f"Cache: {'HIT' if cached else 'MISS'}"
)
```

---

## 13. Implementation Checklist

### 13.1 Module Development

- [ ] Copy `makenaide/gpt_analyzer.py` → `modules/stock_gpt_analyzer.py`
- [ ] Modify database schema for stock-specific fields
- [ ] Update prompt engineering for Weinstein Stage 2
- [ ] Implement Stage 2 breakout validation
- [ ] Add position adjustment calculation
- [ ] Integrate with KellyCalculator

### 13.2 Testing

- [ ] Unit tests for pattern detection
- [ ] Cache system validation
- [ ] Budget enforcement tests
- [ ] Integration tests with Kelly Calculator
- [ ] End-to-end pipeline tests

### 13.3 Documentation

- [ ] API reference documentation
- [ ] Usage examples and best practices
- [ ] Cost optimization guide
- [ ] Troubleshooting guide

### 13.4 Deployment

- [ ] Add to `spock.py` main orchestrator
- [ ] Configure OpenAI API key in `.env`
- [ ] Set daily budget limits
- [ ] Enable monitoring and alerts

---

## 14. Future Enhancements

### 14.1 Pattern Library Expansion
- **Darvas Box** detection
- **Double Bottom** pattern
- **Flag and Pennant** formations
- **Inverse Head & Shoulders**

### 14.2 Advanced Features
- **Multi-timeframe analysis** (daily + weekly)
- **Sector rotation signals** (industry group RS)
- **Market regime detection** (bull/bear/sideways)
- **Correlation analysis** (with market index)

### 14.3 Cost Optimization
- **Adaptive caching** (extend to 7 days for stable patterns)
- **Batch API calls** (analyze 5 tickers per request)
- **Fallback models** (GPT-3.5-turbo for low-priority)
- **Local LLM option** (Llama 3 for cost-free operation)

---

## 15. References

### 15.1 Trading Strategies
- **Stan Weinstein** - "Secrets for Profiting in Bull and Bear Markets"
- **Mark Minervini** - "Trade Like a Stock Market Wizard"
- **William O'Neil** - "How to Make Money in Stocks"

### 15.2 Technical Resources
- OpenAI GPT-4o-mini API Documentation
- Kelly Criterion Position Sizing Theory
- Chart Pattern Recognition Studies

### 15.3 Related Modules
- [integrated_scoring_system.py](../modules/integrated_scoring_system.py)
- [kelly_calculator.py](../modules/kelly_calculator.py)
- [kis_trading_engine.py](../modules/kis_trading_engine.py)

---

**End of Design Specification**
