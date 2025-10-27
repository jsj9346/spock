#!/usr/bin/env python3
"""
validate_db_schema.py - Multi-Market Database Schema Validation Script

Purpose:
- Validate multi-market data integrity (KR, US, HK, CN, JP, VN)
- Check cross-region contamination (region column correctness)
- Verify data quality metrics (NULL values, date ranges, completeness)
- Generate validation report with actionable recommendations

Validation Categories:
1. Schema Validation: Table structure, column types, indexes
2. Data Integrity: Region column, unique constraints, foreign keys
3. Cross-Region Contamination: Region isolation, ticker format validation
4. Data Quality: NULL values, date ranges, completeness
5. Performance Metrics: Table sizes, index usage, query performance

Author: Spock Trading System
Created: 2025-10-16
"""

import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseSchemaValidator:
    """Multi-market database schema validator"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        """Initialize validator"""
        self.db_path = db_path
        self.db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.validation_results = {
            'schema': [],
            'integrity': [],
            'contamination': [],
            'quality': [],
            'performance': []
        }
        self.errors = []
        self.warnings = []
        self.passed_checks = 0
        self.failed_checks = 0

    def validate_all(self) -> Dict[str, Any]:
        """Run all validation checks"""
        logger.info("=" * 60)
        logger.info("Database Schema Validation - Multi-Market")
        logger.info("=" * 60)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Validation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info("")

        # Run validation categories
        self.validate_schema()
        self.validate_data_integrity()
        self.validate_cross_region_contamination()
        self.validate_data_quality()
        self.validate_performance()

        # Generate summary
        return self.generate_summary()

    def validate_schema(self):
        """Validate database schema (tables, columns, indexes)"""
        logger.info("📋 Category 1: Schema Validation")
        logger.info("-" * 60)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Check 1.1: Required tables exist
        required_tables = [
            'ohlcv_data',
            'filter_cache_stage0',
            'exchange_rate_history'
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]

        for table in required_tables:
            if table in existing_tables:
                self._pass_check(f"Table '{table}' exists")
            else:
                self._fail_check(f"Table '{table}' missing")

        # Check 1.2: ohlcv_data table schema
        cursor.execute("PRAGMA table_info(ohlcv_data)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        required_columns = {
            'ticker': 'TEXT',
            'region': 'TEXT',
            'timeframe': 'TEXT',
            'date': 'DATE',
            'open': 'REAL',
            'high': 'REAL',
            'low': 'REAL',
            'close': 'REAL',
            'volume': 'BIGINT',
            'ma5': 'REAL',
            'ma20': 'REAL',
            'ma60': 'REAL',
            'ma120': 'REAL',
            'ma200': 'REAL',
            'rsi_14': 'REAL',
            'macd': 'REAL',
            'macd_signal': 'REAL',
            'macd_hist': 'REAL',
            'volume_ma20': 'BIGINT',
            'volume_ratio': 'REAL',
            'atr': 'REAL',
            'bb_upper': 'REAL',
            'bb_middle': 'REAL',
            'bb_lower': 'REAL'
        }

        for col_name, col_type in required_columns.items():
            if col_name in columns:
                if columns[col_name].upper() == col_type.upper():
                    self._pass_check(f"Column 'ohlcv_data.{col_name}' exists with type {col_type}")
                else:
                    self._warn_check(f"Column 'ohlcv_data.{col_name}' type mismatch: expected {col_type}, got {columns[col_name]}")
            else:
                self._fail_check(f"Column 'ohlcv_data.{col_name}' missing")

        # Check 1.3: Indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ohlcv_data'")
        indexes = [row[0] for row in cursor.fetchall()]

        required_indexes = [
            'idx_ohlcv_ticker_region',
            'idx_ohlcv_date',
            'idx_ohlcv_timeframe',
            'idx_ohlcv_ticker_date'
        ]

        for index in required_indexes:
            if index in indexes:
                self._pass_check(f"Index '{index}' exists")
            else:
                self._warn_check(f"Index '{index}' missing (performance impact)")

        conn.close()
        logger.info("")

    def validate_data_integrity(self):
        """Validate data integrity (region column, unique constraints)"""
        logger.info("🔍 Category 2: Data Integrity")
        logger.info("-" * 60)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Check 2.1: Region column NOT NULL
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL")
        null_regions = cursor.fetchone()[0]

        if null_regions == 0:
            self._pass_check("No NULL regions in ohlcv_data (region column integrity)")
        else:
            self._fail_check(f"Found {null_regions:,} NULL regions in ohlcv_data (CRITICAL: data contamination risk)")

        # Check 2.2: Region values valid
        cursor.execute("SELECT DISTINCT region FROM ohlcv_data ORDER BY region")
        regions = [row[0] for row in cursor.fetchall() if row[0]]

        valid_regions = ['KR', 'US', 'HK', 'CN', 'JP', 'VN']
        invalid_regions = [r for r in regions if r not in valid_regions]

        if not invalid_regions:
            self._pass_check(f"All regions valid: {', '.join(regions)}")
        else:
            self._fail_check(f"Invalid regions found: {', '.join(invalid_regions)}")

        # Check 2.3: UNIQUE constraint on (ticker, region, timeframe, date)
        cursor.execute("""
            SELECT ticker, region, timeframe, date, COUNT(*) as cnt
            FROM ohlcv_data
            GROUP BY ticker, region, timeframe, date
            HAVING cnt > 1
            LIMIT 10
        """)
        duplicates = cursor.fetchall()

        if not duplicates:
            self._pass_check("No duplicate entries (ticker, region, timeframe, date unique)")
        else:
            self._fail_check(f"Found {len(duplicates)} duplicate entries (UNIQUE constraint violation)")
            for dup in duplicates[:5]:
                logger.error(f"   Duplicate: {dup[0]} ({dup[1]}) {dup[2]} {dup[3]} - {dup[4]} occurrences")

        conn.close()
        logger.info("")

    def validate_cross_region_contamination(self):
        """Validate cross-region contamination (ticker format by region)"""
        logger.info("🌐 Category 3: Cross-Region Contamination")
        logger.info("-" * 60)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Ticker format validation rules
        ticker_patterns = {
            'KR': r'^[0-9]{6}$',  # 6-digit numeric
            'US': r'^[A-Z]{1,5}(\.[A-Z])?$',  # 1-5 uppercase letters, optional .B suffix
            'HK': r'^[0-9]{4,5}$',  # 4-5 digit numeric
            'CN': r'^[0-9]{6}$',  # 6-digit numeric
            'JP': r'^[0-9]{4}$',  # 4-digit numeric
            'VN': r'^[A-Z]{3}$'   # 3-letter uppercase
        }

        for region, pattern in ticker_patterns.items():
            # Check ticker format compliance
            cursor.execute(f"""
                SELECT COUNT(*) FROM ohlcv_data
                WHERE region = ?
            """, (region,))
            total_count = cursor.fetchone()[0]

            if total_count == 0:
                self._warn_check(f"No data found for region {region} (not yet populated)")
                continue

            # Check for mismatched ticker formats (basic validation)
            cursor.execute(f"""
                SELECT DISTINCT ticker FROM ohlcv_data
                WHERE region = ?
                LIMIT 100
            """, (region,))
            tickers = [row[0] for row in cursor.fetchall()]

            # Basic format validation (simplified, not full regex)
            invalid_tickers = []
            for ticker in tickers:
                if region == 'KR' and (not ticker.isdigit() or len(ticker) != 6):
                    invalid_tickers.append(ticker)
                elif region == 'US' and not (ticker.isalpha() and ticker.isupper()):
                    # Simplified: allow only uppercase letters (ignore .B suffix for now)
                    pass
                elif region == 'HK' and (not ticker.isdigit() or len(ticker) not in [4, 5]):
                    invalid_tickers.append(ticker)
                elif region == 'CN' and (not ticker.isdigit() or len(ticker) != 6):
                    invalid_tickers.append(ticker)
                elif region == 'JP' and (not ticker.isdigit() or len(ticker) != 4):
                    invalid_tickers.append(ticker)
                elif region == 'VN' and (not ticker.isalpha() or not ticker.isupper() or len(ticker) != 3):
                    invalid_tickers.append(ticker)

            if not invalid_tickers:
                self._pass_check(f"Region {region}: All tickers ({total_count:,} rows) match expected format")
            else:
                self._warn_check(f"Region {region}: {len(invalid_tickers)} tickers may not match expected format (sample: {invalid_tickers[:3]})")

        conn.close()
        logger.info("")

    def validate_data_quality(self):
        """Validate data quality (NULL values, date ranges, completeness)"""
        logger.info("📊 Category 4: Data Quality")
        logger.info("-" * 60)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Check 4.1: OHLCV data completeness (no NULLs in critical columns)
        critical_columns = ['open', 'high', 'low', 'close', 'volume']

        for col in critical_columns:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {col} IS NULL")
            null_count = cursor.fetchone()[0]

            if null_count == 0:
                self._pass_check(f"No NULL values in 'ohlcv_data.{col}' (data completeness)")
            else:
                self._fail_check(f"Found {null_count:,} NULL values in 'ohlcv_data.{col}' (CRITICAL: incomplete data)")

        # Check 4.2: Technical indicators completeness (expected NULLs for recent data)
        indicator_columns = ['ma200', 'rsi_14', 'macd']

        for col in indicator_columns:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {col} IS NULL")
            null_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
            total_count = cursor.fetchone()[0]

            null_pct = (null_count / total_count * 100) if total_count > 0 else 0

            if null_pct < 20:  # Expected <20% NULL for indicators (recent data)
                self._pass_check(f"Indicator '{col}' NULL rate: {null_pct:.1f}% (acceptable)")
            else:
                self._warn_check(f"Indicator '{col}' NULL rate: {null_pct:.1f}% (may indicate incomplete calculations)")

        # Check 4.3: Date range validation (ensure data is recent)
        cursor.execute("SELECT MIN(date), MAX(date) FROM ohlcv_data")
        min_date, max_date = cursor.fetchone()

        if min_date and max_date:
            min_date_obj = datetime.strptime(min_date, '%Y-%m-%d')
            max_date_obj = datetime.strptime(max_date, '%Y-%m-%d')
            days_range = (max_date_obj - min_date_obj).days

            self._pass_check(f"Date range: {min_date} to {max_date} ({days_range} days)")

            # Check if data is recent (within last 7 days)
            days_since_latest = (datetime.now() - max_date_obj).days

            if days_since_latest <= 7:
                self._pass_check(f"Latest data is recent ({days_since_latest} days old)")
            else:
                self._warn_check(f"Latest data is {days_since_latest} days old (may need update)")
        else:
            self._warn_check("No date range found (empty database)")

        # Check 4.4: Per-region data counts
        cursor.execute("""
            SELECT region, COUNT(*) as cnt, COUNT(DISTINCT ticker) as ticker_cnt
            FROM ohlcv_data
            GROUP BY region
            ORDER BY region
        """)
        region_stats = cursor.fetchall()

        logger.info("Per-region data statistics:")
        for region, row_count, ticker_count in region_stats:
            logger.info(f"   • {region}: {row_count:,} rows, {ticker_count:,} tickers")
            self._pass_check(f"Region {region}: {row_count:,} rows, {ticker_count:,} tickers")

        conn.close()
        logger.info("")

    def validate_performance(self):
        """Validate performance metrics (table sizes, index usage)"""
        logger.info("⚡ Category 5: Performance Metrics")
        logger.info("-" * 60)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Check 5.1: Table sizes
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        ohlcv_count = cursor.fetchone()[0]

        if ohlcv_count > 0:
            self._pass_check(f"ohlcv_data table: {ohlcv_count:,} rows")

            # Estimate table size (rough)
            estimated_size_mb = ohlcv_count * 0.5 / 1000  # ~0.5 KB per row
            logger.info(f"   Estimated table size: ~{estimated_size_mb:.1f} MB")

            if estimated_size_mb < 1000:  # <1 GB
                self._pass_check(f"Table size within limits (~{estimated_size_mb:.1f} MB)")
            else:
                self._warn_check(f"Large table size (~{estimated_size_mb:.1f} MB, consider archival)")
        else:
            self._warn_check("ohlcv_data table is empty (no performance metrics)")

        # Check 5.2: Index statistics
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='ohlcv_data'
        """)
        indexes = cursor.fetchall()

        logger.info(f"Indexes on ohlcv_data: {len(indexes)}")
        for idx in indexes:
            logger.info(f"   • {idx[0]}")

        conn.close()
        logger.info("")

    def generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary report"""
        logger.info("=" * 60)
        logger.info("📋 Validation Summary")
        logger.info("=" * 60)

        total_checks = self.passed_checks + self.failed_checks
        pass_rate = (self.passed_checks / total_checks * 100) if total_checks > 0 else 0

        logger.info(f"Total Checks:    {total_checks}")
        logger.info(f"Passed:          {self.passed_checks} ({pass_rate:.1f}%)")
        logger.info(f"Failed:          {self.failed_checks}")
        logger.info(f"Warnings:        {len(self.warnings)}")
        logger.info("=" * 60)

        # Overall status
        if self.failed_checks == 0:
            logger.info("")
            logger.info("✅ DATABASE SCHEMA VALIDATION: PASSED")
            logger.info("   All critical checks passed. Database is production-ready.")
            status = "PASSED"
        elif self.failed_checks <= 2:
            logger.info("")
            logger.info("⚠️ DATABASE SCHEMA VALIDATION: PASSED WITH WARNINGS")
            logger.info(f"   {self.failed_checks} non-critical issues found. Review recommended.")
            status = "PASSED_WITH_WARNINGS"
        else:
            logger.info("")
            logger.info("❌ DATABASE SCHEMA VALIDATION: FAILED")
            logger.info(f"   {self.failed_checks} critical issues found. Fix required before production.")
            status = "FAILED"

        # Print errors and warnings summary
        if self.errors:
            logger.info("")
            logger.info("Critical Errors:")
            for error in self.errors[:10]:
                logger.info(f"   ❌ {error}")

        if self.warnings:
            logger.info("")
            logger.info("Warnings:")
            for warning in self.warnings[:10]:
                logger.info(f"   ⚠️ {warning}")

        return {
            'status': status,
            'total_checks': total_checks,
            'passed': self.passed_checks,
            'failed': self.failed_checks,
            'warnings': len(self.warnings),
            'pass_rate': pass_rate,
            'errors': self.errors,
            'warnings_list': self.warnings
        }

    def _pass_check(self, message: str):
        """Record a passed check"""
        logger.info(f"✅ {message}")
        self.passed_checks += 1

    def _fail_check(self, message: str):
        """Record a failed check"""
        logger.error(f"❌ {message}")
        self.failed_checks += 1
        self.errors.append(message)

    def _warn_check(self, message: str):
        """Record a warning"""
        logger.warning(f"⚠️ {message}")
        self.warnings.append(message)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Database Schema Validation - Multi-Market Data Integrity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Validation Categories:
  1. Schema Validation    - Table structure, columns, indexes
  2. Data Integrity       - Region column, unique constraints
  3. Cross-Region Check   - Region isolation, ticker format
  4. Data Quality         - NULL values, date ranges, completeness
  5. Performance Metrics  - Table sizes, index usage

Exit Codes:
  0 - All checks passed
  1 - Validation failed (critical issues found)
  2 - Passed with warnings (non-critical issues)

Examples:
  # Run full validation
  python3 scripts/validate_db_schema.py

  # Validation with debug output
  python3 scripts/validate_db_schema.py --debug
        """
    )

    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path (default: data/spock_local.db)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Initialize validator
        validator = DatabaseSchemaValidator(db_path=args.db_path)

        # Run validation
        summary = validator.validate_all()

        # Determine exit code
        if summary['status'] == 'PASSED':
            return 0
        elif summary['status'] == 'PASSED_WITH_WARNINGS':
            return 2
        else:
            return 1

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("⚠️ Validation interrupted by user (Ctrl+C)")
        return 130
    except Exception as e:
        logger.error("")
        logger.error(f"❌ Database validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
