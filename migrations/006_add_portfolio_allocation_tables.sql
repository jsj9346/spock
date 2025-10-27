-- ========================================
-- Migration 006: Portfolio Allocation System
-- ========================================
-- Purpose: Add tables for portfolio allocation templates and rebalancing
-- Author: Spock Development Team
-- Date: 2025-10-15
-- Version: 1.0
--
-- Tables Added:
--   1. portfolio_templates - Template definitions
--   2. asset_class_holdings - Current holdings by asset class
--   3. rebalancing_history - Historical rebalancing events
--   4. rebalancing_orders - Individual buy/sell orders
--   5. allocation_drift_log - Drift tracking over time
--
-- Usage:
--   sqlite3 data/spock_local.db < migrations/006_add_portfolio_allocation_tables.sql
--
-- Rollback:
--   sqlite3 data/spock_local.db < migrations/006_rollback.sql

-- Enable foreign key constraints (SQLite default is OFF)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ========================================
-- Table 1: Portfolio Templates
-- ========================================
CREATE TABLE IF NOT EXISTS portfolio_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL UNIQUE,           -- 'conservative', 'balanced', 'aggressive', 'custom'
    template_name_kr TEXT,                        -- '안정형', '균형형', '공격형', '사용자정의'
    risk_level TEXT NOT NULL,                     -- 'conservative', 'moderate', 'aggressive'
    description TEXT,

    -- Asset Allocation Targets (percentages must sum to 100)
    bonds_etf_target_percent REAL DEFAULT 0.0,
    commodities_etf_target_percent REAL DEFAULT 0.0,
    dividend_stocks_target_percent REAL DEFAULT 0.0,
    individual_stocks_target_percent REAL DEFAULT 0.0,
    cash_target_percent REAL DEFAULT 0.0,

    -- Rebalancing Strategy
    rebalancing_method TEXT DEFAULT 'threshold',  -- 'threshold', 'periodic', 'hybrid'
    drift_threshold_percent REAL DEFAULT 5.0,
    periodic_interval_days INTEGER DEFAULT 90,
    min_rebalance_interval_days INTEGER DEFAULT 30,
    max_trade_size_percent REAL DEFAULT 15.0,

    -- Position Limits (template-specific overrides)
    max_single_position_percent REAL DEFAULT 15.0,
    max_sector_exposure_percent REAL DEFAULT 40.0,
    min_cash_reserve_percent REAL DEFAULT 20.0,
    max_concurrent_positions INTEGER DEFAULT 10,

    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Validation Constraints
    CHECK (bonds_etf_target_percent >= 0 AND bonds_etf_target_percent <= 100),
    CHECK (commodities_etf_target_percent >= 0 AND commodities_etf_target_percent <= 100),
    CHECK (dividend_stocks_target_percent >= 0 AND dividend_stocks_target_percent <= 100),
    CHECK (individual_stocks_target_percent >= 0 AND individual_stocks_target_percent <= 100),
    CHECK (cash_target_percent >= 0 AND cash_target_percent <= 100),
    CHECK (risk_level IN ('conservative', 'moderate', 'aggressive')),
    CHECK (rebalancing_method IN ('threshold', 'periodic', 'hybrid'))
);

-- Index for fast template lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_templates_name
ON portfolio_templates(template_name);

CREATE INDEX IF NOT EXISTS idx_portfolio_templates_active
ON portfolio_templates(is_active);

-- ========================================
-- Table 2: Asset Class Holdings
-- ========================================
CREATE TABLE IF NOT EXISTS asset_class_holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    asset_class TEXT NOT NULL,                    -- 'bonds_etf', 'commodities_etf', 'dividend_stocks', 'individual_stocks', 'cash'

    -- Asset Details
    ticker TEXT NOT NULL,
    region TEXT DEFAULT 'KR',
    category TEXT,                                -- 'Fixed Income', 'Commodities', 'Dividend Stocks', 'Growth Stocks', 'Cash'

    -- Position Info
    quantity REAL NOT NULL,
    avg_entry_price REAL NOT NULL,
    current_price REAL NOT NULL,
    market_value REAL NOT NULL,

    -- Allocation Metrics
    target_allocation_percent REAL,               -- Target % for this asset class
    current_allocation_percent REAL,              -- Current % of portfolio
    drift_percent REAL,                           -- Deviation from target

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name),

    -- Validation Constraints
    CHECK (asset_class IN ('bonds_etf', 'commodities_etf', 'dividend_stocks', 'individual_stocks', 'cash')),
    CHECK (quantity >= 0),
    CHECK (avg_entry_price >= 0),
    CHECK (current_price >= 0),
    CHECK (market_value >= 0)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_asset_class_holdings_template
ON asset_class_holdings(template_name);

CREATE INDEX IF NOT EXISTS idx_asset_class_holdings_asset_class
ON asset_class_holdings(asset_class);

CREATE INDEX IF NOT EXISTS idx_asset_class_holdings_ticker
ON asset_class_holdings(ticker, region);

CREATE INDEX IF NOT EXISTS idx_asset_class_holdings_last_updated
ON asset_class_holdings(last_updated DESC);

-- ========================================
-- Table 3: Rebalancing History
-- ========================================
CREATE TABLE IF NOT EXISTS rebalancing_history (
    rebalance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,

    -- Rebalancing Trigger
    trigger_type TEXT NOT NULL,                   -- 'threshold', 'periodic', 'manual'
    trigger_reason TEXT,                          -- 'drift >5%', 'quarterly schedule', 'user initiated'
    max_drift_percent REAL,                       -- Maximum drift detected before rebalancing

    -- Pre-Rebalancing State
    pre_cash_krw REAL,
    pre_invested_krw REAL,
    pre_total_value_krw REAL,
    pre_allocation_json TEXT,                     -- JSON: {"bonds_etf": 15.0, "commodities_etf": 22.0, ...}

    -- Post-Rebalancing State
    post_cash_krw REAL,
    post_invested_krw REAL,
    post_total_value_krw REAL,
    post_allocation_json TEXT,

    -- Execution Metrics
    orders_generated INTEGER DEFAULT 0,
    orders_executed INTEGER DEFAULT 0,
    total_value_traded_krw REAL DEFAULT 0.0,
    transaction_costs_krw REAL DEFAULT 0.0,

    -- Execution Status
    status TEXT DEFAULT 'pending',                -- 'pending', 'in_progress', 'completed', 'failed', 'partial'
    error_message TEXT,

    execution_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_end_time TIMESTAMP,

    FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name),

    -- Validation Constraints
    CHECK (trigger_type IN ('threshold', 'periodic', 'manual')),
    CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'partial')),
    CHECK (orders_generated >= 0),
    CHECK (orders_executed >= 0),
    CHECK (orders_executed <= orders_generated)
);

-- Indexes for history queries
CREATE INDEX IF NOT EXISTS idx_rebalancing_history_template
ON rebalancing_history(template_name);

CREATE INDEX IF NOT EXISTS idx_rebalancing_history_status
ON rebalancing_history(status);

CREATE INDEX IF NOT EXISTS idx_rebalancing_history_date
ON rebalancing_history(execution_start_time DESC);

-- ========================================
-- Table 4: Rebalancing Orders
-- ========================================
CREATE TABLE IF NOT EXISTS rebalancing_orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rebalance_id INTEGER NOT NULL,

    -- Order Details
    ticker TEXT NOT NULL,
    region TEXT DEFAULT 'KR',
    asset_class TEXT NOT NULL,
    side TEXT NOT NULL,                           -- 'BUY', 'SELL'

    -- Order Quantities
    target_value_krw REAL NOT NULL,
    current_value_krw REAL NOT NULL,
    delta_value_krw REAL NOT NULL,               -- Amount to buy/sell (+ for buy, - for sell)
    quantity REAL,

    -- Execution
    order_price REAL,
    executed_price REAL,
    executed_quantity REAL,
    execution_fee_krw REAL DEFAULT 0.0,

    -- Status
    status TEXT DEFAULT 'pending',                -- 'pending', 'executed', 'failed', 'skipped'
    error_message TEXT,
    order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time TIMESTAMP,

    FOREIGN KEY (rebalance_id) REFERENCES rebalancing_history(rebalance_id),

    -- Validation Constraints
    CHECK (side IN ('BUY', 'SELL')),
    CHECK (status IN ('pending', 'executed', 'failed', 'skipped')),
    CHECK (asset_class IN ('bonds_etf', 'commodities_etf', 'dividend_stocks', 'individual_stocks', 'cash'))
);

-- Indexes for order queries
CREATE INDEX IF NOT EXISTS idx_rebalancing_orders_rebalance
ON rebalancing_orders(rebalance_id);

CREATE INDEX IF NOT EXISTS idx_rebalancing_orders_ticker
ON rebalancing_orders(ticker, region);

CREATE INDEX IF NOT EXISTS idx_rebalancing_orders_status
ON rebalancing_orders(status);

CREATE INDEX IF NOT EXISTS idx_rebalancing_orders_side
ON rebalancing_orders(side);

-- ========================================
-- Table 5: Allocation Drift Log
-- ========================================
CREATE TABLE IF NOT EXISTS allocation_drift_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,

    -- Drift Metrics
    asset_class TEXT NOT NULL,
    target_percent REAL NOT NULL,
    current_percent REAL NOT NULL,
    drift_percent REAL NOT NULL,                  -- current - target (can be negative)

    -- Alert Level
    alert_level TEXT DEFAULT 'green',             -- 'green', 'yellow', 'red'
    rebalancing_needed BOOLEAN DEFAULT 0,

    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (template_name) REFERENCES portfolio_templates(template_name),

    -- Validation Constraints
    CHECK (asset_class IN ('bonds_etf', 'commodities_etf', 'dividend_stocks', 'individual_stocks', 'cash')),
    CHECK (alert_level IN ('green', 'yellow', 'red'))
);

-- Indexes for drift tracking
CREATE INDEX IF NOT EXISTS idx_allocation_drift_log_template
ON allocation_drift_log(template_name, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_allocation_drift_log_alert
ON allocation_drift_log(alert_level, rebalancing_needed);

CREATE INDEX IF NOT EXISTS idx_allocation_drift_log_asset_class
ON allocation_drift_log(asset_class);

-- ========================================
-- Initial Data: Insert Default Templates
-- ========================================
INSERT OR IGNORE INTO portfolio_templates (
    template_name, template_name_kr, risk_level, description,
    bonds_etf_target_percent, commodities_etf_target_percent,
    dividend_stocks_target_percent, individual_stocks_target_percent, cash_target_percent,
    rebalancing_method, drift_threshold_percent, periodic_interval_days,
    min_rebalance_interval_days, max_trade_size_percent,
    max_single_position_percent, max_sector_exposure_percent,
    min_cash_reserve_percent, max_concurrent_positions
) VALUES
    -- Conservative Template
    ('conservative', '안정형', 'conservative', 'Low-risk portfolio focused on capital preservation',
     40.0, 20.0, 20.0, 10.0, 10.0,
     'threshold', 5.0, 90, 30, 10.0,
     10.0, 30.0, 10.0, 12),

    -- Balanced Template (Default)
    ('balanced', '균형형', 'moderate', 'Moderate-risk portfolio balancing growth and stability',
     20.0, 20.0, 20.0, 30.0, 10.0,
     'hybrid', 7.0, 60, 30, 15.0,
     15.0, 40.0, 10.0, 10),

    -- Aggressive Template
    ('aggressive', '공격형', 'aggressive', 'High-risk portfolio focused on capital growth',
     10.0, 10.0, 15.0, 55.0, 10.0,
     'threshold', 10.0, 90, 30, 20.0,
     20.0, 50.0, 10.0, 8),

    -- Custom Template
    ('custom', '사용자정의', 'moderate', 'User-defined allocation strategy',
     25.0, 15.0, 20.0, 30.0, 10.0,
     'periodic', 0.0, 90, 30, 15.0,
     15.0, 40.0, 10.0, 10);

-- ========================================
-- Migration Metadata
-- ========================================
CREATE TABLE IF NOT EXISTS migration_history (
    migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_version TEXT NOT NULL UNIQUE,
    migration_name TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO migration_history (migration_version, migration_name)
VALUES ('006', 'add_portfolio_allocation_tables');

COMMIT;

-- ========================================
-- Verification Queries
-- ========================================
-- Run these to verify migration success:
--
-- SELECT name FROM sqlite_master WHERE type='table'
-- AND name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%';
--
-- SELECT * FROM portfolio_templates;
--
-- SELECT COUNT(*) FROM portfolio_templates;  -- Should be 4
