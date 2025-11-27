-- Migration: 008_create_dividend_history.sql
-- Description: Create dividend_history table for tracking dividend payment history
-- Author: Claude
-- Date: 2025-11-27
-- Phase: 3.1 - Week 2 MCP Financial Data Extension

-- ============================================================================
-- Table: dividend_history
-- Purpose: Track historical dividend payments with dates and growth analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS dividend_history (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,

    -- Dividend Basic Information
    fiscal_year INTEGER NOT NULL,           -- Fiscal year attribution
    dividend_type VARCHAR(20) NOT NULL,     -- 'interim', 'final', 'special', 'quarterly'
    dividend_per_share NUMERIC(15,4),       -- Dividend per share (DPS)
    dividend_yield NUMERIC(10,4),           -- Dividend yield at announcement

    -- Dividend Schedule
    declaration_date DATE,                  -- Dividend announcement date
    ex_dividend_date DATE,                  -- Ex-dividend date
    record_date DATE,                       -- Record date
    payment_date DATE,                      -- Payment date

    -- Additional Information
    currency VARCHAR(3) DEFAULT 'KRW',      -- Currency code
    total_dividend_amount NUMERIC(20,2),    -- Total dividend amount paid
    payout_ratio NUMERIC(10,4),             -- Dividend payout ratio

    -- Metadata
    data_source VARCHAR(50),                -- Data source (KIS, yfinance, pykrx, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uk_dividend_history UNIQUE (ticker, region, fiscal_year, dividend_type, ex_dividend_date),
    CONSTRAINT chk_dividend_type CHECK (dividend_type IN ('interim', 'final', 'special', 'quarterly', 'annual')),
    CONSTRAINT chk_dividend_positive CHECK (dividend_per_share IS NULL OR dividend_per_share >= 0),
    CONSTRAINT chk_yield_positive CHECK (dividend_yield IS NULL OR dividend_yield >= 0),
    CONSTRAINT chk_payout_ratio CHECK (payout_ratio IS NULL OR (payout_ratio >= 0 AND payout_ratio <= 1000))
);

-- ============================================================================
-- Indexes for query optimization
-- ============================================================================

-- Primary lookup: ticker + region
CREATE INDEX IF NOT EXISTS idx_dividend_ticker_region
ON dividend_history(ticker, region);

-- Fiscal year lookups (most recent first)
CREATE INDEX IF NOT EXISTS idx_dividend_fiscal_year
ON dividend_history(fiscal_year DESC);

-- Ex-dividend date lookups (for upcoming dividends)
CREATE INDEX IF NOT EXISTS idx_dividend_ex_date
ON dividend_history(ex_dividend_date DESC);

-- Payment date lookups (for payment tracking)
CREATE INDEX IF NOT EXISTS idx_dividend_payment_date
ON dividend_history(payment_date);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_dividend_ticker_year
ON dividend_history(ticker, region, fiscal_year DESC);

-- Index for data source analysis
CREATE INDEX IF NOT EXISTS idx_dividend_source
ON dividend_history(data_source);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE dividend_history IS
'Dividend history table - Tracks dividend payment records by ticker';

COMMENT ON COLUMN dividend_history.ticker IS
'Ticker symbol (KR: 6-digit, US: 1-5 letters)';

COMMENT ON COLUMN dividend_history.region IS
'Market region code (KR, US, JP, HK, CN, VN)';

COMMENT ON COLUMN dividend_history.fiscal_year IS
'Fiscal year to which the dividend is attributed';

COMMENT ON COLUMN dividend_history.dividend_type IS
'Type of dividend: interim (mid-year), final (year-end), special, quarterly, annual';

COMMENT ON COLUMN dividend_history.dividend_per_share IS
'Dividend amount per share in local currency';

COMMENT ON COLUMN dividend_history.dividend_yield IS
'Dividend yield at announcement time (percentage)';

COMMENT ON COLUMN dividend_history.declaration_date IS
'Date when dividend was announced';

COMMENT ON COLUMN dividend_history.ex_dividend_date IS
'Ex-dividend date - stock trades without dividend rights after this date';

COMMENT ON COLUMN dividend_history.record_date IS
'Record date - shareholders on this date receive dividend';

COMMENT ON COLUMN dividend_history.payment_date IS
'Date when dividend is actually paid to shareholders';

COMMENT ON COLUMN dividend_history.currency IS
'Currency code for dividend amount (KRW, USD, JPY, etc.)';

COMMENT ON COLUMN dividend_history.total_dividend_amount IS
'Total dividend amount paid (DPS * shares outstanding)';

COMMENT ON COLUMN dividend_history.payout_ratio IS
'Dividend payout ratio (total dividends / net income * 100)';

COMMENT ON COLUMN dividend_history.data_source IS
'Source of dividend data (KIS, yfinance, pykrx, DART, SEC, etc.)';

-- ============================================================================
-- Trigger for updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_dividend_history_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_dividend_history_updated_at ON dividend_history;

CREATE TRIGGER trigger_dividend_history_updated_at
    BEFORE UPDATE ON dividend_history
    FOR EACH ROW
    EXECUTE FUNCTION update_dividend_history_timestamp();

-- ============================================================================
-- Verification query
-- ============================================================================

-- Verify table creation
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dividend_history') THEN
        RAISE NOTICE 'SUCCESS: dividend_history table created successfully';
    ELSE
        RAISE EXCEPTION 'FAILED: dividend_history table was not created';
    END IF;
END $$;

-- Display table structure
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'dividend_history'
ORDER BY ordinal_position;
