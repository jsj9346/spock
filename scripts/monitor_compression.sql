-- ============================================================================
-- TimescaleDB Compression Monitoring Dashboard
-- ============================================================================
-- Purpose: Monitor compression status, effectiveness, and storage savings
-- Usage: psql -d quant_platform -f scripts/monitor_compression.sql
-- Created: 2025-10-21
-- Part of: Phase 1 Task 3 (Compression Policy Setup)
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'TIMESCALEDB COMPRESSION MONITORING DASHBOARD'
\echo '==================================================================='
\echo ''

-- ============================================================================
-- SECTION 1: Compression Status Overview
-- ============================================================================

\echo 'SECTION 1: Compression Status Overview'
\echo '-------------------------------------------------------------------'
\echo ''

SELECT
    hypertable_schema,
    hypertable_name,
    COUNT(*) as total_chunks,
    COUNT(*) FILTER (WHERE is_compressed) as compressed_chunks,
    COUNT(*) FILTER (WHERE NOT is_compressed) as uncompressed_chunks,
    ROUND(
        COUNT(*) FILTER (WHERE is_compressed)::numeric / COUNT(*) * 100,
        2
    ) as compression_pct,
    pg_size_pretty(
        SUM(pg_total_relation_size(chunk_schema || '.' || chunk_name))
    ) as total_size,
    pg_size_pretty(
        SUM(pg_total_relation_size(chunk_schema || '.' || chunk_name))
        FILTER (WHERE is_compressed)
    ) as compressed_size,
    pg_size_pretty(
        SUM(pg_total_relation_size(chunk_schema || '.' || chunk_name))
        FILTER (WHERE NOT is_compressed)
    ) as uncompressed_size
FROM timescaledb_information.chunks
WHERE hypertable_name IN ('ohlcv_data', 'factor_scores', 'ohlcv_monthly', 'ohlcv_quarterly', 'ohlcv_yearly')
GROUP BY hypertable_schema, hypertable_name
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- SECTION 2: Compression Ratio Analysis
-- ============================================================================

\echo 'SECTION 2: Compression Ratio Analysis'
\echo '-------------------------------------------------------------------'
\echo ''

WITH compression_stats AS (
    SELECT
        hypertable_name,
        chunk_name,
        before_compression_total_bytes,
        after_compression_total_bytes,
        CASE
            WHEN before_compression_total_bytes > 0 THEN
                ROUND(
                    (1 - after_compression_total_bytes::numeric / before_compression_total_bytes) * 100,
                    2
                )
            ELSE 0
        END as compression_ratio_pct
    FROM timescaledb_information.chunk_compression_stats
)
SELECT
    hypertable_name,
    COUNT(*) as compressed_chunks,
    pg_size_pretty(SUM(before_compression_total_bytes)) as original_size,
    pg_size_pretty(SUM(after_compression_total_bytes)) as compressed_size,
    pg_size_pretty(
        SUM(before_compression_total_bytes) - SUM(after_compression_total_bytes)
    ) as space_saved,
    ROUND(AVG(compression_ratio_pct), 2) || '%' as avg_compression_ratio,
    ROUND(MIN(compression_ratio_pct), 2) || '%' as min_compression_ratio,
    ROUND(MAX(compression_ratio_pct), 2) || '%' as max_compression_ratio
FROM compression_stats
GROUP BY hypertable_name
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- SECTION 3: Compression Policy Status
-- ============================================================================

\echo 'SECTION 3: Compression Policy Status'
\echo '-------------------------------------------------------------------'
\echo ''

SELECT
    job_id,
    hypertable_name,
    schedule_interval,
    config->>'compress_after' as compress_after,
    next_start::timestamp as next_run,
    last_run_status,
    last_successful_finish::timestamp as last_success,
    total_runs,
    total_successes,
    total_failures,
    CASE
        WHEN scheduled THEN '✅ Active'
        ELSE '❌ Inactive'
    END as status
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- SECTION 4: Chunks Pending Compression
-- ============================================================================

\echo 'SECTION 4: Chunks Pending Compression'
\echo '-------------------------------------------------------------------'
\echo ''

WITH policy_settings AS (
    SELECT
        hypertable_name,
        (config->>'compress_after')::interval as compress_after
    FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_compression'
)
SELECT
    c.hypertable_name,
    COUNT(*) as chunks_pending,
    MIN(c.range_start) as oldest_chunk,
    pg_size_pretty(
        SUM(pg_total_relation_size(c.chunk_schema || '.' || c.chunk_name))
    ) as total_size_pending,
    p.compress_after
FROM timescaledb_information.chunks c
JOIN policy_settings p ON c.hypertable_name = p.hypertable_name
WHERE NOT c.is_compressed
  AND c.range_end < NOW() - p.compress_after
GROUP BY c.hypertable_name, p.compress_after
ORDER BY c.hypertable_name;

\echo ''
\echo '  Note: Chunks shown are eligible for compression based on policy'
\echo '  but have not yet been compressed by the background job.'
\echo ''

-- ============================================================================
-- SECTION 5: Compression Settings
-- ============================================================================

\echo 'SECTION 5: Compression Settings'
\echo '-------------------------------------------------------------------'
\echo ''

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
            THEN attname || ' ' || CASE WHEN orderby_desc THEN 'DESC' ELSE 'ASC' END
            ELSE NULL
        END,
        ', '
    ) FILTER (WHERE orderby_column_index IS NOT NULL) as order_by
FROM timescaledb_information.compression_settings
GROUP BY hypertable_schema, hypertable_name
ORDER BY hypertable_name;

\echo ''

-- ============================================================================
-- SECTION 6: Storage Savings Summary
-- ============================================================================

\echo 'SECTION 6: Storage Savings Summary'
\echo '-------------------------------------------------------------------'
\echo ''

WITH total_stats AS (
    SELECT
        SUM(before_compression_total_bytes) as total_before,
        SUM(after_compression_total_bytes) as total_after
    FROM timescaledb_information.chunk_compression_stats
)
SELECT
    pg_size_pretty(total_before) as original_size,
    pg_size_pretty(total_after) as compressed_size,
    pg_size_pretty(total_before - total_after) as space_saved,
    ROUND(
        (1 - total_after::numeric / NULLIF(total_before, 0)) * 100,
        2
    ) || '%' as overall_compression_ratio
FROM total_stats;

\echo ''

-- ============================================================================
-- SECTION 7: Recent Compression Activity
-- ============================================================================

\echo 'SECTION 7: Recent Compression Activity (Last 7 Days)'
\echo '-------------------------------------------------------------------'
\echo ''

SELECT
    job_id,
    hypertable_name,
    last_run_started_at::timestamp as started,
    last_successful_finish::timestamp as finished,
    EXTRACT(EPOCH FROM (last_successful_finish - last_run_started_at))::integer as duration_sec,
    last_run_status,
    total_runs,
    total_successes,
    total_failures
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
  AND last_run_started_at > NOW() - INTERVAL '7 days'
ORDER BY last_run_started_at DESC;

\echo ''

-- ============================================================================
-- SECTION 8: Health Checks
-- ============================================================================

\echo 'SECTION 8: Health Checks'
\echo '-------------------------------------------------------------------'
\echo ''

\echo 'Checking for potential issues...'
\echo ''

-- Check 1: Failed compression jobs
SELECT
    'WARNING: Compression job failures detected' as issue,
    COUNT(*) as occurrences,
    STRING_AGG(DISTINCT hypertable_name, ', ') as affected_tables
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
  AND total_failures > 0
HAVING COUNT(*) > 0;

-- Check 2: Inactive compression policies
SELECT
    'ERROR: Inactive compression policies' as issue,
    COUNT(*) as occurrences,
    STRING_AGG(hypertable_name, ', ') as affected_tables
FROM timescaledb_information.jobs
WHERE proc_name = 'policy_compression'
  AND NOT scheduled
HAVING COUNT(*) > 0;

-- Check 3: Old uncompressed chunks (>30 days past policy)
WITH policy_settings AS (
    SELECT
        hypertable_name,
        (config->>'compress_after')::interval as compress_after
    FROM timescaledb_information.jobs
    WHERE proc_name = 'policy_compression'
)
SELECT
    'WARNING: Old uncompressed chunks detected' as issue,
    COUNT(*) as occurrences,
    STRING_AGG(DISTINCT c.hypertable_name, ', ') as affected_tables
FROM timescaledb_information.chunks c
JOIN policy_settings p ON c.hypertable_name = p.hypertable_name
WHERE NOT c.is_compressed
  AND c.range_end < NOW() - p.compress_after - INTERVAL '30 days'
HAVING COUNT(*) > 0;

\echo ''
\echo 'Health check complete. No output = no issues detected.'
\echo ''

-- ============================================================================
-- Success Message
-- ============================================================================

\echo '==================================================================='
\echo '✅ COMPRESSION MONITORING COMPLETE'
\echo '==================================================================='
\echo ''
\echo 'Quick Actions:'
\echo '  • Force compress pending chunks: SELECT compress_chunk(''<chunk_name>'');'
\echo '  • Decompress a chunk: SELECT decompress_chunk(''<chunk_name>'');'
\echo '  • Refresh policies: SELECT alter_job(<job_id>, scheduled => true);'
\echo ''
\echo 'Documentation: docs/COMPRESSION_GUIDE.md'
\echo ''
