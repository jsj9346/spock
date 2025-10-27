#!/usr/bin/env python3
"""
Revenue=0 문제 조사 스크립트

LG화학(051910), 삼성전자(005930) 2022 등에서 Revenue=0 발생
실제 DART API 응답을 확인하여 계정명 확인

Usage:
    python3 tests/investigate_revenue_issue.py --ticker 051910 --year 2023
    python3 tests/investigate_revenue_issue.py --ticker 005930 --year 2022
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from dotenv import load_dotenv
import argparse

load_dotenv()

# Corp code mapping (OFFICIAL from DART XML)
CORP_CODES = {
    '005930': '00126380',  # Samsung
    '051910': '00356361',  # LG Chem (OFFICIAL - was wrong before!)
    '000660': '00164779',  # SK Hynix
    '035720': '00222417',  # Kakao
}

def investigate_revenue(ticker: str, year: int):
    """Revenue=0 문제 조사"""

    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    corp_code = CORP_CODES.get(ticker)
    if not corp_code:
        print(f"❌ Corp code not found for {ticker}")
        return

    print("="*80)
    print(f"🔍 Investigating Revenue=0 Issue")
    print("="*80)
    print(f"Ticker: {ticker}")
    print(f"Corp Code: {corp_code}")
    print(f"Year: {year}")
    print("="*80)

    # Call DART API
    params = {
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': '11011',  # Annual
        'fs_div': 'CFS'  # Consolidated
    }

    try:
        response = dart._make_request('fnlttSinglAcntAll.json', params)

        # Handle Response object
        if hasattr(response, 'json'):
            data = response.json()
        else:
            data = response

        if not data or data.get('status') != '000':
            print(f"❌ API Error: {data}")
            return

        items = data.get('list', [])
    except Exception as e:
        print(f"❌ Error calling DART API: {e}")
        import traceback
        traceback.print_exc()
        return
    print(f"\n📊 Total items: {len(items)}")

    # Create lookup
    item_lookup = {}
    for item in items:
        account_name = item.get('account_nm', '')
        amount = item.get('thstrm_amount', '0').replace(',', '')
        try:
            value = float(amount)
            item_lookup[account_name] = value
        except (ValueError, TypeError):
            pass

    # Search for revenue-related fields
    print("\n" + "="*80)
    print("💰 Revenue-Related Fields Search")
    print("="*80)

    revenue_keywords = ['매출', '영업수익', '수익', '판매']

    revenue_fields = {}
    for keyword in revenue_keywords:
        for name, value in item_lookup.items():
            if keyword in name and value > 0:
                if name not in revenue_fields:
                    revenue_fields[name] = value

    if revenue_fields:
        print(f"\nFound {len(revenue_fields)} revenue-related fields:")
        for name, value in sorted(revenue_fields.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {name}: {value:>25,.0f} won")
    else:
        print("⚠️ No revenue-related fields found!")

    # Check current parsing logic
    print("\n" + "="*80)
    print("🔍 Current Parsing Logic Test")
    print("="*80)

    # Try current logic
    revenue_current = item_lookup.get('영업수익', 0) or item_lookup.get('매출액', 0)
    print(f"\nCurrent logic result:")
    print(f"  영업수익: {item_lookup.get('영업수익', 0):>25,.0f} won")
    print(f"  매출액:   {item_lookup.get('매출액', 0):>25,.0f} won")
    print(f"  → Final: {revenue_current:>25,.0f} won")

    if revenue_current == 0:
        print("\n❌ Current logic returns 0!")
        print("\n💡 Suggested fix:")

        # Suggest best alternative
        if revenue_fields:
            best_field = max(revenue_fields.items(), key=lambda x: x[1])
            print(f"  Use: '{best_field[0]}' = {best_field[1]:,.0f} won")
        else:
            print("  No alternative revenue field found")
    else:
        print("\n✅ Current logic works!")

    # Show all major financial items
    print("\n" + "="*80)
    print("📊 Major Financial Items")
    print("="*80)

    major_fields = [
        '영업수익', '매출액', '매출원가', '매출총이익',
        '판매비와관리비', '영업이익', '당기순이익',
        '영업활동현금흐름', '유형자산'
    ]

    for field in major_fields:
        value = item_lookup.get(field, None)
        if value is not None:
            print(f"  {field:20s}: {value:>25,.0f} won")
        else:
            print(f"  {field:20s}: {'NULL':>25s}")

    # Search for all unique patterns
    print("\n" + "="*80)
    print("🔍 All Account Names with '매출' or '수익'")
    print("="*80)

    for name, value in sorted(item_lookup.items()):
        if '매출' in name or '수익' in name:
            print(f"  {name:40s}: {value:>25,.0f} won")

def main():
    parser = argparse.ArgumentParser(description='Investigate Revenue=0 issue')
    parser.add_argument('--ticker', type=str, required=True, help='Stock ticker')
    parser.add_argument('--year', type=int, required=True, help='Fiscal year')

    args = parser.parse_args()

    investigate_revenue(args.ticker, args.year)

if __name__ == '__main__':
    main()
