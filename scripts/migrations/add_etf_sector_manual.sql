-- Migration: Add sector_manual column to etf_details
-- Purpose: Support manual sector tagging for improved classification accuracy
-- Date: 2025-10-31

-- Add sector_manual column (nullable, will be populated by etf_sector_tagger.py)
ALTER TABLE etf_details
ADD COLUMN IF NOT EXISTS sector_manual TEXT;

-- Add index for efficient queries
CREATE INDEX IF NOT EXISTS idx_etf_details_sector_manual
ON etf_details(sector_manual) WHERE sector_manual IS NOT NULL;

-- Add comment
COMMENT ON COLUMN etf_details.sector_manual IS 'Manually verified sector classification (overrides sector_theme when present)';

-- Verify
SELECT COUNT(*) as total_etfs,
       COUNT(sector_manual) as manually_tagged,
       COUNT(sector_theme) as auto_classified
FROM etf_details
WHERE region = 'KR';
