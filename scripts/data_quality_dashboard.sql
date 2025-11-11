-- ==============================================================================
-- DATA QUALITY DASHBOARD QUERIES
-- Purpose: Comprehensive fundamental data assessment for quant analysis
-- Created: 2025-11-04
-- ==============================================================================

-- ==============================================================================
-- SECTION 1: FUNDAMENTAL DATA OVERVIEW
-- ==============================================================================

-- Query 1.1: Period Type Distribution
-- Shows breakdown of fundamental records by period type
SELECT
    period_type,
    COUNT(*) as record_count,
    COUNT(DISTINCT ticker) as unique_tickers,
    MIN(date) as earliest_date,
    MAX(date) as latest_date,
    ROUND(AVG(CASE WHEN net_income IS NOT NULL THEN 1 ELSE 0 END) * 100, 2) as net_income_fill_rate
FROM ticker_fundamentals
GROUP BY period_type
ORDER BY period_type;

-- Query 1.2: Fiscal Year Coverage
-- Identifies which fiscal years have data by period type
SELECT
    fiscal_year,
    period_type,
    COUNT(*) as record_count,
    COUNT(DISTINCT ticker) as unique_tickers
FROM ticker_fundamentals
WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
  AND fiscal_year IS NOT NULL
GROUP BY fiscal_year, period_type
ORDER BY fiscal_year DESC, period_type;

-- ==============================================================================
-- SECTION 2: DATA COMPLETENESS ASSESSMENT
-- ==============================================================================

-- Query 2.1: Key Column Completeness (QUARTERLY/ANNUAL/SEMI-ANNUAL only)
-- Shows fill rates for critical fundamental metrics
WITH fundamental_records AS (
    SELECT * FROM ticker_fundamentals
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
)
SELECT
    'Total Records' as metric,
    COUNT(*)::text as value,
    '100.00%' as fill_rate
FROM fundamental_records
UNION ALL
SELECT 'Unique Tickers', COUNT(DISTINCT ticker)::text, '-'
FROM fundamental_records
UNION ALL
SELECT 'shares_outstanding',
    SUM(CASE WHEN shares_outstanding > 0 THEN 1 ELSE 0 END)::text,
    ROUND(100.0 * SUM(CASE WHEN shares_outstanding > 0 THEN 1 ELSE 0 END) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'market_cap',
    SUM(CASE WHEN market_cap > 0 THEN 1 ELSE 0 END)::text,
    ROUND(100.0 * SUM(CASE WHEN market_cap > 0 THEN 1 ELSE 0 END) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'per (P/E)',
    COUNT(per)::text,
    ROUND(100.0 * COUNT(per) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'pbr (P/B)',
    COUNT(pbr)::text,
    ROUND(100.0 * COUNT(pbr) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'ev_ebitda',
    COUNT(ev_ebitda)::text,
    ROUND(100.0 * COUNT(ev_ebitda) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'net_income',
    COUNT(net_income)::text,
    ROUND(100.0 * COUNT(net_income) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'revenue',
    COUNT(revenue)::text,
    ROUND(100.0 * COUNT(revenue) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'operating_profit',
    COUNT(operating_profit)::text,
    ROUND(100.0 * COUNT(operating_profit) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'total_assets',
    COUNT(total_assets)::text,
    ROUND(100.0 * COUNT(total_assets) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'total_equity',
    COUNT(total_equity)::text,
    ROUND(100.0 * COUNT(total_equity) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'current_assets',
    COUNT(current_assets)::text,
    ROUND(100.0 * COUNT(current_assets) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'current_liabilities',
    COUNT(current_liabilities)::text,
    ROUND(100.0 * COUNT(current_liabilities) / COUNT(*), 2)::text || '%'
FROM fundamental_records
UNION ALL
SELECT 'ebitda',
    COUNT(ebitda)::text,
    ROUND(100.0 * COUNT(ebitda) / COUNT(*), 2)::text || '%'
FROM fundamental_records;

-- ==============================================================================
-- SECTION 3: TICKER COVERAGE ANALYSIS
-- ==============================================================================

-- Query 3.1: Stock Coverage by Region
-- Shows fundamental coverage for active stocks
WITH fundamental_tickers AS (
    SELECT DISTINCT ticker, region
    FROM ticker_fundamentals
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
)
SELECT
    t.region,
    COUNT(*) as total_stocks,
    COUNT(ft.ticker) as with_fundamentals,
    COUNT(*) - COUNT(ft.ticker) as missing_fundamentals,
    ROUND(100.0 * COUNT(ft.ticker) / COUNT(*), 2) as coverage_pct
FROM tickers t
LEFT JOIN fundamental_tickers ft ON t.ticker = ft.ticker AND t.region = ft.region
WHERE t.asset_type = 'STOCK' AND t.is_active = true
GROUP BY t.region
ORDER BY coverage_pct DESC;

-- Query 3.2: Top 30 Tickers by Fundamental Data Completeness
-- Identifies tickers with most historical fundamental data
SELECT
    ticker,
    COUNT(*) as total_records,
    COUNT(DISTINCT period_type) as unique_periods,
    MIN(date) as earliest_record,
    MAX(date) as latest_record,
    MAX(fiscal_year) as latest_fiscal_year,
    MIN(fiscal_year) as earliest_fiscal_year,
    CASE
        WHEN MIN(date) IS NOT NULL AND MAX(date) IS NOT NULL
        THEN ROUND((MAX(date) - MIN(date))::numeric / 365.25, 1)
        ELSE 0
    END as years_coverage
FROM ticker_fundamentals
WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
GROUP BY ticker
ORDER BY total_records DESC, years_coverage DESC
LIMIT 30;

-- ==============================================================================
-- SECTION 4: LIQUIDITY-BASED PRIORITY ANALYSIS
-- ==============================================================================

-- Query 4.1: Top 100 Liquid Stocks by Volume (Last 90 days)
-- Identifies highest priority tickers for backfill based on trading volume
SELECT
    o.ticker,
    t.name,
    COUNT(DISTINCT o.date) as trading_days,
    ROUND(AVG(o.volume)::numeric, 0) as avg_volume,
    ROUND(AVG(o.close * o.volume)::numeric, 0) as avg_turnover_krw,
    CASE WHEN ft.ticker IS NOT NULL THEN 'YES' ELSE 'NO' END as has_fundamental,
    CASE
        WHEN ft.ticker IS NOT NULL THEN
            (SELECT COUNT(*) FROM ticker_fundamentals tf
             WHERE tf.ticker = o.ticker AND tf.region = o.region
             AND tf.period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL'))
        ELSE 0
    END as fundamental_count
FROM ohlcv_data o
JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
LEFT JOIN (
    SELECT DISTINCT ticker, region
    FROM ticker_fundamentals
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
) ft ON o.ticker = ft.ticker AND o.region = ft.region
WHERE o.region = 'KR'
  AND t.asset_type = 'STOCK'
  AND o.date >= CURRENT_DATE - INTERVAL '90 days'
  AND o.volume > 0
GROUP BY o.ticker, o.region, t.name, ft.ticker
HAVING COUNT(DISTINCT o.date) >= 30
ORDER BY avg_volume DESC
LIMIT 100;

-- Query 4.2: Liquid Stocks Missing Fundamentals Summary
-- High-priority tickers for initial data collection
WITH liquid_stocks AS (
    SELECT
        o.ticker,
        o.region,
        COUNT(DISTINCT o.date) as trading_days,
        AVG(o.volume) as avg_volume
    FROM ohlcv_data o
    JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
    WHERE o.region = 'KR'
      AND t.asset_type = 'STOCK'
      AND o.date >= CURRENT_DATE - INTERVAL '90 days'
      AND o.volume > 0
    GROUP BY o.ticker, o.region
    HAVING COUNT(DISTINCT o.date) >= 30
    ORDER BY AVG(o.volume) DESC
    LIMIT 500
),
fundamental_tickers AS (
    SELECT DISTINCT ticker, region
    FROM ticker_fundamentals
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
)
SELECT
    COUNT(*) as total_liquid_stocks,
    SUM(CASE WHEN ft.ticker IS NOT NULL THEN 1 ELSE 0 END) as with_fundamentals,
    SUM(CASE WHEN ft.ticker IS NULL THEN 1 ELSE 0 END) as missing_fundamentals,
    ROUND(100.0 * SUM(CASE WHEN ft.ticker IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as coverage_pct
FROM liquid_stocks ls
LEFT JOIN fundamental_tickers ft ON ls.ticker = ft.ticker AND ls.region = ft.region;

-- ==============================================================================
-- SECTION 5: MISSING QUARTERS IDENTIFICATION
-- ==============================================================================

-- Query 5.1: Expected vs Actual Quarterly Records (2020-2024)
-- For tickers WITH fundamentals, identifies missing quarters
WITH expected_quarters AS (
    -- Generate expected quarters from Q1 2020 to Q4 2024
    SELECT
        ticker,
        region,
        generate_series(
            '2020-01-01'::date,
            '2024-12-31'::date,
            '3 months'::interval
        )::date as expected_quarter_end
    FROM (SELECT DISTINCT ticker, region FROM ticker_fundamentals
          WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')) t
),
actual_quarters AS (
    SELECT
        ticker,
        region,
        date,
        period_type
    FROM ticker_fundamentals
    WHERE period_type = 'QUARTERLY'
)
SELECT
    eq.ticker,
    EXTRACT(YEAR FROM eq.expected_quarter_end) as year,
    EXTRACT(QUARTER FROM eq.expected_quarter_end) as quarter,
    eq.expected_quarter_end,
    CASE WHEN aq.date IS NOT NULL THEN 'EXISTS' ELSE 'MISSING' END as status
FROM expected_quarters eq
LEFT JOIN actual_quarters aq
    ON eq.ticker = aq.ticker
    AND eq.region = aq.region
    AND eq.expected_quarter_end = aq.date
WHERE EXTRACT(YEAR FROM eq.expected_quarter_end) >= 2020
ORDER BY eq.ticker, eq.expected_quarter_end DESC
LIMIT 100;

-- Query 5.2: Missing Quarters Count by Ticker (Top 20)
-- Aggregates missing quarterly data by ticker
WITH expected_quarters AS (
    SELECT
        ticker,
        region,
        generate_series(
            '2020-01-01'::date,
            '2024-12-31'::date,
            '3 months'::interval
        )::date as expected_quarter_end
    FROM (SELECT DISTINCT ticker, region FROM ticker_fundamentals
          WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')) t
),
actual_quarters AS (
    SELECT ticker, region, date
    FROM ticker_fundamentals
    WHERE period_type = 'QUARTERLY'
),
missing_count AS (
    SELECT
        eq.ticker,
        COUNT(*) as total_expected_quarters,
        COUNT(aq.date) as actual_quarters,
        COUNT(*) - COUNT(aq.date) as missing_quarters
    FROM expected_quarters eq
    LEFT JOIN actual_quarters aq
        ON eq.ticker = aq.ticker
        AND eq.region = aq.region
        AND eq.expected_quarter_end = aq.date
    WHERE EXTRACT(YEAR FROM eq.expected_quarter_end) >= 2020
    GROUP BY eq.ticker
)
SELECT
    m.ticker,
    t.name,
    m.total_expected_quarters,
    m.actual_quarters,
    m.missing_quarters,
    ROUND(100.0 * m.missing_quarters / m.total_expected_quarters, 2) as missing_pct
FROM missing_count m
JOIN tickers t ON m.ticker = t.ticker
ORDER BY m.missing_quarters DESC
LIMIT 20;

-- ==============================================================================
-- SECTION 6: DATA QUALITY SCORES
-- ==============================================================================

-- Query 6.1: Fundamental Data Quality Score by Ticker
-- Composite quality score based on completeness, timeliness, and depth
WITH ticker_quality AS (
    SELECT
        tf.ticker,
        COUNT(*) as total_records,
        -- Completeness: % of key columns filled
        ROUND(AVG(
            CASE WHEN net_income IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN revenue IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN total_assets IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN total_equity IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN operating_profit IS NOT NULL THEN 1 ELSE 0 END
        ) * 20, 2) as completeness_score,
        -- Timeliness: Most recent data date
        MAX(date) as latest_date,
        CASE
            WHEN MAX(date) >= CURRENT_DATE - INTERVAL '6 months' THEN 100
            WHEN MAX(date) >= CURRENT_DATE - INTERVAL '1 year' THEN 70
            WHEN MAX(date) >= CURRENT_DATE - INTERVAL '2 years' THEN 40
            ELSE 10
        END as timeliness_score,
        -- Depth: Historical coverage in years
        CASE
            WHEN MIN(date) IS NOT NULL AND MAX(date) IS NOT NULL
            THEN ROUND((MAX(date) - MIN(date))::numeric / 365.25, 1)
            ELSE 0
        END as years_coverage,
        CASE
            WHEN (MAX(date) - MIN(date))::numeric >= 1825 THEN 100  -- 5+ years
            WHEN (MAX(date) - MIN(date))::numeric >= 1095 THEN 80   -- 3+ years
            WHEN (MAX(date) - MIN(date))::numeric >= 365 THEN 50    -- 1+ year
            ELSE 20
        END as depth_score
    FROM ticker_fundamentals tf
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
    GROUP BY tf.ticker
)
SELECT
    tq.ticker,
    t.name,
    tq.total_records,
    tq.completeness_score,
    tq.timeliness_score,
    tq.depth_score,
    ROUND((tq.completeness_score * 0.4 + tq.timeliness_score * 0.3 + tq.depth_score * 0.3), 2) as composite_quality_score,
    tq.latest_date,
    tq.years_coverage
FROM ticker_quality tq
JOIN tickers t ON tq.ticker = t.ticker
ORDER BY composite_quality_score DESC
LIMIT 50;

-- ==============================================================================
-- SECTION 7: BACKFILL PRIORITY MATRIX
-- ==============================================================================

-- Query 7.1: Backfill Priority Ranking (Top 200 tickers)
-- Combines liquidity + quality + strategic importance
WITH liquidity_rank AS (
    SELECT
        o.ticker,
        o.region,
        AVG(o.volume) as avg_volume,
        ROW_NUMBER() OVER (ORDER BY AVG(o.volume) DESC) as volume_rank
    FROM ohlcv_data o
    JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
    WHERE o.region = 'KR'
      AND t.asset_type = 'STOCK'
      AND o.date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY o.ticker, o.region
),
quality_score AS (
    SELECT
        ticker,
        COUNT(*) as record_count,
        ROUND((MAX(date) - MIN(date))::numeric / 365.25, 1) as years_coverage,
        CASE
            WHEN COUNT(*) >= 20 THEN 100
            WHEN COUNT(*) >= 12 THEN 70
            WHEN COUNT(*) >= 4 THEN 40
            ELSE 20
        END as record_score
    FROM ticker_fundamentals
    WHERE period_type IN ('QUARTERLY', 'ANNUAL', 'SEMI-ANNUAL')
    GROUP BY ticker
)
SELECT
    lr.ticker,
    t.name,
    lr.volume_rank,
    ROUND(lr.avg_volume::numeric, 0) as avg_volume,
    COALESCE(qs.record_count, 0) as fundamental_records,
    COALESCE(qs.years_coverage, 0) as years_coverage,
    COALESCE(qs.record_score, 0) as quality_score,
    -- Priority score: Higher volume rank = higher priority
    -- Lower quality = higher priority (need backfill)
    ROUND(
        (1000 - lr.volume_rank) * 0.7 +  -- Liquidity weight: 70%
        (100 - COALESCE(qs.record_score, 0)) * 0.3  -- Quality gap weight: 30%
    , 2) as backfill_priority_score,
    CASE
        WHEN lr.volume_rank <= 100 AND COALESCE(qs.record_count, 0) < 12 THEN 'CRITICAL'
        WHEN lr.volume_rank <= 200 AND COALESCE(qs.record_count, 0) < 8 THEN 'HIGH'
        WHEN lr.volume_rank <= 500 AND COALESCE(qs.record_count, 0) < 4 THEN 'MEDIUM'
        ELSE 'LOW'
    END as priority_tier
FROM liquidity_rank lr
JOIN tickers t ON lr.ticker = t.ticker AND lr.region = t.region
LEFT JOIN quality_score qs ON lr.ticker = qs.ticker
WHERE lr.volume_rank <= 500
ORDER BY backfill_priority_score DESC
LIMIT 200;

-- ==============================================================================
-- END OF DATA QUALITY DASHBOARD
-- ==============================================================================

-- USAGE INSTRUCTIONS:
-- 1. Run Section 1-3 queries to understand current data state
-- 2. Run Section 4 to identify high-priority tickers
-- 3. Run Section 5-6 to assess missing data and quality scores
-- 4. Run Section 7 to generate backfill priority list
-- 5. Export results to CSV for tracking and planning

-- RECOMMENDATIONS:
-- - Focus on CRITICAL tier tickers first (Top 100 liquid + <12 records)
-- - Target 3 years of quarterly data (2022-2024) for Phase 1
-- - Extend to 5 years (2020-2024) for Phase 2
-- - Add shares_outstanding calculation to enable per/pbr metrics
