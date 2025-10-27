#!/usr/bin/env python3
"""
Test DART API Report Priority Logic

Validates intelligent report selection based on current month.

Author: Spock Trading System
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.dart_api_client import DARTApiClient
from modules.fundamental_data_collector import FundamentalDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_report_priority_logic():
    """
    Test DART API report priority logic

    Validates that report priority is correctly determined based on current month.
    """
    print("\n" + "="*70)
    print("DART API Report Priority Logic Test")
    print("="*70 + "\n")

    # Check DART API key
    if not os.getenv('DART_API_KEY'):
        print("⚠️ DART_API_KEY not found in environment variables")
        print("📝 Get API key from: https://opendart.fss.or.kr/")
        print("💡 Set with: export DART_API_KEY='your_key_here'")
        print("\n❌ Skipping test\n")
        return False

    try:
        # Initialize DART API client
        dart_api = DARTApiClient()

        # Test report priority list
        current_month = datetime.now().month
        priority_list = dart_api._get_report_priority_list()

        print(f"📅 Current Month: {current_month}")
        print(f"📊 Report Priority Order:\n")

        for idx, (year, reprt_code, report_name) in enumerate(priority_list, 1):
            report_type_map = {
                '11011': 'Annual',
                '11012': 'Semi-Annual',
                '11013': 'Q1',
                '11014': 'Q3'
            }
            report_type = report_type_map.get(reprt_code, 'Unknown')

            print(f"  {idx}. {report_name}")
            print(f"     - Year: {year}")
            print(f"     - Code: {reprt_code} ({report_type})")
            print()

        # Validate priority logic
        print("-" * 70)
        print("Validation Results:\n")

        validation_passed = True

        # Check 1: Priority list is not empty
        if not priority_list:
            print("❌ FAIL: Priority list is empty")
            validation_passed = False
        else:
            print(f"✅ PASS: Priority list has {len(priority_list)} entries")

        # Check 2: Most recent year should be prioritized
        if priority_list:
            first_year = priority_list[0][0]
            current_year = datetime.now().year

            if first_year >= current_year - 1:
                print(f"✅ PASS: First priority uses recent year ({first_year})")
            else:
                print(f"❌ FAIL: First priority uses old year ({first_year})")
                validation_passed = False

        # Check 3: Quarterly reports should come before annual (in recent months)
        if current_month >= 5 and priority_list:
            first_reprt_code = priority_list[0][1]
            if first_reprt_code in ['11013', '11014', '11012']:
                print(f"✅ PASS: Quarterly/Semi-annual report prioritized (month {current_month})")
            else:
                print(f"⚠️ WARNING: Annual report prioritized in month {current_month}")

        print("\n" + "="*70)

        if validation_passed:
            print("✅ All validation checks passed!")
            return True
        else:
            print("❌ Some validation checks failed")
            return False

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_fundamental_collection_with_priority():
    """
    Test fundamental data collection with report priority logic

    Tests end-to-end collection using the new intelligent report selection.
    """
    print("\n" + "="*70)
    print("Fundamental Data Collection Test (with Report Priority)")
    print("="*70 + "\n")

    # Check DART API key
    if not os.getenv('DART_API_KEY'):
        print("⚠️ DART_API_KEY not found")
        print("❌ Skipping test\n")
        return False

    try:
        # Initialize
        db = SQLiteDatabaseManager()
        collector = FundamentalDataCollector(db)

        # Test ticker (Samsung Electronics)
        ticker = '005930'

        print(f"📊 Testing fundamental collection for {ticker} (Samsung Electronics)\n")

        # Collect fundamentals
        results = collector.collect_fundamentals(
            tickers=[ticker],
            region='KR',
            force_refresh=True  # Force refresh to test new logic
        )

        if results.get(ticker):
            print(f"\n✅ Collection successful!")

            # Retrieve and display data
            fundamentals = collector.get_fundamentals(ticker, 'KR', limit=1)

            if fundamentals:
                data = fundamentals[0]
                data_source = data.get('data_source', '')

                # Parse data_source field (format: "DART-YYYY-REPCODE")
                fiscal_year = None
                report_code = None
                if data_source.startswith('DART-'):
                    parts = data_source.split('-')
                    if len(parts) >= 3:
                        fiscal_year = parts[1]
                        report_code = parts[2]

                print(f"\n📈 Collected Fundamental Data:")
                print(f"  - Ticker: {data.get('ticker')}")
                print(f"  - Date: {data.get('date')}")
                print(f"  - Period Type: {data.get('period_type')}")
                print(f"  - Fiscal Year: {fiscal_year}")
                print(f"  - Report Code: {report_code}")
                print(f"  - Data Source: {data_source}")
                print(f"  - ROE: {data.get('roe', 'N/A')}")
                print(f"  - ROA: {data.get('roa', 'N/A')}")
                print(f"  - Debt Ratio: {data.get('debt_ratio', 'N/A')}")

                # Validate report code
                if report_code in ['11011', '11012', '11013', '11014']:
                    report_type_map = {
                        '11011': 'Annual',
                        '11012': 'Semi-Annual',
                        '11013': 'Q1',
                        '11014': 'Q3'
                    }
                    report_type = report_type_map.get(report_code, 'Unknown')
                    print(f"\n✅ Valid report: {report_type} (Year: {fiscal_year})")
                    return True
                else:
                    print(f"\n⚠️ Warning: Unexpected report code: {report_code}")
                    return False
            else:
                print(f"\n⚠️ Data retrieved but empty")
                return False
        else:
            print(f"\n❌ Collection failed")
            return False

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Main test runner

    Runs all tests for DART API report priority logic.
    """
    print("\n" + "="*70)
    print("DART API REPORT PRIORITY LOGIC TEST SUITE")
    print("Spock Trading System")
    print("="*70)

    all_passed = True

    try:
        # Test 1: Report priority logic
        print("\n[Test 1/2] Report Priority Logic")
        if not test_report_priority_logic():
            all_passed = False

        # Test 2: End-to-end collection
        print("\n[Test 2/2] Fundamental Collection with Priority")
        if not test_fundamental_collection_with_priority():
            all_passed = False

        # Summary
        print("\n" + "="*70)
        if all_passed:
            print("✅ All tests passed!")
            print("="*70 + "\n")
            return 0
        else:
            print("❌ Some tests failed")
            print("="*70 + "\n")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user\n")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test suite failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
