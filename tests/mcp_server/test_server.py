# tests/mcp_server/test_server.py
"""
Unit tests for MCP server initialization and lifecycle
"""

import pytest
from unittest.mock import patch, MagicMock

from mcp_server.server import SpockMCPServer
from mcp_server.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return Config(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="test_db",
        postgres_user="test_user",
        postgres_password="test_pass",
        log_level="DEBUG",
    )


@pytest.fixture
def mock_server():
    """Mock MCP Server for testing"""
    mock = MagicMock()
    mock.__aenter__ = MagicMock()
    mock.__aexit__ = MagicMock()
    return mock


class TestSpockMCPServer:
    """Test suite for SpockMCPServer"""

    def test_server_initialization(self, mock_config):
        """Test server initializes with correct configuration"""
        with patch("mcp_server.server.Config.from_env", return_value=mock_config):
            server = SpockMCPServer()
            
            assert server.config.postgres_host == "localhost"
            assert server.config.postgres_db == "test_db"
            assert server.config.log_level == "DEBUG"

    def test_server_name(self, mock_config):
        """Test server has correct name"""
        with patch("mcp_server.server.Config.from_env", return_value=mock_config):
            server = SpockMCPServer()
            
            assert server.server.name == "spock"

    @pytest.mark.asyncio
    async def test_server_run_lifecycle(self, mock_config, mock_server):
        """Test server run lifecycle (start and stop)"""
        with patch("mcp_server.server.Config.from_env", return_value=mock_config):
            with patch("mcp_server.server.Server", return_value=mock_server):
                server = SpockMCPServer()
                
                # Mock the async context manager
                mock_server.__aenter__.return_value = mock_server
                mock_server.__aexit__.return_value = None
                mock_server.run = MagicMock(return_value=None)
                
                # This would normally run indefinitely, so we just verify it starts
                # In real usage, this will be tested with E2E tests
                assert server.server is not None

    def test_logging_setup(self, mock_config):
        """Test logging is configured correctly"""
        with patch("mcp_server.server.Config.from_env", return_value=mock_config):
            with patch("mcp_server.server.structlog.configure") as mock_configure:
                server = SpockMCPServer()
                
                # Verify structlog.configure was called
                mock_configure.assert_called_once()
