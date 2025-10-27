#!/usr/bin/env python3
"""
Financial Statements Schema Initialization

Creates tables for Income Statement, Balance Sheet, and Cash Flow Statement
to support Value and Quality factor calculations.

Usage:
    python3 scripts/init_financial_statements_schema.py [--db-path path/to/db]

Tables Created:
- income_statements: Revenue, Operating Income, Net Income, EBITDA
- balance_sheets: Assets, Liabilities, Equity, Debt levels
- cash_flow_statements: CFO, CapEx, FCF, Cash position

Author: Spock Quant Platform - Phase 2
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import logging
import argparse
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# SQL Schema Definitions
INCOME_STATEMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,              -- NULL for annual, 1-4 for quarterly
    period_type TEXT NOT NULL,           -- 'ANNUAL', 'QUARTERLY'
    report_date TEXT NOT NULL,           -- YYYY-MM-DD

    -- Revenue
    revenue BIGINT,                      -- 매출액
    cost_of_revenue BIGINT,              -- 매출원가
    gross_profit BIGINT,                 -- 매출총이익

    -- Operating Items
    operating_expenses BIGINT,            -- 영업비용
    operating_income BIGINT,              -- 영업이익 (EBIT)

    -- Non-Operating Items
    interest_income BIGINT,               -- 이자수익
    interest_expense BIGINT,              -- 이자비용
    other_income BIGINT,                  -- 기타수익
    other_expense BIGINT,                 -- 기타비용

    -- Pre-Tax & Tax
    income_before_tax BIGINT,             -- 법인세차감전순이익
    income_tax_expense BIGINT,            -- 법인세비용

    -- Net Income
    net_income BIGINT,                    -- 당기순이익

    -- Advanced Metrics
    ebitda BIGINT,                        -- EBITDA
    depreciation_amortization BIGINT,     -- 감가상각비

    -- Metadata
    data_source TEXT,                     -- 'DART', 'yfinance', 'manual'
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);
"""

BALANCE_SHEET_SCHEMA = """
CREATE TABLE IF NOT EXISTS balance_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    period_type TEXT NOT NULL,
    report_date TEXT NOT NULL,

    -- Assets
    current_assets BIGINT,                -- 유동자산
    cash_and_equivalents BIGINT,          -- 현금및현금성자산
    accounts_receivable BIGINT,           -- 매출채권
    inventory BIGINT,                     -- 재고자산

    non_current_assets BIGINT,            -- 비유동자산
    property_plant_equipment BIGINT,      -- 유형자산
    intangible_assets BIGINT,             -- 무형자산

    total_assets BIGINT,                  -- 자산총계

    -- Liabilities
    current_liabilities BIGINT,           -- 유동부채
    accounts_payable BIGINT,              -- 매입채무
    short_term_debt BIGINT,               -- 단기차입금

    non_current_liabilities BIGINT,       -- 비유동부채
    long_term_debt BIGINT,                -- 장기차입금

    total_liabilities BIGINT,             -- 부채총계

    -- Equity
    shareholders_equity BIGINT,           -- 자본총계
    common_stock BIGINT,                  -- 자본금
    retained_earnings BIGINT,             -- 이익잉여금

    -- Calculated Metrics
    total_debt BIGINT,                    -- 총부채
    net_debt BIGINT,                      -- 순부채
    working_capital BIGINT,               -- 운전자본

    -- Metadata
    data_source TEXT,
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);
"""

CASH_FLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS cash_flow_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER,
    period_type TEXT NOT NULL,
    report_date TEXT NOT NULL,

    -- Operating Activities
    operating_cash_flow BIGINT,           -- 영업활동현금흐름
    net_income BIGINT,                    -- 당기순이익
    depreciation_amortization BIGINT,     -- 감가상각비
    changes_in_working_capital BIGINT,    -- 운전자본변동

    -- Investing Activities
    investing_cash_flow BIGINT,           -- 투자활동현금흐름
    capital_expenditures BIGINT,          -- 자본적지출 (CapEx)
    investments BIGINT,                   -- 투자자산취득/처분

    -- Financing Activities
    financing_cash_flow BIGINT,           -- 재무활동현금흐름
    dividends_paid BIGINT,                -- 배당금지급
    debt_issued BIGINT,                   -- 차입금증가
    debt_repaid BIGINT,                   -- 차입금상환

    -- Cash Position
    net_change_in_cash BIGINT,            -- 현금증감
    beginning_cash_balance BIGINT,        -- 기초현금
    ending_cash_balance BIGINT,           -- 기말현금

    -- Calculated Metrics
    free_cash_flow BIGINT,                -- FCF = CFO - CapEx

    -- Metadata
    data_source TEXT,
    created_at TEXT NOT NULL,

    UNIQUE(ticker, fiscal_year, period_type, fiscal_quarter),
    FOREIGN KEY (ticker) REFERENCES tickers(ticker)
);
"""

# Index Definitions
INDEXES = [
    # Income Statement Indexes
    "CREATE INDEX IF NOT EXISTS idx_income_ticker_year ON income_statements(ticker, fiscal_year);",
    "CREATE INDEX IF NOT EXISTS idx_income_period ON income_statements(period_type);",
    "CREATE INDEX IF NOT EXISTS idx_income_report_date ON income_statements(report_date);",

    # Balance Sheet Indexes
    "CREATE INDEX IF NOT EXISTS idx_balance_ticker_year ON balance_sheets(ticker, fiscal_year);",
    "CREATE INDEX IF NOT EXISTS idx_balance_period ON balance_sheets(period_type);",
    "CREATE INDEX IF NOT EXISTS idx_balance_report_date ON balance_sheets(report_date);",

    # Cash Flow Statement Indexes
    "CREATE INDEX IF NOT EXISTS idx_cashflow_ticker_year ON cash_flow_statements(ticker, fiscal_year);",
    "CREATE INDEX IF NOT EXISTS idx_cashflow_period ON cash_flow_statements(period_type);",
    "CREATE INDEX IF NOT EXISTS idx_cashflow_report_date ON cash_flow_statements(report_date);",
]


def create_financial_statements_schema(db_path: str = './data/spock_local.db'):
    """
    Create financial statements tables and indexes

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (success: bool, message: str)
    """
    logger.info(f"📊 Initializing financial statements schema: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables
        logger.info("Creating income_statements table...")
        cursor.execute(INCOME_STATEMENT_SCHEMA)

        logger.info("Creating balance_sheets table...")
        cursor.execute(BALANCE_SHEET_SCHEMA)

        logger.info("Creating cash_flow_statements table...")
        cursor.execute(CASH_FLOW_SCHEMA)

        # Create indexes
        logger.info("Creating indexes...")
        for index_sql in INDEXES:
            cursor.execute(index_sql)

        conn.commit()

        # Verify tables created
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('income_statements', 'balance_sheets', 'cash_flow_statements')
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        # Get row counts
        counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

        conn.close()

        logger.info("✅ Financial statements schema initialized successfully")
        logger.info(f"📊 Tables created: {', '.join(tables)}")
        logger.info(f"📈 Row counts: {counts}")

        return True, f"Successfully created {len(tables)} tables with {len(INDEXES)} indexes"

    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        return False, str(e)


def validate_schema(db_path: str = './data/spock_local.db'):
    """
    Validate financial statements schema integrity

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (is_valid: bool, validation_report: dict)
    """
    logger.info("🔍 Validating financial statements schema...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        validation_report = {}

        # Check tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('income_statements', 'balance_sheets', 'cash_flow_statements')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        validation_report['tables_exist'] = len(tables) == 3

        # Check indexes exist
        cursor.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='index' AND (
                name LIKE 'idx_income_%' OR
                name LIKE 'idx_balance_%' OR
                name LIKE 'idx_cashflow_%'
            )
        """)
        index_count = cursor.fetchone()[0]
        validation_report['indexes_count'] = index_count
        validation_report['indexes_expected'] = len(INDEXES)

        # Check foreign key constraints enabled
        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]
        validation_report['foreign_keys_enabled'] = bool(fk_enabled)

        conn.close()

        is_valid = (
            validation_report['tables_exist'] and
            validation_report['indexes_count'] >= 9  # At least 9 indexes (3 per table)
        )

        if is_valid:
            logger.info("✅ Schema validation passed")
        else:
            logger.warning("⚠️ Schema validation failed")

        return is_valid, validation_report

    except Exception as e:
        logger.error(f"❌ Schema validation error: {e}")
        return False, {'error': str(e)}


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Initialize financial statements schema')
    parser.add_argument('--db-path', default='./data/spock_local.db',
                       help='Path to SQLite database file')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate schema without creating')

    args = parser.parse_args()

    if args.validate_only:
        is_valid, report = validate_schema(args.db_path)
        print(f"\n{'✅ VALID' if is_valid else '❌ INVALID'}")
        print(f"Validation Report: {report}")
        sys.exit(0 if is_valid else 1)

    success, message = create_financial_statements_schema(args.db_path)

    if success:
        is_valid, report = validate_schema(args.db_path)
        print(f"\n✅ Schema initialization complete")
        print(f"Validation: {'✅ PASSED' if is_valid else '⚠️ WARNING'}")
        print(f"Report: {report}")
        sys.exit(0)
    else:
        print(f"\n❌ Schema initialization failed: {message}")
        sys.exit(1)


if __name__ == '__main__':
    main()
