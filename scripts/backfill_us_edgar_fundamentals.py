#!/usr/bin/env python3
"""
US EDGAR Fundamentals Backfill

Collects historical fundamental data for US tickers from SEC EDGAR filings.
Provides annual (10-K) financial data including revenue, net income, EPS, assets.

Usage:
    python3 scripts/backfill_us_edgar_fundamentals.py

Author: Spock Trading System
"""

import os
import sys
import time
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, List
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgar import Company, set_identity

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
log_file = f"log/{datetime.now().strftime('%Y%m%d')}_us_edgar_fundamentals.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class USEdgarFundamentalsCollector:
    """Collect fundamentals from SEC EDGAR for US stocks."""

    # Key GAAP concepts to extract
    GAAP_CONCEPTS = {
        # Income Statement
        'revenue': ['us-gaap:Revenues', 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
                    'us-gaap:SalesRevenueNet'],
        'net_income': ['us-gaap:NetIncomeLoss', 'us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic'],
        'operating_income': ['us-gaap:OperatingIncomeLoss'],
        'gross_profit': ['us-gaap:GrossProfit'],
        'ebitda': ['us-gaap:OperatingIncomeLoss'],  # Will need to add D&A

        # Per Share
        'eps_basic': ['us-gaap:EarningsPerShareBasic'],
        'eps_diluted': ['us-gaap:EarningsPerShareDiluted'],

        # Balance Sheet (instant)
        'total_assets': ['us-gaap:Assets'],
        'total_liabilities': ['us-gaap:Liabilities'],
        'shareholders_equity': ['us-gaap:StockholdersEquity', 'us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
        'shares_outstanding': ['us-gaap:CommonStockSharesOutstanding', 'us-gaap:CommonStockSharesIssued'],
        'cash': ['us-gaap:CashAndCashEquivalentsAtCarryingValue'],
        'total_debt': ['us-gaap:LongTermDebt', 'us-gaap:DebtCurrent'],
    }

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager
        self.rate_limit = 0.2  # 5 requests per second (SEC limit is 10/sec)
        self.last_request = 0
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'no_data': 0,
            'start_time': None
        }

        # Set EDGAR identity (required by SEC)
        set_identity("Spock Quant Platform research@example.com")

    def _rate_limit_sleep(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request = time.time()

    def _to_edgar_ticker(self, ticker: str) -> str:
        """Convert DB ticker to EDGAR format."""
        # DB format: BRK/B -> EDGAR: BRK-B
        return ticker.replace('/', '-')

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except:
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert to int."""
        if value is None:
            return None
        try:
            return int(float(value))
        except:
            return None

    def get_target_tickers(self) -> List[Dict]:
        """Get US tickers containing '/'."""
        query = """
            SELECT ticker, name, exchange
            FROM tickers
            WHERE region = 'US' AND ticker LIKE '%%/%%' AND is_active = true
            ORDER BY ticker
        """
        return self.db.execute_query(query)

    def _get_fact_value(self, df: pd.DataFrame, concepts: List[str],
                        fiscal_year: int, period_type: str = 'duration') -> Optional[float]:
        """
        Extract fact value from EDGAR DataFrame.

        Args:
            df: EDGAR facts DataFrame
            concepts: List of GAAP concept names to try
            fiscal_year: Fiscal year to extract
            period_type: 'duration' for income statement, 'instant' for balance sheet

        Returns:
            Numeric value or None
        """
        for concept in concepts:
            concept_df = df[df['concept'] == concept]
            if len(concept_df) == 0:
                continue

            # For duration items, look for full year periods
            if period_type == 'duration':
                concept_df = concept_df.copy()
                concept_df['period_start'] = pd.to_datetime(concept_df['period_start'])
                concept_df['period_end'] = pd.to_datetime(concept_df['period_end'])
                concept_df['days'] = (concept_df['period_end'] - concept_df['period_start']).dt.days
                # Filter for full year (>350 days) and matching fiscal year
                annual = concept_df[(concept_df['days'] > 350) & (concept_df['fiscal_year'] == fiscal_year)]
            else:
                # For instant items, get the end-of-year value
                annual = concept_df[concept_df['fiscal_year'] == fiscal_year]

            if len(annual) > 0:
                # Get the latest value for this fiscal year
                return annual.iloc[-1]['numeric_value']

        return None

    def collect_fundamentals(self, ticker: str) -> List[Dict]:
        """Collect historical fundamentals from EDGAR."""
        edgar_ticker = self._to_edgar_ticker(ticker)
        results = []

        try:
            self._rate_limit_sleep()
            company = Company(edgar_ticker)
            facts = company.get_facts()

            if facts is None:
                return []

            df = facts.to_dataframe()
            if len(df) == 0:
                return []

            # Get available fiscal years
            fiscal_years = sorted(df['fiscal_year'].dropna().unique())
            # Filter to reasonable years (2015-2025)
            fiscal_years = [y for y in fiscal_years if 2015 <= y <= 2025]

            for fy in fiscal_years:
                fundamentals = {
                    'ticker': ticker,
                    'region': 'US',
                    'date': date(int(fy), 12, 31),  # End of fiscal year
                    'period_type': 'ANNUAL',
                    'data_source': 'SEC EDGAR',
                    'fiscal_year': int(fy),
                }

                # Extract income statement items (duration)
                fundamentals['revenue'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['revenue'], fy, 'duration'))
                fundamentals['net_income'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['net_income'], fy, 'duration'))
                fundamentals['operating_income'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['operating_income'], fy, 'duration'))
                fundamentals['trailing_eps'] = self._safe_decimal(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['eps_basic'], fy, 'duration'))

                # Extract balance sheet items (instant)
                fundamentals['total_assets'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['total_assets'], fy, 'instant'))
                fundamentals['total_liabilities'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['total_liabilities'], fy, 'instant'))
                fundamentals['shareholders_equity'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['shareholders_equity'], fy, 'instant'))
                fundamentals['shares_outstanding'] = self._safe_int(
                    self._get_fact_value(df, self.GAAP_CONCEPTS['shares_outstanding'], fy, 'instant'))

                # Calculate book value per share
                if fundamentals['shareholders_equity'] and fundamentals['shares_outstanding']:
                    bv_per_share = fundamentals['shareholders_equity'] / fundamentals['shares_outstanding']
                    fundamentals['book_value_per_share'] = self._safe_decimal(bv_per_share)
                else:
                    fundamentals['book_value_per_share'] = None

                # Only add if we have at least some data
                if any(v is not None for k, v in fundamentals.items()
                       if k not in ['ticker', 'region', 'date', 'period_type', 'data_source', 'fiscal_year']):
                    results.append(fundamentals)

            return results

        except Exception as e:
            logger.debug(f"[{ticker}] EDGAR error: {e}")
            return []

    def save_fundamentals(self, data: Dict) -> bool:
        """Save fundamentals to database."""
        query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, data_source, fiscal_year,
                revenue, net_income, operating_profit,
                total_assets, total_liabilities, total_equity,
                shares_outstanding, trailing_eps,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                revenue = COALESCE(EXCLUDED.revenue, ticker_fundamentals.revenue),
                net_income = COALESCE(EXCLUDED.net_income, ticker_fundamentals.net_income),
                operating_profit = COALESCE(EXCLUDED.operating_profit, ticker_fundamentals.operating_profit),
                total_assets = COALESCE(EXCLUDED.total_assets, ticker_fundamentals.total_assets),
                total_liabilities = COALESCE(EXCLUDED.total_liabilities, ticker_fundamentals.total_liabilities),
                total_equity = COALESCE(EXCLUDED.total_equity, ticker_fundamentals.total_equity),
                shares_outstanding = COALESCE(EXCLUDED.shares_outstanding, ticker_fundamentals.shares_outstanding),
                trailing_eps = COALESCE(EXCLUDED.trailing_eps, ticker_fundamentals.trailing_eps),
                fiscal_year = COALESCE(EXCLUDED.fiscal_year, ticker_fundamentals.fiscal_year),
                data_source = EXCLUDED.data_source
        """

        try:
            params = (
                data['ticker'], data['region'], data['date'], data['period_type'], data['data_source'],
                data.get('fiscal_year'),
                data.get('revenue'), data.get('net_income'), data.get('operating_income'),
                data.get('total_assets'), data.get('total_liabilities'), data.get('shareholders_equity'),
                data.get('shares_outstanding'), data.get('trailing_eps')
            )
            return self.db.execute_update(query, params)
        except Exception as e:
            logger.error(f"[{data['ticker']}] DB save error: {e}")
            return False

    def run(self):
        """Run the backfill process."""
        logger.info("=" * 60)
        logger.info("US EDGAR Fundamentals Backfill")
        logger.info("=" * 60)

        # Get target tickers
        tickers = self.get_target_tickers()
        self.stats['total'] = len(tickers)
        self.stats['start_time'] = time.time()

        logger.info(f"Target tickers: {len(tickers)}")
        logger.info(f"Rate limit: {1/self.rate_limit:.1f} req/sec")
        logger.info(f"Estimated time: ~{len(tickers) * self.rate_limit / 60:.1f} minutes")
        logger.info("-" * 60)

        total_records = 0
        for i, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            name = ticker_info['name'][:30] if ticker_info['name'] else ''

            # Progress
            elapsed = time.time() - self.stats['start_time']
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(tickers) - i) / rate if rate > 0 else 0

            # Collect
            fundamentals_list = self.collect_fundamentals(ticker)

            if fundamentals_list:
                saved_count = 0
                for fundamentals in fundamentals_list:
                    if self.save_fundamentals(fundamentals):
                        saved_count += 1

                if saved_count > 0:
                    self.stats['success'] += 1
                    total_records += saved_count
                    years = [f['fiscal_year'] for f in fundamentals_list]
                    logger.info(f"[{i}/{len(tickers)}] ✅ {ticker} - {saved_count} years ({min(years)}-{max(years)})")
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"[{i}/{len(tickers)}] ❌ {ticker} - Save failed")
            else:
                self.stats['no_data'] += 1
                if i % 10 == 0 or i <= 5:
                    logger.info(f"[{i}/{len(tickers)}] ⚠️ {ticker} - No EDGAR data")

            # Progress summary every 20 tickers
            if i % 20 == 0:
                pct = i / len(tickers) * 100
                logger.info(f"--- Progress: {i}/{len(tickers)} ({pct:.1f}%) | Records: {total_records} | ETA: {eta/60:.1f}min ---")

        # Summary
        elapsed = time.time() - self.stats['start_time']
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total tickers: {self.stats['total']}")
        logger.info(f"Success: {self.stats['success']}")
        logger.info(f"No Data: {self.stats['no_data']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Total records: {total_records}")
        if self.stats['total'] > 0:
            logger.info(f"Success rate: {self.stats['success']/self.stats['total']*100:.1f}%")
        logger.info(f"Duration: {elapsed/60:.1f} minutes")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    from dotenv import load_dotenv
    load_dotenv()

    db_manager = PostgresDatabaseManager()

    collector = USEdgarFundamentalsCollector(db_manager)
    collector.run()


if __name__ == '__main__':
    main()
