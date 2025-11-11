"""
Test PostgresDataProvider Implementation

Tests for PostgreSQL + TimescaleDB data provider for backtesting engine.
Focuses on critical functionality: connection, queries, caching, batch operations.

Usage:
    pytest tests/backtesting/data_providers/test_postgres_data_provider.py -v
"""

import pytest
import pandas as pd
from datetime import date
from unittest.mock import Mock, MagicMock, patch
from contextlib import contextmanager

from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_manager():
    """Create mock PostgresDatabaseManager."""
    mock_db = Mock(spec=PostgresDatabaseManager)
    mock_db.host = 'localhost'
    mock_db.database = 'test_quant'
    mock_db.test_connection = Mock(return_value=True)

    # Mock connection context manager
    @contextmanager
    def mock_connection():
        conn_mock = Mock()
        yield conn_mock
    mock_db._get_connection = mock_connection

    return mock_db


@pytest.fixture
def mock_db_manager_failed():
    """Create mock PostgresDatabaseManager with failed connection."""
    mock_db = Mock(spec=PostgresDatabaseManager)
    mock_db.host = 'localhost'
    mock_db.database = 'test_quant'
    mock_db.test_connection = Mock(return_value=False)
    return mock_db


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV DataFrame."""
    dates = pd.date_range('2024-01-01', '2024-01-31', freq='D')
    return pd.DataFrame({
        'date': dates,
        'open': 75000.0,
        'high': 76000.0,
        'low': 74000.0,
        'close': 75500.0,
        'volume': 10000000
    })


# ============================================================================
# Connection Management Tests
# ============================================================================

class TestConnectionManagement:
    """Test database connection initialization and validation."""

    def test_valid_initialization(self, mock_db_manager):
        """Test successful initialization with valid db_manager."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        assert provider.db == mock_db_manager
        assert provider.cache_enabled is True
        assert provider.backfill_enabled is False
        mock_db_manager.test_connection.assert_called_once()

    def test_invalid_db_manager_none(self):
        """Test initialization fails with None db_manager."""
        with pytest.raises(ValueError, match="db_manager cannot be None"):
            PostgresDataProvider(None)

    def test_connection_test_failure(self, mock_db_manager_failed):
        """Test initialization fails when connection test fails."""
        with pytest.raises(ConnectionError, match="Cannot connect to PostgreSQL"):
            PostgresDataProvider(mock_db_manager_failed, backfill_enabled=False)

    def test_cache_enabled_parameter(self, mock_db_manager):
        """Test cache_enabled parameter is respected."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)
        assert provider.cache_enabled is False

    def test_repr_string(self, mock_db_manager):
        """Test string representation."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)
        repr_str = repr(provider)
        assert 'PostgresDataProvider' in repr_str
        assert 'localhost' in repr_str
        assert 'test_quant' in repr_str


# ============================================================================
# Query Execution Tests
# ============================================================================

class TestQueryExecution:
    """Test OHLCV and data query operations."""

    def test_get_ohlcv_success(self, mock_db_manager, sample_ohlcv_data):
        """Test successful OHLCV data retrieval."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        df = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        assert not df.empty
        assert len(df) == 31
        assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']
        mock_db_manager.get_ohlcv_data.assert_called_once()

    def test_get_ohlcv_empty_result(self, mock_db_manager):
        """Test OHLCV query with no results."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=pd.DataFrame())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        df = provider.get_ohlcv('999999', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        assert df.empty
        assert list(df.columns) == ['date', 'open', 'high', 'low', 'close', 'volume']

    def test_get_ohlcv_invalid_ticker(self, mock_db_manager):
        """Test OHLCV query with invalid ticker."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        with pytest.raises(ValueError, match="Invalid ticker"):
            provider.get_ohlcv('', 'KR', date(2024, 1, 1), date(2024, 1, 31))

    def test_get_ohlcv_invalid_region(self, mock_db_manager):
        """Test OHLCV query with invalid region."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        with pytest.raises(ValueError, match="Invalid region"):
            provider.get_ohlcv('005930', 'XX', date(2024, 1, 1), date(2024, 1, 31))

    def test_get_ohlcv_invalid_date_range(self, mock_db_manager):
        """Test OHLCV query with invalid date range (start > end)."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        with pytest.raises(ValueError, match="Invalid date range"):
            provider.get_ohlcv('005930', 'KR', date(2024, 12, 31), date(2024, 1, 1))


# ============================================================================
# Cache Operations Tests
# ============================================================================

class TestCacheOperations:
    """Test caching functionality specific to PostgresDataProvider."""

    def test_cache_hit_avoids_db_query(self, mock_db_manager, sample_ohlcv_data):
        """Test that cached queries don't hit database."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, cache_enabled=True, backfill_enabled=False)

        # First query - cache miss
        df1 = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_db_manager.get_ohlcv_data.call_count == 1

        # Second query - cache hit
        df2 = provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        assert mock_db_manager.get_ohlcv_data.call_count == 1  # Still 1 (cached)

        assert df1.equals(df2)

    def test_cache_miss_different_tickers(self, mock_db_manager, sample_ohlcv_data):
        """Test that different tickers miss cache."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, cache_enabled=True, backfill_enabled=False)

        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        provider.get_ohlcv('035420', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        assert mock_db_manager.get_ohlcv_data.call_count == 2

    def test_cache_disabled_always_queries(self, mock_db_manager, sample_ohlcv_data):
        """Test that disabled cache always queries database."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, cache_enabled=False, backfill_enabled=False)

        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))
        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        assert mock_db_manager.get_ohlcv_data.call_count == 2  # Not cached


# ============================================================================
# Batch Loading Tests
# ============================================================================

class TestBatchLoading:
    """Test batch query optimization."""

    def test_batch_query_optimization(self, mock_db_manager):
        """Test that batch query uses SQL IN clause."""
        # Create mock batch data
        batch_df = pd.DataFrame({
            'ticker': ['005930', '005930', '035420', '035420'],
            'date': pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-01', '2024-01-02']),
            'open': [75000.0, 75500.0, 200000.0, 201000.0],
            'high': [76000.0, 76500.0, 202000.0, 203000.0],
            'low': [74000.0, 74500.0, 199000.0, 200000.0],
            'close': [75500.0, 76000.0, 201000.0, 202000.0],
            'volume': [10000000, 11000000, 5000000, 5500000]
        })

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        with patch('pandas.read_sql_query', return_value=batch_df):
            result = provider.get_ohlcv_batch(
                ['005930', '035420'],
                'KR',
                date(2024, 1, 1),
                date(2024, 1, 31)
            )

        assert '005930' in result
        assert '035420' in result
        assert len(result['005930']) == 2
        assert len(result['035420']) == 2

    def test_batch_empty_tickers(self, mock_db_manager):
        """Test batch query with empty ticker list."""
        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        result = provider.get_ohlcv_batch([], 'KR', date(2024, 1, 1), date(2024, 1, 31))

        assert result == {}

    def test_batch_mixed_cached_uncached(self, mock_db_manager, sample_ohlcv_data):
        """Test batch query with mixed cached/uncached tickers."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        batch_df = pd.DataFrame({
            'ticker': ['035420', '035420'],
            'date': pd.to_datetime(['2024-01-01', '2024-01-02']),
            'open': [200000.0, 201000.0],
            'high': [202000.0, 203000.0],
            'low': [199000.0, 200000.0],
            'close': [201000.0, 202000.0],
            'volume': [5000000, 5500000]
        })

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, cache_enabled=True, backfill_enabled=False)

        # Cache first ticker
        provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))

        # Batch query with one cached, one uncached
        with patch('pandas.read_sql_query', return_value=batch_df):
            result = provider.get_ohlcv_batch(
                ['005930', '035420'],
                'KR',
                date(2024, 1, 1),
                date(2024, 1, 31)
            )

        assert '005930' in result
        assert '035420' in result


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and recovery."""

    def test_database_query_failure(self, mock_db_manager):
        """Test handling of database query failures."""
        mock_db_manager.get_ohlcv_data = Mock(side_effect=Exception("Database connection lost"))

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        with pytest.raises(Exception, match="Database connection lost"):
            provider.get_ohlcv('005930', 'KR', date(2024, 1, 1), date(2024, 1, 31))

    def test_fundamentals_query_failure(self, mock_db_manager):
        """Test that fundamentals query failure returns empty DataFrame."""
        mock_db_manager.get_fundamentals = Mock(side_effect=Exception("Query failed"))

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        df = provider.get_fundamentals('005930', 'KR', date(2024, 1, 1), date(2024, 12, 31))

        assert df.empty
        assert 'date' in df.columns

    def test_batch_query_fallback(self, mock_db_manager, sample_ohlcv_data):
        """Test batch query falls back to sequential on error."""
        mock_db_manager.get_ohlcv_data = Mock(return_value=sample_ohlcv_data.copy())

        with patch('modules.backtesting.data_providers.backfill_orchestrator.BackfillOrchestrator'):
            provider = PostgresDataProvider(mock_db_manager, backfill_enabled=False)

        # Mock batch query failure
        with patch('pandas.read_sql_query', side_effect=Exception("Batch query failed")):
            result = provider.get_ohlcv_batch(
                ['005930', '035420'],
                'KR',
                date(2024, 1, 1),
                date(2024, 1, 31)
            )

        # Should fall back to sequential queries
        assert '005930' in result
        assert '035420' in result
        assert mock_db_manager.get_ohlcv_data.call_count == 2  # Sequential fallback
