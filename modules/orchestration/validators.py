"""
Data Quality Validators for Database Update Pipeline

Provides post-execution data quality validation to ensure pipeline success.

Author: Quant Investment Platform
Date: 2025-11-01
"""

from typing import Dict, List, Optional
import logging
from modules.db_manager_postgres import PostgresDatabaseManager

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """
    Data quality validator for pipeline output

    Validates:
    - Ticker coverage (expected vs actual)
    - OHLCV data completeness
    - Fundamental data coverage
    - Price anomalies

    Usage:
        validator = DataQualityValidator(db)
        results = validator.validate_pipeline_output(['KR', 'US'])
        if all(r['passed'] for r in results.values()):
            print("✅ All validations passed")
    """

    # Validation thresholds
    OHLCV_COVERAGE_THRESHOLD = 0.80  # 80% of tickers should have OHLCV data
    FUNDAMENTAL_COVERAGE_THRESHOLD = 0.70  # 70% of tickers should have fundamentals
    PRICE_CHANGE_THRESHOLD = 0.20  # 20% daily price change is anomaly

    def __init__(self, db: PostgresDatabaseManager):
        """
        Initialize validator

        Args:
            db: PostgreSQL database manager
        """
        self.db = db
        logger.info("DataQualityValidator initialized")

    def validate_pipeline_output(self, regions: List[str]) -> Dict[str, Dict]:
        """
        Validate pipeline output for all regions

        Args:
            regions: List of region codes to validate

        Returns:
            Dictionary mapping region to validation results:
            {
                'KR': {
                    'ticker_count': 2543,
                    'ohlcv_coverage': 0.98,
                    'fundamental_coverage': 0.85,
                    'anomalies': 3,
                    'passed': True
                },
                ...
            }
        """
        logger.info(f"🔍 Validating data quality for regions: {regions}")

        validation_results = {}

        for region in regions:
            validation_results[region] = self._validate_region(region)

        # Summary
        passed_count = sum(1 for r in validation_results.values() if r['passed'])
        total_count = len(validation_results)

        logger.info(
            f"✅ Validation complete: {passed_count}/{total_count} regions passed"
        )

        return validation_results

    def _validate_region(self, region: str) -> Dict:
        """
        Validate data quality for a single region

        Args:
            region: Region code (e.g., 'KR', 'US')

        Returns:
            Validation result dictionary
        """
        logger.info(f"  Validating region: {region}")

        result = {
            'ticker_count': 0,
            'ohlcv_coverage': 0.0,
            'fundamental_coverage': 0.0,
            'anomalies': 0,
            'passed': False,
            'errors': []
        }

        try:
            # Check 1: Ticker count
            result['ticker_count'] = self._count_tickers(region)

            if result['ticker_count'] == 0:
                result['errors'].append(f"No tickers found for region {region}")
                return result

            # Check 2: OHLCV coverage
            result['ohlcv_coverage'] = self._check_ohlcv_coverage(region)

            if result['ohlcv_coverage'] < self.OHLCV_COVERAGE_THRESHOLD:
                result['errors'].append(
                    f"OHLCV coverage {result['ohlcv_coverage']:.1%} "
                    f"< threshold {self.OHLCV_COVERAGE_THRESHOLD:.1%}"
                )

            # Check 3: Fundamental coverage (KR only)
            if region == 'KR':
                result['fundamental_coverage'] = self._check_fundamental_coverage(region)

                if result['fundamental_coverage'] < self.FUNDAMENTAL_COVERAGE_THRESHOLD:
                    result['errors'].append(
                        f"Fundamental coverage {result['fundamental_coverage']:.1%} "
                        f"< threshold {self.FUNDAMENTAL_COVERAGE_THRESHOLD:.1%}"
                    )

            # Check 4: Price anomalies
            result['anomalies'] = self._detect_price_anomalies(region)

            if result['anomalies'] > 10:
                result['errors'].append(
                    f"{result['anomalies']} price anomalies detected (threshold: 10)"
                )

            # Overall pass/fail
            result['passed'] = len(result['errors']) == 0

            # Log result
            status = "✅" if result['passed'] else "⚠️"
            logger.info(
                f"  {status} [{region}] {result['ticker_count']} tickers, "
                f"OHLCV: {result['ohlcv_coverage']:.1%}, "
                f"Anomalies: {result['anomalies']}"
            )

        except Exception as e:
            logger.error(f"  ❌ [{region}] Validation failed: {e}")
            result['errors'].append(str(e))
            result['passed'] = False

        return result

    def _count_tickers(self, region: str) -> int:
        """Count total tickers for region"""
        query = "SELECT COUNT(*) as cnt FROM tickers WHERE region = %s"
        result = self.db.execute_query(query, (region,))
        return result[0]['cnt'] if result else 0

    def _check_ohlcv_coverage(self, region: str, lookback_days: int = 30) -> float:
        """
        Check OHLCV data coverage (last N days)

        Args:
            region: Region code
            lookback_days: Number of days to check

        Returns:
            Coverage ratio (0.0 to 1.0)
        """
        # Total tickers
        total_tickers = self._count_tickers(region)

        if total_tickers == 0:
            return 0.0

        # Tickers with OHLCV data in last N days
        query = """
        SELECT COUNT(DISTINCT ticker) as cnt
        FROM ohlcv_data
        WHERE region = %s
          AND date >= NOW() - INTERVAL '%s days'
        """

        result = self.db.execute_query(query, (region, lookback_days))
        ohlcv_tickers = result[0]['cnt'] if result else 0

        return ohlcv_tickers / total_tickers

    def _check_fundamental_coverage(self, region: str) -> float:
        """
        Check fundamental data coverage

        Args:
            region: Region code

        Returns:
            Coverage ratio (0.0 to 1.0)
        """
        # Total tickers (excluding ETFs)
        query_total = """
        SELECT COUNT(*) as cnt
        FROM tickers
        WHERE region = %s AND is_etf = FALSE
        """
        result = self.db.execute_query(query_total, (region,))
        total_tickers = result[0]['cnt'] if result else 0

        if total_tickers == 0:
            return 0.0

        # Tickers with fundamental data
        query_fundamental = """
        SELECT COUNT(DISTINCT ticker) as cnt
        FROM ticker_fundamentals
        WHERE region = %s
        """
        result = self.db.execute_query(query_fundamental, (region,))
        fundamental_tickers = result[0]['cnt'] if result else 0

        return fundamental_tickers / total_tickers

    def _detect_price_anomalies(self, region: str, threshold: float = 0.20) -> int:
        """
        Detect price anomalies (sudden price changes)

        Args:
            region: Region code
            threshold: Price change threshold (default: 20%)

        Returns:
            Number of anomalies detected
        """
        query = """
        WITH price_changes AS (
            SELECT
                ticker,
                date,
                close,
                LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close
            FROM ohlcv_data
            WHERE region = %s
              AND date >= NOW() - INTERVAL '7 days'
        )
        SELECT COUNT(*) as cnt
        FROM price_changes
        WHERE prev_close IS NOT NULL
          AND ABS((close - prev_close) / prev_close) > %s
        """

        result = self.db.execute_query(query, (region, threshold))
        return result[0]['cnt'] if result else 0
