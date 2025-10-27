"""
Vietnam Stock Parser - Parse yfinance responses for Vietnamese stocks

Normalizes yfinance API responses to standardized format for database storage.

Key Features:
- Ticker normalization: "VCB.VN" → "VCB"
- ICB (Industry Classification Benchmark) → GICS 11 Sectors mapping
- HOSE/HNX-specific data parsing
- Validation and filtering (REITs, preferred stocks, ETFs)

Author: Spock Trading System
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VNStockParser:
    """
    Parser for Vietnamese stock data from yfinance

    Supports both HOSE (Ho Chi Minh Stock Exchange) and HNX (Hanoi Stock Exchange)

    Usage:
        parser = VNStockParser()
        ticker_data = parser.parse_ticker_info(yfinance_info)
        ohlcv_df = parser.parse_ohlcv_data(yfinance_history, ticker='VCB')
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

    # yfinance Industry → GICS mapping
    # Vietnamese stocks use Yahoo Finance's global industry taxonomy
    INDUSTRY_TO_GICS = {
        # Financials (dominant in Vietnam)
        'Banks—Regional': 'Financials',
        'Banks—Diversified': 'Financials',
        'Insurance—Life': 'Financials',
        'Insurance—Property & Casualty': 'Financials',
        'Insurance—Diversified': 'Financials',
        'Asset Management': 'Financials',
        'Capital Markets': 'Financials',
        'Financial Data & Stock Exchanges': 'Financials',
        'Credit Services': 'Financials',

        # Technology & Communication
        'Software—Application': 'Information Technology',
        'Software—Infrastructure': 'Information Technology',
        'Information Technology Services': 'Information Technology',
        'Computer Hardware': 'Information Technology',
        'Electronic Components': 'Information Technology',
        'Semiconductors': 'Information Technology',
        'Telecommunications Services': 'Communication Services',
        'Internet Content & Information': 'Communication Services',
        'Broadcasting': 'Communication Services',

        # Consumer
        'Beverages—Non-Alcoholic': 'Consumer Staples',
        'Beverages—Alcoholic': 'Consumer Staples',
        'Food Distribution': 'Consumer Staples',
        'Packaged Foods': 'Consumer Staples',
        'Household & Personal Products': 'Consumer Staples',
        'Tobacco': 'Consumer Staples',
        'Grocery Stores': 'Consumer Staples',
        'Retail—Apparel & Specialty': 'Consumer Discretionary',
        'Retail—Cyclical': 'Consumer Discretionary',
        'Department Stores': 'Consumer Discretionary',
        'Restaurants': 'Consumer Discretionary',
        'Auto Manufacturers': 'Consumer Discretionary',
        'Auto Parts': 'Consumer Discretionary',

        # Real Estate
        'Real Estate—Development': 'Real Estate',
        'Real Estate—Diversified': 'Real Estate',
        'Real Estate Services': 'Real Estate',
        'REIT—Diversified': 'Real Estate',
        'REIT—Retail': 'Real Estate',
        'REIT—Residential': 'Real Estate',
        'REIT—Industrial': 'Real Estate',
        'REIT—Office': 'Real Estate',

        # Materials (Steel, Cement)
        'Steel': 'Materials',
        'Aluminum': 'Materials',
        'Copper': 'Materials',
        'Building Materials': 'Materials',
        'Chemicals': 'Materials',
        'Paper & Paper Products': 'Materials',
        'Packaging & Containers': 'Materials',

        # Energy & Utilities
        'Oil & Gas Integrated': 'Energy',
        'Oil & Gas Exploration & Production': 'Energy',
        'Oil & Gas Refining & Marketing': 'Energy',
        'Oil & Gas Equipment & Services': 'Energy',
        'Utilities—Regulated Electric': 'Utilities',
        'Utilities—Regulated Gas': 'Utilities',
        'Utilities—Regulated Water': 'Utilities',
        'Utilities—Independent Power Producers': 'Utilities',
        'Utilities—Diversified': 'Utilities',

        # Industrials
        'Conglomerates': 'Industrials',
        'Aerospace & Defense': 'Industrials',
        'Engineering & Construction': 'Industrials',
        'Infrastructure Operations': 'Industrials',
        'Building Products & Equipment': 'Industrials',
        'Electrical Equipment & Parts': 'Industrials',
        'Machinery': 'Industrials',
        'Industrial Distribution': 'Industrials',
        'Airlines': 'Industrials',
        'Railroads': 'Industrials',
        'Marine Shipping': 'Industrials',
        'Trucking': 'Industrials',
        'Airport Services': 'Industrials',
        'Integrated Freight & Logistics': 'Industrials',

        # Health Care
        'Drug Manufacturers—General': 'Health Care',
        'Drug Manufacturers—Specialty & Generic': 'Health Care',
        'Biotechnology': 'Health Care',
        'Medical Devices': 'Health Care',
        'Medical Instruments & Supplies': 'Health Care',
        'Health Care Plans': 'Health Care',
        'Medical Care Facilities': 'Health Care',
        'Pharmaceuticals': 'Health Care',
    }

    # Fuzzy keyword matching for industry classification
    INDUSTRY_KEYWORDS = {
        'Financials': ['bank', 'insurance', 'finance', 'securities', 'asset management', 'credit'],
        'Information Technology': ['technology', 'software', 'hardware', 'IT', 'computer', 'semiconductor', 'electronic'],
        'Communication Services': ['telecom', 'internet', 'media', 'broadcasting', 'communication'],
        'Consumer Staples': ['food', 'beverage', 'dairy', 'grocery', 'tobacco', 'household'],
        'Consumer Discretionary': ['retail', 'restaurant', 'auto', 'apparel', 'hotel', 'travel'],
        'Real Estate': ['real estate', 'property', 'REIT', 'land', 'housing'],
        'Materials': ['steel', 'cement', 'aluminum', 'chemical', 'paper', 'material', 'mining'],
        'Energy': ['oil', 'gas', 'petroleum', 'energy', 'fuel'],
        'Utilities': ['utility', 'electric', 'power', 'water', 'gas utility'],
        'Industrials': ['construction', 'engineering', 'machinery', 'transport', 'logistics', 'airline', 'shipping'],
        'Health Care': ['pharma', 'medical', 'health', 'hospital', 'biotech', 'drug'],
    }

    def __init__(self):
        """Initialize VN Stock Parser"""
        pass

    def normalize_ticker(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize yfinance ticker to database format

        Args:
            raw_ticker: Raw ticker from yfinance (e.g., "VCB.VN", "FPT.vn")

        Returns:
            Normalized ticker (e.g., "VCB") or None if invalid
        """
        if not raw_ticker:
            return None

        # Convert to uppercase and remove .VN suffix
        ticker = raw_ticker.upper().replace('.VN', '')

        # Validate format: 3 uppercase letters (VCB, FPT, HPG, etc.)
        if not re.match(r'^[A-Z]{3}$', ticker):
            logger.warning(f"⚠️  Invalid Vietnamese ticker format: {raw_ticker}")
            return None

        return ticker

    def denormalize_ticker(self, ticker: str) -> str:
        """
        Convert normalized ticker to yfinance format

        Args:
            ticker: Normalized ticker (e.g., "VCB")

        Returns:
            yfinance-compatible ticker (e.g., "VCB.VN")
        """
        if not ticker:
            return ""

        # Add .VN suffix for Vietnamese Stock Exchange
        return f"{ticker}.VN"

    def parse_ticker_info(self, yfinance_info: Dict) -> Optional[Dict]:
        """
        Parse yfinance ticker info to standardized format

        Args:
            yfinance_info: Dictionary from yfinance Ticker.info

        Returns:
            Standardized ticker data dictionary or None if invalid
        """
        if not yfinance_info:
            return None

        try:
            # Extract raw ticker and normalize
            raw_ticker = yfinance_info.get('symbol', '')
            ticker = self.normalize_ticker(raw_ticker)

            if not ticker:
                return None

            # Extract company name
            name = yfinance_info.get('longName') or yfinance_info.get('shortName', '')

            # Map industry to GICS sector
            industry = yfinance_info.get('industry', '')
            sector = self._map_industry_to_gics(industry)

            # Extract exchange (HOSE or HNX)
            exchange = yfinance_info.get('exchange', 'HOSE')
            # yfinance might return 'VNM' for Vietnam
            if exchange in ['VNM', 'HCM']:
                exchange = 'HOSE'
            elif exchange == 'HNX':
                exchange = 'HNX'
            else:
                # Default to HOSE for Vietnamese stocks
                exchange = 'HOSE'

            # Extract market cap and listing date
            market_cap = yfinance_info.get('marketCap')
            listing_date_ts = yfinance_info.get('firstTradeDateEpochUtc')
            listing_date = None
            if listing_date_ts:
                listing_date = datetime.fromtimestamp(listing_date_ts).strftime('%Y-%m-%d')

            # Build standardized ticker data
            ticker_data = {
                'ticker': ticker,
                'name': name,
                'name_eng': name,  # yfinance provides English names
                'exchange': exchange,
                'region': 'VN',
                'currency': yfinance_info.get('currency', 'VND'),
                'sector': sector,
                'sector_code': self._get_gics_code(sector),
                'industry': industry,
                'market_cap': market_cap,
                'listing_date': listing_date,
                'close_price': yfinance_info.get('currentPrice') or yfinance_info.get('regularMarketPrice'),
                'data_source': 'yfinance'
            }

            return ticker_data

        except Exception as e:
            logger.error(f"❌ Failed to parse ticker info: {e}")
            return None

    def parse_ohlcv_data(self,
                        yfinance_history: pd.DataFrame,
                        ticker: str) -> Optional[pd.DataFrame]:
        """
        Parse yfinance history data to standardized OHLCV format

        Args:
            yfinance_history: DataFrame from yfinance Ticker.history()
            ticker: Normalized ticker code

        Returns:
            Standardized OHLCV DataFrame or None if empty
        """
        if yfinance_history is None or yfinance_history.empty:
            return None

        try:
            df = yfinance_history.copy()

            # Reset index to make date a column
            if df.index.name == 'Date' or 'Date' in str(type(df.index)):
                df = df.reset_index()

            # Standardize column names
            column_mapping = {
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Dividends': 'dividends',
                'Stock Splits': 'stock_splits'
            }

            df = df.rename(columns=column_mapping)

            # Add ticker column
            df['ticker'] = ticker

            # Convert date to datetime and format
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # Ensure numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Select and order columns
            required_cols = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
            optional_cols = ['dividends', 'stock_splits']

            available_cols = required_cols + [col for col in optional_cols if col in df.columns]
            df = df[available_cols]

            # Remove rows with missing OHLCV data
            df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"❌ Failed to parse OHLCV data for {ticker}: {e}")
            return None

    def parse_fundamentals(self, yfinance_info: Dict, ticker: str) -> Optional[Dict]:
        """
        Parse fundamental data from yfinance

        Args:
            yfinance_info: Dictionary from yfinance Ticker.info
            ticker: Normalized ticker code

        Returns:
            Standardized fundamentals dictionary or None
        """
        if not yfinance_info:
            return None

        try:
            fundamentals = {
                'ticker': ticker,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'market_cap': yfinance_info.get('marketCap'),
                'pe_ratio': yfinance_info.get('trailingPE') or yfinance_info.get('forwardPE'),
                'pb_ratio': yfinance_info.get('priceToBook'),
                'ps_ratio': yfinance_info.get('priceToSalesTrailing12Months'),
                'dividend_yield': yfinance_info.get('dividendYield'),
                'eps': yfinance_info.get('trailingEps'),
                'roe': yfinance_info.get('returnOnEquity'),
                'roa': yfinance_info.get('returnOnAssets'),
                'debt_to_equity': yfinance_info.get('debtToEquity'),
                'current_ratio': yfinance_info.get('currentRatio'),
                'revenue': yfinance_info.get('totalRevenue'),
                'net_income': yfinance_info.get('netIncomeToCommon'),
                'close_price': yfinance_info.get('currentPrice') or yfinance_info.get('regularMarketPrice'),
                'data_source': 'yfinance'
            }

            return fundamentals

        except Exception as e:
            logger.error(f"❌ Failed to parse fundamentals for {ticker}: {e}")
            return None

    def filter_common_stocks(self, ticker_data: Dict) -> bool:
        """
        Filter out REITs, preferred stocks, ETFs

        Args:
            ticker_data: Parsed ticker data dictionary

        Returns:
            True if common stock, False otherwise
        """
        if not ticker_data:
            return False

        # Check industry for REITs
        industry = ticker_data.get('industry', '')
        if 'REIT' in industry:
            return False

        # Check name for preferred stock indicators
        name = ticker_data.get('name', '').upper()
        if any(keyword in name for keyword in ['PREFERRED', 'PREF', 'ETF', 'FUND']):
            return False

        return True

    def _map_industry_to_gics(self, industry: Optional[str]) -> str:
        """
        Map yfinance industry to GICS sector

        Uses direct mapping first, then fuzzy keyword matching

        Args:
            industry: Industry string from yfinance

        Returns:
            GICS sector name (defaults to 'Industrials' if no match)
        """
        if not industry:
            return 'Industrials'

        # Try direct mapping first
        if industry in self.INDUSTRY_TO_GICS:
            return self.INDUSTRY_TO_GICS[industry]

        # Fuzzy keyword matching
        industry_lower = industry.lower()
        for sector, keywords in self.INDUSTRY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in industry_lower:
                    return sector

        # Default to Industrials if no match
        logger.warning(f"⚠️  Unknown industry '{industry}', defaulting to Industrials")
        return 'Industrials'

    def _get_gics_code(self, sector: str) -> str:
        """
        Get GICS sector code from sector name

        Args:
            sector: GICS sector name

        Returns:
            Two-digit GICS code or '20' (Industrials) as default
        """
        for code, name in self.GICS_SECTORS.items():
            if name == sector:
                return code
        return '20'  # Default to Industrials
