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

    def classify_asset_type(self, ticker_info: Dict) -> str:
        """
        Classify CN security as STOCK, ETF, MUTUALFUND, or INDEX

        Args:
            ticker_info: Dictionary with ticker metadata
                        Must contain 'ticker' and optionally 'name', 'quoteType'

        Returns:
            Asset type: 'STOCK', 'ETF', 'MUTUALFUND', or 'INDEX'

        Classification Logic:
            1. Check yfinance quoteType (most reliable)
            2. Check name for ETF/Fund keywords (ETF, 指数, 基金, LOF, 交易型开放式)
            3. Check ticker pattern (51xxxx, 52xxxx for CN ETFs)
            4. Default to 'STOCK' (conservative fallback)

        Examples:
            >>> parser.classify_asset_type({'ticker': '510050', 'name': 'China 50 ETF'})
            'ETF'
            >>> parser.classify_asset_type({'ticker': '600519', 'name': '贵州茅台'})
            'STOCK'
        """
        # Step 1: Check yfinance quoteType (if available)
        quote_type = ticker_info.get('quoteType', '').upper()

        # quoteType takes absolute precedence over all other classification methods
        if quote_type in ['ETF', 'MUTUALFUND', 'INDEX', 'EQUITY']:
            # EQUITY -> STOCK
            result = 'STOCK' if quote_type == 'EQUITY' else quote_type
            logger.debug(f"Classified {ticker_info.get('ticker')} as {result} (via quoteType={quote_type})")
            return result

        # Step 2: Name-based classification (Chinese keywords)
        name = ticker_info.get('name', '').upper()

        # ETF keywords (Chinese and English)
        etf_keywords = ['ETF', '指数', '交易型开放式指数', 'LOF', '联接']
        if any(keyword in name for keyword in etf_keywords):
            logger.debug(f"Classified {ticker_info.get('ticker')} as ETF (via name: {name})")
            return 'ETF'

        # Mutual fund keywords
        fund_keywords = ['基金', 'FUND']
        if any(keyword in name for keyword in fund_keywords):
            logger.debug(f"Classified {ticker_info.get('ticker')} as MUTUALFUND (via name: {name})")
            return 'MUTUALFUND'

        # Step 3: CN ticker code patterns
        ticker = ticker_info.get('ticker', '')

        # CN ETF patterns:
        # - 51xxxx: Shanghai ETFs (510050, 510300, etc.)
        # - 52xxxx: Shanghai innovation ETFs
        # - 15xxxx: Shenzhen ETFs (159901, 159915, etc.)
        if ticker and len(ticker) == 6:
            if ticker.startswith(('51', '52', '15')):
                logger.debug(f"Classified {ticker} as ETF (via ticker pattern)")
                return 'ETF'

        # Step 4: Default to STOCK (conservative fallback)
        logger.debug(f"Classified {ticker_info.get('ticker')} as STOCK (default)")
        return 'STOCK'

    # =========================================================================
    # CN Fundamental Data Parsing Methods (Added for Phase 6)
    # =========================================================================

    # Field mapping: AkShare Chinese → DB column
    CN_FINANCIAL_INDICATOR_MAPPING = {
        # Core valuation metrics
        '摊薄每股收益(元)': 'eps',
        '每股净资产_调整前(元)': 'bps',
        '净资产收益率(%)': 'roe',
        '总资产利润率(%)': 'roa',
        # Debt and liquidity
        '资产负债率(%)': 'debt_ratio',
        '流动比率': 'current_ratio',
        '速动比率': 'quick_ratio',
        # Margins
        '销售毛利率(%)': 'gross_margin',
        '销售净利率(%)': 'net_margin',
        '营业利润率(%)': 'operating_margin',
        # Growth
        '主营业务收入增长率(%)': 'revenue_growth',
        '净利润增长率(%)': 'net_income_growth',
        # Per-share metrics
        '每股经营性现金流(元)': 'operating_cash_flow_per_share',
        '每股资本公积金(元)': 'capital_reserve_per_share',
        '每股未分配利润(元)': 'retained_earnings_per_share',
        # Turnover ratios
        '存货周转率(次)': 'inventory_turnover',
        '应收账款周转率(次)': 'receivables_turnover',
        '总资产周转率(次)': 'asset_turnover',
    }

    # Batch earnings report mapping
    CN_EARNINGS_BATCH_MAPPING = {
        '股票代码': 'ticker',
        '股票简称': 'name',
        '每股收益': 'eps',
        '营业总收入-营业总收入': 'revenue',
        '营业总收入-同比增长': 'revenue_yoy',
        '净利润-净利润': 'net_income',
        '净利润-同比增长': 'net_income_yoy',
        '每股净资产': 'bps',
        '净资产收益率': 'roe',
        '销售毛利率': 'gross_margin',
    }

    def _safe_float(self, value, default=None) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or pd.isna(value):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def parse_cn_financial_indicators(self,
                                      df: pd.DataFrame,
                                      ticker: str,
                                      report_date: Optional[str] = None) -> Optional[Dict]:
        """
        Parse CN financial indicator DataFrame to database format

        Args:
            df: DataFrame from ak.stock_financial_analysis_indicator()
            ticker: Stock ticker code
            report_date: Specific report date to extract (e.g., '2024-09-30')
                        If None, uses the most recent date

        Returns:
            Dictionary ready for DB insertion or None if invalid

        Example output:
            {
                'ticker': '600519',
                'region': 'CN',
                'date': '2024-09-30',
                'period_type': 'QUARTERLY',
                'eps': 43.6453,
                'roe': 24.28,
                'roa': 20.92,
                'debt_ratio': 14.14,
                'current_ratio': 5.96,
                'gross_margin': None,  # Not in this dataset
                'net_margin': 53.09,
                'data_source': 'akshare'
            }
        """
        if df is None or df.empty:
            logger.warning(f"⚠️ Empty financial indicators for CN:{ticker}")
            return None

        try:
            # Select row based on report_date or use most recent
            if report_date:
                # Find row matching the report date
                date_col = '日期' if '日期' in df.columns else df.columns[0]
                df[date_col] = pd.to_datetime(df[date_col]).dt.strftime('%Y-%m-%d')
                row = df[df[date_col] == report_date]
                if row.empty:
                    logger.warning(f"⚠️ No data for date {report_date} for CN:{ticker}")
                    row = df.iloc[[0]]  # Fallback to most recent
                else:
                    row = row.iloc[[0]]
            else:
                # Use most recent (first row)
                row = df.iloc[[0]]

            row = row.iloc[0]  # Convert to Series

            # Extract report date
            date_col = '日期' if '日期' in df.columns else df.columns[0]
            raw_date = str(row.get(date_col, ''))
            # Convert to YYYY-MM-DD format
            if raw_date:
                parsed_date = pd.to_datetime(raw_date)
                formatted_date = parsed_date.strftime('%Y-%m-%d')
            else:
                formatted_date = datetime.now().strftime('%Y-%m-%d')

            # Build fundamentals dict
            fundamentals = {
                'ticker': ticker,
                'region': 'CN',
                'date': formatted_date,
                'period_type': 'QUARTERLY',
                'data_source': 'akshare',
                # Core metrics
                'eps': self._safe_float(row.get('摊薄每股收益(元)')),
                'bps': self._safe_float(row.get('每股净资产_调整前(元)')),
                'roe': self._safe_float(row.get('净资产收益率(%)')),
                'roa': self._safe_float(row.get('总资产利润率(%)')),
                # Debt and liquidity
                'debt_ratio': self._safe_float(row.get('资产负债率(%)')),
                'current_ratio': self._safe_float(row.get('流动比率')),
                'quick_ratio': self._safe_float(row.get('速动比率')),
                # Margins
                'gross_margin': self._safe_float(row.get('销售毛利率(%)')),
                'net_margin': self._safe_float(row.get('销售净利率(%)')),
                'operating_margin': self._safe_float(row.get('营业利润率(%)')),
                # Growth
                'revenue_growth': self._safe_float(row.get('主营业务收入增长率(%)')),
                'net_income_growth': self._safe_float(row.get('净利润增长率(%)')),
                # Turnover
                'asset_turnover': self._safe_float(row.get('总资产周转率(次)')),
                'inventory_turnover': self._safe_float(row.get('存货周转率(次)')),
                'receivables_turnover': self._safe_float(row.get('应收账款周转率(次)')),
            }

            # Calculate PBR from BPS and close price if available
            # PBR = Price / BPS (will be calculated at adapter level with current price)

            logger.debug(f"✅ Parsed financial indicators for CN:{ticker} ({formatted_date})")
            return fundamentals

        except Exception as e:
            logger.error(f"❌ Parse error for CN:{ticker} financial indicators: {e}")
            return None

    def parse_cn_earnings_batch(self, df: pd.DataFrame) -> List[Dict]:
        """
        Parse batch earnings DataFrame to list of database records

        Args:
            df: DataFrame from ak.stock_yjbb_em()

        Returns:
            List of dictionaries ready for DB insertion

        Example output:
            [
                {
                    'ticker': '600519',
                    'region': 'CN',
                    'date': '2024-09-30',
                    'period_type': 'QUARTERLY',
                    'eps': 51.53,
                    'revenue': 130903900000,
                    'net_income': 67688000000,
                    'roe': 25.14,
                    'gross_margin': 75.22,
                    'data_source': 'akshare_batch'
                },
                ...
            ]
        """
        if df is None or df.empty:
            logger.warning("⚠️ Empty batch earnings data")
            return []

        results = []

        # Determine report date from column or use current quarter end
        # The date parameter is passed when calling stock_yjbb_em
        # We'll infer it from the data or use the most recent quarter end

        for _, row in df.iterrows():
            try:
                # Extract ticker (6-digit format)
                ticker_raw = str(row.get('股票代码', '')).zfill(6)

                if not self.validate_ticker_format(ticker_raw):
                    continue

                # Normalize to database format (with .SS or .SZ suffix)
                ticker = self.denormalize_ticker_yfinance(ticker_raw)

                # Extract report date from '最新公告日期' if available
                announce_date = row.get('最新公告日期')
                if announce_date and pd.notna(announce_date):
                    # Infer quarter end from announcement date
                    parsed_date = pd.to_datetime(announce_date)
                    # Map to quarter end
                    quarter_month = ((parsed_date.month - 1) // 3) * 3 + 3
                    if quarter_month == 3:
                        quarter_end = f"{parsed_date.year}-03-31"
                    elif quarter_month == 6:
                        quarter_end = f"{parsed_date.year}-06-30"
                    elif quarter_month == 9:
                        quarter_end = f"{parsed_date.year}-09-30"
                    else:
                        quarter_end = f"{parsed_date.year}-12-31"
                else:
                    # Use current quarter end
                    now = datetime.now()
                    quarter_month = ((now.month - 1) // 3) * 3 + 3
                    if quarter_month == 3:
                        quarter_end = f"{now.year}-03-31"
                    elif quarter_month == 6:
                        quarter_end = f"{now.year}-06-30"
                    elif quarter_month == 9:
                        quarter_end = f"{now.year}-09-30"
                    else:
                        quarter_end = f"{now.year}-12-31"

                fundamentals = {
                    'ticker': ticker,  # Now includes .SS or .SZ suffix
                    'region': 'CN',
                    'date': quarter_end,
                    'period_type': 'QUARTERLY',
                    'data_source': 'akshare_batch',
                    # Core metrics
                    'eps': self._safe_float(row.get('每股收益')),
                    'bps': self._safe_float(row.get('每股净资产')),
                    'roe': self._safe_float(row.get('净资产收益率')),
                    'gross_margin': self._safe_float(row.get('销售毛利率')),
                    # Income data
                    'revenue': self._safe_float(row.get('营业总收入-营业总收入')),
                    'revenue_yoy': self._safe_float(row.get('营业总收入-同比增长')),
                    'net_income': self._safe_float(row.get('净利润-净利润')),
                    'net_income_yoy': self._safe_float(row.get('净利润-同比增长')),
                    # Cash flow
                    'operating_cash_flow_per_share': self._safe_float(row.get('每股经营现金流量')),
                }

                results.append(fundamentals)

            except Exception as e:
                logger.debug(f"⚠️ Skipped row in batch parsing: {e}")
                continue

        logger.info(f"✅ Parsed {len(results)} stocks from batch earnings")
        return results
