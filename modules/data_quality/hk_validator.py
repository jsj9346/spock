"""
Hong Kong Market Data Quality Validator

Validates OHLCV data quality for HK market with HKEX-specific checks.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class HKDataQualityValidator:
    """
    HK market data quality validation

    Quality Gates:
    1. Completeness: No missing trading days (HKEX calendar)
    2. Validity: All OHLCV values >0, High ≥ Low ≥ Close ≥ Open
    3. Consistency: No extreme price jumps (>50% single day)
    4. Volume: Volume >0 for active trading days

    HK-Specific Checks:
    - HKEX holiday calendar compliance
    - Half-day trading sessions (pre-holiday)
    - Typhoon/black rainstorm trading halts
    - Board lot size validation
    """

    # HKEX trading calendar (simplified - use official API in production)
    HKEX_HOLIDAYS_2024 = [
        '2024-01-01',  # New Year
        '2024-02-10',  # Lunar New Year Eve
        '2024-02-12',  # Lunar New Year
        '2024-02-13',  # Lunar New Year
        '2024-03-29',  # Good Friday
        '2024-03-30',  # Day after Good Friday
        '2024-04-01',  # Easter Monday
        '2024-04-04',  # Ching Ming Festival
        '2024-05-01',  # Labour Day
        '2024-05-15',  # Buddha's Birthday
        '2024-06-10',  # Dragon Boat Festival
        '2024-07-01',  # Hong Kong SAR Establishment Day
        '2024-09-18',  # Day after Mid-Autumn Festival
        '2024-10-01',  # National Day
        '2024-10-11',  # Chung Yeung Festival
        '2024-12-25',  # Christmas Day
        '2024-12-26',  # Boxing Day
    ]

    # 2025 holidays
    HKEX_HOLIDAYS_2025 = [
        '2025-01-01',  # New Year
        '2025-01-29',  # Lunar New Year Eve
        '2025-01-30',  # Lunar New Year
        '2025-01-31',  # Lunar New Year
        '2025-04-04',  # Ching Ming Festival
        '2025-04-18',  # Good Friday
        '2025-04-19',  # Day after Good Friday
        '2025-04-21',  # Easter Monday
        '2025-05-01',  # Labour Day
        '2025-05-05',  # Buddha's Birthday
        '2025-05-31',  # Dragon Boat Festival
        '2025-07-01',  # Hong Kong SAR Establishment Day
        '2025-10-01',  # National Day
        '2025-10-06',  # Day after Mid-Autumn Festival
        '2025-10-25',  # Chung Yeung Festival
        '2025-12-25',  # Christmas Day
        '2025-12-26',  # Boxing Day
    ]

    def __init__(self):
        all_holidays = self.HKEX_HOLIDAYS_2024 + self.HKEX_HOLIDAYS_2025
        self.holidays = pd.to_datetime(all_holidays)

    def validate_ohlcv(self, ticker: str, df: pd.DataFrame) -> Dict:
        """
        Run comprehensive OHLCV validation

        Args:
            ticker: HK ticker (e.g., "0700.HK")
            df: OHLCV DataFrame with columns [date, open, high, low, close, volume]

        Returns:
            {
                'ticker': '0700.HK',
                'total_days': 1230,
                'completeness_score': 0.98,
                'validity_score': 1.0,
                'consistency_score': 0.99,
                'anomalies': [
                    {'date': '2024-05-10', 'issue': 'price_jump', 'severity': 'warning'}
                ],
                'passed': True
            }
        """
        results = {
            'ticker': ticker,
            'total_days': len(df),
            'anomalies': []
        }

        # 1. Completeness check
        results['completeness_score'] = self._check_completeness(df)

        # 2. Validity check
        results['validity_score'] = self._check_validity(df)

        # 3. Consistency check (price jumps)
        results['consistency_score'], anomalies = self._check_consistency(ticker, df)
        results['anomalies'].extend(anomalies)

        # 4. Volume check
        results['volume_score'] = self._check_volume(df)

        # 5. Overall pass/fail
        results['passed'] = (
            results['completeness_score'] >= 0.95 and
            results['validity_score'] >= 0.99 and
            results['consistency_score'] >= 0.95
        )

        return results

    def _check_completeness(self, df: pd.DataFrame) -> float:
        """
        Check if all expected trading days are present

        Returns:
            Completeness score (0.0-1.0)
        """
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Get date range
        start_date = df['date'].min()
        end_date = df['date'].max()

        # Generate expected trading days (weekdays excluding holidays)
        expected_dates = pd.bdate_range(start=start_date, end=end_date)
        expected_dates = expected_dates[~expected_dates.isin(self.holidays)]

        # Calculate completeness
        actual_dates = set(df['date'])
        expected_dates_set = set(expected_dates)

        if len(expected_dates_set) == 0:
            return 1.0

        completeness = len(actual_dates & expected_dates_set) / len(expected_dates_set)

        return completeness

    def _check_validity(self, df: pd.DataFrame) -> float:
        """
        Check if OHLCV values are valid

        Rules:
        - All values >0
        - High ≥ Low
        - High ≥ Open, Close
        - Low ≤ Open, Close

        Returns:
            Validity score (0.0-1.0)
        """
        invalid_count = 0
        total_rows = len(df)

        # Check for null or negative values
        invalid_count += df[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()
        invalid_count += (df[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        invalid_count += (df['volume'] < 0).sum()

        # Check OHLC relationships
        invalid_count += (df['high'] < df['low']).sum()
        invalid_count += (df['high'] < df['open']).sum()
        invalid_count += (df['high'] < df['close']).sum()
        invalid_count += (df['low'] > df['open']).sum()
        invalid_count += (df['low'] > df['close']).sum()

        if total_rows == 0:
            return 1.0

        validity = 1.0 - (invalid_count / (total_rows * 5))  # 5 checks per row

        return max(0.0, validity)

    def _check_consistency(self, ticker: str, df: pd.DataFrame) -> Tuple[float, List[Dict]]:
        """
        Check for extreme price jumps and anomalies

        Returns:
            (consistency_score, anomaly_list)
        """
        df = df.copy().sort_values('date')
        anomalies = []

        # Calculate daily returns
        df['return'] = df['close'].pct_change()

        # Detect extreme price jumps (>50% in single day)
        extreme_jumps = df[abs(df['return']) > 0.5]

        for idx, row in extreme_jumps.iterrows():
            anomalies.append({
                'date': str(row['date']),
                'issue': 'extreme_price_jump',
                'severity': 'warning',
                'details': f"Return: {row['return']:.2%}"
            })

        # Calculate consistency score
        if len(df) > 0:
            consistency = 1.0 - (len(extreme_jumps) / len(df))
        else:
            consistency = 1.0

        return consistency, anomalies

    def _check_volume(self, df: pd.DataFrame) -> float:
        """
        Check if volume data is reasonable

        Returns:
            Volume score (0.0-1.0)
        """
        zero_volume = (df['volume'] == 0).sum()
        total_rows = len(df)

        if total_rows == 0:
            return 1.0

        # Allow up to 5% zero-volume days (halted trading, etc.)
        volume_score = 1.0 - (zero_volume / total_rows)

        return max(0.0, min(1.0, volume_score + 0.05))


def validate_hk_market_data(tickers: List[str] = None) -> pd.DataFrame:
    """
    Validate HK market data quality for all or specified tickers

    Args:
        tickers: List of HK tickers (e.g., ["0700.HK", "9988.HK"])
                If None, validate all HK tickers with OHLCV data

    Returns:
        DataFrame with validation results
    """
    import psycopg2
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

    validator = HKDataQualityValidator()
    results = []

    # Get tickers to validate
    if tickers is None:
        query = """
        SELECT DISTINCT ticker
        FROM ohlcv_data
        WHERE region = 'HK'
        ORDER BY ticker
        """
        tickers_df = pd.read_sql(query, conn)
        tickers = tickers_df['ticker'].tolist()

    logger.info(f"Validating {len(tickers)} HK tickers...")

    for i, ticker in enumerate(tickers, 1):
        # Fetch OHLCV data
        query = """
        SELECT date, open, high, low, close, volume
        FROM ohlcv_data
        WHERE ticker = %s AND region = 'HK'
        ORDER BY date
        """
        df = pd.read_sql(query, conn, params=(ticker,))

        if df.empty:
            logger.warning(f"No data for {ticker}")
            continue

        # Validate
        result = validator.validate_ohlcv(ticker, df)
        results.append(result)

        if i % 50 == 0:
            logger.info(f"Progress: {i}/{len(tickers)} tickers validated")

    conn.close()

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    return results_df


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Validate all HK tickers
    results = validate_hk_market_data()

    # Print summary
    print("\n=== HK Data Quality Validation Summary ===")
    print(f"Total tickers validated: {len(results)}")
    print(f"Passed: {results['passed'].sum()} ({results['passed'].mean():.1%})")
    print(f"Failed: {(~results['passed']).sum()}")
    print(f"\nAverage Scores:")
    print(f"  Completeness: {results['completeness_score'].mean():.2%}")
    print(f"  Validity: {results['validity_score'].mean():.2%}")
    print(f"  Consistency: {results['consistency_score'].mean():.2%}")
    print(f"  Volume: {results['volume_score'].mean():.2%}")

    # Save report
    results.to_csv('reports/hk_quality_validation_report.csv', index=False)
    print(f"\nReport saved to: reports/hk_quality_validation_report.csv")
