"""
AkShare API Wrapper - China Stock Market Data Source

Wrapper for AkShare library (no API key required, completely free).
Primary data source for China A-shares (SSE/SZSE).

Key Features:
- No API key required (open-source library)
- Rate limiting: 1-2 requests/second (conservative)
- Automatic retry with exponential backoff
- Fallback-ready design (can switch to yfinance)
- Comprehensive error handling

AkShare Documentation: https://akshare.akfamily.xyz/

Author: Spock Trading System
"""

import akshare as ak
import pandas as pd
import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AkShareAPI:
    """
    AkShare API wrapper with rate limiting and error handling

    Usage:
        api = AkShareAPI(rate_limit_per_second=1.0)
        stocks = api.get_stock_list_realtime()
        ohlcv = api.get_stock_daily_ohlcv('600519', period='1y')
    """

    def __init__(self, rate_limit_per_second: float = 1.5):
        """
        Initialize AkShare API wrapper

        Args:
            rate_limit_per_second: Max requests per second (default: 1.5)
                Conservative rate limit to avoid server issues
        """
        self.rate_limit = rate_limit_per_second
        self.last_request_time = 0

        logger.info(f"🇨🇳 AkShareAPI initialized (rate: {rate_limit_per_second} req/s)")

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

    def get_stock_list_realtime(self) -> Optional[pd.DataFrame]:
        """
        Get real-time stock list for SSE and SZSE

        Uses: ak.stock_zh_a_spot_em()

        Returns:
            DataFrame with columns:
            - code: Stock code (e.g., '600519')
            - name: Stock name
            - price: Current price
            - change_percent: Daily change %
            - volume: Trading volume
            - amount: Trading amount
            - market_cap: Market capitalization
            Or None on failure
        """
        def _fetch():
            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                raise ValueError("No stock list data")

            # Rename columns to English
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_percent',
                '成交量': 'volume',
                '成交额': 'amount',
                '总市值': 'market_cap'
            })

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} stocks from real-time list")

        return result

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """
        Get company information for a ticker

        Uses: ak.stock_individual_info_em()

        Args:
            ticker: Stock code (e.g., '600519' for Shanghai, '000001' for Shenzhen)

        Returns:
            Dictionary with company info or None on failure
        """
        def _fetch():
            df = ak.stock_individual_info_em(symbol=ticker)

            if df is None or df.empty:
                raise ValueError(f"No data for ticker {ticker}")

            # Convert DataFrame to dictionary
            info = {}
            for _, row in df.iterrows():
                key = row.get('item', row.get('项目'))
                value = row.get('value', row.get('值'))
                if key and value:
                    info[key] = value

            return info

        result = self._retry_on_failure(_fetch)

        if result:
            logger.debug(f"✅ Fetched info for {ticker}")

        return result

    def get_stock_daily_ohlcv(self,
                              ticker: str,
                              start_date: Optional[str] = None,
                              end_date: Optional[str] = None,
                              period: str = '1y') -> Optional[pd.DataFrame]:
        """
        Get daily OHLCV data for a ticker

        Uses: ak.stock_zh_a_hist()

        Args:
            ticker: Stock code (e.g., '600519')
            start_date: Start date 'YYYYMMDD' or 'YYYY-MM-DD'
            end_date: End date 'YYYYMMDD' or 'YYYY-MM-DD'
            period: Data period ('1y', '5y', etc.) if dates not specified

        Returns:
            DataFrame with columns [date, open, high, low, close, volume]
            or None on failure
        """
        def _fetch():
            # Calculate dates if not provided
            if not start_date or not end_date:
                end = datetime.now()
                if period == '1y':
                    start = end - timedelta(days=365)
                elif period == '5y':
                    start = end - timedelta(days=365*5)
                elif period == '10y':
                    start = end - timedelta(days=365*10)
                else:
                    start = end - timedelta(days=365)  # Default 1 year

                start_str = start.strftime('%Y%m%d')
                end_str = end.strftime('%Y%m%d')
            else:
                # Remove hyphens if present
                start_str = start_date.replace('-', '')
                end_str = end_date.replace('-', '')

            # Fetch data
            df = ak.stock_zh_a_hist(
                symbol=ticker,
                period='daily',
                start_date=start_str,
                end_date=end_str,
                adjust='qfq'  # Forward adjusted for splits/dividends
            )

            if df is None or df.empty:
                raise ValueError(f"No OHLCV data for {ticker}")

            # Rename columns to English
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume',
                '成交额': 'amount'
            })

            # Keep only OHLCV columns
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'])

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} days of OHLCV for {ticker}")

        return result

    def get_industry_classification(self) -> Optional[pd.DataFrame]:
        """
        Get industry classification for all stocks

        Uses: ak.stock_board_industry_name_em()

        Returns:
            DataFrame with stock codes and industry classifications
            or None on failure
        """
        def _fetch():
            df = ak.stock_board_industry_name_em()

            if df is None or df.empty:
                raise ValueError("No industry classification data")

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched industry classification for {len(result)} stocks")

        return result

    def get_concept_classification(self) -> Optional[pd.DataFrame]:
        """
        Get concept classification for stocks (themes)

        Uses: ak.stock_board_concept_name_em()

        Returns:
            DataFrame with concept/theme classifications
            or None on failure
        """
        def _fetch():
            df = ak.stock_board_concept_name_em()

            if df is None or df.empty:
                raise ValueError("No concept classification data")

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} concept classifications")

        return result

    def validate_ticker(self, ticker: str) -> bool:
        """
        Check if ticker exists and has data

        Args:
            ticker: Stock code (6 digits)

        Returns:
            True if valid, False otherwise
        """
        # Basic format check (6 digits starting with 0, 3, or 6)
        if not ticker or len(ticker) != 6:
            return False

        if not ticker[0] in ['0', '3', '6']:
            return False

        # Try to fetch data
        info = self.get_stock_info(ticker)
        return info is not None

    def normalize_ticker(self, ticker: str) -> Optional[str]:
        """
        Normalize ticker format

        Args:
            ticker: Stock code (may include prefix like 'SH600519' or 'SZ000001')

        Returns:
            Normalized 6-digit code (e.g., '600519') or None if invalid
        """
        if not ticker:
            return None

        # Remove common prefixes
        ticker = ticker.upper()
        for prefix in ['SH', 'SZ', 'CN']:
            if ticker.startswith(prefix):
                ticker = ticker[len(prefix):]

        # Check if 6 digits
        if len(ticker) == 6 and ticker.isdigit():
            return ticker

        return None

    def get_exchange(self, ticker: str) -> str:
        """
        Determine exchange from ticker code

        Args:
            ticker: Stock code (6 digits)

        Returns:
            'SSE' (Shanghai) or 'SZSE' (Shenzhen)
        """
        if ticker.startswith('6'):
            return 'SSE'  # Shanghai Stock Exchange
        elif ticker.startswith(('0', '3')):
            return 'SZSE'  # Shenzhen Stock Exchange
        else:
            return 'UNKNOWN'
