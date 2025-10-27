"""
YFinance API Wrapper - Yahoo Finance Data Source

Wrapper for yfinance library with rate limiting and error handling.
Used for Hong Kong stocks and fallback for China/US markets.

Key Features:
- No API key required (completely free)
- Rate limiting: 1 request/second (conservative)
- Automatic retry with exponential backoff
- Session management for connection pooling
- Comprehensive error handling

Author: Spock Trading System
"""

import yfinance as yf
import pandas as pd
import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class YFinanceAPI:
    """
    Yahoo Finance API wrapper with rate limiting and error handling

    Usage:
        api = YFinanceAPI(rate_limit_per_second=1)
        tickers = api.get_tickers_batch(['0700.HK', '0941.HK'])
        ohlcv = api.get_ohlcv('0700.HK', period='1y')
    """

    def __init__(self, rate_limit_per_second: float = 1.0):
        """
        Initialize YFinance API wrapper

        Args:
            rate_limit_per_second: Max requests per second (default: 1.0)
        """
        self.rate_limit = rate_limit_per_second
        self.last_request_time = 0
        self.session = None

        logger.info(f"📊 YFinanceAPI initialized (rate: {rate_limit_per_second} req/s)")

    def _rate_limit_sleep(self):
        """Sleep to enforce rate limiting"""
        if self.rate_limit <= 0:
            return

        elapsed = time.time() - self.last_request_time
        sleep_time = (1.0 / self.rate_limit) - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _retry_on_failure(self, func, max_retries: int = 3, *args, **kwargs):
        """
        Retry logic with exponential backoff

        Args:
            func: Function to retry
            max_retries: Maximum retry attempts
            *args, **kwargs: Arguments for func

        Returns:
            Function result or None on failure
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit_sleep()
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(f"⚠️ Attempt {attempt+1}/{max_retries} failed: {e}")

                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ All {max_retries} attempts failed")
                    return None

    def get_ticker_info(self, ticker: str) -> Optional[Dict]:
        """
        Get company information for a ticker (raw yfinance.Ticker().info)

        Args:
            ticker: Ticker symbol (e.g., '0700.HK', 'AAPL', '7203.T')

        Returns:
            Raw yfinance info dictionary or None on failure
            Contains all fields from yfinance API (symbol, longName, sector, etc.)

        Note:
            This returns the complete raw info dict for maximum compatibility
            with parsers. Use get_ticker_summary() for simplified output.
        """
        def _fetch():
            stock = yf.Ticker(ticker, session=self.session)
            info = stock.info

            if not info or 'symbol' not in info:
                raise ValueError(f"No data for ticker {ticker}")

            return info

        result = self._retry_on_failure(_fetch)

        if result:
            logger.debug(f"✅ Fetched info for {ticker}")

        return result

    def get_ticker_summary(self, ticker: str) -> Optional[Dict]:
        """
        Get simplified company information for a ticker

        Args:
            ticker: Ticker symbol (e.g., '0700.HK', 'AAPL')

        Returns:
            Dictionary with key company info or None on failure

        Example:
            {
                'ticker': '0700.HK',
                'name': 'Tencent Holdings Limited',
                'sector': 'Communication Services',
                'industry': 'Internet Content & Information',
                'market_cap': 3500000000000,
                'currency': 'HKD',
                'exchange': 'HKG'
            }
        """
        info = self.get_ticker_info(ticker)

        if not info:
            return None

        return {
            'ticker': ticker,
            'name': info.get('longName', info.get('shortName', ticker)),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'market_cap': info.get('marketCap'),
            'currency': info.get('currency'),
            'exchange': info.get('exchange'),
            'quote_type': info.get('quoteType', 'EQUITY'),
            'country': info.get('country'),
            'website': info.get('website'),
            'description': info.get('longBusinessSummary'),
        }

    def get_ohlcv(self,
                   ticker: str,
                   period: str = '1y',
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get OHLCV data for a ticker

        Args:
            ticker: Ticker symbol
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            start_date: Start date 'YYYY-MM-DD' (overrides period)
            end_date: End date 'YYYY-MM-DD'

        Returns:
            DataFrame with columns [date, open, high, low, close, volume]
            or None on failure
        """
        def _fetch():
            stock = yf.Ticker(ticker, session=self.session)

            if start_date and end_date:
                df = stock.history(start=start_date, end=end_date)
            else:
                df = stock.history(period=period)

            if df.empty:
                raise ValueError(f"No OHLCV data for {ticker}")

            # Reset index to make date a column
            df = df.reset_index()

            # Rename columns to lowercase
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Keep only OHLCV columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} days of OHLCV for {ticker}")

        return result

    def get_tickers_batch(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Get company info for multiple tickers (batch operation)

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary {ticker: info_dict}
        """
        results = {}

        for i, ticker in enumerate(tickers, 1):
            logger.info(f"📊 Fetching {ticker} ({i}/{len(tickers)})")
            info = self.get_ticker_info(ticker)

            if info:
                results[ticker] = info
            else:
                logger.warning(f"⚠️ Skipped {ticker} (no data)")

        logger.info(f"✅ Fetched {len(results)}/{len(tickers)} tickers")
        return results

    def search_tickers(self,
                       query: str,
                       exchange: Optional[str] = None,
                       max_results: int = 100) -> List[str]:
        """
        Search for tickers by company name or symbol

        Note: yfinance doesn't have built-in search, so this is a workaround

        Args:
            query: Search query
            exchange: Filter by exchange (e.g., 'HKG')
            max_results: Max results to return

        Returns:
            List of ticker symbols
        """
        # yfinance doesn't support search directly
        # This is a placeholder for future implementation
        logger.warning("⚠️ Search not implemented for yfinance (use external ticker lists)")
        return []

    def get_exchange_tickers(self, exchange: str) -> List[str]:
        """
        Get all tickers for an exchange

        Note: yfinance doesn't provide exchange-wide ticker lists
        Use external sources (KRX, Polygon.io, etc.)

        Args:
            exchange: Exchange code ('HKG', 'NYSE', 'NASDAQ', etc.)

        Returns:
            List of ticker symbols
        """
        logger.warning(f"⚠️ Exchange ticker list not available from yfinance")
        logger.info(f"💡 Use external sources for {exchange} ticker list")
        return []

    def validate_ticker(self, ticker: str) -> bool:
        """
        Check if ticker exists and has data

        Args:
            ticker: Ticker symbol

        Returns:
            True if valid, False otherwise
        """
        info = self.get_ticker_info(ticker)
        return info is not None and 'symbol' in str(info)

    def close(self):
        """Close session and cleanup resources"""
        if self.session:
            self.session.close()
            self.session = None
            logger.info("🔒 YFinance session closed")
