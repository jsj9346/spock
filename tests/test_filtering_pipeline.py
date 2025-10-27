"""
Integration Tests for Filtering Pipeline (Stage 0 → Stage 1)

Tests full pipeline integration with real database operations.

Author: Spock Trading System
"""

import unittest
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.scanner import StockScanner
from modules.stock_pre_filter import StockPreFilter


class TestFilteringPipeline(unittest.TestCase):
    """Integration tests for filtering pipeline"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once before all tests"""
        cls.test_db_path = 'data/test_pipeline.db'
        cls.region = 'KR'

        # Initialize test database with sample data
        cls._create_test_database()
        cls._insert_sample_data()

    @classmethod
    def _create_test_database(cls):
        """Create test database with all required tables"""
        conn = sqlite3.connect(cls.test_db_path)
        cursor = conn.cursor()

        # Create filter_cache_stage0
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT,
                exchange TEXT,
                market_cap_krw BIGINT,
                trading_value_krw BIGINT,
                current_price_krw INTEGER,
                market_cap_local REAL,
                trading_value_local REAL,
                current_price_local REAL,
                currency TEXT,
                exchange_rate_to_krw REAL DEFAULT 1.0,
                exchange_rate_date DATE,
                exchange_rate_source TEXT,
                stage0_passed INTEGER DEFAULT 1,
                failed_filters TEXT,
                stage0_score INTEGER,
                cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_source TEXT,
                PRIMARY KEY (ticker, region)
            )
        """)

        # Create ohlcv_data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                ticker TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                ma120 REAL,
                ma200 REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_hist REAL,
                volume_ma20 INTEGER,
                PRIMARY KEY (ticker, timeframe, date)
            )
        """)

        # Create filter_cache_stage1
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT,
                market TEXT,
                market_cap_krw BIGINT,
                current_price_krw INTEGER,
                stage0_score INTEGER,
                stage1_score INTEGER,
                ma_alignment_score INTEGER,
                rsi_score INTEGER,
                macd_signal TEXT,
                volume_spike INTEGER,
                passed_filters INTEGER DEFAULT 1,
                cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, region)
            )
        """)

        # Create filter_execution_log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_execution_log (
                execution_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                filter_stage INTEGER NOT NULL,
                region TEXT,
                input_count INTEGER,
                output_count INTEGER,
                reduction_rate REAL,
                execution_time_ms INTEGER,
                data_source TEXT
            )
        """)

        conn.commit()
        conn.close()

    @classmethod
    def _insert_sample_data(cls):
        """Insert sample test data"""
        conn = sqlite3.connect(cls.test_db_path)
        cursor = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().isoformat()

        # Sample Stage 0 data (5 tickers with varying characteristics)
        stage0_data = [
            # Ticker 1: Perfect alignment, good RSI, bullish MACD, volume spike
            ('005930', 'KR', '삼성전자', 'KOSPI', 500000000000000, 1000000000000,
             70000, 500000000000000.0, 1000000000000.0, 70000.0, 'KRW', 1.0,
             today, 'test', 1, '', 95, now, 'test'),

            # Ticker 2: Partial alignment, moderate RSI, bullish MACD, no volume spike
            ('000660', 'KR', 'SK하이닉스', 'KOSPI', 120000000000000, 500000000000,
             85000, 120000000000000.0, 500000000000.0, 85000.0, 'KRW', 1.0,
             today, 'test', 1, '', 90, now, 'test'),

            # Ticker 3: Bad alignment (should fail Stage 1)
            ('035720', 'KR', '카카오', 'KOSDAQ', 50000000000000, 300000000000,
             45000, 50000000000000.0, 300000000000.0, 45000.0, 'KRW', 1.0,
             today, 'test', 1, '', 85, now, 'test'),

            # Ticker 4: RSI overbought (should fail Stage 1)
            ('035420', 'KR', 'NAVER', 'KOSPI', 80000000000000, 400000000000,
             200000, 80000000000000.0, 400000000000.0, 200000.0, 'KRW', 1.0,
             today, 'test', 1, '', 88, now, 'test'),

            # Ticker 5: MACD bearish (should fail Stage 1)
            ('051910', 'KR', 'LG화학', 'KOSPI', 70000000000000, 350000000000,
             400000, 70000000000000.0, 350000000000.0, 400000.0, 'KRW', 1.0,
             today, 'test', 1, '', 87, now, 'test')
        ]

        cursor.executemany("""
            INSERT INTO filter_cache_stage0 (
                ticker, region, name, exchange,
                market_cap_krw, trading_value_krw, current_price_krw,
                market_cap_local, trading_value_local, current_price_local,
                currency, exchange_rate_to_krw, exchange_rate_date,
                exchange_rate_source, stage0_passed, failed_filters,
                stage0_score, cache_timestamp, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, stage0_data)

        # Insert 250 days of OHLCV data for each ticker
        ohlcv_data = []
        for ticker_info in stage0_data:
            ticker = ticker_info[0]

            # Determine characteristics based on ticker
            if ticker == '005930':  # Perfect case
                ma_values = [100, 90, 80, 70, 60]  # Perfect alignment
                rsi = 50.0  # Ideal
                macd, signal, histogram = 10.0, 8.0, 2.0  # Bullish
                volume, volume_ma20 = 20000000, 10000000  # 2x spike
            elif ticker == '000660':  # Partial alignment
                ma_values = [100, 90, 80, 85, 75]  # Partial alignment (breaks at ma120)
                rsi = 60.0  # Good
                macd, signal, histogram = 10.0, 8.0, 2.0  # Bullish
                volume, volume_ma20 = 16000000, 10000000  # 1.6x (spike!)
            elif ticker == '035720':  # Bad alignment
                ma_values = [80, 90, 85, 75, 70]  # Bad alignment (ma5 < ma20)
                rsi = 45.0
                macd, signal, histogram = 10.0, 8.0, 2.0  # Bullish
                volume, volume_ma20 = 15000000, 10000000  # 1.5x spike
            elif ticker == '035420':  # RSI overbought
                ma_values = [100, 90, 80, 70, 60]  # Perfect alignment
                rsi = 75.0  # Overbought
                macd, signal, histogram = 10.0, 8.0, 2.0  # Bullish
                volume, volume_ma20 = 15000000, 10000000  # 1.5x spike
            else:  # 051910 - MACD bearish
                ma_values = [100, 90, 80, 70, 60]  # Perfect alignment
                rsi = 50.0  # Good
                macd, signal, histogram = 8.0, 10.0, -2.0  # Bearish
                volume, volume_ma20 = 15000000, 10000000  # 1.5x spike

            # Insert 250 days
            for i in range(250):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                ohlcv_data.append((
                    ticker, date,
                    50000.0, 52000.0, 48000.0, 50000.0,  # OHLC
                    volume,
                    ma_values[0], ma_values[1], ma_values[2], ma_values[3], ma_values[4],  # MAs
                    rsi, macd, signal, histogram, volume_ma20
                ))

        # Add 'D' timeframe to each row
        ohlcv_data_with_timeframe = [(ticker, 'D', *rest) for ticker, *rest in ohlcv_data]

        cursor.executemany("""
            INSERT INTO ohlcv_data (
                ticker, timeframe, date, open, high, low, close, volume,
                ma5, ma20, ma60, ma120, ma200,
                rsi_14, macd, macd_signal, macd_hist, volume_ma20
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ohlcv_data_with_timeframe)

        conn.commit()

        # Verify OHLCV data insertion
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        total_rows = cursor.fetchone()[0]
        print(f"✅ Inserted {total_rows} OHLCV rows (expected: {5 * 250} = 1,250)")

        # Verify per-ticker counts
        cursor.execute("""
            SELECT ticker, COUNT(*) as row_count
            FROM ohlcv_data
            GROUP BY ticker
            ORDER BY ticker
        """)
        ticker_counts = cursor.fetchall()
        for ticker, count in ticker_counts:
            print(f"   - {ticker}: {count} rows")

        conn.close()

        # Validate insertion
        assert total_rows == 1250, f"Expected 1,250 OHLCV rows, got {total_rows}"

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

    # ===================================
    # Test: Pipeline Integration
    # ===================================

    def test_01_stage0_to_stage1_pipeline(self):
        """Test Stage 0 → Stage 1 filtering pipeline"""
        print("\n🔄 Test: Stage 0 → Stage 1 Pipeline Integration")

        # Initialize StockPreFilter with test database
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)

        # Run Stage 1 filter (force refresh to bypass cache)
        result_tickers = pre_filter.run_stage1_filter(force_refresh=True)

        # Expected results:
        # - 005930: PASS (perfect alignment, good RSI, bullish MACD, volume spike)
        # - 000660: PASS (partial alignment, moderate RSI, bullish MACD)
        # - 035720: FAIL (bad MA alignment)
        # - 035420: FAIL (RSI overbought)
        # - 051910: FAIL (MACD bearish)

        self.assertEqual(len(result_tickers), 2, "Should have 2 tickers passing Stage 1 (005930, 000660)")

        tickers = {t['ticker'] for t in result_tickers}
        self.assertIn('005930', tickers, "Samsung should pass Stage 1")
        self.assertIn('000660', tickers, "SK Hynix should pass Stage 1")
        self.assertNotIn('035720', tickers, "Kakao should fail (bad MA alignment)")
        self.assertNotIn('035420', tickers, "NAVER should fail (RSI overbought)")
        self.assertNotIn('051910', tickers, "LG Chem should fail (MACD bearish)")

    def test_02_filter_execution_logged(self):
        """Test filter execution is logged"""
        print("\n📊 Test: Filter Execution Logging")

        # Run Stage 1 filter
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)
        pre_filter.run_stage1_filter(force_refresh=True)

        # Check filter_execution_log
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM filter_execution_log
            WHERE filter_stage = 1 AND region = 'KR'
            ORDER BY execution_timestamp DESC LIMIT 1
        """)

        log = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(log, "Filter execution should be logged")
        self.assertEqual(log['input_count'], 5, "Should process 5 tickers from Stage 0")
        self.assertEqual(log['output_count'], 2, "Should output 2 tickers to Stage 1")
        self.assertAlmostEqual(log['reduction_rate'], 60.0, places=1, msg="Reduction rate should be 60%")

    def test_03_stage1_cache_populated(self):
        """Test Stage 1 cache is populated correctly"""
        print("\n💾 Test: Stage 1 Cache Population")

        # Run Stage 1 filter
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)
        pre_filter.run_stage1_filter(force_refresh=True)

        # Check filter_cache_stage1
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM filter_cache_stage1
            WHERE region = 'KR'
            ORDER BY stage1_score DESC
        """)

        cached = cursor.fetchall()
        conn.close()

        self.assertEqual(len(cached), 2, "Should have 2 tickers cached")

        # Check Samsung (005930) - should have highest score
        samsung = next((t for t in cached if t['ticker'] == '005930'), None)
        self.assertIsNotNone(samsung, "Samsung should be in cache")
        self.assertGreater(samsung['stage1_score'], 90, "Samsung should have high Stage 1 score")
        self.assertEqual(samsung['ma_alignment_score'], 100, "Samsung should have perfect MA alignment")
        self.assertEqual(samsung['macd_signal'], 'BULLISH', "Samsung should have bullish MACD")
        self.assertEqual(samsung['volume_spike'], 1, "Samsung should have volume spike")

        # Check SK Hynix (000660) - should have lower score
        sk_hynix = next((t for t in cached if t['ticker'] == '000660'), None)
        self.assertIsNotNone(sk_hynix, "SK Hynix should be in cache")
        self.assertLess(sk_hynix['stage1_score'], samsung['stage1_score'],
                       "SK Hynix should have lower score than Samsung")

    def test_04_stage1_cache_ttl(self):
        """Test Stage 1 cache TTL behavior"""
        print("\n⏰ Test: Stage 1 Cache TTL")

        # Run Stage 1 filter (first time - should cache)
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)
        result1 = pre_filter.run_stage1_filter(force_refresh=True)

        # Run again without force_refresh (should use cache)
        result2 = pre_filter.run_stage1_filter(force_refresh=False)

        self.assertEqual(len(result1), len(result2), "Cache should return same results")
        self.assertEqual(
            {t['ticker'] for t in result1},
            {t['ticker'] for t in result2},
            "Cache should contain same tickers"
        )

    def test_05_reduction_rate_verification(self):
        """Test reduction rate calculation (Stage 0 → Stage 1)"""
        print("\n📉 Test: Reduction Rate Verification")

        # Count Stage 0 tickers
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM filter_cache_stage0 WHERE region = 'KR'")
        stage0_count = cursor.fetchone()[0]

        # Run Stage 1 filter
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)
        result_tickers = pre_filter.run_stage1_filter(force_refresh=True)
        stage1_count = len(result_tickers)

        # Check reduction rate
        reduction_rate = (1 - stage1_count / stage0_count) * 100

        cursor.execute("""
            SELECT reduction_rate FROM filter_execution_log
            WHERE filter_stage = 1 AND region = 'KR'
            ORDER BY execution_timestamp DESC LIMIT 1
        """)
        logged_reduction = cursor.fetchone()[0]
        conn.close()

        self.assertAlmostEqual(reduction_rate, logged_reduction, places=1,
                              msg="Logged reduction rate should match actual")
        self.assertAlmostEqual(reduction_rate, 60.0, places=1,
                              msg="Reduction rate should be 60% (5 → 2 tickers)")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
