"""
Exchange Rate Manager
Multi-source exchange rate management with caching and fallback strategies

Features:
- Primary Source: Bank of Korea (BOK) Open API (official rates)
- Fallback Source: Fixed default rates from market filter configs
- TTL Caching: 1h market hours, 24h after-hours
- Database Persistence: exchange_rate_history table
- Automatic Refresh: Hourly during market hours

Supported Currencies: USD, HKD, CNY, JPY, VND

Author: Spock Trading System
"""

import requests
import logging
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ExchangeRateManager:
    """
    Exchange rate manager with multi-source support and intelligent caching

    Rate Sources:
    1. Bank of Korea (BOK) Open API: Official rates, free access
    2. Default rates: From market filter config files

    Caching Strategy:
    - In-memory cache with TTL (1h market hours, 24h after-hours)
    - Database persistence for historical tracking
    - Automatic refresh during market hours

    Usage:
        >>> manager = ExchangeRateManager(db_manager)
        >>> usd_rate = manager.get_rate('USD')  # 1,300.0 KRW
        >>> krw_value = manager.convert_to_krw(100, 'USD')  # 130,000 KRW
    """

    # Default exchange rates (fallback)
    # Source: Market filter config files (2025-10-16)
    DEFAULT_RATES = {
        'KRW': 1.0,      # Korean Won (base currency)
        'USD': 1300.0,   # US Dollar
        'HKD': 170.0,    # Hong Kong Dollar
        'CNY': 180.0,    # Chinese Yuan
        'JPY': 10.0,     # Japanese Yen
        'VND': 0.055,    # Vietnamese Dong
    }

    # BOK Open API configuration
    BOK_API_BASE_URL = 'https://ecos.bok.or.kr/api'
    BOK_SERVICE_NAME = 'StatisticSearch'

    # BOK currency codes (BOK → ISO 4217 mapping)
    BOK_CURRENCY_CODES = {
        'USD': 'USD',  # US Dollar
        'HKD': 'HKD',  # Hong Kong Dollar
        'CNY': 'CNY',  # Chinese Yuan
        'JPY': 'JPY',  # Japanese Yen (100 yen)
        'VND': 'VND',  # Vietnamese Dong (100 dong)
    }

    # Cache TTL (Time To Live)
    TTL_MARKET_HOURS = 3600       # 1 hour during trading hours
    TTL_AFTER_HOURS = 86400       # 24 hours after market close

    def __init__(self, db_manager=None, bok_api_key: Optional[str] = None):
        """
        Initialize ExchangeRateManager

        Args:
            db_manager: SQLiteDatabaseManager instance (optional)
            bok_api_key: BOK Open API key (optional, for rate limit increase)

        Note:
            BOK API key is optional. Without key: 10,000 req/day
            With key: 100,000 req/day (register at ecos.bok.or.kr)
        """
        self.db_manager = db_manager
        self.bok_api_key = bok_api_key or 'sample'  # BOK allows 'sample' for testing

        # In-memory cache
        self._cache: Dict[str, Dict] = {}  # {currency: {rate: float, timestamp: datetime}}

        # Rate limiting
        self.last_api_call = None
        self.min_api_interval = 0.1  # 10 req/sec (conservative)

        logger.info("💱 ExchangeRateManager initialized")
        logger.info(f"   Default rates loaded: {len(self.DEFAULT_RATES)} currencies")
        logger.info(f"   BOK API: {'Enabled' if bok_api_key else 'Sample mode (10K req/day)'}")

    def get_rate(self, currency: str, force_refresh: bool = False) -> float:
        """
        Get exchange rate for currency (to KRW)

        Args:
            currency: Currency code (USD, HKD, CNY, JPY, VND)
            force_refresh: Force API call (ignore cache)

        Returns:
            Exchange rate (float) - how many KRW per 1 unit of foreign currency

        Example:
            >>> manager.get_rate('USD')
            1300.0  # 1 USD = 1,300 KRW

        Strategy:
        1. Check in-memory cache (if not expired and not force_refresh)
        2. Try BOK API (if available)
        3. Check database cache (historical data)
        4. Fallback to default rate from config
        """
        currency = currency.upper()

        # Base currency (KRW)
        if currency == 'KRW':
            return 1.0

        # Validate currency
        if currency not in self.DEFAULT_RATES:
            logger.warning(f"⚠️ Unknown currency: {currency}, using USD as fallback")
            currency = 'USD'

        # Check in-memory cache
        if not force_refresh and self._is_cache_valid(currency):
            cached_rate = self._cache[currency]['rate']
            logger.debug(f"💾 [{currency}] Using cached rate: {cached_rate} KRW")
            return cached_rate

        # Try BOK API
        rate = self._fetch_from_bok_api(currency)

        # Fallback to database cache
        if rate is None and self.db_manager:
            rate = self._fetch_from_database(currency)

        # Fallback to default rate
        if rate is None:
            rate = self.DEFAULT_RATES[currency]
            logger.info(f"ℹ️ [{currency}] Using default rate: {rate} KRW")

        # Update cache and database
        self._update_cache(currency, rate)
        if self.db_manager:
            self._save_to_database(currency, rate)

        return rate

    def convert_to_krw(self, amount: float, currency: str) -> int:
        """
        Convert foreign currency amount to KRW

        Args:
            amount: Amount in foreign currency
            currency: Currency code (USD, HKD, CNY, JPY, VND)

        Returns:
            Amount in KRW (integer)

        Example:
            >>> manager.convert_to_krw(100, 'USD')
            130000  # 100 USD × 1,300 = 130,000 KRW
        """
        rate = self.get_rate(currency)
        krw_amount = int(amount * rate)

        logger.debug(f"💱 Convert: {amount:,.2f} {currency} → {krw_amount:,} KRW (rate: {rate})")
        return krw_amount

    def convert_from_krw(self, amount_krw: int, currency: str) -> float:
        """
        Convert KRW amount to foreign currency

        Args:
            amount_krw: Amount in KRW
            currency: Currency code (USD, HKD, CNY, JPY, VND)

        Returns:
            Amount in foreign currency (float)

        Example:
            >>> manager.convert_from_krw(130000, 'USD')
            100.0  # 130,000 KRW ÷ 1,300 = 100 USD
        """
        rate = self.get_rate(currency)
        foreign_amount = amount_krw / rate

        logger.debug(f"💱 Convert: {amount_krw:,} KRW → {foreign_amount:.2f} {currency} (rate: {rate})")
        return foreign_amount

    def get_all_rates(self, force_refresh: bool = False) -> Dict[str, float]:
        """
        Get all exchange rates

        Args:
            force_refresh: Force API calls for all currencies

        Returns:
            Dictionary of {currency: rate}

        Example:
            >>> manager.get_all_rates()
            {'KRW': 1.0, 'USD': 1300.0, 'HKD': 170.0, ...}
        """
        rates = {}
        for currency in self.DEFAULT_RATES.keys():
            rates[currency] = self.get_rate(currency, force_refresh=force_refresh)

        return rates

    def _is_cache_valid(self, currency: str) -> bool:
        """
        Check if cached rate is still valid (TTL check)

        Args:
            currency: Currency code

        Returns:
            True if cache is valid, False otherwise
        """
        if currency not in self._cache:
            return False

        cached_data = self._cache[currency]
        cached_time = cached_data['timestamp']

        # Determine TTL based on market hours
        now = datetime.now()
        is_market_hours = self._is_market_hours(now)
        ttl = self.TTL_MARKET_HOURS if is_market_hours else self.TTL_AFTER_HOURS

        # Check if cache expired
        age = (now - cached_time).total_seconds()
        is_valid = age < ttl

        if not is_valid:
            logger.debug(f"⏰ [{currency}] Cache expired (age: {int(age)}s, TTL: {ttl}s)")

        return is_valid

    def _is_market_hours(self, dt: datetime) -> bool:
        """
        Check if current time is during market hours (Korean markets)

        Args:
            dt: Datetime to check

        Returns:
            True if during market hours, False otherwise

        Market Hours (KST):
        - Weekdays: 09:00-15:30
        - Weekends/Holidays: Closed
        """
        # Weekend check
        if dt.weekday() >= 5:  # Saturday (5) or Sunday (6)
            return False

        # Market hours check (09:00-15:30 KST)
        market_open = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = dt.replace(hour=15, minute=30, second=0, microsecond=0)

        return market_open <= dt <= market_close

    def _fetch_from_bok_api(self, currency: str) -> Optional[float]:
        """
        Fetch exchange rate from Bank of Korea Open API

        Args:
            currency: Currency code

        Returns:
            Exchange rate (float) or None if failed

        BOK API Endpoint:
        https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/1/731Y001/D/{START_DATE}/{END_DATE}/{CURRENCY_CODE}

        Response Format:
        {
            "StatisticSearch": {
                "row": [
                    {
                        "STAT_CODE": "731Y001",
                        "STAT_NAME": "3.7.2 주요국 대원화 환율(종가)",
                        "ITEM_CODE1": "0000001",
                        "ITEM_NAME1": "미국 달러",
                        "DATA_VALUE": "1300.0",
                        "TIME": "20251016"
                    }
                ]
            }
        }
        """
        # Rate limiting
        self._rate_limit()

        # BOK API configuration
        bok_currency_code = self.BOK_CURRENCY_CODES.get(currency)
        if not bok_currency_code:
            logger.debug(f"ℹ️ [{currency}] Not available in BOK API")
            return None

        # Date range (today only, for latest rate)
        today = datetime.now().strftime('%Y%m%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')

        # BOK API URL
        # Statistic Table: 731Y001 (Exchange Rates - Closing Price)
        # https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/1/731Y001/D/{START}/{END}/{CURRENCY}
        url = (
            f"{self.BOK_API_BASE_URL}/{self.BOK_SERVICE_NAME}/"
            f"{self.bok_api_key}/json/kr/1/1/731Y001/D/{yesterday}/{today}/{bok_currency_code}"
        )

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API error
            if 'RESULT' in data:
                error_code = data['RESULT'].get('CODE', '')
                error_msg = data['RESULT'].get('MESSAGE', '')

                # Common BOK API errors
                if error_code == 'INFO-200':
                    # No data available (weekend/holiday)
                    logger.debug(f"ℹ️ [{currency}] No BOK data available (weekend/holiday)")
                    return None
                elif error_code == 'ERR-500':
                    # API key limit exceeded
                    logger.warning(f"⚠️ [{currency}] BOK API limit exceeded: {error_msg}")
                    return None
                else:
                    logger.warning(f"⚠️ [{currency}] BOK API error: {error_code} - {error_msg}")
                    return None

            # Parse exchange rate
            if 'StatisticSearch' not in data or 'row' not in data['StatisticSearch']:
                logger.debug(f"ℹ️ [{currency}] No BOK data in response")
                return None

            rows = data['StatisticSearch']['row']
            if not rows:
                logger.debug(f"ℹ️ [{currency}] Empty BOK data")
                return None

            # Get latest rate (last row)
            latest_row = rows[-1]
            rate_str = latest_row.get('DATA_VALUE', '')
            rate_date = latest_row.get('TIME', '')

            if not rate_str:
                logger.warning(f"⚠️ [{currency}] No rate value in BOK data")
                return None

            # Convert to float
            rate = float(rate_str)

            # Special handling for JPY and VND (BOK returns per 100 units)
            if currency == 'JPY':
                rate = rate / 100  # BOK: ¥100 → rate per ¥1
            elif currency == 'VND':
                rate = rate / 100  # BOK: ₫100 → rate per ₫1

            logger.info(f"✅ [{currency}] BOK API rate: {rate} KRW (date: {rate_date})")
            return rate

        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ [{currency}] BOK API timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ [{currency}] BOK API request failed: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ [{currency}] BOK API parse error: {e}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ [{currency}] BOK API unexpected error: {e}")
            return None

    def _fetch_from_database(self, currency: str) -> Optional[float]:
        """
        Fetch latest exchange rate from database cache

        Args:
            currency: Currency code

        Returns:
            Exchange rate (float) or None if not found

        Note:
            Uses exchange_rate_history table (created in Phase 1.4)
        """
        if not self.db_manager:
            return None

        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()

            # Query latest rate (within last 7 days)
            cutoff_date = datetime.now() - timedelta(days=7)

            query = """
                SELECT rate, timestamp
                FROM exchange_rate_history
                WHERE currency = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """

            cursor.execute(query, (currency, cutoff_date.isoformat()))
            row = cursor.fetchone()
            conn.close()

            if row:
                rate = float(row[0])
                timestamp = row[1]
                logger.info(f"✅ [{currency}] Database cache: {rate} KRW (cached: {timestamp})")
                return rate

            return None

        except Exception as e:
            logger.warning(f"⚠️ [{currency}] Database fetch failed: {e}")
            return None

    def _save_to_database(self, currency: str, rate: float):
        """
        Save exchange rate to database for historical tracking

        Args:
            currency: Currency code
            rate: Exchange rate

        Note:
            Inserts into exchange_rate_history table (unique constraint on currency + rate_date)
        """
        if not self.db_manager:
            return

        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()

            now = datetime.now()
            timestamp = now.isoformat()
            rate_date = now.strftime('%Y-%m-%d')  # Date component for uniqueness

            # Insert or replace (unique constraint on currency + rate_date)
            insert_query = """
                INSERT OR REPLACE INTO exchange_rate_history
                (currency, rate, timestamp, rate_date, source)
                VALUES (?, ?, ?, ?, ?)
            """

            cursor.execute(insert_query, (
                currency,
                rate,
                timestamp,
                rate_date,
                'BOK_API'  # Source identifier
            ))

            conn.commit()
            conn.close()

            logger.debug(f"💾 [{currency}] Saved to database: {rate} KRW (date: {rate_date})")

        except Exception as e:
            logger.warning(f"⚠️ [{currency}] Database save failed: {e}")

    def _update_cache(self, currency: str, rate: float):
        """
        Update in-memory cache

        Args:
            currency: Currency code
            rate: Exchange rate
        """
        self._cache[currency] = {
            'rate': rate,
            'timestamp': datetime.now()
        }

        logger.debug(f"💾 [{currency}] Cache updated: {rate} KRW")

    def _rate_limit(self):
        """
        Rate limiting for BOK API calls (10 req/sec)

        BOK API limits:
        - Without key: 10,000 req/day
        - With key: 100,000 req/day
        """
        if self.last_api_call:
            elapsed = time.time() - self.last_api_call
            if elapsed < self.min_api_interval:
                sleep_time = self.min_api_interval - elapsed
                time.sleep(sleep_time)

        self.last_api_call = time.time()

    def clear_cache(self):
        """
        Clear in-memory cache (for testing or manual refresh)
        """
        self._cache.clear()
        logger.info("🗑️ Exchange rate cache cleared")

    def get_cache_status(self) -> Dict:
        """
        Get cache status for monitoring

        Returns:
            Dictionary with cache information:
            {
                'cached_currencies': List[str],
                'cache_count': int,
                'oldest_cache': str (ISO format),
                'newest_cache': str (ISO format)
            }
        """
        if not self._cache:
            return {
                'cached_currencies': [],
                'cache_count': 0,
                'oldest_cache': None,
                'newest_cache': None
            }

        timestamps = [data['timestamp'] for data in self._cache.values()]

        return {
            'cached_currencies': list(self._cache.keys()),
            'cache_count': len(self._cache),
            'oldest_cache': min(timestamps).isoformat() if timestamps else None,
            'newest_cache': max(timestamps).isoformat() if timestamps else None
        }
