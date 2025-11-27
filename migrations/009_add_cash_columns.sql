-- Migration: 009_add_cash_columns.sql
-- Description: Add cash and cash equivalents columns to ticker_fundamentals for cash ratio calculation
-- Author: Claude
-- Date: 2025-11-27
-- Phase: 4.1 - Week 2 MCP Financial Data Extension

-- ============================================================================
-- Add cash-related columns to ticker_fundamentals table
-- ============================================================================

-- Cash and Cash Equivalents (현금 및 현금성자산)
-- Definition: Cash, demand deposits, and short-term highly liquid investments
-- that are readily convertible to known amounts of cash (maturity < 3 months)
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS cash_and_equivalents NUMERIC(20,2);

COMMENT ON COLUMN ticker_fundamentals.cash_and_equivalents IS
'Cash and Cash Equivalents: Cash, demand deposits, and highly liquid investments with maturity < 3 months. Used for cash ratio calculation.';

-- Short-term Investments (단기금융상품)
-- Definition: Investments with maturity between 3 months and 1 year
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS short_term_investments NUMERIC(20,2);

COMMENT ON COLUMN ticker_fundamentals.short_term_investments IS
'Short-term Investments: Financial instruments with maturity between 3 months and 1 year.';

-- Marketable Securities (유가증권)
-- Definition: Trading securities or available-for-sale securities
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS marketable_securities NUMERIC(20,2);

COMMENT ON COLUMN ticker_fundamentals.marketable_securities IS
'Marketable Securities: Trading securities or available-for-sale securities held for short-term purposes.';

-- ============================================================================
-- Add indexes for performance optimization
-- ============================================================================

-- Index for cash ratio queries (ticker + region + period with cash data)
CREATE INDEX IF NOT EXISTS idx_fundamentals_cash_ratio
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE cash_and_equivalents IS NOT NULL AND current_liabilities IS NOT NULL;

-- ============================================================================
-- Verification
-- ============================================================================

-- Verify columns were added
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count
    FROM information_schema.columns
    WHERE table_name = 'ticker_fundamentals'
      AND column_name IN ('cash_and_equivalents', 'short_term_investments', 'marketable_securities');

    IF col_count = 3 THEN
        RAISE NOTICE 'SUCCESS: All 3 cash columns added successfully';
    ELSE
        RAISE WARNING 'PARTIAL: Only % of 3 columns were added', col_count;
    END IF;
END $$;

-- Display new columns
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticker_fundamentals'
  AND column_name IN ('cash_and_equivalents', 'short_term_investments', 'marketable_securities')
ORDER BY column_name;
