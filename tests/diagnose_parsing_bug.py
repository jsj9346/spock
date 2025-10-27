#!/usr/bin/env python3
"""
Diagnostic script to trace DART API parsing discrepancy

Compares results from:
1. Direct get_historical_fundamentals() call
2. Step-by-step manual parsing of raw DART API response

Purpose: Identify where data is lost/corrupted in parsing pipeline
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv
import json

load_dotenv()

CORP_CODES = {
    '051910': '00356361',  # LG Chem (OFFICIAL - was wrong before!)
    '005930': '00126380',  # Samsung
}

def diagnose_lg_chem_2023():
    """Deep dive into LG Chem 2023 parsing"""

    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    ticker = '051910'
    corp_code = CORP_CODES[ticker]
    year = 2023

    print("="*80)
    print(f"🔍 Diagnostic: LG Chem 2023 DART API Parsing")
    print("="*80)

    # Step 1: Call the full method (what backfill script uses)
    print("\n📦 Step 1: Call get_historical_fundamentals() (backfill method)")
    print("-"*80)

    metrics_list = dart.get_historical_fundamentals(
        ticker=ticker,
        corp_code=corp_code,
        start_year=year,
        end_year=year
    )

    if metrics_list:
        metrics = metrics_list[0]
        print(f"  Revenue: {metrics.get('revenue', 0):>25,.0f} won")
        print(f"  COGS:    {metrics.get('cogs', 0):>25,.0f} won")
        print(f"  EBITDA:  {metrics.get('ebitda', 0):>25,.0f} won")
        print(f"\n  Full metrics keys: {sorted(metrics.keys())}")
    else:
        print("  ❌ No data returned")

    # Step 2: Call DART API directly and parse manually
    print("\n\n🔬 Step 2: Manual parsing of raw DART API response")
    print("-"*80)

    params = {
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': '11011',  # Annual
        'fs_div': 'CFS'  # Consolidated
    }

    try:
        response = dart._make_request('fnlttSinglAcntAll.json', params)

        if hasattr(response, 'json'):
            data = response.json()
        else:
            data = response

        if not data or data.get('status') != '000':
            print(f"  ❌ API Error: {data}")
            return

        items = data.get('list', [])
        print(f"  ✅ API returned {len(items)} account items")

        # Create item lookup
        item_lookup = {}
        for item in items:
            account_name = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0').replace(',', '')
            try:
                value = float(amount)
                item_lookup[account_name] = value
            except (ValueError, TypeError):
                pass

        # Check revenue fields
        print("\n  Revenue field variants:")
        revenue_variants = ['영업수익', '매출액', '수익(매출액)', '매출']
        for variant in revenue_variants:
            value = item_lookup.get(variant, None)
            if value is not None:
                print(f"    '{variant}': {value:>25,.0f} won")

        # Check COGS fields
        print("\n  COGS field variants:")
        cogs_variants = ['매출원가', '영업원가', '판매원가']
        for variant in cogs_variants:
            value = item_lookup.get(variant, None)
            if value is not None:
                print(f"    '{variant}': {value:>25,.0f} won")

        # Now call _parse_financial_statements() manually
        print("\n\n🔧 Step 3: Call _parse_financial_statements() method")
        print("-"*80)

        parsed = dart._parse_financial_statements(items, ticker, year)

        print(f"  Revenue: {parsed.get('revenue', 0):>25,.0f} won")
        print(f"  COGS:    {parsed.get('cogs', 0):>25,.0f} won")
        print(f"  EBITDA:  {parsed.get('ebitda', 0):>25,.0f} won")

        # Compare values
        print("\n\n📊 Step 4: Comparison")
        print("-"*80)

        revenue_api = item_lookup.get('영업수익', 0) or item_lookup.get('매출액', 0)
        cogs_api = item_lookup.get('매출원가', 0)

        revenue_parsed = parsed.get('revenue', 0)
        cogs_parsed = parsed.get('cogs', 0)

        print(f"  Revenue (from API):         {revenue_api:>25,.0f} won")
        print(f"  Revenue (after parsing):    {revenue_parsed:>25,.0f} won")
        print(f"  Match: {'✅' if revenue_api == revenue_parsed else '❌ MISMATCH'}")

        print(f"\n  COGS (from API):            {cogs_api:>25,.0f} won")
        print(f"  COGS (after parsing):       {cogs_parsed:>25,.0f} won")
        print(f"  Match: {'✅' if cogs_api == cogs_parsed else '❌ MISMATCH'}")

        # Show all fields in parsed result
        print("\n\n📋 Step 5: All parsed fields (non-zero only)")
        print("-"*80)
        for key, value in sorted(parsed.items()):
            if value and value != 0:
                if isinstance(value, (int, float)):
                    print(f"  {key:30s}: {value:>25,.2f}")
                else:
                    print(f"  {key:30s}: {value}")

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    diagnose_lg_chem_2023()
