-- Migration: Add AkShare Pre-calculated Ratio Columns
-- Date: 2025-12-18
-- Purpose: Support HK/CN/VN fundamental data from AkShare API
-- Related: HK_FUNDAMENTAL_DATA_TROUBLESHOOTING_REPORT.md

BEGIN;

-- Add pre-calculated ratio columns from AkShare
-- These are calculated by the data provider, not by us
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS eps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS bps numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roe numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roa numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS debt_ratio numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS current_ratio numeric(10,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS gross_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_margin numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS roic numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS revenue_yoy numeric(10,4);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS net_income_yoy numeric(10,4);

-- Add column comments
COMMENT ON COLUMN ticker_fundamentals.eps IS 'Earnings per share (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.bps IS 'Book value per share (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.roe IS 'Return on equity - stored value (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.roa IS 'Return on assets - stored value (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.roic IS 'Return on invested capital (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.debt_ratio IS 'Debt to asset ratio (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.current_ratio IS 'Current ratio (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.gross_margin IS 'Gross profit margin % (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.net_margin IS 'Net profit margin % (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.revenue_yoy IS 'Revenue year-over-year growth % (from data provider)';
COMMENT ON COLUMN ticker_fundamentals.net_income_yoy IS 'Net income year-over-year growth % (from data provider)';

-- Add indexes for commonly queried ratios
CREATE INDEX IF NOT EXISTS idx_fundamentals_eps_stored ON ticker_fundamentals(ticker, region, date DESC) WHERE eps IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_roe_stored ON ticker_fundamentals(ticker, region, date DESC) WHERE roe IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_roa_stored ON ticker_fundamentals(ticker, region, date DESC) WHERE roa IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_roic_stored ON ticker_fundamentals(ticker, region, date DESC) WHERE roic IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_debt_ratio ON ticker_fundamentals(debt_ratio) WHERE debt_ratio IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fundamentals_margins ON ticker_fundamentals(ticker, region, date DESC) WHERE gross_margin IS NOT NULL OR net_margin IS NOT NULL;

COMMIT;

-- Verify migration
\d ticker_fundamentals
