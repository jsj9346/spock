#!/usr/bin/env python3
"""
Populate Test Fundamental Ratios

Purpose:
    Insert realistic fundamental ratios for 15 major Korean stocks to validate
    Value factors end-to-end without requiring full KIS API integration.

Why needed:
    - DART provides financial statement data but not market-based ratios
    - Calculating ratios requires shares outstanding data (4-6 hours of work)
    - This test data allows immediate validation of Factor Library infrastructure

Test Universe:
    15 major Korean stocks across different styles:
    - Value stocks (low P/E, low P/B, high dividend)
    - Growth stocks (high P/E, high P/B, low dividend)
    - Balanced stocks (mid-range ratios)
    - Edge cases (NULL values, extreme ratios)

Ratios Inserted:
    - P/E Ratio (Price-to-Earnings)
    - P/B Ratio (Price-to-Book)
    - EV/EBITDA (Enterprise Value / EBITDA)
    - Dividend Yield (%)

Usage:
    python3 scripts/populate_test_fundamental_ratios.py

    # Dry run (preview without changes)
    python3 scripts/populate_test_fundamental_ratios.py --dry-run

    # Verbose output
    python3 scripts/populate_test_fundamental_ratios.py --verbose

Author: Spock Quant Platform
"""

import sqlite3
import logging
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "./data/spock_local.db"

# Test fundamental ratios for 15 major Korean stocks
# Ratios based on realistic market values as of Q4 2024
TEST_FUNDAMENTAL_RATIOS = {
    # Large Cap Value Stocks (Low P/E, Low P/B, High Dividend)
    '005930': {  # Samsung Electronics
        'name': 'Samsung Electronics',
        'per': 12.5,
        'pbr': 1.2,
        'ev_ebitda': 6.5,
        'dividend_yield': 2.5,
        'style': 'Quality Value'
    },
    '000660': {  # SK Hynix
        'name': 'SK Hynix',
        'per': 8.3,
        'pbr': 1.5,
        'ev_ebitda': 5.2,
        'dividend_yield': 1.8,
        'style': 'Quality Value'
    },
    '005380': {  # Hyundai Motor
        'name': 'Hyundai Motor',
        'per': 5.2,
        'pbr': 0.45,
        'ev_ebitda': 3.8,
        'dividend_yield': 4.2,
        'style': 'Deep Value'
    },
    '005490': {  # POSCO Holdings
        'name': 'POSCO Holdings',
        'per': 7.8,
        'pbr': 0.62,
        'ev_ebitda': 4.5,
        'dividend_yield': 3.5,
        'style': 'Deep Value'
    },

    # Large Cap Growth Stocks (High P/E, High P/B, Low Dividend)
    '035420': {  # NAVER
        'name': 'NAVER',
        'per': 25.3,
        'pbr': 2.8,
        'ev_ebitda': 12.1,
        'dividend_yield': 0.3,
        'style': 'Growth'
    },
    '035720': {  # Kakao
        'name': 'Kakao',
        'per': 32.1,
        'pbr': 3.5,
        'ev_ebitda': 15.2,
        'dividend_yield': 0.2,
        'style': 'Growth'
    },
    '207940': {  # Samsung Biologics
        'name': 'Samsung Biologics',
        'per': 45.2,
        'pbr': 5.8,
        'ev_ebitda': 22.3,
        'dividend_yield': 0.0,
        'style': 'Growth'
    },

    # Mid Cap Balanced Stocks
    '105560': {  # KB Financial
        'name': 'KB Financial',
        'per': 6.8,
        'pbr': 0.55,
        'ev_ebitda': None,  # Financials don't have EBITDA
        'dividend_yield': 5.2,
        'style': 'High Dividend'
    },
    '055550': {  # Shinhan Financial
        'name': 'Shinhan Financial',
        'per': 7.2,
        'pbr': 0.48,
        'ev_ebitda': None,  # Financials don't have EBITDA
        'dividend_yield': 4.8,
        'style': 'High Dividend'
    },
    '051910': {  # LG Chem
        'name': 'LG Chem',
        'per': 15.3,
        'pbr': 1.8,
        'ev_ebitda': 8.5,
        'dividend_yield': 1.5,
        'style': 'Quality Value'
    },

    # High Dividend Stocks
    '015760': {  # Korea Electric Power
        'name': 'Korea Electric Power',
        'per': 18.5,
        'pbr': 0.92,
        'ev_ebitda': None,  # Utility with irregular EBITDA
        'dividend_yield': 6.5,
        'style': 'High Dividend'
    },
    '033780': {  # KT&G
        'name': 'KT&G',
        'per': 11.2,
        'pbr': 1.3,
        'ev_ebitda': 7.8,
        'dividend_yield': 5.8,
        'style': 'High Dividend'
    },

    # Small/Mid Cap Mixed
    '068270': {  # Celltrion
        'name': 'Celltrion',
        'per': 22.5,
        'pbr': 4.2,
        'ev_ebitda': 14.5,
        'dividend_yield': 0.5,
        'style': 'Growth'
    },
    '066570': {  # LG Electronics
        'name': 'LG Electronics',
        'per': 9.8,
        'pbr': 0.85,
        'ev_ebitda': 5.5,
        'dividend_yield': 2.2,
        'style': 'Quality Value'
    },
    '006400': {  # Samsung SDI
        'name': 'Samsung SDI',
        'per': 18.5,
        'pbr': 2.5,
        'ev_ebitda': 9.2,
        'dividend_yield': 1.2,
        'style': 'Quality Value'
    },
}


def update_ticker_ratios(ticker: str, ratios: Dict, dry_run: bool = False, verbose: bool = False) -> bool:
    """
    Update fundamental ratios for a ticker

    Args:
        ticker: Ticker symbol (e.g., '005930')
        ratios: Dict with ratio values
        dry_run: If True, preview changes without committing
        verbose: If True, show detailed output

    Returns:
        True if successful
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Step 1: Check if ticker has fundamental data
        cursor.execute("""
            SELECT ticker, date, fiscal_year, period_type
            FROM ticker_fundamentals
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT 1
        """, (ticker,))

        existing = cursor.fetchone()

        if not existing:
            logger.warning(f"⚠️  {ticker} ({ratios['name']}): No fundamental data found, skipping")
            conn.close()
            return False

        existing_ticker, existing_date, fiscal_year, period_type = existing

        if verbose:
            logger.info(f"📊 {ticker} ({ratios['name']}): Found record from {existing_date} ({period_type} {fiscal_year})")

        # Step 2: Update ratios
        if not dry_run:
            cursor.execute("""
                UPDATE ticker_fundamentals
                SET
                    per = ?,
                    pbr = ?,
                    ev_ebitda = ?,
                    dividend_yield = ?
                WHERE ticker = ? AND date = ?
            """, (
                ratios['per'],
                ratios['pbr'],
                ratios['ev_ebitda'],
                ratios['dividend_yield'],
                ticker,
                existing_date
            ))

            conn.commit()

        conn.close()

        # Step 3: Log success
        ratio_summary = f"P/E={ratios['per']}, P/B={ratios['pbr']}, EV/EBITDA={ratios['ev_ebitda'] or 'NULL'}, Div={ratios['dividend_yield']}%"

        if dry_run:
            logger.info(f"🔍 [DRY RUN] {ticker} ({ratios['name']}): Would update {ratio_summary}")
        else:
            logger.info(f"✅ {ticker} ({ratios['name']}): Updated {ratio_summary}")

        return True

    except Exception as e:
        logger.error(f"❌ {ticker}: Failed to update ratios - {e}")
        return False


def verify_insertions() -> Dict:
    """
    Verify test data was inserted correctly

    Returns:
        Dict with verification statistics
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {
            'total_tickers': 0,
            'per_available': 0,
            'pbr_available': 0,
            'ev_ebitda_available': 0,
            'dividend_yield_available': 0
        }

        for ticker in TEST_FUNDAMENTAL_RATIOS.keys():
            cursor.execute("""
                SELECT per, pbr, ev_ebitda, dividend_yield
                FROM ticker_fundamentals
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            """, (ticker,))

            row = cursor.fetchone()
            if row:
                stats['total_tickers'] += 1
                if row[0] is not None:
                    stats['per_available'] += 1
                if row[1] is not None:
                    stats['pbr_available'] += 1
                if row[2] is not None:
                    stats['ev_ebitda_available'] += 1
                if row[3] is not None:
                    stats['dividend_yield_available'] += 1

        conn.close()
        return stats

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return {}


def main():
    """CLI interface for test data population"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Populate Test Fundamental Ratios for Value Factor Validation'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing to database'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("="*80)
    logger.info("📊 Populate Test Fundamental Ratios")
    logger.info("="*80)
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Test universe: {len(TEST_FUNDAMENTAL_RATIOS)} stocks")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("")

    # Update ratios for each ticker
    success_count = 0
    fail_count = 0

    for ticker, ratios in TEST_FUNDAMENTAL_RATIOS.items():
        success = update_ticker_ratios(ticker, ratios, dry_run=args.dry_run, verbose=args.verbose)
        if success:
            success_count += 1
        else:
            fail_count += 1

    # Verify insertions (skip if dry run)
    if not args.dry_run:
        logger.info("")
        logger.info("="*80)
        logger.info("🔍 Verification")
        logger.info("="*80)

        stats = verify_insertions()

        if stats:
            logger.info(f"✅ Updated {stats['total_tickers']}/{len(TEST_FUNDAMENTAL_RATIOS)} tickers")
            logger.info(f"   - P/E Ratio: {stats['per_available']}/{stats['total_tickers']} stocks")
            logger.info(f"   - P/B Ratio: {stats['pbr_available']}/{stats['total_tickers']} stocks")
            logger.info(f"   - EV/EBITDA: {stats['ev_ebitda_available']}/{stats['total_tickers']} stocks (3 NULL by design)")
            logger.info(f"   - Dividend Yield: {stats['dividend_yield_available']}/{stats['total_tickers']} stocks")
        else:
            logger.warning("⚠️  Verification failed")

    # Summary
    logger.info("")
    logger.info("="*80)
    logger.info("📊 Summary")
    logger.info("="*80)
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")

    if args.dry_run:
        logger.info("")
        logger.info("💡 This was a dry run. Run without --dry-run to commit changes.")

    if not args.dry_run and success_count > 0:
        logger.info("")
        logger.info("🎯 Next Steps:")
        logger.info("   python3 examples/example_value_factors_usage.py")
        logger.info("")

    logger.info("="*80)

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    exit(main())
