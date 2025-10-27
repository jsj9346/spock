#!/usr/bin/env python3
"""
FCF Data Collection Script

Collects Free Cash Flow (FCF) data from multiple sources and populates
the ticker_fundamentals table with fcf, operating_cash_flow, capex, and fcf_yield.

Data Sources (in priority order):
1. KIS API (Korea markets) - fundamental data
2. yfinance (Global markets) - cash flow statements
3. Polygon.io (US markets) - financial statements

Usage:
    python3 scripts/collect_fcf_data.py --region KR --dry-run
    python3 scripts/collect_fcf_data.py --region US --tickers AAPL,MSFT,GOOGL
    python3 scripts/collect_fcf_data.py --region ALL --batch-size 100
"""

import os
import sys
import argparse
import psycopg2
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from loguru import logger

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class FCFDataCollector:
    """Collect and store Free Cash Flow data from multiple sources"""

    def __init__(self, conn, dry_run: bool = False):
        self.conn = conn
        self.dry_run = dry_run

    def collect_from_yfinance(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Collect FCF data from yfinance

        Returns dict with:
        - operating_cash_flow: Operating cash flow (annual)
        - capex: Capital expenditures (annual)
        - fcf: Free cash flow (operating_cash_flow - capex)
        - fiscal_year: Fiscal year
        - date: Report date
        """
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            cash_flow = stock.cashflow  # Annual cash flow statement

            if cash_flow.empty:
                logger.warning(f"{ticker} - No cash flow data available")
                return None

            # Get most recent column (latest fiscal year)
            latest_date = cash_flow.columns[0]

            # Extract cash flow components
            operating_cf = None
            capex = None

            # Try different possible row names (yfinance naming can vary)
            ocf_names = ['Operating Cash Flow', 'Total Cash From Operating Activities',
                        'Cash From Operating Activities']
            capex_names = ['Capital Expenditure', 'Capital Expenditures',
                          'Purchase Of Property Plant Equipment', 'Capex']

            for name in ocf_names:
                if name in cash_flow.index:
                    operating_cf = cash_flow.loc[name, latest_date]
                    break

            for name in capex_names:
                if name in cash_flow.index:
                    capex = abs(cash_flow.loc[name, latest_date])  # Make positive
                    break

            if operating_cf is None or capex is None:
                logger.warning(f"{ticker} - Missing cash flow components")
                return None

            fcf = operating_cf - capex
            fiscal_year = latest_date.year

            # Get market cap for FCF yield calculation
            info = stock.info
            market_cap = info.get('marketCap')

            if market_cap and market_cap > 0:
                fcf_yield = float((fcf / market_cap) * 100)  # Convert to percentage and Python float
            else:
                fcf_yield = None

            return {
                'operating_cash_flow': int(operating_cf),
                'capex': int(capex),
                'fcf': int(fcf),
                'fcf_yield': fcf_yield,
                'fiscal_year': fiscal_year,
                'date': latest_date.date()
            }

        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"{ticker} - yfinance FCF collection error: {e}")
            return None

    def collect_from_kis(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Collect FCF data from KIS API (Korea markets)

        TODO: Implement KIS API cash flow statement retrieval
        KIS API may not provide detailed cash flow statements.
        Consider using alternative data sources for KR market.
        """
        logger.warning(f"{ticker} - KIS API cash flow data not yet implemented")
        return None

    def update_fcf_data(self, ticker: str, region: str, fcf_data: Dict) -> bool:
        """Update ticker_fundamentals with FCF data"""
        try:
            cursor = self.conn.cursor()

            if self.dry_run:
                logger.info(f"[DRY-RUN] Would update {ticker} ({region}) with FCF data: {fcf_data}")
                cursor.close()
                return True

            # Check if record exists
            cursor.execute("""
                SELECT id FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s AND date = %s
            """, (ticker, region, fcf_data['date']))

            existing = cursor.fetchone()

            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE ticker_fundamentals
                    SET operating_cash_flow = %s,
                        capex = %s,
                        fcf = %s,
                        fcf_yield = %s
                    WHERE ticker = %s AND region = %s AND date = %s
                """, (
                    fcf_data['operating_cash_flow'],
                    fcf_data['capex'],
                    fcf_data['fcf'],
                    fcf_data['fcf_yield'],
                    ticker,
                    region,
                    fcf_data['date']
                ))
                logger.info(f"{ticker} - Updated FCF data for {fcf_data['date']}")
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO ticker_fundamentals
                    (ticker, region, date, operating_cash_flow, capex, fcf, fcf_yield, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'yfinance')
                """, (
                    ticker,
                    region,
                    fcf_data['date'],
                    fcf_data['operating_cash_flow'],
                    fcf_data['capex'],
                    fcf_data['fcf'],
                    fcf_data['fcf_yield']
                ))
                logger.info(f"{ticker} - Inserted new FCF data for {fcf_data['date']}")

            self.conn.commit()
            cursor.close()
            return True

        except Exception as e:
            logger.error(f"{ticker} - Database update error: {e}")
            self.conn.rollback()
            return False

    def process_ticker(self, ticker: str, region: str) -> bool:
        """Process single ticker for FCF data collection"""
        logger.info(f"Processing {ticker} ({region})...")

        # Try yfinance first (works for most global markets)
        fcf_data = self.collect_from_yfinance(ticker, region)

        if fcf_data:
            return self.update_fcf_data(ticker, region, fcf_data)
        else:
            logger.warning(f"{ticker} - No FCF data collected")
            return False

    def process_batch(self, tickers: List[Tuple[str, str]], batch_size: int = 100) -> Dict:
        """Process batch of tickers"""
        results = {
            'success': 0,
            'failed': 0,
            'skipped': 0
        }

        for i, (ticker, region) in enumerate(tickers, 1):
            logger.info(f"[{i}/{len(tickers)}] Processing {ticker} ({region})")

            if self.process_ticker(ticker, region):
                results['success'] += 1
            else:
                results['failed'] += 1

            # Rate limiting (1 request per second for yfinance)
            if i % batch_size == 0:
                logger.info(f"Processed {i} tickers. Pausing for rate limiting...")
                import time
                time.sleep(1)

        return results


def main():
    parser = argparse.ArgumentParser(description='Collect FCF data for tickers')
    parser.add_argument('--region', type=str, default='ALL',
                       help='Region to collect (KR, US, CN, HK, JP, VN, ALL)')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Comma-separated list of tickers (optional)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Batch size for rate limiting')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no database updates)')

    args = parser.parse_args()

    # Initialize database connection
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='quant_platform',
        user=os.getenv('USER'),
        password=None
    )

    collector = FCFDataCollector(conn, dry_run=args.dry_run)

    # Get tickers to process
    cursor = conn.cursor()

    if args.tickers:
        # Process specific tickers
        ticker_list = args.tickers.split(',')
        cursor.execute("""
            SELECT ticker, region FROM tickers
            WHERE ticker = ANY(%s)
        """, (ticker_list,))
    elif args.region == 'ALL':
        # Process all tickers
        cursor.execute("""
            SELECT ticker, region FROM tickers
            WHERE is_active = TRUE
            ORDER BY region, ticker
        """)
    else:
        # Process specific region
        cursor.execute("""
            SELECT ticker, region FROM tickers
            WHERE region = %s AND is_active = TRUE
            ORDER BY ticker
        """, (args.region,))

    tickers = cursor.fetchall()
    cursor.close()

    logger.info(f"Found {len(tickers)} tickers to process")

    if args.dry_run:
        logger.warning("DRY-RUN MODE: No database updates will be made")

    # Process tickers
    results = collector.process_batch(tickers, batch_size=args.batch_size)

    # Summary
    logger.info("=" * 60)
    logger.info("FCF Data Collection Summary")
    logger.info("=" * 60)
    logger.info(f"Total tickers: {len(tickers)}")
    logger.info(f"Successful: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Skipped: {results['skipped']}")
    logger.info("=" * 60)

    # Cleanup
    conn.close()


if __name__ == "__main__":
    main()
