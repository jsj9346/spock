"""
Exchange Rate API Client

Fetches real-time exchange rates from external API sources.

Supported sources:
- exchangerate-api.com (completely free, no API key required)
- Fallback: Mock rates for development

Author: Spock Quant Platform
Date: 2025-11-06
"""

import logging
import os
from datetime import date
from typing import Dict, List
from decimal import Decimal
import requests

logger = logging.getLogger(__name__)


class ExchangeRateAPI:
    """
    Exchange rate API client with fallback support

    Features:
    - Fetch rates from exchangerate-api.com (completely free, no API key required)
    - Supports all major currencies including KRW as base
    - Mock data fallback for development and testing
    - Decimal precision for accurate currency calculations
    """

    API_BASE_URL = "https://api.exchangerate-api.com/v4"
    TIMEOUT = 10  # seconds

    def __init__(self, base_currency: str = 'KRW'):
        """
        Initialize API client

        Args:
            base_currency: Base currency for rate conversions (default: KRW)
        """
        self.base_currency = base_currency
        self.logger = logger

    def get_rates(self, currencies: List[str]) -> Dict[str, Decimal]:
        """
        Fetch exchange rates for specified currencies

        Args:
            currencies: List of currency codes (e.g., ['USD', 'JPY', 'EUR'])

        Returns:
            Dict mapping currency code to rate (vs base currency)
            Example: {'USD': Decimal('1350.50'), 'JPY': Decimal('10.25')}

        Raises:
            requests.RequestException: If API request fails after retries
        """
        try:
            # Build API request (no API key required for exchangerate-api.com)
            url = f"{self.API_BASE_URL}/latest/{self.base_currency}"

            self.logger.debug(f"Fetching rates from {url}")

            # Make request
            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Extract rates (exchangerate-api.com returns all rates)
            rates_data = data.get('rates', {})

            if not rates_data:
                self.logger.warning("⚠️  API returned empty rates, using mock data")
                return self._get_mock_rates(currencies)

            # Convert to Decimal for precision
            rates = {
                cur: Decimal(str(rate))
                for cur, rate in rates_data.items()
                if cur in currencies
            }

            self.logger.info(f"✅ Fetched {len(rates)} exchange rates")
            return rates

        except requests.RequestException as e:
            self.logger.error(f"❌ API request failed: {e}")
            self.logger.warning("⚠️  Falling back to mock rates")
            return self._get_mock_rates(currencies)

        except Exception as e:
            self.logger.error(f"❌ Unexpected error fetching rates: {e}")
            return self._get_mock_rates(currencies)

    def _get_mock_rates(self, currencies: List[str]) -> Dict[str, Decimal]:
        """
        Generate mock exchange rates for development/testing

        Mock rates are based on approximate real-world values (as of 2025-11)

        Args:
            currencies: List of currency codes

        Returns:
            Dict of mock rates (1 foreign currency = X base currency)
        """
        # Mock rates for KRW base
        # (1 USD = 1350 KRW, 1 JPY = 10 KRW, etc.)
        krw_base_rates = {
            'USD': Decimal('1350.50'),   # US Dollar
            'JPY': Decimal('10.25'),     # Japanese Yen (per 1 JPY)
            'EUR': Decimal('1450.75'),   # Euro
            'CNY': Decimal('185.30'),    # Chinese Yuan
            'GBP': Decimal('1720.00'),   # British Pound
            'HKD': Decimal('172.50'),    # Hong Kong Dollar
            'AUD': Decimal('880.00'),    # Australian Dollar
            'CAD': Decimal('975.00'),    # Canadian Dollar
            'CHF': Decimal('1520.00'),   # Swiss Franc
            'SGD': Decimal('1005.00'),   # Singapore Dollar
        }

        # If base currency is not KRW, convert rates
        if self.base_currency != 'KRW':
            # For simplicity, assume USD base for non-KRW
            usd_base_rates = {
                'KRW': Decimal('0.00074'),  # 1 KRW = 0.00074 USD
                'JPY': Decimal('0.0076'),   # 1 JPY = 0.0076 USD
                'EUR': Decimal('1.075'),    # 1 EUR = 1.075 USD
                'CNY': Decimal('0.137'),    # 1 CNY = 0.137 USD
                'GBP': Decimal('1.273'),    # 1 GBP = 1.273 USD
                'HKD': Decimal('0.128'),    # 1 HKD = 0.128 USD
            }
            return {cur: usd_base_rates.get(cur, Decimal('1.0')) for cur in currencies}

        return {cur: krw_base_rates.get(cur, Decimal('1.0')) for cur in currencies}

    def get_historical_rates(self, currencies: List[str],
                            target_date: date) -> Dict[str, Decimal]:
        """
        Fetch historical exchange rates for a specific date

        Args:
            currencies: List of currency codes
            target_date: Date to fetch rates for

        Returns:
            Dict mapping currency code to rate

        Note:
            Historical data requires API key and may have limited availability
        """
        try:
            url = f"{self.API_BASE_URL}/{target_date.isoformat()}"
            params = {
                'base': self.base_currency,
                'symbols': ','.join(currencies)
            }

            if self.api_key:
                params['access_key'] = self.api_key

            response = requests.get(url, params=params, timeout=self.TIMEOUT)
            response.raise_for_status()

            data = response.json()
            rates_data = data.get('rates', {})

            return {
                cur: Decimal(str(rate))
                for cur, rate in rates_data.items()
                if cur in currencies
            }

        except Exception as e:
            self.logger.error(f"Failed to fetch historical rates for {target_date}: {e}")
            return {}
