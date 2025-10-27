#!/usr/bin/env python3
"""
Net Income Parsing Investigation Script

Purpose: Analyze DART API XML structure for Net Income field variations
Focus: Samsung Electronics (005930) FY2024 annual report
"""

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.dart_api_client import DARTApiClient
import os
from dotenv import load_dotenv
import xml.etree.ElementTree as ET

load_dotenv()

# Initialize DART client
dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))

# Samsung Electronics
ticker = '005930'
corp_code = '00126380'
year = 2024

print("=" * 100)
print(f"🔍 Net Income Parsing Investigation - {ticker} (Samsung Electronics) FY{year}")
print("=" * 100)
print()

# Step 1: Get 2024 annual report
print(f"Step 1: Fetching {year} annual report from DART API...")
print("-" * 100)

# Use get_historical_fundamentals which returns a list of metrics
results = dart.get_historical_fundamentals(
    ticker=ticker,
    corp_code=corp_code,
    start_year=year,
    end_year=year
)

if not results:
    print(f"❌ No annual report found for {year}")
    sys.exit(1)

# Get the first (and only) year's data
metrics = results[0]

print(f"✅ Annual report retrieved")
print(f"   Revenue: {metrics.get('revenue', 0):,.0f} KRW")
print(f"   Operating Profit: {metrics.get('operating_profit', 0):,.0f} KRW")
print(f"   Net Income: {metrics.get('net_income', 0):,.0f} KRW")
print(f"   EBITDA: {metrics.get('ebitda', 0):,.0f} KRW")
print()

# Get the raw XML response for detailed analysis
# We need to call the internal method directly
report_data = dart._get_report_xml(corp_code, year, '11011')

if not report_data:
    print(f"❌ Could not get raw XML")
    sys.exit(1)

# Step 2: Parse XML and find all financial statement items
print(f"Step 2: Analyzing XML structure for financial statement items...")
print("-" * 100)

try:
    root = ET.fromstring(report_data)

    # Find all list elements (financial statement items)
    items = root.findall('.//list')

    print(f"📊 Found {len(items)} financial statement items")
    print()

    # Step 3: Search for Net Income related fields
    print("Step 3: Searching for Net Income related fields...")
    print("-" * 100)

    net_income_keywords = [
        '당기순이익',
        '순이익',
        '당기순손익',
        '당기net',
        '지배기업',
        '연결당기순이익',
        '별도당기순이익',
        '포괄손익',
        'net income',
        'profit',
    ]

    net_income_candidates = []

    for item in items:
        account_nm = item.find('account_nm')
        if account_nm is not None and account_nm.text:
            account_name = account_nm.text.strip()

            # Check if this field contains Net Income keywords
            for keyword in net_income_keywords:
                if keyword.lower() in account_name.lower():
                    # Get the value
                    thstrm_amount = item.find('thstrm_amount')
                    value = thstrm_amount.text if thstrm_amount is not None else 'N/A'

                    net_income_candidates.append({
                        'account_nm': account_name,
                        'value': value,
                        'keyword': keyword
                    })
                    break

    print(f"✅ Found {len(net_income_candidates)} Net Income candidate fields:")
    print()

    if net_income_candidates:
        for i, candidate in enumerate(net_income_candidates, 1):
            print(f"{i}. Account Name: {candidate['account_nm']}")
            print(f"   Value: {candidate['value']}")
            print(f"   Matched Keyword: {candidate['keyword']}")
            print()
    else:
        print("⚠️  No Net Income fields found with known keywords")
        print()
        print("Showing first 20 account names for manual inspection:")
        for i, item in enumerate(items[:20], 1):
            account_nm = item.find('account_nm')
            if account_nm is not None:
                print(f"{i}. {account_nm.text}")
        print()

    # Step 4: Compare with current parsing logic
    print("Step 4: Current parsing logic in dart_api_client.py")
    print("-" * 100)

    current_patterns = [
        '당기순이익',
        '당기순이익(손실)',
        '지배기업 소유주지분 당기순이익',
    ]

    print("Current Net Income field patterns:")
    for pattern in current_patterns:
        print(f"  - {pattern}")
    print()

    # Step 5: Recommendations
    print("Step 5: Recommendations")
    print("-" * 100)

    if net_income_candidates:
        # Find exact match
        exact_matches = [c for c in net_income_candidates if '당기순이익' in c['account_nm'] and c['value'] != 'N/A']

        if exact_matches:
            print("✅ Found exact matches with '당기순이익':")
            for match in exact_matches:
                print(f"   - {match['account_nm']}: {match['value']}")
            print()
            print("🔧 RECOMMENDATION: Current parsing logic should work")
            print("   → Issue may be in field matching or value extraction logic")
        else:
            print("⚠️  No exact '당기순이익' match found")
            print()
            print("🔧 RECOMMENDATION: Add these field patterns:")
            for candidate in net_income_candidates[:5]:
                if candidate['account_nm'] not in current_patterns:
                    print(f"   - {candidate['account_nm']}")
    else:
        print("❌ No Net Income fields found in DART API response")
        print()
        print("🔧 RECOMMENDATION:")
        print("   1. Check if FY2024 annual report is fully published in DART")
        print("   2. Manually inspect DART website for report availability")
        print("   3. Consider using quarterly reports instead")

    print()
    print("=" * 100)
    print("Investigation Complete!")
    print("=" * 100)

except ET.ParseError as e:
    print(f"❌ XML Parsing Error: {e}")
    print()
    print("Raw response (first 1000 chars):")
    print(report_data[:1000])
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
