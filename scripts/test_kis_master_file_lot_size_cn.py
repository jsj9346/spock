#!/usr/bin/env python3
"""
Test KIS Master Files for China stock lot_size information

Check if KIS master files (.cod) contain lot_size information for Chinese A-shares.

Background:
- SSE/SZSE Standard: 100 shares/lot (1手 = 100股)
- All A-shares should have uniform 100 shares/lot
- ST stocks (Special Treatment) also use 100 shares/lot

Usage:
    python3 scripts/test_kis_master_file_lot_size_cn.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager

def test_market(mgr, market_code, market_name, test_tickers):
    """Test a specific Chinese market"""
    print("="*80)
    print(f"KIS Master File Lot_size Investigation ({market_name})")
    print("="*80)
    print()

    try:
        # Parse market master file
        print(f"📁 Parsing {market_name} master file ({market_code}.cod)...")
        df = mgr.parse_market(market_code)

        if df.empty:
            print(f"❌ No data in {market_name} master file")
            return False

        print(f"✅ Loaded {len(df)} {market_name} stocks")
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

        # Test specific tickers
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
                print(f"   ⚠️ Ticker {ticker} not found")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    try:
        mgr = KISMasterFileManager()

        # Test Shanghai Stock Exchange (SSE)
        shanghai_tickers = {
            '600519': 'Kweichow Moutai (Expected: 100)',
            '600036': 'China Merchants Bank (Expected: 100)',
            '601318': 'Ping An Insurance (Expected: 100)',
            '600887': 'Yili Group (Expected: 100)',
        }

        test_market(mgr, 'shs', 'Shanghai Stock Exchange (SSE)', shanghai_tickers)

        print("\n" + "="*80 + "\n")

        # Test Shenzhen Stock Exchange (SZSE)
        shenzhen_tickers = {
            '000858': 'Wuliangye Yibin (Expected: 100)',
            '000333': 'Midea Group (Expected: 100)',
            '000651': 'Gree Electric (Expected: 100)',
            '002594': 'BYD Company (Expected: 100)',
        }

        test_market(mgr, 'szs', 'Shenzhen Stock Exchange (SZSE)', shenzhen_tickers)  # Correct market_code

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
