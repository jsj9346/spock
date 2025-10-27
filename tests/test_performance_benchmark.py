"""
Performance Benchmark Tests for Stage 1 Filtering

Tests filtering performance with various dataset sizes to validate:
- Execution time targets (<10s for 600 tickers)
- Memory usage (<500MB)
- CPU utilization (<30% average)
- Scalability (linear O(n) complexity)
"""

import unittest
import sqlite3
import os
import time
import sys
from datetime import datetime, timedelta
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available, memory/CPU metrics will be skipped")

from modules.stock_pre_filter import StockPreFilter


class TestPerformanceBenchmark(unittest.TestCase):
    """Performance benchmark tests for various dataset sizes"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once before all tests"""
        cls.test_db_path = 'data/test_performance_benchmark.db'
        cls.region = 'KR'
        cls.dataset_sizes = [100, 250, 600, 1000]

        # Create test database with all required tables
        cls._create_test_database()

        # Generate test datasets
        cls._generate_test_data()

    @classmethod
    def _create_test_database(cls):
        """Create test database with simplified schema"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

        conn = sqlite3.connect(cls.test_db_path)
        cursor = conn.cursor()

        # filter_cache_stage0 (matching stock_pre_filter expectations)
        cursor.execute("""
            CREATE TABLE filter_cache_stage0 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT,
                exchange TEXT,  -- Changed from 'market' to 'exchange'
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
                stage0_passed INTEGER DEFAULT 1,  -- Changed from 'passed_filters'
                PRIMARY KEY (ticker, region)
            )
        """)

        # ohlcv_data
        cursor.execute("""
            CREATE TABLE ohlcv_data (
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

        # filter_cache_stage1
        cursor.execute("""
            CREATE TABLE filter_cache_stage1 (
                ticker TEXT NOT NULL,
                region TEXT NOT NULL,
                name TEXT,
                stage1_score INTEGER,
                ma_alignment_score INTEGER,
                rsi_score INTEGER,
                macd_signal TEXT,
                volume_spike INTEGER,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ttl_seconds INTEGER DEFAULT 3600,
                PRIMARY KEY (ticker, region)
            )
        """)

        # filter_execution_log
        cursor.execute("""
            CREATE TABLE filter_execution_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_stage TEXT,
                region TEXT,
                input_count INTEGER,
                output_count INTEGER,
                execution_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        print(f"✅ Test database created: {cls.test_db_path}")

    @classmethod
    def _generate_test_data(cls):
        """Generate test data for all dataset sizes"""
        conn = sqlite3.connect(cls.test_db_path)
        cursor = conn.cursor()

        max_size = max(cls.dataset_sizes)
        base_date = datetime.now()

        print(f"\n🔄 Generating test data for {max_size} tickers...")

        stage0_data = []
        ohlcv_data = []

        for i in range(max_size):
            ticker = f"{i:06d}"

            # Vary characteristics for realistic distribution
            if i < max_size * 0.3:  # 30% good candidates
                base_price, trend = 50000, 1.001
                ma_good, rsi_base = True, 55
                macd_bullish, vol_mult = True, 1.8
            elif i < max_size * 0.6:  # 30% marginal
                base_price, trend = 30000, 1.0005
                ma_good = random.choice([True, False])
                rsi_base = random.choice([45, 65])
                macd_bullish = random.choice([True, False])
                vol_mult = random.choice([1.3, 1.6])
            else:  # 40% poor
                base_price, trend = 20000, 0.999
                ma_good, rsi_base = False, random.choice([25, 75])
                macd_bullish, vol_mult = False, 1.0

            # Stage 0 data (matching column order)
            stage0_data.append((
                ticker, cls.region, f'Stock_{ticker}', 'KOSPI',  # ticker, region, name, exchange
                random.randint(10_000_000_000, 10_000_000_000_000),  # market_cap_krw
                random.randint(1_000_000_000, 100_000_000_000),      # trading_value_krw
                int(base_price),                                      # current_price_krw
                random.randint(10_000_000_000, 10_000_000_000_000),  # market_cap_local
                random.randint(1_000_000_000, 100_000_000_000),      # trading_value_local
                base_price,                                           # current_price_local
                'KRW', 1.0,                                          # currency, exchange_rate_to_krw
                base_date.strftime('%Y-%m-%d'), 'test',              # exchange_rate_date, exchange_rate_source
                1                                                     # stage0_passed
            ))

            # Generate 250 days OHLCV
            for day in range(250):
                date = (base_date - timedelta(days=day)).strftime("%Y-%m-%d")
                price_var = base_price * (trend ** (250 - day))
                close = price_var * (1 + random.uniform(-0.02, 0.02))
                open_p = close * (1 + random.uniform(-0.01, 0.01))
                high = max(open_p, close) * (1 + random.uniform(0, 0.02))
                low = min(open_p, close) * (1 - random.uniform(0, 0.02))
                volume = int(10_000_000 * (1 + random.uniform(-0.3, 0.3)))

                # Most recent day: set indicators based on pattern
                if day == 0:
                    if ma_good:
                        ma5, ma20, ma60, ma120, ma200 = close, close*0.98, close*0.95, close*0.92, close*0.88
                    else:
                        ma5, ma20, ma60, ma120, ma200 = close*0.95, close, close*0.98, close*0.96, close*0.94
                    rsi = rsi_base + random.uniform(-5, 5)
                    macd, signal = (10.0, 8.0) if macd_bullish else (8.0, 10.0)
                    volume_ma20 = int(volume / vol_mult)
                else:
                    ma5 = close * (1 + random.uniform(-0.02, 0.02))
                    ma20 = close * (1 + random.uniform(-0.05, 0.00))
                    ma60 = close * (1 + random.uniform(-0.08, 0.00))
                    ma120 = close * (1 + random.uniform(-0.12, 0.00))
                    ma200 = close * (1 + random.uniform(-0.15, 0.00))
                    rsi = 50 + random.uniform(-20, 20)
                    macd = random.uniform(-5, 15)
                    signal = macd + random.uniform(-2, 2)
                    volume_ma20 = int(volume * random.uniform(0.8, 1.2))

                histogram = macd - signal

                ohlcv_data.append((
                    ticker, date,
                    round(open_p,2), round(high,2), round(low,2), round(close,2), volume,
                    round(ma5,2), round(ma20,2), round(ma60,2), round(ma120,2), round(ma200,2),
                    round(rsi,2), round(macd,2), round(signal,2), round(histogram,2),
                    volume_ma20
                ))

        # Batch insert
        cursor.executemany("""
            INSERT INTO filter_cache_stage0
            (ticker, region, name, exchange, market_cap_krw, trading_value_krw, current_price_krw,
             market_cap_local, trading_value_local, current_price_local, currency,
             exchange_rate_to_krw, exchange_rate_date, exchange_rate_source, stage0_passed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, stage0_data)

        cursor.executemany("""
            INSERT INTO ohlcv_data
            (ticker, date, open, high, low, close, volume,
             ma5, ma20, ma60, ma120, ma200, rsi, macd, macd_signal, macd_histogram, volume_ma20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ohlcv_data)

        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM filter_cache_stage0")
        s0_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        ohlcv_count = cursor.fetchone()[0]

        print(f"✅ Generated {s0_count} tickers with {ohlcv_count} OHLCV records")
        conn.close()

    def _run_benchmark(self, ticker_count: int):
        """
        Run benchmark for specified ticker count

        Returns:
            dict: Performance metrics (time, memory, cpu, results)
        """
        # Limit Stage 0 cache to ticker_count
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE filter_cache_stage0
            SET stage0_passed = CASE
                WHEN CAST(SUBSTR(ticker, 1, 6) AS INTEGER) < {ticker_count} THEN 1
                ELSE 0
            END
        """)
        conn.commit()
        conn.close()

        # Initialize filter
        pre_filter = StockPreFilter(db_path=self.test_db_path, region=self.region)

        # Measure performance
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            cpu_before = psutil.cpu_percent(interval=0.1)

        start_time = time.perf_counter()
        result_tickers = pre_filter.run_stage1_filter(force_refresh=True)
        end_time = time.perf_counter()

        execution_time = end_time - start_time

        if PSUTIL_AVAILABLE:
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            cpu_after = psutil.cpu_percent(interval=0.1)
            memory_used = mem_after - mem_before
            cpu_avg = (cpu_before + cpu_after) / 2
        else:
            memory_used = None
            cpu_avg = None

        return {
            'ticker_count': ticker_count,
            'execution_time': execution_time,
            'passed_count': len(result_tickers),
            'pass_rate': len(result_tickers) / ticker_count * 100 if ticker_count > 0 else 0,
            'memory_mb': memory_used,
            'cpu_percent': cpu_avg
        }

    def test_01_benchmark_100_tickers(self):
        """Benchmark: 100 tickers (small dataset)"""
        print("\n" + "="*70)
        print("📊 BENCHMARK: 100 Tickers")
        print("="*70)

        result = self._run_benchmark(100)

        print(f"⏱️  Execution Time: {result['execution_time']:.3f}s")
        print(f"✅ Passed: {result['passed_count']}/{result['ticker_count']} ({result['pass_rate']:.1f}%)")
        if result['memory_mb']:
            print(f"💾 Memory: {result['memory_mb']:.1f} MB")
            print(f"⚙️  CPU: {result['cpu_percent']:.1f}%")

        # Assertions
        self.assertLess(result['execution_time'], 5.0, "Should complete in <5s")
        if result['memory_mb']:
            self.assertLess(result['memory_mb'], 500, "Memory should be <500MB")

    def test_02_benchmark_250_tickers(self):
        """Benchmark: 250 tickers (medium dataset - Stage 1 target)"""
        print("\n" + "="*70)
        print("📊 BENCHMARK: 250 Tickers (Stage 1 Target Output)")
        print("="*70)

        result = self._run_benchmark(250)

        print(f"⏱️  Execution Time: {result['execution_time']:.3f}s")
        print(f"✅ Passed: {result['passed_count']}/{result['ticker_count']} ({result['pass_rate']:.1f}%)")
        if result['memory_mb']:
            print(f"💾 Memory: {result['memory_mb']:.1f} MB")
            print(f"⚙️  CPU: {result['cpu_percent']:.1f}%")

        self.assertLess(result['execution_time'], 7.0, "Should complete in <7s")

    def test_03_benchmark_600_tickers(self):
        """Benchmark: 600 tickers (large dataset - Stage 0 target)"""
        print("\n" + "="*70)
        print("📊 BENCHMARK: 600 Tickers (Stage 0 Target Input)")
        print("="*70)

        result = self._run_benchmark(600)

        print(f"⏱️  Execution Time: {result['execution_time']:.3f}s")
        print(f"✅ Passed: {result['passed_count']}/{result['ticker_count']} ({result['pass_rate']:.1f}%)")
        if result['memory_mb']:
            print(f"💾 Memory: {result['memory_mb']:.1f} MB")
            print(f"⚙️  CPU: {result['cpu_percent']:.1f}%")

        # Primary target
        self.assertLess(result['execution_time'], 10.0, "🎯 PRIMARY TARGET: Should complete in <10s")
        if result['memory_mb']:
            self.assertLess(result['memory_mb'], 500, "Memory should be <500MB")

    def test_04_benchmark_1000_tickers(self):
        """Benchmark: 1000 tickers (extra large - Phase 4 preparation)"""
        print("\n" + "="*70)
        print("📊 BENCHMARK: 1000 Tickers (Phase 4 Preparation)")
        print("="*70)

        result = self._run_benchmark(1000)

        print(f"⏱️  Execution Time: {result['execution_time']:.3f}s")
        print(f"✅ Passed: {result['passed_count']}/{result['ticker_count']} ({result['pass_rate']:.1f}%)")
        if result['memory_mb']:
            print(f"💾 Memory: {result['memory_mb']:.1f} MB")
            print(f"⚙️  CPU: {result['cpu_percent']:.1f}%")

        self.assertLess(result['execution_time'], 20.0, "Should complete in <20s")

    def test_05_scalability_verification(self):
        """Verify linear scalability O(n)"""
        print("\n" + "="*70)
        print("📈 SCALABILITY VERIFICATION (O(n) Complexity)")
        print("="*70)

        results = []
        for size in self.dataset_sizes:
            result = self._run_benchmark(size)
            results.append(result)
            print(f"  {size:4d} tickers: {result['execution_time']:.3f}s")

        # Check if execution time scales linearly
        # Compare 600 vs 100: should be ~6x
        ratio_600_100 = results[2]['execution_time'] / results[0]['execution_time']
        expected_ratio = 600 / 100  # 6.0

        print(f"\n📊 Scalability Analysis:")
        print(f"   100 tickers: {results[0]['execution_time']:.3f}s (baseline)")
        print(f"   600 tickers: {results[2]['execution_time']:.3f}s")
        print(f"   Ratio: {ratio_600_100:.2f}x (expected: {expected_ratio:.1f}x)")

        # Allow 20% deviation from linear scaling
        self.assertAlmostEqual(ratio_600_100, expected_ratio, delta=expected_ratio * 0.2,
                               msg="Execution time should scale linearly (±20%)")

        print(f"   ✅ Linear scalability confirmed (O(n))")

    @classmethod
    def tearDownClass(cls):
        """Cleanup test database"""
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)
            print(f"\n🧹 Cleaned up test database: {cls.test_db_path}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
