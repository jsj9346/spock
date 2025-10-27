-- ========================================
-- Rollback Migration 006: Portfolio Allocation System
-- ========================================
-- Purpose: Remove portfolio allocation tables safely
-- Date: 2025-10-15
-- Version: 1.0
--
-- WARNING: This will delete all portfolio allocation data!
-- Backup your database before running this script.
--
-- Usage:
--   sqlite3 data/spock_local.db < migrations/006_rollback.sql

BEGIN TRANSACTION;

-- Drop indexes first
DROP INDEX IF EXISTS idx_allocation_drift_log_asset_class;
DROP INDEX IF EXISTS idx_allocation_drift_log_alert;
DROP INDEX IF EXISTS idx_allocation_drift_log_template;

DROP INDEX IF EXISTS idx_rebalancing_orders_side;
DROP INDEX IF EXISTS idx_rebalancing_orders_status;
DROP INDEX IF EXISTS idx_rebalancing_orders_ticker;
DROP INDEX IF EXISTS idx_rebalancing_orders_rebalance;

DROP INDEX IF EXISTS idx_rebalancing_history_date;
DROP INDEX IF EXISTS idx_rebalancing_history_status;
DROP INDEX IF EXISTS idx_rebalancing_history_template;

DROP INDEX IF EXISTS idx_asset_class_holdings_last_updated;
DROP INDEX IF EXISTS idx_asset_class_holdings_ticker;
DROP INDEX IF EXISTS idx_asset_class_holdings_asset_class;
DROP INDEX IF EXISTS idx_asset_class_holdings_template;

DROP INDEX IF EXISTS idx_portfolio_templates_active;
DROP INDEX IF EXISTS idx_portfolio_templates_name;

-- Drop tables in reverse order (respecting foreign key constraints)
DROP TABLE IF EXISTS allocation_drift_log;
DROP TABLE IF EXISTS rebalancing_orders;
DROP TABLE IF EXISTS rebalancing_history;
DROP TABLE IF EXISTS asset_class_holdings;
DROP TABLE IF EXISTS portfolio_templates;

-- Remove migration history record
DELETE FROM migration_history WHERE migration_version = '006';

COMMIT;

-- Verification
SELECT 'Rollback completed successfully.' AS status;
SELECT name FROM sqlite_master WHERE type='table'
AND (name LIKE '%portfolio%' OR name LIKE '%rebalancing%' OR name LIKE '%allocation%');
-- Should return no results if rollback was successful
