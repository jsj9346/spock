#!/usr/bin/env python3
"""
Test KIS Master Files for Hong Kong stock lot_size information

Check if KIS master files (.cod) contain lot_size information.

Usage:
    python3 scripts/test_kis_master_file_lot_size.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager

def main():
    print("="*80)
    print("KIS Master File Lot_size Investigation (Hong Kong)")
    print("="*80)
    print()

    try:
        mgr = KISMasterFileManager()

        # Parse HK master file
        print("📁 Parsing Hong Kong master file (hks.cod)...")
        df = mgr.parse_market('hks')

        if df.empty:
            print("❌ No data in HK master file")
            return

        print(f"✅ Loaded {len(df)} Hong Kong stocks")
        print()

        # Show all columns
        print("📊 Available columns in master file:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        print()

        # Look for lot_size related columns
        lot_columns = [col for col in df.columns
                      if any(keyword in col.lower()
                            for keyword in ['lot', 'unit', 'min', 'qty', 'trade'])]

        if lot_columns:
            print(f"✅ Found {len(lot_columns)} lot_size related columns:")
            for col in lot_columns:
                print(f"   - {col}")
                print(f"     Sample values: {df[col].head(10).tolist()}")
        else:
            print("❌ No lot_size related columns found")

        print()

        # Show sample of first 10 stocks
        print("📋 Sample data (first 10 stocks):")
        print(df.head(10).to_string())
        print()

        # Test specific tickers
        test_tickers = {
            '0700': 'Tencent (Expected: 100)',
            '9988': 'Alibaba (Expected: 500)',
            '0005': 'HSBC Holdings (Expected: 400)',
        }

        print("🔍 Checking specific tickers:")
        for ticker, info in test_tickers.items():
            print(f"\n{ticker}: {info}")
            matches = df[df['Symbol'] == ticker]
            if not matches.empty:
                print(matches.to_dict('records')[0])
            else:
                print(f"   ⚠️ Ticker {ticker} not found")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
