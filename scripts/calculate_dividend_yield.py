#!/usr/bin/env python3
"""
Calculate Dividend Yield Factor for Korean Stocks

This script calculates Dividend Yield factor using pykrx DAILY data:
- Formula: (Latest DPS / Latest Stock Price) × 100
- User Requirement: "가장 최근 지급한 주당 배당금과 가장 최근 수집한 주가를 기준으로 배당수익률이 계산"

Usage:
    # Calculate for all tickers
    python3 scripts/calculate_dividend_yield.py

    # Calculate for specific tickers
    python3 scripts/calculate_dividend_yield.py --tickers 005930 000660

    # Dry run (preview only)
    python3 scripts/calculate_dividend_yield.py --dry-run

    # Background execution with logging
    nohup python3 scripts/calculate_dividend_yield.py > logs/dividend_yield_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    tail -f logs/dividend_yield_*.log

Author: Quant Investment Platform - Option B Implementation
"""

import sys
import os
import argparse
from datetime import datetime, date
from typing import Optional, List, Dict
from decimal import Decimal
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_calculate_dividend_yield.log"
os.makedirs('logs', exist_ok=True)

logger.add(
    log_filename,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)


class DividendYieldCalculator:
    """
    Calculate Dividend Yield factor using Option B data merge approach.

    Query Pattern:
        - Dividend data: WHERE period_type='DAILY' AND data_source='pykrx'
        - Stock prices: FROM ohlcv_data
    """

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        """
        Initialize calculator

        Args:
            db: PostgreSQL database manager
            dry_run: If True, preview calculations without database writes
        """
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_no_dividend': 0,
            'tickers_no_price': 0,
            'tickers_anomaly': 0,
            'tickers_failed': 0
        }

    def get_tickers_with_dividend_data(self, ticker_list: Optional[List[str]] = None) -> List[str]:
        """
        Get list of tickers with dividend data available

        Args:
            ticker_list: Optional list of specific tickers to filter

        Returns:
            List of tickers with dividend data
        """
        query = """
        SELECT DISTINCT f.ticker
        FROM ticker_fundamentals f
        WHERE f.region = 'KR'
          AND f.period_type = 'DAILY'
          AND f.data_source = 'pykrx'
          AND f.dividend_per_share IS NOT NULL
          AND f.dividend_per_share > 0
        """

        if ticker_list:
            placeholders = ','.join(['%s'] * len(ticker_list))
            query += f" AND f.ticker IN ({placeholders})"
            results = self.db.execute_query(query, tuple(ticker_list))
        else:
            results = self.db.execute_query(query)

        tickers = [row['ticker'] for row in results]

        logger.info(f"📊 Found {len(tickers)} tickers with dividend data")
        return tickers

    def calculate_dividend_yield_for_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Calculate Dividend Yield factor for a single ticker

        Args:
            ticker: Stock ticker code

        Returns:
            {
                'ticker': str,
                'dividend_yield': float,  # Percentage
                'dividend_per_share': float,
                'close_price': float,
                'dps_date': date,
                'price_date': date,
                'metadata': dict
            }
            None if calculation fails
        """

        # Step 1: Get latest dividend per share from pykrx (DAILY data)
        query_dps = """
        SELECT
            dividend_per_share,
            dividend_yield as pykrx_dividend_yield,
            date as dps_date
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
          AND dividend_per_share IS NOT NULL
          AND dividend_per_share > 0
        ORDER BY date DESC
        LIMIT 1
        """

        dps_result = self.db.execute_query(query_dps, (ticker,))

        if not dps_result:
            logger.debug(f"{ticker}: No dividend data found")
            self.stats['tickers_no_dividend'] += 1
            return None

        dividend_per_share = float(dps_result[0]['dividend_per_share'])
        pykrx_dividend_yield = float(dps_result[0]['pykrx_dividend_yield']) if dps_result[0]['pykrx_dividend_yield'] else None
        dps_date = dps_result[0]['dps_date']

        # Step 2: Get latest stock price from OHLCV
        query_price = """
        SELECT
            close,
            date as price_date
        FROM ohlcv_data
        WHERE ticker = %s
          AND region = 'KR'
          AND close > 0
        ORDER BY date DESC
        LIMIT 1
        """

        price_result = self.db.execute_query(query_price, (ticker,))

        if not price_result:
            logger.warning(f"{ticker}: No price data found")
            self.stats['tickers_no_price'] += 1
            return None

        close_price = float(price_result[0]['close'])
        price_date = price_result[0]['price_date']

        # Step 3: Calculate dividend yield (user requirement: latest DPS / latest price)
        dividend_yield = (dividend_per_share / close_price) * 100

        # Data quality validation
        is_anomaly = False
        if dividend_yield > 20:
            logger.warning(f"{ticker}: Unusually high dividend yield {dividend_yield:.2f}% (review recommended)")
            self.stats['tickers_anomaly'] += 1
            is_anomaly = True

        # Calculate date difference
        date_diff_days = (price_date - dps_date).days

        # Metadata for logging and debugging
        metadata = {
            'dividend_per_share': dividend_per_share,
            'close_price': close_price,
            'dps_date': str(dps_date),
            'price_date': str(price_date),
            'date_diff_days': date_diff_days,
            'pykrx_dividend_yield': pykrx_dividend_yield,
            'calculated_dividend_yield': dividend_yield,
            'is_anomaly': is_anomaly
        }

        logger.info(
            f"{ticker}: Dividend Yield = {dividend_yield:.2f}% | "
            f"DPS={dividend_per_share} | "
            f"Price={close_price} | "
            f"Date diff={date_diff_days} days"
        )

        return {
            'ticker': ticker,
            'dividend_yield': dividend_yield,
            'dividend_per_share': dividend_per_share,
            'close_price': close_price,
            'dps_date': dps_date,
            'price_date': price_date,
            'metadata': metadata
        }

    def calculate_all_tickers(self, ticker_list: Optional[List[str]] = None) -> List[Dict]:
        """
        Calculate Dividend Yield for all tickers with dividend data

        Args:
            ticker_list: Optional list of specific tickers

        Returns:
            List of calculation results
        """
        logger.info("=== Dividend Yield Factor Calculation ===\n")

        # Get tickers with dividend data
        tickers = self.get_tickers_with_dividend_data(ticker_list)

        if not tickers:
            logger.error("❌ No tickers with dividend data found!")
            return []

        # Calculate for each ticker
        results = []

        for idx, ticker in enumerate(tickers, 1):
            if idx % 100 == 0:
                logger.info(f"   Progress: {idx}/{len(tickers)} tickers processed...")

            try:
                self.stats['tickers_processed'] += 1
                result = self.calculate_dividend_yield_for_ticker(ticker)

                if result:
                    results.append(result)
                    self.stats['tickers_success'] += 1

            except Exception as e:
                logger.error(f"❌ {ticker}: Calculation failed: {e}")
                self.stats['tickers_failed'] += 1

        logger.info(f"\n✅ Calculation complete: {len(results)}/{len(tickers)} tickers")

        return results

    def save_factor_scores(self, results: List[Dict]) -> None:
        """
        Save factor scores to factor_scores table

        Args:
            results: List of calculation results
        """
        if not results:
            logger.warning("No factor scores to save")
            return

        if self.dry_run:
            logger.info("[DRY RUN] Would save factor scores to database")
            self._display_top_scores(results)
            return

        logger.info(f"\n💾 Saving {len(results)} factor scores to database...")

        # Convert to DataFrame for percentile calculation
        import pandas as pd
        df = pd.DataFrame(results)

        # Calculate percentile (0-100, higher dividend yield = higher score)
        df['raw_score'] = df['dividend_yield']
        df['percentile'] = df['raw_score'].rank(pct=True) * 100

        # Prepare records for insertion
        target_date = date.today()
        records = []

        for _, row in df.iterrows():
            records.append((
                row['ticker'],
                'KR',
                target_date,
                'Dividend_Yield',
                float(row['raw_score']),
                float(row['percentile'])
            ))

        # Batch insert
        query = """
        INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, factor_name)
        DO UPDATE SET
            score = EXCLUDED.score,
            percentile = EXCLUDED.percentile
        """

        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(query, records)
                    conn.commit()

            logger.info(f"✅ Saved {len(records)} factor scores")

            # Display top scores
            self._display_top_scores(results)

        except Exception as e:
            logger.error(f"❌ Failed to save factor scores: {e}")
            raise

    def _display_top_scores(self, results: List[Dict]) -> None:
        """Display top 20 high-yield stocks"""

        import pandas as pd

        df = pd.DataFrame(results)
        df['raw_score'] = df['dividend_yield']
        df['percentile'] = df['raw_score'].rank(pct=True) * 100
        df = df.sort_values('dividend_yield', ascending=False)

        # Get ticker names
        query = "SELECT ticker, name FROM tickers WHERE region = 'KR'"
        ticker_names_result = self.db.execute_query(query)
        ticker_names = {row['ticker']: row['name'] for row in ticker_names_result}

        df['name'] = df['ticker'].map(ticker_names)

        logger.info("\n🏆 Top 20 High-Yield Stocks (Dividend Yield)...")
        logger.info("=" * 100)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'Dividend Yield':<16}{'DPS':<12}{'Price':<12}{'Score':<8}")
        logger.info("=" * 100)

        for idx, (_, row) in enumerate(df.head(20).iterrows(), 1):
            name_str = str(row['name']) if pd.notna(row['name']) else 'N/A'
            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{name_str[:28]:<30}"
                f"{row['dividend_yield']:.2f}%{'':<11}"
                f"{row['dividend_per_share']:<12.0f}"
                f"{row['close_price']:<12.0f}"
                f"{row['percentile']:<8.1f}"
            )

    def print_statistics(self) -> None:
        """Print calculation statistics"""

        logger.info("\n" + "=" * 60)
        logger.info("Dividend Yield Factor Calculation Summary")
        logger.info("=" * 60)
        logger.info(f"Tickers processed: {self.stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']}")
        logger.info(f"  ⚠️ No dividend data: {self.stats['tickers_no_dividend']}")
        logger.info(f"  ⚠️ No price data: {self.stats['tickers_no_price']}")
        logger.info(f"  ⚠️ Anomalies detected: {self.stats['tickers_anomaly']}")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']}")
        logger.info("=" * 60)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Calculate Dividend Yield factor for Korean stocks')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to calculate (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Preview calculations without database writes')

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager()

    # Initialize calculator
    calculator = DividendYieldCalculator(db, dry_run=args.dry_run)

    # Calculate factors
    results = calculator.calculate_all_tickers(ticker_list=args.tickers)

    # Save to database
    calculator.save_factor_scores(results)

    # Print statistics
    calculator.print_statistics()

    logger.info("\n✅ Dividend Yield factor calculation complete!")


if __name__ == "__main__":
    main()
