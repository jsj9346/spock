#!/usr/bin/env python3
"""
Test KIS API to find lot_size field for Hong Kong stocks

This script tests various KIS API endpoints to identify which fields
contain lot_size (board lot) information for Hong Kong stocks.

Usage:
    python3 scripts/test_kis_hk_lot_size_api.py
"""

import os
import sys
import json
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI

# Load environment variables
load_dotenv()

APP_KEY = os.getenv('KIS_APP_KEY')
APP_SECRET = os.getenv('KIS_APP_SECRET')

# Test tickers (major Hong Kong stocks with known lot_sizes)
TEST_TICKERS = {
    '0700': {'name': 'Tencent', 'expected_lot': 100},
    '9988': {'name': 'Alibaba', 'expected_lot': 500},
    '0005': {'name': 'HSBC Holdings', 'expected_lot': 400},
    '0941': {'name': 'China Mobile', 'expected_lot': 500},
    '3690': {'name': 'Meituan', 'expected_lot': 100},
}

def test_current_price_api():
    """Test /uapi/overseas-price/v1/quotations/price endpoint"""
    print("="*80)
    print("Test 1: get_current_price() API")
    print("="*80)

    api = KISOverseasStockAPI(APP_KEY, APP_SECRET)

    for ticker, info in TEST_TICKERS.items():
        print(f"\n📊 Testing {ticker} ({info['name']}) - Expected lot: {info['expected_lot']}")
        print("-"*80)

        try:
            response = api.get_current_price(ticker, 'SEHK')

            if response:
                print("✅ API call successful")
                print(f"Response keys: {list(response.keys())}")
                print(f"Full response:")
                print(json.dumps(response, indent=2, ensure_ascii=False))

                # Look for lot_size related fields
                lot_size_fields = ['tr_unit', 'min_tr_qty', 'ovrs_tr_mket_size',
                                  'lot_size', 'board_lot', 'trading_unit',
                                  'min_ord_qty', 'min_trd_qty']

                print(f"\n🔍 Searching for lot_size fields...")
                found_fields = []
                for field in lot_size_fields:
                    if field in response:
                        found_fields.append(f"{field}: {response[field]}")

                if found_fields:
                    print(f"✅ Found lot_size fields:")
                    for field in found_fields:
                        print(f"   - {field}")
                else:
                    print(f"⚠️ No lot_size fields found in response")
            else:
                print("❌ API call returned empty response")

        except Exception as e:
            print(f"❌ Error: {e}")

        print()

def test_raw_api_call():
    """Test raw API call with full response inspection"""
    print("="*80)
    print("Test 2: Raw API Call (Full Response Inspection)")
    print("="*80)

    import requests
    from modules.api_clients.base_kis_api import BaseKISAPI

    api = BaseKISAPI(APP_KEY, APP_SECRET, 'https://openapi.koreainvestment.com:9443')
    api._rate_limit()

    # Try /uapi/overseas-price/v1/quotations/price
    url = f"{api.base_url}/uapi/overseas-price/v1/quotations/price"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {api._get_access_token()}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "HHDFS00000300",
    }

    ticker = '0700'  # Tencent
    params = {
        "AUTH": "",
        "EXCD": "SEHK",
        "SYMB": ticker,
    }

    print(f"\n📡 Raw API call for {ticker} (Tencent)...")
    print(f"URL: {url}")
    print(f"TR_ID: HHDFS00000300")
    print("-"*80)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        print(f"✅ HTTP {response.status_code}")
        print(f"Response rt_cd: {data.get('rt_cd')}")
        print(f"Response msg1: {data.get('msg1')}")

        if 'output' in data:
            print(f"\n📦 Output fields:")
            output = data['output']
            for key, value in sorted(output.items()):
                print(f"   {key:30s} = {value}")

        print(f"\n📄 Full JSON response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Error: {e}")

def test_search_info_api():
    """Test /uapi/overseas-price/v1/quotations/search-info endpoint"""
    print("\n" + "="*80)
    print("Test 3: Search Info API (Alternative Endpoint)")
    print("="*80)

    import requests
    from modules.api_clients.base_kis_api import BaseKISAPI

    api = BaseKISAPI(APP_KEY, APP_SECRET, 'https://openapi.koreainvestment.com:9443')
    api._rate_limit()

    # Try /uapi/overseas-price/v1/quotations/search-info
    url = f"{api.base_url}/uapi/overseas-price/v1/quotations/search-info"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {api._get_access_token()}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "CTPF1702R",  # Search info TR_ID
    }

    ticker = '0700'
    params = {
        "PRDT_TYPE_CD": "512",  # Overseas stock
        "PDNO": ticker,
        "EXCD": "SEHK",
    }

    print(f"\n📡 Search Info API for {ticker} (Tencent)...")
    print(f"URL: {url}")
    print(f"TR_ID: CTPF1702R")
    print("-"*80)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        print(f"✅ HTTP {response.status_code}")
        print(f"Response rt_cd: {data.get('rt_cd')}")
        print(f"Response msg1: {data.get('msg1')}")

        if 'output' in data:
            print(f"\n📦 Output fields:")
            output = data['output']
            for key, value in sorted(output.items()):
                print(f"   {key:30s} = {value}")

        print(f"\n📄 Full JSON response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("\n🔍 KIS API Lot_size Field Investigation for Hong Kong Stocks")
    print("="*80)

    if not APP_KEY or not APP_SECRET:
        print("❌ Error: KIS API credentials not found in .env file")
        print("Please set KIS_APP_KEY and KIS_APP_SECRET")
        sys.exit(1)

    print(f"✅ API credentials loaded")
    print(f"   APP_KEY: {APP_KEY[:10]}...")
    print(f"   APP_SECRET: {APP_SECRET[:10]}...")
    print()

    # Run tests
    test_current_price_api()
    test_raw_api_call()
    test_search_info_api()

    print("\n" + "="*80)
    print("🎯 Investigation Complete")
    print("="*80)
    print("\nNext Steps:")
    print("1. Review API responses above")
    print("2. Identify lot_size field name")
    print("3. Update HKAdapterKIS._fetch_lot_size() accordingly")
    print()

if __name__ == '__main__':
    main()
