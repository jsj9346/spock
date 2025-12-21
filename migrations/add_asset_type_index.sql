-- ============================================================================
-- Migration: Add asset_type Index for CN/HK Fundamental Filtering
-- ============================================================================
-- Purpose: Optimize ticker queries filtered by region, asset_type, and is_active
-- Use Case: Backfill scripts need fast filtering of STOCK vs ETF/FUND tickers
-- Performance: Speeds up backfill filtering from full table scan to index scan
-- ============================================================================

-- Ensure asset_type column exists (should already exist from schema init)
ALTER TABLE tickers
ADD COLUMN IF NOT EXISTS asset_type VARCHAR(20) DEFAULT 'STOCK';

-- Create composite index for fast filtering
-- WHERE clause filters only active tickers to reduce index size
CREATE INDEX IF NOT EXISTS idx_tickers_region_asset_type_active
ON tickers (region, asset_type, is_active)
WHERE is_active = TRUE;

-- Add column comment for documentation
COMMENT ON COLUMN tickers.asset_type IS
'Asset type classification: STOCK, ETF, MUTUALFUND, INDEX, or NULL (unclassified). Used to filter fundamental data collection to stocks only (ETFs/funds have no financial statements).';

-- Verify index creation
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'tickers'
  AND indexname = 'idx_tickers_region_asset_type_active';

-- Show current asset_type distribution (for verification)
SELECT
    region,
    asset_type,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY region), 2) as pct
FROM tickers
WHERE is_active = TRUE
GROUP BY region, asset_type
ORDER BY region, count DESC;
