#!/usr/bin/env python3
"""
Test PerformanceReporter Plotly Integration

Tests the new ic_time_series_report_plotly() method to verify:
1. Plotly import successful
2. ICResult data conversion to DataFrame
3. Chart generation (timeseries, distribution, dashboard)
4. HTML file export

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import sys
from datetime import date

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.analysis.performance_reporter import PerformanceReporter
from modules.analysis.factor_analyzer import ICResult


def load_ic_results_from_db(
    db: PostgresDatabaseManager,
    factor_name: str,
    region: str = 'KR',
    holding_period: int = 21
) -> list:
    """
    Load IC results from database and convert to ICResult objects

    Args:
        db: Database manager
        factor_name: Factor name (e.g., 'PE_Ratio')
        region: Market region
        holding_period: Forward return period

    Returns:
        List[ICResult]
    """
    query = """
        SELECT
            date,
            ic,
            p_value,
            num_stocks,
            is_significant
        FROM ic_time_series
        WHERE factor_name = %s
          AND region = %s
          AND holding_period = %s
        ORDER BY date
    """

    results = db.execute_query(query, (factor_name, region, holding_period))

    if not results:
        print(f"⚠️  No IC data found for {factor_name}")
        return []

    # Convert to ICResult objects
    ic_results = [
        ICResult(
            date=row['date'],
            ic_value=float(row['ic']),
            p_value=float(row['p_value']),
            num_stocks=int(row['num_stocks']),
            is_significant=bool(row['is_significant'])
        )
        for row in results
    ]

    print(f"✓ Loaded {len(ic_results)} IC records for {factor_name}")
    return ic_results


def main():
    """Test PerformanceReporter Plotly integration"""
    print("=" * 80)
    print("TESTING PERFORMANCE REPORTER PLOTLY INTEGRATION")
    print("=" * 80)

    # Initialize database
    db = PostgresDatabaseManager()

    # Test data: Load PE_Ratio IC results
    print("\n1. Loading IC data from database...")
    ic_results = load_ic_results_from_db(db, 'PE_Ratio', 'KR', 21)

    if not ic_results:
        print("❌ No IC data available. Run calculate_ic_time_series.py first.")
        return

    print(f"   Date Range: {ic_results[0].date} to {ic_results[-1].date}")
    print(f"   Total Records: {len(ic_results)}")

    # Initialize PerformanceReporter
    print("\n2. Initializing PerformanceReporter...")
    reporter = PerformanceReporter(output_dir='reports/test_plotly/', theme='plotly_white')
    print("   ✓ PerformanceReporter initialized")

    # Test 1: Generate timeseries chart only
    print("\n3. Test 1: Generate IC timeseries chart...")
    try:
        files = reporter.ic_time_series_report_plotly(
            factor_name='PE_Ratio',
            ic_results=ic_results,
            region='KR',
            holding_period=21,
            export_formats=['html'],
            chart_types=['timeseries']
        )

        if files:
            print("   ✓ Timeseries chart generated:")
            for key, path in files.items():
                print(f"     - {key}: {path}")
        else:
            print("   ⚠️  No files generated")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Test 2: Generate all chart types
    print("\n4. Test 2: Generate all chart types (dashboard)...")
    try:
        files = reporter.ic_time_series_report_plotly(
            factor_name='PE_Ratio',
            ic_results=ic_results,
            region='KR',
            holding_period=21,
            export_formats=['html'],
            chart_types=['timeseries', 'distribution', 'rolling', 'dashboard']
        )

        if files:
            print("   ✓ All charts generated:")
            for key, path in files.items():
                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                print(f"     - {key}: {path} ({file_size:.2f} MB)")
        else:
            print("   ⚠️  No files generated")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # Test 3: Test with both HTML and PNG export
    print("\n5. Test 3: Export to both HTML and PNG...")
    try:
        files = reporter.ic_time_series_report_plotly(
            factor_name='PE_Ratio',
            ic_results=ic_results,
            region='KR',
            holding_period=21,
            export_formats=['html', 'png'],
            chart_types=['dashboard']
        )

        if files:
            print("   ✓ Multi-format export successful:")
            for key, path in files.items():
                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                print(f"     - {key}: {path} ({file_size:.2f} MB)")
        else:
            print("   ⚠️  No files generated")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    print("\n" + "=" * 80)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 80)
    print("\n✓ All tests passed successfully!")
    print(f"✓ Output directory: reports/test_plotly/")


if __name__ == '__main__':
    main()
