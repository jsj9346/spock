#!/usr/bin/env python3
"""
Direct API call test to compare with dry run results
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv

load_dotenv()

CORP_CODES = {
    '051910': '00356361',  # LG Chem (OFFICIAL - was wrong before!)
    '005930': '00126380',  # Samsung
}

def test_lg_chem():
    """Test LG Chem data collection"""

    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    ticker = '051910'
    corp_code = CORP_CODES[ticker]

    print("="*80)
    print(f"Testing get_historical_fundamentals() for LG Chem")
    print("="*80)

    # Call the EXACT same method as backfill script
    metrics_list = dart.get_historical_fundamentals(
        ticker=ticker,
        corp_code=corp_code,
        start_year=2022,
        end_year=2024
    )

    print(f"\n📊 Collected {len(metrics_list)} years of data:\n")

    for metrics in metrics_list:
        year = metrics.get('fiscal_year', 'Unknown')
        revenue = metrics.get('revenue', 0)
        cogs = metrics.get('cogs', 0)
        ebitda = metrics.get('ebitda', 0)

        print(f"FY{year}:")
        print(f"  Revenue: {revenue:>25,.0f} won")
        print(f"  COGS:    {cogs:>25,.0f} won")
        print(f"  EBITDA:  {ebitda:>25,.0f} won")
        print()

def test_samsung():
    """Test Samsung 2022 data collection"""

    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    ticker = '005930'
    corp_code = CORP_CODES[ticker]

    print("="*80)
    print(f"Testing get_historical_fundamentals() for Samsung 2022")
    print("="*80)

    # Call the EXACT same method as backfill script
    metrics_list = dart.get_historical_fundamentals(
        ticker=ticker,
        corp_code=corp_code,
        start_year=2022,
        end_year=2022
    )

    print(f"\n📊 Collected {len(metrics_list)} years of data:\n")

    for metrics in metrics_list:
        year = metrics.get('fiscal_year', 'Unknown')
        revenue = metrics.get('revenue', 0)
        cogs = metrics.get('cogs', 0)
        ebitda = metrics.get('ebitda', 0)

        print(f"FY{year}:")
        print(f"  Revenue: {revenue:>25,.0f} won")
        print(f"  COGS:    {cogs:>25,.0f} won")
        print(f"  EBITDA:  {ebitda:>25,.0f} won")
        print()

        # Show all data
        print("All fields:")
        for key, value in sorted(metrics.items()):
            if value and value != 0:
                if isinstance(value, (int, float)):
                    print(f"  {key:30s}: {value:>25,.2f}")
                else:
                    print(f"  {key:30s}: {value}")

if __name__ == '__main__':
    print("\n### Test 1: LG Chem ###\n")
    test_lg_chem()

    print("\n### Test 2: Samsung 2022 ###\n")
    test_samsung()
