"""
FX Tracker - Exchange Rate Tracking and Signal Generation

Handles:
- Multi-currency exchange rate data collection
- Historical rate storage with INSERT ... ON CONFLICT DO NOTHING
- FX signal generation (rapid appreciation/depreciation detection)
- Region-specific currency mapping

Database Strategy:
- Exchange rates are immutable time-series data
- Use INSERT with conflict handling to prevent duplicates
- No updates needed for historical rates

Author: Spock Quant Platform
Date: 2025-11-05
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Set
from decimal import Decimal

logger = logging.getLogger(__name__)


class FXTracker:
    """
    Exchange rate tracker with FX signal generation

    Features:
    - Fetch exchange rates from multiple sources
    - Store rates in TimescaleDB-optimized table
    - Calculate FX signals (rapid moves, volatility)
    - Region-specific currency mapping

    Usage:
        tracker = FXTracker(db_manager=db)
        result = tracker.update_exchange_rates(
            currencies=['USD', 'JPY', 'EUR'],
            dry_run=False
        )
    """

    # Region-specific currency mappings
    REGION_CURRENCIES = {
        'KR': {'USD', 'JPY', 'CNY', 'EUR', 'HKD'},  # Korean market cares about these
        'US': {'KRW', 'EUR', 'JPY', 'GBP'},  # US market
        'JP': {'USD', 'EUR', 'CNY', 'KRW'},  # Japanese market
        'CN': {'USD', 'EUR', 'JPY', 'HKD'},  # Chinese market
        'HK': {'USD', 'CNY', 'JPY', 'EUR', 'HKD'},  # Hong Kong
        'VN': {'USD', 'CNY', 'JPY', 'KRW'},  # Vietnam
    }

    # Currency to region mapping (for fx_valuation_signals table)
    CURRENCY_REGION_MAP = {
        'USD': 'US',
        'JPY': 'JP',
        'CNY': 'CN',
        'EUR': 'EU',
        'GBP': 'UK',
        'HKD': 'HK',
        'KRW': 'KR',
        'VND': 'VN'
    }

    # FX signal thresholds
    RAPID_MOVE_THRESHOLD = 0.02  # 2% daily change
    VOLATILITY_WINDOW = 20  # 20-day rolling volatility
    HIGH_VOLATILITY_THRESHOLD = 0.015  # 1.5% daily volatility

    def __init__(self, db_manager=None, base_currency: str = 'KRW',
                 notification_service=None):
        """
        Initialize FX Tracker

        Args:
            db_manager: Database manager instance (PostgresDatabaseManager)
            base_currency: Base currency for conversions (default: KRW)
            notification_service: FXNotificationService instance (optional)
        """
        self.db = db_manager
        self.base_currency = base_currency
        self.notification_service = notification_service
        self.logger = logger

        # Lazy-loaded API client
        self._api_client = None

    def update_exchange_rates(self, currencies: List[str],
                              dry_run: bool = False) -> Dict:
        """
        Update exchange rates for specified currencies

        Args:
            currencies: List of currency codes (e.g., ['USD', 'JPY', 'EUR'])
            dry_run: If True, fetch but don't insert into DB

        Returns:
            Dict with keys:
                - updated: Number of rates inserted
                - signals: Number of FX signals generated
                - signals_inserted: Number of FX signals saved to database
                - notifications: Dict with notification results (critical_sent, warning_queued, etc.)
                - success: Boolean indicating success
                - rates: Dict of currency -> rate (for validation)
                - fx_signals: List of generated signal dicts
        """
        try:
            self.logger.info(f"🔄 Updating exchange rates for {len(currencies)} currencies...")

            # 1. Fetch rates from API
            rates = self._fetch_rates(currencies)

            if not rates:
                self.logger.warning("⚠️  No exchange rates fetched")
                return {'updated': 0, 'signals': 0, 'success': False}

            # 2. Insert into database (unless dry run)
            inserted = 0
            valuation_inserted = 0
            if not dry_run and self.db:
                inserted = self._insert_rates(rates)
                valuation_inserted = self._insert_to_valuation_signals(rates)

            # 3. Calculate FX signals
            signals = self._calculate_signals(rates)

            # 4. Insert FX signals into database (unless dry run)
            signals_inserted = 0
            if not dry_run and self.db and signals:
                signals_inserted = self._insert_fx_signals(signals)

            # 5. Send notifications (unless dry run)
            notifications_result = {}
            if not dry_run and self.notification_service and signals:
                notifications_result = self.notification_service.notify_fx_signals(signals)

            self.logger.info(
                f"✅ FX update complete: {inserted} rates inserted, "
                f"{valuation_inserted} valuation signals updated, "
                f"{len(signals)} signals generated, {signals_inserted} signals saved, "
                f"{notifications_result.get('critical_sent', 0)} CRITICAL notifications sent"
            )

            return {
                'updated': inserted,
                'valuation_updated': valuation_inserted,
                'signals': len(signals),
                'signals_inserted': signals_inserted,
                'notifications': notifications_result,
                'success': True,
                'rates': rates,  # For validation
                'fx_signals': signals
            }

        except Exception as e:
            self.logger.error(f"❌ FX update failed: {e}")
            return {'updated': 0, 'signals': 0, 'success': False, 'error': str(e)}

    def _fetch_rates(self, currencies: List[str]) -> Dict[str, Decimal]:
        """
        Fetch exchange rates from API

        Args:
            currencies: List of currency codes

        Returns:
            Dict mapping currency code to rate (vs base currency)
            Example: {'USD': Decimal('1350.50'), 'JPY': Decimal('10.25')}
        """
        if not self._api_client:
            # Lazy load API client
            try:
                from modules.fx_tracking.exchange_rate_api import ExchangeRateAPI
                self._api_client = ExchangeRateAPI(base_currency=self.base_currency)
            except ImportError:
                # Fallback: use mock rates for testing
                self.logger.warning("⚠️  ExchangeRateAPI not available, using mock rates")
                return self._get_mock_rates(currencies)

        try:
            rates = self._api_client.get_rates(currencies)
            self.logger.debug(f"Fetched {len(rates)} exchange rates")
            return rates
        except Exception as e:
            self.logger.error(f"Failed to fetch rates from API: {e}")
            return {}

    def _get_mock_rates(self, currencies: List[str]) -> Dict[str, Decimal]:
        """
        Generate mock exchange rates for testing

        Args:
            currencies: List of currency codes

        Returns:
            Dict of mock rates (vs KRW)
        """
        # Mock rates (1 foreign currency = X KRW)
        mock_rates = {
            'USD': Decimal('1350.50'),
            'JPY': Decimal('10.25'),
            'EUR': Decimal('1450.75'),
            'CNY': Decimal('185.30'),
            'GBP': Decimal('1720.00'),
            'HKD': Decimal('172.50'),
        }

        return {cur: mock_rates.get(cur, Decimal('1.0')) for cur in currencies}

    def _insert_rates(self, rates: Dict[str, Decimal]) -> int:
        """
        Insert exchange rates into database

        Strategy: INSERT ... ON CONFLICT DO NOTHING
        - Exchange rates are immutable historical data
        - Duplicate date + currency pairs are silently ignored

        Args:
            rates: Dict mapping currency to rate

        Returns:
            Number of records inserted (0 if all duplicates)
        """
        if not rates or not self.db:
            return 0

        query = """
            INSERT INTO exchange_rates (
                base_currency, quote_currency, date, rate, source, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (base_currency, quote_currency, date)
            DO NOTHING
        """

        today = date.today()
        source = 'exchangerates_api'

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare batch values
            values = [
                (
                    self.base_currency,  # base (KRW)
                    currency,            # quote (USD, JPY, etc.)
                    today,
                    float(rate),         # Convert Decimal to float for DB
                    source
                )
                for currency, rate in rates.items()
            ]

            # Execute batch insert
            cursor.executemany(query, values)
            inserted = cursor.rowcount
            conn.commit()

            self.logger.debug(f"Inserted {inserted} exchange rates")
            return inserted

    def _insert_to_valuation_signals(self, rates: Dict[str, Decimal]) -> int:
        """
        Insert exchange rates into fx_valuation_signals table

        Strategy: INSERT ... ON CONFLICT DO UPDATE
        - fx_valuation_signals stores USD-normalized rates with derived metrics
        - Updates existing records if date + currency + region already exists

        Args:
            rates: Dict mapping currency to rate (vs base_currency)

        Returns:
            Number of records inserted/updated
        """
        if not rates or not self.db:
            return 0

        # Step 1: Calculate USD-normalized rates
        usd_rates = self._normalize_to_usd(rates)

        # Step 2: Get historical data for trend calculation
        historical_rates = self._get_historical_usd_rates(list(usd_rates.keys()), days=20)

        query = """
            INSERT INTO fx_valuation_signals (
                currency, region, date, usd_rate,
                trend_score, volatility, attractiveness_score,
                data_quality, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON CONFLICT (currency, region, date)
            DO UPDATE SET
                usd_rate = EXCLUDED.usd_rate,
                trend_score = EXCLUDED.trend_score,
                volatility = EXCLUDED.volatility,
                attractiveness_score = EXCLUDED.attractiveness_score,
                data_quality = EXCLUDED.data_quality,
                updated_at = NOW()
        """

        today = date.today()

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            inserted = 0

            for currency, usd_rate in usd_rates.items():
                # Get region for this currency
                region = self.CURRENCY_REGION_MAP.get(currency)
                if not region:
                    self.logger.warning(f"No region mapping for currency {currency}, skipping")
                    continue

                # Calculate derived metrics
                hist_data = historical_rates.get(currency, [])
                trend_score = self._calculate_trend_score(hist_data, float(usd_rate))
                volatility = self._calculate_volatility(hist_data)
                attractiveness_score = self._calculate_attractiveness(
                    trend_score, volatility
                )

                # Determine data quality
                data_quality = 'GOOD' if len(hist_data) >= 10 else 'PARTIAL'

                cursor.execute(query, (
                    currency,
                    region,
                    today,
                    float(usd_rate),
                    trend_score,
                    volatility,
                    attractiveness_score,
                    data_quality
                ))

                inserted += cursor.rowcount

            conn.commit()

            self.logger.debug(
                f"Inserted/updated {inserted} fx_valuation_signals records"
            )
            return inserted

    def _normalize_to_usd(self, rates: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """
        Normalize rates to USD base

        Args:
            rates: Dict of rates vs base_currency (e.g., KRW)

        Returns:
            Dict of USD-normalized rates
        """
        usd_rates = {}

        if self.base_currency == 'USD':
            # Already USD-based
            return rates

        # Get USD rate vs base_currency
        usd_rate = rates.get('USD')
        if not usd_rate:
            self.logger.warning(
                "USD rate not available, cannot normalize to USD"
            )
            return {}

        # Convert all rates to USD base
        for currency, rate in rates.items():
            if currency == 'USD':
                usd_rates['USD'] = Decimal('1.0')  # USD/USD = 1
            else:
                # Example: KRW/JPY = 10, KRW/USD = 1300
                # USD/JPY = (KRW/JPY) / (KRW/USD) = 10 / 1300 = 0.0077
                usd_rates[currency] = rate / usd_rate

        return usd_rates

    def _get_historical_usd_rates(
        self, currencies: List[str], days: int = 20
    ) -> Dict[str, List[float]]:
        """
        Get historical USD-normalized rates for trend calculation

        Args:
            currencies: List of currency codes
            days: Number of historical days to fetch

        Returns:
            Dict mapping currency to list of historical USD rates
        """
        if not self.db:
            return {}

        query = """
            SELECT currency, usd_rate
            FROM fx_valuation_signals
            WHERE currency = ANY(%s)
                AND date >= %s
                AND date < %s
                AND data_quality = 'GOOD'
            ORDER BY currency, date ASC
        """

        lookback_date = date.today() - timedelta(days=days)

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                currencies,
                lookback_date,
                date.today()
            ))

            results = cursor.fetchall()

            # Group by currency
            hist_data = {}
            for currency, usd_rate in results:
                if currency not in hist_data:
                    hist_data[currency] = []
                hist_data[currency].append(float(usd_rate))

            return hist_data

    def _calculate_trend_score(
        self, historical_rates: List[float], current_rate: float
    ) -> float:
        """
        Calculate trend score from historical rates

        Args:
            historical_rates: List of past USD rates
            current_rate: Current USD rate

        Returns:
            Trend score (-1.0 to 1.0)
        """
        if not historical_rates or len(historical_rates) < 2:
            return 0.0

        # Simple momentum: (current - average) / average
        avg_rate = sum(historical_rates) / len(historical_rates)

        if avg_rate == 0:
            return 0.0

        momentum = (current_rate - avg_rate) / avg_rate

        # Normalize to -1.0 to 1.0 range (clip at ±20%)
        trend_score = max(-1.0, min(1.0, momentum * 5))

        return round(trend_score, 4)

    def _calculate_volatility(self, historical_rates: List[float]) -> float:
        """
        Calculate volatility from historical rates

        Args:
            historical_rates: List of past USD rates

        Returns:
            Volatility (standard deviation of returns)
        """
        if not historical_rates or len(historical_rates) < 2:
            return 0.0

        # Calculate daily returns
        returns = []
        for i in range(1, len(historical_rates)):
            if historical_rates[i-1] != 0:
                ret = (historical_rates[i] - historical_rates[i-1]) / historical_rates[i-1]
                returns.append(ret)

        if not returns:
            return 0.0

        # Standard deviation of returns
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5

        return round(volatility, 6)

    def _calculate_attractiveness(
        self, trend_score: float, volatility: float
    ) -> float:
        """
        Calculate currency attractiveness score

        Args:
            trend_score: Trend score (-1.0 to 1.0)
            volatility: Volatility (std dev of returns)

        Returns:
            Attractiveness score (0.0 to 1.0)
        """
        # Simple formula: positive trend + low volatility = attractive
        # Normalize volatility (assume 0.02 = high volatility)
        vol_penalty = min(1.0, volatility / 0.02)

        # Attractiveness: 0.5 + 0.3*trend - 0.2*volatility
        attractiveness = 0.5 + (0.3 * trend_score) - (0.2 * vol_penalty)

        # Clip to 0-1 range
        attractiveness = max(0.0, min(1.0, attractiveness))

        return round(attractiveness, 4)

    def _calculate_signals(self, current_rates: Dict[str, Decimal]) -> List[Dict]:
        """
        Calculate FX signals from current rates

        Signals detected:
        1. Rapid appreciation (>2% daily increase)
        2. Rapid depreciation (>2% daily decrease)
        3. High volatility (>1.5% 20-day volatility)

        Args:
            current_rates: Dict of current exchange rates

        Returns:
            List of signal dicts with keys:
                - currency: Currency code
                - signal_type: 'rapid_appreciation', 'rapid_depreciation', 'high_volatility'
                - magnitude: Absolute change percentage
                - current_rate: Current rate
                - previous_rate: Previous rate (if applicable)
        """
        signals = []

        if not self.db:
            return signals  # Cannot calculate without historical data

        # Get previous day's rates
        previous_rates = self._get_previous_rates(list(current_rates.keys()))

        for currency, current_rate in current_rates.items():
            previous_rate = previous_rates.get(currency)

            if previous_rate:
                # Calculate daily change
                change_pct = float((current_rate - previous_rate) / previous_rate)

                # Signal 1: Rapid appreciation
                if change_pct > self.RAPID_MOVE_THRESHOLD:
                    signals.append({
                        'currency': currency,
                        'signal_type': 'rapid_appreciation',
                        'magnitude': abs(change_pct),
                        'current_rate': float(current_rate),
                        'previous_rate': float(previous_rate),
                        'date': date.today()
                    })

                # Signal 2: Rapid depreciation
                elif change_pct < -self.RAPID_MOVE_THRESHOLD:
                    signals.append({
                        'currency': currency,
                        'signal_type': 'rapid_depreciation',
                        'magnitude': abs(change_pct),
                        'current_rate': float(current_rate),
                        'previous_rate': float(previous_rate),
                        'date': date.today()
                    })

        # Signal 3: High volatility (requires 20-day history)
        volatility_signals = self._detect_high_volatility(list(current_rates.keys()))
        signals.extend(volatility_signals)

        return signals

    def _insert_fx_signals(self, signals: List[Dict]) -> int:
        """
        FX 신호를 fx_signals 테이블에 저장

        Strategy: 중복 신호 방지 (currency + date + signal_type 조합)
        - 동일 날짜 + 통화 + 신호타입 조합은 하루에 1번만 저장
        - 중복 시그널은 무시 (INSERT ... ON CONFLICT DO NOTHING 사용 불가 - unique constraint 없음)
        - 대신 INSERT 전 SELECT로 중복 체크

        Args:
            signals: _calculate_signals()에서 생성된 신호 리스트

        Returns:
            Number of signals inserted (0 if all duplicates)

        Example:
            >>> signals = [
            ...     {'currency': 'USD', 'signal_type': 'rapid_appreciation',
            ...      'magnitude': 0.025, 'current_rate': 1350.50,
            ...      'previous_rate': 1320.00, 'date': date.today()}
            ... ]
            >>> inserted = tracker._insert_fx_signals(signals)
            >>> print(f"Inserted {inserted} signals")
        """
        if not signals or not self.db:
            return 0

        query_insert = """
            INSERT INTO fx_signals (
                currency, signal_type, magnitude,
                current_rate, previous_rate, date, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, NOW()
            )
        """

        query_check_duplicate = """
            SELECT COUNT(*) FROM fx_signals
            WHERE currency = %s
              AND signal_type = %s
              AND date = %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            inserted = 0

            for signal in signals:
                # 1. 중복 체크
                cursor.execute(query_check_duplicate, (
                    signal['currency'],
                    signal['signal_type'],
                    signal['date']
                ))

                duplicate_count = cursor.fetchone()[0]

                if duplicate_count > 0:
                    self.logger.debug(
                        f"Skipping duplicate signal: {signal['currency']} "
                        f"{signal['signal_type']} on {signal['date']}"
                    )
                    continue

                # 2. INSERT 신호
                cursor.execute(query_insert, (
                    signal['currency'],
                    signal['signal_type'],
                    signal['magnitude'],
                    signal.get('current_rate'),      # Optional (high_volatility에는 없음)
                    signal.get('previous_rate'),     # Optional
                    signal['date']
                ))

                inserted += cursor.rowcount

            conn.commit()

            self.logger.debug(f"Inserted {inserted} FX signals (skipped {len(signals) - inserted} duplicates)")
            return inserted

    def _get_previous_rates(self, currencies: List[str]) -> Dict[str, Decimal]:
        """
        Get exchange rates from previous trading day

        Args:
            currencies: List of currency codes

        Returns:
            Dict mapping currency to previous rate
        """
        if not self.db:
            return {}

        query = """
            SELECT quote_currency, rate
            FROM exchange_rates
            WHERE base_currency = %s
                AND quote_currency = ANY(%s)
                AND date < %s
            ORDER BY date DESC
            LIMIT %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                self.base_currency,
                currencies,
                date.today(),
                len(currencies)
            ))

            results = cursor.fetchall()
            return {row[0]: Decimal(str(row[1])) for row in results}

    def _detect_high_volatility(self, currencies: List[str]) -> List[Dict]:
        """
        Detect high volatility currencies (20-day rolling std dev)

        Args:
            currencies: List of currency codes

        Returns:
            List of volatility signal dicts
        """
        signals = []

        if not self.db:
            return signals

        query = """
            WITH daily_returns AS (
                SELECT
                    quote_currency,
                    date,
                    rate,
                    LAG(rate) OVER (PARTITION BY quote_currency ORDER BY date) as prev_rate
                FROM exchange_rates
                WHERE base_currency = %s
                    AND quote_currency = ANY(%s)
                    AND date >= %s
            ),
            volatility AS (
                SELECT
                    quote_currency,
                    STDDEV((rate - prev_rate) / prev_rate) as vol_20d
                FROM daily_returns
                WHERE prev_rate IS NOT NULL
                GROUP BY quote_currency
            )
            SELECT quote_currency, vol_20d
            FROM volatility
            WHERE vol_20d > %s
        """

        lookback_date = date.today() - timedelta(days=self.VOLATILITY_WINDOW)

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                self.base_currency,
                currencies,
                lookback_date,
                self.HIGH_VOLATILITY_THRESHOLD
            ))

            results = cursor.fetchall()
            for row in results:
                signals.append({
                    'currency': row[0],
                    'signal_type': 'high_volatility',
                    'magnitude': float(row[1]),
                    'date': date.today()
                })

        return signals

    @staticmethod
    def get_currencies_for_regions(regions: List[str]) -> List[str]:
        """
        Get currencies relevant for given regions

        Args:
            regions: List of region codes (e.g., ['KR', 'US'])

        Returns:
            List of unique currency codes

        Example:
            >>> FXTracker.get_currencies_for_regions(['KR', 'US'])
            ['USD', 'JPY', 'CNY', 'EUR', 'KRW', 'GBP']
        """
        currencies: Set[str] = set()

        for region in regions:
            if region in FXTracker.REGION_CURRENCIES:
                currencies.update(FXTracker.REGION_CURRENCIES[region])

        return sorted(list(currencies))
