# mcp_server/tools/_tool_helpers.py
"""
Temporary helper functions for tool registration.
These extract tool definitions and handlers from existing register functions.
"""

from typing import Any, Sequence
from mcp.types import Tool, TextContent
import structlog

logger = structlog.get_logger()


# Backtest tools
def get_backtest_tool_def() -> Tool:
    """Get tool definition for run_backtest."""
    return Tool(
        name="run_backtest",
        description=(
            "Run complete end-to-end backtest for investment strategy. "
            "\n\n"
            "⚠️ IMPORTANT: This is a self-contained tool. "
            "DO NOT call query_ohlcv_data before using this tool. "
            "All data loading, processing, and simulation are handled internally. "
            "\n\n"
            "What this tool does automatically: "
            "1. Loads historical OHLCV data for specified tickers and date range "
            "2. Applies strategy signals (momentum, value, or combined) "
            "3. Simulates portfolio performance with realistic transaction costs "
            "4. Calculates comprehensive performance metrics "
            "5. Returns ONLY compact results (performance + trades). "
            "\n\n"
            "Supported strategies: "
            "- momentum: RSI + moving average crossover "
            "- value: P/E, P/B, dividend yield factors "
            "- momentum_value: Combined momentum + value "
            "\n\n"
            "Supported engines: "
            "- vectorbt: 100x faster, ideal for research and parameter optimization "
            "- custom: Production accuracy with event-driven simulation "
            "\n\n"
            "Response size: <1KB (efficient for multi-year backtests). "
            "No external data queries needed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "strategy_type": {"type": "string", "enum": ["momentum", "value", "momentum_value"]},
                "tickers": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "region": {"type": "string", "enum": ["KR", "US"], "default": "KR"},
                "engine": {"type": "string", "enum": ["vectorbt", "custom"], "default": "vectorbt"}
            },
            "required": ["strategy_type", "tickers", "start_date", "end_date"],
            "examples": [
                {
                    "strategy_type": "value",
                    "tickers": ["005930", "000660", "373220"],
                    "start_date": "2021-01-01",
                    "end_date": "2023-12-31",
                    "region": "KR",
                    "engine": "vectorbt"
                },
                {
                    "strategy_type": "momentum",
                    "tickers": ["005380", "000270", "005490"],
                    "start_date": "2023-01-01",
                    "end_date": "2023-12-31",
                    "region": "KR",
                    "engine": "vectorbt"
                },
                {
                    "strategy_type": "momentum_value",
                    "tickers": ["035420", "035720", "207940"],
                    "start_date": "2022-01-01",
                    "end_date": "2023-12-31",
                    "region": "KR",
                    "engine": "vectorbt"
                }
            ]
        }
    )


async def handle_run_backtest(adapter, arguments: Any) -> Sequence[TextContent]:
    """Handle run_backtest tool execution."""
    import json
    try:
        result = await adapter.run_backtest(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.error("backtest_error", error=str(e))
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


# System tools
def get_system_tool_defs() -> list[Tool]:
    """Get tool definitions for system tools."""
    return [
        Tool(
            name="list_available_tickers",
            description="List available stock tickers in database",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {"type": "string", "enum": ["KR", "US"]},
                    "limit": {"type": "number", "default": 100}
                }
            }
        ),
        Tool(
            name="get_system_status",
            description="Get system status and database health",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


async def handle_list_tickers(adapter, arguments: Any) -> Sequence[TextContent]:
    """Handle list_available_tickers tool execution."""
    import json
    try:
        result = await adapter.list_available_tickers(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.error("list_tickers_error", error=str(e))
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def handle_system_status(adapter) -> Sequence[TextContent]:
    """Handle get_system_status tool execution."""
    import json
    try:
        result = await adapter.get_system_status()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.error("system_status_error", error=str(e))
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


# Optimization tools
def get_optimization_tool_def() -> Tool:
    """Get tool definition for optimize_strategy."""
    return Tool(
        name="optimize_strategy",
        description="Optimize strategy parameters using walk-forward analysis",
        inputSchema={
            "type": "object",
            "properties": {
                "strategy_type": {"type": "string", "enum": ["momentum", "value", "momentum_value"]},
                "tickers": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "region": {"type": "string", "enum": ["KR", "US"], "default": "KR"}
            },
            "required": ["strategy_type", "tickers", "start_date", "end_date"]
        }
    )


async def handle_optimize_strategy(adapter, arguments: Any) -> Sequence[TextContent]:
    """Handle optimize_strategy tool execution."""
    import json
    try:
        result = await adapter.optimize(**arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logger.error("optimization_error", error=str(e))
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
