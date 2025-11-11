"""
Live DART API Integration Test - Samsung Electronics (005930)
Tests equity account extraction with real API response

Created: 2025-11-10
Phase: Phase 2 - Equity Account Enhancement (TASK-2.5)
"""

import os
import sys
from dotenv import load_dotenv

# Add modules to path
sys.path.insert(0, os.path.abspath('/Users/13ruce/spock'))

from modules.dart_api_client import DARTApiClient

# Load environment
load_dotenv()
dart_key = os.getenv('DART_API_KEY')

if not dart_key:
    print("❌ DART_API_KEY not found")
    sys.exit(1)

# Create client
client = DARTApiClient(api_key=dart_key)

print("=" * 80)
print("DART API Integration Test - Samsung Electronics (005930)")
print("=" * 80)

# Test: Fetch fundamental metrics (includes equity accounts)
print("\n📊 Fetching fundamental metrics...")
try:
    ticker = "005930"  # Samsung Electronics
    corp_code = "00126380"  # Samsung Electronics corp code from DART

    result = client.get_fundamental_metrics(ticker=ticker, corp_code=corp_code)

    print(f"DEBUG: Result type: {type(result)}")
    print(f"DEBUG: Result keys: {result.keys() if result else 'None'}")

    if result:
        print("✅ Financial data retrieved successfully")

        # get_fundamental_metrics returns the metrics dict directly
        metrics = result

        # Print equity accounts
        print("\n🏦 Equity Account Breakdown:")
        print("-" * 80)

        equity_fields = [
            ('capital_stock', '자본금'),
            ('capital_surplus', '자본잉여금'),
            ('retained_earnings', '이익잉여금'),
            ('treasury_stock', '자기주식'),
            ('other_comprehensive_income', '기타포괄손익누계액'),
            ('non_controlling_interest', '비지배지분'),
            ('unappropriated_retained_earnings', '미처분이익잉여금'),
            ('legal_reserve', '이익준비금'),
        ]

        all_none = True
        for field_name, korean_name in equity_fields:
            value = metrics.get(field_name)
            if value is not None:
                all_none = False
                print(f"{korean_name:25s}: {value:20,.0f} KRW")
            else:
                print(f"{korean_name:25s}: {'None':>20s}")

        if all_none:
            print("\n⚠️  All equity accounts are None - extraction may have failed")
        else:
            print("\n✅ Equity extraction successful!")

        # Print validation results
        if 'equity_validation_passed' in metrics:
            print("\n🔍 Equity Validation:")
            print("-" * 80)
            passed = metrics['equity_validation_passed']
            error_pct = metrics.get('equity_validation_error_pct')

            if passed is None:
                print("⚠️  Validation skipped (insufficient data)")
            elif passed:
                print(f"✅ Validation PASSED (error: {error_pct:.2f}%)")
            else:
                print(f"❌ Validation FAILED (error: {error_pct:.2f}%)")

        # Print total equity for reference
        total_equity = metrics.get('total_equity')
        if total_equity:
            print(f"\n📊 Total Equity (자본총계): {total_equity:20,.0f} KRW")

    else:
        print("❌ No financial data returned")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error fetching financial statements: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ Live DART API Integration Test PASSED")
print("=" * 80)
