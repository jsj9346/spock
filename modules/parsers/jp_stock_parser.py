"""
Japan Stock Parser - Parse yfinance responses for Japanese stocks

Normalizes yfinance API responses to standardized format for database storage.

Key Features:
- Ticker normalization: "7203.T" → "7203"
- TSE 33 Sectors → GICS 11 Sectors mapping
- TSE-specific data parsing
- Validation and filtering (REITs, preferred stocks)

Author: Spock Trading System
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class JPStockParser:
    """
    Parser for Japanese stock data from yfinance

    Usage:
        parser = JPStockParser()
        ticker_data = parser.parse_ticker_info(yfinance_info)
        ohlcv_df = parser.parse_ohlcv_data(yfinance_history, ticker='7203')
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

    # yfinance Industry → GICS mapping (based on Yahoo Finance classifications)
    # Japanese stocks use Yahoo Finance's global industry taxonomy
    INDUSTRY_TO_GICS = {
        # Technology & Communication
        'Consumer Electronics': 'Information Technology',
        'Electronic Components': 'Information Technology',
        'Semiconductors': 'Information Technology',
        'Software—Application': 'Information Technology',
        'Software—Infrastructure': 'Information Technology',
        'Computer Hardware': 'Information Technology',
        'Telecommunications Services': 'Communication Services',
        'Internet Content & Information': 'Communication Services',
        'Electronic Gaming & Multimedia': 'Communication Services',
        'Broadcasting': 'Communication Services',

        # Automotive & Transportation
        'Auto Manufacturers': 'Consumer Discretionary',
        'Auto Parts': 'Consumer Discretionary',
        'Airlines': 'Industrials',
        'Railroads': 'Industrials',
        'Marine Shipping': 'Industrials',
        'Trucking': 'Industrials',

        # Manufacturing & Industrials
        'Aerospace & Defense': 'Industrials',
        'Industrial Distribution': 'Industrials',
        'Electrical Equipment & Parts': 'Industrials',
        'Machinery': 'Industrials',
        'Tools & Accessories': 'Industrials',
        'Building Products & Equipment': 'Industrials',
        'Engineering & Construction': 'Industrials',
        'Infrastructure Operations': 'Industrials',
        'Conglomerates': 'Industrials',

        # Financials
        'Banks—Regional': 'Financials',
        'Banks—Diversified': 'Financials',
        'Insurance—Life': 'Financials',
        'Insurance—Property & Casualty': 'Financials',
        'Insurance—Diversified': 'Financials',
        'Asset Management': 'Financials',
        'Capital Markets': 'Financials',
        'Financial Data & Stock Exchanges': 'Financials',
        'Credit Services': 'Financials',

        # Real Estate
        'Real Estate—Development': 'Real Estate',
        'Real Estate—Diversified': 'Real Estate',
        'Real Estate Services': 'Real Estate',
        'REIT—Diversified': 'Real Estate',
        'REIT—Retail': 'Real Estate',
        'REIT—Residential': 'Real Estate',
        'REIT—Office': 'Real Estate',

        # Consumer Discretionary
        'Restaurants': 'Consumer Discretionary',
        'Apparel Manufacturing': 'Consumer Discretionary',
        'Luxury Goods': 'Consumer Discretionary',
        'Department Stores': 'Consumer Discretionary',
        'Specialty Retail': 'Consumer Discretionary',
        'Leisure': 'Consumer Discretionary',
        'Resorts & Casinos': 'Consumer Discretionary',
        'Gambling': 'Consumer Discretionary',
        'Publishing': 'Consumer Discretionary',
        'Home Improvement Retail': 'Consumer Discretionary',

        # Consumer Staples
        'Beverages—Alcoholic': 'Consumer Staples',
        'Beverages—Non-Alcoholic': 'Consumer Staples',
        'Food Distribution': 'Consumer Staples',
        'Packaged Foods': 'Consumer Staples',
        'Grocery Stores': 'Consumer Staples',
        'Confectioners': 'Consumer Staples',
        'Tobacco': 'Consumer Staples',
        'Personal Products': 'Consumer Staples',
        'Household & Personal Products': 'Consumer Staples',

        # Healthcare & Pharmaceuticals
        'Drug Manufacturers—General': 'Health Care',
        'Drug Manufacturers—Specialty & Generic': 'Health Care',
        'Biotechnology': 'Health Care',
        'Medical Devices': 'Health Care',
        'Medical Instruments & Supplies': 'Health Care',
        'Medical Care Facilities': 'Health Care',
        'Health Information Services': 'Health Care',
        'Diagnostics & Research': 'Health Care',
        'Medical Distribution': 'Health Care',

        # Materials & Chemicals
        'Chemicals': 'Materials',
        'Steel': 'Materials',
        'Aluminum': 'Materials',
        'Copper': 'Materials',
        'Other Industrial Metals & Mining': 'Materials',
        'Paper & Paper Products': 'Materials',
        'Building Materials': 'Materials',
        'Specialty Chemicals': 'Materials',
        'Coking Coal': 'Materials',

        # Energy
        'Oil & Gas E&P': 'Energy',
        'Oil & Gas Integrated': 'Energy',
        'Oil & Gas Refining & Marketing': 'Energy',
        'Oil & Gas Equipment & Services': 'Energy',
        'Thermal Coal': 'Energy',
        'Uranium': 'Energy',

        # Utilities
        'Utilities—Regulated Electric': 'Utilities',
        'Utilities—Regulated Gas': 'Utilities',
        'Utilities—Diversified': 'Utilities',
        'Utilities—Renewable': 'Utilities',
        'Utilities—Independent Power Producers': 'Utilities',
    }

    def __init__(self):
        """Initialize JP Stock Parser"""
        logger.info("📊 JPStockParser initialized")

    def normalize_ticker(self, raw_ticker: str) -> Optional[str]:
        """
        Normalize Japanese ticker format for internal use

        Converts yfinance format to internal format:
        - "7203.T" → "7203" (remove .T suffix)
        - "7203" → "7203" (already normalized)

        Args:
            raw_ticker: Ticker in any format

        Returns:
            Normalized ticker (4-digit code) or None if invalid

        Examples:
            >>> parser.normalize_ticker("7203.T")
            "7203"
            >>> parser.normalize_ticker("7203")
            "7203"
            >>> parser.normalize_ticker("999.T")
            None  # Invalid (must be 4 digits)
        """
        if not raw_ticker:
            return None

        # Remove .T suffix if present
        ticker = raw_ticker.upper().replace('.T', '')

        # Validate: Must be 4-digit code
        if not re.match(r'^\d{4}$', ticker):
            logger.warning(f"⚠️ Invalid Japanese ticker format: {raw_ticker}")
            return None

        return ticker

    def denormalize_ticker(self, ticker: str) -> str:
        """
        Convert normalized ticker to yfinance format

        Args:
            ticker: Normalized ticker (e.g., "7203")

        Returns:
            yfinance-compatible ticker (e.g., "7203.T")
        """
        if not ticker:
            return ""

        # Add .T suffix for Tokyo Stock Exchange
        return f"{ticker}.T"

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

            # Validate name (required field)
            if not name:
                logger.warning(f"⚠️ [{ticker}] No company name found, skipping")
                return None

            # Map industry to GICS sector
            industry = yfinance_info.get('industry', '')
            sector = self._map_industry_to_gics(industry)

            # Extract exchange (should be "JPX" for Tokyo Stock Exchange)
            exchange = yfinance_info.get('exchange', 'TSE')
            if exchange == 'JPX':
                exchange = 'TSE'  # Normalize JPX to TSE

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
                'region': 'JP',
                'currency': yfinance_info.get('currency', 'JPY'),
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

            # Rename columns to lowercase
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # Reset index to get date as column
            df = df.reset_index()

            # Convert Date to string format (YYYY-MM-DD)
            if 'Date' in df.columns:
                df['date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
                df = df.drop('Date', axis=1)

            # Add ticker column
            df['ticker'] = ticker

            # Select and reorder columns
            columns_order = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
            df = df[columns_order]

            # Sort by date ascending
            df = df.sort_values('date')

            return df

        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to parse OHLCV data: {e}")
            return None

    def _map_industry_to_gics(self, industry: Optional[str]) -> str:
        """
        Map yfinance industry classification to GICS sector

        Args:
            industry: Industry string from yfinance

        Returns:
            GICS sector name (defaults to 'Industrials' if unmapped)
        """
        if not industry:
            return 'Industrials'  # Default

        # Direct mapping
        sector = self.INDUSTRY_TO_GICS.get(industry)
        if sector:
            return sector

        # Fuzzy matching with keywords
        industry_lower = industry.lower()

        if any(kw in industry_lower for kw in ['tech', 'software', 'electronic', 'semiconductor', 'computer']):
            return 'Information Technology'
        elif any(kw in industry_lower for kw in ['bank', 'insurance', 'financial', 'capital market', 'asset management']):
            return 'Financials'
        elif any(kw in industry_lower for kw in ['drug', 'pharmaceutical', 'biotech', 'medical', 'health']):
            return 'Health Care'
        elif any(kw in industry_lower for kw in ['telecom', 'internet', 'media', 'broadcast', 'entertainment']):
            return 'Communication Services'
        elif any(kw in industry_lower for kw in ['auto', 'vehicle', 'car']):
            return 'Consumer Discretionary'
        elif any(kw in industry_lower for kw in ['food', 'beverage', 'tobacco', 'consumer product']):
            return 'Consumer Staples'
        elif any(kw in industry_lower for kw in ['utility', 'electric', 'gas', 'water']):
            return 'Utilities'
        elif any(kw in industry_lower for kw in ['real estate', 'reit', 'property']):
            return 'Real Estate'
        elif any(kw in industry_lower for kw in ['oil', 'gas', 'energy', 'coal']):
            return 'Energy'
        elif any(kw in industry_lower for kw in ['chemical', 'metal', 'mining', 'material', 'steel']):
            return 'Materials'

        # Default to Industrials
        logger.debug(f"⚠️ Unmapped industry '{industry}' → defaulting to Industrials")
        return 'Industrials'

    def _get_gics_code(self, sector_name: str) -> str:
        """
        Get GICS sector code from sector name

        Args:
            sector_name: GICS sector name

        Returns:
            GICS sector code (2-digit string)
        """
        for code, name in self.GICS_SECTORS.items():
            if name == sector_name:
                return code
        return '20'  # Default to Industrials code

    def filter_common_stocks(self, tickers: List[Dict]) -> List[Dict]:
        """
        Filter list to include only common stocks

        Excludes:
        - REITs (Real Estate Investment Trusts)
        - Preferred stocks
        - ETFs

        Args:
            tickers: List of ticker dictionaries

        Returns:
            Filtered list with common stocks only
        """
        filtered = []

        for ticker_data in tickers:
            industry = ticker_data.get('industry', '').lower()
            name = ticker_data.get('name', '').lower()

            # Skip REITs
            if 'reit' in industry or 'reit' in name:
                continue

            # Skip ETFs
            if 'etf' in name:
                continue

            # Skip preferred stocks (usually have 'preferred' in name)
            if 'preferred' in name or 'pref' in name:
                continue

            filtered.append(ticker_data)

        return filtered
