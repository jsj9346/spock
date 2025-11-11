# ETF Screening Tool - User Guide

**Tool Name**: `screen_etfs`
**Purpose**: Screen Korean ETFs using available data sources with intelligent workarounds
**Status**: ✅ Production Ready
**Date**: 2025-10-31
**Phase**: ETF Screening Tool - Phase 2 Complete

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Available Filters](#available-filters)
4. [Usage Examples](#usage-examples)
5. [Known Limitations](#known-limitations)
6. [Workarounds and Best Practices](#workarounds-and-best-practices)
7. [Response Format](#response-format)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The `screen_etfs` MCP tool provides ETF screening capabilities using available data sources from the Spock quant platform. Unlike the stock screening tool (`screen_stocks`), this tool uses alternative approaches to work around data limitations in Korean ETF markets.

### What's Available ✅

- ✅ **Basic Metadata**: Ticker, name, listing date
- ✅ **Price History**: OHLCV data for performance analysis
- ✅ **Technical Indicators**: RSI, moving average trends
- ✅ **Performance Metrics**: 1-month price change, 20-day average volume
- ✅ **Sector Approximation**: Parsed from ETF name (e.g., "KODEX 반도체" → Semiconductor)

### What's Not Available ⚠️

- ❌ **AUM** (Assets Under Management): Not readily available from Korean sources
- ❌ **TER** (Total Expense Ratio): Requires complex web scraping
- ❌ **Tracking Error**: Limited data availability from providers
- ❌ **Precise Sector Classification**: Approximated from name parsing

### Data Source

- **Region**: KR (Korean market)
- **ETF Count**: 1,061 standard 6-digit ticker ETFs
- **Update Frequency**: Real-time during market hours, daily post-close
- **Historical Data**: Up to 400 days for technical indicator calculation

---

## Quick Start

### Basic Example: Find Semiconductor ETFs

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "반도체"
    },
    "region": "KR",
    "limit": 10
  }
}
```

**Result**: Returns top 10 ETFs with "반도체" (semiconductor) in their name.

### Example with Technical Filters

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "200"
    },
    "technical_filters": {
      "ma_trend": "bullish",
      "rsi_max": 70
    },
    "region": "KR",
    "limit": 20
  }
}
```

**Result**: Returns up to 20 broad market ETFs (e.g., KODEX 200) with bullish trend and RSI below 70.

---

## Available Filters

### 1. Basic Filters (`filters` object)

#### `name_pattern` (string)
Filter ETFs by name substring. Case-insensitive matching.

**Common Patterns**:
- `"반도체"` - Semiconductor ETFs
- `"배터리"` or `"2차전지"` - Battery/Secondary battery ETFs
- `"200"` - Broad market index ETFs (KOSPI 200)
- `"KODEX"` - KODEX series ETFs
- `"TIGER"` - TIGER series ETFs
- `"바이오"` - Bio/Healthcare ETFs
- `"IT"` - Information Technology ETFs

**Example**:
```json
{
  "filters": {
    "name_pattern": "반도체"
  }
}
```

#### `listing_date_after` (string, YYYY-MM-DD)
Filter ETFs listed after a specific date. Useful for finding newer ETFs.

**Example**:
```json
{
  "filters": {
    "listing_date_after": "2020-01-01"
  }
}
```

#### `listing_date_before` (string, YYYY-MM-DD)
Filter ETFs listed before a specific date. Useful for finding established ETFs.

**Example**:
```json
{
  "filters": {
    "listing_date_before": "2015-12-31"
  }
}
```

---

### 2. Technical Filters (`technical_filters` object)

#### `rsi_min` (number, 0-100)
Minimum RSI value. Use for finding oversold ETFs.

**Example**: Find oversold ETFs
```json
{
  "technical_filters": {
    "rsi_min": 0,
    "rsi_max": 30
  }
}
```

#### `rsi_max` (number, 0-100)
Maximum RSI value. Use for avoiding overbought ETFs.

**Example**: Find neutral momentum ETFs
```json
{
  "technical_filters": {
    "rsi_min": 40,
    "rsi_max": 60
  }
}
```

#### `ma_trend` (string: "bullish" | "bearish" | "neutral")
Moving average trend classification:
- **"bullish"**: MA20 > MA50 > MA200 (strong uptrend)
- **"bearish"**: MA20 < MA50 < MA200 (strong downtrend)
- **"neutral"**: Mixed MA configuration

**Example**: Find ETFs in uptrend
```json
{
  "technical_filters": {
    "ma_trend": "bullish"
  }
}
```

#### `price_change_1m_min` (number, -100 to 1000)
Minimum 1-month price change percentage.

**Example**: Find ETFs up at least 5% in last month
```json
{
  "technical_filters": {
    "price_change_1m_min": 5.0
  }
}
```

#### `price_change_1m_max` (number, -100 to 1000)
Maximum 1-month price change percentage.

**Example**: Find stable ETFs (not up more than 10%)
```json
{
  "technical_filters": {
    "price_change_1m_max": 10.0
  }
}
```

#### `volume_avg_20d_min` (number, >= 0)
Minimum 20-day average volume. Use as proxy for liquidity and ETF size.

**Example**: Find liquid ETFs
```json
{
  "technical_filters": {
    "volume_avg_20d_min": 1000000
  }
}
```

---

### 3. Global Parameters

#### `region` (string, default: "KR")
Market region. Currently only "KR" supported.

#### `limit` (number, 1-200, default: 50)
Maximum number of results to return.

---

## Usage Examples

### Example 1: Find Top Semiconductor ETFs

**Objective**: Find liquid semiconductor ETFs with bullish momentum.

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "반도체"
    },
    "technical_filters": {
      "ma_trend": "bullish",
      "volume_avg_20d_min": 500000
    },
    "region": "KR",
    "limit": 10
  }
}
```

**Expected Result**:
- ETFs with "반도체" in name
- Moving averages in bullish configuration
- Average daily volume > 500,000 shares
- Up to 10 results

---

### Example 2: Find Oversold Broad Market ETFs

**Objective**: Find KOSPI 200 tracking ETFs that are oversold (RSI < 30).

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "200"
    },
    "technical_filters": {
      "rsi_max": 30
    },
    "region": "KR",
    "limit": 5
  }
}
```

**Use Case**: Potential buying opportunities for broad market ETFs.

---

### Example 3: Find Recently Listed Tech ETFs

**Objective**: Find newer IT/Tech ETFs for emerging sector exposure.

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "IT",
      "listing_date_after": "2020-01-01"
    },
    "region": "KR",
    "limit": 15
  }
}
```

---

### Example 4: Find Stable Dividend ETFs

**Objective**: Find ETFs with stable performance (not too volatile).

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "배당"
    },
    "technical_filters": {
      "price_change_1m_min": -5.0,
      "price_change_1m_max": 5.0,
      "volume_avg_20d_min": 100000
    },
    "region": "KR",
    "limit": 10
  }
}
```

**Criteria**:
- Dividend-focused ETFs (name contains "배당")
- Not down/up more than 5% in last month
- Reasonable liquidity (100K+ daily volume)

---

### Example 5: Scan All ETFs for Market Overview

**Objective**: Get a broad view of the ETF market.

```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {},
    "region": "KR",
    "limit": 100
  }
}
```

**Result**: Returns first 100 ETFs (alphabetically by name) with all available data.

---

## Known Limitations

### 1. Missing AUM (Assets Under Management)

**Impact**: Cannot directly filter by ETF size.

**Workaround**: Use `volume_avg_20d_min` as proxy for liquidity/popularity:
- **Large ETFs**: volume_avg_20d > 2,000,000
- **Medium ETFs**: volume_avg_20d 500,000 - 2,000,000
- **Small ETFs**: volume_avg_20d < 500,000

**Example**:
```json
{
  "technical_filters": {
    "volume_avg_20d_min": 2000000  // Proxy for large-cap ETFs
  }
}
```

---

### 2. Missing TER (Total Expense Ratio)

**Impact**: Cannot filter by management fees.

**Workaround**: Generally, larger ETFs (higher volume) have lower expense ratios due to economies of scale. Focus on volume as size proxy.

**Alternative**: Check ETF provider websites manually:
- Samsung Asset Management
- Mirae Asset
- KB Asset Management
- Kiwoom Securities

---

### 3. Missing Tracking Error

**Impact**: Cannot directly assess how well ETF tracks its index.

**Workaround**: Compare ETF price movements to relevant index:
1. Use `screen_etfs` to find ETF (e.g., "KODEX 200")
2. Use `query_ohlcv_data` to get OHLCV for both ETF and KOSPI 200
3. Calculate correlation manually

---

### 4. Sector/Theme Approximation

**Impact**: Sector classification based on name parsing, not official categorization.

**Keyword Mapping** (see [`etf_screening_adapter.py`](../modules/screening/etf_screening_adapter.py)):
```python
SECTOR_KEYWORDS = {
    "반도체": "Semiconductor",
    "배터리": "Battery",
    "2차전지": "Secondary Battery",
    "바이오": "Bio/Healthcare",
    "금융": "Finance",
    "IT": "Information Technology",
    # ... etc
}
```

**Best Practice**: Use broad name patterns and verify results manually:
```json
{
  "filters": {
    "name_pattern": "반도체"  // Matches "KODEX 반도체", "TIGER 반도체", etc.
  }
}
```

---

## Workarounds and Best Practices

### Best Practice 1: Use Volume as Size Proxy

Since AUM data is unavailable, use average volume to identify large/popular ETFs:

```json
{
  "technical_filters": {
    "volume_avg_20d_min": 1000000  // Liquid, likely large AUM
  }
}
```

### Best Practice 2: Combine Multiple Filters

More filters = more precise results:

```json
{
  "filters": {
    "name_pattern": "반도체",
    "listing_date_after": "2018-01-01"
  },
  "technical_filters": {
    "ma_trend": "bullish",
    "rsi_max": 70,
    "volume_avg_20d_min": 500000
  }
}
```

### Best Practice 3: Sector Discovery via Name Patterns

Find all ETFs in a sector using name keywords:

**Semiconductor**:
```json
{"filters": {"name_pattern": "반도체"}}
```

**Battery/Energy Storage**:
```json
{"filters": {"name_pattern": "배터리"}}
// OR
{"filters": {"name_pattern": "2차전지"}}
```

**Broad Market**:
```json
{"filters": {"name_pattern": "200"}}
// OR
{"filters": {"name_pattern": "코스피"}}
```

### Best Practice 4: Use get_technical_indicators for Deep Dive

For detailed technical analysis of specific ETFs:

1. Use `screen_etfs` to find candidates
2. Use `get_technical_indicators` for full indicator set:

```json
{
  "tool": "get_technical_indicators",
  "arguments": {
    "tickers": ["069500", "102110", "091160"],
    "region": "KR",
    "indicators": ["all"],
    "period_days": 400
  }
}
```

---

## Response Format

### Success Response

```json
{
  "success": true,
  "etfs": [
    {
      "ticker": "091160",
      "name": "KODEX 반도체",
      "listing_date": "2015-05-08",
      "sector_theme": "Semiconductor",
      "current_price": 45000,
      "price_change_1m": 8.5,
      "volume_avg_20d": 2500000,
      "rsi": 65.0,
      "rsi_signal": "neutral",
      "ma_trend": "bullish",
      "ma20": 44000,
      "ma50": 43000,
      "ma200": 40000,
      "price_vs_ma20": "above"
    },
    // ... more ETFs
  ],
  "count": 5,
  "total_matching": 43,
  "filters_applied": {
    "name_pattern": "반도체"
  },
  "technical_filters_applied": {
    "ma_trend": "bullish"
  },
  "region": "KR",
  "timestamp": "2025-10-31T14:30:00",
  "limitations": [
    "AUM (Assets Under Management) data not readily available",
    "TER (Total Expense Ratio) data requires complex web scraping",
    "Tracking Error data has limited availability",
    "Sector/Theme approximated from ETF name parsing",
    "Use average volume as proxy for ETF size/liquidity"
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | string | 6-digit ETF ticker code |
| `name` | string | ETF name (Korean) |
| `listing_date` | string | ETF listing date (YYYY-MM-DD) |
| `sector_theme` | string | Parsed sector/theme or "General" |
| `current_price` | number | Latest closing price |
| `price_change_1m` | number | 1-month price change % |
| `volume_avg_20d` | number | 20-day average volume |
| `rsi` | number | 14-period RSI (0-100) |
| `rsi_signal` | string | "oversold", "neutral", "overbought" |
| `ma_trend` | string | "bullish", "neutral", "bearish" |
| `ma20`, `ma50`, `ma200` | number | Moving average values |
| `price_vs_ma20` | string | "above", "at", "below" |

### Error Response

```json
{
  "success": false,
  "error": "Invalid filter: aum_min",
  "filters": {...},
  "technical_filters": {...},
  "region": "KR"
}
```

---

## Optional Enhancements

### ETF Fundamental Scorer (Optional)

The `screen_etfs` tool returns ETFs sorted by name by default. For users who want **quantitative scoring and ranking**, the **ETFFundamentalScorer** is available as an optional post-processing utility.

**Purpose**: Provides composite scores for ETFs based on:
- **Liquidity Score (40%)**: Volume as AUM proxy
- **Momentum Score (30%)**: 1-month price change
- **Technical Score (30%)**: RSI + MA trend

**Key Features**:
- ✅ **Composite Scoring**: 0-100 scale (higher = better opportunity)
- ✅ **Sector-Based Normalization**: Fair comparison within sectors
- ✅ **Ranking**: Overall rank and sector rank
- ✅ **Top N by Sector**: Extract best performers per sector

**Usage Example**:

```python
from modules.screening.etf_screening_adapter import ETFScreeningAdapter
from modules.screening.etf_fundamental_scorer import ETFFundamentalScorer

# Step 1: Get ETFs using screen_etfs
adapter = ETFScreeningAdapter()
result = await adapter.screen_etfs(
    filters={"name_pattern": "반도체"},
    technical_filters={"ma_trend": "bullish"},
    region="KR"
)

# Step 2: Apply optional scoring
scorer = ETFFundamentalScorer()
scored_etfs = scorer.calculate_scores(
    result["etfs"],
    use_zscore=True,
    sector_based=True  # Normalize within sectors for fair comparison
)

# Step 3: Rank by sector
ranked = scorer.rank_by_sector(scored_etfs)

# Step 4: Get top 3 from each sector
top_by_sector = scorer.get_top_by_sector(ranked, top_n=3)

# Result: ETFs with composite_score, normalized_score, sector_rank, overall_rank
```

**Output Fields Added**:
- `liquidity_score`: 0-100 (volume-based)
- `momentum_score`: 0-100 (1-month price change)
- `technical_score`: 0-100 (RSI + MA trend)
- `composite_score`: 0-100 (weighted combination)
- `z_score`: Z-score within sector or overall
- `normalized_score`: 0-100 (mean=50, std=15)
- `sector_rank`: Rank within sector (1 = best)
- `overall_rank`: Overall rank across all ETFs

**When to Use**:
- ✅ Comparing ETFs within the same sector (e.g., "Which semiconductor ETF is best?")
- ✅ Building quantitative ETF selection strategies
- ✅ Ranking large result sets (>20 ETFs)
- ✅ Systematic portfolio construction

**When NOT to Use**:
- ❌ Qualitative research (manual selection)
- ❌ Small result sets (<5 ETFs) - scoring adds little value
- ❌ Cross-sector comparison without normalization (scores not comparable)

**Test Script**: See [test_etf_scorer.py](test_etf_scorer.py:1-200) for complete examples.

---

## Troubleshooting

### Issue 1: No Results Returned

**Symptoms**: `count: 0`, `total_matching: 0`

**Possible Causes**:
1. Filters too restrictive
2. Name pattern too specific
3. Technical criteria impossible to meet

**Solutions**:
- Remove some filters and try again
- Broaden name pattern (use shorter keywords)
- Check if technical filter ranges are realistic

**Example Debug Workflow**:
```json
// Step 1: Try without technical filters
{"filters": {"name_pattern": "반도체"}}

// Step 2: If results found, add technical filters one by one
{"filters": {"name_pattern": "반도체"}, "technical_filters": {"ma_trend": "bullish"}}

// Step 3: Narrow further if too many results
{"filters": {"name_pattern": "반도체"}, "technical_filters": {"ma_trend": "bullish", "rsi_max": 70}}
```

---

### Issue 2: Too Many Results

**Symptoms**: `count: 200`, `total_matching: 500+`

**Solution**: Add more filters or reduce `limit`

**Example**:
```json
{
  "filters": {
    "name_pattern": "KODEX"  // Too broad - 200+ KODEX ETFs
  },
  "limit": 50  // Still too many
}

// Better:
{
  "filters": {
    "name_pattern": "KODEX 반도체"  // More specific
  },
  "technical_filters": {
    "volume_avg_20d_min": 500000  // Add liquidity filter
  },
  "limit": 20
}
```

---

### Issue 3: ETFs Missing Technical Indicators

**Symptoms**: Some ETFs in results have `null` values for RSI, MA trends

**Cause**: Insufficient OHLCV data (newly listed ETFs, illiquid ETFs)

**Solution**: Filter by listing date and volume:
```json
{
  "filters": {
    "listing_date_before": "2023-12-31"  // Exclude very new ETFs
  },
  "technical_filters": {
    "volume_avg_20d_min": 10000  // Exclude illiquid ETFs
  }
}
```

---

### Issue 4: Sector Classification Incorrect

**Symptoms**: ETF classified as "General" instead of specific sector

**Cause**: Name doesn't contain known keywords

**Solution**: Use name pattern directly instead of relying on sector:
```json
{
  "filters": {
    "name_pattern": "게임"  // Gaming ETFs
  }
}
```

If many results are "General" sector, they may be multi-sector or leveraged ETFs.

---

## Performance Notes

### Query Performance

- **Simple name filter**: <1s for 1,000+ ETFs
- **With technical filters**: 1-2s (requires OHLCV fetch + calculation)
- **All ETFs (no filter)**: 2-3s (calculates indicators for all 1,061 ETFs)

### Caching

- **Cache TTL**: 60 seconds
- **Cache Key**: Based on all filters + region + limit
- **Cache Hit**: <100ms response time

**Tip**: Identical queries within 60 seconds return cached results instantly.

---

## Related Tools

### `screen_stocks`
Similar tool for individual stocks with fundamental filters (P/E, P/B, dividend yield).

**Use Case**: Stock screening vs ETF screening.

### `get_technical_indicators`
Get detailed technical indicators for specific tickers.

**Use Case**: Deep dive after finding candidate ETFs via `screen_etfs`.

### `query_ohlcv_data`
Fetch raw OHLCV data for custom analysis.

**Use Case**: Manual tracking error calculation, correlation analysis.

---

## Changelog

### 2025-10-31 - Initial Release (Phase 2 Complete)

**Completed**:
- ✅ ETF screening adapter implementation (743 lines)
- ✅ MCP tool definition and handler
- ✅ Technical indicator integration (RSI, MA trends)
- ✅ Performance metrics calculation (1M change, 20D volume)
- ✅ Sector parsing from ETF names
- ✅ Comprehensive testing (5 test scenarios)
- ✅ User guide documentation

**Deferred** (from Phase 1 Day 2):
- ❌ KRX API data collection (endpoint issues)
- ❌ ETFCheck web scraping (redirect/session issues)
- ❌ Comprehensive ETF fundamentals (AUM, TER, tracking error)

**Rationale**: Deliver working tool with available data rather than spending weeks on web scraping infrastructure.

---

## Support

For issues or feature requests related to the ETF screening tool:

1. **Check Known Limitations** (Section 5) - Many "issues" are documented limitations
2. **Review Workarounds** (Section 6) - Alternative approaches available
3. **Test with Example Queries** (Section 4) - Verify basic functionality
4. **Check Logs** - `logs/YYYYMMDD_quant_platform.log` for detailed errors

**Status Report**: See [`ETF_PHASE1_DAY2_STATUS.md`](ETF_PHASE1_DAY2_STATUS.md) for Phase 1-2 development details.

---

**Last Updated**: 2025-10-31
**Version**: 1.0.0
**Status**: Production Ready ✅
