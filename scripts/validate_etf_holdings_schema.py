"""
ETF Holdings Schema Validation Script

Comprehensive validation and testing for ETF holdings schema migration

Validation Checks:
1. Table existence and structure
2. Foreign key constraints
3. Index effectiveness
4. Data integrity rules
5. Query performance benchmarks

Usage:
    python scripts/validate_etf_holdings_schema.py
    python scripts/validate_etf_holdings_schema.py --insert-test-data
    python scripts/validate_etf_holdings_schema.py --benchmark-queries

Author: Spock Trading System
Date: 2025-10-17
"""

import os
import sys
import sqlite3
import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ETFHoldingsSchemaValidator:
    """ETF Holdings schema validation and testing"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"Database not found: {db_path}\n"
                f"Please run: python init_db.py"
            )

    def validate_all(self) -> bool:
        """Run all validation checks"""
        logger.info("=" * 70)
        logger.info("ETF Holdings Schema Validation")
        logger.info("=" * 70)

        checks = [
            ("Table Structure", self._validate_table_structure),
            ("Foreign Key Constraints", self._validate_foreign_keys),
            ("Indexes", self._validate_indexes),
            ("Data Integrity Rules", self._validate_data_integrity),
        ]

        results = {}
        for check_name, check_func in checks:
            logger.info(f"\n[Check] {check_name}...")
            try:
                success = check_func()
                results[check_name] = success
                if success:
                    logger.info(f"✅ {check_name}: PASSED")
                else:
                    logger.error(f"❌ {check_name}: FAILED")
            except Exception as e:
                logger.error(f"❌ {check_name}: ERROR - {e}")
                results[check_name] = False

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("Validation Summary")
        logger.info("=" * 70)

        passed = sum(1 for v in results.values() if v)
        total = len(results)

        for check_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"  {status}  {check_name}")

        logger.info("=" * 70)
        logger.info(f"Result: {passed}/{total} checks passed")

        if passed == total:
            logger.info("✅ All validation checks PASSED")
            return True
        else:
            logger.error(f"❌ {total - passed} validation check(s) FAILED")
            return False

    def _validate_table_structure(self) -> bool:
        """Validate table structure matches design spec"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check etfs table
            cursor.execute("PRAGMA table_info(etfs)")
            etfs_columns = {row[1]: row[2] for row in cursor.fetchall()}

            expected_etfs_columns = {
                'ticker': 'TEXT',
                'name': 'TEXT',
                'region': 'TEXT',
                'category': 'TEXT',
                'tracking_index': 'TEXT',
                'total_assets': 'REAL',
                'expense_ratio': 'REAL',
                'issuer': 'TEXT',
                'inception_date': 'TEXT',
                'leverage_ratio': 'REAL',
                'tracking_error_20d': 'REAL',
                'avg_daily_volume': 'REAL',
                'created_at': 'TEXT',
                'last_updated': 'TEXT',
            }

            for col_name, col_type in expected_etfs_columns.items():
                if col_name not in etfs_columns:
                    logger.error(f"  ❌ Missing column in etfs: {col_name}")
                    return False
                if etfs_columns[col_name] != col_type:
                    logger.warning(f"  ⚠️  Column type mismatch in etfs.{col_name}: "
                                 f"expected {col_type}, got {etfs_columns[col_name]}")

            logger.info(f"  ✓ etfs table: {len(etfs_columns)} columns")

            # Check etf_holdings table
            cursor.execute("PRAGMA table_info(etf_holdings)")
            holdings_columns = {row[1]: row[2] for row in cursor.fetchall()}

            expected_holdings_columns = {
                'id': 'INTEGER',
                'etf_ticker': 'TEXT',
                'stock_ticker': 'TEXT',
                'weight': 'REAL',
                'shares': 'INTEGER',
                'market_value': 'REAL',
                'rank_in_etf': 'INTEGER',
                'weight_change_from_prev': 'REAL',
                'as_of_date': 'TEXT',
                'created_at': 'TEXT',
            }

            for col_name, col_type in expected_holdings_columns.items():
                if col_name not in holdings_columns:
                    logger.error(f"  ❌ Missing column in etf_holdings: {col_name}")
                    return False
                if holdings_columns[col_name] != col_type:
                    logger.warning(f"  ⚠️  Column type mismatch in etf_holdings.{col_name}: "
                                 f"expected {col_type}, got {holdings_columns[col_name]}")

            logger.info(f"  ✓ etf_holdings table: {len(holdings_columns)} columns")

            return True

        finally:
            conn.close()

    def _validate_foreign_keys(self) -> bool:
        """Validate foreign key constraints"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check foreign key pragma
            cursor.execute("PRAGMA foreign_keys")
            fk_enabled = cursor.fetchone()[0]

            if not fk_enabled:
                logger.warning("  ⚠️  Foreign keys are DISABLED (PRAGMA foreign_keys = OFF)")
                logger.warning("  ⚠️  Enable with: PRAGMA foreign_keys = ON")

            # Check etfs foreign keys
            cursor.execute("PRAGMA foreign_key_list(etfs)")
            etfs_fks = cursor.fetchall()

            if not etfs_fks:
                logger.error("  ❌ etfs table has no foreign keys defined")
                return False

            logger.info(f"  ✓ etfs foreign keys: {len(etfs_fks)}")
            for fk in etfs_fks:
                logger.info(f"    - {fk[3]} → {fk[2]}({fk[4]})")

            # Check etf_holdings foreign keys
            cursor.execute("PRAGMA foreign_key_list(etf_holdings)")
            holdings_fks = cursor.fetchall()

            if len(holdings_fks) != 2:
                logger.error(f"  ❌ etf_holdings should have 2 foreign keys, found {len(holdings_fks)}")
                return False

            logger.info(f"  ✓ etf_holdings foreign keys: {len(holdings_fks)}")
            for fk in holdings_fks:
                logger.info(f"    - {fk[3]} → {fk[2]}({fk[4]})")

            return True

        finally:
            conn.close()

    def _validate_indexes(self) -> bool:
        """Validate indexes exist and are effective"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Expected indexes
            expected_indexes = {
                'idx_etfs_region': 'etfs',
                'idx_etfs_category': 'etfs',
                'idx_etfs_issuer': 'etfs',
                'idx_etfs_total_assets': 'etfs',
                'idx_holdings_stock_date_weight': 'etf_holdings',
                'idx_holdings_etf_date_weight': 'etf_holdings',
                'idx_holdings_date': 'etf_holdings',
                'idx_holdings_weight': 'etf_holdings',
            }

            # Check index existence
            cursor.execute("""
                SELECT name, tbl_name FROM sqlite_master
                WHERE type='index' AND (name LIKE 'idx_%etfs%' OR name LIKE 'idx_holdings%')
            """)
            existing_indexes = {row[0]: row[1] for row in cursor.fetchall()}

            missing_indexes = set(expected_indexes.keys()) - set(existing_indexes.keys())
            if missing_indexes:
                logger.error(f"  ❌ Missing indexes: {missing_indexes}")
                return False

            logger.info(f"  ✓ All {len(expected_indexes)} indexes exist")

            # Verify index tables
            for idx_name, expected_table in expected_indexes.items():
                actual_table = existing_indexes.get(idx_name)
                if actual_table != expected_table:
                    logger.error(f"  ❌ Index {idx_name} on wrong table: "
                               f"expected {expected_table}, got {actual_table}")
                    return False

            # Test index effectiveness (if data exists)
            cursor.execute("SELECT COUNT(*) FROM etf_holdings")
            holdings_count = cursor.fetchone()[0]

            if holdings_count > 0:
                logger.info(f"  ✓ Testing index effectiveness ({holdings_count:,} holdings)...")

                # Test stock→ETF query (should use idx_holdings_stock_date_weight)
                start_time = time.time()
                cursor.execute("""
                    EXPLAIN QUERY PLAN
                    SELECT etf_ticker, weight
                    FROM etf_holdings
                    WHERE stock_ticker = '005930'
                      AND as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
                    ORDER BY weight DESC
                """)
                query_plan = cursor.fetchall()
                elapsed = (time.time() - start_time) * 1000

                uses_index = any('idx_holdings_stock_date_weight' in str(row) for row in query_plan)
                if uses_index:
                    logger.info(f"    ✓ Stock→ETF query uses index ({elapsed:.2f}ms)")
                else:
                    logger.warning(f"    ⚠️  Stock→ETF query may not use index")
                    logger.warning(f"       Query plan: {query_plan}")

            return True

        finally:
            conn.close()

    def _validate_data_integrity(self) -> bool:
        """Validate data integrity rules"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Check UNIQUE constraint on etf_holdings
            cursor.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='etf_holdings'
            """)
            table_sql = cursor.fetchone()[0]

            if 'UNIQUE(etf_ticker, stock_ticker, as_of_date)' not in table_sql:
                logger.error("  ❌ UNIQUE constraint missing on (etf_ticker, stock_ticker, as_of_date)")
                return False

            logger.info("  ✓ UNIQUE constraint exists on etf_holdings")

            # Check NOT NULL constraints
            cursor.execute("PRAGMA table_info(etf_holdings)")
            columns = cursor.fetchall()

            required_not_null = ['etf_ticker', 'stock_ticker', 'weight', 'as_of_date', 'created_at']
            for col in columns:
                col_name, col_type, not_null = col[1], col[2], col[3]
                if col_name in required_not_null and not not_null:
                    logger.error(f"  ❌ Column {col_name} should be NOT NULL")
                    return False

            logger.info(f"  ✓ All required NOT NULL constraints exist")

            # Test UNIQUE constraint (if data exists)
            cursor.execute("SELECT COUNT(*) FROM etf_holdings")
            if cursor.fetchone()[0] > 0:
                # Check for duplicate combinations
                cursor.execute("""
                    SELECT etf_ticker, stock_ticker, as_of_date, COUNT(*) as cnt
                    FROM etf_holdings
                    GROUP BY etf_ticker, stock_ticker, as_of_date
                    HAVING cnt > 1
                """)
                duplicates = cursor.fetchall()

                if duplicates:
                    logger.error(f"  ❌ Found {len(duplicates)} duplicate holdings:")
                    for dup in duplicates[:5]:
                        logger.error(f"     {dup}")
                    return False

                logger.info("  ✓ No duplicate holdings found")

            return True

        finally:
            conn.close()

    def insert_test_data(self) -> bool:
        """Insert test data for validation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        logger.info("\n" + "=" * 70)
        logger.info("Inserting Test Data")
        logger.info("=" * 70)

        try:
            now = datetime.now().isoformat()
            today = datetime.now().strftime('%Y-%m-%d')

            # Insert test tickers (if not exist)
            test_tickers = [
                ('152100', 'TIGER 200', 'ETF', 'KR', 'KOSPI'),
                ('005930', '삼성전자', 'STOCK', 'KR', 'KOSPI'),
                ('000660', 'SK하이닉스', 'STOCK', 'KR', 'KOSPI'),
                ('035420', 'NAVER', 'STOCK', 'KR', 'KOSPI'),
            ]

            for ticker, name, asset_type, region, exchange in test_tickers:
                cursor.execute("""
                    INSERT OR IGNORE INTO tickers (
                        ticker, name, asset_type, region, exchange, currency,
                        is_active, created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, 'KRW', 1, ?, ?)
                """, (ticker, name, asset_type, region, exchange, now, now))

            logger.info(f"  ✓ Inserted {len(test_tickers)} test tickers")

            # Insert test ETF
            cursor.execute("""
                INSERT OR REPLACE INTO etfs (
                    ticker, name, name_eng, region, exchange,
                    category, tracking_index,
                    total_assets, expense_ratio, listed_shares,
                    issuer, inception_date,
                    leverage_ratio, is_inverse, currency_hedged,
                    avg_daily_volume, avg_daily_value,
                    created_at, last_updated, data_source
                ) VALUES (
                    '152100', 'TIGER 200', 'TIGER 200 ETF', 'KR', 'KOSPI',
                    'INDEX', 'KOSPI 200',
                    5000000000000, 0.15, 100000000,
                    '미래에셋자산운용', '2010-01-01',
                    1.0, 0, 0,
                    1000000, 50000000000,
                    ?, ?, 'TEST_DATA'
                )
            """, (now, now))

            logger.info("  ✓ Inserted test ETF (TIGER 200)")

            # Insert test holdings
            test_holdings = [
                ('152100', '005930', 25.5, 10000000, 1, None, today),  # Samsung Electronics
                ('152100', '000660', 8.3, 3000000, 2, None, today),    # SK Hynix
                ('152100', '035420', 5.2, 1500000, 3, None, today),    # NAVER
            ]

            for etf_ticker, stock_ticker, weight, shares, rank, weight_change, as_of_date in test_holdings:
                cursor.execute("""
                    INSERT OR REPLACE INTO etf_holdings (
                        etf_ticker, stock_ticker, weight, shares,
                        rank_in_etf, weight_change_from_prev, as_of_date,
                        created_at, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TEST_DATA')
                """, (etf_ticker, stock_ticker, weight, shares, rank, weight_change, as_of_date, now))

            conn.commit()
            logger.info(f"  ✓ Inserted {len(test_holdings)} test holdings")

            # Verify insertion
            cursor.execute("SELECT COUNT(*) FROM etf_holdings WHERE data_source = 'TEST_DATA'")
            count = cursor.fetchone()[0]
            logger.info(f"  ✓ Total test holdings in DB: {count}")

            return True

        except Exception as e:
            logger.error(f"  ❌ Insert test data error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def benchmark_queries(self) -> bool:
        """Benchmark query performance"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        logger.info("\n" + "=" * 70)
        logger.info("Query Performance Benchmark")
        logger.info("=" * 70)

        try:
            # Check if test data exists
            cursor.execute("SELECT COUNT(*) FROM etf_holdings")
            holdings_count = cursor.fetchone()[0]

            if holdings_count == 0:
                logger.warning("  ⚠️  No holdings data for benchmarking")
                logger.warning("  ⚠️  Run with --insert-test-data first")
                return False

            logger.info(f"  Dataset: {holdings_count:,} holdings")

            # Benchmark 1: Stock → ETF query
            logger.info("\n  [Query 1] Stock → ETF lookup (005930 Samsung Electronics)")
            start_time = time.time()
            cursor.execute("""
                SELECT etf_ticker, weight
                FROM etf_holdings
                WHERE stock_ticker = '005930'
                  AND as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
                ORDER BY weight DESC
            """)
            results = cursor.fetchall()
            elapsed = (time.time() - start_time) * 1000

            logger.info(f"    Results: {len(results)} ETFs")
            logger.info(f"    Time: {elapsed:.2f}ms")
            if elapsed < 10:
                logger.info(f"    ✅ Performance: EXCELLENT (<10ms)")
            elif elapsed < 50:
                logger.info(f"    ✓ Performance: GOOD (<50ms)")
            else:
                logger.warning(f"    ⚠️  Performance: SLOW (>50ms)")

            # Benchmark 2: ETF → Stock query
            logger.info("\n  [Query 2] ETF → Stock lookup (TIGER 200)")
            start_time = time.time()
            cursor.execute("""
                SELECT stock_ticker, weight, rank_in_etf
                FROM etf_holdings
                WHERE etf_ticker = '152100'
                  AND as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
                ORDER BY rank_in_etf ASC
            """)
            results = cursor.fetchall()
            elapsed = (time.time() - start_time) * 1000

            logger.info(f"    Results: {len(results)} stocks")
            logger.info(f"    Time: {elapsed:.2f}ms")
            if elapsed < 15:
                logger.info(f"    ✅ Performance: EXCELLENT (<15ms)")
            elif elapsed < 50:
                logger.info(f"    ✓ Performance: GOOD (<50ms)")
            else:
                logger.warning(f"    ⚠️  Performance: SLOW (>50ms)")

            # Benchmark 3: High-weight filter
            logger.info("\n  [Query 3] High-weight holdings (>5%)")
            start_time = time.time()
            cursor.execute("""
                SELECT etf_ticker, stock_ticker, weight
                FROM etf_holdings
                WHERE weight >= 5.0
                  AND as_of_date = (SELECT MAX(as_of_date) FROM etf_holdings)
                ORDER BY weight DESC
            """)
            results = cursor.fetchall()
            elapsed = (time.time() - start_time) * 1000

            logger.info(f"    Results: {len(results)} holdings")
            logger.info(f"    Time: {elapsed:.2f}ms")
            if elapsed < 50:
                logger.info(f"    ✅ Performance: EXCELLENT (<50ms)")
            else:
                logger.warning(f"    ⚠️  Performance: SLOW (>50ms)")

            return True

        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='ETF Holdings Schema Validation and Testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all validation checks
  python scripts/validate_etf_holdings_schema.py

  # Insert test data and run validation
  python scripts/validate_etf_holdings_schema.py --insert-test-data

  # Run query benchmarks
  python scripts/validate_etf_holdings_schema.py --benchmark-queries

  # Full test suite
  python scripts/validate_etf_holdings_schema.py --insert-test-data --benchmark-queries
        """
    )
    parser.add_argument(
        '--db-path',
        default='data/spock_local.db',
        help='SQLite database path (default: data/spock_local.db)'
    )
    parser.add_argument(
        '--insert-test-data',
        action='store_true',
        help='Insert test data before validation'
    )
    parser.add_argument(
        '--benchmark-queries',
        action='store_true',
        help='Run query performance benchmarks'
    )

    args = parser.parse_args()

    try:
        validator = ETFHoldingsSchemaValidator(db_path=args.db_path)

        # Insert test data if requested
        if args.insert_test_data:
            if not validator.insert_test_data():
                logger.error("\n❌ Test data insertion FAILED")
                sys.exit(1)

        # Run validation
        success = validator.validate_all()

        # Run benchmarks if requested
        if args.benchmark_queries:
            if not validator.benchmark_queries():
                logger.warning("\n⚠️  Query benchmarks could not be completed")

        if success:
            logger.info("\n✅ Validation completed successfully")
            sys.exit(0)
        else:
            logger.error("\n❌ Validation FAILED")
            sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
