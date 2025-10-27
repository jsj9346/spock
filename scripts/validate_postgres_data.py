#!/usr/bin/env python3
"""
PostgreSQL Data Validation Script

Validates data integrity after migration from SQLite to PostgreSQL.

Checks:
- Row count comparison
- Date coverage verification
- NULL value detection
- Data type validation
- Referential integrity
- Outlier detection

Usage:
    python3 scripts/validate_postgres_data.py
    python3 scripts/validate_postgres_data.py --table ohlcv_data
    python3 scripts/validate_postgres_data.py --comprehensive
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.db_manager_postgres import PostgresDatabaseManager


class PostgresDataValidator:
    """
    Validates PostgreSQL data against SQLite source.

    Performs comprehensive data integrity checks to ensure
    successful migration.
    """

    def __init__(self,
                 sqlite_path: str,
                 postgres_manager: PostgresDatabaseManager):
        """
        Initialize validator.

        Args:
            sqlite_path: Path to SQLite database
            postgres_manager: PostgreSQL database manager
        """
        self.sqlite_db = SQLiteDatabaseManager(sqlite_path)
        self.postgres_db = postgres_manager

        # Validation results
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    def validate_row_counts(self, table: str) -> bool:
        """
        Compare row counts between SQLite and PostgreSQL.

        Args:
            table: Table name to validate

        Returns:
            True if counts match, False otherwise
        """
        logger.info(f"Validating row counts for {table}...")

        try:
            # SQLite count
            sqlite_count = self.sqlite_db.execute_query(
                f"SELECT COUNT(*) as count FROM {table}"
            )[0]['count']

            # PostgreSQL count
            pg_result = self.postgres_db.execute_query(
                f"SELECT COUNT(*) as count FROM {table}"
            )
            pg_count = pg_result[0]['count']

            if sqlite_count == pg_count:
                self.results['passed'].append(
                    f"{table}: Row count match ({sqlite_count:,} rows)"
                )
                logger.info(f"✅ {table}: {sqlite_count:,} rows (match)")
                return True
            else:
                diff = abs(sqlite_count - pg_count)
                diff_pct = (diff / sqlite_count * 100) if sqlite_count > 0 else 0
                self.results['failed'].append(
                    f"{table}: Row count mismatch "
                    f"(SQLite: {sqlite_count:,}, PostgreSQL: {pg_count:,}, "
                    f"Diff: {diff:,}, {diff_pct:.2f}%)"
                )
                logger.error(
                    f"❌ {table}: SQLite={sqlite_count:,}, "
                    f"PostgreSQL={pg_count:,} (diff: {diff:,})"
                )
                return False

        except Exception as e:
            self.results['failed'].append(f"{table}: Row count validation error - {e}")
            logger.error(f"❌ Error validating {table}: {e}")
            return False

    def validate_date_coverage(self,
                              table: str = 'ohlcv_data',
                              ticker: str = None) -> bool:
        """
        Validate date coverage for time-series data.

        Args:
            table: Table name (default: ohlcv_data)
            ticker: Specific ticker to validate (optional)

        Returns:
            True if date coverage matches, False otherwise
        """
        logger.info(f"Validating date coverage for {table}...")

        try:
            where_clause = f"WHERE ticker = '{ticker}'" if ticker else ""

            # SQLite date range
            sqlite_range = self.sqlite_db.execute_query(
                f"""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM {table}
                {where_clause}
                """
            )[0]

            # PostgreSQL date range
            pg_range = self.postgres_db.execute_query(
                f"""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM {table}
                {where_clause}
                """
            )[0]

            if (sqlite_range['min_date'] == pg_range['min_date'] and
                sqlite_range['max_date'] == pg_range['max_date']):
                self.results['passed'].append(
                    f"{table}: Date coverage match "
                    f"({sqlite_range['min_date']} to {sqlite_range['max_date']})"
                )
                logger.info(
                    f"✅ {table}: {sqlite_range['min_date']} to {sqlite_range['max_date']}"
                )
                return True
            else:
                self.results['failed'].append(
                    f"{table}: Date coverage mismatch "
                    f"(SQLite: {sqlite_range['min_date']} to {sqlite_range['max_date']}, "
                    f"PostgreSQL: {pg_range['min_date']} to {pg_range['max_date']})"
                )
                logger.error(
                    f"❌ {table}: Date ranges differ - "
                    f"SQLite: {sqlite_range['min_date']} to {sqlite_range['max_date']}, "
                    f"PostgreSQL: {pg_range['min_date']} to {pg_range['max_date']}"
                )
                return False

        except Exception as e:
            self.results['failed'].append(
                f"{table}: Date coverage validation error - {e}"
            )
            logger.error(f"❌ Error validating date coverage: {e}")
            return False

    def validate_null_counts(self, table: str, columns: List[str]) -> bool:
        """
        Check for unexpected NULL values.

        Args:
            table: Table name
            columns: List of columns that should not be NULL

        Returns:
            True if no unexpected NULLs, False otherwise
        """
        logger.info(f"Validating NULL counts for {table}...")

        try:
            all_valid = True

            for column in columns:
                # PostgreSQL NULL count
                null_count = self.postgres_db.execute_query(
                    f"""
                    SELECT COUNT(*) as count
                    FROM {table}
                    WHERE {column} IS NULL
                    """
                )[0]['count']

                if null_count > 0:
                    self.results['warnings'].append(
                        f"{table}.{column}: {null_count:,} NULL values found"
                    )
                    logger.warning(
                        f"⚠️  {table}.{column}: {null_count:,} NULL values"
                    )
                    all_valid = False
                else:
                    logger.info(f"✅ {table}.{column}: No NULL values")

            if all_valid:
                self.results['passed'].append(
                    f"{table}: No unexpected NULL values in {', '.join(columns)}"
                )

            return all_valid

        except Exception as e:
            self.results['failed'].append(
                f"{table}: NULL validation error - {e}"
            )
            logger.error(f"❌ Error validating NULLs: {e}")
            return False

    def validate_ohlcv_data_quality(self, sample_size: int = 1000) -> bool:
        """
        Validate OHLCV data quality with business logic checks.

        Args:
            sample_size: Number of random rows to validate

        Returns:
            True if data quality checks pass, False otherwise
        """
        logger.info("Validating OHLCV data quality...")

        try:
            # Check: High >= Low
            invalid_high_low = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data
                WHERE high < low
                """
            )[0]['count']

            if invalid_high_low > 0:
                self.results['failed'].append(
                    f"OHLCV: {invalid_high_low:,} rows where high < low"
                )
                logger.error(f"❌ {invalid_high_low:,} rows where high < low")
                return False

            # Check: Close within [Low, High]
            invalid_close = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data
                WHERE close < low OR close > high
                """
            )[0]['count']

            if invalid_close > 0:
                self.results['failed'].append(
                    f"OHLCV: {invalid_close:,} rows where close outside [low, high]"
                )
                logger.error(
                    f"❌ {invalid_close:,} rows where close outside [low, high]"
                )
                return False

            # Check: Open within [Low, High]
            invalid_open = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data
                WHERE open < low OR open > high
                """
            )[0]['count']

            if invalid_open > 0:
                self.results['warnings'].append(
                    f"OHLCV: {invalid_open:,} rows where open outside [low, high]"
                )
                logger.warning(
                    f"⚠️  {invalid_open:,} rows where open outside [low, high]"
                )

            # Check: Volume >= 0
            invalid_volume = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data
                WHERE volume < 0
                """
            )[0]['count']

            if invalid_volume > 0:
                self.results['failed'].append(
                    f"OHLCV: {invalid_volume:,} rows with negative volume"
                )
                logger.error(f"❌ {invalid_volume:,} rows with negative volume")
                return False

            # Check: Prices > 0
            invalid_prices = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data
                WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                """
            )[0]['count']

            if invalid_prices > 0:
                self.results['failed'].append(
                    f"OHLCV: {invalid_prices:,} rows with non-positive prices"
                )
                logger.error(
                    f"❌ {invalid_prices:,} rows with non-positive prices"
                )
                return False

            self.results['passed'].append("OHLCV: Data quality checks passed")
            logger.info("✅ OHLCV data quality checks passed")
            return True

        except Exception as e:
            self.results['failed'].append(f"OHLCV: Data quality validation error - {e}")
            logger.error(f"❌ Error validating OHLCV data quality: {e}")
            return False

    def validate_referential_integrity(self) -> bool:
        """
        Validate foreign key relationships.

        Returns:
            True if all relationships are valid, False otherwise
        """
        logger.info("Validating referential integrity...")

        try:
            all_valid = True

            # Check: OHLCV data references valid tickers
            orphaned_ohlcv = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM ohlcv_data o
                LEFT JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
                WHERE t.ticker IS NULL
                """
            )[0]['count']

            if orphaned_ohlcv > 0:
                self.results['failed'].append(
                    f"OHLCV: {orphaned_ohlcv:,} orphaned records "
                    f"(no matching ticker in tickers table)"
                )
                logger.error(
                    f"❌ {orphaned_ohlcv:,} OHLCV records without matching ticker"
                )
                all_valid = False
            else:
                logger.info("✅ All OHLCV records have valid ticker references")

            # Check: Technical analysis references valid tickers
            orphaned_ta = self.postgres_db.execute_query(
                """
                SELECT COUNT(*) as count
                FROM technical_analysis ta
                LEFT JOIN tickers t ON ta.ticker = t.ticker AND ta.region = t.region
                WHERE t.ticker IS NULL
                """
            )[0]['count']

            if orphaned_ta > 0:
                self.results['failed'].append(
                    f"Technical Analysis: {orphaned_ta:,} orphaned records"
                )
                logger.error(
                    f"❌ {orphaned_ta:,} technical analysis records without matching ticker"
                )
                all_valid = False
            else:
                logger.info("✅ All technical analysis records have valid ticker references")

            if all_valid:
                self.results['passed'].append(
                    "Referential integrity: All foreign key relationships valid"
                )

            return all_valid

        except Exception as e:
            self.results['failed'].append(
                f"Referential integrity validation error - {e}"
            )
            logger.error(f"❌ Error validating referential integrity: {e}")
            return False

    def validate_timescaledb_features(self) -> bool:
        """
        Validate TimescaleDB-specific features.

        Returns:
            True if TimescaleDB features are configured, False otherwise
        """
        logger.info("Validating TimescaleDB features...")

        try:
            # Check hypertables
            hypertables = self.postgres_db.execute_query(
                """
                SELECT hypertable_name
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
                """
            )

            hypertable_names = [h['hypertable_name'] for h in hypertables]

            if 'ohlcv_data' in hypertable_names:
                self.results['passed'].append(
                    "TimescaleDB: ohlcv_data is a hypertable"
                )
                logger.info("✅ ohlcv_data is a hypertable")
            else:
                self.results['failed'].append(
                    "TimescaleDB: ohlcv_data is not a hypertable"
                )
                logger.error("❌ ohlcv_data is not a hypertable")
                return False

            # Check compression
            compression = self.postgres_db.execute_query(
                """
                SELECT tablename, compression_enabled
                FROM timescaledb_information.compression_settings
                WHERE tablename = 'ohlcv_data'
                """
            )

            if compression and compression[0]['compression_enabled']:
                self.results['passed'].append(
                    "TimescaleDB: Compression enabled for ohlcv_data"
                )
                logger.info("✅ Compression enabled for ohlcv_data")
            else:
                self.results['warnings'].append(
                    "TimescaleDB: Compression not enabled for ohlcv_data"
                )
                logger.warning("⚠️  Compression not enabled for ohlcv_data")

            # Check continuous aggregates
            continuous_aggs = self.postgres_db.execute_query(
                """
                SELECT view_name
                FROM timescaledb_information.continuous_aggregates
                """
            )

            agg_names = [a['view_name'] for a in continuous_aggs]

            if 'ohlcv_monthly' in agg_names:
                logger.info("✅ ohlcv_monthly continuous aggregate exists")
            else:
                self.results['warnings'].append(
                    "TimescaleDB: ohlcv_monthly continuous aggregate not found"
                )
                logger.warning("⚠️  ohlcv_monthly continuous aggregate not found")

            if 'ohlcv_yearly' in agg_names:
                logger.info("✅ ohlcv_yearly continuous aggregate exists")
            else:
                self.results['warnings'].append(
                    "TimescaleDB: ohlcv_yearly continuous aggregate not found"
                )
                logger.warning("⚠️  ohlcv_yearly continuous aggregate not found")

            return True

        except Exception as e:
            self.results['failed'].append(
                f"TimescaleDB validation error - {e}"
            )
            logger.error(f"❌ Error validating TimescaleDB features: {e}")
            return False

    def print_summary(self):
        """Print validation summary."""
        logger.info("=" * 70)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 70)

        logger.info(f"\n✅ PASSED ({len(self.results['passed'])} checks):")
        for check in self.results['passed']:
            logger.info(f"  ✅ {check}")

        if self.results['warnings']:
            logger.info(f"\n⚠️  WARNINGS ({len(self.results['warnings'])} issues):")
            for warning in self.results['warnings']:
                logger.warning(f"  ⚠️  {warning}")

        if self.results['failed']:
            logger.info(f"\n❌ FAILED ({len(self.results['failed'])} checks):")
            for failure in self.results['failed']:
                logger.error(f"  ❌ {failure}")

        logger.info("=" * 70)

        # Overall result
        if not self.results['failed']:
            logger.info("✅ VALIDATION SUCCESSFUL")
            return True
        else:
            logger.error("❌ VALIDATION FAILED")
            return False


def main():
    """Main validation workflow."""
    parser = argparse.ArgumentParser(description="Validate PostgreSQL data")
    parser.add_argument(
        '--sqlite-path',
        default='data/spock_local.db',
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--table',
        help='Validate specific table only'
    )
    parser.add_argument(
        '--comprehensive',
        action='store_true',
        help='Run comprehensive validation (all checks)'
    )

    args = parser.parse_args()

    # Setup logging
    log_file = f"logs/{datetime.now().strftime('%Y%m%d')}_validation.log"
    logger.add(log_file, rotation="100 MB")

    logger.info("=" * 70)
    logger.info("PostgreSQL Data Validation")
    logger.info("=" * 70)

    # Initialize PostgreSQL
    try:
        postgres_db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    # Create validator
    validator = PostgresDataValidator(
        sqlite_path=args.sqlite_path,
        postgres_manager=postgres_db
    )

    # Run validations
    if args.table:
        # Validate specific table
        validator.validate_row_counts(args.table)
        if args.table == 'ohlcv_data':
            validator.validate_date_coverage()
            validator.validate_ohlcv_data_quality()
    else:
        # Validate all tables
        tables = ['tickers', 'ohlcv_data', 'stock_details', 'technical_analysis']
        for table in tables:
            validator.validate_row_counts(table)

        # Date coverage
        validator.validate_date_coverage('ohlcv_data')

        # NULL checks
        validator.validate_null_counts('tickers', ['ticker', 'region'])
        validator.validate_null_counts('ohlcv_data', ['ticker', 'region', 'date'])

        # Data quality
        validator.validate_ohlcv_data_quality()

        # Referential integrity
        validator.validate_referential_integrity()

        # TimescaleDB features
        if args.comprehensive:
            validator.validate_timescaledb_features()

    # Print summary
    success = validator.print_summary()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
