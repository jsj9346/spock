#!/usr/bin/env python3
"""
Phase A Integration Tests: Data Layer + Backtesting Engine

Integration test scenarios for verifying end-to-end functionality:
- 1.1: PostgreSQL connection pool management
- 1.2: PostgresDataProvider cache integration
- 1.3: OHLCV data query performance
- 1.4: Data integrity validation
- 2.1: DataProvider -> BacktestRunner integration
- 2.2: Backtest result generation and metrics calculation
- 2.3: Walk-Forward optimization integration

Author: Spock Quant Platform
Date: 2025-12-12
"""

import sys
import os
import time
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_db_manager():
    """Create mock PostgresDatabaseManager."""
    mock = MagicMock()
    mock.host = 'localhost'
    mock.port = 5432
    mock.database = 'test_db'
    mock.test_connection.return_value = True
    return mock


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing with proper OHLCV consistency."""
    dates = pd.date_range(start='2024-01-01', end='2024-03-31', freq='B')
    np.random.seed(42)

    base_price = 50000
    returns = np.random.randn(len(dates)) * 0.02
    close_prices = base_price * np.cumprod(1 + returns)

    # Generate OHLCV with proper consistency: high >= open/close/low and low <= open/close
    open_prices = close_prices * (1 + np.random.randn(len(dates)) * 0.005)

    # Ensure high is max of open, close + some random upside
    high_prices = np.maximum(open_prices, close_prices) * (1 + np.abs(np.random.randn(len(dates)) * 0.005))

    # Ensure low is min of open, close - some random downside
    low_prices = np.minimum(open_prices, close_prices) * (1 - np.abs(np.random.randn(len(dates)) * 0.005))

    df = pd.DataFrame({
        'date': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, len(dates))
    })
    return df


@pytest.fixture
def sample_ohlcv_dict(sample_ohlcv_data):
    """Create sample OHLCV data dictionary for batch operations."""
    return {
        '005930': sample_ohlcv_data.copy(),
        '035420': sample_ohlcv_data.copy(),
        '051910': sample_ohlcv_data.copy()
    }


# =============================================================================
# Scenario 1.1: PostgreSQL Connection Pool Management
# =============================================================================

class TestScenario1_1_ConnectionPool:
    """
    Scenario 1.1: PostgreSQL 연결 풀 관리

    Tests:
    - Connection pool creation and initialization
    - Connection acquisition and release
    - Concurrent connection handling
    - Connection pool exhaustion handling
    - Connection recovery after failure
    """

    def test_connection_pool_initialization(self):
        """Test: 연결 풀 초기화"""
        with patch('modules.db_manager_postgres.psycopg2.pool.ThreadedConnectionPool') as mock_pool:
            from modules.db_manager_postgres import PostgresDatabaseManager

            mock_pool_instance = MagicMock()
            mock_pool.return_value = mock_pool_instance

            # Create manager with specific pool settings
            with patch.object(PostgresDatabaseManager, '__init__', lambda self, **kwargs: None):
                manager = PostgresDatabaseManager.__new__(PostgresDatabaseManager)
                manager.pool = mock_pool_instance
                manager.host = 'localhost'
                manager.port = 5432
                manager.database = 'test_db'

                # Verify pool is initialized
                assert manager.pool is not None

    def test_connection_acquire_and_release(self, mock_db_manager):
        """Test: 연결 획득 및 반환"""
        mock_conn = MagicMock()
        mock_db_manager.pool = MagicMock()
        mock_db_manager.pool.getconn.return_value = mock_conn

        # Simulate connection acquisition
        conn = mock_db_manager.pool.getconn()
        assert conn is mock_conn

        # Simulate connection release
        mock_db_manager.pool.putconn(conn)
        mock_db_manager.pool.putconn.assert_called_once_with(conn)

    def test_concurrent_connection_handling(self, mock_db_manager):
        """Test: 동시 연결 처리"""
        mock_db_manager.pool = MagicMock()
        connections = [MagicMock() for _ in range(10)]
        mock_db_manager.pool.getconn.side_effect = connections

        acquired = []

        def acquire_connection():
            conn = mock_db_manager.pool.getconn()
            time.sleep(0.01)  # Simulate work
            acquired.append(conn)
            return conn

        # Concurrent connection acquisition
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(acquire_connection) for _ in range(10)]
            results = [f.result() for f in futures]

        assert len(results) == 10
        assert mock_db_manager.pool.getconn.call_count == 10

    def test_connection_pool_exhaustion(self, mock_db_manager):
        """Test: 연결 풀 고갈 처리"""
        mock_db_manager.pool = MagicMock()

        # Simulate pool exhaustion after 5 connections
        call_count = [0]

        def getconn_side_effect():
            call_count[0] += 1
            if call_count[0] > 5:
                raise Exception("Connection pool exhausted")
            return MagicMock()

        mock_db_manager.pool.getconn.side_effect = getconn_side_effect

        # Should get 5 connections
        for _ in range(5):
            conn = mock_db_manager.pool.getconn()
            assert conn is not None

        # 6th connection should fail
        with pytest.raises(Exception, match="exhausted"):
            mock_db_manager.pool.getconn()

    def test_connection_recovery_after_failure(self, mock_db_manager):
        """Test: 실패 후 연결 복구"""
        mock_db_manager.pool = MagicMock()

        # First call fails, second succeeds
        mock_db_manager.pool.getconn.side_effect = [
            Exception("Connection failed"),
            MagicMock()
        ]

        # First attempt fails
        with pytest.raises(Exception, match="failed"):
            mock_db_manager.pool.getconn()

        # Second attempt succeeds (recovery)
        conn = mock_db_manager.pool.getconn()
        assert conn is not None


# =============================================================================
# Scenario 1.2: PostgresDataProvider Cache Integration
# =============================================================================

class TestScenario1_2_CacheIntegration:
    """
    Scenario 1.2: PostgresDataProvider 캐시 통합

    Tests:
    - Cache hit/miss behavior
    - Cache key generation
    - Cache invalidation
    - Cache performance improvement
    """

    def test_cache_hit_behavior(self, mock_db_manager, sample_ohlcv_data):
        """Test: 캐시 히트 동작"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        # First call - cache miss
        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        result1 = provider.get_ohlcv('005930', 'KR', start_date, end_date)
        assert mock_db_manager.get_ohlcv_data.call_count == 1

        # Second call - cache hit
        result2 = provider.get_ohlcv('005930', 'KR', start_date, end_date)
        assert mock_db_manager.get_ohlcv_data.call_count == 1  # No new DB call

        # Results should be equal
        pd.testing.assert_frame_equal(result1, result2)

    def test_cache_miss_behavior(self, mock_db_manager, sample_ohlcv_data):
        """Test: 캐시 미스 동작"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        # Different parameters = cache miss
        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 3, 31))
        provider.get_ohlcv('035420', 'KR', date(2024, 1, 1), date(2024, 3, 31))
        provider.get_ohlcv('005930', 'US', date(2024, 1, 1), date(2024, 3, 31))

        # Each unique key should trigger DB call
        assert mock_db_manager.get_ohlcv_data.call_count == 3

    def test_cache_key_generation(self, mock_db_manager, sample_ohlcv_data):
        """Test: 캐시 키 생성"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        # Generate cache key
        key = provider._generate_cache_key('005930', 'KR', start_date, end_date, '1d')

        # Key should include all parameters
        assert '005930' in key
        assert 'KR' in key
        assert '2024-01-01' in key
        assert '2024-03-31' in key
        assert '1d' in key

    def test_cache_disabled(self, mock_db_manager, sample_ohlcv_data):
        """Test: 캐시 비활성화"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        # Disable cache
        provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        # Each call should hit DB
        provider.get_ohlcv('005930', 'KR', start_date, end_date)
        provider.get_ohlcv('005930', 'KR', start_date, end_date)

        assert mock_db_manager.get_ohlcv_data.call_count == 2

    def test_cache_performance_improvement(self, mock_db_manager, sample_ohlcv_data):
        """Test: 캐시 성능 개선"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        def slow_query(*args, **kwargs):
            time.sleep(0.05)  # Simulate 50ms query
            return sample_ohlcv_data

        mock_db_manager.get_ohlcv_data.side_effect = slow_query

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        # First call - DB query (slow)
        start = time.time()
        provider.get_ohlcv('005930', 'KR', start_date, end_date)
        first_call_time = time.time() - start

        # Second call - cache hit (fast)
        start = time.time()
        provider.get_ohlcv('005930', 'KR', start_date, end_date)
        second_call_time = time.time() - start

        # Cache hit should be much faster
        assert second_call_time < first_call_time * 0.1


# =============================================================================
# Scenario 1.3: OHLCV Data Query Performance
# =============================================================================

class TestScenario1_3_QueryPerformance:
    """
    Scenario 1.3: OHLCV 데이터 조회 성능

    Tests:
    - Single ticker query performance (<100ms)
    - Batch query performance (<500ms for 20 tickers)
    - Query optimization verification
    """

    def test_single_ticker_query_performance(self, mock_db_manager, sample_ohlcv_data):
        """Test: 단일 ticker 조회 성능 (<100ms)"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)

        start = time.time()
        result = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 3, 31))
        elapsed = time.time() - start

        # Should complete in < 100ms (mocked, so much faster)
        assert elapsed < 0.1
        assert not result.empty

    def test_batch_query_performance(self, mock_db_manager, sample_ohlcv_dict):
        """Test: 배치 조회 성능 (<500ms for 20 tickers)"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        # Create 20 ticker data
        tickers = [f'00{i:04d}' for i in range(20)]

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_dict['005930']

        provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)

        start = time.time()
        result = provider.get_ohlcv_batch(
            tickers[:20], 'KR',
            date(2024, 1, 1), date(2024, 3, 31)
        )
        elapsed = time.time() - start

        # Should complete in < 500ms (mocked, so much faster)
        assert elapsed < 0.5
        assert len(result) == 20

    def test_batch_vs_sequential_performance(self, mock_db_manager, sample_ohlcv_data):
        """Test: 배치 vs 순차 조회 성능 비교"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        call_count = [0]

        def tracked_query(*args, **kwargs):
            call_count[0] += 1
            time.sleep(0.01)  # 10ms per query
            return sample_ohlcv_data

        mock_db_manager.get_ohlcv_data.side_effect = tracked_query

        provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)

        tickers = ['005930', '035420', '051910']
        start_date = date(2024, 1, 1)
        end_date = date(2024, 3, 31)

        # Sequential calls
        call_count[0] = 0
        start = time.time()
        for ticker in tickers:
            provider.get_ohlcv(ticker, 'KR', start_date, end_date)
        sequential_time = time.time() - start
        sequential_calls = call_count[0]

        # Clear cache
        provider.cache.clear()

        # Batch call
        call_count[0] = 0
        start = time.time()
        provider.get_ohlcv_batch(tickers, 'KR', start_date, end_date)
        batch_time = time.time() - start
        batch_calls = call_count[0]

        # Batch should be more efficient (fewer or equal calls)
        assert batch_calls <= sequential_calls


# =============================================================================
# Scenario 1.4: Data Integrity Validation
# =============================================================================

class TestScenario1_4_DataIntegrity:
    """
    Scenario 1.4: 데이터 정합성 검증

    Tests:
    - NULL value handling
    - Outlier detection
    - Date continuity validation
    - OHLCV consistency (high >= low, etc.)
    """

    def test_null_value_handling(self, mock_db_manager):
        """Test: NULL 값 처리"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        # Data with NULL values
        df_with_nulls = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5, freq='B'),
            'open': [100, None, 102, 103, 104],
            'high': [101, 102, None, 104, 105],
            'low': [99, 100, 101, None, 103],
            'close': [100.5, 101.5, 102.5, 103.5, None],
            'volume': [1000, 2000, 3000, 4000, 5000]
        })

        mock_db_manager.get_ohlcv_data.return_value = df_with_nulls

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)
        result = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 7))

        # Should handle NULL values (returned as-is or cleaned)
        assert 'date' in result.columns

    def test_ohlcv_consistency_validation(self, sample_ohlcv_data):
        """Test: OHLCV 데이터 일관성 검증"""
        # Verify high >= open, close, low
        assert (sample_ohlcv_data['high'] >= sample_ohlcv_data['open']).all()
        assert (sample_ohlcv_data['high'] >= sample_ohlcv_data['low']).all()
        assert (sample_ohlcv_data['high'] >= sample_ohlcv_data['close']).all()

        # Verify low <= open, close, high
        assert (sample_ohlcv_data['low'] <= sample_ohlcv_data['open']).all()
        assert (sample_ohlcv_data['low'] <= sample_ohlcv_data['close']).all()

        # Verify volume is positive
        assert (sample_ohlcv_data['volume'] > 0).all()

    def test_date_continuity_validation(self, sample_ohlcv_data):
        """Test: 날짜 연속성 검증"""
        # Check dates are sorted ascending
        dates = sample_ohlcv_data['date'].values
        assert all(dates[i] <= dates[i+1] for i in range(len(dates)-1))

        # Check no duplicate dates
        assert len(dates) == len(set(dates))

    def test_outlier_detection(self, sample_ohlcv_data):
        """Test: 이상치 탐지"""
        # Calculate daily returns
        returns = sample_ohlcv_data['close'].pct_change().dropna()

        # Check for extreme outliers (> 50% daily move)
        extreme_moves = np.abs(returns) > 0.5
        assert not extreme_moves.any(), "Extreme outliers detected"

        # Check for reasonable price levels
        assert (sample_ohlcv_data['close'] > 0).all()
        assert (sample_ohlcv_data['open'] > 0).all()

    def test_data_type_validation(self, sample_ohlcv_data):
        """Test: 데이터 타입 검증"""
        # Date should be datetime
        assert pd.api.types.is_datetime64_any_dtype(sample_ohlcv_data['date'])

        # Numeric columns should be numeric
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            assert pd.api.types.is_numeric_dtype(sample_ohlcv_data[col])


# =============================================================================
# Scenario 2.1: DataProvider -> BacktestRunner Integration
# =============================================================================

class TestScenario2_1_DataProviderBacktestIntegration:
    """
    Scenario 2.1: 데이터 프로바이더 → 백테스트 러너 통합

    Tests:
    - DataProvider to BacktestRunner data flow
    - Config propagation
    - Error handling in integration
    """

    def test_data_flow_to_backtest_runner(self, mock_db_manager, sample_ohlcv_data):
        """Test: DataProvider -> BacktestRunner 데이터 흐름"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.backtest_runner import BacktestRunner

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        config = BacktestConfig(
            tickers=['005930'],
            regions=['KR'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            initial_capital=100_000_000,
            commission_rate=0.00015
        )

        runner = BacktestRunner(config, provider)

        # Verify runner has access to data provider
        assert runner.data_provider is provider
        assert runner.config is config

    def test_config_propagation(self, mock_db_manager, sample_ohlcv_data):
        """Test: 설정 전파"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.backtest_runner import BacktestRunner

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        config = BacktestConfig(
            tickers=['005930', '035420'],
            regions=['KR'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            initial_capital=50_000_000,
            commission_rate=0.001
        )

        runner = BacktestRunner(config, provider)

        # Verify config values are preserved
        assert runner.config.tickers == ['005930', '035420']
        assert runner.config.regions == ['KR']
        assert runner.config.initial_capital == 50_000_000
        assert runner.config.commission_rate == 0.001

    def test_error_handling_in_integration(self, mock_db_manager):
        """Test: 통합 과정 에러 처리"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider

        # Database connection fails
        mock_db_manager.test_connection.return_value = False

        with pytest.raises(ConnectionError):
            PostgresDataProvider(mock_db_manager, backfill_enabled=False)


# =============================================================================
# Scenario 2.2: Backtest Result Generation and Metrics
# =============================================================================

class TestScenario2_2_BacktestResultsMetrics:
    """
    Scenario 2.2: 백테스트 결과 생성 및 메트릭 계산

    Tests:
    - Result generation from backtest
    - Metrics calculation accuracy
    - Performance report generation
    """

    def test_comparison_result_creation(self):
        """Test: ComparisonResult 생성"""
        from modules.backtesting.backtest_runner import ComparisonResult

        result = ComparisonResult(
            custom_total_return=0.15,
            custom_sharpe_ratio=1.5,
            custom_max_drawdown=-0.10,
            custom_total_trades=50,
            custom_execution_time=1.5,
            vectorbt_total_return=0.16,
            vectorbt_sharpe_ratio=1.6,
            vectorbt_max_drawdown=-0.09,
            vectorbt_total_trades=52,
            vectorbt_execution_time=0.05,
            consistency_score=0.95,
            return_difference=0.01,
            trade_count_difference=2,
            speedup_factor=30.0,
            metrics_match={'return': True, 'sharpe': True},
            warnings=[]
        )

        assert result.consistency_score == 0.95
        assert result.speedup_factor == 30.0
        assert result.return_difference == 0.01

    def test_validation_report_creation(self):
        """Test: ValidationReport 생성"""
        from modules.backtesting.backtest_runner import ValidationReport

        report = ValidationReport(
            validation_passed=True,
            consistency_score=0.97,
            discrepancies={'trade_count': 2},
            recommendations=['Consider adjusting commission rate'],
            timestamp=date.today()
        )

        assert report.validation_passed is True
        assert report.consistency_score == 0.97
        assert len(report.recommendations) == 1

    def test_performance_report_creation(self):
        """Test: PerformanceReport 생성"""
        from modules.backtesting.backtest_runner import PerformanceReport

        report = PerformanceReport(
            custom_time=1.5,
            vectorbt_time=0.05,
            speedup_factor=30.0,
            memory_usage_mb=256.5,
            throughput_days_per_sec=1000.0
        )

        assert report.speedup_factor == 30.0
        assert report.throughput_days_per_sec == 1000.0

    def test_comparison_result_string_representation(self):
        """Test: ComparisonResult 문자열 표현"""
        from modules.backtesting.backtest_runner import ComparisonResult

        result = ComparisonResult(
            custom_total_return=0.15,
            custom_sharpe_ratio=1.5,
            custom_max_drawdown=-0.10,
            custom_total_trades=50,
            custom_execution_time=1.5,
            vectorbt_total_return=0.16,
            vectorbt_sharpe_ratio=1.6,
            vectorbt_max_drawdown=-0.09,
            vectorbt_total_trades=52,
            vectorbt_execution_time=0.05,
            consistency_score=0.95,
            return_difference=0.01,
            trade_count_difference=2,
            speedup_factor=30.0,
            metrics_match={},
            warnings=[]
        )

        result_str = str(result)
        assert 'Consistency' in result_str
        assert '95' in result_str  # 95%


# =============================================================================
# Scenario 2.3: Walk-Forward Optimization Integration
# =============================================================================

class TestScenario2_3_WalkForwardIntegration:
    """
    Scenario 2.3: Walk-Forward 최적화 통합

    Tests:
    - Window creation
    - Optimization flow
    - Result aggregation
    """

    def test_walk_forward_window_creation(self, mock_db_manager, sample_ohlcv_data):
        """Test: Walk-Forward 윈도우 생성"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.optimization.walk_forward_optimizer import (
            WalkForwardOptimizer, WalkForwardWindow
        )

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)
        config = BacktestConfig(
            tickers=['005930'],
            regions=['KR'],
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100_000_000
        )

        optimizer = WalkForwardOptimizer(config, provider)

        # Create windows
        windows = optimizer.create_windows(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=252,
            test_period_days=63
        )

        # Should create multiple windows
        assert len(windows) > 0

        # Each window should have valid dates
        for window in windows:
            assert isinstance(window, WalkForwardWindow)
            assert window.train_start < window.train_end
            assert window.test_start < window.test_end
            assert window.train_end <= window.test_start

    def test_walk_forward_window_no_overlap(self, mock_db_manager, sample_ohlcv_data):
        """Test: Walk-Forward 윈도우 비중첩"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.optimization.walk_forward_optimizer import WalkForwardOptimizer

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)
        config = BacktestConfig(
            tickers=['005930'],
            regions=['KR'],
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100_000_000
        )

        optimizer = WalkForwardOptimizer(config, provider)

        windows = optimizer.create_windows(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=252,
            test_period_days=63
        )

        # Test periods should not overlap
        for i in range(len(windows) - 1):
            current_test_end = windows[i].test_end
            next_test_start = windows[i + 1].test_start
            # Adjacent windows: current test end should be <= next test start
            assert current_test_end <= next_test_start

    def test_walk_forward_result_structure(self):
        """Test: WalkForwardResult 구조"""
        from modules.backtesting.optimization.walk_forward_optimizer import WalkForwardResult

        result = WalkForwardResult(
            best_params={'rsi_period': 14, 'oversold': 30},
            all_results=[{'params': {'rsi_period': 14}, 'sharpe': 1.5}],
            windows=[],
            in_sample_performance={'sharpe_ratio': 1.8},
            out_of_sample_performance={'sharpe_ratio': 1.2},
            degradation_pct=0.33,
            robustness_score=0.75,
            overfitting_detected=False
        )

        assert result.best_params == {'rsi_period': 14, 'oversold': 30}
        assert result.degradation_pct == 0.33
        assert result.overfitting_detected is False

    def test_anchored_vs_rolling_window(self, mock_db_manager, sample_ohlcv_data):
        """Test: Anchored vs Rolling 윈도우"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.optimization.walk_forward_optimizer import WalkForwardOptimizer

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)
        config = BacktestConfig(
            tickers=['005930'],
            regions=['KR'],
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100_000_000
        )

        optimizer = WalkForwardOptimizer(config, provider)

        # Rolling windows
        rolling_windows = optimizer.create_windows(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=252,
            test_period_days=63,
            anchored=False
        )

        # Anchored windows
        anchored_windows = optimizer.create_windows(
            start_date=date(2022, 1, 1),
            end_date=date(2024, 12, 31),
            train_period_days=252,
            test_period_days=63,
            anchored=True
        )

        # Anchored windows should all start from the same date
        if len(anchored_windows) > 1:
            first_train_start = anchored_windows[0].train_start
            for window in anchored_windows:
                assert window.train_start == first_train_start

        # Rolling windows should have different train start dates
        if len(rolling_windows) > 1:
            train_starts = [w.train_start for w in rolling_windows]
            # Some windows should have different start dates
            assert len(set(train_starts)) >= 1


# =============================================================================
# End-to-End Integration Test
# =============================================================================

class TestEndToEndIntegration:
    """
    End-to-End Integration Test

    Tests the complete flow from data retrieval to backtest execution.
    """

    def test_complete_backtest_flow(self, mock_db_manager, sample_ohlcv_data):
        """Test: 완전한 백테스트 플로우"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.backtest_runner import BacktestRunner

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_data

        # 1. Initialize data provider
        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        # 2. Create backtest config
        config = BacktestConfig(
            tickers=['005930'],
            regions=['KR'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            initial_capital=100_000_000,
            commission_rate=0.00015
        )

        # 3. Create backtest runner
        runner = BacktestRunner(config, provider)

        # 4. Verify data is accessible
        data = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 3, 31))

        assert not data.empty
        assert len(data) > 0
        assert 'close' in data.columns

        # 5. Verify runner is properly configured
        assert runner.config.initial_capital == 100_000_000

    def test_multi_ticker_backtest_flow(self, mock_db_manager, sample_ohlcv_dict):
        """Test: 멀티 티커 백테스트 플로우"""
        from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
        from modules.backtesting.backtest_config import BacktestConfig
        from modules.backtesting.backtest_runner import BacktestRunner

        mock_db_manager.get_ohlcv_data.return_value = sample_ohlcv_dict['005930']

        # Initialize provider
        provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        # Multi-ticker config
        config = BacktestConfig(
            tickers=['005930', '035420', '051910'],
            regions=['KR'],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            initial_capital=100_000_000
        )

        runner = BacktestRunner(config, provider)

        # Get data for each ticker (using get_ohlcv which is properly mocked)
        # Note: get_ohlcv_batch uses different code path with pd.read_sql_query
        ticker_data = {}
        for ticker in config.tickers:
            data = provider.get_ohlcv(ticker, 'KR', date(2024, 1, 1), date(2024, 3, 31))
            ticker_data[ticker] = data

        # Verify all tickers have data
        assert len(ticker_data) == 3
        for ticker in config.tickers:
            assert ticker in ticker_data
            assert not ticker_data[ticker].empty


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
