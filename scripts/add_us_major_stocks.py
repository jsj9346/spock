#!/usr/bin/env python3
"""
Add major US stocks to tickers table

Since KIS API ticker search has issues, this script manually adds
major US stocks (S&P 500 components, NASDAQ 100, etc.) to the database.

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from dotenv import load_dotenv

# yfinance for stock info
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("⚠️ yfinance not installed. Install with: pip install yfinance")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


# Major US stocks by sector (Top 500+ companies)
MAJOR_US_STOCKS = {
    'Technology': [
        'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA',
        'AVGO', 'ORCL', 'CSCO', 'ADBE', 'CRM', 'ACN', 'INTC', 'AMD',
        'QCOM', 'IBM', 'TXN', 'INTU', 'AMAT', 'MU', 'ADI', 'LRCX',
        'KLAC', 'SNPS', 'CDNS', 'MCHP', 'NXPI', 'FTNT'
    ],
    'Financials': [
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'SCHW', 'AXP', 'BLK', 'SPGI',
        'CME', 'CB', 'PGR', 'AON', 'MMC', 'ICE', 'USB', 'PNC', 'TFC', 'COF'
    ],
    'Healthcare': [
        'UNH', 'JNJ', 'LLY', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY',
        'AMGN', 'CVS', 'ELV', 'CI', 'GILD', 'ISRG', 'VRTX', 'REGN', 'ZTS', 'SYK'
    ],
    'Consumer Discretionary': [
        'AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TJX', 'BKNG', 'CMG',
        'ROST', 'AZO', 'ORLY', 'YUM', 'DHI', 'F', 'GM', 'MAR', 'HLT', 'DG'
    ],
    'Consumer Staples': [
        'WMT', 'PG', 'KO', 'PEP', 'COST', 'PM', 'MO', 'MDLZ', 'CL', 'KMB',
        'GIS', 'KHC', 'STZ', 'SYY', 'HSY', 'K', 'CAG', 'TSN', 'CPB', 'CHD'
    ],
    'Energy': [
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'WMB',
        'KMI', 'HAL', 'BKR', 'DVN', 'HES', 'FANG', 'MRO', 'APA', 'OKE', 'EQT'
    ],
    'Industrials': [
        'BA', 'HON', 'UNP', 'UPS', 'RTX', 'LMT', 'CAT', 'DE', 'GE', 'MMM',
        'FDX', 'NSC', 'CSX', 'EMR', 'ITW', 'ETN', 'PH', 'CARR', 'PCAR', 'JCI'
    ],
    'Materials': [
        'LIN', 'APD', 'SHW', 'ECL', 'DD', 'NEM', 'FCX', 'DOW', 'VMC', 'MLM',
        'PPG', 'CTVA', 'NUE', 'STLD', 'CE', 'ALB', 'FMC', 'IFF', 'MOS', 'CF'
    ],
    'Communication Services': [
        'GOOGL', 'GOOG', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR',
        'EA', 'ATVI', 'TTWO', 'NWSA', 'NWS', 'FOXA', 'FOX', 'OMC', 'IPG', 'PARA'
    ],
    'Utilities': [
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'XEL', 'ED', 'PEG',
        'ES', 'WEC', 'DTE', 'ETR', 'AWK', 'PPL', 'FE', 'AEE', 'CMS', 'CNP'
    ],
    'Real Estate': [
        'PLD', 'AMT', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'SBAC',
        'AVB', 'EQR', 'VTR', 'INVH', 'ESS', 'MAA', 'ARE', 'PEAK', 'UDR', 'CPT'
    ]
}


def add_major_stocks():
    """Add major US stocks to database"""

    if not YFINANCE_AVAILABLE:
        logger.error("❌ yfinance is required but not installed")
        return False

    logger.info("=" * 70)
    logger.info("🚀 Adding Major US Stocks to Database")
    logger.info("=" * 70)

    # Initialize
    db = SQLiteDatabaseManager()

    all_tickers = []
    for sector, tickers in MAJOR_US_STOCKS.items():
        all_tickers.extend(tickers)

    # Remove duplicates
    all_tickers = list(set(all_tickers))

    logger.info(f"📊 Processing {len(all_tickers)} unique tickers...")

    success_count = 0
    failed_count = 0
    skipped_count = 0

    # Get existing US tickers to avoid duplicates
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM tickers WHERE region = 'US' AND asset_type = 'STOCK'")
    existing_ticker_symbols = set(row[0] for row in cursor.fetchall())
    conn.close()

    logger.info(f"📊 Found {len(existing_ticker_symbols)} existing US tickers in database")

    for i, ticker in enumerate(sorted(all_tickers), 1):
        try:
            # Check if ticker already exists
            if ticker in existing_ticker_symbols:
                logger.info(f"⏭️  [{i}/{len(all_tickers)}] {ticker} - Already exists, skipping")
                skipped_count += 1
                continue

            logger.info(f"📊 [{i}/{len(all_tickers)}] Processing {ticker}...")

            # Fetch info from yfinance
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or not info.get('symbol'):
                logger.warning(f"⚠️  {ticker} - No info available from yfinance")
                failed_count += 1
                continue

            # Parse sector mapping (GICS)
            sector = info.get('sector', '')
            industry = info.get('industry', '')

            # Map to GICS 11 sectors
            sector_map = {
                'Technology': 'Information Technology',
                'Financial Services': 'Financials',
                'Healthcare': 'Health Care',
                'Consumer Cyclical': 'Consumer Discretionary',
                'Consumer Defensive': 'Consumer Staples',
                'Energy': 'Energy',
                'Industrials': 'Industrials',
                'Basic Materials': 'Materials',
                'Communication Services': 'Communication Services',
                'Utilities': 'Utilities',
                'Real Estate': 'Real Estate'
            }
            sector = sector_map.get(sector, sector)

            # Determine exchange
            exchange = info.get('exchange', 'NASDAQ')
            kis_exchange_code = 'NASD'  # Default

            if 'NYSE' in exchange.upper():
                kis_exchange_code = 'NYSE'
                exchange = 'NYSE'
            elif 'AMEX' in exchange.upper():
                kis_exchange_code = 'AMEX'
                exchange = 'AMEX'
            elif 'NASDAQ' in exchange.upper() or 'NMS' in exchange.upper():
                kis_exchange_code = 'NASD'
                exchange = 'NASDAQ'

            # Build ticker info
            ticker_info = {
                'ticker': ticker,
                'name': info.get('longName', info.get('shortName', ticker)),
                'region': 'US',
                'asset_type': 'STOCK',
                'exchange': exchange,
                'sector': sector,
                'industry': industry,
                'market_cap': info.get('marketCap', 0),
                'is_active': True,
                'kis_exchange_code': kis_exchange_code
            }

            # Save to database using batch save method (single ticker)
            conn = db._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO tickers
                (ticker, name, region, asset_type, exchange, sector, industry,
                 market_cap, is_active, kis_exchange_code, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticker_info['ticker'],
                ticker_info.get('name', ''),
                ticker_info['region'],
                ticker_info['asset_type'],
                ticker_info['exchange'],
                ticker_info.get('sector', ''),
                ticker_info.get('industry', ''),
                ticker_info.get('market_cap', 0),
                1 if ticker_info['is_active'] else 0,
                ticker_info.get('kis_exchange_code', 'NASD'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            conn.commit()
            conn.close()

            success_count += 1
            logger.info(f"✅ {ticker} - Added ({ticker_info.get('name', 'Unknown')}, {ticker_info.get('exchange', 'Unknown')})")

        except Exception as e:
            logger.error(f"❌ {ticker} - Failed: {e}")
            failed_count += 1
            continue

    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("✅ Major US Stocks Addition Complete")
    logger.info("=" * 70)
    logger.info(f"📊 Total processed: {len(all_tickers)}")
    logger.info(f"✅ Successfully added: {success_count}")
    logger.info(f"⏭️  Skipped (already exists): {skipped_count}")
    logger.info(f"❌ Failed: {failed_count}")

    # Verify database
    us_tickers = db.get_tickers(region='US', asset_type='STOCK')
    logger.info(f"📊 Total US stocks in database: {len(us_tickers)}")

    return success_count > 0


if __name__ == '__main__':
    success = add_major_stocks()
    sys.exit(0 if success else 1)
