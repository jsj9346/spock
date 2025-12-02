"""
Auto-Backfill Orchestrator for Backtesting Data Provider

Coordinates multi-source data fetching with priority-based fallback.
Automatically fills missing OHLCV data from external APIs (pykrx, yfinance, KIS, DART).

Author: Spock Quant Platform
Date: 2025-10-29
Version: 1.0.0
"""

import pandas as pd
from datetime import date, timedelta
from typing import Optional, List, Tuple, Dict, Any
from loguru import logger

from modules.api_clients.pykrx_api import PyKRXAPI
from modules.api_clients.yfinance_api import YFinanceAPI


class BackfillOrchestrator:
    """
    Coordinate data backfilling from multiple API sources.

    API Priority by Region:
    - KR: KIS API → pykrx → yfinance
    - US: yfinance → KIS API
    - CN/HK/JP: yfinance → KIS API

    Fundamental Data:
    - KR: DART → KIS API
    - Global: yfinance
    """

    def __init__(self, db_manager):
        """
        Initialize BackfillOrchestrator.

        Args:
            db_manager: PostgresDatabaseManager instance for data persistence
        """
        self.db = db_manager

        # Initialize API clients (lazy initialization for auth-required APIs)
        self.apis = {
            'kis': None,  # Lazy init (requires authentication)
            'pykrx': PyKRXAPI(),
            'yfinance': YFinanceAPI(rate_limit_per_second=1.0),
            'dart': None  # Lazy init (requires API key)
        }

        # API priority mapping by region
        self.ohlcv_priority = {
            'KR': ['kis', 'pykrx', 'yfinance'],
            'US': ['yfinance', 'kis'],
            'CN': ['yfinance', 'kis'],
            'HK': ['yfinance', 'kis'],
            'JP': ['yfinance', 'kis'],
            'VN': ['kis']
        }

        self.fundamental_priority = {
            'KR': ['dart', 'kis'],
            'US': ['yfinance'],
            'default': ['yfinance']
        }

        # Validation configuration
        self.validation_config = {
            'min_records_per_year': 200,  # ~250 trading days
            'max_price_change_pct': 50.0,  # 50% max daily change
            'allow_zero_volume': False,
            'require_ohlc_consistency': True  # Open/Close within High/Low
        }

        logger.info("✅ BackfillOrchestrator initialized")

    def backfill_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d',
        existing_data: Optional[pd.DataFrame] = None
    ) -> Optional[pd.DataFrame]:
        """
        Backfill OHLCV data from external APIs.

        Strategy:
        1. Identify missing date ranges
        2. Try API sources by priority
        3. Validate fetched data
        4. Merge with existing data
        5. Save to PostgreSQL
        6. Return complete dataset

        Args:
            ticker: Stock ticker symbol
            region: Market region code (KR, US, CN, etc.)
            start_date: Start date for backfill
            end_date: End date for backfill
            timeframe: Data timeframe (default: '1d')
            existing_data: Existing data from PostgreSQL (optional)

        Returns:
            Complete DataFrame or None if all sources fail
        """
        logger.info(f"🔄 Backfill requested: {ticker} ({region}) {start_date} to {end_date}")

        # Step 1: Identify missing ranges
        missing_ranges = self._identify_missing_ranges(
            existing_data, start_date, end_date, region
        )

        if not missing_ranges:
            logger.debug(f"✅ No missing data for {ticker}")
            return existing_data

        total_missing_days = sum((r[1] - r[0]).days + 1 for r in missing_ranges)
        logger.info(
            f"🔍 Missing data detected: {len(missing_ranges)} gaps "
            f"(total ~{total_missing_days} days)"
        )

        # Step 2: Try API sources by priority
        priority_list = self.ohlcv_priority.get(region, ['yfinance'])

        fetched_data = []
        for api_name in priority_list:
            try:
                logger.info(f"📡 Attempting backfill from {api_name}...")

                api_client = self._get_api_client(api_name)
                if api_client is None:
                    logger.warning(f"⚠️ {api_name} not available, skipping")
                    continue

                # Fetch from API
                df = self._fetch_from_api(
                    api_client,
                    api_name,
                    ticker,
                    region,
                    start_date,
                    end_date
                )

                if df is None or df.empty:
                    logger.warning(f"❌ No data from {api_name}")
                    continue

                # Step 3: Validate
                is_valid, validation_errors = self._validate_ohlcv_data(df, ticker)
                if not is_valid:
                    logger.error(
                        f"❌ Validation failed for {ticker} from {api_name}: "
                        f"{validation_errors}"
                    )
                    continue

                # Success!
                logger.info(f"✅ Fetched {len(df)} records from {api_name}")
                fetched_data.append(df)
                break  # Stop trying other sources

            except Exception as e:
                logger.error(f"❌ Failed to fetch from {api_name}: {e}")
                continue

        if not fetched_data:
            logger.error(f"❌ All API sources failed for {ticker}")
            return existing_data

        # Step 4: Merge with existing data
        complete_df = self._merge_data(existing_data, fetched_data[0])

        # Step 5: Save to PostgreSQL
        try:
            self._save_to_postgres(complete_df, ticker, region, timeframe)
            logger.info(f"💾 Saved {len(complete_df)} records to PostgreSQL")
        except Exception as e:
            logger.error(f"❌ Failed to save backfilled data: {e}")
            # Still return the merged data even if save fails

        return complete_df

    def _identify_missing_ranges(
        self,
        existing_data: Optional[pd.DataFrame],
        start_date: date,
        end_date: date,
        region: str
    ) -> List[Tuple[date, date]]:
        """
        Identify missing date ranges in existing data.

        Args:
            existing_data: DataFrame with existing OHLCV data
            start_date: Start of requested range
            end_date: End of requested range
            region: Market region for holiday calculation

        Returns:
            List of (start_date, end_date) tuples for missing ranges
        """
        # Implementation in Step 1.4
        if existing_data is None or existing_data.empty:
            return [(start_date, end_date)]

        # Convert to date range
        existing_dates = pd.to_datetime(existing_data['date']).dt.date.unique()

        # Generate expected trading days (simplified - business days only)
        all_dates = pd.date_range(start_date, end_date, freq='B')  # Business days
        expected_dates = [d.date() for d in all_dates]

        # Find missing dates
        missing_dates = set(expected_dates) - set(existing_dates)

        if not missing_dates:
            return []

        # Group consecutive missing dates into ranges
        sorted_missing = sorted(missing_dates)
        ranges = []
        range_start = sorted_missing[0]
        range_end = sorted_missing[0]

        for i in range(1, len(sorted_missing)):
            # Allow small gaps (weekends/holidays)
            if (sorted_missing[i] - sorted_missing[i-1]).days <= 5:
                range_end = sorted_missing[i]
            else:
                ranges.append((range_start, range_end))
                range_start = sorted_missing[i]
                range_end = sorted_missing[i]

        ranges.append((range_start, range_end))
        return ranges

    def _fetch_from_api(
        self,
        api_client,
        api_name: str,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from specific API.

        Args:
            api_client: API client instance
            api_name: API identifier (pykrx, yfinance, kis, dart)
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with OHLCV data or None
        """
        # Implementation in Steps 2.1, 2.2
        if api_name == 'pykrx':
            # pykrx API
            days = (end_date - start_date).days
            ohlcv_list = api_client.get_ohlcv(ticker, days=days)
            if not ohlcv_list:
                return None
            df = pd.DataFrame(ohlcv_list)
            return df

        elif api_name == 'yfinance':
            # yfinance API
            yf_ticker = self._convert_to_yfinance_ticker(ticker, region)

            import yfinance as yf
            stock = yf.Ticker(yf_ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                return None

            # Standardize column names
            df = df.reset_index()
            df.columns = [col.lower() for col in df.columns]

            # Rename to match internal schema
            column_map = {
                'date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }
            df = df.rename(columns=column_map)
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

            return df

        elif api_name == 'kis':
            # KIS API (requires implementation)
            logger.warning("⚠️ KIS API backfill not yet implemented")
            return None

        else:
            logger.error(f"❌ Unknown API: {api_name}")
            return None

    def _validate_ohlcv_data(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate OHLCV data quality.

        Validation Levels:
        1. Structural: Required columns, no NULLs
        2. Business Logic: OHLC consistency, reasonable price changes
        3. Statistical: Outlier detection (warning only)

        Args:
            df: DataFrame to validate
            ticker: Stock ticker (for logging)

        Returns:
            (is_valid: bool, errors: List[str])
        """
        # Implementation in Step 3.1
        errors = []

        # Level 1: Structural validation
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")
            return False, errors

        # Check for NULL values
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            errors.append(f"NULL values found: {null_counts[null_counts > 0].to_dict()}")

        # Level 2: Business logic validation
        if self.validation_config['require_ohlc_consistency']:
            ohlc_invalid = (
                (df['open'] > df['high']) |
                (df['open'] < df['low']) |
                (df['close'] > df['high']) |
                (df['close'] < df['low'])
            )
            if ohlc_invalid.any():
                errors.append(
                    f"OHLC inconsistency detected in {ohlc_invalid.sum()} rows "
                    f"(open/close outside high/low range)"
                )

        # Price change validation
        df_sorted = df.sort_values('date')
        price_changes = df_sorted['close'].pct_change().abs() * 100
        extreme_changes = price_changes > self.validation_config['max_price_change_pct']
        if extreme_changes.any():
            extreme_count = extreme_changes.sum()
            max_change = price_changes.max()
            errors.append(
                f"Extreme price changes: {extreme_count} days >{self.validation_config['max_price_change_pct']}% "
                f"(max: {max_change:.1f}%)"
            )

        # Volume validation
        if not self.validation_config['allow_zero_volume']:
            zero_volume = (df['volume'] <= 0).sum()
            if zero_volume > 0:
                errors.append(f"Zero/negative volume in {zero_volume} rows")

        # Level 3: Statistical validation (warning only)
        years = (pd.to_datetime(df['date']).max() - pd.to_datetime(df['date']).min()).days / 365.25
        min_expected = int(years * self.validation_config['min_records_per_year'])
        if len(df) < min_expected and years > 0.5:
            logger.warning(
                f"⚠️ Sparse data: {len(df)} records < {min_expected} expected "
                f"({years:.1f} years × {self.validation_config['min_records_per_year']} days/year)"
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    def _merge_data(
        self,
        existing_df: Optional[pd.DataFrame],
        new_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge existing and newly fetched data.

        Strategy:
        - Existing data takes precedence (higher quality)
        - New data fills gaps only
        - Remove duplicates (keep existing)
        - Sort by date

        Args:
            existing_df: Existing data from PostgreSQL
            new_df: Newly fetched data from API

        Returns:
            Merged DataFrame
        """
        # Implementation in Step 3.2
        if existing_df is None or existing_df.empty:
            return new_df

        if new_df is None or new_df.empty:
            return existing_df

        # Ensure date columns are datetime
        existing_df['date'] = pd.to_datetime(existing_df['date'])
        new_df['date'] = pd.to_datetime(new_df['date'])

        # Concatenate
        combined = pd.concat([existing_df, new_df], ignore_index=True)

        # Remove duplicates (keep first = existing data priority)
        combined = combined.drop_duplicates(subset=['date'], keep='first')

        # Sort by date
        combined = combined.sort_values('date').reset_index(drop=True)

        logger.info(
            f"📊 Merged: {len(existing_df)} existing + {len(new_df)} new → "
            f"{len(combined)} total ({len(combined) - len(existing_df)} added)"
        )

        return combined

    def _save_to_postgres(
        self,
        df: pd.DataFrame,
        ticker: str,
        region: str,
        timeframe: str
    ):
        """
        Save backfilled data to PostgreSQL.

        Uses PostgresDatabaseManager's insert_ohlcv_bulk method for efficient
        bulk insertion via PostgreSQL COPY command.

        Args:
            df: DataFrame with OHLCV data
            ticker: Stock ticker symbol
            region: Market region code
            timeframe: Data timeframe
        """
        # Prepare DataFrame for bulk insert
        # insert_ohlcv_bulk expects: ticker, ohlcv_df, region, timeframe

        # Make a copy to avoid modifying original
        df_to_save = df.copy()

        # Ensure date column is in correct format
        if 'date' in df_to_save.columns:
            df_to_save['date'] = pd.to_datetime(df_to_save['date'])

        # Use db_manager's insert_ohlcv_bulk method
        # This method handles the COPY command and bulk insertion efficiently
        self.db.insert_ohlcv_bulk(
            ticker=ticker,
            ohlcv_df=df_to_save,
            region=region,
            timeframe=timeframe
        )

        logger.debug(f"💾 Saved {len(df_to_save)} records via insert_ohlcv_bulk")

    def _get_api_client(self, api_name: str):
        """
        Get or lazily initialize API client.

        Args:
            api_name: API identifier

        Returns:
            API client instance or None
        """
        if api_name not in self.apis:
            return None

        if self.apis[api_name] is not None:
            return self.apis[api_name]

        # Lazy initialization for auth-required APIs
        if api_name == 'kis':
            try:
                from modules.api_clients.base_kis_api import KISApiClient
                self.apis['kis'] = KISApiClient()
                logger.info("✅ KIS API initialized")
            except Exception as e:
                logger.warning(f"⚠️ KIS API initialization failed: {e}")
                return None

        elif api_name == 'dart':
            try:
                from modules.dart_api_client import DARTApiClient
                self.apis['dart'] = DARTApiClient()
                logger.info("✅ DART API initialized")
            except Exception as e:
                logger.warning(f"⚠️ DART API initialization failed: {e}")
                return None

        return self.apis[api_name]

    def _convert_to_yfinance_ticker(self, ticker: str, region: str) -> str:
        """
        Convert internal ticker format to yfinance format.

        Args:
            ticker: Internal ticker symbol
            region: Market region

        Returns:
            yfinance-compatible ticker symbol
        """
        suffix_map = {
            'KR': '.KS',  # KOSPI (KOSDAQ might be .KQ)
            'US': '',     # No suffix needed
            'HK': '.HK',
            'JP': '.T',
            'CN': '.SS',  # Shanghai Stock Exchange
        }

        suffix = suffix_map.get(region, '')

        # Special handling for US tickers with '/'
        if region == 'US':
            # US preferred stocks/classes: DB uses '/' but yfinance uses '.'
            # e.g., BRK/B → BRK.B, MS/A → MS.A
            return ticker.replace('/', '-') if '/' in ticker else ticker

        # Special handling for Korean tickers
        if region == 'KR':
            # KOSDAQ tickers need .KQ suffix
            # This requires market detection (simplified here)
            return f"{ticker}{suffix}"

        return f"{ticker}{suffix}"
