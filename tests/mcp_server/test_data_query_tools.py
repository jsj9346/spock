# tests/mcp_server/test_data_query_tools.py
"""
Integration tests for MCP data query tools
"""

import pytest
import asyncio
from datetime import date
from unittest.mock import Mock, AsyncMock, patch

from mcp_server.tools.data_query import register_data_query_tools
from mcp_server.adapters.data_adapter import DataAdapter
from mcp_server.utils.errors import ValidationError, DataNotFoundError, DatabaseError


class TestDataQueryToolsRegistration:
    """Test suite for tool registration"""

    def test_register_data_query_tools(self):
        """Test tools are registered successfully"""
        mock_server = Mock()
        mock_server.list_tools = Mock(return_value=lambda: None)
        mock_server.call_tool = Mock(return_value=lambda: None)

        # Should not raise any exceptions
        register_data_query_tools(mock_server)

        assert mock_server.list_tools.called
        assert mock_server.call_tool.called


class TestQueryOHLCVDataTool:
    """Test suite for query_ohlcv_data tool"""

    @pytest.fixture
    def mock_adapter(self):
        """Mock DataAdapter for testing"""
        with patch('mcp_server.tools.data_query.DataAdapter') as mock:
            adapter = mock.return_value
            adapter.get_ohlcv = AsyncMock()
            yield adapter

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_success(self, mock_adapter):
        """Test successful OHLCV query"""
        # Setup mock data
        mock_data = {
            "005930": [
                {
                    "date": "2024-01-01",
                    "open": 75000,
                    "high": 76000,
                    "low": 74000,
                    "close": 75500,
                    "volume": 1000000
                }
            ]
        }
        mock_adapter.get_ohlcv.return_value = mock_data

        # Create mock server and register tools
        mock_server = Mock()
        list_tools_handler = None
        call_tool_handler = None

        def mock_list_tools():
            def decorator(func):
                nonlocal list_tools_handler
                list_tools_handler = func
                return func
            return decorator

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = mock_list_tools
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        # Test tool call
        result = await call_tool_handler(
            name="query_ohlcv_data",
            arguments={
                "tickers": ["005930"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "region": "KR"
            }
        )

        assert len(result) == 1
        assert "005930" in result[0].text
        assert "success" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_validation_error(self):
        """Test validation error handling"""
        mock_server = Mock()
        list_tools_handler = None
        call_tool_handler = None

        def mock_list_tools():
            def decorator(func):
                nonlocal list_tools_handler
                list_tools_handler = func
                return func
            return decorator

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = mock_list_tools
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        # Test with invalid ticker format
        result = await call_tool_handler(
            name="query_ohlcv_data",
            arguments={
                "tickers": ["INVALID"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "region": "KR"
            }
        )

        assert len(result) == 1
        assert "VALIDATION_ERROR" in result[0].text
        assert "Invalid ticker format" in result[0].text

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_invalid_date_range(self):
        """Test invalid date range validation"""
        mock_server = Mock()
        call_tool_handler = None

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = lambda: lambda f: f
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        # Test with start_date > end_date
        result = await call_tool_handler(
            name="query_ohlcv_data",
            arguments={
                "tickers": ["005930"],
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",
                "region": "KR"
            }
        )

        assert len(result) == 1
        assert "VALIDATION_ERROR" in result[0].text
        assert "start_date must be before end_date" in result[0].text

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_data_not_found(self, mock_adapter):
        """Test DataNotFoundError handling"""
        mock_adapter.get_ohlcv.side_effect = DataNotFoundError(
            "No data available",
            {"tickers": ["999999"]}
        )

        mock_server = Mock()
        call_tool_handler = None

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = lambda: lambda f: f
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        result = await call_tool_handler(
            name="query_ohlcv_data",
            arguments={
                "tickers": ["999999"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "region": "KR"
            }
        )

        assert len(result) == 1
        assert "DATA_NOT_FOUND" in result[0].text

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_database_error(self, mock_adapter):
        """Test DatabaseError handling"""
        mock_adapter.get_ohlcv.side_effect = DatabaseError(
            "Connection failed",
            {"host": "localhost"}
        )

        mock_server = Mock()
        call_tool_handler = None

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = lambda: lambda f: f
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        result = await call_tool_handler(
            name="query_ohlcv_data",
            arguments={
                "tickers": ["005930"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "region": "KR"
            }
        )

        assert len(result) == 1
        assert "DATABASE_ERROR" in result[0].text

    @pytest.mark.asyncio
    async def test_query_ohlcv_data_unknown_tool(self):
        """Test unknown tool name handling"""
        mock_server = Mock()
        call_tool_handler = None

        def mock_call_tool():
            def decorator(func):
                nonlocal call_tool_handler
                call_tool_handler = func
                return func
            return decorator

        mock_server.list_tools = lambda: lambda f: f
        mock_server.call_tool = mock_call_tool

        register_data_query_tools(mock_server)

        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool_handler(
                name="invalid_tool",
                arguments={}
            )


class TestDataQueryToolsIntegration:
    """Integration tests with real components"""

    def test_tool_schema_structure(self):
        """Test tool schema is properly structured"""
        mock_server = Mock()
        list_tools_handler = None

        def mock_list_tools():
            def decorator(func):
                nonlocal list_tools_handler
                list_tools_handler = func
                return func
            return decorator

        mock_server.list_tools = mock_list_tools
        mock_server.call_tool = lambda: lambda f: f

        register_data_query_tools(mock_server)

        # Get tools
        tools = asyncio.run(list_tools_handler())

        assert len(tools) == 1
        tool = tools[0]

        assert tool.name == "query_ohlcv_data"
        assert "OHLCV" in tool.description
        assert "inputSchema" in tool.__dict__
        assert "properties" in tool.inputSchema
        assert "tickers" in tool.inputSchema["properties"]
        assert "start_date" in tool.inputSchema["properties"]
        assert "end_date" in tool.inputSchema["properties"]
        assert "region" in tool.inputSchema["properties"]
        assert "timeframe" in tool.inputSchema["properties"]

    def test_tool_schema_validation_rules(self):
        """Test tool schema has proper validation rules"""
        mock_server = Mock()
        list_tools_handler = None

        def mock_list_tools():
            def decorator(func):
                nonlocal list_tools_handler
                list_tools_handler = func
                return func
            return decorator

        mock_server.list_tools = mock_list_tools
        mock_server.call_tool = lambda: lambda f: f

        register_data_query_tools(mock_server)

        tools = asyncio.run(list_tools_handler())
        tool = tools[0]
        schema = tool.inputSchema

        # Check tickers array constraints
        assert schema["properties"]["tickers"]["minItems"] == 1
        assert schema["properties"]["tickers"]["maxItems"] == 1000

        # Check date pattern
        assert "pattern" in schema["properties"]["start_date"]
        assert "pattern" in schema["properties"]["end_date"]

        # Check region enum
        assert schema["properties"]["region"]["enum"] == ["KR", "US"]

        # Check required fields
        assert "required" in schema
        assert "tickers" in schema["required"]
        assert "start_date" in schema["required"]
        assert "end_date" in schema["required"]
