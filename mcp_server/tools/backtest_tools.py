# mcp_server/tools/backtest_tools.py
"""
Backtest MCP Tools

MCP tools for running strategy backtests.
Thin wrapper around BacktestAdapter with MCP protocol compliance.
"""

from typing import Any, Sequence
import structlog

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..adapters.backtest_adapter import BacktestAdapter
from ..utils.validators import validate_tickers, validate_date_range
from ..utils.formatters import format_backtest_response
from ..utils.errors import (
    ValidationError,
    DataNotFoundError,
    DatabaseError,
    BacktestError,
)

logger = structlog.get_logger()


def register_backtest_tools(server: Server) -> None:
    """
    Register backtest tools with MCP server.

    Registers:
    - run_backtest: Run strategy backtest with specified parameters

    Args:
        server: MCP Server instance
    """
    # Initialize BacktestAdapter (shared across all tool calls)
    adapter = BacktestAdapter()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available backtest tools."""
        return [
            Tool(
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
                    "- fundamental_quality_growth: ROE + debt ratio + growth rates with annual rebalancing "
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
                        "strategy_type": {
                            "type": "string",
                            "description": (
                                "Strategy type to backtest. "
                                "momentum: RSI + moving average crossover. "
                                "value: P/E, P/B, dividend yield factors. "
                                "momentum_value: Combined momentum + value. "
                                "fundamental_quality_growth: ROE + debt ratio + growth rates (annual rebalancing)."
                            ),
                            "enum": ["momentum", "value", "momentum_value", "fundamental_quality_growth"]
                        },
                        "tickers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "List of ticker symbols to backtest. "
                                "KR format: 6-digit numeric (e.g., 005930 for Samsung). "
                                "US format: 1-5 uppercase letters (e.g., AAPL for Apple). "
                                "Maximum 100 tickers per backtest."
                            ),
                            "minItems": 1,
                            "maxItems": 100
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Backtest start date in YYYY-MM-DD format (inclusive)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Backtest end date in YYYY-MM-DD format (inclusive)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "region": {
                            "type": "string",
                            "description": "Market region code",
                            "enum": ["CN", "HK", "JP", "KR", "US", "VN"],
                            "default": "KR"
                        },
                        "engine": {
                            "type": "string",
                            "description": (
                                "Backtesting engine. "
                                "vectorbt: 100x faster, ideal for parameter optimization. "
                                "custom: Production accuracy, event-driven simulation."
                            ),
                            "enum": ["vectorbt", "custom"],
                            "default": "vectorbt"
                        },
                        "initial_capital": {
                            "type": "number",
                            "description": "Initial capital amount in local currency",
                            "default": 100000000,
                            "minimum": 1000000
                        },
                        "risk_profile": {
                            "type": "string",
                            "description": (
                                "Risk management profile. "
                                "conservative: Lower position sizes, higher score threshold. "
                                "moderate: Balanced risk/return. "
                                "aggressive: Larger positions, lower threshold."
                            ),
                            "enum": ["conservative", "moderate", "aggressive"],
                            "default": "moderate"
                        },
                        "parameters": {
                            "type": "object",
                            "description": (
                                "Optional strategy-specific parameters. "
                                "momentum: {rsi_period: 14, ma_short: 20, ma_long: 50}. "
                                "value: {pe_threshold: 15, pb_threshold: 1.5}. "
                                "fundamental_quality_growth: {roe_min: 15.0, debt_to_equity_max: 100.0, "
                                "net_income_growth_min: 10.0, revenue_growth_min: 10.0, "
                                "require_growth: false (default), top_n: 10, rebalance_freq_days: 252}. "
                                "Set require_growth=true to make YOY growth mandatory, false for optional (flexible mode)."
                            ),
                            "default": {}
                        }
                    },
                    "required": ["strategy_type", "tickers", "start_date", "end_date"]
                }
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
        """
        Handle MCP tool calls.

        Args:
            name: Tool name (must be "run_backtest")
            arguments: Tool arguments dict

        Returns:
            List of TextContent responses

        Raises:
            ValueError: If tool name is invalid
        """
        if name != "run_backtest":
            raise ValueError(f"Unknown tool: {name}")

        # Extract arguments with defaults
        strategy_type = arguments.get("strategy_type")
        tickers = arguments.get("tickers", [])
        start_date = arguments.get("start_date")
        end_date = arguments.get("end_date")
        region = arguments.get("region", "KR")
        engine = arguments.get("engine", "vectorbt")
        initial_capital = arguments.get("initial_capital", 100_000_000)
        risk_profile = arguments.get("risk_profile", "moderate")
        parameters = arguments.get("parameters", {})

        try:
            # Step 1: Validate inputs
            logger.info(
                "run_backtest_start",
                strategy_type=strategy_type,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region,
                engine=engine
            )

            validate_tickers(tickers, region)
            validate_date_range(start_date, end_date)

            # Validate strategy type
            if strategy_type not in ["momentum", "value", "momentum_value", "fundamental_quality_growth"]:
                raise ValidationError(
                    "Invalid strategy type",
                    {
                        "strategy_type": strategy_type,
                        "valid_types": ["momentum", "value", "momentum_value", "fundamental_quality_growth"]
                    }
                )

            # Validate risk profile
            if risk_profile not in ["conservative", "moderate", "aggressive"]:
                raise ValidationError(
                    "Invalid risk profile",
                    {
                        "risk_profile": risk_profile,
                        "valid_profiles": ["conservative", "moderate", "aggressive"]
                    }
                )

            # Step 2: Run backtest
            result = await adapter.run_backtest(
                strategy_type=strategy_type,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region,
                engine=engine,
                initial_capital=initial_capital,
                risk_profile=risk_profile,
                parameters=parameters
            )

            # Step 3: Format response
            response_text = format_backtest_response(result)

            logger.info(
                "run_backtest_success",
                strategy_type=strategy_type,
                engine=engine,
                total_return=result.get("performance", {}).get("total_return"),
                sharpe_ratio=result.get("performance", {}).get("sharpe_ratio")
            )

            return [TextContent(type="text", text=response_text)]

        except ValidationError as e:
            logger.warning("run_backtest_validation_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except DataNotFoundError as e:
            logger.warning("run_backtest_not_found", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except DatabaseError as e:
            logger.error("run_backtest_database_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except BacktestError as e:
            logger.error("run_backtest_execution_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

        except Exception as e:
            logger.error("run_backtest_unexpected_error", error=str(e), exc_info=True)
            from ..utils.errors import SpockMCPError
            error_response = SpockMCPError(
                "INTERNAL_ERROR",
                f"Unexpected error: {str(e)}",
                {"type": type(e).__name__}
            ).to_dict()
            import json
            return [TextContent(type="text", text=json.dumps(error_response, indent=2, ensure_ascii=False))]

    logger.info("backtest_tools_registered", tool_count=1)
