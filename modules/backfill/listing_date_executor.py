"""
Listing date backfill executor with yfinance integration

This executor implements backfill logic for listing_date field in tickers table
using yfinance library for KR and overseas markets.

Key Features:
- yfinance integration for listing date retrieval
- Multi-market support (KR, US, JP, HK, CN, VN)
- Automatic ticker format conversion
- Error handling for delisted/invalid tickers
- Database transaction management

Example Usage:
    from modules.db_manager_postgres import PostgresDatabaseManager
    from modules.backfill.listing_date_executor import ListingDateBackfillExecutor

    db = PostgresDatabaseManager()
    executor = ListingDateBackfillExecutor(db, dry_run=False)

    # Single ticker
    ticker_info = TickerGapInfo(
        ticker='005930',
        name='Samsung Electronics',
        region='KR',
        ...
    )
    success = executor.execute_ticker(ticker_info)

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import logging
from typing import Tuple, List, Optional
from datetime import date

import yfinance as yf

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.data_structures import TickerGapInfo

logger = logging.getLogger(__name__)


class ListingDateBackfillExecutor(BackfillExecutor):
    """
    Listing date backfill executor with yfinance integration

    Implements backfill logic for tickers.listing_date field:
    - Retrieves listing date from yfinance API
    - Converts ticker format for different markets
    - Updates database with transaction safety
    """

    # Ticker suffix mapping for yfinance
    TICKER_SUFFIX_MAP = {
        'KR': '.KS',    # Korea Exchange
        'US': '',       # No suffix for US
        'JP': '.T',     # Tokyo Stock Exchange
        'HK': '.HK',    # Hong Kong Stock Exchange
        'CN': '.SS',    # Shanghai Stock Exchange (use .SZ for Shenzhen)
        'VN': '.VN'     # Vietnam Stock Exchange
    }

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 0.5,  # yfinance is more lenient
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize ListingDateBackfillExecutor

        Args:
            db: PostgreSQL database manager instance
            dry_run: If True, preview operations without executing
            rate_limit_delay: Delay between API calls (default: 0.5s)
            max_retries: Maximum retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
        """
        super().__init__(
            db=db,
            dry_run=dry_run,
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        logger.debug("ListingDateBackfillExecutor initialized")

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        Validate prerequisites before execution

        Checks:
        1. yfinance library availability
        2. Database connection
        3. Network connectivity

        Returns:
            (준비 완료 여부, 문제점 목록) 튜플
        """
        issues = []

        # Check yfinance availability
        try:
            # Test yfinance with a simple ticker
            test_ticker = yf.Ticker("AAPL")
            _ = test_ticker.info
            logger.info("✅ yfinance library verified")
        except Exception as e:
            issues.append(f"yfinance library test failed: {e}")
            logger.error(f"❌ {issues[-1]}")

        # Check database connection
        try:
            test_query = "SELECT 1"
            self.db.execute_query(test_query)
            logger.info("✅ Database connection verified")
        except Exception as e:
            issues.append(f"Database connection failed: {e}")
            logger.error(f"❌ {issues[-1]}")

        return (len(issues) == 0, issues)

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """
        Execute backfill for single ticker

        Workflow:
        1. Convert ticker to yfinance format
        2. Fetch ticker info from yfinance
        3. Extract listing date (firstTradeDateEpochUtc)
        4. Update database with new data

        Args:
            ticker_info: Ticker information from gap analysis

        Returns:
            True if successful, False otherwise
        """
        ticker = ticker_info.ticker
        name = ticker_info.name
        region = ticker_info.region

        logger.info(f"처리 중: {ticker} ({name}) - {region}")

        try:
            # Convert to yfinance format
            yf_ticker = self._convert_to_yfinance_ticker(ticker, region)
            logger.debug(f"yfinance ticker: {yf_ticker}")

            # Fetch ticker info
            ticker_obj = yf.Ticker(yf_ticker)
            info = ticker_obj.info

            if not info or 'firstTradeDateEpochUtc' not in info:
                logger.warning(f"⚠️  {ticker}: No listing date in yfinance data")
                return False

            # Extract listing date
            first_trade_epoch = info['firstTradeDateEpochUtc']
            if first_trade_epoch is None:
                logger.warning(f"⚠️  {ticker}: firstTradeDateEpochUtc is None")
                return False

            # Convert epoch to date
            from datetime import datetime
            listing_date = datetime.fromtimestamp(first_trade_epoch).date()

            logger.info(f"📅 {ticker}: Listing date = {listing_date}")

            # Update database
            success = self._update_database(ticker, region, listing_date)

            if success:
                logger.info(f"✅ {ticker}: Listing date updated successfully")
                self.stats.records_updated += 1
                return True
            else:
                logger.warning(f"⚠️  {ticker}: Database update failed")
                return False

        except Exception as e:
            logger.error(f"❌ {ticker}: Error during backfill - {e}")
            return False

    def _convert_to_yfinance_ticker(self, ticker: str, region: str) -> str:
        """
        Convert ticker to yfinance format

        yfinance requires specific suffixes for non-US markets:
        - KR: 005930.KS
        - JP: 7203.T
        - HK: 0700.HK
        - CN: 600519.SS (or .SZ)
        - VN: VNM.VN
        - US: AAPL (no suffix)

        Args:
            ticker: Original ticker symbol
            region: Market region code

        Returns:
            yfinance-formatted ticker symbol

        Special Cases:
        - KR: Add leading zeros if needed (5930 → 005930)
        - HK: Add leading zeros (700 → 0700)
        """
        suffix = self.TICKER_SUFFIX_MAP.get(region, '')

        # Special handling for KR market
        if region == 'KR':
            # Ensure 6 digits
            ticker_clean = ticker.zfill(6)
            return f"{ticker_clean}{suffix}"

        # Special handling for HK market
        elif region == 'HK':
            # Ensure 4 digits
            ticker_clean = ticker.zfill(4)
            return f"{ticker_clean}{suffix}"

        # Special handling for US market
        elif region == 'US':
            # US preferred stocks/classes: DB uses '/' but yfinance uses '.'
            # e.g., BRK/B → BRK.B, MS/A → MS.A
            return ticker.replace('/', '-') if '/' in ticker else ticker

        # Other markets
        else:
            return f"{ticker}{suffix}"

    def _update_database(
        self,
        ticker: str,
        region: str,
        listing_date: date
    ) -> bool:
        """
        Update tickers table with listing date

        Args:
            ticker: Ticker symbol
            region: Market region
            listing_date: Listing date

        Returns:
            True if update successful, False otherwise
        """
        try:
            query = """
            UPDATE tickers
            SET listing_date = %(listing_date)s,
                updated_at = CURRENT_TIMESTAMP
            WHERE ticker = %(ticker)s
              AND region = %(region)s
            """

            params = {
                'ticker': ticker,
                'region': region,
                'listing_date': listing_date
            }

            self.db.execute_query(query, params)
            return True

        except Exception as e:
            logger.error(f"❌ Database update error for {ticker}: {e}")
            return False
