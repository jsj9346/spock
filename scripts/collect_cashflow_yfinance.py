#!/usr/bin/env python3
"""
Cash Flow Data Collector using yfinance

Collects cash flow statement data (OCF, FCF, CapEx) for Korean stocks
using yfinance API as an alternative to DART API parsing.

Note: yfinance provides cash flow data with some delay (typically quarterly)
and may have gaps for smaller Korean companies.

Usage:
    python scripts/collect_cashflow_yfinance.py [--ticker 005930] [--limit 100]

Author: Quant Platform Development Team
Date: 2024-12-01
"""

import os
import sys
import argparse
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import yfinance as yf
from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


class CashFlowCollector:
    """
    Cash flow data collector using yfinance.

    Collects:
    - Operating Cash Flow (OCF)
    - Capital Expenditure (CapEx)
    - Free Cash Flow (FCF = OCF - CapEx)
    - Cash and Cash Equivalents (from balance sheet)
    """

    # yfinance cash flow field mapping
    CASHFLOW_FIELDS = {
        'Operating Cash Flow': 'operating_cash_flow',
        'Capital Expenditure': 'capex',
        'Free Cash Flow': 'fcf',
        'Investing Cash Flow': 'investing_cf',
        'Financing Cash Flow': 'financing_cf',
    }

    # Balance sheet fields for cash
    BALANCE_FIELDS = {
        'Cash And Cash Equivalents': 'cash_and_equivalents',
        'Cash Cash Equivalents And Short Term Investments': 'cash_and_equivalents',
        'Other Short Term Investments': 'short_term_investments',
    }

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager

    def get_yf_ticker_symbol(self, ticker: str, region: str) -> str:
        """Convert ticker to yfinance format."""
        if region == 'KR':
            # Korean stocks: add .KS (KOSPI) or .KQ (KOSDAQ)
            # Try KOSPI first
            return f"{ticker}.KS"
        elif region == 'US':
            # US preferred stocks/classes: DB uses '/' but yfinance uses '.'
            # e.g., BRK/B → BRK.B, MS/A → MS.A
            return ticker.replace('/', '-') if '/' in ticker else ticker
        else:
            return ticker

    def collect_cashflow(
        self,
        ticker: str,
        region: str = 'KR'
    ) -> Dict:
        """
        Collect cash flow data for a single ticker.

        Args:
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            Dict with cash flow data or empty dict on failure
        """
        yf_symbol = self.get_yf_ticker_symbol(ticker, region)

        try:
            stock = yf.Ticker(yf_symbol)

            # Get cash flow statement
            cashflow = stock.cashflow
            if cashflow is None or cashflow.empty:
                # Try KOSDAQ suffix
                if region == 'KR':
                    yf_symbol = f"{ticker}.KQ"
                    stock = yf.Ticker(yf_symbol)
                    cashflow = stock.cashflow

            if cashflow is None or cashflow.empty:
                logger.warning(f"No cash flow data for {ticker}")
                return {}

            # Get balance sheet for cash position
            balance = stock.balance_sheet

            # Extract latest data
            result = {'ticker': ticker, 'region': region}

            # Cash flow items
            if cashflow is not None and not cashflow.empty:
                latest_date = cashflow.columns[0]
                result['date'] = latest_date.date() if hasattr(latest_date, 'date') else latest_date

                for yf_field, db_field in self.CASHFLOW_FIELDS.items():
                    if yf_field in cashflow.index:
                        value = cashflow.loc[yf_field, latest_date]
                        if value is not None and str(value) != 'nan':
                            result[db_field] = float(value)

            # Balance sheet items (cash)
            if balance is not None and not balance.empty:
                latest_date = balance.columns[0]
                for yf_field, db_field in self.BALANCE_FIELDS.items():
                    if yf_field in balance.index:
                        value = balance.loc[yf_field, latest_date]
                        if value is not None and str(value) != 'nan':
                            result[db_field] = float(value)
                            break  # Use first match

            # Calculate FCF if not available
            if 'fcf' not in result and 'operating_cash_flow' in result:
                ocf = result.get('operating_cash_flow', 0)
                capex = abs(result.get('capex', 0))  # CapEx is usually negative
                result['fcf'] = ocf - capex

            return result

        except Exception as e:
            logger.error(f"Error collecting cash flow for {ticker}: {e}")
            return {}

    def update_fundamentals(
        self,
        ticker: str,
        region: str,
        cashflow_data: Dict
    ) -> bool:
        """
        Update ticker_fundamentals with cash flow data.

        Args:
            ticker: Stock ticker symbol
            region: Market region
            cashflow_data: Collected cash flow data

        Returns:
            True if successful
        """
        if not cashflow_data or 'date' not in cashflow_data:
            return False

        # Build update query
        update_fields = []
        params = []

        for field in ['operating_cash_flow', 'fcf', 'capex', 'investing_cf',
                      'financing_cf', 'cash_and_equivalents', 'short_term_investments']:
            if field in cashflow_data and cashflow_data[field] is not None:
                update_fields.append(f"{field} = %s")
                params.append(cashflow_data[field])

        if not update_fields:
            return False

        # Add last_updated
        update_fields.append("last_updated = NOW()")

        # Build query - update ANNUAL records for the fiscal year
        fiscal_year = cashflow_data['date'].year if hasattr(cashflow_data['date'], 'year') else int(str(cashflow_data['date'])[:4])

        query = f"""
            UPDATE ticker_fundamentals
            SET {', '.join(update_fields)}
            WHERE ticker = %s AND region = %s
              AND period_type = 'ANNUAL'
              AND fiscal_year = %s
        """

        params.extend([ticker, region, fiscal_year])

        try:
            self.db._execute_query(query, tuple(params), commit=True)
            return True
        except Exception as e:
            logger.error(f"Failed to update fundamentals for {ticker}: {e}")
            return False

    def process_ticker(
        self,
        ticker: str,
        region: str = 'KR'
    ) -> bool:
        """
        Process cash flow collection for a single ticker.

        Args:
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            True if successful
        """
        # Collect cash flow data
        cashflow_data = self.collect_cashflow(ticker, region)

        if not cashflow_data:
            return False

        # Update database
        success = self.update_fundamentals(ticker, region, cashflow_data)

        if success:
            ocf = cashflow_data.get('operating_cash_flow', 0)
            fcf = cashflow_data.get('fcf', 0)
            cash = cashflow_data.get('cash_and_equivalents', 0)
            logger.info(f"✅ {ticker}: OCF={ocf/1e9:.1f}B, FCF={fcf/1e9:.1f}B, Cash={cash/1e9:.1f}B")

        return success

    def process_all_tickers(
        self,
        region: str = 'KR',
        limit: int = 100
    ) -> Tuple[int, int]:
        """
        Process cash flow collection for all tickers.

        Args:
            region: Market region
            limit: Maximum tickers to process

        Returns:
            Tuple of (success_count, total_count)
        """
        # Get tickers that need cash flow data
        query = """
            SELECT DISTINCT t.ticker
            FROM tickers t
            JOIN ticker_fundamentals tf ON t.ticker = tf.ticker AND t.region = tf.region
            WHERE t.region = %s
              AND tf.period_type = 'ANNUAL'
              AND (tf.operating_cash_flow IS NULL OR tf.operating_cash_flow = 0)
            LIMIT %s
        """

        rows = self.db._execute_query(query, (region, limit), fetch_all=True)
        tickers = [r['ticker'] for r in rows] if rows else []

        logger.info(f"Processing {len(tickers)} tickers for cash flow data")

        success_count = 0
        for i, ticker in enumerate(tickers):
            if self.process_ticker(ticker, region):
                success_count += 1

            # Rate limiting (yfinance recommended)
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(tickers)} ({success_count} success)")
                time.sleep(2)  # Avoid rate limiting

        return success_count, len(tickers)


def main():
    parser = argparse.ArgumentParser(description='Collect cash flow data using yfinance')
    parser.add_argument('--region', default='KR', help='Market region (default: KR)')
    parser.add_argument('--ticker', help='Specific ticker to process')
    parser.add_argument('--limit', type=int, default=100, help='Max tickers to process')

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER', '13ruce'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
    )

    collector = CashFlowCollector(db)

    if args.ticker:
        # Process single ticker
        success = collector.process_ticker(args.ticker, args.region)
        sys.exit(0 if success else 1)
    else:
        # Process all tickers
        success_count, total_count = collector.process_all_tickers(args.region, args.limit)
        logger.info(f"Completed: {success_count}/{total_count} tickers processed")
        sys.exit(0 if success_count > 0 else 1)


if __name__ == '__main__':
    main()
