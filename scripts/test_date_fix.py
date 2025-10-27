#!/usr/bin/env python3
"""
Quick test script to verify DART API client date field fix
"""

import sys
sys.path.insert(0, '/Users/13ruce/spock')

from modules.dart_api_client import DARTApiClient
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize DART client
dart = DARTApiClient(api_key=os.getenv('DART_API_KEY'))

# Test Samsung Electronics (005930)
ticker = '005930'
corp_code = '00126380'  # Samsung Electronics corp_code

print(f"Testing date field fix for {ticker}...")
print("=" * 80)

# Test historical fundamentals (FY2022-2024)
results = dart.get_historical_fundamentals(
    ticker=ticker,
    corp_code=corp_code,
    start_year=2022,
    end_year=2024
)

if results:
    for metrics in results:
        year = metrics.get('fiscal_year', 'UNKNOWN')
        date = metrics.get('date', 'MISSING')
        data_source = metrics.get('data_source', 'MISSING')
        revenue = metrics.get('revenue', 0)

        # Expected date for annual report
        expected_date = f"{year}-12-31"

        print(f"\n📅 FY{year}:")
        if date == expected_date:
            print(f"  ✅ Date field CORRECT: date='{date}' (expected '{expected_date}')")
        else:
            print(f"  ❌ Date field WRONG: date='{date}' (expected '{expected_date}')")

        print(f"     data_source={data_source}, revenue={revenue:,.0f} KRW")
else:
    print("  ⚠️  No data retrieved")

print("\n" + "=" * 80)
print("Date fix verification complete!")
