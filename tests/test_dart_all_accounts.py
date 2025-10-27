#!/usr/bin/env python3
"""
Quick test to show ALL account names from DART API response
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv

load_dotenv()

dart_api_key = os.getenv('DART_API_KEY')
dart = DARTApiClient(api_key=dart_api_key)

# Samsung 2023 annual report
params = {
    'corp_code': '00126380',
    'bsns_year': 2023,
    'reprt_code': '11011',
    'fs_div': 'OFS'
}

response = dart._make_request('fnlttSinglAcntAll.json', params)
data = response.json()
items = data.get('list', [])

print(f"Total items: {len(items)}\n")
print("="*80)
print("ALL Account Names (계정명)")
print("="*80)

# Create lookup
item_lookup = {}
for item in items:
    account_name = item.get('account_nm', '')
    amount = item.get('thstrm_amount', '0').replace(',', '')
    try:
        item_lookup[account_name] = float(amount)
    except (ValueError, TypeError):
        pass

# Sort and display all
for i, (name, value) in enumerate(sorted(item_lookup.items()), 1):
    print(f"{i:3d}. {name}: {value:,.0f}")

print("\n" + "="*80)
print("Search for missing Phase 2 fields:")
print("="*80)

# Missing fields
missing = [
    '감가상각비',
    '감가상각누계액',
    '연구개발비',
    '이자수익',
    '이자비용',
    '대출금',
    '부실채권',
    '고정이하여신'
]

print("\nExact matches:")
for field in missing:
    if field in item_lookup:
        print(f"✅ {field}: {item_lookup[field]:,.0f}")
    else:
        print(f"❌ {field}: NOT FOUND")

print("\nSearching for partial matches...")
for field in missing:
    key_words = field.split()
    matches = []
    for account_name in item_lookup.keys():
        for word in key_words:
            if word in account_name:
                matches.append((account_name, item_lookup[account_name]))
                break

    if matches:
        print(f"\n'{field}' - possible matches:")
        for match_name, match_value in matches[:10]:
            print(f"  - {match_name}: {match_value:,.0f}")
    else:
        print(f"\n'{field}' - no matches found")
