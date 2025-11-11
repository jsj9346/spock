# mcp_server/tools/etf_tool.py
"""
ETF Screening Tool for MCP Server

Provides screen_etfs tool for filtering ETFs by available criteria.
Uses name-based sector filtering, listing date, and technical indicators.

Tool Definition:
    name: screen_etfs
    description: Screen ETFs by available criteria
    input: filters, technical_filters, region, limit

Handler:
    Validates input -> Calls ETFScreeningAdapter -> Returns formatted results

Known Limitations:
    - AUM data not available
    - TER data not available
    - Sector/theme approximated from name

Author: Spock MCP Server
Date: 2025-10-31
Phase: ETF Screening Tool - Phase 2
"""

from typing import Any, Sequence
from mcp.types import Tool, TextContent
import structlog
import json

logger = structlog.get_logger()


def get_etf_screening_tool_def() -> Tool:
    """
    Get tool definition for screen_etfs.

    Returns:
        MCP Tool object with schema
    """
    return Tool(
        name="screen_etfs",
        description=(
            "Screen Korean ETFs by name pattern, listing date, and technical indicators. "
            "Note: AUM and TER data not available - use volume as liquidity proxy. "
            "Sector/theme approximated from ETF name."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filters": {
                    "type": "object",
                    "description": "Basic screening filters to apply",
                    "properties": {
                        "name_pattern": {
                            "type": "string",
                            "description": (
                                "Filter by ETF name substring. "
                                "Examples: '반도체' (semiconductor), 'KODEX', '200', '배터리' (battery)"
                            )
                        },
                        "listing_date_after": {
                            "type": "string",
                            "description": "Filter ETFs listed after this date (YYYY-MM-DD format)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "listing_date_before": {
                            "type": "string",
                            "description": "Filter ETFs listed before this date (YYYY-MM-DD format)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        }
                    },
                    "additionalProperties": False
                },
                "technical_filters": {
                    "type": "object",
                    "description": "Technical indicator filters to apply",
                    "properties": {
                        "rsi_min": {
                            "type": "number",
                            "description": "Minimum RSI value (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "rsi_max": {
                            "type": "number",
                            "description": "Maximum RSI value (0-100, e.g., 30 for oversold)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "ma_trend": {
                            "type": "string",
                            "enum": ["bullish", "bearish", "neutral"],
                            "description": "Required MA trend (bullish: MA20>MA50>MA200, bearish: opposite, neutral: mixed)"
                        },
                        "price_change_1m_min": {
                            "type": "number",
                            "description": "Minimum 1-month price change % (e.g., -10.0 for any decline >-10%)",
                            "minimum": -100,
                            "maximum": 1000
                        },
                        "price_change_1m_max": {
                            "type": "number",
                            "description": "Maximum 1-month price change % (e.g., 50.0 for moderate gains)",
                            "minimum": -100,
                            "maximum": 1000
                        },
                        "volume_avg_20d_min": {
                            "type": "number",
                            "description": "Minimum 20-day average volume (proxy for liquidity/size)",
                            "minimum": 0
                        }
                    },
                    "additionalProperties": False
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US"],
                    "default": "KR",
                    "description": "Market region to screen (currently only KR supported)"
                },
                "limit": {
                    "type": "number",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum number of results to return"
                }
            }
        }
    )


async def handle_screen_etfs(adapter, arguments: Any) -> Sequence[TextContent]:
    """
    Handle screen_etfs tool execution.

    Args:
        adapter: ETFScreeningAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Sequence of TextContent with screening results

    Example Input:
        {
            "filters": {
                "name_pattern": "반도체"
            },
            "technical_filters": {
                "ma_trend": "bullish",
                "rsi_max": 70,
                "volume_avg_20d_min": 1000000
            },
            "region": "KR",
            "limit": 20
        }

    Example Output:
        {
            "success": true,
            "etfs": [
                {
                    "ticker": "091160",
                    "name": "KODEX 반도체",
                    "listing_date": "2015-05-08",
                    "sector_theme": "Semiconductor",
                    "current_price": 45000,
                    "price_change_1m": 8.5,
                    "volume_avg_20d": 2500000,
                    "rsi": 65.0,
                    "rsi_signal": "neutral",
                    "ma_trend": "bullish",
                    "ma20": 44000,
                    "ma50": 43000,
                    "ma200": 40000
                },
                ...
            ],
            "count": 5,
            "total_matching": 8,
            "filters_applied": {...},
            "technical_filters_applied": {...},
            "region": "KR",
            "limitations": [
                "AUM data not available",
                "TER data not available",
                "Sector/theme approximated from name"
            ]
        }
    """
    try:
        # Extract arguments with defaults
        filters = arguments.get("filters")
        technical_filters = arguments.get("technical_filters")
        region = arguments.get("region", "KR")
        limit = arguments.get("limit", 50)

        logger.info("screen_etfs_called",
                   filters=filters,
                   technical_filters=technical_filters,
                   region=region,
                   limit=limit)

        # Call ETF screening adapter
        result = await adapter.screen_etfs(
            filters=filters,
            technical_filters=technical_filters,
            region=region,
            limit=limit
        )

        # Format response
        response_text = json.dumps(result, indent=2, ensure_ascii=False)

        logger.info("screen_etfs_success",
                   count=result.get("count"),
                   total_matching=result.get("total_matching"))

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error("screen_etfs_error", error=str(e), exc_info=True)
        error_response = {
            "success": False,
            "error": str(e),
            "filters": arguments.get("filters"),
            "technical_filters": arguments.get("technical_filters"),
            "region": arguments.get("region")
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
