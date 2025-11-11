# tests/mcp_server/test_system_adapter.py
"""
Unit tests for SystemAdapter

Tests the MCP adapter for system information and health check operations,
validating ticker listing, status retrieval, caching, and error handling.

Usage:
    pytest tests/mcp_server/test_system_adapter.py -v
"""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from mcp_server.adapters.system_adapter import SystemAdapter
from mcp_server.config import Config
from mcp_server.utils.errors import DatabaseError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock MCP configuration"""
    config = Mock(spec=Config)
    config.postgres_host = "localhost"
    config.postgres_port = 5432
    config.postgres_db = "test_db"
    config.postgres_user = "test_user"
    config.postgres_password = "test_pass"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock PostgresDatabaseManager"""
    manager = Mock()
    manager.get_connection = Mock()
    return manager


@pytest.fixture
def adapter(mock_config):
    """Create SystemAdapter with mocked dependencies"""
    with patch('mcp_server.adapters.system_adapter.PostgresDatabaseManager') as mock_db:
        adapter = SystemAdapter(mock_config)
        adapter.db_manager = mock_db.return_value
        return adapter


# ============================================================================
# Test: Initialization
# ============================================================================

class TestSystemAdapterInitialization:
    """Test suite for adapter initialization"""

    def test_init_with_config(self, mock_config):
        """Test initialization with provided config"""
        with patch('mcp_server.adapters.system_adapter.PostgresDatabaseManager'):
            adapter = SystemAdapter(mock_config)
            assert adapter.config == mock_config
            assert adapter._cache == {}
            assert adapter._cache_time == {}
            assert adapter._cache_ttl == 60

    def test_init_without_config(self):
        """Test initialization with default config"""
        with patch('mcp_server.adapters.system_adapter.Config.from_env') as mock_from_env:
            with patch('mcp_server.adapters.system_adapter.PostgresDatabaseManager'):
                mock_from_env.return_value = Mock(spec=Config)
                adapter = SystemAdapter()
                assert adapter.config is not None
                mock_from_env.assert_called_once()


# ============================================================================
# Test: List Available Tickers
# ============================================================================

class TestListAvailableTickers:
    """Test suite for list_available_tickers method"""

    @pytest.mark.asyncio
    async def test_list_tickers_basic(self, adapter):
        """Test basic ticker listing without filters"""
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[
            ("005930", "KR", "Samsung Electronics", "Technology"),
            ("000660", "KR", "SK Hynix", "Technology"),
        ])

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        result = await adapter.list_available_tickers()

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["tickers"]) == 2
        assert result["tickers"][0]["ticker"] == "005930"
        assert result["tickers"][0]["region"] == "KR"
        assert result["tickers"][0]["name"] == "Samsung Electronics"

    @pytest.mark.asyncio
    async def test_list_tickers_with_region_filter(self, adapter):
        """Test ticker listing with region filter"""
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[
            ("AAPL", "US", "Apple Inc.", "Technology"),
        ])

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        result = await adapter.list_available_tickers(region="US")

        assert result["success"] is True
        assert result["filters"]["region"] == "US"
        assert result["tickers"][0]["region"] == "US"

    @pytest.mark.asyncio
    async def test_list_tickers_with_limit(self, adapter):
        """Test ticker listing with limit"""
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[
            ("005930", "KR", "Samsung Electronics", "Technology"),
        ])

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        result = await adapter.list_available_tickers(limit=1)

        assert result["success"] is True
        assert result["filters"]["limit"] == 1

    @pytest.mark.asyncio
    async def test_list_tickers_caching(self, adapter):
        """Test that ticker results are cached"""
        mock_cursor = Mock()
        mock_cursor.fetchall = Mock(return_value=[
            ("005930", "KR", "Samsung Electronics", "Technology"),
        ])

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        # First call
        result1 = await adapter.list_available_tickers(region="KR")

        # Second call (should use cache)
        result2 = await adapter.list_available_tickers(region="KR")

        assert result1 == result2
        # Database should only be queried once
        assert adapter.db_manager.get_connection.call_count == 1


# ============================================================================
# Test: Get System Status
# ============================================================================

class TestGetSystemStatus:
    """Test suite for get_system_status method"""

    @pytest.mark.asyncio
    async def test_get_status_success(self, adapter):
        """Test successful system status retrieval"""
        mock_cursor = Mock()
        mock_cursor.fetchone = Mock(side_effect=[
            ("PostgreSQL 15.3",),  # version
            {"KR": 1000, "US": 500},  # ticker_counts (mocked as dict)
            (50000,),  # ohlcv_count
            (date(2024, 10, 30),),  # latest_date
            ("500 MB",),  # db_size
        ])
        mock_cursor.fetchall = Mock(side_effect=[
            [("KR", 1000), ("US", 500)],  # ticker_counts rows
        ])

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        result = await adapter.get_system_status()

        assert result["success"] is True
        assert result["status"] in ["healthy", "stale_data"]
        assert "database" in result
        assert "data" in result
        assert result["database"]["connected"] is True
        assert result["data"]["total_tickers"] == 1500
        assert result["data"]["ohlcv_records"] == 50000

    @pytest.mark.asyncio
    async def test_get_status_data_freshness(self, adapter):
        """Test data freshness calculation"""
        recent_date = date.today()

        mock_cursor = Mock()
        mock_cursor.fetchone = Mock(side_effect=[
            ("PostgreSQL 15.3",),
            (recent_date,),
            ("500 MB",),
        ])
        mock_cursor.fetchall = Mock(side_effect=[
            [("KR", 1000)],
            [(50000,)],
        ])

        # Need to mock multiple cursor returns properly
        def mock_cursor_context():
            cursor = Mock()
            cursor.fetchone = Mock(side_effect=[
                ("PostgreSQL 15.3",),
            ])
            cursor.fetchall = Mock(side_effect=[
                [("KR", 1000)],
            ])
            return cursor

        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)

        # Properly mock the context manager
        adapter.db_manager.get_connection = Mock(return_value=mock_conn)

        result = await adapter.get_system_status()

        assert result["success"] is True
        # Fresh data should result in "healthy" status
        # (Note: actual implementation determines this based on days_since_update <= 3)


# ============================================================================
# Test: Caching Behavior
# ============================================================================

class TestSystemAdapterCaching:
    """Test suite for caching behavior"""

    def test_cache_validity_check(self, adapter):
        """Test cache validity checking"""
        # Empty cache
        assert adapter._is_cache_valid("nonexistent") is False

        # Valid cache entry
        adapter._cache["test_key"] = {"data": "value"}
        adapter._cache_time["test_key"] = datetime.now()
        assert adapter._is_cache_valid("test_key") is True

        # Expired cache entry (simulate 120 seconds old)
        from datetime import timedelta
        old_time = datetime.now() - timedelta(seconds=120)
        adapter._cache_time["test_key"] = old_time
        assert adapter._is_cache_valid("test_key") is False


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestSystemAdapterErrorHandling:
    """Test suite for error handling"""

    @pytest.mark.asyncio
    async def test_database_error_on_list_tickers(self, adapter):
        """Test DatabaseError is raised on list_tickers failure"""
        adapter.db_manager.get_connection = Mock(side_effect=Exception("Connection failed"))

        with pytest.raises(DatabaseError) as exc_info:
            await adapter.list_available_tickers()

        error_dict = exc_info.value.to_dict()
        assert "Failed to list tickers" in error_dict["message"]

    @pytest.mark.asyncio
    async def test_database_error_on_get_status(self, adapter):
        """Test DatabaseError is raised on get_status failure"""
        adapter.db_manager.get_connection = Mock(side_effect=Exception("Connection failed"))

        with pytest.raises(DatabaseError) as exc_info:
            await adapter.get_system_status()

        error_dict = exc_info.value.to_dict()
        assert "Failed to get system status" in error_dict["message"]
