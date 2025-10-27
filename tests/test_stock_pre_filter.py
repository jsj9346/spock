"""
Unit Tests for StockPreFilter (Stage 1 Technical Pre-screen)

Tests technical filter logic, scoring system, and database integration.

Author: Spock Trading System
"""

import unittest
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.stock_pre_filter import StockPreFilter


class TestStockPreFilter(unittest.TestCase):
    """Unit tests for StockPreFilter"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once before all tests"""
        cls.test_db_path = 'data/test_spock.db'
        cls.region = 'KR'

        # Initialize test database
        cls._create_test_database()

        # Initialize StockPreFilter
        cls.pre_filter = StockPreFilter(db_path=cls.test_db_path, region=cls.region)

    @classmethod
    def _create_test_database(cls):
        """Create test database with required tables"""
        conn = sqlite3.connect(cls.test_db_path)
        cursor = conn.cursor()

        # Create filter_cache_stage0 table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT,
                market TEXT,
                market_cap_krw BIGINT,
                current_price_krw INTEGER,
                filter_score INTEGER,
                passed_filters INTEGER DEFAULT 1,
                cache_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, region)
            )
        """)

        # Create ohlcv_data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                ticker TEXT NOT NULL,
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
                rsi REAL,
                macd REAL,
                macd_signal REAL,
                macd_histogram REAL,
                volume_ma20 INTEGER,
                PRIMARY KEY (ticker, date)
            )
        """)

        # Create filter_cache_stage1 table (matching production schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                rsi_14 REAL,
                current_price_krw INTEGER,
                week_52_high_krw INTEGER,
                volume_3d_avg BIGINT,
                volume_10d_avg BIGINT,
                filter_date TEXT,
                data_start_date TEXT,
                data_end_date TEXT,
                stage1_passed BOOLEAN DEFAULT 1,
                filter_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, region)
            )
        """)

        # Create filter_execution_log table (matching production schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_execution_log (
                execution_date TEXT NOT NULL,
                stage INTEGER NOT NULL,
                region TEXT,
                input_count INTEGER,
                output_count INTEGER,
                reduction_rate REAL,
                execution_time_sec REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

    def setUp(self):
        """Setup before each test"""
        # Clear test data
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM filter_cache_stage0")
        cursor.execute("DELETE FROM ohlcv_data")
        cursor.execute("DELETE FROM filter_cache_stage1")
        cursor.execute("DELETE FROM filter_execution_log")
        conn.commit()
        conn.close()

    # ===================================
    # Test: MA Alignment Filter
    # ===================================

    def test_ma_alignment_perfect(self):
        """Test perfect MA alignment (5>20>60>120>200)"""
        print("\n🧪 Test: MA Alignment - Perfect")

        latest = {
            'ma5': 100.0,
            'ma20': 90.0,
            'ma60': 80.0,
            'ma120': 70.0,
            'ma200': 60.0
        }

        result = self.pre_filter._check_ma_alignment(latest)

        self.assertTrue(result['passed'], "Perfect MA alignment should pass")
        self.assertEqual(result['score'], 100, "Perfect MA alignment should score 100")
        self.assertEqual(result['reason'], '', "No failure reason for passing filter")

    def test_ma_alignment_partial(self):
        """Test partial MA alignment (5>20>60 only)"""
        print("\n🧪 Test: MA Alignment - Partial")

        latest = {
            'ma5': 100.0,
            'ma20': 90.0,
            'ma60': 80.0,
            'ma120': 85.0,  # Breaks alignment (60 < 120)
            'ma200': 70.0
        }

        result = self.pre_filter._check_ma_alignment(latest)

        self.assertTrue(result['passed'], "Partial MA alignment (5>20>60) should pass")
        self.assertEqual(result['score'], 75, "Partial MA alignment should score 75")

    def test_ma_alignment_failed(self):
        """Test failed MA alignment"""
        print("\n🧪 Test: MA Alignment - Failed")

        latest = {
            'ma5': 80.0,
            'ma20': 90.0,  # 5 < 20 (not aligned)
            'ma60': 85.0,
            'ma120': 75.0,
            'ma200': 70.0
        }

        result = self.pre_filter._check_ma_alignment(latest)

        self.assertFalse(result['passed'], "Bad MA alignment should fail")
        self.assertEqual(result['score'], 0, "Failed MA alignment should score 0")
        self.assertIn('MA 정배열 아님', result['reason'])

    def test_ma_alignment_missing_data(self):
        """Test MA alignment with missing data"""
        print("\n🧪 Test: MA Alignment - Missing Data")

        latest = {
            'ma5': 100.0,
            'ma20': 90.0,
            'ma60': None,  # Missing MA60
            'ma120': 70.0,
            'ma200': 60.0
        }

        result = self.pre_filter._check_ma_alignment(latest)

        self.assertFalse(result['passed'], "Missing MA data should fail")
        self.assertIn('MA 데이터 부족', result['reason'])

    # ===================================
    # Test: RSI Range Filter
    # ===================================

    def test_rsi_ideal(self):
        """Test RSI at ideal level (50)"""
        print("\n🧪 Test: RSI - Ideal (50)")

        latest = {'rsi': 50.0}
        config = {'rsi_min': 30, 'rsi_max': 70}

        result = self.pre_filter._check_rsi_range(latest, config)

        self.assertTrue(result['passed'], "RSI=50 should pass")
        self.assertEqual(result['score'], 100, "RSI=50 should score 100")

    def test_rsi_moderate(self):
        """Test RSI at moderate levels (40, 60)"""
        print("\n🧪 Test: RSI - Moderate")

        # RSI = 40
        latest_40 = {'rsi': 40.0}
        config = {'rsi_min': 30, 'rsi_max': 70}
        result_40 = self.pre_filter._check_rsi_range(latest_40, config)

        self.assertTrue(result_40['passed'], "RSI=40 should pass")
        self.assertEqual(result_40['score'], 80, "RSI=40 should score 80 (100 - |40-50|*2)")

        # RSI = 60
        latest_60 = {'rsi': 60.0}
        result_60 = self.pre_filter._check_rsi_range(latest_60, config)

        self.assertTrue(result_60['passed'], "RSI=60 should pass")
        self.assertEqual(result_60['score'], 80, "RSI=60 should score 80")

    def test_rsi_oversold(self):
        """Test RSI oversold condition (<30)"""
        print("\n🧪 Test: RSI - Oversold")

        latest = {'rsi': 25.0}
        config = {'rsi_min': 30, 'rsi_max': 70}

        result = self.pre_filter._check_rsi_range(latest, config)

        self.assertFalse(result['passed'], "RSI<30 should fail (oversold)")
        self.assertEqual(result['score'], 0)
        self.assertIn('RSI 과매도', result['reason'])

    def test_rsi_overbought(self):
        """Test RSI overbought condition (>70)"""
        print("\n🧪 Test: RSI - Overbought")

        latest = {'rsi': 75.0}
        config = {'rsi_min': 30, 'rsi_max': 70}

        result = self.pre_filter._check_rsi_range(latest, config)

        self.assertFalse(result['passed'], "RSI>70 should fail (overbought)")
        self.assertEqual(result['score'], 0)
        self.assertIn('RSI 과매수', result['reason'])

    def test_rsi_missing_data(self):
        """Test RSI with missing data"""
        print("\n🧪 Test: RSI - Missing Data")

        latest = {'rsi': None}
        config = {'rsi_min': 30, 'rsi_max': 70}

        result = self.pre_filter._check_rsi_range(latest, config)

        self.assertFalse(result['passed'], "Missing RSI should fail")
        self.assertIn('RSI 데이터 없음', result['reason'])

    # ===================================
    # Test: MACD Signal Filter
    # ===================================

    def test_macd_bullish(self):
        """Test MACD bullish crossover"""
        print("\n🧪 Test: MACD - Bullish")

        latest = {
            'macd': 10.0,
            'macd_signal': 8.0,
            'macd_histogram': 2.0
        }
        config = {}

        result = self.pre_filter._check_macd_signal(latest, config)

        self.assertTrue(result['passed'], "MACD>Signal and Histogram>0 should pass")
        self.assertEqual(result['signal'], 'BULLISH')

    def test_macd_bearish(self):
        """Test MACD bearish condition"""
        print("\n🧪 Test: MACD - Bearish")

        latest = {
            'macd': 8.0,
            'macd_signal': 10.0,  # MACD < Signal (bearish)
            'macd_histogram': -2.0
        }
        config = {}

        result = self.pre_filter._check_macd_signal(latest, config)

        self.assertFalse(result['passed'], "MACD<Signal should fail")
        self.assertEqual(result['signal'], 'BEARISH')
        self.assertIn('MACD 약세', result['reason'])

    def test_macd_missing_data(self):
        """Test MACD with missing data"""
        print("\n🧪 Test: MACD - Missing Data")

        latest = {
            'macd': None,
            'macd_signal': 8.0,
            'macd_histogram': 2.0
        }
        config = {}

        result = self.pre_filter._check_macd_signal(latest, config)

        self.assertFalse(result['passed'], "Missing MACD data should fail")
        self.assertEqual(result['signal'], 'UNKNOWN')
        self.assertIn('MACD 데이터 없음', result['reason'])

    # ===================================
    # Test: Volume Spike Filter
    # ===================================

    def test_volume_spike_detected(self):
        """Test volume spike detection (>1.5x)"""
        print("\n🧪 Test: Volume - Spike Detected")

        latest = {
            'volume': 20000000,  # 20M
            'volume_ma20': 10000000  # 10M (2x spike)
        }
        config = {'volume_spike_ratio': 1.5}

        result = self.pre_filter._check_volume_spike(latest, config)

        self.assertTrue(result['passed'], "Volume 2x > 1.5x threshold should pass")
        self.assertTrue(result['spike'])

    def test_volume_spike_not_detected(self):
        """Test no volume spike (<1.5x)"""
        print("\n🧪 Test: Volume - No Spike")

        latest = {
            'volume': 12000000,  # 12M
            'volume_ma20': 10000000  # 10M (1.2x, below 1.5x threshold)
        }
        config = {'volume_spike_ratio': 1.5}

        result = self.pre_filter._check_volume_spike(latest, config)

        self.assertFalse(result['passed'], "Volume 1.2x < 1.5x threshold should fail")
        self.assertFalse(result['spike'])
        self.assertIn('Volume 부족', result['reason'])

    def test_volume_spike_missing_data(self):
        """Test volume spike with missing data"""
        print("\n🧪 Test: Volume - Missing Data")

        latest = {
            'volume': None,
            'volume_ma20': 10000000
        }
        config = {'volume_spike_ratio': 1.5}

        result = self.pre_filter._check_volume_spike(latest, config)

        self.assertFalse(result['passed'], "Missing volume data should fail")
        self.assertIn('Volume 데이터 없음', result['reason'])

    # ===================================
    # Test: Price Above MA20 Filter
    # ===================================

    def test_price_above_ma20(self):
        """Test price above MA20 support"""
        print("\n🧪 Test: Price - Above MA20")

        latest = {
            'close': 50000.0,
            'ma20': 45000.0
        }

        result = self.pre_filter._check_price_above_ma20(latest)

        self.assertTrue(result['passed'], "Price>MA20 should pass")
        self.assertEqual(result['reason'], '')

    def test_price_below_ma20(self):
        """Test price below MA20 (failed)"""
        print("\n🧪 Test: Price - Below MA20")

        latest = {
            'close': 40000.0,
            'ma20': 45000.0
        }

        result = self.pre_filter._check_price_above_ma20(latest)

        self.assertFalse(result['passed'], "Price<MA20 should fail")
        self.assertIn('Price < MA20', result['reason'])

    def test_price_missing_data(self):
        """Test price check with missing data"""
        print("\n🧪 Test: Price - Missing Data")

        latest = {
            'close': None,
            'ma20': 45000.0
        }

        result = self.pre_filter._check_price_above_ma20(latest)

        self.assertFalse(result['passed'], "Missing price data should fail")
        self.assertIn('Price/MA20 데이터 없음', result['reason'])

    # ===================================
    # Test: Stage 1 Scoring Calculation
    # ===================================

    def test_stage1_score_perfect(self):
        """Test Stage 1 score with perfect filters"""
        print("\n🧪 Test: Stage 1 Score - Perfect")

        result = {
            'ma_alignment_score': 100,
            'rsi_score': 100,
            'macd_signal': 'BULLISH',
            'volume_spike': True
        }

        score = self.pre_filter._calculate_stage1_score(result)

        # All filters perfect: 100*0.3 + 100*0.25 + 100*0.2 + 100*0.15 + 100*0.1 = 100
        self.assertEqual(score, 100, "Perfect filters should score 100")

    def test_stage1_score_mixed(self):
        """Test Stage 1 score with mixed results"""
        print("\n🧪 Test: Stage 1 Score - Mixed")

        result = {
            'ma_alignment_score': 75,  # Partial alignment
            'rsi_score': 80,            # RSI=40 or 60
            'macd_signal': 'BULLISH',   # 100
            'volume_spike': False       # 0
        }

        score = self.pre_filter._calculate_stage1_score(result)

        # 75*0.3 + 80*0.25 + 100*0.2 + 0*0.15 + 100*0.1 = 22.5 + 20 + 20 + 0 + 10 = 72.5
        expected = int(75*0.3 + 80*0.25 + 100*0.2 + 0*0.15 + 100*0.1)
        self.assertEqual(score, expected, f"Mixed filters should score {expected}")

    # ===================================
    # Test: Database Integration
    # ===================================

    def test_save_to_cache(self):
        """Test saving Stage 1 results to cache"""
        print("\n🧪 Test: Save to Cache")

        test_tickers = [
            {
                'ticker': '005930',
                'ma5': 70500.0,
                'ma20': 69000.0,
                'ma60': 67000.0,
                'rsi_14': 57.5,
                'current_price_krw': 70000,
                'week_52_high_krw': 75000,
                'volume_3d_avg': 15000000,
                'volume_10d_avg': 12000000,
                'data_start_date': '2025-08-25',
                'data_end_date': '2025-10-10'
            }
        ]

        self.pre_filter._save_to_cache(test_tickers)

        # Verify saved data
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM filter_cache_stage1
            WHERE ticker = '005930' AND region = 'KR'
        """)

        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row, "Data should be saved to cache")
        self.assertEqual(row['ticker'], '005930')
        self.assertEqual(row['ma5'], 70500.0)
        self.assertEqual(row['ma20'], 69000.0)
        self.assertEqual(row['rsi_14'], 57.5)
        self.assertEqual(row['stage1_passed'], 1)

    def test_log_filter_execution(self):
        """Test logging filter execution"""
        print("\n�� Test: Log Filter Execution")

        self.pre_filter._log_filter_execution(
            input_count=600,
            output_count=250,
            execution_time_ms=4500
        )

        # Verify logged data
        conn = sqlite3.connect(self.test_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM filter_execution_log
            WHERE stage = 1 AND region = 'KR'
            ORDER BY created_at DESC LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row, "Execution should be logged")
        self.assertEqual(row['stage'], 1)
        self.assertEqual(row['input_count'], 600)
        self.assertEqual(row['output_count'], 250)
        self.assertAlmostEqual(row['reduction_rate'], 58.33, places=1)
        self.assertAlmostEqual(row['execution_time_sec'], 4.5, places=1)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
