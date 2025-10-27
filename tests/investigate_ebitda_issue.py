#!/usr/bin/env python3
"""
EBITDA=0 문제 조사 스크립트

SK하이닉스(000660) 2024, 카카오(035720), 삼성SDI(006400) 등에서 EBITDA=0 발생
실제 DART API 응답을 확인하여 감가상각비 및 현금흐름 필드명 확인

Usage:
    python3 tests/investigate_ebitda_issue.py --ticker 000660 --year 2024
    python3 tests/investigate_ebitda_issue.py --ticker 035720 --year 2023
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
    '000660': '00164779',  # SK Hynix
    '035720': '00258801',  # Kakao (OFFICIAL - was wrong!)
    '006400': '00126362',  # Samsung SDI (OFFICIAL - was wrong!)
    '005930': '00126380',  # Samsung
    '051910': '00356361',  # LG Chem
}

def investigate_ebitda(ticker: str, year: int):
    """EBITDA=0 문제 조사"""

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
    print(f"🔍 Investigating EBITDA=0 Issue")
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

    # Search for depreciation-related fields
    print("\n" + "="*80)
    print("🏭 Depreciation-Related Fields Search")
    print("="*80)

    depreciation_keywords = ['감가상각', '상각비', '감가', '무형자산상각']

    depreciation_fields = {}
    for keyword in depreciation_keywords:
        for name, value in item_lookup.items():
            if keyword in name:
                if name not in depreciation_fields:
                    depreciation_fields[name] = value

    if depreciation_fields:
        print(f"\nFound {len(depreciation_fields)} depreciation-related fields:")
        for name, value in sorted(depreciation_fields.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"  - {name}: {value:>25,.0f} won")
    else:
        print("⚠️ No depreciation-related fields found!")

    # Search for cash flow-related fields
    print("\n" + "="*80)
    print("💵 Cash Flow-Related Fields Search")
    print("="*80)

    cf_keywords = ['현금흐름', '영업활동', '투자활동', '재무활동']

    cf_fields = {}
    for keyword in cf_keywords:
        for name, value in item_lookup.items():
            if keyword in name:
                if name not in cf_fields:
                    cf_fields[name] = value

    if cf_fields:
        print(f"\nFound {len(cf_fields)} cash flow-related fields:")
        for name, value in sorted(cf_fields.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"  - {name}: {value:>25,.0f} won")
    else:
        print("⚠️ No cash flow-related fields found!")

    # Check current parsing logic
    print("\n" + "="*80)
    print("🔍 Current Parsing Logic Test")
    print("="*80)

    # Try current logic
    depreciation_direct = item_lookup.get('감가상각비', 0)
    operating_cf = item_lookup.get('영업활동현금흐름', 0)
    working_capital_change = item_lookup.get('영업활동으로 인한 자산부채의 변동', 0)
    operating_profit = item_lookup.get('영업이익', 0)

    print(f"\nCurrent field values:")
    print(f"  감가상각비 (direct):              {depreciation_direct:>25,.0f} won")
    print(f"  영업활동현금흐름:                    {operating_cf:>25,.0f} won")
    print(f"  영업활동으로 인한 자산부채의 변동:      {working_capital_change:>25,.0f} won")
    print(f"  영업이익:                          {operating_profit:>25,.0f} won")

    # Calculate depreciation using current logic
    if depreciation_direct > 0:
        depreciation = depreciation_direct
        method = "Direct field"
    elif operating_cf > 0 and operating_profit > 0:
        depreciation = max(0, operating_cf - operating_profit - working_capital_change)
        method = "Estimated from cash flow"
    else:
        depreciation = 0
        method = "Failed (no data)"

    print(f"\n  → Depreciation ({method}): {depreciation:>17,.0f} won")

    # Calculate EBITDA
    if operating_profit > 0 and depreciation > 0:
        ebitda = operating_profit + depreciation
        ebitda_note = "Operating Profit + Depreciation"
    else:
        ebitda = operating_profit
        ebitda_note = "Fallback to Operating Profit (depreciation unavailable)"

    print(f"  → EBITDA ({ebitda_note[:30]}): {ebitda:>6,.0f} won")

    if ebitda == 0 and operating_profit > 0:
        print("\n❌ Current logic returns EBITDA=0 despite positive Operating Profit!")
        print("\n💡 Suggested fixes:")

        # Suggest best alternative depreciation field
        if depreciation_fields:
            best_field = max(depreciation_fields.items(), key=lambda x: abs(x[1]))
            print(f"  1. Use direct depreciation field: '{best_field[0]}' = {best_field[1]:,.0f} won")

        # Suggest alternative CF fields
        if cf_fields:
            operating_cf_variants = {k: v for k, v in cf_fields.items() if '영업' in k and v != 0}
            if operating_cf_variants:
                best_cf = max(operating_cf_variants.items(), key=lambda x: abs(x[1]))
                print(f"  2. Use alternative Operating CF field: '{best_cf[0]}' = {best_cf[1]:,.0f} won")

        # Calculate what EBITDA should be with best available data
        if depreciation_fields:
            best_depreciation = best_field[1] if best_field else 0
            suggested_ebitda = operating_profit + abs(best_depreciation)
            print(f"  3. Expected EBITDA: {suggested_ebitda:,.0f} won (Op Profit + Best Depreciation)")

    elif ebitda == 0:
        print("\n⚠️ EBITDA=0 is expected (Operating Profit = 0 or negative)")
    else:
        print(f"\n✅ Current logic works! EBITDA = {ebitda:,.0f} won")

    # Show all major financial items
    print("\n" + "="*80)
    print("📊 Major Financial Items")
    print("="*80)

    major_fields = [
        '영업수익', '매출액', '수익(매출액)', '매출',  # Revenue variants
        '매출원가', '영업원가',  # COGS variants
        '매출총이익',
        '판매비와관리비',
        '영업이익',
        '당기순이익',
        '유형자산',  # PP&E
    ]

    for field in major_fields:
        value = item_lookup.get(field, None)
        if value is not None:
            print(f"  {field:30s}: {value:>25,.0f} won")
        else:
            print(f"  {field:30s}: {'NULL':>25s}")

    # Search for all depreciation and CF patterns
    print("\n" + "="*80)
    print("🔍 All Account Names with '감가상각' or '현금흐름'")
    print("="*80)

    for name, value in sorted(item_lookup.items()):
        if '감가상각' in name or '현금흐름' in name or '상각' in name:
            print(f"  {name:50s}: {value:>25,.0f} won")

def main():
    parser = argparse.ArgumentParser(description='Investigate EBITDA=0 issue')
    parser.add_argument('--ticker', type=str, required=True, help='Stock ticker')
    parser.add_argument('--year', type=int, required=True, help='Fiscal year')

    args = parser.parse_args()

    investigate_ebitda(args.ticker, args.year)

if __name__ == '__main__':
    main()
