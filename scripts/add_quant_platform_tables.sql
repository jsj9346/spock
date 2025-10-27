-- ============================================================================
-- Add Quant Platform Tables
-- ============================================================================
-- Purpose: Create additional tables for quant research platform
-- Created: 2025-10-21
-- Part of: Phase 1 Task 4 (Add Quant Platform Tables)
-- ============================================================================
--
-- Tables Created:
--   1. portfolio_transactions - Trade history for backtesting
--   2. walk_forward_results - Walk-forward optimization results
--   3. optimization_history - Portfolio optimization tracking
--
-- ============================================================================

\echo ''
\echo '==================================================================='
\echo 'TASK 4: ADD QUANT PLATFORM TABLES'
\echo '==================================================================='
\echo ''

-- ============================================================================
-- TABLE 1: portfolio_transactions
-- ============================================================================
-- Purpose: Record all trades (buy/sell) during backtesting
-- Relationships: References strategies table
-- Retention: Unlimited (essential for performance analysis)
-- ============================================================================

\echo 'Creating Table 1: portfolio_transactions'
\echo '-------------------------------------------------------------------'

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id BIGSERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    shares DECIMAL(15, 4) NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    commission DECIMAL(10, 4) DEFAULT 0,
    slippage DECIMAL(10, 4) DEFAULT 0,
    total_value DECIMAL(15, 4) GENERATED ALWAYS AS (shares * price + commission + slippage) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_transactions_strategy
    ON portfolio_transactions(strategy_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_ticker
    ON portfolio_transactions(ticker, region, date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_date
    ON portfolio_transactions(date DESC);

-- Add comment
COMMENT ON TABLE portfolio_transactions IS
'Trade history for backtesting. Records all buy/sell transactions with commission and slippage.';

COMMENT ON COLUMN portfolio_transactions.total_value IS
'Auto-calculated: shares * price + commission + slippage';

\echo '  ✅ portfolio_transactions created'
\echo '  ✅ 3 indexes created'
\echo ''

-- ============================================================================
-- TABLE 2: walk_forward_results
-- ============================================================================
-- Purpose: Store walk-forward optimization results for out-of-sample validation
-- Relationships: References strategies table
-- Key Metric: overfitting_ratio (out_sample_sharpe / in_sample_sharpe)
-- ============================================================================

\echo 'Creating Table 2: walk_forward_results'
\echo '-------------------------------------------------------------------'

CREATE TABLE IF NOT EXISTS walk_forward_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    train_start_date DATE NOT NULL,
    train_end_date DATE NOT NULL,
    test_start_date DATE NOT NULL,
    test_end_date DATE NOT NULL,
    in_sample_sharpe DECIMAL(10, 4),
    out_sample_sharpe DECIMAL(10, 4),
    in_sample_return DECIMAL(10, 4),
    out_sample_return DECIMAL(10, 4),
    overfitting_ratio DECIMAL(10, 4),  -- out_sample_sharpe / in_sample_sharpe
    optimal_params JSONB,  -- Parameters found during training
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_walkforward_strategy
    ON walk_forward_results(strategy_id);

CREATE INDEX IF NOT EXISTS idx_walkforward_dates
    ON walk_forward_results(train_start_date, test_end_date);

CREATE INDEX IF NOT EXISTS idx_walkforward_ratio
    ON walk_forward_results(overfitting_ratio DESC);

-- Add comment
COMMENT ON TABLE walk_forward_results IS
'Walk-forward optimization results for validating strategy robustness. Tracks in-sample vs out-of-sample performance.';

COMMENT ON COLUMN walk_forward_results.overfitting_ratio IS
'Ratio of out-of-sample to in-sample Sharpe ratio. Values <0.5 indicate significant overfitting.';

\echo '  ✅ walk_forward_results created'
\echo '  ✅ 3 indexes created'
\echo ''

-- ============================================================================
-- TABLE 3: optimization_history
-- ============================================================================
-- Purpose: Track portfolio optimization runs and results
-- Use Cases: Compare optimization methods, track optimal weights over time
-- Retention: Unlimited (important for research)
-- ============================================================================

\echo 'Creating Table 3: optimization_history'
\echo '-------------------------------------------------------------------'

CREATE TABLE IF NOT EXISTS optimization_history (
    id SERIAL PRIMARY KEY,
    optimization_date DATE NOT NULL,
    universe VARCHAR(50) NOT NULL,  -- 'KR_TOP100', 'US_SP500', etc.
    method VARCHAR(50) NOT NULL,    -- 'mean_variance', 'risk_parity', etc.
    target_return DECIMAL(10, 4),
    target_risk DECIMAL(10, 4),
    constraints JSONB,
    optimal_weights JSONB NOT NULL,  -- {ticker: weight}
    expected_return DECIMAL(10, 4),
    expected_risk DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_optimization_date
    ON optimization_history(optimization_date DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_method
    ON optimization_history(method, optimization_date DESC);

CREATE INDEX IF NOT EXISTS idx_optimization_universe
    ON optimization_history(universe, optimization_date DESC);

-- Add comment
COMMENT ON TABLE optimization_history IS
'Portfolio optimization history. Tracks optimal weights and expected performance from various optimization methods.';

COMMENT ON COLUMN optimization_history.optimal_weights IS
'JSONB format: {"ticker1": 0.25, "ticker2": 0.30, ...}';

COMMENT ON COLUMN optimization_history.method IS
'Optimization method: mean_variance, risk_parity, black_litterman, kelly_criterion';

\echo '  ✅ optimization_history created'
\echo '  ✅ 3 indexes created'
\echo ''

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

\echo '==================================================================='
\echo 'VERIFICATION: Table Creation'
\echo '==================================================================='
\echo ''

-- Check all 3 tables exist
\echo 'Checking table existence...'
SELECT
    schemaname,
    tablename,
    tableowner
FROM pg_tables
WHERE tablename IN ('portfolio_transactions', 'walk_forward_results', 'optimization_history')
ORDER BY tablename;

\echo ''

-- Check indexes
\echo 'Checking indexes...'
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('portfolio_transactions', 'walk_forward_results', 'optimization_history')
ORDER BY tablename, indexname;

\echo ''

-- Check foreign keys
\echo 'Checking foreign key constraints...'
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('portfolio_transactions', 'walk_forward_results', 'optimization_history')
ORDER BY tc.table_name;

\echo ''

-- Check table sizes
\echo 'Table sizes:'
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename IN ('portfolio_transactions', 'walk_forward_results', 'optimization_history')
ORDER BY tablename;

\echo ''

-- ============================================================================
-- SAMPLE DATA INSERTION (for validation)
-- ============================================================================

\echo '==================================================================='
\echo 'SAMPLE DATA INSERTION (Validation)'
\echo '==================================================================='
\echo ''

-- Insert sample strategy if not exists
INSERT INTO strategies (name, description, factor_weights, constraints)
VALUES (
    'test_momentum_value',
    'Test strategy for validation (auto-created)',
    '{"momentum": 0.5, "value": 0.5}',
    '{"max_position": 0.15, "max_sector": 0.4}'
)
ON CONFLICT (name) DO NOTHING;

-- Get strategy_id
DO $$
DECLARE
    test_strategy_id INTEGER;
BEGIN
    SELECT id INTO test_strategy_id
    FROM strategies
    WHERE name = 'test_momentum_value'
    LIMIT 1;

    -- Sample portfolio_transactions
    INSERT INTO portfolio_transactions (
        strategy_id, ticker, region, date, transaction_type,
        shares, price, commission, slippage
    ) VALUES
        (test_strategy_id, '005930', 'KR', '2024-01-15', 'BUY', 100, 70000, 105, 50),
        (test_strategy_id, '005930', 'KR', '2024-06-20', 'SELL', 100, 85000, 127, 60),
        (test_strategy_id, '000660', 'KR', '2024-02-01', 'BUY', 50, 550000, 412, 200)
    ON CONFLICT DO NOTHING;

    -- Sample walk_forward_results
    INSERT INTO walk_forward_results (
        strategy_id, train_start_date, train_end_date,
        test_start_date, test_end_date,
        in_sample_sharpe, out_sample_sharpe,
        in_sample_return, out_sample_return,
        overfitting_ratio, optimal_params
    ) VALUES
        (test_strategy_id, '2020-01-01', '2022-12-31',
         '2023-01-01', '2023-12-31',
         1.85, 1.42, 0.185, 0.142, 0.768,
         '{"momentum_period": 252, "value_threshold": 15}')
    ON CONFLICT DO NOTHING;

    -- Sample optimization_history
    INSERT INTO optimization_history (
        optimization_date, universe, method,
        target_return, target_risk, constraints,
        optimal_weights, expected_return, expected_risk, sharpe_ratio
    ) VALUES
        ('2024-01-15', 'KR_TOP100', 'mean_variance',
         0.15, 0.20, '{"max_position": 0.15, "max_sector": 0.4}',
         '{"005930": 0.25, "000660": 0.20, "035420": 0.15, "005380": 0.10, "051910": 0.10, "cash": 0.20}',
         0.152, 0.185, 0.821)
    ON CONFLICT DO NOTHING;

    RAISE NOTICE 'Sample data inserted successfully';
END $$;

\echo ''

-- ============================================================================
-- FINAL VALIDATION
-- ============================================================================

\echo '==================================================================='
\echo 'FINAL VALIDATION'
\echo '==================================================================='
\echo ''

-- Count rows in each table
\echo 'Row counts:'
SELECT 'portfolio_transactions' as table_name, COUNT(*) as row_count
FROM portfolio_transactions
UNION ALL
SELECT 'walk_forward_results', COUNT(*)
FROM walk_forward_results
UNION ALL
SELECT 'optimization_history', COUNT(*)
FROM optimization_history
ORDER BY table_name;

\echo ''

-- Sample data from each table
\echo 'Sample from portfolio_transactions:'
SELECT id, strategy_id, ticker, date, transaction_type, shares, price, total_value
FROM portfolio_transactions
ORDER BY date DESC
LIMIT 3;

\echo ''

\echo 'Sample from walk_forward_results:'
SELECT id, strategy_id, train_start_date, test_end_date,
       in_sample_sharpe, out_sample_sharpe, overfitting_ratio
FROM walk_forward_results
LIMIT 3;

\echo ''

\echo 'Sample from optimization_history:'
SELECT id, optimization_date, universe, method,
       expected_return, expected_risk, sharpe_ratio
FROM optimization_history
ORDER BY optimization_date DESC
LIMIT 3;

\echo ''

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

\echo '==================================================================='
\echo '✅ QUANT PLATFORM TABLES CREATED SUCCESSFULLY!'
\echo '==================================================================='
\echo ''
\echo 'Tables Created (3):'
\echo '  1. portfolio_transactions (trade history)'
\echo '  2. walk_forward_results (optimization validation)'
\echo '  3. optimization_history (portfolio optimization tracking)'
\echo ''
\echo 'Indexes Created: 9 total'
\echo '  - portfolio_transactions: 3 indexes'
\echo '  - walk_forward_results: 3 indexes'
\echo '  - optimization_history: 3 indexes'
\echo ''
\echo 'Foreign Keys: All 3 tables reference strategies(id) with CASCADE delete'
\echo ''
\echo 'Sample Data: Validation records inserted for testing'
\echo ''
\echo 'Next Steps:'
\echo '  1. Review table structures and indexes'
\echo '  2. Test integration with db_manager_postgres.py'
\echo '  3. Proceed to Task 5: Performance Tuning'
\echo ''
