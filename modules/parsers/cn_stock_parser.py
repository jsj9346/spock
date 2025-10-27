"""
China Stock Parser - Parse AkShare/yfinance responses for Chinese stocks

Normalizes AkShare and yfinance API responses to standardized format for database storage.

Key Features:
- Ticker normalization: "600519" → "600519" (SSE), "000001" → "000001" (SZSE)
- CSRC industry → GICS sector mapping
- Hybrid parser (AkShare primary, yfinance fallback)
- SSE/SZSE exchange detection
- Validation and filtering

Author: Spock Trading System
"""

import pandas as pd
import json
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CNStockParser:
    """
    Parser for Chinese stock data from AkShare and yfinance

    Usage:
        parser = CNStockParser()
        ticker_data = parser.parse_akshare_stock_list(akshare_df)
        ohlcv_df = parser.parse_ohlcv_data(akshare_df, ticker='600519')
    """

    # GICS 11 sectors
    GICS_SECTORS = {
        '10': 'Energy',
        '15': 'Materials',
        '20': 'Industrials',
        '25': 'Consumer Discretionary',
        '30': 'Consumer Staples',
        '35': 'Health Care',
        '40': 'Financials',
        '45': 'Information Technology',
        '50': 'Communication Services',
        '55': 'Utilities',
        '60': 'Real Estate'
    }

    def __init__(self):
        """Initialize China stock parser and load CSRC→GICS mapping"""
        self.csrc_mapping = self._load_csrc_mapping()
        logger.info("🇨🇳 CNStockParser initialized")

    def _load_csrc_mapping(self) -> Dict:
        """Load CSRC to GICS sector mapping from JSON file"""
        try:
            mapping_file = Path(__file__).parent.parent.parent / 'config' / 'sector_mappings' / 'csrc_to_gics_mapping.json'

            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)

            logger.info(f"✅ Loaded CSRC mapping: {len(mapping.get('csrc_to_gics_mapping', {}))} industries")
            return mapping

        except Exception as e:
            logger.error(f"❌ Failed to load CSRC mapping: {e}")
            return {}

    def parse_akshare_stock_list(self, akshare_df: pd.DataFrame) -> List[Dict]:
        """
        Parse AkShare stock list to standardized format

        Args:
            akshare_df: DataFrame from ak.stock_zh_a_spot_em()

        Returns:
            List of standardized ticker dictionaries

        Example output:
            [
                {
                    'ticker': '600519',
                    'name': '贵州茅台',
                    'name_eng': 'Kweichow Moutai',
                    'exchange': 'SSE',
                    'region': 'CN',
                    'currency': 'CNY',
                    'market_cap': 2000000000000,
                    'data_source': 'akshare'
                },
                ...
            ]
        """
        if akshare_df is None or akshare_df.empty:
            logger.warning("⚠️ Empty AkShare stock list")
            return []

        stocks = []

        for _, row in akshare_df.iterrows():
            try:
                ticker = str(row.get('code', row.get('代码', ''))).zfill(6)
                name = row.get('name', row.get('名称', ''))

                if not ticker or not name:
                    continue

                # Determine exchange
                exchange = self.get_exchange(ticker)

                # Extract market cap (in CNY)
                market_cap = row.get('market_cap', row.get('总市值'))
                if pd.notna(market_cap):
                    market_cap = float(market_cap)
                else:
                    market_cap = None

                # Extract current price
                price = row.get('price', row.get('最新价'))
                if pd.notna(price):
                    price = float(price)
                else:
                    price = None

                stock_data = {
                    'ticker': ticker,
                    'name': name,
                    'name_eng': None,  # Will be enriched later
                    'exchange': exchange,
                    'region': 'CN',
                    'currency': 'CNY',
                    'market_cap': market_cap,
                    'close_price': price,
                    'data_source': 'akshare'
                }

                stocks.append(stock_data)

            except Exception as e:
                logger.error(f"❌ Parse error for row: {e}")
                continue

        logger.info(f"✅ Parsed {len(stocks)} stocks from AkShare")
        return stocks

    def parse_akshare_stock_info(self, akshare_info: Dict, ticker: str) -> Optional[Dict]:
        """
        Parse AkShare stock info to standardized format

        Args:
            akshare_info: Dictionary from ak.stock_individual_info_em()
            ticker: Stock ticker code

        Returns:
            Standardized ticker dictionary or None if invalid
        """
        try:
            if not akshare_info:
                return None

            # Extract industry classification
            industry = akshare_info.get('所属行业', akshare_info.get('行业'))

            # Map to GICS sector
            sector = self._map_csrc_to_gics(industry)

            # Extract market cap
            market_cap_str = akshare_info.get('总市值', akshare_info.get('市值'))
            market_cap = self._parse_market_cap(market_cap_str)

            return {
                'ticker': ticker,
                'name': akshare_info.get('股票简称', akshare_info.get('名称')),
                'exchange': self.get_exchange(ticker),
                'region': 'CN',
                'currency': 'CNY',
                'sector': sector,
                'industry': industry,
                'market_cap': market_cap,
                'data_source': 'akshare'
            }

        except Exception as e:
            logger.error(f"❌ Parse error for {ticker}: {e}")
            return None

    def parse_yfinance_info(self, yfinance_info: Dict, ticker: str) -> Optional[Dict]:
        """
        Parse yfinance stock info (fallback data source)

        Args:
            yfinance_info: Dictionary from yf.Ticker(symbol).info
            ticker: Stock ticker code (6 digits)

        Returns:
            Standardized ticker dictionary or None if invalid
        """
        try:
            if not yfinance_info or 'symbol' not in yfinance_info:
                return None

            # Get industry from yfinance
            industry = yfinance_info.get('industry')
            sector = yfinance_info.get('sector', 'Industrials')  # yfinance may have GICS sector

            # Map Chinese industry if available
            if industry:
                sector = self._map_csrc_to_gics(industry)

            return {
                'ticker': ticker,
                'name': yfinance_info.get('longName', yfinance_info.get('shortName', ticker)),
                'name_eng': yfinance_info.get('longName'),
                'exchange': self.get_exchange(ticker),
                'region': 'CN',
                'currency': 'CNY',
                'sector': sector,
                'industry': industry,
                'market_cap': yfinance_info.get('marketCap'),
                'data_source': 'yfinance'
            }

        except Exception as e:
            logger.error(f"❌ Parse error for {ticker}: {e}")
            return None

    def parse_ohlcv_data(self,
                         ohlcv_df: pd.DataFrame,
                         ticker: str,
                         source: str = 'akshare') -> Optional[pd.DataFrame]:
        """
        Parse OHLCV DataFrame to standardized format (supports both AkShare and yfinance)

        Args:
            ohlcv_df: DataFrame from ak.stock_zh_a_hist() or yf.Ticker().history()
            ticker: Stock ticker code
            source: 'akshare' or 'yfinance'

        Returns:
            Standardized OHLCV DataFrame or None if invalid

        DataFrame columns:
            [ticker, date, open, high, low, close, volume]
        """
        try:
            if ohlcv_df is None or ohlcv_df.empty:
                logger.warning(f"⚠️ Empty OHLCV data for {ticker}")
                return None

            df = ohlcv_df.copy()

            # Ensure date column exists
            if 'date' not in df.columns:
                if df.index.name == 'Date' or isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
                    df = df.rename(columns={'Date': 'date'})

            # Standardize column names (lowercase)
            df.columns = df.columns.str.lower()

            # Add ticker column
            df['ticker'] = ticker

            # Select and reorder columns
            required_cols = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']

            # Check if all required columns exist
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"❌ Missing columns for {ticker}: {missing_cols}")
                return None

            df = df[required_cols]

            # Convert date to datetime
            df['date'] = pd.to_datetime(df['date'])

            # Sort by date ascending
            df = df.sort_values('date')

            # Remove rows with NaN values
            df = df.dropna()

            logger.debug(f"✅ Parsed {len(df)} days of OHLCV for {ticker} (source: {source})")
            return df

        except Exception as e:
            logger.error(f"❌ OHLCV parse error for {ticker}: {e}")
            return None

    def normalize_ticker(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize CN ticker format: Remove prefixes, ensure 6 digits

        Args:
            raw_ticker: Raw ticker (e.g., "SH600519", "600519", "SZ000001")

        Returns:
            Normalized 6-digit ticker (e.g., "600519") or None if invalid
        """
        if not raw_ticker:
            return None

        ticker = raw_ticker.upper()

        # Remove common prefixes
        for prefix in ['SH', 'SZ', 'CN']:
            if ticker.startswith(prefix):
                ticker = ticker[len(prefix):]

        # Remove suffix if present (e.g., ".SS", ".SZ")
        if '.' in ticker:
            ticker = ticker.split('.')[0]

        # Ensure 6 digits
        if not ticker.isdigit() or len(ticker) != 6:
            logger.warning(f"⚠️ Invalid CN ticker format: {raw_ticker}")
            return None

        return ticker

    def denormalize_ticker_yfinance(self, ticker: str) -> str:
        """
        Convert normalized ticker to yfinance format

        Args:
            ticker: Normalized ticker (e.g., "600519")

        Returns:
            yfinance ticker format (e.g., "600519.SS" for SSE, "000001.SZ" for SZSE)
        """
        if not ticker:
            return ""

        exchange = self.get_exchange(ticker)

        if exchange == 'SSE':
            return f"{ticker}.SS"  # Shanghai Stock Exchange
        elif exchange == 'SZSE':
            return f"{ticker}.SZ"  # Shenzhen Stock Exchange
        else:
            return ticker

    def get_exchange(self, ticker: str) -> str:
        """
        Determine exchange from ticker code

        Args:
            ticker: Stock code (6 digits)

        Returns:
            'SSE' (Shanghai) or 'SZSE' (Shenzhen)
        """
        if not ticker or len(ticker) != 6:
            return 'UNKNOWN'

        if ticker.startswith('6'):
            return 'SSE'  # Shanghai Stock Exchange (600xxx, 601xxx, 603xxx, etc.)
        elif ticker.startswith(('0', '3')):
            return 'SZSE'  # Shenzhen Stock Exchange (000xxx, 002xxx, 300xxx)
        else:
            return 'UNKNOWN'

    def _map_csrc_to_gics(self, industry: Optional[str]) -> str:
        """
        Map CSRC industry classification to GICS sector

        Args:
            industry: Industry string from CSRC or AkShare

        Returns:
            GICS sector name (default: 'Industrials')
        """
        if not industry or not self.csrc_mapping:
            return 'Industrials'

        # Direct mapping
        csrc_map = self.csrc_mapping.get('csrc_to_gics_mapping', {})
        if industry in csrc_map:
            return csrc_map[industry]['sector']

        # Fuzzy keyword matching
        fuzzy_keywords = self.csrc_mapping.get('fuzzy_keywords', {})
        for keyword, sector in fuzzy_keywords.items():
            if keyword in industry:
                logger.debug(f"Fuzzy match: '{industry}' → {sector}")
                return sector

        # Default fallback
        logger.debug(f"⚠️ Unknown industry '{industry}', defaulting to Industrials")
        return 'Industrials'

    def _parse_market_cap(self, market_cap_str: Optional[str]) -> Optional[float]:
        """
        Parse market cap string to float (in CNY)

        Args:
            market_cap_str: Market cap string (e.g., "2.5万亿", "500亿")

        Returns:
            Market cap in CNY or None
        """
        if not market_cap_str or pd.isna(market_cap_str):
            return None

        try:
            # Convert to string if not already
            mc_str = str(market_cap_str)

            # Remove commas
            mc_str = mc_str.replace(',', '')

            # Handle Chinese units
            if '万亿' in mc_str:  # Trillion (万亿 = 10^12)
                value = float(mc_str.replace('万亿', ''))
                return value * 1e12
            elif '亿' in mc_str:  # Hundred million (亿 = 10^8)
                value = float(mc_str.replace('亿', ''))
                return value * 1e8
            elif '万' in mc_str:  # Ten thousand (万 = 10^4)
                value = float(mc_str.replace('万', ''))
                return value * 1e4
            else:
                return float(mc_str)

        except Exception as e:
            logger.debug(f"⚠️ Failed to parse market cap '{market_cap_str}': {e}")
            return None

    def validate_ticker_format(self, ticker: str) -> bool:
        """
        Validate CN ticker format

        Args:
            ticker: Ticker to validate

        Returns:
            True if valid, False otherwise
        """
        if not ticker or len(ticker) != 6:
            return False

        # Must be 6 digits starting with 0, 3, or 6
        if not ticker.isdigit():
            return False

        if ticker[0] not in ['0', '3', '6']:
            return False

        return True

    def filter_common_stocks(self, tickers: List[Dict]) -> List[Dict]:
        """
        Filter to keep only common stocks (exclude special types)

        Args:
            tickers: List of ticker dictionaries

        Returns:
            Filtered list of common stocks
        """
        common_stocks = []

        for ticker_data in tickers:
            ticker = ticker_data.get('ticker', '')
            name = ticker_data.get('name', '')

            # Exclude special types by name patterns
            if any(keyword in name for keyword in ['ST', 'PT', '*ST', 'S*ST', 'SST']):
                # ST stocks: Special Treatment (financial issues)
                logger.debug(f"⚠️ Filtered out ST stock: {ticker} ({name})")
                continue

            if 'B' in name or '退市' in name:
                # B shares or delisted stocks
                logger.debug(f"⚠️ Filtered out special stock: {ticker} ({name})")
                continue

            common_stocks.append(ticker_data)

        logger.info(f"✅ Filtered to {len(common_stocks)}/{len(tickers)} common stocks")
        return common_stocks
