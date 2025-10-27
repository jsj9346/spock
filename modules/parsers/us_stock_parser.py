"""
US Stock Data Parser

Normalizes US stock data from Polygon.io API responses to standardized format
for database insertion.

Data Sources:
- Polygon.io REST API (primary)
- Yahoo Finance (fallback)

Author: Spock Trading System
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class USStockParser:
    """
    US stock data parser and normalizer

    Handles:
    - Polygon.io API response parsing
    - Exchange mapping (NYSE/NASDAQ/AMEX)
    - GICS sector extraction
    - OHLCV data normalization
    - Company details parsing
    """

    # Exchange code mapping
    EXCHANGE_MAP = {
        'XNYS': 'NYSE',
        'XNAS': 'NASDAQ',
        'XASE': 'AMEX',
        'BATS': 'BATS',
        'ARCX': 'NYSE Arca',
        'IEXG': 'IEX'
    }

    # Asset type mapping
    ASSET_TYPE_MAP = {
        'CS': 'Common Stock',
        'PFD': 'Preferred Stock',
        'WARRANT': 'Warrant',
        'RIGHT': 'Right',
        'BOND': 'Bond',
        'ETF': 'ETF',
        'ETN': 'ETN',
        'UNIT': 'Unit',
        'OTHER': 'Other'
    }

    def parse_ticker_list(self, polygon_response: List[Dict]) -> List[Dict]:
        """
        Parse Polygon.io ticker list response

        Args:
            polygon_response: List of ticker dictionaries from Polygon.io

        Returns:
            List of standardized ticker dictionaries

        Example input:
        [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'market': 'stocks',
                'locale': 'us',
                'primary_exchange': 'XNAS',
                'type': 'CS',
                'active': True,
                'currency_name': 'usd',
                'cik': '0000320193',
                'composite_figi': 'BBG000B9XRY4'
            }
        ]

        Example output:
        [
            {
                'ticker': 'AAPL',
                'name': 'Apple Inc.',
                'exchange': 'NASDAQ',
                'asset_type': 'Common Stock',
                'region': 'US',
                'currency': 'USD',
                'active': True,
                'cik': '0000320193',
                'composite_figi': 'BBG000B9XRY4',
                'data_source': 'Polygon.io'
            }
        ]
        """
        parsed_tickers = []

        for raw_ticker in polygon_response:
            try:
                parsed = self._parse_single_ticker(raw_ticker)
                if parsed:
                    parsed_tickers.append(parsed)
            except Exception as e:
                ticker_symbol = raw_ticker.get('ticker', 'UNKNOWN')
                logger.error(f"❌ [{ticker_symbol}] Ticker parsing failed: {e}")
                continue

        logger.info(f"✅ Parsed {len(parsed_tickers)}/{len(polygon_response)} US tickers")
        return parsed_tickers

    def _parse_single_ticker(self, raw_data: Dict) -> Optional[Dict]:
        """
        Parse single ticker from Polygon.io response

        Args:
            raw_data: Raw ticker data from Polygon.io

        Returns:
            Standardized ticker dictionary or None if invalid
        """
        ticker = raw_data.get('ticker')
        if not ticker:
            return None

        # Filter out non-stock assets (options, indices, etc.)
        market = raw_data.get('market', '').lower()
        if market != 'stocks':
            return None

        # Get exchange name
        primary_exchange = raw_data.get('primary_exchange', '')
        exchange = self.EXCHANGE_MAP.get(primary_exchange, primary_exchange)

        # Get asset type
        asset_type_code = raw_data.get('type', 'CS')
        asset_type = self.ASSET_TYPE_MAP.get(asset_type_code, asset_type_code)

        return {
            'ticker': ticker,
            'name': raw_data.get('name', ''),
            'exchange': exchange,
            'exchange_code': primary_exchange,
            'asset_type': asset_type,
            'asset_type_code': asset_type_code,
            'region': 'US',
            'currency': raw_data.get('currency_name', 'usd').upper(),
            'active': raw_data.get('active', True),
            'cik': raw_data.get('cik'),  # SEC CIK identifier
            'composite_figi': raw_data.get('composite_figi'),
            'share_class_figi': raw_data.get('share_class_figi'),
            'delisted_utc': raw_data.get('delisted_utc'),
            'data_source': 'Polygon.io'
        }

    def parse_ticker_details(self, polygon_response: Dict) -> Optional[Dict]:
        """
        Parse Polygon.io ticker details response

        Args:
            polygon_response: Ticker details dictionary from Polygon.io

        Returns:
            Standardized company details dictionary

        Example input:
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
            'market_cap': 2800000000000,
            'share_class_shares_outstanding': 15550000000,
            'sic_code': '3571',
            'sic_description': 'ELECTRONIC COMPUTERS'
        }

        Example output:
        {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'description': 'Apple Inc. designs, manufactures...',
            'homepage_url': 'https://www.apple.com',
            'total_employees': 164000,
            'listing_date': '1980-12-12',
            'market_cap': 2800000000000,
            'shares_outstanding': 15550000000,
            'sic_code': '3571',
            'sic_description': 'ELECTRONIC COMPUTERS',
            'sector': 'Information Technology',  # Mapped from SIC
            'industry': 'Electronic Computers'
        }
        """
        if not polygon_response:
            return None

        try:
            ticker = polygon_response.get('ticker')
            if not ticker:
                return None

            # Map SIC code to GICS sector
            sic_code = polygon_response.get('sic_code', '')
            sic_description = polygon_response.get('sic_description', '')
            sector = self._map_sic_to_gics(sic_code, sic_description)

            return {
                'ticker': ticker,
                'name': polygon_response.get('name', ''),
                'description': polygon_response.get('description'),
                'homepage_url': polygon_response.get('homepage_url'),
                'total_employees': polygon_response.get('total_employees'),
                'listing_date': polygon_response.get('list_date'),
                'market_cap': polygon_response.get('market_cap'),
                'shares_outstanding': polygon_response.get('share_class_shares_outstanding') or
                                     polygon_response.get('weighted_shares_outstanding'),
                'sic_code': sic_code,
                'sic_description': sic_description,
                'sector': sector,
                'industry': sic_description if sic_description else None,
                'phone_number': polygon_response.get('phone_number'),
                'address': self._parse_address(polygon_response.get('address')),
                'branding': polygon_response.get('branding'),
                'data_source': 'Polygon.io'
            }

        except Exception as e:
            ticker = polygon_response.get('ticker', 'UNKNOWN')
            logger.error(f"❌ [{ticker}] Ticker details parsing failed: {e}")
            return None

    def parse_ohlcv_data(self, polygon_response: List[Dict], ticker: str) -> pd.DataFrame:
        """
        Parse Polygon.io OHLCV aggregates response to DataFrame

        Args:
            polygon_response: List of OHLCV dictionaries from Polygon.io
            ticker: Stock ticker symbol

        Returns:
            Standardized OHLCV DataFrame

        Example input:
        [
            {
                'v': 100000000,      # Volume
                'vw': 150.25,        # Volume weighted average price
                'o': 150.00,         # Open
                'c': 151.00,         # Close
                'h': 152.00,         # High
                'l': 149.50,         # Low
                't': 1609459200000,  # Unix timestamp (milliseconds)
                'n': 500000,         # Number of transactions
                'date': '2021-01-01' # Added by PolygonAPI
            }
        ]

        Example output DataFrame:
        | date       | ticker | open   | high   | low    | close  | volume    | vwap   | transactions |
        |------------|--------|--------|--------|--------|--------|-----------|--------|--------------|
        | 2021-01-01 | AAPL   | 150.00 | 152.00 | 149.50 | 151.00 | 100000000 | 150.25 | 500000       |
        """
        if not polygon_response:
            logger.warning(f"⚠️ [{ticker}] Empty OHLCV response")
            return pd.DataFrame()

        try:
            # Convert to DataFrame
            df = pd.DataFrame(polygon_response)

            # Rename columns to standard format
            df = df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
                'vw': 'vwap',
                'n': 'transactions',
                't': 'timestamp'
            })

            # Add ticker column
            df['ticker'] = ticker

            # Convert timestamp to date if not already present
            if 'date' not in df.columns and 'timestamp' in df.columns:
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%Y-%m-%d')

            # Select and order columns
            columns = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']

            # Add optional columns if present
            if 'vwap' in df.columns:
                columns.append('vwap')
            if 'transactions' in df.columns:
                columns.append('transactions')

            df = df[columns]

            # Sort by date ascending
            df = df.sort_values('date')

            # Reset index
            df = df.reset_index(drop=True)

            logger.info(f"✅ [{ticker}] Parsed {len(df)} days of OHLCV data")
            return df

        except Exception as e:
            logger.error(f"❌ [{ticker}] OHLCV parsing failed: {e}")
            return pd.DataFrame()

    def _map_sic_to_gics(self, sic_code: str, sic_description: str) -> str:
        """
        Map SIC (Standard Industrial Classification) code to GICS sector

        Args:
            sic_code: SIC code (e.g., '3571')
            sic_description: SIC description (e.g., 'ELECTRONIC COMPUTERS')

        Returns:
            GICS sector name

        SIC Code Ranges to GICS Mapping:
        - 1000-1499: Energy (Mining, Oil & Gas)
        - 1500-1799: Industrials (Construction)
        - 2000-3999: Materials, Consumer, Health Care, Tech (Manufacturing)
        - 4000-4999: Utilities, Communication Services (Transportation, Utilities, Communications)
        - 5000-5999: Consumer (Retail)
        - 6000-6999: Financials (Finance, Insurance, Real Estate)
        - 7000-8999: Services (various)
        - 9000-9999: Public Administration
        """
        if not sic_code:
            return 'Unknown'

        try:
            sic_int = int(sic_code)
        except (ValueError, TypeError):
            return 'Unknown'

        # Health Care (specific ranges first - most specific)
        if (2833 <= sic_int <= 2836 or 3693 == sic_int or
            3840 <= sic_int <= 3851 or 8000 <= sic_int <= 8099):
            return 'Health Care'

        # Information Technology (before broader categories)
        if (3570 <= sic_int <= 3579 or 3660 <= sic_int <= 3669 or
            7370 <= sic_int <= 7379):
            return 'Information Technology'

        # Energy
        if 1000 <= sic_int <= 1499 or 2900 <= sic_int <= 2911:
            return 'Energy'

        # Materials (before broader industrial category)
        if (1500 <= sic_int <= 1799 or 2600 <= sic_int <= 2699 or
            2800 <= sic_int <= 2829 or 3300 <= sic_int <= 3399):
            return 'Materials'

        # Consumer Discretionary (cars, retail, media)
        if (2300 <= sic_int <= 2399 or 2500 <= sic_int <= 2599 or
            3700 <= sic_int <= 3719 or 3900 <= sic_int <= 3999 or
            5000 <= sic_int <= 5999 or 7800 <= sic_int <= 7999):
            return 'Consumer Discretionary'

        # Consumer Staples
        if 2000 <= sic_int <= 2199:
            return 'Consumer Staples'

        # Industrials (broader category after specific tech/auto)
        if (3400 <= sic_int <= 3569 or 3580 <= sic_int <= 3659 or
            3720 <= sic_int <= 3799 or 4000 <= sic_int <= 4499 or
            7300 <= sic_int <= 7369):
            return 'Industrials'

        # Financials
        if 6000 <= sic_int <= 6499 or 6700 <= sic_int <= 6799:
            return 'Financials'

        # Real Estate
        if 6500 <= sic_int <= 6599:
            return 'Real Estate'

        # Communication Services
        if 4800 <= sic_int <= 4899 or 7380 <= sic_int <= 7389:
            return 'Communication Services'

        # Utilities
        if 4900 <= sic_int <= 4999:
            return 'Utilities'

        return 'Unknown'

    def _parse_address(self, address_dict: Optional[Dict]) -> Optional[str]:
        """
        Parse address dictionary to formatted string

        Args:
            address_dict: Address dictionary from Polygon.io

        Returns:
            Formatted address string or None
        """
        if not address_dict:
            return None

        try:
            parts = []
            if address_dict.get('address1'):
                parts.append(address_dict['address1'])
            if address_dict.get('city'):
                parts.append(address_dict['city'])
            if address_dict.get('state'):
                parts.append(address_dict['state'])
            if address_dict.get('postal_code'):
                parts.append(address_dict['postal_code'])

            return ', '.join(parts) if parts else None

        except Exception:
            return None

    def validate_ticker_format(self, ticker: str) -> bool:
        """
        Validate US ticker format

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if valid US ticker format

        Valid formats:
        - 1-5 uppercase letters (e.g., AAPL, MSFT, BRK.B)
        - May contain one period for share classes (e.g., BRK.A, BRK.B)
        """
        if not ticker or not isinstance(ticker, str):
            return False

        # Remove period for share class
        ticker_base = ticker.replace('.', '')

        # Check length and characters
        if 1 <= len(ticker_base) <= 5 and ticker_base.isalpha() and ticker_base.isupper():
            return True

        return False

    def filter_common_stocks(self, tickers: List[Dict]) -> List[Dict]:
        """
        Filter for common stocks only (exclude ETFs, preferred stocks, etc.)

        Args:
            tickers: List of parsed ticker dictionaries

        Returns:
            List of common stock tickers only
        """
        common_stocks = [
            ticker for ticker in tickers
            if ticker.get('asset_type_code') == 'CS' and ticker.get('active', True)
        ]

        logger.info(f"🔍 Filtered {len(common_stocks)}/{len(tickers)} common stocks")
        return common_stocks

    def enrich_with_sector(self, tickers: List[Dict], sector_map: Dict[str, str]) -> List[Dict]:
        """
        Enrich tickers with GICS sector information

        Args:
            tickers: List of ticker dictionaries
            sector_map: Mapping of ticker -> GICS sector

        Returns:
            Enriched ticker list with sector information
        """
        enriched = []

        for ticker_data in tickers:
            ticker = ticker_data.get('ticker')
            if ticker and ticker in sector_map:
                ticker_data['sector'] = sector_map[ticker]
                ticker_data['sector_source'] = 'External Map'

            enriched.append(ticker_data)

        return enriched
