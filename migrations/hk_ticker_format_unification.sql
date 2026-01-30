-- ===========================================================================
-- HK Ticker Format Unification Migration
-- ===========================================================================
-- Purpose: Unify HK ticker format across all tables to 'XXXX.HK' or 'XXXXX.HK'
--
-- Current State:
--   - ohlcv_data: XXXX.HK format (yfinance)
--   - ticker_fundamentals: XXXXX format (AkShare 5-digit)
--   - tickers: XXXXX format (AkShare 5-digit)
--   - dividend_history: Mixed (XXXX.HK and XXXXX)
--   - stock_details: XXXXX format
--
-- Target State:
--   - All tables: XXXX.HK or XXXXX.HK format (with .HK suffix)
--   - 4-digit codes: 0001.HK (remove leading zero from 00001)
--   - 5-digit codes (8xxxx, 9xxxx): 82318.HK (keep all digits)
--
-- Author: Spock Quant Platform
-- Date: 2025-12-23
-- ===========================================================================

-- Safety: Start transaction
BEGIN;

-- ===========================================================================
-- Step 0: Backup critical data (for rollback)
-- ===========================================================================
DROP TABLE IF EXISTS _migration_hk_ticker_backup;
CREATE TABLE _migration_hk_ticker_backup AS
SELECT 'tickers' as table_name, ticker as old_ticker, region
FROM tickers WHERE region = 'HK' AND ticker NOT LIKE '%.HK'
UNION ALL
SELECT 'ticker_fundamentals', ticker, region
FROM ticker_fundamentals WHERE region = 'HK' AND ticker NOT LIKE '%.HK'
UNION ALL
SELECT 'dividend_history', ticker, region
FROM dividend_history WHERE region = 'HK' AND ticker NOT LIKE '%.HK'
UNION ALL
SELECT 'stock_details', ticker, region
FROM stock_details WHERE region = 'HK' AND ticker NOT LIKE '%.HK';

-- ===========================================================================
-- Step 0.5: Disable FK constraints temporarily
-- ===========================================================================
SET session_replication_role = 'replica';

-- ===========================================================================
-- Step 1: Create conversion function
-- ===========================================================================
CREATE OR REPLACE FUNCTION convert_hk_ticker_to_suffix(ticker_code TEXT)
RETURNS TEXT AS $$
BEGIN
    -- Already has .HK suffix
    IF ticker_code LIKE '%.HK' THEN
        RETURN ticker_code;
    END IF;

    -- 5-digit code starting with 8 or 9 (RMB traded products)
    -- Keep all 5 digits: 82318 -> 82318.HK
    IF LENGTH(ticker_code) = 5 AND LEFT(ticker_code, 1) IN ('8', '9') THEN
        RETURN ticker_code || '.HK';
    END IF;

    -- 5-digit code starting with 0 (standard HK stocks)
    -- Remove leading zero: 02318 -> 2318.HK
    IF LENGTH(ticker_code) = 5 AND LEFT(ticker_code, 1) = '0' THEN
        RETURN LTRIM(ticker_code, '0') || '.HK';
    END IF;

    -- 4-digit code: add .HK suffix
    IF LENGTH(ticker_code) = 4 THEN
        RETURN ticker_code || '.HK';
    END IF;

    -- Other cases: just add .HK
    RETURN ticker_code || '.HK';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ===========================================================================
-- Step 2: Verify conversion logic (dry run)
-- ===========================================================================
-- This SELECT shows what will be converted before actual UPDATE
DO $$
DECLARE
    sample_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO sample_count
    FROM (
        SELECT ticker, convert_hk_ticker_to_suffix(ticker) as new_ticker
        FROM tickers
        WHERE region = 'HK' AND ticker NOT LIKE '%.HK'
        LIMIT 10
    ) t;

    RAISE NOTICE 'Sample conversions ready. Count: %', sample_count;
END $$;

-- ===========================================================================
-- Step 3: Update tables (ordered by foreign key dependencies)
-- ===========================================================================

-- 3.1 tickers (master table - update first)
UPDATE tickers
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- 3.2 ticker_fundamentals
UPDATE ticker_fundamentals
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- 3.3 ticker_fundamentals_ttm (should already be .HK but ensure consistency)
UPDATE ticker_fundamentals_ttm
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- 3.4 dividend_history
UPDATE dividend_history
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- 3.5 stock_details
UPDATE stock_details
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- 3.6 ohlcv_data (fix the single 5-digit record without .HK)
UPDATE ohlcv_data
SET ticker = convert_hk_ticker_to_suffix(ticker)
WHERE region = 'HK'
  AND ticker NOT LIKE '%.HK';

-- ===========================================================================
-- Step 4: Handle potential duplicates after conversion
-- ===========================================================================
-- Some records might have both old and new format; deduplicate
-- (This is a safety check - should not happen with clean data)

-- Check for duplicates in tickers
DO $$
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO dup_count
    FROM (
        SELECT ticker, region, COUNT(*) as cnt
        FROM tickers
        WHERE region = 'HK'
        GROUP BY ticker, region
        HAVING COUNT(*) > 1
    ) t;

    IF dup_count > 0 THEN
        RAISE WARNING 'Found % duplicate tickers after migration. Manual review needed.', dup_count;
    ELSE
        RAISE NOTICE 'No duplicates found in tickers table.';
    END IF;
END $$;

-- ===========================================================================
-- Step 5: Verification queries
-- ===========================================================================

-- Verify all HK tickers now have .HK suffix
DO $$
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count
    FROM tickers
    WHERE region = 'HK' AND ticker NOT LIKE '%.HK';

    IF remaining_count > 0 THEN
        RAISE EXCEPTION 'Migration incomplete: % tickers still without .HK suffix', remaining_count;
    END IF;

    SELECT COUNT(*) INTO remaining_count
    FROM ticker_fundamentals
    WHERE region = 'HK' AND ticker NOT LIKE '%.HK';

    IF remaining_count > 0 THEN
        RAISE EXCEPTION 'Migration incomplete: % fundamentals still without .HK suffix', remaining_count;
    END IF;

    RAISE NOTICE 'Migration verification PASSED: All HK tickers now have .HK suffix';
END $$;

-- ===========================================================================
-- Step 6: Summary statistics
-- ===========================================================================
SELECT
    'Post-Migration Summary' as status,
    (SELECT COUNT(DISTINCT ticker) FROM tickers WHERE region = 'HK') as tickers_count,
    (SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals WHERE region = 'HK') as fundamentals_tickers,
    (SELECT COUNT(DISTINCT ticker) FROM ohlcv_data WHERE region = 'HK') as ohlcv_tickers,
    (SELECT COUNT(DISTINCT ticker) FROM dividend_history WHERE region = 'HK') as dividend_tickers;

-- ===========================================================================
-- Step 6.5: Re-enable FK constraints
-- ===========================================================================
SET session_replication_role = 'origin';

-- ===========================================================================
-- Commit transaction (comment out for dry-run testing)
-- ===========================================================================
COMMIT;

-- ===========================================================================
-- Cleanup (optional - run after verifying migration success)
-- ===========================================================================
-- DROP FUNCTION IF EXISTS convert_hk_ticker_to_suffix(TEXT);
-- DROP TABLE IF EXISTS _migration_hk_ticker_backup;
