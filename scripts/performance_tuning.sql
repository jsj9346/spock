-- ============================================================================
-- Database Performance Tuning Script
-- ============================================================================
-- Purpose: Enable performance monitoring and optimize database configuration
-- Usage: psql -d quant_platform -f scripts/performance_tuning.sql
-- Created: 2025-10-21
-- Part of: Phase 1 Task 5 (Performance Tuning)
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'TASK 5: DATABASE PERFORMANCE TUNING'
\echo '==================================================================='
\echo ''

-- ============================================================================
-- SECTION 1: Enable Performance Monitoring
-- ============================================================================

\echo 'Section 1: Enable Performance Monitoring'
\echo '-------------------------------------------------------------------'
\echo ''

-- Enable pg_stat_statements extension for query performance tracking
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

\echo '  ✅ pg_stat_statements extension enabled'
\echo ''

-- Verify extension is loaded
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'pg_stat_statements';

\echo ''

-- ============================================================================
-- SECTION 2: Current Database Statistics
-- ============================================================================

\echo 'Section 2: Current Database Statistics'
\echo '-------------------------------------------------------------------'
\echo ''

-- Database size
\echo 'Database Size:'
SELECT
    pg_database.datname as database_name,
    pg_size_pretty(pg_database_size(pg_database.datname)) as size
FROM pg_database
WHERE datname = 'quant_platform';

\echo ''

-- Table sizes (top 10 largest)
\echo 'Top 10 Largest Tables:'
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) -
                   pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

\echo ''

-- Index sizes (top 10 largest)
\echo 'Top 10 Largest Indexes:'
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC
LIMIT 10;

\echo ''

-- ============================================================================
-- SECTION 3: Query Performance Analysis
-- ============================================================================

\echo 'Section 3: Query Performance Analysis'
\echo '-------------------------------------------------------------------'
\echo ''

-- Top 10 slowest queries by average execution time
\echo 'Top 10 Slowest Queries (by average execution time):'
SELECT
    SUBSTRING(query, 1, 80) as query_preview,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    ROUND(mean_exec_time::numeric, 2) as avg_time_ms,
    ROUND(max_exec_time::numeric, 2) as max_time_ms,
    ROUND((100 * total_exec_time / SUM(total_exec_time) OVER())::numeric, 2) as pct_total_time
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
  AND query NOT LIKE '%pg_catalog%'
ORDER BY mean_exec_time DESC
LIMIT 10;

\echo ''

-- Top 10 most frequently called queries
\echo 'Top 10 Most Frequently Called Queries:'
SELECT
    SUBSTRING(query, 1, 80) as query_preview,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    ROUND(mean_exec_time::numeric, 2) as avg_time_ms
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
  AND query NOT LIKE '%pg_catalog%'
ORDER BY calls DESC
LIMIT 10;

\echo ''

-- ============================================================================
-- SECTION 4: Index Usage Analysis
-- ============================================================================

\echo 'Section 4: Index Usage Analysis'
\echo '-------------------------------------------------------------------'
\echo ''

-- Unused or rarely used indexes
\echo 'Potentially Unused Indexes (0 scans):'
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND idx_scan = 0
  AND indexname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC;

\echo ''

-- Most used indexes
\echo 'Most Used Indexes (top 10):'
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC
LIMIT 10;

\echo ''

-- ============================================================================
-- SECTION 5: Cache Hit Ratio Analysis
-- ============================================================================

\echo 'Section 5: Cache Hit Ratio Analysis'
\echo '-------------------------------------------------------------------'
\echo ''

-- Table cache hit ratio (should be >90%)
\echo 'Table Cache Hit Ratio:'
SELECT
    'Tables' as type,
    ROUND(
        100.0 * SUM(heap_blks_hit) / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0),
        2
    ) as cache_hit_ratio_pct,
    pg_size_pretty(SUM(heap_blks_hit * 8192)) as hit_size,
    pg_size_pretty(SUM(heap_blks_read * 8192)) as miss_size
FROM pg_statio_user_tables;

\echo ''

-- Index cache hit ratio (should be >90%)
\echo 'Index Cache Hit Ratio:'
SELECT
    'Indexes' as type,
    ROUND(
        100.0 * SUM(idx_blks_hit) / NULLIF(SUM(idx_blks_hit + idx_blks_read), 0),
        2
    ) as cache_hit_ratio_pct,
    pg_size_pretty(SUM(idx_blks_hit * 8192)) as hit_size,
    pg_size_pretty(SUM(idx_blks_read * 8192)) as miss_size
FROM pg_statio_user_indexes;

\echo ''

-- Per-table cache hit ratio
\echo 'Per-Table Cache Hit Ratio (top 10 by size):'
SELECT
    schemaname,
    relname as table_name,
    heap_blks_read as disk_reads,
    heap_blks_hit as cache_hits,
    ROUND(
        100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0),
        2
    ) as cache_hit_ratio_pct,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||relname)) as table_size
FROM pg_statio_user_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||relname) DESC
LIMIT 10;

\echo ''

-- ============================================================================
-- SECTION 6: Update Table Statistics
-- ============================================================================

\echo 'Section 6: Update Table Statistics (ANALYZE)'
\echo '-------------------------------------------------------------------'
\echo ''

\echo 'Analyzing all tables for query planner optimization...'
\echo ''

-- Analyze all major tables
ANALYZE tickers;
\echo '  ✅ tickers analyzed'

ANALYZE ohlcv_data;
\echo '  ✅ ohlcv_data analyzed'

ANALYZE factor_scores;
\echo '  ✅ factor_scores analyzed'

ANALYZE stock_details;
\echo '  ✅ stock_details analyzed'

ANALYZE etf_details;
\echo '  ✅ etf_details analyzed'

ANALYZE strategies;
\echo '  ✅ strategies analyzed'

ANALYZE backtest_results;
\echo '  ✅ backtest_results analyzed'

ANALYZE portfolio_holdings;
\echo '  ✅ portfolio_holdings analyzed'

ANALYZE portfolio_transactions;
\echo '  ✅ portfolio_transactions analyzed'

ANALYZE walk_forward_results;
\echo '  ✅ walk_forward_results analyzed'

ANALYZE optimization_history;
\echo '  ✅ optimization_history analyzed'

ANALYZE ticker_fundamentals;
\echo '  ✅ ticker_fundamentals analyzed'

ANALYZE etf_holdings;
\echo '  ✅ etf_holdings analyzed'

ANALYZE global_market_indices;
\echo '  ✅ global_market_indices analyzed'

ANALYZE exchange_rate_history;
\echo '  ✅ exchange_rate_history analyzed'

\echo ''
\echo '  All tables analyzed successfully'
\echo ''

-- ============================================================================
-- SECTION 7: Connection Statistics
-- ============================================================================

\echo 'Section 7: Connection Statistics'
\echo '-------------------------------------------------------------------'
\echo ''

-- Current connections
\echo 'Current Database Connections:'
SELECT
    COUNT(*) as total_connections,
    COUNT(*) FILTER (WHERE state = 'active') as active,
    COUNT(*) FILTER (WHERE state = 'idle') as idle,
    COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
FROM pg_stat_activity
WHERE datname = 'quant_platform';

\echo ''

-- Connection details
\echo 'Connection Details by State:'
SELECT
    state,
    COUNT(*) as count,
    MAX(NOW() - state_change) as max_duration
FROM pg_stat_activity
WHERE datname = 'quant_platform'
GROUP BY state
ORDER BY count DESC;

\echo ''

-- ============================================================================
-- SECTION 8: Vacuum Statistics
-- ============================================================================

\echo 'Section 8: Vacuum Statistics'
\echo '-------------------------------------------------------------------'
\echo ''

-- Tables needing vacuum (dead tuples)
\echo 'Tables with Dead Tuples (needing VACUUM):'
SELECT
    schemaname,
    relname as table_name,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) as dead_tuple_pct,
    last_vacuum,
    last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND n_dead_tup > 0
ORDER BY n_dead_tup DESC;

\echo ''

-- ============================================================================
-- SECTION 9: Query Plan Analysis Examples
-- ============================================================================

\echo 'Section 9: Query Plan Analysis Examples'
\echo '-------------------------------------------------------------------'
\echo ''

\echo 'Example 1: OHLCV Data Query Plan (10-year data):'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ticker, date, close, volume
FROM ohlcv_data
WHERE ticker = '005930'
  AND region = 'KR'
  AND date >= CURRENT_DATE - INTERVAL '10 years'
ORDER BY date DESC
LIMIT 1000;

\echo ''

\echo 'Example 2: Factor Scores Query Plan:'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ticker, region, date, factor_name, score
FROM factor_scores
WHERE factor_name = 'momentum'
  AND date >= CURRENT_DATE - INTERVAL '1 year'
ORDER BY date DESC, score DESC
LIMIT 100;

\echo ''

\echo 'Example 3: Continuous Aggregate Query Plan (Monthly):'
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ticker, region, month, open, close, volume
FROM ohlcv_monthly
WHERE ticker = '005930'
  AND region = 'KR'
  AND month >= CURRENT_DATE - INTERVAL '5 years'
ORDER BY month DESC;

\echo ''

-- ============================================================================
-- SECTION 10: Performance Recommendations
-- ============================================================================

\echo 'Section 10: Performance Recommendations'
\echo '-------------------------------------------------------------------'
\echo ''

-- Recommendations based on analysis
DO $$
DECLARE
    table_cache_ratio NUMERIC;
    index_cache_ratio NUMERIC;
    total_connections INTEGER;
    dead_tuple_tables INTEGER;
BEGIN
    -- Get cache hit ratios
    SELECT
        ROUND(100.0 * SUM(heap_blks_hit) / NULLIF(SUM(heap_blks_hit + heap_blks_read), 0), 2)
    INTO table_cache_ratio
    FROM pg_statio_user_tables;

    SELECT
        ROUND(100.0 * SUM(idx_blks_hit) / NULLIF(SUM(idx_blks_hit + idx_blks_read), 0), 2)
    INTO index_cache_ratio
    FROM pg_statio_user_indexes;

    -- Get connection count
    SELECT COUNT(*) INTO total_connections
    FROM pg_stat_activity
    WHERE datname = 'quant_platform';

    -- Get tables with significant dead tuples
    SELECT COUNT(*) INTO dead_tuple_tables
    FROM pg_stat_user_tables
    WHERE n_dead_tup > 1000;

    RAISE NOTICE '';
    RAISE NOTICE 'Performance Recommendations:';
    RAISE NOTICE '----------------------------';
    RAISE NOTICE '';

    -- Cache hit ratio recommendations
    IF table_cache_ratio < 90 THEN
        RAISE NOTICE '⚠️ Table Cache Hit Ratio: %.2f%% (Target: >90%%)', table_cache_ratio;
        RAISE NOTICE '   Recommendation: Increase shared_buffers in postgresql.conf';
    ELSE
        RAISE NOTICE '✅ Table Cache Hit Ratio: %.2f%% (Good)', table_cache_ratio;
    END IF;

    IF index_cache_ratio < 90 THEN
        RAISE NOTICE '⚠️ Index Cache Hit Ratio: %.2f%% (Target: >90%%)', index_cache_ratio;
        RAISE NOTICE '   Recommendation: Increase effective_cache_size in postgresql.conf';
    ELSE
        RAISE NOTICE '✅ Index Cache Hit Ratio: %.2f%% (Good)', index_cache_ratio;
    END IF;

    RAISE NOTICE '';

    -- Connection pool recommendations
    IF total_connections < 5 THEN
        RAISE NOTICE '⚠️ Current Connections: % (Low)', total_connections;
        RAISE NOTICE '   Recommendation: Consider increasing connection pool minimum';
    ELSIF total_connections > 50 THEN
        RAISE NOTICE '⚠️ Current Connections: % (High)', total_connections;
        RAISE NOTICE '   Recommendation: Review connection pool settings';
    ELSE
        RAISE NOTICE '✅ Current Connections: % (Normal)', total_connections;
    END IF;

    RAISE NOTICE '';

    -- Dead tuple recommendations
    IF dead_tuple_tables > 0 THEN
        RAISE NOTICE '⚠️ Tables with Dead Tuples: %', dead_tuple_tables;
        RAISE NOTICE '   Recommendation: Run VACUUM ANALYZE on affected tables';
    ELSE
        RAISE NOTICE '✅ No significant dead tuples detected';
    END IF;

    RAISE NOTICE '';
END $$;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

\echo '==================================================================='
\echo '✅ PERFORMANCE TUNING ANALYSIS COMPLETE!'
\echo '==================================================================='
\echo ''
\echo 'Summary:'
\echo '  • pg_stat_statements extension enabled'
\echo '  • All tables analyzed (statistics updated)'
\echo '  • Query performance metrics collected'
\echo '  • Cache hit ratios analyzed'
\echo '  • Index usage statistics reviewed'
\echo ''
\echo 'Next Steps:'
\echo '  1. Review slow queries and optimize as needed'
\echo '  2. Consider removing unused indexes (if any)'
\echo '  3. Run VACUUM if dead tuples detected'
\echo '  4. Monitor cache hit ratios (target: >90%)'
\echo '  5. Run benchmark_queries.py for performance testing'
\echo ''
\echo 'Documentation: docs/PERFORMANCE_TUNING_GUIDE.md'
\echo ''
