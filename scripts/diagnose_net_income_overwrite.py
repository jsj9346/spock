#!/usr/bin/env python3
"""
Diagnose Net Income Overwrite Issue

Purpose: Show how item_lookup dictionary handles duplicate account names
Reproduce the exact logic from dart_api_client.py to identify the bug
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
print(f"Net Income Overwrite Diagnosis - Samsung Electronics (005930) FY{year}")
print("=" * 100)
print()

# Call DART API (same parameters as backfill)
url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
params = {
    'crtfc_key': api_key,
    'corp_code': corp_code,
    'bsns_year': year,
    'reprt_code': '11011',  # Annual
    'fs_div': 'CFS'  # Consolidated
}

response = requests.get(url, params=params, timeout=30)
data = response.json()

if data['status'] != '000':
    print(f"❌ Error: {data.get('message', 'Unknown error')}")
    sys.exit(1)

items = data.get('list', [])
print(f"Total items from DART API: {len(items)}")
print()

# Reproduce exact logic from dart_api_client.py (lines 512-519)
print("=" * 100)
print("STEP 1: Create item_lookup dictionary (reproducing dart_api_client.py logic)")
print("=" * 100)
print()

item_lookup = {}
net_income_entries = []  # Track all '당기순이익' entries

for i, item in enumerate(items):
    account_name = item.get('account_nm', '')
    amount = item.get('thstrm_amount', '0').replace(',', '')

    # Track Net Income entries specifically
    if account_name == '당기순이익':
        try:
            value = float(amount)
            net_income_entries.append({
                'index': i,
                'account_nm': account_name,
                'value': value,
                'sj_div': item.get('sj_div', ''),  # Statement division (BS, IS, CF)
                'account_id': item.get('account_id', '')
            })
            print(f"Found '당기순이익' at index {i}: {value:,.0f} KRW (sj_div={item.get('sj_div', 'N/A')})")
        except (ValueError, TypeError):
            pass

    # Create item_lookup (last value wins for duplicates)
    try:
        item_lookup[account_name] = float(amount)
    except (ValueError, TypeError):
        pass

print()
print(f"Total '당기순이익' entries found: {len(net_income_entries)}")
print()

# Check what value ended up in item_lookup
final_net_income = item_lookup.get('당기순이익', 0)

print("=" * 100)
print("STEP 2: Current parsing logic result")
print("=" * 100)
print()

# Reproduce line 548 from dart_api_client.py
net_income = item_lookup.get('당기순이익(손실)', 0) or item_lookup.get('당기순이익', 0)

print(f"item_lookup['당기순이익'] = {final_net_income:,.0f} KRW")
print(f"net_income (from current logic) = {net_income:,.0f} KRW")
print()

# Identify which entry was used
if net_income_entries:
    last_entry = net_income_entries[-1]
    if last_entry['value'] == final_net_income:
        print(f"✅ item_lookup used LAST occurrence (index {last_entry['index']})")
    else:
        print(f"⚠️ item_lookup value doesn't match last entry - unexpected behavior")

    print()
    print("All '당기순이익' entries (in API response order):")
    for entry in net_income_entries:
        is_final = " ← FINAL VALUE in item_lookup" if entry['value'] == final_net_income else ""
        print(f"  Index {entry['index']:3d}: {entry['value']:20,.0f} KRW (sj_div={entry['sj_div']}){is_final}")

print()
print("=" * 100)
print("STEP 3: Root Cause Analysis")
print("=" * 100)
print()

if final_net_income == 0:
    print("❌ ROOT CAUSE: item_lookup['당기순이익'] = 0")
    print()
    print("Possible reasons:")
    print("1. Last '당기순이익' entry in API response has value 0")
    print("2. All '당기순이익' entries have non-numeric values (parsing failed)")
    print("3. DART API returned different data during backfill")
    print()
elif final_net_income != 34_451_351_000_000:  # Expected Samsung 2024 net income
    print(f"⚠️ WARNING: item_lookup['당기순이익'] = {final_net_income:,.0f} KRW")
    print(f"   Expected: ~34,451,351,000,000 KRW (from consolidated income statement)")
    print()
    print("ROOT CAUSE: Dictionary overwrite issue")
    print("- Multiple '당기순이익' entries exist in DART API response")
    print("- item_lookup dictionary only keeps LAST occurrence")
    print("- LAST occurrence is not the correct consolidated net income value")
    print()
else:
    print("✅ CURRENT LOGIC WORKS: item_lookup['당기순이익'] has correct value")
    print()
    print("If database shows net_income = 0, the issue is elsewhere:")
    print("1. Check database UPSERT logic")
    print("2. Check if value is being zeroed out after parsing")
    print("3. Check logs from actual backfill execution")

print()
print("=" * 100)
print("RECOMMENDATION:")
print("=" * 100)
print()

if final_net_income == 0 or (final_net_income > 0 and final_net_income < 10_000_000_000_000):
    print("Fix: Filter item_lookup creation to use only Income Statement items")
    print()
    print("Modified logic (dart_api_client.py lines 512-519):")
    print()
    print("item_lookup = {}")
    print("for item in items:")
    print("    account_name = item.get('account_nm', '')")
    print("    amount = item.get('thstrm_amount', '0').replace(',', '')")
    print("    sj_div = item.get('sj_div', '')  # Statement division")
    print()
    print("    # Only use first occurrence OR filter by statement type")
    print("    if account_name not in item_lookup:")
    print("        try:")
    print("            item_lookup[account_name] = float(amount)")
    print("        except (ValueError, TypeError):")
    print("            pass")
    print()
    print("OR use sj_div filter:")
    print("    # sj_div: 'BS'=Balance Sheet, 'IS'=Income Statement, 'CF'=Cash Flow")
    print("    if account_name == '당기순이익' and sj_div == 'IS':")
    print("        item_lookup[account_name] = float(amount)")
else:
    print("Current logic appears correct. Issue may be in database layer or UPSERT logic.")

print()
