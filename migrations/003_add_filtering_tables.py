"""
Migration 003: Add Multi-Market Filtering Tables

Adds filtering system tables to support multi-market stock filtering:
- filter_cache_stage0: Basic market filter cache with multi-market support
- filter_cache_stage1: Technical pre-screen filter cache
- filter_execution_log: Performance tracking and metrics

Changes from V1 (Korea-only):
- Added 'region' column to support multiple markets (KR, US, HK, CN, JP, VN)
- Added currency normalization fields (*_krw, *_local)
- Added exchange rate tracking
- Composite PRIMARY KEY (ticker, region)

Author: Spock Trading System
Date: 2025-10-04
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def upgrade(conn: sqlite3.Connection):
    """
    Apply migration: Create filtering system tables

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()

    logger.info("=== Migration 003: Creating filtering system tables ===")

    # ========================================
    # Table 1: filter_cache_stage0
    # ========================================
    logger.info("Creating filter_cache_stage0 table...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
            -- Composite Primary Key (multi-market support)
            ticker TEXT NOT NULL,
            region TEXT NOT NULL,  -- 'KR', 'US', 'HK', 'CN', 'JP', 'VN'

            -- Basic Info
            name TEXT NOT NULL,
            exchange TEXT,  -- 'KOSPI', 'NASDAQ', 'HKEX', 'SSE', 'TSE', 'HOSE', etc.

            -- Currency Normalization (KRW as base currency)
            market_cap_krw BIGINT,          -- Normalized to KRW for comparison
            trading_value_krw BIGINT,       -- Normalized to KRW
            current_price_krw INTEGER,      -- Normalized to KRW

            -- Original Values (Local Currency)
            market_cap_local REAL,          -- Original market cap in local currency
            trading_value_local REAL,       -- Original trading value
            current_price_local REAL,       -- Original current price
            currency TEXT NOT NULL,         -- 'KRW', 'USD', 'HKD', 'CNY', 'JPY', 'VND'

            -- Exchange Rate Metadata
            exchange_rate_to_krw REAL,      -- Conversion rate used (local → KRW)
            exchange_rate_date DATE,        -- Rate timestamp
            exchange_rate_source TEXT,      -- 'kis_api', 'bok', 'fixed', 'manual'

            -- Market-Specific Fields (nullable, used selectively)
            market_warn_code TEXT,          -- Korea: 관리종목 코드 ('00'=정상)
            is_stock_connect BOOLEAN,       -- China: Stock Connect 여부
            is_otc BOOLEAN,                 -- US: OTC market 여부
            is_delisting BOOLEAN,           -- All: 상장폐지 예정 여부

            -- Filter Result
            filter_date DATE NOT NULL,      -- Date when filter was applied
            stage0_passed BOOLEAN DEFAULT TRUE,  -- Filter pass/fail
            filter_reason TEXT,             -- If failed, reason (e.g., 'market_cap_too_low')

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Composite Primary Key
            PRIMARY KEY (ticker, region),

            -- Foreign Key to tickers table (if exists)
            FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
        )
    """)

    logger.info("✅ filter_cache_stage0 table created")

    # Create indexes for filter_cache_stage0
    logger.info("Creating indexes for filter_cache_stage0...")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage0_region_date
        ON filter_cache_stage0(region, filter_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage0_passed
        ON filter_cache_stage0(stage0_passed)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage0_market_cap_krw
        ON filter_cache_stage0(market_cap_krw DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage0_currency
        ON filter_cache_stage0(currency)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage0_filter_date
        ON filter_cache_stage0(filter_date DESC)
    """)

    logger.info("✅ Indexes created for filter_cache_stage0")

    # ========================================
    # Table 2: filter_cache_stage1
    # ========================================
    logger.info("Creating filter_cache_stage1 table...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
            -- Composite Primary Key
            ticker TEXT NOT NULL,
            region TEXT NOT NULL,

            -- Stage 1 Technical Data (30-day OHLCV window)
            -- All values are market-agnostic (normalized indicators)
            ma5 REAL,                       -- 5-day moving average
            ma20 REAL,                      -- 20-day moving average
            ma60 REAL,                      -- 60-day moving average
            rsi_14 REAL,                    -- 14-day RSI
            current_price_krw INTEGER,      -- Current price (always in KRW for comparison)
            week_52_high_krw INTEGER,       -- 52-week high (in KRW)
            volume_3d_avg BIGINT,           -- 3-day average volume
            volume_10d_avg BIGINT,          -- 10-day average volume

            -- Data Window Metadata
            filter_date DATE NOT NULL,      -- Date when filter was applied
            data_start_date DATE,           -- Start of 30-day window
            data_end_date DATE,             -- End of 30-day window

            -- Filter Result
            stage1_passed BOOLEAN DEFAULT TRUE,  -- Filter pass/fail
            filter_reason TEXT,             -- If failed, reason (e.g., 'MA20_not_above_MA60')

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (ticker, region),
            FOREIGN KEY (ticker, region) REFERENCES filter_cache_stage0(ticker, region) ON DELETE CASCADE
        )
    """)

    logger.info("✅ filter_cache_stage1 table created")

    # Create indexes for filter_cache_stage1
    logger.info("Creating indexes for filter_cache_stage1...")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage1_region_date
        ON filter_cache_stage1(region, filter_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage1_passed
        ON filter_cache_stage1(stage1_passed)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage1_ma_alignment
        ON filter_cache_stage1(ma5, ma20, ma60)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stage1_rsi
        ON filter_cache_stage1(rsi_14)
    """)

    logger.info("✅ Indexes created for filter_cache_stage1")

    # ========================================
    # Table 3: filter_execution_log
    # ========================================
    logger.info("Creating filter_execution_log table...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filter_execution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Execution Metadata
            execution_date DATE NOT NULL,   -- Date of filter execution
            region TEXT NOT NULL,           -- Market region ('KR', 'US', etc.)
            stage INTEGER NOT NULL,         -- Filter stage (0, 1, 2)

            -- Performance Metrics
            input_count INTEGER,            -- Number of input tickers
            output_count INTEGER,           -- Number of tickers passed filter
            reduction_rate REAL,            -- (input - output) / input

            execution_time_sec REAL,        -- Execution time in seconds
            api_calls INTEGER,              -- Number of API calls made
            error_count INTEGER,            -- Number of errors encountered

            -- Financial Metrics (KRW normalized)
            total_market_cap_krw BIGINT,    -- Sum of market caps (filtered stocks)
            avg_trading_value_krw BIGINT,   -- Average trading value

            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    logger.info("✅ filter_execution_log table created")

    # Create indexes for filter_execution_log
    logger.info("Creating indexes for filter_execution_log...")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_log_date_region
        ON filter_execution_log(execution_date DESC, region)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_log_stage
        ON filter_execution_log(stage, execution_date DESC)
    """)

    logger.info("✅ Indexes created for filter_execution_log")

    # Commit all changes
    conn.commit()

    logger.info("=== Migration 003 completed successfully ===")


def downgrade(conn: sqlite3.Connection):
    """
    Rollback migration: Drop filtering system tables

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()

    logger.info("=== Migration 003: Rolling back filtering system tables ===")

    # Drop tables in reverse order (foreign key dependencies)
    logger.info("Dropping filter_execution_log...")
    cursor.execute("DROP TABLE IF EXISTS filter_execution_log")

    logger.info("Dropping filter_cache_stage1...")
    cursor.execute("DROP TABLE IF EXISTS filter_cache_stage1")

    logger.info("Dropping filter_cache_stage0...")
    cursor.execute("DROP TABLE IF EXISTS filter_cache_stage0")

    conn.commit()

    logger.info("=== Migration 003 rollback completed ===")


# Standalone execution for testing
if __name__ == '__main__':
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='Migration 003: Filtering System Tables'
    )
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path'
    )
    parser.add_argument(
        '--downgrade',
        action='store_true',
        help='Rollback migration (drop tables)'
    )

    args = parser.parse_args()

    # Connect to database
    try:
        conn = sqlite3.connect(args.db_path)

        if args.downgrade:
            logger.info(f"Rolling back migration on {args.db_path}...")
            downgrade(conn)
            logger.info("✅ Rollback completed")
        else:
            logger.info(f"Applying migration to {args.db_path}...")
            upgrade(conn)
            logger.info("✅ Migration applied successfully")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
