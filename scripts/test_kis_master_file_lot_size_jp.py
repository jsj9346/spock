#!/usr/bin/env python3
"""
Test KIS Master Files for Japan stock lot_size information

Check if KIS master files (.cod) contain lot_size information for Japanese stocks.

Background:
- 2018 TSE Reform: Standardized most stocks to 100 shares/lot
- Exceptions: Some penny stocks, REITs, legacy stocks may have 1, 10, 1000, or 10000

Usage:
    python3 scripts/test_kis_master_file_lot_size_jp.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager

def main():
    print("="*80)
    print("KIS Master File Lot_size Investigation (Japan)")
    print("="*80)
    print()

    try:
        mgr = KISMasterFileManager()

        # Parse JP master file (tsemst.cod)
        print("📁 Parsing Japan master file (tsemst.cod)...")
        df = mgr.parse_market('tse')

        if df.empty:
            print("❌ No data in JP master file")
            return

        print(f"✅ Loaded {len(df)} Japan stocks")
        print()

        # Show all columns
        print("📊 Available columns in master file:")
        for i, col in enumerate(df.columns, 1):
            print(f"   {i:2d}. {col}")
        print()

        # Look for lot_size related columns
        lot_columns = [col for col in df.columns
                      if any(keyword in col.lower()
                            for keyword in ['lot', 'unit', 'min', 'qty', 'trade', 'board', 'order'])]

        if lot_columns:
            print(f"✅ Found {len(lot_columns)} lot_size related columns:")
            for col in lot_columns:
                print(f"\n   Column: {col}")
                print(f"   Data type: {df[col].dtype}")
                print(f"   Unique values: {df[col].nunique()}")
                print(f"   Sample values: {df[col].head(10).tolist()}")

                # Value distribution
                print(f"   Distribution (top 10):")
                value_counts = df[col].value_counts().head(10)
                for val, count in value_counts.items():
                    pct = (count / len(df)) * 100
                    print(f"      {val}: {count} stocks ({pct:.1f}%)")
        else:
            print("❌ No lot_size related columns found")

        print()

        # Show sample of first 10 stocks
        print("📋 Sample data (first 10 stocks):")
        print(df.head(10).to_string())
        print()

        # Test specific tickers (known Japanese stocks)
        test_tickers = {
            '7203': 'Toyota Motor Corp (Expected: 100)',
            '9984': 'SoftBank Group (Expected: 100)',
            '6758': 'Sony Group (Expected: 100)',
            '7974': 'Nintendo (Expected: 100)',
            '9433': 'KDDI (Expected: 100)',
        }

        print("🔍 Checking specific tickers:")
        for ticker, info in test_tickers.items():
            print(f"\n{ticker}: {info}")
            matches = df[df['Symbol'] == ticker]
            if not matches.empty:
                print("   Found in master file:")
                for col in df.columns:
                    val = matches.iloc[0][col]
                    print(f"      {col}: {val}")
            else:
                # Try without leading zeros
                ticker_normalized = ticker.lstrip('0') or '0'
                matches = df[df['Symbol'] == ticker_normalized]
                if not matches.empty:
                    print(f"   Found with normalized ticker '{ticker_normalized}':")
                    for col in df.columns:
                        val = matches.iloc[0][col]
                        print(f"      {col}: {val}")
                else:
                    print(f"   ⚠️ Ticker {ticker} not found")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
