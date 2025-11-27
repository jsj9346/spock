# Spock MCP Server - User Guide

**Version**: 0.2.0
**Date**: 2025-10-31
**Status**: Phase 1 Week 2 Complete

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Available Tools](#available-tools)
4. [Usage Examples](#usage-examples)
5. [Error Handling](#error-handling)
6. [Performance](#performance)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 17+ with TimescaleDB extension
- Claude Code installed and configured
- Spock project environment set up

### Installation

1. **Install Dependencies**:
```bash
cd ~/spock
pip install -r requirements_quant.txt
```

2. **Configure Environment**:
```bash
# Create .env file with database credentials
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

3. **Verify Installation**:
```bash
python3 -m mcp_server.server
# Should initialize without errors
```

---

## Configuration

### MCP Server Configuration

The Spock MCP server is configured via `.claude/mcp_config.json`:

```json
{
  "mcpServers": {
    "spock": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/13ruce/spock",
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "quant_platform",
        "POSTGRES_USER": "bruce"
      }
    }
  }
}
```

### Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `command` | Python interpreter | `python3` |
| `args` | Server module path | `["-m", "mcp_server.server"]` |
| `cwd` | Working directory | `/Users/13ruce/spock` |
| `env.POSTGRES_HOST` | PostgreSQL host | `localhost` |
| `env.POSTGRES_PORT` | PostgreSQL port | `5432` |
| `env.POSTGRES_DB` | Database name | `quant_platform` |
| `env.POSTGRES_USER` | Database user | `bruce` |

**Note**: PostgreSQL password should be in `.env` file, not in MCP config for security.

---

## Available Tools

### query_ohlcv_data

Get OHLCV (Open, High, Low, Close, Volume) historical data for stock tickers.

**Signature**:
```typescript
query_ohlcv_data(
  tickers: string[],      // 1-1000 ticker symbols
  start_date: string,     // YYYY-MM-DD format
  end_date: string,       // YYYY-MM-DD format
  region?: "KR" | "US",   // Market region (default: "KR")
  timeframe?: "1d"        // Data timeframe (default: "1d")
): Promise<OHLCVResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `tickers` | `string[]` | ✅ Yes | 1-1000 items | Ticker symbols |
| `start_date` | `string` | ✅ Yes | YYYY-MM-DD | Start date (inclusive) |
| `end_date` | `string` | ✅ Yes | YYYY-MM-DD | End date (inclusive) |
| `region` | `string` | No | "KR" \| "US" | Market region |
| `timeframe` | `string` | No | "1d" | Data timeframe |

**Ticker Format Validation**:
- **KR (Korean)**: 6-digit numeric (e.g., `005930` for Samsung Electronics)
- **US (American)**: 1-5 uppercase letters (e.g., `AAPL` for Apple Inc.)

**Date Range Validation**:
- Format: `YYYY-MM-DD` (ISO 8601)
- Start date must be before end date
- Maximum range: 10 years (3650 days)
- Handles leap years correctly

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {
        "date": "2024-01-01",
        "open": 75000,
        "high": 76000,
        "low": 74000,
        "close": 75500,
        "volume": 1000000
      },
      ...
    ]
  },
  "metadata": {
    "record_count": 245,
    "tickers": ["005930"]
  }
}
```

### run_backtest

Execute strategy backtests with vectorbt or custom engine.

**Signature**:
```typescript
run_backtest(
  strategy_type: "momentum" | "value" | "momentum_value" | "fundamental_quality_growth",
  tickers: string[],          // 1-100 ticker symbols
  start_date: string,         // YYYY-MM-DD format
  end_date: string,           // YYYY-MM-DD format
  region?: "KR" | "US",       // Market region (default: "KR")
  engine?: "vectorbt" | "custom",  // Engine (default: "vectorbt")
  initial_capital?: number,   // Starting capital (default: 100M KRW)
  risk_profile?: "conservative" | "moderate" | "aggressive",
  parameters?: object         // Strategy-specific parameters (optional)
): Promise<BacktestResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `strategy_type` | `string` | ✅ Yes | momentum \| value \| momentum_value \| fundamental_quality_growth | Strategy to backtest |
| `tickers` | `string[]` | ✅ Yes | 1-100 items | Ticker symbols |
| `start_date` | `string` | ✅ Yes | YYYY-MM-DD | Start date (inclusive) |
| `end_date` | `string` | ✅ Yes | YYYY-MM-DD | End date (inclusive) |
| `region` | `string` | No | KR \| US | Market region (default: KR) |
| `engine` | `string` | No | vectorbt \| custom | Backtest engine (default: vectorbt) |
| `initial_capital` | `number` | No | ≥1M | Starting capital (default: 100M KRW) |
| `risk_profile` | `string` | No | conservative \| moderate \| aggressive | Risk profile (default: moderate) |

**Output Format**:
```json
{
  "success": true,
  "engine": "vectorbt",
  "performance": {
    "total_return": 0.45,
    "annualized_return": 0.35,
    "sharpe_ratio": 1.65,
    "sortino_ratio": 2.10,
    "calmar_ratio": 1.85,
    "max_drawdown": -0.12,
    "max_drawdown_duration": 45
  },
  "trades": {
    "total_trades": 125,
    "win_rate": 0.583,
    "avg_win": 0.048,
    "avg_loss": -0.032,
    "profit_factor": 1.85
  },
  "execution": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "duration_days": 365,
    "initial_capital": 100000000,
    "execution_time": 0.85
  }
}
```

**Strategy Types**:

1. **momentum**: RSI + Moving Average Crossover
   - Entry: RSI oversold + fast MA > slow MA
   - Exit: RSI overbought OR fast MA < slow MA
   - Parameters: `rsi_period`, `rsi_oversold`, `rsi_overbought`, `ma_fast`, `ma_slow`

2. **value**: Buy-and-hold placeholder (⚠️ basic implementation)
   - Entry: Start of period
   - Exit: End of period
   - Note: Limited functionality, use `fundamental_quality_growth` for real fundamental strategies

3. **momentum_value**: Combined momentum + value
   - Entry: Both momentum AND value signals agree
   - Exit: Either momentum OR value signals exit
   - Parameters: Inherits from momentum strategy

4. **fundamental_quality_growth**: ✨ **NEW** Fundamental screening with annual rebalancing
   - Screens stocks by: High ROE, Low debt, High profit growth, High revenue growth
   - Rebalances: Annually (configurable)
   - Allocation: Equal-weight to top N stocks
   - **Parameters**:
     - `roe_min` (default: 15.0): Minimum ROE threshold (%)
     - `debt_to_equity_max` (default: 100.0): Maximum debt-to-equity ratio (%)
     - `net_income_growth_min` (default: 10.0): Minimum net income growth YOY (%)
     - `revenue_growth_min` (default: 10.0): Minimum revenue growth YOY (%)
     - `top_n` (default: 10): Number of stocks to select
     - `rebalance_freq_days` (default: 252): Days between rebalances (252 = annual)

**Example: Fundamental Quality + Growth Strategy**

```json
{
  "tool": "run_backtest",
  "arguments": {
    "strategy_type": "fundamental_quality_growth",
    "tickers": ["005930", "000660", "035420", "035720", "005380", "000270", "005490", "051910", "006400", "028260"],
    "start_date": "2022-01-01",
    "end_date": "2024-12-31",
    "region": "KR",
    "engine": "vectorbt",
    "initial_capital": 100000000,
    "parameters": {
      "roe_min": 15.0,
      "debt_to_equity_max": 100.0,
      "net_income_growth_min": 10.0,
      "revenue_growth_min": 10.0,
      "top_n": 10,
      "rebalance_freq_days": 252
    }
  }
}
```

This strategy will:
1. Screen stocks annually by ROE ≥15%, Debt/Equity ≤100%, profit growth ≥10%, revenue growth ≥10%
2. Select top 10 stocks that pass all criteria
3. Allocate equal weight (10% each) to selected stocks
4. Rebalance after 252 days (1 year)

### optimize_strategy

Run walk-forward optimization to find optimal strategy parameters.

**Signature**:
```typescript
optimize_strategy(
  strategy_type: "momentum" | "value" | "momentum_value",
  tickers: string[],          // 1-100 ticker symbols
  start_date: string,         // YYYY-MM-DD format
  end_date: string,           // YYYY-MM-DD format
  region?: "KR" | "US",       // Market region (default: "KR")
  param_grid?: object,        // Parameter grid (optional)
  train_period_days?: number, // Training period (default: 252)
  test_period_days?: number,  // Testing period (default: 63)
  metric?: string,            // Optimization metric (default: "sharpe_ratio")
  anchored?: boolean          // Anchored windows (default: false)
): Promise<OptimizationResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `strategy_type` | `string` | ✅ Yes | momentum \| value \| momentum_value | Strategy to optimize |
| `tickers` | `string[]` | ✅ Yes | 1-100 items | Ticker symbols |
| `start_date` | `string` | ✅ Yes | YYYY-MM-DD | Start date (inclusive) |
| `end_date` | `string` | ✅ Yes | YYYY-MM-DD | End date (inclusive) |
| `region` | `string` | No | KR \| US | Market region (default: KR) |
| `param_grid` | `object` | No | Dict[str, List] | Parameters to search |
| `train_period_days` | `number` | No | 30-1825 | Training period (default: 252) |
| `test_period_days` | `number` | No | 10-365 | Testing period (default: 63) |
| `metric` | `string` | No | sharpe_ratio \| sortino_ratio \| total_return \| annualized_return \| calmar_ratio | Optimization metric |
| `anchored` | `boolean` | No | true \| false | Use anchored windows (default: false) |

**Default Parameter Grids**:
- **Momentum**: `{"rsi_period": [10, 14, 20], "oversold": [20, 30], "overbought": [70, 80]}`
- **Value**: `{"pe_threshold": [10, 15, 20], "pb_threshold": [1.0, 1.5, 2.0]}`
- **Momentum+Value**: Combination of both grids

**Output Format**:
```json
{
  "success": true,
  "strategy_type": "momentum",
  "optimization": {
    "best_params": {
      "rsi_period": 14,
      "oversold": 30,
      "overbought": 70
    },
    "metric_used": "sharpe_ratio"
  },
  "validation": {
    "in_sample_performance": {
      "mean": 1.85,
      "std": 0.15,
      "min": 1.65,
      "max": 2.05
    },
    "out_of_sample_performance": {
      "mean": 1.65,
      "std": 0.22,
      "min": 1.42,
      "max": 1.88
    },
    "degradation_pct": 0.108,
    "robustness_score": 0.78,
    "overfitting_detected": false,
    "recommendation": "GOOD: Robustness score 0.78, strategy is recommended for deployment"
  }
}
```

### list_available_tickers

List all available ticker symbols in the database.

**Signature**:
```typescript
list_available_tickers(
  region?: "KR" | "US",       // Filter by region (optional)
  sector?: string,            // Filter by sector (optional)
  limit?: number              // Limit results (default: 1000)
): Promise<TickersResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `region` | `string` | No | KR \| US | Filter by market region |
| `sector` | `string` | No | Any | Filter by sector name |
| `limit` | `number` | No | 1-10000 | Maximum results (default: 1000) |

**Output Format**:
```json
{
  "success": true,
  "count": 2,
  "filters": {
    "region": "KR",
    "sector": "Technology",
    "limit": 1000
  },
  "tickers": [
    {
      "ticker": "005930",
      "region": "KR",
      "name": "Samsung Electronics",
      "sector": "Technology"
    },
    {
      "ticker": "000660",
      "region": "KR",
      "name": "SK Hynix",
      "sector": "Technology"
    }
  ]
}
```

### get_system_status

Get database health and data availability status.

**Signature**:
```typescript
get_system_status(): Promise<SystemStatusResponse>
```

**Input Parameters**: None

**Output Format**:
```json
{
  "success": true,
  "status": "healthy",
  "database": {
    "connected": true,
    "version": "PostgreSQL 17.0",
    "size": "500 MB"
  },
  "data": {
    "total_tickers": 1500,
    "ticker_counts_by_region": {
      "KR": 1000,
      "US": 500
    },
    "ohlcv_records": 50000,
    "latest_date": "2024-10-30",
    "days_since_update": 1
  }
}
```

---

### screen_etfs

Screen Korean ETFs by name pattern, listing date, and technical indicators.

**Signature**:
```typescript
screen_etfs(
  filters?: {
    name_pattern?: string,
    listing_date_after?: string,
    listing_date_before?: string
  },
  technical_filters?: {
    rsi_min?: number,
    rsi_max?: number,
    ma_trend?: "bullish" | "bearish" | "neutral",
    price_change_1m_min?: number,
    price_change_1m_max?: number,
    volume_avg_20d_min?: number
  },
  region?: "KR",
  limit?: number
): Promise<ETFScreeningResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `filters.name_pattern` | string | No | Filter by ETF name substring (e.g., "반도체" for semiconductor, "KODEX", "200") |
| `filters.listing_date_after` | string | No | Filter ETFs listed after this date (YYYY-MM-DD) |
| `filters.listing_date_before` | string | No | Filter ETFs listed before this date (YYYY-MM-DD) |
| `technical_filters.rsi_min` | number | No | Minimum RSI value (0-100) |
| `technical_filters.rsi_max` | number | No | Maximum RSI value (0-100, e.g., 30 for oversold) |
| `technical_filters.ma_trend` | string | No | Required MA trend: "bullish" (MA20>MA50>MA200), "bearish" (opposite), "neutral" (mixed) |
| `technical_filters.price_change_1m_min` | number | No | Minimum 1-month price change % (e.g., -10.0 for decline >-10%) |
| `technical_filters.price_change_1m_max` | number | No | Maximum 1-month price change % (e.g., 50.0 for moderate gains) |
| `technical_filters.volume_avg_20d_min` | number | No | Minimum 20-day average volume (proxy for liquidity/size) |
| `region` | string | No | Market region (default: "KR", currently only KR supported) |
| `limit` | number | No | Maximum results to return (default: 50, max: 200) |

**Output Format**:
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
      "ma200": 40000
    }
  ],
  "count": 5,
  "total_matching": 8,
  "filters_applied": {
    "name_pattern": "반도체"
  },
  "technical_filters_applied": {
    "ma_trend": "bullish",
    "rsi_max": 70
  },
  "region": "KR",
  "limitations": [
    "AUM data not available - use volume as liquidity proxy",
    "TER data not available",
    "Sector/theme approximated from ETF name",
    "Tracking error calculation pending"
  ]
}
```

**Known Limitations**:
- **AUM Data Not Available**: Use `volume_avg_20d` as a proxy for fund size and liquidity
- **TER Data Not Available**: Expense ratio information not included
- **Sector Classification**: Approximated from ETF names (~70% accuracy) using keyword matching
- **Tracking Error**: Not yet calculated (planned for future enhancement)

**Usage Examples**:

1. **Find Semiconductor ETFs**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "반도체"
    },
    "region": "KR",
    "limit": 20
  }
}
```

2. **Find Bullish ETFs with Moderate RSI**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "technical_filters": {
      "ma_trend": "bullish",
      "rsi_max": 70
    },
    "region": "KR",
    "limit": 50
  }
}
```

3. **Sector Comparison (Battery ETFs with Performance Filters)**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "배터리"
    },
    "technical_filters": {
      "price_change_1m_min": -20.0,
      "volume_avg_20d_min": 100000
    },
    "region": "KR"
  }
}
```

---

### query_dividend_history

Get dividend payment history and growth analysis for stocks.

**Signature**:
```typescript
query_dividend_history(
  tickers: string[],              // 1-20 ticker symbols
  years?: number,                 // Years of history (1-10, default: 5)
  include_growth_analysis?: boolean,  // Include CAGR/streak analysis (default: true)
  include_upcoming?: boolean,     // Include upcoming dividends (default: true)
  region?: "KR" | "US" | "JP" | "HK" | "CN" | "VN"  // Market region (default: "KR")
): Promise<DividendResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `tickers` | `string[]` | ✅ Yes | 1-20 items | Ticker symbols |
| `years` | `number` | No | 1-10 | Years of history (default: 5) |
| `include_growth_analysis` | `boolean` | No | true/false | Include CAGR and streak analysis |
| `include_upcoming` | `boolean` | No | true/false | Include upcoming dividend dates |
| `region` | `string` | No | KR \| US \| JP \| HK \| CN \| VN | Market region (default: KR) |

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "region": "KR",
      "currency": "KRW",
      "has_dividends": true,
      "dividend_history": [
        {
          "fiscal_year": 2024,
          "dividend_type": "annual",
          "dividend_per_share": 1444,
          "dividend_yield": 2.15,
          "ex_dividend_date": "2024-12-28",
          "payment_date": "2025-04-15"
        }
      ],
      "growth_analysis": {
        "dividend_cagr_3y": 0.082,
        "dividend_cagr_5y": 0.105,
        "consecutive_years": 23,
        "dividend_streak": "dividend_achiever",
        "average_payout_ratio": 22.5
      },
      "summary": {
        "annual_dividend_current": 1444,
        "annual_dividend_last_year": 1444,
        "payments_current_year": 1,
        "dividend_types": ["annual"]
      }
    }
  },
  "metadata": {
    "ticker_count": 1,
    "region": "KR",
    "query_time": "2025-11-27T10:00:00"
  }
}
```

**Dividend Streak Types**:
- `dividend_aristocrat`: 25+ consecutive years of dividends
- `dividend_achiever`: 10+ consecutive years
- `stable`: 5+ consecutive years
- `maintained`: 1-4 consecutive years
- `none`: No recent dividends

---

### calculate_financial_ratios

Calculate financial ratios from fundamental data with interpretation.

**Signature**:
```typescript
calculate_financial_ratios(
  tickers: string[],              // 1-20 ticker symbols
  ratio_categories?: string[],   // Categories to calculate (default: ["all"])
  period_type?: "ANNUAL" | "QUARTERLY",  // Data period (default: "ANNUAL")
  include_interpretation?: boolean,  // Include interpretation (default: true)
  region?: "KR" | "US" | "JP" | "HK" | "CN" | "VN"  // Market region (default: "KR")
): Promise<RatiosResponse>
```

**Input Parameters**:

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `tickers` | `string[]` | ✅ Yes | 1-20 items | Ticker symbols |
| `ratio_categories` | `string[]` | No | See below | Categories to calculate |
| `period_type` | `string` | No | ANNUAL \| QUARTERLY | Data period type |
| `include_interpretation` | `boolean` | No | true/false | Include health assessment |
| `region` | `string` | No | KR \| US \| JP \| HK \| CN \| VN | Market region |

**Available Ratio Categories**:
- `liquidity`: current_ratio, quick_ratio, cash_ratio
- `cash_position`: cash_to_assets, net_cash_position
- `leverage`: debt_ratio, debt_to_assets, interest_coverage
- `profitability`: gross_margin, operating_margin, net_margin, roe, roa, ebitda_margin
- `efficiency`: asset_turnover, inventory_turnover, receivables_turnover, inventory_days, receivables_days
- `dividend`: dividend_yield, dividend_payout_ratio
- `all`: All categories (default)

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "fiscal_year": 2024,
      "period_type": "ANNUAL",
      "ratios": {
        "liquidity": {
          "current_ratio": {
            "value": 2.58,
            "unit": "times",
            "korean": "유동비율",
            "interpretation": "양호한 유동성",
            "health_status": "healthy"
          },
          "cash_ratio": {
            "value": 0.85,
            "unit": "times",
            "korean": "현금비율",
            "interpretation": "적정 현금 보유",
            "health_status": "healthy"
          }
        },
        "efficiency": {
          "inventory_turnover": {
            "value": 6.2,
            "unit": "times",
            "korean": "재고회전율",
            "interpretation": "빠른 재고 회전",
            "health_status": "healthy"
          },
          "inventory_days": {
            "value": 58.9,
            "unit": "days",
            "korean": "재고자산회전일수",
            "interpretation": "적정 재고 회전 기간",
            "health_status": "healthy"
          },
          "receivables_turnover": {
            "value": 8.5,
            "unit": "times",
            "korean": "매출채권회전율",
            "interpretation": "빠른 채권 회수",
            "health_status": "healthy"
          },
          "receivables_days": {
            "value": 42.9,
            "unit": "days",
            "korean": "매출채권회전일수",
            "interpretation": "적정 채권 회수 기간",
            "health_status": "healthy"
          }
        }
      },
      "summary": {
        "overall_health": "healthy",
        "strengths": ["Strong liquidity", "High profitability"],
        "concerns": [],
        "recommendation": "Financially strong company"
      }
    }
  },
  "metadata": {
    "ticker_count": 1,
    "categories": ["liquidity", "efficiency"],
    "ratios_calculated": 8,
    "region": "KR",
    "query_time": "2025-11-27T10:00:00"
  }
}
```

**Health Status Values**:
- `healthy`: Ratio is within optimal range
- `warning`: Ratio requires attention
- `critical`: Ratio indicates potential issues

---

## Usage Examples

### Example 1: Single Ticker Query (Korean Market)

**Request**:
```
Get Samsung Electronics (005930) OHLCV data for 2024.
```

**Tool Call**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["005930"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "region": "KR"
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {"date": "2024-01-02", "open": 76100, "high": 76800, "low": 75600, "close": 76200, "volume": 15234567},
      {"date": "2024-01-03", "open": 76200, "high": 77500, "low": 76000, "close": 77200, "volume": 18456789},
      ...
    ]
  },
  "metadata": {
    "record_count": 245,
    "tickers": ["005930"]
  }
}
```

### Example 2: Multiple Tickers (Batch Query)

**Request**:
```
Get OHLCV data for Samsung (005930), SK Hynix (000660), and Naver (035420) for Q1 2024.
```

**Tool Call**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["005930", "000660", "035420"],
    "start_date": "2024-01-01",
    "end_date": "2024-03-31",
    "region": "KR"
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "005930": [...],
    "000660": [...],
    "035420": [...]
  },
  "metadata": {
    "record_count": 180,
    "tickers": ["005930", "000660", "035420"]
  }
}
```

### Example 3: US Market Query

**Request**:
```
Get Apple (AAPL) stock data for January 2024.
```

**Tool Call**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["AAPL"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "region": "US"
  }
}
```

### Example 4: Run Momentum Strategy Backtest

**Request**:
```
Backtest a momentum strategy on Samsung (005930) for 2024 using vectorbt engine.
```

**Tool Call**:
```json
{
  "tool": "run_backtest",
  "arguments": {
    "strategy_type": "momentum",
    "tickers": ["005930"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "region": "KR",
    "engine": "vectorbt",
    "initial_capital": 100000000
  }
}
```

**Response**:
```json
{
  "success": true,
  "engine": "vectorbt",
  "performance": {
    "total_return": 0.38,
    "annualized_return": 0.38,
    "sharpe_ratio": 1.52,
    "sortino_ratio": 1.95,
    "calmar_ratio": 1.72,
    "max_drawdown": -0.14,
    "max_drawdown_duration": 52
  },
  "trades": {
    "total_trades": 105,
    "win_rate": 0.565,
    "avg_win": 0.045,
    "avg_loss": -0.028,
    "profit_factor": 1.75
  },
  "execution": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "duration_days": 365,
    "initial_capital": 100000000,
    "execution_time": 0.92
  }
}
```

### Example 5: Optimize Strategy Parameters

**Request**:
```
Find optimal RSI parameters for momentum strategy on Samsung (005930) using walk-forward optimization.
```

**Tool Call**:
```json
{
  "tool": "optimize_strategy",
  "arguments": {
    "strategy_type": "momentum",
    "tickers": ["005930"],
    "start_date": "2022-01-01",
    "end_date": "2024-12-31",
    "region": "KR",
    "param_grid": {
      "rsi_period": [10, 14, 20],
      "oversold": [20, 30],
      "overbought": [70, 80]
    },
    "train_period_days": 252,
    "test_period_days": 63,
    "metric": "sharpe_ratio"
  }
}
```

**Response**:
```json
{
  "success": true,
  "strategy_type": "momentum",
  "optimization": {
    "best_params": {
      "rsi_period": 14,
      "oversold": 30,
      "overbought": 70
    },
    "metric_used": "sharpe_ratio"
  },
  "validation": {
    "in_sample_performance": {
      "mean": 1.85,
      "std": 0.15,
      "min": 1.65,
      "max": 2.05
    },
    "out_of_sample_performance": {
      "mean": 1.65,
      "std": 0.22,
      "min": 1.42,
      "max": 1.88
    },
    "degradation_pct": 0.108,
    "robustness_score": 0.78,
    "overfitting_detected": false,
    "recommendation": "GOOD: Robustness score 0.78, strategy is recommended for deployment"
  },
  "windows": [
    {
      "window_id": 0,
      "train_start": "2022-01-01",
      "train_end": "2023-01-01",
      "test_start": "2023-01-02",
      "test_end": "2023-04-02",
      "best_params": {"rsi_period": 14},
      "train_score": 1.85,
      "test_score": 1.65,
      "degradation": 0.108
    }
  ]
}
```

### Example 6: List Available Tickers

**Request**:
```
List all Technology sector stocks in the Korean market.
```

**Tool Call**:
```json
{
  "tool": "list_available_tickers",
  "arguments": {
    "region": "KR",
    "sector": "Technology",
    "limit": 100
  }
}
```

**Response**:
```json
{
  "success": true,
  "count": 3,
  "filters": {
    "region": "KR",
    "sector": "Technology",
    "limit": 100
  },
  "tickers": [
    {
      "ticker": "005930",
      "region": "KR",
      "name": "Samsung Electronics",
      "sector": "Technology"
    },
    {
      "ticker": "000660",
      "region": "KR",
      "name": "SK Hynix",
      "sector": "Technology"
    },
    {
      "ticker": "035420",
      "region": "KR",
      "name": "Naver",
      "sector": "Technology"
    }
  ]
}
```

### Example 7: Check System Status

**Request**:
```
Check the health and data availability of the Spock MCP server.
```

**Tool Call**:
```json
{
  "tool": "get_system_status",
  "arguments": {}
}
```

**Response**:
```json
{
  "success": true,
  "status": "healthy",
  "database": {
    "connected": true,
    "version": "PostgreSQL 17.0",
    "size": "500 MB"
  },
  "data": {
    "total_tickers": 1500,
    "ticker_counts_by_region": {
      "KR": 1000,
      "US": 500
    },
    "ohlcv_records": 50000,
    "latest_date": "2024-10-30",
    "days_since_update": 1
  }
}
```

---

## Error Handling

### Error Types

The Spock MCP server provides detailed error responses for all failure scenarios:

#### 1. ValidationError (VALIDATION_ERROR)

**Cause**: Invalid input parameters

**Example Scenarios**:
- Invalid ticker format
- Invalid date format
- Date range exceeds maximum
- Empty ticker list
- Too many tickers (>1000)

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid ticker format for region KR",
    "details": {
      "invalid_tickers": ["INVALID"],
      "expected_format": "6-digit numeric"
    }
  }
}
```

#### 2. DataNotFoundError (DATA_NOT_FOUND)

**Cause**: No data available for requested tickers/dates

**Example Scenarios**:
- Ticker not in database
- No data for date range
- Future dates requested

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "DATA_NOT_FOUND",
    "message": "No OHLCV data available for requested tickers/dates",
    "details": {
      "tickers": ["999999"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "region": "KR"
    }
  }
}
```

#### 3. DatabaseError (DATABASE_ERROR)

**Cause**: Database connection or query failure

**Example Scenarios**:
- PostgreSQL connection lost
- Query timeout
- Permission denied

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "DATABASE_ERROR",
    "message": "Failed to query OHLCV data: connection timeout",
    "details": {
      "tickers": ["005930"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    }
  }
}
```

#### 4. InternalError (INTERNAL_ERROR)

**Cause**: Unexpected server error

**Error Response**:
```json
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Unexpected error: ...",
    "details": {
      "type": "RuntimeError"
    }
  }
}
```

---

## Performance

### Performance Targets

| Metric | Target | Achieved |
|--------|--------|----------|
| Cache hit latency | <100ms | ✅ <100ms |
| Cache miss (single) | <200ms | ✅ <200ms |
| Cache miss (batch 20) | <500ms | ✅ <500ms |
| Cache hit rate | >80% | ✅ >85% |
| Database connections | 10-30 pooled | ✅ 10-30 |

### Caching Strategy

The Spock MCP server implements a **two-layer caching** strategy:

**Layer 1: MCP Adapter Cache**
- In-memory dictionary cache
- Cache key: `{tickers}:{start_date}:{end_date}:{region}:{timeframe}`
- Deterministic cache keys (sorted tickers)
- No TTL (session-scoped)

**Layer 2: PostgresDataProvider Cache**
- Inherited from `BaseDataProvider`
- DataFrame caching with size limits
- LRU eviction policy
- Cache hit rate: >85%

### Performance Tips

1. **Batch Queries**: Query multiple tickers in one request for better performance
2. **Reuse Date Ranges**: Identical queries hit cache automatically
3. **Connection Pooling**: Server maintains 10-30 PostgreSQL connections
4. **TimescaleDB Optimization**: Queries leverage chunk exclusion for fast results

---

## Troubleshooting

### Common Issues

#### Issue 1: Server Not Detected by Claude Code

**Symptoms**: Spock server not appearing in Claude Code MCP servers list

**Solutions**:
1. Verify `.claude/mcp_config.json` exists and is valid JSON
2. Restart Claude Code completely
3. Check server initialization: `python3 -m mcp_server.server`
4. Verify working directory is correct in config

#### Issue 2: Database Connection Errors

**Symptoms**: `DATABASE_ERROR` responses

**Solutions**:
1. Verify PostgreSQL is running: `psql --version`
2. Check connection: `psql -d quant_platform`
3. Verify `.env` file has correct credentials
4. Check PostgreSQL logs for errors

#### Issue 3: No Data Returned

**Symptoms**: `DATA_NOT_FOUND` errors for valid tickers

**Solutions**:
1. Verify ticker exists: `SELECT * FROM tickers WHERE ticker='005930' AND region='KR';`
2. Check OHLCV data: `SELECT COUNT(*) FROM ohlcv_data WHERE ticker='005930';`
3. Run data backfill if needed
4. Verify date range overlaps with available data

#### Issue 4: Slow Query Performance

**Symptoms**: Queries taking >1 second

**Solutions**:
1. Check database size: `SELECT pg_size_pretty(pg_database_size('quant_platform'));`
2. Run `ANALYZE` on ohlcv_data table
3. Verify TimescaleDB continuous aggregates
4. Check connection pool: Should show 10-30 connections
5. Enable query logging to identify slow queries

### Debug Logging

Enable DEBUG logging for detailed server operation:

```python
# In .env file
LOG_LEVEL=DEBUG
```

**Debug Log Output**:
```
2025-10-30T13:38:38Z [info] data_adapter_initialized cache_max_size_mb=500
2025-10-30T13:38:38Z [info] data_query_tools_registered tool_count=1
2025-10-30T13:38:38Z [info] mcp_server_initialized server_name=spock version=0.1.0
2025-10-30T13:38:39Z [info] query_ohlcv_data_start tickers=['005930'] start_date=2024-01-01
2025-10-30T13:38:39Z [debug] cache_miss cache_key=005930:2024-01-01:2024-12-31:KR:1d
2025-10-30T13:38:39Z [info] query_ohlcv_data_success ticker_count=1 record_count=245
```

---

## Support & Resources

### Documentation
- **MCP Design**: `docs/MCP_DESIGN.md` - Architecture and design patterns
- **MCP Workflow**: `docs/MCP_WORKFLOW.md` - Development workflow and roadmap
- **Completion Reports**: `docs/PHASE1_WEEK1_DAY*.md` - Implementation details

### Code Examples
- **Integration Tests**: `tests/mcp_server/test_data_query_tools.py`
- **Manual Tests**: Day 3-4 completion report includes test scripts

### External Resources
- **MCP SDK Documentation**: https://github.com/anthropics/mcp
- **Claude Code Documentation**: https://docs.claude.com/claude-code
- **TimescaleDB Documentation**: https://docs.timescale.com/

### Reporting Issues

Found a bug or have a feature request? Please include:
1. MCP server version
2. Error message and stack trace
3. Input parameters that caused the issue
4. Expected vs actual behavior
5. Debug logs (if applicable)

---

**Last Updated**: 2025-11-27
**Version**: 0.3.0
**Status**: Production Ready (Financial Data Extension Complete)

## Tool Summary

| Tool | Purpose | Performance | Status |
|------|---------|-------------|--------|
| `query_ohlcv_data` | Get historical price data | <200ms cache miss | ✅ Production |
| `run_backtest` | Execute strategy backtests | <1s vectorbt, <30s custom | ✅ Production |
| `optimize_strategy` | Find optimal parameters | Varies by grid size | ✅ Production |
| `list_available_tickers` | List available stocks | <100ms with caching | ✅ Production |
| `get_system_status` | Check system health | <50ms | ✅ Production |
| `screen_etfs` | Screen Korean ETFs | <500ms | ✅ Production |
| `query_dividend_history` | Get dividend history & growth analysis | <300ms | ✅ Production |
| `calculate_financial_ratios` | Calculate financial ratios with interpretation | <500ms | ✅ Production |
