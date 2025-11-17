# mcp_server/tools/system_tools.py
"""
System MCP Tools

MCP tools for system information and health checks.
Thin wrapper around SystemAdapter with MCP protocol compliance.
"""

from typing import Any, Sequence
import structlog

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..adapters.system_adapter import SystemAdapter
from ..utils.errors import ValidationError, DatabaseError

logger = structlog.get_logger()


def register_system_tools(server: Server) -> None:
    """
    Register system tools with MCP server.

    Registers:
    - list_available_tickers: List tickers in database with filtering
    - get_system_status: Get system health status and statistics

    Args:
        server: MCP Server instance
    """
    # Initialize SystemAdapter (shared across all tool calls)
    adapter = SystemAdapter()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available system tools."""
        return [
            Tool(
                name="list_available_tickers",
                description=(
                    "List available ticker symbols in database. "
                    "Supports filtering by region, ticker type, and result limit. "
                    "Returns ticker metadata including symbol, name, sector, and region."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "region": {
                            "type": "string",
                            "description": "Filter by market region code",
                            "enum": ["CN", "HK", "JP", "KR", "US", "VN"]
                        },
                        "ticker_type": {
                            "type": "string",
                            "description": "Filter by ticker type (stock, etf, etc.)",
                            "enum": ["stock", "etf"]
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 100
                        }
                    }
                }
            ),
            Tool(
                name="get_system_status",
                description=(
                    "Get system health status and database statistics. "
                    "Returns database version, ticker counts by region, "
                    "OHLCV record count, latest data date, and data freshness indicators."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
        """
        Handle MCP tool calls.

        Args:
            name: Tool name (list_available_tickers or get_system_status)
            arguments: Tool arguments dict

        Returns:
            List of TextContent responses

        Raises:
            ValueError: If tool name is invalid
        """
        if name not in ["list_available_tickers", "get_system_status"]:
            raise ValueError(f"Unknown tool: {name}")

        try:
            if name == "list_available_tickers":
                # Extract arguments with defaults
                region = arguments.get("region")
                ticker_type = arguments.get("ticker_type")
                limit = arguments.get("limit", 100)

                logger.info(
                    "list_available_tickers_start",
                    region=region,
                    ticker_type=ticker_type,
                    limit=limit
                )

                # Validate limit
                if limit < 1 or limit > 1000:
                    raise ValidationError(
                        "Invalid limit value",
                        {
                            "limit": limit,
                            "valid_range": "1-1000"
                        }
                    )

                # Query tickers
                result = await adapter.list_available_tickers(
                    region=region,
                    ticker_type=ticker_type,
                    limit=limit
                )

                # Format response
                import json
                response_text = json.dumps(result, indent=2, ensure_ascii=False)

                logger.info(
                    "list_available_tickers_success",
                    count=result.get("count", 0)
                )

                return [TextContent(type="text", text=response_text)]

            elif name == "get_system_status":
                logger.info("get_system_status_start")

                # Get system status
                result = await adapter.get_system_status()

                # Format response
                import json
                response_text = json.dumps(result, indent=2, ensure_ascii=False)

                logger.info(
                    "get_system_status_success",
                    status=result.get("status"),
                    total_tickers=result.get("data", {}).get("total_tickers", 0)
                )

                return [TextContent(type="text", text=response_text)]

        except ValidationError as e:
            logger.warning(f"{name}_validation_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except DatabaseError as e:
            logger.error(f"{name}_database_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except Exception as e:
            logger.error(f"{name}_unexpected_error", error=str(e), exc_info=True)
            from ..utils.errors import SpockMCPError
            error_response = SpockMCPError(
                "INTERNAL_ERROR",
                f"Unexpected error: {str(e)}",
                {"type": type(e).__name__}
            ).to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

    logger.info("system_tools_registered", tool_count=2)
