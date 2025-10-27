#!/usr/bin/env python3
"""
Database Maintenance Validation Script

Validates that all 4 database maintenance methods are operational:
1. cleanup_old_ohlcv_data()
2. vacuum_database()
3. analyze_database()
4. get_database_stats()

Usage:
    python3 scripts/validate_db_maintenance.py

Exit Codes:
    0: All validations passed
    1: One or more validations failed
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager


def validate_method_exists(db, method_name: str) -> bool:
    """Validate that a method exists on the database manager"""
    if not hasattr(db, method_name):
        print(f"❌ Method {method_name}() does not exist")
        return False

    if not callable(getattr(db, method_name)):
        print(f"❌ {method_name} exists but is not callable")
        return False

    print(f"✅ Method {method_name}() exists and is callable")
    return True


def validate_cleanup_old_ohlcv_data(db) -> bool:
    """Validate cleanup_old_ohlcv_data() method"""
    print("\n📋 Validating cleanup_old_ohlcv_data() method...")

    if not validate_method_exists(db, 'cleanup_old_ohlcv_data'):
        return False

    try:
        # Test with dry run (retention_days=10000 means no deletion)
        deleted = db.cleanup_old_ohlcv_data(retention_days=10000)

        if not isinstance(deleted, int):
            print(f"❌ cleanup_old_ohlcv_data() returned {type(deleted)}, expected int")
            return False

        if deleted < 0:
            print(f"❌ cleanup_old_ohlcv_data() returned negative value: {deleted}")
            return False

        print(f"✅ cleanup_old_ohlcv_data() validation passed (would delete {deleted} rows with 10000-day retention)")
        return True

    except Exception as e:
        print(f"❌ cleanup_old_ohlcv_data() failed: {e}")
        return False


def validate_vacuum_database(db) -> bool:
    """Validate vacuum_database() method"""
    print("\n🔧 Validating vacuum_database() method...")

    if not validate_method_exists(db, 'vacuum_database'):
        return False

    try:
        result = db.vacuum_database()

        if not isinstance(result, dict):
            print(f"❌ vacuum_database() returned {type(result)}, expected dict")
            return False

        required_keys = ['size_before_mb', 'size_after_mb', 'space_reclaimed_mb',
                        'space_reclaimed_pct', 'duration_seconds']

        for key in required_keys:
            if key not in result:
                print(f"❌ vacuum_database() result missing key: {key}")
                return False

        print(f"✅ vacuum_database() validation passed")
        print(f"   Size: {result['size_before_mb']:.2f} MB → {result['size_after_mb']:.2f} MB")
        print(f"   Reclaimed: {result['space_reclaimed_mb']:.2f} MB ({result['space_reclaimed_pct']:.1f}%)")
        print(f"   Duration: {result['duration_seconds']:.2f}s")
        return True

    except Exception as e:
        print(f"❌ vacuum_database() failed: {e}")
        return False


def validate_analyze_database(db) -> bool:
    """Validate analyze_database() method"""
    print("\n📊 Validating analyze_database() method...")

    if not validate_method_exists(db, 'analyze_database'):
        return False

    try:
        success = db.analyze_database()

        if not isinstance(success, bool):
            print(f"❌ analyze_database() returned {type(success)}, expected bool")
            return False

        if not success:
            print(f"❌ analyze_database() returned False (operation failed)")
            return False

        print(f"✅ analyze_database() validation passed")
        return True

    except Exception as e:
        print(f"❌ analyze_database() failed: {e}")
        return False


def validate_get_database_stats(db) -> bool:
    """Validate get_database_stats() method"""
    print("\n📈 Validating get_database_stats() method...")

    if not validate_method_exists(db, 'get_database_stats'):
        return False

    try:
        stats = db.get_database_stats()

        if not isinstance(stats, dict):
            print(f"❌ get_database_stats() returned {type(stats)}, expected dict")
            return False

        required_keys = [
            'db_path', 'db_size_mb', 'table_count', 'ohlcv_rows',
            'ticker_count', 'unique_regions', 'regions',
            'oldest_ohlcv_date', 'newest_ohlcv_date', 'data_retention_days'
        ]

        for key in required_keys:
            if key not in stats:
                print(f"❌ get_database_stats() result missing key: {key}")
                return False

        print(f"✅ get_database_stats() validation passed")
        print(f"   Database: {stats['db_path']}")
        print(f"   Size: {stats['db_size_mb']} MB")
        print(f"   OHLCV Rows: {stats['ohlcv_rows']:,}")
        print(f"   Tickers: {stats['ticker_count']:,}")
        print(f"   Regions: {stats['regions']}")
        print(f"   Retention: {stats['data_retention_days']} days")
        return True

    except Exception as e:
        print(f"❌ get_database_stats() failed: {e}")
        return False


def main():
    """Run all validation tests"""
    print("=" * 60)
    print("Database Maintenance Validation")
    print("=" * 60)

    try:
        db = SQLiteDatabaseManager()
        print(f"✅ SQLiteDatabaseManager initialized")
        print(f"   Database: {db.db_path}")
    except Exception as e:
        print(f"❌ Failed to initialize SQLiteDatabaseManager: {e}")
        return 1

    # Run all validations
    validations = [
        ("cleanup_old_ohlcv_data", validate_cleanup_old_ohlcv_data),
        ("vacuum_database", validate_vacuum_database),
        ("analyze_database", validate_analyze_database),
        ("get_database_stats", validate_get_database_stats),
    ]

    results = []
    for name, validator in validations:
        result = validator(db)
        results.append((name, result))

    # Print summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}()")

    print(f"\nTotal: {passed}/{total} validations passed")

    if passed == total:
        print("\n🎉 All database maintenance methods are operational!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
