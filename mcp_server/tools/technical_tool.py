# mcp_server/tools/technical_tool.py
"""
Technical Indicators Tool for MCP Server

Provides get_technical_indicators tool for calculating technical indicators
without returning full OHLCV data. Optimized for Claude Desktop context limits.

Tool Definition:
    name: get_technical_indicators
    description: Get technical indicators (RSI, MA) without raw OHLCV data
    input: tickers, region, indicators, period_days

Handler:
    Validates input -> Calls DataAdapter.get_technical_indicators -> Returns indicators only

Performance:
    - 96% size reduction vs full OHLCV (50KB -> 2KB for 9 tickers)
    - Optimized for large result sets in Claude Desktop

Author: Spock MCP Server
Date: 2025-10-31
"""

from typing import Any, Sequence
from mcp.types import Tool, TextContent
import structlog
import json

logger = structlog.get_logger()


def get_technical_tool_def() -> Tool:
    """
    Get tool definition for get_technical_indicators.

    Returns:
        MCP Tool object with schema
    """
    return Tool(
        name="get_technical_indicators",
        description="Calculate technical indicators (RSI, MA trends) for stocks without returning raw OHLCV data. Optimized for large result sets (96% size reduction vs full OHLCV).",
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols (e.g., ['005930', '000660'] for KR, ['AAPL', 'MSFT'] for US)",
                    "minItems": 1,
                    "maxItems": 100
                },
                "region": {
                    "type": "string",
                    "enum": ["KR", "US"],
                    "default": "KR",
                    "description": "Market region"
                },
                "indicators": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["rsi", "ma", "all"]
                    },
                    "default": ["all"],
                    "description": "Indicators to calculate: 'rsi' (RSI only), 'ma' (Moving Averages only), 'all' (both)"
                },
                "period_days": {
                    "type": "number",
                    "default": 400,
                    "minimum": 100,
                    "maximum": 1000,
                    "description": "Number of calendar days to fetch for calculation (400 days ≈ 285 trading days, sufficient for MA200)"
                }
            },
            "required": ["tickers"]
        }
    )


async def handle_get_technical_indicators(adapter, arguments: Any) -> Sequence[TextContent]:
    """
    Handle get_technical_indicators tool execution.

    Args:
        adapter: DataAdapter instance
        arguments: Tool arguments from MCP client

    Returns:
        Sequence of TextContent with indicator results (NO OHLCV)

    Example Input:
        {
            "tickers": ["005930", "000660"],
            "region": "KR",
            "indicators": ["all"],
            "period_days": 400
        }

    Example Output:
        {
            "success": true,
            "indicators": {
                "005930": {
                    "rsi": {
                        "rsi": 45.2,
                        "signal": "neutral",
                        "period": 14,
                        "oversold_threshold": 30.0,
                        "overbought_threshold": 70.0
                    },
                    "moving_averages": {
                        "ma20": 52000.5,
                        "ma50": 51800.2,
                        "ma200": 50500.0,
                        "trend": "bullish",
                        "price": 52500.0,
                        "price_vs_ma20": "above",
                        "ma_crossover": "none"
                    },
                    "timestamp": "2025-10-31T12:34:56.789"
                },
                "000660": {
                    "rsi": {...},
                    "moving_averages": {...},
                    "timestamp": "..."
                }
            },
            "count": 2,
            "region": "KR",
            "period_days": 400
        }
    """
    try:
        # Extract arguments with defaults
        tickers = arguments.get("tickers", [])
        region = arguments.get("region", "KR")
        indicators = arguments.get("indicators", ["all"])
        period_days = arguments.get("period_days", 400)

        logger.info("get_technical_indicators_called",
                   tickers=tickers,
                   region=region,
                   indicators=indicators,
                   period_days=period_days)

        # Call data adapter
        result = await adapter.get_technical_indicators(
            tickers=tickers,
            region=region,
            indicators=indicators,
            period_days=period_days
        )

        # Format response
        response_text = json.dumps(result, indent=2, ensure_ascii=False)

        logger.info("get_technical_indicators_success",
                   count=result.get("count"),
                   region=result.get("region"))

        return [TextContent(type="text", text=response_text)]

    except Exception as e:
        logger.error("get_technical_indicators_error", error=str(e))
        error_response = {
            "success": False,
            "error": str(e),
            "tickers": arguments.get("tickers"),
            "region": arguments.get("region")
        }
        return [TextContent(type="text", text=json.dumps(error_response, indent=2))]
