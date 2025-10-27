#!/usr/bin/env python3
"""
Test with official DART corp_code for LG Chem
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv

load_dotenv()

dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))

print("="*80)
print("Testing LG Chem with OFFICIAL corp_code from DART XML")
print("="*80)

# Official corp_code from DART XML
official_corp_code = '00356361'

print(f"\n📊 LG Chem (051910) with corp_code='{official_corp_code}':")
print("-"*80)

metrics_list = dart.get_historical_fundamentals(
    ticker='051910',
    corp_code=official_corp_code,
    start_year=2022,
    end_year=2024
)

if metrics_list:
    for metrics in metrics_list:
        year = metrics.get('fiscal_year')
        revenue = metrics.get('revenue', 0)
        cogs = metrics.get('cogs', 0)
        ebitda = metrics.get('ebitda', 0)

        print(f"FY{year}: Revenue={revenue/1e12:.1f}T, COGS={cogs/1e12:.1f}T, EBITDA={ebitda/1e12:.1f}T")
else:
    print("❌ No data returned")

# Compare with wrong corp_code
print(f"\n📊 Comparison: Testing with WRONG corp_code '00164742':")
print("-"*80)

wrong_corp_code = '00164742'
metrics_list2 = dart.get_historical_fundamentals(
    ticker='051910',
    corp_code=wrong_corp_code,
    start_year=2023,
    end_year=2023
)

if metrics_list2:
    metrics = metrics_list2[0]
    revenue = metrics.get('revenue', 0)
    cogs = metrics.get('cogs', 0)
    print(f"FY2023: Revenue={revenue/1e12:.1f}T, COGS={cogs/1e12:.1f}T")
    print(f"\n⚠️ NOTE: This corp_code returns data but it's NOT LG Chem's official code!")
else:
    print("❌ No data returned")

# Search for what company 00164742 is
print(f"\n🔍 Identifying what company corp_code='00164742' belongs to:")
print("-"*80)

xml_path = dart.download_corp_codes()
corp_data = dart.parse_corp_codes(xml_path)

for name, data in corp_data.items():
    if data.get('corp_code') == '00164742':
        print(f"  Company name: {name}")
        print(f"  Stock code: {data.get('stock_code')}")
        print(f"  Corp code: {data.get('corp_code')}")
        break
