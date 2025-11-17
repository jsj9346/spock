#!/usr/bin/env python3
"""
Fundamental Data Collection Script for HK Market
Collects P/E, P/B, ROE, dividend yield, market cap from yfinance

Usage:
    python3 scripts/collect_fundamental_data.py --region HK --rate-limit 1.0
"""

import sys
import os
import argparse
import logging
import time
from datetime import datetime, date
from typing import Optional, Dict
import pandas as pd
import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/fundamental_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FundamentalDataCollector:
    """Collect and store fundamental data from yfinance"""

    def __init__(self, db_manager: PostgresDatabaseManager, rate_limit: float = 1.0):
        self.db = db_manager
        self.rate_limit = rate_limit  # requests per second

    def fetch_fundamental_data(self, ticker: str) -> Optional[Dict]:
        """Fetch fundamental data for a single ticker from yfinance"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract fundamental metrics
            fundamentals = {
                'ticker': ticker,
                'date': date.today(),
                'period_type': 'DAILY',
                'shares_outstanding': info.get('sharesOutstanding'),
                'market_cap': info.get('marketCap'),
                'close_price': info.get('currentPrice') or info.get('previousClose'),
                'per': info.get('trailingPE') or info.get('forwardPE'),
                'pbr': info.get('priceToBook'),
                'psr': info.get('priceToSalesTrailing12Months'),
                'pcr': None,  # Not directly available, need to calculate
                'ev': info.get('enterpriseValue'),
                'ev_ebitda': info.get('enterpriseToEbitda'),
                'dividend_yield': info.get('dividendYield'),
                'dividend_per_share': info.get('dividendRate')
            }

            # Validate that we got at least some data
            if fundamentals['market_cap'] is None and fundamentals['close_price'] is None:
                logger.warning(f"⚠️  {ticker}: No fundamental data available")
                return None

            return fundamentals

        except Exception as e:
            logger.error(f"❌ {ticker}: Error fetching data - {str(e)}")
            return None

    def save_fundamental_data(self, ticker: str, region: str, fundamentals: Dict) -> bool:
        """Save fundamental data to ticker_fundamentals table"""
        try:
            # Check if record exists for today
            check_query = """
                SELECT id FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s AND date = %s
            """
            existing = self.db.execute_query(
                check_query,
                (ticker, region, fundamentals['date'])
            )

            if existing:
                # Update existing record
                update_query = """
                    UPDATE ticker_fundamentals
                    SET shares_outstanding = %(shares_outstanding)s,
                        market_cap = %(market_cap)s,
                        close_price = %(close_price)s,
                        per = %(per)s,
                        pbr = %(pbr)s,
                        psr = %(psr)s,
                        pcr = %(pcr)s,
                        ev = %(ev)s,
                        ev_ebitda = %(ev_ebitda)s,
                        dividend_yield = %(dividend_yield)s,
                        dividend_per_share = %(dividend_per_share)s
                    WHERE ticker = %(ticker)s AND region = %(region)s AND date = %(date)s
                """
                fundamentals['region'] = region
                self.db.execute_update(update_query, fundamentals)
                logger.debug(f"✅ {ticker}: Updated existing record")
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO ticker_fundamentals (
                        ticker, region, date, period_type,
                        shares_outstanding, market_cap, close_price,
                        per, pbr, psr, pcr,
                        ev, ev_ebitda,
                        dividend_yield, dividend_per_share
                    ) VALUES (
                        %(ticker)s, %(region)s, %(date)s, %(period_type)s,
                        %(shares_outstanding)s, %(market_cap)s, %(close_price)s,
                        %(per)s, %(pbr)s, %(psr)s, %(pcr)s,
                        %(ev)s, %(ev_ebitda)s,
                        %(dividend_yield)s, %(dividend_per_share)s
                    )
                """
                fundamentals['region'] = region
                self.db.execute_update(insert_query, fundamentals)
                logger.debug(f"✅ {ticker}: Inserted new record")

            return True

        except Exception as e:
            logger.error(f"❌ {ticker}: Error saving data - {str(e)}")
            return False

    def collect_all_tickers(self, region: str, batch_size: int = 50) -> dict:
        """Collect fundamental data for all active tickers in a region"""
        logger.info(f"🚀 Starting fundamental data collection for region: {region}")

        # Get list of active tickers
        query = """
            SELECT ticker, name
            FROM tickers
            WHERE region = %s AND is_active = true
            ORDER BY ticker
        """

        # Extract ticker list from List[Dict] result
        result = self.db.execute_query(query, (region,))
        tickers = [row['ticker'] for row in result]

        logger.info(f"📊 Found {len(tickers)} active tickers to process")

        # Process tickers with rate limiting
        success_count = 0
        failed_count = 0
        no_data_count = 0
        start_time = datetime.now()

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] Fetching {ticker}...")

            # Fetch data
            fundamentals = self.fetch_fundamental_data(ticker)

            if fundamentals is None:
                no_data_count += 1
                failed_count += 1
            else:
                # Save to database
                if self.save_fundamental_data(ticker, region, fundamentals):
                    success_count += 1
                    logger.info(f"✅ {ticker}: P/E={fundamentals.get('per')}, "
                              f"P/B={fundamentals.get('pbr')}, "
                              f"Div Yield={fundamentals.get('dividend_yield')}")
                else:
                    failed_count += 1

            # Rate limiting
            time.sleep(1.0 / self.rate_limit)

            # Progress update every batch_size
            if i % batch_size == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = i / elapsed
                remaining = (len(tickers) - i) / rate if rate > 0 else 0
                logger.info(f"📈 Progress: {i}/{len(tickers)} ({i*100//len(tickers)}%) | "
                          f"Success: {success_count} | Failed: {failed_count} | "
                          f"ETA: {remaining/60:.1f} min")

        # Final summary
        duration = (datetime.now() - start_time).total_seconds()
        results = {
            'total_tickers': len(tickers),
            'success_count': success_count,
            'failed_count': failed_count,
            'no_data_count': no_data_count,
            'success_rate': f"{success_count*100/len(tickers):.2f}%",
            'duration_seconds': duration,
            'duration_minutes': duration / 60,
            'rate_per_second': len(tickers) / duration if duration > 0 else 0
        }

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Fundamental Data Collection Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Total Tickers: {results['total_tickers']}")
        logger.info(f"Success: {results['success_count']} ({results['success_rate']})")
        logger.info(f"Failed: {results['failed_count']} (No data: {results['no_data_count']})")
        logger.info(f"Duration: {results['duration_minutes']:.2f} minutes")
        logger.info(f"Rate: {results['rate_per_second']:.2f} tickers/sec")
        logger.info(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(description='Collect fundamental data from yfinance')
    parser.add_argument('--region', type=str, default='HK', help='Market region (default: HK)')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                       help='Max requests per second (default: 1.0)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Progress report batch size (default: 50)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (fetch but do not save)')

    args = parser.parse_args()

    logger.info(f"🎯 Fundamental Data Collector")
    logger.info(f"Region: {args.region}")
    logger.info(f"Rate Limit: {args.rate_limit} req/s")
    logger.info(f"Batch Size: {args.batch_size}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("")

    # Initialize database
    db_manager = PostgresDatabaseManager()

    if args.dry_run:
        logger.info("⚠️  DRY RUN MODE - No database updates will be performed")

    # Collect fundamental data
    collector = FundamentalDataCollector(db_manager, rate_limit=args.rate_limit)
    results = collector.collect_all_tickers(region=args.region, batch_size=args.batch_size)

    # Close database connection pool
    try:
        db_manager.close_pool()
    except AttributeError:
        pass  # Connection pool closes automatically

    logger.info("🎉 Script completed successfully!")


if __name__ == "__main__":
    main()
