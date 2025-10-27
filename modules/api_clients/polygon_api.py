"""
Polygon.io API Client

Free-tier API client for US stock market data.

Features:
- Stock ticker listing (NYSE, NASDAQ, AMEX)
- Company information with GICS sector codes
- Daily OHLCV data retrieval
- Rate limiting (5 req/min free tier)

API Documentation: https://polygon.io/docs/stocks

Author: Spock Trading System
"""

import time
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PolygonAPI:
    """
    Polygon.io API client for US stock market data

    Free Tier Limits:
    - 5 API requests/minute
    - 2 years historical data
    - Real-time data delayed by 15 minutes
    """

    BASE_URL = "https://api.polygon.io"

    # API endpoints
    ENDPOINTS = {
        'tickers': '/v3/reference/tickers',
        'ticker_details': '/v3/reference/tickers/{ticker}',
        'aggregates': '/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}',
        'daily_open_close': '/v1/open-close/{ticker}/{date}',
        'market_status': '/v1/marketstatus/now'
    }

    # Exchange codes
    EXCHANGES = {
        'XNYS': 'NYSE',
        'XNAS': 'NASDAQ',
        'XASE': 'AMEX',
        'BATS': 'BATS',
        'ARCX': 'NYSE Arca'
    }

    def __init__(self, api_key: str, rate_limit_per_minute: int = 5):
        """
        Initialize Polygon API client

        Args:
            api_key: Polygon.io API key
            rate_limit_per_minute: Max requests per minute (default: 5 for free tier)
        """
        self.api_key = api_key
        self.rate_limit = rate_limit_per_minute
        self.last_call_time = None
        self.min_interval = 60.0 / rate_limit_per_minute  # Seconds between calls

        if not api_key:
            raise ValueError("Polygon API key is required")

    def _rate_limit_sleep(self):
        """
        Sleep if necessary to respect rate limits
        """
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                logger.debug(f"⏳ Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_call_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make HTTP request to Polygon API

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.HTTPError: If API returns error status
        """
        # Rate limiting
        self._rate_limit_sleep()

        # Add API key to params
        if params is None:
            params = {}
        params['apiKey'] = self.api_key

        # Build URL
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check for API-level errors
            if data.get('status') == 'ERROR':
                error_msg = data.get('error', 'Unknown error')
                logger.error(f"❌ Polygon API error: {error_msg}")
                raise Exception(f"Polygon API error: {error_msg}")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"❌ Polygon API timeout: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Polygon API request failed: {e}")
            raise

    def get_stock_list(self,
                      exchange: Optional[str] = None,
                      active: bool = True,
                      limit: int = 1000) -> List[Dict]:
        """
        Get list of stock tickers

        Args:
            exchange: Filter by exchange (XNYS, XNAS, XASE) or None for all
            active: Only active stocks (default: True)
            limit: Max results per page (max: 1000)

        Returns:
            List of ticker dictionaries

        Example response:
        [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'locale': 'us',
                'primary_exchange': 'XNAS',
                'type': 'CS',  # Common Stock
                'active': True,
                'currency_name': 'usd',
                'cik': '0000320193',
                'composite_figi': 'BBG000B9XRY4',
                'share_class_figi': 'BBG001S5N8V8'
            }
        ]
        """
        logger.info(f"🔍 Fetching US stock list from Polygon.io...")

        all_tickers = []
        next_url = None

        params = {
            'market': 'stocks',
            'active': str(active).lower(),
            'limit': limit,
            'order': 'asc',
            'sort': 'ticker'
        }

        if exchange:
            params['exchange'] = exchange

        # Pagination loop
        while True:
            if next_url:
                # Use next_url from previous response
                response = self._make_request(next_url.replace(self.BASE_URL, ''))
            else:
                response = self._make_request(self.ENDPOINTS['tickers'], params)

            # Extract results
            results = response.get('results', [])
            all_tickers.extend(results)

            logger.info(f"   Fetched {len(results)} tickers (total: {len(all_tickers)})")

            # Check for next page
            next_url = response.get('next_url')
            if not next_url:
                break

            # Safety limit: max 10,000 tickers
            if len(all_tickers) >= 10000:
                logger.warning(f"⚠️ Reached safety limit of 10,000 tickers")
                break

        logger.info(f"✅ Polygon.io: {len(all_tickers)} stock tickers fetched")
        return all_tickers

    def get_ticker_details(self, ticker: str) -> Optional[Dict]:
        """
        Get detailed information for a specific ticker

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Ticker details dictionary or None if not found

        Example response:
        {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'market': 'stocks',
            'locale': 'us',
            'primary_exchange': 'XNAS',
            'type': 'CS',
            'active': True,
            'currency_name': 'usd',
            'description': 'Apple Inc. designs, manufactures...',
            'homepage_url': 'https://www.apple.com',
            'total_employees': 164000,
            'list_date': '1980-12-12',
            'branding': {
                'logo_url': 'https://...',
                'icon_url': 'https://...'
            },
            'market_cap': 2800000000000,
            'share_class_shares_outstanding': 15550000000,
            'weighted_shares_outstanding': 15550000000,
            'sic_code': '3571',
            'sic_description': 'ELECTRONIC COMPUTERS'
        }
        """
        endpoint = self.ENDPOINTS['ticker_details'].format(ticker=ticker)

        try:
            response = self._make_request(endpoint)
            return response.get('results')
        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to get ticker details: {e}")
            return None

    def get_daily_ohlcv(self,
                       ticker: str,
                       from_date: str,
                       to_date: str) -> List[Dict]:
        """
        Get daily OHLCV data for a ticker

        Args:
            ticker: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)

        Returns:
            List of daily OHLCV dictionaries

        Example response:
        [
            {
                'v': 100000000,      # Volume
                'vw': 150.25,        # Volume weighted average price
                'o': 150.00,         # Open
                'c': 151.00,         # Close
                'h': 152.00,         # High
                'l': 149.50,         # Low
                't': 1609459200000,  # Unix timestamp (milliseconds)
                'n': 500000          # Number of transactions
            }
        ]
        """
        endpoint = self.ENDPOINTS['aggregates'].format(
            ticker=ticker,
            multiplier=1,
            timespan='day',
            from_date=from_date,
            to_date=to_date
        )

        params = {
            'adjusted': 'true',  # Adjust for splits
            'sort': 'asc',
            'limit': 50000  # Max results
        }

        try:
            response = self._make_request(endpoint, params)
            results = response.get('results', [])

            if not results:
                logger.warning(f"⚠️ [{ticker}] No OHLCV data found for {from_date} to {to_date}")
                return []

            # Convert timestamp to date string
            for item in results:
                item['date'] = datetime.fromtimestamp(item['t'] / 1000).strftime('%Y-%m-%d')

            logger.info(f"✅ [{ticker}] {len(results)} days of OHLCV data")
            return results

        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to get OHLCV data: {e}")
            return []

    def get_daily_ohlcv_last_n_days(self, ticker: str, days: int = 250) -> List[Dict]:
        """
        Get last N days of OHLCV data

        Args:
            ticker: Stock ticker symbol
            days: Number of trading days to fetch (default: 250)

        Returns:
            List of daily OHLCV dictionaries
        """
        end_date = datetime.now()
        # Approximate: ~252 trading days per year, so multiply by 1.4 for safety
        start_date = end_date - timedelta(days=int(days * 1.4))

        from_str = start_date.strftime('%Y-%m-%d')
        to_str = end_date.strftime('%Y-%m-%d')

        return self.get_daily_ohlcv(ticker, from_str, to_str)

    def check_connection(self) -> bool:
        """
        Test API connection and authentication

        Returns:
            True if connection successful
        """
        try:
            # Test with market status endpoint (lightweight)
            response = self._make_request(self.ENDPOINTS['market_status'])

            if response.get('market') == 'open' or response.get('market') == 'closed':
                logger.info(f"✅ Polygon.io connection successful")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Polygon.io connection failed: {e}")
            return False

    def get_exchange_name(self, exchange_code: str) -> str:
        """
        Get exchange name from code

        Args:
            exchange_code: Exchange code (e.g., 'XNYS')

        Returns:
            Exchange name (e.g., 'NYSE')
        """
        return self.EXCHANGES.get(exchange_code, exchange_code)
