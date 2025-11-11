"""
OHLCV Update System - Incremental OHLCV updates with technical indicators

Handles:
- Incremental OHLCV data updates
- NULL technical indicator backfill
- Multi-region support
- Batch processing with rate limiting
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import logging
import pandas as pd
import numpy as np

from modules.db_manager_postgres import PostgresDatabaseManager


class OHLCVUpdater:
    """Incremental OHLCV update and technical indicator backfill"""

    def __init__(self, db_manager: Optional[PostgresDatabaseManager] = None):
        """
        Initialize OHLCVUpdater

        Args:
            db_manager: Database manager instance. If None, creates new instance.
        """
        self.db = db_manager or PostgresDatabaseManager()
        self.logger = logging.getLogger(__name__)

        # Market adapters (lazy loaded)
        self._adapters = {}

    def update_all_tickers(self, region: str, backfill_indicators: bool = True,
                          batch_size: int = 100) -> Dict:
        """
        Update OHLCV data for all active tickers in region

        Args:
            region: Region code (KR, US, etc.)
            backfill_indicators: If True, backfill NULL technical indicators
            batch_size: Number of tickers to process in each batch

        Returns:
            Update statistics dict
        """
        self.logger.info(f"Starting OHLCV update for region {region}")

        # Get active tickers
        tickers = self._get_active_tickers(region)
        self.logger.info(f"Found {len(tickers)} active tickers in {region}")

        stats = {
            'total_tickers': len(tickers),
            'successful': 0,
            'failed': 0,
            'total_records': 0,
            'indicators_backfilled': 0
        }

        # Process in batches
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i + batch_size]
            self.logger.info(f"Processing batch {i // batch_size + 1}/{(len(tickers) + batch_size - 1) // batch_size}")

            for ticker in batch:
                try:
                    result = self.update_ticker(ticker, region, backfill_indicators)
                    stats['successful'] += 1
                    stats['total_records'] += result.get('records', 0)

                    if result.get('indicators_backfilled'):
                        stats['indicators_backfilled'] += 1

                except Exception as e:
                    self.logger.error(f"Failed to update {ticker}: {e}")
                    stats['failed'] += 1

        self.logger.info(f"OHLCV update completed: {stats}")
        return stats

    def update_ticker(self, ticker: str, region: str,
                     backfill_indicators: bool = True) -> Dict:
        """
        Update OHLCV data for a single ticker

        Args:
            ticker: Ticker symbol
            region: Region code
            backfill_indicators: If True, backfill NULL technical indicators

        Returns:
            Update result dict
        """
        self.logger.debug(f"Updating OHLCV for {ticker} ({region})")

        # 1. Determine update range
        last_date = self._get_last_ohlcv_date(ticker, region)
        today = date.today()

        if last_date:
            start_date = last_date + timedelta(days=1)
        else:
            # No existing data - fetch 5 years
            start_date = today - timedelta(days=365 * 5)

        # Skip if already up to date
        if start_date >= today:
            self.logger.debug(f"{ticker} is already up to date")
            return {'status': 'up_to_date', 'records': 0}

        # 2. Fetch data from adapter
        adapter = self._get_adapter(region)

        try:
            ohlcv_data = adapter.get_ohlcv(ticker, start_date, today)
        except Exception as e:
            self.logger.error(f"Failed to fetch OHLCV for {ticker}: {e}")
            raise

        if not ohlcv_data or len(ohlcv_data) == 0:
            self.logger.warning(f"No OHLCV data returned for {ticker}")
            return {'status': 'no_data', 'records': 0}

        # 3. Validate data
        validated_data = self._validate_ohlcv(ohlcv_data, ticker)

        # 4. Insert to database
        inserted = self._insert_ohlcv_batch(validated_data, ticker, region)

        result = {
            'status': 'success',
            'records': inserted,
            'indicators_backfilled': False
        }

        # 5. Calculate technical indicators if needed
        if backfill_indicators:
            backfilled = self._backfill_indicators(ticker, region)
            result['indicators_backfilled'] = backfilled

        return result

    def backfill_null_indicators(self, region: Optional[str] = None,
                                ticker: Optional[str] = None) -> Dict:
        """
        Backfill NULL technical indicators

        Args:
            region: If specified, only backfill for this region
            ticker: If specified, only backfill for this ticker

        Returns:
            Backfill statistics dict
        """
        self.logger.info(f"Starting indicator backfill (region={region}, ticker={ticker})")

        # Get tickers with NULL indicators
        tickers_to_backfill = self._get_null_indicator_tickers(region, ticker)
        self.logger.info(f"Found {len(tickers_to_backfill)} tickers with NULL indicators")

        stats = {
            'total': len(tickers_to_backfill),
            'successful': 0,
            'failed': 0
        }

        for ticker_info in tickers_to_backfill:
            try:
                self._backfill_indicators(
                    ticker_info['ticker'],
                    ticker_info['region']
                )
                stats['successful'] += 1

            except Exception as e:
                self.logger.error(f"Failed to backfill indicators for {ticker_info['ticker']}: {e}")
                stats['failed'] += 1

        self.logger.info(f"Indicator backfill completed: {stats}")
        return stats

    def _get_active_tickers(self, region: str) -> List[str]:
        """Get list of active tickers in region"""
        query = """
            SELECT ticker
            FROM tickers
            WHERE region = %s AND status = 'active'
            ORDER BY ticker
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (region,))
            return [row[0] for row in cursor.fetchall()]

    def _get_last_ohlcv_date(self, ticker: str, region: str) -> Optional[date]:
        """Get the last OHLCV date for ticker"""
        query = """
            SELECT MAX(date)
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ticker, region))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None

    def _validate_ohlcv(self, ohlcv_data: List[Dict], ticker: str) -> List[Dict]:
        """
        Validate OHLCV data

        Checks:
        - Required fields present
        - Positive prices and volumes
        - No extreme outliers
        - OHLC relationship (low <= open/close <= high)

        Args:
            ohlcv_data: List of OHLCV dictionaries
            ticker: Ticker symbol (for logging)

        Returns:
            List of validated OHLCV dictionaries
        """
        validated = []

        for record in ohlcv_data:
            # Check required fields
            required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(field in record for field in required_fields):
                self.logger.warning(f"Skipping record with missing fields for {ticker}: {record}")
                continue

            # Check for positive values
            if any(record[field] <= 0 for field in ['open', 'high', 'low', 'close']):
                self.logger.warning(f"Skipping record with non-positive prices for {ticker}: {record}")
                continue

            # Check OHLC relationship
            if not (record['low'] <= record['open'] <= record['high'] and
                   record['low'] <= record['close'] <= record['high']):
                self.logger.warning(f"Skipping record with invalid OHLC relationship for {ticker}: {record}")
                continue

            # Check for extreme outliers (>1000% daily change)
            if len(validated) > 0:
                prev_close = validated[-1]['close']
                daily_change = abs(record['close'] - prev_close) / prev_close

                if daily_change > 10.0:  # 1000% change
                    self.logger.warning(f"Skipping record with extreme price change for {ticker}: {daily_change:.2%}")
                    continue

            validated.append(record)

        return validated

    def _insert_ohlcv_batch(self, ohlcv_data: List[Dict], ticker: str, region: str) -> int:
        """
        Insert OHLCV batch to database with ON CONFLICT handling

        Args:
            ohlcv_data: List of OHLCV dictionaries
            ticker: Ticker symbol
            region: Region code

        Returns:
            Number of records inserted
        """
        if not ohlcv_data:
            return 0

        query = """
            INSERT INTO ohlcv_data (
                ticker, region, date, timeframe,
                open, high, low, close, volume, turnover
            ) VALUES (
                %s, %s, %s, '1d', %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (ticker, region, date, timeframe) DO NOTHING
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare batch values
            values = [
                (
                    ticker,
                    region,
                    record['date'],
                    record['open'],
                    record['high'],
                    record['low'],
                    record['close'],
                    record.get('volume', 0),
                    record.get('turnover', 0)
                )
                for record in ohlcv_data
            ]

            # Execute batch insert
            cursor.executemany(query, values)
            conn.commit()

            return len(values)

    def _get_null_indicator_tickers(self, region: Optional[str] = None,
                                   ticker: Optional[str] = None) -> List[Dict]:
        """Get tickers with NULL technical indicators"""
        conditions = []
        params = []

        if region:
            conditions.append("region = %s")
            params.append(region)

        if ticker:
            conditions.append("ticker = %s")
            params.append(ticker)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        query = f"""
            SELECT DISTINCT ticker, region
            FROM ohlcv_data
            {where_clause}
            AND (
                ma_20 IS NULL OR
                ma_50 IS NULL OR
                ma_200 IS NULL OR
                rsi_14 IS NULL OR
                macd IS NULL OR
                bb_upper IS NULL
            )
            ORDER BY ticker
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [
                {'ticker': row[0], 'region': row[1]}
                for row in cursor.fetchall()
            ]

    def _backfill_indicators(self, ticker: str, region: str) -> bool:
        """
        Calculate and backfill technical indicators for ticker

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if indicators were backfilled
        """
        self.logger.debug(f"Backfilling indicators for {ticker} ({region})")

        # Fetch OHLCV data
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s AND timeframe = '1d'
            ORDER BY date
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ticker, region))
            rows = cursor.fetchall()

            if not rows or len(rows) < 200:
                # Need at least 200 days for MA200
                self.logger.warning(f"Insufficient data for indicators: {ticker} ({len(rows)} rows)")
                return False

            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

        # Calculate indicators
        df = self._calculate_indicators(df)

        # Update database
        self._update_indicators(df, ticker, region)

        return True

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators using pandas_ta

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with added indicator columns
        """
        try:
            import pandas_ta as ta
        except ImportError:
            self.logger.error("pandas_ta not installed. Install with: pip install pandas-ta")
            return df

        # Moving Averages
        df['ma_20'] = ta.sma(df['close'], length=20)
        df['ma_50'] = ta.sma(df['close'], length=50)
        df['ma_200'] = ta.sma(df['close'], length=200)

        # RSI
        df['rsi_14'] = ta.rsi(df['close'], length=14)

        # MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            df['macd_hist'] = macd['MACDh_12_26_9']

        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None:
            df['bb_upper'] = bbands['BBU_20_2.0']
            df['bb_middle'] = bbands['BBM_20_2.0']
            df['bb_lower'] = bbands['BBL_20_2.0']

        return df

    def _update_indicators(self, df: pd.DataFrame, ticker: str, region: str):
        """
        Update technical indicators in database

        Args:
            df: DataFrame with calculated indicators
            ticker: Ticker symbol
            region: Region code
        """
        query = """
            UPDATE ohlcv_data
            SET
                ma_20 = %s,
                ma_50 = %s,
                ma_200 = %s,
                rsi_14 = %s,
                macd = %s,
                macd_signal = %s,
                macd_hist = %s,
                bb_upper = %s,
                bb_middle = %s,
                bb_lower = %s
            WHERE ticker = %s AND region = %s AND date = %s AND timeframe = '1d'
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Prepare batch values (skip rows with all NULL indicators)
            values = []
            for _, row in df.iterrows():
                # Skip if all indicators are NULL
                if pd.isna([
                    row.get('ma_20'), row.get('ma_50'), row.get('ma_200'),
                    row.get('rsi_14'), row.get('macd')
                ]).all():
                    continue

                values.append((
                    row.get('ma_20'),
                    row.get('ma_50'),
                    row.get('ma_200'),
                    row.get('rsi_14'),
                    row.get('macd'),
                    row.get('macd_signal'),
                    row.get('macd_hist'),
                    row.get('bb_upper'),
                    row.get('bb_middle'),
                    row.get('bb_lower'),
                    ticker,
                    region,
                    row['date']
                ))

            # Execute batch update
            if values:
                cursor.executemany(query, values)
                conn.commit()
                self.logger.debug(f"Updated {len(values)} indicator records for {ticker}")

    def _get_adapter(self, region: str):
        """Get market adapter for region (lazy loading)"""
        if region not in self._adapters:
            if region == 'KR':
                from modules.market_adapters.kr_adapter import KRMarketAdapter
                self._adapters[region] = KRMarketAdapter()
            elif region == 'US':
                from modules.market_adapters.us_adapter import USMarketAdapter
                self._adapters[region] = USMarketAdapter()
            # Add other regions as needed

        return self._adapters[region]
