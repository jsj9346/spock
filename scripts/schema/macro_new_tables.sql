-- ============================================================================
-- Macro Analysis Tables - New Schema
-- ============================================================================
-- Purpose: Add 3 new tables for macro analysis (bonds, commodities, sectors)
-- Reuse: global_market_indices, exchange_rates, fx_valuation_signals
-- Author: Spock Quant Platform
-- Created: 2025-01-12
-- ============================================================================

-- ============================================================================
-- 1. bond_yields (채권 수익률)
-- ============================================================================
-- Purpose: Track bond yields for rate environment analysis
-- Data Source: yfinance (US bonds)
-- Update Frequency: Daily
-- Coverage: US 2Y, 5Y, 10Y, 30Y
-- ============================================================================

CREATE TABLE IF NOT EXISTS bond_yields (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,        -- US10Y, US2Y, US30Y
    country VARCHAR(10) NOT NULL,       -- US, KR, JP, DE
    maturity VARCHAR(10) NOT NULL,      -- 2Y, 5Y, 10Y, 30Y
    date DATE NOT NULL,
    yield DECIMAL(10, 6) NOT NULL,      -- Yield in % (e.g., 4.250000)
    change_bps DECIMAL(10, 2),          -- Change in basis points
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('bond_yields', 'date', if_not_exists => TRUE);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_bond_yields_symbol
    ON bond_yields(symbol, date DESC);

CREATE INDEX IF NOT EXISTS idx_bond_yields_country
    ON bond_yields(country, maturity, date DESC);

CREATE INDEX IF NOT EXISTS idx_bond_yields_date
    ON bond_yields(date DESC);

-- Compression policy (compress data older than 1 year)
SELECT add_compression_policy('bond_yields', INTERVAL '365 days', if_not_exists => TRUE);

-- Comment
COMMENT ON TABLE bond_yields IS 'Bond yields for rate environment analysis';
COMMENT ON COLUMN bond_yields.symbol IS 'Bond symbol (e.g., US10Y, KR10Y)';
COMMENT ON COLUMN bond_yields.yield IS 'Yield in percentage (e.g., 4.25 for 4.25%)';
COMMENT ON COLUMN bond_yields.change_bps IS 'Daily change in basis points';


-- ============================================================================
-- 2. commodities (원자재 가격)
-- ============================================================================
-- Purpose: Track commodity prices for inflation and safe-haven demand
-- Data Source: yfinance
-- Update Frequency: Daily
-- Coverage: Gold, Silver, Oil, Copper, Natural Gas
-- ============================================================================

CREATE TABLE IF NOT EXISTS commodities (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,        -- GC=F, CL=F, SI=F
    name VARCHAR(50) NOT NULL,          -- Gold Futures, Crude Oil WTI
    category VARCHAR(20) NOT NULL,      -- Metals, Energy, Agriculture
    date DATE NOT NULL,
    close DECIMAL(15, 4) NOT NULL,      -- Closing price
    open DECIMAL(15, 4),                -- Opening price
    high DECIMAL(15, 4),                -- Highest price
    low DECIMAL(15, 4),                 -- Lowest price
    volume BIGINT,                       -- Trading volume
    change_pct DECIMAL(10, 4),          -- Daily % change
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (symbol, date)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('commodities', 'date', if_not_exists => TRUE);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_commodities_symbol
    ON commodities(symbol, date DESC);

CREATE INDEX IF NOT EXISTS idx_commodities_category
    ON commodities(category, date DESC);

CREATE INDEX IF NOT EXISTS idx_commodities_date
    ON commodities(date DESC);

-- Compression policy
SELECT add_compression_policy('commodities', INTERVAL '365 days', if_not_exists => TRUE);

-- Comment
COMMENT ON TABLE commodities IS 'Commodity prices for inflation and economic indicators';
COMMENT ON COLUMN commodities.symbol IS 'Commodity futures symbol (e.g., GC=F for Gold)';
COMMENT ON COLUMN commodities.category IS 'Commodity category: Metals, Energy, Agriculture';
COMMENT ON COLUMN commodities.change_pct IS 'Daily percentage change';


-- ============================================================================
-- 3. sector_performance (섹터 성과)
-- ============================================================================
-- Purpose: Track sector performance for rotation analysis
-- Data Source: Calculated from ohlcv_data (no external collection needed!)
-- Update Frequency: Daily
-- Coverage: KR 10 sectors, US 11 sectors
-- ============================================================================

CREATE TABLE IF NOT EXISTS sector_performance (
    id BIGSERIAL,
    region VARCHAR(10) NOT NULL,        -- KR, US
    sector VARCHAR(50) NOT NULL,        -- Technology, Healthcare, Financials
    date DATE NOT NULL,
    avg_return_1d DECIMAL(10, 4),       -- 1-day average return
    avg_return_1w DECIMAL(10, 4),       -- 1-week average return
    avg_return_1m DECIMAL(10, 4),       -- 1-month average return
    avg_return_3m DECIMAL(10, 4),       -- 3-month average return
    num_stocks INTEGER,                  -- Number of stocks in sector
    strong_stocks INTEGER,               -- Stocks with positive momentum
    weak_stocks INTEGER,                 -- Stocks with negative momentum
    momentum VARCHAR(20),                -- strong/moderate/weak/negative
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (region, sector, date)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('sector_performance', 'date', if_not_exists => TRUE);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_sector_perf_region
    ON sector_performance(region, date DESC);

CREATE INDEX IF NOT EXISTS idx_sector_perf_sector
    ON sector_performance(region, sector, date DESC);

CREATE INDEX IF NOT EXISTS idx_sector_perf_momentum
    ON sector_performance(momentum, date DESC)
    WHERE momentum IN ('strong', 'moderate');

CREATE INDEX IF NOT EXISTS idx_sector_perf_date
    ON sector_performance(date DESC);

-- Compression policy
SELECT add_compression_policy('sector_performance', INTERVAL '365 days', if_not_exists => TRUE);

-- Comment
COMMENT ON TABLE sector_performance IS 'Sector performance calculated from ohlcv_data';
COMMENT ON COLUMN sector_performance.momentum IS 'Momentum classification: strong (>10%), moderate (3-10%), weak (0-3%), negative (<0%)';
COMMENT ON COLUMN sector_performance.num_stocks IS 'Total number of stocks in sector';
COMMENT ON COLUMN sector_performance.strong_stocks IS 'Number of stocks with positive 1m return';


-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check table creation
SELECT tablename, schemaname
FROM pg_tables
WHERE tablename IN ('bond_yields', 'commodities', 'sector_performance')
ORDER BY tablename;

-- Check hypertables
SELECT hypertable_name, num_dimensions
FROM timescaledb_information.hypertables
WHERE hypertable_name IN ('bond_yields', 'commodities', 'sector_performance')
ORDER BY hypertable_name;

-- Check indexes
SELECT tablename, indexname
FROM pg_indexes
WHERE tablename IN ('bond_yields', 'commodities', 'sector_performance')
ORDER BY tablename, indexname;

-- ============================================================================
-- Usage Examples
-- ============================================================================

-- Insert bond yield
/*
INSERT INTO bond_yields (symbol, country, maturity, date, yield, change_bps)
VALUES ('US10Y', 'US', '10Y', '2025-01-12', 4.250, -5.0);
*/

-- Insert commodity price
/*
INSERT INTO commodities (symbol, name, category, date, close, change_pct)
VALUES ('GC=F', 'Gold Futures', 'Metals', '2025-01-12', 2042.50, -0.5);
*/

-- Insert sector performance
/*
INSERT INTO sector_performance (region, sector, date, avg_return_1d, avg_return_1m, num_stocks, strong_stocks, weak_stocks, momentum)
VALUES ('KR', 'Technology', '2025-01-12', 1.23, 8.45, 25, 18, 7, 'strong');
*/

-- Query yield curve (10Y - 2Y spread)
/*
SELECT
    date,
    MAX(CASE WHEN maturity = '10Y' THEN yield END) -
    MAX(CASE WHEN maturity = '2Y' THEN yield END) as yield_spread
FROM bond_yields
WHERE country = 'US' AND date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;
*/

-- Query sector leaders
/*
SELECT sector, avg_return_1m, momentum
FROM sector_performance
WHERE region = 'KR' AND date = CURRENT_DATE
ORDER BY avg_return_1m DESC
LIMIT 5;
*/

-- ============================================================================
-- End of Schema
-- ============================================================================
