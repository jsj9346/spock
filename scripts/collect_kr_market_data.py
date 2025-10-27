#!/usr/bin/env python3
"""
Collect market data (shares outstanding, market cap, prices) for Korean stocks
Uses yfinance for comprehensive market data + KIS API for real-time prices

Usage:
    python3 scripts/collect_kr_market_data.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import yfinance as yf
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.api_clients.kis_domestic_stock_api import KISDomesticStockAPI
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress yfinance warnings
logging.getLogger('yfinance').setLevel(logging.ERROR)

def get_market_data_from_yfinance(ticker: str) -> dict:
    """
    Get market data from yfinance for Korean stock

    Args:
        ticker: Korean stock ticker (6-digit, e.g., '005930')

    Returns:
        Dict with market_cap, shares_outstanding, close_price
    """
    try:
        # Korean stocks need .KS or .KQ suffix for yfinance
        # KS = KOSPI, KQ = KOSDAQ
        # Most major stocks are on KOSPI (.KS)
        yahoo_ticker = f"{ticker}.KS"

        stock = yf.Ticker(yahoo_ticker)
        info = stock.info

        # Get current price (fallback to history if not available)
        close_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not close_price:
            hist = stock.history(period='1d')
            if not hist.empty:
                close_price = float(hist['Close'].iloc[-1])

        market_data = {
            'ticker': ticker,
            'market_cap': info.get('marketCap'),  # Market capitalization (KRW)
            'shares_outstanding': info.get('sharesOutstanding'),  # Total shares
            'close_price': close_price,  # Current price
            'pe_ratio': info.get('trailingPE'),  # P/E ratio
            'pb_ratio': info.get('priceToBook'),  # P/B ratio
            'dividend_yield': info.get('dividendYield'),  # Dividend yield (decimal)
        }

        # Log success
        logger.info(
            f"✅ [{ticker}] yfinance: "
            f"Price={market_data['close_price']:,.0f}원, "
            f"Market Cap={market_data['market_cap']/1e12:.2f}T KRW"
            if market_data['market_cap'] else f"Price={market_data['close_price']}"
        )

        return market_data

    except Exception as e:
        logger.error(f"❌ [{ticker}] yfinance failed: {e}")
        return {'ticker': ticker}

def get_current_price_from_kis(ticker: str, kis_api: KISDomesticStockAPI) -> float:
    """
    Get current price from KIS API (more accurate for Korean stocks)

    Args:
        ticker: Korean stock ticker
        kis_api: KIS API client

    Returns:
        Current price in KRW, or None if failed
    """
    try:
        price_data = kis_api.get_current_price(ticker)
        if price_data:
            return float(price_data.get('stck_prpr', 0))
    except Exception as e:
        logger.warning(f"⚠️ [{ticker}] KIS price failed: {e}")

    return None

def update_market_data_in_db(db: SQLiteDatabaseManager, market_data: dict, fiscal_year: int = 2025):
    """
    Update ticker_fundamentals with market data

    Args:
        db: Database manager
        market_data: Market data dictionary
        fiscal_year: Fiscal year to update (default: 2025)

    Returns:
        True if successful
    """
    ticker = market_data['ticker']

    try:
        # Get existing fundamental record for this ticker and fiscal year
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Check if record exists
        cursor.execute("""
            SELECT id FROM ticker_fundamentals
            WHERE ticker = ? AND fiscal_year = ? AND period_type = 'SEMI-ANNUAL'
            ORDER BY date DESC
            LIMIT 1
        """, (ticker, fiscal_year))

        result = cursor.fetchone()

        if result:
            # Update existing record
            record_id = result[0]

            cursor.execute("""
                UPDATE ticker_fundamentals
                SET market_cap = ?,
                    shares_outstanding = ?,
                    close_price = ?,
                    per = ?,
                    pbr = ?,
                    dividend_yield = ?
                WHERE id = ?
            """, (
                market_data.get('market_cap'),
                market_data.get('shares_outstanding'),
                market_data.get('close_price'),
                market_data.get('pe_ratio'),
                market_data.get('pb_ratio'),
                market_data.get('dividend_yield') * 100 if market_data.get('dividend_yield') else None,  # Convert to percentage
                record_id
            ))

            conn.commit()
            logger.info(f"✅ [{ticker}] Updated market data in database (ID: {record_id})")
            success = True
        else:
            logger.warning(f"⚠️ [{ticker}] No fundamental record found for {fiscal_year}")
            success = False

        conn.close()
        return success

    except Exception as e:
        logger.error(f"❌ [{ticker}] Database update failed: {e}")
        return False

def main():
    """Collect market data for 5 major Korean stocks"""

    # Target tickers
    tickers = [
        '005930',  # Samsung Electronics
        '000660',  # SK Hynix
        '035720',  # Kakao
        '051910',  # LG Chem
        '006400'   # Samsung SDI
    ]

    logger.info("="*70)
    logger.info("📊 Collecting market data for Korean stocks")
    logger.info("="*70)
    logger.info(f"Tickers: {', '.join(tickers)}")
    logger.info(f"Data Sources: yfinance (market cap, shares) + KIS API (real-time price)")
    logger.info("="*70)

    # Initialize KIS API for real-time prices
    try:
        kis_api = KISDomesticStockAPI(
            app_key=os.getenv('KIS_APP_KEY'),
            app_secret=os.getenv('KIS_APP_SECRET')
        )
        logger.info("✅ KIS API initialized")
    except Exception as e:
        logger.warning(f"⚠️ KIS API initialization failed: {e}")
        kis_api = None

    # Initialize database
    db = SQLiteDatabaseManager()

    # Collect market data
    results = {}

    for ticker in tickers:
        logger.info(f"\n🔄 [{ticker}] Collecting market data...")

        # Get market data from yfinance
        market_data = get_market_data_from_yfinance(ticker)

        # Get current price from KIS API (more accurate)
        if kis_api:
            kis_price = get_current_price_from_kis(ticker, kis_api)
            if kis_price:
                market_data['close_price'] = kis_price

                # Recalculate P/E and P/B with KIS price
                if market_data.get('shares_outstanding') and kis_price:
                    market_data['market_cap'] = int(market_data['shares_outstanding'] * kis_price)

        # Update database
        success = update_market_data_in_db(db, market_data, fiscal_year=2025)
        results[ticker] = success

    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 MARKET DATA COLLECTION RESULTS")
    logger.info("="*70)

    for ticker, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"{ticker}: {status}")

    success_count = sum(1 for s in results.values() if s)
    logger.info("="*70)
    logger.info(f"Total: {len(tickers)} tickers")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {len(tickers) - success_count}")
    logger.info(f"Success rate: {success_count/len(tickers)*100:.1f}%")
    logger.info("="*70)

    return 0 if success_count == len(tickers) else 1

if __name__ == '__main__':
    exit(main())
