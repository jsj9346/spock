"""
Unit tests for cli/utils/database.py - DatabaseManager
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncpg

# Import module under test at module level
from cli.utils.database import DatabaseManager


@pytest.mark.unit
class TestDatabaseManager:
    """Test DatabaseManager class"""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset DatabaseManager singleton before each test"""
        DatabaseManager._instance = None
        DatabaseManager._pool = None
        yield
        # Cleanup after test
        DatabaseManager._instance = None
        DatabaseManager._pool = None

    @pytest.fixture
    def db_config(self):
        """Database configuration fixture"""
        return {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_pass'
        }

    @pytest.fixture
    def mock_pool(self):
        """Mock asyncpg connection pool"""
        # Create mock connection for acquire() context manager
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        # Create async context manager mock for acquire()
        mock_acquire_cm = MagicMock()
        mock_acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_cm.__aexit__ = AsyncMock(return_value=None)

        # Create mock pool
        pool = AsyncMock()
        # Make acquire() return the context manager (not a coroutine)
        pool.acquire = MagicMock(return_value=mock_acquire_cm)
        pool.close = AsyncMock()

        # Store reference to mock_conn for test assertions
        pool._mock_conn = mock_conn

        return pool

    @pytest.fixture
    def mock_create_pool(self, mock_pool):
        """Mock asyncpg.create_pool as async function"""
        return AsyncMock(return_value=mock_pool)

    @pytest.mark.asyncio
    async def test_singleton_pattern(self, db_config):
        """Test that DatabaseManager implements singleton pattern"""
        with patch('cli.utils.database.asyncpg.create_pool') as mock_create:
            mock_create.return_value = AsyncMock()

            # Create two instances
            db1 = DatabaseManager()
            db2 = DatabaseManager()

            # They should be the same instance
            assert db1 is db2

    @pytest.mark.asyncio
    async def test_connect_creates_pool(self, db_config, mock_pool, mock_create_pool):
        """Test that connect() creates connection pool"""
        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)

            assert db._pool is not None
            assert db._pool == mock_pool

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self, db_config, mock_pool, mock_create_pool):
        """Test that disconnect() closes connection pool"""
        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)
            await db.disconnect()

            mock_pool.close.assert_called_once()
            assert db._pool is None

    @pytest.mark.asyncio
    async def test_fetch_returns_rows(self, db_config, mock_pool, mock_create_pool):
        """Test that fetch() returns rows"""
        expected_rows = [{'id': 1, 'name': 'test'}]
        mock_pool._mock_conn.fetch.return_value = expected_rows

        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)

            result = await db.fetch("SELECT * FROM test")

            assert result == expected_rows
            mock_pool._mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetchval_returns_single_value(self, db_config, mock_pool, mock_create_pool):
        """Test that fetchval() returns single value"""
        expected_value = 42
        # First call returns 1 (connection test), second returns 42 (our query)
        mock_pool._mock_conn.fetchval.side_effect = [1, expected_value]

        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)

            result = await db.fetchval("SELECT COUNT(*) FROM test")

            assert result == expected_value
            # Should be called twice: once for connect test, once for our query
            assert mock_pool._mock_conn.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_runs_query(self, db_config, mock_pool, mock_create_pool):
        """Test that execute() runs query"""
        mock_pool._mock_conn.execute.return_value = "INSERT 1"

        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)

            result = await db.execute("INSERT INTO test VALUES (1, 'test')")

            assert result == "INSERT 1"
            mock_pool._mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_without_connection_raises_error(self):
        """Test that fetch() without connection raises error"""
        db = DatabaseManager()

        with pytest.raises(RuntimeError, match="Database not connected"):
            await db.fetch("SELECT * FROM test")

    @pytest.mark.asyncio
    async def test_connection_pool_configuration(self, db_config, mock_pool, mock_create_pool):
        """Test that connection pool is configured correctly"""
        with patch('cli.utils.database.asyncpg.create_pool', mock_create_pool):
            db = DatabaseManager()
            await db.connect(config=db_config)

            # Verify pool was created with correct parameters
            mock_create_pool.assert_called_once()
            call_kwargs = mock_create_pool.call_args.kwargs

            assert call_kwargs['host'] == 'localhost'
            assert call_kwargs['port'] == 5432
            assert call_kwargs['database'] == 'test_db'
            assert call_kwargs['user'] == 'test_user'
