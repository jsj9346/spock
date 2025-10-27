#!/usr/bin/env python3
"""
Test DART API Phase 2 Field Parsing

Purpose: Verify that Phase 2 financial statement items are correctly parsed from DART API responses.

Tests:
1. Fetch Samsung (005930) 2023 annual report
2. Display all available account names (계정명)
3. Check if Phase 2 target fields exist
4. Display actual values for Phase 2 fields

Usage:
    python3 tests/test_dart_phase2_parsing.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv
import json

load_dotenv()

def test_samsung_2023_annual_report():
    """Test Samsung 2023 annual report parsing"""

    # Initialize DART API client
    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found in environment")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    # Samsung corp_code
    SAMSUNG_CORP_CODE = '00126380'
    SAMSUNG_TICKER = '005930'

    print("="*80)
    print("🧪 DART API Phase 2 Field Parsing Test")
    print("="*80)
    print(f"Ticker: {SAMSUNG_TICKER} (Samsung Electronics)")
    print(f"Corp Code: {SAMSUNG_CORP_CODE}")
    print(f"Year: 2023")
    print(f"Report Type: Annual (11011)")
    print("="*80)

    # Fetch 2023 annual report - USE fnlttSinglAcntAll for ALL account items
    params = {
        'corp_code': SAMSUNG_CORP_CODE,
        'bsns_year': 2023,
        'reprt_code': '11011',
        'fs_div': 'OFS'  # OFS=개별재무제표, CFS=연결재무제표
    }

    try:
        response = dart._make_request('fnlttSinglAcntAll.json', params)
        data = response.json()

        if data['status'] != '000':
            print(f"❌ API Error: {data.get('message', 'Unknown error')}")
            return

        items = data.get('list', [])
        if not items:
            print("❌ No financial data returned")
            return

        print(f"✅ Fetched {len(items)} financial statement items\n")

        # Create item_lookup like the parsing method does
        item_lookup = {}
        for item in items:
            account_name = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0').replace(',', '')
            try:
                item_lookup[account_name] = float(amount)
            except (ValueError, TypeError):
                pass

        print("="*80)
        print("📋 Phase 2 Target Fields Check")
        print("="*80)

        # Phase 2 target fields (18 items)
        phase2_targets = {
            'Manufacturing (6)': [
                '매출원가',
                '유형자산',
                '감가상각비',
                '매출채권',
                '감가상각누계액'
            ],
            'Retail/E-Commerce (3)': [
                '판매비와관리비',
                '연구개발비'
            ],
            'Financial (5)': [
                '이자수익',
                '이자비용',
                '대출금',
                '부실채권',
                '고정이하여신'
            ],
            'Common (4)': [
                '투자활동현금흐름',
                '재무활동현금흐름'
            ]
        }

        found_fields = []
        missing_fields = []

        for category, fields in phase2_targets.items():
            print(f"\n{category}:")
            for field in fields:
                if field in item_lookup:
                    value = item_lookup[field]
                    print(f"  ✅ {field}: {value:,.0f}")
                    found_fields.append(field)
                else:
                    print(f"  ❌ {field}: NOT FOUND")
                    missing_fields.append(field)

        print("\n" + "="*80)
        print("📊 Summary")
        print("="*80)
        print(f"Found: {len(found_fields)}/{len(found_fields) + len(missing_fields)} fields")
        print(f"Missing: {len(missing_fields)} fields")

        if missing_fields:
            print("\n⚠️ Missing Fields:")
            for field in missing_fields:
                print(f"  - {field}")

            # Search for similar account names
            print("\n🔍 Searching for similar account names...")
            for missing in missing_fields:
                # Extract key words from missing field
                key_words = missing.replace('/', '').split()

                print(f"\n  Searching for '{missing}':")
                matches = []
                for account_name in item_lookup.keys():
                    # Check if any key word is in the account name
                    for word in key_words:
                        if word in account_name:
                            matches.append(account_name)
                            break

                if matches:
                    for match in matches[:5]:  # Show top 5 matches
                        print(f"    - {match}: {item_lookup[match]:,.0f}")
                else:
                    print(f"    No similar names found")

        # Display all unique account names for reference
        print("\n" + "="*80)
        print("📄 All Available Account Names (first 50)")
        print("="*80)
        account_names = sorted(item_lookup.keys())
        for i, name in enumerate(account_names[:50], 1):
            value = item_lookup[name]
            print(f"{i:3d}. {name}: {value:,.0f}")

        if len(account_names) > 50:
            print(f"\n... and {len(account_names) - 50} more accounts")

        # Test calculated fields
        print("\n" + "="*80)
        print("🧮 Calculated Fields Test")
        print("="*80)

        revenue = item_lookup.get('매출액', 0)
        cogs = item_lookup.get('매출원가', 0)
        operating_profit = item_lookup.get('영업이익', 0)
        depreciation = item_lookup.get('감가상각비', 0)

        print(f"Revenue (매출액): {revenue:,.0f}")
        print(f"COGS (매출원가): {cogs:,.0f}")
        print(f"Operating Profit (영업이익): {operating_profit:,.0f}")
        print(f"Depreciation (감가상각비): {depreciation:,.0f}")

        gross_profit = revenue - cogs if revenue > 0 and cogs > 0 else 0
        ebitda = operating_profit + depreciation if operating_profit > 0 and depreciation > 0 else 0

        print(f"\nCalculated:")
        print(f"  Gross Profit: {gross_profit:,.0f}")
        print(f"  EBITDA: {ebitda:,.0f}")

        if gross_profit == 0:
            print("  ⚠️ Gross Profit is 0 - likely missing COGS data")
        if ebitda == 0:
            print("  ⚠️ EBITDA is 0 - likely missing depreciation data")

        print("\n" + "="*80)
        print("✅ Test Complete")
        print("="*80)

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_samsung_2023_annual_report()
