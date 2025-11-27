#!/usr/bin/env python3
"""
Cash Data Backfill Script

Backfills cash_and_equivalents, short_term_investments, and marketable_securities
columns for tickers that have fundamentals data.

Uses yfinance for US market data.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from modules.db_manager_postgres import PostgresDatabaseManager


class CashDataBackfiller:
    """Backfills cash position data for stocks."""

    def __init__(self, db_manager: Optional[PostgresDatabaseManager] = None):
        self.db = db_manager or PostgresDatabaseManager()
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def get_tickers_needing_cash_data(self, region: str, limit: int = 100) -> List[Dict]:
        """
        Get tickers that have fundamentals but no cash data.

        Args:
            region: Market region code
            limit: Maximum number of tickers to process

        Returns:
            List of ticker records
        """
        query = """
        SELECT DISTINCT ticker
        FROM ticker_fundamentals
        WHERE region = %s
          AND period_type = 'ANNUAL'
          AND cash_and_equivalents IS NULL
          AND total_assets IS NOT NULL
        ORDER BY ticker
        LIMIT %s
        """
        result = self.db.execute_query(query, (region, limit))
        return [row['ticker'] for row in result] if result else []

    def fetch_us_cash_data(self, ticker: str) -> Optional[Dict]:
        """
        Fetch cash position data from yfinance for US stocks.

        Args:
            ticker: US ticker symbol

        Returns:
            Dict with cash position data or None
        """
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            balance_sheet = stock.balance_sheet

            if balance_sheet is None or balance_sheet.empty:
                logger.debug(f"No balance sheet for {ticker}")
                return None

            # Get most recent data (first column)
            latest = balance_sheet.iloc[:, 0]

            # Try different field names (yfinance API changes over time)
            cash_fields = [
                'Cash And Cash Equivalents',
                'Cash',
                'Cash And Short Term Investments',
                'CashAndCashEquivalentsAtCarryingValue'
            ]
            short_term_fields = [
                'Short Term Investments',
                'Other Short Term Investments',
                'ShortTermInvestments'
            ]
            securities_fields = [
                'Available For Sale Securities',
                'Marketable Securities',
                'Other Current Assets'
            ]

            import math
            result = {}

            def is_valid_value(val):
                """Check if value is valid (not None, not NaN)"""
                if val is None:
                    return False
                try:
                    return not math.isnan(float(val))
                except (TypeError, ValueError):
                    return False

            # Get cash and equivalents
            for field in cash_fields:
                if field in latest.index and is_valid_value(latest[field]):
                    result['cash_and_equivalents'] = float(latest[field])
                    break

            # Get short-term investments
            for field in short_term_fields:
                if field in latest.index and is_valid_value(latest[field]):
                    result['short_term_investments'] = float(latest[field])
                    break

            # Get marketable securities
            for field in securities_fields:
                if field in latest.index and is_valid_value(latest[field]):
                    result['marketable_securities'] = float(latest[field])
                    break

            return result if result else None

        except ImportError:
            logger.warning("yfinance not installed. Install with: pip install yfinance")
            return None
        except Exception as e:
            logger.error(f"Error fetching cash data for {ticker}: {e}")
            return None

    def update_cash_data(self, ticker: str, region: str, cash_data: Dict) -> bool:
        """
        Update cash data for a ticker in the database.

        Args:
            ticker: Ticker symbol
            region: Market region
            cash_data: Dict with cash position values

        Returns:
            True if successful
        """
        if not cash_data:
            return False

        # Build dynamic SET clause
        set_parts = []
        params = []

        if 'cash_and_equivalents' in cash_data:
            set_parts.append("cash_and_equivalents = %s")
            params.append(cash_data['cash_and_equivalents'])

        if 'short_term_investments' in cash_data:
            set_parts.append("short_term_investments = %s")
            params.append(cash_data['short_term_investments'])

        if 'marketable_securities' in cash_data:
            set_parts.append("marketable_securities = %s")
            params.append(cash_data['marketable_securities'])

        if not set_parts:
            return False

        # Update most recent ANNUAL record
        query = f"""
        UPDATE ticker_fundamentals
        SET {", ".join(set_parts)}
        WHERE ticker = %s
          AND region = %s
          AND period_type = 'ANNUAL'
          AND date = (
              SELECT MAX(date)
              FROM ticker_fundamentals
              WHERE ticker = %s AND region = %s AND period_type = 'ANNUAL'
          )
        """
        params.extend([ticker, region, ticker, region])

        try:
            return self.db.execute_update(query, tuple(params))
        except Exception as e:
            logger.error(f"Failed to update cash data for {ticker}: {e}")
            return False

    def backfill_region(self, region: str, limit: int = 100) -> Dict:
        """
        Backfill cash data for a specific region.

        Args:
            region: Market region code
            limit: Maximum tickers to process

        Returns:
            Summary statistics
        """
        logger.info(f"Starting cash data backfill for region: {region}")

        tickers = self.get_tickers_needing_cash_data(region, limit)
        logger.info(f"Found {len(tickers)} tickers needing cash data in {region}")

        stats = {
            "total": len(tickers),
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }

        for i, ticker in enumerate(tickers):
            logger.info(f"Processing {ticker} ({i+1}/{len(tickers)})")

            if region == "US":
                cash_data = self.fetch_us_cash_data(ticker)
            else:
                # TODO: Add support for other regions (KR using pykrx, etc.)
                logger.warning(f"Cash data fetch not implemented for region {region}")
                stats["skipped"] += 1
                continue

            if cash_data:
                success = self.update_cash_data(ticker, region, cash_data)
                if success:
                    stats["updated"] += 1
                    self.updated_count += 1
                    logger.info(f"  Updated {ticker}: {cash_data}")
                else:
                    stats["errors"] += 1
                    self.error_count += 1
            else:
                stats["skipped"] += 1
                self.skipped_count += 1

        logger.info(
            f"Region {region} completed: "
            f"updated={stats['updated']}, "
            f"skipped={stats['skipped']}, "
            f"errors={stats['errors']}"
        )

        return stats

    def run_backfill(self, regions: Optional[List[str]] = None, limit: int = 100) -> Dict:
        """
        Run backfill for specified regions.

        Args:
            regions: List of regions to backfill
            limit: Max tickers per region

        Returns:
            Summary statistics
        """
        if regions is None:
            regions = ["US"]  # Only US supported initially

        logger.info(f"Starting cash data backfill for regions: {regions}")

        results = {}
        for region in regions:
            try:
                results[region] = self.backfill_region(region, limit)
            except Exception as e:
                logger.error(f"Failed to backfill region {region}: {e}")
                results[region] = {"error": str(e)}

        summary = {
            "total_updated": self.updated_count,
            "total_skipped": self.skipped_count,
            "total_errors": self.error_count,
            "regions": results
        }

        return summary


def main():
    """Run cash data backfill"""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill cash position data")
    parser.add_argument(
        "--region", "-r",
        default="US",
        help="Market region to backfill (default: US)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Maximum tickers to process (default: 50)"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Cash Data Backfill")
    logger.info("=" * 60)

    backfiller = CashDataBackfiller()
    summary = backfiller.run_backfill(regions=[args.region], limit=args.limit)

    logger.info("\n" + "=" * 60)
    logger.info("Backfill Summary")
    logger.info("=" * 60)
    logger.info(f"Total Updated: {summary['total_updated']}")
    logger.info(f"Total Skipped: {summary['total_skipped']}")
    logger.info(f"Total Errors:  {summary['total_errors']}")

    return summary


if __name__ == "__main__":
    result = main()

    if result.get('total_errors', 0) > 0:
        sys.exit(1)
    sys.exit(0)
