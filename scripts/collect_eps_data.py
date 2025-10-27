#!/usr/bin/env python3
"""
EPS Data Collection Script - Week 2 Earnings Momentum Factor

Collects Earnings Per Share (EPS) data from yfinance for ticker_fundamentals table.

Data Collected:
- Trailing EPS (actual reported earnings)
- Forward EPS (analyst estimates)
- EPS Growth YoY (calculated)
- Earnings Momentum (calculated)

Usage:
    # Dry-run test
    python3 scripts/collect_eps_data.py --region US --tickers AAPL,MSFT,GOOGL --dry-run

    # Collect data
    python3 scripts/collect_eps_data.py --region US --tickers AAPL,MSFT,GOOGL

    # Batch collection for all US stocks
    python3 scripts/collect_eps_data.py --region US --batch-size 50

Author: Quant Platform Development Team
Date: 2025-10-23
"""

import sys
import os
import argparse
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
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


class EPSDataCollector:
    """
    EPS Data Collector using yfinance API

    Features:
    - Collects Trailing EPS and Forward EPS
    - Calculates YoY EPS Growth
    - Calculates Earnings Momentum score
    - Rate limiting (2 req/sec)
    - Dry-run mode for testing
    """

    def __init__(self, conn, dry_run: bool = False, rate_limit: float = 0.5):
        """
        Initialize EPS data collector

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
        Collect EPS data from yfinance

        Args:
            ticker: Stock ticker symbol
            region: Market region (US, KR, JP, CN, HK, VN)

        Returns:
            Dict with EPS data, or None if unavailable
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
            self.last_api_call = time.time()
            self.stats['api_calls'] += 1

            # Extract EPS data
            trailing_eps = info.get('trailingEps')
            forward_eps = info.get('forwardEps')

            # Validate data
            if trailing_eps is None and forward_eps is None:
                logger.debug(f"{ticker}: No EPS data available")
                return None

            # Get market cap for additional validation
            market_cap = info.get('marketCap')
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')

            # Build result dictionary
            eps_data = {
                'trailing_eps': float(trailing_eps) if trailing_eps else None,
                'forward_eps': float(forward_eps) if forward_eps else None,
                'market_cap': int(market_cap) if market_cap else None,
                'close_price': float(current_price) if current_price else None,
                'date': date.today(),
                'data_source': 'yfinance'
            }

            # Log collected data
            trailing_str = f"${trailing_eps:.2f}" if trailing_eps else "N/A"
            forward_str = f"${forward_eps:.2f}" if forward_eps else "N/A"
            logger.info(
                f"{ticker}: Trailing EPS {trailing_str}, Forward EPS {forward_str}"
            )

            return eps_data

        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"{ticker}: Error collecting EPS data - {e}")
            return None

    def calculate_eps_metrics(self, ticker: str, region: str, current_eps: float) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate EPS Growth YoY and Earnings Momentum

        Args:
            ticker: Stock ticker symbol
            region: Market region
            current_eps: Current trailing EPS

        Returns:
            Tuple of (eps_growth_yoy, earnings_momentum) or (None, None)
        """
        try:
            cursor = self.conn.cursor()

            # Get historical EPS data (last 2 years)
            cursor.execute("""
                SELECT date, trailing_eps
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND trailing_eps IS NOT NULL
                ORDER BY date DESC
                LIMIT 4
            """, (ticker, region))

            historical = cursor.fetchall()
            cursor.close()

            if len(historical) < 1:
                # No historical data, can't calculate growth
                return None, None

            # Calculate YoY growth (current vs 1 year ago)
            if len(historical) >= 1:
                prior_eps = float(historical[0][1])  # Most recent historical EPS

                if prior_eps != 0:
                    eps_growth_yoy = float(((current_eps - prior_eps) / abs(prior_eps)) * 100)
                    # Cap extreme values
                    eps_growth_yoy = max(-200.0, min(500.0, eps_growth_yoy))
                else:
                    eps_growth_yoy = 100.0 if current_eps > 0 else -100.0
            else:
                eps_growth_yoy = None

            # Calculate Earnings Momentum (requires 4 data points)
            if len(historical) >= 3:
                eps_series = [current_eps] + [float(row[1]) for row in historical[:3]]

                # Recent growth rate
                if eps_series[1] != 0:
                    recent_growth = ((eps_series[0] / eps_series[1]) - 1) * 100
                else:
                    recent_growth = 0.0

                # Prior growth rate
                if eps_series[2] != 0:
                    prior_growth = ((eps_series[1] / eps_series[2]) - 1) * 100
                else:
                    prior_growth = 0.0

                # Acceleration
                acceleration = recent_growth - prior_growth
                acceleration = max(-100.0, min(100.0, acceleration))

                # Earnings momentum = 70% growth + 30% acceleration
                earnings_momentum = float(eps_growth_yoy * 0.7 + acceleration * 0.3)
            else:
                earnings_momentum = eps_growth_yoy  # Use growth rate only

            return eps_growth_yoy, earnings_momentum

        except Exception as e:
            logger.error(f"{ticker}: Error calculating EPS metrics - {e}")
            return None, None

    def update_eps_data(self, ticker: str, region: str, eps_data: Dict) -> bool:
        """
        Update ticker_fundamentals with EPS data

        Args:
            ticker: Stock ticker symbol
            region: Market region
            eps_data: EPS data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would update {ticker} with EPS data")
                return True

            cursor = self.conn.cursor()

            # Calculate EPS metrics if trailing_eps is available
            eps_growth_yoy = None
            earnings_momentum = None

            if eps_data.get('trailing_eps'):
                eps_growth_yoy, earnings_momentum = self.calculate_eps_metrics(
                    ticker, region, eps_data['trailing_eps']
                )

            # Insert or update record
            cursor.execute("""
                INSERT INTO ticker_fundamentals (
                    ticker, region, date, period_type,
                    trailing_eps, forward_eps, eps_growth_yoy, earnings_momentum,
                    market_cap, close_price, data_source
                )
                VALUES (%s, %s, %s, 'DAILY', %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, period_type)
                DO UPDATE SET
                    trailing_eps = EXCLUDED.trailing_eps,
                    forward_eps = EXCLUDED.forward_eps,
                    eps_growth_yoy = EXCLUDED.eps_growth_yoy,
                    earnings_momentum = EXCLUDED.earnings_momentum,
                    market_cap = COALESCE(EXCLUDED.market_cap, ticker_fundamentals.market_cap),
                    close_price = COALESCE(EXCLUDED.close_price, ticker_fundamentals.close_price),
                    data_source = EXCLUDED.data_source
            """, (
                ticker, region, eps_data['date'],
                eps_data.get('trailing_eps'),
                eps_data.get('forward_eps'),
                eps_growth_yoy,
                earnings_momentum,
                eps_data.get('market_cap'),
                eps_data.get('close_price'),
                eps_data['data_source']
            ))

            self.conn.commit()
            cursor.close()

            growth_str = f"{eps_growth_yoy:.2f}%" if eps_growth_yoy is not None else "N/A"
            momentum_str = f"{earnings_momentum:.2f}" if earnings_momentum is not None else "N/A"
            logger.success(
                f"{ticker}: Updated EPS data (Growth: {growth_str}, Momentum: {momentum_str})"
            )

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

        # Collect EPS data
        eps_data = self.collect_from_yfinance(ticker, region)

        if eps_data is None:
            self.stats['skipped'] += 1
            return False

        # Update database
        success = self.update_eps_data(ticker, region, eps_data)

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
        logger.info("EPS Data Collection Summary")
        logger.info("=" * 60)
        logger.info(f"Total tickers: {self.stats['processed']}")
        logger.info(f"Successful: {self.stats['success']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"API calls: {self.stats['api_calls']}")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Collect EPS data from yfinance')
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
    collector = EPSDataCollector(conn, dry_run=args.dry_run, rate_limit=args.rate_limit)

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
