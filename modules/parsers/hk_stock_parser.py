"""
Hong Kong Stock Parser - Parse yfinance responses for HK stocks

Normalizes yfinance API responses to standardized format for database storage.

Key Features:
- Ticker normalization: "0700.HK" → "0700"
- HK industry → GICS sector mapping
- HKEX-specific data parsing
- Validation and filtering

Author: Spock Trading System
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HKStockParser:
    """
    Parser for Hong Kong stock data from yfinance

    Usage:
        parser = HKStockParser()
        ticker_data = parser.parse_ticker_info(yfinance_info)
        ohlcv_df = parser.parse_ohlcv_data(yfinance_history, ticker='0700')
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

    # HK Industry to GICS mapping (simplified)
    # Based on common HKEX industry classifications
    INDUSTRY_TO_GICS = {
        # Technology
        'Internet Content & Information': 'Communication Services',
        'Electronic Gaming & Multimedia': 'Communication Services',
        'Software—Application': 'Information Technology',
        'Software—Infrastructure': 'Information Technology',
        'Semiconductors': 'Information Technology',
        'Consumer Electronics': 'Information Technology',
        'Computer Hardware': 'Information Technology',

        # Financials
        'Banks—Regional': 'Financials',
        'Banks—Diversified': 'Financials',
        'Insurance—Life': 'Financials',
        'Insurance—Property & Casualty': 'Financials',
        'Asset Management': 'Financials',
        'Capital Markets': 'Financials',

        # Real Estate
        'Real Estate—Development': 'Real Estate',
        'Real Estate—Diversified': 'Real Estate',
        'Real Estate Services': 'Real Estate',
        'REIT—Diversified': 'Real Estate',

        # Consumer
        'Restaurants': 'Consumer Discretionary',
        'Apparel Manufacturing': 'Consumer Discretionary',
        'Luxury Goods': 'Consumer Discretionary',
        'Department Stores': 'Consumer Discretionary',
        'Specialty Retail': 'Consumer Discretionary',
        'Beverages—Non-Alcoholic': 'Consumer Staples',
        'Food Distribution': 'Consumer Staples',
        'Packaged Foods': 'Consumer Staples',

        # Healthcare
        'Drug Manufacturers—General': 'Health Care',
        'Biotechnology': 'Health Care',
        'Medical Devices': 'Health Care',
        'Health Information Services': 'Health Care',

        # Industrials
        'Aerospace & Defense': 'Industrials',
        'Airlines': 'Industrials',
        'Railroads': 'Industrials',
        'Conglomerates': 'Industrials',
        'Engineering & Construction': 'Industrials',

        # Energy & Utilities
        'Oil & Gas E&P': 'Energy',
        'Oil & Gas Integrated': 'Energy',
        'Utilities—Regulated Electric': 'Utilities',
        'Utilities—Diversified': 'Utilities',

        # Materials
        'Steel': 'Materials',
        'Chemicals': 'Materials',
        'Building Materials': 'Materials',
    }

    def __init__(self):
        """Initialize Hong Kong stock parser"""
        logger.info("🇭🇰 HKStockParser initialized")

    def parse_ticker_info(self, yfinance_info: Dict) -> Optional[Dict]:
        """
        Parse yfinance ticker info to standardized format

        Args:
            yfinance_info: Dictionary from yf.Ticker(symbol).info

        Returns:
            Standardized ticker dictionary or None if invalid

        Example output:
            {
                'ticker': '0700.HK',
                'name': 'Tencent Holdings Limited',
                'name_eng': 'Tencent Holdings Limited',
                'exchange': 'HKEX',
                'region': 'HK',
                'currency': 'HKD',
                'sector': 'Communication Services',
                'industry': 'Internet Content & Information',
                'market_cap': 3500000000000,
                'data_source': 'yfinance'
            }

        Note:
            Ticker is normalized to database format (XXXX.HK) using normalize_ticker_db()
        """
        try:
            if not yfinance_info or 'symbol' not in yfinance_info:
                logger.warning("⚠️ Invalid yfinance info (missing symbol)")
                return None

            # Normalize ticker to database format: "0700.HK" → "0700.HK"
            raw_ticker = yfinance_info.get('symbol', '')
            ticker = self.normalize_ticker_db(raw_ticker)

            if not ticker:
                logger.warning(f"⚠️ Invalid HK ticker format: {raw_ticker}")
                return None

            # Get company name
            name = yfinance_info.get('longName') or yfinance_info.get('shortName', ticker)

            # Map industry to GICS sector
            industry = yfinance_info.get('industry')
            sector = self._map_industry_to_gics(industry)

            # Extract market cap
            market_cap = yfinance_info.get('marketCap')

            return {
                'ticker': ticker,
                'name': name,
                'name_eng': name,
                'exchange': 'HKEX',
                'region': 'HK',
                'currency': 'HKD',
                'sector': sector,
                'industry': industry,
                'market_cap': market_cap,
                'quote_type': yfinance_info.get('quoteType', 'EQUITY'),
                'country': yfinance_info.get('country'),
                'data_source': 'yfinance'
            }

        except Exception as e:
            logger.error(f"❌ Parse error: {e}")
            return None

    def parse_ohlcv_data(self,
                         yfinance_history: pd.DataFrame,
                         ticker: str) -> Optional[pd.DataFrame]:
        """
        Parse yfinance OHLCV DataFrame to standardized format

        Args:
            yfinance_history: DataFrame from yf.Ticker(symbol).history()
            ticker: Normalized ticker code (e.g., '0700')

        Returns:
            Standardized OHLCV DataFrame or None if invalid

        DataFrame columns:
            [ticker, date, open, high, low, close, volume]
        """
        try:
            if yfinance_history is None or yfinance_history.empty:
                logger.warning(f"⚠️ Empty OHLCV data for {ticker}")
                return None

            df = yfinance_history.copy()

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

            logger.debug(f"✅ Parsed {len(df)} days of OHLCV for {ticker}")
            return df

        except Exception as e:
            logger.error(f"❌ OHLCV parse error for {ticker}: {e}")
            return None

    def normalize_ticker(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize HK ticker format: "0700.HK" → "0700"

        Args:
            raw_ticker: Raw ticker from yfinance (e.g., "0700.HK")

        Returns:
            Normalized ticker (e.g., "0700") or None if invalid

        Note:
            This returns ticker WITHOUT .HK suffix for internal processing.
            Use normalize_ticker_db() for database storage format.
        """
        if not raw_ticker:
            return None

        # Remove ".HK" suffix if present
        if raw_ticker.endswith('.HK'):
            ticker = raw_ticker[:-3]
        else:
            ticker = raw_ticker

        # Validate format: 4-5 digits
        if not re.match(r'^\d{4,5}$', ticker):
            logger.warning(f"⚠️ Invalid HK ticker format: {raw_ticker}")
            return None

        return ticker

    def normalize_ticker_db(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize HK ticker to database storage format: XXXX.HK or XXXXX.HK

        This is the STANDARD format for all HK tickers in the database.
        Ensures consistency across all tables (ohlcv_data, ticker_fundamentals, etc.)

        Conversion rules:
            - "1", "32", "663" → "0001.HK", "0032.HK", "0663.HK" (pad to 4 digits)
            - "02318" (5-digit, starts with 0) → "2318.HK" (4-digit, remove leading 0)
            - "82318" (5-digit, starts with 8/9) → "82318.HK" (5-digit, RMB traded)
            - "2318.HK" → "2318.HK" (already correct, but pad if short)
            - "0700" (4-digit) → "0700.HK"

        Args:
            raw_ticker: Raw ticker in any format

        Returns:
            Database format ticker (e.g., "0001.HK", "2318.HK", "82318.HK") or None if invalid

        Examples:
            >>> parser.normalize_ticker_db("1")
            "0001.HK"
            >>> parser.normalize_ticker_db("02318")
            "2318.HK"
            >>> parser.normalize_ticker_db("82318")
            "82318.HK"
            >>> parser.normalize_ticker_db("0700.HK")
            "0700.HK"
        """
        if not raw_ticker:
            return None

        # Already has .HK suffix - extract code and normalize
        if raw_ticker.endswith('.HK'):
            code = raw_ticker[:-3]
            # Remove leading zeros and re-normalize
            ticker = ''.join(c for c in code if c.isdigit())
        else:
            # Remove any non-digit characters
            ticker = ''.join(c for c in raw_ticker if c.isdigit())

        if not ticker:
            logger.warning(f"⚠️ Invalid HK ticker (no digits): {raw_ticker}")
            return None

        # 5-digit code starting with 8 or 9 (RMB traded products)
        # Keep all 5 digits: 82318 -> 82318.HK
        if len(ticker) == 5 and ticker[0] in ('8', '9'):
            return f"{ticker}.HK"

        # 5-digit code starting with 0 (standard HK stocks)
        # Remove leading zero: 02318 -> 2318.HK
        if len(ticker) == 5 and ticker[0] == '0':
            ticker = ticker[1:]  # Now 4 digits

        # Pad to minimum 4 digits for yfinance compatibility
        # 1 -> 0001, 32 -> 0032, 663 -> 0663
        if len(ticker) < 4:
            ticker = ticker.zfill(4)

        # Final validation: should be 4 digits now (or 5 for RMB)
        if len(ticker) not in (4, 5):
            logger.warning(f"⚠️ Invalid HK ticker length after normalization: {raw_ticker}")
            return None

        return f"{ticker}.HK"

    def normalize_ticker_akshare(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize HK ticker for AkShare API: "0001.HK" → "00001" (5 digits)

        AkShare HK API requires 5-digit format with leading zeros.

        Args:
            raw_ticker: Raw ticker from DB (e.g., "0001.HK", "0700.HK")

        Returns:
            5-digit ticker for AkShare (e.g., "00001", "00700") or None if invalid
        """
        if not raw_ticker:
            return None

        # Remove ".HK" suffix if present
        if raw_ticker.endswith('.HK'):
            ticker = raw_ticker[:-3]
        else:
            ticker = raw_ticker

        # Remove any non-digit characters
        ticker = ''.join(c for c in ticker if c.isdigit())

        if not ticker:
            logger.warning(f"⚠️ Invalid HK ticker format for AkShare: {raw_ticker}")
            return None

        # Pad to 5 digits with leading zeros (AkShare HK requirement)
        akshare_ticker = ticker.zfill(5)

        return akshare_ticker

    def denormalize_ticker(self, ticker: str) -> str:
        """
        Convert normalized ticker to yfinance format: "0700" → "0700.HK"

        Args:
            ticker: Normalized ticker (e.g., "0700")

        Returns:
            yfinance ticker format (e.g., "0700.HK")
        """
        if not ticker:
            return ""

        # Add ".HK" suffix if not present
        if not ticker.endswith('.HK'):
            return f"{ticker}.HK"

        return ticker

    def _map_industry_to_gics(self, industry: Optional[str]) -> str:
        """
        Map HK industry classification to GICS sector

        Args:
            industry: Industry string from yfinance

        Returns:
            GICS sector name (default: 'Industrials')
        """
        if not industry:
            return 'Industrials'

        # Direct mapping
        if industry in self.INDUSTRY_TO_GICS:
            return self.INDUSTRY_TO_GICS[industry]

        # Fuzzy matching for partial matches
        industry_lower = industry.lower()

        if 'software' in industry_lower or 'tech' in industry_lower or 'semiconductor' in industry_lower:
            return 'Information Technology'
        elif 'internet' in industry_lower or 'media' in industry_lower or 'telecom' in industry_lower:
            return 'Communication Services'
        elif 'bank' in industry_lower or 'insurance' in industry_lower or 'financial' in industry_lower:
            return 'Financials'
        elif 'real estate' in industry_lower or 'reit' in industry_lower or 'property' in industry_lower:
            return 'Real Estate'
        elif 'consumer' in industry_lower or 'retail' in industry_lower or 'apparel' in industry_lower:
            return 'Consumer Discretionary'
        elif 'food' in industry_lower or 'beverage' in industry_lower:
            return 'Consumer Staples'
        elif 'health' in industry_lower or 'pharma' in industry_lower or 'medical' in industry_lower:
            return 'Health Care'
        elif 'energy' in industry_lower or 'oil' in industry_lower or 'gas' in industry_lower:
            return 'Energy'
        elif 'utility' in industry_lower or 'utilities' in industry_lower or 'electric' in industry_lower:
            return 'Utilities'
        elif 'material' in industry_lower or 'chemical' in industry_lower or 'steel' in industry_lower:
            return 'Materials'
        else:
            logger.debug(f"⚠️ Unknown industry '{industry}', defaulting to Industrials")
            return 'Industrials'

    def validate_ticker_format(self, ticker: str, require_suffix: bool = False) -> bool:
        """
        Validate HK ticker format

        Args:
            ticker: Ticker to validate
            require_suffix: If True, require ".HK" suffix

        Returns:
            True if valid, False otherwise
        """
        if not ticker:
            return False

        if require_suffix:
            # Must end with ".HK" and have 4-5 digits before it
            return bool(re.match(r'^\d{4,5}\.HK$', ticker))
        else:
            # Just 4-5 digits
            return bool(re.match(r'^\d{4,5}$', ticker))

    def filter_common_stocks(self, tickers: List[Dict]) -> List[Dict]:
        """
        Filter to keep only common stocks (exclude ETFs, warrants, etc.)

        Args:
            tickers: List of ticker dictionaries

        Returns:
            Filtered list of common stocks
        """
        common_stocks = []

        for ticker_data in tickers:
            quote_type = ticker_data.get('quote_type', 'EQUITY')

            # Keep only EQUITY type
            if quote_type == 'EQUITY':
                common_stocks.append(ticker_data)
            else:
                logger.debug(f"⚠️ Filtered out {ticker_data.get('ticker')}: {quote_type}")

        logger.info(f"✅ Filtered to {len(common_stocks)}/{len(tickers)} common stocks")
        return common_stocks

    # =========================================================================
    # Asset Type Classification (Added for CN/HK Fundamental Improvement)
    # =========================================================================

    def classify_asset_type(self, ticker_info: Dict) -> str:
        """
        Classify HK security as STOCK, ETF, MUTUALFUND, or INDEX

        Args:
            ticker_info: Dictionary with ticker metadata
                        Must contain 'ticker' and optionally 'name', 'quoteType'

        Returns:
            Asset type: 'STOCK', 'ETF', 'MUTUALFUND', or 'INDEX'

        Classification Logic:
            1. Check yfinance quoteType (most reliable)
            2. Check name for ETF/Fund keywords (English + Chinese)
            3. Default to 'STOCK' (conservative fallback)

        Examples:
            >>> parser.classify_asset_type({'ticker': '02800', 'name': 'Tracker Fund', 'quoteType': 'ETF'})
            'ETF'
            >>> parser.classify_asset_type({'ticker': '00700', 'name': 'Tencent Holdings'})
            'STOCK'
            >>> parser.classify_asset_type({'ticker': '00091', 'name': 'HK Equity Fund', 'quoteType': 'MUTUALFUND'})
            'MUTUALFUND'
        """
        # Step 1: Check yfinance quoteType (if available)
        quote_type = ticker_info.get('quoteType', '').upper()

        # quoteType takes absolute precedence over all other classification methods
        if quote_type in ['ETF', 'MUTUALFUND', 'INDEX', 'EQUITY']:
            # EQUITY -> STOCK
            result = 'STOCK' if quote_type == 'EQUITY' else quote_type
            logger.debug(f"Classified {ticker_info.get('ticker')} as {result} (via quoteType={quote_type})")
            return result

        # Step 2: Name-based classification (English and Chinese keywords)
        name = ticker_info.get('name', '').upper()

        # HK ETF keywords (both English and Chinese)
        # Common patterns: "Tracker Fund", "iShares", "SPDR", "Vanguard", "XXX ETF"
        etf_keywords = [
            'ETF', 'TRACKER', 'ISHARES', 'SPDR', 'VANGUARD',
            '指数', '交易型开放式', 'INDEX FUND'
        ]
        if any(keyword in name for keyword in etf_keywords):
            logger.debug(f"Classified {ticker_info.get('ticker')} as ETF (via name: {name})")
            return 'ETF'

        # HK Mutual fund keywords
        # Common patterns: "XXX Fund", "Investment Fund", "基金"
        fund_keywords = [
            'FUND', 'INVESTMENT FUND', 'UNIT TRUST',
            '基金', 'MUTUAL FUND'
        ]
        # Exclude "TRACKER FUND" (already caught as ETF)
        if any(keyword in name for keyword in fund_keywords) and 'TRACKER' not in name:
            logger.debug(f"Classified {ticker_info.get('ticker')} as MUTUALFUND (via name: {name})")
            return 'MUTUALFUND'

        # Step 3: Default to STOCK (conservative fallback)
        logger.debug(f"Classified {ticker_info.get('ticker')} as STOCK (default)")
        return 'STOCK'

    # =========================================================================
    # HK Fundamental Data Parsing Methods (Added for Phase 6 - AkShare)
    # =========================================================================

    # Field mapping: AkShare HK indicators → DB column
    HK_FINANCIAL_INDICATOR_MAPPING = {
        'BASIC_EPS': 'eps',
        'BPS': 'bps',
        'ROE_AVG': 'roe',
        'ROA': 'roa',
        'DEBT_ASSET_RATIO': 'debt_ratio',
        'CURRENT_RATIO': 'current_ratio',
        'GROSS_PROFIT_RATIO': 'gross_margin',
        'NET_PROFIT_RATIO': 'net_margin',
        'OPERATE_INCOME': 'revenue',
        'HOLDER_PROFIT': 'net_income',
        'OPERATE_INCOME_YOY': 'revenue_yoy',
        'HOLDER_PROFIT_YOY': 'net_income_yoy',
        'EPS_TTM': 'eps_ttm',
        'ROE_YEARLY': 'roe_yearly',
        'ROIC_YEARLY': 'roic',
    }

    def _safe_float(self, value, default=None) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or pd.isna(value):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def parse_hk_stock_list(self, akshare_df: pd.DataFrame) -> List[Dict]:
        """
        Parse AkShare HK stock list to standardized format

        Args:
            akshare_df: DataFrame from ak.stock_hk_spot_em()

        Returns:
            List of standardized ticker dictionaries

        Example output:
            [
                {
                    'ticker': '0700.HK',
                    'name': '腾讯控股',
                    'exchange': 'HKEX',
                    'region': 'HK',
                    'currency': 'HKD',
                    'close_price': 350.0,
                    'data_source': 'akshare'
                },
                ...
            ]

        Note:
            Tickers are normalized to database format (XXXX.HK) using normalize_ticker_db()
        """
        if akshare_df is None or akshare_df.empty:
            logger.warning("⚠️ Empty AkShare HK stock list")
            return []

        stocks = []

        for _, row in akshare_df.iterrows():
            try:
                # Extract code (already English from akshare_api.py)
                raw_ticker = str(row.get('code', row.get('代码', ''))).zfill(5)
                name = row.get('name', row.get('名称', ''))

                if not raw_ticker or not name:
                    continue

                # Normalize to database format (XXXX.HK or XXXXX.HK)
                ticker = self.normalize_ticker_db(raw_ticker)
                if not ticker:
                    logger.debug(f"⚠️ Skipping invalid HK ticker: {raw_ticker}")
                    continue

                # Extract price
                price = row.get('price', row.get('最新价'))
                if pd.notna(price):
                    try:
                        price = float(price)
                    except (ValueError, TypeError):
                        price = None
                else:
                    price = None

                stock_data = {
                    'ticker': ticker,
                    'name': name,
                    'name_eng': None,  # Will be enriched via yfinance if needed
                    'exchange': 'HKEX',
                    'region': 'HK',
                    'currency': 'HKD',
                    'close_price': price,
                    'data_source': 'akshare'
                }

                stocks.append(stock_data)

            except Exception as e:
                logger.debug(f"⚠️ Parse error for HK row: {e}")
                continue

        logger.info(f"✅ Parsed {len(stocks)} HK stocks from AkShare (DB format: XXXX.HK)")
        return stocks

    def parse_hk_financial_indicators(self,
                                      df: pd.DataFrame,
                                      ticker: str,
                                      report_date: Optional[str] = None) -> Optional[Dict]:
        """
        Parse HK financial indicator DataFrame to database format

        Args:
            df: DataFrame from ak.stock_financial_hk_analysis_indicator_em()
            ticker: HK stock ticker code (e.g., '00700' or '0700.HK')
            report_date: Specific report date to extract (e.g., '2024-12-31')
                        If None, uses the most recent date

        Returns:
            Dictionary ready for DB insertion or None if invalid

        Example output:
            {
                'ticker': '0700.HK',
                'region': 'HK',
                'date': '2024-12-31',
                'period_type': 'QUARTERLY',
                'eps': 20.938,
                'bps': 106.62,
                'roe': 21.78,
                'roa': 11.56,
                'debt_ratio': 40.83,
                'current_ratio': 1.25,
                'gross_margin': 52.90,
                'net_margin': 21.78,
                'revenue': 660257000000,
                'net_income': 194073000000,
                'data_source': 'akshare'
            }

        Note:
            Ticker is normalized to database format (XXXX.HK) using normalize_ticker_db()
        """
        if df is None or df.empty:
            logger.warning(f"⚠️ Empty financial indicators for HK:{ticker}")
            return None

        # Normalize ticker to database format
        db_ticker = self.normalize_ticker_db(ticker)
        if not db_ticker:
            logger.warning(f"⚠️ Invalid HK ticker for fundamentals: {ticker}")
            return None

        try:
            # Select row based on report_date or use most recent
            if report_date:
                # Find row matching the report date
                if 'REPORT_DATE' in df.columns:
                    df['_parsed_date'] = pd.to_datetime(df['REPORT_DATE']).dt.strftime('%Y-%m-%d')
                    row = df[df['_parsed_date'] == report_date]
                    if row.empty:
                        logger.warning(f"⚠️ No data for date {report_date} for HK:{ticker}")
                        row = df.iloc[[0]]  # Fallback to most recent
                    else:
                        row = row.iloc[[0]]
                else:
                    row = df.iloc[[0]]
            else:
                # Use most recent (first row)
                row = df.iloc[[0]]

            # Safety check before accessing iloc
            if row is None or (hasattr(row, 'empty') and row.empty):
                logger.warning(f"⚠️ No valid row found for HK:{ticker}")
                return None

            row = row.iloc[0]  # Convert to Series

            # Extract report date
            raw_date = row.get('REPORT_DATE', '')
            if raw_date:
                parsed_date = pd.to_datetime(raw_date)
                formatted_date = parsed_date.strftime('%Y-%m-%d')
            else:
                formatted_date = datetime.now().strftime('%Y-%m-%d')

            # Build fundamentals dict with normalized ticker
            fundamentals = {
                'ticker': db_ticker,
                'region': 'HK',
                'date': formatted_date,
                'period_type': 'QUARTERLY',
                'data_source': 'akshare',
                # Core valuation metrics
                'eps': self._safe_float(row.get('BASIC_EPS')),
                'bps': self._safe_float(row.get('BPS')),
                'roe': self._safe_float(row.get('ROE_AVG')),
                'roa': self._safe_float(row.get('ROA')),
                # Debt and liquidity
                'debt_ratio': self._safe_float(row.get('DEBT_ASSET_RATIO')),
                'current_ratio': self._safe_float(row.get('CURRENT_RATIO')),
                # Margins
                'gross_margin': self._safe_float(row.get('GROSS_PROFIT_RATIO')),
                'net_margin': self._safe_float(row.get('NET_PROFIT_RATIO')),
                # Income data
                'revenue': self._safe_float(row.get('OPERATE_INCOME')),
                'revenue_yoy': self._safe_float(row.get('OPERATE_INCOME_YOY')),
                'net_income': self._safe_float(row.get('HOLDER_PROFIT')),
                'net_income_yoy': self._safe_float(row.get('HOLDER_PROFIT_YOY')),
                # TTM and additional metrics
                'eps_ttm': self._safe_float(row.get('EPS_TTM')),
                'roe_yearly': self._safe_float(row.get('ROE_YEARLY')),
                'roic': self._safe_float(row.get('ROIC_YEARLY')),
            }

            logger.debug(f"✅ Parsed financial indicators for HK:{ticker} ({formatted_date})")
            return fundamentals

        except Exception as e:
            logger.error(f"❌ Parse error for HK:{ticker} financial indicators: {e}")
            return None
