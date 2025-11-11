-- ============================================================================
-- Phase 3: Equity Account Enhancement - Database Migration
-- ============================================================================
--
-- Purpose: Add 8 equity account columns + 2 validation columns to ticker_fundamentals
-- Date: 2025-11-10
-- Database: quant_platform (Production)
--
-- Pre-requisites:
--   - Backup created: backups/ticker_fundamentals_YYYYMMDD_HHMMSS.sql
--   - PostgreSQL 17.6 + TimescaleDB 2.22.1
--
-- Rollback: Use backup to restore original table
--
-- ============================================================================

-- Step 1: Add 8 equity account columns (Phase 1)
-- ============================================================================

ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS capital_stock NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS capital_surplus NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS retained_earnings NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS treasury_stock NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS other_comprehensive_income NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS non_controlling_interest NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS unappropriated_retained_earnings NUMERIC(20,2);
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS legal_reserve NUMERIC(20,2);

-- Step 2: Add 2 validation columns (Phase 2)
-- ============================================================================

ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS equity_validation_passed BOOLEAN;
ALTER TABLE ticker_fundamentals ADD COLUMN IF NOT EXISTS equity_validation_error_pct NUMERIC(5,2);

-- Step 3: Add constraints (Phase 1)
-- ============================================================================

-- Treasury stock must be negative (deduction account)
ALTER TABLE ticker_fundamentals
  DROP CONSTRAINT IF EXISTS chk_treasury_stock_negative;

ALTER TABLE ticker_fundamentals
  ADD CONSTRAINT chk_treasury_stock_negative
  CHECK (treasury_stock IS NULL OR treasury_stock <= 0);

-- Capital stock must be positive
ALTER TABLE ticker_fundamentals
  DROP CONSTRAINT IF EXISTS chk_capital_stock_positive;

ALTER TABLE ticker_fundamentals
  ADD CONSTRAINT chk_capital_stock_positive
  CHECK (capital_stock IS NULL OR capital_stock >= 0);

-- Step 4: Create indexes (Phase 1)
-- ============================================================================

-- Index for complete equity data queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_equity_complete
  ON ticker_fundamentals(ticker, region, date)
  WHERE capital_stock IS NOT NULL;

-- Index for negative equity screening
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_negative_equity
  ON ticker_fundamentals(ticker, region, date)
  WHERE total_equity < 0;

-- Index for treasury stock analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tf_treasury_stock
  ON ticker_fundamentals(ticker, region)
  WHERE treasury_stock IS NOT NULL;

-- Step 5: Verify migration
-- ============================================================================

-- Check new columns exist
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'ticker_fundamentals'
  AND column_name IN (
    'capital_stock', 'capital_surplus', 'retained_earnings', 'treasury_stock',
    'other_comprehensive_income', 'non_controlling_interest',
    'unappropriated_retained_earnings', 'legal_reserve',
    'equity_validation_passed', 'equity_validation_error_pct'
  )
ORDER BY column_name;

-- Check constraints exist
SELECT
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'ticker_fundamentals'
  AND constraint_name IN ('chk_treasury_stock_negative', 'chk_capital_stock_positive')
ORDER BY constraint_name;

-- Check indexes exist
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'ticker_fundamentals'
  AND indexname IN ('idx_tf_equity_complete', 'idx_tf_negative_equity', 'idx_tf_treasury_stock')
ORDER BY indexname;

-- ============================================================================
-- Migration Complete
-- ============================================================================
--
-- Summary:
--   - 8 equity account columns added
--   - 2 validation columns added
--   - 2 CHECK constraints added
--   - 3 indexes created
--
-- Next Steps:
--   - Run backfill script: scripts/backfill_fundamentals_dart.py
--   - Verify data quality: SQL queries in Step 5
--
-- ============================================================================
