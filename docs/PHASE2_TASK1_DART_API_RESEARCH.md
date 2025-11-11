# Task 1: DART API Research for Annual Financial Statements

**Date**: 2025-11-02
**Status**: ✅ COMPLETE (3 hours planned)
**Phase**: 2 - DART Annual Data Backfill

---

## Executive Summary

The DART API client already has **full support for annual financial statement collection** via the `get_historical_fundamentals()` method. The current backfill script needs to be modified to use this method instead of `get_fundamental_metrics()` which collects recent/DAILY data.

**Key Finding**: The infrastructure is already built - we just need to change which method the backfill script calls.

---

## DART API Architecture

### API Base URL
```
https://opendart.fss.or.kr/api
```

### Key Endpoints

#### 1. **`fnlttSinglAcntAll.json`** (Financial Statement - All Accounts)
**Purpose**: Get detailed financial statement data with 100+ line items

**Parameters**:
- `crtfc_key`: API key (required)
- `corp_code`: 8-digit DART corporate code (required)
- `bsns_year`: Business year (e.g., 2024, 2023, 2022)
- `reprt_code`: Report type code (see below)
- `fs_div`: Financial statement division
  - `CFS`: Consolidated (연결재무제표) - **Recommended**
  - `OFS`: Separate (개별재무제표)

**Report Type Codes (`reprt_code`)**:
| Code | Type | Published | Description |
|------|------|-----------|-------------|
| `11011` | Annual | March-April | 사업보고서 (Annual Report) ← **Target for Phase 2** |
| `11012` | Semi-Annual | August | 반기보고서 (Half-Year Report) |
| `11013` | Q1 | May | 1분기보고서 (Q1 Report) |
| `11014` | Q3 | November | 3분기보고서 (Q3 Report) |

**Example API Call**:
```python
params = {
    'corp_code': '00126380',  # Samsung Electronics
    'bsns_year': 2024,
    'reprt_code': '11011',  # Annual report
    'fs_div': 'CFS'  # Consolidated
}

response = self._make_request('fnlttSinglAcntAll.json', params)
data = response.json()
```

**Response Structure**:
```json
{
    "status": "000",  // Success
    "message": "정상",
    "list": [
        {
            "rcept_no": "20240401...",
            "reprt_code": "11011",
            "bsns_year": "2024",
            "corp_code": "00126380",
            "sj_div": "BS",  // Balance Sheet
            "sj_nm": "재무상태표",
            "account_id": "ifrs_CurrentAssets",
            "account_nm": "유동자산",
            "account_detail": "",
            "thstrm_nm": "제52기",
            "thstrm_amount": "161234567890",  // Current year
            "frmtrm_nm": "제51기",
            "frmtrm_amount": "156789012345",  // Previous year
            "bfefrmtrm_nm": "제50기",
            "bfefrmtrm_amount": "152345678901"  // 2 years ago
        },
        // ... 100+ more line items
    ]
}
```

#### 2. **`corpCode.xml`** (Corporate Code Master)
**Purpose**: Download mapping between stock tickers and DART corp_codes

**URL**: `https://opendart.fss.or.kr/api/corpCode.xml`

**Returns**: ZIP file containing `CORPCODE.xml` with ~30,000 corporations

**Example XML Structure**:
```xml
<result>
    <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <stock_code>005930</stock_code>
        <modify_date>20241101</modify_date>
    </list>
    <!-- ... more corporations -->
</result>
```

---

## Existing DARTApiClient Implementation

### Class Overview
```python
class DARTApiClient:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str = None, rate_limit_delay: float = 36.0):
        self.api_key = api_key or os.getenv('DART_API_KEY')
        self.rate_limit_delay = rate_limit_delay  # 100 req/hour = 36 sec delay
```

### Rate Limits
- **Daily Quota**: 1,000 requests per day
- **Recommended**: 100 requests per hour (36 seconds between calls)
- **Current Backfill**: 1 request/second = 3,600 req/hour (too fast, may hit limits)

**⚠️ Risk**: Current backfill script uses `rate_limit_delay=1.0` which is aggressive. Should increase to 10-36 seconds to avoid API blocks.

---

### Key Methods

#### 1. **`get_fundamental_metrics(ticker, corp_code)`** ← Current (WRONG for Phase 2)
**Purpose**: Get most recent fundamental data (prioritizes quarterly/semi-annual)

**Report Priority**:
```python
# November-December: Q3 2025 > H1 2025 > Q1 2025 > Annual 2025
# August-October: H1 2025 > Q1 2025 > Annual 2025 > Q3 2024
# May-July: Q1 2025 > Annual 2025 > H1 2024
# April: Annual 2025 > Q3 2024 > H1 2024
# January-March: Q3 2024 > H1 2024 > Annual 2024
```

**Why This Fails**:
- Returns most recent data (DAILY/SEMI-ANNUAL period_type)
- Does NOT collect 2024, 2023, 2022 annual data
- Produces inaccurate ROE (1.28% from 6-month data)
- Cannot calculate YOY growth (missing previous year)

**Example Usage**:
```python
metrics = dart.get_fundamental_metrics(ticker='005930', corp_code='00126380')
# Returns: {'ticker': '005930', 'period_type': 'SEMI-ANNUAL', 'fiscal_year': 2025, ...}
```

---

#### 2. **`get_historical_fundamentals(ticker, corp_code, start_year, end_year)`** ← **TARGET for Phase 2**
**Purpose**: Get annual financial statements for multiple years (backtesting)

**Implementation** (Lines 314-385 in `modules/dart_api_client.py`):
```python
def get_historical_fundamentals(self,
                               ticker: str,
                               corp_code: str,
                               start_year: int,
                               end_year: int) -> List[Dict]:
    """
    Get historical annual fundamental data for backtesting

    Returns:
        List of fundamental metrics dictionaries (one per year)
    """
    results = []

    for year in range(start_year, end_year + 1):
        logger.info(f"📊 [DART] {ticker}: Collecting {year} annual report...")

        try:
            # Query annual report for specific year
            params = {
                'corp_code': corp_code,
                'bsns_year': year,
                'reprt_code': '11011',  # Annual report ONLY
                'fs_div': 'CFS'  # Consolidated
            }

            response = self._make_request('fnlttSinglAcntAll.json', params)
            data = response.json()

            if data['status'] == '000' and data.get('list'):
                items = data.get('list', [])

                # Parse financial metrics
                metrics = self._parse_financial_statements(
                    ticker=ticker,
                    items=items,
                    year=year,
                    reprt_code='11011'
                )

                results.append(metrics)
                logger.info(f"✅ [DART] {ticker}: {year} annual data collected")
            else:
                logger.warning(f"⚠️ [DART] {ticker}: {year} annual data not available")

        except Exception as e:
            logger.error(f"❌ [DART] {ticker}: Failed to collect {year} data - {e}")
            continue

    logger.info(f"📊 [DART] {ticker}: Collected {len(results)}/{end_year - start_year + 1} years")
    return results
```

**Key Features**:
- ✅ Collects **ANNUAL reports only** (`reprt_code='11011'`)
- ✅ Supports **multi-year backfill** (2022-2024)
- ✅ Returns **list of dicts** (one per year)
- ✅ Each dict has **fiscal_year field populated**
- ✅ Uses **consolidated financial statements** (CFS)
- ✅ Includes **rate limiting** via `_make_request()`

**Example Usage**:
```python
metrics_list = dart.get_historical_fundamentals(
    ticker='005930',
    corp_code='00126380',
    start_year=2022,
    end_year=2024
)

# Returns:
# [
#     {'ticker': '005930', 'fiscal_year': 2022, 'period_type': 'ANNUAL', 'roe': 13.5, ...},
#     {'ticker': '005930', 'fiscal_year': 2023, 'period_type': 'ANNUAL', 'roe': 12.8, ...},
#     {'ticker': '005930', 'fiscal_year': 2024, 'period_type': 'ANNUAL', 'roe': 7.5, ...}
# ]
```

---

#### 3. **`_parse_financial_statements(ticker, items, year, reprt_code)`**
**Purpose**: Parse DART API response into structured metrics dict

**Extracted Fields** (~40+ line items):

**Balance Sheet**:
- `total_assets`: Total assets (총자산)
- `total_liabilities`: Total liabilities (총부채)
- `total_equity`: Total equity (총자본)
- `current_assets`: Current assets (유동자산)
- `current_liabilities`: Current liabilities (유동부채)
- `inventory`: Inventory (재고자산)
- `accounts_receivable`: Accounts receivable (매출채권)
- `pp_e`: Property, plant & equipment (유형자산)
- `accumulated_depreciation`: Accumulated depreciation (감가상각누계액)

**Income Statement**:
- `revenue`: Revenue (매출액)
- `operating_profit`: Operating profit (영업이익)
- `net_income`: Net income (당기순이익)
- `cogs`: Cost of goods sold (매출원가)
- `gross_profit`: Gross profit (매출총이익)
- `sga_expense`: Selling, general & admin expenses (판매관리비)
- `rd_expense`: R&D expenses (연구개발비)
- `depreciation`: Depreciation expense (감가상각비)
- `interest_income`: Interest income (이자수익)
- `interest_expense`: Interest expense (이자비용)

**Cash Flow Statement**:
- `operating_cf`: Operating cash flow (영업활동현금흐름)
- `investing_cf`: Investing cash flow (투자활동현금흐름)
- `financing_cf`: Financing cash flow (재무활동현금흐름)

**Calculated Metrics**:
- `roe`: Return on equity ((net_income / total_equity) * 100)
- `roa`: Return on assets ((net_income / total_assets) * 100)
- `debt_ratio`: Debt ratio ((total_liabilities / total_equity) * 100)
- `ebitda`: EBITDA (operating_profit + depreciation)
- `ebitda_margin`: EBITDA margin ((ebitda / revenue) * 100)
- `nim`: Net interest margin (for financial institutions)

**Metadata**:
- `ticker`: Stock ticker (e.g., '005930')
- `fiscal_year`: Fiscal year (2024, 2023, 2022)
- `period_type`: 'ANNUAL' (for reprt_code='11011')
- `date`: Report date (from `rcept_no`)
- `data_source`: 'DART_ANNUAL_2024', 'DART_ANNUAL_2023', etc.

**Example Output**:
```python
{
    'ticker': '005930',
    'fiscal_year': 2024,
    'period_type': 'ANNUAL',
    'date': '2024-03-20',
    'data_source': 'DART_ANNUAL_2024',

    # Balance Sheet
    'total_assets': 426_900_000_000_000,  # 426.9 trillion KRW
    'total_equity': 399_600_000_000_000,  # 399.6 trillion KRW
    'total_liabilities': 105_300_000_000_000,  # 105.3 trillion KRW

    # Income Statement
    'revenue': 258_900_000_000_000,  # 258.9 trillion KRW
    'operating_profit': 35_400_000_000_000,  # 35.4 trillion KRW
    'net_income': 30_500_000_000_000,  # 30.5 trillion KRW

    # Calculated Ratios
    'roe': 7.63,  # 30.5T / 399.6T * 100 = 7.63% (annual, not 1.28%)
    'roa': 7.14,  # 30.5T / 426.9T * 100
    'debt_ratio': 26.36  # 105.3T / 399.6T * 100
}
```

---

## Current Backfill Script Analysis

### File: `scripts/backfill_fundamentals_dart.py`

**Current Flow**:
1. Load corp_code mapping (ticker → DART corp_code)
2. Get list of KR stocks from database
3. **For each ticker:**
   - Call `dart.get_fundamental_metrics(ticker, corp_code)` ← **Problem!**
   - Get latest stock price from ohlcv_data
   - Calculate valuation ratios (P/E, P/B)
   - Insert into ticker_fundamentals table

**Problem**:
- `get_fundamental_metrics()` returns most recent data (SEMI-ANNUAL, QUARTERLY)
- Does NOT collect 2024, 2023, 2022 annual data
- fiscal_year is usually NULL or 2025 (current year only)
- Cannot calculate YOY growth (missing 2023 data)

**Current Database INSERT** (Lines 450-476):
```python
query = """
INSERT INTO ticker_fundamentals (
    ticker, region, date, period_type,
    ...,
    fiscal_year,  ← Present in schema
    data_source, created_at
)
VALUES (
    %s, %s, %s, %s,
    ...,
    %s,  ← fiscal_year value
    %s, NOW()
)
"""

data = {
    'ticker': ticker,
    'region': 'KR',
    'date': metrics.get('date'),
    'period_type': metrics.get('period_type', 'ANNUAL'),  ← Currently 'SEMI-ANNUAL' or 'DAILY'
    'fiscal_year': metrics.get('fiscal_year'),  ← Currently NULL or 2025 only
    ...
}
```

**What's Missing**:
1. No loop to collect 2022, 2023, 2024 data
2. Not using `get_historical_fundamentals()`
3. No enforcement that period_type = 'ANNUAL'

---

## Required Modifications

### High-Level Changes

**Before (Current Implementation)**:
```python
# Line 238 in backfill script
metrics = self.dart.get_fundamental_metrics(ticker=ticker, corp_code=corp_code)

# Returns single dict:
# {'ticker': '005930', 'fiscal_year': 2025, 'period_type': 'SEMI-ANNUAL', ...}
```

**After (Phase 2 Target)**:
```python
# Modified line
metrics_list = self.dart.get_historical_fundamentals(
    ticker=ticker,
    corp_code=corp_code,
    start_year=2022,
    end_year=2024
)

# Returns list of 3 dicts:
# [
#     {'ticker': '005930', 'fiscal_year': 2022, 'period_type': 'ANNUAL', ...},
#     {'ticker': '005930', 'fiscal_year': 2023, 'period_type': 'ANNUAL', ...},
#     {'ticker': '005930', 'fiscal_year': 2024, 'period_type': 'ANNUAL', ...}
# ]

# Process each year
for metrics in metrics_list:
    price = self.get_latest_price(ticker, as_of_date=metrics.get('date'))
    ratios = self.calculate_valuation_ratios(ticker, metrics, price)
    self.insert_or_update_fundamental_data(ticker, metrics, ratios, price)
```

### Detailed Modifications

**File: `scripts/backfill_fundamentals_dart.py`**

1. **Add year parameters** (Lines 66-80):
```python
class DARTFundamentalBackfiller:
    def __init__(self, db, dart, dry_run=False, rate_limit_delay=1.0,
                 start_year=2022, end_year=2024):  # Add year range
        self.start_year = start_year
        self.end_year = end_year
```

2. **Modify fetch method** (Lines 221-254):
```python
def fetch_dart_fundamental_data(self, ticker: str, corp_code: str) -> List[Dict]:
    """
    Fetch historical annual fundamental metrics from DART API

    Returns:
        List of dicts (one per year) or empty list on failure
    """
    try:
        time.sleep(self.rate_limit_delay)
        self.stats['api_calls'] += 1

        # Call DART API for historical data
        metrics_list = self.dart.get_historical_fundamentals(
            ticker=ticker,
            corp_code=corp_code,
            start_year=self.start_year,
            end_year=self.end_year
        )

        if not metrics_list:
            logger.warning(f"⚠️ [{ticker}] No annual fundamental data available")
            return []

        logger.info(f"✅ [{ticker}] DART data fetched: {len(metrics_list)} years")
        return metrics_list

    except Exception as e:
        logger.error(f"❌ [{ticker}] DART API call failed: {e}")
        return []
```

3. **Update main backfill loop** (process multiple years per ticker):
```python
# For each ticker
for ticker_info in tickers:
    ticker = ticker_info['ticker']
    corp_code = ticker_info['corp_code']

    # Fetch multi-year data
    metrics_list = self.fetch_dart_fundamental_data(ticker, corp_code)

    if not metrics_list:
        self.stats['tickers_skipped_no_data'] += 1
        continue

    # Process each year
    for metrics in metrics_list:
        fiscal_year = metrics.get('fiscal_year')
        logger.info(f"📊 [{ticker}] Processing {fiscal_year} data...")

        # Get price as of report date
        price = self.get_latest_price(ticker, as_of_date=metrics.get('date'))

        if not price:
            logger.warning(f"⚠️ [{ticker}] No price data for {fiscal_year} - skipping")
            continue

        # Calculate ratios
        ratios = self.calculate_valuation_ratios(ticker, metrics, price)

        # Insert/update database
        success = self.insert_or_update_fundamental_data(ticker, metrics, ratios, price)

        if success:
            self.stats['records_inserted'] += 1

    self.stats['tickers_success'] += 1
```

4. **Update rate limiting** (increase from 1.0s to 10.0s):
```python
# In __init__ or argparse
rate_limit_delay = 10.0  # 10 seconds = 360 req/hour (safer than 3,600 req/hour)
```

---

## API Rate Limit Strategy

### Current Risk
```python
rate_limit_delay = 1.0  # 1 request/second
# 2,000 tickers × 3 years = 6,000 requests
# At 1 req/sec = 1.7 hours
# 6,000 requests exceeds daily quota of 1,000 ❌
```

### Recommended Strategy

**Option A: Batch Processing (3 days)**
```python
# Day 1: 2024 data only (2,000 requests)
python3 scripts/backfill_fundamentals_dart.py --start-year 2024 --end-year 2024 --rate-limit 10.0

# Day 2: 2023 data only (2,000 requests)
python3 scripts/backfill_fundamentals_dart.py --start-year 2023 --end-year 2023 --rate-limit 10.0

# Day 3: 2022 data only (2,000 requests)
python3 scripts/backfill_fundamentals_dart.py --start-year 2022 --end-year 2022 --rate-limit 10.0
```

**Option B: Weekend Run (1 session, 2 hours)**
```python
# Run all years overnight/weekend
python3 scripts/backfill_fundamentals_dart.py \
  --start-year 2022 \
  --end-year 2024 \
  --rate-limit 10.0 \
  --batch-size 333  # 333 tickers × 3 years = 999 requests (under 1,000 limit)
```

**Recommended**: Option A (3-day batch) for safety

---

## Validation Plan

### 1. Dry-Run Test (Task 6)
```bash
python3 scripts/backfill_fundamentals_dart.py \
  --dry-run \
  --tickers 005930 \
  --start-year 2022 \
  --end-year 2024
```

**Expected Output**:
```
[DRY RUN] Would insert/update fundamental data for 005930
  → Fiscal Year: 2022, Period Type: ANNUAL
  → ROE: 13.5%, Debt/Equity: 28.4%

[DRY RUN] Would insert/update fundamental data for 005930
  → Fiscal Year: 2023, Period Type: ANNUAL
  → ROE: 12.8%, Debt/Equity: 27.1%

[DRY RUN] Would insert/update fundamental data for 005930
  → Fiscal Year: 2024, Period Type: ANNUAL
  → ROE: 7.5%, Debt/Equity: 26.4%
```

### 2. Database Validation (Task 7)
```sql
SELECT ticker, fiscal_year, period_type,
       (net_income / total_equity * 100) as roe_calculated,
       roe as roe_stored
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND period_type = 'ANNUAL'
  AND fiscal_year >= 2022
ORDER BY fiscal_year DESC;
```

**Expected Result**:
```
 ticker | fiscal_year | period_type | roe_calculated | roe_stored
--------+-------------+-------------+----------------+------------
 005930 |        2024 | ANNUAL      |           7.50 |       7.50
 005930 |        2023 | ANNUAL      |          12.80 |      12.80
 005930 |        2022 | ANNUAL      |          13.50 |      13.50
```

---

## Summary & Next Steps

### ✅ Research Complete

**Key Findings**:
1. ✅ DART API fully supports annual data collection
2. ✅ `DARTApiClient.get_historical_fundamentals()` already implements multi-year backfill
3. ✅ Database schema supports fiscal_year and ANNUAL period_type
4. ⚠️ Current backfill script uses wrong method (`get_fundamental_metrics()` instead of `get_historical_fundamentals()`)

**Required Changes**:
1. Modify backfill script to call `get_historical_fundamentals(start_year=2022, end_year=2024)`
2. Loop through returned list (3 years × 2,000 tickers = 6,000 records)
3. Increase rate limiting to 10 seconds (safer than 1 second)
4. Process in 3-day batches or weekend run to avoid quota limits

**API Quotas & Timing**:
- Daily quota: 1,000 requests
- Recommended: 3-day batch (2024 → 2023 → 2022)
- Alternative: Weekend run with batch_size=333 (999 requests)

### 📋 Next Task: Analyze Current Implementation

**Task 2** (Day 1-2.2): Deep dive into current backfill script to identify exact code changes needed.

---

**Report Generated**: 2025-11-02
**Author**: Spock Development Team
**Status**: Task 1 COMPLETE ✅ | Task 2 IN PROGRESS 🔄
