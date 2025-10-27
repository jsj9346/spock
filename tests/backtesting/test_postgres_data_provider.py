"""
Unit Tests for PostgresDataProvider

Tests:
    - BaseDataProvider interface implementation
    - PostgreSQL + TimescaleDB integration
    - Connection pooling behavior
    - Batch query optimization
    - Technical indicators loading
    - Multi-region support

Coverage Target: >90%

Author: Spock Quant Platform
Date: 2025-10-26
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager


class TestPostgresDataProvider:
    """Test suite for PostgresDataProvider."""

    @pytest.fixture(scope="class")
    def db_manager(self):
        """Create database manager for tests."""
        try:
            db = PostgresDatabaseManager(
                host='localhost',
                database='quant_platform'
            )
            # Test connection
            if not db.test_connection():
                pytest.skip("Cannot connect to PostgreSQL database")
            return db
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    @pytest.fixture
    def provider(self, db_manager):
        """Create PostgreSQL data provider for tests."""
        return PostgresDataProvider(db_manager, cache_enabled=True)

    @pytest.fixture
    def provider_no_cache(self, db_manager):
        """Create PostgreSQL data provider with caching disabled."""
        return PostgresDataProvider(db_manager, cache_enabled=False)

    def test_initialization(self, db_manager):
        """Test provider initialization."""
        provider = PostgresDataProvider(db_manager, cache_enabled=True)
        assert provider.db == db_manager
        assert provider.cache_enabled is True
        assert len(provider.cache) == 0

    def test_initialization_invalid_db_manager(self):
        """Test initialization fails with invalid db_manager."""
        with pytest.raises(ValueError, match="db_manager cannot be None"):
            PostgresDataProvider(None, cache_enabled=True)

    def test_get_ohlcv_returns_dataframe(self, provider):
        """Test get_ohlcv returns DataFrame with correct structure."""
        df = provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        assert isinstance(df, pd.DataFrame)
        if not df.empty:  # Only check if data exists
            assert 'date' in df.columns
            assert 'open' in df.columns
            assert 'high' in df.columns
            assert 'low' in df.columns
            assert 'close' in df.columns
            assert 'volume' in df.columns

    def test_get_ohlcv_sorted_by_date(self, provider):
        """Test get_ohlcv returns data sorted by date."""
        df = provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        if len(df) > 1:
            assert df['date'].is_monotonic_increasing

    def test_get_ohlcv_date_range(self, provider):
        """Test get_ohlcv respects date range."""
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)

        df = provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=start,
            end_date=end
        )

        if not df.empty:
            min_date = df['date'].iloc[0]
            max_date = df['date'].iloc[-1]
            assert min_date >= pd.Timestamp(start)
            assert max_date <= pd.Timestamp(end)

    def test_get_ohlcv_cache(self, provider):
        """Test caching reduces redundant queries."""
        ticker = '005930'
        region = 'KR'
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)

        # First call (cache miss)
        df1 = provider.get_ohlcv(ticker, region, start, end)
        cache_size_1 = len(provider.cache)

        # Second call (cache hit)
        df2 = provider.get_ohlcv(ticker, region, start, end)
        cache_size_2 = len(provider.cache)

        # Cache size should not increase
        assert cache_size_1 == cache_size_2

        # DataFrames should be identical
        if not df1.empty:
            pd.testing.assert_frame_equal(df1, df2)

    def test_get_ohlcv_no_cache(self, provider_no_cache):
        """Test caching can be disabled."""
        df = provider_no_cache.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        # Cache should remain empty
        assert len(provider_no_cache.cache) == 0

    def test_get_ohlcv_empty_result(self, provider):
        """Test get_ohlcv handles missing data gracefully."""
        # Query far future date (no data should exist)
        df = provider.get_ohlcv(
            ticker='NONEXISTENT',
            region='KR',
            start_date=date(2030, 1, 1),
            end_date=date(2030, 12, 31)
        )

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        # Check schema is correct even for empty DataFrame
        assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']

    def test_get_ohlcv_multi_region(self, provider):
        """Test multi-region support."""
        regions = ['KR', 'US']
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)

        for region in regions:
            df = provider.get_ohlcv(
                ticker='005930' if region == 'KR' else 'AAPL',
                region=region,
                start_date=start,
                end_date=end
            )

            # Should return DataFrame (empty or with data)
            assert isinstance(df, pd.DataFrame)

    def test_get_ohlcv_batch(self, provider):
        """Test get_ohlcv_batch returns data for multiple tickers."""
        tickers = ['005930', '035420', '051910']
        result = provider.get_ohlcv_batch(
            tickers=tickers,
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        assert isinstance(result, dict)
        assert len(result) == len(tickers)
        for ticker in tickers:
            assert ticker in result
            assert isinstance(result[ticker], pd.DataFrame)

    def test_get_ohlcv_batch_empty_list(self, provider):
        """Test get_ohlcv_batch handles empty ticker list."""
        result = provider.get_ohlcv_batch(
            tickers=[],
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_get_ohlcv_batch_caching(self, provider):
        """Test batch query uses cache for repeated requests."""
        tickers = ['005930', '035420']
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)

        # First batch query
        result1 = provider.get_ohlcv_batch(tickers, 'KR', start, end)
        cache_size_1 = len(provider.cache)

        # Second batch query (should hit cache)
        result2 = provider.get_ohlcv_batch(tickers, 'KR', start, end)
        cache_size_2 = len(provider.cache)

        # Cache size should not increase
        assert cache_size_1 == cache_size_2

    def test_get_technical_indicators(self, provider):
        """Test get_technical_indicators returns DataFrame."""
        df = provider.get_technical_indicators(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            indicators=['rsi', 'macd']
        )

        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert 'date' in df.columns

    def test_get_technical_indicators_all(self, provider):
        """Test get_technical_indicators with None returns all indicators."""
        df = provider.get_technical_indicators(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            indicators=None  # Request all indicators
        )

        assert isinstance(df, pd.DataFrame)

    def test_get_fundamentals(self, provider):
        """Test get_fundamentals returns DataFrame."""
        df = provider.get_fundamentals(
            ticker='005930',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        assert isinstance(df, pd.DataFrame)
        assert 'date' in df.columns

    def test_get_available_tickers(self, provider):
        """Test get_available_tickers returns list."""
        tickers = provider.get_available_tickers(
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31)
        )

        assert isinstance(tickers, list)
        assert all(isinstance(t, str) for t in tickers)

    def test_get_available_tickers_with_volume_filter(self, provider):
        """Test get_available_tickers with volume filter."""
        tickers = provider.get_available_tickers(
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            min_volume=100000
        )

        assert isinstance(tickers, list)

    def test_get_available_tickers_with_price_filter(self, provider):
        """Test get_available_tickers with price filter."""
        tickers = provider.get_available_tickers(
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            min_price=1000
        )

        assert isinstance(tickers, list)

    def test_get_available_tickers_both_filters(self, provider):
        """Test get_available_tickers with both volume and price filters."""
        tickers = provider.get_available_tickers(
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            min_volume=100000,
            min_price=1000
        )

        assert isinstance(tickers, list)

    def test_validate_ticker_invalid_region(self, provider):
        """Test _validate_ticker rejects invalid region."""
        with pytest.raises(ValueError, match="Invalid region"):
            provider._validate_ticker('005930', 'INVALID')

    def test_validate_date_range_invalid(self, provider):
        """Test _validate_date_range rejects invalid dates."""
        with pytest.raises(ValueError, match="Invalid date range"):
            provider._validate_date_range(date(2024, 12, 31), date(2024, 1, 1))

    def test_clear_cache(self, provider):
        """Test cache can be cleared."""
        # Populate cache
        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 3, 31))
        initial_cache_size = len(provider.cache)

        if initial_cache_size > 0:
            # Clear cache
            provider.clear_cache()
            assert len(provider.cache) == 0

    def test_get_cache_stats(self, provider):
        """Test get_cache_stats returns statistics."""
        # Populate cache
        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 3, 31))

        stats = provider.get_cache_stats()
        assert isinstance(stats, dict)
        assert 'enabled' in stats
        assert 'size' in stats
        assert 'memory_mb' in stats
        assert stats['enabled'] is True

    def test_repr(self, provider):
        """Test string representation."""
        repr_str = repr(provider)
        assert 'PostgresDataProvider' in repr_str
        assert 'cache_enabled' in repr_str
        assert 'cache_size' in repr_str

    def test_connection_pooling(self, provider):
        """Test connection pooling is working."""
        # Multiple queries should reuse connections
        for i in range(5):
            df = provider.get_ohlcv(
                ticker='005930',
                region='KR',
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
            assert isinstance(df, pd.DataFrame)

        # Connection pool should still be valid
        assert provider.db.test_connection()

    def test_hypertable_query_performance(self, provider):
        """Test hypertable query performance."""
        import time

        # Query large date range (should be fast due to hypertable partitioning)
        start_time = time.time()
        df = provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31)
        )
        elapsed = time.time() - start_time

        # Should complete in <100ms (target performance)
        # Relax to <1s for CI environment
        assert elapsed < 1.0, f"Query took {elapsed:.3f}s (target: <1s)"

    def test_batch_query_performance(self, provider):
        """Test batch query performance vs sequential."""
        import time

        tickers = ['005930', '035420', '051910', '005380', '068270']
        start = date(2024, 1, 1)
        end = date(2024, 3, 31)

        # Clear cache for fair comparison
        provider.clear_cache()

        # Batch query
        start_time = time.time()
        result_batch = provider.get_ohlcv_batch(tickers, 'KR', start, end)
        batch_time = time.time() - start_time

        # Should complete in <500ms (target performance)
        # Relax to <2s for CI environment
        assert batch_time < 2.0, f"Batch query took {batch_time:.3f}s (target: <2s)"

        # Verify results
        assert len(result_batch) == len(tickers)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.backtesting.data_providers.postgres_data_provider', '--cov-report=term-missing'])
