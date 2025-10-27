#!/usr/bin/env python3
"""
Extend Database Schema for Quality Factors

Purpose:
    Add 11 new columns to ticker_fundamentals table to support comprehensive
    Quality factor analysis (17 factors across 5 categories).

New Columns:
    Profitability:
    - cogs (BIGINT): Cost of Goods Sold - 매출원가
    - gross_profit (BIGINT): Gross Profit - 매출총이익
    - depreciation (BIGINT): Depreciation & Amortization - 감가상각비
    - interest_expense (BIGINT): Interest Expense - 이자비용

    Balance Sheet:
    - current_assets (BIGINT): Current Assets - 유동자산
    - current_liabilities (BIGINT): Current Liabilities - 유동부채
    - inventory (BIGINT): Inventory - 재고자산
    - accounts_receivable (BIGINT): Accounts Receivable - 매출채권
    - cash_and_equivalents (BIGINT): Cash and Cash Equivalents - 현금및현금성자산

    Cash Flow:
    - operating_cash_flow (BIGINT): Operating Cash Flow - 영업활동현금흐름
    - capital_expenditure (BIGINT): Capital Expenditure - 자본적지출

Quality Factors Enabled:
    Profitability (6 factors):
    - ROE (자기자본이익률): net_income / total_equity
    - ROA (총자산이익률): net_income / total_assets
    - Operating Margin (영업이익률): operating_profit / revenue
    - Net Profit Margin (순이익률): net_income / revenue
    - Gross Profit Margin (매출총이익률): gross_profit / revenue
    - ROIC (투하자본이익률): NOPAT / invested_capital

    Liquidity (3 factors):
    - Current Ratio (유동비율): current_assets / current_liabilities
    - Quick Ratio (당좌비율): (current_assets - inventory) / current_liabilities
    - Cash Ratio (현금비율): cash_and_equivalents / current_liabilities

    Leverage (3 factors):
    - Debt-to-Equity (부채비율): total_liabilities / total_equity
    - Interest Coverage (이자보상배율): operating_profit / interest_expense
    - Net Debt-to-EBITDA: (total_liabilities - cash) / EBITDA

    Efficiency (3 factors):
    - Asset Turnover (총자산회전율): revenue / total_assets
    - Inventory Turnover (재고회전율): cogs / inventory
    - Receivables Turnover (매출채권회전율): revenue / accounts_receivable

    Earnings Quality (2 factors):
    - Accruals Ratio (발생액비율): (net_income - operating_cash_flow) / total_assets
    - CF-to-NI Ratio (현금흐름/순이익): operating_cash_flow / net_income

Usage:
    python3 scripts/extend_schema_for_quality_factors.py

    # Preview changes without applying
    python3 scripts/extend_schema_for_quality_factors.py --dry-run

    # Verbose output
    python3 scripts/extend_schema_for_quality_factors.py --verbose

Author: Spock Quant Platform - Phase 2 Quality Factors
"""

import sqlite3
import logging
from typing import List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "./data/spock_local.db"

# New columns for Quality factors
# Format: (column_name, data_type, description_korean, description_english)
NEW_COLUMNS: List[Tuple[str, str, str, str]] = [
    # Profitability columns
    ("cogs", "BIGINT", "매출원가", "Cost of Goods Sold"),
    ("gross_profit", "BIGINT", "매출총이익", "Gross Profit"),
    ("depreciation", "BIGINT", "감가상각비", "Depreciation & Amortization"),
    ("interest_expense", "BIGINT", "이자비용", "Interest Expense"),

    # Balance sheet columns
    ("current_assets", "BIGINT", "유동자산", "Current Assets"),
    ("current_liabilities", "BIGINT", "유동부채", "Current Liabilities"),
    ("inventory", "BIGINT", "재고자산", "Inventory"),
    ("accounts_receivable", "BIGINT", "매출채권", "Accounts Receivable"),
    ("cash_and_equivalents", "BIGINT", "현금및현금성자산", "Cash and Cash Equivalents"),

    # Cash flow columns
    ("operating_cash_flow", "BIGINT", "영업활동현금흐름", "Operating Cash Flow"),
    ("capital_expenditure", "BIGINT", "자본적지출", "Capital Expenditure (CapEx)"),
]


def get_existing_columns() -> List[str]:
    """Get list of existing columns in ticker_fundamentals table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(ticker_fundamentals)")
        columns = [row[1] for row in cursor.fetchall()]

        conn.close()
        return columns

    except Exception as e:
        logger.error(f"❌ Failed to get existing columns: {e}")
        return []


def add_quality_factor_columns(dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Add new columns to ticker_fundamentals table for Quality factors

    Args:
        dry_run: If True, preview changes without applying
        verbose: If True, show detailed output

    Returns:
        True if successful
    """
    try:
        # Get existing columns
        existing_columns = get_existing_columns()

        if not existing_columns:
            logger.error("❌ Failed to retrieve existing columns")
            return False

        logger.info(f"📊 Current ticker_fundamentals schema: {len(existing_columns)} columns")

        if verbose:
            logger.info(f"   Existing columns: {', '.join(existing_columns[:10])}...")

        # Determine which columns need to be added
        columns_to_add = [
            (col_name, col_type, desc_kr, desc_en)
            for col_name, col_type, desc_kr, desc_en in NEW_COLUMNS
            if col_name not in existing_columns
        ]

        if not columns_to_add:
            logger.info("✅ All Quality factor columns already exist")
            return True

        logger.info(f"\n📋 Columns to add: {len(columns_to_add)}")
        logger.info("="*80)

        # Add columns
        if not dry_run:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

        added_count = 0

        for col_name, col_type, desc_kr, desc_en in columns_to_add:
            if dry_run:
                logger.info(f"🔍 [DRY RUN] Would add: {col_name} ({col_type}) - {desc_kr} / {desc_en}")
            else:
                try:
                    cursor.execute(f"ALTER TABLE ticker_fundamentals ADD COLUMN {col_name} {col_type}")
                    logger.info(f"✅ Added: {col_name} ({col_type}) - {desc_kr} / {desc_en}")
                    added_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to add {col_name}: {e}")

        if not dry_run:
            conn.commit()
            conn.close()

        # Summary
        logger.info("")
        logger.info("="*80)
        logger.info("📊 Schema Extension Summary")
        logger.info("="*80)

        if dry_run:
            logger.info(f"🔍 [DRY RUN] Would add {len(columns_to_add)} columns")
        else:
            logger.info(f"✅ Successfully added {added_count}/{len(columns_to_add)} columns")

            # Verify
            new_column_count = len(get_existing_columns())
            logger.info(f"📊 New total columns: {new_column_count}")

        # Show enabled Quality factors
        logger.info("")
        logger.info("🎯 Quality Factors Enabled:")
        logger.info("   Profitability (6): ROE, ROA, Operating Margin, Net Margin, Gross Margin, ROIC")
        logger.info("   Liquidity (3): Current Ratio, Quick Ratio, Cash Ratio")
        logger.info("   Leverage (3): Debt-to-Equity, Interest Coverage, Net Debt-to-EBITDA")
        logger.info("   Efficiency (3): Asset Turnover, Inventory Turnover, Receivables Turnover")
        logger.info("   Earnings Quality (2): Accruals Ratio, CF-to-NI Ratio")
        logger.info("   Total: 17 Quality factors")

        logger.info("="*80)

        return True

    except Exception as e:
        logger.error(f"❌ Schema extension failed: {e}")
        return False


def verify_schema() -> bool:
    """Verify all required columns exist"""
    try:
        existing_columns = get_existing_columns()

        missing_columns = [
            col_name for col_name, _, _, _ in NEW_COLUMNS
            if col_name not in existing_columns
        ]

        if missing_columns:
            logger.warning(f"⚠️  Missing columns: {', '.join(missing_columns)}")
            return False
        else:
            logger.info("✅ All Quality factor columns verified")
            return True

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False


def main():
    """CLI interface for schema extension"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Extend Database Schema for Quality Factors (17 factors)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify schema without making changes'
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("="*80)
    logger.info("📊 Extend Database Schema for Quality Factors")
    logger.info("="*80)
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"New columns: {len(NEW_COLUMNS)}")
    logger.info(f"Quality factors enabled: 17 (across 5 categories)")
    logger.info("")

    if args.verify_only:
        # Verification only
        logger.info("🔍 Verification Mode")
        logger.info("="*80)
        success = verify_schema()
        return 0 if success else 1
    else:
        # Schema extension
        success = add_quality_factor_columns(dry_run=args.dry_run, verbose=args.verbose)

        if not args.dry_run and success:
            # Verify after extension
            logger.info("")
            logger.info("🔍 Verifying schema changes...")
            verify_schema()

        if args.dry_run:
            logger.info("")
            logger.info("💡 This was a dry run. Run without --dry-run to apply changes.")

        return 0 if success else 1


if __name__ == '__main__':
    exit(main())
