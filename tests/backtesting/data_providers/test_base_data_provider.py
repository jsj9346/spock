"""
Test BaseDataProvider Abstract Interface

Tests for the base data provider abstract class and its helper methods.

Usage:
    pytest tests/backtesting/data_providers/test_base_data_provider.py -v
"""

import pytest
import pandas as pd
from datetime import date
from typing import List, Dict, Optional

from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


# ============================================================================
# Mock Implementation for Testing
# ============================================================================

class MockDataProvider(BaseDataProvider):
    """
    Mock implementation of BaseDataProvider for testing abstract interface.
    """

    def __init__(self, cache_enabled: bool = True):
        super().__init__(cache_enabled=cache_enabled)
        self.call_count = {'ohlcv': 0, 'batch': 0, 'fundamentals': 0, 'indicators': 0, 'tickers': 0}

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """Mock OHLCV data retrieval."""
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        # Check cache FIRST (before incrementing counter)
        cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
        if self.cache_enabled and cache_key in self.cache:
            return self.cache[cache_key].copy()

        # Only increment counter for actual data retrieval (cache miss)
        self.call_count['ohlcv'] += 1

        # Generate mock data
        dates = pd.date_range(start_date, end_date, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000000
        })

        # Cache result
        if self.cache_enabled:
            self.cache[cache_key] = df.copy()

        return df

    def get_ohlcv_batch(
        self,
        tickers: List[str],
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> Dict[str, pd.DataFrame]:
        """Mock batch OHLCV data retrieval."""
        self.call_count['batch'] += 1
        result = {}
        for ticker in tickers:
            result[ticker] = self.get_ohlcv(ticker, region, start_date, end_date, timeframe)
        return result

    def get_fundamentals(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Mock fundamentals data retrieval."""
        self.call_count['fundamentals'] += 1
        dates = pd.date_range(start_date, end_date, freq='Q')
        return pd.DataFrame({
            'date': dates,
            'pe_ratio': 15.0,
            'pb_ratio': 1.5,
            'roe': 0.15
        })

    def get_technical_indicators(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Mock technical indicators retrieval."""
        self.call_count['indicators'] += 1
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'date': dates,
            'rsi': 50.0,
            'macd': 0.5
        })

    def get_available_tickers(
        self,
        region: str,
        start_date: date,
        end_date: date,
        min_volume: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> List[str]:
        """Mock available tickers retrieval."""
        self.call_count['tickers'] += 1
        return ['005930', '035420', '051910']


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_provider():
    """Create mock data provider with caching enabled."""
    return MockDataProvider(cache_enabled=True)


@pytest.fixture
def mock_provider_no_cache():
    """Create mock data provider with caching disabled."""
    return MockDataProvider(cache_enabled=False)


# ============================================================================
# Interface Validation Tests
# ============================================================================

class TestAbstractInterface:
    """Test abstract interface and inheritance."""

    def test_mock_implements_interface(self, mock_provider):
        """Test that mock provider implements BaseDataProvider interface."""
        assert isinstance(mock_provider, BaseDataProvider)
        assert hasattr(mock_provider, 'get_ohlcv')
        assert hasattr(mock_provider, 'get_ohlcv_batch')
        assert hasattr(mock_provider, 'get_fundamentals')
        assert hasattr(mock_provider, 'get_technical_indicators')
        assert hasattr(mock_provider, 'get_available_tickers')

    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseDataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseDataProvider(cache_enabled=True)


# ============================================================================
# Cache Mechanism Tests
# ============================================================================

class TestCacheMechanism:
    """Test caching functionality."""

    def test_cache_enabled_initialization(self, mock_provider):
        """Test provider initializes with caching enabled."""
        assert mock_provider.cache_enabled is True
        assert isinstance(mock_provider.cache, dict)
        assert len(mock_provider.cache) == 0

    def test_cache_disabled_initialization(self, mock_provider_no_cache):
        """Test provider initializes with caching disabled."""
        assert mock_provider_no_cache.cache_enabled is False
        assert isinstance(mock_provider_no_cache.cache, dict)

    def test_cache_hit_scenario(self, mock_provider):
        """Test that repeated queries return cached results."""
        # First query - cache miss
        df1 = mock_provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        call_count_after_first = mock_provider.call_count['ohlcv']

        # Second query - cache hit (should return cached data)
        df2 = mock_provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        # Verify cache was actually used (call count should still be same)
        assert mock_provider.call_count['ohlcv'] == call_count_after_first

        # Verify data is identical
        assert df1.equals(df2)

    def test_cache_miss_scenario(self, mock_provider):
        """Test that different queries miss cache."""
        # First query
        df1 = mock_provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_provider.call_count['ohlcv'] == 1

        # Different ticker - cache miss
        df2 = mock_provider.get_ohlcv('035420', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_provider.call_count['ohlcv'] == 2

        # Different date range - cache miss
        df3 = mock_provider.get_ohlcv('005930', 'KR', date(2024, 2, 1), date(2024, 2, 28))
        assert mock_provider.call_count['ohlcv'] == 3

    def test_cache_disabled_no_caching(self, mock_provider_no_cache):
        """Test that caching is disabled when configured."""
        # First query
        df1 = mock_provider_no_cache.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_provider_no_cache.call_count['ohlcv'] == 1

        # Second identical query - no caching
        df2 = mock_provider_no_cache.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_provider_no_cache.call_count['ohlcv'] == 2  # Increased (not cached)

    def test_clear_cache(self, mock_provider):
        """Test cache clearing functionality."""
        # Populate cache
        mock_provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        mock_provider.get_ohlcv('035420', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert len(mock_provider.cache) == 2

        # Clear cache
        mock_provider.clear_cache()
        assert len(mock_provider.cache) == 0

    def test_cache_statistics(self, mock_provider):
        """Test cache statistics reporting."""
        # Empty cache
        stats = mock_provider.get_cache_stats()
        assert stats['enabled'] is True
        assert stats['size'] == 0
        assert stats['memory_mb'] == 0

        # Populate cache
        mock_provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 12, 31))
        stats = mock_provider.get_cache_stats()
        assert stats['enabled'] is True
        assert stats['size'] == 1
        assert stats['memory_mb'] > 0


# ============================================================================
# Helper Method Tests
# ============================================================================

class TestHelperMethods:
    """Test helper methods."""

    def test_validate_date_range_valid(self, mock_provider):
        """Test date range validation with valid inputs."""
        # Should not raise
        mock_provider._validate_date_range(date(2024, 1, 1), date(2024, 12, 31))
        mock_provider._validate_date_range(date(2024, 1, 1), date(2024, 1, 1))  # Same date

    def test_validate_date_range_invalid(self, mock_provider):
        """Test date range validation with invalid inputs."""
        # Start after end
        with pytest.raises(ValueError, match="Invalid date range"):
            mock_provider._validate_date_range(date(2024, 12, 31), date(2024, 1, 1))

    def test_validate_ticker_valid(self, mock_provider):
        """Test ticker validation with valid inputs."""
        # Should not raise
        mock_provider._validate_ticker('005930', 'KR')
        mock_provider._validate_ticker('AAPL', 'US')

    def test_validate_ticker_invalid_empty(self, mock_provider):
        """Test ticker validation with empty ticker."""
        with pytest.raises(ValueError, match="Invalid ticker"):
            mock_provider._validate_ticker('', 'KR')

    def test_validate_ticker_invalid_region(self, mock_provider):
        """Test ticker validation with invalid region."""
        with pytest.raises(ValueError, match="Invalid region"):
            mock_provider._validate_ticker('005930', 'XX')

    def test_generate_cache_key_uniqueness(self, mock_provider):
        """Test that cache keys are unique for different parameters."""
        key1 = mock_provider._generate_cache_key(
            '005930', 'KR', date(2024, 1, 1), date(2024, 12, 31), '1d'
        )
        key2 = mock_provider._generate_cache_key(
            '035420', 'KR', date(2024, 1, 1), date(2024, 12, 31), '1d'
        )
        key3 = mock_provider._generate_cache_key(
            '005930', 'KR', date(2024, 1, 1), date(2024, 6, 30), '1d'
        )

        # All keys should be unique
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_generate_cache_key_with_data_type(self, mock_provider):
        """Test cache key generation with different data types."""
        key_ohlcv = mock_provider._generate_cache_key(
            '005930', 'KR', date(2024, 1, 1), date(2024, 12, 31), '1d', data_type='ohlcv'
        )
        key_fundamentals = mock_provider._generate_cache_key(
            '005930', 'KR', date(2024, 1, 1), date(2024, 12, 31), '1d', data_type='fundamentals'
        )

        # Different data types should have different keys
        assert key_ohlcv != key_fundamentals

    def test_repr(self, mock_provider):
        """Test string representation."""
        repr_str = repr(mock_provider)
        assert 'MockDataProvider' in repr_str
        assert 'cache_enabled=True' in repr_str
        assert 'cache_size=' in repr_str
