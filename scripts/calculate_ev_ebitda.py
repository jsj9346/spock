#!/usr/bin/env python3
"""
Calculate EV/EBITDA Factor for Korean Stocks

This script calculates EV/EBITDA factor using DART annual financial data:
- Formula: EV/EBITDA where EV = Market Cap + Total Debt - Cash
- Data Source: DART API (period_type='ANNUAL', data_source='DART')
- User Requirement: Latest annual EBITDA from DART combined with latest stock price

Usage:
    # Calculate for all tickers with DART data
    python3 scripts/calculate_ev_ebitda.py

    # Calculate for specific tickers
    python3 scripts/calculate_ev_ebitda.py --tickers 005930 000660

    # Dry run (preview only)
    python3 scripts/calculate_ev_ebitda.py --dry-run

    # Background execution with logging
    nohup python3 scripts/calculate_ev_ebitda.py > logs/ev_ebitda_$(date +%Y%m%d_%H%M%S).log 2>&1 &
    tail -f logs/ev_ebitda_*.log

Author: Quant Investment Platform - Option B Implementation
"""

import sys
import os
import argparse
from datetime import datetime, date
from typing import Optional, List, Dict
from decimal import Decimal
from loguru import logger
import numpy as np
from pykrx import stock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}_calculate_ev_ebitda.log"
os.makedirs('logs', exist_ok=True)

logger.add(
    log_filename,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)


class EVEBITDACalculator:
    """
    Calculate EV/EBITDA factor using Option B data merge approach.

    Query Pattern:
        - Financial data: WHERE period_type='ANNUAL' AND data_source='DART'
        - Stock prices: FROM ohlcv_data

    Formula:
        EV = Market Cap + Total Debt - Cash
        EV/EBITDA = EV / EBITDA

    Note: Cash approximated using current_assets (DART limitation)
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
            'tickers_no_dart_data': 0,
            'tickers_no_price': 0,
            'tickers_negative_ev': 0,
            'tickers_anomaly': 0,
            'tickers_failed': 0
        }

    def get_tickers_with_dart_data(self, ticker_list: Optional[List[str]] = None) -> List[str]:
        """
        Get list of tickers with DART financial data available

        Note: Accepts both ANNUAL and SEMI-ANNUAL data (DART provides SEMI-ANNUAL)

        Args:
            ticker_list: Optional list of specific tickers to filter

        Returns:
            List of tickers with DART data (ANNUAL or SEMI-ANNUAL)
        """
        query = """
        SELECT DISTINCT f.ticker
        FROM ticker_fundamentals f
        WHERE f.region = 'KR'
          AND f.period_type IN ('ANNUAL', 'SEMI-ANNUAL')
          AND f.data_source = 'DART'
          AND f.ebitda IS NOT NULL
          AND f.ebitda > 0
          AND f.total_liabilities IS NOT NULL
        """

        if ticker_list:
            placeholders = ','.join(['%s'] * len(ticker_list))
            query += f" AND f.ticker IN ({placeholders})"
            results = self.db.execute_query(query, tuple(ticker_list))
        else:
            results = self.db.execute_query(query)

        tickers = [row['ticker'] for row in results]

        logger.info(f"📊 Found {len(tickers)} tickers with DART annual data")
        return tickers

    def calculate_ev_ebitda_for_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Calculate EV/EBITDA factor for a single ticker

        Args:
            ticker: Stock ticker code

        Returns:
            {
                'ticker': str,
                'ev_to_ebitda': float,
                'enterprise_value': float,
                'ebitda': float,
                'market_cap': float,
                'total_liabilities': float,
                'cash_approximation': float,
                'shares_outstanding': float,
                'close_price': float,
                'fiscal_year': int,
                'financial_date': date,
                'price_date': date,
                'metadata': dict
            }
            None if calculation fails
        """

        # Step 1: Get latest DART financial data (ANNUAL or SEMI-ANNUAL)
        # Note: DART provides SEMI-ANNUAL data, prefer most recent
        # shares_outstanding is obtained from pykrx (Step 2.5)
        query_dart = """
        SELECT
            ebitda,
            total_liabilities,
            current_assets,
            fiscal_year,
            date as financial_date,
            operating_profit,
            depreciation,
            revenue,
            period_type
        FROM ticker_fundamentals
        WHERE ticker = %s
          AND region = 'KR'
          AND period_type IN ('ANNUAL', 'SEMI-ANNUAL')
          AND data_source = 'DART'
          AND ebitda IS NOT NULL
          AND ebitda > 0
          AND total_liabilities IS NOT NULL
        ORDER BY fiscal_year DESC, date DESC
        LIMIT 1
        """

        dart_result = self.db.execute_query(query_dart, (ticker,))

        if not dart_result:
            logger.debug(f"{ticker}: No DART annual data found")
            self.stats['tickers_no_dart_data'] += 1
            return None

        ebitda = float(dart_result[0]['ebitda'])
        total_liabilities = float(dart_result[0]['total_liabilities'])
        current_assets = float(dart_result[0]['current_assets'] or 0)
        fiscal_year = dart_result[0]['fiscal_year']
        financial_date = dart_result[0]['financial_date']

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

        # Step 2.5: Get shares outstanding from pykrx
        # Note: DART doesn't provide shares_outstanding, so we get it from pykrx
        try:
            date_str = price_date.strftime('%Y%m%d')
            df_cap = stock.get_market_cap(date_str, date_str, ticker)

            if df_cap.empty:
                logger.warning(f"{ticker}: No market cap data from pykrx for {date_str}")
                self.stats['tickers_no_price'] += 1
                return None

            shares_outstanding = float(df_cap.iloc[0]['상장주식수'])

            if shares_outstanding <= 0:
                logger.warning(f"{ticker}: Invalid shares_outstanding {shares_outstanding}")
                self.stats['tickers_no_price'] += 1
                return None

            logger.debug(f"{ticker}: Shares outstanding = {shares_outstanding:,.0f} from pykrx")

        except Exception as e:
            logger.error(f"{ticker}: Failed to get shares_outstanding from pykrx: {e}")
            self.stats['tickers_failed'] += 1
            return None

        # Step 3: Calculate Enterprise Value
        # EV = Market Cap + Total Debt - Cash
        # Note: Using current_assets as cash proxy (DART limitation)
        market_cap = close_price * shares_outstanding
        cash_equivalents = current_assets  # Approximation
        enterprise_value = market_cap + total_liabilities - cash_equivalents

        # Step 4: Calculate EV/EBITDA
        ev_to_ebitda = enterprise_value / ebitda

        # Data quality validation
        is_anomaly = False

        # Filter negative EV (cash > market_cap + debt)
        if ev_to_ebitda < 0:
            logger.warning(f"{ticker}: Negative EV/EBITDA {ev_to_ebitda:.2f} (EV={enterprise_value:,.0f})")
            self.stats['tickers_negative_ev'] += 1
            return None

        # Flag unusually high EV/EBITDA
        if ev_to_ebitda > 100:
            logger.warning(f"{ticker}: Unusually high EV/EBITDA {ev_to_ebitda:.2f} (review recommended)")
            self.stats['tickers_anomaly'] += 1
            is_anomaly = True

        # Calculate date difference
        date_diff_days = (price_date - financial_date).days

        # Metadata for logging and debugging
        metadata = {
            'ebitda': ebitda,
            'total_liabilities': total_liabilities,
            'current_assets': current_assets,
            'shares_outstanding': shares_outstanding,
            'market_cap': market_cap,
            'cash_approximation': cash_equivalents,
            'enterprise_value': enterprise_value,
            'close_price': close_price,
            'fiscal_year': fiscal_year,
            'financial_date': str(financial_date),
            'price_date': str(price_date),
            'date_diff_days': date_diff_days,
            'ev_to_ebitda': ev_to_ebitda,
            'is_anomaly': is_anomaly,
            'note': 'Cash approximated using current_assets (DART limitation)'
        }

        logger.info(
            f"{ticker}: EV/EBITDA = {ev_to_ebitda:.2f} | "
            f"EV={enterprise_value/1e9:.1f}B | "
            f"EBITDA={ebitda/1e9:.1f}B | "
            f"FY={fiscal_year} | "
            f"Date diff={date_diff_days} days"
        )

        return {
            'ticker': ticker,
            'ev_to_ebitda': ev_to_ebitda,
            'enterprise_value': enterprise_value,
            'ebitda': ebitda,
            'market_cap': market_cap,
            'total_liabilities': total_liabilities,
            'cash_approximation': cash_equivalents,
            'shares_outstanding': shares_outstanding,
            'close_price': close_price,
            'fiscal_year': fiscal_year,
            'financial_date': financial_date,
            'price_date': price_date,
            'metadata': metadata
        }

    def calculate_all_tickers(self, ticker_list: Optional[List[str]] = None) -> List[Dict]:
        """
        Calculate EV/EBITDA for all tickers with DART annual data

        Args:
            ticker_list: Optional list of specific tickers

        Returns:
            List of calculation results
        """
        logger.info("=== EV/EBITDA Factor Calculation ===\n")

        # Get tickers with DART annual data
        tickers = self.get_tickers_with_dart_data(ticker_list)

        if not tickers:
            logger.error("❌ No tickers with DART annual data found!")
            return []

        # Calculate for each ticker
        results = []

        for idx, ticker in enumerate(tickers, 1):
            if idx % 20 == 0:
                logger.info(f"   Progress: {idx}/{len(tickers)} tickers processed...")

            try:
                self.stats['tickers_processed'] += 1
                result = self.calculate_ev_ebitda_for_ticker(ticker)

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

        # Calculate percentile (0-100, LOWER EV/EBITDA = HIGHER score for value)
        # Use -log transformation to invert ranking
        df['raw_score'] = -np.log(df['ev_to_ebitda'])
        df['percentile'] = df['raw_score'].rank(pct=True) * 100

        # Prepare records for insertion
        target_date = date.today()
        records = []

        for _, row in df.iterrows():
            records.append((
                row['ticker'],
                'KR',
                target_date,
                'EV_EBITDA',
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
        """Display top 20 value stocks (lowest EV/EBITDA)"""

        import pandas as pd

        df = pd.DataFrame(results)

        # Calculate scores
        df['raw_score'] = -np.log(df['ev_to_ebitda'])
        df['percentile'] = df['raw_score'].rank(pct=True) * 100

        # Sort by EV/EBITDA ascending (lower = better value)
        df = df.sort_values('ev_to_ebitda', ascending=True)

        # Get ticker names
        query = "SELECT ticker, name FROM tickers WHERE region = 'KR'"
        ticker_names_result = self.db.execute_query(query)
        ticker_names = {row['ticker']: row['name'] for row in ticker_names_result}

        df['name'] = df['ticker'].map(ticker_names)

        logger.info("\n🏆 Top 20 Value Stocks (Lowest EV/EBITDA)...")
        logger.info("=" * 120)
        logger.info(f"{'Rank':<6}{'Ticker':<8}{'Name':<30}{'EV/EBITDA':<12}{'EV (억원)':<15}{'EBITDA (억원)':<15}{'FY':<6}{'Score':<8}")
        logger.info("=" * 120)

        for idx, (_, row) in enumerate(df.head(20).iterrows(), 1):
            name_str = str(row['name']) if pd.notna(row['name']) else 'N/A'
            ev_str = f"{row['enterprise_value']/1e8:,.0f}"
            ebitda_str = f"{row['ebitda']/1e8:,.0f}"

            logger.info(
                f"{idx:<6}"
                f"{row['ticker']:<8}"
                f"{name_str[:28]:<30}"
                f"{row['ev_to_ebitda']:<12.2f}"
                f"{ev_str:<15}"
                f"{ebitda_str:<15}"
                f"{row['fiscal_year']:<6}"
                f"{row['percentile']:<8.1f}"
            )

    def print_statistics(self) -> None:
        """Print calculation statistics"""

        logger.info("\n" + "=" * 60)
        logger.info("EV/EBITDA Factor Calculation Summary")
        logger.info("=" * 60)
        logger.info(f"Tickers processed: {self.stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']}")
        logger.info(f"  ⚠️ No DART data: {self.stats['tickers_no_dart_data']}")
        logger.info(f"  ⚠️ No price data: {self.stats['tickers_no_price']}")
        logger.info(f"  ⚠️ Negative EV: {self.stats['tickers_negative_ev']}")
        logger.info(f"  ⚠️ Anomalies detected (>100): {self.stats['tickers_anomaly']}")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']}")
        logger.info("=" * 60)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Calculate EV/EBITDA factor for Korean stocks')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to calculate (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Preview calculations without database writes')

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager()

    # Initialize calculator
    calculator = EVEBITDACalculator(db, dry_run=args.dry_run)

    # Calculate factors
    results = calculator.calculate_all_tickers(ticker_list=args.tickers)

    # Save to database
    calculator.save_factor_scores(results)

    # Print statistics
    calculator.print_statistics()

    logger.info("\n✅ EV/EBITDA factor calculation complete!")


if __name__ == "__main__":
    main()
