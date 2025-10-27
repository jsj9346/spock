#!/usr/bin/env python3
"""
Test yfinance for Hong Kong stock lot_size information

Hong Kong stocks have lot_size information available through yfinance.
This script tests if we can retrieve accurate board lot data.

Usage:
    python3 scripts/test_yfinance_hk_lot_size.py
"""

import yfinance as yf
import pandas as pd

# Test tickers with known lot_sizes (verified from HKEX)
TEST_TICKERS = {
    '0700.HK': {'name': 'Tencent', 'expected_lot': 100},
    '9988.HK': {'name': 'Alibaba', 'expected_lot': 500},
    '0005.HK': {'name': 'HSBC Holdings', 'expected_lot': 400},
    '0941.HK': {'name': 'China Mobile', 'expected_lot': 500},
    '3690.HK': {'name': 'Meituan', 'expected_lot': 100},
    '0001.HK': {'name': 'CKH Holdings', 'expected_lot': 500},
    '0002.HK': {'name': 'CLP Holdings', 'expected_lot': 500},
    '0003.HK': {'name': 'HK & China Gas', 'expected_lot': 1000},
    '0011.HK': {'name': 'Hang Seng Bank', 'expected_lot': 400},
    '1299.HK': {'name': 'AIA', 'expected_lot': 400},
}

def test_yfinance_lot_size():
    """Test yfinance for lot_size information"""
    print("="*80)
    print("Testing yfinance for Hong Kong Stock Lot_size Information")
    print("="*80)
    print()

    results = []

    for ticker, info in TEST_TICKERS.items():
        print(f"📊 {ticker:10s} ({info['name']:20s}) Expected: {info['expected_lot']:5d} shares/lot")
        print("-"*80)

        try:
            stock = yf.Ticker(ticker)
            stock_info = stock.info

            # Print all available keys
            print(f"Available info keys ({len(stock_info)} total):")
            for i, key in enumerate(sorted(stock_info.keys()), 1):
                print(f"  {i:3d}. {key:30s} = {stock_info.get(key)}")

            # Look for lot_size related fields
            lot_fields = [
                'lotSize', 'lot_size', 'boardLot', 'board_lot',
                'tradingUnit', 'trading_unit', 'minTradeQty',
                'minimumTradingQuantity', 'roundLot'
            ]

            print(f"\n🔍 Checking lot_size fields:")
            found = False
            for field in lot_fields:
                if field in stock_info:
                    value = stock_info[field]
                    match = "✅" if value == info['expected_lot'] else "❌"
                    print(f"   {match} {field:25s} = {value}")
                    found = True

            if not found:
                print(f"   ⚠️ No lot_size fields found")

            results.append({
                'ticker': ticker,
                'name': info['name'],
                'expected': info['expected_lot'],
                'yfinance_lotSize': stock_info.get('lotSize'),
                'found': found
            })

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'ticker': ticker,
                'name': info['name'],
                'expected': info['expected_lot'],
                'yfinance_lotSize': None,
                'error': str(e)
            })

        print()

    # Summary
    print("="*80)
    print("Summary")
    print("="*80)

    df = pd.DataFrame(results)
    print(df.to_string(index=False))

    if 'yfinance_lotSize' in df.columns and df['yfinance_lotSize'].notna().any():
        matches = (df['yfinance_lotSize'] == df['expected']).sum()
        total = len(df)
        print(f"\n✅ Accuracy: {matches}/{total} ({matches/total*100:.1f}%)")
        print(f"\n🎯 Conclusion: yfinance {'CAN' if matches > total/2 else 'CANNOT'} provide accurate lot_size data")
    else:
        print(f"\n❌ yfinance does not provide lot_size information")

def main():
    print("\n🔍 yfinance Lot_size Data Availability Test")
    print()
    test_yfinance_lot_size()
    print()

if __name__ == '__main__':
    main()
