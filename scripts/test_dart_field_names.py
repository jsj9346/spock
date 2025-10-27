#!/usr/bin/env python3
"""
Simple DART API Field Name Inspector

Purpose: List ALL field names from Samsung 2024 annual report
"""

import sys
sys.path.insert(0, '/Users/13ruce/spock')

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('DART_API_KEY')
corp_code = '00126380'  # Samsung
year = 2024

print("=" * 100)
print(f"DART API Field Names - Samsung Electronics (005930) FY{year}")
print("=" * 100)
print()

# Call DART API directly
url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
params = {
    'crtfc_key': api_key,
    'corp_code': corp_code,
    'bsns_year': year,
    'reprt_code': '11011',  # Annual
    'fs_div': 'CFS'  # Consolidated
}

print(f"Fetching: {url}")
print(f"Params: corp_code={corp_code}, year={year}, report=11011, fs=CFS")
print()

response = requests.get(url, params=params, timeout=30)
data = response.json()

if data['status'] != '000':
    print(f"❌ Error: {data.get('message', 'Unknown error')}")
    sys.exit(1)

items = data.get('list', [])
print(f"✅ Retrieved {len(items)} financial statement items")
print()

# Search for Net Income related fields
net_income_keywords = ['순이익', '손익', 'profit', 'income']

print("=" * 100)
print("NET INCOME CANDIDATE FIELDS:")
print("=" * 100)
print()

found_candidates = []

for item in items:
    account_nm = item.get('account_nm', '')
    amount = item.get('thstrm_amount', '0')

    # Check if this field contains Net Income keywords
    for keyword in net_income_keywords:
        if keyword in account_nm.lower():
            # Convert amount to number
            try:
                value = float(amount.replace(',', ''))
                if value != 0:  # Only show non-zero values
                    found_candidates.append({
                        'name': account_nm,
                        'value': value,
                        'keyword': keyword
                    })
            except:
                pass
            break

# Sort by absolute value (largest first)
found_candidates.sort(key=lambda x: abs(x['value']), reverse=True)

if found_candidates:
    for i, candidate in enumerate(found_candidates, 1):
        print(f"{i}. '{candidate['name']}'")
        print(f"   Value: {candidate['value']:,.0f} KRW")
        print(f"   Matched: {candidate['keyword']}")
        print()
else:
    print("⚠️  No Net Income fields found")
    print()

print("=" * 100)
print("CURRENT PARSING LOGIC:")
print("=" * 100)
print()
print("Line 548 in dart_api_client.py:")
print("  net_income = item_lookup.get('당기순이익(손실)', 0) or item_lookup.get('당기순이익', 0)")
print()

# Check if current patterns would match
current_patterns = ['당기순이익(손실)', '당기순이익']
matched = [c for c in found_candidates if c['name'] in current_patterns]
unmatched = [c for c in found_candidates if c['name'] not in current_patterns]

if matched:
    print("✅ MATCHED by current logic:")
    for m in matched:
        print(f"   - '{m['name']}': {m['value']:,.0f} KRW")
    print()

if unmatched:
    print("❌ NOT MATCHED (missing patterns):")
    for m in unmatched:
        print(f"   - '{m['name']}': {m['value']:,.0f} KRW")
    print()

print("=" * 100)
print("RECOMMENDATION:")
print("=" * 100)
print()

if unmatched:
    print("Add these field patterns to dart_api_client.py line 548:")
    print()
    print("net_income = (")
    for pattern in current_patterns:
        print(f"    item_lookup.get('{pattern}', 0) or")
    for m in unmatched[:5]:  # Show top 5 missing patterns
        print(f"    item_lookup.get('{m['name']}', 0) or")
    print("    0")
    print(")")
else:
    print("Current parsing logic should work. Issue may be elsewhere.")

print()
