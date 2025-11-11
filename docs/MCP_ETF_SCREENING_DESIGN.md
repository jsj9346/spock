# ETF Screening Tool Design - Spock MCP Server

**Purpose**: Sector trend analysis and retirement account optimization through ETF screening

**Target Users**: Retirement account investors, sector rotation strategists, passive investment managers

**Date**: 2025-10-31

---

## 📋 Table of Contents

1. [Requirements Analysis](#requirements-analysis)
2. [System Architecture](#system-architecture)
3. [Data Model Design](#data-model-design)
4. [Tool Interface Design](#tool-interface-design)
5. [ETF Data Collection Strategy](#etf-data-collection-strategy)
6. [ETF Scoring Logic](#etf-scoring-logic)
7. [Implementation Plan](#implementation-plan)
8. [Testing Strategy](#testing-strategy)

---

## 1. Requirements Analysis

### 1.1 Primary Use Cases

| Use Case | Description | Key Metrics |
|----------|-------------|-------------|
| **Sector Trend Analysis** | Identify sector momentum through ETF price trends | MA trend, RSI, sector theme |
| **Cost Efficiency** | Compare expense ratios within same sector | TER, tracking error |
| **Performance Comparison** | Compare ETF returns vs benchmark | Benchmark return, tracking error |
| **Retirement Portfolio** | Select low-cost, diversified ETFs | AUM, TER, dividend yield |
| **Risk Assessment** | Evaluate ETF stability and tracking quality | Tracking error, AUM, volatility |

### 1.2 Essential ETF Metrics

#### 1.2.1 Fundamental Metrics
- **AUM (Assets Under Management)**: 운용자산규모
  - Purpose: Liquidity and stability indicator
  - Filter: `aum_min` (e.g., ≥ 100억원)
  - Unit: KRW (원)

- **TER/Expense Ratio**: 총보수비용
  - Purpose: Cost efficiency comparison
  - Filter: `ter_max` (e.g., ≤ 0.5%)
  - Unit: Percentage (%)

- **Tracking Error**: 추적오차
  - Purpose: Index tracking quality
  - Filter: `tracking_error_max` (e.g., ≤ 2%)
  - Unit: Percentage (%)

- **Dividend Yield**: 분배금수익률
  - Purpose: Income generation potential
  - Filter: `dividend_yield_min` (e.g., ≥ 3%)
  - Unit: Percentage (%)

#### 1.2.2 Descriptive Attributes
- **Sector/Theme**: 투자 섹터 (e.g., "반도체", "2차전지", "헬스케어")
- **Tracking Index**: 추종 지수 (e.g., "KOSPI 200", "S&P 500")
- **Geographic Region**: 투자 지역 (e.g., "국내", "미국", "선진국")
- **Fund Type**: 펀드 유형 (e.g., "주식형", "채권형", "리츠")

#### 1.2.3 Technical Metrics (from existing tools)
- **RSI**: Momentum indicator
- **MA Trend**: Trend direction (bullish/bearish/neutral)
- **Price vs MA20**: Current position vs short-term trend

### 1.3 Comparison Requirements

#### Within-Sector Comparison
```
Input: sector_theme = "반도체"
Output: Sorted ETFs by:
  1. TER (ascending) - 낮은 운용보수 우선
  2. Tracking Error (ascending) - 낮은 추적오차 우선
  3. AUM (descending) - 큰 규모 우선
  4. MA Trend (bullish first) - 상승 추세 우선
```

#### Benchmark Performance Comparison
```
Metric: (ETF Return - Benchmark Return) over same period
Filter: tracking_error_max to ensure quality tracking
Display: Return difference in percentage points
```

---

## 2. System Architecture

### 2.1 Overall Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude Desktop / Claude Code                 │
│                    MCP Client (User Interface)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP Protocol
┌────────────────────────────▼────────────────────────────────────┐
│                        Spock MCP Server                          │
│  Tools: screen_etfs | get_technical_indicators                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      ETF Screening Adapter                       │
│  - ETF-specific filtering logic                                 │
│  - Sector comparison & ranking                                  │
│  - Cost efficiency analysis                                     │
└──────────┬──────────────────────────┬──────────────────────────┘
           │                          │
┌──────────▼────────────┐  ┌──────────▼────────────────────────┐
│  PostgreSQL Database  │  │  Technical Calculator (Reused)   │
│  - tickers (ETF)      │  │  - RSI calculation               │
│  - etf_details        │  │  - MA trend analysis             │
│  - ohlcv_data         │  │  - Price momentum                │
│  - ticker_fundamentals│  │                                  │
└───────────────────────┘  └──────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility | Input | Output |
|-----------|----------------|-------|--------|
| **screen_etfs Tool** | MCP tool definition and validation | JSON schema | Tool response |
| **ETFScreeningAdapter** | ETF filtering and ranking | Filter criteria | Sorted ETF list |
| **ETFDataCollector** | Collect ETF data from external sources | Ticker list | ETF details |
| **ETFScorer** | Sector comparison and scoring | ETF list | Ranked scores |
| **TechnicalCalculator** | Technical indicators (reused) | OHLCV data | RSI, MA, trend |

---

## 3. Data Model Design

### 3.1 Current Database Schema

#### 3.1.1 tickers Table (Existing)
```sql
CREATE TABLE tickers (
    ticker VARCHAR(20),
    region VARCHAR(2),
    name TEXT,
    asset_type VARCHAR(20),  -- 'ETF', 'STOCK', 'PREFERRED', 'REIT'
    exchange VARCHAR(20),
    listing_date DATE,
    is_active BOOLEAN,
    PRIMARY KEY (ticker, region)
);

-- Current data: 1,208 ETFs in KR region
SELECT COUNT(*) FROM tickers WHERE region='KR' AND asset_type='ETF';
-- Result: 1,208
```

#### 3.1.2 etf_details Table (Exists but Empty)
```sql
CREATE TABLE etf_details (
    ticker VARCHAR(20),
    region VARCHAR(2),
    issuer TEXT,                    -- 운용사 (e.g., "삼성자산운용")
    inception_date DATE,            -- 설정일
    underlying_asset_class TEXT,    -- 기초자산 (e.g., "주식")
    tracking_index TEXT,            -- 추종지수 (e.g., "KOSPI 200")
    geographic_region TEXT,         -- 투자지역 (e.g., "국내")
    sector_theme TEXT,              -- 섹터/테마 (e.g., "반도체")
    fund_type TEXT,                 -- 펀드유형 (e.g., "주식형")
    aum BIGINT,                     -- 순자산총액 (원)
    listed_shares BIGINT,           -- 상장주식수
    underlying_asset_count INTEGER, -- 구성종목수
    expense_ratio NUMERIC(5, 4),    -- 총보수 (%)
    ter NUMERIC(5, 4),              -- TER (%)
    leverage_ratio VARCHAR(10),     -- 레버리지 (e.g., "2X", "INVERSE")
    currency_hedged BOOLEAN,        -- 환헤지 여부
    tracking_error_20d NUMERIC(6, 4),  -- 추적오차 20일 (%)
    tracking_error_60d NUMERIC(6, 4),  -- 추적오차 60일 (%)
    tracking_error_120d NUMERIC(6, 4), -- 추적오차 120일 (%)
    tracking_error_250d NUMERIC(6, 4), -- 추적오차 250일 (%)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, region),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region)
);

-- Current status: EMPTY (needs backfill)
SELECT COUNT(*) FROM etf_details;
-- Result: 0
```

#### 3.1.3 ticker_fundamentals Table (ETF용 확장 필요)
```sql
-- Current: Only stocks have data
-- Need: Add dividend_yield for ETFs

CREATE TABLE ticker_fundamentals (
    ticker VARCHAR(20),
    region VARCHAR(2),
    date DATE,
    per NUMERIC(10, 4),            -- Not applicable for ETFs
    pbr NUMERIC(10, 4),            -- Not applicable for ETFs
    dividend_yield NUMERIC(6, 4),  -- Applicable for ETFs (분배금수익률)
    market_cap BIGINT,             -- AUM for ETFs
    PRIMARY KEY (ticker, region, date)
);
```

### 3.2 Required Data Extensions

#### 3.2.1 ETF Dividend Yield (분배금수익률)
- **Source**: KRX ETF portal, 운용사 공시
- **Calculation**: (연간 분배금 / 현재 가격) × 100
- **Storage**: `ticker_fundamentals.dividend_yield`
- **Update Frequency**: Daily

#### 3.2.2 ETF Performance Metrics
- **Benchmark Return**: 추종지수 수익률
- **ETF Return**: ETF 수익률
- **Return Difference**: ETF Return - Benchmark Return
- **Calculation Period**: 20일, 60일, 120일, 250일

---

## 4. Tool Interface Design

### 4.1 screen_etfs Tool Definition

#### 4.1.1 Tool Schema
```python
Tool(
    name="screen_etfs",
    description="Screen ETFs by fundamental criteria (AUM, TER, tracking error) and technical indicators (MA trend, RSI)",
    inputSchema={
        "type": "object",
        "properties": {
            "filters": {
                "type": "object",
                "description": "ETF fundamental filters",
                "properties": {
                    "aum_min": {
                        "type": "number",
                        "description": "Minimum AUM in KRW (e.g., 10000000000 for 100억원)",
                        "minimum": 0
                    },
                    "ter_max": {
                        "type": "number",
                        "description": "Maximum TER in % (e.g., 0.5 for 0.5%)",
                        "minimum": 0,
                        "maximum": 5.0
                    },
                    "tracking_error_max": {
                        "type": "number",
                        "description": "Maximum tracking error in % (e.g., 2.0 for 2%)",
                        "minimum": 0,
                        "maximum": 10.0
                    },
                    "dividend_yield_min": {
                        "type": "number",
                        "description": "Minimum dividend yield in % (e.g., 3.0 for 3%)",
                        "minimum": 0,
                        "maximum": 50.0
                    },
                    "sector_theme": {
                        "type": "string",
                        "description": "Sector or theme (e.g., '반도체', '2차전지', 'AI')"
                    },
                    "geographic_region": {
                        "type": "string",
                        "description": "Geographic region (e.g., '국내', '미국', '선진국')"
                    },
                    "fund_type": {
                        "type": "string",
                        "description": "Fund type (e.g., '주식형', '채권형', '리츠')"
                    }
                }
            },
            "technical_filters": {
                "type": "object",
                "description": "Technical indicator filters",
                "properties": {
                    "ma_trend": {
                        "type": "string",
                        "enum": ["bullish", "bearish", "neutral"],
                        "description": "MA trend (bullish: MA20>MA50>MA200)"
                    },
                    "rsi_min": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100
                    },
                    "rsi_max": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100
                    }
                }
            },
            "sort_by": {
                "type": "string",
                "enum": ["ter", "aum", "tracking_error", "dividend_yield", "ma_trend"],
                "default": "ter",
                "description": "Sort criteria (default: ter ascending)"
            },
            "region": {
                "type": "string",
                "enum": ["KR", "US"],
                "default": "KR"
            },
            "limit": {
                "type": "number",
                "default": 50,
                "minimum": 1,
                "maximum": 200
            }
        },
        "required": ["filters"]
    }
)
```

#### 4.1.2 Example Request
```json
{
  "filters": {
    "sector_theme": "반도체",
    "aum_min": 10000000000,
    "ter_max": 0.5
  },
  "technical_filters": {
    "ma_trend": "bullish"
  },
  "sort_by": "ter",
  "region": "KR",
  "limit": 20
}
```

#### 4.1.3 Example Response
```json
{
  "success": true,
  "etfs": [
    {
      "ticker": "252670",
      "name": "KODEX 200선물인버스2X",
      "issuer": "삼성자산운용",
      "sector_theme": "반도체",
      "tracking_index": "KOSPI 200",
      "geographic_region": "국내",
      "fund_type": "주식형",
      "aum": 250000000000,
      "aum_formatted": "2,500억원",
      "ter": 0.35,
      "tracking_error_20d": 0.15,
      "tracking_error_60d": 0.18,
      "tracking_error_250d": 0.22,
      "dividend_yield": 2.5,
      "current_price": 12500.0,
      "rsi": 55.2,
      "rsi_signal": "neutral",
      "ma_trend": "bullish",
      "ma20": 12300,
      "ma50": 12000,
      "ma200": 11800,
      "price_vs_ma20": "above",
      "fundamental_score": 95.5,
      "technical_score": 100.0,
      "composite_score": 97.2,
      "date": "2025-10-31"
    }
  ],
  "count": 5,
  "total_matching": 5,
  "filters_applied": {
    "sector_theme": "반도체",
    "aum_min": 10000000000,
    "ter_max": 0.5
  },
  "technical_filters_applied": {
    "ma_trend": "bullish"
  },
  "sector_comparison": {
    "sector": "반도체",
    "etf_count": 5,
    "avg_ter": 0.42,
    "avg_aum": 180000000000,
    "best_ter": 0.35,
    "worst_ter": 0.49
  },
  "region": "KR",
  "timestamp": "2025-10-31T16:30:00"
}
```

---

## 5. ETF Data Collection Strategy

### 5.1 Data Sources

| Source | Data Type | Collection Method | Update Frequency |
|--------|-----------|-------------------|------------------|
| **KRX ETF Portal** | AUM, TER, tracking error | Web scraping / API | Daily |
| **운용사 공시** | Dividend yield, fund type | Web scraping | Weekly |
| **ETFCheck** | Sector theme, tracking index | Web scraping | Monthly |
| **KIS API** | OHLCV data | API (already implemented) | Real-time |

### 5.2 ETF Data Collector Implementation

#### 5.2.1 Architecture
```python
# scripts/collect_etf_data.py

class ETFDataCollector:
    """
    Collect ETF fundamental data from multiple sources.

    Sources:
    - KRX: AUM, TER, tracking error
    - ETFCheck: Sector theme, tracking index
    - 운용사: Dividend yield
    """

    def __init__(self):
        self.db_manager = PostgresDatabaseManager()
        self.krx_scraper = KRXScraper()
        self.etfcheck_scraper = ETFCheckScraper()

    async def collect_all_etfs(self, region: str = "KR") -> int:
        """Collect data for all ETFs in region."""
        pass

    async def collect_etf_details(self, ticker: str, region: str) -> Dict:
        """Collect detailed data for single ETF."""
        pass

    async def update_aum(self) -> int:
        """Update AUM for all ETFs (daily)."""
        pass

    async def update_dividend_yield(self) -> int:
        """Update dividend yield (weekly)."""
        pass
```

#### 5.2.2 Data Collection Workflow
```
1. Get ETF list from tickers table (asset_type='ETF')
2. For each ETF:
   a. Scrape KRX for AUM, TER, tracking error
   b. Scrape ETFCheck for sector, theme, tracking index
   c. Calculate dividend yield from historical distributions
   d. Insert/update etf_details table
3. Log collection statistics
4. Schedule next collection
```

### 5.3 Collection Script
```bash
# Daily collection (AUM, prices)
python3 scripts/collect_etf_data.py --mode daily --region KR

# Weekly collection (dividend yield, distributions)
python3 scripts/collect_etf_data.py --mode weekly --region KR

# Monthly collection (sector classification, fund details)
python3 scripts/collect_etf_data.py --mode monthly --region KR

# Full backfill (all data)
python3 scripts/collect_etf_data.py --mode backfill --region KR --dry-run
```

---

## 6. ETF Scoring Logic

### 6.1 ETF-Specific Scoring

#### 6.1.1 Fundamental Score (60%)
```python
class ETFFundamentalScorer:
    """
    ETF fundamental scoring based on cost efficiency and size.

    Factors (equal weight):
    - TER (lower is better)
    - AUM (higher is better)
    - Tracking Error (lower is better)
    - Dividend Yield (higher is better)
    """

    def calculate_fundamental_score(self, etf: Dict) -> float:
        """
        Score: 0-100

        TER Score: 25 points
        - 0.0-0.3%: 25 points
        - 0.3-0.5%: 20 points
        - 0.5-1.0%: 15 points
        - >1.0%: 10 points

        AUM Score: 25 points
        - ≥ 1조원: 25 points
        - ≥ 5천억원: 20 points
        - ≥ 1천억원: 15 points
        - < 1천억원: 10 points

        Tracking Error Score: 25 points
        - < 0.5%: 25 points
        - 0.5-1.0%: 20 points
        - 1.0-2.0%: 15 points
        - > 2.0%: 10 points

        Dividend Yield Score: 25 points
        - ≥ 5%: 25 points
        - 3-5%: 20 points
        - 1-3%: 15 points
        - < 1%: 10 points
        """
        pass
```

#### 6.1.2 Technical Score (40%)
```python
# Reuse existing TechnicalScorer from stock screening
from modules.screening.composite_scorer import CompositeScorer

scorer = CompositeScorer(
    fundamental_weight=0.6,  # ETF fundamental (TER, AUM, etc.)
    technical_weight=0.4     # Technical indicators (MA, RSI)
)
```

### 6.2 Sector Comparison

#### 6.2.1 Within-Sector Ranking
```python
def rank_etfs_within_sector(etfs: List[Dict], sector: str) -> List[Dict]:
    """
    Rank ETFs within same sector.

    Primary Sort: TER (ascending)
    Secondary Sort: Tracking Error (ascending)
    Tertiary Sort: AUM (descending)
    Quaternary Sort: MA Trend (bullish first)
    """

    sector_etfs = [e for e in etfs if e['sector_theme'] == sector]

    return sorted(sector_etfs, key=lambda x: (
        x['ter'],                    # Lower TER first
        x['tracking_error_250d'],    # Lower tracking error first
        -x['aum'],                   # Larger AUM first
        0 if x['ma_trend'] == 'bullish' else 1  # Bullish first
    ))
```

#### 6.2.2 Sector Statistics
```python
def calculate_sector_stats(etfs: List[Dict], sector: str) -> Dict:
    """
    Calculate sector-level statistics for comparison.

    Returns:
    {
        "sector": "반도체",
        "etf_count": 5,
        "avg_ter": 0.42,
        "avg_aum": 180000000000,
        "best_ter": 0.35,
        "worst_ter": 0.49,
        "avg_tracking_error": 0.25,
        "bullish_count": 3,
        "bearish_count": 1,
        "neutral_count": 1
    }
    """
    pass
```

---

## 7. Implementation Plan

### 7.1 Phase 1: Data Collection (3-4 days)

#### Day 1: ETF Data Scrapers
- [ ] Implement KRX scraper for AUM, TER, tracking error
- [ ] Implement ETFCheck scraper for sector, theme, tracking index
- [ ] Test scrapers with sample ETFs

#### Day 2: Data Pipeline
- [ ] Create `collect_etf_data.py` script
- [ ] Implement backfill logic for all 1,208 ETFs
- [ ] Add error handling and retry logic

#### Day 3: Dividend Yield Collection
- [ ] Scrape historical dividend distributions
- [ ] Calculate dividend yield for each ETF
- [ ] Store in `ticker_fundamentals` table

#### Day 4: Validation
- [ ] Validate data completeness (all 1,208 ETFs)
- [ ] Check data accuracy against official sources
- [ ] Document data collection process

### 7.2 Phase 2: ETF Screening Tool (2-3 days)

#### Day 1: Adapter Implementation
- [ ] Create `ETFScreeningAdapter` class
- [ ] Implement ETF filtering logic
- [ ] Add sector comparison functionality

#### Day 2: Tool Definition
- [ ] Create `etf_tool.py` with tool definition
- [ ] Implement `handle_screen_etfs` handler
- [ ] Register tool in `server.py`

#### Day 3: Scoring Logic
- [ ] Create `ETFFundamentalScorer` class
- [ ] Integrate with existing `CompositeScorer`
- [ ] Add within-sector ranking

### 7.3 Phase 3: Testing & Validation (1-2 days)

#### Day 1: Unit Tests
- [ ] Test ETF filtering logic
- [ ] Test sector comparison
- [ ] Test scoring calculations

#### Day 2: Integration Tests
- [ ] Test complete workflow (filter → score → rank)
- [ ] Test with Claude Desktop
- [ ] Performance testing (query < 2s)

---

## 8. Testing Strategy

### 8.1 Test Data

#### 8.1.1 Sample ETFs for Testing
```python
TEST_ETFS = [
    # 반도체 섹터
    {"ticker": "252670", "name": "KODEX 반도체", "sector": "반도체", "ter": 0.35, "aum": 2.5e11},
    {"ticker": "091160", "name": "TIGER 반도체", "sector": "반도체", "ter": 0.40, "aum": 1.8e11},

    # 2차전지 섹터
    {"ticker": "364980", "name": "KODEX 2차전지", "sector": "2차전지", "ter": 0.45, "aum": 1.2e11},
    {"ticker": "371460", "name": "TIGER 2차전지", "sector": "2차전지", "ter": 0.50, "aum": 0.9e11},
]
```

### 8.2 Test Cases

#### 8.2.1 Functional Tests
```python
# Test 1: Basic filtering
async def test_filter_by_ter():
    result = await adapter.screen_etfs(
        filters={"ter_max": 0.5},
        region="KR",
        limit=50
    )
    assert all(etf['ter'] <= 0.5 for etf in result['etfs'])

# Test 2: Sector filtering
async def test_filter_by_sector():
    result = await adapter.screen_etfs(
        filters={"sector_theme": "반도체"},
        region="KR"
    )
    assert all(etf['sector_theme'] == "반도체" for etf in result['etfs'])

# Test 3: Technical + Fundamental
async def test_combined_filters():
    result = await adapter.screen_etfs(
        filters={"ter_max": 0.5, "aum_min": 1e11},
        technical_filters={"ma_trend": "bullish"},
        region="KR"
    )
    assert all(
        etf['ter'] <= 0.5 and
        etf['aum'] >= 1e11 and
        etf['ma_trend'] == "bullish"
        for etf in result['etfs']
    )

# Test 4: Sector comparison
async def test_sector_comparison():
    result = await adapter.screen_etfs(
        filters={"sector_theme": "반도체"},
        sort_by="ter",
        region="KR"
    )
    # Check ETFs sorted by TER ascending
    ters = [etf['ter'] for etf in result['etfs']]
    assert ters == sorted(ters)

    # Check sector statistics present
    assert 'sector_comparison' in result
    assert result['sector_comparison']['sector'] == "반도체"
```

#### 8.2.2 Performance Tests
```python
# Test 5: Query performance
async def test_query_performance():
    import time
    start = time.time()
    result = await adapter.screen_etfs(
        filters={"ter_max": 0.5},
        region="KR",
        limit=100
    )
    duration = time.time() - start
    assert duration < 2.0  # Must complete within 2 seconds

# Test 6: Large result set
async def test_large_result_set():
    result = await adapter.screen_etfs(
        filters={},  # No filters
        region="KR",
        limit=200
    )
    assert len(result['etfs']) <= 200
```

#### 8.2.3 Integration Tests
```python
# Test 7: End-to-end workflow
async def test_e2e_retirement_portfolio_selection():
    """
    Use case: Select low-cost, diversified ETFs for retirement account
    """
    # Step 1: Filter by cost
    result = await adapter.screen_etfs(
        filters={
            "ter_max": 0.5,
            "aum_min": 1e11,
            "tracking_error_max": 1.0
        },
        region="KR",
        limit=50
    )

    # Step 2: Group by sector
    sectors = {}
    for etf in result['etfs']:
        sector = etf['sector_theme']
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(etf)

    # Step 3: Select best ETF from each sector (diversification)
    portfolio = []
    for sector, etfs in sectors.items():
        # Best = lowest TER + bullish trend
        best_etf = sorted(etfs, key=lambda x: (
            x['ter'],
            0 if x.get('ma_trend') == 'bullish' else 1
        ))[0]
        portfolio.append(best_etf)

    # Validation
    assert len(portfolio) >= 5  # At least 5 sectors
    assert all(etf['ter'] <= 0.5 for etf in portfolio)
    assert sum(etf['aum'] for etf in portfolio) >= 1e12  # Total AUM ≥ 1조원
```

### 8.3 Manual Testing in Claude Desktop

#### Test Scenario 1: Sector Trend Analysis
```
User: 반도체 섹터의 ETF 중에서 운용보수가 낮고 추세가 상승하는 종목을 찾아줘.

Expected Response:
- Filter: sector_theme="반도체", ter_max=0.5, ma_trend="bullish"
- Result: 3-5 ETFs sorted by TER
- Sector comparison showing average TER and best options
```

#### Test Scenario 2: Cost Comparison
```
User: 2차전지 섹터의 ETF들을 운용보수로 비교해줘.

Expected Response:
- Filter: sector_theme="2차전지"
- Sort: ter ascending
- Display: sector_comparison with avg_ter, best_ter, worst_ter
```

#### Test Scenario 3: Retirement Portfolio
```
User: 퇴직연금 계좌에 넣을 ETF를 추천해줘. 운용보수는 낮고, 안정적이며, 분배금이 있는 종목으로.

Expected Response:
- Filter: ter_max=0.5, aum_min=1e11, tracking_error_max=1.0, dividend_yield_min=2.0
- Sort: ter ascending
- Result: Diversified across sectors
```

---

## 9. File Structure

### 9.1 New Files to Create
```
~/spock/
├── mcp_server/
│   ├── adapters/
│   │   └── etf_screening_adapter.py          # NEW: ETF screening logic
│   └── tools/
│       └── etf_tool.py                        # NEW: screen_etfs tool definition
├── modules/
│   └── screening/
│       ├── etf_fundamental_scorer.py          # NEW: ETF scoring logic
│       └── etf_data_collector.py              # NEW: ETF data collection
├── scripts/
│   ├── collect_etf_data.py                    # NEW: Data collection script
│   └── backfill_etf_details.py                # NEW: Backfill existing ETFs
├── tests/
│   └── test_etf_screening.py                  # NEW: ETF screening tests
└── docs/
    └── MCP_ETF_SCREENING_DESIGN.md            # THIS FILE
```

### 9.2 Files to Modify
```
~/spock/
├── mcp_server/
│   └── server.py                              # MODIFY: Register screen_etfs tool
└── requirements_quant.txt                     # MODIFY: Add beautifulsoup4, requests
```

---

## 10. Success Criteria

### 10.1 Data Collection
- ✅ All 1,208 KR ETFs have complete data in `etf_details` table
- ✅ Data accuracy > 95% (validated against official sources)
- ✅ Update frequency: Daily for AUM, Weekly for dividends

### 10.2 Tool Functionality
- ✅ `screen_etfs` returns results in < 2 seconds
- ✅ All filters work correctly (fundamental + technical)
- ✅ Sector comparison shows accurate statistics
- ✅ Sorting by TER, AUM, tracking_error works correctly

### 10.3 User Experience
- ✅ Claude Desktop can successfully call `screen_etfs` tool
- ✅ Response size < 10 KB (no context overflow)
- ✅ Clear sector comparison for cost efficiency analysis
- ✅ Retirement portfolio use case works end-to-end

### 10.4 Code Quality
- ✅ Unit test coverage > 80%
- ✅ All integration tests passing
- ✅ Code follows existing patterns (screening_adapter.py)
- ✅ Proper error handling and logging

---

## 11. Risk Mitigation

### 11.1 Data Collection Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Web scraping blocked | HIGH | Use multiple sources, add rate limiting, retry logic |
| Data format changes | MEDIUM | Regular validation, automated alerts |
| Missing data for some ETFs | MEDIUM | Graceful degradation, use partial data |

### 11.2 Implementation Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance issues | HIGH | Database indexing, query optimization, caching |
| Tool registration conflicts | LOW | Follow existing patterns, comprehensive testing |
| Scoring logic errors | MEDIUM | Extensive unit tests, manual validation |

---

## 12. Future Enhancements (Post-MVP)

### 12.1 Phase 2 Features
- **Benchmark Performance Tracking**: Compare ETF returns vs benchmark over time
- **Historical Tracking Error**: Chart tracking error trends
- **Expense Ratio History**: Track TER changes over time
- **Sector Rotation Signals**: Identify sector momentum shifts

### 12.2 Phase 3 Features
- **Portfolio Backtesting**: Test ETF portfolio strategies
- **Rebalancing Recommendations**: Suggest optimal rebalancing timing
- **Tax Efficiency Analysis**: Calculate tax implications for retirement accounts
- **Multi-Asset ETFs**: Include bond, commodity, and mixed-asset ETFs

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31
**Status**: Design Complete, Ready for Implementation
