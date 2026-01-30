-- ===========================================================================
-- HK Ticker 4-Digit Padding Correction
-- ===========================================================================
-- Purpose: Fix short HK tickers (1.HK, 32.HK, 663.HK) to 4-digit format
--          for yfinance compatibility (0001.HK, 0032.HK, 0663.HK)
--
-- Current State: Many HK tickers have 1-3 digit codes after migration
-- Target State: All HK tickers have minimum 4 digits (e.g., 0001.HK)
--
-- Author: Spock Quant Platform
-- Date: 2025-12-23
-- ===========================================================================

BEGIN;

-- Disable FK constraints
SET session_replication_role = 'replica';

-- ===========================================================================
-- Create padding function
-- ===========================================================================
CREATE OR REPLACE FUNCTION pad_hk_ticker_4digit(ticker_code TEXT)
RETURNS TEXT AS $$
DECLARE
    code_part TEXT;
    padded_code TEXT;
BEGIN
    -- Extract numeric part before .HK
    code_part := SPLIT_PART(ticker_code, '.', 1);

    -- Already 4+ digits or 5-digit RMB (8xxxx, 9xxxx)
    IF LENGTH(code_part) >= 4 THEN
        RETURN ticker_code;
    END IF;

    -- Pad to 4 digits
    padded_code := LPAD(code_part, 4, '0');

    RETURN padded_code || '.HK';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ===========================================================================
-- Verify padding logic (dry run)
-- ===========================================================================
DO $$
DECLARE
    sample_record RECORD;
BEGIN
    RAISE NOTICE 'Sample conversions:';
    FOR sample_record IN
        SELECT ticker, pad_hk_ticker_4digit(ticker) as new_ticker
        FROM tickers
        WHERE region = 'HK'
          AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4
        LIMIT 5
    LOOP
        RAISE NOTICE '  % -> %', sample_record.ticker, sample_record.new_ticker;
    END LOOP;
END $$;

-- ===========================================================================
-- Update all tables
-- ===========================================================================

-- 1. tickers (master table)
UPDATE tickers
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- 2. ticker_fundamentals
UPDATE ticker_fundamentals
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- 3. ticker_fundamentals_ttm
UPDATE ticker_fundamentals_ttm
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- 4. dividend_history
UPDATE dividend_history
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- 5. stock_details
UPDATE stock_details
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- 6. ohlcv_data
UPDATE ohlcv_data
SET ticker = pad_hk_ticker_4digit(ticker)
WHERE region = 'HK'
  AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

-- ===========================================================================
-- Verification
-- ===========================================================================
DO $$
DECLARE
    short_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO short_count
    FROM tickers
    WHERE region = 'HK' AND LENGTH(SPLIT_PART(ticker, '.', 1)) < 4;

    IF short_count > 0 THEN
        RAISE EXCEPTION 'Correction failed: % tickers still have < 4 digits', short_count;
    END IF;

    RAISE NOTICE 'SUCCESS: All HK tickers now have 4+ digit codes';
END $$;

-- Re-enable FK constraints
SET session_replication_role = 'origin';

COMMIT;

-- Show summary
SELECT
    'HK Ticker Format Summary' as status,
    (SELECT COUNT(*) FROM tickers WHERE region = 'HK' AND ticker LIKE '0___.HK') as "4-digit (0XXX.HK)",
    (SELECT COUNT(*) FROM tickers WHERE region = 'HK' AND ticker ~ '^\d{4}\.HK$' AND ticker NOT LIKE '0%') as "4-digit (XXXX.HK)",
    (SELECT COUNT(*) FROM tickers WHERE region = 'HK' AND ticker ~ '^\d{5}\.HK$') as "5-digit (RMB)";
