-- ============================================================================
-- Quant Platform Database Schema
-- PostgreSQL 17 + TimescaleDB 2.22.1
-- Created: 2025-10-23
-- Version: 1.0.0
-- ============================================================================

-- Drop existing schema (use with caution in production)
-- DROP SCHEMA IF EXISTS public CASCADE;
-- CREATE SCHEMA public;

-- ============================================================================
-- SECTION 1: Core Reference Tables
-- ============================================================================

-- Tickers table (master ticker registry)
CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,  -- KR, US, CN, HK, JP, VN
    name VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    currency VARCHAR(3) DEFAULT 'USD',
    exchange VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    listed_date DATE,
    delisted_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_ticker_region UNIQUE (ticker, region)
);

CREATE INDEX idx_tickers_region ON tickers(region);
CREATE INDEX idx_tickers_sector ON tickers(sector);
CREATE INDEX idx_tickers_active ON tickers(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE tickers IS 'Master ticker registry with sector, industry, and market metadata';
COMMENT ON COLUMN tickers.region IS 'Market region: KR (Korea), US (United States), CN (China), HK (Hong Kong), JP (Japan), VN (Vietnam)';
COMMENT ON COLUMN tickers.market_cap IS 'Market capitalization in local currency';

-- ============================================================================
-- SECTION 2: Time-Series Tables (Hypertables)
-- ============================================================================

-- OHLCV data (primary time-series table)
CREATE TABLE IF NOT EXISTS ohlcv_data (
    id BIGSERIAL,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    timeframe VARCHAR(10) DEFAULT '1d',  -- 1d, 1h, 5m, etc.
    open DECIMAL(15, 4),
    high DECIMAL(15, 4),
    low DECIMAL(15, 4),
    close DECIMAL(15, 4),
    volume BIGINT,
    adj_close DECIMAL(15, 4),  -- Adjusted for splits and dividends
    split_factor DECIMAL(10, 4) DEFAULT 1.0,
    dividend DECIMAL(10, 4) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, region, date, timeframe)
);

COMMENT ON TABLE ohlcv_data IS 'OHLCV (Open, High, Low, Close, Volume) time-series data with split and dividend adjustments';
COMMENT ON COLUMN ohlcv_data.adj_close IS 'Close price adjusted for splits and dividends for accurate return calculations';
COMMENT ON COLUMN ohlcv_data.split_factor IS 'Stock split multiplier (e.g., 2.0 for 2-for-1 split)';
COMMENT ON COLUMN ohlcv_data.dividend IS 'Dividend amount per share on ex-dividend date';

-- Convert to hypertable (TimescaleDB)
SELECT create_hypertable(
    'ohlcv_data',
    'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression (10x space savings)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, timeframe',
    timescaledb.compress_orderby = 'date DESC'
);

-- Automatic compression policy (compress data older than 1 year)
SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days', if_not_exists => TRUE);

-- Indexes for optimal query performance
CREATE INDEX idx_ohlcv_ticker_region ON ohlcv_data(ticker, region, date DESC);
CREATE INDEX idx_ohlcv_date ON ohlcv_data(date DESC);
CREATE INDEX idx_ohlcv_region_date ON ohlcv_data(region, date DESC);

-- Factor scores (multi-factor analysis results)
CREATE TABLE IF NOT EXISTS factor_scores (
    id BIGSERIAL,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    factor_name VARCHAR(50) NOT NULL,  -- momentum, value, quality, low_vol, size
    score DECIMAL(10, 4),  -- 0-100 score
    percentile DECIMAL(5, 2),  -- 0-100 percentile within universe
    raw_value DECIMAL(15, 4),  -- Raw factor value (e.g., actual P/E ratio)
    zscore DECIMAL(10, 4),  -- Z-score for normalization
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, region, date, factor_name)
);

COMMENT ON TABLE factor_scores IS 'Daily factor scores for each ticker across multiple factors (value, momentum, quality, etc.)';
COMMENT ON COLUMN factor_scores.score IS 'Normalized 0-100 score where higher is better';
COMMENT ON COLUMN factor_scores.percentile IS 'Percentile rank within universe (0=worst, 100=best)';
COMMENT ON COLUMN factor_scores.raw_value IS 'Raw factor value before normalization (e.g., P/E ratio, ROE percentage)';

-- Convert to hypertable
SELECT create_hypertable(
    'factor_scores',
    'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE factor_scores SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, factor_name',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('factor_scores', INTERVAL '365 days', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_factor_scores_date ON factor_scores(date DESC);
CREATE INDEX idx_factor_scores_ticker ON factor_scores(ticker, region, date DESC);
CREATE INDEX idx_factor_scores_factor ON factor_scores(factor_name, date DESC);
CREATE INDEX idx_factor_scores_score ON factor_scores(score DESC) WHERE score IS NOT NULL;

-- Technical analysis indicators
CREATE TABLE IF NOT EXISTS technical_analysis (
    id BIGSERIAL,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    indicator_name VARCHAR(50) NOT NULL,  -- sma_20, rsi_14, macd, bbands, etc.
    value DECIMAL(15, 4),
    signal DECIMAL(15, 4),  -- For indicators with signal lines (e.g., MACD signal)
    upper_band DECIMAL(15, 4),  -- For Bollinger Bands, Donchian Channels
    lower_band DECIMAL(15, 4),
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, region, date, indicator_name)
);

COMMENT ON TABLE technical_analysis IS 'Technical indicators (SMA, RSI, MACD, Bollinger Bands, etc.)';

-- Convert to hypertable
SELECT create_hypertable(
    'technical_analysis',
    'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE technical_analysis SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, indicator_name',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('technical_analysis', INTERVAL '365 days', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_technical_ticker ON technical_analysis(ticker, region, date DESC);
CREATE INDEX idx_technical_indicator ON technical_analysis(indicator_name, date DESC);

-- ============================================================================
-- SECTION 3: Strategy and Backtest Tables
-- ============================================================================

-- Strategy definitions
CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    strategy_type VARCHAR(50),  -- multi_factor, technical, fundamental, hybrid
    factor_weights JSONB,  -- {"momentum": 0.4, "value": 0.3, "quality": 0.3}
    universe_filter JSONB,  -- {"region": ["KR", "US"], "min_market_cap": 100000000}
    rebalance_frequency VARCHAR(20) DEFAULT 'monthly',  -- daily, weekly, monthly, quarterly
    max_positions INTEGER DEFAULT 20,
    position_sizing_method VARCHAR(50) DEFAULT 'equal_weight',  -- equal_weight, risk_parity, kelly
    constraints JSONB,  -- {"max_position": 0.15, "max_sector": 0.4, "min_cash": 0.1}
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_strategies_active ON strategies(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_strategies_type ON strategies(strategy_type);

COMMENT ON TABLE strategies IS 'Strategy definitions with factor weights, universe filters, and constraints';
COMMENT ON COLUMN strategies.factor_weights IS 'JSON mapping of factor names to weights (must sum to 1.0)';
COMMENT ON COLUMN strategies.universe_filter IS 'JSON criteria for stock universe selection';
COMMENT ON COLUMN strategies.constraints IS 'JSON portfolio constraints (position limits, sector limits, turnover, etc.)';

-- Backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    backtest_name VARCHAR(100),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15, 2) DEFAULT 100000000,  -- 100M default
    final_capital DECIMAL(15, 2),
    total_return DECIMAL(10, 4),  -- Percentage
    annualized_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    calmar_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    volatility DECIMAL(10, 4),
    win_rate DECIMAL(5, 2),  -- Percentage
    num_trades INTEGER,
    avg_holding_period INTEGER,  -- Days
    total_commission DECIMAL(15, 2),
    total_slippage DECIMAL(15, 2),
    results_json JSONB,  -- Detailed trade history, daily returns, etc.
    benchmark_return DECIMAL(10, 4),  -- Benchmark comparison
    alpha DECIMAL(10, 4),  -- Alpha vs benchmark
    beta DECIMAL(10, 4),  -- Beta vs benchmark
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_results(strategy_id, start_date DESC);
CREATE INDEX idx_backtest_dates ON backtest_results(start_date, end_date);
CREATE INDEX idx_backtest_sharpe ON backtest_results(sharpe_ratio DESC) WHERE sharpe_ratio IS NOT NULL;

COMMENT ON TABLE backtest_results IS 'Backtest results with performance metrics, risk metrics, and detailed trade history';
COMMENT ON COLUMN backtest_results.results_json IS 'Detailed results: daily returns, trade log, portfolio weights over time, etc.';

-- Portfolio holdings (time-series of portfolio composition)
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id BIGSERIAL,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    shares INTEGER,
    weight DECIMAL(10, 6),  -- Portfolio weight (0-1)
    cost_basis DECIMAL(15, 4),  -- Average purchase price
    market_value DECIMAL(15, 4),  -- Current market value
    unrealized_pnl DECIMAL(15, 4),  -- Unrealized profit/loss
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (strategy_id, ticker, region, date)
);

COMMENT ON TABLE portfolio_holdings IS 'Daily snapshot of portfolio holdings for each strategy';

-- Convert to hypertable
SELECT create_hypertable(
    'portfolio_holdings',
    'date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

-- Enable compression
ALTER TABLE portfolio_holdings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'strategy_id, ticker, region',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('portfolio_holdings', INTERVAL '730 days', if_not_exists => TRUE);

-- Indexes
CREATE INDEX idx_holdings_strategy_date ON portfolio_holdings(strategy_id, date DESC);
CREATE INDEX idx_holdings_ticker ON portfolio_holdings(ticker, region, date DESC);

-- ============================================================================
-- SECTION 4: Portfolio Optimization Tables
-- ============================================================================

-- Optimization results
CREATE TABLE IF NOT EXISTS optimization_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    optimization_date DATE NOT NULL,
    optimization_method VARCHAR(50) NOT NULL,  -- mean_variance, risk_parity, black_litterman, kelly
    target_return DECIMAL(10, 4),
    target_risk DECIMAL(10, 4),
    weights JSONB NOT NULL,  -- {"005930": 0.15, "000660": 0.12, ...}
    expected_return DECIMAL(10, 4),
    expected_volatility DECIMAL(10, 4),
    expected_sharpe DECIMAL(10, 4),
    constraints_met BOOLEAN DEFAULT TRUE,
    optimization_params JSONB,  -- Algorithm-specific parameters
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_optimization_strategy ON optimization_results(strategy_id, optimization_date DESC);
CREATE INDEX idx_optimization_method ON optimization_results(optimization_method);

COMMENT ON TABLE optimization_results IS 'Portfolio optimization results with optimal weights and expected metrics';
COMMENT ON COLUMN optimization_results.weights IS 'JSON mapping of tickers to portfolio weights';

-- ============================================================================
-- SECTION 5: Risk Management Tables
-- ============================================================================

-- Risk metrics
CREATE TABLE IF NOT EXISTS risk_metrics (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    metric_type VARCHAR(50) NOT NULL,  -- var, cvar, beta, correlation, etc.
    metric_value DECIMAL(15, 4),
    confidence_level DECIMAL(5, 2),  -- For VaR/CVaR (e.g., 95.0, 99.0)
    time_horizon INTEGER,  -- Days (e.g., 1, 10, 20)
    details JSONB,  -- Additional metric-specific details
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_strategy_date_metric UNIQUE (strategy_id, date, metric_type, confidence_level, time_horizon)
);

CREATE INDEX idx_risk_strategy_date ON risk_metrics(strategy_id, date DESC);
CREATE INDEX idx_risk_metric_type ON risk_metrics(metric_type);

COMMENT ON TABLE risk_metrics IS 'Risk metrics (VaR, CVaR, beta, correlation, etc.) for portfolio monitoring';

-- Stress test scenarios
CREATE TABLE IF NOT EXISTS stress_test_results (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    scenario_name VARCHAR(100) NOT NULL,  -- 2008_crisis, 2020_covid, custom, etc.
    test_date DATE NOT NULL,
    portfolio_loss DECIMAL(10, 4),  -- Percentage loss under scenario
    scenario_params JSONB,  -- Scenario definition (shocks to factors, correlations, etc.)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stress_strategy ON stress_test_results(strategy_id, test_date DESC);
CREATE INDEX idx_stress_scenario ON stress_test_results(scenario_name);

COMMENT ON TABLE stress_test_results IS 'Stress test results showing portfolio loss under various crisis scenarios';

-- ============================================================================
-- SECTION 6: Factor Analysis Tables
-- ============================================================================

-- Factor performance (historical factor returns)
CREATE TABLE IF NOT EXISTS factor_performance (
    id SERIAL PRIMARY KEY,
    factor_name VARCHAR(50) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    quintile INTEGER,  -- 1 (lowest score) to 5 (highest score)
    num_stocks INTEGER,  -- Number of stocks in quintile
    avg_forward_return DECIMAL(10, 4),  -- Average return of stocks in quintile
    holding_period INTEGER DEFAULT 20,  -- Days
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_factor_date_quintile UNIQUE (factor_name, region, date, quintile, holding_period)
);

CREATE INDEX idx_factor_perf_factor ON factor_performance(factor_name, region, date DESC);
CREATE INDEX idx_factor_perf_quintile ON factor_performance(factor_name, quintile);

COMMENT ON TABLE factor_performance IS 'Historical factor performance using quintile analysis';
COMMENT ON COLUMN factor_performance.quintile IS 'Quintile bucket (1=lowest factor score, 5=highest factor score)';
COMMENT ON COLUMN factor_performance.avg_forward_return IS 'Average forward return of stocks in this quintile';

-- Factor correlation matrix
CREATE TABLE IF NOT EXISTS factor_correlations (
    id SERIAL PRIMARY KEY,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    factor1 VARCHAR(50) NOT NULL,
    factor2 VARCHAR(50) NOT NULL,
    correlation DECIMAL(10, 4),  -- -1.0 to 1.0
    num_observations INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_factor_pair UNIQUE (region, date, factor1, factor2)
);

CREATE INDEX idx_factor_corr_date ON factor_correlations(region, date DESC);
CREATE INDEX idx_factor_corr_factors ON factor_correlations(factor1, factor2);

COMMENT ON TABLE factor_correlations IS 'Factor correlation matrix for identifying redundant factors';

-- ============================================================================
-- SECTION 7: Continuous Aggregates (Materialized Views)
-- ============================================================================

-- Weekly OHLCV aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_weekly
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    region,
    time_bucket('1 week', date) AS week,
    first(open, date) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, date) AS close,
    last(adj_close, date) AS adj_close,
    sum(volume) AS volume,
    count(*) AS num_trading_days
FROM ohlcv_data
WHERE timeframe = '1d'
GROUP BY ticker, region, week;

COMMENT ON MATERIALIZED VIEW ohlcv_weekly IS 'Weekly OHLCV aggregates (continuous aggregate)';

-- Monthly OHLCV aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT
    ticker,
    region,
    time_bucket('1 month', date) AS month,
    first(open, date) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, date) AS close,
    last(adj_close, date) AS adj_close,
    sum(volume) AS volume,
    count(*) AS num_trading_days
FROM ohlcv_data
WHERE timeframe = '1d'
GROUP BY ticker, region, month;

COMMENT ON MATERIALIZED VIEW ohlcv_monthly IS 'Monthly OHLCV aggregates (continuous aggregate)';

-- Refresh policies (automatically update materialized views)
SELECT add_continuous_aggregate_policy('ohlcv_weekly',
    start_offset => INTERVAL '3 weeks',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy('ohlcv_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Factor performance summary (monthly IC and returns)
CREATE MATERIALIZED VIEW IF NOT EXISTS factor_stats_monthly
WITH (timescaledb.continuous) AS
SELECT
    factor_name,
    region,
    time_bucket('1 month', date) AS month,
    avg(score) AS avg_score,
    stddev(score) AS score_volatility,
    count(*) AS num_observations,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY score) AS median_score
FROM factor_scores
GROUP BY factor_name, region, month;

COMMENT ON MATERIALIZED VIEW factor_stats_monthly IS 'Monthly factor statistics (average score, volatility, median)';

SELECT add_continuous_aggregate_policy('factor_stats_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================================================
-- SECTION 8: Utility Functions
-- ============================================================================

-- Function to calculate daily returns
CREATE OR REPLACE FUNCTION calculate_daily_return(
    p_ticker VARCHAR,
    p_region VARCHAR,
    p_date DATE
) RETURNS DECIMAL(10, 6) AS $$
DECLARE
    v_current_price DECIMAL(15, 4);
    v_previous_price DECIMAL(15, 4);
    v_return DECIMAL(10, 6);
BEGIN
    -- Get current day close price
    SELECT adj_close INTO v_current_price
    FROM ohlcv_data
    WHERE ticker = p_ticker
      AND region = p_region
      AND date = p_date
      AND timeframe = '1d';

    -- Get previous trading day close price
    SELECT adj_close INTO v_previous_price
    FROM ohlcv_data
    WHERE ticker = p_ticker
      AND region = p_region
      AND date < p_date
      AND timeframe = '1d'
    ORDER BY date DESC
    LIMIT 1;

    -- Calculate return
    IF v_previous_price IS NULL OR v_previous_price = 0 THEN
        RETURN NULL;
    ELSE
        v_return := (v_current_price - v_previous_price) / v_previous_price;
        RETURN v_return;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_daily_return IS 'Calculate daily return for a ticker using adjusted close prices';

-- Function to get latest factor score
CREATE OR REPLACE FUNCTION get_latest_factor_score(
    p_ticker VARCHAR,
    p_region VARCHAR,
    p_factor_name VARCHAR,
    p_max_days_old INTEGER DEFAULT 7
) RETURNS TABLE(score DECIMAL(10, 4), percentile DECIMAL(5, 2), date DATE) AS $$
BEGIN
    RETURN QUERY
    SELECT fs.score, fs.percentile, fs.date
    FROM factor_scores fs
    WHERE fs.ticker = p_ticker
      AND fs.region = p_region
      AND fs.factor_name = p_factor_name
      AND fs.date >= CURRENT_DATE - INTERVAL '1 day' * p_max_days_old
    ORDER BY fs.date DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_latest_factor_score IS 'Get most recent factor score for a ticker (within max_days_old)';

-- ============================================================================
-- SECTION 9: Triggers for Automatic Timestamp Updates
-- ============================================================================

-- Create function for updating updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for tables with updated_at column
CREATE TRIGGER update_tickers_updated_at
    BEFORE UPDATE ON tickers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SECTION 10: Grants and Permissions
-- ============================================================================

-- Grant SELECT permissions to read-only user (for dashboard/API)
-- CREATE ROLE quant_readonly WITH LOGIN PASSWORD 'your_secure_password';
-- GRANT CONNECT ON DATABASE quant_platform TO quant_readonly;
-- GRANT USAGE ON SCHEMA public TO quant_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO quant_readonly;
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO quant_readonly;

-- Grant full permissions to application user
-- CREATE ROLE quant_app WITH LOGIN PASSWORD 'your_secure_password';
-- GRANT CONNECT ON DATABASE quant_platform TO quant_app;
-- GRANT USAGE ON SCHEMA public TO quant_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quant_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO quant_app;

-- ============================================================================
-- SECTION 11: Data Validation Constraints
-- ============================================================================

-- Ensure factor scores are in valid range
ALTER TABLE factor_scores
    ADD CONSTRAINT check_score_range CHECK (score >= 0 AND score <= 100),
    ADD CONSTRAINT check_percentile_range CHECK (percentile >= 0 AND percentile <= 100);

-- Ensure OHLCV data consistency
ALTER TABLE ohlcv_data
    ADD CONSTRAINT check_ohlcv_positive CHECK (
        open >= 0 AND high >= 0 AND low >= 0 AND close >= 0 AND volume >= 0
    ),
    ADD CONSTRAINT check_high_low CHECK (high >= low),
    ADD CONSTRAINT check_ohlc_range CHECK (
        high >= open AND high >= close AND low <= open AND low <= close
    );

-- Ensure portfolio weights sum to approximately 1.0 (handled in application)
-- This is informational only (cannot be enforced at row level)

-- ============================================================================
-- SCHEMA VERIFICATION QUERIES
-- ============================================================================

-- Verify hypertables
-- SELECT * FROM timescaledb_information.hypertables;

-- Verify continuous aggregates
-- SELECT * FROM timescaledb_information.continuous_aggregates;

-- Verify compression policies
-- SELECT * FROM timescaledb_information.compression_settings;

-- Check table sizes
-- SELECT
--     schemaname,
--     tablename,
--     pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
