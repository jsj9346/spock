#!/usr/bin/env python3
"""
Quality Factor Data Collection Script - Week 2 Task 3

Collects fundamental financial data for quality factors from yfinance.

Data Collected:
- Profitability: net_income, total_equity, total_assets, revenue, operating_profit
- Liquidity: current_assets, current_liabilities, inventory
- Leverage: total_liabilities
- Fiscal year

Usage:
    # Dry-run test
    python3 scripts/collect_quality_data.py --region US --tickers AAPL,MSFT,GOOGL --dry-run

    # Collect data
    python3 scripts/collect_quality_data.py --region US --tickers AAPL,MSFT,GOOGL

    # Batch collection
    python3 scripts/collect_quality_data.py --region US --batch-size 50

Author: Spock Quant Platform
Date: 2025-10-23
"""

import sys
import os
import argparse
from datetime import date
from typing import Dict, List, Optional
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


class QualityDataCollector:
    """
    Quality Factor Data Collector using yfinance API

    Features:
    - Collects balance sheet and income statement data
    - Rate limiting (2 req/sec)
    - Dry-run mode for testing
    """

    def __init__(self, conn, dry_run: bool = False, rate_limit: float = 0.5):
        """
        Initialize quality data collector

        Args:
            conn: psycopg2 connection object
            dry_run: If True, preview data without database writes
            rate_limit: Delay between API calls (seconds)
        """
        self.conn = conn
        self.dry_run = dry_run
        self.rate_limit = rate_limit
        self.last_api_call = time.time()

        # Statistics
        self.stats = {
            'processed': 0,
            'success': 0,
            'skipped': 0,
            'failed': 0,
            'api_calls': 0
        }

    def collect_from_yfinance(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Collect fundamental data from yfinance

        Args:
            ticker: Stock ticker symbol
            region: Market region (US, KR, JP, CN, HK, VN)

        Returns:
            Dict with fundamental data, or None if unavailable
        """
        try:
            import yfinance as yf

            # Rate limiting
            elapsed = time.time() - self.last_api_call
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)

            # Get ticker data
            stock = yf.Ticker(ticker)
            info = stock.info
            balance_sheet = stock.balance_sheet
            financials = stock.financials
            self.last_api_call = time.time()
            self.stats['api_calls'] += 1

            # Extract fundamental data (most recent fiscal year)
            fundamental_data = {
                'net_income': None,
                'total_equity': None,
                'total_assets': None,
                'revenue': None,
                'operating_profit': None,
                'current_assets': None,
                'current_liabilities': None,
                'inventory': None,
                'total_liabilities': None,
                'fiscal_year': None,
                'date': date.today(),
                'data_source': 'yfinance'
            }

            # Get fiscal year from most recent financial statement
            if not financials.empty:
                fiscal_year = int(financials.columns[0].year)
                fundamental_data['fiscal_year'] = fiscal_year

                # Income statement data
                if 'Net Income' in financials.index:
                    fundamental_data['net_income'] = float(financials.loc['Net Income'].iloc[0])
                if 'Total Revenue' in financials.index:
                    fundamental_data['revenue'] = float(financials.loc['Total Revenue'].iloc[0])
                if 'Operating Income' in financials.index:
                    fundamental_data['operating_profit'] = float(financials.loc['Operating Income'].iloc[0])

            # Balance sheet data
            if not balance_sheet.empty:
                if 'Total Assets' in balance_sheet.index:
                    fundamental_data['total_assets'] = float(balance_sheet.loc['Total Assets'].iloc[0])
                if 'Total Equity Gross Minority Interest' in balance_sheet.index:
                    fundamental_data['total_equity'] = float(balance_sheet.loc['Total Equity Gross Minority Interest'].iloc[0])
                if 'Current Assets' in balance_sheet.index:
                    fundamental_data['current_assets'] = float(balance_sheet.loc['Current Assets'].iloc[0])
                if 'Current Liabilities' in balance_sheet.index:
                    fundamental_data['current_liabilities'] = float(balance_sheet.loc['Current Liabilities'].iloc[0])
                if 'Inventory' in balance_sheet.index:
                    fundamental_data['inventory'] = float(balance_sheet.loc['Inventory'].iloc[0])
                if 'Total Liabilities Net Minority Interest' in balance_sheet.index:
                    fundamental_data['total_liabilities'] = float(balance_sheet.loc['Total Liabilities Net Minority Interest'].iloc[0])

            # Validate data
            if not any([fundamental_data['net_income'], fundamental_data['total_equity'], fundamental_data['total_assets']]):
                logger.debug(f"{ticker}: No fundamental data available")
                return None

            # Log collected data
            logger.info(
                f"{ticker}: Net Income ${fundamental_data['net_income']/1e9:.2f}B, "
                f"Total Equity ${fundamental_data['total_equity']/1e9:.2f}B, "
                f"FY{fundamental_data['fiscal_year']}"
            )

            return fundamental_data

        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"{ticker}: Error collecting fundamental data - {e}")
            return None

    def update_fundamental_data(self, ticker: str, region: str, fundamental_data: Dict) -> bool:
        """
        Update ticker_fundamentals with quality factor data

        Args:
            ticker: Stock ticker symbol
            region: Market region
            fundamental_data: Fundamental data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would update {ticker} with fundamental data")
                return True

            cursor = self.conn.cursor()

            # Insert or update record
            cursor.execute("""
                INSERT INTO ticker_fundamentals (
                    ticker, region, date, period_type, fiscal_year,
                    net_income, total_equity, total_assets, revenue, operating_profit,
                    current_assets, current_liabilities, inventory, total_liabilities,
                    data_source
                )
                VALUES (%s, %s, %s, 'ANNUAL', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, period_type)
                DO UPDATE SET
                    fiscal_year = EXCLUDED.fiscal_year,
                    net_income = COALESCE(EXCLUDED.net_income, ticker_fundamentals.net_income),
                    total_equity = COALESCE(EXCLUDED.total_equity, ticker_fundamentals.total_equity),
                    total_assets = COALESCE(EXCLUDED.total_assets, ticker_fundamentals.total_assets),
                    revenue = COALESCE(EXCLUDED.revenue, ticker_fundamentals.revenue),
                    operating_profit = COALESCE(EXCLUDED.operating_profit, ticker_fundamentals.operating_profit),
                    current_assets = COALESCE(EXCLUDED.current_assets, ticker_fundamentals.current_assets),
                    current_liabilities = COALESCE(EXCLUDED.current_liabilities, ticker_fundamentals.current_liabilities),
                    inventory = COALESCE(EXCLUDED.inventory, ticker_fundamentals.inventory),
                    total_liabilities = COALESCE(EXCLUDED.total_liabilities, ticker_fundamentals.total_liabilities),
                    data_source = EXCLUDED.data_source
            """, (
                ticker, region, fundamental_data['date'], fundamental_data.get('fiscal_year'),
                fundamental_data.get('net_income'),
                fundamental_data.get('total_equity'),
                fundamental_data.get('total_assets'),
                fundamental_data.get('revenue'),
                fundamental_data.get('operating_profit'),
                fundamental_data.get('current_assets'),
                fundamental_data.get('current_liabilities'),
                fundamental_data.get('inventory'),
                fundamental_data.get('total_liabilities'),
                fundamental_data['data_source']
            ))

            self.conn.commit()
            cursor.close()

            logger.success(f"{ticker}: Updated fundamental data (FY{fundamental_data.get('fiscal_year')})")
            return True

        except Exception as e:
            logger.error(f"{ticker}: Error updating database - {e}")
            self.conn.rollback()
            return False

    def process_ticker(self, ticker: str, region: str) -> bool:
        """
        Process a single ticker

        Args:
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            True if successful, False otherwise
        """
        self.stats['processed'] += 1

        # Collect fundamental data
        fundamental_data = self.collect_from_yfinance(ticker, region)

        if fundamental_data is None:
            self.stats['skipped'] += 1
            return False

        # Update database
        success = self.update_fundamental_data(ticker, region, fundamental_data)

        if success:
            self.stats['success'] += 1
        else:
            self.stats['failed'] += 1

        return success

    def process_batch(self, tickers: List[str], region: str):
        """
        Process a batch of tickers

        Args:
            tickers: List of ticker symbols
            region: Market region
        """
        logger.info(f"Processing {len(tickers)} tickers for region {region}")

        for ticker in tickers:
            self.process_ticker(ticker, region)

        # Print summary
        logger.info("=" * 60)
        logger.info("Quality Factor Data Collection Summary")
        logger.info("=" * 60)
        logger.info(f"Total tickers: {self.stats['processed']}")
        logger.info(f"Successful: {self.stats['success']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"API calls: {self.stats['api_calls']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Collect quality factor data from yfinance')
    parser.add_argument('--region', type=str, default='US', help='Market region (US, KR, JP, CN, HK, VN)')
    parser.add_argument('--tickers', type=str, help='Comma-separated ticker list (e.g., AAPL,MSFT,GOOGL)')
    parser.add_argument('--batch-size', type=int, help='Batch size for database query')
    parser.add_argument('--dry-run', action='store_true', help='Preview data without database writes')
    parser.add_argument('--rate-limit', type=float, default=0.5, help='Delay between API calls (seconds)')

    args = parser.parse_args()

    # Connect to database
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='quant_platform',
            user=os.getenv('USER'),
            password=None
        )
        logger.info("Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return 1

    # Create collector
    collector = QualityDataCollector(conn, dry_run=args.dry_run, rate_limit=args.rate_limit)

    # Get tickers
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]
    elif args.batch_size:
        # Query database for tickers
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker FROM tickers
            WHERE region = %s
            ORDER BY ticker
            LIMIT %s
        """, (args.region, args.batch_size))
        tickers = [row[0] for row in cursor.fetchall()]
        cursor.close()
    else:
        logger.error("Must specify either --tickers or --batch-size")
        return 1

    # Process tickers
    collector.process_batch(tickers, args.region)

    # Cleanup
    conn.close()
    logger.info("Database connection closed")

    return 0


if __name__ == '__main__':
    sys.exit(main())
