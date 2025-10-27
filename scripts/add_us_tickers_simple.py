#!/usr/bin/env python3
"""
Simple script to add major US stock tickers to database

Uses yfinance to fetch basic info and adds to tickers table.
Adheres to existing database schema (no sector/industry columns in tickers table).

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager

try:
    import yfinance as yf
except ImportError:
    print("❌ yfinance not installed. Install with: pip install yfinance")
    sys.exit(1)

# Major US stocks (Top 100)
MAJOR_TICKERS = [
    # Technology
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA',
    'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM', 'ACN', 'INTC', 'AMD',

    # Financials
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'SCHW', 'AXP', 'BLK',

    # Healthcare
    'UNH', 'JNJ', 'LLY', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT',

    # Consumer
    'WMT', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TJX', 'COST',
    'PG', 'KO', 'PEP', 'PM', 'MO', 'MDLZ', 'CL',

    # Energy
    'XOM', 'CVX', 'COP', 'SLB', 'EOG',

    # Industrials
    'BA', 'HON', 'UNP', 'UPS', 'RTX', 'LMT', 'CAT', 'DE', 'GE',

    # Materials
    'LIN', 'APD', 'SHW', 'ECL', 'DD', 'NEM', 'FCX',

    # Communication
    'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS',

    # Utilities
    'NEE', 'DUK', 'SO', 'D', 'AEP',

    # Real Estate
    'PLD', 'AMT', 'CCI', 'EQIX', 'PSA', 'SPG'
]


def add_ticker_to_db(db, ticker, ticker_info):
    """Add single ticker to database"""
    conn = db._get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO tickers
            (ticker, name, name_eng, exchange, region, currency, asset_type,
             is_active, created_at, last_updated, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticker,
            ticker_info['name'],
            ticker_info['name'],  # name_eng same as name for US stocks
            ticker_info['exchange'],
            'US',
            'USD',
            'STOCK',
            1,  # is_active
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'yfinance'
        ))

        conn.commit()
        return True

    except Exception as e:
        print(f"  ❌ DB insert error: {e}")
        return False

    finally:
        conn.close()


def main():
    print("=" * 70)
    print("🚀 Adding Major US Stocks to Database (Simple Version)")
    print("=" * 70)
    print()

    db = SQLiteDatabaseManager()

    # Get existing tickers
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers WHERE region='US' AND asset_type='STOCK'")
    existing = set(row[0] for row in cursor.fetchall())
    conn.close()

    print(f"📊 Found {len(existing)} existing US tickers")
    print(f"📊 Processing {len(MAJOR_TICKERS)} major US stocks...")
    print()

    success = 0
    skipped = 0
    failed = 0

    for i, ticker in enumerate(MAJOR_TICKERS, 1):
        try:
            # Check if already exists
            if ticker in existing:
                print(f"⏭️  [{i}/{len(MAJOR_TICKERS)}] {ticker} - Already exists")
                skipped += 1
                continue

            print(f"📊 [{i}/{len(MAJOR_TICKERS)}] {ticker}...", end=' ')

            # Fetch from yfinance
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or not info.get('symbol'):
                print("❌ No data")
                failed += 1
                continue

            # Determine exchange
            yf_exchange = info.get('exchange', 'NMS')
            if 'NYSE' in yf_exchange.upper():
                exchange = 'NYSE'
            elif 'AMEX' in yf_exchange.upper():
                exchange = 'AMEX'
            else:
                exchange = 'NASDAQ'

            ticker_info = {
                'name': info.get('longName', info.get('shortName', ticker)),
                'exchange': exchange
            }

            # Add to database
            if add_ticker_to_db(db, ticker, ticker_info):
                name = ticker_info['name'][:40]
                print(f"✅ {name} | {exchange}")
                success += 1
            else:
                print("❌ DB error")
                failed += 1

        except Exception as e:
            print(f"❌ {e}")
            failed += 1
            continue

    print()
    print("=" * 70)
    print("✅ Complete")
    print("=" * 70)
    print(f"📊 Total: {len(MAJOR_TICKERS)}")
    print(f"✅ Added: {success}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"❌ Failed: {failed}")
    print()

    # Final count
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickers WHERE region='US' AND asset_type='STOCK'")
    final_count = cursor.fetchone()[0]
    conn.close()

    print(f"📊 Total US stocks in database: {final_count}")

    return success > 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
