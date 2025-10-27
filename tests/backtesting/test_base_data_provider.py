"""
Unit Tests for BaseDataProvider

Tests:
    - Abstract interface contract
    - Cache functionality
    - Input validation
    - Error handling
    - Performance characteristics

Coverage Target: >95%

Author: Spock Quant Platform
Date: 2025-10-26
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional

from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


# Mock implementation for testing abstract base class
class MockDataProvider(BaseDataProvider):
    """Mock data provider for testing abstract interface."""

    def __init__(self, cache_enabled: bool = True):
        super().__init__(cache_enabled=cache_enabled)
        self.call_count = {
            'get_ohlcv': 0,
            'get_ohlcv_batch': 0,
            'get_fundamentals': 0,
            'get_technical_indicators': 0,
            'get_available_tickers': 0
        }

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """Mock OHLCV data generation."""
        self._validate_ticker(ticker, region)
        self._validate_date_range(start_date, end_date)

        # Check cache first
        cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
        if self.cache_enabled and cache_key in self.cache:
            return self.cache[cache_key].copy()

        # Increment call count only for cache miss
        self.call_count['get_ohlcv'] += 1

        # Generate mock data with proper datetime conversion
        dates = pd.date_range(start_date, end_date, freq='D')
        df = pd.DataFrame({
            'date': pd.to_datetime(dates),  # Convert to proper datetime
            'open': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'close': 50500.0,
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
        """Mock batch OHLCV data generation."""
        self.call_count['get_ohlcv_batch'] += 1
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
        """Mock fundamental data generation."""
        self.call_count['get_fundamentals'] += 1
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'date': dates,
            'pe_ratio': 15.0,
            'pb_ratio': 1.2,
            'roe': 0.15,
            'debt_to_equity': 0.5
        })

    def get_technical_indicators(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Mock technical indicator generation."""
        self.call_count['get_technical_indicators'] += 1
        dates = pd.date_range(start_date, end_date, freq='D')
        return pd.DataFrame({
            'date': dates,
            'rsi': 50.0,
            'macd': 100.0,
            'bb_upper': 52000.0
        })

    def get_available_tickers(
        self,
        region: str,
        start_date: date,
        end_date: date,
        min_volume: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> List[str]:
        """Mock ticker list generation."""
        self.call_count['get_available_tickers'] += 1
        return ['005930', '035420', '051910']


class TestBaseDataProvider:
    """Test suite for BaseDataProvider abstract base class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.provider = MockDataProvider(cache_enabled=True)
        self.start_date = date(2020, 1, 1)
        self.end_date = date(2020, 12, 31)

    def test_initialization(self):
        """Test provider initialization."""
        provider = MockDataProvider(cache_enabled=True)
        assert provider.cache_enabled is True
        assert len(provider.cache) == 0

        provider_no_cache = MockDataProvider(cache_enabled=False)
        assert provider_no_cache.cache_enabled is False

    def test_get_ohlcv_returns_dataframe(self):
        """Test get_ohlcv returns DataFrame with correct structure."""
        df = self.provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']

    def test_get_ohlcv_date_range(self):
        """Test get_ohlcv respects date range."""
        df = self.provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        # Use iloc to avoid pandas/numpy version compatibility issue with min/max
        min_date = df['date'].iloc[0]
        max_date = df['date'].iloc[-1]

        assert min_date >= pd.Timestamp(self.start_date)
        assert max_date <= pd.Timestamp(self.end_date)

    def test_get_ohlcv_sorted_by_date(self):
        """Test get_ohlcv returns data sorted by date."""
        df = self.provider.get_ohlcv(
            ticker='005930',
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        assert df['date'].is_monotonic_increasing

    def test_get_ohlcv_batch(self):
        """Test get_ohlcv_batch returns data for all tickers."""
        tickers = ['005930', '035420', '051910']
        result = self.provider.get_ohlcv_batch(
            tickers=tickers,
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        assert isinstance(result, dict)
        assert len(result) == len(tickers)
        for ticker in tickers:
            assert ticker in result
            assert isinstance(result[ticker], pd.DataFrame)
            assert not result[ticker].empty

    def test_get_fundamentals_returns_dataframe(self):
        """Test get_fundamentals returns DataFrame with correct structure."""
        df = self.provider.get_fundamentals(
            ticker='005930',
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'date' in df.columns
        assert 'pe_ratio' in df.columns
        assert 'roe' in df.columns

    def test_get_technical_indicators_returns_dataframe(self):
        """Test get_technical_indicators returns DataFrame with correct structure."""
        df = self.provider.get_technical_indicators(
            ticker='005930',
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date,
            indicators=['rsi', 'macd']
        )

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'date' in df.columns
        assert 'rsi' in df.columns

    def test_get_available_tickers_returns_list(self):
        """Test get_available_tickers returns list of tickers."""
        tickers = self.provider.get_available_tickers(
            region='KR',
            start_date=self.start_date,
            end_date=self.end_date
        )

        assert isinstance(tickers, list)
        assert len(tickers) > 0
        assert all(isinstance(ticker, str) for ticker in tickers)

    def test_cache_functionality(self):
        """Test caching reduces redundant queries."""
        # First call (cache miss)
        df1 = self.provider.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        call_count_1 = self.provider.call_count['get_ohlcv']

        # Second call (cache hit)
        df2 = self.provider.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        call_count_2 = self.provider.call_count['get_ohlcv']

        # Cache should prevent second query
        assert call_count_1 == call_count_2
        pd.testing.assert_frame_equal(df1, df2)

    def test_cache_disabled(self):
        """Test caching can be disabled."""
        provider_no_cache = MockDataProvider(cache_enabled=False)

        # First call
        df1 = provider_no_cache.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        call_count_1 = provider_no_cache.call_count['get_ohlcv']

        # Second call (should query again)
        df2 = provider_no_cache.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        call_count_2 = provider_no_cache.call_count['get_ohlcv']

        # Should have two queries
        assert call_count_2 == call_count_1 + 1

    def test_clear_cache(self):
        """Test cache can be cleared."""
        # Populate cache
        self.provider.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        assert len(self.provider.cache) > 0

        # Clear cache
        self.provider.clear_cache()
        assert len(self.provider.cache) == 0

    def test_get_cache_stats(self):
        """Test cache statistics."""
        # Empty cache
        stats = self.provider.get_cache_stats()
        assert stats['enabled'] is True
        assert stats['size'] == 0

        # Populate cache
        self.provider.get_ohlcv('005930', 'KR', self.start_date, self.end_date)
        self.provider.get_ohlcv('035420', 'KR', self.start_date, self.end_date)

        stats = self.provider.get_cache_stats()
        assert stats['size'] == 2
        assert stats['memory_mb'] > 0

    def test_validate_date_range_valid(self):
        """Test date range validation accepts valid dates."""
        # Should not raise exception
        self.provider._validate_date_range(self.start_date, self.end_date)

    def test_validate_date_range_invalid(self):
        """Test date range validation rejects invalid dates."""
        with pytest.raises(ValueError, match="Invalid date range"):
            self.provider._validate_date_range(self.end_date, self.start_date)

    def test_validate_ticker_valid(self):
        """Test ticker validation accepts valid tickers."""
        # Should not raise exception
        self.provider._validate_ticker('005930', 'KR')
        self.provider._validate_ticker('AAPL', 'US')

    def test_validate_ticker_invalid_region(self):
        """Test ticker validation rejects invalid regions."""
        with pytest.raises(ValueError, match="Invalid region"):
            self.provider._validate_ticker('005930', 'INVALID')

    def test_validate_ticker_empty_ticker(self):
        """Test ticker validation rejects empty ticker."""
        with pytest.raises(ValueError, match="Invalid ticker"):
            self.provider._validate_ticker('', 'KR')

    def test_generate_cache_key_consistency(self):
        """Test cache key generation is consistent."""
        key1 = self.provider._generate_cache_key(
            '005930', 'KR', self.start_date, self.end_date, '1d', 'ohlcv'
        )
        key2 = self.provider._generate_cache_key(
            '005930', 'KR', self.start_date, self.end_date, '1d', 'ohlcv'
        )
        assert key1 == key2

    def test_generate_cache_key_uniqueness(self):
        """Test cache keys are unique for different parameters."""
        key1 = self.provider._generate_cache_key(
            '005930', 'KR', self.start_date, self.end_date, '1d', 'ohlcv'
        )
        key2 = self.provider._generate_cache_key(
            '035420', 'KR', self.start_date, self.end_date, '1d', 'ohlcv'
        )
        assert key1 != key2

    def test_repr(self):
        """Test string representation."""
        repr_str = repr(self.provider)
        assert 'MockDataProvider' in repr_str
        assert 'cache_enabled=True' in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=modules.backtesting.data_providers', '--cov-report=term-missing'])
