# mcp_server/tools/screening_tool.py
"""
Stock Screening Tool for MCP Server

Provides screen_stocks tool for filtering stocks by fundamental criteria.
Supports P/E ratio, P/B ratio, and dividend yield filters.

Tool Definition:
    name: screen_stocks
    description: Screen stocks by fundamental criteria
    input: filters, region, limit

Handler:
    Validates input -> Calls ScreeningAdapter -> Returns formatted results

Author: Spock MCP Server
Date: 2025-10-31
"""

from typing import Any, Sequence
from mcp.types import Tool, TextContent
import structlog
import json

logger = structlog.get_logger()


def get_screening_tool_def() -> Tool:
    """
    Get tool definition for screen_stocks.

    Returns:
        MCP Tool object with schema
    """
    return Tool(
        name="screen_stocks",
        description="Screen stocks by fundamental and technical criteria (P/E, P/B, dividend yield, RSI, MA trend)",
        inputSchema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Fundamental screening filters to apply",
                    "properties": {
                        "per_max": {
                            "type": "number",
                            "description": "Maximum P/E ratio (e.g., 15 for value stocks)",
                            "minimum": 0,
                            "maximum": 1000
                        },
                        "pbr_max": {
                            "type": "number",
                            "description": "Maximum P/B ratio (e.g., 2 for value stocks)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "dividend_yield_min": {
                            "type": "number",
                            "description": "Minimum dividend yield in % (e.g., 3.0 for income stocks)",
                            "minimum": 0,
                            "maximum": 50
                        },
                        "market_cap_min": {
                            "type": "number",
                            "description": "Minimum market cap (optional, Phase 3)",
                            "minimum": 0
                        }
                    },
                    "additionalProperties": False
                },
                "technical_filters": {
                    "type": "object",
                    "description": "Technical indicator filters to apply (Phase 2)",
                    "properties": {
                        "rsi_min": {
                            "type": "number",
                            "description": "Minimum RSI value (e.g., 0 for any oversold)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "rsi_max": {
                            "type": "number",
                            "description": "Maximum RSI value (e.g., 30 for oversold stocks)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "ma_trend": {
                            "type": "string",
                            "enum": ["bullish", "bearish", "neutral"],
                            "description": "Required MA trend (bullish: MA20>MA50>MA200, bearish: MA20<MA50<MA200)"
                        }
                    },
                    "additionalProperties": False
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US"],
                    "default": "KR",
                    "description": "Market region to screen"
                },
                "limit": {
                    "type": "number",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum number of results to return"
                }
            },
            "required": ["filters"]
        }
    )


async def handle_screen_stocks(adapter, arguments: Any) -> Sequence[TextContent]:
    """
    Handle screen_stocks tool execution.

    Args:
        adapter: ScreeningAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Sequence of TextContent with screening results

    Example Input:
        {
            "filters": {
                "per_max": 15,
                "pbr_max": 2,
                "dividend_yield_min": 3.0
            },
            "technical_filters": {
                "rsi_max": 30,
                "ma_trend": "bullish"
            },
            "region": "KR",
            "limit": 50
        }

    Example Output:
        {
            "success": true,
            "stocks": [
                {
                    "ticker": "005930",
                    "name": "Samsung Electronics",
                    "per": 12.5,
                    "pbr": 1.8,
                    "dividend_yield": 3.2,
                    "rsi": 28.5,
                    "rsi_signal": "oversold",
                    "ma_trend": "bullish",
                    "price_vs_ma20": "above",
                    "date": "2025-10-28"
                },
                ...
            ],
            "count": 23,
            "filters_applied": {...},
            "region": "KR"
        }
    """
    try:
        # Extract arguments with defaults
        filters = arguments.get("filters", {})
        technical_filters = arguments.get("technical_filters")
        region = arguments.get("region", "KR")
        limit = arguments.get("limit", 50)

        logger.info("screen_stocks_called",
                   filters=filters,
                   technical_filters=technical_filters,
                   region=region,
                   limit=limit)

        # Call screening adapter
        result = await adapter.screen_stocks(
            filters=filters,
            technical_filters=technical_filters,
            region=region,
            limit=limit
        )

        # Format response
        response_text = json.dumps(result, indent=2, ensure_ascii=False)

        logger.info("screen_stocks_success",
                   count=result.get("count"),
                   total_matching=result.get("total_matching"))

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error("screen_stocks_error", error=str(e))
        error_response = {
            "success": False,
            "error": str(e),
            "filters": arguments.get("filters"),
            "region": arguments.get("region")
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
