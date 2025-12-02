#!/usr/bin/env python3
"""
TTM (Trailing Twelve Months) Fundamentals Calculator

Calculates TTM financial metrics by aggregating the last 4 quarters of data
from ticker_fundamentals table and storing results in ticker_fundamentals_ttm.

Usage:
    python scripts/calculate_ttm_fundamentals.py [--region KR] [--ticker 005930]

Author: Quant Platform Development Team
Date: 2024-12-01
"""

import os
import sys
import argparse
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from modules.db_manager_postgres import PostgresDatabaseManager
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


class TTMCalculator:
    """
    TTM (Trailing Twelve Months) Calculator.

    Aggregates the last 4 quarters of financial data to compute
    annualized metrics for more accurate analysis.
    """

    # Income statement items to sum (flow items)
    FLOW_ITEMS = [
        'revenue', 'cogs', 'gross_profit', 'sga_expense', 'rd_expense',
        'operating_profit', 'interest_expense', 'interest_income',
        'net_income', 'ebitda', 'operating_cash_flow', 'investing_cf',
        'financing_cf', 'capex', 'fcf'
    ]

    # Balance sheet items - use latest quarter value (stock items)
    STOCK_ITEMS = [
        'total_assets', 'total_liabilities', 'total_equity',
        'current_assets', 'current_liabilities', 'inventory',
        'accounts_receivable', 'cash_and_equivalents', 'pp_e'
    ]

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager

    def get_last_4_quarters(
        self,
        ticker: str,
        region: str,
        as_of_date: date
    ) -> List[Dict]:
        """
        Get the last 4 quarters of data for a ticker.

        Args:
            ticker: Stock ticker symbol
            region: Market region (KR, US, etc.)
            as_of_date: Reference date for TTM calculation

        Returns:
            List of quarterly records (newest first), up to 4 quarters
        """
        query = """
            SELECT *
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND period_type = 'QUARTERLY'
              AND date <= %s
            ORDER BY date DESC
            LIMIT 4
        """

        # Use _execute_query with fetch_all for SELECT
        rows = self.db._execute_query(query, (ticker, region, as_of_date), fetch_all=True)
        return rows if rows else []

    def calculate_ttm(
        self,
        quarters: List[Dict]
    ) -> Optional[Dict]:
        """
        Calculate TTM values from quarterly data.

        Args:
            quarters: List of quarterly records (4 quarters ideally)

        Returns:
            TTM calculated values or None if insufficient data
        """
        if not quarters:
            return None

        num_quarters = len(quarters)

        # Calculate data completeness
        completeness = num_quarters / 4.0

        # Initialize TTM values
        ttm_data = {
            'quarters_included': [str(q.get('date')) for q in quarters],
            'data_completeness': completeness,
        }

        # Sum flow items (income statement, cash flow)
        for item in self.FLOW_ITEMS:
            values = [q.get(item) for q in quarters if q.get(item) is not None]
            if values:
                # Annualize if less than 4 quarters
                total = sum(float(v) for v in values)
                if num_quarters < 4 and num_quarters > 0:
                    total = total * (4 / num_quarters)
                ttm_data[f'{item}_ttm'] = total

        # Use latest quarter for stock items (balance sheet)
        latest = quarters[0]
        for item in self.STOCK_ITEMS:
            value = latest.get(item)
            if value is not None:
                ttm_data[item] = float(value)

        # Calculate ratios
        ttm_data.update(self._calculate_ratios(ttm_data))

        return ttm_data

    def _calculate_ratios(self, ttm_data: Dict) -> Dict:
        """Calculate financial ratios from TTM data."""
        ratios = {}

        # ROE = Net Income TTM / Total Equity
        net_income = ttm_data.get('net_income_ttm')
        equity = ttm_data.get('total_equity')
        if net_income and equity and equity > 0:
            ratios['roe_ttm'] = round(net_income / equity, 4)

        # ROA = Net Income TTM / Total Assets
        assets = ttm_data.get('total_assets')
        if net_income and assets and assets > 0:
            ratios['roa_ttm'] = round(net_income / assets, 4)

        # Operating Margin = Operating Profit TTM / Revenue TTM
        op_profit = ttm_data.get('operating_profit_ttm')
        revenue = ttm_data.get('revenue_ttm')
        if op_profit and revenue and revenue > 0:
            ratios['operating_margin_ttm'] = round(op_profit / revenue, 4)

        # Net Margin = Net Income TTM / Revenue TTM
        if net_income and revenue and revenue > 0:
            ratios['net_margin_ttm'] = round(net_income / revenue, 4)

        # Gross Margin = Gross Profit TTM / Revenue TTM
        gross_profit = ttm_data.get('gross_profit_ttm')
        if gross_profit and revenue and revenue > 0:
            ratios['gross_margin_ttm'] = round(gross_profit / revenue, 4)

        # Debt Ratio = Total Liabilities / Total Equity
        liabilities = ttm_data.get('total_liabilities')
        if liabilities and equity and equity > 0:
            ratios['debt_ratio'] = round(liabilities / equity, 4)

        # Current Ratio = Current Assets / Current Liabilities
        curr_assets = ttm_data.get('current_assets')
        curr_liab = ttm_data.get('current_liabilities')
        if curr_assets and curr_liab and curr_liab > 0:
            ratios['current_ratio'] = round(curr_assets / curr_liab, 4)

        # Asset Turnover = Revenue TTM / Total Assets
        if revenue and assets and assets > 0:
            ratios['asset_turnover_ttm'] = round(revenue / assets, 4)

        return ratios

    def save_ttm(
        self,
        ticker: str,
        region: str,
        as_of_date: date,
        ttm_data: Dict
    ) -> bool:
        """
        Save TTM data to ticker_fundamentals_ttm table.

        Args:
            ticker: Stock ticker symbol
            region: Market region
            as_of_date: TTM calculation date
            ttm_data: Calculated TTM values

        Returns:
            True if successful, False otherwise
        """
        # Build insert query
        columns = ['ticker', 'region', 'as_of_date']
        values = [ticker, region, as_of_date]

        # Map TTM data to table columns
        column_mapping = {
            'revenue_ttm': 'revenue_ttm',
            'gross_profit_ttm': 'gross_profit_ttm',
            'operating_profit_ttm': 'operating_profit_ttm',
            'net_income_ttm': 'net_income_ttm',
            'ebitda_ttm': 'ebitda_ttm',
            'interest_expense_ttm': 'interest_expense_ttm',
            'operating_cash_flow_ttm': 'operating_cash_flow_ttm',
            'fcf_ttm': 'fcf_ttm',
            'capex_ttm': 'capex_ttm',
            'total_assets': 'total_assets',
            'total_liabilities': 'total_liabilities',
            'total_equity': 'total_equity',
            'current_assets': 'current_assets',
            'current_liabilities': 'current_liabilities',
            'cash_and_equivalents': 'cash_and_equivalents',
            'inventory': 'inventory',
            'accounts_receivable': 'accounts_receivable',
            'roe_ttm': 'roe_ttm',
            'roa_ttm': 'roa_ttm',
            'operating_margin_ttm': 'operating_margin_ttm',
            'net_margin_ttm': 'net_margin_ttm',
            'gross_margin_ttm': 'gross_margin_ttm',
            'debt_ratio': 'debt_ratio',
            'current_ratio': 'current_ratio',
            'asset_turnover_ttm': 'asset_turnover_ttm',
            'data_completeness': 'data_completeness',
        }

        for data_key, col_name in column_mapping.items():
            if data_key in ttm_data and ttm_data[data_key] is not None:
                columns.append(col_name)
                values.append(ttm_data[data_key])

        # Handle quarters_included array
        if 'quarters_included' in ttm_data:
            columns.append('quarters_included')
            values.append(ttm_data['quarters_included'])

        # Add metadata
        columns.extend(['calculation_method', 'data_source', 'calculated_at'])
        values.extend(['STANDARD', 'calculated', datetime.now()])

        # Build query
        placeholders = ', '.join(['%s'] * len(values))
        col_str = ', '.join(columns)

        query = f"""
            INSERT INTO ticker_fundamentals_ttm ({col_str})
            VALUES ({placeholders})
            ON CONFLICT (ticker, region, as_of_date)
            DO UPDATE SET
                {', '.join([f'{c} = EXCLUDED.{c}' for c in columns if c not in ['ticker', 'region', 'as_of_date']])}
        """

        try:
            self.db._execute_query(query, tuple(values), commit=True)
            return True
        except Exception as e:
            logger.error(f"Failed to save TTM for {ticker}: {e}")
            return False

    def process_ticker(
        self,
        ticker: str,
        region: str,
        as_of_date: date = None
    ) -> bool:
        """
        Process TTM calculation for a single ticker.

        Args:
            ticker: Stock ticker symbol
            region: Market region
            as_of_date: Reference date (default: today)

        Returns:
            True if successful, False otherwise
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Get last 4 quarters
        quarters = self.get_last_4_quarters(ticker, region, as_of_date)

        if not quarters:
            logger.warning(f"No quarterly data for {ticker}")
            return False

        # Calculate TTM
        ttm_data = self.calculate_ttm(quarters)

        if not ttm_data:
            logger.warning(f"Failed to calculate TTM for {ticker}")
            return False

        # Save to database
        success = self.save_ttm(ticker, region, as_of_date, ttm_data)

        if success:
            logger.info(f"✅ TTM calculated for {ticker} ({len(quarters)} quarters, completeness: {ttm_data['data_completeness']:.0%})")

        return success

    def process_all_tickers(
        self,
        region: str,
        as_of_date: date = None
    ) -> Tuple[int, int]:
        """
        Process TTM calculation for all tickers with quarterly data.

        Args:
            region: Market region
            as_of_date: Reference date (default: today)

        Returns:
            Tuple of (success_count, total_count)
        """
        # Get all tickers with quarterly data
        query = """
            SELECT DISTINCT ticker
            FROM ticker_fundamentals
            WHERE region = %s AND period_type = 'QUARTERLY'
        """

        rows = self.db._execute_query(query, (region,), fetch_all=True)
        tickers = [r['ticker'] for r in rows] if rows else []

        logger.info(f"Processing TTM for {len(tickers)} tickers in {region}")

        success_count = 0
        for ticker in tickers:
            if self.process_ticker(ticker, region, as_of_date):
                success_count += 1

        return success_count, len(tickers)


def main():
    parser = argparse.ArgumentParser(description='Calculate TTM fundamentals')
    parser.add_argument('--region', default='KR', help='Market region (default: KR)')
    parser.add_argument('--ticker', help='Specific ticker to process (optional)')
    parser.add_argument('--date', help='As-of date in YYYY-MM-DD format (default: today)')

    args = parser.parse_args()

    # Parse date
    as_of_date = None
    if args.date:
        as_of_date = datetime.strptime(args.date, '%Y-%m-%d').date()

    # Initialize database
    db = PostgresDatabaseManager(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER', '13ruce'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
    )

    calculator = TTMCalculator(db)

    if args.ticker:
        # Process single ticker
        success = calculator.process_ticker(args.ticker, args.region, as_of_date)
        sys.exit(0 if success else 1)
    else:
        # Process all tickers
        success_count, total_count = calculator.process_all_tickers(args.region, as_of_date)
        logger.info(f"Completed: {success_count}/{total_count} tickers processed successfully")
        sys.exit(0 if success_count == total_count else 1)


if __name__ == '__main__':
    main()
