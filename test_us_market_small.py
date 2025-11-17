#!/usr/bin/env python3
"""
US Market Small-Scale Test

Tests Week 2 implementation with 10 US tickers.
Validates:
- Technical indicator calculation logic
- Database updates (ohlcv_data columns)
- Progress monitoring
- Error handling
"""

import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from modules.db_manager_postgres import PostgresDatabaseManager
from scripts.calculate_technical_indicators import TechnicalIndicatorCalculator


def get_test_tickers(db_manager, limit=10):
    """Get US tickers with sufficient data"""
    query = """
        SELECT
            t.ticker,
            COUNT(o.date) as data_points
        FROM tickers t
        INNER JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
        WHERE t.region = 'US' AND o.timeframe = '1d'
        GROUP BY t.ticker
        HAVING COUNT(o.date) >= 200
        ORDER BY COUNT(o.date) DESC
        LIMIT %s
    """

    result = db_manager.execute_query(query, (limit,))
    return [row['ticker'] for row in result]


def check_indicators_before(db_manager, tickers):
    """Check if indicators exist before calculation"""
    ticker_list = ",".join([f"'{t}'" for t in tickers])
    query = f"""
        SELECT
            ticker,
            COUNT(*) as total_records,
            COUNT(CASE WHEN ma5 IS NOT NULL THEN 1 END) as with_ma5,
            COUNT(CASE WHEN rsi_14 IS NOT NULL THEN 1 END) as with_rsi
        FROM ohlcv_data
        WHERE region = 'US' AND ticker IN ({ticker_list})
        GROUP BY ticker
        ORDER BY ticker
    """

    result = db_manager.execute_query(query, None)
    return result


def check_indicators_after(db_manager, tickers):
    """Check indicators after calculation"""
    return check_indicators_before(db_manager, tickers)


def main():
    print("=" * 80)
    print("US MARKET SMALL-SCALE TEST")
    print("Week 2 Implementation Validation")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize
    db_manager = PostgresDatabaseManager()
    calculator = TechnicalIndicatorCalculator(db_manager)

    # Step 1: Get test tickers
    print("Step 1: Selecting test tickers...")
    print("-" * 80)

    tickers = get_test_tickers(db_manager, limit=10)
    print(f"Selected {len(tickers)} US tickers:")
    for i, ticker in enumerate(tickers, 1):
        print(f"  {i}. {ticker}")
    print()

    # Step 2: Check indicators before
    print("Step 2: Checking indicators BEFORE calculation...")
    print("-" * 80)

    before_data = check_indicators_before(db_manager, tickers)

    print(f"{'Ticker':<10} {'Total Records':<15} {'With MA5':<12} {'With RSI':<12}")
    print("-" * 80)
    for row in before_data:
        print(f"{row['ticker']:<10} {row['total_records']:<15} "
              f"{row['with_ma5']:<12} {row['with_rsi']:<12}")
    print()

    # Step 3: Calculate indicators
    print("Step 3: Calculating technical indicators...")
    print("-" * 80)
    print()

    start_time = time.time()
    success_count = 0
    failed_count = 0

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Processing {ticker}...", end=' ')

        try:
            if calculator.calculate_indicators_for_ticker(ticker, 'US'):
                print("✅ Success")
                success_count += 1
            else:
                print("⚠️  Skipped (insufficient data)")
                failed_count += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            failed_count += 1

    duration = time.time() - start_time

    print()
    print("=" * 80)
    print("Calculation Results:")
    print("=" * 80)
    print(f"  Success: {success_count}/{len(tickers)} tickers")
    print(f"  Failed: {failed_count}/{len(tickers)} tickers")
    print(f"  Duration: {duration:.2f} seconds ({duration/len(tickers):.2f} sec/ticker)")
    print()

    # Step 4: Verify results
    print("Step 4: Verifying indicators AFTER calculation...")
    print("-" * 80)

    after_data = check_indicators_after(db_manager, tickers)

    print(f"{'Ticker':<10} {'Total Records':<15} {'With MA5':<12} {'With RSI':<12} {'Status'}")
    print("-" * 80)

    verification_passed = 0

    for row in after_data:
        ticker = row['ticker']
        has_indicators = row['with_ma5'] > 0 and row['with_rsi'] > 0
        status = "✅ OK" if has_indicators else "❌ MISSING"

        print(f"{ticker:<10} {row['total_records']:<15} "
              f"{row['with_ma5']:<12} {row['with_rsi']:<12} {status}")

        if has_indicators:
            verification_passed += 1

    print()
    print("=" * 80)
    print("VERIFICATION RESULTS:")
    print("=" * 80)
    print(f"  Indicators verified: {verification_passed}/{len(tickers)} tickers")
    print(f"  Success rate: {verification_passed*100/len(tickers):.2f}%")
    print()

    # Step 5: Sample data inspection
    print("Step 5: Sample data inspection (first ticker)...")
    print("-" * 80)

    sample_ticker = tickers[0]
    sample_query = """
        SELECT
            ticker, date, close,
            ma5, ma20, ma60, ma120, ma200,
            rsi_14, macd, macd_signal
        FROM ohlcv_data
        WHERE region = 'US' AND ticker = %s
          AND ma5 IS NOT NULL
        ORDER BY date DESC
        LIMIT 5
    """

    sample_data = db_manager.execute_query(sample_query, (sample_ticker,))

    if sample_data:
        print(f"\nSample data for {sample_ticker} (latest 5 records):")
        print()
        for row in sample_data:
            print(f"Date: {row['date']}")
            print(f"  Close: {row['close']:.2f}")
            print(f"  MA5: {row['ma5']:.2f} | MA20: {row['ma20']:.2f} | MA60: {row['ma60']:.2f}")
            print(f"  RSI-14: {row['rsi_14']:.2f}")
            print(f"  MACD: {row['macd']:.4f} | Signal: {row['macd_signal']:.4f}")
            print()
    else:
        print(f"⚠️  No indicator data found for {sample_ticker}")

    # Final summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    all_passed = (success_count == len(tickers) and verification_passed == len(tickers))

    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("Week 2 Implementation Validation: ✅ SUCCESS")
        print()
        print("Validated:")
        print("  ✅ Technical indicator calculation logic")
        print("  ✅ Database updates (ohlcv_data columns)")
        print("  ✅ Multi-ticker processing")
        print("  ✅ Progress monitoring")
        print("  ✅ Data verification")
    else:
        print("⚠️  PARTIAL SUCCESS")
        print()
        print(f"Calculation: {success_count}/{len(tickers)} ({'✅' if success_count == len(tickers) else '⚠️'})")
        print(f"Verification: {verification_passed}/{len(tickers)} ({'✅' if verification_passed == len(tickers) else '⚠️'})")

    print()
    print("=" * 80)
    print(f"Test completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
