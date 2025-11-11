# mcp_server/tools/data_query.py
"""
Data Query MCP Tools

First MCP tool implementation for OHLCV data queries.
Thin wrapper around DataAdapter with MCP protocol compliance.
"""

from typing import Any, Sequence
from datetime import datetime
import structlog

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..adapters.data_adapter import DataAdapter
from ..utils.validators import validate_tickers, validate_date_range
from ..utils.formatters import format_ohlcv_response
from ..utils.errors import ValidationError, DataNotFoundError, DatabaseError

logger = structlog.get_logger()

# Pagination constants
MAX_ROWS = 5000  # Maximum rows to return (prevents context overflow)
SAMPLE_SIZE = 100  # Sample size for large responses


def estimate_response_size(tickers: list[str], start_date: str, end_date: str) -> int:
    """
    Estimate number of rows in OHLCV response.

    Args:
        tickers: List of ticker symbols
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Estimated number of rows (tickers * trading_days)
    """
    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Calculate calendar days
    calendar_days = (end - start).days + 1

    # Estimate trading days (~250 trading days per 365 calendar days)
    trading_days = int(calendar_days * 250 / 365)

    # Total rows = tickers * trading_days
    estimated_rows = len(tickers) * trading_days

    return estimated_rows


def get_data_query_tool_def() -> Tool:
    """Get tool definition for query_ohlcv_data."""
    return Tool(
        name="query_ohlcv_data",
        description=(
            "Get OHLCV (Open, High, Low, Close, Volume) data for stock tickers. "
            "Supports Korean (KR) and US markets with daily timeframe. "
            "Returns historical price and volume data for analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "List of ticker symbols. "
                        "KR format: 6-digit numeric (e.g., 005930 for Samsung). "
                        "US format: 1-5 uppercase letters (e.g., AAPL for Apple). "
                        "Maximum 1000 tickers per request."
                    ),
                    "minItems": 1,
                    "maxItems": 1000
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (inclusive)",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format (inclusive)",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                },
                "region": {
                    "type": "string",
                    "description": "Market region code",
                    "enum": ["KR", "US"],
                    "default": "KR"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Data timeframe",
                    "enum": ["1d"],
                    "default": "1d"
                }
            },
            "required": ["tickers", "start_date", "end_date"]
        }
    )


async def handle_query_ohlcv_data(adapter: DataAdapter, arguments: Any) -> Sequence[TextContent]:
    """Handle query_ohlcv_data tool execution."""
    # Extract arguments with defaults
    tickers = arguments.get("tickers", [])
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")
    region = arguments.get("region", "KR")
    timeframe = arguments.get("timeframe", "1d")

    try:
        # Step 1: Validate inputs
        logger.info(
            "query_ohlcv_data_start",
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            region=region
        )

        validate_tickers(tickers, region)
        validate_date_range(start_date, end_date)

        # Step 2: Execute query
        data = await adapter.get_ohlcv(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe=timeframe
        )

        # Step 3: Format response
        response_text = format_ohlcv_response(data)

        logger.info(
            "query_ohlcv_data_success",
            ticker_count=len(data),
            record_count=sum(len(records) for records in data.values())
        )

        return [TextContent(type="text", text=response_text)]

    except ValidationError as e:
        logger.warning("query_ohlcv_data_validation_error", error=str(e))
        error_response = e.to_dict()
        import json
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    except DataNotFoundError as e:
        logger.warning("query_ohlcv_data_not_found", error=str(e))
        error_response = e.to_dict()
        import json
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    except DatabaseError as e:
        logger.error("query_ohlcv_data_database_error", error=str(e))
        error_response = e.to_dict()
        import json
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]

    except Exception as e:
        logger.error("query_ohlcv_data_unexpected_error", error=str(e), exc_info=True)
        from ..utils.errors import SpockMCPError
        error_response = SpockMCPError(
            "INTERNAL_ERROR",
            f"Unexpected error: {str(e)}",
            {"type": type(e).__name__}
        ).to_dict()
        import json
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]


def register_data_query_tools(server: Server) -> None:
    """
    Register data query tools with MCP server.
    
    Registers:
    - query_ohlcv_data: Get OHLCV data for tickers with date range
    
    Args:
        server: MCP Server instance
    """
    # Initialize DataAdapter (shared across all tool calls)
    adapter = DataAdapter()
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available data query tools."""
        return [
            Tool(
                name="query_ohlcv_data",
                description=(
                    "Get OHLCV (Open, High, Low, Close, Volume) data for stock tickers. "
                    "Supports Korean (KR) and US markets with daily timeframe. "
                    "Returns historical price and volume data for analysis."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "List of ticker symbols. "
                                "KR format: 6-digit numeric (e.g., 005930 for Samsung). "
                                "US format: 1-5 uppercase letters (e.g., AAPL for Apple). "
                                "Maximum 1000 tickers per request."
                            ),
                            "minItems": 1,
                            "maxItems": 1000
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format (inclusive)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format (inclusive)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "region": {
                            "type": "string",
                            "description": "Market region code",
                            "enum": ["KR", "US"],
                            "default": "KR"
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Data timeframe",
                            "enum": ["1d"],
                            "default": "1d"
                        }
                    },
                    "required": ["tickers", "start_date", "end_date"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
        """
        Handle MCP tool calls.
        
        Args:
            name: Tool name (must be "query_ohlcv_data")
            arguments: Tool arguments dict
        
        Returns:
            List of TextContent responses
        
        Raises:
            ValueError: If tool name is invalid
        """
        if name != "query_ohlcv_data":
            raise ValueError(f"Unknown tool: {name}")
        
        # Extract arguments with defaults
        tickers = arguments.get("tickers", [])
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")
        region = arguments.get("region", "KR")
        timeframe = arguments.get("timeframe", "1d")
        
        try:
            # Step 1: Validate inputs
            logger.info(
                "query_ohlcv_data_start",
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region
            )
            
            validate_tickers(tickers, region)
            validate_date_range(start_date, end_date)

            # Step 2: Check if response will be too large
            estimated_rows = estimate_response_size(tickers, start_date, end_date)
            logger.info(
                "query_ohlcv_data_size_check",
                estimated_rows=estimated_rows,
                max_rows=MAX_ROWS,
                will_paginate=estimated_rows > MAX_ROWS
            )

            if estimated_rows > MAX_ROWS:
                # Return summary response instead of full data
                import json
                summary_response = {
                    "status": "partial",
                    "message": f"Data exceeds maximum row limit ({estimated_rows:,} > {MAX_ROWS:,})",
                    "summary": {
                        "total_estimated_rows": estimated_rows,
                        "ticker_count": len(tickers),
                        "date_range": f"{start_date} to {end_date}",
                        "region": region,
                        "suggestion": (
                            "To retrieve data:\n"
                            f"1. Reduce date range (currently {estimated_rows // len(tickers):,} days per ticker)\n"
                            f"2. Reduce ticker count (currently {len(tickers)} tickers)\n"
                            f"3. Query tickers individually or in smaller batches"
                        )
                    },
                    "limits": {
                        "max_rows": MAX_ROWS,
                        "recommended_date_range_days": MAX_ROWS // len(tickers) if tickers else MAX_ROWS,
                        "recommended_ticker_batch_size": MAX_ROWS // (estimated_rows // len(tickers)) if tickers else 1
                    }
                }

                logger.warning(
                    "query_ohlcv_data_too_large",
                    estimated_rows=estimated_rows,
                    max_rows=MAX_ROWS
                )

                return [TextContent(type="text", text=json.dumps(summary_response, indent=2, ensure_ascii=False))]

            # Step 3: Execute query
            data = await adapter.get_ohlcv(
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region,
                timeframe=timeframe
            )

            # Step 4: Format response
            response_text = format_ohlcv_response(data)
            
            logger.info(
                "query_ohlcv_data_success",
                ticker_count=len(data),
                record_count=sum(len(records) for records in data.values())
            )
            
            return [TextContent(type="text", text=response_text)]
        
        except ValidationError as e:
            logger.warning("query_ohlcv_data_validation_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        
        except DataNotFoundError as e:
            logger.warning("query_ohlcv_data_not_found", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        
        except DatabaseError as e:
            logger.error("query_ohlcv_data_database_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
        
        except Exception as e:
            logger.error("query_ohlcv_data_unexpected_error", error=str(e), exc_info=True)
            from ..utils.errors import SpockMCPError
            error_response = SpockMCPError(
                "INTERNAL_ERROR",
                f"Unexpected error: {str(e)}",
                {"type": type(e).__name__}
            ).to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
    
    logger.info("data_query_tools_registered", tool_count=1)
