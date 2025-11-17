#!/usr/bin/env python3
"""
Macro Data Collection Script - Bonds & Commodities

Purpose:
- Collect bond yields (Treasury rates)
- Collect commodity prices (Gold, Oil, Silver, etc.)
- Store data in PostgreSQL (bond_yields, commodities tables)

Usage:
    python3 scripts/collect_macro_data.py \\
      --start-date 2024-01-01 \\
      --end-date 2025-01-12 \\
      --components bonds,commodities

Author: Spock Quant Platform
Created: 2025-11-12
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
import time

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


# ============================================================================
# Symbol Mappings
# ============================================================================

# Bond symbols (yfinance tickers for US Treasury yields)
BOND_SYMBOLS = {
    'US2Y': {
        'ticker': '^IRX',  # 13-week Treasury Bill (proxy for short-term)
        'country': 'US',
        'maturity': '3M',
        'name': 'US 3-Month Treasury'
    },
    'US10Y': {
        'ticker': '^TNX',  # 10-Year Treasury Note Yield
        'country': 'US',
        'maturity': '10Y',
        'name': 'US 10-Year Treasury'
    },
    'US30Y': {
        'ticker': '^TYX',  # 30-Year Treasury Bond Yield
        'country': 'US',
        'maturity': '30Y',
        'name': 'US 30-Year Treasury'
    }
}

# Commodity symbols (yfinance futures)
COMMODITY_SYMBOLS = {
    'GC=F': {
        'name': 'Gold Futures',
        'category': 'Metals'
    },
    'SI=F': {
        'name': 'Silver Futures',
        'category': 'Metals'
    },
    'CL=F': {
        'name': 'Crude Oil WTI Futures',
        'category': 'Energy'
    },
    'NG=F': {
        'name': 'Natural Gas Futures',
        'category': 'Energy'
    },
    'HG=F': {
        'name': 'Copper Futures',
        'category': 'Metals'
    },
    'PL=F': {
        'name': 'Platinum Futures',
        'category': 'Metals'
    }
}


# ============================================================================
# Bond Data Collection
# ============================================================================

def fetch_bond_data(symbol_key: str, start_date: date, end_date: date):
    """
    Fetch bond yield data from yfinance

    Args:
        symbol_key: Key from BOND_SYMBOLS (e.g., 'US10Y')
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with Date index and Close column (yield values)
    """
    bond_info = BOND_SYMBOLS.get(symbol_key)
    if not bond_info:
        logger.error(f"❌ Bond symbol {symbol_key} not found")
        return None

    try:
        logger.info(f"📊 Fetching {bond_info['name']} ({bond_info['ticker']})...")
        ticker = yf.Ticker(bond_info['ticker'])

        # Add 1 day to end_date for yfinance (exclusive end)
        hist = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        )

        if hist.empty:
            logger.warning(f"⚠️  No data available for {symbol_key}")
            return None

        logger.info(f"✅ Fetched {len(hist)} data points for {symbol_key}")
        return hist

    except Exception as e:
        logger.error(f"❌ Error fetching {symbol_key}: {e}")
        return None


def insert_bond_record(db, symbol_key: str, record_date: date, yield_value: float, prev_yield: float = None):
    """
    Insert bond yield record to PostgreSQL

    Args:
        db: Database manager
        symbol_key: Bond symbol key (e.g., 'US10Y')
        record_date: Date of record
        yield_value: Yield value (e.g., 4.25 for 4.25%)
        prev_yield: Previous day yield for change calculation

    Returns:
        True if successful
    """
    try:
        bond_info = BOND_SYMBOLS[symbol_key]

        # Calculate change in basis points
        change_bps = None
        if prev_yield is not None:
            change_bps = (yield_value - prev_yield) * 100  # Convert to basis points

        # Upsert query
        query = """
            INSERT INTO bond_yields (
                symbol,
                country,
                maturity,
                date,
                yield,
                change_bps,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (symbol, date)
            DO UPDATE SET
                yield = EXCLUDED.yield,
                change_bps = EXCLUDED.change_bps,
                created_at = NOW()
            RETURNING id
        """

        success = db.execute_update(
            query,
            (symbol_key, bond_info['country'], bond_info['maturity'],
             record_date, yield_value, change_bps)
        )

        if success:
            logger.debug(f"   ✓ {record_date}: {yield_value:.4f}% (Change: {change_bps:+.2f} bps)" if change_bps else f"   ✓ {record_date}: {yield_value:.4f}%")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ [{symbol_key}] Insert error ({record_date}): {e}")
        return False


def backfill_bond(db, symbol_key: str, start_date: date, end_date: date):
    """
    Backfill bond yield data

    Args:
        db: Database manager
        symbol_key: Bond symbol key
        start_date: Start date
        end_date: End date

    Returns:
        Number of records inserted
    """
    logger.info(f"\n{'─'*80}")
    logger.info(f"Processing Bond: {symbol_key} ({BOND_SYMBOLS[symbol_key]['name']})")
    logger.info(f"{'─'*80}")
    logger.info(f"📅 Date range: {start_date} → {end_date}")

    # Fetch data from yfinance
    hist = fetch_bond_data(symbol_key, start_date, end_date)
    if hist is None or hist.empty:
        logger.warning(f"⚠️  No data for {symbol_key}, skipping...")
        return 0

    # Insert each record
    inserted_count = 0
    prev_yield = None

    for idx, row in hist.iterrows():
        record_date = idx.date()
        yield_value = float(row['Close'])

        if insert_bond_record(db, symbol_key, record_date, yield_value, prev_yield):
            inserted_count += 1

        prev_yield = yield_value
        time.sleep(0.1)  # Rate limiting

    logger.info(f"✅ [{symbol_key}] Inserted {inserted_count} records")
    return inserted_count


# ============================================================================
# Commodity Data Collection
# ============================================================================

def fetch_commodity_data(symbol: str, start_date: date, end_date: date):
    """
    Fetch commodity price data from yfinance

    Args:
        symbol: Commodity symbol (e.g., 'GC=F')
        start_date: Start date
        end_date: End date

    Returns:
        DataFrame with OHLCV data
    """
    commodity_info = COMMODITY_SYMBOLS.get(symbol)
    if not commodity_info:
        logger.error(f"❌ Commodity symbol {symbol} not found")
        return None

    try:
        logger.info(f"📊 Fetching {commodity_info['name']} ({symbol})...")
        ticker = yf.Ticker(symbol)

        # Add 1 day to end_date for yfinance (exclusive end)
        hist = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        )

        if hist.empty:
            logger.warning(f"⚠️  No data available for {symbol}")
            return None

        logger.info(f"✅ Fetched {len(hist)} data points for {symbol}")
        return hist

    except Exception as e:
        logger.error(f"❌ Error fetching {symbol}: {e}")
        return None


def insert_commodity_record(db, symbol: str, record_date: date, row, prev_close: float = None):
    """
    Insert commodity price record to PostgreSQL

    Args:
        db: Database manager
        symbol: Commodity symbol
        record_date: Date of record
        row: DataFrame row with OHLCV data
        prev_close: Previous day close for change calculation

    Returns:
        True if successful
    """
    try:
        commodity_info = COMMODITY_SYMBOLS[symbol]

        # Calculate percentage change
        change_pct = None
        if prev_close is not None and prev_close > 0:
            change_pct = float(((row['Close'] - prev_close) / prev_close) * 100)

        # Upsert query
        query = """
            INSERT INTO commodities (
                symbol,
                name,
                category,
                date,
                close,
                open,
                high,
                low,
                volume,
                change_pct,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (symbol, date)
            DO UPDATE SET
                close = EXCLUDED.close,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                volume = EXCLUDED.volume,
                change_pct = EXCLUDED.change_pct,
                created_at = NOW()
            RETURNING id
        """

        success = db.execute_update(
            query,
            (symbol, commodity_info['name'], commodity_info['category'],
             record_date, float(row['Close']), float(row['Open']),
             float(row['High']), float(row['Low']),
             int(row['Volume']) if row.get('Volume') else None,
             change_pct)
        )

        if success:
            logger.debug(f"   ✓ {record_date}: ${row['Close']:,.2f} (Change: {change_pct:+.2f}%)" if change_pct else f"   ✓ {record_date}: ${row['Close']:,.2f}")
            return True

        return False

    except Exception as e:
        logger.error(f"❌ [{symbol}] Insert error ({record_date}): {e}")
        return False


def backfill_commodity(db, symbol: str, start_date: date, end_date: date):
    """
    Backfill commodity price data

    Args:
        db: Database manager
        symbol: Commodity symbol
        start_date: Start date
        end_date: End date

    Returns:
        Number of records inserted
    """
    logger.info(f"\n{'─'*80}")
    logger.info(f"Processing Commodity: {symbol} ({COMMODITY_SYMBOLS[symbol]['name']})")
    logger.info(f"{'─'*80}")
    logger.info(f"📅 Date range: {start_date} → {end_date}")

    # Fetch data from yfinance
    hist = fetch_commodity_data(symbol, start_date, end_date)
    if hist is None or hist.empty:
        logger.warning(f"⚠️  No data for {symbol}, skipping...")
        return 0

    # Insert each record
    inserted_count = 0
    prev_close = None

    for idx, row in hist.iterrows():
        record_date = idx.date()

        if insert_commodity_record(db, symbol, record_date, row, prev_close):
            inserted_count += 1

        prev_close = row['Close']
        time.sleep(0.1)  # Rate limiting

    logger.info(f"✅ [{symbol}] Inserted {inserted_count} records")
    return inserted_count


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Macro Data Collection (Bonds & Commodities)')
    parser.add_argument('--start-date', type=str, required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--components', type=str, default='bonds,commodities',
                       help='Components to collect (bonds,commodities)')

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    components = [c.strip().lower() for c in args.components.split(',')]

    logger.info("="*80)
    logger.info("MACRO DATA COLLECTION")
    logger.info("="*80)
    logger.info(f"Date range: {start_date} → {end_date}")
    logger.info(f"Components: {', '.join(components)}")
    logger.info("")

    # Initialize database
    db = PostgresDatabaseManager()

    # Collect bonds
    total_inserted = 0
    if 'bonds' in components:
        logger.info("\n" + "="*80)
        logger.info("BOND YIELDS COLLECTION")
        logger.info("="*80)

        for symbol_key in BOND_SYMBOLS.keys():
            count = backfill_bond(db, symbol_key, start_date, end_date)
            total_inserted += count
            time.sleep(1)  # Rate limiting between symbols

    # Collect commodities
    if 'commodities' in components:
        logger.info("\n" + "="*80)
        logger.info("COMMODITY PRICES COLLECTION")
        logger.info("="*80)

        for symbol in COMMODITY_SYMBOLS.keys():
            count = backfill_commodity(db, symbol, start_date, end_date)
            total_inserted += count
            time.sleep(1)  # Rate limiting between symbols

    logger.info("\n" + "="*80)
    logger.info("COLLECTION SUMMARY")
    logger.info("="*80)
    logger.info(f"Total records inserted: {total_inserted}")
    logger.info("="*80)


if __name__ == '__main__':
    main()
