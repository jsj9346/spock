-- Migration: 007_add_fx_valuation_signals.sql
-- Purpose: Add FX valuation signals table for currency-based investment attractiveness analysis
-- Author: SuperClaude Quant Platform
-- Date: 2025-10-23
-- Dependencies: 006_add_exchange_rate_history.py

-- ============================================================================
-- 1. Create fx_valuation_signals table
-- ============================================================================
CREATE TABLE IF NOT EXISTS fx_valuation_signals (
    id BIGSERIAL PRIMARY KEY,
    currency VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,

    -- USD-normalized exchange rate
    usd_rate NUMERIC(15,6) NOT NULL,

    -- Multi-period returns (negative = depreciation = higher attractiveness)
    return_1m NUMERIC(10,4),
    return_3m NUMERIC(10,4),
    return_6m NUMERIC(10,4),
    return_12m NUMERIC(10,4),

    -- Valuation signals
    trend_score NUMERIC(10,4),              -- -100 to +100 (weighted avg of returns)
    volatility NUMERIC(10,4),               -- 30-day rolling std
    momentum_acceleration NUMERIC(10,4),    -- 2nd derivative of trend

    -- Final attractiveness score
    attractiveness_score NUMERIC(10,4),     -- 0-100 (higher = more attractive)
    confidence NUMERIC(5,4),                -- 0.0-1.0 (data quality indicator)

    -- Metadata
    data_quality VARCHAR(20) DEFAULT 'GOOD' CHECK (data_quality IN ('GOOD', 'PARTIAL', 'POOR', 'MISSING')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_fx_valuation_signals_currency_region_date UNIQUE (currency, region, date),
    CONSTRAINT chk_confidence CHECK (confidence >= 0.0 AND confidence <= 1.0),
    CONSTRAINT chk_attractiveness_score CHECK (attractiveness_score >= 0 AND attractiveness_score <= 100),
    CONSTRAINT chk_trend_score CHECK (trend_score >= -100 AND trend_score <= 100)
);

-- ============================================================================
-- 2. Create indexes for performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_fx_valuation_signals_date
    ON fx_valuation_signals(date DESC);

CREATE INDEX IF NOT EXISTS idx_fx_valuation_signals_currency_region
    ON fx_valuation_signals(currency, region);

CREATE INDEX IF NOT EXISTS idx_fx_valuation_signals_region_date
    ON fx_valuation_signals(region, date DESC);

CREATE INDEX IF NOT EXISTS idx_fx_valuation_signals_attractiveness
    ON fx_valuation_signals(attractiveness_score DESC)
    WHERE data_quality = 'GOOD';

CREATE INDEX IF NOT EXISTS idx_fx_valuation_signals_trend
    ON fx_valuation_signals(trend_score)
    WHERE data_quality = 'GOOD';

-- ============================================================================
-- 3. Add metadata column to exchange_rate_history (if not exists)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'exchange_rate_history'
        AND column_name = 'metadata'
    ) THEN
        ALTER TABLE exchange_rate_history
        ADD COLUMN metadata JSONB DEFAULT '{}';

        CREATE INDEX IF NOT EXISTS idx_exchange_rate_history_metadata
            ON exchange_rate_history USING GIN(metadata);
    END IF;
END $$;

-- ============================================================================
-- 4. Create materialized view for latest FX signals
-- ============================================================================
DROP MATERIALIZED VIEW IF EXISTS mv_latest_fx_signals;

CREATE MATERIALIZED VIEW mv_latest_fx_signals AS
SELECT DISTINCT ON (currency, region)
    currency,
    region,
    date,
    usd_rate,
    return_1m,
    return_3m,
    return_6m,
    return_12m,
    trend_score,
    volatility,
    momentum_acceleration,
    attractiveness_score,
    confidence,
    data_quality,
    updated_at
FROM fx_valuation_signals
WHERE data_quality IN ('GOOD', 'PARTIAL')
ORDER BY currency, region, date DESC;

-- Create index on materialized view
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_latest_fx_signals_currency_region
    ON mv_latest_fx_signals(currency, region);

CREATE INDEX IF NOT EXISTS idx_mv_latest_fx_signals_attractiveness
    ON mv_latest_fx_signals(attractiveness_score DESC);

-- ============================================================================
-- 5. Create trigger for updated_at timestamp
-- ============================================================================
CREATE OR REPLACE FUNCTION update_fx_valuation_signals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fx_valuation_signals_updated_at ON fx_valuation_signals;

CREATE TRIGGER trg_fx_valuation_signals_updated_at
    BEFORE UPDATE ON fx_valuation_signals
    FOR EACH ROW
    EXECUTE FUNCTION update_fx_valuation_signals_updated_at();

-- ============================================================================
-- 6. Insert base currency (USD) record
-- ============================================================================
INSERT INTO fx_valuation_signals (
    currency, region, date, usd_rate,
    return_1m, return_3m, return_6m, return_12m,
    trend_score, volatility, momentum_acceleration,
    attractiveness_score, confidence, data_quality
)
VALUES (
    'USD', 'US', CURRENT_DATE, 1.000000,
    0.0000, 0.0000, 0.0000, 0.0000,
    0.0000, 0.0000, 0.0000,
    50.0000, 1.0000, 'GOOD'
)
ON CONFLICT (currency, region, date) DO NOTHING;

-- ============================================================================
-- 7. Create function to refresh materialized view
-- ============================================================================
CREATE OR REPLACE FUNCTION refresh_latest_fx_signals()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_fx_signals;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 8. Grant permissions (adjust as needed)
-- ============================================================================
GRANT SELECT, INSERT, UPDATE ON fx_valuation_signals TO PUBLIC;
GRANT SELECT ON mv_latest_fx_signals TO PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE fx_valuation_signals_id_seq TO PUBLIC;

-- ============================================================================
-- 9. Verification queries
-- ============================================================================
-- Verify table creation
SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename = 'fx_valuation_signals';

-- Verify indexes
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'fx_valuation_signals'
ORDER BY indexname;

-- Verify materialized view
SELECT
    schemaname,
    matviewname,
    matviewowner
FROM pg_matviews
WHERE matviewname = 'mv_latest_fx_signals';

-- Display table structure
\d+ fx_valuation_signals

-- Display materialized view structure
\d+ mv_latest_fx_signals

-- Show initial USD record
SELECT * FROM fx_valuation_signals WHERE currency = 'USD';

-- ============================================================================
-- Migration complete
-- ============================================================================
-- Next steps:
-- 1. Run KIS API ticker verification (Task 1.2)
-- 2. Implement fx_data_collector.py (Task 1.3)
-- 3. Backfill historical data (Task 1.4)
-- ============================================================================
