"""
End-to-End Tests for KoreaAdapter

Tests complete workflow from scanning to data collection to database verification.

Author: Spock Trading System
"""

import unittest
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.market_adapters import KoreaAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestKoreaAdapterE2E(unittest.TestCase):
    """End-to-end integration tests for KoreaAdapter"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once before all tests"""
        # Load environment variables
        load_dotenv()

        cls.kis_app_key = os.getenv('KIS_APP_KEY')
        cls.kis_app_secret = os.getenv('KIS_APP_SECRET')

        if not cls.kis_app_key or not cls.kis_app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET must be set in .env")

        # Initialize database
        cls.db = SQLiteDatabaseManager(db_path='data/spock_local.db')

        # Initialize adapter
        cls.adapter = KoreaAdapter(
            db_manager=cls.db,
            kis_app_key=cls.kis_app_key,
            kis_app_secret=cls.kis_app_secret
        )

        print("\n" + "=" * 80)
        print("KOREA ADAPTER - END-TO-END TEST")
        print("=" * 80)

    def test_e2e_stock_workflow(self):
        """E2E Test: Complete stock workflow"""
        print("\n📊 E2E Test: Complete Stock Workflow")
        print("-" * 80)

        # ========================================
        # Step 1: Health Check
        # ========================================
        print("\n[Step 1/5] Health Check...")
        health = self.adapter.health_check()
        self.assertTrue(any(health.values()), "At least one API should be healthy")
        print("✅ Health check passed")

        # ========================================
        # Step 2: Scan Stocks
        # ========================================
        print("\n[Step 2/5] Scanning stocks...")
        stocks = self.adapter.scan_stocks(force_refresh=True)
        self.assertGreater(len(stocks), 0, "Should find stocks")
        print(f"✅ Found {len(stocks)} stocks")

        # ========================================
        # Step 3: Verify Database (Tickers)
        # ========================================
        print("\n[Step 3/5] Verifying tickers in database...")
        db_stocks = self.db.get_tickers(region='KR', asset_type='STOCK', is_active=True)
        self.assertEqual(len(stocks), len(db_stocks), "Database should have all scanned stocks")

        # Check sample stock
        sample_stock = db_stocks[0]
        print(f"✅ Database verification passed")
        print(f"   Sample: {sample_stock['ticker']} - {sample_stock['name']} ({sample_stock['exchange']})")

        # ========================================
        # Step 4: Collect OHLCV (Sample)
        # ========================================
        print("\n[Step 4/5] Collecting OHLCV data for sample stocks...")
        test_tickers = [s['ticker'] for s in stocks[:5]]  # Top 5 stocks

        success_count = self.adapter.collect_stock_ohlcv(
            tickers=test_tickers,
            days=100
        )
        self.assertGreaterEqual(success_count, 3, "Should successfully collect data for at least 3 stocks")
        print(f"✅ Collected OHLCV for {success_count}/{len(test_tickers)} stocks")

        # ========================================
        # Step 5: Verify Database (OHLCV)
        # ========================================
        print("\n[Step 5/5] Verifying OHLCV data in database...")

        # Check first successful ticker
        for ticker in test_tickers:
            ohlcv_data = self.db.get_ohlcv(ticker, period_type='DAILY', limit=10)
            if ohlcv_data:
                row = ohlcv_data[0]
                print(f"✅ Database verification passed")
                print(f"   Ticker: {ticker}")
                print(f"   Latest: {row.get('date')}")
                print(f"   Close: {row.get('close'):,} KRW")
                print(f"   MA20: {row.get('ma20'):.2f}" if row.get('ma20') else "   MA20: N/A")
                print(f"   RSI: {row.get('rsi_14'):.2f}" if row.get('rsi_14') else "   RSI: N/A")
                break

        print("\n" + "=" * 80)
        print("✅ STOCK WORKFLOW COMPLETE")
        print("=" * 80)

    def test_e2e_etf_workflow(self):
        """E2E Test: Complete ETF workflow"""
        print("\n📊 E2E Test: Complete ETF Workflow")
        print("-" * 80)

        # ========================================
        # Step 1: Scan ETFs
        # ========================================
        print("\n[Step 1/5] Scanning ETFs...")
        etfs = self.adapter.scan_etfs(force_refresh=True)
        self.assertGreater(len(etfs), 0, "Should find ETFs")
        print(f"✅ Found {len(etfs)} ETFs")

        # ========================================
        # Step 2: Verify Database (Tickers)
        # ========================================
        print("\n[Step 2/5] Verifying ETF tickers in database...")
        db_etfs = self.db.get_tickers(region='KR', asset_type='ETF', is_active=True)
        self.assertEqual(len(etfs), len(db_etfs), "Database should have all scanned ETFs")

        # Check sample ETF
        sample_etf = db_etfs[0]
        print(f"✅ Database verification passed")
        print(f"   Sample: {sample_etf['ticker']} - {sample_etf['name']}")

        # ========================================
        # Step 3: Collect OHLCV (Sample)
        # ========================================
        print("\n[Step 3/5] Collecting OHLCV data for sample ETFs...")
        test_etfs = [e['ticker'] for e in etfs[:3]]  # Top 3 ETFs

        success_count = self.adapter.collect_etf_ohlcv(
            tickers=test_etfs,
            days=100
        )
        self.assertGreaterEqual(success_count, 1, "Should successfully collect data for at least 1 ETF")
        print(f"✅ Collected OHLCV for {success_count}/{len(test_etfs)} ETFs")

        # ========================================
        # Step 4: Collect ETF Details
        # ========================================
        print("\n[Step 4/5] Collecting ETF details...")
        details_count = self.adapter.collect_etf_details(tickers=test_etfs)
        print(f"✅ Collected details for {details_count}/{len(test_etfs)} ETFs")

        # ========================================
        # Step 5: Verify Database (ETF Details)
        # ========================================
        print("\n[Step 5/5] Verifying ETF details in database...")

        for ticker in test_etfs:
            etf_details = self.db.get_etf_details(ticker)
            if etf_details:
                print(f"✅ Database verification passed")
                print(f"   Ticker: {ticker}")
                print(f"   Issuer: {etf_details.get('issuer', 'N/A')}")
                print(f"   Tracking Index: {etf_details.get('tracking_index', 'N/A')}")
                print(f"   Expense Ratio: {etf_details.get('expense_ratio', 'N/A')}%")
                break

        print("\n" + "=" * 80)
        print("✅ ETF WORKFLOW COMPLETE")
        print("=" * 80)

    def test_e2e_full_workflow(self):
        """E2E Test: Full system workflow with statistics"""
        print("\n📊 E2E Test: Full System Workflow")
        print("-" * 80)

        # ========================================
        # Collect Statistics
        # ========================================
        print("\n[Statistics] Collecting system statistics...")

        # Count tickers
        total_stocks = len(self.db.get_tickers(region='KR', asset_type='STOCK', is_active=True))
        total_etfs = len(self.db.get_tickers(region='KR', asset_type='ETF', is_active=True))

        # Count OHLCV records
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM ohlcv_data
            WHERE ticker IN (
                SELECT ticker FROM tickers WHERE region = 'KR' AND asset_type = 'STOCK'
            )
        """)
        stocks_with_ohlcv = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM ohlcv_data
            WHERE ticker IN (
                SELECT ticker FROM tickers WHERE region = 'KR' AND asset_type = 'ETF'
            )
        """)
        etfs_with_ohlcv = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE ticker IN (
                SELECT ticker FROM tickers WHERE region = 'KR'
            )
        """)
        total_ohlcv_records = cursor.fetchone()[0]

        conn.close()

        # ========================================
        # Print Summary
        # ========================================
        print("\n" + "=" * 80)
        print("SYSTEM STATISTICS")
        print("=" * 80)
        print(f"Total Stocks: {total_stocks}")
        print(f"Total ETFs: {total_etfs}")
        print(f"Stocks with OHLCV: {stocks_with_ohlcv} ({stocks_with_ohlcv/total_stocks*100:.1f}%)" if total_stocks > 0 else "Stocks with OHLCV: 0")
        print(f"ETFs with OHLCV: {etfs_with_ohlcv} ({etfs_with_ohlcv/total_etfs*100:.1f}%)" if total_etfs > 0 else "ETFs with OHLCV: 0")
        print(f"Total OHLCV Records: {total_ohlcv_records:,}")
        print("=" * 80)

        # Assertions
        self.assertGreater(total_stocks, 0, "Should have stocks in database")
        self.assertGreater(total_etfs, 0, "Should have ETFs in database")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
