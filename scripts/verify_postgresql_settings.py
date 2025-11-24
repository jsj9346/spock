#!/usr/bin/env python3
"""
Verify PostgreSQL Settings After Phase 2 Optimization

Checks if optimized settings were applied correctly.

Author: Quant Investment Platform
Date: 2025-11-23
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager

def verify_settings():
    """Verify PostgreSQL settings"""
    db = PostgresDatabaseManager()

    settings_to_check = {
        'shared_buffers': '6GB',
        'work_mem': '204MB',
        'random_page_cost': '1.1',
        'max_parallel_workers': '10',
        'synchronous_commit': 'off',
        'effective_cache_size': '12GB',
        'max_connections': '60'
    }

    print("="*80)
    print("PostgreSQL Settings Verification")
    print("="*80)
    print()

    all_correct = True

    for setting, expected in settings_to_check.items():
        query = f"SHOW {setting}"
        result = db.execute_query(query)

        if result:
            actual = result[0][setting]
            status = "✅" if str(actual) == expected else "⚠️"

            if str(actual) != expected:
                all_correct = False

            print(f"{status} {setting:30s} Expected: {expected:15s} Actual: {actual}")
        else:
            print(f"❌ {setting:30s} Failed to read")
            all_correct = False

    print()
    print("="*80)

    if all_correct:
        print("✅ All settings applied correctly!")
    else:
        print("⚠️ Some settings differ from expected values")
        print("   This may be due to PostgreSQL auto-adjusting values")

    print("="*80)

    return all_correct

if __name__ == '__main__':
    verify_settings()
