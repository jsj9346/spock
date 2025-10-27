-- ============================================================================
-- Performance Testing for Quarterly Continuous Aggregate
-- ============================================================================
-- Purpose: Benchmark query performance for ohlcv_quarterly
-- Target: <200ms for single-ticker, <500ms for multi-ticker, <1s for aggregates
-- Created: 2025-10-21
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'PERFORMANCE TESTING: ohlcv_quarterly'
\echo '==================================================================='
\echo ''

-- Enable timing
\timing on

-- ============================================================================
-- Test 1: Single Ticker Quarterly Data (Target: <200ms)
-- ============================================================================
\echo ''
\echo 'Test 1: Single ticker quarterly data (005930 - Samsung Electronics)'
\echo '-------------------------------------------------------------------'
SELECT
    ticker,
    region,
    quarter::date,
    open,
    close,
    volume,
    trading_days,
    price_volatility,
    quarter_range_pct
FROM ohlcv_quarterly
WHERE ticker = '005930' AND region = 'KR'
ORDER BY quarter DESC;

-- ============================================================================
-- Test 2: Multi-Ticker Quarterly Comparison (Target: <500ms)
-- ============================================================================
\echo ''
\echo 'Test 2: Multi-ticker quarterly comparison (Top 3 KR stocks)'
\echo '-------------------------------------------------------------------'
SELECT
    ticker,
    quarter::date,
    close,
    volume,
    trading_days,
    price_volatility
FROM ohlcv_quarterly
WHERE region = 'KR'
  AND ticker IN ('005930', '000660', '035420')
  AND quarter >= '2024-01-01'
ORDER BY quarter DESC, ticker;

-- ============================================================================
-- Test 3: Aggregate of Aggregates (Target: <1s)
-- ============================================================================
\echo ''
\echo 'Test 3: Market-wide quarterly statistics'
\echo '-------------------------------------------------------------------'
SELECT
    quarter::date,
    COUNT(DISTINCT ticker) as num_tickers,
    ROUND(AVG(close), 2) as avg_close,
    SUM(volume) as total_volume,
    ROUND(AVG(trading_days), 1) as avg_trading_days,
    ROUND(AVG(price_volatility), 2) as avg_volatility
FROM ohlcv_quarterly
WHERE region = 'KR'
GROUP BY quarter
ORDER BY quarter DESC;

-- ============================================================================
-- Test 4: Comparison with Raw Daily Data (Speedup Test)
-- ============================================================================
\echo ''
\echo 'Test 4A: Query using continuous aggregate (FAST)'
\echo '-------------------------------------------------------------------'
SELECT ticker, quarter::date, close, volume
FROM ohlcv_quarterly
WHERE ticker = '005930' AND region = 'KR'
ORDER BY quarter DESC;

\echo ''
\echo 'Test 4B: Query using raw daily data (SLOW - for comparison)'
\echo '-------------------------------------------------------------------'
SELECT
    ticker,
    time_bucket('3 months', date)::date AS quarter,
    last(close, date) as close,
    sum(volume) as volume
FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR' AND timeframe = 'D'
GROUP BY ticker, quarter
ORDER BY quarter DESC;

-- Disable timing
\timing off

-- ============================================================================
-- Summary Report
-- ============================================================================
\echo ''
\echo '==================================================================='
\echo 'PERFORMANCE TEST SUMMARY'
\echo '==================================================================='
\echo ''
\echo 'View Statistics:'
SELECT
    COUNT(*) as total_quarters,
    COUNT(DISTINCT ticker) as num_tickers,
    MIN(quarter)::date as first_quarter,
    MAX(quarter)::date as last_quarter,
    pg_size_pretty(pg_total_relation_size('ohlcv_quarterly')) as view_size
FROM ohlcv_quarterly;

\echo ''
\echo 'Refresh Policy:'
SELECT
    job_id,
    schedule_interval,
    next_start::timestamp as next_refresh,
    config->>'start_offset' as data_window_start,
    config->>'end_offset' as data_window_end
FROM timescaledb_information.jobs
WHERE application_name LIKE '%ohlcv_quarterly%';

\echo ''
\echo '✅ Performance testing complete!'
\echo ''
\echo 'Expected Results:'
\echo '  - Test 1 (single ticker): <200ms'
\echo '  - Test 2 (multi-ticker): <500ms'
\echo '  - Test 3 (aggregates): <1s'
\echo '  - Test 4 speedup: 10-100x faster than raw data'
\echo ''
