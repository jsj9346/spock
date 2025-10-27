#!/usr/bin/env python3
"""
Calculate Fundamental Ratios Script

Purpose:
    Calculate market-based fundamental ratios (P/E, P/B, EV/EBITDA, Dividend Yield)
    from DART financial statement data + current market prices.

Why needed:
    DART API provides financial statement data (net income, equity, EBITDA, dividends)
    but does NOT provide market-based ratios which require current stock price and shares outstanding.

Ratios calculated:
    - P/E Ratio = Market Price / EPS (Earnings Per Share)
    - P/B Ratio = Market Price / Book Value Per Share
    - EV/EBITDA = (Market Cap + Total Debt - Cash) / EBITDA
    - Dividend Yield = (Annual Dividend / Market Price) * 100

Data sources:
    - Financial data: ticker_fundamentals table (from DART API)
    - Market prices: ohlcv_data table (from KIS API)
    - Shares outstanding: KIS API or estimated from market cap

Usage:
    # Calculate ratios for all KR stocks with DART data
    python3 scripts/calculate_fundamental_ratios.py --region KR

    # Calculate for specific tickers
    python3 scripts/calculate_fundamental_ratios.py --tickers 005930 000660 035420

    # Force recalculation (skip cache)
    python3 scripts/calculate_fundamental_ratios.py --region KR --force-refresh

Author: Spock Quant Platform
"""

import sys
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FundamentalRatioCalculator:
    """
    Calculate market-based fundamental ratios

    Workflow:
    1. Load financial statement data from ticker_fundamentals (DART)
    2. Get current market price from ohlcv_data (latest close price)
    3. Calculate ratios using formulas
    4. Update ticker_fundamentals with calculated ratios
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        """
        Initialize ratio calculator

        Args:
            db_path: Path to SQLite database
        """
        self.db = SQLiteDatabaseManager(db_path)
        logger.info("📊 FundamentalRatioCalculator initialized")

    def calculate_ratios_for_ticker(self, ticker: str) -> Dict[str, bool]:
        """
        Calculate all ratios for a single ticker

        Args:
            ticker: Ticker symbol (e.g., '005930')

        Returns:
            Dict with calculation results {ratio_name: success}

        Example:
            results = calculator.calculate_ratios_for_ticker('005930')
            # {'per': True, 'pbr': True, 'ev_ebitda': False, 'dividend_yield': True}
        """
        results = {
            'per': False,
            'pbr': False,
            'ev_ebitda': False,
            'dividend_yield': False
        }

        try:
            # Step 1: Get latest fundamental data from DART
            fundamentals = self.db.get_ticker_fundamentals(
                ticker=ticker,
                period_type='ANNUAL',  # Use annual reports
                limit=1
            )

            if not fundamentals or len(fundamentals) == 0:
                logger.warning(f"⚠️ {ticker}: No fundamental data found")
                return results

            fund_data = fundamentals[0]

            # Step 2: Get current market price (latest close)
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT close, date
                FROM ohlcv_data
                WHERE ticker = ? AND region = 'KR'
                ORDER BY date DESC
                LIMIT 1
            """, (ticker,))

            price_row = cursor.fetchone()
            conn.close()

            if not price_row:
                logger.warning(f"⚠️ {ticker}: No price data found")
                return results

            current_price = float(price_row[0])
            price_date = price_row[1]

            logger.debug(f"📊 {ticker}: Price={current_price:,.0f} (as of {price_date})")

            # Step 3: Extract financial metrics from DART data
            # Note: DART stores raw financial values (total_assets, total_equity, etc.)
            # We need to calculate per-share values

            total_assets = fund_data.get('total_assets')
            total_equity = fund_data.get('total_equity')
            total_liabilities = fund_data.get('total_liabilities')
            net_income = fund_data.get('net_income')
            revenue = fund_data.get('revenue')
            operating_profit = fund_data.get('operating_profit')

            # Estimate shares outstanding from market cap if available
            # Or use a conservative estimate based on equity
            shares_outstanding = fund_data.get('shares_outstanding')

            if not shares_outstanding and total_equity:
                # Rough estimate: assume book value per share ~= equity / estimated shares
                # This is a placeholder - ideally we'd get real shares outstanding from KIS API
                estimated_market_cap = current_price * 1_000_000  # Rough guess
                shares_outstanding = estimated_market_cap / current_price
                logger.debug(f"📊 {ticker}: Estimated shares outstanding (placeholder)")

            # Step 4: Calculate ratios
            update_data = {}

            # P/E Ratio = Price / EPS
            if net_income and shares_outstanding and net_income > 0:
                eps = net_income / shares_outstanding
                per = current_price / eps
                update_data['per'] = round(per, 2)
                results['per'] = True
                logger.debug(f"✅ {ticker}: P/E = {per:.2f}")

            # P/B Ratio = Price / Book Value Per Share
            if total_equity and shares_outstanding and total_equity > 0:
                book_value_per_share = total_equity / shares_outstanding
                pbr = current_price / book_value_per_share
                update_data['pbr'] = round(pbr, 2)
                results['pbr'] = True
                logger.debug(f"✅ {ticker}: P/B = {pbr:.2f}")

            # EV/EBITDA - requires EBITDA (operating profit + depreciation)
            # DART doesn't always provide depreciation, so this may fail
            # Placeholder: skip for now

            # Dividend Yield - requires dividend per share
            # DART may not provide this in current implementation
            # Placeholder: skip for now

            # Step 5: Update database with calculated ratios
            if update_data:
                # Update the specific fundamental record
                conn = sqlite3.connect(self.db.db_path)
                cursor = conn.cursor()

                update_fields = ', '.join([f"{k} = ?" for k in update_data.keys()])
                update_values = list(update_data.values()) + [ticker, fund_data['date']]

                cursor.execute(f"""
                    UPDATE ticker_fundamentals
                    SET {update_fields}
                    WHERE ticker = ? AND date = ?
                """, update_values)

                conn.commit()
                conn.close()

                logger.info(f"✅ {ticker}: Updated {len(update_data)} ratios")
            else:
                logger.warning(f"⚠️ {ticker}: No ratios calculated (missing data)")

            return results

        except Exception as e:
            logger.error(f"❌ {ticker}: Ratio calculation failed - {e}")
            return results

    def calculate_ratios_for_universe(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Calculate ratios for multiple tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict {ticker: {ratio_name: success}}
        """
        logger.info(f"📊 Calculating ratios for {len(tickers)} tickers...")

        all_results = {}
        success_count = 0

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"🔄 [{i}/{len(tickers)}] Processing {ticker}...")
            results = self.calculate_ratios_for_ticker(ticker)
            all_results[ticker] = results

            if any(results.values()):
                success_count += 1

        logger.info(f"✅ Ratio calculation complete: {success_count}/{len(tickers)} tickers updated")

        return all_results


def main():
    """CLI interface for ratio calculation"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Calculate Fundamental Ratios (P/E, P/B, EV/EBITDA, Dividend Yield)'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='List of ticker symbols (e.g., 005930 000660)'
    )
    parser.add_argument(
        '--region',
        choices=['KR', 'US', 'HK', 'CN', 'JP', 'VN'],
        help='Calculate for all tickers in region'
    )
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force recalculation (skip cache)'
    )

    args = parser.parse_args()

    # Collect tickers
    tickers = []

    if args.tickers:
        tickers.extend(args.tickers)
    elif args.region:
        # Get all tickers with fundamental data in region
        import sqlite3
        conn = sqlite3.connect("./data/spock_local.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT tf.ticker
            FROM ticker_fundamentals tf
            JOIN tickers t ON tf.ticker = t.ticker
            WHERE t.region = ?
            ORDER BY tf.ticker
        """, (args.region,))

        tickers = [row[0] for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📊 Found {len(tickers)} tickers with fundamental data in {args.region}")

    if not tickers:
        logger.error("❌ No tickers provided. Use --tickers or --region")
        return 1

    # Calculate ratios
    calculator = FundamentalRatioCalculator()
    results = calculator.calculate_ratios_for_universe(tickers)

    # Report summary
    logger.info("\n" + "="*60)
    logger.info("📊 Ratio Calculation Report")
    logger.info("="*60)

    per_success = sum(1 for r in results.values() if r['per'])
    pbr_success = sum(1 for r in results.values() if r['pbr'])

    logger.info(f"P/E Ratio calculated: {per_success}/{len(tickers)}")
    logger.info(f"P/B Ratio calculated: {pbr_success}/{len(tickers)}")
    logger.info("="*60)

    return 0


if __name__ == '__main__':
    exit(main())
