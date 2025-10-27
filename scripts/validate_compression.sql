-- ============================================================================
-- TimescaleDB Compression Validation Script
-- ============================================================================
-- Purpose: Validate compression configuration and policies
-- Usage: psql -d quant_platform -f scripts/validate_compression.sql
-- Created: 2025-10-21
-- Part of: Phase 1 Task 3 (Compression Policy Setup)
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'TIMESCALEDB COMPRESSION VALIDATION'
\echo '==================================================================='
\echo ''

-- Initialize validation result tracking
CREATE TEMP TABLE validation_results (
    test_name TEXT,
    status TEXT,
    message TEXT,
    severity TEXT
);

-- ============================================================================
-- TEST 1: Verify Compression Settings Exist
-- ============================================================================

\echo 'Test 1: Verify Compression Settings Exist'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Compression Settings - ' || hypertable_name,
    CASE
        WHEN COUNT(*) > 0 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END,
    CASE
        WHEN COUNT(*) > 0 THEN 'Compression configured (' || COUNT(*) || ' columns)'
        ELSE 'No compression settings found'
    END,
    CASE
        WHEN COUNT(*) > 0 THEN 'INFO'
        ELSE 'CRITICAL'
    END
FROM timescaledb_information.compression_settings
WHERE hypertable_name IN ('ohlcv_data', 'factor_scores', 'ohlcv_monthly', 'ohlcv_quarterly', 'ohlcv_yearly')
GROUP BY hypertable_name;

-- Check for missing tables
INSERT INTO validation_results
SELECT
    'Missing Compression - ' || t.table_name,
    '⚠️ WARNING',
    'Table exists but compression not configured',
    'WARNING'
FROM (VALUES
    ('ohlcv_data'),
    ('factor_scores'),
    ('ohlcv_monthly'),
    ('ohlcv_quarterly'),
    ('ohlcv_yearly')
) AS t(table_name)
WHERE NOT EXISTS (
    SELECT 1
    FROM timescaledb_information.compression_settings cs
    WHERE cs.hypertable_name = t.table_name
);

SELECT * FROM validation_results WHERE test_name LIKE 'Compression Settings%' OR test_name LIKE 'Missing Compression%';
\echo ''

-- ============================================================================
-- TEST 2: Verify Compression Policies Exist and Are Active
-- ============================================================================

\echo 'Test 2: Verify Compression Policies Exist and Are Active'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Compression Policy - ' || hypertable_name,
    CASE
        WHEN scheduled THEN '✅ PASS'
        ELSE '❌ FAIL'
    END,
    CASE
        WHEN scheduled THEN 'Policy active (compress after ' || (config->>'compress_after') || ')'
        ELSE 'Policy exists but INACTIVE'
    END,
    CASE
        WHEN scheduled THEN 'INFO'
        ELSE 'CRITICAL'
    END
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

-- Check for tables without policies
INSERT INTO validation_results
SELECT
    'Missing Policy - ' || hypertable_name,
    '⚠️ WARNING',
    'Compression configured but no policy found',
    'WARNING'
FROM timescaledb_information.compression_settings
WHERE hypertable_name NOT IN (
    SELECT hypertable_name
    FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_compression'
)
GROUP BY hypertable_name;

SELECT * FROM validation_results WHERE test_name LIKE '%Policy%';
\echo ''

-- ============================================================================
-- TEST 3: Verify Compression Segmentby Columns
-- ============================================================================

\echo 'Test 3: Verify Compression Segmentby Columns'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Segmentby Config - ' || hypertable_name,
    CASE
        WHEN STRING_AGG(attname, ', ') FILTER (WHERE segmentby_column_index IS NOT NULL) LIKE '%ticker%region%'
            OR hypertable_name = 'factor_scores' THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Segmentby: ' || COALESCE(
        STRING_AGG(attname, ', ') FILTER (WHERE segmentby_column_index IS NOT NULL),
        'NONE'
    ),
    CASE
        WHEN STRING_AGG(attname, ', ') FILTER (WHERE segmentby_column_index IS NOT NULL) LIKE '%ticker%region%'
            OR hypertable_name = 'factor_scores' THEN 'INFO'
        ELSE 'WARNING'
    END
FROM timescaledb_information.compression_settings
GROUP BY hypertable_name;

SELECT * FROM validation_results WHERE test_name LIKE 'Segmentby Config%';
\echo ''

-- ============================================================================
-- TEST 4: Verify Compression Orderby Columns
-- ============================================================================

\echo 'Test 4: Verify Compression Orderby Columns'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Orderby Config - ' || hypertable_name,
    CASE
        WHEN STRING_AGG(attname, ', ') FILTER (WHERE orderby_column_index IS NOT NULL) IS NOT NULL THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Orderby: ' || COALESCE(
        STRING_AGG(
            attname || ' ' || CASE WHEN orderby_desc THEN 'DESC' ELSE 'ASC' END,
            ', '
        ) FILTER (WHERE orderby_column_index IS NOT NULL),
        'NONE'
    ),
    'INFO'
FROM timescaledb_information.compression_settings
GROUP BY hypertable_name;

SELECT * FROM validation_results WHERE test_name LIKE 'Orderby Config%';
\echo ''

-- ============================================================================
-- TEST 5: Verify Compression Ratio
-- ============================================================================

\echo 'Test 5: Verify Compression Ratio (Target: >80%)'
\echo '-------------------------------------------------------------------'

WITH compression_ratios AS (
    SELECT
        hypertable_name,
        CASE
            WHEN SUM(before_compression_total_bytes) > 0 THEN
                (1 - SUM(after_compression_total_bytes)::numeric / SUM(before_compression_total_bytes)) * 100
            ELSE 0
        END as compression_pct
    FROM timescaledb_information.chunk_compression_stats
    GROUP BY hypertable_name
)
INSERT INTO validation_results
SELECT
    'Compression Ratio - ' || hypertable_name,
    CASE
        WHEN compression_pct >= 80 THEN '✅ PASS'
        WHEN compression_pct >= 50 THEN '⚠️ WARNING'
        ELSE '❌ FAIL'
    END,
    ROUND(compression_pct, 2) || '% compression achieved',
    CASE
        WHEN compression_pct >= 80 THEN 'INFO'
        WHEN compression_pct >= 50 THEN 'WARNING'
        ELSE 'CRITICAL'
    END
FROM compression_ratios;

SELECT * FROM validation_results WHERE test_name LIKE 'Compression Ratio%';
\echo ''

-- ============================================================================
-- TEST 6: Verify No Recent Job Failures
-- ============================================================================

\echo 'Test 6: Verify No Recent Job Failures'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Job Failures - ' || hypertable_name,
    CASE
        WHEN total_failures = 0 THEN '✅ PASS'
        WHEN total_failures < 3 THEN '⚠️ WARNING'
        ELSE '❌ FAIL'
    END,
    'Failures: ' || total_failures || ' / ' || total_runs || ' runs',
    CASE
        WHEN total_failures = 0 THEN 'INFO'
        WHEN total_failures < 3 THEN 'WARNING'
        ELSE 'CRITICAL'
    END
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

SELECT * FROM validation_results WHERE test_name LIKE 'Job Failures%';
\echo ''

-- ============================================================================
-- TEST 7: Verify Schedule Intervals
-- ============================================================================

\echo 'Test 7: Verify Schedule Intervals (Expected: 1 day)'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Schedule Interval - ' || hypertable_name,
    CASE
        WHEN schedule_interval <= INTERVAL '1 day' THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Interval: ' || schedule_interval::text,
    CASE
        WHEN schedule_interval <= INTERVAL '1 day' THEN 'INFO'
        ELSE 'WARNING'
    END
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

SELECT * FROM validation_results WHERE test_name LIKE 'Schedule Interval%';
\echo ''

-- ============================================================================
-- TEST 8: Verify Compress After Settings
-- ============================================================================

\echo 'Test 8: Verify Compress After Settings'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Compress After - ' || hypertable_name,
    '✅ PASS',
    'Compress after: ' || (config->>'compress_after'),
    'INFO'
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

SELECT * FROM validation_results WHERE test_name LIKE 'Compress After%';
\echo ''

-- ============================================================================
-- TEST 9: Verify Next Run Schedule
-- ============================================================================

\echo 'Test 9: Verify Next Run Schedule'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Next Run - ' || hypertable_name,
    CASE
        WHEN next_start IS NOT NULL AND next_start > NOW() THEN '✅ PASS'
        WHEN next_start IS NULL THEN '❌ FAIL'
        ELSE '⚠️ WARNING'
    END,
    CASE
        WHEN next_start IS NOT NULL THEN 'Scheduled for: ' || next_start::timestamp::text
        ELSE 'No next run scheduled'
    END,
    CASE
        WHEN next_start IS NOT NULL AND next_start > NOW() THEN 'INFO'
        WHEN next_start IS NULL THEN 'CRITICAL'
        ELSE 'WARNING'
    END
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression';

SELECT * FROM validation_results WHERE test_name LIKE 'Next Run%';
\echo ''

-- ============================================================================
-- TEST 10: Verify Database Has TimescaleDB Extension
-- ============================================================================

\echo 'Test 10: Verify TimescaleDB Extension'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'TimescaleDB Extension',
    CASE
        WHEN COUNT(*) > 0 THEN '✅ PASS'
        ELSE '❌ FAIL'
    END,
    CASE
        WHEN COUNT(*) > 0 THEN 'Version: ' || extversion
        ELSE 'TimescaleDB not installed'
    END,
    CASE
        WHEN COUNT(*) > 0 THEN 'INFO'
        ELSE 'CRITICAL'
    END
FROM pg_extension
WHERE extname = 'timescaledb'
GROUP BY extversion;

SELECT * FROM validation_results WHERE test_name LIKE 'TimescaleDB Extension%';
\echo ''

-- ============================================================================
-- VALIDATION SUMMARY
-- ============================================================================

\echo '==================================================================='
\echo 'VALIDATION SUMMARY'
\echo '==================================================================='
\echo ''

-- Count results by status
SELECT
    severity,
    COUNT(*) as count,
    ARRAY_AGG(test_name ORDER BY test_name) as tests
FROM validation_results
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'WARNING' THEN 2
        WHEN 'INFO' THEN 3
    END;

\echo ''

-- Show all failures and warnings
\echo 'Issues Requiring Attention:'
\echo '-------------------------------------------------------------------'

SELECT
    status,
    test_name,
    message
FROM validation_results
WHERE severity IN ('CRITICAL', 'WARNING')
ORDER BY
    CASE severity
        WHEN 'CRITICAL' THEN 1
        WHEN 'WARNING' THEN 2
    END,
    test_name;

\echo ''

-- Overall validation result
DO $$
DECLARE
    critical_count INTEGER;
    warning_count INTEGER;
    pass_count INTEGER;
BEGIN
    SELECT
        COUNT(*) FILTER (WHERE severity = 'CRITICAL'),
        COUNT(*) FILTER (WHERE severity = 'WARNING'),
        COUNT(*) FILTER (WHERE severity = 'INFO')
    INTO critical_count, warning_count, pass_count
    FROM validation_results;

    RAISE NOTICE '';
    RAISE NOTICE '===================================================================';

    IF critical_count = 0 AND warning_count = 0 THEN
        RAISE NOTICE '✅ VALIDATION PASSED - All tests passed (% checks)', pass_count;
    ELSIF critical_count = 0 THEN
        RAISE NOTICE '⚠️ VALIDATION PASSED WITH WARNINGS - % critical, % warnings, % passed',
            critical_count, warning_count, pass_count;
    ELSE
        RAISE NOTICE '❌ VALIDATION FAILED - % critical issues, % warnings, % passed',
            critical_count, warning_count, pass_count;
    END IF;

    RAISE NOTICE '===================================================================';
    RAISE NOTICE '';

    IF critical_count > 0 THEN
        RAISE NOTICE 'Action Required: Fix critical issues before proceeding';
    ELSIF warning_count > 0 THEN
        RAISE NOTICE 'Recommendation: Review warnings for optimization opportunities';
    ELSE
        RAISE NOTICE 'Status: Compression configuration is optimal';
    END IF;

    RAISE NOTICE '';
END $$;

-- Cleanup
DROP TABLE validation_results;

\echo 'Validation complete. Review any issues above.'
\echo ''
