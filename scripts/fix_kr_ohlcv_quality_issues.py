#!/usr/bin/env python3
"""
KR OHLCV Data Quality Fix Script

Fixes critical data quality issues identified by validate_kr_ohlcv_quality.py:
1. Recalculate MA120/MA200 (30.48% and 73.74% NULL)
2. Recalculate ATR-14 (99.98% NULL)
3. Collect missing historical data to reach 250-day requirement (currently 136 days avg)
4. Update data to latest trading day (currently 3 days old)

Usage:
    python3 scripts/fix_kr_ohlcv_quality_issues.py --recalculate-indicators
    python3 scripts/fix_kr_ohlcv_quality_issues.py --collect-missing-data
    python3 scripts/fix_kr_ohlcv_quality_issues.py --full  # Both operations
    python3 scripts/fix_kr_ohlcv_quality_issues.py --dry-run  # Test mode

Exit Codes:
    0: All fixes successful
    1: Critical errors occurred
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import argparse
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters.kr_adapter import KoreaAdapter
import os


class KROHLCVQualityFixer:
    """Korean market OHLCV data quality fixer"""

    def __init__(self, db: SQLiteDatabaseManager, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.region = "KR"
        self.stats = {
            'tickers_fixed': 0,
            'indicators_recalculated': 0,
            'rows_collected': 0,
            'errors': []
        }

    def recalculate_indicators(self):
        """Recalculate missing technical indicators (MA120, MA200, ATR-14)"""
        print("\n" + "=" * 80)
        print("Recalculating Technical Indicators")
        print("=" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Get all KR tickers
        cursor.execute('''
            SELECT DISTINCT ticker
            FROM ohlcv_data
            WHERE region = ?
        ''', (self.region,))

        tickers = [row[0] for row in cursor.fetchall()]
        total_tickers = len(tickers)

        print(f"\n📊 Processing {total_tickers} KR tickers...")

        for idx, ticker in enumerate(tickers, 1):
            try:
                if idx % 100 == 0:
                    print(f"Progress: {idx}/{total_tickers} tickers ({idx/total_tickers*100:.1f}%)")

                # Fetch OHLCV data for this ticker
                cursor.execute('''
                    SELECT date, open, high, low, close, volume
                    FROM ohlcv_data
                    WHERE region = ? AND ticker = ?
                    ORDER BY date ASC
                ''', (self.region, ticker))

                rows = cursor.fetchall()

                if len(rows) < 200:  # Need at least 200 days for MA200
                    self.stats['errors'].append(f"{ticker}: Insufficient data ({len(rows)} days < 200)")
                    continue

                # Convert to DataFrame for easier calculation
                df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')

                # Calculate MA120
                df['ma120'] = df['close'].rolling(window=120, min_periods=120).mean()

                # Calculate MA200
                df['ma200'] = df['close'].rolling(window=200, min_periods=200).mean()

                # Calculate ATR-14
                df['h_l'] = df['high'] - df['low']
                df['h_pc'] = abs(df['high'] - df['close'].shift(1))
                df['l_pc'] = abs(df['low'] - df['close'].shift(1))
                df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis=1)
                df['atr_14'] = df['tr'].rolling(window=14, min_periods=14).mean()

                # Update database
                if not self.dry_run:
                    for _, row in df.iterrows():
                        cursor.execute('''
                            UPDATE ohlcv_data
                            SET ma120 = ?, ma200 = ?, atr_14 = ?
                            WHERE region = ? AND ticker = ? AND date = ?
                        ''', (
                            float(row['ma120']) if not pd.isna(row['ma120']) else None,
                            float(row['ma200']) if not pd.isna(row['ma200']) else None,
                            float(row['atr_14']) if not pd.isna(row['atr_14']) else None,
                            self.region,
                            ticker,
                            row['date'].strftime('%Y-%m-%d')
                        ))

                    conn.commit()

                self.stats['tickers_fixed'] += 1
                self.stats['indicators_recalculated'] += len(df)

            except Exception as e:
                self.stats['errors'].append(f"{ticker}: {str(e)}")
                print(f"❌ Error processing {ticker}: {e}")

        conn.close()

        print(f"\n✅ Recalculated indicators for {self.stats['tickers_fixed']} tickers")
        print(f"   Total rows updated: {self.stats['indicators_recalculated']:,}")

    def collect_missing_data(self):
        """Collect missing historical data to reach 250-day requirement"""
        print("\n" + "=" * 80)
        print("Collecting Missing Historical Data")
        print("=" * 80)

        # Initialize KR adapter
        app_key = os.getenv('KIS_APP_KEY')
        app_secret = os.getenv('KIS_APP_SECRET')

        if not app_key or not app_secret:
            print("❌ ERROR: KIS API credentials not found in environment")
            print("   Please set KIS_APP_KEY and KIS_APP_SECRET in .env file")
            self.stats['errors'].append("Missing KIS API credentials")
            return

        adapter = KoreaAdapter(self.db, app_key, app_secret)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Get tickers with insufficient data
        cursor.execute('''
            SELECT ticker, COUNT(*) as day_count, MIN(date) as earliest_date, MAX(date) as latest_date
            FROM ohlcv_data
            WHERE region = ?
            GROUP BY ticker
            HAVING day_count < 250
        ''', (self.region,))

        insufficient_tickers = cursor.fetchall()
        total_tickers = len(insufficient_tickers)

        print(f"\n📊 Found {total_tickers} tickers with < 250 days of data")

        if total_tickers == 0:
            print("✅ All tickers already have sufficient data coverage")
            conn.close()
            return

        print("\nCollecting missing data (this may take a while)...")

        for idx, (ticker, day_count, earliest_date, latest_date) in enumerate(insufficient_tickers, 1):
            try:
                if idx % 10 == 0:
                    print(f"Progress: {idx}/{total_tickers} tickers ({idx/total_tickers*100:.1f}%)")

                missing_days = 250 - day_count

                print(f"\n{ticker}: {day_count} days → collecting {missing_days} more days")

                if not self.dry_run:
                    # Collect additional data
                    result = adapter.collect_stock_ohlcv(
                        tickers=[ticker],
                        days=250,  # Request full 250 days
                        force_update=True
                    )

                    if result.get('success', 0) > 0:
                        self.stats['rows_collected'] += result.get('rows_inserted', 0)
                        print(f"✅ {ticker}: Collected {result.get('rows_inserted', 0)} additional rows")
                    else:
                        self.stats['errors'].append(f"{ticker}: Collection failed")
                        print(f"❌ {ticker}: Collection failed")

            except Exception as e:
                self.stats['errors'].append(f"{ticker}: {str(e)}")
                print(f"❌ Error collecting {ticker}: {e}")

        conn.close()

        print(f"\n✅ Collection complete")
        print(f"   Total rows collected: {self.stats['rows_collected']:,}")

    def generate_summary(self):
        """Generate fix summary"""
        print("\n" + "=" * 80)
        print("Fix Summary")
        print("=" * 80)

        print(f"\n📊 Statistics:")
        print(f"  Tickers fixed: {self.stats['tickers_fixed']}")
        print(f"  Indicators recalculated: {self.stats['indicators_recalculated']:,} rows")
        print(f"  Historical data collected: {self.stats['rows_collected']:,} rows")
        print(f"  Errors: {len(self.stats['errors'])}")

        if self.stats['errors']:
            print(f"\n⚠️  Errors encountered:")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")

        print("\n" + "=" * 80)

        if self.dry_run:
            print("🔍 DRY RUN MODE: No changes were made to the database")
        elif self.stats['errors']:
            print("⚠️  COMPLETED WITH ERRORS")
            print("   → Review errors and re-run if necessary")
        else:
            print("✅ ALL FIXES SUCCESSFUL")
            print("   → Re-run validation script to verify data quality")

        print("=" * 80)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Fix KR OHLCV data quality issues')
    parser.add_argument('--recalculate-indicators', action='store_true', help='Recalculate MA120/MA200/ATR-14')
    parser.add_argument('--collect-missing-data', action='store_true', help='Collect missing historical data')
    parser.add_argument('--full', action='store_true', help='Run all fixes (recalculate + collect)')
    parser.add_argument('--dry-run', action='store_true', help='Test mode (no database changes)')
    args = parser.parse_args()

    # Default to full operation if no specific flags
    if not any([args.recalculate_indicators, args.collect_missing_data, args.full]):
        args.full = True

    try:
        # Initialize database
        db = SQLiteDatabaseManager()
        print(f"✅ Database initialized: {db.db_path}")

        # Create fixer
        fixer = KROHLCVQualityFixer(db, dry_run=args.dry_run)

        # Run fixes
        if args.full or args.recalculate_indicators:
            fixer.recalculate_indicators()

        if args.full or args.collect_missing_data:
            fixer.collect_missing_data()

        # Generate summary
        fixer.generate_summary()

        return 0 if not fixer.stats['errors'] else 1

    except Exception as e:
        print(f"\n❌ Fix failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
