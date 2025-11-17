# mcp_server/tools/optimization_tools.py
"""
Optimization MCP Tools

MCP tools for walk-forward optimization and parameter tuning.
Thin wrapper around OptimizationAdapter with MCP protocol compliance.
"""

from typing import Any, Sequence
import structlog

from mcp.server import Server
from mcp.types import Tool, TextContent

from ..adapters.optimization_adapter import OptimizationAdapter
from ..utils.errors import ValidationError, DatabaseError, SpockMCPError

logger = structlog.get_logger()


def register_optimization_tools(server: Server) -> None:
    """
    Register optimization tools with MCP server.

    Registers:
    - optimize_strategy: Walk-forward parameter optimization with overfitting detection

    Args:
        server: MCP Server instance
    """
    # Initialize OptimizationAdapter (shared across all tool calls)
    adapter = OptimizationAdapter()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available optimization tools."""
        return [
            Tool(
                name="optimize_strategy",
                description=(
                    "Run walk-forward optimization for strategy parameters. "
                    "Uses time-series cross-validation to find optimal parameters "
                    "while detecting overfitting. Returns best parameters, "
                    "robustness score, and performance degradation metrics."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_type": {
                            "type": "string",
                            "description": "Strategy type to optimize",
                            "enum": ["momentum", "value", "momentum_value"]
                        },
                        "tickers": {
                            "type": "array",
                            "description": "List of ticker symbols to optimize on",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 100
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optimization start date (YYYY-MM-DD)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optimization end date (YYYY-MM-DD)",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        },
                        "region": {
                            "type": "string",
                            "description": "Market region code",
                            "enum": ["CN", "HK", "JP", "KR", "US", "VN"],
                            "default": "KR"
                        },
                        "param_grid": {
                            "type": "object",
                            "description": "Parameter grid to search (e.g., {\"rsi_period\": [10, 14, 20]}). If not provided, uses default grid.",
                            "additionalProperties": {
                                "type": "array",
                                "items": {}
                            }
                        },
                        "train_period_days": {
                            "type": "integer",
                            "description": "Training period length in days (default: 252 / 1 year)",
                            "minimum": 30,
                            "maximum": 1825,
                            "default": 252
                        },
                        "test_period_days": {
                            "type": "integer",
                            "description": "Testing period length in days (default: 63 / 3 months)",
                            "minimum": 10,
                            "maximum": 365,
                            "default": 63
                        },
                        "initial_capital": {
                            "type": "number",
                            "description": "Initial capital amount (default: 100M KRW)",
                            "minimum": 1000000,
                            "default": 100000000
                        },
                        "risk_profile": {
                            "type": "string",
                            "description": "Risk profile (default: moderate)",
                            "enum": ["conservative", "moderate", "aggressive"],
                            "default": "moderate"
                        },
                        "metric": {
                            "type": "string",
                            "description": "Optimization metric (default: sharpe_ratio)",
                            "enum": [
                                "sharpe_ratio",
                                "sortino_ratio",
                                "total_return",
                                "annualized_return",
                                "calmar_ratio"
                            ],
                            "default": "sharpe_ratio"
                        },
                        "anchored": {
                            "type": "boolean",
                            "description": "Use anchored (vs rolling) windows (default: false)",
                            "default": false
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
            name: Tool name (optimize_strategy)
            arguments: Tool arguments dict

        Returns:
            List of TextContent responses

        Raises:
            ValueError: If tool name is invalid
        """
        if name != "optimize_strategy":
            raise ValueError(f"Unknown tool: {name}")

        try:
            # Extract arguments with defaults
            strategy_type = arguments["strategy_type"]
            tickers = arguments["tickers"]
            start_date = arguments["start_date"]
            end_date = arguments["end_date"]
            region = arguments.get("region", "KR")
            param_grid = arguments.get("param_grid")
            train_period_days = arguments.get("train_period_days", 252)
            test_period_days = arguments.get("test_period_days", 63)
            initial_capital = arguments.get("initial_capital", 100_000_000)
            risk_profile = arguments.get("risk_profile", "moderate")
            metric = arguments.get("metric", "sharpe_ratio")
            anchored = arguments.get("anchored", False)

            logger.info(
                "optimize_strategy_start",
                strategy_type=strategy_type,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region,
                metric=metric
            )

            # Run optimization
            result = await adapter.optimize_strategy(
                strategy_type=strategy_type,
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                region=region,
                param_grid=param_grid,
                train_period_days=train_period_days,
                test_period_days=test_period_days,
                initial_capital=initial_capital,
                risk_profile=risk_profile,
                metric=metric,
                anchored=anchored
            )

            # Format response
            import json
            response_text = json.dumps(result, indent=2, ensure_ascii=False)

            logger.info(
                "optimize_strategy_success",
                strategy_type=strategy_type,
                best_params=result.get("optimization", {}).get("best_params"),
                robustness_score=result.get("validation", {}).get("robustness_score")
            )

            return [TextContent(type="text", text=response_text)]

        except ValidationError as e:
            logger.warning(f"optimize_strategy_validation_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(
                type="text",
                text=json.dumps(error_response, indent=2, ensure_ascii=False)
            )]

        except DatabaseError as e:
            logger.error(f"optimize_strategy_database_error", error=str(e))
            error_response = e.to_dict()
            import json
            return [TextContent(
                type="text",
                text=json.dumps(error_response, indent=2, ensure_ascii=False)
            )]

        except Exception as e:
            logger.error(f"optimize_strategy_unexpected_error", error=str(e), exc_info=True)
            error_response = SpockMCPError(
                "INTERNAL_ERROR",
                f"Unexpected error: {str(e)}",
                {"type": type(e).__name__}
            ).to_dict()
            import json
            return [TextContent(
                type="text",
                text=json.dumps(error_response, indent=2, ensure_ascii=False)
            )]

    logger.info("optimization_tools_registered", tool_count=1)
