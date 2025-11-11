"""
Unit tests for cli/utils/ohlcv_loader.py - OHLCVLoader
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
from datetime import datetime, date


@pytest.mark.unit
class TestOHLCVLoader:
    """Test OHLCVLoader class"""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset OHLCVLoader cache before each test"""
        from cli.utils.ohlcv_loader import OHLCVLoader
        # Clear any cached data between tests
        yield

    @pytest.fixture
    def mock_db(self):
        """Mock database manager"""
        db = Mock()
        db.fetch = AsyncMock(return_value=[])
        return db

    @pytest.fixture
    def sample_ohlcv_records(self):
        """Sample OHLCV database records for single ticker"""
        return [
            {
                'date': date(2023, 1, 3),
                'ticker': '005930',
                'open': 60000,
                'high': 61000,
                'low': 59000,
                'close': 60500,
                'volume': 10000000
            },
            {
                'date': date(2023, 1, 4),
                'ticker': '005930',
                'open': 60500,
                'high': 62000,
                'low': 60000,
                'close': 61500,
                'volume': 12000000
            }
        ]

    @pytest.fixture
    def sample_multi_ticker_records(self):
        """Sample OHLCV database records for multiple tickers"""
        return [
            {
                'date': date(2023, 1, 3),
                'ticker': '005930',
                'open': 60000,
                'high': 61000,
                'low': 59000,
                'close': 60500,
                'volume': 10000000
            },
            {
                'date': date(2023, 1, 3),
                'ticker': '000660',
                'open': 50000,
                'high': 51000,
                'low': 49000,
                'close': 50500,
                'volume': 8000000
            },
            {
                'date': date(2023, 1, 4),
                'ticker': '005930',
                'open': 60500,
                'high': 62000,
                'low': 60000,
                'close': 61500,
                'volume': 12000000
            },
            {
                'date': date(2023, 1, 4),
                'ticker': '000660',
                'open': 50500,
                'high': 52000,
                'low': 50000,
                'close': 51500,
                'volume': 9000000
            }
        ]

    @pytest.mark.asyncio
    async def test_load_single_ticker(self, mock_db, sample_ohlcv_records):
        """Test loading OHLCV data for single ticker"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)
        df = await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'open' in df.columns
        assert 'close' in df.columns
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_multiple_tickers(self, mock_db, sample_multi_ticker_records):
        """Test loading OHLCV data for multiple tickers"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_multi_ticker_records

        loader = OHLCVLoader(mock_db)
        df = await loader.load_data(['005930', '000660'], '2023-01-01', '2023-12-31')

        assert isinstance(df, pd.DataFrame)
        assert isinstance(df.index, pd.MultiIndex)
        assert len(df) == 4  # 2 dates x 2 tickers
        assert 'open' in df.columns
        assert 'close' in df.columns

    @pytest.mark.asyncio
    async def test_cache_hit_doesnt_query_database(self, mock_db, sample_ohlcv_records):
        """Test that cache hit doesn't query database"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)

        # First call - should query database
        await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')
        assert mock_db.fetch.call_count == 1

        # Second call with same parameters - should use cache
        await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')
        assert mock_db.fetch.call_count == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_different_date_ranges_not_cached(self, mock_db, sample_ohlcv_records):
        """Test that different date ranges are not cached together"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)

        # First call
        await loader.load_single_ticker('005930', '2023-01-01', '2023-06-30')
        assert mock_db.fetch.call_count == 1

        # Second call with different date range
        await loader.load_single_ticker('005930', '2023-07-01', '2023-12-31')
        assert mock_db.fetch.call_count == 2  # Should query again

    @pytest.mark.asyncio
    async def test_empty_results_raises_error(self, mock_db):
        """Test that empty results raise ValueError"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = []

        loader = OHLCVLoader(mock_db)

        # Should raise ValueError when no data found
        with pytest.raises(ValueError, match="No data found"):
            await loader.load_single_ticker('INVALID', '2023-01-01', '2023-12-31')

    @pytest.mark.asyncio
    async def test_dataframe_has_correct_columns(self, mock_db, sample_ohlcv_records):
        """Test that DataFrame has correct OHLCV columns"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)
        df = await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')

        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            assert col in df.columns

    @pytest.mark.asyncio
    async def test_dataframe_indexed_by_date(self, mock_db, sample_ohlcv_records):
        """Test that DataFrame is indexed by date"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)
        df = await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')

        # Index should be datetime
        assert isinstance(df.index, pd.DatetimeIndex)

    @pytest.mark.asyncio
    async def test_cache_clear(self, mock_db, sample_ohlcv_records):
        """Test that cache can be cleared"""
        from cli.utils.ohlcv_loader import OHLCVLoader

        mock_db.fetch.return_value = sample_ohlcv_records

        loader = OHLCVLoader(mock_db)

        # Load data (will be cached)
        await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')
        assert mock_db.fetch.call_count == 1

        # Clear cache
        loader.clear_cache()

        # Load again (should query database)
        await loader.load_single_ticker('005930', '2023-01-01', '2023-12-31')
        assert mock_db.fetch.call_count == 2
