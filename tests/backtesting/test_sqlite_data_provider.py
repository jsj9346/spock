"""
Unit Tests for SQLiteDataProvider

Tests:
    - BaseDataProvider interface implementation
    - SQLite-specific queries and caching
    - Batch query optimization
    - Technical indicators loading
    - Integration with existing SQLite schema

Coverage Target: >90%

Author: Spock Quant Platform
Date: 2025-10-26
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from pathlib import Path

from modules.backtesting.data_providers.sqlite_data_provider import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestSQLiteDataProvider:
    """Test suite for SQLiteDataProvider."""

    @pytest.fixture(scope="class")
    def test_db_path(self):
        """Get test database path."""
        db_path = Path(__file__).parent.parent.parent / 'data' / 'spock_test_phase5.db'
        if not db_path.exists():
            pytest.skip(f"Test database not found: {db_path}")
        return str(db_path)

    @pytest.fixture(scope="class")
    def db_manager(self, test_db_path):
        """Create database manager for tests."""
        return SQLiteDatabaseManager(test_db_path)

    @pytest.fixture
    def provider(self, db_manager):
        """Create SQLite data provider for tests."""
        return SQLiteDataProvider(db_manager, cache_enabled=True)

    @pytest.fixture
    def provider_no_cache(self, db_manager):
        """Create SQLite data provider with caching disabled."""
        return SQLiteDataProvider(db_manager, cache_enabled=False)

    def test_initialization(self, db_manager):
        """Test provider initialization."""
        provider = SQLiteDataProvider(db_manager, cache_enabled=True)
        assert provider.db == db_manager
        assert provider.cache_enabled is True
        assert len(provider.cache) == 0

    def test_get_ohlcv_returns_dataframe(self, provider):
        """Test get_ohlcv returns DataFrame with correct structure."""
        df = provider.get_ohlcv(
            ticker='TIGER',
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
            ticker='TIGER',
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
            ticker='TIGER',
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
        ticker = 'TIGER'
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
            ticker='TIGER',
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

    def test_get_ohlcv_batch(self, provider):
        """Test get_ohlcv_batch returns data for multiple tickers."""
        tickers = ['TIGER']  # Use known ticker from test DB
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

    def test_get_technical_indicators(self, provider):
        """Test get_technical_indicators returns DataFrame."""
        df = provider.get_technical_indicators(
            ticker='TIGER',
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
            ticker='TIGER',
            region='KR',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            indicators=None  # Request all indicators
        )

        assert isinstance(df, pd.DataFrame)

    def test_get_fundamentals(self, provider):
        """Test get_fundamentals returns DataFrame."""
        df = provider.get_fundamentals(
            ticker='TIGER',
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

    def test_load_data_with_indicators(self, provider):
        """Test load_data_with_indicators loads OHLCV + indicators."""
        tickers = ['TIGER']
        result = provider.load_data_with_indicators(
            tickers=tickers,
            region='KR',
            start_date=date(2024, 2, 1),
            end_date=date(2024, 3, 31),
            lookback_days=60
        )

        assert isinstance(result, dict)
        if 'TIGER' in result:
            df = result['TIGER']
            assert isinstance(df, pd.DataFrame)
            # Should have date as index
            assert df.index.name == 'date' or 'date' in df.index.names

    def test_validate_ticker_invalid_region(self, provider):
        """Test _validate_ticker rejects invalid region."""
        with pytest.raises(ValueError, match="Invalid region"):
            provider._validate_ticker('TIGER', 'INVALID')

    def test_validate_date_range_invalid(self, provider):
        """Test _validate_date_range rejects invalid dates."""
        with pytest.raises(ValueError, match="Invalid date range"):
            provider._validate_date_range(date(2024, 12, 31), date(2024, 1, 1))

    def test_clear_cache(self, provider):
        """Test cache can be cleared."""
        # Populate cache
        provider.get_ohlcv('TIGER', 'KR', date(2024, 1, 1), date(2024, 3, 31))
        initial_cache_size = len(provider.cache)

        if initial_cache_size > 0:
            # Clear cache
            provider.clear_cache()
            assert len(provider.cache) == 0

    def test_get_cache_stats(self, provider):
        """Test get_cache_stats returns statistics."""
        # Populate cache
        provider.get_ohlcv('TIGER', 'KR', date(2024, 1, 1), date(2024, 3, 31))

        stats = provider.get_cache_stats()
        assert isinstance(stats, dict)
        assert 'enabled' in stats
        assert 'size' in stats
        assert 'memory_mb' in stats
        assert stats['enabled'] is True

    def test_repr(self, provider):
        """Test string representation."""
        repr_str = repr(provider)
        assert 'SQLiteDataProvider' in repr_str
        assert 'cache_enabled' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.backtesting.data_providers.sqlite_data_provider', '--cov-report=term-missing'])
