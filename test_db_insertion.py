"""
Test database insertion with equity columns

Tests that equity account data is correctly saved to the database.

Created: 2025-11-10
Phase: Phase 2 - Equity Account Enhancement (TASK-2.6)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add modules to path
sys.path.insert(0, os.path.abspath('/Users/13ruce/spock'))

from modules.db_manager_postgres import PostgresDatabaseManager

# Load environment
load_dotenv()

print("=" * 80)
print("Database Insertion Test - Equity Columns")
print("=" * 80)

# Connect to staging database
print("\n📊 Connecting to staging database...")
db = PostgresDatabaseManager(
    database="quant_platform_staging",
    user=os.getenv('POSTGRES_USER', 'bruce'),
    password=os.getenv('POSTGRES_PASSWORD', ''),
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', 5432))
)

# Test data with equity accounts (Samsung Electronics sample)
test_data = {
    'ticker': '005930',
    'region': 'KR',
    'date': datetime(2024, 6, 30).date(),  # 2024 Q2
    'period_type': 'QUARTERLY',
    'shares_outstanding': None,
    'market_cap': None,
    'close_price': None,
    'per': None,
    'pbr': None,
    'psr': None,
    'pcr': None,
    'ev': None,
    'ev_ebitda': None,
    'dividend_yield': None,
    'dividend_per_share': None,
    # Equity accounts (Phase 2)
    'capital_stock': 897514000000.0,
    'capital_surplus': 4403893000000.0,
    'retained_earnings': 375605244000000.0,
    'treasury_stock': None,
    'other_comprehensive_income': 7787466000000.0,
    'non_controlling_interest': 10867850000000.0,
    'unappropriated_retained_earnings': None,
    'legal_reserve': None,
    'data_source': 'DART_API_TEST'
}

print("\n📝 Test data prepared:")
print(f"  Ticker: {test_data['ticker']}")
print(f"  Date: {test_data['date']}")
print(f"  Period: {test_data['period_type']}")
print(f"  Equity columns: 5 non-null values")

# Insert test data
print("\n💾 Inserting test data...")
try:
    success = db.insert_fundamentals(test_data)

    if success:
        print("✅ Data inserted successfully")
    else:
        print("❌ Insertion failed")
        sys.exit(1)

except Exception as e:
    print(f"❌ Insertion error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify insertion
print("\n🔍 Verifying data...")
try:
    results = db.get_fundamentals(
        ticker=test_data['ticker'],
        region=test_data['region'],
        period_type=test_data['period_type']
    )

    if results and len(results) > 0:
        result = results[0]  # Get most recent
        print("✅ Data found in database")
        print("\n📊 Equity Account Verification:")
        print("-" * 80)

        equity_fields = [
            ('capital_stock', result.get('capital_stock'), test_data['capital_stock']),
            ('capital_surplus', result.get('capital_surplus'), test_data['capital_surplus']),
            ('retained_earnings', result.get('retained_earnings'), test_data['retained_earnings']),
            ('treasury_stock', result.get('treasury_stock'), test_data['treasury_stock']),
            ('other_comprehensive_income', result.get('other_comprehensive_income'), test_data['other_comprehensive_income']),
            ('non_controlling_interest', result.get('non_controlling_interest'), test_data['non_controlling_interest']),
            ('unappropriated_retained_earnings', result.get('unappropriated_retained_earnings'), test_data['unappropriated_retained_earnings']),
            ('legal_reserve', result.get('legal_reserve'), test_data['legal_reserve']),
        ]

        all_match = True
        for field_name, db_value, expected_value in equity_fields:
            match = "✅" if db_value == expected_value else "❌"
            if db_value != expected_value:
                all_match = False

            if expected_value is not None:
                print(f"{match} {field_name:30s}: {db_value:20,.0f} (expected {expected_value:,.0f})")
            else:
                print(f"{match} {field_name:30s}: {db_value} (expected None)")

        if all_match:
            print("\n✅ All equity accounts match!")
        else:
            print("\n❌ Some equity accounts don't match")
            sys.exit(1)

    else:
        print("❌ Data not found in database")
        sys.exit(1)

except Exception as e:
    print(f"❌ Verification error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ Database Insertion Test PASSED")
print("=" * 80)
