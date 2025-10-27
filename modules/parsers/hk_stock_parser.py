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
                'ticker': '0700',
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
        """
        try:
            if not yfinance_info or 'symbol' not in yfinance_info:
                logger.warning("⚠️ Invalid yfinance info (missing symbol)")
                return None

            # Normalize ticker: "0700.HK" → "0700"
            raw_ticker = yfinance_info.get('symbol', '')
            ticker = self.normalize_ticker(raw_ticker)

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
        """
        if not raw_ticker:
            return None

        # Remove ".HK" suffix if present
        if raw_ticker.endswith('.HK'):
            ticker = raw_ticker[:-3]
        else:
            ticker = raw_ticker

        # Validate format: 4 digits
        if not re.match(r'^\d{4,5}$', ticker):
            logger.warning(f"⚠️ Invalid HK ticker format: {raw_ticker}")
            return None

        return ticker

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
