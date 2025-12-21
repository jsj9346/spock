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

    # =========================================================================
    # CN/HK Fundamental Data Methods (Added for Phase 6)
    # =========================================================================

    def get_cn_financial_indicators(self,
                                    ticker: str,
                                    start_year: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get financial analysis indicators for CN A-share stock (86 indicators)

        Uses: ak.stock_financial_analysis_indicator()

        Args:
            ticker: Stock code (e.g., '600519' for Moutai)
            start_year: Starting year for data (e.g., '2020'). Default: current year - 2

        Returns:
            DataFrame with 86 financial indicators including:
            - 摊薄每股收益(元): Diluted EPS
            - 每股净资产_调整前(元): BPS (before adjustment)
            - 净资产收益率(%): ROE
            - 总资产利润率(%): ROA
            - 资产负债率(%): Debt ratio
            - 流动比率: Current ratio
            - 销售毛利率(%): Gross margin
            - 销售净利率(%): Net margin
            Or None on failure
        """
        def _fetch():
            # Default to 2 years of data if not specified
            if not start_year:
                year = str(datetime.now().year - 2)
            else:
                year = start_year

            df = ak.stock_financial_analysis_indicator(symbol=ticker, start_year=year)

            if df is None or df.empty:
                raise ValueError(f"No financial indicators for CN:{ticker}")

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} periods of financial indicators for CN:{ticker}")

        return result

    def get_cn_earnings_batch(self, report_date: str) -> Optional[pd.DataFrame]:
        """
        Get earnings report for all CN A-shares (batch collection)

        Uses: ak.stock_yjbb_em()

        Args:
            report_date: Report date in YYYYMMDD format (e.g., '20240930' for Q3 2024)
                        Common dates: 03-31 (Q1), 06-30 (Q2), 09-30 (Q3), 12-31 (Q4)

        Returns:
            DataFrame with earnings data for ~5,900 stocks including:
            - 股票代码: Stock code
            - 股票简称: Stock name
            - 每股收益: EPS
            - 营业总收入-营业总收入: Total revenue
            - 营业总收入-同比增长: Revenue YoY growth
            - 净利润-净利润: Net income
            - 净利润-同比增长: Net income YoY growth
            - 净资产收益率: ROE
            - 销售毛利率: Gross margin
            Or None on failure
        """
        def _fetch():
            df = ak.stock_yjbb_em(date=report_date)

            if df is None or df.empty:
                raise ValueError(f"No earnings data for date {report_date}")

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.info(f"✅ Fetched earnings batch: {len(result)} CN stocks for {report_date}")

        return result

    def get_hk_stock_list(self) -> Optional[pd.DataFrame]:
        """
        Get real-time stock list for Hong Kong Exchange (dynamic ticker expansion)

        Uses: ak.stock_hk_spot_em()

        Returns:
            DataFrame with ~4,600 HK stocks including:
            - 代码: Stock code (e.g., '00700')
            - 名称: Stock name
            - 最新价: Current price
            - 涨跌幅: Change percent
            - 成交量: Volume
            - 成交额: Amount
            Or None on failure
        """
        def _fetch():
            df = ak.stock_hk_spot_em()

            if df is None or df.empty:
                raise ValueError("No HK stock list data")

            # Rename columns to English
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_percent',
                '成交量': 'volume',
                '成交额': 'amount'
            })

            return df

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.info(f"✅ Fetched {len(result)} HK stocks from real-time list")

        return result

    def get_hk_financial_indicators(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get financial analysis indicators for HK stock (36 indicators)

        Uses: ak.stock_financial_hk_analysis_indicator_em()

        Args:
            ticker: HK stock code (e.g., '00700' for Tencent, '09988' for Alibaba)

        Returns:
            DataFrame with 36 financial indicators including:
            - BASIC_EPS: Earnings per share
            - BPS: Book value per share
            - ROE_AVG: Return on equity (average)
            - ROA: Return on assets
            - DEBT_ASSET_RATIO: Debt to asset ratio
            - CURRENT_RATIO: Current ratio
            - GROSS_PROFIT_RATIO: Gross profit margin
            - NET_PROFIT_RATIO: Net profit margin
            - OPERATE_INCOME: Operating income
            - HOLDER_PROFIT: Net profit attributable to shareholders
            Or None on failure
        """
        def _fetch():
            try:
                df = ak.stock_financial_hk_analysis_indicator_em(symbol=ticker)

                if df is None or df.empty:
                    raise ValueError(f"No financial indicators for HK:{ticker}")

                return df
            except (TypeError, AttributeError, KeyError) as e:
                # Handle cases where akshare returns invalid data structure
                raise ValueError(f"Invalid data structure for HK:{ticker}: {e}")

        result = self._retry_on_failure(_fetch)

        if result is not None:
            logger.debug(f"✅ Fetched {len(result)} periods of financial indicators for HK:{ticker}")

        return result
