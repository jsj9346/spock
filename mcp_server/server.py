# mcp_server/server.py
"""
Spock MCP Server - AI-powered quant analysis interface

Provides MCP (Model Context Protocol) server for accessing
quant platform capabilities through AI assistants.
"""

import asyncio
from typing import Any, Sequence

from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import structlog

from .config import Config

logger = structlog.get_logger()


class SpockMCPServer:
    """Spock MCP Server for AI-powered quant analysis"""

    def __init__(self):
        """Initialize MCP server with configuration"""
        self.server = Server("spock")
        self.config = Config.from_env()

        # Validate project context before proceeding
        from .utils.validators import validate_project_context
        validate_project_context(self.config.allowed_project_path)

        self._setup_logging()
        self._register_handlers()

        logger.info(
            "mcp_server_initialized",
            server_name=self.config.server_name,
            version=self.config.server_version,
            postgres_host=self.config.postgres_host,
            allowed_path=self.config.allowed_project_path,
            current_path=__import__('os').getcwd(),
        )

    def _setup_logging(self) -> None:
        """
        Configure structured logging for MCP server.

        Note: Loguru (used by imported modules) is configured globally in
        mcp_server/__init__.py to prevent colored output to stderr.
        This method configures structlog for the server's own logging.
        """
        import logging
        import sys

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(colors=False),  # Disable ANSI colors for MCP
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, self.config.log_level.upper())
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),  # Log to stderr for MCP
            cache_logger_on_first_use=True,
        )

    def _register_handlers(self) -> None:
        """Register MCP tool and resource handlers"""
        # Initialize all adapters
        from .adapters.data_adapter import DataAdapter
        from .adapters.backtest_adapter import BacktestAdapter
        from .adapters.system_adapter import SystemAdapter
        from .adapters.optimization_adapter import OptimizationAdapter
        from .adapters.screening_adapter import ScreeningAdapter
        from modules.screening.etf_screening_adapter import ETFScreeningAdapter

        self.data_adapter = DataAdapter()
        self.backtest_adapter = BacktestAdapter()
        self.system_adapter = SystemAdapter()
        self.optimization_adapter = OptimizationAdapter()
        self.screening_adapter = ScreeningAdapter()
        self.etf_screening_adapter = ETFScreeningAdapter()

        # Register unified list_tools handler
        @self.server.list_tools()
        async def list_tools_handler() -> list[Tool]:
            """List all available MCP tools."""
            from .tools.data_query import get_data_query_tool_def
            from .tools._tool_helpers import (
                get_backtest_tool_def,
                get_system_tool_defs,
                get_optimization_tool_def
            )
            from .tools.screening_tool import get_screening_tool_def
            from .tools.technical_tool import get_technical_tool_def
            from .tools.etf_tool import get_etf_screening_tool_def

            tools = []
            tools.append(get_data_query_tool_def())
            tools.append(get_backtest_tool_def())
            tools.extend(get_system_tool_defs())
            tools.append(get_optimization_tool_def())
            tools.append(get_screening_tool_def())
            tools.append(get_technical_tool_def())
            tools.append(get_etf_screening_tool_def())

            logger.info("tools_listed", tool_count=len(tools))
            return tools

        # Register unified call_tool handler
        @self.server.call_tool()
        async def call_tool_handler(name: str, arguments: Any) -> Sequence[TextContent]:
            """Handle all tool calls."""
            logger.info("tool_called", tool_name=name)

            if name == "query_ohlcv_data":
                from .tools.data_query import handle_query_ohlcv_data
                return await handle_query_ohlcv_data(self.data_adapter, arguments)
            elif name == "run_backtest":
                from .tools._tool_helpers import handle_run_backtest
                return await handle_run_backtest(self.backtest_adapter, arguments)
            elif name == "list_available_tickers":
                from .tools._tool_helpers import handle_list_tickers
                return await handle_list_tickers(self.system_adapter, arguments)
            elif name == "get_system_status":
                from .tools._tool_helpers import handle_system_status
                return await handle_system_status(self.system_adapter)
            elif name == "optimize_strategy":
                from .tools._tool_helpers import handle_optimize_strategy
                return await handle_optimize_strategy(self.optimization_adapter, arguments)
            elif name == "screen_stocks":
                from .tools.screening_tool import handle_screen_stocks
                return await handle_screen_stocks(self.screening_adapter, arguments)
            elif name == "get_technical_indicators":
                from .tools.technical_tool import handle_get_technical_indicators
                return await handle_get_technical_indicators(self.data_adapter, arguments)
            elif name == "screen_etfs":
                from .tools.etf_tool import handle_screen_etfs
                return await handle_screen_etfs(self.etf_screening_adapter, arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

        logger.debug("mcp_unified_handlers_registered", tool_count=8)

    async def run(self) -> None:
        """Run MCP server (async main loop)"""
        from mcp.server.stdio import stdio_server

        logger.info("mcp_server_starting")

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )
        except Exception as e:
            logger.error("mcp_server_error", error=str(e), exc_info=True)
            raise
        finally:
            logger.info("mcp_server_stopped")


def main() -> None:
    """Entry point for MCP server"""
    import os

    # Ensure we're running from the project directory
    # The MCP config specifies cwd, but we need to ensure it's set before validation
    project_path = os.getenv("SPOCK_PROJECT_PATH", "/Users/13ruce/spock")
    os.chdir(project_path)

    server = SpockMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
