#!/usr/bin/env python3
"""
Week 4: Automated Price Anomaly Detection

Purpose: Daily data quality monitoring for OHLCV data

Detects:
- Orphaned tickers (OHLCV without ticker registry)
- OHLC violations (high < low, invalid relationships)
- Extreme daily ranges (asset-type aware)
- Zero-volume anomalies with price changes

Usage:
    # Daily run (last 30 days)
    python3 scripts/detect_price_anomalies.py

    # Historical scan (all data)
    python3 scripts/detect_price_anomalies.py --historical

    # Specific date range
    python3 scripts/detect_price_anomalies.py --start 2024-01-01 --end 2024-12-31

Author: Spock Quant Platform - Week 4
Date: 2025-10-27
"""

import sys
import os
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_anomaly_detection.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Single anomaly detection result."""
    anomaly_type: str
    ticker: str
    date: date
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    details: str


class PriceAnomalyDetector:
    """Automated price anomaly detection system."""

    def __init__(self, db: PostgresDatabaseManager):
        """
        Initialize detector.

        Args:
            db: PostgreSQL database manager
        """
        self.db = db
        self.anomalies: List[AnomalyResult] = []

    def detect_orphaned_tickers(self, start_date: date = None, end_date: date = None):
        """
        Detect OHLCV data without ticker registry entries.

        Args:
            start_date: Start date for detection (None = all history)
            end_date: End date for detection (None = today)
        """
        logger.info("🔍 Detecting orphaned tickers...")

        if start_date and end_date:
            date_filter = "AND o.date BETWEEN %s AND %s"
            params = (start_date, end_date)
        else:
            date_filter = ""
            params = None

        query = f"""
        SELECT
            o.ticker,
            o.region,
            COUNT(*) as record_count,
            MIN(o.date) as earliest_date,
            MAX(o.date) as latest_date
        FROM ohlcv_data o
        LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
        WHERE t.ticker IS NULL
          {date_filter}
        GROUP BY o.ticker, o.region
        ORDER BY record_count DESC;
        """

        results = self.db.execute_query(query, params) if params else self.db.execute_query(query)

        for row in results:
            self.anomalies.append(AnomalyResult(
                anomaly_type="ORPHANED_TICKER",
                ticker=row['ticker'],
                date=row['latest_date'],
                severity="HIGH",
                details=f"Ticker not in registry | {row['record_count']} records | "
                        f"{row['earliest_date']} to {row['latest_date']}"
            ))

        logger.info(f"  Found {len(results)} orphaned tickers")

    def detect_ohlc_violations(self, start_date: date = None, end_date: date = None):
        """
        Detect invalid OHLC relationships.

        Args:
            start_date: Start date for detection
            end_date: End date for detection
        """
        logger.info("🔍 Detecting OHLC violations...")

        if start_date and end_date:
            date_filter = "AND date BETWEEN %s AND %s"
            params = (start_date, end_date)
        else:
            date_filter = ""
            params = None

        query = f"""
        SELECT
            ticker,
            date,
            open,
            high,
            low,
            close,
            volume,
            CASE
                WHEN high < low THEN 'HIGH_BELOW_LOW'
                WHEN high < close THEN 'HIGH_BELOW_CLOSE'
                WHEN high < open THEN 'HIGH_BELOW_OPEN'
                WHEN low > close THEN 'LOW_ABOVE_CLOSE'
                WHEN low > open THEN 'LOW_ABOVE_OPEN'
                WHEN close <= 0 THEN 'INVALID_CLOSE'
                WHEN open <= 0 THEN 'INVALID_OPEN'
                ELSE 'OTHER'
            END as violation_type
        FROM ohlcv_data
        WHERE region = 'KR'
          {date_filter}
          AND (
            high < low
            OR high < close
            OR high < open
            OR low > close
            OR low > open
            OR close <= 0
            OR open <= 0
          )
        ORDER BY date DESC, ticker;
        """

        results = self.db.execute_query(query, params) if params else self.db.execute_query(query)

        for row in results:
            self.anomalies.append(AnomalyResult(
                anomaly_type="OHLC_VIOLATION",
                ticker=row['ticker'],
                date=row['date'],
                severity="CRITICAL",
                details=f"{row['violation_type']} | O={row['open']:.2f} H={row['high']:.2f} "
                        f"L={row['low']:.2f} C={row['close']:.2f}"
            ))

        logger.info(f"  Found {len(results)} OHLC violations")

    def detect_extreme_ranges(self, start_date: date = None, end_date: date = None):
        """
        Detect extreme daily price ranges (asset-type aware).

        Args:
            start_date: Start date for detection
            end_date: End date for detection
        """
        logger.info("🔍 Detecting extreme daily ranges...")

        if start_date and end_date:
            date_filter = "AND o.date BETWEEN %s AND %s"
            params = (start_date, end_date)
        else:
            date_filter = ""
            params = None

        query = f"""
        SELECT
            o.ticker,
            o.date,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            (o.high - o.low) as absolute_range,
            (o.high - o.low) / NULLIF(o.close, 0) * 100 as range_pct,
            COALESCE(t.asset_type, 'UNKNOWN') as asset_type,
            CASE
                WHEN COALESCE(t.asset_type, 'STOCK') = 'STOCK' AND (o.high - o.low) / NULLIF(o.close, 0) > 0.30 THEN 'HIGH'
                WHEN t.asset_type = 'ETF' AND (o.high - o.low) > 500 THEN 'HIGH'
                ELSE 'NORMAL'
            END as anomaly_severity
        FROM ohlcv_data o
        LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
        WHERE o.region = 'KR'
          {date_filter}
          AND (
            -- Stock: >30%% daily range (double %% for psycopg2 escaping)
            (COALESCE(t.asset_type, 'STOCK') = 'STOCK' AND (o.high - o.low) / NULLIF(o.close, 0) > 0.30)
            OR
            -- ETF: >500 absolute range
            (t.asset_type = 'ETF' AND (o.high - o.low) > 500)
          )
        ORDER BY o.date DESC, range_pct DESC;
        """

        results = self.db.execute_query(query, params) if params else self.db.execute_query(query)

        for row in results:
            self.anomalies.append(AnomalyResult(
                anomaly_type="EXTREME_RANGE",
                ticker=row['ticker'],
                date=row['date'],
                severity=row['anomaly_severity'],
                details=f"{row['asset_type']} | Range: {row['range_pct']:.2f}% "
                        f"(₩{row['absolute_range']:,.2f}) | Vol: {row['volume']:,}"
            ))

        logger.info(f"  Found {len(results)} extreme range anomalies")

    def detect_zero_volume_anomalies(self, start_date: date = None, end_date: date = None):
        """
        Detect zero-volume trading days with price changes.

        Args:
            start_date: Start date for detection
            end_date: End date for detection
        """
        logger.info("🔍 Detecting zero-volume anomalies...")

        if start_date and end_date:
            date_filter = "WHERE date BETWEEN %s AND %s"
            params = (start_date, end_date)
        else:
            date_filter = ""
            params = None

        query = f"""
        WITH price_changes AS (
            SELECT
                ticker,
                date,
                open,
                close,
                volume,
                LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close,
                (close - LAG(close) OVER (PARTITION BY ticker ORDER BY date)) /
                    NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY date), 0) * 100 as price_change_pct
            FROM ohlcv_data
            {date_filter}
        )
        SELECT *
        FROM price_changes
        WHERE volume = 0
          AND ABS(price_change_pct) > 0.1  -- >0.1%% change on zero volume (double %% for psycopg2 escaping)
          AND prev_close IS NOT NULL
        ORDER BY date DESC, ABS(price_change_pct) DESC;
        """

        results = self.db.execute_query(query, params) if params else self.db.execute_query(query)

        for row in results:
            self.anomalies.append(AnomalyResult(
                anomaly_type="ZERO_VOLUME_ANOMALY",
                ticker=row['ticker'],
                date=row['date'],
                severity="MEDIUM",
                details=f"Price change: {row['price_change_pct']:.2f}% on zero volume | "
                        f"{row['prev_close']:.2f} → {row['close']:.2f}"
            ))

        logger.info(f"  Found {len(results)} zero-volume anomalies")

    def run_all_checks(self, start_date: date = None, end_date: date = None):
        """
        Run all anomaly detection checks.

        Args:
            start_date: Start date for detection (None = 30 days ago)
            end_date: End date for detection (None = today)
        """
        # Default to last 30 days
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        logger.info("=" * 80)
        logger.info("PRICE ANOMALY DETECTION - Week 4")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date} to {end_date}")
        logger.info("")

        # Run all checks
        self.detect_orphaned_tickers(start_date, end_date)
        self.detect_ohlc_violations(start_date, end_date)
        self.detect_extreme_ranges(start_date, end_date)
        self.detect_zero_volume_anomalies(start_date, end_date)

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print anomaly detection summary."""
        logger.info("\n" + "=" * 80)
        logger.info("ANOMALY DETECTION SUMMARY")
        logger.info("=" * 80)

        # Group by type
        by_type = {}
        by_severity = {}

        for anomaly in self.anomalies:
            by_type[anomaly.anomaly_type] = by_type.get(anomaly.anomaly_type, 0) + 1
            by_severity[anomaly.severity] = by_severity.get(anomaly.severity, 0) + 1

        logger.info(f"Total Anomalies: {len(self.anomalies)}")
        logger.info("")

        # By type
        logger.info("By Type:")
        for atype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {atype:25} {count:>6,}")

        logger.info("")

        # By severity
        logger.info("By Severity:")
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        for severity in severity_order:
            if severity in by_severity:
                logger.info(f"  {severity:25} {by_severity[severity]:>6,}")

        # Top 10 anomalies
        if self.anomalies:
            logger.info("\nTop 10 Anomalies:")
            severity_rank = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            sorted_anomalies = sorted(
                self.anomalies,
                key=lambda x: (severity_rank.get(x.severity, 0), x.date),
                reverse=True
            )

            for i, anomaly in enumerate(sorted_anomalies[:10], 1):
                logger.info(f"  {i}. [{anomaly.severity}] {anomaly.ticker} | "
                           f"{anomaly.date} | {anomaly.anomaly_type}")
                logger.info(f"     {anomaly.details}")

        logger.info("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Detect price anomalies in OHLCV data')
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--historical', action='store_true', help='Scan all historical data')

    args = parser.parse_args()

    # Parse dates
    start_date = None
    end_date = None

    if args.historical:
        # No date filters - scan all data
        pass
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    else:
        # Default: last 30 days
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

    # Initialize database
    try:
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return 1

    # Run anomaly detection
    try:
        detector = PriceAnomalyDetector(db)
        detector.run_all_checks(start_date, end_date)

        # Return non-zero exit code if anomalies found (for alerting)
        if detector.anomalies:
            logger.warning(f"\n⚠️  {len(detector.anomalies)} anomalies detected")
            return 1
        else:
            logger.info("\n✅ No anomalies detected")
            return 0

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Detection interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Detection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
