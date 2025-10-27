#!/usr/bin/env python3
"""
Data Quality Checks for PostgreSQL

Performs ongoing data quality monitoring for the Quant Investment Platform.

Checks:
- Statistical outlier detection
- Time-series continuity (missing dates)
- Duplicate detection
- Data freshness monitoring
- Price anomaly detection
- Volume anomaly detection

Usage:
    python3 scripts/data_quality_checks.py --daily
    python3 scripts/data_quality_checks.py --ticker 005930 --region KR
    python3 scripts/data_quality_checks.py --comprehensive
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal
import statistics

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from modules.db_manager_postgres import PostgresDatabaseManager


class DataQualityChecker:
    """
    Performs data quality checks on PostgreSQL database.

    Monitors:
    - Data completeness
    - Statistical anomalies
    - Time-series continuity
    - Data freshness
    """

    def __init__(self, postgres_manager: PostgresDatabaseManager):
        """
        Initialize data quality checker.

        Args:
            postgres_manager: PostgreSQL database manager
        """
        self.db = postgres_manager

        # Quality issue tracking
        self.issues = {
            'critical': [],  # Data integrity issues
            'warning': [],   # Potential problems
            'info': []       # Informational notices
        }

    def check_missing_dates(self,
                           ticker: Optional[str] = None,
                           region: Optional[str] = None,
                           start_date: Optional[date] = None,
                           end_date: Optional[date] = None) -> List[Dict]:
        """
        Detect missing trading days in OHLCV data.

        Args:
            ticker: Specific ticker to check (optional)
            region: Specific region to check (optional)
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of gaps found
        """
        logger.info("Checking for missing dates in OHLCV data...")

        try:
            where_clauses = []
            if ticker:
                where_clauses.append(f"ticker = '{ticker}'")
            if region:
                where_clauses.append(f"region = '{region}'")
            if start_date:
                where_clauses.append(f"date >= '{start_date}'")
            if end_date:
                where_clauses.append(f"date <= '{end_date}'")

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Find gaps in dates (>3 days between consecutive records)
            query = f"""
                WITH date_gaps AS (
                    SELECT
                        ticker,
                        region,
                        date AS current_date,
                        LAG(date) OVER (PARTITION BY ticker, region ORDER BY date) AS prev_date,
                        date - LAG(date) OVER (PARTITION BY ticker, region ORDER BY date) AS gap_days
                    FROM ohlcv_data
                    {where_sql}
                )
                SELECT ticker, region, prev_date, current_date, gap_days
                FROM date_gaps
                WHERE gap_days > 3
                ORDER BY ticker, region, current_date
                LIMIT 100
            """

            gaps = self.db.execute_query(query)

            if gaps:
                for gap in gaps:
                    self.issues['warning'].append(
                        f"Gap: {gap['ticker']} ({gap['region']}) - "
                        f"{gap['prev_date']} to {gap['current_date']} "
                        f"({gap['gap_days']} days)"
                    )
                    logger.warning(
                        f"⚠️  Gap detected: {gap['ticker']} ({gap['region']}) - "
                        f"{gap['prev_date']} to {gap['current_date']} ({gap['gap_days']} days)"
                    )

                logger.info(f"Found {len(gaps)} date gaps")
            else:
                logger.info("✅ No significant date gaps found")

            return gaps

        except Exception as e:
            self.issues['critical'].append(f"Error checking missing dates: {e}")
            logger.error(f"❌ Error checking missing dates: {e}")
            return []

    def check_duplicate_records(self) -> List[Dict]:
        """
        Detect duplicate OHLCV records.

        Returns:
            List of duplicate records
        """
        logger.info("Checking for duplicate OHLCV records...")

        try:
            query = """
                SELECT ticker, region, date, timeframe, COUNT(*) as count
                FROM ohlcv_data
                GROUP BY ticker, region, date, timeframe
                HAVING COUNT(*) > 1
                ORDER BY count DESC, ticker, region, date
                LIMIT 100
            """

            duplicates = self.db.execute_query(query)

            if duplicates:
                for dup in duplicates:
                    self.issues['critical'].append(
                        f"Duplicate: {dup['ticker']} ({dup['region']}) - "
                        f"{dup['date']} ({dup['count']} records)"
                    )
                    logger.error(
                        f"❌ Duplicate: {dup['ticker']} ({dup['region']}) - "
                        f"{dup['date']} ({dup['count']} records)"
                    )

                logger.error(f"Found {len(duplicates)} duplicate records")
            else:
                logger.info("✅ No duplicate records found")

            return duplicates

        except Exception as e:
            self.issues['critical'].append(f"Error checking duplicates: {e}")
            logger.error(f"❌ Error checking duplicates: {e}")
            return []

    def check_price_anomalies(self,
                             ticker: Optional[str] = None,
                             threshold: float = 3.0) -> List[Dict]:
        """
        Detect price anomalies using statistical methods.

        Uses Z-score to identify outliers (default: >3 standard deviations).

        Args:
            ticker: Specific ticker to check (optional)
            threshold: Z-score threshold (default: 3.0)

        Returns:
            List of anomalies detected
        """
        logger.info(f"Checking for price anomalies (threshold: {threshold} std dev)...")

        try:
            where_clause = f"WHERE ticker = '{ticker}'" if ticker else ""

            # Calculate daily returns and detect outliers
            query = f"""
                WITH daily_returns AS (
                    SELECT
                        ticker,
                        region,
                        date,
                        close,
                        LAG(close) OVER (PARTITION BY ticker, region ORDER BY date) AS prev_close,
                        CASE
                            WHEN LAG(close) OVER (PARTITION BY ticker, region ORDER BY date) > 0
                            THEN (close - LAG(close) OVER (PARTITION BY ticker, region ORDER BY date)) /
                                 LAG(close) OVER (PARTITION BY ticker, region ORDER BY date)
                            ELSE NULL
                        END AS daily_return
                    FROM ohlcv_data
                    {where_clause}
                ),
                return_stats AS (
                    SELECT
                        ticker,
                        region,
                        AVG(daily_return) AS mean_return,
                        STDDEV(daily_return) AS std_return
                    FROM daily_returns
                    WHERE daily_return IS NOT NULL
                    GROUP BY ticker, region
                )
                SELECT
                    dr.ticker,
                    dr.region,
                    dr.date,
                    dr.close,
                    dr.prev_close,
                    dr.daily_return,
                    rs.mean_return,
                    rs.std_return,
                    ABS((dr.daily_return - rs.mean_return) / NULLIF(rs.std_return, 0)) AS z_score
                FROM daily_returns dr
                JOIN return_stats rs ON dr.ticker = rs.ticker AND dr.region = rs.region
                WHERE dr.daily_return IS NOT NULL
                  AND rs.std_return > 0
                  AND ABS((dr.daily_return - rs.mean_return) / rs.std_return) > {threshold}
                ORDER BY z_score DESC
                LIMIT 100
            """

            anomalies = self.db.execute_query(query)

            if anomalies:
                for anomaly in anomalies:
                    return_pct = anomaly['daily_return'] * 100
                    z_score = anomaly['z_score']

                    self.issues['warning'].append(
                        f"Price anomaly: {anomaly['ticker']} ({anomaly['region']}) - "
                        f"{anomaly['date']}: {return_pct:+.2f}% "
                        f"(Z-score: {z_score:.2f})"
                    )
                    logger.warning(
                        f"⚠️  Price anomaly: {anomaly['ticker']} ({anomaly['region']}) - "
                        f"{anomaly['date']}: {return_pct:+.2f}% (Z-score: {z_score:.2f})"
                    )

                logger.info(f"Found {len(anomalies)} price anomalies")
            else:
                logger.info("✅ No significant price anomalies found")

            return anomalies

        except Exception as e:
            self.issues['critical'].append(f"Error checking price anomalies: {e}")
            logger.error(f"❌ Error checking price anomalies: {e}")
            return []

    def check_volume_anomalies(self,
                              ticker: Optional[str] = None,
                              threshold: float = 3.0) -> List[Dict]:
        """
        Detect volume anomalies using statistical methods.

        Args:
            ticker: Specific ticker to check (optional)
            threshold: Z-score threshold (default: 3.0)

        Returns:
            List of volume anomalies
        """
        logger.info(f"Checking for volume anomalies (threshold: {threshold} std dev)...")

        try:
            where_clause = f"WHERE ticker = '{ticker}'" if ticker else ""

            # Calculate volume statistics and detect outliers
            query = f"""
                WITH volume_stats AS (
                    SELECT
                        ticker,
                        region,
                        AVG(volume) AS mean_volume,
                        STDDEV(volume) AS std_volume
                    FROM ohlcv_data
                    {where_clause}
                    WHERE volume > 0
                    GROUP BY ticker, region
                )
                SELECT
                    o.ticker,
                    o.region,
                    o.date,
                    o.volume,
                    vs.mean_volume,
                    vs.std_volume,
                    ABS((o.volume - vs.mean_volume) / NULLIF(vs.std_volume, 0)) AS z_score
                FROM ohlcv_data o
                JOIN volume_stats vs ON o.ticker = vs.ticker AND o.region = vs.region
                WHERE vs.std_volume > 0
                  AND ABS((o.volume - vs.mean_volume) / vs.std_volume) > {threshold}
                ORDER BY z_score DESC
                LIMIT 100
            """

            anomalies = self.db.execute_query(query)

            if anomalies:
                for anomaly in anomalies:
                    z_score = anomaly['z_score']
                    volume_ratio = anomaly['volume'] / anomaly['mean_volume'] if anomaly['mean_volume'] > 0 else 0

                    self.issues['info'].append(
                        f"Volume anomaly: {anomaly['ticker']} ({anomaly['region']}) - "
                        f"{anomaly['date']}: {anomaly['volume']:,} "
                        f"({volume_ratio:.1f}x avg, Z-score: {z_score:.2f})"
                    )
                    logger.info(
                        f"ℹ️  Volume anomaly: {anomaly['ticker']} ({anomaly['region']}) - "
                        f"{anomaly['date']}: {anomaly['volume']:,} "
                        f"({volume_ratio:.1f}x avg, Z-score: {z_score:.2f})"
                    )

                logger.info(f"Found {len(anomalies)} volume anomalies")
            else:
                logger.info("✅ No significant volume anomalies found")

            return anomalies

        except Exception as e:
            self.issues['critical'].append(f"Error checking volume anomalies: {e}")
            logger.error(f"❌ Error checking volume anomalies: {e}")
            return []

    def check_data_freshness(self, max_age_days: int = 7) -> Dict[str, Any]:
        """
        Check data freshness (last update time).

        Args:
            max_age_days: Maximum acceptable age in days

        Returns:
            Dictionary with freshness statistics
        """
        logger.info(f"Checking data freshness (max age: {max_age_days} days)...")

        try:
            query = """
                SELECT
                    region,
                    MAX(date) AS latest_date,
                    COUNT(DISTINCT ticker) AS ticker_count,
                    NOW()::date - MAX(date) AS age_days
                FROM ohlcv_data
                GROUP BY region
                ORDER BY region
            """

            freshness = self.db.execute_query(query)

            for region_data in freshness:
                region = region_data['region']
                latest_date = region_data['latest_date']
                age_days = region_data['age_days']
                ticker_count = region_data['ticker_count']

                if age_days > max_age_days:
                    self.issues['warning'].append(
                        f"Stale data: {region} - Latest: {latest_date} "
                        f"({age_days} days old, {ticker_count} tickers)"
                    )
                    logger.warning(
                        f"⚠️  Stale data: {region} - Latest: {latest_date} "
                        f"({age_days} days old)"
                    )
                else:
                    logger.info(
                        f"✅ {region}: {latest_date} ({age_days} days old, {ticker_count} tickers)"
                    )

            return freshness

        except Exception as e:
            self.issues['critical'].append(f"Error checking data freshness: {e}")
            logger.error(f"❌ Error checking data freshness: {e}")
            return {}

    def check_zero_volume_days(self, min_consecutive: int = 5) -> List[Dict]:
        """
        Detect consecutive zero-volume days.

        Args:
            min_consecutive: Minimum consecutive days to flag

        Returns:
            List of zero-volume streaks
        """
        logger.info(f"Checking for zero-volume streaks ({min_consecutive}+ days)...")

        try:
            query = f"""
                WITH zero_volume AS (
                    SELECT
                        ticker,
                        region,
                        date,
                        volume,
                        CASE WHEN volume = 0 THEN 1 ELSE 0 END AS is_zero,
                        SUM(CASE WHEN volume = 0 THEN 1 ELSE 0 END)
                            OVER (PARTITION BY ticker, region
                                  ORDER BY date
                                  ROWS BETWEEN {min_consecutive - 1} PRECEDING AND CURRENT ROW) AS zero_count
                    FROM ohlcv_data
                )
                SELECT DISTINCT ticker, region, date
                FROM zero_volume
                WHERE zero_count >= {min_consecutive}
                ORDER BY ticker, region, date DESC
                LIMIT 100
            """

            streaks = self.db.execute_query(query)

            if streaks:
                for streak in streaks:
                    self.issues['info'].append(
                        f"Zero volume streak: {streak['ticker']} ({streak['region']}) - "
                        f"ending {streak['date']}"
                    )
                    logger.info(
                        f"ℹ️  Zero volume streak: {streak['ticker']} ({streak['region']}) - "
                        f"ending {streak['date']}"
                    )

                logger.info(f"Found {len(streaks)} zero-volume streaks")
            else:
                logger.info("✅ No prolonged zero-volume periods found")

            return streaks

        except Exception as e:
            self.issues['critical'].append(f"Error checking zero-volume days: {e}")
            logger.error(f"❌ Error checking zero-volume days: {e}")
            return []

    def check_price_consistency(self) -> List[Dict]:
        """
        Check price consistency (high >= low, close in range).

        Returns:
            List of inconsistent records
        """
        logger.info("Checking price consistency...")

        try:
            query = """
                SELECT ticker, region, date, open, high, low, close
                FROM ohlcv_data
                WHERE high < low
                   OR close < low
                   OR close > high
                   OR open < low
                   OR open > high
                LIMIT 100
            """

            inconsistent = self.db.execute_query(query)

            if inconsistent:
                for rec in inconsistent:
                    self.issues['critical'].append(
                        f"Price inconsistency: {rec['ticker']} ({rec['region']}) - "
                        f"{rec['date']}: O={rec['open']}, H={rec['high']}, "
                        f"L={rec['low']}, C={rec['close']}"
                    )
                    logger.error(
                        f"❌ Price inconsistency: {rec['ticker']} ({rec['region']}) - "
                        f"{rec['date']}"
                    )

                logger.error(f"Found {len(inconsistent)} price inconsistencies")
            else:
                logger.info("✅ All prices are consistent")

            return inconsistent

        except Exception as e:
            self.issues['critical'].append(f"Error checking price consistency: {e}")
            logger.error(f"❌ Error checking price consistency: {e}")
            return []

    def print_summary(self):
        """Print data quality summary."""
        logger.info("=" * 70)
        logger.info("DATA QUALITY SUMMARY")
        logger.info("=" * 70)

        total_issues = (
            len(self.issues['critical']) +
            len(self.issues['warning']) +
            len(self.issues['info'])
        )

        logger.info(f"\nTotal Issues Found: {total_issues}")

        if self.issues['critical']:
            logger.info(f"\n🚨 CRITICAL ({len(self.issues['critical'])} issues):")
            for issue in self.issues['critical']:
                logger.error(f"  ❌ {issue}")

        if self.issues['warning']:
            logger.info(f"\n⚠️  WARNINGS ({len(self.issues['warning'])} issues):")
            for issue in self.issues['warning'][:20]:  # Limit to 20
                logger.warning(f"  ⚠️  {issue}")
            if len(self.issues['warning']) > 20:
                logger.warning(f"  ... and {len(self.issues['warning']) - 20} more")

        if self.issues['info']:
            logger.info(f"\nℹ️  INFO ({len(self.issues['info'])} notices):")
            for issue in self.issues['info'][:10]:  # Limit to 10
                logger.info(f"  ℹ️  {issue}")
            if len(self.issues['info']) > 10:
                logger.info(f"  ... and {len(self.issues['info']) - 10} more")

        logger.info("=" * 70)

        # Overall assessment
        if not self.issues['critical']:
            if not self.issues['warning']:
                logger.info("✅ DATA QUALITY: EXCELLENT")
            else:
                logger.info("⚠️  DATA QUALITY: GOOD (warnings present)")
        else:
            logger.error("❌ DATA QUALITY: POOR (critical issues found)")


def main():
    """Main data quality check workflow."""
    parser = argparse.ArgumentParser(description="Check PostgreSQL data quality")
    parser.add_argument(
        '--daily',
        action='store_true',
        help='Run daily quality checks'
    )
    parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='Run comprehensive quality checks'
    )
    parser.add_argument(
        '--ticker',
        help='Check specific ticker'
    )
    parser.add_argument(
        '--region',
        help='Check specific region'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=3.0,
        help='Z-score threshold for anomaly detection (default: 3.0)'
    )

    args = parser.parse_args()

    # Setup logging
    log_file = f"logs/{datetime.now().strftime('%Y%m%d')}_quality_checks.log"
    logger.add(log_file, rotation="100 MB")

    logger.info("=" * 70)
    logger.info("PostgreSQL Data Quality Checks")
    logger.info("=" * 70)

    # Initialize PostgreSQL
    try:
        postgres_db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    # Create quality checker
    checker = DataQualityChecker(postgres_db)

    # Run checks based on mode
    if args.daily:
        # Daily checks (lightweight)
        checker.check_data_freshness(max_age_days=7)
        checker.check_duplicate_records()
        checker.check_price_consistency()

    elif args.comprehensive:
        # Comprehensive checks (all checks)
        checker.check_missing_dates(ticker=args.ticker, region=args.region)
        checker.check_duplicate_records()
        checker.check_price_consistency()
        checker.check_price_anomalies(ticker=args.ticker, threshold=args.threshold)
        checker.check_volume_anomalies(ticker=args.ticker, threshold=args.threshold)
        checker.check_zero_volume_days(min_consecutive=5)
        checker.check_data_freshness(max_age_days=7)

    else:
        # Standard checks
        checker.check_missing_dates(ticker=args.ticker, region=args.region)
        checker.check_duplicate_records()
        checker.check_price_consistency()
        checker.check_data_freshness(max_age_days=7)

    # Print summary
    checker.print_summary()

    # Return exit code
    if checker.issues['critical']:
        return 1
    else:
        return 0


if __name__ == '__main__':
    sys.exit(main())
