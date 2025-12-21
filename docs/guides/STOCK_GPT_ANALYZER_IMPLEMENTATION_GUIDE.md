# Stock GPT Analyzer Implementation Guide

## Quick Start Guide

### Step 1: Copy Base Module from Makenaide

```bash
# Copy the proven GPT analyzer from Makenaide
cp ~/makenaide/gpt_analyzer.py modules/stock_gpt_analyzer.py

# Verify file exists
ls -la modules/stock_gpt_analyzer.py
```

---

### Step 2: Modify for Stock-Specific Patterns

#### 2.1 Update Imports and Database Path

```python
# In modules/stock_gpt_analyzer.py

# Change database path reference
# FROM: self.db_path = "./makenaide_local.db"
# TO: self.db_path = "./data/spock_local.db"

class StockGPTAnalyzer:  # Renamed from GPTPatternAnalyzer
    def __init__(self,
                 db_path: str = "./data/spock_local.db",  # Stock-specific path
                 api_key: str = None,
                 enable_gpt: bool = True,
                 daily_cost_limit: float = 0.50):
        # ... rest of initialization
```

#### 2.2 Add Stage 2 Breakout Analysis

```python
# Add new dataclass for Stage 2 analysis
@dataclass
class Stage2Analysis:
    """Stage 2 Breakout Validation Result"""
    confirmed: bool
    confidence: float  # 0.0-1.0
    ma_alignment: bool  # MA5 > MA20 > MA60 > MA120
    volume_surge: bool  # Volume > 1.5x average
    reasoning: str

# Update GPTAnalysisResult to include Stage 2
@dataclass
class GPTAnalysisResult:
    ticker: str
    analysis_date: str
    vcp_analysis: VCPAnalysis
    cup_handle_analysis: CupHandleAnalysis
    stage2_analysis: Stage2Analysis  # NEW: Stock-specific field
    recommendation: GPTRecommendation
    confidence: float
    reasoning: str
    position_adjustment: float  # NEW: For Kelly Calculator
    api_cost_usd: float
    processing_time_ms: int
```

#### 2.3 Update Database Schema

```python
def init_database(self):
    """Create gpt_analysis table with stock-specific fields"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS gpt_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        analysis_date TEXT NOT NULL,

        -- VCP Pattern Analysis
        vcp_detected BOOLEAN DEFAULT 0,
        vcp_confidence REAL DEFAULT 0.0,
        vcp_stage INTEGER DEFAULT 0,
        vcp_volatility_ratio REAL DEFAULT 0.0,
        vcp_reasoning TEXT DEFAULT '',

        -- Cup & Handle Pattern Analysis
        cup_handle_detected BOOLEAN DEFAULT 0,
        cup_handle_confidence REAL DEFAULT 0.0,
        cup_depth_ratio REAL DEFAULT 0.0,
        handle_duration_days INTEGER DEFAULT 0,
        cup_handle_reasoning TEXT DEFAULT '',

        -- Stage 2 Breakout Validation (NEW for stocks)
        stage2_confirmed BOOLEAN DEFAULT 0,
        stage2_confidence REAL DEFAULT 0.0,
        stage2_ma_alignment BOOLEAN DEFAULT 0,
        stage2_volume_surge BOOLEAN DEFAULT 0,
        stage2_reasoning TEXT DEFAULT '',

        -- GPT Recommendation
        gpt_recommendation TEXT DEFAULT 'HOLD',
        gpt_confidence REAL DEFAULT 0.0,
        gpt_reasoning TEXT DEFAULT '',
        position_adjustment REAL DEFAULT 1.0,  -- NEW: Kelly multiplier

        -- Cost Tracking
        api_cost_usd REAL DEFAULT 0.0,
        processing_time_ms INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),

        UNIQUE(ticker, analysis_date)
    );
    """

    cursor.execute(create_table_sql)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_ticker ON gpt_analysis(ticker);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_date ON gpt_analysis(analysis_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_recommendation ON gpt_analysis(gpt_recommendation);")
```

#### 2.4 Update GPT Prompt for Stock Analysis

```python
# Update SYSTEM_PROMPT for stock-specific patterns
SYSTEM_PROMPT = """You are an expert stock chart pattern analyst specializing in:
1. Weinstein Stage 2 Theory - Uptrend identification with MA alignment
2. Mark Minervini VCP (Volatility Contraction Pattern) - 3-4 stage contraction
3. William O'Neil Cup & Handle - Base depth 12-33%, handle 1-4 weeks

Analyze Korean stock market (KOSPI/KOSDAQ) OHLCV data and identify:
- VCP patterns with volatility contraction stages
- Cup & Handle formations with proper base and handle
- Stage 2 breakout confirmation (MA alignment + volume surge)

Respond ONLY in JSON format:
{
    "vcp_analysis": {
        "detected": boolean,
        "confidence": 0.0-1.0,
        "stage": 1-4,
        "volatility_ratio": 0.0-1.0,
        "reasoning": "Describe contraction stages and volatility reduction"
    },
    "cup_handle_analysis": {
        "detected": boolean,
        "confidence": 0.0-1.0,
        "cup_depth_ratio": 0.0-0.33,
        "handle_duration_days": 7-28,
        "reasoning": "Describe cup base and handle formation"
    },
    "stage2_analysis": {
        "confirmed": boolean,
        "confidence": 0.0-1.0,
        "ma_alignment": boolean,
        "volume_surge": boolean,
        "reasoning": "Describe MA alignment and volume breakout"
    },
    "recommendation": "STRONG_BUY|BUY|HOLD|AVOID",
    "confidence": 0.0-1.0,
    "reasoning": "Overall assessment and risk factors",
    "position_adjustment": 0.5-1.5
}

Position Adjustment Guidelines:
- STRONG_BUY: 1.3-1.5 (increase position 30-50%)
- BUY: 1.1-1.2 (increase position 10-20%)
- HOLD: 0.9-1.0 (neutral to slight reduction)
- AVOID: 0.5-0.7 (reduce position 30-50%)
"""
```

#### 2.5 Update Data Preparation for Stock Data

```python
def _prepare_chart_data_for_gpt(self, df: pd.DataFrame) -> str:
    """Prepare stock-specific chart data for GPT analysis"""

    ticker = df['ticker'].iloc[0]
    recent_df = df.tail(60)  # Use 60 days for pattern detection

    # Calculate key statistics
    current_price = recent_df['close'].iloc[-1]
    ma5 = recent_df['ma5'].iloc[-1] if 'ma5' in recent_df.columns else 0
    ma20 = recent_df['ma20'].iloc[-1] if 'ma20' in recent_df.columns else 0
    ma60 = recent_df['ma60'].iloc[-1] if 'ma60' in recent_df.columns else 0
    ma120 = recent_df['ma120'].iloc[-1] if 'ma120' in recent_df.columns else 0

    # Check MA alignment (Stage 2 indicator)
    ma_alignment = (ma5 > ma20 > ma60 > ma120) if all([ma5, ma20, ma60, ma120]) else False

    # Volume analysis
    volume_avg = recent_df['volume'].mean()
    volume_recent = recent_df['volume'].iloc[-1]
    volume_ratio = volume_recent / volume_avg if volume_avg > 0 else 0

    # Volatility analysis (for VCP detection)
    recent_30 = recent_df.tail(30)
    volatility_30d = recent_30['close'].pct_change().std() * 100

    recent_10 = recent_df.tail(10)
    volatility_10d = recent_10['close'].pct_change().std() * 100

    volatility_contraction = (volatility_10d / volatility_30d) if volatility_30d > 0 else 1.0

    # Price high/low analysis (for Cup & Handle)
    high_60d = recent_df['high'].max()
    low_60d = recent_df['low'].min()
    current_vs_high = ((current_price - high_60d) / high_60d) * 100
    cup_depth = ((high_60d - low_60d) / high_60d) * 100

    chart_text = f"""
{ticker} Stock Chart Analysis (60-Day Data):

Price Information:
- Current Price: {current_price:,.0f} KRW
- MA5: {ma5:,.0f} KRW ({((current_price-ma5)/ma5)*100 if ma5 > 0 else 0:+.1f}%)
- MA20: {ma20:,.0f} KRW ({((current_price-ma20)/ma20)*100 if ma20 > 0 else 0:+.1f}%)
- MA60: {ma60:,.0f} KRW ({((current_price-ma60)/ma60)*100 if ma60 > 0 else 0:+.1f}%)
- MA120: {ma120:,.0f} KRW ({((current_price-ma120)/ma120)*100 if ma120 > 0 else 0:+.1f}%)
- MA Alignment (Stage 2): {'YES' if ma_alignment else 'NO'}

Volume Analysis:
- Current Volume: {volume_recent:,.0f}
- 60-Day Average: {volume_avg:,.0f}
- Volume Ratio: {volume_ratio:.2f}x
- Volume Surge: {'YES' if volume_ratio > 1.5 else 'NO'}

Volatility Analysis (VCP Indicator):
- 30-Day Volatility: {volatility_30d:.1f}%
- 10-Day Volatility: {volatility_10d:.1f}%
- Contraction Ratio: {volatility_contraction:.2f} ({'Contracting' if volatility_contraction < 0.7 else 'Stable'})

Base Formation (Cup & Handle):
- 60-Day High: {high_60d:,.0f} KRW
- 60-Day Low: {low_60d:,.0f} KRW
- Cup Depth: {cup_depth:.1f}% (Ideal: 12-33%)
- Current vs High: {current_vs_high:+.1f}%

Recent 20-Day Price Movement:
"""

    # Add recent price history
    recent_20 = recent_df.tail(20).reset_index(drop=True)
    for i, row in recent_20.iterrows():
        date = row['date'].strftime('%m/%d')
        close = row['close']
        volume_ratio = row['volume'] / volume_avg if volume_avg > 0 else 0
        change = ((close - recent_20['close'].iloc[i-1]) / recent_20['close'].iloc[i-1] * 100) if i > 0 else 0

        chart_text += f"{date}: {close:,.0f} KRW ({change:+.1f}%) Vol:{volume_ratio:.1f}x\n"

    return chart_text
```

---

### Step 3: Integrate with Kelly Calculator

#### 3.1 Update kelly_calculator.py

```python
# In modules/kelly_calculator.py

from modules.stock_gpt_analyzer import (
    StockGPTAnalyzer,
    GPTAnalysisResult,
    GPTRecommendation
)

class KellyCalculator:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.gpt_analyzer = None  # Optional GPT integration

    def enable_gpt_analysis(self, enable: bool = True,
                           daily_cost_limit: float = 0.50):
        """Enable GPT-based position adjustment"""
        if enable:
            self.gpt_analyzer = StockGPTAnalyzer(
                db_path=self.db_path,
                enable_gpt=True,
                daily_cost_limit=daily_cost_limit
            )
            logger.info("✅ GPT analysis enabled for Kelly Calculator")

    def calculate_position_with_gpt(self,
                                    ticker: str,
                                    detected_pattern: PatternType,
                                    quality_score: float,
                                    risk_level: RiskLevel = RiskLevel.MODERATE,
                                    use_gpt: bool = True) -> KellyResult:
        """Calculate position size with optional GPT adjustment"""

        # Stage 1: Technical-based position sizing
        kelly_result = self.calculate_base_position(
            ticker=ticker,
            detected_pattern=detected_pattern,
            quality_score=quality_score,
            risk_level=risk_level
        )

        # Stage 2: GPT adjustment (optional)
        if use_gpt and self.gpt_analyzer and quality_score >= 70.0:
            try:
                gpt_result = self.gpt_analyzer.analyze_ticker(ticker)

                if gpt_result:
                    kelly_result = self._apply_gpt_adjustment(
                        kelly_result,
                        gpt_result
                    )
                    logger.info(
                        f"🎯 {ticker}: GPT adjustment applied - "
                        f"{kelly_result.technical_position_pct:.1f}% × "
                        f"{gpt_result.position_adjustment:.2f} = "
                        f"{kelly_result.final_position_pct:.1f}%"
                    )
            except Exception as e:
                logger.warning(f"⚠️ {ticker}: GPT adjustment failed - {e}")
                kelly_result.final_position_pct = kelly_result.technical_position_pct

        else:
            # No GPT adjustment
            kelly_result.final_position_pct = kelly_result.technical_position_pct

        return kelly_result

    def _apply_gpt_adjustment(self,
                             kelly_result: KellyResult,
                             gpt_result: GPTAnalysisResult) -> KellyResult:
        """Apply GPT confidence to position size"""

        # Extract GPT data
        kelly_result.gpt_confidence = gpt_result.confidence
        kelly_result.gpt_recommendation = gpt_result.recommendation.value
        kelly_result.gpt_adjustment = gpt_result.position_adjustment

        # Calculate final position
        technical_position = kelly_result.technical_position_pct
        adjusted_position = technical_position * gpt_result.position_adjustment

        # Apply bounds (1%-15% per position)
        kelly_result.final_position_pct = max(1.0, min(15.0, adjusted_position))

        # Save to database
        self._save_kelly_result_with_gpt(kelly_result)

        return kelly_result

    def _save_kelly_result_with_gpt(self, kelly_result: KellyResult):
        """Save Kelly calculation with GPT adjustment to database"""

        insert_sql = """
        INSERT OR REPLACE INTO kelly_sizing (
            ticker, analysis_date,
            detected_pattern, quality_score,
            base_position_pct, quality_multiplier, technical_position_pct,
            gpt_confidence, gpt_recommendation, gpt_adjustment, final_position_pct,
            risk_level, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(insert_sql, (
            kelly_result.ticker,
            kelly_result.analysis_date,
            kelly_result.detected_pattern.value,
            kelly_result.quality_score,
            kelly_result.base_position_pct,
            kelly_result.quality_multiplier,
            kelly_result.technical_position_pct,
            kelly_result.gpt_confidence,
            kelly_result.gpt_recommendation,
            kelly_result.gpt_adjustment,
            kelly_result.final_position_pct,
            kelly_result.risk_level.value
        ))

        conn.commit()
        conn.close()
```

---

### Step 4: Integrate into Main Pipeline (spock.py)

```python
# In spock.py

from modules.stock_gpt_analyzer import StockGPTAnalyzer

class SpockOrchestrator:
    def __init__(self, config_path: str, db_path: str, log_path: str):
        # ... existing initialization ...

        # Optional GPT analyzer
        self.gpt_analyzer = None

    def _initialize_subsystems(self):
        # ... existing subsystems ...

        # Kelly calculator with optional GPT
        self.kelly_calculator = KellyCalculator(str(self.db_path))

        # Enable GPT analysis if configured
        if self.config.enable_gpt:
            self.kelly_calculator.enable_gpt_analysis(
                enable=True,
                daily_cost_limit=0.50
            )
            self.logger.info("✅ GPT analysis enabled")

    async def _stage4_position_sizing(self,
                                      config: ExecutionConfig,
                                      result: PipelineResult,
                                      analyzed_candidates: List[Dict]) -> List[Dict]:
        """Stage 4: Position Sizing with GPT adjustment"""

        self.logger.info("=" * 80)
        self.logger.info("Stage 4: Position Sizing (Kelly Formula + GPT)")
        self.logger.info("=" * 80)

        sized_candidates = []

        for candidate in analyzed_candidates:
            ticker = candidate['ticker']
            quality_score = candidate['quality_score']
            detected_pattern = candidate['detected_pattern']

            # Calculate position with GPT adjustment
            kelly_result = self.kelly_calculator.calculate_position_with_gpt(
                ticker=ticker,
                detected_pattern=detected_pattern,
                quality_score=quality_score,
                risk_level=config.risk_level,
                use_gpt=config.enable_gpt  # Controlled by CLI flag
            )

            candidate['position_pct'] = kelly_result.final_position_pct
            candidate['gpt_recommendation'] = kelly_result.gpt_recommendation
            candidate['gpt_confidence'] = kelly_result.gpt_confidence

            sized_candidates.append(candidate)

            self.logger.info(
                f"💰 {ticker}: Position {kelly_result.final_position_pct:.1f}% "
                f"(Technical: {kelly_result.technical_position_pct:.1f}% × "
                f"GPT: {kelly_result.gpt_adjustment:.2f})"
            )

        return sized_candidates
```

---

### Step 5: Configure Environment

#### 5.1 Add OpenAI API Key to .env

```bash
# In .env file
OPENAI_API_KEY=sk-proj-your-api-key-here

# KIS API credentials (existing)
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
```

#### 5.2 Update requirements.txt

```bash
# Add to requirements.txt
openai>=1.0.0
```

#### 5.3 Install Dependencies

```bash
pip install openai python-dotenv
```

---

### Step 6: Testing

#### 6.1 Unit Test

```python
# tests/test_stock_gpt_analyzer.py

import pytest
from modules.stock_gpt_analyzer import StockGPTAnalyzer

@pytest.fixture
def gpt_analyzer():
    return StockGPTAnalyzer(
        db_path="data/spock_local.db",
        enable_gpt=True,
        daily_cost_limit=0.50
    )

def test_analyze_samsung_electronics(gpt_analyzer):
    """Test GPT analysis on Samsung Electronics (005930)"""
    result = gpt_analyzer.analyze_ticker("005930")

    assert result is not None
    assert result.ticker == "005930"
    assert 0.0 <= result.confidence <= 1.0
    assert result.recommendation in [
        "STRONG_BUY", "BUY", "HOLD", "AVOID"
    ]
    assert 0.5 <= result.position_adjustment <= 1.5
    print(f"✅ VCP Detected: {result.vcp_analysis.detected}")
    print(f"✅ Cup & Handle: {result.cup_handle_analysis.detected}")
    print(f"✅ Recommendation: {result.recommendation}")

def test_cache_system(gpt_analyzer):
    """Verify cache hit on second analysis"""
    ticker = "005930"

    # First call - API hit
    result1 = gpt_analyzer.analyze_ticker(ticker)
    cost1 = result1.api_cost_usd

    # Second call - Cache hit
    result2 = gpt_analyzer.analyze_ticker(ticker)
    cost2 = result2.api_cost_usd

    assert cost1 > 0  # First call had API cost
    assert cost2 == 0 or cost2 == cost1  # Second call used cache
    print(f"✅ Cache system working - First: ${cost1:.6f}, Second: ${cost2:.6f}")

def test_budget_enforcement(gpt_analyzer):
    """Verify daily budget limits"""
    initial_usage = gpt_analyzer.cost_manager.get_daily_usage()
    budget_available = gpt_analyzer.cost_manager.check_budget_available(0.01)

    assert budget_available or initial_usage >= 0.50
    print(f"✅ Daily usage: ${initial_usage:.4f} / $0.50")
```

#### 6.2 Integration Test

```bash
# Run integration test
python3 -c "
from modules.stock_gpt_analyzer import StockGPTAnalyzer
from modules.integrated_scoring_system import IntegratedScoringSystem

# Initialize
scoring = IntegratedScoringSystem('data/spock_local.db')
gpt = StockGPTAnalyzer('data/spock_local.db', enable_gpt=True)

# Test pipeline
ticker = '005930'
score = scoring.calculate_score(ticker)
print(f'Technical Score: {score}')

if score >= 70.0:
    result = gpt.analyze_ticker(ticker)
    print(f'GPT Recommendation: {result.recommendation}')
    print(f'Position Adjustment: {result.position_adjustment}x')
"
```

---

### Step 7: Run Full Pipeline

```bash
# Dry run with GPT analysis enabled
python3 spock.py --dry-run --region KR --enable-gpt

# Expected output:
# Stage 1: Stock Scanning - 50 candidates
# Stage 2: Data Collection - 250-day OHLCV
# Stage 3: Technical Analysis - 10 candidates (score ≥70)
# Stage 4: Position Sizing - GPT analysis on 10 stocks
#   💰 005930: Position 12.5% (Technical: 10.0% × GPT: 1.25)
#   💰 035720: Position 9.0% (Technical: 10.0% × GPT: 0.90)
# Stage 5: DRY RUN - Would execute 8 trades
# Stage 6: Portfolio Sync
#
# 💰 Daily GPT Cost: $0.05 / $0.50
```

---

## Troubleshooting

### Issue 1: OpenAI API Key Not Found

```bash
# Error: "OpenAI API key not found"
# Solution: Check .env file
cat .env | grep OPENAI_API_KEY

# If missing, add it
echo "OPENAI_API_KEY=sk-proj-your-key" >> .env
```

### Issue 2: Budget Exceeded

```bash
# Error: "Daily budget exceeded"
# Solution: Check daily usage
python3 -c "
from modules.stock_gpt_analyzer import StockGPTAnalyzer
gpt = StockGPTAnalyzer('data/spock_local.db')
usage = gpt.cost_manager.get_daily_usage()
print(f'Daily usage: \${usage:.4f} / \$0.50')
"

# Reset if needed (new day)
# Or increase daily_cost_limit in config
```

### Issue 3: JSON Parse Error

```bash
# Error: "JSON decode error from GPT response"
# Solution: Check GPT response format
# - Verify SYSTEM_PROMPT includes response_format instruction
# - Add retry logic (already implemented)
# - Check OpenAI API status
```

### Issue 4: Cache Not Working

```bash
# Error: "Cache miss on repeated analysis"
# Solution: Verify database connection
python3 -c "
import sqlite3
conn = sqlite3.connect('data/spock_local.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM gpt_analysis')
count = cursor.fetchone()[0]
print(f'Cached analyses: {count}')
conn.close()
"
```

---

## Performance Optimization

### Optimize 1: Reduce Token Usage

```python
# Use only recent 40 days instead of 60
recent_df = df.tail(40)  # Reduces input tokens by 33%

# Summarize price history instead of daily details
# Before: 20 lines × 50 chars = 1000 chars
# After: 5 summary stats = 200 chars (80% reduction)
```

### Optimize 2: Batch Analysis

```python
# Analyze multiple tickers in one session
def analyze_batch(self, tickers: List[str]) -> List[GPTAnalysisResult]:
    """Batch analysis with budget control"""
    results = []
    for ticker in tickers:
        if not self.cost_manager.check_budget_available(0.005):
            logger.warning("Budget exhausted, stopping batch")
            break
        result = self.analyze_ticker(ticker)
        if result:
            results.append(result)
    return results
```

### Optimize 3: Extend Cache TTL

```python
# Increase cache validity for stable patterns
# From 72 hours → 168 hours (7 days)
self.cache_ttl_hours = 168

# Rationale: Chart patterns don't change significantly in 7 days
```

---

## Monitoring Commands

```bash
# Check daily GPT cost
python3 -c "
from modules.stock_gpt_analyzer import StockGPTAnalyzer
gpt = StockGPTAnalyzer('data/spock_local.db')
print(f'Daily cost: \${gpt.cost_manager.get_daily_usage():.4f}')
"

# Check cache hit rate
sqlite3 data/spock_local.db "
SELECT
  COUNT(*) as total_analyses,
  SUM(CASE WHEN api_cost_usd > 0 THEN 1 ELSE 0 END) as api_calls,
  ROUND(100.0 * SUM(CASE WHEN api_cost_usd = 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as cache_hit_rate
FROM gpt_analysis
WHERE DATE(created_at) = DATE('now');
"

# Check pattern detection rates
sqlite3 data/spock_local.db "
SELECT
  SUM(vcp_detected) as vcp_count,
  SUM(cup_handle_detected) as cup_handle_count,
  COUNT(*) as total,
  gpt_recommendation,
  COUNT(*) as recommendation_count
FROM gpt_analysis
WHERE DATE(created_at) >= DATE('now', '-7 days')
GROUP BY gpt_recommendation;
"
```

---

## Next Steps

1. **Implement Module**: Follow Steps 1-3 to create `modules/stock_gpt_analyzer.py`
2. **Write Tests**: Implement unit tests in `tests/test_stock_gpt_analyzer.py`
3. **Integration**: Add to main pipeline in `spock.py`
4. **Validation**: Run dry-run mode with real data
5. **Monitoring**: Track cost, cache hit rate, and recommendation accuracy

---

**Implementation Time Estimate**: 2-3 days
- Day 1: Module creation and database schema (4-6 hours)
- Day 2: Integration and testing (4-6 hours)
- Day 3: Validation and optimization (2-4 hours)
