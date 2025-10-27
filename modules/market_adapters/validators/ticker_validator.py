"""
Ticker Validator

Validates and normalizes ticker symbols for different regional markets.

Each market has different ticker formats:
- Korea: 6-digit numeric (005930)
- USA: 1-5 character alphanumeric with optional suffix (AAPL, BRK.B)
- China: 6-digit with exchange suffix (600000.SS, 000001.SZ)
- Hong Kong: 4-5 digit numeric with .HK suffix (0700.HK)
- Japan: 4-digit numeric (7203)
- Vietnam: 3-character alphanumeric (VNM, FPT)

Author: Spock Trading System
"""

import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class TickerValidator:
    """
    Ticker format validator and normalizer for global markets
    """

    # Regex patterns for each region
    PATTERNS = {
        'KR': r'^\d{6}$',                       # 005930 (6 digits)
        'US': r'^[A-Z]{1,5}(\.[A-Z])?$',       # AAPL, BRK.B (1-5 letters + optional suffix)
        'CN': r'^\d{6}\.(SS|SZ|SH)$',          # 600000.SS (Shanghai), 000001.SZ (Shenzhen)
        'HK': r'^\d{4,5}(\.HK)?$',             # 0700.HK, 09988.HK (4-5 digits + optional .HK)
        'JP': r'^\d{4}$',                       # 7203 (4 digits)
        'VN': r'^[A-Z]{3}$'                     # VNM, FPT (3 letters)
    }

    # Exchange suffixes
    EXCHANGE_SUFFIXES = {
        'CN': {
            'SS': 'Shanghai Stock Exchange',
            'SZ': 'Shenzhen Stock Exchange',
            'SH': 'Shanghai Stock Exchange'  # Alternative notation
        },
        'HK': {
            'HK': 'Hong Kong Stock Exchange'
        }
    }

    # Market-specific validation rules
    VALIDATION_RULES = {
        'KR': {
            'pad_zeros': True,
            'uppercase': False,
            'max_length': 6
        },
        'US': {
            'pad_zeros': False,
            'uppercase': True,
            'max_length': 6  # Including suffix
        },
        'CN': {
            'pad_zeros': True,
            'uppercase': True,
            'max_length': 9  # Including .SS/.SZ
        },
        'HK': {
            'pad_zeros': True,
            'uppercase': True,
            'max_length': 8  # Including .HK
        },
        'JP': {
            'pad_zeros': True,
            'uppercase': False,
            'max_length': 4
        },
        'VN': {
            'pad_zeros': False,
            'uppercase': True,
            'max_length': 3
        }
    }

    @classmethod
    def validate(cls, ticker: str, region: str) -> bool:
        """
        Validate ticker format for specific region

        Args:
            ticker: Ticker symbol
            region: Region code (KR, US, CN, HK, JP, VN)

        Returns:
            True if valid, False otherwise
        """
        if not ticker or not region:
            return False

        pattern = cls.PATTERNS.get(region)
        if not pattern:
            logger.warning(f"⚠️ Unknown region: {region}")
            return False

        # Normalize before validation
        normalized = cls.normalize(ticker, region)
        if not normalized:
            return False

        # Check regex pattern
        is_valid = bool(re.match(pattern, normalized))

        if not is_valid:
            logger.debug(f"❌ [{region}] Invalid ticker format: {ticker} (normalized: {normalized})")

        return is_valid

    @classmethod
    def normalize(cls, ticker: str, region: str) -> Optional[str]:
        """
        Normalize ticker symbol for specific region

        Args:
            ticker: Raw ticker symbol
            region: Region code

        Returns:
            Normalized ticker or None if invalid
        """
        if not ticker:
            return None

        rules = cls.VALIDATION_RULES.get(region, {})

        # Trim whitespace
        ticker = ticker.strip()

        # Apply region-specific rules
        if rules.get('uppercase'):
            ticker = ticker.upper()

        # Zero padding (for numeric tickers)
        if rules.get('pad_zeros') and region in ['KR', 'JP']:
            # Korean tickers: 6 digits
            if region == 'KR' and ticker.isdigit():
                ticker = ticker.zfill(6)
            # Japanese tickers: 4 digits
            elif region == 'JP' and ticker.isdigit():
                ticker = ticker.zfill(4)

        # Hong Kong: Add .HK suffix if missing
        if region == 'HK' and not ticker.endswith('.HK'):
            if ticker.isdigit():
                ticker = ticker.zfill(4)  # Pad to 4 digits
                ticker = f"{ticker}.HK"

        # China: Validate exchange suffix
        if region == 'CN':
            if '.' not in ticker:
                logger.warning(f"⚠️ Chinese ticker missing exchange suffix: {ticker}")
                return None
            code, suffix = ticker.split('.')
            if suffix.upper() not in ['SS', 'SZ', 'SH']:
                logger.warning(f"⚠️ Invalid Chinese exchange suffix: {suffix}")
                return None
            ticker = f"{code.zfill(6)}.{suffix.upper()}"

        return ticker

    @classmethod
    def extract_components(cls, ticker: str, region: str) -> Dict:
        """
        Extract ticker components (code, exchange, suffix)

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            Dictionary with ticker components
        """
        result = {
            'ticker': ticker,
            'code': ticker,
            'exchange': None,
            'suffix': None,
            'region': region
        }

        # China: Split code and exchange
        if region == 'CN' and '.' in ticker:
            code, suffix = ticker.split('.')
            result['code'] = code
            result['suffix'] = suffix
            result['exchange'] = cls.EXCHANGE_SUFFIXES['CN'].get(suffix.upper())

        # Hong Kong: Split code and .HK
        elif region == 'HK' and '.' in ticker:
            code, suffix = ticker.split('.')
            result['code'] = code
            result['suffix'] = suffix
            result['exchange'] = cls.EXCHANGE_SUFFIXES['HK'].get(suffix.upper())

        # USA: Split ticker and suffix (e.g., BRK.B)
        elif region == 'US' and '.' in ticker:
            code, suffix = ticker.split('.')
            result['code'] = code
            result['suffix'] = suffix

        return result

    @classmethod
    def get_exchange_from_ticker(cls, ticker: str, region: str) -> Optional[str]:
        """
        Extract exchange name from ticker

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            Exchange name or None
        """
        components = cls.extract_components(ticker, region)
        return components.get('exchange')

    @classmethod
    def validate_batch(cls, tickers: list, region: str) -> Dict:
        """
        Validate batch of tickers

        Args:
            tickers: List of ticker symbols
            region: Region code

        Returns:
            Dictionary with validation results
        """
        valid = []
        invalid = []

        for ticker in tickers:
            if cls.validate(ticker, region):
                valid.append(cls.normalize(ticker, region))
            else:
                invalid.append(ticker)

        return {
            'valid': valid,
            'invalid': invalid,
            'total': len(tickers),
            'valid_count': len(valid),
            'invalid_count': len(invalid),
            'success_rate': len(valid) / len(tickers) if tickers else 0
        }

    @classmethod
    def get_region_info(cls, region: str) -> Dict:
        """
        Get validation rules and pattern for region

        Args:
            region: Region code

        Returns:
            Dictionary with region validation info
        """
        return {
            'region': region,
            'pattern': cls.PATTERNS.get(region),
            'rules': cls.VALIDATION_RULES.get(region),
            'exchange_suffixes': cls.EXCHANGE_SUFFIXES.get(region, {})
        }
