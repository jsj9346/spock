#!/usr/bin/env python3
"""
Check corp_code mapping used by backfill script

Identify if wrong corp_code is being used for LG Chem
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient
from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

load_dotenv()

def check_mapping():
    """Check corp_code mapping from multiple sources"""

    print("="*80)
    print("🔍 Corp Code Mapping Check")
    print("="*80)

    # Initialize clients
    dart_api_key = os.getenv('DART_API_KEY')
    if not dart_api_key:
        print("❌ DART_API_KEY not found")
        return

    dart = DARTApiClient(api_key=dart_api_key)

    # 1. Check database mapping
    print("\n📊 Source 1: Database (stock_details table)")
    print("-"*80)

    try:
        db = PostgresDatabaseManager()
        query = """
        SELECT ticker, corp_code, corp_name
        FROM stock_details
        WHERE ticker IN ('051910', '005930') AND region = 'KR'
        ORDER BY ticker
        """
        db.execute_query(query)
        results = db.cursor.fetchall()

        if results:
            for row in results:
                print(f"  {row[0]}: corp_code='{row[1]}', name='{row[2]}'")
        else:
            print("  ⚠️ No corp codes found in database")

        db.close()
    except Exception as e:
        print(f"  ❌ Database error: {e}")

    # 2. Check DART XML mapping
    print("\n📄 Source 2: DART XML (corpCode.xml)")
    print("-"*80)

    try:
        xml_path = dart.download_corp_codes()
        if xml_path and os.path.exists(xml_path):
            corp_data = dart.parse_corp_codes(xml_path)

            # Search for LG Chem and Samsung
            for corp_name, data in corp_data.items():
                stock_code = data.get('stock_code', '').strip()
                corp_code = data.get('corp_code')

                if stock_code in ['051910', '005930']:
                    print(f"  {stock_code}: corp_code='{corp_code}', name='{corp_name}'")
        else:
            print("  ❌ Failed to download XML")
    except Exception as e:
        print(f"  ❌ XML parsing error: {e}")

    # 3. Verify data quality for each corp_code
    print("\n🔬 Source 3: Test data collection for each corp_code")
    print("-"*80)

    test_cases = {
        '051910': ['00164742', '00126380'],  # Correct, Wrong (Samsung's code)
        '005930': ['00126380', '00164742']   # Correct, Wrong (LG Chem's code)
    }

    for ticker, corp_codes in test_cases.items():
        print(f"\n  Testing ticker {ticker}:")
        for corp_code in corp_codes:
            try:
                metrics_list = dart.get_historical_fundamentals(
                    ticker=ticker,
                    corp_code=corp_code,
                    start_year=2023,
                    end_year=2023
                )

                if metrics_list:
                    metrics = metrics_list[0]
                    revenue = metrics.get('revenue', 0)
                    cogs = metrics.get('cogs', 0)

                    print(f"    corp_code='{corp_code}': Revenue={revenue/1e12:.1f}T, COGS={cogs/1e12:.1f}T")
                else:
                    print(f"    corp_code='{corp_code}': ❌ No data returned")

            except Exception as e:
                print(f"    corp_code='{corp_code}': ❌ Error - {e}")

    # 4. Search DART XML for similar company names
    print("\n\n🔍 Source 4: Search for LG-related companies in DART XML")
    print("-"*80)

    try:
        xml_path = dart.download_corp_codes()
        if xml_path and os.path.exists(xml_path):
            corp_data = dart.parse_corp_codes(xml_path)

            lg_companies = {}
            for corp_name, data in corp_data.items():
                if 'LG' in corp_name or 'LG' in corp_name:
                    stock_code = data.get('stock_code', '').strip()
                    corp_code = data.get('corp_code')

                    if stock_code:  # Only listed companies
                        lg_companies[corp_name] = {
                            'stock_code': stock_code,
                            'corp_code': corp_code
                        }

            print(f"  Found {len(lg_companies)} LG-related listed companies:")
            for name, data in sorted(lg_companies.items()):
                if data['stock_code'] in ['051910', '066570', '006360']:  # LG Chem, LG전자, LG디스플레이
                    print(f"    {name:30s}: ticker={data['stock_code']}, corp_code='{data['corp_code']}'")

    except Exception as e:
        print(f"  ❌ Error: {e}")

if __name__ == '__main__':
    check_mapping()
