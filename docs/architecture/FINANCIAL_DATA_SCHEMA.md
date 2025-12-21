# Financial Data Schema Design - Phase 2

## Overview
Comprehensive financial statement schema for Value and Quality factor calculations.

## Design Philosophy
- **Normalized Structure**: Separate tables for Income Statement, Balance Sheet, Cash Flow
- **Temporal Coverage**: Support quarterly and annual statements
- **Multi-Region Support**: IFRS and US GAAP compatible
- **Factor-Optimized**: Schema designed for efficient factor calculation

## Database Tables

### 1. income_statements
**Purpose**: Profit & Loss (P&L) data for profitability analysis

```sql
CREATE TABLE IF NOT EXISTS income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,              -- NULL for annual, 1-4 for quarterly
    period_type TEXT NOT NULL,           -- 'ANNUAL', 'QUARTERLY'
    report_date TEXT NOT NULL,           -- YYYY-MM-DD

    -- Revenue
    revenue BIGINT,                      -- 매출액 (Sales, Revenue)
    cost_of_revenue BIGINT,              -- 매출원가 (COGS)
    gross_profit BIGINT,                 -- 매출총이익

    -- Operating Items
    operating_expenses BIGINT,            -- 영업비용 (SG&A + R&D + etc)
    operating_income BIGINT,              -- 영업이익 (Operating Income, EBIT)

    -- Non-Operating Items
    interest_income BIGINT,               -- 이자수익
    interest_expense BIGINT,              -- 이자비용
    other_income BIGINT,                  -- 기타수익
    other_expense BIGINT,                 -- 기타비용

    -- Pre-Tax & Tax
    income_before_tax BIGINT,             -- 법인세차감전순이익
    income_tax_expense BIGINT,            -- 법인세비용

    -- Net Income
    net_income BIGINT,                    -- 당기순이익 (Net Income)

    -- Advanced Metrics
    ebitda BIGINT,                        -- EBITDA (Operating Income + D&A)
    depreciation_amortization BIGINT,     -- 감가상각비

    -- Metadata
    data_source TEXT,                     -- 'DART', 'yfinance', 'manual'
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);

CREATE INDEX idx_income_ticker_year ON income_statements(ticker, fiscal_year);
CREATE INDEX idx_income_period ON income_statements(period_type);
```

### 2. balance_sheets
**Purpose**: Asset, Liability, Equity data for financial health analysis

```sql
CREATE TABLE IF NOT EXISTS balance_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    period_type TEXT NOT NULL,
    report_date TEXT NOT NULL,

    -- Assets
    current_assets BIGINT,                -- 유동자산
    cash_and_equivalents BIGINT,          -- 현금및현금성자산
    accounts_receivable BIGINT,           -- 매출채권
    inventory BIGINT,                     -- 재고자산

    non_current_assets BIGINT,            -- 비유동자산
    property_plant_equipment BIGINT,      -- 유형자산 (PP&E)
    intangible_assets BIGINT,             -- 무형자산

    total_assets BIGINT,                  -- 자산총계

    -- Liabilities
    current_liabilities BIGINT,           -- 유동부채
    accounts_payable BIGINT,              -- 매입채무
    short_term_debt BIGINT,               -- 단기차입금

    non_current_liabilities BIGINT,       -- 비유동부채
    long_term_debt BIGINT,                -- 장기차입금

    total_liabilities BIGINT,             -- 부채총계

    -- Equity
    shareholders_equity BIGINT,           -- 자본총계 (Total Equity)
    common_stock BIGINT,                  -- 자본금
    retained_earnings BIGINT,             -- 이익잉여금

    -- Calculated Metrics
    total_debt BIGINT,                    -- 총부채 (Short + Long)
    net_debt BIGINT,                      -- 순부채 (Total Debt - Cash)
    working_capital BIGINT,               -- 운전자본 (Current Assets - Current Liabilities)

    -- Metadata
    data_source TEXT,
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);

CREATE INDEX idx_balance_ticker_year ON balance_sheets(ticker, fiscal_year);
CREATE INDEX idx_balance_period ON balance_sheets(period_type);
```

### 3. cash_flow_statements
**Purpose**: Operating, Investing, Financing cash flows for cash quality analysis

```sql
CREATE TABLE IF NOT EXISTS cash_flow_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    period_type TEXT NOT NULL,
    report_date TEXT NOT NULL,

    -- Operating Activities
    operating_cash_flow BIGINT,           -- 영업활동현금흐름 (CFO)
    net_income BIGINT,                    -- 당기순이익 (starting point)
    depreciation_amortization BIGINT,     -- 감가상각비 (non-cash)
    changes_in_working_capital BIGINT,    -- 운전자본변동

    -- Investing Activities
    investing_cash_flow BIGINT,           -- 투자활동현금흐름
    capital_expenditures BIGINT,          -- 자본적지출 (CapEx)
    investments BIGINT,                   -- 투자자산 취득/처분

    -- Financing Activities
    financing_cash_flow BIGINT,           -- 재무활동현금흐름
    dividends_paid BIGINT,                -- 배당금지급
    debt_issued BIGINT,                   -- 차입금증가
    debt_repaid BIGINT,                   -- 차입금상환

    -- Cash Position
    net_change_in_cash BIGINT,            -- 현금증감
    beginning_cash_balance BIGINT,        -- 기초현금
    ending_cash_balance BIGINT,           -- 기말현금

    -- Calculated Metrics
    free_cash_flow BIGINT,                -- FCF = CFO - CapEx

    -- Metadata
    data_source TEXT,
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);

CREATE INDEX idx_cashflow_ticker_year ON cash_flow_statements(ticker, fiscal_year);
CREATE INDEX idx_cashflow_period ON cash_flow_statements(period_type);
```

## Factor Calculations (SQL Views for Performance)

### Value Factors

```sql
-- P/E Ratio (Price-to-Earnings)
-- = Market Cap / Net Income
SELECT
    f.ticker,
    f.fiscal_year,
    f.market_cap / NULLIF(i.net_income, 0) AS pe_ratio
FROM ticker_fundamentals f
JOIN income_statements i
    ON f.ticker = i.ticker
    AND f.fiscal_year = i.fiscal_year
    AND i.period_type = 'ANNUAL';

-- P/B Ratio (Price-to-Book)
-- = Market Cap / Shareholders Equity
SELECT
    f.ticker,
    f.fiscal_year,
    f.market_cap / NULLIF(b.shareholders_equity, 0) AS pb_ratio
FROM ticker_fundamentals f
JOIN balance_sheets b
    ON f.ticker = b.ticker
    AND f.fiscal_year = b.fiscal_year
    AND b.period_type = 'ANNUAL';

-- EV/EBITDA
-- = (Market Cap + Total Debt - Cash) / EBITDA
SELECT
    f.ticker,
    f.fiscal_year,
    f.ev / NULLIF(i.ebitda, 0) AS ev_ebitda_ratio
FROM ticker_fundamentals f
JOIN income_statements i
    ON f.ticker = i.ticker
    AND f.fiscal_year = i.fiscal_year
    AND i.period_type = 'ANNUAL';

-- Dividend Yield (already in ticker_fundamentals)
-- = Annual Dividend / Stock Price
```

### Quality Factors

```sql
-- ROE (Return on Equity)
-- = Net Income / Shareholders Equity
SELECT
    i.ticker,
    i.fiscal_year,
    (i.net_income * 100.0) / NULLIF(b.shareholders_equity, 0) AS roe_percent
FROM income_statements i
JOIN balance_sheets b
    ON i.ticker = b.ticker
    AND i.fiscal_year = b.fiscal_year
    AND i.period_type = b.period_type
WHERE i.period_type = 'ANNUAL';

-- Debt-to-Equity Ratio
-- = Total Debt / Shareholders Equity
SELECT
    ticker,
    fiscal_year,
    (total_debt * 1.0) / NULLIF(shareholders_equity, 0) AS debt_to_equity_ratio
FROM balance_sheets
WHERE period_type = 'ANNUAL';

-- Earnings Quality (Accruals)
-- = (Net Income - Operating Cash Flow) / Total Assets
SELECT
    i.ticker,
    i.fiscal_year,
    ((i.net_income - cf.operating_cash_flow) * 1.0) / NULLIF(b.total_assets, 0) AS accruals_ratio
FROM income_statements i
JOIN cash_flow_statements cf
    ON i.ticker = cf.ticker
    AND i.fiscal_year = cf.fiscal_year
    AND i.period_type = cf.period_type
JOIN balance_sheets b
    ON i.ticker = b.ticker
    AND i.fiscal_year = b.fiscal_year
    AND i.period_type = b.period_type
WHERE i.period_type = 'ANNUAL';

-- Profit Margin
-- = Net Income / Revenue
SELECT
    ticker,
    fiscal_year,
    (net_income * 100.0) / NULLIF(revenue, 0) AS profit_margin_percent
FROM income_statements
WHERE period_type = 'ANNUAL';
```

## Data Collection Workflow

### Phase 2A: Korean Market (DART API)
1. **Corporate Code Mapping**: ticker → DART corp_code
2. **Financial Statement API**: `/api/fnlttSinglAcnt.json`
   - Income Statement (손익계산서)
   - Balance Sheet (재무상태표)
   - Cash Flow Statement (현금흐름표)
3. **Data Parsing**: XML/JSON → Normalized fields
4. **Storage**: Quarterly + Annual data

### Phase 2B: Global Markets (yfinance)
1. **Ticker Resolution**: Region-specific ticker format
2. **Financial API**: `ticker.financials`, `ticker.balance_sheet`, `ticker.cashflow`
3. **Currency Normalization**: Convert to KRW for consistency
4. **Storage**: Annual data (quarterly if available)

## Migration Script

**Location**: `scripts/init_financial_statements_schema.py`

**Features**:
- Create tables if not exist
- Create indexes for performance
- Validate existing data integrity
- No data loss on re-run

## Performance Considerations

**Indexes**:
- Composite indexes on (ticker, fiscal_year) for join performance
- Period_type index for filtering quarterly vs annual
- Created_at index for data freshness queries

**Query Optimization**:
- Factor calculations use JOINs (not subqueries)
- NULLIF prevents division by zero errors
- Period_type filtering at index level

## Data Retention Policy

- **Quarterly Data**: 5 years (20 quarters)
- **Annual Data**: 10 years minimum
- **Daily ticker_fundamentals**: 1 year (for PER/PBR tracking)

## Next Steps

1. Create schema migration script
2. Extend DART API client for financial statements
3. Implement Value factors using new schema
4. Implement Quality factors using new schema
5. Create data collection workflow
