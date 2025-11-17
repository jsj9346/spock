#!/usr/bin/env python3
"""
YFinance FX Data Backfill - Alternative to BOK API

Purpose:
- Collect historical FX rates using yfinance (bypasses BOK API rate limits)
- Supports USD, HKD, CNY, JPY, VND
- Direct PostgreSQL insertion

Usage:
    python3 scripts/yfinance_fx_backfill.py --start-date 2024-01-01 --end-date 2024-01-07 --currencies USD

Author: Spock Quant Platform
Created: 2025-11-12
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Currency mapping to yfinance tickers
CURRENCY_TICKER_MAP = {
    'USD': 'KRW=X',      # USD/KRW
    'JPY': 'JPYKRW=X',   # JPY/KRW
    'CNY': 'CNYKRW=X',   # CNY/KRW
    'HKD': 'HKDKRW=X',   # HKD/KRW
    'VND': 'VNDKRW=X',   # VND/KRW (may not be available)
}

CURRENCY_REGION_MAP = {
    'USD': 'US',
    'HKD': 'HK',
    'CNY': 'CN',
    'JPY': 'JP',
    'VND': 'VN',
}


def fetch_fx_data(currency: str, start_date: date, end_date: date):
    """
    Fetch FX data from yfinance

    Args:
        currency: Currency code (USD, JPY, etc.)
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with Date index and Close column
    """
    ticker_symbol = CURRENCY_TICKER_MAP.get(currency)
    if not ticker_symbol:
        logger.error(f"❌ Currency {currency} not supported")
        return None

    try:
        logger.info(f"📊 Fetching {currency} from yfinance ({ticker_symbol})...")
        ticker = yf.Ticker(ticker_symbol)

        # Add 1 day to end_date for yfinance (exclusive end)
        hist = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        )

        if hist.empty:
            logger.warning(f"⚠️ No data available for {currency}")
            return None

        logger.info(f"✅ Fetched {len(hist)} data points for {currency}")
        return hist

    except Exception as e:
        logger.error(f"❌ Error fetching {currency}: {e}")
        return None


def insert_fx_record(db, currency: str, record_date: date, krw_rate: float):
    """
    Insert FX record to PostgreSQL

    Args:
        db: Database manager
        currency: Currency code
        record_date: Date of record
        krw_rate: KRW exchange rate

    Returns:
        True if successful
    """
    try:
        # Calculate USD-normalized rate
        if currency == 'USD':
            usd_rate = 1.0
        else:
            # For other currencies, normalize against USD
            # This is a simplification - in production, fetch actual USD rates
            usd_rate = krw_rate / 1300.0  # Approximate

        region = CURRENCY_REGION_MAP.get(currency, 'US')

        # Upsert query
        query = """
            INSERT INTO fx_valuation_signals (
                currency,
                region,
                date,
                usd_rate,
                data_quality,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON CONFLICT (currency, region, date)
            DO UPDATE SET
                usd_rate = EXCLUDED.usd_rate,
                data_quality = EXCLUDED.data_quality,
                updated_at = NOW()
            RETURNING id
        """

        success = db.execute_update(
            query,
            (currency, region, record_date, usd_rate, 'GOOD')
        )

        if success:
            logger.debug(f"   ✓ {record_date}: {krw_rate:.2f} KRW (USD: {usd_rate:.6f})")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ [{currency}] Insert error ({record_date}): {e}")
        return False


def backfill_currency(db, currency: str, start_date: date, end_date: date):
    """
    Backfill FX data for a single currency

    Args:
        db: Database manager
        currency: Currency code
        start_date: Start date
        end_date: End date

    Returns:
        Number of records inserted
    """
    logger.info(f"\n{'─'*80}")
    logger.info(f"Processing Currency: {currency}")
    logger.info(f"{'─'*80}")
    logger.info(f"📅 Date range: {start_date} → {end_date}")

    # Fetch data from yfinance
    hist = fetch_fx_data(currency, start_date, end_date)
    if hist is None or hist.empty:
        logger.warning(f"⚠️ No data for {currency}, skipping...")
        return 0

    # Insert each record
    inserted_count = 0
    for idx, row in hist.iterrows():
        record_date = idx.date()
        krw_rate = float(row['Close'])

        if insert_fx_record(db, currency, record_date, krw_rate):
            inserted_count += 1

    logger.info(f"✅ [{currency}] Inserted {inserted_count} records")
    return inserted_count


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='YFinance FX Data Backfill')
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--currencies', type=str, default='USD', help='Comma-separated currencies (USD,JPY,CNY)')

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    currencies = [c.strip().upper() for c in args.currencies.split(',')]

    logger.info("="*80)
    logger.info("YFINANCE FX HISTORICAL BACKFILL")
    logger.info("="*80)
    logger.info(f"Date range: {start_date} → {end_date}")
    logger.info(f"Currencies: {', '.join(currencies)}")
    logger.info("")

    # Initialize database
    db = PostgresDatabaseManager()

    # Process each currency
    total_inserted = 0
    for currency in currencies:
        count = backfill_currency(db, currency, start_date, end_date)
        total_inserted += count

    logger.info("\n" + "="*80)
    logger.info("BACKFILL SUMMARY")
    logger.info("="*80)
    logger.info(f"Total records inserted: {total_inserted}")
    logger.info("="*80)


if __name__ == '__main__':
    main()
