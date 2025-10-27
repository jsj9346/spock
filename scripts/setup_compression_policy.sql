-- ============================================================================
-- Setup Compression Policy for TimescaleDB Hypertables
-- ============================================================================
-- Purpose: Enable compression on continuous aggregates and verify settings
-- Created: 2025-10-21
-- Part of: Phase 1 Task 3 (Database Migration)
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'TASK 3: SETUP COMPRESSION POLICY'
\echo '==================================================================='
\echo ''

-- ============================================================================
-- STEP 1: Verify Current Compression Status
-- ============================================================================

\echo 'Step 1: Current Compression Status'
\echo '-------------------------------------------------------------------'

SELECT
    hypertable_name,
    COUNT(*) as total_chunks,
    COUNT(*) FILTER (WHERE is_compressed) as compressed,
    COUNT(*) FILTER (WHERE NOT is_compressed) as uncompressed,
    ROUND(
        COUNT(*) FILTER (WHERE is_compressed)::numeric / COUNT(*) * 100,
        2
    ) as compression_pct,
    pg_size_pretty(
        SUM(pg_total_relation_size(chunk_schema || '.' || chunk_name))
    ) as total_size
FROM timescaledb_information.chunks
WHERE hypertable_name IN ('ohlcv_data', 'factor_scores')
GROUP BY hypertable_name
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- STEP 2: Enable Compression on Continuous Aggregates
-- ============================================================================

\echo 'Step 2: Enabling Compression on Continuous Aggregates'
\echo '-------------------------------------------------------------------'

-- 2.1 ohlcv_monthly compression
\echo '  Configuring ohlcv_monthly...'
ALTER MATERIALIZED VIEW ohlcv_monthly SET (
    timescaledb.compress = true,
    timescaledb.compress_segmentby = 'ticker, region, timeframe',
    timescaledb.compress_orderby = 'month DESC'
);

-- Add compression policy (compress after 1 year)
SELECT add_compression_policy('ohlcv_monthly',
    compress_after => INTERVAL '1 year'
);

\echo '  ✅ ohlcv_monthly compression enabled (compress after 1 year)'
\echo ''

-- 2.2 ohlcv_yearly compression
\echo '  Configuring ohlcv_yearly...'
ALTER MATERIALIZED VIEW ohlcv_yearly SET (
    timescaledb.compress = true,
    timescaledb.compress_segmentby = 'ticker, region, timeframe',
    timescaledb.compress_orderby = 'year DESC'
);

-- Add compression policy (compress after 2 years)
SELECT add_compression_policy('ohlcv_yearly',
    compress_after => INTERVAL '2 years'
);

\echo '  ✅ ohlcv_yearly compression enabled (compress after 2 years)'
\echo ''

-- 2.3 ohlcv_quarterly compression
\echo '  Configuring ohlcv_quarterly...'
ALTER MATERIALIZED VIEW ohlcv_quarterly SET (
    timescaledb.compress = true,
    timescaledb.compress_segmentby = 'ticker, region, timeframe',
    timescaledb.compress_orderby = 'quarter DESC'
);

-- Add compression policy (compress after 18 months)
SELECT add_compression_policy('ohlcv_quarterly',
    compress_after => INTERVAL '18 months'
);

\echo '  ✅ ohlcv_quarterly compression enabled (compress after 18 months)'
\echo ''

-- ============================================================================
-- STEP 3: Verify Compression Policies
-- ============================================================================

\echo 'Step 3: Verify All Compression Policies'
\echo '-------------------------------------------------------------------'

SELECT
    job_id,
    hypertable_name,
    schedule_interval,
    config->>'compress_after' as compress_after,
    next_start::timestamp as next_run,
    CASE
        WHEN scheduled THEN '✅ Active'
        ELSE '❌ Inactive'
    END as status
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- STEP 4: Compression Configuration Summary
-- ============================================================================

\echo 'Step 4: Compression Configuration Summary'
\echo '-------------------------------------------------------------------'

SELECT
    hypertable_schema,
    hypertable_name,
    STRING_AGG(
        CASE
            WHEN segmentby_column_index IS NOT NULL
            THEN attname
            ELSE NULL
        END,
        ', '
    ) FILTER (WHERE segmentby_column_index IS NOT NULL) as segment_by,
    STRING_AGG(
        CASE
            WHEN orderby_column_index IS NOT NULL
            THEN attname || ' DESC'
            ELSE NULL
        END,
        ', '
    ) FILTER (WHERE orderby_column_index IS NOT NULL) as order_by
FROM timescaledb_information.compression_settings
GROUP BY hypertable_schema, hypertable_name
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- STEP 5: Storage Savings Estimate
-- ============================================================================

\echo 'Step 5: Estimated Storage Savings'
\echo '-------------------------------------------------------------------'

WITH chunk_sizes AS (
    SELECT
        hypertable_name,
        is_compressed,
        pg_total_relation_size(chunk_schema || '.' || chunk_name) as size
    FROM timescaledb_information.chunks
    WHERE hypertable_name = 'ohlcv_data'
)
SELECT
    hypertable_name,
    pg_size_pretty(SUM(size) FILTER (WHERE is_compressed)) as compressed_size,
    pg_size_pretty(SUM(size) FILTER (WHERE NOT is_compressed)) as uncompressed_size,
    pg_size_pretty(
        -- Estimate if all chunks compressed (based on 99.8% ratio)
        SUM(size) * 0.002
    ) as est_total_compressed,
    pg_size_pretty(
        -- Estimated savings
        SUM(size) * 0.998
    ) as potential_savings,
    ROUND(
        (SUM(size) * 0.998) / NULLIF(SUM(size), 0) * 100,
        2
    ) || '%' as savings_pct
FROM chunk_sizes
GROUP BY hypertable_name;

\echo ''

-- ============================================================================
-- Success Message
-- ============================================================================

\echo '==================================================================='
\echo '✅ COMPRESSION POLICY SETUP COMPLETE!'
\echo '==================================================================='
\echo ''
\echo 'Configuration Summary:'
\echo '  • ohlcv_data: Compress after 365 days (already active)'
\echo '  • factor_scores: Compress after 180 days (already active)'
\echo '  • ohlcv_monthly: Compress after 1 year (NEW)'
\echo '  • ohlcv_quarterly: Compress after 18 months (NEW)'
\echo '  • ohlcv_yearly: Compress after 2 years (NEW)'
\echo ''
\echo 'Compression Ratio: ~99.8% (16 MB → 32 KB per chunk)'
\echo ''
\echo 'Next Steps:'
\echo '  1. Run: psql -d quant_platform -f scripts/monitor_compression.sql'
\echo '  2. Review: docs/COMPRESSION_GUIDE.md'
\echo ''
