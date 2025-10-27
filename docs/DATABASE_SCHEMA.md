# DATABASE_SCHEMA.md

Complete PostgreSQL + TimescaleDB database schema for the Quant Investment Platform.

## Table of Contents

1. [Overview](#overview)
2. [Database Configuration](#database-configuration)
3. [Core Tables](#core-tables)
4. [Hypertables Setup](#hypertables-setup)
5. [Continuous Aggregates](#continuous-aggregates)
6. [Indexes and Constraints](#indexes-and-constraints)
7. [Compression Policies](#compression-policies)
8. [Backup and Retention](#backup-and-retention)
9. [Query Optimization](#query-optimization)
10. [Migration from SQLite](#migration-from-sqlite)

---

## Overview

### Architecture Decisions

**Why PostgreSQL + TimescaleDB?**

- **Unlimited Historical Data**: No 250-day retention limit (vs SQLite)
- **Time-Series Optimization**: Native support for time-series queries
- **Compression**: 20:1 compression ratio for historical data
- **Continuous Aggregates**: Pre-computed views for fast analysis
- **Scalability**: Handle millions of OHLCV records efficiently
- **Advanced Features**: Window functions, CTEs, parallel queries

**Database Stack**:
- PostgreSQL 15+
- TimescaleDB 2.11+
- pg_stat_statements (query monitoring)
- pgcrypto (credential encryption)

### Key Features

```yaml
Hypertables:
  - ohlcv_data: Partitioned by date (1-month chunks)
  - factor_scores: Partitioned by calculation_date (1-month chunks)
  - backtest_results: Partitioned by simulation_date (3-month chunks)

Continuous Aggregates:
  - ohlcv_daily_summary: Pre-aggregated daily statistics
  - factor_monthly_performance: Rolling factor performance metrics
  - portfolio_daily_metrics: Portfolio performance tracking

Compression:
  - Compress data older than 90 days
  - 20:1 compression ratio for OHLCV data
  - Transparent decompression on query

Retention:
  - OHLCV data: Unlimited (compressed after 90 days)
  - Backtest results: 5 years
  - Logs: 1 year
```

---

## Database Configuration

### 1.1 PostgreSQL Installation

```bash
# macOS
brew install postgresql@15 timescaledb

# Ubuntu/Debian
sudo apt-get install postgresql-15 postgresql-15-timescaledb

# Enable TimescaleDB
echo "shared_preload_libraries = 'timescaledb'" | sudo tee -a /etc/postgresql/15/main/postgresql.conf
sudo systemctl restart postgresql
```

### 1.2 Database Initialization

```sql
-- database_init.sql

-- Create database
CREATE DATABASE quant_platform
  WITH ENCODING 'UTF8'
       LC_COLLATE = 'en_US.UTF-8'
       LC_CTYPE = 'en_US.UTF-8'
       TEMPLATE template0;

\c quant_platform

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Set timezone
SET timezone = 'Asia/Seoul';

-- Performance tuning
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET max_worker_processes = 8;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- Reload configuration
SELECT pg_reload_conf();
```

### 1.3 User and Permissions

```sql
-- Create application user
CREATE USER quant_user WITH PASSWORD 'secure_password_here';

-- Grant permissions
GRANT CONNECT ON DATABASE quant_platform TO quant_user;
GRANT USAGE ON SCHEMA public TO quant_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO quant_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO quant_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO quant_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO quant_user;
```

---

## Core Tables

### 2.1 Tickers Table

```sql
-- Ticker universe (all tradable stocks)
CREATE TABLE tickers (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    market VARCHAR(20),
    sector VARCHAR(50),
    industry VARCHAR(100),
    market_cap BIGINT,
    listed_date DATE,
    delisted_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,

    PRIMARY KEY (ticker, region)
);

CREATE INDEX idx_tickers_region ON tickers(region);
CREATE INDEX idx_tickers_sector ON tickers(sector);
CREATE INDEX idx_tickers_market_cap ON tickers(market_cap DESC);
CREATE INDEX idx_tickers_is_active ON tickers(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_tickers_metadata ON tickers USING GIN(metadata);

COMMENT ON TABLE tickers IS 'Ticker universe across all supported regions';
COMMENT ON COLUMN tickers.metadata IS 'Additional metadata as JSON (e.g., exchange, currency)';
```

### 2.2 OHLCV Data (Hypertable)

```sql
-- Price and volume data (hypertable for time-series optimization)
CREATE TABLE ohlcv_data (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    date DATE NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT 'daily',
    open NUMERIC(18, 4),
    high NUMERIC(18, 4),
    low NUMERIC(18, 4),
    close NUMERIC(18, 4),
    volume BIGINT,
    adjusted_close NUMERIC(18, 4),

    -- Technical indicators
    ma5 NUMERIC(18, 4),
    ma20 NUMERIC(18, 4),
    ma60 NUMERIC(18, 4),
    ma120 NUMERIC(18, 4),
    ma200 NUMERIC(18, 4),
    rsi NUMERIC(8, 4),
    macd NUMERIC(18, 4),
    macd_signal NUMERIC(18, 4),
    bb_upper NUMERIC(18, 4),
    bb_middle NUMERIC(18, 4),
    bb_lower NUMERIC(18, 4),
    atr NUMERIC(18, 4),

    last_updated TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT ohlcv_data_pkey PRIMARY KEY (ticker, region, date, timeframe)
);

-- Convert to hypertable (partitioned by date)
SELECT create_hypertable(
    'ohlcv_data',
    'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_ohlcv_ticker_region ON ohlcv_data(ticker, region, date DESC);
CREATE INDEX idx_ohlcv_region_date ON ohlcv_data(region, date DESC);
CREATE INDEX idx_ohlcv_date ON ohlcv_data(date DESC);

COMMENT ON TABLE ohlcv_data IS 'Historical OHLCV data with technical indicators (hypertable)';
```

### 2.3 Factor Scores (Hypertable)

```sql
-- Multi-factor analysis results
CREATE TABLE factor_scores (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    calculation_date DATE NOT NULL,

    -- Layer 1: Macro (25 points)
    market_regime_score NUMERIC(5, 2),
    volume_profile_score NUMERIC(5, 2),
    price_action_score NUMERIC(5, 2),
    layer1_total NUMERIC(5, 2),

    -- Layer 2: Structural (45 points)
    stage_analysis_score NUMERIC(5, 2),
    moving_average_score NUMERIC(5, 2),
    relative_strength_score NUMERIC(5, 2),
    layer2_total NUMERIC(5, 2),

    -- Layer 3: Micro (30 points)
    pattern_recognition_score NUMERIC(5, 2),
    volume_spike_score NUMERIC(5, 2),
    momentum_score NUMERIC(5, 2),
    layer3_total NUMERIC(5, 2),

    -- Overall
    total_score NUMERIC(5, 2),
    signal VARCHAR(10),  -- 'BUY', 'WATCH', 'AVOID'

    -- Individual factors (Value, Momentum, Quality, Low-Vol, Size)
    pe_ratio NUMERIC(10, 4),
    pb_ratio NUMERIC(10, 4),
    momentum_12m NUMERIC(10, 4),
    rsi_factor NUMERIC(10, 4),
    roe NUMERIC(10, 4),
    debt_equity NUMERIC(10, 4),
    volatility_factor NUMERIC(10, 4),
    market_cap_factor NUMERIC(10, 4),

    calculation_metadata JSONB,
    last_updated TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT factor_scores_pkey PRIMARY KEY (ticker, region, calculation_date)
);

-- Convert to hypertable
SELECT create_hypertable(
    'factor_scores',
    'calculation_date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_factor_ticker_date ON factor_scores(ticker, region, calculation_date DESC);
CREATE INDEX idx_factor_date_signal ON factor_scores(calculation_date DESC, signal);
CREATE INDEX idx_factor_total_score ON factor_scores(total_score DESC) WHERE signal = 'BUY';
CREATE INDEX idx_factor_metadata ON factor_scores USING GIN(calculation_metadata);

COMMENT ON TABLE factor_scores IS 'Multi-factor analysis scores and signals (hypertable)';
```

### 2.4 Backtests Table (Hypertable)

```sql
-- Backtesting results
CREATE TABLE backtest_results (
    backtest_id SERIAL,
    strategy_name VARCHAR(100) NOT NULL,
    region VARCHAR(5) NOT NULL,
    simulation_date TIMESTAMPTZ NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital NUMERIC(18, 2),
    final_capital NUMERIC(18, 2),
    total_return NUMERIC(10, 6),
    annual_return NUMERIC(10, 6),
    sharpe_ratio NUMERIC(10, 4),
    sortino_ratio NUMERIC(10, 4),
    max_drawdown NUMERIC(10, 6),
    win_rate NUMERIC(10, 6),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    avg_win NUMERIC(18, 4),
    avg_loss NUMERIC(18, 4),

    -- Configuration
    strategy_params JSONB,
    rebalance_frequency VARCHAR(20),
    transaction_cost_bps NUMERIC(6, 2),

    -- Trade log
    trades JSONB,

    last_updated TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT backtest_results_pkey PRIMARY KEY (backtest_id, simulation_date)
);

-- Convert to hypertable
SELECT create_hypertable(
    'backtest_results',
    'simulation_date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX idx_backtest_strategy ON backtest_results(strategy_name, region, simulation_date DESC);
CREATE INDEX idx_backtest_sharpe ON backtest_results(sharpe_ratio DESC);
CREATE INDEX idx_backtest_params ON backtest_results USING GIN(strategy_params);

COMMENT ON TABLE backtest_results IS 'Backtesting simulation results (hypertable)';
```

### 2.5 Portfolio Table

```sql
-- Current portfolio holdings
CREATE TABLE portfolio (
    portfolio_id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_buy_price NUMERIC(18, 4) NOT NULL,
    current_price NUMERIC(18, 4),
    unrealized_pnl NUMERIC(18, 4),
    unrealized_pnl_pct NUMERIC(10, 6),
    position_value NUMERIC(18, 2),
    weight NUMERIC(10, 6),

    -- Risk management
    stop_loss_price NUMERIC(18, 4),
    take_profit_price NUMERIC(18, 4),
    trailing_stop_distance NUMERIC(10, 6),

    -- Metadata
    entry_date DATE NOT NULL,
    entry_signal VARCHAR(50),
    last_rebalance_date DATE,
    notes TEXT,

    last_updated TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT portfolio_ticker_region_key UNIQUE (ticker, region)
);

CREATE INDEX idx_portfolio_region ON portfolio(region);
CREATE INDEX idx_portfolio_weight ON portfolio(weight DESC);
CREATE INDEX idx_portfolio_pnl ON portfolio(unrealized_pnl_pct DESC);

COMMENT ON TABLE portfolio IS 'Current portfolio holdings and positions';
```

### 2.6 Trades Table

```sql
-- Trade execution history
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(5) NOT NULL,
    trade_date DATE NOT NULL,
    trade_type VARCHAR(10) NOT NULL,  -- 'BUY', 'SELL'
    quantity INTEGER NOT NULL,
    price NUMERIC(18, 4) NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL,
    commission NUMERIC(18, 4),
    slippage_bps NUMERIC(6, 2),

    -- Strategy context
    strategy_name VARCHAR(100),
    signal_source VARCHAR(50),
    entry_reason TEXT,

    -- Performance tracking
    realized_pnl NUMERIC(18, 4),
    realized_pnl_pct NUMERIC(10, 6),
    hold_days INTEGER,

    -- Metadata
    order_id VARCHAR(50),
    execution_timestamp TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT,

    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trades_ticker_region ON trades(ticker, region, trade_date DESC);
CREATE INDEX idx_trades_date ON trades(trade_date DESC);
CREATE INDEX idx_trades_type ON trades(trade_type);
CREATE INDEX idx_trades_strategy ON trades(strategy_name);

COMMENT ON TABLE trades IS 'Trade execution history and performance tracking';
```

### 2.7 Portfolio Snapshots (Hypertable)

```sql
-- Daily portfolio snapshots for performance tracking
CREATE TABLE portfolio_snapshots (
    snapshot_date DATE NOT NULL,
    total_value NUMERIC(18, 2) NOT NULL,
    cash NUMERIC(18, 2) NOT NULL,
    invested_value NUMERIC(18, 2) NOT NULL,
    unrealized_pnl NUMERIC(18, 4),
    daily_return NUMERIC(10, 6),
    cumulative_return NUMERIC(10, 6),
    positions JSONB,
    sector_exposures JSONB,
    region_exposures JSONB,

    last_updated TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT portfolio_snapshots_pkey PRIMARY KEY (snapshot_date)
);

-- Convert to hypertable
SELECT create_hypertable(
    'portfolio_snapshots',
    'snapshot_date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

CREATE INDEX idx_portfolio_snapshots_date ON portfolio_snapshots(snapshot_date DESC);

COMMENT ON TABLE portfolio_snapshots IS 'Daily portfolio snapshots for performance analysis (hypertable)';
```

### 2.8 API Logs Table

```sql
-- KIS API call logs
CREATE TABLE api_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    api_endpoint VARCHAR(200) NOT NULL,
    region VARCHAR(5),
    request_params JSONB,
    response_status INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    success BOOLEAN,

    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_logs_timestamp ON api_logs(timestamp DESC);
CREATE INDEX idx_api_logs_endpoint ON api_logs(api_endpoint);
CREATE INDEX idx_api_logs_success ON api_logs(success) WHERE success = FALSE;

COMMENT ON TABLE api_logs IS 'KIS API call logs for monitoring and debugging';
```

### 2.9 System Logs Table

```sql
-- System event logs
CREATE TABLE system_logs (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    log_level VARCHAR(20) NOT NULL,  -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    module VARCHAR(100),
    message TEXT NOT NULL,
    exception_type VARCHAR(100),
    stack_trace TEXT,
    context JSONB,

    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_system_logs_timestamp ON system_logs(timestamp DESC);
CREATE INDEX idx_system_logs_level ON system_logs(log_level) WHERE log_level IN ('ERROR', 'CRITICAL');
CREATE INDEX idx_system_logs_module ON system_logs(module);

COMMENT ON TABLE system_logs IS 'System event logs for debugging and monitoring';
```

---

## Hypertables Setup

### 3.1 Compression Policies

```sql
-- Enable compression on hypertables (compress data older than 90 days)

-- OHLCV data compression
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker,region',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('ohlcv_data', INTERVAL '90 days');

-- Factor scores compression
ALTER TABLE factor_scores SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker,region',
    timescaledb.compress_orderby = 'calculation_date DESC'
);

SELECT add_compression_policy('factor_scores', INTERVAL '90 days');

-- Backtest results compression
ALTER TABLE backtest_results SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'strategy_name,region',
    timescaledb.compress_orderby = 'simulation_date DESC'
);

SELECT add_compression_policy('backtest_results', INTERVAL '180 days');

-- Portfolio snapshots compression
ALTER TABLE portfolio_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'snapshot_date DESC'
);

SELECT add_compression_policy('portfolio_snapshots', INTERVAL '180 days');
```

### 3.2 Retention Policies

```sql
-- Retention policies (automatic data deletion)

-- Backtest results: Keep 5 years
SELECT add_retention_policy('backtest_results', INTERVAL '5 years');

-- API logs: Keep 1 year
SELECT add_retention_policy('api_logs', INTERVAL '1 year', if_not_exists => TRUE);

-- System logs: Keep 1 year
SELECT add_retention_policy('system_logs', INTERVAL '1 year', if_not_exists => TRUE);

-- OHLCV data: No retention (keep forever)
-- Factor scores: No retention (keep forever)
-- Portfolio snapshots: No retention (keep forever)
```

---

## Continuous Aggregates

### 4.1 Daily OHLCV Summary

```sql
-- Pre-computed daily statistics for fast queries
CREATE MATERIALIZED VIEW ohlcv_daily_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', date) AS day,
    region,
    COUNT(DISTINCT ticker) AS n_tickers,
    AVG(close) AS avg_close,
    AVG(volume) AS avg_volume,
    SUM(volume) AS total_volume,
    AVG(rsi) AS avg_rsi,
    AVG(atr) AS avg_atr
FROM ohlcv_data
WHERE timeframe = 'daily'
GROUP BY day, region
WITH NO DATA;

-- Refresh policy (refresh every 1 hour)
SELECT add_continuous_aggregate_policy('ohlcv_daily_summary',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

### 4.2 Factor Monthly Performance

```sql
-- Rolling factor performance metrics
CREATE MATERIALIZED VIEW factor_monthly_performance
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', calculation_date) AS month,
    region,
    signal,
    COUNT(*) AS n_stocks,
    AVG(total_score) AS avg_score,
    AVG(pe_ratio) AS avg_pe,
    AVG(momentum_12m) AS avg_momentum,
    AVG(roe) AS avg_roe,
    AVG(volatility_factor) AS avg_volatility
FROM factor_scores
GROUP BY month, region, signal
WITH NO DATA;

-- Refresh policy
SELECT add_continuous_aggregate_policy('factor_monthly_performance',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

### 4.3 Portfolio Daily Metrics

```sql
-- Daily portfolio performance tracking
CREATE MATERIALIZED VIEW portfolio_daily_metrics
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', snapshot_date) AS day,
    total_value,
    cash,
    invested_value,
    unrealized_pnl,
    daily_return,
    cumulative_return,
    AVG(total_value) OVER (ORDER BY snapshot_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma30_value,
    AVG(daily_return) OVER (ORDER BY snapshot_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma30_return,
    STDDEV(daily_return) OVER (ORDER BY snapshot_date ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS volatility_60d
FROM portfolio_snapshots
WITH NO DATA;

-- Refresh policy
SELECT add_continuous_aggregate_policy('portfolio_daily_metrics',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

---

## Indexes and Constraints

### 5.1 Foreign Key Constraints

```sql
-- Add foreign key constraints for referential integrity

-- Portfolio → Tickers
ALTER TABLE portfolio
ADD CONSTRAINT fk_portfolio_ticker
FOREIGN KEY (ticker, region)
REFERENCES tickers(ticker, region)
ON DELETE CASCADE;

-- Trades → Tickers
ALTER TABLE trades
ADD CONSTRAINT fk_trades_ticker
FOREIGN KEY (ticker, region)
REFERENCES tickers(ticker, region)
ON DELETE CASCADE;

-- Factor scores → Tickers
ALTER TABLE factor_scores
ADD CONSTRAINT fk_factor_scores_ticker
FOREIGN KEY (ticker, region)
REFERENCES tickers(ticker, region)
ON DELETE CASCADE;
```

### 5.2 Check Constraints

```sql
-- Data validation constraints

-- OHLCV data: high >= low, high >= open, high >= close
ALTER TABLE ohlcv_data
ADD CONSTRAINT chk_ohlcv_high_low CHECK (high >= low),
ADD CONSTRAINT chk_ohlcv_high_open CHECK (high >= open),
ADD CONSTRAINT chk_ohlcv_high_close CHECK (high >= close),
ADD CONSTRAINT chk_ohlcv_low_open CHECK (low <= open),
ADD CONSTRAINT chk_ohlcv_low_close CHECK (low <= close),
ADD CONSTRAINT chk_ohlcv_volume CHECK (volume >= 0);

-- Factor scores: total_score = layer1 + layer2 + layer3
ALTER TABLE factor_scores
ADD CONSTRAINT chk_factor_total_score
CHECK (ABS(total_score - (layer1_total + layer2_total + layer3_total)) < 0.01);

-- Portfolio: quantity > 0
ALTER TABLE portfolio
ADD CONSTRAINT chk_portfolio_quantity CHECK (quantity > 0);

-- Trades: quantity > 0, price > 0
ALTER TABLE trades
ADD CONSTRAINT chk_trades_quantity CHECK (quantity > 0),
ADD CONSTRAINT chk_trades_price CHECK (price > 0);
```

### 5.3 Partial Indexes

```sql
-- Partial indexes for common query patterns

-- Active tickers only
CREATE INDEX idx_tickers_active_by_sector
ON tickers(sector, market_cap DESC)
WHERE is_active = TRUE;

-- BUY signals only
CREATE INDEX idx_factor_buy_signals
ON factor_scores(calculation_date DESC, total_score DESC)
WHERE signal = 'BUY';

-- Open positions only
CREATE INDEX idx_portfolio_open_positions
ON portfolio(ticker, region, weight DESC)
WHERE quantity > 0;

-- Failed API calls only
CREATE INDEX idx_api_logs_failures
ON api_logs(timestamp DESC, api_endpoint)
WHERE success = FALSE;

-- ERROR/CRITICAL logs only
CREATE INDEX idx_system_logs_errors
ON system_logs(timestamp DESC, module)
WHERE log_level IN ('ERROR', 'CRITICAL');
```

---

## Compression Policies

### 6.1 Compression Statistics

```sql
-- View compression statistics
SELECT
    hypertable_name,
    total_chunks,
    number_compressed_chunks,
    ROUND(100.0 * number_compressed_chunks / NULLIF(total_chunks, 0), 2) AS compression_pct,
    pg_size_pretty(before_compression_total_bytes) AS uncompressed_size,
    pg_size_pretty(after_compression_total_bytes) AS compressed_size,
    ROUND(before_compression_total_bytes::NUMERIC / NULLIF(after_compression_total_bytes, 0), 2) AS compression_ratio
FROM timescaledb_information.compression_settings
JOIN timescaledb_information.chunks ON hypertable_name = hypertable_schema || '.' || hypertable_name
GROUP BY hypertable_name, total_chunks, number_compressed_chunks,
         before_compression_total_bytes, after_compression_total_bytes;
```

### 6.2 Manual Compression

```sql
-- Manually compress specific chunks

-- Compress OHLCV data older than 90 days
SELECT compress_chunk(chunk_schema || '.' || chunk_name)
FROM timescaledb_information.chunks
WHERE hypertable_name = 'ohlcv_data'
  AND range_end < NOW() - INTERVAL '90 days'
  AND NOT is_compressed;

-- Decompress recent data for updates
SELECT decompress_chunk(chunk_schema || '.' || chunk_name)
FROM timescaledb_information.chunks
WHERE hypertable_name = 'ohlcv_data'
  AND range_end >= NOW() - INTERVAL '7 days'
  AND is_compressed;
```

---

## Backup and Retention

### 7.1 Automated Backup Script

```bash
#!/bin/bash
# backup_database.sh - Automated PostgreSQL backup

DB_NAME="quant_platform"
DB_USER="quant_user"
BACKUP_DIR="/var/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U $DB_USER -h localhost -Fc $DB_NAME | gzip > $BACKUP_FILE

# Delete backups older than 30 days
find $BACKUP_DIR -name "${DB_NAME}_*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
```

### 7.2 Point-in-Time Recovery

```sql
-- Enable continuous archiving (WAL archiving)
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'test ! -f /var/lib/postgresql/archive/%f && cp %p /var/lib/postgresql/archive/%f';
ALTER SYSTEM SET archive_timeout = '1h';

-- Restart PostgreSQL to apply changes
SELECT pg_reload_conf();
```

### 7.3 Restore from Backup

```bash
#!/bin/bash
# restore_database.sh - Restore from backup

BACKUP_FILE="/var/backups/postgresql/quant_platform_20250115_120000.sql.gz"
DB_NAME="quant_platform"
DB_USER="quant_user"

# Drop existing database
dropdb -U $DB_USER $DB_NAME

# Create new database
createdb -U $DB_USER $DB_NAME

# Restore from backup
gunzip -c $BACKUP_FILE | psql -U $DB_USER -d $DB_NAME

echo "Database restored from: $BACKUP_FILE"
```

---

## Query Optimization

### 8.1 Common Query Patterns

```sql
-- 1. Get latest OHLCV data for a ticker
EXPLAIN ANALYZE
SELECT *
FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR' AND timeframe = 'daily'
ORDER BY date DESC
LIMIT 250;

-- Optimization: Index on (ticker, region, date DESC)
-- Expected: Index scan, <10ms

-- 2. Find top BUY signals by total_score
EXPLAIN ANALYZE
SELECT ticker, region, total_score, signal
FROM factor_scores
WHERE calculation_date = CURRENT_DATE
  AND signal = 'BUY'
ORDER BY total_score DESC
LIMIT 50;

-- Optimization: Partial index on (calculation_date, total_score) WHERE signal = 'BUY'
-- Expected: Index scan, <50ms

-- 3. Portfolio performance over time
EXPLAIN ANALYZE
SELECT
    snapshot_date,
    total_value,
    daily_return,
    cumulative_return,
    AVG(daily_return) OVER (ORDER BY snapshot_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma30_return
FROM portfolio_snapshots
WHERE snapshot_date >= CURRENT_DATE - INTERVAL '1 year'
ORDER BY snapshot_date;

-- Optimization: Use continuous aggregate (portfolio_daily_metrics)
-- Expected: Sequential scan on aggregate, <100ms

-- 4. Sector exposure analysis
EXPLAIN ANALYZE
SELECT
    t.sector,
    COUNT(*) AS n_stocks,
    SUM(p.position_value) AS total_value,
    SUM(p.weight) AS total_weight,
    AVG(p.unrealized_pnl_pct) AS avg_pnl_pct
FROM portfolio p
JOIN tickers t ON p.ticker = t.ticker AND p.region = t.region
WHERE p.quantity > 0
GROUP BY t.sector
ORDER BY total_value DESC;

-- Optimization: Index on tickers(sector), portfolio(weight DESC)
-- Expected: Hash join, <50ms
```

### 8.2 Query Performance Monitoring

```sql
-- View slow queries (pg_stat_statements)
SELECT
    query,
    calls,
    ROUND(total_exec_time::NUMERIC / 1000, 2) AS total_time_sec,
    ROUND(mean_exec_time::NUMERIC, 2) AS mean_time_ms,
    ROUND(stddev_exec_time::NUMERIC, 2) AS stddev_time_ms,
    ROUND(100.0 * shared_blks_hit / NULLIF(shared_blks_hit + shared_blks_read, 0), 2) AS cache_hit_pct
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 20;

-- Reset statistics
SELECT pg_stat_statements_reset();
```

### 8.3 Index Usage Analysis

```sql
-- View index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Identify unused indexes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelid NOT IN (
      SELECT conindid FROM pg_constraint WHERE contype IN ('p', 'u')
  )
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

## Migration from SQLite

### 9.1 Data Migration Script

```python
# migrate_sqlite_to_postgres.py

import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from tqdm import tqdm
import pandas as pd

# Connection parameters
SQLITE_DB = "data/spock_local.db"
PG_HOST = "localhost"
PG_DB = "quant_platform"
PG_USER = "quant_user"
PG_PASSWORD = "secure_password_here"

def migrate_tickers():
    """Migrate tickers table."""
    print("Migrating tickers...")

    # Read from SQLite
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    df = pd.read_sql_query("SELECT * FROM tickers", sqlite_conn)
    sqlite_conn.close()

    # Write to PostgreSQL
    pg_conn = psycopg2.connect(
        host=PG_HOST, database=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    cursor = pg_conn.cursor()

    insert_query = """
        INSERT INTO tickers (
            ticker, region, market, sector, industry, market_cap,
            listed_date, delisted_date, is_active, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region) DO UPDATE SET
            market = EXCLUDED.market,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            market_cap = EXCLUDED.market_cap,
            last_updated = NOW()
    """

    data = [tuple(row) for row in df.values]
    execute_batch(cursor, insert_query, data, page_size=1000)

    pg_conn.commit()
    cursor.close()
    pg_conn.close()

    print(f"Migrated {len(df)} tickers")

def migrate_ohlcv_data():
    """Migrate OHLCV data."""
    print("Migrating OHLCV data...")

    sqlite_conn = sqlite3.connect(SQLITE_DB)
    cursor = sqlite_conn.cursor()

    # Get total row count
    total_rows = cursor.execute("SELECT COUNT(*) FROM ohlcv_data").fetchone()[0]

    pg_conn = psycopg2.connect(
        host=PG_HOST, database=PG_DB, user=PG_USER, password=PG_PASSWORD
    )
    pg_cursor = pg_conn.cursor()

    insert_query = """
        INSERT INTO ohlcv_data (
            ticker, region, date, timeframe, open, high, low, close, volume,
            adjusted_close, ma5, ma20, ma60, ma120, ma200, rsi, macd, macd_signal,
            bb_upper, bb_middle, bb_lower, atr
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, timeframe) DO NOTHING
    """

    # Batch migration
    batch_size = 10000
    offset = 0

    with tqdm(total=total_rows, desc="OHLCV data") as pbar:
        while True:
            df = pd.read_sql_query(
                f"SELECT * FROM ohlcv_data LIMIT {batch_size} OFFSET {offset}",
                sqlite_conn
            )

            if len(df) == 0:
                break

            data = [tuple(row) for row in df.values]
            execute_batch(pg_cursor, insert_query, data, page_size=1000)
            pg_conn.commit()

            offset += batch_size
            pbar.update(len(df))

    sqlite_conn.close()
    pg_cursor.close()
    pg_conn.close()

    print(f"Migrated {total_rows} OHLCV records")

def migrate_all():
    """Run full migration."""
    migrate_tickers()
    migrate_ohlcv_data()
    # Add more migration functions as needed
    print("Migration completed!")

if __name__ == "__main__":
    migrate_all()
```

### 9.2 Post-Migration Validation

```sql
-- Validate migrated data

-- 1. Row count comparison
SELECT 'tickers' AS table_name, COUNT(*) AS row_count FROM tickers
UNION ALL
SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL
SELECT 'factor_scores', COUNT(*) FROM factor_scores
UNION ALL
SELECT 'portfolio', COUNT(*) FROM portfolio
UNION ALL
SELECT 'trades', COUNT(*) FROM trades;

-- 2. Data integrity checks
SELECT
    'OHLCV NULL regions' AS check_name,
    COUNT(*) AS error_count
FROM ohlcv_data
WHERE region IS NULL

UNION ALL

SELECT
    'OHLCV invalid prices',
    COUNT(*)
FROM ohlcv_data
WHERE high < low OR open < 0 OR close < 0

UNION ALL

SELECT
    'Factor scores out of range',
    COUNT(*)
FROM factor_scores
WHERE total_score < 0 OR total_score > 100

UNION ALL

SELECT
    'Portfolio negative quantities',
    COUNT(*)
FROM portfolio
WHERE quantity < 0;

-- 3. Date range validation
SELECT
    'OHLCV data' AS table_name,
    MIN(date) AS min_date,
    MAX(date) AS max_date,
    COUNT(DISTINCT ticker) AS n_tickers
FROM ohlcv_data;
```

---

## Summary

### Database Design Highlights

1. **TimescaleDB Hypertables**:
   - `ohlcv_data`: 1-month chunks, compressed after 90 days
   - `factor_scores`: 1-month chunks, compressed after 90 days
   - `backtest_results`: 3-month chunks, compressed after 180 days
   - `portfolio_snapshots`: 3-month chunks, compressed after 180 days

2. **Continuous Aggregates**:
   - `ohlcv_daily_summary`: Pre-computed daily market statistics
   - `factor_monthly_performance`: Rolling factor performance metrics
   - `portfolio_daily_metrics`: Daily portfolio performance tracking

3. **Compression & Retention**:
   - 20:1 compression ratio for historical data
   - Unlimited OHLCV storage (no 250-day limit)
   - 5-year retention for backtests
   - 1-year retention for logs

4. **Performance Optimization**:
   - Partitioned indexes for time-series queries
   - Partial indexes for common query patterns
   - Foreign key constraints for referential integrity
   - Check constraints for data validation

### Capacity Planning

| Data Type | Daily Volume | Monthly Storage | Annual Storage (Compressed) |
|-----------|-------------|-----------------|----------------------------|
| OHLCV Data (5 regions, 10K tickers) | 50K rows | 1.5M rows (~200MB) | ~1.2GB |
| Factor Scores (5 regions, 10K tickers) | 50K rows | 1.5M rows (~150MB) | ~900MB |
| Backtest Results | 100 simulations | 3K rows (~50MB) | ~300MB |
| Portfolio Snapshots | 1 snapshot/day | 30 rows (~1KB) | ~365KB |
| **Total** | | | **~2.5GB/year** |

### Integration with Quant Platform

This schema integrates with:
- Multi-factor analysis engine (`factor_scores` table)
- Backtesting framework (`backtest_results` table)
- Portfolio optimizer (reads `factor_scores`, writes `portfolio`)
- Risk management system (reads `portfolio`, `portfolio_snapshots`)
- Monitoring infrastructure (Prometheus metrics from `api_logs`, `system_logs`)

See `QUANT_PLATFORM_ARCHITECTURE.md` for complete system integration.

---

**All 5 Architecture Documents Complete!** 🎉

1. ✅ QUANT_PLATFORM_ARCHITECTURE.md (1,200+ lines)
2. ✅ FACTOR_LIBRARY_REFERENCE.md (1,100+ lines)
3. ✅ BACKTESTING_GUIDE.md (900+ lines)
4. ✅ OPTIMIZATION_COOKBOOK.md (1,300+ lines)
5. ✅ DATABASE_SCHEMA.md (1,100+ lines)
