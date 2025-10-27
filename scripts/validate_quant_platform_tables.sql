-- ============================================================================
-- Quant Platform Tables Validation Script
-- ============================================================================
-- Purpose: Comprehensive validation of all Quant Platform tables
-- Usage: psql -d quant_platform -f scripts/validate_quant_platform_tables.sql
-- Created: 2025-10-21
-- Part of: Phase 1 Task 4 (Add Quant Platform Tables)
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'QUANT PLATFORM TABLES VALIDATION'
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
-- TEST 1: Verify All Required Tables Exist
-- ============================================================================

\echo 'Test 1: Verify All Required Tables Exist'
\echo '-------------------------------------------------------------------'

DO $$
DECLARE
    required_tables TEXT[] := ARRAY[
        'strategies',
        'backtest_results',
        'portfolio_holdings',
        'portfolio_transactions',
        'walk_forward_results',
        'optimization_history',
        'factor_scores',
        'ohlcv_data',
        'tickers'
    ];
    missing_tables TEXT[] := '{}';
    table_name TEXT;
    table_exists BOOLEAN;
BEGIN
    FOREACH table_name IN ARRAY required_tables LOOP
        SELECT EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'public' AND tablename = table_name
        ) INTO table_exists;

        IF NOT table_exists THEN
            missing_tables := array_append(missing_tables, table_name);
        END IF;
    END LOOP;

    IF array_length(missing_tables, 1) IS NULL THEN
        INSERT INTO validation_results VALUES
            ('All Required Tables', '✅ PASS', 'All 9 required tables exist', 'INFO');
    ELSE
        INSERT INTO validation_results VALUES
            ('All Required Tables', '❌ FAIL',
             'Missing tables: ' || array_to_string(missing_tables, ', '), 'CRITICAL');
    END IF;
END $$;

SELECT * FROM validation_results WHERE test_name LIKE '%Required Tables%';
\echo ''

-- ============================================================================
-- TEST 2: Verify Foreign Key Constraints
-- ============================================================================

\echo 'Test 2: Verify Foreign Key Constraints'
\echo '-------------------------------------------------------------------'

WITH expected_fks AS (
    SELECT * FROM (VALUES
        ('backtest_results', 'strategy_id', 'strategies', 'id', 'CASCADE'),
        ('portfolio_holdings', 'strategy_id', 'strategies', 'id', 'NO ACTION'),
        ('portfolio_transactions', 'strategy_id', 'strategies', 'id', 'CASCADE'),
        ('walk_forward_results', 'strategy_id', 'strategies', 'id', 'CASCADE')
    ) AS t(table_name, column_name, foreign_table, foreign_column, expected_delete_rule)
),
actual_fks AS (
    SELECT
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table,
        ccu.column_name AS foreign_column,
        rc.delete_rule
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    JOIN information_schema.referential_constraints AS rc
        ON rc.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public'
)
INSERT INTO validation_results
SELECT
    'Foreign Key - ' || e.table_name || '.' || e.column_name,
    CASE
        WHEN a.table_name IS NOT NULL THEN '✅ PASS'
        ELSE '❌ FAIL'
    END,
    CASE
        WHEN a.table_name IS NOT NULL THEN
            'References ' || e.foreign_table || '(' || e.foreign_column || ') ON DELETE ' || a.delete_rule
        ELSE
            'Missing foreign key constraint'
    END,
    CASE
        WHEN a.table_name IS NOT NULL THEN 'INFO'
        ELSE 'CRITICAL'
    END
FROM expected_fks e
LEFT JOIN actual_fks a
    ON e.table_name = a.table_name
    AND e.column_name = a.column_name
    AND e.foreign_table = a.foreign_table;

SELECT * FROM validation_results WHERE test_name LIKE 'Foreign Key%';
\echo ''

-- ============================================================================
-- TEST 3: Verify Indexes Exist
-- ============================================================================

\echo 'Test 3: Verify Indexes Exist'
\echo '-------------------------------------------------------------------'

WITH expected_indexes AS (
    SELECT * FROM (VALUES
        ('portfolio_transactions', 'idx_transactions_strategy'),
        ('portfolio_transactions', 'idx_transactions_ticker'),
        ('portfolio_transactions', 'idx_transactions_date'),
        ('walk_forward_results', 'idx_walkforward_strategy'),
        ('walk_forward_results', 'idx_walkforward_dates'),
        ('walk_forward_results', 'idx_walkforward_ratio'),
        ('optimization_history', 'idx_optimization_date'),
        ('optimization_history', 'idx_optimization_method'),
        ('optimization_history', 'idx_optimization_universe'),
        ('portfolio_holdings', 'idx_holdings_strategy_date'),
        ('backtest_results', 'idx_backtest_results_strategy'),
        ('backtest_results', 'idx_backtest_results_date'),
        ('factor_scores', 'idx_factor_scores_date'),
        ('factor_scores', 'idx_factor_scores_ticker')
    ) AS t(table_name, index_name)
),
actual_indexes AS (
    SELECT tablename, indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
)
INSERT INTO validation_results
SELECT
    'Index - ' || e.index_name,
    CASE
        WHEN a.indexname IS NOT NULL THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Table: ' || e.table_name,
    CASE
        WHEN a.indexname IS NOT NULL THEN 'INFO'
        ELSE 'WARNING'
    END
FROM expected_indexes e
LEFT JOIN actual_indexes a
    ON e.table_name = a.tablename
    AND e.index_name = a.indexname;

SELECT * FROM validation_results WHERE test_name LIKE 'Index%' ORDER BY status, test_name;
\echo ''

-- ============================================================================
-- TEST 4: Verify Column Data Types
-- ============================================================================

\echo 'Test 4: Verify Column Data Types (Sample)'
\echo '-------------------------------------------------------------------'

WITH expected_columns AS (
    SELECT * FROM (VALUES
        ('portfolio_transactions', 'id', 'bigint'),
        ('portfolio_transactions', 'strategy_id', 'integer'),
        ('portfolio_transactions', 'ticker', 'character varying'),
        ('portfolio_transactions', 'transaction_type', 'character varying'),
        ('portfolio_transactions', 'total_value', 'numeric'),
        ('walk_forward_results', 'overfitting_ratio', 'numeric'),
        ('optimization_history', 'optimal_weights', 'jsonb'),
        ('strategies', 'factor_weights', 'jsonb')
    ) AS t(table_name, column_name, expected_type)
),
actual_columns AS (
    SELECT
        table_name,
        column_name,
        CASE
            WHEN data_type = 'USER-DEFINED' THEN udt_name
            ELSE data_type
        END as data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
)
INSERT INTO validation_results
SELECT
    'Column Type - ' || e.table_name || '.' || e.column_name,
    CASE
        WHEN a.data_type LIKE e.expected_type || '%' THEN '✅ PASS'
        WHEN a.data_type IS NOT NULL THEN '⚠️ WARNING'
        ELSE '❌ FAIL'
    END,
    'Expected: ' || e.expected_type || ', Got: ' || COALESCE(a.data_type, 'MISSING'),
    CASE
        WHEN a.data_type LIKE e.expected_type || '%' THEN 'INFO'
        WHEN a.data_type IS NOT NULL THEN 'WARNING'
        ELSE 'CRITICAL'
    END
FROM expected_columns e
LEFT JOIN actual_columns a
    ON e.table_name = a.table_name
    AND e.column_name = a.column_name;

SELECT * FROM validation_results WHERE test_name LIKE 'Column Type%';
\echo ''

-- ============================================================================
-- TEST 5: Verify Check Constraints
-- ============================================================================

\echo 'Test 5: Verify Check Constraints'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Check Constraint - ' || tc.table_name,
    '✅ PASS',
    'Constraint: ' || tc.constraint_name,
    'INFO'
FROM information_schema.table_constraints tc
WHERE tc.constraint_type = 'CHECK'
  AND tc.table_name IN ('portfolio_transactions')
  AND tc.table_schema = 'public';

-- If no check constraints found, add warning
INSERT INTO validation_results
SELECT
    'Check Constraint - portfolio_transactions',
    '⚠️ WARNING',
    'No check constraints found (expected transaction_type CHECK)',
    'WARNING'
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_type = 'CHECK'
      AND table_name = 'portfolio_transactions'
);

SELECT * FROM validation_results WHERE test_name LIKE 'Check Constraint%';
\echo ''

-- ============================================================================
-- TEST 6: Verify Generated Columns
-- ============================================================================

\echo 'Test 6: Verify Generated Columns'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Generated Column - ' || table_name || '.' || column_name,
    CASE
        WHEN generation_expression IS NOT NULL THEN '✅ PASS'
        ELSE '❌ FAIL'
    END,
    CASE
        WHEN generation_expression IS NOT NULL THEN
            'Expression: ' || substring(generation_expression, 1, 50)
        ELSE
            'Column is not generated'
    END,
    CASE
        WHEN generation_expression IS NOT NULL THEN 'INFO'
        ELSE 'WARNING'
    END
FROM information_schema.columns
WHERE table_name = 'portfolio_transactions'
  AND column_name = 'total_value'
  AND table_schema = 'public';

SELECT * FROM validation_results WHERE test_name LIKE 'Generated Column%';
\echo ''

-- ============================================================================
-- TEST 7: Verify Table Row Counts
-- ============================================================================

\echo 'Test 7: Verify Tables Are Accessible'
\echo '-------------------------------------------------------------------'

DO $$
DECLARE
    table_name TEXT;
    row_count BIGINT;
BEGIN
    FOR table_name IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename IN (
              'strategies', 'backtest_results', 'portfolio_holdings',
              'portfolio_transactions', 'walk_forward_results', 'optimization_history'
          )
    LOOP
        EXECUTE 'SELECT COUNT(*) FROM ' || table_name INTO row_count;
        INSERT INTO validation_results VALUES (
            'Table Access - ' || table_name,
            '✅ PASS',
            'Row count: ' || row_count,
            'INFO'
        );
    END LOOP;
END $$;

SELECT * FROM validation_results WHERE test_name LIKE 'Table Access%';
\echo ''

-- ============================================================================
-- TEST 8: Verify TimescaleDB Integration
-- ============================================================================

\echo 'Test 8: Verify TimescaleDB Hypertables'
\echo '-------------------------------------------------------------------'

INSERT INTO validation_results
SELECT
    'Hypertable - ' || hypertable_name,
    '✅ PASS',
    'Dimensions: ' || num_dimensions || ', Chunks: ' || num_chunks,
    'INFO'
FROM timescaledb_information.hypertables
WHERE hypertable_schema = 'public'
  AND hypertable_name IN ('ohlcv_data', 'factor_scores');

-- Check if expected hypertables exist
INSERT INTO validation_results
SELECT
    'Hypertable - ohlcv_data',
    '❌ FAIL',
    'Not configured as hypertable',
    'CRITICAL'
WHERE NOT EXISTS (
    SELECT 1 FROM timescaledb_information.hypertables
    WHERE hypertable_name = 'ohlcv_data'
);

INSERT INTO validation_results
SELECT
    'Hypertable - factor_scores',
    '❌ FAIL',
    'Not configured as hypertable',
    'CRITICAL'
WHERE NOT EXISTS (
    SELECT 1 FROM timescaledb_information.hypertables
    WHERE hypertable_name = 'factor_scores'
);

SELECT * FROM validation_results WHERE test_name LIKE 'Hypertable%';
\echo ''

-- ============================================================================
-- TEST 9: Verify Sample Data Integrity
-- ============================================================================

\echo 'Test 9: Verify Sample Data Integrity'
\echo '-------------------------------------------------------------------'

-- Check portfolio_transactions sample data
INSERT INTO validation_results
SELECT
    'Sample Data - portfolio_transactions',
    CASE
        WHEN COUNT(*) >= 3 THEN '✅ PASS'
        WHEN COUNT(*) > 0 THEN '⚠️ WARNING'
        ELSE '❌ FAIL'
    END,
    'Sample rows: ' || COUNT(*),
    CASE
        WHEN COUNT(*) >= 3 THEN 'INFO'
        WHEN COUNT(*) > 0 THEN 'WARNING'
        ELSE 'CRITICAL'
    END
FROM portfolio_transactions;

-- Check walk_forward_results sample data
INSERT INTO validation_results
SELECT
    'Sample Data - walk_forward_results',
    CASE
        WHEN COUNT(*) >= 1 THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Sample rows: ' || COUNT(*),
    CASE
        WHEN COUNT(*) >= 1 THEN 'INFO'
        ELSE 'WARNING'
    END
FROM walk_forward_results;

-- Check optimization_history sample data
INSERT INTO validation_results
SELECT
    'Sample Data - optimization_history',
    CASE
        WHEN COUNT(*) >= 1 THEN '✅ PASS'
        ELSE '⚠️ WARNING'
    END,
    'Sample rows: ' || COUNT(*),
    CASE
        WHEN COUNT(*) >= 1 THEN 'INFO'
        ELSE 'WARNING'
    END
FROM optimization_history;

SELECT * FROM validation_results WHERE test_name LIKE 'Sample Data%';
\echo ''

-- ============================================================================
-- TEST 10: Verify JSONB Columns
-- ============================================================================

\echo 'Test 10: Verify JSONB Columns'
\echo '-------------------------------------------------------------------'

-- Check if JSONB columns can be queried
DO $$
DECLARE
    json_valid BOOLEAN;
BEGIN
    -- Test strategies.factor_weights
    SELECT COUNT(*) > 0 INTO json_valid
    FROM strategies
    WHERE factor_weights IS NOT NULL
      AND jsonb_typeof(factor_weights) = 'object';

    IF json_valid THEN
        INSERT INTO validation_results VALUES (
            'JSONB - strategies.factor_weights',
            '✅ PASS',
            'Valid JSONB data found',
            'INFO'
        );
    ELSE
        INSERT INTO validation_results VALUES (
            'JSONB - strategies.factor_weights',
            '⚠️ WARNING',
            'No valid JSONB data found',
            'WARNING'
        );
    END IF;

    -- Test optimization_history.optimal_weights
    SELECT COUNT(*) > 0 INTO json_valid
    FROM optimization_history
    WHERE optimal_weights IS NOT NULL
      AND jsonb_typeof(optimal_weights) = 'object';

    IF json_valid THEN
        INSERT INTO validation_results VALUES (
            'JSONB - optimization_history.optimal_weights',
            '✅ PASS',
            'Valid JSONB data found',
            'INFO'
        );
    ELSE
        INSERT INTO validation_results VALUES (
            'JSONB - optimization_history.optimal_weights',
            '⚠️ WARNING',
            'No valid JSONB data found',
            'WARNING'
        );
    END IF;
END $$;

SELECT * FROM validation_results WHERE test_name LIKE 'JSONB%';
\echo ''

-- ============================================================================
-- VALIDATION SUMMARY
-- ============================================================================

\echo '==================================================================='
\echo 'VALIDATION SUMMARY'
\echo '==================================================================='
\echo ''

-- Count results by severity
SELECT
    severity,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM validation_results) * 100, 1) || '%' as percentage
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
    total_count INTEGER;
BEGIN
    SELECT
        COUNT(*) FILTER (WHERE severity = 'CRITICAL'),
        COUNT(*) FILTER (WHERE severity = 'WARNING'),
        COUNT(*) FILTER (WHERE severity = 'INFO'),
        COUNT(*)
    INTO critical_count, warning_count, pass_count, total_count
    FROM validation_results;

    RAISE NOTICE '';
    RAISE NOTICE '===================================================================';

    IF critical_count = 0 AND warning_count = 0 THEN
        RAISE NOTICE '✅ VALIDATION PASSED - All % tests passed', pass_count;
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
        RAISE NOTICE 'Status: All Quant Platform tables validated successfully';
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE 'Total Tests Run: %', total_count;
    RAISE NOTICE '  ✅ Passed: % (%.1f%%)', pass_count, (pass_count::numeric / total_count * 100);
    RAISE NOTICE '  ⚠️ Warnings: % (%.1f%%)', warning_count, (warning_count::numeric / total_count * 100);
    RAISE NOTICE '  ❌ Critical: % (%.1f%%)', critical_count, (critical_count::numeric / total_count * 100);
    RAISE NOTICE '';
END $$;

-- Cleanup
DROP TABLE validation_results;

\echo 'Validation complete. Review any issues above.'
\echo ''
